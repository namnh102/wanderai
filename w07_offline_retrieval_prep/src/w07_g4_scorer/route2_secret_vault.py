"""Outside-repo Windows DPAPI (CurrentUser) API secret vault with zero secret echoing.

Stores OpenAI / Anthropic / Google / xAI API credentials encrypted at rest using Win32 DPAPI
(``CryptProtectData`` / ``CryptUnprotectData`` with ``CRYPTPROTECT_UI_FORBIDDEN``) outside all git
repositories, rejecting symlinks and NTFS reparse points. Never logs, prints, or persists
plaintext secret bytes or secret digests inside workspace artifacts.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import Any

from w07_g4_scorer.route2_aiproxy import (
    _assert_not_symlink_or_reparse,
    _assert_path_outside_repositories,
)

SECRET_VAULT_SCHEMA_VERSION = "GOMATE_W07_PROVIDER_SECRET_VAULT_V1"

SUPPORTED_SECRET_PROVIDERS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
    "xai": "XAI_API_KEY",
}

_PLACEHOLDER_PREFIXES: tuple[str, ...] = (
    "your-",
    "your_",
    "replace",
    "dummy",
    "placeholder",
    "test-",
    "changeme",
    "sk-dummy",
    "sk-ant-dummy",
)


def default_dpapi_vault_path() -> Path:
    """Return canonical per-user DPAPI secret vault path strictly outside all git repositories."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base and base.strip():
            return Path(base) / "GoMate_W07_Secrets" / "provider_secrets.dpapi.json"
        return Path.home() / "AppData" / "Local" / "GoMate_W07_Secrets" / "provider_secrets.dpapi.json"
    return Path.home() / ".config" / "gomate_w07_secrets" / "provider_secrets.json"


def is_plausible_api_secret(value: Any) -> bool:
    """Reject empty, whitespace-padded-only, malformed, or placeholder API keys."""
    if type(value) is not str:
        return False
    cleaned = value.strip()
    if len(cleaned) < 15 or any(ch.isspace() for ch in cleaned):
        return False
    low = cleaned.lower()
    if any(low.startswith(pref) for pref in _PLACEHOLDER_PREFIXES):
        return False
    if "xxx" in low or "your_api_key" in low:
        return False
    return True


def redact_secret_text(text: str, secret_values: Sequence[str] = ()) -> str:
    """Mask any known API secrets or token prefixes before constructing logs or error strings."""
    masked = text
    for sec in secret_values:
        if isinstance(sec, str) and len(sec) >= 8 and sec in masked:
            masked = masked.replace(sec, "[REDACTED_API_KEY]")
    return masked


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi_protect(plaintext: bytes) -> bytes:
    """Encrypt bytes using Win32 DPAPI CurrentUser scope without interactive UI prompts."""
    if os.name != "nt":
        return plaintext
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    in_buf = ctypes.create_string_buffer(plaintext, len(plaintext))
    in_blob = _DATA_BLOB(len(plaintext), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_ubyte)))
    out_blob = _DATA_BLOB()
    # CRYPTPROTECT_UI_FORBIDDEN = 0x1
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "GoMate_W07_Route2_Secret",
        None,
        None,
        None,
        0x1,
        ctypes.byref(out_blob),
    )
    if not ok:
        err = ctypes.get_last_error()
        raise OSError(err, f"WIN32_DPAPI_PROTECT_FAILED:err={err}")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(ciphertext: bytes) -> bytes:
    """Decrypt bytes previously sealed with Win32 DPAPI CurrentUser scope."""
    if os.name != "nt":
        return ciphertext
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    in_buf = ctypes.create_string_buffer(ciphertext, len(ciphertext))
    in_blob = _DATA_BLOB(len(ciphertext), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_ubyte)))
    out_blob = _DATA_BLOB()
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(out_blob),
    )
    if not ok:
        err = ctypes.get_last_error()
        raise OSError(err, f"WIN32_DPAPI_UNPROTECT_FAILED:err={err}")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _validate_external_vault_path(vault_path: Path) -> Path:
    if not isinstance(vault_path, Path):
        raise ValueError("vault_path must be a pathlib.Path")
    resolved = vault_path.resolve()
    _assert_path_outside_repositories(resolved)
    for anc in (resolved.parent, resolved):
        if anc.exists():
            _assert_not_symlink_or_reparse(anc)
    return resolved


