"""
Keyframe Extractor — Optimized for Windows 11 (16GB RAM + NVIDIA 6GB GPU)
=======================================================================
Extracts keyframes from videos using OpenCLIP visual similarity.
Only saves representative frames when the visual content changes beyond threshold.
"""

import argparse
import csv
import glob
import os
import sys
from typing import List

import cv2
import torch
import torch.nn.functional as F
from PIL import Image
from tqdm import tqdm
import open_clip


def preprocess_frame(frame, preprocess):
    """Convert OpenCV BGR numpy frame to PIL RGB and preprocess for CLIP"""
    pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return preprocess(pil_image).unsqueeze(0)  # (1, C, H, W)


def encode_batch(frames: List, model, preprocess, device: torch.device) -> torch.Tensor:
    """CPU image preprocessing + GPU visual encoding (DINOv2 / OpenCLIP)"""
    processed = [preprocess_frame(fr, preprocess) for fr in frames]
    images = torch.cat(processed, dim=0).to(device, non_blocking=True)  # (B, C, H, W)

    with torch.inference_mode():
        if device.type == "cuda":
            with torch.amp.autocast(device_type="cuda"):
                if hasattr(model, "encode_image"):
                    feats = model.encode_image(images)
                else:
                    feats = model(images)
        else:
            if hasattr(model, "encode_image"):
                feats = model.encode_image(images)
            else:
                feats = model(images)

        feats = F.normalize(feats.float(), dim=-1)  # unit-length cosine similarity
    return feats


def save_image_webp(img_bgr, path: str, quality: int = 80, resize_factor: float = 0.5):
    """Save keyframe image as optimized WebP format"""
    if resize_factor != 1.0:
        img_bgr = cv2.resize(img_bgr, (0, 0), fx=resize_factor, fy=resize_factor)
    img_pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img_pil.save(path, format="WEBP", quality=quality)


def process_video(
    video_path: str,
    out_dir: str,
    maps_dir: str,
    model,
    preprocess,
    device: torch.device,
    clip_threshold: float,
    skip_frames: int,
    batch_size: int = 32,
    resize_factor: float = 0.5,
    webp_quality: int = 80,
) -> int:
    os.makedirs(out_dir, exist_ok=True)
    kf_dir = os.path.join(out_dir, "keyframes")
    os.makedirs(kf_dir, exist_ok=True)
    os.makedirs(maps_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"⚠️ Warning: Failed to open video: {video_path}")
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    map_csv = os.path.join(maps_dir, f"{video_name}_map.csv")

    frames: List = []
    indices: List[int] = []
    keyframe_count = 0
    prev_feat = None

    def evaluate_batch(frames_buf, indices_buf, prev_f, count, csv_writer):
        feats = encode_batch(frames_buf, model, preprocess, device)
        for img, fid, feat in zip(frames_buf, indices_buf, feats):
            if prev_f is None:
                kf_path = os.path.join(kf_dir, f"keyframe_{fid}.webp")
                save_image_webp(img, kf_path, quality=webp_quality, resize_factor=resize_factor)
                csv_writer.writerow([fid, f"{fid / fps:.2f}"])
                prev_f = feat
                count += 1
            else:
                sim = torch.dot(prev_f, feat).item()
                if sim < clip_threshold:
                    kf_path = os.path.join(kf_dir, f"keyframe_{fid}.webp")
                    save_image_webp(img, kf_path, quality=webp_quality, resize_factor=resize_factor)
                    csv_writer.writerow([fid, f"{fid / fps:.2f}"])
                    prev_f = feat
                    count += 1
        return prev_f, count

    with open(map_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["FrameID", "Seconds"])

        pbar = tqdm(total=total_frames if total_frames > 0 else None, desc=f"Processing {video_name}")
        frame_id = 0

        while True:
            ok, frame = cap.read()
            if not ok:
                break

            # process every (skip_frames + 1)-th frame
            if skip_frames < 0 or (frame_id % (skip_frames + 1) == 0):
                frames.append(frame)
                indices.append(frame_id)

                if len(frames) >= batch_size:
                    prev_feat, keyframe_count = evaluate_batch(frames, indices, prev_feat, keyframe_count, writer)
                    frames.clear()
                    indices.clear()

            frame_id += 1
            pbar.update(1)

        # Flush remaining buffer
        if frames:
            prev_feat, keyframe_count = evaluate_batch(frames, indices, prev_feat, keyframe_count, writer)
            frames.clear()
            indices.clear()

        pbar.close()
    cap.release()
    return keyframe_count


