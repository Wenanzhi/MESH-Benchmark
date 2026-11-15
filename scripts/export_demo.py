"""Export frozen records for the browser. Never invokes inference or scoring.

Inputs are explicit, immutable paper and listening-tool checkouts, plus the
published dataset. The exporter rejects unknown IDs, conflicting records and
question/reference mismatches. Only compact existing metrics enter the shards.
"""
from __future__ import annotations

import argparse
import ast
import collections
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path

DATA_REV = 'f7ca282fbb610206fe12336037c6cd0e587a7e55'
LISTEN_REV = 'c18bd9515a430a79673a0fb3d0f982d7f3135001'
MODELS = [
    ('qwen3_w_only', 'Qwen3-Omni', 'FOA-W'),
    ('qwen3_wxyz', 'Qwen3-Omni', 'FOA-sep'),
    ('qwen35_w_only', 'Qwen3.5-Omni-Plus', 'FOA-W'),
    ('qwen35_wxyz_mono', 'Qwen3.5-Omni-Plus', 'FOA-sep'),
    ('bat', 'BAT', 'Binaural'), ('midasheng', 'MiDasheng-Spatial', 'Binaural'),
    ('so7', 'Spatial-Omni-7B', 'FOA'), ('so30', 'Spatial-Omni-30B', 'FOA'),
    ('jaeger2', 'JAEGER Neural', 'FOA'),
    ('jaeger_classical_2', 'JAEGER Classical', 'FOA'),
    ('qwen38_flash', 'Qwen3.8-Omni-Flash', 'FOA'),
    ('agent_v2', 'MESH-agent', 'FOA'),
]
ALIASES = {'qwen35_wxyz': 'qwen35_wxyz_mono'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paper-repo', type=Path, required=True)
    parser.add_argument('--paper-revision', required=True)
    parser.add_argument('--listening-repo', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('demo/data'))
    args = parser.parse_args()
    source_hashes = {}

    def paper(path):
        data = subprocess.check_output(['git', '-C', str(args.paper_repo), 'show', args.paper_revision + ':' + path])
        source_hashes[path] = digest(data)
        return data

    def paper_json(path):
        return json.loads(paper('manuscript/notes/' + path))

    def frozen_listening(path):
        data = subprocess.check_output(['git', '-C', str(args.listening_repo), 'show', LISTEN_REV + ':web/' + path])
        return json.loads(data)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'shards').mkdir(exist_ok=True)
    catalog = frozen_listening('data/catalog.json')
    questions = {}
    scenes = {}
    public = {}
    public_inputs = {}
    dataset_hashes = {}
    asset_hashes = {}
    recordings = {}
    gold = {}
    for split in ['static', 'dynamic']:
        for relative in ['public/test/index.jsonl', 'public/test/inputs.jsonl', 'public/test/recordings.jsonl', 'private/test/gold.jsonl']:
            dataset_hashes[split + '/' + relative] = digest((args.dataset / split / relative).read_bytes())
        for line in (args.dataset / split / 'public/test/inputs.jsonl').read_text().splitlines():
            row = json.loads(line)
            assert row['sample_id'] not in public_inputs
            public_inputs[row['sample_id']] = row
        for line in (args.dataset / split / 'public/test/index.jsonl').read_text().splitlines():
            row = json.loads(line)
            assert row['sample_id'] not in public
            public[row['sample_id']] = row
        for line in (args.dataset / split / 'public/test/recordings.jsonl').read_text().splitlines():
            row = json.loads(line)
            recordings[row['recording_id']] = row
        for line in (args.dataset / split / 'private/test/gold.jsonl').read_text().splitlines():
            row = json.loads(line)
            gold[row['sample_id']] = row
    assert len(public) == len(gold) == 39999

    # Verify the pinned listening export against the actual task release.
    # File hashes prove the checkout files are the pinned public files without
    # issuing thousands of subprocesses.
    listing = subprocess.check_output(['git', '-C', str(args.listening_repo), 'ls-tree', '-r', LISTEN_REV, 'web/data']).decode()
    blobs = {line.split('\t', 1)[1]: line.split()[2] for line in listing.splitlines()}

    def read_export(path):
        data = (args.listening_repo / 'web' / path).read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        assert blob == blobs['web/' + path], path
        asset_hashes[path] = digest(data)
        return json.loads(data)

    for scene in catalog['scenes']:
        sid = scene['id']
        scenes[sid] = scene
        ref = read_export('data/references/' + sid + '.json')
        inp = read_export('data/scenes/' + sid + '.json')
        inputs = {q['id']: q for q in inp['questions']}
        for question in scene['questions']:
            qid = question['id']
            assert qid not in questions
            row = public[qid]
            assert (row['episode_id'], row['task_id'], row['setting'], row['mode']) == (
                sid, question['task'], question['setting'], scene['mode'])
            assert ref['questions'][qid]['output'] == gold[qid]['output'], qid
            assert ref['questions'][qid]['target_source_id'] == gold[qid]['target_source_id'], qid
            for key in ['query', 'receiver_ids', 'time_window_samples']:
                assert inputs[qid][key] == public_inputs[qid][key], (qid, key)
            for audio in inputs[qid]['audio']:
                r = recordings[audio['recording_id']]
                assert r['sha256'] == audio['sha256'] and r['episode_id'] == sid
                assert scene['mode'] + '/' + r['path'] == audio['path']
                assert audio['id'] == r['receiver_robot_id']
            assert inputs[qid]['receiver_ids'] == [a['id'] for a in inputs[qid]['audio']]
            questions[qid] = {'scene': sid, 'task': question['task'], 'setting': question['setting'],
                              'mode': scene['mode'], 'receivers': inputs[qid]['receiver_ids'],
                              'empty_reference': gold[qid]['output'] == ''}
    assert set(questions) == set(public)

    # Read task names as literal data, without executing paper-maintenance code.
    tree = ast.parse(paper('scripts/task_names.py'))
    constants = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
                 if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                 and n.targets[0].id in ['NAMES', 'FULL_NAMES', 'GROUPS']}
    tasks = {}
    for view, mode, ids in constants['GROUPS']:
        for task in ids:
            tasks[task] = {'code': constants['NAMES'][task][1], 'name': constants['FULL_NAMES'][task],
                           'view': view, 'mode': mode.lower()}

    model_ids = {m[0] for m in MODELS}
    metrics = collections.defaultdict(dict)
    metric_sources = {}
    metric_files = ['case_equal_overall_20261013/per_case_weighted_scores.jsonl.gz',
                    'agent_overall_d70a6d7/per_case_weighted_scores.jsonl.gz',
                    'qwen35_20261013/w_only_per_case_weighted_scores.jsonl.gz',
                    'qwen35_20261013/wxyz_mono_per_case_weighted_scores.jsonl.gz']
    for path in metric_files:
        for line in gzip.decompress(paper('manuscript/notes/' + path)).splitlines():
            row = json.loads(line)
            model = ALIASES.get(row['model'], row['model'])
            if model not in model_ids:
                continue
            qid = row['sample_id']
            q = questions[qid]
            assert row['task_id'] == q['task'] and row['split'] == q['mode']
            assert row['viewpoint'] == ('Ego' if q['setting'] == 'edge' else 'Global')
            assert model not in metrics[qid]
            # Exact archived values; no scorer or aggregate is run here.
            metrics[qid][model] = {'case_score': row['case_score'], 'case_wer': row['case_wer'], 'rule': row['rule']}
            metric_sources[model] = path
    assert all(set(metrics[qid]) == model_ids for qid in questions)

    outputs = collections.defaultdict(dict)

    def add_output(model, qid, output, raw, score, source, review=None):
        model = ALIASES.get(model, model)
        if model not in model_ids:
            return
        q = questions[qid]
        assert score['sample_id'] == qid and score['task_id'] == q['task']
        assert score['episode_id'] == q['scene'] and score['setting'] == q['setting']
        record = {'output': output, 'raw_text': raw, 'scored': score,
                  'source': source, 'review': review,
                  'status': 'invalid' if not score['format_valid'] else ('valid_empty' if output == '' else 'available')}
        if model in outputs[qid]:
            old = outputs[qid][model]
            assert old['output'] == output and old['scored'] == score, (qid, model)
            return
        outputs[qid][model] = record

    for path in ['appendix_evidence_20261013/shared_case_outputs.json', 'qwen35_20261013/shared_case_outputs.json']:
        for row in paper_json(path):
            review = row.get('review', {})
            add_output(row['model'], row['sample_id'], row['prediction']['output'], review.get('raw_text'),
                       row['scored'], path, review)
    for path, default_model in [('qwen35_20261013/case_studies.json', None),
                                ('new_models_20261013/qwen38_case_studies.json', 'qwen38_flash')]:
        for row in paper_json(path):
            model = default_model or ('qwen35_w_only' if row['condition'] == 'w_only' else 'qwen35_wxyz_mono')
            add_output(model, row['sample_id'], row['reviewed_output'], row.get('raw_text'),
                       row.get('scored', row.get('score')), path)
    path = 'new_models_20261013/classical_case_examples.json'
    for qid, row in paper_json(path).items():
        add_output('jaeger_classical_2', qid, row['reviewed_output'], row['worker_record'].get('raw_text'), row['scored'], path)

    sources = []
    for path in ['case_equal_overall_20261013/sources.json', 'case_equal_overall_20261013/extra_sources.json',
                 'qwen35_20261013/sources.json']:
        sources += paper_json(path)
    baselines = []
    inference = paper_json('appendix_evidence_20261013/inference_configs.json')
    agent_freeze = paper_json('agent_v2_score4/prediction_freeze.json')
    agent_scores = paper_json('agent_overall_d70a6d7/overall_complete.json')
    agent_model = paper_json('agent_v2_score4/model_manifest.json')
    for model, name, audio in MODELS:
        archived = [row for row in sources if ALIASES.get(row.get('model'), row.get('model')) == model]
        archive_hashes = [{k: row[k] for k in ['split', 'scored_sha256', 'reviewed_predictions_sha256', 'asr_audit_sha256'] if k in row}
                          for row in archived]
        archive_hashes = list({encode(row): row for row in archive_hashes}.values())
        if model == 'agent_v2':
            archive_hashes = [{'split': split, 'predictions_sha256': agent_freeze['by_mode'][split]['sha256'],
                               'scored_sha256': agent_scores['sources'][split]['scores_sha256']}
                              for split in ['static', 'dynamic']]
        config = inference.get(model)
        config_public = {k: v for k, v in (config or {}).items()
                         if k in ['dataset_revision', 'system_prompt', 'max_new_tokens', 'input_mode', 'engine_kwargs', 'model', 'input_model']}
        if model == 'agent_v2':
            config_public = {'model': agent_model['repo'], 'model_revision': agent_model['revision'],
                             'run': 'disrobot_exhibition_full_v2_20261009', 'policy': 'frozen Agent V2'}
        baselines.append({'id': model, 'name': name, 'input': audio,
                          'information_condition': 'Egocentric: focal receiver + peer metadata; Allocentric: all receivers + metadata.',
                          'metric_source': metric_sources[model], 'metric_records': 39999,
                          'output_records': sum(model in d for d in outputs.values()),
                          'scorer': 'dish_exhibition_v3.score.4',
                          'postprocessing': 'frozen Agent V2 structured outputs' if model == 'agent_v2' else 'gold_blind_content_v1',
                          'inference_config': config_public or None,
                          'inference_config_note': 'Only archived configuration fields are shown; absent fields are unknown, not defaults. Inference and scoring revisions are recorded separately.',
                          'archive_hashes': archive_hashes})

    shard_hashes = {}
    shards = collections.defaultdict(dict)
    for qid, q in questions.items():
        shards[qid[:2]][qid] = {'task': q['task'], 'scene': q['scene'], 'receivers': q['receivers'],
                               'metrics': metrics[qid], 'outputs': outputs.get(qid, {})}
    for prefix, records in sorted(shards.items()):
        payload = gzip.compress(encode(records), mtime=0)
        filename = 'shards/' + prefix + '.json.gz'
        (args.output / filename).write_bytes(payload)
        shard_hashes[filename] = digest(payload)

    # Default examples use data attributes and lexical IDs only, never scores.
    ordered = sorted(questions)
    defaults = []
    criteria = [('Static scene', lambda q: q['mode'] == 'static' and not q['empty_reference']),
                ('Moving sources', lambda q: q['task'] == 'TEXT_TRAJECTORY'),
                ('Multiple receivers', lambda q: q['setting'] == 'cloud' and len(q['receivers']) > 1),
                ('Empty region', lambda q: q['empty_reference'])]
    for label, criterion in criteria:
        defaults.append({'label': label, 'question': next(qid for qid in ordered if criterion(questions[qid]))})
    index = {'version': 'mesh-demo-data-v1', 'dataset_revision': DATA_REV, 'counts': catalog['counts'],
             'scenes': catalog['scenes'], 'tasks': tasks, 'defaults': defaults,
             'archived_examples': sorted(outputs),
             'empty_questions': sorted(q for q in questions if questions[q]['empty_reference'])}

    # The published aggregate table is transcribed from its frozen TeX cells.
    table_rows = {}
    table_task_ids = {'egocentric_results': ['DOA', 'RANGE', 'TEXT_DOA', 'TEXT_RANGE', 'DOA_RANGE_ASR', 'DOA_TRAJECTORY', 'RANGE_TRAJECTORY', 'SPATIAL_ASR'],
                      'global_results': ['C1_SETLOC', 'C3_TEXTLOC', 'C2_REGION_ASR', 'TEXT_TRAJECTORY', 'WORLD_TRAJECTORY_ASR']}
    for file, ids in table_task_ids.items():
        for line in paper('manuscript/tables/' + file + '.tex').decode().splitlines():
            cells = [re.sub(r'\\textbf\{([^}]+)\}', r'\1', cell.strip()) for cell in line.split('&')]
            for model, name, audio in MODELS:
                if len(cells) == len(ids) + 3 and cells[:2] == [name, audio]:
                    nums = [float(re.sub(r'\\.*$', '', c).strip()) for c in cells[2:]]
                    dest = table_rows.setdefault(model, {})
                    dest.update(dict(zip(ids, nums[:-1])))
                    dest['egocentric_overall' if file == 'egocentric_results' else 'allocentric_overall'] = nums[-1]
    assert set(table_rows) == model_ids and all(len(row) == 15 for row in table_rows.values())
    provenance = {'dataset': 'Heiheihaha17/MESH-Benchmark', 'dataset_revision': DATA_REV,
                  'task_protocol': 'dish_exhibition_v3.tasks.3', 'scorer': 'dish_exhibition_v3.score.4',
                  'overall': 'dish_case_equal_two_objectives_v1', 'postprocessing': 'gold_blind_content_v1',
                  'paper_revision': args.paper_revision, 'paper': 'https://arxiv.org/abs/2611.16787v1',
                  'listening_export_revision': LISTEN_REV, 'listening_dataset_revision': catalog['revision'],
                  'scene_asset_base': 'https://raw.githubusercontent.com/Wenanzhi/dish-listening-review/' + LISTEN_REV + '/web/',
                  'audio_base': 'https://huggingface.co/datasets/Heiheihaha17/MESH-Benchmark/resolve/' + DATA_REV + '/',
                  'metric_records': len(questions) * len(MODELS),
                  'output_records': sum(len(d) for d in outputs.values()), 'output_questions': len(outputs),
                  'availability_note': 'Full per-question metrics are archived for every published configuration. Raw/reviewed outputs are available only for the listed diagnostic records. Missing output records are not unrun experiments or zero scores.',
                  'default_selection': 'Lexically first eligible question by dataset-only conditions; no score-dependent selection.',
                  'diagnostic_selection': 'Archived paper case studies; these are selected examples, not a representative sample.',
                  'source_sha256': source_hashes, 'shard_sha256': shard_hashes,
                  'dataset_file_sha256': dataset_hashes, 'scene_asset_sha256': asset_hashes,
                  'joins_verified': {'questions': len(questions), 'references': len(gold), 'recordings': len(recordings), 'all_model_metrics': True},
                  'new_inference': False, 'new_scoring': False}
    for name, value in [('index.json', index), ('baselines.json', baselines), ('provenance.json', provenance), ('paper-results.json', table_rows)]:
        (args.output / name).write_bytes(encode(value))
    print(json.dumps({k: provenance[k] for k in ['metric_records', 'output_records', 'output_questions', 'joins_verified']}, indent=2))


if __name__ == '__main__':
    main()
