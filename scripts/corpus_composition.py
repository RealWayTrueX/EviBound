#!/usr/bin/env python3
"""Machine-generated composition statistics for the v2 and v3 corpora.

Feeds `docs/datasheet_v2_v3.md`; reads only the frozen JSONL files.

    python3 scripts/corpus_composition.py --output artifacts/corpus_composition_v2_v3.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

LEVELS = {'off': 0, 'low': 1, 'high': 2}
SPLITS = {'v2': ('data/scenarios_v2', ('dev', 'pilot', 'test')),
          'v3': ('data/scenarios_v3', ('dev', 'holdout'))}


def legal(light, fan, presence):
    """The six rules for a static state (R4/R5 are transition rules and do not apply)."""
    if light != 'off' and not presence:
        return False
    if fan == 'high' and (not presence or light == 'off'):
        return False
    return LEVELS[light] + LEVELS[fan] <= 3


def stats(rows):
    labels = [r.get('labels', {}) for r in rows]
    branch_goal = [r['goal_present'] if r['initial']['presence'] else r['goal_absent'] for r in rows]
    states = {(l, f, p) for l in LEVELS for f in LEVELS for p in (True, False) if legal(l, f, p)}
    return {
        'tasks': len(rows),
        'physical_structures': len({r.get('physical_structure_id') for r in rows}),
        'task_type': dict(Counter(x.get('task_type', 'n/a') for x in labels)),
        'attack': dict(Counter(r['perturbation'] for r in rows)),
        'modality': dict(Counter(x.get('modality', 'presence_flag') for x in labels)),
        'language': dict(Counter(x.get('language', 'explicit') for x in labels)),
        'cells_modality_x_language': dict(Counter(f"{x.get('modality')}|{x.get('language')}" for x in labels)),
        'actual_presence': dict(Counter(str(r['initial']['presence']) for r in rows)),
        'presence_by_modality': {m: dict(Counter(str(r['initial']['presence']) for r, x in zip(rows, labels)
                                                if x.get('modality') == m))
                                 for m in sorted({x.get('modality') for x in labels if x.get('modality')})},
        'writes_needed_actual_branch': dict(Counter(str(x.get('writes_needed')) for x in labels)),
        'rules_stressed': dict(Counter(rule for x in labels for rule in x.get('rules_stressed', []))),
        'authorization_sets': dict(Counter('+'.join(sorted(r['authorized'])) for r in rows)),
        'distinct_initial_tuples': len({json.dumps(r['initial'], sort_keys=True) for r in rows}),
        'distinct_goal_present': len({json.dumps(r['goal_present'], sort_keys=True) for r in rows}),
        'distinct_goal_absent': len({json.dumps(r['goal_absent'], sort_keys=True) for r in rows}),
        'distinct_actual_branch_goals': len({json.dumps(g, sort_keys=True) for g in branch_goal}),
        'legal_static_world_states': len(states),
        'contexts': dict(Counter(r.get('context', 'n/a') for r in rows)),
        'families': dict(Counter(r['family'] for r in rows)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    out = {}
    for version, (folder, splits) in SPLITS.items():
        for split in splits:
            path = args.root / folder / f'{split}.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            out[f'{version}/{split}'] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), **stats(rows)}
    text = json.dumps(out, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text)


if __name__ == '__main__':
    main()
