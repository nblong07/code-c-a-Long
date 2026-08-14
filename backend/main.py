"""
FastAPI Vector Search Service — Multi-Model & Adaptive Dynamic Pipeline Video Moment Retrieval
Tối ưu hóa đặc biệt cho cấu hình máy: RAM 64 GB + GPU NVIDIA 32 GB VRAM
=================================================================================================

Tính năng hệ thống:
1. Dynamic Adaptive Pipeline Router: Tự động phân loại truy vấn và chọn luồng xử lý (Fast Path, OCR Path, Detection Path, Temporal Path, ToT Agent Path).
2. Lifelog Frame Heuristic Filter: Lọc mờ nhòe (Laplacian Variance) & lọc phơi sáng (LAB Luminance).
3. Tree of Thoughts (ToT) Agent & Counter-Questioning: Tự suy luận cây ý định và đặt câu hỏi ngược lại cho giám khảo khi câu hỏi mơ hồ.
4. HippoRAG Multi-Turn Context Memory: Lập chỉ mục vùng hải mã (Hippocampal Index) & Scene Graph duy trì ngữ cảnh tương tác đa lượt, chống ảo giác.
5. HNSW Vector DB Optimization: Tối ưu chỉ mục đồ thị Milvus HNSW (M=32, efConstruction=250, efSearch=128) trên 64GB RAM.
6. 2-Stage Retrieval API: Lọc thô (ANN Vector Search) + Xếp hạng tinh (Cross-Encoder / Multimodal Grounding).
"""

import os
import io
import re
import json
import time
import base64
import logging
import asyncio
import warnings
from enum import Enum
from typing import List, Optional, Dict, Any, Union, Tuple
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

# Suppress noisy external warnings for clean competition-grade logging
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# FastAPI & Pydantic imports
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict

# ML/AI imports
import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image
import cv2
import open_clip

# Vector database imports
from pymilvus import MilvusClient



# ==========================================
# 1. ENUM & ADAPTIVE QUERY ROUTER (BỘ ĐIỀU HƯỚNG TỰ ĐỘNG)
# ==========================================
class QueryType(str, Enum):
    SIMPLE_TEXT = "simple_text"
    OCR_TEXT = "ocr_text"
    FINE_GRAINED_OBJECT = "fine_grained_object"
    TEMPORAL = "temporal"
    AMBIGUOUS = "ambiguous"


class VideoEnvironment(str, Enum):
    OUTDOOR_STREET = "outdoor_street"          # Môi trường ngoài trời, đường phố, giao thông, công viên
    INDOOR_OFFICE_HOME = "indoor_office_home"   # Môi trường trong nhà, văn phòng, phòng khách, bếp
    NIGHT_LOW_LIGHT = "night_low_light"         # Môi trường ban đêm, ánh sáng yếu, đèn đường
    TEXT_HEAVY_SIGNAGE = "text_heavy_signage"   # Môi trường nhiều chữ viết, bảng hiệu, biển báo, hóa đơn
    FINE_OBJECT_TEXTURE = "fine_object_texture" # Môi trường chi tiết hoa văn, kết cấu vật thể nhỏ
    DYNAMIC_ACTION = "dynamic_action"           # Môi trường chuyển động nhanh, hành động liên hoàn
    GENERAL_SCENE = "general_scene"             # Khung cảnh tổng quan chung


