# MESH-Bench evaluation

Review distribution of the evaluation tools for distributed spatial speech understanding. The dataset is distributed separately. This repository contains no recordings, reference transcripts, model checkpoints, generation pipeline, or experimental prediction files.

Use Python 3.12 and install from this repository:

```bash
python -m pip install -e .
```

The dataset directory must contain `static/` and `dynamic/`. Preserve the released files and relative paths. The frozen protocol identifiers remain unchanged for compatibility: `dish_exhibition_v3.tasks.3` and `dish_exhibition_v3.score.4`.

## Model inputs

```python
from exhibition_v3.loader import Dataset

dataset = Dataset("/path/to/dataset/static")
sample = dataset.load(dataset.ids()[0])
# Supply sample["audio"], sample["prompt"], and the permitted public context.
# Each audio array has shape [samples, 4], in ACN/SN3D [W, Y, Z, X] order.
```

Use `dynamic` for dynamic tasks and `audio=False` when inspecting prompts. Edge questions receive one robot's recording; cloud questions receive all robots' synchronized recordings as separate inputs. Do not downmix FOA silently, concatenate receivers along time, or expose `private/` labels and sibling-question answers to the model. Dynamic spatial labels use a 0.5 s grid.

The loader supports the released input-context variants, including removal of peer poses and playback information, and validated `cue_variant` queries. Compare only their common eligible sample IDs. See the dataset's `public/ablation_recipes.json` and `public/test/spatial_query_variants.jsonl`.

## Fixed response processing

Save raw responses as JSONL with `sample_id`, `task_id`, and string `raw_text`. The task ID comes from the public index, not from a reference answer. Never turn a failed request or null output into an empty string.

```bash
python postprocess/postprocess_predictions.py --predictions raw_static.jsonl --output-dir processed/static
python postprocess/postprocess_predictions.py --predictions raw_dynamic.jsonl --output-dir processed/dynamic
```

Both output directories must be new. The driver produces `raw_predictions.jsonl`, `baseline_predictions.jsonl`, `reviewed_predictions.jsonl`, a per-question audit, and a completion receipt. The published comparison uses the reviewed predictions. It applies deterministic syntax/schema conversion and gold-blind extraction of explicitly asserted transcript text. It never estimates missing coordinates, selects content using gold, retranscribes audio, or removes repetitions from a claimed transcript. A refusal is not a correct empty-region answer.

The optional `manual_asr_overrides.json` is a hash-checked extraction for a named historical response. It is not applied by default and must not be transferred to a new model run. See [the processing policy](postprocess/asr_review_policy.json). The old source-machine batch runner is omitted; the extraction functions and patterns are preserved.

## Official task scoring

```bash
python -m exhibition_v3.score --root /path/to/dataset/static --predictions processed/static/reviewed_predictions.jsonl --output scores/static
python -m exhibition_v3.score --root /path/to/dataset/dynamic --predictions processed/dynamic/reviewed_predictions.jsonl --output scores/dynamic
```

Predictions have `sample_id` and `output`. The scorer writes `metrics.json` and `per_sample.jsonl.gz`, retaining the full reference population. Missing and invalid predictions reduce accuracy and coverage; error means over covered predictions do not replace success rates.

| Setting | Tasks | Main task metrics |
|---|---|---|
| Static edge | DOA, TEXT_DOA; RANGE, TEXT_RANGE; DOA_RANGE_ASR | Acc@20°; RelAcc@20%; corpus WER |
| Static cloud | C1_SETLOC, C3_TEXTLOC; C2_REGION_ASR | Acc@2 m; corpus WER and separate empty-region accuracy |
| Dynamic edge | DOA_TRAJECTORY; RANGE_TRAJECTORY; SPATIAL_ASR | Acc@20°; RelAcc@20%; corpus WER |
| Dynamic cloud | TEXT_TRAJECTORY; WORLD_TRAJECTORY_ASR | Acc@2 m; corpus WER |

Relative distance error is `abs(prediction - truth) / truth`. Distance accuracy averages within each trajectory first and then across questions. Dynamic spatial tasks score target-active frames; DOA identity assignment is fixed for the whole clip. Coordinate conventions, additional thresholds, and empty-target rules are documented in each split's `public/evaluation_protocol.json`. There are no KW-ASR questions in this release.

## Overall scores

```bash
python overall/overall_score.py --model my_model --static scores/static/per_sample.jsonl.gz --dynamic scores/dynamic/per_sample.jsonl.gz --static-index /path/to/dataset/static/public/test/index.jsonl --dynamic-index /path/to/dataset/dynamic/public/test/index.jsonl --output-dir scores/overall
```

This uses the current `dish_case_equal_two_objectives_v1` protocol. Ego and Global are reported separately. Within each perspective, localization and semantic scores each receive 50% weight. Within each objective, every question has equal weight across static/dynamic settings and tasks:

- Localization: the mean fraction of successful reference targets or active frames within each question, then the mean across questions.
- Semantic: `max(0, 1 - edits/reference_words)` for each nonempty-reference question; official empty-answer correctness for each empty-region question.
- Overall: `100 * (0.5 * localization_mean + 0.5 * semantic_mean)`.

Thus Overall is not reconstructed from corpus WER or from equally weighted task/setting averages. The aggregator requires all 39,999 scored questions, checks their public IDs, and keeps all 800 empty-region negatives. It outputs perspective, task, and split tables, per-case weights, and a completion receipt. Raw corpus WER remains available in the official task metrics.

## Verification

```bash
python -m unittest discover -s overall -p "test_*.py" -v
python -m unittest discover -s tests -p "test_*.py" -v
```

The review package preserves the scoring functions and prompt behavior while removing generation dependencies and project-owner/source-machine information. `validation.json` records packaging and equivalence checks. Neither successful scoring nor an Overall value establishes that a model's audio adapter or inference configuration was correct.
