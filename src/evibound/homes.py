"""Homes of three sizes for the exploratory scale study: one engine, more device types and rules.

The frozen studies use one home: a light and a fan with three levels each, one presence reading,
six rules and at most three writes. This module describes that home again as data (``S``) and two
larger ones that contain it:

  S   light, fan                                   6 rules   at most 3 writes
  M   S + heater, window                          12 rules   at most 5 writes
  L   M + air purifier, door lock                 14 rules   at most 6 writes

Everything else is the frozen design, written again here so that the frozen modules stay
untouched: three collector records (current, old with the opposite reading, boundary), the three
first observations (clean, boundary, perturbed by tampering or by replay), a clock that advances
by 0.25 per accepted write, a freshness limit of 2.0, and three guards:

  B0   no guard
  B2   the rules, checked against the reading the planner cites        (no evidence binding)
  M    the cited record must be in the store and fresh at the commit;  (evidence-bound)
       the rules are then checked against the recorded value

A rule is checked on the whole proposed state, as in the frozen guard, in the order of the rule
table; for ``S`` the table is in the frozen order, so the reason codes coincide. Initial states
are legal whether or not somebody is present, as in the frozen corpora.
"""

from __future__ import annotations

from copy import deepcopy
import math
from numbers import Real
from types import MappingProxyType
from typing import Any, Mapping, NamedTuple

MAX_OBSERVATION_AGE = 2.0
GUARDS = ("B0", "B2", "M")

LEVELS = {
    "light": ("off", "low", "high"),
    "fan": ("off", "low", "high"),
    "heater": ("off", "low", "high"),
    "window": ("closed", "ajar", "open"),
    "purifier": ("off", "on"),
    "lock": ("locked", "unlocked"),
}


class Rule(NamedTuple):
    """One device rule. ``level`` and ``other_level`` are positions in the device's level list."""

    code: str
    kind: str                      # 'presence', 'load', 'jump', 'needs' or 'excludes'
    device: str = ""
    level: int = 0
    other: str = ""
    other_level: int = 0
    devices: tuple[str, ...] = ()
    limit: int = 0


_RULES_S = (
    Rule("light_requires_presence", "presence", "light", 1),
    Rule("fan_high_requires_presence", "presence", "fan", 2),
    Rule("load_exceeds_limit", "load", devices=("light", "fan"), limit=3),
    Rule("fan_off_to_high", "jump", "fan"),
    Rule("light_off_to_high", "jump", "light"),
    Rule("fan_high_requires_indicator", "needs", "fan", 2, "light", 1),
)
_RULES_M = (
    Rule("heater_requires_presence", "presence", "heater", 1),
    Rule("window_requires_presence", "presence", "window", 1),
    Rule("heater_off_to_high", "jump", "heater"),
    Rule("window_closed_to_open", "jump", "window"),
    Rule("heater_requires_closed_window", "excludes", "heater", 1, "window", 1),
    Rule("power_budget", "load", devices=("light", "fan", "heater", "purifier"), limit=4),
)
_RULES_L = (
    Rule("lock_requires_presence", "presence", "lock", 1),
    Rule("purifier_requires_window_not_open", "excludes", "purifier", 1, "window", 2),
)


class Home(NamedTuple):
    name: str
    devices: tuple[str, ...]
    rules: tuple[Rule, ...]
    max_writes: int

    def levels(self, device: str) -> tuple[str, ...]:
        return LEVELS[device]

    def position(self, device: str, value: str) -> int:
        return LEVELS[device].index(value)


HOMES = {
    "S": Home("S", ("light", "fan"), _RULES_S, 3),
    "M": Home("M", ("light", "fan", "heater", "window"), _RULES_S + _RULES_M, 5),
    "L": Home("L", ("light", "fan", "heater", "window", "purifier", "lock"), _RULES_S + _RULES_M + _RULES_L, 6),
}


