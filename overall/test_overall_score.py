"""Regression tests for choices that change the benchmark's weighting."""
import copy
import unittest

from overall_score import case_score, summarize


def semantic(edits, words=10, negative=False, empty_correct=False, valid=True):
    return dict(task_id="C2_REGION_ASR", reference_words=words, edits=edits,
                negative=negative, empty_correct=empty_correct, format_valid=valid)


def spatial(task, errors, valid=True):
    return dict(task_id=task, errors=errors, relative_errors=errors,
                total=len(errors), format_valid=valid)


def case(view, objective, split, score, negative=False):
    return dict(viewpoint=view, objective=objective, split=split, case_score=score,
                task_id=objective, negative=negative)


class ScoringTests(unittest.TestCase):
    def test_semantic_clipping_is_per_question(self):
        values = [case_score(semantic(0))[0], case_score(semantic(20))[0]]
        self.assertEqual(sum(values) / 2, 0.5)
        # Clipping the aggregate WER instead would incorrectly give zero.
        self.assertEqual(max(0, 1 - (0 + 20) / (10 + 10)), 0)

    def test_negative_empty_answer_is_not_missing_output(self):
        good = semantic(0, words=0, negative=True, empty_correct=True)
        missing = semantic(0, words=0, negative=True, valid=False)
        self.assertEqual(case_score(good)[0], 1)
        self.assertEqual(case_score(missing)[0], 0)
        with self.assertRaises(ValueError):
            case_score(dict(good, format_valid=False))

    def test_missing_targets_and_partial_format_failure(self):
        for task, errors in [("DOA", [20, None, 21]),
                             ("C1_SETLOC", [2, None, 3]),
                             ("RANGE", [0.2, None, 0.21])]:
            self.assertEqual(case_score(spatial(task, errors, valid=False))[0], 1 / 3)
        self.assertEqual(case_score(spatial("DOA", [None, None], valid=False))[0], 0)

    def test_targets_do_not_change_question_weight(self):
        values = [case_score(spatial("DOA", [0]))[0],
                  case_score(spatial("DOA", [None, None, None]))[0]]
        self.assertEqual(sum(values) / len(values), 0.5)  # Not target-pooled 1/4.

    def test_relative_distance_boundary_only(self):
        self.assertEqual(case_score(spatial("RANGE_TRAJECTORY", [0.2 + 5e-13]))[0], 1)
        self.assertEqual(case_score(spatial("RANGE", [0.2 + 2e-12]))[0], 0)
        self.assertEqual(case_score(spatial("DOA", [20 + 5e-13]))[0], 0)
        self.assertEqual(case_score(spatial("TEXT_TRAJECTORY", [2 + 5e-13]))[0], 0)

    def test_invalid_errors_are_rejected(self):
        for error in [float("nan"), float("inf"), -1, "0", True]:
            with self.assertRaises(ValueError):
                case_score(spatial("DOA", [error]))
        with self.assertRaises(ValueError):
            case_score(dict(spatial("DOA", [0]), total=2))

    def test_split_sample_weights_and_objective_weights(self):
        cases = []
        for view in ("Ego", "Global"):
            cases += [case(view, "localization", "static", 1)]
            cases += [case(view, "localization", "dynamic", 0) for _ in range(3)]
            cases += [case(view, "semantic", "static", 1),
                      case(view, "semantic", "dynamic", 1)]
        original = copy.deepcopy(cases)
        scores, _, _ = summarize(cases, "example")
        for row in scores:
            self.assertEqual(row["localization_pct"], 25)  # Not split-equal 50.
            self.assertEqual(row["semantic_pct"], 100)
            self.assertEqual(row["total_pct"], 62.5)  # Not all-case mean 50.
            subset = [c for c in cases if c["viewpoint"] == row["viewpoint"]]
            self.assertEqual(sum(c["overall_weight"] for c in subset), 1)
            self.assertEqual(sum(c["contribution_points"] for c in subset), 62.5)
        reversed_scores, _, _ = summarize(list(reversed(original)), "example")
        self.assertEqual(scores, reversed_scores)


if __name__ == "__main__":
    unittest.main()
