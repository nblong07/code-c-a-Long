"""
FastAPI Vector Search Service — Optimized for Windows 11 (16GB RAM + NVIDIA 6GB GPU)
=================================================================================

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
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ML/AI imports
import torch
import torch.nn.functional as F
import numpy as np
import open_clip

# Vector database imports
from pymilvus import MilvusClient


# ==========================================
# Pydantic Schemas
# ==========================================
class TextQueryRequest(BaseModel):
    First_query: str = Field(..., alias="firstQuery")
    Next_query: Optional[str] = Field("", alias="secondQuery")

    class Config:
        populate_by_name = True


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
    clip_model_name: str = "ViT-L-14"
    clip_pretrained: str = "laion2b_s32b_b82k"
    device: str = "cuda"

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
    keyframes_dir: str = "./data-keyframes"
    api_key: str = ""

class Config:
    """Main configuration class that loads from environment variables or config file"""

    def __init__(self, config_file: str = None):
        config_data = {}
        if config_file:
            target_path = config_file
            if not os.path.exists(target_path):
                target_path = os.path.join(os.path.dirname(__file__), config_file)
            if os.path.exists(target_path):
                try:
                    with open(target_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                except Exception as e:
                    print(f"Warning: Could not parse {target_path}: {e}")

        # Choose default device based on CUDA availability
        default_device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model = ModelConfig(
            clip_model_name=os.getenv("CLIP_MODEL_NAME", config_data.get("clip_model_name", "ViT-L-14")),
            clip_pretrained=os.getenv("CLIP_PRETRAINED", config_data.get("clip_pretrained", "laion2b_s32b_b82k")),
            device=os.getenv("DEVICE", config_data.get("device", default_device))
        )

        if self.model.device == "cuda" and not torch.cuda.is_available():
            print("⚠️ CUDA requested but not available. Falling back to CPU.")
            self.model.device = "cpu"

        milvus_host = config_data.get("milvus_host", "localhost")
        milvus_port = config_data.get("milvus_port", 19530)
        default_uri = f"http://{milvus_host}:{milvus_port}"

        self.database = DatabaseConfig(
            uri=os.getenv("MILVUS_URI", config_data.get("milvus_uri", default_uri)),
            database=os.getenv("MILVUS_DATABASE", config_data.get("milvus_database", "default")),
            collection_name=os.getenv("COLLECTION_NAME", config_data.get("collection_name", "AIC25_fullbatch1")),
            search_limit=int(os.getenv("SEARCH_LIMIT", config_data.get("search_limit", 3000))),
            replica_number=int(os.getenv("REPLICA_NUMBER", config_data.get("replica_number", 1)))
        )

        self.server = ServerConfig(
            cors_origins=os.getenv("CORS_ORIGINS", config_data.get("cors_origins", "*")),
            max_workers=int(os.getenv("MAX_WORKERS", config_data.get("max_workers", 4))),
            log_level=os.getenv("LOG_LEVEL", config_data.get("log_level", "INFO")),
            gzip_minimum_size=int(os.getenv("GZIP_MIN_SIZE", config_data.get("gzip_minimum_size", 1000))),
            keyframes_dir=config_data.get("keyframes_dir", "./data-keyframes"),
            api_key=os.getenv("API_KEY", config_data.get("api_key", ""))
        )


# ==========================================
# Vector Search Service
# ==========================================
class VectorSearchService:
    """Main service class encapsulating vector search & CLIP operations"""

    def __init__(self, config: Config):
        self.config = config
        self.device = torch.device(self.config.model.device)

        logging.basicConfig(
            level=getattr(logging, self.config.server.log_level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        self.logger = logging.getLogger(__name__)

        self.logger.info(f"⚡ Running service on device: {self.device}")
        if self.device.type == "cuda":
            self.logger.info(f"GPU Name: {torch.cuda.get_device_name(0)} | VRAM Total: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")

        self.thread_pool = ThreadPoolExecutor(max_workers=self.config.server.max_workers)
        self.active_connections: List[WebSocket] = []
        self.common_queries = ["person", "car", "building", "street", "night", "day"]
        self.precomputed_tokens = {}

        self._initialize_models()
        self._initialize_database()

    def _initialize_models(self):
        """Initialize OpenCLIP ML models with GPU acceleration"""
        model_name = self.config.model.clip_model_name
        pretrained = self.config.model.clip_pretrained
        self.logger.info(f"Initializing OpenCLIP model '{model_name}' (pretrained='{pretrained}') on device {self.device}...")

        try:
            self.clip_model, _, self.clip_preprocess = open_clip.create_model_and_transforms(
                model_name,
                pretrained=pretrained
            )
            self.clip_model = self.clip_model.to(self.device).eval()
            self.clip_tokenizer = open_clip.get_tokenizer(model_name)
            self.logger.info(f"OpenCLIP model '{model_name}' initialized successfully!")

            # Pre-tokenize common queries
            self.precomputed_tokens = {
                query: self.clip_tokenizer([query]).to(self.device)
                for query in self.common_queries
            }
        except Exception as e:
            self.logger.error(f"Failed to initialize ML models: {e}")
            raise e

    def _initialize_database(self):
        """Initialize Milvus database connection"""
        self.logger.info(f"Connecting to Milvus at {self.config.database.uri}...")
        try:
            self.milvus_client = MilvusClient(
                uri=self.config.database.uri,
                timeout=10,
                db_name=self.config.database.database
            )

            col_name = self.config.database.collection_name
            if self.milvus_client.has_collection(collection_name=col_name):
                self.milvus_client.load_collection(collection_name=col_name)
                self.logger.info(f"Milvus Collection '{col_name}' loaded successfully.")
            else:
                self.logger.warning(f"Collection '{col_name}' does not exist yet in Milvus. Please run upload_database.py first.")
        except Exception as e:
            self.logger.error(f"Milvus Initialization Warning: {e}")
            self.milvus_client = None

    def translate_query(self, query: str) -> str:
        """Automatically translate Vietnamese query to English if needed"""
        if not query or not query.strip():
            return ""
        q_str = query.strip()
        
        # Try deep_translator first
        try:
            from deep_translator import GoogleTranslator
            translated = GoogleTranslator(source='auto', target='en').translate(q_str)
            if translated and translated.strip():
                self.logger.info(f"🌐 Translated query (deep_translator): '{q_str}' -> '{translated}'")
                return translated.strip()
        except Exception as e:
            self.logger.debug(f"deep_translator error: {e}")

        # Fallback to free Google Translate API via urllib
        try:
            import urllib.request
            import urllib.parse
            import json
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q=" + urllib.parse.quote(q_str)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                res = json.loads(response.read().decode('utf-8'))
                translated = "".join([item[0] for item in res[0] if item and item[0]])
                if translated and translated.strip():
                    self.logger.info(f"🌐 Translated query (urllib_gtx): '{q_str}' -> '{translated}'")
                    return translated.strip()
        except Exception as e:
            self.logger.warning(f"Translation fallback error: {e}")

        return q_str

    def encode_clip_text(self, query: str) -> List[float]:
        """Encode text query into normalized embedding vector using OpenCLIP"""
        if not query or not query.strip():
            return []

        query = self.translate_query(query)

        text_inputs = self.precomputed_tokens.get(query.strip().lower())
        if text_inputs is None:
            text_inputs = self.clip_tokenizer([query]).to(self.device)

        with torch.inference_mode():
            if self.device.type == "cuda":
                with torch.amp.autocast(device_type="cuda"):
                    text_features = self.clip_model.encode_text(text_inputs)
            else:
                text_features = self.clip_model.encode_text(text_inputs)

            text_features = F.normalize(text_features.float(), p=2, dim=-1)
            return text_features.squeeze(0).cpu().numpy().tolist()


    async def query_milvus(self, query_vector: Any, limit: int = None) -> List[Dict[str, Any]]:
        """Query Milvus vector database safely"""
        if self.milvus_client is None:
            self.logger.error("Milvus client is not connected.")
            return []

        if not query_vector:
            return []

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
                search_params={"metric_type": "COSINE", "params": {"nprobe": 16}}
            )
            return results[0] if results and len(results) > 0 else []
        except Exception as e:
            self.logger.error(f"Error querying Milvus: {e}")
            return []

    async def get_vectors_by_ids(self, ids: List[str]) -> List[List[float]]:
        if not ids or self.milvus_client is None:
            return []

        formatted_ids = ", ".join([f"'{i}'" if isinstance(i, str) else str(i) for i in ids])
        filter_expr = f"id in [{formatted_ids}] or frame_id in [{formatted_ids}]"

        try:
            results = await asyncio.to_thread(
                self.milvus_client.query,
                collection_name=self.config.database.collection_name,
                filter=filter_expr,
                output_fields=["embedding"]
            )
            return [item["embedding"] for item in results if "embedding" in item]
        except Exception as e:
            self.logger.error(f"Error fetching vectors from Milvus by ID: {e}")
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
        """Rocchio Feedback Vector Refinement"""
        q0 = np.array(original_vec, dtype=np.float32)

        rel_term = np.mean(relevant_vecs, axis=0) if relevant_vecs else np.zeros_like(q0)
        non_rel_term = np.mean(non_relevant_vecs, axis=0) if non_relevant_vecs else np.zeros_like(q0)

        q_new = alpha * q0 + beta * rel_term - gamma * non_rel_term

        norm = np.linalg.norm(q_new)
        if norm > 0:
            q_new = q_new / norm

        return q_new.tolist()

    async def process_temporal_query(self, first_query: str, second_query: str = "") -> List[Dict[str, Any]]:
        """Process primary query and optional temporal next query"""
        start_time = time.time()
        try:
            if second_query and second_query.strip():
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
        """Boost ranking of keyframes when event 1 is followed by event 2 in the same video"""
        if not first_results or not second_results:
            return first_results[:1000]

        def safe_str_hash(s: str) -> int:
            return abs(hash(s)) % (2**31)

        try:
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
        except Exception as e:
            self.logger.error(f"Temporal relationship calculation error: {e}")
            return first_results[:1000]


# ==========================================
# FastAPI Application Setup
# ==========================================
def create_app(config_file: str = None) -> FastAPI:
    config = Config(config_file)
    service = VectorSearchService(config)

    app = FastAPI(
        title="Video Retrieval Vector Search Service",
        description="High-performance vector search service with CLIP models for Video Retrieval (AIC25)",
        version="2.0.0"
    )
    app.state.service = service

    async def check_ws_auth(websocket: WebSocket) -> bool:
        expected_key = service.config.server.api_key
        if not expected_key:
            return True
        token = websocket.query_params.get("token")
        if token != expected_key:
            await websocket.close(code=1008, reason="Unauthorized: Invalid Token")
            return False
        return True

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

    # Mount keyframe output directory for image serving with multi-path resolution
    kf_setting = config.server.keyframes_dir
    possible_kf_paths = [
        os.path.abspath(kf_setting),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", kf_setting)),
        os.path.abspath(os.path.join(os.path.dirname(__file__), kf_setting)),
    ]
    kf_path = next((p for p in possible_kf_paths if os.path.exists(p)), None)
    if kf_path:
        app.mount("/keyframes", StaticFiles(directory=kf_path), name="keyframes")
        service.logger.info(f"Mounted keyframes static path: {kf_path} -> /keyframes")
    else:
        service.logger.warning(f"Keyframe directory not found in candidate paths: {possible_kf_paths}")

    video_setting = os.environ.get("VIDEO_DIR", "D:/video_test")
    possible_video_paths = [
        os.path.abspath(video_setting),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", video_setting)),
        os.path.abspath(os.path.join(os.path.dirname(__file__), video_setting)),
    ]
    video_path = next((p for p in possible_video_paths if os.path.exists(p)), None)
    if video_path:
        app.mount("/videos", StaticFiles(directory=video_path), name="videos")
        service.logger.info(f"Mounted videos static path: {video_path} -> /videos")
    else:
        service.logger.info(f"Video directory not found at: {video_setting}")

    @app.get("/")
    async def root():
        return {
            "message": "Video Retrieval Vector Search System API",
            "status": "online",
            "docs": "/docs"
        }


    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        if not await check_ws_auth(websocket):
            return
        service.active_connections.append(websocket)
        service.logger.info("WebSocket connection accepted")

        try:
            while True:
                data = await websocket.receive_json()
                req_type = data.get("type")

                service.logger.info(f"Received WebSocket req_type: {req_type}")

                if req_type in ("text_query", "multi_query"):
                    first_q, second_q = "", ""
                    if req_type == "multi_query":
                        queries = data.get("queries", [])
                        text_contents = [
                            q.get("content", "")
                            for q in queries
                            if isinstance(q, dict) and q.get("content")
                        ]
                        if len(text_contents) > 0:
                            first_q = text_contents[0]
                        if len(text_contents) > 1:
                            second_q = text_contents[1]
                    else:
                        first_q = data.get("firstQuery", "")
                        second_q = data.get("secondQuery", "")

                    result = await service.process_temporal_query(first_q, second_q)
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
                else:
                    service.logger.warning(f"Unhandled WebSocket req_type: {req_type}")
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
    async def text_query_endpoint(payload: TextQueryRequest, authorization: Optional[str] = Header(None)):
        expected_key = service.config.server.api_key
        if expected_key:
            if not authorization or not authorization.startswith("Bearer ") or authorization.split(" ")[1] != expected_key:
                raise HTTPException(status_code=403, detail="Unauthorized")
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
    async def refine_query_endpoint(payload: RefineSearchRequest, authorization: Optional[str] = Header(None)):
        expected_key = service.config.server.api_key
        if expected_key:
            if not authorization or not authorization.startswith("Bearer ") or authorization.split(" ")[1] != expected_key:
                raise HTTPException(status_code=403, detail="Unauthorized")
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
            "device": str(service.device),
            "clip_model": service.config.model.clip_model_name,
            "database_connected": service.milvus_client is not None,
            "active_connections": len(service.active_connections)
        }

    @app.websocket("/ws/similarity_search")
    async def similarity_search_endpoint(websocket: WebSocket):
        await websocket.accept()
        if not await check_ws_auth(websocket):
            return
        service.logger.info("WebSocket /ws/similarity_search connected")
        try:
            while True:
                data = await websocket.receive_json()
                vector_id = data.get("vector") or data.get("vector_id") or data.get("id")
                service.logger.info(f"Similarity search requested for vector_id: {vector_id}")
                if vector_id is not None:
                    vecs = await service.get_vectors_by_ids([vector_id])
                    if vecs:
                        results = await service.query_milvus(vecs[0], limit=3000)
                        await websocket.send_json({"kq": results})
                    else:
                        service.logger.warning(f"Vector ID {vector_id} not found in Milvus")
                        await websocket.send_json({"kq": [], "error": f"Vector ID {vector_id} not found"})
                else:
                    await websocket.send_json({"kq": []})
        except WebSocketDisconnect:
            service.logger.info("WebSocket /ws/similarity_search disconnected")
        except Exception as e:
            service.logger.error(f"Error in similarity search websocket: {e}")

    @app.websocket("/ws/pagnition")
    async def pagnition_endpoint(websocket: WebSocket):
        await websocket.accept()
        if not await check_ws_auth(websocket):
            return
        service.logger.info("WebSocket /ws/pagnition connected")
        try:
            while True:
                data = await websocket.receive_json()
                page = data.get("page", 0)
                limit = data.get("limit", 50)
                offset = page * limit
                if service.milvus_client and service.milvus_client.has_collection(service.config.database.collection_name):
                    results = await asyncio.to_thread(
                        service.milvus_client.query,
                        collection_name=service.config.database.collection_name,
                        filter="id >= 0",
                        output_fields=['filepath', 'video_id', 'frame_id'],
                        limit=limit,
                        offset=offset
                    )
                    formatted = [{"entity": item, "id": item.get("id")} for item in results]
                    await websocket.send_json({"kq": formatted, "page": page})
                else:
                    await websocket.send_json({"kq": [], "page": page})
        except WebSocketDisconnect:
            service.logger.info("WebSocket /ws/pagnition disconnected")
        except Exception as e:
            service.logger.error(f"Error in pagnition websocket: {e}")

    return app


config_file = os.getenv("CONFIG_FILE", "config.json")
app = create_app(config_file)

@app.websocket("/ws/group_search")
@app.websocket("/ws/alerts")
@app.websocket("/ws/share_query")
@app.websocket("/ws/filter_query")
@app.websocket("/ws/share_image")
@app.websocket("/ws/log")
async def dummy_websocket(websocket: WebSocket):
    await websocket.accept()
    expected_key = app.state.service.config.server.api_key if hasattr(app, "state") and hasattr(app.state, "service") else ""
    if expected_key:
        token = websocket.query_params.get("token")
        if token != expected_key:
            await websocket.close(code=1008, reason="Unauthorized: Invalid Token")
            return
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", reload=False)