"""Frozen evaluation I/O helpers."""
import gzip, hashlib, json, os
from pathlib import Path
from dynamic_demo.common import angular, tokens
VERSION = "dish_exhibition_v1"

def read(path):
    return json.loads(Path(path).read_text())

def rows(path):
    p = Path(path)
    with (gzip.open(p, 'rt') if p.suffix == '.gz' else p.open()) as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)

def write(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temporary = p.with_name(p.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temporary.replace(p)

def jsonl(path, values):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temporary = p.with_name(p.name + f'.{os.getpid()}.tmp')
    with temporary.open('w') as stream:
        for value in values:
            stream.write(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
    temporary.replace(p)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()
