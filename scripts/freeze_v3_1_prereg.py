#!/usr/bin/env python3
"""Freeze (or verify) the v3.1 preregistration before any holdout output.

--approve NAME   requires passing corpus checks, a current layer-1 record and no holdout
                 output, then writes artifacts/v3_1_prereg_freeze.json with the hash of every
                 file the confirmatory run and its analysis depend on.
--verify         exits 0 only if the freeze exists and every hash still matches.

Unlike the v3 freeze, this one does not require a human sign-off of the corpus before the
run. The corpus owner decided on 2026-11-24 that the machine-generated corpus is checked
after the run. The freeze records that decision; the preregistration says how a label
rejected later is handled.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FREEZE = Path('artifacts/v3_1_prereg_freeze.json')
HOLDOUT_RUNS = Path('/mnt/HDD-8T-0/evibound_yanke/runs')
FROZEN_FILES = [
    'docs/v3_1_preregistration.md', 'docs/v3_1_layer1_attainability.md',
    'data/scenarios_v3_1/holdout.jsonl', 'data/scenarios_v3_1/dev.jsonl',
    'data/scenarios_v3_1/manifest.json', 'data/scenarios_v3_1/check_report.json',
    'src/evibound/backend.py', 'src/evibound/backend_v3.py', 'src/evibound/oracle.py',
    'src/evibound/oracle_v3.py', 'src/evibound/planner.py', 'src/evibound/planner_v3.py',
    'src/evibound/recovery.py', 'src/evibound/recovery_v3_1.py', 'src/evibound/runner_v3.py',
    'src/evibound/runner_v3_1.py', 'src/evibound/planner_v3_1.py', 'src/evibound/attainability.py',
    'scripts/run_experiment_v3_1.py', 'scripts/run_v3_1.sh', 'scripts/v3_1_env.sh',
    'scripts/analyze_v3_1.py', 'scripts/v3_1_lib.py', 'scripts/analyze.py', 'scripts/analyze_v3.py',
    'scripts/generate_scenarios_v3_1.py', 'scripts/check_scenarios_v3_1.py',
    'scripts/scenario_v2_lib.py', 'scripts/generate_scenarios_v2.py', 'scripts/generate_scenarios_v3.py',
]
MODEL_REVISION = 'a09a35458c702b33eeacc393d103063234e8bc28'
LABEL_REVIEW = {
    'status': 'after the run',
    'decided_by': 'corpus owner',
    'decided_on': '2026-11-24',
    'basis': ('Owner instruction in the project session of 2026-11-24: the generated corpus is adequate for the '
              'attack and defence test with the pinned planner and can be checked afterwards.'),
    'before_the_run': 'scripts/check_scenarios_v3_1.py: labels recomputed with the oracle rule function and each task played through the simulator',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify():
    if not FREEZE.exists():
        print('NOT FROZEN: run scripts/freeze_v3_1_prereg.py --approve "Name"')
        return 1
    freeze = json.loads(FREEZE.read_text())
    changed = [p for p, h in freeze['sha256'].items() if not Path(p).exists() or digest(p) != h]
    if changed:
        print('FREEZE MISMATCH:', ', '.join(changed))
        return 1
    print(f'v3.1 freeze ok ({freeze["approved_by"]}, {freeze["frozen_utc"]})')
    return 0


def approve(name, executed_by):
    existing = sorted(HOLDOUT_RUNS.glob('v3_1_holdout*')) if HOLDOUT_RUNS.exists() else []
    if any(any(p.iterdir()) for p in existing if p.is_dir()):
        sys.exit(f'holdout output already exists ({existing[0]}); a freeze must precede holdout output')
    subprocess.run([sys.executable, 'scripts/check_scenarios_v3_1.py'], check=True)
    subprocess.run([sys.executable, 'scripts/analyze_v3_1_layer1.py', '--check'], check=True)
    missing = [p for p in FROZEN_FILES if not Path(p).exists()]
    if missing:
        sys.exit('missing files: ' + ', '.join(missing))
    freeze = {'study': 'EviBound v3.1 feedback ladder', 'approved_by': name, 'executed_by': executed_by,
              'frozen_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'model_revision': MODEL_REVISION, 'label_review': LABEL_REVIEW,
              'corpus_check': json.loads(Path('data/scenarios_v3_1/check_report.json').read_text())['total_errors'],
              'sha256': {p: digest(p) for p in FROZEN_FILES}}
    FREEZE.write_text(json.dumps(freeze, indent=2, sort_keys=True) + '\n')
    print(f'frozen: {FREEZE}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--approve', metavar='NAME')
    group.add_argument('--verify', action='store_true')
    parser.add_argument('--executed-by', default='')
    args = parser.parse_args()
    if args.verify:
        sys.exit(verify())
    approve(args.approve, args.executed_by)


if __name__ == '__main__':
    main()
