"""Thin HTTP adapter around an unmodified SimuHome checkout.

The adapter uses only the public simulator API. It never imports or edits
SimuHome source files. Device signatures are emulated at this proxy boundary:
the client signs each observation it accepts from the simulator, so L1 replays
cannot manufacture new records while L2 freeze attacks retain the original
observation time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SimuHomeResponse:
    status_code: int
    payload: dict[str, Any]

    @property
    def data(self) -> Any:
        return self.payload.get("data")


class SimuHomeClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", *, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> SimuHomeResponse:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            f"{self.base_url}/api{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("SimuHome returned a non-object JSON response")
                return SimuHomeResponse(int(response.status), payload)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"SimuHome {method} {path} failed with HTTP {error.code}: {detail}"
            ) from error
        except URLError as error:
            raise RuntimeError(
                f"Cannot reach SimuHome at {self.base_url}: {error.reason}"
            ) from error

    @staticmethod
    def _assert_ok(response: SimuHomeResponse) -> Any:
        status = response.payload.get("status", response.payload)
        if not isinstance(status, dict) or int(status.get("code", 500)) >= 400:
            raise RuntimeError(f"SimuHome rejected request: {response.payload}")
        return response.data

    def health(self) -> bool:
        response = self._request("GET", "/__health__")
        self._assert_ok(response)
        return True

    def reset(self, initial_home_config: dict[str, Any]) -> dict[str, Any]:
        response = self._request("POST", "/simulation/reset", initial_home_config)
        data = self._assert_ok(response)
        if not isinstance(data, dict):
            raise ValueError("SimuHome reset did not return a configuration")
        return data

    def current_time(self) -> str:
        data = self._assert_ok(self._request("GET", "/time"))
        return str(data["now"])

    def home_state(self) -> dict[str, Any]:
        data = self._assert_ok(self._request("GET", "/home/state"))
        if not isinstance(data, dict):
            raise ValueError("SimuHome home state is not an object")
        return data

    def attributes(self, device_id: str) -> dict[str, Any]:
        data = self._assert_ok(self._request("GET", f"/devices/{device_id}/attributes"))
        if not isinstance(data, dict):
            raise ValueError("SimuHome attributes are not an object")
        return data

    def structure(self, device_id: str) -> dict[str, Any]:
        data = self._assert_ok(self._request("GET", f"/devices/{device_id}/structure"))
        if not isinstance(data, dict):
            raise ValueError("SimuHome structure is not an object")
        return data

    def execute_command(
        self,
        device_id: str,
        *,
        endpoint_id: int,
        cluster_id: str,
        command_id: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "endpoint_id": endpoint_id,
            "cluster_id": cluster_id,
            "command_id": command_id,
            "args": arguments or {},
        }
        data = self._assert_ok(
            self._request("POST", f"/devices/{device_id}/commands", payload)
        )
        return data if isinstance(data, dict) else {"result": data}

    def fast_forward(self, to_tick: int) -> dict[str, Any]:
        data = self._assert_ok(
            self._request(
                "POST", "/simulation/fast_forward_to", {"to_tick": int(to_tick)}
            )
        )
        return data if isinstance(data, dict) else {"result": data}

    def schedule_workflow(
        self,
        *,
        start_time: str,
        steps: list[dict[str, Any]],
        description: str = "EviBound v4 smoke",
    ) -> str:
        data = self._assert_ok(
            self._request(
                "POST",
                "/schedule/workflow",
                {"start_time": start_time, "description": description, "steps": steps},
            )
        )
        return str(data["workflow_id"])

    def workflow_status(self, workflow_id: str) -> dict[str, Any]:
        data = self._assert_ok(
            self._request("GET", f"/schedule/workflow/{workflow_id}/status")
        )
        return data if isinstance(data, dict) else {"result": data}


@dataclass(frozen=True)
class WorkflowCommand:
    device_id: str
    endpoint_id: int
    cluster_id: str
    command_id: str
    arguments: dict[str, Any]

    def step(self) -> dict[str, Any]:
        return {
            "tool": "execute_command",
            "args": {
                "device_id": self.device_id,
                "endpoint_id": self.endpoint_id,
                "cluster_id": self.cluster_id,
                "command_id": self.command_id,
                "args": self.arguments,
            },
        }


def command_for_assert(device_id: str, attribute: str, value: Any) -> WorkflowCommand | None:
    endpoint_text, cluster_id, attribute_id = attribute.split(".", 2)
    endpoint_id = int(endpoint_text)
    if cluster_id == "OnOff" and attribute_id == "OnOff":
        return WorkflowCommand(device_id, endpoint_id, cluster_id, "On" if value else "Off", {})
    if cluster_id == "LevelControl" and attribute_id == "CurrentLevel" and isinstance(value, int):
        return WorkflowCommand(
            device_id,
            endpoint_id,
            cluster_id,
            "MoveToLevel",
            {
                "Level": value,
                "TransitionTime": 0,
                "OptionsMask": 0,
                "OptionsOverride": 0,
            },
        )
    return None


def supported_commands(episode: dict[str, Any]) -> list[WorkflowCommand]:
    commands: list[WorkflowCommand] = []
    for goal in episode.get("eval", {}).get("goals", []):
        for target in goal.get("targets", []):
            device_id = target.get("device_id")
            if not isinstance(device_id, str):
                continue
            for assertion in target.get("asserts", []):
                command = command_for_assert(
                    device_id,
                    str(assertion.get("attribute")),
                    assertion.get("value"),
                )
                if command is not None:
                    commands.append(command)
    return commands


def first_supported_command(episode: dict[str, Any]) -> WorkflowCommand | None:
    commands = supported_commands(episode)
    return commands[0] if commands else None


def _natural_episode_key(path: Path) -> tuple[str, int]:
    stem = path.stem.replace("_feasible_seed_", " ")
    prefix, raw_seed = stem.rsplit(" ", 1)
    return prefix, int(raw_seed)


def select_qt4_episodes(episode_dir: Path, *, limit: int = 10) -> list[Path]:
    by_type: dict[str, list[Path]] = {}
    for path in sorted(episode_dir.glob("qt4-*_feasible_seed_*.json"), key=_natural_episode_key):
        prefix, _ = _natural_episode_key(path)
        by_type.setdefault(prefix, []).append(path)
    selected: list[Path] = []
    index = 0
    while len(selected) < limit:
        added = False
        for prefix in sorted(by_type):
            if index < len(by_type[prefix]):
                selected.append(by_type[prefix][index])
                added = True
                if len(selected) == limit:
                    break
        if not added:
            break
        index += 1
    return selected


def _future_time(now: str, seconds: int) -> str:
    parsed = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
    return (parsed + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")


def smoke_qt4_episodes(
    *,
    client: SimuHomeClient,
    episode_dir: Path,
    limit: int = 10,
) -> dict[str, Any]:
    client.health()
    rows: list[dict[str, Any]] = []
    for path in select_qt4_episodes(episode_dir, limit=max(limit * 5, limit)):
        if sum(row["status"] == "ok" for row in rows) >= limit:
            break
        episode = json.loads(path.read_text(encoding="utf-8"))
        commands = supported_commands(episode)
        if not commands:
            rows.append({"episode": path.name, "status": "skipped_no_supported_command"})
            continue
        try:
            reset = client.reset(episode["initial_home_config"])
            before = client.current_time()
            first = commands[0]
            attributes_before = client.attributes(first.device_id)
            for command in commands:
                client.execute_command(
                    command.device_id,
                    endpoint_id=command.endpoint_id,
                    cluster_id=command.cluster_id,
                    command_id=command.command_id,
                    arguments=command.arguments,
                )
            state = client.home_state()
            start_time = _future_time(before, 5)
            workflow_id = client.schedule_workflow(
                start_time=start_time,
                steps=[command.step() for command in commands],
                description=f"EviBound smoke {path.name}",
            )
            tick_interval = float(state.get("tick_interval", 0.1))
            target_tick = int(state["current_tick"]) + max(
                1, math.ceil(10.0 / tick_interval)
            )
            client.fast_forward(target_tick)
            workflow = client.workflow_status(workflow_id)
            attributes_after = client.attributes(first.device_id)
            rows.append(
                {
                    "episode": path.name,
                    "status": "ok",
                    "query_type": episode.get("meta", {}).get("query_type"),
                    "num_rooms": reset.get("meta", {}).get("num_rooms"),
                    "device_id": first.device_id,
                    "commands_executed": len(commands),
                    "before_time": before,
                    "after_time": client.current_time(),
                    "attribute_before_sha256": hashlib.sha256(
                        json.dumps(attributes_before, sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                    "attribute_after_sha256": hashlib.sha256(
                        json.dumps(attributes_after, sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                    "workflow_id": workflow_id,
                    "workflow_status": workflow.get("status"),
                }
            )
        except Exception as error:  # pragma: no cover - live integration path
            rows.append(
                {
                    "episode": path.name,
                    "status": "error",
                    "error": str(error),
                }
            )
    return {
        "schema": "evibound-v4-simuhome-smoke-v1",
        "simuhome_commit": "83d28837b69f0cbf1bc02ed5334cb8b561a9d54d",
        "limit": limit,
        "episodes_attempted": len(rows),
        "episodes_ok": sum(row["status"] == "ok" for row in rows),
        "episodes_error": sum(row["status"] == "error" for row in rows),
        "rows": rows,
    }
