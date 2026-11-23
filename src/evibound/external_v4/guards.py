"""Implementations of the v4 guards and comparison baselines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .expressions import evaluate, read_priority
from .lifetime import LifetimePolicy, assign
from .model import (
    Condition,
    Decision,
    DecisionStatus,
    Expression,
    Fact,
    FactKind,
    Proposal,
    SignedObservation,
    Truth,
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
    fixed_delta: float = 2.0
    fresh_reading_available: bool = True
    trace: list[dict[str, Any]] = field(default_factory=list)


def _dep_conditions(context: GuardContext) -> tuple[Condition, ...]:
    return conditions_in(context.static_rules) + conditions_in(context.proposal.requires)


def _dep_facts(context: GuardContext) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for condition in _dep_conditions(context):
        if condition.fact not in seen:
            seen.add(condition.fact)
            ordered.append(condition.fact)
    return ordered


def _combined(context: GuardContext):
    from .model import AllOf

    return AllOf((context.static_rules, context.proposal.requires))


def _initial_assignment(context: GuardContext) -> tuple[dict[str, Truth], dict[str, str], str | None]:
    assignment: dict[str, Truth] = {}
    evidence: dict[str, str] = {}
    for condition in _dep_conditions(context):
        fact = context.facts[condition.fact]
        record_id = context.proposal.cites.get(condition.fact)
        if not record_id:
            return assignment, evidence, "missing_citation"
        record = context.store.get(record_id)
        if record is None or record.fact != condition.fact:
            return assignment, evidence, "unknown_record"
        truth, detail = assign(
            fact=fact,
            observation=record,
            condition=condition,
            now=context.now,
            policy=context.policy,
        )
        assignment[condition.fact] = truth
        evidence[condition.fact] = record.record_id
        context.trace.append(
            {"stage": "assign_cited", "fact": condition.fact, "truth": truth.value, **detail}
        )
    return assignment, evidence, None


def _terminal(status: DecisionStatus, reason: str, reads: int, evidence: dict[str, str], **details: Any) -> Decision:
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
        status = DecisionStatus.DEFER if now < deadline else DecisionStatus.REJECT
        reason = false_reason if status is DecisionStatus.DEFER else "deadline_expired"
        return _terminal(status, reason, reads, evidence)
    return _terminal(DecisionStatus.REJECT, unknown_reason, reads, evidence)


def decide_sl(context: GuardContext) -> Decision:
    assignment, evidence, error = _initial_assignment(context)
    if error is not None:
        return _terminal(DecisionStatus.REJECT, error, 0, evidence)
    expression = _combined(context)
    attempted: set[str] = set()
    reads = 0
    failures: dict[str, str] = {}
    while True:
        truth = evaluate(expression, assignment)
        if truth is not Truth.UNKNOWN:
            break
        candidates = [
            item
            for item in read_priority(expression, assignment)
            if item.fact not in attempted
        ]
        if not candidates:
            break
        progressed = False
        for condition in candidates:
            fact_name = condition.fact
            attempted.add(fact_name)
            try:
                observation = context.trusted_source.read(fact_name, context.now)
            except KeyError:
                failures[fact_name] = "unavailable"
                continue
            reads += 1
            ingested = context.store.ingest(observation, now=context.now)
            if not ingested.accepted:
                failures[fact_name] = ingested.reason
                context.trace.append(
                    {
                        "stage": "reread",
                        "fact": fact_name,
                        "accepted": False,
                        "reason": ingested.reason,
                    }
                )
                continue
            truth_value, detail = assign(
                fact=context.facts[fact_name],
                observation=observation,
                condition=condition,
                now=context.now,
                policy=context.policy,
            )
            assignment[fact_name] = truth_value
            evidence[fact_name] = observation.record_id
            context.trace.append(
                {
                    "stage": "reread",
                    "fact": fact_name,
                    "accepted": True,
                    "truth": truth_value.value,
                    **detail,
                }
            )
            progressed = progressed or truth_value is not Truth.UNKNOWN
            break
        if not progressed:
            continue
    final_truth = evaluate(expression, assignment)
    decision = _truth_decision(
        final_truth,
        now=context.now,
        deadline=context.deadline,
        reads=reads,
        evidence=evidence,
        unknown_reason="stale_evidence",
    )
    return Decision(
        status=decision.status,
        reason_code=decision.reason_code,
        reads=decision.reads,
        evidence=decision.evidence,
        details={**decision.details, "read_failures": failures},
    )


def _fixed_assign(
    fact: Fact,
    condition: Condition,
    observation: SignedObservation,
    *,
    now: float,
    delta: float,
) -> Truth:
    del fact
    age = now - observation.observed_at
    if age < 0 or age > delta:
        return Truth.UNKNOWN
    if condition.holds(observation.value):
        return Truth.TRUE
    return Truth.FALSE if age <= 1e-12 else Truth.UNKNOWN


def _batch_guard(
    context: GuardContext,
    *,
    mode: str,
) -> Decision:
    assignment: dict[str, Truth] = {}
    evidence: dict[str, str] = {}
    failures: dict[str, str] = {}
    reads = 0

    if mode in ("M", "MS"):
        assignment, evidence, error = _initial_assignment(context)
        if error is not None:
            return _terminal(DecisionStatus.REJECT, error, 0, evidence)
        conditions_by_fact: dict[str, Condition] = {}
        for condition in _dep_conditions(context):
            conditions_by_fact.setdefault(condition.fact, condition)
        reread = [
            fact
            for fact, truth in assignment.items()
            if truth is Truth.UNKNOWN
        ] if mode == "MS" else list(conditions_by_fact)
        if mode == "M":
            reread = [
                fact
                for fact in conditions_by_fact
                if assignment.get(fact) is not Truth.TRUE
            ]
    else:
        conditions_by_fact = {}
        for condition in _dep_conditions(context):
            conditions_by_fact.setdefault(condition.fact, condition)
        reread = list(conditions_by_fact)

    for fact_name in reread:
        condition = conditions_by_fact[fact_name]
        try:
            observation = context.trusted_source.read(fact_name, context.now)
        except KeyError:
            failures[fact_name] = "unavailable"
            continue
        reads += 1
        if mode in ("M", "MS"):
            truth = _fixed_assign(
                context.facts[fact_name],
                condition,
                observation,
                now=context.now,
                delta=context.fixed_delta,
            )
        else:
            ingested = context.store.ingest(observation, now=context.now)
            if not ingested.accepted:
                failures[fact_name] = ingested.reason
                truth = Truth.UNKNOWN
            else:
                truth, detail = assign(
                    fact=context.facts[fact_name],
                    observation=observation,
                    condition=condition,
                    now=context.now,
                    policy=context.policy,
                )
                evidence[fact_name] = observation.record_id
                context.trace.append(
                    {
                        "stage": "batch_reread",
                        "fact": fact_name,
                        "truth": truth.value,
                        **detail,
                    }
                )
        assignment[fact_name] = truth
        if truth is Truth.TRUE:
            evidence[fact_name] = observation.record_id

    truth = evaluate(_combined(context), assignment)
    if failures and truth is Truth.UNKNOWN:
        return _terminal(
            DecisionStatus.REJECT, "stale_evidence", reads, evidence, failures=failures
        )
    return _truth_decision(
        truth,
        now=context.now,
        deadline=context.deadline,
        reads=reads,
        evidence=evidence,
        unknown_reason="stale_evidence",
    )


def decide_m(context: GuardContext) -> Decision:
    return _batch_guard(context, mode="M")


def decide_ar(context: GuardContext) -> Decision:
    return _batch_guard(context, mode="AR")


def decide_ms(context: GuardContext) -> Decision:
    return _batch_guard(context, mode="MS")


def _untrusted_assignment(context: GuardContext) -> tuple[dict[str, Truth], int]:
    assignment: dict[str, Truth] = {}
    reads = 0
    for condition in _dep_conditions(context):
        try:
            observation = context.context_source.read(condition.fact, context.now)
        except KeyError:
            assignment[condition.fact] = Truth.UNKNOWN
            continue
        reads += 1
        assignment[condition.fact] = (
            Truth.TRUE if condition.holds(observation.value) else Truth.FALSE
        )
    return assignment, reads


def decide_b0(context: GuardContext) -> Decision:
    return _terminal(DecisionStatus.EXECUTE, "unprotected", 0, {})


def decide_peek(context: GuardContext) -> Decision:
    assignment, reads = _untrusted_assignment(context)
    return _truth_decision(
        evaluate(_combined(context), assignment),
        now=context.now,
        deadline=context.deadline,
        reads=reads,
        evidence={},
        accepted="untrusted_reread",
    )


def decide_ver(context: GuardContext) -> Decision:
    assignment: dict[str, Truth] = {}
    reads = 0
    for condition in _dep_conditions(context):
        cited = context.store.get(context.proposal.cites.get(condition.fact, ""))
        if cited is None:
            return _terminal(DecisionStatus.REJECT, "unknown_record", reads, {})
        try:
            observed = context.context_source.read(condition.fact, context.now)
        except KeyError:
            assignment[condition.fact] = Truth.UNKNOWN
            continue
        reads += 1
        if not strict_json_equal(observed.value, cited.value):
            return _terminal(DecisionStatus.REJECT, "evidence_changed", reads, {})
        assignment[condition.fact] = (
            Truth.TRUE if condition.holds(observed.value) else Truth.FALSE
        )
    return _truth_decision(
        evaluate(_combined(context), assignment),
        now=context.now,
        deadline=context.deadline,
        reads=reads,
        evidence={},
        accepted="version_unchanged",
    )


def decide_fbs(context: GuardContext) -> Decision:
    # The FBS baseline estimates freshness from arrival/variation. A frozen
    # packet looks perfectly unchanged and is therefore treated as current.
    assignment, reads = _untrusted_assignment(context)
    return _truth_decision(
        evaluate(_combined(context), assignment),
        now=context.now,
        deadline=context.deadline,
        reads=reads,
        evidence={},
        accepted="arrival_fresh",
    )


def decide_phys(context: GuardContext) -> Decision:
    assignment: dict[str, Truth] = {}
    reads = 0
    for condition in _dep_conditions(context):
        fact = context.facts[condition.fact]
        cited = context.store.get(context.proposal.cites.get(condition.fact, ""))
        if cited is None:
            return _terminal(DecisionStatus.REJECT, "unknown_record", reads, {})
        try:
            observed = context.context_source.read(condition.fact, context.now)
        except KeyError:
            assignment[condition.fact] = Truth.UNKNOWN
            continue
        reads += 1
        if (
            fact.kind is FactKind.CONTINUOUS
            and fact.max_rate is not None
            and isinstance(observed.value, (int, float))
            and not isinstance(observed.value, bool)
            and isinstance(cited.value, (int, float))
            and not isinstance(cited.value, bool)
        ):
            elapsed = max(0.0, observed.observed_at - cited.observed_at)
            max_move = fact.max_rate * elapsed
            if abs(float(observed.value) - float(cited.value)) > max_move + 1e-9:
                return _terminal(
                    DecisionStatus.REJECT, "physically_implausible", reads, {}
                )
        assignment[condition.fact] = (
            Truth.TRUE if condition.holds(observed.value) else Truth.FALSE
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
