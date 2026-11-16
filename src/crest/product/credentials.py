"""Provider credential storage for CREST 1.1.

On Windows, credentials are encrypted with DPAPI (``CryptProtectData``) under
the current user account and stored as ciphertext in SQLite.  A plaintext key
never enters settings, audit events, logs, API responses, or the database.

A portable AES-GCM fallback is used on non-Windows development machines.  It is
explicitly reported as weaker than DPAPI and is never used on Windows.
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wintypes
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any

from .db import Database, now_iso

MAX_KEY_LENGTH = 8192


class CredentialError(Exception):
    """Credential storage failed without exposing the secret."""


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi_available() -> bool:
    if os.name != "nt":
        return False
    try:
        ctypes.WinDLL("crypt32", use_last_error=True)
        return True
    except OSError:
        return False


def _blob(data: bytes) -> tuple[_DATA_BLOB, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _dpapi_protect(data: bytes, entropy: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    in_blob, in_buffer = _blob(data)
    entropy_blob, entropy_buffer = _blob(entropy)
    out_blob = _DATA_BLOB()
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "CREST provider credential",
        ctypes.byref(entropy_blob),
        None,
        None,
        0x1,  # CRYPTPROTECT_UI_FORBIDDEN
        ctypes.byref(out_blob),
    )
    _ = (in_buffer, entropy_buffer)
    if not ok:
        raise CredentialError(f"DPAPI protect failed ({ctypes.get_last_error()})")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(blob: bytes, entropy: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    in_blob, in_buffer = _blob(blob)
    entropy_blob, entropy_buffer = _blob(entropy)
    out_blob = _DATA_BLOB()
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        0x1,
        ctypes.byref(out_blob),
    )
    _ = (in_buffer, entropy_buffer)
    if not ok:
        raise CredentialError(
            "DPAPI could not decrypt the stored credential. It may belong to a "
            "different Windows user or machine. Re-enter the key."
        )
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


class _PortableCipher:
    """AES-GCM fallback for non-Windows development only."""

    def __init__(self, data_dir: Path):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:  # pragma: no cover - Windows uses DPAPI
            raise CredentialError(
                "credential encryption is unavailable: install cryptography or run on Windows"
            ) from exc
        self._AESGCM = AESGCM
        key_path = data_dir / "credentials.key"
        if key_path.exists():
            key = key_path.read_bytes()
        else:
            key = secrets.token_bytes(32)
            key_path.write_bytes(key)
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
        if len(key) != 32:
            raise CredentialError("credential key file is corrupt")
        self._key = key

    def encrypt(self, data: bytes, entropy: bytes) -> bytes:
        nonce = secrets.token_bytes(12)
        return nonce + self._AESGCM(self._key).encrypt(nonce, data, entropy)

    def decrypt(self, data: bytes, entropy: bytes) -> bytes:
        return self._AESGCM(self._key).decrypt(data[:12], data[12:], entropy)


def _entropy(provider_id: str) -> bytes:
    return f"CREST|provider-credential|{provider_id}".encode("utf-8")


class CredentialStore:
    def __init__(self, db: Database, data_dir: str | Path | None = None):
        self.db = db
        self.data_dir = Path(data_dir) if data_dir else db.path.parent
        self.backend = "dpapi" if _dpapi_available() else "aes-gcm-portable"
        self._portable = None if _dpapi_available() else _PortableCipher(self.data_dir)

    # --------------------------------------------------------------- crypto
    def _encrypt(self, provider_id: str, plaintext: str) -> tuple[bytes, str]:
        raw = plaintext.encode("utf-8")
        entropy = _entropy(provider_id)
        if self.backend == "dpapi":
            return _dpapi_protect(raw, entropy), "dpapi"
        assert self._portable is not None
        return self._portable.encrypt(raw, entropy), "aes-gcm-portable"

    def _decrypt(self, provider_id: str, ciphertext: bytes, method: str) -> str:
        entropy = _entropy(provider_id)
        if method == "dpapi":
            if not _dpapi_available():
                raise CredentialError("DPAPI credential cannot be read on this platform")
            raw = _dpapi_unprotect(ciphertext, entropy)
        elif method == "aes-gcm-portable":
            assert self._portable is not None
            raw = self._portable.decrypt(ciphertext, entropy)
        else:
            raise CredentialError("unknown credential storage method")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CredentialError("stored credential is corrupt") from exc

    # ---------------------------------------------------------------- store
    @staticmethod
    def _validate(api_key: str) -> str:
        if not isinstance(api_key, str):
            raise CredentialError("api_key must be a string")
        clean = api_key.strip()
        if not clean:
            raise CredentialError("api_key must not be empty")
        if len(clean) > MAX_KEY_LENGTH:
            raise CredentialError(f"api_key must be at most {MAX_KEY_LENGTH} characters")
        if any(ch in clean for ch in "\r\n\x00"):
            raise CredentialError("api_key must not contain control characters")
        return clean

    def set(self, provider_id: str, api_key: str) -> dict[str, Any]:
        clean = self._validate(api_key)
        ciphertext, method = self._encrypt(provider_id, clean)
        ts = now_iso()
        with self.db.tx() as conn:
            conn.execute(
                """INSERT INTO provider_credentials
                   (provider_id, ciphertext, method, created_at, updated_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(provider_id) DO UPDATE SET
                     ciphertext=excluded.ciphertext, method=excluded.method,
                     updated_at=excluded.updated_at""",
                (provider_id, sqlite3_binary(ciphertext), method, ts, ts),
            )
        return {"provider_id": provider_id, "configured": True, "method": method, "updated_at": ts}

    def get(self, provider_id: str) -> str | None:
        with self.db.read() as conn:
            row = conn.execute(
                "SELECT ciphertext, method FROM provider_credentials WHERE provider_id=?",
                (provider_id,),
            ).fetchone()
        if row is None:
            return None
        return self._decrypt(provider_id, bytes(row["ciphertext"]), str(row["method"]))

    def delete(self, provider_id: str) -> bool:
        with self.db.tx() as conn:
            cur = conn.execute(
                "DELETE FROM provider_credentials WHERE provider_id=?", (provider_id,)
            )
        return cur.rowcount > 0

    def has(self, provider_id: str) -> bool:
        with self.db.read() as conn:
            row = conn.execute(
                "SELECT 1 FROM provider_credentials WHERE provider_id=?", (provider_id,)
            ).fetchone()
        return row is not None

    def status(self) -> list[dict[str, Any]]:
        with self.db.read() as conn:
            rows = conn.execute(
                "SELECT provider_id, method, created_at, updated_at FROM provider_credentials ORDER BY provider_id"
            ).fetchall()
        return [
            {
                "provider_id": row["provider_id"],
                "configured": True,
                "method": row["method"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def key_status(self, provider_id: str, env_name: str = "") -> dict[str, Any]:
        stored = self.has(provider_id)
        env_present = bool(env_name and os.environ.get(env_name))
        return {
            "configured": stored or env_present,
            "source": "windows-dpapi" if stored else ("environment" if env_present else "none"),
            "storage_backend": self.backend,
            "environment_variable": env_name if env_present else "",
        }


def sqlite3_binary(value: bytes) -> Any:
    """Return a sqlite3-compatible binary value without importing globally."""
    import sqlite3

    return sqlite3.Binary(value)


def reset_portable_key(data_dir: str | Path) -> None:
    """Delete the portable fallback key (used by explicit data deletion)."""
    if sys.platform == "win32":
        return
    path = Path(data_dir) / "credentials.key"
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def describe_backend() -> dict[str, Any]:
    return {
        "backend": "dpapi" if _dpapi_available() else "aes-gcm-portable",
        "windows_dpapi": _dpapi_available(),
        "detail": (
            "Credentials are encrypted with Windows DPAPI for the current user."
            if _dpapi_available()
            else "Development fallback: AES-GCM with a local key file. Not used on Windows."
        ),
    }
