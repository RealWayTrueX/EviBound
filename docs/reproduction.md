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
