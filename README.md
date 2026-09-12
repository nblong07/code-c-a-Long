# Multimodal Video Retrieval System

Lifelog video retrieval system for AIC 2026. Supports text, image, OCR and ASR queries against a corpus of keyframes indexed with FAISS ANN.

**Runtime:** Windows 11 local-only. No network dependencies during search.

---

## Architecture

| Component | Model / Technology | Specification |
| :--- | :--- | :--- |
| **Visual encoder** | `ViT-gopt-16-SigLIP2-384` (`webli`) | 1536d embedding, FP16, CUDA. FAISS IVF-SQ8 index. |
| **Query decomposer** | `SmartQueryDecomposer` | Rule-based Vi→En translation, temporal TRAKE parsing, synonym expansion. CPU-only, <2ms. |
| **ASR** | `Faster-Whisper large-v3-turbo` | CTranslate2 FP16. Silero VAD. Segment-level timestamps. |
| **OCR** | `Qwen2-VL-2B-Instruct` | FP16, SDPA attention. Text/signboard/license plate detection. |
| **Shot detection** | `TransNetV2` | Frame-level shot boundary. Adaptive sampling. Blur filter (Laplacian >= 70.0). |
| **Fusion** | `Reciprocal Rank Fusion (RRF)` | Visual FAISS + BM25 (OCR/ASR) score fusion. |

---

## Directory Structure

```
D:\code-c-a-Long/
├── backend/
│   ├── main.py                      # FastAPI server: WebSocket, FAISS search, RRF fusion
│   ├── smart_query_decomposer.py    # Query parsing, Vi->En translation, TRAKE decomposition
│   ├── config.json                  # Runtime configuration
│   ├── .env                         # Environment variable overrides
│   ├── requirements.txt             # Python dependencies
│   └── README.md
├── frontend/
│   ├── index.html                   # Main search UI and submission tray
│   ├── login.html                   # DRES session configuration
│   ├── scripts/                     # JavaScript modules
│   ├── styles/                      # CSS stylesheets
│   └── README.md
├── data_pipeline/
│   ├── transnetv2_keyframes.py      # Step 1: Shot-based keyframe extraction (TransNetV2)
│   ├── extract_asr_advanced.py      # Step 2: ASR transcription (Faster-Whisper large-v3-turbo)
│   ├── extract_ocr_qwen_vl.py       # Step 3: OCR extraction (Qwen2-VL-2B-Instruct)
│   ├── merge_ocr_asr_metadata.py    # Step 4: Merge OCR/ASR into ocr_asr_metadata.json
│   ├── extract_features.py          # Step 5: Visual feature extraction (SigLIP 2, 1536d FP16)
│   ├── build_faiss_index.py         # Step 6: Build FAISS IVF-SQ8 index
│   ├── pack_submission.py           # Pack and validate submission.zip
│   ├── benchmark_eval.py            # Recall@K, MRR, latency evaluation
│   ├── tune_rrf_weights.py          # Grid-search RRF weight optimization
│   └── README.md
├── data-keyframes/                  # Keyframe images (.webp) + timestamp _map.csv files
├── features.faiss                   # FAISS IVF-SQ8 index (173,921 vectors, 1536d)
├── features.npy                     # Feature matrix: float32 (173921, 1536)
├── image_paths.npy                  # Keyframe path list aligned to features.npy rows
├── ocr_results.jsonl                # Raw OCR records per keyframe
├── asr_results.jsonl                # Raw ASR segments per video
└── ocr_asr_metadata.json            # Merged OCR + ASR lookup table (loaded at server start)
```

---

## Hardware Configuration

| Resource | Spec | Allocation |
| :--- | :--- | :--- |
| CPU | AMD 7000 Series, 16 logical cores | 13-14 workers (85% cap via OPTIMAL_CPU_THREADS) |
| GPU | NVIDIA RTX 3050 Laptop, 6 GB VRAM | FP16, TF32, 88% memory cap (~5.28 GB). SigLIP 2 inference. |
| RAM | 16 GB DDR5 | BM25 index, mmap feature array, result cache |

---

## Setup and Run

```bash
conda activate video_ai
cd /d D:\code-c-a-Long
```

### Data pipeline (run once per new video batch)

```bash
# Step 1: Shot-based keyframe extraction
python data_pipeline/transnetv2_keyframes.py --input-folder "C:/video_test" --output-base "D:/code-c-a-Long/data-keyframes" --workers 13

# Step 2: ASR transcription
python data_pipeline/extract_asr_advanced.py --video-dir "C:/video_test"

# Step 3: OCR extraction
python data_pipeline/extract_ocr_qwen_vl.py --keyframes-dir "D:/code-c-a-Long/data-keyframes"

# Step 4: Merge OCR/ASR metadata
python data_pipeline/merge_ocr_asr_metadata.py

# Step 5: Extract visual features
python data_pipeline/extract_features.py --keyframes-dir "D:/code-c-a-Long/data-keyframes" --batch-size 24 --workers 12

# Step 6: Build FAISS IVF-SQ8 index
python data_pipeline/build_faiss_index.py --features "D:/code-c-a-Long/features.npy" --output "D:/code-c-a-Long/features.faiss"
```

### Start server

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

- Frontend: `http://localhost:8000/frontend/`
- Health check: `http://localhost:8000/health`

---

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Enter` | Submit search query |
| `Middle-click` / `[+]` | Add keyframe to submission tray |
| `Alt+A` | Toggle submission tray visibility |
| `Alt+R` | Rocchio relevance feedback refinement |
| `Alt+S` | Save query to session list |
| `Ctrl+S` / `Alt+P` | Pack and validate `submission.zip` |
| `Ctrl+Q` | Clear search input |
| `Ctrl+I` | Switch to OCR search tab |
| `Ctrl+K` | Switch to ASR search tab |
| `Alt+C` | Clear submission tray |
| `Esc` | Close modal or video player |
