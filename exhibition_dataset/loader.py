"""Blind single-question loading and concrete input-information ablations."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

import soundfile as sf

from .common import read,rows,jsonl,sha
from .prompts import render,ablation_recipes


def build_index(root):
    root=Path(root)
    offsets={}
    for kind in ['inputs','prompts']:
        with (root/'public/test'/f'{kind}.jsonl').open('rb') as stream:
            while True:
                offset=stream.tell()
                line=stream.readline()
                if not line:
                    break
                row=json.loads(line)
                sid=row['sample_id']
                offsets.setdefault(sid,{})[kind+'_offset']=offset
                if kind=='inputs':
                    offsets[sid].update({k:row[k] for k in ['sample_id','episode_id','scene_id','task_id','setting','mode']})
    if any('inputs_offset' not in r or 'prompts_offset' not in r for r in offsets.values()):
        raise ValueError('Input/prompt inventory mismatch')
    jsonl(root/'public/test/index.jsonl',offsets.values())
    return len(offsets)


class Dataset:
    def __init__(self,root,allow_pilot=False):
        self.root=Path(root)
        receipt=self.root/'release.complete.json'
        if not allow_pilot and (not receipt.exists() or read(receipt).get('passed') is not True):
            raise ValueError('Dataset acceptance is incomplete; --allow-pilot is only for explicit pilot checks')
        self.index={r['sample_id']:r for r in rows(self.root/'public/test/index.jsonl')}
        self.contexts={r['id']:r for r in ablation_recipes()['input_context']}
    def ids(self):
        return sorted(self.index)
    def _read(self,kind,sid):
        with (self.root/'public/test'/f'{kind}.jsonl').open('rb') as stream:
            stream.seek(self.index[sid][kind+'_offset'])
            return json.loads(stream.readline())
    def load(self,sid,context='full',audio=True):
        sample=self._read('inputs',sid)
        configuration=self.contexts[context]
        prompt_renderer=render
        recording_bound=sample.get('task_protocol_version')=='dish_exhibition_v3.tasks.3'
        if recording_bound:
            from exhibition_v3.prompts import render as prompt_renderer
        # No raw dataset row, sibling questions, source IDs or private labels are
        # sent to the model adapter. Context ablations remove structured fields
        # as well as removing them from the rendered prompt.
        poses=[p for p in sample['known_robot_poses'] if configuration['peer_poses'] or p['robot_id'] in sample['receiver_ids']]
        playback=[]
        if configuration['playback_times'] or configuration['playback_text']:
            for event in sample['known_robot_playback']:
                public=dict(robot_id=event['robot_id'])
                if configuration['playback_times']:
                    public.update(start_time_s=event['start_time_s'],end_time_s=event['end_time_s'])
                if configuration['playback_text']:
                    public['text']=event['text']
                playback.append(public)
        model_input=dict(sample_id=sid,task_id=sample['task_id'],setting=sample['setting'],mode=sample['mode'],
                         receiver_ids=sample['receiver_ids'],reference_robot_id=sample['reference_robot_id'],
                         duration_samples=sample['duration_samples'],sample_rate_hz=16000,
                         label_step_s=.5 if sample['mode']=='dynamic' else None,query=sample['query'],
                         robot_poses=poses,robot_playback=playback,prompt=prompt_renderer(sample,configuration),
                         audio_bindings=sample['audio_bindings'])
        if recording_bound:model_input.pop('reference_robot_id',None)
        if configuration['room']=='dimensions':
            model_input['room_dimensions_m']=sample['room_dimensions_m']
        elif configuration['room']=='layout':
            model_input['room_configuration']=sample['known_room']
        if audio:
            waveforms=[]
            for binding in sample['audio_bindings']:
                path=self.root/binding['path']
                if sha(path)!=binding['sha256']:
                    raise ValueError('Model audio checksum mismatch')
                wave,rate=sf.read(path,dtype='float32')
                if rate!=16000 or wave.shape!=(sample['duration_samples'],4):
                    raise ValueError('Invalid model audio shape')
                waveforms.append(wave)
            model_input['audio']=waveforms
        return model_input


def run(root,adapter,output,task=None,setting=None,context='full',limit=0,shard=0,shards=1,allow_pilot=False):
    dataset=Dataset(root,allow_pilot=allow_pilot)
    module,name=adapter.split(':',1)
    predict=getattr(importlib.import_module(module),name)
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    completed={r['sample_id'] for r in rows(output)} if output.exists() else set()
    count=0
    with output.open('a') as stream:
        for index,sid in enumerate(dataset.ids()):
            row=dataset.index[sid]
            if index%shards!=shard or sid in completed or (task and row['task_id']!=task) or (setting and row['setting']!=setting):
                continue
            prediction=predict(dataset.load(sid,context))
            stream.write(json.dumps(dict(sample_id=sid,output=prediction),allow_nan=False)+'\n')
            stream.flush()
            count+=1
            if limit and count>=limit:
                break


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--adapter',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--task')
    parser.add_argument('--setting',choices=['edge','cloud'])
    parser.add_argument('--context',default='full')
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--shard',type=int,default=0)
    parser.add_argument('--shards',type=int,default=1)
    parser.add_argument('--allow-pilot',action='store_true',help='Allow an unfinished pilot dataset for a smoke check')
    a=parser.parse_args()
    run(a.root,a.adapter,a.output,a.task,a.setting,a.context,a.limit,a.shard,a.shards,a.allow_pilot)
