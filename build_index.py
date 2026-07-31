
"""
FAISS Index Builder — Build FAISS index from features.npy for offline search
========================================================================
"""

import argparse
import os
import faiss
import numpy as np


def parse_args():
    p = argparse.ArgumentParser(description="Build FAISS vector index from numpy feature array.")
    p.add_argument("--features", type=str, default="features.npy", help="Path to features.npy file.")
    p.add_argument("--output", type=str, default="faiss_index.bin", help="Output path for index binary.")
    return p.parse_args()


def main():
    args = parse_args()

    if not os.path.exists(args.features):
        print(f"❌ Error: Features file '{args.features}' not found. Run extract.py first.")
        return

    print(f"Loading features from '{args.features}'...")
    features = np.load(args.features).astype('float32')

    # Normalize vectors to ensure exact Cosine / Inner Product similarity
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    features = features / norms

    num_vectors, dimension = features.shape
    print(f"Total vectors: {num_vectors}, Vector dimension: {dimension}")

    print("Building FAISS Index (Inner Product / Cosine)...")
    index = faiss.IndexFlatIP(dimension)
    index.add(features)

    faiss.write_index(index, args.output)
    print(f"✅ SUCCESS! FAISS index saved to '{args.output}'.")


if __name__ == "__main__":
    main()