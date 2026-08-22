# 🏆 CẨM NANG HƯỚNG DẪN THI ĐẤU TOÀN DIỆN (A - Z)
## Hệ Thống Video Retrieval — `code-c-a-Long` (AIC 2026 / VBS)

---

## 📌 1. TỔNG QUAN KIẾN TRÚC & MÔ HÌNH CHÍNH THỨC

Hệ thống sử dụng bộ mô hình AI chuẩn SOTA:
* **Visual Backbone (Thị giác):** Google OpenCLIP `ViT-gopt-16-SigLIP2-384` (**Google SigLIP 2 Giant** ~1 tỷ tham số, vector 1152 chiều, Pretrained WebLI).
* **ASR Backbone (Âm thanh & Lời thoại):** `Faster-Whisper Large-v3-Turbo` tích hợp **Silero VAD** chạy trên CUDA Tensor Cores (nhanh gấp 4 lần, lọc sạch 100% tạp âm/nhạc nền).
* **OCR Backbone (Văn bản trên màn hình):** `PaddleOCR PP-OCRv4` kết hợp bộ cân bằng sáng thích ứng **CLAHE (Contrast Limited Adaptive Histogram Equalization)**.
* **Keyframe Selection (Trích xuất thích ứng):** `TransNetV2` chia shot tự động + Bộ lọc mờ **Laplacian Variance** ($\text{Var} \ge 95.0$) + Bộ lọc ánh sáng LAB, tự động chọn frame nét nhất trong từng phân đoạn.
* **Hybrid Search & Fusion Engine:** Bộ tìm kiếm kết hợp **Reciprocal Rank Fusion (RRF)** dung hợp điểm số giữa Dense Vector Search (GPU CUDA) và Sparse Lexical Search (BM25 Inverted Index trên CPU RAM).
* **Quản lý Nộp bài & Nén ZIP:** Quản lý toàn bộ 3 dạng bài KIS, Q&A, TRAKE và đóng gói `submission.zip` 1-click chuẩn 100% quy định BTC (`Ctrl + S`).

---

## 🧹 BƯỚC 1: DỌN DẸP DỮ LIỆU CŨ (CLEAN SLATE)

Trước khi nạp bộ video mới, hãy xóa sạch các file chỉ mục cũ để tránh xung đột dữ liệu:

Mở **PowerShell** và chạy đoạn lệnh sau:
```powershell
# 1. Xóa thư mục keyframe cũ
Remove-Item -Recurse -Force "D:\code-c-a-Long\data-keyframes\*" -ErrorAction SilentlyContinue

# 2. Xóa các file chỉ mục vector và metadata cũ
Remove-Item "D:\code-c-a-Long\features.npy", "D:\code-c-a-Long\image_paths.npy", "D:\code-c-a-Long\ocr_results.jsonl", "D:\code-c-a-Long\asr_results.jsonl", "D:\code-c-a-Long\ocr_asr_metadata.json" -ErrorAction SilentlyContinue

# 3. Xóa các gói nộp bài cũ
Remove-Item -Recurse -Force "D:\code-c-a-Long\submission\*", "D:\code-c-a-Long\submission.zip" -ErrorAction SilentlyContinue
```

---

## 📦 BƯỚC 2: KIỂM TRA & CÀI ĐẶT MÔI TRƯỜNG (NẾU CẦN)

Mở **Anaconda Prompt (Miniconda3)**:
```cmd
# 1. Kích hoạt môi trường
conda activate video_ai
cd /d D:\code-c-a-Long

# 2. Cài đặt / cập nhật thư viện từ file chuẩn (nếu máy mới hoặc chưa cài đủ)
pip install -r backend/requirements.txt
```

---

## 🚀 BƯỚC 3: NẠP TẬP VIDEO MỚI (MASTER OFFLINE PIPELINE)

Khi nhận được thư mục video mới từ Ban tổ chức (ví dụ đặt tại `D:\video_moi` hoặc `C:\video_test`), bạn chỉ cần chạy **1 dòng lệnh duy nhất**:

