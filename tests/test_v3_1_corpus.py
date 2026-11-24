"""v3.1 corpus, its checker, and the analysis pipeline (CPU only, scripted planner)."""

import copy
import json
import random
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import analyze_v3_1  # noqa: E402
import check_scenarios_v3_1 as check  # noqa: E402
import generate_scenarios_v3_1 as gen  # noqa: E402
import v3_1_lib as lib  # noqa: E402
from evibound.attainability import DEVICES, attainability  # noqa: E402
from evibound.backend_v3 import WorldV3  # noqa: E402
from evibound.planner_v3 import messages_for_v3  # noqa: E402
from evibound.recovery_v3_1 import V31_CONDITIONS  # noqa: E402
from scenario_v2_lib import render_instruction  # noqa: E402

CORPUS = ROOT / 'data/scenarios_v3_1'


def load(split):
    return [json.loads(line) for line in (CORPUS / f'{split}.jsonl').read_text().splitlines()]


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        cls._cwd = os.getcwd()
        os.chdir(ROOT)
        cls.pool = gen.frame()

    @classmethod
    def tearDownClass(cls):
        import os
        os.chdir(cls._cwd)

    def test_generation_is_deterministic_and_matches_the_committed_files(self):
        rng = random.Random(gen.SEED)
        chosen = gen.select(self.pool, rng)
        for split in gen.SPLIT_ORDER:
            rows = gen.build_rows(split, chosen[split], rng)
            text = ''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows)
            self.assertEqual(text, (CORPUS / f'{split}.jsonl').read_text(), split)

    def test_frame_is_fresh_and_both_rule_implementations_agree_on_every_structure(self):
        earlier = gen.earlier_structure_ids(ROOT)
        self.assertEqual(len(self.pool), 327)
        self.assertEqual(Counter(c['_stratum'] for c in self.pool),
                         {'full_dual': 82, 'full_scoped': 95, 'part': 101, 'none': 49})
        for cand in self.pool:
            self.assertNotIn(cand['_pid'], earlier)
            att = attainability(cand)                      # oracle rule function
            mine = cand['_att']                            # scenario rule library
            self.assertEqual((att.cls, list(att.attained[0]), dict(zip(DEVICES, att.targets[0])), att.shortest),
                             (mine['class'], mine['attained'], mine['target'], len(mine['shortest_plan'])))
            self.assertEqual(len(att.targets), 1)

    def test_explicit_wording_is_the_v3_wording_when_both_branches_ask_for_something(self):
        present, absent = {'light': 'low', 'fan': 'off'}, {'fan': 'low'}
        self.assertEqual(gen.render_explicit('study', 'soft lighting', present, absent),
                         render_instruction('study', 'soft lighting', present, absent))
        text = gen.render_explicit('study', 'soft lighting', present, {})
        self.assertIn('If nobody is present, leave all devices unchanged.', text)
        self.assertNotIn('achieve leave', text)


