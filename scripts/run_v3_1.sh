#!/usr/bin/env bash
# One v3.1 run: experiment, analysis, fingerprints.
#
#   bash scripts/run_v3_1.sh <dev_v3|dev|holdout> <gpu-index|scripted> [tag] [seeds]
#
# dev_v3   the v3 corpus (holdout and dev) as development data
# dev      the development split of the v3.1 corpus
# holdout  the confirmatory run; refuses to start unless the v3.1 preregistration freeze
#          exists and every frozen hash still matches
# "scripted" in place of a GPU index runs a deterministic persona without a model, to
# exercise the whole pipeline. Raw traces stay in $EVIBOUND_DATA/runs/v3_1_<stage>[_tag]/.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/v3_1_env.sh"
stage="${1:?usage: run_v3_1.sh <dev_v3|dev|holdout> <gpu-index|scripted> [tag] [seeds]}"
gpu="${2:?gpu index or 'scripted'}"
tag="${3:-}"
seeds="${4:-11 22 33}"
case "$stage" in
  dev_v3)  corpus=v3;   splits="holdout dev" ;;
  dev)     corpus=v3_1; splits="dev" ;;
  holdout) corpus=v3_1; splits="holdout"; python scripts/freeze_v3_1_prereg.py --verify ;;
  *) echo "unknown stage $stage" >&2; exit 2 ;;
esac
run_dir="${V31_RUN_ROOT:-$EVIBOUND_DATA/runs}/v3_1_${stage}${tag:+_$tag}"
mkdir -p "$run_dir"
if [ -e "$run_dir/COMPLETE" ]; then echo "$run_dir is already complete"; exit 0; fi
echo $$ > "$run_dir/RUNNING"
trap 'rm -f "$run_dir/RUNNING"' EXIT
if [ "$gpu" = scripted ]; then planner_args=(--planner scripted:hasty)
else export CUDA_VISIBLE_DEVICES="$gpu"; planner_args=(--planner local); fi
[ "$stage" = holdout ] && cp artifacts/v3_1_prereg_freeze.json "$run_dir/prereg_freeze.json"
git rev-parse HEAD > "$run_dir/code_commit.txt" 2>/dev/null || true
inputs=()
for split in $splits; do
  # shellcheck disable=SC2086
  python scripts/run_experiment_v3_1.py --corpus "$corpus" --split "$split" --seeds $seeds \
    --batch-size 8 "${planner_args[@]}" --output "$run_dir/episodes_$split.jsonl" >> "$run_dir/run.log" 2>&1
  inputs+=("$run_dir/episodes_$split.jsonl")
done
python scripts/analyze_v3_1.py --stage "$stage" --input "${inputs[@]}" --output "$run_dir/analysis" \
  --fingerprints "$run_dir/fingerprints.json.gz" > "$run_dir/analysis.log" 2>&1 || status=$?
python scripts/v3_1_examples.py --input "${inputs[@]}" --output "$run_dir/examples.json" >> "$run_dir/analysis.log" 2>&1 || true
sha256sum "${inputs[@]}" > "$run_dir/episodes.sha256"
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$run_dir/COMPLETE"
exit "${status:-0}"
