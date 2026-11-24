#!/usr/bin/env python3
"""Development record of v3.1: every number the preregistration quotes from the development runs.

The development runs came before the freeze and shaped the plan. This script recomputes what the
preregistration says about them from the committed episode fingerprints, writes the record
(artifacts/v3_1_dev_record.json) and refreshes the generated tables of the section "Development
record" in docs/v3_1_preregistration.md.

  python scripts/v3_1_dev_record.py            # write the record and the tables
  python scripts/v3_1_dev_record.py --check    # fail if either is stale

Runs (fingerprints in artifacts/; no model text):
  d1_v3   first round, the v3 corpus (holdout and dev splits, 84 tasks), ten conditions
  d1_dev  first round, the development split of the v3.1 corpus (48 tasks), ten conditions
  d2_v3   second round, the v3 corpus, five conditions including the reading level
  d2_dev  second round, the development split of the v3.1 corpus, the same five conditions
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import analyze_v3_1 as plan  # noqa: E402
import v3_1_choose_wording as wording  # noqa: E402
import v3_1_lib as lib  # noqa: E402
import v3_1_replication_check as replication  # noqa: E402

RECORD = ROOT / 'artifacts/v3_1_dev_record.json'
DOC = ROOT / 'docs/v3_1_preregistration.md'
V3 = ('data/scenarios_v3/holdout.jsonl', 'data/scenarios_v3/dev.jsonl')
DEV = ('data/scenarios_v3_1/dev.jsonl',)
RUNS = {
    'd1_v3': ('artifacts/v3_1_dev_d1_v3_fingerprints.json.gz', V3, 'round 1, v3 corpus'),
    'd1_dev': ('artifacts/v3_1_dev_d1_fingerprints.json.gz', DEV, 'round 1, v3.1 development split'),
    'd2_v3': ('artifacts/v3_1_dev_d2_v3_fingerprints.json.gz', V3, 'round 2, v3 corpus'),
    'd2_dev': ('artifacts/v3_1_dev_d2_fingerprints.json.gz', DEV, 'round 2, v3.1 development split'),
}
LEVELS = ('B0', 'M', 'M_recover', 'M_reading', 'M_full', 'M_menu2', 'M_plan', 'M_plan_open', 'M_plan_text', 'M_seq', 'B2_plan')
KIND_COLUMNS = ('M_recover', 'M_reading', 'M_full', 'M_menu2', 'M_plan', 'M_seq')


def compact(item):
    effect = item['effect']
    if not effect:
        return {'decision': 'missing'}
    return {'left': effect['left_count'], 'right': effect['right_count'], 'episodes': effect['episodes_per_arm'],
            'structures': effect['n_tasks'], 'estimate_pp': round(100 * effect['estimate'], 1),
            'low_pp': round(100 * effect['ci95_low'], 1), 'high_pp': round(100 * effect['ci95_high'], 1),
            'decision': item['decision']}


def one_run(path, task_files):
    tasks = {}
    for name in task_files:
        tasks.update(lib.load_tasks(ROOT / name))
    rows = lib.read_fingerprints(ROOT / path)
    result = plan.analyze(rows, tasks)
    totals = {}
    for item in result['summary']:
        if item['class'] == 'all':
            cell = totals.setdefault(item['condition'], {'episodes': 0, 'exact_target': 0, 'unrequested_change': 0,
                                                         'unsafe_effect': 0})
            cell['episodes'] += item['n']
            for key in ('exact_target', 'unrequested_change', 'unsafe_effect'):
                cell[key] += item[key]
    contrasts = {i: compact(result['decisions'][i]) for i in result['decisions']}
    secondary = {i['id']: compact(i) for i in result['secondary']}
    return {'input': {'file': path, 'sha256': lib.sha256_file(ROOT / path)},
            'tasks': result['design']['tasks'], 'conditions': result['design']['conditions'],
            'episodes': result['design']['episodes'], 'seeds': result['design']['seeds'],
            'replay_disagreements': result['replay_disagreements'],
            'totals': totals, 'kinds': result['kinds']['rows'], 'claims': result['joint'],
            'contrasts': contrasts, 'draft': {i: secondary[i] for i in plan.DRAFT_IDS if i in secondary},
            'secondary': {k: v for k, v in secondary.items() if k not in plan.DRAFT_IDS}}, rows


def build():
    record = {'study': 'EviBound v3.1, development runs before the freeze (no confirmatory weight)', 'runs': {}}
    rows = {}
    for name, (path, task_files, _) in RUNS.items():
        if (ROOT / path).exists():
            record['runs'][name], rows[name] = one_run(path, task_files)
    # the rule for the wording of the plan review, applied to the first round as written
    pooled = rows['d1_v3'] + rows['d1_dev']
    conditions = sorted({r['condition'] for r in pooled})
    table = wording.table(pooled, conditions)
    record['wording_rule'] = {'table': {c: table[c] for c in ('M_recover',) + wording.WORDINGS},
                              'decision': wording.choose(table)}
    record['replication_of_v3'] = replication.compare(ROOT / 'artifacts/episode_fingerprints_v3_holdout.json.gz',
                                                      ROOT / RUNS['d1_v3'][0])
    return record


def cell(item):
    if item.get('decision') == 'missing' or 'left' not in item:
        return 'not run'
    return (f"{item['left']} vs {item['right']} of {item['episodes']}; {item['estimate_pp']:+.1f} "
            f"[{item['low_pp']:+.1f}, {item['high_pp']:+.1f}]; {item['structures']}; {item['decision']}")


def blocks(record):
    T = lib.table
    runs = record['runs']
    names = [n for n in RUNS if n in runs]
    label = {n: RUNS[n][2] for n in names}
    out = {}
    out['dev_runs'] = T(['Run', 'Tasks', 'Conditions', 'Episodes', 'Seeds'],
                        [[label[n], runs[n]['tasks'], ', '.join(f'`{c}`' for c in runs[n]['conditions']),
                          f"{runs[n]['episodes']:,}", ', '.join(map(str, runs[n]['seeds']))] for n in names])
    rows = []
    for condition in LEVELS:
        if not any(condition in runs[n]['totals'] for n in names):
            continue
        row = [f'`{condition}`']
        for n in names:
            v = runs[n]['totals'].get(condition)
            row.append(f"{v['exact_target']} / {v['unrequested_change']} of {v['episodes']}" if v else '')
        rows.append(row)
    out['dev_totals'] = T(['Condition'] + [label[n] for n in names], rows)
    rows = []
    for n in names:
        for kind, row in runs[n]['kinds'].items():
            if kind == 'no recovery turn':
                continue
            rows.append([label[n], kind, row['n'] if isinstance(row['n'], int) else '']
                        + [(f"{row['by_condition'][c]['exact_target']} / {row['by_condition'][c]['unrequested_change']}"
                            if c in row['by_condition'] else '') for c in KIND_COLUMNS])
    out['dev_kinds'] = T(['Run', 'Kind of turn', 'Turns'] + [f'`{c}`' for c in KIND_COLUMNS], rows)
    ids = [i for members in plan.JOINT.values() for i in members]
    claim_of = {i: name for name, members in plan.JOINT.items() for i in members}
    out['dev_claims'] = T(['Claim', 'Id'] + [label[n] for n in names],
                          [[claim_of[i], i] + [cell(runs[n]['contrasts'][i]) for n in names] for i in ids])
    out['dev_draft'] = T(['Id'] + [label[n] for n in names],
                         [[i] + [cell(runs[n]['draft'].get(i, {'decision': 'missing'})) for n in names] for i in plan.DRAFT_IDS])
    rule = record['wording_rule']
    fmt = lambda v: 'n/a' if v is None else f'{v:.1f}'  # noqa: E731
    out['dev_wording'] = T(['Wording', 'Completed at the boundary, class `full` (%)', 'Unrequested change, clean, class `part` (%)',
                            'Score', 'Completed, clean, class `full` (%)', 'Eligible'],
                           [[f'`{c}`', fmt(v['boundary_full_completion']), fmt(v['clean_part_unrequested']), fmt(v['score']),
                             fmt(v['clean_full_completion']),
                             'reference' if c == 'M_recover' else ('yes' if c in rule['decision']['eligible'] else 'no')]
                            for c, v in rule['table'].items()])
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
            problems.append(f'{DOC.relative_to(ROOT)} has stale development tables')
        print('\n'.join(problems) or 'development record and tables are current')
        return 1 if problems else 0
    RECORD.write_text(text)
    DOC.write_text(fresh)
    print(json.dumps({'record': str(RECORD.relative_to(ROOT)), 'runs': list(record['runs']),
                      'wording': record['wording_rule']['decision']['chosen']}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
