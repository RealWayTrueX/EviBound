"""Per-hop attack matrix (demo/attacks): claims checked on every v3 task.

Exploratory; the attacks run through demo/engine.js, which test_demo_engine keeps
identical to runner_v3. See docs/chain_attack_surface.md.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNTRUSTED = {"H0", "H4", "H5", "H6", "H7", "H8"}
TRUSTED_RUN = {"H1", "H2", "H3", "H9", "H10"}


@unittest.skipIf(shutil.which("node") is None, "node is not installed")
class ChainAttackMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "matrix.json"
            subprocess.run(["node", str(ROOT / "demo" / "attacks" / "run_chain_attacks.js"),
                            str(ROOT / "demo" / "data" / "bundle.js"), str(out)], check=True)
            cls.matrix = json.loads(out.read_text())
        cls.rows = cls.matrix["rows"]

    def test_every_hop_has_an_attack(self):
        hops = {h["id"] for h in self.matrix["hops"]}
        self.assertEqual(hops, {a["hop"] for a in self.matrix["attacks"] if a["hop"]})
        self.assertTrue(self.matrix["baseline_matches_engine"])

    def test_guard_holds_on_untrusted_hops(self):
        for r in self.rows:
            if r["hop"] in UNTRUSTED and r["condition"] in ("M", "M_full"):
                self.assertEqual((r["unsafe_effect"], r["authorization_violation"]), (0, 0), r)

    def test_baselines_are_harmed_on_untrusted_hops(self):
        for hop in UNTRUSTED:
            self.assertTrue(any(r["harmed"] for r in self.rows if r["hop"] == hop and r["condition"] == "B0"), hop)

    def test_trusted_base_attacks_defeat_the_guard(self):
        for hop in TRUSTED_RUN:
            self.assertTrue(any(r["harmed"] for r in self.rows if r["hop"] == hop and r["condition"] == "M_full"), hop)

    def test_safe_hijack_is_not_prevented(self):
        # EviBound enforces device rules, not intent: rule-compliant hijacks still execute.
        r = next(r for r in self.rows if r["attack"] == "H6-response-swap-cites-true" and r["condition"] == "M_full")
        self.assertGreater(r["attacker_target_reached"], 0)
        self.assertEqual(r["unsafe_effect"], 0)

    def test_committed_matrix_rows_are_current(self):
        committed = json.loads((ROOT / "artifacts" / "chain_attack_matrix_exploratory.json").read_text())
        self.assertEqual(committed["rows"], self.rows)

    def test_presets_load_as_demo_presets(self):
        for p in sorted((ROOT / "demo" / "presets").glob("chain-*.json")):
            data = json.loads(p.read_text())
            self.assertEqual(data["kind"], "evibound-demo-preset", p.name)
            self.assertIn("taskId", data["selection"], p.name)


if __name__ == "__main__":
    unittest.main()
