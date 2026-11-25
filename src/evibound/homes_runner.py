"""Engine of the scale study: the frozen v3.1 engine (``runner_v3_1.run_seed``) for a home of any size.

One first proposal per task, variant and seed is shared by every condition; the single recovery
call is condition-specific. Episodes are scored by ``homes_oracle`` from their executed writes.
"""

from __future__ import annotations

import copy
import json
import re
import time
from typing import Any, Callable, Iterable

from evibound import homes_oracle as oracle
from evibound.homes import HOMES, LEVELS, Home, HomeWorld
from evibound.homes_ladder import (CONDITIONS, best_plan, messages_for, recovery_turn, situation, trigger)
from evibound.planner import batch_seed

Generate = Callable[[list[list[dict[str, str]]], int], list[dict[str, Any]]]


def _cited_presence(world: HomeWorld, evidence: Any) -> bool | None:
    if isinstance(evidence, dict) and "value" in evidence:
        try:
            return world.decode(evidence["value"])
        except Exception:     # a value the collector cannot read
            return None
    return None


def run_seed(home: Home, generate: Generate, scenarios: Iterable[dict[str, Any]], conditions: list[str],
             variants: list[str], seed: int, batch_size: int,
             completed: set[tuple[str, str, str, int]] | None = None,
             on_progress: Callable[[dict[str, Any]], None] | None = None):
    """Yield finished episodes for one seed; identities in ``completed`` are skipped."""
    for condition in conditions:
        if condition not in CONDITIONS:
            raise ValueError(f"Unknown condition: {condition}")
    completed = completed if completed is not None else set()
    scenarios = list(scenarios)
    cache = {s["task_id"]: oracle.attainability(home, s) for s in scenarios}
    jobs = []
    for scenario in scenarios:
        for variant in variants:
            world = HomeWorld(home, scenario, variant)
            observation = world.observe()
            jobs.append({"scenario": scenario, "variant": variant,
                         "messages": messages_for(home, scenario, world.state, observation),
                         "job_id": f'{home.name}/{scenario["task_id"]}/{variant}/base'})
    for offset in range(0, len(jobs), batch_size):
        chunk = jobs[offset:offset + batch_size]
        if all((j["scenario"]["task_id"], j["variant"], c, seed) in completed for j in chunk for c in conditions):
            continue
        responses = generate([j["messages"] for j in chunk], batch_seed("initial", seed, [j["job_id"] for j in chunk]))
        episodes, pending = [], []
        for job, response in zip(chunk, responses):
            scenario = job["scenario"]
            for condition in conditions:
                if (scenario["task_id"], job["variant"], condition, seed) in completed:
                    continue
                guard = CONDITIONS[condition].guard
                world = HomeWorld(home, scenario, job["variant"])
                world.observe()
                episode = {"home": home.name, "task_id": scenario["task_id"], "variant": job["variant"],
                           "condition": condition, "guard": guard, "seed": seed, "scenario": scenario,
                           "proposals": [copy.deepcopy(response)], "recovery_trigger": None,
                           "recovery_payload": None, "recovery_review": None, "recovery_form": None,
                           "guard_execution_s": 0.0}
                data = response["parsed"] or {}
                before = time.perf_counter()
                events = world.execute(data.get("actions"), data.get("evidence", {}), guard)
                episode["guard_execution_s"] += time.perf_counter() - before
                trig = trigger(home, condition, response, events, world.successful_writes)
                if trig:
                    cited = _cited_presence(world, data.get("evidence"))
                    observation = world.observe()
                    reason = events[-1]["reason"] if trig == "rejection" else None
                    executed = sum(e["kind"] == "write" for e in events)
                    remaining = home.max_writes - world.successful_writes
                    presence = world.decode(observation["value"])
                    episode["recovery_trigger"] = trig
                    episode["_messages"], episode["recovery_review"] = recovery_turn(
                        home, condition, job["messages"], response["raw"], world.state, observation, trig, reason,
                        remaining, presence=presence, authorized=scenario["authorized"],
                        proposal=data.get("actions"), executed=executed, cited_presence=cited)
                    episode["recovery_payload"] = json.loads(episode["_messages"][-1]["content"])
                    episode["recovery_form"] = situation(
                        home, trig, episode["recovery_payload"].get("actuators"), presence, scenario["authorized"],
                        data.get("actions"), executed, reason, remaining, cited)
                    pending.append(episode)
                episode["_world"] = world
                episodes.append(episode)
        for roffset in range(0, len(pending), batch_size):
            rchunk = pending[roffset:roffset + batch_size]
            retries = generate([e["_messages"] for e in rchunk],
                               batch_seed("retry", seed, [f'{home.name}/{e["task_id"]}/{e["variant"]}/{e["condition"]}'
                                                          for e in rchunk]))
            for episode, response in zip(rchunk, retries):
                episode["proposals"].append(response)
                data = response["parsed"] or {}
                before = time.perf_counter()
                episode["_world"].execute(data.get("actions"), data.get("evidence", {}), episode["guard"])
                episode["guard_execution_s"] += time.perf_counter() - before
        for episode in episodes:
            world = episode.pop("_world")
            episode.pop("_messages", None)
            episode["trace"] = world.trace()
            writes = [(e["device"], e["value"]) for e in episode["trace"]["events"] if e["kind"] == "write"]
            episode["writes"] = [list(w) for w in writes]
            episode["metrics"] = oracle.score(home, episode["scenario"], writes, cache[episode["task_id"]])
            proposals = episode["proposals"]
            episode["model_calls"] = len(proposals)
            episode["model_tokens"] = sum(p["input_tokens"] + p["output_tokens"] for p in proposals)
            episode["output_tokens"] = sum(p["output_tokens"] for p in proposals)
            episode["model_latency_s"] = sum(p["latency_s"] for p in proposals)
            completed.add((episode["task_id"], episode["variant"], episode["condition"], seed))
            yield episode
        if on_progress:
            on_progress({"seed": seed, "initial_jobs_done": min(offset + len(chunk), len(jobs)),
                         "initial_jobs": len(jobs)})


