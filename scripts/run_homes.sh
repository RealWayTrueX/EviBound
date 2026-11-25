#!/usr/bin/env bash
# Exploratory scale study: the refusal ladder in homes of three sizes (docs/scale_study.md).
#
#   bash scripts/run_homes.sh <homespilot_NAME|homes_NAME> <gpu[,gpu...]|scripted> [tag] [seeds]
#
# NAME is the planner: qwen25 (the planner of the confirmatory studies) or qwen3 (the second model).
# homespilot_NAME  the 12 pilot tasks of each home, seed 11: does the model answer in the form the
#                  parser expects, and do its answers fit into the token limit? Only the form is used.
# homes_NAME       the 120 tasks of each home, five conditions, three seeds. Refuses to start unless
#                  a pilot of the same planner has passed its check.
#
# The homes run one after another (S, M, L). With several graphics cards the tasks of a home are
# split into as many parts, one per card; the number of parts is fixed when a run first starts.
# "scripted" in place of a card runs a deterministic planner without a model. Raw traces stay in
# $EVIBOUND_DATA/runs/v3_1_<stage>_<tag>/. Nothing here has confirmatory weight.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/v3_1_env.sh"

stage="${1:?usage: run_homes.sh <homespilot_NAME|homes_NAME> <gpu[,gpu...]|scripted> [tag] [seeds]}"
gpu="${2:?gpu index, several separated by commas, or 'scripted'}"
tag="${3:-}"
case "$stage" in
  homespilot_*) name="${stage#homespilot_}"; split=pilot; seeds="${4:-11}" ;;
  homes_*)      name="${stage#homes_}"; split=main; seeds="${4:-11 22 33}" ;;
  *) echo "unknown stage $stage" >&2; exit 2 ;;
esac
case "$name" in
  qwen25) model="${V31_MODEL_PATH:-$EVIBOUND_DATA/models/Qwen2.5-7B-Instruct}"; model_args=() ;;
  qwen3)  model="${V31_MODEL_PATH:-/mnt/HDD-8T-0/huggingface/models/Qwen3-8B}"; model_args=(--direct-answer) ;;
  *) echo "unknown planner $name" >&2; exit 2 ;;
esac
token_limit=384
run_root="${V31_RUN_ROOT:-$EVIBOUND_DATA/runs}"
run_dir="$run_root/v3_1_${stage}${tag:+_$tag}"
mkdir -p "$run_dir"
if [ -e "$run_dir/COMPLETE" ]; then echo "$run_dir is already complete"; exit 0; fi
python scripts/freeze_v3_1_prereg.py --verify            # the engine uses the frozen planner; it must be unchanged
python scripts/generate_scenarios_homes.py --check       # the task files are the ones the generator writes
if [ "$split" = main ]; then
  passed=no
  for check in "$run_root"/v3_1_homespilot_"${name}"_*/model_check.json; do
    [ -e "$check" ] && python -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))["ok"] else 1)' "$check" && passed=yes
  done
  if [ "$passed" != yes ]; then echo "no pilot of $name has passed its check; not starting $stage" >&2; exit 3; fi
fi
echo $$ > "$run_dir/RUNNING"
trap 'rm -f "$run_dir/RUNNING"' EXIT
git rev-parse HEAD > "$run_dir/code_commit.txt" 2>/dev/null || true

IFS=, read -ra gpus <<< "$gpu"
parts="$(cat "$run_dir/parts.txt" 2>/dev/null || echo "${#gpus[@]}")"
echo "$parts" > "$run_dir/parts.txt"
if [ "${gpus[0]}" = scripted ]; then planner_args=(--planner scripted:careful)
else
  planner_args=(--planner local --model "$model" "${model_args[@]}")
  [ -e "$run_dir/model_files.json" ] || nice -n 19 python scripts/v3_1_model_check.py --files "$model" \
    --output "$run_dir/model_files.json" > /dev/null 2>> "$run_dir/analysis.log" &
fi

pids=()
for slot in "${!gpus[@]}"; do
  (
    [ "${gpus[$slot]}" = scripted ] || export CUDA_VISIBLE_DEVICES="${gpus[$slot]}"
    log="$run_dir/run.log"; [ "$slot" -gt 0 ] && log="$run_dir/run_p$((slot + 1)).log"
    for home in S M L; do
      for part in $(seq 1 "$parts"); do
        [ $(( (part - 1) % ${#gpus[@]} )) -eq "$slot" ] || continue
        # shellcheck disable=SC2086
        python scripts/run_experiment_homes.py --home "$home" --split "$split" --part "$part/$parts" --seeds $seeds \
          --batch-size 8 --max-new-tokens "$token_limit" "${planner_args[@]}" \
          --output "$run_dir/episodes_${home}_p$part.jsonl" >> "$log" 2>&1
      done
    done
  ) &
  pids+=($!)
done
failed=0
for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
if [ "$failed" -ne 0 ]; then echo "a part of $stage stopped without completing; start it again to resume" >&2; exit 1; fi
wait   # the file hashes

inputs=()
for home in S M L; do for part in $(seq 1 "$parts"); do inputs+=("$run_dir/episodes_${home}_p$part.jsonl"); done; done
python scripts/v3_1_model_check.py --plumbing "${inputs[@]}" --token-limit "$token_limit" \
  --output "$run_dir/model_check.json" >> "$run_dir/analysis.log" 2>&1
python scripts/analyze_homes.py --input "${inputs[@]}" --output "$run_dir/analysis" \
  --fingerprints "$run_dir/fingerprints.json.gz" >> "$run_dir/analysis.log" 2>&1 || status=$?
sha256sum "${inputs[@]}" > "$run_dir/episodes.sha256"
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$run_dir/COMPLETE"
exit "${status:-0}"
