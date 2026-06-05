#!/bin/bash
# Launch the Stock Research dashboard — HARDENED for private use.
#
# Security model:
#  * Binds ONLY to the Tailscale interface (100.x) so the app is invisible on
#    your home Wi-Fi / LAN. If Tailscale isn't up yet, it falls back to
#    localhost-only (127.0.0.1) — it NEVER binds to 0.0.0.0 (all interfaces).
#  * Optional password gate: put your password in deploy/app_password.txt and
#    every visitor must enter it.
#  * Streamlit's XSRF + CORS protections are left ON (secure defaults).
set -e

APP_DIR="$HOME/.claude/skills/stock-research"
cd "$APP_DIR"

# First-run safety: build the venv if it's missing (e.g. fresh Mac mini).
if [ ! -x ".venv/bin/streamlit" ]; then
  echo "[run_server] .venv not found — creating it and installing deps…"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi

# Optional password: if deploy/app_password.txt exists, require it in the app.
PW_FILE="$APP_DIR/deploy/app_password.txt"
if [ -f "$PW_FILE" ]; then
  export STOCK_RESEARCH_PASSWORD="$(tr -d '\r\n' < "$PW_FILE")"
  echo "[run_server] password protection: ON"
else
  echo "[run_server] password protection: OFF (create deploy/app_password.txt to enable)"
fi

# Find the Tailscale IP (100.64.0.0/10). Wait up to ~90s for Tailscale at boot.
# Fall back to localhost-only — we deliberately never expose on the LAN.
BIND="127.0.0.1"
for _ in $(seq 1 20); do
  IP="$(ifconfig 2>/dev/null | awk '/inet 100\./{print $2; exit}')"
  if [ -n "$IP" ]; then
    BIND="$IP"
    break
  fi
  sleep 2
done
echo "[run_server] binding to $BIND:8501"

exec .venv/bin/streamlit run app.py \
  --server.address "$BIND" \
  --server.port 8501 \
  --server.headless true \
  --browser.gatherUsageStats false
