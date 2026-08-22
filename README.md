# Hệ Thống Truy Vấn Video Đa Phương Thức (Multimodal Video Retrieval System) 🚀
**Codebase:** `code-c-a-Long` | **Tối ưu cho:** Cuộc thi Video Retrieval / AI City Challenge (AIC 2026) / VBS

---

## 📌 1. TỔNG QUAN HỆ THỐNG (SYSTEM OVERVIEW)

Hệ thống cung cấp giải pháp tìm kiếm khoảnh khắc video (Video Moment Retrieval) toàn diện và hiệu năng cao từ văn bản tự nhiên, sử dụng các mô hình AI chuẩn SOTA mới nhất:
* **Visual Backbone (Thị giác):** Google OpenCLIP `ViT-gopt-16-SigLIP2-384` (**Google SigLIP 2 Giant** - Mô hình thị giác ~1 tỷ tham số SOTA đỉnh cao, vector 1152 chiều, Pretrained WebLI).
* **ASR Backbone (Âm thanh & Lời thoại):** `Faster-Whisper Large-v3-Turbo` tích hợp **Silero VAD (Voice Activity Detection)** chạy trên CUDA Tensor Cores (nhanh gấp 4 lần, lọc sạch 100% tạp âm/nhạc nền).
* **OCR Backbone (Văn bản trên màn hình):** `PaddleOCR PP-OCRv4` kết hợp bộ tiền xử lý tăng tương phản thích ứng **CLAHE (Contrast Limited Adaptive Histogram Equalization)** bắt trọn biển số, logo và phụ đề mờ.
* **Keyframe Extraction (Trích xuất thích ứng):** `TransNetV2` chia shot tự động + Bộ lọc mờ **Laplacian Variance** ($\text{Var} \ge 95.0$) + Bộ lọc ánh sáng LAB, tự động chọn frame nét nhất trong từng phân đoạn.
* **Hybrid Search & Fusion Engine:** Bộ tìm kiếm kết hợp **Reciprocal Rank Fusion (RRF)** dung hợp điểm số giữa Dense Vector Search (GPU CUDA) và Sparse Lexical Search (BM25 Inverted Index trên CPU RAM) với thời gian phản hồi siêu tốc ($< 10\text{ms}$).
* **Giao diện thi đấu & Quản lý nộp bài:** Web UI Cyberpunk hỗ trợ phím tắt thần tốc, chế độ tìm kiếm **KIS (Mô tả đơn)** và **TRAKE (Chuỗi sự kiện theo thời gian)**, đóng gói `submission.zip` 1-click chuẩn 100% quy định BTC (hỗ trợ cả 3 dạng bài KIS, Q&A, TRAKE).

---

## 🏛️ 2. KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)

