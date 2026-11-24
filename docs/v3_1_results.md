# EviBound v3.1 results: what a guard should say after it blocks / 守卫拦截之后该说什么

Status: **the confirmatory run is in progress** (started 2026-11-24 20:21:45
UTC). This file is the frame of the results document: the tables between
`generated` markers are empty until the run has completed and are then written
by `scripts/analyze_v3_1.py` from the committed episode fingerprints (`--check`
fails if they are stale). The run follows the preregistration
([v3_1_preregistration.md](v3_1_preregistration.md)), frozen in
`artifacts/v3_1_prereg_freeze.json` at 2026-11-24 20:20:43 UTC, before any
holdout output existed.

| Item | Value |
|---|---|
| Record | `artifacts/v3_1_holdout_results.json` |
| Episode fingerprints | `artifacts/v3_1_holdout_fingerprints.json.gz` (executed writes, parsed plans, rejection reasons, outcomes; no model text) |
| Script | `python scripts/analyze_v3_1.py --stage holdout --input artifacts/v3_1_holdout_fingerprints.json.gz --record artifacts/v3_1_holdout_results.json --doc docs/v3_1_results.md` |
| Estimator | `analyze.paired_contrast`: physical structures as clusters, seeds matched and averaged within a cluster, 10,000 resamples, seed 20261011; non-inferiority margin −5 pp |
| Raw traces | on the experiment machine's data disk; not in the repository |

## Summary

To be written when the run has completed.

## 1. Design as run

<!-- generated:design -->
<!-- /generated:design -->

Run notes (start and end, restarts, deviations from the plan) are added here
when the run has completed.

## 2. Confirmatory claims

The six claims were fixed before the freeze. Each needs all of its parts.
`M_recover` gives the reason, `M_reading` the reason and the trusted reading,
`M_full` and `M_menu2` a list of legal writes (the v3 wording and a corrected
one), `M_plan` a review of the plan, `M_seq` a sequence of writes.

<!-- generated:claims -->
<!-- /generated:claims -->

**C1. A list of legal writes makes the planner change things nobody asked for, however the list is worded.**

<!-- generated:c1 -->
<!-- /generated:c1 -->

**C2. With a list, a plan that was only interrupted is not carried on.**

<!-- generated:c2 -->
<!-- /generated:c2 -->

**C3. Telling the planner how to revise its plan, or which writes to return, repairs fewer plans than the reason alone.**

<!-- generated:c3 -->
<!-- /generated:c3 -->

**C4. Saying the trusted reading helps when it is not the reading the plan was chosen for.**

<!-- generated:c4 -->
<!-- /generated:c4 -->

**C5. The reason alone is not behind any level that prescribes writes.**

<!-- generated:c5 -->
<!-- /generated:c5 -->

**C6. Under attack, evidence binding prevents unsafe effects and keeps the home as it was.**

<!-- generated:c6 -->
<!-- /generated:c6 -->

### Level against level within one kind of recovery turn

Each cell: episodes that ended at the attainable target / episodes with an
unrequested change. The kind of a turn is fixed before the message is written,
so a row holds the same episodes in every column.

<!-- generated:kinds -->
<!-- /generated:kinds -->

### The claims of the first draft

Written before any v3.1 run and replaced after the development runs (see the
preregistration). Computed as drafted, without confirmatory weight.

<!-- generated:draft -->
<!-- /generated:draft -->

## 3. Every condition at a glance (core tasks)

Completed: goal completion on tasks whose whole goal is attainable (class
`full`). Unrequested change: no violation, and a device ends at a level that
is neither its initial level nor its level in the attainable target, on tasks
where only part of the goal is attainable (class `part`). Unsafe: unsafe
effect, all core tasks. Each cell is episodes out of episodes.

<!-- generated:cells -->
<!-- /generated:cells -->

## 4. Paired split against the unguarded run (core tasks, class `full`)

A: the unguarded run completed without a violation and this condition did
not. B: the unguarded run completed with a violation and this condition did
not complete. C: this condition completed and the unguarded run did not.
D: neither completed.

<!-- generated:split -->
<!-- /generated:split -->

## 5. Where episodes ended (core tasks)

`exact`: the attainable target. `extra`: the attainable part of the goal plus
a change nobody asked for. `unrequested`: a permitted state that is neither.
`short`: on the way to the target. `nothing`: no change although one was
attainable. `violation`: a rule or the scope was broken.

<!-- generated:outcomes -->
<!-- /generated:outcomes -->

## 6. Attack battery

Tasks in which nothing has to be done unless the attack is believed.

<!-- generated:battery -->
<!-- /generated:battery -->

<!-- generated:battery_outcomes -->
<!-- /generated:battery_outcomes -->

## 7. Recovery turns

<!-- generated:reviews -->
<!-- /generated:reviews -->

## 8. Secondary contrasts

Reported with intervals and without confirmatory weight.

<!-- generated:secondary -->
<!-- /generated:secondary -->

## 9. Exploratory: planner characters

To be completed when the three runs of the exploratory arm have finished.

<!-- generated:roles -->
<!-- /generated:roles -->

<!-- generated:roles_totals -->
<!-- /generated:roles_totals -->

<!-- generated:roles_turns -->
<!-- /generated:roles_turns -->

## 10. Limits

See the section "Limits" of the preregistration.
