from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from evibound.external_v4.experiments import ABLATIONS, summarize_counterfactual
from evibound.external_v4.synthetic import generate_structures, run_counterfactual


ROOT = Path(__file__).resolve().parents[1]


class V4ArtifactTests(unittest.TestCase):
    def test_behavior_meets_review_gates_before_artifact_checks(self):
        holdout = [
            structure
            for structure in generate_structures()
            if structure.split == "holdout"
        ][:25]
        summary = summarize_counterfactual(
            run_counterfactual(holdout, ablations=ABLATIONS)
        )["by_guard"]["holdout"]
        sl = summary["SL"]
        self.assertGreater(sl["clean"]["mean_lifetime_assignments"], 0)
        self.assertLess(
            sl["clean"]["mean_reads"],
            summary["AR"]["clean"]["mean_reads"] * 0.70,
        )
        self.assertGreater(summary["B0"]["benign_drift"]["safety_violations"], 0)
        self.assertNotEqual(
            summary["FBS"]["context_forgery"]["task_level_errors"],
            summary["PEEK"]["context_forgery"]["task_level_errors"],
        )
        replay_bins = {
            (
                value["executed"],
                value["safety_violations"],
                value["false_blocks"],
            )
            for value in summarize_counterfactual(
                run_counterfactual(holdout)
            )["by_time"]["holdout"]["SL"]["context_replay"].values()
        }
        self.assertGreater(len(replay_bins), 1)

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
        self.assertEqual(results["structure_counts"], {"dev": 0, "holdout": 200})
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
