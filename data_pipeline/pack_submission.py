"""
AIC 2026 Batch Submission Auto-Packer & Validator CLI.
Scans, validates, and zips submission/ into submission.zip at D:\code-c-a-Long.
"""

import os
import sys
import re
import csv
import zipfile
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def validate_and_pack_submission(project_root: str = "D:\\code-c-a-Long", zip_name: str = "submission.zip"):
    root = Path(project_root)
    sub_dir = root / "submission"
    
    print("=" * 65)
    print("  AIC 2026 SUBMISSION PACKAGE VALIDATOR & ZIP AUTO-PACKER")
    print("=" * 65)
    
    if not sub_dir.exists():
        sub_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[WARN] 'submission/' not found. Created: {sub_dir}")
        print("[INFO] Export query-X.csv files to this directory, then re-run.")
        return False
        
    csv_files = sorted(list(sub_dir.glob("*.csv")))
    
    if not csv_files:
        print(f"\n[ERROR] No CSV files found in {sub_dir}.")
        print("[INFO] Save at least one query CSV (e.g. query-1-kis.csv) to submission/.")
        return False
        
    print(f"\n[INFO] Found {len(csv_files)} CSV files in 'submission/':\n")
    
    total_valid = 0
    total_warnings = 0
    
    for f in csv_files:
        fname = f.name
        warnings = []
        errors = []
        
        try:
            content = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append("Encoding is not valid UTF-8.")
            content = f.read_text(encoding="utf-8", errors="ignore")
            
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        
        # 1. Row count check
        if len(lines) > 100:
            warnings.append(f"Has {len(lines)} rows (exceeds 100-row limit; only first 100 will be used).")
            lines = lines[:100]
        elif len(lines) == 0:
            errors.append("File is empty.")
            
        # 2. Header check
        if lines and any(h in lines[0].lower() for h in ["video", "frame", "answer", "mediaitem"]):
            warnings.append("Header row detected and removed.")
            lines = lines[1:]
            
        # 3. Check each row
        clean_lines = []
        for row_idx, row in enumerate(lines, 1):
            parts = [p.strip() for p in row.split(",")]
            
            # Check video name
            vname = parts[0]
            if vname.lower().endswith(".mp4"):
                vname = re.sub(r'\.mp4$', '', vname, flags=re.IGNORECASE)
                warnings.append(f"Row {row_idx}: Removed '.mp4' suffix from video name.")
                parts[0] = vname
                
            # Check KIS
            if "kis" in fname.lower():
                if len(parts) < 2:
                    errors.append(f"Row {row_idx}: KIS format error — missing frame_id (<video>,<frame_id>).")
                elif not parts[1].isdigit():
                    errors.append(f"Row {row_idx}: Frame ID '{parts[1]}' is not an integer.")
            # Check QA
            elif "qa" in fname.lower():
                if len(parts) < 3:
                    warnings.append(f"Row {row_idx}: Missing Q&A answer field (defaulting to '0').")
                else:
                    ans = ",".join(parts[2:]).strip()
                    if (ans.startswith('"') and ans.endswith('"')) or (ans.startswith("'") and ans.endswith("'")):
                        ans = ans[1:-1].strip()
                    if len(ans) > 100:
                        warnings.append(f"Row {row_idx}: Answer exceeds 100 chars (truncated).")
                        ans = ans[:100]
                    ans = ans.replace('"', '""')
                    parts = [parts[0], parts[1], f'"{ans}"']
            # Check TRAKE
            elif "trake" in fname.lower():
                if len(parts) < 2:
                    errors.append(f"Row {row_idx}: TRAKE format error — need <video>,<frame_1>,<frame_2>...")
                else:
                    f_nums = []
                    for p in parts[1:]:
                        if p.isdigit():
                            f_nums.append(int(p))
                        else:
                            warnings.append(f"Row {row_idx}: Skipping invalid frame '{p}'.")
                    if f_nums:
                        f_nums = sorted(list(set(f_nums)))
                        parts = [parts[0]] + [str(x) for x in f_nums]
                    else:
                        errors.append(f"Row {row_idx}: No valid frame_ids for TRAKE event.")
                    
            clean_lines.append(",".join(parts))
            
        # Rewrite cleaned content
        f.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")
        
        status = "[OK]" if not errors else "[ERROR]"
        print(f"  {status} [{fname}] -> {len(clean_lines)} valid rows")
        if warnings:
            for w in warnings[:3]:
                print(f"     [WARN] {w}")
            total_warnings += len(warnings)
        if errors:
            for e in errors:
                print(f"     [ERROR] {e}")
        else:
            total_valid += 1
            
    print("-" * 65)
    
    # Pack into zip
    zip_path = root / zip_name
    print(f"\n[INFO] Packing files into: {zip_path}...")
    
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for csv_file in csv_files:
            # Arc name must be submission/<filename.csv>
            arcname = f"submission/{csv_file.name}"
            zf.write(csv_file, arcname=arcname)
            
    zip_size_kb = zip_path.stat().st_size / 1024.0
    print(f"[OK] submission.zip created ({zip_size_kb:.1f} KB): {zip_path}")
    print(f"[OK] Archive root: submission/ — {total_valid} CSV files.")
    print("=" * 65)
    return True

if __name__ == "__main__":
    validate_and_pack_submission()
