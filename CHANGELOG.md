# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2026-10-19

Polish wave (2026-10-19, same day):

- This commit removes unused imports and unused local variables in
  `rigforge/telemetry.py`, `rigforge/tests/test_cli.py`,
  `rigforge/tests/test_public_attest.py`, `rigforge/benchmark.py`,
  `rigforge/cli.py`, `rigforge/commands/status.py`, `rigforge/evalloop.py`,
  `rigforge/lattice/router.py`, `rigforge/public_attest.py`,
  `rigforge/registry.py`, `rigforge/triple_diamond.py` and four test modules,
  so `ruff check --isolated` (the full default rule set) passes clean.
- This commit changes `.github/workflows/ci.yml` and `.github/workflows/smoke.yml`
  to add `timeout-minutes: 15` to every job and to remove
  `continue-on-error: true` from the full-rule-set lint step, which is now
  blocking because it passes.
- This commit changes the README CI badge to the shields
  `github/actions/workflow/status` form for `ci.yml` on `main`.
- This commit adds `rigforge/tests/test_repo_hygiene.py`, which asserts from the
  files on disk: `.github/CODEOWNERS` contains `* @mrodgersjs-web`;
  `.github/copilot-instructions.md` is at most 8000 bytes and names a test
  command; the README carries a `github/actions/workflow/status` badge, the
  `rodgersintelligence.com` footer, a test command word, and clone examples
  targeting `mrodgersjs-web/rigforge`; and every workflow job has
  `timeout-minutes` and no `continue-on-error`.

Lint repair wave (2026-10-20):

- This commit sorts the import blocks in the `contracts/` modules and tests that `ruff check --isolated` flagged as unsorted (rule I001); no behavior changes.
- This commit sorts the import blocks in the top-level `rigforge/` modules flagged unsorted by `ruff check --isolated` (rule I001); no behavior changes.
- This commit sorts the import blocks in the `rigforge/tests/` modules flagged unsorted by `ruff check --isolated` (rule I001); no behavior changes.
- This commit sorts the import blocks in the `rigforge/lattice/` and `rigforge/commands/` modules flagged unsorted by `ruff check --isolated` (rule I001); no behavior changes.
- This commit removes the four `# noqa` markers that `ruff check --isolated` reported as unused (rule RUF100), keeping a marker's reason text as a plain comment where it had one.
- This commit applies ruff's remaining safe autofixes under the default rule set (UP035, UP037, UP045, FURB167, RUF022, PLR0402, TC005, SIM117, PLR1711, RET501); annotation and style modernization only, no behavior changes.
- This commit narrows one blind except to `ValueError` and keeps the eight deliberate catch-all handlers with `# noqa` reasons (rules BLE001, S110); no behavior changes.
- This commit asserts the specific `pydantic.ValidationError` in three contract tests and makes dict iteration and subprocess `check=False` explicit (rules B017, PLC0206, PLW1510); no behavior changes.

### Added

- Tests for the intent-routing subsystem (lattice model, intent parser, lattice
  router, troika triad, forge engine, standalone commands) and the telemetry
  no-op fallback: 25 tests, `rigforge/tests/test_intent_pipeline.py`.
- Packaging invariant tests (`rigforge/tests/test_packaging.py`) asserting the
  installed version, the `py.typed` marker, the console script, and the Python
  floor.
- CI config invariant tests (`rigforge/tests/test_ci_config.py`) that parse both
  workflow files and assert triggers, read-only permissions, the version matrix,
  and that the real suite runs.
- `rigforge/py.typed` (partial typing marker).
- Community files: `CODE_OF_CONDUCT.md`, this changelog, issue templates, a pull
  request template, and `CITATION.cff`.
- `docs/USAGE.md`: the CLI reference, configuration, MCP integration, spec-bound
  proofs, merge gate, swarm verdict board, and the public-attestation compose
  path, moved off the README front page.

### Changed

- README rewritten to the front-page pattern: one-line pitch, badges, kept demo
  GIF, "Why this exists", a "What it proves" table of runnable checks with
  measured results, quickstart, real example output, a mermaid architecture
  diagram, project layout, development, and the public boundary.
- Packaging: version 1.0.0 -> 1.1.0, authors "Mike Rodgers", plain-English
  description, `requires-python >=3.10` with the 3.10 classifier and ruff
  `target-version = "py310"`, and `cryptography` added to the `dev` extra so the
  public-attestation tests run instead of skipping.
- The `python_version` hard gate now defaults to 3.10, matching the advertised
  floor in `pyproject.toml` and the CI matrix (it enforced 3.11).
- CI: the test matrix covers Python 3.10 to 3.13 and runs pytest with coverage;
  the smoke workflow runs the full test suite before `scripts/smoke.sh`.

### Fixed

- README claimed "252 passing"; the measured result on this version is 320
  passed, 0 skipped, with 84% package coverage (test files excluded).
- Stale test-count comments in `pyproject.toml` and `.github/workflows/ci.yml`.

## [1.0.0]

Initial public release. (Release date not recorded in this repository.)
