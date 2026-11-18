# Safety statement and AI-assistance disclosure / 安全声明与 AI 协助披露

This file is the safety statement required by the research contract
(section VII) and the disclosure of AI assistance required by the same
section. It applies to everything in this repository and to the raw-trace
bundle.

## 1. What this project is, and is not

- **Synthetic and offline.** Every experiment runs in a deterministic
  simulator with two simulated devices (a light and a fan) and simulated
  presence readings. No real home, device, account, network service or person
  is involved, and no personal data is collected or stored.
- **A local open-weight model.** The planner is Qwen2.5-7B-Instruct (Apache-2.0,
  revision pinned in `artifacts/model_manifest.json`), run locally. No paid or
  hosted model API was used. The weights are not redistributed here.
- **Not a product and not a certification.** The device rules R1–R6 are
  illustrative policies written for the experiment. They are not safety codes,
  and passing them says nothing about a real installation.

## 2. What the results do and do not show

- The results hold for the fixed synthetic tasks, the fixed attacks (value
  tampering, stale-record replay, unauthorized-device requests) and one model
  revision. Zero observed unsafe effects is an observation, never a guarantee.
- The guard's soundness statement is conditional on a trusted record store,
  clock, ledger and commit path (`docs/v4_formal_model.md`). If those are
  compromised, the guarantee is void. Record matching stands in for
  cryptographic sensor authentication, which is not implemented.
- A fresh reading is not the same as a currently true one: a fact can change
  inside the freshness window. The guard bounds that window; it does not
  remove it.
- Prompt injection, trained backdoors, adaptive attackers and attacks on the
  trusted base are outside the confirmatory experiments. The whole-chain
  attack matrix (`docs/chain_attack_surface.md`) is exploratory and
  deterministic; it reports where the guard does **not** help.

## 3. Use of the attack material

- The attacks act only on the simulator's own data structures: a simulated
  reading is altered or an old simulated record is served again. The
  repository contains no exploit for any real smart-home product, protocol,
  hub or cloud service.
- The demo's injection presets are prompts aimed at the simulated planner.
  They illustrate published attack classes and are included so that the
  defence can be inspected step by step.
- Do not connect the guard, the demo or the planner to real actuators (locks,
  heaters, cameras, vehicles, occupied spaces) or to real accounts
  (`AGENTS.md`). The code has not been engineered or reviewed for that use.

## 4. Operating the demo safely

- The demo page runs locally and works offline with scripted planners and
  recorded traces.
- The optional model server answers only on loopback and a private network
  range, and requires a bearer token that is never stored in the repository.
  Stop it after a demonstration (`demo/launch/EviBound-Demo-Stop.command`).

## 5. Human oversight

Policies, labels, freezes and release decisions were approved by the human
corpus owner, who signed off the task reviews before each corpus was frozen
(`artifacts/week8_preregistration.json`,
`artifacts/week11_v3_prereg_freeze.json`). Automatic checks and AI review
supported those decisions; they did not replace them.

## 6. AI-assistance disclosure

AI coding assistants were used throughout this project, as the research
contract anticipated ("AI-assisted test-driven development/review").

| Activity | AI assistance | Human role |
|---|---|---|
| Code (simulator, guard, oracle, runners, analysis, tools, demo) | Largely written and tested by AI assistants (Anthropic Claude Code; OpenAI Codex) under the owner's direction, test-first where practical | Set requirements, reviewed behaviour and results, decided what was merged |
| Scenario corpora | Generators and independent checkers written with AI assistance | Reviewed and signed off the required task cards and the rules |
| Protocols and preregistrations | Drafted with AI assistance | Decided hypotheses, endpoints, amendments and freezes; approved each freeze |
| Experiment runs | Launched and monitored with AI assistance on the owner's machine | Authorized the runs and the compute |
| Analysis and review | Statistics scripts written with AI assistance; an independent AI review (2026-11-03) audited all materials | Decided how findings were handled (`docs/review_response_2026-11-03.md`) |
| Documentation | Largely drafted by AI assistants | Reviewed and directed |

Where to check: commits written with an assistant carry a `Co-Authored-By`
trailer (31 of the 41 commits that existed when this file was written on
2026-11-10), and `docs/agentic_workflow.md` describes the working rules. The
owner maintains the table above and adds any tool that the commit history
does not show. The model under test (Qwen2.5-7B-Instruct) is the
experimental subject, not an assistant. No AI system acted as ground truth:
outcomes come from a deterministic oracle and human sign-off.

Any text submitted for assessment follows the course's own rules on AI use and
is disclosed there by its author.

## 中文摘要

- **范围。** 全部实验都在确定性的模拟器里做：模拟的灯、风扇和人体存在读数。不连接真实住宅、设备、账号，不收集个人数据，不调用付费或托管的模型 API。
- **结论的边界。** 结果只对固定的合成任务、固定的攻击和一个模型版本成立；"零不安全后果"是观察结果，不是保证。守卫的可靠性以可信的记录库、时钟、账本和提交路径为前提；读数"新鲜"不等于"当前为真"。
- **攻击材料。** 攻击只作用于模拟器自己的数据，仓库里没有针对任何真实智能家居产品或服务的利用代码。不要把守卫、演示或规划器接到真实设备或账号上。
- **人工把关。** 策略、标签、冻结和发布都由语料负责人批准；自动检查和 AI 复核只是辅助。
- **AI 协助披露。** 代码、协议草稿、分析脚本和文档大部分由 AI 编码助手（Claude Code、Codex）在负责人指导下完成；负责人决定假设、终点、修订和冻结并审核结果。带 `Co-Authored-By` 的提交可以查到。被测模型（Qwen2.5-7B）是实验对象，不是助手；判分由确定性判分器和人工签署完成。提交给课程评分的文字，按课程自己的 AI 使用规定由作者另行披露。
