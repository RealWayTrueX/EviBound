#!/usr/bin/env python3
"""Run the live SimuHome counterfactual A group."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evibound.external_v4.simuhome_adapter import SimuHomeClient  # noqa: E402
from evibound.external_v4.simuhome_experiment import run_simuhome_a  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simuhome-root", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "v4_simuhome_a.json",
    )
    args = parser.parse_args()
    result = run_simuhome_a(
        client=SimuHomeClient(args.base_url),
        episode_dir=args.simuhome_root / "data" / "benchmark",
        limit=args.limit,
    )
    result["simuhome_commit"] = (
        __import__("subprocess")
        .check_output(
            ["git", "-C", str(args.simuhome_root), "rev-parse", "HEAD"], text=True
        )
        .strip()
    )
    result["benchmark_digest"] = hashlib.sha256(
        json.dumps(
            sorted(path.name for path in (args.simuhome_root / "data" / "benchmark").glob("*.json"))
        ).encode("utf-8")
    ).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result["rows"].clear()
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {args.output}: episodes={result['episodes_used']} "
        f"rows_sha256={result['rows_sha256']}"
    )
    return 0 if result["episodes_used"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
