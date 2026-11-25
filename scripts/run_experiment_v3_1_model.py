#!/usr/bin/env python3
"""Exploratory: the frozen v3.1 runner with a second local model.

Everything is the frozen runner (scripts/run_experiment_v3_1.py); this file adds two things around it.

  * The planner class is ``evibound.planner_models.DirectAnswerPlanner``: the frozen planner, with
    the model's chat template rendered with thinking switched off. What the switch does to the
    template is written next to the episodes (model_switch_<part>.json).
  * ``--part I/N`` runs the tasks whose position in the split is I-1 modulo N, so that N graphics
    cards can share one run. A task is always complete within one part: its conditions share the
    first proposal, as in the frozen design.

Every other argument is passed on unchanged, for example
  --corpus v3_1 --split holdout --planner local --model /path/to/Qwen3-8B --output RUN/episodes_holdout_p1.jsonl
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import run_experiment_v3_1 as frozen  # noqa: E402


def part_task_ids(corpus, split, part):
    """Task ids of part ``I/N``, in corpus order."""
    index, parts = (int(x) for x in part.split('/'))
    if not 1 <= index <= parts:
        raise ValueError(f'--part {part}: expected I/N with 1 <= I <= N')
    path = ROOT / frozen.CORPORA[corpus] / f'{split}.jsonl'
    ids = [json.loads(line)['task_id'] for line in path.read_text().splitlines()]
    return [task for position, task in enumerate(ids) if position % parts == index - 1]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--part', default='1/1')
    p.add_argument('--corpus', choices=sorted(frozen.CORPORA), default='v3_1')
    p.add_argument('--split', choices=['dev', 'holdout'], required=True)
    p.add_argument('--output', type=Path, required=True)
    args, rest = p.parse_known_args()
    if '--task-ids' in rest:
        raise SystemExit('--task-ids is set by --part')

    import evibound.planner as frozen_planner
    from evibound.planner_models import DirectAnswerPlanner

    record = args.output.parent / f'model_switch_{args.part.replace("/", "of")}.json'

    class Recorded(DirectAnswerPlanner):
        def __init__(self, path, max_new_tokens=224):
            super().__init__(path, max_new_tokens)
            record.write_text(json.dumps({'model': str(path), 'part': args.part, **self.switch}, indent=2) + '\n')

    # the frozen runner looks the class up when it builds the planner
    frozen_planner.LocalPlanner = Recorded
    sys.argv = [frozen.__file__, '--corpus', args.corpus, '--split', args.split, '--output', str(args.output),
                *rest, '--task-ids', *part_task_ids(args.corpus, args.split, args.part)]
    frozen.main()


if __name__ == '__main__':
    main()
