# ============================================================
# Dockerfile cho Backend — Video Retrieval System
# Build: docker build -t aic-backend ./backend
# Run:   docker run -p 8000:8000 --env-file .env aic-backend
# ============================================================

FROM python:3.10-slim

# Cài hệ thống dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements trước để tận dụng Docker layer cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY main.py .
COPY config.json .

# Port expose
EXPOSE 8000

# Healthcheck — gọi /health endpoint mỗi 30 giây
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Khởi động server
CMD ["uvicorn", "main.py:app", "--host", "0.0.0.0", "--port", "8000"]
