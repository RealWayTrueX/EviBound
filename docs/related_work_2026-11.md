# Related work and the narrowed contribution (2026-11-03) / 相关工作与收窄后的贡献

This file updates §2 of `docs/week12_direction_review.md` (checked 2026-10-12).

- **Why.** The independent review (D-03) found five October 2026 preprints that the gap statement did not cover.
- **How each was checked.** All five were confirmed on arXiv on 2026-11-03, and each characterization below comes from the paper's abstract page.
- **Status of the 2026 items.** Every 2026 item here is a preprint, not a peer-reviewed paper.

## 1. Newly added (October 2026)

| Work | What it does | Evaluation | Relation to EviBound |
|---|---|---|---|
| **PACE** — Provenance-Aware Capability Enforcement (arXiv 2610.01349, 1 Oct) | Mediates every tool call immediately before execution. Confines represented influence paths and verifies schema-defined effects against authority compiled from the authenticated request. Can restore an authorized call after a block or apply a declared repair. | 8 executable agent-security benchmarks; 3 model families; 1,167 paired ablation cases; native utility loss ≤ 3 points | Closest *enforcement* neighbour: pre-execution, provenance-aware, reports utility. It has no commit-time age bound, no verbatim check of a cited observation against a trusted store, and no physical state machine. |
| **TRAP / ReplayBench** — Tool-result Replay Attack (2610.16333, 12 Oct) | Defines tool-result *misbinding*: a genuine, unmodified result consumed in an incompatible context, including stale results. Calls for runtime validity mechanisms and explicit contextual binding. | 19 scenarios; 4 failure properties; 3 replay mechanisms; 8 LLMs; 3 frameworks; mean final-state error 0.649 under cross-task replay | The closest *attack* work. EviBound's replay is one instance, and its record binding plus age bound is one concrete binding mechanism. TRAP's cross-task replay maps to our memory-channel replay (J5). |
| **StateWise** (2610.05241, 4 Oct) | Diagnoses and repairs persistent operational state before an agent acts: typed evidence grounding binds evidence to records and scopes, then an independent state–action check runs. | 150 executable coding-agent cases, cross-model; 93.3% correctness vs 38.7% under corrupted state | Repair-before-action on *digital* state. Related to our recovery aids (J6) and evidence binding; no physical rules, no age bound at commit. |
| **From Evidence to Action** / SafeActBench (2610.07753, 6 Oct) | Locates where the evidence-to-action chain breaks: agents act before establishing evidence, and multi-action workflows expose unresolved prerequisites. Uses a provenance-bound Evidence Ledger for evaluation. | 656 cases; 6 domains; 10 model–harness configurations | Supports our finding that planner recovery, not the guard, limits utility. Evaluation method only; no enforcement. |
| **Formal runtime verification** for tool-using agents (2610.09793, 7 Oct) | Offline MFOTL monitoring (MonPoly) of recorded AgentDojo and STAC trajectories. Binding provenance to the lookup that produced it closes a planted-line evasion. Benchmarks lack timestamps, so history-dependent obligations degrade. | 5 obligations flag 71.8% of STAC attack chains and 70.1% of successful AgentDojo attacks, but fire on 29.3% of benign runs | Supports J1 (formal statement) and our trace schema. EviBound traces carry timestamps, approvals and rejection reasons, which this paper identifies as missing from current benchmarks. |

The precision critique also deserves exact numbers.

- **Paper.** Stale≠Unsafe (2609.29522, submitted 25 Aug).
- **Setup.** 16 infrastructure tasks in 4 domains, 3,456 trajectories, 3 quantized local models.
- **Finding.** Global-epoch and read-set freshness guards needlessly block 92–95% of benign races and forfeit up to 43% of safe completions. A semantic commit predicate blocks none of the benign races.

`M_scoped` (Lemma 3 in `docs/v4_formal_model.md`) is the answer EviBound owes this paper.

## 2. Mechanism matrix

Columns:

- **a** — the cited or consumed observation is verified against a trusted source;
- **b** — the age of the data the action depends on is bounded at commit;
- **c** — stateful rules over a trusted state;
- **d** — physical side effects;
- **e** — repair or feedback to the planner;
- **f** — utility is reported.

Entries: Y = yes, P = partial, N = no, — = not applicable.