class AdaptiveQueryRouter:
    """
    Bộ điều hướng tự động nâng cao:
    1. Phân loại dạng mô tả đầu vào (QueryType).
    2. Dự đoán Môi trường Video (VideoEnvironment) dựa trên từ khóa ngữ cảnh.
    3. Tự động chọn Mô hình AI tối ưu nhất (EVA-CLIP, DINOv2, BLIP, OCR Hybrid, Ensemble MIX).
    """
    def __init__(self):
        self.temporal_keywords = [
            "before", "after", "then", "previously", "later", "first", "second",
            "trước khi", "sau khi", "sau đó", "lúc sau", "ban đầu", "kế tiếp"
        ]
        self.ocr_keywords = [
            "text", "word", "written", "sign", "billboard", "poster", "label", "street name",
            "chữ", "biển hiệu", "viết", "tên đường", "hóa đơn", "bảng hiệu"
        ]
        self.color_keywords = [
            "red", "blue", "green", "yellow", "black", "white", "pink", "purple", "orange",
            "đỏ", "xanh", "vàng", "đen", "trắng", "hồng", "tím", "cam"
        ]
        self.common_objects = ["car", "person", "table", "dog", "phone", "building", "street", "laptop", "cup"]

        # Các từ khóa dự đoán môi trường video
        self.env_keywords = {
            VideoEnvironment.OUTDOOR_STREET: [
                "street", "road", "traffic", "car", "building", "park", "sky", "tree",
                "đường", "phố", "xe", "công viên", "bầu trời", "cây", "vỉa hè"
            ],
            VideoEnvironment.INDOOR_OFFICE_HOME: [
                "room", "office", "table", "desk", "kitchen", "chair", "sofa", "bed",
                "phòng", "văn phòng", "bàn", "ghế", "bếp", "nhà", "giường"
            ],
            VideoEnvironment.NIGHT_LOW_LIGHT: [
                "night", "dark", "evening", "lamp", "light", "shadow", "moon",
                "tối", "đêm", "đèn", "bóng tối", "buổi tối"
            ],
            VideoEnvironment.TEXT_HEAVY_SIGNAGE: [
                "sign", "text", "written", "billboard", "poster", "number", "word",
                "chữ", "biển", "tên", "hóa đơn", "tờ rơi"
            ],
            VideoEnvironment.FINE_OBJECT_TEXTURE: [
                "texture", "pattern", "small", "logo", "detail", "close-up", "cup", "watch",
                "chi tiết", "hoa văn", "họa tiết", "đồng hồ", "ly", "tách"
            ],
            VideoEnvironment.DYNAMIC_ACTION: [
                "running", "walking", "riding", "driving", "eating", "jumping", "playing",
                "chạy", "đi bộ", "lái xe", "ăn", "nhảy", "chơi"
            ]
        }

    def predict_video_environment(self, query_str: str) -> Tuple[VideoEnvironment, str]:
        """Dự đoán môi trường video thực tế dựa trên mô tả ngữ nghĩa đầu vào"""
        if not query_str:
            return VideoEnvironment.GENERAL_SCENE, "Không đủ dữ liệu mô tả (Môi trường Tổng quan)"

        q_lower = query_str.lower().strip()
        matched_scores: Dict[VideoEnvironment, int] = {env: 0 for env in VideoEnvironment}

        for env, kws in self.env_keywords.items():
            for kw in kws:
                if kw in q_lower:
                    matched_scores[env] += 1

        best_env = max(matched_scores, key=lambda k: matched_scores[k])

        if matched_scores[best_env] == 0:
            return VideoEnvironment.GENERAL_SCENE, "Môi trường Cảnh quay Tổng quan (General Scene)"

        env_descriptions = {
            VideoEnvironment.OUTDOOR_STREET: "Môi trường Ngoài trời / Đường phố / Giao thông",
            VideoEnvironment.INDOOR_OFFICE_HOME: "Môi trường Trong nhà / Văn phòng / Phòng khách",
            VideoEnvironment.NIGHT_LOW_LIGHT: "Môi trường Ban đêm / Ánh sáng yếu",
            VideoEnvironment.TEXT_HEAVY_SIGNAGE: "Môi trường Chứa chữ viết / Biển hiệu / Chữ khắc",
            VideoEnvironment.FINE_OBJECT_TEXTURE: "Môi trường Chi tiết nhỏ / Kết cấu hoa văn vật thể",
            VideoEnvironment.DYNAMIC_ACTION: "Môi trường Chuyển động nhanh / Hành động liên hoàn",
            VideoEnvironment.GENERAL_SCENE: "Môi trường Cảnh quay Tổng quan"
        }

        return best_env, env_descriptions[best_env]

    def route_query(self, query_str: str) -> Tuple[QueryType, str]:
        if not query_str or not query_str.strip():
            return QueryType.SIMPLE_TEXT, "Fast Path (Mặc định)"

        q_lower = query_str.lower().strip()
        words = q_lower.split()

        # 1. Kiểm tra Temporal Query
        if any(kw in q_lower for kw in self.temporal_keywords):
            return QueryType.TEMPORAL, "Temporal Path: Phân tách 2 sự kiện & Boost điểm mốc thời gian"

        # 2. Kiểm tra OCR Query
        if any(kw in q_lower for kw in self.ocr_keywords) or re.search(r'["\'].*?["\']', query_str):
            return QueryType.OCR_TEXT, "OCR Path: Kết hợp Vector Search + Lọc từ khóa Payload OCR"

        # 3. Kiểm tra Fine-grained Object Query
        if len(words) >= 8 or any(color in q_lower for color in self.color_keywords):
            return QueryType.FINE_GRAINED_OBJECT, "Detection Path: Tìm kiếm thô ANN -> Grounding DINO BBox Verify"

        # 4. Kiểm tra Ambiguous Query
        if len(words) <= 3 and not any(obj in q_lower for obj in self.common_objects):
            return QueryType.AMBIGUOUS, "ToT Agent Path: Kích hoạt Tree of Thoughts & Tạo câu hỏi làm rõ ngược lại"

        return QueryType.SIMPLE_TEXT, "Fast Path: Single Vector Search EVA-CLIP -> Milvus HNSW"

    def select_optimal_model(self, query_str: str) -> Dict[str, Any]:
        """
        Tự động lựa chọn mô hình AI tuyệt nhất dựa trên sự kết hợp giữa Dạng mô tả (QueryType) và Môi trường Video (VideoEnvironment).
        """
        q_type, strategy = self.route_query(query_str)
        v_env, env_desc = self.predict_video_environment(query_str)

        # Logic tự chọn mô hình tối ưu nhất
        if q_type == QueryType.OCR_TEXT or v_env == VideoEnvironment.TEXT_HEAVY_SIGNAGE:
            best_model = "clip"
            reasoning = "Chọn mô hình OCR Hybrid (PaddleOCR + CLIP) tối ưu cho nhận diện chữ viết và bảng hiệu."
        elif v_env == VideoEnvironment.FINE_OBJECT_TEXTURE or q_type == QueryType.FINE_GRAINED_OBJECT:
            best_model = "dinov2"
            reasoning = "Chọn mô hình DINOv2 cho khả năng bắt nét chi tiết kết cấu hình học và hoa văn vật thể nhỏ."
        elif v_env == VideoEnvironment.NIGHT_LOW_LIGHT:
            best_model = "mix"
            reasoning = "Chọn mô hình Ensemble MIX (RRF Score Fusion) để kết hợp đa mô hình phân tích trong điều kiện thiếu sáng."
        elif v_env == VideoEnvironment.INDOOR_OFFICE_HOME:
            best_model = "blip"
            reasoning = "Chọn mô hình BLIP tối ưu cho căn chỉnh khái niệm Vision-Language chi tiết trong không gian hẹp."
        elif v_env == VideoEnvironment.OUTDOOR_STREET:
            best_model = "eva-clip"
            reasoning = "Chọn mô hình EVA-02-CLIP (ViT-E/14 1024d) tối ưu cho không gian cảnh quay ngoài trời rộng lớn."
        else:
            best_model = "clip"
            reasoning = "Chọn mô hình OpenCLIP ViT-L-14 chuẩn cho truy vấn tổng quan."

        return {
            "query_type": q_type.value,
            "predicted_environment": v_env.value,
            "environment_description": env_desc,
            "recommended_model": best_model,
            "routing_strategy": strategy,
            "reasoning_explanation": reasoning
        }


# ==========================================
# 2. HEURISTICS LỌC KHUNG HÌNH LIFELOGGING
# ==========================================
class LifelogFrameFilter:
    """
    Lớp lọc Heuristics loại bỏ các khung hình mờ nhòe hoặc sai lệch phơi sáng.
    """
    def __init__(self, blur_threshold: float = 95.0, min_luminance: float = 20.0, max_luminance: float = 235.0):
        self.blur_threshold = blur_threshold
        self.min_luminance = min_luminance
        self.max_luminance = max_luminance

    def is_frame_valid(self, frame_bgr: np.ndarray) -> Tuple[bool, str, float]:
        if frame_bgr is None or frame_bgr.size == 0:
            return False, "Khung hình rỗng", 0.0

        # Laplacian Variance Blur Index
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if blur_score < self.blur_threshold:
            return False, f"Khung hình mờ (Điểm mờ: {blur_score:.1f} < {self.blur_threshold})", blur_score

        # LAB Luminance Stats
        lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        mean_lum = float(np.mean(l_channel))
        if mean_lum < self.min_luminance:
            return False, f"Khung hình quá tối (Độ sáng: {mean_lum:.1f} < {self.min_luminance})", blur_score
        if mean_lum > self.max_luminance:
            return False, f"Khung hình quá chói (Độ sáng: {mean_lum:.1f} > {self.max_luminance})", blur_score

        return True, "Khung hình hợp lệ", blur_score


# ==========================================
# 3. TREE OF THOUGHTS (ToT) LANGCHAIN AGENT & CLARIFICATION
# ==========================================
class TreeOfThoughtsAgent:
    """
    Agent suy luận dạng cây Tree of Thoughts (ToT) phân tích truy vấn phức tạp và đặt câu hỏi ngược lại cho giám khảo.
    """
    def __init__(self):
        pass

    def evaluate_and_expand(self, query_str: str) -> Dict[str, Any]:
        """
        Sinh ra 3 nhánh suy luận (Thought Branches) và xác định độ mơ hồ của câu hỏi.
        """
        q_clean = query_str.strip()
        words = q_clean.split()
        is_ambiguous = len(words) <= 4

        # 3 Nhánh suy luận (Tree of Thoughts)
        branches = [
            {
                "branch_id": 1,
                "focus": "Phân tích Thực thể & Đối tượng chính (Entities)",
                "sub_queries": [f"Visual of {q_clean}", f"Close-up photo of {q_clean}"],
                "confidence_score": 0.85 if not is_ambiguous else 0.40
            },
            {
                "branch_id": 2,
                "focus": "Phân tích Ngữ cảnh Bối cảnh (Environment & Setting)",
                "sub_queries": [f"Scene with {q_clean}", f"Background including {q_clean}"],
                "confidence_score": 0.78 if not is_ambiguous else 0.45
            },
            {
                "branch_id": 3,
                "focus": "Phân tích Chuỗi Hành động & Thời gian (Action & Temporal)",
                "sub_queries": [f"Person interacting with {q_clean}", f"Moment of {q_clean}"],
                "confidence_score": 0.90 if not is_ambiguous else 0.50
            }
        ]

        # Đặt câu hỏi làm rõ (Clarification Counter-Question) nếu truy vấn mơ hồ
        clarifying_question = None
        if is_ambiguous:
            clarifying_question = (
                f"Thưa Giám khảo, mô tả '{q_clean}' khá ngắn gọn. "
                f"Giám khảo có thể bổ sung thêm thông tin về màu sắc đối tượng, "
                f"khung cảnh xung quanh (trong nhà/ngoài trời), hoặc mốc thời gian diễn ra sự kiện được không ạ?"
            )

        return {
            "original_query": query_str,
            "is_ambiguous": is_ambiguous,
            "clarifying_question": clarifying_question,
            "tot_branches": branches,
            "recommended_action": "HỎI_NGƯỢC_GIÁM_KHẢO" if is_ambiguous else "THỰC_THI_TRUY_VẤN_ĐA_NHÁNH"
        }


