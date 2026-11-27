"""Review desk for the v3.1 corpus (checked by the owner after the run)."""

import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import build_review_desk as desk  # noqa: E402


class V31ReviewDeskTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = desk.build('v3_1')
        cls.tasks = [i for i in cls.data['items'] if i['kind'] == 'task']

    def test_inventory_and_fixed_required_sample(self):
        self.assertEqual(self.data['meta']['counts']['task'], 420)
        required = [t for t in self.tasks if t['required']]
        self.assertEqual(len(required), 84)             # 7 strata x 12 modality-language cells
        self.assertTrue(all(t['group'] == 'holdout' for t in required))
        cells = Counter((t['modality'], t['instruction']['style']) for t in required)
        self.assertEqual(set(cells.values()), {7})
        self.assertEqual(len({i['id'] for i in self.data['items']}), len(self.data['items']))

    def test_the_desk_s_own_rule_engine_agrees_with_every_label(self):
        failed = [(i['id'], c['en']) for i in self.data['items'] for c in i.get('checks', []) if not c['ok']]
        self.assertEqual(failed, [])
        for task in self.tasks:
            self.assertTrue(any('attainability' in c['en'] for c in task['checks']))
            self.assertIn('attainability', [c['k'] for c in task['chips']])

    def test_mode_and_notes_say_that_the_check_follows_the_run(self):
        meta = self.data['meta']
        self.assertEqual(meta['mode'], 'posthoc')
        self.assertTrue(meta['run_key'].startswith('v3_1-') and meta['run_key'].endswith('-posthoc'))
        self.assertIn('2026-11-24', meta['banner']['zh'])
        self.assertIn('敏感性分析', meta['after_note']['zh'])
        self.assertIsNone(meta['chain'])
        page = desk.render(self.data, body_only=False)
        self.assertIn(meta['after_note']['zh'], page)

    def test_a_branch_that_asks_for_nothing_is_parsed_and_translated(self):
        text = ('Configure the study for soft lighting. If the presence observation says someone is present, '
                'achieve light=low. If nobody is present, leave all devices unchanged. Use the observation to '
                'choose the branch. Make only necessary writes and obey the device rules.')
        parsed = desk.translate_instruction(text)
        self.assertEqual((parsed['present'], parsed['absent']), ({'light': 'low'}, {}))
        self.assertIn('如果没人，所有设备保持不变', parsed['zh'])
        self.assertIn('书房', parsed['zh'])
        with self.assertRaises(ValueError):
            desk.translate_instruction(text.replace('leave all devices unchanged', 'do nothing'))

    def test_attainable_part_on_three_hand_made_tasks(self):
        base = {'initial': {'light': 'off', 'fan': 'off', 'presence': True}, 'goal_absent': {}}
        full = dict(base, authorized=['light', 'fan'], goal_present={'light': 'high'})
        part = dict(base, authorized=['light'], goal_present={'light': 'low', 'fan': 'low'})
        none = dict(base, authorized=['light'], goal_present={'fan': 'low'})
        self.assertEqual(desk.attainable_part(full), ('full', {'light': 'high'}, [('light', 'low'), ('light', 'high')]))
        self.assertEqual(desk.attainable_part(part), ('part', {'light': 'low'}, [('light', 'low')]))
        self.assertEqual(desk.attainable_part(none), ('none', {}, []))


if __name__ == '__main__':
    unittest.main()
