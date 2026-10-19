# EviBound attack/defense demo / 攻防演示台

An interactive page that walks through one EviBound episode step by step: the
attacker tampering with or replaying the sensor reading, the model's plan, every
guard check (provenance, freshness, device rules, authorization), the recovery
feedback, and the independent oracle's verdict. Prompts, parameters, tasks and
the model are editable; edits can be saved as presets.

逐步演示一个 EviBound 回合：攻击者如何篡改或重放传感器读数、模型给出什么计划、
守卫每一项检查（来源、时效、设备规则、授权）的结果、恢复反馈，以及独立判分器的
结论。提示词、参数、任务和模型都可以改，改动可以保存成预设。

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

Edit `backends.json`. Examples: Ollama on the Mac
(`ollama pull qwen2.5:7b-instruct`), vLLM on the GPU machine through
`ssh -L 8000:127.0.0.1:8000 <gpu-host>`, or a local Hugging Face folder via
transformers. API keys are read from the environment variable named in
`api_key_env`; the page never asks for them. On a Mac whose conda `torch`
aborts with a duplicate-OpenMP error, the local-weights path sets
`KMP_DUPLICATE_LIB_OK=TRUE` before importing torch (Ollama avoids the issue).

## Test / 测试

```bash
PYTHONPATH=src:. python3 -m unittest demo.tests.test_demo_engine -v
```

Run it after any change to `src/evibound` or `engine.js`.
