#!/usr/bin/env python3
"""Exploratory scale study: run the refusal ladder in a home of a given size.

The engine is ``evibound.homes_runner`` (the v3.1 engine for a home of any size). One first
proposal per task, variant and seed is shared by every condition; the recovery call is
condition-specific. An existing output file is continued by episode identity.

  --home S|M|L            the home (docs/scale_study.md)
  --split main|pilot      the 120 tasks of the study, or the 12 pilot tasks
  --planner local         a local model on CUDA, bfloat16 (--model; --direct-answer for a template
                          that would otherwise open a reasoning block, as Qwen3's does)
  --planner scripted:P    a deterministic planner without a model: careful, hasty or menu
  --part I/N              the tasks at positions I-1 modulo N, so that N graphics cards share a run
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

from evibound.homes import HOMES  # noqa: E402
from evibound.homes_ladder import CONDITIONS  # noqa: E402
from evibound.homes_runner import ScriptedHomePlanner, run_seed  # noqa: E402
from run_experiment_v3_1 import resume_identities  # noqa: E402  (the frozen resume rule)

DATA = 'data/scenarios_homes'
CODE = ('src/evibound/homes.py', 'src/evibound/homes_ladder.py', 'src/evibound/homes_oracle.py',
        'src/evibound/homes_runner.py', 'src/evibound/planner.py', 'src/evibound/planner_models.py')
STUDY_CONDITIONS = ('B0', 'B2_plan', 'M_recover', 'M_full', 'M_plan')
MAX_NEW_TOKENS = 384


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--home', choices=sorted(HOMES), required=True)
    p.add_argument('--split', choices=['main', 'pilot'], default='main')
    p.add_argument('--conditions', nargs='+', default=list(STUDY_CONDITIONS), choices=sorted(CONDITIONS))
    p.add_argument('--variants', nargs='+', default=['clean', 'perturbed', 'boundary'])
    p.add_argument('--seeds', nargs='+', type=int, default=[11, 22, 33])
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--batch-size', type=int, default=8)
    p.add_argument('--part', default='1/1')
    p.add_argument('--planner', default='local')
    p.add_argument('--model', default='/mnt/HDD-8T-0/evibound_yanke/models/Qwen2.5-7B-Instruct')
    p.add_argument('--direct-answer', action='store_true')
    p.add_argument('--max-new-tokens', type=int, default=MAX_NEW_TOKENS)
    args = p.parse_args()
    home = HOMES[args.home]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    dataset = f'{DATA}/{args.home}_{args.split}.jsonl'
    scenarios = [json.loads(line) for line in (ROOT / dataset).read_text().splitlines()]
    index, parts = (int(x) for x in args.part.split('/'))
    if not 1 <= index <= parts:
        raise SystemExit(f'--part {args.part}: expected I/N with 1 <= I <= N')
    scenarios = [s for position, s in enumerate(scenarios) if position % parts == index - 1]
    config = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}
    config.update({
        'study': 'EviBound scale study (exploratory)', 'tasks': len(scenarios),
        'start_time_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'physical_gpu': os.environ.get('CUDA_VISIBLE_DEVICES'), 'python': platform.python_version(),
        'dataset': dataset, 'dataset_sha256': digest(dataset),
        'code_sha256': {path: digest(path) for path in CODE},
        'proposal_pairing': 'Identical first sampled response shared across all conditions; recovery calls are condition-specific.',
        'precision': 'bfloat16 on CUDA' if args.planner == 'local' else 'no model',
        'temperature': 0.2, 'top_p': 0.9, 'top_k': 20,
    })
    config_path = args.output.with_suffix('.config.json')
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    completed = resume_identities(args.output) if args.output.exists() else set()
    if args.planner == 'local':
        if args.direct_answer:
            from evibound.planner_models import DirectAnswerPlanner as Planner
        else:
            from evibound.planner import LocalPlanner as Planner
        generate = Planner(args.model, max_new_tokens=args.max_new_tokens).generate
    elif args.planner.startswith('scripted:'):
        generate = ScriptedHomePlanner(home, args.planner.split(':', 1)[1], scenarios)
    else:
        raise SystemExit('--planner must be local or scripted:<persona>')
    start = time.perf_counter()
    count = 0

    def progress(info):
        print(json.dumps({**info, 'home': args.home, 'part': args.part, 'episodes_written': count,
                          'elapsed_s': round(time.perf_counter() - start, 1)}), flush=True)

    with args.output.open('a', buffering=1) as out:
        for seed in args.seeds:
            for episode in run_seed(home, generate, scenarios, args.conditions, args.variants, seed,
                                    args.batch_size, completed, progress):
                out.write(json.dumps(episode, sort_keys=True) + '\n')
                out.flush()
                os.fsync(out.fileno())
                count += 1
    config.update({'completed_episodes': len(completed), 'new_episodes': count,
                   'wall_elapsed_s': time.perf_counter() - start,
                   'finished_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'status': 'complete'})
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    print('COMPLETE', json.dumps({k: config[k] for k in ('completed_episodes', 'new_episodes', 'wall_elapsed_s')}),
          flush=True)


if __name__ == '__main__':
    main()
