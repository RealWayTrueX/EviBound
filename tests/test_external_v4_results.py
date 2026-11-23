from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class V4ArtifactTests(unittest.TestCase):
    def test_frozen_inputs_still_match(self):
        freeze = json.loads(
            (ROOT / "artifacts" / "v4_prereg_freeze.json").read_text(encoding="utf-8")
        )
        changed = []
        for relative, expected in freeze["sha256"].items():
            path = ROOT / relative
            actual = (
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            )
            if actual != expected:
                changed.append(relative)
        self.assertEqual(changed, [])

    def test_core_acceptance_and_scenario_count(self):
        results = json.loads(
            (ROOT / "artifacts" / "v4_core_results.json").read_text(encoding="utf-8")
        )
        self.assertTrue(all(results["acceptance"].values()))
        self.assertEqual(results["structure_counts"], {"dev": 50, "holdout": 200})
        self.assertEqual(results["c1"]["c1_row_count"], 2400)
        self.assertEqual(results["c2"]["c2_row_count"], 7200)

    def test_simuhome_smoke_has_ten_successes(self):
        smoke = json.loads(
            (ROOT / "artifacts" / "v4_simuhome_smoke.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            smoke["simuhome_commit"], "83d28837b69f0cbf1bc02ed5334cb8b561a9d54d"
        )
        self.assertEqual(smoke["episodes_ok"], 10)
        self.assertEqual(smoke["episodes_error"], 0)

    def test_planner_preflight_does_not_fabricate_model_results(self):
        preflight = json.loads(
            (ROOT / "artifacts" / "v4_planner_preflight.json").read_text(encoding="utf-8")
        )
        self.assertIn("ready", preflight)
        self.assertEqual(len(preflight["planners"]), 2)
        self.assertNotIn("results", preflight)


if __name__ == "__main__":
    unittest.main()
