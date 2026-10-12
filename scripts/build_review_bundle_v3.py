#!/usr/bin/env python3
"""Build or sign off the human review bundle for the DRAFT v3 corpus.

Default mode writes reviews/v3/{holdout,dev}.md cards and checklist.csv.
REQUIRED rows: every holdout task plus every dev A3 task. `--signoff NAME`
re-runs the v3 checker, validates every REQUIRED row, writes
reviews/v3/signoff.json and advances data/scenarios_v3/manifest.json.
Card rendering reuses the v2 bundle so reviewers see the same layout.
"""
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_review_bundle import QCOLS, card  # noqa: E402
from scenario_v2_lib import DEVICES  # noqa: E402

ROOT = Path('data/scenarios_v3')
OUT = Path('reviews/v3')
SPLITS = ('holdout', 'dev')
RECOVERY_NOTE = (
    '> v3 note: every condition keeps the v2 guard. Recovery conditions only change the message after '
    'a rejection (rule explanation) or after an empty first plan (one confirmation reread). The budget '
    'stays one reread and one resubmission per episode.')


def load(split):
    return [json.loads(line) for line in (ROOT / f'{split}.jsonl').read_text().splitlines()]


def required(task):
    return task['split'] == 'holdout' or set(task['authorized']) != set(DEVICES)


def cmd_build():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = {split: load(split) for split in SPLITS}
    n_required = sum(required(t) for split in SPLITS for t in rows[split])
    readme = ['# EviBound v3 recovery corpus - human review bundle', '',
              f'Generated: {datetime.now(timezone.utc).isoformat(timespec="seconds")}',
              'Machine checks: data/scenarios_v3/check_report.json (must pass first).',
              f'Review load: {n_required} REQUIRED (all holdout tasks and all dev A3 tasks).', '',
              'Guide: docs/review_guide_v2.md applies unchanged. Fill checklist.csv, then run',
              '`python3 scripts/build_review_bundle_v3.py --signoff "Your Name"`.', '', RECOVERY_NOTE, '']
    for split in SPLITS:
        parts = [f'# {split} split review cards ({len(rows[split])} tasks)', '', RECOVERY_NOTE, '']
        parts += [f'- [{t["task_id"]}](#task-{t["task_id"]}) ({"REQUIRED" if required(t) else "optional"}) '
                  f'{t["family"]}/{t["perturbation"]}' for t in rows[split]]
        parts += ['', '---', '']
        parts += [card(t, required(t)) for t in rows[split]]
        (OUT / f'{split}.md').write_text('\n'.join(parts))
        readme.append(f'- {split}.md: {len(rows[split])} tasks, '
                      f'{sum(required(t) for t in rows[split])} REQUIRED')
    (OUT / 'README.md').write_text('\n'.join(readme) + '\n')
    with (OUT / 'checklist.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['task_id', 'split', 'family', 'perturbation', 'required'] + QCOLS + ['decision', 'comment'])
        for split in SPLITS:
            for t in rows[split]:
                writer.writerow([t['task_id'], split, t['family'], t['perturbation'],
                                 'yes' if required(t) else 'no'] + [''] * (len(QCOLS) + 2))
    print(f'bundle written to {OUT}/ ({n_required} required rows)')


def cmd_signoff(reviewer):
    subprocess.run([sys.executable, 'scripts/check_scenarios_v3.py'], check=True, capture_output=True)
    rows = list(csv.DictReader((OUT / 'checklist.csv').open()))
    problems, decided = [], 0
    for row in rows:
        if row['required'] != 'yes':
            continue
        if row['decision'] not in ('approve', 'fix', 'reject'):
            problems.append(f'{row["task_id"]}: missing decision')
            continue
        decided += 1
        problems += [f'{row["task_id"]}: {q} must be Y/N' for q in QCOLS[:4] if row[q] not in ('Y', 'N')]
        if row['q5_label_confidence'] not in ('high', 'med', 'low'):
            problems.append(f'{row["task_id"]}: q5 must be high/med/low')
    if problems:
        print('INCOMPLETE:')
        for problem in problems[:30]:
            print(' -', problem)
        sys.exit(1)
    open_items = [r['task_id'] for r in rows if r['required'] == 'yes' and r['decision'] != 'approve']
    signoff = {'reviewer': reviewer, 'date': datetime.now(timezone.utc).isoformat(timespec='seconds'),
               'required_rows': decided, 'open_items': open_items,
               'checklist_sha256': hashlib.sha256((OUT / 'checklist.csv').read_bytes()).hexdigest(),
               'corpus_sha256': {s: hashlib.sha256((ROOT / f'{s}.jsonl').read_bytes()).hexdigest() for s in SPLITS}}
    (OUT / 'signoff.json').write_text(json.dumps(signoff, indent=2) + '\n')
    manifest_path = ROOT / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if not open_items:
        manifest['lifecycle'] = {s: 'human_reviewed' for s in SPLITS}
    manifest['human_review'] = {'status': 'human_reviewed' if not open_items else 'open_items_remain',
                                'signoff': 'reviews/v3/signoff.json',
                                'note': 'holdout runs still require the v3 preregistration freeze'}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'signoff recorded: {decided} required rows, open items: {len(open_items)}')
    if open_items:
        sys.exit(2)


if __name__ == '__main__':
    if '--signoff' in sys.argv:
        index = sys.argv.index('--signoff')
        cmd_signoff(sys.argv[index + 1] if index + 1 < len(sys.argv) else '<unknown>')
    else:
        cmd_build()
