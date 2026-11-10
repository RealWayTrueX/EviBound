#!/usr/bin/env bash
# Run one command on a GPU that nobody else is using, without ever sharing a GPU.
#
#   bash scripts/run_when_gpu_idle.sh STATUS_FILE COMMAND...
#
# The command is started with EVIBOUND_GPU set to the chosen GPU index, only when
# that GPU has had at most MAX_USED_MIB of memory in use on STABLE_CHECKS consecutive
# checks (default: 10 checks, one a minute). Other jobs are never preempted, and a
# GPU that another job merely left room on is not used.
#
# While the command runs, the GPU is watched: if another process starts using it,
# the command is stopped at once so that the other job is not disturbed.
#
# Hard limits: the whole script ends within DEADLINE_S seconds of its start, and
# the command gets at most JOB_MAX_S seconds. Every child process is stopped on exit.
#
# Environment: MAX_USED_MIB (1500), STABLE_CHECKS (10), INTERVAL_S (60),
#              DEADLINE_S (20400 = 5 h 40 min), JOB_MAX_S (7200), MIN_JOB_S (1200).
set -uo pipefail

STATUS_FILE="${1:?usage: run_when_gpu_idle.sh STATUS_FILE COMMAND...}"; shift
[ $# -gt 0 ] || { echo "no command given" >&2; exit 2; }
MAX_USED_MIB="${MAX_USED_MIB:-1500}"
STABLE_CHECKS="${STABLE_CHECKS:-10}"
INTERVAL_S="${INTERVAL_S:-60}"
DEADLINE_S="${DEADLINE_S:-20400}"
JOB_MAX_S="${JOB_MAX_S:-7200}"
MIN_JOB_S="${MIN_JOB_S:-1200}"
START="$(date +%s)"
JOB_PID=""

status() { echo "$(date -Is) $*" | tee -a "$STATUS_FILE"; }
left()   { echo $(( DEADLINE_S - ($(date +%s) - START) )); }
stop_job() {
  if [ -n "$JOB_PID" ] && kill -0 "$JOB_PID" 2>/dev/null; then
    kill -TERM -- "-$JOB_PID" 2>/dev/null
    sleep 5
    kill -KILL -- "-$JOB_PID" 2>/dev/null
  fi
}
trap 'stop_job' EXIT
trap 'status "interrupted"; exit 130' INT TERM

# Memory used on GPU $1 by processes outside our job's process group.
foreign_mib() {
  local uuid total=0 pid mib
  uuid="$(nvidia-smi -i "$1" --query-gpu=uuid --format=csv,noheader)"
  while IFS=', ' read -r gpu_uuid pid mib; do
    [ "$gpu_uuid" = "$uuid" ] || continue
    if [ -n "$JOB_PID" ] && [ "$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')" = "$JOB_PID" ]; then continue; fi
    total=$(( total + mib ))
  done < <(nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv,noheader,nounits)
  echo "$total"
}

status "waiting for an idle GPU (<= ${MAX_USED_MIB} MiB used for ${STABLE_CHECKS} checks); deadline in ${DEADLINE_S}s"
declare -A streak=()
gpu=""
while [ -z "$gpu" ]; do
  if [ "$(left)" -lt "$MIN_JOB_S" ]; then
    status "gave up: no GPU became idle in time; nothing was run"
    exit 3
  fi
  while IFS=', ' read -r idx used; do
    if [ "$used" -le "$MAX_USED_MIB" ]; then streak[$idx]=$(( ${streak[$idx]:-0} + 1 )); else streak[$idx]=0; fi
    if [ "${streak[$idx]}" -ge "$STABLE_CHECKS" ]; then gpu="$idx"; break; fi
  done < <(nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits)
  [ -n "$gpu" ] || sleep "$INTERVAL_S"
done

budget="$(left)"; [ "$budget" -gt "$JOB_MAX_S" ] && budget="$JOB_MAX_S"
status "GPU $gpu is idle; starting the command with a ${budget}s limit"
EVIBOUND_GPU="$gpu" setsid timeout "$budget" "$@" &
JOB_PID=$!
while kill -0 "$JOB_PID" 2>/dev/null; do
  sleep 10
  other="$(foreign_mib "$gpu")"
  if [ "$other" -gt "$MAX_USED_MIB" ]; then
    status "another job started on GPU $gpu (${other} MiB); stopping our command to stay out of its way"
    stop_job
    wait "$JOB_PID" 2>/dev/null
    status "yielded"
    exit 4
  fi
done
wait "$JOB_PID"; code=$?
JOB_PID=""
status "command finished with exit code $code after $(( $(date +%s) - START ))s"
exit "$code"
