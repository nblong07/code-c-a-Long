@echo off
chcp 65001 > NUL
echo ============================================================
echo   Video Retrieval System — Windows 11 Setup Script
echo ============================================================
echo.

echo [1/5] Checking Python environment...
if exist "%USERPROFILE%\miniconda3\envs\video_ai\python.exe" (
    set "PYTHON_CMD=%USERPROFILE%\miniconda3\envs\video_ai\python.exe"
    echo   - Found Anaconda/Miniconda environment: video_ai
) else (
    set "PYTHON_CMD=python"
)

%PYTHON_CMD% --version
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

echo.
echo [2/5] Creating Backend environment file (.env)...
if not exist "backend\.env" (
    copy "backend\.env.example" "backend\.env"
    echo   - Created backend\.env from template.
) else (
    echo   - backend\.env already exists.
)

echo.
echo [3/5] Creating Frontend config file (config.js)...
if not exist "frontend\src\scripts\config.js" (
    if exist "frontend\src\scripts\config.example.js" (
        copy "frontend\src\scripts\config.example.js" "frontend\src\scripts\config.js"
        echo   - Created frontend\src\scripts\config.js from template.
    )
) else (
    echo   - frontend\src\scripts\config.js already exists.
)

echo.
echo [4/5] Creating data & Milvus volume directories...
if not exist "data-keyframes\maps" mkdir "data-keyframes\maps"
if not exist "database\volumes\etcd" mkdir "database\volumes\etcd"
if not exist "database\volumes\minio" mkdir "database\volumes\minio"
if not exist "database\volumes\milvus" mkdir "database\volumes\milvus"
echo   - Storage directories prepared.

echo.
echo [5/5] Installing Python Dependencies...
%PYTHON_CMD% -m pip install -r backend\requirements.txt

echo.
echo ============================================================
echo   [SUCCESS] Setup completed!
echo ============================================================
echo Next steps:
echo 1. Start Milvus: cd database ^&^& docker compose up -d
echo 2. Extract keyframes: python database/get_keyframes.py --input-folder path/to/videos
echo 3. Index into Milvus: python database/upload_database.py --root ./data-keyframes --build-index
echo 4. Run Backend: python backend/main.py
echo.
pause
