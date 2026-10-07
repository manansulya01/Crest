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


class ReceiptStructureError(ValueError):
    """Raised when a receipt payload fails structural validation."""


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
    signature: str = ""
    signature_algorithm: str = ""
    key_id: str = ""

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
        expires = self._parse_ts(self.expires_at)
        if expires is None:
            raise ReceiptStructureError(f"malformed expires_at: {self.expires_at!r}")
        return now.astimezone(timezone.utc) >= expires

    @staticmethod
    def _parse_ts(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None
        if dt.tzinfo is None:
            return None
        return dt

    # ---------------- structural validation ----------------
    def structural_problems(self) -> list[str]:
        """Deterministic fail-closed validation of every required field.

        Returns a list of problem codes; empty means structurally sound.
        Never raises.
        """
        problems: list[str] = []
        if self.receipt_version != RECEIPT_VERSION:
            problems.append(f"UNKNOWN_RECEIPT_VERSION:{self.receipt_version}")
        if self.schema_version != SCHEMA_VERSION:
            problems.append(f"UNSUPPORTED_SCHEMA_VERSION:{self.schema_version}")
        for field_name in ("receipt_id", "action_class", "target_scope", "recovery_program_digest", "policy_version", "verifier_version"):
            value = getattr(self, field_name, None)
            if not isinstance(value, str) or not value:
                problems.append(f"MISSING_OR_INVALID:{field_name}")
        for field_name in ("issued_at", "expires_at"):
            if self._parse_ts(getattr(self, field_name, None)) is None:
                problems.append(f"MALFORMED_TIMESTAMP:{field_name}")
        issued = self._parse_ts(self.issued_at)
        expires = self._parse_ts(self.expires_at)
        if issued is not None and expires is not None and expires < issued:
            problems.append("EXPIRY_BEFORE_ISSUE")
        for field_name in ("evidence_digest", "payload_digest", "bound_digest"):
            value = getattr(self, field_name, None)
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                problems.append(f"MALFORMED_DIGEST:{field_name}")
        if self.status not in (STATUS_VERIFIED, STATUS_FAILED, STATUS_ERROR):
            problems.append(f"INVALID_STATUS:{self.status}")
        if not isinstance(self.revoked, bool):
            problems.append("INVALID_REVOKED_FLAG")
        ev = self.evidence
        if not isinstance(ev, RecoveryEvidence):
            problems.append("MISSING_EVIDENCE")
        else:
            if not isinstance(ev.test_count, int) or ev.test_count < 0:
                problems.append("INVALID_EVIDENCE:test_count")
            if not isinstance(ev.failed_tests, int) or ev.failed_tests < 0:
                problems.append("INVALID_EVIDENCE:failed_tests")
            for rate_name in ("recovery_success_rate", "residual_exposure_ucb"):
                v = getattr(ev, rate_name)
                if not isinstance(v, (int, float)) or isinstance(v, bool) or not (0.0 <= float(v) <= 1.0):
                    problems.append(f"INVALID_EVIDENCE:{rate_name}")
            for lat_name in ("recovery_latency_p50_ms", "recovery_latency_p95_ms", "recovery_latency_p99_ms"):
                v = getattr(ev, lat_name)
                if not isinstance(v, (int, float)) or isinstance(v, bool) or float(v) < 0:
                    problems.append(f"INVALID_EVIDENCE:{lat_name}")
            if not isinstance(ev.random_seed, int) or isinstance(ev.random_seed, bool):
                problems.append("INVALID_EVIDENCE:random_seed")
        for sig_field in ("signature", "signature_algorithm", "key_id"):
            value = getattr(self, sig_field, None)
            if not isinstance(value, str):
                problems.append(f"INVALID_SIGNATURE_FIELD:{sig_field}")
        if self.signature_algorithm and self.signature_algorithm != "Ed25519":
            problems.append(f"UNSUPPORTED_SIGNATURE_ALGORITHM:{self.signature_algorithm}")
        return problems

    def with_metadata(self, *, policy_version: str | None = None, verifier_version: str | None = None) -> "CapabilityReceipt":
        """Re-bind metadata and recompute all dependent digests."""
        updated = dataclasses.replace(
            self,
            policy_version=policy_version or self.policy_version,
            verifier_version=verifier_version or self.verifier_version,
        )
        payload_digest = updated.recompute_payload_digest()
        return dataclasses.replace(
            updated,
            payload_digest=payload_digest,
            bound_digest=digest_of({"payload_digest": payload_digest, "receipt_id": updated.receipt_id, "schema_version": updated.schema_version}),
        )

    def sign_with(self, key) -> "CapabilityReceipt":
        from . import signing

        signature = signing.sign_digest_hex(key, self.recompute_payload_digest())
        return dataclasses.replace(
            self,
            signature=signature,
            signature_algorithm=signing.ALGORITHM,
            key_id=key.key_id,
        )

    def signature_valid(self, public) -> bool:
        from . import signing

        if not self.signature or not self.signature_algorithm or not self.key_id:
            return False
        if self.signature_algorithm != signing.ALGORITHM or public.key_id != self.key_id:
            return False
        return signing.verify_digest_hex(public, self.recompute_payload_digest(), self.signature)

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

    # Extra fields the runtime legitimately attaches to the stored payload
    # after creation; anything else is attacker-controlled noise.
    _KNOWN_EXTRAS = {
        "recovery_program", "evidence_classification", "pinned_target",
        "pinned_target_meta", "generalization", "verification_measurement",
        "verification_seconds",
    }

    @classmethod
    def from_payload(cls, d: dict[str, Any]) -> "CapabilityReceipt":
        """Strict parse: unknown or missing fields are rejected outright."""
        if not isinstance(d, dict):
            raise ReceiptStructureError("payload is not an object")
        names = {f.name for f in dataclasses.fields(cls)}
        unknown = set(d) - names - cls._KNOWN_EXTRAS
        if unknown:
            raise ReceiptStructureError(f"unknown fields: {sorted(unknown)}")
        required = [
            f.name for f in dataclasses.fields(cls)
            if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
        ]
        missing = [n for n in required if n not in d]
        if missing:
            raise ReceiptStructureError(f"missing fields: {missing}")
        # explicit type enforcement on security-critical fields
        str_fields = ["receipt_id", "receipt_version", "issued_at", "action_class", "target_scope", "recovery_program_digest", "verification_environment", "verifier_version", "policy_version", "expires_at", "status", "evidence_digest", "payload_digest", "bound_digest", "signature", "signature_algorithm", "key_id"]
        for name in str_fields:
            if name in d and not isinstance(d[name], str):
                raise ReceiptStructureError(f"field {name} must be a string")
        if "schema_version" in d and (not isinstance(d["schema_version"], int) or isinstance(d["schema_version"], bool)):
            raise ReceiptStructureError("schema_version must be an integer")
        if "revoked" in d and not isinstance(d["revoked"], bool):
            raise ReceiptStructureError("revoked must be a boolean")
        ev = d.get("evidence")
        if not isinstance(ev, dict):
            raise ReceiptStructureError("evidence must be an object")
        ev_names = {f.name for f in dataclasses.fields(RecoveryEvidence)}
        unknown_ev = set(ev) - ev_names
        if unknown_ev:
            raise ReceiptStructureError(f"unknown evidence fields: {sorted(unknown_ev)}")
        missing_ev = ev_names - set(ev)
        if missing_ev:
            raise ReceiptStructureError(f"missing evidence fields: {sorted(missing_ev)}")
        try:
            return cls.from_dict(d)
        except (TypeError, ValueError) as exc:
            raise ReceiptStructureError(str(exc)) from exc

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)