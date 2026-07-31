# Retrieval System Frontend 🌐

Giao diện web trực quan của hệ thống Video Retrieval System (AIC), được xây dựng bằng **HTML5, CSS3 Vanilla và JavaScript Async/WebSocket**.

Tối ưu hóa cho môi trường: **Windows 11 (Google Chrome / Microsoft Edge / Brave)**.

---

## ✨ Tính năng chính

- **Tìm kiếm Ngữ nghĩa (Text Query)**: Nhập mô tả tiếng Anh để tìm kiếm khoảnh khắc video (Single & Temporal Query).
- **Xem Video & Keyframe**: Trình chiếu HLS stream video, xem các khung hình filmstrip xung quanh keyframe.
- **Rocchio Relevance Feedback**: Chọn các keyframe liên quan / không liên quan để tinh chỉnh kết quả tìm kiếm thời gian thực.
- **Xuất Kết Quả (Export & Submit DRES)**: Thu thập danh sách frame, xem trước và gửi bài thi tới server DRES.
- **Lịch sử & Phân trang (History & Pagination)**: Lưu lại các truy vấn trước đó và phân trang kết quả tìm kiếm mượt mà.

---

## 📂 Cấu Trúc Thư Mục

```
frontend/
├── index.html                # Trang chính giao diện tìm kiếm
├── login.html                # Trang nhập thông tin Session / DRES Login
├── service-worker.js         # Hỗ trợ cache PWA cơ bản
└── src/
    ├── Img/                  # Biểu tượng, icon giao diện
    ├── scripts/              # Mã xử lý JavaScript (WebSocket, Render UI, Events)
    │   ├── web_socket.js     # Quản lý kết nối WebSocket tới Backend
    │   ├── show_videoframe.js# Hiển thị lưới kết quả keyframe
    │   ├── show_video.js    # Trình phát video HLS & Filmstrip
    │   ├── update_result.js # Cập nhật danh sách kết quả
    │   ├── submit_dres.js   # Xử lý gửi bài thi DRES
    │   └── ...
    └── styles/               # CSS định dạng giao diện & layout
```

---

## ⚡ Hướng Dẫn Khởi Chạy Trên Windows 11

### Cách 1: Sử dụng Extension "Live Server" trong VS Code (Khuyên dùng)
1. Mở thư mục dự án bằng **VS Code**.
2. Cài đặt extension **Live Server** (của Ritwick Dey).
3. Nhấp chuột phải vào file [frontend/index.html](file:///D:/code-c-a-Long/frontend/index.html) và chọn **Open with Live Server**.
4. Trình duyệt sẽ mở giao diện tại địa chỉ `http://127.0.0.1:5500`.

---

### Cách 2: Sử dụng Python HTTP Server trên Windows PowerShell / CMD
Mở Terminal trên Windows và chạy lệnh:

```cmd
# Phục vụ thư mục frontend tại port 8007
python -m http.server 8007 --directory frontend
```
Sau đó truy cập trình duyệt tại: **`http://localhost:8007`**

---

### Cách 3: Sử dụng Docker Desktop trên Windows
Nếu bạn chạy bằng Docker Compose:

```cmd
docker compose up -d frontend
```
Nginx container sẽ tự động phục vụ frontend tại: **`http://localhost:8007`**

---

## 🔗 Kết Nối Backend

Frontend được cấu hình tự động kết nối với Backend FastAPI tại:
- **REST API:** `http://localhost:8000`
- **WebSocket:** `ws://localhost:8000/ws`

> 📖 Xem hướng dẫn chi tiết toàn bộ hệ thống tại [HUONG_DAN.md](file:///D:/code-c-a-Long/HUONG_DAN.md).