"""Reviewer agreement on review-desk exports: AC1, missing answers, build checks, sampling."""
import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


ra = load('review_agreement')
RUN_KEY = 'v3-000000000000-practice'
QS = {'rule': 4, 'convention': 2, 'caption': 3, 'task': 4}


def item(item_id, kind):
    return {'id': item_id, 'kind': kind, 'required': True, 'item_hash': 'h-' + item_id}


def verdict(item_id, kind, decision='approve', conf='high', **answers):
    """A verdict as the desk stores it: q answers, decision, confidence, bookkeeping fields."""
    v = {f'q{n}': 'Y' for n in range(1, QS.get(kind, 3) + 1)}
    v.update(answers)
    v.update({'decision': decision, 'conf': conf, 'kind': kind, 'item_hash': 'h-' + item_id,
              'updated_at': '2026-11-10T00:00:00.000Z'})
    return v


def export(items, verdicts, run_key=RUN_KEY, stale=(), reviewer=None, tag=''):
    """A desk JSON export in the shape jsonText() writes (review_desk/template.html)."""
    return {
        'tool': 'EviBound review desk', 'version': 1, 'mode': 'practice', 'corpus': 'v3', 'run_key': run_key,
        'corpus_files': {}, 'corpus_sha256': {'holdout': 'x'}, 'exported_at': '2026-11-10T00:00:00.000Z' + tag,
        'reviewer_id': reviewer, 'summary': {},
        'items': [dict(it, stale=it['id'] in stale, verdict=verdicts.get(it['id'])) for it in items],
    }


def as_loaded(doc, name):
    """What load_export returns for doc, without touching the disk."""
    loaded = json.loads(json.dumps(doc))
    loaded['_file'] = name
    loaded['_sha256'] = ra.hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()
    return loaded


def row(report, kind, question):
    return next(r for r in report['results'] if r['kind'] == kind and r['question'] == question)


TASKS = [item(f't{n}', 'task') for n in range(1, 11)]
RULES = [item(f'rule-R{n}', 'rule') for n in range(1, 4)]


