# Reproducing EviBound / 复现说明

Status: tooling and records for the research contract's "one-command
reproducible subset" and "independent reproduction" (Weeks 13–15). Nothing here
changes a frozen file or a frozen decision.

本文说明怎样复现本项目：不需要显卡的检查、从原始轨迹重算已发布的数字、以及用
冻结的运行器重新跑模型。所有工具都不改动冻结文件和冻结结论。

## 1. Four levels / 四个层级

| Level | Needs | Command | What it shows | Time |
|---|---|---|---|---|
| 1. Code and evidence chain | Python 3.10+ (node 21+ for two optional tests) | `bash scripts/reproduce.sh` | unit tests, corpus checkers, all four protocol freezes, and the full pipeline (runner → guard → oracle → analysis) with a scripted planner | about 1 min |
| 2. Published numbers | level 1 + the raw traces | `bash scripts/reproduce.sh --traces DIR` | every primary number, count, interval, hash and decision of the v2 formal test and the v3 holdout, recomputed from the traces (23 checks), plus the contract-outcome table | about 1 min |
| 3. Model re-run, original machine | level 2 + one 24 GB GPU + the pinned weights | `EVIBOUND_DATA=/path/to/data-disk bash scripts/reproduce.sh --gpu 0` | the v2 formal-test matrix run again with the frozen runner and compared episode by episode; `--seeds "11 22 33"` and `--v3-seeds "11"` widen it | 15 min to 2 h |
| 4. Model re-run, another machine | a fresh GPU machine with internet (for example Google Colab, one GPU with at least 24 GB) | `bash scripts/reproduce_cloud.sh` | the same re-run on different hardware: pins the library versions, downloads and verifies the pinned model revision, runs the frozen runners, and reports the re-run beside the published results | about 1 h |

Level 1 is the "one-command reproducible subset": it needs no GPU, no model
and no data beyond the repository. The scripted planner illustrates the
pipeline; it is not evidence about the model.

`DIR` is laid out like the data disk's `runs/` folder:
`week8_v2_main_test/seed_{11,22,33}.jsonl` and
`week11_v3_holdout/episodes.jsonl`.

The September v1 subset (`scripts/reproduce_subset.sh`, 30 episodes) is part
of the v1 freeze and still runs on the original machine. It is kept for the
v1 record; the commands above replace it for everything later.

## 2. What "reproduced" means here / "复现"的含义

The planner samples (temperature 0.2, top-p 0.9, top-k 20) on a GPU in
batches. Random numbers come from the seed, but the scores they are applied
to depend on the GPU model, the driver and the batch, so a re-run is not
expected to be identical byte for byte. The tools therefore report agreement
at three levels and then the scientific claim itself:

1. identical first model response (hash of the raw text);
2. identical executed write sequence;
3. identical oracle outcomes (unsafe effect, authorization violation, goal
   completion, safe completion), both runs rescored by the independent oracle;
4. the preregistered primary contrasts on both runs, with the preregistered
   cluster bootstrap: v2 safety (B2 − M unsafe effects under attack) and
   utility (M − B0 goal completion on clean tasks); v3 S1, U1 and U2.

A reproduction succeeds when level 4 gives the same decisions and estimates
inside each other's intervals. Levels 1–3 say how much of that is exact
replay and how much is statistical replication.

规划器在 GPU 上按批采样，随机数由种子决定，但概率值受显卡型号、驱动和批次影响，
所以重跑不要求逐字节一致。工具给出三级一致率（首个回复、执行的写入、判分结果），
再给出预注册主要对比在两次运行上的估计值和区间。判断复现是否成立看第四项。

## 3. Comparing runs without moving raw traces / 不搬运原始轨迹也能逐回合对比

`scripts/episode_fingerprints.py` reduces a trace file to one small row per
episode: identity, physical-structure cluster, a 16-hex-digit SHA-256 prefix
of the first raw response, the executed writes and the four oracle outcomes.
It holds no model text. `scripts/compare_runs.py` accepts a fingerprint file
wherever it accepts raw traces, and `--pack` prints a fingerprint file as a
short checksummed text block that survives copy and paste.

