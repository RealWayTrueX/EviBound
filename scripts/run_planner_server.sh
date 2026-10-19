#!/usr/bin/env bash
# Serve the frozen planner (and the experiment traces) for the Mac demo, inside tmux.
# Usage:  tmux new-session -d -s evibound_planner 'bash scripts/run_planner_server.sh <gpu-index|cpu|none> [port]'
#         tmux capture-pane -p -t evibound_planner | tail -5     # readiness and the token file path
# "none" serves only /runs (trace replay) without loading the model.
# The bearer token is created once in $EVIBOUND_DATA/planner_token; copy its content to the Mac:
#         export EVIBOUND_API_TOKEN=<content>; python3 demo/serve.py
set -euo pipefail
source /home/yanke/EviBound/scripts/env.sh
gpu="${1:?usage: run_planner_server.sh <gpu-index|cpu|none> [port]}"
port="${2:-8000}"
token_file="$EVIBOUND_DATA/planner_token"
if [[ ! -s "$token_file" ]]; then
  (umask 077 && openssl rand -hex 24 > "$token_file")
fi
export EVIBOUND_API_TOKEN
EVIBOUND_API_TOKEN="$(cat "$token_file")"
echo "token file: $token_file"
case "$gpu" in
  none) device_args=(--no-model) ;;
  cpu)  device_args=(--device cpu --cpu-threads "${CPU_THREADS:-12}") ;;
  *)    export CUDA_VISIBLE_DEVICES="$gpu"; device_args=(--device cuda) ;;
esac
# Listen on the Tailscale address only (reachable just from Xin's own devices), unless
# PLANNER_HOST overrides it; without Tailscale fall back to every interface (token still required).
host="${PLANNER_HOST:-$(tailscale ip -4 2>/dev/null | head -1)}"
host="${host:-0.0.0.0}"
mkdir -p "$EVIBOUND_DATA/runs"
echo "listening on http://$host:$port  (Mac: base_url http://$host:$port/v1)"
exec python scripts/serve_planner.py --host "$host" --port "$port" --runs-dir "$EVIBOUND_DATA/runs" \
  "${device_args[@]}" 2>&1 | tee -a "$EVIBOUND_DATA/runs/planner_server.log"
