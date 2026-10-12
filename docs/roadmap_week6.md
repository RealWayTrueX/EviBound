# EviBound Week-6/7 Execution Roadmap (living document)

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
- [x] C1. `docs/design_v2_dataset.md` - schema v2, structural families, perturbation
      decoupled from family, authorization-negative tasks, split sizes, storage layout,
      versioning/hashing, draft->freeze lifecycle
- [x] C2. `scripts/generate_scenarios_v2.py` + draft corpus under `data/scenarios_v2/`
- [x] C3. `scripts/check_scenarios_v2.py` - machine pre-checks: schema, initial-state
      legality at both event boundaries, every clean goal needs >=1 write, BFS
      solvability, perturbation branch-flip probe, oracle label self-consistency

### D. Human inspection mechanism
- [x] D1. `scripts/build_review_bundle.py` - per-task human-readable review cards
      (Markdown with explicit anchors) into `reviews/v2/`
- [x] D2. `reviews/v2/checklist.csv` + `docs/review_guide_v2.md` - how a human reviews,
      sampling plan (100% of test + all authorization-negative tasks), sign-off
      recording back into `data/scenarios_v2/manifest.json`
- [x] D3. Human review completed and signed off (owner: corpus owner); 44/44 required
      rows approved with zero open items

### E. Close-out
- [x] E1. Environment manifest completion (CPU/OS/CUDA/driver/runtime/precision fields
      flagged missing in implementation_notes.md) - collect current machine facts
- [x] E2. Roadmap updated, session summary reported to user

### F. Agentic workflow and repository contract
- [x] F1. `AGENTS.md` + `docs/research-contract.md` - repository minimum and
      always-loaded research/safety boundary
- [x] F2. `docs/agentic_workflow.md` - selective skills adoption, controlled
      delegation, Jev placement, and evidence discipline
- [x] F3. A3 oracle utility metrics + recovery/empty-plan instrumentation tests

### G. Week-8 preregistration and v2 pilot
- [x] G1. Freeze corpus, prompts, model revision, conditions, seeds, metrics,
      analysis contrasts, and decision rules before model execution
- [x] G2. Run the official 18-episode dev smoke and the complete 864-episode
      held-out pilot matrix in persistent model sessions
- [x] G3. Independently rescore all episodes and retain failures, empty plans,
      recovery use, cost, and physical-cluster uncertainty
- [x] G4. Record the confirmatory decision honestly; keep the v2 test split
      untouched for the later main evaluation

### H. Formal v2 test and bilingual report
- [x] H1. Freeze the unchanged formal test matrix before any test model output
- [x] H2. Run all 1,296 test episodes with complete raw trace retention
- [x] H3. Independently rescore, audit failures/recovery/cost, and apply the
      preregistered safety and utility decisions
- [x] H4. Produce the self-contained bilingual HTML experiment report and
      machine-readable result record

### I. Week 11-12 recovery study (v3)
- [x] I1. Retrospective failure taxonomy of retained v2 traces
      (`scripts/week11_failure_taxonomy.py` -> `artifacts/week11_v2_failure_taxonomy.json`)
- [x] I2. Goal-agnostic recovery interface and eight equal-budget conditions
      (`src/evibound/recovery.py`, `src/evibound/runner_v3.py`, `tests/test_recovery_v3.py`)
- [x] I3. Fresh v3 corpus: dev 12 / holdout 32, no v2 physical structure
      (`scripts/generate_scenarios_v3.py`, `scripts/check_scenarios_v3.py`)
- [x] I4. Review bundle, DRAFT preregistration, freeze/verify gate
      (`scripts/build_review_bundle_v3.py`, `docs/week11_v3_preregistration.md`,
      `scripts/freeze_v3_prereg.py`)
- [~] I5. Unattended GPU launcher (`scripts/wait_gpu_then_run_v3.sh`, tmux
      `evibound_v3`): dev is complete; holdout waits for the refreshed I6 freeze
- [~] I6. Human review is complete for 77 REQUIRED cards; regenerate and verify
      the preregistration freeze after the later review/corpus changes, using
      `python3 scripts/freeze_v3_prereg.py --approve "<reviewer-name>"`
- [ ] I7. Holdout run, independent rescoring, bilingual report, decisions recorded

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

- 2026-10-10: C1-C3 done. DRAFT v2 corpus generated (dev16/pilot16/test24);
  independent checker passes 9/9 check groups (rule coverage R1-R6 every split,
  perturbation 50:50, structures disjoint, A3 semantics valid). Iteration log:
  fixed stale-context bug (all splits got dev contexts), perturbation rebalance
  guard inversion, A3 subgoal validator/checker asymmetry, cross-family
  concrete-structure collisions (economy==reading==gentle tuples) via
  split-level exclusion + coverage-repair selection.

- 2026-10-10: D1-D2 and E1-E2 done. Review bundle generated with 44 REQUIRED
  rows; `artifacts/environment_v2.json` records the current two-GPU machine.
  The independent oracle now reports `safe_partial_completion`,
  `safe_utility_completion`, and zero-write `safe_abstention`; runner output
  records empty-plan and recovery-budget fields. `artifacts/week7_validation.json`
  is `pass_pending_human_review` after 32 passing tests and zero checker errors.

- 2026-10-10: Selective agentic workflow adopted in `docs/agentic_workflow.md`.
  The missing `handoff` skill from `mattpocock/skills` was installed; ticket-graph
  and parallel-implementation skills remain deferred. Jev stays optional
  secondary triage and is outside ground truth, enforcement, and Week-7 calls.

