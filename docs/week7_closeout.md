# EviBound Week-7 Closeout

Status: engineering package complete; human scenario review remains open. No
v2 model-in-the-loop evaluation was run before the Week-8 preregistration gate.

## Week-7 Outcome

The active research contract asks whether an evidence-bound runtime mediator can
reduce executed unsafe effects under observation tamper and stale replay while
preserving useful automation. Week 7 completes the core mechanism, attack/defense
design, draft attack corpus, invariant checks, review workflow, and environment
manifest needed to prepare a Week-8 metric and pilot freeze.

## Completed Evidence

- Repository contract and scope are explicit in `AGENTS.md` and
  `docs/research-contract.md`.
- `docs/threat-model.md` covers A1 tamper, A2 replay, A3 unauthorized action,
  trusted components, and exclusions.
- `docs/design_v2_attack_defense.md` keeps the six-rule guard unchanged, records
  rule-2 redundancy, equal recovery budgets, omission accounting, and A3 utility
  semantics.
- `data/scenarios_v2/` contains DRAFT dev16, pilot16, and test24 tasks with
  disjoint family-conditioned structures, balanced tamper/replay assignment, and
  authorization-negative families. Both clean and perturbed branches require
  1-3 writes. Shared physical structures across family labels are recorded with
  `physical_structure_id` and used as analysis clusters.
- `data/scenarios_v2/check_report.json` reports zero machine-check errors and
  R1-R6 coverage in every split.
- `reviews/v2/` contains 56 review cards and a 44-row required checklist covering
  all test tasks, all A3 tasks, and a deterministic dev/pilot sample.
- The independent oracle now distinguishes full-goal completion, safe partial
  completion, safe utility completion, and safe abstention for A3 tasks.
- The runner records empty-plan flags and per-episode recovery-budget consumption
  while preserving one reread/resubmission and three successful-write limits.
- `artifacts/environment_v2.json` records OS, CPU, memory, two RTX 4090 GPUs,
  driver 580.178.04, CUDA-toolchain/runtime facts, Python packages, and planned
  model precision without loading model weights.
- `artifacts/week7_validation.json` and `.log` record the no-model validation run:
  32 tests pass, corpus hashes match, checker errors are zero, and the package is
  `pass_pending_human_review`.

## AI and Agentic Tooling

`docs/agentic_workflow.md` records a selective integration rather than adding
every available tool. Existing research, TDD, code-review, and bug-diagnosis
skills cover the main loop; the exact `handoff` skill from `mattpocock/skills`
was installed for cross-session continuity. Ticket graphs and parallel
implementation skills are deferred because the repository already has a compact
roadmap and the current work has a narrow critical path.

The agentic-engineering video contributed four durable practices: turn repeated
prompts into focused skills, record why decisions were made, use one bounded
review pass, and control delegation and dangerous-tool permissions. Jev is
documented only as optional secondary triage with confidence routing. It is not
ground truth, not a guard, and was not called.

## Limits and Next Gate

- The 44 required human decisions in `reviews/v2/checklist.csv` are still blank.
  Machine consistency is not human label validation.
- Some exact device-state/goal tuples recur under different family instructions;
  those are one physical cluster, not independent evidence. The analysis groups
  uncertainty by `physical_structure_id` when present.
- Hidden instruction injection remains outside v2 so the experiment keeps one
  primary observation-integrity question.
- Empty plans remain failures; an explicit-justification planner condition is
  reserved for a preregistered v3 comparison.
- No v2 claims, tables, or model results exist yet. Week 8 must freeze primary
  metrics and pilot protocol before any model run.

## Week-8 Handoff

1. Complete `docs/review_guide_v2.md` review and run
   `python3 scripts/build_review_bundle.py --signoff "<reviewer>"`.
2. Resolve every `fix` or `reject` task by regeneration and re-review.
3. Preregister metrics, seeds, prompts, conditions, recovery accounting, and
   analysis contrasts.
4. Freeze hashes only after human sign-off, then run held-out pilot tasks.