class AgreementTest(unittest.TestCase):
    def report(self, *docs, **kwargs):
        labels = kwargs.pop('labels', [chr(ord('A') + n) for n in range(len(docs))])
        return ra.agreement([as_loaded(d, f'{l}.json') for d, l in zip(docs, labels)], labels, **kwargs)

    def test_perfect_agreement(self):
        items = RULES + TASKS[:4]
        same = {it['id']: verdict(it['id'], it['kind']) for it in items}
        rep = self.report(export(items, same), export(items, same, tag='b'))
        for r in rep['results']:
            self.assertEqual(r['n'], r['items_in_scope'], r)
            self.assertEqual((r['percent_agreement'], r['pa'], r['ac1']), (100.0, 1.0, 1.0), r)
            self.assertEqual(r['disagreements'], [])
        # One answer only, so Cohen's kappa would be 0/0 here; AC1 stays defined.
        self.assertEqual(row(rep, 'task', 'q1')['pe'], 0.0)
        self.assertEqual({r['kind'] for r in rep['results']}, {'rule', 'task', 'all'})
        self.assertEqual(len([r for r in rep['results'] if r['kind'] == 'rule']), 4 + 2)

    def test_known_disagreement_matches_hand_computed_ac1(self):
        # q1: A says N only on t10, B says N on t9 and t10. Agreement 9/10.
        # pi_Y = (0.9 + 0.8) / 2 = 0.85, p_e = 2 * 0.85 * 0.15 = 0.255,
        # AC1 = (0.9 - 0.255) / (1 - 0.255) = 0.645 / 0.745. (Cohen's kappa would be 0.615.)
        a = {t['id']: verdict(t['id'], 'task') for t in TASKS}
        b = {t['id']: verdict(t['id'], 'task') for t in TASKS}
        a['t10'] = verdict('t10', 'task', 'fix', 'med', q1='N')
        b['t9'] = verdict('t9', 'task', 'fix', 'med', q1='N')
        b['t10'] = verdict('t10', 'task', 'fix', 'med', q1='N')
        rep = self.report(export(TASKS, a), export(TASKS, b))
        q1 = row(rep, 'task', 'q1')
        self.assertEqual((q1['n'], q1['full_agreement'], q1['percent_agreement']), (10, 9, 90.0))
        self.assertAlmostEqual(q1['pe'], 0.255, places=6)
        self.assertAlmostEqual(q1['ac1'], 0.645 / 0.745, places=6)
        self.assertEqual(q1['disagreements'], ['t9'])
        self.assertEqual(q1['disagreement_answers']['t9']['answers'], {'A': 'Y', 'B': 'N'})
        self.assertEqual(q1['answer_counts'], {'A': {'N': 1, 'Y': 9}, 'B': {'N': 2, 'Y': 8}})
        self.assertEqual(row(rep, 'task', 'q2')['ac1'], 1.0)

    def test_three_category_decision_by_hand(self):
        # Four tasks. A: approve, approve, fix, reject; B: approve, fix, fix, approve.
        # p_a = 2/4; pi = approve 0.5, fix 0.375, reject 0.125;
        # p_e = (0.25 + 0.234375 + 0.109375) / 2 = 0.296875; AC1 = 0.203125 / 0.703125 = 13/45.
        tasks = TASKS[:4]
        da, db = ['approve', 'approve', 'fix', 'reject'], ['approve', 'fix', 'fix', 'approve']
        a = {t['id']: verdict(t['id'], 'task', d) for t, d in zip(tasks, da)}
        b = {t['id']: verdict(t['id'], 'task', d) for t, d in zip(tasks, db)}
        dec = row(self.report(export(tasks, a), export(tasks, b)), 'task', 'decision')
        self.assertEqual(dec['categories'], ['approve', 'fix', 'reject'])
        self.assertAlmostEqual(dec['pa'], 0.5)
        self.assertAlmostEqual(dec['pe'], 0.296875)
        self.assertAlmostEqual(dec['ac1'], 13 / 45, places=6)
        self.assertEqual(dec['disagreements'], ['t2', 't4'])

    def test_three_reviewers_use_the_multi_rater_formula(self):
        # Items: (Y,Y,Y), (Y,Y,N), (N,N,N). p_a = (1 + 1/3 + 1) / 3 = 7/9; pi_Y = 5/9;
        # p_e = 2 * 5/9 * 4/9 = 40/81; AC1 = (7/9 - 40/81) / (1 - 40/81) = 23/41.
        tasks = TASKS[:3]
        answers = [('Y', 'Y', 'N'), ('Y', 'Y', 'N'), ('Y', 'N', 'N')]  # per reviewer, items t1..t3
        docs = []
        for n, per_item in enumerate(answers):
            docs.append(export(tasks, {t['id']: verdict(t['id'], 'task', q1=v) for t, v in zip(tasks, per_item)},
                               tag=str(n)))
        q1 = row(self.report(*docs), 'task', 'q1')
        self.assertAlmostEqual(q1['pa'], 7 / 9, places=6)
        self.assertAlmostEqual(q1['ac1'], 23 / 41, places=6)
        self.assertEqual((q1['full_agreement'], q1['disagreements']), (2, ['t2']))

    def test_missing_answers_are_counted_not_imputed(self):
        a = {t['id']: verdict(t['id'], 'task') for t in TASKS}
        b = {t['id']: verdict(t['id'], 'task') for t in TASKS}
        del b['t1']                      # never reviewed
        del b['t2']                      # reviewed on older item content: the desk exports null + stale
        del b['t3']['q2']                # decision given, q2 left unanswered
        b['t4']['q3'] = ''               # an empty answer is missing too
        b['t5']['item_hash'] = 'h-old'   # a verdict for other content is treated as stale
        rep = self.report(export(TASKS, a), export(TASKS, b, stale={'t2'}))
        reviewer_b = rep['reviewers'][1]
        self.assertEqual(reviewer_b['not_reviewed'], ['t1'])
        self.assertEqual(reviewer_b['stale'], ['t2', 't5'])
        self.assertEqual((reviewer_b['reviewed'], reviewer_b['with_decision']), (7, 7))
        q1, q2, q3 = (row(rep, 'task', q) for q in ('q1', 'q2', 'q3'))
        self.assertEqual((q1['n'], q1['single_answer'], q1['no_answer']), (7, 3, 0))
        self.assertEqual((q2['n'], q2['single_answer'], q2['unanswered']), (6, 4, {'B': ['t3']}))
        self.assertEqual((q3['n'], q3['unanswered']), (6, {'B': ['t4']}))
        self.assertEqual(q2['ac1'], 1.0)  # agreement is computed on the answered items only

    def test_no_item_with_two_answers_gives_no_coefficient(self):
        a = {t['id']: verdict(t['id'], 'task') for t in TASKS[:2]}
        rep = self.report(export(TASKS[:2], a), export(TASKS[:2], {}))
        q1 = row(rep, 'task', 'q1')
        self.assertEqual((q1['n'], q1['ac1'], q1['percent_agreement'], q1['single_answer']), (0, None, None, 2))

    def test_item_list_and_excluded_questions(self):
        items = RULES + TASKS
        a = {it['id']: verdict(it['id'], it['kind']) for it in items}
        b = {it['id']: verdict(it['id'], it['kind']) for it in RULES + TASKS[:2]}
        rep = self.report(export(items, a), export(items, b), items=['rule-R1', 'rule-R2', 'rule-R3', 't1', 't2'],
                          exclude=['rule:q4'])
        self.assertEqual(rep['scope']['items_in_scope'], 5)
        self.assertNotIn(('rule', 'q4'), {(r['kind'], r['question']) for r in rep['results']})
        self.assertEqual(row(rep, 'task', 'q1')['n'], 2)
        self.assertEqual(row(rep, 'all', 'decision')['n'], 5)
        with self.assertRaises(ra.InputError):
            self.report(export(items, a), export(items, b), items=['t1', 'no-such-item'])
        with self.assertRaises(ra.InputError):
            self.report(export(items, a), export(items, b), exclude=['rule:q9'])

    def test_unknown_item_kind_is_analysed_by_its_question_keys(self):
        traces = [item(f'trace-{n}', 'trace') for n in range(1, 4)]
        a = {t['id']: verdict(t['id'], 'trace') for t in traces}
        b = {t['id']: verdict(t['id'], 'trace') for t in traces}
        b['trace-2'] = verdict('trace-2', 'trace', 'fix', 'med', q2='N')
        rep = self.report(export(traces, a), export(traces, b))
        self.assertEqual([r['question'] for r in rep['results'] if r['kind'] == 'trace'],
                         ['q1', 'q2', 'q3', 'decision', 'conf'])
        self.assertEqual(row(rep, 'trace', 'q2')['disagreements'], ['trace-2'])

    def test_comments_only_on_request(self):
        a = {t['id']: verdict(t['id'], 'task') for t in TASKS[:2]}
        b = {t['id']: verdict(t['id'], 'task') for t in TASKS[:2]}
        b['t2'] = dict(verdict('t2', 'task', 'fix', 'med', q1='N'), comment='branch wording is ambiguous')
        plain = row(self.report(export(TASKS[:2], a), export(TASKS[:2], b)), 'task', 'q1')
        self.assertNotIn('comments', plain['disagreement_answers']['t2'])
        full = row(self.report(export(TASKS[:2], a), export(TASKS[:2], b), with_comments=True), 'task', 'q1')
        self.assertEqual(full['disagreement_answers']['t2']['comments']['B'], 'branch wording is ambiguous')


