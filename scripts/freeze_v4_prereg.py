#!/usr/bin/env python3
"""Freeze the v4 preregistration, rules, world design and execution code."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FROZEN_PATHS = (
    "AGENTS.md",
    "docs/v4_execution_spec.md",
    "docs/v4_preregistration.md",
    "docs/design_v4_world.md",
    "configs/v4_rules.json",
    *sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "src" / "evibound" / "external_v4").glob("*.py")
    ),
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> dict[str, str]:
    missing = [relative for relative in FROZEN_PATHS if not (ROOT / relative).is_file()]
    if missing:
        raise FileNotFoundError("missing freeze inputs: " + ", ".join(missing))
    return {relative: digest(ROOT / relative) for relative in FROZEN_PATHS}


def verify_manifest(manifest: dict[str, str]) -> list[str]:
    changed = []
    for relative, expected in manifest.items():
        path = ROOT / relative
        if not path.is_file() or digest(path) != expected:
            changed.append(relative)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approve", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "v4_prereg_freeze.json",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    current = build_manifest()
    if args.check:
        record = json.loads(args.output.read_text(encoding="utf-8"))
        changed = verify_manifest(record["sha256"])
        print(
            "v4 preregistration freeze: "
            + ("ok" if not changed else "changed: " + ", ".join(changed))
        )
        return 0 if not changed else 1
    if args.output.exists():
        old = json.loads(args.output.read_text(encoding="utf-8"))
        changed = verify_manifest(old["sha256"])
        if changed:
            print(
                "refusing to overwrite a frozen protocol whose inputs changed: "
                + ", ".join(changed),
                file=sys.stderr,
            )
            return 1
    record = {
        "schema": "evibound-v4-prereg-freeze-v1",
        "approved_by": args.approve,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "sha256": current,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"froze {len(current)} files -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
