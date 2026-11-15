# Licenses and attributions

Project-authored code and documentation in MESH-Benchmark are licensed under
the [Apache License 2.0](../LICENSE). See [NOTICE](../NOTICE). This grant does
not replace the licenses of third-party dependencies or dataset components.

| Component | Terms and attribution |
| --- | --- |
| Project-authored evaluation code and documentation | Apache-2.0 |
| Dataset recordings and source materials | [Component-specific licenses](https://huggingface.co/datasets/Heiheihaha17/MESH-Benchmark/blob/f7ca282fbb610206fe12336037c6cd0e587a7e55/LICENSES.md); no blanket Apache-2.0 or CC BY grant |
| LibriSpeech speech | CC BY 4.0; retain the original corpus attribution and per-source provenance |
| Environmental recordings | Per-recording attribution in `source_attributions.json` and `private/sources/noise.json` in the reproduction archive. Some sources have noncommercial restrictions. Original ESC-50 license information is under `shared/noise` in that archive. |
| Dataset annotations and metadata | Consult the dataset release and its source records; the repository's code license does not grant additional rights to third-party text or metadata. |
| Pretrained models | Their respective model licenses; weights are not redistributed here. |
| Python and browser dependencies | Their respective licenses; installing them does not relicense them. |
| Paper | The [arXiv publication license](https://arxiv.org/abs/2611.16787), independent of the code and dataset licenses |

The separate [listening-review application](https://github.com/Wenanzhi/dish-listening-review)
is MIT-licensed. Its dataset audio, transcripts, metadata and HRTF-derived assets
have separate terms. Reused application code must retain its MIT notice.

The listening application's binaural decoder is derived from the MIT KEMAR
measurements by Bill Gardner and Keith Martin. See the
[original resource and attribution requirements](https://sound.media.mit.edu/resources/KEMAR.html)
and [application data notices](https://github.com/Wenanzhi/dish-listening-review/blob/main/DATA_LICENSES.md).
An HRTF attribution is separate from the Apache license for project code.

For redistribution, retain applicable notices and the source-attribution records
for the particular assets used. No source audio, model weights or HRTF recordings
are relicensed by this repository.
