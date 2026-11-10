#!/usr/bin/env bash
# Independent reproduction on a fresh GPU machine with internet access (for example Google Colab,
# one GPU with at least 24 GB).
#
#   git clone -q -b <branch> https://github.com/RealWayTrueX/EviBound.git
#   bash EviBound/scripts/reproduce_cloud.sh                         # v2 seeds 11 22 33 + v3 holdout seed 11
#   SEEDS="11" V3_SEEDS="" bash EviBound/scripts/reproduce_cloud.sh  # shortest model run (432 episodes)
#
# What it does
#   1. installs the library versions of the original runs (configs/requirements_observed.txt);
#      KEEP_ENV=1 keeps the machine's own versions instead;
#   2. downloads the pinned model revision and checks every file against artifacts/model_manifest.json;
#   3. runs scripts/reproduce.sh (checks, then the frozen runners) in the background and prints one
#      status line a minute; MAX_MINUTES (default 170) stops a run that takes too long;
#   4. summarises the re-run beside the published results, compares it episode by episode with the
#      original run when artifacts/episode_fingerprints_*.json.gz exist, and prints the reports and a
#      packed fingerprint block of the re-run between marker lines.
#
# Nothing is uploaded anywhere. Outputs stay under $WORK (default /content/evibound_work on Colab).
# The machine differs from the original (GPU model, drivers), so sampled responses are not expected to
# be identical episode by episode; the reports say how far they agree.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -z "${WORK:-}" ]; then
  if [ -d /content ]; then WORK=/content/evibound_work; else WORK="$ROOT/cloud_work"; fi
fi
MODEL="$WORK/models/Qwen2.5-7B-Instruct"
OUT="$WORK/out"
SEEDS="${SEEDS-11 22 33}"
V3_SEEDS="${V3_SEEDS-11}"
MAX_MINUTES="${MAX_MINUTES:-170}"
mkdir -p "$WORK" "$OUT"
export TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
export PYTHONPATH="$ROOT/src:$ROOT${PYTHONPATH:+:$PYTHONPATH}"
say() { printf '\n[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
START="$(date +%s)"

say "Commit $(git rev-parse --short HEAD) on $(git rev-parse --abbrev-ref HEAD)"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader \
  || { echo "no NVIDIA GPU is visible: choose a GPU runtime"; exit 2; }
free_mib="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)"
[ "$free_mib" -ge 22000 ] || { echo "the GPU has ${free_mib} MiB; the frozen runner needs about 24 GB"; exit 2; }

if [ "${KEEP_ENV:-0}" != 1 ]; then
  say "1/4 Installing the library versions of the original runs"
  current="$(python3 -c 'import torch; print(torch.__version__.split("+")[0])' 2>/dev/null || echo none)"
  if [ "$current" != "2.9.0" ]; then
    python3 -m pip uninstall -q -y torchvision torchaudio 2>/dev/null | tail -1
    python3 -m pip install -q torch==2.9.0 --index-url https://download.pytorch.org/whl/cu128 2>&1 | tail -2
  fi
  python3 -m pip install -q transformers==4.57.1 tokenizers==0.22.2 accelerate==1.11.0 \
      safetensors==0.5.3 huggingface-hub==0.36.0 2>&1 | tail -2
else
  say "1/4 Keeping the machine's own library versions (KEEP_ENV=1)"
fi
python3 - > "$OUT/environment.json" <<'PYEOF'
import json, platform, subprocess
def sh(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as exc:
        return f'unavailable: {exc}'
info = {'python': platform.python_version(), 'platform': platform.platform(),
        'gpu': sh('nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'),
        'commit': sh('git', 'rev-parse', 'HEAD'), 'node': sh('node', '--version')}
for name in ('torch', 'transformers', 'tokenizers', 'accelerate', 'safetensors', 'huggingface_hub', 'numpy'):
    try:
        info[name] = __import__(name).__version__
    except Exception as exc:
        info[name] = f'unavailable: {exc}'
try:
    import torch
    info['cuda_compiled'] = torch.version.cuda
    info['cuda_available'] = torch.cuda.is_available()
except Exception as exc:
    info['cuda_available'] = f'unavailable: {exc}'
print(json.dumps(info, indent=1))
PYEOF
cat "$OUT/environment.json"
python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("cuda_available") is True else 1)' \
  "$OUT/environment.json" || { echo "torch cannot use the GPU after the install"; exit 2; }

say "2/4 Downloading the pinned model revision and checking it against artifacts/model_manifest.json"
python3 - "$MODEL" <<'PYEOF' || { echo "model download or verification failed"; exit 2; }
import hashlib, json, pathlib, sys
from huggingface_hub import snapshot_download
manifest = json.load(open('artifacts/model_manifest.json'))
root = pathlib.Path(snapshot_download(manifest['model'], revision=manifest['revision'], local_dir=sys.argv[1]))
bad = 0
for name, expected in sorted(manifest['files'].items()):
    path = root / name
    digest = hashlib.sha256()
    if path.exists():
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1 << 24), b''):
                digest.update(chunk)
    ok = path.exists() and digest.hexdigest() == expected['sha256']
    bad += not ok
    if not ok:
        print('MISMATCH', name)
