---
name: gpu-idle-autorun
description: Run long local-LLM experiment sweeps politely and safely on a shared multi-GPU Linux server — waiting for sustained free VRAM before launching, using tmux and nice so other users are never disrupted, resuming cleanly by episode identity after any crash, and publishing compact prompt-free fingerprints while keeping raw traces off GitHub. Use when scheduling multi-hour GPU experiments on shared lab machines.
---

# Polite & Crash-Resilient Shared-GPU Experiment Runner

Worked examples in EviBound:
- Shared-GPU watcher: `scripts/wait_gpu_then_run_v3.sh`
- Multi-GPU sharded runners & step orchestrator: `scripts/run_v3_1.sh`, `scripts/run_v3_1_model.sh`, `scripts/run_homes.sh`, `scripts/v3_1_step.sh`
- Remote planner lifecycle: `docs/remote_planner_setup.md`, `demo/launch/EviBound-Demo-Start.command`

## 1. Respect shared machines (hard rules)

- **Never preempt or touch other users' processes or checkouts.** Before launching, inspect `nvidia-smi` for free memory *and* active GPU PIDs. Require a **sustained** free-memory window (e.g., `< 2,000 MiB` used for several consecutive checks) before claiming a card.
- **Lower CPU priority.** Launch model jobs with `nice -n 10` and background analysis/compression with `nice -n 19` so interactive users and co-tenants stay responsive.
- **Detach in `tmux` (or a lock-guarded background runner).** Never poll from an active agent loop that burns tokens or dies if SSH drops. Guard with a PID lockfile (`pipeline.lock`) so repeated status checks print `BUSY` + progress instead of spawning duplicate jobs.
- **Shut down idle GPU servers.** Keep interactive demo/model servers off by default (`EviBound-Demo-Stop.command`) when not actively demonstrating so GPUs remain free.

## 2. Fail-fast pilot before multi-hour runs

- Always run a short **format-only pilot** on the dev split first (e.g., 3–5 minutes) before a multi-hour holdout or new-model sweep:
  - verify zero thinking/reasoning leakage (e.g., `enable_thinking=False` for Qwen3-8B),
  - verify parse-failure rate and max-token truncation stay within bounds,
  - abort automatically if the pilot fails rather than wasting GPU hours.

## 3. Crash-safe resume & clean result publishing

- **Episode-identity resume.** Write one JSON line per completed episode and remove any truncated trailing line on restart; resume strictly by `(task_id, variant, condition, seed)` identity rather than deleting outputs and starting over. Log every restart transparently.
- **Split GPUs cleanly.** When two identical GPUs are free, shard disjoint task subsets across GPU 0 and GPU 1 (`CUDA_VISIBLE_DEVICES=0` / `1`), merge outputs deterministically, and write a `COMPLETE` marker with episode count and wall-clock time only after verification passes.
- **Keep raw traces off GitHub.** Store model weights, caches, and full JSONL transcripts on the local data disk (`/mnt/HDD-8T-0/...`). Publish only compact, prompt-free episode fingerprints (`*.json.gz`), analysis JSONs, and logs; verify that server-side analysis from raw traces matches local recomputation from fingerprints field-for-field.

## Verification checklist

- [ ] `nvidia-smi` confirmed target GPU(s) free before launch; zero other-user processes touched.
- [ ] Pre-run pilot passed format and token-budget checks.
- [ ] Freeze verification (`--verify`) ran *inside* the launcher script before any holdout episode started.
- [ ] `COMPLETE` marker matches expected matrix size; fingerprint recomputation matches server-side raw-trace analysis with 0 disagreements.

## Related skills

`preregistered-agent-security-experiment`, `evidence-bound-report-pipeline`.
