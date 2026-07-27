"""
FastAPI Vector Search Service
===========================

A high-performance vector search service using CLIP models for image-text similarity search.
Supports temporal queries, interactive retrieval (Rocchio), and provides both REST API and WebSocket interfaces.
"""

import os
import json
import time
import logging
import asyncio
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

# FastAPI imports
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

# ML/AI imports
import torch
import torch.nn.functional as F
import numpy as np
import open_clip

# Vector database imports
from pymilvus import MilvusClient


# ==========================================
# Pydantic Schemas (Đã hỗ trợ cờ alias để sửa lỗi 422)
# ==========================================
class TextQueryRequest(BaseModel):
    First_query: str = Field(..., alias="firstQuery")
    Next_query: Optional[str] = Field("", alias="secondQuery")

    class Config:
        populate_by_name = True  # Cho phép nhận cả "First_query" lẫn "firstQuery"


class RefineSearchRequest(BaseModel):
    """Schema nhận request lọc lại kết quả bằng thuật toán Rocchio"""
    original_vector: List[float]
    relevant_ids: List[str]
    non_relevant_ids: Optional[List[str]] = []
    top_k: Optional[int] = 1000
    alpha: Optional[float] = 1.0
    beta: Optional[float] = 0.75
    gamma: Optional[float] = 0.15


# ==========================================
# Configuration Management
# ==========================================
@dataclass
class ModelConfig:
    """Configuration for ML models"""
    clip_model_name: str = "ViT-B-32"
    clip_pretrained: str = "laion2b_s34b_b79k"
    device: str = "cpu"

@dataclass
class DatabaseConfig:
    """Configuration for Milvus vector database"""
    uri: str = "http://localhost:19530"
    database: str = "default"
    collection_name: str = "AIC25_fullbatch1"
    search_limit: int = 3000
    replica_number: int = 1

@dataclass
class ServerConfig:
    """Configuration for FastAPI server"""
    cors_origins: str = "*"
    max_workers: int = 4
    log_level: str = "INFO"
    gzip_minimum_size: int = 1000

class Config:
    """Main configuration class that loads from environment variables or config file"""

    def __init__(self, config_file: str = None):
        config_data = {}
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config_data = json.load(f)

        self.model = ModelConfig(
            clip_model_name="ViT-B-32",
            clip_pretrained="laion2b_s34b_b79k",
            device="cpu"
        )

        self.database = DatabaseConfig(
            uri=os.getenv("MILVUS_URI", config_data.get("milvus_uri", "http://localhost:19530")),
            database=os.getenv("MILVUS_DATABASE", config_data.get("milvus_database", "default")),
            collection_name=os.getenv("COLLECTION_NAME", config_data.get("collection_name", "AIC25_fullbatch1")),
            search_limit=int(os.getenv("SEARCH_LIMIT", config_data.get("search_limit", 3000))),
            replica_number=int(os.getenv("REPLICA_NUMBER", config_data.get("replica_number", 1)))
        )

        self.server = ServerConfig(
            cors_origins=os.getenv("CORS_ORIGINS", config_data.get("cors_origins", "*")),
            max_workers=int(os.getenv("MAX_WORKERS", config_data.get("max_workers", 4))),
            log_level=os.getenv("LOG_LEVEL", config_data.get("log_level", "INFO")),
            gzip_minimum_size=int(os.getenv("GZIP_MIN_SIZE", config_data.get("gzip_minimum_size", 1000)))
        )

        if self.model.device == "cuda" and not torch.cuda.is_available():
            self.model.device = "cpu"


