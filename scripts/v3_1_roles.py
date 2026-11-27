#!/usr/bin/env python3
"""Exploratory arm of v3.1: one model, several planner characters.

The holdout tasks were run again with three other system prompts (cautious, faithful, experienced)
under four conditions. This script puts those runs next to the confirmatory run (the v3 prompt,
restricted to the same four conditions), writes the record (artifacts/v3_1_roles_record.json) and
refreshes the generated tables of the section on planner characters in docs/v3_1_results.md.

Nothing here has confirmatory weight. The contrasts are those of the frozen plan
(scripts/analyze_v3_1.py); only the selection shown in the document is made here.

  python scripts/v3_1_roles.py            # write the record and the tables
  python scripts/v3_1_roles.py --check    # fail if either is stale
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

RECORD = ROOT / 'artifacts/v3_1_roles_record.json'
DOC = ROOT / 'docs/v3_1_results.md'
TASKS = 'data/scenarios_v3_1/holdout.jsonl'
CONDITIONS = ('B0', 'M_recover', 'M_reading', 'M_full')
RUNS = {
    'base': ('artifacts/v3_1_holdout_fingerprints.json.gz', 'v3 prompt (the confirmatory run)'),
    'cautious': ('artifacts/v3_1_role_cautious_fingerprints.json.gz', 'cautious'),
    'faithful': ('artifacts/v3_1_role_faithful_fingerprints.json.gz', 'faithful'),
    'experienced': ('artifacts/v3_1_role_experienced_fingerprints.json.gz', 'experienced'),
}
# the contrasts shown in the document; the record holds every contrast the four conditions allow
SHOWN = (
    ('U1', 'Unrequested change, all tasks: list − reason'),
    ('K31', 'the same on the attack battery'),
    ('N1', 'Exact target, all tasks: reason − list (not behind by 5 pp)'),
    ('K36', 'the same as a test of superiority'),
    ('I1', 'Exact target in turns of the kind `interrupted`: reason − list'),
    ('K43', 'Exact target in turns of the kind `revise`: reason − list'),
    ('K54', 'Exact target in turns of the kind `reselect`: reason − list'),
    ('R1', 'Exact target in turns of the kind `reselect`: reason and reading − reason'),
    ('K37', 'Exact target, all turns: reason and reading − reason'),
    ('K41', 'Goal completion on attainable goals: list − reason'),
)
KINDS = ('interrupted', 'reselect', 'revise', 'empty', 'no review (malformed output and the like)', 'no recovery turn')


def compact(item):
    effect = item['effect']
    if not effect:
        return {'decision': 'missing'}
    return {'left': effect['left_count'], 'right': effect['right_count'], 'episodes': effect['episodes_per_arm'],
            'structures': effect['n_tasks'], 'estimate_pp': round(100 * effect['estimate'], 1),
            'low_pp': round(100 * effect['ci95_low'], 1), 'high_pp': round(100 * effect['ci95_high'], 1),
            'rule': item['rule'], 'decision': item['decision']}


def one_role(path, tasks):
    rows = [r for r in lib.read_fingerprints(ROOT / path) if r['condition'] in CONDITIONS]
    result = plan.analyze(rows, tasks)
    totals = {}
    for item in result['summary']:
        if item['class'] == 'all':
            cell = totals.setdefault(item['condition'], {'episodes': 0, 'exact_target': 0, 'unrequested_change': 0,
                                                         'unsafe_effect': 0, 'goal_completion': 0})
            cell['episodes'] += item['n']
            for key in ('exact_target', 'unrequested_change', 'unsafe_effect', 'goal_completion'):
                cell[key] += item[key]
    contrasts = {i: compact(item) for i, item in result['decisions'].items() if item['effect']}
    contrasts.update({item['id']: compact(item) for item in result['secondary']})
    turns = {kind: row['by_condition']['M_recover']['n'] for kind, row in result['kinds']['rows'].items()}
    return {'input': {'file': path, 'sha256': lib.sha256_file(ROOT / path)},
            'tasks': result['design']['tasks'], 'conditions': result['design']['conditions'],
            'episodes': result['design']['episodes'], 'seeds': result['design']['seeds'],
            'complete_matrix': result['design']['complete_matrix'],
            'replay_disagreements': result['replay_disagreements'],
            'totals': totals, 'turns_by_kind': turns, 'kinds': result['kinds']['rows'], 'contrasts': contrasts}


def build():
    tasks = lib.load_tasks(ROOT / TASKS)
    record = {'study': 'EviBound v3.1, exploratory arm: one model, several planner characters (no confirmatory weight)',
              'conditions': list(CONDITIONS), 'roles': {}}
    for name, (path, _) in RUNS.items():
        if (ROOT / path).exists():
            record['roles'][name] = one_role(path, tasks)
    return record


def cell(item):
    if not item or item.get('decision') == 'missing':
        return 'not run'
    return (f"{item['left']} vs {item['right']} of {item['episodes']}; {item['estimate_pp']:+.1f} "
            f"[{item['low_pp']:+.1f}, {item['high_pp']:+.1f}]; {item['decision']}")


def blocks(record):
    T = lib.table
    roles = record['roles']
    names = [n for n in RUNS if n in roles]
    label = {n: RUNS[n][1] for n in names}
    out = {}
    out['roles'] = T(['Id', 'Contrast'] + [label[n] for n in names],
                     [[i, text] + [cell(roles[n]['contrasts'].get(i)) for n in names] for i, text in SHOWN])
    rows = []
    for condition in CONDITIONS:
        row = [f'`{condition}`']
        for n in names:
            v = roles[n]['totals'].get(condition)
            row.append(f"{v['exact_target']} / {v['unrequested_change']} / {v['unsafe_effect']} of {v['episodes']}" if v else '')
        rows.append(row)
    out['roles_totals'] = T(['Condition'] + [label[n] for n in names], rows)
    out['roles_turns'] = T(['Kind of recovery turn'] + [label[n] for n in names],
                           [[kind] + [roles[n]['turns_by_kind'].get(kind, 0) for n in names] for kind in KINDS])
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    record = build()
    text = json.dumps(record, indent=1, sort_keys=True) + '\n'
    doc = DOC.read_text()
    fresh = lib.refresh_blocks(doc, blocks(record))
    if args.check:
        problems = []
        if not RECORD.exists() or RECORD.read_text() != text:
            problems.append(f'{RECORD.relative_to(ROOT)} is stale')
        if fresh != doc:
            problems.append(f'{DOC.relative_to(ROOT)} has stale tables on the planner characters')
        print('\n'.join(problems) or 'record and tables of the planner characters are current')
        return 1 if problems else 0
    RECORD.write_text(text)
    DOC.write_text(fresh)
    print(json.dumps({'record': str(RECORD.relative_to(ROOT)), 'roles': list(record['roles'])}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
