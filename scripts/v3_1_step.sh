#!/usr/bin/env bash
# Server-side dispatcher for the v3.1 runs.
#
# The experiment machine is driven through a terminal that accepts one stored command.
# That command updates this checkout to the work branch and calls this script, which
# carries out the steps listed in scripts/v3_1_step.txt (one per line, '#' comments).
# Small outputs (logs, analysis, fingerprints; never raw traces) are copied to a
# separate results repository and pushed to the branch claude/v3-1-results.
#
# Steps:
#   probe                    GPUs, sessions, disk, Python environment, model folder
#   stop_v4                  stop the two v4 planner servers (owner's decision of 2026-11-24)
#   smoke                    tests and a scripted pipeline run, no GPU
#   conditions <names...>    development runs started after this line use these conditions
#   run <stage> <gpu> <tag> [seeds]   start a run in the background (dev_v3, dev, holdout)
#   status                   progress of every v3.1 run
#   wait <stage> <tag> [minutes]      block until that run is complete (default 20 minutes)
#   publish                  push the small outputs now (always done once more at the end)
#   detach                   as the first step: carry out the remaining steps in the background, so
#                            that they survive the terminal session; pipeline.lock in the steps
#                            folder holds the process id
#
# The stored terminal command, for reference (it does not update the checkout while a
# detached pipeline is running):
#   L=$D/runs/v3_1_steps; cd $D/repro_clone/EviBound && if [ -e $L/pipeline.lock ] &&
#     kill -0 "$(cat $L/pipeline.lock)" 2>/dev/null; then echo BUSY; tail -5 $L/steps.log; else
#     git fetch -q origin claude/v3-1-feedback-ladder && git checkout -q --detach FETCH_HEAD &&
#     bash scripts/v3_1_step.sh; fi
#
# It never touches /home/yanke/EviBound, reads no credential file, and starts a GPU job
# only on a GPU that is idle.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/v3_1_env.sh"
RUNS="$EVIBOUND_DATA/runs"
OUT="$EVIBOUND_DATA/repro_clone/v3_1_results"
LOG_DIR="$RUNS/v3_1_steps"
mkdir -p "$LOG_DIR"
STEP_FILE="$EVIBOUND_ROOT/scripts/v3_1_step.txt"
LOCK="$LOG_DIR/pipeline.lock"
if [ "${1:-}" != --attached ] && grep -v '^ *#' "$STEP_FILE" | grep -v '^ *$' | head -1 | grep -qx 'detach'; then
  if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK")" 2>/dev/null; then
    echo "a detached pipeline is already running (pid $(cat "$LOCK")); not starting another"; exit 1
  fi
  setsid nohup bash "${BASH_SOURCE[0]}" --attached > "$LOG_DIR/detached_$(date -u +%Y%m%dT%H%M%SZ).log" 2>&1 < /dev/null &
  echo $! > "$LOCK"
  echo "detached pipeline started (pid $!) at $(git rev-parse --short HEAD); steps: $(grep -v '^ *#' "$STEP_FILE" | grep -v '^ *$' | tr '\n' ';')"
  echo "progress: $LOG_DIR/steps.log, and the branch claude/v3-1-results"
  exit 0
fi
if [ "${1:-}" = --attached ]; then echo $$ > "$LOCK"; trap 'rm -f "$LOCK"' EXIT; fi
stamp() { date -u +'%Y-%m-%dT%H:%M:%SZ'; }
say() { echo "[$(stamp)] $*"; }

gpu_table() { nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>&1; }
gpu_used() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$1" 2>/dev/null | tr -d ' '; }

step_probe() {
  say "host $(hostname), user $(whoami), checkout $EVIBOUND_ROOT @ $(git rev-parse --short HEAD)"
  echo "GPUs (index, name, used, total, load):"; gpu_table | sed 's/^/  /'
  echo "GPU processes (pid, used MiB, owner, elapsed, name):"
  nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2>/dev/null | while IFS=', ' read -r pid mem; do
    [ -n "$pid" ] && echo "  $pid ${mem}MiB $(ps -o user=,etime=,comm= -p "$pid" 2>/dev/null)"
  done
  echo "tmux sessions:"; tmux list-sessions -F '  #{session_name} (created #{t:session_created})' 2>/dev/null || echo "  none"
  echo "data disk:"; df -h "$EVIBOUND_DATA" | tail -1 | sed 's/^/  /'
  echo "python: $(command -v python) $(python -c 'import sys, torch, transformers; print(sys.version.split()[0], "torch", torch.__version__, "transformers", transformers.__version__)' 2>&1)"
  echo "model folder: $(ls -d "$EVIBOUND_DATA"/models/Qwen2.5-7B-Instruct 2>&1) ($(ls "$EVIBOUND_DATA/models" 2>/dev/null | tr '\n' ' '))"
  echo "v3.1 runs: $(ls -d "$RUNS"/v3_1_* 2>/dev/null | xargs -n1 basename 2>/dev/null | tr '\n' ' ')"
  echo "load: $(uptime | sed 's/.*load average/load average/')"
}

