"""Relative distance accuracy with equal weighting of whole trajectories."""
from collections import Counter
import math

from exhibition_dataset.score import Accumulator, finite
from .scoring_protocol import ABSOLUTE_THRESHOLDS_M, RELATIVE_THRESHOLDS_PERCENT, DISTANCE_BINS


def within(error, threshold):
    return error is not None and (error <= threshold or math.isclose(error,threshold,rel_tol=0.,abs_tol=1e-12))


def add_distance_references(gold, result):
    distances=([f['distance_m'] for f in gold['output']['frames'] if f['active']]
               if gold['task_id']=='RANGE_TRAJECTORY' else [gold['output']])
    if len(distances)!=len(result['errors']) or not all(finite(d) and d>0 for d in distances):
        raise ValueError('Distance references must be aligned, finite and strictly positive')
    result['reference_distances_m']=distances
    result['relative_errors']=[None if e is None else e/d for d,e in zip(distances,result['errors'])]
    return result


class RangeSummary:
    def __init__(self):
        self.counts=Counter();self.sums=Counter()
        self.relative_success=Counter();self.absolute_success=Counter();self.micro_relative_success=Counter()

    def add(self, distances, errors):
        if not distances:return
        n=len(distances)
        absolute=[e for e in errors if e is not None]
        relative=[None if e is None else e/d for d,e in zip(distances,errors)]
        valid_relative=[e for e in relative if e is not None]
        c,s=self.counts,self.sums
        c['questions']+=1;c['reference_positions']+=n;c['covered_positions']+=len(absolute)
        s['coverage']+=len(absolute)/n
        if absolute:
            c['covered_questions']+=1
            s['mae']+=sum(absolute)/len(absolute)
            s['mse']+=sum(e*e for e in absolute)/len(absolute)
            s['relative_mean']+=sum(valid_relative)/len(valid_relative)
            s['micro_relative_sum']+=sum(valid_relative)
        for percent in RELATIVE_THRESHOLDS_PERCENT:
            hits=sum(within(e,percent/100) for e in relative)
            self.relative_success[str(percent)]+=hits/n
            self.micro_relative_success[str(percent)]+=hits
        for threshold in ABSOLUTE_THRESHOLDS_M:
            self.absolute_success[str(threshold)]+=sum(within(e,threshold) for e in errors)/n

    def finish(self):
        c,s=self.counts,self.sums;n=c['questions'];k=c['covered_questions']
        mean=s['mae']/k if k else None
        mse=s['mse']/k if k else None
        rel={str(p):self.relative_success[str(p)]/n if n else None for p in RELATIVE_THRESHOLDS_PERCENT}
        return dict(aggregation='question_macro_after_active_frame_mean',questions=n,
            reference_positions=c['reference_positions'],covered_positions=c['covered_positions'],
            questions_with_valid_predictions=k,questions_without_valid_predictions=n-k,
            coverage=s['coverage']/n if n else None,
            primary_metric='rel_acc_at_20_percent',rel_acc_at_20_percent=rel['20'],
            relative_tolerance_success=rel,mean_relative_error_percent=100*s['relative_mean']/k if k else None,
            mae_m=mean,mean_error=mean,variance_error=max(0.,mse-mean*mean) if k else None,
            rmse=math.sqrt(mse) if k else None,
            tolerance_success={str(t):self.absolute_success[str(t)]/n if n else None for t in ABSOLUTE_THRESHOLDS_M})


class DistanceAccumulator(Accumulator):
    """Leave non-distance tasks and older callers of Accumulator unchanged."""
    def __init__(self):
        super().__init__()
        self.distance=None
        self.bins={}

    def add(self,result,thresholds):
        super().add(result,thresholds)
        if 'reference_distances_m' not in result:return
        if self.distance is None:
            self.distance=RangeSummary()
            self.bins={name:RangeSummary() for name,_,_ in DISTANCE_BINS}
        ds=result['reference_distances_m'];errors=result['errors']
        self.distance.add(ds,errors)
        for name,lo,hi in DISTANCE_BINS:
            pairs=[(d,e) for d,e in zip(ds,errors) if d>=lo and (hi is None or d<hi)]
            self.bins[name].add([d for d,e in pairs],[e for d,e in pairs])

    def finish(self):
        result=super().finish()
        if self.distance is None:return result
        micro=dict(result)
        n=self.distance.counts['reference_positions'];k=self.distance.counts['covered_positions']
        micro.update(aggregation='pooled_active_frames',
            mean_relative_error_percent=100*self.distance.sums['micro_relative_sum']/k if k else None,
            relative_tolerance_success={str(p):self.distance.micro_relative_success[str(p)]/n if n else None
                                        for p in RELATIVE_THRESHOLDS_PERCENT})
        result.update(self.distance.finish(),frame_micro_diagnostic=micro,
            distance_bins={name:dict(lower_inclusive_m=lo,upper_exclusive_m=hi,**self.bins[name].finish())
                           for name,lo,hi in DISTANCE_BINS})
        return result
