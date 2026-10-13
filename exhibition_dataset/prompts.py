"""Public-input-only task prompts and reproducible information ablations."""
from __future__ import annotations

import json


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def context_lines(sample, context=None, recording_bound=False):
    context = context or dict(peer_poses=True, playback_times=True, playback_text=True, room='dimensions')
    dynamic = sample['mode'] == 'dynamic'
    lines = ['You are given synchronized recordings of the same exhibition-hall speech scene.']
    for robot in sample['receiver_ids']:
        lines.append(robot+': <|AUDIO|><|spatial|>')
    lines += [f"Each audio covers [0.000,{sample['duration_samples']/16000:.3f}) seconds.",
              'The input is four-channel 16 kHz FOA, ACN/SN3D [W,Y,Z,X].',
              'Receiver-local X is front, Y is left, Z is up. Azimuth: front 0, left +90, right -90 degrees. Elevation is positive upwards.',
              'World [x,y,z] coordinates are meters; +y is up. Robot yaw 0 faces world -z; positive yaw turns towards +x.',
              'Each receiver has its own playback ideally removed. Other robot playback is interference except when the static DOA task explicitly includes it.',
              'Environmental noise is never a speech target. Do not transcribe noise.',
              'Known positions are rounded to 0.1 m, yaw to whole degrees.']
    if dynamic:
        lines += ['Spatial trajectory outputs, when requested, use scene times 0.0,0.5,1.0,1.5,... strictly before the audio ends.',
                  'Robots and people may translate horizontally; robot yaw and height stay fixed.',
                  'Spatial labels describe physical positions at the requested scene time. Propagation delay remains in the audio.']
    lines.append('Known robot poses; positions are [time_s,x,y,z]:')
    for pose in sample['known_robot_poses']:
        # All supplied receivers remain calibrated for the world-coordinate tasks.
        if context['peer_poses'] or pose['robot_id'] in sample['receiver_ids']:
            lines.append(pose['robot_id']+': yaw '+str(pose['yaw_deg'])+'; '+compact(pose['positions']))
    if context['playback_times'] or context['playback_text']:
        lines.append('Known robot playback:')
        for event in sample['known_robot_playback']:
            text = event['robot_id']
            if context['playback_times']:
                text += f": [{event['start_time_s']:.3f},{event['end_time_s']:.3f}) seconds"
            if context['playback_text']:
                text += '; text '+compact(event['text'])
            lines.append(text)
    if context['room'] == 'dimensions':
        lines.append('Room dimensions [width,height,depth], meters: '+compact(sample['room_dimensions_m']))
    elif context['room'] == 'layout':
        lines.append('Room configuration: '+compact(sample['known_room']))
    reference = sample.get('reference_robot_id')
    if recording_bound and sample['setting']=='edge':
        if len(sample['receiver_ids'])!=1 or reference not in [None,sample['receiver_ids'][0]]:
            raise ValueError('Edge spatial coordinates must belong to the supplied recording')
        lines.append("All directions and microphone distances use this recording's receiving microphone at the specified time.")
    elif reference and not recording_bound:
        lines.append('Use '+reference+' as the direction and microphone-distance reference at each time.')
    return lines


