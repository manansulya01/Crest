"""Capability receipts: typed, content-addressed evidence records.

A receipt is hash-bound to action class, target scope, recovery program,
verifier version, test configuration, and measured evidence. V0 uses
content-addressed hashing; no cryptographic signing is claimed.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .hashing import digest_of

RECEIPT_VERSION = "0.1"
STATUS_VERIFIED = "VERIFIED"
STATUS_FAILED = "FAILED"
STATUS_ERROR = "ERROR"


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


def _bound_payload(r: "CapabilityReceipt") -> dict[str, Any]:
    return {
        "receipt_version": r.receipt_version,
        "action_class": r.action_class,
        "target_scope": r.target_scope,
        "recovery_program_digest": r.recovery_program_digest,
        "verification_environment": r.verification_environment,
        "evidence_digest": r.evidence_digest,
        "verified_at": r.verified_at,
        "expires_at": r.expires_at,
        "status": r.status,
    }


@dataclass(frozen=True)
class CapabilityReceipt:
    receipt_version: str
    action_class: str
    target_scope: str
    recovery_program_digest: str
    verification_environment: str
    evidence: RecoveryEvidence
    verified_at: str
    expires_at: str
    status: str
    evidence_digest: str
    bound_digest: str

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
    ) -> "CapabilityReceipt":
        verified_at = now.astimezone(timezone.utc).isoformat()
        expires_at = (now.astimezone(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
        evidence_digest = evidence.digest()
        tmp = CapabilityReceipt(
            receipt_version=RECEIPT_VERSION,
            action_class=action_class,
            target_scope=target_scope,
            recovery_program_digest=recovery_program_digest,
            verification_environment=evidence.verification_environment,
            evidence=evidence,
            verified_at=verified_at,
            expires_at=expires_at,
            status=status,
            evidence_digest=evidence_digest,
            bound_digest="",
        )
        return CapabilityReceipt(**{**dataclasses.asdict(tmp), "evidence": evidence, "bound_digest": digest_of(_bound_payload(tmp))})

    def is_hash_valid(self) -> bool:
        if self.evidence.digest() != self.evidence_digest:
            return False
        return digest_of(_bound_payload(self)) == self.bound_digest

    def is_expired(self, now: datetime) -> bool:
        exp = datetime.fromisoformat(self.expires_at)
        return now.astimezone(timezone.utc) >= exp

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)
