#!/usr/bin/env python3
"""Run the Week-11 v3 recovery matrix with the frozen local planner.

One shared first proposal per task/variant/seed is executed under every v3
condition; recovery calls are condition-specific. Resumes exact missing
episode identities from an existing output file.
"""
import argparse
import hashlib
import json
import os
import platform
import time
from pathlib import Path

from evibound.planner import LocalPlanner
from evibound.planner_v3 import CPUPlanner
from evibound.recovery import V3_CONDITIONS
from evibound.runner_v3 import run_seed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--split', choices=['dev', 'holdout'], required=True)
    p.add_argument('--conditions', nargs='+', default=list(V3_CONDITIONS))
    p.add_argument('--variants', nargs='+', default=['clean', 'perturbed', 'boundary'])
    p.add_argument('--seeds', nargs='+', type=int, default=[11, 22, 33])
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--batch-size', type=int, default=8)
    p.add_argument('--task-ids', nargs='+')
    p.add_argument('--model', default='/mnt/HDD-8T-0/evibound_yanke/models/Qwen2.5-7B-Instruct')
    p.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    p.add_argument('--cpu-threads', type=int, default=12)
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scenario_path = Path(f'data/scenarios_v3/{args.split}.jsonl')
    config = vars(args).copy()
    config.update({
        'output': str(args.output), 'corpus': 'v3',
        'start_time_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'physical_gpu': os.environ.get('CUDA_VISIBLE_DEVICES'), 'python': platform.python_version(),
        'dataset_sha256': hashlib.sha256(scenario_path.read_bytes()).hexdigest(),
        'proposal_pairing': 'Identical first sampled response shared across all v3 conditions; recovery calls are condition-specific.',
        'precision': 'float32 on CPU' if args.device == 'cpu' else 'bfloat16 on CUDA',
        'temperature': 0.2, 'top_p': 0.9, 'top_k': 20, 'max_new_tokens': 224,
    })
    config_path = args.output.with_suffix('.config.json')
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    scenarios = [json.loads(x) for x in scenario_path.read_text().splitlines()]
    if args.task_ids:
        scenarios = [s for s in scenarios if s['task_id'] in args.task_ids]
        if len(scenarios) != len(set(args.task_ids)):
            raise ValueError('Unknown or split-mismatched task ID')
    completed = set()
    if args.output.exists():
        for line in args.output.read_text().splitlines():
            r = json.loads(line)
            completed.add((r['task_id'], r['variant'], r['condition'], r['seed']))
    planner = (CPUPlanner(args.model, threads=args.cpu_threads) if args.device == 'cpu'
               else LocalPlanner(args.model))
    start = time.perf_counter()
    count = 0

    def progress(info):
        print(json.dumps({**info, 'split': args.split, 'episodes_written': count,
                          'elapsed_s': round(time.perf_counter() - start, 1)}), flush=True)

    with args.output.open('a', buffering=1) as out:
        for seed in args.seeds:
            for episode in run_seed(planner.generate, scenarios, args.conditions, args.variants,
                                    seed, args.batch_size, completed, progress):
                out.write(json.dumps(episode, sort_keys=True) + '\n')
                out.flush()
                os.fsync(out.fileno())
                count += 1
    config.update({'completed_episodes': len(completed), 'new_episodes': count,
                   'wall_elapsed_s': time.perf_counter() - start,
                   'finished_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                   'status': 'complete'})
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    print('COMPLETE', json.dumps(config), flush=True)


if __name__ == '__main__':
    main()
