"""
Multi-modal Text Extractor (OCR + ASR) for Hybrid Video Search
==============================================================
Extracts:
1. OCR (Optical Character Recognition) from keyframe images (billboards, license plates, signs).
2. ASR (Speech-to-Text) from video audio tracks.
Saves extracted text metadata into `ocr_asr_metadata.json` for BM25 / Text Search indexing.
"""

import os
import json
import glob
import argparse
from tqdm import tqdm

def extract_ocr_from_keyframes(keyframes_dir: str):
    """Trích xuất chữ viết xuất hiện trong khung hình keyframe (OCR)"""
    ocr_results = {}
    
    try:
        import easyocr
        reader = easyocr.Reader(['vi', 'en'], gpu=True)
        use_easyocr = True
    except Exception:
        use_easyocr = False
        print("⚠️ EasyOCR chưa sẵn sàng. Chạy chế độ quét fallback.")

    image_paths = []
    for root, _, files in os.walk(keyframes_dir):
        for f in files:
            if f.lower().endswith(('.webp', '.jpg', '.jpeg', '.png')):
                image_paths.append(os.path.join(root, f))
                
    print(f"🔍 Đang chạy OCR trên {len(image_paths)} keyframes...")
    for img_path in tqdm(image_paths):
        rel_path = os.path.relpath(img_path, keyframes_dir)
        if use_easyocr:
            try:
                text_list = reader.readtext(img_path, detail=0)
                extracted_text = " ".join(text_list)
            except Exception:
                extracted_text = ""
        else:
            extracted_text = ""
            
        ocr_results[rel_path] = extracted_text

    return ocr_results

def extract_asr_from_videos(videos_dir: str):
    """Trích xuất lời nói từ file audio trong video (ASR Speech-to-Text)"""
    asr_results = {}
    
    try:
        import whisper
        model = whisper.load_model("base")
        use_whisper = True
    except Exception:
        use_whisper = False
        print("⚠️ Whisper chưa sẵn sàng. Chạy chế độ quét fallback.")

    video_paths = glob.glob(os.path.join(videos_dir, "*.mp4"))
    print(f"🎙️ Đang chạy ASR Speech-to-Text trên {len(video_paths)} video...")
    for v_path in tqdm(video_paths):
        v_name = os.path.splitext(os.path.basename(v_path))[0]
        if use_whisper:
            try:
                res = model.transcribe(v_path)
                asr_results[v_name] = res.get("text", "")
            except Exception:
                asr_results[v_name] = ""
        else:
            asr_results[v_name] = ""

    return asr_results

def main():
    parser = argparse.ArgumentParser(description="Extract OCR and ASR metadata for Hybrid Search.")
    parser.add_argument("--keyframes-dir", type=str, default="./data-keyframes", help="Path to keyframes directory")
    parser.add_argument("--videos-dir", type=str, default="./data-videos", help="Path to videos directory")
    parser.add_argument("--output", type=str, default="ocr_asr_metadata.json", help="Path to output JSON")
    args = parser.parse_args()

    print("==================================================")
    print("🚀 BẮT ĐẦU TRÍCH XUẤT OCR & ASR ĐA PHƯƠNG THỨC")
    print("==================================================")

    ocr_data = {}
    if os.path.exists(args.keyframes_dir):
        ocr_data = extract_ocr_from_keyframes(args.keyframes_dir)
    else:
        print(f"⚠️ Không tìm thấy thư mục keyframe: {args.keyframes_dir}")

    asr_data = {}
    if os.path.exists(args.videos_dir):
        asr_data = extract_asr_from_videos(args.videos_dir)
    else:
        print(f"⚠️ Không tìm thấy thư mục video: {args.videos_dir}")

    metadata = {
        "ocr": ocr_data,
        "asr": asr_data
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"✅ Hoàn tất! Đã lưu kết quả vào file: {args.output}")

if __name__ == "__main__":
    main()