```bash
python3 scripts/episode_fingerprints.py --study v2 --inputs seed_11.jsonl seed_22.jsonl seed_33.jsonl \
    --output artifacts/episode_fingerprints_v2_formal_test.json.gz
python3 scripts/compare_runs.py --study v2 --original artifacts/episode_fingerprints_v2_formal_test.json.gz \
    --rerun out/seed_11.jsonl out/seed_22.jsonl out/seed_33.jsonl --output out/episode_comparison_v2.json
python3 scripts/summarize_rerun.py --study v2 --rerun out/seed_*.jsonl --output out/rerun_summary_v2.json
```

## 4. Environment / 环境

| Item | Original runs | Pinned by |
|---|---|---|
| Model | Qwen/Qwen2.5-7B-Instruct, revision `a09a3545…`, bf16 | `artifacts/model_manifest.json` (SHA-256 of every file) |
| Libraries | torch 2.9.0 (CUDA 12.8), transformers 4.57.1, tokenizers 0.22.2, accelerate 1.11.0, safetensors 0.5.3 | `configs/requirements_observed.txt`, `artifacts/environment_v2.json` |
| Hardware | 2 × NVIDIA RTX 4090 (24 GB), one GPU per run | `artifacts/environment_v2.json` |
| Sampling | batch 8, seeds 11 / 22 / 33, batch seed derived from stage, seed and job ids | `src/evibound/planner.py` (frozen) |

`scripts/reproduce.sh` reads three optional variables instead of fixed paths:
`EVIBOUND_DATA` (uses its `runs/`, `models/Qwen2.5-7B-Instruct` and
`envs/runtime/bin/python` when present), `EVIBOUND_MODEL` and
`EVIBOUND_PYTHON`. Outputs go to `--out` or a new timestamped folder; the
frozen run folders are never written.

## 5. Raw traces / 原始轨迹

The retained traces of every run are packaged by
`EVIBOUND_DATA=… bash scripts/package_traces.sh`: one archive with a manifest
of SHA-256 hashes, read-only on the run folders, no weights, logs or tokens.

| Archive | Size | SHA-256 | Contents |
|---|---|---|---|
| `evibound_raw_traces_20261110.tar.gz` | 2,279,422 bytes | `5086166a19ff16838d72cc28282b187f3c9966aa5bba9dd98cccd536042027fa` | 93 files: all v1, v2 and v3 episode files, run configurations, hash files, completion markers and analysis outputs |

The archive is on the data disk (`release/`). It is the "raw traces"
deliverable of the research contract; whether it is also published with the
repository is the corpus owner's decision. The episode fingerprints of the
two confirmatory runs are in `artifacts/`.

原始轨迹已打成一个带哈希清单的压缩包，放在数据盘的 `release/` 目录，是研究合同里
"raw traces" 这一项交付物；是否随仓库公开由语料负责人决定。两次确认性实验的
逐回合指纹在 `artifacts/` 里。

## 6. Sharing a GPU machine safely / 在共用机器上不打扰别人

`scripts/run_when_gpu_idle.sh STATUS_FILE COMMAND…` starts a command only on
a GPU that has been idle for ten consecutive checks, never shares a GPU,
stops the command at once if another job appears on that GPU, and ends within
a fixed deadline with every child process stopped. It is the way to run
level 3 on a machine that other people use.

## 7. Recorded runs / 复现记录

### 7.1 Published numbers recomputed from the raw traces (2026-11-10)

Fresh clone on the original machine, CPU only.
`scripts/verify_published_results.py` recomputed every primary number, count,
interval, hash and decision of the v2 formal test and the v3 holdout from the
retained traces: **23 checks, 0 failed**
(`artifacts/reproduction_published_results_check.json`). The oracle rescored
all 8,424 episodes with no disagreement. `scripts/contract_outcomes.py`
derived the outcomes the research contract lists and the frozen analyses do
not tabulate, attack-goal success among them
(`artifacts/contract_outcomes_v2_v3.json`).

### 7.2 Model re-run on a second machine (2026-11-10)

