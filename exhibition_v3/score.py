"""Version adapter for the established 0.5s static/dynamic formal scorer."""
import argparse,collections
from pathlib import Path
from exhibition_dataset.score import one as original_one
from exhibition_dataset import score as implementation
from .common import write,rows
from .tasks import TASK_VERSION
from .distance_metrics import DistanceAccumulator,add_distance_references
from .scoring_protocol import SCORER_VERSION,DISTANCE_TASKS,distance_protocol

def one(gold,prediction):
    if gold['task_id'] in ['KW_ASR','DOA_ASR']:raise ValueError('Removed V3 task')
    aliases={'TEXT_RANGE':'RANGE','DOA_RANGE_ASR':'DOA_ASR','SPATIAL_ASR':'DOA_ASR','WORLD_TRAJECTORY_ASR':'DOA_ASR'}
    result=original_one(dict(gold,task_id=aliases.get(gold['task_id'],gold['task_id'])),prediction)
    return add_distance_references(gold,result) if gold['task_id'] in DISTANCE_TASKS else result

def same_target_spatial_asr(root,output):
    tasks={'SPATIAL_ASR','WORLD_TRAJECTORY_ASR'}
    scores={r['sample_id']:r for r in rows(Path(output)/'per_sample.jsonl.gz') if r['task_id'] in tasks}
    groups=collections.defaultdict(list)
    for gold in rows(Path(root)/'private/test/gold.jsonl'):
        if gold['task_id'] in tasks:groups[gold['target_group_id']].append(gold)
    values=collections.defaultdict(list);unmatched=collections.Counter()
    for group in groups.values():
        clouds=[g for g in group if g['setting']=='cloud'];edges=[g for g in group if g['setting']=='edge']
        if len(clouds)>1:raise ValueError('Duplicate cloud query for one target')
        if not clouds or not edges:
            unmatched['cloud_only' if clouds else 'edge_only']+=1
            continue
        cloud=clouds[0];c=scores[cloud['sample_id']]
        if any(g['target_source_id']!=cloud['target_source_id'] or g['output']!=cloud['output'] for g in edges):
            raise ValueError('Mismatched edge/cloud target or transcript')
        subsets={'all':edges,'robots/'+str(cloud['num_robots']):edges,'target_motion/'+cloud['target_human_motion']:edges}
        for label in {g['cue_type'] for g in edges}:subsets['edge_cue/'+label]=[g for g in edges if g['cue_type']==label]
        for key,subset in subsets.items():
            e=[scores[g['sample_id']] for g in subset]
            values[key].append(dict(wer_difference=sum(x['edits']/x['reference_words'] for x in e)/len(e)-c['edits']/c['reference_words'],
                exact_difference=float(c['exact_match'])-sum(float(x['exact_match']) for x in e)/len(e),edge_views=len(e)))
    return dict(protocol='Same target, different spatial cues: edge microphone-local conditions versus cloud WORLD trajectory. This is not a controlled receiver-count benefit.',
        aggregation='Average edge views within each physical target before averaging targets; never duplicate the cloud question.',
        unmatched_target_groups=dict(unmatched),
        strata={key:dict(target_groups=len(items),edge_views=sum(x['edge_views'] for x in items),
            mean_edge_minus_cloud_wer=sum(x['wer_difference'] for x in items)/len(items),
            mean_cloud_minus_edge_exact_match=sum(x['exact_difference'] for x in items)/len(items)) for key,items in values.items()})

def evaluate(root,predictions,output):
    result=implementation.evaluate(root,predictions,output,score_fn=one,accumulator_factory=DistanceAccumulator)
    result.pop('paired_kw_asr',None)
    result.update(scorer_version=SCORER_VERSION,task_protocol_version=TASK_VERSION,distance_evaluation=distance_protocol(),same_target_spatial_asr=same_target_spatial_asr(root,output),
        independence='Cluster by room then base scene. Receiver views and the static/two dynamic derivatives are correlated.')
    write(Path(output)/'metrics.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();evaluate(a.root,a.predictions,a.output)
