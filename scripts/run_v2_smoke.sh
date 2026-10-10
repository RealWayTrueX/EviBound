#!/usr/bin/env bash
set -euo pipefail
source /home/yanke/EviBound/scripts/env.sh

run_dir="${1:-$EVIBOUND_DATA/runs/week8_v2_smoke_dev_reading_00}"
mkdir -p "$run_dir"

CUDA_VISIBLE_DEVICES="${EVIBOUND_GPU:-0}" python scripts/run_experiment.py \
  --corpus v2 \
  --split dev \
  --task-ids dev_reading_00 \
  --conditions B0 B1 B2 M M_no_freshness Always_refresh \
  --variants clean perturbed boundary \
  --seeds 11 \
  --batch-size 8 \
  --output "$run_dir/episodes.jsonl" \
  2>&1 | tee "$run_dir/worker.log"

python scripts/analyze.py \
  --input "$run_dir/episodes.jsonl" \
  --output "$run_dir/analysis" \
  --bootstrap-seed 20260923 \
  --bootstrap-resamples 10000

test "$(wc -l < "$run_dir/episodes.jsonl")" -eq 18
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$run_dir/COMPLETE"