print(f'{len(manifest["files"]) - bad} of {len(manifest["files"])} model files match the manifest '
      f'(revision {manifest["revision"][:12]})')
sys.exit(1 if bad else 0)
PYEOF

say "3/4 Running scripts/reproduce.sh (v2 seeds: ${SEEDS}; v3 holdout seeds: ${V3_SEEDS:-none})"
traces=()
[ -d "$WORK/traces/week8_v2_main_test" ] && traces=(--traces "$WORK/traces")
rm -f "$OUT/exit_code"
(
  if [ -n "$V3_SEEDS" ]; then
    bash scripts/reproduce.sh --gpu 0 --model "$MODEL" --seeds "$SEEDS" --v3-seeds "$V3_SEEDS" \
        "${traces[@]}" --out "$OUT" > "$OUT/console.log" 2>&1
  else
    bash scripts/reproduce.sh --gpu 0 --model "$MODEL" --seeds "$SEEDS" "${traces[@]}" --out "$OUT" \
        > "$OUT/console.log" 2>&1
  fi
  echo $? > "$OUT/exit_code"
) &
runner=$!
count() { cat "$@" 2>/dev/null | wc -l; }
while [ ! -f "$OUT/exit_code" ]; do
  sleep 60
  minutes=$(( ($(date +%s) - START) / 60 ))
  step="$(grep '^== ' "$OUT/reproduce.log" 2>/dev/null | tail -1 | cut -c1-60)"
  printf '[%s] %s min | %s | v2 episodes %s | v3 episodes %s | GPU %s MiB\n' "$(date -u +%H:%M:%S)" \
    "$minutes" "$step" "$(count "$OUT"/seed_*.jsonl)" "$(count "$OUT"/v3_holdout_rerun.jsonl)" \
    "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)"
  if [ "$minutes" -ge "$MAX_MINUTES" ]; then
    echo "stopping: the run passed MAX_MINUTES=$MAX_MINUTES; finished episodes are kept and a later run resumes"
    pkill -TERM -P "$runner" 2>/dev/null; pkill -TERM -f scripts/run_experiment 2>/dev/null
    sleep 5; echo 124 > "$OUT/exit_code"
  fi
done
code="$(cat "$OUT/exit_code")"
say "reproduce.sh finished with exit code $code after $(( ($(date +%s) - START) / 60 )) minutes"
grep -E '^(== |Ran |OK|FAILED|\[ok\]|\[FAIL\]|COMPLETE|compared |  [A-Za-z0-9_]+: original)' "$OUT/reproduce.log" \
  | cut -c1-220 | tail -40

say "4/4 Reports"
v2_files=(); for seed in $SEEDS; do [ -s "$OUT/seed_${seed}.jsonl" ] && v2_files+=("$OUT/seed_${seed}.jsonl"); done
if [ "${#v2_files[@]}" -gt 0 ]; then
  python3 scripts/summarize_rerun.py --study v2 --rerun "${v2_files[@]}" --output "$OUT/rerun_summary_v2.json"
  python3 scripts/episode_fingerprints.py --study v2 --inputs "${v2_files[@]}" \
      --output "$OUT/rerun_fingerprints_v2.json" --pack
  original="artifacts/episode_fingerprints_v2_formal_test.json.gz"
  [ -f "$original" ] && python3 scripts/compare_runs.py --study v2 --original "$original" \
      --rerun "$OUT/rerun_fingerprints_v2.json" --output "$OUT/episode_comparison_v2.json"
fi
if [ -s "$OUT/v3_holdout_rerun.jsonl" ]; then
  python3 scripts/summarize_rerun.py --study v3 --rerun "$OUT/v3_holdout_rerun.jsonl" \
      --output "$OUT/rerun_summary_v3.json"
  python3 scripts/episode_fingerprints.py --study v3 --inputs "$OUT/v3_holdout_rerun.jsonl" \
      --output "$OUT/rerun_fingerprints_v3.json" --pack
  original="artifacts/episode_fingerprints_v3_holdout.json.gz"
  [ -f "$original" ] && python3 scripts/compare_runs.py --study v3 --original "$original" \
      --rerun "$OUT/rerun_fingerprints_v3.json" --output "$OUT/episode_comparison_v3.json"
fi
bundle="$WORK/evibound_cloud_rerun_$(date -u +%Y%m%dT%H%MZ).tar.gz"
( cd "$OUT" && tar -czf "$bundle" --exclude='pipeline_scripted' . ) \
  && echo "re-run bundle (traces, logs, reports): $bundle ($(du -h "$bundle" | cut -f1), sha256 $(sha256sum "$bundle" | cut -c1-64))"
sha256sum "$OUT"/seed_*.jsonl "$OUT"/v3_holdout_rerun.jsonl 2>/dev/null | sed "s#$OUT/##"
say "Done in $(( ($(date +%s) - START) / 60 )) minutes. Disconnect and delete the runtime now to stop billing."
exit "$code"