| Work | a | b | c | d | e | f |
|---|---|---|---|---|---|---|
| **EviBound M / M_full** | Y (verbatim record match) | Y (0 ≤ age ≤ Δ) | Y (R1–R6 on the ledger) | Y (simulated) | Y (rule explanation, legal-writes menu) | Y (U1, U2, U_dec) |
| PACE | P (influence paths, authority from the authenticated request) | N | P (schema-defined effects) | N | P | Y |
| TRAP / ReplayBench | — (attack and benchmark) | studies staleness | stateful workflows | N | N | final-state error |
| StateWise | P (typed evidence grounding) | P (reliability checks, no bound) | P (persistent state) | N | Y | Y |
| SafeActBench | evaluation only | — | — | N | N | Y |
| MFOTL runtime verification | P (provenance-bound lookup) | needs timestamps | Y (temporal obligations) | N | N | benign firing rate |
| Stale≠Unsafe | N | Y (epoch, read-set) vs semantic | Y | N | N | Y |
| CommitGuard (2607.10487) | N (trusts runtime signals) | Y (witness validity window) | P | N | P | Y |
| Freshness-Bounded Shield (2608.26306) | N | Y (age of the verdict) | P | N | N | Y |
| CaMeL; ProvenanceGuard; AGATE | P (data flow, derivability) | N | N | N | P | Y |
| AgentSpec; Progent; ShieldAgent; GuardAgent | N | N | N or Y | N | Y or P | Y |
| Safety Chip; RoboGuard; VIRF | N (world model assumed correct) | N | Y | Y | Y or P | Y |

## 3. The contribution, narrowed

**What we can say.** To our knowledge on 2026-11-03, EviBound is the only
runtime guard *for physical actuation* that requires, at every write, all of
the following at once:

1. the cited observation is verbatim in a trusted, immutable store;
2. it is no older than Δ at commit;
3. the stateful device rules and the authorization scope hold on a trusted ledger.

It is evaluated with paired clean and attack episodes and reports safety and
utility separately. Each ingredient has prior art:

| Ingredient | Prior art |
|---|---|
| Provenance and capability enforcement | CaMeL, PACE |
| Commit-time freshness | CommitGuard, FBS, Stale≠Unsafe |
| Physical shields | Safety Chip, RoboGuard, VIRF |
| Replay and staleness attacks | TRAP |

The contribution is their conjunction at the physical write, the record-relative
soundness statement (`docs/v4_formal_model.md`), and the evidence that planner
recovery, not the guard, limits utility.

**What we must not say.**

- "No system enforces provenance, freshness or stateful rules before actions." PACE, CommitGuard, StateWise and Stale≠Unsafe each do part of this.
- "The first defense against replayed tool results."
- "Freshness is sufficient." Stale≠Unsafe shows it over-blocks; we must measure it (J2).

**What v4 must compare against.**

- Always_refresh, a co-primary baseline.
- A semantic-predicate guard: `M_scoped`, the Stale≠Unsafe idea inside EviBound.
- A simplified PACE-style capability and effect check without evidence binding.
- The cross-task replay mechanism from TRAP, as an attack family next to tamper and replay.

## 4. Utility of a guard and feedback after a denial (added 2026-11-24, for v3.1)

Sections 1 to 3 cover enforcement mechanisms. v3.1 asks a different question:
how the utility cost of a guard is measured, and what the guard tells the
planner after it refuses a write. The works below were read on 2026-11-24
through summaries of their arXiv full text. Every 2026 item is a preprint, and
any detail that goes into the report or a paper needs a check against the
paper itself.

**How the utility cost of a guard is measured**

| Approach | Examples | What it leaves open |
|---|---|---|
| Task success with and without the defence | AgentDojo-style utility in FIDES (2505.23643), StepGuard (2608.24777), FORGE (2602.16708), PRUDENTIA (2602.11416), Symbolic Guardrails (2604.15579) | Whether a lost task was attainable under the policy; whether the baseline's successes were compliant |
| Completion under policy | ST-WebAgentBench, CuP (2410.06703) | Equals our rule-compliant completion (U2), which credits the guard with the baseline's violations |
| Task categories assigned by hand | FIDES (data independent / with query / data dependent, by manual inspection); AgentGuard (2609.16287, three reviewers judge feasibility) | No automatic label, no numeric ceiling, no attribution per episode |
| Cohorts by whether a gate fired | FORGE's denial cohort; deterministic gates on tau2-bench (2607.07405) | No run of the same plan without the gate to compare with |
| Per-action error rates | PolicyGym (2610.28989); GuardianAgentBench (2607.20982) | What the agent does after a correct block |
| Outcome taxonomies | BLINDSPOT (2609.16305): safe completion, correct refusal, unsafe completion, over-refusal | No label for a permitted action nobody asked for; no automatic achievability label |
| Theory | "What Can Be Enforced?" (2607.22868): gate transparency and a per-action utility loss; per-action error rates do not determine closed-loop utility because the agent adapts | No task-level attainable set and no measurement |

**What the agent is told after a block**

