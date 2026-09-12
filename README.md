# Hệ Thống Tìm Kiếm Video Đa Phương Thức (Video Retrieval)

Hệ thống phục vụ tìm kiếm khoảnh khắc trong video bằng văn bản mô tả, lời thoại và chữ viết trên màn hình, chạy trực tiếp trên máy cục bộ (Windows 11, AMD 7000 Series 16 luồng, 16GB RAM, GPU NVIDIA RTX 3050 6GB VRAM).

---

## 1. Kiến trúc hệ thống và mô hình

| Thành phần | Mô hình / Công nghệ | Vai trò & Thông số |
| :--- | :--- | :--- |
| **Vector hình ảnh** | `Google SigLIP 2 Giant` (`ViT-gopt-16-SigLIP2-384`, `webli`) | Trích xuất vector 1152 chiều (FP16). Tìm kiếm qua chỉ mục FAISS IVF-SQ8 và ma trận GPU CUDA. |
| **Phân tích câu hỏi** | `SmartQueryDecomposer` | Tách từ khóa OCR, ASR, phân tích chuỗi thời gian cho bài TRAKE, dịch tự động Việt - Anh. |
| **Bóc băng lời nói (ASR)** | `Faster-Whisper Large-v3-Turbo` | Chuyển giọng nói thành văn bản, dùng Silero VAD lọc im lặng, khớp timestamp vào keyframe. |
| **Đọc chữ màn hình (OCR)** | `Qwen2-VL-2B-Instruct` | Nhận diện chữ, biển hiệu, biển số xe trực tiếp trên ảnh độ phân giải cao; lọc watermark. |
| **Trích xuất khung hình** | `TransNetV2` | Cắt cảnh, lấy mẫu thích ứng, lọc ảnh mờ (Laplacian $\ge 70.0$) và ảnh trùng lặp (dHash). |
| **Hợp nhất kết quả** | `Reciprocal Rank Fusion (RRF)` | Dung hợp thứ hạng từ vector hình ảnh và điểm BM25 văn bản (OCR/ASR). |

---

## 2. Cấu trúc thư mục dự án

```
D:\code-c-a-Long/
├── backend/                    # Máy chủ FastAPI (REST API & WebSocket /ws)
│   ├── main.py                 # Core server, WebSocket, FAISS search, RRF Fusion
│   ├── smart_query_decomposer.py # Phân tích câu truy vấn, dịch thuật, tách TRAKE
│   ├── config.json             # Cấu hình hệ thống (ngưỡng điểm, đường dẫn, tham số)
│   ├── requirements.txt        # Danh sách thư viện Python
│   └── README.md               # Tài liệu chi tiết backend
├── frontend/                   # Giao diện web người dùng (HTML5, CSS, Vanilla JS)
│   ├── index.html              # Trang tìm kiếm chính và khay nộp bài
│   ├── login.html              # Trang cấu hình phiên kết nối DRES
│   ├── scripts/                # Mã nguồn JavaScript điều khiển giao diện
│   ├── styles/                 # Bảng định kiểu CSS
│   └── README.md               # Tài liệu chi tiết frontend
├── data_pipeline/              # Quy trình xử lý video ngoại tuyến
│   ├── transnetv2_keyframes.py        # 1. Trích xuất keyframe theo shot (TransNetV2)
│   ├── extract_asr_advanced.py        # 2. Bóc băng âm thanh (Faster-Whisper large-v3-turbo)
│   ├── extract_ocr_qwen_vl.py         # 3. Đọc chữ hình ảnh (Qwen2-VL-2B-Instruct)
│   ├── merge_ocr_asr_metadata.py      # 4. Gộp mốc thời gian vào ocr_asr_metadata.json
│   ├── extract_features.py            # 5. Trích xuất vector SigLIP 2 Giant (1152d FP16)
│   ├── build_faiss_index.py           # 6. Lập chỉ mục FAISS IVF-SQ8
│   ├── pack_submission.py             # Đóng gói và kiểm tra file submission.zip
│   ├── benchmark_eval.py              # Đánh giá độ chính xác (Recall, MRR)
│   ├── tune_rrf_weights.py            # Tối ưu bộ trọng số RRF
│   └── README.md                      # Hướng dẫn chi tiết data_pipeline
├── data-keyframes/             # Thư mục chứa keyframes (.webp) và maps CSV
├── features.faiss              # Chỉ mục không gian vector FAISS IVF-SQ8
├── features.npy                # Ma trận vector đặc trưng SigLIP (N x 1152, FP16)
├── image_paths.npy             # Danh sách đường dẫn tương ứng với từng vector
├── ocr_results.jsonl           # Dữ liệu văn bản OCR trích xuất từ keyframe
├── asr_results.jsonl           # Dữ liệu lời thoại ASR trích xuất từ audio
└── README.md                   # Tài liệu tổng quan dự án
```

