from FlagEmbedding import BGEM3FlagModel
import numpy as np

class BGEM3Service:
    def __init__(self, model_name='BAAI/bge-m3', device='cuda'):
        print(f"Loading BGE-M3 model: {model_name} on {device}...")
        self.model = BGEM3FlagModel(model_name, use_fp16=True, device=device)
        
    def encode_text(self, text: str) -> np.ndarray:
        """Encode text into dense embedding vector."""
        if not text:
            return None
        output = self.model.encode([text], return_dense=True, return_sparse=False, return_colbert_vecs=False)
        dense_vecs = output['dense_vecs']
        # Normalize
        dense_vecs = dense_vecs / np.linalg.norm(dense_vecs, axis=1, keepdims=True)
        return dense_vecs[0]
        
    def encode_batch(self, texts: list) -> np.ndarray:
        output = self.model.encode(texts, batch_size=12, return_dense=True, return_sparse=False, return_colbert_vecs=False)
        dense_vecs = output['dense_vecs']
        dense_vecs = dense_vecs / np.linalg.norm(dense_vecs, axis=1, keepdims=True)
        return dense_vecs

# Ví dụ cách tích hợp vào main.py:
# bge_service = BGEM3Service()
# vec = bge_service.encode_text("người đàn ông mặc áo đỏ")
# # Tìm kiếm trong Milvus với collection chứa BGE-M3 vectors...
