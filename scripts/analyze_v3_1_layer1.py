#!/usr/bin/env python3
"""v3.1 layer 1: policy-attainable goals on the frozen v3 holdout (exploratory, post hoc).

For every task of the v3 holdout an exhaustive search gives what a rule-abiding agent could
have delivered. The 7,128 frozen episodes are then compared with that reference: the ceiling
of raw completion, an exact split of the raw gap, a paired split of every guard condition
against the unguarded run of the same first proposal, and a label for where each episode
ended. Inputs are committed files only; no GPU and no model.

    python3 scripts/analyze_v3_1_layer1.py            # write artifacts/v3_1_layer1_attainability.json
    python3 scripts/analyze_v3_1_layer1.py --check    # recompute; fail if the record or the document is stale
    python3 scripts/analyze_v3_1_layer1.py --write-doc  # refresh the generated tables of the document
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import v3_1_lib as lib  # noqa: E402
from episode_fingerprints import load_any  # noqa: E402

SCENARIOS = ROOT / 'data/scenarios_v3/holdout.jsonl'
FINGERPRINTS = ROOT / 'artifacts/episode_fingerprints_v3_holdout.json.gz'
RECORD = ROOT / 'artifacts/v3_1_layer1_attainability.json'
DOC = ROOT / 'docs/v3_1_layer1_attainability.md'
GUARDS = ('B2', 'M', 'M_repair', 'M_confirm_empty', 'M_recover', 'M_mask', 'B2_recover', 'B2_full', 'M_full')
SHOWN = ('M', 'M_repair', 'M_recover', 'M_mask', 'M_full', 'B2_recover', 'B2_full')
NI, SUP = 'non_inferiority', 'superiority'


def spec(cid, variants, left, right, metric, rule, classes=('full',), note=''):
    return {'id': cid, 'variants': list(variants), 'left': left, 'right': right, 'metric': metric,
            'rule': rule, 'classes': list(classes), 'note': note}


CONTRASTS = [
    spec('att_full_vs_B0_clean', ['clean'], 'M_full', 'B0', 'goal_completion', NI),
    spec('att_B2full_vs_B0_clean', ['clean'], 'B2_full', 'B0', 'goal_completion', NI),
    spec('att_recover_vs_B0_clean', ['clean'], 'M_recover', 'B0', 'goal_completion', NI),
    spec('att_M_vs_B0_clean', ['clean'], 'M', 'B0', 'goal_completion', NI),
    spec('att_full_vs_M_clean', ['clean'], 'M_full', 'M', 'goal_completion', SUP),
    spec('att_full_vs_B2full_clean', ['clean'], 'M_full', 'B2_full', 'goal_completion', NI),
    spec('att_full_vs_B0_attacked', ['perturbed'], 'M_full', 'B0', 'goal_completion', NI),
    spec('att_full_vs_B0_boundary', ['boundary'], 'M_full', 'B0', 'goal_completion', NI),
    spec('att_full_vs_B2full_boundary', ['boundary'], 'M_full', 'B2_full', 'goal_completion', NI),
    spec('att_recover_vs_B0_boundary', ['boundary'], 'M_recover', 'B0', 'goal_completion', NI),
    spec('reason_vs_silence_clean', ['clean'], 'M_recover', 'M', 'goal_completion', SUP,
         note='what one sentence naming the rule adds'),
    spec('menu_gain_clean', ['clean'], 'M_full', 'M_recover', 'goal_completion', SUP,
         note='what the list of legal writes adds on clean tasks'),
    spec('menu_gain_attacked', ['perturbed'], 'M_full', 'M_recover', 'goal_completion', SUP,
         note='the same under attack'),
    spec('menu_loss_boundary', ['boundary'], 'M_recover', 'M_full', 'goal_completion', SUP,
         note='what the list costs at the freshness boundary'),
    spec('menu_off_target_part', ['clean', 'boundary'], 'M_full', 'M_recover', 'off_target', SUP,
         classes=('part',), note='ends in a permitted state nobody asked for; 4 structures only'),
    spec('target_all_full_vs_B0_clean', ['clean'], 'M_full', 'B0', 'target_reached', NI,
         classes=lib.CLASSES, note='attainable target reached, all classes (the earlier U_dec)'),
]


def load():
    tasks = lib.load_tasks(SCENARIOS)
    rows = list(load_any([FINGERPRINTS], 'v3').values())
    attain, disagreements = lib.annotate(rows, tasks)
    return tasks, rows, attain, disagreements


def checks(tasks, rows, attain, disagreements):
    structures = {}
    for tid, task in tasks.items():
        structures.setdefault(task['physical_structure_id'], set()).add(attain[tid].cls)
    dual = [tid for tid, t in tasks.items() if t['labels']['task_type'] == 'dual_device']
    scoped = [tid for tid, t in tasks.items() if t['labels']['task_type'] == 'unauthorized']

    def subgoal_matches(tid):
        task, att = tasks[tid], attain[tid]
        sub = task['authorized_subgoal_present'] if task['initial']['presence'] else task['authorized_subgoal_absent']
        # the corpus subgoal lists the goal's entries on authorized devices; applied to the initial
        # levels it must give the end state the search found
        levels = {'light': task['initial']['light'], 'fan': task['initial']['fan'], **(sub or {})}
        return att.targets == ((levels['light'], levels['fan']),)

    beyond = [r for r in rows if r['cls'] != 'full' and r['metrics']['goal_completion']]
    return {
        'episodes': len(rows),
        'replay_disagreements': len(disagreements),
        'structures_with_more_than_one_class': sum(len(v) > 1 for v in structures.values()),
        'dual_device_tasks': len(dual),
        'dual_device_class_full': sum(attain[t].cls == 'full' for t in dual),
        'dual_device_shortest_equals_annotation': sum(
            attain[t].shortest == tasks[t]['labels']['writes_needed'] for t in dual),
        'scoped_tasks': len(scoped),
        'scoped_target_equals_corpus_subgoal': sum(subgoal_matches(t) for t in scoped),
        'tasks_with_more_than_one_target_state': sum(len(a.targets) > 1 for a in attain.values()),
        'completions_of_a_goal_that_is_not_attainable': {
            'total': len(beyond), 'by_condition': dict(sorted(Counter(r['condition'] for r in beyond).items())),
            'with_a_violation': sum(r['metrics']['violation'] for r in beyond)},
    }


def ceiling(rows):
    per_cell = lib.count(rows, 'clean', 'B0', lambda r: True)
    full = lib.count(rows, 'clean', 'B0', lambda r: r['cls'] == 'full')
    raw = {c: lib.count(rows, 'clean', c, lambda r: r['metrics']['goal_completion'])
           for c in ('B0', 'B2', 'M', 'M_recover', 'B2_full', 'M_full')}
    on_full = {c: lib.count(rows, 'clean', c, lambda r: r['cls'] == 'full' and r['metrics']['goal_completion'])
               for c in raw}
    return {'episodes_per_cell': per_cell, 'attainable_per_cell': full, 'raw_completion_clean': raw,
            'attainable_completion_clean': on_full,
            'gap_M_full_minus_B0': {
                'raw': raw['M_full'] - raw['B0'],
                'goals_not_attainable': (raw['M_full'] - on_full['M_full']) - (raw['B0'] - on_full['B0']),
                'goals_attainable': on_full['M_full'] - on_full['B0']}}


def paired_table(rows, guard='M_full'):
    by = lib.cells(rows)
    ref, grd = by[('clean', 'B0')], by[('clean', guard)]
    out = {k: {'episodes': 0, 'guard_completed': 0} for k in ('compliant', 'violating', 'none')}
    for key, base in ref.items():
        if base['cls'] != 'full':
            continue
        kind = ('compliant' if base['metrics']['safe_completion']
                else 'violating' if base['metrics']['goal_completion'] else 'none')
        out[kind]['episodes'] += 1
        out[kind]['guard_completed'] += bool(grd[key]['metrics']['goal_completion'])
    return out


def ledger(rows):
    done = lambda r: r['cls'] == 'full' and r['metrics']['goal_completion']  # noqa: E731
    bad = lambda r: done(r) and not r['metrics']['safe_completion']  # noqa: E731
    return {c: {v: {'completed': lib.count(rows, v, c, done), 'with_a_violation': lib.count(rows, v, c, bad)}
                for v in ('clean', 'boundary', 'perturbed')}
            for c in ('B0', 'M', 'M_recover', 'M_full', 'B2_full')}


def not_attainable(rows):
    out = {}
    for c in ('B0', 'B2', 'M', 'M_recover', 'M_mask', 'B2_full', 'M_full'):
        sub = lambda r: r['cls'] != 'full'  # noqa: E731
        out[c] = {
            'episodes': lib.count(rows, 'clean', c, sub),
            'goal_completed': lib.count(rows, 'clean', c, lambda r: sub(r) and r['metrics']['goal_completion']),
            'with_a_violation': lib.count(rows, 'clean', c, lambda r: sub(r) and r['metrics']['violation']),
            'nothing_needed': lib.count(rows, 'clean', c, lambda r: sub(r) and r['shortest'] == 0),
            'changed_although_nothing_needed': lib.count(
                rows, 'clean', c, lambda r: sub(r) and r['shortest'] == 0 and r['final'] != r['start']),
            'part_episodes': lib.count(rows, 'clean', c, lambda r: r['cls'] == 'part'),
            'part_target_reached': lib.count(
                rows, 'clean', c, lambda r: r['cls'] == 'part' and r['metrics']['target_reached']),
        }
    return out


def interrupted(rows):
    """Boundary variant, attainable goals: what happened to plans that were correct without a guard."""
    by = lib.cells(rows)
    ref = by[('boundary', 'B0')]
    out = {}
    for condition in ('M', 'M_recover', 'M_mask', 'M_full', 'B2_full'):
        patterns = Counter()
        for key, base in ref.items():
            row = by[('boundary', condition)][key]
            if base['cls'] != 'full' or not base['metrics']['safe_completion']:
                continue
            plan = [tuple(w) for w in base['writes']]
            got = [tuple(w) for w in row['writes']]
            patterns['correct_plans'] += 1
            patterns['plans_of_two_or_more_writes'] += len(plan) >= 2
            patterns['retried'] += row['proposals'] > 1
            if row['metrics']['goal_completion']:
                continue
            patterns['abandoned'] += 1
            if got[:1] == plan[:1] and any(w not in plan for w in got[1:]):
                patterns['abandoned_first_write_then_a_write_outside_the_plan'] += 1
            elif got == plan[:len(got)]:
                patterns['abandoned_stopped_part_way'] += 1
            else:
                patterns['abandoned_other'] += 1
        out[condition] = dict(sorted(patterns.items()))
    return out


def build():
    tasks, rows, attain, disagreements = load()
    contrasts = [lib.contrast(rows, item) for item in CONTRASTS]
    sizes = {}
    for item in contrasts:
        effect = item['effect']
        if item['id'] in ('att_full_vs_B0_clean', 'menu_loss_boundary', 'menu_off_target_part', 'reason_vs_silence_clean'):
            margin = -lib.MARGIN if item['rule'] == NI else 0.0
            base = 0.0 if item['rule'] == NI else abs(effect['estimate'])
            sizes[item['id']] = {
                'cluster_sd': round(effect['cluster_sd'], 4), 'clusters': effect['n_tasks'],
                'structures_for_power_0.9': (
                    {'true effect 0': lib.structures_needed(effect['cluster_sd'], 0.0, 0.9, margin),
                     'true effect +2.5 pp': lib.structures_needed(effect['cluster_sd'], 0.025, 0.9, margin),
                     'true effect = estimate': lib.structures_needed(effect['cluster_sd'], effect['estimate'], 0.9, margin)}
                    if item['rule'] == NI else
                    {'true effect = estimate': lib.structures_needed(effect['cluster_sd'], base, 0.9),
                     'true effect = half the estimate': lib.structures_needed(effect['cluster_sd'], base / 2, 0.9)})}
    record = {
        'study': 'EviBound v3.1, layer 1: policy-attainable goals on the frozen v3 holdout',
        'status': 'exploratory and post hoc; no confirmatory weight',
        'inputs': {str(p.relative_to(ROOT)): lib.sha256_file(p) for p in (SCENARIOS, FINGERPRINTS)},
        'estimator': {'function': 'analyze.paired_contrast', 'clusters': 'physical structures',
                      'resamples': lib.RESAMPLES, 'bootstrap_seed': lib.BOOTSTRAP_SEED,
                      'non_inferiority_margin': lib.MARGIN},
        'checks': checks(tasks, rows, attain, disagreements),
        'classes': lib.class_table(tasks, attain),
        'ceiling': ceiling(rows),
        'paired_table_M_full': paired_table(rows),
        'ledger': ledger(rows),
        'goals_not_attainable': not_attainable(rows),
        'split': lib.split_table(rows),
        'outcomes': lib.outcome_table(rows),
        'boundary_interrupted_plans': interrupted(rows),
        'contrasts': contrasts,
        'sizes_for_a_confirmatory_test': sizes,
    }
    return record


def pct(effect, key):
    return f"{100 * effect[key]:+.1f}"


def blocks(record):
    L = lib.table
    classes = record['classes']
    out = {'classes': L(['Class', 'Tasks', 'Structures', 'Episodes per cell', 'Shortest plan (writes: tasks)', 'Task types'], [
        [f'`{c}`', v['tasks'], v['structures'], 3 * v['tasks'],
         ', '.join(f'{k}: {n}' for k, n in v['shortest_plan'].items()),
         ', '.join(f'{n} {k}' for k, n in v['task_types'].items())] for c, v in classes.items()])}
    ceil = record['ceiling']
    gap = ceil['gap_M_full_minus_B0']
    n = ceil['episodes_per_cell']
    out['gap'] = L(['Part', 'Episodes', f'Share of {n}'], [
        ['Raw gap, M_full − B0', f"{gap['raw']:+d}", f"{100 * gap['raw'] / n:+.1f} pp"],
        ['Goals that are not attainable', f"{gap['goals_not_attainable']:+d}", f"{100 * gap['goals_not_attainable'] / n:+.1f} pp"],
        ['Attainable goals', f"{gap['goals_attainable']:+d}", f"{100 * gap['goals_attainable'] / n:+.1f} pp"]])
    pt = record['paired_table_M_full']
    names = {'compliant': 'Compliant completion', 'violating': 'Completion with a violation', 'none': 'No completion'}
    out['paired'] = L(['B0', 'Episodes', 'M_full completed', 'M_full did not'], [
        [names[k], v['episodes'], v['guard_completed'], v['episodes'] - v['guard_completed']] for k, v in pt.items()])
    out['contrasts'] = L(['Id', 'Contrast', 'Variant', 'Class', 'Metric', 'Counts', 'Estimate', '95% CI', 'Rule', 'Decision if applied'], [
        [c['id'], f"{c['left']} − {c['right']}", '+'.join(c['variants']), '+'.join(c['classes']), c['metric'],
         f"{c['effect']['left_count']} vs {c['effect']['right_count']} of {c['effect']['episodes_per_arm']}",
         pct(c['effect'], 'estimate') + ' pp', f"[{pct(c['effect'], 'ci95_low')}, {pct(c['effect'], 'ci95_high')}]",
         c['rule'].replace('_', '-'), c['decision']] for c in record['contrasts']])
    led = record['ledger']
    out['ledger'] = L(['Condition', 'Clean', 'Boundary', 'Attacked'], [
        [c] + [f"{v[var]['completed']}" + (f" ({v[var]['with_a_violation']} with a violation)" if v[var]['with_a_violation'] else '')
               for var in ('clean', 'boundary', 'perturbed')] for c, v in led.items()])
    na = record['goals_not_attainable']
    first = next(iter(na.values()))
    out['not_attainable'] = L(
        ['Condition (clean)', f"Goal completed, of {first['episodes']}", 'Episodes with a violation',
         f"State changed although nothing needed doing, of {first['nothing_needed']}",
         f"Attainable part reached, class `part`, of {first['part_episodes']}"],
        [[c, v['goal_completed'], v['with_a_violation'], v['changed_although_nothing_needed'], v['part_target_reached']]
         for c, v in na.items()])
    rows = []
    for variant in ('clean', 'boundary', 'perturbed'):
        for c in SHOWN:
            v = record['split'][variant][c]
            rows.append([variant if variant != 'perturbed' else 'attacked', c, f"{v['done']} of {v['n']}",
                         f"{v['A']} of {v['reference_compliant']}", f"{v['B']} of {v['reference_violating']}",
                         v['C'], v['D'], v['retried']])
    out['split'] = L(['Variant', 'Condition', 'Completed', 'A: correct plan lost', 'B: blocked, not recovered',
                      'C: gained', 'D: neither', 'Episodes with a retry'], rows)
    rows = []
    for variant in ('clean', 'boundary'):
        for c in ('B0',) + SHOWN:
            for cls in ('part', 'none'):
                v = record['outcomes'][variant][c][cls]
                rows.append([variant, c, f'`{cls}`'] + [v[k] for k in lib.OUTCOMES])
    out['outcomes'] = L(['Variant', 'Condition', 'Class'] + list(lib.OUTCOMES), rows)
    bi = record['boundary_interrupted_plans']
    out['interrupted'] = L(['Condition', 'Correct plans', 'With two or more writes', 'Episodes with a retry', 'Abandoned',
                            'First write, then a write outside the plan', 'Stopped part way', 'Other'], [
        [c, v['correct_plans'], v['plans_of_two_or_more_writes'], v.get('retried', 0), v.get('abandoned', 0),
         v.get('abandoned_first_write_then_a_write_outside_the_plan', 0), v.get('abandoned_stopped_part_way', 0),
         v.get('abandoned_other', 0)] for c, v in bi.items()])
    rows = []
    for cid, v in record['sizes_for_a_confirmatory_test'].items():
        rows.append([cid, v['clusters'], v['cluster_sd'],
                     '; '.join(f'{k}: {n}' for k, n in v['structures_for_power_0.9'].items())])
    out['sizes'] = L(['Contrast', 'Structures here', 'Between-structure SD', 'Structures needed for power 0.9'], rows)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--write-doc', action='store_true')
    args = parser.parse_args()
    record = build()
    text = json.dumps(record, indent=1, sort_keys=True) + '\n'
    if args.check:
        problems = []
        if not RECORD.exists() or RECORD.read_text() != text:
            problems.append(f'{RECORD.relative_to(ROOT)} is stale')
        if DOC.exists() and lib.refresh_blocks(DOC.read_text(), blocks(record)) != DOC.read_text():
            problems.append(f'{DOC.relative_to(ROOT)} has stale generated tables')
        print('\n'.join(problems) or 'layer-1 record and document are current')
        return 1 if problems else 0
    RECORD.write_text(text)
    if args.write_doc:
        DOC.write_text(lib.refresh_blocks(DOC.read_text(), blocks(record)))
    c = record['checks']
    print(json.dumps({'record': str(RECORD.relative_to(ROOT)), 'episodes': c['episodes'],
                      'replay_disagreements': c['replay_disagreements'],
                      'classes': {k: v['tasks'] for k, v in record['classes'].items()}}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
