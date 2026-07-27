import os
import torch
import clip
from PIL import Image
import numpy as np
from tqdm import tqdm

# 1. Đường dẫn thư mục
keyframes_dir = r"D:\Users\ADMIN\Downloads\output-keyframes"

print("--------------------------------------------------")
print("Đường dẫn đang quét:", keyframes_dir)
print("Thư mục có tồn tại không?:", os.path.exists(keyframes_dir))

# 2. Tìm tất cả các file ảnh (kể cả file trong thư mục con)
image_paths = []
for root, _, files in os.walk(keyframes_dir):
    # Bỏ qua thư mục maps
    if "maps" in root:
        continue
    for file in files:
        # Lấy tất cả file trừ các file hệ thống hoặc file text
        if not file.endswith(('.json', '.csv', '.txt', '.DS_Store')):
            image_paths.append(os.path.join(root, file))

image_paths.sort()
print(f"Tìm thấy tổng cộng {len(image_paths)} ảnh keyframe.")
print("--------------------------------------------------")

if len(image_paths) == 0:
    print("X Báo lỗi: Vẫn không thấy ảnh! Vui lòng kiểm tra lại file bên trong folder K01_V001 xem có phải là ảnh không.")
    exit()

# 3. Load CLIP
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Đang chạy trên thiết bị: {device}")
model, preprocess = clip.load("ViT-B/32", device=device)

# 4. Trích xuất feature
features = []
valid_paths = []

for path in tqdm(image_paths, desc="Đang trích xuất vector"):
    try:
        image = preprocess(Image.open(path)).unsqueeze(0).to(device)
        with torch.no_grad():
            image_feature = model.encode_image(image)
            image_feature /= image_feature.norm(dim=-1, keepdim=True)
            features.append(image_feature.cpu().numpy().flatten())
            valid_paths.append(path)
    except Exception as e:
        # Bỏ qua nếu file đó không phải là ảnh hợp lệ
        continue

# 5. Lưu ra file
features = np.array(features).astype('float32')
np.save("features.npy", features)
np.save("image_paths.npy", np.array(valid_paths))

print(f"\n---> XONG BƯỚC 1! Đã trích xuất thành công {len(features)} vector đặc trưng!")