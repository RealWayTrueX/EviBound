"""Week-11 v3 episode engine: shared first proposal, condition-specific recovery.

Planner-agnostic so the full pipeline can be exercised on CPU with a scripted
planner. ``scripts/run_experiment_v3.py`` binds it to the frozen local model.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Callable, Iterable

from evibound.backend import MAX_WRITES
from evibound.backend_v3 import WorldV3 as World
from evibound.oracle_v3 import score_episode_v3 as score_episode
from evibound.planner import batch_seed
from evibound.planner_v3 import messages_for_v3
from evibound.recovery import (MAX_INTERFACE_REREADS, MAX_RESUBMISSIONS, recovery_messages,
                               recovery_trigger, spec_for)

Generate = Callable[[list[list[dict[str, str]]], int], list[dict[str, Any]]]


def instrument(episode: dict[str, Any]) -> dict[str, Any]:
    proposals = episode["proposals"]
    parsed = [p.get("parsed") or {} for p in proposals]
    failed = [bool(p.get("parse_error")) for p in proposals]
    empty = [not (d.get("actions") or []) and not bad for d, bad in zip(parsed, failed)]
    metrics = episode["metrics"]
    writes = int(metrics.get("executed_writes", 0))
    metrics.update({
        "empty_plan": all(empty) and bool(empty),
        "empty_plan_initial": bool(empty) and empty[0],
        "empty_plan_final": bool(empty) and empty[-1],
        "parse_failure": any(failed),
        "parse_failure_initial": bool(failed) and failed[0],
        "parse_failure_final": bool(failed) and failed[-1],
        "parse_failures": sum(failed),
        "resubmissions": max(0, len(proposals) - 1),
        "rejection_rereads": int(episode["recovery_trigger"] == "rejection"),
        "confirmation_rereads": int(episode["recovery_trigger"] == "empty_plan"),
        "interface_rereads": int(episode["recovery_trigger"] is not None),
        "writes_remaining": max(0, MAX_WRITES - writes),
    })
    episode["recovery_budget"] = {
        "max_successful_writes": MAX_WRITES,
        "max_interface_rereads": MAX_INTERFACE_REREADS,
        "max_resubmissions": MAX_RESUBMISSIONS,
        "resubmissions_used": metrics["resubmissions"],
        "interface_rereads_used": metrics["interface_rereads"],
        "successful_writes": writes,
        "writes_remaining": metrics["writes_remaining"],
    }
    return episode


def run_seed(generate: Generate, scenarios: Iterable[dict[str, Any]], conditions: list[str],
             variants: list[str], seed: int, batch_size: int,
             completed: set[tuple[str, str, str, int]] | None = None,
             on_progress: Callable[[dict[str, Any]], None] | None = None):
    """Yield finished episodes for one seed; skips identities already completed."""
    for condition in conditions:
        spec_for(condition)
    completed = completed if completed is not None else set()
    jobs = []
    for scenario in scenarios:
        for variant in variants:
            world = World(scenario, variant)
            observation = world.observe()
            jobs.append({"scenario": scenario, "variant": variant,
                         "messages": messages_for_v3(scenario, world.state, observation),
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
                guard = spec_for(condition).guard
                world = World(scenario, job["variant"])
                world.observe()
                episode = {
                    "task_id": scenario["task_id"], "split": scenario["split"],
                    "family": scenario["family"], "perturbation": scenario["perturbation"],
                    "variant": job["variant"], "condition": condition, "guard": guard,
                    "physical_structure_id": scenario.get("physical_structure_id", scenario["task_id"]),
                    "seed": seed, "scenario": scenario, "proposals": [copy.deepcopy(response)],
                    "recovery_trigger": None, "guard_execution_s": 0.0,
                }
                data = response["parsed"] or {}
                before = time.perf_counter()
                events = world.execute(data.get("actions"), data.get("evidence", {}), guard)
                episode["guard_execution_s"] += time.perf_counter() - before
                trigger = recovery_trigger(condition, response, events, world.successful_writes)
                if trigger:
                    observation = world.observe()
                    episode["recovery_trigger"] = trigger
                    reason = events[-1]["reason"] if trigger == "rejection" else None
                    episode["_messages"] = recovery_messages(
                        condition, job["messages"], response["raw"], world.state, observation,
                        trigger, reason, MAX_WRITES - world.successful_writes)
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
