#!/bin/bash
# scripts/setup.sh — One-time setup script

set -e

echo "=========================================="
echo " Document Reading Services — Setup"
echo "=========================================="

# Install system dependencies
echo "[1/4] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-mar \
    poppler-utils \
    libgl1-mesa-glx \
    libglib2.0-0

# Python packages
echo "[2/4] Installing Python packages..."
pip install -r requirements.txt

# Create directories
echo "[3/4] Creating required directories..."
mkdir -p uploads outputs logs

# Copy env template
echo "[4/4] Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  ✅ .env file created — EDIT IT and add your GEMINI_API_KEY"
else
    echo "  ℹ️  .env already exists"
fi

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "  1. Add GEMINI_API_KEY to .env"
echo "  2. Run: uvicorn app.main:app --reload"
echo "  3. Visit: http://localhost:8000/docs"
echo "=========================================="
