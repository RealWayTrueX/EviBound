"""The human review desk: independent checks, faithful translation, export format."""
import importlib.util
import json
import re
import sys
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


desk = load('build_review_desk')
SEGMENT = re.compile(r'^[A-Za-z0-9_\-.~:@+]{1,200}$')


class ReviewDeskTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = desk.build('v3')
        cls.items = cls.data['items']
        cls.tasks = [i for i in cls.items if i['kind'] == 'task']

    def test_item_inventory(self):
        counts = self.data['meta']['counts']
        self.assertEqual(counts, {'rule': 6, 'convention': 3, 'caption': 39, 'task': 84})
        # REQUIRED tasks follow the v3 bundle: every holdout task plus every dev A3 task.
        self.assertEqual(sum(t['required'] for t in self.tasks), 77)
        self.assertEqual(len({i['id'] for i in self.items}), len(self.items))

    def test_independent_checks_agree_with_the_frozen_corpus(self):
        failed = [(i['id'], c['en']) for i in self.items for c in i['checks'] if not c['ok']]
        self.assertEqual(failed, [])

    def test_every_task_is_translated_and_has_four_questions(self):
        for task in self.tasks:
            self.assertRegex(task['instruction']['zh'], r'[一-鿿]')
            self.assertTrue(all(re.search(r'[一-鿿]', r['zh']) for r in task['readings']))
            self.assertEqual([q['key'] for q in task['questions']], ['q1', 'q2', 'q3', 'q4'])
            self.assertTrue(all(q['hint']['zh'] for q in task['questions']))

    def test_translation_reads_the_words_not_the_labels(self):
        text = ('Configure the kitchen for soft lighting. If the presence observation says someone is present, '
                'achieve light=high, fan=off. If nobody is present, achieve fan=low. Use the observation to '
                'choose the branch. Make only necessary writes and obey the device rules.')
        parsed = desk.translate_instruction(text)
        self.assertEqual(parsed['present'], {'light': 'high', 'fan': 'off'})
        self.assertIn('灯=2 档（high）', parsed['zh'])
        everyday = desk.translate_instruction(
            "Can you set up the office? If someone is in there, I'd like the light on and strong airflow. "
            "If it's empty, a gentle breeze.")
        self.assertEqual(everyday['present'], {'light': 'low', 'fan': 'high'})
        self.assertIn('开着灯', everyday['zh'])
        self.assertNotIn('1 档', everyday['zh'])  # words are translated, not converted to levels

    def test_a_changed_instruction_fails_the_reading_check(self):
        task = json.loads((ROOT / 'data/scenarios_v3/holdout.jsonl').read_text().splitlines()[0])
        task['instruction'] = task['instruction'].replace('achieve light=low', 'achieve light=high')
        item = desk.task_item(task, True)
        self.assertFalse(item['instruction']['reading_ok'])
        self.assertIn(False, [c['ok'] for c in item['checks']])

    def test_unknown_sentences_are_errors(self):
        with self.assertRaises(ValueError):
            desk.translate_instruction('Please make the kitchen cosy.')
        with self.assertRaises(ValueError):
            desk.translate_caption('A dog is barking in the kitchen.')

    def test_builder_imports_no_project_code(self):
        source = (SCRIPTS / 'build_review_desk.py').read_text()
        imports = [line for line in source.splitlines() if re.match(r'\s*(from|import)\s', line)]
        for line in imports:
            self.assertNotRegex(line, r'evibound|scenario_v2_lib|generate_scenarios|check_scenarios|build_review_bundle|backend|oracle')

    def test_csv_columns_match_the_signoff_script(self):
        bundle = load('build_review_bundle')
        columns = self.data['meta']['csv_columns']
        self.assertEqual(columns, ['task_id', 'split', 'family', 'perturbation', 'required'] + bundle.QCOLS
                         + ['decision', 'comment'])

    def test_store_paths_are_valid(self):
        self.assertRegex(self.data['meta']['run_key'], SEGMENT)
        for item in self.items:
            self.assertRegex(item['id'], SEGMENT)

    def test_rendered_pages(self):
        local = desk.render(self.data, body_only=False)
        body = desk.render(self.data, body_only=True)
        self.assertTrue(local.startswith('<!doctype html>'))
        self.assertLess(local.index('<title>'), local.index('<body>'))
        self.assertFalse(body.lower().startswith('<!doctype'))
        self.assertTrue(body.startswith('<title>'))
        for page in (local, body):
            self.assertNotIn('/*__REVIEW_DATA__*/', page)
            self.assertNotIn('confirm(', page)
            self.assertLess(len(page.encode()), 16 * 1024 * 1024)

    def test_practice_mode_for_the_frozen_corpus(self):
        meta = self.data['meta']
        self.assertEqual(meta['mode'], 'practice')
        self.assertTrue(meta['run_key'].endswith('-practice'))
        self.assertIn('--signoff', meta['banner']['zh'])


if __name__ == '__main__':
    unittest.main()
