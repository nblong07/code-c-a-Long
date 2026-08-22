"""
Standalone Feature Extractor â€” Extract CLIP image features to numpy file
========================================================================
"""

import os
import sys
import argparse
import torch
import torch.nn.functional as F
import open_clip
from PIL import Image
import numpy as np
from tqdm import tqdm

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_args():
    p = argparse.ArgumentParser(description="Extract SigLIP 2 Giant feature vectors to numpy format.")
    p.add_argument("--keyframes-dir", type=str, default="./data-keyframes",
                   help="Path to directory containing keyframe images.")
    p.add_argument("--output-features", type=str, default="features.npy",
                   help="Output path for feature array.")
    p.add_argument("--output-paths", type=str, default="image_paths.npy",
                   help="Output path for image paths array.")
    p.add_argument("--model", type=str, default="ViT-gopt-16-SigLIP2-384",
                   help="Vision model (default: ViT-gopt-16-SigLIP2-384 Google SigLIP 2 Giant).")
    p.add_argument("--pretrained", type=str, default="webli",
                   help="Pretrained weights dataset (default: webli).")
    p.add_argument("--batch-size", type=int, default=16,
                   help="Batch size for feature extraction.")
    return p.parse_args()


def extract_clip_main():
    args = parse_args()

    keyframes_dir = os.path.abspath(args.keyframes_dir)
    print("--------------------------------------------------")
    print(f"Scanning directory: {keyframes_dir}")
    print(f"Directory exists: {os.path.exists(keyframes_dir)}")

    if not os.path.exists(keyframes_dir):
        print(f"❌ Error: Path '{keyframes_dir}' does not exist.")
        return

    # Find all image paths
    image_paths = []
    for root, _, files in os.walk(keyframes_dir, followlinks=True):
        if "maps" in root:
            continue
        for file in files:
            if file.lower().endswith(('.webp', '.png', '.jpg', '.jpeg')):
                image_paths.append(os.path.join(root, file))

    image_paths.sort()
    print(f"Found {len(image_paths)} keyframe images.")
    print("--------------------------------------------------")

    if len(image_paths) == 0:
        print("❌ Error: No valid image files found!")
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🚀 Running feature extraction on device: {device}")

    # Load Visual Model (Google SigLIP 2 Giant)
    print(f"📦 Loading Visual Backbone: {args.model} ({args.pretrained})...")
    model, _, preprocess = open_clip.create_model_and_transforms(args.model, pretrained=args.pretrained)
    model = model.to(device).eval()

    features = []
    valid_paths = []

    buffer_imgs = []
    buffer_paths = []

    for path in tqdm(image_paths, desc="Extracting vector features"):
        try:
            img = Image.open(path).convert("RGB")
            tensor_img = preprocess(img)
            buffer_imgs.append(tensor_img)
            buffer_paths.append(path)
        except Exception:
            continue

        if len(buffer_imgs) >= args.batch_size:
            imgs_tensor = torch.stack(buffer_imgs).to(device, non_blocking=True)
            with torch.inference_mode():
                if device.type == "cuda":
                    with torch.amp.autocast(device_type="cuda"):
                        embs = model.encode_image(imgs_tensor) if hasattr(model, "encode_image") else model(imgs_tensor)
                else:
                    embs = model.encode_image(imgs_tensor) if hasattr(model, "encode_image") else model(imgs_tensor)
                embs = F.normalize(embs.float(), p=2, dim=-1)

            features.append(embs.cpu().numpy())
            valid_paths.extend(buffer_paths)
            buffer_imgs.clear()
            buffer_paths.clear()

    # Flush remaining
    if buffer_imgs:
        imgs_tensor = torch.stack(buffer_imgs).to(device, non_blocking=True)
        with torch.inference_mode():
            if device.type == "cuda":
                with torch.amp.autocast(device_type="cuda"):
                    embs = model.encode_image(imgs_tensor) if hasattr(model, "encode_image") else model(imgs_tensor)
            else:
                embs = model.encode_image(imgs_tensor) if hasattr(model, "encode_image") else model(imgs_tensor)
            embs = F.normalize(embs.float(), p=2, dim=-1)

        features.append(embs.cpu().numpy())
        valid_paths.extend(buffer_paths)

    features = np.vstack(features).astype('float32')
    np.save(args.output_features, features)
    np.save(args.output_paths, np.array(valid_paths))

    print(f"\n✨ SUCCESS! Extracted {len(features)} vector features (dimension: {features.shape[1]}).")
    print(f"Saved features to '{args.output_features}' and paths to '{args.output_paths}'.")




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
    advanced_ocr_file = "ocr_results.jsonl"
    if os.path.exists(advanced_ocr_file):
        print(f"🌟 Đang tích hợp dữ liệu OCR từ file {advanced_ocr_file}...")
        try:
            with open(advanced_ocr_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    text = data.get("text", "").strip()
                    if not text:
                        continue

                    if "video_path" in data:
                        path = data["video_path"]
                        rel_path = os.path.relpath(path, keyframes_dir).replace("\\", "/") if os.path.isabs(path) else path.replace("\\", "/")
                    elif "video_id" in data and "frame_id" in data:
                        vid = data["video_id"].replace("\\", "/")
                        fid = data["frame_id"]
                        rel_path = f"{vid}/keyframes/keyframe_{fid}.webp"
                    else:
                        continue

                    ocr_results[rel_path] = text
            if ocr_results:
                print(f"✅ Đã nạp thành công {len(ocr_results)} bản ghi OCR có chữ.")
                return ocr_results
        except Exception as e:
            print(f"⚠️ Lỗi đọc {advanced_ocr_file}: {e}")
    return ocr_results

def extract_asr_from_videos(videos_dir: str):
    """Trích xuất lời nói từ file audio trong video (ASR Speech-to-Text)"""
    asr_results = {}
    advanced_asr_file = "asr_results.jsonl"
    if os.path.exists(advanced_asr_file):
        print(f"🌟 Đang tích hợp dữ liệu ASR từ file {advanced_asr_file}...")
        try:
            with open(advanced_asr_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if "video_path" in data and "text" in data and data["text"]:
                        v_name = os.path.splitext(os.path.basename(data["video_path"]))[0]
                        existing = asr_results.get(v_name, "")
                        asr_results[v_name] = (existing + " " + data["text"]).strip()
            if asr_results:
                print(f"✅ Đã nạp thành công dữ liệu ASR cho {len(asr_results)} video.")
                return asr_results
        except Exception as e:
            print(f"⚠️ Lỗi đọc {advanced_asr_file}: {e}")
    return asr_results

def extract_ocr_asr_main():
    parser = argparse.ArgumentParser(description="Extract OCR and ASR metadata for Hybrid Search.")
    parser.add_argument("--keyframes-dir", type=str, default="./data-keyframes", help="Path to keyframes directory")
    parser.add_argument("--videos-dir", type=str, default=r"C:\video_test", help="Path to videos directory")
    parser.add_argument("--output", type=str, default="ocr_asr_metadata.json", help="Path to output JSON")
    args = parser.parse_args()

    print("==================================================")
    print("🚀 BẮT ĐẦU TRÍCH XUẤT OCR & ASR ĐA PHƯƠNG THỨC")
    print("==================================================")

    ocr_data = {}
    if os.path.exists(args.keyframes_dir) or os.path.exists("ocr_results.jsonl"):
        ocr_data = extract_ocr_from_keyframes(args.keyframes_dir)
    else:
        print(f"⚠️ Không tìm thấy thư mục keyframe: {args.keyframes_dir}")

    asr_data = {}
    if os.path.exists(args.videos_dir) or os.path.exists("asr_results.jsonl"):
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




if __name__ == '__main__':
    import sys
    print('Choose extraction task: 1 for CLIP, 2 for OCR/ASR, 3 for BOTH')
    if len(sys.argv) > 1 and sys.argv[1] in ['1', '2', '3']:
        choice = sys.argv[1]
        sys.argv = [sys.argv[0]] + sys.argv[2:]
    elif len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        choice = sys.argv[1]
        sys.argv = [sys.argv[0]] + sys.argv[2:]
    else:
        choice = input('Enter choice (1 for CLIP / 2 for OCR-ASR / 3 for BOTH): ').strip()
    
    if choice == '1':
        extract_clip_main()
    elif choice == '2':
        extract_ocr_asr_main()
    elif choice == '3':
        print('--- EXTRACTING CLIP ---')
        orig_argv = list(sys.argv)
        extract_clip_main()
        print('--- EXTRACTING OCR/ASR ---')
        sys.argv = orig_argv
        extract_ocr_asr_main()
    else:
        print('Invalid choice')
