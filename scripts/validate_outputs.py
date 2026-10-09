#!/usr/bin/env python3
"""Audit complete held-out run coverage, trace integrity, budgets and pairing."""
import hashlib
import json
from collections import Counter,defaultdict
from pathlib import Path
from evibound.oracle import score_episode

ROOT=Path('/home/yanke/EviBound')
DATA=Path('/mnt/HDD-8T-0/evibound_yanke')
conditions={'B0','B1','B2','M','M_no_freshness','Always_refresh'}
scenarios={r['task_id']:r for r in map(json.loads,(ROOT/'data/scenarios/test.jsonl').read_text().splitlines())}
paths=sorted((DATA/'runs/test').glob('worker[01].jsonl'))
assert len(paths)==2,'Two worker outputs required'
rows=[json.loads(line) for p in paths for line in p.read_text().splitlines()]
expected={(task,variant,condition,seed) for task in scenarios for variant in ['clean','perturbed','boundary']
          for condition in conditions for seed in [11,22,33]}
seen=set(); shared=defaultdict(list); issues=[]; rejection_reasons=Counter(); formats=Counter()
unique_inferences={}; physical_batches={}
for row in rows:
    key=(row['task_id'],row['variant'],row['condition'],row['seed'])
    if key in seen:issues.append(['duplicate',key])
    seen.add(key)
    if row['scenario']!=scenarios[row['task_id']]:issues.append(['scenario_mismatch',key])
    metrics=score_episode(row['scenario'],row['trace'])
    if metrics!=row['metrics']:issues.append(['oracle_mismatch',key])
    if metrics['trace_inconsistencies'] or metrics['initial_state_violations']:issues.append(['trace_error',key])
    if row['model_calls']>2 or row['trace']['successful_writes']>3 or row['rejection_rereads']>1:
        issues.append(['budget_error',key])
    if row['trace']['query_count']!=len(row['trace']['reads']):issues.append(['read_audit',key])
    if row['condition']!='B1':shared[(row['task_id'],row['variant'],row['seed'])].append(row['proposals'][0])
    rejection_reasons.update(metrics['rejection_reasons'])
    for index,prop in enumerate(row['proposals']):
        formats['responses_total']+=1
        formats['parse_invalid']+=prop['parse_error'] is not None
        formats['max_tokens_reached']+=prop['output_tokens']>=224
        identity=(row['task_id'],row['variant'],row['seed'],
                  ('B1' if row['condition']=='B1' else 'shared') if index==0 else row['condition'],index)
        unique_inferences[identity]=prop
        physical_batches[(row['worker'],index,prop['batch_seed'])]=prop['batch_latency_s']
for key,props in shared.items():
    if len(props)!=5 or any(p!=props[0] for p in props):issues.append(['pairing_error',key])
if seen!=expected:issues.append(['coverage',{'missing':len(expected-seen),'extra':len(seen-expected)}])
freeze=json.loads((ROOT/'artifacts/protocol_freeze.json').read_text())
for relative,expected_hash in freeze['files'].items():
    path=ROOT/relative
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected_hash:
        issues.append(['post_freeze_change',relative])
result={'status':'pass' if not issues else 'fail','episodes':len(rows),'expected_episodes':len(expected),
        'task_ids':len(scenarios),'paired_initial_proposal_groups':len(shared),'issues':issues,
        'rejection_reasons':dict(rejection_reasons),'logical_response_formats':dict(formats),
        'physical_model_calls':len(unique_inferences),
        'physical_input_tokens':sum(p['input_tokens'] for p in unique_inferences.values()),
        'physical_output_tokens':sum(p['output_tokens'] for p in unique_inferences.values()),
        'physical_batches':len(physical_batches),'summed_gpu_model_batch_seconds':sum(physical_batches.values()),
        'raw_files':{str(p):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in paths}}
(ROOT/'artifacts/final_validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
assert not issues,issues
