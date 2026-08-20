# 📖 CẨM NANG HƯỚNG DẪN THI ĐẤU TOÀN DIỆN TỪ A ĐẾN Z
## Dự Án Video Retrieval System — code-c-a-Long (AIC 2026)

---

## 🏗️ 1. TỔNG QUAN CÔNG NGHỆ SOTA CỦA HỆ THỐNG
- **Thị giác AI Top-1 SOTA:** Google OpenCLIP `ViT-SO400M-14-SigLIP-384` (Vector 1152 chiều, Pretrained WebLI).
- **Dung hợp Ngữ nghĩa Song ngữ:** Cross-Lingual Dual-Embedding Blending (0.45 Tiếng Việt + 0.55 Tiếng Anh).
- **Từ điển Mở rộng Tiếng Việt:** Vietnamese Synonym Thesaurus tự động mở rộng từ đồng nghĩa.
- **Tra cứu Văn bản & Lời thoại Siêu tốc:** BM25 Inverted Index trên CPU RAM (< 2ms, chiếm 0 MB VRAM).
- **Tinh chỉnh Đa phương thức:** Thuật toán Rocchio Relevance Feedback (Phím tắt `Alt + R`).
- **Trình Quản lý Gói Nộp Bài (Batch Submission Package Manager):** Quản lý toàn bộ câu truy vấn KIS, Q&A, TRAKE và tự động nén `submission.zip` chuẩn 100% cấu trúc BTC chỉ với 1 cú click!

---

## 🗄️ 2. GIẢI THÍCH VỀ ĐỊNH DẠNG DỮ LIỆU (VÌ SAO DÙNG .JSONL THAY VÌ .JSON CŨ?)
Trong các hệ thống AI xử lý dữ liệu lớn (Big Data):
- **Định dạng cũ (`.json` đơn lẻ):** Toàn bộ dữ liệu nằm trong 1 file cây json khổng lồ. Khi máy đang chạy mà bị tắt ngang hoặc crash thì **toàn bộ file json bị hỏng (corrupt) và mất sạch dữ liệu**.
- **Định dạng mới chuẩn quốc tế (`.jsonl` - JSON Lines):** Mỗi dòng là 1 bản ghi độc lập.
  - Tự động lưu tức thì theo từng video (không bao giờ sợ mất dữ liệu).
  - Tốc độ đọc/ghi theo luồng (streaming) nhanh gấp 10 lần, tiết kiệm RAM.
  - Cả 2 file `ocr_results.jsonl` và `asr_results.jsonl` được Backend tự động nạp vào **Bộ chỉ mục BM25 CPU RAM** để tìm kiếm tức thì trong < 2ms!

---

## 📌 3. QUY TRÌNH CHUẨN BỊ DỮ LIỆU ĐỂ THI ĐẤU (CHỈ 2 BƯỚC)

Bạn đã có sẵn kho **166.628 Keyframe WebP** và **137.321 dòng lời thoại ASR**. Bạn chỉ cần chạy đúng 2 lệnh sau:

### 🔹 BƯỚC 1: Trích xuất Vector SOTA 1152 chiều mới (SigLIP SO400M)
Mở **PowerShell** tại `D:\code-c-a-Long` và chạy:
```powershell
python data_pipeline/extract_features.py --keyframes-dir ./data-keyframes --batch-size 32
```
- **Khối lượng:** 166.628 ảnh WebP.
- ⏱️ **Thời gian chạy:** **~ 38 - 45 phút** trên GPU NVIDIA RTX 3050.
- **Kết quả:** Tạo ra file `features.npy` mới hoàn toàn (1152 chiều) và `image_paths.npy`.

---

### 🔹 BƯỚC 2: Trích xuất Chữ viết OCR tiếng Việt mới
Sau khi Bước 1 chạy xong, chạy tiếp:
```powershell
python data_pipeline/extract_ocr_advanced.py
```
- **Khối lượng:** 166.628 ảnh WebP.
- ⏱️ **Thời gian chạy:** **~ 1.5 - 2 tiếng** (nhận diện biển số, biển hiệu, chữ trên áo, tên đường).
- **Kết quả:** Tạo ra file `ocr_results.jsonl` mới sạch sẽ, khớp 100% với keyframe.

---

### 🔹 BƯỚC 3: Khởi động Backend Server
```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
- Mở trình duyệt tại: 👉 **`http://localhost:8000/frontend/`**

---

## 🎮 4. HƯỚNG DẪN THAO TÁC TRÊN GIAO DIỆN KHI THI ĐẤU

### ⌨️ BẢNG PHÍM TẮT THẦN TỐC (SHORTCUTS):
- **`Alt + A`**: Bật / Tắt Khay Chọn kết quả bên phải.
- **`Alt + R`**: Kích hoạt **Cây Đũa Phép ✨ (Tinh chỉnh Refine Search)** theo các ảnh đã chọn.
- **`Alt + S`**: Lưu câu truy vấn hiện tại vào Gói Nộp Bài.
- **`Alt + P`** hoặc **`Ctrl + S`**: Mở Bảng Quản Lý Gói Nộp Bài & Nén ZIP.
- **`Enter`**: Tìm kiếm câu truy vấn đang gõ.
- **`Chuột giữa (Middle Click)`**: Bấm trực tiếp lên ảnh để thêm ngay vào Khay Chọn.

---

### 📝 THAO TÁC CHO TỪNG DẠNG CÂU HỎI:

