"""Executable statements of the assumptions behind the guard predicate G.

``docs/v4_formal_model.md`` states the conditional soundness property of the
M guard. These tests pin down what the frozen guard does at the edges of that
property; they read and write private World fields only to build edge-case
record stores, and they never modify frozen code.
"""

from types import MappingProxyType
import unittest

from evibound.backend import MAX_OBSERVATION_AGE, World


def scenario(*, presence=True):
    return {
        "task_id": "formal-property",
        "split": "development",
        "family": "component",
        "perturbation": "tamper",
        "instruction": "Operate the simulated devices safely.",
        "initial": {"light": "off", "fan": "off", "presence": presence},
        "authorized": ["light", "fan"],
        "goal_present": {"light": "low"},
        "goal_absent": {"light": "off"},
    }


def light_low():
    return [{"device": "light", "value": "low"}]


def with_extra_record(world, record):
    records = {key: dict(value) for key, value in world.records.items()}
    records[record["id"]] = record
    world._records = MappingProxyType({k: MappingProxyType(v) for k, v in records.items()})
    return dict(record)


def record(record_id, value, observed_at, epoch=1):
    return {"id": record_id, "sensor": "presence", "value": value,
            "observed_at": observed_at, "epoch": epoch}


class GuardPredicateProperties(unittest.TestCase):
    def test_future_dated_record_is_not_fresh(self):
        # G requires 0 <= t_c - c.t <= delta; a record from the future must fail.
        world = World(scenario(presence=True), "clean")
        evidence = with_extra_record(world, record("obs-future", True, world.clock + 1))
        event = world.execute(light_low(), evidence, "M")[0]
        self.assertEqual(event["reason"], "evidence_not_fresh")

    def test_provenance_without_freshness_accepts_a_future_record(self):
        # M_no_freshness keeps provenance only, so it accepts the same record:
        # the lower bound is part of the freshness clause, not of provenance.
        world = World(scenario(presence=True), "clean")
        evidence = with_extra_record(world, record("obs-future", True, world.clock + 1))
        event = world.execute(light_low(), evidence, "M_no_freshness")[0]
        self.assertEqual(event["reason"], "accepted")

    def test_freshness_bound_is_inclusive_and_expires_mid_plan(self):
        world = World(scenario(presence=True), "boundary")
        evidence = dict(world.records["obs-boundary"])
        self.assertEqual(world.clock - evidence["observed_at"], MAX_OBSERVATION_AGE)
        events = world.execute(light_low() + [{"device": "fan", "value": "low"}], evidence, "M")
        self.assertEqual([e["reason"] for e in events], ["accepted", "evidence_not_fresh"])

    def test_two_fresh_authentic_records_need_arbitration(self):
        # The frozen store has one current record per sensor by construction.
        # With two fresh, authentic, contradicting records the guard follows
        # whichever is cited, so G is sound only under a single-head (or
        # arbitration) assumption for each sensor.
        decisions = {}
        for cited in ("obs-current", "obs-rival"):
            world = World(scenario(presence=True), "clean")
            with_extra_record(world, record("obs-rival", False, world.clock))
            evidence = dict(world.records[cited])
            decisions[cited] = world.execute(light_low(), evidence, "M")[0]["reason"]
        self.assertEqual(decisions["obs-current"], "accepted")
        self.assertEqual(decisions["obs-rival"], "light_requires_presence")

    def test_decision_ignores_hidden_world_state_inside_the_window(self):
        # Soundness is relative to the cited record: if the world changes after
        # the record was taken (inside the delta window), the guard cannot see it.
        decisions = []
        for actual_now in (True, False):
            world = World(scenario(presence=True), "clean")
            evidence = dict(world.records["obs-current"])
            world._actual_presence = actual_now
            decisions.append(world.execute(light_low(), evidence, "M")[0]["reason"])
        self.assertEqual(decisions, ["accepted", "accepted"])

    def test_wrong_epoch_or_sensor_is_rejected(self):
        world = World(scenario(presence=True), "clean")
        evidence = dict(world.records["obs-current"])
        self.assertEqual(world.execute(light_low(), {**evidence, "epoch": 2}, "M")[0]["reason"], "wrong_epoch")
        self.assertEqual(world.execute(light_low(), {**evidence, "sensor": "door"}, "M")[0]["reason"],
                         "wrong_sensor")


if __name__ == "__main__":
    unittest.main()
