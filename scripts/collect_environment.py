#!/usr/bin/env python3
"""Collect reproducibility facts without loading the experimental model."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone


PACKAGE_NAMES = (
    "torch",
    "transformers",
    "tokenizers",
    "huggingface-hub",
    "accelerate",
    "numpy",
    "matplotlib",
    "safetensors",
    "pandas",
)


def run(command: list[str]) -> dict:
    executable = shutil.which(command[0])
    if executable is None:
        return {"available": False, "command": command}
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    return {
        "available": True,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def read_os_release() -> dict:
    path = Path("/etc/os-release")
    values = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    return values


def package_versions(executable: str) -> dict:
    code = (
        "import importlib.metadata as m, json; "
        f"names={PACKAGE_NAMES!r}; "
        "print(json.dumps({n: (m.version(n) if n in {d.metadata['Name'].lower() for d in m.distributions() if d.metadata.get('Name')} else None) for n in names}, sort_keys=True))"
    )
    result = run([executable, "-c", code])
    if result["returncode"] != 0:
        return {"error": result["stderr"]}
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"error": "invalid package metadata response"}


def torch_facts(executable: str) -> dict:
    code = (
        "import json, torch; "
        "print(json.dumps({'torch': torch.__version__, "
        "'cuda_compiled': torch.version.cuda, "
        "'cudnn': torch.backends.cudnn.version(), "
        "'cuda_available': torch.cuda.is_available(), "
        "'device_count': torch.cuda.device_count(), "
        "'default_dtype': str(torch.get_default_dtype()), "
        "'float32_matmul_precision': torch.get_float32_matmul_precision(), "
        "'cuda_device_names': [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}, sort_keys=True))"
    )
    result = run([executable, "-c", code])
    if result["returncode"] != 0:
        return {"error": result["stderr"]}
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"error": "invalid torch metadata response"}


def gpu_facts() -> dict:
    result = run([
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,driver_version,pci.bus_id",
        "--format=csv,noheader,nounits",
    ])
    devices = []
    if result["returncode"] == 0:
        for line in result["stdout"].splitlines():
            fields = [field.strip() for field in line.split(",")]
            if len(fields) == 5:
                devices.append({
                    "index": int(fields[0]),
                    "name": fields[1],
                    "memory_total_mib": int(fields[2]),
                    "driver_version": fields[3],
                    "pci_bus_id": fields[4],
                })
    return {"devices": devices, "raw": result}


def python_facts(executable: str) -> dict:
    resolved = str(Path(executable).resolve())
    return {
        "executable": executable,
        "resolved_executable": resolved,
        "version": run([executable, "--version"]),
        "packages": package_versions(executable),
        "torch": torch_facts(executable),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/environment_v2.json"),
    )
    args = parser.parse_args()
    runtime_python = "/mnt/HDD-8T-0/evibound_yanke/envs/runtime/bin/python"
    cpu = run(["lscpu"])
    uname = run(["uname", "-a"])
    manifest = {
        "schema_version": 2,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "collection_policy": "No model weights loaded and no model-in-the-loop episodes executed.",
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "hostname": platform.node(),
            "os_release": read_os_release(),
            "uname": uname,
            "cpu": cpu,
            "logical_cpu_count": os.cpu_count(),
            "memory": run(["free", "-b"]),
        },
        "gpu": gpu_facts(),
        "cuda_tools": {
            "nvidia_smi": run(["nvidia-smi", "--version"]),
            "nvcc": run(["nvcc", "--version"]),
        },
        "python": {
            "base": python_facts(sys.executable),
            "runtime": python_facts(runtime_python),
        },
        "planned_inference": {
            "model": "Qwen2.5-7B-Instruct",
            "revision": "a09a35458c702b33eeacc393d103063234e8bc28",
            "precision": "bfloat16",
            "observed_in_this_collection": False,
            "source": "docs/implementation_contract.md",
        },
        "storage": {
            "project_root": str(Path.cwd().resolve()),
            "large_asset_root": "/mnt/HDD-8T-0/evibound_yanke",
            "large_asset_root_exists": Path("/mnt/HDD-8T-0/evibound_yanke").exists(),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
