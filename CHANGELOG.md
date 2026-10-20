# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2026-10-19

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
