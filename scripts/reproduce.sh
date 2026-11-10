#!/usr/bin/env bash
# One-command reproduction for the course deliverable (research contract, section VII).
#
#   bash scripts/reproduce.sh                      # level 1: no GPU, no traces (about one minute)
#   bash scripts/reproduce.sh --traces DIR         # level 2: also recompute every published number from raw traces
#   bash scripts/reproduce.sh --traces DIR --gpu 0 --model PATH
#                                                  # level 3: also re-run the v2 formal-test seed-11 matrix
#                                                  #          (432 episodes) with the frozen runner and compare
#   options for level 3:  --seeds "11 22 33"       # re-run every v2 seed (the full 1,296-episode matrix)
#                         --v3-seeds "11"          # also re-run the v3 holdout for these seeds (2,376 episodes each)
#
# Level 1 checks the code and the evidence chain: unit tests, corpus checkers, all protocol
# freezes, and the full v3 pipeline (runner -> guard -> oracle -> analysis) with a scripted planner.
# Level 2 needs the raw-trace bundle (see docs/reproduction.md). DIR is laid out like the data
# disk's runs/ folder: week8_v2_main_test/seed_{11,22,33}.jsonl, week11_v3_holdout/episodes.jsonl.
# Level 3 needs one 24 GB GPU and the pinned Qwen2.5-7B-Instruct weights.
#
# On the original machine everything is found from one variable:
#   EVIBOUND_DATA=/path/to/data-disk bash scripts/reproduce.sh --gpu 0
# (uses $EVIBOUND_DATA/runs, $EVIBOUND_DATA/models/Qwen2.5-7B-Instruct and
#  $EVIBOUND_DATA/envs/runtime/bin/python when they exist).
#
# Nothing here writes into the frozen run directories; outputs go to --out
# (default: a new timestamped folder under $EVIBOUND_DATA/runs or ./reproduction_out).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TRACES="" GPU="" MODEL="${EVIBOUND_MODEL:-}" OUT="" PY="${EVIBOUND_PYTHON:-}" SEEDS="11" V3_SEEDS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --traces) TRACES="$2"; shift 2 ;;
    --gpu)    GPU="$2"; shift 2 ;;
    --model)  MODEL="$2"; shift 2 ;;
    --out)    OUT="$2"; shift 2 ;;
    --seeds)  SEEDS="$2"; shift 2 ;;
    --v3-seeds) V3_SEEDS="$2"; shift 2 ;;
    -h|--help) sed -n 2,24p "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
  esac
done

if [ -n "${EVIBOUND_DATA:-}" ]; then
  [ -z "$TRACES" ] && [ -d "$EVIBOUND_DATA/runs" ] && TRACES="$EVIBOUND_DATA/runs"
  [ -z "$MODEL" ] && [ -d "$EVIBOUND_DATA/models/Qwen2.5-7B-Instruct" ] && MODEL="$EVIBOUND_DATA/models/Qwen2.5-7B-Instruct"
  [ -z "$PY" ] && [ -x "$EVIBOUND_DATA/envs/runtime/bin/python" ] && PY="$EVIBOUND_DATA/envs/runtime/bin/python"
fi
PY="${PY:-python3}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
if [ -z "$OUT" ]; then
  if [ -n "${EVIBOUND_DATA:-}" ] && [ -d "$EVIBOUND_DATA/runs" ]; then OUT="$EVIBOUND_DATA/runs/reproduction_$stamp"
  else OUT="$ROOT/reproduction_out/$stamp"; fi
fi
mkdir -p "$OUT"
export PYTHONPATH="$ROOT/src:$ROOT${PYTHONPATH:+:$PYTHONPATH}"
LOG="$OUT/reproduce.log"
step() { printf '\n== %s\n' "$*" | tee -a "$LOG"; }
run()  { "$@" 2>&1 | tee -a "$LOG"; return "${PIPESTATUS[0]}"; }

