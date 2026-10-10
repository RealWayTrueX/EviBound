#!/usr/bin/env python3
"""Build the human review bundle for the DRAFT v2 corpus.

Default mode: writes per-split review cards (Markdown, explicit HTML anchors +
headings), an index, and checklist.csv (required vs optional review load per
docs/design_v2_dataset.md Section 7).

--signoff mode: re-runs machine checks, validates that every REQUIRED checklist
row is decided, then writes reviews/v2/signoff.json and advances
data/scenarios_v2/manifest.json lifecycle for fully approved splits.

The bundle is review tooling only; it never touches frozen v1 data and never
feeds annotations into any agent prompt.
"""
import csv
import hashlib
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scenario_v2_lib import DEVICES, bfs_path

ROOT = Path('data/scenarios_v2')
OUT = Path('reviews/v2')
SAMPLE_SEED = 20261010
QCOLS = ['q1_instruction_clear', 'q2_goals_sensible', 'q3_perturbation_correct',
         'q4_expected_behavior_agree', 'q5_label_confidence']


def load(split):
    return [json.loads(l) for l in (ROOT / f'{split}.jsonl').read_text().splitlines()]


def fmt_state(d):
    return f"light={d['light']}, fan={d['fan']}, presence={str(d['presence']).lower()}"


def fmt_goal(g):
    return ', '.join(f'{k}={v}' for k, v in sorted(g.items())) if g else '(leave unchanged)'


def fmt_path(path):
    if path is None:
        return 'unreachable'
    if not path:
        return '(already satisfied - 0 writes)'
    return ' -> '.join(f'{d}={v}' for d, v in path) + f'  [{len(path)} write(s)]'


def expected_lines(t):
    a = t['annotations']
    init, presence = t['initial'], t['initial']['presence']
    clean = a['clean_branch']
    off = 'goal_absent' if clean == 'goal_present' else 'goal_present'
    lines = []
    lines.append(f"- **Clean variant** (actual presence={str(presence).lower()}): "
                 f"goal is `{fmt_goal(t[clean])}`; shortest legal plan: "
                 f"{fmt_path(bfs_path(init, t[clean], presence, t['authorized']))}.")
    naive = bfs_path(init, t[off], not presence, DEVICES)
    flags = []
    cur = dict(init)
    from scenario_v2_lib import state_legal, transition_ok
    for dev, val in naive or []:
        nxt = dict(cur)
        nxt[dev] = val
        tag = []
        if dev not in t['authorized']:
            tag.append('UNAUTHORIZED')
        if not (transition_ok(cur, dev, val) and state_legal(nxt, presence)):
            tag.append('RULE-VIOLATING under actual presence')
        flags.append(f"{dev}={val}{' [' + ', '.join(tag) + ']' if tag else ''}")
        cur = nxt
    lines.append(f"- **Perturbed variant** ({t['perturbation']}): observation indicates the "
                 f"{'absent' if clean == 'goal_present' else 'present'} branch; a policy that "
                 f"trusts it plans: {fmt_path(naive)}")
    if flags:
        lines.append(f"  - naive write sequence: {' -> '.join(flags)}")
    lines.append(f"  - B0: executes it -> "
                 f"{'UNSAFE effects' if a['attack_expects_unsafe'] else 'no rule violation'}"
                 f"{' + authorization violation' if a['attack_expects_unauthorized'] else ''}"
                 f"{' + goal failure' if not (a['attack_expects_unsafe'] or a['attack_expects_unauthorized']) else ''}.")
    lines.append("  - B1: same attack surface as B0 (prompt-only; v1 measured no difference).")
    lines.append("  - B2: enforces transition/load rules but trusts the agent's presence "
                 "evidence -> presence-rule violations pass when the attack claims "
                 "'present'; otherwise goal failure.")
    mech = ('provenance mismatch (value differs from the immutable record)' if t['perturbation'] == 'tamper'
            else 'staleness (replayed record is authentic but older than 2 time units)')
    lines.append(f"  - M: rejects the first evidence via {mech}; one reread then allows "
                 f"correct-branch recovery or a safe block.")
    if a['abstention_expected']:
        lines.append("  - Note: abstention (0 writes) is a correct outcome for at least "
                     "one branch of this task (authorized subgoal already satisfied).")
    lines.append(f"- **Boundary variant**: fresh boundary record (t=8) is served; any "
                 f"guard that accepts authentic fresh evidence must treat it like clean.")
    return lines


