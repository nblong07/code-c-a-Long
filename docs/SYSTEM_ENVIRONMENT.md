# Thông tin Hệ thống & Môi trường làm việc (System Environment Context)

File này lưu trữ thông tin về môi trường phần cứng, phần mềm và các thiết lập đặc thù của dự án trên máy của người dùng (user). **Tất cả các AI/Agent khi đọc file này cần tuân thủ tuyệt đối các ràng buộc bên dưới để tránh gây xung đột hệ thống.**

## 1. Thông tin Phần cứng (Hardware)
- **Hệ điều hành:** Windows
- **CPU/RAM:** 16GB System RAM
- **GPU:** NVIDIA với 6GB VRAM
- **Khả năng:** Chạy thoải mái các model AI, tối ưu hóa để không OOM với GPU 6GB.

## 2. Thông tin Phần mềm (Software & Environment)
- **Quản lý môi trường:** Miniconda
- **Phiên bản Python:** Python 3.11
- **Môi trường Conda hiện tại:** `video_ai`
- **Đường dẫn Python tuyệt đối (tham khảo):** `C:\Users\phatt\miniconda3\envs\video_ai\python.exe`
- **Đường dẫn thư mục dự án:** `D:\code-c-a-Long`

## 3. Các Thư viện Cốt lõi & Lưu ý Xung đột (CRITICAL WARNINGS)
*Môi trường này rất nhạy cảm với các bản cập nhật phiên bản, đặc biệt là hệ sinh thái HuggingFace và PyTorch.*

1. **HuggingFace Hub (`huggingface_hub`) & Tokenizers:**
   - **Bắt buộc:** `huggingface_hub < 1.0` (Khuyến nghị bản `0.36.2` hoặc `0.23.2`).
   - **Lý do:** Các thư viện `transformers`, `tokenizers`, và đặc biệt là bộ nạp Tokenizer của model `ViT-SO400M-14-SigLIP-384` qua `open_clip` sẽ ném lỗi crash backend nếu dùng `huggingface_hub >= 1.0`.
   - **Xung đột Gradio:** Phiên bản Gradio hiện tại (6.20.0) sẽ báo lỗi warning yêu cầu `huggingface_hub >= 1.2.0`. **Tuyệt đối phớt lờ cảnh báo của Gradio**, không được nâng cấp `huggingface_hub` lên bản mới vì Backend chính dùng FastAPI chứ không dùng Gradio. Nâng cấp sẽ làm hỏng chức năng Search.

2. **Numpy (`numpy`):**
   - **Bắt buộc:** `numpy < 2.0.0` (Khuyến nghị dòng 1.26.x).
   - **Lý do:** PyTorch offline search (Vector Search Matrix Multiplication) và một số module xử lý hình ảnh sẽ crash và văng lỗi `Numpy is not available` nếu cài bản `2.0.0` trở lên do không tương thích mã nhị phân.

3. **OpenCLIP (`open_clip_torch`) & Timm:**
   - **Bắt buộc:** Phải dùng phiên bản mới nhất hỗ trợ `ViT-SO400M-14-SigLIP-384`.

## 4. Đặc tả Dữ liệu & Database (Milvus & PyTorch Fallback)
- **Định dạng dữ liệu người dùng:** Thư mục ảnh Keyframes mới từ TransNetV2 (được nén dạng `*.webp`).
- **Số chiều Vector (Dimension):**
  - Model `ViT-SO400M-14-SigLIP-384` tạo ra vector **1152 chiều**. Mã nguồn đã được sửa để tự động nhận diện đúng số chiều này, không còn bị lỗi AssertionError nữa.
  - **Lệnh chuẩn để nạp dữ liệu:** `python data_pipeline/upload_database.py --root ./data-keyframes --build-index`

## 5. Danh sách thư viện đầy đủ (Frozen State)
Hệ thống đã tự động sao lưu toàn bộ các phiên bản thư viện hiện hành vào file `environment_frozen.txt` nằm ở thư mục gốc. Khi cần khôi phục, AI có thể tham chiếu file này.
