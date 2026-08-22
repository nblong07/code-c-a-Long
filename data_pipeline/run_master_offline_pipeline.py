#!/usr/bin/env python3
"""
MASTER OFFLINE PIPELINE - Multimodal Indexing
Optimized for Laptop RTX 3050 6GB VRAM + 16GB RAM
==============================================================
Runs sequentially to avoid GPU OOM:
Step 1: Adaptive Shot & Sharp Keyframe Extraction (TransNetV2 + Laplacian Blur Filter)
Step 2: Speech-to-Text Transcription (Faster-Whisper Large-v3-Turbo + Silero VAD)
Step 3: Text on Screen OCR (PaddleOCR PP-OCRv4 + CLAHE Contrast Enhancement)
Step 4: Synchronize & Merge Multimodal Metadata (ocr_asr_metadata.json)
Step 5: Visual Feature Vector Extraction (Google SigLIP 2 Giant - ViT-gopt-16-SigLIP2-384)
"""

import os
import sys
import time
import argparse
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def clean_gpu_memory():
    try:
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

def run_step(cmd_list, step_name):
    print("\n" + "=" * 70)
    print(f"🚀 [BẮT ĐẦU] {step_name}")
    print(f"Lệnh thực thi: {' '.join(cmd_list)}")
    print("=" * 70)
    
    clean_gpu_memory()
    start_t = time.time()
    
    res = subprocess.run(cmd_list, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    clean_gpu_memory()
    
    elapsed = time.time() - start_t
    if res.returncode != 0:
        print(f"❌ [LỖI] {step_name} thất bại với mã lỗi {res.returncode} sau {elapsed:.1f}s!")
        return False
    else:
        print(f"✅ [HOÀN TẤT] {step_name} thành công trong {elapsed:.1f}s!")
        return True

def main():
    parser = argparse.ArgumentParser(description="Chạy toàn bộ Offline Data Pipeline cho tập video mới.")
    parser.add_argument("--videos-dir", type=str, nargs="+", required=True, help="Đường dẫn một hoặc nhiều thư mục chứa video mới")
    parser.add_argument("--keyframes-dir", type=str, default="./data-keyframes", help="Thư mục xuất keyframes")
    parser.add_argument("--model", type=str, default="ViT-gopt-16-SigLIP2-384", help="Mô hình Visual Backbone (mặc định: Google SigLIP 2 Giant ViT-gopt-16-SigLIP2-384)")
    parser.add_argument("--skip-keyframes", action="store_true", help="Bỏ qua bước 1 (nếu đã trích xuất keyframes)")
    parser.add_argument("--skip-asr", action="store_true", help="Bỏ qua bước 2 (ASR)")
    parser.add_argument("--skip-ocr", action="store_true", help="Bỏ qua bước 3 (OCR)")
    parser.add_argument("--parallel-videos", type=int, default=3, help="Số video cắt frame song song (mặc định: 3 tối ưu GPU)")
    parser.add_argument("--batch-size", type=int, default=512, help="GPU batch size cho TransNetV2 (mặc định: 512)")
    parser.add_argument("--workers", type=int, default=16, help="Số luồng ghi ảnh WebP (mặc định: 16)")
    args = parser.parse_args()

    # Xử lý danh sách các thư mục video đầu vào
    input_dirs = [os.path.abspath(d) for d in args.videos_dir]
    kf_dir = os.path.abspath(args.keyframes_dir)
    python_exe = sys.executable

    print("\n" + "#" * 70)
    print("🎯 BẮT ĐẦU QUY TRÌNH OFFLINE INDEXING ĐA PHƯƠNG THỨC (SIGLIP 2 GIANT)")
    print(f"📁 Tổng số thư mục video đầu vào: {len(input_dirs)}")
    for i, d in enumerate(input_dirs, 1):
        print(f"   [{i}] {d}")
    print(f"📁 Thư mục keyframe đầu ra: {kf_dir}")
    print(f"🧠 Visual Backbone: {args.model} (Google SigLIP 2 Giant SOTA)")
    print(f"⚡ Cấu hình cắt frame: Parallel Videos={args.parallel_videos}, Batch Size={args.batch_size}, I/O Workers={args.workers}")
    print("#" * 70)

    total_start = time.time()

    for dir_idx, v_dir in enumerate(input_dirs, 1):
        print("\n" + "🔥" * 35)
        print(f"🎬 ĐANG XỬ LÝ THƯ MỤC [{dir_idx}/{len(input_dirs)}]: {v_dir}")
        print("🔥" * 35)

        # Bước 1: Keyframe Extraction
        if not args.skip_keyframes:
            cmd1 = [
                python_exe, "data_pipeline/transnetv2_keyframes.py",
                "--input-folder", v_dir,
                "--output-base", kf_dir,
                "--parallel-videos", str(args.parallel_videos),
                "--batch-size", str(args.batch_size),
                "--workers", str(args.workers)
            ]
            if not run_step(cmd1, f"Bước 1/5 ({dir_idx}/{len(input_dirs)}): Trích xuất Frame & Lọc mờ ({os.path.basename(v_dir)})"):
                continue

        # Bước 2: ASR Extraction
        if not args.skip_asr:
            os.environ["VIDEO_DIR"] = v_dir
            cmd2 = [python_exe, "data_pipeline/extract_asr_advanced.py"]
            if not run_step(cmd2, f"Bước 2/5 ({dir_idx}/{len(input_dirs)}): Bóc băng Lời thoại ASR ({os.path.basename(v_dir)})"):
                continue

    # Bước 3: OCR Extraction
    if not args.skip_ocr:
        os.environ["OCR_BATCH_SIZE"] = "16"
        cmd3 = [python_exe, "data_pipeline/extract_ocr_advanced.py", "--keyframes-dir", kf_dir]
        if not run_step(cmd3, "Bước 3/5: Trích xuất Chữ viết OCR (PaddleOCR PP-OCRv4 + CLAHE)"):
            return

    # Bước 4: Merge Metadata
    cmd4 = [python_exe, "data_pipeline/merge_ocr_asr_metadata.py"]
    if not run_step(cmd4, "Bước 4/5: Đồng bộ & Gộp Metadata OCR & ASR (ocr_asr_metadata.json)"):
        return

    # Bước 5: Feature Extraction
    cmd5 = [
        python_exe, "data_pipeline/extract_features.py", "1",
        "--keyframes-dir", kf_dir,
        "--model", args.model,
        "--batch-size", "24"
    ]
    if not run_step(cmd5, "Bước 5/5: Trích xuất Vector Đặc trưng Thị giác (Google SigLIP 2 Giant 1152d FP16)"):
        return

    total_time = time.time() - total_start
    print("\n" + "=" * 70)
    print(f"🎉 TẤT CẢ DỮ LIỆU ĐÃ ĐƯỢC INDEX XONG TRONG {total_time / 60:.2f} PHÚT!")
    print("👉 Hệ thống sẵn sàng khởi động Server để thi đấu: python -m uvicorn backend.main:app")
    print("=" * 70)

if __name__ == "__main__":
    main()
