/**
 * config.js — File cấu hình đường dẫn cho Frontend
 * ===================================================
 * SAU KHI CLONE VỀ: chỉ cần sửa file này, KHÔNG sửa file nào khác!
 *
 * Cách dùng:
 *   1. Copy file này: cp config.example.js config.js
 *   2. Sửa các giá trị bên dưới cho phù hợp với máy của bạn
 *   3. File config.js đã được .gitignore — không lo bị commit nhầm
 */

// ============================================================
// ĐƯỜNG DẪN ĐẾN KEYFRAME (ảnh .webp)
// Ví dụ nếu serve ảnh qua Nginx/Python HTTP tại cổng 8007:
//   window.KEYFRAME_BASE = 'http://localhost:8007/output-keyframes';
//
// Ví dụ nếu ảnh nằm trên server Linux:
//   window.KEYFRAME_BASE = '/mlcv2/WorkingSpace/Personal/quannh/Project/Project/AIC/get_keyframes/data-batch-2';
//
// Cấu trúc thư mục phải là:
//   <KEYFRAME_BASE>/<video_name>/keyframes/keyframe_<frame_id>.webp
// ============================================================
window.KEYFRAME_BASE = 'http://localhost:8007/output-keyframes';


// ============================================================
// ĐƯỜNG DẪN ĐẾN FILE CSV (ánh xạ frame_id → giây)
// Ví dụ: 'http://localhost:8007/output-keyframes/maps'
//
// Cấu trúc thư mục phải là:
//   <CSV_BASE>/<video_name>.csv
//   hoặc <CSV_BASE>/<video_name>_map.csv
// ============================================================
window.CSV_BASE = 'http://localhost:8007/output-keyframes/maps';


// ============================================================
// ĐƯỜNG DẪN ĐẾN FILE VIDEO (.m3u8 HLS stream)
// Ví dụ nếu serve video qua Nginx:
//   window.VIDEO_BASE = 'http://localhost:8007/videos';
//
// Ví dụ nếu video trên server Linux:
//   window.VIDEO_BASE = '/mlcv2/Datasets/HCMAI24/streaming';
//
// Cấu trúc thư mục phải là:
//   <VIDEO_BASE>/batch1_audio/<video_name>/<video_name>.m3u8
// ============================================================
window.VIDEO_BASE = 'http://localhost:8007/videos';


// ============================================================
// URL CỦA BACKEND API
// Mặc định: http://localhost:8000
// ============================================================
window.BACKEND_URL = 'http://localhost:8000';
window.WS_URL      = 'ws://localhost:8000';
window.API_KEY     = 'aic_challenge_secure_token_2026';