step_stop_v4() {
  for session in evibound_v4_qwen25 evibound_v4_qwen3; do
    if tmux has-session -t "$session" 2>/dev/null; then
      # keep a note of how the session was started, with anything that looks like a secret masked
      tmux list-panes -t "$session" -F "$session started with: #{pane_start_command}" 2>/dev/null \
        | sed -E 's/((token|key|secret|password)[A-Za-z_]*[= ])[^ ]+/\1***/Ig' | tee -a "$LOG_DIR/v4_sessions_before_stop.txt"
      tmux send-keys -t "$session" C-c 2>/dev/null; sleep 4
      tmux kill-session -t "$session" 2>/dev/null
      say "stopped tmux session $session"
    else
      say "tmux session $session is not running"
    fi
  done
  sleep 3; echo "GPUs after stopping:"; gpu_table | sed 's/^/  /'
}

step_smoke() {
  say "unit tests (nice 19)"
  nice -n 19 python -m unittest discover -s tests -p 'test_v3_1*.py' 2>&1 | tail -4
  nice -n 19 python scripts/check_scenarios_v3_1.py 2>&1 | tail -2
  rm -rf "$LOG_DIR/smoke_run"; mkdir -p "$LOG_DIR/smoke_run"
  V31_RUN_ROOT="$LOG_DIR/smoke_run" nice -n 19 bash scripts/run_v3_1.sh dev scripted smoke "11" 2>&1 | tail -2
  say "scripted pipeline: $(cat "$LOG_DIR/smoke_run/v3_1_dev_smoke/analysis.log" 2>/dev/null | head -1 | cut -c1-160)"
}

step_run() {
  local stage="$1" gpu="$2" tag="$3" seeds="${4:-11 22 33}"
  local run_dir="$RUNS/v3_1_${stage}_${tag}"
  if [ -e "$run_dir/COMPLETE" ]; then say "$run_dir already complete"; return 0; fi
  if [ -e "$run_dir/RUNNING" ] && kill -0 "$(cat "$run_dir/RUNNING")" 2>/dev/null; then say "$run_dir is running"; return 0; fi
  if [ "$gpu" != scripted ]; then   # "scripted" runs a persona without a model, for a dry run of the pipeline
    local used tries=0; used="$(gpu_used "$gpu")"
    while { [ -z "$used" ] || [ "$used" -gt 2000 ]; } && [ "$tries" -lt 12 ]; do sleep 5; tries=$((tries + 1)); used="$(gpu_used "$gpu")"; done
    if [ -z "$used" ] || [ "$used" -gt 2000 ]; then say "GPU $gpu is not idle (${used:-?} MiB used); not starting $stage"; return 1; fi
  fi
  mkdir -p "$run_dir"
  setsid nohup bash scripts/run_v3_1.sh "$stage" "$gpu" "$tag" "$seeds" > "$LOG_DIR/run_${stage}_${tag}.log" 2>&1 < /dev/null &
  say "started $stage on GPU $gpu as $run_dir (pid $!)"
}

run_state() {
  local dir="$1" name; name="$(basename "$dir")"
  local lines=0; for f in "$dir"/episodes_*.jsonl; do [ -e "$f" ] && lines=$((lines + $(wc -l < "$f"))); done
  local state=stopped
  [ -e "$dir/RUNNING" ] && kill -0 "$(cat "$dir/RUNNING")" 2>/dev/null && state=running
  [ -e "$dir/COMPLETE" ] && state="complete $(cat "$dir/COMPLETE")"
  echo "  $name: $state, $lines episodes; $(tail -1 "$dir/run.log" 2>/dev/null | cut -c1-140)"
}