def _load_vault_plaintext_map(vault_path: Path) -> dict[str, str]:
    target = _validate_external_vault_path(vault_path)
    if not target.is_file():
        return {}
    raw_doc = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw_doc, Mapping) or raw_doc.get("schema_version") != SECRET_VAULT_SCHEMA_VERSION:
        raise ValueError("INVALID_SECRET_VAULT_SCHEMA")
    backend = raw_doc.get("encryption_backend")
    if os.name == "nt":
        if backend != "WINDOWS_DPAPI_CURRENT_USER":
            raise PermissionError(f"UNENCRYPTED_VAULT_FORBIDDEN_ON_WINDOWS:{backend!r}")
        sealed = base64.b64decode(str(raw_doc["dpapi_ciphertext_b64"]).encode("ascii"))
        inner = _dpapi_unprotect(sealed)
    else:
        if backend != "POSIX_USER_CHMOD_0600_JSON":
            raise PermissionError(f"UNSUPPORTED_VAULT_BACKEND:{backend!r}")
        mode = target.stat().st_mode & 0o777
        if mode & 0o077:
            raise PermissionError(f"INSECURE_POSIX_SECRET_FILE_PERMISSIONS:{oct(mode)}")
        inner = base64.b64decode(str(raw_doc["payload_b64"]).encode("ascii"))
    parsed = json.loads(inner.decode("utf-8"))
    if not isinstance(parsed, Mapping):
        raise ValueError("CORRUPTED_SECRET_VAULT_PAYLOAD")
    return {str(k): str(v) for k, v in parsed.items() if isinstance(k, str) and isinstance(v, str)}


