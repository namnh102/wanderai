"""Session-wide offline, Python 3.11.9, no-network, and snapshot verification fixtures."""

from __future__ import annotations

import hashlib
import os
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

if sys.version_info[:2] != (3, 11):
    raise RuntimeError(
        f"Python 3.11 is required for W07 offline prep (never py/3.13); got {sys.version}"
    )

for _env_key in (
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
    "HF_DATASETS_OFFLINE",
    "PYTHONDONTWRITEBYTECODE",
):
    _val = os.environ.get(_env_key)
    if _val is not None and _val != "1":
        raise RuntimeError(
            f"Environment variable {_env_key} must be '1' (got {_val!r})"
        )
    os.environ[_env_key] = "1"

sys.dont_write_bytecode = True
os.environ["PYTHONHASHSEED"] = "0"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

PINNED_SNAPSHOT_ID = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
PINNED_TOKENIZER_SHA256 = (
    "2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8"
)
REAL_CORPUS_GATE_REASON = (
    "HOLD: awaiting G1.5 freeze, signed Owner authorization receipt, and verified "
    "frozen 137-doc corpus receipt (plain env vars cannot simulate Owner authority)"
)
REAL_CORPUS_STUB01_05_GATE_REASON = (
    "HOLD: Annex v0.2.2 technical spec is Owner chat-approved (e78013fd...), but "
    "STUB-01..STUB-05 real 137-doc execution awaits a separate Ed25519-signed Owner "
    "STUB-01..05 execution receipt and pinned live Owner public key (plain env vars rejected)"
)
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def is_real_corpus_stub01_05_authorized(
    *,
    requested_stub_id: str = "STUB-01",
    annex_v0_2_2_path: str | Path | None = None,
    tech_freeze_receipt_path: str | Path | None = None,
    stub_auth_receipt_path: str | Path | None = None,
    corpus_bundle_manifest_path: str | Path | None = None,
) -> bool:
    """Return True iff separate Owner STUB-01..05 read-only 137-doc receipt verification succeeds.

    CRITICAL GOVERNANCE RULE:
    Plain environment variables (W07_G15_FROZEN='1', W07_OWNER_AUTHORIZED='1',
    W07_STUB_01_05_AUTHORIZED='1') NEVER grant real-corpus execution authority.
    """
    from w07_retrieval.real_corpus_preflight import (
        PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX,
        validate_stub01_05_readonly_preflight_gate,
    )

    if PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX is None:
        return False

    annex_p = annex_v0_2_2_path or os.environ.get("W07_APPROVED_ANNEX_V022_PATH")
    freeze_rec_p = tech_freeze_receipt_path or os.environ.get(
        "W07_TECH_FREEZE_RECEIPT_PATH"
    )
    stub_rec_p = stub_auth_receipt_path or os.environ.get(
        "W07_STUB01_05_AUTH_RECEIPT_PATH"
    )
    bundle_p = corpus_bundle_manifest_path or os.environ.get(
        "W07_STUB01_05_BUNDLE_MANIFEST_PATH"
    )
    if not (annex_p and freeze_rec_p and stub_rec_p and bundle_p):
        return False

    try:
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id=requested_stub_id,
            annex_v0_2_2_path=Path(annex_p),
            tech_freeze_receipt_path=Path(freeze_rec_p),
            stub_auth_receipt_path=Path(stub_rec_p),
            corpus_bundle_manifest_path=Path(bundle_p),
        )
        return True
    except Exception:
        return False


