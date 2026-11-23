#!/usr/bin/env python3
"""Reduce raw episode traces to small per-episode fingerprints, and back.

A fingerprint keeps what an episode-level comparison of two runs needs and
nothing else: the episode identity, its physical-structure cluster, a hash of
the model's first raw response, the executed writes, and the four oracle
outcomes (rescored here by the independent oracle). It holds no model text.

Why: a re-run on another machine can then be compared with the original run
without moving either set of raw traces. ``scripts/compare_runs.py`` accepts a
fingerprint file wherever it accepts raw ``.jsonl`` traces.

Usage::

    # traces -> fingerprint file
    python3 scripts/episode_fingerprints.py --study v2 \
        --inputs runs/week8_v2_main_test/seed_11.jsonl ... --output fp_v2.json
    # (an output name ending in .json.gz is written gzip-compressed)
    # the same, also printed as a short text block (gzip + base64) that can be
    # copied out of a notebook or terminal
    python3 scripts/episode_fingerprints.py --study v3 --inputs rerun.jsonl \
        --output fp_v3.json --pack
    # text block (saved in a file) -> fingerprint file
    python3 scripts/episode_fingerprints.py --unpack block.txt --output fp_v3.json
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

FORMAT = 'evibound-episode-fingerprints-1'
OUTCOMES = ('unsafe_effect', 'authorization_violation', 'goal_completion', 'safe_completion')
BEGIN, END = '-----BEGIN EVIBOUND FINGERPRINTS-----', '-----END EVIBOUND FINGERPRINTS-----'


def scorer(study):
    if study == 'v3':
        from evibound.oracle_v3 import score_episode_v3
        return score_episode_v3
    from evibound.oracle import score_episode
    return score_episode


def light_row(row, score_episode):
    """The comparison view of one raw episode."""
    metrics = score_episode(row['scenario'], row['trace'])
    raw = (row.get('proposals') or [{}])[0].get('raw')
    return {
        'task_id': row['task_id'], 'variant': row['variant'], 'condition': row['condition'],
        'seed': row['seed'],
        'physical_structure_id': (row.get('physical_structure_id')
                                  or row['scenario'].get('physical_structure_id') or row['task_id']),
        'first': None if raw is None else hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16],
        'writes': [[e['device'], e['value']] for e in row['trace']['events'] if e.get('kind') == 'write'],
        'proposals': len(row.get('proposals') or []),
        'metrics': {k: bool(metrics[k]) for k in OUTCOMES},
    }


def identity(row):
    return (row['task_id'], row['variant'], row['condition'], row['seed'])


def load_raw(paths, study):
    score_episode = scorer(study)
    rows = {}
    for path in paths:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            row = light_row(json.loads(line), score_episode)
            if identity(row) in rows:
                raise ValueError(f'duplicate episode {identity(row)} in {path}')
            rows[identity(row)] = row
    return rows


def to_document(rows, study, sources):
    """Compact, sorted, self-describing JSON document."""
    table = []
    for key in sorted(rows, key=lambda k: (k[0], k[1], k[2], str(k[3]))):
        row = rows[key]
        table.append([row['task_id'], row['variant'], row['condition'], row['seed'],
                      row['physical_structure_id'], row['first'],
                      ';'.join(f'{d}={v}' for d, v in row['writes']),
                      ''.join('1' if row['metrics'][k] else '0' for k in OUTCOMES), row['proposals']])
    return {'format': FORMAT, 'study': study, 'episodes': len(table),
            'columns': ['task_id', 'variant', 'condition', 'seed', 'physical_structure_id',
                        'first_response_sha256_16', 'executed_writes', 'outcomes', 'proposals'],
            'outcome_keys': list(OUTCOMES), 'sources': sources, 'rows': table}


def from_document(document):
    if document.get('format') != FORMAT:
        raise ValueError(f'not a fingerprint file (format {document.get("format")!r})')
    keys = document['outcome_keys']
    rows = {}
    for task, variant, condition, seed, cluster, first, writes, bits, proposals in document['rows']:
        row = {'task_id': task, 'variant': variant, 'condition': condition, 'seed': seed,
               'physical_structure_id': cluster, 'first': first,
               'writes': [w.split('=', 1) for w in writes.split(';') if w],
               'proposals': proposals, 'metrics': {k: bit == '1' for k, bit in zip(keys, bits)}}
        rows[identity(row)] = row
    if len(rows) != document['episodes']:
        raise ValueError('fingerprint file has duplicate or missing rows')
    return rows


def is_fingerprint_file(path):
    return str(path).endswith(('.json', '.json.gz'))


def read_document(path):
    data = Path(path).read_bytes()
    if str(path).endswith('.gz'):
        data = gzip.decompress(data)
    return json.loads(data.decode('utf-8'))


def load_any(paths, study):
    """Rows keyed by episode identity, from raw .jsonl traces or fingerprint .json(.gz) files."""
    rows = {}
    raw = [p for p in paths if not is_fingerprint_file(p)]
    for path in (p for p in paths if is_fingerprint_file(p)):
        document = read_document(path)
        if document.get('study') != study:
            raise ValueError(f'{path} is a {document.get("study")} fingerprint file, expected {study}')
        for key, row in from_document(document).items():
            if key in rows:
                raise ValueError(f'duplicate episode {key} in {path}')
            rows[key] = row
    for key, row in load_raw(raw, study).items():
        if key in rows:
            raise ValueError(f'duplicate episode {key}')
        rows[key] = row
    return rows


def pack(document):
    data = gzip.compress(json.dumps(document, separators=(',', ':')).encode('utf-8'), mtime=0)
    text = base64.b64encode(data).decode('ascii')
    lines = [text[i:i + 100] for i in range(0, len(text), 100)]
    return '\n'.join([BEGIN, f'study={document["study"]} episodes={document["episodes"]} '
                             f'sha256={hashlib.sha256(data).hexdigest()}', *lines, END])


def unpack(text):
    body = text.split(BEGIN, 1)[1].split(END, 1)[0].strip().splitlines()
    header, payload = body[0], ''.join(line.strip() for line in body[1:])
    data = base64.b64decode(payload)
    expected = dict(part.split('=', 1) for part in header.split())['sha256']
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('fingerprint block is damaged: checksum does not match')
    return json.loads(gzip.decompress(data).decode('utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--study', choices=['v2', 'v3'])
    parser.add_argument('--inputs', type=Path, nargs='+', help='raw episode .jsonl files')
    parser.add_argument('--unpack', type=Path, help='text file that contains a packed block')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pack', action='store_true', help='also print the packed text block')
    args = parser.parse_args(argv)
    if args.unpack:
        document = unpack(args.unpack.read_text(encoding='utf-8'))
        from_document(document)
    else:
        if not (args.study and args.inputs):
            parser.error('--study and --inputs are required unless --unpack is given')
        sources = [{'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in args.inputs]
        document = to_document(load_raw(args.inputs, args.study), args.study, sources)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = (json.dumps(document, separators=(',', ':')) + '\n').encode('utf-8')
    args.output.write_bytes(gzip.compress(text, mtime=0) if str(args.output).endswith('.gz') else text)
    print(f'{document["study"]}: {document["episodes"]} episode fingerprints -> {args.output}')
    if args.pack:
        print(pack(document))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
