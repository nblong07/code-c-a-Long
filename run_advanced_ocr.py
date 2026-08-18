import csv
import gc
import glob
import json
import logging
import multiprocessing as mp
import os
import re
import tempfile
import subprocess
import time
import shutil
import warnings
from collections import Counter, deque
from pathlib import Path

# Cấu hình backend Paddle/PIR/oneDNN và giới hạn native threads phải đặt
# trước khi import NumPy/OpenCV/Paddle/PyTorch.
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import cv2
import numpy as np

warnings.filterwarnings("ignore", category=UserWarning)

LOG_LEVEL = os.environ.get("OCR_LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("OCR_LOG_FILE", "")
_logger = logging.getLogger("video_ocr")
if not _logger.handlers:
    _logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(processName)s | %(message)s"
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    _logger.addHandler(console)
    if LOG_FILE:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)
    _logger.propagate = False

# ================= CẤU HÌNH =================
KEYFRAME_ROOT = os.environ.get("KEYFRAME_ROOT", "/app/data-keyframes")
KEYFRAME_MAP_ROOT = os.environ.get("KEYFRAME_MAP_ROOT", os.path.join(KEYFRAME_ROOT, "maps"))
OUTPUT_FILE = os.environ.get("OCR_OUTPUT_FILE", "/app/ocr_results.jsonl")
PIPELINE_VERSION = "v5.10-hardened"

CROP_BOTTOM_RATIO = float(os.environ.get("OCR_CROP_BOTTOM_RATIO", "0.45"))
TICKER_BAND_RATIO = float(os.environ.get("OCR_TICKER_BAND_RATIO", "0.35"))
OCR_MAX_WIDTH = max(320, int(os.environ.get("OCR_MAX_WIDTH", "960")))
MIN_CROP_WIDTH = max(50, int(os.environ.get("OCR_MIN_CROP_WIDTH", "50")))
MIN_CROP_HEIGHT = max(20, int(os.environ.get("OCR_MIN_CROP_HEIGHT", "20")))

CONFIDENCE_THRESHOLD = float(os.environ.get("OCR_CONFIDENCE_THRESHOLD", "0.40"))
HARD_CONFIDENCE_THRESHOLD = float(os.environ.get("OCR_HARD_CONFIDENCE_THRESHOLD", "0.70"))
MIN_TEXT_LEN = max(1, int(os.environ.get("OCR_MIN_TEXT_LEN", "3")))
TOP_K = max(1, min(5, int(os.environ.get("OCR_TOP_K", "5"))))

OCR_BATCH_SIZE_RAW = os.environ.get("OCR_BATCH_SIZE", "auto").strip().lower()
if OCR_BATCH_SIZE_RAW == "auto":
    BATCH_SIZE = 8
else:
    try:
        BATCH_SIZE = max(1, int(OCR_BATCH_SIZE_RAW))
    except ValueError as e:
        raise ValueError("OCR_BATCH_SIZE phải là số nguyên >= 1 hoặc 'auto'") from e

