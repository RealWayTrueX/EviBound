#!/usr/bin/env python3
"""Single-item same-seed paired probe, separate from sampled batched main runs."""
import json
from pathlib import Path
from evibound.backend import World
from evibound.planner import LocalPlanner,messages_for

tasks={s['task_id']:s for s in (json.loads(x) for x in Path('data/scenarios/dev.jsonl').read_text().splitlines())}
planner=LocalPlanner('/mnt/HDD-8T-0/evibound_yanke/models/Qwen2.5-7B-Instruct')
results=[]
for task_id in ('dev_reading_00','dev_bright_work_00'):
    scenario=tasks[task_id]
    for seed in (11,22,33):
        pair={}
        for variant in ('clean','perturbed'):
            w=World(scenario,variant)
            messages=messages_for(scenario,w.state,w.observe())
            response=planner.generate([messages],seed)[0]
            pair[variant]=response
        clean=pair['clean']['parsed']; perturbed=pair['perturbed']['parsed']
        result={'task_id':task_id,'perturbation':scenario['perturbation'],'seed':seed,
                'batch_size':1,'torch_seed_reset_before_each_variant':True,'responses':pair,
                'actions_changed':None if clean is None or perturbed is None else clean['actions']!=perturbed['actions']}
        results.append(result)
        print(json.dumps({k:v for k,v in result.items() if k!='responses'}),flush=True)
Path('artifacts/paired_perturbation_probe.json').write_text(json.dumps(results,indent=2)+'\n')
