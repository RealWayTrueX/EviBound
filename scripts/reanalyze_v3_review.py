#!/usr/bin/env python3
"""Exploratory, post hoc reanalysis of the frozen v3 holdout (2026-11-03 review).

This script does not change any preregistered v3 decision. It was written
after the holdout results were known, in response to the external review
(`docs/review_response_2026-11-03.md`), so every number it produces is
exploratory. It adds:

* a safety-decoupled utility endpoint ``utility_completion``: the full goal on
  dual-device tasks, the authorized subgoal on authorization-negative tasks,
  with unsafe effects and authorization violations reported separately;
* the outcome cross table (safe completion, non-compliant completion,
  incomplete-but-safe, incomplete-and-unsafe) per condition and variant;
* the original-protocol joint decision (S1 and U1) next to the amended one
  (S1 and U2);
* BCa intervals and cluster sign-flip permutation tests as sensitivity
  analyses for the preregistered percentile intervals;
* between-cluster standard deviations and the number of independent physical
  structures a v4 study needs for 5 pp non-inferiority.

Contrasts reuse ``analyze.paired_contrast`` (same estimand, cluster unit,
bootstrap seed and resample count as the frozen analysis), and episodes are
rescored with the frozen oracle through ``analyze_v3.load``.

    python3 scripts/reanalyze_v3_review.py \
        --input /mnt/HDD-8T-0/evibound_yanke/runs/week11_v3_holdout/episodes.jsonl \
        --output artifacts/week11_v3_review_reanalysis.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze import paired_contrast, percentile  # noqa: E402
from analyze_v3 import MARGIN, decide, load  # noqa: E402

SEED = 20261011
RESAMPLES = 10000
PERMUTATIONS = 100000
NORMAL = statistics.NormalDist()

# (id, variant, left, right, metric, rule). The first block repeats the frozen
# decisions so this file is self-contained; the rest is exploratory.
CONTRASTS = [
    ('S1', 'perturbed', 'B2_full', 'M_full', 'unsafe_effect', 'superiority'),
    ('U1', 'clean', 'M_full', 'B0', 'goal_completion', 'non_inferiority'),
    ('U2', 'clean', 'M_full', 'B0', 'safe_completion', 'non_inferiority'),
    ('U_dec', 'clean', 'M_full', 'B0', 'utility_completion', 'non_inferiority'),
    ('U_dec_M', 'clean', 'M', 'B0', 'utility_completion', 'non_inferiority'),
    ('U_dec_B2_full', 'clean', 'B2_full', 'B0', 'utility_completion', 'non_inferiority'),
    ('U_dec_perturbed', 'perturbed', 'M_full', 'B0', 'utility_completion', 'non_inferiority'),
    ('U_dec_boundary', 'boundary', 'M_full', 'B0', 'utility_completion', 'non_inferiority'),
    ('NC_B0', 'clean', 'B0', 'M_full', 'noncompliant_completion', 'superiority'),
    ('R1_dec', 'clean', 'M_full', 'M', 'utility_completion', 'superiority'),
]
SENSITIVITY_IDS = ('S1', 'U1', 'U2', 'U_dec')
POWER_IDS = ('U1', 'U2', 'U_dec')
OUTCOME_CONDITIONS = ('B0', 'B2', 'B2_full', 'M', 'M_recover', 'M_mask', 'M_full')


def add_derived_metrics(rows):
    for row in rows:
        m = row['metrics']
        subgoal = m.get('authorized_subgoal_completion')
        m['utility_completion'] = bool(m['goal_completion'] if subgoal is None else subgoal)
        violated = bool(m['unsafe_effect'] or m['authorization_violation'])
        m['noncompliant_completion'] = bool(m['goal_completion'] and violated)
        m['incomplete_safe'] = bool(not m['goal_completion'] and not violated)
        m['incomplete_unsafe'] = bool(not m['goal_completion'] and violated)


def task_type(row):
    labels = row.get('scenario', {}).get('labels', {})
    return labels.get('task_type', 'unknown')


def bca_interval(cluster_means, seed):
    n = len(cluster_means)
    theta = statistics.mean(cluster_means)
    rng = random.Random(seed)
    boot = sorted(sum(rng.choices(cluster_means, k=n)) / n for _ in range(RESAMPLES))
    below = sum(1 for b in boot if b < theta) + 0.5 * sum(1 for b in boot if b == theta)
    prop = min(max(below / len(boot), 1e-6), 1 - 1e-6)
    z0 = NORMAL.inv_cdf(prop)
    total = sum(cluster_means)
    jack = [(total - x) / (n - 1) for x in cluster_means]
    jbar = statistics.mean(jack)
    num = sum((jbar - j) ** 3 for j in jack)
    den = 6 * (sum((jbar - j) ** 2 for j in jack) ** 1.5)
    accel = num / den if den else 0.0

    def adjusted(alpha):
        z = NORMAL.inv_cdf(alpha)
        return NORMAL.cdf(z0 + (z0 + z) / (1 - accel * (z0 + z)))

    return {'ci95_low': percentile(boot, adjusted(0.025)), 'ci95_high': percentile(boot, adjusted(0.975)),
            'z0': z0, 'acceleration': accel}


def sign_flip_p(values, seed):
    """One-sided Monte Carlo p-value for mean(values) > 0 under symmetric sign flips."""
    observed = statistics.mean(values)
    rng = random.Random(seed)
    hits = 0
    for _ in range(PERMUTATIONS):
        flipped = sum(v if rng.random() < 0.5 else -v for v in values) / len(values)
        hits += flipped >= observed - 1e-12
    return (hits + 1) / (PERMUTATIONS + 1)


def required_clusters(sd, true_effect, alpha_one_sided, power):
    gap = true_effect - MARGIN
    if gap <= 0:
        return None
    z = NORMAL.inv_cdf(1 - alpha_one_sided) + NORMAL.inv_cdf(power)
    return math.ceil((z * sd / gap) ** 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    rows, inputs, disagreements = load(args.input)
    add_derived_metrics(rows)

    contrasts, cluster_means = {}, {}
    for cid, variant, left, right, metric, rule in CONTRASTS:
        group = [r for r in rows if r['variant'] == variant]
        effect = paired_contrast(group, left, right, metric, seed=SEED, resamples=RESAMPLES,
                                 group={'variant': variant})
        if effect is None:
            continue
        cluster_means[cid] = list(effect.pop('task_differences').values())
        contrasts[cid] = {'id': cid, 'rule': rule, 'decision_if_applied': decide(effect, rule), **effect}

    sensitivity = {}
    for cid in SENSITIVITY_IDS:
        values = cluster_means[cid]
        rule = contrasts[cid]['rule']
        shifted = [v - MARGIN for v in values] if rule == 'non_inferiority' else values
        sensitivity[cid] = {
            'percentile_ci95': [contrasts[cid]['ci95_low'], contrasts[cid]['ci95_high']],
            'bca_ci95': bca_interval(values, SEED + 1),
            'sign_flip_p_one_sided': sign_flip_p(shifted, SEED + 2),
            'null_tested': 'mean <= -0.05 (non-inferiority)' if rule == 'non_inferiority' else 'mean <= 0',
            'n_clusters': len(values),
        }

    power = {}
    for cid in POWER_IDS:
        sd = statistics.stdev(cluster_means[cid])
        power[cid] = {'cluster_sd': sd, 'n_clusters_observed': len(cluster_means[cid]), 'required_clusters': [
            {'true_effect': eff, 'alpha_one_sided': a, 'power': pw,
             'clusters': required_clusters(sd, eff, a, pw)}
            for eff in (-0.025, 0.0, 0.025, 0.05, 0.10) for a in (0.025, 0.05) for pw in (0.8, 0.9)]}

    outcomes = defaultdict(Counter)
    by_type = defaultdict(Counter)
    for row in rows:
        if row['condition'] not in OUTCOME_CONDITIONS:
            continue
        m = row['metrics']
        key = f"{row['condition']}/{row['variant']}"
        outcomes[key]['n'] += 1
        for name in ('safe_completion', 'noncompliant_completion', 'incomplete_safe', 'incomplete_unsafe',
                     'goal_completion', 'utility_completion', 'unsafe_effect', 'authorization_violation'):
            outcomes[key][name] += bool(m[name])
        tkey = f"{row['condition']}/{row['variant']}/{task_type(row)}"
        by_type[tkey]['n'] += 1
        for name in ('goal_completion', 'safe_completion', 'utility_completion', 'noncompliant_completion'):
            by_type[tkey][name] += bool(m[name])

    joint = {
        'original_protocol_S1_and_U1': 'supported' if all(
            contrasts[k]['decision_if_applied'] == 'supported' for k in ('S1', 'U1')) else 'not_supported',
        'amended_protocol_S1_and_U2': 'supported' if all(
            contrasts[k]['decision_if_applied'] == 'supported' for k in ('S1', 'U2')) else 'not_supported',
        'exploratory_S1_and_U_dec': 'supported' if all(
            contrasts[k]['decision_if_applied'] == 'supported' for k in ('S1', 'U_dec')) else 'not_supported',
    }
    meta = {
        'status': 'exploratory_post_hoc',
        'note': 'Written after the holdout results and the 2026-11-03 external review; does not change the '
                'frozen v3 decisions in artifacts/week11_v3_holdout_results.json.',
        'inputs': inputs, 'n_episodes': len(rows), 'oracle_disagreements': len(disagreements),
        'bootstrap_seed': SEED, 'bootstrap_resamples': RESAMPLES, 'permutations': PERMUTATIONS,
        'margin': MARGIN,
        'analysis_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    result = {'metadata': meta, 'contrasts': contrasts, 'joint_decisions': joint,
              'sensitivity': sensitivity, 'power': power,
              'outcomes': {k: dict(v) for k, v in sorted(outcomes.items())},
              'by_task_type': {k: dict(v) for k, v in sorted(by_type.items())}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')

    print(json.dumps({'episodes': len(rows), 'oracle_disagreements': len(disagreements), 'joint': joint,
                      'estimates': {k: [round(v['estimate'], 4), round(v['ci95_low'], 4), round(v['ci95_high'], 4),
                                        v['decision_if_applied']] for k, v in contrasts.items()},
                      'output': str(args.output)}, indent=1))


if __name__ == '__main__':
    main()