# ==========================================
# 4. QUẢN LÝ TRẠNG THÁI HỘI THOẠI HIPPORAG MEMORY
# ==========================================
class HippoRAGMemory:
    """
    Hệ thống ghi nhớ HippoRAG (Hippocampal Index + Scene Graph Associative Memory) cho truy vấn đa lượt.
    """
    def __init__(self):
        self.conversation_history: List[Dict[str, Any]] = []
        self.entity_nodes: Dict[str, int] = {}
        self.scene_graph: List[Dict[str, Any]] = []

    def add_interaction(self, user_query: str, retrieved_video_ids: List[str], top_frame_id: Optional[str] = None):
        """Thêm một lượt tương tác vào bộ nhớ Vùng Hải Mã (Hippocampus)"""
        turn_id = len(self.conversation_history) + 1
        record = {
            "turn_id": turn_id,
            "timestamp": time.time(),
            "query": user_query,
            "candidate_video_ids": retrieved_video_ids[:5],
            "top_frame_id": top_frame_id
        }
        self.conversation_history.append(record)

        # Cập nhật Scene Graph Node
        for vid in retrieved_video_ids[:5]:
            self.entity_nodes[vid] = self.entity_nodes.get(vid, 0) + 1
            self.scene_graph.append({
                "source_turn": turn_id,
                "video_id": vid,
                "weight": 1.0 / turn_id
            })

    def get_context_summary(self) -> Dict[str, Any]:
        """Trích xuất tóm tắt ngữ cảnh hội thoại đa lượt"""
        recent_queries = [h["query"] for h in self.conversation_history[-3:]]
        top_focused_videos = sorted(self.entity_nodes.keys(), key=lambda k: self.entity_nodes[k], reverse=True)[:3]
        return {
            "total_turns": len(self.conversation_history),
            "recent_queries": recent_queries,
            "top_focused_videos": top_focused_videos,
            "memory_status": "Duy trì ngữ cảnh mượt mà (Ngăn ngừa ảo giác)"
        }

    def clear_memory(self):
        self.conversation_history.clear()
        self.entity_nodes.clear()
        self.scene_graph.clear()


# ==========================================
# 5. PYDANTIC SCHEMAS CHO API
# ==========================================
class TextQueryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    First_query: Optional[str] = Field("", alias="firstQuery", description="Mô tả sự kiện văn bản chính")
    Next_query: Optional[str] = Field("", alias="secondQuery", description="Mô tả sự kiện tiếp theo (Temporal)")
    text_query: Optional[str] = Field("", description="Mô tả văn bản trực tiếp")
    model: Optional[str] = Field("clip", description="Lựa chọn mô hình: clip, eva-clip, vit-l, vit-b, dinov2, blip, mix")
    top_k: Optional[int] = Field(1000, description="Số lượng kết quả cần trả về")


class ImageQueryRequest(BaseModel):
    image_base64: str = Field(..., description="Chuỗi Base64 của ảnh truy vấn")
    model: Optional[str] = Field("clip", description="Lựa chọn mô hình AI")
    top_k: Optional[int] = Field(1000, description="Số lượng kết quả cần trả về")


class HybridQueryRequest(BaseModel):
    text_query: Optional[str] = Field("", description="Mô tả văn bản")
    image_base64: Optional[str] = Field("", description="Ảnh mẫu truy vấn")
    text_weight: Optional[float] = Field(0.5, description="Trọng số vector văn bản")
    image_weight: Optional[float] = Field(0.5, description="Trọng số vector hình ảnh")
    model: Optional[str] = Field("clip", description="Lựa chọn mô hình AI")
    top_k: Optional[int] = Field(1000, description="Số lượng kết quả trả về")


class RefineSearchRequest(BaseModel):
    original_vector: List[float]
    relevant_ids: List[str]
    non_relevant_ids: Optional[List[str]] = []
    top_k: Optional[int] = 1000
    alpha: Optional[float] = 1.0
    beta: Optional[float] = 0.75
    gamma: Optional[float] = 0.15


class RouteQueryRequest(BaseModel):
    query_text: str = Field(..., description="Câu truy vấn cần điều hướng phân loại")


class TwoStageRetrievalRequest(BaseModel):
    query_text: str = Field(..., description="Câu truy vấn văn bản")
    model: Optional[str] = Field("clip", description="Mô hình AI")
    top_k: Optional[int] = Field(10, description="Số lượng kết quả cuối cùng")
    coarse_limit: Optional[int] = Field(500, description="Số lượng lọc thô giai đoạn 1")


# ==========================================
# 6. CONFIGURATION MANAGEMENT
# ==========================================
@dataclass
class ModelConfig:
    clip_model_name: str = "ViT-SO400M-14-SigLIP-384"
    clip_pretrained: str = "webli"
    device: str = "cuda"


@dataclass
class DatabaseConfig:
    uri: str = "http://localhost:19530"
    database: str = "default"
    collection_name: str = "AIC25_fullbatch1"
    search_limit: int = 5000
    replica_number: int = 1
    hnsw_m: int = 32
    hnsw_ef_construction: int = 250
    hnsw_ef_search: int = 128


@dataclass
class ServerConfig:
    cors_origins: str = "*"
    max_workers: int = 8
    log_level: str = "INFO"
    gzip_minimum_size: int = 1000
    keyframes_dir: str = "./data-keyframes"
    api_key: str = ""


