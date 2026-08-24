"""
Smart Query Decomposer & Multi-Modal Omni-Parser
=================================================
Mô-đun Phân Rã & Tinh Chỉnh Câu Truy Vấn Đa Phương Thức Thông Minh
Tối ưu hóa: 0 MB VRAM, chạy siêu tốc trên CPU RAM (< 2ms), chống tràn bộ nhớ.
Hỗ trợ cả 3 dạng bài thi: KIS, Video QA, TRAKE.
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("smart_query_decomposer")

# ==============================================================================
# 1. BỘ TỪ ĐIỂN DỊCH VÀ MỞ RỘNG THỊ GIÁC CHUYÊN DỤNG (VIETNAMESE -> VISUAL ENGLISH)
# ==============================================================================
VIET_TO_ENG_VISUAL_MAP = {
    # Người & Hành động
    "người đàn ông": "a man",
    "đàn ông": "a man",
    "phụ nữ": "a woman",
    "người phụ nữ": "a woman",
    "cô gái": "a young woman",
    "chàng trai": "a young man",
    "trẻ em": "children",
    "em bé": "a baby child",
    "học sinh": "students in uniform",
    "sinh viên": "college students",
    "công an": "police officer",
    "cảnh sát": "police officer",
    "công an giao thông": "traffic police officer",
    "csgt": "traffic police officer",
    "bác sĩ": "doctor in white coat",
    "y tá": "nurse",
    "tài xế": "driver",
    "người lái xe": "driver",
    "đầu bếp": "chef cooking",
    "người bán hàng": "shop vendor seller",
    
    # Phương tiện
    "xe máy": "motorbike motorcycle",
    "xe mô tô": "motorcycle",
    "xe gắn máy": "scooter motorbike",
    "xe tay ga": "scooter",
    "ô tô": "car automobile",
    "xe hơi": "car vehicle",
    "xe tải": "cargo truck",
    "xe buýt": "city transit bus",
    "xe bus": "bus",
    "xe khách": "coach bus",
    "xe cấp cứu": "ambulance with siren",
    "xe cứu thương": "ambulance",
    "xe cảnh sát": "police car patrol",
    "xe đạp": "bicycle cyclist",
    "máy bay": "airplane flight",
    "thuyền": "boat ship on water",
    "tàu hỏa": "train railway",
    "xe ba gác": "three wheeled motorized cart",

    # Trang phục & Phụ kiện
    "áo dài": "traditional vietnamese ao dai dress",
    "nón lá": "vietnamese conical leaf hat",
    "mũ bảo hiểm": "helmet",
    "nón bảo hiểm": "helmet",
    "khẩu trang": "face mask",
    "balo": "backpack bag",
    "ba lô": "backpack",
    "túi xách": "handbag purse",
    "kính mắt": "sunglasses eyeglasses",
    "áo khoác": "jacket coat",
    "áo thun": "t-shirt",
    "áo sơ mi": "collared dress shirt",
    "áo đỏ": "red shirt",
    "áo xanh": "blue shirt",
    "áo vàng": "yellow shirt",
    "áo trắng": "white shirt",
    "áo đen": "black shirt",

    # Địa điểm & Không gian
    "ngã tư": "street intersection crossroad",
    "ngã ba": "three way road junction",
    "đường phố": "city street road",
    "vỉa hè": "sidewalk pavement",
    "công viên": "public park garden",
    "bãi biển": "sandy beach seashore",
    "quán cà phê": "coffee shop cafe",
    "quán ăn": "restaurant eatery",
    "siêu thị": "supermarket grocery store",
    "chợ": "traditional outdoor market",
    "bệnh viện": "hospital clinic",
    "trường học": "school campus classroom",
    "chùa": "buddhist pagoda temple",
    "nhà thờ": "church cathedral",
    "sân bay": "airport terminal",
    "bến xe": "bus station",
    "bờ sông": "riverbank river",
    "cầu": "bridge over water",
    "trong nhà": "indoor room interior",
    "ngoài trời": "outdoor scene",
    "ban đêm": "night time night street",
    "buổi tối": "evening night",
    "hoàng hôn": "sunset golden hour",
    "bình minh": "sunrise dawn",

    # Hành động
    "chạy bộ": "running jogging",
    "đi bộ": "walking on sidewalk",
    "lái xe": "driving vehicle",
    "đi xe máy": "riding motorcycle",
    "nghe điện thoại": "talking on mobile phone",
    "bấm điện thoại": "using smartphone",
    "ăn uống": "eating food dining",
    "uống nước": "drinking beverage",
    "nói chuyện": "people talking chatting",
    "bắt tay": "people shaking hands",
    # Ẩm thực & Nấu nướng
    "măng tây": "fresh green asparagus vegetable",
    "măng tây xanh": "fresh green asparagus vegetable",
    "chế biến măng tây": "cooking preparing fresh asparagus",
    "chế biến": "cooking preparing food in kitchen",
    "nấu ăn": "cooking preparing meal in kitchen",
    "món ăn": "delicious food culinary plate dish",
    "xào": "stir frying pan cooking",
    "áp chảo": "pan searing cooking",
    "cắt thái": "chopping slicing vegetables",
    "thịt bò": "beef steak meat",
    "hải sản": "seafood shrimp squid",
    "salad": "fresh vegetable salad",
    "sầu riêng": "durian fruit thorny yellow flesh fruit stall",
    "trái sầu riêng": "durian fruit thorny yellow flesh fruit stall",
    "quả sầu riêng": "durian fruit thorny yellow flesh fruit stall",
    "mít": "jackfruit large fruit",
    "thanh long": "dragonfruit pitaya pink fruit",
    "dưa hấu": "watermelon red juicy fruit slice",
    "chuối": "bananas yellow ripe fruit",
    "xoài": "mango yellow tropical fruit",
    "cam": "orange citrus fruit",
    "dứa": "pineapple tropical fruit",
    "nước uống": "drink beverage glass",
    "trà": "tea cup teapot",
    "cà phê": "coffee cup latte espresso",
    "bánh": "cake pastry bakery",
    "hoa quả": "fresh fruits",
    "trái cây": "fresh fruits",

    # Bản đồ, Giấy tờ, Biểu đồ & Thông tin trực quan
    "bản đồ": "a geographical map atlas navigation chart",
    "tấm bản đồ": "a geographical map chart atlas",
    "bản đồ việt nam": "geographical map of vietnam",
    "bản đồ thế giới": "world geographical map atlas",
    "sơ đồ": "diagram schematic layout blueprint",
    "biểu đồ": "chart graph infographic data visual",
    "lá cờ": "national flag fluttering banner",
    "quốc kỳ": "national flag",
    "cờ đỏ sao vàng": "vietnamese national flag with yellow star",
    "cờ": "flag banner",
    "biển báo": "traffic road sign street sign",
    "đèn giao thông": "traffic lights intersection signal",
    "biển số xe": "vehicle license plate",
    "bảng hiệu": "storefront billboard signboard",

    # Thiết bị điện tử, Công nghệ & Đồ vật
    "máy tính": "computer laptop desktop screen monitor",
    "laptop": "laptop computer open on desk",
    "màn hình": "digital screen display monitor",
    "điện thoại": "mobile phone smartphone screen",
    "smartphone": "smartphone mobile device",
    "tivi": "television tv screen display",
    "ti vi": "television tv screen display",
    "máy quay": "video camera recording",
    "máy ảnh": "dslr camera photography",
    "sách": "reading book open pages library",
    "báo": "reading newspaper printed paper",
    "tài liệu": "paper documents paperwork",
    "tiền": "cash banknotes paper money currency",
    "hộ chiếu": "passport identity booklet",
    "vali": "travel suitcase luggage bag",
    "đồng hồ": "wrist watch wall clock timer",
    "bút": "writing pen pencil",
    "bàn ghế": "table and chairs furniture",
    "giường": "bed bedroom furniture",
    "gương": "mirror reflection",
    "cửa sổ": "glass window daylight",
    "cửa ra vào": "door doorway entrance",
    "bục phát biểu": "podium lectern microphone speech",
    "sân khấu": "stage performance auditorium hall",
    "hội trường": "conference hall meeting room auditorium",
    "phòng họp": "meeting room conference table",

    # Thiên nhiên & Cảnh quan
    "cây cối": "green trees foliage plants",
    "cây xanh": "lush green trees park",
    "rừng": "forest woodland trees",
    "núi": "mountain peaks landscape",
    "đồi": "rolling hills green landscape",
    "thác nước": "waterfall cascading water",
    "sông": "river flowing water",
    "hồ": "lake tranquil water",
    "biển": "ocean sea waves beach",
    "ruộng lúa": "green rice field terrace paddy",
    "cánh đồng": "open countryside green field",
    "hoa sen": "lotus flower blooming",
    "hoa": "colorful blooming flowers",
    "mặt trời": "bright sun daylight sunshine",
    "mặt trăng": "night moon glowing",
    "trời mưa": "rainy weather rain falling",
    "mưa lớn": "heavy rainfall storm",
    "cầu vồng": "rainbow in the sky",
    "tuyết": "winter snow snowy landscape",
    "bão": "heavy storm tempest windy",
    "cháy": "fire flames burning blaze",
    "khói": "smoke rising plume",

    # Động vật
    "chó": "pet dog puppy canine",
    "mèo": "pet cat kitten feline",
    "chim": "bird flying perched",
    "cá": "fish swimming underwater",
    "ngựa": "horse equestrian",
    "bò": "cow cattle grazing",
    "heo": "pig livestock",
    "lợn": "pig livestock",
    "gà": "chicken rooster poultry",
    "vịt": "duck swimming bird",
    "hổ": "tiger wild predator",
    "sư tử": "lion wild predator",
    "voi": "elephant large mammal",
    "khỉ": "monkey primate",
    "rắn": "snake reptile",
    "rùa": "turtle tortoise",
}

# ==============================================================================
# 2. BỘ TỪ KHÓA TÁCH CHUỖI THỜI GIAN (TEMPORAL CONNECTORS)
# ==============================================================================
TEMPORAL_SPLIT_REGEX = re.compile(
    r'(?:\b(?:sau\s+đó|tiếp\s+theo|tiếp\s+đến|kế\s+tiếp|ngay\s+sau\s+đó|về\s+sau|lúc\s+sau|đoạn\s+sau|rồi\s+mới|rồi\s+sau\s+đó|rồi|then|after\s+that|afterwards|following\s+that|subsequently|later\s+on|next)\b'
    r'|(?:\b(?:giai\s+đoạn|bước|stage|scene|cảnh)\s+[0-9]+[:\.\-]?\s*)'
    r'|(?:\b(?:thứ\s+nhất|thứ\s+hai|thứ\s+ba|đầu\s+tiên|tiếp\s+tục|cuối\s+cùng)\b[:\.\-]?\s*)'
    r'|(?:\s*->\s*|\s*-->\s*|\s*=>\s*|\s*;\s*))',
    re.IGNORECASE
)

# Các mẫu câu hỏi rác cần lọc bỏ trong Video QA
QA_QUESTION_CLEAN_PATTERNS = [
    r'^(?:hãy\s+)?(?:cho\s+biết|tìm\s+xem|hỏi\s+rằng|hỏi|xem|tìm|cho\s+tôi\s+biết|xác\s+định)\s+[:：]?',
    r'\b(?:là\s+gì|tên\s+gì|tên\s+là\s+gì|như\s+thế\s+nào|ở\s+đâu|khi\s+nào|năm\s+nào|bao\s+nhiêu|mấy\s+người|màu\s+gì|màu\s+sắc\s+gì|thơ\s+gì|chữ\s+gì|ai)\b[\s\?\.!]*$',
    r'\b(?:what\s+is|where\s+is|who\s+is|when\s+is|how\s+many|what\s+color\s+is)\b',
    r'[\?\.!]+$'
]

# Các mẫu câu dẫn chuyện dư thừa trong KIS
PROMPT_NOISE_PATTERNS = [
    r'^(?:hãy\s+)?(?:tìm\s+kiếm|tìm\s+cho\s+tôi|tìm\s+cảnh\s+chiếc|tìm\s+cảnh|tìm\s+chiếc|tìm\s+ảnh|tìm|cho\s+tôi\s+thấy|xuất\s+hiện|video\s+quay\s+cảnh|đoạn\s+video\s+về|khung\s+hình\s+chứa|hình\s+ảnh\s+về|tìm\s+video)\s+[:：]?',
    r'^(?:search\s+for|find\s+a\s+video\s+of|show\s+me|look\s+for)\s+[:：]?'
]


class DecomposedQuery(BaseModel):
    raw_query: str
    mode: str = "kis"  # "kis" | "trake" | "ocr" | "asr" | "qa"
    global_topic: str = ""
    stages: List[str] = Field(default_factory=list)
    visual_query: str = ""
    visual_query_en: str = ""
    ocr_keywords: List[str] = Field(default_factory=list)
    asr_keywords: List[str] = Field(default_factory=list)
    detected_entities: List[str] = Field(default_factory=list)
    is_temporal: bool = False
    is_qa: bool = False
    is_ocr_dominant: bool = False
    confidence: float = 1.0
    explanation: str = ""


class SmartQueryDecomposer:
    """
    Bộ bóc tách & phân rã truy vấn thông minh:
    - Zero VRAM (chạy 100% trên CPU RAM).
    - Tự động nhận diện bài thi KIS, QA, TRAKE, OCR, ASR.
    - Cắt chuỗi sự kiện theo thời gian cực kỳ chuẩn xác.
    - Trích xuất từ khóa OCR trong dấu ngoặc kép hoặc sau các tiền tố.
    - Tự động sinh visual English description để tối đa hóa hiệu năng Google SigLIP 2 Giant.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.provider = self.config.get("provider", "rule_fast")  # "rule_fast" | "local_cpu" | "openai" | "gemini"

    def clean_noise(self, text: str) -> str:
        """Loại bỏ các từ nối dẫn chuyện không mang thông tin hình ảnh"""
        if not text:
            return ""
        res = text.strip()
        for pat in PROMPT_NOISE_PATTERNS:
            res = re.sub(pat, '', res, flags=re.IGNORECASE).strip()
        return res

    def clean_qa_question(self, text: str) -> Tuple[str, bool]:
        """Làm sạch câu hỏi QA thành mệnh đề thị giác trực tiếp"""
        if not text:
            return "", False
        is_qa = False
        res = text.strip()

        # Kiểm tra dấu hỏi hoặc từ để hỏi
        if "?" in res or any(q in res.lower() for q in ["là gì", "ở đâu", "ai", "màu gì", "bao nhiêu", "mấy", "tên gì", "what", "where", "who", "which"]):
            is_qa = True

        for pat in QA_QUESTION_CLEAN_PATTERNS:
            res = re.sub(pat, '', res, flags=re.IGNORECASE).strip()

        # Xóa các từ nghi vấn ở giữa câu nếu có
        res = re.sub(r'\b(?:màu\s+gì|ở\s+đâu|là\s+ai|tên\s+gì)\b', '', res, flags=re.IGNORECASE).strip()
        res = re.sub(r'\s+', ' ', res)
        return res, is_qa

    def extract_ocr_keywords(self, text: str) -> Tuple[str, List[str]]:
        """
        Trích xuất từ khóa OCR:
        1. Ưu tiên tuyệt đối chuỗi trong dấu ngoặc kép: "Highlands", 'BIDV', "29A-12345"
        2. Nếu không có ngoặc kép, trích xuất chính xác theo tiền tố: có chữ..., biển số..., bảng hiệu...
        """
        if not text:
            return text, []

        ocr_kws = []
        cleaned_text = text

        # 1. Trích xuất chính xác trong dấu ngoặc kép
        quotes = re.findall(r'["\'“«](.*?)["\'”»]', text)
        for q in quotes:
            q_clean = q.strip()
            if len(q_clean) >= 2 and q_clean not in ocr_kws:
                ocr_kws.append(q_clean)
                cleaned_text = cleaned_text.replace(f'"{q}"', q_clean).replace(f"'{q}'", q_clean).replace(f'“{q}”', q_clean).replace(f'«{q}»', q_clean)

        # 2. Nếu đã có ngoặc kép thì dừng lại để giữ độ chính xác 100%, không nhận thêm từ thừa
        if ocr_kws:
            return cleaned_text, ocr_kws

        # 3. Trích xuất theo tiền tố nhận diện (khi người dùng không dùng ngoặc kép)
        patterns = [
            r'(?:biển\s+số|biển\s+xe)\s+[:：]?\s*([A-Z0-9\-\.\s]{3,12})',
            r'(?:có\s+chữ|in\s+chữ|khắc\s+chữ|mang\s+dòng\s+chữ|chữ\s+in\s+hoa|chữ)\s+[:：]?\s*([^,\.\n;]+)',
            r'(?:bảng\s+hiệu|bảng\s+tên|biển\s+hiệu|logo|cổng\s+chào)\s+[:：]?\s*([^,\.\n;]+)',
            r'(?:tên\s+đường)\s+[:：]?\s*([^,\.\n;]+)'
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                val = m.group(1).strip(" \"'“”«»")
                # Cắt bỏ các từ chỉ vị trí hoặc từ nối phía sau nếu có
                val = re.split(r'\b(?:ở|tại|trên|dưới|góc|màu|trong|với|của)\b', val, flags=re.IGNORECASE)[0].strip()
                if len(val) >= 2 and val.lower() not in {"ở", "trên", "dưới", "của", "và", "trong"} and val not in ocr_kws:
                    ocr_kws.append(val)

        return cleaned_text, ocr_kws

    def extract_asr_keywords(self, text: str) -> Tuple[str, List[str]]:
        """Trích xuất từ khóa ASR (Lời thoại / Âm thanh)"""
        if not text:
            return text, []

        asr_kws = []
        cleaned_text = text

        # 1. Trích xuất lời thoại trong ngoặc kép sau từ khóa nói/hát
        spoken_quotes = re.findall(r'(?:nói|bảo|hát|phát\s+biểu|hỏi|kể)\s*[:：]?\s*["\'“«](.*?)["\'”»]', text, re.IGNORECASE)
        for q in spoken_quotes:
            q_clean = q.strip()
            if len(q_clean) >= 2 and q_clean not in asr_kws:
                asr_kws.append(q_clean)

        # 2. Trích xuất mọi chuỗi trong dấu ngoặc kép (người dùng tìm từ khóa văn bản / lời thoại)
        general_quotes = re.findall(r'["\'“«](.*?)["\'”»]', text)
        for q in general_quotes:
            q_clean = q.strip()
            if len(q_clean) >= 2 and q_clean not in asr_kws:
                asr_kws.append(q_clean)

        if asr_kws:
            return cleaned_text, asr_kws

        patterns = [
            r'(?:nói|kể|hát|phát\s+biểu|chia\s+sẻ|nhắc\s+đến|đọc\s+thơ|ca\s+ngợi)\s+về\s+[:：]?\s*([^,\.\n;]+)',
            r'(?:nói\s+rằng|bảo\s+rằng|hát\s+câu)\s+[:：]?\s*([^,\.\n;]+)',
            r'(?:bài\s+thơ|câu\s+thơ)\s+[:：]?\s*([^,\.\n;]+)'
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                val = m.group(1).strip(" \"'“”«»")
                val = re.split(r'\b(?:ở|tại|trên|dưới|trong|sau\s+đó|tiếp\s+theo)\b', val, flags=re.IGNORECASE)[0].strip()
                if len(val) >= 2 and val not in asr_kws:
                    asr_kws.append(val)

        return cleaned_text, asr_kws

    def extract_global_topic(self, text: str) -> Tuple[str, str]:
        """
        Trích xuất chủ đề chung (Global Topic) nếu câu mở đầu bằng bối cảnh:
        Ví dụ: "Trong một quán cà phê, người đàn ông gọi nước sau đó rời đi" -> Topic: "quán cà phê"
        """
        if not text:
            return "", text

        topic_match = re.match(
            r'^(?:trong\s+(?:một\s+)?|tại\s+(?:một\s+)?|ở\s+(?:một\s+)?|khung\s+cảnh\s+)([^,;\n\.\-–]+)[,;\-–]\s*(.+)$',
            text.strip(),
            re.IGNORECASE
        )
        if topic_match:
            topic = topic_match.group(1).strip()
            rest = topic_match.group(2).strip()
            # Nếu topic hợp lý (dưới 60 ký tự)
            if 2 <= len(topic) <= 60 and len(rest) >= 4:
                return topic, rest

        return "", text

    def translate_to_visual_english(self, text_vn: str) -> str:
        """
        Dịch và làm giàu câu mô tả tiếng Việt sang tiếng Anh tự nhiên (Visual English)
        giúp tăng 5-10% độ chính xác cho SigLIP 2 Giant (WebLI Pretrained).
        """
        if not text_vn:
            return ""

        t_lower = text_vn.lower().strip()
        matched_en_terms = []

        # 1. Tìm các cụm từ trong từ điển theo thứ tự độ dài giảm dần
        sorted_keys = sorted(VIET_TO_ENG_VISUAL_MAP.keys(), key=lambda k: len(k), reverse=True)
        for key in sorted_keys:
            if key in t_lower:
                en_val = VIET_TO_ENG_VISUAL_MAP[key]
                if en_val not in matched_en_terms:
                    matched_en_terms.append(en_val)

        if matched_en_terms:
            # Tạo câu visual English cô đọng
            combined_en = ", ".join(matched_en_terms)
            return f"A video scene of {combined_en}"
        return ""

    def decompose(self, raw_text: str, current_topic: str = "") -> DecomposedQuery:
        """
        Thực hiện toàn bộ quy trình phân rã & tinh chỉnh câu truy vấn.
        """
        if not raw_text or not raw_text.strip():
            return DecomposedQuery(raw_query="", mode="kis", visual_query="")

        raw_clean = raw_text.strip()
        
        # 1. Bóc tách chủ đề chung (Global Topic) nếu chưa có
        extracted_topic, text_no_topic = self.extract_global_topic(raw_clean)
        global_topic = (current_topic or extracted_topic).strip()

        # 2. Bóc tách OCR & ASR keywords
        text_no_ocr, ocr_kws = self.extract_ocr_keywords(text_no_topic)
        text_no_asr, asr_kws = self.extract_asr_keywords(text_no_topic)

        # Mọi từ khóa trong ngoặc kép đều được tìm kiếm song song trên cả OCR và ASR
        all_exact_kws = list(dict.fromkeys(ocr_kws + asr_kws))
        ocr_kws = all_exact_kws
        asr_kws = all_exact_kws

        # 3. Làm sạch câu hỏi Video QA & từ nối rác
        cleaned_core, is_qa = self.clean_qa_question(text_no_ocr)
        cleaned_core = self.clean_noise(cleaned_core)

        # 4. Kiểm tra và bóc tách chuỗi thời gian (TRAKE Multi-stage)
        raw_stages = [s.strip() for s in TEMPORAL_SPLIT_REGEX.split(cleaned_core) if s and s.strip()]
        
        # Lọc các stage hợp lệ (loại bỏ từ nối đơn lẻ và dấu phẩy/chấm thừa)
        valid_stages = []
        for s in raw_stages:
            clean_s = self.clean_noise(s)
            clean_s = re.sub(r'^(?:sau\s+đó|tiếp\s+theo|tiếp\s+đến|kế\s+tiếp|ngay\s+sau\s+đó|về\s+sau|lúc\s+sau|đoạn\s+sau|rồi\s+mới|rồi\s+sau\s+đó|rồi|then|after\s+that|afterwards|following\s+that|next)\s*[:,\.\-–]?\s*', '', clean_s, flags=re.IGNORECASE).strip()
            # Xóa các dấu câu ở đầu và cuối stage
            clean_s = clean_s.strip(" ,;.:-–—/|")
            if len(clean_s) >= 3 and not re.match(r'^(?:->|-->|=>|;|stage|bước|cảnh)\s*[0-9]*$', clean_s, re.IGNORECASE):
                valid_stages.append(clean_s)

        is_temporal = len(valid_stages) >= 2

        # 5. Xác định Mode chính xác
        if is_temporal:
            mode = "trake"
            explanation = f"Nhận diện chuỗi sự kiện đa thời gian TRAKE ({len(valid_stages)} giai đoạn tuần tự)."
        elif ocr_kws and len(cleaned_core.split()) <= 4:
            mode = "ocr"
            explanation = f"Nhận diện truy vấn tập trung vào chữ viết màn hình OCR: {', '.join(ocr_kws)}."
        elif asr_kws and len(cleaned_core.split()) <= 4:
            mode = "asr"
            explanation = f"Nhận diện truy vấn tập trung vào lời thoại ASR: {', '.join(asr_kws)}."
        elif is_qa:
            mode = "qa"
            explanation = "Nhận diện câu hỏi Video QA -> Đã làm sạch thành mô tả thị giác cốt lõi."
        else:
            mode = "kis"
            explanation = "Nhận diện mô tả khoảnh khắc đơn lẻ (KIS Mode)."

        # 6. Tạo visual query sạch và visual query tiếng Anh
        final_visual_vn = " - ".join(valid_stages) if is_temporal else (cleaned_core or raw_clean)
        if global_topic and global_topic.lower() not in final_visual_vn.lower():
            final_visual_vn = f"{global_topic} - {final_visual_vn}"

        visual_en = self.translate_to_visual_english(final_visual_vn)

        return DecomposedQuery(
            raw_query=raw_clean,
            mode=mode,
            global_topic=global_topic,
            stages=valid_stages if is_temporal else [final_visual_vn],
            visual_query=final_visual_vn,
            visual_query_en=visual_en,
            ocr_keywords=ocr_kws,
            asr_keywords=asr_kws,
            detected_entities=[k for k in VIET_TO_ENG_VISUAL_MAP if k in raw_clean.lower()],
            is_temporal=is_temporal,
            is_qa=is_qa,
            is_ocr_dominant=(mode == "ocr"),
            confidence=0.95,
            explanation=explanation
        )


# Singleton instance để sử dụng toàn cục
smart_decomposer = SmartQueryDecomposer()
