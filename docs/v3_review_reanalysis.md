# v3 holdout: reanalysis after the independent review / 复核后的 v3 再分析

Status: **exploratory and post hoc.** It was written after the holdout results
and the 2026-11-03 review were known. The frozen v3 decisions in
`artifacts/week11_v3_holdout_results.json` are unchanged.

| Item | Value |
|---|---|
| Machine-readable record | `artifacts/week11_v3_review_reanalysis.json` |
| Script | `scripts/reanalyze_v3_review.py` |
| Input | the real holdout traces, `runs/week11_v3_holdout/episodes.jsonl` (sha256 `4bce8621…08e7`), 7,128 episodes, run on the UQ server |
| Oracle rescoring disagreements | 0 |

The script reuses the frozen estimand and bootstrap (`analyze.paired_contrast`):

- 36 physical-structure clusters;
- seeds matched and averaged within each cluster;
- 10,000 resamples, seed 20261011.

It reproduces the frozen S1, U1 and U2 estimates and intervals exactly.

## 1. One study, three ways to call joint feasibility

| Protocol | Safety | Utility endpoint | Utility result | Joint |
|---|---|---|---|---|
| Original (research contract, before amendment A2) | S1 +14.4 pp [+4.6, +25.9] supported | U1 raw goal completion | −7.4 pp [−19.0, +3.2] unsupported | **not supported** |
| Amended (frozen preregistration, A2) | same | U2 rule-compliant completion | +29.2 pp [+16.7, +43.1] supported | supported |
| Exploratory (this file) | same | U_dec safety-decoupled utility | +1.4 pp [−5.6, +8.3] inconclusive | **not supported** |

**U_dec definition.**

- Dual-device tasks: the full branch goal.
- Authorization-negative tasks: the authorized subgoal.
- Unsafe effects and authorization violations are not part of it; they are reported separately.

U_dec asks "did the user get what they could legitimately ask for", independently of how.

## 2. Why U2 favours any guard (review C-01)

Clean episodes, n = 216 per condition:

| Condition | Safe completion | Non-compliant completion (goal reached with an unsafe or unauthorized step) | Incomplete, no violation | Incomplete with a violation | Goal | U_dec |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 93 | 79 | 35 | 9 | 172 | 190 |
| M | 114 | 0 | 102 | 0 | 114 | 157 |
| B2_full | 157 | 0 | 59 | 0 | 157 | 194 |
| M_full | 156 | 0 | 60 | 0 | 156 | 193 |

A guard cannot execute an unsafe or unauthorized step, so it has no
non-compliant completions by construction. Because every cluster has the same
weight, the U2 contrast splits exactly into two parts:

| Part | Contrast | Estimate |
|---|---|---:|
| U1 (raw completion) | M_full − B0 | −7.4 pp |
| Non-compliant completions | B0 − M_full | +36.6 pp [+23.6, +50.5] |
| **U2 (sum)** | M_full − B0 | **+29.2 pp** |

U2 is therefore a valid *safe completion* rate, but most of its margin is the
baseline's rule breaking rather than added utility from the guard. Papers
should report it as "safe completion", next to U1 and U_dec, and should not
use it as the utility half of a joint-feasibility claim.

## 3. Safety-decoupled utility

| Contrast | Variant | Estimate | 95% CI | Rule applied | Reading |
|---|---|---:|---:|---|---|
| M_full − B0 | clean | +1.4 pp | [−5.6, +8.3] | non-inferiority (−5 pp) | inconclusive: lower bound just below the margin |
| B2_full − B0 | clean | +1.9 pp | [−5.6, +8.8] | non-inferiority | inconclusive |
| M − B0 | clean | −15.3 pp | [−27.8, −4.2] | non-inferiority | unsupported: the guard alone, without recovery aids, costs utility |
| M_full − M | clean | +16.7 pp | [+5.6, +30.6] | superiority | the aids recover that cost |
| M_full − B0 | perturbed | +25.5 pp | [+9.7, +41.7] | non-inferiority | under attack the guarded agent delivers more legitimate utility |
| M_full − B0 | boundary | −13.9 pp | [−24.1, −3.7] | non-inferiority | evidence expiring mid-plan costs utility (design effect; see J2 and J6) |

