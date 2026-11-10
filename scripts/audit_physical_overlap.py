#!/usr/bin/env python3
"""Audit physical-structure reuse across corpus versions and splits.

A task's physical structure is its initial state, both branch goals and its
authorization set; family labels, wording, modality and attack are not part
of it. The signature is computed here without importing generator or guard
code, so it can serve as an independent check for every corpus, including v4.

    python3 scripts/audit_physical_overlap.py --output artifacts/physical_overlap_audit.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

CORPORA = {
    'v1': ('data/scenarios', ('dev', 'pilot', 'test')),
    'v2': ('data/scenarios_v2', ('dev', 'pilot', 'test')),
    'v3': ('data/scenarios_v3', ('dev', 'holdout')),
}


def physical_signature(task: dict) -> str:
    """Canonical physical tuple: initial state, both goals, sorted authorization."""
    payload = [task['initial'], task['goal_present'], task['goal_absent'], sorted(task['authorized'])]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def load(root: Path):
    rows = []
    for version, (folder, splits) in CORPORA.items():
        for split in splits:
            path = root / folder / f'{split}.jsonl'
            for line in path.read_text().splitlines():
                task = json.loads(line)
                rows.append({'version': version, 'split': split, 'task_id': task['task_id'],
                             'signature': physical_signature(task)})
    return rows


def audit(rows):
    by_sig = defaultdict(list)
    for row in rows:
        by_sig[row['signature']].append(row)
    report = {'per_split': {}, 'within_version_cross_split': {}, 'cross_version': {}}
    for version, (_, splits) in CORPORA.items():
        version_rows = [r for r in rows if r['version'] == version]
        for split in splits:
            split_rows = [r for r in version_rows if r['split'] == split]
            report['per_split'][f'{version}/{split}'] = {
                'tasks': len(split_rows), 'physical_structures': len({r['signature'] for r in split_rows})}
        groups = {}
        for sig in {r['signature'] for r in version_rows}:
            members = [r for r in version_rows if r['signature'] == sig]
            if len({r['split'] for r in members}) > 1:
                groups[sig] = sorted(f"{r['split']}:{r['task_id']}" for r in members)
        report['within_version_cross_split'][version] = {
            'physical_structures': len({r['signature'] for r in version_rows}),
            'structures_spanning_splits': len(groups),
            'task_rows_involved': sum(len(v) for v in groups.values()),
            'groups': dict(sorted(groups.items())),
        }
    versions = list(CORPORA)
    for i, later in enumerate(versions):
        for earlier in versions[:i]:
            earlier_sigs = {r['signature'] for r in rows if r['version'] == earlier}
            per_split = {}
            for split in CORPORA[later][1]:
                hits = [r for r in rows if r['version'] == later and r['split'] == split
                        and r['signature'] in earlier_sigs]
                per_split[split] = {'task_rows': len(hits), 'structures': len({r['signature'] for r in hits}),
                                    'task_ids': sorted(r['task_id'] for r in hits)}
            report['cross_version'][f'{later}_vs_{earlier}'] = per_split
    report['union_physical_structures'] = len(by_sig)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = audit(load(args.root))
    text = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(text)
    summary = {k: v for k, v in report['per_split'].items()}
    print(json.dumps({'per_split': summary,
                      'cross_split': {v: {k: x[k] for k in ('physical_structures', 'structures_spanning_splits',
                                                             'task_rows_involved')}
                                      for v, x in report['within_version_cross_split'].items()},
                      'cross_version': {k: {s: (x['task_rows'], x['structures']) for s, x in v.items()}
                                        for k, v in report['cross_version'].items()},
                      'union_physical_structures': report['union_physical_structures']}, indent=1))


if __name__ == '__main__':
    main()
