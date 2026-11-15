# Contributing

Use GitHub issues for reproducible bugs, data questions and result submissions.
For a correction, include the dataset revision, question ID, task, receiver
bindings and expected/observed behavior. For a website issue, include the shared
question link and browser version. Avoid attaching credentials or unrelated
private recordings.

The [evaluation protocol](docs/evaluation.md) and frozen paper results are
versioned contracts. Explain any scoring or input change before proposing it;
do not silently replace the published values or mix dataset revisions. New
baselines must provide complete predictions, failures included, plus model/input
configuration, raw and reviewed outputs, postprocessing policy, scorer version
and full-population results. A low-level score alone does not validate the
inference setup. See the result-submission issue template.

Use a topic branch and a focused PR. Preserve source provenance and component
license notices. For code changes run the checks in
[reproducibility](docs/reproducibility.md). For explorer changes also verify the
affected task, missing/invalid/empty states, reference/input separation and
desktop/mobile display. No model inference is needed to test the explorer.

The prepared CI workflows are currently inactive because the publication
credential lacks GitHub's `workflow` scope. Local checks and recorded browser
verification remain required; see [maintainer notes](docs/maintainers/README.md).

Project-authored contributions are provided under Apache-2.0. Include the
appropriate separate attribution and terms for third-party assets.