**Split by task type** (clean, M_full vs B0):

- Dual-device tasks, full goal: 135/144 vs 126/144.
- Authorization-negative tasks, authorized subgoal: 58/72 vs 64/72. Plain M reaches 64/72 here too, so the recovery aids cost six authorization-negative episodes. This is an exploratory observation for the v4 recovery design.

## 4. Sensitivity of the intervals (review C-04)

| Contrast | Percentile CI (frozen method) | BCa CI | Sign-flip p, one-sided | Null tested |
|---|---|---|---:|---|
| S1 | [+4.6, +25.9] | [+6.0, +28.7] | 0.008 | mean ≤ 0 |
| U1 | [−19.0, +3.2] | [−20.4, +2.8] | 0.667 | mean ≤ −5 pp |
| U2 | [+16.7, +43.1] | [+18.1, +44.4] | < 0.0001 | mean ≤ −5 pp |
| U_dec | [−5.6, +8.3] | [−5.6, +8.3] | 0.054 | mean ≤ −5 pp |

The decisions do not depend on the interval method. Permutation p-values use
100,000 Monte Carlo sign flips of cluster means.

## 5. How many independent structures a confirmatory utility test needs

Between-cluster standard deviation of the cluster-mean difference, and the
number of clusters needed for 80% power to show non-inferiority at −5 pp
(one-sided α = 0.025, i.e. the 95% CI lower bound):

| Endpoint | Cluster SD | True effect 0 | +2.5 pp | +5 pp | +10 pp |
|---|---:|---:|---:|---:|---:|
| U1 raw completion | 0.348 | 381 | 170 | 96 | 43 |
| U2 safe completion | 0.420 | 556 | 247 | 139 | 62 |
| **U_dec** | **0.223** | **157** | **70** | **40** | **18** |

U_dec is the least noisy endpoint. A v4 holdout with about 160 independent
physical structures can test it at a −5 pp margin even if the true effect is
zero. The 36 structures of v3 cannot, which is why U_dec is inconclusive here.

## 6. What may be claimed / 能说什么、不能说什么

**May be claimed**

- Under the fixed synthetic threat model, the evidence-bound guard removed every executed unsafe effect that the identical-rule guard allowed (S1). The result is robust to the interval method.
- With the recovery aids, legitimate task utility is on par with the unguarded agent within about ±8 pp. Non-inferiority at −5 pp is not established with 36 structures.
- The guard alone costs about 15 pp of utility; the aids recover it.
- Evidence expiring mid-plan costs about 14 pp on the boundary variant.

**Should not be claimed**

- "Joint feasibility" without naming the protocol.
- U2 as evidence that utility did not drop.
- Zero false blocks as evidence of precision (review C-03).
- Any per-modality or per-language effect (6 tasks per cell).

## 中文摘要

以下都是在复核之后用真实 holdout 轨迹做的**探索性、事后**分析，冻结的 v3 判定不变。

- **三种口径的联合判定。** 原定口径（S1 ∧ U1）不支持；修订口径（S1 ∧ U2）支持；与安全解耦的效用口径（S1 ∧ U_dec，事后定义）不支持。
- **为什么不支持。** U_dec 为 +1.4 pp [−5.6, +8.3]，下界刚好低于 −5 pp。
- **U2 的拆解。** U2 的 +29.2 pp 恰好等于 U1 的 −7.4 pp 加上 B0 的 36.6 pp 违规完成。它是"安全完成率"，不能当作"效用没有下降"的证据。
- **辅助措施的作用。** 只有守卫、没有恢复辅助时，解耦效用下降约 15 pp；三种辅助把它补回来（+16.7 pp）。
- **boundary 变体。** 证据在计划中途过期，带来约 14 pp 的效用代价。
- **区间方法。** 百分位区间、BCa 区间和置换检验给出同样的判定。
- **v4 规模。** 若以 U_dec 为主要效用终点，约需 160 个独立物理结构才能在 −5 pp 门槛上做确认性检验。v3 只有 36 个。
