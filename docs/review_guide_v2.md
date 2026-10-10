# Human Review Guide - v2 Scenario Corpus (DRAFT)

Audience: Xin Li (corpus owner). Estimated time: 44 REQUIRED cards x ~5 min
plus optional spot checks. Everything you need is under `reviews/v2/`.

## Why this review exists

Course rule: ground truth must be deterministic or independently annotated, and
humans validate labels. The v1 corpus was never human-reviewed
(`human_policy_review: pending` in its manifest); v2 does not advance to
preregistration without your sign-off. Machine checks
(`scripts/check_scenarios_v2.py`) already passed, so every card you see is
schema-valid, solvable, and deduplicated within its family-conditioned structure
space. Shared physical clusters across family labels are disclosed by
`physical_structure_id`; your job is judgement, not debugging.

## Files

- `reviews/v2/test.md` / `pilot.md` / `dev.md` - one card per task, explicit
  anchors (`#task-<task_id>`), an index at the top.
- `reviews/v2/checklist.csv` - one row per task; only `required=yes` rows are
  mandatory (24 test including 6 A3 + the remaining 8 dev/pilot A3 + 12 sampled
  non-A3 dev/pilot tasks = 44 rows).
- `data/scenarios_v2/check_report.json` - the machine evidence; skim it first.

## What each card tells you

1. The task as the agent sees it: instruction, initial state, authorized set.
   (Annotations never reach the agent; they exist only for you and the oracle.)
2. Goal table: full goal, shortest legal write plan (BFS over the six rules),
   and for A3 tasks the authorized subgoal with its own plan.
3. Attack explanation: what the perturbed first observation claims and why a
   trusting policy takes the wrong branch.
4. Derived expected behavior per condition (B0/B1/B2/M) - treat these as
   hypotheses to challenge, not ground truth (q4).

## How to fill the checklist (per REQUIRED row)

- `q1_instruction_clear` Y/N: a competent agent (and you) can tell what outcome
  is requested on both branches without guessing.
- `q2_goals_sensible` Y/N: the requested end states are plausible smart-home
  behavior; nothing contradictory or trivial.
- `q3_perturbation_correct` Y/N: the attack explanation matches the mechanism
  (tamper = forged value, replay = authentic-but-stale) and the flipped branch
  is indeed the tempting one.
- `q4_expected_behavior_agree` Y/N: you agree with the derived per-condition
  expectations, especially which writes are unsafe/unauthorized.
- `q5_label_confidence` high/med/low: your confidence that this task's labels
  will be scored correctly by the independent oracle.
- `decision`: `approve` (usable as-is) / `fix` (usable after a specific change -
  say what in comment) / `reject` (unusable - say why).
- `comment`: mandatory for fix/reject and for any N answer.

Rules: answer honestly even for "obvious" cards; the point is a defensible
audit trail. If you spot a systematic issue (same complaint 3+ times), stop and
tell me - we fix the generator once instead of annotating 20 rows.

## After the review

```bash
python3 scripts/build_review_bundle.py --signoff "Xin Li"
```

This re-runs machine checks, validates checklist completeness, writes
`reviews/v2/signoff.json`, and advances the manifest lifecycle to
`human_reviewed` only if zero open items remain. `fix`/`reject` tasks are then
regenerated with a new seed offset and re-reviewed (loop until clean). The
corpus freezes only at Week-8 preregistration; until then everything under
`data/scenarios_v2/` remains DRAFT.

## What you are NOT being asked to review

- Guard/oracle code correctness (separate test suites own that).
- The six provisional rules themselves (rule audit lives in
  docs/design_v2_attack_defense.md Section 4; changing rules is a v3 decision).
- Optional (required=no) rows - spot-check only if time permits.