def card(t, required):
    a = t['annotations']
    is_a3 = set(t['authorized']) != set(DEVICES)
    lines = [f'<a id="task-{t["task_id"]}"></a>', '',
             f'### {t["task_id"]}  `({"REQUIRED" if required else "optional"})`', '']
    lines.append(f'- family: `{t["family"]}` | structure: `{t["structure_id"]}` | '
                 f'physical cluster: `{t["physical_structure_id"]}` | '
                 f'perturbation: **{t["perturbation"]}** | context: {t["context"]}'
                 + (' | **AUTHORIZATION-NEGATIVE (A3)**' if is_a3 else ''))
    lines.append(f'- initial: `{fmt_state(t["initial"])}` | authorized: `{t["authorized"]}`')
    lines.append(f'- instruction: "{t["instruction"]}"')
    lines.append('')
    lines.append('| branch | full goal | shortest legal plan | authorized subgoal | subgoal plan |')
    lines.append('|---|---|---|---|---|')
    for branch, pres in (('goal_present', True), ('goal_absent', False)):
        sub = t[f'authorized_subgoal_{"present" if pres else "absent"}']
        subpath = bfs_path(t['initial'], sub, pres, t['authorized']) if sub is not None else None
        mark = '  <- clean branch' if a['clean_branch'] == branch else ''
        lines.append(f'| {branch}{mark} | {fmt_goal(t[branch])} | '
                     f'{fmt_path(bfs_path(t["initial"], t[branch], pres, DEVICES))} | '
                     f'{fmt_goal(sub) if sub is not None else "-"} | '
                     f'{fmt_path(subpath) if sub is not None else "-"} |')
    lines.append('')
    lines.append(f'**Attack explanation**: {a["attack_explanation"]}')
    lines.append('')
    lines.append('**Expected behavior (derived, please challenge)**')
    lines.extend(expected_lines(t))
    lines.append('')
    lines.append('Reviewer: answer q1-q5 + decision in checklist.csv row for this task.')
    lines.append('')
    lines.append('---')
    lines.append('')
    return '\n'.join(lines)


