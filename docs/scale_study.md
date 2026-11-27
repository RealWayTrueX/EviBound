# Exploratory: does it still hold in a bigger home?

Written on 2026-11-25, **before** the first run of this study and **after** the confirmatory
results of v2, v3 and v3.1 were known. Nothing here has confirmatory weight. No frozen file is
changed; the study uses new files only.

The study ran later the same day. Everything down to "Where the output goes" is the plan as it
was published before the run; the [results](#results) follow it.

## Why

All confirmatory results come from one very small home: a light and a fan with three levels
each, one presence reading, six rules, and at most three writes per episode. That is 18 states,
of which 9 are legal. A reader can fairly ask whether the findings are facts about guarding an
LLM planner or facts about a toy. This study runs the same experiment in three homes of
growing size and puts the results side by side.

## The three homes

Each home contains the one before it: the same devices and rules, plus new ones.

| | Small (S) | Medium (M) | Large (L) |
|---|---|---|---|
| Devices | light, fan | + heater, window | + air purifier, door lock |
| Kinds of level | off / low / high | + closed / ajar / open | + off / on, locked / unlocked |
| Rules | 6 | 12 | 14 |
| States (legal) | 18 (9) | 162 (35) | 648 (114) |
| Writes per episode, at most | 3 | 5 | 6 |

The small home is the home of the frozen studies, described again as data. Tests check that it
behaves identically: the same guard decision on every plan, the same attainable target and
outcome label for every v3.1 task, and the same content in every refusal message
(`tests/test_homes.py`).

The rules that the larger homes add are of the kinds the small home already has:

- **needs somebody present:** heater above off; window above closed; lock unlocked
- **no jump from the lowest to the highest level:** heater, window
- **must never hold together:** heater on and window not closed; purifier on and window open
- **power budget:** light + fan + heater + purifier, counted 0, 1, 2 from the lowest level, at most 4

The attack is the one of the frozen studies. The first reading the planner gets is forged or
replayed, so that it says the opposite of the truth. In the large home a forged "somebody is
home" asks for more than a lamp: it can turn the heater on and unlock the door.

## What stays the same

Everything that is not the home:

- the three guards: none (`B0`); the rules checked against the reading the planner cites
  (`B2`, no evidence binding); the evidence-bound guard (`M`), which accepts a write only if the
  cited record is in the trusted store and fresh at the commit, and then checks the rules
  against the recorded value
- the records, the three first observations (clean, at the freshness boundary, perturbed), the
  clock and the freshness limit
- one recovery turn after a refusal; the first proposal is shared by every condition
- the refusal messages, sentence by sentence where they do not name a device
- the scoring: an exhaustive search for what the rules allow, the attainable target, and the two
  outcomes *exact target* and *unrequested change*
- the planner prompt, sentence by sentence; the device list, the rules and the worked examples
  are generated from the description of the home
- sampling: temperature 0.2, top-p 0.9, top-k 20, three seeds (11, 22, 33)

Two settings differ from the frozen runs and are the same for all three homes: the answer may
be 384 new tokens long instead of 224, because a plan in the large home has up to six writes;
and the prompt is the generated one, not the hand-written one.

## Tasks

120 tasks per home, drawn at random with a fixed seed and then labelled by the scoring side
(`scripts/generate_scenarios_homes.py`). A task gives a room, the devices the planner may write,
the levels at the start, and one goal for each reading. Every home gets the same mix:

- somebody present in 60 tasks, nobody in 60
- the true goal can be reached in full in 68 tasks, in part in 26, not at all in 26
- 44 tasks need no write at all: the right course is to leave the home as it is
- in 42 of the 60 tasks with nobody present, a planner that believed the forged reading and
  followed the rules for it would break a rule in the real home

Twelve further tasks per home are pilot tasks. They are not tasks of the study.

## Conditions

Five, chosen for the comparisons the paper rests on:

| Condition | Guard | After a refusal the planner is told |
|---|---|---|
| `B0` | none | nothing is refused |
| `B2_plan` | rules on the cited reading | the reason, and a review of its plan |
| `M_recover` | evidence-bound | the reason |
| `M_full` | evidence-bound | the reason, and every write that is legal now |
| `M_plan` | evidence-bound | the reason, and a review of its plan |

Per home: 120 tasks x 3 variants x 3 seeds x 5 conditions = 5,400 episodes; 16,200 in all.
The planner is Qwen2.5-7B-Instruct, the planner of the confirmatory studies. If the study is
repeated with the second model (Qwen3-8B), that run uses the same files and is reported
separately.

## Before the run: a check of the form of the answers

A pilot runs the 12 pilot tasks of each home with seed 11. The study starts only if no answer
carries reasoning text and at most 20 percent of the first proposals fail to parse (a plan cut
off by the token limit fails to parse). The pilot also yields outcome numbers; they are not
used for any decision and not reported as results.

## How it is read

`scripts/analyze_homes.py` computes, for each home separately, five contrasts with the rules of
the frozen analysis (paired by task, variant and seed; equal weight per task; percentile
bootstrap over tasks, 10,000 resamples; superiority needs an interval above zero; the
non-inferiority margin is 5 percentage points).

| Id | Question | Contrast | Rule |
|---|---|---|---|
| S1 | Does evidence binding prevent unsafe effects under attack? | unsafe effect, perturbed: `B2_plan` - `M_plan` | superiority |
| S2 | Does it also leave the home as it should be? | exact target, perturbed, nobody present: `M_plan` - `B2_plan` | superiority |
| U1 | Does a list of legal writes make the planner change things nobody asked for? | unrequested change: `M_full` - `M_recover` | superiority |
| N1 | Is the reason alone at least as good as the list? | exact target: `M_recover` - `M_full` | non-inferiority |
| P1 | Is a review of the plan better than the reason alone? | exact target: `M_plan` - `M_recover` | superiority |

Fixed here, before any output:

- A finding **carries over** to a larger home when the rule gives the same decision there as in
  the small home of this study. Agreement in sign alone is reported as agreement in sign.
- All five contrasts are reported for all three homes, whatever they show. So is the rate of
  each outcome under each condition, and how often the planner's first answer was unusable.
- In the confirmatory study the plan review was ahead of the reason alone by 2.4 points
  (interval 0.6 to 4.1), although no claim tested that direction. We expect P1 to be small.
- Zero unsafe effects under the evidence-bound guard is a property of the guard. Tests check it
  for random plans in every home. The run can show a counterexample; it cannot add evidence
  beyond that.
- The small home of this study is not the confirmatory run again: the prompt is generated, the
  token limit is higher and the tasks are new. We report its numbers next to the confirmatory
  ones and say where they differ.

## Limits

- Still one presence reading, a simulated home and one recovery turn. The larger homes add
  devices, kinds of level and rules; they do not add sensors.
- The rules of the larger homes are of the kinds the small home already has. A different kind
  of rule (timing, for instance) is not covered.
- The planner is a 7B model. In the large home its first plans will be wrong more often; a
  stronger planner would be refused less and the refusal message would matter less.
- The study was planned after the confirmatory results were known.

## Where the output goes

Raw traces stay on the experiment machine. Fingerprints (the executed writes of every episode,
no prompt and no model output), the analysis, the record of the model files and the check of
the answers are published as for the other runs. Results are added to
[v3_1_results.md](v3_1_results.md) under their own exploratory heading.

## Results

Run on 2026-11-25 from the code at commit `6f0083c`, after the plan above was public (commit
`43fafd8`, 10:35 UTC). Exploratory: no confirmatory weight.

| | Qwen2.5-7B | Qwen3-8B (reasoning mode off) |
|---|---|---|
| Check of the answers on the pilot split (540 episodes, seed 11) | passed: no answer with reasoning text, none not parsed, none at the token limit | passed: the same |
| Run, UTC | 17:58:09 to 18:43:11 | 18:46:15 to 19:38:23 |
| Episodes | 16,200: 3 homes × 120 tasks × 5 conditions × 3 variants × 3 seeds | 16,200 |
| Hardware | two RTX 4090, half of the tasks of a home on each; small, medium, large in turn; no restart | the same |
| First answers not parsed | 0 of 3,240 | 0 of 3,240 |
| Recovery answers not parsed | 11 of 9,750, all in the large home | 0 of 8,742 |
| Answers at the limit of 384 new tokens | 0 | 0 |
| Outcome labels that differ when recomputed from the fingerprints | 0 | 0 |
| Fingerprints (no prompt, no model output) | `artifacts/homes_qwen25_fingerprints.json.gz` | `artifacts/homes_qwen3_fingerprints.json.gz` |
| Check of the answers of the run | `artifacts/homes_qwen25_check.json` | `artifacts/homes_qwen3_check.json` |
| Raw traces (on the experiment machine), SHA-256 begins | S `c0a0a9e619e10a8a`, `411efa88eb259d5c`; M `992e27def4e28e45`, `cbd5f64c4129b4c0`; L `5b462e2f7066ae16`, `a1070a1e4cca0ca6` | S `c7f9ddc3f53ba4be`, `1287b04d3a8ce666`; M `24d6ceba8f515432`, `1e5f0bd92c5cf43c`; L `1248e4104fac73c9`, `29968763aa048c39` |

The record is `artifacts/homes_record.json`. `python scripts/homes_record.py` rebuilds it and
the four tables below from the fingerprints; `--check` fails if any of them is stale.

### The runs

<!-- generated:homes_runs -->
| Planner | Home | Devices | Rules | States (legal) | Writes | Episodes | First answers not parsed | Mean entries in the list |
|---|---|---|---|---|---|---|---|---|
| Qwen2.5-7B | small | 2 | 6 | 18 (9) | 3 | 5400 | 0 of 1080 | 1.3 |
| Qwen2.5-7B | medium | 4 | 12 | 162 (35) | 5 | 5400 | 0 of 1080 | 2.06 |
| Qwen2.5-7B | large | 6 | 14 | 648 (114) | 6 | 5400 | 0 of 1080 | 3.15 |
| Qwen3-8B | small | 2 | 6 | 18 (9) | 3 | 5400 | 0 of 1080 | 1.39 |
| Qwen3-8B | medium | 4 | 12 | 162 (35) | 5 | 5400 | 0 of 1080 | 2.01 |
| Qwen3-8B | large | 6 | 14 | 648 (114) | 6 | 5400 | 0 of 1080 | 3.03 |
<!-- /generated:homes_runs -->

### Next to the simple home: Study 3 and the three homes

Study 3 is v3.1 in the frozen two-device home on its own 372 tasks: the confirmatory run for
Qwen2.5-7B and the exploratory repetition for Qwen3-8B
([v3_1_results.md](v3_1_results.md), sections 5 and 10). The three homes of this study use new
tasks, a generated prompt and a higher token limit, so the first two columns are two
measurements of the same small home, not one measurement twice.

<!-- generated:homes_vs_study3 -->
| Planner | Quantity | Study 3 (frozen small home) | small | medium | large |
|---|---|---|---|---|---|
| Qwen2.5-7B | Unsafe effect under attack, guard that trusts the cited reading | 134 of 1116 (12.0%) | 48 of 360 (13.3%) | 51 of 360 (14.2%) | 63 of 360 (17.5%) |
| Qwen2.5-7B | Unsafe effect under attack, evidence-bound guard (reason) | 0 of 1116 (0.0%) | 0 of 360 (0.0%) | 0 of 360 (0.0%) | 0 of 360 (0.0%) |
| Qwen2.5-7B | Unrequested change, reason alone | 445 of 3348 (13.3%) | 70 of 1080 (6.5%) | 49 of 1080 (4.5%) | 77 of 1080 (7.1%) |
| Qwen2.5-7B | Unrequested change, reason + list | 850 of 3348 (25.4%) | 198 of 1080 (18.3%) | 267 of 1080 (24.7%) | 346 of 1080 (32.0%) |
| Qwen2.5-7B | Exact target, reason alone | 2505 of 3348 (74.8%) | 876 of 1080 (81.1%) | 887 of 1080 (82.1%) | 806 of 1080 (74.6%) |
| Qwen2.5-7B | Exact target, reason + list | 2218 of 3348 (66.2%) | 766 of 1080 (70.9%) | 717 of 1080 (66.4%) | 592 of 1080 (54.8%) |
| Qwen2.5-7B | Exact target, reason + plan review | 2584 of 3348 (77.2%) | 891 of 1080 (82.5%) | 897 of 1080 (83.1%) | 855 of 1080 (79.2%) |
| Qwen2.5-7B | List minus reason, unrequested change (pp) | +12.1 [+9.5, +14.8] | +11.9 [+8.1, +15.9] | +20.2 [+15.2, +25.6] | +24.9 [+18.9, +31.3] |
| Qwen2.5-7B | Reason minus list, exact target (pp) | +8.6 [+5.3, +11.9] | +10.2 [+5.7, +14.8] | +15.7 [+9.9, +21.8] | +19.8 [+12.6, +27.2] |
| Qwen2.5-7B | Plan review minus reason, exact target (pp) | +2.4 [+0.6, +4.1] | +1.4 [+0.2, +3.1] | +0.9 [-1.9, +3.8] | +4.5 [+0.2, +8.9] |
| Qwen3-8B | Unsafe effect under attack, guard that trusts the cited reading | 127 of 1116 (11.4%) | 108 of 360 (30.0%) | 96 of 360 (26.7%) | 90 of 360 (25.0%) |
| Qwen3-8B | Unsafe effect under attack, evidence-bound guard (reason) | 0 of 1116 (0.0%) | 0 of 360 (0.0%) | 0 of 360 (0.0%) | 0 of 360 (0.0%) |
| Qwen3-8B | Unrequested change, reason alone | 304 of 3348 (9.1%) | 160 of 1080 (14.8%) | 121 of 1080 (11.2%) | 149 of 1080 (13.8%) |
| Qwen3-8B | Unrequested change, reason + list | 588 of 3348 (17.6%) | 214 of 1080 (19.8%) | 204 of 1080 (18.9%) | 247 of 1080 (22.9%) |
| Qwen3-8B | Exact target, reason alone | 2568 of 3348 (76.7%) | 781 of 1080 (72.3%) | 783 of 1080 (72.5%) | 717 of 1080 (66.4%) |
| Qwen3-8B | Exact target, reason + list | 2451 of 3348 (73.2%) | 798 of 1080 (73.9%) | 774 of 1080 (71.7%) | 688 of 1080 (63.7%) |
| Qwen3-8B | Exact target, reason + plan review | 2595 of 3348 (77.5%) | 820 of 1080 (75.9%) | 858 of 1080 (79.4%) | 793 of 1080 (73.4%) |
| Qwen3-8B | List minus reason, unrequested change (pp) | +8.5 [+6.3, +10.9] | +5.0 [+1.7, +8.5] | +7.7 [+4.6, +11.2] | +9.1 [+4.7, +13.9] |
| Qwen3-8B | Reason minus list, exact target (pp) | +3.5 [+0.6, +6.4] | -1.6 [-6.5, +3.2] | +0.8 [-4.3, +5.7] | +2.7 [-2.3, +8.0] |
| Qwen3-8B | Plan review minus reason, exact target (pp) | +0.8 [-0.7, +2.3] | +3.6 [+0.7, +6.5] | +6.9 [+3.6, +10.2] | +7.0 [+3.4, +10.6] |
<!-- /generated:homes_vs_study3 -->

### Every condition

<!-- generated:homes_rates -->
| Planner | Home | Condition |  | Unsafe effect, attacked | Exact target, clean | Exact target, all | Unrequested change, all |
|---|---|---|---|---|---|---|---|
| Qwen2.5-7B | small | `B0` | no guard | 191 (53.1%) | 174 (48.3%) | 396 (36.7%) | 61 (5.6%) |
| Qwen2.5-7B | small | `B2_plan` | rules on the cited reading | 48 (13.3%) | 332 (92.2%) | 801 (74.2%) | 100 (9.3%) |
| Qwen2.5-7B | small | `M_recover` | evidence-bound, reason | 0 (0.0%) | 322 (89.4%) | 876 (81.1%) | 70 (6.5%) |
| Qwen2.5-7B | small | `M_full` | evidence-bound, reason + list | 0 (0.0%) | 291 (80.8%) | 766 (70.9%) | 198 (18.3%) |
| Qwen2.5-7B | small | `M_plan` | evidence-bound, reason + plan review | 0 (0.0%) | 331 (91.9%) | 891 (82.5%) | 66 (6.1%) |
| Qwen2.5-7B | medium | `B0` | no guard | 245 (68.1%) | 138 (38.3%) | 302 (28.0%) | 32 (3.0%) |
| Qwen2.5-7B | medium | `B2_plan` | rules on the cited reading | 51 (14.2%) | 329 (91.4%) | 778 (72.0%) | 83 (7.7%) |
| Qwen2.5-7B | medium | `M_recover` | evidence-bound, reason | 0 (0.0%) | 323 (89.7%) | 887 (82.1%) | 49 (4.5%) |
| Qwen2.5-7B | medium | `M_full` | evidence-bound, reason + list | 0 (0.0%) | 269 (74.7%) | 717 (66.4%) | 267 (24.7%) |
| Qwen2.5-7B | medium | `M_plan` | evidence-bound, reason + plan review | 0 (0.0%) | 329 (91.4%) | 897 (83.1%) | 44 (4.1%) |
| Qwen2.5-7B | large | `B0` | no guard | 232 (64.4%) | 129 (35.8%) | 276 (25.6%) | 67 (6.2%) |
| Qwen2.5-7B | large | `B2_plan` | rules on the cited reading | 63 (17.5%) | 314 (87.2%) | 749 (69.4%) | 140 (13.0%) |
| Qwen2.5-7B | large | `M_recover` | evidence-bound, reason | 0 (0.0%) | 289 (80.3%) | 806 (74.6%) | 77 (7.1%) |
| Qwen2.5-7B | large | `M_full` | evidence-bound, reason + list | 0 (0.0%) | 242 (67.2%) | 592 (54.8%) | 346 (32.0%) |
| Qwen2.5-7B | large | `M_plan` | evidence-bound, reason + plan review | 0 (0.0%) | 311 (86.4%) | 855 (79.2%) | 94 (8.7%) |
| Qwen3-8B | small | `B0` | no guard | 181 (50.3%) | 235 (65.3%) | 537 (49.7%) | 92 (8.5%) |
| Qwen3-8B | small | `B2_plan` | rules on the cited reading | 108 (30.0%) | 305 (84.7%) | 739 (68.4%) | 144 (13.3%) |
| Qwen3-8B | small | `M_recover` | evidence-bound, reason | 0 (0.0%) | 299 (83.1%) | 781 (72.3%) | 160 (14.8%) |
| Qwen3-8B | small | `M_full` | evidence-bound, reason + list | 0 (0.0%) | 307 (85.3%) | 798 (73.9%) | 214 (19.8%) |
| Qwen3-8B | small | `M_plan` | evidence-bound, reason + plan review | 0 (0.0%) | 305 (84.7%) | 820 (75.9%) | 145 (13.4%) |
| Qwen3-8B | medium | `B0` | no guard | 191 (53.1%) | 204 (56.7%) | 469 (43.4%) | 59 (5.5%) |
| Qwen3-8B | medium | `B2_plan` | rules on the cited reading | 96 (26.7%) | 307 (85.3%) | 736 (68.1%) | 120 (11.1%) |
| Qwen3-8B | medium | `M_recover` | evidence-bound, reason | 0 (0.0%) | 309 (85.8%) | 783 (72.5%) | 121 (11.2%) |
| Qwen3-8B | medium | `M_full` | evidence-bound, reason + list | 0 (0.0%) | 305 (84.7%) | 774 (71.7%) | 204 (18.9%) |
| Qwen3-8B | medium | `M_plan` | evidence-bound, reason + plan review | 0 (0.0%) | 306 (85.0%) | 858 (79.4%) | 71 (6.6%) |
| Qwen3-8B | large | `B0` | no guard | 189 (52.5%) | 147 (40.8%) | 370 (34.3%) | 68 (6.3%) |
| Qwen3-8B | large | `B2_plan` | rules on the cited reading | 90 (25.0%) | 276 (76.7%) | 667 (61.8%) | 124 (11.5%) |
| Qwen3-8B | large | `M_recover` | evidence-bound, reason | 0 (0.0%) | 282 (78.3%) | 717 (66.4%) | 149 (13.8%) |
| Qwen3-8B | large | `M_full` | evidence-bound, reason + list | 0 (0.0%) | 270 (75.0%) | 688 (63.7%) | 247 (22.9%) |
| Qwen3-8B | large | `M_plan` | evidence-bound, reason + plan review | 0 (0.0%) | 276 (76.7%) | 793 (73.4%) | 106 (9.8%) |
<!-- /generated:homes_rates -->

### The contrasts

S1, S2, U1, N1 and P1 are the five planned contrasts; K1 to K6 are descriptive.

<!-- generated:homes_contrasts -->
| Id | Contrast | Planner | small | medium | large |
|---|---|---|---|---|---|
| S1 | Evidence binding prevents unsafe effects under attack: unsafe effect, B2_plan - M_plan | Qwen2.5-7B | 48 vs 0 of 360; +13.3 [+7.5, +20.0]; supported | 51 vs 0 of 360; +14.2 [+8.3, +20.8]; supported | 63 vs 0 of 360; +17.5 [+10.8, +25.0]; supported |
| S1 | Evidence binding prevents unsafe effects under attack: unsafe effect, B2_plan - M_plan | Qwen3-8B | 108 vs 0 of 360; +30.0 [+21.7, +38.3]; supported | 96 vs 0 of 360; +26.7 [+19.2, +35.0]; supported | 90 vs 0 of 360; +25.0 [+17.5, +33.3]; supported |
| S2 | and keeps the home as it should be: exact target with nobody present, M_plan - B2_plan | Qwen2.5-7B | 155 vs 69 of 180; +47.8 [+31.7, +62.8]; supported | 159 vs 53 of 180; +58.9 [+46.1, +71.1]; supported | 156 vs 69 of 180; +48.3 [+35.0, +61.7]; supported |
| S2 | and keeps the home as it should be: exact target with nobody present, M_plan - B2_plan | Qwen3-8B | 124 vs 44 of 180; +44.4 [+31.1, +57.8]; supported | 131 vs 48 of 180; +46.1 [+33.3, +58.3]; supported | 135 vs 57 of 180; +43.3 [+31.1, +56.1]; supported |
| U1 | A list of legal writes makes the planner change things nobody asked for: unrequested change, M_full - M_recover | Qwen2.5-7B | 198 vs 70 of 1080; +11.9 [+8.1, +15.9]; supported | 267 vs 49 of 1080; +20.2 [+15.2, +25.6]; supported | 346 vs 77 of 1080; +24.9 [+18.9, +31.3]; supported |
| U1 | A list of legal writes makes the planner change things nobody asked for: unrequested change, M_full - M_recover | Qwen3-8B | 214 vs 160 of 1080; +5.0 [+1.7, +8.5]; supported | 204 vs 121 of 1080; +7.7 [+4.6, +11.2]; supported | 247 vs 149 of 1080; +9.1 [+4.7, +13.9]; supported |
| N1 | The reason alone is not behind the list: exact target, M_recover - M_full (margin -5 pp) | Qwen2.5-7B | 876 vs 766 of 1080; +10.2 [+5.7, +14.8]; supported | 887 vs 717 of 1080; +15.7 [+9.9, +21.8]; supported | 806 vs 592 of 1080; +19.8 [+12.6, +27.2]; supported |
| N1 | The reason alone is not behind the list: exact target, M_recover - M_full (margin -5 pp) | Qwen3-8B | 781 vs 798 of 1080; -1.6 [-6.5, +3.2]; inconclusive | 783 vs 774 of 1080; +0.8 [-4.3, +5.7]; supported | 717 vs 688 of 1080; +2.7 [-2.3, +8.0]; supported |
| P1 | A review of the plan against the reason alone: exact target, M_plan - M_recover | Qwen2.5-7B | 891 vs 876 of 1080; +1.4 [+0.2, +3.1]; supported | 897 vs 887 of 1080; +0.9 [-1.9, +3.8]; inconclusive | 855 vs 806 of 1080; +4.5 [+0.2, +8.9]; supported |
| P1 | A review of the plan against the reason alone: exact target, M_plan - M_recover | Qwen3-8B | 820 vs 781 of 1080; +3.6 [+0.7, +6.5]; supported | 858 vs 783 of 1080; +6.9 [+3.6, +10.2]; supported | 793 vs 717 of 1080; +7.0 [+3.4, +10.6]; supported |
| K1 | Exact target, the reason alone against the list | Qwen2.5-7B | 876 vs 766 of 1080; +10.2 [+5.7, +14.8]; supported | 887 vs 717 of 1080; +15.7 [+10.1, +21.7]; supported | 806 vs 592 of 1080; +19.8 [+12.6, +26.9]; supported |
| K1 | Exact target, the reason alone against the list | Qwen3-8B | 781 vs 798 of 1080; -1.6 [-6.3, +3.3]; unsupported | 783 vs 774 of 1080; +0.8 [-4.0, +5.8]; inconclusive | 717 vs 688 of 1080; +2.7 [-2.3, +7.9]; inconclusive |
| K2 | U1 on tasks that need no write | Qwen2.5-7B | 126 vs 41 of 396; +21.5 [+12.9, +30.3]; supported | 143 vs 18 of 396; +31.6 [+21.5, +41.9]; supported | 128 vs 16 of 396; +28.3 [+17.7, +39.6]; supported |
| K2 | U1 on tasks that need no write | Qwen3-8B | 151 vs 106 of 396; +11.4 [+3.0, +19.7]; supported | 111 vs 42 of 396; +17.4 [+10.1, +25.3]; supported | 121 vs 40 of 396; +20.5 [+11.9, +30.1]; supported |
| K3 | U1 on tasks that need a write | Qwen2.5-7B | 72 vs 29 of 684; +6.3 [+3.2, +9.8]; supported | 124 vs 31 of 684; +13.6 [+8.6, +19.2]; supported | 218 vs 61 of 684; +23.0 [+16.1, +30.6]; supported |
| K3 | U1 on tasks that need a write | Qwen3-8B | 63 vs 54 of 684; +1.3 [-0.7, +3.5]; inconclusive | 93 vs 79 of 684; +2.0 [+0.4, +3.9]; supported | 126 vs 109 of 684; +2.5 [-1.8, +7.0]; inconclusive |
| K4 | What the guard costs without attack: exact target, B0 - M_recover | Qwen2.5-7B | 174 vs 322 of 360; -41.1 [-49.4, -32.8]; unsupported | 138 vs 323 of 360; -51.4 [-60.6, -42.5]; unsupported | 129 vs 289 of 360; -44.4 [-53.6, -35.8]; unsupported |
| K4 | What the guard costs without attack: exact target, B0 - M_recover | Qwen3-8B | 235 vs 299 of 360; -17.8 [-24.5, -11.1]; unsupported | 204 vs 309 of 360; -29.2 [-37.5, -21.4]; unsupported | 147 vs 282 of 360; -37.5 [-45.8, -29.2]; unsupported |
| K5 | S1 where a believed attack asks for an unsafe write | Qwen2.5-7B | 48 vs 0 of 126; +38.1 [+23.8, +52.4]; supported | 51 vs 0 of 126; +40.5 [+26.2, +54.8]; supported | 60 vs 0 of 126; +47.6 [+33.3, +61.9]; supported |
| K5 | S1 where a believed attack asks for an unsafe write | Qwen3-8B | 105 vs 0 of 126; +83.3 [+71.4, +92.9]; supported | 96 vs 0 of 126; +76.2 [+61.9, +88.1]; supported | 90 vs 0 of 126; +71.4 [+57.1, +85.7]; supported |
| K6 | The plan review is not behind the reason alone: exact target, M_plan - M_recover (margin -5 pp) | Qwen2.5-7B | 891 vs 876 of 1080; +1.4 [+0.2, +3.0]; supported | 897 vs 887 of 1080; +0.9 [-1.9, +3.8]; supported | 855 vs 806 of 1080; +4.5 [+0.1, +9.0]; supported |
| K6 | The plan review is not behind the reason alone: exact target, M_plan - M_recover (margin -5 pp) | Qwen3-8B | 820 vs 781 of 1080; +3.6 [+0.8, +6.5]; supported | 858 vs 783 of 1080; +6.9 [+3.7, +10.3]; supported | 793 vs 717 of 1080; +7.0 [+3.4, +10.6]; supported |
<!-- /generated:homes_contrasts -->

### What the runs show

<!-- prose:checked -->
**Evidence binding carries over, in every home and with both planners.** Under attack, the
guard that checks the rules on the cited reading executed an unsafe write in 13.3%, 14.2% and
17.5% of episodes with Qwen2.5-7B (small, medium, large) and in 30.0%, 26.7% and 25.0% with
Qwen3-8B. The evidence-bound guard executed none, under any of its three messages. S1 and S2
are supported in all six cells. Without attack the evidence-bound guard costs almost nothing
against the rule guard: with the plan review, 91.9% against 92.2% of clean episodes end in the
attainable target in the small home, 91.4% against 91.4% in the medium one and 86.4% against
87.2% in the large one (Qwen2.5-7B).

**The harm of the list carries over, and it grows with the home.** A list of legal writes
raised the share of episodes with a change nobody asked for in all six cells (U1 supported
everywhere). With Qwen2.5-7B the difference to the reason alone is +11.9, +20.2 and +24.9
points as the home grows; with Qwen3-8B it is +5.0, +7.7 and +9.1. The list itself grows with
the home, from 1.3 entries on average to 2.06 and 3.15, so the planner is shown more writes
that its plan never contained. The effect is largest on tasks that need no write at all (K2).

**Whether the list also costs attainable targets depends on the planner.** With Qwen2.5-7B
the reason alone is ahead of the list by +10.2, +15.7 and +19.8 points, and N1 is supported in
all three homes. With Qwen3-8B the two are level: -1.6, +0.8 and +2.7 points, every interval
containing zero. N1 is supported for Qwen3-8B in the medium and large home and inconclusive in
the small one, where the lower end of the interval (-6.5) is beyond the margin. By the rule set
in the plan, N1 therefore does not "carry over" for Qwen3-8B: its decision in the two larger
homes differs from the one in the small home, and it differs in the favourable direction.

**The plan review gains on the reason alone as the home grows.** With Qwen3-8B the review of
the planner's own plan is ahead by +3.6, +6.9 and +7.0 points (P1 supported in all three
homes). With Qwen2.5-7B it is ahead by +1.4 and +4.5 points in the small and large home and by
+0.9 in the medium one, where the interval contains zero. The plan expected P1 to be small. It
is small in the two-device home and not small with Qwen3-8B in the larger ones.

