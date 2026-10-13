"""Boundary checks for the released scoring and answer-processing contracts."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'postprocess'))
from postprocess_predictions import process_record, verify_frozen_files
from dynamic_demo.common import angular
from dynamic_dataset.frame_score import frame_map
from exhibition_v3.distance_metrics import RangeSummary
from exhibition_v3.score import one


class ContractTests(unittest.TestCase):
    def test_direction_wraparound(self):
        self.assertAlmostEqual(angular([179, 0], [-179, 0]), 2, places=10)

    def test_distance_uses_relative_error_and_full_denominator(self):
        scores = RangeSummary()
        scores.add([1, 10], [.2, 2])
        scores.add([3], [None])
        result = scores.finish()
        self.assertEqual(result['rel_acc_at_20_percent'], .5)
        self.assertEqual(result['coverage'], .5)
        self.assertAlmostEqual(result['mean_relative_error_percent'], 20)

    def test_all_missing_distance_has_no_error_mean(self):
        scores = RangeSummary()
        scores.add([2, 5], [None, None])
        result = scores.finish()
        self.assertEqual(result['rel_acc_at_20_percent'], 0)
        self.assertEqual(result['coverage'], 0)
        self.assertIsNone(result['mean_relative_error_percent'])

    def test_duplicate_trajectory_frames_are_rejected(self):
        output = {'frames': [dict(time_s=0, active=True, distance_m=2),
                             dict(time_s=0, active=True, distance_m=3)]}
        frames, valid = frame_map(output, [0, .5], 'distance_m', .5)
        self.assertFalse(valid)
        self.assertNotIn(0, frames)

    def test_refusal_is_not_an_empty_region_answer(self):
        values, _ = process_record(dict(sample_id='example', task_id='C2_REGION_ASR',
            raw_text="I cannot transcribe the audio because it was not provided."))
        self.assertIsNone(values['reviewed'])
        gold = dict(task_id='C2_REGION_ASR', output='')
        self.assertFalse(one(gold, values['reviewed'])['empty_correct'])
        self.assertTrue(one(gold, '')['empty_correct'])

    def test_claimed_repetitions_are_preserved(self):
        values, _ = process_record(dict(sample_id='example', task_id='SPATIAL_ASR',
                                       raw_text='Transcript: "go go go home"'))
        self.assertEqual(values['reviewed'], 'go go go home')

    def test_named_distance_is_unwrapped_without_changing_value(self):
        values, _ = process_record(dict(sample_id='example', task_id='TEXT_RANGE',
                                       raw_text='{"distance_m": 7.25}'))
        self.assertEqual(values['reviewed'], 7.25)

    def test_frozen_processing_sources_match(self):
        self.assertEqual(verify_frozen_files()['postprocess_version'], 'gold_blind_content_v1')


if __name__ == '__main__':
    unittest.main()
