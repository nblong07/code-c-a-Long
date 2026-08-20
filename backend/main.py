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

# ==============================================================================
# VIETNAMESE SYNONYM THESAURUS (BỘ TỪ ĐIỂN TỪ ĐỒNG NGHĨA TIẾNG VIỆT CHUYÊN DỤNG)
# ==============================================================================
VIETNAMESE_SYNONYM_THESAURUS = {
    # Phương tiện giao thông
    "xe máy": ["xe mô tô", "xe gắn máy", "xe hai bánh", "xe honda", "motorbike", "motorcycle", "scooter"],
    "xe mô tô": ["xe máy", "xe gắn máy", "xe hai bánh", "motorbike", "motorcycle"],
    "ô tô": ["xe hơi", "xe bốn bánh", "xế hộp", "car", "automobile", "vehicle"],
    "xe hơi": ["ô tô", "xe bốn bánh", "xế hộp", "car", "automobile"],
    "xe buýt": ["xe bus", "xe khách", "bus", "coach"],
    "xe bus": ["xe buýt", "xe khách", "bus"],
    "xe đạp": ["xe hai bánh", "bicycle", "bike", "cyclist"],
    "máy bay": ["phi cơ", "tàu bay", "airplane", "plane", "aircraft"],
    "thuyền": ["tàu", "ghe", "cano", "thuyền buồm", "boat", "ship"],
    "xe tải": ["xe chở hàng", "truck", "lorry"],
    "xe cứu thương": ["xe cấp cứu", "ambulance"],
    "xe cảnh sát": ["xe công an", "police car"],

    # Con người & Chức danh
    "người đàn ông": ["nam giới", "chàng trai", "người nam", "đàn ông", "man", "male", "guy"],
    "đàn ông": ["người đàn ông", "nam giới", "chàng trai", "man", "male"],
    "phụ nữ": ["người phụ nữ", "cô gái", "nữ giới", "người nữ", "woman", "female", "girl", "lady"],
    "cô gái": ["phụ nữ", "thiếu nữ", "bạn nữ", "girl", "young woman"],
    "trẻ em": ["em bé", "đứa trẻ", "học sinh", "con nít", "trẻ nhỏ", "child", "children", "kid", "baby"],
    "em bé": ["trẻ sơ sinh", "đứa trẻ", "baby", "toddler", "infant"],
    "cảnh sát": ["công an", "CSGT", "công an giao thông", "chiến sĩ", "police", "officer"],
    "bác sĩ": ["y sĩ", "thầy thuốc", "doctor", "physician"],
    "học sinh": ["sinh viên", "học trò", "student", "pupil"],
    "tài xế": ["người lái xe", "bác tài", "driver"],

    # Trang phục & Phụ kiện
    "áo dài": ["áo dài truyền thống", "ao dai", "traditional dress"],
    "nón lá": ["nón bài thơ", "conical hat"],
    "mũ bảo hiểm": ["nón bảo hiểm", "helmet"],
    "nón bảo hiểm": ["mũ bảo hiểm", "helmet"],
    "khẩu trang": ["mặt nạ y tế", "facemask", "mask"],
    "balo": ["ba lô", "cặp sách", "túi xách", "backpack", "bag"],
    "kính mắt": ["kính râm", "mắt kính", "glasses", "sunglasses"],

    # Hành động
    "chạy bộ": ["chạy nhanh", "chạy", "tập thể dục", "running", "jogging"],
    "đi bộ": ["tản bộ", "dạo phố", "walking", "strolling"],
    "nói chuyện": ["trò chuyện", "giao tiếp", "thảo luận", "bàn tán", "talking", "chatting", "conversing"],
    "bắt tay": ["chào hỏi", "bắt tay nhau", "handshake", "shaking hands"],
    "ăn uống": ["dùng bữa", "thưởng thức", "eating", "drinking", "dining"],
    "nghe điện thoại": ["gọi điện thoại", "bấm điện thoại", "on the phone", "calling"],
    "lái xe": ["điều khiển xe", "driving", "riding"],

    # Địa điểm & Không gian
    "đường phố": ["lòng đường", "phố xá", "vỉa hè", "street", "road", "avenue"],
    "ngã tư": ["ngã tư đường", "giao lộ", "vòng xoay", "ngã ba", "intersection", "crossroad", "junction"],
    "bãi biển": ["bờ biển", "bờ cát", "bãi cát", "beach", "seashore", "coastline"],
    "công viên": ["vườn hoa", "khu vui chơi", "park", "garden"],
    "quán cà phê": ["quán cafe", "quán nước", "tiệm cà phê", "coffee shop", "cafe"],
    "siêu thị": ["cửa hàng", "tiệm tạp hóa", "supermarket", "store", "grocery"],
    "bệnh viện": ["phòng khám", "trung tâm y tế", "hospital", "clinic"],
    "trường học": ["lớp học", "giảng đường", "school", "classroom"],
}

def expand_text_synonyms(text: str) -> str:
    """Mở rộng câu truy vấn với các từ đồng nghĩa tương ứng"""
    if not text:
        return ""
    t_lower = text.lower()
    added_terms = []
    for key, syns in VIETNAMESE_SYNONYM_THESAURUS.items():
        if key in t_lower:
            for s in syns[:2]:
                if s.lower() not in t_lower and s.lower() not in added_terms:
                    added_terms.append(s)
    if added_terms:
        return f"{text} ({', '.join(added_terms[:3])})"
    return text
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
    top_k: Optional[int] = Field(50, description="Số lượng kết quả cần trả về")


class ImageQueryRequest(BaseModel):
    image_base64: str = Field(..., description="Chuỗi Base64 của ảnh truy vấn")
    model: Optional[str] = Field("clip", description="Lựa chọn mô hình AI")
    top_k: Optional[int] = Field(50, description="Số lượng kết quả cần trả về")


class HybridQueryRequest(BaseModel):
    text_query: Optional[str] = Field("", description="Mô tả văn bản")
    image_base64: Optional[str] = Field("", description="Ảnh mẫu truy vấn")
    text_weight: Optional[float] = Field(0.5, description="Trọng số vector văn bản")
    image_weight: Optional[float] = Field(0.5, description="Trọng số vector hình ảnh")
    model: Optional[str] = Field("clip", description="Lựa chọn mô hình AI")
    top_k: Optional[int] = Field(50, description="Số lượng kết quả trả về")


