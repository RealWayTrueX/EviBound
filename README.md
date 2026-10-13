# EviBound: Evidence-Bound Runtime Enforcement for Smart-Home Agents

COSC 723 course project. An AI agent (local Qwen2.5-7B-Instruct) controls a
simulated light and fan from a presence-sensor reading. If the reading it sees
is forged or out of date, a well-formed command can still be unsafe, such as
turning the light on in an empty room. EviBound sits between the agent and the
devices and, before every write, checks that the sensor record the agent cited
is genuine and recent, and that the write obeys the device rules and
permissions. The experiments measure whether this removes unsafe effects while
still letting normal tasks finish. Everything is synthetic and offline: no real
home, device, account or paid API.

**New readers: start with the [Reading Guide](docs/reading_guide.md)**, which
explains the toy world (levels are off / level 1 / level 2), the device rules,
every condition code (B0, B2, M, ...), the metrics and the statistics terms.
For how the simulated attacks map to real homes, see
[Threat Model in the Real World](docs/threat_model_real_world.md).

## Status

| Study | Unsafe under attack: B2 vs EviBound (M) | Normal-task goal completion: no checker (B0) vs M | Verdict |
|---|---|---|---|
| v2 formal test (1,296 episodes) | 30/72 vs 0/72 | 53/72 vs 44/72 | Safety supported; "no worse than 5 points" utility target not met |
| v3 holdout (7,128 episodes, frozen amended protocol) | B2_full 31/216 vs M_full 0/216 (+14.4 pp [+4.6, +25.9]) | raw: 172/216 vs 156/216 (−7.4 pp, unsupported); rule-compliant: 93/216 vs 156/216 (+29.2 pp [+16.7, +43.1], supported) | **Joint feasibility supported** (S1 ∧ U2); recovery gain M_full − M +19.4 pp |

EviBound never refused a legal write. On the rule-compliant metric
(`safe_completion`: goal reached with no unsafe or unauthorized transition) B0
and M tie at 44/72; the raw gap is B0 completing nine tasks by breaking
stated sequencing rules, which M blocks and the agent then fails to repair.
The Week 11–12 **v3** study tests three recovery aids (rule explanation,
empty-plan check, and a legal-writes menu added before the freeze) on 72 new
tasks that also vary the sensor modality and the phrasing of requests
([plan with amendment log](docs/week11_v3_preregistration.md)). The holdout
ran on 2026-10-12 under the frozen protocol: zero unsafe effects and zero
false blocks under every M-guard condition, and the rule-compliant utility
criterion is met; the raw-completion deficit (−7.4 pp) is entirely the
unguarded baseline "completing" authorization-negative tasks by writing the
forbidden device ([closeout](docs/week12_v3_holdout_closeout.md),
[results record](artifacts/week11_v3_holdout_results.json)). Why the plan was
amended, where the work sits in the 2024–2026 literature, and which external
datasets come next: [Week-12 direction review](docs/week12_direction_review.md).

## Where things are

| Need | Location |
|---|---|
| Research question and conditions | [docs/research-contract.md](docs/research-contract.md) |
| Threat model (frozen) and its real-world companion | [docs/threat-model.md](docs/threat-model.md), [docs/threat_model_real_world.md](docs/threat_model_real_world.md) |
| Exact rules and runtime contract | [docs/implementation_contract.md](docs/implementation_contract.md) |
| v2 preregistration and results | [docs/week8_preregistration.md](docs/week8_preregistration.md), [artifacts/week8_main_results.json](artifacts/week8_main_results.json) |
| v3 recovery study | [docs/week11_v3_preregistration.md](docs/week11_v3_preregistration.md) |
| v3 holdout closeout and results | [docs/week12_v3_holdout_closeout.md](docs/week12_v3_holdout_closeout.md), [artifacts/week11_v3_holdout_results.json](artifacts/week11_v3_holdout_results.json) |
| Direction review, literature positioning, external datasets | [docs/week12_direction_review.md](docs/week12_direction_review.md) |
| Formal test validation record | [artifacts/week8_main_validation.json](artifacts/week8_main_validation.json) |
| v1 dataset card and literature check | [docs/dataset_card.md](docs/dataset_card.md), [docs/sources_and_design_review.md](docs/sources_and_design_review.md) |
| Roadmap and decision log | [docs/roadmap_week6.md](docs/roadmap_week6.md) |
| Agent working rules | [AGENTS.md](AGENTS.md) |

Task corpora: `data/scenarios/` (v1, 48 tasks, frozen), `data/scenarios_v2/`
(56 tasks, frozen and human-reviewed), `data/scenarios_v3/` (84 tasks across 4
sensor modalities and 3 language levels, human-reviewed, frozen, holdout complete). Model weights, raw traces and run logs live on the data disk
(`/mnt/HDD-8T-0/evibound_yanke/`). Human-facing experiment reports, review
packs and session notes stay local and are not in the public repository.

