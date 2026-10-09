#!/usr/bin/env bash
set -euo pipefail
source /home/yanke/EviBound/scripts/env.sh
stamp=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="$EVIBOUND_DATA/runs/reproduce_$stamp"
mkdir -p "$run_dir"
CUDA_VISIBLE_DEVICES="${EVIBOUND_GPU:-1}" python scripts/run_experiment.py --split test --seeds 11 \
    --task-ids test_reading_00 test_bright_work_00 \
    --conditions B0 B2 M M_no_freshness Always_refresh \
    --output "$run_dir/episodes.jsonl"
python scripts/analyze.py --input "$run_dir/episodes.jsonl" --output "$run_dir/analysis"
echo "Subset complete: $run_dir"
