# Quy Trình Xử Lý Dữ Liệu Ngoại Tuyến (Offline Data Pipeline)

Tài liệu kỹ thuật mô tả chuỗi 6 bước xử lý video ngoại tuyến phục vụ hệ thống truy vấn đa phương thức. Toàn bộ các công đoạn được thực thi độc lập qua giao diện dòng lệnh (CLI), tối ưu hóa cho cấu hình phần cứng cục bộ.

---

## 1. Thông số phần cứng và phân bổ tài nguyên

- **CPU**: AMD 7000 Series (8 nhân / 16 luồng).
  - Phân bổ tính toán: 13–14 luồng (~85% công suất) qua `torch.set_num_threads(13)`, `cv2.setNumThreads(13)`, `faiss.omp_set_num_threads(13)`.
- **RAM**: 16 GB DDR5.
  - Streaming I/O cho DataLoader (`pin_memory=True`, `prefetch_factor=2`, `num_workers=12`).
- **GPU / VRAM**: NVIDIA GeForce RTX 3050 Laptop GPU (6.0 GB GDDR6, 2048 CUDA Cores, 64 Tensor Cores).
  - Định dạng số học: FP16 (Half Precision) kết hợp Tensor Core TF32 (`torch.backends.cuda.matmul.allow_tf32 = True`).
  - Giới hạn bộ nhớ an toàn: `torch.cuda.set_per_process_memory_fraction(0.88, 0)` (~5.28 GB VRAM), ngăn ngừa lỗi phân bổ vượt ngưỡng CUDA OOM.

---

## 2. Thông số kỹ thuật các mô hình sử dụng

| Công đoạn | Mã nguồn | Mô hình / Thuật toán | Thông số kỹ thuật | Mức tiêu thụ VRAM / RAM | Đầu ra |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Khung hình** | `transnetv2_keyframes.py` | `TransNetV2` + Laplacian + dHash | Cửa sổ trượt 100 frames; ngưỡng phân cảnh $\ge 0.5$; độ nét Laplacian $\ge 70.0$; dHash Hamming $\le 5$ | ~1.2 GB VRAM / ~1.5 GB RAM | `data-keyframes/*.webp`, `maps/*_map.csv` |
| **2. Âm thanh (ASR)** | `extract_asr_advanced.py` | `Faster-Whisper large-v3-turbo` | CTranslate2 backend, FP16, Silero VAD lọc khoảng lặng; ngưỡng lọc `no_speech_prob > 0.65` | ~2.5 GB VRAM / ~2.0 GB RAM | `asr_results.jsonl` |
| **3. Thị giác chữ (OCR)** | `extract_ocr_qwen_vl.py` | `Qwen2-VL-2B-Instruct` | 2.2 tỷ tham số, FP16, SDPA attention, độ phân giải $256 \times 28 \times 28$ đến Native Full HD ($1920 \times 1080$), `max_new_tokens=128` | ~4.4 GB VRAM / ~3.0 GB RAM | `ocr_results.jsonl` |
| **4. Gộp Metadata** | `merge_ocr_asr_metadata.py` | Tìm kiếm nhị phân `bisect` | Ánh xạ timestamp giây/mili-giây từ `_map.csv` với khoảng thời gian `start`–`end` của ASR, gộp với OCR | ~0 MB VRAM / ~800 MB RAM | `ocr_asr_metadata.json` |
| **5. Vector hóa ảnh** | `extract_features.py` | `Google SigLIP 2 Giant` (`ViT-gopt-16-SigLIP2-384`, `webli`) | 1152 chiều, FP16, ảnh đầu vào $384 \times 384$, chuẩn hóa L2, batch size 24 | ~4.2 GB VRAM / ~3.5 GB RAM | `features.npy` ($N \times 1152$), `image_paths.npy` ($N$) |
| **6. Lập chỉ mục** | `build_faiss_index.py` | `FAISS IndexIVFScalarQuantizer` (IVF-SQ8) | Lượng tử hóa 8-bit SQ8, độ đo khoảng cách tích vô hướng (Inner Product / Cosine), số cụm $nlist = 4 \times \sqrt{N}$ | 0 MB VRAM / ~300 MB RAM | `features.faiss` |

