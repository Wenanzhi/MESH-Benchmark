"""Check shipped archive coverage, hashes and identity joins. Does not rescore."""
import collections
import gzip
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1] / 'demo/data'
    read = lambda name: json.loads((root / name).read_text())
    index, provenance, baselines = map(read, ['index.json', 'provenance.json', 'baselines.json'])
    models = {b['id'] for b in baselines}
    questions = {q['id']: (q, s) for s in index['scenes'] for q in s['questions']}
    assert len(questions) == 39999 and len(models) == 12
    assert len(index['scenes']) == 2400 and len(index['empty_questions']) == 800
    seen = set()
    output_counts = collections.Counter()
    output_questions = set()
    for path, expected in provenance['shard_sha256'].items():
        raw = (root / path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected, path
        for qid, record in json.loads(gzip.decompress(raw)).items():
            assert qid not in seen and qid in questions
            seen.add(qid)
            q, scene = questions[qid]
            assert (record['task'], record['scene']) == (q['task'], scene['id'])
            assert set(record['metrics']) == models
            assert set(record['outputs']) <= models
            assert len(record['receivers']) == (1 if q['setting'] == 'edge' else scene['receivers'])
            for metric in record['metrics'].values():
                assert 0 <= metric['case_score'] <= 1
                assert metric['case_wer'] is None or metric['case_wer'] >= 0
                assert metric['rule']
            for model, output in record['outputs'].items():
                score = output['scored']
                assert (score['sample_id'], score['episode_id'], score['task_id'], score['setting']) == (qid, scene['id'], q['task'], q['setting'])
                assert output['status'] == ('invalid' if not score['format_valid'] else 'valid_empty' if output['output'] == '' else 'available')
                assert 'manuscript/notes/' + output['source'] in provenance['source_sha256']
                output_counts[model] += 1
                output_questions.add(qid)
    assert seen == set(questions)
    assert output_questions == set(index['archived_examples'])
    assert sum(output_counts.values()) == provenance['output_records'] == 47
    assert len(output_questions) == provenance['output_questions'] == 24
    assert len(questions) * len(models) == provenance['metric_records'] == 479988
    for baseline in baselines:
        assert baseline['metric_records'] == 39999
        assert baseline['output_records'] == output_counts[baseline['id']]
        assert {r['split'] for r in baseline['archive_hashes']} == {'static', 'dynamic'}
    assert set(read('paper-results.json')) == models
    print('Verified: 39,999 question joins; 479,988 frozen scores; 47 outputs; every shard hash; 12 configurations.')


if __name__ == '__main__':
    main()
