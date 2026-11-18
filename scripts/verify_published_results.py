#!/usr/bin/env python3
"""Recompute the published v2 and v3 results from raw traces and compare them
with the committed result records.

For each study whose traces are present under ``--traces`` this script:

1. hashes the trace files and compares them with the hashes committed before
   analysis (v2: ``artifacts/week8_main_results.json``; v3:
   ``artifacts/week11_v3_holdout_episodes.sha256``);
2. rescores every episode with the independent oracle (done by the frozen
   loaders) and counts disagreements with the stored metrics;
3. reruns the frozen analysis functions by import (``analyze.all_contrasts``,
   ``analyze_v3.analyze``) with the preregistered bootstrap seeds;
4. compares every primary estimate, interval, count and decision with the
   committed record.

Exit status 0 means every check that could run passed. A study without traces
is reported as skipped, not as passed.

Usage::

    python3 scripts/verify_published_results.py --traces /path/to/runs [--output report.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

TOLERANCE = 1e-12


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a, b):
    return abs(float(a) - float(b)) <= TOLERANCE


class Report:
    def __init__(self):
        self.checks = []

    def add(self, study, name, ok, detail=''):
        self.checks.append({'study': study, 'check': name, 'ok': bool(ok), 'detail': detail})
        print(f'  [{"ok" if ok else "FAIL"}] {name}' + (f' — {detail}' if detail else ''))


def verify_v2(traces, report):
    import analyze  # frozen analysis module (Week-8 main freeze)
    from evibound.oracle import score_episode

    study = 'v2_formal_test'
    record = json.loads((ROOT / 'artifacts/week8_main_results.json').read_text())
    folder = traces / 'week8_v2_main_test'
    expected_hashes = record['run']['seed_file_sha256']
    paths = [folder / name for name in sorted(expected_hashes)]
    if not all(path.exists() for path in paths):
        print(f'{study}: skipped (no traces under {folder})')
        return False
    print(f'{study}:')
    for path in paths:
        report.add(study, f'sha256 {path.name}', sha256(path) == expected_hashes[path.name])
    rows, disagreements, seen = [], 0, set()
    for path in paths:
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            identity = (row['split'], row['task_id'], row['variant'], row['condition'], row['seed'])
            if identity in seen:
                raise ValueError(f'duplicate episode {identity}')
            seen.add(identity)
            recomputed = score_episode(row['scenario'], row['trace'])
            stored = row.get('metrics', {})
            disagreements += any(key in stored and stored[key] != recomputed[key]
                                 for key in analyze.ORACLE_RATE_METRICS + analyze.ORACLE_COUNT_METRICS)
            row['metrics'] = analyze.merge_recomputed_metrics(stored, recomputed)
            rows.append(row)
    report.add(study, 'episode count', len(rows) == record['run']['episodes'], f'{len(rows)}')
    report.add(study, 'oracle rescoring disagreements', disagreements == record['run']['metric_disagreements'],
               f'{disagreements}')
    report.add(study, 'false blocks', sum(r['metrics']['false_blocks'] for r in rows) == record['run']['false_blocks'])
    effects = analyze.all_contrasts(rows, record['analysis']['bootstrap_seed'],
                                    record['analysis']['bootstrap_resamples'])

    def effect(variant, left, right, metric):
        for item in effects:
            if (item.get('variant') == variant and 'perturbation' not in item and item['left'] == left
                    and item['right'] == right and item['metric'] == metric):
                return item
        raise KeyError((variant, left, right, metric))

    def count(condition, variant, metric):
        return sum(bool(r['metrics'][metric]) for r in rows
                   if r['condition'] == condition and r['variant'] == variant)

    safety, utility = record['primary_results']['safety'], record['primary_results']['utility']
    s = effect('perturbed', 'B2', 'M', 'unsafe_effect')
    u = effect('clean', 'M', 'B0', 'goal_completion')
    for name, got, want in (('safety', s, safety), ('utility', u, utility)):
        report.add(study, f'{name} estimate and 95% CI',
                   close(got['estimate'], want['cluster_estimate']) and close(got['ci95_low'], want['ci95_low'])
                   and close(got['ci95_high'], want['ci95_high']),
                   f'{got["estimate"]:+.4f} [{got["ci95_low"]:+.4f}, {got["ci95_high"]:+.4f}]')
        report.add(study, f'{name} clusters', got['n_tasks'] == want['physical_clusters'], str(got['n_tasks']))
    report.add(study, 'raw counts',
               count('B2', 'perturbed', 'unsafe_effect') == safety['raw']['B2_unsafe_count']
               and count('M', 'perturbed', 'unsafe_effect') == safety['raw']['M_unsafe_count']
               and count('B0', 'clean', 'goal_completion') == utility['raw']['B0_goal_count']
               and count('M', 'clean', 'goal_completion') == utility['raw']['M_goal_count'],
               f'B2 {count("B2", "perturbed", "unsafe_effect")}/72 vs M {count("M", "perturbed", "unsafe_effect")}/72 unsafe; '
               f'B0 {count("B0", "clean", "goal_completion")}/72 vs M {count("M", "clean", "goal_completion")}/72 goal')
    safety_ok = s['estimate'] > 0 and s['ci95_low'] > 0
    margin = utility['non_inferiority_margin']
    utility_decision = ('unsupported' if u['estimate'] < margin
                        else 'supported' if u['ci95_low'] >= margin else 'inconclusive')
    report.add(study, 'decisions',
               ('supported' if safety_ok else 'not supported') == safety['preregistered_decision']
               and utility_decision == utility['preregistered_decision'],
               f'safety {safety["preregistered_decision"]}, utility {utility["preregistered_decision"]}, '
               f'joint {record["primary_results"]["joint_feasibility"]}')
    return True


def verify_v3(traces, report):
    import analyze_v3  # frozen analysis module (v3 preregistration freeze)

    study = 'v3_holdout'
    record = json.loads((ROOT / 'artifacts/week11_v3_holdout_results.json').read_text())
    path = traces / 'week11_v3_holdout' / 'episodes.jsonl'
    if not path.exists():
        print(f'{study}: skipped (no traces at {path})')
        return False
    print(f'{study}:')
    expected = (ROOT / 'artifacts/week11_v3_holdout_episodes.sha256').read_text().split()[0]
    report.add(study, 'sha256 episodes.jsonl', sha256(path) == expected)
    rows, _, disagreements = analyze_v3.load([path])
    report.add(study, 'episode count', len(rows) == record['metadata']['n_episodes'], f'{len(rows)}')
    report.add(study, 'oracle rescoring disagreements', len(disagreements) == 0, f'{len(disagreements)}')
    result = analyze_v3.analyze(rows, record['metadata']['bootstrap_seed'], record['metadata']['bootstrap_resamples'])
    for key, want in sorted(record['decisions'].items()):
        got = result['decisions'][key]
        same = (got['decision'] == want['decision'] and close(got['effect']['estimate'], want['effect']['estimate'])
                and close(got['effect']['ci95_low'], want['effect']['ci95_low'])
                and close(got['effect']['ci95_high'], want['effect']['ci95_high'])
                and got['effect']['n_tasks'] == want['effect']['n_tasks'])
        report.add(study, f'{key} estimate, 95% CI and decision', same,
                   f'{got["effect"]["estimate"]:+.4f} [{got["effect"]["ci95_low"]:+.4f}, '
                   f'{got["effect"]["ci95_high"]:+.4f}] {got["decision"]}')
    report.add(study, 'joint feasibility (frozen amended rule S1 and U2)',
               result['joint_feasibility'] == record['joint_feasibility'], result['joint_feasibility'])

    def cells(summary):
        return {(i['condition'], i['variant']): (i['unsafe_effect_count'], i['goal_completion_count'],
                                                 i['safe_completion_count'], i['false_blocks_total'])
                for i in summary}

    report.add(study, 'per-cell unsafe, goal, safe-completion and false-block counts (33 cells)',
               cells(result['summary']) == cells(record['summary']))
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--traces', type=Path, required=True,
                        help="directory laid out like the data disk's runs/ folder")
    parser.add_argument('--output', type=Path, help='write the check list as JSON')
    args = parser.parse_args(argv)
    report = Report()
    ran = [verify_v2(args.traces, report), verify_v3(args.traces, report)]
    failed = [c for c in report.checks if not c['ok']]
    summary = {'studies_verified': sum(ran), 'checks': len(report.checks), 'failed': len(failed)}
    print(json.dumps(summary))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({'summary': summary, 'checks': report.checks}, indent=1) + '\n')
    if not any(ran):
        print('no traces found: nothing was verified')
        return 2
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
