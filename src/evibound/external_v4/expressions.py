"""Three-valued evaluation and short-circuit read ordering."""

from __future__ import annotations

from collections.abc import Mapping

from .model import (
    AllOf,
    AnyOf,
    BooleanConstant,
    Condition,
    Expression,
    Truth,
    condition_key,
    conditions_in,
)


def evaluate(expression: Expression, values: Mapping[str, Truth]) -> Truth:
    if isinstance(expression, BooleanConstant):
        return Truth.TRUE if expression.value else Truth.FALSE
    if isinstance(expression, Condition):
        return values.get(condition_key(expression), Truth.UNKNOWN)
    if isinstance(expression, AllOf):
        saw_unknown = False
        for term in expression.terms:
            result = evaluate(term, values)
            if result is Truth.FALSE:
                return Truth.FALSE
            saw_unknown = saw_unknown or result is Truth.UNKNOWN
        return Truth.UNKNOWN if saw_unknown else Truth.TRUE
    if isinstance(expression, AnyOf):
        saw_unknown = False
        for term in expression.terms:
            result = evaluate(term, values)
            if result is Truth.TRUE:
                return Truth.TRUE
            saw_unknown = saw_unknown or result is Truth.UNKNOWN
        return Truth.UNKNOWN if saw_unknown else Truth.FALSE
    raise TypeError(f"unknown expression: {type(expression).__name__}")


def unknown_conditions(
    expression: Expression, values: Mapping[str, Truth]
) -> list[Condition]:
    return [
        condition
        for condition in conditions_in(expression)
        if values.get(condition_key(condition), Truth.UNKNOWN) is Truth.UNKNOWN
    ]


def read_priority(expression: Expression, values: Mapping[str, Truth]) -> list[Condition]:
    """Order unknown conditions by how likely a read is to decide the expression.

    ``priority`` is supplied by the experiment or planner adapter. It is only a
    read-order heuristic; no correctness result depends on it.
    """
    candidates = unknown_conditions(expression, values)
    seen: set[str] = set()
    unique: list[Condition] = []
    for condition in candidates:
        key = condition_key(condition)
        if key not in seen:
            unique.append(condition)
            seen.add(key)

    if isinstance(expression, AllOf):
        return sorted(unique, key=lambda item: item.priority)
    if isinstance(expression, AnyOf):
        return sorted(unique, key=lambda item: -item.priority)

    def mixed_score(condition: Condition) -> float:
        return condition.priority

    return sorted(unique, key=mixed_score)
