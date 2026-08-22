# Vector Search Service Backend 🚀

FastAPI backend service cho hệ thống tìm kiếm video retrieval hiệu năng cao, tích hợp mô hình Google OpenCLIP `ViT-gopt-16-SigLIP2-384` (**Google SigLIP 2 Giant 1152d**) và bộ tìm kiếm ma trận GPU CUDA.

Tối ưu hóa cho môi trường: **Windows 11, RAM 16GB, GPU NVIDIA RTX 3050 6GB VRAM (PyTorch CUDA)**.

## ✨ Tính năng chính

- **Google OpenCLIP `ViT-gopt-16-SigLIP2-384` (`webli`)**: Trích xuất embedding 1152 chiều chất lượng cao SOTA từ mô hình Google SigLIP 2 Giant ~1 tỷ tham số.
- **Direct GPU CUDA Tensor Matrix Search**: Tìm kiếm cosine similarity trên 166,628 vector trong $< 2\text{ms}$.
- **Khởi động nóng (Warm-up Engine)**: Tải sẵn cuBLAS, tokenizer, và dịch song ngữ — loại bỏ hoàn toàn độ trễ khởi động lạnh.
- **Phục vụ Keyframe Tốc độ O(1) RAM Index**: Bảng băm bộ nhớ RAM phục vụ ảnh siêu tốc qua endpoint `/keyframes/`.
- **Cross-Lingual Dual-Embedding Blending**: Tự động nhận diện tiếng Việt và dung hợp song ngữ (`0.45 * vi + 0.55 * en`) với bộ từ điển đồng nghĩa chuyên sâu.
- **BM25 Inverted Index Engine**: Tìm kiếm OCR (158,193 bản ghi) và ASR (144,429 bản ghi) trên RAM CPU với độ trễ $< 2\text{ms}$ và **0 MB VRAM**.
- **TRAKE Temporal Query Logic**: Quy hoạch động chuỗi thời gian GPU Tensor Dynamic Programming.
- **Rocchio Relevance Feedback**: Phản hồi tương tác tinh chỉnh vector tìm kiếm theo các keyframe đã chọn (`Alt + R`).
- **Batch Submission Package Manager**: Quản lý gói nộp bài và tự động nén `submission.zip` chuẩn 100% BTC (`Ctrl + S` / `Alt + P`).
- **Real-time WebSocket & REST API**: Hỗ trợ endpoint `/TextQuery`, WebSocket `/ws`, `/ws/filter_query`.

## 🛠️ Cài đặt & Khởi chạy

### 1. Kích hoạt môi trường Conda

```bash
conda activate video_ai
cd /d D:\code-c-a-Long
```

### 2. Khởi chạy Server

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Server sẽ lắng nghe tại: `http://localhost:8000`
- Swagger UI Docs: `http://localhost:8000/docs`
- Web Frontend: `http://localhost:8000/frontend/`

## 📡 Các API chính

| Endpoint | Phương thức | Mô tả |
| --- | --- | --- |
| `/health` | `GET` | Kiểm tra trạng thái hệ thống, GPU CUDA, số lượng vector & metadata |
| `/keyframes/{path}` | `GET` | Phục vụ file ảnh keyframe tức thì qua RAM lookup O(1) |
| `/TextQuery` | `POST` | Truy vấn Text-to-Video qua REST API |
| `/ws` | `WebSocket` | Kết nối tìm kiếm và tinh chỉnh thời gian thực |
| `/ws/filter_query` | `WebSocket` | Kết nối lọc kết quả theo OCR / ASR |
| `/api/submission/pack` | `POST` | Đóng gói và nén file `submission.zip` |
| `/api/submission/status` | `GET` | Kiểm tra trạng thái thư mục bài thi |
| `/api/submission/clear` | `POST` | Làm sạch toàn bộ thư mục bài thi |

Xem hướng dẫn sử dụng toàn bộ hệ thống tại **[HUONG_DAN.md](file:///D:/code-c-a-Long/HUONG_DAN.md)**.