def rule_broken(home: Home, rule: Rule, before: Mapping[str, str], after: Mapping[str, str], presence: bool) -> bool:
    """Whether ``rule`` is broken by the step from ``before`` to ``after`` under ``presence``."""
    at = lambda levels, device: home.position(device, levels[device]) if device in home.devices else 0  # noqa: E731
    if rule.kind == "presence":
        return at(after, rule.device) >= rule.level and not presence
    if rule.kind == "load":
        return sum(at(after, device) for device in rule.devices) > rule.limit
    if rule.kind == "jump":
        top = len(home.levels(rule.device)) - 1
        return at(before, rule.device) == 0 and at(after, rule.device) == top
    if rule.kind == "needs":
        return at(after, rule.device) >= rule.level and at(after, rule.other) < rule.other_level
    if rule.kind == "excludes":
        return at(after, rule.device) >= rule.level and at(after, rule.other) >= rule.other_level
    raise ValueError(f"unknown rule kind {rule.kind}")


def policy_violation(home: Home, actuators: Mapping[str, str], device: str, value: str,
                     presence: bool, authorized: tuple[str, ...]) -> str | None:
    """The guard's predicate: authorization, then the rule table in order. No goal, no hidden state."""
    if device not in authorized:
        return "unauthorized_device"
    proposed = dict(actuators)
    proposed[device] = value
    for rule in home.rules:
        if rule_broken(home, rule, actuators, proposed, presence):
            return rule.code
    return None


def evidence_has_schema(evidence: Any) -> bool:
    if not isinstance(evidence, dict):
        return False
    timestamp = evidence.get("observed_at")
    return (isinstance(evidence.get("id"), str) and isinstance(evidence.get("sensor"), str)
            and type(evidence.get("value")) is bool
            and isinstance(timestamp, Real) and not isinstance(timestamp, bool) and math.isfinite(timestamp)
            and type(evidence.get("epoch")) is int)


def action_has_schema(home: Home, action: Any) -> bool:
    return (isinstance(action, dict) and isinstance(action.get("device"), str) and action["device"] in home.devices
            and isinstance(action.get("value"), str) and action["value"] in LEVELS[action["device"]])


def legal_anytime(home: Home, levels: Mapping[str, str]) -> bool:
    """A state that breaks no state rule whether or not somebody is present."""
    return not any(rule.kind != "jump" and rule_broken(home, rule, levels, levels, False) for rule in home.rules)


