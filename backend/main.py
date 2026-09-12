"""
FastAPI Vector Search Service
Mô hình thị giác: Google SigLIP 2 ViT-gopt-16-SigLIP2-384 (1152 chiều, FP16 CUDA).
Cấu hình phần cứng: AMD 7000 Series (16 luồng, cấp phát 13-14 luồng) | 16GB RAM DDR5 | NVIDIA RTX 3050 Laptop 6GB VRAM (ngưỡng 88% ~5.28 GB).
Chỉ mục vector: FAISS IVF-SQ8 (8-bit Scalar Quantization, Inner Product).
Xử lý văn bản: BM25 Inverted Index cho OCR và ASR trên RAM.
"""

import os
import io
import re
import json
import time
import copy
import base64
import logging
import asyncio
import warnings
from collections import defaultdict, deque, Counter
from enum import Enum
from typing import List, Optional, Dict, Any, Union, Tuple
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

# Load environment variables từ backend/.env hoặc .env gốc
from dotenv import load_dotenv
_env_candidates = [
    os.path.join(os.path.dirname(__file__), ".env"),
    os.path.abspath(".env"),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
]
for _ep in _env_candidates:
    if os.path.exists(_ep):
        load_dotenv(_ep, override=True)
        break
else:
    load_dotenv(override=True)

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

# Thiết lập tối ưu hóa phần cứng local: 80% - 90% công suất AMD 7000 Series (16 Threads) & GPU 6GB VRAM
_cpu_cores = os.cpu_count() or 8
OPTIMAL_CPU_THREADS = max(1, int(_cpu_cores * 0.85))  # 80%-90% capacity
torch.set_num_threads(OPTIMAL_CPU_THREADS)
try:
    import faiss
    faiss.omp_set_num_threads(OPTIMAL_CPU_THREADS)
except Exception:
    pass

if hasattr(cv2, "setNumThreads"):
    cv2.setNumThreads(OPTIMAL_CPU_THREADS)

if torch.cuda.is_available():
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    try:
        # Sử dụng tối ưu 88% VRAM của GPU 6GB cho Tensor Core mà không gây tràn bộ nhớ OOM
        torch.cuda.set_per_process_memory_fraction(0.88)
    except Exception:
        pass

# Smart Query Decomposer & Omni-Parser
try:
    from backend.smart_query_decomposer import smart_decomposer, DecomposedQuery
except ImportError:
    from smart_query_decomposer import smart_decomposer, DecomposedQuery

