"""
RunEnvelope — deterministic record of *what was actually executed*.

``DoneContract.run_id`` already references a RunEnvelope by id, but until now
no model existed for it. Every CLI command that mutates phase state should
construct (or load) a RunEnvelope so that the proof packet, ledger entry, and
verifier all reference the same immutable description of the run.

Fields capture the four "evidence" categories called out in the platform
review:

* identity         — ``run_id``, ``phase``, ``started_at``, ``finished_at``
* command          — argv transcript actually invoked
* environment      — Python version, platform, env-var fingerprint
* control surface  — dry-run flag, mode (local/ci), verifier identity
"""

from __future__ import annotations

import hashlib
import os
import platform
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


RunMode = Literal["local", "ci", "agent"]


def _env_fingerprint() -> str:
    """Stable hash over a controlled subset of env vars.

    We never store raw env values (they may contain secrets); instead we hash
    the sorted ``name=len(value)`` pairs of CI/runtime-relevant variables.
    """
    keys = sorted(
        k for k in os.environ
        if k.startswith(("CI", "GITHUB_", "RUNNER_", "PYTHON", "VIRTUAL_ENV"))
    )
    blob = "\n".join(f"{k}={len(os.environ[k])}" for k in keys)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── Lockfile discovery (G004) ────────────────────────────────────────

LOCKFILE_NAMES: tuple[str, ...] = (
    "requirements.txt",
    "requirements-lock.txt",
    "constraints.txt",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "pnpm-lock.yml",
)


def _discover_lockfiles(start: Path | None = None) -> list[Path]:
    """Walk upward from *start* (defaulting to cwd) and collect lockfiles.

    Returns every lockfile found in the walk from *start* up to (and
    including) the filesystem root.  The order is nearest-first.
    """
    root = (start or Path.cwd()).resolve()
    found: list[Path] = []
    for candidate in (root, *root.parents):
        for name in LOCKFILE_NAMES:
            path = candidate / name
            if path.is_file():
                found.append(path)
    return found


def _lockfile_hash(lockfiles: list[Path]) -> str:
    """Deterministic SHA-256 over the sorted contents of *lockfiles*.

    When no lockfiles are provided the hash is the empty-blob SHA-256 so
    that the field is always present and of constant length.
    """
    sha = hashlib.sha256()
    for path in sorted(lockfiles):
        sha.update(path.read_bytes())
    return sha.hexdigest()


def _detect_mode() -> RunMode:
    if os.environ.get("CI", "").lower() in ("1", "true"):
        return "ci"
    if os.environ.get("RIGFORGE_AGENT_MODE", "").lower() in ("1", "true"):
        return "agent"
    return "local"


class RunEnvelope(BaseModel):
    """Immutable record of a single ``rigforge run`` invocation."""

    run_id: str = Field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    phase: int = Field(..., ge=1, le=7)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    argv: list[str] = Field(default_factory=lambda: list(sys.argv))
    python_version: str = Field(default_factory=lambda: sys.version.split()[0])
    platform: str = Field(default_factory=platform.platform)
    env_fingerprint: str = Field(default_factory=_env_fingerprint)
    lockfile_hash: str = Field(
        default_factory=lambda: _lockfile_hash(_discover_lockfiles()),
        description="SHA-256 of the sorted dep-lockfile contents found during run construction.",
    )
    lockfiles: list[str] = Field(
        default_factory=lambda: [str(p) for p in _discover_lockfiles()],
        description="Paths to lockfiles discovered during run construction.",
    )
    mode: RunMode = Field(default_factory=_detect_mode)
    dry_run: bool = False
    verifier: str | None = Field(
        default=None,
        description="Identity of the verifier (agent name, human handle, or CI job).",
    )

    def finish(self) -> "RunEnvelope":
        """Return a copy with ``finished_at`` set to now."""
        return self.model_copy(update={"finished_at": datetime.now(timezone.utc)})

    def duration_seconds(self) -> float | None:
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()

    def to_dict(self) -> dict:
        data = self.model_dump(mode="json")
        return data
