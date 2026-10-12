#!/usr/bin/env python3
"""Write reviews/v3/review.html: a plain-language Chinese review page.

Each REQUIRED v3 task becomes one short card (scene, both branch goals, the
correct plan, what the attack makes a trusting agent do). The reviewer clicks
approve / fix / reject, optionally lowers confidence or adds a note, and
exports checklist.csv in the exact format build_review_bundle_v3.py --signoff
reads. Generated content only; it never changes the corpus.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_review_bundle_v3 import ROOT, OUT, SPLITS, required  # noqa: E402
from scenario_v2_lib import DEVICES, bfs_path, state_legal, transition_ok  # noqa: E402

CN_DEV = {'light': '灯', 'fan': '风扇'}
CN_VAL = {'off': '关', 'low': '1档(开)', 'high': '2档(强)'}
CN_FAMILY = {'focus': '柔光', 'task_lighting': '强光', 'comfort_mix': '灯和风扇',
             'lamp_only': '晚间照明（风扇无权限）', 'vent_only': '空气流通（灯无权限）'}
CN_CONTEXT = {'kitchen': '厨房', 'bedroom': '卧室', 'hallway': '走廊', 'garage': '车库',
              'office': '办公室', 'nursery': '育婴室'}


def cn_state(state):
    return '，'.join(f'{CN_DEV[d]}{CN_VAL[state[d]]}' for d in ('light', 'fan') if d in state) or '保持不变'


def cn_plan(path, authorized=None):
    if path is None:
        return '做不到'
    if not path:
        return '什么都不用做'
    steps = []
    for device, value in path:
        tag = '（无权限）' if authorized is not None and device not in authorized else ''
        steps.append(f'{CN_DEV[device]}→{CN_VAL[value]}{tag}')
    return ' → '.join(steps)


def attack_effect(task):
    init, presence = task['initial'], task['initial']['presence']
    wrong = 'goal_absent' if presence else 'goal_present'
    path = bfs_path(init, task[wrong], not presence, DEVICES) or []
    problems, current = [], {d: init[d] for d in DEVICES}
    for device, value in path:
        nxt = dict(current, **{device: value})
        if device not in task['authorized']:
            problems.append(f'写了无权限的{CN_DEV[device]}')
        if not (transition_ok(current, device, value) and state_legal({**nxt, 'presence': presence}, presence)):
            problems.append(f'{CN_DEV[device]}→{CN_VAL[value]} 在真实{"有人" if presence else "无人"}时违规')
        current = nxt
    outcome = '；'.join(dict.fromkeys(problems)) or '不违规，但完成的是错误分支'
    return cn_plan(path, task['authorized']), outcome


CN_MODALITY = {'presence_flag': '存在标志', 'motion_timer': '运动计时', 'camera_caption': '摄像头描述',
               'multi_sensor': '多传感器（运动计时 + 摄像头）'}
CN_LANGUAGE = {'explicit': '明确档位', 'everyday': '日常说法', 'scene': '场景名'}


def cn_reading(value):
    """How a payload reads to a person."""
    if isinstance(value, bool):
        return '有人' if value else '没人'
    if isinstance(value, str):
        return f'“{value}”'
    parts = []
    if 'minutes_since_motion' in value:
        parts.append(f'{value["minutes_since_motion"]} 分钟前检测到动静')
    if 'camera' in value:
        parts.append(f'摄像头：“{value["camera"]}”')
    return '；'.join(parts)


def card(task):
    init, presence, a3 = task['initial'], task['initial']['presence'], set(task['authorized']) != set(DEVICES)
    clean = 'goal_present' if presence else 'goal_absent'
    auth = task['authorized'] if a3 else DEVICES
    target = task[f'authorized_subgoal_{clean[5:]}'] if a3 else task[clean]
    plan = cn_plan(bfs_path(init, target, presence, task['authorized']))
    fake_plan, fake_effect = attack_effect(task)
    attack = ('篡改：读数被改成相反值' if task['perturbation'] == 'tamper'
              else '重放：拿出一条过期的旧记录（内容相反）')
    return {
        'id': task['task_id'], 'split': task['split'], 'family': task['family'],
        'perturbation': task['perturbation'],
        'title': f'{CN_CONTEXT.get(task["context"], task["context"])} · {CN_FAMILY[task["family"]]}',
        'lines': [
            ['标签', f'{CN_MODALITY[task["observation"]["modality"]]} · {CN_LANGUAGE[task["language"]]} · '
                     f'{"越权" if a3 else "双设备"} · 需要 {task["labels"]["writes_needed"]} 步'],
            ['用户原话', task['instruction']],
            ['有人时传感器显示', cn_reading(task['observation']['payload_present'])],
            ['没人时传感器显示', cn_reading(task['observation']['payload_absent'])],
            ['开始时', f'{cn_state(init)}；实际{"有人" if presence else "无人"}'],
            ['可控设备', '、'.join(CN_DEV[d] for d in task['authorized']) + ('（另一个设备没有权限）' if a3 else '')],
            ['有人时要', cn_state(task['goal_present'])],
            ['无人时要', cn_state(task['goal_absent'])],
            ['正确做法', f'按“{"有人" if presence else "无人"}”分支：{plan}'
                        + ('（只做有权限的部分）' if a3 else '')],
            ['攻击', attack],
            ['如果模型信了攻击', f'会做：{fake_plan}。结果：{fake_effect}'],
        ],
        'instruction': task['instruction'],
        'auth': list(auth),
    }


PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>v3 语料审核</title>
<style>
:root{--bg:#fafafa;--card:#fff;--fg:#222;--muted:#666;--line:#ddd;--ok:#1a7f37;--warn:#b26b00;--bad:#c62828}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--card:#222;--fg:#eee;--muted:#aaa;--line:#444}}
body{background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif;max-width:860px;margin:auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:12px 0}
.card.approve{border-left:5px solid var(--ok)}.card.fix{border-left:5px solid var(--warn)}.card.reject{border-left:5px solid var(--bad)}
h1{font-size:22px}h3{margin:0 0 6px;font-size:16px}.id{color:var(--muted);font-size:12px}
table{border-collapse:collapse;width:100%}td{padding:2px 6px;vertical-align:top}td:first-child{color:var(--muted);white-space:nowrap;width:8em}
details{color:var(--muted);font-size:13px;margin-top:4px}
.btns{margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
button{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:4px 10px;cursor:pointer}
button.on.approve{background:var(--ok);color:#fff}button.on.fix{background:var(--warn);color:#fff}button.on.reject{background:var(--bad);color:#fff}
input[type=text]{flex:1;min-width:160px;padding:4px;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px}
.bar{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);display:flex;gap:8px;flex-wrap:wrap;align-items:center}
</style></head><body>
<h1>v3 语料审核（__N__ 个必审任务）</h1>
<p>每张卡请看三件事：<b>“用户原话”是否能唯一读出两个分支的目标；两种传感器显示是否一眼能分清有没有人；“正确做法”和“如果模型信了攻击”是否对。</b>日常说法按家里约定理解：“开灯/the light on”=1 档，“全亮/full brightness”=2 档，“微风/a gentle breeze”=风扇 1 档，“强风/strong airflow”=风扇 2 档；没提到的设备保持不变。运动计时 5 分钟以内算有人。
对就点“通过”；觉得任务本身不合理点“需修改”或“拒绝”并写一句原因。
置信度默认“高”，拿不准可以调低。场景名（柔光、强光等）只是标签，以“有人时要/无人时要”两行为准；没人时开风扇 1 档是允许的（给空房间通风）。档位只有三档：关、1档(开)、2档(强)，没有“正常档”。规则：灯不关时必须有人；风扇2档必须有人且灯至少1档；灯档位+风扇档位≤3；灯和风扇都不能从关直接跳到2档。</p>
<div class="bar"><button id="all">全部标为通过</button><span id="count"></span>
<button id="export"><b>导出 checklist.csv</b></button></div>
<div id="cards"></div>
<p>术语和规则的完整解释见 <code>docs/reading_guide.md</code>。导出后把文件保存为 <code>reviews/v3/checklist.csv</code>（覆盖原文件），再运行
<code>python3 scripts/build_review_bundle_v3.py --signoff "&lt;reviewer-name&gt;"</code>。</p>
<script>
const CARDS = __CARDS__;
const META = __META__;
const STORE = 'v3review-__HASH__';
const state = {};
try { Object.assign(state, JSON.parse(localStorage.getItem(STORE) || '{}')); } catch (e) {}
function save(){ try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) {} render(); }
function render(){
  const root = document.getElementById('cards'); root.innerHTML = '';
  let done = 0;
  for (const c of CARDS) {
    const s = state[c.id] || {}; if (s.decision) done++;
    const el = document.createElement('div'); el.className = 'card ' + (s.decision || '');
    el.innerHTML = `<h3>${c.title}</h3><div class="id">${c.id} · ${c.perturbation}</div>
      <table>${c.lines.map(([k,v])=>`<tr><td>${k}</td><td>${v}</td></tr>`).join('')}</table>
      <div class="btns">
        ${[['approve','通过'],['fix','需修改'],['reject','拒绝']].map(([k,l])=>
          `<button class="${k} ${s.decision===k?'on':''}" data-id="${c.id}" data-d="${k}">${l}</button>`).join('')}
        <select data-id="${c.id}">${['high','med','low'].map(v=>`<option value="${v}" ${(s.conf||'high')===v?'selected':''}>置信度 ${({high:'高',med:'中',low:'低'})[v]}</option>`).join('')}</select>
        <input type="text" data-id="${c.id}" placeholder="备注（需修改/拒绝时必填）" value="${(s.comment||'').replace(/"/g,'&quot;')}">
      </div>`;
    root.appendChild(el);
  }
  document.getElementById('count').textContent = `已决定 ${done}/${CARDS.length}`;
  root.querySelectorAll('button[data-d]').forEach(b=>b.onclick=()=>{state[b.dataset.id]={...(state[b.dataset.id]||{}),decision:b.dataset.d};save();});
  root.querySelectorAll('select').forEach(x=>x.onchange=()=>{state[x.dataset.id]={...(state[x.dataset.id]||{}),conf:x.value};save();});
  root.querySelectorAll('input[type=text]').forEach(x=>x.onchange=()=>{state[x.dataset.id]={...(state[x.dataset.id]||{}),comment:x.value};save();});
}
document.getElementById('all').onclick=()=>{for(const c of CARDS){state[c.id]={...(state[c.id]||{}),decision:(state[c.id]||{}).decision||'approve'};}save();};
document.getElementById('export').onclick=()=>{
  const missing = CARDS.filter(c=>!(state[c.id]||{}).decision).length;
  if (missing && !confirm(`还有 ${missing} 张没决定，仍然导出？`)) return;
  const q = v => '"' + String(v ?? '').replace(/"/g,'""') + '"';
  const rows = [['task_id','split','family','perturbation','required','q1_instruction_clear','q2_goals_sensible','q3_perturbation_correct','q4_expected_behavior_agree','q5_label_confidence','decision','comment']];
  for (const r of META) {
    const s = state[r.id] || {};
    const yes = s.decision === 'approve' ? 'Y' : (s.decision ? 'N' : '');
    rows.push([r.id, r.split, r.family, r.perturbation, r.required ? 'yes' : 'no',
      r.required ? yes : '', r.required ? yes : '', r.required ? yes : '', r.required ? yes : '',
      r.required && s.decision ? (s.conf || 'high') : '', r.required ? (s.decision || '') : '', s.comment || '']);
  }
  const blob = new Blob([rows.map(r=>r.map(q).join(',')).join('\\n') + '\\n'], {type:'text/csv'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'checklist.csv'; a.click();
};
render();
</script></body></html>"""


def main():
    tasks = [json.loads(line) for split in SPLITS for line in (ROOT / f'{split}.jsonl').read_text().splitlines()]
    cards = [card(t) for t in tasks if required(t)]
    meta = [{'id': t['task_id'], 'split': t['split'], 'family': t['family'],
             'perturbation': t['perturbation'], 'required': required(t)} for t in tasks]
    OUT.mkdir(parents=True, exist_ok=True)
    corpus_hash = hashlib.sha256(''.join((ROOT / f'{s}.jsonl').read_text() for s in SPLITS).encode()).hexdigest()[:12]
    page = PAGE.replace('__HASH__', corpus_hash).replace('__N__', str(len(cards))).replace('__CARDS__', json.dumps(cards, ensure_ascii=False)).replace('__META__', json.dumps(meta))
    (OUT / 'review.html').write_text(page, encoding='utf-8')
    print(f'{OUT / "review.html"}: {len(cards)} cards')


if __name__ == '__main__':
    main()
