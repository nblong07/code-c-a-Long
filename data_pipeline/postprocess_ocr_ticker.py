"""
Script hậu xử lý ocr_results.jsonl: gộp các frame liên tiếp có nội dung
overlap nhau (do ticker trượt ngang qua nhiều frame) thành các câu hoàn
chỉnh, thay vì giữ nguyên từng mảnh vụn theo từng frame.

Cách hoạt động:
  - Với mỗi video, gom các dòng theo frame_id tăng dần.
  - So sánh text của frame hiện tại với frame trước bằng tỉ lệ overlap
    (difflib.SequenceMatcher). Nếu overlap đủ cao -> coi là cùng 1 "đoạn
    ticker đang trượt", gộp vào cùng 1 segment.
  - Trong mỗi segment, chọn dòng TEXT DÀI NHẤT làm đại diện (vì ticker
    trượt dần lộ ra nhiều chữ hơn, dòng dài nhất thường là bản đầy đủ nhất).

Đây là heuristic đơn giản, không phải giải pháp hoàn hảo tuyệt đối -
với ticker có nhiều tin xen kẽ nhanh, kết quả có thể vẫn cần soát lại
bằng mắt cho các trường hợp quan trọng.

Cách chạy:
  python data_pipeline/postprocess_ocr_ticker.py ocr_results.jsonl ocr_stitched.jsonl
"""
import sys
import json
from difflib import SequenceMatcher
from collections import defaultdict

OVERLAP_THRESHOLD = 0.5  # tỉ lệ trùng khớp tối thiểu để coi là cùng 1 đoạn ticker


def overlap_ratio(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def stitch_video(records):
    """records: list các dict đã sort theo frame_id (dạng số)."""
    segments = []
    current_segment = []

    for rec in records:
        text = rec.get("text", "")
        if not current_segment:
            current_segment = [rec]
            continue

        prev_text = current_segment[-1].get("text", "")
        if overlap_ratio(prev_text, text) >= OVERLAP_THRESHOLD:
            current_segment.append(rec)
        else:
            segments.append(current_segment)
            current_segment = [rec]

    if current_segment:
        segments.append(current_segment)

    stitched = []
    for seg in segments:
        best = max(seg, key=lambda r: len(r.get("text", "")))
        stitched.append({
            "video_id": best["video_id"],
            "frame_id_start": seg[0]["frame_id"],
            "frame_id_end": seg[-1]["frame_id"],
            "text": best.get("text", ""),
            "confidence": best.get("confidence", 0.0),
        })
    return stitched


def main():
    if len(sys.argv) < 3:
        print("Cách dùng: python3 stitch_ticker.py <input.jsonl> <output.jsonl>")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    by_video = defaultdict(list)
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("video_done"):
                continue
            if not rec.get("text"):
                continue
            by_video[rec["video_id"]].append(rec)

    total_before = 0
    total_after = 0
    with open(output_path, "w", encoding="utf-8") as out_f:
        for video_id, records in by_video.items():
            records.sort(key=lambda r: int(r["frame_id"]))
            stitched = stitch_video(records)
            total_before += len(records)
            total_after += len(stitched)
            for rec in stitched:
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Số dòng gốc: {total_before}")
    print(f"Số dòng sau khi gộp: {total_after}")
    print(f"Đã ghi: {output_path}")


if __name__ == "__main__":
    main()
