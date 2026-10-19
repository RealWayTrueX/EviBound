"""HTTP contract of scripts/serve_planner.py with a scripted planner (no model, no GPU)."""

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from serve_planner import PlannerService, make_server  # noqa: E402


class FakePlanner:
    def __init__(self):
        self.seen = []

    def generate(self, batches, seed):
        self.seen.append((batches, seed))
        return [{"raw": '{"actions":[],"evidence":{}}', "parsed": {"actions": [], "evidence": {}}, "parse_error": None,
                 "input_tokens": 12, "output_tokens": 7, "latency_s": 0.01} for _ in batches]


class ServePlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        runs = Path(cls.tmp.name) / "runs"
        (runs / "demo_run").mkdir(parents=True)
        rows = [{"task_id": f"t{i % 2}", "variant": "clean", "condition": "M", "seed": 11, "n": i} for i in range(6)]
        (runs / "demo_run" / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        (runs / "demo_run" / "COMPLETE").write_text("x\n")
        (runs / "not_a_run").mkdir()
        cls.planner = FakePlanner()
        cls.service = PlannerService(cls.planner, device="cpu", runs_dir=runs, token="secret-token")
        cls.server = make_server(cls.service, "127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def request(self, path, body=None, token="secret-token"):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data, headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    def test_health_is_open_and_everything_else_needs_the_token(self):
        status, body = self.request("/health", token=None)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["auth_required"])
        self.assertEqual(self.request("/v1/models", token=None)[0], 401)
        self.assertEqual(self.request("/runs", token="wrong")[0], 401)
        self.assertEqual(self.request("/v1/chat/completions", {"messages": []}, token=None)[0], 401)

    def test_chat_completion_shape_and_seed(self):
        messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
        status, body = self.request("/v1/chat/completions", {"messages": messages, "seed": 23, "temperature": 1.5})
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["choices"][0]["message"]["content"], '{"actions":[],"evidence":{}}')
        self.assertEqual(data["usage"], {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19})
        self.assertEqual(data["evibound"]["seed"], 23)
        self.assertEqual(self.planner.seen[-1], ([messages], 23))
        self.assertEqual(data["evibound"]["sampling"]["temperature"], 0.2)  # request sampling is ignored

    def test_chat_completion_rejects_bad_input(self):
        self.assertEqual(self.request("/v1/chat/completions", {"messages": "x"})[0], 400)
        self.assertEqual(self.request("/v1/chat/completions", {"messages": [{"role": "tool", "content": "x"}]})[0], 400)
        self.assertEqual(self.request("/v1/chat/completions", {"messages": [{"role": "user", "content": "x"}], "seed": -1})[0], 400)
        self.assertEqual(self.request("/v1/chat/completions", {"messages": [{"role": "user", "content": "x"}] * 9})[0], 400)

    def test_runs_listing_and_filtered_episode_stream(self):
        status, body = self.request("/runs")
        self.assertEqual(status, 200)
        runs = json.loads(body)["runs"]
        self.assertEqual([(r["name"], r["episodes"], r["complete"]) for r in runs], [("demo_run", 6, True)])
        status, body = self.request("/runs/demo_run/episodes?task_id=t1&limit=2")
        self.assertEqual(status, 200)
        rows = [json.loads(line) for line in body.splitlines() if line.strip()]
        self.assertEqual([r["n"] for r in rows], [1, 3])
        self.assertEqual(self.request("/runs/not_a_run/episodes")[0], 404)
        self.assertEqual(self.request("/runs/..%2Fdemo_run/episodes")[0], 404)
        self.assertEqual(self.request("/runs/demo_run/episodes?limit=x")[0], 400)

    def test_non_loopback_listener_requires_a_token(self):
        with self.assertRaises(SystemExit):
            make_server(PlannerService(None, runs_dir=None, token=None), "0.0.0.0", 0)


if __name__ == "__main__":
    unittest.main()