```cmd
conda activate video_ai
cd /d D:\code-c-a-Long

# Chạy Master Pipeline tự động 5 bước:
python data_pipeline/run_master_offline_pipeline.py --videos-dir "D:/video_moi"
```
*(Thay `"D:/video_moi"` bằng đường dẫn thực tế chứa các file `.mp4` của bạn)*

### ⚙️ Quy trình 5 bước tự động diễn ra ngầm:
1. **Bước 1/5 (Trích xuất Frame Thích ứng):** `TransNetV2` chia shot + Lọc mờ Laplacian $\to$ Lưu ảnh nét vào `data-keyframes/` và tạo các file `_map.csv`.
2. **Bước 2/5 (Trích xuất Lời thoại ASR):** `Faster-Whisper Large-v3-Turbo + Silero VAD` $\to$ Xuất `asr_results.jsonl`.
3. **Bước 3/5 (Trích xuất Chữ viết OCR):** `PaddleOCR PP-OCRv4 + CLAHE` $\to$ Xuất `ocr_results.jsonl`.
4. **Bước 4/5 (Đồng bộ Metadata):** Gộp toàn bộ OCR & ASR vào `ocr_asr_metadata.json`.
5. **Bước 5/5 (Trích xuất Vector Thị giác):** `Google SigLIP 2 Giant` $\to$ Xuất ma trận vector vào `features.npy` và `image_paths.npy`.

> Khi màn hình hiện thông báo **`🎉 TẤT CẢ DỮ LIỆU ĐÃ ĐƯỢC INDEX XONG!`** là hoàn tất 100%.

---

## 🌐 BƯỚC 4: KHỞI ĐỘNG SERVER & MỞ GIAO DIỆN

1. **Khởi động Backend AI Server:**
   ```cmd
   conda activate video_ai
   cd /d D:\code-c-a-Long
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```
2. **Truy cập Giao diện Web:**
   Mở trình duyệt Web tại: 👉 **`http://localhost:8000/frontend/`**

---

## 🎮 BƯỚC 5: HƯỚNG DẪN THAO TÁC THI ĐẤU THỰC CHIẾN

### 🎯 1. Dạng Bài KIS (Mô tả đơn)
* **Giao diện:** Chọn tab **`KIS`** ở góc trái.
* **Thao tác:**
  1. Nhập câu mô tả (tiếng Việt hoặc tiếng Anh) $\to$ Bấm **`Enter`** (Hệ thống trả về **80 frame**).
  2. Bấm vào ảnh để xem chi tiết, hoặc dùng nút **`<` / `>`** trên thẻ để lùi/tiến frame.
  3. Bấm **`Chuột giữa`** (hoặc dấu **`+`**) để chọn 1 đến 3 frame chuẩn xác nhất vào khay bên phải.
  4. Bấm **`Alt + S`** (hoặc nút **`Lưu`**) $\to$ Nhập tên file: `query-1-kis.csv` $\to$ Bấm Lưu.

---

### ❓ 2. Dạng Bài Q&A (Câu hỏi video)
* **Giao diện:** Tìm kiếm bằng tab **`KIS`**, sau đó nộp bài ở tab **`Q&A`** ở khay bên phải.
* **Thao tác:**
  1. Nhập mô tả để tìm video chứa khoảnh khắc trả lời $\to$ Bấm **`Enter`**.
  2. Click đúp vào frame kết quả để **mở Video Player lên xem trực tiếp** khoảnh khắc đó để tìm câu trả lời.
  3. Chọn frame đúng vào Khay Nộp $\to$ Chuyển tab Khay Nộp sang **`Q&A`** $\to$ Điền câu trả lời ngắn vào ô đáp án.
  4. Bấm **`Alt + S`** $\to$ Nhập tên file: `query-2-qa.csv` $\to$ Bấm Lưu.

---

