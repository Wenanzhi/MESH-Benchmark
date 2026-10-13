"""Recording-local edge cues and receiver-independent world-trajectory cloud cues."""
from exhibition_dataset.prompts import context_lines,compact,render as legacy_render
from .tasks import TASK_VERSION

def render(sample,context=None):
    task=sample['task_id'];query=sample['query']
    if task in ['KW_ASR','DOA_ASR']:
        raise ValueError('Task removed from '+TASK_VERSION)
    if task not in ['TEXT_RANGE','DOA_RANGE_ASR','SPATIAL_ASR','WORLD_TRAJECTORY_ASR']:
        return legacy_render(sample,context,recording_bound=True)
    lines=context_lines(sample,context,recording_bound=True)
    if task=='TEXT_RANGE':
        lines += ['Find the HUMAN saying '+compact(query['transcript'])+'.',
                  'Return only that person\'s three-dimensional straight-line distance from this recording\'s microphone in meters, as a positive JSON number.']
        return '\n'.join(lines)
    if task=='WORLD_TRAJECTORY_ASR':
        if sample['setting']!='cloud' or sample.get('reference_robot_id') is not None:
            raise ValueError('World trajectory ASR must have no receiver reference')
        lines += ['Select the HUMAN whose WORLD position follows this trajectory. Each row is [time_s,x,y,z], in seconds and meters:',
                  compact([[f['time_s']]+f['xyz_m'] for f in query['frames']]),
                  f"Position tolerance is {query['position_tolerance_m']:g} m in three-dimensional Euclidean distance at each listed time.",
                  'The trajectory describes physical position, including silent periods; it does not indicate speaking activity. A constant trajectory denotes a stationary person.',
                  'Use all supplied recordings and their known microphone poses to identify this same person across the clip.',
                  'Exactly one human satisfies the whole trajectory. Ignore robot playback, other people and environmental noise.',
                  'Transcribe ALL of that person\'s speech in the ENTIRE input.',
                  'Return only the English transcript; no timestamps, speaker IDs, JSON fields or explanation.']
        return '\n'.join(lines)
    if sample['setting']!='edge':raise ValueError('Receiver-local ASR requires one edge recording')
    lines += ['Select the same HUMAN speaker satisfying ALL of the following spatial conditions.']
    for anchor in query['anchors']:
        fields=[]
        if 'doa_deg' in anchor:
            fields.append('direction [azimuth,elevation] '+compact(anchor['doa_deg'])+
                          f" degrees, spherical angular tolerance {query['angular_tolerance_deg']:g} degrees")
        if 'azimuth_deg' in anchor:
            fields.append(f"azimuth {anchor['azimuth_deg']} degrees, circular tolerance +/-{query['azimuth_tolerance_deg']:g} degrees")
        if 'distance_m' in anchor:
            fields.append(f"distance {anchor['distance_m']:.1f} m, tolerance +/-{query['distance_tolerance_m']:g} m")
        prefix=f"At scene time {anchor['time_s']:.1f} s, while this person is emitting speech: " if task=='SPATIAL_ASR' else 'Throughout this static recording: '
        lines.append(prefix+'; '.join(fields)+'.')
    if task=='SPATIAL_ASR':
        lines += ['These angles and distances belong to this recording\'s receiving microphone at each specified time. They can change because the person, microphone, or both move.',
                  'Angles wrap at -180/+180 degrees. The same person must satisfy every anchor; do not switch speakers at a crossing.']
    scope='Transcribe ALL of that person\'s speech in the ENTIRE input'
    if task=='SPATIAL_ASR':scope+=', including speech before, between and after the anchor times'
    lines += ['Exactly one human satisfies this query. Ignore other people, robot playback and environmental noise.',
              scope+'.',
              'Return only the English transcript; no timestamps, speaker IDs, JSON fields or explanation.']
    return '\n'.join(lines)
