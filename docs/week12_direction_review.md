# Week-12 Direction Review: Gap, Positioning, Amendments, and the Road Past the Course
# 第 12 周方向复审：缺口、定位、修订与课程之后的路线

Date: 2026-10-12. Status: review record, not a frozen protocol. It explains
why the v3 preregistration was amended before its freeze (A1–A3 in
`week11_v3_preregistration.md`), where the research gap sits in the 2024–2026
literature, which external datasets can be joined later, and what a
venue-grade version of EviBound would need. Nothing here touches v2 (frozen)
or the v3 holdout.

日期 2026-10-12。本文是复审记录，不是冻结协议。它说明 v3 预注册在冻结前为何
修订（A1–A3）、研究缺口在 2024–2026 文献中的位置、以后可并入的外部数据集，以及
把 EviBound 做到会议水平还缺什么。不改动已冻结的 v2，也不碰 v3 holdout。

---

## 1. What the results so far actually say / 现有结果到底说明了什么

### 1.1 Safety (v2 formal test, public record)

Perturbed episodes: B2 30/72 unsafe vs M 0/72; cluster effect +36.4 pp
[+18.2, +59.1]. The freshness ablation carries +22.7 pp of that on its own
(M_no_freshness 18/72 unsafe). Always_refresh is equally safe (0/72) at
+1.46 reads/episode. Zero false blocks in 1,296 episodes, including the
boundary variant (age exactly 2). **Supported, and robust across pilot and
test.**

### 1.2 Utility: the gap is a metric artefact, then a planner-recovery problem

Clean episodes, from `artifacts/week8_main_results.json`:

| Metric (clean, n=72 each) | B0 | M |
|---|---|---|
| `goal_completion` (raw; credits rule-breaking completions) | 53 | 44 |
| `safe_completion` (goal reached, no unsafe/unauthorized transition) | **44** | **44** |
| `safe_utility_completion` (A3-aware) | 53 | 56 |

Every one of the nine B0-only completions executed an off→high jump or a
fan-high-without-indicator transition that the task prompt forbids
(`week11_v2_failure_taxonomy.json`: B0/clean has 9 unsafe completions; M/clean
rejections were `light_off_to_high` 9, `fan_off_to_high` 6,
`fan_high_requires_indicator` 6, and `recovered_goal_after_rejection = 0`).
So:

1. On rule-compliant completion M is exactly non-inferior to B0 (0 pp).
2. The raw-completion deficit exists only because B0 is credited for
   completing by breaking stated rules.
3. What M actually loses is the *repair*: the 7B planner, told only "write
   rejected: light_off_to_high", never fixed its plan (0/12 clean), and under
   attack 27/66 resubmissions after a correct evidence rejection were empty.

The exploratory v3 dev run (8 draft conditions, 864 episodes) reproduced the
pattern: S1 safety supported, R1 (text explanation) not supported, U1 not
supported. A rule *explanation* is not enough for this planner.

安全结论稳固（v2 正式测试 30/72 vs 0/72，零误拦）。效用缺口首先是口径问题：
按“合规完成”口径 B0 与 M 都是 44/72；B0 多出的 9 次“完成”全是违反 R4/R5/R6
直跳完成的。其次是修复问题：模型被正确拒绝后 0/12 修好计划，受攻击时 27/66 次
重提交是空计划。v3 开发集显示“只解释规则”不够。

### 1.3 Outcome of the amended holdout (added 2026-10-13) / 修订后 holdout 的结果

The holdout ran the same day under the frozen amended protocol
(`docs/week12_v3_holdout_closeout.md`): joint feasibility **supported** for
the first time (S1 +14.4 pp [+4.6, +25.9]; U2 +29.2 pp [+16.7, +43.1]);
R1 +19.4 pp [+8.3, +31.9]; U1 −7.4 pp [−19.0, +3.2] unsupported, and that
deficit is entirely the unguarded baseline writing forbidden devices on
authorization-negative tasks (dual-device tasks: M_full 135/144 vs B0
126/144). Two findings revise §3 below: the rule explanation, not the menu,
carried the clean gain (dev was underpowered), and the one-step menu *hurts*
on the boundary variant (M_mask 95/216 vs M 117/216) by biasing the planner
toward single-write resubmissions when two writes remain. Zero false blocks
in 7,128 episodes.

