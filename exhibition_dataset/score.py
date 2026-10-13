"""Formal scoring of static and 0.5-second dynamic exhibition tasks.

Predictions: JSONL {sample_id, output}. Missing/invalid predictions remain in
the full denominator. Spatial error statistics are accompanied by coverage
and tolerance success. Dynamic DOA uses one identity assignment for the whole
clip. Threshold curves reuse the SAME frozen prediction file.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import itertools
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from dynamic_dataset.score import safe_score
from dynamic_dataset.frame_score import frame_map, edit_distance
from .common import VERSION, angular, tokens, rows, sha, write


def finite(value):
    return type(value) in [float,int] and math.isfinite(value)


def decode(value, task):
    if isinstance(value,str):
        text=value.strip()
        if text.startswith('```') and text.endswith('```'):
            text=text.split('\n',1)[-1].rsplit('```',1)[0].strip()
        if task in ['KW_ASR','DOA_ASR','C2_REGION_ASR']:
            if text == '""':
                return ''
            return value
        try:
            value=json.loads(text,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
        except (ValueError,TypeError):
            return None
    return value


def spatial_static(gold, prediction):
    task, answer = gold['task_id'],gold['output']
    degree = task in ['DOA','TEXT_DOA']
    reference = answer if task in ['DOA','C1_SETLOC'] else [answer]
    if task == 'RANGE':
        valid = finite(prediction) and prediction > 0
        errors = [abs(answer-prediction)] if valid else [None]
    elif task in ['DOA','C1_SETLOC']:
        dimension = 2 if task == 'DOA' else 3
        valid = isinstance(prediction,list) and len(prediction)==len(reference)
        points = prediction if isinstance(prediction,list) and len(prediction)<=8 else []
        points = [p for p in points if isinstance(p,list) and len(p)==dimension and all(finite(v) for v in p)
                  and (not degree or (-180<=p[0]<=180 and -90<=p[1]<=90))]
        valid = valid and len(points)==len(reference)
        n=max(len(points),len(reference))
        costs=np.full((len(reference),n),1e6)
        for i,target in enumerate(reference):
            for j,point in enumerate(points):
                costs[i,j]=angular(target,point) if degree else math.dist(target,point)
        indices,mapping=linear_sum_assignment(costs)
        errors=[None]*len(reference)
        for i,j in zip(indices,mapping):
            if j<len(points):
                errors[i]=float(costs[i,j])
    else:
        dimension=2 if task == 'TEXT_DOA' else 3
        valid = isinstance(prediction,list) and len(prediction)==dimension and all(finite(v) for v in prediction)
        if degree and valid:
            valid = -180<=prediction[0]<=180 and -90<=prediction[1]<=90
        errors = [(angular(answer,prediction) if degree else math.dist(answer,prediction)) if valid else None]
    # Static DOA requests humans AND other robot playback, so the main score
    # includes both. Role-specific diagnostics allow a human-only comparison
    # against the dynamic task without dropping requested targets silently.
    if task=='DOA':
        role_errors={role:[e for e,r in zip(errors,gold['source_roles']) if r==role] for role in ['human','robot']}
    else:
        role_errors=None
    if degree:
        statistics_errors=[e if e is not None else 180. for e in errors]
    else:
        statistics_errors=[e for e in errors if e is not None]
    return dict(format_valid=bool(valid),units='degrees' if degree else 'meters',
                errors=errors,statistics_errors=statistics_errors,total=len(errors),
                covered=sum(e is not None for e in errors),speech_role_errors_diagnostic=role_errors)


def dynamic_errors(gold,prediction,result):
    task=gold['task_id']
    times=gold['expected_times_s']
    step=.5
    if task=='DOA_TRAJECTORY':
        raw=prediction.get('tracks',[]) if isinstance(prediction,dict) else []
        valid_ids=isinstance(raw,list) and len(raw)<=8 and all(isinstance(t,dict) and isinstance(t.get('track_id'),str) and t['track_id'] for t in raw)
        tracks={t['track_id']:t for t in raw} if valid_ids and len({t['track_id'] for t in raw})==len(raw) else {}
        errors=[]
        for reference in gold['output']['tracks']:
            identity=result['whole_clip_assignment'].get(reference['track_id'])
            mapped,_=frame_map(tracks.get(identity),times,'doa_deg',step)
            for frame in reference['frames']:
                if not frame['active']:
                    continue
                p=mapped.get(round(frame['time_s']/step))
                value=p['doa_deg'] if p and p['active'] else None
                valid=value is not None and -180<=value[0]<=180 and -90<=value[1]<=90
                errors.append(angular(frame['doa_deg'],value) if valid else None)
        return errors
    key='distance_m' if task=='RANGE_TRAJECTORY' else 'xyz_m'
    mapped,_=frame_map(prediction,times,key,step)
    errors=[]
    for frame in gold['output']['frames']:
        if not frame['active']:
            continue
        p=mapped.get(round(frame['time_s']/step))
        value=p[key] if p and p['active'] else None
        valid=value is not None and (abs(value)<=1000 if key=='distance_m' else all(abs(v)<=1000 for v in value))
        errors.append((abs(frame[key]-value) if key=='distance_m' else math.dist(frame[key],value)) if valid else None)
    return errors


def one(gold,prediction):
    task=gold['task_id']
    prediction=decode(prediction,task)
    if task in ['KW_ASR','DOA_ASR','C2_REGION_ASR']:
        valid=isinstance(prediction,str)
        target=tokens(gold['output'])
        given=tokens(prediction) if valid else []
        edits=edit_distance(target,given)
        return dict(format_valid=valid,asr=True,reference_words=len(target),edits=edits,
                    negative=not target,empty_correct=valid and not prediction.strip(),
                    exact_match=valid and target==given and (bool(target) or not prediction.strip()))
    if task.endswith('TRAJECTORY'):
        result=safe_score(gold,prediction)
        errors=dynamic_errors(gold,prediction,result)
        degree=task=='DOA_TRAJECTORY'
        return dict(format_valid=result['format_valid'],asr=False,
                    units='degrees' if degree else 'meters',errors=errors,total=len(errors),
                    covered=sum(e is not None for e in errors),
                    statistics_errors=[e if e is not None else 180. for e in errors] if degree else [e for e in errors if e is not None],
                    missed_frames=result['missed_frames'],false_positive_frames=result['false_positive_frames'],
                    identity_switches_diagnostic=result.get('identity_switches_diagnostic',0))
    return dict(spatial_static(gold,prediction),asr=False)


class Accumulator:
    def __init__(self):
        self.values=Counter()
        self.success=Counter()
        self.is_asr=None
        self.units=None
    def add(self,result,thresholds):
        v=self.values
        v['samples']+=1
        v['format_valid']+=result['format_valid']
        self.is_asr=result['asr']
        if self.is_asr:
            v['reference_words']+=result['reference_words']
            v['edits']+=result['edits'] if result['reference_words'] else 0
            v['negative_samples']+=result['negative']
            v['empty_correct']+=result['negative'] and result['empty_correct']
            v['exact_match']+=result['exact_match']
            return
        self.units=result['units']
        v['reference_positions']+=result['total']
        v['covered_positions']+=result['covered']
        errors=result['statistics_errors']
        v['error_count']+=len(errors)
        v['error_sum']+=sum(errors)
        v['error_square_sum']+=sum(e*e for e in errors)
        v['missed_frames']+=result.get('missed_frames',0)
        v['false_positive_frames']+=result.get('false_positive_frames',0)
        v['identity_switches']+=result.get('identity_switches_diagnostic',0)
        for threshold in thresholds:
            self.success[str(threshold)]+=sum(e is not None and e<=threshold for e in result['errors'])
    def finish(self):
        v=self.values
        result=dict(samples=v['samples'],format_valid_fraction=v['format_valid']/max(v['samples'],1))
        if self.is_asr:
            result.update(corpus_wer=v['edits']/v['reference_words'] if v['reference_words'] else None,
                          reference_words=v['reference_words'],word_edits=v['edits'],negative_samples=v['negative_samples'],
                          negative_empty_accuracy=v['empty_correct']/v['negative_samples'] if v['negative_samples'] else None,
                          exact_match_fraction=v['exact_match']/max(v['samples'],1))
        else:
            count=v['error_count']
            mean=v['error_sum']/count if count else None
            result.update(units=self.units,reference_positions=v['reference_positions'],covered_positions=v['covered_positions'],
                          coverage=v['covered_positions']/max(v['reference_positions'],1),mean_error=mean,
                          variance_error=max(0.,v['error_square_sum']/count-mean**2) if count else None,
                          rmse=math.sqrt(v['error_square_sum']/count) if count else None,
                          tolerance_success={k:n/max(v['reference_positions'],1) for k,n in self.success.items()},
                          missed_frames=v['missed_frames'],false_positive_frames=v['false_positive_frames'],
                          identity_switches_diagnostic=v['identity_switches'])
        return result


def evaluate(root,predictions,output,score_fn=None,accumulator_factory=Accumulator):
    root,output=Path(root),Path(output)
    score_fn=score_fn or one
    output.mkdir(parents=True,exist_ok=True)
    known={r['sample_id'] for r in rows(root/'public/test/index.jsonl')}
    # Freeze the prediction bytes before opening gold; duplicate IDs become failures.
    digest=sha(predictions)
    given={}
    duplicates=set()
    invalid=0
    for row in rows(predictions):
        sid=row.get('sample_id')
        if sid not in known:
            invalid+=1
            continue
        if sid in given or sid in duplicates:
            given.pop(sid,None)
            duplicates.add(sid)
        else:
            given[sid]=row.get('output')
    accumulators=defaultdict(accumulator_factory)
    keyword_pairs=defaultdict(list)
    total=missing=0
    with gzip.open(output/'per_sample.jsonl.gz','wt') as stream:
        for gold in rows(root/'private/test/gold.jsonl'):
            total+=1
            prediction=given.get(gold['sample_id'])
            missing+=gold['sample_id'] not in given
            try:
                result=score_fn(gold,prediction)
            except (ValueError,TypeError,KeyError,IndexError,OverflowError):
                result=score_fn(gold,None)
                result['format_valid']=False
            thresholds=[5.,10.,20.,30.,45.] if result.get('units')=='degrees' else [.25,.5,1.,1.5,2.]
            base=gold['setting']+'/'+gold['task_id']
            keys=[base,base+'/robots/'+str(gold['num_robots']),base+'/humans/'+str(gold['num_humans']),
                  base+'/rt_bin/'+str(gold['rt_bin']),base+'/branch/'+gold['branch'],
                  base+'/noise/'+gold.get('noise_type','unspecified'),
                  base+'/noise_snr/'+str(gold.get('noise_nominal_snr_db')),
                  base+'/layout/'+gold.get('layout_template','unspecified'),
                  base+'/motion/target_'+gold.get('target_human_motion','unspecified')+'/receiver_'+gold.get('observed_receiver_motion','unspecified')]
            case=gold.get('case',gold.get('keyword_case'))
            if case is not None:
                keys.append(base+'/case/'+case)
            if 'cue_type' in gold:keys.append(base+'/cue/'+gold['cue_type'])
            if 'evaluation_group' in gold:keys.append(base+'/selection/'+gold['evaluation_group'])
            for key in keys:
                accumulators[key].add(result,thresholds)
            for role,errors in (result.get('speech_role_errors_diagnostic') or {}).items():
                if errors:
                    specific=dict(result,errors=errors,total=len(errors),covered=sum(e is not None for e in errors),
                                  statistics_errors=[e if e is not None else 180. for e in errors])
                    accumulators[base+'/source_role/'+role].add(specific,thresholds)
            if gold['task_id']=='KW_ASR':
                keyword_pairs[gold['query_group_id']].append(dict(setting=gold['setting'],
                    wer=result['edits']/result['reference_words'] if result['reference_words'] else None,
                    exact=result['exact_match']))
            stream.write(json.dumps(dict(sample_id=gold['sample_id'],episode_id=gold['episode_id'],
                        scene_id=gold['scene_id'],task_id=gold['task_id'],setting=gold['setting'],**result),
                        separators=(',',':'),allow_nan=False)+'\n')
    if total!=len(known):
        raise ValueError('Public/gold sample inventory mismatch')
    wer_gains=[]
    exact_gains=[]
    for values in keyword_pairs.values():
        edges=[v for v in values if v['setting']=='edge']
        cloud=next(v for v in values if v['setting']=='cloud')
        if cloud['wer'] is not None:
            wer_gains.append(sum(v['wer'] for v in edges)/len(edges)-cloud['wer'])
        exact_gains.append(float(cloud['exact'])-sum(float(v['exact']) for v in edges)/len(edges))
    report=dict(scorer_version=VERSION+'.1',label_step_s=.5,samples=total,missing_predictions=missing,
                prediction_sha256=digest,duplicate_prediction_ids=len(duplicates),unknown_prediction_rows=invalid,
                metrics={k:v.finish() for k,v in sorted(accumulators.items())},
                paired_kw_asr=dict(query_groups=len(keyword_pairs),positive_query_groups=len(wer_gains),
                    mean_cloud_wer_improvement_over_mean_edge=sum(wer_gains)/len(wer_gains) if wer_gains else None,
                    mean_cloud_exact_match_improvement_over_mean_edge=sum(exact_gains)/len(exact_gains) if exact_gains else None),
                protocol='All-reference denominators. DOA omissions count as 180 degrees in errors. Metric errors accompany coverage. Fixed identity across the whole dynamic clip.',
                independence='Bootstrap over hall and matched family; receiver views, conditions and source crops are correlated.',
                threshold_curves='Computed from one frozen prediction file; larger tolerance changes the criterion, not model predictions.')
    write(output/'metrics.json',report)
    print('SCORED',total,'questions;',missing,'missing',flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--predictions',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    evaluate(args.root,args.predictions,args.output)
