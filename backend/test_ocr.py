import os
import re
import glob
import json
import time
import warnings
import multiprocessing as mp
import cv2
import numpy as np

warnings.filterwarnings("ignore", category=UserWarning)

KEYFRAME_ROOT = "/app/data-keyframes"
OUTPUT_FILE = "/app/ocr_results.jsonl"

# Vùng text tổng (tính từ đáy ảnh lên) chứa cả tiêu đề + băng ticker.
CROP_BOTTOM_RATIO = 0.45

# Chỉ dùng để xác định vùng "title" (phần trên của crop, không dính ticker)
# cho mục đích SO SÁNH TRÙNG LẶP. OCR vẫn chạy trên toàn bộ vùng crop
# (title + ticker) trong MỘT lần gọi duy nhất -> tránh nhân đôi OCR call
# như bản trước (đã test thực tế: tách 2 vùng làm chậm gấp 3.5 lần vì
# overhead cố định của mỗi lần gọi readtext()).
TICKER_BAND_RATIO = 0.35

CONFIDENCE_THRESHOLD = 0.4
TITLE_DUPLICATE_DIFF_THRESHOLD = 6.0
MIN_TEXT_LEN = 3

OCR_MAX_WIDTH = 960

# Số frame gom lại trước khi gọi OCR theo batch (giảm overhead cố định/lần gọi).
# Máy yếu RAM thì giảm số này xuống (VD 4).
BATCH_SIZE = int(os.environ.get("OCR_BATCH_SIZE", 8))

# Ghi file tăng dần sau mỗi FLUSH_EVERY dòng, thay vì gom hết tới cuối video
# mới ghi 1 lần -> nếu có sự cố giữa chừng (mất kết nối, container restart,
# crash...) chỉ mất tối đa phần chưa kịp ghi, không mất trắng cả video.
FLUSH_EVERY = 200

NUM_WORKERS = int(os.environ.get("OCR_NUM_WORKERS", max(1, (os.cpu_count() or 2) - 1)))

# Từ điển sửa lỗi chính tả PHỔ BIẾN do EasyOCR hay nhận sai với tiếng Việt.
# Chỉ đưa vào các trường hợp KHÔNG mơ hồ (không phải từ có nghĩa khác khi
# viết đúng chính tả kiểu cũ). Các trường hợp d/đ mơ hồ (dạo/đạo, dông/đông...)
# CỐ TÌNH bỏ qua vì dễ sửa sai theo ngữ cảnh - cần bộ spell-checker tiếng Việt
# riêng nếu muốn xử lý triệt để hơn.
SPELL_FIX_MAP = {
    "iuong": "lương", "ivong": "lương", "luong": "lương",
    "tuong": "thương", "thvong": "thương",
    "huong": "hưởng", "hvong": "hưởng", "huởng": "hưởng", "hvởng": "hưởng",
    "nguoi": "người", "nguòi": "người", "nguời": "người",
    "duong": "đường", "duờng": "đường", "dường": "đường",
    "cuong": "cường",
    "phuong": "phường",
    "chuong": "chương",
    "truong": "trường", "truờng": "trường",
    "vuon": "vươn",
    "duoc": "được",
}
_SPELL_FIX_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in SPELL_FIX_MAP) + r")\b",
    re.IGNORECASE
)


def apply_spell_fix(text):
    if not text:
        return text

    def _replace(m):
        word = m.group(0)
        fixed = SPELL_FIX_MAP[word.lower()]
        return fixed.capitalize() if word[0].isupper() else fixed

    return _SPELL_FIX_RE.sub(_replace, text)


