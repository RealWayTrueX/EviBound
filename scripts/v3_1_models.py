#!/usr/bin/env python3
"""Exploratory arm of v3.1: the same study with a second planner model.

The 372 holdout tasks, the nine conditions and the three seeds were run again with Qwen3-8B
(docs/v3_1_second_model.md). This script puts that run next to the confirmatory one, writes the
record (artifacts/v3_1_models_record.json) and refreshes the generated tables of the section on
the second model in docs/v3_1_results.md.

Nothing here has confirmatory weight. The contrasts, the rules and the code that computes them
are those of the frozen plan (scripts/analyze_v3_1.py); a claim "carries over" when the frozen
rule gives the same decision for the second model as in the confirmatory run.

  python scripts/v3_1_models.py            # write the record and the tables
  python scripts/v3_1_models.py --check    # fail if either is stale
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
from evibound.recovery_v3_1 import LADDER, V31_CONDITIONS  # noqa: E402

RECORD = ROOT / 'artifacts/v3_1_models_record.json'
DOC = ROOT / 'docs/v3_1_results.md'
TASKS = 'data/scenarios_v3_1/holdout.jsonl'
RUNS = {
    'qwen25': ('artifacts/v3_1_holdout_fingerprints.json.gz', 'Qwen2.5-7B (the confirmatory run)'),
    'qwen3': ('artifacts/v3_1_model_qwen3_fingerprints.json.gz', 'Qwen3-8B (exploratory)'),
}
EXTRA = {'qwen3': {'files': 'artifacts/v3_1_model_qwen3_files.json', 'check': 'artifacts/v3_1_model_qwen3_check.json'}}
# secondary contrasts shown next to the thirteen confirmatory ones
SHOWN = (
    ('K36', 'Exact target, all tasks: reason − list (superiority)'),
    ('K31', 'Unrequested change on the attack battery: list − reason'),
    ('K43', 'Exact target in turns of the kind `revise`: reason − list'),
    ('K37', 'Exact target, all turns: reason and reading − reason'),
    ('K11', 'Safe completion under attack, attainable goals: list − reason'),
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


def one_model(name, path, tasks):
    rows = lib.read_fingerprints(ROOT / path)
    result = plan.analyze(rows, tasks)
    totals = {}
    for item in result['summary']:
        if item['class'] == 'all':
            cell = totals.setdefault(item['condition'], {'episodes': 0, 'exact_target': 0, 'unrequested_change': 0,
                                                         'unsafe_effect': 0, 'authorization_violation': 0,
                                                         'goal_completion': 0, 'retried': 0})
            cell['episodes'] += item['n']
            for key in cell:
                if key != 'episodes':
                    cell[key] += item[key]
    attacked = {item['condition']: {'episodes': item['n'], 'unsafe_effect': item['unsafe_effect'],
                                    'exact_target': item['exact_target']}
                for item in result['summary'] if item['class'] == 'all' and item['variant'] == 'perturbed'}
    contrasts = {i: compact(item) for i, item in result['decisions'].items()}
    contrasts.update({item['id']: compact(item) for item in result['secondary']})
    turns = {kind: row['by_condition']['M_recover']['n'] for kind, row in result['kinds']['rows'].items()}
    record = {'input': {'file': path, 'sha256': lib.sha256_file(ROOT / path)},
              'tasks': result['design']['tasks'], 'conditions': result['design']['conditions'],
              'episodes': result['design']['episodes'], 'seeds': result['design']['seeds'],
              'complete_matrix': result['design']['complete_matrix'],
              'replay_disagreements': result['replay_disagreements'],
              'claims': result['joint'], 'totals': totals, 'attacked': attacked, 'turns_by_kind': turns,
              'contrasts': contrasts}
    for key, extra in EXTRA.get(name, {}).items():
        if (ROOT / extra).exists():
            data = json.loads((ROOT / extra).read_text())
            if key == 'files':
                record['model_files'] = {'config': data.get('config'),
                                         'weights_sha256': {n: v['sha256'] for n, v in data['files'].items()
                                                            if n.endswith('.safetensors')}}
            else:
                record['answers'] = {k: data[k] for k in ('first_proposals', 'recovery_answers', 'ok')}
    return record


def build():
    tasks = lib.load_tasks(ROOT / TASKS)
    record = {'study': 'EviBound v3.1, exploratory arm: the same study with a second planner model (no confirmatory weight)',
              'models': {}}
    for name, (path, _) in RUNS.items():
        if (ROOT / path).exists():
            record['models'][name] = one_model(name, path, tasks)
    models = record['models']
    if len(models) == 2:
        base, other = models['qwen25'], models['qwen3']
        record['carried_over'] = {
            'claims': {c: other['claims'][c] == base['claims'][c] for c in sorted(base['claims'])},
            'contrasts': {i: other['contrasts'][i]['decision'] == base['contrasts'][i]['decision']
                          for i in [c['id'] for c in plan.CONFIRMATORY]},
            'same_sign': {i: (other['contrasts'][i]['estimate_pp'] > 0) == (base['contrasts'][i]['estimate_pp'] > 0)
                          for i in [c['id'] for c in plan.CONFIRMATORY]},
        }
    return record


def cell(item):
    if not item or item.get('decision') == 'missing':
        return 'not run'
    return (f"{item['left']} vs {item['right']} of {item['episodes']}; {item['estimate_pp']:+.1f} "
            f"[{item['low_pp']:+.1f}, {item['high_pp']:+.1f}]; {item['decision']}")


def blocks(record):
    T = lib.table
    models = record['models']
    names = [n for n in RUNS if n in models]
    label = {n: RUNS[n][1] for n in names}
    out = {}
    out['models_claims'] = T(['Claim', 'Statement'] + [label[n] for n in names] + ['Same decision'],
                             [[c, plan.CLAIMS[c]] + [models[n]['claims'][c].replace('_', ' ') for n in names]
                              + [('yes' if record['carried_over']['claims'][c] else 'no') if 'carried_over' in record else '']
                              for c in sorted(plan.CLAIMS)])
    shown = [(c['id'], c['label']) for c in plan.CONFIRMATORY] + list(SHOWN)
    out['models'] = T(['Id', 'Contrast'] + [label[n] for n in names],
                      [[i, text] + [cell(models[n]['contrasts'].get(i)) for n in names] for i, text in shown])
    rows = []
    for condition in V31_CONDITIONS:
        row = [f'`{condition}`', LADDER.get(condition, 'reference')]
        for n in names:
            v = models[n]['totals'].get(condition)
            row.append(f"{v['exact_target']} / {v['unrequested_change']} / {v['unsafe_effect']} of {v['episodes']}" if v else '')
        rows.append(row)
    out['models_totals'] = T(['Condition', 'Level'] + [label[n] for n in names], rows)
    bound = [c for c in V31_CONDITIONS if c in LADDER]
    lines = []
    for n in names:
        totals = models[n]['totals']
        unsafe = sum(totals[c]['unsafe_effect'] + totals[c]['authorization_violation'] for c in bound)
        episodes = sum(totals[c]['episodes'] for c in bound)
        attacked = models[n]['attacked']['B2_plan']
        lines.append(f"- {label[n]}: {unsafe} episodes with an unsafe effect or a write outside the scope in "
                     f"{episodes:,} episodes under the {len(bound)} evidence-bound conditions; under the guard that "
                     f"trusts the cited reading, {attacked['unsafe_effect']} of {attacked['episodes']:,} attacked episodes "
                     f"had an unsafe effect.")
    out['models_safety'] = '\n'.join(lines)
    out['models_turns'] = T(['Kind of recovery turn'] + [label[n] for n in names],
                            [[kind] + [models[n]['turns_by_kind'].get(kind, 0) for n in names] for kind in KINDS])
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    record = build()
    text = json.dumps(record, indent=1, sort_keys=True) + '\n'
    doc = DOC.read_text()
    fresh = lib.refresh_blocks(doc, blocks(record)) if '<!-- generated:models -->' in doc else doc
    if args.check:
        problems = []
        if not RECORD.exists() or RECORD.read_text() != text:
            problems.append(f'{RECORD.relative_to(ROOT)} is stale')
        if fresh != doc:
            problems.append(f'{DOC.relative_to(ROOT)} has stale tables on the second model')
        print('\n'.join(problems) or 'record and tables of the second model are current')
        return 1 if problems else 0
    RECORD.write_text(text)
    DOC.write_text(fresh)
    print(json.dumps({'record': str(RECORD.relative_to(ROOT)), 'models': list(record['models']),
                      'claims': {n: m['claims'] for n, m in record['models'].items()}}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
