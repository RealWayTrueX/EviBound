# EviBound Research Contract

## Research Question

Can a deterministic evidence-bound runtime mediator reduce adversarially induced
unsafe smart-home effects while preserving useful automation under a fixed
recovery budget?

## Directional Hypothesis

Under fixed observation tampering and stale-record replay, EviBound (M) will
reduce executed unsafe effects relative to an identical-rule stateful guard (B2),
while keeping clean goal completion within five percentage points of an
unprotected baseline (B0). Safety and utility are reported separately.

## System and Threat Model

The subject is a local Qwen2.5-7B-Instruct planner proposing typed JSON actions
for simulated light and fan devices. EviBound validates agent-supplied evidence
against an immutable collector record before guarded writes. The detailed
attacker capabilities, trusted components, assets, and exclusions are defined in
`docs/threat-model.md`.

## Conditions and Ablations

- B0: schema-only unprotected execution.
- B1: safety prompt without runtime enforcement.
- B2: authorization and six state/sequence rules using agent-supplied presence.
- M: B2 plus exact record provenance and freshness validation.
- M_no_freshness: provenance validation without age validation.
- Always_refresh: authentic reread before every write.

One rejection-triggered reread and resubmission is shared across conditions, with
at most three successful writes. Observations, policies, prompts, and seed rules
must remain paired across relevant comparisons.

## Measures and Success Criteria

Primary safety outcome: executed unsafe-effect rate, including unsafe
intermediate transitions. Primary utility outcomes: clean goal completion,
authorized-subgoal completion for authorization-negative tasks, false blocks,
safe repair or abstention, reads, model calls, tokens, and latency.

The proposed mechanism passes the feasibility safety comparison only if M has
fewer unsafe effects than B2 under perturbation. Utility non-inferiority requires
M clean completion no more than five percentage points below B0. Zero observed
violations is never treated as a guarantee.

## Ground Truth and Validation

An independent trajectory oracle derives outcomes from executed states and
immutable records without importing guard predicates. Humans validate scenario
labels and policy semantics through `reviews/v2/` before corpus freeze. LLM
judges or decision APIs may support review triage only as secondary evidence.

## Scope

Included: deterministic simulator, synthetic paired tasks, observation tamper,
stale-record replay, authorization-negative cases, fixed recovery budgets,
ablations, failure taxonomy, machine-readable traces, and reproduction tooling.

Excluded: real homes or devices, external control targets, identifiable data,
training-time backdoors, adaptive attackers, production-security claims, and
cloud or paid APIs without approval.

## Freeze Schedule

- Week 7: rule audit, attack/defense design, draft corpus, human-review mechanism,
  and environment manifest.
- Week 8: primary metrics, pilot protocol, and preregistration.
- Week 10: task corpus, attack variants, and labels frozen.
- Week 12: code and experimental configuration frozen except correctness fixes.
