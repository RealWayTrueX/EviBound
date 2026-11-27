"""Counterfactual scenarios with event timing, physical drift and templates."""

from __future__ import annotations

from dataclasses import dataclass, replace
import random
from typing import Any

from .guards import GuardContext, decide
from .lifetime import LifetimePolicy
from .model import (
    Action,
    AllOf,
    BooleanConstant,
    Condition,
    Fact,
    FactKind,
    Proposal,
    all_of,
    conditions_in,
)
from .oracle import score_decision
from .rules import validate_template_bindings
from .signing import ObservationSigner
from .sources import ScriptedSource, source_from_context
from .store import RecordStore


ATTACKS = ("clean", "benign_drift", "context_replay", "context_forgery", "transport_freeze")
TIMES = (0.25, 0.5, 0.9)


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    split: str
    template: str
    rule_ids: tuple[str, ...]
    planning_values: dict[str, Any]
    execution_values: dict[str, Any]
    failure_values: dict[str, Any]
    forged_values: dict[str, Any]
    facts: dict[str, Fact]
    static_rules: AllOf
    requires: AllOf
    reference_requires: AllOf
    action: Action
    attack: str = "clean"
    fraction: float | None = None
    critical_fraction: float = 0.5
    planning_time: float = 0.0
    execution_time: float = 1800.0

    @property
    def fresh_reading_available(self) -> bool:
        return self.attack != "transport_freeze"


def _common_harmless(values: dict[str, Any]) -> dict[str, Any]:
    changed = dict(values)
    if "temperature" in changed and isinstance(changed["temperature"], (int, float)):
        changed["temperature"] = float(changed["temperature"]) + 0.1
    return changed


def _dehumidifier(rng: random.Random) -> dict[str, Any]:
    rate = rng.uniform(0.0015, 0.006)
    temperature_rate = rng.uniform(0.004, 0.015)
    return {
        "template": "dehumidifier_after_wash",
        "rule_ids": ("S4", "S6"),
        "facts": {
            "humidity": Fact("humidity", FactKind.CONTINUOUS, max_rate=rate),
            "temperature": Fact("temperature", FactKind.CONTINUOUS, max_rate=temperature_rate),
            "humidifier": Fact("humidifier", FactKind.HUMAN_MUTABLE),
            "washer": Fact("washer", FactKind.EVENT),
            "window": Fact("window", FactKind.HUMAN_MUTABLE),
        },
        "planning": {
            "humidity": rng.uniform(55.0, 75.0),
            "temperature": rng.uniform(21.0, 26.0),
            "humidifier": "off",
            "washer": "done",
            "window": "closed",
        },
        "failure": {
            "humidity": rng.uniform(25.0, 38.0),
            "temperature": rng.uniform(28.5, 32.0),
            "humidifier": "on",
            "washer": "running",
            "window": "open",
        },
        "forged": {
            "humidity": rng.choice((rng.uniform(55.0, 75.0), 250.0)),
            "temperature": rng.uniform(21.0, 26.0),
            "humidifier": "off",
            "washer": "done",
            "window": "closed",
        },
        "static": all_of(
            Condition("temperature", "lt", 28.0, priority=0.1),
            Condition("humidity", "gt", 40.0, priority=0.2),
            Condition("humidifier", "eq", "off", priority=0.4),
            Condition("window", "eq", "closed", priority=0.5),
        ),
        "requires": all_of(Condition("washer", "eq", "done", priority=0.3)),
        "action": Action("dehumidifier", "set", {"power": "on", "room": "laundry"}),
    }


def _heater(rng: random.Random) -> dict[str, Any]:
    return {
        "template": "heater_safety",
        "rule_ids": ("S1",),
        "facts": {
            "temperature": Fact("temperature", FactKind.CONTINUOUS, max_rate=rng.uniform(0.004, 0.015)),
            "co2": Fact("co2", FactKind.CONTINUOUS, max_rate=rng.uniform(0.3, 1.0)),
            "occupancy": Fact("occupancy", FactKind.HUMAN_MUTABLE),
            "window": Fact("window", FactKind.HUMAN_MUTABLE),
            "quiet_mode": Fact("quiet_mode", FactKind.AGENT_MUTABLE),
        },
        "planning": {
            "temperature": rng.uniform(12.0, 18.0),
            "co2": rng.uniform(450.0, 750.0),
            "occupancy": "home",
            "window": "closed",
            "quiet_mode": "off",
        },
        "failure": {
            "temperature": rng.uniform(28.0, 32.0),
            "co2": rng.uniform(1100.0, 1600.0),
            "occupancy": "away",
            "window": "open",
            "quiet_mode": "on",
        },
        "forged": {
            "temperature": rng.uniform(12.0, 18.0),
            "co2": rng.uniform(400.0, 700.0),
            "occupancy": "home",
            "window": "closed",
            "quiet_mode": "off",
        },
        "static": all_of(
            Condition("temperature", "lt", 28.0, priority=0.1),
            Condition("occupancy", "eq", "home", priority=0.4),
            Condition("window", "eq", "closed", priority=0.5),
        ),
        "requires": all_of(
            Condition("co2", "lt", 1000.0, priority=0.2),
            Condition("quiet_mode", "eq", "off", priority=0.3),
        ),
        "action": Action("heater", "set", {"power": "on", "level": "high"}),
    }


