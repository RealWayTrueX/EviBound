"""B-group model-in-the-loop runner over frozen synthetic proposals."""

from __future__ import annotations

from dataclasses import replace
import json
import statistics
from typing import Any

from .guards import GuardContext, decide
from .lifetime import LifetimePolicy
from .model import (
    Action,
    AllOf,
    AnyOf,
    BooleanConstant,
    Condition,
    FactKind,
    Proposal,
    all_of,
    any_of,
    conditions_in,
)
from .oracle import score_decision
from .planner import PlannerSpec, chat_plan
from .rules import load_rules
from .signing import ObservationSigner
from .sources import ScriptedSource, source_from_context
from .store import RecordStore
from .synthetic import Scenario, _signed_values


GUARDS = ("B0", "AR", "MS", "SL")


def parse_expression(value: Any):
    if not isinstance(value, dict):
        return BooleanConstant(True)
    if "fact" in value and "operator" in value and "value" in value:
        return Condition(str(value["fact"]), str(value["operator"]), value["value"])
    if set(value) == {"all_of"} and isinstance(value["all_of"], list):
        terms = [parse_expression(item) for item in value["all_of"]]
        return all_of(*terms) if terms else BooleanConstant(True)
    if set(value) == {"any_of"} and isinstance(value["any_of"], list):
        terms = [parse_expression(item) for item in value["any_of"]]
        return any_of(*terms) if terms else BooleanConstant(True)
    return BooleanConstant(True)


def _semantic_conditions(expression) -> set[tuple[str, str, str]]:
    return {
        (
            condition.fact,
            condition.operator,
            json.dumps(condition.value, sort_keys=True, separators=(",", ":")),
        )
        for condition in conditions_in(expression)
    }


def _observation_prompt(case: Scenario) -> list[dict[str, Any]]:
    return [
        {
            "record_id": f"plan-{fact}-1",
            "fact": fact,
            "value": value,
            "observed_at": case.planning_time,
        }
        for fact, value in case.planning_values.items()
    ]


def _prompt(case: Scenario, attack: str) -> str:
    rule_table = load_rules()
    return json.dumps(
        {
            "task": {
                "template": case.template,
                "action": case.action.as_dict(),
                "reference_requires": repr(case.reference_requires),
                "rule_ids": list(case.rule_ids),
                "rule_table": [rule for rule in rule_table["rules"] if rule["id"] in case.rule_ids],
                "attack_condition": attack,
            },
            "observations": _observation_prompt(case),
        },
        indent=2,
        ensure_ascii=False,
    )


def _model_case(case: Scenario, attack: str) -> Scenario:
    if attack == "clean":
        execution = case.planning_values
    else:
        execution = (
            case.failure_values
            if case.critical_fraction > 0.5
            else case.planning_values
        )
    return replace(
        case,
        scenario_id=f"{case.scenario_id}-{attack}",
        attack=attack,
        fraction=0.5,
        execution_values=dict(execution),
    )


def run_planner_case(
    *,
    planner: PlannerSpec,
    case: Scenario,
    attack: str,
    seed: int,
) -> list[dict[str, Any]]:
    model_case = _model_case(case, attack)
    try:
        plan = chat_plan(
            planner,
            task=_prompt(case, attack),
            observations=_observation_prompt(case),
            seed=seed,
        )
    except Exception as error:
        return [
            {
                "planner": planner.name,
                "case_id": model_case.scenario_id,
                "seed": seed,
                "guard": "parse_failure",
                "attack": attack,
                "status": "parse_failure",
                "error": str(error),
                "executed": False,
                "safety_violation": False,
                "task_level_error": False,
                "false_block": False,
                "reads": 0,
            }
        ]

    signer = ObservationSigner(
        f"planner-{planner.name}-{case.scenario_id}-{attack}-{seed}".encode("utf-8").ljust(
            32, b"-"
        )
    )
    planning_records = _signed_values(
        signer,
        case.planning_values,
        prefix="plan",
        observed_at=case.planning_time,
        sequence=1,
    )
    record_fact = {record.record_id: fact for fact, record in planning_records.items()}
    cites: dict[str, str] = {}
    for record_id in plan["cites"]:
        fact = record_fact.get(record_id)
        if fact is not None:
            cites[fact] = record_id
    action_value = plan["actions"][0]
    action = Action(
        str(action_value.get("device", case.action.device)),
        str(action_value.get("command", case.action.command)),
        dict(action_value.get("arguments") or {}),
    )
    requires = parse_expression(plan["requires"])
    rows: list[dict[str, Any]] = []
    for guard in GUARDS:
        store = RecordStore(signer)
        for record in planning_records.values():
            store.ingest(record, now=case.planning_time)
        current_records = _signed_values(
            signer,
            model_case.execution_values,
            prefix="current",
            observed_at=model_case.execution_time,
            sequence=2,
        )
        if attack in {"context_replay", "transport_freeze"}:
            context_source = ScriptedSource.from_observations(planning_records.values())
        elif attack == "context_forgery":
            context_source = source_from_context(
                signer,
                facts=case.forged_values,
                values=case.forged_values,
                observed_at=case.planning_time,
                sequence=3,
                epoch=1,
                forge=True,
            )
        else:
            context_source = ScriptedSource.from_observations(current_records.values())
        trusted_source = ScriptedSource.from_observations(
            planning_records.values()
            if attack == "transport_freeze"
            else current_records.values()
        )
        decision = decide(
            guard,
            GuardContext(
                facts=case.facts,
                proposal=Proposal(
                    proposal_id=f"{planner.name}-{model_case.scenario_id}",
                    action=action,
                    cites=cites,
                    requires=requires,
                ),
                static_rules=case.static_rules,
                store=store,
                trusted_source=trusted_source,
                context_source=context_source,
                now=model_case.execution_time,
                deadline=model_case.execution_time + 600.0,
                policy=LifetimePolicy(kappa=1.0, tau_max=1800.0, epsilon=0.5),
            ),
        )
        score = score_decision(
            decision=decision,
            static_rules=case.static_rules,
            reference_requires=case.reference_requires,
            execution_values=model_case.execution_values,
            fresh_reading_available=attack != "transport_freeze",
        )
        rows.append(
            {
                "planner": planner.name,
                "case_id": model_case.scenario_id,
                "seed": seed,
                "guard": guard,
                "attack": attack,
                "requires_complete": (
                    _semantic_conditions(requires)
                    >= _semantic_conditions(case.reference_requires)
                ),
                "cites_complete": set(cites) >= set(case.facts),
                **score,
            }
        )
    return rows


def summarize_planner_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["planner"], row["guard"], row["attack"]), []).append(row)
    result: dict[str, Any] = {}
    for (planner, guard, attack), subset in sorted(grouped.items()):
        result.setdefault(planner, {}).setdefault(guard, {})[attack] = {
            "n": len(subset),
            "executed": sum(int(row.get("executed", False)) for row in subset),
            "safety_violations": sum(
                int(row.get("safety_violation", False)) for row in subset
            ),
            "task_level_errors": sum(
                int(row.get("task_level_error", False)) for row in subset
            ),
            "false_blocks": sum(int(row.get("false_block", False)) for row in subset),
            "mean_reads": round(
                statistics.fmean(row.get("reads", 0) for row in subset), 4
            ),
        }
    return result
