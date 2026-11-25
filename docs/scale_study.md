# Exploratory: does it still hold in a bigger home?

Written on 2026-11-25, **before** the first run of this study and **after** the confirmatory
results of v2, v3 and v3.1 were known. Nothing here has confirmatory weight. No frozen file is
changed; the study uses new files only.

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
