import os
import json
import time
import tarfile
import tempfile
import urllib.request
import subprocess
import multiprocessing as mp
from collections import deque
from typing import Optional

import numpy as np

# ================= CẤU HÌNH =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data-videos")
MODEL_DIR = os.path.join(BASE_DIR, "models", "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09")
VAD_MODEL_PATH = os.path.join(BASE_DIR, "models", "silero_vad.onnx")
OUTPUT_FILE = os.path.join(BASE_DIR, "asr_results.jsonl")
ISSUES_FILE = os.path.join(BASE_DIR, "asr_issues.jsonl")
PIPELINE_VERSION = "v2.3"

MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09.tar.bz2"
)
VAD_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "silero_vad.onnx"
)

SAMPLE_RATE = 16000
AUDIO_CHUNK_SECONDS = 5
AUDIO_CHUNK_BYTES = SAMPLE_RATE * AUDIO_CHUNK_SECONDS * 2

VAD_THRESHOLD = 0.5
VAD_MIN_SILENCE = 0.3
VAD_MIN_SPEECH = 0.25
VAD_BUFFER_SECONDS = 30

MAX_SEGMENT_SECONDS = 120.0
CONTEXT_PADDING_SECONDS = 0.3
MIN_ASR_SEGMENT_SECONDS = 0.5
MERGE_GAP_SECONDS = 0.5

# Chỉ dùng khi safety-split bắt buộc; ưu tiên điểm có năng lượng thấp trước.
SPLIT_SEARCH_SECONDS = 2.0
SPLIT_OVERLAP_SECONDS = 0.2

ENABLE_PEAK_NORMALIZATION = False
NORMALIZATION_TARGET_PEAK = 0.95
MAX_NORMALIZATION_GAIN = 3.0

ASR_PROVIDER_MODE = os.environ.get("ASR_PROVIDER", "auto").lower()
ASR_NUM_THREADS = max(1, int(os.environ.get("ASR_NUM_THREADS", "1")))
MAX_VIDEO_RETRIES = 2
ISSUE_STATUSES = {"filtered", "failed", "empty"}

_worker_engine = None


# ================= PROVIDER / CPU-GPU =================
def _nvidia_available() -> bool:
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return False


def detect_provider() -> str:
    if ASR_PROVIDER_MODE in {"cpu", "cuda", "coreml"}:
        return ASR_PROVIDER_MODE
    if ASR_PROVIDER_MODE != "auto":
        raise ValueError("ASR_PROVIDER phải là auto, cpu, cuda hoặc coreml")
    return "cuda" if _nvidia_available() else "cpu"


