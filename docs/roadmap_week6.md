# EviBound Week-6 Execution Roadmap (living document)

Status legend: `[ ]` pending · `[~]` in progress · `[x]` done · `(!)` needs human decision

This file is the resumable anchor for the Week-6 work package. Every work session
must update the checkboxes and the Progress Log before stopping. Derived from the
COSC 723 syllabus (15-week plan, repository minimum, evaluation rules) and the
submitted research contract (Weeks 5-7: rule audit + environment manifest;
Week 8: preregistration; Weeks 9-10: freeze new corpus + main runs).

Frozen-boundary rules (non-negotiable):
- `data/scenarios/`, `reports/`, `artifacts/` (v1, 2026-09-23) are immutable.
- No model-in-the-loop experiment runs before Week-8 preregistration.
- New corpus is authored under `data/scenarios_v2/` as DRAFT until human review
  and preregistration freeze it.

## Work items

### A. Orientation and planning
- [x] A1. Re-read syllabus, research contract, v1 machinery (backend/oracle/contract docs)
- [x] A2. Create this roadmap

### B. Attack/defense design (docs only)
- [x] B1. `docs/threat-model.md` - attacker, capabilities, assets, trust assumptions,
      in/out of scope (course repository-minimum requirement)
- [x] B2. `docs/design_v2_attack_defense.md` - v2 attack families (tamper, replay,
      authorization-negative), defense conditions carried over from v1, recovery-budget
      equalization, omission (empty-plan) handling, utility-gap remediation tied to
      rule audit (rule 2 implied by rules 1+6)

### C. Dataset v2 (authoring + storage + machine checks)
- [~] C1. `docs/design_v2_dataset.md` - schema v2, structural families, perturbation
      decoupled from family, authorization-negative tasks, split sizes, storage layout,
      versioning/hashing, draft->freeze lifecycle
- [ ] C2. `scripts/generate_scenarios_v2.py` + draft corpus under `data/scenarios_v2/`
- [ ] C3. `scripts/check_scenarios_v2.py` - machine pre-checks: schema, initial-state
      legality at both event boundaries, every clean goal needs >=1 write, BFS
      solvability, perturbation branch-flip probe, oracle label self-consistency

### D. Human inspection mechanism
- [ ] D1. `scripts/build_review_bundle.py` - per-task human-readable review cards
      (Markdown with explicit anchors) into `reviews/v2/`
- [ ] D2. `reviews/v2/checklist.csv` + `docs/review_guide_v2.md` - how a human reviews,
      sampling plan (100% of test + all authorization-negative tasks), sign-off
      recording back into `data/scenarios_v2/manifest.json`
- [ ] D3. (!) Human actually reviews and signs off (owner: Xin Li)

### E. Close-out
- [ ] E1. Environment manifest completion (CPU/OS/CUDA/driver/runtime/precision fields
      flagged missing in implementation_notes.md) - collect current machine facts
- [ ] E2. Roadmap updated, session summary reported to user

## Progress Log

- 2026-10-10: A1-A2 done. v1 confounds reconfirmed from current files: perturbation
  type tied 1:1 to family (tamper<->reading/gentle_comfort/bright_ventilation;
  replay<->bright_work/strong_ventilation/economy); all v1 tasks authorize both
  actuators (authorization-negative evidence only from component tests); rule 2
  implied by rules 1+6; 9 empty-plan perturbed-M episodes never triggered reread;
  utility gap 20.83pp vs 5pp target.

- 2026-10-10: B1 threat-model.md and B2 design_v2_attack_defense.md written.
  Key open decisions flagged (!): A3 safe_abstention metric, hidden-instruction
  deferral, rule-2 redundancy handling, empty-plan v3 policy.
