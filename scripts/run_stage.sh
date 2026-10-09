#!/usr/bin/env bash
set -euo pipefail
source /home/yanke/EviBound/scripts/env.sh
stage="${1:-dev}"
run_dir="$EVIBOUND_DATA/runs/$stage"
mkdir -p "$run_dir"
if [[ "$stage" == dev ]]; then
    CUDA_VISIBLE_DEVICES=1 python scripts/run_experiment.py --split dev --seeds 11 --output "$run_dir/episodes.jsonl" 2>&1 | tee "$run_dir/worker.log"
    python scripts/analyze.py --input "$run_dir/episodes.jsonl" --output "reports/$stage"
elif [[ "$stage" == pilot ]]; then
    CUDA_VISIBLE_DEVICES=1 python scripts/run_experiment.py --split pilot --seeds 11 --output "$run_dir/episodes.jsonl" 2>&1 | tee "$run_dir/worker.log"
    python scripts/analyze.py --input "$run_dir/episodes.jsonl" --output "reports/$stage"
elif [[ "$stage" == test ]]; then
    CUDA_VISIBLE_DEVICES=0 python scripts/run_experiment.py --split test --worker 0 --workers 2 --output "$run_dir/worker0.jsonl" > "$run_dir/worker0.log" 2>&1 &
    pid0=$!
    CUDA_VISIBLE_DEVICES=1 python scripts/run_experiment.py --split test --worker 1 --workers 2 --output "$run_dir/worker1.jsonl" > "$run_dir/worker1.log" 2>&1 &
    pid1=$!
    status0=0; status1=0
    wait "$pid0" || status0=$?
    wait "$pid1" || status1=$?
    if [[ "$status0" != 0 || "$status1" != 0 ]]; then
        echo "Worker failures: gpu0=$status0 gpu1=$status1"
        exit 1
    fi
    python scripts/analyze.py --input "$run_dir/worker0.jsonl" "$run_dir/worker1.jsonl" --output "reports/$stage"
else
    echo "Unknown stage: $stage" >&2
    exit 2
fi
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$run_dir/COMPLETE"
