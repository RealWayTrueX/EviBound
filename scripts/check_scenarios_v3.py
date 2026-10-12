#!/usr/bin/env python3
"""Independent pre-review checks for the DRAFT v3 recovery corpus.

Reuses the per-task v2 checks (schema, legality, BFS budgets, A3 semantics,
instruction lint) on the written files and adds the v3 rules:
- freshness: no physical structure from any v2 split; dev and holdout
  physically disjoint; a holdout structure appears in exactly two cells that
  differ in modality and language and carry opposite attacks;
- design: 4 modalities x 3 languages, 6 holdout tasks (3 tamper, 3 replay)
  and 1 dev task per cell;
- observation payloads match their modality and the reading conventions in
  the v3 prompt (motion <= 5 minutes means present);
- language: explicit and scene instructions render both goals exactly;
  everyday instructions use the house-convention phrases for every goal entry;
- labels agree with the task fields.
Writes data/scenarios_v3/check_report.json; exit code 1 on any failure.
"""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_scenarios_v2 import check_task, stress_rules  # noqa: E402
from scenario_v2_lib import DEVICES, render_goal  # noqa: E402
from generate_scenarios_v3 import (ABSENT_CAPTIONS, CELLS, LANGUAGES, MODALITIES,  # noqa: E402
                                   PRESENT_CAPTIONS, everyday_goal)

ROOT = Path('data/scenarios_v3')
V2_ROOT = Path('data/scenarios_v2')
SPLITS = ('dev', 'holdout')
PER_CELL = {'holdout': 6, 'dev': 1}


def caption_ok(text, context, pool):
    return any(text == item.format(ctx=context) for item in pool)


def payload_errors(task):
    tid, obs, ctx = task['task_id'], task.get('observation') or {}, task['context']
    modality, present, absent = obs.get('modality'), obs.get('payload_present'), obs.get('payload_absent')
    errors = []
    if modality not in MODALITIES:
        return [f'{tid}: unknown modality {modality}']
    if present == absent:
        errors.append(f'{tid}: payloads are identical')
    if modality == 'presence_flag' and (present is not True or absent is not False):
        errors.append(f'{tid}: presence_flag payloads must be true/false')
    if modality in ('motion_timer', 'multi_sensor'):
        near = present.get('minutes_since_motion') if isinstance(present, dict) else None
        far = absent.get('minutes_since_motion') if isinstance(absent, dict) else None
        if type(near) is not int or type(far) is not int or not (0 <= near <= 5 < far):
            errors.append(f'{tid}: motion minutes violate the <=5 presence convention')
    if modality == 'camera_caption' and not (
            caption_ok(present, ctx, PRESENT_CAPTIONS) and caption_ok(absent, ctx, ABSENT_CAPTIONS)):
        errors.append(f'{tid}: captions not from the reviewed caption pools')
    if modality == 'multi_sensor' and not (
            isinstance(present, dict) and isinstance(absent, dict)
            and caption_ok(present.get('camera'), ctx, PRESENT_CAPTIONS)
            and caption_ok(absent.get('camera'), ctx, ABSENT_CAPTIONS)):
        errors.append(f'{tid}: multi_sensor camera captions not from the reviewed pools')
    return errors


def language_errors(task, task_errors):
    """Swap the v2 render lint for a language-aware one on everyday tasks."""
    tid, language = task['task_id'], task.get('language')
    if language not in LANGUAGES:
        return [f'{tid}: unknown language {language}']
    if language != 'everyday':
        return []
    task_errors[:] = [e for e in task_errors if not (e.startswith(f'{tid}: instruction missing'))]
    return [f'{tid}: everyday instruction missing "{everyday_goal(task[b])}"'
            for b in ('goal_present', 'goal_absent') if everyday_goal(task[b]) not in task['instruction']]


def label_errors(task):
    tid, labels = task['task_id'], task.get('labels') or {}
    expected = {'modality': task['observation']['modality'], 'language': task['language'],
                'attack': task['perturbation'],
                'task_type': 'unauthorized' if set(task['authorized']) != set(DEVICES) else 'dual_device',
                'rules_stressed': sorted(stress_rules(task))}
    errors = [f'{tid}: label {k}={labels.get(k)!r} expected {v!r}' for k, v in expected.items()
              if labels.get(k) != v]
    low = 0 if expected['task_type'] == 'unauthorized' else 1  # A3: abstaining can be correct
    if not isinstance(labels.get('writes_needed'), int) or not low <= labels['writes_needed'] <= 3:
        errors.append(f'{tid}: label writes_needed out of range')
    display = task.get('labels_display') or {}
    for key in ('modality', 'language', 'attack', 'task_type'):
        if not (display.get(key, {}).get('en') and display.get(key, {}).get('zh')):
            errors.append(f'{tid}: missing display label {key}')
    return errors


