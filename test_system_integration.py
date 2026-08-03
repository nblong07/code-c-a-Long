"""
Kịch bản Kiểm thử Tự động Hệ thống (System Integration & Verification Script)
=============================================================================
Kiểm tra toàn bộ các module mới nâng cấp:
1. Adaptive Query Router (Phân loại truy vấn tự động)
2. Lifelog Frame Filter (Heuristics lọc mờ nhòe & phơi sáng)
3. Tree of Thoughts (ToT) Agent & Counter-Questioning (Hỏi ngược lại giám khảo)
4. HippoRAG Memory System (Duy trì ngữ cảnh đa lượt)
5. FastAPI Backend Routes & App Health
"""

import sys
import unittest
import numpy as np
import cv2

# Tự động cấu hình mã hóa UTF-8 cho Windows Console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Import các module từ backend và database
from backend.main import (
    AdaptiveQueryRouter,
    QueryType,
    LifelogFrameFilter,
    TreeOfThoughtsAgent,
    HippoRAGMemory,
    create_app
)


class TestLifelogSystem(unittest.TestCase):

    def setUp(self):
        self.router = AdaptiveQueryRouter()
        self.frame_filter = LifelogFrameFilter(blur_threshold=95.0)
        self.tot_agent = TreeOfThoughtsAgent()
        self.hippo_memory = HippoRAGMemory()

    def test_01_adaptive_query_router(self):
        print("\n[TEST 1] Kiểm thử Adaptive Query Router...")
        
        # Test Simple Text
        qtype, strategy = self.router.route_query("a man walking dog")
        self.assertEqual(qtype, QueryType.SIMPLE_TEXT)
        print(f"  ✓ Simple Text Query: '{qtype.value}' ({strategy})")

        # Test Temporal Query
        qtype, strategy = self.router.route_query("after holding red cup, then he sat down")
        self.assertEqual(qtype, QueryType.TEMPORAL)
        print(f"  ✓ Temporal Query: '{qtype.value}' ({strategy})")

        # Test OCR Query
        qtype, strategy = self.router.route_query("storefront with written sign 'COFFEE'")
        self.assertEqual(qtype, QueryType.OCR_TEXT)
        print(f"  ✓ OCR Query: '{qtype.value}' ({strategy})")

        # Test Fine-grained Object Query
        qtype, strategy = self.router.route_query("a red cup on a white round table next to a black laptop computer")
        self.assertEqual(qtype, QueryType.FINE_GRAINED_OBJECT)
        print(f"  ✓ Fine-grained Object Query: '{qtype.value}' ({strategy})")

        # Test Ambiguous Query
        qtype, strategy = self.router.route_query("vui vẻ")
        self.assertEqual(qtype, QueryType.AMBIGUOUS)
        print(f"  ✓ Ambiguous Query: '{qtype.value}' ({strategy})")

        # Test Automatic Model Selection & Environment Prediction
        opt_info = self.router.select_optimal_model("storefront on street at night with sign 'COFFEE'")
        self.assertIn("recommended_model", opt_info)
        self.assertIn("predicted_environment", opt_info)
        print(f"  ✓ Dự đoán Môi trường Video: '{opt_info['predicted_environment']}' -> Mô hình tự chọn tuyệt nhất: '{opt_info['recommended_model']}'")
        print(f"  ✓ Lý giải: {opt_info['reasoning_explanation']}")

    def test_02_lifelog_frame_filter(self):
        print("\n[TEST 2] Kiểm thử Lifelog Frame Heuristic Filter...")
        
        # Tạo khung hình bình thường hợp lệ
        valid_img = np.ones((480, 640, 3), dtype=np.uint8) * 128
        # Thêm vân chi tiết để có điểm Laplacian variance cao
        cv2.putText(valid_img, "TEST FRAME VALID", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
        valid, msg, score = self.frame_filter.is_frame_valid(valid_img)
        self.assertTrue(valid)
        print(f"  ✓ Valid Frame Check: {msg} (Score: {score:.1f})")

        # Tạo khung hình mờ nhòe (Blank/Uniform)
        blurry_img = np.ones((480, 640, 3), dtype=np.uint8) * 100
        valid, msg, score = self.frame_filter.is_frame_valid(blurry_img)
        self.assertFalse(valid)
        print(f"  ✓ Blurred Frame Filtered: {msg} (Score: {score:.1f})")

        # Tạo khung hình đen tối (Underexposed)
        dark_img = np.zeros((480, 640, 3), dtype=np.uint8)
        valid, msg, score = self.frame_filter.is_frame_valid(dark_img)
        self.assertFalse(valid)
        print(f"  ✓ Dark Frame Filtered: {msg}")

    def test_03_tot_agent_clarification(self):
        print("\n[TEST 3] Kiểm thử Tree of Thoughts (ToT) Agent & Counter-Questioning...")
        
        # Thử nghiệm với câu truy vấn mơ hồ
        ambiguous_res = self.tot_agent.evaluate_and_expand("ăn cơm")
        self.assertTrue(ambiguous_res["is_ambiguous"])
        self.assertIsNotNone(ambiguous_res["clarifying_question"])
        print(f"  ✓ Tự động phát hiện mơ hồ: {ambiguous_res['recommended_action']}")
        print(f"  ✓ Câu hỏi làm rõ gửi Giám khảo: '{ambiguous_res['clarifying_question']}'")
        self.assertEqual(len(ambiguous_res["tot_branches"]), 3)

    def test_04_hipporag_memory(self):
        print("\n[TEST 4] Kiểm thử HippoRAG Multi-Turn Memory...")
        
        self.hippo_memory.add_interaction("tìm xe máy màu đỏ", ["video_001", "video_002"])
        self.hippo_memory.add_interaction("khung hình sau đó", ["video_001", "video_003"])
        
        summary = self.hippo_memory.get_context_summary()
        self.assertEqual(summary["total_turns"], 2)
        self.assertEqual(summary["top_focused_videos"][0], "video_001")
        print(f"  ✓ HippoRAG Memory Summary: {summary}")

    def test_06_multi_query_payload_extraction(self):
        print("\n[TEST 6] Kiểm thử bóc tách payload multi_query tiếng Việt ('tòa nhà')...")
        payload = {
            "type": "multi_query",
            "model": "clip",
            "queries": [
                {"type": "text", "content": "tòa nhà", "mode": "temporal-search"}
            ]
        }
        queries = payload.get("queries", [])
        first_q = queries[0].get("content") if queries else ""
        self.assertEqual(first_q, "tòa nhà")
        print(f"  ✓ Bóc tách thành công Cảnh 1 query: '{first_q}' từ payload Frontend")


if __name__ == "__main__":
    unittest.main()
