"""Tests for the upgraded RIGForge CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from rigforge.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal RIGForge project rooted at ``tmp_path``."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (tmp_path / "rigforge").mkdir()
    (tmp_path / "contracts" / "v1").mkdir(parents=True)
    return tmp_path


def _invoke(runner, project: Path, *args: str):
    return runner.invoke(main, ["--cwd", str(project), *args])


# ── version + top-level ─────────────────────────────────────────────────


class TestVersion:
    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output


# ── init ────────────────────────────────────────────────────────────────


class TestInit:
    def test_init_scaffolds_layout(self, runner, tmp_path):
        result = _invoke(runner, tmp_path, "init")
        assert result.exit_code == 0, result.output
        assert (tmp_path / "proofs").is_dir()
        assert (tmp_path / "ledger").is_dir()
        assert (tmp_path / "docs").is_dir()
        assert (tmp_path / "rigforge.yaml").exists()

    def test_init_json(self, runner, tmp_path):
        result = _invoke(runner, tmp_path, "--json", "init")
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["ok"] is True
        assert "rigforge.yaml" in payload["created"]


# ── verdicts (swarm board) ──────────────────────────────────────────────


class TestVerdicts:
    def _seed(self, project: Path):
        from rigforge.ledger import ExecutionLedger

        led = ExecutionLedger(project / "ledger" / "execution.jsonl")
        for _ in range(3):
            led.append(kind="verify", actor="good-agent", accepted=True)
        led.append(kind="verify", actor="rogue-bot", accepted=False)

    def test_verdicts_json(self, runner, project):
        self._seed(project)
        result = _invoke(runner, project, "--json", "verdicts")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["verdicts"]["good-agent"]["accepted"] == 3
        assert payload["verdicts"]["rogue-bot"]["rejected"] == 1

    def test_verdicts_text_lists_agents(self, runner, project):
        self._seed(project)
        result = _invoke(runner, project, "verdicts")
        assert result.exit_code == 0, result.output
        assert "good-agent" in result.output
        assert "rogue-bot" in result.output


# ── spec-check (spec-bound proofs, Move #2) ──────────────────────────────


class TestSpecCheck:
    def _write_proof(self, project: Path, *, lint_gate: bool):
        import secrets

        from rigforge.proof import GateOutcome, ProofPacket
        from rigforge.spec import Spec, SpecBinding

        spec_f = project / "spec.md"
        spec_f.write_text("## AC\n- [ ] tests pass\n- [ ] lint clean\n")
        key = secrets.token_bytes(32)
        gates = [GateOutcome(name="tests pass", passed=True)]
        if lint_gate:
            gates.append(GateOutcome(name="lint clean", passed=True))
        packet = ProofPacket(
            phase=1, name="a", verifier="v", evidence="e", gates=gates,
            spec=SpecBinding.of(Spec.from_file(spec_f)),
        ).sealed(signing_key=key)
        proof_f = project / "proof.json"
        packet.write(proof_f, signing_key=key)
        return proof_f, spec_f

    def test_spec_check_pass(self, runner, tmp_path):
        proof, spec = self._write_proof(tmp_path, lint_gate=True)
        r = _invoke(runner, tmp_path, "spec-check", "--proof", str(proof), "--spec", str(spec))
        assert r.exit_code == 0, r.output
        assert "PASS" in r.output

    def test_spec_check_fails_on_skipped_criterion(self, runner, tmp_path):
        proof, spec = self._write_proof(tmp_path, lint_gate=False)
        r = _invoke(runner, tmp_path, "spec-check", "--proof", str(proof), "--spec", str(spec))
        assert r.exit_code == 1
        assert "MISSING" in r.output and "lint clean" in r.output


# ── doctor ──────────────────────────────────────────────────────────────


class TestDoctor:
    def test_doctor_runs(self, runner, project):
        result = _invoke(runner, project, "--json", "doctor")
        payload = json.loads(result.output)
        names = [c["name"] for c in payload["checks"]]
        assert "python_version" in names
        assert "repo_layout" in names
        assert "ci_workflow" in names


# ── run + seal + verify ─────────────────────────────────────────────────


class TestRunSealVerify:
    def test_run_dry_run(self, runner, project):
        result = _invoke(runner, project, "--json", "run", "1", "--dry-run")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["phase"] == 1
        assert payload["envelope"]["dry_run"] is True
        assert payload["gates"] == []

    def test_run_invalid_phase(self, runner, project):
        assert _invoke(runner, project, "run", "0").exit_code != 0
        assert _invoke(runner, project, "run", "8").exit_code != 0

    def test_seal_writes_proof_with_hash(self, runner, project):
        _invoke(runner, project, "init")
        # phase 1 only checks python+repo layout — should pass in a normal env
        artifact = project / "docs" / "evidence.txt"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("hello")
        result = _invoke(
            runner, project, "--json",
            "seal", "1",
            "--artifact", str(artifact),
            "--evidence", "phase 1 bootstrap complete",
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["ok"] is True
        assert len(payload["packet_sha256"]) == 64
        proof_path = project / "proofs" / "phase1_proof.json"
        assert proof_path.exists()
        raw = json.loads(proof_path.read_text())
        assert raw["verifier"]
        assert raw["packet_sha256"] == payload["packet_sha256"]
        assert raw["artifacts"][0]["sha256"]

    def test_verify_reports_unsealed(self, runner, project):
        _invoke(runner, project, "init")
        result = _invoke(runner, project, "--json", "verify")
        # No phases sealed → ok=True (no errors), but all phases NOT SEALED
        payload = json.loads(result.output)
        assert payload["ok"] is True
        assert all(not p["sealed"] for p in payload["phases"])

    def test_verify_strict_passes_after_seal(self, runner, project):
        _invoke(runner, project, "init")
        artifact = project / "docs" / "evidence.txt"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("hi")
        seal_res = _invoke(runner, project, "seal", "1", "--artifact", str(artifact))
        assert seal_res.exit_code == 0
        result = _invoke(runner, project, "--json", "verify", "--strict")
        payload = json.loads(result.output)
        assert payload["ok"] is True
        phase1 = next(p for p in payload["phases"] if p["phase"] == 1)
        assert phase1["integrity_ok"] is True


# ── contract group ─────────────────────────────────────────────────────


class TestContractGroup:
    def test_contract_list_empty(self, runner, project):
        result = _invoke(runner, project, "--json", "contract", "list")
        payload = json.loads(result.output)
        assert payload["count"] == 0

    def test_contract_create_and_validate(self, runner, project, tmp_path):
        out = project / "contracts" / "v1" / "demo.yaml"
        result = _invoke(
            runner, project,
            "contract", "create",
            "--studio", "strategy",
            "--lane", "BC-DEMO-V1",
            "--objective", "demo contract",
            "--out", str(out),
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        val = _invoke(runner, project, "--json", "contract", "validate", str(out))
        assert val.exit_code == 0
        assert json.loads(val.output)["ok"] is True

    def test_contract_inspect(self, runner, project):
        out = project / "contracts" / "v1" / "demo.yaml"
        _invoke(
            runner, project,
            "contract", "create",
            "--studio", "strategy", "--lane", "BC-DEMO-V1",
            "--out", str(out),
        )
        result = _invoke(runner, project, "--json", "contract", "inspect", str(out))
        payload = json.loads(result.output)
        assert payload["studio"] == "strategy"
        assert payload["lane"] == "BC-DEMO-V1"


# ── archon group ───────────────────────────────────────────────────────


class TestArchon:
    def test_archon_plan(self, runner, project):
        result = _invoke(runner, project, "--json", "archon", "plan", "1")
        payload = json.loads(result.output)
        assert payload["phase"] == 1
        assert any(s["name"] == "seal" for s in payload["steps"])

    def test_archon_status_includes_ledger(self, runner, project):
        _invoke(runner, project, "init")
        _invoke(runner, project, "run", "1", "--dry-run")
        result = _invoke(runner, project, "--json", "archon", "status")
        payload = json.loads(result.output)
        assert len(payload["ledger_tail"]) >= 2  # run.start + run.finish


# ── review / questions / gaps ──────────────────────────────────────────


class TestReview:
    def test_questions_has_20(self, runner):
        result = runner.invoke(main, ["--json", "questions"])
        payload = json.loads(result.output)
        assert len(payload["questions"]) == 20

    def test_gaps_listed(self, runner):
        result = runner.invoke(main, ["--json", "gaps", "--all"])
        payload = json.loads(result.output)
        # Open gap list may be empty once G004 is resolved; --all still
        # returns the audit trail of closed gaps.
        assert "gaps" in payload
        assert payload.get("resolved")
        assert all("id" in g for g in payload["resolved"])

    def test_review_text(self, runner, project):
        result = _invoke(runner, project, "review")
        assert result.exit_code == 0
        assert "engineering questions" in result.output


# ── MCP serve help still works ─────────────────────────────────────────


class TestMCPHelp:
    def test_mcp_serve_help(self, runner):
        result = runner.invoke(main, ["mcp-serve", "--help"])
        assert result.exit_code == 0
        assert "MCP" in result.output or "mcp" in result.output.lower()


# ── keygen + public attestation verify (ed25519) ────────────────────────


class TestKeygenAndPublicVerify:
    """CLI tests for ed25519 keygen, --require-public, --public-key, and --spec."""

    # -- keygen --

    def test_keygen_writes_keys(self, runner, tmp_path):
        """keygen --out-dir creates private + public key files; priv is 0o600."""
        crypto = pytest.importorskip("cryptography")
        out_dir = tmp_path / "keys"
        out_dir.mkdir()
        result = _invoke(runner, tmp_path, "keygen", "--out-dir", str(out_dir))
        assert result.exit_code == 0, result.output
        # The command should have created at least two files in out_dir
        created = list(out_dir.iterdir())
        assert len(created) >= 2, f"expected ≥2 key files, got {created}"
        # Identify the private key (shorter name or .key extension) — check
        # permissions; the public key may be .pub or end with _public.
        priv_candidates = [f for f in created if "private" in f.name or "priv" in f.name or not f.suffix]
        pub_candidates = [f for f in created if "public" in f.name or "pub" in f.name or f.suffix == ".pub"]
        # Fallback: if naming is ambiguous, pick the two smallest files
        if not priv_candidates or not pub_candidates:
            by_size = sorted(created, key=lambda p: p.stat().st_size)
            priv_candidates = [by_size[0]]
            pub_candidates = [by_size[1]] if len(by_size) > 1 else []
        assert priv_candidates, "could not identify private key file"
        assert pub_candidates, "could not identify public key file"
        priv_file = priv_candidates[0]
        priv_mode = priv_file.stat().st_mode & 0o777
        assert priv_mode == 0o600, f"private key permissions {oct(priv_mode)} != 0o600"

    # -- verify --require-public --

    def test_verify_require_public_fails_without_sig(self, runner, project):
        """verify --require-public exits non-zero when packet lacks public_signature."""
        _invoke(runner, project, "init")
        # Seal phase 1 without any ed25519 signing (no --ed25519-key)
        artifact = project / "docs" / "evidence.txt"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("proof data")
        seal_res = _invoke(runner, project, "seal", "1", "--artifact", str(artifact))
        assert seal_res.exit_code == 0, seal_res.output
        # Verify with --require-public should fail — packet has no public_signature
        result = _invoke(runner, project, "verify", "--require-public")
        assert result.exit_code != 0, "expected non-zero exit for missing public_signature"
        # Should mention the failure reason
        assert "public" in result.output.lower() or "require" in result.output.lower()

    # -- verify --spec --

    def test_verify_with_spec_flag(self, runner, project):
        """verify --spec runs spec-bound verification on a spec-sealed proof."""
        from rigforge.proof import GateOutcome, ProofPacket
        from rigforge.spec import Spec, SpecBinding
        import secrets

        _invoke(runner, project, "init")

        # Write a spec file with two criteria
        spec_f = project / "spec.md"
        spec_f.write_text("## AC\n- [x] tests pass\n- [x] lint clean\n")

        # Create a sealed proof with matching gates via the spec-binding pattern
        key = secrets.token_bytes(32)
        gates = [
            GateOutcome(name="tests pass", passed=True),
            GateOutcome(name="lint clean", passed=True),
        ]
        packet = ProofPacket(
            phase=1, name="a", verifier="v", evidence="e", gates=gates,
            spec=SpecBinding.of(Spec.from_file(spec_f)),
        ).sealed(signing_key=key)
        proof_dir = project / "proofs"
        proof_dir.mkdir(parents=True, exist_ok=True)
        packet.write(proof_dir / "phase1_proof.json", signing_key=key)

        # verify --spec <spec_file> should pass (exit 0, spec=✅ shown for phase 1)
        result = _invoke(runner, project, "verify", "--spec", str(spec_f))
        assert result.exit_code == 0, result.output
        assert "spec=" in result.output

    # -- public sign + verify roundtrip --

    def test_public_sign_and_verify_roundtrip(self, runner, project):
        """keygen → seal → sign_packet → verify --public-key succeeds; tamper fails."""
        pytest.importorskip("cryptography")
        from rigforge.public_attest import generate_keypair, sign_packet
        from rigforge.proof import ProofPacket
        import json as _json

        _invoke(runner, project, "init")

        # Generate keys and write public key to a file
        private_bytes, public_hex = generate_keypair()
        pub_file = project / "signer.pub"
        pub_file.write_text(public_hex)

        # Seal phase 1 with an artifact
        artifact = project / "docs" / "evidence.txt"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("attested content")
        seal_res = _invoke(runner, project, "seal", "1", "--artifact", str(artifact))
        assert seal_res.exit_code == 0, seal_res.output

        # Load the sealed proof and sign it with ed25519
        proof_path = project / "proofs" / "phase1_proof.json"
        packet = ProofPacket.load(proof_path)
        signed_packet = sign_packet(packet, private_bytes)
        # Rewrite the proof file with the public attestation fields
        proof_path.write_text(_json.dumps(signed_packet.model_dump(mode="json"), indent=2))

        # verify --public-key <pubfile> should succeed
        result = _invoke(runner, project, "verify", "--public-key", str(pub_file))
        assert result.exit_code == 0, result.output
        assert "ok" in result.output.lower() or "pass" in result.output.lower() or "verify" in result.output.lower()

        # Tamper: flip a hex digit in public_signature → verify should fail
        raw = _json.loads(proof_path.read_text())
        sig = raw["public_signature"]
        flip_char = "0" if sig[0] != "0" else "1"
        raw["public_signature"] = flip_char + sig[1:]
        proof_path.write_text(_json.dumps(raw, indent=2))

        result_tampered = _invoke(runner, project, "verify", "--public-key", str(pub_file))
        assert result_tampered.exit_code != 0, "tampered signature should fail verification"
