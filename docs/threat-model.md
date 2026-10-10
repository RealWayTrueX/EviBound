# EviBound Threat Model (v1.0, 2026-10-10)

Course requirement: COSC 723 repository minimum. This document is the single
source of truth for what the defense claims to cover and what it explicitly does
not. The Week-8 preregistration must reference this version or a newer dated one.

## 1. System under protection

A tool-using LLM agent (local Qwen2.5-7B-Instruct) controls simulated smart-home
actuators (light, fan) based on a user instruction and presence-sensor
observations. EviBound is a deterministic middleware between the agent's typed
JSON action proposals and the simulated device ledger. No real devices, accounts,
networks, or occupied spaces are involved (course safety boundary for
EffectShield-derived projects).

## 2. Assets (what can be harmed, in simulation)

- Physical-state safety: no actuator state may violate occupancy-dependent rules
  (e.g., light on while nobody is present; fan high without presence), the
  normalized load limit (light+fan <= 3), or legal transition sequences.
- Authorization integrity: only actuators listed in a task's `authorized` set may
  be written.
- Goal utility: benign tasks should still complete; a defense that refuses
  everything is a failure (course evaluation rule).

## 3. Attacker / fault model

The v1/v2 study models a **fault/injection at the observation channel**, not a
general adversary:

| # | Attack/fault | Mechanism in testbed | First seen |
|---|---|---|---|
| A1 | Tamper (fixed corruption) | The first observation's current presence record value is flipped to the opposite boolean | v1 |
| A2 | Replay (stale record) | The first observation replays the authentic historical record (opposite presence, t=0) unchanged | v1 |
| A3 | Unauthorized action | Task's goal or a plausible agent error path requires an actuator outside `authorized` | v2 (new) |

Properties of A1/A2: fixed, not adaptive; the attacker cannot write devices
directly, cannot forge collector records (ids/epochs are authentic or absent),
and cannot affect re-reads (subsequent reads always return the authentic current
record in every condition).

**Out of scope** (explicitly not claimed): adaptive or optimization-based
attacks, hidden instruction / prompt injection in tool data (EffectShield's
second attack; see Section 7), trained backdoors (BALD), real-device
authentication, continuous-time safety, multi-agent settings.

## 4. Trusted computing base (assumed uncompromised)

Per the implementation contract: authorization lists, policies/rules, the
collector, the immutable record store and its metadata, the clock, and the atomic
check-and-commit inside the guard. The oracle that scores traces is independent
of the guard and must not import guard predicates.

## 5. Defender capabilities and limits

The guard sees: the typed action proposal, the agent-supplied evidence object,
the trusted actuator ledger, and (condition M and diagnostics) the immutable
collector records with ids, epochs, and timestamps. The guard cannot see: the
task goal, oracle labels, actual hidden presence, or future states. An action
guard can only check attempted writes; it cannot correct an omitted action
(v1 finding: 9 perturbed-M empty-plan episodes never triggered a reread).

## 6. Security claims (falsifiable form, per course guidance)

Under the fault model in Section 3 and the v1 testbed: mechanism M reduces the
executed unsafe-effect rate relative to B0/B1/B2 while retaining clean goal
completion within five percentage points of B0, at measured query/latency cost.
The v1 frozen results support the safety half (0/72 perturbed unsafe under M vs
37.50% under B2) and refute, at the point estimate, the utility half
(70.83% vs 91.67%). v2 work must re-test both halves on a new frozen corpus.

## 7. Deferred attack family: hidden instruction in tool/device data

EffectShield's scope includes a hidden-instruction attack. EviBound's research
question targets observation integrity, and the planner's only untrusted text
inputs are the instruction and the observation payload, so a hidden-instruction
channel would require a new surface (e.g., free-text fields in device metadata).
Decision for v2: **not in the main comparison**; candidate stretch item after the
Week-12 freeze only if the utility question is resolved, because adding a second
attack family mid-semester would split the evaluation budget. Recorded here so
the omission is a decision, not an oversight.

## 8. Disclosure and tooling boundary

Development assistants (Codex/skills) and any decision-support API (e.g., Jev)
may support engineering, triage, and review. They never determine ground truth,
labels, guard decisions, or reported metrics; all of those remain deterministic
or human-validated (course rule; research contract).
