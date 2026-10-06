"""Receipt format v2: explicit digests, canonical serialization, replay fields.

Content integrity (hash binding) is implemented. Cryptographic authenticity
is NOT implemented: there is no signature, and none is claimed.
"""
from __future__ import annotations

import dataclasses
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .hashing import canonical_bytes, digest_of

RECEIPT_VERSION = "2.0"
SCHEMA_VERSION = 2
STATUS_VERIFIED = "VERIFIED"
STATUS_FAILED = "FAILED"
STATUS_ERROR = "ERROR"


def canonical_json(obj: Any) -> str:
    """Stable serialization used for every digest. Dict ordering never
    matters; only the canonical form is hashed."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=_default)


def _default(o: Any) -> Any:
    if isinstance(o, (bytes, bytearray)):
        return o.hex()
    if hasattr(o, "value"):
        return o.value
    raise TypeError(f"not serializable: {type(o)!r}")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RecoveryEvidence:
    test_count: int
    failed_tests: int
    recovery_success_rate: float
    recovery_latency_p50_ms: float
    recovery_latency_p95_ms: float
    recovery_latency_p99_ms: float
    residual_exposure_ucb: float
    propagation_depth: int
    verification_environment: str
    verification_version: str
    test_config_digest: str
    random_seed: int

    def digest(self) -> str:
        return digest_of(dataclasses.asdict(self))


@dataclass(frozen=True)
class CapabilityReceipt:
    receipt_id: str
    receipt_version: str
    schema_version: int
    issued_at: str
    action_class: str
    target_scope: str
    recovery_program_digest: str
    verification_environment: str
    verifier_version: str
    policy_version: str
    evidence: RecoveryEvidence
    expires_at: str
    status: str
    evidence_digest: str
    payload_digest: str
    bound_digest: str
    revoked: bool = False

    # ---------------- construction ----------------
    @staticmethod
    def create(
        *,
        action_class: str,
        target_scope: str,
        recovery_program_digest: str,
        evidence: RecoveryEvidence,
        status: str,
        now: datetime,
        ttl_seconds: float,
        verifier_version: str = "unknown",
        policy_version: str = "policy-v1",
        receipt_id: str | None = None,
    ) -> "CapabilityReceipt":
        issued = now.astimezone(timezone.utc)
        issued_at = issued.isoformat()
        expires_at = (issued + timedelta(seconds=ttl_seconds)).isoformat()
        evidence_digest = evidence.digest()
        payload = {
            "action_class": action_class,
            "target_scope": target_scope,
            "recovery_program_digest": recovery_program_digest,
            "verification_environment": evidence.verification_environment,
            "verifier_version": verifier_version,
            "policy_version": policy_version,
            "evidence_digest": evidence_digest,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "status": status,
            "schema_version": SCHEMA_VERSION,
            "receipt_version": RECEIPT_VERSION,
        }
        payload_digest = digest_of(payload)
        final_id = receipt_id or uuid.uuid4().hex
        return CapabilityReceipt(
            receipt_id=final_id,
            receipt_version=RECEIPT_VERSION,
            schema_version=SCHEMA_VERSION,
            issued_at=issued_at,
            action_class=action_class,
            target_scope=target_scope,
            recovery_program_digest=recovery_program_digest,
            verification_environment=evidence.verification_environment,
            verifier_version=verifier_version,
            policy_version=policy_version,
            evidence=evidence,
            expires_at=expires_at,
            status=status,
            evidence_digest=evidence_digest,
            payload_digest=payload_digest,
            bound_digest=digest_of({"payload_digest": payload_digest, "receipt_id": final_id, "schema_version": SCHEMA_VERSION}),
            revoked=False,
        )

    # ---------------- integrity ----------------
    def recompute_payload_digest(self) -> str:
        return digest_of(
            {
                "action_class": self.action_class,
                "target_scope": self.target_scope,
                "recovery_program_digest": self.recovery_program_digest,
                "verification_environment": self.verification_environment,
                "verifier_version": self.verifier_version,
                "policy_version": self.policy_version,
                "evidence_digest": self.evidence_digest,
                "issued_at": self.issued_at,
                "expires_at": self.expires_at,
                "status": self.status,
                "schema_version": self.schema_version,
                "receipt_version": self.receipt_version,
            }
        )

    def is_hash_valid(self) -> bool:
        if self.evidence.digest() != self.evidence_digest:
            return False
        if self.recompute_payload_digest() != self.payload_digest:
            return False
        return digest_of({"payload_digest": self.payload_digest, "receipt_id": self.receipt_id, "schema_version": self.schema_version}) == self.bound_digest

    def is_expired(self, now: datetime) -> bool:
        return now.astimezone(timezone.utc) >= datetime.fromisoformat(self.expires_at)

    def canonical_payload(self) -> str:
        return canonical_json(self.to_dict())

    # ---------------- serialization ----------------
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CapabilityReceipt":
        names = {f.name for f in dataclasses.fields(cls)}
        d = {k: v for k, v in d.items() if k in names}
        if "evidence" in d and isinstance(d["evidence"], dict):
            d["evidence"] = RecoveryEvidence(**d["evidence"])
        return cls(**d)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)