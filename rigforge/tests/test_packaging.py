"""Packaging invariants: version, typing marker, console script, python floor.

These assert the metadata a consumer actually depends on, so a broken
pyproject.toml change fails the suite instead of only failing at install time.
"""

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path

import rigforge

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = Path(rigforge.__file__).resolve().parent


def _pyproject_text() -> str:
    return (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_installed_version_is_the_next_minor_release():
    assert metadata.version("rigforge") == "1.1.0"
    assert 'version = "1.1.0"' in _pyproject_text()


def test_py_typed_marker_exists_and_declares_partial_typing():
    marker = PKG_DIR / "py.typed"
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8").strip() == "partial"


def test_console_script_is_installed():
    scripts = {ep.name for ep in metadata.entry_points(group="console_scripts")}
    assert "rigforge" in scripts


def test_python_floor_is_310_and_the_runner_satisfies_it():
    assert 'requires-python = ">=3.10"' in _pyproject_text()
    assert sys.version_info >= (3, 10)