def process_all_videos(
    input_folder: str,
    output_base: str,
    clip_threshold: float,
    skip_frames: int,
    batch_size: int,
    resize_factor: float,
    webp_quality: int,
    start_index: int,
    pattern: str,
    model_name: str,
    pretrained: str,
    device: torch.device,
):
    print(f"🚀 Loading model: '{model_name}' on device {device}...")
    if "dinov2" in model_name.lower():
        from torchvision import transforms
        model = torch.hub.load('facebookresearch/dinov2', model_name).to(device).eval()
        preprocess = transforms.Compose([
            transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    else:
        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained
        )
        model = model.to(device).eval()

    video_files = sorted(glob.glob(os.path.join(input_folder, pattern)))
    if not video_files:
        print(f"❌ No videos found matching pattern: {os.path.join(input_folder, pattern)}")
        return

    maps_dir = os.path.join(output_base, "maps")
    os.makedirs(maps_dir, exist_ok=True)

    print(f"Found {len(video_files)} videos. Starting from index {start_index}...")

    for i, video_path in enumerate(video_files[start_index:], start=start_index):
        name = os.path.splitext(os.path.basename(video_path))[0]
        out_dir = os.path.join(output_base, name)
        os.makedirs(out_dir, exist_ok=True)

        print(f"\n[{i+1}/{len(video_files)}] Processing video: {name}")
        try:
            kf_count = process_video(
                video_path=video_path,
                out_dir=out_dir,
                maps_dir=maps_dir,
                model=model,
                preprocess=preprocess,
                device=device,
                clip_threshold=clip_threshold,
                skip_frames=skip_frames,
                batch_size=batch_size,
                resize_factor=resize_factor,
                webp_quality=webp_quality,
            )
            print(f"✅ Finished {name}: {kf_count} keyframes extracted.")
        except Exception as e:
            print(f"❌ Error processing {name}: {e}")


def parse_args():
    p = argparse.ArgumentParser(
        description="Extract visual keyframes using OpenCLIP cosine similarity."
    )
    p.add_argument("--input-folder", type=str, required=True,
                   help="Folder containing input videos.")
    p.add_argument("--output-base", type=str, default="./output-keyframes",
                   help="Output directory for keyframe images and CSV maps.")
    p.add_argument("--pattern", type=str, default="*.mp4",
                   help="File search glob pattern (e.g. '*.mp4').")
    p.add_argument("--start-index", type=int, default=0,
                   help="Index of video to start processing from.")
    p.add_argument("--clip-threshold", type=float, default=0.93,
                   help="Cosine similarity threshold for scene detection.")
    p.add_argument("--skip-frames", type=int, default=5,
                   help="Process every (skip_frames + 1)-th frame.")
    p.add_argument("--batch-size", type=int, default=32,
                   help="Batch size for CLIP visual encoding (32 fits well in 6GB GPU).")
    p.add_argument("--resize-factor", type=float, default=0.5,
                   help="Scale factor for output WebP image size (0.5 saves storage).")
    p.add_argument("--webp-quality", type=int, default=80,
                   help="WebP image quality (0-100).")
    p.add_argument("--model", type=str, default="ViT-L-14",
                   help="Visual backbone model architecture (default: ViT-L-14).")
    p.add_argument("--pretrained", type=str, default="laion2b_s32b_b82k",
                   help="Pretrained weights dataset (default: laion2b_s32b_b82k).")
    p.add_argument("--cpu", action="store_true",
                   help="Force CPU execution.")
    return p.parse_args()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    device = torch.device("cpu" if args.cpu or not torch.cuda.is_available() else "cuda")
    process_all_videos(
        input_folder=args.input_folder,
        output_base=args.output_base,
        clip_threshold=args.clip_threshold,
        skip_frames=args.skip_frames,
        batch_size=args.batch_size,
        resize_factor=args.resize_factor,
        webp_quality=args.webp_quality,
        start_index=args.start_index,
        pattern=args.pattern,
        model_name=args.model,
        pretrained=args.pretrained,
        device=device,
    )


if __name__ == "__main__":
    main()

