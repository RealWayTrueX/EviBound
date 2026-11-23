"""Independent execution-time scoring for the v4 counterfactual runner."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .model import Condition, Decision, Expression, Truth


def condition_truth(condition: Condition, values: Mapping[str, Any]) -> Truth:
    if condition.fact not in values:
        return Truth.UNKNOWN
    return Truth.TRUE if condition.holds(values[condition.fact]) else Truth.FALSE


def expression_truth(expression: Expression, values: Mapping[str, Any]) -> Truth:
    from .expressions import evaluate

    assignment = {
        condition.fact: condition_truth(condition, values)
        for condition in _conditions(expression)
    }
    return evaluate(expression, assignment)


def _conditions(expression: Expression) -> tuple[Condition, ...]:
    from .model import conditions_in

    return conditions_in(expression)


def score_decision(
    *,
    decision: Decision,
    static_rules: Expression,
    requires: Expression,
    execution_values: Mapping[str, Any],
    fresh_reading_available: bool,
) -> dict[str, Any]:
    static = expression_truth(static_rules, execution_values)
    task = expression_truth(requires, execution_values)
    truth = Truth.TRUE if static is Truth.TRUE and task is Truth.TRUE else Truth.FALSE
    executed = decision.execute
    unsafe = bool(executed and static is Truth.FALSE)
    task_error = bool(executed and static is Truth.TRUE and task is Truth.FALSE)
    false_block = bool(not executed and truth is Truth.TRUE and fresh_reading_available)
    fail_safe = bool(
        not executed
        and not fresh_reading_available
        and decision.reason_code in {"stale_evidence", "unknown_record"}
    )
    return {
        "status": decision.status.value,
        "reason_code": decision.reason_code,
        "reads": decision.reads,
        "executed": executed,
        "truth_precondition": truth.value,
        "static_true": static.value,
        "task_true": task.value,
        "safety_violation": unsafe,
        "task_level_error": task_error,
        "false_block": false_block,
        "fail_safe": fail_safe,
        "evidence": dict(decision.evidence),
    }