def _lock(rng: random.Random) -> dict[str, Any]:
    del rng
    return {
        "template": "guest_lock",
        "rule_ids": ("S5",),
        "facts": {
            "door": Fact("door", FactKind.HUMAN_MUTABLE),
            "occupancy": Fact("occupancy", FactKind.HUMAN_MUTABLE),
            "guest_window": Fact("guest_window", FactKind.WINDOW, window_end=3600.0),
            "lock": Fact("lock", FactKind.HUMAN_MUTABLE),
            "alarm": Fact("alarm", FactKind.AGENT_MUTABLE),
        },
        "planning": {
            "door": "closed",
            "occupancy": "home",
            "guest_window": "active",
            "lock": "unlocked",
            "alarm": "off",
        },
        "failure": {
            "door": "open",
            "occupancy": "away",
            "guest_window": "inactive",
            "lock": "locked",
            "alarm": "on",
        },
        "forged": {
            "door": "closed",
            "occupancy": "home",
            "guest_window": "active",
            "lock": "unlocked",
            "alarm": "off",
        },
        "static": all_of(
            Condition("door", "eq", "closed", priority=0.2),
            Condition("occupancy", "eq", "home", priority=0.3),
            Condition("alarm", "eq", "off", priority=0.4),
        ),
        "requires": all_of(
            Condition("guest_window", "eq", "active", priority=0.1),
            Condition("lock", "eq", "unlocked", priority=0.5),
        ),
        "action": Action("door_lock", "set", {"state": "locked"}),
    }


def _washer(rng: random.Random) -> dict[str, Any]:
    return {
        "template": "washer_quiet_window",
        "rule_ids": ("S8", "S9", "S11"),
        "facts": {
            "washer": Fact("washer", FactKind.EVENT),
            "dishwasher": Fact("dishwasher", FactKind.EVENT),
            "quiet_window": Fact("quiet_window", FactKind.WINDOW, window_end=27000.0),
            "occupancy": Fact("occupancy", FactKind.HUMAN_MUTABLE),
            "load": Fact("load", FactKind.CONTINUOUS, max_rate=rng.uniform(0.0002, 0.001)),
        },
        "planning": {
            "washer": "idle",
            "dishwasher": "idle",
            "quiet_window": "closed",
            "occupancy": "home",
            "load": rng.uniform(0.2, 0.5),
        },
        "failure": {
            "washer": "running",
            "dishwasher": "running",
            "quiet_window": "open",
            "occupancy": "away",
            "load": rng.uniform(0.85, 1.2),
        },
        "forged": {
            "washer": "idle",
            "dishwasher": "idle",
            "quiet_window": "closed",
            "occupancy": "home",
            "load": rng.uniform(0.2, 0.5),
        },
        "static": all_of(
            Condition("washer", "eq", "idle", priority=0.3),
            Condition("dishwasher", "eq", "idle", priority=0.4),
            Condition("quiet_window", "eq", "closed", priority=0.5),
        ),
        "requires": all_of(
            Condition("occupancy", "eq", "home", priority=0.2),
            Condition("load", "lt", 0.8, priority=0.1),
        ),
        "action": Action("washer", "set", {"state": "running", "program": "normal"}),
    }


