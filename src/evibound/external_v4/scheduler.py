"""Scheduled execution loop with defer, retry, deadline and reason codes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .model import Decision, DecisionStatus


@dataclass(frozen=True)
class ScheduleResult:
    status: str
    reason_code: str
    attempts: int
    final_clock: float
    decisions: tuple[Decision, ...] = field(default_factory=tuple)


def run_scheduled_action(
    *,
    due_at: float,
    deadline: float,
    decide_at: Callable[[float], tuple[Decision, float | None]],
) -> ScheduleResult:
    """Evaluate at due time and follow guard-directed retry times.

    ``decide_at`` returns a decision and the next retry time for a deferral.
    A deferral without a retry time is rejected rather than silently dropped.
    """
    clock = due_at
    attempts = 0
    decisions: list[Decision] = []
    while clock <= deadline:
        attempts += 1
        decision, retry_at = decide_at(clock)
        decisions.append(decision)
        if decision.status is DecisionStatus.EXECUTE:
            return ScheduleResult("executed", decision.reason_code, attempts, clock, tuple(decisions))
        if decision.status is DecisionStatus.REJECT:
            return ScheduleResult("rejected", decision.reason_code, attempts, clock, tuple(decisions))
        if retry_at is None or retry_at <= clock:
            return ScheduleResult(
                "rejected", "defer_without_progress", attempts, clock, tuple(decisions)
            )
        clock = min(retry_at, deadline + 1e-9)
    return ScheduleResult("rejected", "deadline_expired", attempts, clock, tuple(decisions))
