# 📖 HƯỚNG DẪN CHI TIẾT TỪ A ĐẾN Z DỰ ÁN VIDEO RETRIEVAL SYSTEM
## Code-c-a-Long — Tối Ưu Cho Windows 11 (RAM 16GB + NVIDIA 6GB GPU)

> **Công nghệ sử dụng:** PyTorch (CUDA GPU), OpenCLIP (`ViT-SO400M-14-SigLIP-384`), Milvus Vector Database (Docker), FastAPI, WebSocket, PaddleOCR (v4), Faster-Whisper (Large-v3).

---

## 📌 QUY TRÌNH CHẠY HỆ THỐNG CHUẨN (TỪ A ĐẾN Z)
Dưới đây là quy trình chuẩn xác, đã được tinh chỉnh chống lỗi 100% để bạn chạy từ dữ liệu video thô cho đến khi có thể tìm kiếm trên trình duyệt.

### BƯỚC 0: TẢI VÀ CÀI ĐẶT MÔI TRƯỜNG (DÀNH CHO NGƯỜI MỚI)
Để hệ thống có thể chạy được, bạn cần chuẩn bị môi trường Python và Docker. Nếu bạn chưa biết gì, hãy làm theo từng bước sau:

1. **Cài đặt Miniconda (Trình quản lý Python):** 
   - Truy cập [trang chủ Miniconda](https://docs.conda.io/en/latest/miniconda.html) và tải bản cài đặt cho Windows.
   - Cài đặt bình thường (cứ ấn Next liên tục).
2. **Cài đặt Docker Desktop (Chạy Cơ sở dữ liệu):** 
   - Tải [Docker Desktop](https://www.docker.com/products/docker-desktop) và cài đặt.
   - Mở Docker Desktop lên và để nó chạy ngầm.
3. Mở **Anaconda Prompt (Miniconda3)** bằng cách tìm kiếm trong menu Start của Windows (chuột phải chọn Run as Administrator nếu có thể).
4. Tạo môi trường ảo (giúp cài đặt gọn gàng, không bị lỗi máy):
   ```cmd
   conda create -n video_ai python=3.11 -y
   ```
5. Kích hoạt môi trường vừa tạo:
   ```cmd
   conda activate video_ai
   ```
6. Di chuyển vào thư mục dự án (Nếu bạn lưu thư mục code ở nơi khác, hãy thay đổi đường dẫn `D:\code-c-a-Long` cho phù hợp):
   ```cmd
   cd /d D:\code-c-a-Long
   ```
7. Cài đặt toàn bộ thư viện cần thiết:
   ```cmd
   pip install -r backend/requirements.txt
   ```

---

### BƯỚC 1: TRÍCH XUẤT KHUNG HÌNH (KEYFRAMES) TỪ VIDEO
Sử dụng AI TransNetV2 để tự động cắt các phân cảnh quan trọng từ video, loại bỏ rác/quảng cáo.
1. Gom tất cả video (mp4) của bạn vào một thư mục, ví dụ: `D:/Videos_AI`.
2. Chạy lệnh trích xuất:
   ```cmd
   python data_pipeline/transnetv2_keyframes.py --input-folder "D:/Videos_AI" --output-base "./data-keyframes"
   ```
   > **Lưu ý:** AI sẽ quét video và tự động lưu các khung hình ở định dạng nén `.webp` vào thư mục `./data-keyframes` trong dự án của bạn.

---

### BƯỚC 2: TRÍCH XUẤT SIÊU DỮ LIỆU BỔ SUNG (OCR & ASR)
Đọc chữ từ biển số/biển báo (OCR) và nghe âm thanh video (ASR).
1. Nhận diện chữ viết tiếng Việt bằng VietOCR + PaddleOCR (Đa luồng/siêu tốc):
   ```cmd
   python data_pipeline/extract_ocr_advanced.py
   ```
2. Nhận diện giọng nói bằng Faster-Whisper:
   *(Hệ thống đã được kết nối tự động với ổ `C:\video_test` của bạn).*
   ```cmd
   python data_pipeline/extract_asr_advanced.py
   ```
3. Tổng hợp thành siêu dữ liệu để Backend sử dụng:
   ```cmd
   python data_pipeline/extract_features.py 2
   ```
   > Sẽ tạo ra file `ocr_asr_metadata.json` ở ngay thư mục gốc.

---

### BƯỚC 3: KHỞI ĐỘNG CƠ SỞ DỮ LIỆU VECTOR (MILVUS)
1. Bật cơ sở dữ liệu Milvus trong Docker:
   ```cmd
   cd data_pipeline
   docker compose up -d
   ```
2. Trở lại thư mục gốc:
   ```cmd
   cd ..
   ```

---

### BƯỚC 4: NẠP DỮ LIỆU LÊN DATABASE VÀ TẠO CHỈ MỤC (HNSW INDEX)
Mã hóa các khung hình `.webp` thành các vector 1152 chiều bằng OpenCLIP (ViT-SO400M-14-SigLIP-384) và đẩy lên Milvus.
Chạy lệnh sau:
```cmd
python data_pipeline/upload_database.py --root "./data-keyframes" --dimension 1152 --build-index --batch-size 16
```
> **Đảm bảo an toàn:** Đã cài sẵn `--dimension 1152` và `--batch-size 16` để chống lỗi kích thước (Dimension Mismatch) và chống tràn bộ nhớ (Out Of Memory) cho GPU 6GB của bạn.

---

### BƯỚC 5: KHỞI ĐỘNG BACKEND SERVICE (AI SERVER)
Khởi động máy chủ backend để nhận truy vấn và gọi AI xử lý.
```cmd
python backend/main.py
```
> **Kiểm tra thành công:** Terminal sẽ báo `⚡ Running service on device: cuda` và `✅ Đã nạp bản ghi OCR` (Nếu Bước 2 thành công). 

---

### BƯỚC 6: BẬT GIAO DIỆN FRONTEND VÀ TÌM KIẾM
Để giao diện web gọi API mượt mà không bị lỗi CORS chặn, hãy mở một cửa sổ Terminal mới (không tắt terminal backend), và chạy một HTTP Server nhỏ:
```cmd
conda activate video_ai
cd /d D:\code-c-a-Long
python -m http.server 8007 --directory frontend
```

Bây giờ, hãy mở trình duyệt web (Chrome/Edge) và truy cập:
👉 **http://localhost:8007**

*Bạn đã có thể gõ câu lệnh tiếng Việt hoặc tiếng Anh để tìm kiếm bằng AI!*

---

### BƯỚC 7: CÁCH CHẠY LẠI HỆ THỐNG VÀO NGÀY HÔM SAU
Nếu bạn đã hoàn thành trích xuất và nạp dữ liệu lên Milvus (Bước 1 đến Bước 4) từ hôm trước, thì vào lần mở máy tiếp theo bạn **KHÔNG CẦN** làm lại từ đầu. Chỉ cần làm các thao tác ngắn gọn sau để bật hệ thống:

1. **Bật Database (Docker):**
   - Mở phần mềm **Docker Desktop** và đợi phần mềm khởi động xong.
   - Thường thì Milvus sẽ tự chạy ngầm cùng Docker. Nếu không, bạn mở Anaconda Prompt, gõ `cd /d D:\code-c-a-Long\data_pipeline` và chạy lệnh `docker compose up -d`.
2. **Bật Backend (Terminal 1):**
   Mở Anaconda Prompt và gõ lần lượt các lệnh:
   ```cmd
   conda activate video_ai
   cd /d D:\code-c-a-Long
   python backend/main.py
   ```
3. **Bật Frontend UI (Terminal 2):**
   Để nguyên cửa sổ trên, mở thêm một cửa sổ Anaconda Prompt thứ 2 và gõ:
   ```cmd
   conda activate video_ai
   cd /d D:\code-c-a-Long
   python -m http.server 8007 --directory frontend
   ```
4. **Bắt đầu tìm kiếm:**
   Mở trình duyệt web và truy cập địa chỉ **http://localhost:8007** là hệ thống của bạn đã sẵn sàng!

---

## 🛠️ XỬ LÝ SỰ CỐ NHANH (TROUBLESHOOTING)
- **Lỗi `ModuleNotFoundError: No module named 'tensorflow'` khi chạy Bước 1:** Môi trường chưa cài TensorFlow. Gõ lệnh `pip install tensorflow` rồi chạy lại Bước 1.
- **Lỗi Protobuf khi chạy Bước 2 (OCR):** Do TensorFlow vô tình làm lệch phiên bản protobuf của PaddleOCR. Chạy lệnh: `pip install protobuf==3.20.2` để sửa.
- **Lỗi Milvus / Connection Refused ở Bước 4 hoặc Bước 5:** Bạn quên bật Docker Desktop hoặc Docker chưa chạy `docker compose up -d` ở Bước 3.
- **Hết bộ nhớ GPU (CUDA OOM):** Đảm bảo bạn không mở nhiều tab Chrome (ngốn VRAM) hoặc phần mềm khác dùng GPU trong lúc AI đang mã hóa dữ liệu. Batch size đã được chỉnh an toàn ở mức 16.

Chúc bạn sử dụng hệ thống thành công và bảo mật tuyệt đối! 🚀
