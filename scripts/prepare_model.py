#!/usr/bin/env python3
"""Download a pinned model and verify every safetensors shard against Hub metadata."""
import argparse
import hashlib
import json
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

REPO_ID = 'Qwen/Qwen2.5-7B-Instruct'
REVISION = 'a09a35458c702b33eeacc393d103063234e8bc28'
DEST = Path('/mnt/HDD-8T-0/evibound_yanke/models/Qwen2.5-7B-Instruct')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('artifacts/model_manifest.json'))
    args = parser.parse_args()

    DEST.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=REPO_ID,
        revision=REVISION,
        local_dir=str(DEST),
        max_workers=4,
    )

    api = HfApi()
    info = api.model_info(REPO_ID, revision=REVISION, files_metadata=True)
    expected = {item.rfilename: item for item in info.siblings}
    files = {}
    shard_checks = []
    for relative_name, item in sorted(expected.items()):
        path = DEST / relative_name
        if not path.is_file():
            raise RuntimeError(f'missing model file: {relative_name}')
        actual_size = path.stat().st_size
        actual_sha256 = sha256(path)
        expected_size = item.size
        expected_sha256 = item.lfs.sha256 if item.lfs is not None else None
        size_ok = expected_size in (None, actual_size)
        sha256_ok = expected_sha256 in (None, actual_sha256)
        if not size_ok or not sha256_ok:
            raise RuntimeError(
                f'integrity failure: {relative_name} size={actual_size}/{expected_size} '
                f'sha256={actual_sha256}/{expected_sha256}'
            )
        record = {
            'bytes': actual_size,
            'sha256': actual_sha256,
            'hub_blob_id': item.blob_id,
            'hub_lfs_sha256': expected_sha256,
            'integrity': 'sha256_and_size_verified' if expected_sha256 else 'size_verified',
        }
        files[relative_name] = record
        if relative_name.endswith('.safetensors'):
            shard_checks.append({
                'file': relative_name,
                'bytes': actual_size,
                'sha256': actual_sha256,
                'expected_sha256': expected_sha256,
                'passed': bool(size_ok and sha256_ok),
            })

    index_path = DEST / 'model.safetensors.index.json'
    index = json.loads(index_path.read_text())
    indexed_shards = sorted(set(index['weight_map'].values()))
    actual_shards = sorted(path.name for path in DEST.glob('*.safetensors'))
    if indexed_shards != actual_shards:
        raise RuntimeError(f'index shard mismatch: indexed={indexed_shards} actual={actual_shards}')
    if not shard_checks or not all(check['passed'] for check in shard_checks):
        raise RuntimeError('one or more safetensors shards failed integrity checks')

    manifest = {
        'model': REPO_ID,
        'revision': REVISION,
        'path': str(DEST),
        'download_method': 'huggingface_hub.snapshot_download pinned revision',
        'integrity_method': (
            'Full SHA-256 and byte-size verification for every Hub file; '
            'safetensors shards additionally match Hub LFS SHA-256 metadata.'
        ),
        'safetensors_shards': shard_checks,
        'indexed_shards': indexed_shards,
        'files': files,
        'status': 'verified',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({
        'status': 'READY',
        'path': str(DEST),
        'files': len(files),
        'safetensors_shards': len(shard_checks),
        'manifest': str(args.output),
    }, sort_keys=True))


if __name__ == '__main__':
    main()