def render(sample, context=None, recording_bound=False):
    task, query = sample['task_id'], sample['query']
    lines = context_lines(sample, context, recording_bound)
    microphone='recording microphone' if recording_bound else 'reference microphone'
    if task == 'DOA':
        lines += [f"Localize {query['source_count']} speech sources: all humans and any OTHER robot with audible playback. Ignore this receiver's own playback.",
                  'Return only a JSON array of [azimuth,elevation] degree pairs, one per speech source. No labels or explanation.']
    elif task == 'RANGE':
        low, high = query['azimuth_sector_deg']
        lines += [f'Select the human speaker in the azimuth sector [{low},{high}) degrees.',
                  f'Return only that person\'s distance from the {microphone} in meters, as a positive JSON number.']
    elif task == 'TEXT_DOA':
        lines += ['Find the human saying '+compact(query['transcript'])+'.',
                  'Return only [azimuth,elevation] in degrees, as a JSON array.']
    elif task == 'DOA_ASR':
        lines += ['Select the human at direction [azimuth,elevation] '+compact(query['doa_deg'])+' degrees.',
                  'Transcribe all that person\'s speech in the input. Return only the English transcript.']
    elif task == 'C1_SETLOC':
        lines += [f"Localize the {query['human_source_count']} HUMAN speakers. Robot playback is not a human.",
                  'Return only a JSON array of world [x,y,z] points in meters, one per person.']
    elif task == 'C2_REGION_ASR':
        lines += ['Select the human in this WORLD region: '+compact(query['region'])+'.',
                  'The region uses inclusive minimum and exclusive maximum bounds on each axis.',
                  'Transcribe all of that person\'s speech; if no human is in the region, return the literal empty string "".',
                  'Return only the English transcript or "".']
    elif task == 'C3_TEXTLOC':
        lines += ['Find the human saying '+compact(query['transcript'])+'.',
                  'Return only that person\'s WORLD [x,y,z] point in meters, as a JSON array.']
    elif task == 'DOA_TRAJECTORY':
        lines += [f"Return {query['human_source_count']} HUMAN speaker tracks. Keep one stable arbitrary track_id per person across the whole clip.",
                  'Robot playback and noise are never tracks. Output absolute DOA, not angular changes.',
                  'Return JSON {"tracks":[{"track_id":"S1","frames":[{"time_s":0.0,"active":false},...]}]} with every requested grid time in every track.',
                  'active=true means the person is emitting speech; brief phonetic pauses and reverberation-only tails are inactive.',
                  'For active=true add "doa_deg":[azimuth,elevation], in degrees. For active=false omit doa_deg.']
    elif task == 'RANGE_TRAJECTORY':
        low, high = query['initial_sector_deg']
        a, b = query['cue_time_range_s']
        lines += [f"At {query['selection_time_s']:.3f} seconds, select the HUMAN emitting speech in azimuth sector [{low},{high}) degrees. Initial listening cue: [{a:.3f},{b:.3f}) seconds.",
                  'Keep following this same person after they leave the sector.',
                  'Return JSON {"frames":[{"time_s":0.0,"active":false},...]} containing every requested grid time.',
                  f'During this person\'s emitted speech use active=true and "distance_m": a positive distance from the current {microphone}. Otherwise use active=false and omit distance_m.']
    elif task == 'TEXT_TRAJECTORY':
        lines += ['Find the human saying '+compact(query['transcript'])+'. Track this same person during all their speech in the clip.',
                  'Return JSON {"frames":[{"time_s":0.0,"active":false},...]} containing every requested grid time.',
                  'During target speech use active=true and "xyz_m":[x,y,z] in WORLD meters; otherwise use active=false and omit xyz_m.']
    elif task == 'KW_ASR':
        lines += ['The wake keyword/phrase is '+compact(query['wake_phrase'])+'.',
                  'Match consecutive whole words at the BEGINNING of a human utterance, ignoring case and punctuation. A brief natural pause does not start a new utterance.',
                  'If exactly one distinct human matches, transcribe ALL their speech in the input, including the wake phrase, in time order.',
                  'Ignore all other people, robot playback and environmental noise. If zero or multiple humans match, return the literal empty string "".',
                  'Return only the English transcript or ""; no timestamps, labels, fields or explanation.']
    else:
        raise ValueError('Unknown task')
    return '\n'.join(lines)


def ablation_recipes():
    return dict(input_context=[
        dict(id='full', peer_poses=True, playback_times=True, playback_text=True, room='dimensions'),
        dict(id='without_peer_poses', peer_poses=False, playback_times=True, playback_text=True, room='dimensions'),
        dict(id='without_playback_times', peer_poses=True, playback_times=False, playback_text=True, room='dimensions'),
        dict(id='without_playback_text', peer_poses=True, playback_times=True, playback_text=False, room='dimensions'),
        dict(id='without_playback_info', peer_poses=True, playback_times=False, playback_text=False, room='dimensions'),
        dict(id='without_room_info', peer_poses=True, playback_times=True, playback_text=True, room='none'),
        dict(id='with_full_room_layout', peer_poses=True, playback_times=True, playback_text=True, room='layout')],
        receiver_views='Use every existing single-robot edge view and the one full-cloud view. Do not generate cloud receiver subsets.',
        keywords='public/test/keyword_variants.jsonl contains unique human utterance prefixes of 1/2/3 words. Use the intersection of sample IDs eligible at every compared length; target and full ASR reference stay unchanged. Load only the selected query into a model.',
        thresholds=dict(doa_deg=[5,10,20,30,45], distance_m=[.25,.5,1.,1.5,2.], world_m=[.25,.5,1.,1.5,2.]),
        acoustic_pairs='See private/ablation_groups.jsonl and public/test/physical_pairs.jsonl; one-factor and combined interventions are explicitly separated.',
        calibration='Removing peer poses only removes unobserved robot poses. Cloud always retains every supplied receiver pose needed for WORLD coordinates.')
