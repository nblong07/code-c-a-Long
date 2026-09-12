# Offline Data Pipeline

Six-step offline processing pipeline to prepare video data for the retrieval system. Each step is a standalone CLI script.

```bash
conda activate video_ai
cd /d D:\code-c-a-Long
```

---

## Model Specifications

| Step | Script | Model | Key Parameters | VRAM | Output |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `transnetv2_keyframes.py` | TransNetV2 | Window=100 frames; shot threshold>=0.5; Laplacian>=70.0; dHash Hamming<=5 | ~1.2 GB | `data-keyframes/*.webp`, `*_map.csv` |
| 2 | `extract_asr_advanced.py` | Faster-Whisper large-v3-turbo | CTranslate2 FP16; Silero VAD; no_speech_prob>0.65 filtered | ~2.5 GB | `asr_results.jsonl` |
| 3 | `extract_ocr_qwen_vl.py` | Qwen2-VL-2B-Instruct | 2.2B params, FP16, SDPA; max_new_tokens=128 | ~4.4 GB | `ocr_results.jsonl` |
| 4 | `merge_ocr_asr_metadata.py` | — | Bisect timestamp matching from `_map.csv` | ~0 MB | `ocr_asr_metadata.json` |
| 5 | `extract_features.py` | ViT-gopt-16-SigLIP2-384 (webli) | 1536d FP16; input 384x384; L2-norm; batch_size=24 | ~4.2 GB | `features.npy` (N x 1536), `image_paths.npy` |
| 6 | `build_faiss_index.py` | FAISS IVFScalarQuantizer | IVF-SQ8, Inner Product metric; nlist=2*sqrt(N) | 0 MB | `features.faiss` |

---

## Step 1: Keyframe Extraction

```bash
python data_pipeline/transnetv2_keyframes.py \
  --input-folder "C:/video_test" \
  --output-base "D:/code-c-a-Long/data-keyframes" \
  --workers 13
```

## Step 2: ASR Transcription

```bash
python data_pipeline/extract_asr_advanced.py \
  --video-dir "C:/video_test"
```

## Step 3: OCR Extraction

```bash
python data_pipeline/extract_ocr_qwen_vl.py \
  --keyframes-dir "D:/code-c-a-Long/data-keyframes"
```

## Step 4: Merge OCR/ASR Metadata

```bash
python data_pipeline/merge_ocr_asr_metadata.py
```

## Step 5: Extract Visual Features

```bash
python data_pipeline/extract_features.py \
  --keyframes-dir "D:/code-c-a-Long/data-keyframes" \
  --batch-size 24 \
  --workers 12
```

## Step 6: Build FAISS Index

```bash
python data_pipeline/build_faiss_index.py \
  --features "D:/code-c-a-Long/features.npy" \
  --output "D:/code-c-a-Long/features.faiss"
```

---

## Evaluation and Tuning

### Retrieval benchmark (Recall@K, MRR, latency P50/P95/P99)

```bash
python data_pipeline/benchmark_eval.py \
  --queries data_pipeline/validation_queries.json \
  --top-k 10 \
  --server http://localhost:8000
```

### RRF weight grid search

Grid over `w_visual in [1.5,1.75,2.0,2.25,2.5]`, `w_ocr in [0.8,0.95,1.1,1.2,1.35]`, `w_asr in [0.75,0.9,1.0,1.1,1.2]`. Optimizes MRR.

```bash
python data_pipeline/tune_rrf_weights.py \
  --queries data_pipeline/validation_queries.json \
  --top-k 10 \
  --server http://localhost:8000
```

### Pack submission

```bash
python data_pipeline/pack_submission.py \
  --project-root "D:/code-c-a-Long" \
  --zip-name "submission.zip"
```
