#!/usr/bin/env bash
# Script tiện ích 1-click khởi chạy Shopee MUSE với đầy đủ 2.000.000 sản phẩm và Cloudflare Tunnel (100% Free)
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "🚀 [1/3] Kiểm tra Backend Shopee MUSE..."
if ! curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo "  -> Đang khởi động Uvicorn Backend (2 triệu sản phẩm, model MUSE PyTorch)..."
    ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 > /tmp/shopee_muse_backend.log 2>&1 &
    sleep 3
fi

if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo "  ✅ Backend Uvicorn đang chạy tốt tại http://127.0.0.1:8000"
else
    echo "  ❌ Không thể kết nối Backend. Vui lòng kiểm tra log: /tmp/shopee_muse_backend.log"
    exit 1
fi

echo "🌐 [2/3] Kiểm tra Cloudflare Tunnel..."
CLOUDFLARED="/home/midea/.local/bin/cloudflared"
if [ ! -x "$CLOUDFLARED" ]; then
    CLOUDFLARED="$(which cloudflared || true)"
fi

if [ -z "$CLOUDFLARED" ] || [ ! -x "$CLOUDFLARED" ]; then
    echo "  -> Tải binary cloudflared..."
    mkdir -p /home/midea/.local/bin
    curl -sL -o /home/midea/.local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
    chmod +x /home/midea/.local/bin/cloudflared
    CLOUDFLARED="/home/midea/.local/bin/cloudflared"
fi

echo "🎉 [3/3] Đang mở đường hầm HTTPS ra Internet..."
echo "=========================================================="
echo " Nhấn Ctrl+C bất cứ lúc nào để dừng đường hầm."
echo "=========================================================="
"$CLOUDFLARED" tunnel --url http://127.0.0.1:8000
