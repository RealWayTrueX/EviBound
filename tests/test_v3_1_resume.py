"""Resuming a v3.1 run from an output file that a crash left behind."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_experiment_v3_1 as run  # noqa: E402


def line(task, seed=11):
    return json.dumps({'task_id': task, 'variant': 'clean', 'condition': 'M', 'seed': seed}) + '\n'


class Resume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'episodes.jsonl'

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_file_is_read_as_it_is(self):
        self.path.write_text(line('a') + line('b'))
        self.assertEqual(run.resume_identities(self.path), {('a', 'clean', 'M', 11), ('b', 'clean', 'M', 11)})
        self.assertEqual(self.path.read_text(), line('a') + line('b'))

    def test_partial_last_line_is_cut_off_and_its_episode_runs_again(self):
        for tail in (line('c')[:17], line('c').rstrip('\n'), '{"task_id": "c"}\n'):
            self.path.write_text(line('a') + line('b') + tail)
            self.assertEqual(run.resume_identities(self.path), {('a', 'clean', 'M', 11), ('b', 'clean', 'M', 11)})
            self.assertEqual(self.path.read_text(), line('a') + line('b'))

    def test_damage_before_the_last_line_is_an_error(self):
        self.path.write_text(line('a') + '{"task_id": \n' + line('b'))
        with self.assertRaises(ValueError):
            run.resume_identities(self.path)
        self.assertEqual(self.path.read_text(), line('a') + '{"task_id": \n' + line('b'))


if __name__ == '__main__':
    unittest.main()
