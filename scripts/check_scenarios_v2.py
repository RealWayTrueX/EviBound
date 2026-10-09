#!/usr/bin/env python3
"""Independent pre-review checks for the DRAFT v2 corpus.

Implements the nine checks from docs/design_v2_dataset.md Section 6. Reads
only the written corpus files (not generator state), so it catches both
authoring errors and file corruption. Exit code 1 on any failure; writes a
machine-readable report to data/scenarios_v2/check_report.json.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scenario_v2_lib import (DEVICES, VALUES, LEVELS, state_legal, bfs_path,
                             goal_load, render_goal)

ROOT = Path('data/scenarios_v2')
REQUIRED = ['task_id', 'split', 'family', 'structure_id', 'perturbation',
            'instruction', 'context', 'initial', 'authorized', 'goal_present',
            'goal_absent', 'authorized_subgoal_present',
            'authorized_subgoal_absent', 'annotations']
ANN_REQUIRED = ['goal_variant', 'abstention_expected', 'clean_branch',
                'writes_needed_present', 'writes_needed_absent',
                'off_branch_noop', 'attack_expects_unsafe',
                'attack_expects_unauthorized', 'attack_explanation',
                'expected_safe_behavior']


def check_task(t, errors):
    tid = t.get('task_id', '<missing>')
    for k in REQUIRED:
        if k not in t:
            errors.append(f'{tid}: missing field {k}')
    if errors:
        return
    for k in ANN_REQUIRED:
        if k not in t['annotations']:
            errors.append(f'{tid}: missing annotation {k}')
    if t['perturbation'] not in ('tamper', 'replay'):
        errors.append(f'{tid}: bad perturbation {t["perturbation"]}')
    init = t['initial']
    if set(init) != {'light', 'fan', 'presence'}:
        errors.append(f'{tid}: initial keys != light/fan/presence')
    if not all(init[d] in VALUES for d in DEVICES) or not isinstance(init['presence'], bool):
        errors.append(f'{tid}: bad initial values')
    if not t['authorized'] or not set(t['authorized']) <= set(DEVICES):
        errors.append(f'{tid}: bad authorized set {t["authorized"]}')
    for d, v in {**t['goal_present'], **t['goal_absent']}.items():
        if d not in DEVICES or v not in VALUES:
            errors.append(f'{tid}: bad goal entry {d}={v}')
    if errors:
        return

    # 2/3. legality of initial and goal states
    for p in (True, False):
        if not state_legal(init, p):
            errors.append(f'{tid}: initial illegal under presence={p}')
    for branch, pres in (('goal_present', True), ('goal_absent', False)):
        probe = dict(init)
        probe.update(t[branch])
        if not state_legal(probe, pres):
            errors.append(f'{tid}: {branch} illegal under presence={pres}')

    # 4. reachability / write budgets
    is_a3 = set(t['authorized']) != set(DEVICES)
    presence = init['presence']
    clean = 'goal_present' if presence else 'goal_absent'
    off = 'goal_absent' if presence else 'goal_present'
    devs = DEVICES if is_a3 else t['authorized']
    paths = {}
    for branch, pres in (('goal_present', True), ('goal_absent', False)):
        paths[branch] = bfs_path(init, t[branch], pres, devs)
        if paths[branch] is None:
            errors.append(f'{tid}: {branch} unreachable within 3 writes')
    if errors:
        return
    n_clean, n_off = len(paths[clean]), len(paths[off])
    if not is_a3 and not (1 <= n_clean <= 3):
        errors.append(f'{tid}: clean branch needs {n_clean} writes')
    if is_a3 and not (1 <= n_clean <= 3):
        errors.append(f'{tid}: A3 full-goal clean branch needs {n_clean} writes')
    if (n_off == 0) != t['annotations']['off_branch_noop']:
        errors.append(f'{tid}: off_branch_noop annotation mismatch')
    for branch, key in (('goal_present', 'writes_needed_present'),
                        ('goal_absent', 'writes_needed_absent')):
        if len(paths[branch]) != t['annotations'][key]:
            errors.append(f'{tid}: annotation {key} mismatch')

    # 5. branch-flip property (construction guarantee of the testbed)
    if t['annotations']['clean_branch'] != clean:
        errors.append(f'{tid}: clean_branch annotation mismatch')

    # 6. A3-specific
    if is_a3:
        tempt = any(d not in t['authorized'] and init.get(d) != v
                    for b in ('goal_present', 'goal_absent')
                    for d, v in t[b].items())
        if not tempt:
            errors.append(f'{tid}: A3 task without unauthorized temptation')
        for sub, pres in (('authorized_subgoal_present', True),
                          ('authorized_subgoal_absent', False)):
            goal = t[sub]
            if goal is None:
                errors.append(f'{tid}: missing {sub}')
                continue
            sp = bfs_path(init, goal, pres, t['authorized'])
            if sp is None:
                errors.append(f'{tid}: {sub} unreachable with authorized devices')
            elif len(sp) == 0 and not t['annotations']['abstention_expected']:
                errors.append(f'{tid}: {sub} zero-write without abstention flag')
    else:
        if t['authorized_subgoal_present'] is not None or t['authorized_subgoal_absent'] is not None:
            errors.append(f'{tid}: non-A3 task carries subgoals')

    # 9. instruction lint
    ins = t['instruction'].lower()
    if 'authorized' in ins or 'permission' in ins:
        errors.append(f'{tid}: instruction leaks authorization metadata')
    for branch in ('goal_present', 'goal_absent'):
        if render_goal(t[branch]) not in t['instruction']:
            errors.append(f'{tid}: instruction missing {branch} rendering')


def stress_rules(t):
    stressed = set()
    for branch in ('goal_present', 'goal_absent'):
        g = t[branch]
        if g.get('light') in ('low', 'high'):
            stressed.add('R1')
        if g.get('fan') == 'high':
            stressed.update(('R2', 'R6'))
        if goal_load(g) == 3:
            stressed.add('R3')
        if g.get('fan') == 'high' and t['initial']['fan'] == 'off':
            stressed.add('R4')
        if g.get('light') == 'high':
            stressed.add('R5')
    return stressed


def main():
    all_errors, report = [], {}
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    structure_sets = {}
    for split in ('dev', 'pilot', 'test'):
        rows = [json.loads(l) for l in (ROOT / f'{split}.jsonl').read_text().splitlines()]
        text = (ROOT / f'{split}.jsonl').read_text()
        errors = []
        if hashlib.sha256(text.encode()).hexdigest() != manifest['splits'][split]['sha256']:
            errors.append(f'{split}: manifest sha256 mismatch')
        if manifest['splits'][split]['lifecycle'] if 'lifecycle' in manifest['splits'][split] else False:
            pass
        ids = [r['task_id'] for r in rows]
        if len(ids) != len(set(ids)):
            errors.append(f'{split}: duplicate task_ids')
        seen_struct = set()
        for t in rows:
            if t['split'] != split:
                errors.append(f'{t["task_id"]}: split field mismatch')
            key = (json.dumps(t['initial'], sort_keys=True),
                   json.dumps(t['goal_present'], sort_keys=True),
                   json.dumps(t['goal_absent'], sort_keys=True),
                   json.dumps(sorted(t['authorized'])))
            if key in seen_struct:
                errors.append(f'{t["task_id"]}: duplicate concrete structure within split')
            seen_struct.add(key)
            check_task(t, errors)
        # 7. rule-stress coverage per split
        coverage = set()
        for t in rows:
            coverage |= stress_rules(t)
        missing = {f'R{i}' for i in range(1, 7)} - coverage
        if missing:
            errors.append(f'{split}: rules never stressed by goal paths: {sorted(missing)}')
        # 5b. per-family perturbation diversity
        fams = {}
        for t in rows:
            fams.setdefault(t['family'], set()).add(t['perturbation'])
        for fam, ps in fams.items():
            if len(ps) < 2:
                errors.append(f'{split}/{fam}: only one perturbation type (W1 regression)')
        p_counts = {p: sum(1 for t in rows if t['perturbation'] == p)
                    for p in ('tamper', 'replay')}
        if p_counts['tamper'] != p_counts['replay']:
            errors.append(f'{split}: perturbation imbalance {p_counts}')
        structure_sets[split] = set(manifest['splits'][split]['structure_ids'])
        report[split] = {'tasks': len(rows), 'rule_coverage': sorted(coverage),
                         'perturbations': p_counts, 'errors': errors}
        all_errors.extend(errors)
    # 8. cross-split structure disjointness
    for a in ('dev', 'pilot', 'test'):
        for b in ('dev', 'pilot', 'test'):
            if a < b and structure_sets[a] & structure_sets[b]:
                all_errors.append(f'structure_id overlap {a}&{b}: '
                                  f'{sorted(structure_sets[a] & structure_sets[b])}')
    report['total_errors'] = len(all_errors)
    (ROOT / 'check_report.json').write_text(json.dumps(report, indent=2) + '\n')
    if all_errors:
        print(f'FAIL ({len(all_errors)} errors)')
        for e in all_errors[:40]:
            print(' -', e)
        sys.exit(1)
    total = sum(report[s]['tasks'] for s in ('dev', 'pilot', 'test'))
    print(f'OK: all checks passed ({total} tasks)')


if __name__ == '__main__':
    main()
