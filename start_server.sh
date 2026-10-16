#!/usr/bin/env bash
# Khởi động server Lumi AI cho buổi thuyết trình
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
if [ -z "${PYTHON_BIN:-}" ]; then
    if [ -x "$DIR/.venv/bin/python" ]; then
        PYTHON_BIN="$DIR/.venv/bin/python"
    elif [ -x "$DIR/../demo_env/bin/python" ]; then
        PYTHON_BIN="$DIR/../demo_env/bin/python"
    else
        PYTHON_BIN="python3"
    fi
fi

if "$PYTHON_BIN" - "$PORT" <<'PY'
import sys,urllib.request,json
try:
    with urllib.request.urlopen('http://127.0.0.1:'+sys.argv[1]+'/api/health',timeout=2) as response:
        data=json.load(response)
        sys.exit(0 if data.get('status')=='ok' and 'model_ready' in data else 1)
except (OSError,ValueError):
    sys.exit(1)
PY
then
    echo "⚡ Server Lumi AI đang chạy sẵn tại: http://localhost:$PORT"
else
    echo "🚀 Đang khởi động Lumi AI Server trên cổng $PORT..."
    # One model process; reload/watchers would load extra copies during edits.
    exec "$PYTHON_BIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --workers 1
fi
