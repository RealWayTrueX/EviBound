#!/usr/bin/env python3
"""Summarise a re-run next to the published results, without the original traces.

The independent reproduction re-runs the frozen runner on another machine.
This script reports, for the re-run alone: the count of each oracle outcome
per condition and variant, and the preregistered primary contrasts with the
preregistered cluster bootstrap. It prints them beside the values in the
committed results records (``artifacts/week8_main_results.json`` for v2,
``artifacts/week11_v3_holdout_results.json`` for v3).

It is the aggregate half of the reproduction. The episode-level half is
``scripts/compare_runs.py``, which needs the original traces or their
fingerprints.

Usage::

    python3 scripts/summarize_rerun.py --study v2 --rerun out/seed_11.jsonl out/seed_22.jsonl \
        out/seed_33.jsonl --output out/rerun_summary_v2.json

``--rerun`` takes raw ``.jsonl`` traces or fingerprint ``.json`` files.
The published v3 values cover all three seeds; a one-seed re-run has a third
of the episodes, so compare rates and estimates, not counts.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from compare_runs import STUDIES, contrasts  # noqa: E402
from episode_fingerprints import OUTCOMES, load_any  # noqa: E402


def cells(rows):
    table = defaultdict(lambda: {'episodes': 0, **{k: 0 for k in OUTCOMES}})
    for row in rows:
        cell = table[(row['condition'], row['variant'])]
        cell['episodes'] += 1
        for key in OUTCOMES:
            cell[key] += bool(row['metrics'][key])
    return [{'condition': c, 'variant': v, **table[(c, v)]} for c, v in sorted(table)]


def published(study):
    """The published value of each primary contrast, from the committed results records."""
    out = {}
    if study == 'v2':
        record = json.loads((ROOT / 'artifacts/week8_main_results.json').read_text())['primary_results']
        for name, key, left, right in (('safety_B2_minus_M_unsafe', 'safety', 'B2_unsafe_count', 'M_unsafe_count'),
                                       ('utility_M_minus_B0_goal', 'utility', 'M_goal_count', 'B0_goal_count')):
            part = record[key]
            out[name] = {'estimate': part['cluster_estimate'], 'ci95_low': part['ci95_low'],
                         'ci95_high': part['ci95_high'], 'left_count': part['raw'][left],
                         'right_count': part['raw'][right], 'episodes_per_condition': part['paired_episodes'],
                         'decision': part['preregistered_decision']}
    else:
        record = json.loads((ROOT / 'artifacts/week11_v3_holdout_results.json').read_text())
        counts = {(r['condition'], r['variant']): r for r in record['summary']}
        for name, variant, left, right, metric in STUDIES['v3']['contrasts']:
            decision = record['decisions'][name.split('_')[0]]
            effect = decision['effect']
            out[name] = {'estimate': effect['estimate'], 'ci95_low': effect['ci95_low'],
                         'ci95_high': effect['ci95_high'],
                         'left_count': counts[(left, variant)][f'{metric}_count'],
                         'right_count': counts[(right, variant)][f'{metric}_count'],
                         'episodes_per_condition': counts[(left, variant)]['n'],
                         'decision': decision['decision']}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--study', choices=sorted(STUDIES), required=True)
    parser.add_argument('--rerun', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    rows = list(load_any(args.rerun, args.study).values())
    result = {'study': args.study, 'episodes': len(rows),
              'seeds': sorted({row['seed'] for row in rows}),
              'tasks': len({row['task_id'] for row in rows}),
              'clusters': len({row['physical_structure_id'] for row in rows}),
              'cells': cells(rows), 'contrasts_rerun': contrasts(rows, args.study),
              'contrasts_published': published(args.study),
              'note': 'published values use every seed of the original run; compare rates and estimates '
                      'when the re-run has fewer seeds'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    print(f'{args.study} re-run: {result["episodes"]} episodes, seeds {result["seeds"]}, '
          f'{result["tasks"]} tasks, {result["clusters"]} clusters')
    for name, *_ in STUDIES[args.study]['contrasts']:
        new, old = result['contrasts_rerun'].get(name), result['contrasts_published'].get(name)
        if new and old:
            print(f'  {name}: re-run {new["estimate"]:+.4f} [{new["ci95_low"]:+.4f}, {new["ci95_high"]:+.4f}] '
                  f'({new["left_count"]} vs {new["right_count"]} of {new["episodes_per_condition"]}); '
                  f'published {old["estimate"]:+.4f} [{old["ci95_low"]:+.4f}, {old["ci95_high"]:+.4f}] '
                  f'({old["left_count"]} vs {old["right_count"]} of {old["episodes_per_condition"]}, '
                  f'{old["decision"]})')
    print('  condition/variant: episodes ' + ' '.join(OUTCOMES))
    for cell in result['cells']:
        print(f'  {cell["condition"]}/{cell["variant"]}: {cell["episodes"]} '
              + ' '.join(str(cell[k]) for k in OUTCOMES))
    return 0 if rows else 2


if __name__ == '__main__':
    raise SystemExit(main())
