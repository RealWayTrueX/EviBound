#!/usr/bin/env python3
"""Run the G0 smoke test against an already-running, unmodified SimuHome."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evibound.external_v4.simuhome_adapter import SimuHomeClient, smoke_qt4_episodes  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simuhome-root", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "v4_simuhome_smoke.json",
    )
    args = parser.parse_args()

    commit = subprocess.check_output(
        ["git", "-C", str(args.simuhome_root), "rev-parse", "HEAD"], text=True
    ).strip()
    client = SimuHomeClient(args.base_url)
    result = smoke_qt4_episodes(
        client=client,
        episode_dir=args.simuhome_root / "data" / "benchmark",
        limit=args.limit,
    )
    result["simuhome_commit"] = commit
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output}: ok={result['episodes_ok']} "
        f"error={result['episodes_error']}"
    )
    return 0 if result["episodes_ok"] == min(args.limit, 10) else 1


if __name__ == "__main__":
    raise SystemExit(main())