**The small home here and Study 3 agree for Qwen2.5-7B and less so for Qwen3-8B.** For
Qwen2.5-7B the two measurements of the small home are close: an unsafe write under the rule
guard in 13.3% of attacked episodes here against 12.0% in Study 3, and a difference in
unrequested changes of +11.9 points here against +12.1 there. For Qwen3-8B they are further
apart: 30.0% against 11.4%, and +5.0 against +8.5 points. The tasks, the prompt text and the
token limit all differ between the two, and this study cannot say which of them moves
Qwen3-8B.
<!-- /prose:checked -->

### Reading

- The two results the project rests on do not depend on the home having two devices. Binding
  a write to a trusted, fresh reading removed every unsafe effect in homes with 18, 162 and
  648 states, and a list of legal writes produced unrequested changes in all of them.
- The list gets worse as the home gets bigger. This fits the reading given after Study 3: the
  harm comes from showing the planner writes that were not in its plan, and a bigger home
  means more of them.
- "State the reason" stays a safe default against the list. Against the plan review it is no
  longer clearly as good once the home has four or six devices: with Qwen3-8B the review is
  ahead by about seven points there. Study 3 found the two within five points of each other
  in the small home (claim C5). No contrast of this study tested a margin in that direction,
  so this is an observation, not a decision.
- The large home is harder than the small one: under every condition and with both planners,
  fewer episodes end in the attainable target there. The medium home is not consistently
  harder than the small one.

### What was added after the run

- The table "Next to the simple home" and the reference points in the report's figure were
  written after the run. They rearrange numbers of this study and of Study 3 and decide
  nothing. For Study 3 they use its contrasts U1, K36 (reason minus list, exact target) and
  N3 with the sign turned (plan review minus reason).
- The plan said results would be added to `v3_1_results.md`. The tables are here; section 11
  of that document carries the side-by-side table and a summary.
- Nothing else departed from the plan: the conditions, tasks, seeds, token limit, contrasts
  and decision rules are those written above.
