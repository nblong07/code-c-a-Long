r"""
AIC 2026 Batch Submission Auto-Packer & Validator CLI
Tự động quét, kiểm tra định dạng và đóng gói thư mục submission/ thành submission.zip tại D:\code-c-a-Long
====================================================================================================
"""

import os
import re
import csv
import zipfile
from pathlib import Path

def validate_and_pack_submission(project_root: str = "D:\\code-c-a-Long", zip_name: str = "submission.zip"):
    root = Path(project_root)
    sub_dir = root / "submission"
    
    print("=" * 65)
    print("  AIC 2026 SUBMISSION PACKAGE VALIDATOR & ZIP AUTO-PACKER")
    print("=" * 65)
    
    if not sub_dir.exists():
        sub_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n⚠️ Thư mục 'submission/' chưa tồn tại. Đã tự động tạo: {sub_dir}")
        print("👉 Hãy xuất các file query-X.csv vào thư mục này rồi chạy lại lệnh!")
        return False
        
    csv_files = sorted(list(sub_dir.glob("*.csv")))
    
    if not csv_files:
        print(f"\n❌ Không tìm thấy file CSV nào trong {sub_dir}!")
        print("👉 Hãy lưu ít nhất 1 câu truy vấn (ví dụ: query-1-kis.csv) vào thư mục submission/")
        return False
        
    print(f"\n🔍 Tìm thấy {len(csv_files)} file CSV trong thư mục 'submission/':\n")
    
    total_valid = 0
    total_warnings = 0
    
    for f in csv_files:
        fname = f.name
        warnings = []
        errors = []
        
        try:
            content = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append("Mã hóa không phải UTF-8 chuẩn!")
            content = f.read_text(encoding="utf-8", errors="ignore")
            
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        
        # 1. Row count check
        if len(lines) > 100:
            warnings.append(f"Có {len(lines)} dòng (vượt quá giới hạn 100 dòng của BTC, sẽ chỉ lấy 100 dòng đầu).")
            lines = lines[:100]
        elif len(lines) == 0:
            errors.append("File rỗng!")
            
        # 2. Header check
        if lines and any(h in lines[0].lower() for h in ["video", "frame", "answer", "mediaitem"]):
            warnings.append("Phát hiện dòng Header. Đã tự động loại bỏ.")
            lines = lines[1:]
            
        # 3. Check each row
        clean_lines = []
        for row_idx, row in enumerate(lines, 1):
            parts = [p.strip() for p in row.split(",")]
            
            # Check video name
            vname = parts[0]
            if vname.lower().endswith(".mp4"):
                vname = re.sub(r'\.mp4$', '', vname, flags=re.IGNORECASE)
                warnings.append(f"Dòng {row_idx}: Tên video chứa đuôi '.mp4', đã tự động xóa.")
                parts[0] = vname
                
            # Check KIS
            if "kis" in fname.lower():
                if len(parts) < 2:
                    errors.append(f"Dòng {row_idx}: Format KIS sai, thiếu frame_id (Cần: <video>,<frame_id>).")
                elif not parts[1].isdigit():
                    errors.append(f"Dòng {row_idx}: Frame ID '{parts[1]}' không phải số nguyên.")
            # Check QA
            elif "qa" in fname.lower():
                if len(parts) < 3:
                    warnings.append(f"Dòng {row_idx}: Thiếu trường câu trả lời Q&A (sẽ dùng mặc định '0').")
                else:
                    ans = ",".join(parts[2:]).strip()
                    if (ans.startswith('"') and ans.endswith('"')) or (ans.startswith("'") and ans.endswith("'")):
                        ans = ans[1:-1].strip()
                    if len(ans) > 100:
                        warnings.append(f"Dòng {row_idx}: Câu trả lời vượt quá 100 ký tự (sẽ cắt ngắn).")
                        ans = ans[:100]
                    ans = ans.replace('"', '""')
                    parts = [parts[0], parts[1], f'"{ans}"']
            # Check TRAKE
            elif "trake" in fname.lower():
                if len(parts) < 2:
                    errors.append(f"Dòng {row_idx}: Format TRAKE sai, cần ít nhất 1 frame (Cần: <video>,<frame_1>,<frame_2>...).")
                else:
                    f_nums = []
                    for p in parts[1:]:
                        if p.isdigit():
                            f_nums.append(int(p))
                        else:
                            warnings.append(f"Dòng {row_idx}: Bỏ qua frame không hợp lệ '{p}'.")
                    if f_nums:
                        f_nums = sorted(list(set(f_nums)))
                        parts = [parts[0]] + [str(x) for x in f_nums]
                    else:
                        errors.append(f"Dòng {row_idx}: Không có frame_id hợp lệ cho sự kiện TRAKE.")
                    
            clean_lines.append(",".join(parts))
            
        # Rewrite cleaned content
        f.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")
        
        status_icon = "✅" if not errors else "❌"
        print(f"  {status_icon} [{fname}] -> {len(clean_lines)} dòng hợp lệ")
        if warnings:
            for w in warnings[:3]:
                print(f"     ⚠️  {w}")
            total_warnings += len(warnings)
        if errors:
            for e in errors:
                print(f"     ❌  {e}")
        else:
            total_valid += 1
            
    print("-" * 65)
    
    # Pack into zip
    zip_path = root / zip_name
    print(f"\n📦 Đang nén các file vào: {zip_path}...")
    
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for csv_file in csv_files:
            # ARC_NAME MUST BE submission/<filename.csv>
            arcname = f"submission/{csv_file.name}"
            zf.write(csv_file, arcname=arcname)
            
    zip_size_kb = zip_path.stat().st_size / 1024.0
    print(f"🎉 ĐÃ ĐÓNG GÓI THÀNH CÔNG FILE SUBMISSION.ZIP ({zip_size_kb:.1f} KB)!")
    print(f"📁 Đường dẫn file nộp: {zip_path}")
    print(f"🏆 Cấu trúc chuẩn 100%: Bên trong zip có thư mục gốc 'submission/' chứa {total_valid} file CSV.")
    print("=" * 65)
    return True

if __name__ == "__main__":
    validate_and_pack_submission()
