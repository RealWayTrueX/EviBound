#!/usr/bin/env python3
"""Run the development split before the preregistration freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evibound.external_v4.experiments import run_core  # noqa: E402
from evibound.external_v4.synthetic import generate_structures  # noqa: E402


def _compact_rows(block: dict, name: str) -> None:
    rows = block.pop("rows")
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    block[f"{name}_row_count"] = len(rows)
    block[f"{name}_rows_sha256"] = hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "v4_dev_results.json",
    )
    args = parser.parse_args()
    structures = [
        structure
        for structure in generate_structures()
        if structure.split == "dev"
    ]
    results = run_core(structures=structures)
    _compact_rows(results["c1"], "c1")
    _compact_rows(results["c2"], "c2")
    results["scope"]["status"] = "development run; not a confirmatory holdout"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.output}: dev structures={len(structures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
