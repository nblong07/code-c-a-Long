#!/usr/bin/env python3
"""
Feature Extractor - Google SigLIP 2 Giant (ViT-gopt-16-SigLIP2-384, 1152d FP16)
Tối ưu hóa 80% - 90% phần cứng: AMD 7000 Series (16 Threads) + RTX 3050 6GB VRAM
================================================================================
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
import cv2
from torch.utils.data import Dataset, DataLoader

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Tối ưu hóa phân bổ tài nguyên CPU (80% - 90% công suất AMD 7000 Series 16 Threads)
_cpu_cores = os.cpu_count() or 8
OPTIMAL_CPU_THREADS = max(1, int(_cpu_cores * 0.85))
torch.set_num_threads(OPTIMAL_CPU_THREADS)
if hasattr(cv2, "setNumThreads"):
    cv2.setNumThreads(OPTIMAL_CPU_THREADS)


class KeyframeDataset(Dataset):
    def __init__(self, paths, transform):
        self.paths = paths
        self.transform = transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        path = self.paths[idx]
        try:
            # OpenCV native WebP decoder: nhanh gấp 3 lần PIL trên Windows
            img_bgr = cv2.imread(path, cv2.IMREAD_COLOR)
            if img_bgr is not None:
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                # Bicubic resize squash về kích thước chuẩn 384x384 của SigLIP 2
                img_resized = cv2.resize(img_rgb, (384, 384), interpolation=cv2.INTER_CUBIC)
                # Chuẩn hóa ma trận trực tiếp: (img / 255.0 - 0.5) / 0.5 = img * 0.007843137 - 1.0
                tensor = torch.from_numpy(img_resized).permute(2, 0, 1).float().mul_(0.007843137).sub_(1.0)
                return tensor, path, True
            else:
                img = Image.open(path).convert("RGB")
                return self.transform(img), path, True
        except Exception:
            return torch.zeros((3, 384, 384), dtype=torch.float32), path, False


def parse_args():
    p = argparse.ArgumentParser(description="Trích xuất vector đặc trưng hình ảnh SigLIP 2 Giant.")
    p.add_argument("--keyframes-dir", type=str, default="./data-keyframes",
                   help="Thư mục chứa ảnh keyframes.")
    p.add_argument("--output-features", type=str, default="features.npy",
                   help="File xuất vector đặc trưng (.npy).")
    p.add_argument("--output-paths", type=str, default="image_paths.npy",
                   help="File xuất danh sách đường dẫn ảnh (.npy).")
    p.add_argument("--model", type=str, default="ViT-gopt-16-SigLIP2-384",
                   help="Mô hình thị giác (mặc định: ViT-gopt-16-SigLIP2-384 Google SigLIP 2 Giant).")
    p.add_argument("--pretrained", type=str, default="webli",
                   help="Tập trọng số pretrained (mặc định: webli).")
    p.add_argument("--batch-size", type=int, default=24,
                   help="Kích thước batch cho trích xuất (mặc định: 24 tối ưu cho GPU 6GB VRAM).")
    p.add_argument("--workers", type=int, default=OPTIMAL_CPU_THREADS,
                   help=f"Số luồng CPU nạp ảnh (mặc định: {OPTIMAL_CPU_THREADS}).")
    return p.parse_args()


def extract_features_main():
    args = parse_args()

    keyframes_dir = os.path.abspath(args.keyframes_dir)
    print("=" * 65)
    print("🚀 TRÍCH XUẤT VECTOR ĐẶC TRƯNG HÌNH ẢNH — GOOGLE SIGLIP 2 GIANT")
    print(f"📁 Thư mục keyframes: {keyframes_dir}")
    print(f"🧠 Mô hình: {args.model} ({args.pretrained}) | Vector 1152d FP16")
    print(f"⚡ CPU Threads: {OPTIMAL_CPU_THREADS} / {_cpu_cores} luồng phần cứng")
    print("=" * 65)

    if not os.path.exists(keyframes_dir):
        print(f"❌ Lỗi: Thư mục '{keyframes_dir}' không tồn tại.")
        return False

    # Tìm kiếm toàn bộ ảnh keyframe
    image_paths = []
    for root, _, files in os.walk(keyframes_dir, followlinks=True):
        if "maps" in root:
            continue
        for file in files:
            if file.lower().endswith(('.webp', '.png', '.jpg', '.jpeg')):
                image_paths.append(os.path.join(root, file))

    image_paths.sort()
    print(f"🔍 Tìm thấy {len(image_paths):,} ảnh keyframe.")

    if len(image_paths) == 0:
        print("❌ Lỗi: Không tìm thấy ảnh hợp lệ!")
        return False

    # Kiểm tra Resume / Skip nếu đã trích xuất từ trước
    if os.path.exists(args.output_features) and os.path.exists(args.output_paths):
        try:
            existing_feats = np.load(args.output_features, mmap_mode='r')
            existing_paths = np.load(args.output_paths, allow_pickle=True)
            if len(existing_feats) == len(image_paths) and len(existing_paths) == len(image_paths):
                print(f"⏩ [SKIP] Đã có đủ 100% vector ({len(existing_feats):,} keyframes, dim {existing_feats.shape[1]}). Bỏ qua!")
                return True
        except Exception:
            pass

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🎮 Thiết bị tính toán: {device}")

    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        try:
            torch.cuda.set_per_process_memory_fraction(0.88)
        except Exception:
            pass
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"   GPU: {torch.cuda.get_device_name(0)} | VRAM: {vram_gb:.2f} GB")

    # Nạp mô hình Google SigLIP 2 Giant
    print(f"📦 Đang nạp mô hình: {args.model} ({args.pretrained})...")
    model, _, preprocess = open_clip.create_model_and_transforms(args.model, pretrained=args.pretrained)

    # Chuyển mô hình sang FP16 để tối ưu bộ nhớ VRAM và tăng tốc Tensor Core
    if device.type == "cuda":
        model = model.to(device=device, dtype=torch.float16).eval()
    else:
        model = model.to(device).eval()

    eff_batch_size = min(args.batch_size, 28)
    num_loader_workers = min(args.workers, 12)
    print(f"⚡ Batch Size = {eff_batch_size} | DataLoader Workers = {num_loader_workers}")

    dataset = KeyframeDataset(image_paths, preprocess)
    dataloader = DataLoader(
        dataset,
        batch_size=eff_batch_size,
        shuffle=False,
        num_workers=num_loader_workers,
        pin_memory=True if device.type == "cuda" else False,
        persistent_workers=True if num_loader_workers > 0 else False,
        prefetch_factor=2 if num_loader_workers > 0 else None
    )

    features = []
    valid_paths = []

    with torch.inference_mode():
        for batch_imgs, batch_paths, batch_valid in tqdm(dataloader, desc="⚡ Trích xuất SigLIP 2 Giant (FP16 CUDA)"):
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
        print("❌ Lỗi: Không trích xuất được vector nào!")
        return False

    features = np.vstack(features).astype('float32')

    # Lưu file dạng Atomic để chống hỏng file
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

    os.replace(temp_feat, args.output_features)
    os.replace(temp_paths, args.output_paths)

    feat_size_mb = os.path.getsize(args.output_features) / (1024 * 1024)
    print(f"\n🎉 HOÀN TẤT! Đã trích xuất {len(features):,} vector (kích thước {features.shape[1]} chiều).")
    print(f"💾 File vector: '{args.output_features}' ({feat_size_mb:.1f} MB)")
    print(f"💾 File đường dẫn: '{args.output_paths}'")
    return True


if __name__ == '__main__':
    extract_features_main()
