#!/usr/bin/env python3
"""Aggregate official exhibition-v3 score.4 records, with equal case weights.

Python 3.10+, standard library only. Read per-sample scores, never raw answers
or private labels. See ../README.md for the frozen population and semantics.
"""
import argparse
import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

PROTOCOL = "dish_case_equal_two_objectives_v1"
SCORING_REVISION = "dish_exhibition_v3.score.4"
# task: (split, setting, objective, full test inventory)
TASKS = {
    "DOA": ("static", "edge", "localization", 1587),
    "RANGE": ("static", "edge", "localization", 3182),
    "TEXT_DOA": ("static", "edge", "localization", 3182),
    "TEXT_RANGE": ("static", "edge", "localization", 3182),
    "DOA_RANGE_ASR": ("static", "edge", "semantic", 3182),
    "C1_SETLOC": ("static", "cloud", "localization", 800),
    "C3_TEXTLOC": ("static", "cloud", "localization", 1601),
    "C2_REGION_ASR": ("static", "cloud", "semantic", 2401),
    "DOA_TRAJECTORY": ("dynamic", "edge", "localization", 3174),
    "RANGE_TRAJECTORY": ("dynamic", "edge", "localization", 6364),
    "SPATIAL_ASR": ("dynamic", "edge", "semantic", 4940),
    "TEXT_TRAJECTORY": ("dynamic", "cloud", "localization", 3202),
    "WORLD_TRAJECTORY_ASR": ("dynamic", "cloud", "semantic", 3202),
}
ANGLE = {"DOA", "TEXT_DOA", "DOA_TRAJECTORY"}
DISTANCE = {"RANGE", "TEXT_RANGE", "RANGE_TRAJECTORY"}
VIEWPOINTS = {"edge": "Ego", "cloud": "Global"}
SPLITS = ("static", "dynamic")
OBJECTIVES = ("localization", "semantic")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def jsonl(path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"{path}:{number}: blank record")
            row = json.loads(line)
            require(isinstance(row, dict), f"{path}:{number}: expected object")
            yield row


def integer(value, name):
    require(type(value) is int and value >= 0, f"{name}: expected nonnegative integer")
    return value


def case_score(row):
    """Return (0..1 score, scoring rule, positive-case WER or None)."""
    task = row["task_id"]
    require(task in TASKS, f"Unknown task: {task}")
    require(type(row["format_valid"]) is bool, "format_valid must be a boolean")
    if TASKS[task][2] == "semantic":
        words = integer(row["reference_words"], "reference_words")
        edits = integer(row["edits"], "edits")
        require(type(row["negative"]) is bool, "negative must be a boolean")
        if words:
            require(not row["negative"], "Positive reference marked negative")
            wer = edits / words
            return max(0.0, 1.0 - wer), "clipped_case_wer", wer
        require(row["negative"], "Zero-word reference must be marked negative")
        require(type(row["empty_correct"]) is bool, "empty_correct must be a boolean")
        require(not row["empty_correct"] or row["format_valid"],
                "An invalid response cannot be a correct empty answer")
        return float(row["empty_correct"]), "official_negative_empty_accuracy", None

    distance = task in DISTANCE
    errors = row["relative_errors"] if distance else row["errors"]
    total = integer(row["total"], "total")
    require(isinstance(errors, list) and total > 0 and len(errors) == total,
            "Localization errors must retain all reference targets/frames")
    threshold = 0.2 if distance else 20.0 if task in ANGLE else 2.0
    successes = 0
    for error in errors:
        # Unmatched targets/frames remain failures in the denominator.
        if error is None:
            continue
        require(type(error) in (float, int) and math.isfinite(error) and error >= 0,
                f"Invalid localization error: {error!r}")
        successes += error <= threshold or (
            distance and math.isclose(error, threshold, rel_tol=0.0, abs_tol=1e-12)
        )
    # Official matched successes survive partial format failures.
    return successes / total, "within_case_accuracy", None


def load_cases(score_paths, index_paths):
    """Validate the full public inventory and return one scored row per question."""
    cases = []
    for split in SPLITS:
        inventory = {}
        counts = Counter()
        for row in jsonl(index_paths[split]):
            sid = row["sample_id"]
            require(isinstance(sid, str) and sid, "Invalid sample_id")
            require(sid not in inventory, f"Duplicate index ID: {split}/{sid}")
            task = row["task_id"]
            require(task in TASKS, f"Unknown index task: {task}")
            expected_split, setting, _, _ = TASKS[task]
            require(expected_split == split and row["setting"] == setting
                    and row["mode"] == split, f"Index task/setting/mode mismatch: {sid}")
            inventory[sid] = row
            counts[task] += 1
        expected = Counter({t: spec[3] for t, spec in TASKS.items() if spec[0] == split})
        require(counts == expected,
                f"{split}: expected full frozen task counts {dict(expected)}, got {dict(counts)}")
        seen = set()
        negatives = 0
        for row in jsonl(score_paths[split]):
            sid = row["sample_id"]
            require(sid in inventory, f"Unknown scored ID: {split}/{sid}")
            require(sid not in seen, f"Duplicate scored ID: {split}/{sid}")
            seen.add(sid)
            for field in ("task_id", "setting", "episode_id", "scene_id"):
                require(row[field] == inventory[sid][field], f"{split}/{sid}: {field} mismatch")
            task = row["task_id"]
            score, rule, wer = case_score(row)
            negative = TASKS[task][2] == "semantic" and row["negative"]
            if negative:
                require(task == "C2_REGION_ASR", f"Unexpected empty-reference task: {task}")
                negatives += 1
            cases.append(dict(split=split, sample_id=sid, task_id=task,
                              viewpoint=VIEWPOINTS[row["setting"]], objective=TASKS[task][2],
                              case_score=score, rule=rule, case_wer=wer,
                              negative=bool(negative)))
        missing = set(inventory) - seen
        require(not missing, f"{split}: missing {len(missing)} scored samples; "
                "run the official scorer over the full index; do not drop failures")
        require(negatives == (800 if split == "static" else 0),
                f"{split}: unexpected empty-reference population: {negatives}")
    return cases