---

## 3. Cấu hình phần cứng tối ưu

Hệ thống được thiết lập vận hành ở mức 80%–90% công suất phần cứng:
- **CPU**: AMD 7000 Series (16 luồng) $\to$ phân bổ 13–14 luồng tính toán song song (`torch`, `OpenMP`, `OpenCV`).
- **GPU / VRAM**: NVIDIA RTX 3050 6GB $\to$ định dạng FP16, Tensor Core TF32, giới hạn trần 88% (~5.1–5.3 GB VRAM).
- **RAM**: 16 GB $\to$ bộ nhớ đệm kết quả, chỉ mục BM25 trên RAM và streaming I/O.

---

## 4. Hướng dẫn sử dụng

### Khởi động môi trường
```bash
conda activate video_ai
cd /d D:\code-c-a-Long
```

### Xử lý dữ liệu video mới (Thực thi trực tiếp từng bước)
```bash
# Bước 1: Trích xuất keyframes
python data_pipeline/transnetv2_keyframes.py --input-folder "D:/code-c-a-Long/data-video" --output-base "D:/code-c-a-Long/data-keyframes" --workers 13

# Bước 2: Bóc băng âm thanh ASR
python data_pipeline/extract_asr_advanced.py --video-dir "D:/code-c-a-Long/data-video"

# Bước 3: Đọc chữ màn hình OCR
python data_pipeline/extract_ocr_qwen_vl.py --keyframes-dir "D:/code-c-a-Long/data-keyframes"

# Bước 4: Khớp mốc thời gian và gộp siêu dữ liệu
python data_pipeline/merge_ocr_asr_metadata.py

# Bước 5: Trích xuất vector đặc trưng SigLIP 2
python data_pipeline/extract_features.py --keyframes-dir "D:/code-c-a-Long/data-keyframes" --batch-size 24 --workers 12

# Bước 6: Lập chỉ mục vector FAISS IVF-SQ8
python data_pipeline/build_faiss_index.py --features-path "D:/code-c-a-Long/features.npy" --output-path "D:/code-c-a-Long/features.faiss"
```

### Khởi động máy chủ tìm kiếm
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Truy cập giao diện tại: **`http://localhost:8000/frontend/`**

---

## 5. Phím tắt thao tác nhanh

| Phím tắt | Thao tác | Mô tả |
| :--- | :--- | :--- |
| **`Enter`** | Tìm kiếm | Gửi câu truy vấn ở ô tìm kiếm hiện tại |
| **`Chuột giữa`** / **`[+]`** | Chọn ảnh | Thêm keyframe đang trỏ vào khay nộp bài |
| **`Alt + A`** | Bật/tắt khay | Ẩn hoặc hiện thanh khay nộp bài |
| **`Alt + R`** | Rocchio | Tinh chỉnh vector tìm kiếm theo ảnh đã chọn |
| **`Alt + S`** | Lưu kết quả | Lưu câu truy vấn vào danh sách bài thi |
| **`Ctrl + S`** / **`Alt + P`** | Đóng gói | Kiểm tra định dạng và tạo file `submission.zip` |
| **`Ctrl + Q`** | Xóa nhanh | Xóa nội dung ô tìm kiếm |
| **`Ctrl + I`** | Tab OCR | Chuyển nhanh sang tìm kiếm chữ viết màn hình |
| **`Ctrl + K`** | Tab ASR | Chuyển nhanh sang tìm kiếm lời thoại |
| **`Alt + C`** | Dọn khay | Xóa toàn bộ ảnh đang chọn trong khay |
| **`Esc`** | Đóng popup | Đóng video player hoặc hộp thoại đang mở |
