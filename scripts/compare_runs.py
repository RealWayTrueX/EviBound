#!/usr/bin/env python3
"""Compare a re-run of an experiment with the original raw traces, episode by episode.

Used by the independent reproduction (``scripts/reproduce.sh --gpu``): the
frozen runner is executed again with the same corpus, seeds, batch size and
model revision, and this script reports how far the new traces agree with the
recorded ones. Sampling on a GPU is not guaranteed to be bit-identical across
runs, so agreement is reported at three levels:

- ``first_proposal_text``: the model's first raw response is identical;
- ``executed_writes``: the executed write sequence is identical;
- ``oracle_outcomes``: unsafe effect, authorization violation, goal completion
  and safe completion are all identical (both sides rescored here by the
  independent oracle).

It also recomputes the preregistered primary contrasts on the compared
episodes for both runs, with the preregistered cluster bootstrap:

- ``--study v2``: B2 minus M unsafe effects (perturbed); M minus B0 goal
  completion (clean);
- ``--study v3``: S1 (B2_full minus M_full unsafe effects, perturbed), U1 and
  U2 (M_full minus B0 goal completion and safe completion, clean).

Usage::

    python3 scripts/compare_runs.py --study v2 --original runs/week8_v2_main_test/seed_11.jsonl \
        --rerun out/seed_11.jsonl --output out/reproduction_report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

OUTCOMES = ('unsafe_effect', 'authorization_violation', 'goal_completion', 'safe_completion')
RESAMPLES = 10000
STUDIES = {
    'v2': {'bootstrap_seed': 20260923, 'contrasts': (
        ('safety_B2_minus_M_unsafe', 'perturbed', 'B2', 'M', 'unsafe_effect'),
        ('utility_M_minus_B0_goal', 'clean', 'M', 'B0', 'goal_completion'))},
    'v3': {'bootstrap_seed': 20261011, 'contrasts': (
        ('S1_B2full_minus_Mfull_unsafe', 'perturbed', 'B2_full', 'M_full', 'unsafe_effect'),
        ('U1_Mfull_minus_B0_goal', 'clean', 'M_full', 'B0', 'goal_completion'),
        ('U2_Mfull_minus_B0_safe_completion', 'clean', 'M_full', 'B0', 'safe_completion'))},
}


def scorer(study):
    if study == 'v3':
        from evibound.oracle_v3 import score_episode_v3
        return score_episode_v3
    from evibound.oracle import score_episode
    return score_episode


def load(paths, study):
    score_episode = scorer(study)
    rows = {}
    for path in paths:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            identity = (row['task_id'], row['variant'], row['condition'], row['seed'])
            if identity in rows:
                raise ValueError(f'duplicate episode {identity} in {path}')
            row['metrics'] = {**row.get('metrics', {}), **score_episode(row['scenario'], row['trace'])}
            rows[identity] = row
    return rows


def writes(row):
    return [(e['device'], e['value']) for e in row['trace']['events'] if e.get('kind') == 'write']


def first_text(row):
    proposals = row.get('proposals') or [{}]
    return proposals[0].get('raw')


def contrasts(rows, study):
    import analyze

    out = {}
    spec = STUDIES[study]
    for name, variant, left, right, metric in spec['contrasts']:
        group = [r for r in rows if r['variant'] == variant]
        effect = analyze.paired_contrast(group, left, right, metric, seed=spec['bootstrap_seed'],
                                         resamples=RESAMPLES, group={'variant': variant})
        if effect:
            out[name] = {k: effect[k] for k in ('estimate', 'ci95_low', 'ci95_high', 'n_tasks', 'n_paired_episodes')}
            out[name]['left_count'] = sum(bool(r['metrics'][metric]) for r in group if r['condition'] == left)
            out[name]['right_count'] = sum(bool(r['metrics'][metric]) for r in group if r['condition'] == right)
            out[name]['episodes_per_condition'] = sum(r['condition'] == left for r in group)
    return out


def compare(original, rerun, study):
    common = sorted(original.keys() & rerun.keys())
    levels = Counter()
    by_condition = {}
    differing = []
    for identity in common:
        a, b = original[identity], rerun[identity]
        same_text = first_text(a) == first_text(b)
        same_writes = writes(a) == writes(b)
        same_outcomes = all(bool(a['metrics'][k]) == bool(b['metrics'][k]) for k in OUTCOMES)
        levels.update(first_proposal_text=same_text, executed_writes=same_writes, oracle_outcomes=same_outcomes)
        cell = by_condition.setdefault(identity[2], Counter())
        cell.update(episodes=1, oracle_outcomes=same_outcomes, executed_writes=same_writes)
        if not same_outcomes and len(differing) < 50:
            differing.append({'task_id': identity[0], 'variant': identity[1], 'condition': identity[2],
                              'seed': identity[3],
                              'original': {k: bool(a['metrics'][k]) for k in OUTCOMES},
                              'rerun': {k: bool(b['metrics'][k]) for k in OUTCOMES}})
    n = len(common)
    return {
        'episodes_compared': n,
        'only_in_original': len(original.keys() - rerun.keys()),
        'only_in_rerun': len(rerun.keys() - original.keys()),
        'agreement': {k: {'count': levels[k], 'rate': (levels[k] / n if n else None)}
                      for k in ('first_proposal_text', 'executed_writes', 'oracle_outcomes')},
        'agreement_by_condition': {c: dict(v) for c, v in sorted(by_condition.items())},
        'episodes_with_different_outcomes': differing,
        'contrasts_original_subset': contrasts([original[i] for i in common], study),
        'contrasts_rerun': contrasts([rerun[i] for i in common], study),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--study', choices=sorted(STUDIES), default='v2')
    parser.add_argument('--original', type=Path, nargs='+', required=True)
    parser.add_argument('--rerun', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    result = compare(load(args.original, args.study), load(args.rerun, args.study), args.study)
    result['study'] = args.study
    result['note'] = ('contrasts_original_subset is the original run restricted to the re-run episodes; '
                      'it equals the published estimate only when every seed was re-run')
    result['inputs'] = {
        'original': [{'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in args.original],
        'rerun': [{'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in args.rerun],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    agreement = result['agreement']
    print(f'compared {result["episodes_compared"]} episodes: identical first response '
          f'{agreement["first_proposal_text"]["count"]}, identical executed writes '
          f'{agreement["executed_writes"]["count"]}, identical oracle outcomes '
          f'{agreement["oracle_outcomes"]["count"]}')
    for name, *_ in STUDIES[args.study]['contrasts']:
        a, b = result['contrasts_original_subset'].get(name), result['contrasts_rerun'].get(name)
        if a and b:
            print(f'  {name}: original {a["estimate"]:+.4f} [{a["ci95_low"]:+.4f}, {a["ci95_high"]:+.4f}] '
                  f'({a["left_count"]} vs {a["right_count"]}); rerun {b["estimate"]:+.4f} '
                  f'[{b["ci95_low"]:+.4f}, {b["ci95_high"]:+.4f}] ({b["left_count"]} vs {b["right_count"]})')
    return 0 if result['episodes_compared'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