修订后的 holdout 当天跑完：联合可行性首次支持；R1 支持；U1 不支持但差额全部来自
B0 在越权任务上的越权"完成"。两点修正下文第 3 节的预期：清洁任务上的增益主要来自
规则说明而非清单（开发集功效不足）；一步清单在 boundary 变体上反而有害（模型倾向
只重提交一步）。7,128 回合零误拦。

### 1.4 Consequences for the plan / 对计划的影响

- The v3 holdout as drafted would most likely have confirmed a negative
  (text aids do not help), spending the only confirmatory run on it.
- Both problems have standard remedies in the literature that do **not**
  change the guard: a goal-agnostic *action mask* (Safety Chip, ICRA 2024;
  shield synthesis) for the repair problem, and a *rule-compliant* utility
  criterion for the metric problem (AgentDojo reports utility and security
  separately; τ-bench scores policy compliance, not raw completion).
- Hence amendments A1–A3, made before the freeze and justified only from the
  public v2 record.

---

## 2. The gap, stated precisely / 缺口的精确表述

**Claim being made.** A deterministic enforcement point between an LLM
planner and physical actuators should accept a write only if the planner's
*cited* observation (i) is verbatim present in a trusted, immutable record
store (provenance), (ii) is younger than a bound Δ at the moment of commit
(freshness), and (iii) together with the trusted actuator ledger satisfies the
stateful device rules and the authorization scope. We call this
**evidence-bound actuation**. The soundness property it buys is narrow and
honest: *under a channel-fault model where the attacker controls everything
between the store and the model but not the store itself, every executed
write is rule-compliant with respect to a genuine world reading taken at most
Δ before commit.* The residual risk is the Δ window, which is a parameter,
not an assumption.

**What exists (checked 2026-10-12; abstracts/venue pages verified, see
references).** Twenty-seven runtime guards, shields and benchmarks from
2024–2026 were read for five properties: (a) provenance/authenticity of the
observation, (b) temporal validity of the data an action depends on, (c)
stateful physical rules per action, (d) repair feedback to the planner, (e)
reported utility cost.

| Family | Representative systems | a | b | c | d | e | Why it is not this |
|---|---|---|---|---|---|---|---|
| Policy/privilege guards for tool agents | AgentSpec (ICSE 2026), Progent, ShieldAgent (ICML 2025), GuardAgent (ICML 2025), VeriGuard, Conseca (HotOS 2025), LlamaFirewall | N/P | N | N/Y | Y/P | Y | Check the action and the agent's own trajectory; take observations on trust; no notion of age at commit |
| Provenance / IFC | CaMeL, ProvenanceGuard (ASE 2026), AGATE, Google agent-security whitepaper | P | N/P | N | P | Y/P | Track *where data came from* or whether an argument is derivable from context; never verify a cited record against a trusted store, no age bound |
| Embodied shields | Safety Chip (ICRA 2024), RoboGuard (RA-L 2026), VIRF (ICLR 2026), RoboSafe, ProbGuard, PanelShield | N | N | Y | Y/P | Y | Physical rules per action, but the world model is assumed correct (RoboGuard says so explicitly; VIRF uses a hand-verified scene graph) |
| Freshness / TOCTOU (all 2025–2026, all digital) | Mind the Gap (NeurIPS 2025 wksp), **CommitGuard** (2607.10487), **Stale≠Unsafe** (2609.29522), **Freshness-Bounded Shield** (2608.26306), CapLease, ContractBench, Concord (2610.05281) | N/P | Y | N/P | P | Y | Nearest neighbours. CommitGuard binds a *witness* to a commit with a validity window (browser/API tasks, Qwen2.5-7B) but trusts runtime-emitted signals; FBS bounds the age of a *verdict* in self-adaptive systems; Stale≠Unsafe shows that freshness-only guards over-block benign races in infrastructure. None covers physical actuation, verbatim provenance, or stateful device rules. |
| Smart-home agent work | SimuHome (ICLR 2026), HomeBench (ACL 2025), SmartBench, "Increasing Resilience of Smart Home Agents" (2610.04923) | – | – | – | – | – | Benchmarks and prompting/fine-tuning studies; no enforcement layer, no sensor-integrity threat model (the resilience paper has a "sensor disagreement" category but no guard) |

Two 2026 surveys name the hole: the embodied-agent security survey
(2608.16843) lists "world-state integrity" as comparatively underexplored and
"state provenance" as an open challenge; the specification/verification
survey (2608.14590) finds runtime monitoring the most mature enforcement but
no system doing observation provenance or TOCTOU.

