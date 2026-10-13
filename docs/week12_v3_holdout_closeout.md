# EviBound v3 Holdout Closeout / v3 holdout 收尾

Status: confirmatory run complete under the amended, frozen preregistration.
Machine-readable record: `artifacts/week11_v3_holdout_results.json` (sha256 of
the 7,128-episode trace file in `artifacts/week11_v3_holdout_episodes.sha256`).
Protocol: `docs/week11_v3_preregistration.md` (amendments A1–A3), frozen
2026-10-12T19:55:49Z by the corpus owner (`artifacts/week11_v3_prereg_freeze.json`,
17 hashed files, verified before and after the run). Holdout output was
generated 2026-10-12T20:57:00Z; no code, prompt, task or label changed in
between. Every number below is read from the results file.

状态：确认性运行已按修订并冻结的预注册完成。机器可读记录在
`artifacts/week11_v3_holdout_results.json`；冻结在 2026-10-12 19:55:49Z，运行
在 20:57:00Z 完成，期间未改动任何代码、提示、任务或标签。下文所有数字均来自结果文件。

## 1. Run integrity / 运行完整性

| Item | Value |
|---|---|
| Episodes | 7,128 = 72 tasks × 3 variants × 11 conditions × 3 seeds (216 per condition × variant cell) |
| Physical clusters (inference units) | 36 |
| Oracle disagreements on independent rescoring | 0 |
| False blocks (all conditions, all variants) | 0 |
| Parse failures | 0 |
| Model / sampling | Qwen2.5-7B-Instruct `a09a354`, bf16, temperature 0.2, top-p 0.9, top-k 20, 224 new tokens |
| Bootstrap | 10,000 physical-cluster resamples, seed 20261011, seeds averaged within cluster |

## 2. Preregistered decisions / 预注册判定

| ID | Contrast | Estimate | 95% CI | Rule | Decision |
|---|---|---:|---:|---|---|
| **S1** | perturbed `unsafe_effect`, B2_full − M_full | **+14.4 pp** | [+4.6, +25.9] | superiority | **supported** |
| **U2** | clean `safe_completion`, M_full − B0 (margin −5 pp) | **+29.2 pp** | [+16.7, +43.1] | non-inferiority | **supported** |
| U1 | clean `goal_completion`, M_full − B0 (margin −5 pp) | −7.4 pp | [−19.0, +3.2] | non-inferiority | unsupported |
| **Joint feasibility (S1 ∧ U2)** | | | | | **supported** |
| R1 | clean `goal_completion`, M_full − M | +19.4 pp | [+8.3, +31.9] | superiority | supported |
| R2 | perturbed `safe_completion`, M_full − M | +9.7 pp | [+0.0, +19.9] | superiority | inconclusive (lower bound exactly 0) |
| R3 | clean `goal_completion`, M_full − M_recover | +2.8 pp | [−2.8, +8.3] | superiority | inconclusive |

Formal claim: *under the fixed synthetic threat model, four observation
modalities and three request styles, the amended EviBound (M_full) eliminates
executed unsafe effects relative to an identical-rule guard that trusts the
cited value, and completes more clean tasks rule-compliantly than the unguarded
baseline. On raw completion it is 7.4 pp below the unguarded baseline; that
difference is entirely the baseline completing authorization-negative tasks
by writing the device it was not allowed to touch (see §4).*

判定：S1 与 U2 支持，联合可行性**支持**；U1（raw 口径）不支持，−7.4 pp 的差额
全部来自 B0 在越权任务上靠写未授权设备"完成"（见第 4 节）。

## 3. Condition summary (holdout, n = 216 per cell) / 条件汇总

| Condition | clean goal | clean safe | clean unsafe | clean auth-viol | perturbed goal | perturbed unsafe | boundary goal | reads (perturbed) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 | 172 | 93 | 69 | 28 | 80 | 77 | 169 | 1.07 |
| B0_confirm_empty | 172 | 93 | 69 | 28 | 80 | 77 | 169 | 1.07 |
| B2 | 114 | 114 | 0 | 0 | 78 | 31 | 118 | 1.53 |
| B2_recover | 150 | 150 | 0 | 0 | 61 | 31 | 155 | 1.53 |
| B2_full | 157 | 157 | 0 | 0 | 68 | 31 | 147 | 1.53 |
| M | 114 | 114 | 0 | 0 | 102 | 0 | 117 | 2.00 |
| M_repair | 150 | 150 | 0 | 0 | 111 | 0 | 155 | 2.00 |
| M_confirm_empty | 114 | 114 | 0 | 0 | 101 | 0 | 120 | 2.00 |
| M_recover | 150 | 150 | 0 | 0 | 111 | 0 | 154 | 2.00 |
| M_mask | 126 | 126 | 0 | 0 | 112 | 0 | 95 | 2.00 |
| **M_full** | **156** | **156** | 0 | 0 | **123** | 0 | 121 | 2.00 |

