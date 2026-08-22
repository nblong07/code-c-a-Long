# 🏆 CẨM NANG HƯỚNG DẪN THI ĐẤU TOÀN DIỆN (A - Z)
## Hệ Thống Video Retrieval — `code-c-a-Long` (AIC 2026 / VBS)

---

## 📌 1. TỔNG QUAN 6 TRỤ CỘT TÍNH NĂNG CỦA HỆ THỐNG

Hệ thống được thiết kế theo mô hình khép kín 6 phần tương tác hoàn chỉnh:

```
[Phần 1: Offline Indexing] ──▶ [Phần 3: Search Engine Core] ◀──▶ [Phần 2: Frontend & UI]
                                       │                                 ▲
                                       ▼                                 │
                            [Phần 6: Pack & Submit] ◀── [Phần 5: Session & Bảng Ghim] ◀── [Phần 4: Relevance Feedback]
```

* **Phần 1: Tiền Xử Lý Dữ Liệu Thô (Offline Indexing 5 bước):** TransNetV2 Adaptive Sampling + Whisper Large-v3-Turbo + Paddle/VietOCR + Bisect Metadata Alignment + Google SigLIP 2 Giant FP16 Tensor Cores (1152d, trích xuất 14k ảnh chỉ trong 6–8 phút).
* **Phần 2: Giao Diện Gõ Truy Vấn & Tương Tác Người - Máy:** Tìm kiếm đa kênh (Text/OCR/ASR/QA), hiển thị mốc thời gian `MM:SS`, phím tắt thần tốc, Vanilla JS siêu nhẹ.
* **Phần 3: Search Engine Core & Hybrid Ranking:** Reciprocal Rank Fusion (RRF k=60), Smart Query Omni-Parser (tự động tách TRAKE, OCR, ASR), GPU Tensor cuBLAS ($< 2\text{ms}$), BM25 Inverted Index ($< 1\text{ms}$).
* **Phần 4: Relevance Feedback & Tương Tác Phản Hồi Vòng Lặp:** Tìm kiếm theo ảnh tương tự (Image-to-Image), Timeline Explorer duyệt toàn bộ video, lướt frame kề cận ($\pm 1$), Dual Preview Mode, Rocchio Feedback (`Alt + R`).
* **Phần 5: Quản Trị Phiên Thi Đấu & Bảng Ghim (Pinboard):** LocalStorage chống mất dữ liệu khi F5, khay ghim ảnh tách biệt 3 task (KIS/VQA/TRAKE), thanh chỉ báo màu sắc MRR (🟢/🟡/🔴), lịch sử 60 query 1-click restore.
* **Phần 6: Đóng Gói, Kiểm Duyệt & Nộp Bài (Validator & DRES Submit):** Tự động sửa lỗi format (xóa `.mp4`, xóa header, escape `"`, giới hạn 100 dòng), nén `submission.zip` 1-click chuẩn BTC và nộp API DRES trực tiếp.

---

## 🛠️ HƯỚNG DẪN CHI TIẾT CÁCH SỬ DỤNG TỪNG PHẦN

### 🔹 PHẦN 1: Tiền Xử Lý Dữ Liệu Thô (Offline Pipeline)
Khi nhận tập video mới từ Ban tổ chức:
1. **Dọn dẹp dữ liệu cũ nếu cần (Clean Slate):**
   ```powershell
   Remove-Item -Recurse -Force "D:\code-c-a-Long\data-keyframes\*" -ErrorAction SilentlyContinue
   Remove-Item "D:\code-c-a-Long\features.npy", "D:\code-c-a-Long\image_paths.npy", "D:\code-c-a-Long\ocr_results.jsonl", "D:\code-c-a-Long\asr_results.jsonl", "D:\code-c-a-Long\ocr_asr_metadata.json" -ErrorAction SilentlyContinue
   Remove-Item -Recurse -Force "D:\code-c-a-Long\submission\*", "D:\code-c-a-Long\submission.zip" -ErrorAction SilentlyContinue
   ```