def seal_provider_secrets_dpapi(
    secrets_by_env_var: Mapping[str, str],
    *,
    vault_path: Path | None = None,
    merge_existing: bool = True,
) -> dict[str, Any]:
    """Seal provider API secrets outside git repositories using Win32 DPAPI (or 0600 POSIX)."""
    target = _validate_external_vault_path(vault_path or default_dpapi_vault_path())
    allowed_env_vars = set(SUPPORTED_SECRET_PROVIDERS.values())
    current: dict[str, str] = _load_vault_plaintext_map(target) if (merge_existing and target.is_file()) else {}

    for env_var, raw_val in secrets_by_env_var.items():
        if env_var not in allowed_env_vars:
            raise ValueError(f"UNSUPPORTED_SECRET_ENV_VAR:{env_var!r}")
        cleaned = raw_val.strip()
        if not is_plausible_api_secret(cleaned):
            raise ValueError(f"INVALID_OR_PLACEHOLDER_SECRET:{env_var}")
        current[env_var] = cleaned

    if not current:
        raise ValueError("NO_VALID_SECRETS_PROVIDED_TO_SEAL")

    target.parent.mkdir(parents=True, exist_ok=True)
    _assert_not_symlink_or_reparse(target.parent)
    if os.name != "nt":
        os.chmod(target.parent, 0o700)

    inner_bytes = json.dumps(current, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if os.name == "nt":
        sealed = _dpapi_protect(inner_bytes)
        envelope = {
            "schema_version": SECRET_VAULT_SCHEMA_VERSION,
            "encryption_backend": "WINDOWS_DPAPI_CURRENT_USER",
            "configured_vars": sorted(current.keys()),
            "dpapi_ciphertext_b64": base64.b64encode(sealed).decode("ascii"),
        }
    else:
        envelope = {
            "schema_version": SECRET_VAULT_SCHEMA_VERSION,
            "encryption_backend": "POSIX_USER_CHMOD_0600_JSON",
            "configured_vars": sorted(current.keys()),
            "payload_b64": base64.b64encode(inner_bytes).decode("ascii"),
        }

    tmp_p = target.with_suffix(".tmp")
    raw_out = (json.dumps(envelope, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    with tmp_p.open("wb") as fh:
        fh.write(raw_out)
        fh.flush()
        os.fsync(fh.fileno())
    if os.name != "nt":
        os.chmod(tmp_p, 0o600)
    os.replace(tmp_p, target)
    if os.name != "nt":
        os.chmod(target, 0o600)

    return {
        "vault_path": str(target),
        "encryption_backend": envelope["encryption_backend"],
        "outside_repositories": True,
        "providers_configured": {
            prov: (env_name in current) for prov, env_name in sorted(SUPPORTED_SECRET_PROVIDERS.items())
        },
        "secret_values_exposed": False,
    }


def import_dotenv_to_dpapi_vault(
    dotenv_path: Path,
    *,
    vault_path: Path | None = None,
    providers: Sequence[str] = ("openai", "anthropic", "google"),
) -> dict[str, Any]:
    """Read supported provider keys locally from a dotenv file and seal them into the external DPAPI vault."""
    if not dotenv_path.is_file():
        raise FileNotFoundError(f"DOTENV_FILE_NOT_FOUND:{dotenv_path}")
    wanted_vars = {SUPPORTED_SECRET_PROVIDERS[p] for p in providers}
    extracted: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k in wanted_vars and is_plausible_api_secret(v):
            extracted[k] = v
    if not extracted:
        raise ValueError(f"NO_SUPPORTED_VALID_SECRETS_IN_DOTENV:{sorted(wanted_vars)}")
    return seal_provider_secrets_dpapi(extracted, vault_path=vault_path, merge_existing=True)


def resolve_provider_secret(
    provider: str,
    *,
    vault_path: Path | None = None,
    prefer_env: bool = True,
) -> str:
    """Resolve a provider API key in memory from process env or outside-repo DPAPI vault without printing it."""
    if provider not in SUPPORTED_SECRET_PROVIDERS:
        raise ValueError(f"UNSUPPORTED_SECRET_PROVIDER:{provider!r}")
    env_var = SUPPORTED_SECRET_PROVIDERS[provider]
    if prefer_env:
        env_val = os.environ.get(env_var)
        if env_val and is_plausible_api_secret(env_val):
            return env_val.strip()

    target = vault_path or default_dpapi_vault_path()
    if target.is_file():
        mapping = _load_vault_plaintext_map(target)
        sec = mapping.get(env_var)
        if sec and is_plausible_api_secret(sec):
            return sec.strip()

    if not prefer_env:
        env_val = os.environ.get(env_var)
        if env_val and is_plausible_api_secret(env_val):
            return env_val.strip()

    raise PermissionError(f"HOLD_PROVIDER_SECRET_UNSET_IN_ENV_AND_DPAPI_VAULT:{provider}:{env_var}")


@contextmanager
def scoped_vault_env_for_providers(
    providers: Sequence[str],
    *,
    vault_path: Path | None = None,
) -> Iterator[dict[str, bool]]:
    """Temporarily project DPAPI-sealed provider keys into process env ONLY in memory, restoring on exit."""
    target = vault_path or default_dpapi_vault_path()
    snapshot: dict[str, str | None] = {}
    projected: dict[str, bool] = {}
    try:
        for prov in providers:
            env_var = SUPPORTED_SECRET_PROVIDERS[prov]
            snapshot[env_var] = os.environ.get(env_var)
            cur = snapshot[env_var]
            if cur and is_plausible_api_secret(cur):
                projected[prov] = True
                continue
            secret = resolve_provider_secret(prov, vault_path=target, prefer_env=True)
            os.environ[env_var] = secret
            projected[prov] = True
        yield projected
    finally:
        for env_var, prior in snapshot.items():
            if prior is None:
                os.environ.pop(env_var, None)
            else:
                os.environ[env_var] = prior


def inspect_provider_secret_posture(
    *,
    vault_path: Path | None = None,
    legacy_dotenv_path: Path | None = None,
) -> dict[str, Any]:
    """Report boolean secret configuration posture across env, external DPAPI vault, and legacy dotenv."""
    target = vault_path or default_dpapi_vault_path()
    _assert_path_outside_repositories(target.resolve())
    vault_configured: set[str] = set()
    vault_status = "UNPROVISIONED"
    if target.is_file():
        try:
            vault_configured = set(_load_vault_plaintext_map(target).keys())
            vault_status = "DPAPI_SEALED_VALID" if os.name == "nt" else "POSIX_0600_VALID"
        except Exception as exc:
            vault_status = f"VAULT_READ_ERROR:{type(exc).__name__}"

    dotenv_detected: set[str] = set()
    if legacy_dotenv_path is not None and legacy_dotenv_path.is_file():
        for raw_line in legacy_dotenv_path.read_text(encoding="utf-8").splitlines():
            ln = raw_line.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k in SUPPORTED_SECRET_PROVIDERS.values() and is_plausible_api_secret(v):
                dotenv_detected.add(k)

    providers_posture: dict[str, Any] = {}
    for prov, env_var in sorted(SUPPORTED_SECRET_PROVIDERS.items()):
        in_env = is_plausible_api_secret(os.environ.get(env_var))
        in_vault = env_var in vault_configured
        in_legacy = env_var in dotenv_detected
        providers_posture[prov] = {
            "env_var": env_var,
            "configured_in_process_env": in_env,
            "configured_in_external_dpapi_vault": in_vault,
            "detected_in_legacy_repo_dotenv": in_legacy,
            "secure_runtime_ready": in_env or in_vault,
        }

    return {
        "schema_version": "GOMATE_W07_SECRET_POSTURE_REPORT_V1",
        "vault_path": str(target),
        "vault_status": vault_status,
        "legacy_dotenv_path": str(legacy_dotenv_path) if legacy_dotenv_path is not None else None,
        "legacy_repo_dotenv_security_note": (
            "IN_REPO_PLAINTEXT_DOTENV_DETECTED_MIGRATE_TO_DPAPI_VAULT" if dotenv_detected else "NO_LEGACY_DOTENV_KEYS"
        ),
        "providers": providers_posture,
        "secret_values_exposed": False,
    }