step_status() {
  echo "runs:"; for dir in "$RUNS"/v3_1_*_*; do [ -d "$dir" ] && [ "$dir" != "$LOG_DIR" ] && run_state "$dir"; done
  echo "GPUs:"; gpu_table | sed 's/^/  /'
}

step_wait() {
  local dir="$RUNS/v3_1_${1}_${2}" minutes="${3:-20}" waited=0
  while [ ! -e "$dir/COMPLETE" ] && [ "$waited" -lt $((minutes * 60)) ]; do
    if [ ! -e "$dir/RUNNING" ] && [ "$waited" -gt 60 ]; then say "$dir is neither running nor complete"; break; fi
    sleep 20; waited=$((waited + 20))
  done
  run_state "$dir"
  [ -s "$LOG_DIR/run_${1}_${2}.log" ] && { echo "launcher output:"; tail -5 "$LOG_DIR/run_${1}_${2}.log" | cut -c1-200 | sed 's/^/  /'; }
}

publish() {
  mkdir -p "$OUT/server_out"
  if [ ! -d "$OUT/.git" ]; then
    git init -q "$OUT" && git -C "$OUT" checkout -q -b claude/v3-1-results
    git -C "$OUT" remote add origin "$(git -C "$EVIBOUND_ROOT" remote get-url origin)"
  fi
  cp "$LOG_DIR/steps.log" "$OUT/server_out/steps.log" 2>/dev/null
  cp "$LOG_DIR/v4_sessions_before_stop.txt" "$OUT/server_out/" 2>/dev/null
  for dir in "$RUNS"/v3_1_*_*; do
    [ -d "$dir" ] && [ -e "$dir/COMPLETE" ] || continue
    local dest="$OUT/server_out/$(basename "$dir")"; mkdir -p "$dest"
    cp "$dir"/analysis/results.json "$dir"/analysis/summary.md "$dir"/fingerprints.json.gz "$dir"/examples.json \
       "$dir"/episodes.sha256 "$dir"/code_commit.txt "$dir"/COMPLETE "$dir"/*.config.json "$dir"/analysis.log "$dest/" 2>/dev/null
    [ -e "$dir/prereg_freeze.json" ] && cp "$dir/prereg_freeze.json" "$dest/"
  done
  tar -czf "$LOG_DIR/v3_1_server_out.tar.gz" -C "$OUT" server_out 2>/dev/null   # one file, in case it has to be fetched by hand
  git -C "$OUT" add -A >/dev/null 2>&1
  if ! git -C "$OUT" diff --cached --quiet 2>/dev/null; then
    git -C "$OUT" -c user.name=Claude -c user.email=noreply@anthropic.com commit -q -m "v3.1 server output $(stamp)" \
      >/dev/null 2>"$LOG_DIR/commit_error.txt" || say "COMMIT FAILED: $(head -2 "$LOG_DIR/commit_error.txt" | tr '\n' ' ' | cut -c1-160)"
  fi
  if [ -n "${V31_NO_PUSH:-}" ]; then say "push skipped (V31_NO_PUSH)"; return 0; fi
  if timeout 60 git -C "$OUT" push -q -f origin claude/v3-1-results >/dev/null 2>"$LOG_DIR/push_error.txt"; then
    say "published $(git -C "$OUT" rev-parse --short HEAD) to claude/v3-1-results"
  else
    say "PUSH FAILED: $(head -2 "$LOG_DIR/push_error.txt" | tr '\n' ' ' | cut -c1-160)"
  fi
}

{
  echo "===== $(stamp) steps at $(git rev-parse --short HEAD): $(grep -v '^ *#' "$STEP_FILE" | grep -v '^ *$' | tr '\n' ';')"
  mapfile -t STEPS < "$STEP_FILE"
  for line in "${STEPS[@]}"; do
    read -r name a b c d <<< "$line"
    case "$name" in
      ''|'#'*) ;;
      probe) step_probe ;;
      stop_v4) step_stop_v4 ;;
      smoke) step_smoke ;;
      conditions) export V31_CONDITIONS="$a $b $c $d"; say "development conditions: $V31_CONDITIONS" ;;
      run) step_run "$a" "$b" "$c" "${d:-}" ;;
      status) step_status ;;
      wait) step_wait "$a" "$b" "${c:-}" ;;
      publish) publish ;;
      detach) ;;
      *) say "unknown step: $name" ;;
    esac
  done
} 2>&1 | tee -a "$LOG_DIR/steps.log"
publish 2>&1 | tee -a "$LOG_DIR/steps.log"
