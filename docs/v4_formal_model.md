# Evidence-bound actuation: formal model (J1, draft) / 形式化模型（草稿）

Status: draft for v4, 2026-11-03. It replaces the one-line predicate in
`docs/week12_direction_review.md` §5, which lacked the lower age bound
(review D-01). Each assumption is pinned by a test in
`tests/test_formal_properties.py`; implementation references are to the frozen
`src/evibound/backend.py`.

## 1. Setting

| Symbol | Meaning |
|---|---|
| `D`, `L` | devices and their levels (v1–v3: light, fan; off < low < high) |
| `λ_t : D → L` | trusted actuator ledger: the committed device state at time `t` |
| `Σ` | trusted record store; a record is `r = (id, s, v, τ, e)`: id, sensor, value, observation time, epoch |
| `T` | trusted clock; every committed write advances it (by 0.25 in v1–v3) |
| `A ⊆ D` | authorization scope of the current request |
| `w = (d, ℓ)` | a proposed write; `c` is the evidence object the planner cites for it |
| `dec(s, v)` | trusted decoder from a sensor payload to the fact it reports (v1–v3: presence) |
| `R(λ, w, x)` | the device rules R1–R6 evaluated on the ledger, the write and the fact `x` |
| `Δ` | freshness bound (2.0 in v1–v3) |

## 2. The guard predicate

```
G(w, c, t_c) ≜  c ∈ Σ                      (exact match: same id, every field and type equal)
             ∧ c.s = s(w) ∧ c.e = e_now     (right sensor, current epoch)
             ∧ 0 ≤ t_c − c.τ ≤ Δ            (fresh at commit time; no future-dated records)
             ∧ w.d ∈ A                      (authorized device)
             ∧ R(λ_{t_c}, w, dec(c.s, c.v)) (rules hold on the ledger and the cited fact)
```

M commits `w` at `t_c` iff `G(w, c, t_c)` holds.

| Clause | Implementation | Rejection reason codes |
|---|---|---|
| sensor, epoch, membership, exact match, age | `World._validated_presence` | `wrong_sensor`, `wrong_epoch`, `unknown_record`, `record_mismatch`, `evidence_not_fresh` |
| authorization and rules | `_policy_violation` | — |

The implementation always enforced the lower bound `0 ≤ age`; only the
earlier written predicate missed it.

| Condition | Clauses dropped |
|---|---|
| B2 | membership, exact match and age; `R` reads the fact straight from `c.v` |
| M_no_freshness | age only |

## 3. Threat model and trusted base

**Adversary (channel-fault model).** The adversary controls everything between
`Σ` and the guard: the observation the planner reads, the planner's prompt and
reply, the feedback channel, and therefore both `w` and `c` (hops H0 and H4–H8
in `docs/chain_attack_surface.md`).

**Trusted computing base.** The store, the clock, the ledger, the scope `A`,
the decoder, the guard code, and the single commit path (H1–H3, H9, H10).

| ID | Assumption | Pinned by |
|---|---|---|
| A1 | **Store integrity.** Each `r ∈ Σ` is a genuine reading of sensor `r.s` taken at `r.τ`, and records are immutable. | existing backend tests (immutability) |
| A2 | **Unique identifiers.** `id` determines the record. | — |
| A3 | **Trusted monotone clock.** `T` never decreases and is not adversary-controlled. | `test_future_dated_record_is_not_fresh` (the predicate side) |
| A4 | **Atomic check-and-commit.** No actuator change between evaluating `G` and committing, so `λ_{t_c}` is the state the write lands on. | sequential execution in `World.execute` |
| A5 | **True scope.** `A` is the scope the user actually granted for this request. | chain attack H9 shows what breaks otherwise |
| A6 | **Correct decoding.** `dec` returns the fact the sensor measured. v1–v3 decode by exact lookup among two declared payloads. | `backend_v3` unit tests |
| A7 | **Single head.** Among records of one sensor that are fresh at `t_c`, at most one value is current; equivalently, an arbitration rule is applied, such as "cite the most recent record". | `test_two_fresh_authentic_records_need_arbitration` |
| A8 | **State stability inside the window.** Needed only for the world-relative corollary: the sensed fact does not change during `(c.τ, t_c]`. | `test_decision_ignores_hidden_world_state_inside_the_window` |

## 4. Results

**Theorem 1 (record-relative soundness).**

*Statement.* Under A1–A7, every write `w` that M commits at time `t_c`
satisfies all three:

1. `w.d ∈ A`;
2. the device rules hold on the committed state `λ_{t_c}`;
3. the rules hold for a genuine reading of the relevant sensor taken during `[t_c − Δ, t_c]`.

This holds for any planner and any channel adversary.

*Proof sketch.* M commits only if `G(w, c, t_c)` holds, and by A4 the ledger
seen by `G` is the state the write lands on.

- **The evidence is genuine.** `c ∈ Σ` with an exact field match and a unique
  id (A2), so `c` is a stored record. By A1 that record is a genuine reading
  taken at `c.τ`.
- **It was taken inside the window.** The age clause and A3 give
  `c.τ ∈ [t_c − Δ, t_c]`.
