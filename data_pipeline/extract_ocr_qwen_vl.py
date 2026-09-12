"""
Quy trình trích xuất văn bản OCR bằng mô hình Qwen2-VL-2B-Instruct
- Mô hình: Qwen/Qwen2-VL-2B-Instruct (2.2 tỷ tham số, định dạng float16, cơ chế SDPA attention).
- Độ phân giải xử lý: Tối thiểu 200,704 pixels (256x28x28), tối đa Native Full Resolution (1920x1080).
- Tiền xử lý: Lọc watermark và logo đài truyền hình lặp lại để hạn chế nhiễu chỉ mục BM25.
- Đầu ra: ocr_results.jsonl và đồng bộ vào ocr_asr_metadata.json.
"""

import os
import sys
import json
import glob
import re
import logging
import argparse
from pathlib import Path
from PIL import Image
from tqdm import tqdm
import torch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="ignore")

# Cấu hình tối ưu phần cứng (80-90% công suất: ~13-14 luồng CPU và ~5.1-5.3 GB VRAM trên RTX 3050 6GB)
_cpu_cores = os.cpu_count() or 8
OPTIMAL_CPU_THREADS = max(1, int(_cpu_cores * 0.85))
torch.set_num_threads(OPTIMAL_CPU_THREADS)

if torch.cuda.is_available():
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    try:
        torch.cuda.set_per_process_memory_fraction(0.88, 0)
    except Exception:
        pass

# Cấu hình logging chuẩn
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("qwen_ocr")

# Thư mục gốc dự án
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_KEYFRAME_ROOT = os.path.join(BASE_DIR, "data-keyframes")
OUTPUT_FILE = os.path.join(BASE_DIR, "ocr_results.jsonl")
DONE_FILE = os.path.join(BASE_DIR, "ocr_done.txt")
METADATA_FILE = os.path.join(BASE_DIR, "ocr_asr_metadata.json")

# Danh sách từ khóa watermark cần lọc bỏ
BLACKLIST_WATERMARKS = [
    re.compile(r"^\s*(htv|hiv|thanhnien|thanh niên|vtv|hệ thao|he thao)\b", re.IGNORECASE),
    re.compile(r"^\s*\d{2}:\d{2}:\d{2}\s*(\|\s*giây.*)?$", re.IGNORECASE),
]

def is_unwanted_text(text: str) -> bool:
    """Lọc bỏ các text rác, mốc thời gian hoặc ký tự quá ngắn."""
    cleaned = text.strip().lower()
    if not cleaned or cleaned == "no_text" or len(cleaned) < 2:
        return True
    for pat in BLACKLIST_WATERMARKS:
        if pat.search(cleaned):
            return True
    return False

def clean_and_normalize_ocr(raw_text: str) -> str:
    """Chuẩn hóa kết quả OCR từ mô hình thị giác ngôn ngữ."""
    if not raw_text:
        return ""
    raw_text = re.sub(r"\bNO_TEXT\b", "", raw_text, flags=re.IGNORECASE)
    parts = [p.strip() for p in raw_text.split("|") if p.strip()]
    
    filtered_parts = []
    for p in parts:
        if not is_unwanted_text(p):
            filtered_parts.append(p)
            
    return " | ".join(filtered_parts)

