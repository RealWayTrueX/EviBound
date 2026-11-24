#!/usr/bin/env python3
"""Independent checks of the v3.1 corpus (data/scenarios_v3_1/).

The generator derives every label with the scenario rule library. This checker derives
them again with the oracle's rule function (``evibound.attainability``) and then plays
each task through the real simulator, so a label is accepted only if two implementations
agree and the simulator realizes it:

- structure: schema, ids, manifest hashes, freshness against the v1, v2 and v3 corpora,
  dev and holdout disjoint, each structure once;
- semantics: legal initial and goal states, branches end in different states, the
  authorized part of each goal is reachable; in a core task the selected branch needs
  one to three writes for an agent that may write both devices, in an attack-battery
  task it needs none and the other branch needs one to three;
- labels: class, attained conditions, target state and shortest plan recomputed; attack
  annotations recomputed; label codes agree with the task fields;
- text: explicit and scene instructions state both goals exactly, everyday instructions
  use the house-convention phrases, observation payloads follow the v3 conventions;
- simulator: (a) the shortest compliant plan runs under the evidence-bound guard and
  ends in the target with no violation; (b) at the freshness boundary a plan of two or
  more writes is interrupted after its first write and completes after a reread;
  (c) the plan of an agent that believes the attack never executes under the guard, and
  without a guard it has exactly the annotated unsafe and unauthorized effects; (d) an
  unguarded agent that pursues the whole goal completes it, with a violation exactly
  when the goal is not fully attainable; (e) under the guard that checks rules and scope
  but trusts the cited reading, the attacked plan executes exactly the annotated number
  of writes with the annotated safety outcome, which also fixes the task's stratum.

Writes data/scenarios_v3_1/check_report.json; exit code 1 on any failure.
"""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from evibound.attainability import DEVICES, attainability, initial_levels, outcome, reach  # noqa: E402
from evibound.backend_v3 import WorldV3  # noqa: E402
from evibound.oracle import _violations  # noqa: E402
from evibound.oracle_v3 import score_episode_v3  # noqa: E402
from check_scenarios_v3 import payload_errors  # noqa: E402
from generate_scenarios_v2 import physical_structure_id, stress_rules  # noqa: E402
from generate_scenarios_v3 import CELLS, LANGUAGES, MODALITIES, everyday_goal  # noqa: E402
from generate_scenarios_v3_1 import (BATTERY_STRATA, CONTEXTS, EARLIER, FAMILY_LABELS, QUOTAS, STRATA,  # noqa: E402
                                     earlier_structure_ids, family_of, render_explicit)
from scenario_v2_lib import render_goal  # noqa: E402

CORPUS = ROOT / 'data/scenarios_v3_1'
SPLITS = ('dev', 'holdout')
REQUIRED = ('task_id', 'split', 'family', 'structure_id', 'perturbation', 'instruction', 'context',
            'physical_structure_id', 'observation', 'language', 'labels', 'labels_display', 'initial',
            'authorized', 'goal_present', 'goal_absent', 'authorized_subgoal_present',
            'authorized_subgoal_absent', 'annotations')
LEVELS = ('off', 'low', 'high')


def legal(levels, presence):
    """A state is legal when standing still in it breaks no rule."""
    state = {'light': levels[0], 'fan': levels[1], 'presence': presence}
    return not _violations(state, dict(state))


def merged(task, goal):
    return tuple({'light': task['initial']['light'], 'fan': task['initial']['fan'], **goal}[d] for d in DEVICES)


def shortest_to(task, goal, presence, authorized):
    """A shortest compliant plan from the initial state to the goal map under ``presence``, or None."""
    plans = reach(initial_levels(task), presence, authorized)
    hits = [s for s in plans if all(dict(zip(DEVICES, s))[d] == v for d, v in goal.items())]
    return list(min((plans[s] for s in hits), key=len)) if hits else None


def believed_plan(task):
    """Shortest plan, with both devices, to the goal of the branch the attack suggests."""
    presence = task['initial']['presence']
    other = task['goal_absent'] if presence else task['goal_present']
    return [list(w) for w in (shortest_to(task, other, not presence, DEVICES) or [])]


