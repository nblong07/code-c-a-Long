"""
Script: merge_ocr_asr_metadata.py
Nhiệm vụ: Gộp toàn bộ dữ liệu OCR (từ ocr_results.jsonl) và ASR (từ asr_results.jsonl)
vào file tổng ocr_asr_metadata.json, ánh xạ chuẩn xác từng đoạn hội thoại / lời thoại
vào đúng keyframe theo mốc thời gian (timestamp).
"""

import os
import sys
import json
import bisect
import csv
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='ignore')

def merge_metadata(project_root: str = "D:\\code-c-a-Long", output_file: str = "ocr_asr_metadata.json"):
    root = Path(project_root)
    maps_dir = root / "data-keyframes"
    ocr_file = root / "ocr_results.jsonl"
    asr_file = root / "asr_results.jsonl"
    output_path = root / output_file

    print("=" * 60)
    print("🚀 BẮT ĐẦU ĐỒNG BỘ & GỘP DỮ LIỆU OCR & ASR VÀO METADATA TỔNG")
    print("=" * 60)

    # 1. Quét toàn bộ file _map.csv để xây dựng ánh xạ (Seconds -> Keyframe) cho từng video
    print("\n[1/4] Đang quét cấu trúc keyframes và nạp mốc thời gian từ các file _map.csv...")
    video_frames = defaultdict(list)  # vid -> list of (sec, fid, key)

    if maps_dir.exists():
        for r, _, files in os.walk(maps_dir):
            for f in files:
                if f.endswith('_map.csv'):
                    vid = f.replace('_map.csv', '')
                    rel = os.path.relpath(r, maps_dir).replace('\\', '/')
                    parts = rel.split('/')
                    batch = parts[0] if len(parts) > 0 and parts[0] != '.' and parts[0] != 'maps' else ''
                    full_vid = f'{batch}/{vid}' if batch else vid
                    csv_p = os.path.join(r, f)
                    try:
                        with open(csv_p, 'r', encoding='utf-8') as cf:
                            reader = csv.reader(cf)
                            next(reader, None)
                            for row in reader:
                                if len(row) >= 2:
                                    fid = int(row[0])
                                    sec = float(row[1])
                                    key = f'{full_vid}/keyframes/keyframe_{fid}.webp'
                                    video_frames[vid].append((sec, fid, key))
                    except Exception:
                        pass

    for vid in video_frames:
        video_frames[vid].sort(key=lambda x: x[0])

    print(f"   -> Đã nạp mốc thời gian cho {len(video_frames):,} video.")

    # 2. Xử lý OCR
    print("\n[2/4] Đang nạp dữ liệu OCR từ ocr_results.jsonl...")
    ocr_data = {}
    if ocr_file.exists():
        with open(ocr_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    txt = (d.get('text') or '').strip()
                    if txt:
                        vid = d.get('video_id', '')
                        fid = d.get('frame_id', '')
                        key = f'{vid}/keyframes/keyframe_{fid}.webp'
                        ocr_data[key] = txt
                except Exception:
                    pass
        print(f"   -> Đã nạp thành công {len(ocr_data):,} bản ghi OCR.")
    else:
        print(f"   ⚠️ Không tìm thấy file {ocr_file}!")

    # 3. Xử lý ASR
    print("\n[3/4] Đang nạp và ánh xạ thời gian ASR từ asr_results.jsonl...")
    asr_by_keyframe = defaultdict(list)
    total_asr_lines = 0
    matched_asr_lines = 0

    if asr_file.exists():
        with open(asr_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                total_asr_lines += 1
                try:
                    d = json.loads(line)
                    txt = (d.get('text') or d.get('asr_text') or '').strip()
                    if not txt:
                        continue

                    vp = d.get('video_path', '')
                    if vp:
                        vname = os.path.splitext(os.path.basename(vp))[0]
                    else:
                        vname = d.get('video_id', '')

                    frames = video_frames.get(vname, [])
                    if not frames:
                        # Fallback nếu không có trong maps
                        vp_clean = vp.replace('\\', '/')
                        parts = vp_clean.split('/')
                        filename = parts[-1].replace('.mp4', '')
                        batch = parts[-2].replace('video_', '') if len(parts) >= 2 else ''
                        vid = f'{batch}/{filename}' if batch else filename
                        start_sec = float(d.get('start', 0))
                        fid = int(d.get('frame_id', int(start_sec * 25)))
                        key = f'{vid}/keyframes/keyframe_{fid}.webp'
                        if txt not in asr_by_keyframe[key]:
                            asr_by_keyframe[key].append(txt)
                        continue

                    start = float(d.get('start', 0.0))
                    end = float(d.get('end', start + 2.0))
                    mid = (start + end) / 2.0

                    secs = [f[0] for f in frames]
                    idx_left = bisect.bisect_left(secs, start)
                    idx_right = bisect.bisect_right(secs, end)

                    selected_keys = []
                    if idx_right > idx_left:
                        for i in range(idx_left, idx_right):
                            selected_keys.append(frames[i][2])
                    else:
                        idx = min(idx_left, len(frames) - 1)
                        if idx > 0 and abs(frames[idx - 1][0] - mid) < abs(frames[idx][0] - mid):
                            idx = idx - 1
                        selected_keys.append(frames[idx][2])

                    for k in selected_keys:
                        if txt not in asr_by_keyframe[k]:
                            asr_by_keyframe[k].append(txt)
                    matched_asr_lines += 1
                except Exception:
                    pass

        print(f"   -> Đã xử lý {total_asr_lines:,} đoạn ASR.")
        print(f"   -> Đã ánh xạ thành công {matched_asr_lines:,} đoạn vào {len(asr_by_keyframe):,} keyframe độc nhất.")
    else:
        print(f"   ⚠️ Không tìm thấy file {asr_file}!")

    asr_data = {k: " | ".join(v) for k, v in asr_by_keyframe.items()}

    # 4. Ghi ra ocr_asr_metadata.json
    print(f"\n[4/4] Đang ghi dữ liệu tổng hợp vào {output_path}...")
    metadata = {
        "ocr": ocr_data,
        "asr": asr_data
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    sz_mb = output_path.stat().st_size / (1024 * 1024)
    print("=" * 60)
    print(f"✅ HOÀN TẤT ĐỒNG BỘ ocr_asr_metadata.json!")
    print(f"📊 Thống kê:")
    print(f"   - Tổng số keyframes có OCR: {len(ocr_data):,}")
    print(f"   - Tổng số keyframes có ASR: {len(asr_data):,}")
    print(f"   - Dung lượng file metadata: {sz_mb:.2f} MB")
    print("=" * 60)
    return True

if __name__ == "__main__":
    merge_metadata()
