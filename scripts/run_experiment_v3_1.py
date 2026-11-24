#!/usr/bin/env python3
"""Run the v3.1 feedback-ladder matrix.

One shared first proposal per task, variant and seed is executed under every condition;
the recovery call is condition-specific (``evibound.runner_v3_1``). Resumes exact missing
episode identities from an existing output file.

  --corpus v3_1 --split holdout     the confirmatory run (needs the v3.1 freeze, see run_v3_1.sh)
  --corpus v3_1 --split dev         development split of the new corpus
  --corpus v3   --split holdout     the v3 holdout, which v3.1 uses as development data

  --planner local                   the frozen planner (bf16 Qwen2.5-7B-Instruct on CUDA)
  --planner cpu                     the same model in float32 on CPU
  --planner scripted:hasty          a deterministic persona, to exercise the pipeline without a model
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from evibound.planner_v3_1 import ROLES  # noqa: E402
from evibound.recovery_v3_1 import V31_CONDITIONS  # noqa: E402
from evibound.runner_v3_1 import run_seed  # noqa: E402

CORPORA = {'v3_1': 'data/scenarios_v3_1', 'v3': 'data/scenarios_v3'}
CODE = ('src/evibound/recovery_v3_1.py', 'src/evibound/runner_v3_1.py', 'src/evibound/planner_v3_1.py',
        'src/evibound/recovery.py',
        'src/evibound/backend.py', 'src/evibound/backend_v3.py', 'src/evibound/planner.py',
        'src/evibound/planner_v3.py', 'src/evibound/oracle.py', 'src/evibound/oracle_v3.py')


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--corpus', choices=sorted(CORPORA), default='v3_1')
    p.add_argument('--split', choices=['dev', 'holdout'], required=True)
    p.add_argument('--conditions', nargs='+', default=list(V31_CONDITIONS))
    p.add_argument('--variants', nargs='+', default=['clean', 'perturbed', 'boundary'])
    p.add_argument('--seeds', nargs='+', type=int, default=[11, 22, 33])
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--batch-size', type=int, default=8)
    p.add_argument('--task-ids', nargs='+')
    p.add_argument('--planner', default='local')
    p.add_argument('--role', choices=ROLES, default='base',
                   help='planner character; anything but base is the exploratory robustness arm')
    p.add_argument('--model', default='/mnt/HDD-8T-0/evibound_yanke/models/Qwen2.5-7B-Instruct')
    p.add_argument('--cpu-threads', type=int, default=12)
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scenario_path = ROOT / CORPORA[args.corpus] / f'{args.split}.jsonl'
    config = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}
    config.update({
        'study': 'EviBound v3.1 feedback ladder',
        'start_time_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'physical_gpu': os.environ.get('CUDA_VISIBLE_DEVICES'), 'python': platform.python_version(),
        'dataset': str(scenario_path.relative_to(ROOT)), 'dataset_sha256': digest(scenario_path.relative_to(ROOT)),
        'code_sha256': {path: digest(path) for path in CODE},
        'proposal_pairing': ('Identical first sampled response shared across all conditions; '
                             'recovery calls are condition-specific.'),
        'precision': {'local': 'bfloat16 on CUDA', 'cpu': 'float32 on CPU'}.get(args.planner, 'no model'),
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
    if args.planner == 'local':
        from evibound.planner import LocalPlanner
        generate = LocalPlanner(args.model).generate
    elif args.planner == 'cpu':
        from evibound.planner_v3 import CPUPlanner
        generate = CPUPlanner(args.model, threads=args.cpu_threads).generate
    elif args.planner.startswith('scripted:'):
        from run_v3_local import ScriptedPlanner
        generate = ScriptedPlanner(args.planner.split(':', 1)[1], scenarios)
    else:
        raise ValueError('--planner must be local, cpu or scripted:<persona>')
    start = time.perf_counter()
    count = 0

    def progress(info):
        print(json.dumps({**info, 'split': args.split, 'episodes_written': count,
                          'elapsed_s': round(time.perf_counter() - start, 1)}), flush=True)

    with args.output.open('a', buffering=1) as out:
        for seed in args.seeds:
            for episode in run_seed(generate, scenarios, args.conditions, args.variants,
                                    seed, args.batch_size, completed, progress, role=args.role):
                out.write(json.dumps(episode, sort_keys=True) + '\n')
                out.flush()
                os.fsync(out.fileno())
                count += 1
    config.update({'completed_episodes': len(completed), 'new_episodes': count,
                   'wall_elapsed_s': time.perf_counter() - start,
                   'finished_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                   'status': 'complete'})
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    print('COMPLETE', json.dumps({k: config[k] for k in ('completed_episodes', 'new_episodes', 'wall_elapsed_s')}),
          flush=True)


if __name__ == '__main__':
    main()
