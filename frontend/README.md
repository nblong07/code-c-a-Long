# Giao Diện Người Dùng (Frontend Web UI)

Thư mục này chứa mã nguồn giao diện web phục vụ việc tìm kiếm, xem lại video và quản lý bài nộp thi đấu. Giao diện được xây dựng bằng **HTML5, CSS3 và JavaScript thuần (Vanilla JS)**, kết nối trực tiếp với backend qua giao thức **WebSocket** để cập nhật kết quả tức thì.

Tương thích tốt trên các trình duyệt hiện đại: **Google Chrome, Microsoft Edge, Brave**.

---

## 1. Các tính năng chính

* **Tìm kiếm đa dạng:**
  * Hỗ trợ tìm kiếm bằng mô tả ngữ cảnh hình ảnh (tiếng Việt hoặc tiếng Anh).
  * Hỗ trợ tìm kiếm chuyên biệt theo chữ viết xuất hiện trên màn hình (`Ctrl + I`) và lời thoại của nhân vật/MC (`Ctrl + K`).
* **Duyệt khung hình lân cận (Neighbor Scrubbing):**
  * Nhấp vào bất kỳ ảnh keyframe nào để mở dải khung hình lân cận (từ $-5$ đến $+5$ frame xung quanh) kèm mốc giây chính xác, giúp người dùng quan sát diễn biến trước và sau khoảnh khắc đó.
* **Trình phát video tích hợp:**
  * Bấm đúp vào ảnh để mở trình phát video và tự động nhảy tới đúng giây xuất hiện của khung hình. Giúp người dùng xác minh nội dung và tìm đáp án cho dạng bài Q&A.
* **Tinh chỉnh kết quả tìm kiếm (`Alt + R`):**
  * Chọn các ảnh đúng mục tiêu và bấm phím tắt để hệ thống tính lại trọng tâm tìm kiếm, đưa các khung hình tương tự lên đầu danh sách.
* **Khay nộp bài đa năng:**
  * **Tab KIS:** Chọn từ 1 đến 3 khung hình đại diện cho khoảnh khắc được mô tả. Có chỉ báo số lượng để tránh chọn quá nhiều làm giảm điểm MRR.
  * **Tab Q&A:** Chọn khung hình minh chứng và nhập câu trả lời ngắn vào ô đáp án.
  * **Tab TRAKE:** Chọn chuỗi các khung hình theo đúng thứ tự thời gian của cùng một video. Hệ thống hỗ trợ tạo nhiều phương án (PA 1, PA 2...) và tự động sắp xếp theo mốc thời gian tăng dần.
* **Đóng gói file nộp bài (`Ctrl + S` hoặc `Alt + P`):**
  * Mở bảng kiểm tra các câu đã làm, kiểm tra định dạng và nén trực tiếp thành file `submission.zip` để nộp cho ban tổ chức.

---

## 2. Cách truy cập giao diện

### Cách 1: Sử dụng cùng Backend FastAPI (Khuyên dùng)
Khi backend đã chạy (cổng 8000), mở trình duyệt và truy cập:
👉 **`http://localhost:8000/frontend/`**

### Cách 2: Mở độc lập qua Live Server (VS Code)
1. Mở thư mục dự án trong VS Code.
2. Nhấp chuột phải vào file `frontend/index.html` $\to$ chọn **Open with Live Server**.
3. Trình duyệt sẽ mở tại địa chỉ `http://127.0.0.1:5500`.

---

## 3. Bảng phím tắt thao tác nhanh

| Phím tắt | Thao tác | Mô tả chi tiết |
| :--- | :--- | :--- |
| **`Enter`** | Tìm kiếm | Gửi câu truy vấn ở ô tìm kiếm hiện tại |
| **`Chuột giữa`** hoặc **`[+]`** | Chọn ảnh | Thêm keyframe vào khay nộp bài |
| **`Alt + A`** | Bật / tắt khay | Ẩn hoặc hiện thanh khay nộp bài bên phải |
| **`Alt + R`** | Tinh chỉnh | Tinh chỉnh kết quả tìm kiếm dựa trên các ảnh đã chọn trong khay |
| **`Alt + S`** | Lưu câu hỏi | Lưu kết quả của câu hiện tại vào bộ bài thi |
| **`Ctrl + S`** hoặc **`Alt + P`** | Nén bài thi | Mở bảng quản lý bài thi và nén thành file `submission.zip` |
| **`Ctrl + Q`** | Xóa ô nhập | Xóa nhanh nội dung ô tìm kiếm để nhập câu mới |
| **`Ctrl + I`** | Tìm OCR | Chuyển sang ô tìm kiếm chữ viết trên màn hình |
| **`Ctrl + K`** | Tìm ASR | Chuyển sang ô tìm kiếm giọng nói / lời thoại |
| **`Alt + C`** hoặc **`Alt + X`** | Xóa khay | Xóa toàn bộ ảnh đang chọn trong khay nộp |
| **`Esc`** | Đóng cửa sổ | Đóng trình phát video hoặc hộp thoại đang mở |