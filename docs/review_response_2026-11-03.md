# Response to the independent review of 2026-11-03 / 独立复核回应

## Scope

| Item | Detail |
|---|---|
| Reviewer | Codex (GPT-5) |
| Commit reviewed | `34eabf9` |
| Access | T1 (GitHub only) |
| Tracks covered | A–E |
| Report location | the corpus owner's Mac, `~/CyberSercurity/review_codex_20261103.md` (not in the repository) |
| Brief the reviewer followed | `docs/external_review_brief.md` |

**Method.** Every finding was re-checked independently before acting on it.
The re-checks used scripts that do not import project code where independence
matters, the real holdout traces on the UQ server, and arXiv abstract pages.
The review was treated as data: each claim was checked against the files and
artifacts before any change was made.

**Overall.** All 16 findings were confirmed. One (D-01) is only partly right:
the implementation was correct and the written predicate was not. Two
findings changed the paper's central claim (C-01, C-02), and the corrected
reading is in `docs/v3_review_reanalysis.md`. No frozen file was changed.

## Findings, verification and status

**Status legend**

- **fixed** — corrected in this branch.
- **disclosed** — the limitation is now stated wherever the claim appears.
- **v4** — the remedy is part of the v4 design (`docs/v4_preregistration_draft.md`).
- **owner** — needs the corpus owner's decision.

