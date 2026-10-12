#!/usr/bin/env bash
# Unattended v3 launcher: waits for a free GPU, runs the dev stage, then waits
# for the v3 preregistration freeze (human sign-off) and a free GPU again
# before the holdout stage. Pure bash polling; no agent or API involved.
#
# A GPU counts as free only after it has had >= MIN_FREE_MIB free memory on
# every check for STABLE_CHECKS consecutive checks, so short gaps between
# another project's stages are not grabbed.
#
# Start:  tmux new-session -d -s evibound_v3 'bash scripts/wait_gpu_then_run_v3.sh'
# Status: cat /mnt/HDD-8T-0/evibound_yanke/runs/week11_v3_watcher.status
set -uo pipefail
cd /home/yanke/EviBound
DATA=/mnt/HDD-8T-0/evibound_yanke
LOG="$DATA/runs/week11_v3_watcher.log"
STATUS="$DATA/runs/week11_v3_watcher.status"
DEV_DIR="$DATA/runs/week11_v3_dev"
HOLDOUT_DIR="$DATA/runs/week11_v3_holdout"
MIN_FREE_MIB="${MIN_FREE_MIB:-20480}"
STABLE_CHECKS="${STABLE_CHECKS:-10}"
INTERVAL_S="${INTERVAL_S:-60}"
mkdir -p "$DATA/runs"

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }
status() { echo "$(date -Is) $*" > "$STATUS"; log "STATUS $*"; }

# Prints the index of a GPU that stayed free for STABLE_CHECKS checks.
wait_for_gpu() {
  declare -A streak=()
  while true; do
    while IFS=', ' read -r idx free; do
      if [[ "$free" -ge "$MIN_FREE_MIB" ]]; then
        streak[$idx]=$(( ${streak[$idx]:-0} + 1 ))
      else
        streak[$idx]=0
      fi
      if [[ "${streak[$idx]}" -ge "$STABLE_CHECKS" ]]; then
        echo "$idx"
        return 0
      fi
    done < <(nvidia-smi --query-gpu=index,memory.free --format=csv,noheader,nounits)
    sleep "$INTERVAL_S"
  done
}

run_stage() {
  local name="$1" script="$2" dir="$3"
  local attempt
  for attempt in 1 2 3; do
    status "$name: waiting for a GPU with ${MIN_FREE_MIB} MiB free for ${STABLE_CHECKS} checks (attempt $attempt)"
    local gpu
    gpu="$(wait_for_gpu)"
    status "$name: running on GPU $gpu"
    if bash "$script" "$gpu" "$dir" >> "$LOG" 2>&1; then
      status "$name: complete ($(cat "$dir/COMPLETE"))"
      return 0
    fi
    log "$name: attempt $attempt failed; see $dir/run.log (completed episodes are resumed)"
    sleep 300
  done
  status "$name: FAILED after 3 attempts; see $LOG and $dir/run.log"
  return 1
}

log "watcher started (pid $$)"
# A dev run started elsewhere (e.g. on CPU) holds $DEV_DIR/RUNNING; wait for it instead of competing.
while [[ -f "$DEV_DIR/RUNNING" ]] && kill -0 "$(cat "$DEV_DIR/RUNNING")" 2>/dev/null; do
  status "dev: another dev run is in progress (pid $(cat "$DEV_DIR/RUNNING")); waiting"
  sleep 600
done
if [[ ! -f "$DEV_DIR/COMPLETE" ]]; then
  run_stage dev scripts/run_v3_dev.sh "$DEV_DIR" || exit 1
fi

until python3 scripts/freeze_v3_prereg.py --verify >> "$LOG" 2>&1; do
  status "holdout: dev done; waiting for review sign-off and scripts/freeze_v3_prereg.py --approve"
  sleep 600
done

if [[ ! -f "$HOLDOUT_DIR/COMPLETE" ]]; then
  run_stage holdout scripts/run_v3_holdout.sh "$HOLDOUT_DIR" || exit 1
fi
status "all v3 stages complete; reports in $DEV_DIR/analysis and $HOLDOUT_DIR/analysis"