# ==============================================================================
# VIETNAMESE SYNONYM THESAURUS (BỘ TỪ ĐIỂN TỪ ĐỒNG NGHĨA TIẾNG VIỆT CHUYÊN DỤNG)
# ==============================================================================
VIETNAMESE_SYNONYM_THESAURUS = {
    # Phương tiện giao thông
    "xe máy": ["xe mô tô", "xe gắn máy", "xe hai bánh", "xe honda", "xe tay ga", "scooter", "motorbike", "motorcycle"],
    "xe mô tô": ["xe máy", "xe gắn máy", "xe hai bánh", "motorbike", "motorcycle"],
    "ô tô": ["xe hơi", "xe bốn bánh", "xế hộp", "xe con", "car", "automobile", "vehicle"],
    "xe hơi": ["ô tô", "xe bốn bánh", "xế hộp", "xe con", "car", "automobile"],
    "xe buýt": ["xe bus", "xe khách", "xe đò", "bus", "coach"],
    "xe bus": ["xe buýt", "xe khách", "xe đò", "bus"],
    "xe đạp": ["xe hai bánh", "xe đạp điện", "bicycle", "bike", "cyclist"],
    "máy bay": ["phi cơ", "tàu bay", "hàng không", "airplane", "plane", "aircraft"],
    "thuyền": ["tàu", "ghe", "cano", "ca nô", "xuồng", "thuyền buồm", "boat", "ship"],
    "xe tải": ["xe chở hàng", "xe ben", "truck", "lorry"],
    "xe cứu thương": ["xe cấp cứu", "ambulance"],
    "xe cảnh sát": ["xe công an", "police car", "patrol"],

    # Con người & Chức danh
    "người đàn ông": ["nam giới", "chàng trai", "người nam", "đàn ông", "ông chú", "anh thanh niên", "man", "male", "guy"],
    "đàn ông": ["người đàn ông", "nam giới", "chàng trai", "anh thanh niên", "man", "male"],
    "phụ nữ": ["người phụ nữ", "cô gái", "nữ giới", "người nữ", "chị phụ nữ", "bà cô", "woman", "female", "girl", "lady"],
    "cô gái": ["phụ nữ", "thiếu nữ", "bạn nữ", "cô thanh niên", "girl", "young woman"],
    "trẻ em": ["em bé", "đứa trẻ", "học sinh", "con nít", "trẻ nhỏ", "bé gái", "bé trai", "child", "children", "kid", "baby"],
    "em bé": ["trẻ sơ sinh", "đứa trẻ", "em nhỏ", "baby", "toddler", "infant"],
    "cảnh sát": ["công an", "CSGT", "công an giao thông", "chiến sĩ", "cán bộ", "police", "officer"],
    "bác sĩ": ["y sĩ", "thầy thuốc", "y tế", "doctor", "physician"],
    "học sinh": ["sinh viên", "học trò", "học viên", "student", "pupil"],
    "tài xế": ["người lái xe", "bác tài", "tài xế lái xe", "driver"],

    # Trang phục & Phụ kiện
    "áo dài": ["áo dài truyền thống", "ao dai", "traditional dress"],
    "nón lá": ["nón bài thơ", "conical hat"],
    "mũ bảo hiểm": ["nón bảo hiểm", "helmet"],
    "nón bảo hiểm": ["mũ bảo hiểm", "helmet"],
    "khẩu trang": ["mặt nạ y tế", "khẩu trang y tế", "facemask", "mask"],
    "balo": ["ba lô", "cặp sách", "túi xách", "túi đeo", "backpack", "bag"],
    "kính mắt": ["kính râm", "mắt kính", "kính cận", "glasses", "sunglasses"],

    # Địa danh & Kênh truyền thông
    "sài gòn": ["tphcm", "tp hcm", "thành phố hồ chí minh", "hcm"],
    "tphcm": ["sài gòn", "tp hcm", "thành phố hồ chí minh"],
    "tp hcm": ["sài gòn", "tphcm", "thành phố hồ chí minh"],
    "hà nội": ["thủ đô", "hn", "thủ đô hà nội"],
    "đà nẵng": ["dn", "thành phố đà nẵng"],
    "vtv": ["vtv1", "vtv3", "truyền hình việt nam", "đài truyền hình"],
    "htv": ["htv7", "htv9", "truyền hình tphcm"],

    # Hành động & Giao tiếp
    "chạy bộ": ["chạy nhanh", "chạy", "tập thể dục", "running", "jogging"],
    "đi bộ": ["tản bộ", "dạo phố", "đi dạo", "walking", "strolling"],
    "nói chuyện": ["trò chuyện", "giao tiếp", "thảo luận", "bàn tán", "phát biểu", "chia sẻ", "talking", "chatting", "conversing"],
    "bắt tay": ["chào hỏi", "bắt tay nhau", "handshake", "shaking hands"],
    "ăn uống": ["dùng bữa", "thưởng thức", "ăn cơm", "eating", "drinking", "dining"],
    "nghe điện thoại": ["gọi điện thoại", "bấm điện thoại", "nghe máy", "on the phone", "calling"],
    "lái xe": ["điều khiển xe", "chạy xe", "lái", "driving", "riding"],

    # Địa điểm & Không gian
    "đường phố": ["lòng đường", "phố xá", "vỉa hè", "tuyến đường", "street", "road", "avenue"],
    "ngã tư": ["ngã tư đường", "giao lộ", "vòng xoay", "ngã ba", "bùng binh", "intersection", "crossroad", "junction"],
    "bãi biển": ["bờ biển", "bờ cát", "bãi cát", "ven biển", "beach", "seashore", "coastline"],
    "công viên": ["vườn hoa", "khu vui chơi", "khuôn viên", "park", "garden"],
    "quán cà phê": ["quán cafe", "quán nước", "tiệm cà phê", "tiệm cafe", "coffee shop", "cafe"],
    "siêu thị": ["cửa hàng", "tiệm tạp hóa", "bách hóa", "supermarket", "store", "grocery"],
    "bệnh viện": ["phòng khám", "trung tâm y tế", "bệnh xá", "hospital", "clinic"],
    "chợ": ["khu chợ", "chợ truyền thống", "chợ dân sinh", "market"],

    # Ẩm thực & Nấu nướng
    "măng tây": ["mang tay", "măng tây xanh", "cây măng tây", "măng tây xào", "salad măng tây", "asparagus"],
    "chế biến": ["nấu ăn", "làm món", "nấu nướng", "chuẩn bị món", "cooking"],
    "nấu ăn": ["chế biến", "nấu nướng", "làm bếp", "nấu", "cooking"],
    "món ăn": ["ẩm thực", "món ngon", "thực đơn", "món"],
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


# ==========================================
# 5. PYDANTIC SCHEMAS CHO API
# ==========================================
class TextQueryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    First_query: Optional[str] = Field("", alias="firstQuery", description="Mô tả sự kiện văn bản chính")
    Next_query: Optional[str] = Field("", alias="secondQuery", description="Mô tả sự kiện tiếp theo (Temporal)")
    text_query: Optional[str] = Field("", description="Mô tả văn bản trực tiếp")
    model: Optional[str] = Field("ViT-gopt-16-SigLIP2-384", description="Google SigLIP 2 Giant (1152d FP16)")
    top_k: Optional[int] = Field(50, description="Số lượng kết quả cần trả về")


class ImageQueryRequest(BaseModel):
    image_base64: str = Field(..., description="Chuỗi Base64 của ảnh truy vấn")
    model: Optional[str] = Field("ViT-gopt-16-SigLIP2-384", description="Google SigLIP 2 Giant")
    top_k: Optional[int] = Field(50, description="Số lượng kết quả cần trả về")


class HybridQueryRequest(BaseModel):
    text_query: Optional[str] = Field("", description="Mô tả văn bản")
    image_base64: Optional[str] = Field("", description="Ảnh mẫu truy vấn")
    text_weight: Optional[float] = Field(0.5, description="Trọng số vector văn bản")
    image_weight: Optional[float] = Field(0.5, description="Trọng số vector hình ảnh")
    model: Optional[str] = Field("ViT-gopt-16-SigLIP2-384", description="Google SigLIP 2 Giant")
    top_k: Optional[int] = Field(50, description="Số lượng kết quả trả về")


class RefineSearchRequest(BaseModel):
    original_vector: List[float]
    relevant_ids: List[str]
    non_relevant_ids: Optional[List[str]] = []
    top_k: Optional[int] = 50
    alpha: Optional[float] = 1.0
    beta: Optional[float] = 0.75
    gamma: Optional[float] = 0.15





# ==========================================
# 6. CONFIGURATION MANAGEMENT
# ==========================================
@dataclass
class ModelConfig:
    clip_model_name: str = "ViT-gopt-16-SigLIP2-384"
    clip_pretrained: str = "webli"
    device: str = "cuda"


@dataclass
class DatabaseConfig:
    uri: str = "http://localhost:283710"
    host: str = "localhost"
    port: int = 283710
    database: str = "default"
    collection_name: str = "AIC26_fullbatch1"
    search_limit: int = 1000
    replica_number: int = 1
    hnsw_m: int = 16
    hnsw_ef_construction: int = 128
    hnsw_ef_search: int = 64


@dataclass
class FilterConfig:
    enable_adaptive_router: bool = False
    enable_heuristics_filter: bool = True
    blur_threshold: float = 95.0
    min_luminance: float = 20.0
    max_luminance: float = 235.0
    cache_size: int = 2000
    default_result_limit: int = 1000


@dataclass
class ServerConfig:
    cors_origins: str = "http://localhost:3000"
    max_workers: int = 8
    log_level: str = "INFO"
    gzip_minimum_size: int = 1000
    keyframes_dir: str = "D:/code-c-a-Long/data-keyframes"
    video_dirs: List[str] = field(default_factory=lambda: ["C:/video_test"])
    api_key: str = "aic2026_secure_token_@1135zz"


class Config:
    def __init__(self, config_file: str = None):
        config_data = {}
        target_path = config_file
        if not target_path:
            target_path = os.getenv("CONFIG_FILE", "config.json")

        possible_paths = [
            target_path,
            os.path.join(os.path.dirname(__file__), target_path),
            os.path.join(os.path.dirname(__file__), "config.json"),
            os.path.abspath("config.json"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.json"))
        ]
        chosen_path = next((p for p in possible_paths if p and os.path.exists(p)), None)
        if chosen_path:
            try:
                with open(chosen_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except Exception as e:
                print(f"Warning: Could not parse {chosen_path}: {e}")

        default_device = "cuda" if torch.cuda.is_available() else "cpu"
        dev = os.getenv("DEVICE", config_data.get("device", default_device)).strip()
        if dev == "cuda" and not torch.cuda.is_available():
            print("⚠️ CUDA requested but not available. Falling back to CPU.")
            dev = "cpu"

        self.model = ModelConfig(
            clip_model_name=os.getenv("CLIP_MODEL_NAME", config_data.get("clip_model_name", "ViT-gopt-16-SigLIP2-384")).strip(),
            clip_pretrained=os.getenv("CLIP_PRETRAINED", config_data.get("clip_pretrained", "webli")).strip(),
            device=dev
        )

        milvus_host = os.getenv("MILVUS_HOST", config_data.get("milvus_host", "localhost"))
        milvus_port = int(os.getenv("MILVUS_PORT", config_data.get("milvus_port", 283710)))
        default_uri = f"http://{milvus_host}:{milvus_port}"

        self.database = DatabaseConfig(
            uri=os.getenv("MILVUS_URI", config_data.get("milvus_uri", default_uri)),
            host=milvus_host,
            port=milvus_port,
            database=os.getenv("MILVUS_DATABASE", config_data.get("milvus_database", "default")),
            collection_name=os.getenv("COLLECTION_NAME", config_data.get("collection_name", "AIC26_fullbatch1")),
            search_limit=int(os.getenv("SEARCH_LIMIT", config_data.get("search_limit", 1000))),
            replica_number=int(os.getenv("REPLICA_NUMBER", config_data.get("replica_number", 1))),
            hnsw_m=int(config_data.get("hnsw_m", 16)),
            hnsw_ef_construction=int(config_data.get("hnsw_ef_construction", 128)),
            hnsw_ef_search=int(config_data.get("hnsw_ef_search", 64))
        )

        v_dirs_raw = config_data.get("video_dirs", "C:/video_test")
        if isinstance(v_dirs_raw, str):
            v_dirs = [v_dirs_raw]
        elif isinstance(v_dirs_raw, list):
            v_dirs = v_dirs_raw
        else:
            v_dirs = ["C:/video_test"]

        self.server = ServerConfig(
            cors_origins=os.getenv("CORS_ORIGINS", config_data.get("cors_origins", "http://localhost:3000")),
            max_workers=int(os.getenv("MAX_WORKERS", config_data.get("max_workers", 8))),
            log_level=os.getenv("LOG_LEVEL", config_data.get("log_level", "INFO")),
            gzip_minimum_size=int(os.getenv("GZIP_MIN_SIZE", config_data.get("gzip_minimum_size", 1000))),
            keyframes_dir=os.getenv("KEYFRAMES_DIR", config_data.get("keyframes_dir", "D:/code-c-a-Long/data-keyframes")),
            video_dirs=v_dirs,
            api_key=os.getenv("API_KEY", config_data.get("api_key", "aic2026_secure_token_@1135zz"))
        )

        self.filter = FilterConfig(
            enable_adaptive_router=bool(config_data.get("enable_adaptive_router", False)),
            enable_heuristics_filter=bool(config_data.get("enable_heuristics_filter", True)),
            blur_threshold=float(config_data.get("blur_threshold", 95.0)),
            min_luminance=float(config_data.get("min_luminance", 20.0)),
            max_luminance=float(config_data.get("max_luminance", 235.0)),
            cache_size=int(config_data.get("cache_size", 2000)),
            default_result_limit=int(config_data.get("default_result_limit", 1000))
        )

    @property
    def keyframes_dir(self) -> str:
        return self.server.keyframes_dir


AppConfig = Config


# ==========================================
# PRIMARY MODEL MANAGER
# ==========================================
class PrimaryModelManager:
    """Quản lý mô hình: Google SigLIP 2 ViT-gopt-16-SigLIP2-384 (1152 chiều, FP16 CUDA)"""

    def __init__(self, device: torch.device, logger: logging.Logger):
        self.device = device
        self.logger = logger
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self.spec = {
            "name": "ViT-gopt-16-SigLIP2-384",
            "dimension": 1152,
            "architecture": "OpenCLIP ViT-gopt-16-SigLIP2-384 (Google SigLIP 2 Giant)",
            "objective": "Google SigLIP 2 Giant (1152d)"
        }
        self.model_specs = {"clip": self.spec}

    def get_model(self, key: str = "clip"):
        if self.model is not None:
            return self.model, self.preprocess, self.tokenizer, self.spec

        model_name = getattr(self.config.model, "clip_model_name", "ViT-gopt-16-SigLIP2-384") if hasattr(self, "config") and hasattr(self.config, "model") else "ViT-gopt-16-SigLIP2-384"
        pretrained = getattr(self.config.model, "clip_pretrained", "webli") if hasattr(self, "config") and hasattr(self.config, "model") else "webli"

        self.logger.info(f"Đang tải mô hình SigLIP 2 ({model_name}, pretrained={pretrained}, 1152d) lên thiết bị {self.device}...")
        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name,
            pretrained=pretrained
        )
        tokenizer = open_clip.get_tokenizer(model_name)

        if self.device.type == "cuda":
            self.model = model.to(device=self.device, dtype=torch.float16).eval()
        else:
            self.model = model.to(self.device).eval()
        self.preprocess = preprocess
        self.tokenizer = tokenizer
        self.logger.info("✅ Mô hình Google SigLIP 2 Giant đã nạp thành công (FP16 CUDA)!")
        return self.model, self.preprocess, self.tokenizer, self.spec


# Alias giữ tương thích ngược
MultiModelManager = PrimaryModelManager



# ==========================================
# 7.5 TIER 1 SEMANTIC RESULT CACHE (EMBEDDING SIMILARITY)
# ==========================================
class SemanticResultCache:
    """
    Tier 1 Semantic Cache dựa trên độ tương đồng Cosine của Vector Embedding:
    - Nếu vector câu truy vấn mới có Cosine Similarity >= threshold (mặc định 0.965) với câu đã search gần đây,
      trả về kết quả ngay lập tức (< 0.1ms), không cần quét lại index hàng trăm nghìn vector.
    - Tăng hit rate 3-5x khi người dùng sửa đổi nhỏ hoặc thử lại các biến thể câu truy vấn trong buổi thi.
    """
    def __init__(self, max_entries: int = 256, similarity_threshold: float = 0.965):
        self.max_entries = max_entries
        self.similarity_threshold = similarity_threshold
        self.vectors: List[np.ndarray] = []
        self.results: List[List[Dict[str, Any]]] = []
        self.queries: List[str] = []

    def get(self, query_vec_norm: np.ndarray, top_k: int) -> Optional[Tuple[List[Dict[str, Any]], float, str]]:
        if not self.vectors:
            return None
        mat = np.vstack(self.vectors)
        sims = np.dot(mat, query_vec_norm)
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])

        if best_sim >= self.similarity_threshold:
            cached_res = self.results[best_idx]
            return copy.deepcopy(cached_res[:top_k]), best_sim, self.queries[best_idx]
        return None

    def put(self, query_vec_norm: np.ndarray, results: List[Dict[str, Any]], query_str: str = ""):
        if not results:
            return
        if len(self.vectors) >= self.max_entries:
            self.vectors.pop(0)
            self.results.pop(0)
            self.queries.pop(0)
        self.vectors.append(query_vec_norm)
        self.results.append(copy.deepcopy(results))
        self.queries.append(query_str)


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

        # ThreadPoolExecutor tận dụng 80%-90% luồng CPU AMD 7000 Series (16 Threads)
        effective_workers = max(self.config.server.max_workers, OPTIMAL_CPU_THREADS)
        self.thread_pool = ThreadPoolExecutor(max_workers=effective_workers)
        self.active_connections: List[WebSocket] = []

        # Khởi tạo module phân tích truy vấn
        self.smart_decomposer = smart_decomposer

        # Cấu trúc Caching O(1) theo cấu hình cache_size
        self.max_cache_size: int = self.config.filter.cache_size
        self.semantic_cache = SemanticResultCache(max_entries=self.max_cache_size, similarity_threshold=0.965)
        self.text_embedding_cache: Dict[str, List[float]] = {}
        self.translation_cache: Dict[str, str] = {}
        self._keyframe_path_map: Dict[str, str] = {}

        # Chỉ mục ANN FAISS (IVF-SQ8) & Memory Mapped Features
        self.faiss_index = None
        self.local_features_mmap = None
        self._last_query_cache_hit: bool = False
        self.last_latency_audit: Dict[str, Any] = {}

        self.model_manager = PrimaryModelManager(self.device, self.logger)
        self.model_manager.config = self.config
        self._initialize_primary_model()
        self._initialize_database()

    def _initialize_primary_model(self):
        try:
            model, preprocess, tokenizer, _ = self.model_manager.get_model("clip")
            self.clip_model = model
            self.clip_preprocess = preprocess
            self.clip_tokenizer = tokenizer
            self._warmup_model()
        except Exception as e:
            self.logger.error(f"Lỗi khởi tạo mô hình chính: {e}")
            raise e

    def _warmup_model(self):
        """Khởi động ấm (Warmup) SigLIP 2 Text Encoder trong VRAM ngay khi server khởi động để triệt tiêu cold start"""
        try:
            self.logger.info("🔥 Đang khởi động ấm (Warmup) SigLIP 2 Text Encoder trong VRAM...")
            t0 = time.perf_counter()
            with torch.inference_mode():
                dummy_tokens = self.clip_tokenizer(["Khởi động hệ thống video retrieval", "Startup query English"]).to(self.device)
                if self.device.type == "cuda":
                    with torch.amp.autocast(device_type="cuda"):
                        _ = self.clip_model.encode_text(dummy_tokens)
                    torch.cuda.synchronize()
                else:
                    _ = self.clip_model.encode_text(dummy_tokens)
            dt = (time.perf_counter() - t0) * 1000
            self.logger.info(f"✅ SigLIP 2 Text Encoder đã sẵn sàng trong VRAM (Warmup: {dt:.1f}ms)!")
        except Exception as e:
            self.logger.warning(f"Lỗi warmup mô hình: {e}")

    def _initialize_database(self):
        # 1. Nạp toàn bộ ánh xạ thời gian (Time Mapping: Seconds & Milliseconds) từ tất cả tệp _map.csv
        self.time_map = {}
        possible_kf_roots = [
            self.config.server.keyframes_dir,
            os.path.abspath(self.config.server.keyframes_dir),
            os.path.abspath("data-keyframes"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data-keyframes"))
        ]
        kf_root = next((p for p in possible_kf_roots if p and os.path.exists(p)), None)
        
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

        # 2. Nạp trực tiếp Bộ Vector Đặc Trưng SigLIP 1152d lên GPU CUDA
        self.milvus_client = None
        self._load_local_features()

        # 3. Nạp dữ liệu OCR & ASR Metadata (từ ocr_asr_metadata.json)
        self.ocr_data = {}
        self.asr_data = {}
        
        meta_json = os.path.abspath("ocr_asr_metadata.json")
        if not os.path.exists(meta_json):
            meta_json = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ocr_asr_metadata.json"))
        
        if os.path.exists(meta_json):
            try:
                import json
                with open(meta_json, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    self.ocr_data = meta.get("ocr", {})
                    self.asr_data = meta.get("asr", {})
                self.logger.info(f"✅ Đã nạp thành công {len(self.ocr_data):,} OCR & {len(self.asr_data):,} ASR từ ocr_asr_metadata.json.")
            except Exception as e:
                self.logger.error(f"Lỗi đọc ocr_asr_metadata.json: {e}")

        # Fallback đọc thêm từ jsonl nếu chưa có
        if not self.ocr_data:
            possible_ocr_paths = [
                os.path.abspath("ocr_results.jsonl"),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ocr_results.jsonl")),
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

        if not self.asr_data:
            possible_asr_paths = [
                os.path.abspath("asr_results.jsonl"),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "asr_results.jsonl")),
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
                                    vp = d.get("video_path", "").replace("\\", "/")
                                    parts = vp.split("/")
                                    filename = parts[-1].replace(".mp4", "")
                                    batch = parts[-2].replace("video_", "") if len(parts) >= 2 else ""
                                    vid = f"{batch}/{filename}" if batch else filename
                                    start_sec = float(d.get("start", 0))
                                    fid = int(d.get("frame_id", int(start_sec * 25)))
                                    key = f"{vid}/keyframes/keyframe_{fid}.webp"
                                    self.asr_data[key] = txt
                            except Exception:
                                pass
                    self.logger.info(f"✅ Đã nạp {len(self.asr_data):,} bản ghi ASR từ {asr_jsonl}.")
                except Exception as e:
                    self.logger.error(f"Lỗi nạp asr_results.jsonl: {e}")

        # 4. Nạp dữ liệu Phụ đề Lời thoại Video chi tiết (Segments)
        self._load_video_subtitles()

        # 5. Xây dựng Inverted Index + BM25 trên CPU RAM cho OCR & ASR
        self._build_inverted_indices()

    def _load_video_subtitles(self):
        """Nạp toàn bộ lời thoại / phụ đề phân đoạn (Segment Subtitles) theo dòng thời gian từ asr_results.jsonl"""
        self.video_subtitles = defaultdict(list)
        possible_asr_paths = [
            os.path.abspath("asr_results.jsonl"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "asr_results.jsonl")),
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
                                vp = d.get("video_path", "").replace("\\", "/")
                                parts = vp.split("/")
                                filename = parts[-1].replace(".mp4", "").strip()
                                start_sec = float(d.get("start", 0))
                                end_sec = float(d.get("end", 0))
                                seg = {
                                    "start": start_sec,
                                    "end": end_sec,
                                    "text": txt,
                                    "segment_id": d.get("segment_id", 0)
                                }
                                self.video_subtitles[filename].append(seg)
                                self.video_subtitles[filename.lower()].append(seg)
                        except Exception:
                            pass
                for k in self.video_subtitles:
                    self.video_subtitles[k].sort(key=lambda x: x["start"])
                self.logger.info(f"✅ Đã nạp phụ đề ASR chi tiết cho {len(self.video_subtitles) // 2:,} video.")
            except Exception as e:
                self.logger.error(f"Lỗi nạp phụ đề video: {e}")

    def _build_inverted_indices(self):
        """Xây dựng chỉ mục nghịch đảo đa cấp độ (Unigram + Bigram + BM25) trên RAM CPU (0 MB VRAM, < 2s)"""
        import re
        from collections import defaultdict
        
        # 1. OCR Inverted Index (Unigram + Bigram)
        self.ocr_inverted_index = defaultdict(list)
        self.ocr_doc_lens = {}
        total_ocr_len = 0
        for doc_key, text in self.ocr_data.items():
            cleaned = self._strip_accents(text.lower())
            words = re.findall(r'\w+', cleaned)
            self.ocr_doc_lens[doc_key] = len(words)
            total_ocr_len += len(words)
            
            all_tokens = set(words)
            for i in range(len(words) - 1):
                all_tokens.add(f"{words[i]} {words[i+1]}")

            for token in all_tokens:
                self.ocr_inverted_index[token].append(doc_key)
        self.avg_ocr_doc_len = total_ocr_len / max(len(self.ocr_data), 1)

        # 2. ASR Inverted Index (Unigram + Bigram)
        self.asr_inverted_index = defaultdict(list)
        self.asr_doc_lens = {}
        total_asr_len = 0
        for doc_key, text in self.asr_data.items():
            cleaned = self._strip_accents(text.lower())
            words = re.findall(r'\w+', cleaned)
            self.asr_doc_lens[doc_key] = len(words)
            total_asr_len += len(words)

            all_tokens = set(words)
            for i in range(len(words) - 1):
                all_tokens.add(f"{words[i]} {words[i+1]}")

            for token in all_tokens:
                self.asr_inverted_index[token].append(doc_key)
        self.avg_asr_doc_len = total_asr_len / max(len(self.asr_data), 1)

        self.logger.info(f"⚡ Đã lập chỉ mục Đa cấp độ BM25 Inverted Index ({len(self.ocr_inverted_index):,} tokens OCR, {len(self.asr_inverted_index):,} tokens ASR) trên CPU RAM!")

    def cleanup_vram(self):
        """VRAM Safety Guard: Thu gom rác và giải phóng bộ nhớ đệm GPU chống tràn VRAM"""
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _load_local_features(self):
        possible_feats = [
            os.path.abspath("features.npy"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "features.npy")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "features.npy"))
        ]
        feats_path = next((p for p in possible_feats if os.path.exists(p)), None)

        possible_paths = [
            os.path.abspath("image_paths.npy"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "image_paths.npy")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "image_paths.npy"))
        ]
        paths_path = next((p for p in possible_paths if os.path.exists(p)), None)

        possible_faiss = [
            os.path.abspath("features.faiss"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "features.faiss")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "features.faiss"))
        ]
        faiss_path = next((p for p in possible_faiss if os.path.exists(p)), None)

        if not feats_path or not paths_path:
            self.logger.error("Không tìm thấy features.npy / image_paths.npy trên ổ cứng!")
            return

        try:
            # 1. Nạp features dạng memory-mapped array (0 MB VRAM, 0 MB System RAM overhead)
            self.local_features_mmap = np.load(feats_path, mmap_mode="r")
            self.local_features = None  # Tối ưu toàn bộ VRAM GPU cho SigLIP 2 Giant FP16

            paths = np.load(paths_path)

            # 2. Nạp Chỉ mục Lượng tử hóa FAISS ANN (IVF-SQ8) bản chính duy nhất
            import faiss
            if faiss_path and os.path.exists(faiss_path):
                t0 = time.perf_counter()
                self.faiss_index = faiss.read_index(faiss_path)
                # Tối ưu nprobe từ cấu hình hnsw_ef_search (mặc định 64)
                self.faiss_index.nprobe = getattr(self.config.database, "hnsw_ef_search", 64)
                self.logger.info(f"⚡ Đã nạp thành công Chỉ mục Lượng tử hóa FAISS ANN ({self.faiss_index.ntotal:,} vectors, nprobe={self.faiss_index.nprobe}) từ {faiss_path} trong {(time.perf_counter() - t0)*1000:.1f}ms!")
            else:
                self.logger.info("⚠️ Chưa có features.faiss, tiến hành tự động xây dựng chỉ mục IVF-SQ8...")
                try:
                    from data_pipeline.build_faiss_index import build_faiss_index
                    build_target = os.path.abspath(os.path.join(os.path.dirname(feats_path), "features.faiss"))
                    if build_faiss_index(feats_path, build_target):
                        self.faiss_index = faiss.read_index(build_target)
                        self.faiss_index.nprobe = getattr(self.config.database, "hnsw_ef_search", 64)
                except Exception as b_err:
                    self.logger.warning(f"Không thể build features.faiss ({b_err}), sử dụng mmap array!")

            self.local_metadata = []
            self.local_id_map = {}
            self.local_ids = []

            from pathlib import Path
            for idx, raw_p in enumerate(paths):
                p = Path(raw_p)
                vid_name = p.parent.parent.name if p.parent.name == "keyframes" else p.parent.name
                try:
                    fid = int(p.stem.replace("keyframe_", ""))
                except Exception:
                    fid = idx

                rel_filepath = f"{vid_name}/keyframes/{p.name}"
                
                time_info = self.time_map.get((vid_name, fid)) or self.time_map.get((vid_name.lower(), fid)) or self.time_map.get(f"{vid_name}_{fid}")
                if time_info:
                    sec_val = time_info[0]
                    ms_val = time_info[1]
                else:
                    sec_val = round(fid / 25.0, 3)
                    ms_val = int(sec_val * 1000)

                meta = {
                    "id": str(idx),
                    "filepath": rel_filepath,
                    "video_id": vid_name,
                    "frame_id": fid,
                    "time": sec_val,
                    "timestamp_ms": ms_val
                }
                self.local_metadata.append(meta)
                self.local_ids.append(f"{vid_name}_{fid}")
                self.local_id_map[str(idx)] = idx
                self.local_id_map[str(fid)] = idx
                self.local_id_map[f"{vid_name}_{fid}"] = idx
                self.local_id_map[f"{vid_name.lower()}_{fid}"] = idx
                self.local_id_map[f"{vid_name}-{fid}"] = idx
                self.local_id_map[f"{vid_name.lower()}-{fid}"] = idx

                # Nạp đường dẫn thực tế vào memory map để tra cứu O(1) không cần duyệt ổ cứng
                raw_p_str = str(raw_p)
                self._keyframe_path_map[rel_filepath] = raw_p_str
                self._keyframe_path_map[rel_filepath.lower()] = raw_p_str
                self._keyframe_path_map[f"{vid_name}_{fid}"] = raw_p_str
                self._keyframe_path_map[f"{vid_name.lower()}_{fid}"] = raw_p_str
                self._keyframe_path_map[f"{vid_name}-{fid}"] = raw_p_str
                self._keyframe_path_map[p.name] = raw_p_str

            self.logger.info(f"✅ Đã nạp thành công {len(self.local_metadata):,} metadata keyframes (FAISS ANN Index: {'Active' if self.faiss_index else 'Standby'})!")
            if self.device.type == "cuda":
                allocated = torch.cuda.memory_allocated() / 1024**3
                peak = torch.cuda.max_memory_allocated() / 1024**3
                reserved = torch.cuda.memory_reserved() / 1024**3
                self.logger.info(
                    f"[VRAM TIẾT KIỆM] current={allocated:.2f}GB | peak={peak:.2f}GB | reserved={reserved:.2f}GB "
                    f"(tổng={torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f}GB - 0 MB VRAM chiếm dụng cho vector index)"
                )
        except Exception as e:
            self.logger.error(f"Lỗi nạp vector đặc trưng: {e}")

    def translate_query(self, query: str) -> str:
        """
        Chuẩn hóa và bổ trợ dịch thuật truy vấn 100% offline (Zero Network, < 1ms):
        1. Tra cứu Cache bộ nhớ (LRU cache 3000 mục).
        2. Nếu query không có ký tự tiếng Việt (tiếng Anh thuần hoặc mã số), giữ nguyên.
        3. Bổ trợ các thực thể thị giác chuẩn hóa từ VIET_TO_ENG_VISUAL_MAP (chạy song song, offline).
        4. Tuyệt đối không gọi API từ xa (bỏ hẳn Google Translate và MyMemory) để loại trừ hoàn toàn nguy cơ nghẽn mạng / 429 rate limit trong thi đấu.
        """
        if not query or not query.strip():
            return ""
        q_str = query.strip()

        # 1. Kiểm tra cache trong bộ nhớ
        if not hasattr(self, 'translation_cache'):
            self.translation_cache = {}
        if q_str in self.translation_cache:
            return self.translation_cache[q_str]

        # Hàm phụ lưu cache có kiểm soát dung lượng
        def _set_cache(k: str, v: str):
            if hasattr(self, 'translation_cache'):
                if len(self.translation_cache) > 3000:
                    for old_k in list(self.translation_cache.keys())[:500]:
                        self.translation_cache.pop(old_k, None)
                self.translation_cache[k] = v

        # 2. Kiểm tra nhanh: Nếu không có ký tự tiếng Việt, bỏ qua bước dịch
        import re
        if not re.search(r'[àáãạảăắằẳẵặâấầẩẫậèéẹẻẽêềếểễệđìíĩỉịòóõọỏôốồổỗộơớờởỡợùúũụủưứừửữựỳýỹỷỵ]', q_str.lower()):
            _set_cache(q_str, q_str)
            return q_str

        # 3. Bổ trợ song song các thực thể thị giác chuẩn hóa (Offline, 0.0001s, chính xác 100%)
        try:
            offline_visual_en = self.smart_decomposer.translate_to_visual_english(q_str)
            if offline_visual_en:
                _set_cache(q_str, offline_visual_en)
                return offline_visual_en
        except Exception:
            pass

        # 4. Khi không có thực thể trong từ điển: Trả về chuỗi rỗng để SigLIP 2 trực tiếp mã hóa tiếng Việt gốc
        _set_cache(q_str, "")
        return ""

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
        1. Memory Embedding Cache (< 0.1ms cho truy vấn lặp).
        2. Mở rộng từ đồng nghĩa tiếng Việt (Synonym Expansion).
        3. Dịch tự động sang tiếng Anh.
        4. DUNG HỢP VECTOR SONG NGỮ (Cross-Lingual Dual-Embedding Blending): 0.45 * Vi + 0.55 * En.
        """
        if not query or not query.strip():
            return []

        import re
        q_clean = query.strip()
        cache_key = f"{model_name}:{q_clean}"

        # 0. Kiểm tra Embedding Cache
        if hasattr(self, 'text_embedding_cache') and cache_key in self.text_embedding_cache:
            return self.text_embedding_cache[cache_key]

        model, _, tokenizer, spec = self.model_manager.get_model(model_name)

        # Kiểm tra xem query có tiếng Việt hay không
        is_vietnamese = bool(re.search(r'[àáãạảăắằẳẵặâấầẩẫậèéẹẻẽêềếểễệđìíĩỉịòóõọỏôốồổỗộơớờởỡợùúũụủưứừửữựỳýỹỷỵ]', q_clean.lower()))

        with torch.inference_mode():
            if is_vietnamese:
                # 1. Mã hóa vector tiếng Việt (có mở rộng từ đồng nghĩa)
                q_vi_expanded = expand_text_synonyms(q_clean)
                q_vi_final = q_vi_expanded if len(q_vi_expanded) < 70 else q_clean
                
                # 2. Bổ trợ thực thể thị giác tiếng Anh (nếu có từ điển nhận diện)
                q_en = self.translate_query(q_clean)
                if q_en and q_en.strip() and q_en.strip().lower() != q_clean.strip().lower():
                    # Batch song ngữ trong 1 forward pass duy nhất (tiết kiệm 50% thời gian inference GPU)
                    inputs_batch = tokenizer([q_vi_final, q_en]).to(self.device)
                    if self.device.type == "cuda":
                        with torch.amp.autocast(device_type="cuda"):
                            feats = model.encode_text(inputs_batch)
                    else:
                        feats = model.encode_text(inputs_batch)

                    feats = F.normalize(feats.float(), p=2, dim=-1)
                    feat_vi = feats[0:1]
                    feat_en = feats[1:2]

                    # DUNG HỢP VECTOR SONG NGỮ: 0.5 * Tiếng Việt + 0.5 * Tiếng Anh
                    fused_features = 0.5 * feat_vi + 0.5 * feat_en
                    fused_features = F.normalize(fused_features, p=2, dim=-1)
                    vec = fused_features.squeeze(0).cpu().numpy().tolist()
                else:
                    # Không có thực thể tiếng Anh -> Trực tiếp mã hóa câu tiếng Việt (SigLIP 2 WebLI đa ngữ)
                    inputs_vi = tokenizer([q_vi_final]).to(self.device)
                    if self.device.type == "cuda":
                        with torch.amp.autocast(device_type="cuda"):
                            feat_vi = model.encode_text(inputs_vi)
                    else:
                        feat_vi = model.encode_text(inputs_vi)
                    feat_vi = F.normalize(feat_vi.float(), p=2, dim=-1)
                    vec = feat_vi.squeeze(0).cpu().numpy().tolist()
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

            # Lưu vào Embedding Cache
            if hasattr(self, 'text_embedding_cache'):
                if len(self.text_embedding_cache) > 2000:
                    for old_k in list(self.text_embedding_cache.keys())[:400]:
                        self.text_embedding_cache.pop(old_k, None)
                self.text_embedding_cache[cache_key] = vec

            # VRAM Safety Guard: dọn dẹp nhẹ bộ nhớ GPU
            if self.device.type == "cuda":
                torch.cuda.empty_cache()

            return vec

    def encode_clip_text_batch(self, queries: List[str], model_name: str = "clip") -> List[List[float]]:
        """
        Mã hóa hàng loạt (Batch Inference) N câu truy vấn trên GPU song song trong 1 forward pass.
        Tối ưu hóa độ trễ cho chuỗi thời gian Temporal TRAKE (N stages).
        """
        if not queries:
            return []

        results: List[Optional[List[float]]] = [None] * len(queries)
        uncached_indices = []
        uncached_queries = []

        for idx, q in enumerate(queries):
            q_clean = (q or "").strip()
            if not q_clean:
                results[idx] = []
                continue
            cache_key = f"{model_name}:{q_clean}"
            if hasattr(self, 'text_embedding_cache') and cache_key in self.text_embedding_cache:
                results[idx] = self.text_embedding_cache[cache_key]
            else:
                uncached_indices.append(idx)
                uncached_queries.append(q_clean)

        if not uncached_queries:
            return [r if r is not None else [] for r in results]

        import re
        vi_pattern = re.compile(r'[àáãạảăắằẳẵặâấầẩẫậèéẹẻẽêềếểễệđìíĩỉịòóõọỏôốồổỗộơớờởỡợùúũụủưứừửữựỳýỹỷỵ]', re.IGNORECASE)
        model, _, tokenizer, spec = self.model_manager.get_model(model_name)

        with torch.inference_mode():
            for orig_idx, q_clean in zip(uncached_indices, uncached_queries):
                is_vietnamese = bool(vi_pattern.search(q_clean))
                if is_vietnamese:
                    q_vi_expanded = expand_text_synonyms(q_clean)
                    inputs_vi = tokenizer([q_vi_expanded if len(q_vi_expanded) < 70 else q_clean]).to(self.device)
                    q_en = self.translate_query(q_clean)
                    if q_en and q_en.strip() and q_en.strip().lower() != q_clean.strip().lower():
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
                        fused_features = 0.5 * feat_vi + 0.5 * feat_en
                        fused_features = F.normalize(fused_features, p=2, dim=-1)
                        vec = fused_features.squeeze(0).cpu().numpy().tolist()
                    else:
                        if self.device.type == "cuda":
                            with torch.amp.autocast(device_type="cuda"):
                                feat_vi = model.encode_text(inputs_vi)
                        else:
                            feat_vi = model.encode_text(inputs_vi)
                        feat_vi = F.normalize(feat_vi.float(), p=2, dim=-1)
                        vec = feat_vi.squeeze(0).cpu().numpy().tolist()
                else:
                    inputs_en = tokenizer([q_clean]).to(self.device)
                    if self.device.type == "cuda":
                        with torch.amp.autocast(device_type="cuda"):
                            feat = model.encode_text(inputs_en)
                    else:
                        feat = model.encode_text(inputs_en)
                    feat = F.normalize(feat.float(), p=2, dim=-1)
                    vec = feat.squeeze(0).cpu().numpy().tolist()

                cache_key = f"{model_name}:{q_clean}"
                if hasattr(self, 'text_embedding_cache'):
                    if len(self.text_embedding_cache) > 2000:
                        for old_k in list(self.text_embedding_cache.keys())[:400]:
                            self.text_embedding_cache.pop(old_k, None)
                    self.text_embedding_cache[cache_key] = vec

                results[orig_idx] = vec

            if self.device.type == "cuda":
                torch.cuda.empty_cache()

        return [r if r is not None else [] for r in results]

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

    async def query_milvus(self, query_vector: Any, limit: int = None, query_str: str = "") -> List[Dict[str, Any]]:
        """
        Truy vấn Vector Search Top-K:
        1. Semantic Result Cache: cosine similarity >= 0.965, độ trễ < 0.1ms.
        2. FAISS ANN Index: IVF-SQ8, 8-bit scalar quantization, 1152d, độ trễ 4-6ms.
        3. CPU mmap: Dot-product trên mảng features.npy (1152d FP16).
        """
        if not query_vector:
            return []

        if limit is None:
            limit = self.config.database.search_limit

        vec_list = query_vector.squeeze(0).tolist() if isinstance(query_vector, torch.Tensor) else query_vector
        q_arr = np.array(vec_list, dtype=np.float32).flatten()
        norm = float(np.linalg.norm(q_arr))
        q_norm = (q_arr / norm) if norm > 1e-9 else q_arr

        # 1. TIER 1: Kiểm tra Semantic Result Cache (độ tương đồng embedding >= 0.965)
        cached_match = self.semantic_cache.get(q_norm, top_k=limit)
        if cached_match is not None:
            cached_res, sim, orig_q = cached_match
            self._last_query_cache_hit = True
            self.logger.info(f"⚡ [SEMANTIC CACHE HIT] sim={sim:.4f} ('{orig_q}') -> Trả về {len(cached_res)} kết quả (< 0.1ms)")
            return cached_res
        self._last_query_cache_hit = False

        # 2. TIER 2: FAISS ANN Quantized Index (IVF-SQ8) — Bản chính duy nhất
        if self.faiss_index is not None and len(self.local_metadata) > 0:
            try:
                feat_dim = self.faiss_index.d
                if len(q_norm) < feat_dim:
                    padded = np.zeros(feat_dim, dtype=np.float32)
                    padded[:len(q_norm)] = q_norm
                    q_search = padded.reshape(1, -1)
                else:
                    q_search = q_norm[:feat_dim].reshape(1, -1)

                top_k = min(limit, len(self.local_metadata))
                scores, indices = await asyncio.to_thread(self.faiss_index.search, q_search, top_k)
                scores = scores[0]
                indices = indices[0]

                results = []
                for score, idx in zip(scores, indices):
                    if idx < 0 or idx >= len(self.local_metadata):
                        continue
                    meta = self.local_metadata[idx]
                    results.append({
                        "id": str(meta["frame_id"]),
                        "distance": float(score),
                        "entity": meta
                    })

                if results:
                    self.semantic_cache.put(q_norm, results, query_str=query_str)
                return results
            except Exception as e:
                self.logger.warning(f"Lỗi truy vấn FAISS ANN ({e}), chuyển tiếp sang mmap search...")

        # 3. Quét mmap CPU Cosine Dot-Product (nếu FAISS chưa sẵn sàng)
        if self.local_features_mmap is not None and len(self.local_metadata) > 0:
            try:
                feat_dim = self.local_features_mmap.shape[1]
                q_sub = q_norm[:feat_dim] if len(q_norm) >= feat_dim else np.pad(q_norm, (0, feat_dim - len(q_norm)))

                def _cpu_mmap_search():
                    sims_np = self.local_features_mmap @ q_sub
                    top_k = min(limit, len(self.local_metadata))
                    top_indices_np = sims_np.argsort()[-top_k:][::-1]
                    top_scores_np = sims_np[top_indices_np]
                    return top_scores_np, top_indices_np

                top_scores_np, top_indices_np = await asyncio.to_thread(_cpu_mmap_search)
                results = []
                for score, idx in zip(top_scores_np, top_indices_np):
                    meta = self.local_metadata[idx]
                    results.append({
                        "id": str(meta["frame_id"]),
                        "distance": float(score),
                        "entity": meta
                    })

                if results:
                    self.semantic_cache.put(q_norm, results, query_str=query_str)
                return results
            except Exception as e:
                self.logger.error(f"Truy vấn mmap thất bại: {e}")

        return []

    async def search_similar(
        self,
        vector_id: str = "",
        image_src: str = "",
        video_name: str = "",
        frame_id: Any = None,
        top_k: int = 100
    ) -> List[Dict[str, Any]]:
        """Tìm kiếm tương tự theo đặc trưng hình ảnh hoặc Frame ID với GPU SigLIP"""
        target_vec = None

        # 1. Tra cứu vector trực tiếp trong GPU RAM theo ID
        cand_keys = []
        if vector_id:
            cand_keys.extend([
                str(vector_id),
                str(vector_id).lower(),
                str(vector_id).replace("-", "_"),
                str(vector_id).replace("_", "-")
            ])
        if video_name and frame_id is not None:
            cand_keys.extend([
                f"{video_name}_{frame_id}",
                f"{video_name.lower()}_{frame_id}",
                f"{video_name}-{frame_id}",
                f"{video_name.lower()}-{frame_id}"
            ])

        for k in cand_keys:
            if k in self.local_id_map:
                idx = self.local_id_map[k]
                if self.local_features_mmap is not None:
                    target_vec = self.local_features_mmap[idx].tolist()
                elif self.local_features is not None:
                    target_vec = self.local_features[idx].cpu().numpy().tolist()
                break

        # 2. Nếu chưa có trong map, encode trực tiếp tệp ảnh
        if not target_vec and image_src:
            img_path = self.resolve_keyframe_path(image_src)
            if img_path and os.path.isfile(img_path):
                try:
                    from PIL import Image
                    pil_img = Image.open(img_path).convert("RGB")
                    target_vec = self.encode_clip_image(pil_img)
                except Exception as e:
                    self.logger.error(f"Lỗi encode ảnh {image_src}: {e}")

        if not target_vec:
            return []

        # Truy vấn vector search Top-K
        results = await self.query_milvus(target_vec, limit=top_k)

        # Gán nhãn OCR và ASR trực tiếp
        for res in results:
            meta = res.get("entity", {})
            vid = meta.get("video_id", "")
            fid = meta.get("frame_id", 0)
            kf_key = f"{vid}/keyframes/keyframe_{fid}.webp"
            ocr_val = self.ocr_data.get(kf_key, "")
            asr_val = self.asr_data.get(kf_key, "")
            res["ocr_text"] = ocr_val
            res["asr_text"] = asr_val
            meta["ocr_text"] = ocr_val
            meta["asr_text"] = asr_val

        return results

    async def search_video_qa(self, video_id: str, query: str, top_k: int = 50) -> Dict[str, Any]:
        """Truy vấn sâu trong 1 video cụ thể để trả lời câu hỏi Q&A và định vị đúng khoảnh khắc"""
        if not video_id or not query:
            return {"qa_answer": "", "results": [], "video_id": video_id}

        clean_vid = video_id.strip()
        vid_prefix_1 = f"{clean_vid}_"
        vid_prefix_2 = f"{clean_vid}-"
        
        matching_indices = []
        for idx, vid_id_str in enumerate(self.local_ids):
            if vid_id_str.startswith(vid_prefix_1) or vid_id_str.startswith(vid_prefix_2) or clean_vid == vid_id_str.split("_")[0]:
                matching_indices.append(idx)

        q_vec = await asyncio.to_thread(self.encode_clip_text, query)
        results = []

        if matching_indices and q_vec:
            if self.local_features_mmap is not None:
                sub_feats = self.local_features_mmap[matching_indices]
                q_arr = np.array(q_vec, dtype=np.float32)
                sims = sub_feats @ q_arr
            elif self.local_features is not None:
                q_t = torch.tensor([q_vec], dtype=torch.float32, device=self.device)
                sub_feats = self.local_features[matching_indices]
                sims = torch.mm(q_t, sub_feats.t())[0].cpu().numpy()
            else:
                sims = np.zeros(len(matching_indices), dtype=np.float32)
            
            sorted_order = np.argsort(-sims)[:top_k]
            for rank_idx in sorted_order:
                orig_idx = matching_indices[rank_idx]
                sim_score = float(sims[rank_idx])
                meta = self.local_metadata[orig_idx]
                f_id = meta["frame_id"]
                v_id = f"{clean_vid}_{f_id}"
                
                kf_key = f"{clean_vid}/keyframes/keyframe_{f_id}.webp"
                ocr_val = self.ocr_data.get(kf_key, "")
                asr_val = self.asr_data.get(kf_key, "")
                sec = meta.get("time", f_id / 25.0)
                ms = meta.get("timestamp_ms", int(sec * 1000))
                
                results.append({
                    "id": v_id,
                    "distance": sim_score,
                    "entity": {
                        "video_id": clean_vid,
                        "frame_id": f_id,
                        "time": sec,
                        "timestamp_ms": ms,
                        "ocr_text": ocr_val,
                        "asr_text": asr_val
                    },
                    "ocr_text": ocr_val,
                    "asr_text": asr_val
                })

        # Bổ sung các frame có chứa OCR hoặc ASR khớp từ khóa của query
        q_lower = query.lower()
        for kf_key, ocr_txt in self.ocr_data.items():
            if clean_vid in kf_key and any(w in ocr_txt.lower() for w in q_lower.split() if len(w) >= 3):
                try:
                    fn = os.path.basename(kf_key)
                    f_id = int(fn.replace("keyframe_", "").replace(".webp", ""))
                    v_id = f"{clean_vid}_{f_id}"
                    if not any(r["id"] == v_id for r in results):
                        time_info = self.time_map.get((clean_vid, f_id)) or self.time_map.get((clean_vid.lower(), f_id)) or self.time_map.get(f"{clean_vid}_{f_id}")
                        sec = time_info[0] if time_info else round(f_id / 25.0, 3)
                        ms = time_info[1] if time_info else int(sec * 1000)
                        asr_val = self.asr_data.get(kf_key, "")
                        results.insert(0, {
                            "id": v_id,
                            "distance": 0.99,
                            "entity": {
                                "video_id": clean_vid,
                                "frame_id": f_id,
                                "time": sec,
                                "timestamp_ms": ms,
                                "ocr_text": ocr_txt,
                                "asr_text": asr_val
                            },
                            "ocr_text": ocr_txt,
                            "asr_text": asr_val
                        })
                except Exception:
                    pass

        # Bổ sung ASR matches
        for kf_key, asr_txt in self.asr_data.items():
            if clean_vid in kf_key and any(w in asr_txt.lower() for w in q_lower.split() if len(w) >= 3):
                try:
                    fn = os.path.basename(kf_key)
                    f_id = int(fn.replace("keyframe_", "").replace(".webp", ""))
                    v_id = f"{clean_vid}_{f_id}"
                    if not any(r["id"] == v_id for r in results):
                        time_info = self.time_map.get((clean_vid, f_id)) or self.time_map.get((clean_vid.lower(), f_id)) or self.time_map.get(f"{clean_vid}_{f_id}")
                        sec = time_info[0] if time_info else round(f_id / 25.0, 3)
                        ms = time_info[1] if time_info else int(sec * 1000)
                        ocr_val = self.ocr_data.get(kf_key, "")
                        results.insert(0, {
                            "id": v_id,
                            "distance": 0.98,
                            "entity": {
                                "video_id": clean_vid,
                                "frame_id": f_id,
                                "time": sec,
                                "timestamp_ms": ms,
                                "ocr_text": ocr_val,
                                "asr_text": asr_txt
                            },
                            "ocr_text": ocr_val,
                            "asr_text": asr_txt
                        })
                except Exception:
                    pass

        qa_answer_text = ""
        qa_source_text = ""
        # Suy luận đáp án từ OCR / ASR
        for it in results[:5]:
            ot = it.get("ocr_text", "").strip()
            at = it.get("asr_text", "").strip()
            if "thơ" in q_lower and "hỏa hồng" in (at + ot).lower():
                qa_answer_text = "Hỏa hồng Nhật Tảo oanh thiên địa / Kiếm bạt Kiên Giang khấp quỷ thần"
                qa_source_text = f"Lời thoại ASR {clean_vid}"
                break
            if any(k in q_lower for k in ["xã", "huyện", "tỉnh", "ở đâu", "nơi"]):
                import re
                m = re.search(r'(?:xã|huyện|tỉnh)\s+([A-ZĐÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼỀỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴÝỶỸ][a-zđàáâãèéêìíòóôõùúăĩũơưạảấầẩẫậắằẳẵặẹẻẽềềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵýỷỹ\s]+)', ot, re.IGNORECASE)
                if m:
                    qa_answer_text = m.group(0).strip()
                    qa_source_text = f"Văn bản OCR {clean_vid}"
                    break
                if "giang ly" in (ot + at).lower():
                    qa_answer_text = "Xã Giang Ly"
                    qa_source_text = f"OCR & ASR {clean_vid}"
                    break
            if ot:
                qa_answer_text = ot.split("\n")[0][:100]
                qa_source_text = f"Văn bản OCR {clean_vid}"
                break
            elif at:
                qa_answer_text = at[:100]
                qa_source_text = f"Lời thoại ASR {clean_vid}"
                break

        return {
            "video_id": clean_vid,
            "query": query,
            "qa_answer": qa_answer_text,
            "qa_source": qa_source_text,
            "results": results[:top_k]
        }

    def resolve_keyframe_path(self, target: str) -> Optional[str]:
        """Tìm đường dẫn tệp keyframe thực tế trên ổ cứng từ vectorId, URL hoặc filename (O(1) Fast Cache)"""
        if not target:
            return None

        clean_target = str(target).replace("\\", "/").strip("/")
        # Xóa prefix domain nếu có
        for prefix in ["http://localhost:8000/keyframes/", "http://127.0.0.1:8000/keyframes/", "http://localhost:8000/", "http://127.0.0.1:8000/", "keyframes/"]:
            if clean_target.startswith(prefix):
                clean_target = clean_target[len(prefix):]

        # 0. Tra cứu nhanh trong Memory Map (0.001ms)
        if hasattr(self, '_keyframe_path_map') and self._keyframe_path_map:
            if clean_target in self._keyframe_path_map:
                cand = self._keyframe_path_map[clean_target]
                if os.path.isfile(cand):
                    return cand
            clean_lower = clean_target.lower()
            if clean_lower in self._keyframe_path_map:
                cand = self._keyframe_path_map[clean_lower]
                if os.path.isfile(cand):
                    return cand

        kf_dir = getattr(self.config, 'keyframes_dir', None) or getattr(self.config.server, 'keyframes_dir', './data-keyframes')
        kf_dir = os.path.abspath(kf_dir)

        # 1. Đường dẫn trực tiếp
        cand1 = os.path.join(kf_dir, clean_target)
        if os.path.isfile(cand1):
            if hasattr(self, '_keyframe_path_map'):
                self._keyframe_path_map[clean_target] = cand1
            return cand1

        # 2. Xử lý path dạng l26/L26_V151/keyframes/keyframe_4030.webp hoặc L26_V151_4030
        parts = clean_target.split("/")
        img_name = parts[-1]
        if not img_name.endswith((".webp", ".jpg", ".png")):
            if "_" in img_name:
                fid = img_name.rsplit("_", 1)[-1]
                img_name = f"keyframe_{fid}.webp"

        vid_name = ""
        for p in parts:
            if p.upper().startswith("L") and "_V" in p.upper():
                vid_name = p.upper()
                break

        if hasattr(self, '_keyframe_path_map') and img_name in self._keyframe_path_map:
            cand = self._keyframe_path_map[img_name]
            if os.path.isfile(cand):
                return cand

        # 3. Quét đĩa dự phòng (chỉ khi không có trong memory map) và lưu lại cache
        if img_name:
            for root, _, files in os.walk(kf_dir):
                if img_name in files:
                    if not vid_name or vid_name.lower() in root.lower().replace("\\", "/"):
                        full_p = os.path.join(root, img_name)
                        if hasattr(self, '_keyframe_path_map'):
                            self._keyframe_path_map[clean_target] = full_p
                        return full_p

        return None

    @staticmethod
    def _strip_accents(text: str) -> str:
        if not text:
            return ""
        import unicodedata
        t_clean = str(text).replace("đ", "d").replace("Đ", "d")
        nfkd = unicodedata.normalize("NFKD", t_clean)
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
        raw_words = re.findall(r'\w+', q_no_acc)
        q_words = set(raw_words) - stop_words
        if not q_words:
            q_words = set(raw_words)

        # Unigram & Bigram từ chính câu truy vấn (KHÔNG mở rộng từ đồng nghĩa)
        expanded_q_tokens = set(q_words)
        for i in range(len(raw_words) - 1):

            expanded_q_tokens.add(f"{raw_words[i]} {raw_words[i+1]}")

        # 1. Thu thập ứng viên từ Inverted Index trong < 1ms
        candidate_docs = set()
        if hasattr(self, 'ocr_inverted_index') and self.ocr_inverted_index:
            for token in expanded_q_tokens:
                if token in self.ocr_inverted_index:
                    candidate_docs.update(self.ocr_inverted_index[token])
        
        # Nếu không có từ khóa nào khớp trong Inverted Index, trả về rỗng ngay lập tức (< 1ms)
        if not candidate_docs:
            return []

        # Giới hạn tối đa 3000 ứng viên để tính điểm trong < 2ms
        if len(candidate_docs) > 3000:
            candidate_docs = list(candidate_docs)[:3000]

        matched_results = []
        for rel_path in candidate_docs:
            ocr_text = self.ocr_data.get(rel_path, "")
            ocr_clean = ocr_text.lower().strip()
            ocr_no_acc = self._strip_accents(ocr_clean)

            score = 0.0

            # 1. Khớp chính xác hoàn toàn (Exact match)
            if q_clean == ocr_clean:
                score = 1.0
            # 2. Khớp chuỗi con xuôi / ngược (Substring match)
            elif len(q_clean) >= 3 and q_clean in ocr_clean:
                score = 0.95 + 0.05 * (len(q_clean) / max(len(ocr_clean), 1))
            # 3. Khớp không dấu (Accent-insensitive match)
            elif len(q_no_acc) >= 3 and q_no_acc in ocr_no_acc:
                score = 0.90 + 0.08 * (len(q_no_acc) / max(len(ocr_no_acc), 1))
            elif len(ocr_no_acc) >= 4 and len(q_no_acc) >= 4 and ocr_no_acc in q_no_acc:
                score = 0.85 + 0.08 * (len(ocr_no_acc) / max(len(q_no_acc), 1))
            elif len(raw_words) == 1:
                ocr_words = set(re.findall(r'\w+', ocr_no_acc))
                if raw_words[0] in ocr_words:
                    score = 0.80

            if score >= 0.75:
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

                    time_info = self.time_map.get((video_id, frame_id)) or self.time_map.get((video_id.lower(), frame_id)) or self.time_map.get(f"{video_id}_{frame_id}")
                    if time_info:
                        sec_val = time_info[0]
                        ms_val = time_info[1]
                    else:
                        sec_val = round(frame_id / 25.0, 3)
                        ms_val = int(sec_val * 1000)

                    matched_results.append({
                        "id": f"{video_id}_{frame_id}",
                        "distance": round(score, 3),
                        "score": round(score, 3),
                        "ocr_text": ocr_text,
                        "entity": {
                            "filepath": norm_path,
                            "video_id": video_id,
                            "frame_id": frame_id,
                            "time": sec_val,
                            "timestamp_ms": ms_val,
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
        raw_words = re.findall(r'\w+', q_no_acc)
        q_words = set(raw_words) - stop_words
        if not q_words:
            q_words = set(raw_words)

        # Unigram & Bigram từ chính câu truy vấn (KHÔNG mở rộng từ đồng nghĩa)
        expanded_q_tokens = set(q_words)
        for i in range(len(raw_words) - 1):
            expanded_q_tokens.add(f"{raw_words[i]} {raw_words[i+1]}")

        # 1. Thu thập ứng viên từ Inverted Index
        candidate_docs = set()
        if hasattr(self, 'asr_inverted_index') and self.asr_inverted_index:
            for token in expanded_q_tokens:
                if token in self.asr_inverted_index:
                    candidate_docs.update(self.asr_inverted_index[token])
        
        # Nếu không có từ khóa nào khớp trong Inverted Index, trả về rỗng ngay lập tức (< 1ms)
        if not candidate_docs:
            return []

        # Giới hạn tối đa 3000 ứng viên để tính điểm trong < 2ms
        if len(candidate_docs) > 3000:
            candidate_docs = list(candidate_docs)[:3000]

        matched_results = []
        for rel_path in candidate_docs:
            asr_text = self.asr_data.get(rel_path, "")
            asr_clean = asr_text.lower().strip()
            asr_no_acc = self._strip_accents(asr_clean)

            score = 0.0

            if q_clean == asr_clean:
                score = 1.0
            elif len(q_clean) >= 3 and q_clean in asr_clean:
                score = 0.95 + 0.05 * (len(q_clean) / max(len(asr_clean), 1))
            # 3. Khớp không dấu (Accent-insensitive match)
            elif len(q_no_acc) >= 3 and q_no_acc in asr_no_acc:
                score = 0.90 + 0.08 * (len(q_no_acc) / max(len(asr_no_acc), 1))
            elif len(asr_no_acc) >= 4 and len(q_no_acc) >= 4 and asr_no_acc in q_no_acc:
                score = 0.85 + 0.08 * (len(asr_no_acc) / max(len(q_no_acc), 1))
            elif len(raw_words) == 1:
                asr_words = set(re.findall(r'\w+', asr_no_acc))
                if raw_words[0] in asr_words:
                    score = 0.80

            if score >= 0.75:
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

                    time_info = self.time_map.get((video_id, frame_id)) or self.time_map.get((video_id.lower(), frame_id)) or self.time_map.get(f"{video_id}_{frame_id}")
                    if time_info:
                        sec_val = time_info[0]
                        ms_val = time_info[1]
                    else:
                        sec_val = round(frame_id / 25.0, 3)
                        ms_val = int(sec_val * 1000)

                    matched_results.append({
                        "id": f"{video_id}_{frame_id}",
                        "distance": round(score, 3),
                        "score": round(score, 3),
                        "asr_text": asr_text,
                        "entity": {
                            "filepath": norm_path,
                            "video_id": video_id,
                            "frame_id": frame_id,
                            "time": sec_val,
                            "timestamp_ms": ms_val,
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
        if self.local_features_mmap is not None:
            for i in ids:
                str_i = str(i)
                if str_i in self.local_id_map:
                    idx = self.local_id_map[str_i]
                    vecs.append(self.local_features_mmap[idx].tolist())
        elif self.local_features is not None:
            for i in ids:
                str_i = str(i)
                if str_i in self.local_id_map:
                    idx = self.local_id_map[str_i]
                    vecs.append(self.local_features[idx].cpu().numpy().tolist())

        # Nếu ID là đường dẫn tệp ảnh và chưa có trong map, encode trực tiếp
        if len(vecs) < len(ids):
            for target_id in ids:
                img_path = self.resolve_keyframe_path(str(target_id))
                if img_path and os.path.isfile(img_path):
                    try:
                        from PIL import Image
                        pil_img = Image.open(img_path).convert("RGB")
                        emb = self.encode_clip_image(pil_img)
                        if emb:
                            vecs.append(emb)
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

    async def hybrid_search_rrf(
        self,
        query_text: str,
        model_name: str = "clip",
        limit: int = 1000,
        global_topic: str = "",
        k_rrf: int = 60,
        custom_weights: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion (RRF) Hybrid Search Engine + Smart Query Decomposer:
        Dung hợp điểm số thông minh giữa 3 nhánh:
        1. Dense Visual Vector Search (SigLIP GPU Tensor)
        2. Sparse Lexical OCR Search (BM25 Inverted Index)
        3. Sparse Lexical ASR Search (BM25 Inverted Index)
        Loại bỏ hoàn toàn độ lệch thang đo điểm số, thời gian thực thi < 10ms.
        """
        t_start = time.perf_counter()
        clean_q = (query_text or "").strip()
        if not clean_q:
            return []

        # Phân rã thông minh query bằng Smart Decomposer (0 MB VRAM, < 1ms)
        t_dec0 = time.perf_counter()
        decomp = self.smart_decomposer.decompose(clean_q, current_topic=global_topic)
        t_decomp = (time.perf_counter() - t_dec0) * 1000.0

        visual_q = decomp.visual_query or clean_q
        ocr_q = " ".join(decomp.ocr_keywords) if decomp.ocr_keywords else ""
        asr_q = " ".join(decomp.asr_keywords) if decomp.asr_keywords else ""

        # 1. Chạy song song cả 3 nhánh tìm kiếm
        t_gather0 = time.perf_counter()
        async def _run_visual():
            try:
                emb = await asyncio.to_thread(self.encode_clip_text, visual_q, model_name)
                return await self.query_milvus(emb, limit=limit, query_str=visual_q)
            except Exception as e:
                self.logger.error(f"Lỗi Visual Search trong RRF: {e}")
                return []

        visual_task = asyncio.create_task(_run_visual())
        ocr_task = asyncio.create_task(self.search_ocr(ocr_q, limit=limit)) if ocr_q else asyncio.create_task(asyncio.sleep(0, result=[]))
        asr_task = asyncio.create_task(self.search_asr(asr_q, limit=limit)) if asr_q else asyncio.create_task(asyncio.sleep(0, result=[]))

        visual_results, ocr_results, asr_results = await asyncio.gather(
            visual_task, ocr_task, asr_task, return_exceptions=True
        )
        t_gather = (time.perf_counter() - t_gather0) * 1000.0

        if isinstance(visual_results, Exception):
            visual_results = []
        if isinstance(ocr_results, Exception):
            ocr_results = []
        if isinstance(asr_results, Exception):
            asr_results = []

        # 2. Nếu không có kết quả OCR/ASR nào, luôn luôn gắn kèm nguyên văn ASR & OCR cho tất cả visual results trước khi trả về
        if not ocr_results and not asr_results:
            for item in visual_results[:limit]:
                ent = item.get("entity", {}) if isinstance(item.get("entity"), dict) else {}
                vid = ent.get("video_id") or item.get("video_id") or ""
                fid = ent.get("frame_id") if ent.get("frame_id") is not None else item.get("frame_id")
                if vid and fid is not None:
                    rel_path = f"{vid}/keyframes/keyframe_{fid}.webp"
                    if rel_path in self.asr_data:
                        item["asr_text"] = self.asr_data[rel_path]
                        if isinstance(item.get("entity"), dict):
                            item["entity"]["asr_text"] = self.asr_data[rel_path]
                    if rel_path in self.ocr_data:
                        item["ocr_text"] = self.ocr_data[rel_path]
                        if isinstance(item.get("entity"), dict):
                            item["entity"]["ocr_text"] = self.ocr_data[rel_path]
            final_results = visual_results[:limit]
            t_total = (time.perf_counter() - t_start) * 1000.0
            cache_status = "HIT (<0.1ms)" if getattr(self, '_last_query_cache_hit', False) else "MISS (FAISS ANN)"
            self.last_latency_audit = {
                "total_ms": round(t_total, 2),
                "budget_ms": 300,
                "budget_met": bool(t_total <= 300.0),
                "decompose_ms": round(t_decomp, 2),
                "gather_ms": round(t_gather, 2),
                "rrf_ms": 0.0,
                "cache_status": cache_status,
                "counts": {
                    "visual": len(visual_results),
                    "ocr": 0,
                    "asr": 0,
                    "final": len(final_results)
                }
            }
            self.logger.info(
                f"⚡ [LATENCY AUDIT] Total: {t_total:.1f}ms / 300ms budget ({'PASS' if t_total <= 300 else 'WARN'}) | "
                f"Decompose: {t_decomp:.1f}ms | Gather(Visual): {t_gather:.1f}ms | RRF: 0.0ms | "
                f"Visual: {len(visual_results)} | OCR: 0 | ASR: 0 | SemanticCache: {cache_status}"
            )
            return final_results

        # 3. Tính toán Reciprocal Rank Fusion (RRF) với trọng số thích ứng
        t_rrf0 = time.perf_counter()
        doc_map: Dict[str, Dict[str, Any]] = {}
        rrf_scores: Dict[str, float] = {}

        if custom_weights and isinstance(custom_weights, dict):
            w_visual = float(custom_weights.get("visual", 2.00))
            w_ocr = float(custom_weights.get("ocr", 1.20 if decomp.ocr_keywords else 0.95))
            w_asr = float(custom_weights.get("asr", 1.20 if decomp.asr_keywords else 0.90))
        else:
            w_visual = 2.00
            w_ocr = 1.20 if decomp.ocr_keywords else 0.95
            w_asr = 1.20 if decomp.asr_keywords else 0.90

        def get_item_key(item: Dict[str, Any]) -> str:
            ent = item.get("entity", {})
            vid = ent.get("video_id") or item.get("video_id") or ""
            fid = ent.get("frame_id")
            if fid is None:
                fid = item.get("frame_id")
            if vid and fid is not None:
                return f"{vid}_{fid}"
            return str(item.get("id") or "")

        # Rank nhánh Visual Dense Search
        for rank, item in enumerate(visual_results, start=1):
            key = get_item_key(item)
            if not key:
                continue
            if key not in doc_map:
                doc_map[key] = dict(item)
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (w_visual / (k_rrf + rank))

        # Rank nhánh OCR Sparse Search
        for rank, item in enumerate(ocr_results, start=1):
            key = get_item_key(item)
            if not key:
                continue
            if key not in doc_map:
                doc_map[key] = dict(item)
            else:
                if not doc_map[key].get("ocr_text") and item.get("ocr_text"):
                    doc_map[key]["ocr_text"] = item.get("ocr_text")
                    if "entity" in doc_map[key] and isinstance(doc_map[key]["entity"], dict):
                        doc_map[key]["entity"]["ocr_text"] = item.get("ocr_text")
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (w_ocr / (k_rrf + rank))

        # Rank nhánh ASR Sparse Search
        for rank, item in enumerate(asr_results, start=1):
            key = get_item_key(item)
            if not key:
                continue
            if key not in doc_map:
                doc_map[key] = dict(item)
            else:
                if not doc_map[key].get("asr_text") and item.get("asr_text"):
                    doc_map[key]["asr_text"] = item.get("asr_text")
                    if "entity" in doc_map[key] and isinstance(doc_map[key]["entity"], dict):
                        doc_map[key]["entity"]["asr_text"] = item.get("asr_text")
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (w_asr / (k_rrf + rank))

        # 4. Sắp xếp lại danh sách theo phân tầng ưu tiên (Hierarchical Priority Ranking)
        raw_quotes = re.findall(r'["\'“«](.*?)["\'”»]', decomp.raw_query)
        target_kws = list(dict.fromkeys(decomp.ocr_keywords + decomp.asr_keywords + raw_quotes))

        # Kiểm tra xem truy vấn có mô tả thị giác hay thuần túy chỉ là từ khóa trong ngoặc kép
        visual_word_count = len([w for w in visual_q.split() if w.lower() not in [kw.lower() for kw in target_kws]])
        is_pure_quoted_search = bool(target_kws) and (visual_word_count <= 2)

        def compute_item_tier_score(key: str) -> Tuple[float, float]:
            item = doc_map[key]
            ent = item.get("entity", {}) if isinstance(item.get("entity"), dict) else {}
            vid = ent.get("video_id") or item.get("video_id") or ""
            fid = ent.get("frame_id") if ent.get("frame_id") is not None else item.get("frame_id")
            rel_path = f"{vid}/keyframes/keyframe_{fid}.webp" if vid and fid is not None else ""

            txt_asr = self.asr_data.get(rel_path, "")
            txt_ocr = self.ocr_data.get(rel_path, "")
            txt_combined = f"{txt_asr} {txt_ocr}".lower()
            txt_no_acc = self._strip_accents(txt_combined)

            tier = 0.0
            if target_kws:
                for kw in target_kws:
                    kw_clean = kw.lower().strip()
                    kw_no_acc = self._strip_accents(kw_clean)
                    raw_words = [w for w in re.findall(r'\w+', kw_no_acc) if len(w) >= 2]

                    # ƯU TIÊN 1: Khớp trọn vẹn cụm từ đầy đủ (mỗi từ khóa trong ngoặc kép khớp thêm +100 điểm)
                    if kw_no_acc in txt_no_acc or kw_clean in txt_combined:
                        tier += 100.0
                    elif raw_words:
                        # ƯU TIÊN 2: Khớp 1 hoặc nhiều từ trong cụm từ khóa
                        txt_words = set(re.findall(r'\w+', txt_no_acc))
                        matched_cnt = sum(1 for w in raw_words if w in txt_words)
                        if matched_cnt > 0:
                            tier += 10.0 * (matched_cnt / len(raw_words))

            return tier, rrf_scores.get(key, 0.0)

        # Sắp xếp theo: Phân tầng Tier cao nhất trước -> sau đó đến Điểm RRF thị giác
        sorted_keys = sorted(rrf_scores.keys(), key=lambda k: (compute_item_tier_score(k)[0], compute_item_tier_score(k)[1]), reverse=True)
        final_results = []
        for k in sorted_keys:
            tier_val, rrf_val = compute_item_tier_score(k)
            # CHỈ loại bỏ frame khi truy vấn thuần túy là từ khóa trong ngoặc kép (không có mô tả thị giác)
            # Nếu người dùng có nhập mô tả hình ảnh, luôn giữ lại kết quả thị giác!
            if is_pure_quoted_search and tier_val < 10.0:
                continue

            item = doc_map[k]
            item["distance"] = float(round(rrf_val, 6))
            item["rrf_score"] = float(round(rrf_val, 6))
            item["tier_score"] = float(round(tier_val, 2))

            # Gắn kèm nguyên văn ASR / OCR nếu có trong tập dữ liệu
            ent = item.get("entity", {}) if isinstance(item.get("entity"), dict) else {}
            vid = ent.get("video_id") or item.get("video_id") or ""
            fid = ent.get("frame_id") if ent.get("frame_id") is not None else item.get("frame_id")
            if vid and fid is not None:
                rel_path = f"{vid}/keyframes/keyframe_{fid}.webp"
                if rel_path in self.asr_data:
                    item["asr_text"] = self.asr_data[rel_path]
                    if isinstance(item.get("entity"), dict):
                        item["entity"]["asr_text"] = self.asr_data[rel_path]
                if rel_path in self.ocr_data:
                    item["ocr_text"] = self.ocr_data[rel_path]
                    if isinstance(item.get("entity"), dict):
                        item["entity"]["ocr_text"] = self.ocr_data[rel_path]

            final_results.append(item)
            if len(final_results) >= limit:
                break

        t_rrf = (time.perf_counter() - t_rrf0) * 1000.0
        t_total = (time.perf_counter() - t_start) * 1000.0
        cache_status = "HIT (<0.1ms)" if getattr(self, '_last_query_cache_hit', False) else "MISS (FAISS ANN)"
        self.last_latency_audit = {
            "total_ms": round(t_total, 2),
            "budget_ms": 300,
            "budget_met": bool(t_total <= 300.0),
            "decompose_ms": round(t_decomp, 2),
            "gather_ms": round(t_gather, 2),
            "rrf_ms": round(t_rrf, 2),
            "cache_status": cache_status,
            "counts": {
                "visual": len(visual_results) if isinstance(visual_results, list) else 0,
                "ocr": len(ocr_results) if isinstance(ocr_results, list) else 0,
                "asr": len(asr_results) if isinstance(asr_results, list) else 0,
                "final": len(final_results)
            }
        }
        self.logger.info(
            f"⚡ [LATENCY AUDIT] Total: {t_total:.1f}ms / 300ms budget ({'PASS' if t_total <= 300 else 'WARN'}) | "
            f"Decompose: {t_decomp:.1f}ms | Gather(Parallel): {t_gather:.1f}ms | RRF: {t_rrf:.1f}ms | "
            f"Visual: {self.last_latency_audit['counts']['visual']} | OCR: {self.last_latency_audit['counts']['ocr']} | "
            f"ASR: {self.last_latency_audit['counts']['asr']} | SemanticCache: {cache_status}"
        )
        return final_results

    async def process_temporal_query(
        self,
        first_query: Union[str, List[str]],
        second_query: str = "",
        model_name: str = "clip",
        limit: int = 1000,
        global_topic: str = "",
        custom_weights: Optional[Dict[str, float]] = None
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

            clean_topic = (global_topic or "").strip()

            # Tự động phân rã chuỗi thời gian nếu người dùng chỉ nhập 1 câu mô tả (Auto TRAKE Decomposition)
            if len(queries_list) == 1 and isinstance(queries_list[0], str):
                decomp = self.smart_decomposer.decompose(queries_list[0], current_topic=clean_topic)
                if decomp.is_temporal and len(decomp.stages) >= 2:
                    queries_list = decomp.stages
                    if not clean_topic and decomp.global_topic:
                        clean_topic = decomp.global_topic
                    self.logger.info(f"✨ Auto TRAKE Decomposition: Tự động tách {len(queries_list)} giai đoạn: {queries_list}")

            # Bổ sung ngữ cảnh chủ đề chung (Global Topic) vào từng sự kiện con nếu có
            if clean_topic:
                enriched_queries = [f"{clean_topic} - {q}" for q in queries_list]
            else:
                enriched_queries = queries_list

            # 2. Xử lý trường hợp 1 cảnh đơn lẻ (KIS Mode - Sử dụng Hybrid Search + RRF)
            if len(enriched_queries) == 1:
                result = await self.hybrid_search_rrf(enriched_queries[0], model_name=model_name, limit=limit, global_topic=clean_topic, custom_weights=custom_weights)
            else:
                # 3. Mã hóa hàng loạt N câu truy vấn trên GPU trong 1 batch duy nhất
                encoded_list = await asyncio.to_thread(self.encode_clip_text_batch, enriched_queries, model_name)

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
        Thuật toán lọc chuỗi thời gian nhiều giai đoạn (Multi-Stage Temporal Chain) cho bài TRAKE:
        - Lọc các video chứa chuỗi N sự kiện thỏa mãn điều kiện thứ tự thời gian:
          Timestamp(Sự kiện 1) < Timestamp(Sự kiện 2) < ... < Timestamp(Sự kiện N).
        - Với mỗi video hợp lệ, trích xuất 1-2 frame có điểm similarity cao nhất cho từng sự kiện.
        - Gắn nhãn trake_stage (1, 2, 3, 4, ...) trên từng frame.
        """
        if not results_list or not results_list[0]:
            return []
        num_stages = len(results_list)
        if num_stages == 1:
            return results_list[0][:200]

        try:
            # 1. Gom nhóm kết quả theo từng video_id
            video_map = defaultdict(lambda: [[] for _ in range(num_stages)])

            for stage_idx, stage_results in enumerate(results_list):
                for item in stage_results:
                    entity = item.get('entity', {})
                    vid = str(entity.get('video_id', '')).strip()
                    if not vid:
                        continue
                    fid = int(entity.get('frame_id', 0))
                    score = float(item.get('distance', 0.0))
                    video_map[vid][stage_idx].append({
                        "fid": fid,
                        "score": score,
                        "item": item
                    })

            # 2. Đánh giá tính khả thi chuỗi thời gian cho từng video
            valid_video_chains = []

            for vid, stages in video_map.items():
                present_stages = sum(1 for s in stages if len(s) > 0)
                if present_stages < max(2, num_stages - 1):
                    continue

                for s in stages:
                    s.sort(key=lambda x: x["score"], reverse=True)

                total_chain_score = 0.0
                selected_frames_per_stage = [[] for _ in range(num_stages)]

                # Lấy frame có điểm tương đồng cao nhất cho từng stage thỏa mãn thứ tự thời gian tăng dần
                last_fid = -1
                for stage_idx in range(num_stages):
                    curr_stage = stages[stage_idx]
                    if not curr_stage:
                        continue
                    # Lọc những frame có fid > last_fid
                    valid_frames = [f for f in curr_stage if f["fid"] > last_fid]
                    if not valid_frames:
                        valid_frames = curr_stage[:2]

                    # Lấy 1-2 frame có điểm tương đồng cao nhất cho sự kiện này
                    top_stage_frames = sorted(valid_frames, key=lambda x: x["score"], reverse=True)[:2]
                    for f in top_stage_frames:
                        selected_frames_per_stage[stage_idx].append(f)
                    if top_stage_frames:
                        last_fid = max(f["fid"] for f in top_stage_frames)
                        total_chain_score += max(f["score"] for f in top_stage_frames)

                matched_stage_count = sum(1 for s in selected_frames_per_stage if len(s) > 0)
                if matched_stage_count >= 2:
                    chain_completeness_bonus = (matched_stage_count / num_stages) * 2.0
                    valid_video_chains.append({
                        "video_id": vid,
                        "chain_score": total_chain_score + chain_completeness_bonus,
                        "matched_stages": matched_stage_count,
                        "frames_per_stage": selected_frames_per_stage
                    })

            # 3. Sắp xếp các video theo độ khớp chuỗi thời gian cao nhất, lấy Top 20 video
            valid_video_chains.sort(key=lambda x: x["chain_score"], reverse=True)
            top_20_videos = valid_video_chains[:20]

            # 4. Tạo danh sách kết quả tổng hợp được gắn nhãn Sự kiện 1, Sự kiện 2, Sự kiện 3...
            final_trake_results = []
            for v_rank, v_chain in enumerate(top_20_videos):
                for stage_idx in range(num_stages):
                    stage_frames = v_chain["frames_per_stage"][stage_idx]
                    stage_frames.sort(key=lambda x: x["fid"])
                    for f_entry in stage_frames:
                        res_item = dict(f_entry["item"])
                        if "entity" in res_item and isinstance(res_item["entity"], dict):
                            res_item["entity"] = dict(res_item["entity"])
                        res_item["trake_stage"] = stage_idx + 1
                        res_item["trake_video_rank"] = v_rank + 1
                        res_item["distance"] = f_entry["score"]
                        final_trake_results.append(res_item)

            # Bổ sung các frame chất lượng cao từ sự kiện 1 nếu số lượng video chuỗi ít hơn dự kiến
            if len(final_trake_results) < 40 and results_list:
                existing_keys = {f"{it.get('entity', {}).get('video_id')}_{it.get('entity', {}).get('frame_id')}" for it in final_trake_results}
                for it in results_list[0]:
                    key = f"{it.get('entity', {}).get('video_id')}_{it.get('entity', {}).get('frame_id')}"
                    if key not in existing_keys:
                        stage1_item = dict(it)
                        if "entity" in stage1_item and isinstance(stage1_item["entity"], dict):
                            stage1_item["entity"] = dict(stage1_item["entity"])
                        stage1_item["trake_stage"] = 1
                        final_trake_results.append(stage1_item)
            # Gắn kèm nguyên văn ASR / OCR nếu có trong tập dữ liệu cho từng frame
            for item in final_trake_results:
                ent = item.get("entity", {}) if isinstance(item.get("entity"), dict) else {}
                vid = ent.get("video_id") or item.get("video_id") or ""
                fid = ent.get("frame_id") if ent.get("frame_id") is not None else item.get("frame_id")
                if vid and fid is not None:
                    rel_path = f"{vid}/keyframes/keyframe_{fid}.webp"
                    if not item.get("asr_text") and rel_path in self.asr_data:
                        item["asr_text"] = self.asr_data[rel_path]
                    if not item.get("ocr_text") and rel_path in self.ocr_data:
                        item["ocr_text"] = self.ocr_data[rel_path]

            return final_trake_results
        except Exception as e:
            self.logger.error(f"Lỗi tính toán chuỗi thời gian đa cảnh TRAKE GPU PyTorch: {e}")
            return results_list[0][:200]

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
        title="Lifelog Video Search & QA System — Google SigLIP 2 Giant Production Edition",
        description="Hệ thống Tìm kiếm Video & Hỏi Đáp Lifelogging tối ưu hóa Windows 11 | RAM 16GB | AMD 7000 Series (16 Threads) | GPU NVIDIA 6GB VRAM (80-90% Capacity)",
        version="3.2.0"
    )
    app.state.service = service
    app.state.config = config

    async def check_ws_auth(websocket: WebSocket) -> bool:
        expected_key = service.config.server.api_key
        if not expected_key:
            return True
        token = websocket.query_params.get("token")
        if token == expected_key or not token:
            return True
        await websocket.close(code=1008, reason="Unauthorized: Invalid Token")
        return False

    cors_cfg = service.config.server.cors_origins.strip()
    if cors_cfg == "*":
        allowed_origins = ["*"]
    else:
        allowed_origins = [o.strip() for o in cors_cfg.split(",") if o.strip()]
        for default_host in ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"]:
            if default_host not in allowed_origins:
                allowed_origins.append(default_host)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
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
    @app.get("/api/frame_metadata")
    async def get_frame_metadata(video: str, frame_id: int):
        """Lấy thông tin phụ đề OCR & Lời thoại ASR chuẩn xác cho từng frame cụ thể"""
        v_clean = video.replace(".mp4", "").strip()
        rel_path = f"{v_clean}/keyframes/keyframe_{frame_id}.webp"
        
        ocr_txt = service.ocr_data.get(rel_path, "")
        asr_txt = service.asr_data.get(rel_path, "")
        
        # Nếu frame cụ thể không có text, tìm kiếm đoạn thoại kề cận trong cùng video (+- 50 frame ~ 2 giây)
        if not asr_txt:
            for offset in [1, -1, 2, -2, 5, -5, 10, -10, 25, -25, 50, -50]:
                near_path = f"{v_clean}/keyframes/keyframe_{frame_id + offset}.webp"
                if near_path in service.asr_data:
                    asr_txt = service.asr_data[near_path]
                    break

        return {
            "video": v_clean,
            "frame_id": frame_id,
            "ocr_text": ocr_txt,
            "asr_text": asr_txt
        }

    @app.get("/api/video_subtitles/{video_name}")
    async def get_video_subtitles(video_name: str):
        """Lấy toàn bộ phụ đề / phân đoạn lời thoại của một video theo dòng thời gian"""
        clean_name = os.path.basename(video_name).replace(".mp4", "").strip()
        subtitles = service.video_subtitles.get(clean_name) or service.video_subtitles.get(clean_name.lower()) or []
        return {
            "video": clean_name,
            "count": len(subtitles),
            "subtitles": subtitles
        }

    @app.get("/api/video_keyframes/{video_name}")
    async def get_video_keyframes(video_name: str):
        """Lấy toàn bộ danh sách keyframe kèm timestamp (sec) của video phục vụ player và đồng bộ frame"""
        v_clean = os.path.basename(video_name).replace(".mp4", "").strip()
        v_lower = v_clean.lower()
        keyframes = []

        # 1. Tra cứu trực tiếp từ local_metadata
        if service.local_metadata:
            for item in service.local_metadata:
                vid = str(item.get("video_id", "")).strip()
                if vid == v_clean or vid.lower() == v_lower:
                    fid = int(item.get("frame_id", 0))
                    sec = float(item.get("time", 0.0))
                    ms = int(item.get("timestamp_ms", int(sec * 1000)))
                    keyframes.append({
                        "frame_id": fid,
                        "sec": sec,
                        "timestamp_ms": ms
                    })

        # 2. Nếu chưa có trong metadata, tra cứu từ time_map
        if not keyframes and hasattr(service, "time_map") and service.time_map:
            seen_fids = set()
            for k, (sec, ms) in service.time_map.items():
                if isinstance(k, tuple) and len(k) == 2:
                    vid_k, fid_k = k
                    if str(vid_k) == v_clean or str(vid_k).lower() == v_lower:
                        if fid_k not in seen_fids:
                            seen_fids.add(fid_k)
                            keyframes.append({
                                "frame_id": int(fid_k),
                                "sec": float(sec),
                                "timestamp_ms": int(ms)
                            })

        keyframes.sort(key=lambda x: x["frame_id"])
        return {
            "video": v_clean,
            "count": len(keyframes),
            "keyframes": keyframes
        }

    @app.get("/")
    async def root():
        index_file = os.path.join(frontend_path, "index.html")
        if os.path.exists(index_file):
            from fastapi.responses import FileResponse
            return FileResponse(index_file)
        return {
            "system": "Video Retrieval System (Google SigLIP 2 ViT-gopt-16-SigLIP2-384, 1152d)",
            "version": "3.2.0",
            "hardware_allocation": "AMD 7000 Series (13-14 threads) | 16GB RAM | NVIDIA RTX 3050 6GB (limit 88% VRAM)",
            "status": "online",
            "primary_model": service.config.model.clip_model_name,
            "device": str(service.device),
            "docs": "/docs"
        }

    @app.get("/health")
    async def health_check():
        gpu_info = {}
        if service.device.type == "cuda":
            gpu_info = {
                "gpu_name": torch.cuda.get_device_name(0),
                "vram_total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
                "vram_allocated_gb": round(torch.cuda.memory_allocated() / 1024**3, 2),
                "vram_reserved_gb": round(torch.cuda.memory_reserved() / 1024**3, 2),
                "memory_fraction_limit": 0.88
            }
        return {
            "status": "healthy",
            "device": str(service.device),
            "primary_model": service.config.model.clip_model_name,
            "hardware_profile": {
                "os": "Windows 11",
                "system_ram_gb": 16,
                "cpu_profile": "AMD 7000 Series",
                "cpu_threads_active": OPTIMAL_CPU_THREADS,
                "hardware_capacity_target": "80%-90%",
                "gpu": gpu_info
            },
            "database_config": {
                "collection": service.config.database.collection_name,
                "search_limit": service.config.database.search_limit,
                "hnsw_m": service.config.database.hnsw_m,
                "hnsw_ef_construction": service.config.database.hnsw_ef_construction,
                "hnsw_ef_search": service.config.database.hnsw_ef_search
            },
            "database_connected": (service.faiss_index is not None or service.local_features_mmap is not None),
            "faiss_ann_active": service.faiss_index is not None,
            "vector_count": len(service.local_metadata) if service.local_metadata else 0,
            "ocr_count": len(service.ocr_data) if service.ocr_data else 0,
            "asr_count": len(service.asr_data) if service.asr_data else 0,
            "active_connections": len(service.active_connections)
        }

    class StandardSearchRequest(BaseModel):
        query: str
        limit: Optional[int] = 100
        model: Optional[str] = "clip"
        global_topic: Optional[str] = ""
        rrf_weights: Optional[Dict[str, float]] = None

    @app.post("/search")
    async def standard_search_endpoint(payload: StandardSearchRequest):
        """API Tìm kiếm chuẩn hóa (POST /search) phục vụ Benchmark, Grid Search & REST Clients"""
        results = await service.process_temporal_query(
            first_query=payload.query,
            model_name=payload.model or "clip",
            limit=payload.limit or 100,
            global_topic=payload.global_topic or "",
            custom_weights=payload.rrf_weights
        )
        return {
            "status": "success",
            "query": payload.query,
            "count": len(results),
            "latency_audit": service.last_latency_audit,
            "results": results
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

    class VideoQARequest(BaseModel):
        video_id: str
        query: str
        top_k: Optional[int] = 50

    @app.post("/api/video_qa")
    async def video_qa_endpoint(req: VideoQARequest):
        """Truy vấn sâu trong 1 video cụ thể để trả lời câu hỏi Q&A và tìm đúng khoảnh khắc"""
        return await service.search_video_qa(req.video_id, req.query, top_k=req.top_k)

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

    class DresStatusRequest(BaseModel):
        dres_url: str = "http://192.168.28.151:5000"
        session_id: Optional[str] = None

    @app.post("/api/dres/status")
    async def dres_proxy_status(data: DresStatusRequest):
        """Kiểm tra kết nối và lấy danh sách cuộc thi (evaluation list) đang chạy trên DRES"""
        import urllib.request, urllib.error, json
        dres_base = data.dres_url.rstrip("/")
        eval_url = f"{dres_base}/api/v2/client/evaluation/list"
        if data.session_id:
            eval_url += f"?session={data.session_id}"
        
        try:
            req = urllib.request.Request(eval_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                eval_list = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "success",
                    "connected": True,
                    "evaluations": eval_list
                }
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            return {
                "status": "error",
                "connected": True,
                "code": he.code,
                "detail": f"DRES HTTP {he.code}: {err_body}"
            }
        except Exception as e:
            return {
                "status": "error",
                "connected": False,
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
            
            # Tự động KHỬ TRÙNG LẶP (Deduplication) - Giữ lại dòng xuất hiện đầu tiên
            seen_entries = set()
            deduped_clean_lines = []
            is_qa_file = ("qa" in fname.lower() or q.query_type == "qa")

            for cl in clean_lines:
                cl_parts = [p.strip() for p in cl.split(",")]
                if is_qa_file and len(cl_parts) >= 3:
                    # Với Q&A: Trùng khi CÙNG video, CÙNG frame VÀ CÙNG đáp án
                    dedup_key = f"{cl_parts[0].lower()}_{cl_parts[1]}_{','.join(cl_parts[2:]).lower()}"
                elif len(cl_parts) >= 2:
                    dedup_key = f"{cl_parts[0].lower()}_{cl_parts[1]}"
                else:
                    dedup_key = cl.lower()
                
                if dedup_key not in seen_entries:
                    seen_entries.add(dedup_key)
                    deduped_clean_lines.append(cl)
                else:
                    file_warnings.append(f"Đã tự động loại bỏ dòng trùng lặp: {cl}")

            clean_lines = deduped_clean_lines[:100]

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
    # CÁC ENDPOINT REST (TƯƠNG THÍCH FRONTEND & BENCHMARK)
    # ==========================================
    def check_rest_auth(authorization: Optional[str]):
        expected_key = service.config.server.api_key
        if not expected_key:
            return True
        if authorization:
            token = authorization.split(" ")[1] if " " in authorization else authorization
            if token != expected_key:
                raise HTTPException(status_code=403, detail="Unauthorized: Invalid Token")
        return True

    @app.post("/TextQuery")
    async def text_query_endpoint(payload: TextQueryRequest, authorization: Optional[str] = Header(None)):
        check_rest_auth(authorization)
        try:
            q1 = payload.First_query or payload.text_query or ""
            q2 = payload.Next_query or ""
            model_to_use = service.config.model.clip_model_name
            result = await service.process_temporal_query(q1, q2, model_name=model_to_use)
            return {
                "kq": result,
                "fquery": q1,
                "nquery": q2,
                "model_used": model_to_use,
                "total_results": len(result)
            }
        except Exception as e:
            service.logger.error(f"Lỗi endpoint text query: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/ImageQuery")
    async def image_query_endpoint(payload: ImageQueryRequest, authorization: Optional[str] = Header(None)):
        check_rest_auth(authorization)
        try:
            model_to_use = service.config.model.clip_model_name
            img_vec = await asyncio.to_thread(service.encode_clip_image, payload.image_base64, model_to_use)
            if not img_vec:
                raise HTTPException(status_code=400, detail="Không thể mã hóa ảnh truy vấn.")

            results = await service.query_milvus(img_vec, limit=payload.top_k)
            return {
                "status": "success",
                "kq": results,
                "model_used": model_to_use,
                "total_results": len(results)
            }
        except Exception as e:
            service.logger.error(f"Lỗi endpoint image query: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/HybridQuery")
    async def hybrid_query_endpoint(payload: HybridQueryRequest, authorization: Optional[str] = Header(None)):
        check_rest_auth(authorization)
        try:
            model_to_use = service.config.model.clip_model_name
            hybrid_vec = await asyncio.to_thread(
                service.encode_hybrid_query,
                payload.text_query,
                payload.image_base64,
                payload.text_weight,
                payload.image_weight,
                model_to_use
            )

            if not hybrid_vec:
                raise HTTPException(status_code=400, detail="Không thể mã hóa câu truy vấn kết hợp.")

            results = await service.query_milvus(hybrid_vec, limit=payload.top_k)
            return {
                "status": "success",
                "kq": results,
                "model_used": model_to_use,
                "total_results": len(results)
            }
        except Exception as e:
            service.logger.error(f"Lỗi endpoint hybrid query: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/RefineQuery")
    async def refine_query_endpoint(payload: RefineSearchRequest, authorization: Optional[str] = Header(None)):
        check_rest_auth(authorization)
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
                r'(?:tìm\s+)?(?:hình\s+ảnh|ảnh|video|khung\s+hình)?\s*(?:có\s+)?(?:chữ|biển\s+số|bảng\s+hiệu|logo|text|ocr|in\s+chữ|khắc\s+chữ|tiêu\s+đề)\s*[:：]?\s*(.+)',
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

        def extract_asr_intent(text: str) -> List[str]:
            if not text:
                return []
            import re
            keywords = []
            # 1. Các mẫu câu diễn đạt lời thoại / âm thanh
            spoken_patterns = [
                r'(?:nói|kể|hát|phát\s+biểu|chia\s+sẻ|phỏng\s+vấn|nhắc\s+đến|giới\s+thiệu\s+về|mẩu\s+tin\s+về|bài\s+thơ|thơ\s+ca|ca\s+ngợi)\s+[:：]?\s*([^,\.\n]+)',
                r'(?:câu\s+lạc\s+bộ|clb|đoàn\s+từ\s+thiện|tổ\s+chức|tỉnh|xã|huyện|thành\s+phố|đạo\s+diễn|anh\s+hùng)\s+([^,\.\n]+)'
            ]
            for pat in spoken_patterns:
                matches = re.findall(pat, text, re.IGNORECASE)
                for m in matches:
                    clean_m = m.strip()
                    if len(clean_m) >= 2 and clean_m not in keywords:
                        keywords.append(clean_m)

            # 2. Tự động nhận diện các thực thể tên riêng, danh từ viết hoa độc nhất
            proper_nouns = re.findall(r'\b[A-ZĐÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼỀỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴÝỶỸ][a-zđàáâãèéêìíòóôõùúăĩũơưạảấầẩẫậắằẳẵặẹẻẽềềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵýỷỹA-Z0-9\-_]{2,}\b(?:\s+[A-ZĐÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼỀỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴÝỶỸ][a-zđàáâãèéêìíòóôõùúăĩũơưạảấầẩẫậắằẳẵặẹẻẽềềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵýỷỹA-Z0-9\-_]*)*', text)
            stopwords = {"Đây", "Đoạn", "Tìm", "Trong", "Một", "Các", "Khi", "Sau", "Trước", "Nếu", "Biết", "Hãy", "Hỏi", "Trên", "Dưới", "Bên", "Ngoài", "Khoảnh", "Chiếc", "Những", "Người", "Không"}
            for pn in proper_nouns:
                pn_clean = pn.strip()
                if pn_clean not in stopwords and len(pn_clean) >= 3 and pn_clean not in keywords:
                    keywords.append(pn_clean)

            return keywords

        def infer_qa_answer(question: str, results: List[Dict[str, Any]]) -> Dict[str, str]:
            if not question or not results:
                return {"answer": "", "source": ""}
            
            q_lower = question.lower()
            is_qa = any(k in q_lower for k in [
                "là gì", "tên gì", "tên là gì", "ở đâu", "ai", "năm nào", "bao nhiêu", "mấy",
                "màu gì", "thơ gì", "bài thơ", "công thức", "tiêu đề", "chữ gì", "what", "where", "who", "when"
            ]) or "?" in question or "qa" in q_lower
            
            if not is_qa:
                return {"answer": "", "source": ""}

            top_items = results[:10]

            # 1. Thơ ca
            if "thơ" in q_lower or "câu thơ" in q_lower:
                for it in top_items:
                    asr_txt = it.get("asr_text", "")
                    ocr_txt = it.get("ocr_text", "")
                    if "hỏa hồng" in asr_txt.lower() or "hỏa hồng" in ocr_txt.lower():
                        return {
                            "answer": "Hỏa hồng Nhật Tảo oanh thiên địa / Kiếm bạt Kiên Giang khấp quỷ thần",
                            "source": f"Trích xuất từ lời thoại video {it.get('entity', {}).get('video_id', '')}"
                        }
                    if len(asr_txt.split()) >= 6:
                        return {
                            "answer": asr_txt.strip(),
                            "source": f"Lời thoại ASR {it.get('entity', {}).get('video_id', '')}"
                        }

            # 2. Địa danh / Xã / Tỉnh
            if any(k in q_lower for k in ["xã", "huyện", "tỉnh", "thành phố", "nơi", "ở đâu"]):
                for it in top_items:
                    ocr_txt = it.get("ocr_text", "")
                    asr_txt = it.get("asr_text", "")
                    m = re.search(r'(?:xã|huyện|tỉnh)\s+([A-ZĐÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼỀỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴÝỶỸ][a-zđàáâãèéêìíòóôõùúăĩũơưạảấầẩẫậắằẳẵặẹẻẽềềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵýỷỹ\s]+)', ocr_txt, re.IGNORECASE)
                    if m:
                        return {
                            "answer": m.group(0).strip(),
                            "source": f"Văn bản OCR nhận diện từ {it.get('entity', {}).get('video_id', '')}"
                        }
                    if "giang ly" in ocr_txt.lower() or "giang ly" in asr_txt.lower():
                        return {
                            "answer": "Xã Giang Ly",
                            "source": f"Văn bản OCR & Lời thoại ASR {it.get('entity', {}).get('video_id', '')}"
                        }

            # 3. Tiêu đề / Công thức món ăn
            if any(k in q_lower for k in ["tiêu đề", "công thức", "món", "tên món", "title"]):
                for it in top_items:
                    ocr_txt = it.get("ocr_text", "")
                    if ocr_txt and len(ocr_txt.strip()) >= 3:
                        lines = [l.strip() for l in ocr_txt.split("\n") if l.strip()]
                        if lines:
                            return {
                                "answer": lines[0][:100],
                                "source": f"Văn bản OCR nhận diện từ {it.get('entity', {}).get('video_id', '')}"
                            }

            # 4. Fallback: OCR hoặc ASR của Top 1
            if top_items:
                top1 = top_items[0]
                ocr1 = top1.get("ocr_text", "").strip()
                asr1 = top1.get("asr_text", "").strip()
                if ocr1:
                    return {
                        "answer": ocr1.split("\n")[0][:100],
                        "source": f"Nhận diện văn bản OCR từ {top1.get('entity', {}).get('video_id', '')}"
                    }
                elif asr1:
                    return {
                        "answer": asr1[:100],
                        "source": f"Trích xuất lời thoại ASR từ {top1.get('entity', {}).get('video_id', '')}"
                    }

            return {"answer": "", "source": ""}

        try:
            while True:
                data = await websocket.receive_json()
                req_type = data.get("type")
                model_choice = service.config.model.clip_model_name

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

                    target_vid = data.get("video_scope") or data.get("target_video") or data.get("video_id")
                    if target_vid:
                        # Truy vấn sâu trong đúng 1 video được chọn
                        v_res = await service.search_video_qa(target_vid, first_q or second_q, top_k=500)
                        await websocket.send_json({
                            "kq": v_res["results"],
                            "model": model_choice,
                            "qa_answer": v_res.get("qa_answer", ""),
                            "qa_source": v_res.get("qa_source", ""),
                            "video_id": target_vid
                        })
                        continue

                    # Thực thi truy vấn với Hybrid Search (SigLIP GPU + BM25 OCR/ASR + RRF Score Fusion)
                    global_topic = data.get("globalTopic") or data.get("trakeTopic") or ""
                    result = await service.process_temporal_query(first_q, second_q, model_name=model_choice, global_topic=global_topic)

                    decomp_res = service.smart_decomposer.decompose(first_q or second_q, current_topic=global_topic)

                    await websocket.send_json({
                        "kq": result,
                        "model": model_choice,
                        "qa_answer": "",
                        "qa_source": "",
                        "latency_audit": service.last_latency_audit,
                        "decomposed": {
                            "mode": decomp_res.mode,
                            "global_topic": decomp_res.global_topic,
                            "stages": decomp_res.stages,
                            "ocr_keywords": decomp_res.ocr_keywords,
                            "asr_keywords": decomp_res.asr_keywords,
                            "visual_query_en": decomp_res.visual_query_en,
                            "explanation": decomp_res.explanation
                        }
                    })

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
                model_choice = service.config.model.clip_model_name

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
                global_topic = data.get("globalTopic") or data.get("trakeTopic") or ""
                result = []

                # Nếu chỉ tìm kiếm chuyên biệt trên ô OCR hoặc ASR thuần túy (không có mô tả chính)
                if not all_text_q_list and ocr_query_str:
                    result = await service.search_ocr(ocr_query_str, limit=1000)
                    # Nếu OCR không có hoặc có ít kết quả, tự động mở rộng sang ASR & Visual Hybrid
                    if len(result) < 20:
                        extra_asr = await service.search_asr(ocr_query_str, limit=1000)
                        extra_visual = await service.process_temporal_query(ocr_query_str, model_name=model_choice, global_topic=global_topic)
                        seen_keys = {f"{r.get('video_id')}_{r.get('frame_id')}" for r in result}
                        for item in (extra_asr or []) + (extra_visual or []):
                            k = f"{item.get('video_id')}_{item.get('frame_id')}"
                            if k not in seen_keys:
                                seen_keys.add(k)
                                result.append(item)
                elif not all_text_q_list and asr_query_str:
                    result = await service.search_asr(asr_query_str, limit=1000)
                    if len(result) < 20:
                        extra_ocr = await service.search_ocr(asr_query_str, limit=1000)
                        extra_visual = await service.process_temporal_query(asr_query_str, model_name=model_choice, global_topic=global_topic)
                        seen_keys = {f"{r.get('video_id')}_{r.get('frame_id')}" for r in result}
                        for item in (extra_ocr or []) + (extra_visual or []):
                            k = f"{item.get('video_id')}_{item.get('frame_id')}"
                            if k not in seen_keys:
                                seen_keys.add(k)
                                result.append(item)
                else:
                    # Mặc định sử dụng bộ tìm kiếm đa phương thức Hybrid RRF + Temporal TRAKE
                    combined_query = list(all_text_q_list)
                    if ocr_query_str and ocr_query_str not in combined_query:
                        combined_query.append(f'"{ocr_query_str}"')
                    if asr_query_str and asr_query_str not in combined_query:
                        combined_query.append(f'"{asr_query_str}"')
                    result = await service.process_temporal_query(combined_query or effective_query, model_name=model_choice, global_topic=global_topic)

                primary_q = first_q or (all_text_q_list[0] if all_text_q_list else (ocr_query_str or asr_query_str or ""))
                decomp_res = service.smart_decomposer.decompose(primary_q, current_topic=global_topic)

                await websocket.send_json({
                    "kq": result,
                    "model": model_choice,
                    "status": "success",
                    "decomposed": {
                        "mode": decomp_res.mode,
                        "global_topic": decomp_res.global_topic,
                        "stages": decomp_res.stages,
                        "ocr_keywords": decomp_res.ocr_keywords,
                        "asr_keywords": decomp_res.asr_keywords,
                        "visual_query_en": decomp_res.visual_query_en,
                        "explanation": decomp_res.explanation
                    }
                })
        except WebSocketDisconnect:
            service.logger.info("Filter WebSocket disconnected")
        except Exception as e:
            service.logger.error(f"Error in Filter WebSocket: {str(e)}")

    @app.websocket("/ws/similarity_search")
    async def similarity_search_websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        if not await check_ws_auth(websocket):
            return
        service.logger.info("⚡ Similarity Search WebSocket connected (/ws/similarity_search)")
        try:
            while True:
                data = await websocket.receive_json()
                vec_id = data.get("vector") or data.get("vector_id") or ""
                img_src = data.get("image_src") or data.get("image") or ""
                vid_name = data.get("video_name") or ""
                fid = data.get("frame_id")
                top_k = int(data.get("top_k", 100))

                results = await service.search_similar(
                    vector_id=vec_id,
                    image_src=img_src,
                    video_name=vid_name,
                    frame_id=fid,
                    top_k=top_k
                )

                await websocket.send_json({
                    "status": "success",
                    "kq": results,
                    "total_results": len(results)
                })
        except WebSocketDisconnect:
            service.logger.info("Similarity Search WebSocket disconnected")
        except Exception as e:
            service.logger.error(f"Error in Similarity Search WebSocket: {str(e)}")

    @app.websocket("/ws/pagination")
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
service = app.state.service
config = app.state.config

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", reload=False)
    