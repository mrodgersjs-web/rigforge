"""Tests for rigforge.public_attest — ed25519 signing helpers.

Run with: pytest rigforge/tests/test_public_attest.py -v

Requires: ``pip install rigforge[public]`` (cryptography extra).
"""

from __future__ import annotations

import json
import pytest

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization

    HAS_CRYPTOGRAPHY = True
except ModuleNotFoundError:
    HAS_CRYPTOGRAPHY = False

from rigforge.proof import ArtifactRecord, GateOutcome, ProofPacket

if HAS_CRYPTOGRAPHY:
    from rigforge.public_attest import (
        generate_keypair,
        load_private_key,
        load_public_key_hex,
        sign,
        verify,
        sign_packet,
        verify_packet,
    )


# ---------------------------------------------------------------------------
# Skip entire module when cryptography is not installed
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not HAS_CRYPTOGRAPHY,
    reason="cryptography package not installed — pip install rigforge[public]",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def keypair():
    """Return (private_bytes, public_hex) from a fresh generate_keypair()."""
    return generate_keypair()


@pytest.fixture()
def sample_packet():
    """Return a minimal sealed ProofPacket for integration tests."""
    pkt = ProofPacket(
        phase=1,
        name="test-phase",
        verifier="test-agent",
        artifacts=[
            ArtifactRecord(path="src/main.py", sha256="aabb", size_bytes=42),
        ],
        gates=[
            GateOutcome(name="lint", passed=True),
        ],
    )
    return pkt.sealed(signing_key=b"test-hmac-key-32-bytes-long!!")


# ---------------------------------------------------------------------------
# Unit tests — key generation
# ---------------------------------------------------------------------------

class TestKeypair:
    def test_returns_tuple_of_bytes_and_hex(self, keypair):
        private_bytes, public_hex = keypair
        assert isinstance(private_bytes, bytes)
        assert isinstance(public_hex, str)

    def test_private_key_is_32_bytes(self, keypair):
        assert len(keypair[0]) == 32

    def test_public_hex_is_64_chars(self, keypair):
        assert len(keypair[1]) == 64
        # Must be valid hex
        bytes.fromhex(keypair[1])

    def test_two_calls_produce_different_keys(self):
        _, pub1 = generate_keypair()
        _, pub2 = generate_keypair()
        assert pub1 != pub2


# ---------------------------------------------------------------------------
# Unit tests — raw sign / verify
# ---------------------------------------------------------------------------

class TestSignVerify:
    def test_roundtrip(self, keypair):
        private_bytes, public_hex = keypair
        message = b"hello, rigforge"
        sig = sign(message, private_bytes)
        assert verify(message, sig, public_hex) is True

    def test_wrong_key_fails(self, keypair):
        private_bytes, _pub = keypair
        _, other_pub = generate_keypair()
        message = b"hello, rigforge"
        sig = sign(message, private_bytes)
        assert verify(message, sig, other_pub) is False

    def test_tampered_message_fails(self, keypair):
        private_bytes, public_hex = keypair
        sig = sign(b"original", private_bytes)
        assert verify(b"tampered", sig, public_hex) is False

    def test_signature_is_64_bytes(self, keypair):
        sig = sign(b"test", keypair[0])
        assert len(sig) == 64


# ---------------------------------------------------------------------------
# Unit tests — key loading
# ---------------------------------------------------------------------------

class TestKeyLoading:
    def test_load_private_key_roundtrip(self, keypair):
        private_bytes, _pub = keypair
        loaded = load_private_key(private_bytes)
        msg = b"roundtrip"
        sig = loaded.sign(msg)
        assert len(sig) == 64

    def test_load_public_key_hex_roundtrip(self, keypair):
        private_bytes, public_hex = keypair
        loaded_pub = load_public_key_hex(public_hex)
        msg = b"roundtrip"
        sig = Ed25519PrivateKey.from_private_bytes(private_bytes).sign(msg)
        loaded_pub.verify(sig, msg)


# ---------------------------------------------------------------------------
# Integration tests — ProofPacket
# ---------------------------------------------------------------------------

class TestPacketSigning:
    def test_sign_packet_populates_fields(self, sample_packet, keypair):
        private_bytes, expected_pub = keypair
        signed = sign_packet(sample_packet, private_bytes)
        assert signed.public_signature_algo == "ed25519"
        assert signed.public_signer == expected_pub
        assert len(signed.public_signature) == 128  # 64 bytes hex

    def test_verify_packet_passes(self, sample_packet, keypair):
        private_bytes, public_hex = keypair
        signed = sign_packet(sample_packet, private_bytes)
        assert verify_packet(signed, public_hex) is True

    def test_verify_packet_without_explicit_key(self, sample_packet, keypair):
        """Trust-on-first-use: packet's own public_signer is used."""
        private_bytes, _pub = keypair
        signed = sign_packet(sample_packet, private_bytes)
        assert verify_packet(signed) is True

    def test_verify_packet_wrong_key_fails(self, sample_packet, keypair):
        private_bytes, _pub = keypair
        signed = sign_packet(sample_packet, private_bytes)
        _, other_pub = generate_keypair()
        assert verify_packet(signed, other_pub) is False

    def test_sign_requires_sealed_packet(self, keypair):
        private_bytes, _pub = keypair
        unsealed = ProofPacket(phase=1, name="unsealed", verifier="test")
        with pytest.raises(ValueError, match="sealed"):
            sign_packet(unsealed, private_bytes)

    def test_verify_unsigned_packet_fails(self, sample_packet):
        assert verify_packet(sample_packet) is False


# ---------------------------------------------------------------------------
# Hash-exclusion invariant
# ---------------------------------------------------------------------------

class TestHashExclusion:
    """The public_* fields MUST NOT affect packet_sha256."""

    def test_hash_unchanged_by_public_fields(self, keypair):
        """Signing a packet must not change packet_sha256."""
        private_bytes, _pub = keypair
        base = ProofPacket(
            phase=2,
            name="hash-excl-test",
            verifier="test-agent",
        ).sealed()
        original_hash = base.packet_sha256

        signed = sign_packet(base, private_bytes)
        assert signed.packet_sha256 == original_hash

    def test_hash_ignores_public_fields_explicitly(self):
        """Manually setting public_* on an identical packet yields same hash."""
        from datetime import datetime, timezone
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        common = dict(phase=3, name="h", verifier="v", sealed_at=ts)
        pkt1 = ProofPacket(**common)
        pkt2 = ProofPacket(
            **common,
            public_signer="aabb",
            public_signature="ccdd",
            public_signature_algo="ed25519",
        )
        assert pkt1.compute_hash() == pkt2.compute_hash()

    def test_json_roundtrip_preserves_public_fields(self, sample_packet, keypair):
        """Writing and loading must keep public_* fields intact."""
        private_bytes, _pub = keypair
        signed = sign_packet(sample_packet, private_bytes)
        data = json.loads(signed.model_dump_json())
        loaded = ProofPacket.model_validate(data)
        assert loaded.public_signer == signed.public_signer
        assert loaded.public_signature == signed.public_signature
        assert loaded.public_signature_algo == signed.public_signature_algo
