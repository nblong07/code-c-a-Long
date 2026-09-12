# Dịch Vụ Tìm Kiếm Backend (Backend Search Service)

Thư mục này chứa mã nguồn máy chủ FastAPI phục vụ việc tìm kiếm khoảnh khắc video, kết hợp tìm kiếm vector thị giác trên GPU và tìm kiếm từ khóa trên RAM CPU qua giao thức REST API và WebSocket.

Môi trường kiểm thử chuẩn: **Windows 11, RAM 16 GB, GPU NVIDIA GeForce RTX 3050 Laptop (6 GB VRAM)**.

---

## 1. Các chức năng chính

* **Tìm kiếm theo ảnh (Dense Vector Search):**
  * Sử dụng Text Encoder của mô hình `Google SigLIP 2 Giant` (`ViT-gopt-16-SigLIP2-384`) để chuyển câu mô tả thành vector 1152 chiều (định dạng FP16).
  * Nạp sẵn toàn bộ vector đặc trưng của các keyframe lên GPU. Phép nhân ma trận cosine similarity qua `torch.mm` thực thi dưới **2 mili-giây** cho hơn 160.000 khung hình.
* **Phân tích câu hỏi tự động (`SmartQueryDecomposer`):**
  * Chạy trên CPU, xử lý dưới **1 mili-giây**, không dùng VRAM.
  * Tự động trích xuất các từ trong dấu ngoặc kép `"..."` để tìm theo OCR (chữ trên màn hình).
  * Nhận diện các từ khóa chỉ hội thoại (ví dụ: *nói rằng, bảo là, MC giới thiệu*) để tìm theo ASR (lời nói).
  * Tự động tách các giai đoạn thời gian (Stage 1, Stage 2...) đối với dạng bài TRAKE.
  * Hỗ trợ bộ từ điển song ngữ Việt - Anh kết hợp dịch tự động để làm giàu câu truy vấn.
* **Tìm kiếm theo chữ viết & lời nói (BM25 Lexical Search):**
  * Đánh chỉ mục đảo (Inverted Index) và tính điểm BM25 trực tiếp trên bộ nhớ RAM cho tập dữ liệu văn bản (172.937 bản ghi OCR và 154.026 bản ghi ASR), thời gian phản hồi dưới **1 mili-giây**.
* **Dung hợp kết quả (Reciprocal Rank Fusion - RRF):**
  * Kết hợp thứ hạng từ kết quả tìm theo ảnh và kết quả tìm theo từ khóa văn bản. Tự động tăng trọng số cho kênh OCR hoặc ASR khi câu truy vấn có chứa từ khóa tương ứng.
* **Hỗ trợ tinh chỉnh kết quả (Rocchio Relevance Feedback):**
  * Khi người dùng chọn các khung hình chính xác trên giao diện và bấm `Alt + R`, hệ thống tính toán lại vector trọng tâm dựa trên các ảnh đã chọn để đưa thêm các góc quay tương tự lên đầu danh sách.
* **Quản lý gói bài thi & nén kết quả:**
  * Cung cấp các API kiểm tra tính hợp lệ và đóng gói các file `.csv` của ba dạng bài (KIS, Q&A, TRAKE) thành file `submission.zip` để nộp cho ban tổ chức.

---

## 2. Hướng dẫn khởi chạy

### Bước 1: Kích hoạt môi trường
```bash
conda activate video_ai
cd /d D:\code-c-a-Long
```

### Bước 2: Khởi động máy chủ
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Khi khởi động thành công:
* Địa chỉ server: `http://localhost:8000`
* Tài liệu API (Swagger UI): `http://localhost:8000/docs`
* Giao diện người dùng: `http://localhost:8000/frontend/`

---

## 3. Mức tiêu thụ tài nguyên thực tế

| Tài nguyên | Khi vừa khởi động server | Trong lúc xử lý truy vấn | Ghi chú |
| :--- | :--- | :--- | :--- |
| **RAM hệ thống** | ~2.2 GB | ~2.5 – 2.8 GB | Chứa chỉ mục BM25 và từ điển keyframe |
| **VRAM card đồ họa** | ~3.0 GB | ~3.2 – 3.5 GB | Nạp mô hình SigLIP Text Encoder và ma trận vector |
| **Độ trễ truy vấn** | — | 30 – 50 mili-giây / câu | Bao gồm: phân tích câu, sinh vector và tính điểm RRF |

---

## 4. Danh sách các API chính

| Đường dẫn (Endpoint) | Giao thức | Chức năng |
| :--- | :--- | :--- |
| `/health` | `GET` | Kiểm tra trạng thái server, tình trạng GPU CUDA, số lượng vector và dữ liệu văn bản |
| `/keyframes/{path}` | `GET` | Trả về file ảnh keyframe từ đường dẫn tương đối qua bộ nhớ đệm |
| `/TextQuery` | `POST` | Gửi câu truy vấn văn bản và nhận về danh sách keyframe phù hợp nhất (REST) |
| `/api/v2/decompose_query` | `POST` | Phân tích câu hỏi thành các thành phần: mô tả hình ảnh, từ khóa OCR, ASR và giai đoạn |
| `/ws` | `WebSocket` | Kết nối thời gian thực phục vụ tìm kiếm, phân trang và tinh chỉnh kết quả (Rocchio) |
| `/ws/filter_query` | `WebSocket` | Lọc kết quả tìm kiếm chuyên sâu theo OCR hoặc ASR |
| `/ws/similarity_search` | `WebSocket` | Tìm kiếm các khung hình tương tự dựa trên vector của một ảnh được chọn |
| `/api/submission/pack` | `POST` | Kiểm tra định dạng các file trong thư mục `submission/` và nén thành `submission.zip` |
| `/api/submission/status` | `GET` | Xem số lượng câu hỏi đã hoàn thành của từng dạng bài (KIS, Q&A, TRAKE) |
| `/api/submission/clear` | `POST` | Xóa sạch các file bài thi cũ trong thư mục `submission/` để chuẩn bị cho lượt thi mới |