## Run the checks

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/check_scenarios_v2.py
python3 scripts/check_scenarios_v3.py
```

Model runs need one 24 GB GPU and must be launched inside tmux; see
`scripts/run_v2_main_test.sh` (v2) and `scripts/wait_gpu_then_run_v3.sh` (v3).

## Interpretation limits

The device rules are synthetic policies for the experiment, not real safety
codes. B2 is a guard built for this project, not a reproduction of a published
system. Attacks are fixed value tampering and stale-record replay plus
unauthorized-device requests; prompt injection, trained backdoors and adaptive
attackers are out of scope. Record matching stands in for cryptographic sensor
authentication.

---

# 中文说明

COSC 723 课程项目。AI 智能体（本地 Qwen2.5-7B-Instruct）根据人体存在传感器的
读数控制模拟的灯和风扇。如果它看到的读数是伪造的或过时的，一条格式正确的
命令也可能不安全，比如在没人的房间开灯。EviBound 放在智能体和设备之间，
每次写设备前核对智能体引用的传感器记录是否真实、是否足够新，以及这次写入
是否符合设备规则和权限。实验衡量它能否消除不安全后果，同时不耽误正常任务。
全部为离线合成实验，不连接真实家居、设备或账号，不调用付费 API，不训练模型。

**第一次读请先看[阅读指南](docs/reading_guide.md)**：解释档位（关 / 1 档 /
2 档，`low` 不是“调暗”）、设备规则、各条件代号（B0、B2、M……）、指标和统计
术语。模拟攻击在真实家庭中对应什么，见[威胁模型的现实对应](docs/threat_model_real_world.md)。

## 当前进展

v2 正式测试共 1,296 个回合：受攻击时，B2 有 30/72 次实际不安全，EviBound（M）
为 0/72，安全假设得到支持；正常任务目标完成 B0 为 53/72，M 为 44/72，差距
超过预设的 5 个百分点，效用目标未达到。EviBound 从未拒绝过合法写入；按“合规完成”
口径（达到目标且全程无不安全/越权写入）B0 与 M 都是 44/72，差距来自 B0 靠违反
既定顺序规则“完成”的 9 个任务被 M 正确拦下后，智能体没能修好计划。Week 11–12 的
**v3** 实验在 72 个新任务上测试三种恢复辅助（规则说明、空计划确认、冻结前新增的
“合法写入清单”），同时改变传感器模态和用户说法（[计划与修订记录](docs/week11_v3_preregistration.md)）。
holdout 已于 2026-10-12 按冻结协议跑完 7,128 回合：所有 M 守卫条件零不安全、
零误拦；合规完成口径达标（+29.2 pp），联合可行性首次支持；raw 口径 −7.4 pp 的差额
全部来自无守卫基线在越权任务上写了未授权设备（[收尾记录](docs/week12_v3_holdout_closeout.md)、
[结果文件](artifacts/week11_v3_holdout_results.json)）。为什么修订、工作在
2024–2026 文献中的位置、下一步并入哪些外部数据集：
[第 12 周方向复审](docs/week12_direction_review.md)。

## 文件布局

任务语料：`data/scenarios/`（v1，48 个，已冻结）、`data/scenarios_v2/`（56 个，
已冻结并经人工审核）、`data/scenarios_v3/`（84 个，覆盖 4 种传感器模态和 3 级语言，已审核并冻结，holdout 已完成）。模型权重、
完整逐回合轨迹和运行日志在数据盘 `/mnt/HDD-8T-0/evibound_yanke/`。面向人的
实验报告、审核包和交接记录只保存在本地，不放进公开仓库。

## 运行检查

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/check_scenarios_v2.py
python3 scripts/check_scenarios_v3.py
```

模型运行需要一张 24 GB 显卡，并在 tmux 里启动：v2 见
`scripts/run_v2_main_test.sh`，v3 见 `scripts/wait_gpu_then_run_v3.sh`。
v1 的 30 回合复现子集仍可用 `bash scripts/reproduce_subset.sh` 运行，它只验证
管线，不能替代完整统计。精确依赖版本见 `artifacts/environment_v2.json` 和
`configs/requirements_observed.txt`。

## 解释边界

设备规则是课程实验的合成策略，不是真实安全规范。B2 是本项目自建的守卫，
不是已发表系统的复现。攻击仅包括固定的读数篡改、旧记录重放和越权设备请求；
不包括提示注入、训练后门或自适应攻击者。“记录精确匹配”代替的是密码学传感器
认证。