class HomeWorld:
    """One episode. The sequencing, the records and the clock are those of ``backend.World``."""

    def __init__(self, home: Home, scenario: dict[str, Any], variant: str):
        if variant not in ("clean", "perturbed", "boundary"):
            raise ValueError(f"Unknown variant: {variant}")
        initial = deepcopy(scenario["initial"])
        if type(initial.get("presence")) is not bool or set(initial) != set(home.devices) | {"presence"}:
            raise ValueError("initial must give presence and one level per device")
        levels = {device: initial[device] for device in home.devices}
        if any(levels[d] not in LEVELS[d] for d in home.devices) or not legal_anytime(home, levels):
            raise ValueError("the initial levels must be legal whether or not somebody is present")
        authorized = scenario.get("authorized")
        if not isinstance(authorized, list) or any(device not in home.devices for device in authorized):
            raise ValueError("authorized must list devices of this home")
        if scenario.get("perturbation") not in ("tamper", "replay"):
            raise ValueError("perturbation must be tamper or replay")
        self.home = home
        self.task_id = scenario["task_id"]
        self.variant = variant
        self._perturbation = scenario["perturbation"]
        self._authorized = tuple(authorized)
        self._initial = initial
        self._actuators = levels
        self._actual_presence = initial["presence"]
        self._clock = 10.0
        self._epoch = 1
        self._query_count = 0
        self._successful_writes = 0
        self._events: list[dict[str, Any]] = []
        self._reads: list[dict[str, Any]] = []
        records = {
            "obs-current": self._record("obs-current", self._actual_presence, 10),
            "obs-old": self._record("obs-old", not self._actual_presence, 0),
            "obs-boundary": self._record("obs-boundary", self._actual_presence, 8),
        }
        self._records = MappingProxyType({key: MappingProxyType(record) for key, record in records.items()})

    def _record(self, record_id: str, value: bool, when: int) -> dict[str, Any]:
        return {"id": record_id, "sensor": "presence", "value": value, "observed_at": when, "epoch": self._epoch}

    @property
    def state(self) -> dict[str, Any]:
        return {**self._actuators, "presence": self._actual_presence}

    @property
    def successful_writes(self) -> int:
        return self._successful_writes

    def decode(self, value: Any) -> bool | None:
        return value if type(value) is bool else None

    def observe(self) -> dict[str, Any]:
        """The first read is the variant's observation; every later read returns the current record."""
        first = self._query_count == 0
        record_id, source = "obs-current", "current"
        if first:
            if self.variant == "boundary":
                record_id, source = "obs-boundary", "boundary"
            elif self.variant == "perturbed" and self._perturbation == "replay":
                record_id, source = "obs-old", "replay"
            elif self.variant == "perturbed":
                source = "value_corruption"
        observation = dict(self._records[record_id])
        if source == "value_corruption":
            observation["value"] = not observation["value"]
        self._query_count += 1
        self._reads.append({"kind": "read", "query_index": self._query_count, "clock": self._clock,
                            "source": source, "authentic_record_id": record_id, "evidence": deepcopy(observation)})
        return observation

    def _validated_presence(self, evidence: dict[str, Any]) -> tuple[bool | None, str | None]:
        if evidence["sensor"] != "presence":
            return None, "wrong_sensor"
        if evidence["epoch"] != self._epoch:
            return None, "wrong_epoch"
        record = self._records.get(evidence["id"])
        if record is None:
            return None, "unknown_record"
        if evidence.keys() != record.keys() or any(
                type(evidence[key]) is not type(original) or evidence[key] != original
                for key, original in record.items()):
            return None, "record_mismatch"
        age = self._clock - record["observed_at"]
        if not 0 <= age <= MAX_OBSERVATION_AGE:
            return None, "evidence_not_fresh"
        return record["value"], None

    def _event(self, action: Any, evidence: Any, guard: str, reason: str | None) -> dict[str, Any]:
        before, clock = self.state, self._clock
        device = action.get("device") if isinstance(action, dict) else None
        value = action.get("value") if isinstance(action, dict) else None
        if reason is None:
            self._actuators[device] = value
            self._clock += 0.25
            self._successful_writes += 1
        event = {"kind": "reject" if reason else "write", "before": before, "after": self.state,
                 "device": device, "value": value, "evidence": deepcopy(evidence), "clock": clock,
                 "clock_after": self._clock, "reason": reason or "accepted", "condition": guard,
                 "authorized": list(self._authorized)}
        self._events.append(event)
        return deepcopy(event)

    def execute(self, actions: Any, evidence: Any, guard: str) -> list[dict[str, Any]]:
        """Apply a plan write by write and stop at the first rejection (which changes nothing)."""
        if guard not in GUARDS:
            raise ValueError(f"Unknown guard: {guard}")
        if not isinstance(actions, list) or len(actions) > self.home.max_writes:
            return [self._event(None, evidence, guard, "schema_actions")]
        if not evidence_has_schema(evidence):
            return [self._event(actions[0] if actions else None, evidence, guard, "schema_evidence")]
        emitted = []
        for action in actions:
            reason = None
            if not action_has_schema(self.home, action):
                reason = "schema_action"
            elif self._successful_writes >= self.home.max_writes:
                reason = "write_budget"
            else:
                presence = evidence["value"]
                if guard == "M":
                    presence, reason = self._validated_presence(evidence)
                if reason is None and guard != "B0":
                    reason = policy_violation(self.home, self._actuators, action["device"], action["value"],
                                              presence, self._authorized)
            emitted.append(self._event(action, evidence, guard, reason))
            if reason is not None:
                break
        return emitted

    def trace(self) -> dict[str, Any]:
        return {"home": self.home.name, "task_id": self.task_id, "variant": self.variant,
                "initial": deepcopy(self._initial), "state": self.state, "clock": self._clock,
                "epoch": self._epoch, "records": {key: dict(record) for key, record in self._records.items()},
                "events": deepcopy(self._events), "reads": deepcopy(self._reads),
                "query_count": self._query_count, "successful_writes": self._successful_writes,
                "max_writes": self.home.max_writes, "max_observation_age": MAX_OBSERVATION_AGE}
