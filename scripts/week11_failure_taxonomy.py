#!/usr/bin/env python3
"""Retrospective failure taxonomy of the frozen Week-8 v2 traces (no reruns).

Motivates the v3 recovery conditions. Reads retained episode JSONL files and
writes artifacts/week11_v2_failure_taxonomy.json. Descriptive only: the v2
test split stays closed for tuning and is not re-analysed confirmatorily.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_v3 import failure_category  # noqa: E402

RUNS = Path('/mnt/HDD-8T-0/evibound_yanke/runs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', nargs='+', default=['week8_v2_pilot', 'week8_v2_main_test'])
    parser.add_argument('--output', type=Path, default=Path('artifacts/week11_v2_failure_taxonomy.json'))
    args = parser.parse_args()
    result = {'purpose': __doc__.strip().splitlines()[0], 'inputs': [], 'by_run': {}}
    for run in args.runs:
        taxonomy, totals = defaultdict(Counter), Counter()
        for path in sorted((RUNS / run).glob('seed_*.jsonl')):
            data = path.read_bytes()
            result['inputs'].append({'path': str(path), 'sha256': hashlib.sha256(data).hexdigest()})
            for line in data.decode().splitlines():
                episode = json.loads(line)
                if episode['variant'] not in ('clean', 'perturbed'):
                    continue
                cell = f'{episode["condition"]}/{episode["variant"]}'
                totals[cell] += 1
                category = failure_category(episode)
                if category:
                    taxonomy[cell][category] += 1
        result['by_run'][run] = {cell: {'n': totals[cell], 'failures': dict(taxonomy[cell])}
                                 for cell in sorted(totals)}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    for run, cells in result['by_run'].items():
        for cell in ('B0/clean', 'M/clean', 'M/perturbed'):
            print(run, cell, cells.get(cell))


if __name__ == '__main__':
    main()
