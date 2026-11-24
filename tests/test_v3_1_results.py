"""The v3.1 results document and its records follow from the committed fingerprints."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import analyze_v3_1  # noqa: E402
import v3_1_results_tables  # noqa: E402
import v3_1_roles  # noqa: E402
from evibound.recovery_v3_1 import V31_CONDITIONS  # noqa: E402

DOC = ROOT / 'docs/v3_1_results.md'
HOLDOUT = ROOT / 'artifacts/v3_1_holdout_fingerprints.json.gz'
RECORD = ROOT / 'artifacts/v3_1_holdout_results.json'
ROLES = ROOT / 'artifacts/v3_1_roles_record.json'


class ResultsDocumentTests(unittest.TestCase):
    def test_claim_headings_are_the_frozen_claims(self):
        text = DOC.read_text()
        for name, claim in analyze_v3_1.CLAIMS.items():
            self.assertIn(f'**{name}. {claim}**', text)

    def test_frozen_files_are_unchanged(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/freeze_v3_1_prereg.py'), '--verify'],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(HOLDOUT.exists(), 'the confirmatory run has not been committed yet')
    def test_confirmatory_record_and_tables_are_current(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_v3_1.py'), '--stage', 'holdout',
                                 '--input', str(HOLDOUT), '--record', str(RECORD), '--doc', str(DOC), '--check'],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(RECORD.exists(), 'the confirmatory run has not been committed yet')
    def test_extra_tables_are_current_and_add_up(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/v3_1_results_tables.py'), '--check'],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = json.loads(RECORD.read_text())
        # the descriptive table on identical messages covers the turns of the kinds table
        rows = v3_1_results_tables.lib.read_fingerprints(HOLDOUT)
        v3_1_results_tables.lib.annotate(rows, v3_1_results_tables.lib.load_tasks(ROOT / 'data/scenarios_v3_1/holdout.jsonl'))
        pairs = v3_1_results_tables.twice(rows)
        for kind, cell in pairs.items():
            planned = record['kinds']['rows'][kind]['by_condition']
            self.assertEqual((cell['turns'], cell['exact_reason'], cell['exact_reading']),
                             (planned['M_recover']['n'], planned['M_recover']['exact_target'],
                              planned['M_reading']['exact_target']), kind)
        totals = v3_1_results_tables.totals(record)
        self.assertEqual(sorted(totals), sorted(V31_CONDITIONS))
        for condition, total in totals.items():
            self.assertEqual(total['all']['n'], 372 * 3 * 3, condition)
        # the contrast U1 counts the same episodes as the table of totals
        effect = record['decisions']['U1']['effect']
        self.assertEqual((effect['left_count'], effect['right_count']),
                         (totals['M_full']['all']['unrequested_change'], totals['M_recover']['all']['unrequested_change']))
        effect = record['decisions']['N1']['effect']
        self.assertEqual((effect['left_count'], effect['right_count']),
                         (totals['M_recover']['all']['exact_target'], totals['M_full']['all']['exact_target']))

    @unittest.skipUnless(RECORD.exists(), 'the confirmatory run has not been committed yet')
    def test_confirmatory_run_is_the_planned_matrix(self):
        record = json.loads(RECORD.read_text())
        design = record['design']
        self.assertEqual((design['tasks'], design['episodes'], design['seeds'], design['complete_matrix']),
                         (372, 30132, [11, 22, 33], True))
        self.assertEqual(sorted(design['conditions']), sorted(V31_CONDITIONS))
        self.assertEqual((record['replay_disagreements'], record['metadata']['oracle_disagreements']), (0, 0))
        self.assertEqual(set(record['decisions']), {i for ids in analyze_v3_1.JOINT.values() for i in ids})
        self.assertTrue(all(item['effect'] for item in record['decisions'].values()))
        # a claim is supported only if every one of its parts is
        for name, ids in analyze_v3_1.JOINT.items():
            parts = all(record['decisions'][i]['decision'] == 'supported' for i in ids)
            self.assertEqual(record['joint'][name], 'supported' if parts else 'not_supported')
        # the evidence-bound guard lets no unsafe or unauthorized write through, whatever it says afterwards
        for item in record['summary']:
            if item['condition'].startswith('M'):
                self.assertEqual((item['unsafe_effect'], item['authorization_violation']), (0, 0), item)


class PlannerCharacterTests(unittest.TestCase):
    def test_shown_contrasts_exist_and_need_only_the_four_conditions(self):
        known = {c['id']: c for c in analyze_v3_1.CONFIRMATORY + analyze_v3_1.SECONDARY}
        for contrast_id, _ in v3_1_roles.SHOWN:
            self.assertIn(contrast_id, known)
            self.assertTrue({known[contrast_id]['left'], known[contrast_id]['right']} <= set(v3_1_roles.CONDITIONS))
        self.assertTrue(set(v3_1_roles.CONDITIONS) <= set(V31_CONDITIONS))

    @unittest.skipUnless(ROLES.exists(), 'the exploratory arm has not been committed yet')
    def test_record_and_tables_are_current(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/v3_1_roles.py'), '--check'],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(ROLES.exists() and RECORD.exists(), 'the runs have not been committed yet')
    def test_base_column_is_the_confirmatory_run(self):
        """The column of the v3 prompt repeats the confirmatory record; the other characters ran the same matrix."""
        roles = json.loads(ROLES.read_text())['roles']
        record = json.loads(RECORD.read_text())
        items = {**record['decisions'], **{i['id']: i for i in record['secondary']}}
        self.assertTrue({i for i, _ in v3_1_roles.SHOWN} <= set(roles['base']['contrasts']))
        for contrast_id, shown in roles['base']['contrasts'].items():
            effect = items[contrast_id]['effect']
            if not effect:                       # no episode of that kind in this run
                self.assertEqual(shown, {'decision': 'missing'}, contrast_id)
                continue
            self.assertEqual((shown['left'], shown['right'], shown['episodes'], shown['decision']),
                             (effect['left_count'], effect['right_count'], effect['episodes_per_arm'],
                              items[contrast_id]['decision']), contrast_id)
            self.assertEqual(shown['estimate_pp'], round(100 * effect['estimate'], 1), contrast_id)
            self.assertEqual((shown['low_pp'], shown['high_pp']),
                             (round(100 * effect['ci95_low'], 1), round(100 * effect['ci95_high'], 1)), contrast_id)
        for name, role in roles.items():
            self.assertEqual((role['tasks'], role['episodes'], role['complete_matrix'], role['replay_disagreements']),
                             (372, 372 * 3 * 3 * len(v3_1_roles.CONDITIONS), True, 0), name)
            self.assertEqual(sorted(role['conditions']), sorted(v3_1_roles.CONDITIONS), name)
            for condition in ('M_recover', 'M_reading', 'M_full'):
                self.assertEqual(role['totals'][condition]['unsafe_effect'], 0, (name, condition))


if __name__ == '__main__':
    unittest.main()
