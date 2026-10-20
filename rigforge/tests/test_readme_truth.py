"""README truth lint.

The front page makes measurable claims, so the suite enforces the copy rules
with it: no banned marketing words, no machine paths, no stale test counts,
and every required section present. A README edit that breaks any of these
fails `pytest` instead of shipping.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

BANNED_WORDS = [
    "unlock", "empower", "synergy", "leverage", "disrupt", "hustle",
    "utilize", "iterate", "optimize", "1000x", "novel-to-the-world",
    "first in the world",
]

REQUIRED_SECTIONS = [
    "## Why this exists",
    "## What it proves",
    "## Quickstart",
    "## Usage",
    "## How it works",
    "## Project layout",
    "## Development",
    "## Public boundary",
    "## Security",
    "## License",
]


def test_readme_has_no_banned_marketing_words():
    lowered = README.lower()
    found = [w for w in BANNED_WORDS if re.search(rf"\b{re.escape(w)}\b", lowered)]
    assert found == []


def test_readme_has_no_machine_paths():
    assert "/Users/" not in README
    assert "~/Developer" not in README


def test_readme_has_no_stale_test_counts():
    assert "252 passing" not in README
    assert "221 passed" not in README


def test_readme_required_sections_and_footer():
    for section in REQUIRED_SECTIONS:
        assert section in README, f"missing section: {section}"
    assert "Built by Mike Rodgers" in README
    assert "rodgersintelligence.com" in README


def test_readme_keeps_the_demo_gif_and_architecture_diagram():
    assert "docs/rigforge-demo.gif" in README
    assert "```mermaid" in README
