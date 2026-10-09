#!/usr/bin/env bash
set -euo pipefail
source /home/yanke/EviBound/scripts/env.sh
CUDA_VISIBLE_DEVICES=0 python scripts/confirm_perturbation.py > "$EVIBOUND_DATA/runs/paired_probe.log" 2>&1 &
probe_pid=$!
bash scripts/run_stage.sh dev
wait "$probe_pid"
python - <<'PY'
import json
from pathlib import Path
rows=json.loads(Path('reports/dev/summary.json').read_text())
b0=next(r for r in rows if r['condition']=='B0' and r['variant']=='clean')
probe=json.loads(Path('artifacts/paired_perturbation_probe.json').read_text())
gates={'development_b0_clean_completion':b0['goal_completion_rate'],
       'development_pass':b0['goal_completion_rate']>=0.7,
       'paired_probe_changes':sum(p['actions_changed'] is True for p in probe),
       'paired_probe_pairs':len(probe)}
gates['perturbation_pass']=any(all(p['actions_changed'] is True for p in probe if p['task_id']==task)
                             for task in {p['task_id'] for p in probe})
Path('artifacts/feasibility_gates.json').write_text(json.dumps(gates,indent=2)+'\n')
print(json.dumps(gates))
if not gates['development_pass'] or not gates['perturbation_pass']:
 raise SystemExit('Feasibility gate not met; main test not launched. Preserve evidence and review 12-task pivot.')
PY
bash scripts/run_stage.sh pilot
python -m unittest discover -s tests -v > artifacts/component_tests.log 2>&1
python scripts/freeze_protocol.py
bash scripts/run_stage.sh test
python scripts/validate_outputs.py > artifacts/final_validation.log
python scripts/build_figures.py --report-dir reports/test
date -u +'%Y-%m-%dT%H:%M:%SZ' > "$EVIBOUND_DATA/runs/OVERNIGHT_COMPLETE"
