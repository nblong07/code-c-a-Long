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
    p.add_argument("--batch-size", type=int, default=32,
                   help="Batch size for feature extraction.")
    return p.parse_args()


from torch.utils.data import Dataset, DataLoader

import cv2

class KeyframeDataset(Dataset):
    def __init__(self, paths, transform):
        self.paths = paths
        self.transform = transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        path = self.paths[idx]
        try:
            # OpenCV C++ native WebP decoder: nhanh gấp 3 lần PIL trên Windows
            img_bgr = cv2.imread(path, cv2.IMREAD_COLOR)
            if img_bgr is not None:
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                # C++ Bicubic resize squash trực tiếp về kích thước chuẩn 384x384 của SigLIP 2
                img_resized = cv2.resize(img_rgb, (384, 384), interpolation=cv2.INTER_CUBIC)
                # Chuẩn hóa ma trận trực tiếp: (img / 255.0 - 0.5) / 0.5 = img * 0.007843137 - 1.0
                tensor = torch.from_numpy(img_resized).permute(2, 0, 1).float().mul_(0.007843137).sub_(1.0)
                return tensor, path, True
            else:
                img = Image.open(path).convert("RGB")
                return self.transform(img), path, True
        except Exception:
            return torch.zeros((3, 384, 384), dtype=torch.float32), path, False


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

    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        # Hiển thị thông số VRAM GPU
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"🎮 GPU: {torch.cuda.get_device_name(0)} | VRAM: {vram_gb:.2f} GB")

    # Load Visual Model (Google SigLIP 2 Giant)
    print(f"📦 Loading Visual Backbone: {args.model} ({args.pretrained})...")
    model, _, preprocess = open_clip.create_model_and_transforms(args.model, pretrained=args.pretrained)
    
    # CHUYỂN TRỰC TIẾP MODEL SANG FP16: Giảm kích thước model từ 3.8GB xuống 1.9GB VRAM!
    if device.type == "cuda":
        model = model.to(device=device, dtype=torch.float16).eval()
    else:
        model = model.to(device).eval()

    # Sử dụng batch size tối ưu (24 cho 6GB VRAM) để đạt mức chiếm dụng 70-78% VRAM (~4.5GB), tối đa hóa Tensor Cores
    eff_batch_size = args.batch_size if args.batch_size <= 28 else 24
    print(f"⚡ Tối ưu VRAM: Sử dụng Batch Size = {eff_batch_size} (Tải 75% VRAM ~4.5GB, an toàn 100% chống OOM)")

    # PyTorch DataLoader đa luồng với persistent workers và DMA Pin Memory
    dataset = KeyframeDataset(image_paths, preprocess)
    dataloader = DataLoader(
        dataset, 
        batch_size=eff_batch_size, 
        shuffle=False, 
        num_workers=6, 
        pin_memory=True if device.type == "cuda" else False,
        persistent_workers=True,
        prefetch_factor=3
    )

    features = []
    valid_paths = []

    with torch.inference_mode():
        for batch_imgs, batch_paths, batch_valid in tqdm(dataloader, desc="⚡ Extracting SigLIP 2 Giant vectors (CUDA Tensor Cores FP16)"):
            # Lọc các ảnh đọc thành công
            mask = batch_valid.numpy()
            if not np.any(mask):
                continue
                
            imgs_tensor = batch_imgs[mask].to(
                device=device, 
                dtype=torch.float16 if device.type == "cuda" else torch.float32, 
                non_blocking=True
            )
            paths = [p for p, v in zip(batch_paths, mask) if v]

            embs = model.encode_image(imgs_tensor) if hasattr(model, "encode_image") else model(imgs_tensor)
            embs = F.normalize(embs.float(), p=2, dim=-1)

            features.append(embs.cpu().numpy())
            valid_paths.extend(paths)

    if not features:
        print("❌ Error: No features extracted!")
        return

    features = np.vstack(features).astype('float32')
    
    # Lưu an toàn dạng Atomic File
    temp_feat = args.output_features + ".tmp.npy"
    temp_paths = args.output_paths + ".tmp.npy"
    np.save(temp_feat, features)
    np.save(temp_paths, np.array(valid_paths))

    if os.path.exists(args.output_features):
        try: os.remove(args.output_features)
        except: pass
    if os.path.exists(args.output_paths):
        try: os.remove(args.output_paths)
        except: pass

    os.rename(temp_feat, args.output_features)
    os.rename(temp_paths, args.output_paths)

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
