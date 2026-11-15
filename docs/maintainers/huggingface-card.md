---
language:
- en
license: other
license_name: component-specific-licenses
license_link: https://huggingface.co/datasets/Heiheihaha17/MESH-Benchmark/blob/main/LICENSES.md
tags:
- spatial-audio
- ambisonics
- multi-robot
- benchmark
size_categories:
- 10K<n<100K
configs:
- config_name: static
  default: true
  data_files:
  - split: test
    path: static/model_index.jsonl
- config_name: dynamic
  data_files:
  - split: test
    path: dynamic/model_index.jsonl
---

# MESH-Benchmark

**MESH: Multi-receiver Evaluation of Spatial Hearing across Egocentric and Allocentric Views**

[Paper](https://arxiv.org/abs/2611.16787) · [Code and evaluation](https://github.com/Wenanzhi/MESH-Benchmark) · [Data and baseline explorer](https://wenanzhi.github.io/MESH-Benchmark/)

MESH evaluates whether a system can associate speech content with source position across receiving perspectives and maintain that association under motion. The explorer compares frozen per-question scores for all published configurations; original output coverage is disclosed there.

100 exhibition rooms, 800 fixed base scenes, 800 static and 1,600 dynamic physical
samples. Each base fixes speech identities/content, noise, initial positions,
duration and static-anchor SNR; two motion variants are drawn independently.
Every sample has one egocentric view per receiver and one allocentric view using **all** robots.
Receiver views and questions do not count as additional physical scenes.
Task protocol: **dish_exhibition_v3.tasks.3**. Released JSON retains the legacy setting keys `edge` and `cloud` for compatibility. This revision reuses the accepted audio.

| Split | Physical samples | FOA recordings | Questions |
|---|---:|---:|---:|
| static | 800 | 1587 | 19117 |
| dynamic | 1600 | 3174 | 20882 |

There are 299 human identities. 95% of base scenes
include environmental noise. Audio is 16 kHz float32 four-channel ACN/SN3D
**[W,Y,Z,X]**; preserve all four channels. RIR source/receiver knots are 0.2 s;
dynamic spatial outputs are 0.5 s. Motion arclength is 1.5–5 m, horizontal with
fixed height/yaw. The browser explorer provides FOA-to-binaural playback separately; the released recordings remain FOA.

## Download and evaluate

```python
from huggingface_hub import snapshot_download
root = snapshot_download("Heiheihaha17/MESH-Benchmark", repo_type="dataset", revision="f7ca282fbb610206fe12336037c6cd0e587a7e55", local_dir="mesh-benchmark")
```

The Hub viewer and `datasets.load_dataset(..., "static")` / `"dynamic"` use
uniform `model_index.jsonl` rows. These expose prompts and relative audio paths;
they do not decode or downmix FOA and contain no gold answers.

Use Python 3.12 and `pip install -r mesh-benchmark/requirements-eval.txt`. From `mesh-benchmark`:

```bash
PYTHONPATH=code python -m exhibition_v3.score --root static --predictions predictions.jsonl --output scores/static
PYTHONPATH=code python -m exhibition_v3.score --root dynamic --predictions dynamic_predictions.jsonl --output scores/dynamic
```

Predictions are JSONL objects with `sample_id` and `output`. Formal prompt templates,
pre-rendered prompts, the blind loader and scoring implementations are included.
`exhibition_v3.loader.Dataset(root / "static")` loads individual model inputs;
use `dynamic` for dynamic questions. The evaluation dependencies do not require Habitat.

- Static egocentric: DOA, RANGE, TEXT_DOA, TEXT_RANGE, DOA_RANGE_ASR.
- Static allocentric: C1_SETLOC, C2_REGION_ASR, C3_TEXTLOC.
- Dynamic egocentric: DOA_TRAJECTORY, RANGE_TRAJECTORY, SPATIAL_ASR.
- Dynamic allocentric: TEXT_TRAJECTORY, WORLD_TRAJECTORY_ASR.
- TEXT_RANGE pairs with static TEXT_DOA using the same transcript, target and receiver.
- DOA_RANGE_ASR selects a human jointly by direction and distance.
- Egocentric SPATIAL_ASR selects the same human using two speech-active 0.5 s grid anchors
  at least 1 s apart: changing azimuth, changing distance, or both. Direction
  cues use circular angle differences, including wraparound at -180/+180 degrees.
  Cues are rechecked after integer-degree / 0.1 m rounding, with explicit tolerances
  and safety margins. Transcribe the target's **entire input speech**, not just
  the interval between anchors. All angles/distances belong to the supplied
  recording's receiving microphone; no other robot is designated as a reference.
- Allocentric WORLD_TRAJECTORY_ASR selects a human using a WORLD [x,y,z] trajectory
  every 0.5 s, rounded to 0.1 m with an explicit Euclidean tolerance and 0.2 m
  boundary margin. Positions include silent periods without activity labels.
  Stationary humans have constant trajectories and are reported separately.
  Each human has only one allocentric ASR question per physical episode, receiving all
  robot recordings. It shares the target and whole transcript with egocentric ASR,
  but the spatial cues differ; this is not an identical-query receiver ablation.
- No keyword ASR questions are included in this task revision. Empty-region
  C2_REGION_ASR negatives remain and require an empty string.
- Dynamic DOA is absolute; spatial scoring excludes the target's silent frames.

## Files and correspondence

`static/` and `dynamic/` contain `public/audio/test`, `public/test` (inputs, prompts,
episodes, recordings, views, pairs, physical_pairs, spatial cue variants and index),
and `private/test` (gold answers, full metadata and excluded ambiguous queries).
The directory name `private` is an evaluation separation, **not access control**:
these files are published for scoring and must never be sent to the model.
Join by `base_scene_id`, `episode_id`, `view_id`, `query_group_id` and
`base_target_group_id` as appropriate. Allocentric audio bindings contain all robots.

## Reproduction

`reproduction_inputs.tar.gz` contains the frozen room assets, all 800 plans,
selected original speech/noise recordings, source catalogs and environment provenance.
`acoustic_audits.tar.gz` contains per-base gain/SNR checks and RIR metadata/hashes.
Neither archive contains machine credentials, operational logs, pilot outputs or
temporary RIR arrays. Extract archives into a separate replay directory.
The acoustic-audit reports describe the published output: keep them in a reference
directory rather than using them as completion records in an empty replay directory.

The code in `code/exhibition_v3/README.zh.md` documents the complete pipeline.
Build the native environment using `code/dynamic_demo/Dockerfile` (build context
`code/`), then run `exhibition_v3.render` on the extracted frozen plans. On a
standalone reproduction machine set `DISH_ALLOW_LOCAL_RENDER=1`. The Dockerfile
pins Habitat/RLR and the source-position patch; install the recorded generation
versions from `private/runtime_versions.json` before reproducing the release.
For one base: `python -m exhibition_v3.render --root REPLAY --gpu 0 --shard 0
--shards 800 --cache-root /tmp/dish-replay`. Use the same renderer and seed, then
`exhibition_v3.normalize.normalize_base(Path("REPLAY"), 0)` for the shared peak
normalization. For the full dataset run all shards and `exhibition_v3.finish`.

The native acoustic backend primarily uses CPU; GPU was used for speech alignment.
Two-time RIR interpolation is a quasi-static propagation approximation, not exact
Doppler simulation. Real environmental clips may contain their original reverberation;
speech absence was screened automatically, not certified by human listening.

## Evaluation and limitations

`acceptance.json` records full dataset validation; `upload.verification.json`
records the verified Hub revision and file hashes. Validation covers rendered
audio integrity, correspondence, labels, prompts, oracle scoring and rejection of
missing predictions; it is not baseline model inference or human listening.
Resample statistical uncertainty by room and base scene. Two dynamic siblings are
independent draws, not a controlled one-factor pair. Noise/count comparisons across
unrelated bases are observational strata. Only the documented paired variants and
input-context/metric-tolerance ablations support corresponding controlled analyses.

Source-specific licenses are in `LICENSES.md` and `source_attributions.json`.

Spatial ASR scores are stratified into `multi_human_spatial_selection`,
`temporal_selection_control`, and `single_human_control`. The latter two should
not be reported as evidence that the model used spatial information. The formal
scorer reports cue-type strata and same-target egocentric/allocentric WER comparisons,
averaging egocentric views within a target first. Because egocentric and allocentric use different
spatial cues, this difference must not be interpreted as receiver-count gain.
`content_localization_pair_id` links static text-to-direction and text-to-range.
`public/test/spatial_query_variants.jsonl` supports direction-only/distance-only
static ablations and single-anchor dynamic ablations only where the reduced cue
remains unambiguous. Load these with `Dataset.load(cue_variant=...)` and compare
the common eligible sample intersection.

## Distance evaluation (scorer dish_exhibition_v3.score.4)

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


## Official evaluation and citation

Use the [evaluation toolkit](https://github.com/Wenanzhi/MESH-Benchmark/blob/main/docs/evaluation.md) for frozen response processing, task scoring and the current `dish_case_equal_two_objectives_v1` Overall. Egocentric and Allocentric Overall are separate; localization and semantics each receive half the weight, with equal question weights within each objective. Code/documentation licensing is Apache-2.0; dataset and source-asset component licenses above remain unchanged.

```bibtex
@misc{wen2026mesh,
  title={MESH: Multi-receiver Evaluation of Spatial Hearing across Egocentric and Allocentric Views},
  author={Wen Wen and Bohan Li and KwanHo Tam and Yu Xi and Jing Peng and Shuai Wang and Kai Yu},
  year={2026},
  eprint={2611.16787},
  archivePrefix={arXiv},
  url={https://arxiv.org/abs/2611.16787}
}
```
