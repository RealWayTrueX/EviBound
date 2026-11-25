"""The v3.1 results document and its records follow from the committed fingerprints."""
import json
import re
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

    def test_numbers_in_the_prose_are_in_the_generated_tables(self):
        """A number quoted in a checked paragraph has to occur in a generated block of the document."""
        text = DOC.read_text()
        generated = ' '.join(re.findall(r'<!-- generated:\w+ -->(.*?)<!-- /generated:\w+ -->', text, flags=re.S))
        prose = re.findall(r'<!-- prose:checked -->(.*?)<!-- /prose:checked -->', text, flags=re.S)
        number = re.compile(r'(?<![A-Za-z`_])\d[\d,]*(?:\.\d+)?')
        known = {token.replace(',', '') for token in number.findall(generated)}
        for block in prose:
            for token in number.findall(block):
                value = token.replace(',', '')
                if '.' in value or int(value) >= 10:
                    self.assertTrue(value in known, f'{token} is quoted in the prose and is in no generated table')

    def test_numbers_in_the_readme_are_in_the_generated_tables(self):
        generated = ' '.join(re.findall(r'<!-- generated:\w+ -->(.*?)<!-- /generated:\w+ -->', DOC.read_text(), flags=re.S))
        number = re.compile(r'(?<![A-Za-z`_])\d[\d,]*(?:\.\d+)?')
        known = {token.replace(',', '') for token in number.findall(generated)}
        readme = (ROOT / 'README.md').read_text()
        blocks = re.findall(r'<!-- v3.1:checked -->(.*?)<!-- /v3.1:checked -->', readme, flags=re.S)
        self.assertEqual(len(blocks), 2)             # the English and the Chinese paragraphs
        # the row of the status table: it has to follow the table directly, or it is not rendered as a row
        row = re.findall(r'^\| v3\.1 feedback ladder \(30,132 episodes.*\|$', readme, flags=re.M)
        self.assertEqual(len(row), 1)
        self.assertIn('\n| v3 holdout (7,128 episodes, frozen amended protocol) |', readme.split(row[0])[0][-2500:])
        self.assertTrue(readme.split(row[0])[0].endswith('|\n'))
        blocks.append(row[0].replace('30,132 episodes', ''))
        for block in blocks:
            block = re.sub(r'\d{4}-\d{2}-\d{2}', '', block)        # dates
            for token in number.findall(block):
                value = token.replace(',', '')
                if '.' in value or int(value) >= 10:
                    self.assertTrue(value in known, f'{token} is quoted in the README and is in no generated table')

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
        # the sentence under the table of single seeds: one decision differs, R1 in one seed
        # (the table itself is kept current by the --check above)
        table = re.search(r'<!-- generated:seeds -->(.*?)<!-- /generated:seeds -->', DOC.read_text(), flags=re.S).group(1)
        differing = []
        for line in table.strip().splitlines()[2:]:
            cells = [c.strip() for c in line.strip('|').split('|')]
            decisions = [c.rsplit(';', 1)[1].strip() for c in cells[2:]]
            self.assertEqual(decisions[-1], record['decisions'][cells[1]]['decision'])
            differing += [cells[1] for decision in decisions[:-1] if decision != decisions[-1]]
        self.assertEqual(differing, ['R1'])
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

    @unittest.skipUnless(ROLES.exists(), 'the exploratory arm has not been committed yet')
    def test_what_the_document_says_about_the_characters(self):
        """The paragraph "What the arm shows" in section 9, statement by statement."""
        roles = json.loads(ROLES.read_text())['roles']
        self.assertEqual(sorted(roles), ['base', 'cautious', 'experienced', 'faithful'])
        base = roles['base']['turns_by_kind']
        for name in ('cautious', 'faithful', 'experienced'):
            contrasts = roles[name]['contrasts']
            for contrast_id in ('U1', 'K31', 'N1', 'K36', 'I1', 'K43', 'K54'):
                self.assertEqual(contrasts[contrast_id]['decision'], 'supported', (name, contrast_id))
            for contrast_id in ('R1', 'K37'):       # the same direction, an interval that includes zero
                self.assertEqual(contrasts[contrast_id]['decision'], 'inconclusive', (name, contrast_id))
                self.assertGreater(contrasts[contrast_id]['estimate_pp'], 0, (name, contrast_id))
                self.assertLess(contrasts[contrast_id]['estimate_pp'], roles['base']['contrasts'][contrast_id]['estimate_pp'])
        malformed = 'no review (malformed output and the like)'
        self.assertGreater(roles['faithful']['turns_by_kind'][malformed], 1.8 * base[malformed])
        self.assertLess(roles['faithful']['turns_by_kind'][malformed], 2.2 * base[malformed])
        self.assertGreater(roles['cautious']['turns_by_kind']['empty'], base['empty'])
        self.assertGreater(roles['experienced']['turns_by_kind']['revise'], base['revise'])

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