- **The rules were checked on the true reading.** By A6, `dec(c.s, c.v)` is
  the fact that was read, so `R` was evaluated on a genuine, fresh fact.
- **The device is in scope.** The scope clause and A5 give `w.d ∈ A`.
- **The planner and channel do not matter.** An adversarial `c` either fails
  membership or equals a genuine record, so no assumption about them is
  needed.
- **Fresh readings agree.** A7 ensures that no other fresh, genuine reading of
  the same sensor contradicts `c` at `t_c`. ∎

**Corollary 2 (world-relative safety and the residual window).**

- If A8 also holds, every committed write satisfies the rules with respect to
  the true world state at `t_c`.
- Otherwise, an unsafe commit requires the sensed fact to change inside the
  window `(c.τ, t_c]`, whose length is at most `Δ`.
- If the fact changes as a Poisson process with rate `μ`, the probability that
  a given commit is unsafe is at most `1 − e^{−μΔ} ≈ μΔ`.

`Δ` is therefore a safety parameter with a quantifiable residual risk. It is
not a free assumption.

**Lemma 3 (fact-independent writes; basis of `M_scoped`).**

- Call a write `w` *fact-independent* on ledger `λ` when `R(λ, w, x)` has the
  same value for every fact `x`. In v1–v3 these are the writes that neither
  turn the light above off nor set the fan to high (R1, R2, R6).
- For such writes, the predicate `G_scoped` drops the store, freshness and
  epoch clauses; the scope and rule clauses remain.
- Theorem 1 still holds for `G_scoped`, because the rule outcome does not
  depend on which reading is cited.
- **What it buys.** `M_scoped` keeps the safety guarantee and removes rejections of
  stale-but-harmless writes. This is the precision question raised by
  Stale≠Unsafe (arXiv 2609.29522), measured in v4 as J2.

## 5. What the property does not cover

| # | Case | Why it is outside |
|---|---|---|
| C1 | Future-dated record | Excluded by the lower bound (implementation correct; the earlier written predicate was wrong). |
| C2 | Two fresh, genuine records disagree (two sensors, a fast toggle, a second head) | Violates A7. The guard follows the cited one. v4 needs an arbitration rule and a conflicting-sensor test family. |
| C3 | The world changes inside the window (a person leaves at `t = 9`; a record from `t = 8` is cited at `t = 10`) | Violates A8. Bounded by Corollary 2, not prevented. |
| C4 | Rule-compliant hijack (chain attacks H0, H5, H6: 30/79 tasks) | G constrains rules, not user intent. Needs intent binding (`M_intent`, J7). |
| C5 | Trusted-base compromise (H1–H3, H9, H10) | The property is void by assumption. Mitigations: record signing, configuration hashing, single commit path. |
| C6 | Over-blocking | G demands fresh evidence even for fact-independent writes. Addressed by Lemma 3 and `M_scoped`. |
| C7 | Always_refresh | Satisfies Theorem 1 with the age of the collector's latest sample, but it needs the guard to own a sensor path (another trust assumption) and costs extra reads (v2: +1.46 per episode). It is a co-primary baseline in v4, not dominated by M. |

## 6. Positioning

| Work | What it binds | Difference from EviBound |
|---|---|---|
| CommitGuard (arXiv 2607.10487) | a witness, with a validity window, to a commit | digital tasks; trusts runtime-emitted signals |
| Freshness-Bounded Shield (2608.26306) | the age of a verdict | does not bind the observation itself |
| PACE (2610.01349) | pre-execution capability and effect verification with influence-path confinement | no age bound, no physical state machine |
| Stale≠Unsafe (2609.29522) | semantic commit predicates (their precision argument) | Lemma 3 adopts the argument inside EviBound |

Theorem 1 is the conjunction of verbatim provenance, a commit-time age bound
and stateful physical rules over a trusted ledger. That conjunction is the
narrowed contribution (`docs/related_work_2026-11.md`).

## 中文摘要

**守卫谓词。** 修正后的谓词补上了年龄下界 `0 ≤ t_c − c.τ`（实现里一直有，只是旧文档漏写）。

**定理 1：相对被引用记录的可靠性。** 在下列前提成立时，任何规划器、任何信道攻击者都只能让守卫提交这样的写入：授权范围内，并且对提交时的账本、以及一条 Δ 时间内的真实读数满足规则。前提是：

- 记录库可信、不可变；
- 记录 id 唯一；
- 时钟单调可信；
- 检查与提交原子完成；
- 授权范围真实；
- 解码正确；
- 同一传感器只有一个当前值（或有仲裁规则）。

**推论 2：对真实世界的安全性。** 只有再假设"Δ 时间窗内事实不变"，才能推出对真实世界安全；否则剩余风险受 Δ 约束，泊松变化率为 μ 时单次提交的风险约为 μΔ。

**引理 3：`M_scoped` 的依据。** 对规则结果不依赖观测事实的写入，可以不要求新鲜证据而不损失安全性。这正面回应 Stale≠Unsafe 的批评。

**不覆盖的情况。** 未来时间戳记录、两条新鲜记录互相矛盾、时间窗内世界变化、合规劫持、可信基被攻破、过度拦截。每一项都写明了原因，前三项有对应的性质测试。
