"""Shared analysis machinery for v3.1: attainability labels, the paired split, contrasts.

Every function works on *light rows*: one dict per episode with its identity, its
physical-structure cluster, the executed writes, the number of proposals and the four
oracle outcomes. A light row is what ``scripts/episode_fingerprints.py`` stores, so the
whole v3.1 analysis can be recomputed from a committed fingerprint file without the raw
traces. ``fingerprint_v31`` adds, for v3.1 runs, the parsed plans and the rejection
reasons (still no model text).

Estimator and decision rule are the frozen ones: ``analyze.paired_contrast`` (physical
structures as clusters, seeds matched and averaged within a cluster, percentile
bootstrap) and ``analyze_v3.decide`` (non-inferiority margin of -5 points).
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from analyze import paired_contrast  # noqa: E402
from analyze_v3 import MARGIN, decide  # noqa: E402
from evibound.attainability import (CLASSES, OUTCOMES, attainability, initial_levels, outcome, replay,  # noqa: E402
                                    target_reached, unrequested_change)

BOOTSTRAP_SEED = 20261011
RESAMPLES = 10000
FORMAT_V31 = 'evibound-episode-fingerprints-v3.1'
SPLIT_KEYS = ('done', 'A', 'B', 'C', 'D', 'retried', 'reference_compliant', 'reference_violating')


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_tasks(path):
    return {task['task_id']: task for task in map(json.loads, Path(path).read_text().splitlines())}


def identity(row):
    return row['task_id'], row['variant'], row['condition'], row['seed']


# ---------------------------------------------------------------- fingerprints for v3.1 runs

def _plan(proposal):
    """Parsed writes of one proposal as [device, value] pairs; None when it did not parse."""
    if proposal.get('parse_error') or not isinstance(proposal.get('parsed'), dict):
        return None
    actions = proposal['parsed'].get('actions')
    if not isinstance(actions, list):
        return None
    return [[a.get('device'), a.get('value')] if isinstance(a, dict) else [None, None] for a in actions]


def fingerprint_v31(row, score_episode):
    """Light row of one raw v3.1 episode: no model text, enough for every v3.1 table."""
    metrics = score_episode(row['scenario'], row['trace'])
    events = row['trace']['events']
    raw = (row.get('proposals') or [{}])[0].get('raw')
    return {
        'task_id': row['task_id'], 'variant': row['variant'], 'condition': row['condition'], 'seed': row['seed'],
        'physical_structure_id': (row.get('physical_structure_id')
                                  or row['scenario'].get('physical_structure_id') or row['task_id']),
        'first': None if raw is None else hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16],
        'writes': [[e['device'], e['value']] for e in events if e.get('kind') == 'write'],
        'proposals': len(row.get('proposals') or []),
        'plans': [_plan(p) for p in row.get('proposals') or []],
        'rejects': [e.get('reason') for e in events if e.get('kind') == 'reject'],
        'trigger': row.get('recovery_trigger'),
        'review': ((row.get('recovery_payload') or {}).get('plan_review') or {}).get('status'),
        'metrics': {k: bool(metrics[k]) for k in ('unsafe_effect', 'authorization_violation',
                                                  'goal_completion', 'safe_completion')},
    }


def write_fingerprints(rows, path, sources, study):
    document = {'format': FORMAT_V31, 'study': study, 'episodes': len(rows), 'sources': sources,
                'rows': sorted(rows, key=lambda r: (r['task_id'], r['variant'], r['condition'], r['seed']))}
    text = json.dumps(document, sort_keys=True, separators=(',', ':'))
    path = Path(path)
    if path.suffix == '.gz':
        import gzip
        with path.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as stream:
            stream.write(text.encode())
    else:
        path.write_text(text + '\n')
    return document


def read_fingerprints(path):
    path = Path(path)
    if path.suffix == '.gz':
        import gzip
        document = json.loads(gzip.open(path).read().decode())
    else:
        document = json.loads(path.read_text())
    if document.get('format') != FORMAT_V31:
        raise ValueError(f'{path}: not a v3.1 fingerprint file')
    return document['rows']


# ---------------------------------------------------------------- labels

def annotate(rows, tasks):
    """Add the attainability class and the outcome labels to every light row (in place)."""
    cache = {}
    disagreements = []
    for row in rows:
        task = tasks[row['task_id']]
        att = cache.get(row['task_id'])
        if att is None:
            att = cache[row['task_id']] = attainability(task)
        final, replayed = replay(task, row['writes'])
        if any(bool(row['metrics'][key]) != replayed[key] for key in replayed):
            disagreements.append(identity(row))
        start = initial_levels(task)
        row['cls'] = att.cls
        row['outcome'] = outcome(task, row['writes'], att)
        clean_path = not (replayed['unsafe_effect'] or replayed['authorization_violation'])
        row['metrics'].update({
            'target_reached': target_reached(final, att),
            'exact_target': clean_path and final in att.targets,
            'unrequested_change': clean_path and row['outcome'] in ('extra', 'unrequested'),
            'off_target': clean_path and row['outcome'] == 'unrequested',
            'violation': not clean_path,
            'retried': row['proposals'] > 1,
        })
        row['final'] = list(final)
        row['start'] = list(start)
        row['shortest'] = att.shortest
        notes = task.get('annotations') or {}
        row['attack_relevant'] = bool(notes.get('attack_expects_unsafe') or notes.get('attack_expects_unauthorized'))
    return cache, disagreements


def cells(rows):
    out = defaultdict(dict)
    for row in rows:
        out[(row['variant'], row['condition'])][(row['task_id'], row['seed'])] = row
    return out


def class_table(tasks, attain):
    table = {}
    for cls in CLASSES:
        ids = [tid for tid in tasks if attain[tid].cls == cls]
        table[cls] = {
            'tasks': len(ids),
            'structures': len({tasks[tid]['physical_structure_id'] for tid in ids}),
            'shortest_plan': dict(sorted(Counter(str(attain[tid].shortest) for tid in ids).items())),
            'task_types': dict(sorted(Counter(tasks[tid].get('labels', {}).get('task_type', 'unlabelled')
                                              for tid in ids).items())),
        }
    return table


def split_table(rows, reference='B0', classes=('full',)):
    """Paired split against the unguarded run of the same first proposal.

    A: the reference completed compliantly and this condition did not complete.
    B: the reference completed with a violation and this condition did not complete.
    C: the reference did not complete and this condition did.
    D: neither completed.
    """
    by_cell = cells(rows)
    out = {}
    for (variant, condition), group in sorted(by_cell.items()):
        ref = by_cell.get((variant, reference), {})
        counts = Counter()
        for key, row in group.items():
            if row['cls'] not in classes or key not in ref:
                continue
            base, done = ref[key]['metrics'], bool(row['metrics']['goal_completion'])
            kind = 'compliant' if base['safe_completion'] else ('violating' if base['goal_completion'] else 'none')
            counts['n'] += 1
            counts['done'] += done
            counts['retried'] += row['proposals'] > 1
            counts['reference_compliant'] += kind == 'compliant'
            counts['reference_violating'] += kind == 'violating'
            counts['A'] += kind == 'compliant' and not done
            counts['B'] += kind == 'violating' and not done
            counts['C'] += kind == 'none' and done
            counts['D'] += kind == 'none' and not done
        if counts['n']:
            out.setdefault(variant, {})[condition] = {key: counts[key] for key in ('n',) + SPLIT_KEYS}
    return out


def outcome_table(rows):
    out = {}
    for row in rows:
        cell = out.setdefault(row['variant'], {}).setdefault(row['condition'], {}).setdefault(
            row['cls'], {label: 0 for label in OUTCOMES})
        cell[row['outcome']] += 1
    return out


def count(rows, variant, condition, predicate):
    return sum(1 for r in rows if r['variant'] == variant and r['condition'] == condition and predicate(r))


# ---------------------------------------------------------------- contrasts

def contrast(rows, spec, seed=BOOTSTRAP_SEED, resamples=RESAMPLES):
    """One paired contrast. ``spec`` keys: id, variants, left, right, metric, rule, and optionally
    classes (attainability classes to keep) and where (name of an extra subset, see SUBSETS)."""
    variants = tuple(spec['variants'])
    classes = tuple(spec.get('classes') or CLASSES)
    keep = SUBSETS[spec.get('where', 'all')]
    group_rows = [dict(r, task_id=f"{r['task_id']}|{r['variant']}") for r in rows
                  if r['variant'] in variants and r['cls'] in classes and keep(r)]
    group = {'variants': list(variants), 'classes': list(classes), 'where': spec.get('where', 'all')}
    effect = paired_contrast(group_rows, spec['left'], spec['right'], spec['metric'],
                             seed=seed, resamples=resamples, group=group)
    if effect is None:
        return {**spec, 'effect': None, 'decision': 'missing'}
    differences = list(effect.pop('task_differences').values())
    left = sum(float(r['metrics'][spec['metric']]) for r in group_rows if r['condition'] == spec['left'])
    right = sum(float(r['metrics'][spec['metric']]) for r in group_rows if r['condition'] == spec['right'])
    effect.update({'left_count': int(left), 'right_count': int(right),
                   'episodes_per_arm': effect['n_paired_episodes'],
                   'cluster_sd': statistics.stdev(differences) if len(differences) > 1 else None})
    return {**spec, 'effect': effect, 'decision': decide(effect, spec['rule'])}


SUBSETS = {
    'all': lambda row: True,
    'multi_write': lambda row: row.get('shortest', 0) >= 2,
    'single_write': lambda row: row.get('shortest', 0) == 1,
    'attack_relevant': lambda row: bool(row.get('attack_relevant')),
}


def structures_needed(sd, effect, power, margin=0.0, alpha=0.025):
    """Clusters for a one-sided test of mean > -margin at the given power (normal approximation)."""
    z = NormalDist().inv_cdf
    distance = effect + margin
    if not sd or distance <= 0:
        return None
    return int(-(-((z(1 - alpha) + z(power)) * sd / distance) ** 2 // 1))


def fmt_effect(item):
    effect = item['effect']
    if not effect:
        return 'missing'
    return (f"{100 * effect['estimate']:+.1f} pp [{100 * effect['ci95_low']:+.1f}, "
            f"{100 * effect['ci95_high']:+.1f}]")


# ---------------------------------------------------------------- generated blocks in documents

def _block(name, body):
    return f'<!-- generated:{name} -->\n{body.rstrip()}\n<!-- /generated:{name} -->'


def refresh_blocks(text, blocks):
    """Replace every ``<!-- generated:NAME -->`` block of a document with freshly built Markdown."""
    for name, body in blocks.items():
        start, end = f'<!-- generated:{name} -->', f'<!-- /generated:{name} -->'
        if start not in text or end not in text:
            raise ValueError(f'document has no generated block named {name}')
        head, rest = text.split(start, 1)
        _, tail = rest.split(end, 1)
        text = head + _block(name, body) + tail
    return text


def table(header, rows):
    lines = ['| ' + ' | '.join(header) + ' |', '|' + '|'.join('---' for _ in header) + '|']
    lines += ['| ' + ' | '.join(str(cell) for cell in row) + ' |' for row in rows]
    return '\n'.join(lines)