ASR_PROVIDER = detect_provider()
_DEFAULT_WORKERS = 1 if ASR_PROVIDER == "cuda" else max(1, min(2, (os.cpu_count() or 2) // 2))
NUM_WORKERS = max(1, int(os.environ.get("ASR_NUM_WORKERS", str(_DEFAULT_WORKERS))))
if ASR_PROVIDER == "cuda" and NUM_WORKERS != 1:
    print("⚠️ CUDA: ép NUM_WORKERS=1 để tránh nhân bản model trên GPU và OOM VRAM.")
    NUM_WORKERS = 1


# ================= MODEL / PATH =================
def safe_extract_tar(archive_path: str, target_dir: str):
    target_dir = os.path.abspath(target_dir)
    with tarfile.open(archive_path, "r:*") as tar:
        for member in tar.getmembers():
            member_path = os.path.abspath(os.path.join(target_dir, member.name))
            if not (member_path == target_dir or member_path.startswith(target_dir + os.sep)):
                raise RuntimeError(f"Archive path không an toàn: {member.name}")
            if member.issym() or member.islnk():
                raise RuntimeError(f"Archive chứa symlink/hardlink không an toàn: {member.name}")
        tar.extractall(target_dir)


def get_model_paths():
    return {
        "encoder": os.path.join(MODEL_DIR, "encoder.int8.onnx"),
        "decoder": os.path.join(MODEL_DIR, "decoder.onnx"),
        "joiner": os.path.join(MODEL_DIR, "joiner.int8.onnx"),
        "tokens": os.path.join(MODEL_DIR, "tokens.txt"),
        "silero_vad": VAD_MODEL_PATH,
    }


def _download_atomic(url: str, target_path: str):
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".download_", suffix=".tmp", dir=os.path.dirname(target_path))
    os.close(fd)
    try:
        urllib.request.urlretrieve(url, tmp_path)
        with open(tmp_path, "rb") as f:
            os.fsync(f.fileno())
        os.replace(tmp_path, target_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def ensure_models_downloaded():
    paths = get_model_paths()
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(VAD_MODEL_PATH), exist_ok=True)
    required = [paths["encoder"], paths["decoder"], paths["joiner"], paths["tokens"], paths["silero_vad"]]

    if all(os.path.isfile(p) for p in required):
        return

    if not all(os.path.isfile(paths[k]) for k in ("encoder", "decoder", "joiner", "tokens")):
        archive_path = MODEL_DIR + ".tar.bz2"
        print("🚀 Đang tải Vietnamese Zipformer 30M...")
        _download_atomic(MODEL_URL, archive_path)
        try:
            safe_extract_tar(archive_path, os.path.dirname(MODEL_DIR))
        finally:
            if os.path.exists(archive_path):
                os.remove(archive_path)

    if not os.path.isfile(paths["silero_vad"]):
        print("🚀 Đang tải Silero VAD...")
        _download_atomic(VAD_URL, paths["silero_vad"])

    missing = [p for p in required if not os.path.isfile(p)]
    if missing:
        raise FileNotFoundError("Thiếu model files:\n" + "\n".join(missing))


# ================= AUDIO RING BUFFER =================
class AudioRingBuffer:
    """Giữ audio theo absolute sample index, hạn chế copy/slice khi trim."""

    def __init__(self, max_seconds: float, sample_rate: int = SAMPLE_RATE):
        self.max_samples = max(1, int(max_seconds * sample_rate))
        self.chunks = deque()
        self.left_offset = 0
        self.start_sample = 0
        self.end_sample = 0

    def append(self, samples: np.ndarray):
        samples = np.asarray(samples, dtype=np.float32)
        if len(samples) == 0:
            return
        self.chunks.append(samples)
        self.end_sample += len(samples)

        excess = self.end_sample - self.start_sample - self.max_samples
        while excess > 0 and self.chunks:
            first_len = len(self.chunks[0]) - self.left_offset
            remove = min(excess, first_len)
            self.start_sample += remove
            self.left_offset += remove
            excess -= remove
            if self.left_offset == len(self.chunks[0]):
                self.chunks.popleft()
                self.left_offset = 0

    def get(self, start_sample: int, end_sample: int, allow_clamp: bool = False) -> Optional[np.ndarray]:
        if start_sample >= end_sample:
            return None
        if allow_clamp:
            start_sample = max(self.start_sample, start_sample)
            end_sample = min(self.end_sample, end_sample)
        elif start_sample < self.start_sample or end_sample > self.end_sample:
            return None
        if start_sample >= end_sample:
            return None

        pieces = []
        cursor = self.start_sample
        first = True

        for chunk in self.chunks:
            offset = self.left_offset if first else 0
            first = False
            chunk_start = cursor
            chunk_end = chunk_start + len(chunk) - offset
            left = max(start_sample, chunk_start)
            right = min(end_sample, chunk_end)
            if left < right:
                pieces.append(chunk[offset + left - chunk_start:offset + right - chunk_start])
            cursor = chunk_end
            if cursor >= end_sample:
                break

        return np.concatenate(pieces) if pieces else None


# ================= ASR ENGINE =================
class SherpaZipformerASR:
    def __init__(self, num_threads=ASR_NUM_THREADS):
        self.num_threads = max(1, int(num_threads))
        self.provider = ASR_PROVIDER
        self.recognizer = None
        self.vad_config = None
        self.vad = None
        self.is_ready = False
        self._initialize()

    def _initialize(self):
        try:
            import sherpa_onnx
        except ImportError as e:
            raise ImportError("Chưa cài sherpa-onnx: pip install sherpa-onnx") from e

        paths = get_model_paths()
        missing = [p for p in [paths["encoder"], paths["decoder"], paths["joiner"], paths["tokens"], paths["silero_vad"]] if not os.path.isfile(p)]
        if missing:
            raise FileNotFoundError("Thiếu model files:\n" + "\n".join(missing))

        kwargs = dict(
            encoder=paths["encoder"],
            decoder=paths["decoder"],
            joiner=paths["joiner"],
            tokens=paths["tokens"],
            num_threads=self.num_threads,
            sample_rate=SAMPLE_RATE,
            feature_dim=80,
            decoding_method="greedy_search",
            provider=self.provider,
        )

        try:
            self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(**kwargs)
        except Exception as e:
            if self.provider != "cpu":
                print(f"⚠️ Không khởi tạo được provider={self.provider}: {e}")
                print("↩️ Fallback sang CPU.")
                self.provider = "cpu"
                kwargs["provider"] = "cpu"
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(**kwargs)
            else:
                raise

        self.vad_config = sherpa_onnx.VadModelConfig()
        self.vad_config.silero_vad.model = paths["silero_vad"]
        self.vad_config.silero_vad.threshold = VAD_THRESHOLD
        self.vad_config.silero_vad.min_silence_duration = VAD_MIN_SILENCE
        self.vad_config.silero_vad.min_speech_duration = VAD_MIN_SPEECH
        if hasattr(self.vad_config.silero_vad, "max_speech_duration"):
            self.vad_config.silero_vad.max_speech_duration = MAX_SEGMENT_SECONDS
        self.vad_config.sample_rate = SAMPLE_RATE
        if hasattr(self.vad_config, "num_threads"):
            self.vad_config.num_threads = 1

        self.vad = self._new_vad()
        self.is_ready = True
        print(f"✅ ASR ready | provider={self.provider} | threads={self.num_threads}")

    def _new_vad(self):
        import sherpa_onnx
        return sherpa_onnx.VoiceActivityDetector(self.vad_config, buffer_size_in_seconds=VAD_BUFFER_SECONDS)

    def reset_vad(self):
        if self.vad is None:
            self.vad = self._new_vad()
            return
        reset_fn = getattr(self.vad, "reset", None)
        if callable(reset_fn):
            reset_fn()
        else:
            self.vad = self._new_vad()

    def stream_audio(self, video_path: str):
        command = [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-i", video_path, "-vn", "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"
        ]

        with tempfile.TemporaryFile() as stderr_file:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr_file, bufsize=0)
            remainder = b""
            try:
                while True:
                    data = process.stdout.read(AUDIO_CHUNK_BYTES)
                    if not data and not remainder:
                        break
                    data = remainder + data
                    if len(data) % 2:
                        remainder, data = data[-1:], data[:-1]
                    else:
                        remainder = b""
                    if data:
                        yield np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

                rc = process.wait()
                if rc != 0:
                    stderr_file.seek(0)
                    err_msg = stderr_file.read().decode(errors="ignore").strip()
                    raise RuntimeError(f"FFmpeg failed: {err_msg[-1000:]}")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    @staticmethod
    def _normalize_audio(samples: np.ndarray) -> np.ndarray:
        if len(samples) == 0:
            return samples
        peak = float(np.max(np.abs(samples)))
        if peak <= 1e-4:
            return samples
        gain = min(NORMALIZATION_TARGET_PEAK / peak, MAX_NORMALIZATION_GAIN)
        if gain <= 1.01:
            return samples
        return np.clip(samples * gain, -1.0, 1.0).astype(np.float32, copy=False)

    def _pop_vad_segments(self):
        segments = []
        while not self.vad.empty():
            seg = self.vad.front
            start = int(seg.start)
            end = start + len(seg.samples)
            segments.append({"start_sample": start, "end_sample": end})
            self.vad.pop()
        return segments

    def _recognize(self, samples: np.ndarray) -> str:
        stream = self.recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples)
        self.recognizer.decode_stream(stream)
        return stream.result.text.strip()

    @staticmethod
    def _rms(samples: np.ndarray) -> float:
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(samples), dtype=np.float64)))

    def _find_silence_cut(self, desired_cut: int, audio_buffer: AudioRingBuffer) -> int:
        search = int(SPLIT_SEARCH_SECONDS * SAMPLE_RATE)
        lo = max(audio_buffer.start_sample, desired_cut - search)
        hi = min(audio_buffer.end_sample, desired_cut + search)
        audio = audio_buffer.get(lo, hi, allow_clamp=False)
        if audio is None:
            return desired_cut

        window = max(1, int(0.02 * SAMPLE_RATE))
        if len(audio) < window:
            return desired_cut

        center = desired_cut - lo
        best_offset = max(0, min(center, len(audio) - window))
        best_score = float("inf")

        for offset in range(0, len(audio) - window + 1, window):
            distance = abs(offset - center)
            if distance > search:
                continue
            rms = self._rms(audio[offset:offset + window])
            score = rms * (1.0 + 0.15 * distance / max(search, 1))
            if score < best_score:
                best_score = score
                best_offset = offset

        return lo + best_offset

    def _split_segment(self, segment, audio_buffer: AudioRingBuffer):
        start = int(segment["start_sample"])
        end = int(segment["end_sample"])
        max_samples = int(MAX_SEGMENT_SECONDS * SAMPLE_RATE)
        overlap = int(SPLIT_OVERLAP_SECONDS * SAMPLE_RATE)
        parts = []

        while end - start > max_samples:
            desired_cut = start + max_samples
            cut = self._find_silence_cut(desired_cut, audio_buffer)
            if cut <= start or cut >= end:
                cut = desired_cut

            parts.append({"start_sample": start, "end_sample": cut})
            start = max(start + 1, cut - overlap)

        if start < end:
            parts.append({"start_sample": start, "end_sample": end})
        return parts

    def _process_vad_segment(self, segment, audio_buffer: AudioRingBuffer, segment_id: int):
        start = int(segment["start_sample"])
        end = int(segment["end_sample"])
        length_sec = (end - start) / SAMPLE_RATE
        base = {
            "segment_id": segment_id,
            "start": round(start / SAMPLE_RATE, 2),
            "end": round(end / SAMPLE_RATE, 2),
            "language": "vi",
        }

        if length_sec < MIN_ASR_SEGMENT_SECONDS:
            return {**base, "text": "", "status": "filtered", "error": "segment_too_short"}, False
        if length_sec > MAX_SEGMENT_SECONDS:
            return {**base, "text": "", "status": "failed", "error": "segment_too_long"}, False
        if start < audio_buffer.start_sample or end > audio_buffer.end_sample:
            return {**base, "text": "", "status": "failed", "error": "audio_buffer_unavailable"}, False

        pad = int(CONTEXT_PADDING_SECONDS * SAMPLE_RATE)
        samples = audio_buffer.get(start - pad, end + pad, allow_clamp=True)
        if samples is None:
            return {**base, "text": "", "status": "failed", "error": "audio_buffer_unavailable"}, False
        if ENABLE_PEAK_NORMALIZATION:
            samples = self._normalize_audio(samples)

        try:
            text = self._recognize(samples)
        except Exception as e:
            return {**base, "text": "", "status": "failed", "error": str(e)}, False
        if not text:
            return {**base, "text": "", "status": "empty"}, False
        return {**base, "text": text, "status": "ok"}, True

    def transcribe_video(self, video_path: str):
        if not self.is_ready:
            return {"status": "failed", "video_path": video_path, "error": "engine_not_ready"}

        self.reset_vad()
        buffer_seconds = MAX_SEGMENT_SECONDS + 2 * CONTEXT_PADDING_SECONDS + MERGE_GAP_SECONDS + AUDIO_CHUNK_SECONDS
        audio_buffer = AudioRingBuffer(buffer_seconds, SAMPLE_RATE)
        merge_gap_samples = int(MERGE_GAP_SECONDS * SAMPLE_RATE)

        pending_segment = None
        segments = []
        counters = {"ok": 0, "failed": 0, "filtered": 0, "empty": 0}
        segment_id = 0
        total_audio_samples = 0

        def add_record(record, ok):
            nonlocal segment_id
            segments.append(record)
            segment_id += 1
            if ok:
                counters["ok"] += 1
            else:
                counters[record.get("status", "failed")] += 1

        def emit_pending():
            nonlocal pending_segment
            if pending_segment is None:
                return
            for part in self._split_segment(pending_segment, audio_buffer):
                record, ok = self._process_vad_segment(part, audio_buffer, segment_id)
                add_record(record, ok)
            pending_segment = None

        def queue_segments(new_segments):
            nonlocal pending_segment
            for current in new_segments:
                if pending_segment is None:
                    pending_segment = current
                    continue
                gap = current["start_sample"] - pending_segment["end_sample"]
                merged_end = max(pending_segment["end_sample"], current["end_sample"])
                merged_duration = (merged_end - pending_segment["start_sample"]) / SAMPLE_RATE
                if 0 <= gap <= merge_gap_samples and merged_duration <= MAX_SEGMENT_SECONDS:
                    pending_segment["end_sample"] = merged_end
                else:
                    emit_pending()
                    pending_segment = current

        try:
            saw_audio = False
            for samples in self.stream_audio(video_path):
                if len(samples) == 0:
                    continue
                saw_audio = True
                total_audio_samples += len(samples)
                audio_buffer.append(samples)
                self.vad.accept_waveform(samples)
                queue_segments(self._pop_vad_segments())

                if pending_segment is not None:
                    available_after_end = audio_buffer.end_sample - pending_segment["end_sample"]
                    wait_samples = merge_gap_samples + int(CONTEXT_PADDING_SECONDS * SAMPLE_RATE)
                    if available_after_end >= wait_samples:
                        emit_pending()

            self.vad.flush()
            queue_segments(self._pop_vad_segments())
            emit_pending()

            if not saw_audio:
                return {"status": "failed", "video_path": video_path, "error": "no_audio_stream", "segments": []}

            duration_sec = total_audio_samples / SAMPLE_RATE
            status = "completed_with_issues" if any(counters[k] for k in ("failed", "filtered", "empty")) else "completed"

            return {
                "status": status,
                "video_path": video_path,
                "duration_sec": round(duration_sec, 2),
                "segments": segments,
                "num_segments": segment_id,
                "successful_segments": counters["ok"],
                "failed_segments": counters["failed"],
                "filtered_segments": counters["filtered"],
                "empty_segments": counters["empty"],
            }
        except Exception as e:
            return {
                "status": "failed",
                "video_path": video_path,
                "error": str(e),
                "segments": segments,
                "num_segments": segment_id,
                "successful_segments": counters["ok"],
                "failed_segments": counters["failed"],
                "filtered_segments": counters["filtered"],
                "empty_segments": counters["empty"],
            }


