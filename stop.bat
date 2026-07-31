@echo off
chcp 65001 > NUL
echo ============================================================
echo   Stopping Video Retrieval System (Backend ^& Milvus DB)...
echo ============================================================

echo [1/2] Stopping Python Backend...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>NUL
)

echo [2/2] Stopping Milvus Vector Database (Docker)...
cd /d "%~dp0database"
docker compose down

echo.
echo ============================================================
echo   [SUCCESS] System stopped successfully!
echo ============================================================
pause