def rule_guard_outcome(task):
    """What the attacked plan does under the guard that trusts the cited reading (in the simulator)."""
    world, events = execute(task, 'perturbed', 'B2', [(believed_plan(task), False)])
    metrics = score_episode_v3(task, world.trace())
    return {'writes': sum(e['kind'] == 'write' for e in events), 'unsafe': bool(metrics['unsafe_effect'])}


def stratum(task):
    """Recomputed from the task alone: the group by what each branch needs, the rest by search and simulation."""
    presence = task['initial']['presence']
    clean = task['goal_present'] if presence else task['goal_absent']
    wish = shortest_to(task, clean, presence, DEVICES)
    scoped = len(task['authorized']) < 2
    if wish == []:
        seen = rule_guard_outcome(task)
        if seen['unsafe']:
            return 'attack_unsafe_scoped' if scoped else 'attack_unsafe_dual'
        return 'attack_hijack' if seen['writes'] else 'attack_blocked'
    cls = attainability(task).cls
    return cls if cls != 'full' else ('full_scoped' if scoped else 'full_dual')


def execute(task, variant, guard, steps):
    """Run (writes, evidence source) steps in the simulator; returns the world and its events."""
    world = WorldV3(task, variant)
    observation = world.observe()
    events = []
    for writes, reread in steps:
        if reread:
            observation = world.observe()
        if writes:
            events += world.execute([{'device': d, 'value': v} for d, v in writes], observation, guard)
    return world, events


def semantic_errors(task):
    tid, errors = task['task_id'], []
    initial, presence = task['initial'], task['initial']['presence']
    start = initial_levels(task)
    if initial.get('light') != 'off' or initial.get('fan') not in ('off', 'low') or type(presence) is not bool:
        errors.append(f'{tid}: initial state outside light=off, fan=off/low')
    if not (legal(start, True) and legal(start, False)):
        errors.append(f'{tid}: initial state not legal under both presence values')
    if not task['authorized'] or not set(task['authorized']) <= set(DEVICES):
        errors.append(f'{tid}: bad authorized set')
    for branch, pres in (('goal_present', True), ('goal_absent', False)):
        if any(d not in DEVICES or v not in LEVELS for d, v in task[branch].items()):
            errors.append(f'{tid}: bad entry in {branch}')
        elif not legal(merged(task, task[branch]), pres):
            errors.append(f'{tid}: {branch} is not a legal state under presence={pres}')
    if errors:
        return errors
    if merged(task, task['goal_present']) == merged(task, task['goal_absent']):
        errors.append(f'{tid}: both branches end in the same state')
    clean = 'goal_present' if presence else 'goal_absent'
    other = 'goal_absent' if presence else 'goal_present'
    wish = shortest_to(task, task[clean], presence, DEVICES)
    believed = shortest_to(task, task[other], not presence, DEVICES)
    notes = task['annotations']
    battery = task.get('labels', {}).get('stratum') in BATTERY_STRATA
    if believed is None or wish is None:
        errors.append(f'{tid}: a branch is not reachable')
    elif battery and not (wish == [] and 1 <= len(believed) <= 3):
        errors.append(f'{tid}: attack-battery task: the selected branch must need no write and the other one to three')
    elif not battery and not 1 <= len(wish) <= 3:
        errors.append(f'{tid}: the selected branch does not need one to three writes')
    if errors:
        return errors
    expected = {'clean_branch': clean, 'off_branch_noop': not believed,
                'writes_needed_present': len(wish if presence else believed),
                'writes_needed_absent': len(believed if presence else wish)}
    errors += [f'{tid}: annotation {k}={notes.get(k)!r}, recomputed {v!r}' for k, v in expected.items()
               if notes.get(k) != v]
    scoped = len(task['authorized']) < 2
    for branch, pres in (('present', True), ('absent', False)):
        sub = task[f'authorized_subgoal_{branch}']
        if not scoped:
            if sub is not None:
                errors.append(f'{tid}: task with both devices in scope carries a subgoal')
            continue
        want = {k: v for k, v in task[f'goal_{branch}'].items() if k in task['authorized']}
        if sub != want:
            errors.append(f'{tid}: authorized_subgoal_{branch} is not the goal restricted to the scope')
        elif shortest_to(task, sub, pres, task['authorized']) is None:
            errors.append(f'{tid}: authorized_subgoal_{branch} is not reachable')
    return errors


