#!/usr/bin/env python3
"""Three more tables for the v3.1 results document.

The frozen analysis script writes the tables its plan names. Two things the plan promises to
report always are easier to read in tables of their own: every condition over all tasks (exact
target, unrequested change, unsafe effect), and the raw completion of the unguarded run against
the ceiling. Both only rearrange numbers of artifacts/v3_1_holdout_results.json.

The third table is descriptive and was not planned: outside turns of the kind `reselect`, the
levels `M_recover` and `M_reading` send the same message, byte for byte, and their answers are
sampled separately. How often the two then end differently shows how much of a difference
between two levels is sampling alone. It is counted from the committed episode fingerprints.

  python scripts/v3_1_results_tables.py            # refresh the tables in docs/v3_1_results.md
  python scripts/v3_1_results_tables.py --check    # fail if they are stale
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import analyze_v3_1 as plan  # noqa: E402
import v3_1_lib as lib  # noqa: E402
from evibound.recovery_v3_1 import V31_CONDITIONS  # noqa: E402

RECORD = ROOT / 'artifacts/v3_1_holdout_results.json'
FINGERPRINTS = ROOT / 'artifacts/v3_1_holdout_fingerprints.json.gz'
SAME_MESSAGE = ('interrupted', 'revise', 'empty', 'no review (malformed output and the like)')
DOC = ROOT / 'docs/v3_1_results.md'
VARIANTS = (('clean', 'clean'), ('boundary', 'boundary'), ('perturbed', 'attacked'))


def cells(record):
    return {(i['variant'], i['condition'], i['class']): i for i in record['summary']}


def totals(record):
    """Per condition: episodes and counts over all tasks, by variant and summed."""
    cell = cells(record)
    out = {}
    for condition in record['design']['conditions']:
        by_variant = {v: cell[(v, condition, 'all')] for v, _ in VARIANTS}
        out[condition] = {'by_variant': by_variant,
                          'all': {k: sum(item[k] for item in by_variant.values())
                                  for k in ('n', 'exact_target', 'unrequested_change', 'unsafe_effect',
                                            'authorization_violation', 'goal_completion')}}
    return out


def twice(rows):
    """Recovery turns under `M_recover` and `M_reading`, by kind: how often the executed writes are the same."""
    cells = {}
    for row in rows:
        if row['condition'] in ('M_recover', 'M_reading'):
            cells.setdefault((row['task_id'], row['variant'], row['seed']), {})[row['condition']] = row
    out = {}
    for pair in cells.values():
        a, b = pair['M_recover'], pair['M_reading']
        if not a.get('trigger'):
            continue
        kind = a.get('form') or SAME_MESSAGE[-1]
        cell = out.setdefault(kind, {'turns': 0, 'same_writes': 0, 'exact_reason': 0, 'exact_reading': 0})
        cell['turns'] += 1
        cell['same_writes'] += a['writes'] == b['writes']
        cell['exact_reason'] += bool(a['metrics']['exact_target'])
        cell['exact_reading'] += bool(b['metrics']['exact_target'])
    return out


def share(count, n):
    return f'{count} ({100 * count / n:.1f}%)'


def blocks(record, episodes=None):
    T = lib.table
    order = [c for c in V31_CONDITIONS if c in record['design']['conditions']]
    total = totals(record)
    rows = []
    for condition in order:
        t = total[condition]
        row = [f'`{condition}`', record['ladder'].get(condition) or plan.OTHER_LEVELS.get(condition, '')]
        row += [t['by_variant'][v]['exact_target'] for v, _ in VARIANTS] + [share(t['all']['exact_target'], t['all']['n'])]
        row += [t['by_variant'][v]['unrequested_change'] for v, _ in VARIANTS]
        row += [share(t['all']['unrequested_change'], t['all']['n']), t['all']['unsafe_effect'], t['all']['authorization_violation']]
        rows.append(row)
    per_variant = total[order[0]]['by_variant']['clean']['n']
    out = {'totals': T(['Condition', 'Level'] + [f'exact target, {name} (of {per_variant})' for _, name in VARIANTS]
                       + [f"exact target, all (of {total[order[0]]['all']['n']})"]
                       + [f'unrequested change, {name}' for _, name in VARIANTS]
                       + ['unrequested change, all', 'unsafe effect, all', 'write outside the scope, all'], rows)}
    cell = cells(record)
    rows = []
    for variant, name in VARIANTS:
        core, full = cell[(variant, 'B0', 'core')], cell[(variant, 'B0', 'full')]
        guarded = cell[(variant, 'M_recover', 'full')]
        rows.append([name, f"{core['goal_completion']} of {core['n']}", core['safe_completion'],
                     core['goal_completion'] - core['safe_completion'], f"{full['n']} of {core['n']}",
                     f"{full['goal_completion']} ({full['safe_completion']} without a violation)",
                     guarded['goal_completion']])
    out['ceiling'] = T(['Variant', '`B0`: goal reached, core tasks', 'of these without a violation', 'with a violation',
                        'Ceiling: episodes whose whole goal is attainable', '`B0` on those: goal reached',
                        '`M_recover` on those: goal reached'], rows)
    if episodes is not None:
        pairs = twice(episodes)
        same = {k: sum(pairs.get(kind, {}).get(k, 0) for kind in SAME_MESSAGE)
                for k in ('turns', 'same_writes', 'exact_reason', 'exact_reading')}
        table = [[kind, 'the same', v['turns'], share(v['same_writes'], v['turns']), v['turns'] - v['same_writes'],
                  v['exact_reason'], v['exact_reading']] for kind in SAME_MESSAGE if (v := pairs.get(kind))]
        table.append(['all four', 'the same', same['turns'], share(same['same_writes'], same['turns']),
                      same['turns'] - same['same_writes'], same['exact_reason'], same['exact_reading']])
        if (v := pairs.get('reselect')):
            table.append(['reselect', 'different', v['turns'], share(v['same_writes'], v['turns']),
                          v['turns'] - v['same_writes'], v['exact_reason'], v['exact_reading']])
        out['twice'] = T(['Kind of recovery turn', 'Message of `M_recover` and `M_reading`', 'Turns',
                          'Same executed writes', 'Different', 'Exact target, `M_recover`', 'Exact target, `M_reading`'], table)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    record = json.loads(RECORD.read_text())
    episodes = lib.read_fingerprints(FINGERPRINTS)
    lib.annotate(episodes, lib.load_tasks(ROOT / 'data/scenarios_v3_1/holdout.jsonl'))    # adds the outcome measures
    doc = DOC.read_text()
    fresh = lib.refresh_blocks(doc, blocks(record, episodes))
    if args.check:
        print('the extra tables are current' if fresh == doc else f'{DOC.relative_to(ROOT)} has stale extra tables')
        return 0 if fresh == doc else 1
    DOC.write_text(fresh)
    print(json.dumps({'document': str(DOC.relative_to(ROOT)), 'tables': ['totals', 'ceiling', 'twice']}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
