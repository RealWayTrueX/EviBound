#!/usr/bin/env python3
"""Record of the exploratory scale study: homes of three sizes, one record per planner.

Reads the published fingerprints of each run (artifacts/homes_<planner>_fingerprints.json.gz),
recomputes everything with scripts/analyze_homes.py, writes artifacts/homes_record.json and
refreshes the generated tables in docs/scale_study.md (and the side-by-side table in
docs/v3_1_results.md, which puts Study 3 next to the three homes). Nothing here has
confirmatory weight.

  python scripts/homes_record.py            # write the record and the tables
  python scripts/homes_record.py --check    # fail if either is stale
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import analyze_homes as study  # noqa: E402
import v3_1_lib as lib  # noqa: E402

RECORD = ROOT / 'artifacts/homes_record.json'
STUDY3 = ROOT / 'artifacts/v3_1_models_record.json'     # Study 3 in the frozen small home, per planner
DOC = ROOT / 'docs/scale_study.md'
SUMMARY_DOC = ROOT / 'docs/v3_1_results.md'         # carries the side-by-side table as well
RUNS = {'qwen25': ('artifacts/homes_qwen25_fingerprints.json.gz', 'Qwen2.5-7B'),
        'qwen3': ('artifacts/homes_qwen3_fingerprints.json.gz', 'Qwen3-8B')}
HOME_NAMES = {'S': 'small', 'M': 'medium', 'L': 'large'}
CONDITION_NAMES = {'B0': 'no guard', 'B2_plan': 'rules on the cited reading', 'M_recover': 'evidence-bound, reason',
                   'M_full': 'evidence-bound, reason + list', 'M_plan': 'evidence-bound, reason + plan review'}


def compact(item):
    if item['decision'] == 'missing':
        return {'decision': 'missing'}
    return {'left': item['left_count'], 'right': item['right_count'], 'episodes': item['episodes_per_arm'],
            'tasks': item['tasks'], 'estimate_pp': round(100 * item['estimate'], 1),
            'low_pp': round(100 * item['ci95_low'], 1), 'high_pp': round(100 * item['ci95_high'], 1),
            'rule': item['rule'], 'decision': item['decision']}


def one_planner(path, tasks):
    rows, inputs, stored = study.load_rows([ROOT / path])
    disagreements = study.annotate(rows, tasks, stored)
    result = study.analyse(rows)
    homes = {}
    for name, home in result['homes'].items():
        by_variant = {}
        for cell in home['cells']:
            by_variant.setdefault(cell['variant'], {})[cell['condition']] = {
                key: cell[key] for key in ('episodes', 'unsafe_effect', 'exact_target', 'unrequested_change', 'retried')}
        homes[name] = {'size': home['size'], 'tasks': home['tasks'], 'episodes': home['episodes'],
                       'seeds': home['seeds'], 'totals': home['totals'], 'by_variant': by_variant,
                       'form': home['form'], 'contrasts': {c['id']: compact(c) for c in home['contrasts']}}
    return {'input': {'file': path, 'sha256': lib.sha256_file(ROOT / path)}, 'episodes': len(rows),
            'recomputed_differently': len(disagreements), 'homes': homes,
            'carried_over_from_small': result['carried_over_from_small']}


def build():
    tasks = study.load_tasks()
    record = {'study': 'EviBound scale study: homes of three sizes (exploratory, no confirmatory weight)',
              'primary_contrasts': list(study.PRIMARY), 'planners': {}}
    for name, (path, _) in RUNS.items():
        if (ROOT / path).exists():
            record['planners'][name] = one_planner(path, tasks)
    return record


def share(count, total):
    return f'{count} ({100 * count / total:.1f}%)'


def cell(item):
    if not item or item['decision'] == 'missing':
        return 'not run'
    return (f"{item['left']} vs {item['right']} of {item['episodes']}; {item['estimate_pp']:+.1f} "
            f"[{item['low_pp']:+.1f}, {item['high_pp']:+.1f}]; {item['decision']}")


def blocks(record):
    T = lib.table
    planners = record['planners']
    out = {}
    rows = []
    for planner, data in planners.items():
        for name, home in data['homes'].items():
            size, form = home['size'], home['form']
            rows.append([RUNS[planner][1], HOME_NAMES[name], size['devices'], size['rules'],
                         f"{size['states']} ({size['legal_states']})", size['max_writes'], home['episodes'],
                         f"{form['first_not_parsed']} of {form['first_proposals']}", form['mean_list_length']])
    out['homes_runs'] = T(['Planner', 'Home', 'Devices', 'Rules', 'States (legal)', 'Writes', 'Episodes',
                           'First answers not parsed', 'Mean entries in the list'], rows)
    rows = []
    for planner, data in planners.items():
        for name, home in data['homes'].items():
            for condition in CONDITION_NAMES:
                total = home['totals'].get(condition)
                if not total:
                    continue
                attacked = home['by_variant']['perturbed'][condition]
                clean = home['by_variant']['clean'][condition]
                rows.append([RUNS[planner][1], HOME_NAMES[name], f'`{condition}`', CONDITION_NAMES[condition],
                             share(attacked['unsafe_effect'], attacked['episodes']),
                             share(clean['exact_target'], clean['episodes']),
                             share(total['exact_target'], total['episodes']),
                             share(total['unrequested_change'], total['episodes'])])
    out['homes_rates'] = T(['Planner', 'Home', 'Condition', '', 'Unsafe effect, attacked', 'Exact target, clean',
                            'Exact target, all', 'Unrequested change, all'], rows)
    labels = {c[0]: c[1] for c in study.CONTRASTS}
    rows = []
    for cid in [c[0] for c in study.CONTRASTS]:
        for planner, data in planners.items():
            rows.append([cid, labels[cid], RUNS[planner][1]] + [cell(data['homes'][name]['contrasts'].get(cid))
                                                                for name in HOME_NAMES if name in data['homes']])
    out['homes_contrasts'] = T(['Id', 'Contrast', 'Planner'] + [HOME_NAMES[n] for n in HOME_NAMES], rows)
    out['homes_vs_study3'] = T(['Planner', 'Quantity', 'Study 3 (frozen small home)'] + [HOME_NAMES[n] for n in HOME_NAMES],
                               side_by_side(planners))
    return out


def side_by_side(planners):
    """The same quantities in Study 3 (frozen small home, its own 372 tasks) and in the three homes of this study."""
    study3 = json.loads(STUDY3.read_text())['models']
    rates = (('Unsafe effect under attack, guard that trusts the cited reading', 'B2_plan', 'unsafe_effect', True),
             ('Unsafe effect under attack, evidence-bound guard (reason)', 'M_recover', 'unsafe_effect', True),
             ('Unrequested change, reason alone', 'M_recover', 'unrequested_change', False),
             ('Unrequested change, reason + list', 'M_full', 'unrequested_change', False),
             ('Exact target, reason alone', 'M_recover', 'exact_target', False),
             ('Exact target, reason + list', 'M_full', 'exact_target', False),
             ('Exact target, reason + plan review', 'M_plan', 'exact_target', False))
    differences = (('List minus reason, unrequested change (pp)', 'U1', 'U1', 1),
                   ('Reason minus list, exact target (pp)', 'N1', 'K36', 1),
                   ('Plan review minus reason, exact target (pp)', 'P1', 'N3', -1))

    def interval(item, sign=1):
        low, high = sorted((sign * item['low_pp'], sign * item['high_pp']))
        return f"{sign * item['estimate_pp']:+.1f} [{low:+.1f}, {high:+.1f}]"

    rows = []
    for planner, data in planners.items():
        reference = study3.get(planner)
        for label, condition, metric, attacked in rates:
            row = [RUNS[planner][1], label]
            if reference:
                cell = reference['attacked'][condition] if attacked else reference['totals'][condition]
                row.append(f"{cell[metric]} of {cell['episodes']} ({100 * cell[metric] / cell['episodes']:.1f}%)")
            else:
                row.append('not run')
            for name in HOME_NAMES:
                home = data['homes'][name]
                cell = home['by_variant']['perturbed'][condition] if attacked else home['totals'][condition]
                row.append(f"{cell[metric]} of {cell['episodes']} ({100 * cell[metric] / cell['episodes']:.1f}%)")
            rows.append(row)
        for label, here, there, sign in differences:
            row = [RUNS[planner][1], label, interval(reference['contrasts'][there], sign) if reference else 'not run']
            row += [interval(data['homes'][name]['contrasts'][here]) for name in HOME_NAMES]
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    record = build()
    text = json.dumps(record, indent=1, sort_keys=True) + '\n'
    if not record['planners'] and not RECORD.exists():
        print('no run of the scale study is recorded yet')
        return 0
    built = blocks(record) if record['planners'] else {}
    docs = {}
    for path, names in ((DOC, list(built)), (SUMMARY_DOC, ['homes_vs_study3'])):
        doc = path.read_text()
        present = {name: built[name] for name in names if name in built and f'<!-- generated:{name} -->' in doc}
        docs[path] = (doc, lib.refresh_blocks(doc, present))
    if args.check:
        problems = []
        if not RECORD.exists() or RECORD.read_text() != text:
            problems.append(f'{RECORD.relative_to(ROOT)} is stale')
        for path, (doc, fresh) in docs.items():
            if fresh != doc:
                problems.append(f'{path.relative_to(ROOT)} has stale tables')
        if record['planners'] and '<!-- generated:homes_runs -->' not in docs[DOC][0]:
            problems.append(f'{DOC.relative_to(ROOT)} has no results section')
        print('\n'.join(problems) or 'record and tables of the scale study are current')
        return 1 if problems else 0
    RECORD.write_text(text)
    for path, (_, fresh) in docs.items():
        path.write_text(fresh)
    print(json.dumps({'record': str(RECORD.relative_to(ROOT)), 'planners': {
        p: {h: {c: v['decision'] for c, v in home['contrasts'].items() if c in study.PRIMARY}
            for h, home in data['homes'].items()} for p, data in record['planners'].items()}}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
