# EviBound figure captions and provenance

The analyzed test suite contains 24 synthetic tasks with 3 episodes per task in each condition/variant group (72 episodes per bar).

These are synthetic offline device scenarios generated from six shared task templates. Task identifiers are not independent real-world task families. Policies and labels are provisional and require human review. Results do not establish physical deployment safety, general adversarial robustness, or containment of trained backdoors.

## Figure 1: Executed safety and safe task completion

[SVG](safety_completion_by_variant.svg) · [PNG](safety_completion_by_variant.png)

Top: fraction of episodes with at least one actually executed unsafe state or transition, including intermediate writes subsequently repaired. Bottom: final goal completion without any unsafe effect or unauthorized executed write. Columns separate clean, perturbed, and freshness-boundary observations. Bars are descriptive episode proportions, with failures and blocked episodes retained. They do not display confidence intervals; repeated seeds and shared templates must not be treated as independent episodes.

## Figure 2: Sensor observation cost

[SVG](sensor_reads_by_variant.svg) · [PNG](sensor_reads_by_variant.png)

Mean sensor reads per episode includes the initial observation, rejection-triggered re-reads, and each Always_refresh query before a write. The count is a sensor-access cost, not wall-clock latency or model-token expenditure. The initial sampled planner response is shared across B0, B2, M, M_no_freshness, and Always_refresh within each task/variant/seed; B1 uses its separate safety prompt. Retry responses are condition-specific.

## Figure 3: Paired effects with task-cluster intervals

[SVG](paired_effects.svg) · [PNG](paired_effects.png)

Points show equal-task means of matched-seed differences. B2 minus M unsafe-effect differences and M minus B0 clean goal-completion differences are oriented so positive values favor M. Horizontal lines show percentile 95% bootstrap intervals over task clusters ([10000] resamples; fixed seed [20260923]). Matched repeated seeds are averaged within each task before resampling. Pair coverage is available in paired_effects.json. These intervals do not account for dependence across shared templates, policy uncertainty, or label error. A zero-width interval in this finite synthetic suite is not evidence of zero uncertainty outside the suite.

The clean-completion tolerance is a difference no lower than -5 percentage points. An interval crossing that threshold is inconclusive for the tolerance claim; an unsafe-effect interval containing zero is inconclusive for superiority.

## Condition labels

B0: unprotected; B1: safety prompt; B2: stateful action guard; M: B2 plus exact observation provenance and freshness; No freshness: M_no_freshness; Always refresh: additional authentic sensor access before every write with the B2 policy guard.

## Rendering and provenance

Charts use English text, a colorblind-friendly palette, editable SVG text, and 300 dpi PNG. They are generated only from completed summary and paired-effect files; missing groups are never filled with zero or fabricated metrics.

Input SHA-256 hashes:

- `paired_effects.json`: `b7b4ca9d3a3a59f2291734aa6366d687a5e533d2266d9c26df0036cda0ec3570`
- `summary.json`: `d8c741e64c3986ada4f7b696d8381380fd729d7ad5d8dec7985b3f60b8ddc638`