---

## 3. Quy trình thực thi 6 bước tuần tự qua giao diện dòng lệnh (CLI)

Chạy từng lệnh tuần tự từ thư mục gốc của dự án (`D:\code-c-a-Long`):

```bash
conda activate video_ai
cd /d D:\code-c-a-Long
```

### Bước 1: Trích xuất khung hình chính (Keyframes)
Cắt video thành các cảnh theo ranh giới shot, tự động chọn frame nét nhất trong lân cận $\pm 3$ frame và xuất ảnh nén WebP:
```bash
python data_pipeline/transnetv2_keyframes.py --input-folder "D:/code-c-a-Long/data-video" --output-base "D:/code-c-a-Long/data-keyframes" --workers 13
```

### Bước 2: Bóc băng lời thoại ASR
Nhận diện giọng nói tiếng Việt bằng Faster-Whisper và gán mốc thời gian:
```bash
python data_pipeline/extract_asr_advanced.py --video-dir "D:/code-c-a-Long/data-video"
```

### Bước 3: Nhận diện văn bản thị giác OCR
Nhận diện chữ viết, biển hiệu và phụ đề trên khung hình bằng mô hình Qwen2-VL:
```bash
python data_pipeline/extract_ocr_qwen_vl.py --keyframes-dir "D:/code-c-a-Long/data-keyframes"
```

### Bước 4: Khớp mốc thời gian và gộp siêu dữ liệu
Ánh xạ mốc thời gian giữa keyframe và lời thoại ASR, đồng bộ hóa với dữ liệu OCR:
```bash
python data_pipeline/merge_ocr_asr_metadata.py
```

### Bước 5: Trích xuất vector đặc trưng hình ảnh
Mã hóa toàn bộ keyframe thành mảng vector 1152 chiều bằng SigLIP 2:
```bash
python data_pipeline/extract_features.py --keyframes-dir "D:/code-c-a-Long/data-keyframes" --batch-size 24 --workers 12
```

### Bước 6: Xây dựng chỉ mục không gian vector FAISS
Huấn luyện và lập chỉ mục lượng tử hóa IVF-SQ8 cho mảng `features.npy`:
```bash
python data_pipeline/build_faiss_index.py --features-path "D:/code-c-a-Long/features.npy" --output-path "D:/code-c-a-Long/features.faiss"
```

---

## 4. Công cụ kiểm thử và tối ưu tham số

### Đánh giá độ chính xác truy xuất (Benchmark Evaluation)
Tính toán các chỉ số kỹ thuật gồm Recall@1, Recall@5, Recall@10, Mean Reciprocal Rank (MRR) và độ trễ phân vị P50/P95:
```bash
python data_pipeline/benchmark_eval.py --queries data_pipeline/validation_queries.json --top-k 10 --server http://localhost:8000
```

### Tối ưu hóa trọng số RRF (Grid Search RRF Weights)
Tìm kiếm lưới giá trị tham số tối ưu cho bộ ba trọng số ($w_{visual}, w_{ocr}, w_{asr}$) theo công thức $RRF(d) = \sum_{m} \frac{w_m}{60 + r_m(d)}$:
```bash
python data_pipeline/tune_rrf_weights.py --queries data_pipeline/validation_queries.json --top-k 10 --server http://localhost:8000
```


### Đóng gói bài thi (Submission Validator & Packer)
Kiểm tra tính hợp lệ định dạng CSV của 3 dạng bài thi (KIS, Q&A, TRAKE) và nén thành file `submission.zip`:
```bash
python data_pipeline/pack_submission.py --project-root "D:/code-c-a-Long" --zip-name "submission.zip"
```
