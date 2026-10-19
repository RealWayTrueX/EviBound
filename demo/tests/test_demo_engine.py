"""Cross-check the demo's JavaScript engine against the real Python v3 runner.

Node runs every v3 task x variant x condition through demo/engine.js with the
three scripted planners and a set of adversarial personas (malformed JSON,
prototype-named levels, extra keys, wrong ids, float/bool-typed numbers) and
records each planner reply. The same replies are then fed to
``runner_v3.run_seed`` as its "model", keyed by the exact prompt text the
Python side builds. Any difference in prompts, recovery messages, guard events
or oracle metrics fails the test. The bundle is built into a temporary file so
the test never touches demo/data/bundle.js.

    PYTHONPATH=src:. python3 -m unittest demo.tests.test_demo_engine -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from evibound.recovery import V3_CONDITIONS  # noqa: E402
from evibound.runner_v3 import run_seed  # noqa: E402

METRICS = ("unsafe_effect", "authorization_violation", "goal_completion", "safe_completion",
           "safe_utility_completion", "executed_writes", "rejected_proposals", "false_blocks",
           "false_block_eligible_proposals", "reads", "authorized_subgoal_completion")
VARIANTS = ["clean", "perturbed", "boundary"]


def _scenarios():
    out = []
    for split in ("dev", "holdout"):
        path = ROOT / "data" / "scenarios_v3" / f"{split}.jsonl"
        out += [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return out


@unittest.skipIf(shutil.which("node") is None, "node is not installed")
class DemoEngineMatchesPython(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        bundle = Path(cls.tmp.name) / "bundle.js"
        subprocess.run([sys.executable, str(ROOT / "demo" / "build_demo_data.py"), "--output", str(bundle)],
                       check=True, capture_output=True)
        out = subprocess.run(["node", str(ROOT / "demo" / "tests" / "crosscheck_dump.js"), str(bundle)],
                             check=True, capture_output=True, text=True).stdout
        cls.js = [json.loads(line) for line in out.splitlines()]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_committed_bundle_matches_repository(self):
        """demo/data/bundle.js must be a current export (same content digest)."""
        committed = (ROOT / "demo" / "data" / "bundle.js").read_text()
        committed_json = json.loads(committed.split("=", 1)[1].strip().rstrip(";"))
        fresh = json.loads((Path(self.tmp.name) / "bundle.js").read_text().split("=", 1)[1].strip().rstrip(";"))
        self.assertEqual(committed_json["content_sha256"], fresh["content_sha256"],
                         "run python3 demo/build_demo_data.py and commit demo/data/bundle.js")

    def test_every_episode_matches(self):
        scenarios = _scenarios()
        by_persona = defaultdict(list)
        for row in self.js:
            by_persona[row["persona"]].append(row)
        personas = {row["persona"] for row in self.js}
        self.assertGreaterEqual(len(personas), 3)
        self.assertEqual(len(self.js), len(personas) * len(scenarios) * len(VARIANTS) * len(V3_CONDITIONS))
        checked = 0
        for persona, rows in by_persona.items():
            first_reply, retry_reply = {}, {}
            for row in rows:
                first_reply[row["first_user"]] = row["raws"][0]
                if row["retry_user"] is not None:
                    retry_reply[(row["first_user"], row["retry_user"])] = row["raws"][1]
            missing = []

            def generate(batches, seed):
                replies = []
                for messages in batches:
                    first = messages[1]["content"]
                    if len(messages) == 2:
                        raw = first_reply.get(first)
                    else:
                        raw = retry_reply.get((first, messages[-1]["content"]))
                    if raw is None:
                        missing.append(messages[-1]["content"][:300])
                        raw = "{}"
                    replies.append({"raw": raw, "parsed": None, "parse_error": None,
                                    "input_tokens": 0, "output_tokens": 0, "latency_s": 0.0})
                from evibound.planner import parse_response
                for reply in replies:
                    reply["parsed"], reply["parse_error"] = parse_response(reply["raw"])
                return replies

            js_index = {(r["task_id"], r["variant"], r["condition"]): r for r in rows}
            for episode in run_seed(generate, scenarios, list(V3_CONDITIONS), VARIANTS, 11, 64):
                key = (episode["task_id"], episode["variant"], episode["condition"])
                js = js_index[key]
                label = f"{persona} {key}"
                self.assertEqual(episode["recovery_trigger"], js["trigger"], label)
                events = [[e["kind"], e["device"], e["value"], e["reason"], e["before"], e["after"]]
                          for e in episode["trace"]["events"]]
                self.assertEqual(json.loads(json.dumps(events)), js["events"], label)
                for metric in METRICS:
                    self.assertEqual(episode["metrics"][metric], js["metrics"][metric], f"{label} {metric}")
                checked += 1
            self.assertEqual(missing, [], f"{persona}: Python built prompts the JS side never produced")
        self.assertEqual(checked, len(self.js))


if __name__ == "__main__":
    unittest.main()
