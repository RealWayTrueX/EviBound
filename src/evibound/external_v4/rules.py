"""Load the authoritative v4 rule and rate tables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
RULES_PATH = ROOT / "configs" / "v4_rules.json"


def load_rules(path: Path = RULES_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "evibound-v4-rules-v2":
        raise ValueError("unsupported v4 rule schema")
    return value


def rules_by_id(path: Path = RULES_PATH) -> dict[str, dict[str, Any]]:
    return {rule["id"]: rule for rule in load_rules(path)["rules"]}


def validate_template_bindings(
    bindings: dict[str, tuple[str, ...]], *, path: Path = RULES_PATH
) -> None:
    known = rules_by_id(path)
    configured = {
        template["id"]: tuple(template["rule_ids"])
        for template in load_rules(path)["templates"]
    }
    for template, ids in bindings.items():
        if configured.get(template) != ids:
            raise ValueError(f"template {template} does not match configs/v4_rules.json")
        missing = [rule_id for rule_id in ids if rule_id not in known]
        if missing:
            raise ValueError(f"unknown rule ids: {', '.join(missing)}")


def rate_table(path: Path = RULES_PATH) -> dict[str, dict[str, Any]]:
    return {row["fact"]: row for row in load_rules(path)["rate_table"]}
