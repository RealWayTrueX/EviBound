#!/usr/bin/env python3
"""Run the frozen v4 counterfactual and synthetic pressure-test core."""

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


def _freeze_errors() -> list[str]:
    freeze_path = ROOT / "artifacts" / "v4_prereg_freeze.json"
    if not freeze_path.is_file():
        return ["missing artifacts/v4_prereg_freeze.json"]
    manifest = json.loads(freeze_path.read_text(encoding="utf-8"))["sha256"]
    changed = []
    for relative, expected in manifest.items():
        path = ROOT / relative
        if not path.is_file():
            changed.append(relative)
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            changed.append(relative)
    return changed


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
        default=ROOT / "artifacts" / "v4_core_results.json",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    changed = _freeze_errors()
    if changed:
        print("refusing holdout: freeze mismatch: " + ", ".join(changed), file=sys.stderr)
        return 1
    structures = [
        structure
        for structure in generate_structures()
        if structure.split == "holdout"
    ]
    results = run_core(structures=structures)
    _compact_rows(results["c1"], "c1")
    _compact_rows(results["c2"], "c2")
    failed = [name for name, passed in results["acceptance"].items() if not passed]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {args.output}: {results['acceptance']['a_scenario_count']} "
        f"holdout scenarios, acceptance={'pass' if not failed else 'fail'}"
    )
    if failed:
        print("failed acceptance checks: " + ", ".join(failed))
        return 1 if args.check else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