def mean(values):
    return math.fsum(values) / len(values)


def summarize(cases, model):
    """Pool static/dynamic questions inside each objective; weight objectives 50:50.

    load_cases must validate the formal population before this is published.
    This helper also permits small examples for testing the aggregation math.
    """
    groups, tasks, splits = defaultdict(list), defaultdict(list), defaultdict(list)
    positives, negatives = defaultdict(list), defaultdict(list)
    for row in cases:
        view, dim, score = row["viewpoint"], row["objective"], row["case_score"]
        groups[view, dim].append(score)
        tasks[view, row["split"], row["task_id"]].append(score)
        splits[view, row["split"], dim].append(score)
        if dim == "semantic":
            (negatives if row["negative"] else positives)[view].append(score)
    scores = []
    for view in VIEWPOINTS.values():
        loc, sem = (groups[view, dim] for dim in OBJECTIVES)
        require(loc and sem, f"{view}: both objectives are required")
        loc_pct, sem_pct = 100 * mean(loc), 100 * mean(sem)
        scores.append(dict(model=model, viewpoint=view, localization_pct=loc_pct,
                           semantic_pct=sem_pct, total_pct=0.5 * loc_pct + 0.5 * sem_pct,
                           localization_cases=len(loc), semantic_cases=len(sem),
                           positive_semantic_pct=100 * mean(positives[view]) if positives[view] else None,
                           negative_cases=len(negatives[view]),
                           negative_empty_accuracy_pct=100 * mean(negatives[view]) if negatives[view] else None))
    task_scores = [dict(model=model, viewpoint=v, split=s, task=t, cases=len(xs),
                        case_equal_score_pct=100 * mean(xs))
                   for (v, s, t), xs in sorted(tasks.items())]
    split_scores = [dict(model=model, viewpoint=v, split=s, objective=d,
                         cases=len(xs), score_pct=100 * mean(xs))
                    for (v, s, d), xs in sorted(splits.items())]
    for row in cases:
        count = len(groups[row["viewpoint"], row["objective"]])
        weight = 0.5 / count
        row.update(model=model, overall_weight=weight,
                   contribution_points=100 * 0.5 * row["case_score"] / count)
    return scores, task_scores, split_scores


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static", type=Path, required=True, help="Official static per_sample.jsonl[.gz]")
    parser.add_argument("--dynamic", type=Path, required=True, help="Official dynamic per_sample.jsonl[.gz]")
    parser.add_argument("--static-index", type=Path, required=True, help="Static public/test/index.jsonl")
    parser.add_argument("--dynamic-index", type=Path, required=True, help="Dynamic public/test/index.jsonl")
    parser.add_argument("--model", required=True, help="Model/input-configuration label for these two runs")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; never overwrite a run")
    args = parser.parse_args()
    try:
        require(not args.output_dir.exists(), "Output directory already exists")
        paths = {s: getattr(args, s) for s in SPLITS}
        indexes = {s: getattr(args, s + "_index") for s in SPLITS}
        sources = {s: {"scores_file": paths[s].name, "scores_sha256": sha256(paths[s]),
                       "index_file": indexes[s].name, "index_sha256": sha256(indexes[s])}
                   for s in SPLITS}
        cases = load_cases(paths, indexes)
        scores, task_scores, split_scores = summarize(cases, args.model)
        for s in SPLITS:
            require(sha256(paths[s]) == sources[s]["scores_sha256"]
                    and sha256(indexes[s]) == sources[s]["index_sha256"],
                    "Input changed during aggregation; freeze the score artifacts first")
        args.output_dir.mkdir(parents=True, exist_ok=False)
        for name, rows in (("scores.csv", scores), ("task_scores.csv", task_scores),
                           ("split_scores.csv", split_scores)):
            write_csv(args.output_dir / name, rows)
        with gzip.open(args.output_dir / "per_case_weighted_scores.jsonl.gz", "wt", encoding="utf-8") as handle:
            for row in cases:
                handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        result = dict(protocol=PROTOCOL, scoring_revision=SCORING_REVISION,
                      formula="100 * (0.5 * mean(localization_cases) + 0.5 * mean(semantic_cases))",
                      split_weight="Pool static and dynamic samples within each objective",
                      localization="Within-question accuracy: direction 20 deg, relative range 20%, world position 2 m",
                      semantic_positive="max(0, 1 - edits/reference_words) per sample before averaging",
                      semantic_negative="Official empty_correct (0 or 1), including all 800 negative cases",
                      model=args.model, case_rows=len(cases), sources=sources, scores=scores,
                      code_sha256=sha256(__file__), population_validated=True,
                      input_protocol_validated=False,
                      note="Aggregation verifies score records and coverage, not inference inputs, model weights or upstream postprocessing.")
        # Completion marker is written last; CSV files alone do not signal success.
        (args.output_dir / "overall_complete.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"output_dir": str(args.output_dir), "scores": scores}, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"Overall scoring failed: {exc}\n")


if __name__ == "__main__":
    main()
