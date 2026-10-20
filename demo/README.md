# EviBound attack/defense demo / 攻防演示台

An interactive page that walks through one EviBound episode step by step: the
attacker tampering with or replaying the sensor reading, the model's plan, every
guard check (provenance, freshness, device rules, authorization), the recovery
feedback, and the independent oracle's verdict. Prompts, parameters, tasks and
the model are editable; edits can be saved as presets.

逐步演示一个 EviBound 回合：攻击者如何篡改或重放传感器读数、模型给出什么计划、
守卫每一项检查（来源、时效、设备规则、授权）的结果、恢复反馈，以及独立判分器的
结论。提示词、参数、任务和模型都可以改，改动可以保存成预设。

## What you see / 画面

The stage is a blueprint of the simulated home: six rooms (kitchen, hallway,
bedroom, garage, office, nursery) with their furniture, a ceiling light, a
fan, the room's sensor (presence, motion, camera or both) and the people in
it; the active task's room is lit. Around the house sits the data chain:
hub / record store → cloud & integrations (where the attacker reaches in) →
LLM agent → EviBound guard (with one LED per check: provenance, freshness,
authorization, R1–R6) → oracle. Every step animates: packets travel the
chain, a tampered or replayed reading glitches red and conjures a phantom
occupant, a blocked write shatters on the guard with a BLOCKED stamp and a
mint shock-wave, an executed unsafe write floods the room and the screen
rose with an UNSAFE EFFECT stamp and a shake, and the verdict ends with a
SAFE sweep or an UNSAFE flash. The 动画 control sets slow / normal / fast /
instant; "直接跑完" always runs instantly. Reduced-motion settings disable
the full-screen effects.

舞台是模拟住宅的蓝图：六个房间、家具、顶灯、风扇、该任务的传感器和房间里的人，
当前任务的房间高亮；房子外面是数据链路：网关记录库 → 云端/集成层（攻击者插手处）
→ 智能体 → EviBound 守卫（每项检查一个指示灯）→ 判分器。攻击读数会沿链路变红、
在房间里生成"幻影"；拦截会在守卫处碎裂并盖 BLOCKED 印章；真正执行了不安全写入时
整屏变红、晃动并盖 UNSAFE EFFECT 印章；判分以绿色扫光或红色闪烁收尾。

## Attack content and language / 攻击内容与语言

"On the wire" (链路数据), directly under the stage, shows what actually travels on
each hop: the true record next to the reading the attacker hands the agent
(altered fields highlighted), the full prompt with the injected observation
line marked, the raw model output, the evidence the guard compares against
the trusted record, and the feedback message. Click any step in the log to
inspect it. At the "Read the sensor" step the payload the agent will receive
is editable, with presets for tamper, replay, a forged record id, or no
attack. The 中文 / English switch in the header renders the whole page in
either language.

舞台下方的“链路数据”显示每一跳实际传输的内容；“读取传感器”这一步可以直接改攻击
载荷（预设：篡改、重放、伪造 id、取消攻击）；右上角可切换中文 / English。

## Whole-chain attacks / 全链路攻击

`attacks/chain_attacks.js` assumes every hop can be attacked (user instruction,
sensor, radio, record store, cloud, prompt assembly, model API, feedback,
re-read, config, commit path, traces) and defines a deterministic injection for
each; `attacks/run_chain_attacks.js` runs them on every task. Results and the
proposed defenses: [docs/chain_attack_surface.md](../docs/chain_attack_surface.md).
Presets `chain-*` in `presets/` load the hops the page can already show
(`node attacks/build_chain_presets.js` regenerates them).

`attacks/chain_attacks.js` 假设链路每个环节都可能被改，给每个环节定义了攻击；
结果和防御建议见 [docs/chain_attack_surface.md](../docs/chain_attack_surface.md)，
`presets/chain-*` 是现在就能载入的演示预设。