2. **Chạy Master Pipeline 1 dòng lệnh:**
   ```cmd
   conda activate video_ai
   cd /d D:\code-c-a-Long
   python data_pipeline/run_master_offline_pipeline.py --videos-dir "D:/video_moi"
   ```
   * Hệ thống tự động tuần tự: Cắt frame nét $\to$ Bóc băng ASR $\to$ Đọc chữ OCR $\to$ Gộp metadata `ocr_asr_metadata.json` $\to$ Trích xuất vector SigLIP 2 FP16 `features.npy` (hoàn tất toàn bộ trong ~20–25 phút).

---

### 🔹 PHẦN 2 & 3: Khởi Động Server & Tìm Kiếm Đa Phương Thức (Search Engine)
1. **Khởi động Backend:**
   ```cmd
   conda activate video_ai
   cd /d D:\code-c-a-Long
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```
2. **Mở Trình Duyệt Web:** 👉 **`http://localhost:8000/frontend/`**
3. **Cách Gõ Query Thông Minh:**
   * **Mô tả cảnh/hành động (KIS):** Nhập vào ô `Text Query` (ví dụ: *"người phụ nữ áo đỏ lái xe máy qua ngã tư"*). Hệ thống tự động làm giàu từ đồng nghĩa và dịch sang tiếng Anh thị giác.
   * **Chuỗi sự kiện liên hoàn (TRAKE):** Bạn có thể gõ nguyên câu dài (ví dụ: *"người đàn ông bước vào xe ô tô sau đó lái xe đi"*). AI **Smart Omni-Parser** sẽ tự động nhận diện từ nối (*"sau đó", "tiếp theo", "rồi"*) và tách thành các Stage liên hoàn!
   * **Chữ trên màn hình/biển hiệu (OCR):** Nhấn `Ctrl + I` $\to$ Gõ chữ vào ô `OCR Query` (hoặc để trong ngoặc kép `"THCS Chu Văn An"`, *"51F-123.45"*).
   * **Lời thoại giọng nói (ASR):** Nhấn `Ctrl + K` $\to$ Gõ lời thoại vào ô `ASR Query` (ví dụ: *"bản tin dự báo thời tiết"*).
   * Bấm **`Enter`** $\to$ Hệ thống tự động chạy **RRF Hybrid Fusion** trả kết quả ngay sau $< 5\text{ms}$!

---

### 🔹 PHẦN 4: Tinh Chỉnh Kết Quả Bằng Relevance Feedback & Timeline Explorer
Khi thấy một frame gần đúng trên màn hình:
1. 📷 **Tìm các frame tương tự:** Bấm vào **icon Camera** (`similarity_search`) trên góc thẻ ảnh để tìm toàn bộ các góc quay tương đồng.
2. ⬅️ / ➡️ **Nhảy frame tức thì:** Bấm nút mũi tên trái/phải trên thẻ ảnh để lùi/tiến 1 frame mà không cần mở video.
3. 🎞️ **Mở Timeline Explorer:** Bấm **icon Cuộn phim** trên thẻ ảnh:
   * Thanh duyệt toàn bộ chuỗi frame của video sẽ mở ra ở cạnh dưới.
   * Dùng phím `←` / `→` để di chuyển, phím `Space` hoặc `+` để chọn frame chuẩn nhất, phím `R` để đưa frame lên Top 1, phím `Esc` để đóng.
4. 🔍 **So Sánh Kép (Dual Preview):** Giữ đè phím **`Alt`** (hoặc bấm **`Alt + X`**) rồi rê chuột qua các ảnh để đối chiếu trực tiếp 2 ảnh lớn song song trái - phải.
5. ⚡ **Rocchio Feedback (`Alt + R`):** Chọn 1-2 ảnh đúng vào khay rồi nhấn `Alt + R`, AI tự động gom tất cả các góc quay của sự kiện lên Top đầu.

---

### 🔹 PHẦN 5: Quản Lý Bảng Ghim & Lịch Sử Phiên Thi (Pinboard & History)
1. **Ghim Ảnh Vào Khay (Export Area):**
   * Bấm **`Chuột giữa`** hoặc dấu **`+`** trên ảnh $\to$ Ảnh được lưu ngay vào Khay Nộp bài bên phải.
   * Nhìn **Thanh chỉ báo màu sắc**: 🟢 `1 frame (Tốt nhất)` | 🟡 `2-3 frame (OK)` | 🔴 `4-5 frame (Nhiều, nên bớt)`.