```mermaid
graph TD
    subgraph "1. OFFLINE DATA PIPELINE (Xử lý tuần tự, VRAM an toàn 100%)"
        Raw_Videos[Thư mục Video MP4 Mới] --> Step1["Bước 1: transnetv2_keyframes.py<br/>(TransNetV2 + Lọc mờ Laplacian + Lấy Frame Nét)"]
        Step1 --> Keyframes["Thư mục data-keyframes/ & CSV Maps"]
        Step1 --> Step2["Bước 2: extract_asr_advanced.py<br/>(Faster-Whisper Large-v3-Turbo + Silero VAD)"]
        Step1 --> Step3["Bước 3: extract_ocr_advanced.py<br/>(PaddleOCR v4 + Tiền xử lý CLAHE)"]
        Step2 --> ASR_JSONL["asr_results.jsonl"]
        Step3 --> OCR_JSONL["ocr_results.jsonl"]
        ASR_JSONL & OCR_JSONL --> Step4["Bước 4: merge_ocr_asr_metadata.py<br/>(ocr_asr_metadata.json)"]
        Keyframes --> Step5["Bước 5: extract_features.py<br/>(Google SigLIP 2 Giant 1152d)"]
        Step5 --> Feats_NPY["features.npy & image_paths.npy"]
    end

    subgraph "2. RUNTIME BACKEND SERVER (FastAPI + GPU Tensor Matrix Search)"
        Feats_NPY --> GPU_Tensor["PyTorch CUDA Tensor Cache (166k x 1152d)"]
        Step4 --> BM25_Engine["BM25 Inverted Index (OCR & ASR trên CPU RAM)"]
        
        Client_WS[WebSocket /ws] <--> Main_FastAPI[FastAPI Server backend/main.py]
        Main_FastAPI --> VSS[Vector Search Service]
        VSS -->|Mã hóa Query trực tiếp| SigLIP_Encoder[SigLIP 2 Giant Text Encoder]
        SigLIP_Encoder --> Dense_Search[GPU Matrix Multi cuBLAS]
        VSS --> BM25_Engine
        Dense_Search & BM25_Engine --> RRF_Fusion["Reciprocal Rank Fusion (RRF)"]
        RRF_Fusion --> Ranked_Results[Top 100 Kết quả Khớp nhất]
    end

    subgraph "3. FRONTEND INTERACTIVE UI (HTML5 / Vanilla JS / CSS3)"
        Ranked_Results --> Web_UI[Web Browser Dashboard /frontend/]
        Web_UI --> Player[Trình phát Video HLS/MP4 & Duyệt Frame]
        Web_UI --> Tray[Khay Nộp Bài: KIS / Q&A / TRAKE]
        Tray --> Submission_Packer[1-Click Đóng gói submission.zip]
    end
```

---

## ⚙️ 3. DANH MỤC MÔ HÌNH VÀ CÔNG NGHỆ CHÍNH

| Thành phần | Mô hình duy nhất được sử dụng | Vai trò & Đặc điểm vượt trội |
| :--- | :--- | :--- |
| **Visual Backbone** | `Google SigLIP 2 Giant` (`ViT-gopt-16-SigLIP2-384`) | Mô hình thị giác ~1 tỷ tham số Vision-Language SOTA, vector 1152 chiều, nhận diện xuất sắc màu sắc, vật thể nhỏ và ngữ nghĩa phức tạp. |
| **ASR (Speech-to-Text)** | `Faster-Whisper Large-v3-Turbo` + `Silero VAD` | Nhận diện tiếng Việt chuẩn xác từng mili-giây, lọc sạch 100% tiếng ồn/nhạc nền, tốc độ siêu nhanh. |
| **OCR (Text-on-Screen)** | `PaddleOCR PP-OCRv4` + `CLAHE Enhancement` | Cân bằng sáng thích ứng làm rõ chữ mờ/cháy sáng; nhận diện biển số xe, tên đường, banner. |
| **Keyframe Selection** | `TransNetV2` + `Laplacian Variance Filter` | Tự động phát hiện chuyển cảnh, quét lân cận $\pm 5$ frames để chọn khung hình nét nhất ($\text{Var} \ge 95.0$). |
| **Hybrid Search & Fusion** | `Reciprocal Rank Fusion (RRF)` | Dung hợp điểm số chuẩn xác: $RRF(d) = \frac{1.00}{60 + \text{Rank}_{\text{visual}}} + \frac{0.90}{60 + \text{Rank}_{\text{ocr}}} + \frac{0.85}{60 + \text{Rank}_{\text{asr}}}$. |
| **Vector Search Engine** | `PyTorch CUDA Tensor Matrix Search` | Nhân ma trận trực tiếp trên GPU CUDA (RTX 3050), thời gian truy vấn $< 2\text{ms}$. |
| **Interactive Feedback** | `Rocchio Relevance Feedback` (`Alt + R`) | AI tái định vị vector trọng tâm dựa trên các ảnh thí sinh đã chọn để gom toàn bộ góc quay liên quan. |

---

## 💻 4. YÊU CẦU PHẦN CỨNG (SYSTEM PROFILE)

* **Hệ điều hành:** Windows 10 / 11 hoặc Ubuntu Linux.
* **CPU:** AMD Ryzen 7 / Intel Core i7.
* **RAM:** 16 GB RAM (hệ thống được tối ưu chỉ tiêu thụ $\sim 6\text{GB RAM}$).
* **GPU:** NVIDIA GeForce RTX 3050 (6GB VRAM) hoặc cao hơn. Mức chiếm dụng VRAM runtime chỉ $\sim 3.6\text{GB VRAM}$.

