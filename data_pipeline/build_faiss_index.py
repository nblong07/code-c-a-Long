#!/usr/bin/env python3
"""
Xây dựng chỉ mục FAISS IVF-SQ8
Cấu hình: 8-bit Scalar Quantization (SQ8), khoảng cách Inner Product, vector 1152 chiều.
Tối ưu phần cứng: CPU OpenMP đa luồng (85% số luồng CPU).
"""
import os
import sys
import time
import argparse
import numpy as np
import faiss

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_cpu_cores = os.cpu_count() or 8
OPTIMAL_CPU_THREADS = max(1, int(_cpu_cores * 0.85))
faiss.omp_set_num_threads(OPTIMAL_CPU_THREADS)

def build_faiss_index(features_path: str, output_path: str, nlist: int = None, batch_size: int = 50000):
    if not os.path.exists(features_path):
        print(f"[ERROR] Khong tim thay file {features_path}")
        return False

    print(f"[INFO] Doc vector dac trung tu: {features_path}")
    t0 = time.perf_counter()
    feats = np.load(features_path, mmap_mode="r")
    N, d = feats.shape
    print(f"       Tong so vectors: {N:,} | So chieu: {d}")

    if nlist is None:
        nlist = min(2048, max(256, int(np.sqrt(N) * 2)))
    print(f"[INFO] Cau hinh FAISS IVF-SQ8: nlist={nlist}, metric=INNER_PRODUCT (Cosine), quantizer=QT_8bit")

    quantizer = faiss.IndexFlatIP(d)
    index = faiss.IndexIVFScalarQuantizer(
        quantizer, d, nlist, faiss.ScalarQuantizer.QT_8bit, faiss.METRIC_INNER_PRODUCT
    )

    train_n = min(60000, N)
    print(f"[INFO] Huan luyen bo luong tu hoa SQ8 tren mau {train_n:,} vectors...")
    train_sample = np.array(feats[:train_n], dtype=np.float32)
    faiss.normalize_L2(train_sample)
    index.train(train_sample)

    print(f"[INFO] Them {N:,} vectors vao chi muc theo tung batch ({batch_size:,})...")
    for i in range(0, N, batch_size):
        batch = np.array(feats[i:i+batch_size], dtype=np.float32)
        faiss.normalize_L2(batch)
        index.add(batch)
        print(f"       Da them {min(i + batch_size, N):,}/{N:,} vectors...")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    faiss.write_index(index, output_path)
    elapsed = time.perf_counter() - t0
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"[OK] Da xay dung va luu thanh cong {output_path} ({size_mb:.1f} MB) trong {elapsed:.2f}s!")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build FAISS IVF-SQ8 Index")
    parser.add_argument("--features", type=str, default="features.npy", help="Đường dẫn file features.npy")
    parser.add_argument("--output", type=str, default="features.faiss", help="Đường dẫn file xuất features.faiss")
    parser.add_argument("--nlist", type=int, default=None, help="Số lượng cluster centroids (mặc định: 2*sqrt(N))")
    args = parser.parse_args()

    build_faiss_index(args.features, args.output, nlist=args.nlist)
