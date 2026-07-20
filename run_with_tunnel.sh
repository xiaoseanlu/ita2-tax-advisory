#!/bin/bash
# Tax Advisory (project-air) — run web UI + public tunnel
#
# Default app: web_ui_server.py on port 5000.
# Expert Advisory E2E (baseline / PDF POC):  APP=expert_e2e ./run_with_tunnel.sh  (port 5002 unless PORT is set)
#
# Default: Cloudflare quick tunnel (free, no account). Sometimes api.trycloudflare.com
# returns 500 / "Worker threw exception" — that's Cloudflare, not this app. Retry later
# or use ngrok:
#
#   TUNNEL=ngrok ./run_with_tunnel.sh
#
# Other:
#   PORT=5001 ./run_with_tunnel.sh

set -e
cd "$(dirname "$0")"

APP="${APP:-web_ui}"
if [ "$APP" = "expert_e2e" ] || [ "$APP" = "e2e" ]; then
  export PORT="${PORT:-5002}"
else
  export PORT="${PORT:-5000}"
fi
TUNNEL="${TUNNEL:-cloudflare}"

echo "🚀 Tax Advisory — Flask + tunnel (mode: $TUNNEL, app: $APP, port: $PORT)"
echo "============================================"

if [ "$APP" = "expert_e2e" ] || [ "$APP" = "e2e" ]; then
  echo "Starting expert_advisory_e2e.py on port $PORT..."
  python3 expert_advisory_e2e.py &
else
  echo "Starting web_ui_server.py on port $PORT..."
  python3 web_ui_server.py &
fi
FLASK_PID=$!

for i in {1..30}; do
    if curl -s -o /dev/null "http://127.0.0.1:${PORT}/" 2>/dev/null; then
        break
    fi
    if ! kill -0 "$FLASK_PID" 2>/dev/null; then
        echo "❌ Server process exited unexpectedly."
        exit 1
    fi
    sleep 0.5
done
if ! curl -s -o /dev/null "http://127.0.0.1:${PORT}/" 2>/dev/null; then
    kill "$FLASK_PID" 2>/dev/null || true
    echo "❌ Server did not become ready in time."
    exit 1
fi

echo ""
echo "Local: http://127.0.0.1:${PORT}/"
echo ""

cleanup() {
    echo ""
    echo "Stopping server (PID $FLASK_PID)..."
    kill "$FLASK_PID" 2>/dev/null || true
    wait "$FLASK_PID" 2>/dev/null || true
    exit 0
}
trap cleanup EXIT INT TERM

if [ "$TUNNEL" = "ngrok" ]; then
    if ! command -v ngrok &> /dev/null; then
        echo "❌ ngrok not found. Install: brew install ngrok/ngrok/ngrok"
        echo "   Then: ngrok config add-authtoken <token>  (from https://dashboard.ngrok.com )"
        exit 1
    fi
    echo "📋 ngrok will print a public https URL below."
    echo ""
    ngrok http "$PORT"
elif [ "$TUNNEL" = "localtunnel" ]; then
    if ! command -v lt &> /dev/null; then
        echo "❌ localtunnel not found. Install: npm install -g localtunnel"
        exit 1
    fi
    echo "📋 Public URL from localtunnel:"
    lt --port "$PORT"
else
    if ! command -v cloudflared &> /dev/null; then
        echo "❌ cloudflared not found."
        echo "  brew install cloudflare/cloudflare/cloudflared"
        echo "Or use ngrok:  TUNNEL=ngrok ./run_with_tunnel.sh"
        exit 1
    fi
    echo "Creating Cloudflare quick tunnel..."
    echo "If you see HTML / 'invalid character' / Error 1101: Cloudflare's service failed."
    echo "Retry later or run:  TUNNEL=ngrok ./run_with_tunnel.sh"
    echo ""
    if ! cloudflared tunnel --url "http://127.0.0.1:${PORT}"; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Cloudflare quick tunnel failed (their API returned an error page)."
        echo "Try:"
        echo "  • Wait a few minutes and run this script again"
        echo "  • TUNNEL=ngrok ./run_with_tunnel.sh"
        echo "  • Or in another terminal:  ngrok http $PORT"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        exit 1
    fi
fi