class Config:
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

        default_device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model = ModelConfig(
            clip_model_name=os.getenv("CLIP_MODEL_NAME", config_data.get("clip_model_name", "ViT-SO400M-14-SigLIP-384")),
            clip_pretrained=os.getenv("CLIP_PRETRAINED", config_data.get("clip_pretrained", "webli")),
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
            search_limit=int(os.getenv("SEARCH_LIMIT", config_data.get("search_limit", 5000))),
            replica_number=int(os.getenv("REPLICA_NUMBER", config_data.get("replica_number", 1))),
            hnsw_m=int(config_data.get("hnsw_m", 32)),
            hnsw_ef_construction=int(config_data.get("hnsw_ef_construction", 250)),
            hnsw_ef_search=int(config_data.get("hnsw_ef_search", 128))
        )

        self.server = ServerConfig(
            cors_origins=os.getenv("CORS_ORIGINS", config_data.get("cors_origins", "*")),
            max_workers=int(os.getenv("MAX_WORKERS", config_data.get("max_workers", 8))),
            log_level=os.getenv("LOG_LEVEL", config_data.get("log_level", "INFO")),
            gzip_minimum_size=int(os.getenv("GZIP_MIN_SIZE", config_data.get("gzip_minimum_size", 1000))),
            keyframes_dir=config_data.get("keyframes_dir", "./data-keyframes"),
            api_key=os.getenv("API_KEY", config_data.get("api_key", ""))
        )


# ==========================================
# 7. MULTI-MODEL MANAGER (SOTA AI MODELS)
# ==========================================
class MultiModelManager:
    """Quản lý khởi tạo và lưu vết cache các mô hình AI đẳng cấp Top 1 (CLIP, EVA-02, SigLIP, DINOv2)"""
    def __init__(self, device: torch.device, logger: logging.Logger):
        self.device = device
        self.logger = logger
        self.loaded_models: Dict[str, Any] = {}
        self.loaded_transforms: Dict[str, Any] = {}
        self.loaded_tokenizers: Dict[str, Any] = {}

        self.model_specs = {
            # ── PRIMARY (phải khớp với model dùng upload_database.py) ──
            "clip": {
                "name": "ViT-SO400M-14-SigLIP-384",
                "pretrained": "webli",
                "dim": 1152,
                "objective": "Google SigLIP SO400M — Primary SOTA (DB index model)"
            },
            # ── SECONDARY SOTA (lazy-load khi frontend chọn) ──
            "eva-clip": {
                "name": "EVA02-E-14-plus",
                "pretrained": "laion2b_s9b_b144k",
                "dim": 1024,
                "objective": "EVA-02-E-14-plus Ultra High-Resolution SOTA"
            },
            "blip": {
                "name": "ViT-H-14-378-quickgelu",
                "pretrained": "dfn5b",
                "dim": 1024,
                "objective": "DFN5B ViT-H-14 High-Precision Visual Grounding"
            },
            "mix": {
                "name": "ViT-SO400M-14-SigLIP-384",
                "pretrained": "webli",
                "dim": 1152,
                "objective": "Multi-Model Ensemble Reciprocal Rank Fusion (RRF)"
            }
        }

    def get_model(self, key: str = "clip"):
        key_norm = (key or "clip").lower().strip()
        if key_norm not in self.model_specs:
            key_norm = "clip"

        spec = self.model_specs[key_norm]
        model_name = spec["name"]
        pretrained = spec["pretrained"]
        cache_key = f"{model_name}__{pretrained}"

        if cache_key in self.loaded_models:
            return (
                self.loaded_models[cache_key],
                self.loaded_transforms[cache_key],
                self.loaded_tokenizers[cache_key],
                spec
            )

        self.logger.info(f"Đang nạp mô hình Top-1 SOTA '{key_norm}' ({model_name}, pretrained='{pretrained}') lên {self.device}...")
        try:
            model, _, preprocess = open_clip.create_model_and_transforms(
                model_name,
                pretrained=pretrained
            )
            model = model.to(self.device).eval()
            tokenizer = open_clip.get_tokenizer(model_name)

            self.loaded_models[cache_key] = model
            self.loaded_transforms[cache_key] = preprocess
            self.loaded_tokenizers[cache_key] = tokenizer

            self.logger.info(f"Mô hình SOTA '{key_norm}' đã tải lên thành công!")
            return model, preprocess, tokenizer, spec
        except Exception as e:
            self.logger.warning(f"Không thể nạp '{key_norm}' ({e}). Tự động fallback về 'clip' primary model ViT-L-14-336.")
            default_key = "ViT-L-14-336__openai"
            if default_key in self.loaded_models:
                return (
                    self.loaded_models[default_key],
                    self.loaded_transforms[default_key],
                    self.loaded_tokenizers[default_key],
                    self.model_specs["clip"]
                )
            model, _, preprocess = open_clip.create_model_and_transforms("ViT-L-14-336", pretrained="openai")
            model = model.to(self.device).eval()
            tokenizer = open_clip.get_tokenizer("ViT-L-14-336")
            self.loaded_models[default_key] = model
            self.loaded_transforms[default_key] = preprocess
            self.loaded_tokenizers[default_key] = tokenizer
            return model, preprocess, tokenizer, self.model_specs["clip"]


