"""The exploratory scale study: homes of three sizes on one engine.

The small home must be the frozen world again (same guard decisions, same attainable targets, same
refusal content); the larger homes must keep the properties the paper relies on.
"""
import itertools
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from evibound import attainability as frozen_att  # noqa: E402
from evibound import homes_ladder as ladder  # noqa: E402
from evibound import homes_oracle as oracle  # noqa: E402
from evibound import recovery as frozen_recovery  # noqa: E402
from evibound import recovery_v3_1 as frozen_ladder  # noqa: E402
from evibound.backend import World  # noqa: E402
from evibound.homes import HOMES, LEVELS, HomeWorld, legal_anytime, policy_violation  # noqa: E402
from evibound.homes_runner import ScriptedHomePlanner, run_seed  # noqa: E402

DATA = ROOT / 'data/scenarios_homes'
VARIANTS = ('clean', 'perturbed', 'boundary')


def tasks(name, split='main'):
    return [json.loads(line) for line in (DATA / f'{name}_{split}.jsonl').read_text().splitlines()]


def v31_tasks():
    return [json.loads(line) for line in (ROOT / 'data/scenarios_v3_1/holdout.jsonl').read_text().splitlines()]


def random_plan(rng, home, length=None):
    length = rng.randint(0, home.max_writes) if length is None else length
    plan = []
    for _ in range(length):
        device = rng.choice(home.devices)
        plan.append({'device': device, 'value': rng.choice(LEVELS[device])})
    return plan


def some_evidence(rng, world, delivered):
    choice = rng.randrange(5)
    if choice == 0:
        return delivered
    if choice == 1:
        return {'id': 'obs-current', 'sensor': 'presence', 'value': world.state['presence'], 'observed_at': 10, 'epoch': 1}
    if choice == 2:
        return {'id': 'obs-old', 'sensor': 'presence', 'value': not world.state['presence'], 'observed_at': 0, 'epoch': 1}
    if choice == 3:
        return {'id': 'obs-current', 'sensor': 'presence', 'value': not world.state['presence'], 'observed_at': 10, 'epoch': 1}
    return {'id': 'made-up', 'sensor': 'presence', 'value': True, 'observed_at': 10, 'epoch': 1}