- 2026-10-10: corpus audit found eight zero-write perturbation branches, which
  made those attacks action-vacuous. Candidate generation now rejects any branch
  needing 0 writes, the checker enforces 1-3 writes on both branches, and the
  family goal registry gained equivalent partial-goal variants under the fixed
  initial constraints to retain 56
  family-conditioned task structures. Exact physical tuples shared across family
  labels are explicitly clustered by `physical_structure_id`. Regenerated corpus
  and review bundle pass.

- 2026-10-10: Week-8 gate completed. The corpus owner approved all 44 required review rows.
  `artifacts/week8_preregistration.json` and
  `artifacts/week8_protocol_freeze.json` froze the v2 pilot protocol before
  output. The official smoke passed 18/18 episodes and the pilot completed
  864/864 unique episodes with zero parse failures, false blocks, duplicate IDs,
  trace inconsistencies, or oracle disagreements.

- 2026-10-10: preregistered pilot decision is joint feasibility **not
  supported**. Safety B2−M on perturbed episodes was +20.0 pp [+0.0, +40.0]
  (inconclusive under the strict rule), while clean utility M−B0 was -20.0 pp
  [-40.0, -4.4] (unsupported against the -5 pp margin). Raw rates were B2
  12/48 versus M 0/48 perturbed unsafe, and B0 36/48 versus M 27/48 clean goal
  completion. See `docs/week8_pilot_closeout.md`; the v2 test split is untouched.

- 2026-10-10: formal v2 test protocol frozen at 12:52:33Z with no changes from
  the pilot. The complete 24-task, six-condition, three-variant, three-seed
  matrix produced 1,296/1,296 unique episodes with zero parse failures, false
  blocks, duplicate IDs, trace inconsistencies, or oracle disagreements.

- 2026-10-10: formal test supports safety but not joint feasibility. Perturbed
  unsafe effects were B2 30/72 versus M 0/72; cluster effect B2−M was +36.4 pp
  [+18.2,+59.1]. Clean full-goal completion was B0 53/72 versus M 44/72;
  cluster effect M−B0 was -13.6 pp [-27.3,0.0], failing the -5 pp margin. See
  `reports/week8_v2_formal_experiment_bilingual.html` and
  `artifacts/week8_main_results.json`.

- 2026-10-11: public repository sync scope finalized. Local-only privacy and
  human-communication materials (`Background_dont_push_to_github/`, `reports/`,
  `reviews/`, `docs/session_memory.md`, and the student-identifying contract text)
  remain untracked; code, datasets, tests, protocols, and machine-readable
  evidence are prepared for publication.

- 2026-10-11: the publication commit was created locally and all 33 tests plus
  the v2 corpus checker passed. GitHub push is pending because this execution
  environment has no configured HTTPS token or SSH private key.

- 2026-10-11: Week 11-12 recovery package built. Retained v2 traces show the
  clean utility gap is planner recovery, not guard error: M clean test misses
  were 7 empty first plans, 9 failed repairs after correct rejections, 3
  incomplete recoveries and 9 A3 full-goal misses; 27/72 M perturbed episodes
  resubmitted an empty plan after a correct evidence rejection. v3 adds rule
  explanations and empty-plan confirmation under the unchanged budget, on a
  physically fresh 32-task holdout. 42 tests and both corpus checkers pass. The
  GPU launcher waits for the StreamVLN G1 runs to release a GPU; holdout stays
  gated on human review and the preregistration freeze.
- 2026-10-11: human-facing documentation pass at the corpus owner's request. Added
  `docs/reading_guide.md` (bilingual glossary: levels off/1/2, rule reasons,
  condition codes, metrics, statistics terms, document map, confusing spots in
  frozen docs) and `docs/threat_model_real_world.md` (how tamper/replay/A3 arise
  in real homes, out-of-scope cases). `threat-model.md` stays byte-identical
  because it is sealed in the Week-8 freeze; the companion is added to the v3
  freeze list instead. README rewritten bilingual; v1 dataset card and v1 demo
  outline carry scope banners; v3 prereg gained a plain-language summary; v3
  reports gained condition/metric/failure legends; v3 family labels made
  neutral (A3 families reuse the v2 scene names).
- 2026-10-11: at the corpus owner's request (before the v3 freeze) the v3 corpus was
  expanded: holdout 72 tasks on 36 fresh physical structures, dev 12, in a
  4 x 3 design of observation modality (presence flag, motion timer, camera
  caption, multi-sensor) x request language (explicit, everyday, named scene),
  with English/Chinese labels per task. New modules `backend_v3.py`,
  `oracle_v3.py`, `planner_v3.py` leave frozen v1/v2 code untouched; the
  presence-flag world is unit-tested against the v2 World. The earlier 37-row
  sign-off is superseded; the expanded 77-card review is now complete.

- 2026-10-12: v3 dev completed 864/864 exploratory episodes with zero parse
  failures, trace inconsistencies, invalid initial episodes, false blocks,
  empty plans, or oracle disagreements. S1 safety is supported, while R1
  recovery gain and U1 utility non-inferiority are unsupported; joint
  feasibility is not supported. Holdout has not started. The preserved 37-row
  freeze is marked superseded because later review/corpus/code changes produce
  hash mismatches; a fresh preregistration freeze is required before holdout.
