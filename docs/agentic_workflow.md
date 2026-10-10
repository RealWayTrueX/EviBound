# Agentic Workflow for EviBound

This document records which AI workflow tools improve this repository and which
would add complexity without improving the course evidence chain.

## Adopted Workflow

- `AGENTS.md` is the concise always-loaded scope and safety boundary.
- `docs/roadmap_week6.md` is the resumable work map and decision log.
- Existing `research`, `tdd`, `code-review`, and `diagnosing-bugs` skills cover
  evidence gathering, behavior-first changes, focused review, and root-cause loops.
- The `handoff` skill from `mattpocock/skills` is installed for compact
  cross-session continuation. Project state remains in repository artifacts and
  `docs/session_memory.md`; the temporary handoff is only a pointer bundle.
- Long model or experiment jobs use persistent terminal sessions and retain raw
  outputs under `/mnt/HDD-8T-0/evibound_yanke/`.
- Human-owned decisions are recorded before implementation when options change
  the threat model, metrics, labels, recovery budget, or safety semantics.

## External Tool Review

The reviewed source is `mattpocock/skills` at commit
`49dd158d1076134a641b33efb035946536778336`:
https://github.com/mattpocock/skills

- Use: `research`, `tdd`, `code-review`, `diagnosing-bugs`, and `handoff`.
- Deferred: `to-tickets`, `to-spec`, and `wayfinder`. This repository already has
  a compact roadmap and no configured issue tracker; installing their full task
  graph would duplicate project state.
- Deferred: `implement-spec` concurrency. Week 7 is a narrow audit and corpus
  package; parallel workers would add coordination cost without shortening the
  critical path.

The engineering-video guidance was checked against the original video metadata
and a full auto-caption transcript:
https://www.youtube.com/watch?v=c9nRxEy1kUY

The durable ideas adopted here are repeated prompts becoming focused skills,
decision records, one bounded review pass, controlled delegation, meaningful
tests only, persistent sessions, and hard tool guardrails. Disposable product
stack choices from the video are not imported.

## Jev Placement

TypeSafe describes Jev as a System One model that returns typed `Choice`, `Score`,
or `Noul` decisions with probabilities and confidence:
https://docs.typesafe.ai/introduction

Jev is useful only as optional secondary software support:

- triage human-review cards by likely ambiguity;
- confidence-route low-certainty labels or proposed tool calls to human review;
- compare a learned triage signal with deterministic checks after the corpus is
  human-reviewed.

It remains outside the ground-truth and enforcement path. The deterministic
oracle and human sign-off stay authoritative. No Jev request is part of Week 7,
and any paid API use requires explicit approval, data disclosure, pinned request
schemas, and a frozen comparison protocol.

## Evidence Discipline

AI assistance accelerates implementation and review, while the student owns the
research question, threat model, ground truth, safety boundary, accepted changes,
and interpretation. Every experimental claim must be regenerated from saved
machine-readable results rather than copied from an assistant response.