def main(root=ROOT):
    manifest = json.loads((root / 'manifest.json').read_text())
    v2_ids = {json.loads(line)['physical_structure_id']
              for split in ('dev', 'pilot', 'test')
              for line in (V2_ROOT / f'{split}.jsonl').read_text().splitlines()}
    report, all_errors, physical_split = {}, [], {}
    for split in SPLITS:
        text = (root / f'{split}.jsonl').read_text()
        rows = [json.loads(line) for line in text.splitlines()]
        errors = []
        if hashlib.sha256(text.encode()).hexdigest() != manifest['splits'][split]['sha256']:
            errors.append(f'{split}: manifest sha256 mismatch')
        ids = [r['task_id'] for r in rows]
        if len(ids) != len(set(ids)):
            errors.append(f'{split}: duplicate task_ids')
        copies = defaultdict(list)
        for task in rows:
            tid = task['task_id']
            if task['split'] != split:
                errors.append(f'{tid}: split field mismatch')
            pid = task.get('physical_structure_id')
            if pid in v2_ids:
                errors.append(f'{tid}: physical structure reused from v2')
            if physical_split.setdefault(pid, split) != split:
                errors.append(f'{tid}: physical structure shared between dev and holdout')
            copies[pid].append(task)
            init = {d: task['initial'][d] for d in DEVICES}
            if {**init, **task['goal_present']} == {**init, **task['goal_absent']}:
                errors.append(f'{tid}: both branches require the same final state')
            task_errors = []
            check_task(task, task_errors)
            errors += language_errors(task, task_errors) + task_errors
            errors += payload_errors(task) + label_errors(task)
            if task['language'] == 'scene' and not all(
                    render_goal(task[b]) in task['instruction'] for b in ('goal_present', 'goal_absent')):
                errors.append(f'{tid}: scene definitions do not render both goals')
        want = 2 if split == 'holdout' else 1
        for pid, group in copies.items():
            if len(group) != want:
                errors.append(f'{split}: structure {pid} appears {len(group)} times (want {want})')
            elif want == 2:
                a, b = group
                if (a['observation']['modality'] == b['observation']['modality']
                        or a['language'] == b['language'] or a['perturbation'] == b['perturbation']):
                    errors.append(f'{split}: copies of {pid} must differ in modality, language and attack')
        cells = Counter((t['observation']['modality'], t['language']) for t in rows)
        attacks = Counter((t['observation']['modality'], t['language'], t['perturbation']) for t in rows)
        for cell in CELLS:
            if cells[cell] != PER_CELL[split]:
                errors.append(f'{split}: cell {cell} has {cells[cell]} tasks (want {PER_CELL[split]})')
            if split == 'holdout' and any(attacks[cell + (p,)] != 3 for p in ('tamper', 'replay')):
                errors.append(f'{split}: cell {cell} is not 3 tamper / 3 replay')
        coverage = set().union(*(stress_rules(t) for t in rows))
        missing = {f'R{i}' for i in range(1, 7)} - coverage
        if missing:
            errors.append(f'{split}: rules never stressed: {sorted(missing)}')
        families = defaultdict(set)
        for task in rows:
            families[task['family']].add(task['perturbation'])
        errors += [f'{split}/{f}: only one perturbation type' for f, p in families.items()
                   if len(p) < 2 and sum(t['family'] == f for t in rows) >= 2]
        counts = {p: sum(t['perturbation'] == p for t in rows) for p in ('tamper', 'replay')}
        if counts['tamper'] != counts['replay']:
            errors.append(f'{split}: perturbation imbalance {counts}')
        report[split] = {'tasks': len(rows), 'physical_structures': len(copies),
                         'rule_coverage': sorted(coverage), 'perturbations': counts,
                         'cells': {f'{m}/{l}': cells[(m, l)] for m, l in CELLS},
                         'authorization_negative': sum(set(t['authorized']) != set(DEVICES) for t in rows),
                         'errors': errors}
        all_errors.extend(errors)
    report['total_errors'] = len(all_errors)
    report['v2_physical_overlap'] = 0 if not any('reused from v2' in e for e in all_errors) else 'see errors'
    (root / 'check_report.json').write_text(json.dumps(report, indent=2) + '\n')
    if all_errors:
        print(f'FAIL ({len(all_errors)} errors)')
        for error in all_errors[:40]:
            print(' -', error)
        return 1
    print(f'OK: all v3 checks passed ({sum(report[s]["tasks"] for s in SPLITS)} tasks, '
          f'{sum(report[s]["physical_structures"] for s in SPLITS)} physical structures)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
