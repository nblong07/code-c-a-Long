# 📖 HƯỚNG DẪN CHI TIẾT DỰ ÁN VIDEO RETRIEVAL SYSTEM
## Code-c-a-Long — Tối Ưu Cho Windows 11 (RAM 16GB + NVIDIA 6GB GPU)

> **Công nghệ sử dụng:** PyTorch (CUDA GPU), OpenCLIP (`ViT-SO400M-14-SigLIP-384`), Milvus Vector Database (Docker), FastAPI, WebSocket, PaddleOCR (v4), Faster-Whisper (Large-v3).

---

## 📌 MỤC LỤC
1. [Thông Số Máy & Tối Ưu Hệ Thống](#1-thông-số-máy--tối-ưu-hệ-thống)
2. [Cấu Trúc Luồng Dữ Liệu](#2-cấu-trúc-luồng-dữ-liệu)
3. [Cài Đặt Môi Trường (Miniconda Python 3.11)](#3-cài-đặt-môi-trường-miniconda-python-311)
4. [Khởi Động Milvus Vector Database (Docker)](#4-khởi-động-milvus-vector-database-docker)
5. [Bước 1: Trích Xuất Keyframe Từ Video (`get_keyframes.py`)](#5-bước-1-trích-xuất-keyframe-từ-video-get_keyframespy)
6. [Bước 2: Mã Hóa & Upload Vector Vào Milvus (`upload_database.py`)](#6-bước-2-mã-hóa--upload-vector-vào-milvus-upload_databasepy)
7. [Bước 3: Chạy Backend Service (`backend/main.py`)](#7-bước-3-chạy-backend-service-backendmainpy)
8. [Bước 4: Mở Frontend Tương Tác (`frontend/index.html`)](#8-bước-4-mở-frontend-tương-tác-frontendindexhtml)
9. [Công Cụ Phụ Trợ (FAISS Offline & DRES Submit)](#9-công-cụ-phụ-trợ-faiss-offline--dres-submit)
10. [Xử Lý Lỗi Thường Gặp (Troubleshooting)](#10-xử-lý-lỗi-thường-gặp-troubleshooting)

---

## 1. THÔNG SỐ MÁY & TỐI ƯU HỆ THỐNG

Dự án đã được chuyên gia tinh chỉnh lại toàn bộ mã nguồn để chạy tối ưu nhất trên máy của bạn:

| Thành phần | Cấu hình máy của bạn | Tối ưu hóa được áp dụng trong mã nguồn |
| :--- | :--- | :--- |
| **OS** | Windows 11 | Đường dẫn an toàn (Pathlib), tránh lỗi Windows Process Spawn. |
| **RAM** | 16 GB | Batch size & HNSW Index (`M=16, efConstruction=200`) giữ bộ nhớ RAM cực nhẹ. |
| **GPU** | NVIDIA 6 GB VRAM | Sử dụng mô hình State-of-the-Art **OpenCLIP `ViT-SO400M-14-SigLIP-384`** (Google) kết hợp **PyTorch FP16 Autocast**, đạt độ chính xác ngữ nghĩa cao nhất thế giới và **không bị tràn VRAM (OOM)**. |
| **Python** | 3.11 (Miniconda) | Tương thích hoàn hảo PyTorch CUDA 11.8/12.1 + open_clip_torch + pymilvus. |

---

## 2. CẤU TRÚC LUỒNG DỮ LIỆU

```
 Video MP4 (.mp4)
       │
       ▼  [BƯỚC 1] get_keyframes.py
       │  (Đọc video bằng OpenCV + OpenCLIP SigLIP SO400M FP16 trên CUDA GPU,
       │   lọc khung hình chuyển cảnh khi Cosine Similarity < 0.93)
 Keyframe WebP (.webp) + File CSV Mapping (frame_id → giây)
       │
       ▼  [BƯỚC 2] upload_database.py
       │  (Mã hóa toàn bộ ảnh → Chuẩn hóa Vector 768d → Upload & tạo HNSW Index trên Milvus)
 Milvus Vector Collection (AIC25_fullbatch1)
       │
       ▼  [BƯỚC 3] backend/main.py (FastAPI + WebSocket trên CUDA GPU)
       │  (Nhận câu tìm kiếm từ người dùng → Encode CLIP Text → Tìm COSINE Top 3000)
 REST API / WebSocket (Port 8000)
       │
       ▼  [BƯỚC 4] frontend/index.html
 Giao diện người dùng: Nhập câu truy vấn → Xem keyframe → Lọc thời gian → Export / Submit DRES
```

---

## 3. CÀI ĐẶT MÔI TRƯỜNG (MINICONDA PYTHON 3.11)

Mở **Anaconda Prompt** hoặc **Terminal (Miniconda)** trên Windows 11:

### 3.1 Kích hoạt môi trường Miniconda
```cmd
# Kích hoạt môi trường Python 3.11 của bạn
conda activate base
# (Hoặc tên môi trường ảo của bạn, ví dụ: conda activate py311)
```

### 3.2 Kiểm tra GPU CUDA PyTorch
```cmd
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```
> Kết quả cần hiển thị `CUDA available: True` và tên GPU NVIDIA của bạn.

### 3.3 Cài đặt gói thư viện phụ thuộc
Chạy lệnh sau để cài đặt môi trường (thay vì dùng script tự động):
```cmd
cd /d D:\code-c-a-Long
pip install -r backend/requirements.txt
```

---

## 4. KHỞI ĐỘNG MILVUS VECTOR DATABASE (DOCKER)

Milvus là cơ sở dữ liệu siêu tốc dùng để lưu trữ và tìm kiếm vector.

1. Bật ứng dụng **Docker Desktop** trên Windows 11.
2. Trong Terminal, di chuyển vào thư mục `database` và khởi động container:
```cmd
cd /d D:\code-c-a-Long\database
docker compose up -d
```
3. Kiểm tra trạng thái Milvus:
```cmd
docker compose ps
```
> Tất cả các container (`milvus-standalone`, `milvus-etcd`, `milvus-minio`) phải hiển thị trạng thái `running` hoặc `healthy`.

---

## 5. BƯỚC 1: TRÍCH XUẤT KEYFRAME TỪ VIDEO (`get_keyframes.py`)

File [get_keyframes.py](file:///D:/code-c-a-Long/database/get_keyframes.py) giúp tự động trích xuất các ảnh đại diện (keyframe) khi nội dung video có sự thay đổi cảnh.

### Lệnh thực thi (chạy trên GPU CUDA):
```cmd
cd /d D:\code-c-a-Long

python database/get_keyframes.py ^
  --input-folder "D:/path/to/your/videos" ^
  --output-base "./data-keyframes" ^
  --clip-threshold 0.93 ^
  --skip-frames 5 ^
  --batch-size 64 ^
  --model "ViT-SO400M-14-SigLIP-384" ^
  --pretrained "webli"
```

### Giải thích các tham số tối ưu:
* `--input-folder`: Thư mục chứa các file video `.mp4`.
* `--output-base`: Thư mục lưu ảnh keyframe xuất ra (`./data-keyframes`).
* `--clip-threshold 0.93`: Ngưỡng nhận biết đổi cảnh (Cosine similarity < 0.93 sẽ lưu keyframe mới).
* `--skip-frames 5`: Đọc mỗi 6 frame (bỏ qua 5 frame) để tăng tốc độ gấp 6 lần.
* `--batch-size 64`: Kích thước batch encode trên GPU 6GB VRAM.

---

## 6. BƯỚC 2: MÃ HÓA & UPLOAD VECTOR VÀO MILVUS (`upload_database.py`)

File [upload_database.py](file:///D:/code-c-a-Long/database/upload_database.py) đọc các file ảnh WebP đã trích xuất, tạo vector đặc trưng 768 chiều, chuẩn hóa vector và tải lên Milvus.

### Lệnh thực thi:
```cmd
cd /d D:\code-c-a-Long

python database/upload_database.py ^
  --root "./data-keyframes" ^
  --collection-name "AIC25_fullbatch1" ^
  --host "localhost" ^
  --port "19530" ^
  --batch-size 32 ^
  --model "ViT-SO400M-14-SigLIP-384" ^
  --pretrained "webli" ^
  --build-index
```

### Các điểm cải tiến quan trọng:
1. **Chuẩn hóa Vector (`F.normalize`):** Đảm bảo các vector đặc trưng có độ dài đơn vị (unit-length), giúp thuật toán tính khoảng cách Cosine trên Milvus chính xác 100%.
2. **Tự động đóng Index (`--build-index`):** Tạo chỉ mục HNSW tối ưu cho bộ nhớ RAM 16GB và nạp dữ liệu sẵn sàng phục vụ tìm kiếm.

---

## 7. BƯỚC 3: CHẠY BACKEND SERVICE (`backend/main.py`)

Backend được viết bằng FastAPI kết hợp WebSocket, load mô hình CLIP trực tiếp vào GPU NVIDIA.

### Lệnh khởi động Backend:
```cmd
cd /d D:\code-c-a-Long

python backend/main.py
```
Hoặc dùng uvicorn:
```cmd
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Trạng thái Backend khi khởi động thành công:
* Hiển thị log: `⚡ Running service on device: cuda`
* Hiển thị GPU: `GPU Name: NVIDIA GeForce ... | VRAM Total: ~6.00 GB`
* Milvus status: `Milvus Collection 'AIC25_fullbatch1' loaded successfully.`
* Swagger UI: Truy cập kiểm tra API tại `http://localhost:8000/docs` hoặc `http://localhost:8000/health`.

---

## 8. BƯỚC 4: MỞ FRONTEND TƯƠNG TÁC (`frontend/index.html`)

1. Mở file [frontend/index.html](file:///D:/code-c-a-Long/frontend/index.html) bằng trình duyệt (Google Chrome / Microsoft Edge).
2. Nhập câu truy vấn tiếng Anh (ví dụ: `a man walking a red car on street at night`).
3. Giao diện sẽ hiển thị ngay lập tức các keyframe phù hợp nhất được xếp hạng theo điểm tương đồng.

---

## 9. CÔNG CỤ PHỤ TRỢ (FAISS OFFLINE & TRÍCH XUẤT ĐẶC TRƯNG)

### 9.1 Trích xuất đặc trưng đa phương thức (`extract_features.py`)
Sử dụng file đã được gộp chung để trích xuất cả CLIP features, OCR và ASR:
```cmd
python extract_features.py
```
(Sau đó chọn tuỳ chọn 1, 2, hoặc 3 để trích xuất loại dữ liệu mong muốn)

### 9.2 Tạo chỉ mục FAISS offline (`build_index.py`)
```cmd
python build_index.py --features "features.npy" --output "faiss_index.bin"
```

*(Lưu ý: Các script gửi kết quả DRES tự động đã được xóa bỏ để giữ source code tập trung vào công cụ tìm kiếm chuẩn. Bạn có thể sử dụng UI hoặc viết script ngoài nếu cần nộp bài).*

---

## 10. XỬ LÝ LỖI THƯỜNG GẶP (TROUBLESHOOTING)

| Lỗi | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| **CUDA Out of Memory (OOM)** | Dùng model quá lớn (`ViT-H-14`) hoặc batch_size quá cao. | Code hiện tại đã mặc định `ViT-SO400M-14-SigLIP-384` với batch_size 32/64, hoạt động mượt mà với FP16 Autocast trên GPU 6GB của bạn. |
| **Milvus Connection Failed** | Chưa bật Docker Desktop hoặc chưa `docker compose up -d`. | Kiểm tra `docker ps` và bật Docker Desktop trước khi chạy script. |
| **Dimension Mismatch** | Upload vector bằng model này nhưng backend search bằng model khác. | Đã đồng bộ tất cả file dùng model mặc định `ViT-SO400M-14-SigLIP-384` (tự động nhận diện số chiều). Nếu làm lại, dùng cờ `--recreate` khi upload. |
| **Lỗi Windows Process Spawn** | Đa tiến trình `multiprocessing` trên Windows. | Code `upload_database.py` đã được cập nhật luồng xử lý đơn GPU tăng tốc bằng CUDA stream không cần spawn sub-process. |

---
*Chúc bạn thực hiện cuộc thi AI City Challenge đạt kết quả cao nhất!* 🚀
