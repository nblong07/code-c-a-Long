import os
import sys
import re
import json
import time
import subprocess
import multiprocessing as mp
import torch
from faster_whisper import WhisperModel

# ================= CẤU HÌNH =================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("VIDEO_DIR", r"C:\video_test")
OUTPUT_FILE = os.path.join(BASE_DIR, "asr_results.jsonl")
ISSUES_FILE = os.path.join(BASE_DIR, "asr_issues.jsonl")
PIPELINE_VERSION = "v3.0-whisper"

MAX_VIDEO_RETRIES = 2
NUM_WORKERS = 1  # 6GB VRAM dictates exactly 1 worker for ASR model
_worker_engine = None

def is_junk_asr_segment(segment, text: str) -> bool:
    """Lọc bỏ âm thanh nền, nhạc rác, ảo giác lặp từ hoặc quảng cáo kết video"""
    # 1. Đoạn có xác suất không phải tiếng người cao (nhạc nền to, tiếng ồn)
    if hasattr(segment, "no_speech_prob") and segment.no_speech_prob > 0.65:
        return True

    # 2. Điểm tin cậy quá thấp (nhiễu âm nặng)
    if hasattr(segment, "avg_logprob") and segment.avg_logprob < -1.3:
        return True

    # 3. Ký tự quá ngắn hoặc thán từ vô nghĩa
    clean = re.sub(r'[^\w\s]', '', text).strip().lower()
    if len(clean) < 2:
        return True
    if clean in {"ừ", "ờ", "à", "uhm", "uh", "ah", "um", "ồ", "ê", "hả", "dạ", "vâng"}:
        return True

    # 4. Ảo giác lặp từ (Whisper hallucination: lặp lại 1 từ liên tục)
    words = clean.split()
    if len(words) >= 4 and len(set(words)) == 1:
        return True

    # 5. Mẫu câu quảng cáo kênh / lời cảm ơn outro không mang giá trị ngữ nghĩa tìm kiếm
    junk_patterns = [
        "hãy like và subscribe",
        "đăng ký kênh để",
        "nhấn chuông thông báo",
        "phụ đề thực hiện bởi",
        "phụ đề bởi",
        "subtitles by",
        "cảm ơn các bạn đã theo dõi",
        "hẹn gặp lại trong các video",
    ]
    if any(p in clean for p in junk_patterns) and len(words) <= 12:
        return True

    return False

class FasterWhisperASR:
    def __init__(self):
        print("⚡ Khởi tạo Faster-Whisper Large-v3-Turbo / Large-v3 (int8_float16 GPU Tensor Cores) cho 6GB VRAM...")
        model_candidates = ["deepdml/faster-whisper-large-v3-turbo", "large-v3-turbo", "large-v3"]
        self.model = None
        self.batched_model = None
        
        for m_name in model_candidates:
            try:
                print(f"🔄 Thử nạp model ASR: {m_name}...")
                self.model = WhisperModel(m_name, device="cuda", compute_type="int8_float16", cpu_threads=6)
                print(f"✅ Nạp thành công model: {m_name} trên CUDA Tensor Cores!")
                break
            except Exception as e:
                try:
                    self.model = WhisperModel(m_name, device="cuda", compute_type="float16", cpu_threads=6)
                    print(f"✅ Nạp thành công model: {m_name} trên CUDA (float16)!")
                    break
                except Exception:
                    continue
        
        if self.model is None:
            print("⚠️ Chuyển sang nạp Whisper Large-v3 trên CPU (int8)...")
            self.model = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=6)
            
        # Thử kích hoạt BatchedInferencePipeline để tăng tốc bóc băng song song theo batch audio
        try:
            from faster_whisper import BatchedInferencePipeline
            self.batched_model = BatchedInferencePipeline(model=self.model)
            print("🚀 Đã kích hoạt Faster-Whisper BatchedInferencePipeline (Tăng tốc xử lý audio đa luồng)!")
        except Exception:
            self.batched_model = None
            
    def transcribe_video(self, video_path: str):
        start_time = time.time()
        segments_data = []
        counters = {"ok": 0, "failed": 0, "filtered": 0, "empty": 0}
        
        try:
            if self.batched_model is not None:
                # Batched transcription với batch_size=36 (tối ưu Tensor Cores, VRAM ~2.2GB, bóc audio siêu tốc)
                segments, info = self.batched_model.transcribe(
                    video_path,
                    batch_size=36,
                    language="vi",
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=300, speech_pad_ms=200)
                )
            else:
                segments, info = self.model.transcribe(
                    video_path,
                    beam_size=1,
                    language="vi",
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=350, speech_pad_ms=200)
                )
            
            for i, segment in enumerate(segments):
                text = segment.text.strip()
                if not text:
                    counters["empty"] += 1
                    continue

                # Lọc bỏ rác âm thanh, nhạc nền và quảng cáo
                if is_junk_asr_segment(segment, text):
                    counters["filtered"] += 1
                    continue

                counters["ok"] += 1
                segments_data.append({
                    "segment_id": i,
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "language": "vi",
                    "text": text,
                    "status": "ok"
                })
                
            return {
                "status": "completed",
                "video_path": video_path,
                "duration_sec": round(info.duration, 2),
                "segments": segments_data,
                "num_segments": len(segments_data),
                "successful_segments": counters["ok"],
                "failed_segments": counters["failed"],
                "filtered_segments": counters["filtered"],
                "empty_segments": counters["empty"],
                "elapsed_sec": round(time.time() - start_time, 2)
            }
        except Exception as e:
            return {
                "status": "failed",
                "video_path": video_path,
                "error": str(e),
                "segments": [],
                "num_segments": 0,
                "successful_segments": 0,
                "failed_segments": 1,
                "filtered_segments": 0,
                "empty_segments": 0,
                "elapsed_sec": round(time.time() - start_time, 2)
            }

