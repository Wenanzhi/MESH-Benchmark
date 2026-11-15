# Data and baseline explorer

The [live explorer](https://wenanzhi.github.io/MESH-Benchmark/) in `demo/` is a
static application for inspecting the published
dataset and comparing frozen baselines on a single question. It has no inference
server, reviewer identity, listening questionnaire or feedback collection.
The separate [listening-review tool](https://wenanzhi.github.io/dish-listening-review/)
and its existing records remain unchanged.

## Available evidence

- All 39,999 question IDs across 2,400 scene realizations are searchable.
- All 12 published configurations have a frozen score for every question:
  **479,988 per-question metric records**.
- **47 actual output records across 24 questions** are available from archived
  paper diagnostics. Raw text, reviewed output and original task-scoring records
  are preserved when available. These cases are explicitly labeled as selected
  diagnostics, not representative examples.
- Full original prediction archives have not been recovered. A missing answer
  is shown as **Output not archived**, even when its evaluated metric is known.
  It is never inferred from the score or replaced with an empty string or zero.
- Default static, moving-source, multi-receiver and empty-region examples use
  dataset attributes and lexical IDs only, without model-score selection.

The main comparison always lists all configurations. Full raw text and numeric
values are expandable. Localization predictions can be overlaid when an actual
valid record is available. Trajectory views use submitted points and exact grid
frames; missing/inactive prediction frames are not interpolated. Physical scene
positions may be interpolated solely for animation. WER remains uncapped, with
original insertions and repetitions preserved in the displayed answer.

Reference answers and scene truth are marked **Evaluator only**. Exact allowed
prompts/queries and permitted recordings are shown separately. Only the focal
recording is playable for an egocentric question; an allocentric question allows
its multiple synchronized receivers. Switching receivers retains the time cursor.
Browser playback is FOA decoded to binaural using MIT KEMAR filters, separate
from the baselines' original audio adapters.

## Serve and validate

Use a modern browser with Web Audio, Web Crypto and `DecompressionStream`.
Serve over HTTPS or localhost; opening `index.html` as a file is unsupported.

```bash
python -m http.server 8000 --directory demo
```

The index and compact result shards are bundled; audio and scene/reference
assets load on demand from immutable HF/GitHub revisions. Network failures are
reported and can be retried by selecting the question or Listen again. Audio
does not autoplay. There is no miniature evaluation dataset.

## Regenerate the frozen export

Maintainers need the immutable paper artifact repository, the pinned listening
repository and the complete task release. The exporter validates joins and
copies existing values; it never invokes inference, parsing repair or scoring.

```bash
python scripts/export_demo.py --paper-repo /path/to/dish-paper --paper-revision f20c1ebbcbe7a339173e92f68c6d7fc41633221d --listening-repo /path/to/dish-listening-review --dataset /path/to/MESH-Benchmark --output demo/data
python scripts/validate_demo.py
node --test demo/tests/*.test.mjs
```

The listening checkout must contain the files at
`c18bd9515a430a79673a0fb3d0f982d7f3135001`; the exporter rejects modified source
assets. Version identities, source hashes, coverage and selection policy are in
[`provenance.json`](../demo/data/provenance.json). SHA-256 identifies frozen
original score/prediction archives even where their full contents are unavailable.

When restoring more outputs, require the original run/configuration, question,
receiver, dataset and scorer bindings; do not merge similarly named older runs.
Add the source manifest, update export coverage and test raw-text preservation.
Keep available, valid-empty, invalid, unsupported, not-run and missing-archive
states distinct. No sample page reports an official Overall; that is confined to
the separately versioned [paper results](results.md).

GitHub Pages deployment uses the checked `demo/` directory copied to the root of
the `gh-pages` branch, with `.nojekyll`. The publication credential does not have
the `workflow` scope, so custom workflow files are retained as inactive examples
under `docs/maintainers/`; they are not represented as active CI. See the
[maintainer deployment notes](maintainers/README.md). Reused player code is MIT-licensed; see
[component notices](licenses-and-attributions.md).
