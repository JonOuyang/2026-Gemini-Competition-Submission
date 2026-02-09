#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd python3
require_cmd npm

# Verify Python >= 3.11 (required by browser-use)
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
  echo "[setup] ERROR: Python >= 3.11 required (found $PY_VERSION)." >&2
  echo "[setup] Create a conda env:  conda create -n clovis python=3.11 && conda activate clovis" >&2
  exit 1
fi
echo "[setup] Using Python $PY_VERSION"

cd "$ROOT_DIR"

if [ ! -f "$ROOT_DIR/.env" ]; then
  echo "[setup] Creating .env with placeholder keys..."
  cat <<'ENV_EOF' > "$ROOT_DIR/.env"
GEMINI_API_KEY="YOUR_API_KEY"

ELEVENLABS_URL="YOUR_API_KEY"
ELEVENLABS_API_KEY="YOUR_API_KEY"
ENV_EOF
fi

echo "[setup] Installing Python dependencies..."
python3 -m pip install -r requirements.txt

echo "[setup] Installing Playwright browsers..."
python3 -m playwright install chromium

echo "[setup] Clearing Python bytecode cache..."
find "$ROOT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "[setup] Installing UI dependencies..."
cd "$ROOT_DIR/ui"
npm install

echo "[setup] Installing Gemini CLI dependencies and building..."
cd "$ROOT_DIR/agents/cua_cli/gemini-cli"
npm install
npm run build

echo "[setup] Done. Activate your env and run:  python app.py"
