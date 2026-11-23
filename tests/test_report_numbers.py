"""The course report takes every number from the committed artifacts.

``scripts/build_report_numbers.py`` writes ``report/generated/*.tex``; the report looks each value up
by key. These tests fail when the generated files are stale, when the report uses a key that does not
exist, or when a headline value changes.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import build_report_numbers as report  # noqa: E402

TEX = ROOT / 'report' / 'evibound_report.tex'


@unittest.skipUnless(TEX.exists(), 'the course report is kept locally, not in the public repository')
class ReportNumbersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.numbers, cls.files = report.outputs()
        cls.values = cls.numbers.values
        cls.tex = TEX.read_text(encoding='utf-8')

    def test_generated_files_match_the_artifacts(self):
        for name, text in self.files.items():
            path = report.OUT / name
            self.assertTrue(path.exists(), f'missing report/generated/{name}')
            self.assertEqual(path.read_text(encoding='utf-8'), text,
                             f'report/generated/{name} is stale: run scripts/build_report_numbers.py')

    def test_every_key_in_the_report_exists(self):
        body = '\n'.join(line for line in self.tex.splitlines() if not line.lstrip().startswith('%'))
        used = set(re.findall(r'\\V\{([^}]+)\}', body))
        for key in re.findall(r'\\ci\{([^}]+)\}', body):
            used.update({f'{key}.lo', f'{key}.hi'})
        used = {key for key in used if '#' not in key}
        self.assertGreater(len(used), 150)
        self.assertEqual(sorted(used - set(self.values)), [])

    def test_contract_decisions(self):
        v = self.values
        self.assertEqual((v['v2.safety.b2'], v['v2.safety.m'], v['v2.cell']), ('30', '0', '72'))
        self.assertEqual((v['v2.safety.est'], v['v2.safety.lo'], v['v2.safety.hi']), ('+36.4', '+18.2', '+59.1'))
        self.assertEqual((v['v2.utility.m'], v['v2.utility.b0']), ('44', '53'))
        self.assertEqual((v['v2.utility.est'], v['v2.utility.lo'], v['v2.utility.hi']),
                         ('$-$13.6', '$-$27.3', '0.0'))
        self.assertEqual(v['v2.margin'], '$-$5')

    def test_clean_episodes_add_up(self):
        v = {key: int(value) for key, value in self.values.items()
             if key in ('v2.cell', 'v2.clean.unreachable', 'v2.clean.empty_both', 'v2.clean.m.safe',
                        'v2.gap.episodes', 'v2.gap.light_jumps', 'v2.gap.fan_jumps', 'v2.utility.b0',
                        'v2.utility.m')}
        self.assertEqual(v['v2.clean.unreachable'] + v['v2.clean.empty_both'] + v['v2.clean.m.safe']
                         + v['v2.gap.episodes'], v['v2.cell'])
        self.assertEqual(v['v2.utility.b0'] - v['v2.utility.m'], v['v2.gap.episodes'])
        self.assertEqual(v['v2.gap.light_jumps'] + v['v2.gap.fan_jumps'], v['v2.gap.episodes'])

    def test_holdout_scope_breakdown_adds_up(self):
        v = {key: int(value) for key, value in self.values.items() if key.startswith('v3.scope.')}
        self.assertEqual(v['v3.scope.in.n'] + v['v3.scope.out.n'], int(self.values['v3.cell']))
        self.assertEqual(v['v3.scope.in.b0'] + v['v3.scope.out.b0'], int(self.values['v3.U1.right']))
        self.assertEqual(v['v3.scope.in.mfull'], int(self.values['v3.U1.left']))
        self.assertEqual(v['v3.scope.in.b0_violation'] + v['v3.scope.out.b0'],
                         int(self.values['v3.clean.b0.noncompliant']))

    def test_no_full_guard_episode_was_unsafe(self):
        for key, value in self.values.items():
            if re.fullmatch(r'v[23]\.(att|clean|bound)\.(m|mfull|refresh)\.unsafe', key):
                self.assertEqual(value, '0', key)

    def test_report_has_no_private_details(self):
        self.assertIsNone(re.search(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', self.tex))
        for word in ('student id', 'student number', 'planner_token'):
            self.assertNotIn(word, self.tex.lower())

    def test_report_states_the_unsupported_results(self):
        flat = ' '.join(self.tex.split())
        for phrase in ('safety hypothesis is supported', 'utility hypothesis is not supported',
                       'not a structural holdout', 'is post hoc', 'not a guarantee'):
            self.assertTrue(phrase in flat, phrase)

    def test_snapshot_does_not_overstate_the_test_suite(self):
        suite = unittest.TestLoader().discover(str(ROOT / 'tests'), pattern='test_*.py')
        self.assertGreaterEqual(suite.countTestCases(), report.SNAPSHOT['unit_tests'])
        self.assertGreater(report.SNAPSHOT['unit_tests'], 100)


if __name__ == '__main__':
    unittest.main()