def init_worker():
    global _worker_engine
    _worker_engine = FasterWhisperASR()

def process_worker(job):
    video_path = job["video_path"]
    attempt = job.get("attempt", 1)
    result = _worker_engine.transcribe_video(video_path)
    result["attempt"] = attempt
    return result

def write_result(result):
    video_path = result.get("video_path")
    status = result.get("status")

    if status in {"completed", "completed_with_issues"}:
        summary = {
            "pipeline_version": PIPELINE_VERSION,
            "video_path": video_path,
            "status": status,
            "duration_sec": result.get("duration_sec", 0),
            "num_segments": result.get("num_segments", 0),
            "successful_segments": result.get("successful_segments", 0),
            "failed_segments": result.get("failed_segments", 0),
            "filtered_segments": result.get("filtered_segments", 0),
            "empty_segments": result.get("empty_segments", 0),
            "elapsed_sec": result.get("elapsed_sec", 0),
            "attempt": result.get("attempt", 1),
        }

        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            for segment in result.get("segments", []):
                f.write(json.dumps({"pipeline_version": PIPELINE_VERSION, "video_path": video_path, **segment}, ensure_ascii=False) + "\n")
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")

def load_completed_videos():
    completed = set()
    if not os.path.isfile(OUTPUT_FILE): return completed
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                if record.get("status") == "completed":
                    completed.add(record["video_path"])
            except: pass
    return completed

def discover_videos():
    extensions = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv")
    videos = []
    if not os.path.isdir(DATA_DIR): return videos
    for root, _, files in os.walk(DATA_DIR):
        for file in files:
            if file.lower().endswith(extensions):
                videos.append(os.path.join(root, file))
    return sorted(set(videos))

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    videos = discover_videos()
    completed = load_completed_videos()
    pending = [{"video_path": p, "attempt": 1} for p in videos if p not in completed]

    print(f"📊 Tổng video: {len(videos)} | Đã xong: {len(completed)} | Cần xử lý: {len(pending)}", flush=True)
    if not pending:
        print("🎉 Toàn bộ video đã được bóc băng ASR hoàn tất 100%!", flush=True)
        return

    for attempt in range(1, MAX_VIDEO_RETRIES + 2):
        if not pending:
            break
        print(f"\n--- Lần chạy {attempt} ({len(pending)} video cần xử lý) ---", flush=True)

        init_worker()
        next_pending = []
        total_pending = len(pending)
        for idx, job in enumerate(pending, 1):
            vid_name = os.path.basename(job["video_path"])
            print(f"[{idx}/{total_pending}] 🎙️ Đang nghe: {vid_name}...", end="", flush=True)
            result = process_worker(job)
            write_result(result)
            if result.get("status") == "completed":
                dur = result.get("duration_sec", 0)
                segs = result.get("num_segments", 0)
                elapsed = result.get("elapsed_sec", 0)
                print(f" -> ✅ Xong! ({dur/60:.1f} phút | {segs} câu thoại | mất {elapsed:.1f}s)", flush=True)
            else:
                err = result.get("error", "Lỗi")
                print(f" -> ❌ Thất bại: {err}", flush=True)
                job["attempt"] += 1
                next_pending.append(job)
        pending = next_pending

    print("\n🎉 Bóc băng giọng nói (ASR) đã hoàn tất toàn bộ!", flush=True)


if __name__ == "__main__":
    main()