On the page: pick a hop under 攻击环节 / Attacked hop. The attacker moves to that
hop on the stage, strikes it at the step where the attack applies (COMPROMISED
stamp; guard LEDs dashed when the hop is in the trusted base), and the episode
runs step by step with the attack's hooks, scored against the user's real task.
A rule-compliant takeover of an occupied room ends with a violet HIJACKED
verdict instead of SAFE. Worst-case attacks on text channels use the attacker's
plan with scripted planners and the real model's answer with a live model.

页面上：在“攻击环节”里选一个环节，攻击者会移到舞台上对应位置，在攻击生效的那一步
发动（COMPROMISED 印章；可信基环节时守卫指示灯变虚线），按用户真实任务判分；
有人房间里被合规劫持时以紫色 HIJACKED 收尾。

## Run / 运行

```bash
python3 demo/build_demo_data.py   # sync prompts, corpus and results from the repo
python3 demo/serve.py             # open http://127.0.0.1:8765/
```

Opening `demo/index.html` directly also works for everything except live
models and saving presets to files (it downloads the preset JSON instead).

## What is real and what is simulated / 哪些是真实的

| On screen | Source |
|---|---|
| Prompts, recovery texts, rules, constants | exported from `src/evibound` by `build_demo_data.py` |
| Guard, recovery and scoring logic | `engine.js`, a port of `backend*.py`, `recovery.py`, `oracle*.py`, verified by `tests/test_demo_engine.py` against `runner_v3.run_seed` on all 84 tasks x 3 variants x 11 conditions x 3 scripted planners |
| "脚本规划器" plans | deterministic illustrations (careful / hasty / empty-plan), **not** model data |
| "正式实验结果" charts and decisions | read from `artifacts/week11_v3_holdout_results.json` |
| Live model plans | whatever endpoint is selected in `backends.json` (sampling differs from the frozen runs; not formal results) |
| "回放真实轨迹" | episode JSONL from `/mnt/HDD-8T-0/evibound_yanke/runs/...`, re-executed and checked against the record |

`tests/sample_episodes.jsonl` is a small scripted sample in the runner's
episode format, only for testing the replay tab. Episode files written by
`scripts/run_v3_local.py` (the real runner with a scripted or local-model
planner) load into the replay tab the same way.

## Models / 模型

The default live backend is the frozen planner served from the GPU machine by
`scripts/serve_planner.py` over Tailscale (setup, token and fallbacks without
SSH: [docs/remote_planner_setup.md](../docs/remote_planner_setup.md)); the
replay tab can pull real holdout episodes from the same service.

Edit `backends.json` for other endpoints. Examples: Ollama on the Mac
(`ollama pull qwen2.5:7b-instruct`), vLLM on the GPU machine through
`ssh -L 8000:127.0.0.1:8000 <gpu-host>`, or a local Hugging Face folder via
transformers. API keys are read from the environment variable named in
`api_key_env`; the page never asks for them. On a Mac whose conda `torch`
aborts with a duplicate-OpenMP error, the local-weights path sets
`KMP_DUPLICATE_LIB_OK=TRUE` before importing torch (Ollama avoids the issue).

## Fidelity notes / 保真说明

- The engine keeps Python's int/float distinction in model output (`10` vs
  `10.0`, `1` vs `1.0`) by tagging float literals while parsing, which needs
  `JSON.parse` source access (Chrome/Edge 114+, Node 21+). In an older
  browser the header shows a warning chip and such outputs may be judged
  differently from the Python guard.
- `demo/tests/test_demo_engine.py` runs 22 planner personas (3 scripted, 19
  adversarial: malformed JSON, prototype-named levels, extra keys, wrong ids,
  float/bool-typed numbers, budget overruns, opposite-branch plans) over all
  84 tasks x 3 variants x 11 conditions and requires identical events,
  recovery messages and oracle metrics from `runner_v3`. All 18 guard reason
  codes are exercised. It is part of the standard `discover -s tests` run.
- The server resolves backends by id from `backends.json`; the page cannot
  name a model path, key variable or timeout. Requests with a non-loopback
  `Host` or a foreign `Origin` are refused.

## Test / 测试

```bash
PYTHONPATH=src:. python3 -m unittest demo.tests.test_demo_engine -v
```

Run it after any change to `src/evibound` or `engine.js`.