`scripts/reproduce_cloud.sh` on a Google Colab runtime with an NVIDIA A100
(40 GB): same library versions (torch 2.9.0 with CUDA 12.8, transformers
4.57.1), same pinned model revision (14 of 14 files match the manifest),
frozen runners, batch size 8. It ran the full v2 formal-test matrix (seeds
11, 22, 33; 1,296 episodes) and seed 11 of the v3 holdout (2,376 of 7,128
episodes) in 21 minutes including set-up. The original runs used an RTX 4090.
Record: `artifacts/reproduction_colab_a100_record.json`.

Episode-level agreement with the original runs:

| Study | Episodes | Identical first response | Identical executed writes | Identical oracle outcomes | Identical unsafe-effect outcome |
|---|---|---|---|---|---|
| v2 formal test | 1,296 | 1,181 (91.1%) | 1,167 (90.0%) | 1,221 (94.2%) | 1,295 |
| v3 holdout, seed 11 | 2,376 | 2,178 (91.7%) | 2,227 (93.7%) | 2,321 (97.7%) | 2,372 |

About one first response in eleven differs between the two GPUs, as expected
for sampling on different hardware (section 2). The preregistered contrasts:

| Contrast | Original run | Re-run on the second machine | Decision in both |
|---|---|---|---|
| v2 safety: B2 − M unsafe effects under attack | +36.4 pp [18.2, 59.1], 30 vs 0 of 72 | +36.4 pp [18.2, 59.1], 30 vs 0 of 72 | supported |
| v2 utility: M − B0 clean goal completion (margin −5 pp) | −13.6 pp [−27.3, 0.0], 44 vs 53 of 72 | −13.6 pp [−27.3, 0.0], 45 vs 54 of 72 | not supported |
| v3 S1, seed 11: B2_full − M_full unsafe effects under attack | +15.3 pp [5.6, 26.4], 11 vs 0 of 72 | +15.3 pp [5.6, 26.4], 11 vs 0 of 72 | supported |
| v3 U1, seed 11: M_full − B0 clean goal completion | −8.3 pp [−20.8, 2.8], 52 vs 58 of 72 | −9.7 pp [−23.6, 2.8], 51 vs 58 of 72 | not supported |
| v3 U2, seed 11: M_full − B0 clean rule-compliant completion | +29.2 pp [16.7, 43.1], 52 vs 31 of 72 | +29.2 pp [16.7, 43.1], 51 vs 30 of 72 | supported |

No episode under a full guard had an unsafe effect in either run: 0 of 432 in
v2 (M and Always_refresh) and 0 of 1,296 in v3 seed 11 (the six M
conditions). The v3 rows use one seed, so they are compared with the same
seed of the original run, not with the published three-seed values.

The re-run's episode fingerprints are committed
(`artifacts/reproduction_colab_a100_fingerprints_v{2,3}.json.gz`), so the
table can be recomputed from the repository alone:

```bash
python3 scripts/compare_runs.py --study v2 \
    --original artifacts/episode_fingerprints_v2_formal_test.json.gz \
    --rerun artifacts/reproduction_colab_a100_fingerprints_v2.json.gz --output /tmp/v2_comparison.json
```

`tests/test_reproduction_tools.py` runs this on every test run and fails if
the committed record stops matching the committed fingerprints. The raw
traces of the re-run were not kept (the runtime was released when the run
ended); their SHA-256 values are in the record.

Limits of this reproduction: same model revision, prompts, tasks and code, so
it tests whether the published numbers follow from the published procedure
on other hardware. It says nothing about other models, other tasks or other
attacks. The second machine was the corpus owner's existing Colab
subscription and was used only for this re-run; every confirmatory number in
the project comes from the original runs.

第二台机器（Colab A100，库版本和模型版本与原实验一致）上的重跑：v2 全部 1,296 回合、
v3 holdout 种子 11 的 2,376 回合，共 21 分钟。约九成回合的首个回复逐字一致；预注册的
主要对比结论全部相同：v2 安全假设成立（30 比 0，估计值和区间完全一致），效用假设不
成立（−13.6 个百分点，同样完全一致）。完整守卫条件在两次运行中都没有出现不安全后果。
重跑的逐回合指纹已提交，表中数字可以只靠仓库重新算出。