AUTO_BATCH_SIZE = OCR_BATCH_SIZE_RAW == "auto"
MAX_AUTO_BATCH_SIZE = max(1, int(os.environ.get("OCR_MAX_BATCH_SIZE", "16")))
MIN_AUTO_BATCH_SIZE = max(1, int(os.environ.get("OCR_MIN_BATCH_SIZE", "2")))
FLUSH_EVERY_RECORDS = max(20, int(os.environ.get("OCR_FLUSH_EVERY", "200")))  # compatibility; temp file is fsynced per OCR batch
CPU_COUNT = os.cpu_count() or 2
DEFAULT_WORKERS = max(1, min(4, CPU_COUNT // 2 or 1))
NUM_WORKERS = max(1, int(os.environ.get("OCR_NUM_WORKERS", DEFAULT_WORKERS)))
# Keep total Paddle CPU parallelism bounded: workers x Paddle threads should
# not accidentally oversubscribe a small container. Explicit env still wins.
_CPU_THREADS_ENV = os.environ.get("OCR_CPU_THREADS")
if _CPU_THREADS_ENV is None:
    OCR_CPU_THREADS = max(1, CPU_COUNT // max(1, NUM_WORKERS))
else:
    OCR_CPU_THREADS = max(1, int(_CPU_THREADS_ENV))
MAX_TASKS_PER_CHILD = max(1, int(os.environ.get("OCR_MAX_TASKS_PER_CHILD", "30")))
# Safety cap: never let a worker accumulate an unbounded number of tasks.
MAX_TASKS_PER_CHILD = min(MAX_TASKS_PER_CHILD, 1000)
LOCK_ACQUIRE_TIMEOUT = max(5.0, float(os.environ.get("OCR_LOCK_TIMEOUT", "120")))
TEMP_MAX_AGE_SECONDS = max(3600.0, float(os.environ.get("OCR_TEMP_MAX_AGE_HOURS", "24")) * 3600.0)

TITLE_DUPLICATE_DIFF_THRESHOLD = float(os.environ.get("OCR_TITLE_DIFF_THRESHOLD", "6.0"))
TICKER_DUPLICATE_DIFF_THRESHOLD = float(os.environ.get("OCR_TICKER_DIFF_THRESHOLD", "8.0"))
SIGNATURE_SIZE = (64, 24)

OCR_GPU_ENV = os.environ.get("OCR_GPU", "auto").strip().lower()
OCR_GPU_VALUES = {"", "auto", "0", "1", "false", "true", "no", "yes", "cuda", "gpu"}
if OCR_GPU_ENV not in OCR_GPU_VALUES:
    raise ValueError("OCR_GPU phải là auto, 0/false hoặc 1/true/cuda/gpu")

KEYFRAME_FPS = float(os.environ.get("KEYFRAME_FPS", "0"))
USE_INTERVAL_MIDPOINT = os.environ.get("OCR_USE_INTERVAL_MIDPOINT", "1").lower() in {"1", "true", "yes"}
TIMESTAMP_DECIMALS = max(0, int(os.environ.get("OCR_TIMESTAMP_DECIMALS", "3")))

ENABLE_EASYOCR_FALLBACK = os.environ.get("OCR_ENABLE_EASYOCR_FALLBACK", "1").lower() in {"1", "true", "yes"}
ENABLE_HARD_PREPROCESS = os.environ.get("OCR_ENABLE_HARD_PREPROCESS", "1").lower() in {"1", "true", "yes"}
ENABLE_SPELL_FIX = os.environ.get("OCR_ENABLE_SPELL_FIX", "0").lower() in {"1", "true", "yes"}
CONSENSUS_WINDOW = max(2, int(os.environ.get("OCR_CONSENSUS_WINDOW", "5")))

SPELL_FIX_MAP = {
    "iuong": "lương", "ivong": "lương", "luong": "lương",
    "tuong": "thương", "thvong": "thương",
    "huong": "hưởng", "hvong": "hưởng", "huởng": "hưởng", "hvởng": "hưởng",
    "nguoi": "người", "nguòi": "người", "nguời": "người",
    "duong": "đường", "duờng": "đường", "dường": "đường",
    "cuong": "cường", "phuong": "phường", "chuong": "chương",
    "truong": "trường", "truờng": "trường", "vuon": "vươn", "duoc": "được",
}
_SPELL_FIX_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in SPELL_FIX_MAP) + r")\b",
    re.IGNORECASE,
)

_worker_ocr = None
_worker_easyocr = None
_worker_lock = None
_worker_gpu = False
_worker_provider = "unknown"


# ================= TEXT / SCORE =================
def normalize_text(text):
    text = " ".join(str(text or "").split()).strip()
    if not ENABLE_SPELL_FIX:
        return text

    def replace(match):
        word = match.group(0)
        fixed = SPELL_FIX_MAP[word.lower()]
        if word.isupper():
            return fixed.upper()
        return fixed.capitalize() if word[0].isupper() else fixed

    return _SPELL_FIX_RE.sub(replace, text)


def text_quality(text):
    if not text:
        return 0.0
    valid = sum(ch.isalnum() or ch.isspace() or ch in ".,:;!?'-_/()%+&" for ch in text)
    ratio = valid / max(1, len(text))
    length_score = min(1.0, len(text) / 12.0)
    return 0.65 * ratio + 0.35 * length_score


def format_timestamp(seconds):
    if seconds is None:
        return None
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def candidate_score(confidence, sources, quality, consensus):
    source_bonus = min(1.0, len(sources) / 2.0)
    return (
        0.55 * confidence
        + 0.15 * source_bonus
        + 0.10 * quality
        + 0.20 * consensus
    )


def rank_candidates(candidates, recent_texts=()):
    merged = {}
    counts = Counter(t.casefold() for t in recent_texts if t)

    for item in candidates:
        text = normalize_text(item.get("text", ""))
        if len(text) < MIN_TEXT_LEN:
            continue
        key = text.casefold()
        conf = max(0.0, min(1.0, float(item.get("confidence", 0.0))))
        source = item.get("source", "unknown")
        variant = item.get("variant", "original")

        current = merged.setdefault(
            key,
            {
                "text": text,
                "confidence": conf,
                "sources": set(),
                "variants": set(),
            },
        )
        current["confidence"] = max(current["confidence"], conf)
        current["sources"].add(source)
        current["variants"].add(variant)

    ranked = []
    for item in merged.values():
        consensus = min(1.0, counts[item["text"].casefold()] / max(1, CONSENSUS_WINDOW))
        quality = text_quality(item["text"])
        score = candidate_score(
            item["confidence"],
            item["sources"],
            quality,
            consensus,
        )
        ranked.append(
            {
                "text": item["text"],
                "confidence": round(item["confidence"], 3),
                "score": round(score, 4),
                "sources": sorted(item["sources"]),
                "variants": sorted(item["variants"]),
                "consensus": round(consensus, 3),
            }
        )

    ranked.sort(
        key=lambda x: (x["score"], x["confidence"], len(x["text"])),
        reverse=True,
    )
    return ranked[:TOP_K]


# ================= IMAGE / DEDUP =================
def resize_for_ocr(img):
    if img is None or img.size == 0:
        return img
    h, w = img.shape[:2]
    if w <= OCR_MAX_WIDTH:
        return img
    scale = OCR_MAX_WIDTH / float(w)
    return cv2.resize(
        img,
        (OCR_MAX_WIDTH, max(1, int(h * scale))),
        interpolation=cv2.INTER_AREA,
    )


def make_signature(region):
    if region is None or region.size == 0:
        return None
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, SIGNATURE_SIZE, interpolation=cv2.INTER_AREA).astype(np.float32)
    mean, std = float(small.mean()), float(small.std())
    if std > 1e-3:
        small = (small - mean) / std
    return small


def mean_abs_diff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return float("inf")
    return float(np.mean(np.abs(a - b)))


def is_duplicate(prev_title, cur_title, prev_ticker, cur_ticker):
    if any(x is None for x in (prev_title, cur_title, prev_ticker, cur_ticker)):
        return False
    return (
        mean_abs_diff(prev_title, cur_title) < TITLE_DUPLICATE_DIFF_THRESHOLD
        and mean_abs_diff(prev_ticker, cur_ticker) < TICKER_DUPLICATE_DIFF_THRESHOLD
    )


def _safe_imread(path):
    """Read an image with OpenCV, with a Unicode-path fallback for Windows."""
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is not None:
        return img
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size:
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    except (OSError, ValueError, cv2.error):
        img = None
    return img


