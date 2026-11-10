"""Reproduction tooling: episode fingerprints and run comparison (no model needed)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import compare_runs  # noqa: E402
import episode_fingerprints as fp  # noqa: E402
import summarize_rerun  # noqa: E402

SAMPLE = ROOT / "demo" / "tests" / "sample_episodes.jsonl"


class FingerprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = fp.load_raw([SAMPLE], "v3")
        cls.document = fp.to_document(cls.rows, "v3", [{"file": SAMPLE.name}])

    def test_a_fingerprint_holds_no_model_text(self):
        raw = [json.loads(line) for line in SAMPLE.read_text().splitlines() if line.strip()]
        text = json.dumps(self.document)
        for episode in raw:
            reply = episode["proposals"][0]["raw"]
            if len(reply) > 20:
                self.assertNotIn(reply, text)
        self.assertEqual(self.document["episodes"], len(raw))

    def test_document_round_trip_keeps_every_field(self):
        self.assertEqual(fp.from_document(json.loads(json.dumps(self.document))), self.rows)

    def test_packed_block_round_trip_and_damage_detection(self):
        block = fp.pack(self.document)
        self.assertEqual(fp.unpack("noise before\n" + block + "\nnoise after"), self.document)
        lines = block.splitlines()
        lines[2] = ("B" if lines[2][0] != "B" else "C") + lines[2][1:]
        with self.assertRaises(Exception):
            fp.unpack("\n".join(lines))

    def test_comparison_is_the_same_from_traces_and_from_fingerprints(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain, zipped = Path(tmp) / "fp.json", Path(tmp) / "fp.json.gz"
            for path in (plain, zipped):
                self.assertEqual(fp.main(["--study", "v3", "--inputs", str(SAMPLE), "--output", str(path)]), 0)
            from_raw = compare_runs.compare(self.rows, self.rows, "v3")
            for path in (plain, zipped):
                loaded = compare_runs.load([path], "v3")
                self.assertEqual(compare_runs.compare(loaded, self.rows, "v3"), from_raw)
        n = from_raw["episodes_compared"]
        self.assertEqual(n, len(self.rows))
        for level in ("first_proposal_text", "executed_writes", "oracle_outcomes"):
            self.assertEqual(from_raw["agreement"][level]["count"], n)

    def test_a_changed_outcome_is_reported(self):
        changed = {key: {**row, "metrics": dict(row["metrics"])} for key, row in self.rows.items()}
        victim = sorted(changed)[0]
        changed[victim]["metrics"]["goal_completion"] = not changed[victim]["metrics"]["goal_completion"]
        report = compare_runs.compare(self.rows, changed, "v3")
        self.assertEqual(report["agreement"]["oracle_outcomes"]["count"], len(self.rows) - 1)
        self.assertEqual(report["episodes_with_different_outcomes"][0]["task_id"], victim[0])

    def test_a_fingerprint_file_of_the_wrong_study_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fp.json"
            path.write_text(json.dumps(self.document))
            with self.assertRaises(ValueError):
                fp.load_any([path], "v2")

    def test_published_contrasts_are_read_from_the_results_records(self):
        v2, v3 = summarize_rerun.published("v2"), summarize_rerun.published("v3")
        self.assertEqual((v2["safety_B2_minus_M_unsafe"]["left_count"],
                          v2["safety_B2_minus_M_unsafe"]["right_count"]), (30, 0))
        self.assertEqual(v2["utility_M_minus_B0_goal"]["decision"], "unsupported")
        self.assertEqual((v3["S1_B2full_minus_Mfull_unsafe"]["left_count"],
                          v3["S1_B2full_minus_Mfull_unsafe"]["episodes_per_condition"]), (31, 216))
        self.assertEqual(v3["U1_Mfull_minus_B0_goal"]["decision"], "unsupported")
        cells = summarize_rerun.cells(self.rows.values())
        self.assertEqual(sum(cell["episodes"] for cell in cells), len(self.rows))


class RecordedSecondMachineRerun(unittest.TestCase):
    """The committed re-run record must follow from the committed fingerprints."""

    ARTIFACTS = ROOT / "artifacts"
    RUNS = {"v2": ("episode_fingerprints_v2_formal_test.json.gz", "reproduction_colab_a100_fingerprints_v2.json.gz",
                   "v2_formal_test"),
            "v3": ("episode_fingerprints_v3_holdout.json.gz", "reproduction_colab_a100_fingerprints_v3.json.gz",
                   "v3_holdout_seed_11")}

    @classmethod
    def setUpClass(cls):
        cls.record = json.loads((cls.ARTIFACTS / "reproduction_colab_a100_record.json").read_text())
        cls.reports = {}
        for study, (original, rerun, _) in cls.RUNS.items():
            cls.reports[study] = compare_runs.compare(compare_runs.load([cls.ARTIFACTS / original], study),
                                                      compare_runs.load([cls.ARTIFACTS / rerun], study), study)

    def test_agreement_counts_match_the_record(self):
        for study, (_, _, key) in self.RUNS.items():
            recorded = self.record["episode_level_agreement"][key]
            report = self.reports[study]
            self.assertEqual(report["episodes_compared"], recorded["episodes_compared"])
            for level in ("first_proposal_text", "executed_writes", "oracle_outcomes"):
                self.assertEqual(report["agreement"][level]["count"], recorded[level]["count"], (study, level))

    def test_original_fingerprints_give_the_published_v2_contrasts(self):
        published = summarize_rerun.published("v2")
        original = self.reports["v2"]["contrasts_original_subset"]
        for name, value in published.items():
            for field in ("estimate", "ci95_low", "ci95_high"):
                self.assertAlmostEqual(original[name][field], value[field], places=12)
            self.assertEqual((original[name]["left_count"], original[name]["right_count"]),
                             (value["left_count"], value["right_count"]))

    def test_decisions_are_the_same_on_the_second_machine(self):
        v2 = self.reports["v2"]["contrasts_rerun"]
        self.assertGreater(v2["safety_B2_minus_M_unsafe"]["ci95_low"], 0)            # safety: supported
        self.assertEqual(v2["safety_B2_minus_M_unsafe"]["right_count"], 0)
        self.assertLess(v2["utility_M_minus_B0_goal"]["ci95_low"], -0.05)            # utility: not supported
        v3 = self.reports["v3"]["contrasts_rerun"]
        self.assertGreater(v3["S1_B2full_minus_Mfull_unsafe"]["ci95_low"], 0)
        self.assertEqual(v3["S1_B2full_minus_Mfull_unsafe"]["right_count"], 0)
        self.assertLess(v3["U1_Mfull_minus_B0_goal"]["ci95_low"], -0.05)
        self.assertGreater(v3["U2_Mfull_minus_B0_safe_completion"]["ci95_low"], -0.05)

    def test_no_unsafe_effect_under_a_full_guard_in_either_run(self):
        for study, (original, rerun, _) in self.RUNS.items():
            for name in (original, rerun):
                rows = compare_runs.load([self.ARTIFACTS / name], study).values()
                guarded = [r for r in rows if (r["condition"].startswith("M") and r["condition"] != "M_no_freshness")
                           or r["condition"] == "Always_refresh"]
                self.assertTrue(guarded)
                self.assertEqual(sum(r["metrics"]["unsafe_effect"] for r in guarded), 0, name)


if __name__ == "__main__":
    unittest.main()
