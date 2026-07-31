"""
Standalone Feature Extractor — Extract CLIP image features to numpy file
========================================================================
"""

import os
import argparse
import torch
import torch.nn.functional as F
import open_clip
from PIL import Image
import numpy as np
from tqdm import tqdm


def parse_args():
    p = argparse.ArgumentParser(description="Extract CLIP feature vectors to numpy format.")
    p.add_argument("--keyframes-dir", type=str, default="./data-keyframes",
                   help="Path to directory containing keyframe images.")
    p.add_argument("--output-features", type=str, default="features.npy",
                   help="Output path for feature array.")
    p.add_argument("--output-paths", type=str, default="image_paths.npy",
                   help="Output path for image paths array.")
    p.add_argument("--model", type=str, default="ViT-L-14",
                   help="Model architecture name (default: ViT-L-14).")
    p.add_argument("--pretrained", type=str, default="laion2b_s32b_b82k",
                   help="Pretrained weights dataset (default: laion2b_s32b_b82k).")
    p.add_argument("--batch-size", type=int, default=32,
                   help="Batch size for feature extraction.")
    return p.parse_args()


def main():
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
    for root, _, files in os.walk(keyframes_dir):
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

    if "dinov2" in args.model.lower():
        from torchvision import transforms
        model = torch.hub.load('facebookresearch/dinov2', args.model).to(device).eval()
        preprocess = transforms.Compose([
            transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    else:
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

    print(f"\n✅ SUCCESS! Extracted {len(features)} vector features (dimension: {features.shape[1]}).")
    print(f"Saved features to '{args.output_features}' and paths to '{args.output_paths}'.")


if __name__ == "__main__":
    main()