"""v3.1 episode engine: the v3 engine with the feedback ladder of ``recovery_v3_1``.

Sequencing, budgets, seeding and scoring are those of ``runner_v3.run_seed``: one
shared first proposal per task, variant and seed is executed under every condition,
and at most one condition-specific recovery call follows. The only differences are
that the recovery turn may come from a new ladder level, which is given the rejected
proposal, and that the payload of the recovery turn is stored with the episode. A planner
role other than ``base`` changes the system prompt for the exploratory robustness arm.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any, Callable, Iterable

from evibound.backend import MAX_WRITES
from evibound.backend_v3 import WorldV3 as World
from evibound.oracle_v3 import score_episode_v3 as score_episode
from evibound.planner import batch_seed
from evibound.planner_v3_1 import messages_for_role
from evibound.recovery_v3_1 import guard_for, recovery_turn, trigger_v31
from evibound.runner_v3 import instrument

Generate = Callable[[list[list[dict[str, str]]], int], list[dict[str, Any]]]


def _cited_presence(world: World, evidence: Any) -> bool | None:
    """The trusted collector's reading of the observation the planner cited, if it has one."""
    if not isinstance(evidence, dict) or "value" not in evidence:
        return None
    try:
        return world.decode(evidence["value"])
    except Exception:  # an unhashable or otherwise malformed value has no reading
        return None


def run_seed(generate: Generate, scenarios: Iterable[dict[str, Any]], conditions: list[str],
             variants: list[str], seed: int, batch_size: int,
             completed: set[tuple[str, str, str, int]] | None = None,
             on_progress: Callable[[dict[str, Any]], None] | None = None, role: str = "base"):
    """Yield finished episodes for one seed; skips identities already completed.

    ``role`` selects the planner's system prompt (``planner_v3_1``); ``base`` is the frozen prompt.
    """
    for condition in conditions:
        guard_for(condition)
    completed = completed if completed is not None else set()
    jobs = []
    for scenario in scenarios:
        for variant in variants:
            world = World(scenario, variant)
            observation = world.observe()
            jobs.append({"scenario": scenario, "variant": variant,
                         "messages": messages_for_role(role, scenario, world.state, observation),
                         "job_id": f'{scenario["task_id"]}/{variant}/base'})
    for offset in range(0, len(jobs), batch_size):
        chunk = jobs[offset:offset + batch_size]
        if all((j["scenario"]["task_id"], j["variant"], c, seed) in completed
               for j in chunk for c in conditions):
            continue
        responses = generate([j["messages"] for j in chunk],
                             batch_seed("initial", seed, [j["job_id"] for j in chunk]))
        episodes, pending = [], []
        for job, response in zip(chunk, responses):
            scenario = job["scenario"]
            for condition in conditions:
                if (scenario["task_id"], job["variant"], condition, seed) in completed:
                    continue
                guard = guard_for(condition)
                world = World(scenario, job["variant"])
                world.observe()
                episode = {
                    "task_id": scenario["task_id"], "split": scenario["split"],
                    "family": scenario["family"], "perturbation": scenario["perturbation"],
                    "variant": job["variant"], "condition": condition, "guard": guard,
                    "physical_structure_id": scenario.get("physical_structure_id", scenario["task_id"]),
                    "seed": seed, "planner_role": role, "scenario": scenario,
                    "proposals": [copy.deepcopy(response)],
                    "recovery_trigger": None, "recovery_payload": None, "recovery_review": None,
                    "guard_execution_s": 0.0,
                }
                data = response["parsed"] or {}
                before = time.perf_counter()
                events = world.execute(data.get("actions"), data.get("evidence", {}), guard)
                episode["guard_execution_s"] += time.perf_counter() - before
                trigger = trigger_v31(condition, response, events, world.successful_writes)
                if trigger:
                    cited = _cited_presence(world, data.get("evidence"))
                    observation = world.observe()
                    episode["recovery_trigger"] = trigger
                    reason = events[-1]["reason"] if trigger == "rejection" else None
                    episode["_messages"], episode["recovery_review"] = recovery_turn(
                        condition, job["messages"], response["raw"], world.state, observation,
                        trigger, reason, MAX_WRITES - world.successful_writes,
                        presence=world.decode(observation["value"]),
                        authorized=scenario["authorized"],
                        proposal=data.get("actions"),
                        executed=sum(e["kind"] == "write" for e in events),
                        cited_presence=cited)
                    episode["recovery_payload"] = json.loads(episode["_messages"][-1]["content"])
                    pending.append(episode)
                episode["_world"] = world
                episodes.append(episode)
        for roffset in range(0, len(pending), batch_size):
            rchunk = pending[roffset:roffset + batch_size]
            retry_responses = generate(
                [e["_messages"] for e in rchunk],
                batch_seed("retry", seed, [f'{e["task_id"]}/{e["variant"]}/{e["condition"]}' for e in rchunk]))
            for episode, response in zip(rchunk, retry_responses):
                episode["proposals"].append(response)
                data = response["parsed"] or {}
                before = time.perf_counter()
                episode["_world"].execute(data.get("actions"), data.get("evidence", {}), episode["guard"])
                episode["guard_execution_s"] += time.perf_counter() - before
        for episode in episodes:
            world = episode.pop("_world")
            episode.pop("_messages", None)
            episode["trace"] = world.trace()
            episode["metrics"] = score_episode(episode["scenario"], episode["trace"])
            instrument(episode)
            proposals = episode["proposals"]
            episode["model_calls"] = len(proposals)
            episode["model_tokens"] = sum(p["input_tokens"] + p["output_tokens"] for p in proposals)
            episode["output_tokens"] = sum(p["output_tokens"] for p in proposals)
            episode["model_latency_s"] = sum(p["latency_s"] for p in proposals)
            episode["latency_s"] = episode["model_latency_s"] + episode["guard_execution_s"]
            completed.add((episode["task_id"], episode["variant"], episode["condition"], seed))
            yield episode
        if on_progress:
            on_progress({"seed": seed, "initial_jobs_done": min(offset + len(chunk), len(jobs)),
                         "initial_jobs": len(jobs)})
