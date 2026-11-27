"""EviBound-T and the v4 comparison baselines.

Condition truth is keyed by the full predicate, never by fact name. This
prevents a planner's weak predicate from overwriting a stricter static rule
over the same fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .expressions import evaluate, read_priority
from .lifetime import LifetimePolicy, assign
from .model import (
    AllOf,
    Condition,
    Decision,
    DecisionStatus,
    Expression,
    Fact,
    FactKind,
    Proposal,
    SignedObservation,
    Truth,
    condition_key,
    conditions_in,
    strict_json_equal,
)
from .sources import ScriptedSource
from .store import RecordStore


@dataclass
class GuardContext:
    facts: dict[str, Fact]
    proposal: Proposal
    static_rules: Expression
    store: RecordStore
    trusted_source: ScriptedSource
    context_source: ScriptedSource
    now: float
    deadline: float
    policy: LifetimePolicy
    fixed_delta: float = 120.0
    fresh_reading_available: bool = True
    ablation: str = ""
    rate_overrides: dict[str, float] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    dep_conditions: tuple[Condition, ...] = field(init=False)
    conditions_by_fact: dict[str, tuple[Condition, ...]] = field(init=False)

    def __post_init__(self) -> None:
        conditions = conditions_in(self.static_rules) + conditions_in(
            self.proposal.requires
        )
        object.__setattr__(self, "dep_conditions", conditions)
        grouped: dict[str, list[Condition]] = {}
        for condition in conditions:
            grouped.setdefault(condition.fact, []).append(condition)
        object.__setattr__(
            self,
            "conditions_by_fact",
            {fact: tuple(items) for fact, items in grouped.items()},
        )


def _dep_conditions(context: GuardContext) -> tuple[Condition, ...]:
    return context.dep_conditions


def _dep_facts(context: GuardContext) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for condition in _dep_conditions(context):
        if condition.fact not in seen:
            ordered.append(condition.fact)
            seen.add(condition.fact)
    return ordered


def _conditions_by_fact(context: GuardContext) -> dict[str, tuple[Condition, ...]]:
    return context.conditions_by_fact


def _combined(context: GuardContext) -> AllOf:
    return AllOf((context.static_rules, context.proposal.requires))


def _fact_for_mode(context: GuardContext, fact_name: str) -> Fact:
    fact = context.facts[fact_name]
    if context.ablation == "observed_rate_lifetime" and fact_name in context.rate_overrides:
        return replace(fact, max_rate=context.rate_overrides[fact_name])
    if context.ablation == "rate_x0.5" and fact.max_rate is not None:
        return replace(fact, max_rate=fact.max_rate * 0.5)
    if context.ablation == "rate_x2" and fact.max_rate is not None:
        return replace(fact, max_rate=fact.max_rate * 2.0)
    return fact


def _fixed_assignment(
    condition: Condition, observation: SignedObservation, *, now: float, delta: float
) -> Truth:
    age = now - observation.observed_at
    if age < 0 or age > delta:
        return Truth.UNKNOWN
    if condition.holds(observation.value):
        return Truth.TRUE
    return Truth.FALSE if age <= 1e-9 else Truth.UNKNOWN


def _assignment_from_observation(
    context: GuardContext,
    fact_name: str,
    observation: SignedObservation,
    *,
    mode: str,
) -> dict[str, Truth]:
    result: dict[str, Truth] = {}
    for condition in _conditions_by_fact(context)[fact_name]:
        if mode == "fixed":
            truth = _fixed_assignment(
                condition,
                observation,
                now=context.now,
                delta=context.fixed_delta,
            )
        else:
            truth, detail = assign(
                fact=_fact_for_mode(context, fact_name),
                observation=observation,
                condition=condition,
                now=context.now,
                policy=context.policy,
            )
            context.trace.append(
                {
                    "stage": "assign",
                    "fact": fact_name,
                    "condition": condition_key(condition),
                    "truth": truth.value,
                    **detail,
                }
            )
        result[condition_key(condition)] = truth
    return result


def _assign_cited(
    context: GuardContext, *, mode: str
) -> tuple[dict[str, Truth], dict[str, str], str | None]:
    assignment: dict[str, Truth] = {}
    evidence: dict[str, str] = {}
    for fact_name in _dep_facts(context):
        record_id = context.proposal.cites.get(fact_name)
        if not record_id:
            return assignment, evidence, "missing_citation"
        record = context.store.get(record_id)
        if record is None or record.fact != fact_name:
            return assignment, evidence, "unknown_record"
        if mode == "fixed":
            for condition in _conditions_by_fact(context)[fact_name]:
                assignment[condition_key(condition)] = _fixed_assignment(
                    condition,
                    record,
                    now=context.now,
                    delta=context.fixed_delta,
                )
        else:
            assignment.update(
                _assignment_from_observation(
                    context, fact_name, record, mode=mode
                )
            )
        evidence[fact_name] = record.record_id
    return assignment, evidence, None


def _terminal(
    status: DecisionStatus,
    reason: str,
    reads: int,
    evidence: dict[str, str],
    **details: Any,
) -> Decision:
    return Decision(
        status=status,
        reason_code=reason,
        reads=reads,
        evidence=evidence,
        details=details,
    )


def _truth_decision(
    truth: Truth,
    *,
    now: float,
    deadline: float,
    reads: int,
    evidence: dict[str, str],
    accepted: str = "accepted",
    false_reason: str = "precondition_false",
    unknown_reason: str = "stale_evidence",
) -> Decision:
    if truth is Truth.TRUE:
        return _terminal(DecisionStatus.EXECUTE, accepted, reads, evidence)
    if truth is Truth.FALSE:
        if now < deadline:
            return _terminal(DecisionStatus.DEFER, false_reason, reads, evidence)
        return _terminal(DecisionStatus.REJECT, "deadline_expired", reads, evidence)
    return _terminal(DecisionStatus.REJECT, unknown_reason, reads, evidence)


def _ingest_and_assign(
    context: GuardContext,
    fact_name: str,
    *,
    mode: str,
    assignment: dict[str, Truth],
    evidence: dict[str, str],
) -> tuple[bool, str | None]:
    try:
        observation = context.trusted_source.read(fact_name, context.now)
    except KeyError:
        return False, "unavailable"
    ingested = context.store.ingest(observation, now=context.now)
    if not ingested.accepted:
        return False, ingested.reason
    assignment.update(
        _assignment_from_observation(context, fact_name, observation, mode=mode)
    )
    evidence[fact_name] = observation.record_id
    return True, None


def decide_sl(context: GuardContext) -> Decision:
    assignment, evidence, error = _assign_cited(context, mode="physical")
    if error is not None:
        return _terminal(DecisionStatus.REJECT, error, 0, evidence)
    expression = _combined(context)
    truth = evaluate(expression, assignment)
    if truth is Truth.UNKNOWN and context.ablation == "no_reread":
        return _terminal(DecisionStatus.REJECT, "evidence_expired", 0, evidence)

    attempted: set[str] = set()
    failures: dict[str, str] = {}
    reads = 0
    while truth is Truth.UNKNOWN:
        if context.ablation == "no_short_circuit":
            candidates: list[Condition] = []
            seen_facts: set[str] = set()
            for item in _dep_conditions(context):
                if (
                    assignment.get(condition_key(item), Truth.UNKNOWN) is Truth.UNKNOWN
                    and item.fact not in seen_facts
                    and item.fact not in attempted
                ):
                    candidates.append(item)
                    seen_facts.add(item.fact)
        else:
            candidates = [
                item
                for item in read_priority(expression, assignment)
                if item.fact not in attempted
            ]
        if not candidates:
            break
        made_progress = False
        for condition in candidates:
            fact_name = condition.fact
            if fact_name in attempted:
                continue
            attempted.add(fact_name)
            reads += 1
            accepted, failure = _ingest_and_assign(
                context,
                fact_name,
                mode="physical",
                assignment=assignment,
                evidence=evidence,
            )
            if not accepted:
                failures[fact_name] = failure or "unavailable"
            made_progress = made_progress or accepted
            if context.ablation != "no_short_circuit":
                break
        truth = evaluate(expression, assignment)
        if not made_progress and context.ablation != "no_short_circuit":
            continue

    decision = _truth_decision(
        truth,
        now=context.now,
        deadline=context.deadline,
        reads=reads,
        evidence=evidence,
    )
    return Decision(
        status=decision.status,
        reason_code=decision.reason_code,
        reads=decision.reads,
        evidence=decision.evidence,
        details={**decision.details, "read_failures": failures},
    )


def _batch_guard(context: GuardContext, *, mode: str) -> Decision:
    read_mode = "fixed" if mode == "M" else "physical"
    assignment: dict[str, Truth] = {}
    evidence: dict[str, str] = {}
    if mode in {"M", "MS"}:
        assignment, evidence, error = _assign_cited(context, mode=read_mode)
        if error is not None:
            return _terminal(DecisionStatus.REJECT, error, 0, evidence)
    unknown = {
        condition.fact
        for condition in _dep_conditions(context)
        if assignment.get(condition_key(condition), Truth.UNKNOWN) is Truth.UNKNOWN
    }
    reread_facts = (
        _dep_facts(context) if mode == "AR" else [fact for fact in _dep_facts(context) if fact in unknown]
    )
    reads = 0
    failures: dict[str, str] = {}
    for fact_name in reread_facts:
        reads += 1
        accepted, failure = _ingest_and_assign(
            context,
            fact_name,
            mode=read_mode,
            assignment=assignment,
            evidence=evidence,
        )
        if not accepted:
            failures[fact_name] = failure or "unavailable"
    truth = evaluate(_combined(context), assignment)
    if truth is Truth.UNKNOWN and failures:
        return _terminal(
            DecisionStatus.REJECT,
            "stale_evidence",
            reads,
            evidence,
            read_failures=failures,
        )
    return _truth_decision(
        truth,
        now=context.now,
        deadline=context.deadline,
        reads=reads,
        evidence=evidence,
    )


def decide_m(context: GuardContext) -> Decision:
    return _batch_guard(context, mode="M")


def decide_ar(context: GuardContext) -> Decision:
    return _batch_guard(context, mode="AR")


def decide_ms(context: GuardContext) -> Decision:
    return _batch_guard(context, mode="MS")


def _untrusted_assignment(
    context: GuardContext,
) -> tuple[dict[str, Truth], dict[str, SignedObservation], int]:
    by_fact = _conditions_by_fact(context)
    assignment: dict[str, Truth] = {}
    observations: dict[str, SignedObservation] = {}
    reads = 0
    for fact_name, conditions in by_fact.items():
        try:
            observation = context.context_source.read(fact_name, context.now)
        except KeyError:
            for condition in conditions:
                assignment[condition_key(condition)] = Truth.UNKNOWN
            continue
        reads += 1
        observations[fact_name] = observation
        for condition in conditions:
            assignment[condition_key(condition)] = (
                Truth.TRUE if condition.holds(observation.value) else Truth.FALSE
            )
    return assignment, observations, reads


def decide_b0(context: GuardContext) -> Decision:
    return _terminal(DecisionStatus.EXECUTE, "unprotected", 0, {})


def decide_peek(context: GuardContext) -> Decision:
    assignment, _, reads = _untrusted_assignment(context)
    return _truth_decision(
        evaluate(_combined(context), assignment),
        now=context.now,
        deadline=context.deadline,
        reads=reads,
        evidence={},
        accepted="untrusted_reread",
    )


def decide_ver(context: GuardContext) -> Decision:
    assignment, observations, reads = _untrusted_assignment(context)
    for fact_name, observation in observations.items():
        cited = context.store.get(context.proposal.cites.get(fact_name, ""))
        if cited is None:
            return _terminal(DecisionStatus.REJECT, "unknown_record", reads, {})
        if not strict_json_equal(observation.value, cited.value):
            return _terminal(DecisionStatus.REJECT, "evidence_changed", reads, {})
    return _truth_decision(
        evaluate(_combined(context), assignment),
        now=context.now,
        deadline=context.deadline,
        reads=reads,
        evidence={},
        accepted="version_unchanged",
    )


def decide_fbs(context: GuardContext) -> Decision:
    """Arrival-time baseline with a conservative observed-variation estimate.

    A changed value cannot be certified by the old sample's variation, so the
    estimated lifetime for that fact is exhausted. A frozen packet has zero
    observed change and is incorrectly treated as current.
    """
    assignment, observations, reads = _untrusted_assignment(context)
    for fact_name, observation in observations.items():
        cited = context.store.get(context.proposal.cites.get(fact_name, ""))
        if cited is None:
            return _terminal(DecisionStatus.REJECT, "unknown_record", reads, {})
        if not strict_json_equal(observation.value, cited.value):
            return _terminal(
                DecisionStatus.REJECT,
                "estimated_variation_exceeded",
                reads,
                {},
                fact=fact_name,
            )
    return _truth_decision(
        evaluate(_combined(context), assignment),
        now=context.now,
        deadline=context.deadline,
        reads=reads,
        evidence={},
        accepted="arrival_fresh",
    )


def decide_phys(context: GuardContext) -> Decision:
    assignment, observations, reads = _untrusted_assignment(context)
    for fact_name, observation in observations.items():
        cited = context.store.get(context.proposal.cites.get(fact_name, ""))
        if cited is None:
            return _terminal(DecisionStatus.REJECT, "unknown_record", reads, {})
        fact = context.facts[fact_name]
        if (
            fact.kind is FactKind.CONTINUOUS
            and fact.max_rate is not None
            and isinstance(observation.value, (int, float))
            and not isinstance(observation.value, bool)
            and isinstance(cited.value, (int, float))
            and not isinstance(cited.value, bool)
        ):
            elapsed = max(0.0, observation.observed_at - cited.observed_at)
            if abs(float(observation.value) - float(cited.value)) > fact.max_rate * elapsed + 1e-9:
                return _terminal(
                    DecisionStatus.REJECT,
                    "physically_implausible",
                    reads,
                    {},
                    fact=fact_name,
                )
    return _truth_decision(
        evaluate(_combined(context), assignment),
        now=context.now,
        deadline=context.deadline,
        reads=reads,
        evidence={},
        accepted="physically_consistent",
    )


GUARDS = {
    "B0": decide_b0,
    "PEEK": decide_peek,
    "VER": decide_ver,
    "FBS": decide_fbs,
    "PHYS": decide_phys,
    "M": decide_m,
    "AR": decide_ar,
    "MS": decide_ms,
    "SL": decide_sl,
}


def decide(name: str, context: GuardContext) -> Decision:
    try:
        guard = GUARDS[name]
    except KeyError as error:
        raise ValueError(f"unknown guard: {name}") from error
    return guard(context)
