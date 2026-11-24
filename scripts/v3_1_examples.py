#!/usr/bin/env python3
"""Pick a few recovery turns per condition and review status from raw v3.1 traces.

For reading how the planner answers each kind of feedback. Each example holds the
interface's recovery payload, the planner's parsed plans (no raw model text) and the
outcome. Selection is deterministic: the first ``--per-group`` episodes of each group in
file order.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def plan(proposal):
    parsed = proposal.get('parsed') or {}
    actions = parsed.get('actions') if isinstance(parsed, dict) else None
    if proposal.get('parse_error') or not isinstance(actions, list):
        return None
    return [f"{a.get('device')}={a.get('value')}" if isinstance(a, dict) else '?' for a in actions]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--per-group', type=int, default=4)
    args = parser.parse_args()
    groups = defaultdict(list)
    for path in args.input:
        with path.open() as stream:
            for line in stream:
                row = json.loads(line)
                payload = row.get('recovery_payload')
                if not payload:
                    continue
                review = payload.get('plan_review') or {}
                done = bool(row['metrics']['goal_completion'])
                key = (row['condition'], row['variant'], row['recovery_trigger'],
                       review.get('status') or ('menu' if 'legal_writes_now' in payload else 'text'),
                       'done' if done else 'not done')
                if len(groups[key]) >= args.per_group:
                    continue
                scenario = row['scenario']
                events = row['trace']['events']
                groups[key].append({
                    'task_id': row['task_id'], 'seed': row['seed'], 'instruction': scenario['instruction'],
                    'authorized': scenario['authorized'], 'initial': scenario['initial'],
                    'goal_present': scenario['goal_present'], 'goal_absent': scenario['goal_absent'],
                    'first_plan': plan(row['proposals'][0]),
                    'events': [f"{e['kind']}:{e.get('device')}={e.get('value')}:{e['reason']}" for e in events],
                    'payload': {k: v for k, v in payload.items() if k != 'fresh_observation'},
                    'second_plan': plan(row['proposals'][1]) if len(row['proposals']) > 1 else None,
                    'final': {k: row['trace']['state'][k] for k in ('light', 'fan')},
                    'goal_completion': done, 'unsafe_effect': bool(row['metrics']['unsafe_effect']),
                })
    out = [{'condition': k[0], 'variant': k[1], 'trigger': k[2], 'kind': k[3], 'result': k[4], 'examples': v}
           for k, v in sorted(groups.items())]
    args.output.write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps({'groups': len(out), 'examples': sum(len(g['examples']) for g in out)}))


if __name__ == '__main__':
    main()
