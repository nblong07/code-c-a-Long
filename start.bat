@echo off
chcp 65001 > NUL
echo ============================================================
echo   Starting Video Retrieval System...
echo ============================================================

echo [1/3] Starting Milvus Vector Database (Docker)...
cd /d "%~dp0database"
docker compose up -d
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker Container failed to start! Make sure Docker Desktop is running.
    pause
    exit /b 1
)

echo.
echo [2/3] Opening Frontend Interface in Browser...
start "" "%~dp0frontend\index.html"

echo.
echo [3/3] Starting Backend Service (FastAPI + CUDA)...
cd /d "%~dp0"

if exist "%USERPROFILE%\miniconda3\envs\video_ai\python.exe" (
    "%USERPROFILE%\miniconda3\envs\video_ai\python.exe" backend/main.py
) else if exist "C:\ProgramData\miniconda3\envs\video_ai\python.exe" (
    "C:\ProgramData\miniconda3\envs\video_ai\python.exe" backend/main.py
) else (
    python backend/main.py
)

pause

