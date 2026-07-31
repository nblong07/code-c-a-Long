#!/usr/bin/env python3
"""
Milvus Indexer & Uploader — Optimized for Windows 11 (16GB RAM + NVIDIA 6GB GPU)
=============================================================================
Reads extracted keyframe WEBP images, encodes them into 512-d CLIP vectors,
normalizes embeddings, and uploads them to Milvus Vector Database with HNSW index.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Tuple

import torch
import torch.nn.functional as F
from tqdm import tqdm
from PIL import Image

from pymilvus import (
    connections, utility, Collection, CollectionSchema,
    FieldSchema, DataType
)
import open_clip


def ensure_collection(
    collection_name: str,
    dimension: int,
    milvus_host: str,
    milvus_port: str,
    recreate: bool,
    field_names=("id", "filepath", "embedding", "video_id", "frame_id"),
):
    """Ensure Milvus collection exists with proper schema"""
    id_f, path_f, emb_f, vid_f, frame_f = field_names

    connections.connect(alias="default", host=milvus_host, port=milvus_port)

    if recreate and utility.has_collection(collection_name):
        print(f"⚠️ Dropping existing collection: {collection_name}")
        utility.drop_collection(collection_name)

    if not utility.has_collection(collection_name):
        print(f"✨ Creating collection '{collection_name}' (dimension: {dimension})...")
        schema = CollectionSchema(
            fields=[
                FieldSchema(name=id_f, dtype=DataType.INT64, is_primary=True, auto_id=False),
                FieldSchema(name=path_f, dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name=emb_f, dtype=DataType.FLOAT_VECTOR, dim=dimension),
                FieldSchema(name=vid_f, dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name=frame_f, dtype=DataType.INT64),
            ],
            description="Keyframe embeddings (OpenCLIP) for video retrieval",
        )
        Collection(name=collection_name, schema=schema)
        print(f"✅ Collection '{collection_name}' created.")
    else:
        print(f"ℹ️ Collection '{collection_name}' already exists.")


def discover_images(root: Path, glob_pat: str, start_index: int) -> List[Path]:
    """Find all matching keyframe images relative to root folder"""
    paths = sorted(root.glob(glob_pat))
    if start_index > 0:
        paths = paths[start_index:]
    return paths


def detect_model_dim(model, device: torch.device) -> int:
    """Detect output embedding dimension for a loaded CLIP model"""
    dim = getattr(model, "embed_dim", None)
    if dim is None and hasattr(model, "visual") and hasattr(model.visual, "output_dim"):
        dim = model.visual.output_dim
    if dim is None:
        dummy = torch.zeros(1, 3, 224, 224, device=device)
        with torch.no_grad():
            out = model.encode_image(dummy)
        dim = out.shape[-1]
    return int(dim)


def process_and_upload(
    indexed_paths: List[Tuple[int, Path]],
    model,
    preprocess,
    device: torch.device,
    milvus_host: str,
    milvus_port: str,
    collection_name: str,
    batch_size: int,
    flush_interval: int,
    field_names=("id", "filepath", "embedding", "video_id", "frame_id"),
):
    """Encodes images on PyTorch device and inserts into Milvus in batches"""
    id_f, path_f, emb_f, vid_f, frame_f = field_names

    connections.connect(alias="default", host=milvus_host, port=milvus_port)
    collection = Collection(name=collection_name)

    buffer = {"ids": [], "paths": [], "vids": [], "frames": [], "images": []}
    since_flush = 0
    total = len(indexed_paths)

    pbar = tqdm(total=total, desc="Encoding & Uploading to Milvus")

    for _id, path in indexed_paths:
        try:
            img = Image.open(path).convert("RGB")
            tensor_img = preprocess(img)
        except Exception as e:
            print(f"⚠️ Failed to open {path}: {e}")
            pbar.update(1)
            continue

        buffer["ids"].append(_id)
        buffer["paths"].append(str(path))

        # Infer video ID from parent directory structure
        # Expected pattern: root/<video_id>/keyframes/keyframe_<fid>.webp
        vid_name = path.parent.parent.name if path.parent.name == "keyframes" else path.parent.name
        buffer["vids"].append(vid_name)

        try:
            fid = int(path.stem.replace("keyframe_", ""))
        except Exception:
            try:
                fid = int(path.stem.split("_")[-1])
            except Exception:
                fid = _id
        buffer["frames"].append(fid)
        buffer["images"].append(tensor_img)

        if len(buffer["images"]) >= batch_size:
            _flush_batch(collection, buffer, model, device, id_f, path_f, emb_f, vid_f, frame_f)
            since_flush += len(buffer["ids"])
            pbar.update(len(buffer["ids"]))
            buffer = {"ids": [], "paths": [], "vids": [], "frames": [], "images": []}

            if since_flush >= flush_interval:
                collection.flush()
                since_flush = 0

    # Remaining buffer flush
    if buffer["images"]:
        _flush_batch(collection, buffer, model, device, id_f, path_f, emb_f, vid_f, frame_f)
        pbar.update(len(buffer["ids"]))
        collection.flush()

    pbar.close()
    print("✅ All keyframes processed and inserted into Milvus.")


def _flush_batch(collection, buffer, model, device, id_f, path_f, emb_f, vid_f, frame_f):
    """Encode images, normalize vectors, and insert into Milvus"""
    if not buffer["images"]:
        return

    images_tensor = torch.stack(buffer["images"]).to(device, non_blocking=True)

    with torch.inference_mode():
        if device.type == "cuda":
            with torch.amp.autocast(device_type="cuda"):
                if hasattr(model, "encode_image"):
                    embs = model.encode_image(images_tensor)
                else:
                    embs = model(images_tensor)
        else:
            if hasattr(model, "encode_image"):
                embs = model.encode_image(images_tensor)
            else:
                embs = model(images_tensor)

        # Normalize embeddings to unit length for accurate Cosine similarity search
        embs = F.normalize(embs.float(), p=2, dim=-1).cpu().numpy().tolist()

    try:
        collection.insert(
            [
                buffer["ids"],
                buffer["paths"],
                embs,
                buffer["vids"],
                buffer["frames"],
            ]
        )
    except Exception as e:
        print(f"❌ Milvus Insert Error: {e}")


def build_index_and_load(collection_name: str, milvus_host: str, milvus_port: str, field_name="embedding"):
    """Build HNSW index on embeddings field and load collection into RAM"""
    connections.connect(alias="default", host=milvus_host, port=milvus_port)
    collection = Collection(name=collection_name)

    print("🔄 Flushing collection before indexing...")
    collection.flush()

    has_index = any(idx.field_name == field_name for idx in collection.indexes)
    if not has_index:
        print("🔨 Building HNSW vector index (M=16, efConstruction=200)...")
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 200}
        }
        collection.create_index(field_name, index_params)
        print("✅ HNSW Index created successfully.")
    else:
        print("ℹ️ Index already exists; skipping build.")

    print("⚡ Loading collection into Milvus memory for query serving...")
    collection.load()
    print("🚀 Vector Database ready for fast queries!")


def parse_args():
    p = argparse.ArgumentParser(description="Milvus Indexer for video keyframe WEBP files.")
    p.add_argument("--root", type=str, default="./output-keyframes",
                   help="Root folder containing video keyframe subfolders (default: ./output-keyframes).")
    p.add_argument("--glob", type=str, default="**/keyframes/*.webp",
                   help="Glob pattern relative to root (default: **/keyframes/*.webp).")
    p.add_argument("--start-index", type=int, default=0, help="Skip first N files.")
    p.add_argument("--id-offset", type=int, default=0, help="ID starting offset.")

    # Milvus params
    p.add_argument("--collection-name", type=str, default="AIC25_fullbatch1")
    p.add_argument("--host", type=str, default="localhost")
    p.add_argument("--port", type=str, default="19530")
    p.add_argument("--recreate", action="store_true", help="Recreate collection if exists.")
    p.add_argument("--build-index", action="store_true", help="Build HNSW index and load collection after upload.")

    # Model params
    p.add_argument("--model", type=str, default="ViT-L-14",
                   help="Model architecture (default: ViT-L-14).")
    p.add_argument("--pretrained", type=str, default="laion2b_s32b_b82k",
                   help="Pretrained weights dataset (default: laion2b_s32b_b82k).")
    p.add_argument("--dimension", type=int, default=-1, help="-1 to auto-detect dimension.")

    # Performance params
    p.add_argument("--batch-size", type=int, default=32, help="Batch size for image encoding.")
    p.add_argument("--flush-interval", type=int, default=2000, help="Milvus flush interval.")
    p.add_argument("--cpu", action="store_true", help="Force CPU mode.")
    return p.parse_args()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        print(f"❌ Error: Root folder not found: {root}")
        sys.exit(1)

    device = torch.device("cpu" if args.cpu or not torch.cuda.is_available() else "cuda")
    print(f"🖥️ Execution target device: {device}")

    print(f"🚀 Loading model '{args.model}' on device: {device}...")
    if "dinov2" in args.model.lower():
        from torchvision import transforms
        model = torch.hub.load('facebookresearch/dinov2', args.model).to(device).eval()
        preprocess = transforms.Compose([
            transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    else:
        model, _, preprocess = open_clip.create_model_and_transforms(args.model, pretrained=args.pretrained)
        model = model.to(device).eval()

    # Auto detect dimension if -1
    dimension = args.dimension
    if dimension == -1:
        dimension = detect_model_dim(model, device)
        print(f"🔍 Vector dimension: {dimension}")

    # Step 1: Ensure collection schema
    ensure_collection(
        collection_name=args.collection_name,
        dimension=dimension,
        milvus_host=args.host,
        milvus_port=args.port,
        recreate=args.recreate,
    )

    # Step 2: Discover images
    paths = discover_images(root, args.glob, args.start_index)
    if not paths:
        print("❌ No matching images found. Check --root and --glob parameters.")
        sys.exit(0)

    print(f"Found {len(paths)} keyframe images to encode and upload.")

    indexed_paths = list(enumerate(paths, start=args.id_offset))

    # Step 3: Process and upload
    process_and_upload(
        indexed_paths=indexed_paths,
        model=model,
        preprocess=preprocess,
        device=device,
        milvus_host=args.host,
        milvus_port=args.port,
        collection_name=args.collection_name,
        batch_size=args.batch_size,
        flush_interval=args.flush_interval,
    )

    # Step 4: Build HNSW index & load into memory
    if args.build_index:
        build_index_and_load(
            collection_name=args.collection_name,
            milvus_host=args.host,
            milvus_port=args.port,
        )


if __name__ == "__main__":
    main()

