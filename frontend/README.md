# Retrieval System Frontend 🌐

Giao diện web trực quan của hệ thống Video Retrieval System (AIC), được xây dựng bằng **HTML5, CSS3 Vanilla và JavaScript Async/WebSocket**.

Tối ưu hóa cho môi trường: **Windows 11 (Google Chrome / Microsoft Edge / Brave)**.

---

## ✨ Tính năng chính

- **Tìm kiếm Ngữ nghĩa Đa phương thức**: Nhập mô tả tiếng Việt / tiếng Anh để tìm kiếm khoảnh khắc video trong $< 0.05\text{s}$.
- **Giao diện Tối giản & Tinh gọn (Compact UI)**: Bố cục thanh mảnh, ô nhập tối ưu không gian hiển thị, loại bỏ các chi tiết thừa thãi.
- **Hỗ trợ Chữ viết (OCR) & Lời thoại (ASR)**: Nhấn `Ctrl + I` để tìm chữ trên ảnh và `Ctrl + K` để tìm lời thoại.
- **Duyệt Khung Hình Lân Cận (Neighbor Scrubbing)**: Click vào ảnh để xem các frame trước/sau (từ $-5$ đến $+5$ frame) theo mốc giây thực tế.
- **Hỏi Đáp AI Trực Tiếp Trên Video Player (Visual Q&A)**: Xem video trực tiếp và nhận câu trả lời tức thì từ mô hình phân tích ngữ cảnh.
- **Rocchio Relevance Feedback (`Alt + R`)**: Chọn các keyframe đúng rồi nhấn `Alt + R` để AI tính toán lại vector trọng tâm, gom toàn bộ khoảnh khắc liên quan lên đầu.
- **Khay Nộp Thông Minh (Smart Frame Limit Guard)**: Cảnh báo màu sắc và kiểm soát số lượng frame cho KIS để tối đa hóa điểm số (MRR).
- **Trình Quản Lý Gói Bài Thi & Nén ZIP (`Ctrl + S` / `Alt + P`)**:
  - Hỗ trợ đầy đủ KIS, Visual Q&A (gán đáp án tự động) và TRAKE (quản lý đa phương án PA 1, PA 2... sắp xếp thời gian tăng dần).
  - Tự động đóng gói và nén file `submission.zip` chuẩn 100% BTC chỉ với 1 cú click.

---

## ⚡ Hướng Dẫn Khởi Chạy

### Cách 1: Sử dụng trực tiếp từ FastAPI Backend (Khuyên dùng)
Khi Backend khởi động, frontend đã được mount sẵn tại:
👉 **`http://localhost:8000/frontend/`**

### Cách 2: Sử dụng Extension "Live Server" trong VS Code
1. Mở thư mục dự án bằng **VS Code**.
2. Nhấp chuột phải vào file [frontend/index.html](file:///D:/code-c-a-Long/frontend/index.html) và chọn **Open with Live Server**.
3. Trình duyệt sẽ mở giao diện tại `http://127.0.0.1:5500`.

---

## ⌨️ Bảng Phím Tắt Nhanh
- **`Enter`**: Tìm kiếm câu query.
- **`Chuột giữa`** hoặc **`[+]`**: Chọn ảnh vào Khay Nộp bài.
- **`Alt + A`**: Bật/tắt Khay Nộp kết quả.
- **`Alt + R`**: ✨ Tinh chỉnh tìm kiếm (Refine Search).
- **`Alt + S`**: 💾 Lưu câu truy vấn vào Gói Bài Thi.
- **`Ctrl + S`** hoặc **`Alt + P`**: Mở Bảng Quản Lý Gói Bài Thi & Nén `submission.zip`.
- **`Ctrl + Q`**: Xóa nhanh câu query để gõ câu mới.
- **`Ctrl + I`**: Mở ô tìm kiếm OCR.
- **`Ctrl + K`**: Mở ô tìm kiếm ASR.
- **`Alt + C`** hoặc **`Alt + X`**: Xóa sạch ảnh trong khay.
- **`Esc`**: Đóng trình phát video hoặc modal xem trước.

Xem hướng dẫn chi tiết tại **[HUONG_DAN.md](file:///D:/code-c-a-Long/HUONG_DAN.md)**.