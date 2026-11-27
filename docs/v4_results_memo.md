# EviBound v4 two-week run results

Run date: 2026-11-24. Frozen protocol:
`artifacts/v4_prereg_freeze.json`.

## Decision

The local core passes its preregistered acceptance checks. EviBound-T (SL)
executed no static-rule violations in 2,600 holdout counterfactual scenarios,
false-blocked no clean or benign case, short-circuited context attacks in one
read, and failed safely under transport freeze. C1 and C2 also passed.

The SimuHome G0 smoke gate passed at the pinned commit. The B-group planner arm
did not run because neither Qwen endpoint was available in this environment.
This memo therefore reports a complete local core and external API smoke test,
not an end-to-end multi-model result.

## Frozen inputs

| Item | Value |
|---|---|
| preregistration freeze | `artifacts/v4_prereg_freeze.json`, 18 files |
| rules | `configs/v4_rules.json`, 12 owner-approved candidates |
| structures | 50 development, 200 holdout |
| attacks | benign drift, context replay, context forgery, transport freeze |
| timing | 25%, 50%, 90% of the interval |
| holdout scenarios | 2,600: `200 * (1 + 4 * 3)` |
| seed | 20261123 |
| lifetime parameters | `kappa=1`, `tau_max=600 s`, `epsilon=0.5 s` |

## A group

The following counts use the 200 holdout structures. Each attack family has
600 scenarios because it is repeated at three timing fractions.

| Guard | Clean unsafe | Benign unsafe | Replay unsafe | Forgery unsafe | Freeze unsafe | Freeze fail-safe |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 0/200 | 0/600 | 600/600 | 600/600 | 600/600 | 0/600 |
| PEEK | 0/200 | 0/600 | 600/600 | 600/600 | 600/600 | 0/600 |
| VER | 0/200 | 0/600 | 600/600 | 600/600 | 600/600 | 0/600 |
| FBS | 0/200 | 0/600 | 600/600 | 600/600 | 600/600 | 0/600 |
| PHYS | 0/200 | 0/600 | 600/600 | 600/600 | 600/600 | 0/600 |
| M | 0/200 | 0/600 | 0/600 | 0/600 | 0/600 | 600/600 |
| AR | 0/200 | 0/600 | 0/600 | 0/600 | 0/600 | 600/600 |
| MS | 0/200 | 0/600 | 0/600 | 0/600 | 0/600 | 600/600 |
| SL | 0/200 | 0/600 | 0/600 | 0/600 | 0/600 | 600/600 |

Mean active reads:

- B0: 0 in every family.
- PEEK, VER, FBS, PHYS, M, AR, and MS: 5 in this five-fact design.
- SL: 5 on clean, benign, and freeze cases; 1 on context replay and forgery.

VER also rejected all 600 benign-drift cases after the temperature value
changed, although every precondition remained true. This is the false-block
pattern the v4 design predicts for value-equality checks.

## C1 rate stress

C1 ran 200 random scenarios at each of 12 rate/safety-factor grid points:
`rho` in `{0.5, 1, 1.25, 1.5, 2, 4}` and `kappa` in `{1, 1.5}`.

- Every case with `rho <= kappa` had zero violations.
- No observed overshoot exceeded the analytic bound.
- At `rho=4`, violations rose as expected:
  - `kappa=1`: 180/200 violations, maximum overshoot 81.90, bound 83.67.
  - `kappa=1.5`: 170/200 violations, maximum overshoot 47.59, bound 48.28.

C1 measures the consequence of an incorrect declared rate. It does not turn a
rate violation into a pass condition; the safety theorem assumes
`true_rate <= kappa * declared_rate`.

## C2 read cost

C2 ran 200 deterministic cases at every combination of:

- shape: `all_of`, `any_of`, mixed;
- condition count: 2, 4, 8;
- stale proportion: 0%, 25%, 50%, 100%.

All 7,200 cases satisfied:

`SL reads <= MS reads <= AR reads`.

At eight conditions with 25% stale, the mean reads were:

| Shape | SL | MS | AR |
|---|---:|---:|---:|
| `all_of` | 1 | 2 | 8 |
| `any_of` | 1 | 2 | 8 |
| mixed | 1 | 2 | 8 |

Read priority is heuristic. These results establish that the implementation
short-circuits and never exceeds the two comparison guards; they do not claim a
minimum possible read count.

## SimuHome G0

The pinned SimuHome checkout
`83d28837b69f0cbf1bc02ed5334cb8b561a9d54d` ran locally with its frozen
dependency lock. Through the public API, the adapter completed ten QT4 feasible
episodes with zero errors. Each successful episode exercised:

- reset from `initial_home_config`;
- clock and state reads;
- an immediate device command;
- `schedule_workflow`;
- virtual-clock fast-forward;
- workflow status retrieval.

Four additional candidate episodes were inspected before the ten supported
first actions were reached; the smoke output records them as
`skipped_no_supported_command`.

This gate establishes interface compatibility, not an end-to-end SimuHome
guard result. The full A and C experiments use the synthetic fallback because
the two-week core was designed to remain runnable when the external service is
absent.

## Planner preflight

Both planned planners were probed:

- `Qwen/Qwen2.5-7B-Instruct` at `127.0.0.1:8001` - connection refused.
- `Qwen/Qwen3-8B` at `127.0.0.1:8002` - connection refused.

The strict planner parser and OpenAI-compatible harness are implemented and
tested. No planner rows, utility estimates, or cross-family claims are reported
without model endpoints.

## Limitations

- Split-level safety is deterministic and has no sampling confidence interval.
- The synthetic core is not SimuHome end-to-end evidence.
- SimuHome does not expose device signatures. The proxy emulates the signature
  boundary; it cannot validate a real Matter deployment.
- The 12 safety rules are project policy, not appliance safety standards.
- PHYS is a concept-level baseline, not the original PAV or EVS system.
- The planner arm has only preflight and parser evidence in this environment.
- The work does not cover forged device keys, a compromised proxy, user-intent
  safety, or real hardware.

## Reproduction

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/freeze_v4_prereg.py --approve RealWayTrueX --check
python3 scripts/run_v4_core.py --check
python3 scripts/v4_simuhome_smoke.py \
  --simuhome-root /path/to/SimuHome --base-url http://127.0.0.1:8000
python3 scripts/run_v4_planner.py
```

The machine-readable core result is `artifacts/v4_core_results.json`. The raw
C1 and C2 row streams are represented by their SHA-256 digests in that file
and can be regenerated deterministically from the frozen source.
