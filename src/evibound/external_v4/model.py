"""Core data types shared by the v4 guard, oracle and experiment runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import math
from numbers import Real
from typing import Any, Mapping


class FactKind(str, Enum):
    CONTINUOUS = "continuous"
    COUNTDOWN = "countdown"
    EVENT = "event"
    HUMAN_MUTABLE = "human_mutable"
    AGENT_MUTABLE = "agent_mutable"
    WINDOW = "window"
    IRRELEVANT = "irrelevant"


class Truth(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class DecisionStatus(str, Enum):
    EXECUTE = "execute"
    DEFER = "defer"
    REJECT = "reject"


@dataclass(frozen=True)
class Fact:
    name: str
    kind: FactKind
    max_rate: float | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("fact name must be non-empty")
        if self.kind is FactKind.CONTINUOUS:
            if self.max_rate is None or not math.isfinite(self.max_rate) or self.max_rate < 0:
                raise ValueError("continuous facts need a finite non-negative max_rate")
        elif self.max_rate is not None:
            raise ValueError("max_rate is only valid for continuous facts")


@dataclass(frozen=True)
class Condition:
    fact: str
    operator: str
    value: Any
    priority: float = 0.0

    OPERATORS = frozenset(("eq", "ne", "lt", "le", "gt", "ge"))

    def __post_init__(self) -> None:
        if self.operator not in self.OPERATORS:
            raise ValueError(f"unknown comparison operator: {self.operator}")

    def holds(self, observed: Any) -> bool:
        if self.operator == "eq":
            return observed == self.value
        if self.operator == "ne":
            return observed != self.value
        try:
            if self.operator == "lt":
                return observed < self.value
            if self.operator == "le":
                return observed <= self.value
            if self.operator == "gt":
                return observed > self.value
            return observed >= self.value
        except TypeError:
            return False


@dataclass(frozen=True)
class AllOf:
    terms: tuple["Expression", ...]

    def __post_init__(self) -> None:
        if not self.terms:
            raise ValueError("all_of needs at least one term")


@dataclass(frozen=True)
class AnyOf:
    terms: tuple["Expression", ...]

    def __post_init__(self) -> None:
        if not self.terms:
            raise ValueError("any_of needs at least one term")


Expression = Condition | AllOf | AnyOf


def all_of(*terms: Expression) -> AllOf:
    return AllOf(tuple(terms))


def any_of(*terms: Expression) -> AnyOf:
    return AnyOf(tuple(terms))


def conditions_in(expression: Expression) -> tuple[Condition, ...]:
    if isinstance(expression, Condition):
        return (expression,)
    found: list[Condition] = []
    for term in expression.terms:
        found.extend(conditions_in(term))
    return tuple(found)


@dataclass(frozen=True)
class Action:
    device: str
    command: str
    arguments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.device or not self.command:
            raise ValueError("action device and command must be non-empty")
        object.__setattr__(self, "arguments", dict(self.arguments))

    def as_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "command": self.command,
            "arguments": dict(self.arguments),
        }


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    action: Action
    cites: Mapping[str, str]
    requires: Expression

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise ValueError("proposal_id must be non-empty")
        object.__setattr__(self, "cites", dict(self.cites))


@dataclass(frozen=True)
class SignedObservation:
    record_id: str
    fact: str
    value: Any
    observed_at: float
    sequence: int
    epoch: int
    signature: str

    def __post_init__(self) -> None:
        if not self.record_id or not self.fact:
            raise ValueError("record_id and fact must be non-empty")
        if (
            not isinstance(self.observed_at, Real)
            or isinstance(self.observed_at, bool)
            or not math.isfinite(self.observed_at)
        ):
            raise ValueError("observed_at must be finite")
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        if type(self.epoch) is not int or self.epoch < 0:
            raise ValueError("epoch must be a non-negative integer")

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "fact": self.fact,
            "value": self.value,
            "observed_at": self.observed_at,
            "sequence": self.sequence,
            "epoch": self.epoch,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.unsigned_payload(), "signature": self.signature}


@dataclass(frozen=True)
class Decision:
    status: DecisionStatus
    reason_code: str
    reads: int = 0
    evidence: Mapping[str, str] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def execute(self) -> bool:
        return self.status is DecisionStatus.EXECUTE

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason_code": self.reason_code,
            "reads": self.reads,
            "evidence": dict(self.evidence),
            "details": dict(self.details),
        }


def strict_json_equal(left: Any, right: Any) -> bool:
    """Compare JSON-shaped values without treating ``True`` as ``1``."""
    try:
        return json.dumps(left, sort_keys=True, separators=(",", ":"), allow_nan=False) == json.dumps(
            right, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError):
        return False
