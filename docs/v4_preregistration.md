# EviBound v4 preregistration

Status: frozen before the holdout run, 2026-11-23.

## Scope

This two-week run tests whether EviBound-T preserves static and declared task
safety while reading fewer facts than full or dependency-wide rereading. The
confirmatory core is a counterfactual guard comparison over the same frozen,
check-time-legal proposals and the same perturbation trajectories. The
end-to-end planner arm is descriptive. SimuHome is an unmodified external
environment; the synthetic fallback supplies the confirmatory core when that
external service is unavailable.

The run does not claim user-intent safety, resistance to a compromised sensor,
resistance to a compromised proxy, or behavior on real devices. Paid models and
paid APIs are excluded.

## Conditions

All guards use the same proposal, evidence records, execution time, and oracle.

| Code | Execution-time behavior |
|---|---|
| B0 | execute without checking |
| PEEK | follow one fresh-looking read through the untrusted tool channel |
| VER | reject only when the new value differs from the cited value |
| FBS | estimate freshness from arrival and observed variation |
| PHYS | reread once and reject physically implausible movement |
| M | signed provenance plus fixed two-minute freshness |
| AR | reread every fact the rules use |
| MS | reread every expired fact the rules use |
| SL | EviBound-T: physical lifetime plus three-valued short-circuit reread |

EviBound-T uses
`tau = min(margin / (kappa * declared_rate), tau_max) - epsilon`.
The frozen core values are `kappa = 1`, `tau_max = 600 seconds`, and
`epsilon = 0.5 seconds`.

## Data

- 50 development structures: IDs 1-50.
- 200 holdout structures: IDs 51-250.
- Clean: one case per structure.
- Benign drift, context replay, context forgery, and transport freeze: each at
  25%, 50%, and 90% of the check-to-execute interval.
- Holdout size: `200 * (1 + 4 * 3) = 2600` scenarios.
- Fixed seed: `20261123`.

Development cases may tune read priority and implementation defects. Static
rules, guards, hypotheses, sample size, split, and acceptance thresholds may
not change after the freeze. Correctness repairs reset the freeze before any
holdout result is reported.

## Hypotheses

| ID | Prediction | Decision rule |
|---|---|---|
| H1 | SL executes zero static-rule violations under all required perturbations | every holdout SL safety count is zero |
| H2 | clean and benign cases do not false-block SL | both false-block counts are zero |
| H3 | SL reads less than AR and no more than MS | every C2 case satisfies `SL <= MS <= AR` |
| H4 | every SL failure, deferral, or rejection carries a machine-readable reason | reason code is non-empty in every row |
| H5 | when true rate exceeds `kappa * declared_rate`, overshoot rises but never exceeds the analytic bound | every C1 row satisfies observed overshoot <= bound |
| H6 | transport freeze can force fail-safe rejection | SL records fail-safe rejections in the freeze family |
| H7 | removing task preconditions does not create static violations | checked by the `requires_50` and `requires_100` ablations when available |

## Primary descriptive comparisons

The result memo reports, by guard and perturbation:

- executed count;
- static safety violations;
- task-level errors;
- false blocks;
- fail-safe rejections;
- mean active reads;
- reason-code distribution.

The B-group arm is descriptive because the planned 7B/8B models are not hosted
inside this workspace. Its harness records the two model endpoints and refuses
to interpret absent model output as data.

## Stop rules

Stop and repair before reporting if:

1. SL executes even one static violation when the declared rate bound holds.
2. A clean or benign case false-blocks SL.
3. C1 overshoot exceeds its analytic bound.
4. C2 reports `SL > MS` or `MS > AR`.
5. A recorded result differs from the frozen source hash.

If the SimuHome external arm cannot run, report the synthetic core as the
primary result and omit external-validity claims. If planner endpoints are not
available, report the B group as not run rather than substituting mock results.
