"""The report's figures are drawn from the committed records, and its worked example is a real episode.

``scripts/build_report_figures.py`` (charts) and ``scripts/build_report_diagrams.py`` (schematics) take
every plotted value and every fact of the worked example from the artifacts. These tests fail when a
figure would show something the records do not say. The checks on the typeset report itself run only
where the report exists; it is kept locally, not in the public repository.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import build_report_diagrams as diagrams  # noqa: E402
import build_report_figures as figures  # noqa: E402
import build_report_numbers as report  # noqa: E402
import report_style as style  # noqa: E402

TEX = ROOT / 'report' / 'evibound_report.tex'


class FigureDataTest(unittest.TestCase):
    def test_claims_figure_shows_the_frozen_decisions(self):
        record = report.v31_record()
        data = figures.data_claims()
        shown = [row for group in data['groups'] for row in group['rows']]
        self.assertEqual([row['id'] for row in shown], list(report.V31_CONFIRMATORY))
        for row in shown:
            item = record['decisions'][row['id']]
            self.assertAlmostEqual(row['estimate'], 100 * item['effect']['estimate'])
            self.assertAlmostEqual(row['low'], 100 * item['effect']['ci95_low'])
            self.assertAlmostEqual(row['high'], 100 * item['effect']['ci95_high'])
            self.assertEqual(row['decision'].replace('not supported', 'unsupported'), item['decision'])
            self.assertEqual(row['rule'], item['rule'])
        self.assertEqual({group['claim']: group['outcome'] for group in data['groups']},
                         {claim: outcome.replace('_', ' ') for claim, outcome in record['joint'].items()})
        self.assertEqual([group['outcome'] for group in data['groups']].count('not supported'), 1)

    def test_ladder_figure_shows_the_recorded_counts(self):
        record = report.v31_record()
        totals = report.v31_totals(record)
        data = figures.data_ladder()
        self.assertEqual([row['condition'] for row in data['rows']],
                         ['M', 'M_recover', 'M_reading', 'M_full', 'M_menu2', 'M_plan', 'M_seq', 'B2_plan', 'B0'])
        for row in data['rows']:
            total = totals[row['condition']]
            self.assertEqual((row['exact'], row['unrequested'], row['n']),
                             (total['exact_target'], total['unrequested_change'], total['episodes']))
        by_condition = {row['condition']: row for row in data['rows']}
        # the two lists are the only messages with about twice the unrequested changes of the reason alone
        reason = by_condition['M_recover']['unrequested']
        for condition, row in by_condition.items():
            if row['group'] == 'list':
                self.assertGreater(row['unrequested'], 1.8 * reason, condition)
            elif row['group'] in ('describe', 'plan'):
                self.assertLess(row['unrequested'], 1.1 * reason, condition)
        kinds = record['kinds']['rows']
        for kind, _ in figures.KINDS:
            self.assertEqual(by_condition['M_plan']['kinds'][kind]['exact'],
                             kinds[kind]['by_condition']['M_plan']['exact_target'])

    @unittest.skipUnless((report.ART / 'homes_record.json').exists(), 'the exploratory scale study has not been recorded')
    def test_scale_figure_shows_the_recorded_rates(self):
        record = report.load('homes_record.json')
        data = figures.data_scale()
        self.assertEqual([h['states'] for h in data['homes']], [18, 162, 648])
        names = dict(figures.SCALE_PLANNERS)
        for panel, series in figures.SCALE_SERIES.items():
            for (key, label, _, condition, metric, variant), drawn in zip(series, data['panels'][panel]):
                self.assertEqual((drawn['key'], drawn['label']), (key, label))
                for planner, values in drawn['values'].items():
                    homes = record['planners'][next(k for k, v in names.items() if v == planner)]['homes']
                    for name, value in zip('SML', values):
                        cell = homes[name]['by_variant'][variant][condition] if variant else homes[name]['totals'][condition]
                        self.assertAlmostEqual(value, 100 * cell[metric] / cell['episodes'])
        # the evidence-bound guard let no unsafe write through in any home, under any planner
        bound = next(s for s in data['panels']['unsafe'] if s['key'] == 'reason')
        self.assertTrue(all(v == 0 for values in bound['values'].values() for v in values))
        # the reference points are each planner's own Study 3; the first planner's are the confirmatory run
        study3 = report.load('v3_1_models_record.json')['models']
        confirmatory = report.v31_totals(report.v31_record())
        listed = next(s for s in data['panels']['unrequested'] if s['key'] == 'list')
        self.assertAlmostEqual(listed['study3']['Qwen2.5-7B'],
                               100 * confirmatory['M_full']['unrequested_change'] / confirmatory['M_full']['episodes'])
        for planner, value in listed['study3'].items():
            total = study3[next(k for k, v in names.items() if v == planner)]['totals']['M_full']
            self.assertAlmostEqual(value, 100 * total['unrequested_change'] / total['episodes'])

    def test_formal_test_figure_adds_up(self):
        data = figures.data_formal_test()
        by_condition = {row['condition']: row for row in data['rows']}
        self.assertEqual((by_condition['B2']['unsafe'], by_condition['M']['unsafe']), (30, 0))
        self.assertEqual((by_condition['B0']['goal'], by_condition['M']['goal']), (53, 44))
        for row in data['rows']:
            self.assertLessEqual(row['safe'], row['goal'])
            self.assertLessEqual(row['goal'], data['cell'])


class DiagramTest(unittest.TestCase):
    def test_worked_example_is_an_episode_of_the_confirmatory_run(self):
        example = diagrams.example_episode()      # its own assertions compare every stated fact with the records
        self.assertEqual(example['listed'], [{'device': 'fan', 'value': 'low'}])
        ends = {condition: cell['final'] for condition, cell in example['cells'].items()}
        self.assertEqual(sorted(c for c, state in ends.items() if state != example['initial']), ['M_full', 'M_menu2'])

    def test_ladder_of_the_diagram_is_the_ladder_of_the_run(self):
        self.assertEqual([row[0] for row in diagrams.LADDER], [row[0] for row in figures.LADDER])
        self.assertEqual([row[3] for row in diagrams.LADDER], [row[3] for row in figures.LADDER])
        self.assertEqual({row[0] for row in diagrams.LADDER}, {row[0] for row in report.V31_LADDER})

    def test_diagrams_are_editable_vector_drawings(self):
        measured = diagrams.text_width('M', 10) != 10 * 0.5       # False where the font is not installed
        for name, build in diagrams.FIGURES.items():
            diagrams.OVERFLOWS.clear()
            svg = build().svg()
            if measured:
                self.assertEqual(diagrams.OVERFLOWS, [], name)
            self.assertNotIn('<image', svg, name)
            self.assertNotIn('foreignObject', svg, name)
            self.assertGreater(svg.count('<text'), 30, name)
            # every arrowhead that is used is defined
            self.assertEqual(set(re.findall(r'url\(#(head\d+)\)', svg)), set(re.findall(r'<marker id="(head\d+)"', svg)), name)
        diagrams.OVERFLOWS.clear()

    def test_added_metadata_does_not_make_a_diagram_stale(self):
        svg = diagrams.fig_overview().svg()
        diagrams.OVERFLOWS.clear()
        passed_on = svg.replace('font-family=', 'xmlns:c2pa="http://c2pa.org/manifest" font-family=', 1).replace(
            '</svg>', '<metadata><c2pa:manifest>AAAA</c2pa:manifest></metadata></svg>')
        self.assertNotEqual(passed_on, svg)
        self.assertEqual(diagrams.without_metadata(passed_on), svg)
        self.assertEqual(diagrams.without_metadata(svg), svg)

    def test_colour_roles_are_the_checked_palette(self):
        # blue, orange and aqua are the first three slots of the reference palette, which pass its
        # colour-vision checks for every pair; red against blue was checked separately (docs/reproduction.md)
        self.assertEqual((style.BLUE, style.ORANGE, style.AQUA, style.RED), ('#257de0', '#f47230', '#00b894', '#dc3c3d'))
        self.assertEqual(set(style.GROUP_COLOUR), {'describe', 'list', 'plan', 'reference'})


@unittest.skipUnless(TEX.exists(), 'the course report is kept locally, not in the public repository')
class TypesetReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tex = TEX.read_text(encoding='utf-8')
        cls.body, rest = cls.tex.split('\\begin{thebibliography}')
        cls.bibliography = rest.split('\\end{thebibliography}')[0]

    def test_references_are_numbered_in_the_order_they_are_cited(self):
        cited = []
        for group in re.findall(r'\\cite\{([^}]+)\}', self.body):
            for key in (k.strip() for k in group.split(',')):
                if key not in cited:
                    cited.append(key)
        listed = re.findall(r'\\bibitem\{([^}]+)\}', self.bibliography)
        self.assertEqual(listed, cited)

    def test_every_figure_of_the_report_is_built(self):
        used = re.findall(r'\\includegraphics\[[^\]]*\]\{([^}]+)\}', self.tex)
        self.assertEqual(sorted(used), sorted(list(diagrams.FIGURES) + list(figures.DRAW)))
        for name in used:
            self.assertTrue((ROOT / 'report' / 'figures' / f'{name}.pdf').exists(), name)

    def test_committed_diagrams_are_current(self):
        for name, build in diagrams.FIGURES.items():
            diagrams.OVERFLOWS.clear()
            path = ROOT / 'report' / 'figures' / f'{name}.svg'
            self.assertTrue(path.exists(), name)
            if diagrams.text_width('M', 10) != 10 * 0.5:
                self.assertEqual(diagrams.without_metadata(path.read_text(encoding='utf-8')), build().svg(),
                                 f'{name}.svg is stale')
        diagrams.OVERFLOWS.clear()

    def test_report_is_in_the_ieee_format(self):
        self.assertIn('\\documentclass[conference,a4paper]{IEEEtran}', self.tex)
        self.assertTrue((ROOT / 'report' / 'IEEEtran.cls').exists())
        for part in ('\\begin{abstract}', '\\begin{IEEEkeywords}', '\\section{Introduction}',
                     '\\section{Conclusion and Outlook}'):
            self.assertIn(part, self.tex)

    def test_report_does_not_overstate_the_closest_related_work(self):
        # Environment Steering does compare three kinds of feedback; the report must say so
        flat = ' '.join(self.tex.split())
        self.assertIn('compares stopping, a generic retry and a constraint-aware retry', flat)
        self.assertNotIn('Neither varies the content of a refusal', flat)


if __name__ == '__main__':
    unittest.main()