#### A. Dạng 1: Textual KIS (`query-X-kis.csv`):
1. Gõ mô tả sự kiện -> Nhấn `Enter`.
2. Bấm dấu `[+]` vào 1 - 5 ảnh bạn thấy đúng nhất bằng mắt.
3. *(Tùy chọn)* Bấm **`✨ Tinh chỉnh (Alt + R)`** nếu muốn AI gom thêm các frame cùng video.
4. Bấm **`➕ Lưu Query (Alt + S)`** -> Hệ thống tự động đặt ảnh bạn chọn lên đầu và bù đủ 100 dòng AI có điểm cao nhất.

#### B. Dạng 2: Visual Q&A (`query-X-qa.csv`):
1. Chuyển sang Tab **`❓ Q&A`** ở Khay Chọn.
2. Gõ câu trả lời vào ô **`"ĐÁP ÁN Q&A"`** (VD: `5`, `Màu đỏ`, `Xe cứu thương`...).
3. Chọn menu số dòng: `Xuất 100 dòng (Khuyên dùng)` hoặc `Xuất 30 dòng`.
4. Bấm chọn vài frame khả nghi -> Bấm **`➕ Lưu Query (Alt + S)`**.
5. Hệ thống tự động gán đáp án đó cho toàn bộ 100 (hoặc 30) dòng ứng viên!

#### C. Dạng 3: TRAKE (`query-X-trake.csv`):
1. Chuyển sang Tab **`⏱️ TRAKE`** ở Khay Chọn.
2. Tìm kiếm Event 1 -> Chọn frame 1 của video.
3. Tìm kiếm Event 2, 3 -> Chọn tiếp frame 2, 3 của video đó.
4. Bấm **`➕ Lưu Query (Alt + S)`**.
5. Hệ thống tự động nhóm theo từng video và sắp xếp thời gian tăng dần frame_1 < frame_2 < ... < frame_N.

---

### 📦 ĐÓNG GÓI NÉN ZIP NỘP BÀI (CHỈ 1 CÚ CLICK):
1. Sau khi làm xong tất cả các câu trong đợt thi (Badge hiện `4/4`), bấm nút **`📦 Gói Nộp Bài & Nén ZIP`** (hoặc nhấn `Ctrl + S`).
2. Kiểm tra danh sách các câu đã làm (có thể bấm nút `👁️ Xem` để preview file CSV).
3. Bấm nút neon: **`⚡ NÉN & TẠO FILE SUBMISSION.ZIP`**.
4. File ZIP hoàn chỉnh sẽ được tạo trực tiếp tại:
   👉 **`D:\code-c-a-Long\submission.zip`** *(Bên trong có sẵn thư mục `submission/` chứa đầy đủ các file CSV chuẩn 100% quy định BTC)*.
5. Lên portal cuộc thi và tải file này lên nộp!

---

## 🎯 5. NHỮNG VIỆC TIẾP THEO CẦN LÀM CHO CUỘC THI NGÀY MAI (CHI TIẾT TỪNG BƯỚC)

Dưới đây là kế hoạch hành động chuẩn bị toàn diện để ngày mai bạn bước vào phòng thi với tâm thế tự tin 100%:

### 🕒 GIAI ĐOẠN 1: CHIỀU NAY (16h00 - 18h30) — CHẠY DỮ LIỆU
1. **Chạy trích xuất Vector SigLIP 1152d:**
   ```powershell
   python data_pipeline/extract_features.py --keyframes-dir ./data-keyframes --batch-size 32
   ```
2. **Chạy trích xuất OCR tiếng Việt:**
   ```powershell
   python data_pipeline/extract_ocr_advanced.py
   ```

---

### 🕒 GIAI ĐOẠN 2: TỐI NAY (19h00 - 21h00) — TEST VẬN HÀNH THỰC TẾ
1. **Khởi động Backend AI:**
   ```powershell
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```
2. **Mở trình duyệt `http://localhost:8000/frontend/` và thử nghiệm:**
   - [ ] Gõ 1 câu KIS thử (vd: *"cảnh sát giao thông đuổi bắt xe ô tô"*), xem ảnh trả về trong < 0.05s.
   - [ ] Thử chọn 3 ảnh -> Bấm `Alt + R` để kiểm tra tính năng Tinh chỉnh (Refine Search).
   - [ ] Thử tạo 1 câu Q&A (gõ đáp án "5") -> Bấm `Alt + S` lưu query.
   - [ ] Bấm `Ctrl + S` mở bảng Gói Nộp Bài -> Bấm **Nén Submission.zip** -> Kiểm tra xem file `D:\code-c-a-Long\submission.zip` đã được tạo chưa.
3. **Nghỉ ngơi sớm:** Sau khi test xong mọi thứ mượt mà, tắt máy và đi ngủ sớm để giữ tinh thần sảng khoái.

---

### 🕒 GIAI ĐOẠN 3: NGÀY MAI TRƯỚC 17H00 — SẴN SÀNG CHIẾN ĐẤU
1. **16h30 ngày mai (Trước giờ thi 30 phút):**
   - Bật máy tính, kết nối mạng Internet ổn định.
   - Khởi động sẵn Backend: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`
   - Mở sẵn giao diện web `http://localhost:8000/frontend/` trên trình duyệt.
   - Đăng nhập sẵn tài khoản Portal nộp bài của BTC.
2. **17h00 ngày mai (Bắt đầu thi):**
   - Khi BTC phát đề đợt 1 (các file `query-1-kis.txt`, `query-2-kis.txt`, `query-3-qa.txt`...):
   - Đọc từng câu -> Tìm kiếm -> Bấm chọn frame -> Bấm `➕ Lưu Query`.
   - Khi làm xong đợt thi -> Bấm **`⚡ NÉN SUBMISSION.ZIP`** -> Lấy file `submission.zip` nộp lên portal BTC.
   - Hoàn thành xuất sắc vòng thi! 🏆