step "Reproduction started $stamp (commit $(git rev-parse --short HEAD 2>/dev/null || echo unknown), python: $($PY --version 2>&1))"
status=0

step "1/6 Unit tests"
run "$PY" -m unittest discover -s tests -p 'test_*.py' || status=1

step "2/6 Corpus checkers (v2: 56 tasks, v3: 84 tasks)"
run "$PY" scripts/check_scenarios_v2.py || status=1
run "$PY" scripts/check_scenarios_v3.py || status=1

step "3/6 Protocol freezes (v1, v2 pilot, v2 formal test, v3)"
run "$PY" scripts/verify_freezes.py || status=1

step "4/6 Full v3 pipeline with a scripted planner (illustrates the pipeline; not evidence about the model)"
run "$PY" scripts/run_v3_local.py --split dev --planner scripted:hasty --seeds 11 --output "$OUT/pipeline_scripted" || status=1

if [ -n "$TRACES" ]; then
  step "5/6 Recompute published results from raw traces in $TRACES"
  run "$PY" scripts/verify_published_results.py --traces "$TRACES" --output "$OUT/published_results_check.json" || status=1
  run "$PY" scripts/contract_outcomes.py --traces "$TRACES" --output "$OUT/contract_outcomes.json" || status=1
else
  step "5/6 Skipped: no raw traces (pass --traces DIR to recompute the published numbers)"
fi

if [ -n "$GPU" ]; then
  [ -n "$MODEL" ] || { echo "--gpu needs --model PATH (or EVIBOUND_MODEL / EVIBOUND_DATA)" | tee -a "$LOG"; exit 2; }
  step "6/6 Re-run the v2 formal test on GPU $GPU with the frozen runner (seeds: $SEEDS; 432 episodes each)"
  originals=() reruns=()
  for seed in $SEEDS; do
    # One invocation per seed, as in the original run (scripts/run_v2_main_test.sh).
    CUDA_VISIBLE_DEVICES="$GPU" run "$PY" scripts/run_experiment.py --corpus v2 --split test \
        --conditions B0 B1 B2 M M_no_freshness Always_refresh --variants clean perturbed boundary \
        --seeds "$seed" --batch-size 8 --model "$MODEL" --output "$OUT/seed_${seed}.jsonl" || status=1
    reruns+=("$OUT/seed_${seed}.jsonl")
    [ -n "$TRACES" ] && [ -f "$TRACES/week8_v2_main_test/seed_${seed}.jsonl" ] \
      && originals+=("$TRACES/week8_v2_main_test/seed_${seed}.jsonl")
  done
  if [ "${#originals[@]}" -eq "${#reruns[@]}" ]; then
    run "$PY" scripts/compare_runs.py --study v2 --original "${originals[@]}" --rerun "${reruns[@]}" \
        --output "$OUT/reproduction_report.json" || status=1
  else
    echo "no original traces to compare with; the re-run is in $OUT" | tee -a "$LOG"
  fi
  if [ -n "$V3_SEEDS" ]; then
    step "6b Re-run the v3 holdout on GPU $GPU with the frozen runner (seeds: $V3_SEEDS; 2,376 episodes each)"
    # shellcheck disable=SC2086
    CUDA_VISIBLE_DEVICES="$GPU" run "$PY" scripts/run_experiment_v3.py --split holdout --seeds $V3_SEEDS \
        --batch-size 8 --model "$MODEL" --output "$OUT/v3_holdout_rerun.jsonl" || status=1
    if [ -n "$TRACES" ] && [ -f "$TRACES/week11_v3_holdout/episodes.jsonl" ]; then
      run "$PY" scripts/compare_runs.py --study v3 --original "$TRACES/week11_v3_holdout/episodes.jsonl" \
          --rerun "$OUT/v3_holdout_rerun.jsonl" --output "$OUT/reproduction_report_v3.json" || status=1
    fi
  fi
else
  step "6/6 Skipped: no GPU re-run (pass --gpu N --model PATH)"
fi

step "Finished with status $status. Outputs: $OUT"
exit "$status"
