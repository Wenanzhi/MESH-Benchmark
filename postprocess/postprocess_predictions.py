"""Portable driver for the frozen baseline rules; requires no labels or GPU."""
import argparse
import hashlib
import json
from pathlib import Path

from normalization import ASR, parse
from review_asr_score4 import extract
from schema_repair import repair

HERE = Path(__file__).resolve().parent


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify_frozen_files():
    manifest = json.loads((HERE / 'provenance.json').read_text(encoding='utf-8'))
    for name, item in manifest['frozen_files'].items():
        if sha256(HERE / name) != item['sha256']:
            raise ValueError(f'Frozen source changed: {name}')
    return manifest


def process_record(record, override=None):
    """Apply the original worker parsing, schema repair, then ASR extraction."""
    sid, task, text = record['sample_id'], record['task_id'], record['raw_text']
    if not isinstance(text, str):
        raise ValueError(f'{sid}: raw_text must be a string; do not turn null into silence')
    raw, raw_rules = parse(text, task)
    parsed, syntax_rules = parse(text, task, True)
    baseline, schema_rules = repair(parsed, task)
    reviewed = baseline
    audit = dict(sample_id=sid, task_id=task, raw_text=text,
                 raw_parse_rules=raw_rules, syntax_rules=syntax_rules,
                 schema_rules=schema_rules, manual_override_applied=False)
    if task in ASR:
        reviewed, rules, kind, flags = extract(text)
        if override is not None:
            if (hashlib.sha256(text.encode('utf-8')).hexdigest() != override['raw_sha256']
                    or not override['transcript'] or override['transcript'] not in text):
                raise ValueError(f'{sid}: historical override does not match the frozen response')
            reviewed = override['transcript']
            rules, kind, flags = ['manual_explicit_final_paragraph'], 'candidate', []
            audit['manual_override_applied'] = True
        audit.update(review_rules=rules, review_status=kind, review_flags=flags)
    elif override is not None:
        raise ValueError(f'{sid}: ASR override supplied for a spatial task')
    audit.update(baseline_output=baseline, reviewed_output=reviewed)
    return {'raw': raw, 'baseline': baseline, 'reviewed': reviewed}, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions', type=Path, required=True, nargs='+',
                        help='JSONL files from ONE model and ONE static/dynamic split')
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='New directory; an existing directory is never overwritten')
    parser.add_argument('--historical-overrides', type=Path,
                        help='Only when replaying the named historical baseline')
    parser.add_argument('--model')
    parser.add_argument('--split', choices=['static', 'dynamic'])
    args = parser.parse_args()
    manifest = verify_frozen_files()
    overrides = {}
    if args.historical_overrides:
        if not args.model or not args.split:
            parser.error('--historical-overrides requires --model and --split')
        for item in json.loads(args.historical_overrides.read_text(encoding='utf-8')):
            if (item['arm'], item['split']) == (args.model, args.split):
                if item['sample_id'] in overrides:
                    raise ValueError('Duplicate historical override')
                overrides[item['sample_id']] = item
    args.output_dir.mkdir(parents=True, exist_ok=False)
    from contextlib import ExitStack
    seen = set()
    applied = 0
    with ExitStack() as stack:
        streams = {name: stack.enter_context((args.output_dir / f'{name}_predictions.jsonl')
                   .open('w', encoding='utf-8', newline='\n')) for name in ('raw', 'baseline', 'reviewed')}
        audit_stream = stack.enter_context((args.output_dir / 'postprocess_audit.jsonl')
                       .open('w', encoding='utf-8', newline='\n'))
        for path in args.predictions:
            with path.open(encoding='utf-8') as source:
                for line in source:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    sid = record['sample_id']
                    if sid in seen:
                        raise ValueError(f'Duplicate sample_id: {sid}')
                    seen.add(sid)
                    outputs, audit = process_record(record, overrides.get(sid))
                    applied += audit['manual_override_applied']
                    for name, value in outputs.items():
                        streams[name].write(json.dumps(dict(sample_id=sid, output=value),
                            ensure_ascii=False, allow_nan=False) + '\n')
                    audit_stream.write(json.dumps(audit, ensure_ascii=False, allow_nan=False) + '\n')
    if set(overrides) - seen:
        raise ValueError('Requested historical override sample is absent from the input')
    summary = dict(complete=True, records=len(seen), model=args.model, split=args.split,
                   historical_overrides_applied=applied, scoring_revision=manifest['scoring_revision'],
                   source_files=[dict(name=p.name, sha256=sha256(p)) for p in args.predictions],
                   frozen_source_hashes={k: v['sha256'] for k, v in manifest['frozen_files'].items()},
                   driver_sha256=sha256(__file__),
                   overrides_sha256=sha256(args.historical_overrides) if args.historical_overrides else None,
                   review_scope='deterministic extraction, not exhaustive human review')
    (args.output_dir / 'postprocess_complete.json').write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