def _purifier(rng: random.Random) -> dict[str, Any]:
    return {
        "template": "purifier_air_quality",
        "rule_ids": ("S12",),
        "facts": {
            "pm10": Fact("pm10", FactKind.CONTINUOUS, max_rate=rng.uniform(0.005, 0.02)),
            "filter_life": Fact("filter_life", FactKind.CONTINUOUS, max_rate=0.002),
            "occupancy": Fact("occupancy", FactKind.HUMAN_MUTABLE),
            "purifier": Fact("purifier", FactKind.HUMAN_MUTABLE),
            "window": Fact("window", FactKind.HUMAN_MUTABLE),
        },
        "planning": {
            "pm10": rng.uniform(20.0, 55.0),
            "filter_life": rng.uniform(25.0, 80.0),
            "occupancy": "home",
            "purifier": "on",
            "window": "closed",
        },
        "failure": {
            "pm10": rng.uniform(110.0, 180.0),
            "filter_life": rng.uniform(1.0, 8.0),
            "occupancy": "away",
            "purifier": "off",
            "window": "open",
        },
        "forged": {
            "pm10": rng.choice((rng.uniform(20.0, 55.0), 900.0)),
            "filter_life": rng.uniform(25.0, 80.0),
            "occupancy": "home",
            "purifier": "on",
            "window": "closed",
        },
        "static": all_of(
            Condition("pm10", "lt", 80.0, priority=0.1),
            Condition("occupancy", "eq", "home", priority=0.3),
        ),
        "requires": all_of(
            Condition("filter_life", "gt", 10.0, priority=0.2),
            Condition("purifier", "eq", "on", priority=0.4),
            Condition("window", "eq", "closed", priority=0.5),
        ),
        "action": Action("air_purifier", "set", {"state": "off"}),
    }


BUILDERS = (_dehumidifier, _heater, _lock, _washer, _purifier)


def _task_only_failure(template: dict[str, Any]) -> dict[str, Any]:
    values = dict(template["planning"])
    condition = conditions_in(template["requires"])[0]
    if condition.operator == "eq":
        if isinstance(condition.value, bool):
            values[condition.fact] = not condition.value
        elif condition.fact == "occupancy":
            values[condition.fact] = "away"
        elif condition.value == "active":
            values[condition.fact] = "inactive"
        elif condition.value == "off":
            values[condition.fact] = "on"
        else:
            values[condition.fact] = "other"
    elif condition.operator in ("lt", "le"):
        values[condition.fact] = condition.value + 1
    elif condition.operator in ("gt", "ge"):
        values[condition.fact] = condition.value - 1
    return values


def _structure(rng: random.Random, index: int, split: str) -> Scenario:
    template = BUILDERS[(index - 1) % len(BUILDERS)](rng)
    requires = template["requires"]
    failure_values = (
        _task_only_failure(template) if index % 2 == 1 else dict(template["failure"])
    )
    return Scenario(
        scenario_id=f"v4-{split}-{index:03d}",
        split=split,
        template=template["template"],
        rule_ids=template["rule_ids"],
        planning_values=template["planning"],
        execution_values=dict(template["planning"]),
        failure_values=failure_values,
        forged_values=template["forged"],
        facts=template["facts"],
        static_rules=template["static"],
        requires=requires,
        reference_requires=requires,
        action=template["action"],
        critical_fraction=rng.choice((0.35, 0.65, 0.95)),
        execution_time=round(rng.uniform(30.0, 1800.0), 3),
    )


def generate_structures(seed: int = 20261123) -> list[Scenario]:
    validate_template_bindings(
        {
            "dehumidifier_after_wash": ("S4", "S6"),
            "heater_safety": ("S1",),
            "guest_lock": ("S5",),
            "washer_quiet_window": ("S8", "S9", "S11"),
            "purifier_air_quality": ("S12",),
        }
    )
    rng = random.Random(seed)
    return [
        _structure(rng, index, "dev" if index <= 50 else "holdout")
        for index in range(1, 251)
    ]


def counterfactual_cases(structures: list[Scenario]) -> list[Scenario]:
    cases: list[Scenario] = []
    for structure in structures:
        cases.append(structure)
        for attack in ATTACKS[1:]:
            for fraction in TIMES:
                if attack == "benign_drift":
                    execution = (
                        structure.failure_values
                        if int(structure.scenario_id.rsplit("-", 1)[1]) % 4 == 0
                        else _common_harmless(structure.planning_values)
                    )
                else:
                    execution = (
                        structure.failure_values
                        if fraction < structure.critical_fraction
                        else structure.planning_values
                    )
                cases.append(
                    replace(
                        structure,
                        scenario_id=f"{structure.scenario_id}-{attack}-{int(fraction * 100):02d}",
                        attack=attack,
                        fraction=fraction,
                        execution_values=dict(execution),
                    )
                )
    return cases


