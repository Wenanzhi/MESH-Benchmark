"""Versioned distance evaluation policy; no rendering/runtime dependencies."""
from copy import deepcopy

SCORER_VERSION = 'dish_exhibition_v3.score.4'
DISTANCE_TASKS = ('RANGE', 'TEXT_RANGE', 'RANGE_TRAJECTORY')
RELATIVE_THRESHOLDS_PERCENT = (5, 10, 20, 30, 50)
ABSOLUTE_THRESHOLDS_M = (.25, .5, 1., 1.5, 2.)
DISTANCE_BINS = (('near', 0., 2.), ('middle', 2., 5.), ('far', 5., None))


def distance_protocol():
    return dict(
        tasks=list(DISTANCE_TASKS), primary_metric='rel_acc_at_20_percent',
        relative_error='abs(predicted_distance_m - true_distance_m) / true_distance_m',
        relative_thresholds_percent=list(RELATIVE_THRESHOLDS_PERCENT),
        accuracy_units='Fractions in [0,1]; multiply by 100 for display as accuracy percent.',
        mean_relative_error_units='Percent (100 times mean relative error); lower is better.',
        aggregation='Equal weight per question/trajectory, after averaging its speech-active frames. Static questions have one value. Each receiver view remains one question.',
        missing='Missing, inactive-on-active-gold and invalid distance predictions fail every accuracy threshold and reduce coverage. Error means use valid predictions only, exclude entirely uncovered trajectories and must be reported with coverage.',
        distance_domain='Ground-truth distances must be finite and strictly positive. No denominator epsilon or distance-label rounding is applied.',
        absolute_metrics='MAE (m), variance (m^2), RMSE (m) and absolute tolerance success remain auxiliary; their frame moments are averaged within trajectory first.',
        absolute_thresholds_m=list(ABSOLUTE_THRESHOLDS_M),
        diagnostics='frame_micro_diagnostic retains pooled-frame scores. Distance bins condition on each active frame true distance; trajectories may contribute to multiple bins. Bin scores are not equally averaged into the main score.',
        distance_bins=[dict(name=n,lower_inclusive_m=lo,upper_exclusive_m=hi) for n,lo,hi in DISTANCE_BINS],
        boundary_comparison='Inclusive <=, with absolute floating-point comparison tolerance 1e-12.',
        unchanged='DOA, WORLD coordinate errors, ASR WER and spatial-query selection tolerances are unchanged. Predictions remain distances in meters; label grid remains 0.5 s.',
        source='https://dcase.community/challenge2025/task-stereo-sound-event-localization-and-detection-in-regular-video-content#evaluation')


def update_evaluation_protocol(protocol):
    result=deepcopy(protocol)
    result['scorer_version']=SCORER_VERSION
    result['default_thresholds'].pop('distance_m',None)
    result['default_thresholds']['distance_relative_percent']=20
    result['distance_evaluation']=distance_protocol()
    return result


def update_ablation_recipes(recipes):
    result=deepcopy(recipes)
    result['thresholds'].pop('distance_m',None)
    result['thresholds'].update(distance_relative_percent=list(RELATIVE_THRESHOLDS_PERCENT),
                                distance_absolute_m_auxiliary=list(ABSOLUTE_THRESHOLDS_M))
    result['distance_metric_ablations']='Reuse one frozen prediction file for all relative/absolute tolerance curves; report distance-bin diagnostics and coverage. Do not change prompts or rerun inference per threshold.'
    return result


DISTANCE_README = '''## Distance evaluation (scorer dish_exhibition_v3.score.4)

For static `RANGE` / `TEXT_RANGE` and dynamic `RANGE_TRAJECTORY`, the primary
metric is **RelAcc@20%**: `abs(prediction - truth) / truth <= 0.20`.
`relative_tolerance_success` reports thresholds 5%, 10%, 20%, 30%, 50%; values
are accuracy fractions in [0,1]. `mean_relative_error_percent` (mRDE, lower is
better) is expressed in percent. `mae_m`, variance, RMSE and meter tolerance
success remain auxiliary. Predictions and gold distances remain in meters.

Each dynamic trajectory is averaged over its speech-active 0.5 s frames first,
then trajectories/questions receive equal weight. Static questions have one
distance. Missing/invalid predictions count as failures in every accuracy
denominator and reduce coverage. Error means use valid predictions only;
entirely uncovered trajectories have no error mean and must not be hidden by
omitting coverage. All-missing predictions produce zero accuracy/coverage and
null error means. Frame-micro results remain under `frame_micro_diagnostic`.

`distance_bins` reports near (<2 m), middle (2 <= d < 5 m), and far (>=5 m)
using the true distance at each active frame. The main score is not an equal
average of these bins. See each split's `public/evaluation_protocol.json` for
the complete policy. This score version changes no audio, labels, prompts,
DOA/WORLD-position scores, ASR scores or spatial-query selection tolerances.
The relative-error definition follows the [DCASE 2025 evaluation protocol](https://dcase.community/challenge2025/task-stereo-sound-event-localization-and-detection-in-regular-video-content#evaluation);
the 20% primary threshold and per-trajectory averaging are this benchmark's
choices. Historical scores retain their original scorer version.
'''
