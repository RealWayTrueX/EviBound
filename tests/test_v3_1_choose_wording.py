"""The rule that picks the plan-review wording on development data."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import v3_1_choose_wording as cw  # noqa: E402


def entry(boundary, unrequested, clean):
    return {'boundary_full_completion': boundary, 'clean_part_unrequested': unrequested,
            'clean_full_completion': clean, 'score': boundary - unrequested}


class ChooseWording(unittest.TestCase):
    def test_default_is_kept_inside_the_margin(self):
        pooled = {'M_recover': entry(95, 5, 90), 'M_plan': entry(90, 10, 90),
                  'M_plan_open': entry(93, 10, 90), 'M_plan_text': entry(92, 9, 90)}
        self.assertEqual(cw.choose(pooled)['chosen'], 'M_plan')

    def test_another_wording_wins_with_a_clear_lead(self):
        pooled = {'M_recover': entry(95, 5, 90), 'M_plan': entry(80, 10, 90),
                  'M_plan_open': entry(90, 10, 90), 'M_plan_text': entry(84, 10, 90)}
        self.assertEqual(cw.choose(pooled)['chosen'], 'M_plan_open')

    def test_a_wording_that_costs_clean_completion_is_not_eligible(self):
        pooled = {'M_recover': entry(95, 5, 90), 'M_plan': entry(80, 10, 90),
                  'M_plan_open': entry(99, 0, 84.9), 'M_plan_text': entry(82, 10, 85)}
        decision = cw.choose(pooled)
        self.assertEqual(decision['eligible'], ['M_plan', 'M_plan_text'])
        self.assertEqual(decision['chosen'], 'M_plan')

    def test_default_not_eligible(self):
        pooled = {'M_recover': entry(95, 5, 90), 'M_plan': entry(99, 0, 80),
                  'M_plan_open': entry(70, 10, 90), 'M_plan_text': entry(72, 10, 90)}
        self.assertEqual(cw.choose(pooled)['chosen'], 'M_plan_text')

    def test_nothing_eligible(self):
        pooled = {'M_recover': entry(95, 5, 90), 'M_plan': entry(99, 0, 80),
                  'M_plan_open': entry(70, 10, 80), 'M_plan_text': entry(72, 10, 80)}
        self.assertIsNone(cw.choose(pooled)['chosen'])


if __name__ == '__main__':
    unittest.main()
