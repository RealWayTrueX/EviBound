#!/usr/bin/env python3
"""Agreement between reviewers who used the human review desk.

Reads two or more JSON exports of the review desk (the 导出 / Export button,
file ``evibound_<corpus>[_practice]_review.json``, written by ``jsonText()`` in
``review_desk/template.html``) and reports, for every item kind and every
question:

- ``n``: items answered by at least two reviewers;
- percent agreement: share of those items on which every answer is the same;
- Gwet's AC1 (first-order agreement coefficient);
- the ids of the items on which the reviewers disagree;
- missing answers, counted and listed, never imputed.

Protocol: ``docs/peer_review_protocol.md``. Standard library only.

Usage::

    python3 scripts/review_agreement.py A_review.json B_review.json --labels A B \\
        --items reviews/peer_review/sample.json --output reviews/peer_review/agreement.json
    python3 scripts/review_agreement.py --draw-sample desk_data.json --seed 20261110 \\
        --output reviews/peer_review/sample.json

``desk_data.json`` is written by ``python3 scripts/build_review_desk.py --data-out PATH``.

Exit status: 0 on success; 2 when the exports come from different desk builds
(tool version, run key, corpus hashes, item ids or item hashes differ); 1 for
any other input error.

AC1 is computed on the items that at least two reviewers answered. With r_i
answers on item i, r_ik of them in category k, q categories and n such items::

    p_a  = (1/n) * sum_i sum_k r_ik (r_ik - 1) / (r_i (r_i - 1))
    pi_k = (1/n) * sum_i r_ik / r_i
    p_e  = (1/(q - 1)) * sum_k pi_k (1 - pi_k)
    AC1  = (p_a - p_e) / (1 - p_e)

For two reviewers p_a is the share of items with the same answer and pi_k is
the mean of the two reviewers' shares of category k. q is fixed by the
question (yes/no: 2; decision and confidence: 3), not by the answers seen.
Items answered by only one reviewer do not enter p_a or pi_k; they are counted
as ``single_answer``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / 'reviews' / 'peer_review'  # git-ignored, local-only
REPORT_FORMAT = 'evibound-review-agreement-1'
SAMPLE_FORMAT = 'evibound-review-sample-1'
DEFAULT_SEED = 20261110

YES_NO = ('Y', 'N')
DECISIONS = ('approve', 'fix', 'reject')
CONFIDENCE = ('high', 'med', 'low')

# English labels of the questions each item kind asks, as in scripts/build_review_desk.py
# (TASK_QUESTIONS, rule_items, convention_items, caption_items). The export carries only
# the keys, so the labels are for display; an unknown kind is analysed by the q1, q2, ...
# keys found in its verdicts.
QUESTIONS = {
    'rule': [('q1', 'Wording clear'), ('q2', 'Rule sensible'), ('q3', 'Diagram correct'),
             ('q4', 'Chinese accurate')],
    'convention': [('q1', 'Convention sensible'), ('q2', 'Chinese accurate')],
    'caption': [('q1', 'Readable at a glance'), ('q2', 'Matches the label'), ('q3', 'Chinese accurate')],
    'task': [('q1', 'Instruction clear'), ('q2', 'Goals sensible'), ('q3', 'Perturbation correct'),
             ('q4', 'Expected behaviour agreed')],
}
EXTRA = [('decision', 'Decision', DECISIONS), ('conf', 'Confidence', CONFIDENCE)]
KIND_ORDER = ['rule', 'convention', 'caption', 'task']
Q_KEY = re.compile(r'^q\d+$')


class InputError(Exception):
    """An export, item list or option cannot be used (exit status 1)."""


class BuildMismatch(Exception):
    """The exports come from different desk builds (exit status 2)."""


# ---------------------------------------------------------------- loading
def load_export(path):
    """Read and check one desk JSON export. Returns the parsed document."""
    path = Path(path)
    try:
        raw = path.read_bytes()
        doc = json.loads(raw.decode('utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as err:
        raise InputError(f'{path}: cannot read a JSON export ({err})') from err
    if not isinstance(doc, dict) or not isinstance(doc.get('items'), list):
        raise InputError(f'{path}: not a review-desk export (no "items" list)')
    if not isinstance(doc.get('run_key'), str) or not doc['run_key']:
        raise InputError(f'{path}: the export has no run key')
    seen = set()
    for index, item in enumerate(doc['items']):
        if not isinstance(item, dict):
            raise InputError(f'{path}: item {index} is not an object')
        for field in ('id', 'kind', 'item_hash'):
            if not isinstance(item.get(field), str) or not item[field]:
                raise InputError(f'{path}: item {index} has no {field}')
        if item['id'] in seen:
            raise InputError(f'{path}: item id {item["id"]} appears twice')
        seen.add(item['id'])
        verdict = item.get('verdict')
        if verdict is not None and not isinstance(verdict, dict):
            raise InputError(f'{path}: item {item["id"]}: verdict is neither an object nor null')
    doc['_file'] = str(path)
    doc['_sha256'] = hashlib.sha256(raw).hexdigest()
    return doc


def check_same_build(exports, labels):
    """Raise BuildMismatch unless every export comes from the same desk build."""
    problems = []
    first, name0 = exports[0], labels[0]
    for doc, name in zip(exports[1:], labels[1:]):
        for field in ('tool', 'version', 'run_key'):
            if first.get(field) != doc.get(field):
                problems.append(f'{field}: {name0} has {first.get(field)!r}, {name} has {doc.get(field)!r}')
        if first.get('corpus_sha256') and doc.get('corpus_sha256') and first['corpus_sha256'] != doc['corpus_sha256']:
            problems.append(f'corpus_sha256 differs between {name0} and {name}')
        ids0 = {i['id']: i for i in first['items']}
        ids1 = {i['id']: i for i in doc['items']}
        only0, only1 = sorted(set(ids0) - set(ids1)), sorted(set(ids1) - set(ids0))
        if only0 or only1:
            problems.append(f'item set differs: {len(only0)} only in {name0} {only0[:3]}, '
                            f'{len(only1)} only in {name} {only1[:3]}')
        changed = sorted(i for i in set(ids0) & set(ids1)
                         if (ids0[i]['item_hash'], ids0[i]['kind']) != (ids1[i]['item_hash'], ids1[i]['kind']))
        if changed:
            problems.append(f'{len(changed)} items differ in content between {name0} and {name} {changed[:3]}')
    if problems:
        raise BuildMismatch('the exports come from different desk builds:\n  ' + '\n  '.join(problems))


def answer_status(item):
    """('reviewed', verdict) or ('not_reviewed' | 'stale', None) for one exported item."""
    verdict = item.get('verdict')
    if verdict is None:
        return ('stale' if item.get('stale') else 'not_reviewed'), None
    if verdict.get('item_hash') not in (None, item['item_hash']):
        return 'stale', None  # the desk discards verdicts given on other item content
    return 'reviewed', verdict


def read_items_file(path):
    """Item ids from a sample file (--draw-sample output), a JSON list or one id per line."""
    try:
        text = Path(path).read_text(encoding='utf-8')
    except OSError as err:
        raise InputError(f'{path}: cannot read the item list ({err})') from err
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        doc = None
    if isinstance(doc, dict) and isinstance(doc.get('items'), list):
        ids = doc['items']
    elif isinstance(doc, list):
        ids = doc
    elif doc is None:
        ids = [line.split('#', 1)[0].strip() for line in text.splitlines()]
        ids = [i for i in ids if i]
    else:
        raise InputError(f'{path}: expected a list of item ids')
    if not all(isinstance(i, str) and i for i in ids):
        raise InputError(f'{path}: every item id must be a non-empty string')
    return list(dict.fromkeys(ids))


# ---------------------------------------------------------------- statistics
def gwet_ac1(ratings, categories):
    """Observed agreement, chance agreement and AC1 for items with at least two answers.

    ``ratings``: one list of answers per item (missing answers already removed).
    ``categories``: the categories the question allows; observed values outside
    it are added, so q never falls below the instrument's number of categories.
    """
    rated = [r for r in ratings if len(r) >= 2]
    n = len(rated)
    cats = list(categories) + sorted({a for r in rated for a in r} - set(categories))
    if n == 0:
        return {'n': 0, 'categories': cats, 'pa': None, 'pe': None, 'ac1': None}
    q = len(cats)
    counts = [Counter(r) for r in rated]
    pa = sum(sum(c * (c - 1) for c in cnt.values()) / (len(r) * (len(r) - 1))
             for cnt, r in zip(counts, rated)) / n
    pi = {k: sum(cnt[k] / len(r) for cnt, r in zip(counts, rated)) / n for k in cats}
    pe = sum(p * (1 - p) for p in pi.values()) / (q - 1)
    return {'n': n, 'categories': cats, 'pa': pa, 'pe': pe, 'ac1': (pa - pe) / (1 - pe)}


def _round(x, digits=6):
    return None if x is None else round(x, digits)


# ---------------------------------------------------------------- agreement
def question_table(kinds, statuses):
    """(kind, key, label, categories) for every question to analyse, in a stable order."""
    rows = []
    order = [k for k in KIND_ORDER if k in kinds] + sorted(k for k in kinds if k not in KIND_ORDER)
    for kind in order:
        known = list(QUESTIONS.get(kind, []))
        seen = {key for st in statuses for item_id, (status, verdict) in st.items()
                if status == 'reviewed' and kinds[kind].get(item_id) for key in verdict if Q_KEY.match(key)}
        extra = sorted(seen - {k for k, _ in known}, key=lambda k: int(k[1:]))
        for key, label in known + [(k, k) for k in extra]:
            rows.append((kind, key, label, YES_NO))
        for key, label, cats in EXTRA:
            rows.append((kind, key, label, cats))
    for key, label, cats in EXTRA:
        rows.append(('all', key, label, cats))
    return rows


def agreement(exports, labels, items=None, exclude=(), with_comments=False):
    """The agreement report (a JSON-ready dict) for exports of one desk build."""
    if len(exports) < 2:
        raise InputError('agreement needs at least two exports')
    if len(set(labels)) != len(labels) or len(labels) != len(exports):
        raise InputError('give one distinct label per export')
    if len({doc['_sha256'] for doc in exports}) != len(exports):
        raise InputError('two of the exports are the same file')
    ids_with_reviewer = [doc.get('reviewer_id') for doc in exports if doc.get('reviewer_id')]
    if len(set(ids_with_reviewer)) != len(ids_with_reviewer):
        raise InputError('two exports carry the same reviewer id')
    check_same_build(exports, labels)

    desk_items = exports[0]['items']
    if items is not None:
        known = {i['id'] for i in desk_items}
        unknown = [i for i in items if i not in known]
        if unknown:
            raise InputError(f'{len(unknown)} listed items are not in this desk build: {unknown[:5]}')
        scope = [i for i in desk_items if i['id'] in set(items)]
    else:
        scope = list(desk_items)
    kinds = defaultdict(dict)
    for item in scope:
        kinds[item['kind']][item['id']] = item
    scope_ids = {item['id'] for item in scope}
    statuses = [{i['id']: answer_status(i) for i in doc['items'] if i['id'] in scope_ids} for doc in exports]

    table = question_table(kinds, statuses)
    valid = {f'{kind}:{key}' for kind, key, _, _ in table}
    bad = [e for e in exclude if e not in valid]
    if bad:
        raise InputError(f'--exclude matches no question: {bad} (valid: {sorted(valid)})')
    excluded = set(exclude)

    results = []
    for kind, key, label, cats in table:
        if f'{kind}:{key}' in excluded:
            continue
        pool = scope if kind == 'all' else [i for i in scope if i['kind'] == kind]
        per_item, unanswered, counts = [], {name: [] for name in labels}, {name: Counter() for name in labels}
        single = none = 0
        disagreements, detail = [], {}
        for item in pool:
            answers = {}
            for name, st in zip(labels, statuses):
                status, verdict = st[item['id']]
                if status != 'reviewed':
                    continue
                value = verdict.get(key)
                if value is None or value == '':
                    unanswered[name].append(item['id'])
                    continue
                if not isinstance(value, str):
                    raise InputError(f'{name}: item {item["id"]}: answer to {key} is not a string')
                answers[name] = value
                counts[name][value] += 1
            if len(answers) >= 2:
                per_item.append(list(answers.values()))
                if len(set(answers.values())) > 1:
                    disagreements.append(item['id'])
                    entry = {'answers': answers}
                    if with_comments:
                        entry['comments'] = {name: str(st[item['id']][1].get('comment') or '')
                                             for name, st in zip(labels, statuses) if name in answers}
                    detail[item['id']] = entry
            elif len(answers) == 1:
                single += 1
            else:
                none += 1
        stats = gwet_ac1(per_item, cats)
        full = sum(1 for r in per_item if len(set(r)) == 1)
        results.append({
            'kind': kind, 'question': key, 'label': label, 'categories': stats['categories'],
            'items_in_scope': len(pool), 'n': stats['n'], 'full_agreement': full,
            'percent_agreement': _round(100.0 * full / stats['n'], 2) if stats['n'] else None,
            'pa': _round(stats['pa']), 'pe': _round(stats['pe']), 'ac1': _round(stats['ac1']),
            'disagreements': disagreements, 'disagreement_answers': detail,
            'single_answer': single, 'no_answer': none,
            'unanswered': {k: v for k, v in unanswered.items() if v},
            'answer_counts': {name: dict(sorted(c.items())) for name, c in counts.items()},
            'unexpected_values': [c for c in stats['categories'] if c not in cats],
        })

    reviewers = []
    for name, doc, st in zip(labels, exports, statuses):
        by_status = defaultdict(list)
        for item_id, (status, verdict) in st.items():
            by_status[status].append(item_id)
        decided = sum(1 for status, verdict in st.values() if status == 'reviewed' and verdict.get('decision'))
        reviewers.append({
            'label': name, 'file': Path(doc['_file']).name, 'file_sha256': doc['_sha256'],
            'exported_at': doc.get('exported_at'), 'items_in_scope': len(st),
            'reviewed': len(by_status['reviewed']), 'with_decision': decided,
            'not_reviewed': sorted(by_status['not_reviewed']), 'stale': sorted(by_status['stale']),
        })
    first = exports[0]
    return {
        'format': REPORT_FORMAT,
        'generated_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'desk': {'tool': first.get('tool'), 'version': first.get('version'), 'corpus': first.get('corpus'),
                 'mode': first.get('mode'), 'run_key': first['run_key'],
                 'corpus_sha256': first.get('corpus_sha256'), 'items': len(desk_items)},
        'scope': {'items': 'listed' if items is not None else 'all', 'items_in_scope': len(scope),
                  'by_kind': {k: len(v) for k, v in kinds.items()}, 'excluded_questions': sorted(excluded)},
        'reviewers': reviewers,
        'method': ('Per item kind and question: n = items answered by at least two reviewers; percent agreement = '
                   'share of those items with identical answers; Gwet AC1 with p_a and pi_k over the same items and '
                   'q fixed by the question (yes/no 2, decision 3, confidence 3). Missing answers are listed, '
                   'never imputed. Reviewer identities are not copied from the exports.'),
        'results': results,
    }


def format_table(report, width=4):
    """A short plain-text table of the report."""
    rev = ', '.join(r['label'] for r in report['reviewers'])
    lines = [f"Review agreement · run key {report['desk']['run_key']} · reviewers {rev} · "
             f"{report['scope']['items_in_scope']} items in scope ({report['scope']['items']})",
             f"{'kind':<11}{'question':<30}{'n':>4}{'agree':>9}{'AC1':>8}  disagreeing items"]
    for row in report['results']:
        agree = '—' if row['percent_agreement'] is None else f"{row['percent_agreement']:.1f}%"
        ac1 = '—' if row['ac1'] is None else f"{row['ac1']:.3f}"
        ids = row['disagreements']
        shown = ', '.join(ids[:width]) + (f' (+{len(ids) - width} more)' if len(ids) > width else '') if ids else '-'
        lines.append(f"{row['kind']:<11}{(row['question'] + ' ' + row['label'])[:29]:<30}{row['n']:>4}"
                     f"{agree:>9}{ac1:>8}  {shown}")
    for r in report['reviewers']:
        lines.append(f"{r['label']}: reviewed {r['reviewed']}/{r['items_in_scope']}, with a decision "
                     f"{r['with_decision']}, not reviewed {len(r['not_reviewed'])}, stale {len(r['stale'])}")
    gaps = [(row['kind'], row['question'], name, len(v)) for row in report['results']
            for name, v in row['unanswered'].items()]
    if gaps:
        lines.append('Unanswered questions on reviewed items: ' +
                     '; '.join(f'{name} {kind}:{q} {k}' for kind, q, name, k in gaps))
    return '\n'.join(lines)


# ---------------------------------------------------------------- sampling
def draw_sample(desk, seed=DEFAULT_SEED, tasks_per_cell=1, captions_per_branch=5, split='holdout',
                core_tasks=8):
    """The reviewer-B sample of docs/peer_review_protocol.md, drawn from the desk data.

    Rule (one random.Random(seed), calls in this order):
    1. every rule and reading-convention item, in desk order;
    2. tasks of ``split``: for each (modality, language) cell in sorted order of the
       English chip labels, ``rng.sample(sorted ids, tasks_per_cell)``; then
       ``rng.shuffle`` of the drawn tasks gives the review order;
    3. captions: for each labelled branch in sorted order, ``rng.sample(sorted ids,
       captions_per_branch)``; captions are listed in desk order.
    The core is the rules and conventions, the captions and the first ``core_tasks`` tasks.
    """
    if not isinstance(desk, dict) or not isinstance(desk.get('items'), list) or 'meta' not in desk:
        raise InputError('expected the desk data written by build_review_desk.py --data-out')
    items, meta = desk['items'], desk['meta']
    position = {it['id']: n for n, it in enumerate(items)}
    rng = random.Random(seed)
    fixed = [it['id'] for it in items if it['kind'] in ('rule', 'convention')]

    cells = defaultdict(list)
    for it in items:
        if it['kind'] == 'task' and it.get('group') == split:
            chips = {c.get('k'): c.get('en') for c in it.get('chips', [])}
            if not chips.get('modality') or not chips.get('language'):
                raise InputError(f'task {it["id"]} has no modality or language chip')
            cells[(chips['modality'], chips['language'])].append(it['id'])
    if not cells:
        raise InputError(f'no task of split {split!r} in the desk data')
    tasks, cell_of = [], {}
    for cell in sorted(cells):
        ids = sorted(cells[cell])
        if len(ids) < tasks_per_cell:
            raise InputError(f'cell {cell} has {len(ids)} tasks, fewer than {tasks_per_cell}')
        for task_id in rng.sample(ids, tasks_per_cell):
            tasks.append(task_id)
            cell_of[task_id] = list(cell)
    rng.shuffle(tasks)

    branches = defaultdict(list)
    for it in items:
        if it['kind'] == 'caption':
            branches[(it.get('caption') or {}).get('branch') or 'both'].append(it['id'])
    captions = []
    for branch in sorted(branches):
        ids = sorted(branches[branch])
        if len(ids) < captions_per_branch:
            raise InputError(f'branch {branch} has {len(ids)} captions, fewer than {captions_per_branch}')
        captions += rng.sample(ids, captions_per_branch)
    captions.sort(key=position.get)

    by_id = {it['id']: it for it in items}

    def title(item_id):
        return (by_id[item_id].get('title') or {}).get('en', item_id)

    branch_of = {i: b for b, ids in branches.items() for i in ids}
    rule = ' '.join(line.strip() for line in draw_sample.__doc__.split('\n\n')[1].splitlines())
    return {
        'format': SAMPLE_FORMAT, 'run_key': meta.get('run_key'), 'corpus_sha256': meta.get('corpus_sha256'),
        'seed': seed, 'split': split, 'tasks_per_cell': tasks_per_cell,
        'captions_per_branch': captions_per_branch, 'rule': rule,
        'items': fixed + captions + tasks, 'core': fixed + captions + tasks[:core_tasks],
        'detail': ([{'id': i, 'kind': by_id[i]['kind'], 'title': title(i)} for i in fixed]
                   + [{'id': i, 'kind': 'caption', 'title': title(i), 'branch': branch_of[i]} for i in captions]
                   + [{'id': i, 'kind': 'task', 'title': title(i), 'review_order': n + 1, 'cell': cell_of[i],
                       'core': n < core_tasks} for n, i in enumerate(tasks)]),
    }


# ---------------------------------------------------------------- command line
def _write_json(path, doc):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('exports', nargs='*', help='two or more review-desk JSON exports')
    parser.add_argument('--labels', nargs='+', help='one label per export (default A, B, C, ...); '
                        'use labels, not names: the report may be published')
    parser.add_argument('--items', help='restrict to these item ids (sample file, JSON list or one id per line)')
    parser.add_argument('--exclude', action='append', default=[], metavar='KIND:QUESTION',
                        help='leave a question out, e.g. caption:q3 when a reviewer does not read Chinese')
    parser.add_argument('--with-comments', action='store_true',
                        help='copy the reviewers\' comments on disagreeing items into the report (keep it local)')
    parser.add_argument('--output', help='JSON report or sample file (default under reviews/peer_review/)')
    parser.add_argument('--draw-sample', metavar='DESK_DATA', help='draw the reviewer-B sample instead')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    parser.add_argument('--tasks-per-cell', type=int, default=1)
    parser.add_argument('--captions-per-branch', type=int, default=5)
    parser.add_argument('--core-tasks', type=int, default=8)
    parser.add_argument('--split', default='holdout')
    args = parser.parse_args(argv)
    try:
        if args.draw_sample:
            try:
                desk = json.loads(Path(args.draw_sample).read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError) as err:
                raise InputError(f'{args.draw_sample}: cannot read the desk data ({err})') from err
            sample = draw_sample(desk, args.seed, args.tasks_per_cell, args.captions_per_branch,
                                 args.split, args.core_tasks)
            out = Path(args.output) if args.output else DEFAULT_OUT / 'sample.json'
            _write_json(out, sample)
            print(f'{out}: {len(sample["items"])} items (core {len(sample["core"])}), seed {sample["seed"]}, '
                  f'run key {sample["run_key"]}')
            for entry in sample['detail']:
                if entry['kind'] == 'task':
                    extra = f"order {entry['review_order']}, cell {' × '.join(entry['cell'])}"
                    extra += ', core' if entry['core'] else ''
                else:
                    extra = entry.get('branch') or ''
                print(f"  {entry['id']:<30} {entry.get('title', ''):<22} {extra}")
            return 0
        if len(args.exports) < 2:
            raise InputError('give at least two exports (or --draw-sample DESK_DATA)')
        labels = args.labels or [chr(ord('A') + n) for n in range(len(args.exports))]
        exports = [load_export(p) for p in args.exports]
        items = read_items_file(args.items) if args.items else None
        report = agreement(exports, labels, items, args.exclude, args.with_comments)
        out = Path(args.output) if args.output else DEFAULT_OUT / 'agreement.json'
        _write_json(out, report)
        print(format_table(report))
        print(f'report: {out}')
        return 0
    except BuildMismatch as err:
        print(f'review_agreement: {err}', file=sys.stderr)
        return 2
    except InputError as err:
        print(f'review_agreement: {err}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
