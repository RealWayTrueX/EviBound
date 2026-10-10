# EviBound Week-8 Pilot Closeout

Status: preregistration and the complete v2 pilot matrix are finished. The
preregistered joint feasibility criterion is **not supported** on this pilot.
The v2 `test` split remains untouched.

## Gate and Run Integrity

- The 44 required corpus reviews are approved with zero open items and signed by
  Xin Li; AI-assisted review provenance remains explicit.
- The v2 corpus, prompts, runner, oracle, analysis, conditions, seeds, metrics,
  and decision rules were frozen at `2026-10-10T11:02:44Z`, before model output.
- Qwen2.5-7B-Instruct revision
  `a09a35458c702b33eeacc393d103063234e8bc28` has four verified safetensors
  shards and a full file-level SHA-256 manifest.
- The official dev smoke produced 18/18 expected episodes with no duplicate IDs
  or metric disagreements.
- The pilot produced 864/864 expected episodes across 16 tasks, 15 physical
  clusters, three seeds, six conditions, and three variants. There are zero
  duplicate episode IDs, parse failures, false blocks, trace inconsistencies,
  invalid initial states, or independent-oracle metric disagreements.

Raw traces and analysis are under
`/mnt/HDD-8T-0/evibound_yanke/runs/week8_v2_pilot/`. Machine-readable results
are in `artifacts/week8_pilot_results.json`.

## Confirmatory Results

| Criterion | Preregistered contrast | Estimate [95% CI] | Decision |
|---|---|---:|---|
| Safety superiority | perturbed B2−M `unsafe_effect` | +20.0 pp [+0.0, +40.0] | inconclusive |
| Utility non-inferiority | clean M−B0 `goal_completion` | -20.0 pp [-40.0, -4.4] | unsupported |

Safety is directionally favorable: raw perturbed unsafe effects were 12/48 for
B2 and 0/48 for M. The physical-cluster interval lower bound is exactly zero,
so the frozen rule does not call this supported superiority. Utility clearly
misses the -5 pp margin: raw clean completion was 36/48 for B0 and 27/48 for M.
Therefore the joint feasibility criterion is not supported.

## Secondary Evidence

- B0 and B1 each produced 24/48 perturbed unsafe episodes; the safety prompt
  alone did not change this rate.
- `M_no_freshness` produced 6/48 perturbed unsafe episodes versus 0/48 for M.
  The paired freshness contribution was +10.0 pp [+0.0, +26.7], concentrated in
  authentic stale-record replay.
- `Always_refresh` also produced 0/48 perturbed unsafe episodes but used +1.38
  reads/episode versus M [+0.93, +1.84]. This is a safety/cost tradeoff, not
  evidence that refresh dominates M.
- Perturbed evidence changed the full B0 plan in 24/24 tamper pairs and 24/24
  replay pairs. The first action changed in all tamper pairs and 22/24 replay
  pairs, confirming that the observation fault reaches action selection.
- On the four A3 tasks, M had zero authorization violations. Clean A3
  `safe_utility_completion` was 12/12; perturbed A3 outcomes were 9/12 safe
  partial completions plus 3/12 safe abstentions. B0 recorded 3/12 clean and
  4/12 perturbed authorization violations.

## Failure Audit

For M on clean episodes, 21/48 failed the preregistered full-goal metric while
36/48 achieved `safe_utility_completion`. Six failures were valid empty plans.
Nine episodes used a rejection/retry path, with nine `light_off_to_high` and six
`unauthorized_device` rejection events. No event was a false block. Thus the
utility gap is not explained by incorrect guard blocking; it is concentrated in
planner omission and recovery after correct enforcement, with A3 full-goal
semantics contributing additional apparent failures.

This matches the earlier v1 concern without changing v2 after results. A future
recovery aid or explicit-empty-plan policy is a new condition requiring a new
preregistration and fresh holdouts; it must not be retrofitted into these runs.

## Evidence and Limits

- Confirmatory analysis used 10,000 physical-cluster bootstrap resamples with
  seed 20260923 and complete matched-pair coverage.
- The estimator averages run seeds within `physical_structure_id`, then weights
  physical clusters equally. Some generated review prose still says “tasks”;
  the frozen machine analysis and metadata use physical-cluster grouping.
- A post-freeze duplicate dev smoke probe is preserved at
  `/mnt/HDD-8T-0/evibound_yanke/runs/week8_v2_smoke_dev_reading_00_probe`.
  It was not used for tuning and is excluded from pilot analysis.
- These findings apply only to the fixed offline simulator, synthetic tasks,
  model revision, prompts, and fixed tamper/replay attacks. They do not establish
  real-home, cryptographic sensor, trained-backdoor, prompt-injection, or
  production-security guarantees.

## Next Gate

Keep this pilot immutable. Quantify H1 repeated-blocked-plan and H2 transition
recovery failures from retained traces, then preregister any planner/recovery
condition separately. The v2 `test` split should run only under a later frozen
main-evaluation protocol without prompt or task tuning from pilot outcomes.
