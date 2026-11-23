from __future__ import annotations

from dataclasses import replace
import math
import unittest

from evibound.external_v4.experiments import _c2_case, _c1_case, run_counterfactual
from evibound.external_v4.guards import GuardContext, decide
from evibound.external_v4.lifetime import LifetimePolicy, assign, lifetime, overshoot_bound
from evibound.external_v4.model import (
    Condition,
    Fact,
    FactKind,
    Proposal,
    SignedObservation,
    Truth,
    all_of,
)
from evibound.external_v4.planner import parse_plan
from evibound.external_v4.signing import ObservationSigner
from evibound.external_v4.simuhome_adapter import command_for_assert
from evibound.external_v4.sources import ScriptedSource
from evibound.external_v4.store import RecordStore
from evibound.external_v4.synthetic import generate_structures, run_guard


class LifetimeTests(unittest.TestCase):
    def test_formula_caps_then_subtracts_clock_error(self):
        signer = ObservationSigner(b"lifetime-test-key-material")
        fact = Fact("temperature", FactKind.CONTINUOUS, max_rate=0.1)
        condition = Condition("temperature", "gt", 40.0)
        record = signer.signed(
            record_id="r1",
            fact="temperature",
            value=43.0,
            observed_at=0.0,
            sequence=1,
        )
        policy = LifetimePolicy(kappa=1.5, tau_max=15.0, epsilon=0.5)
        self.assertAlmostEqual(lifetime(fact, record, condition, policy), 14.5)

    def test_current_false_observation_is_false(self):
        signer = ObservationSigner(b"lifetime-test-key-material")
        fact = Fact("temperature", FactKind.CONTINUOUS, max_rate=0.1)
        condition = Condition("temperature", "gt", 40.0)
        record = signer.signed(
            record_id="r1",
            fact="temperature",
            value=39.0,
            observed_at=10.0,
            sequence=1,
        )
        value, _ = assign(
            fact=fact,
            observation=record,
            condition=condition,
            now=10.0,
            policy=LifetimePolicy(),
        )
        self.assertIs(value, Truth.FALSE)

    def test_overshoot_bound_matches_formula(self):
        self.assertAlmostEqual(overshoot_bound(2.0, 1.0, 0.1, 30.0, 0.5), 3.05)
        self.assertEqual(overshoot_bound(0.5, 1.0, 0.1, 30.0, 0.5), 0.0)


class SigningAndStoreTests(unittest.TestCase):
    def setUp(self):
        self.signer = ObservationSigner(b"record-store-test-key-material")
        self.store = RecordStore(self.signer)
        self.record = self.signer.signed(
            record_id="r1",
            fact="humidity",
            value=60.0,
            observed_at=1.0,
            sequence=1,
        )

    def test_accepts_and_indexes_authentic_record(self):
        result = self.store.ingest(self.record, now=2.0)
        self.assertTrue(result.accepted)
        self.assertEqual(self.store.latest("humidity"), self.record)

    def test_rejects_replay_and_forgery(self):
        self.assertTrue(self.store.ingest(self.record, now=2.0).accepted)
        replay = self.store.ingest(self.record, now=3.0)
        self.assertEqual(replay.reason, "stale_sequence")
        forged = self.signer.forge(self.record, value=10.0)
        self.assertEqual(
            RecordStore(self.signer).ingest(forged, now=2.0).reason,
            "invalid_signature",
        )

    def test_rejects_future_clock_and_wrong_epoch(self):
        future = self.signer.signed(
            record_id="r2",
            fact="humidity",
            value=61.0,
            observed_at=10.0,
            sequence=2,
        )
        self.assertEqual(
            RecordStore(self.signer).ingest(future, now=9.0).reason,
            "future_dated",
        )
        wrong_epoch = self.signer.signed(
            record_id="r3",
            fact="humidity",
            value=61.0,
            observed_at=1.0,
            sequence=2,
            epoch=2,
        )
        self.assertEqual(
            RecordStore(self.signer).ingest(wrong_epoch, now=2.0).reason,
            "wrong_epoch",
        )


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.structure = generate_structures()[0]

    def test_context_replay_cannot_turn_stale_evidence_into_execute(self):
        case = replace(
            self.structure,
            scenario_id="context-replay-test",
            attack="context_replay",
            execution_values=self.structure.failure_values,
        )
        vulnerable = run_guard(case, "PEEK", policy=LifetimePolicy())
        guarded = run_guard(case, "SL", policy=LifetimePolicy())
        self.assertTrue(vulnerable["safety_violation"])
        self.assertFalse(guarded["safety_violation"])
        self.assertEqual(guarded["reads"], 1)

    def test_transport_freeze_is_fail_safe_not_a_false_block(self):
        case = replace(
            self.structure,
            scenario_id="freeze-test",
            attack="transport_freeze",
            execution_values=self.structure.failure_values,
        )
        result = run_guard(case, "SL", policy=LifetimePolicy())
        self.assertTrue(result["fail_safe"])
        self.assertFalse(result["false_block"])
        self.assertEqual(result["reason_code"], "stale_evidence")

    def test_clean_and_benign_paths_execute(self):
        for attack in ("clean", "benign_drift"):
            with self.subTest(attack=attack):
                case = replace(self.structure, attack=attack, scenario_id=f"test-{attack}")
                result = run_guard(case, "SL", policy=LifetimePolicy())
                self.assertTrue(result["executed"])
                self.assertFalse(result["false_block"])

    def test_all_guard_rows_are_deterministic(self):
        structures = generate_structures()[:2]
        first = run_counterfactual(structures)
        second = run_counterfactual(structures)
        self.assertEqual(first, second)


class PressureTestMathTests(unittest.TestCase):
    def test_c1_respects_overshoot_bound(self):
        row = _c1_case(
            case_id="bound",
            rho=2.0,
            kappa=1.0,
            rbar=0.1,
            margin=10.0,
            tau_max=60.0,
            epsilon=0.5,
        )
        self.assertTrue(row["bound_holds"])

    def test_short_circuit_read_order_holds(self):
        row = _c2_case(
            case_id="order",
            shape="all_of",
            size=4,
            stale_fraction=0.5,
        )
        self.assertTrue(row["ordering_holds"])
        self.assertLessEqual(row["reads"]["SL"], row["reads"]["MS"])
        self.assertLessEqual(row["reads"]["MS"], row["reads"]["AR"])


class AdapterAndPlannerTests(unittest.TestCase):
    def test_simuhome_goal_maps_to_public_command(self):
        command = command_for_assert(
            "living_room_dimmable_light_1", "1.OnOff.OnOff", True
        )
        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual(command.command_id, "On")
        self.assertEqual(command.step()["args"]["device_id"], command.device_id)

    def test_planner_json_fence_is_accepted(self):
        plan = parse_plan(
            """```json
{"actions":[{"device":"light","command":"on","arguments":{}}],
 "cites":["r1"],
 "requires":{"all_of":[{"fact":"washer","operator":"eq","value":"done"}]}}
```"""
        )
        self.assertEqual(plan["cites"], ["r1"])

    def test_planner_missing_requires_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_plan('{"actions":[],"cites":[]}')


if __name__ == "__main__":
    unittest.main()
