#!/usr/bin/env python3
"""Reuse cached weight blobs; fetch only public metadata at a pinned revision."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path('/mnt/HDD-8T-0/evibound_yanke')
REVISION = 'a09a35458c702b33eeacc393d103063234e8bc28'
SOURCE = Path('/mnt/HDD-8T-0/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots') / REVISION
DEST = ROOT / 'models/Qwen2.5-7B-Instruct'
DEST.mkdir(parents=True, exist_ok=True)
for p in SOURCE.glob('*.safetensors*'):
    target = DEST / p.name
    if not target.exists():
        target.symlink_to(p.resolve())
metadata = ['config.json', 'generation_config.json', 'tokenizer.json',
            'tokenizer_config.json', 'vocab.json', 'merges.txt', 'README.md', 'LICENSE']
for name in metadata:
    target = DEST / name
    if not target.exists():
        url = f'https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/resolve/{REVISION}/{name}'
        with urllib.request.urlopen(url, timeout=90) as response:
            target.write_bytes(response.read())
        print('downloaded', name, target.stat().st_size, flush=True)
files = {p.name: {'bytes': p.stat().st_size, 'resolved_path': str(p.resolve()),
                  'sha256': hashlib.sha256(p.read_bytes()).hexdigest() if p.stat().st_size < 20_000_000 else p.resolve().name}
         for p in sorted(DEST.iterdir()) if p.is_file()}
Path('artifacts/model_manifest.json').write_text(json.dumps({
    'model': 'Qwen/Qwen2.5-7B-Instruct', 'revision': REVISION, 'path': str(DEST),
    'weight_hash_note': 'Cached Hugging Face blob names; large weights not independently rehashed yet.',
    'files': files}, indent=2)+'\n')
print('READY', DEST, flush=True)