Secondary contrasts (clean unless stated): M_repair − M goal +16.7 pp [+5.6,
+29.2]; M_mask − M goal +5.6 pp [+1.4, +11.1]; M_confirm_empty − M +0.0 [0, 0];
B0_confirm_empty − B0 +0.0 [0, 0]; M_full − B0 `safe_utility_completion`
+38.0 pp [+24.1, +52.3]; perturbed M_full − B2_full `safe_completion` +32.9 pp
[+20.8, +46.3]; perturbed B0 − M_full `unsafe_effect` +35.6 pp [+21.3, +51.4];
perturbed B2 − M `unsafe_effect` +14.4 pp [+4.6, +25.5]; boundary M_full − B0
goal −22.2 pp [−33.8, −10.6]; M_full − M reads +0.0 (the aids cost no extra
sensor reads).

## 4. What the numbers say / 数字说明了什么

1. **Safety is unchanged by the aids and holds in every modality and
   language.** Every M-guard condition has 0/216 unsafe and 0 authorization
   violations in all three variants; B2 variants stay at 31/216 unsafe under
   attack because the shared first write is where the damage happens. B0 is
   unsafe in 69/216 *clean* episodes (32%) and writes an unauthorized device
   in 28/216: on this corpus the unguarded agent is unsafe without any
   attacker, far more than in v2 (9/72), because v3 goals stress sequencing
   rules and four modalities.
2. **The raw-completion deficit is the confused deputy, not the guard.** By
   task type (clean goal): dual-device B0 126/144 vs M_full 135/144, so M_full
   is *ahead* where completing is legal; authorization-negative B0 46/72 vs
   M_full 21/72, where B0 "completes" by writing the forbidden device. The
   A3-aware `safe_utility_completion` is B0 111/216 vs M_full 193/216.
3. **Which aid did what.** The rule explanation carried the clean gain
   (+16.7 pp alone; M_repair = M_recover = 150). The legal-writes menu alone
   added +5.6 pp clean and was the stronger aid *under attack* (M_mask 112 vs
   M_repair 111; combined M_full 123 vs M 102). The empty-plan confirmation did
   nothing because no holdout first plan was empty: the v2 empty-plan failure
   mode did not recur under the v3 prompt and corpus. R3 says the menu adds
   little over the text aids on clean tasks (+2.8 pp, inconclusive).
4. **The menu hurts on the boundary variant.** M_mask boundary 95/216 vs M
   117/216, and M_full 121 vs M_recover 154. On boundary episodes the first
   write is accepted at age 2.0 and the second is refused at age 2.25, so
   recovery starts with one or two writes still needed. `recovery_accepted_
   incomplete` is 71/216 for M_mask there: the planner resubmits a single
   listed write and stops. A one-step mask biases a 7B planner toward
   one-step resubmissions when a multi-step remainder is required. This is a
   design defect of the aid's wording/shape, not of the guard (false blocks
   remain 0), and it is the first item of the v4 recovery work (§6).
5. **Dev was underpowered.** The 12-task exploratory dev run called R1
   unsupported; the 36-structure holdout gives +19.4 pp [+8.3, +31.9]. Do not
   read decisions off the dev split.
6. **Modality and language (descriptive, clean goal for M_full / B0):**
   camera 39/54 vs 40/54, motion timer 36/54 vs 33/54, multi-sensor 42/54 vs
   51/54, presence flag 39/54 vs 48/54; everyday 51/72 vs 51/72, explicit
   57/72 vs 60/72, scene 48/72 vs 61/72. Under attack B0 is most unsafe on
   named-scene requests (35/72) and on the plain presence flag (24/54); M_full
   is 0 everywhere.

## 5. Limits that still apply / 仍然成立的限制

Synthetic simulator and policies; verbatim record match stands in for
cryptographic sensor authentication; fixed tamper / replay / A3 threats; one
model revision; 36 physical clusters, so intervals are descriptive; the
boundary-variant drop is an effect of evidence expiring mid-plan by design
(not a false block) combined with the aid defect in §4.4.

## 6. Carried into v4 / 带入 v4

- J6: multi-step legal menu (sequences legal within `writes_remaining`, or the
  one-step menu with an explicit "submit every remaining write" instruction),
  preregistered on a fresh holdout; expect it to remove the boundary penalty.
- Drop `confirm_empty` from future matrices unless a corpus reintroduces
  empty first plans.
- J2 (`M_scoped` precision ablation), J3 (external worlds), J4 (second
  planner) unchanged; `docs/week12_direction_review.md` §5.