| Work | After a block | Is the content of the feedback studied? |
|---|---|---|
| FIDES (2505.23643) | the planning loop aborts | no |
| Least-privilege auditing (2611.11305) | call withheld in a replay | no; named as a limitation |
| StepGuard (2608.24777) | replaced by a self-reflect message | no |
| Safety Chip (2309.09919) | explanation of the violated constraint, then re-planning | argued, not measured |
| FORGE (2602.16708), GuardianAgentBench (2607.20982), deterministic gates (2607.07405) | structured denial, the agent re-plans | no; the gates paper lists informative against generic rejection as future work |
| TRIAD (2606.05805), RAIL Guard (2607.16215) | proceed, update or refuse; plan remediation | strategies are compared, contents are not |
| PolicyGuide (2608.19861) | workflow-level remediation after a refusal | process-valid rate only |
| MENTOR (2610.17039) | the violated manual excerpt and a suggested compliant call | no ablation, no measurement of what following the suggestion does |
| Environment Steering (2609.35807) | stop, generic retry, or constraint-aware retry | three variants compared, on task success and attack success only |

**Error messages for tool failures, and actions nobody asked for**

- Error-message design: "MCP Error Messages Written for Developers Hurt the Most Capable Agents Most" (2609.35381) and "Same Error, Different Recovery" (2611.11581) vary the content and the delivery of tool errors. Neither concerns a policy denial after which part of the request cannot be had, and neither has a reference for what was still achievable.
- Side effects: "Recovery Gone Too Far" (2611.19886) measures over- and under-modification after tool errors against hand-fixed sets of expected changes. OverAct (2610.01508), Overeager Coding Agents (2605.18583) and Authorization Drift (2611.09113) measure out-of-scope actions on benign tasks against annotated references. OverAct reports that a permission list with slack is used up in proportion to the slack. None of them studies a guard's feedback as the trigger.

**Where v3.1 stands.** Its instrument is an exact search for what the rules
and the scope allow in each task, which gives a ceiling, an attainable target
and a label for where each episode ended, with no annotation. Its question is
what a guard should say after a block, with the guard's decisions held fixed.
It does not claim that a completion measure should exclude violations (CuP),
that explanation after a block recovers utility (Safety Chip, Environment
Steering, MENTOR), or that the wording of an error changes recovery
(2609.35381, 2611.11581); those are established. Background on the classical
side: transparency of enforcement mechanisms (Schneider 2000; Ligatti, Bauer
and Walker 2005), shields with minimal interference (Bloem et al. 2015;
Alshiekh et al. 2018), and partial-satisfaction planning (Smith 2004; van den
Briel et al. 2004) are cited from memory here and are still to be checked.

## 中文摘要

**新增工作。** 复核指出的五篇 2026 年 10 月预印本都已在 arXiv 上核实。

| 论文 | 定位 | 与 EviBound 的区别 |
|---|---|---|
| PACE | 执行前的来源感知能力/效果核验，报告了效用，是最接近的"执法"工作 | 没有提交时的时效上界，没有逐字记录比对，没有物理状态机 |
| TRAP | 最接近的"攻击"工作 | 定义了工具结果错误绑定和重放，ReplayBench 覆盖 8 个模型 |
| StateWise | 行动前修复持久状态 | 数字域（代码智能体） |
| From Evidence to Action | 评测工作，说明问题出在规划器"拿到证据前就行动" | 不提供防御 |
| MFOTL 形式化运行时验证 | 指出现有基准缺时间戳 | 离线监测，不在执行点拦截 |

**收窄后的贡献。** 在物理执行点上同时要求三件事：

1. 被引用的观测逐字存在于可信记录库；
2. 提交时年龄不超过 Δ；
3. 有状态设备规则和授权在可信账本上成立。

另外两部分贡献是：只对被引用记录成立的可靠性定理，以及"效用瓶颈在规划器恢复而不在守卫"的证据。每个单项都有先例，贡献在于它们的组合。

**不能再说的话。** "没有系统做来源/时效/状态检查""首个重放防御""时效检查就够了"。

**v4 必须对比的对象。** Always_refresh、`M_scoped`、简化的 PACE 式能力核验，以及 TRAP 的跨任务重放攻击。

**2026-11-24 补充（第 4 节，为 v3.1）。** 同行衡量守卫效用代价的办法主要是带守卫和不带守卫的完成率、合规完成率（CuP）、人工划分任务类别；拦截之后的反馈大多只是"给出原因让智能体重试"，只有 Environment Steering 比过三种反馈，而且只看完成率和攻击成功率。v3.1 的工具是对每个任务精确搜索"规则之内最多能做到什么"，问题是守卫拦截之后该说什么。