### 🎬 3. Dạng Bài TRAKE (Chuỗi sự kiện theo thời gian)
* **Giao diện:** Chọn tab **`TRAKE`** ở góc trái.
* **Thao tác:**
  1. Nhập **Sự kiện 1** (Ví dụ: *"người phụ nữ mặc áo trắng bước xuống xe"*).
  2. Bấm nút **`+ Thêm Sự Kiện Tiếp Theo`** $\to$ Nhập **Sự kiện 2** (Ví dụ: *"người phụ nữ đi vào cửa hàng"*).
  3. Bấm **`Enter`** $\to$ Hệ thống tự động phân tích và trả về **Top 20 video** chứa đầy đủ chuỗi sự kiện theo đúng thứ tự thời gian thực tế với tổng cộng $\sim 120\text{ frames}$, mỗi frame được gắn nhãn màu sắc rõ ràng (**Sự kiện 1**, **Sự kiện 2**, **Sự kiện 3**...).
  4. Ở khay nộp bài bên phải (tab **`TRAKE`**):
     * Chọn frame cho Sự kiện 1 $\to$ Chọn frame cho Sự kiện 2 trong cùng 1 video.
     * Có thể bấm `+ Thêm Phương Án` để nộp thêm PA 2 nếu muốn.
  5. Bấm **`Alt + S`** $\to$ Nhập tên file: `query-3-trake.csv` $\to$ Bấm Lưu.

---

## 📦 BƯỚC 6: ĐÓNG GÓI BÀI THI & NỘP CHO BAN TỔ CHỨC

1. Bấm tổ hợp phím **`Ctrl + S`** (hoặc nút **`Gói Bài Thi`** ở góc trên bên phải màn hình).
2. Kiểm tra danh sách các câu đã làm (`query-1-kis.csv`, `query-2-qa.csv`, `query-3-trake.csv`...).
3. Bấm nút màu xanh: **`NÉN & TẠO FILE SUBMISSION.ZIP`**.
4. Nộp trực tiếp file **`D:\code-c-a-Long\submission.zip`** lên cổng thi đấu của BTC!

---

## ⌨️ BẢNG PHÍM TẮT THẦN TỐC (KEYBOARD SHORTCUTS)

| Phím tắt | Thao tác | Mô tả chi tiết |
| :--- | :--- | :--- |
| **`Enter`** | **Tìm kiếm** | Thực thi tìm kiếm câu truy vấn đang gõ. |
| **`Chuột giữa`** / **`[+]`** | **Chọn ảnh** | Thêm ngay khung hình vào Khay Nộp bài. |
| **`Alt + A`** | **Bật / Tắt Khay** | Ẩn/hiện thanh công cụ chọn ảnh bên phải. |
| **`Alt + R`** | **Tinh chỉnh AI (Refine)** | AI gom toàn bộ các góc quay cùng sự kiện lên hàng đầu (Rocchio Feedback). |
| **`Alt + S`** | **Lưu Query** | Lưu câu truy vấn hiện tại vào Gói Bài Thi. |
| **`Ctrl + S`** / **`Alt + P`** | **Gói Bài & Nén ZIP** | Mở Bảng Quản Lý & Nén `submission.zip` 1-click chuẩn 100% BTC. |
| **`Ctrl + Q`** | **Làm mới ô nhập** | Xóa nhanh câu query để gõ câu mới. |
| **`Ctrl + I`** | **Tìm kiếm OCR** | Mở ô tìm kiếm chữ viết xuất hiện trên video (biển số xe, tên đường, chữ trên áo...). |
| **`Ctrl + K`** | **Tìm kiếm ASR** | Mở ô tìm kiếm lời thoại / âm thanh phát ra trong video. |
| **`Alt + C`** / **`Alt + X`** | **Xóa ảnh khay** | Làm trống Khay Nộp để làm câu tiếp theo. |
| **`Esc`** | **Đóng cửa sổ** | Đóng trình phát video hoặc các modal xem trước. |

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
