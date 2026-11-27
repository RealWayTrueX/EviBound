# v3.1, exploratory: the feedback ladder with a second planner model

Written on 2026-11-25, **before** the first run of this arm and **after** the confirmatory
results of v3.1 were known ([v3_1_results.md](v3_1_results.md)). Nothing here has confirmatory
weight. The preregistration, the frozen files and the confirmatory record are not changed by it.

## Why

Every result of v3.1 comes from one planner, Qwen2.5-7B-Instruct at one revision. The
planner-character arm changed the system prompt and kept the model. The open question it left is
the first limit named in the results: do the findings belong to the method or to that one model?
This arm runs the same study with a second model.

## What is run

| | Confirmatory run | This arm |
|---|---|---|
| Tasks | 372 holdout tasks, three variants | the same |
| Conditions | the nine of the frozen matrix | the same |
| Seeds | 11, 22, 33 | the same |
| Episodes | 30,132 | 30,132 |
| Planner | Qwen2.5-7B-Instruct, bfloat16 | Qwen3-8B, bfloat16, from a local folder; sizes and hashes of its files are recorded with the run |
| Prompt, sampling | frozen prompt; temperature 0.2, top-p 0.9, top-k 20, 224 new tokens | the same |
| Chat template | the model's own, no argument | the model's own, rendered with `enable_thinking=False` |
| Runner, guard, oracle, analysis | frozen code | the same frozen code, unchanged |

The one difference in the planner is the template switch. Qwen3 opens a reasoning block unless
its template is told not to, and the 224 new tokens of the frozen settings would be spent inside
it. With the switch the model answers directly, as Qwen2.5 does. The switch is applied in
`src/evibound/planner_models.py`; generation, seeding and parsing are inherited from the frozen
planner. The sampling settings were chosen for Qwen2.5 and are kept as they are, so that the
two runs differ in the model only. They are not the settings the Qwen3 model card suggests.

With two graphics cards the tasks are split into two parts, one per card
(`scripts/run_v3_1_model.sh`). A task is complete within one part, so its nine conditions share
one first proposal, as in the frozen design.

## Before the run: a check of the form of the answers

A pilot runs the development split (48 tasks, three variants, seed 11, nine conditions, 1,296
episodes). It answers one question: does the model reply in the form the frozen parser expects?
The holdout run starts only if, in the pilot,

- no answer carries reasoning text (`<think>`), and
- at most 20 percent of the first proposals fail to parse.

The rule looks at the form of the answers and at nothing else. The pilot also produces outcome
numbers, because the frozen analysis runs on every run. They are not used for any decision and
are not reported as results.

## How it is read

The analysis is `scripts/analyze_v3_1.py --stage explore`, the frozen code. It computes every
contrast of the frozen plan. We report, for each of the six claims C1 to C6, the estimate, the
interval and the decision the frozen rule gives for this planner, next to the confirmatory ones.
All six are reported whatever they show.

Fixed here, before any output:

- A claim **carries over** to the second model when the frozen rule gives the same decision as
  in the confirmatory run. C3 was not supported there; it carries over when it is again not
  supported.
- When the decisions differ, we say so and give both estimates. Agreement in sign alone is
  reported as agreement in sign, not as a replication.
- The contrasts of first interest are U1 (a list of legal writes makes the planner change things
  nobody asked for), N1 (the reason alone is not behind the list), S1 and S2 (evidence binding
  under attack) and R1 (stating the trusted reading).
- Zero unsafe effects under the evidence-bound guard is a property of the guard and does not
  depend on the planner. The run can show a counterexample; it cannot add evidence beyond that.

## Limits

- One more model. It is from the same family and of the same size class as the first. A larger
  model, a model trained differently, or a model that reasons before it answers may behave
  differently.
- The decisions are computed with the frozen rules, but the run was planned after the
  confirmatory results were known. They describe this planner; they are not a second
  confirmatory test.
- Sampling settings and the prompt were developed on Qwen2.5. A prompt tuned for Qwen3 could
  change its level of performance.

## Where the output goes

Raw traces stay on the experiment machine. Fingerprints, the analysis, the record of the model
files and the check of the answers are published as for the other runs. Results are added to
[v3_1_results.md](v3_1_results.md) under their own exploratory heading.
