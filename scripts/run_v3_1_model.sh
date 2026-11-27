#!/usr/bin/env bash
# Exploratory arm of v3.1: the same tasks and conditions with a second local planner model.
#
#   bash scripts/run_v3_1_model.sh <modelpilot_NAME|model_NAME> <gpu[,gpu...]|scripted> [tag] [seeds]
#   bash scripts/run_v3_1_model.sh --where NAME        print the model folder
#
# modelpilot_NAME  the development split, seed 11: does the model answer in the form the frozen
#                  parser expects? Only the form of the answers is used (model_check.json).
# model_NAME       the holdout tasks, the nine conditions of the frozen matrix, three seeds.
#                  Refuses to start unless the v3.1 freeze still verifies and a pilot of the same
#                  model has passed its check.
#
# The runner, the prompt, the sampling settings and the analysis are the frozen ones
# (scripts/run_experiment_v3_1.py, scripts/analyze_v3_1.py); the one difference is described in
# src/evibound/planner_models.py. With several graphics cards the tasks are split into as many
# parts, one per card; the number of parts is fixed when a run first starts, so that a restart on
# fewer cards continues the same parts one after another. "scripted" in place of a card runs a
# deterministic persona without a model. Raw traces stay in $EVIBOUND_DATA/runs/v3_1_<stage>_<tag>/.
#
# Nothing here has confirmatory weight: the run was planned after the confirmatory results were
# known (docs/v3_1_second_model.md).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/v3_1_env.sh"

model_folder() {
  case "$1" in
    qwen3)  echo "${V31_MODEL_PATH:-/mnt/HDD-8T-0/huggingface/models/Qwen3-8B}" ;;
    qwen25) echo "${V31_MODEL_PATH:-$EVIBOUND_DATA/models/Qwen2.5-7B-Instruct}" ;;   # the frozen model, as a check of this launcher
    *) echo "unknown model $1" >&2; return 2 ;;
  esac
}
if [ "${1:-}" = --where ]; then model_folder "${2:?model name}"; exit; fi

stage="${1:?usage: run_v3_1_model.sh <modelpilot_NAME|model_NAME> <gpu[,gpu...]|scripted> [tag] [seeds]}"
gpu="${2:?gpu index, several separated by commas, or 'scripted'}"
tag="${3:-}"
case "$stage" in
  modelpilot_*) name="${stage#modelpilot_}"; split=dev; analysis_stage=dev; seeds="${4:-11}" ;;
  model_*)      name="${stage#model_}"; split=holdout; analysis_stage=explore; seeds="${4:-11 22 33}" ;;
  *) echo "unknown stage $stage" >&2; exit 2 ;;
esac
model="$(model_folder "$name")"
run_root="${V31_RUN_ROOT:-$EVIBOUND_DATA/runs}"
run_dir="$run_root/v3_1_${stage}${tag:+_$tag}"
mkdir -p "$run_dir"
if [ -e "$run_dir/COMPLETE" ]; then echo "$run_dir is already complete"; exit 0; fi
if [ "$split" = holdout ]; then
  # it uses the holdout tasks: like every run on them it needs the freeze
  python scripts/freeze_v3_1_prereg.py --verify
  passed=no
  for check in "$run_root"/v3_1_modelpilot_"${name}"_*/model_check.json; do
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
if [ "${gpus[0]}" = scripted ]; then planner_args=(--planner scripted:hasty)
else
  planner_args=(--planner local --model "$model")
  # which model exactly: sizes and hashes of its files, read once at low priority next to the run
  [ -e "$run_dir/model_files.json" ] || nice -n 19 python scripts/v3_1_model_check.py --files "$model" \
    --output "$run_dir/model_files.json" > /dev/null 2>> "$run_dir/analysis.log" &
fi

pids=()
for slot in "${!gpus[@]}"; do
  (
    [ "${gpus[$slot]}" = scripted ] || export CUDA_VISIBLE_DEVICES="${gpus[$slot]}"
    for part in $(seq 1 "$parts"); do
      [ $(( (part - 1) % ${#gpus[@]} )) -eq "$slot" ] || continue
      log="$run_dir/run.log"; [ "$part" -gt 1 ] && log="$run_dir/run_p$part.log"
      # shellcheck disable=SC2086
      python scripts/run_experiment_v3_1_model.py --part "$part/$parts" --corpus v3_1 --split "$split" --seeds $seeds \
        --batch-size 8 "${planner_args[@]}" --output "$run_dir/episodes_${split}_p$part.jsonl" >> "$log" 2>&1
    done
  ) &
  pids+=($!)
done
failed=0
for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
if [ "$failed" -ne 0 ]; then echo "a part of $stage stopped without completing; start it again to resume" >&2; exit 1; fi
wait   # the file hashes

inputs=()
for part in $(seq 1 "$parts"); do inputs+=("$run_dir/episodes_${split}_p$part.jsonl"); done
python scripts/v3_1_model_check.py --plumbing "${inputs[@]}" --output "$run_dir/model_check.json" >> "$run_dir/analysis.log" 2>&1
python scripts/analyze_v3_1.py --stage "$analysis_stage" --input "${inputs[@]}" --output "$run_dir/analysis" \
  --fingerprints "$run_dir/fingerprints.json.gz" >> "$run_dir/analysis.log" 2>&1 || status=$?
python scripts/v3_1_examples.py --input "${inputs[@]}" --output "$run_dir/examples.json" >> "$run_dir/analysis.log" 2>&1 || true
sha256sum "${inputs[@]}" > "$run_dir/episodes.sha256"
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$run_dir/COMPLETE"
exit "${status:-0}"
