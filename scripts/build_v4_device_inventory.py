#!/usr/bin/env python3
"""Summarize SimuHome device types and attribute paths without episode data."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simuhome-root", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "artifacts"
        / "v4_device_inventory.json",
    )
    args = parser.parse_args()
    episode_dir = args.simuhome_root / "data" / "benchmark"
    device_counts: Counter[str] = Counter()
    attributes: dict[str, set[str]] = defaultdict(set)
    query_counts: Counter[str] = Counter()
    for path in sorted(episode_dir.glob("*.json")):
        episode = json.loads(path.read_text(encoding="utf-8"))
        query_counts[str(episode.get("meta", {}).get("query_type"))] += 1
        rooms = episode.get("initial_home_config", {}).get("rooms", {})
        for room in rooms.values():
            for device in room.get("devices", []):
                device_type = device.get("device_type")
                if not isinstance(device_type, str):
                    continue
                device_counts[device_type] += 1
                for key in (device.get("attributes") or {}):
                    attributes[device_type].add(str(key))
    result = {
        "schema": "evibound-v4-device-inventory-v1",
        "simuhome_commit": __import__("subprocess")
        .check_output(
            ["git", "-C", str(args.simuhome_root), "rev-parse", "HEAD"], text=True
        )
        .strip(),
        "episode_count": sum(query_counts.values()),
        "query_types": dict(sorted(query_counts.items())),
        "device_types": dict(sorted(device_counts.items())),
        "attribute_paths": {
            device_type: sorted(paths) for device_type, paths in sorted(attributes.items())
        },
        "content_sha256": hashlib.sha256(
            json.dumps(
                {
                    "device_types": sorted(device_counts),
                    "attribute_paths": {
                        key: sorted(value) for key, value in attributes.items()
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {args.output}: {result['episode_count']} episodes, "
        f"{len(result['device_types'])} device types"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
