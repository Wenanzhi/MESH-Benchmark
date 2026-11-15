# Changelog

## 0.2.0 — 2026-11-15

- Public data and frozen-baseline explorer: all 39,999 questions and 12 published
  configurations, with 479,988 archived per-question metrics. Actual output
  coverage is 47 records on 24 diagnostic questions; missing archives are explicit.
- Scene/receiver visualization, time controls, verified FOA-to-binaural playback,
  original raw/reviewed/scored records and separate published aggregate tables.
- Project homepage, paper citation, dataset/task/evaluation/reproducibility
  documentation, contribution guidance and issue templates.
- Apache-2.0 for project-authored code/docs; component licenses remain separate.
- Existing scorer, response processing, Overall calculation, tests and provenance
  preserved. No new inference or rescoring. Python package remains `0.1.0`.
- Native GitHub Pages branch deployment. Custom CI workflows are prepared but
  inactive because the publication credential lacks `workflow` scope.
- HF data-card proposal retained for later synchronization at the owner's request;
  this release does not claim that the live HF card was changed.

Release source: the commit referenced by Git tag `v0.2.0`. Exact dataset,
scorer, processing, Overall and data-export identities are recorded in
[`release.json`](release.json) and [explorer provenance](demo/data/provenance.json).

## 0.1.0 — Evaluation toolkit

Initial public evaluation package at commit
`333a15985a27764b56d2075d5d3f0f7987553faf`, including the public loader,
score.4 task scorer, fixed response processing and current Overall aggregator.
