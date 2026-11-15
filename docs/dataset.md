# Dataset

[MESH-Benchmark on Hugging Face](https://huggingface.co/datasets/Heiheihaha17/MESH-Benchmark)
is the canonical dataset. The paper and explorer bind to revision
`f7ca282fbb610206fe12336037c6cd0e587a7e55`, task protocol
`dish_exhibition_v3.tasks.3`. The former `Heiheihaha17/DiSH-Bench-exhibition-v3`
address redirects to this repository; internal IDs remain unchanged.

| Unit | Static | Dynamic | Total |
| --- | ---: | ---: | ---: |
| Physical scene realizations | 800 | 1,600 | 2,400 |
| Receiver recordings | 1,587 | 3,174 | 4,761 |
| Questions | 19,117 | 20,882 | 39,999 |

There are 100 rooms, 800 base scenes and 299 distinct human speaker identities
in the released manifests. Each base scene fixes speech identity/content,
noise and initial configuration, with one static realization and two independently
drawn motion variants. Receiver views and questions are not additional physical
scenes. Approximate descriptions such as “40,000 questions” do not replace the
exact population for scoring.

Recordings are synchronized, 16 kHz, four-channel FOA in ACN/SN3D order
`[W, Y, Z, X]`. World coordinates are meters with **Y up**; receiver-local axes
are X front, Y left, Z up. Azimuth is 0° forward, +90° left and −90° right.
Robot yaw 0° faces world −Z and positive yaw turns toward +X. Dynamic output
labels use a 0.5-second grid; acoustic-rendering knots are not the output grid.

Keep the directory structure under `static/` and `dynamic/` intact:

- `public/test/index.jsonl`: question identities and task/scene bindings.
- `public/test/inputs.jsonl`: permitted queries, poses, playback metadata and audio bindings.
- `public/test/recordings.jsonl` and `public/audio/test/`: recording identities, paths and hashes.
- `private/test/gold.jsonl`: evaluator-only reference answers.
- `public/evaluation_protocol.json`: coordinate, matching and task-scoring rules.

The `private` directory is an evaluation boundary, not an access-control claim.
Never supply its answers, source identities, reference transcripts or another
question's labels as inference context. The explorer deliberately shows this
information for inspection and labels it **Evaluator only**.

Obtain the complete release using the Hugging Face repository's download
instructions, selecting the immutable revision above. Preserve relative paths
and verify manifest checksums. This repository does not redistribute the full
audio or define an additional demonstration split.

Data and underlying source assets have component-specific licenses, including
sources with noncommercial conditions. See [licenses and attributions](licenses-and-attributions.md).
