#!/bin/bash
# Quick build script for AuditBee
# Usage: ./scripts/quick_build.sh [--no-model]

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "========================================"
echo "AuditBee Quick Build"
echo "========================================"

# Kill any running AuditBee processes
taskkill //F //IM AuditBee.exe 2>/dev/null || true
sleep 1

echo ""
echo "[1/4] Building frontend..."
cd frontend
npm run build
cd ..

echo ""
echo "[2/4] Copying frontend static files..."
rm -rf backend/static
cp -r frontend/build backend/static

echo ""
echo "[3/4] Running PyInstaller..."
pyinstaller scripts/build.spec --noconfirm

echo ""
echo "[4/4] Copying embedding model..."
if [[ "$1" != "--no-model" ]]; then
    if [ -d "model" ]; then
        cp -r model dist/AuditBee/model
        echo "  Model copied."
    else
        echo "  WARNING: model/ directory not found."
    fi
else
    echo "  Skipped (--no-model flag)."
fi

echo ""
echo "========================================"
echo "Build complete!"
echo "Output: dist/AuditBee/"
echo "========================================"