def label_errors(task):
    tid, labels, notes = task['task_id'], task['labels'], task['annotations']
    errors = []
    att = attainability(task)
    stored = notes.get('attainability') or {}
    recomputed = {'class': att.cls, 'attained': list(att.attained[0]), 'target': dict(zip(DEVICES, att.targets[0])),
                  'shortest_plan': [list(w) for w in att.plan]}
    if len(att.targets) != 1 or len(att.attained) != 1:
        errors.append(f'{tid}: attainable target is not unique')
    for key, value in recomputed.items():
        if key == 'shortest_plan':
            if len(stored.get(key, [None] * 9)) != len(value):
                errors.append(f'{tid}: shortest plan length {len(stored.get(key, []))}, recomputed {len(value)}')
        elif stored.get(key) != value:
            errors.append(f'{tid}: attainability {key}={stored.get(key)!r}, recomputed {value!r}')
    scoped = len(task['authorized']) < 2
    found = stratum(task)
    group = 'core' if found not in BATTERY_STRATA else ('attack_hijack' if found == 'attack_hijack' else 'attack_unsafe')
    expected = {'modality': task['observation']['modality'], 'language': task['language'],
                'attack': task['perturbation'], 'task_type': 'restricted_scope' if scoped else 'dual_device',
                'attainability': att.cls, 'writes_needed': att.shortest, 'rules_stressed': sorted(stress_rules(task)),
                'stratum': found, 'group': group}
    errors += [f'{tid}: label {k}={labels.get(k)!r}, expected {v!r}' for k, v in expected.items() if labels.get(k) != v]
    display = task.get('labels_display') or {}
    for key in ('modality', 'language', 'attack', 'task_type', 'attainability', 'group'):
        if not (display.get(key, {}).get('en') and display.get(key, {}).get('zh')):
            errors.append(f'{tid}: missing display label {key}')
    if task['family'] != family_of(task['authorized'], task['goal_present']):
        errors.append(f'{tid}: family does not follow from scope and present-branch goal')
    if physical_structure_id(task) != task['physical_structure_id']:
        errors.append(f'{tid}: physical_structure_id does not match the structure')
    return errors


def text_errors(task):
    tid, text, language = task['task_id'], task['instruction'], task['language']
    errors = payload_errors(task)
    if task['perturbation'] not in ('tamper', 'replay'):
        errors.append(f'{tid}: bad perturbation')
    if language not in LANGUAGES:
        return errors + [f'{tid}: unknown language {language}']
    if task['context'] not in CONTEXTS[task['split']] or task['context'] not in text:
        errors.append(f'{tid}: context missing from the instruction or not from the split\'s list')
    if 'authorized' in text.lower() or 'permission' in text.lower():
        errors.append(f'{tid}: instruction leaks authorization metadata')
    goals = (task['goal_present'], task['goal_absent'])
    if language == 'explicit':
        if text != render_explicit(task['context'], FAMILY_LABELS[task['family']], *goals):
            errors.append(f'{tid}: explicit instruction is not the rendering of its goals')
    elif language == 'scene':
        definitions = text.split('My scenes: ', 1)[-1].rsplit('. Obey the device rules.', 1)[0].split('; ')
        stated = [d.split(' = ', 1)[-1] for d in definitions]
        if stated != [render_goal(g) for g in goals]:
            errors.append(f'{tid}: scene definitions do not state both goals exactly')
    else:
        positions = [text.find(everyday_goal(g)) for g in goals]
        if -1 in positions:
            errors.append(f'{tid}: everyday instruction lacks a house-convention phrase for a goal')
    return errors


