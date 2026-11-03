#!/bin/bash
# EviBound demo: one-click stop from the Mac (double-click in Finder).
# Stops the GPU planner (tmux session "evibound_model_server") on the UQ server
# so the GPU is free for experiments, then stops the local demo page.
# The server password may be asked once unless key login is set up.
set -u
HOST="${EVIBOUND_GPU_HOST:-yanke@100.72.39.67}"

printf '\n== Stopping the GPU planner on %s\n' "$HOST"
ssh -o ConnectTimeout=15 "$HOST" 'tmux kill-session -t evibound_model_server 2>/dev/null && echo "planner stopped" || echo "planner was not running"; nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader' \
  || printf '!! could not reach the server; the planner may still be running\n'

stopped=0
for pid in $(lsof -ti tcp:8765 -sTCP:LISTEN 2>/dev/null); do
  if ps -o command= -p "$pid" | grep -q 'demo/serve.py'; then
    kill "$pid" && stopped=1
  fi
done
if [ "$stopped" = 1 ]; then printf '\n== Demo page stopped\n'; else printf '\n== Demo page was not running\n'; fi
read -r -p "Done. Press Return to close..." _
