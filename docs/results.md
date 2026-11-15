# Published results

These are the exact published cells from [arXiv:2611.16787v1](https://arxiv.org/abs/2611.16787v1). Values are copied from the frozen paper tables, not recomputed for this website. The [machine-readable table](../demo/data/paper-results.json), [baseline configurations](../demo/data/baselines.json) and [source hashes](../demo/data/provenance.json) bind this comparison to its source revision.

Localization values are accuracy percentages (higher is better). Transcription values are corpus WER percentages (lower is better), without clipping. Overall is reported separately per view using `dish_case_equal_two_objectives_v1`; it is not obtained from corpus WER or an equal average of table columns. See [task codes](tasks-and-inputs.md) and [evaluation](evaluation.md).

## Egocentric

| Model | Input | ES-Dir Acc ↑ | ES-Dist Acc ↑ | ES-CDir Acc ↑ | ES-CDist Acc ↑ | ES-Trans WER ↓ | ED-Dir Acc ↑ | ED-Dist Acc ↑ | ED-Trans WER ↓ | Overall ↑ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-Omni | FOA-W | 11.34 | 18.79 | 10.15 | 20.52 | 96.53 | 3.34 | 20.73 | 128.00 | 20.56 |
| Qwen3-Omni | FOA-sep | 13.07 | 19.61 | 8.71 | 21.68 | 93.55 | 4.07 | 19.52 | 123.70 | 21.41 |
| Qwen3.5-Omni-Plus | FOA-W | 18.13 | 21.34 | 9.37 | 20.77 | 80.74 | 6.56 | 22.24 | 78.00 | 24.75 |
| Qwen3.5-Omni-Plus | FOA-sep | 17.33 | 21.90 | 9.15 | 20.65 | 72.14 | 7.64 | 19.40 | 73.10 | 26.52 |
| BAT | Binaural | 0.00 | 0.00 | 0.00 | 0.00 | 99.89 | 0.00 | 0.00 | 99.82 | 0.07 |
| MiDasheng-Spatial | Binaural | 4.62 | 6.10 | 7.95 | 13.76 | 77.21 | 0.00 | 1.20 | 86.56 | 13.23 |
| Spatial-Omni-7B | FOA | 7.63 | 6.91 | 10.97 | 15.02 | 87.68 | 1.30 | 0.70 | 97.35 | 13.66 |
| Spatial-Omni-30B | FOA | 18.91 | 5.81 | 24.76 | 5.88 | 137.11 | 6.70 | 5.75 | 165.46 | 18.54 |
| JAEGER Neural | FOA | 13.62 | 7.23 | 7.54 | 3.33 | 101.62 | 0.00 | 3.35 | 101.20 | 2.80 |
| JAEGER Classical | FOA | 7.60 | 0.06 | 0.19 | 0.00 | 103.47 | 0.04 | 3.14 | 100.75 | 0.94 |
| Qwen3.8-Omni-Flash | FOA | 41.37 | 13.98 | 50.03 | 19.55 | 72.09 | 41.54 | 19.36 | 73.32 | 30.18 |
| MESH-agent | FOA | 49.34 | 16.47 | 47.17 | 20.43 | 61.09 | 28.61 | 19.06 | 78.98 | 34.97 |

## Allocentric

| Model | Input | AS-Pos Acc ↑ | AS-CPos Acc ↑ | AS-Trans WER ↓ | AD-CPos Acc ↑ | AD-Trans WER ↓ | Overall ↑ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-Omni | FOA-W | 1.19 | 0.31 | 104.00 | 6.48 | 95.10 | 13.77 |
| Qwen3-Omni | FOA-sep | 1.19 | 0.06 | 109.59 | 6.45 | 92.06 | 14.22 |
| Qwen3.5-Omni-Plus | FOA-W | 9.49 | 7.62 | 71.06 | 6.93 | 74.10 | 19.45 |
| Qwen3.5-Omni-Plus | FOA-sep | 10.99 | 11.37 | 72.65 | 6.41 | 68.91 | 21.86 |
| BAT | Binaural | 0.00 | 0.00 | 99.89 | 0.00 | 99.98 | 0.04 |
| MiDasheng-Spatial | Binaural | 7.00 | 7.56 | 83.36 | 0.19 | 81.18 | 15.36 |
| Spatial-Omni-7B | FOA | 11.62 | 6.43 | 96.39 | 0.28 | 89.87 | 12.55 |
| Spatial-Omni-30B | FOA | 2.87 | 3.31 | 150.43 | 2.66 | 152.76 | 12.72 |
| JAEGER Neural | FOA | 5.00 | 3.56 | 106.95 | 0.00 | 101.57 | 6.58 |
| JAEGER Classical | FOA | 0.00 | 0.06 | 102.87 | 0.00 | 101.38 | 1.21 |
| Qwen3.8-Omni-Flash | FOA | 3.75 | 4.43 | 73.98 | 4.19 | 73.68 | 15.90 |
| MESH-agent | FOA | 32.04 | 31.79 | 78.54 | 18.39 | 59.15 | 31.01 |

## Coverage and interpretation

Each configuration has 39,999 archived per-question score records. Egocentric models receive the focal recording plus permitted metadata; allocentric models receive all bound receiver recordings plus permitted metadata. FOA-W, FOA-sep, Binaural and FOA are different input conditions and remain explicit in the comparison.

The explorer provides 47 archived actual outputs across 24 selected paper diagnostic questions. Full original prediction archives are currently unavailable; metric-only rows are labeled as such. A missing archive record is not evidence that the model was unrun or unsupported. MESH-agent metrics cover its full frozen V2 test; the absence of its raw outputs in the explorer does not change that coverage.

Empty-region accuracy is separate from positive-reference corpus WER; all 800 empty-region questions remain in the Overall semantic component. Direction/position task accuracy and within-question Overall components can use different averaging denominators. Do not infer the latter from the published task columns.

Community results should be submitted through the result-submission issue template with complete input, output and version provenance. They are not silently appended to the frozen paper comparison.