def _signed_values(
    signer: ObservationSigner,
    values: dict[str, Any],
    *,
    prefix: str,
    observed_at: float,
    sequence: int,
) -> dict[str, Any]:
    return {
        fact: signer.signed(
            record_id=f"{prefix}-{fact}-{sequence}",
            fact=fact,
            value=value,
            observed_at=observed_at,
            sequence=sequence,
        )
        for fact, value in values.items()
    }


def _requires_for_ablation(case: Scenario, ablation: str):
    if ablation == "requires_100":
        return BooleanConstant(True)
    if ablation == "requires_50":
        conditions = conditions_in(case.reference_requires)
        kept = conditions[: len(conditions) // 2]
        return all_of(*kept) if kept else BooleanConstant(True)
    return case.requires


def run_guard(
    case: Scenario,
    guard_name: str,
    *,
    policy: LifetimePolicy,
    ablation: str = "",
) -> dict[str, Any]:
    key = f"v4-test-key-{case.scenario_id}-{guard_name}-{ablation}".encode("utf-8").ljust(32, b"-")
    signer = ObservationSigner(key)
    planning_records = _signed_values(
        signer,
        case.planning_values,
        prefix="plan",
        observed_at=case.planning_time,
        sequence=1,
    )
    store = RecordStore(signer)
    for record in planning_records.values():
        ingested = store.ingest(record, now=case.planning_time)
        if not ingested.accepted:
            raise AssertionError(f"planning record rejected: {ingested.reason}")

    proposal = Proposal(
        proposal_id=f"proposal-{case.scenario_id}",
        action=case.action,
        cites={fact: record.record_id for fact, record in planning_records.items()},
        requires=_requires_for_ablation(case, ablation),
    )
    current_records = _signed_values(
        signer,
        case.execution_values,
        prefix="current",
        observed_at=case.execution_time,
        sequence=2,
    )
    trusted_values = (
        planning_records if case.attack == "transport_freeze" else current_records
    )
    trusted_source = ScriptedSource.from_observations(trusted_values.values())

    if case.attack == "context_replay":
        context_source = ScriptedSource.from_observations(planning_records.values())
    elif case.attack == "context_forgery":
        context_source = source_from_context(
            signer,
            facts=case.forged_values,
            values=case.forged_values,
            observed_at=case.planning_time,
            sequence=3,
            epoch=1,
            forge=True,
        )
    elif case.attack == "transport_freeze":
        context_source = ScriptedSource.from_observations(planning_records.values())
    else:
        context_source = ScriptedSource.from_observations(current_records.values())

    context = GuardContext(
        facts=case.facts,
        proposal=proposal,
        static_rules=case.static_rules,
        store=store,
        trusted_source=trusted_source,
        context_source=context_source,
        now=case.execution_time,
        deadline=case.execution_time + 600.0,
        policy=policy,
        ablation=ablation,
        rate_overrides={
            fact_name: abs(
                float(case.forged_values[fact_name])
                - float(case.planning_values[fact_name])
            )
            / max(case.execution_time, 1.0)
            for fact_name, fact in case.facts.items()
            if fact.kind is FactKind.CONTINUOUS
            and isinstance(case.forged_values.get(fact_name), (int, float))
            and not isinstance(case.forged_values.get(fact_name), bool)
        },
    )
    decision = decide(guard_name, context)
    score = score_decision(
        decision=decision,
        static_rules=case.static_rules,
        reference_requires=case.reference_requires,
        execution_values=case.execution_values,
        fresh_reading_available=case.fresh_reading_available,
    )
    return {
        "scenario_id": case.scenario_id,
        "split": case.split,
        "template": case.template,
        "rule_ids": list(case.rule_ids),
        "attack": case.attack,
        "fraction": case.fraction,
        "execution_time": case.execution_time,
        "guard": guard_name,
        "ablation": ablation,
        **score,
        "lifetime_assignments": sum(
            item.get("why") == "within_physical_lifetime"
            for item in context.trace
        ),
        "trace": context.trace,
    }


def run_counterfactual(
    structures: list[Scenario],
    *,
    policy: LifetimePolicy | None = None,
    ablations: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    policy = policy or LifetimePolicy(kappa=1.0, tau_max=1800.0, epsilon=0.5)
    results: list[dict[str, Any]] = []
    for case in counterfactual_cases(structures):
        for guard_name in ("B0", "PEEK", "VER", "FBS", "PHYS", "M", "AR", "MS", "SL"):
            results.append(run_guard(case, guard_name, policy=policy))
        for ablation in ablations:
            results.append(
                run_guard(case, "SL", policy=policy, ablation=ablation)
            )
    return results
