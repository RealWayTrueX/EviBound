"""v3 multi-modality world: same devices, rules and guards as the frozen v2 backend.

Each v3 task fixes an observation modality and the two collector payloads that
modality produces (one when someone is present, one when nobody is). Records
keep the v2 shape (id, sensor, value, observed_at, epoch); only ``value`` may be
a number object, caption text or a combined object instead of a boolean.

The trusted collector interprets a payload by exact lookup against the task's
two declared payloads. That lookup stands in for a real sensor-fusion or
captioning pipeline and is part of the trusted base, like the record store.
Tamper replaces the current record's value with the opposite payload; replay
serves the authentic old record, exactly as in v2. ``backend.py`` is untouched.
"""

from __future__ import annotations

from copy import deepcopy
import math
from numbers import Real
from types import MappingProxyType
from typing import Any

from evibound.backend import (CONDITIONS, MAX_OBSERVATION_AGE, MAX_WRITES, World,
                              _action_has_schema, _policy_violation)

MODALITIES = ("presence_flag", "motion_timer", "camera_caption", "multi_sensor")
SENSOR_NAMES = {"presence_flag": "presence", "motion_timer": "motion",
                "camera_caption": "camera", "multi_sensor": "multi"}


def _json_value(value: Any) -> bool:
    if type(value) in (bool, str):
        return True
    if isinstance(value, Real) and not isinstance(value, bool):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _json_value(v) for k, v in value.items())
    return False


def _evidence_has_schema(evidence: Any) -> bool:
    if not isinstance(evidence, dict):
        return False
    timestamp = evidence.get("observed_at")
    return (
        isinstance(evidence.get("id"), str)
        and isinstance(evidence.get("sensor"), str)
        and "value" in evidence and _json_value(evidence["value"])
        and isinstance(timestamp, Real) and not isinstance(timestamp, bool)
        and math.isfinite(timestamp)
        and type(evidence.get("epoch")) is int
    )


class WorldV3(World):
    """v2 World with modality payloads; guard decisions use decoded presence."""

    def __init__(self, scenario: dict[str, Any], variant: str):
        super().__init__(scenario, variant)
        observation = scenario.get("observation")
        if not isinstance(observation, dict) or observation.get("modality") not in MODALITIES:
            raise ValueError("v3 scenario needs observation.modality in " + ", ".join(MODALITIES))
        present, absent = observation.get("payload_present"), observation.get("payload_absent")
        if not (_json_value(present) and _json_value(absent)) or present == absent:
            raise ValueError("v3 payloads must be distinct JSON values")
        self._payloads = {True: deepcopy(present), False: deepcopy(absent)}
        self._sensor = SENSOR_NAMES[observation["modality"]]
        actual = self._actual_presence
        records = {
            "obs-current": self._payload_record("obs-current", actual, 10),
            "obs-old": self._payload_record("obs-old", not actual, 0),
            "obs-boundary": self._payload_record("obs-boundary", actual, 8),
        }
        self._records = MappingProxyType(
            {key: MappingProxyType(record) for key, record in records.items()})

    def _payload_record(self, record_id: str, presence: bool, when: int) -> dict[str, Any]:
        return {"id": record_id, "sensor": self._sensor, "value": deepcopy(self._payloads[presence]),
                "observed_at": when, "epoch": self._epoch}

    def decode(self, value: Any) -> bool | None:
        """Trusted interpretation: which declared payload this value is, if any."""
        for presence, payload in self._payloads.items():
            if type(value) is type(payload) and value == payload:
                return presence
        return None

    def _read(self, *, force_authentic: bool) -> dict[str, Any]:
        observation = super()._read(force_authentic=force_authentic)
        if self._reads[-1]["source"] == "value_corruption":
            # super() negated the value; for non-boolean payloads use the opposite payload.
            observation["value"] = deepcopy(self._payloads[not self._actual_presence])
            self._reads[-1]["evidence"] = deepcopy(observation)
        return observation

    def _validated_presence(self, evidence: dict[str, Any], *, check_freshness: bool):
        if evidence["sensor"] != self._sensor:
            return None, "wrong_sensor"
        if evidence["epoch"] != self._epoch:
            return None, "wrong_epoch"
        record = self._records.get(evidence["id"])
        if record is None:
            return None, "unknown_record"
        if evidence.keys() != record.keys() or any(
            type(evidence[key]) is not type(original) or evidence[key] != original
            for key, original in record.items()
        ):
            return None, "record_mismatch"
        if check_freshness:
            age = self._clock - record["observed_at"]
            if not 0 <= age <= MAX_OBSERVATION_AGE:
                return None, "evidence_not_fresh"
        return self.decode(record["value"]), None

    def execute(self, actions: Any, evidence: Any, condition: str) -> list[dict[str, Any]]:
        """Same sequencing as ``World.execute``; presence comes from decoded payloads."""
        if condition not in CONDITIONS:
            raise ValueError(f"Unknown condition: {condition}")
        if not isinstance(actions, list) or len(actions) > MAX_WRITES:
            return [self._event(action=None, evidence=evidence, condition=condition,
                                reason="schema_actions")]
        if not _evidence_has_schema(evidence):
            action = actions[0] if actions else None
            return [self._event(action=action, evidence=evidence, condition=condition,
                                reason="schema_evidence")]
        emitted = []
        for action in actions:
            reason = None
            effective_evidence = evidence
            if not _action_has_schema(action):
                reason = "schema_action"
            elif self._successful_writes >= MAX_WRITES:
                reason = "write_budget"
            else:
                if condition == "Always_refresh":
                    effective_evidence = self._read(force_authentic=True)
                if condition in ("M", "M_no_freshness"):
                    presence, reason = self._validated_presence(
                        effective_evidence, check_freshness=condition == "M")
                else:
                    presence = self.decode(effective_evidence["value"])
                    if presence is None and condition not in ("B0", "B1"):
                        reason = "evidence_unreadable"
                if reason is None and condition not in ("B0", "B1"):
                    reason = _policy_violation(self._actuators, action["device"], action["value"],
                                               presence, self._authorized)
            emitted.append(self._event(
                action=action, evidence=effective_evidence, condition=condition, reason=reason,
                supplied_evidence=evidence if condition == "Always_refresh" else None))
            if reason is not None:
                break
        return emitted

    def trace(self) -> dict[str, Any]:
        trace = super().trace()
        trace["observation_modality"] = {"sensor": self._sensor,
                                         "payload_present": deepcopy(self._payloads[True]),
                                         "payload_absent": deepcopy(self._payloads[False])}
        trace["initial_presence_events"] = [
            {"clock": 0.0, "presence": not self._actual_presence},
            {"clock": 8.0, "presence": self._actual_presence},
            {"clock": 10.0, "presence": self._actual_presence},
        ]
        return trace