# ================= BATCH / RESUME =================
def init_worker():
    global _worker_engine
    _worker_engine = SherpaZipformerASR(ASR_NUM_THREADS)


def process_worker(job):
    video_path = job["video_path"]
    attempt = job.get("attempt", 1)
    start = time.time()
    try:
        result = _worker_engine.transcribe_video(video_path)
        result["elapsed_sec"] = round(time.time() - start, 2)
        result["attempt"] = attempt
        return result
    except Exception as e:
        return {
            "status": "failed",
            "video_path": video_path,
            "error": str(e),
            "segments": [],
            "attempt": attempt,
            "elapsed_sec": round(time.time() - start, 2),
        }


def _read_output_blocks():
    """Chỉ giữ block có summary hoàn chỉnh; block dở sẽ bị loại khi resume."""
    blocks = {}
    current_video = None
    current_lines = []
    invalid = False

    def finish():
        nonlocal current_video, current_lines, invalid
        if current_video and current_lines and not invalid:
            try:
                summary = json.loads(current_lines[-1])
                if summary.get("status") in {"completed", "completed_with_issues"}:
                    blocks[current_video] = list(current_lines)
            except json.JSONDecodeError:
                pass
        current_video = None
        current_lines = []
        invalid = False

    if not os.path.isfile(OUTPUT_FILE):
        return blocks

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                invalid = True
                continue

            video_path = record.get("video_path")
            if not video_path:
                invalid = True
                continue

            if current_video is None:
                current_video = video_path
            elif video_path != current_video:
                finish()
                current_video = video_path
            current_lines.append(line)

        finish()
    return blocks


