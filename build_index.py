import faiss
import numpy as np

print("Đang load file features...")
features = np.load("features.npy")
dimension = features.shape[1] # Độ dài vector (thường là 512)

print(f"Tổng số vector: {features.shape[0]}, Chiều vector: {dimension}")

# Tạo Index dùng Cosine / Inner Product
index = faiss.IndexFlatIP(dimension)
index.add(features)

# Lưu file Index
faiss.write_index(index, "faiss_index.bin")
print("---> XONG BƯỚC 2! Đã tạo thành công file 'faiss_index.bin'")