def is_real_corpus_authorized(
    *,
    owner_auth_receipt_path: str | Path | None = None,
    frozen_corpus_receipt_path: str | Path | None = None,
    corpus_path: str | Path | None = None,
    queries_path: str | Path | None = None,
) -> bool:
    """Return True iff formal G1.5 freeze & signed Owner receipt verification succeed.

    CRITICAL GOVERNANCE RULE:
    Plain environment variables (W07_G15_FROZEN='1', W07_OWNER_AUTHORIZED='1')
    NEVER grant real-corpus execution authority on their own.
    """
    from w07_retrieval.runner import (
        PINNED_LIVE_OWNER_G3_PUBKEY_HEX,
        validate_formal_execution_gate,
    )

    if PINNED_LIVE_OWNER_G3_PUBKEY_HEX is None:
        return False

    owner_rec = owner_auth_receipt_path or os.environ.get("W07_OWNER_AUTH_RECEIPT_PATH")
    frozen_rec = frozen_corpus_receipt_path or os.environ.get(
        "W07_FROZEN_CORPUS_RECEIPT_PATH"
    )
    corp_p = corpus_path or os.environ.get("W07_FROZEN_CORPUS_PATH")
    quer_p = queries_path or os.environ.get("W07_FROZEN_QUERIES_PATH")
    if not (owner_rec and frozen_rec and corp_p and quer_p):
        return False

    try:
        validate_formal_execution_gate(
            corpus_path=Path(corp_p),
            queries_path=Path(quer_p),
            owner_auth_receipt_path=Path(owner_rec),
            frozen_corpus_receipt_path=Path(frozen_rec),
        )
        return True
    except Exception:
        return False


def pytest_configure(config: Any) -> None:
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError(
            f"Python 3.11 is required for W07 offline prep; got {sys.version}"
        )


def _extract_host(address: Any) -> str | None:
    if isinstance(address, tuple) and len(address) >= 1 and isinstance(address[0], str):
        return address[0]
    return None


@pytest.fixture(autouse=True, scope="session")
def block_outbound_network() -> Any:
    """Fail closed on any non-loopback socket connection during the test session."""
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_create_connection = socket.create_connection

    def _guarded_connect(self: socket.socket, address: Any) -> Any:
        host = _extract_host(address)
        if host is not None and host not in _LOOPBACK_HOSTS:
            raise RuntimeError(
                f"Network calls are forbidden in offline W07 prep (target={host!r})"
            )
        return orig_connect(self, address)

    def _guarded_connect_ex(self: socket.socket, address: Any) -> int:
        host = _extract_host(address)
        if host is not None and host not in _LOOPBACK_HOSTS:
            raise RuntimeError(
                f"Network calls are forbidden in offline W07 prep (target={host!r})"
            )
        return orig_connect_ex(self, address)

    def _guarded_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        host = _extract_host(address)
        if host is not None and host not in _LOOPBACK_HOSTS:
            raise RuntimeError(
                f"Network calls are forbidden in offline W07 prep (target={host!r})"
            )
        return orig_create_connection(address, *args, **kwargs)

    mp = pytest.MonkeyPatch()
    mp.setattr(socket.socket, "connect", _guarded_connect)
    mp.setattr(socket.socket, "connect_ex", _guarded_connect_ex)
    mp.setattr(socket, "create_connection", _guarded_create_connection)
    yield
    mp.undo()


@pytest.fixture(scope="session")
def snapshot_dir() -> Path:
    """Resolve and verify the local cached MiniLM HuggingFace snapshot."""
    env_dir = os.environ.get("W07_HF_SNAPSHOT_DIR")
    resolved = (
        Path(env_dir)
        if env_dir
        else Path.home()
        / ".cache"
        / "huggingface"
        / "hub"
        / "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
        / "snapshots"
        / PINNED_SNAPSHOT_ID
    )
    assert resolved.is_dir(), f"Missing cached snapshot directory: {resolved}"
    tok_json = resolved / "tokenizer.json"
    assert tok_json.is_file(), f"Missing tokenizer.json in {resolved}"
    actual_sha = hashlib.sha256(tok_json.read_bytes()).hexdigest()
    assert actual_sha == PINNED_TOKENIZER_SHA256, (
        f"tokenizer.json SHA-256 mismatch: expected {PINNED_TOKENIZER_SHA256}, got {actual_sha}"
    )
    return resolved
