#!/usr/bin/env bash
# Exploratory v3 dev run (allowed before the v3 preregistration freeze).
# Usage: run_v3_dev.sh <gpu-index|cpu> [run-dir]
set -euo pipefail
source /home/yanke/EviBound/scripts/env.sh
gpu="$1"
run_dir="${2:-$EVIBOUND_DATA/runs/week11_v3_dev}"
mkdir -p "$run_dir"
echo $$ > "$run_dir/RUNNING"
trap 'rm -f "$run_dir/RUNNING"' EXIT
if [[ "$gpu" == cpu ]]; then
  device_args=(--device cpu --cpu-threads "${CPU_THREADS:-12}")
else
  export CUDA_VISIBLE_DEVICES="$gpu"
  device_args=(--device cuda)
fi
python scripts/run_experiment_v3.py \
  --split dev --seeds 11 22 33 --batch-size 8 "${device_args[@]}" \
  --output "$run_dir/episodes.jsonl" > "$run_dir/run.log" 2>&1
test "$(wc -l < "$run_dir/episodes.jsonl")" -eq $((12 * 3 * 11 * 3))
python scripts/analyze_v3.py --stage dev --input "$run_dir/episodes.jsonl" --output "$run_dir/analysis"
sha256sum "$run_dir/episodes.jsonl" > "$run_dir/episodes.sha256"
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$run_dir/COMPLETE"