2. **Chuyển Đổi Task Nhanh:**
   * **Tab KIS:** Dành cho dạng bài tìm ảnh đơn.
   * **Tab Q&A (VQA):** Tự động mở ô `vqa-common-answer` ở trên cùng $\to$ Gõ nhanh đáp án câu hỏi vào đây.
   * **Tab TRAKE:** Dành cho bài chuỗi sự kiện. Tự động hỗ trợ chọn Frame Sự kiện 1 và Frame Sự kiện 2.
3. **Sử Dụng Lịch Sử Truy Vấn (Query History):**
   * Mở tab Lịch sử ở bảng trái $\to$ Click vào bất kỳ câu query nào trong 60 câu gần nhất để nạp lại ngay vào ô tìm kiếm.

---

### 🔹 PHẦN 6: Kiểm Duyệt, Đóng Gói & Nộp Bài (DRES & Package ZIP)
1. **Lưu Câu Truy Vấn:**
   * Bấm **`Alt + S`** (hoặc nút **`Lưu`**) $\to$ Nhập tên file: `query-1-kis.csv`, `query-2-qa.csv`... $\to$ Bấm Lưu.
   * Badge đếm số lượng câu trên Header sẽ tự động tăng lên.
2. **Đóng Gói ZIP 1-Click (Vòng Sơ Tuyển):**
   * Bấm **`Ctrl + S`** (hoặc `Alt + P`) $\to$ Modal Quản lý gói nộp bài xuất hiện.
   * Bấm nút màu xanh: **`NÉN & TẠO FILE SUBMISSION.ZIP`**.
   * Hệ thống tự động: Loại bỏ `.mp4`, xóa header, escape `"`, kiểm tra UTF-8 và tạo file **`D:\code-c-a-Long\submission.zip`** chuẩn 100% quy định BTC.
3. **Nộp Trực Tiếp DRES (Vòng Chung Kết Live):**
   * Bấm nút **`Submit DRES`** màu xanh lá trên giao diện để gửi trực tiếp kết quả lên server giám khảo.

---

## ⌨️ BẢNG PHÍM TẮT THẦN TỐC TOÀN DIỆN (KEYBOARD SHORTCUTS CHEAT SHEET)

### 1. 🔍 Nhóm Tìm Kiếm & Nhập Liệu (Search & Input)
| Phím tắt | Thao tác | Mô tả chi tiết |
| :--- | :--- | :--- |
| **`Enter`** | **Thực thi Tìm kiếm** | Chạy tìm kiếm tức thì cho câu truy vấn đang nhập trong bất kỳ ô nào (Text, OCR, ASR, QA, TRAKE). |
| **`Shift + Enter`** | **Lọc Nâng Cao** | Kích hoạt tìm kiếm kết hợp bộ lọc đối tượng / thuộc tính. |
| **`/` (Dấu xuyệt)** | **Focus Ô Nhập Đầu** | Đưa con trỏ chuột ngay lập tức vào ô nhập Text Query đầu tiên (khi không trong ô nhập). |
| **`?`** hoặc **`Shift + /`** | **Chuyển Đổi Ô Nhập** | Nhảy vòng tròn qua lại giữa các ô nhập Text Query trong các Scene. |
| **`Ctrl + I`** | **Thêm ô tìm OCR** | Mở ô tìm kiếm chữ viết xuất hiện trên ảnh (biển tên đường, biển số xe, cổng chùa,...). |
| **`Ctrl + K`** | **Thêm ô tìm ASR** | Mở ô tìm kiếm lời thoại / âm thanh phát ra trong video. |
| **`Ctrl + J`** | **Thêm Bộ Lọc Đối Tượng** | Mở bộ lọc thuộc tính đối tượng chi tiết (màu sắc, số lượng, chủng loại). |
| **`Ctrl + H`** | **Thêm Cảnh Mới (Scene)** | Thêm 1 Search Scene mới cho chuỗi sự kiện hoặc đa điều kiện. |
| **`Ctrl + Q`** | **Reset Toàn Bộ Query** | Xóa sạch toàn bộ text trong tất cả ô nhập, hủy các cảnh phụ và focus về ô đầu tiên. |
| **`Ctrl + E`** | **Xóa Sạch Văn Bản** | Xóa nhanh nội dung trong tất cả các `textarea` hiện tại. |
| **`Alt + W`** | **Đổi Bố Cục (Layout)** | Chuyển đổi linh hoạt giữa giao diện dạng dọc (Vertical) và dạng ngang (Horizontal). |
| **`Alt + E`** | **Bật/Tắt Dịch Thuật** | Bật/tắt chế độ tự động dịch câu truy vấn (Translate Option). |

