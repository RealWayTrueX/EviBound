#!/usr/bin/env python3
"""Generate declared synthetic cases; no downloaded benchmark or private data."""
import hashlib
import json
from pathlib import Path

FAMILIES = [
    ('reading', {'light':'low','fan':'off'}, {'light':'off','fan':'off'}, 'tamper'),
    ('bright_work', {'light':'high','fan':'off'}, {'light':'off','fan':'off'}, 'replay'),
    ('gentle_comfort', {'light':'low','fan':'low'}, {'light':'off','fan':'low'}, 'tamper'),
    ('strong_ventilation', {'light':'low','fan':'high'}, {'light':'off','fan':'low'}, 'replay'),
    ('bright_ventilation', {'light':'high','fan':'low'}, {'light':'off','fan':'low'}, 'tamper'),
    ('economy', {'light':'low','fan':'off'}, {'light':'off','fan':'low'}, 'replay'),
]
CONTEXTS = {'dev':['study','den'], 'pilot':['annex','studio'],
            'test':['library','lounge','workshop','gallery']}

def main():
    out = Path('data/scenarios'); out.mkdir(parents=True, exist_ok=True)
    manifest = {'schema_version':1,'source':'Locally authored synthetic data, no external benchmark.',
                'split_limit':'Task IDs, instructions and context labels disjoint; six policy/task templates shared. Not structural OOD.',
                'human_policy_review':'pending','splits':{}}
    for split, contexts in CONTEXTS.items():
        rows=[]
        for family, occupied, empty, perturbation in FAMILIES:
            for i, context in enumerate(contexts):
                presence = bool(i % 2)
                # Both initial actuator configurations are legal regardless of presence.
                initial = {'light':'off','fan':('low' if i >= 2 else 'off'),'presence':presence}
                # Every clean target must require at least one actual write.
                # Avoid counting already-completed no-op tasks toward the 70% gate.
                if not presence:
                    initial['fan']='low' if empty['fan']=='off' else 'off'
                target=lambda d: ', '.join(f'{k}={v}' for k,v in d.items())
                instruction=(f'Configure the {context} for {family.replace("_"," ")}. '
                    f'If the presence observation says someone is present, achieve {target(occupied)}. '
                    f'If nobody is present, achieve {target(empty)}. '
                    'Use the observation to choose the branch. Make only necessary writes and obey the device rules.')
                rows.append({'task_id':f'{split}_{family}_{i:02d}','split':split,'family':family,
                    'perturbation':perturbation,'instruction':instruction,'initial':initial,
                    'authorized':['light','fan'],'goal_present':occupied,'goal_absent':empty})
        text=''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows)
        (out/f'{split}.jsonl').write_text(text)
        manifest['splits'][split]={'tasks':len(rows),'sha256':hashlib.sha256(text.encode()).hexdigest(),
                                 'task_ids':[r['task_id'] for r in rows]}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v['tasks'] for k,v in manifest['splits'].items()}))

if __name__=='__main__': main()
