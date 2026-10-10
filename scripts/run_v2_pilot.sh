#!/usr/bin/env bash
set -euo pipefail
source /home/yanke/EviBound/scripts/env.sh

run_dir="${1:-$EVIBOUND_DATA/runs/week8_v2_pilot}"
mkdir -p "$run_dir"

run_seed() {
  local seed="$1"
  local gpu="$2"
  CUDA_VISIBLE_DEVICES="$gpu" python scripts/run_experiment.py \
    --corpus v2 \
    --split pilot \
    --conditions B0 B1 B2 M M_no_freshness Always_refresh \
    --variants clean perturbed boundary \
    --seeds "$seed" \
    --batch-size 8 \
    --output "$run_dir/seed_${seed}.jsonl" \
    > "$run_dir/seed_${seed}.log" 2>&1
}

run_seed 11 0 &
pid11=$!
run_seed 22 1 &
pid22=$!
status11=0
status22=0
wait "$pid11" || status11=$?
wait "$pid22" || status22=$?
if [[ "$status11" != 0 || "$status22" != 0 ]]; then
  echo "Pilot worker failure: seed11=$status11 seed22=$status22" >&2
  exit 1
fi

run_seed 33 0

python scripts/analyze.py \
  --input "$run_dir/seed_11.jsonl" "$run_dir/seed_22.jsonl" "$run_dir/seed_33.jsonl" \
  --output "$run_dir/analysis" \
  --bootstrap-seed 20260923 \
  --bootstrap-resamples 10000

test "$(cat "$run_dir"/seed_*.jsonl | wc -l)" -eq 864
sha256sum "$run_dir"/seed_*.jsonl > "$run_dir/episodes.sha256"
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$run_dir/COMPLETE"
