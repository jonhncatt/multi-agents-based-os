#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

export OFFICETOOL_APP_PROFILE="${OFFICETOOL_APP_PROFILE:-role_agent_lab}"
export OFFICETOOL_APP_MODULE="${OFFICETOOL_APP_MODULE:-app.role_agent_lab_main:app}"
export OFFICETOOL_APP_PORT="${OFFICETOOL_APP_PORT:-8081}"

exec ./run.sh
