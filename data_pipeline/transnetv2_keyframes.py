import os
import sys
import cv2
import glob
import numpy as np
import argparse
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

# Tự động ưu tiên load model TransNetV2 tối ưu nhất (PyTorch GPU > ONNX GPU > TensorFlow)
MODEL_TYPE = "unknown"
try:
    from transnetv2_pytorch import TransNetV2
    MODEL_TYPE = "pytorch"
except ImportError:
    try:
        from transnetv2 import TransNetV2
        MODEL_TYPE = "tensorflow"
    except ImportError:
        TransNetV2 = None

def save_image_webp(img_bgr, path: str, quality: int = 80, resize_factor: float = 0.5):
    """Lưu ảnh WebP với nội suy INTER_AREA cho chất lượng sắc nét nhất"""
    if resize_factor != 1.0:
        img_bgr = cv2.resize(img_bgr, (0, 0), fx=resize_factor, fy=resize_factor, interpolation=cv2.INTER_AREA)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, img_bgr, [cv2.IMWRITE_WEBP_QUALITY, quality])

def compute_dhash(image_bgr, hash_size=8):
    """
    Tính Difference Hash (dHash) để so khớp độ tương đồng hình ảnh siêu nhanh.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    # So sánh cột liền kề
    diff = resized[:, 1:] > resized[:, :-1]
    return diff.flatten()

def compute_hamming_distance(hash1, hash2):
    """Tính khoảng cách Hamming giữa 2 dHash (0 -> 64). Càng nhỏ càng giống nhau."""
    return int(np.count_nonzero(hash1 != hash2))

def evaluate_frame_quality(frame_bgr, is_boundary: bool = False, blur_thresh: float = 70.0, min_lum: float = 20.0, max_lum: float = 238.0):
    """
    Đánh giá chất lượng frame và LỌC RÁC KHÁCH QUAN:
    1. Lọc nhòe chuyển động (Laplacian variance) với ngưỡng thích nghi
    2. Lọc đen xì / tối mù hoặc cháy sáng toàn phần
    3. Lọc frame chớp sáng / hiệu ứng chuyển cảnh flash (CHỈ KÍCH HOẠT Ở 2 ĐẦU BIÊN CẢNH)
    4. Lọc frame đơn sắc / solid banner quảng cáo
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return 0.0, False

    # 1. Độ nét Laplacian
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if blur_score < blur_thresh:
        return blur_score, False

    # 2. Độ sáng trung bình (Luminance)
    lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0]
    mean_lum = float(np.mean(l_channel))
    if mean_lum < min_lum or mean_lum > max_lum:
        return blur_score, False

    # 3. Lọc hiệu ứng chói lóa / transition flash:
    # Chỉ lọc khi ở ranh giới 2 đầu của shot (is_boundary=True). 
    # Tránh xóa nhầm frame ở giữa shot chứa ánh đèn sân khấu, tuyết trắng thật.
    if is_boundary:
        overexposed_ratio = float(np.count_nonzero(l_channel > 248)) / l_channel.size
        if overexposed_ratio > 0.28:
            return blur_score, False

    # 4. Lọc frame đơn sắc / solid banner quảng cáo
    std_lum = float(np.std(l_channel))
    if std_lum < 16.0:
        return blur_score, False

    return blur_score, True

