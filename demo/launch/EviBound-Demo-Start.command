#!/bin/bash
# EviBound demo: one-click start from the Mac (double-click in Finder).
#
#   1. Starts the frozen planner on the UQ GPU server in tmux session
#      "evibound_model_server" (scripts/model_server.py, most-free GPU), unless
#      it already answers on Tailscale.
#   2. Waits until http://100.72.39.67:8000/health answers (model loaded).
#   3. Starts the local demo page (demo/serve.py, port 8765) and opens it.
#
# The server password is asked once per start unless key login is set up
# (docs/remote_planner_setup.md, section 5). Stop everything with
# EviBound-Demo-Stop.command. Overrides: EVIBOUND_GPU_HOST, EVIBOUND_API_BASE,
# EVIBOUND_MAC_REPO, EVIBOUND_MIN_FREE_MIB.
set -u

HOST="${EVIBOUND_GPU_HOST:-yanke@100.72.39.67}"
API="${EVIBOUND_API_BASE:-http://100.72.39.67:8000}"
REPO="${EVIBOUND_MAC_REPO:-$HOME/CyberSercurity/EviBound}"
MIN_FREE_MIB="${EVIBOUND_MIN_FREE_MIB:-19000}"
DEMO_URL="http://127.0.0.1:8765/"
LOG="$HOME/Library/Logs/evibound_demo.log"

say()  { printf '\n== %s\n' "$*"; }
fail() { printf '\n!! %s\n' "$*"; read -r -p "Press Return to close..." _; exit 1; }
up()   { curl -fsS -m 3 "$1" >/dev/null 2>&1; }

[ -f "$REPO/demo/serve.py" ] || fail "demo not found at $REPO (set EVIBOUND_MAC_REPO to your EviBound clone)"
if [ ! -s "$HOME/.config/evibound/planner_token" ] && [ -z "${EVIBOUND_API_TOKEN:-}" ]; then
  say "Note: ~/.config/evibound/planner_token is missing; the page runs, but live model calls will be refused."
fi

if up "$API/health"; then
  say "GPU planner already running at $API"
else
  say "Starting the GPU planner on $HOST (the server password may be asked)"
  ssh -o ConnectTimeout=15 "$HOST" "MIN_FREE_MIB=$MIN_FREE_MIB bash -s" <<'REMOTE' \
    || fail "could not start the planner on the server (Tailscale up? password right? GPU free?)"
set -e
session=evibound_model_server
if tmux has-session -t "$session" 2>/dev/null; then
  echo "tmux session $session already exists; waiting for it"
  exit 0
fi
best=$(nvidia-smi --query-gpu=index,memory.free --format=csv,noheader,nounits | sort -t, -k2 -nr | head -1)
gpu=$(echo "$best" | cut -d, -f1 | tr -d ' ')
free=$(echo "$best" | cut -d, -f2 | tr -d ' ')
echo "most free GPU: $gpu ($free MiB free)"
if [ "${free:-0}" -lt "$MIN_FREE_MIB" ]; then
  echo "no GPU has >= $MIN_FREE_MIB MiB free (experiments running?):"
  nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader
  exit 3
fi
tmux new-session -d -s "$session" \
  "cd /home/yanke/EviBound && source scripts/env.sh && CUDA_VISIBLE_DEVICES=$gpu python scripts/model_server.py --preload 2>&1 | tee -a /mnt/HDD-8T-0/evibound_yanke/runs/model_server.log"
echo "started tmux session $session on GPU $gpu"
REMOTE
  say "Waiting for the model to load (up to 5 minutes)"
  for _ in $(seq 1 100); do
    up "$API/health" && break
    sleep 3
    printf '.'
  done
  up "$API/health" || fail "no answer from $API/health; on the server run: tmux attach -t evibound_model_server"
  say "GPU planner is up"
fi

if up "$DEMO_URL"; then
  say "Demo page already running"
else
  say "Starting the demo page (log: $LOG)"
  cd "$REPO" || fail "cannot open $REPO"
  nohup python3 demo/serve.py >"$LOG" 2>&1 &
  for _ in $(seq 1 30); do
    up "$DEMO_URL" && break
    sleep 1
  done
  up "$DEMO_URL" || fail "demo page did not start; see $LOG"
fi

open "$DEMO_URL"
say "Ready. In the page choose 智能体 → 'UQ Linux GPU 机' and press 检查连接."
say "This window can be closed; stop everything with EviBound-Demo-Stop.command."
