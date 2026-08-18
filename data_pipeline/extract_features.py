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
        print(f"âŒ Error: Path '{keyframes_dir}' does not exist.")
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
    """Trích xuất chữ viết xuất hiện trong khung hình keyframe (OCR)"""
    ocr_results = {}
    
    # [TÍCH HỢP CHỌN LỌC] Đọc kết quả từ script test_ocr.py nâng cao nếu có
    advanced_ocr_file = "ocr_results.jsonl"
    if os.path.exists(advanced_ocr_file):
        print(f"🌟 Đang tích hợp dữ liệu OCR từ mô hình nâng cao ({advanced_ocr_file})...")
        try:
            with open(advanced_ocr_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    data = json.loads(line)
                    # File jsonl của test_ocr lưu các segment có trường 'text'
                    if "video_path" in data and "text" in data and data["text"]:
                        # Giả định video_path có thể chứa đường dẫn file ảnh keyframe
                        path = data["video_path"]
                        rel_path = os.path.relpath(path, keyframes_dir) if os.path.isabs(path) else path
                        ocr_results[rel_path] = data["text"]
            if ocr_results:
                print(f"✅ Đã nạp {len(ocr_results)} kết quả OCR nâng cao (có fix lỗi chính tả & CLAHE).")
                return ocr_results
        except Exception as e:
            print(f"⚠️ Lỗi đọc {advanced_ocr_file}: {e}. Rớt xuống (fallback) OCR cơ bản.")

    # Fallback OCR cơ bản
    try:
        from paddleocr import PaddleOCR
        reader = PaddleOCR(use_angle_cls=True, lang='vi', use_gpu=True, show_log=False)
        use_paddle = True
    except Exception:
        use_paddle = False
        print("⚠️ PaddleOCR chưa sẵn sàng. Chạy chế độ fallback trống.")

    image_paths = []
    for root, _, files in os.walk(keyframes_dir):
        for f in files:
            if f.lower().endswith(('.webp', '.jpg', '.jpeg', '.png')):
                image_paths.append(os.path.join(root, f))
                
    print(f"🔍 Đang chạy OCR cơ bản trên {len(image_paths)} keyframes...")
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
    """Trích xuất lời nói từ file audio trong video (ASR Speech-to-Text)"""
    asr_results = {}
    
    # [TÍCH HỢP CHỌN LỌC] Đọc kết quả từ script test_asr.py nâng cao nếu có
    advanced_asr_file = "asr_results.jsonl"
    if os.path.exists(advanced_asr_file):
        print(f"🌟 Đang tích hợp dữ liệu ASR từ mô hình nâng cao ({advanced_asr_file})...")
        try:
            with open(advanced_asr_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    data = json.loads(line)
                    # File jsonl của test_asr lưu các segment có text hoặc status
                    if "video_path" in data and "text" in data and data["text"]:
                        v_name = os.path.splitext(os.path.basename(data["video_path"]))[0]
                        # Gộp text của các segment trong cùng 1 video
                        existing = asr_results.get(v_name, "")
                        asr_results[v_name] = (existing + " " + data["text"]).strip()
            if asr_results:
                print(f"✅ Đã nạp kết quả ASR nâng cao cho {len(asr_results)} video (có Silero VAD & RingBuffer).")
                return asr_results
        except Exception as e:
            print(f"⚠️ Lỗi đọc {advanced_asr_file}: {e}. Rớt xuống (fallback) ASR cơ bản.")

    # Fallback ASR cơ bản
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
            model = WhisperModel("large-v3", device="cuda", compute_type="float16")
            use_whisper = True
            print("🎙️ Sử dụng mô hình ASR SOTA Faster-Whisper Large-v3...")
        except Exception:
            use_whisper = False
            print("⚠️ Cả Sherpa-ONNX và Faster-Whisper chưa sẵn sàng. Chạy chế độ fallback trống.")
    else:
        print("⚡ Sử dụng mô hình ASR cơ bản Sherpa-ONNX Zipformer...")

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
