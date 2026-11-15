# MESH-Benchmark

**Multi-receiver Evaluation of Spatial Hearing across Egocentric and Allocentric Views**

Wen Wen\*, Bohan Li\*, KwanHo Tam, Yu Xi, Jing Peng, Shuai Wang, Kai Yu (\*equal contribution)

[Paper](https://arxiv.org/abs/2611.16787) · [Dataset](https://huggingface.co/datasets/Heiheihaha17/MESH-Benchmark) · [Demo](https://wenanzhi.github.io/MESH-Benchmark/) · [Citation](#citation)

MESH evaluates the association between speech content and source position across
receiving perspectives and under motion. This repository provides data loaders,
response processing, task scoring, Overall aggregation and a frozen-result explorer.

## Installation

Use Python 3.12. The commands below use Bash and run from the repository root.
Loading, postprocessing and scoring run on CPU; your model adapter determines
the inference dependencies and hardware requirements.

```bash
git clone https://github.com/Wenanzhi/MESH-Benchmark.git
cd MESH-Benchmark
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install huggingface_hub
```

## Dataset preparation

Download the complete release at the revision used for the published evaluation:

```bash
export MESH_DATASET="$PWD/data/MESH-Benchmark"
hf download Heiheihaha17/MESH-Benchmark \
  --repo-type dataset \
  --revision f7ca282fbb610206fe12336037c6cd0e587a7e55 \
  --local-dir "$MESH_DATASET"
```

Keep the released directory structure, indices and completion receipts intact:

```text
MESH-Benchmark/
├── static/
│   ├── release.complete.json
│   ├── public/                  # Audio, prompts, inputs and question index
│   └── private/test/gold.jsonl  # Scoring references
└── dynamic/                     # Same layout
```

Audio is 16 kHz, four-channel FOA in ACN/SN3D `[W, Y, Z, X]` order.
Egocentric questions receive the focal recording and permitted peer metadata;
allocentric questions receive all bound receiver recordings and permitted metadata.
Preserve channel order and receiver identities. Keep `private/` references out of
model inputs. See [dataset details](docs/dataset.md) and [task definitions](docs/tasks-and-inputs.md).

## Prepare predictions

Choose a new run directory for each model and input configuration:

```bash
export MESH_RUN="$PWD/runs/my-model"
mkdir -p "$MESH_RUN"
```

Load permitted inputs through the public loader:

```python
import os
from pathlib import Path
from exhibition_v3.loader import Dataset

dataset = Dataset(Path(os.environ["MESH_DATASET"]) / "static")
sample = dataset.load(dataset.ids()[0])
# sample["prompt"] contains the task instructions and permitted context.
# sample["audio"] is a list of receiver recordings, each shaped [samples, 4].
```

Use `dynamic` for dynamic questions and `audio=False` for prompt inspection.
Implement your own model/API adapter; model-specific baseline adapters are not
bundled with this evaluation package. Choose one of the following output routes.

### A. Raw model text

Save one JSON object per line to `$MESH_RUN/raw_static.jsonl` and
`$MESH_RUN/raw_dynamic.jsonl`. Use the actual question ID, public task ID and
unaltered model response; this line illustrates the format:

```json
{"sample_id":"<question ID>","task_id":"DOA_RANGE_ASR","raw_text":"<model response>"}
```

Preserve failed requests in a separate failure log. Do not turn a failed request
or null response into an empty transcript. Apply the fixed text processor in
[Evaluation](#evaluation).

### B. Structured predictions

If your model already returns the task's required JSON value, save rows with
`sample_id` and `output`. For a transcription task, for example:

```json
{"sample_id":"<question ID>","output":"<recognized transcript>"}
```

The general runner can write these files. Implement `predict(sample)` in your
own `my_model.py` at the repository root; return only the task-specific output
value as specified by the prompt. The runner adds `sample_id` and iterates over
all released question IDs by default:

```bash
python -m exhibition_dataset.loader \
  --root "$MESH_DATASET/static" --adapter my_model:predict \
  --output "$MESH_RUN/predictions/static.jsonl"
python -m exhibition_dataset.loader \
  --root "$MESH_DATASET/dynamic" --adapter my_model:predict \
  --output "$MESH_RUN/predictions/dynamic.jsonl"

export MESH_STATIC_PRED="$MESH_RUN/predictions/static.jsonl"
export MESH_DYNAMIC_PRED="$MESH_RUN/predictions/dynamic.jsonl"
```

Rerunning the same command resumes IDs absent from the output file. Keep failures
explicit (for example, `output: null` plus a separate error log). These predictions
go directly to [task scoring](#2-score-static-and-dynamic-tasks); the raw-text
processor requires a different input schema.

## Evaluation

### 1. Process raw text (route A only)

```bash
python postprocess/postprocess_predictions.py \
  --predictions "$MESH_RUN/raw_static.jsonl" \
  --output-dir "$MESH_RUN/processed/static"
python postprocess/postprocess_predictions.py \
  --predictions "$MESH_RUN/raw_dynamic.jsonl" \
  --output-dir "$MESH_RUN/processed/dynamic"

export MESH_STATIC_PRED="$MESH_RUN/processed/static/reviewed_predictions.jsonl"
export MESH_DYNAMIC_PRED="$MESH_RUN/processed/dynamic/reviewed_predictions.jsonl"
```

Each output directory must be new. The processor writes normalized predictions,
`reviewed_predictions.jsonl`, `postprocess_audit.jsonl` and
`postprocess_complete.json`. Use the reviewed files for scoring. See the
[processing policy](docs/evaluation.md#fixed-response-processing) for details.

### 2. Score static and dynamic tasks

Run this step with the prediction paths from either route above:

```bash
python -m exhibition_v3.score \
  --root "$MESH_DATASET/static" --predictions "$MESH_STATIC_PRED" \
  --output "$MESH_RUN/scores/static"
python -m exhibition_v3.score \
  --root "$MESH_DATASET/dynamic" --predictions "$MESH_DYNAMIC_PRED" \
  --output "$MESH_RUN/scores/dynamic"
```

Each score directory contains `metrics.json` (task summaries) and
`per_sample.jsonl.gz` (per-question scores). Missing or invalid predictions remain
in the full evaluation population and reduce accuracy/coverage.

### 3. Compute Overall

```bash
python overall/overall_score.py \
  --model my-model \
  --static "$MESH_RUN/scores/static/per_sample.jsonl.gz" \
  --dynamic "$MESH_RUN/scores/dynamic/per_sample.jsonl.gz" \
  --static-index "$MESH_DATASET/static/public/test/index.jsonl" \
  --dynamic-index "$MESH_DATASET/dynamic/public/test/index.jsonl" \
  --output-dir "$MESH_RUN/scores/overall"
```

The Overall directory must be new. Read `scores.csv` for Egocentric and Allocentric
Overall, and `overall_complete.json` to confirm completion. Task/split summaries
and per-question weighted scores are also saved. Aggregation requires all 39,999
scored questions and includes empty-region cases. See the
[evaluation protocol](docs/evaluation.md#overall-scores) for weighting and metrics.

## Run the demo

Open the [hosted explorer](https://wenanzhi.github.io/MESH-Benchmark/), or serve it locally:

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory demo
```

Visit <http://127.0.0.1:8000>. The explorer displays frozen results; it does not run
models. Audio and scene/reference assets load on demand over the network, so
local serving does not require downloading the complete dataset. See
[demo usage and coverage](docs/demo.md).

## Further documentation

- [Tasks and permitted inputs](docs/tasks-and-inputs.md) · [Dataset](docs/dataset.md)
- [Published results](docs/results.md) · [Evaluation details](docs/evaluation.md)
- [Reproducibility and checks](docs/reproducibility.md) · [Release versions](release.json)
- [Contributing and result submissions](CONTRIBUTING.md) · [Report an issue](https://github.com/Wenanzhi/MESH-Benchmark/issues)

## Citation

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

## License and contact

Project-authored code and documentation use [Apache-2.0](LICENSE).
Data and third-party components retain their [respective licenses](docs/licenses-and-attributions.md).
Research contact: [Wen Wen](mailto:wenyideng@sjtu.edu.cn) and
[Bohan Li](mailto:everlastingnight@sjtu.edu.cn).
