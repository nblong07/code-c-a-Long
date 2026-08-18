# Video Retrieval System — code-c-a-Long 🚀

Hệ thống tìm kiếm hình ảnh & khoảnh khắc video thông minh dựa trên mô tả ngữ nghĩa (Text-to-Video Retrieval), tối ưu hóa cho cuộc thi **AI City Challenge (AIC)**.

Dự án cung cấp một giải pháp end-to-end hiệu năng cao: từ khâu trích xuất khung hình tiêu biểu (Keyframe), mã hóa đặc trưng vector, lưu trữ tìm kiếm trên Cơ sở dữ liệu Vector cho đến giao diện người dùng tương tác thời gian thực, tích hợp gửi kết quả thi DRES trực tiếp.

> [!NOTE]
> **Tối ưu hóa cao cấp cho phần cứng:**
> - **Hệ điều hành:** Windows 11 (Pathlib an toàn, xử lý bất đồng bộ & đa tiến trình)
> - **Cấu hình phần cứng tối ưu:** Tối ưu hóa cho cấu hình **16 GB RAM**, GPU NVIDIA **6 GB VRAM** (hỗ trợ CUDA PyTorch, FP16 Autocast). Hoạt động mượt mà trên máy tính cá nhân.
> - **Bộ điều hướng tự động:** Dynamic Adaptive Query Router + Heuristics Frame Filter + Tree of Thoughts Agent + HippoRAG Memory System
> - **Môi trường chạy:** Python 3.11 / PyTorch 2.x CUDA

---

## 🏗️ Kiến Trúc Hệ Thống (System Architecture)

Hệ thống hoạt động theo mô hình **Client-Server** kết hợp giữa kết nối giao thức REST API truyền thống và WebSocket thời gian thực nhằm tối đa hóa tốc độ phản hồi.

```mermaid
graph TD
    subgraph Client [Frontend UI - HTML/JS/CSS]
        UI[Giao diện Tương tác] <--> WS_Client[WebSocket Client]
        UI <--> HTTP_Client[HTTP API Client]
        VJS[Video.js + HLS.js] -->|Phát Video Stream| UI
    end

    subgraph Backend [FastAPI Backend Service]
        HTTP_Client <-->|REST API| REST[FastAPI Endpoints]
        WS_Client <-->|WebSockets| WS_Server[WebSocket Server]
        REST & WS_Server --> VSS[Vector Search Service]
        VSS -->|Encode Text Query| CLIP[OpenCLIP ViT-SO400M-14 GPU]
        VSS -->|Dịch truy vấn| Trans[Google Translator]
        VSS -->|Xử lý mốc thời gian| Temp[Temporal Query Logic]
        VSS -->|Tối ưu hóa vector| Rocchio[Rocchio Relevance Feedback]
    end

    subgraph Database [Milvus Vector Database]
        VSS <-->|PyMilvus SDK| Milvus[Milvus Standalone]
        Milvus -->|Lưu trữ Vector Đặc Trưng| HNSW[HNSW Index]
    end

    subgraph Data_Files [Hệ thống Tệp tin]
        Video[Thư mục Video MP4] -->|get_keyframes.py| Keyframes[Keyframe WebP & CSV Maps]
        Keyframes -->|upload_database.py| Milvus
        Keyframes -.->|Phục vụ ảnh tĩnh| REST
        Video -.->|Phục vụ stream| REST
    end

    subgraph Contest_Server [Máy chủ Cuộc thi]
        UI -->|submit_dres.js| DRES[DRES Server]
    end
```

---

## 🛠️ Chi Tiết Công Nghệ & Công Cụ (Technologies & Tools)

Hệ thống được thiết kế đồng bộ từ các thư viện AI tiên tiến nhất cho đến các framework web nhẹ, giúp vận hành mượt mà trên môi trường máy cá nhân.

