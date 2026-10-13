"""Frozen dynamic evaluation helpers."""
import gzip, json, os
from pathlib import Path
from dynamic_demo.common import angular, tokens
VERSION = "dish_dynamic_test_v1"

def rows(path):
    opener=gzip.open if str(path).endswith('.gz') else open
    with opener(path,'rt') as f:
        for line in f:
            if line.strip():yield json.loads(line)

def write(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.'+str(os.getpid())+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(p)
