#!/usr/bin/env python3
"""Freeze (or verify) the Week-11 v3 preregistration before any holdout output.

--approve NAME  requires a clean v3 review sign-off, an absent holdout run
                directory, passing v3 checks, and writes
                artifacts/week11_v3_prereg_freeze.json with source hashes.
--verify        exits 0 only if the freeze exists and every hash still matches.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FREEZE = Path('artifacts/week11_v3_prereg_freeze.json')
HOLDOUT_RUN = Path('/mnt/HDD-8T-0/evibound_yanke/runs/week11_v3_holdout')
FROZEN_FILES = [
    'docs/week11_v3_preregistration.md', 'docs/threat_model_real_world.md',
    'data/scenarios_v3/holdout.jsonl', 'data/scenarios_v3/dev.jsonl', 'data/scenarios_v3/manifest.json',
    'src/evibound/backend.py', 'src/evibound/oracle.py', 'src/evibound/planner.py',
    'src/evibound/recovery.py', 'src/evibound/runner_v3.py', 'src/evibound/backend_v3.py',
    'src/evibound/oracle_v3.py', 'src/evibound/planner_v3.py',
    'scripts/run_experiment_v3.py', 'scripts/analyze_v3.py', 'scripts/analyze.py',
    'scripts/run_v3_holdout.sh',
]
MODEL_REVISION = 'a09a35458c702b33eeacc393d103063234e8bc28'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify():
    if not FREEZE.exists():
        print('NOT FROZEN: run scripts/freeze_v3_prereg.py --approve "Name" after review sign-off')
        return 1
    freeze = json.loads(FREEZE.read_text())
    changed = [p for p, h in freeze['sha256'].items() if not Path(p).exists() or digest(p) != h]
    if changed:
        print('FREEZE MISMATCH:', ', '.join(changed))
        return 1
    print(f'freeze ok ({freeze["approved_by"]}, {freeze["frozen_utc"]})')
    return 0


def approve(name):
    signoff_path = Path('reviews/v3/signoff.json')
    if not signoff_path.exists():
        sys.exit('missing reviews/v3/signoff.json: finish the v3 review bundle first')
    signoff = json.loads(signoff_path.read_text())
    if signoff['open_items']:
        sys.exit(f'review has open items: {signoff["open_items"]}')
    for split in ('dev', 'holdout'):
        if digest(f'data/scenarios_v3/{split}.jsonl') != signoff['corpus_sha256'][split]:
            sys.exit(f'{split} corpus changed after review sign-off')
    if HOLDOUT_RUN.exists() and any(HOLDOUT_RUN.iterdir()):
        sys.exit(f'{HOLDOUT_RUN} already has output; a freeze must precede holdout output')
    subprocess.run([sys.executable, 'scripts/check_scenarios_v3.py'], check=True)
    freeze = {'study': 'EviBound v3 recovery', 'approved_by': name,
              'frozen_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'model_revision': MODEL_REVISION, 'review_signoff': signoff,
              'sha256': {p: digest(p) for p in FROZEN_FILES}}
    FREEZE.write_text(json.dumps(freeze, indent=2, sort_keys=True) + '\n')
    print(f'frozen: {FREEZE}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--approve', metavar='NAME')
    group.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        sys.exit(verify())
    approve(args.approve)


if __name__ == '__main__':
    main()
