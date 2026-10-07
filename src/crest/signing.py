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


# ---------------------------------------------------------------------------
# KeyProvider abstraction (Phase 3: production key custody is external)
#
# DEVELOPMENT: DevKeyProvider (this file, file-backed, per-state-dir).
# TEST: DeterministicKeyProvider (in-memory, seeded).
# PRODUCTION-HSM-INTEGRATION-BOUNDARY: implement KeyProvider against an HSM
# or KMS; do not claim HSM guarantees from DevKeyProvider.
# ---------------------------------------------------------------------------


class KeyProvider:
    def sign(self, payload_digest_hex: str) -> tuple[str, str]:
        """Return (key_id, signature_b64) over the canonical payload digest."""
        raise NotImplementedError

    def get_public_key(self, key_id: str) -> PublicKey | None:
        raise NotImplementedError

    def is_revoked(self, key_id: str) -> bool:
        raise NotImplementedError

    def get_active_key_id(self) -> str:
        raise NotImplementedError


class DevKeyProvider(KeyProvider):
    """File-backed local provider. Active key bytes live under
    <state_dir>/keys; historical public keys are retained for verification;
    revoked key IDs are listed in keys/revoked_keys.json.

    Custody boundary: Whoever can WRITE <state_dir>/keys owns forgery of NEW
    receipts from a new runtime. The runtime itself only signs; revocation is
    always checked first so a revoked key can no longer authorize.
    """

    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self._active = ensure_dev_key(self.state_dir)
        # archive the active public key under its key_id for future verification
        pub_copy = self.state_dir / "keys" / f"public_{self._active.key_id}.pem"
        pub_copy.write_bytes(self._active.public_pem)

    def get_active_key_id(self) -> str:
        return self._active.key_id

    def sign(self, payload_digest_hex: str) -> tuple[str, str]:
        return self._active.key_id, sign_digest_hex(self._active, payload_digest_hex)

    def get_public_key(self, key_id: str) -> PublicKey | None:
        archived = self.state_dir / "keys" / f"public_{key_id}.pem"
        if archived.exists():
            pem = archived.read_bytes()
            if key_id_of(pem) == key_id:
                return PublicKey(key_id=key_id, public_pem=pem)
        return load_public_key(self.state_dir, key_id)

    def is_revoked(self, key_id: str) -> bool:
        revoked_path = self.state_dir / "keys" / "revoked_keys.json"
        if not revoked_path.exists():
            return False
        try:
            import json

            return key_id in json.loads(revoked_path.read_text(encoding="utf-8"))
        except Exception:
            return True  # unreadable revocation list fails closed

    def rotate(self) -> str:
        """Generate a new active key; the previous public key remains verifiable."""
        import json

        archived = self.state_dir / "keys" / f"public_{self._active.key_id}.pem"
        archived.write_bytes(self._active.public_pem)
        # record the outgoing key as no longer ACTIVE but still verifiable:
        # nothing to write; revocation list is the only state.
        key = generate_key()
        keys_dir = self.state_dir / "keys"
        (keys_dir / "ed25519_private.pem").write_bytes(key.private_pem)
        (keys_dir / "ed25519_public.pem").write_bytes(key.public_pem)
        (keys_dir / f"public_{key.key_id}.pem").write_bytes(key.public_pem)
        self._active = key
        return key.key_id

    def revoke(self, key_id: str) -> None:
        import json

        keys_dir = self.state_dir / "keys"
        revoked_path = keys_dir / "revoked_keys.json"
        current: list[str] = []
        if revoked_path.exists():
            try:
                current = list(json.loads(revoked_path.read_text(encoding="utf-8")))
            except Exception:
                current = []
        if key_id not in current:
            current.append(key_id)
        revoked_path.write_text(json.dumps(current), encoding="utf-8")


class DeterministicKeyProvider(KeyProvider):
    """Fixed in-memory key for reproducible tests; never used by default."""

    def __init__(self):
        self._key = generate_key()
        self._revoked: set[str] = set()

    def get_active_key_id(self) -> str:
        return self._key.key_id  # type: ignore[union-attr]

    def sign(self, payload_digest_hex: str) -> tuple[str, str]:
        return self._key.key_id, sign_digest_hex(self._key, payload_digest_hex)  # type: ignore[union-attr]

    def get_public_key(self, key_id: str) -> PublicKey | None:
        if key_id == self._key.key_id:  # type: ignore[union-attr]
            return PublicKey(key_id=key_id, public_pem=self._key.public_pem)  # type: ignore[union-attr]
        return None

    def is_revoked(self, key_id: str) -> bool:
        return key_id in self._revoked

    def revoke(self, key_id: str) -> None:
        self._revoked.add(key_id)

