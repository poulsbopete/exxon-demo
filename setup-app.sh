#!/usr/bin/env bash
# =============================================================================
# Shared App Setup — installs the Elastic Launch Demo FastAPI app and starts
# it as the "Elastic" tab. Called by each challenge's setup-shell script.
# Only runs the full install on the first challenge; subsequent challenges
# check if the app is already running and skip the heavy install.
# =============================================================================
set -euo pipefail

APP_DIR="/opt/exxon-demo"
APP_PORT=80
LOG_FILE="/tmp/exxon-demo.log"
LOCK_FILE="/tmp/exxon-demo-installed.lock"

info()  { echo "[SETUP] $*"; }
ok()    { echo "[OK]    $*"; }
warn()  { echo "[WARN]  $*"; }

# ── Already installed? ────────────────────────────────────────────────────────
if [[ -f "${LOCK_FILE}" ]]; then
    info "App already installed — checking if running..."
    if pgrep -f "uvicorn app.main:app" > /dev/null 2>&1; then
        ok "Elastic demo app already running on port ${APP_PORT}"
        exit 0
    fi
    info "App installed but not running — restarting..."
    cd "${APP_DIR}" && sudo nohup python3 -m uvicorn app.main:app \
        --host 0.0.0.0 --port "${APP_PORT}" > "${LOG_FILE}" 2>&1 &
    sleep 3
    ok "App restarted"
    exit 0
fi

# ── First-time install ────────────────────────────────────────────────────────
info "Installing Python dependencies..."
apt-get update -qq 2>/dev/null || true
apt-get install -y -qq python3-pip python3-venv curl jq 2>/dev/null || true

# Copy app from Instruqt workspace (mounted at /root by default)
info "Setting up app directory at ${APP_DIR}..."
mkdir -p "${APP_DIR}"

# The repo is checked out to /root by Instruqt — copy it over
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "${REPO_ROOT}/app"            "${APP_DIR}/"
cp -r "${REPO_ROOT}/log_generators" "${APP_DIR}/"
cp -r "${REPO_ROOT}/elastic_config" "${APP_DIR}/"
cp -r "${REPO_ROOT}/scenarios"      "${APP_DIR}/"
cp    "${REPO_ROOT}/requirements.txt" "${APP_DIR}/"

# Create .env — ACTIVE_SCENARIO=exxon, no real Elastic creds needed yet
# (the app's selector UI will capture them when the user pastes in their keys)
cat > "${APP_DIR}/.env" << 'ENVEOF'
ACTIVE_SCENARIO=exxon
APP_PORT=80
APP_HOST=0.0.0.0
ENVEOF

# Install Python packages
info "Installing Python packages (this takes ~30s)..."
pip3 install -q -r "${APP_DIR}/requirements.txt"

# Create data directory for SQLite store
mkdir -p "${APP_DIR}/data"

# ── Start the app ─────────────────────────────────────────────────────────────
info "Starting Elastic demo app on port ${APP_PORT}..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

cd "${APP_DIR}"
sudo nohup python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${APP_PORT}" > "${LOG_FILE}" 2>&1 &

# Wait for the app to be healthy
MAX_WAIT=30
for i in $(seq 1 ${MAX_WAIT}); do
    if curl -sf "http://localhost:${APP_PORT}/health" > /dev/null 2>&1; then
        ok "Elastic demo app is live at http://localhost:${APP_PORT}"
        touch "${LOCK_FILE}"
        exit 0
    fi
    sleep 1
done

warn "App did not respond within ${MAX_WAIT}s. Check ${LOG_FILE}"
exit 0   # Don't fail the challenge setup — the app may still be starting