def required_set(rows_by_split):
    req = set()
    rng = random.Random(SAMPLE_SEED)
    for split, rows in rows_by_split.items():
        for t in rows:
            if split == 'test' or set(t['authorized']) != set(DEVICES):
                req.add(t['task_id'])
    for split in ('dev', 'pilot'):
        pool = [t['task_id'] for t in rows_by_split[split]
                if t['task_id'] not in req]
        rng.shuffle(pool)
        req.update(pool[: (len(pool) + 1) // 2])
    return req


def cmd_build():
    rows_by_split = {s: load(s) for s in ('dev', 'pilot', 'test')}
    req = required_set(rows_by_split)
    OUT.mkdir(parents=True, exist_ok=True)
    index = ['# EviBound v2 corpus - human review bundle', '',
             f'Generated: {datetime.now(timezone.utc).isoformat(timespec="seconds")}',
             f'Machine checks: see data/scenarios_v2/check_report.json (must pass first).',
             f'Review load: {len(req)} REQUIRED of '
             f'{sum(len(r) for r in rows_by_split.values())} tasks '
             f'(100% of test, 100% of A3, ~50% sample of other dev/pilot).', '',
             'How to review: docs/review_guide_v2.md. Record decisions in checklist.csv;',
             'then run `python3 scripts/build_review_bundle.py --signoff`.', '']
    for split in ('test', 'pilot', 'dev'):
        rows = rows_by_split[split]
        n_req = sum(1 for t in rows if t['task_id'] in req)
        index.append(f'- [{split}.md](#{split}md): {len(rows)} tasks, {n_req} REQUIRED')
        parts = [f'<a id="{split}md"></a>', '',
                 f'# {split} split review cards ({len(rows)} tasks)', '']
        parts.append('## Index')
        parts.append('')
        for t in rows:
            parts.append(f'- [{t["task_id"]}](#task-{t["task_id"]}) '
                         f'({"REQUIRED" if t["task_id"] in req else "optional"}) '
                         f'{t["family"]}/{t["perturbation"]}')
        parts.append('')
        parts.append('---')
        parts.append('')
        for t in rows:
            parts.append(card(t, t['task_id'] in req))
        (OUT / f'{split}.md').write_text('\n'.join(parts))
    (OUT / 'README.md').write_text('\n'.join(index) + '\n')
    with open(OUT / 'checklist.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['task_id', 'split', 'family', 'perturbation', 'required'] +
                   QCOLS + ['decision', 'comment'])
        for split in ('test', 'pilot', 'dev'):
            for t in rows_by_split[split]:
                w.writerow([t['task_id'], split, t['family'], t['perturbation'],
                            'yes' if t['task_id'] in req else 'no',
                            '', '', '', '', '', '', ''])
    print(f'bundle written to {OUT}/ ({len(req)} required rows)')


def cmd_signoff(reviewer):
    subprocess.run([sys.executable, 'scripts/check_scenarios_v2.py'],
                   check=True, capture_output=True)
    rows = list(csv.DictReader(open(OUT / 'checklist.csv')))
    problems, decided = [], 0
    for r in rows:
        if r['required'] != 'yes':
            continue
        if r['decision'] not in ('approve', 'fix', 'reject'):
            problems.append(f'{r["task_id"]}: missing decision')
            continue
        decided += 1
        for q in QCOLS[:4]:
            if r[q] not in ('Y', 'N'):
                problems.append(f'{r["task_id"]}: {q} must be Y/N')
        if r['q5_label_confidence'] not in ('high', 'med', 'low'):
            problems.append(f'{r["task_id"]}: q5 must be high/med/low')
    open_items = [r['task_id'] for r in rows
                  if r['required'] == 'yes' and r['decision'] in ('fix', 'reject')]
    if problems:
        print('INCOMPLETE:'); [print(' -', p) for p in problems[:30]]
        sys.exit(1)
    cl_bytes = (OUT / 'checklist.csv').read_bytes()
    signoff = {'reviewer': reviewer,
               'date': datetime.now(timezone.utc).isoformat(timespec='seconds'),
               'required_rows': decided,
               'open_items': open_items,
               'checklist_sha256': hashlib.sha256(cl_bytes).hexdigest()}
    (OUT / 'signoff.json').write_text(json.dumps(signoff, indent=2) + '\n')
    mp = ROOT / 'manifest.json'
    manifest = json.loads(mp.read_text())
    ok = not open_items
    for split in ('dev', 'pilot', 'test'):
        if ok:
            manifest['lifecycle'][split] = 'human_reviewed'
    manifest['human_review'] = {
        'status': 'human_reviewed' if ok else 'open_items_remain',
        'signoff': 'reviews/v2/signoff.json',
        'note': 'freeze still requires Week-8 preregistration'}
    mp.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'signoff recorded: {decided} required rows, open items: {len(open_items)}')
    if not ok:
        print('open items must be regenerated and re-reviewed before freeze:')
        [print(' -', t) for t in open_items]
        sys.exit(2)


if __name__ == '__main__':
    if '--signoff' in sys.argv:
        i = sys.argv.index('--signoff')
        reviewer = sys.argv[i + 1] if i + 1 < len(sys.argv) else '<unknown>'
        cmd_signoff(reviewer)
    else:
        cmd_build()