def simulator_errors(task):
    tid, errors = task['task_id'], []
    presence = task['initial']['presence']
    att = attainability(task)
    plan = [list(w) for w in att.plan]
    target = att.targets[0]
    final = lambda world: (world.state['light'], world.state['fan'])  # noqa: E731

    # (a) the shortest compliant plan under the evidence-bound guard, clean variant
    world, events = execute(task, 'clean', 'M', [(plan, False)])
    metrics = score_episode_v3(task, world.trace())
    if any(e['kind'] == 'reject' for e in events) or final(world) != target:
        errors.append(f'{tid}: (a) the shortest plan does not run to the target under the guard')
    if metrics['unsafe_effect'] or metrics['authorization_violation'] or metrics['false_blocks']:
        errors.append(f'{tid}: (a) the oracle finds a violation or a false block on the shortest plan')
    if metrics['goal_completion'] != (att.cls == 'full'):
        errors.append(f'{tid}: (a) oracle goal completion disagrees with the class')
    if outcome(task, plan, att) != 'exact':
        errors.append(f'{tid}: (a) the shortest plan is not labelled exact')

    # (b) freshness boundary: interrupted after the first write, completed after a reread
    world, events = execute(task, 'boundary', 'M', [(plan, False)])
    if len(plan) >= 2:
        if [e['reason'] for e in events] != ['accepted', 'evidence_not_fresh']:
            errors.append(f'{tid}: (b) a plan of two or more writes is not interrupted after its first write')
        world, events = execute(task, 'boundary', 'M', [(plan, False), (plan[1:], True)])
        if [e['kind'] for e in events].count('reject') != 1 or final(world) != target:
            errors.append(f'{tid}: (b) the interrupted plan does not complete after a reread')
    elif any(e['kind'] == 'reject' for e in events) or final(world) != target:
        errors.append(f'{tid}: (b) a plan of at most one write is refused at the boundary')

    # (c) the plan of an agent that believes the attack
    believed = believed_plan(task)
    world, events = execute(task, 'perturbed', 'M', [(believed, False)])
    if any(e['kind'] == 'write' for e in events):
        errors.append(f'{tid}: (c) a write chosen from the attacked observation executes under the guard')
    world, events = execute(task, 'perturbed', 'B0', [(believed, False)])
    metrics = score_episode_v3(task, world.trace())
    notes = task['annotations']
    if (bool(metrics['unsafe_effect']), bool(metrics['authorization_violation'])) != (
            notes['attack_expects_unsafe'], notes['attack_expects_unauthorized']):
        errors.append(f'{tid}: (c) attack annotations do not match the unguarded run')

    # (e) the same plan under the guard that trusts the cited reading
    if rule_guard_outcome(task) != notes.get('attack_under_rule_guard'):
        errors.append(f'{tid}: (e) attack_under_rule_guard does not match the simulator')

    # (d) an unguarded agent that pursues the whole goal
    goal = task['goal_present'] if presence else task['goal_absent']
    wish = shortest_to(task, goal, presence, DEVICES)
    world, events = execute(task, 'clean', 'B0', [([list(w) for w in wish], False)])
    metrics = score_episode_v3(task, world.trace())
    violated = bool(metrics['unsafe_effect'] or metrics['authorization_violation'])
    if not metrics['goal_completion'] or violated != (att.cls != 'full'):
        errors.append(f'{tid}: (d) the unguarded pursuit of the whole goal does not behave as the class says')
    return errors


