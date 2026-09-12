#!/usr/bin/env python3
"""
Synchronize & Merge Multimodal Metadata
Gộp dữ liệu OCR, ASR và mốc thời gian Keyframe vào ocr_asr_metadata.json
"""

import os
import sys
import json
import glob
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCR_FILE = os.path.join(BASE_DIR, "ocr_results.jsonl")
ASR_FILE = os.path.join(BASE_DIR, "asr_results.jsonl")
OUTPUT_METADATA = os.path.join(BASE_DIR, "ocr_asr_metadata.json")

def merge_metadata():
    print("=" * 60)
    print("🔄 ĐANG ĐỒNG BỘ VÀ GỘP METADATA OCR & ASR...")
    print("=" * 60)

    ocr_map = {}
    if os.path.exists(OCR_FILE):
        print(f"📖 Đang đọc {OCR_FILE}...")
        with open(OCR_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    txt = (d.get("text") or d.get("ocr_text") or "").strip()
                    if not txt:
                        continue
                    if "video_path" in d:
                        p = d["video_path"].replace("\\", "/")
                        ocr_map[p] = txt
                    elif "video_id" in d and "frame_id" in d:
                        vid = str(d["video_id"]).replace("\\", "/")
                        fid = d["frame_id"]
                        rel = f"{vid}/keyframes/keyframe_{fid}.webp"
                        ocr_map[rel] = txt
                except Exception:
                    pass
        print(f"✅ Đã đọc {len(ocr_map):,} bản ghi OCR.")
    else:
        print(f"⚠️ Không tìm thấy {OCR_FILE}")

    asr_map = {}
    asr_subtitles = {}
    if os.path.exists(ASR_FILE):
        print(f"📖 Đang đọc {ASR_FILE}...")
        with open(ASR_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    txt = (d.get("text") or d.get("asr_text") or "").strip()
                    if not txt:
                        continue
                    vp = d.get("video_path", "").replace("\\", "/")
                    vid = os.path.splitext(os.path.basename(vp))[0]
                    if vid:
                        asr_map[vid] = (asr_map.get(vid, "") + " " + txt).strip()
                        if vid not in asr_subtitles:
                            asr_subtitles[vid] = []
                        start = float(d.get("start", 0.0))
                        end = float(d.get("end", 0.0))
                        asr_subtitles[vid].append({"start": start, "end": end, "text": txt})
                except Exception:
                    pass
        print(f"✅ Đã nạp dữ liệu ASR cho {len(asr_map):,} video.")
    else:
        print(f"⚠️ Không tìm thấy {ASR_FILE}")

    merged = {
        "ocr": ocr_map,
        "asr": asr_map,
        "subtitles": asr_subtitles
    }

    with open(OUTPUT_METADATA, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    size_mb = os.path.getsize(OUTPUT_METADATA) / (1024 * 1024)
    print(f"🎉 Đã lưu thành công {OUTPUT_METADATA} ({size_mb:.2f} MB)!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    merge_metadata()