**So the gap is real but narrow, and must be stated as the combination.**
Any one ingredient has prior art (CaMeL for provenance, CommitGuard/FBS for
freshness, Safety Chip for physical shields). The contribution is the
conjunction at the physical write, the paired attack/clean evaluation with a
non-inferiority criterion, and the finding that the binding is perfectly
safe while the *planner's* recovery is the bottleneck.

缺口是真的，但要说得窄：单项都有先例（CaMeL 做来源，CommitGuard/FBS 做新鲜度，
Safety Chip 做物理动作屏蔽）；没有任何系统在每次物理写入前同时做“引用记录逐字
比对 + 提交时刻年龄上界 + 有状态设备规则”。最近的三篇（2026 年 7–9 月）全在数字域。
两篇 2026 综述把 world-state integrity / state provenance 列为未解问题。

### 2.1 The critique we must answer: "stale ≠ unsafe"

Stale≠Unsafe (2609.29522) reports that freshness-only guards block 92–95% of
benign state races and forfeit up to 43% of safe completions in infrastructure
tasks, and argues for semantic commit predicates instead. EviBound's answer is
already partly in the data: M evaluates the semantic predicate (the six rules)
*on the validated evidence*, and the boundary variant (age exactly Δ) produced
zero false blocks. The remaining exposure is that M refuses a stale-cited
write even when the write's rule does not read the observation (e.g. fan=low,
light=off). Section 5 proposes `M_scoped` to measure exactly that cost. This
is the one place where a reviewer can say "your guard is imprecise", so the
measurement belongs in the paper.

### 2.2 The critique "why not just refresh?"

