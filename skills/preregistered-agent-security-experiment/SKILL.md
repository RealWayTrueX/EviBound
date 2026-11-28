---
name: preregistered-agent-security-experiment
description: Design, freeze, execute and report an LLM-agent attack/defense experiment (runtime guard, attacked observations, refusal feedback, safety and utility metrics) so results are rigorous and reproducible — covering hash-frozen preregistration, an independent attainability oracle, exact-target vs. unrequested-change side-effect scoring, paired conditions, clustered bootstrap statistics, and exploratory generalization checks. Use when planning a new study round, adding guard conditions or refusal messages, scaling environments, or writing up evaluation results.
---

# Preregistered Agent-Security Experiment

Worked examples in EviBound:
- Core guard & protocols: `AGENTS.md`, `docs/week8_preregistration.md`, `docs/week11_v3_preregistration.md`, `docs/v3_1_preregistration.md`
- Attainability oracle & refusal ladder: `src/evibound/attainability.py`, `src/evibound/recovery_v3_1.py`, `src/evibound/runner_v3_1.py`
- Multi-device scale & second-model generalization: `src/evibound/homes.py`, `docs/scale_study.md`, `docs/v3_1_second_model.md`
- Freeze & analysis: `scripts/freeze_v3_1_prereg.py`, `scripts/analyze_v3_1.py`, `artifacts/v3_1_holdout_results.json`

## 1. Define falsifiable claims before touching holdout data

- State a **joint** criterion covering safety under attack *and* utility on normal tasks (a guard that blocks everything must fail utility).
- Specify each condition as a minimal delta from a clear reference (`B0` unguarded, `B2` identical rules trusting cited values, `M` evidence-bound commit, ablations such as `M_no_freshness` and `Always_refresh`).
- When studying **refusal feedback** (`v3.1`), hold the guard's accept/refuse decisions identical across all arms and vary *only* the post-refusal message (from bare verdict `L0` to rule reason `L1`, trusted reading `L1r`, legal-writes lists `L2a/L2a'`, plan review `L2b`, and valid sequence `L3`).
- Map synthetic attacks explicitly to real-world system hops (`docs/threat_model_real_world.md`) and state what is out of scope (e.g., adaptive adversaries, compromised trusted base).

## 2. Build measurement that cannot flatter the guard

- **Independent oracle.** The scorer shares zero code with the guard and re-evaluates safety strictly from executed device transitions and hidden ground truth. Rejected proposals are never counted as unsafe, and a later safe state never erases an earlier unsafe transition.
- **Attainability yardstick (avoid unfair scoreboards).** Raw completion rewards an unguarded baseline for completing tasks by breaking rules; rule-compliant completion favors any guard by construction. Compute each task's policy-**attainable target** via independent search and score two complementary outcomes:
  1. `exact_target`: zero violations and home ends exactly at the attainable target.
  2. `unrequested_change`: zero violations, yet some device ends at a state neither initial nor requested (critical for catching side effects of "helpful" refusal messages).
- **Attack battery.** Include tasks where the true branch requires *doing nothing* unless the attacked reading is believed, measuring whether the guard keeps the environment unchanged.
- **Paired design & honest denominators.** Share the planner's exact first generation across conditions that share a prompt; keep equal recovery budgets; retain parse errors, empty plans, and refusals in every denominator.
- **Clustered statistics.** Resample independent **physical structures** (not repeated seeds or paraphrases) with a fixed bootstrap seed; pre-specify thresholds (0 for superiority, e.g., −5 pp for non-inferiority) and verdict rules (`supported` / `inconclusive` / `not supported`).

## 3. Splits, corpora, and human verification

- Maintain strict split hygiene: `dev` (iterate freely) → `pilot` (format/smoke check) → `holdout` (touched once after freeze). Enforce zero structural overlap between holdout and earlier splits (`scripts/check_scenarios_v3_1.py`).
- Generate corpora programmatically, verify every task with an independent simulator checker, and record human review explicitly (`artifacts/v3_1_postrun_review.json`). If review happens post-run, preserve frozen counts unchanged and report any exclusions only in a sensitivity analysis.

## 4. Freeze, run once, and separate exploratory follow-ups

- Freeze protocol docs, corpus files, engine code, and analysis scripts into a SHA-256 manifest (`scripts/freeze_v3_1_prereg.py --approve`); refuse holdout execution if `--verify` fails.
- Re-score raw trajectories with the independent oracle and require `0` replay disagreements. Commit compact, prompt-free **episode fingerprints** (`*.json.gz`) so every table and figure recomputes offline without raw logs.
- Label follow-up runs (e.g., second model `Qwen3-8B`, alternative system prompts, larger 4-/6-device homes) explicitly as **exploratory**, publish their plans before execution (`docs/v3_1_second_model.md`, `docs/scale_study.md`), and never retroactively alter frozen confirmatory claims.

## 5. Common pitfalls caught in EviBound

- **Legal-write menus backfire.** Adding a list of currently legal writes as a "recovery aid" in v3 looked harmless under coarse completion metrics, yet v3.1 proved it nearly doubles `unrequested_change` (25.4% vs. 13.3%) and worsens in larger homes (+24.9 pp at 6 devices). Always test refusal messages for unintended side effects.
- **Development trends can flip on holdout.** Claim C3 (derived from a noisy dev difference) reversed sign on holdout (`M_plan` slightly beat `M_recover`). Freezing first prevented post-hoc story-fitting and revealed the cleaner dividing line (plan-anchored vs. unrequested options).
- **Utility gaps often belong to recovery, not over-blocking.** Always pair-decompose lost tasks (`A/B/C/D` split) before blaming the guard.

## Verification checklist

- [ ] `python3 scripts/verify_freezes.py` and `python3 scripts/freeze_v3_1_prereg.py --verify` exit 0.
- [ ] All corpus checkers (`check_scenarios_v2.py`, `v3`, `v3_1`) report zero errors and zero structural overlap.
- [ ] Oracle replay reports `0` disagreements against recorded trajectories/fingerprints.
- [ ] Every unsupported/refuted preregistered claim is reported alongside supported ones.

## Related skills

`evidence-bound-report-pipeline`, `human-review-cards`, `gpu-idle-autorun`, `attack-defense-demo`, `tdd` (`mattpocock/skills`).
