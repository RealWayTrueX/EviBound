#!/usr/bin/env python3
"""Exploratory second-model arm of v3.1: two records that hold no raw trace.

  --files MODEL_DIR --output OUT.json
      name, size and sha256 of the model files (weights, configuration, tokenizer), so that the
      exact model can be named afterwards. Hidden files and folders are not read.

  --plumbing EPISODES... --output OUT.json
      Does the model answer in the form the frozen parser expects? Counts over the first proposals
      (one per task, variant and seed; the conditions share it) and over the recovery answers:
      how many could not be parsed, how many carry reasoning text, how many ran into the token
      limit. The record says ``ok`` when no answer carries reasoning text and at most 20 percent
      of the first proposals fail to parse. The rule was fixed before the first run and looks at
      the form of the answers only, never at an outcome (docs/v3_1_second_model.md).
"""
import argparse
import hashlib
import json
from pathlib import Path

MODEL_FILES = ('.json', '.safetensors', '.txt', '.jinja', '.md', '.model')
MAX_PARSE_FAILURES = 0.20
TOKEN_LIMIT = 224


def file_record(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def model_files(folder):
    folder = Path(folder)
    files = sorted(p for p in folder.iterdir()
                   if p.is_file() and not p.name.startswith('.') and (p.suffix in MODEL_FILES or p.name == 'LICENSE'))
    record = {'folder': str(folder), 'files': {p.name: file_record(p) for p in files}}
    config = folder / 'config.json'
    if config.exists():
        data = json.loads(config.read_text())
        record['config'] = {key: data.get(key) for key in
                            ('model_type', 'architectures', 'hidden_size', 'num_hidden_layers', 'torch_dtype',
                             'vocab_size', 'transformers_version')}
    return record


def tally(answers, token_limit=TOKEN_LIMIT):
    answers = list(answers)
    n = len(answers)
    count = lambda test: sum(1 for a in answers if test(a))  # noqa: E731
    return {
        'answers': n,
        'not_parsed': count(lambda a: a.get('parsed') is None),
        'with_reasoning_text': count(lambda a: '<think>' in a.get('raw', '') or '</think>' in a.get('raw', '')),
        'at_token_limit': count(lambda a: a.get('output_tokens', 0) >= token_limit),
        'mean_output_tokens': round(sum(a.get('output_tokens', 0) for a in answers) / n, 1) if n else None,
    }


def plumbing(paths, token_limit=TOKEN_LIMIT):
    first, recovery, by_condition = {}, [], {}
    for path in paths:
        with open(path) as stream:
            for line in stream:
                episode = json.loads(line)
                proposals = episode['proposals']
                first[(episode.get('home'), episode['task_id'], episode['variant'], episode['seed'])] = proposals[0]
                recovery.extend(proposals[1:])
                by_condition.setdefault(episode['condition'], []).extend(proposals[1:])
    record = {'first_proposals': tally(first.values(), token_limit), 'recovery_answers': tally(recovery, token_limit),
              'recovery_answers_by_condition': {c: tally(v, token_limit) for c, v in sorted(by_condition.items())},
              'token_limit': token_limit}
    head = record['first_proposals']
    reasoning = head['with_reasoning_text'] + record['recovery_answers']['with_reasoning_text']
    share = head['not_parsed'] / head['answers'] if head['answers'] else 1.0
    record['rule'] = (f'no answer with reasoning text, and at most {MAX_PARSE_FAILURES:.0%} of the first '
                      'proposals not parsed')
    record['first_proposals_not_parsed_share'] = round(share, 4)
    record['ok'] = bool(head['answers']) and reasoning == 0 and share <= MAX_PARSE_FAILURES
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--files')
    p.add_argument('--plumbing', nargs='+')
    p.add_argument('--token-limit', type=int, default=TOKEN_LIMIT,
                   help='new tokens allowed per answer in the run (224 in v3.1, 384 in the scale study)')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if bool(args.files) == bool(args.plumbing):
        raise SystemExit('give exactly one of --files and --plumbing')
    record = model_files(args.files) if args.files else plumbing(args.plumbing, args.token_limit)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: v for k, v in record.items() if k not in ('files', 'recovery_answers_by_condition')}))


if __name__ == '__main__':
    main()
