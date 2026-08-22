import os
import sys
import cv2
import glob
import numpy as np
import argparse
from tqdm import tqdm
from transnetv2 import TransNetV2

def save_image_webp(img_bgr, path: str, quality: int = 80, resize_factor: float = 0.5):
    if resize_factor != 1.0:
        img_bgr = cv2.resize(img_bgr, (0, 0), fx=resize_factor, fy=resize_factor)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, img_bgr, [cv2.IMWRITE_WEBP_QUALITY, quality])

def evaluate_frame_quality(frame_bgr, blur_thresh: float = 95.0, min_lum: float = 20.0, max_lum: float = 235.0):
    """Danh gia do net va do sang cua frame de loai bo frame mo/nhoe hoac chay sang"""
    if frame_bgr is None or frame_bgr.size == 0:
        return 0.0, False
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
    mean_lum = float(np.mean(lab[:, :, 0]))
    
    is_valid = (blur_score >= blur_thresh) and (min_lum <= mean_lum <= max_lum)
    return blur_score, is_valid

def extract_with_transnet(model, video_path, output_dir, resize_factor=0.5, quality=80):
    
    print(f"Processing {video_path}...")
    video_frames, single_frame_predictions, all_frame_predictions = model.predict_video(video_path)
    
    predictions = (single_frame_predictions > 0.5).astype(np.uint8)
    
    # Find shot boundaries (where prediction changes to 1)
    scenes = []
    current_scene = []
    for i, p in enumerate(predictions):
        if p == 1 and len(current_scene) > 0:
            scenes.append(current_scene)
            current_scene = []
        current_scene.append(i)
    if current_scene:
        scenes.append(current_scene)
        
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    kf_dir = os.path.join(output_dir, video_name, "keyframes")
    os.makedirs(kf_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    
    csv_path = os.path.join(output_dir, "maps", f"{video_name}_map.csv")
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    
    saved_count = 0
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write("FrameID,Seconds,VideoID,Timestamp_ms,FPS\n")
        
        for scene_frames in scenes:
            if not scene_frames:
                continue
            
            # Xac dinh so luong keyframe can lay theo do dai shot
            # Canh ngan (< 3s): 1 frame; Canh vua (3-8s): 2 frames; Canh dai (> 8s): 3 frames
            num_frames = len(scene_frames)
            duration_sec = num_frames / fps
            
            if duration_sec > 8.0:
                target_indices = [
                    scene_frames[int(num_frames * 0.2)],
                    scene_frames[int(num_frames * 0.5)],
                    scene_frames[int(num_frames * 0.8)]
                ]
            elif duration_sec > 3.5:
                target_indices = [
                    scene_frames[int(num_frames * 0.33)],
                    scene_frames[int(num_frames * 0.67)]
                ]
            else:
                target_indices = [scene_frames[len(scene_frames) // 2]]

            for base_idx in target_indices:
                # Tim frame net nhat trong ban kinh 5 frames lan can
                best_idx = base_idx
                best_score = -1.0
                best_frame = None

                search_window = [
                    idx for idx in range(max(scene_frames[0], base_idx - 5), min(scene_frames[-1] + 1, base_idx + 6))
                ]
                
                for cand_idx in search_window:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, cand_idx)
                    ret, frame = cap.read()
                    if ret:
                        score, valid = evaluate_frame_quality(frame)
                        if score > best_score:
                            best_score = score
                            best_idx = cand_idx
                            best_frame = frame
                
                if best_frame is not None:
                    frame_id_1based = best_idx + 1
                    kf_path = os.path.join(kf_dir, f"keyframe_{frame_id_1based}.webp")
                    save_image_webp(best_frame, kf_path, quality, resize_factor)
                    
                    # Presentation Time (PTS) theo mili-giây từ luồng video
                    pts_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                    if pts_msec <= 0 and fps > 0:
                        pts_msec = (best_idx / fps) * 1000.0
                    pts_sec = pts_msec / 1000.0
                    
                    # Ghi CSV theo chuẩn DRES: FrameID (1-based), Seconds (PTS), Timestamp_ms (PTS ms)
                    f.write(f"{frame_id_1based},{pts_sec:.3f},{video_name},{pts_msec:.3f},{fps:.2f}\n")
                    saved_count += 1
                
    cap.release()
    print(f"Extracted {saved_count} adaptive keyframes across {len(scenes)} scenes for {video_name} (1-based FrameID, PTS Presentation Time)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-folder", type=str, required=True)
    parser.add_argument("--output-base", type=str, default="./data-keyframes")
    args = parser.parse_args()
    
    videos = glob.glob(os.path.join(args.input_folder, "*.mp4"))
    
    if videos:
        print("Loading TransNetV2 model...")
        model = TransNetV2()
    else:
        print("No videos found.")
        sys.exit(0)

    for v in tqdm(videos):
        extract_with_transnet(model, v, args.output_base)
