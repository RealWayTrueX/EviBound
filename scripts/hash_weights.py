#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import time

manifest=Path('artifacts/model_manifest.json')
obj=json.loads(manifest.read_text())
checks={}
for name,record in obj['files'].items():
    if not name.endswith('.safetensors'):continue
    h=hashlib.sha256(); start=time.perf_counter()
    with Path(record['resolved_path']).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    digest=h.hexdigest()
    checks[name]={'sha256':digest,'matches_hf_blob_name':digest==Path(record['resolved_path']).name,
                  'seconds':time.perf_counter()-start}
    print(name,checks[name],flush=True)
Path('artifacts/weight_integrity.json').write_text(json.dumps(checks,indent=2)+'\n')
assert all(r['matches_hf_blob_name'] for r in checks.values())