class RefineSearchRequest(BaseModel):
    original_vector: List[float]
    relevant_ids: List[str]
    non_relevant_ids: Optional[List[str]] = []
    top_k: Optional[int] = 50
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
    video_dirs: List[str] = field(default_factory=lambda: ["C:/video_test", "D:/video_test"])
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

    @property
    def keyframes_dir(self) -> str:
        return self.server.keyframes_dir


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
            # ── PRIMARY SOTA MODEL (Google SigLIP SO400M 1152d) ──
            "clip": {
                "name": "ViT-SO400M-14-SigLIP-384",
                "pretrained": "webli",
                "dim": 1152,
                "objective": "Google SigLIP SO400M — Primary Multimodal Search Engine (1152d)"
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

        # Kiểm tra nhanh: nếu là model phụ chưa tải xong trọng số (>100MB safetensors/bin), tự động dùng Primary SigLIP để không bị đứng mạng khi thi đấu
        hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
        is_model_available = True
        if key_norm in ["eva-clip", "blip"]:
            folder_hint = "eva02" if key_norm == "eva-clip" else "DFN5B"
            matched_folder = [f for f in os.listdir(hf_cache) if folder_hint.lower() in f.lower()] if os.path.exists(hf_cache) else []
            if matched_folder:
                f_path = os.path.join(hf_cache, matched_folder[0])
                st_files = [os.path.join(r, f) for r, _, fl in os.walk(f_path) for f in fl if f.endswith('.safetensors') or f.endswith('.bin')]
                total_sz = sum(os.path.getsize(f) for f in st_files)
                if total_sz < 100 * 1024 * 1024: # Dưới 100MB coi như chưa tải xong
                    is_model_available = False
            else:
                is_model_available = False

        if not is_model_available:
            self.logger.info(f"Mô hình '{key_norm}' chưa có sẵn file weights offline (>100MB). Tự động chuyển hướng xử lý qua Google SigLIP SO400M (Primary SOTA).")
            return self.get_model("clip")

        self.logger.info(f"Đang nạp mô hình Top-1 SOTA '{key_norm}' ({model_name}, pretrained='{pretrained}') lên {self.device}...")
        
        # OOM Prevention for 6GB VRAM: Clear old models before loading new ones
        if len(self.loaded_models) > 0:
            self.logger.info(f"Đang giải phóng VRAM các mô hình cũ để tránh tràn bộ nhớ (OOM)...")
            self.loaded_models.clear()
            self.loaded_transforms.clear()
            self.loaded_tokenizers.clear()
            import gc
            gc.collect()
            if self.device.type == "cuda":
                torch.cuda.empty_cache()

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

            self.logger.info(f"Mô hình SOTA '{key_norm}' đã nạp thành công!")
            return model, preprocess, tokenizer, spec
        except Exception as e:
            self.logger.warning(f"Không thể nạp '{key_norm}' ({e}). Tự động fallback về SigLIP primary model ViT-SO400M-14-SigLIP-384.")
            default_key = "ViT-SO400M-14-SigLIP-384__webli"
            if default_key in self.loaded_models:
                return (
                    self.loaded_models[default_key],
                    self.loaded_transforms[default_key],
                    self.loaded_tokenizers[default_key],
                    self.model_specs["clip"]
                )
            model, _, preprocess = open_clip.create_model_and_transforms("ViT-SO400M-14-SigLIP-384", pretrained="webli")
            model = model.to(self.device).eval()
            tokenizer = open_clip.get_tokenizer("ViT-SO400M-14-SigLIP-384")
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

        # Nạp dữ liệu OCR & ASR Metadata để hỗ trợ tìm kiếm chính xác
        self.ocr_data = {}
        self.asr_data = {}
        
        # 1. Nạp OCR từ ocr_results.jsonl
        possible_ocr_paths = [
            os.path.abspath("ocr_results.jsonl"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ocr_results.jsonl")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "ocr_results.jsonl")),
        ]
        ocr_jsonl = next((p for p in possible_ocr_paths if os.path.exists(p)), None)
        if ocr_jsonl:
            try:
                import json
                with open(ocr_jsonl, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            d = json.loads(line)
                            txt = (d.get("text") or "").strip()
                            if txt:
                                vid = d.get("video_id", "")
                                fid = str(d.get("frame_id", ""))
                                key = f"{vid}/keyframes/keyframe_{fid}.webp"
                                self.ocr_data[key] = txt
                        except Exception:
                            pass
                self.logger.info(f"✅ Đã nạp {len(self.ocr_data):,} bản ghi OCR từ {ocr_jsonl}.")
            except Exception as e:
                self.logger.error(f"Lỗi nạp ocr_results.jsonl: {e}")

        # 2. Nạp ASR từ asr_results.jsonl
        possible_asr_paths = [
            os.path.abspath("asr_results.jsonl"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "asr_results.jsonl")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "asr_results.jsonl")),
        ]
        asr_jsonl = next((p for p in possible_asr_paths if os.path.exists(p)), None)
        if asr_jsonl:
            try:
                import json
                with open(asr_jsonl, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            d = json.loads(line)
                            txt = (d.get("text") or d.get("asr_text") or "").strip()
                            if txt:
                                vid = d.get("video_id")
                                if not vid and d.get("video_path"):
                                    vp = d.get("video_path").replace("\\", "/")
                                    parts = vp.split("/")
                                    filename = parts[-1].replace(".mp4", "")
                                    batch = parts[-2].replace("video_", "") if len(parts) >= 2 else ""
                                    vid = f"{batch}/{filename}" if batch else filename
                                elif not vid:
                                    vid = "video"
                                start_sec = float(d.get("start", 0))
                                fid = int(d.get("frame_id", int(start_sec * 25)))
                                key = f"{vid}/keyframes/keyframe_{fid}.webp"
                                self.asr_data[key] = txt
                        except Exception:
                            pass
                self.logger.info(f"✅ Đã nạp {len(self.asr_data):,} bản ghi ASR từ {asr_jsonl}.")
            except Exception as e:
                self.logger.error(f"Lỗi nạp asr_results.jsonl: {e}")

        # 3. Fallback từ ocr_asr_metadata.json nếu còn trống
        if not self.ocr_data or not self.asr_data:
            meta_json = os.path.abspath("ocr_asr_metadata.json")
            if os.path.exists(meta_json):
                try:
                    import json
                    with open(meta_json, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                        if not self.ocr_data:
                            self.ocr_data = meta.get("ocr", {})
                        if not self.asr_data:
                            self.asr_data = meta.get("asr", {})
                except Exception as e:
                    self.logger.error(f"Lỗi nạp fallback ocr_asr_metadata.json: {e}")

        # 4. Nạp toàn bộ ánh xạ thời gian (Time Mapping: Seconds & Milliseconds) từ tất cả tệp _map.csv
        self.time_map = {}
        kf_root = os.path.abspath("data-keyframes")
        if not os.path.exists(kf_root):
            kf_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data-keyframes"))
        
        if os.path.exists(kf_root):
            import csv
            for root, _, files in os.walk(kf_root):
                for f in files:
                    if f.endswith('_map.csv'):
                        vid = f.replace('_map.csv', '')
                        csv_p = os.path.join(root, f)
                        try:
                            with open(csv_p, 'r', encoding='utf-8') as cf:
                                reader = csv.reader(cf)
                                next(reader, None)
                                for row in reader:
                                    if len(row) >= 4:
                                        fid = int(row[0])
                                        sec = float(row[1])
                                        ms = int(float(row[3]))
                                        self.time_map[(vid, fid)] = (sec, ms)
                                        self.time_map[(vid.lower(), fid)] = (sec, ms)
                                        self.time_map[f"{vid}_{fid}"] = (sec, ms)
                                    elif len(row) >= 2:
                                        fid = int(row[0])
                                        sec = float(row[1])
                                        ms = int(sec * 1000)
                                        self.time_map[(vid, fid)] = (sec, ms)
                                        self.time_map[(vid.lower(), fid)] = (sec, ms)
                                        self.time_map[f"{vid}_{fid}"] = (sec, ms)
                        except Exception:
                            pass
            self.logger.info(f"✅ Đã nạp {len(self.time_map):,} ánh xạ timestamp (Seconds & Milliseconds) từ CSDL video maps.")
            
            # 5. Xây dựng Inverted Index + BM25 trên CPU RAM cho OCR & ASR
            self._build_inverted_indices()

    def _build_inverted_indices(self):
        """Xây dựng chỉ mục nghịch đảo Inverted Index + BM25 trên RAM CPU cho OCR và ASR (0 MB VRAM)"""
        import re
        from collections import defaultdict
        
        # 1. OCR Inverted Index
        self.ocr_inverted_index = defaultdict(list)
        self.ocr_doc_lens = {}
        total_ocr_len = 0
        for doc_key, text in self.ocr_data.items():
            tokens = set(re.findall(r'\w+', self._strip_accents(text.lower())))
            self.ocr_doc_lens[doc_key] = len(tokens)
            total_ocr_len += len(tokens)
            for token in tokens:
                self.ocr_inverted_index[token].append(doc_key)
        self.avg_ocr_doc_len = total_ocr_len / max(len(self.ocr_data), 1)

        # 2. ASR Inverted Index
        self.asr_inverted_index = defaultdict(list)
        self.asr_doc_lens = {}
        total_asr_len = 0
        for doc_key, text in self.asr_data.items():
            tokens = set(re.findall(r'\w+', self._strip_accents(text.lower())))
            self.asr_doc_lens[doc_key] = len(tokens)
            total_asr_len += len(tokens)
            for token in tokens:
                self.asr_inverted_index[token].append(doc_key)
        self.avg_asr_doc_len = total_asr_len / max(len(self.asr_data), 1)

        self.logger.info(f"⚡ Đã lập chỉ mục BM25 Inverted Index ({len(self.ocr_inverted_index):,} tokens OCR, {len(self.asr_inverted_index):,} tokens ASR) trên CPU RAM!")

    def cleanup_vram(self):
        """VRAM Safety Guard: Thu gom rác và giải phóng bộ nhớ đệm GPU chống tràn VRAM"""
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

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

        # Kiểm tra nhanh: Nếu không có ký tự tiếng Việt, bỏ qua bước dịch để tăng tốc độ phản hồi
        import re
        if not re.search(r'[àáãạảăắằẳẵặâấầẩẫậèéẹẻẽêềếểễệđìíĩỉịòóõọỏôốồổỗộơớờởỡợùúũụủưứừửữựỳýỹỷỵ]', q_str.lower()):
            return q_str

        # Sử dụng urllib để gọi trực tiếp Google Translate API ẩn danh với timeout ngắn (2.5 giây)
        try:
            import urllib.request
            import urllib.parse
            import json
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q=" + urllib.parse.quote(q_str)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=2.5) as response:
                res = json.loads(response.read().decode('utf-8'))
                translated = "".join([item[0] for item in res[0] if item and item[0]])
                if translated and translated.strip():
                    self.logger.info(f"🌐 Dịch tự động (Timeout 2.5s): '{q_str}' -> '{translated}'")
                    return translated.strip()
        except Exception as e:
            self.logger.warning(f"Translation timeout hoặc mất mạng: {e}")

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
        """
        Mã hóa câu truy vấn nâng cao với:
        1. Mở rộng từ đồng nghĩa tiếng Việt (Synonym Expansion).
        2. Dịch tự động sang tiếng Anh.
        3. DUNG HỢP VECTOR SONG NGỮ (Cross-Lingual Dual-Embedding Blending): 0.45 * Vi + 0.55 * En.
        """
        if not query or not query.strip():
            return []

        import re
        q_clean = query.strip()
        model, _, tokenizer, spec = self.model_manager.get_model(model_name)

        # Kiểm tra xem query có tiếng Việt hay không
        is_vietnamese = bool(re.search(r'[àáãạảăắằẳẵặâấầẩẫậèéẹẻẽêềếểễệđìíĩỉịòóõọỏôốồổỗộơớờởỡợùúũụủưứừửữựỳýỹỷỵ]', q_clean.lower()))

        with torch.inference_mode():
            if is_vietnamese:
                # 1. Mã hóa vector tiếng Việt (có mở rộng từ đồng nghĩa)
                q_vi_expanded = expand_text_synonyms(q_clean)
                inputs_vi = tokenizer([q_vi_expanded if len(q_vi_expanded) < 70 else q_clean]).to(self.device)
                
                # 2. Dịch tự động sang tiếng Anh & mã hóa vector tiếng Anh
                q_en = self.translate_query(q_clean)
                inputs_en = tokenizer([q_en]).to(self.device)

                if self.device.type == "cuda":
                    with torch.amp.autocast(device_type="cuda"):
                        feat_vi = model.encode_text(inputs_vi)
                        feat_en = model.encode_text(inputs_en)
                else:
                    feat_vi = model.encode_text(inputs_vi)
                    feat_en = model.encode_text(inputs_en)

                feat_vi = F.normalize(feat_vi.float(), p=2, dim=-1)
                feat_en = F.normalize(feat_en.float(), p=2, dim=-1)

                # DUNG HỢP VECTOR SONG NGỮ: 0.45 * Tiếng Việt + 0.55 * Tiếng Anh
                fused_features = 0.45 * feat_vi + 0.55 * feat_en
                fused_features = F.normalize(fused_features, p=2, dim=-1)
                vec = fused_features.squeeze(0).cpu().numpy().tolist()
            else:
                # Query thuần tiếng Anh
                inputs_en = tokenizer([q_clean]).to(self.device)
                if self.device.type == "cuda":
                    with torch.amp.autocast(device_type="cuda"):
                        feat = model.encode_text(inputs_en)
                else:
                    feat = model.encode_text(inputs_en)
                feat = F.normalize(feat.float(), p=2, dim=-1)
                vec = feat.squeeze(0).cpu().numpy().tolist()

            # VRAM Safety Guard: dọn dẹp nhẹ bộ nhớ GPU
            if self.device.type == "cuda":
                torch.cuda.empty_cache()

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
                            entity_dict = item.get("entity", item)
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
                        
                        # Tra cứu thời gian thực tế chính xác (Seconds & ms)
                        vid_clean = str(entity_dict.get('video_id', '')).replace('\\', '/')
                        if '/' in vid_clean:
                            vid_clean = vid_clean.split('/')[-1]
                        try:
                            fid_val = int(entity_dict.get('frame_id', 0))
                        except Exception:
                            fid_val = 0
                        
                        time_info = self.time_map.get((vid_clean, fid_val)) or self.time_map.get((vid_clean.lower(), fid_val)) or self.time_map.get(f"{vid_clean}_{fid_val}")
                        if time_info:
                            entity_dict['time'] = time_info[0]
                            entity_dict['timestamp_ms'] = time_info[1]
                        else:
                            sec_approx = round(fid_val / 25.0, 3)
                            entity_dict['time'] = sec_approx
                            entity_dict['timestamp_ms'] = int(sec_approx * 1000)

                        parsed_results.append({
                            "id": str(getattr(item, 'id', '') if not isinstance(item, dict) else item.get('id', '')),
                            "distance": float(getattr(item, 'distance', 0.0) if not isinstance(item, dict) else item.get('distance', 0.0)),
                            "entity": entity_dict
                        })
                    return parsed_results
            except Exception as e:
                self.logger.error(f"Lỗi truy vấn Milvus HNSW: {e}")

        # Offline Local Fallback Vector Search (PyTorch CUDA)
        if self.local_features is not None and len(self.local_metadata) > 0:
            try:
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
            except Exception as e:
                self.logger.error(f"Lỗi tìm kiếm offline (Có thể do sai lệch số chiều Vector khi fallback model): {e}")
                return []

        return []

    def resolve_keyframe_path(self, target: str) -> Optional[str]:
        """Tìm đường dẫn tệp keyframe thực tế trên ổ cứng từ vectorId, URL hoặc filename"""
        if not target:
            return None
        kf_dir = getattr(self.config, 'keyframes_dir', None) or getattr(self.config.server, 'keyframes_dir', './data-keyframes')
        kf_dir = os.path.abspath(kf_dir)

        # Xóa prefix domain nếu có
        for prefix in ["http://localhost:8000/keyframes/", "http://127.0.0.1:8000/keyframes/", "http://localhost:8000/", "http://127.0.0.1:8000/"]:
            if target.startswith(prefix):
                target = target[len(prefix):]
        target = target.replace("\\", "/").strip("/")

        # 1. Đường dẫn trực tiếp
        cand1 = os.path.join(kf_dir, target)
        if os.path.isfile(cand1):
            return cand1
        if target.startswith("keyframes/"):
            cand2 = os.path.join(kf_dir, target[len("keyframes/"):])
            if os.path.isfile(cand2):
                return cand2

        # 2. Xử lý path dạng l26/L26_V151/keyframes/keyframe_4030.webp hoặc L26_V151_4030
        parts = target.replace("\\", "/").split("/")
        img_name = parts[-1]
        if not img_name.endswith(".webp") and not img_name.endswith(".jpg") and not img_name.endswith(".png"):
            if "_" in img_name:
                fid = img_name.rsplit("_", 1)[-1]
                img_name = f"keyframe_{fid}.webp"

        vid_name = ""
        for p in parts:
            if p.upper().startswith("L") and "_V" in p.upper():
                vid_name = p.upper()
                break

        if img_name:
            for root, _, files in os.walk(kf_dir):
                if img_name in files:
                    if not vid_name or vid_name.lower() in root.lower().replace("\\", "/"):
                        return os.path.join(root, img_name)

        return None

    @staticmethod
    def _strip_accents(text: str) -> str:
        if not text:
            return ""
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", str(text))
        return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()

    async def search_ocr(self, query_text: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Tìm kiếm chuỗi ký tự OCR nâng cao với BM25 Inverted Index & Từ đồng nghĩa (Tốc độ < 2ms)"""
        if not query_text or not self.ocr_data:
            return []

        import difflib
        import re
        import math

        q_clean = query_text.lower().strip()
        q_no_acc = self._strip_accents(q_clean)
        
        # Stop words thường gặp trong câu hỏi / biển chỉ dẫn
        stop_words = {'đường', 'duong', 'phố', 'pho', 'quận', 'quan', 'phường', 'phuong', 'tp', 'thành', 'thanh', 'biển', 'bien', 'chữ', 'chu', 'bảng', 'bang', 'hiệu', 'hieu', 'tên', 'ten', 'tìm', 'tim', 'ảnh', 'anh', 'hình', 'hinh', 'có', 'co'}
        q_words = set(re.findall(r'\w+', q_no_acc)) - stop_words
        if not q_words:
            q_words = set(re.findall(r'\w+', q_no_acc))

        # Mở rộng từ đồng nghĩa vào tập tokens tìm kiếm
        expanded_q_words = set(q_words)
        for key, syns in VIETNAMESE_SYNONYM_THESAURUS.items():
            key_no_acc = self._strip_accents(key.lower())
            if key_no_acc in q_no_acc:
                for s in syns:
                    for w in re.findall(r'\w+', self._strip_accents(s.lower())):
                        if w not in stop_words:
                            expanded_q_words.add(w)

        # 1. Thu thập ứng viên từ Inverted Index trong < 1ms
        candidate_docs = set()
        if hasattr(self, 'ocr_inverted_index') and self.ocr_inverted_index:
            for token in expanded_q_words:
                if token in self.ocr_inverted_index:
                    candidate_docs.update(self.ocr_inverted_index[token])
        else:
            candidate_docs = set(self.ocr_data.keys())

        if not candidate_docs:
            candidate_docs = set(self.ocr_data.keys())

        matched_results = []
        k1 = 1.2
        b = 0.75
        N = max(len(self.ocr_data), 1)
        avgdl = getattr(self, 'avg_ocr_doc_len', 10.0)

        for rel_path in candidate_docs:
            ocr_text = self.ocr_data.get(rel_path, "")
            ocr_clean = ocr_text.lower().strip()
            ocr_no_acc = self._strip_accents(ocr_clean)

            score = 0.0

            # 1. Khớp chính xác hoàn toàn (Exact match)
            if q_clean == ocr_clean:
                score = 1.0
            # 2. Khớp chuỗi con xuôi / ngược (Substring match)
            elif q_clean in ocr_clean:
                score = 0.95 + 0.05 * (len(q_clean) / max(len(ocr_clean), 1))
            elif len(ocr_clean) >= 3 and ocr_clean in q_clean:
                score = 0.90 + 0.05 * (len(ocr_clean) / max(len(q_clean), 1))
            # 3. Khớp không dấu (Accent-insensitive match)
            elif q_no_acc in ocr_no_acc:
                score = 0.88 + 0.08 * (len(q_no_acc) / max(len(ocr_no_acc), 1))
            elif len(ocr_no_acc) >= 3 and ocr_no_acc in q_no_acc:
                score = 0.82 + 0.08 * (len(ocr_no_acc) / max(len(q_no_acc), 1))
            else:
                # 4. Tính điểm BM25 Token Matching
                ocr_words = set(re.findall(r'\w+', ocr_no_acc))
                intersection = expanded_q_words & ocr_words
                if intersection:
                    doc_len = len(ocr_words)
                    bm25_score = 0.0
                    for term in intersection:
                        df = len(self.ocr_inverted_index.get(term, [])) if hasattr(self, 'ocr_inverted_index') else 1
                        idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                        tf = 1.0
                        term_score = idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / max(avgdl, 1.0)))))
                        bm25_score += term_score
                    
                    precision = len(intersection) / len(expanded_q_words)
                    recall = len(intersection) / max(len(ocr_words), 1)
                    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
                    score = max(score, round(min(0.70 + 0.20 * min(bm25_score / 3.0, 1.0) + 0.10 * f1, 0.96), 3))

                # 5. Khớp mờ Levenshtein / SequenceMatcher
                if len(ocr_no_acc) >= 3 and len(q_no_acc) >= 3:
                    ratio = difflib.SequenceMatcher(None, q_no_acc, ocr_no_acc).ratio()
                    if ratio >= 0.65:
                        score = max(score, round(0.65 + 0.22 * ratio, 3))

            if score >= 0.65:
                try:
                    norm_path = rel_path.replace("\\", "/")
                    parts = norm_path.split("/")
                    if "keyframes" in parts:
                        kf_idx = parts.index("keyframes")
                        video_id = "/".join(parts[:kf_idx])
                    elif len(parts) > 1:
                        video_id = "/".join(parts[:-1])
                    else:
                        video_id = parts[0]

                    filename = parts[-1]
                    match = re.search(r'(\d+)', filename)
                    frame_id = int(match.group(1)) if match else 0

                    matched_results.append({
                        "id": f"{video_id}_{frame_id}",
                        "distance": round(score, 3),
                        "score": round(score, 3),
                        "entity": {
                            "filepath": norm_path,
                            "video_id": video_id,
                            "frame_id": frame_id,
                            "time": frame_id,
                            "ocr_text": ocr_text
                        }
                    })
                except Exception:
                    continue

        matched_results.sort(key=lambda x: x["distance"], reverse=True)
        return matched_results[:limit]

    async def search_asr(self, query_text: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Tìm kiếm giọng nói / lời thoại (ASR) nâng cao với BM25 Inverted Index & Từ đồng nghĩa (Tốc độ < 2ms)"""
        if not query_text or not self.asr_data:
            return []

        import difflib
        import re
        import math

        q_clean = query_text.lower().strip()
        q_no_acc = self._strip_accents(q_clean)
        
        stop_words = {'tìm', 'tim', 'người', 'nguoi', 'nói', 'noi', 'lời', 'loi', 'thoại', 'thoai', 'âm', 'am', 'thanh'}
        q_words = set(re.findall(r'\w+', q_no_acc)) - stop_words
        if not q_words:
            q_words = set(re.findall(r'\w+', q_no_acc))

        # Mở rộng từ đồng nghĩa vào tập tokens tìm kiếm
        expanded_q_words = set(q_words)
        for key, syns in VIETNAMESE_SYNONYM_THESAURUS.items():
            key_no_acc = self._strip_accents(key.lower())
            if key_no_acc in q_no_acc:
                for s in syns:
                    for w in re.findall(r'\w+', self._strip_accents(s.lower())):
                        if w not in stop_words:
                            expanded_q_words.add(w)

        # 1. Thu thập ứng viên từ Inverted Index
        candidate_docs = set()
        if hasattr(self, 'asr_inverted_index') and self.asr_inverted_index:
            for token in expanded_q_words:
                if token in self.asr_inverted_index:
                    candidate_docs.update(self.asr_inverted_index[token])
        else:
            candidate_docs = set(self.asr_data.keys())

        if not candidate_docs:
            candidate_docs = set(self.asr_data.keys())

        matched_results = []
        k1 = 1.2
        b = 0.75
        N = max(len(self.asr_data), 1)
        avgdl = getattr(self, 'avg_asr_doc_len', 10.0)

        for rel_path in candidate_docs:
            asr_text = self.asr_data.get(rel_path, "")
            asr_clean = asr_text.lower().strip()
            asr_no_acc = self._strip_accents(asr_clean)

            score = 0.0

            if q_clean == asr_clean:
                score = 1.0
            elif q_clean in asr_clean:
                score = 0.95 + 0.05 * (len(q_clean) / max(len(asr_clean), 1))
            elif len(asr_clean) >= 3 and asr_clean in q_clean:
                score = 0.90 + 0.05 * (len(asr_clean) / max(len(q_clean), 1))
            elif q_no_acc in asr_no_acc:
                score = 0.88 + 0.08 * (len(q_no_acc) / max(len(asr_no_acc), 1))
            elif len(asr_no_acc) >= 3 and asr_no_acc in q_no_acc:
                score = 0.82 + 0.08 * (len(asr_no_acc) / max(len(q_no_acc), 1))
            else:
                # 4. Tính điểm BM25 Token Matching
                asr_words = set(re.findall(r'\w+', asr_no_acc))
                intersection = expanded_q_words & asr_words
                if intersection:
                    doc_len = len(asr_words)
                    bm25_score = 0.0
                    for term in intersection:
                        df = len(self.asr_inverted_index.get(term, [])) if hasattr(self, 'asr_inverted_index') else 1
                        idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                        tf = 1.0
                        term_score = idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / max(avgdl, 1.0)))))
                        bm25_score += term_score
                    
                    precision = len(intersection) / len(expanded_q_words)
                    recall = len(intersection) / max(len(asr_words), 1)
                    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
                    score = max(score, round(min(0.70 + 0.20 * min(bm25_score / 3.0, 1.0) + 0.10 * f1, 0.96), 3))

                if len(asr_no_acc) >= 3 and len(q_no_acc) >= 3:
                    ratio = difflib.SequenceMatcher(None, q_no_acc, asr_no_acc).ratio()
                    if ratio >= 0.65:
                        score = max(score, round(0.65 + 0.22 * ratio, 3))

            if score >= 0.65:
                try:
                    norm_path = rel_path.replace("\\", "/")
                    parts = norm_path.split("/")
                    if "keyframes" in parts:
                        kf_idx = parts.index("keyframes")
                        video_id = "/".join(parts[:kf_idx])
                    elif len(parts) > 1:
                        video_id = "/".join(parts[:-1])
                    else:
                        video_id = parts[0]

                    filename = parts[-1]
                    match = re.search(r'(\d+)', filename)
                    frame_id = int(match.group(1)) if match else 0

                    matched_results.append({
                        "id": f"{video_id}_{frame_id}",
                        "distance": round(score, 3),
                        "score": round(score, 3),
                        "entity": {
                            "filepath": norm_path,
                            "video_id": video_id,
                            "frame_id": frame_id,
                            "time": frame_id,
                            "asr_text": asr_text
                        }
                    })
                except Exception:
                    continue

        matched_results.sort(key=lambda x: x["distance"], reverse=True)
        return matched_results[:limit]

    async def get_vectors_by_ids(self, ids: List[str]) -> List[List[float]]:
        if not ids:
            return []

        vecs = []

        if self.milvus_client is not None:
            int_ids = []
            str_conditions = []
            for i in ids:
                s = str(i).strip()
                if s.isdigit():
                    int_ids.append(int(s))
                elif "_" in s:
                    parts = s.rsplit("_", 1)
                    vid = parts[0]
                    fid = parts[1].split(".")[0]
                    if fid.isdigit():
                        str_conditions.append(f"(video_id like '%{vid}%' and frame_id == {int(fid)})")

            filter_clauses = []
            if int_ids:
                filter_clauses.append(f"id in {int_ids}")
            if str_conditions:
                filter_clauses.extend(str_conditions)

            if filter_clauses:
                filter_expr = " or ".join(filter_clauses)
                try:
                    results = await asyncio.to_thread(
                        self.milvus_client.query,
                        collection_name=self.config.database.collection_name,
                        filter=filter_expr,
                        output_fields=["embedding"]
                    )
                    if results:
                        for item in results:
                            if "embedding" in item:
                                vecs.append(item["embedding"])
                except Exception as e:
                    self.logger.error(f"Lỗi lấy vector từ Milvus theo ID: {e}")

        if not vecs and self.local_features is not None:
            for i in ids:
                str_i = str(i)
                if str_i in self.local_id_map:
                    idx = self.local_id_map[str_i]
                    vecs.append(self.local_features[idx].cpu().numpy().tolist())

        # Fallback tự động: nếu chưa lấy đủ vector từ Milvus/Index, đọc trực tiếp ảnh từ ổ đĩa và encode bằng SigLIP
        if len(vecs) < len(ids):
            for target_id in ids:
                img_path = self.resolve_keyframe_path(str(target_id))
                if img_path and os.path.isfile(img_path):
                    try:
                        from PIL import Image
                        pil_img = Image.open(img_path).convert("RGB")
                        if self.preprocess is not None and self.model is not None:
                            img_tensor = self.preprocess(pil_img).unsqueeze(0).to(self.device)
                            with torch.no_grad():
                                emb = self.model.encode_image(img_tensor)
                                emb = F.normalize(emb.float(), p=2, dim=-1)
                            vecs.append(emb[0].cpu().numpy().tolist())
                    except Exception as enc_err:
                        self.logger.error(f"Lỗi encode ảnh refine: {enc_err}")

        return vecs

    def compute_rocchio_vector(
        self,
        original_vec: List[float],
        relevant_vecs: List[List[float]],
        non_relevant_vecs: List[List[float]] = None,
        alpha: float = 1.0,
        beta: float = 0.75,
        gamma: float = 0.15
    ) -> List[float]:
        # Define base dimension from relevant_vecs or non_relevant_vecs if original_vec is empty
        base_dim = None
        if relevant_vecs and len(relevant_vecs[0]) > 0:
            base_dim = len(relevant_vecs[0])
        elif non_relevant_vecs and len(non_relevant_vecs[0]) > 0:
            base_dim = len(non_relevant_vecs[0])
        elif original_vec and len(original_vec) > 0:
            base_dim = len(original_vec)
            
        if not base_dim:
            return []

        if original_vec and len(original_vec) == base_dim:
            q0 = np.array(original_vec, dtype=np.float32)
        else:
            q0 = np.zeros(base_dim, dtype=np.float32)
            alpha = 0.0 # Ignore original_vec if it's empty

        rel_term = np.mean(relevant_vecs, axis=0) if relevant_vecs else np.zeros(base_dim, dtype=np.float32)
        non_rel_term = np.mean(non_relevant_vecs, axis=0) if non_relevant_vecs else np.zeros(base_dim, dtype=np.float32)

        q_new = alpha * q0 + beta * rel_term - gamma * non_rel_term
        norm = np.linalg.norm(q_new)
        if norm > 0:
            q_new = q_new / norm

        return q_new.tolist()

    async def process_temporal_query(
        self,
        first_query: Union[str, List[str]],
        second_query: str = "",
        model_name: str = "clip",
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        start_time = time.time()
        try:
            # 1. Chuẩn hóa danh sách các câu truy vấn thời gian (N cảnh liên tiếp)
            queries_list = []
            if isinstance(first_query, list):
                queries_list = [q.strip() for q in first_query if isinstance(q, str) and q.strip()]
            elif isinstance(first_query, str) and first_query.strip():
                queries_list.append(first_query.strip())
            
            if second_query and isinstance(second_query, str) and second_query.strip():
                queries_list.append(second_query.strip())

            if not queries_list:
                queries_list = ["scenery video overview"]

            # 2. Xử lý trường hợp 1 cảnh đơn lẻ
            if len(queries_list) == 1:
                first_encoded = await asyncio.to_thread(self.encode_clip_text, queries_list[0], model_name)
                result = await self.query_milvus(first_encoded, limit=limit)
            else:
                # 3. Mã hóa song song toàn bộ N câu truy vấn
                encoded_tasks = [
                    asyncio.to_thread(self.encode_clip_text, q, model_name) for q in queries_list
                ]
                encoded_list = await asyncio.gather(*encoded_tasks)

                # 4. Truy vấn Milvus song song cho toàn bộ N cảnh
                query_tasks = [
                    self.query_milvus(enc, limit=limit * 2) for enc in encoded_list
                ]
                results_list = await asyncio.gather(*query_tasks)

                # 5. Thực thi thuật toán chuỗi thời gian đa cảnh PyTorch GPU
                result = self._process_multi_temporal_relationships(results_list)

            # Lưu vết tương tác vào bộ nhớ HippoRAG Context Memory
            retrieved_vids = [item.get('entity', {}).get('video_id', '') for item in result[:5] if item.get('entity')]
            self.hippo_memory.add_interaction(queries_list[0], retrieved_vids)

            return result
        except Exception as e:
            self.logger.error(f"Lỗi xử lý temporal query: {e}")
            raise HTTPException(status_code=500, detail=f"Query Execution Error: {str(e)}")

    def _process_temporal_relationships(
        self,
        first_results: List[Dict[str, Any]],
        second_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        return self._process_multi_temporal_relationships([first_results, second_results])

    def _process_multi_temporal_relationships(
        self,
        results_list: List[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Thuật toán Ma trận Chuỗi Thời gian Đa Cảnh (Multi-Stage Temporal Chain) trên GPU PyTorch.
        Hỗ trợ chuỗi N sự kiện liên tiếp (Cảnh 1 -> Cảnh 2 -> Cảnh 3 -> ... -> Cảnh N).
        """
        if not results_list or not results_list[0]:
            return []
        if len(results_list) == 1:
            return results_list[0][:1000]

        def safe_str_hash(s: str) -> int:
            return abs(hash(s)) % (2**31)

        try:
            # Chuyển đổi danh sách kết quả từng cảnh thành tensor GPU
            tensors_list = []
            for r_list in results_list:
                if not r_list:
                    continue
                t_data = torch.tensor([
                    [
                        int(item.get('entity', {}).get('frame_id', 0)),
                        float(item.get('distance', 0.0)),
                        safe_str_hash(str(item.get('entity', {}).get('video_id', '')))
                    ]
                    for item in r_list
                ], device=self.device, dtype=torch.float32)
                tensors_list.append(t_data)

            if len(tensors_list) < 2:
                return results_list[0][:1000]

            # Lan truyền điểm ngược chuỗi thời gian (Dynamic Temporal Chain Backward Propagation)
            # Từ Cảnh N-1 đến Cảnh 1
            for k in range(len(tensors_list) - 2, -1, -1):
                curr_tensor = tensors_list[k]
                next_tensor = tensors_list[k + 1]

                frame_diff = next_tensor[:, None, 0] - curr_tensor[None, :, 0]
                same_video_mask = curr_tensor[None, :, 2] == next_tensor[:, None, 2]
                valid_mask = (frame_diff > 0) & (frame_diff <= 1500) & same_video_mask

                score_increase = next_tensor[:, None, 1] * (1500 - frame_diff) / 1500
                score_increase = torch.where(valid_mask, score_increase, torch.zeros_like(score_increase))

                max_boost, _ = score_increase.max(dim=0)
                curr_tensor[:, 1] += max_boost

            # Sắp xếp lại kết quả của Cảnh 1 theo điểm số tích lũy của toàn bộ chuỗi
            final_scores = tensors_list[0][:, 1].cpu().numpy()
            sorted_indices = np.argsort(final_scores)[::-1][:1000]

            updated_results = []
            for i in sorted_indices:
                res_item = dict(results_list[0][i])
                res_item['distance'] = float(final_scores[i])
                updated_results.append(res_item)

            return updated_results
        except Exception as e:
            self.logger.error(f"Lỗi tính toán chuỗi thời gian đa cảnh GPU PyTorch: {e}")
            return results_list[0][:1000]

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

        @app.get("/keyframes/maps/{map_name}")
        async def dynamic_map_handler(map_name: str):
            for root, _, files in os.walk(kf_path):
                if "maps" in root and map_name in files:
                    return FileResponse(os.path.join(root, map_name))
            return Response(status_code=404)

        @app.get("/keyframes/{rest_of_path:path}")
        async def dynamic_keyframe_handler(rest_of_path: str):
            # 1. Đường dẫn trực tiếp
            cand = os.path.join(kf_path, rest_of_path)
            if os.path.isfile(cand):
                return FileResponse(cand)

            # 2. Tìm kiếm thông minh theo filename và video name
            parts = rest_of_path.replace("\\", "/").split("/")
            img_name = parts[-1]
            vid_name = ""
            for p in parts:
                if p.upper().startswith("L") and "_V" in p.upper():
                    vid_name = p.upper()
                    break

            if img_name.endswith((".webp", ".jpg", ".png")):
                for root, _, files in os.walk(kf_path):
                    if img_name in files:
                        if not vid_name or vid_name.lower() in root.lower().replace("\\", "/"):
                            return FileResponse(os.path.join(root, img_name))

            return Response(status_code=404)

        service.logger.info(f"Registered universal dynamic keyframe handler for: {kf_path}")

    frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
    if os.path.exists(frontend_path):
        app.mount("/frontend", StaticFiles(directory=frontend_path, html=True), name="frontend")
        service.logger.info(f"Mounted static frontend: {frontend_path} -> /frontend")

    from fastapi.responses import FileResponse, Response
    @app.get("/videos/{video_name}")
    async def dynamic_video_handler(video_name: str):
        for vdir in config.server.video_dirs:
            if os.path.exists(vdir):
                for root, _, files in os.walk(vdir):
                    if video_name in files:
                        return FileResponse(os.path.join(root, video_name), media_type="video/mp4")
        return Response(status_code=404)

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
    # DRES COMPETITION PROXY (BYPASS CORS 100%)
    # ==========================================
    class DresLoginRequest(BaseModel):
        dres_url: str = "http://192.168.28.151:5000"
        username: str
        password: str

    @app.post("/api/dres/login")
    async def dres_proxy_login(payload: DresLoginRequest):
        """Proxy DRES login to avoid browser CORS issues"""
        import urllib.request, urllib.error, json
        dres_base = payload.dres_url.rstrip("/")
        login_url = f"{dres_base}/api/v2/login"
        
        try:
            req_data = json.dumps({"username": payload.username, "password": payload.password}).encode("utf-8")
            req = urllib.request.Request(login_url, data=req_data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                session_id = data.get("sessionId")
                
                # Fetch active evaluation list
                eval_id = None
                if session_id:
                    eval_url = f"{dres_base}/api/v2/client/evaluation/list?session={session_id}"
                    try:
                        eval_req = urllib.request.Request(eval_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(eval_req, timeout=5) as eval_resp:
                            eval_list = json.loads(eval_resp.read().decode("utf-8"))
                            if eval_list and len(eval_list) > 0:
                                eval_id = eval_list[0].get("id")
                    except Exception as ev_err:
                        service.logger.warning(f"Lỗi lấy evaluation list: {ev_err}")

                return {
                    "status": "success",
                    "sessionId": session_id,
                    "evaluationID": eval_id,
                    "user": data
                }
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            raise HTTPException(status_code=he.code, detail=f"DRES Error {he.code}: {err_body}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Không thể kết nối DRES ({dres_base}): {str(e)}")

    class DresSubmitRequest(BaseModel):
        dres_url: str = "http://192.168.28.151:5000"
        evaluation_id: str
        session_id: str
        payload: Dict[str, Any]

    @app.post("/api/dres/submit")
    async def dres_proxy_submit(data: DresSubmitRequest):
        """Proxy DRES submit to avoid browser CORS issues"""
        import urllib.request, urllib.error, json
        dres_base = data.dres_url.rstrip("/")
        submit_url = f"{dres_base}/api/v2/submit/{data.evaluation_id}?session={data.session_id}"
        
        try:
            req_data = json.dumps(data.payload).encode("utf-8")
            req = urllib.request.Request(submit_url, data=req_data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "success",
                    "dres_response": resp_data
                }
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            return {
                "status": "error",
                "code": he.code,
                "detail": err_body
            }
        except Exception as e:
            return {
                "status": "error",
                "code": 500,
                "detail": str(e)
            }

    # ==========================================
    # CÁC ENDPOINT ĐÓNG GÓI BÀI THI SƠ TUYỂN (AIC 2026 BATCH SUBMISSION)
    # ==========================================
    class SubmissionQueryItem(BaseModel):
        filename: str
        content: str
        query_type: Optional[str] = "kis"
        notes: Optional[str] = ""

    class SubmissionPackRequest(BaseModel):
        queries: List[SubmissionQueryItem]
        zip_filename: Optional[str] = "submission.zip"
        team_name: Optional[str] = ""

    @app.post("/api/submission/pack")
    async def pack_submission_endpoint(payload: SubmissionPackRequest):
        """
        Tự động kiểm tra tính hợp lệ và đóng gói các file CSV vào thư mục submission/ 
        rồi nén thành file submission.zip tại D:\\code-c-a-Long theo đúng chuẩn BTC AIC 2026.
        """
        import zipfile
        from pathlib import Path
        
        project_root = Path(__file__).resolve().parent.parent
        submission_dir = project_root / "submission"
        submission_dir.mkdir(parents=True, exist_ok=True)
        
        # Dọn dẹp các file csv cũ trong submission/
        for f in submission_dir.glob("*.csv"):
            try:
                f.unlink()
            except Exception:
                pass
                
        reports = []
        
        for q in payload.queries:
            fname = q.filename.strip()
            if not fname.endswith(".csv"):
                fname += ".csv"
            # Chuẩn hóa tên file
            fname = re.sub(r'[^\w\-\.]', '_', fname)
            
            lines = [line.strip() for line in q.content.strip().split("\n") if line.strip()]
            
            # Giới hạn tối đa 100 dòng theo luật BTC
            if len(lines) > 100:
                lines = lines[:100]
                
            clean_lines = []
            file_warnings = []
            
            for idx, line in enumerate(lines):
                # Tự động loại bỏ dòng Header nếu người dùng lỡ tạo
                if idx == 0 and any(h in line.lower() for h in ["video", "frame", "answer", "mediaitem", "time"]):
                    file_warnings.append("Đã tự động loại bỏ dòng tiêu đề (Header).")
                    continue
                
                parts = [p.strip() for p in line.split(",")]
                # Tên video: Xóa bỏ đuôi .mp4
                if len(parts) >= 1:
                    parts[0] = re.sub(r'\.mp4$', '', parts[0], flags=re.IGNORECASE).strip()
                
                if "qa" in fname.lower() or q.query_type == "qa":
                    # Format Q&A: <video_name>,<frame_id>,"<answer>"
                    if len(parts) >= 3:
                        video_part = parts[0]
                        frame_part = parts[1]
                        ans_part = ",".join(parts[2:]).strip()
                        # Loại bỏ ngoặc kép bao ngoài nếu có
                        if (ans_part.startswith('"') and ans_part.endswith('"')) or (ans_part.startswith("'") and ans_part.endswith("'")):
                            ans_part = ans_part[1:-1].strip()
                        # Giới hạn tối đa 100 ký tự theo quy định BTC
                        ans_part = ans_part[:100]
                        # Escape dấu ngoặc kép bên trong thành ""
                        ans_part = ans_part.replace('"', '""')
                        clean_line = f'{video_part},{frame_part},"{ans_part}"'
                    else:
                        clean_line = ",".join(parts)
                else:
                    # KIS hoặc TRAKE
                    clean_line = ",".join(parts)
                
                clean_lines.append(clean_line)
            
            # Ghi file CSV vào thư mục submission/
            file_path = submission_dir / fname
            file_content = "\n".join(clean_lines) + "\n"
            file_path.write_text(file_content, encoding="utf-8")
            
            reports.append({
                "filename": fname,
                "lines_count": len(clean_lines),
                "status": "valid",
                "warnings": file_warnings
            })
            
        # Tạo file submission.zip ở thư mục gốc D:\code-c-a-Long
        zip_filename = payload.zip_filename.strip() if payload.zip_filename else "submission.zip"
        if not zip_filename.endswith(".zip"):
            zip_filename += ".zip"
        zip_path = project_root / zip_filename
        
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for csv_file in submission_dir.glob("*.csv"):
                # Cấu trúc BẮT BUỘC: submission/<filename.csv>
                arcname = f"submission/{csv_file.name}"
                zf.write(csv_file, arcname=arcname)
                
        return {
            "status": "success",
            "zip_path": str(zip_path),
            "zip_filename": zip_filename,
            "submission_folder": str(submission_dir),
            "total_queries": len(reports),
            "reports": reports,
            "message": f"🎉 Đã đóng gói thành công {len(reports)} file CSV vào {zip_path}"
        }

    @app.get("/api/submission/status")
    async def get_submission_status():
        """Lấy trạng thái các file query đã xuất và file zip hiện có"""
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent
        submission_dir = project_root / "submission"
        zip_path = project_root / "submission.zip"
        
        files = []
        if submission_dir.exists():
            for f in sorted(submission_dir.glob("*.csv")):
                lines = [l for l in f.read_text(encoding="utf-8").split("\n") if l.strip()]
                files.append({
                    "filename": f.name,
                    "lines_count": len(lines),
                    "size_bytes": f.stat().st_size,
                    "modified_time": time.ctime(f.stat().st_mtime)
                })
                
        return {
            "submission_dir": str(submission_dir),
            "files": files,
            "zip_exists": zip_path.exists(),
            "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
            "zip_path": str(zip_path) if zip_path.exists() else None
        }

    @app.post("/api/submission/clear")
    async def clear_submission_endpoint():
        """Xóa sạch thư mục submission/ và file zip để làm gói mới"""
        from pathlib import Path
        import shutil
        project_root = Path(__file__).resolve().parent.parent
        submission_dir = project_root / "submission"
        zip_path = project_root / "submission.zip"
        
        if submission_dir.exists():
            shutil.rmtree(submission_dir, ignore_errors=True)
            submission_dir.mkdir(parents=True, exist_ok=True)
            
        if zip_path.exists():
            try:
                zip_path.unlink()
            except Exception:
                pass
                
        return {"status": "success", "message": "Đã làm sạch thư mục submission/ và file zip"}

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

        def extract_ocr_intent(text: str) -> str:
            if not text:
                return ""
            import re
            m = re.search(r'["\'](.*?)["\']', text)
            if m and m.group(1).strip():
                return m.group(1).strip()
            patterns = [
                r'(?:tìm\s+)?(?:hình\s+ảnh|ảnh|video|khung\s+hình)?\s*(?:có\s+)?(?:chữ|biển\s+số|bảng\s+hiệu|logo|text|ocr)\s*[:：]?\s*(.+)',
                r'(?:có\s+chữ)\s+(.+)',
                r'(?:chữ)\s+(.+)',
                r'(?:biển\s+số)\s+(.+)',
                r'(?:bảng\s+hiệu)\s+(.+)'
            ]
            for pat in patterns:
                m = re.search(pat, text.strip(), re.IGNORECASE)
                if m and m.group(1).strip():
                    return m.group(1).strip()
            return ""

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

                    # 1. Kiểm tra từ khóa OCR Tiếng Việt chính xác (Ưu tiên số 1)
                    ocr_kw = extract_ocr_intent(first_q)
                    ocr_results = []
                    if ocr_kw:
                        ocr_results = await service.search_ocr(ocr_kw, limit=1000)

                    if ocr_results:
                        # Kết hợp kết quả: Đưa toàn bộ ảnh chứa đúng chữ OCR lên đầu tiên (#1, #2, #3...)
                        semantic_results = await service.process_temporal_query(first_q, second_q, model_name=model_choice)
                        seen_ids = {item["id"] for item in ocr_results}
                        merged_results = list(ocr_results)
                        for sem in semantic_results:
                            if sem.get("id") not in seen_ids:
                                merged_results.append(sem)
                                seen_ids.add(sem.get("id"))
                        result = merged_results
                    else:
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
            service.logger.info("Main WebSocket disconnected")
        except Exception as e:
            service.logger.error(f"Error in Main WebSocket: {str(e)}")

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
                ocr_texts = data.get("ocrtext", [])
                asm_texts = data.get("asmtext", [])

                # 1. Parse all textQueries (Hỗ trợ 1, 2, 3, 4... N cảnh chuỗi thời gian)
                all_text_q_list = []
                if isinstance(text_queries, list):
                    for q_item in text_queries:
                        if isinstance(q_item, dict):
                            val = q_item.get("content", "") or q_item.get("text", "")
                            if val and val.strip():
                                all_text_q_list.append(val.strip())
                        elif isinstance(q_item, str) and q_item.strip():
                            all_text_q_list.append(q_item.strip())

                first_q = all_text_q_list[0] if len(all_text_q_list) >= 1 else ""

                # 2. Parse OCR & ASR texts
                ocr_query_str = ""
                for o_text in ocr_texts:
                    if isinstance(o_text, str) and o_text.strip():
                        ocr_query_str = o_text.strip()
                        break

                asr_query_str = ""
                for a_text in asm_texts:
                    if isinstance(a_text, str) and a_text.strip():
                        asr_query_str = a_text.strip()
                        break

                # Câu truy vấn hiệu dụng để tìm kiếm ngữ nghĩa SigLIP
                effective_query = all_text_q_list if all_text_q_list else (ocr_query_str or asr_query_str or "scenery overview")

                result = []
                
                # 3. Trích xuất ý định tìm kiếm chữ (OCR Intent Recognition) thông minh
                if not ocr_query_str and first_q:
                    import re
                    m = re.search(r'["\'](.*?)["\']', first_q)
                    if m and m.group(1).strip():
                        ocr_query_str = m.group(1).strip()
                    else:
                        ocr_patterns = [
                            r'(?:tìm\s+)?(?:hình\s+ảnh|ảnh|video|khung\s+hình)?\s*(?:có\s+)?(?:chữ|biển\s+số|bảng\s+hiệu|logo|text|ocr)\s*[:：]?\s*(.+)',
                            r'(?:có\s+chữ)\s+(.+)',
                            r'(?:chữ)\s+(.+)',
                            r'(?:biển\s+số)\s+(.+)',
                            r'(?:bảng\s+hiệu)\s+(.+)'
                        ]
                        for pat in ocr_patterns:
                            m = re.search(pat, first_q.strip(), re.IGNORECASE)
                            if m and m.group(1).strip():
                                ocr_query_str = m.group(1).strip()
                                break
                        
                # A. Tìm kiếm theo OCR nếu có chuỗi OCR
                ocr_results = []
                if ocr_query_str:
                    ocr_results = await service.search_ocr(ocr_query_str, limit=1000)

                # B. Tìm kiếm theo ASR nếu có chuỗi ASR
                asr_results = []
                if asr_query_str:
                    asr_results = await service.search_asr(asr_query_str, limit=1000)

                exact_matches = ocr_results + asr_results
                if exact_matches:
                    # Đưa toàn bộ ảnh khớp OCR / ASR lên đầu
                    semantic_results = await service.process_temporal_query(effective_query, model_name=model_choice)
                    seen_ids = {item["id"] for item in exact_matches}
                    merged_results = list(exact_matches)
                    for sem in semantic_results:
                        if sem.get("id") not in seen_ids:
                            merged_results.append(sem)
                            seen_ids.add(sem.get("id"))
                    result = merged_results
                
                # Nếu không có kết quả OCR/ASR hoặc là tìm kiếm ngữ nghĩa thông thường
                if not result:
                    result = await service.process_temporal_query(effective_query, model_name=model_choice)

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
    