def repair_output_file():
    blocks = _read_output_blocks()
    if not os.path.isfile(OUTPUT_FILE):
        return

    fd, tmp_path = tempfile.mkstemp(prefix=".asr_repair_", suffix=".tmp", dir=BASE_DIR)
    os.close(fd)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            for lines in blocks.values():
                f.writelines(line + "\n" for line in lines)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, OUTPUT_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def load_completed_videos():
    repair_output_file()
    completed = set()
    if not os.path.isfile(OUTPUT_FILE):
        return completed

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("video_path") and record.get("status") in {"completed", "completed_with_issues"}:
                completed.add(record["video_path"])
    return completed


def _atomic_append_block(lines):
    """Stage + fsync trước; main process vẫn là nơi append vào master JSONL."""
    fd, tmp_path = tempfile.mkstemp(prefix=".asr_block_", suffix=".tmp", dir=BASE_DIR)
    os.close(fd)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
            f.flush()
            os.fsync(f.fileno())

        with open(OUTPUT_FILE, "ab") as out, open(tmp_path, "rb") as src:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def write_result(result):
    video_path = result.get("video_path")
    status = result.get("status")

    if status in {"completed", "completed_with_issues"}:
        summary = {
            "pipeline_version": PIPELINE_VERSION,
            "video_path": video_path,
            "status": status,
            "provider": ASR_PROVIDER,
            "duration_sec": result.get("duration_sec", 0),
            "num_segments": result.get("num_segments", 0),
            "successful_segments": result.get("successful_segments", 0),
            "failed_segments": result.get("failed_segments", 0),
            "filtered_segments": result.get("filtered_segments", 0),
            "empty_segments": result.get("empty_segments", 0),
            "elapsed_sec": result.get("elapsed_sec", 0),
            "attempt": result.get("attempt", 1),
        }

        lines = [
            json.dumps(
                {
                    "pipeline_version": PIPELINE_VERSION,
                    "video_path": video_path,
                    **segment,
                },
                ensure_ascii=False,
            ) + "\n"
            for segment in result.get("segments", [])
        ]
        lines.append(json.dumps(summary, ensure_ascii=False) + "\n")
        _atomic_append_block(lines)

    issue_lines = []
    if status == "failed":
        issue_lines.append(
            json.dumps(
                {
                    "pipeline_version": PIPELINE_VERSION,
                    "video_path": video_path,
                    "status": "failed_video",
                    "error": result.get("error", "unknown_error"),
                    "attempt": result.get("attempt", 1),
                },
                ensure_ascii=False,
            ) + "\n"
        )

    issue_lines.extend(
        json.dumps(
            {
                "pipeline_version": PIPELINE_VERSION,
                "video_path": video_path,
                **segment,
            },
            ensure_ascii=False,
        ) + "\n"
        for segment in result.get("segments", [])
        if segment.get("status") in ISSUE_STATUSES
    )

    if issue_lines:
        with open(ISSUES_FILE, "ab") as f:
            for line in issue_lines:
                f.write(line.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())


