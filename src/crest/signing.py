"""Receipt signing: Ed25519 signatures over the canonical payload digest.

Uses the `cryptography` package (standard, audited library). No invented
primitives. Local development keys are generated per-state-directory and
marked as development keys; production key custody is external (documented
in docs/configuration.md and docs/security-review-v0.4.md).
"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

ALGORITHM = "Ed25519"


class SigningError(Exception):
    pass


@dataclass(frozen=True)
class SigningKey:
    key_id: str
    private_pem: bytes
    public_pem: bytes
    is_development_key: bool = True

    def private_key(self) -> Ed25519PrivateKey:
        return serialization.load_pem_private_key(self.private_pem, password=None)  # type: ignore[return-value]

    def public_bytes(self) -> bytes:
        return self.public_pem


@dataclass(frozen=True)
class PublicKey:
    key_id: str
    public_pem: bytes

    def verifying_key(self) -> Ed25519PublicKey:
        return serialization.load_pem_public_key(self.public_pem)  # type: ignore[return-value]


def key_id_of(public_pem: bytes) -> str:
    return hashlib.sha256(public_pem).hexdigest()[:16]


def generate_key() -> SigningKey:
    priv = Ed25519PrivateKey.generate()
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return SigningKey(key_id=key_id_of(pub_pem), private_pem=priv_pem, public_pem=pub_pem)


def ensure_dev_key(state_dir: Path) -> SigningKey:
    keys_dir = Path(state_dir) / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    priv_path = keys_dir / "ed25519_private.pem"
    pub_path = keys_dir / "ed25519_public.pem"
    if priv_path.exists() and pub_path.exists():
        priv_pem = priv_path.read_bytes()
        pub_pem = pub_path.read_bytes()
        return SigningKey(key_id=key_id_of(pub_pem), private_pem=priv_pem, public_pem=pub_pem)
    key = generate_key()
    priv_path.write_bytes(key.private_pem)
    pub_path.write_bytes(key.public_pem)
    try:
        priv_path.chmod(0o600)
    except OSError:
        pass
    return key


def sign_digest_hex(key: SigningKey, payload_digest_hex: str) -> str:
    sig = key.private_key().sign(payload_digest_hex.encode("ascii"))
    return base64.b64encode(sig).decode("ascii")


def verify_digest_hex(public: PublicKey, payload_digest_hex: str, signature_b64: str) -> bool:
    try:
        public.verifying_key().verify(base64.b64decode(signature_b64), payload_digest_hex.encode("ascii"))
        return True
    except Exception:
        return False


def load_public_key(state_dir: Path, key_id: str) -> PublicKey | None:
    pub_path = Path(state_dir) / "keys" / "ed25519_public.pem"
    if not pub_path.exists():
        return None
    pem = pub_path.read_bytes()
    if key_id_of(pem) != key_id:
        return None
    return PublicKey(key_id=key_id, public_pem=pem)
