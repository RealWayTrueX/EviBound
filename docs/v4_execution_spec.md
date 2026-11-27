# EviBound v4 execution specification

Status: implementation contract awaiting the new freeze.

This specification converts the two-week EviBound-T plan into executable work
packages. A work package is complete only when its file exists, its public
interface is covered by a test, and its acceptance command passes.

## Required data flow

1. The environment emits `(device, property, value, observed_at, sequence)`.
2. The proxy signs that tuple and appends it to an immutable record store.
3. The planner returns an action, one cited record per required fact, and a
   machine-readable `requires` expression.
4. At execution, the static rule expression is combined with `requires`.
5. EviBound-T assigns each cited condition true, false, or unknown from its physical
   lifetime, rereads only decision-dependent unknown facts, and then executes,
   defers, or rejects.
6. An independent oracle scores the actual environment state at execution.

## Interface

The v4 package is `src/evibound/external_v4/`.

| Module | Public responsibility |
|---|---|
| `model.py` | facts, comparisons, expressions, proposals, signed observations, decisions |
| `signing.py` | deterministic test signatures and forgery envelopes |
| `store.py` | append-only ingestion, signature/epoch/sequence checks |
| `lifetime.py` | lifetime formula, three-valued assignment, overshoot bound |
| `expressions.py` | all-of/any-of evaluation and unknown read ordering |
| `guards.py` | B0, PEEK, VER, FBS, PHYS, M, AR, MS, SL |
| `scheduler.py` | due-time evaluation, defer/retry loop and deadline reasons |
| `rules.py` | loads and validates the authoritative rule and rate table |
| `oracle.py` | execution-time independent scoring |
| `synthetic.py` | five-template counterfactual A group with event timing |
| `experiments.py` | A summary, seven ablations, C1 trajectory stress, C2 short-circuit reads |
| `simuhome_adapter.py` | unmodified SimuHome HTTP adapter and G0 smoke runner |
| `simuhome_experiment.py` | live SimuHome counterfactual A group |
| `planner.py`, `planner_b.py` | OpenAI-compatible B-group model-in-the-loop harness |

## Record format

```json
{
  "record_id": "current-humidity-2",
  "fact": "humidity",
  "value": 62.0,
  "observed_at": 0.0,
  "sequence": 2,
  "epoch": 1,
  "signature": "64 lowercase hex characters"
}
```

The store accepts a record only when the signature, epoch, future-time bound,
and strictly increasing per-fact sequence all pass. A replay never extends
evidence age.

## Proposal format

```json
{
  "proposal_id": "p-001",
  "action": {
    "device": "dehumidifier",
    "command": "set",
    "arguments": {"power": "on"}
  },
  "cites": {"humidity": "plan-humidity-1"},
  "requires": {
    "all_of": [
      {"fact": "washer", "operator": "eq", "value": "done"}
    ]
  }
}
```

Static safety rules are supplied by the proxy and combined by conjunction with
`requires`. The planner cannot remove them.

Condition truth is keyed by `(fact, operator, value)`, not by fact name. Two
predicates over the same fact therefore remain independent. One authenticated
reread can assign several conditions over that fact without overwriting them.

## Work packages and gates

| WP | Work | Acceptance |
|---|---|---|
| WP0 | Pin SimuHome commit and inventory 10 QT4 episodes | `scripts/v4_simuhome_smoke.py` reaches 10 successful external resets, reads, commands, schedules, clock advances |
| WP1 | Device-signed record store | forged, future-dated, wrong-epoch, and replayed records are rejected |
| WP2 | Static rules and independent oracle | all 12 rules have data declarations; oracle imports no guard module |
| WP3 | Lifetime and three-valued evaluator | formula tests pass; false/unknown assignment is conservative; window expiry uses its declared end |
| WP4 | EviBound-T short-circuit guard | context replay uses 1 read; transport freeze fails safe; no unsafe execution |
| WP5 | Baselines and ablations | nine guards plus seven ablations share one context interface; deterministic paired output |
| WP6 | Counterfactual A group | 50 dev and 200 holdout structures; 2,600 holdout scenarios |
| WP7 | C1/C2 pressure tests | C1 obeys overshoot bound; every case has `SL reads <= MS reads <= AR reads` |
| WP8 | B-group planners | two endpoint probes and strict model-in-the-loop runner on the UQ 4090 host |
| WP9 | Freeze and reporting | SHA-256 freeze file precedes holdout; result memo records passes and limits |

## Cut order if time or infrastructure is short

1. Keep WP0-WP7 and the freeze.
2. Drop B-group model execution before changing A or C definitions.
3. Drop PHYS before removing the four required perturbations.
4. Drop C3, C4, and the physically plausible forgery bonus.
5. Never run or report holdout before the preregistration freeze.