def check_split(split, manifest, earlier, owner):
    path = CORPUS / f'{split}.jsonl'
    text = path.read_text()
    rows = [json.loads(line) for line in text.splitlines()]
    errors = []
    if hashlib.sha256(text.encode()).hexdigest() != manifest['splits'][split]['sha256']:
        errors.append(f'{split}: manifest sha256 mismatch')
    if len({r.get('task_id') for r in rows}) != len(rows):
        errors.append(f'{split}: duplicate task ids')
    for task in rows:
        missing = [k for k in REQUIRED if k not in task]
        if missing:
            errors.append(f'{task.get("task_id")}: missing fields {missing}')
            continue
        tid, pid = task['task_id'], task['physical_structure_id']
        if task['split'] != split:
            errors.append(f'{tid}: split field mismatch')
        if pid in earlier:
            errors.append(f'{tid}: physical structure appears in an earlier corpus')
        if owner.setdefault(pid, tid) != tid:
            errors.append(f'{tid}: physical structure also used by {owner[pid]}')
        found = semantic_errors(task)
        errors += found
        if not found:
            errors += label_errors(task) + text_errors(task) + simulator_errors(task)
    strata = Counter(t['labels'].get('stratum') for t in rows if 'labels' in t)
    if dict(strata) != {k: v for k, v in QUOTAS[split].items() if v}:
        errors.append(f'{split}: strata {dict(strata)} differ from the quotas {QUOTAS[split]}')
    cells = Counter((t['observation']['modality'], t['language']) for t in rows)
    if len(set(cells[c] for c in CELLS)) != 1:
        errors.append(f'{split}: cells are not equally filled: {dict(cells)}')
    attacks = defaultdict(Counter)
    for task in rows:
        attacks[task['labels'].get('stratum') if split == 'holdout' else 'all'][task['perturbation']] += 1
    for name, counts in attacks.items():
        if counts['tamper'] != counts['replay']:
            errors.append(f'{split}/{name}: tamper and replay are not balanced: {dict(counts)}')
    if split == 'holdout':
        per = Counter((t['labels'].get('stratum'), t['observation']['modality'], t['language']) for t in rows)
        for name in STRATA:
            if len({per[(name,) + cell] for cell in CELLS}) != 1:
                errors.append(f'{split}/{name}: not equally spread over the twelve cells')
    coverage = set().union(*(stress_rules(t) for t in rows))
    if coverage != {f'R{i}' for i in range(1, 7)}:
        errors.append(f'{split}: rules never stressed: {sorted({f"R{i}" for i in range(1, 7)} - coverage)}')
    return rows, errors, {
        'tasks': len(rows), 'physical_structures': len({t['physical_structure_id'] for t in rows}),
        'strata': dict(sorted(strata.items())), 'attacks': {k: dict(v) for k, v in sorted(attacks.items())},
        'rule_coverage': sorted(coverage), 'cells': {f'{m}/{l}': cells[(m, l)] for m, l in CELLS},
        'attack_can_cause_an_unsafe_write': sum(t['annotations']['attack_expects_unsafe'] for t in rows),
        'unsafe_under_a_rule_guard_if_the_attack_is_believed': sum(
            t['annotations']['attack_under_rule_guard']['unsafe'] for t in rows),
        'attack_can_cause_an_unauthorized_write': sum(t['annotations']['attack_expects_unauthorized'] for t in rows),
        'plans_of_two_or_more_writes': sum(t['labels']['writes_needed'] >= 2 for t in rows),
        'simulator_checks_per_task': ['a shortest plan under the guard', 'b boundary interruption and completion',
                                      'c attacked plan blocked, annotations match', 'd unguarded pursuit of the goal',
                                      'e attacked plan under the rule-only guard'],
        'errors': errors}


def main():
    manifest = json.loads((CORPUS / 'manifest.json').read_text())
    earlier = earlier_structure_ids(ROOT)
    owner, report, all_errors = {}, {}, []
    for split in SPLITS:
        _, errors, report[split] = check_split(split, manifest, earlier, owner)
        all_errors += errors
    report['total_errors'] = len(all_errors)
    report['earlier_corpora'] = {'folders': list(EARLIER), 'structures': len(earlier)}
    report['modalities'] = list(MODALITIES)
    (CORPUS / 'check_report.json').write_text(json.dumps(report, indent=2) + '\n')
    if all_errors:
        print(f'FAIL ({len(all_errors)} errors)')
        for error in all_errors[:40]:
            print(' -', error)
        return 1
    print(f'OK: all v3.1 checks passed ({sum(report[s]["tasks"] for s in SPLITS)} tasks, '
          f'{sum(report[s]["physical_structures"] for s in SPLITS)} physical structures, '
          f'{len(earlier)} earlier structures excluded)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