class CorpusTests(unittest.TestCase):
    def test_splits_are_disjoint_balanced_and_usable_by_the_engine(self):
        holdout, dev = load('holdout'), load('dev')
        self.assertEqual((len(holdout), len(dev)), (276, 36))
        ids = [t['physical_structure_id'] for t in holdout + dev]
        self.assertEqual(len(set(ids)), 312)
        self.assertEqual(Counter(t['labels']['attainability'] for t in holdout), {'full': 156, 'part': 84, 'none': 36})
        self.assertEqual(Counter(t['perturbation'] for t in holdout), {'tamper': 138, 'replay': 138})
        self.assertEqual(set(Counter((t['observation']['modality'], t['language']) for t in holdout).values()), {23})
        for task in holdout + dev:
            for variant in ('clean', 'perturbed', 'boundary'):
                world = WorldV3(task, variant)
                messages = messages_for_v3(task, world.state, world.observe())
                self.assertIn(task['instruction'], messages[1]['content'])

    def test_checker_passes_on_the_committed_corpus(self):
        before = (CORPUS / 'check_report.json').read_text()
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/check_scenarios_v3_1.py')],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout[-2000:])
        self.assertEqual((CORPUS / 'check_report.json').read_text(), before)
        self.assertEqual(json.loads(before)['total_errors'], 0)

    def test_checker_catches_wrong_labels_text_and_semantics(self):
        tasks = {t['task_id']: t for t in load('holdout')}
        part = next(t for t in tasks.values() if t['labels']['attainability'] == 'part' and t['language'] == 'explicit')
        full = next(t for t in tasks.values() if t['labels']['attainability'] == 'full'
                    and t['labels']['writes_needed'] >= 2 and t['language'] == 'scene')
        for task in (part, full):
            self.assertEqual(check.semantic_errors(task) + check.label_errors(task) + check.text_errors(task)
                             + check.simulator_errors(task), [])

        def mutated(task, path, value):
            clone = copy.deepcopy(task)
            node = clone
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
            return clone

        self.assertTrue(check.label_errors(mutated(part, ['labels', 'attainability'], 'full')))
        self.assertTrue(check.label_errors(mutated(part, ['annotations', 'attainability', 'target'], {'light': 'high', 'fan': 'high'})))
        self.assertTrue(check.label_errors(mutated(full, ['labels', 'writes_needed'], 1)))
        self.assertTrue(check.label_errors(mutated(full, ['authorized'], ['light'])))            # structure id no longer matches
        self.assertTrue(check.text_errors(mutated(part, ['instruction'], part['instruction'].replace('achieve', 'reach', 1))))
        self.assertTrue(check.text_errors(mutated(full, ['instruction'], full['instruction'].replace('=', ' is ', 1))))
        self.assertTrue(check.text_errors(mutated(full, ['observation', 'payload_present'], full['observation']['payload_absent'])))
        self.assertTrue(check.semantic_errors(mutated(full, ['goal_absent'], dict(full['goal_present']))))
        self.assertTrue(check.semantic_errors(mutated(full, ['goal_present'], {'light': 'high', 'fan': 'high'})))
        self.assertTrue(check.semantic_errors(mutated(part, ['authorized_subgoal_present'], {'light': 'high', 'fan': 'low'})))
        self.assertTrue(check.simulator_errors(mutated(full, ['annotations', 'attack_expects_unsafe'],
                                                       not full['annotations']['attack_expects_unsafe'])))


class PipelineTests(unittest.TestCase):
    def test_scripted_run_analyses_identically_from_traces_and_from_fingerprints(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ids = [t['task_id'] for t in load('dev')][:9]
            subprocess.run([sys.executable, str(ROOT / 'scripts/run_experiment_v3_1.py'), '--corpus', 'v3_1',
                            '--split', 'dev', '--planner', 'scripted:hasty', '--seeds', '11', '--task-ids', *ids,
                            '--output', str(tmp / 'episodes.jsonl')], check=True, capture_output=True, cwd=ROOT)
            rows, _, disagreements = analyze_v3_1.load_rows([tmp / 'episodes.jsonl'])
            self.assertEqual((len(rows), disagreements), (9 * 3 * len(V31_CONDITIONS), []))
            lib.write_fingerprints(rows, tmp / 'fp.json.gz', [], 'test')
            again = lib.read_fingerprints(tmp / 'fp.json.gz')
            tasks = lib.load_tasks(CORPUS / 'dev.jsonl')
            first = analyze_v3_1.analyze(rows, tasks, resamples=200)
            second = analyze_v3_1.analyze(again, tasks, resamples=200)
            self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
            self.assertEqual(first['replay_disagreements'], 0)
            self.assertTrue(first['design']['complete_matrix'])
            self.assertEqual(set(first['decisions']), {'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'S1'})
            # the guard never lets an unsafe or unauthorized write through, whatever the feedback level
            for item in first['summary']:
                if item['condition'].startswith('M'):
                    self.assertEqual((item['unsafe_effect'], item['authorization_violation']), (0, 0), item)

    def test_contrast_plan_is_well_formed(self):
        ids = [c['id'] for c in analyze_v3_1.PRIMARY + analyze_v3_1.KEEP + analyze_v3_1.SECONDARY]
        self.assertEqual(len(ids), len(set(ids)))
        known = {i for c in (analyze_v3_1.PRIMARY, analyze_v3_1.KEEP) for i in (x['id'] for x in c)}
        for members in analyze_v3_1.JOINT.values():
            self.assertTrue(set(members) <= known)
        for item in analyze_v3_1.PRIMARY + analyze_v3_1.KEEP + analyze_v3_1.SECONDARY:
            self.assertIn(item['metric'], analyze_v3_1.METRICS)
            self.assertIn(item['where'], lib.SUBSETS)
            self.assertTrue({item['left'], item['right']} <= set(V31_CONDITIONS))

    def test_shell_entry_points_parse(self):
        for name in ('run_v3_1.sh', 'v3_1_step.sh', 'v3_1_env.sh'):
            subprocess.run(['bash', '-n', str(ROOT / 'scripts' / name)], check=True)


if __name__ == '__main__':
    unittest.main()
