import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from scenario_v2_lib import validate_task


class ScenarioV2Test(unittest.TestCase):
    def setUp(self):
        path = ROOT / "data/scenarios_v2" / "test.jsonl"
        for line in path.read_text().splitlines():
            task = json.loads(line)
            if task["initial"]["presence"]:
                self.task = task
                return
        raise AssertionError("no present-branch test task")

    def test_zero_write_perturbation_branch_is_rejected(self):
        task = copy.deepcopy(self.task)
        task["goal_absent"] = {}
        errors, info = validate_task(task)
        self.assertTrue(info["off_branch_noop"])
        self.assertIn("off branch needs 0 writes (must be 1..3)", errors)

    def test_generated_corpus_requires_writes_on_both_branches(self):
        for split in ("dev", "pilot", "test"):
            path = ROOT / "data/scenarios_v2" / f"{split}.jsonl"
            for line in path.read_text().splitlines():
                task = json.loads(line)
                errors, _ = validate_task(task)
                self.assertEqual(errors, [], task["task_id"])
                self.assertGreaterEqual(task["annotations"]["writes_needed_present"], 1)
                self.assertGreaterEqual(task["annotations"]["writes_needed_absent"], 1)


if __name__ == "__main__":
    unittest.main()