---

## 🚀 5. HƯỚNG DẪN VẬN HÀNH TOÀN DIỆN

### A. Kích hoạt môi trường
Mở **Anaconda Prompt (Miniconda3)**:
```cmd
conda activate video_ai
cd /d D:\code-c-a-Long
```

---

### B. Quy trình nạp tập Video mới (Master Offline Indexing Pipeline)
Khi nhận được tập video mới từ Ban tổ chức, bạn chỉ cần chạy **1 lệnh duy nhất** để tự động thực hiện tuần tự toàn bộ 5 bước (quản lý VRAM 6GB an toàn, không bao giờ lỗi Out-Of-Memory):

```cmd
# Cú pháp chạy chuẩn:
python data_pipeline/run_master_offline_pipeline.py --videos-dir "D:/thu_muc_video_moi"
```

*Các tham số tùy chọn nếu cần:*
* `--videos-dir`: Đường dẫn thư mục chứa video gốc `.mp4` (*bắt buộc*).
* `--skip-keyframes`: Bỏ qua bước trích xuất keyframe nếu đã chạy trước đó.
* `--skip-asr`: Bỏ qua bước ASR nếu đã chạy trước đó.
* `--skip-ocr`: Bỏ qua bước OCR nếu đã chạy trước đó.

---

### C. Khởi động Web Server & Vào phòng thi
Sau khi nạp xong dữ liệu, khởi chạy Backend:
```cmd
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Mở trình duyệt Web tại: 👉 **`http://localhost:8000/frontend/`**

---

## ⌨️ 6. BẢNG PHÍM TẮT THẦN TỐC (KEYBOARD SHORTCUTS)

| Phím tắt | Thao tác | Mô tả chi tiết |
| :--- | :--- | :--- |
| **`Enter`** | **Tìm kiếm** | Thực thi tìm kiếm câu truy vấn đang gõ (trong ô KIS hoặc TRAKE). |
| **`Chuột giữa`** / **`[+]`** | **Chọn ảnh** | Thêm ngay khung hình vào Khay Nộp bài. |
| **`Alt + A`** | **Bật / Tắt Khay** | Ẩn/hiện thanh công cụ chọn ảnh bên phải. |
| **`Alt + R`** | **Tinh chỉnh (Refine)** | AI gom toàn bộ các góc quay cùng sự kiện lên hàng đầu (Rocchio Feedback). |
| **`Alt + S`** | **Lưu Query** | Lưu câu truy vấn hiện tại vào Gói Bài Thi. |
| **`Ctrl + S`** / **`Alt + P`** | **Gói Bài & Nén ZIP** | Mở Bảng Quản Lý & Nén `submission.zip` 1-click chuẩn 100% BTC. |
| **`Ctrl + Q`** | **Làm mới ô nhập** | Xóa nhanh câu query để gõ câu mới. |
| **`Ctrl + I`** | **Tìm kiếm OCR** | Mở ô tìm kiếm chữ viết xuất hiện trên video. |
| **`Ctrl + K`** | **Tìm kiếm ASR** | Mở ô tìm kiếm giọng nói / lời thoại âm thanh trong video. |
| **`Alt + C`** / **`Alt + X`** | **Xóa ảnh khay** | Làm trống Khay Nộp để làm câu tiếp theo. |
| **`Esc`** | **Đóng cửa sổ** | Đóng trình phát video hoặc các modal xem trước. |

---

## 📦 7. CẤU TRÚC THƯ MỤC DỰ ÁN (PROJECT STRUCTURE)

