#!/usr/bin/env python3
"""Does the v3.1 engine reproduce the frozen v3 holdout run where it should?

The development run on the v3 corpus repeats the v3 holdout tasks with the same planner,
prompt, seeds and batches. First responses should therefore be identical, and so should
every episode that had no recovery turn. Episodes with a recovery turn are sampled with
other batch seeds (the batches hold other conditions), so only their rates can be compared.

  python scripts/v3_1_replication_check.py --v3 artifacts/episode_fingerprints_v3_holdout.json.gz \
      --dev-v3 <fingerprints of the dev_v3 run> [--output file.json]
"""
import argparse
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import v3_1_lib as lib  # noqa: E402

SHARED = ('B0', 'M', 'M_recover', 'M_full')


def frozen_rows(path):
    document = json.loads(gzip.open(path).read().decode())
    keys = document['outcome_keys']
    rows = {}
    for task, variant, condition, seed, _, first, writes, outcomes, proposals in document['rows']:
        rows[(task, variant, condition, seed)] = {
            'first': first, 'writes': writes, 'proposals': proposals,
            'metrics': {k: outcomes[i] == '1' for i, k in enumerate(keys)}}
    return rows


def compare(v3_path, dev_v3_path):
    """Counts for the comparison of the frozen v3 holdout run with a development run on the v3 corpus."""
    old = frozen_rows(v3_path)
    new = {lib.identity(r): r for r in lib.read_fingerprints(dev_v3_path)}
    cells = sorted({(k[0], k[1], k[3]) for k in old} & {(k[0], k[1], k[3]) for k in new})
    same_first = sum(old[(t, v, 'B0', s)]['first'] == new[(t, v, 'B0', s)]['first'] for t, v, s in cells)
    result = {'cells_compared': len(cells), 'first_response_identical': same_first, 'conditions': {}}
    for condition in SHARED:
        stats = defaultdict(int)
        for task, variant, seed in cells:
            a, b = old.get((task, variant, condition, seed)), new.get((task, variant, condition, seed))
            if a is None or b is None:
                continue
            stats['episodes'] += 1
            new_writes = ';'.join(f'{d}={v}' for d, v in b['writes'])
            if a['first'] == b['first'] and a['proposals'] == 1 and b['proposals'] == 1:
                stats['no_recovery'] += 1
                stats['no_recovery_identical'] += a['writes'] == new_writes and a['metrics'] == b['metrics']
            elif a['first'] == b['first']:
                stats['with_recovery'] += 1
                stats['with_recovery_same_writes'] += a['writes'] == new_writes
            stats['goal_completion_v3'] += a['metrics']['goal_completion']
            stats['goal_completion_now'] += b['metrics']['goal_completion']
            stats['unsafe_effect_v3'] += a['metrics']['unsafe_effect']
            stats['unsafe_effect_now'] += b['metrics']['unsafe_effect']
        result['conditions'][condition] = dict(stats)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--v3', type=Path, default=ROOT / 'artifacts/episode_fingerprints_v3_holdout.json.gz')
    parser.add_argument('--dev-v3', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = compare(args.v3, args.dev_v3)
    print(f"first responses identical: {result['first_response_identical']} of {result['cells_compared']} "
          f"(task, variant, seed) cells")
    for condition, s in result['conditions'].items():
        print(f"{condition:<10} episodes {s.get('episodes', 0):>4}; without recovery {s.get('no_recovery', 0):>4}, "
              f"identical {s.get('no_recovery_identical', 0):>4}; with recovery {s.get('with_recovery', 0):>4}, "
              f"same writes {s.get('with_recovery_same_writes', 0):>4}; goal completion v3 "
              f"{s.get('goal_completion_v3', 0)} / now {s.get('goal_completion_now', 0)}; unsafe v3 "
              f"{s.get('unsafe_effect_v3', 0)} / now {s.get('unsafe_effect_now', 0)}")
    if args.output:
        args.output.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
