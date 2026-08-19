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
    
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write("FrameID,Seconds,VideoID,Timestamp_ms,FPS\n")
        
        for scene_frames in scenes:
            if not scene_frames: continue
            # Get middle frame of the scene as keyframe
            mid_idx = scene_frames[len(scene_frames) // 2]
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, mid_idx)
            ret, frame = cap.read()
            if ret:
                kf_path = os.path.join(kf_dir, f"keyframe_{mid_idx}.webp")
                save_image_webp(frame, kf_path, quality, resize_factor)
                
                msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                sec = msec / 1000.0
                f.write(f"{mid_idx},{sec:.3f},{video_name},{msec:.3f},{fps:.2f}\n")
                
    cap.release()
    print(f"Extracted {len(scenes)} scenes for {video_name}")

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