def discover_videos():
    extensions = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv")
    videos = []
    for name in os.listdir(DATA_DIR):
        path = os.path.join(DATA_DIR, name)
        if os.path.isfile(path):
            if name.lower().endswith(extensions):
                videos.append(path)
            continue
        if os.path.isdir(path):
            for child in os.listdir(path):
                child_path = os.path.join(path, child)
                if os.path.isfile(child_path) and child.lower().endswith(extensions):
                    videos.append(child_path)
    return sorted(set(videos))


def main():
    ensure_models_downloaded()

    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"Đã tạo DATA_DIR: {DATA_DIR}")
        return

    videos = discover_videos()
    completed = load_completed_videos()
    pending = [{"video_path": p, "attempt": 1} for p in videos if p not in completed]

    print(f"Tổng: {len(videos)} | Đã xong: {len(completed)} | Còn lại: {len(pending)}")
    print(f"Provider: {ASR_PROVIDER} | Workers: {NUM_WORKERS} | ASR threads/worker: {ASR_NUM_THREADS}")

    if ASR_PROVIDER == "cuda":
        print("GPU mode: NUM_WORKERS=1 để tránh nhân bản model trên cùng GPU.")

    if NUM_WORKERS * ASR_NUM_THREADS > (os.cpu_count() or 1):
        print("⚠️ Cảnh báo: workers × threads vượt CPU logic.")

    if not pending:
        return

    remaining = pending
    for attempt in range(1, MAX_VIDEO_RETRIES + 2):
        if not remaining:
            break

        jobs = [{"video_path": job["video_path"], "attempt": attempt} for job in remaining]
        next_remaining = []
        print(f"\n--- Attempt {attempt} ({len(jobs)} video) ---")

        try:
            with mp.Pool(processes=NUM_WORKERS, initializer=init_worker) as pool:
                for result in pool.imap_unordered(process_worker, jobs):
                    status = result.get("status")
                    write_result(result)
                    print(
                        f"[{status}] {result.get('video_path')} | "
                        f"segments={result.get('num_segments', 0)} | "
                        f"time={result.get('elapsed_sec', 0)}s"
                    )
                    if status == "failed":
                        next_remaining.append({"video_path": result.get("video_path")})
        except KeyboardInterrupt:
            print("\n⚠️ Dừng bằng Ctrl+C. Video chưa hoàn tất sẽ chạy lại ở lần sau.")
            return

        remaining = next_remaining
        if remaining and attempt <= MAX_VIDEO_RETRIES:
            print(f"🔁 Retry {len(remaining)} video lỗi...")

    if remaining:
        print(f"\n⚠️ Còn {len(remaining)} video failed sau retry.")
    else:
        print("\n✅ Pipeline hoàn tất.")


if __name__ == "__main__":
    mp.freeze_support()
    main()
