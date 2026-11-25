"""The exploratory second-model arm of v3.1: the frozen runner with one change around it."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

import run_experiment_v3_1_model as model_run  # noqa: E402
import v3_1_model_check as check  # noqa: E402
from evibound import planner_models  # noqa: E402
from evibound.planner import LocalPlanner  # noqa: E402


class Tokenizer:
    """A chat template in the manner of Qwen3 (``thinking``) or of Qwen2.5 (no switch)."""

    def __init__(self, thinking):
        self.thinking = thinking
        self.chat_template = "{% if enable_thinking is defined %}" if thinking else "plain"
        self.calls = []

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True, **extra):
        self.calls.append(extra)
        tail = '<|im_start|>assistant\n'
        if self.thinking and extra.get('enable_thinking') is False:
            tail += '<think>\n\n</think>\n\n'
        return ''.join(m['content'] for m in messages) + tail


def planner(tokenizer):
    def init(self, path, max_new_tokens=224):
        self.tokenizer = tokenizer
    with mock.patch.object(LocalPlanner, '__init__', init):
        return planner_models.DirectAnswerPlanner('unused')


class DirectAnswer(unittest.TestCase):
    def test_the_template_is_rendered_with_thinking_switched_off(self):
        tokenizer = Tokenizer(thinking=True)
        subject = planner(tokenizer)
        tokenizer.calls.clear()
        # the call the frozen planner makes
        text = subject.tokenizer.apply_chat_template([{'role': 'user', 'content': 'x'}], tokenize=False,
                                                     add_generation_prompt=True)
        self.assertEqual(tokenizer.calls, [{'enable_thinking': False}])
        self.assertTrue(text.endswith('<think>\n\n</think>\n\n'))
        self.assertEqual(subject.switch['switch_changes_the_prompt'], True)
        self.assertEqual(subject.switch['template_mentions_enable_thinking'], True)
        self.assertEqual(subject.switch['default_equals_thinking_on'], True)

    def test_a_template_without_the_switch_renders_as_before(self):
        tokenizer = Tokenizer(thinking=False)
        subject = planner(tokenizer)
        messages = [{'role': 'user', 'content': 'x'}]
        self.assertEqual(subject.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True),
                         Tokenizer(thinking=False).apply_chat_template(messages))
        self.assertEqual(subject.switch['switch_changes_the_prompt'], False)

    def test_only_the_rendering_differs_from_the_frozen_planner(self):
        """Sampling, token limit, seeding and parsing stay the frozen code: nothing else is defined here."""
        own = {name for name in vars(planner_models.DirectAnswerPlanner) if not name.startswith('__')}
        self.assertEqual(own, set())
        self.assertIs(planner_models.DirectAnswerPlanner.generate, LocalPlanner.generate)


class Parts(unittest.TestCase):
    def test_parts_split_the_tasks_without_overlap(self):
        tasks = [json.loads(line)['task_id'] for line in
                 (ROOT / 'data/scenarios_v3_1/holdout.jsonl').read_text().splitlines()]
        for parts in (1, 2, 3):
            chunks = [model_run.part_task_ids('v3_1', 'holdout', f'{i}/{parts}') for i in range(1, parts + 1)]
            self.assertEqual(sorted(t for chunk in chunks for t in chunk), sorted(tasks))
            self.assertLessEqual(max(map(len, chunks)) - min(map(len, chunks)), 1)
        with self.assertRaises(ValueError):
            model_run.part_task_ids('v3_1', 'holdout', '3/2')


def answer(raw='{}', parsed=True, tokens=40):
    return {'raw': raw, 'parsed': {'actions': [], 'evidence': {}} if parsed else None, 'output_tokens': tokens}


class Plumbing(unittest.TestCase):
    def record(self, episodes):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'episodes.jsonl'
            path.write_text(''.join(json.dumps(e) + '\n' for e in episodes))
            return check.plumbing([path])

    def episode(self, task, condition='M', proposals=None):
        return {'task_id': task, 'variant': 'clean', 'seed': 11, 'condition': condition,
                'proposals': proposals or [answer()]}

    def test_the_first_proposal_is_counted_once_for_all_conditions(self):
        record = self.record([self.episode('a', 'M', [answer(), answer()]), self.episode('a', 'B0')])
        self.assertEqual(record['first_proposals']['answers'], 1)
        self.assertEqual(record['recovery_answers']['answers'], 1)
        self.assertTrue(record['ok'])

    def test_reasoning_text_fails_the_check(self):
        record = self.record([self.episode('a', proposals=[answer('<think>hm</think>{}', parsed=False)])] +
                             [self.episode(str(i)) for i in range(20)])
        self.assertEqual(record['first_proposals']['with_reasoning_text'], 1)
        self.assertFalse(record['ok'])

    def test_too_many_unparsed_first_proposals_fail_the_check(self):
        bad = [self.episode(f'b{i}', proposals=[answer('no', parsed=False, tokens=224)]) for i in range(3)]
        good = [self.episode(f'g{i}') for i in range(7)]
        record = self.record(bad + good)
        self.assertEqual(record['first_proposals']['at_token_limit'], 3)
        self.assertFalse(record['ok'])                      # 30 percent
        self.assertTrue(self.record(bad[:2] + good + [self.episode('g7')])['ok'])   # 20 percent

    def test_the_file_record_reads_no_hidden_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'config.json').write_text('{"model_type": "qwen3"}')
            Path(tmp, '.secret').write_text('x')
            Path(tmp, 'notes.bin').write_text('x')
            record = check.model_files(tmp)
        self.assertEqual(list(record['files']), ['config.json'])
        self.assertEqual(record['config']['model_type'], 'qwen3')


class Launcher(unittest.TestCase):
    script = ROOT / 'scripts/run_v3_1_model.sh'

    def run_stage(self, root, *args):
        env = {**os.environ, 'V31_RUN_ROOT': str(root)}
        return subprocess.run(['bash', str(self.script), *args], env=env, capture_output=True, text=True)

    def test_it_parses_and_the_dispatcher_sends_the_arm_to_it(self):
        subprocess.run(['bash', '-n', str(self.script)], check=True)
        dispatcher = (ROOT / 'scripts/v3_1_step.sh').read_text()
        branch = re.search(r'model_\*\|modelpilot_\*\).*?;;', dispatcher, re.S).group(0)
        self.assertIn('scripts/run_v3_1_model.sh', branch)
        self.assertIn('nice -n 10', branch)

    def test_the_holdout_run_needs_the_freeze_and_a_pilot_that_passed(self):
        text = self.script.read_text()
        self.assertIn('set -euo pipefail', text)
        guard = re.search(r'if \[ "\$split" = holdout \]; then.*?\nfi\n', text, re.S).group(0)
        self.assertIn('freeze_v3_1_prereg.py --verify', guard)
        self.assertIn('model_check.json', guard)
        with tempfile.TemporaryDirectory() as tmp:
            refused = self.run_stage(tmp, 'model_qwen3', 'scripted', 't', '11')
            self.assertEqual(refused.returncode, 3, refused.stderr)
            self.assertFalse(list(Path(tmp).glob('*/episodes_*.jsonl')))

    def test_a_pilot_runs_in_two_parts_and_records_the_form_of_the_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = self.run_stage(tmp, 'modelpilot_qwen3', 'scripted,scripted', 't')
            self.assertEqual(done.returncode, 0, done.stderr)
            run = Path(tmp) / 'v3_1_modelpilot_qwen3_t'
            self.assertTrue((run / 'COMPLETE').exists())
            self.assertEqual((run / 'parts.txt').read_text().strip(), '2')
            episodes = [json.loads(line) for part in (1, 2)
                        for line in (run / f'episodes_dev_p{part}.jsonl').read_text().splitlines()]
            tasks = len((ROOT / 'data/scenarios_v3_1/dev.jsonl').read_text().splitlines())
            self.assertEqual(len(episodes), tasks * 3 * 9)            # three variants, nine conditions, one seed
            self.assertEqual(len({(e['task_id'], e['variant'], e['condition'], e['seed']) for e in episodes}),
                             len(episodes))
            self.assertTrue(json.loads((run / 'model_check.json').read_text())['ok'])
            self.assertEqual(json.loads((run / 'analysis/results.json').read_text())['metadata']['stage'], 'dev')


if __name__ == '__main__':
    unittest.main()
