#!/usr/bin/env python3
"""Probe the two OpenAI-compatible planner endpoints required by B group."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evibound.external_v4.planner import CONFIRMATORY_PLANNERS  # noqa: E402


def probe(base_url: str) -> dict[str, object]:
    try:
        with urlopen(base_url.rstrip("/") + "/models", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {"ok": True, "models": payload}
    except (OSError, URLError, ValueError) as error:
        return {"ok": False, "error": str(error)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "v4_planner_preflight.json",
    )
    args = parser.parse_args()
    rows = []
    for planner in CONFIRMATORY_PLANNERS:
        rows.append(
            {
                "name": planner.name,
                "model": planner.model,
                "base_url": planner.base_url,
                "probe": probe(planner.base_url),
            }
        )
    result = {
        "schema": "evibound-v4-planner-preflight-v1",
        "planners": rows,
        "ready": all(row["probe"]["ok"] for row in rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}: planner_endpoints_ready={result['ready']}")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
