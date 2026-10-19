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
| Demo engine vs real runner | 8,316 real-runner episodes (4 local runs) replayed through `demo/engine.js`; `demo/tests/test_demo_engine.py` with 22 personas (60,984 episodes, all 18 reason codes) | 0 mismatches in events, recovery trigger and metrics |

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

## 3. Demo code review / 演示代码复审

An independent read-only review of `demo/` (engine port, page, server) was
run with a stub-DOM harness and Python probes. It found 17 items; all were
fixed in the same pass and the cross-check was widened so the kinds of input
that exposed them are now tested on every run.

对 `demo/`（引擎移植、页面、本地服务）做了一次独立只读复审，共 17 项，已全部
修正，并把暴露问题的那类输入加进了对拍测试。

| Severity | Finding | Fix |
|---|---|---|
| high | `value in LEVELS` walked the prototype chain, so a level named `toString` passed the JS schema check while Python rejected it | own-property check in schema, oracle and scorer |
| high | the server's origin allowlist included the request's own `Host`, so a DNS-rebinding page could call the API, name an environment variable to read, a `base_url` to send it to, or a local path to load | loopback-only `Host` check on every request, strict loopback `Origin` set, backends resolved by id from `backends.json`, body fields whitelisted, JSON content type required |
| medium | model-chosen device/value, task labels and replay condition were inserted into HTML unescaped | escaped |
| medium | an imported preset could persist an unknown planner/task/condition and brick the page on every load; an invalid scenario wiped all overrides | selections validated field by field, scenarios validated before saving, only the offending override dropped, boot clears per-viewer state once on failure |
| medium | JavaScript could not tell `10` from `10.0` or `1` from `true` inside evidence, so the guard and oracle could disagree with Python on such outputs | float literals tagged while parsing (`PyFloat`), Python `==` and `type()` semantics ported (`pyEq`, `pyType`), `json.dumps` float formatting and `\b` `\f` escapes matched |
| medium | prompt templating used `String.replace` (`$&` expansion, placeholder re-scan, first match only) | one-pass regex substitution |
| medium | transformers model could be loaded and run concurrently from two requests | lock around load and generate |
| low | "saved" label set before the save succeeded; fetch failures surfaced nothing | set after success, errors shown |
| low | prompt/feedback edits silently had no effect on scripted planners; invalid feedback JSON was swallowed | explained in the panel; invalid JSON blocks the step with the error |
| low | browser draft kept old defaults after the repository changed | draft stored as a diff keyed by the data digest, stale drafts dropped with a notice |
| low | replays ran under edited parameters and unknown v2 conditions crashed | replays use repository defaults; unsupported records are refused with a reason |
| low | "直接跑完" spun while a live call was in flight; a reset mid-call left the page stuck | per-run busy state, late responses discarded |
| low | cross-check rewrote the committed bundle and covered 5 of 18 reason codes | test builds to a temp file and checks the committed digest; 19 adversarial personas cover all 18 codes |

Two items are outside the demo and are recorded for v4 rather than changed
(the files are frozen): `oracle.py` / `oracle_v3.py` call
`records.get(evidence.get("id"))`, which raises on a list- or dict-valued
`id` instead of scoring the episode; and `backend_v3.decode` compares nested
payloads with Python `==`, so `{"minutes_since_motion": true}` decodes as
`1` while the oracle's canonical comparison does not. Neither occurred in any
recorded run (zero parse failures, zero oracle disagreements).

另有两点属于冻结代码、只记录不改：判分器遇到 `id` 为列表或字典的证据会抛错而
不是判分；`decode` 用 Python `==` 比较嵌套读数，`true` 会等同于 `1`，判分器则
不会。正式运行中都没有出现过。

## 4. Local reproduction path / 本地复现路径

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
