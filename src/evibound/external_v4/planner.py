"""OpenAI-compatible planner harness for the B-group arm."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class PlannerSpec:
    name: str
    model: str
    base_url: str
    api_key: str | None = None
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 320


CONFIRMATORY_PLANNERS = (
    PlannerSpec(
        name="qwen2.5-7b",
        model="Qwen2.5-7B-Instruct",
        base_url="http://127.0.0.1:8001/v1",
    ),
    PlannerSpec(
        name="qwen3-8b",
        model="Qwen3-8B",
        base_url="http://127.0.0.1:8002/v1",
    ),
)


SYSTEM_PROMPT = """You control simulated home devices.
Return one JSON object and no prose:
{"actions":[{"device":"...","command":"...","arguments":{}}],
 "cites":["record-id",...],
 "requires":{"all_of":[{"fact":"...","operator":"eq|ne|lt|le|gt|ge","value":...}]}}
Only cite record ids present in the supplied observations. State every task
precondition under requires. Do not omit a precondition to make the plan easier.
"""


def parse_plan(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    value = json.loads(candidate)
    if not isinstance(value, dict) or set(value) != {"actions", "cites", "requires"}:
        raise ValueError("planner output must contain actions, cites and requires")
    if not isinstance(value["actions"], list) or not value["actions"]:
        raise ValueError("planner actions must be a non-empty list")
    if not isinstance(value["cites"], list) or not all(
        isinstance(item, str) for item in value["cites"]
    ):
        raise ValueError("planner cites must be a list of record ids")
    if not isinstance(value["requires"], dict):
        raise ValueError("planner requires must be an object")
    return value


def chat_plan(
    planner: PlannerSpec,
    *,
    task: str,
    observations: list[dict[str, Any]],
    seed: int,
) -> dict[str, Any]:
    user = json.dumps(
        {"task": task, "observations": observations, "seed": seed},
        indent=2,
        ensure_ascii=False,
    )
    payload = {
        "model": planner.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": planner.temperature,
        "top_p": planner.top_p,
        "max_tokens": planner.max_tokens,
        "seed": seed,
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json"}
    if planner.api_key:
        headers["Authorization"] = f"Bearer {planner.api_key}"
    request = Request(
        f"{planner.base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    with urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
    text = result["choices"][0]["message"]["content"]
    return parse_plan(text)