class QwenOCRExtractor:
    def __init__(
        self,
        model_id: str = "Qwen/Qwen2-VL-2B-Instruct",
        device: str = "cuda",
        min_pixels: int = 256 * 28 * 28,
        max_pixels: int = None,
        crop_top: float = 0.0,
        crop_bottom: float = 1.0,
    ):
        logger.info(f"Khoi tao mo hinh Qwen2-VL OCR: {model_id} (CPU threads: {OPTIMAL_CPU_THREADS})...")
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        from qwen_vl_utils import process_vision_info
        
        self.device = device if torch.cuda.is_available() else "cpu"
        self.process_vision_info = process_vision_info
        self.crop_top = max(0.0, min(1.0, float(crop_top)))
        self.crop_bottom = max(0.0, min(1.0, float(crop_bottom)))
        if self.crop_top >= self.crop_bottom:
            self.crop_top, self.crop_bottom = 0.0, 1.0

        proc_kwargs = {"min_pixels": min_pixels}
        if max_pixels is not None and str(max_pixels).lower() != "max":
            proc_kwargs["max_pixels"] = int(max_pixels)
            logger.info(f"Cau hinh do phan giai: Min={min_pixels:,} pixels, Max={int(max_pixels):,} pixels")
        else:
            proc_kwargs["max_pixels"] = 2048 * 28 * 28
            logger.info(f"Cau hinh do phan giai: Min={min_pixels:,} pixels, Max=Native Full Resolution")

        if self.crop_top > 0.0 or self.crop_bottom < 1.0:
            logger.info(f"Vung cat anh (Crop ROI): Tu Y={self.crop_top*100:.1f}% den Y={self.crop_bottom*100:.1f}%")

        self.processor = AutoProcessor.from_pretrained(
            model_id,
            **proc_kwargs
        )
        
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        model_kwargs = {
            "torch_dtype": dtype,
            "device_map": "auto" if self.device == "cuda" else None,
        }
        if self.device == "cuda":
            model_kwargs["attn_implementation"] = "sdpa"

        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_id,
            **model_kwargs
        )
        self.model.eval()
        
        if self.device == "cuda":
            allocated_gb = torch.cuda.memory_allocated() / (1024 ** 3)
            logger.info(f"Da tai mo hinh len GPU thanh cong (VRAM: {allocated_gb:.2f} GB / 6.0 GB).")
            
    def predict_image(self, image_path: str) -> str:
        """Thực hiện trích xuất toàn bộ text trong 1 ảnh keyframe."""
        try:
            image = Image.open(image_path).convert("RGB")
            # Nếu có cấu hình cắt vùng (Crop):
            if self.crop_top > 0.0 or self.crop_bottom < 1.0:
                w, h = image.size
                y1 = int(h * self.crop_top)
                y2 = int(h * self.crop_bottom)
                image = image.crop((0, y1, w, y2))
        except Exception as e:
            logger.warning(f"Không thể đọc ảnh {image_path}: {e}")
            return ""

        prompt_text = (
            "Trích xuất chính xác toàn bộ chữ viết, con số, biển số xe (ô tô, xe máy), "
            "tên bảng hiệu, biển báo đường phố, tiêu đề và phụ đề xuất hiện trong ảnh này. "
            "Nếu không có chữ, chỉ trả lời NO_TEXT. "
            "Chỉ liệt kê các chuỗi chữ phân tách nhau bằng dấu ' | ', không giải thích thêm."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt_text}
                ]
            }
        ]

        text_input = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = self.process_vision_info(messages)
        inputs = self.processor(
            text=[text_input],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt"
        )
        inputs = inputs.to(self.device)

        import torch
        with torch.no_grad():
            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=128,
                do_sample=False
            )
            generated_ids_trimmed = [
                out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
            ]
            output_text = self.processor.batch_decode(
                generated_ids_trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False
            )

        raw_result = output_text[0] if output_text else ""
        return clean_and_normalize_ocr(raw_result)

