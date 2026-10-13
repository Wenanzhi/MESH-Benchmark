"""Formal frame scorer. Time-grid stride comes from the frozen gold protocol.

DOA associations are fixed for the ENTIRE clip. Missing positions receive 180
degrees in DOA mean/variance; distance and world errors accompany coverage and
all-reference-frame success, so selective omission cannot hide failures.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

from .common import angular,tokens


def finite(x):
    return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)


def frame_map(output,times,kind,step=.2):
    valid=isinstance(output,dict) and isinstance(output.get('frames'),list)
    if not valid:return {},False
    expected={round(t/step) for t in times};result={};duplicates=set()
    for f in output['frames']:
        if not isinstance(f,dict) or not finite(f.get('time_s')):
            valid=False;continue
        t=f['time_s'];key=round(t/step)
        if abs(t-key*step)>1e-6 or key not in expected or not isinstance(f.get('active'),bool):
            valid=False;continue
        if key in result or key in duplicates:
            result.pop(key,None);duplicates.add(key);valid=False;continue
        if f['active']:
            v=f.get(kind)
            good=finite(v) and v>0 if kind=='distance_m' else (
                isinstance(v,list) and len(v)==(2 if kind=='doa_deg' else 3) and all(finite(x) for x in v))
            if kind=='doa_deg' and good:good=-90<=v[1]<=90
            if not good:valid=False;continue
        result[key]=f
    if set(result)!=expected:valid=False
    return result,valid


def edit_distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        new=[i]
        for j,y in enumerate(b,1):new.append(min(row[j]+1,new[-1]+1,row[j-1]+(x!=y)))
        row=new
    return row[-1]


def stats(errors):
    if not errors:return dict(mean_error=None,variance_error=None,rmse=None)
    mean=sum(errors)/len(errors)
    return dict(mean_error=mean,variance_error=sum((e-mean)**2 for e in errors)/len(errors),
                rmse=math.sqrt(sum(e*e for e in errors)/len(errors)))


def score(gold,prediction):
    task=gold['task_id'];answer=gold['output'];times=gold['expected_times_s'];step=(times[1]-times[0]) if len(times)>1 else .2
    if task=='KW_ASR':
        valid=isinstance(prediction,str);p=tokens(prediction) if valid else [];r=tokens(answer)
        if not r:
            return dict(format_valid=valid,keyword_case=gold['keyword_case'],reference_words=0,
                edits=0,wer=None,empty_correct=valid and not p,exact_match=valid and not p)
        edits=edit_distance(r,p)
        return dict(format_valid=valid,keyword_case=gold['keyword_case'],reference_words=len(r),
            edits=edits,wer=edits/len(r),empty_correct=None,exact_match=valid and p==r)
    if task=='DOA_TRAJECTORY':
        refs=answer['tracks'];raw=prediction.get('tracks',[]) if isinstance(prediction,dict) else []
        valid=isinstance(raw,list) and isinstance(prediction,dict) and 'tracks' in prediction
        if not isinstance(raw,list) or len(raw)>8:raw=[];valid=False
        track_ids=[tr.get('track_id') for tr in raw if isinstance(tr,dict)]
        if len(track_ids)!=len(raw) or any(not isinstance(x,str) or not x for x in track_ids) or len(set(track_ids))!=len(track_ids):
            raw=[];valid=False
        maps=[]
        for tr in raw:
            m,v=frame_map(tr,times,'doa_deg',step);maps.append(m);valid&=v
        if len(raw)!=len(refs):valid=False
        while len(maps)<len(refs):maps.append({})
        def cost(ref,m):
            return sum(angular(f['doa_deg'],m[round(f['time_s']/step)]['doa_deg'])
                if round(f['time_s']/step) in m and m[round(f['time_s']/step)]['active'] else 180.
                for f in ref['frames'] if f['active'])
        assignment=min(itertools.permutations(range(len(maps)),len(refs)),
            key=lambda p:sum(cost(refs[i],maps[j]) for i,j in enumerate(p)))
        errors=[];total=observed=success=tp=fp=fn=0;association={}
        for i,j in enumerate(assignment):
            ref=refs[i];m=maps[j];association[ref['track_id']]=raw[j]['track_id'] if j<len(raw) else None
            for f in ref['frames']:
                p=m.get(round(f['time_s']/step));on=bool(p and p['active'])
                tp+=f['active'] and on;fp+=not f['active'] and on;fn+=f['active'] and not on
                if f['active']:
                    total+=1
                    e=angular(f['doa_deg'],p['doa_deg']) if on else 180.
                    errors.append(e);observed+=on;success+=on and e<=20.
        for j,m in enumerate(maps):
            if j not in assignment:fp+=sum(f['active'] for f in m.values())
        switches=0
        for m in maps:
            previous=None
            for key in sorted(m):
                f=m[key]
                if not f['active']:continue
                candidates=[]
                for ref in refs:
                    rf=ref['frames'][key]
                    if rf['active']:candidates.append((angular(rf['doa_deg'],f['doa_deg']),ref['track_id']))
                if not candidates:continue
                e,identity=min(candidates)
                if e<=20:
                    if previous is not None and previous!=identity:switches+=1
                    previous=identity
        return dict(format_valid=bool(valid),units='degrees; variance degrees squared',**stats(errors),
            reference_active_frames=total,covered_frames=observed,coverage=observed/max(total,1),
            success_rate_20deg=success/max(total,1),active_precision=tp/max(tp+fp,1),
            active_recall=tp/max(tp+fn,1),missed_frames=fn,false_positive_frames=fp,
            identity_switches_diagnostic=switches,whole_clip_assignment=association)
    kind='distance_m' if task=='RANGE_TRAJECTORY' else 'xyz_m'
    m,valid=frame_map(prediction,times,kind,step);errors=[];total=tp=fp=fn=success=0
    for f in answer['frames']:
        p=m.get(round(f['time_s']/step));on=bool(p and p['active'])
        tp+=f['active'] and on;fp+=not f['active'] and on;fn+=f['active'] and not on
        if f['active']:
            total+=1
            if on:
                e=abs(f[kind]-p[kind]) if kind=='distance_m' else math.dist(f[kind],p[kind])
                errors.append(e);success+=e<=.5
    return dict(format_valid=valid,units='meters; variance meters squared',**stats(errors),
        reference_active_frames=total,covered_frames=len(errors),coverage=len(errors)/max(total,1),
        success_rate_0_5m=success/max(total,1),active_precision=tp/max(tp+fp,1),
        active_recall=tp/max(tp+fn,1),missed_frames=fn,false_positive_frames=fp)
