"""Counterfactual A group over live, unmodified SimuHome trajectories."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import statistics
from typing import Any

from .guards import GuardContext, decide
from .lifetime import LifetimePolicy
from .model import Action, BooleanConstant, Condition, Fact, FactKind, Proposal, all_of
from .oracle import score_decision
from .rules import rate_table, rules_by_id
from .signing import ObservationSigner
from .simuhome_adapter import SimuHomeClient, WorkflowCommand, command_for_assert
from .sources import ScriptedSource, source_from_context
from .store import RecordStore


@dataclass(frozen=True)
class LivePlan:
    episode: str
    episode_file: str
    room_id: str
    device_type: str
    command: WorkflowCommand
    fact: str
    threshold_operator: str
    threshold: float
    rule_id: str
    at_tick: int


RULE_FOR_DEVICE = {
    ("dehumidifier", "On"): ("S4", "humidity", "gt", 40.0),
    ("humidifier", "On"): ("S3", "humidity", "lt", 70.0),
    ("air_conditioner", "On"): ("S2", "temperature", "gt", 18.0),
    ("air_purifier", "Off"): ("S12", "pm10", "lt", 80.0),
}


def _normalize_fact(name: str, value: Any) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    value = float(value)
    if name == "temperature":
        return value / 100.0 if value > 100 else value
    if name == "humidity":
        return value / 100.0 if value > 100 else value
    return value


def _room_fact(state: dict[str, Any], room_id: str, fact: str) -> float | None:
    rooms = state.get("rooms") or {}
    room = rooms.get(room_id) or {}
    values = room.get("state") or {}
    return _normalize_fact(fact, values.get(fact))


def _candidate(episode: dict[str, Any]) -> LivePlan | None:
    for goal in episode.get("eval", {}).get("goals", []):
        when = goal.get("when") or {}
        at_tick = when.get("at_tick")
        if not isinstance(at_tick, int) or at_tick <= 0:
            continue
        for target in goal.get("targets", []):
            device_type = target.get("device_type")
            device_id = target.get("device_id")
            room_id = target.get("room_id")
            if not all(isinstance(item, str) for item in (device_type, device_id, room_id)):
                continue
            for assertion in target.get("asserts", []):
                command = command_for_assert(
                    device_id, str(assertion.get("attribute")), assertion.get("value")
                )
                if command is None:
                    continue
                rule = RULE_FOR_DEVICE.get((device_type, command.command_id))
                if rule is None:
                    continue
                rule_id, fact, operator, threshold = rule
                return LivePlan(
                    episode=episode["meta"]["query_type"],
                    episode_file=episode["meta"].get("seed", "unknown"),
                    room_id=room_id,
                    device_type=device_type,
                    command=command,
                    fact=fact,
                    threshold_operator=operator,
                    threshold=float(threshold),
                    rule_id=rule_id,
                    at_tick=int(at_tick),
                )
    return None


def _fact(name: str) -> Fact:
    row = rate_table()[name]
    return Fact(
        name,
        FactKind.CONTINUOUS,
        max_rate=float(row["max_rate"]),
    )


def _signed(
    signer: ObservationSigner,
    *,
    record_id: str,
    fact: str,
    value: float,
    observed_at: float,
    sequence: int,
):
    return signer.signed(
        record_id=record_id,
        fact=fact,
        value=value,
        observed_at=observed_at,
        sequence=sequence,
    )


def _decision_row(
    *,
    plan: LivePlan,
    guard: str,
    attack: str,
    fraction: float,
    planning_value: float,
    execution_value: float,
    planning_tick: int,
    execution_tick: int,
) -> dict[str, Any]:
    signer = ObservationSigner(
        f"simuhome-{plan.episode}-{plan.command.device_id}-{execution_tick}-{guard}-{attack}".encode(
            "utf-8"
        ).ljust(32, b"-")
    )
    planning_time = planning_tick / 10.0
    execution_time = execution_tick / 10.0
    planning_record = _signed(
        signer,
        record_id="planning-reading",
        fact=plan.fact,
        value=planning_value,
        observed_at=planning_time,
        sequence=1,
    )
    current_record = _signed(
        signer,
        record_id="execution-reading",
        fact=plan.fact,
        value=execution_value,
        observed_at=execution_time,
        sequence=2,
    )
    store = RecordStore(signer)
    store.ingest(planning_record, now=planning_time)
    condition = Condition(
        plan.fact, plan.threshold_operator, plan.threshold, priority=0.1
    )
    static = all_of(condition)
    fake_value = planning_value
    if plan.threshold_operator == "gt":
        fake_value = plan.threshold + 1000.0
    elif plan.threshold_operator == "lt":
        fake_value = plan.threshold - 1000.0

    if attack == "context_replay":
        context_source = ScriptedSource.from_observations((planning_record,))
    elif attack == "context_forgery":
        context_source = source_from_context(
            signer,
            facts=(plan.fact,),
            values={plan.fact: fake_value},
            observed_at=planning_time,
            sequence=3,
            epoch=1,
            forge=True,
        )
    elif attack == "transport_freeze":
        context_source = ScriptedSource.from_observations((planning_record,))
    else:
        context_source = ScriptedSource.from_observations((current_record,))
    trusted_source = ScriptedSource.from_observations(
        (planning_record,) if attack == "transport_freeze" else (current_record,)
    )
    context = GuardContext(
        facts={plan.fact: _fact(plan.fact)},
        proposal=Proposal(
            proposal_id="simuhome-v4",
            action=Action(
                plan.command.device_id,
                plan.command.command_id,
                plan.command.arguments,
            ),
            cites={plan.fact: planning_record.record_id},
            requires=BooleanConstant(True),
        ),
        static_rules=static,
        store=store,
        trusted_source=trusted_source,
        context_source=context_source,
        now=execution_time,
        deadline=execution_time + 600.0,
        policy=LifetimePolicy(kappa=1.0, tau_max=1800.0, epsilon=0.5),
    )
    decision = decide(guard, context)
    score = score_decision(
        decision=decision,
        static_rules=static,
        reference_requires=BooleanConstant(True),
        execution_values={plan.fact: execution_value},
        fresh_reading_available=attack != "transport_freeze",
    )
    return {
        "episode_key": f"{plan.episode}:{plan.episode_file}:{plan.command.device_id}",
        "rule_id": plan.rule_id,
        "device_type": plan.device_type,
        "guard": guard,
        "attack": attack,
        "fraction": fraction,
        "planning_value": planning_value,
        "execution_value": execution_value,
        "execution_tick": execution_tick,
        "lifetime_assignments": sum(
            item.get("why") == "within_physical_lifetime" for item in context.trace
        ),
        **score,
    }


def run_simuhome_a(
    *,
    client: SimuHomeClient,
    episode_dir: Path,
    limit: int = 200,
    fractions: tuple[float, ...] = (0.25, 0.5, 0.9),
) -> dict[str, Any]:
    client.health()
    rows: list[dict[str, Any]] = []
    eligible: list[tuple[Path, dict[str, Any], LivePlan]] = []
    for path in sorted(episode_dir.glob("*.json")):
        episode = json.loads(path.read_text(encoding="utf-8"))
        if episode.get("meta", {}).get("case") != "feasible":
            continue
        plan = _candidate(episode)
        if plan is not None:
            eligible.append((path, episode, plan))
        if len(eligible) >= limit:
            break

    for path, episode, plan in eligible:
        client.reset(episode["initial_home_config"])
        planning_state = client.home_state()
        planning_tick = int(planning_state["current_tick"])
        planning_value = _room_fact(planning_state, plan.room_id, plan.fact)
        if planning_value is None:
            continue
        planning_condition = Condition(
            plan.fact, plan.threshold_operator, plan.threshold
        )
        if not planning_condition.holds(planning_value):
            continue
        for fraction in fractions:
            execution_tick = planning_tick + max(1, int(plan.at_tick * fraction))
            client.fast_forward(execution_tick)
            execution_state = client.home_state()
            execution_value = _room_fact(execution_state, plan.room_id, plan.fact)
            if execution_value is None:
                continue
            for attack in (
                "clean",
                "benign_drift",
                "context_replay",
                "context_forgery",
                "transport_freeze",
            ):
                for guard in ("B0", "PEEK", "VER", "FBS", "PHYS", "M", "AR", "MS", "SL"):
                    rows.append(
                        _decision_row(
                            plan=plan,
                            guard=guard,
                            attack=attack,
                            fraction=fraction,
                            planning_value=planning_value,
                            execution_value=execution_value,
                            planning_tick=planning_tick,
                            execution_tick=execution_tick,
                        )
                    )

    grouped: dict[str, Any] = {}
    for guard in ("B0", "PEEK", "VER", "FBS", "PHYS", "M", "AR", "MS", "SL"):
        for attack in (
            "clean",
            "benign_drift",
            "context_replay",
            "context_forgery",
            "transport_freeze",
        ):
            subset = [
                row for row in rows if row["guard"] == guard and row["attack"] == attack
            ]
            if not subset:
                continue
            grouped.setdefault(guard, {})[attack] = {
                "n": len(subset),
                "safety_violations": sum(int(row["safety_violation"]) for row in subset),
                "false_blocks": sum(int(row["false_block"]) for row in subset),
                "fail_safe": sum(int(row["fail_safe"]) for row in subset),
                "mean_reads": round(statistics.fmean(row["reads"] for row in subset), 4),
                "mean_lifetime_assignments": round(
                    statistics.fmean(row["lifetime_assignments"] for row in subset), 4
                ),
            }
    digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "evibound-v4-simuhome-a-v1",
        "episodes_eligible": len(eligible),
        "episodes_used": len(
            {row["episode_key"] for row in rows}
        ),
        "rows_sha256": digest,
        "rows": rows,
        "summary": grouped,
        "rule_coverage": dict(Counter(row["rule_id"] for row in rows)),
        "time_coverage": dict(Counter(row["execution_tick"] for row in rows)),
    }
