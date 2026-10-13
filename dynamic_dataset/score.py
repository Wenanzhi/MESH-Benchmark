"""Formal dynamic evaluation with full inventory denominators and fixed identities."""
from __future__ import annotations
import argparse,copy,gzip,hashlib,json,math,sqlite3,tempfile
from collections import defaultdict
from pathlib import Path
from .frame_score import score as demo_score
from .common import VERSION,rows,write


def safe_score(gold,prediction):
    """Bound malformed coordinates/times before invoking the tested frame scorer."""
    invalid=False;p=copy.deepcopy(prediction)
    if gold['task_id']=='KW_ASR':
        if isinstance(p,str):
            p=p.replace('’',"'").replace('‘',"'")
            if p.strip()=='""':p=''
        result=demo_score(gold,p)
        if not gold['output']:
            correct=isinstance(p,str) and not p.strip()
            result['empty_correct']=correct;result['exact_match']=correct
        return result
    sets=[]
    if isinstance(p,dict):
        if gold['task_id']=='DOA_TRAJECTORY' and isinstance(p.get('tracks'),list):
            sets=[t for t in p['tracks'] if isinstance(t,dict)]
        elif isinstance(p.get('frames'),list):sets=[p]
    maximum=max(gold['expected_times_s'])
    for container in sets:
        if not isinstance(container.get('frames'),list):continue
        filtered=[]
        for f in container['frames']:
            if not isinstance(f,dict):invalid=True;continue
            t=f.get('time_s')
            if isinstance(t,bool) or not isinstance(t,(int,float)) or not math.isfinite(t) or not 0<=t<=maximum+1e-6:
                invalid=True;continue
            if f.get('active') is True:
                key='doa_deg' if gold['task_id']=='DOA_TRAJECTORY' else 'distance_m' if gold['task_id']=='RANGE_TRAJECTORY' else 'xyz_m'
                value=f.get(key);v=[value] if key=='distance_m' else value
                if not isinstance(v,list) or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or abs(x)>1000 for x in v):
                    invalid=True;continue
                if key=='doa_deg' and (len(v)!=2 or not -180<=v[0]<=180 or not -90<=v[1]<=90):invalid=True;continue
            filtered.append(f)
        container['frames']=filtered
    try:result=demo_score(gold,p)
    except (ValueError,TypeError,OverflowError,IndexError,KeyError):
        result=demo_score(gold,None);invalid=True
    if invalid:result['format_valid']=False
    return result


class Accumulator:
    def __init__(self):self.values=defaultdict(float);self.case_counts=defaultdict(int)
    def add(self,record):
        v=self.values;v['samples']+=1;v['format_valid']+=record['format_valid']
        if record.get('keyword_case') is not None:
            v['reference_words']+=record['reference_words'];v['edits']+=record['edits'];v['exact_match']+=record['exact_match']
            self.case_counts[record['keyword_case']]+=1
            if not record['reference_words']:v['negative_samples']+=1;v['empty_correct']+=bool(record['empty_correct'])
            return
        v['reference_active_frames']+=record['reference_active_frames'];v['covered_frames']+=record['covered_frames']
        n=record['reference_active_frames'] if record['units'].startswith('degrees') else record['covered_frames']
        if n and record['mean_error'] is not None:
            v['error_count']+=n;v['error_sum']+=record['mean_error']*n;v['error_square_sum']+=(record['variance_error']+record['mean_error']**2)*n
        threshold='success_rate_20deg' if record['units'].startswith('degrees') else 'success_rate_0_5m'
        v['successful_frames']+=record[threshold]*record['reference_active_frames'];v['missed_frames']+=record['missed_frames'];v['false_positive_frames']+=record['false_positive_frames']
        v['true_positive_frames']+=record['covered_frames'];v['identity_switches']+=record.get('identity_switches_diagnostic',0)
    def finish(self):
        v=self.values;n=v['samples'];out=dict(samples=int(n),format_valid_fraction=v['format_valid']/max(n,1))
        if self.case_counts:
            refs=v['reference_words'];negs=v['negative_samples']
            out.update(corpus_wer=v['edits']/refs if refs else None,reference_words=int(refs),edits=int(v['edits']),
                exact_match_fraction=v['exact_match']/max(n,1),negative_samples=int(negs),negative_empty_accuracy=v['empty_correct']/negs if negs else None,
                keyword_cases=dict(self.case_counts))
        else:
            count=v['error_count'];mean=v['error_sum']/count if count else None
            out.update(reference_active_frames=int(v['reference_active_frames']),covered_frames=int(v['covered_frames']),
                coverage=v['covered_frames']/max(v['reference_active_frames'],1),success_rate=v['successful_frames']/max(v['reference_active_frames'],1),
                mean_error=mean,variance_error=max(0.,v['error_square_sum']/count-mean**2) if count else None,
                rmse=math.sqrt(v['error_square_sum']/count) if count else None,
                error_count=int(count),active_precision=v['true_positive_frames']/max(v['true_positive_frames']+v['false_positive_frames'],1),
                active_recall=v['true_positive_frames']/max(v['true_positive_frames']+v['missed_frames'],1),
                missed_frames=int(v['missed_frames']),false_positive_frames=int(v['false_positive_frames']),identity_switches_diagnostic=int(v['identity_switches']))
        return out


