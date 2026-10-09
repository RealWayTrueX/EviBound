#!/usr/bin/env python3
"""Post-hoc descriptive M failure signatures, separate from frozen endpoints."""
from collections import Counter
import json
from pathlib import Path

rows=[json.loads(line) for path in Path('/mnt/HDD-8T-0/evibound_yanke/runs/test').glob('worker[01].jsonl')
      for line in path.read_text().splitlines()]
result={}
for variant in ('clean','perturbed','boundary'):
    counts=Counter()
    failures=[r for r in rows if r['condition']=='M' and r['variant']==variant
              and not r['metrics']['goal_completion']]
    for row in failures:
        proposals=row['proposals']; events=row['trace']['events']
        if proposals[0]['parsed']['actions']==[] and not events:
            counts['initial_empty_plan_no_rejection']+=1
        elif len(proposals)>1 and proposals[-1]['parsed']['actions']==[]:
            counts['empty_retry_after_rejection']+=1
        elif events and events[-1]['kind']=='reject':
            counts['final_retry_rejected:'+events[-1]['reason']]+=1
        else:
            counts['accepted_plan_wrong_final_state']+=1
    assert sum(counts.values())==len(failures)
    result[variant]=dict(counts)
Path('reports/test/m_failure_breakdown.json').write_text(json.dumps({
    'posthoc':True,'exclusive_categories':'Priority: initial empty/no events; empty final retry; final rejection reason; accepted wrong final state. These are trace signatures, not inferred cognitive causes.',
    'counts':result},indent=2)+'\n')
print(json.dumps(result))
