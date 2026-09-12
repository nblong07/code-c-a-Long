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

_cpu_cores = os.cpu_count() or 8
OPTIMAL_CPU_THREADS = max(1, int(_cpu_cores * 0.85))
faiss.omp_set_num_threads(OPTIMAL_CPU_THREADS)

def build_faiss_index(features_path: str, output_path: str, nlist: int = None, batch_size: int = 50000):
    if not os.path.exists(features_path):
        print(f"❌ 0 Không tìm thấy file {features_path}")
        return False

    print(f"👂 Đang đọc vector đặc trưng từ: {features_path}")
    t0 = time.perf_counter()
    feats = np.load(features_path, mmap_mode="r")
    N, d = feats.shape
    print(f"   Tổng số vectors: {N:,} | Số chiều: {d}")

    if nlist is None:
        nlist = min(2048, max(256, int(np.sqrt(N) * 2)))
    print(f"⚡️  Cấu hình FAISS IVF-SQ8: nlist={nlist}, metric=INNER_PRODUCT (Cosine), quantizer=QT_8bit")

    quantizer = faiss.IndexFlatIP(d)
    index = faiss.IndexIVFScalarQuantizer(
        quantizer, d, nlist, faiss.ScalarQuantizer.QT_8bit, faiss.METRIC_INNER_PRODUCT
    )

    train_n = min(60000, N)
    print(f"🧠 Đang huấn luyện bộ lượng tử hóa SQ8 trên mẫu {train_n:,} vectors...")
    train_sample = np.array(feats[:train_n], dtype=np.float32)
    faiss.normalize_L2(train_sample)
    index.train(train_sample)

    print(f"📥 Đang thêm {N:,} vectors vào chỉ mục theo từng batch ({batch_size:,})...")
    for i in range(0, N, batch_size):
        batch = np.array(feats[i:i+batch_size], dtype=np.float32)
        faiss.normalize_L2(batch)
        index.add(batch)
        print(f"   Đã thêm {min(i + batch_size, N):,}/{N:,} vectors...")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    faiss.write_index(index, output_path)
    elapsed = time.perf_counter() - t0
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ đã xây dựng và lưu thành công {output_path} ({size_mb:.1f} MB) trong {elapsed:.2f}s!")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build FAISS IVF-SQ8 Index")
    parser.add_argument("--features", type=str, default="features.npy", help="Đường dẫn file features.npy")
    parser.add_argument("--output", type=str, default="features.faiss", help="Đường dẫn file xuất features.faiss")
    parser.add_argument("--nlist", type=int, default=None, help="Số lượng cluster centroids (mặc định: 2*sqrt(N))")
    args = parser.parse_args()

    build_faiss_index(args.features, args.output, nlist=args.nlist)
