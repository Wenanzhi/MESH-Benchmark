# Reproducibility and release bindings

The scoring source, postprocessing policy, tests and original provenance files
from the evaluation release are retained. This documentation/explorer release
does not rerun inference or rescore predictions.

| Artifact | Frozen identity |
| --- | --- |
| Paper | [arXiv:2611.16787v1](https://arxiv.org/abs/2611.16787v1), 2026-11-12 |
| Dataset | `Heiheihaha17/MESH-Benchmark@f7ca282fbb610206fe12336037c6cd0e587a7e55` |
| Task protocol | `dish_exhibition_v3.tasks.3` |
| Task scorer | `dish_exhibition_v3.score.4` |
| LALM response processing | `gold_blind_content_v1`; [policy](../postprocess/asr_review_policy.json) |
| Overall | `dish_case_equal_two_objectives_v1` |
| Paper artifact source commit | `f20c1ebbcbe7a339173e92f68c6d7fc41633221d` |
| Agent | Frozen V2 full test, `disrobot_exhibition_full_v2_20261009` |
| Listening asset source | `Wenanzhi/dish-listening-review@c18bd9515a430a79673a0fb3d0f982d7f3135001` |
| Explorer data format | `mesh-demo-data-v1` |
| Python package version | `0.1.0` (independent of protocol and website releases) |

The source paper repository is an archival dependency for regenerating the
export; public users can inspect the shipped shards and their hashes without
accessing it. See [demo provenance](../demo/data/provenance.json) and the
[baseline registry](../demo/data/baselines.json). Neither a matching question
ID nor a successful score alone proves that inference inputs were correct.

For a new evaluation, archive the model/checkpoint and service version, exact
dataset revision, input adapter, receiver bindings, system prompt, generation
configuration, full raw responses, reviewed outputs, processing audit and scorer
results. Record failed requests rather than dropping them. Follow the
[full evaluation commands](evaluation.md), keeping all 39,999 questions.

For the published comparison, use the original frozen values. Inference
configuration revisions and the final scoring revision are recorded separately;
the explorer does not relabel an earlier inference snapshot as the scoring
snapshot. Some source configuration fields and full prediction archives are
unavailable in the public export. Their absence is disclosed in the registry.

The listening snapshot uses dataset revision `87e9f4d5394887d5d8a262ae8497ff2ba0089627`.
Its static/dynamic public indices, inputs and private gold files have identical
HF blob/LFS identities to the final release. The archived LALM inference snapshot
`54552513b3e69a814acd5b3ae9f85a28c41bdd25` has the same six file identities;
see the [revision-comparison receipt](../demo/data/dataset-revisions.json).
The exporter additionally checks
every question, reference output, target, query, time window, receiver and
recording hash against the local final release. It checks the listening files
against the pinned Git objects before export. The browser verifies result shards,
scene/reference assets and loaded audio by SHA-256.

Run repository checks:

```bash
python -m unittest discover -s overall -p 'test_*.py' -v
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/validate_demo.py
node --test demo/tests/*.test.mjs
```

The existing `validation.json` describes the original package equivalence audit.
It is not rewritten as evidence for the new website. The
[website verification receipt](maintainers/release-verification-20261115.json)
records the deployed source, existing tests, frozen-record checks and live
audio/mobile verification. Release metadata is in [`release.json`](../release.json).
