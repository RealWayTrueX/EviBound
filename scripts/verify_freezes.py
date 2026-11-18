#!/usr/bin/env python3
"""Verify every protocol freeze of the project in one pass.

A freeze manifest lists files and the SHA-256 each had when the protocol was
frozen. This script checks each manifest against the working tree and, where a
sealed archive exists, against the archive, so that the two expected and
documented deviations are reported as such instead of looking like tampering
(``docs/week13_local_recheck.md``):

- v1 (September): six code files were extended for v2. They no longer match
  the working tree but must match the sealed tarball.
- Week-8 pilot: three human-review files are local-only by design and are not
  in the public repository. They must match the sealed tarball.

Exit status 0 means every frozen file matches the working tree or its sealed
archive.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZES = [
    ('v1 feasibility protocol (2026-09-22)', 'artifacts/protocol_freeze.json'),
    ('v2 pilot preregistration (Week 8)', 'artifacts/week8_protocol_freeze.json'),
    ('v2 formal test protocol (Week 8)', 'artifacts/week8_main_protocol_freeze.json'),
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archive_hashes(path):
    hashes = {}
    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            if member.isfile():
                name = member.name[2:] if member.name.startswith('./') else member.name
                hashes[name] = digest(archive.extractfile(member).read())
    return hashes


def check_manifest(label, manifest_path):
    manifest = json.loads((ROOT / manifest_path).read_text())
    files = manifest['files']
    archive = manifest.get('archive')
    sealed = archive_hashes(ROOT / archive) if archive and (ROOT / archive).exists() else {}
    tree = via_archive = failed = 0
    notes = []
    for path, expected in sorted(files.items()):
        target = ROOT / path
        if target.exists() and digest(target.read_bytes()) == expected:
            tree += 1
            continue
        match = [name for name, value in sealed.items() if value == expected
                 and (name == path or name.endswith('/' + path))]
        if match:
            via_archive += 1
            notes.append(f'{path}: {"changed since the freeze" if target.exists() else "local-only"}, '
                         f'matches the sealed archive')
        else:
            failed += 1
            notes.append(f'{path}: MISMATCH (not in the working tree or the sealed archive)')
    ok = failed == 0
    print(f'[{"ok" if ok else "FAIL"}] {label}: {len(files)} files, {tree} match the working tree, '
          f'{via_archive} match the sealed archive only, {failed} mismatches')
    for note in notes:
        print(f'       {note}')
    return ok


def main():
    results = [check_manifest(label, path) for label, path in FREEZES]
    v3 = subprocess.run([sys.executable, str(ROOT / 'scripts/freeze_v3_prereg.py'), '--verify'],
                        capture_output=True, text=True, cwd=ROOT)
    line = (v3.stdout.strip().splitlines() or v3.stderr.strip().splitlines() or ['no output'])[-1]
    print(f'[{"ok" if v3.returncode == 0 else "FAIL"}] v3 preregistration (Week 11): {line}')
    results.append(v3.returncode == 0)
    return 0 if all(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