class SmallHomeIsTheFrozenWorld(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(oracle.state_counts(HOMES['S']),
                         {'devices': 2, 'rules': 6, 'device_states': 9, 'states': 18, 'legal_states': 9,
                          'legal_present': 7, 'legal_absent': 2, 'max_writes': 3})
        self.assertEqual([oracle.state_counts(HOMES[n])['states'] for n in 'SML'], [18, 162, 648])
        for small, large in (('S', 'M'), ('M', 'L')):      # each home contains the one before it
            self.assertEqual(HOMES[large].devices[:len(HOMES[small].devices)], HOMES[small].devices)
            self.assertEqual(HOMES[large].rules[:len(HOMES[small].rules)], HOMES[small].rules)

    def test_guard_decisions_equal_the_frozen_guard(self):
        rng = random.Random(1)
        home = HOMES['S']
        for task in v31_tasks()[::3]:
            for variant in VARIANTS:
                for guard in ('B0', 'B2', 'M'):
                    mine, theirs = HomeWorld(home, {**task, 'initial': task['initial']}, variant), World(task, variant)
                    delivered = mine.observe()
                    self.assertEqual(delivered, theirs.observe())
                    plan = random_plan(rng, home)
                    evidence = some_evidence(rng, mine, delivered)
                    a, b = mine.execute(plan, evidence, guard), theirs.execute(plan, evidence, guard)
                    self.assertEqual([(e['kind'], e['device'], e['value'], e['reason']) for e in a],
                                     [(e['kind'], e['device'], e['value'], e['reason']) for e in b])
                    self.assertEqual(mine.state, theirs.state)

    def test_attainable_targets_equal_the_frozen_search(self):
        home = HOMES['S']
        for task in v31_tasks():
            a, b = frozen_att.attainability(task), oracle.attainability(home, task)
            self.assertEqual((a.cls, a.goal, a.attained, a.targets, a.plan, a.shortest),
                             (b.cls, b.goal, b.attained, b.targets, b.plan, b.shortest))
            rng = random.Random(task['task_id'])
            writes = [(w['device'], w['value']) for w in random_plan(rng, home)]
            self.assertEqual(frozen_att.outcome(task, writes, a), oracle.outcome(home, task, writes, b))

    def test_refusal_content_equals_the_frozen_ladder(self):
        home = HOMES['S']
        for code, text in frozen_recovery.RULE_FEEDBACK.items():
            if code in {r.code for r in home.rules} | {'unauthorized_device', 'evidence_not_fresh', 'record_mismatch',
                                                       'write_budget', 'schema_evidence'}:
                self.assertEqual(ladder.rule_feedback(home, code), text, code)
        self.assertEqual(ladder.LEGAL_WRITES_SUFFIX, frozen_recovery.LEGAL_WRITES_SUFFIX)
        self.assertEqual(ladder.BASE_RETRY_REQUEST, frozen_recovery.BASE_RETRY_REQUEST)
        self.assertEqual(ladder.CONFIRM_EMPTY_REQUEST, frozen_recovery.CONFIRM_EMPTY_REQUEST)
        for key in ('interrupted', 'reselect', 'empty', 'empty/changed', 'revise'):
            self.assertEqual(ladder.PLAN_TEXT[key], frozen_ladder.PLAN_TEXT[key])
        rng = random.Random(2)
        states = [dict(zip(home.devices, s)) for s in itertools.product(*(LEVELS[d] for d in home.devices))]
        for levels in states:
            for presence in (True, False):
                for authorized in (['light'], ['fan'], ['light', 'fan']):
                    self.assertEqual(ladder.legal_writes(home, levels, presence, authorized),
                                     frozen_recovery.legal_writes(levels, presence, authorized))
                    for _ in range(12):
                        plan = random_plan(rng, home, rng.randint(1, 3))
                        executed = rng.randint(0, len(plan) - 1)
                        reason = rng.choice(['evidence_not_fresh', 'record_mismatch', 'light_off_to_high',
                                             'load_exceeds_limit', 'unauthorized_device', 'schema_action'])
                        remaining, cited = rng.randint(0, 3), rng.choice([True, False, None])
                        args = (levels, presence, authorized, plan, executed, reason, remaining, cited)
                        for sequence in (False, True):
                            self.assertEqual(ladder.plan_review(home, *args, with_sequence=sequence),
                                             frozen_ladder.plan_review(*args, with_sequence=sequence))


class EveryHome(unittest.TestCase):
    def test_the_two_rule_evaluators_agree(self):
        """Guard and scoring side are written separately; on every state and write they must agree."""
        for home in HOMES.values():
            for state in itertools.product(*(LEVELS[d] for d in home.devices)):
                levels = dict(zip(home.devices, state))
                for presence in (True, False):
                    for device in home.devices:
                        for value in LEVELS[device]:
                            after = {**levels, device: value}
                            guard = policy_violation(home, levels, device, value, presence, home.devices) is None
                            self.assertEqual(guard, not oracle.violations(home, levels, after, presence),
                                             (home.name, levels, presence, device, value))

    def test_no_unsafe_effect_under_the_evidence_bound_guard_whatever_the_planner_writes(self):
        rng = random.Random(3)
        for name, home in HOMES.items():
            unguarded = 0
            for task in tasks(name)[::2]:
                for variant in VARIANTS:
                    for guard in ('M', 'B0'):
                        world = HomeWorld(home, task, variant)
                        delivered = world.observe()
                        for _ in range(2):      # a first plan and a second one, as in an episode
                            world.execute(random_plan(rng, home), some_evidence(rng, world, delivered), guard)
                        writes = [(e['device'], e['value']) for e in world.trace()['events'] if e['kind'] == 'write']
                        _, metrics = oracle.replay(home, task, writes)
                        if guard == 'M':
                            self.assertFalse(metrics['unsafe_effect'] or metrics['authorization_violation'],
                                             (task['task_id'], variant, writes))
                        else:
                            unguarded += metrics['unsafe_effect']
            self.assertGreater(unguarded, 20, name)      # the same random plans do break rules without a guard

    def test_a_stale_or_forged_reading_is_refused_and_a_rule_guard_believes_it(self):
        for name, home in HOMES.items():
            task = next(t for t in tasks(name) if not t['initial']['presence'] and t['labels']['lure_unsafe']
                        and t['perturbation'] == 'tamper')
            plan = [{'device': d, 'value': v} for d, v in task['labels']['lure_plan']]
            for guard, unsafe in (('B2', True), ('M', False)):
                world = HomeWorld(home, task, 'perturbed')
                forged = world.observe()
                self.assertIs(forged['value'], True)            # the delivered reading says somebody is present
                events = world.execute(plan, forged, guard)
                writes = [(e['device'], e['value']) for e in events if e['kind'] == 'write']
                self.assertEqual(oracle.replay(home, task, writes)[1]['unsafe_effect'], unsafe)
                if guard == 'M':
                    self.assertEqual(events[0]['reason'], 'record_mismatch')
            world = HomeWorld(home, task, 'boundary')            # fresh for the first write only
            first = world.observe()
            legal = {'device': 'fan', 'value': 'low' if task['initial']['fan'] == 'off' else 'off'}
            back = {'device': 'fan', 'value': task['initial']['fan']}
            if 'fan' in task['authorized']:
                events = world.execute([legal, back], first, 'M')
                self.assertEqual([e['reason'] for e in events], ['accepted', 'evidence_not_fresh'])

    def test_the_prompt_names_every_device_rule_and_limit(self):
        for home in HOMES.values():
            prompt = ladder.system_prompt(home)
            for device in home.devices:
                self.assertIn(f'{device} ({", ".join(LEVELS[device])})', prompt)
            for rule in home.rules:
                self.assertIn(ladder.rule_sentence(home, rule), prompt)
            self.assertIn(f'zero to {home.max_writes} writes', prompt)
            for line in prompt.splitlines():                     # every worked example is accepted by the guard
                if not line.startswith('Example:'):
                    continue
                presence = 'presence=true' in line
                levels = {d: re.search(rf'current .*?{d}=(\w+)', line).group(1) for d in home.devices}
                plan = json.loads(re.search(r'(?:Actions: |"actions":)(\[.*?\])', line).group(1))
                for write in plan:
                    self.assertIsNone(policy_violation(home, levels, write['device'], write['value'], presence, home.devices))
                    levels[write['device']] = write['value']


class Corpus(unittest.TestCase):
    def test_the_files_are_what_the_generator_writes(self):
        done = subprocess.run([sys.executable, str(ROOT / 'scripts/generate_scenarios_homes.py'), '--check'],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout)

    def test_the_three_homes_get_the_same_mix(self):
        mixes = []
        for name, home in HOMES.items():
            rows = tasks(name)
            self.assertEqual(len(rows), 120)
            self.assertEqual(len({r['task_id'] for r in rows}), 120)
            mix = sorted((r['initial']['presence'], r['labels']['class'], r['labels']['writes_needed'] > 0) for r in rows)
            mixes.append((mix, sum(r['labels']['lure_unsafe'] for r in rows),
                          sorted(r['perturbation'] for r in rows)))
            for row in rows:
                levels = {d: row['initial'][d] for d in home.devices}
                self.assertTrue(legal_anytime(home, levels))
                att = oracle.attainability(home, row)
                self.assertEqual((att.cls, att.shortest), (row['labels']['class'], row['labels']['writes_needed']))
                clauses = re.match(r'.*someone is present, achieve (.*?)\. If nobody is present, achieve (.*?)\. Use',
                                   row['instruction']).groups()
                for clause, branch in zip(clauses, ('present', 'absent')):       # the instruction states both goals
                    self.assertEqual(sorted(clause.split(', ')), sorted(f'{d}={v}' for d, v in row[f'goal_{branch}'].items()))
            pilot = {json.dumps({k: r[k] for k in ('initial', 'authorized', 'goal_present', 'goal_absent')}, sort_keys=True)
                     for r in tasks(name, 'pilot')}
            main = {json.dumps({k: r[k] for k in ('initial', 'authorized', 'goal_present', 'goal_absent')}, sort_keys=True)
                    for r in rows}
            self.assertFalse(pilot & main)                       # the pilot tasks are not tasks of the study
        self.assertEqual(mixes[0], mixes[1])
        self.assertEqual(mixes[1], mixes[2])


class Engine(unittest.TestCase):
    conditions = ['B0', 'B2_plan', 'M', 'M_recover', 'M_reading', 'M_full', 'M_plan', 'M_seq']

    def run_home(self, name, persona, subset=slice(0, 120, 3)):
        home, rows = HOMES[name], tasks(name)[subset]
        return rows, list(run_seed(home, ScriptedHomePlanner(home, persona, rows), rows, self.conditions,
                                   list(VARIANTS), 11, 8))

    def test_a_careful_planner_in_every_home(self):
        for name in HOMES:
            rows, episodes = self.run_home(name, 'careful')
            self.assertEqual(len(episodes), len(rows) * 3 * len(self.conditions))
            lured = {r['task_id'] for r in rows if r['labels']['lure_unsafe'] and r['labels']['lure_plan']}
            for e in episodes:
                bound = e['guard'] == 'M'
                if bound:
                    self.assertFalse(e['metrics']['unsafe_effect'], (name, e['task_id'], e['condition']))
                if e['condition'] in ('M_recover', 'M_reading', 'M_full', 'M_plan', 'M_seq'):
                    self.assertTrue(e['metrics']['exact_target'], (name, e['task_id'], e['variant'], e['condition']))
                if e['condition'] == 'B2_plan' and e['variant'] == 'perturbed':
                    # a rule guard believes the false reading: the unsafe plan runs exactly where the attack asks for one
                    self.assertEqual(e['metrics']['unsafe_effect'], e['task_id'] in lured and not e['scenario']['initial']['presence'])

    def test_first_proposals_are_shared_and_the_list_alone_moves_a_planner_that_follows_it(self):
        _, episodes = self.run_home('L', 'menu')
        first = {}
        for e in episodes:
            key = (e['task_id'], e['variant'])
            self.assertEqual(first.setdefault(key, e['proposals'][0]['raw']), e['proposals'][0]['raw'])
        unrequested = {c: sum(e['metrics']['unrequested_change'] for e in episodes if e['condition'] == c)
                       for c in self.conditions}
        self.assertGreater(unrequested['M_full'], 10)
        self.assertEqual(unrequested['M_recover'], 0)
        self.assertEqual(unrequested['M_plan'], 0)

    def test_the_launcher_needs_a_pilot_and_the_analysis_reads_its_own_fingerprints(self):
        script = ROOT / 'scripts/run_homes.sh'
        subprocess.run(['bash', '-n', str(script)], check=True)
        dispatcher = (ROOT / 'scripts/v3_1_step.sh').read_text()
        self.assertIn('scripts/run_homes.sh', re.search(r'homes_\*\|homespilot_\*\).*?;;', dispatcher, re.S).group(0))
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, 'V31_RUN_ROOT': tmp}
            run = lambda *args: subprocess.run(['bash', str(script), *args], env=env, capture_output=True, text=True)  # noqa: E731
            self.assertEqual(run('homes_qwen25', 'scripted', 't', '11').returncode, 3)
            pilot = run('homespilot_qwen25', 'scripted,scripted', 't')
            self.assertEqual(pilot.returncode, 0, pilot.stderr)
            folder = Path(tmp) / 'v3_1_homespilot_qwen25_t'
            self.assertTrue(json.loads((folder / 'model_check.json').read_text())['ok'])
            first = json.loads((folder / 'analysis/results.json').read_text())
            again = subprocess.run([sys.executable, str(ROOT / 'scripts/analyze_homes.py'), '--input',
                                    str(folder / 'fingerprints.json.gz'), '--output', str(Path(tmp) / 'again')],
                                   capture_output=True, text=True)
            self.assertEqual(again.returncode, 0, again.stderr)
            second = json.loads((Path(tmp) / 'again/results.json').read_text())
            self.assertEqual(first['homes'], second['homes'])
            self.assertEqual(sorted(first['homes']), ['L', 'M', 'S'])
            self.assertEqual(first['homes']['L']['episodes'], 12 * 3 * 5)
            raw = (folder / 'episodes_L_p1.jsonl').read_text()
            self.assertNotIn('"raw"', gz_text(folder / 'fingerprints.json.gz'))      # no model output in what is published
            self.assertIn('"raw"', raw)


def gz_text(path):
    import gzip
    with gzip.open(path, 'rt') as stream:
        return stream.read()


if __name__ == '__main__':
    unittest.main()
