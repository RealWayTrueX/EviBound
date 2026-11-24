"""Evidence lifetimes and the conservative three-valued assignment rule."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .model import Condition, Fact, FactKind, SignedObservation, Truth


@dataclass(frozen=True)
class LifetimePolicy:
    kappa: float = 1.0
    tau_max: float = 600.0
    epsilon: float = 0.5

    def __post_init__(self) -> None:
        if not math.isfinite(self.kappa) or self.kappa < 1:
            raise ValueError("kappa must be finite and at least 1")
        if not math.isfinite(self.tau_max) or self.tau_max < 0:
            raise ValueError("tau_max must be finite and non-negative")
        if not math.isfinite(self.epsilon) or self.epsilon < 0:
            raise ValueError("epsilon must be finite and non-negative")


def _numeric(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def margin_to_threshold(value: object, condition: Condition) -> float | None:
    observed = _numeric(value)
    threshold = _numeric(condition.value)
    if observed is None or threshold is None:
        return None
    if condition.operator in ("gt", "ge"):
        return observed - threshold
    if condition.operator in ("lt", "le"):
        return threshold - observed
    return None


def lifetime(
    fact: Fact, observation: SignedObservation, condition: Condition, policy: LifetimePolicy
) -> float:
    if fact.kind in (FactKind.IRRELEVANT,):
        return math.inf
    if fact.kind in (FactKind.EVENT, FactKind.HUMAN_MUTABLE):
        return 0.0
    if fact.kind is FactKind.AGENT_MUTABLE:
        return math.inf
    if fact.kind is FactKind.WINDOW:
        assert fact.window_end is not None
        return max(0.0, min(fact.window_end, observation.observed_at + policy.tau_max) - observation.observed_at - policy.epsilon)
    if fact.kind is FactKind.COUNTDOWN:
        remaining = _numeric(observation.value)
        if remaining is None or not condition.holds(observation.value):
            return 0.0
        return max(0.0, min(remaining, policy.tau_max) - policy.epsilon)

    margin = margin_to_threshold(observation.value, condition)
    if margin is None or margin < 0:
        return 0.0
    assert fact.max_rate is not None
    if fact.max_rate == 0:
        return math.inf
    return max(
        0.0,
        min(margin / (policy.kappa * fact.max_rate), policy.tau_max) - policy.epsilon,
    )


def assign(
    *,
    fact: Fact,
    observation: SignedObservation,
    condition: Condition,
    now: float,
    policy: LifetimePolicy,
) -> tuple[Truth, dict[str, float | str | bool]]:
    """Assign true, false or unknown from one authentic record.

    A true reading remains true only inside its physical lifetime. A false
    reading is returned as false only when the declared rate proves it cannot
    cross the condition threshold by ``now``.
    """
    age = now - observation.observed_at
    tau = lifetime(fact, observation, condition, policy)
    detail: dict[str, float | str | bool] = {
        "age": age,
        "tau": tau,
        "record_value": observation.value,
        "satisfied_at_observation": condition.holds(observation.value),
    }
    if age < 0:
        return Truth.UNKNOWN, {**detail, "why": "future_dated"}
    if age <= policy.epsilon:
        return (
            Truth.TRUE if condition.holds(observation.value) else Truth.FALSE,
            {**detail, "why": "current_observation"},
        )
    if age <= tau and condition.holds(observation.value):
        return Truth.TRUE, {**detail, "why": "within_physical_lifetime"}

    if not condition.holds(observation.value):
        margin = margin_to_threshold(observation.value, condition)
        if fact.kind is FactKind.CONTINUOUS and margin is not None and fact.max_rate is not None:
            if condition.operator in ("gt", "ge"):
                distance_to_satisfy = max(0.0, condition.value - observation.value)
            else:
                distance_to_satisfy = max(0.0, observation.value - condition.value)
            if distance_to_satisfy > fact.max_rate * age:
                return Truth.FALSE, {**detail, "why": "cannot_cross_by_execution"}
        if fact.kind in (FactKind.EVENT, FactKind.HUMAN_MUTABLE):
            return Truth.UNKNOWN, {**detail, "why": "mutable_false_reading"}

    return Truth.UNKNOWN, {**detail, "why": "expired_or_cannot_prove"}


def overshoot_bound(
    rho: float, kappa: float, declared_rate: float, tau: float, epsilon: float
) -> float:
    """Maximum threshold overshoot when the true rate is ``rho / kappa`` too high."""
    return max(0.0, rho - kappa) * declared_rate * (tau + epsilon)