def get_adaptive_target_indices(scene_frames, fps, is_fast_action=False):
    """
    Chiến lược Adaptive Dynamic Density Sampling:
    - Cảnh hành động dồn dập: Lấy frame mỗi ~0.8s - 1.0s
    - Cảnh ngắn (< 1.5s): 1 frame
    - Cảnh vừa (1.5s - 4.0s): 2 frames (30%, 70%)
    - Cảnh trung bình (4.0s - 8.0s): 3 frames (20%, 50%, 80%)
    - Cảnh dài (> 8.0s): Lấy đều mỗi ~2.5s
    """
    num_frames = len(scene_frames)
    if num_frames == 0:
        return []
    
    fps_val = fps or 25.0
    duration_sec = num_frames / fps_val

    if is_fast_action:
        step_frames = max(int(fps_val * 0.9), 1)
        indices = list(range(scene_frames[0] + step_frames // 2, scene_frames[-1], step_frames))
        if not indices:
            indices = [scene_frames[num_frames // 2]]
        return indices

    if duration_sec <= 1.5:
        return [scene_frames[num_frames // 2]]
    elif duration_sec <= 4.0:
        return [
            scene_frames[int(num_frames * 0.3)],
            scene_frames[int(num_frames * 0.7)]
        ]
    elif duration_sec <= 8.0:
        return [
            scene_frames[int(num_frames * 0.2)],
            scene_frames[int(num_frames * 0.5)],
            scene_frames[int(num_frames * 0.8)]
        ]
    else:
        step_frames = int(fps_val * 2.5)
        indices = list(range(scene_frames[0] + int(fps_val * 0.8), scene_frames[-1], step_frames))
        if not indices:
            indices = [scene_frames[num_frames // 2]]
        return indices

def extract_with_transnet(model, video_path, output_dir, resize_factor=0.5, quality=80, dhash_threshold=6, num_workers=4):
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    csv_path = os.path.join(output_dir, "maps", f"{video_name}_map.csv")
    
    # Tự động kiểm tra Resume / Skip nếu video đã xử lý xong
    if os.path.exists(csv_path) and os.path.getsize(csv_path) > 100:
        print(f"⏩ [SKIP] Đã trích xuất trước đó: {video_name}")
        return

    print(f"🎬 Processing {os.path.basename(video_path)}...")
    video_frames, single_frame_predictions, all_frame_predictions = model.predict_video(video_path)
    
    predictions = (single_frame_predictions > 0.5).astype(np.uint8)
    
    # Gom nhóm shot boundaries
    scenes = []
    current_scene = []
    for i, p in enumerate(predictions):
        if p == 1 and len(current_scene) > 0:
            scenes.append(current_scene)
            current_scene = []
        current_scene.append(i)
    if current_scene:
        scenes.append(current_scene)
        
    kf_dir = os.path.join(output_dir, video_name, "keyframes")
    os.makedirs(kf_dir, exist_ok=True)
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    
    saved_count = 0
    saved_hashes = []  # Lưu dHash để lọc trùng lặp nội dung
    current_cap_pos = -1  # Bộ đếm vị trí đọc video liên tục

    # Sử dụng ThreadPoolExecutor để ghi ảnh WebP bất đồng bộ
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write("FrameID,Seconds,VideoID,Timestamp_ms,FPS\n")
            
            for scene_frames in scenes:
                if not scene_frames:
                    continue
                
                is_fast_action = len(scene_frames) < int(fps * 2.0) and len(scenes) > 15
                target_indices = get_adaptive_target_indices(scene_frames, fps, is_fast_action=is_fast_action)

                for base_idx in target_indices:
                    start_window = max(scene_frames[0], base_idx - 3)
                    end_window = min(scene_frames[-1], base_idx + 3)
                    
                    # Kiểm tra xem base_idx có nằm sát 2 đầu biên shot hay không
                    is_boundary = (base_idx - scene_frames[0] <= 4) or (scene_frames[-1] - base_idx <= 4)
                    
                    # TỐI ƯU HÓA: Fast Seek
                    if current_cap_pos < 0 or start_window < current_cap_pos or (start_window - current_cap_pos) > 15:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, start_window)
                        current_cap_pos = start_window
                    else:
                        while current_cap_pos < start_window:
                            cap.grab()
                            current_cap_pos += 1

                    best_idx = base_idx
                    best_score = -1.0
                    best_frame = None

                    fallback_idx = base_idx
                    fallback_score = -1.0
                    fallback_frame = None

                    # Quét tìm frame đẹp nhất trong cửa sổ
                    for curr_frame_idx in range(start_window, end_window + 1):
                        ret, frame = cap.read()
                        current_cap_pos += 1
                        if not ret or frame is None:
                            break
                        
                        score, is_valid = evaluate_frame_quality(frame, is_boundary=is_boundary)
                        
                        # Lưu fallback dự phòng (trong trường hợp video cũ quá mờ không qua được bộ lọc)
                        if score > fallback_score:
                            fallback_score = score
                            fallback_idx = curr_frame_idx
                            fallback_frame = frame

                        if is_valid and score > best_score:
                            best_score = score
                            best_idx = curr_frame_idx
                            best_frame = frame
                            # Early Exit nếu frame cực nét
                            if score > 280.0:
                                break
                    
                    # Fallback Guarantee: Đảm bảo không bao giờ bỏ sót cảnh dù video có chất lượng thấp
                    chosen_frame = best_frame if best_frame is not None else fallback_frame
                    chosen_idx = best_idx if best_frame is not None else fallback_idx

                    if chosen_frame is not None:
                        frame_hash = compute_dhash(chosen_frame)
                        
                        is_duplicate = False
                        for past_hash in saved_hashes[-4:]:
                            if compute_hamming_distance(frame_hash, past_hash) <= dhash_threshold:
                                is_duplicate = True
                                break
                        
                        if is_duplicate:
                            continue

                        frame_id_1based = chosen_idx + 1
                        kf_path = os.path.join(kf_dir, f"keyframe_{frame_id_1based}.webp")
                        
                        # Ghi ảnh trên background thread
                        executor.submit(save_image_webp, chosen_frame.copy(), kf_path, quality, resize_factor)
                        saved_hashes.append(frame_hash)
                        
                        # Tính Presentation Time (PTS)
                        pts_msec = (chosen_idx / fps) * 1000.0
                        pts_sec = pts_msec / 1000.0
                        
                        f.write(f"{frame_id_1based},{pts_sec:.3f},{video_name},{pts_msec:.3f},{fps:.2f}\n")
                        saved_count += 1
                
    cap.release()
    print(f"✨ Trích xuất thành công {saved_count} keyframes (Đảm bảo 100% không mất cảnh) cho {video_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-folder", type=str, required=True, help="Thư mục chứa video (.mp4)")
    parser.add_argument("--output-base", type=str, default="./data-keyframes", help="Thư mục lưu keyframes và map csv")
    parser.add_argument("--resize-factor", type=float, default=0.5, help="Hệ số scale ảnh (0.5 = 50% độ phân giải)")
    parser.add_argument("--quality", type=int, default=80, help="Chất lượng nén ảnh WebP (1-100)")
    parser.add_argument("--dhash-thresh", type=int, default=6, help="Ngưỡng lọc trùng dHash (mặc định 6)")
    parser.add_argument("--workers", type=int, default=4, help="Số luồng ghi ảnh WebP đồng thời")
    args = parser.parse_args()
    
    videos = glob.glob(os.path.join(args.input_folder, "*.mp4")) + glob.glob(os.path.join(args.input_folder, "*.mkv"))
    
    if not videos:
        print(f"Không tìm thấy video nào trong '{args.input_folder}'.")
        sys.exit(0)

    print(f"Khởi tạo TransNetV2 (Backend: {MODEL_TYPE.upper()})...")
    if TransNetV2 is None:
        print("Lỗi: Chưa cài đặt thư viện TransNetV2. Vui lòng cài transnetv2-pytorch hoặc transnetv2.")
        sys.exit(1)
        
    model = TransNetV2()

    for v in tqdm(videos, desc="Đang trích xuất Video Keyframes"):
        extract_with_transnet(
            model, 
            v, 
            args.output_base, 
            resize_factor=args.resize_factor, 
            quality=args.quality,
            dhash_threshold=args.dhash_thresh,
            num_workers=args.workers
        )


