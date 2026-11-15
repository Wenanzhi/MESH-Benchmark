# CI and publication

The initial publication credential has repository access but lacks GitHub's
`workflow` OAuth scope. GitHub rejected the push of `.github/workflows/*`.
The prepared workflows are therefore retained here as **inactive examples**:
`tests.yml.example` and `pages.yml.example`. No CI badge claims they are running.

To activate custom CI after obtaining the required credential scope, copy the
examples to `.github/workflows/tests.yml` and `.github/workflows/pages.yml` in a
reviewed PR. If enabling the Pages workflow, change Pages' build type to GitHub
Actions. Do not run both publishing mechanisms for the same site.

Current publication uses GitHub's supported branch-based Pages configuration:
`gh-pages`, root directory, `.nojekyll`. Copy only the validated `demo/` tree.
The deployment commit message records the source main-branch commit. Check the
actual public site after deployment; do not treat a successful Git push as a
successful website deployment.

Before publication, run the Python contract/Overall tests, `scripts/validate_demo.py`
and Node display/download tests, then `scripts/check_demo.mjs` with Playwright.
For a live check, set `DEMO_URL=https://wenanzhi.github.io/MESH-Benchmark/`.
Browser receipts include the tested URL, timestamp, question IDs and audio/mobile
checks. Do not substitute fixtures for the live audio test without reporting it.
