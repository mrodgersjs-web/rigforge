"""CI configuration invariants: triggers, permissions, version matrix.

Parses the workflow YAML so a syntax error or a drifted matrix fails the
test suite instead of surfacing on the next push.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(wf: dict):
    # PyYAML reads a bare `on:` key as boolean True (YAML 1.1).
    return wf.get("on", wf.get(True))


def test_ci_yaml_parses_and_runs_on_push_and_pull_request():
    wf = _load("ci.yml")
    triggers = _triggers(wf)
    assert "push" in triggers and "pull_request" in triggers


def test_ci_permissions_are_read_only():
    assert _load("ci.yml")["permissions"] == {"contents": "read"}


def test_ci_matrix_covers_the_supported_python_range():
    matrix = _load("ci.yml")["jobs"]["test"]["strategy"]["matrix"]
    assert matrix["python-version"] == ["3.10", "3.11", "3.12", "3.13"]
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.10"' in pyproject  # floor matches the matrix


def test_ci_runs_the_real_suite_with_coverage():
    steps = _load("ci.yml")["jobs"]["test"]["steps"]
    run_lines = " ".join(s.get("run", "") for s in steps if isinstance(s, dict))
    assert "pytest" in run_lines and "--cov" in run_lines


def test_smoke_workflow_runs_the_test_suite_too():
    wf = _load("smoke.yml")
    assert "pull_request" in _triggers(wf)
    run_lines = " ".join(s.get("run", "") for s in wf["jobs"]["smoke"]["steps"] if isinstance(s, dict))
    assert "pytest" in run_lines  # not only scripts/smoke.sh