# ---------------------------------------------------------------- planners without a model (tests, dry runs)

class ScriptedHomePlanner:
    """A deterministic planner, to exercise the pipeline without a model.

    ``careful`` plans a shortest rule-abiding way to the goal of the branch that the delivered
    observation selects. ``hasty`` writes the goal levels directly, without the middle levels.
    ``menu`` is careful, and after a refusal that lists legal writes it also makes the first
    listed write that its plan does not contain. Each cites the observation it was given.
    """

    def __init__(self, home: Home, persona: str, scenarios: Iterable[dict[str, Any]]):
        if persona not in ("careful", "hasty", "menu"):
            raise ValueError(f"unknown persona {persona}")
        self.home, self.persona = home, persona
        self.tasks = {s["instruction"]: s for s in scenarios}

    def __call__(self, message_batches: list[list[dict[str, str]]], seed: int) -> list[dict[str, Any]]:
        return [self._answer(messages, len(message_batches), seed) for messages in message_batches]

    def _plan(self, task, levels, observation, budget, direct=False):
        present = observation["value"] is True
        goal = task["goal_present"] if present else task["goal_absent"]
        if direct:
            return [{"device": d, "value": v} for d, v in goal.items() if levels[d] != v][:budget]
        plan, _ = best_plan(self.home, levels, present, tuple(task["authorized"]), goal, budget)
        return plan

    def _answer(self, messages, batch, seed):
        first = messages[1]["content"]
        task = self.tasks[re.match(r"Task: (.*)\n", first).group(1)]
        if len(messages) == 2:
            levels = json.loads(re.search(r"Current actuator levels: (\{.*\})\n", first).group(1))
            observation = json.loads(re.search(r"into evidence\): (\{.*\})\n", first).group(1))
            actions = self._plan(task, levels, observation, self.home.max_writes, direct=self.persona == "hasty")
        else:
            payload = json.loads(messages[-1]["content"])
            levels, observation = payload["actuators"], payload["fresh_observation"]
            actions = self._plan(task, levels, observation, payload["writes_remaining"])
            if self.persona == "menu" and payload.get("legal_writes_now"):
                extra = next((w for w in payload["legal_writes_now"] if w not in actions), None)
                if extra and len(actions) < payload["writes_remaining"]:
                    actions = actions + [extra]
        raw = json.dumps({"actions": actions, "evidence": observation})
        return {"raw": raw, "parsed": json.loads(raw), "parse_error": None, "input_tokens": 0, "output_tokens": 0,
                "latency_s": 0.0, "batch_latency_s": 0.0, "batch_size": batch, "batch_seed": seed}


__all__ = ["HOMES", "LEVELS", "ScriptedHomePlanner", "run_seed"]