```
d:\code-c-a-Long/
├── backend/
│   ├── main.py                  # FastAPI Server, WebSocket /ws, RRF Hybrid Search Engine
│   ├── config.json              # File cấu hình Server, GPU Tensor & Thresholds
│   └── requirements.txt         # Danh sách thư viện Python
├── frontend/
│   ├── index.html               # Giao diện thi đấu Cyberpunk Dashboard
│   └── src/scripts/             # Toàn bộ script xử lý UI, WebSocket, Video Player, Submission
├── data_pipeline/
│   ├── run_master_offline_pipeline.py  # Master Runner tự động 5 bước Offline Indexing
│   ├── transnetv2_keyframes.py         # Trích xuất keyframe thích ứng + Lọc mờ Laplacian
│   ├── extract_asr_advanced.py         # Trích xuất ASR Faster-Whisper Large-v3-Turbo + VAD
│   ├── extract_ocr_advanced.py         # Trích xuất OCR PaddleOCR v4 + Tiền xử lý CLAHE
│   ├── merge_ocr_asr_metadata.py       # Đồng bộ và gộp Metadata OCR & ASR
│   ├── extract_features.py             # Trích xuất Vector Google SigLIP 2 Giant 1152d
│   └── pack_submission.py              # Đóng gói và kiểm tra tính hợp lệ file submission.zip
├── data-keyframes/              # Thư mục lưu keyframes trích xuất (.webp) và maps CSV
├── features.npy                 # Tensor đặc trưng vector (~166k x 1152d)
├── image_paths.npy              # Danh sách đường dẫn keyframe tương ứng
├── ocr_asr_metadata.json        # Cơ sở dữ liệu văn bản OCR & ASR
├── HUONG_DAN.md                 # Cẩm nang hướng dẫn thao tác thi đấu chi tiết
└── README.md                    # Tài liệu tổng quan kiến trúc và kỹ thuật hệ thống
```

---

## 🏆 8. CHIẾN THUẬT NỘP BÀI TỐI ƯU ĐIỂM SỐ (MRR & TOP RANK)

1. **Dạng bài KIS (`query-X-kis.csv`):**
   * Định dạng: `<video_name>,<frame_id>`.
   * Gõ mô tả ở tab **`KIS`** $\to$ Chọn **1 đến 3 frame chuẩn xác nhất** bằng mắt $\to$ Bấm **`Alt + S`**.
2. **Dạng bài Q&A (`query-X-qa.csv`):**
   * Định dạng: `<video_name>,<frame_id>,"<answer>"`.
   * Gõ mô tả ở tab **`KIS`** để tìm đúng đoạn video $\to$ Mở video lên xem khoảnh khắc để tìm câu trả lời $\to$ Chuyển khay nộp sang tab **`Q&A`** và điền đáp án $\to$ Bấm **`Alt + S`**.
3. **Dạng bài TRAKE (`query-X-trake.csv`):**
   * Định dạng: `<video_name>,<frame_1>,<frame_2>,...,<frame_N>`.
   * Chuyển sang tab **`TRAKE`** $\to$ Nhập Sự kiện 1 $\to$ Bấm `+ Thêm Sự Kiện Tiếp Theo` $\to$ Nhập Sự kiện 2, 3...
   * Hệ thống tự động phân tích và trả về **Top 20 video** chứa đầy đủ chuỗi sự kiện theo đúng thứ tự thời gian ($t(E_1) < t(E_2) < \dots < t(E_N)$) với tổng cộng $\sim 120\text{ frames}$, mỗi frame được gắn nhãn màu sắc rõ ràng (**Sự kiện 1**, **Sự kiện 2**, **Sự kiện 3**, **Sự kiện 4**...).
   * Chọn chuỗi frame đúng thứ tự thời gian trong cùng 1 video $\to$ Bấm **`Alt + S`**.
4. **Nén file nộp bài:**
   * Bấm **`Ctrl + S`** (hoặc nút **`Gói Bài Thi`**) $\to$ Bấm **`NÉN & TẠO FILE SUBMISSION.ZIP`** $\to$ Nộp trực tiếp file `D:\code-c-a-Long\submission.zip` lên cổng thi đấu của BTC!

---

## 📖 Hướng Dẫn Sử Dụng Chi Tiết
Xem toàn bộ hướng dẫn thao tác thi đấu tại: **[HUONG_DAN.md](HUONG_DAN.md)**

