#!/bin/bash
# ============================================================
# setup.sh \u2014 Script thi\u1ebft l\u1eadp m\u00f4i tr\u01b0\u1eddng cho Linux/macOS
# Ch\u1ea1y 1 l\u1ea7n sau khi clone d\u1ef1 \u00e1n:
#   chmod +x setup.sh && ./setup.sh
# ============================================================

set -e  # D\u1eebng ngay khi c\u00f3 l\u1ed7i

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Video Retrieval System \u2014 Team Setup Script${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""

# ---- B\u01b0\u1edbc 1: Ki\u1ec3m tra Python ----
echo -e "${YELLOW}[1/6] Ki\u1ec3m tra Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}L\u1ed7i: Python 3 ch\u01b0a \u0111\u01b0\u1ee3c c\u00e0i. Vui l\u00f2ng c\u00e0i Python 3.9+${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "  \u2713 Python $PYTHON_VERSION"

# ---- B\u01b0\u1edbc 2: Ki\u1ec3m tra Docker ----
echo -e "${YELLOW}[2/6] Ki\u1ec3m tra Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}L\u1ed7i: Docker ch\u01b0a \u0111\u01b0\u1ee3c c\u00e0i.${NC}"
    echo "  H\u01b0\u1edbng d\u1eabn: https://docs.docker.com/engine/install/"
    exit 1
fi
echo "  \u2713 Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

# ---- B\u01b0\u1edbc 3: Thi\u1ebft l\u1eadp m\u00f4i tr\u01b0\u1eddng Python ----
echo -e "${YELLOW}[3/6] Thi\u1ebft l\u1eadp m\u00f4i tr\u01b0\u1eddng Python...${NC}"
if command -v conda &> /dev/null; then
    echo "  Ph\u00e1t hi\u1ec7n Conda \u2014 t\u1ea1o m\u00f4i tr\u01b0\u1eddng 'aic'..."
    conda create -n aic python=3.10 -y 2>/dev/null || echo "  M\u00f4i tr\u01b0\u1eddng 'aic' \u0111\u00e3 t\u1ed3n t\u1ea1i, b\u1ecf qua"
    echo "  \u2713 M\u00f4i tr\u01b0\u1eddng conda 'aic' s\u1eb5n s\u00e0ng"
    echo "  \u2192 K\u00edch ho\u1ea1t: conda activate aic"
    PYTHON_CMD="conda run -n aic python"
    PIP_CMD="conda run -n aic pip"
else
    echo "  S\u1eed d\u1ee5ng venv..."
    python3 -m venv venv
    source venv/bin/activate
    echo "  \u2713 venv t\u1ea1o xong"
    echo "  \u2192 K\u00edch ho\u1ea1t: source venv/bin/activate"
    PYTHON_CMD="python"
    PIP_CMD="pip"
fi

# ---- B\u01b0\u1edbc 4: C\u00e0i th\u01b0 vi\u1ec7n ----
echo -e "${YELLOW}[4/6] C\u00e0i \u0111\u1eb7t th\u01b0 vi\u1ec7n Python...${NC}"
$PIP_CMD install --upgrade pip -q
$PIP_CMD install -r backend/requirements.txt -q
echo "  \u2713 Backend dependencies \u0111\u00e3 c\u00e0i"
$PIP_CMD install torch torchvision torchaudio opencv-python pillow tqdm -q 2>/dev/null || \
$PIP_CMD install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu -q
echo "  \u2713 Database pipeline dependencies \u0111\u00e3 c\u00e0i"

# ---- B\u01b0\u1edbc 5: T\u1ea1o file config ----
echo -e "${YELLOW}[5/6] T\u1ea1o file config...${NC}"

# Backend .env
if [ ! -f "backend/.env" ]; then
    cp backend/.env.example backend/.env
    echo "  \u2713 T\u1ea1o backend/.env t\u1eeb .env.example"
    echo -e "  ${YELLOW}\u26a0 H\u00e3y s\u1eeda backend/.env cho ph\u00f9 h\u1ee3p m\u00e1y c\u1ee7a b\u1ea1n!${NC}"
else
    echo "  backend/.env \u0111\u00e3 t\u1ed3n t\u1ea1i, b\u1ecf qua"
fi

# Frontend config.js
if [ ! -f "frontend/src/scripts/config.js" ]; then
    cp frontend/src/scripts/config.example.js frontend/src/scripts/config.js
    echo "  \u2713 T\u1ea1o frontend/src/scripts/config.js t\u1eeb config.example.js"
    echo -e "  ${YELLOW}\u26a0 H\u00e3y s\u1eeda config.js \u0111\u01b0\u1eddng d\u1eabn cho ph\u00f9 h\u1ee3p m\u00e1y c\u1ee7a b\u1ea1n!${NC}"
else
    echo "  frontend/src/scripts/config.js \u0111\u00e3 t\u1ed3n t\u1ea1i, b\u1ecf qua"
fi

# ---- B\u01b0\u1edbc 6: T\u1ea1o th\u01b0 m\u1ee5c output ----
echo -e "${YELLOW}[6/6] T\u1ea1o th\u01b0 m\u1ee5c...${NC}"
mkdir -p output-keyframes/maps
mkdir -p database/volumes/{etcd,minio,milvus}
echo "  \u2713 output-keyframes/ s\u1eb5n s\u00e0ng"
echo "  \u2713 database/volumes/ s\u1eb5n s\u00e0ng"

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  \u2713 Setup ho\u00e0n t\u1ea5t!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "  B\u01b0\u1edbc ti\u1ebfp theo:"
echo "  1. S\u1eeda backend/.env \u2014 \u0111i\u1ec1u ch\u1ec9nh CLIP model v\u00e0 Milvus settings"
echo "  2. S\u1eeda frontend/src/scripts/config.js \u2014 \u0111i\u1ec1u ch\u1ec9nh \u0111\u01b0\u1eddng d\u1eabn keyframe"
echo "  3. Ch\u1ea1y: docker compose up -d   \u2190 kh\u1edfi \u0111\u1ed9ng to\u00e0n b\u1ed9 h\u1ec7 th\u1ed1ng"
echo ""
