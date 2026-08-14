"""
Standalone Feature Extractor â€” Extract CLIP image features to numpy file
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
    p.add_argument("--model", type=str, default="ViT-SO400M-14-SigLIP-384",
                   help="Model architecture name (default: ViT-SO400M-14-SigLIP-384).")
    p.add_argument("--pretrained", type=str, default="webli",
                   help="Pretrained weights dataset (default: webli).")
    p.add_argument("--batch-size", type=int, default=32,
                   help="Batch size for feature extraction.")
    return p.parse_args()


def extract_clip_main():
    args = parse_args()

    keyframes_dir = os.path.abspath(args.keyframes_dir)
    print("--------------------------------------------------")
    print(f"Scanning directory: {keyframes_dir}")
    print(f"Directory exists: {os.path.exists(keyframes_dir)}")

    if not os.path.exists(keyframes_dir):
        print(f"âŒ Error: Path '{keyframes_dir}' does not exist.")
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
        print("âŒ Error: No valid image files found!")
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"ðŸš€ Running feature extraction on device: {device}")

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

    print(f"\nâœ… SUCCESS! Extracted {len(features)} vector features (dimension: {features.shape[1]}).")
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
    """Trích xuất chữ viết xuất hiện trong khung hình keyframe (OCR) - Đã nâng cấp lên SOTA PaddleOCR"""
    ocr_results = {}
    
    try:
        from paddleocr import PaddleOCR
        # Sử dụng mô hình PaddleOCR v4 mới nhất, siêu mạnh cho tiếng Việt
        reader = PaddleOCR(use_angle_cls=True, lang='vi', use_gpu=True, show_log=False)
        use_paddle = True
    except Exception:
        use_paddle = False
        print("⚠️ PaddleOCR chưa sẵn sàng (cài đặt: pip install paddlepaddle-gpu paddleocr). Chạy chế độ fallback.")

    image_paths = []
    for root, _, files in os.walk(keyframes_dir):
        for f in files:
            if f.lower().endswith(('.webp', '.jpg', '.jpeg', '.png')):
                image_paths.append(os.path.join(root, f))
                
    print(f"🔍 Đang chạy SOTA OCR trên {len(image_paths)} keyframes...")
    for img_path in tqdm(image_paths):
        rel_path = os.path.relpath(img_path, keyframes_dir)
        if use_paddle:
            try:
                result = reader.ocr(img_path, cls=True)
                if result and result[0]:
                    text_list = [line[1][0] for line in result[0] if line is not None and len(line) > 1]
                    extracted_text = " ".join(text_list)
                else:
                    extracted_text = ""
            except Exception:
                extracted_text = ""
        else:
            extracted_text = ""
            
        ocr_results[rel_path] = extracted_text

    return ocr_results

def extract_asr_from_videos(videos_dir: str):
    """Trích xuất lời nói từ file audio trong video (ASR Speech-to-Text) - Đã nâng cấp lên Faster-Whisper Large-v3"""
    asr_results = {}
    
    # Thử khởi tạo Sherpa-ONNX Zipformer (chế độ nhẹ)
    try:
        from backend.asr_sherpa import SherpaZipformerASR
        sherpa_engine = SherpaZipformerASR()
        use_sherpa = sherpa_engine.is_ready
    except Exception:
        use_sherpa = False

    use_whisper = False
    if not use_sherpa:
        try:
            from faster_whisper import WhisperModel
            # Nâng cấp cấp độ: Sử dụng mô hình large-v3 cực mạnh thay vì base
            model = WhisperModel("large-v3", device="cuda", compute_type="float16")
            use_whisper = True
            print("🎙️ Sử dụng mô hình ASR SOTA Faster-Whisper Large-v3 (Chính xác cao nhất)...")
        except Exception:
            use_whisper = False
            print("⚠️ Cả Sherpa-ONNX và Faster-Whisper chưa sẵn sàng (cài đặt: pip install faster-whisper). Chạy chế độ fallback.")
    else:
        print("⚡ Sử dụng mô hình ASR siêu nhẹ Sherpa-ONNX Zipformer...")

    video_paths = glob.glob(os.path.join(videos_dir, "*.mp4")) + glob.glob(os.path.join(videos_dir, "*.mkv"))
    print(f"🎙️ Đang chạy ASR Speech-to-Text trên {len(video_paths)} video...")
    for v_path in tqdm(video_paths):
        v_name = os.path.splitext(os.path.basename(v_path))[0]
        if use_sherpa:
            res = sherpa_engine.transcribe_video(v_path)
            asr_results[v_name] = res.get("text", "")
        elif use_whisper:
            try:
                segments, info = model.transcribe(v_path, beam_size=5)
                asr_results[v_name] = " ".join([segment.text for segment in segments])
            except Exception:
                asr_results[v_name] = ""
        else:
            asr_results[v_name] = ""

    return asr_results

def extract_ocr_asr_main():
    parser = argparse.ArgumentParser(description="Extract OCR and ASR metadata for Hybrid Search.")
    parser.add_argument("--keyframes-dir", type=str, default="./data-keyframes", help="Path to keyframes directory")
    parser.add_argument("--videos-dir", type=str, default="./data-videos", help="Path to videos directory")
    parser.add_argument("--output", type=str, default="ocr_asr_metadata.json", help="Path to output JSON")
    args = parser.parse_args()

    print("==================================================")
    print("ðŸš€ Báº®T Äáº¦U TRÃCH XUáº¤T OCR & ASR ÄA PHÆ¯Æ NG THá»¨C")
    print("==================================================")

    ocr_data = {}
    if os.path.exists(args.keyframes_dir):
        ocr_data = extract_ocr_from_keyframes(args.keyframes_dir)
    else:
        print(f"âš ï¸ KhÃ´ng tÃ¬m tháº¥y thÆ° má»¥c keyframe: {args.keyframes_dir}")

    asr_data = {}
    if os.path.exists(args.videos_dir):
        asr_data = extract_asr_from_videos(args.videos_dir)
    else:
        print(f"âš ï¸ KhÃ´ng tÃ¬m tháº¥y thÆ° má»¥c video: {args.videos_dir}")

    metadata = {
        "ocr": ocr_data,
        "asr": asr_data
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"âœ… HoÃ n táº¥t! ÄÃ£ lÆ°u káº¿t quáº£ vÃ o file: {args.output}")




if __name__ == '__main__':
    import sys
    print('Choose extraction task: 1 for CLIP, 2 for OCR/ASR, 3 for BOTH')
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input('Enter choice (1/2/3): ')
    
    if choice == '1':
        extract_clip_main()
    elif choice == '2':
        extract_ocr_asr_main()
    elif choice == '3':
        print('--- EXTRACTING CLIP ---')
        # reset sys.argv to avoid conflicts
        sys.argv = [sys.argv[0]]
        extract_clip_main()
        print('--- EXTRACTING OCR/ASR ---')
        extract_ocr_asr_main()
    else:
        print('Invalid choice')
