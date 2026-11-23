"""Counterfactual A-group scenarios and deterministic guard comparison."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

from .guards import GuardContext, decide
from .lifetime import LifetimePolicy
from .model import Action, AllOf, Condition, Fact, FactKind, Proposal, all_of
from .oracle import score_decision
from .signing import ObservationSigner
from .sources import ScriptedSource, source_from_context
from .store import RecordStore


ATTACKS = ("clean", "benign_drift", "context_replay", "context_forgery", "transport_freeze")
TIMES = (0.25, 0.5, 0.9)
KEYS = ("humidity", "humidifier", "washer", "temperature", "window", "lamp")


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    split: str
    planning_values: dict[str, Any]
    execution_values: dict[str, Any]
    failure_values: dict[str, Any]
    facts: dict[str, Fact]
    static_rules: AllOf
    requires: AllOf
    action: Action
    attack: str
    fraction: float | None = None
    planning_time: float = 0.0
    execution_time: float = 1800.0

    @property
    def fresh_reading_available(self) -> bool:
        return self.attack != "transport_freeze"


def _structure(rng: random.Random, index: int, split: str) -> Scenario:
    humidity = round(rng.uniform(52.0, 78.0), 2)
    temperature = round(rng.uniform(19.0, 26.0), 2)
    rate = rng.choice((0.01, 0.02, 0.03, 0.05))
    facts = {
        "humidity": Fact("humidity", FactKind.CONTINUOUS, max_rate=rate),
        "humidifier": Fact("humidifier", FactKind.HUMAN_MUTABLE),
        "washer": Fact("washer", FactKind.EVENT),
        "temperature": Fact("temperature", FactKind.CONTINUOUS, max_rate=0.08),
        "window": Fact("window", FactKind.HUMAN_MUTABLE),
        "lamp": Fact("lamp", FactKind.AGENT_MUTABLE),
    }
    static_rules = all_of(
        Condition("humidity", "gt", 40.0, priority=0.2),
        Condition("humidifier", "eq", "off", priority=0.4),
        Condition("window", "eq", "closed", priority=0.6),
    )
    requires = all_of(
        Condition("washer", "eq", "done", priority=0.1),
        Condition("temperature", "lt", 28.0, priority=0.5),
    )
    planning = {
        "humidity": humidity,
        "humidifier": "off",
        "washer": "done",
        "temperature": temperature,
        "window": "closed",
        "lamp": "off",
    }
    failure = {
        "humidity": 30.0 + rng.uniform(0.0, 6.0),
        "humidifier": "on",
        "washer": "running",
        "temperature": temperature + rng.uniform(0.2, 1.5),
        "window": "open",
        "lamp": "off",
    }
    return Scenario(
        scenario_id=f"v4-{split}-{index:03d}",
        split=split,
        planning_values=planning,
        execution_values=dict(planning),
        failure_values=failure,
        facts=facts,
        static_rules=static_rules,
        requires=requires,
        action=Action(
            "dehumidifier",
            "set",
            {"power": "on", "room": "laundry", "duration_minutes": 30},
        ),
        attack="clean",
    )


def generate_structures(seed: int = 20261123) -> list[Scenario]:
    rng = random.Random(seed)
    structures: list[Scenario] = []
    for index in range(1, 251):
        split = "dev" if index <= 50 else "holdout"
        structures.append(_structure(rng, index, split))
    return structures


def counterfactual_cases(structures: list[Scenario]) -> list[Scenario]:
    cases: list[Scenario] = []
    for structure in structures:
        cases.append(structure)
        for attack in ATTACKS[1:]:
            for fraction in TIMES:
                execution = dict(structure.failure_values)
                if attack == "benign_drift":
                    execution = dict(structure.planning_values)
                    execution["temperature"] = structure.planning_values["temperature"] + 0.1
                cases.append(
                    Scenario(
                        scenario_id=f"{structure.scenario_id}-{attack}-{int(fraction * 100):02d}",
                        split=structure.split,
                        planning_values=structure.planning_values,
                        execution_values=execution,
                        failure_values=structure.failure_values,
                        facts=structure.facts,
                        static_rules=structure.static_rules,
                        requires=structure.requires,
                        action=structure.action,
                        attack=attack,
                        fraction=fraction,
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


def run_guard(case: Scenario, guard_name: str, *, policy: LifetimePolicy) -> dict[str, Any]:
    key = f"v4-test-key-{case.scenario_id}".encode("utf-8").ljust(32, b"-")
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
        result = store.ingest(record, now=case.planning_time)
        if not result.accepted:
            raise AssertionError(f"planning record rejected: {result.reason}")

    proposal = Proposal(
        proposal_id=f"proposal-{case.scenario_id}",
        action=case.action,
        cites={fact: record.record_id for fact, record in planning_records.items()},
        requires=case.requires,
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
        context_observations = planning_records.values()
        context_source = ScriptedSource.from_observations(context_observations)
    elif case.attack == "context_forgery":
        context_source = source_from_context(
            signer,
            facts=case.planning_values,
            values=case.planning_values,
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
    )
    decision = decide(guard_name, context)
    score = score_decision(
        decision=decision,
        static_rules=case.static_rules,
        requires=case.requires,
        execution_values=case.execution_values,
        fresh_reading_available=case.fresh_reading_available,
    )
    return {
        "scenario_id": case.scenario_id,
        "split": case.split,
        "attack": case.attack,
        "fraction": case.fraction,
        "guard": guard_name,
        **score,
        "trace": context.trace,
    }


def run_counterfactual(
    structures: list[Scenario], *, policy: LifetimePolicy | None = None
) -> list[dict[str, Any]]:
    policy = policy or LifetimePolicy()
    results: list[dict[str, Any]] = []
    for case in counterfactual_cases(structures):
        for guard_name in ("B0", "PEEK", "VER", "FBS", "PHYS", "M", "AR", "MS", "SL"):
            results.append(run_guard(case, guard_name, policy=policy))
    return results