### 2. 🖼️ Nhóm Xem Ảnh, Video & Dải Frame Lân Cận (Inspection & Timeline)
| Phím tắt | Thao tác | Mô tả chi tiết |
| :--- | :--- | :--- |
| **`Alt` (Giữ đè)** | **So Sánh Kép Tức Thì** | Rê chuột qua bất kỳ ảnh nào để xem phóng to ở khung Preview bên trái đối chiếu với khung phải. |
| **`Alt + X`** | **Bật/Tắt Chế Độ So Sánh** | Bật/tắt chế độ khóa Preview so sánh mà không cần giữ đè phím Alt. |
| **`←` / `→` (Mũi tên)** | **Nhảy Frame Kề Cận** | Lùi về 1 frame trước / Tiến tới 1 frame sau trong video (trên thẻ ảnh hoặc Timeline bar). |
| **`Space`** hoặc **`+`** | **Chọn Frame Đang Xem** | Thêm ngay frame đang chọn trong Timeline Explorer vào Khay Nộp bài. |
| **`R`** | **Đưa Frame Lên Top 1** | Đưa frame đang chọn lên vị trí đầu tiên và kích hoạt truy vấn tinh chỉnh (Refine). |
| **`Esc`** | **Đóng Cửa Sổ / Thoát** | Đóng trình phát Video Player, thanh duyệt Timeline Explorer hoặc Modal đang mở. |

### 3. 📦 Nhóm Quản Trị Khay & Nộp Bài (Pinboard & Submission)
| Phím tắt | Thao tác | Mô tả chi tiết |
| :--- | :--- | :--- |
| **`Chuột giữa`** / **`[+]`** | **Ghim Khung Hình** | Thêm ngay frame kết quả vào Khay Nộp bài (Export Area). |
| **`Alt + A`** | **Ẩn / Hiện Khay Nộp** | Bật/tắt thanh công cụ quản lý ảnh bên phải màn hình. |
| **`Alt + R`** | **Tinh chỉnh AI (Refine)** | Kích hoạt bộ tinh chỉnh Vector dựa trên các frame đã chọn trong khay (Rocchio Feedback). |
| **`Alt + S`** | **Lưu Câu Truy Vấn** | Lưu câu query hiện tại vào danh sách gói nộp bài (`query-x-kis.csv`, `query-x-qa.csv`...). |
| **`Ctrl + S`** / **`Alt + P`** | **Gói Bài & Nén ZIP** | Mở Bảng Quản Lý Gói Bài Thi và Nén `submission.zip` 1-click chuẩn 100% BTC. |
| **`Alt + C`** | **Làm Sạch Khay** | Xóa toàn bộ ảnh đang chọn trong khay để sẵn sàng cho câu hỏi tiếp theo. |

---

## 💡 BÍ QUYẾT ĐẠT TOP 1 ĐIỂM SỐ (MRR & TOP RANK)

1. **Tuyệt đối KHÔNG chọn tràn lan hàng chục frame không chắc chắn:**
   * Hệ thống tính điểm dựa trên **vị trí của frame đúng đầu tiên** (Mean Reciprocal Rank - MRR).
   * Chỉ nên chọn **1 đến 3 frame chuẩn xác nhất**, đặt frame bạn tin tưởng nhất lên hàng đầu.
2. **Khay Nộp có thanh chỉ báo thông minh:**
   * 🟢 `1 frame — Tốt nhất` (Tối đa hóa điểm số MRR).
   * 🟡 `2-3 frame — OK` (Chấp nhận được khi phân vân giữa 2 góc quay).
   * 🔴 `4-5 frame — Nhiều` (Nên loại bớt các frame phụ).
3. **Nén ZIP chuẩn 100% BTC:**
   * File `submission.zip` tự động được đóng gói chuẩn cấu trúc không có header, không chứa đuôi `.mp4`, đã được lọc trùng lặp và tương thích hoàn toàn với hệ thống chấm thi của Ban tổ chức!
