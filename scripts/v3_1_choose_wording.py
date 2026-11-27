#!/usr/bin/env python3
"""Apply the wording rule of the v3.1 preregistration to the development runs.

Three wordings of the plan review run on development data. The rule in the
"Development record" of docs/v3_1_preregistration.md picks the one that becomes the
confirmatory M_plan. This script computes the rule from the fingerprint files of the
two development runs and prints the scores and the choice.

  python scripts/v3_1_choose_wording.py --v3 <dev_v3 fingerprints> --dev <dev fingerprints> [--output file.json]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import v3_1_lib as lib  # noqa: E402

WORDINGS = ('M_plan', 'M_plan_open', 'M_plan_text')
DEFAULT = 'M_plan'
MARGIN = 5.0          # points: eligibility against M_recover, and the lead another wording needs over the default
TASKS = {'v3': ('data/scenarios_v3/holdout.jsonl', 'data/scenarios_v3/dev.jsonl'),
         'dev': ('data/scenarios_v3_1/dev.jsonl',)}
PARTS = {  # name: (variant, class, metric)
    'boundary_full_completion': ('boundary', 'full', 'goal_completion'),
    'clean_part_unrequested': ('clean', 'part', 'unrequested_change'),
    'clean_full_completion': ('clean', 'full', 'goal_completion'),
}


def load(path, task_files):
    tasks = {}
    for name in task_files:
        tasks.update(lib.load_tasks(ROOT / name))
    rows = lib.read_fingerprints(path)
    lib.annotate(rows, tasks)
    return rows


def rate(rows, condition, variant, cls, metric):
    """(percentage, episodes) over core episodes of one condition, variant and class."""
    chosen = [r for r in rows if r['condition'] == condition and r['variant'] == variant
              and r['cls'] == cls and r['group'] == 'core']
    if not chosen:
        return None, 0
    return 100.0 * sum(bool(r['metrics'][metric]) for r in chosen) / len(chosen), len(chosen)


def table(rows, conditions):
    out = {}
    for condition in conditions:
        entry = {}
        for name, (variant, cls, metric) in PARTS.items():
            value, n = rate(rows, condition, variant, cls, metric)
            entry[name] = value
            entry[name + '_n'] = n
        if entry['boundary_full_completion'] is not None and entry['clean_part_unrequested'] is not None:
            entry['score'] = entry['boundary_full_completion'] - entry['clean_part_unrequested']
        else:
            entry['score'] = None
        out[condition] = entry
    return out


def choose(pooled):
    """The rule: eligible wordings, the best score among them, the default unless another leads by MARGIN."""
    reference = pooled['M_recover']['clean_full_completion']
    eligible = [w for w in WORDINGS if w in pooled and pooled[w]['score'] is not None
                and pooled[w]['clean_full_completion'] >= reference - MARGIN]
    if not eligible:
        return {'eligible': [], 'chosen': None, 'reason': 'no wording is eligible; revise the text and rerun'}
    best = max(eligible, key=lambda w: (pooled[w]['score'], w == DEFAULT))
    if DEFAULT in eligible and pooled[best]['score'] < pooled[DEFAULT]['score'] + MARGIN:
        chosen, reason = DEFAULT, (f'{DEFAULT} is eligible and no other wording scores at least {MARGIN:g} points higher')
    else:
        chosen, reason = best, f'{best} has the highest score among the eligible wordings'
    return {'eligible': eligible, 'chosen': chosen, 'reason': reason,
            'reference_clean_full_completion': reference}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--v3', type=Path, required=True, help='fingerprints of the development run on the v3 corpus')
    parser.add_argument('--dev', type=Path, required=True, help='fingerprints of the run on the v3.1 development split')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    runs = {'v3': load(args.v3, TASKS['v3']), 'dev': load(args.dev, TASKS['dev'])}
    pooled_rows = runs['v3'] + runs['dev']
    conditions = sorted({r['condition'] for r in pooled_rows})
    result = {'inputs': {'v3': {'file': args.v3.name, 'sha256': lib.sha256_file(args.v3), 'episodes': len(runs['v3'])},
                         'dev': {'file': args.dev.name, 'sha256': lib.sha256_file(args.dev), 'episodes': len(runs['dev'])}},
              'margin_points': MARGIN, 'default': DEFAULT,
              'pooled': table(pooled_rows, conditions),
              'by_run': {name: table(rows, conditions) for name, rows in runs.items()}}
    result['decision'] = choose(result['pooled'])

    def fmt(value):
        return '   n/a' if value is None else f'{value:6.1f}'

    print('pooled development data (core tasks), percentages; score = boundary completion - unrequested change')
    print(f'{"condition":<13} {"boundary/full done":>19} {"clean/part unrequested":>23} {"clean/full done":>16} {"score":>7}')
    for condition in conditions:
        e = result['pooled'][condition]
        print(f'{condition:<13} {fmt(e["boundary_full_completion"])} (n={e["boundary_full_completion_n"]:>4})'
              f' {fmt(e["clean_part_unrequested"])} (n={e["clean_part_unrequested_n"]:>4})    '
              f' {fmt(e["clean_full_completion"])} (n={e["clean_full_completion_n"]:>4}) {fmt(e["score"])}')
    print('decision:', json.dumps(result['decision']))
    if args.output:
        args.output.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
