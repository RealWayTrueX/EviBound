#!/usr/bin/env bash
# Confirmatory v3 holdout run. Refuses to start unless the preregistration
# freeze exists and every frozen hash still matches.
# Usage: run_v3_holdout.sh <gpu-index> [run-dir]
set -euo pipefail
source /home/yanke/EviBound/scripts/env.sh
gpu="$1"
run_dir="${2:-$EVIBOUND_DATA/runs/week11_v3_holdout}"
python scripts/freeze_v3_prereg.py --verify
mkdir -p "$run_dir"
cp artifacts/week11_v3_prereg_freeze.json "$run_dir/prereg_freeze.json"
CUDA_VISIBLE_DEVICES="$gpu" python scripts/run_experiment_v3.py \
  --split holdout --seeds 11 22 33 --batch-size 8 \
  --output "$run_dir/episodes.jsonl" > "$run_dir/run.log" 2>&1
test "$(wc -l < "$run_dir/episodes.jsonl")" -eq $((72 * 3 * 8 * 3))
python scripts/analyze_v3.py --stage holdout --input "$run_dir/episodes.jsonl" --output "$run_dir/analysis"
sha256sum "$run_dir/episodes.jsonl" > "$run_dir/episodes.sha256"
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$run_dir/COMPLETE"