def sync_to_metadata_json():
    """Dong bo ket qua OCR vao file tong ocr_asr_metadata.json"""
    logger.info(f"Dong bo du lieu OCR vao {METADATA_FILE}...")
    current_data = {"ocr": {}, "asr": {}}
    if os.path.isfile(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception as e:
            logger.warning(f"Khong the doc {METADATA_FILE}, khoi tao cau truc moi: {e}")

    ocr_dict = current_data.get("ocr", {})
    if not isinstance(ocr_dict, dict):
        ocr_dict = {}

    count_added = 0
    if os.path.isfile(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    txt = (item.get("text") or "").strip()
                    if txt:
                        vid = item.get("video_id", "")
                        fid = item.get("frame_id", "0")
                        key = f"{vid}/keyframes/keyframe_{fid}.webp"
                        ocr_dict[key] = txt
                        count_added += 1
                except Exception:
                    continue

    current_data["ocr"] = ocr_dict
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Da dong bo {len(ocr_dict):,} ban ghi OCR vao {METADATA_FILE}.")

def main():
    parser = argparse.ArgumentParser(description="Trích xuất OCR bằng mô hình Qwen2-VL")
    parser.add_argument("--keyframes-dir", type=str, default=DEFAULT_KEYFRAME_ROOT, help="Đường dẫn thư mục data-keyframes")
    parser.add_argument("--model-id", type=str, default="Qwen/Qwen2-VL-2B-Instruct", help="Tên model HuggingFace Qwen2-VL")
    parser.add_argument("--min-pixels", type=int, default=256 * 28 * 28, help="Số pixel tối thiểu (mặc định: 256*28*28 = 200,704)")
    parser.add_argument("--max-pixels", type=str, default="max", help="Số pixel tối đa ('max' để giữ nguyên độ phân giải gốc của ảnh, hoặc nhập số như 2073600)")
    parser.add_argument("--crop-top", type=float, default=0.0, help="Tỉ lệ bắt đầu cắt từ đỉnh màn hình (0.0 đến 1.0, mặc định 0.0)")
    parser.add_argument("--crop-bottom", type=float, default=1.0, help="Tỉ lệ cắt đến đáy màn hình (0.0 đến 1.0, mặc định 1.0 tối đa)")
    parser.add_argument("--batch-size", type=int, default=1, help="Kích thước batch (mặc định 1 ảnh)")
    parser.add_argument("--limit-videos", type=int, default=None, help="Giới hạn số lượng video cần chạy (dùng test)")
    args = parser.parse_args()

    # Nạp danh sách video đã hoàn thành (Resume)
    done_videos = set()
    if os.path.exists(DONE_FILE):
        with open(DONE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                v = line.strip()
                if v:
                    done_videos.add(v)
        logger.info(f"⏩ Đã nạp {len(done_videos):,} video đã hoàn thành trước đó (Resume Mode).")

    # Quét tất cả các thư mục video chứa keyframes
    pattern = os.path.join(args.keyframes_dir, "**", "keyframes")
    kf_folders = glob.glob(pattern, recursive=True)

    if not kf_folders:
        logger.warning(f"Không tìm thấy thư mục keyframes nào trong {args.keyframes_dir}!")
        return

    logger.info(f"Tìm thấy {len(kf_folders):,} thư mục keyframes cần xử lý.")

    # Khởi tạo mô hình Qwen2-VL
    extractor = QwenOCRExtractor(
        model_id=args.model_id,
        min_pixels=args.min_pixels,
        max_pixels=args.max_pixels,
        crop_top=args.crop_top,
        crop_bottom=args.crop_bottom,
    )

    total_processed_frames = 0
    total_saved_ocr = 0

    with open(OUTPUT_FILE, "a", encoding="utf-8") as out_f, open(DONE_FILE, "a", encoding="utf-8") as done_f:
        for idx, kf_dir in enumerate(kf_folders):
            video_dir = os.path.dirname(kf_dir)
            rel_video_id = os.path.relpath(video_dir, args.keyframes_dir).replace("\\", "/")

            if rel_video_id in done_videos:
                continue

            if args.limit_videos and idx >= args.limit_videos:
                logger.info(f"Đã đạt giới hạn {args.limit_videos} video.")
                break

            # Lấy danh sách ảnh keyframe
            image_files = glob.glob(os.path.join(kf_dir, "*.webp"))
            if not image_files:
                image_files = glob.glob(os.path.join(kf_dir, "*.jpg")) + glob.glob(os.path.join(kf_dir, "*.png"))

            if not image_files:
                done_videos.add(rel_video_id)
                done_f.write(f"{rel_video_id}\n")
                done_f.flush()
                continue

            # Sắp xếp theo số frame id
            def get_fid(p):
                stem = Path(p).stem
                m = re.search(r"(\d+)", stem)
                return int(m.group(1)) if m else 0
            image_files.sort(key=get_fid)

            logger.info(f"[{idx+1}/{len(kf_folders)}] Đang xử lý {rel_video_id} ({len(image_files)} keyframes)...")

            for img_p in tqdm(image_files, desc=f"OCR {rel_video_id}", leave=False):
                fid = get_fid(img_p)
                ocr_text = extractor.predict_image(img_p)

                total_processed_frames += 1
                if ocr_text:
                    record = {
                        "video_id": rel_video_id,
                        "frame_id": fid,
                        "text": ocr_text,
                        "source": "qwen2-vl",
                    }
                    out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out_f.flush()
                    total_saved_ocr += 1

            done_videos.add(rel_video_id)
            done_f.write(f"{rel_video_id}\n")
            done_f.flush()

    # Cuối cùng đồng bộ vào ocr_asr_metadata.json
    sync_to_metadata_json()
    logger.info("=" * 60)
    logger.info("Hoan tat trich xuat OCR voi Qwen2-VL.")
    logger.info(f"Tong so keyframe da xu ly: {total_processed_frames:,}")
    logger.info(f"So keyframe phat hien chu: {total_saved_ocr:,}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
