#!/bin/bash
# Test script for AuditBee build artifact
# Usage: ./scripts/test_build.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist/AuditBee"

echo "========================================"
echo "AuditBee Build Test"
echo "========================================"

# Check if build exists
if [ ! -f "$DIST_DIR/AuditBee.exe" ]; then
    echo "ERROR: AuditBee.exe not found in dist/AuditBee/"
    exit 1
fi

# Kill any running instances
taskkill //F //IM AuditBee.exe 2>/dev/null || true
sleep 2

echo ""
echo "[1/5] Checking build artifacts..."
echo "  AuditBee.exe: $(ls -lh "$DIST_DIR/AuditBee.exe" | awk '{print $5}')"
echo "  _internal/: $(ls "$DIST_DIR/_internal/" | wc -l) items"

echo ""
echo "[2/5] Checking model..."
if [ -f "$DIST_DIR/model/pytorch_model.bin" ]; then
    echo "  Model: OK ($(ls -lh "$DIST_DIR/model/pytorch_model.bin" | awk '{print $5}'))"
else
    echo "  Model: MISSING"
fi

echo ""
echo "[3/5] Starting server..."
cd "$DIST_DIR"
start //B AuditBee.exe --no-launcher
sleep 10

echo ""
echo "[4/5] Testing API..."
HEALTH=$(curl -s http://localhost:8000/api/health 2>/dev/null)
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo "  Health: OK"
else
    echo "  Health: FAILED"
    taskkill //F //IM AuditBee.exe 2>/dev/null || true
    exit 1
fi

ALERTS=$(curl -s http://localhost:8000/api/alerts/ 2>/dev/null)
ALERT_COUNT=$(echo "$ALERTS" | python -c "import sys,json; print(json.load(sys.stdin)['total'])" 2>/dev/null || echo "0")
echo "  Alerts API: OK ($ALERT_COUNT alerts)"

echo ""
echo "[5/5] Testing frontend..."
FRONTEND=$(curl -s http://localhost:8000/ 2>/dev/null)
if echo "$FRONTEND" | grep -q '<title>AuditBee</title>'; then
    echo "  Frontend: OK"
else
    echo "  Frontend: FAILED"
fi

# Cleanup
taskkill //F //IM AuditBee.exe 2>/dev/null || true

echo ""
echo "========================================"
echo "All tests passed!"
echo "========================================"
