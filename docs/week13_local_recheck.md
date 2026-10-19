# Week-13 Full-Pipeline Recheck on a Laptop / 第 13 周全流程本地复查

Date: 2026-10-19. Status: review record, not a protocol. Everything below was
run on a Mac (Apple M5, 24 GB, no GPU, no model weights) from the public
`main` at `7afc5af`, so it checks the *pipeline* (corpus → runner → guard →
oracle → analysis → report) and the published evidence chain, not the model.
Nothing frozen was edited; the one new executable is `scripts/run_v3_local.py`.

日期 2026-10-19。这是复查记录，不是协议。全部在一台没有 GPU、没有模型权重的
Mac 上从公开的 `main`（`7afc5af`）运行，检查的是**流水线**（语料→运行器→守卫→
判分→分析→报告）和已发布的证据链，不是模型本身。没有改动任何冻结文件；新增的
可执行文件只有 `scripts/run_v3_local.py`。

## 1. What was run and what it showed / 跑了什么，结果如何

| Check | Command | Result |
|---|---|---|
| Unit tests | `PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_*.py'` | 50/50 pass |
| v2 corpus checker | `python3 scripts/check_scenarios_v2.py` | OK, 56 tasks |
| v3 corpus checker | `python3 scripts/check_scenarios_v3.py` | OK, 84 tasks, 48 physical structures |
| v3 freeze | `python3 scripts/freeze_v3_prereg.py --verify` | `freeze ok (Xin Li, 2026-10-12T19:55:49+00:00)`, 17/17 hashes match HEAD |
| Week-8 main freeze | hashes in `artifacts/week8_main_protocol_freeze.json` vs HEAD | 15/15 match |
| Week-8 pilot freeze | hashes in `artifacts/week8_protocol_freeze.json` vs HEAD | 29/32 match; the 3 others are `reviews/v2/*`, local-only by design (`.gitignore`); all 32 match the sealed tarball |
| v1 freeze (Sept) | hashes in `artifacts/protocol_freeze.json` vs HEAD | 20/26 match; 6 code files evolved for v2 (`oracle.py`, `analyze.py`, `run_experiment.py`, `prepare_model.py`, `tests/test_oracle.py`, `model_manifest.json`); all 26 match `artifacts/protocol_20260922T193023Z.tar.gz`, so the v1 record stays reproducible from the tarball |
| Corpus determinism | regenerate v2 and v3 with `scripts/generate_scenarios_v{2,3}.py` in a scratch copy | every `.jsonl` byte-identical to the frozen files; only the v3 manifest's `lifecycle` / `human_review` fields differ (set by the review step after generation, as intended) |
| Published numbers | README, `week12_v3_holdout_closeout.md` vs `artifacts/week11_v3_holdout_results.json` | all quoted counts, estimates, CIs and decisions match the results file |
| End-to-end pipeline, no GPU | `scripts/run_v3_local.py --split holdout --planner scripted:hasty --seeds 11 22 33` | 7,128 episodes through `runner_v3` → `oracle_v3` → `analyze_v3` in ~2 s; 0 oracle disagreements, 0 false blocks, bilingual report rendered |
| Demo engine vs real runner | 8,316 real-runner episodes (4 local runs) replayed through `demo/engine.js` | 0 mismatches in events, recovery trigger and metrics (in addition to `demo/tests/test_demo_engine.py`) |

The scripted-planner runs are **illustrations of the pipeline**, not evidence
about the model. With the "hasty" persona the decision pattern happens to
match the real holdout (S1 and U2 supported, U1 unsupported, R1 supported),
because the persona was written to reproduce the two failure modes the v2
traces showed; the real result rests only on the frozen Qwen2.5-7B run.

脚本规划器的运行只用于**验证流水线**，不是关于模型的证据。"粗心"规划器的判定
模式恰好与真实 holdout 一致（S1、U2 支持，U1 不支持，R1 支持），因为它就是按
v2 轨迹里的两种失败方式写的；真实结论只来自冻结的 Qwen2.5-7B 运行。

## 2. Findings / 发现

1. **The evidence chain closes.** Every number in prose is regenerated from
   the results file; every freeze is verifiable from HEAD or from its sealed
   tarball; the corpus is reproducible from its generator and seed.
   证据链闭合：文中数字可从结果文件复算，冻结记录可从 HEAD 或封存的 tarball 校验，
   语料可从生成器和种子复现。
2. **The v1 freeze record no longer matches HEAD for six code files.** This is
   expected (v2 extended the oracle and runner) and the tarball preserves the
   frozen versions, but a reader who only runs a hash check against HEAD will
   see six mismatches. Recorded here so it is not mistaken for tampering.
   v1 冻结记录有 6 个代码文件与当前 HEAD 不一致：这是 v2 扩展判分器和运行器的
   结果，tarball 里保存着冻结版本；在此记录以免被误读为篡改。
3. **The Week-8 pilot freeze lists three local-only review files.** The public
   repository cannot verify them; the GPU machine can. Also by design.
4. **`analyze_v3.py` labels any `--stage holdout` input as a confirmatory
   run.** A local or exploratory re-run of the holdout split would therefore
   produce a report with the "confirmatory, frozen protocol" banner.
   `scripts/run_v3_local.py` always analyses as `dev` and stamps the report
   with an "exploratory local run" banner; the frozen analysis script itself
   is unchanged.
   `analyze_v3.py` 会把任何 `--stage holdout` 输入标成"确认性运行"；本地脚本
   因此一律按 `dev` 分析并加"本地探索性运行"横幅，冻结的分析脚本不动。
5. **Laptop environment notes.** `import torch` aborts on this Mac (duplicate
   OpenMP runtimes from the conda build) unless `KMP_DUPLICATE_LIB_OK=TRUE`
   is set; the demo server sets it only for its optional local-weights path.
   No model weights are on the Mac; a quantised Qwen2.5-7B via Ollama is the
   practical way to drive the demo or `run_v3_local.py --planner openai`
   with a real model, clearly labelled as non-confirmatory.
6. **Stale copies outside the repository.** `~/CyberSercurity/` (the parent
   folder of this clone) still holds September–11 October copies of v1/v2
   files (`docs/`, `dev/`, `pilot/`, `test/`, feasibility reports). The clone
   in `~/CyberSercurity/EviBound/` is the only copy tracking GitHub.

## 3. Local reproduction path / 本地复现路径

```bash
cd EviBound
PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/check_scenarios_v3.py && python3 scripts/freeze_v3_prereg.py --verify
# pipeline without a model (seconds):
python3 scripts/run_v3_local.py --split dev --planner scripted:hasty --output /tmp/v3_local/dev_hasty
# pipeline with a local quantised model (needs an OpenAI-compatible server such as Ollama):
python3 scripts/run_v3_local.py --split dev --planner openai \
    --base-url http://127.0.0.1:11434/v1 --model qwen2.5:7b-instruct --seeds 11 \
    --output /tmp/v3_local/ollama_dev
# step-by-step visual demo:
python3 demo/serve.py   # http://127.0.0.1:8765/
```

The episode files written by `run_v3_local.py` load directly into the demo's
"回放真实轨迹" tab.
