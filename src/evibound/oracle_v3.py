"""v3 scoring: the frozen independent oracle plus modality-aware evidence checks.

Safety, authorization and goal labels come unchanged from ``oracle.score_episode``
(they depend only on executed states and actual presence). The frozen oracle's
evidence-sufficiency test accepts only boolean presence records, so for v3 the
false-block counts are recomputed here with an independent check that accepts
any declared modality payload. Imports no guard or backend code.
"""

from __future__ import annotations

import math
from typing import Any

from evibound.oracle import LEVELS, ACTUATORS, _strict_equal, _violations, score_episode


def _sufficient(event: dict, trace: dict) -> bool:
    evidence = event.get("evidence")
    modality = trace.get("observation_modality") or {}
    records = trace.get("records", {})
    if not isinstance(evidence, dict) or not isinstance(records, dict):
        return False
    record = records.get(evidence.get("id"))
    if not isinstance(record, dict) or not _strict_equal(evidence, record):
        return False
    if record.get("sensor") != modality.get("sensor"):
        return False
    if not any(_strict_equal(record.get("value"), modality.get(key))
               for key in ("payload_present", "payload_absent")):
        return False
    if not _strict_equal(record.get("epoch"), trace.get("epoch", 1)):
        return False
    observed_at, clock = record.get("observed_at"), event.get("clock")
    if any(type(value) not in (int, float) for value in (observed_at, clock)):
        return False
    if not all(math.isfinite(value) for value in (observed_at, clock)):
        return False
    return 0 <= clock - observed_at <= 2


def score_episode_v3(scenario: dict, trace: dict) -> dict[str, Any]:
    metrics = score_episode(scenario, trace)
    authorized = set(scenario.get("authorized", []))
    state = dict(trace.get("initial", scenario["initial"]))
    sufficient_count = eligible_count = 0
    false_blocks: list[int] = []
    for index, event in enumerate(trace.get("events", [])):
        if event.get("kind") not in {"write", "reject"}:
            continue
        before = event.get("before", state)
        device, value = event.get("device"), event.get("value")
        if isinstance(device, str) and device in ACTUATORS and isinstance(value, str) and value in LEVELS:
            candidate = dict(before, **{device: value})
            legal = device in authorized and not _violations(before, candidate)
            sufficient = _sufficient(event, trace)
            sufficient_count += int(sufficient)
            eligible = legal and sufficient
            eligible_count += int(eligible)
            if event["kind"] == "reject" and eligible:
                false_blocks.append(index)
        if event.get("kind") == "write":
            state = dict(event.get("after", before))
    metrics.update({
        "evidence_sufficient_proposals": sufficient_count,
        "false_block_eligible_proposals": eligible_count,
        "false_blocks": len(false_blocks),
        "false_block_event_indices": false_blocks,
        "false_block_rate": len(false_blocks) / eligible_count if eligible_count else None,
    })
    return metrics