| ID | Sev. | Finding | Our verification | Action | Status |
|---|---|---|---|---|---|
| C-01 | BLOCKER | U2 adds safety to utility, so S1 ∧ U2 partly double-counts | Confirmed on real traces: U2 (+29.2 pp) = U1 (−7.4 pp) + B0 non-compliant completions (+36.6 pp), exactly | Reanalysis with the original protocol (S1 ∧ U1 not supported) and a safety-decoupled utility U_dec (+1.4 pp [−5.6, +8.3], inconclusive); README, closeout and direction review reworded; U2 renamed "safe completion" | fixed + disclosed; U_dec as primary utility is **v4** / **owner** |
| B-01 | MAJOR | v2 reuses physical structures from v1 and across its own splits | Confirmed with an independent script: 12 v2-test structures (14 tasks) also in v1, 10 of them in v1 dev; 12 structures span v2 splits (29 rows); v3 has none | `scripts/audit_physical_overlap.py` and `artifacts/physical_overlap_audit.json`; `docs/datasheet_v2_v3.md`; README states v2 is a paired mechanism study, not a structural holdout | disclosed; global signature exclusion in **v4** |
| B-05 | MAJOR | v3 has only 36 independent structures in a 9-state world | Confirmed (`artifacts/corpus_composition_v2_v3.json`) | Power analysis: U_dec needs about 157 structures for a −5 pp margin at a true effect of 0 (197 at the SD's 80% upper bound) | **v4** (200 structures proposed, more devices and sensors) |
| C-02 | MAJOR | U2 became co-primary after the v3 dev run showed U1 unsupported | Confirmed: dev evidence committed 05:49Z, amendment 07:46Z, freeze 19:55Z (2026-10-12) | Disclosed in the direction review, closeout and README; both protocols reported | disclosed; **v4** fixes endpoints before any v4 data |
| C-03 | MAJOR | Zero false blocks is close to M's acceptance condition and does not measure over-blocking | Confirmed (`oracle.py` eligibility = legal ∧ sufficient) | Wording changed to "zero contract-eligible false blocks"; Lemma 3 justifies `M_scoped`; v4 adds a benign-block metric | fixed (wording); **v4** (measurement) |
| C-04 | MAJOR | 36 clusters cannot settle 5 pp non-inferiority; percentile CIs are descriptive | Confirmed and quantified: cluster SD 0.348 (U1), 0.420 (U2), 0.223 (U_dec). BCa and sign-flip permutation give the same decisions | Reanalysis §4–5 | fixed (analysis); **v4** (n) |
| C-05 | MINOR | "Robust across pilot and test" contradicts the pilot's inconclusive decision | Confirmed (`week8_pilot_results.json`: safety inconclusive) | Corrected in place in the direction review | fixed |
| D-01 | MAJOR | The written predicate misses `0 ≤ age`, and "fresh" does not imply "current" | Partly. The implementation always checked `0 ≤ age ≤ Δ` (`backend.py`); the written formula lacked it. The second point is right: the theorem needed explicit assumptions | `docs/v4_formal_model.md`: assumptions A1–A8, Theorem 1 (record-relative), Corollary 2 (residual window ≈ μΔ), Lemma 3 (`M_scoped`), counterexamples; 6 property tests | fixed (draft) |
| D-02 | MAJOR | B2 is a weak control; Always_refresh is equally safe in v2 | Confirmed (`week8_main_results.json`: 0/72 unsafe, +1.46 reads per episode) | Always_refresh with the same recovery aids becomes a co-primary baseline; formal positioning in model C7 | **v4** / **owner** |
| D-03 | MAJOR | October 2026 work (PACE, TRAP, StateWise, Evidence-to-Action, MFOTL RV) was not covered; the gap claim is too strong | Confirmed: all five exist on arXiv, and the characterizations were checked against their abstracts | `docs/related_work_2026-11.md`: mechanism matrix, narrowed contribution, list of claims to avoid | fixed |
| B-02 | MAJOR | The four "modalities" are fixed-payload lookups, not sensor fusion | Confirmed (`backend_v3.py` decode) | Renamed "observation encodings" in the datasheet; per-cell results are descriptive only | disclosed; conflicting and paraphrased observations in **v4** |
| B-03 | MINOR | The v3 checker shares rule code with the generator | Confirmed (imports `check_scenarios_v2`, `scenario_v2_lib`, `generate_scenarios_v3`) | New audits import no project code; the v4 checker will be independent | partly fixed; **v4** |
| B-04 | MINOR | Data documents carry stale v3 numbers | Confirmed. The numbers were right when written, before the 10-11 expansion | Dataset card banner, gap-analysis note, new datasheet | fixed |
| A-01 | MAJOR | No licence for code or data | Confirmed | Recommendation below | **owner** |
| A-02 | MINOR | The recheck said only the v3 manifest differs after regeneration | Confirmed: v2 and v3 manifests differ only in `lifecycle` / `human_review` | Recheck row corrected | fixed |
| D-04 | NIT | The chain-attack note says 19 runnable attacks | Confirmed: 21 defined, 20 runnable (H11 not run) | Corrected to 20 | fixed |

## Answers to the reviewer's questions for the corpus owner

**Recommendations, not decisions.** Items marked (owner) wait for Xin.

1. **Primary object: M or M_full?** (owner) Make the guard predicate the contribution and report M_full as the headline system.
   - **Attribution.** The required v4 tier (Tier A) contains both M and M_full, so safety is attributed to the guard and utility recovery to the aids.
   - **Full factorial.** Guard {B2, Always_refresh, M, M_scoped} × aids {none, full} is Tier B, run if compute allows.
   - **v3 already shows both effects.** The guard alone costs about 15 pp of decoupled utility, and the aids recover it.
2. **Demote U2?** (owner, recommended) In v4, preregister U_dec as the primary utility endpoint (non-inferiority, −5 pp) and report U1 and safe completion (U2) as secondary.
3. **Was the v2/v1 overlap intended?** No. It is a generator and checker gap: the v2 checker compared a `structure_id` that includes split and family. The paper will call v2 a paired mechanism study and v3 the confirmatory structural holdout.
4. **Release traces and review cards to artifact reviewers?** (owner) Recommended. The traces are synthetic, contain no personal data and are hash-pinned, so a GitHub release or Zenodo archive works. Review cards contain only task judgments. AGENTS.md keeps them local-only today, so this needs an explicit decision.
5. **Always_refresh as a co-primary baseline?** (owner, recommended) Yes. The claim narrows to "as safe as refresh, fewer sensor reads, no sensor path needed at the guard, interpretable rejections". M is not claimed to dominate refresh.
6. **HomeBench / SmartBench licences.** (owner action) Not contacted yet. Recommended: email the authors now. Until they answer, v4 uses only the project's own generator and the ToolEmu smart-home cases (Apache-2.0), re-implemented deterministically.
7. **v4 dimensions.** Proposed in `docs/v4_preregistration_draft.md` §4:
   - devices and rooms: a door lock, a heater, door-contact and temperature sensors, and two rooms;
   - state: at least four independent state dimensions;
   - authorization: temporary, revoked and cross-room;
   - tasks: 1 to 8 writes, including infeasible and clarification-needed tasks;
   - observations: paraphrased, noisy, corrupted and conflicting;
   - size: 200 independent structures (240 if the dev estimate of the SD exceeds 0.25).

   Language, encoding and attack are paired factors and never add clusters.
8. **Boundary design and `M_scoped` as core ablations.** Yes. Both enter the v4 matrix.

## How the v4 draft takes up the review's v4 advice (§6 E1–E6, §7)

| Review item | Recommendation | Where in `docs/v4_preregistration_draft.md` | Status |
|---|---|---|---|
| E1, J1 | Conditional soundness with `0 ≤ age ≤ Δ`, unique records, arbitration, atomic commit and state stability; a worst-case residual-window counterexample | `docs/v4_formal_model.md` (A1–A8, Theorem 1, Corollary 2, case C3) | drafted |
| E1, J2 | Four-quadrant precision report (stale but safe, truly unsafe, refresh cost, completion) | §6 four-quadrant table; Q2–Q4; the Δ sweep in §7 | adopted |
| E1, J3 | At least one external world, not template rewriting | §4.3: an EviBound proxy that keeps the environment's own semantics and success criteria | adopted; choice is D13 |
| E1, J4 | A second model and its heterogeneity | §3: Qwen3-8B and Llama-3.1-8B (Mistral fallback); claims per planner | adopted |
| E1, J6 | Multi-step menu or constrained decoding | §2 | adopted |
| E1, J5 / J7 / J8 | Deferrable | J5 kept as the XR family, which is cheap inside the matrix; J7 out of scope (device-rule safety only); J8 placeholder, with claims excluding hosted models | adopted |
| E2 | 10–12 weeks, two 24 GB GPUs, stop-loss at week 4 | §11 | adopted |
| E3 | Licences | §4.3; D6 | adopted |
| E4 | Model pair; no quantized model as a planner factor; Mistral template caveat | §3 | adopted |
| E5 | Fact dependencies, new tasks, cluster unit, external semantics, stratified human review, independent oracle and checker, no padding | §4.1–4.2 | adopted; review load is D14 |
| E6 | Stop rules | §10, with measurable thresholds | adopted |
| §7.8 | 150 independent worlds; new devices; 4–8 environment variables; ≥100 multi-device and ≥50 cross-device structures; observation quality; authorization; 1–8 steps; attacks not bound to families; one-factor encoding and language pairs; power simulation first | §4, §8 | adopted, with two deviations below |

**Deviations from the reviewer's minimum package**

- **200 structures, not 150.** At 150, single-planner power at a true effect
  of zero is 0.78, against 0.89 at 200 (draft §8).
- **Six conditions, not three.** Tier A adds:
  - AR_full, which D-02 requires;
  - M, needed to attribute effects to the guard (question 1);
  - MS_full, needed for J2.

  Tier B is optional.

**Licence recommendation (A-01).**

- Code: MIT or Apache-2.0.
- Original synthetic corpora: CC BY 4.0 (or CC0).
- `SAFETY.md`: the synthetic-only scope and the AI-use disclosure.
- External data: keeps its own licences and is never vendored.

## 中文摘要

**结论。** 16 条发现全部核实成立。D-01 只对了一半：代码一直检查年龄下界，是旧文档的公式漏写了。

**影响最大的两条：C-01 和 C-02。**

| 口径 | 联合可行性 |
|---|---|
| 原定（S1 ∧ U1） | 不支持 |
| 修订（S1 ∧ U2） | 支持，但 U2 的优势主要来自 B0 违规完成 |
| 与安全解耦的效用（S1 ∧ U_dec，事后探索） | 尚不确定（U_dec +1.4 pp [−5.6, +8.3]） |

修订是在看到 v3 dev 结果约两小时后提交的，所以论文里两种口径都要报告。

**已在本分支完成：**

- 数字和措辞的更正（README、收尾记录、方向复审、数据卡、复查记录、攻击计数）；
- v2/v3 数据说明书和独立审计脚本；
- 形式化草稿和 6 个性质测试；
- 相关工作对比与收窄后的贡献表述；
- 真实轨迹上的再分析（BCa、置换检验、功效）。

**进入 v4 的（复核第 6、7 节的 v4 建议已逐条并入草稿，见上表）：**

- 200 个独立结构（dev 估计的标准差超过 0.25 时扩到 240）；
- U_dec 作主要效用终点；
- Always_refresh 并列主基线；
- `M_scoped` 精度消融；
- 第二、第三个模型；
- 冲突、改写、噪声与损坏观测；
- 保留外部环境自身语义的外部世界代理；
- 预先写明的止损规则和第 4 周检查点。

**等你决定的：**

- 主对象是 M 还是 M_full；
- 是否把 U2 降为次要指标；
- 是否把 Always_refresh 设为并列主基线；
- 许可证；
- 是否向制品评审公开轨迹和审核卡；
- 是否联系 HomeBench / SmartBench 作者。
