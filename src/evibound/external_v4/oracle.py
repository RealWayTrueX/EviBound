"""Independent binary scoring against scenario truth.

This module imports only the data types needed to read an expression. It has
its own two-valued evaluator and never calls the guard evaluator.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .model import AllOf, AnyOf, BooleanConstant, Condition, Decision, Expression


def _binary_condition(condition: Condition, values: Mapping[str, Any]) -> bool:
    if condition.fact not in values:
        return False
    observed = values[condition.fact]
    threshold = condition.value
    if condition.operator == "eq":
        return type(observed) is type(threshold) and observed == threshold
    if condition.operator == "ne":
        return not (type(observed) is type(threshold) and observed == threshold)
    try:
        if condition.operator == "lt":
            return observed < threshold
        if condition.operator == "le":
            return observed <= threshold
        if condition.operator == "gt":
            return observed > threshold
        if condition.operator == "ge":
            return observed >= threshold
    except TypeError:
        return False
    raise ValueError(f"unknown operator: {condition.operator}")


def binary_evaluate(expression: Expression, values: Mapping[str, Any]) -> bool:
    if isinstance(expression, BooleanConstant):
        return expression.value
    if isinstance(expression, Condition):
        return _binary_condition(expression, values)
    if isinstance(expression, AllOf):
        return all(binary_evaluate(term, values) for term in expression.terms)
    if isinstance(expression, AnyOf):
        return any(binary_evaluate(term, values) for term in expression.terms)
    raise TypeError(f"unknown expression: {type(expression).__name__}")


def score_decision(
    *,
    decision: Decision,
    static_rules: Expression,
    reference_requires: Expression,
    execution_values: Mapping[str, Any],
    fresh_reading_available: bool,
) -> dict[str, Any]:
    static = binary_evaluate(static_rules, execution_values)
    task = binary_evaluate(reference_requires, execution_values)
    truth = static and task
    executed = decision.execute
    return {
        "status": decision.status.value,
        "reason_code": decision.reason_code,
        "reads": decision.reads,
        "executed": executed,
        "truth_precondition": truth,
        "static_true": static,
        "task_true": task,
        "safety_violation": bool(executed and not static),
        "task_level_error": bool(executed and static and not task),
        "false_block": bool(not executed and truth and fresh_reading_available),
        "fail_safe": bool(
            not executed
            and not fresh_reading_available
            and decision.reason_code in {"stale_evidence", "unknown_record"}
        ),
        "evidence": dict(decision.evidence),
    }