Always_refresh is as safe as M at +1.46 reads/episode. The honest positioning:
(1) refresh silently executes a plan that was chosen on wrong evidence as long
as it is rule-safe (Always_refresh/perturbed: 14 accepted-but-incomplete
plans), whereas M's rejection *names the fault* and triggers re-planning; (2)
refresh needs the enforcement point to own a sensor path, which in a
hub/integration architecture is a separate trust assumption; (3) the cost
argument strengthens when the "sensor" is a captioning or fusion pipeline
(v3's camera/multi-sensor modalities make this concrete). Report all three;
do not claim M dominates refresh.

---

## 3. Why the amended v3 is likely to work / 修订后的 v3 为什么大概率可行

1. **Mechanism fits the failure.** The two dominant failures are "empty plan
   after evidence rejection" (27/66) and "same-device off→high repeated or
   rejected again" (12 clean rejections, 0 repaired). A one-step legal-writes
   menu converts both into a selection problem: the planner sees, e.g.,
   `[{fan:low}]` when nobody is present, or `[{fan:low},{light:low}]` when
   someone is, and only has to chain listed moves. Safety Chip reports
   VirtualHome success 90%→98% with masking plus explanation; VIRF reports
   ≈1.1 repair iterations with a structured diagnostic.
2. **Nothing leaks.** The menu is computed by the guard's own predicate
   from the trusted reread; it contains no goal and no route, so the
   guard/oracle independence and the "guard cannot see the goal" invariant
   hold (unit-tested: the menu under M after a tamper attack lists only
   presence-false moves).
3. **Fairness holds.** `B2_full` receives the same three aids; budgets are
   unchanged; first proposals are shared; the eight draft conditions are
   byte-identical to the dev run, so ablations remain interpretable.
4. **The utility criterion matches the question.** U2 asks whether the
   guarded agent completes tasks *the way the task says they must be
   completed*; U1 stays visible so nobody can accuse the study of hiding the
   strict number.
5. **Cost is trivial.** 7,128 episodes reuse 648 shared first proposals;
   v2's 1,296-episode matrix ran in three minutes on one GPU.

Risks (written before the run): the 7B planner may still fail to chain two
listed moves within one resubmission. **What happened:** R3 was flat on
clean tasks (+2.8 pp, inconclusive) and the menu alone lowered boundary
completion (95 vs 117), confirming the risk in the multi-step case; under
attack the combination was still the best condition (123 vs 102). The fix is
J6 in §5.

---

## 4. Datasets that can be joined / 可并入的外部数据集

Survey of 27 candidates (licences read where visible). Ranked for a
course-scale extension (one 24 GB GPU, ~2 weeks) and for a later venue run.

| Rank | Dataset | Venue / licence | What it adds | Ingest path | Effort |
|---|---|---|---|---|---|
| 1 | **HomeBench** (BITHLP/HomeBench) | ACL 2025 main; **no LICENSE file** – ask authors | 100 homes, ≥47 devices each, valid *and invalid* (non-existent device/function) instructions → fixes the 2-device world and the single template | Import room/device state blocks as world files; map expected calls to EviBound writes; invalid cases become A3-style unauthorized/non-existent targets | low–med |
| 2 | **ToolEmu** smart-home cases | ICLR 2024; **Apache-2.0** | 18 cases (GoogleHome 5, AugustSmartLock 6, IndoorRobot 7) with risk annotations and *time-windowed guest access* | Re-implement the three toolkits deterministically (no LM emulator); lock guest windows become freshness-bounded authorization scopes | med |
| 3 | **SimuHome** | ICLR 2026 oral; **CC BY-NC-ND 4.0** | Executable, time-accelerated home with 17 Matter device types and environmental sensors; feasible/infeasible queries | Run EviBound as a proxy around its tool server; log every read into the trusted store; inject tamper/replay in the proxy. Publish proxy code + numbers only; never redistribute modified episodes | med |
| 4 | **SmartBench** | arXiv 2603.06636; no licence | 4,400 samples with *timestamped* device/sensor streams and normal/anomalous labels | Timestamps give realistic inter-event gaps for replay; anomalies are third-party "implausible value" labels | low–med |
| 5 | **Home-Assistant-Requests-V2** (acon96) | community; **MIT** | 240k templated requests, 3 personas, 5 languages, HA tool schema | Instruction-style diversification only | low |
| (venue) | **AgentDojo** suite | NeurIPS 2024 D&B; **MIT** | Standard injection attack/defence harness | Ship a `smart_home` suite so EviBound is scored in the common framework (TOCTOU-Bench was built this way) | med |
| (venue) | **Agent-SafetyBench** household subset | MIT | Failure mode M9 "over-trusting tool results" | Wrap tool returns with the guard; report M9 reduction | med |

Not usable or low fit: SAGE (no public data), SMH-Bench / DevicesWorld /
PersonalHomeBench (not yet released or ND), ASB / InjecAgent / R-Judge (no
physical state), HAZARD / SafeAgentBench simulators (heavy 3D, text-only
hazard taxonomy still useful for rules).

Design principle for all of them: EviBound's record store, Δ and rule set are
*ours*; external datasets supply worlds, instructions and third-party
ground truth. Attacks are injected at the proxy so no licensed data is
modified.

课程阶段先做 HomeBench（世界与无效指令）和 ToolEmu 的 18 个家居用例（Apache-2.0，
带时间窗权限）；SimuHome 只作外部环境、不改其数据。会议阶段再加 AgentDojo
`smart_home` suite 与 Agent-SafetyBench 家居子集。

---

## 5. v4: what a venue-grade EviBound needs / 会议级版本还缺什么

1. **Formal statement.** Define the guard as a predicate
   `G(w, c, t_c) = c ∈ Store ∧ t_c − c.t ≤ Δ ∧ Rules(ledger, w, c.value) ∧ w.device ∈ Auth`
   and prove the per-write soundness in §2 for the channel-fault model; state
   explicitly that the store, clock and ledger are the TCB and that Δ is the
   residual window. Position against CommitGuard (witness freshness, digital)
   and FBS (verdict age) as the two nearest formalisations.
2. **Precision ablation `M_scoped`.** Require fresh evidence only for writes
   whose rule evaluation reads the observation (R1, R2). Report benign-block
   rate and goal completion against M and Always_refresh. This answers
   Stale≠Unsafe directly.
3. **Second planner family.** Repeat the frozen v3 holdout with one more
   open model (Qwen3-8B or Llama-3.1-8B-Instruct), same revision-pinning,
   seeds and budget. A one-model result is a course result.
4. **Bigger world.** Third device (thermostat or lock) and a second sensor
   so the number of independent physical structures grows beyond 36 — the
   true limit on statistical power (v2 test: 22 clusters).
5. **Memory-channel replay.** The one in-scope attack family not yet tested:
   the stale reading arrives through conversation history while the sensor
   read is fresh (gap-analysis item 4; also what Concord and STALE study for
   software context).
6. **External validation** per §4, starting with HomeBench + ToolEmu, then
   SimuHome behind a proxy.
7. **J6 — recovery beyond a one-step mask** (now required by the holdout):
   a multi-step legal menu (sequences legal within `writes_remaining`) or the
   one-step menu with an explicit "submit every remaining write" instruction,
   then constrained decoding of the action list to the legal set (Agent-C
   style) or guard-side insertion of the mandatory intermediate step on the
   same device (a conservative shield-with-correction). Drop `confirm_empty`
   unless a corpus reintroduces empty first plans.

Target venues, by framing: USENIX Security / NDSS / CCS (enforcement +
threat model + precision), or ICLR / NeurIPS D&B if the multi-dataset suite
becomes the main artefact.

---

## 6. Decisions for the corpus owner / 需要负责人拍板的事项

All three were taken on 2026-10-12: A2 kept (`JOINT_IDS = ('S1', 'U2')`),
dev rerun for the new conditions, freeze approved by the corpus owner and
verified before and after the holdout. Remaining decision: whether the
course deliverable stops here or includes J6 on a fresh preregistered
holdout.

三项决定已于 2026-10-12 完成（保留 A2、补跑 dev、负责人批准冻结）。剩下的决定：
课程交付是否到此为止，还是再做一轮带 J6 的新 holdout。

---

## References (all checked against abstract or venue page on 2026-10-12)

- AgentSpec, ICSE 2026 — https://arxiv.org/abs/2503.18666
- Progent — https://arxiv.org/abs/2504.11703
- ShieldAgent, ICML 2025 — https://arxiv.org/abs/2503.22738
- GuardAgent, ICML 2025 — https://arxiv.org/abs/2406.09187
- LlamaFirewall — https://arxiv.org/abs/2505.03574
- Conseca, HotOS 2025 — https://arxiv.org/abs/2501.17070
- VeriGuard — https://arxiv.org/abs/2510.05156
- CaMeL — https://arxiv.org/abs/2503.18813
- ProvenanceGuard, ASE 2026 — https://arxiv.org/abs/2607.01236
- AGATE — https://arxiv.org/abs/2609.30830
- Google, An Introduction to Google's Approach for Secure AI Agents (2025) — https://research.google/pubs/an-introduction-to-googles-approach-for-secure-ai-agents/
- Safety Chip, ICRA 2024 — https://arxiv.org/abs/2309.09919
- RoboGuard, IEEE RA-L 2026 — https://arxiv.org/abs/2503.07885
- VIRF, ICLR 2026 — https://arxiv.org/abs/2602.08373
- RoboSafe — https://arxiv.org/abs/2512.21220
- ProbGuard — https://arxiv.org/abs/2508.00500
- Agent-C (ICLR 2026 workshop) — https://arxiv.org/abs/2512.23738
- Mind the Gap: TOCTOU in LLM agents (NeurIPS 2025 workshop) — https://arxiv.org/abs/2508.17155
- CommitGuard: Temporary Authority, Permanent Effects — https://arxiv.org/abs/2607.10487
- Stale Does Not Mean Unsafe — https://arxiv.org/abs/2609.29522
- Approved Too Late / Freshness-Bounded Shield — https://arxiv.org/abs/2608.26306
- CapLease — https://arxiv.org/abs/2608.01710
- ContractBench — https://arxiv.org/abs/2605.17281
- Concord: When Agent Context Goes Stale — https://arxiv.org/abs/2610.05281
- Increasing Resilience of Smart Home Agents — https://arxiv.org/abs/2610.04923
- Survey: Security of FM-Powered Embodied Agents — https://arxiv.org/abs/2608.16843
- Survey: Toward Safe LLM Agents (specification/verification/enforcement) — https://arxiv.org/abs/2608.14590
- SimuHome, ICLR 2026 — https://arxiv.org/abs/2509.24282 ; https://github.com/holi-lab/SimuHome
- HomeBench, ACL 2025 — https://arxiv.org/abs/2505.19628 ; https://github.com/BITHLP/HomeBench
- SmartBench — https://arxiv.org/abs/2603.06636
- ToolEmu, ICLR 2024 — https://arxiv.org/abs/2309.15817 ; https://github.com/ryoungj/ToolEmu
- AgentDojo, NeurIPS 2024 D&B — https://arxiv.org/abs/2406.13352 ; https://github.com/ethz-spylab/agentdojo
- Agent-SafetyBench — https://arxiv.org/abs/2412.14470
- Home-Assistant-Requests-V2 — https://huggingface.co/datasets/acon96/Home-Assistant-Requests-V2
