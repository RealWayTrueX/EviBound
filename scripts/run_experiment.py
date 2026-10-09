#!/usr/bin/env python3
"""Batched paired proposals followed by real condition-specific execution/retries."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import time
import traceback
from evibound.backend import World
from evibound.oracle import score_episode
from evibound.planner import LocalPlanner,messages_for,retry_messages,batch_seed

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--split',choices=['dev','pilot','test'],required=True)
    p.add_argument('--conditions',nargs='+',default=['B0','B1','B2','M','M_no_freshness','Always_refresh'])
    p.add_argument('--variants',nargs='+',default=['clean','perturbed','boundary'])
    p.add_argument('--seeds',nargs='+',type=int,default=[11,22,33])
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--worker',type=int,default=0)
    p.add_argument('--workers',type=int,default=1)
    p.add_argument('--batch-size',type=int,default=8)
    p.add_argument('--limit',type=int,default=0)
    p.add_argument('--task-ids',nargs='+')
    p.add_argument('--model',default='/mnt/HDD-8T-0/evibound_yanke/models/Qwen2.5-7B-Instruct')
    args=p.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    config=vars(args).copy(); config['output']=str(config['output'])
    config.update({'start_time_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'physical_gpu':os.environ.get('CUDA_VISIBLE_DEVICES'), 'python':platform.python_version(),
        'proposal_pairing':'Identical first sampled response shared across B0/B2/M/M_no_freshness/Always_refresh; B1 uses extra safety prompt.',
        'temperature':0.2,'top_p':0.9,'top_k':20,'max_new_tokens':224,
        'latency_definition':'Sum of amortized model batch times plus execution time. Logical calls/tokens count reused initial response. See wall_elapsed_s for actual worker time.'})
    scenario_path=Path(f'data/scenarios/{args.split}.jsonl')
    config['dataset_sha256']=hashlib.sha256(scenario_path.read_bytes()).hexdigest()
    config_path=args.output.with_suffix('.config.json')
    config_path.write_text(json.dumps(config,indent=2)+'\n')
    scenarios=[json.loads(x) for x in scenario_path.read_text().splitlines()]
    if args.task_ids:
        scenarios=[s for s in scenarios if s['task_id'] in args.task_ids]
        if len(scenarios)!=len(set(args.task_ids)):
            raise ValueError('Unknown or split-mismatched task ID')
    if args.limit: scenarios=scenarios[:args.limit]
    scenarios=[s for i,s in enumerate(scenarios) if i%args.workers==args.worker]
    completed=set()
    if args.output.exists():
        for line in args.output.read_text().splitlines():
            r=json.loads(line); completed.add((r['task_id'],r['variant'],r['condition'],r['seed']))
    planner=LocalPlanner(args.model)
    start=time.perf_counter(); count=0
    with args.output.open('a',buffering=1) as out:
        for seed in args.seeds:
            jobs=[]
            for s in scenarios:
                for variant in args.variants:
                    for prompt_type in ('base','safety'):
                        conditions=[c for c in args.conditions if (c=='B1')==(prompt_type=='safety')]
                        if not conditions: continue
                        world=World(s,variant); observation=world.observe()
                        jobs.append({'scenario':s,'variant':variant,'conditions':conditions,
                                     'messages':messages_for(s,world.state,observation,prompt_type=='safety'),
                                     'job_id':f'{s["task_id"]}/{variant}/{prompt_type}'})
            for offset in range(0,len(jobs),args.batch_size):
                chunk=jobs[offset:offset+args.batch_size]
                if all((j['scenario']['task_id'],j['variant'],c,seed) in completed
                       for j in chunk for c in j['conditions']):
                    continue
                responses=planner.generate([j['messages'] for j in chunk],
                    batch_seed('initial',seed,[j['job_id'] for j in chunk]))
                episodes=[]; retries=[]
                for job,response in zip(chunk,responses):
                    s=job['scenario']
                    for condition in job['conditions']:
                        key=(s['task_id'],job['variant'],condition,seed)
                        world=World(s,job['variant']); world.observe()
                        ep={'task_id':s['task_id'],'split':s['split'],'family':s['family'],
                            'perturbation':s['perturbation'],'variant':job['variant'],'condition':condition,
                            'seed':seed,'scenario':s,'proposals':[copy.deepcopy(response)],
                            'rejection_rereads':0,'guard_execution_s':0.0,'world':world,'job':job}
                        data=response['parsed'] or {}
                        before=time.perf_counter()
                        events=world.execute(data.get('actions'),data.get('evidence',{}),condition)
                        ep['guard_execution_s']+=time.perf_counter()-before
                        if events and events[-1]['kind']=='reject' and world.successful_writes<3:
                            obs=world.observe(); ep['rejection_rereads']=1
                            ep['retry_messages']=retry_messages(job['messages'],response['raw'],world.state,
                                obs,events[-1]['reason'],3-world.successful_writes)
                            retries.append(ep)
                        episodes.append(ep)
                for roffset in range(0,len(retries),args.batch_size):
                    rchunk=retries[roffset:roffset+args.batch_size]
                    rr=planner.generate([e['retry_messages'] for e in rchunk],batch_seed('retry',seed,
                        [f'{e["task_id"]}/{e["variant"]}/{e["condition"]}' for e in rchunk]))
                    for ep,response in zip(rchunk,rr):
                        ep['proposals'].append(response); data=response['parsed'] or {}
                        before=time.perf_counter()
                        ep['world'].execute(data.get('actions'),data.get('evidence',{}),ep['condition'])
                        ep['guard_execution_s']+=time.perf_counter()-before
                for ep in episodes:
                    if (ep['task_id'],ep['variant'],ep['condition'],ep['seed']) in completed:
                        continue
                    world=ep.pop('world'); ep.pop('job'); ep.pop('retry_messages',None)
                    ep['trace']=world.trace(); ep['metrics']=score_episode(ep['scenario'],ep['trace'])
                    ep['model_calls']=len(ep['proposals'])
                    ep['model_tokens']=sum(r['input_tokens']+r['output_tokens'] for r in ep['proposals'])
                    ep['output_tokens']=sum(r['output_tokens'] for r in ep['proposals'])
                    ep['latency_s']=sum(r['latency_s'] for r in ep['proposals'])+ep['guard_execution_s']
                    ep['model_latency_s']=sum(r['latency_s'] for r in ep['proposals'])
                    ep['worker']=args.worker
                    out.write(json.dumps(ep,sort_keys=True)+'\n'); out.flush(); os.fsync(out.fileno())
                    completed.add((ep['task_id'],ep['variant'],ep['condition'],ep['seed'])); count+=1
                print(json.dumps({'split':args.split,'worker':args.worker,'seed':seed,
                    'initial_jobs_done':min(offset+len(chunk),len(jobs)),'initial_jobs':len(jobs),
                    'episodes_written':count,'elapsed_s':round(time.perf_counter()-start,1)}),flush=True)
    config.update({'completed_episodes':len(completed),'new_episodes':count,'wall_elapsed_s':time.perf_counter()-start,
                   'finished_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'status':'complete'})
    config_path.write_text(json.dumps(config,indent=2)+'\n')
    print('COMPLETE',json.dumps(config),flush=True)

if __name__=='__main__':
    main()