def resize_for_ocr(img, max_width=OCR_MAX_WIDTH):
    if img is None or img.size == 0:
        return img
    h, w = img.shape[:2]
    if w <= max_width:
        return img
    scale = max_width / w
    new_w = max_width
    new_h = max(1, int(h * scale))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def preprocess_cv2(img_path):
    """
    Trả về (full_rgb, title_gray_small):
      - full_rgb: TOÀN BỘ vùng crop (title + ticker), đưa vào OCR 1 lần duy nhất.
      - title_gray_small: chỉ vùng title (phần trên, không dính ticker),
        dùng riêng để so sánh trùng lặp giữa các frame liên tiếp.
    """
    img = cv2.imread(img_path)
    if img is None:
        return None, None

    h, w = img.shape[:2]
    crop_top = int(h * (1 - CROP_BOTTOM_RATIO))
    cropped = img[crop_top:h, 0:w]
    if cropped.size == 0:
        return None, None

    ch = cropped.shape[0]
    ticker_top = int(ch * (1 - TICKER_BAND_RATIO))
    title_region = cropped[0:ticker_top, :]

    title_gray_small = None
    if title_region.size > 0:
        title_gray_small = cv2.resize(
            cv2.cvtColor(title_region, cv2.COLOR_BGR2GRAY), (64, 24)
        ).astype(np.float32)

    full_rgb = resize_for_ocr(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
    return full_rgb, title_gray_small


def is_duplicate(prev_gray, cur_gray, threshold):
    if prev_gray is None or cur_gray is None:
        return False
    return np.mean(np.abs(prev_gray - cur_gray)) < threshold


def load_done_videos_and_clean_partial():
    done = set()
    if not os.path.exists(OUTPUT_FILE):
        return done

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    parsed = []
    for line in lines:
        try:
            rec = json.loads(line)
        except Exception:
            continue
        parsed.append(rec)
        if rec.get("video_done"):
            done.add(rec["video_id"])

    kept = [rec for rec in parsed if rec.get("video_id") in done]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for rec in kept:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return done


# ---- Worker process ----

_worker_reader = None
_worker_lock = None
_batched_ocr_supported = True  # nếu readtext_batched() lỗi 1 lần, tắt vĩnh viễn cho worker này


def _init_worker(lock):
    global _worker_reader, _worker_lock
    import cv2 as _cv2
    import torch as _torch
    _cv2.setNumThreads(1)
    _torch.set_num_threads(1)
    import easyocr
    _worker_lock = lock
    _worker_reader = easyocr.Reader(['vi', 'en'], gpu=False, verbose=False)


def _extract_text_conf(result):
    kept = [
        (t, c) for (_, t, c) in result
        if c >= CONFIDENCE_THRESHOLD and len(t.strip()) >= MIN_TEXT_LEN
    ]
    text = " | ".join(t for t, _ in kept)
    text = apply_spell_fix(text)
    conf = round(sum(c for _, c in kept) / len(kept), 3) if kept else 0.0
    return text, conf


def _ocr_batch(images):
    """
    OCR từng ảnh một. ĐÃ THỬ dùng readtext_batched() để tăng tốc nhưng đo
    thực tế cho thấy CHẬM HƠN gọi riêng lẻ trên CPU (~3.4 lần) - batching
    tối ưu cho GPU (song song phần cứng), trên CPU chỉ cộng thêm overhead
    resize/pad ảnh về cùng kích thước mà không có lợi ích tương ứng.
    """
    out = []
    for img in images:
        try:
            result = _worker_reader.readtext(img, detail=1, paragraph=False)
            out.append(_extract_text_conf(result))
        except Exception as e:
            print(f"  [Lỗi OCR] {e}")
            out.append(("", 0.0))
    return out


def _process_video(video_id):
    try:
        video_dir = os.path.join(KEYFRAME_ROOT, video_id, "keyframes")
        if not os.path.isdir(video_dir):
            return video_id, 0, 0, 0, 0.0

        images = sorted(glob.glob(os.path.join(video_dir, "*.webp")))
        # So sánh với ANCHOR cố định (frame đầu của mỗi nhóm), KHÔNG so với
        # frame liền trước -> tránh lỗi "drift": nếu chỉ so N với N-1, cảnh
        # đổi từ từ (fade/mờ dần) sẽ khiến sai lệch tích lũy mà không frame
        # nào vượt ngưỡng, dẫn tới gán nhầm text cũ cho cả chuỗi dài đã đổi.
        anchor_title_gray = None
        ocr_runs = 0
        skipped_dup = 0
        lines_to_write = []
        video_start = time.time()

        # batch = danh sách các "anchor" đang chờ OCR theo lô.
        # mỗi phần tử: {"frame_id":..., "img":..., "followers": [frame_id...]}
        batch = []
        # Sau mỗi lần flush, giữ lại (text, conf) của anchor CUỐI CÙNG vừa
        # OCR xong -> nếu frame ngay sau đó vẫn trùng (chuỗi trùng lặp kéo
        # dài qua ranh giới flush), dùng lại kết quả này thay vì tạo anchor
        # mới không cần thiết (tránh lãng phí 1 lần OCR thừa).
        last_flushed = {"text": None, "conf": None}

        def flush_batch():
            nonlocal batch, ocr_runs, lines_to_write, last_flushed
            if not batch:
                return
            imgs = [b["img"] for b in batch]
            results = _ocr_batch(imgs)
            ocr_runs += len(imgs)
            for b, (text, conf) in zip(batch, results):
                lines_to_write.append(json.dumps({
                    "video_id": video_id,
                    "frame_id": b["frame_id"],
                    "text": text,
                    "confidence": conf,
                    "reused": False
                }, ensure_ascii=False))
                for fid in b["followers"]:
                    lines_to_write.append(json.dumps({
                        "video_id": video_id,
                        "frame_id": fid,
                        "text": text,
                        "confidence": conf,
                        "reused": True
                    }, ensure_ascii=False))
            last_flushed["text"], last_flushed["conf"] = results[-1]
            batch = []

        def flush_to_disk():
            nonlocal lines_to_write
            if not lines_to_write:
                return
            with _worker_lock:
                with open(OUTPUT_FILE, "a", encoding="utf-8") as out_f:
                    out_f.write("\n".join(lines_to_write) + "\n")
            lines_to_write = []

        for img_path in images:
            frame_id = os.path.splitext(os.path.basename(img_path))[0].replace("keyframe_", "")

            try:
                full_rgb, title_gray = preprocess_cv2(img_path)
            except Exception as e:
                print(f"  [Lỗi đọc ảnh] {img_path}: {e}")
                continue
            if full_rgb is None:
                continue

            is_dup = is_duplicate(anchor_title_gray, title_gray, TITLE_DUPLICATE_DIFF_THRESHOLD)
            if is_dup and batch:
                # Trùng với anchor hiện tại -> gắn vào danh sách "followers".
                # LƯU Ý: vì OCR gộp chung title+ticker, follower sẽ dùng lại
                # NGUYÊN VĂN ticker của anchor -> ticker thật của follower có
                # thể đã trượt sang nội dung khác, không được ghi nhận chính
                # xác. Đây là đánh đổi tốc độ, đánh dấu "reused": true để
                # biết dòng nào có khả năng ticker không chính xác.
                batch[-1]["followers"].append(frame_id)
                skipped_dup += 1
            elif is_dup and last_flushed["text"] is not None:
                # Trùng với anchor, nhưng batch vừa bị flush (rỗng) -> dùng
                # lại kết quả anchor vừa OCR xong thay vì tốn OCR mới.
                lines_to_write.append(json.dumps({
                    "video_id": video_id,
                    "frame_id": frame_id,
                    "text": last_flushed["text"],
                    "confidence": last_flushed["conf"],
                    "reused": True
                }, ensure_ascii=False))
                skipped_dup += 1
            else:
                batch.append({"frame_id": frame_id, "img": full_rgb, "followers": []})
                # Chỉ cập nhật anchor khi thật sự có anchor MỚI (frame không
                # trùng) -> followers tiếp theo luôn so với anchor này, không
                # so với frame liền trước -> tránh drift tích lũy qua fade.
                anchor_title_gray = title_gray

            if len(batch) >= BATCH_SIZE:
                flush_batch()

            if len(lines_to_write) >= FLUSH_EVERY:
                flush_to_disk()

        flush_batch()
        lines_to_write.append(json.dumps({"video_id": video_id, "video_done": True}, ensure_ascii=False))
        flush_to_disk()

        elapsed = time.time() - video_start
        return video_id, len(images), ocr_runs, skipped_dup, elapsed

    except Exception as e:
        print(f"  [Lỗi video] {video_id}: {e}")
        return video_id, 0, 0, 0, 0.0


def main():
    print(f"--- Máy không có GPU NVIDIA -> chạy CPU với {NUM_WORKERS} worker song song ---")
    print(f"--- OCR_MAX_WIDTH = {OCR_MAX_WIDTH}px, BATCH_SIZE = {BATCH_SIZE}, "
          f"TITLE_DUPLICATE_DIFF_THRESHOLD = {TITLE_DUPLICATE_DIFF_THRESHOLD} ---\n")

    videos = sorted([d for d in os.listdir(KEYFRAME_ROOT) if os.path.isdir(os.path.join(KEYFRAME_ROOT, d))])
    done_videos = load_done_videos_and_clean_partial()
    todo = [v for v in videos if v not in done_videos]
    print(f"Tổng số video: {len(videos)} | Đã hoàn thành trước đó: {len(done_videos)} | Còn lại: {len(todo)}\n")

    total_frames = 0
    total_ocr_runs = 0
    total_skipped_dup = 0
    start_all = time.time()

    manager = mp.Manager()
    lock = manager.Lock()

    try:
        with mp.Pool(processes=NUM_WORKERS, initializer=_init_worker, initargs=(lock,)) as pool:
            for i, (video_id, n_images, ocr_runs, skipped_dup, elapsed) in enumerate(
                pool.imap_unordered(_process_video, todo), 1
            ):
                total_frames += n_images
                total_ocr_runs += ocr_runs
                total_skipped_dup += skipped_dup
                print(f"[{i}/{len(todo)}] Xong: {video_id} ({n_images} frames, OCR thật: {ocr_runs}, "
                      f"bỏ qua trùng: {skipped_dup}, thời gian: {elapsed:.1f}s)")
    except KeyboardInterrupt:
        print("\nĐã dừng (Ctrl+C). Các video đã ghi xong (có video_done) được giữ nguyên; "
              "video đang dở dang khi chạy lại sẽ tự làm lại từ đầu, không bị trùng dữ liệu.")

    total_elapsed = time.time() - start_all
    print(f"\n--- Thống kê ---")
    print(f"Tổng frame đã duyệt: {total_frames}")
    print(f"Số lần chạy OCR thật: {total_ocr_runs}")
    print(f"Số frame bỏ qua trùng: {total_skipped_dup}")
    print(f"Thời gian thực thi: {total_elapsed/60:.1f} phút")
    print(f"File kết quả: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
    
