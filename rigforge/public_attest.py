"""
Public attestation helpers — ed25519 signing for ProofPacket.

Wraps ``cryptography.hazmat.primitives.asymmetric.ed25519`` for
human-readable key/signature management.  The ``cryptography`` package is
**optional**: this module is usable only when installed via
``pip install rigforge[public]``.  Importing without the extra gives a clear
``ImportError``.

Public attestation sits *alongside* the existing HMAC-SHA256 signing
(``ProofPacket.signature``).  The HMAC protects the packet hash with a shared
secret; ed25519 provides asymmetric proof-of-signing that anyone can verify
with just the public key.  Both signatures cover the *same* ``packet_sha256``
but the ed25519 signature is **not** bound into the hash (it is metadata, not
part of the integrity payload — same as ``signature`` / ``signature_algo``).

Usage::

    from rigforge.public_attest import generate_keypair, sign_packet, verify_packet

    private_bytes, public_hex = generate_keypair()
    packet = packet.sealed(signing_key=shared_key)
    packet = sign_packet(packet, private_bytes)
    assert verify_packet(packet, public_hex)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — type stubs only
    from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Optional import gate
# ---------------------------------------------------------------------------

def _require_cryptography():
    """Import and return the cryptography primitives we need.

    Raises a clear ``ImportError`` with install instructions when the
    ``cryptography`` extra is missing.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
        from cryptography.hazmat.primitives import serialization
        return Ed25519PrivateKey, Ed25519PublicKey, serialization
    except ModuleNotFoundError:
        raise ModuleNotFoundError(
            "ed25519 attestation requires the 'cryptography' package. "
            "Install it with: pip install rigforge[public]"
        ) from None


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

def generate_keypair() -> tuple[bytes, str]:
    """Generate an ed25519 key pair.

    Returns
    -------
    private_bytes : bytes
        Raw 32-byte private (seed) key, ready for :func:`sign`.
    public_hex : str
        Hex-encoded 32-byte public key, suitable for storage in a
        ``ProofPacket.public_signer`` field.
    """
    Ed25519PrivateKey, Ed25519PublicKey, serialization = _require_cryptography()
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return private_bytes, public_bytes.hex()


def load_private_key(raw_bytes: bytes):
    """Reconstruct an ``Ed25519PrivateKey`` from raw 32-byte seed."""
    Ed25519PrivateKey, _Ed25519PublicKey, _serialization = _require_cryptography()
    return Ed25519PrivateKey.from_private_bytes(raw_bytes)


def load_public_key_hex(public_hex: str):
    """Reconstruct an ``Ed25519PublicKey`` from its hex encoding."""
    _Ed25519PrivateKey, Ed25519PublicKey, _serialization = _require_cryptography()
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex))


# ---------------------------------------------------------------------------
# Signing / verification
# ---------------------------------------------------------------------------

def sign(message: bytes, private_key_bytes: bytes) -> bytes:
    """Sign *message* with an ed25519 private key.  Returns 64-byte sig."""
    Ed25519PrivateKey, _pk, _ser = _require_cryptography()
    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    return private_key.sign(message)


def verify(message: bytes, signature: bytes, public_key_hex: str) -> bool:
    """Verify an ed25519 signature.  Returns True on success, False on failure."""
    _sk, Ed25519PublicKey, _ser = _require_cryptography()
    public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
    try:
        public_key.verify(signature, message)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Packet-level convenience
# ---------------------------------------------------------------------------

def sign_packet(packet, private_key_bytes: bytes):
    """Sign a ``ProofPacket`` with ed25519 and return a copy.

    The signature covers ``packet.packet_sha256`` (the same bytes the HMAC
    covers).  The ed25519 signature itself is stored in
    ``packet.public_signature`` and the public key fingerprint in
    ``packet.public_signer`` — both fields are **excluded** from the packet
    hash so signing does not invalidate integrity.

    Parameters
    ----------
    packet : ProofPacket
        Must already be sealed (``packet_sha256`` non-empty).
    private_key_bytes : bytes
        Raw 32-byte ed25519 private key seed.

    Returns
    -------
    ProofPacket
        Copy with ``public_signature``, ``public_signer``, and
        ``public_signature_algo`` populated.
    """
    if not packet.packet_sha256:
        raise ValueError("packet must be sealed before public signing (call .sealed() first)")
    Ed25519PrivateKey, _pk, _ser = _require_cryptography()
    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    msg = packet.packet_sha256.encode("utf-8")
    sig_bytes = private_key.sign(msg)
    public_hex = private_key.public_key().public_bytes(
        _ser.Encoding.Raw, _ser.PublicFormat.Raw
    ).hex()
    return packet.model_copy(
        update={
            "public_signature": sig_bytes.hex(),
            "public_signer": public_hex,
            "public_signature_algo": "ed25519",
        }
    )


def verify_packet(packet, public_key_hex: str | None = None) -> bool:
    """Verify the ed25519 signature on a ``ProofPacket``.

    Parameters
    ----------
    packet : ProofPacket
        Must have ``public_signature`` and ``public_signer`` set.
    public_key_hex : str, optional
        If provided, the signature is verified against *this* key and the
        packet's ``public_signer`` is checked to match.  If omitted, the
        packet's own ``public_signer`` is used (trust-on-first-use).

    Returns
    -------
    bool
        True if the signature is valid and the packet hash is intact.
    """
    _sk, Ed25519PublicKey, _ser = _require_cryptography()
    if not packet.public_signature or not packet.packet_sha256:
        return False
    sig_bytes = bytes.fromhex(packet.public_signature)
    msg = packet.packet_sha256.encode("utf-8")
    if public_key_hex is not None and public_key_hex != packet.public_signer:
        return False
    key_hex = public_key_hex or packet.public_signer
    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex))
        public_key.verify(sig_bytes, msg)
        return True
    except Exception:
        return False
