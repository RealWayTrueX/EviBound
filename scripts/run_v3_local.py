#!/usr/bin/env python3
"""Run the v3 recovery pipeline on a laptop: real runner, oracle and analysis, any planner.

Exploratory tooling only. It exercises exactly the frozen code path
(``runner_v3.run_seed`` -> ``oracle_v3`` -> ``analyze_v3``) but with a planner
the preregistration does not cover, so its output must never be mixed with or
cited as the confirmatory holdout result (bf16 Qwen2.5-7B on CUDA).

Planners:
  --planner scripted:careful   shortest legal plan for the branch the observation suggests
  --planner scripted:hasty     jumps straight to target levels, ignores authorization until told
  --planner scripted:empty     empty first plan, plans properly only when asked to confirm
  --planner openai             any OpenAI-compatible chat endpoint (Ollama, LM Studio, vLLM)

Examples (from the repository root):
  python3 scripts/run_v3_local.py --split dev --planner scripted:hasty --output /tmp/v3_local/dev
  python3 scripts/run_v3_local.py --split dev --planner openai --base-url http://127.0.0.1:11434/v1 \\
      --model qwen2.5:7b-instruct --seeds 11 --output /tmp/v3_local/ollama_dev

The output directory receives episodes.jsonl, run.config.json and analysis/
(results.json, summary.csv, report.html) produced by scripts/analyze_v3.py.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evibound.backend import LEVELS, _policy_violation  # noqa: E402
from evibound.planner import parse_response  # noqa: E402
from evibound.recovery import V3_CONDITIONS  # noqa: E402
from evibound.runner_v3 import run_seed  # noqa: E402

OBS_MARKER = "Observation (copy only this object into evidence): "
VARIANTS = ("clean", "perturbed", "boundary")


# ---------------------------------------------------------------- scripted planners
def _believed_presence(scenario, observation):
    payloads = scenario["observation"]
    for presence, key in ((True, "payload_present"), (False, "payload_absent")):
        if json.dumps(observation["value"], sort_keys=True) == json.dumps(payloads[key], sort_keys=True):
            return presence
    return False


def _target(scenario, presence, authorized_only):
    goal = scenario["goal_present" if presence else "goal_absent"]
    if not authorized_only:
        return goal
    sub = scenario["authorized_subgoal_present" if presence else "authorized_subgoal_absent"]
    if sub is not None:
        return sub
    return {d: v for d, v in goal.items() if d in scenario["authorized"]}


def _shortest_legal_plan(state, target, presence, authorized, budget):
    """Breadth-first search over single writes the guard would accept (same as demo/engine.js)."""
    start = (state["light"], state["fan"])
    done = lambda s: all(dict(zip(("light", "fan"), s))[d] == v for d, v in target.items())  # noqa: E731
    queue, seen = deque([(start, [])]), {start}
    while queue:
        current, path = queue.popleft()
        if done(current):
            return path
        if len(path) >= budget:
            continue
        actuators = dict(zip(("light", "fan"), current))
        for device in ("light", "fan"):
            if device not in target:
                continue
            for value in ("off", "low", "high"):
                if actuators[device] == value:
                    continue
                if _policy_violation(actuators, device, value, presence, tuple(authorized)) is not None:
                    continue
                nxt = tuple(dict(actuators, **{device: value})[d] for d in ("light", "fan"))
                if nxt in seen:
                    continue
                seen.add(nxt)
                queue.append((nxt, path + [{"device": device, "value": value}]))
    return []


def _direct_plan(state, target):
    return [{"device": d, "value": v} for d, v in (("light", target.get("light")), ("fan", target.get("fan")))
            if v is not None and state[d] != v]


class ScriptedPlanner:
    """Deterministic personas that mirror demo/engine.js scriptedPlan; not a model."""

    def __init__(self, persona, scenarios):
        if persona not in ("careful", "hasty", "empty"):
            raise ValueError("persona must be careful, hasty or empty")
        self.persona = persona
        self.by_instruction = {}
        for scenario in scenarios:
            self.by_instruction.setdefault(scenario["instruction"], []).append(scenario)

    def _scenario_for(self, messages):
        task_line = messages[1]["content"].split("\n", 1)[0]
        instruction = task_line[len("Task: "):]
        candidates = self.by_instruction[instruction]
        authorized = json.loads(messages[1]["content"].split("Authorized devices: ", 1)[1].split("\n", 1)[0])
        matches = [s for s in candidates if s["authorized"] == authorized]
        return matches[0]

    def _plan(self, scenario, state, observation, turn, feedback, budget):
        presence = _believed_presence(scenario, observation)
        informed = bool(feedback and (feedback.get("rule_explanation") or feedback.get("legal_writes_now")))
        confirming = bool(feedback and feedback.get("execution_result") == "no writes submitted")
        if self.persona == "empty" and turn == 0:
            return []
        if self.persona == "hasty" and not (turn == 1 and (informed or confirming)):
            return _direct_plan(state, _target(scenario, presence, False))
        return _shortest_legal_plan(state, _target(scenario, presence, True), presence,
                                    scenario["authorized"], budget)

    def __call__(self, batches, seed):
        out = []
        for messages in batches:
            scenario = self._scenario_for(messages)
            user = messages[1]["content"]
            first_state = json.loads(user.split("Current actuator levels: ", 1)[1].split("\n", 1)[0])
            first_obs = json.loads(user.split(OBS_MARKER, 1)[1].split("\n", 1)[0])
            last = messages[-1]["content"]
            if len(messages) == 2:
                actions = self._plan(scenario, first_state, first_obs, 0, None, 3)
                evidence = first_obs
            else:
                payload = json.loads(last)
                actions = self._plan(scenario, payload["actuators"], payload["fresh_observation"], 1,
                                     payload, payload["writes_remaining"])
                evidence = payload["fresh_observation"]
            raw = json.dumps({"actions": actions, "evidence": evidence})
            parsed, error = parse_response(raw)
            out.append({"raw": raw, "parsed": parsed, "parse_error": error, "input_tokens": 0,
                        "output_tokens": 0, "latency_s": 0.0, "batch_latency_s": 0.0,
                        "batch_size": len(batches), "batch_seed": seed})
        return out


# ---------------------------------------------------------------- OpenAI-compatible planner
class OpenAIPlanner:
    """Sequential calls to a chat-completions endpoint; sampling mirrors the frozen planner."""

    def __init__(self, base_url, model, *, api_key_env=None, timeout_s=600, max_new_tokens=224,
                 temperature=0.2, top_p=0.9, top_k=20):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model, self.timeout_s = model, timeout_s
        self.sampling = {"max_tokens": max_new_tokens, "temperature": temperature, "top_p": top_p,
                         "top_k": top_k}
        self.headers = {"Content-Type": "application/json"}
        if api_key_env and os.environ.get(api_key_env):
            self.headers["Authorization"] = "Bearer " + os.environ[api_key_env]

    def _one(self, messages, seed):
        body = {"model": self.model, "messages": messages, "stream": False, "seed": seed, **self.sampling}
        request = urllib.request.Request(self.url, json.dumps(body).encode(), self.headers)
        start = time.perf_counter()
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            data = json.loads(response.read())
        elapsed = time.perf_counter() - start
        raw = data["choices"][0]["message"]["content"].strip()
        usage = data.get("usage") or {}
        parsed, error = parse_response(raw)
        return {"raw": raw, "parsed": parsed, "parse_error": error,
                "input_tokens": int(usage.get("prompt_tokens") or 0),
                "output_tokens": int(usage.get("completion_tokens") or 0),
                "latency_s": elapsed, "batch_latency_s": elapsed, "batch_size": 1, "batch_seed": seed}

    def __call__(self, batches, seed):
        return [self._one(messages, seed) for messages in batches]


# ---------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["dev", "holdout"], required=True)
    parser.add_argument("--planner", required=True,
                        help="scripted:careful | scripted:hasty | scripted:empty | openai")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--model", default="qwen2.5:7b-instruct")
    parser.add_argument("--api-key-env", help="environment variable holding a bearer token (optional)")
    parser.add_argument("--conditions", nargs="+", default=list(V3_CONDITIONS))
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS))
    parser.add_argument("--seeds", nargs="+", type=int, default=[11])
    parser.add_argument("--task-ids", nargs="+")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True, help="run directory (created)")
    parser.add_argument("--bootstrap-resamples", type=int, default=10000)
    parser.add_argument("--no-analysis", action="store_true")
    args = parser.parse_args()

    scenario_path = ROOT / "data" / "scenarios_v3" / f"{args.split}.jsonl"
    scenarios = [json.loads(line) for line in scenario_path.read_text().splitlines() if line.strip()]
    if args.task_ids:
        scenarios = [s for s in scenarios if s["task_id"] in args.task_ids]
        if len(scenarios) != len(set(args.task_ids)):
            sys.exit("unknown or split-mismatched task id")
    if args.planner.startswith("scripted:"):
        planner = ScriptedPlanner(args.planner.split(":", 1)[1], scenarios)
        planner_desc = {"kind": "scripted", "persona": args.planner.split(":", 1)[1]}
    elif args.planner == "openai":
        planner = OpenAIPlanner(args.base_url, args.model, api_key_env=args.api_key_env)
        planner_desc = {"kind": "openai_compatible", "base_url": args.base_url, "model": args.model}
    else:
        sys.exit("--planner must be scripted:<persona> or openai")

    args.output.mkdir(parents=True, exist_ok=True)
    episodes_path = args.output / "episodes.jsonl"
    completed = set()
    if episodes_path.exists():
        for line in episodes_path.read_text().splitlines():
            row = json.loads(line)
            completed.add((row["task_id"], row["variant"], row["condition"], row["seed"]))
    config = {
        "purpose": "EXPLORATORY local run; not the preregistered holdout (planner/precision differ)",
        "split": args.split, "planner": planner_desc, "conditions": args.conditions,
        "variants": args.variants, "seeds": args.seeds, "task_ids": args.task_ids,
        "dataset_sha256": __import__("hashlib").sha256(scenario_path.read_bytes()).hexdigest(),
        "start_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "resumed_episodes": len(completed),
    }
    (args.output / "run.config.json").write_text(json.dumps(config, indent=2) + "\n")
    expected = len(scenarios) * len(args.variants) * len(args.conditions) * len(args.seeds)
    start, count = time.perf_counter(), 0
    with episodes_path.open("a", buffering=1) as out:
        for seed in args.seeds:
            def progress(info, seed=seed):
                print(json.dumps({**info, "episodes_written": count,
                                  "elapsed_s": round(time.perf_counter() - start, 1)}), flush=True)
            for episode in run_seed(planner, scenarios, args.conditions, args.variants, seed,
                                    args.batch_size, completed, progress):
                out.write(json.dumps(episode, sort_keys=True) + "\n")
                count += 1
    config.update({"new_episodes": count, "total_episodes": len(completed),
                   "expected_episodes": expected, "wall_elapsed_s": round(time.perf_counter() - start, 1),
                   "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    (args.output / "run.config.json").write_text(json.dumps(config, indent=2) + "\n")
    print(json.dumps({"episodes": len(completed), "expected": expected, "output": str(episodes_path)}))
    if args.no_analysis:
        return 0
    if len(completed) != expected:
        print("episode count differs from the full matrix; analysis skipped", file=sys.stderr)
        return 1
    # analyze_v3.py is part of the v3 freeze and cannot grow a new stage, so every local run is
    # analysed as "dev" (its exploratory banner) and the report is stamped as a local run.
    analysis_dir = args.output / "analysis_exploratory"
    code = subprocess.call([sys.executable, str(ROOT / "scripts" / "analyze_v3.py"), "--stage", "dev",
                            "--input", str(episodes_path), "--output", str(analysis_dir),
                            "--bootstrap-resamples", str(args.bootstrap_resamples)], cwd=str(ROOT))
    report = analysis_dir / "report.html"
    if report.exists():
        banner = (f'<p style="background:#ffe0e0;border-left:4px solid #c00;padding:8px"><b>本地探索性运行 / '
                  f'EXPLORATORY LOCAL RUN</b> — split <code>{args.split}</code>, planner '
                  f'<code>{json.dumps(planner_desc)}</code>. Not the preregistered holdout; '
                  f'never cite these numbers as results.</p>')
        text = report.read_text(encoding="utf-8")
        report.write_text(text.replace("<body>", "<body>" + banner, 1), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
