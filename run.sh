#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

AUTH_MODE="${OFFICETOOL_OPENAI_AUTH_MODE:-${OFFCIATOOL_OPENAI_AUTH_MODE:-auto}}"
APP_MODULE="${OFFICETOOL_APP_MODULE:-app.kernel_robot_main:app}"
APP_PORT="${OFFICETOOL_APP_PORT:-8080}"
CODEX_HOME_DIR="${OFFICETOOL_CODEX_HOME:-${OFFCIATOOL_CODEX_HOME:-${CODEX_HOME:-$HOME/.codex}}}"
CODEX_AUTH_FILE="${OFFICETOOL_CODEX_AUTH_FILE:-${OFFCIATOOL_CODEX_AUTH_FILE:-$CODEX_HOME_DIR/auth.json}}"

has_api_key=false
has_codex_auth=false

if [ -n "${OPENAI_API_KEY:-}" ]; then
  has_api_key=true
fi

if [ -f "$CODEX_AUTH_FILE" ]; then
  has_codex_auth=true
fi

case "$AUTH_MODE" in
  api_key)
    if [ "$has_api_key" = false ]; then
      echo "WARN: OFFICETOOL_OPENAI_AUTH_MODE=api_key but OPENAI_API_KEY is not set." >&2
    fi
    ;;
  codex_auth)
    if [ "$has_codex_auth" = false ]; then
      echo "WARN: OFFICETOOL_OPENAI_AUTH_MODE=codex_auth but Codex auth file was not found at $CODEX_AUTH_FILE." >&2
    fi
    ;;
  *)
    if [ "$has_api_key" = false ] && [ "$has_codex_auth" = false ]; then
      echo "WARN: Neither OPENAI_API_KEY nor Codex auth.json is configured. /api/chat requests will fail until one auth mode is available." >&2
    fi
    ;;
esac

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  exec "$ROOT_DIR/.venv/bin/python" -m uvicorn "$APP_MODULE" --host 0.0.0.0 --port "$APP_PORT" --reload
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 -m uvicorn "$APP_MODULE" --host 0.0.0.0 --port "$APP_PORT" --reload
fi

exec uvicorn "$APP_MODULE" --host 0.0.0.0 --port "$APP_PORT" --reload