class BuildCheckTest(unittest.TestCase):
    def run_cli(self, docs, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for n, doc in enumerate(docs):
                path = Path(tmp) / f'r{n}.json'
                path.write_text(json.dumps(doc))
                paths.append(str(path))
            out = Path(tmp) / 'agreement.json'
            err, std = io.StringIO(), io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(std):
                code = ra.main(paths + ['--output', str(out)] + list(extra))
            report = json.loads(out.read_text()) if out.exists() else None
        return code, report, std.getvalue(), err.getvalue()

    def setUp(self):
        self.a = export(TASKS, {t['id']: verdict(t['id'], 'task') for t in TASKS})
        self.b = export(TASKS, {t['id']: verdict(t['id'], 'task') for t in TASKS}, tag='b')

    def test_same_build_succeeds_and_writes_the_report(self):
        code, report, out, _ = self.run_cli([self.a, self.b], '--labels', 'A', 'B')
        self.assertEqual(code, 0)
        self.assertEqual(report['format'], ra.REPORT_FORMAT)
        self.assertEqual(report['desk']['run_key'], RUN_KEY)
        self.assertIn('task       q1 Instruction clear', out)
        self.assertNotIn('reviewer_id', json.dumps(report['reviewers']))

    def test_different_run_key_exits_2(self):
        other = export(TASKS, {}, run_key='v3-111111111111-practice')
        code, report, _, err = self.run_cli([self.a, other])
        self.assertEqual((code, report), (2, None))
        self.assertIn('run_key', err)

    def test_different_item_set_exits_2(self):
        code, _, _, err = self.run_cli([self.a, export(TASKS[:9], {})])
        self.assertEqual(code, 2)
        self.assertIn('item set differs', err)

    def test_changed_item_content_exits_2(self):
        changed = json.loads(json.dumps(self.b))
        changed['items'][0]['item_hash'] = 'h-new'
        code, _, _, err = self.run_cli([self.a, changed])
        self.assertEqual(code, 2)
        self.assertIn('differ in content', err)

    def test_bad_input_exits_1(self):
        self.assertEqual(self.run_cli([self.a])[0], 1)                  # one export only
        self.assertEqual(self.run_cli([self.a, self.a])[0], 1)          # the same file twice
        self.assertEqual(self.run_cli([self.a, {'items': []}])[0], 1)   # no run key
        same_reviewer = [export(TASKS, {}, reviewer='u1'), export(TASKS, {}, reviewer='u1', tag='b')]
        self.assertEqual(self.run_cli(same_reviewer)[0], 1)


class SampleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desk = load('build_review_desk').build('v3')
        cls.sample = ra.draw_sample(cls.desk, seed=20261110)

    def test_sample_follows_the_stated_rule(self):
        s, items = self.sample, {i['id']: i for i in self.desk['items']}
        fixed = [i for i in s['items'] if items[i]['kind'] in ('rule', 'convention')]
        tasks = [d for d in s['detail'] if d['kind'] == 'task']
        captions = [d for d in s['detail'] if d['kind'] == 'caption']
        self.assertEqual(len(fixed), 9)
        self.assertEqual(len(tasks), 12)
        self.assertEqual(len({tuple(t['cell']) for t in tasks}), 12)  # one task per modality x language cell
        self.assertTrue(all(items[t['id']]['group'] == 'holdout' and items[t['id']]['required'] for t in tasks))
        self.assertEqual(sorted(c['branch'] for c in captions), ['absent'] * 5 + ['present'] * 5)
        self.assertEqual(s['core'], s['items'][:9 + 10 + 8])
        self.assertEqual(s['run_key'], self.desk['meta']['run_key'])

    def test_sample_is_reproducible_and_depends_on_the_seed(self):
        self.assertEqual(ra.draw_sample(self.desk, seed=20261110)['items'], self.sample['items'])
        self.assertNotEqual(ra.draw_sample(self.desk, seed=1)['items'], self.sample['items'])

    def test_protocol_lists_the_drawn_sample(self):
        text = (ROOT / 'docs' / 'peer_review_protocol.md').read_text(encoding='utf-8')
        block = text.split('<!-- sample:begin -->')[1].split('<!-- sample:end -->')[0]
        listed = re.findall(r'`((?:rule|conv|cap)-[\w-]+|v3_holdout_\w+)`', block)
        self.assertEqual(listed, self.sample['items'])

    def test_command_line_draw(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, out = Path(tmp) / 'desk.json', Path(tmp) / 'sample.json'
            data.write_text(json.dumps(self.desk, ensure_ascii=False))
            with contextlib.redirect_stdout(io.StringIO()):
                code = ra.main(['--draw-sample', str(data), '--seed', '20261110', '--output', str(out)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.read_text())['items'], self.sample['items'])
            self.assertEqual(ra.read_items_file(out), self.sample['items'])


if __name__ == '__main__':
    unittest.main()
