#!/usr/bin/env bash
# Independent reproduction, recorded: run scripts/reproduce.sh at level 3 on GPU
# $EVIBOUND_GPU (all three v2 seeds, v3 holdout seed 11), then save the reports
# as artifacts, commit them and push. Meant to be started by
# scripts/run_when_gpu_idle.sh from a fresh clone:
#
#   EVIBOUND_DATA=/path/to/data-disk bash scripts/run_when_gpu_idle.sh STATUS \
#       bash scripts/reproduce_and_record.sh
#
# Raw re-run traces stay in $EVIBOUND_DATA/runs/reproduction_<UTC>/; only the
# small JSON reports are committed.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
: "${EVIBOUND_DATA:?set EVIBOUND_DATA}" "${EVIBOUND_GPU:?set EVIBOUND_GPU}"
PY="$EVIBOUND_DATA/envs/runtime/bin/python"; [ -x "$PY" ] || PY=python3
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$EVIBOUND_DATA/runs/reproduction_$stamp"

nice -n 10 bash scripts/reproduce.sh --gpu "$EVIBOUND_GPU" --seeds "11 22 33" --v3-seeds "11" --out "$out"
code=$?

copy() { [ -f "$1" ] && cp "$1" "$2"; }
copy "$out/reproduction_report.json"      artifacts/reproduction_v2_formal_test_rerun.json
copy "$out/reproduction_report_v3.json"   artifacts/reproduction_v3_holdout_rerun.json
copy "$out/published_results_check.json"  artifacts/reproduction_published_results_check.json
copy "$out/contract_outcomes.json"        artifacts/contract_outcomes_v2_v3.json
"$PY" - "$stamp" "$code" "$out" > artifacts/reproduction_environment.json <<'PYEOF'
import json, platform, subprocess, sys
def sh(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as exc:  # recorded, not fatal
        return f'unavailable: {exc}'
info = {'started_utc': sys.argv[1], 'reproduce_exit_code': int(sys.argv[2]),
        'run_folder': sys.argv[3].rsplit('/', 1)[-1],
        'commit': sh('git', 'rev-parse', 'HEAD'), 'checkout': 'fresh shallow clone of the public repository',
        'python': platform.python_version(), 'platform': platform.platform(),
        'gpu': sh('nvidia-smi', '--query-gpu=index,name,driver_version', '--format=csv,noheader'),
        'levels': 'unit tests, corpus checkers, freezes, scripted pipeline, published numbers from raw traces, '
                  'v2 formal test re-run (seeds 11 22 33), v3 holdout re-run (seed 11)'}
for name in ('torch', 'transformers'):
    try:
        info[name] = __import__(name).__version__
    except Exception as exc:
        info[name] = f'unavailable: {exc}'
print(json.dumps(info, indent=1))
PYEOF

git add artifacts/reproduction_*.json artifacts/contract_outcomes_v2_v3.json
git commit -q -m "Record the independent reproduction run $stamp" \
  -m "Reports from scripts/reproduce.sh level 3 in a fresh clone on the original GPU machine (exit code $code). No frozen file is changed." \
  -m "Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01PKUG385foEG4C13ww9pV3f" || echo "nothing to commit"
git pull -q --rebase && git push -q || echo "push failed: reports are committed locally in $ROOT"
echo "reproduction $stamp finished with code $code; outputs in $out"
exit "$code"