| Thành phần | Công nghệ / Thư viện | Vai trò & Đặc điểm |
| :--- | :--- | :--- |
| **Deep Learning** | `torch` >= 2.0.0, `torchvision` | Khung xử lý Tensor & chạy mô hình trên card đồ họa NVIDIA CUDA. |
| **CLIP Encoder** | `open_clip_torch` >= 2.24.0 | Cung cấp kiến trúc mô hình CLIP để ánh xạ ảnh và văn bản vào cùng không gian vector. |
| **Image Handling** | `Pillow` >= 9.0.0 | Thư viện xử lý ảnh, hỗ trợ nạp và lưu định dạng WebP tối ưu dung lượng. |
| **Computer Vision**| `opencv-python` >= 4.8.0 | Đọc luồng video, trích xuất khung hình và đo tỷ lệ khung hình. |
| **Vector DB Client**| `pymilvus` >= 2.4.0 | Kết nối và thực hiện truy vấn tìm kiếm Vector trên Milvus DB. |
| **Translation** | `deep-translator` | Tự động phát hiện và dịch câu truy vấn tiếng Việt sang tiếng Anh. |
| **Backend Web** | `fastapi` >= 0.110.0 | Framework Web bất đồng bộ (async), hiệu năng cao, tự động tạo tài liệu Swagger. |
| **ASGI Server** | `uvicorn` >= 0.28.0 | Máy chủ web trung gian chạy FastAPI. |
| **Web Server** | `nginx` (Alpine) | Đóng gói qua Docker để phục vụ static files frontend và proxy ngược các API. |
| **Containerization**| `Docker` & `Docker Compose` | Đóng gói cơ sở dữ liệu Milvus và toàn bộ stack ứng dụng để chạy môi trường biệt lập. |
| **Frontend Core** | HTML5, CSS3 Vanilla | Viết giao diện thuần không sử dụng framework cồng kềnh giúp tải trang cực nhanh. |
| **HLS Streaming** | `hls.js`, `video.js` 7.17.0 | Phát video trực tuyến chất lượng cao theo phân đoạn mà không cần tải toàn bộ file MP4. |
| **Vector DB** | `Milvus` v2.6.2 (Standalone) | Lưu trữ và tìm kiếm vector tương đồng trên quy mô hàng triệu bản ghi. |

---

## 🧠 Chi Tiết Mô Hình AI & Đáp Ứng Yêu Cầu Cuộc Thi (AI Models & Competition Alignment)

Hệ thống được thiết kế để giải quyết triệt để 3 dạng truy vấn của vòng sơ tuyển AIC 2026:

### 1. Truy vấn dạng 1: Textual KIS (Tìm kiếm chính xác theo văn bản)
- **Mô hình cốt lõi:** OpenCLIP `ViT-SO400M-14-SigLIP-384` (Google)
- **Đặc điểm:** Tự động nhận diện dimension (1152d), chạy với `torch.inference_mode()` và **FP16 Autocast** trên GPU 6GB VRAM.
- **Ý nghĩa:** Ánh xạ mô tả văn bản tự nhiên (ví dụ: "người đàn ông mặc áo đỏ") sang không gian vector để tìm chính xác khung hình ngữ nghĩa tương ứng với tốc độ cực nhanh.

### 2. Truy vấn dạng 2: Q&A (Hỏi-Đáp Visual & Audio)
- **Mô hình hỗ trợ:** `PaddleOCR` (nhận diện chữ viết trong video) & `Faster-Whisper` (nhận diện giọng nói) kết hợp **Tree of Thoughts (ToT) Agent**.
- **Ý nghĩa:** Khi giám khảo hỏi chi tiết cụ thể (vd: "Biển số xe là gì?", "Trên sân khấu có mấy người?"), hệ thống kết hợp thông tin trích xuất từ OCR/ASR (metadata) và sử dụng ToT Agent phân tích câu hỏi để đưa ra ngữ cảnh trả lời chính xác nhất, có thể dùng khay tìm kiếm chuyên biệt để truy vấn chữ.

### 3. Truy vấn dạng 3: TRAKE (Truy xuất và căn chỉnh sự kiện theo thời gian)
- **Thuật toán cốt lõi:** **Dynamic Adaptive Pipeline Router** và **Temporal Query Logic** (Tính toán `frame_diff` và Score Boosting).
- **Ý nghĩa:** Giải quyết bài toán tìm chuỗi sự kiện. Hệ thống cho phép nhập đa sự kiện (First Query, Next Query), sau đó tính toán khoảng cách thời gian giữa các khung hình (ví dụ < 1500 frame) để tăng điểm tương đồng, giúp căn chỉnh và tìm ra chính xác chuỗi hành động theo đúng trật tự thời gian.

### 4. Tối ưu Chỉ mục Vector HNSW (Hierarchical Navigable Small World)
Để tìm kiếm siêu tốc trên cơ sở dữ liệu Milvus, chúng tôi cấu hình chỉ mục đồ thị HNSW với các tham số tối ưu bộ nhớ RAM 16GB:
- **Metric Type:** `COSINE` (Khoảng cách Cosine tương đồng).
- **M (Max Connection):** `32` (Số liên kết tối đa của mỗi node đồ thị).
- **efConstruction:** `250` (Độ sâu tìm kiếm khi xây dựng chỉ mục).
- **nprobe:** `16` (Đảm bảo thời gian truy vấn dưới **50ms**).

