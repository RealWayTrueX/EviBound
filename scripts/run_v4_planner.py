#!/usr/bin/env python3
"""Probe or run the two B-group OpenAI-compatible planners."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evibound.external_v4.planner import CONFIRMATORY_PLANNERS  # noqa: E402
from evibound.external_v4.planner_b import (  # noqa: E402
    run_planner_case,
    summarize_planner_rows,
)
from evibound.external_v4.synthetic import generate_structures  # noqa: E402


def probe(base_url: str, api_key: str | None) -> dict[str, object]:
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        request = Request(
            base_url.rstrip("/") + "/models",
            headers=headers,
        )
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {"ok": True, "models": payload}
    except (OSError, URLError, ValueError) as error:
        return {"ok": False, "error": str(error)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "v4_planner_results.json",
    )
    parser.add_argument(
        "--raw-output",
        type=Path,
        default=ROOT / "artifacts" / "v4_planner_rows.jsonl",
    )
    args = parser.parse_args()
    token = os.getenv("EVIBOUND_API_TOKEN")
    planners = [
        replace(planner, api_key=token) if token else planner
        for planner in CONFIRMATORY_PLANNERS
    ]
    probes = {
        planner.name: probe(planner.base_url, planner.api_key)
        for planner in planners
    }
    result: dict[str, object] = {
        "schema": "evibound-v4-planner-preflight-v2",
        "seed": args.seed,
        "limit": args.limit,
        "planners": [
            {
                "name": planner.name,
                "model": planner.model,
                "base_url": planner.base_url,
                "probe": probes[planner.name],
            }
            for planner in planners
        ],
        "ready": all(value["ok"] for value in probes.values()),
    }
    if args.run and result["ready"]:
        cases = [
            structure
            for structure in generate_structures()
            if structure.split == "holdout"
        ][: args.limit]
        rows: list[dict[str, object]] = []
        attacks = ("context_replay", "context_forgery", "transport_freeze")
        for planner in planners:
            for index, case in enumerate(cases):
                rows.extend(
                    run_planner_case(
                        planner=planner,
                        case=case,
                        attack="clean",
                        seed=args.seed,
                    )
                )
                rows.extend(
                    run_planner_case(
                        planner=planner,
                        case=case,
                        attack=attacks[index % len(attacks)],
                        seed=args.seed,
                    )
                )
        result["rows"] = len(rows)
        result["summary"] = summarize_planner_rows(rows)
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)
        args.raw_output.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {args.output}: ready={result['ready']}"
        + (f" rows={result['rows']}" if "rows" in result else "")
    )
    return 0 if result["ready"] or not args.run else 1


if __name__ == "__main__":
    raise SystemExit(main())
