
# Vector Search Service Backend 🚀

FastAPI backend service cho hệ thống tìm kiếm vector (Video Retrieval System), tích hợp mô hình OpenCLIP `ViT-L-14` và cơ sở dữ liệu vector Milvus.

Tối ưu hóa cho môi trường: **Windows 11, RAM 16GB, GPU NVIDIA 6GB VRAM (PyTorch CUDA)**.

## ✨ Tính năng chính

- **OpenCLIP `ViT-SO400M-14-SigLIP-384` (`webli`)**: Trích xuất embedding 1152 chiều chất lượng cao SOTA, nhận diện ngữ nghĩa siêu chuẩn xác.
- **Cross-Lingual Dual-Embedding Blending**: Tự động nhận diện tiếng Việt và dung hợp song ngữ (`0.45 * vi + 0.55 * en`) với bộ từ điển đồng nghĩa chuyên sâu.
- **BM25 Inverted Index Engine**: Tìm kiếm OCR ($17.223$ bản ghi) và ASR ($137.321$ bản ghi) trên RAM CPU với độ trễ $<2\text{ms}$ và **0 MB VRAM**.
- **TRAKE Temporal Query Logic**: Quy hoạch động chuỗi thời gian GPU Tensor Dynamic Programming ($<35\text{ms}$).
- **Rocchio Relevance Feedback**: Phản hồi tương tác tinh chỉnh vector tìm kiếm theo các keyframe đã chọn.
- **VRAM Safety Guard**: Tự động giải phóng cache bộ nhớ đệm GPU chống tràn VRAM trên RTX 3050 6GB.
- **Real-time WebSocket & REST API**: Hỗ trợ endpoint `/TextQuery` và WebSocket `/ws`.
- **Cấu hình qua `config.json`**: Dễ dàng tùy chỉnh host, port, collection name, limit.

## 🛠️ Cài đặt & Khởi chạy

### 1. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### 2. Cấu hình (`config.json`)

Mẫu file `config.json`:
```json
{
  "clip_model_name": "ViT-SO400M-14-SigLIP-384",
  "clip_pretrained": "webli",
  "device": "cuda",
  "milvus_host": "localhost",
  "milvus_port": 19530,
  "collection_name": "AIC25_fullbatch1",
  "keyframes_dir": "./data-keyframes"
}
```

### 3. Khởi chạy Server

```bash
python main.py
```
Server sẽ lắng nghe tại: `http://localhost:8000` (Docs Swagger UI tại `http://localhost:8000/docs`).

## 📡 Các API chính

| Endpoint | Phương thức | Mô tả |
| --- | --- | --- |
| `/health` | `GET` | Kiểm tra trạng thái kết nối Milvus & Model |
| `/TextQuery` | `POST` | Truy vấn Text-to-Video (Hỗ trợ 1 hoặc 2 query thời gian) |
| `/ws` | `WebSocket` | Kết nối thời gian thực |
| `/config` | `GET` | Lấy thông tin cấu hình hiện tại |

Xem hướng dẫn sử dụng toàn bộ hệ thống tại [HUONG_DAN.md](file:///D:/code-c-a-Long/HUONG_DAN.md).

## Temporal Query Logic

The service supports temporal queries where:

1. First query finds initial matches
2. Second query finds subsequent events
3. Results are reranked based on temporal proximity
4. Frame difference threshold: 1500 frames
5. Score boosting based on temporal closeness

## Development

### Running in Development Mode

```bash
uvicorn main:app --reload --log-level debug
```

### Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test text query
curl -X POST http://localhost:8000/TextQuery \
  -H "Content-Type: application/json" \
  -d '{"First_query": "person walking"}'
```

## Troubleshooting

### Common Issues

1. **CUDA not available**: Service automatically falls back to CPU
2. **Milvus connection failed**: Check host/port configuration
3. **Model loading errors**: Ensure sufficient disk space and memory

### Logs

Check logs for detailed error information:

```bash
# Service logs include execution times and error details
# Set LOG_LEVEL=DEBUG for verbose logging
```

## License

This project is configured for easy deployment and maintenance in production environments.
