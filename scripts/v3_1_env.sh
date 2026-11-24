#!/usr/bin/env bash
# Environment for v3.1 runs. scripts/env.sh is frozen and tied to one checkout
# (/home/yanke/EviBound). Here the repository root is wherever this file lives, so a
# second clone can run without touching the first. The data disk, caches and the Python
# environment are the same as in env.sh.
export EVIBOUND_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export EVIBOUND_DATA="${EVIBOUND_DATA:-/mnt/HDD-8T-0/evibound_yanke}"
export HF_HOME="$EVIBOUND_DATA/cache/huggingface"
export HF_HUB_CACHE="$HF_HOME/hub"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TORCH_HOME="$EVIBOUND_DATA/cache/torch"
export XDG_CACHE_HOME="$EVIBOUND_DATA/cache"
export TMPDIR="$EVIBOUND_DATA/tmp"
export TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$EVIBOUND_ROOT/src:$EVIBOUND_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
unset TRANSFORMERS_CACHE
if [ -x "$EVIBOUND_DATA/envs/runtime/bin/python" ]; then export PATH="$EVIBOUND_DATA/envs/runtime/bin:$PATH"; fi
cd "$EVIBOUND_ROOT"