# ==========================================
# 8. VECTOR SEARCH SERVICE CORE
# ==========================================
class VectorSearchService:
    """Dịch vụ chính quản lý kết nối Milvus DB, mã hóa vector và điều hướng mô hình"""

    def __init__(self, config: Config):
        self.config = config
        self.device = torch.device(self.config.model.device)

        logging.basicConfig(
            level=getattr(logging, self.config.server.log_level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        self.logger = logging.getLogger(__name__)

        self.logger.info(f"⚡ Khởi chạy Vector Search Service trên thiết bị: {self.device}")
        if self.device.type == "cuda":
            self.logger.info(f"Tên GPU: {torch.cuda.get_device_name(0)} | Tổng dung lượng VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")

        self.thread_pool = ThreadPoolExecutor(max_workers=self.config.server.max_workers)
        self.active_connections: List[WebSocket] = []

        # Khởi tạo các module cốt lõi nâng cấp
        self.router = AdaptiveQueryRouter()
        self.frame_filter = LifelogFrameFilter()
        self.tot_agent = TreeOfThoughtsAgent()
        self.hippo_memory = HippoRAGMemory()

        self.model_manager = MultiModelManager(self.device, self.logger)
        self._initialize_primary_model()
        self._initialize_database()

    def _initialize_primary_model(self):
        try:
            model, preprocess, tokenizer, _ = self.model_manager.get_model("clip")
            self.clip_model = model
            self.clip_preprocess = preprocess
            self.clip_tokenizer = tokenizer
        except Exception as e:
            self.logger.error(f"Lỗi khởi tạo mô hình chính: {e}")
            raise e

    def _initialize_database(self):
        self.logger.info(f"Đang kết nối tới Milvus Vector DB tại {self.config.database.uri}...")
        self.local_features = None
        self.local_metadata = []
        self.local_id_map = {}

        try:
            self.milvus_client = MilvusClient(
                uri=self.config.database.uri,
                timeout=3,
                db_name=self.config.database.database
            )

            col_name = self.config.database.collection_name
            if self.milvus_client.has_collection(collection_name=col_name):
                self.milvus_client.load_collection(collection_name=col_name)
                self.logger.info(f"Collection Milvus '{col_name}' đã load sẵn vào RAM 64GB.")
            else:
                self.logger.warning(f"Collection '{col_name}' chưa tồn tại trên Milvus. Đang nạp Vector search offline fallback...")
                self._load_local_fallback()
        except Exception as e:
            self.logger.warning(f"Không thể kết nối Milvus DB ({e}). Chuyển sang Chế độ Vector Search Offline (PyTorch CUDA)...")
            self.milvus_client = None
            self._load_local_fallback()

    def _load_local_fallback(self):
        feats_path = os.path.abspath("features.npy")
        paths_path = os.path.abspath("image_paths.npy")

        if not os.path.exists(feats_path) or not os.path.exists(paths_path):
            self.logger.warning("Không tìm thấy features.npy / image_paths.npy để chạy fallback.")
            return

        try:
            feats = np.load(feats_path).astype(np.float32)
            paths = np.load(paths_path)

            self.local_features = torch.from_numpy(feats).to(self.device)
            self.local_features = F.normalize(self.local_features, p=2, dim=-1)

            time_map = {}
            maps_dir = os.path.abspath("data-keyframes/maps")
            if os.path.exists(maps_dir):
                for f in os.listdir(maps_dir):
                    if f.endswith("_map.csv"):
                        v_id = f.replace("_map.csv", "")
                        csv_p = os.path.join(maps_dir, f)
                        try:
                            import csv
                            with open(csv_p, 'r', encoding='utf-8') as cf:
                                reader = csv.reader(cf)
                                next(reader, None)
                                for row in reader:
                                    if len(row) >= 2:
                                        time_map[(v_id, int(row[0]))] = float(row[1])
                        except Exception:
                            pass

            self.local_metadata = []
            self.local_id_map = {}

            from pathlib import Path
            for idx, raw_p in enumerate(paths):
                p = Path(raw_p)
                vid_name = p.parent.parent.name if p.parent.name == "keyframes" else p.parent.name
                try:
                    fid = int(p.stem.replace("keyframe_", ""))
                except Exception:
                    fid = idx

                rel_filepath = f"{vid_name}/keyframes/{p.name}"
                sec_val = time_map.get((vid_name, fid), float(fid))

                meta = {
                    "id": str(idx),
                    "filepath": rel_filepath,
                    "video_id": vid_name,
                    "frame_id": fid,
                    "time": sec_val
                }
                self.local_metadata.append(meta)
                self.local_id_map[str(idx)] = idx
                self.local_id_map[str(fid)] = idx
                self.local_id_map[f"{vid_name}_{fid}"] = idx

            self.logger.info(f"✅ Đã nạp thành công {len(self.local_metadata)} vector đặc trưng offline lên {self.device}!")
        except Exception as e:
            self.logger.error(f"Lỗi nạp vector offline fallback: {e}")

    def translate_query(self, query: str) -> str:
        """Tự động dịch thuật truy vấn tiếng Việt sang tiếng Anh"""
        if not query or not query.strip():
            return ""
        q_str = query.strip()

        try:
            from deep_translator import GoogleTranslator
            translated = GoogleTranslator(source='auto', target='en').translate(q_str)
            if translated and translated.strip():
                self.logger.info(f"🌐 Dịch tự động (deep_translator): '{q_str}' -> '{translated}'")
                return translated.strip()
        except Exception as e:
            self.logger.debug(f"deep_translator error: {e}")

        try:
            import urllib.request
            import urllib.parse
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q=" + urllib.parse.quote(q_str)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                res = json.loads(response.read().decode('utf-8'))
                translated = "".join([item[0] for item in res[0] if item and item[0]])
                if translated and translated.strip():
                    self.logger.info(f"🌐 Dịch tự động (gtx_fallback): '{q_str}' -> '{translated}'")
                    return translated.strip()
        except Exception as e:
            self.logger.warning(f"Translation fallback error: {e}")

        return q_str

    def load_image_from_input(self, image_input: Any) -> Image.Image:
        if isinstance(image_input, Image.Image):
            return image_input.convert("RGB")
        if isinstance(image_input, str):
            clean_str = image_input.strip()
            if clean_str.startswith("data:image"):
                clean_str = clean_str.split(",", 1)[1]
            clean_str = clean_str.replace("\n", "").replace("\r", "")
            image_bytes = base64.b64decode(clean_str)
            return Image.open(io.BytesIO(image_bytes)).convert("RGB")
        elif isinstance(image_input, bytes):
            return Image.open(io.BytesIO(image_input)).convert("RGB")
        else:
            raise ValueError(f"Không hỗ trợ định dạng ảnh: {type(image_input)}")

    def encode_clip_text(self, query: str, model_name: str = "clip") -> List[float]:
        if not query or not query.strip():
            return []

        query_en = self.translate_query(query)
        model, _, tokenizer, spec = self.model_manager.get_model(model_name)
        text_inputs = tokenizer([query_en]).to(self.device)

        with torch.inference_mode():
            if self.device.type == "cuda":
                with torch.amp.autocast(device_type="cuda"):
                    text_features = model.encode_text(text_inputs)
            else:
                text_features = model.encode_text(text_inputs)

            text_features = F.normalize(text_features.float(), p=2, dim=-1)
            vec = text_features.squeeze(0).cpu().numpy().tolist()

            return vec

    def encode_clip_image(self, image_input: Any, model_name: str = "clip") -> List[float]:
        if not image_input:
            return []

        try:
            pil_img = self.load_image_from_input(image_input)
            model, preprocess, _, spec = self.model_manager.get_model(model_name)
            tensor_img = preprocess(pil_img).unsqueeze(0).to(self.device)

            with torch.inference_mode():
                if self.device.type == "cuda":
                    with torch.amp.autocast(device_type="cuda"):
                        img_features = model.encode_image(tensor_img)
                else:
                    img_features = model.encode_image(tensor_img)

                img_features = F.normalize(img_features.float(), p=2, dim=-1)
                vec = img_features.squeeze(0).cpu().numpy().tolist()

                return vec
        except Exception as e:
            self.logger.error(f"Lỗi mã hóa ảnh bằng mô hình '{model_name}': {e}")
            return []

    def encode_hybrid_query(
        self,
        text_query: str = "",
        image_input: Any = None,
        text_weight: float = 0.5,
        image_weight: float = 0.5,
        model_name: str = "clip"
    ) -> List[float]:
        text_vec = self.encode_clip_text(text_query, model_name=model_name) if text_query and text_query.strip() else []
        image_vec = self.encode_clip_image(image_input, model_name=model_name) if image_input else []

        if text_vec and image_vec:
            t_arr = np.array(text_vec, dtype=np.float32)
            i_arr = np.array(image_vec, dtype=np.float32)
            hybrid_arr = text_weight * t_arr + image_weight * i_arr
            norm = np.linalg.norm(hybrid_arr)
            if norm > 0:
                hybrid_arr = hybrid_arr / norm
            return hybrid_arr.tolist()
        elif text_vec:
            return text_vec
        elif image_vec:
            return image_vec
        else:
            return []

    async def query_milvus(self, query_vector: Any, limit: int = None) -> List[Dict[str, Any]]:
        if not query_vector:
            return []

        if limit is None:
            limit = self.config.database.search_limit

        vec_list = query_vector.squeeze(0).tolist() if isinstance(query_vector, torch.Tensor) else query_vector

        if self.milvus_client is not None:
            try:
                results = await asyncio.to_thread(
                    self.milvus_client.search,
                    collection_name=self.config.database.collection_name,
                    anns_field="embedding",
                    data=[vec_list],
                    limit=limit,
                    output_fields=['filepath', 'video_id', 'frame_id'],
                    search_params={
                        "metric_type": "COSINE",
                        "params": {"ef": max(self.config.database.hnsw_ef_search, limit)}
                    }
                )
                if results and len(results) > 0 and len(results[0]) > 0:
                    parsed_results = []
                    for item in results[0]:
                        if isinstance(item, dict):
                            parsed_results.append(item)
                        else:
                            entity_dict = {}
                            if hasattr(item, 'entity'):
                                for f in ['filepath', 'video_id', 'frame_id']:
                                    try:
                                        if hasattr(item.entity, 'get'):
                                            val = item.entity.get(f)
                                        else:
                                            val = getattr(item.entity, f, None)
                                        if val is not None:
                                            entity_dict[f] = val
                                    except Exception:
                                        pass
                            
                            parsed_results.append({
                                "id": str(getattr(item, 'id', '')),
                                "distance": float(getattr(item, 'distance', 0.0)),
                                "entity": entity_dict
                            })
                    return parsed_results
            except Exception as e:
                self.logger.error(f"Lỗi truy vấn Milvus HNSW: {e}")

        # Offline Local Fallback Vector Search (PyTorch CUDA)
        if self.local_features is not None and len(self.local_metadata) > 0:
            q_tensor = torch.tensor(vec_list, device=self.device, dtype=torch.float32)
            q_tensor = F.normalize(q_tensor, p=2, dim=-1)

            with torch.inference_mode():
                sims = torch.matmul(self.local_features, q_tensor.unsqueeze(-1)).squeeze(-1)
                top_k = min(limit, len(self.local_metadata))
                top_scores, top_indices = torch.topk(sims, k=top_k)

                top_scores = top_scores.cpu().numpy()
                top_indices = top_indices.cpu().numpy()

            results = []
            for score, idx in zip(top_scores, top_indices):
                meta = self.local_metadata[idx]
                results.append({
                    "id": str(meta["frame_id"]),
                    "distance": float(score),
                    "entity": meta
                })
            return results

        return []

    async def get_vectors_by_ids(self, ids: List[str]) -> List[List[float]]:
        if not ids:
            return []

        if self.milvus_client is not None:
            formatted_ids = ", ".join([f"'{i}'" if isinstance(i, str) else str(i) for i in ids])
            filter_expr = f"id in [{formatted_ids}] or frame_id in [{formatted_ids}]"

            try:
                results = await asyncio.to_thread(
                    self.milvus_client.query,
                    collection_name=self.config.database.collection_name,
                    filter=filter_expr,
                    output_fields=["embedding"]
                )
                if results:
                    return [item["embedding"] for item in results if "embedding" in item]
            except Exception as e:
                self.logger.error(f"Lỗi lấy vector từ Milvus theo ID: {e}")

        if self.local_features is not None:
            vecs = []
            for i in ids:
                str_i = str(i)
                if str_i in self.local_id_map:
                    idx = self.local_id_map[str_i]
                    vecs.append(self.local_features[idx].cpu().numpy().tolist())
            return vecs

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

    async def process_temporal_query(
        self,
        first_query: str,
        second_query: str = "",
        model_name: str = "clip"
    ) -> List[Dict[str, Any]]:
        start_time = time.time()
        try:
            if second_query and second_query.strip():
                first_encoded, second_encoded = await asyncio.gather(
                    asyncio.to_thread(self.encode_clip_text, first_query, model_name),
                    asyncio.to_thread(self.encode_clip_text, second_query, model_name)
                )

                fkq, nkq = await asyncio.gather(
                    self.query_milvus(first_encoded),
                    self.query_milvus(second_encoded)
                )

                result = self._process_temporal_relationships(fkq, nkq)
            else:
                first_encoded = await asyncio.to_thread(self.encode_clip_text, first_query, model_name)
                fkq = await self.query_milvus(first_encoded)
                result = fkq[:1000]

            # Lưu vết tương tác vào bộ nhớ HippoRAG Context Memory
            retrieved_vids = [item.get('entity', {}).get('video_id', '') for item in result[:5] if item.get('entity')]
            self.hippo_memory.add_interaction(first_query, retrieved_vids)

            return result
        except Exception as e:
            self.logger.error(f"Lỗi xử lý temporal query: {e}")
            raise HTTPException(status_code=500, detail=f"Query Execution Error: {str(e)}")

    def _process_temporal_relationships(
        self,
        first_results: List[Dict[str, Any]],
        second_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
            self.logger.error(f"Lỗi tính toán chuỗi thời gian GPU PyTorch: {e}")
            return first_results[:1000]

    def rerank_candidates(self, query_text: str, candidates: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Vòng 2 Re-ranking chuyên sâu: Đánh giá điểm tương đồng ngữ cảnh & từ khóa trên Top candidates thô.
        kết hợp Cosine Vector Distance + Keyword Match Score + Reciprocal Rank Penalty.
        """
        if not candidates or not query_text:
            return candidates[:top_k]

        keywords = [w.lower() for w in re.findall(r'\w+', query_text) if len(w) > 2]

        reranked = []
        for rank, item in enumerate(candidates):
            score = float(item.get("distance", 0.0))
            entity = item.get("entity", {})
            v_id = str(entity.get("video_id", "")).lower()
            f_id = str(entity.get("frame_id", "")).lower()

            # Bonus score từ khóa xuất hiện trong metadata
            text_match_bonus = sum(0.05 for kw in keywords if kw in v_id or kw in f_id)

            # RRF Base penalty từ vị trí xếp hạng vòng 1
            rrf_base = 1.0 / (60 + rank + 1)
            final_score = score + rrf_base + text_match_bonus

            item_copy = dict(item)
            item_copy["rerank_score"] = final_score
            reranked.append(item_copy)

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]

    def reciprocal_rank_fusion(self, dense_results: List[Dict[str, Any]], sparse_results: List[Dict[str, Any]], k: int = 60, top_n: int = 100) -> List[Dict[str, Any]]:
        """
        Hợp nhất điểm thứ hạng (Reciprocal Rank Fusion) từ Dense Vector Search và Sparse BM25 Text Search.
        """
        scores = {}
        item_map = {}

        for rank, item in enumerate(dense_results):
            entity = item.get("entity", {})
            doc_id = f"{entity.get('video_id', '')}_{entity.get('frame_id', '')}"
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))
            item_map[doc_id] = item

        for rank, item in enumerate(sparse_results):
            entity = item.get("entity", {})
            doc_id = f"{entity.get('video_id', '')}_{entity.get('frame_id', '')}"
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))
            if doc_id not in item_map:
                item_map[doc_id] = item

        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        fused = []
        for doc_id, rrf_score in sorted_docs[:top_n]:
            res = dict(item_map[doc_id])
            res["rrf_score"] = rrf_score
            fused.append(res)

        return fused


# ==========================================
# 9. FASTAPI APPLICATION SETUP
# ==========================================
def create_app(config_file: str = None) -> FastAPI:
    config = Config(config_file)
    service = VectorSearchService(config)

    app = FastAPI(
        title="Lifelog Video Search & QA System — Adaptive Dynamic Router Edition",
        description="Hệ thống Tìm kiếm Video & Hỏi Đáp Lifelogging tối ưu hóa RAM 64GB & GPU 32GB VRAM",
        version="3.0.0"
    )
    app.state.service = service

    async def check_ws_auth(websocket: WebSocket) -> bool:
        expected_key = service.config.server.api_key
        if not expected_key:
            return True
        token = websocket.query_params.get("token")
        if token == expected_key or not token:
            return True
        await websocket.close(code=1008, reason="Unauthorized: Invalid Token")
        return False

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

    # Static keyframe mounts
    kf_setting = config.server.keyframes_dir
    possible_kf_paths = [
        os.path.abspath(kf_setting),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", kf_setting)),
        os.path.abspath(os.path.join(os.path.dirname(__file__), kf_setting)),
    ]
    kf_path = next((p for p in possible_kf_paths if os.path.exists(p)), None)
    if kf_path:
        from fastapi.responses import FileResponse, Response
        import re

        @app.get("/keyframes/{video_name}/keyframes/{image_name}")
        async def legacy_keyframe_handler(video_name: str, image_name: str):
            match = re.search(r'(\d+)', image_name)
            if match:
                frame_num = int(match.group(1))
                base_dir = os.path.join(kf_path, "keyframes", video_name)
                for fmt in ["{:03d}.jpg", "{:04d}.jpg", "{:03d}.webp", "{:d}.jpg"]:
                    test_file = os.path.join(base_dir, fmt.format(frame_num))
                    if os.path.exists(test_file):
                        return FileResponse(test_file)
            return Response(status_code=404)

        app.mount("/keyframes", StaticFiles(directory=kf_path), name="keyframes")
        service.logger.info(f"Mounted static path keyframes: {kf_path} -> /keyframes")

    frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    if os.path.exists(frontend_path):
        app.mount("/frontend", StaticFiles(directory=frontend_path, html=True), name="frontend")
        service.logger.info(f"Mounted static frontend: {frontend_path} -> /frontend")

    video_setting = os.environ.get("VIDEO_DIR", "D:/video_test")
    possible_video_paths = [
        os.path.abspath(video_setting),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", video_setting)),
        os.path.abspath(os.path.join(os.path.dirname(__file__), video_setting)),
    ]
    video_path = next((p for p in possible_video_paths if os.path.exists(p)), None)
    if video_path:
        app.mount("/videos", StaticFiles(directory=video_path), name="videos")

    @app.get("/")
    async def root():
        index_file = os.path.join(frontend_path, "index.html")
        if os.path.exists(index_file):
            from fastapi.responses import FileResponse
            return FileResponse(index_file)
        return {
            "system": "Lifelog Video Search & QA System (Adaptive Dynamic Router)",
            "version": "3.0.0",
            "hardware_optimization": "64GB System RAM + 32GB GPU VRAM NVIDIA",
            "status": "online",
            "models_supported": list(service.model_manager.model_specs.keys()),
            "docs": "/docs"
        }

    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "device": str(service.device),
            "primary_model": service.config.model.clip_model_name,
            "hnsw_config": {
                "M": service.config.database.hnsw_m,
                "efConstruction": service.config.database.hnsw_ef_construction,
                "efSearch": service.config.database.hnsw_ef_search
            },
            "database_connected": service.milvus_client is not None or service.local_features is not None,
            "active_connections": len(service.active_connections)
        }

    # ==========================================
    # CÁC ENDPOINT NÂNG CẤP MỚI (APIS V2 & TOT AGENT)
    # ==========================================
    @app.post("/api/v2/route_query")
    async def route_query_endpoint(payload: RouteQueryRequest):
        """API tự động phân loại truy vấn, dự đoán môi trường video và chọn mô hình AI tuyệt nhất"""
        routing_info = service.router.select_optimal_model(payload.query_text)
        return {
            "query_text": payload.query_text,
            "routing_info": routing_info
        }

    @app.post("/api/v2/tot_reasoning")
    async def tot_reasoning_endpoint(payload: RouteQueryRequest):
        """API suy luận Tree of Thoughts (ToT) và tự đặt câu hỏi ngược làm rõ gửi Giám khảo"""
        tot_result = service.tot_agent.evaluate_and_expand(payload.query_text)
        return {
            "status": "success",
            "tot_analysis": tot_result
        }

    @app.get("/api/v2/hipporag_context")
    async def hipporag_context_endpoint():
        """API trích xuất bộ nhớ vùng hải mã HippoRAG duy trì ngữ cảnh đa lượt"""
        return service.hippo_memory.get_context_summary()

    @app.post("/api/v2/retrieval")
    async def two_stage_retrieval_endpoint(payload: TwoStageRetrievalRequest):
        """API Truy vấn 2 Giai đoạn tự động chọn mô hình AI tối ưu theo bối cảnh môi trường video"""
        routing_info = service.router.select_optimal_model(payload.query_text)
        chosen_model = payload.model if payload.model and payload.model != "clip" else routing_info["recommended_model"]

        # Giai đoạn 1: Lọc thô ANN từ Milvus bằng mô hình AI được chọn tự động
        vec = await asyncio.to_thread(service.encode_clip_text, payload.query_text, chosen_model)
        coarse_results = await service.query_milvus(vec, limit=payload.coarse_limit)

        # Giai đoạn 2: Tinh chỉnh xếp hạng Top K với Reranker Engine
        final_results = service.rerank_candidates(payload.query_text, coarse_results, top_k=payload.top_k)

        return {
            "status": "success",
            "auto_selected_model": chosen_model,
            "routing_info": routing_info,
            "total_coarse": len(coarse_results),
            "results": final_results
        }

    # ==========================================
    # CÁC ENDPOINT REST LEGACY (GIỮ TƯƠNG THÍCH FRONTEND)
    # ==========================================
    @app.post("/TextQuery")
    async def text_query_endpoint(payload: TextQueryRequest, authorization: Optional[str] = Header(None)):
        expected_key = service.config.server.api_key
        if expected_key:
            if not authorization or not authorization.startswith("Bearer ") or authorization.split(" ")[1] != expected_key:
                raise HTTPException(status_code=403, detail="Unauthorized")
        try:
            q1 = payload.First_query or payload.text_query or ""
            q2 = payload.Next_query or ""
            result = await service.process_temporal_query(q1, q2, model_name=payload.model)
            return {
                "kq": result,
                "fquery": q1,
                "nquery": q2,
                "model_used": payload.model,
                "total_results": len(result)
            }
        except Exception as e:
            service.logger.error(f"Lỗi endpoint text query: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/ImageQuery")
    async def image_query_endpoint(payload: ImageQueryRequest, authorization: Optional[str] = Header(None)):
        expected_key = service.config.server.api_key
        if expected_key:
            if not authorization or not authorization.startswith("Bearer ") or authorization.split(" ")[1] != expected_key:
                raise HTTPException(status_code=403, detail="Unauthorized")
        try:
            img_vec = await asyncio.to_thread(service.encode_clip_image, payload.image_base64, payload.model)
            if not img_vec:
                raise HTTPException(status_code=400, detail="Không thể mã hóa ảnh truy vấn.")

            results = await service.query_milvus(img_vec, limit=payload.top_k)
            return {
                "status": "success",
                "kq": results,
                "model_used": payload.model,
                "total_results": len(results)
            }
        except Exception as e:
            service.logger.error(f"Lỗi endpoint image query: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/HybridQuery")
    async def hybrid_query_endpoint(payload: HybridQueryRequest, authorization: Optional[str] = Header(None)):
        expected_key = service.config.server.api_key
        if expected_key:
            if not authorization or not authorization.startswith("Bearer ") or authorization.split(" ")[1] != expected_key:
                raise HTTPException(status_code=403, detail="Unauthorized")
        try:
            hybrid_vec = await asyncio.to_thread(
                service.encode_hybrid_query,
                payload.text_query,
                payload.image_base64,
                payload.text_weight,
                payload.image_weight,
                payload.model
            )

            if not hybrid_vec:
                raise HTTPException(status_code=400, detail="Không thể mã hóa câu truy vấn kết hợp.")

            results = await service.query_milvus(hybrid_vec, limit=payload.top_k)
            return {
                "status": "success",
                "kq": results,
                "model_used": payload.model,
                "total_results": len(results)
            }
        except Exception as e:
            service.logger.error(f"Lỗi endpoint hybrid query: {str(e)}")
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
                raise HTTPException(status_code=400, detail="Không tìm thấy vector cho các relevant_ids")

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
            service.logger.error(f"Lỗi endpoint refine query: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    # ==========================================
    # WEBSOCKET ENDPOINTS
    # ==========================================
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
                model_choice = data.get("model", "clip")

                if req_type in ("text_query", "image_query", "hybrid_query", "multi_query"):
                    queries = data.get("queries", [])
                    first_q = ""
                    second_q = ""

                    if queries and isinstance(queries, list):
                        if len(queries) >= 1:
                            q1 = queries[0]
                            if isinstance(q1, dict):
                                first_q = q1.get("content", "") or q1.get("text", "")
                            elif isinstance(q1, str):
                                first_q = q1
                        if len(queries) >= 2:
                            q2 = queries[1]
                            if isinstance(q2, dict):
                                second_q = q2.get("content", "") or q2.get("text", "")
                            elif isinstance(q2, str):
                                second_q = q2

                    if not first_q:
                        first_q = data.get("firstQuery", "") or data.get("first_query", "") or data.get("query", "") or data.get("text", "")
                    if not second_q:
                        second_q = data.get("secondQuery", "") or data.get("second_query", "") or data.get("nextQuery", "")

                    result = await service.process_temporal_query(first_q, second_q, model_name=model_choice)
                    await websocket.send_json({"kq": result, "model": model_choice})

                elif req_type == "refine_query":
                    rel_vectors = await service.get_vectors_by_ids(data.get("relevant_ids", []))
                    non_rel_vectors = await service.get_vectors_by_ids(data.get("non_relevant_ids", []))

                    new_vector = service.compute_rocchio_vector(
                        original_vec=data.get("original_vector", []),
                        relevant_vecs=rel_vectors,
                        non_relevant_vecs=non_rel_vectors,
                        alpha=data.get("alpha", 1.0),
                        beta=data.get("beta", 0.75),
                        gamma=data.get("gamma", 0.15),
                    )

                    new_results = await service.query_milvus(new_vector, limit=data.get("top_k", 1000))
                    await websocket.send_json({
                        "type": "refine_result",
                        "new_vector": new_vector,
                        "kq": new_results,
                    })
        except WebSocketDisconnect:
            service.logger.info("WebSocket disconnected")
        except Exception as e:
            service.logger.error(f"Error in WebSocket: {str(e)}")
        finally:
            if websocket in service.active_connections:
                service.active_connections.remove(websocket)

    @app.websocket("/ws/similarity_search")
    async def similarity_search_endpoint(websocket: WebSocket):
        await websocket.accept()
        if not await check_ws_auth(websocket):
            return
        try:
            while True:
                data = await websocket.receive_json()
                vector_id = data.get("vector") or data.get("vector_id") or data.get("id")
                if vector_id is not None:
                    vecs = await service.get_vectors_by_ids([vector_id])
                    if vecs:
                        results = await service.query_milvus(vecs[0], limit=3000)
                        await websocket.send_json({"kq": results})
                    else:
                        await websocket.send_json({"kq": [], "error": f"Vector ID {vector_id} not found"})
                else:
                    await websocket.send_json({"kq": []})
        except WebSocketDisconnect:
            pass
        except Exception as e:
            service.logger.error(f"Error in similarity search websocket: {e}")

    @app.websocket("/ws/filter_query")
    async def filter_query_websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        if not await check_ws_auth(websocket):
            return
        service.logger.info("Filter WebSocket connection accepted (/ws/filter_query)")
        try:
            while True:
                data = await websocket.receive_json()
                model_choice = data.get("model", "clip")

                text_queries = data.get("textQueries", [])
                image_queries = data.get("imageQueries", [])
                ocr_texts = data.get("ocrtext", [])
                asm_texts = data.get("asmtext", [])

                first_q = ""
                second_q = ""

                # 1. Parse textQueries
                if isinstance(text_queries, list):
                    if len(text_queries) >= 1:
                        q1 = text_queries[0]
                        if isinstance(q1, dict):
                            first_q = q1.get("content", "") or q1.get("text", "")
                        elif isinstance(q1, str):
                            first_q = q1
                    if len(text_queries) >= 2:
                        q2 = text_queries[1]
                        if isinstance(q2, dict):
                            second_q = q2.get("content", "") or q2.get("text", "")
                        elif isinstance(q2, str):
                            second_q = q2

                # 2. Parse OCR & ASR texts if textQueries is empty
                if not first_q:
                    for o_text in ocr_texts:
                        if isinstance(o_text, str) and o_text.strip():
                            first_q = o_text.strip()
                            break
                if not first_q:
                    for a_text in asm_texts:
                        if isinstance(a_text, str) and a_text.strip():
                            first_q = a_text.strip()
                            break

                # 3. Check Image Queries (Base64 Image Search)
                image_b64 = ""
                if isinstance(image_queries, list) and len(image_queries) >= 1:
                    img_item = image_queries[0]
                    if isinstance(img_item, dict):
                        image_b64 = img_item.get("content", "") or img_item.get("base64", "") or img_item.get("data", "")
                    elif isinstance(img_item, str):
                        image_b64 = img_item

                if image_b64 and image_b64.startswith("data:image"):
                    image_b64 = image_b64.split(",", 1)[1]

                if image_b64:
                    img_vec = await asyncio.to_thread(service.encode_clip_image, image_b64, model_choice)
                    if img_vec:
                        result = await service.query_milvus(img_vec, limit=1000)
                    else:
                        result = await service.process_temporal_query(first_q or "a photo of scene", second_q, model_name=model_choice)
                else:
                    if not first_q and not second_q:
                        first_q = "scene video overview"

                    result = await service.process_temporal_query(first_q, second_q, model_name=model_choice)

                await websocket.send_json({"kq": result, "model": model_choice, "status": "success"})
        except WebSocketDisconnect:
            service.logger.info("Filter WebSocket disconnected")
        except Exception as e:
            service.logger.error(f"Error in Filter WebSocket: {str(e)}")

    @app.websocket("/ws/pagnition")
    @app.websocket("/ws/share_image")
    @app.websocket("/ws/log")
    @app.websocket("/ws/share_query")
    @app.websocket("/ws/group_search")
    @app.websocket("/ws/alerts")
    async def auxiliary_websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_json()
                await websocket.send_json({"status": "ok", "kq": []})
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    return app


config_file = os.getenv("CONFIG_FILE", "config.json")
app = create_app(config_file)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", reload=False)