---

## 📡 Dịch Vụ Backend & Các Đầu Cuối API (Backend Service & APIs)

Dịch vụ backend được triển khai tại file [backend/main.py](file:///D:/code-c-a-Long/backend/main.py) thông qua class [VectorSearchService](file:///D:/code-c-a-Long/backend/main.py#L134) quản lý vòng đời mô hình và kết nối database.

### Các Endpoints API Chính

| Đầu cuối (Endpoint) | Giao thức | Lớp Dữ Liệu Payload | Mô tả chức năng |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | Không | Kiểm tra sức khỏe hệ thống: trạng thái Milvus, thiết bị chạy (CPU/CUDA), tên mô hình AI. |
| `/TextQuery` | `POST` | [TextQueryRequest](file:///D:/code-c-a-Long/backend/main.py#L38) | Tìm kiếm ngữ nghĩa từ mô tả văn bản. Hỗ trợ Single Query hoặc Temporal Query. |
| `/RefineQuery` | `POST` | [RefineSearchRequest](file:///D:/code-c-a-Long/backend/main.py#L46) | Lọc và tinh chỉnh vector tìm kiếm bằng phản hồi tương tác Rocchio. |
| `/config` | `GET` | Không | Lấy thông tin cấu hình hiện tại của hệ thống từ file [backend/config.json](file:///D:/code-c-a-Long/backend/config.json). |
| `/ws` | `WebSocket`| JSON format | Kết nối thời gian thực phục vụ tìm kiếm ngữ nghĩa `/ws` và phản hồi tương tác nhanh. |
| `/ws/similarity_search`| `WebSocket`| JSON format | WebSocket phục vụ truy vấn tìm kiếm các khung hình tương đồng với một khung hình chỉ định. |

### Các Thuật Toán & Logic Tối Ưu Trên Backend

#### A. Tìm kiếm Đa mốc Thời gian (Temporal Query Logic)
Khi người dùng nhập cả 2 mô tả sự kiện (Cảnh 1 xảy ra trước, Cảnh 2 xảy ra sau), phương thức [process_temporal_query](file:///D:/code-c-a-Long/backend/main.py#L308) sẽ thực hiện:
1. Mã hóa song song cả 2 câu truy vấn bằng OpenCLIP và truy vấn Milvus lấy top kết quả tương ứng.
2. Hàm xử lý logic [_process_temporal_relationships](file:///D:/code-c-a-Long/backend/main.py#L337) sử dụng PyTorch Tensors trên GPU để tính toán chênh lệch khung hình (`frame_diff`) giữa kết quả của hai cảnh.
3. Nếu hai khung hình nằm trong cùng một video (`video_id`) và Cảnh 2 xuất hiện sau Cảnh 1 trong phạm vi **1500 khung hình** (tương đương khoảng 60 giây ở 25fps), hệ thống sẽ tăng điểm số tương đồng (Score Boosting) dựa trên công thức độ gần thời gian:
   $$\text{Score Boost} = \text{Score}_{\text{Cảnh 2}} \times \frac{1500 - \text{Frame Diff}}{1500}$$
4. Kết quả sau đó được sắp xếp lại (Reranking) để đưa các khoảnh khắc khớp chuỗi thời gian lên đầu.

#### B. Phản hồi Tương tác Người dùng (Rocchio Relevance Feedback)
Sử dụng phương thức [compute_rocchio_vector](file:///D:/code-c-a-Long/backend/main.py#L285) để tinh chỉnh vector truy vấn $q_{new}$ dựa trên các ảnh liên quan (Relevant) và không liên quan (Non-relevant) do người dùng đánh dấu trên UI:
$$q_{new} = \alpha \cdot q_0 + \frac{\beta}{|R|} \sum_{v \in R} v - \frac{\gamma}{|N|} \sum_{v \in N} v$$
Trong đó:
- $q_0$ là vector truy vấn ban đầu.
- $R$ là tập hợp các vector khung hình được đánh dấu là liên quan (Relevant).
- $N$ là tập hợp các vector khung hình không liên quan (Non-relevant).
- Các trọng số mặc định: $\alpha = 1.0$, $\beta = 0.75$, $\gamma = 0.15$. Vector $q_{new}$ sau đó được chuẩn hóa về độ dài đơn vị trước khi thực hiện tìm kiếm lại.

#### C. Dịch Thuật Tự Động (Query Translation)
Để hỗ trợ người dùng nhập truy vấn bằng tiếng Việt, hàm [translate_query](file:///D:/code-c-a-Long/backend/main.py#L200) tự động phát hiện ký tự UTF-8 (tiếng Việt có dấu) và gọi thư viện dịch thuật để chuyển đổi sang tiếng Anh trước khi đưa vào OpenCLIP Text Encoder.

---

## 💻 Giao Diện Người Dùng Frontend (Frontend Application)

Frontend của dự án nằm tại thư mục [frontend](file:///D:/code-c-a-Long/frontend) được thiết kế theo phong cách tối giản, trực quan và tối ưu hóa cho phản xạ nhanh của đấu thủ trong phòng thi.

### 1. Cấu trúc Giao diện & Layout CSS
Giao diện được phân chia khoa học bằng CSS Grid & Flexbox trong các tệp tin phong phú tại `src/styles/`:
- [layout.css](file:///D:/code-c-a-Long/frontend/src/styles/layout.css): Định dạng tổng thể, chia cột Left Panel (chức năng tìm kiếm) và Right Panel (khu vực hiển thị kết quả).
- [video_frame.css](file:///D:/code-c-a-Long/frontend/src/styles/video_frame.css): Hiển thị lưới các khung hình ảnh keyframe kết quả, hỗ trợ bo góc, hiệu ứng hover và hiệu ứng chọn trạng thái Rocchio (đỏ/xanh).
- [show_video.css](file:///D:/code-c-a-Long/frontend/src/styles/show_video.css): Thiết kế trình phát video và thanh filmstrip xem trước các khung hình lân cận.
- [export_area.css](file:///D:/code-c-a-Long/frontend/src/styles/export_area.css) & [preview.css](file:///D:/code-c-a-Long/frontend/src/styles/preview.css): Quản lý khay chứa kết quả chờ nộp bài hoặc xuất file.

### 2. Các Script Điều Khiển Chính (JavaScript)
- [web_socket.js](file:///D:/code-c-a-Long/frontend/src/scripts/web_socket.js): Thiết lập và quản lý kết nối WebSocket đến Backend, xử lý gửi/nhận dữ liệu tìm kiếm và phản hồi Rocchio thời gian thực.
- [show_videoframe.js](file:///D:/code-c-a-Long/frontend/src/scripts/show_videoframe.js): Nhận danh sách kết quả, dựng thẻ HTML động, hiển thị độ tương đồng và quản lý các sự kiện click chuột, phím tắt.
- [show_video.js](file:///D:/code-c-a-Long/frontend/src/scripts/show_video.js): Tích hợp thư viện `video.js` và `hls.js` để phát stream phân đoạn video trực tiếp khi click đúp vào keyframe. Đồng thời hiển thị dải filmstrip (các frame trước và sau keyframe hiện tại) giúp người dùng định vị chính xác giây cần nộp.
- [submit_dres.js](file:///D:/code-c-a-Long/frontend/src/scripts/submit_dres.js): Kết nối API tới server DRES để gửi bài dự thi (Submit) trực tiếp từ giao diện.
- [queries_history.js](file:///D:/code-c-a-Long/frontend/src/scripts/queries_history.js): Quản lý lưu trữ lịch sử các câu truy vấn đã thực hiện vào `localStorage` của trình duyệt.
- [object_list.js](file:///D:/code-c-a-Long/frontend/src/scripts/object_list.js): Cung cấp danh sách hàng trăm đối tượng định sẵn (COCO Classes) để người dùng tích chọn nhanh nhằm lọc kết quả.

---

## 🗄️ Cơ Sở Dữ Liệu & Quy Trình Xử Lý Dữ Liệu (Database & Pipelines)

Dữ liệu của hệ thống được quản lý thông qua hai giai đoạn chính bằng các script Python chuyên dụng:

```
Thư mục Video (.mp4)
      │
      ▼  [Chạy offline] data_pipeline/get_keyframes.py
Trích xuất Khung hình WebP + Tệp tin CSV Ánh xạ (Frame ID -> Giây)
      │
      ▼  [Chạy offline] data_pipeline/upload_database.py
Mã hóa CLIP & Tải lên Milvus DB (HNSW Index Cosine)
```

### 1. Trích xuất Khung hình đại diện ([get_keyframes.py](file:///D:/code-c-a-Long/data_pipeline/get_keyframes.py))
- Đọc video tuần tự bằng OpenCV. Để tăng tốc độ xử lý, script sử dụng tham số `--skip-frames` (mặc định bỏ qua 5 frame, chỉ đọc frame thứ 6).
- Sử dụng hàm [encode_batch](file:///D:/code-c-a-Long/data_pipeline/get_keyframes.py#L29) thực hiện xử lý song song đa luồng (`ThreadPoolExecutor`) trên CPU để tiền xử lý ảnh (Resize, Normalize) và gom batch đưa lên GPU để OpenCLIP mã hóa.
- Đo khoảng cách Cosine giữa các frame liên tiếp. Nếu độ tương đồng **< 0.93** (tức cảnh thay đổi rõ rệt), khung hình đó được xác định là Keyframe đại diện và lưu xuống đĩa cứng dưới dạng ảnh WebP nén (Resize 0.5x, chất lượng 80% để tiết kiệm bộ nhớ) thông qua hàm [save_image_webp](file:///D:/code-c-a-Long/data_pipeline/get_keyframes.py#L47).
- Xuất ra file ánh xạ CSV lưu thông tin Frame ID và mốc thời gian tương ứng.

### 2. Tải dữ liệu lên Vector Database ([upload_database.py](file:///D:/code-c-a-Long/data_pipeline/upload_database.py))
- Kết nối tới Milvus Database qua hàm [ensure_collection](file:///D:/code-c-a-Long/data_pipeline/upload_database.py#L27) để khởi tạo Collection với lược đồ (Schema) gồm: `id` (Primary Key), `filepath` (Đường dẫn ảnh), `embedding` (Vector tự động số chiều), `video_id` (Tên video) và `frame_id` (Số thứ tự khung hình).
- Đọc các ảnh WebP, sinh vector đặc trưng từ OpenCLIP (tự động nhận diện dimension).
- **Quan trọng:** Tiến hành chuẩn hóa L2 (`F.normalize`) đưa vector về độ dài đơn vị trước khi insert. Việc chuẩn hóa này đảm bảo khoảng cách IP (Inner Product) trên Milvus tương đương chính xác 100% với tính toán khoảng cách Cosine Similarity.
- Gọi hàm [process_and_upload](file:///D:/code-c-a-Long/data_pipeline/upload_database.py#L86) thực hiện tải dữ liệu theo Batch lên Milvus và tự động xây dựng chỉ mục HNSW để sẵn sàng tìm kiếm.

### 3. Các Công cụ Hỗ trợ Khác
- [extract_features.py](file:///D:/code-c-a-Long/data_pipeline/extract_features.py): Trích xuất vector đặc trưng OCR, ASR, CLIP.

---

## ⚡ Hướng Dẫn Cài Đặt & Khởi Chạy Nhanh (Quick Start)

### 1. Chuẩn bị Môi trường Python
Chạy script cài đặt tự động trên Windows 11 để tạo thư mục và cài đặt đầy đủ các gói phụ thuộc:
```cmd
setup.bat
```
Hoặc trên Linux/macOS:
```bash
bash setup.sh
```

### 2. Khởi động Milvus Database (Docker)
Yêu cầu đã cài đặt và đang chạy **Docker Desktop** trên máy:
```cmd
cd data_pipeline
docker compose up -d
```
Kiểm tra trạng thái container bằng lệnh `docker compose ps`.

### 3. Pipeline Xử lý Dữ liệu
3. **Trích xuất thông tin (Tuỳ chọn nâng cao cho OCR & ASR):**
   ```cmd
   python run_advanced_ocr.py
   python run_advanced_asr.py
   python data_pipeline/extract_features.py 2
   ```
   Trích xuất khung hình từ thư mục video:
   ```cmd
   python data_pipeline/get_keyframes.py --input-folder "D:/path/to/videos" --output-base "./data-keyframes"
   ```
Mã hóa và tải lên Milvus DB:
```cmd
python data_pipeline/upload_database.py --root "./data-keyframes" --build-index
```

### 4. Chạy dịch vụ Backend FastAPI
Khởi động backend server:
```cmd
python backend/main.py
```
Backend sẽ lắng nghe tại cổng `http://localhost:8000`. Tài liệu API Swagger có thể xem trực tiếp tại `http://localhost:8000/docs`.

### 5. Mở Frontend UI
Mở file [frontend/index.html](file:///D:/code-c-a-Long/frontend/index.html) bằng trình duyệt web của bạn, hoặc phục vụ qua Python HTTP Server để tránh lỗi CORS cục bộ:
```cmd
python -m http.server 8007 --directory frontend
```
Sau đó truy cập địa chỉ **`http://localhost:8007`** để bắt đầu trải nghiệm hệ thống tìm kiếm video thông minh!