def freeze_predictions(path,known,database,strict=False):
    database.execute('CREATE TABLE predictions (sample_id TEXT PRIMARY KEY, output TEXT)')
    bad=set();counts=defaultdict(int);digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for number,line in enumerate(f,1):
            digest.update(line)
            if not line.strip():continue
            try:
                r=json.loads(line);sid=r.get('sample_id');output=r.get('output')
                if sid not in known:raise ValueError('Unknown sample_id')
                if sid in bad:counts['duplicate_rows']+=1;continue
                if database.execute('SELECT 1 FROM predictions WHERE sample_id=?',(sid,)).fetchone():
                    counts['duplicate_rows']+=1;bad.add(sid);database.execute('DELETE FROM predictions WHERE sample_id=?',(sid,))
                    if strict:raise ValueError('Duplicate sample_id')
                    continue
                database.execute('INSERT INTO predictions VALUES (?,?)',(sid,json.dumps(output)))
            except (ValueError,TypeError,AttributeError) as e:
                counts['invalid_rows']+=1
                if strict:raise ValueError('Invalid prediction row '+str(number)+': '+str(e)) from e
            if number%2000==0:database.commit()
    database.commit();counts['accepted_rows']=database.execute('SELECT COUNT(*) FROM predictions').fetchone()[0]
    return dict(prediction_sha256=digest.hexdigest(),counts=dict(counts),duplicate_ids=len(bad))


def evaluate(root,predictions,output,strict=False):
    root=Path(root);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    known={r['sample_id'] for r in rows(root/'public/test/index.jsonl')}
    buckets=defaultdict(Accumulator);missing=total=0;kw_pairs={}
    with tempfile.TemporaryDirectory(prefix='dish-evaluate-') as temp:
        db=sqlite3.connect(str(Path(temp)/'predictions.sqlite'))
        inventory=freeze_predictions(predictions,known,db,strict)
        # Gold is first opened only after the prediction inventory has been frozen.
        with gzip.open(output/'per_sample.jsonl.gz','wt') as per_sample:
            for g in rows(root/'private/test/gold.jsonl'):
                found=db.execute('SELECT output FROM predictions WHERE sample_id=?',(g['sample_id'],)).fetchone()
                p=json.loads(found[0]) if found else None;missing+=found is None;total+=1
                result=safe_score(g,p);record=dict(sample_id=g['sample_id'],scene_id=g['scene_id'],task_id=g['task_id'],setting=g['setting'],
                    branch=g['branch'],difficulty=g['difficulty'],**result)
                record.update(target_human_motion=g.get('target_human_motion','unspecified'),observed_receiver_motion=g.get('observed_receiver_motion','unspecified'))
                per_sample.write(json.dumps(record,allow_nan=False,separators=(',',':'))+'\n')
                keys=[g['setting']+'/'+g['task_id'],g['setting']+'/'+g['task_id']+'/'+g['difficulty'],
                    g['setting']+'/'+g['task_id']+'/branch/'+g['branch'],g['setting']+'/'+g['task_id']+'/robots/'+str(g['num_robots']),
                    g['setting']+'/'+g['task_id']+'/humans/'+str(g['num_humans']),g['setting']+'/'+g['task_id']+'/rt_bin/'+str(g['rt_bin'])]
                keys.append(g['setting']+'/'+g['task_id']+'/motion/target_'+g.get('target_human_motion','unspecified')+'/receiver_'+g.get('observed_receiver_motion','unspecified'))
                if g['task_id']=='KW_ASR':keys.append(g['setting']+'/KW_ASR/case/'+g.get('keyword_observation_case',g['keyword_case']))
                for key in keys:buckets[key].add(result)
                if g['task_id']=='KW_ASR':kw_pairs.setdefault(g['query_group_id'],[]).append(dict(setting=g['setting'],wer=result['wer'],correct=result['exact_match']))
        db.close()
    if total!=len(known):raise ValueError('Gold/public inventory mismatch')
    gains=[];accuracy_gains=[]
    for values in kw_pairs.values():
        edges=[r for r in values if r['setting']=='edge'];cloud=next(r for r in values if r['setting']=='cloud')
        if cloud['wer'] is not None:gains.append(sum(e['wer'] for e in edges)/len(edges)-cloud['wer'])
        accuracy_gains.append(float(cloud['correct'])-sum(float(e['correct']) for e in edges)/len(edges))
    report=dict(scorer_version=VERSION+'.1',samples=total,missing_predictions=missing,inventory=inventory,
        summary={k:v.finish() for k,v in sorted(buckets.items())},
        paired_kw_asr=dict(query_groups=len(kw_pairs),positive_groups=len(gains),
            mean_cloud_wer_improvement_over_mean_edge=sum(gains)/len(gains) if gains else None,
            mean_cloud_exact_match_improvement_over_mean_edge=sum(accuracy_gains)/len(accuracy_gains) if accuracy_gains else None),
        definitions=dict(doa='Whole-clip fixed identity matching; active-frame spherical error, mean/population variance/RMSE. Missing DOA positions count as 180 degrees.',
            distance_and_world='Error statistics on covered active frames, always accompanied by all-reference-frame coverage and 0.5m success.',
            kw_asr='Positive corpus WER; negative empty-string accuracy; invalid and missing outputs remain failures.',
            error_statistics='Frame-pooled statistics, not averages of per-example variances.',
            sampling_unit='Paired motion group/room and original source/speaker; views, questions and overlapping speech crops are correlated. No cross-task overall score.',
            motion_strata='Target-human and observed-receiver motion are reported separately. Motion elsewhere in the scene does not imply either selected entity moves.'))
    write(output/'metrics.json',report);print('SCORED',total,'samples;',missing,'missing',flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--strict',action='store_true')
    a=p.parse_args();evaluate(a.root,a.predictions,a.output,a.strict)