# ==========================================
# Vector Search Service
# ==========================================
class VectorSearchService:
    """Main service class that encapsulates all functionality"""

    def __init__(self, config: Config):
        self.config = config
        self.device = torch.device(self.config.model.device)

        logging.basicConfig(level=getattr(logging, self.config.server.log_level))
        self.logger = logging.getLogger(__name__)

        self.thread_pool = ThreadPoolExecutor(max_workers=self.config.server.max_workers)
        self.active_connections: List[WebSocket] = []
        self.common_queries = ["person", "car", "building"]
        self.precomputed_tokens = {}

        self._initialize_models()
        self._initialize_database()

    def _initialize_models(self):
        """Initialize ML models (CLIP)"""
        self.logger.info("Initializing ML models...")
        self.clip_model, _, self.clip_preprocess = open_clip.create_model_and_transforms(
            self.config.model.clip_model_name,
            pretrained=self.config.model.clip_pretrained
        )
        self.clip_model = self.clip_model.to(self.device).eval()
        self.clip_tokenizer = open_clip.get_tokenizer(self.config.model.clip_model_name)

        self.precomputed_tokens = {
            query: self.clip_tokenizer([query]).to(self.device)
            for query in self.common_queries
        }
        self.logger.info("Models initialized successfully")

    def _initialize_database(self):
        """Initialize Milvus database connection"""
        self.logger.info("Initializing database connection...")
        try:
            self.milvus_client = MilvusClient(
                uri=self.config.database.uri,
                timeout=10,
                db_name=self.config.database.database
            )

            col_name = self.config.database.collection_name
            if self.milvus_client.has_collection(collection_name=col_name):
                index_params = self.milvus_client.prepare_index_params()
                index_params.add_index(
                    field_name="embedding",
                    metric_type="COSINE",
                    index_type="AUTOINDEX"
                )
                self.milvus_client.create_index(
                    collection_name=col_name,
                    index_params=index_params
                )
                self.milvus_client.load_collection(collection_name=col_name)
                self.logger.info(f"Collection '{col_name}' loaded successfully.")
            else:
                self.logger.warning(f"Collection '{col_name}' does not exist in Milvus.")
        except Exception as e:
            self.logger.error(f"Milvus Initialization Warning: {e}")

    def encode_clip_text(self, query: str) -> torch.Tensor:
        """Encode text using CLIP model"""
        text_inputs = self.precomputed_tokens.get(query)
        if text_inputs is None:
            text_inputs = self.clip_tokenizer([query]).to(self.device)

        with torch.no_grad():
            text_features = self.clip_model.encode_text(text_inputs)
            return F.normalize(text_features, p=2, dim=-1)

    async def query_milvus(self, query_vector: Any, limit: int = None) -> List[Dict[str, Any]]:
        """Query Milvus vector database an toàn, tránh văng lỗi 500"""
        if limit is None:
            limit = self.config.database.search_limit

        vec_list = query_vector.squeeze(0).tolist() if isinstance(query_vector, torch.Tensor) else query_vector

        try:
            results = await asyncio.to_thread(
                self.milvus_client.search,
                collection_name=self.config.database.collection_name,
                anns_field="embedding",
                data=[vec_list],
                limit=limit,
                output_fields=['filepath', 'video_id', 'frame_id'],
                search_params={"metric_type": "COSINE", "params": {}}
            )
            return results[0] if results and len(results) > 0 else []
        except Exception as e:
            self.logger.error(f"Error querying Milvus: {e}")
            return []

    async def get_vectors_by_ids(self, ids: List[str]) -> List[List[float]]:
        if not ids:
            return []

        formatted_ids = ", ".join([f"'{i}'" if isinstance(i, str) else str(i) for i in ids])
        filter_expr = f"frame_id in [{formatted_ids}]"

        try:
            results = await asyncio.to_thread(
                self.milvus_client.query,
                collection_name=self.config.database.collection_name,
                filter=filter_expr,
                output_fields=["embedding"]
            )
            return [item["embedding"] for item in results if "embedding" in item]
        except Exception as e:
            self.logger.error(f"Lỗi khi truy vấn vector từ Milvus theo ID: {e}")
            return []

    def compute_rocchio_vector(
        self,
        original_vec: List[float],
        relevant_vecs: List[List[float]],
        non_relevant_vecs: List[List[float]] = None,
        alpha: float = 1.0,
        beta: float = 0.75,
        gamma: float = 0.15
    ) -> List[float]:
        q0 = np.array(original_vec, dtype=np.float32)

        rel_term = np.mean(relevant_vecs, axis=0) if relevant_vecs else np.zeros_like(q0)
        non_rel_term = np.mean(non_relevant_vecs, axis=0) if non_relevant_vecs else np.zeros_like(q0)

        q_new = alpha * q0 + beta * rel_term - gamma * non_rel_term

        norm = np.linalg.norm(q_new)
        if norm > 0:
            q_new = q_new / norm

        return q_new.tolist()

    async def process_temporal_query(self, first_query: str, second_query: str = "") -> List[Dict[str, Any]]:
        start_time = time.time()
        try:
            if second_query:
                first_encoded, second_encoded = await asyncio.gather(
                    asyncio.to_thread(self.encode_clip_text, first_query),
                    asyncio.to_thread(self.encode_clip_text, second_query)
                )

                fkq, nkq = await asyncio.gather(
                    self.query_milvus(first_encoded),
                    self.query_milvus(second_encoded)
                )

                result = self._process_temporal_relationships(fkq, nkq)
            else:
                first_encoded = await asyncio.to_thread(self.encode_clip_text, first_query)
                fkq = await self.query_milvus(first_encoded)
                result = fkq[:1000]

            return result

        except Exception as e:
            self.logger.error(f"Error in temporal query processing: {e}")
            raise HTTPException(status_code=500, detail=f"Query Execution Error: {str(e)}")
        finally:
            self.logger.info(f"Temporal query executed in {time.time() - start_time:.4f} seconds")

    def _process_temporal_relationships(self, first_results: List[Dict[str, Any]], second_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not first_results or not second_results:
            return first_results[:1000]

        def safe_str_hash(s: str) -> int:
            return abs(hash(s)) % (2**31)

        # Đã bọc an toàn dict get tránh văng lỗi KeyError
        fkq_data = torch.tensor([
            [
                int(item.get('entity', {}).get('frame_id', 0)),
                float(item.get('distance', 0.0)),
                safe_str_hash(str(item.get('entity', {}).get('video_id', '')))
            ]
            for item in first_results
        ], device=self.device, dtype=torch.float32)

        nkq_data = torch.tensor([
            [
                int(item.get('entity', {}).get('frame_id', 0)),
                float(item.get('distance', 0.0)),
                safe_str_hash(str(item.get('entity', {}).get('video_id', '')))
            ]
            for item in second_results
        ], device=self.device, dtype=torch.float32)

        frame_diff = nkq_data[:, None, 0] - fkq_data[None, :, 0]
        same_video_mask = fkq_data[None, :, 2] == nkq_data[:, None, 2]
        valid_frame_diff_mask = (frame_diff > 0) & (frame_diff <= 1500) & same_video_mask

        score_increase = nkq_data[:, None, 1] * (1500 - frame_diff) / 1500
        score_increase = torch.where(valid_frame_diff_mask, score_increase, torch.zeros_like(score_increase))

        max_boost, _ = score_increase.max(dim=0)
        fkq_data[:, 1] += max_boost

        scores = fkq_data[:, 1].cpu().numpy()
        sorted_indices = np.argsort(scores)[::-1][:1000]

        updated_results = []
        for i in sorted_indices:
            res_item = dict(first_results[i])
            res_item['distance'] = float(scores[i])
            updated_results.append(res_item)

        return updated_results


# ==========================================
# FastAPI Application Setup
# ==========================================
def create_app(config_file: str = None) -> FastAPI:
    config = Config(config_file)
    service = VectorSearchService(config)

    app = FastAPI(
        title="Vector Search Service",
        description="High-performance vector search service with CLIP models and Interactive Retrieval",
        version="1.0.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600,
    )

    app.add_middleware(
        GZipMiddleware,
        minimum_size=config.server.gzip_minimum_size
    )

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        service.active_connections.append(websocket)
        service.logger.info("WebSocket connection accepted")

        try:
            while True:
                data = await websocket.receive_json()
                req_type = data.get("type")

                service.logger.info(f"Received req_type: {req_type}")

                if req_type == "text_query":
                    result = await service.process_temporal_query(
                        data.get("firstQuery", ""), data.get("secondQuery", "")
                    )
                    await websocket.send_json({"kq": result})

                elif req_type == "refine_query":
                    rel_vectors = await service.get_vectors_by_ids(
                        data.get("relevant_ids", [])
                    )
                    non_rel_vectors = await service.get_vectors_by_ids(
                        data.get("non_relevant_ids", [])
                    )

                    new_vector = service.compute_rocchio_vector(
                        original_vec=data.get("original_vector", []),
                        relevant_vecs=rel_vectors,
                        non_relevant_vecs=non_rel_vectors,
                        alpha=data.get("alpha", 1.0),
                        beta=data.get("beta", 0.75),
                        gamma=data.get("gamma", 0.15),
                    )

                    new_results = await service.query_milvus(
                        new_vector, limit=data.get("top_k", 1000)
                    )
                    await websocket.send_json(
                        {
                            "type": "refine_result",
                            "new_vector": new_vector,
                            "kq": new_results,
                        }
                    )

                elif req_type == "multi_query":
                    model_type = data.get("model")  # clip, blip, beit...
                    queries = data.get("queries", [])

                    result = await service.process_multi_query(model_type, queries)
                    await websocket.send_json({"kq": result})

                else:
                    service.logger.warning(f"Unhandled req_type: {req_type}")
                    await websocket.send_json(
                        {"error": f"Unknown req_type: {req_type}"}
                    )

        except WebSocketDisconnect:
            service.logger.info("WebSocket disconnected")
        except Exception as e:
            service.logger.error(f"Error in WebSocket: {str(e)}", exc_info=True)
        finally:
            if websocket in service.active_connections:
                service.active_connections.remove(websocket)

    @app.post("/TextQuery")
    async def text_query_endpoint(payload: TextQueryRequest):
        try:
            result = await service.process_temporal_query(payload.First_query, payload.Next_query)
            return {
                "kq": result,
                "fquery": payload.First_query,
                "nquery": payload.Next_query,
                "total_results": len(result)
            }
        except Exception as e:
            service.logger.error(f"Error in text query: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/RefineQuery")
    async def refine_query_endpoint(payload: RefineSearchRequest):
        try:
            rel_vectors = await service.get_vectors_by_ids(payload.relevant_ids)
            non_rel_vectors = await service.get_vectors_by_ids(payload.non_relevant_ids)

            if not rel_vectors:
                raise HTTPException(status_code=400, detail="Không tìm thấy vector phù hợp cho các relevant_ids đã cung cấp")

            new_vector = service.compute_rocchio_vector(
                original_vec=payload.original_vector,
                relevant_vecs=rel_vectors,
                non_relevant_vecs=non_rel_vectors,
                alpha=payload.alpha,
                beta=payload.beta,
                gamma=payload.gamma
            )

            results = await service.query_milvus(new_vector, limit=payload.top_k)

            return {
                "status": "success",
                "new_vector": new_vector,
                "kq": results,
                "total_results": len(results)
            }

        except Exception as e:
            service.logger.error(f"Lỗi trong quá trình refine query: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "models_loaded": True,
            "database_connected": True,
            "active_connections": len(service.active_connections)
        }

    return app


config_file = os.getenv("CONFIG_FILE", "config.json")
app = create_app(config_file)

@app.websocket("/ws/group_search")
@app.websocket("/ws/alerts")
@app.websocket("/ws/share_query")
@app.websocket("/ws/filter_query")
@app.websocket("/ws/share_image")
@app.websocket("/ws/similarity_search")
@app.websocket("/ws/log")
@app.websocket("/ws/pagnition")
async def dummy_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", reload=False)