def preprocess_cv2(img_path):
    img = _safe_imread(img_path)
    if img is None:
        return None, None, None

    h, w = img.shape[:2]
    if h < MIN_CROP_HEIGHT or w < MIN_CROP_WIDTH:
        return None, None, None

    crop_top = min(max(int(h * (1.0 - CROP_BOTTOM_RATIO)), 0), h - 1)
    cropped = img[crop_top:, :]
    if cropped.size == 0:
        return None, None, None

    ch = cropped.shape[0]
    ticker_top = min(max(int(ch * (1.0 - TICKER_BAND_RATIO)), 1), ch - 1)
    title_sig = make_signature(cropped[:ticker_top, :])
    ticker_sig = make_signature(cropped[ticker_top:, :])
    full_rgb = resize_for_ocr(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
    return full_rgb, title_sig, ticker_sig


def preprocess_variants(img):
    variants = [("original", img)]
    if not ENABLE_HARD_PREPROCESS or img is None or img.size == 0:
        return variants

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    variants.append(("clahe", cv2.cvtColor(clahe, cv2.COLOR_GRAY2RGB)))

    blur = cv2.GaussianBlur(clahe, (0, 0), 1.0)
    sharp = cv2.addWeighted(clahe, 1.35, blur, -0.35, 0)
    variants.append(("sharpen", cv2.cvtColor(sharp, cv2.COLOR_GRAY2RGB)))
    return variants


# ================= TIMESTAMP =================
def parse_frame_id(path):
    stem = Path(path).stem
    m = re.search(r"keyframe[_-]?(.+)$", stem, re.IGNORECASE)
    return m.group(1) if m else stem


def canonical_frame_id(frame_id):
    """Normalize numeric frame IDs such as 001, frame_001 and keyframe_001."""
    value = str(frame_id or "").strip()
    if not value:
        return value
    match = re.fullmatch(
        r"(?:frame[_-]?|keyframe[_-]?)?(\d+)(?:\.0+)?",
        value,
        re.IGNORECASE,
    )
    return str(int(match.group(1))) if match else value


def _frame_order_key(frame_id):
    """Deterministic natural ordering for frame IDs, numeric when possible."""
    value = str(frame_id or "").strip()
    canonical = canonical_frame_id(value)
    if canonical.isdigit():
        return (0, int(canonical), "")
    return (1, canonical.casefold(), value.casefold())


def parse_timestamp_from_filename(path):
    stem = Path(path).stem

    m = re.search(r"(?:^|[_-])ts[_-]?(\d+(?:\.\d+)?)s?(?:[_-]|$)", stem, re.IGNORECASE)
    if m:
        return float(m.group(1))

    m = re.search(r"(?:^|[_-])(\d+(?:\.\d+)?)ms(?:[_-]|$)", stem, re.IGNORECASE)
    if m:
        return float(m.group(1)) / 1000.0

    m = re.search(r"(?:^|[_-])(\d+\.\d+)(?:[_-]|$)", stem)
    return float(m.group(1)) if m else None


def find_map_csv(video_id):
    candidates = (
        os.path.join(KEYFRAME_MAP_ROOT, f"{video_id}_map.csv"),
        os.path.join(os.path.dirname(KEYFRAME_ROOT), "maps", f"{video_id}_map.csv"),
    )
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def load_timestamp_map(video_id):
    path = find_map_csv(video_id)
    if not path:
        return {}

    mapping = {}
    bad_rows = 0
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = {name.strip() for name in (reader.fieldnames or []) if name}
            if not {"FrameID", "Seconds"}.issubset(fieldnames):
                _logger.warning(f"[timestamp] {path} thiếu cột FrameID/Seconds; sẽ fallback.")
                return {}

            for row in reader:
                frame_id = str(row.get("FrameID", "")).strip()
                seconds = str(row.get("Seconds", "")).strip()
                if not frame_id or not seconds:
                    bad_rows += 1
                    continue
                try:
                    ts = float(seconds)
                    if ts < 0:
                        bad_rows += 1
                        continue
                    frame_key = canonical_frame_id(frame_id)
                    if not frame_key:
                        bad_rows += 1
                        continue
                    mapping[frame_key] = ts
                except (TypeError, ValueError):
                    bad_rows += 1
    except (OSError, csv.Error) as e:
        _logger.warning(f"[timestamp] Không đọc được {path}: {e}; sẽ fallback.")
        return {}

    if bad_rows:
        _logger.warning(
            f"[timestamp] {path}: bỏ qua {bad_rows} dòng lỗi; "
            f"các frame thiếu sẽ fallback theo FPS nếu có."
        )
    return mapping


def resolve_timestamp(path, timestamp_map=None):
    frame_id = parse_frame_id(path)
    normalized_id = canonical_frame_id(frame_id)

    if timestamp_map:
        if normalized_id in timestamp_map:
            return timestamp_map[normalized_id]
        if frame_id in timestamp_map:
            return timestamp_map[frame_id]

    timestamp = parse_timestamp_from_filename(path)
    if timestamp is not None:
        return timestamp
    if KEYFRAME_FPS > 0 and frame_id.isdigit():
        return int(frame_id) / KEYFRAME_FPS
    return None


def add_interval_timestamp(records):
    records.sort(
        key=lambda r: (
            r.get("_keyframe_timestamp") is None,
            r.get("_keyframe_timestamp")
            if r.get("_keyframe_timestamp") is not None
            else float("inf"),
        )
    )
    timestamps = [r.pop("_keyframe_timestamp", None) for r in records]

    for i, record in enumerate(records):
        start = timestamps[i]
        end = timestamps[i + 1] if i + 1 < len(timestamps) else None

        if start is None:
            record.update(
                {
                    "timestamp_sec": None,
                    "timestamp_hms": None,
                    "interval_start_sec": None,
                    "interval_end_sec": None,
                }
            )
            continue

        if end is not None and end >= start:
            timestamp = (start + end) / 2.0 if USE_INTERVAL_MIDPOINT else start
            record.update(
                {
                    "timestamp_sec": round(timestamp, TIMESTAMP_DECIMALS),
                    "timestamp_hms": format_timestamp(timestamp),
                    "interval_start_sec": round(start, TIMESTAMP_DECIMALS),
                    "interval_end_sec": round(end, TIMESTAMP_DECIMALS),
                }
            )
        else:
            record.update(
                {
                    "timestamp_sec": round(start, TIMESTAMP_DECIMALS),
                    "timestamp_hms": format_timestamp(start),
                    "interval_start_sec": round(start, TIMESTAMP_DECIMALS),
                    "interval_end_sec": None,
                }
            )
    return records


# ================= OCR ENGINE =================
def _paddle_init(use_gpu):
    """Khởi tạo PaddleOCR an toàn với CPU/GPU và tương thích API nhiều phiên bản."""
    from paddleocr import PaddleOCR

    kwargs = {
        "lang": "vi",
        "engine": "paddle",
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
    }
    if use_gpu:
        kwargs["device"] = "gpu:0"
    else:
        kwargs.update({
            "device": "cpu",
            "enable_mkldnn": False,
            "cpu_threads": OCR_CPU_THREADS,
        })

    try:
        return PaddleOCR(**kwargs)
    except TypeError as exc:
        msg = str(exc).lower()
        # Chỉ bỏ các keyword được xác định là không được phiên bản hiện tại hỗ trợ.
        removable = []
        for key in ("cpu_threads", "enable_mkldnn", "engine"):
            if key in msg or "unexpected keyword" in msg:
                removable.append(key)
        if not removable:
            raise
        for key in removable:
            kwargs.pop(key, None)
        return PaddleOCR(**kwargs)


def _is_oom_error(exc):
    """Nhận diện lỗi thiếu bộ nhớ GPU."""
    msg = str(exc).lower()
    return (
        "out of memory" in msg
        or "cuda error: out of memory" in msg
        or "cuda out of memory" in msg
        or "memory boundary" in msg
        or "resource exhausted" in msg
    )


def _empty_gpu_cache():
    if not _worker_gpu:
        return
    try:
        import paddle
        if paddle.device.is_compiled_with_cuda():
            paddle.device.cuda.empty_cache()
    except Exception:
        pass


def _clear_inference_cache():
    """Best-effort cache cleanup; never turns cleanup failure into OCR failure."""
    try:
        _empty_gpu_cache()
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _safe_result_list(result):
    """Normalize PaddleOCR predict() output without silently fabricating records."""
    if result is None:
        return []
    if isinstance(result, (list, tuple)):
        return list(result)
    try:
        return list(result)
    except TypeError:
        return [result]


def _predict_single(img):
    result = _worker_ocr.predict(img)
    if isinstance(result, (list, tuple)) and len(result) == 1:
        return result[0]
    return result


def _paddle_predict(images):
    """Run every image exactly once per successful attempt, preserving 1:1 order."""
    global BATCH_SIZE
    if _worker_ocr is None or not images:
        return []

    all_results = []
    index = 0
    total = len(images)

    while index < total:
        current_batch = max(1, min(BATCH_SIZE, total - index))
        batch = images[index:index + current_batch]

        try:
            result = _safe_result_list(_worker_ocr.predict(batch))

            # A batch result must map 1:1 to the input batch. Never silently
            # shift OCR results to another frame.
            if len(result) != len(batch):
                if len(batch) == 1:
                    # Some adapters return a single result object rather than [obj].
                    if len(result) == 1:
                        all_results.append(result[0])
                    else:
                        raise RuntimeError(
                            f"PaddleOCR trả {len(result)} kết quả cho 1 ảnh."
                        )
                else:
                    raise RuntimeError(
                        f"PaddleOCR trả {len(result)} kết quả cho {len(batch)} ảnh."
                    )
            else:
                all_results.extend(result)

            index += len(batch)

        except TypeError as exc:
            # New PaddleOCR/PaddleX APIs do not accept batch_size=...; this
            # implementation intentionally never passes that keyword.
            msg = str(exc).lower()
            if not any(token in msg for token in (
                "list", "iterable", "positional argument", "argument type",
                "input", "image"
            )):
                raise

            _logger.warning(
                "PaddleOCR.predict() không nhận batch list; fallback từng ảnh."
            )
            for img in batch:
                single = _safe_result_list(_worker_ocr.predict(img))
                if len(single) == 1:
                    all_results.append(single[0])
                elif len(single) == 0:
                    all_results.append(None)
                else:
                    raise RuntimeError(
                        f"PaddleOCR single-image trả {len(single)} kết quả."
                    )
            index += len(batch)

        except Exception as exc:
            if _worker_gpu and AUTO_BATCH_SIZE and _is_oom_error(exc) and current_batch > 1:
                new_batch = max(1, current_batch // 2)
                _logger.warning(
                    "Paddle CUDA OOM tại index %d với batch=%d; giảm batch xuống %d.",
                    index, current_batch, new_batch,
                )
                BATCH_SIZE = new_batch
                _clear_inference_cache()
                # Retry the same input batch; index is intentionally unchanged.
                continue

            _logger.exception(
                "Paddle batch inference thất bại tại index %d (batch=%d).",
                index, current_batch,
            )
            raise

    return all_results


def _ensure_easyocr_fallback():
    global _worker_easyocr
    if _worker_easyocr is not None or not ENABLE_EASYOCR_FALLBACK:
        return _worker_easyocr

    try:
        import easyocr
        _worker_easyocr = easyocr.Reader(["vi", "en"], gpu=False, verbose=False)
        _logger.info(f"EasyOCR fallback ready | provider=cpu | pid={os.getpid()}")
    except Exception:
        _logger.exception("Không khởi tạo được EasyOCR fallback")
        _worker_easyocr = None
    return _worker_easyocr


def _detect_free_vram_mb():
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode != 0:
            return None
        values = []
        for line in result.stdout.splitlines():
            try:
                values.append(int(float(line.strip())))
            except ValueError:
                continue
        return max(values) if values else None
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None


def _auto_batch_from_vram():
    free_mb = _detect_free_vram_mb()
    if free_mb is None:
        return min(8, MAX_AUTO_BATCH_SIZE), None

    if free_mb >= 12000:
        batch = 16
    elif free_mb >= 8000:
        batch = 12
    elif free_mb >= 6000:
        batch = 8
    elif free_mb >= 4000:
        batch = 4
    else:
        batch = 2

    return min(MAX_AUTO_BATCH_SIZE, max(MIN_AUTO_BATCH_SIZE, batch)), free_mb


def _configure_batch_size():
    global BATCH_SIZE
    if not AUTO_BATCH_SIZE:
        return

    if not _worker_gpu:
        BATCH_SIZE = min(8, MAX_AUTO_BATCH_SIZE)
        _logger.info(f"CPU batch tự động={BATCH_SIZE}")
        return

    batch, free_mb = _auto_batch_from_vram()
    BATCH_SIZE = batch
    if free_mb is None:
        _logger.warning(f"Không lấy được VRAM; dùng batch bảo thủ={BATCH_SIZE}")
    else:
        _logger.info(f"VRAM khả dụng ~{free_mb} MB; batch tự động={BATCH_SIZE}")


def init_worker(lock, use_gpu):
    global _worker_ocr, _worker_easyocr, _worker_lock, _worker_gpu, _worker_provider
    _worker_lock = lock
    _worker_easyocr = None
    _worker_gpu = use_gpu
    _worker_provider = "unknown"

    cv2.setNumThreads(1)
    if not use_gpu:
        try:
            import torch
            torch.set_num_threads(1)
        except Exception:
            pass

    try:
        _worker_ocr = _paddle_init(use_gpu)
        _worker_provider = "paddle-cuda" if use_gpu else "paddle-cpu"
    except Exception:
        _logger.exception("PaddleOCR init lỗi")
        if not ENABLE_EASYOCR_FALLBACK:
            raise
        reader = _ensure_easyocr_fallback()
        if reader is None:
            raise RuntimeError("PaddleOCR khởi tạo thất bại và EasyOCR fallback không khả dụng.")
        _worker_provider = "easyocr-cpu-fallback"
        _worker_gpu = False

    _configure_batch_size()
    _logger.info(
        f"OCR ready | provider={_worker_provider} | pid={os.getpid()} | batch={BATCH_SIZE}"
    )


def _result_json(result):
    data = getattr(result, "json", None)
    if callable(data):
        data = data()
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return {}
    if isinstance(data, dict):
        return data
    return {}


def parse_paddle_result(result):
    data = _result_json(result)
    if "res" in data and isinstance(data["res"], dict):
        data = data["res"]

    texts = data.get("rec_texts", []) or []
    scores = data.get("rec_scores", []) or []
    boxes = data.get("rec_boxes", data.get("rec_polys", [])) or []
    items = []

    for i, text in enumerate(texts):
        text = normalize_text(text)
        try:
            conf = float(scores[i])
        except (IndexError, TypeError, ValueError):
            conf = 0.0
        if len(text) < MIN_TEXT_LEN or conf < CONFIDENCE_THRESHOLD:
            continue

        y = None
        if i < len(boxes):
            try:
                box = np.asarray(boxes[i], dtype=np.float32).reshape(-1, 2)
                y = float(box[:, 1].mean())
            except Exception:
                pass
        items.append((y if y is not None else float("inf"), text, conf))

    items.sort(key=lambda x: (x[0], x[1].casefold()))
    if not items:
        return []

    return [
        {
            "text": " | ".join(x[1] for x in items),
            "confidence": round(float(np.mean([x[2] for x in items])), 3),
            "source": "paddle",
            "variant": "original",
        }
    ]


def parse_easyocr_result(result):
    items = []
    for item in result or []:
        if len(item) < 3:
            continue
        text = normalize_text(item[1])
        try:
            conf = float(item[2])
        except (TypeError, ValueError):
            conf = 0.0
        if len(text) >= MIN_TEXT_LEN and conf >= CONFIDENCE_THRESHOLD:
            items.append((text, conf))

    if not items:
        return []

    return [
        {
            "text": " | ".join(x[0] for x in items),
            "confidence": round(float(np.mean([x[1] for x in items])), 3),
            "source": "easyocr",
            "variant": "original",
        }
    ]


def _easyocr_one(image):
    reader = _ensure_easyocr_fallback()
    if reader is None:
        return []
    try:
        # EasyOCR already performs inference without gradients internally in
        # normal releases; no_grad here is an additional best-effort guard.
        try:
            import torch
            with torch.no_grad():
                raw = reader.readtext(
                    image, detail=1, paragraph=False, decoder="greedy"
                )
        except (ImportError, AttributeError):
            raw = reader.readtext(
                image, detail=1, paragraph=False, decoder="greedy"
            )
        return parse_easyocr_result(raw)
    except Exception as exc:
        _logger.warning(f"EasyOCR fallback lỗi: {exc}")
        return []

def ocr_pending_items(items, recent_texts):
    """OCR each shape bucket separately; preserves original item order."""
    if not items:
        return []

    if len(items) == 1:
        result = ocr_batch([items[0]["img"]], recent_texts)
        return result

    indexed = list(enumerate(items))
    indexed_buckets = {}
    for idx, item in indexed:
        indexed_buckets.setdefault(tuple(item["img"].shape), []).append((idx, item))

    results = [None] * len(items)
    for bucket in indexed_buckets.values():
        bucket_results = ocr_batch(
            [item["img"] for _, item in bucket],
            recent_texts,
        )
        for (idx, _), result in zip(bucket, bucket_results):
            results[idx] = result

    return results


def ocr_batch(images, recent_texts):
    if not images:
        return []

    raw = _paddle_predict(images)
    if len(raw) != len(images):
        raw = [None] * len(images)

    outputs = []
    hard_indices = []

    for i, result in enumerate(raw):
        candidates = parse_paddle_result(result) if result is not None else []
        ranked = rank_candidates(candidates, recent_texts)
        outputs.append(
            {
                "text": ranked[0]["text"] if ranked else "",
                "confidence": ranked[0]["confidence"] if ranked else 0.0,
                "top_candidates": ranked,
            }
        )
        if not ranked or ranked[0]["confidence"] < HARD_CONFIDENCE_THRESHOLD:
            hard_indices.append(i)

    # Chỉ làm preprocessing/fallback cho frame khó.
    for i in hard_indices:
        candidates = parse_paddle_result(raw[i]) if raw[i] is not None else []
        if ENABLE_HARD_PREPROCESS:
            for variant, image in preprocess_variants(images[i])[1:]:
                extra = _paddle_predict([image])
                if extra:
                    for item in parse_paddle_result(extra[0]):
                        item["variant"] = variant
                        item["source"] = "preprocess"
                        candidates.append(item)

        if (not candidates or max(x["confidence"] for x in candidates) < HARD_CONFIDENCE_THRESHOLD) and ENABLE_EASYOCR_FALLBACK:
            candidates.extend(_easyocr_one(images[i]))

        ranked = rank_candidates(candidates, recent_texts)
        outputs[i] = {
            "text": ranked[0]["text"] if ranked else "",
            "confidence": ranked[0]["confidence"] if ranked else 0.0,
            "top_candidates": ranked,
        }

    return outputs


# ================= OUTPUT / RESUME =================
def _check_rewrite_disk_space(required_bytes=0):
    """Best-effort preflight; never replaces the existing output on low disk."""
    directory = os.path.dirname(os.path.abspath(OUTPUT_FILE)) or "."
    try:
        free = shutil.disk_usage(directory).free
    except OSError:
        return
    safety_margin = 16 * 1024 * 1024
    if free < required_bytes + safety_margin:
        raise OSError(
            f"Không đủ dung lượng đĩa để rewrite OCR: còn {free / (1024**2):.1f} MB"
        )


def atomic_rewrite(records):
    directory = os.path.dirname(os.path.abspath(OUTPUT_FILE)) or "."
    os.makedirs(directory, exist_ok=True)
    estimated = sum(len(json.dumps(r, ensure_ascii=False)) + 1 for r in records)
    _check_rewrite_disk_space(estimated)
    try:
        fd, temp_path = tempfile.mkstemp(prefix=".ocr_rewrite_", suffix=".tmp", dir=directory)
    except OSError as e:
        raise RuntimeError(
            f"Không thể tạo file rewrite OCR; có thể ổ đĩa đầy: {e}"
        ) from e

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, OUTPUT_FILE)

        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def atomic_rewrite_ranges(ranges):
    """Atomically rewrite OUTPUT_FILE by copying selected byte ranges only.

    This keeps resume-cleanup memory bounded even when ocr_results.jsonl is very large.
    """
    directory = os.path.dirname(os.path.abspath(OUTPUT_FILE)) or "."
    os.makedirs(directory, exist_ok=True)
    try:
        source_size = os.path.getsize(OUTPUT_FILE)
    except OSError as e:
        raise RuntimeError(f"Không thể xác định kích thước output OCR: {e}") from e
    selected_bytes = sum(max(0, end - start) for start, end in ranges)
    _check_rewrite_disk_space(selected_bytes)
    try:
        fd, temp_path = tempfile.mkstemp(
            prefix=".ocr_rewrite_", suffix=".tmp", dir=directory
        )
    except OSError as e:
        raise RuntimeError(
            f"Không thể tạo file rewrite OCR; có thể ổ đĩa đầy: {e}"
        ) from e

    try:
        with os.fdopen(fd, "wb") as dst, open(OUTPUT_FILE, "rb") as src:
            for start, end in ranges:
                if end <= start:
                    continue
                src.seek(start)
                remaining = end - start
                while remaining:
                    chunk = src.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise OSError("EOF bất ngờ khi atomic rewrite output OCR")
                    dst.write(chunk)
                    remaining -= len(chunk)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(temp_path, OUTPUT_FILE)
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def load_done_videos_and_clean_partial():
    """Find completed videos and remove interrupted/duplicate blocks with bounded RAM."""
    if not os.path.isfile(OUTPUT_FILE):
        return set()

    latest_ranges = {}
    completion_seq = 0
    current_video = None
    current_start = None
    current_valid = True
    current_done = False
    rewrite_needed = False

    def finish_block(end_pos):
        nonlocal current_video, current_start, current_valid, current_done, rewrite_needed, completion_seq
        if current_video is not None and current_start is not None:
            if current_done and current_valid:
                completion_seq += 1
                if current_video in latest_ranges:
                    rewrite_needed = True
                latest_ranges[current_video] = (completion_seq, current_start, end_pos)
            else:
                rewrite_needed = True
        current_video = None
        current_start = None
        current_valid = True
        current_done = False

    try:
        with open(OUTPUT_FILE, "rb") as f:
            while True:
                line_start = f.tell()
                raw = f.readline()
                if not raw:
                    end_pos = f.tell()
                    if current_video is not None:
                        finish_block(end_pos)
                    break

                line = raw.strip()
                if not line:
                    rewrite_needed = True
                    continue

                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    rewrite_needed = True
                    current_valid = False
                    continue

                video_id = record.get("video_id")
                if not video_id:
                    rewrite_needed = True
                    current_valid = False
                    continue

                if current_video is None:
                    current_video = video_id
                    current_start = line_start
                    current_valid = True
                elif video_id != current_video:
                    finish_block(line_start)
                    current_video = video_id
                    current_start = line_start
                    current_valid = True

                if record.get("video_done"):
                    current_done = True
                    finish_block(f.tell())
    except OSError as e:
        _logger.warning(f"[resume] Không đọc được {OUTPUT_FILE}: {e}")
        return set()

    # Reconstruct the output in original completion order. Keeping only byte ranges
    # avoids loading all OCR records into Python memory.
    if latest_ranges:
        ranges = [
            (item[1], item[2])
            for item in sorted(latest_ranges.values(), key=lambda item: item[0])
        ]
    else:
        ranges = []

    # Detect whether the file already consists exactly of one complete block per video.
    # If not, perform the bounded-memory atomic cleanup.
    try:
        file_size = os.path.getsize(OUTPUT_FILE)
    except OSError:
        file_size = -1

    if rewrite_needed or len(latest_ranges) == 0:
        try:
            if ranges:
                atomic_rewrite_ranges(ranges)
            elif file_size > 0:
                atomic_rewrite_ranges([])
        except (OSError, RuntimeError) as e:
            # Fail-safe: NEVER rename/reset the existing output on cleanup failure.
            # The old file remains available for the next resume attempt.
            _logger.error(
                f"[resume] Cleanup atomic thất bại; giữ nguyên OUTPUT_FILE để bảo toàn dữ liệu: {e}"
            )
    else:
        # A second lightweight structural check is unnecessary when every observed
        # block was complete and unique; latest_ranges then represents the file exactly.
        pass

    return set(latest_ranges)


def append_video_temp(temp_path):
    """Append one complete staged video block without holding the lock during fsync."""
    output_dir = os.path.dirname(os.path.abspath(OUTPUT_FILE)) or "."
    os.makedirs(output_dir, exist_ok=True)
    out = None
    acquired = False
    try:
        if _worker_lock is None:
            raise RuntimeError("Worker lock chưa được khởi tạo.")
        acquired = bool(_worker_lock.acquire(timeout=LOCK_ACQUIRE_TIMEOUT))
        if not acquired:
            raise TimeoutError(
                f"Không lấy được lock ghi OUTPUT_FILE sau {LOCK_ACQUIRE_TIMEOUT:.0f}s"
            )
        try:
            out = open(OUTPUT_FILE, "ab")
            with open(temp_path, "rb") as src:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            out.flush()
        finally:
            # Release serialization lock before potentially slow fsync.
            if acquired:
                _worker_lock.release()
                acquired = False

        # Durability is intentionally outside the inter-worker critical section.
        # The complete video block was already serialized under the lock.
        try:
            os.fsync(out.fileno())
        except OSError as e:
            _logger.warning(f"[I/O] fsync output thất bại: {e}")
        finally:
            out.close()
            out = None
        try:
            dir_fd = os.open(output_dir, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except TimeoutError:
        if acquired and _worker_lock is not None:
            try:
                _worker_lock.release()
            except Exception:
                pass
        if out is not None:
            try:
                out.close()
            except OSError:
                pass
        raise
    except OSError as e:
        if acquired and _worker_lock is not None:
            try:
                _worker_lock.release()
            except Exception:
                pass
        if out is not None:
            try:
                out.close()
            except OSError:
                pass
        raise RuntimeError(f"Không thể ghi output OCR (có thể ổ đĩa đầy): {e}") from e
    except Exception:
        if acquired and _worker_lock is not None:
            try:
                _worker_lock.release()
            except Exception:
                pass
        if out is not None:
            try:
                out.close()
            except OSError:
                pass
        raise


def write_temp_record(f, record):
    f.write(json.dumps(record, ensure_ascii=False) + "\n")


# The pipeline intentionally keeps only: one OCR batch + one staged temp file per video.
# It does not accumulate the whole video's transcript in Python RAM.

def cleanup_orphaned_temp_files():
    """Remove only old OCR temp files owned by this pipeline."""
    output_dir = os.path.dirname(os.path.abspath(OUTPUT_FILE)) or "."
    if not os.path.isdir(output_dir):
        return 0
    prefixes = (".ocr_", ".ocr_final_", ".ocr_rewrite_")
    now = time.time()
    removed = 0
    try:
        for name in os.listdir(output_dir):
            if not name.endswith(".tmp") or not name.startswith(prefixes):
                continue
            path = os.path.join(output_dir, name)
            try:
                age = now - os.path.getmtime(path)
                if age < TEMP_MAX_AGE_SECONDS:
                    continue
                os.remove(path)
                removed += 1
            except OSError:
                continue
    except OSError as e:
        _logger.warning(f"[cleanup] Không quét được temp OCR: {e}")
    if removed:
        _logger.info(f"[cleanup] Đã xóa {removed} temp OCR mồ côi.")
    return removed


# ================= VIDEO =================
def make_record(video_id, frame_id, timestamp, result, reused):
    return {
        "pipeline_version": PIPELINE_VERSION,
        "video_id": video_id,
        "frame_id": frame_id,
        "_keyframe_timestamp": timestamp,
        "text": result.get("text", ""),
        "confidence": result.get("confidence", 0.0),
        "top_candidates": result.get("top_candidates", [])[:TOP_K],
        "reused": reused,
    }


def process_video(video_id):
    start_time = time.time()
    n_images = ocr_runs = skipped_dup = 0
    temp_path = None

    try:
        video_dir = os.path.join(KEYFRAME_ROOT, video_id, "keyframes")
        if not os.path.isdir(video_dir):
            return video_id, 0, 0, 0, 0.0, False

        images = glob.glob(os.path.join(video_dir, "*.webp"))
        if not images:
            return video_id, 0, 0, 0, 0.0, False

        timestamp_map = load_timestamp_map(video_id)
        image_items = [
            (path, parse_frame_id(path), resolve_timestamp(path, timestamp_map))
            for path in images
        ]
        timestamps = [x[2] for x in image_items]
        # Ordering policy:
        #   * all timestamps known -> sort by the real timestamp;
        #   * any timestamp missing -> preserve deterministic frame order.
        # We never move an unknown-timestamp frame to the end merely because
        # it is unknown; that would manufacture false temporal intervals.
        if all(ts is not None for ts in timestamps):
            bad_order = any(
                b < a for a, b in zip(timestamps, timestamps[1:])
            )
            if bad_order:
                _logger.warning(
                    f"[timestamp] {video_id}: timestamp không đơn điệu; "
                    "sắp xếp lại toàn bộ frame theo timestamp thực."
                )
            image_items.sort(
                key=lambda x: (
                    float(x[2]),
                    _frame_order_key(x[1]),
                    x[0],
                )
            )
        else:
            missing = sum(ts is None for ts in timestamps)
            if missing:
                _logger.warning(
                    f"[timestamp] {video_id}: {missing}/{len(image_items)} frame "
                    "thiếu timestamp; giữ thứ tự frame để tránh tạo interval giả."
                )
            image_items.sort(key=lambda x: (_frame_order_key(x[1]), x[0]))

        output_dir = os.path.dirname(os.path.abspath(OUTPUT_FILE)) or "."
        os.makedirs(output_dir, exist_ok=True)
        try:
            fd, temp_path = tempfile.mkstemp(
                prefix=f".ocr_{video_id}_",
                suffix=".tmp",
                dir=output_dir,
            )
        except OSError as e:
            raise RuntimeError(
                f"Không thể tạo file tạm OCR cho video {video_id}; "
                f"có thể ổ đĩa đầy hoặc thư mục không ghi được: {e}"
            ) from e

        recent_texts = deque(maxlen=CONSENSUS_WINDOW)
        anchor_title = anchor_ticker = None
        last_result = {"text": "", "confidence": 0.0, "top_candidates": []}
        pending = []

        with os.fdopen(fd, "w", encoding="utf-8") as temp_f:
            def flush_pending():
                nonlocal pending, ocr_runs, last_result
                if not pending:
                    return

                outputs = ocr_pending_items(
                    pending,
                    list(recent_texts),
                )
                ocr_runs += len(pending)

                for item, result in zip(pending, outputs):
                    write_temp_record(
                        temp_f,
                        make_record(
                            video_id,
                            item["frame_id"],
                            item["timestamp"],
                            result,
                            False,
                        ),
                    )

                    for follower in item["followers"]:
                        write_temp_record(
                            temp_f,
                            make_record(
                                video_id,
                                follower["frame_id"],
                                follower["timestamp"],
                                result,
                                True,
                            ),
                        )
    
                    text = result.get("text", "")
                    if text:
                        recent_texts.append(text)

                last_result = outputs[-1] if outputs else last_result
                temp_f.flush()

                # Giải phóng reference tới numpy images ngay sau batch.
                for item in pending:
                    item["img"] = None
                    item["followers"].clear()
                pending.clear()

            for img_path, frame_id, timestamp in image_items:
                n_images += 1
                try:
                    full_rgb, title_sig, ticker_sig = preprocess_cv2(img_path)
                except Exception as e:
                    _logger.warning(f"Lỗi đọc ảnh {img_path}: {e}")
                    continue

                if full_rgb is None:
                    continue

                duplicate = is_duplicate(
                    anchor_title,
                    title_sig,
                    anchor_ticker,
                    ticker_sig,
                )

                if duplicate and (pending or last_result.get("text")):
                    skipped_dup += 1
                    if pending:
                        pending[-1]["followers"].append(
                            {"frame_id": frame_id, "timestamp": timestamp}
                        )
                    else:
                        write_temp_record(
                            temp_f,
                            make_record(
                                video_id,
                                frame_id,
                                timestamp,
                                last_result,
                                True,
                            ),
                        )
                    continue

                pending.append(
                    {
                        "frame_id": frame_id,
                        "timestamp": timestamp,
                        "img": full_rgb,
                        "followers": [],
                    }
                )
                anchor_title, anchor_ticker = title_sig, ticker_sig

                if len(pending) >= BATCH_SIZE:
                    flush_pending()

            flush_pending()

            temp_f.flush()
            os.fsync(temp_f.fileno())

        # Stream post-processing with one-record lookahead:
        # no full-video transcript list is loaded into RAM.
        try:
            final_fd, final_temp = tempfile.mkstemp(
                prefix=f".ocr_final_{video_id}_",
                suffix=".tmp",
                dir=output_dir,
            )
        except OSError as e:
            raise RuntimeError(
                f"Không thể tạo file hậu xử lý OCR cho video {video_id}; "
                f"có thể ổ đĩa đầy hoặc thư mục không ghi được: {e}"
            ) from e

        wrote_any = False
        event_id = 0
        previous_text = None

        try:
            with os.fdopen(final_fd, "w", encoding="utf-8") as final_f:
                def emit_final(record, next_timestamp):
                    nonlocal wrote_any, event_id, previous_text
                    timestamp = record.pop("_keyframe_timestamp", None)
                    if timestamp is None:
                        record["timestamp_sec"] = None
                        record["timestamp_hms"] = None
                        record["interval_start_sec"] = None
                        record["interval_end_sec"] = None
                    elif next_timestamp is not None and next_timestamp >= timestamp:
                        value = (timestamp + next_timestamp) / 2.0 if USE_INTERVAL_MIDPOINT else timestamp
                        record["timestamp_sec"] = round(value, TIMESTAMP_DECIMALS)
                        record["timestamp_hms"] = format_timestamp(value)
                        record["interval_start_sec"] = round(timestamp, TIMESTAMP_DECIMALS)
                        record["interval_end_sec"] = round(next_timestamp, TIMESTAMP_DECIMALS)
                    else:
                        record["timestamp_sec"] = round(timestamp, TIMESTAMP_DECIMALS)
                        record["timestamp_hms"] = format_timestamp(timestamp)
                        record["interval_start_sec"] = round(timestamp, TIMESTAMP_DECIMALS)
                        record["interval_end_sec"] = None

                    text = record.get("text", "")
                    if text != previous_text:
                        event_id += 1
                        previous_text = text
                    record["event_id"] = event_id
                    write_temp_record(final_f, record)
                    wrote_any = True

                with open(temp_path, "r", encoding="utf-8") as staged:
                    pending_record = None
                    for line in staged:
                        try:
                            current = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if pending_record is None:
                            pending_record = current
                            continue

                        current_ts = current.get("_keyframe_timestamp")
                        pending_ts = pending_record.get("_keyframe_timestamp")
                        if (
                            pending_ts is not None
                            and current_ts is not None
                            and current_ts < pending_ts
                        ):
                            _logger.warning(
                                f"[timestamp] {video_id}: phát hiện interval ngược "
                                f"({pending_ts} -> {current_ts}); không phá timestamp, "
                                "emit record hiện tại với kiểm tra an toàn."
                            )

                        emit_final(pending_record, current_ts)
                        pending_record = current

                    if pending_record is not None:
                        emit_final(pending_record, None)

                if not wrote_any:
                    return video_id, n_images, ocr_runs, skipped_dup, time.time() - start_time, False

                write_temp_record(
                    final_f,
                    {
                        "pipeline_version": PIPELINE_VERSION,
                        "video_id": video_id,
                        "video_done": True,
                        "num_frames": n_images,
                        "ocr_runs": ocr_runs,
                        "skipped_duplicate": skipped_dup,
                    },
                )
                final_f.flush()
                os.fsync(final_f.fileno())

            os.replace(final_temp, temp_path)
            append_video_temp(temp_path)
        finally:
            if os.path.exists(final_temp):
                try:
                    os.remove(final_temp)
                except OSError:
                    pass
        elapsed = time.time() - start_time
        return video_id, n_images, ocr_runs, skipped_dup, elapsed, True

    except Exception as e:
        _logger.error(f"Lỗi video {video_id}: {e}")
        return video_id, n_images, ocr_runs, skipped_dup, time.time() - start_time, False
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        _clear_inference_cache()
        gc.collect()


# ================= MAIN =================
def detect_gpu():
    try:
        import paddle
        return bool(paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0)
    except Exception:
        try:
            import torch
            return bool(torch.cuda.is_available())
        except Exception:
            return False


def main():
    global NUM_WORKERS

    if not os.path.isdir(KEYFRAME_ROOT):
        _logger.error(f"Không tồn tại KEYFRAME_ROOT: {KEYFRAME_ROOT}")
        return

    gpu_available = detect_gpu()
    use_gpu_requested = OCR_GPU_ENV in {"1", "true", "yes", "cuda", "gpu"}
    use_gpu = gpu_available if OCR_GPU_ENV in {"", "auto"} else use_gpu_requested and gpu_available
    if use_gpu_requested and not gpu_available:
        _logger.warning("OCR_GPU yêu cầu GPU nhưng không phát hiện CUDA/Paddle CUDA; chuyển sang CPU.")

    if use_gpu and NUM_WORKERS > 1:
        _logger.warning(f"GPU OCR: giảm workers {NUM_WORKERS} -> 1 để tránh nhân model/OOM VRAM.")
        NUM_WORKERS = 1

    provider = "cuda" if use_gpu else "cpu"
    _logger.info(
        f"OCR {PIPELINE_VERSION} | provider={provider} | "
        f"workers={NUM_WORKERS} | batch={OCR_BATCH_SIZE_RAW} | top_k={TOP_K}"
    )
    _logger.info(
        f"PP-OCRv6 | crop={CROP_BOTTOM_RATIO:.2f} | "
        f"max_width={OCR_MAX_WIDTH}px | midpoint={'ON' if USE_INTERVAL_MIDPOINT else 'OFF'}"
    )

    cleanup_orphaned_temp_files()
    videos = sorted(
        name for name in os.listdir(KEYFRAME_ROOT)
        if name != "maps" and os.path.isdir(os.path.join(KEYFRAME_ROOT, name))
    )
    done = load_done_videos_and_clean_partial()
    todo = [video_id for video_id in videos if video_id not in done]

    _logger.info(f"Tổng: {len(videos)} | Đã xong: {len(done)} | Còn lại: {len(todo)}")
    if not todo:
        return

    total_frames = total_ocr = total_dup = 0
    completed_since_gc = 0
    start_all = time.time()
    # Use one multiprocessing context consistently. This avoids passing a Lock
    # created by a different context into a spawn-based Pool (Windows/macOS) and
    # is also safe for CUDA because the parent never initializes an OCR model.
    mp_context_name = os.environ.get("OCR_MP_CONTEXT", "spawn").strip().lower()
    if mp_context_name not in {"spawn", "fork", "forkserver"}:
        _logger.warning(
            f"OCR_MP_CONTEXT={mp_context_name!r} không hợp lệ; dùng spawn."
        )
        mp_context_name = "spawn"
    if use_gpu and mp_context_name == "fork":
        _logger.warning("CUDA không dùng fork an toàn; tự động chuyển multiprocessing context sang spawn.")
        mp_context_name = "spawn"
    ctx = mp.get_context(mp_context_name)

    # Manager proxy is deliberately used here because the lock is passed
    # through Pool initializer under spawn. It is slower than ctx.Lock(),
    # but robust across spawn/forkserver and worker replacement.
    try:
        with ctx.Manager() as manager:
            lock = manager.Lock()
            with ctx.Pool(
                processes=NUM_WORKERS,
                initializer=init_worker,
                initargs=(lock, use_gpu),
                maxtasksperchild=MAX_TASKS_PER_CHILD,
            ) as pool:
                for i, result in enumerate(pool.imap_unordered(process_video, todo), 1):
                    video_id, frames, ocr_runs, skipped, elapsed, completed = result
                    total_frames += frames
                    total_ocr += ocr_runs
                    total_dup += skipped
    
                    if completed:
                        completed_since_gc += 1
                        if completed_since_gc >= max(5, NUM_WORKERS * 2):
                            gc.collect()
                            completed_since_gc = 0
    
                    status = "completed" if completed else "failed"
                    _logger.info(
                        f"[{i}/{len(todo)}] {status} {video_id} | "
                        f"frames={frames} | OCR={ocr_runs} | "
                        f"dup={skipped} | time={elapsed:.1f}s"
                    )
    except KeyboardInterrupt:
        _logger.warning("Dừng Ctrl+C. Chỉ video có video_done mới được coi là hoàn tất.")
        return

    elapsed_all = time.time() - start_all
    _logger.info("--- Thống kê ---")
    _logger.info(f"Tổng frame: {total_frames}")
    _logger.info(f"OCR thật: {total_ocr}")
    _logger.info(f"Bỏ qua trùng: {total_dup}")
    _logger.info(f"Thời gian: {elapsed_all / 60:.1f} phút")
    _logger.info(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
