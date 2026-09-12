# Backend Search Service

FastAPI server providing REST and WebSocket interfaces for multimodal video retrieval.

**Stack:** Python 3.11, FastAPI, PyTorch 2.2 (CUDA 12.1), FAISS CPU, OpenCLIP.

---

## Features

- **Dense visual search:** SigLIP 2 text encoder encodes queries into 1536d FP16 vectors. FAISS IVF-SQ8 ANN search over 173,921 keyframes.
- **BM25 lexical search:** In-memory inverted index (unigram + bigram) over OCR (172,937 records) and ASR (847 videos). Latency <1ms.
- **RRF fusion:** Reciprocal Rank Fusion combines visual and text ranks. OCR/ASR channel weights auto-scale based on query content.
- **Query decomposer:** `SmartQueryDecomposer` — CPU-only (<2ms). Vi→En translation, synonym expansion, TRAKE stage splitting, OCR/ASR keyword detection.
- **Rocchio refinement:** Relevance feedback via `Alt+R`. Updates query vector toward selected keyframe embeddings.
- **Semantic result cache:** Cosine similarity cache (threshold 0.965, 256 entries). Returns cached results for near-duplicate queries in <0.1ms.
- **DRES proxy:** Backend-side CORS bypass for DRES login, submit, and evaluation list endpoints.
- **Submission manager:** Validate and pack KIS/QA/TRAKE CSV files into `submission.zip`.

---

## Start Server

```bash
conda activate video_ai
cd /d D:\code-c-a-Long
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

- Frontend: `http://localhost:8000/frontend/`
- Swagger docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

---

## Resource Usage (measured on RTX 3050 Laptop 6GB)

| Resource | At startup | During query |
| :--- | :--- | :--- |
| VRAM | ~3.5 GB | ~3.5-3.6 GB |
| System RAM | ~2.2 GB | ~2.5-2.8 GB |
| Query latency | — | 30-250ms (P50) |

---

## API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/health` | GET | Server status, CUDA info, vector and text index counts |
| `/keyframes/{path}` | GET | Serve keyframe image by relative path |
| `/videos/{name}` | GET | Serve video file by name (cached path lookup) |
| `/TextQuery` | POST | Text-to-vector search (REST) |
| `/ws` | WebSocket | Real-time search, pagination, Rocchio refinement |
| `/ws/filter_query` | WebSocket | Filter results by OCR or ASR keyword |
| `/ws/similarity_search` | WebSocket | Find visually similar frames from a selected keyframe |
| `/api/frame_metadata` | GET | OCR + ASR text for a specific frame |
| `/api/video_subtitles/{name}` | GET | ASR segment timeline for a video |
| `/api/video_keyframes/{name}` | GET | Keyframe list with timestamps for a video |
| `/api/dres/login` | POST | DRES login proxy (returns sessionId, evaluationID) |
| `/api/dres/submit` | POST | DRES submission proxy |
| `/api/dres/status` | POST | DRES connection check and evaluation list |
| `/api/submission/pack` | POST | Validate and zip submission files |
| `/api/submission/status` | GET | Count completed questions per task type |
| `/api/submission/clear` | POST | Clear submission directory |
