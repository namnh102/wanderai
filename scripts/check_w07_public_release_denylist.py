#!/usr/bin/env python3
"""Authoritative Standalone Trusted Publication Boundary Verifier for GoMate / WanderAI W07 (`v2.0.0`).

Parent Task: `W07-KEY-PIN-MIGRATION-IMPLEMENTATION-01`
Corrective:  `W07-KEY-PIN-MIGRATION-TRUSTED-PUBLICATION-BOUNDARY-CORRECTIVE-01`
Closes:      `PUB-R1-TRUST-01`, `PUB-R1-OWNER-02`, `PUB-R1-CI-03`, and `PUB-R1-PUBLISH-04`.

CRITICAL TRUST-BOUNDARY INVARIANTS:
  1. ZERO CANDIDATE CODE EXECUTION (`PUB-R1-TRUST-01`):
     - Standalone zero-dependency executable with embedded pure-Python RFC 8032 Ed25519 VERIFICATION ONLY
       (zero keygen or signing functions, zero imports from `--root` / `--candidate-root`).
     - In authoritative mode (`--require-external-trusted-verifier`), immediately FAILS CLOSED
       (`CANDIDATE_SELF_EXECUTION_FORBIDDEN`, `EXIT 1`) if `__file__` resides inside `--root`.
     - Supports `--git-objects-only` (`git diff --raw` + `git cat-file -p <commit>:<path>`) so candidate PR
       commits are inspected as inert Git objects without checking out or executing PR code.
  2. CRYPTOGRAPHIC PINNED OWNER TRUST ANCHOR (`PUB-R1-OWNER-02`):
     - Unsigned external approval JSON is ALWAYS rejected (`UNSIGNED_EXTERNAL_APPROVAL_JSON_FORBIDDEN`, `EXIT 1`).
     - Signatures verified only against a public key self-declared inside the approval JSON are ALWAYS rejected
       (`SELF_DECLARED_PUBKEY_WITHOUT_TRUSTED_ANCHOR_FORBIDDEN` / `ROGUE_SELF_SIGNED_APPROVAL_PUBKEY_MISMATCH`, `EXIT 1`).
     - Live Owner trust anchor `PINNED_LIVE_PUBLICATION_OWNER_ED25519_PUBKEY_HEX` is currently `None`
       (unprovisioned) -> live W07 gate deterministically returns `LIVE_HOLD`
       (`HOLD_UNPROVISIONED_OWNER_PUBLICATION_TRUST_ANCHOR`, `EXIT 2`).
     - Offline automated tests must supply `EphemeralSandboxPublicationTrustAnchor`
       (`--ephemeral-sandbox-owner-pubkey-hex`), which forces `evaluation_scope = "DISPOSABLE_TEST_SANDBOX"`,
       `verdict_class = "PASS_TESTED_OFFLINE"`, and `live_publication_authorized = False`.
  3. CLEAN TWO-TIER `develop` PR APPLICABILITY (`PUB-R1-CI-03`):
     - Universal Step 1 runs on 100% of PRs into `develop` (blocking restricted paths, `.sig`/`.key`, withheld
       baseline/quarantined SHA-256s, personal user-profile paths, local drive paths, secrets, symlinks, gitlinks).
     - Step 2 classifies PRs touching any W07 governed or gate-protected path (`tools/w07_stage1/**`,
       `scripts/check_w07_public_release_denylist.py`, `.github/workflows/w07_key_pin_public_ci.yml`,
       `tests/test_w07_*`, `docs/research/*w07*`, `data/*/w07/**`) as `W07_GOVERNED_OR_GATE_PROTECTED_PR` and
       requires exact 100%-of-PR-files match against the Owner Ed25519-signed V2 approval record.
     - Ordinary unrelated product PRs touching zero W07/gate paths pass Step 1 with
       `PASS_NON_W07_RESTRICTED_SCAN_ONLY_NOT_W07_APPROVED` (`w07_release_approved = False`).
  4. SAFE FIRST PUBLICATION (`PUB-R1-PUBLISH-04`):
     - Generates & verifies an offline exact-byte pre-publication manifest from outside the repository before
       any `git push`, auditing hidden/dotfiles, excluded `DEV-5`/`DEV-6`/`T0`/host metadata, frozen hashes,
       and `origin/develop` SHA.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

TOOL_VERSION = "2.0.0-trusted-publication-boundary"
DEFAULT_ALLOWLIST_REL_PATH = "tools/w07_stage1/schemas/w07_public_safe_release_allowlist_v1.json"
IN_REPO_BOOTSTRAP_VERIFIER_REL_PATH = "scripts/check_w07_public_release_denylist.py"
GATE_WORKFLOW_REL_PATH = ".github/workflows/w07_key_pin_public_ci.yml"

# ============================================================================
# LIVE OWNER PUBLICATION TRUST ANCHOR (UNPROVISIONED -> LIVE_HOLD)
# ============================================================================
PINNED_LIVE_PUBLICATION_OWNER_ED25519_PUBKEY_HEX: str | None = None

DISCLOSED_TEST_ONLY_PUBKEYS_HEX: frozenset[str] = frozenset(
    {
        "ce4b82ee91f158407b88179213532862cf413b151e62c2075724435e40b6b157",
        "f133307cd8c605fb177e31267bc21509edf4275d63c2df3b14b2a008e741750c",
    }
)
FORBIDDEN_TOY_HEX64: frozenset[str] = frozenset(
    {"0" * 64, "f" * 64, "a" * 64, "1" * 64, "deadbeef" * 8}
)

HEX40_RE = re.compile(r"\A[0-9a-f]{40}\Z")
HEX64_RE = re.compile(r"\A[0-9a-f]{64}\Z")
HEX128_RE = re.compile(r"\A[0-9a-f]{128}\Z")
ISO_DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")

MIN_PLAUSIBLE_LIVE_UTC_DATE = _dt.date(2026, 11, 19)
MAX_PLAUSIBLE_UTC_DATE = _dt.date(2100, 12, 31)
MAX_APPROVAL_WINDOW_DAYS = 14
FORBIDDEN_CLOCK_TAMPER_ENV_VARS: tuple[str, ...] = (
    "FAKETIME",
    "FAKETIME_FMT",
    "FAKETIME_TIMESTAMP_FILE",
    "W07_OVERRIDE_UTC_DATE",
    "W07_FAKE_CLOCK",
    "W07_REFERENCE_UTC_DATE",
)

ED25519_DOMAIN_PUBLIC_RELEASE_APPROVAL_V2 = b"W07-PUBLIC-RELEASE-APPROVAL-V2\x00"

# ============================================================================
# EMBEDDED PURE-PYTHON RFC 8032 ED25519 VERIFIER (VERIFY-ONLY; 0 KEYGEN/SIGN)
# ============================================================================
_ED25519_P = 2**255 - 19
_ED25519_L = 2**252 + 27742317777372353535851937790883648493
_ED25519_D = (-121665 * pow(121666, _ED25519_P - 2, _ED25519_P)) % _ED25519_P
_ED25519_I = pow(2, (_ED25519_P - 1) // 4, _ED25519_P)


def _ed25519_xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_ED25519_D * y * y + 1, _ED25519_P - 2, _ED25519_P) % _ED25519_P
    x = pow(xx, (_ED25519_P + 3) // 8, _ED25519_P)
    if (x * x - xx) % _ED25519_P != 0:
        x = (x * _ED25519_I) % _ED25519_P
    if (x * x - xx) % _ED25519_P != 0:
        raise ValueError("ED25519_POINT_NOT_ON_CURVE")
    if x & 1:
        x = _ED25519_P - x
    return x


_ED25519_BY = 4 * pow(5, _ED25519_P - 2, _ED25519_P) % _ED25519_P
_ED25519_BX = _ed25519_xrecover(_ED25519_BY)
_ED25519_B = (_ED25519_BX, _ED25519_BY, 1, (_ED25519_BX * _ED25519_BY) % _ED25519_P)
_ED25519_IDENTITY_ENCODED = (1).to_bytes(32, "little")


def _ed25519_add(
    p1: tuple[int, int, int, int],
    p2: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = (y1 - x1) * (y2 - x2) % _ED25519_P
    b = (y1 + x1) * (y2 + x2) % _ED25519_P
    c = 2 * t1 * t2 * _ED25519_D % _ED25519_P
    d = 2 * z1 * z2 % _ED25519_P
    e = (b - a) % _ED25519_P
    f = (d - c) % _ED25519_P
    g = (d + c) % _ED25519_P
    h = (b + a) % _ED25519_P
    return (e * f % _ED25519_P, g * h % _ED25519_P, f * g % _ED25519_P, e * h % _ED25519_P)


def _ed25519_mul(pt: tuple[int, int, int, int], scalar: int) -> tuple[int, int, int, int]:
    res = (0, 1, 1, 0)
    cur = pt
    e = scalar
    while e > 0:
        if e & 1:
            res = _ed25519_add(res, cur)
        cur = _ed25519_add(cur, cur)
        e >>= 1
    return res


def _ed25519_encode(pt: tuple[int, int, int, int]) -> bytes:
    x, y, z, _ = pt
    zi = pow(z, _ED25519_P - 2, _ED25519_P)
    x = (x * zi) % _ED25519_P
    y = (y * zi) % _ED25519_P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _ed25519_decode(raw32: bytes) -> tuple[int, int, int, int]:
    if len(raw32) != 32:
        raise ValueError("ED25519_INVALID_POINT_LENGTH")
    n = int.from_bytes(raw32, "little")
    y = n & ((1 << 255) - 1)
    x_sign = n >> 255
    if y >= _ED25519_P:
        raise ValueError("ED25519_NON_CANONICAL_Y")
    x = _ed25519_xrecover(y)
    if x == 0 and x_sign == 1:
        raise ValueError("ED25519_INVALID_NEGATIVE_ZERO_X")
    if (x & 1) != x_sign:
        x = _ED25519_P - x
    pt = (x, y, 1, (x * y) % _ED25519_P)
    if _ed25519_encode(pt) != raw32:
        raise ValueError("ED25519_NON_CANONICAL_POINT")
    return pt


def assert_valid_ed25519_pubkey_hex(pubkey_hex: Any, *, field_name: str, reject_disclosed_test_keys: bool = True) -> str:
    if type(pubkey_hex) is not str or HEX64_RE.fullmatch(pubkey_hex) is None:
        raise ValueError(f"INVALID_ED25519_PUBKEY_HEX on {field_name}: {pubkey_hex!r}")
    if pubkey_hex in FORBIDDEN_TOY_HEX64:
        raise ValueError(f"FORBIDDEN_TOY_PUBKEY_HEX on {field_name}")
    if reject_disclosed_test_keys and pubkey_hex in DISCLOSED_TEST_ONLY_PUBKEYS_HEX:
        raise ValueError(f"DISCLOSED_TEST_PUBKEY_FORBIDDEN on {field_name}")
    pt = _ed25519_decode(bytes.fromhex(pubkey_hex))
    if _ed25519_encode(_ed25519_mul(pt, 8)) == _ED25519_IDENTITY_ENCODED:
        raise ValueError(f"SMALL_ORDER_ED25519_PUBKEY_FORBIDDEN on {field_name}")
    return pubkey_hex


def verify_detached_ed25519_hex(
    *,
    pubkey_hex: str,
    domain_tag: bytes,
    payload_bytes: bytes,
    signature_hex: Any,
    context_label: str,
) -> None:
    clean_pk = assert_valid_ed25519_pubkey_hex(pubkey_hex, field_name=f"{context_label}.pubkey", reject_disclosed_test_keys=True)
    if type(signature_hex) is not str:
        raise ValueError(f"MISSING_DETACHED_SIGNATURE on {context_label}")
    sig_clean = signature_hex.strip()
    if HEX128_RE.fullmatch(sig_clean) is None:
        raise ValueError(f"MALFORMED_DETACHED_SIGNATURE_HEX128 on {context_label}")
    raw_sig = bytes.fromhex(sig_clean)
    r_bytes, s_bytes = raw_sig[:32], raw_sig[32:]
    s_int = int.from_bytes(s_bytes, "little")
    if s_int >= _ED25519_L:
        raise ValueError(f"NON_CANONICAL_SIGNATURE_SCALAR on {context_label}")
    a_pt = _ed25519_decode(bytes.fromhex(clean_pk))
    r_pt = _ed25519_decode(r_bytes)
    msg = domain_tag + payload_bytes
    k = int.from_bytes(hashlib.sha512(r_bytes + bytes.fromhex(clean_pk) + msg).digest(), "little") % _ED25519_L
    lhs = _ed25519_mul(_ED25519_B, s_int)
    rhs = _ed25519_add(r_pt, _ed25519_mul(a_pt, k))
    if not hmac.compare_digest(_ed25519_encode(lhs), _ed25519_encode(rhs)):
        raise ValueError(f"ED25519_SIGNATURE_VERIFICATION_FAILED on {context_label}")


# ============================================================================
# TRUSTED CLOCK & EPHEMERAL SANDBOX ANCHOR
# ============================================================================
@dataclass(frozen=True)
class EphemeralSandboxPublicationTrustAnchor:
    """Test-only disposable publication trust anchor (`PASS_TESTED_OFFLINE` only; NEVER grants live publication)."""

    owner_ed25519_pubkey_hex: str
    sandbox_utc_date: str | None = None


def _read_trusted_live_utc_date() -> _dt.date:
    for env_k in FORBIDDEN_CLOCK_TAMPER_ENV_VARS:
        if os.environ.get(env_k):
            raise ValueError(f"UNTRUSTED_RUNTIME_CLOCK_ENV_OVERRIDE_DETECTED: {env_k}")
    if "faketime" in os.environ.get("LD_PRELOAD", "").lower():
        raise ValueError("UNTRUSTED_RUNTIME_CLOCK_LIBFAKETIME_DETECTED")

    py_sec = time.time_ns() / 1_000_000_000.0
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        ft = wintypes.FILETIME()
        ctypes.WinDLL("kernel32", use_last_error=True).GetSystemTimeAsFileTime(ctypes.byref(ft))
        ticks_100ns = (int(ft.dwHighDateTime) << 32) | int(ft.dwLowDateTime)
        os_sec = (ticks_100ns - 116444736000000000) / 10_000_000.0
    else:
        os_sec = float(time.clock_gettime(time.CLOCK_REALTIME))

    if abs(os_sec - py_sec) > 5.0:
        raise ValueError("UNTRUSTED_DIVERGENT_RUNTIME_CLOCK")

    d = _dt.datetime.fromtimestamp(os_sec, tz=_dt.timezone.utc).date()
    if d < MIN_PLAUSIBLE_LIVE_UTC_DATE or d > MAX_PLAUSIBLE_UTC_DATE:
        raise ValueError(f"LIVE_CLOCK_ROLLBACK_OR_IMPLAUSIBLE_UTC_DATE: {d.isoformat()}")
    return d


# ============================================================================
# DENYLIST & W07 SCOPE CLASSIFICATION CONSTANTS
# ============================================================================
W07_GOVERNED_OR_GATE_PROTECTED_PATH_PREFIXES: tuple[str, ...] = (
    ".github/workflows/w07_",
    "tools/w07_stage1/",
    "tools/w07_",
    "scripts/w07_",
    "tests/test_w07_",
    "docs/research/w07_",
    "docs/research/W07_",
    "docs/research/GoMate_W07_",
    "data/evaluation/w07/",
    "data/curated/w07/",
)
W07_GOVERNED_OR_GATE_PROTECTED_EXACT_PATHS: frozenset[str] = frozenset(
    {
        IN_REPO_BOOTSTRAP_VERIFIER_REL_PATH,
        GATE_WORKFLOW_REL_PATH,
    }
)

FORBIDDEN_PATH_SUBSTRINGS: tuple[str, ...] = (
    "data/restricted/",
    "w07_quarantined",
    "t0_private",
    "01_dev5_materialized_quarantined_artifacts",
    "02_stage1_builder_and_t0_canonical_v2_6",
    "03_stage1_configs_and_cost_estimator",
    "04_provider_and_data_rights_dev5",
    "05_hold_exception_and_trust_root",
    "07_readonly_frozen_and_audited_baselines",
    "08_proposed_sandbox_not_deployed",
    "09_diffs_and_evidence_ledger",
    "_w07_auto_eval_isolated_logs",
    "owner_private_vault",
)

FORBIDDEN_EXTENSIONS: tuple[str, ...] = (".pem", ".key", ".sig", ".pfx", ".p12", ".kdbx")
FORBIDDEN_EXACT_FILENAMES: frozenset[str] = frozenset(
    {
        "MY_KEYS.txt",
        "consumed_authorization_nonces_v1.json",
        "owner_pin_update_audit_receipt_v1.json",
        "W07_ISSUER_PUBKEY_BOOTSTRAP_v1.json",
        "W07_T0_DISPOSITION_TRUST_PINS_v1.json",
        "W07_TRUST_ROOT_READINESS_AUDIT_REPORT_v1_1.json",
        "W07_OWNER_T0_HOLD_EXCEPTION_DECISION_V1_UNSIGNED_DRAFT.json",
        "W07_STAGE1_DEV5_CANDIDATE_QUERIES_DRAFT_QUARANTINED_v1_2.json",
        "W07_STAGE1_DEV5_BLIND_PACKET_DRAFT_QUARANTINED_v1_2.json",
        "W07_STAGE1_Q06_S5_QUERY_BOUND_137_DOC_RECEIPT_v1_2.json",
        "verify_auto_eval_01_v0_4_2_pf_customid01.py",
        "verify_w07_stagea_offset01.py",
    }
)

FORBIDDEN_WITHHELD_ARTIFACT_SHA256: dict[str, str] = {
    "cb7dce00a688dc9d62c3933d32ed2014d5c7a5bfcddcc4b989a7bc400c157c89": "verify_auto_eval_01_v0_4_2_pf_customid01.py",
    "30f28d397313f83f9ec02e2f7305ed384d4aa48200fce0da65c144b92a0231eb": "verify_w07_stagea_offset01.py",
    "9ca36a97cafcb6538eab92f73d622cc8ddfc1cd50b1b7765a9ca412855de5466": "Stage-1 Builder v1.4-dev5 baseline",
    "b86a8d98f1a1e611904cb125aed51e81947ff9e691991313add6ed2c3fa3d671": "Runtime Adapter v1.3 baseline",
    "bc01cab91e87df40229f9fb9b65b40910df1d68f8ef88754a85e488c3a6880f4": "Budget40 v2.0 archive-coupled baseline",
    "d9a5dbb6bc8ea6983a05758ba1f5eec51d9950837a0d18b53af91f97bd99d5c0": "Signing Prep v1.1.1-f01r01 baseline",
    "d41e70d905eaecb3fe8e3d543a9fc91e625577ca7967cb743b10abc9e4f53a11": "Signing Prep v1.1.0 baseline",
    "96426b0b403ce81b5cccce5f5aad3d163e3808ffc0568a836cd36b2c0e0e77ed": "Signing Prep v1.0 baseline",
    "e7656acb6bdd0ecbc5f35a2026e275fd31e02489eee838e641114f981522312d": "Quarantined DEV-5 candidate manifest v1_2",
    "9bb5de093a6e75f16f2ef796f8a44a25a4ae3dbbeb44b53a6d55c0ab206c23b0": "Quarantined DEV-5 685-pair blind packet v1_2",
    "9a787c04533349e726fbdea3df3eedfccdec4e14c042f0a2e769da9d416a7735": "Quarantined Q06 S5 137-doc receipt v1_2",
    "e54fe13728612e9e2d8407ab4d582cbd1f48f46e38a4a018c8f986076355941b": "Retired quarantined DEV-6 manifest v1_1",
    "3aae900bfc31af92438adc70a52c506b97271c37ab3b8e367054e978a82eee04": "Unsigned Hold-Exception draft JSON",
    "122daeeb41ade4c9aa7dd36707afffb5cde4d3bfdadc188a788d8f4fa26b0c86": "Host-local Win32 readiness audit report",
    "5056c5c2373ee9584b8850ba49411160cc2c382ad6315aaada4c05fb9b0030c2": "Original Protocol v1.0 markdown",
    "842530dd737e2b2371280a4091ca760e540ec783d6ae654d462e33e148075740": "Original Annex G1.5 v0.2.1 candidate markdown",
    "c33b69881cc98efbaa851c341efb6c9a35c2a9c29f868418a99988305cb2c7ae": "Original AUTO-EVAL v0.4.2 candidate markdown",
    "7da0bfdc070c1e9d5847f6ce4e3e8881a38e0b7879278cfe93d4f2e175fddbe3": "Original G2A v2.0.1 draft markdown",
    "85c184abe62947a0d43523ecb5ce1f6ec80709275f51675fbddef15d9653a8a3": "Original G2B v1.1 draft markdown",
    "94b31486a477943b6ae669948815f07354647ce6f26de9c4a69a28c78e4470c4": "Original Budget40 chat amendment markdown",
    "615254461c2e3146689f5b9fdb2d554264c05e3e0c25bd498e79bc5e992d3dce": "Original W07 Master Execution Plan markdown",
}

DISCLOSED_IMMUTABLE_BASELINE_EXCEPTIONS: dict[str, str] = {
    "tools/w07_stage1/baselines/w07_zh_methodology_skeleton.py": (
        "8514189f20d4ddffefcaad2b767b42391e8e47c970689ff0bf090686dc96da6a"
    ),
    "tools/w07_stage1/baselines/w07_dev1_os_aware_log_guard_reference.py": (
        "17a27209941e145602d9f256b689d2a20029c0005dd077f2517b1df553823d5c"
    ),
}

SECRET_OR_PERSONAL_PATH_RE = re.compile(
    r"(?i)"
    r"([A-Za-z]:[\\/]+Users[\\/]+)"
    r"|(file:///[A-Za-z]:/Users/)"
    r"|(\.gemini[\\/]+antigravity[\\/]+brain)"
    r"|(sk-ant-[A-Za-z0-9_-]{8,})"
    r"|(sk-proj-[A-Za-z0-9_-]{8,})"
    r"|(AIzaSy[A-Za-z0-9_-]{10,})"
    r"|(BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY)"
)
LOCAL_DRIVE_DO_AN_RE = re.compile(r"(?i)[A-Za-z]:[\\/]+do_an\b")
QUARANTINED_DATA_CONTENT_MARKERS: tuple[str, ...] = (
    '"schema_version": "W07_STAGE1_DEV_BLIND_PACKET_DRAFT_QUARANTINED',
    '"schema_version": "W07_STAGE1_DEV_CANDIDATE_QUERIES_DRAFT_QUARANTINED',
    '"schema_version": "W07_STAGE1_Q06_S5_QUERY_BOUND_137_DOC_RECEIPT',
    '"probe_source": "LIVE_WIN32_ADVAPI32_INSPECTION"',
)

EXPECTED_ALLOWLIST_TOP_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "task_id",
        "authorizing_decision_id",
        "governance_role",
        "source_mapping_hold_review_ref",
        "public_gate_corrective_ref",
        "target_public_repository",
        "repository_visibility",
        "baseline_develop_commit",
        "publication_gate_status",
        "dev_authorized",
        "final_50_or_g5_authorized",
        "public_ci_full_packet_dispatch_integration_status",
        "allowlisted_file_count_excluding_self",
        "total_staged_public_file_count_including_self",
        "allowlist_self_path",
        "allowlisted_files",
        "existing_in_develop_in_place_dependencies",
        "withheld_private_lane_artifacts",
    }
)

EXPECTED_ALLOWLIST_ROW_KEYS: frozenset[str] = frozenset(
    {
        "destination_repo_path",
        "sha256",
        "size_bytes",
        "allowed_git_operation",
        "artifact_layer",
        "purpose",
        "sensitivity_scan_result",
        "upstream_dependencies",
        "downstream_consumers",
        "owner_public_release_approval_status",
    }
)

EXPECTED_OWNER_APPROVAL_V2_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "approval_gate_id",
        "authorizing_owner_decision_id",
        "target_public_repository",
        "target_base_branch",
        "expected_base_develop_commit_sha",
        "approved_candidate_commit_sha",
        "approval_status",
        "approved_on_utc_date",
        "expires_on_utc_date",
        "approved_allowlist_manifest_path",
        "approved_allowlist_manifest_sha256",
        "require_complete_approved_fileset",
        "approved_pr_files",
        "owner_ed25519_pubkey_hex",
        "owner_detached_signature_hex",
    }
)


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _parse_json_strict_unique_keys(raw_text: str, *, label: str) -> Any:
    def _hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"DUPLICATE_JSON_KEY_FORBIDDEN in {label}: {k!r}")
            out[k] = v
        return out

    return json.loads(raw_text, object_pairs_hook=_hook)


def _is_valid_norm_rel_posix_path(rel: str) -> bool:
    if not rel or rel.startswith("/") or rel.endswith("/") or "\\" in rel or "\x00" in rel:
        return False
    parts = rel.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def _is_w07_governed_or_gate_protected_path(rel: str) -> bool:
    if rel in W07_GOVERNED_OR_GATE_PROTECTED_EXACT_PATHS:
        return True
    return any(rel.startswith(pref) for pref in W07_GOVERNED_OR_GATE_PROTECTED_PATH_PREFIXES)


def _has_unexpected_hidden_segment(rel: str) -> bool:
    """Reject hidden/dotfiles except explicit `.github/workflows/w07_key_pin_public_ci.yml`."""
    if rel == GATE_WORKFLOW_REL_PATH:
        return False
    return any(seg.startswith(".") for seg in rel.split("/"))


def _run_git(root: Path, args: list[str], *, text: bool = False) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        check=False,
    )


def _scan_single_file_denylist(rel: str, raw: bytes, *, check_hidden: bool = False) -> list[dict[str, str]]:
    """Universal defense-in-depth denylist check (runs on BOTH ordinary PRs and W07 PRs)."""
    v: list[dict[str, str]] = []
    rel_low = rel.lower()
    fname = rel.rsplit("/", 1)[-1]

    if check_hidden and _has_unexpected_hidden_segment(rel):
        v.append({"path": rel, "rule": "UNEXPECTED_HIDDEN_OR_DOTFILE_FORBIDDEN", "detail": rel})

    for bad_sub in FORBIDDEN_PATH_SUBSTRINGS:
        if bad_sub in rel_low:
            v.append({"path": rel, "rule": "FORBIDDEN_PATH_SEGMENT", "detail": bad_sub})

    if fname in FORBIDDEN_EXACT_FILENAMES:
        v.append({"path": rel, "rule": "FORBIDDEN_RESTRICTED_FILENAME", "detail": fname})

    if any(rel_low.endswith(ext) for ext in FORBIDDEN_EXTENSIONS):
        ext_hit = "." + rel_low.rsplit(".", 1)[-1]
        v.append({"path": rel, "rule": "FORBIDDEN_KEY_OR_SIG_EXTENSION", "detail": ext_hit})

    f_sha = _sha256_bytes(raw)
    if f_sha in FORBIDDEN_WITHHELD_ARTIFACT_SHA256:
        v.append(
            {
                "path": rel,
                "rule": "FORBIDDEN_WITHHELD_ARTIFACT_SHA256",
                "detail": f"{f_sha} ({FORBIDDEN_WITHHELD_ARTIFACT_SHA256[f_sha]})",
            }
        )

    # Note: the bootstrap verifier copy itself legitimately contains its own denylist regex literals;
    # in W07 PRs its exact 64-hex SHA-256 is still pinned by Owner Ed25519 signature!
    if rel == IN_REPO_BOOTSTRAP_VERIFIER_REL_PATH:
        return v

    txt = raw.decode("utf-8", errors="replace")
    m_sec = SECRET_OR_PERSONAL_PATH_RE.search(txt)
    if m_sec is not None:
        v.append(
            {
                "path": rel,
                "rule": "PERSONAL_PATH_OR_SECRET_PATTERN_DETECTED",
                "detail": m_sec.group(0)[:80],
            }
        )

    is_disclosed_immutable = (
        rel in DISCLOSED_IMMUTABLE_BASELINE_EXCEPTIONS
        and hmac.compare_digest(f_sha, DISCLOSED_IMMUTABLE_BASELINE_EXCEPTIONS[rel])
    )
    if not is_disclosed_immutable:
        m_do_an = LOCAL_DRIVE_DO_AN_RE.search(txt)
        if m_do_an is not None:
            v.append(
                {
                    "path": rel,
                    "rule": "LOCAL_WORKSPACE_DRIVE_PATH_FORBIDDEN",
                    "detail": m_do_an.group(0),
                }
            )

    if rel.endswith((".json", ".jsonl", ".md", ".csv", ".yml", ".yaml", ".txt")):
        for q_marker in QUARANTINED_DATA_CONTENT_MARKERS:
            if q_marker in txt:
                v.append(
                    {
                        "path": rel,
                        "rule": "QUARANTINED_OR_HOST_DUMP_CONTENT_MARKER",
                        "detail": q_marker,
                    }
                )
    return v


def validate_candidate_allowlist_manifest_strict(
    allowlist_bytes: bytes,
    *,
    expected_self_rel: str = DEFAULT_ALLOWLIST_REL_PATH,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    """Validate candidate allowlist JSON schema, uniqueness, counts, provenance, & forbid PR-local self-approval."""
    violations: list[dict[str, str]] = []
    try:
        obj = _parse_json_strict_unique_keys(allowlist_bytes.decode("utf-8"), label=expected_self_rel)
    except Exception as exc:
        return (
            {},
            {},
            [{"path": expected_self_rel, "rule": "INVALID_ALLOWLIST_MANIFEST_JSON", "detail": str(exc)}],
        )

    if type(obj) is not dict:
        return (
            {},
            {},
            [{"path": expected_self_rel, "rule": "INVALID_ALLOWLIST_MANIFEST_SCHEMA", "detail": "Root must be JSON object"}],
        )

    actual_keys = set(obj.keys())
    if actual_keys != EXPECTED_ALLOWLIST_TOP_KEYS:
        missing = sorted(EXPECTED_ALLOWLIST_TOP_KEYS - actual_keys)
        extra = sorted(actual_keys - EXPECTED_ALLOWLIST_TOP_KEYS)
        violations.append(
            {
                "path": expected_self_rel,
                "rule": "INVALID_ALLOWLIST_MANIFEST_SCHEMA",
                "detail": f"missing={missing}, extra={extra}",
            }
        )
        return ({}, obj, violations)

    gov_role = str(obj.get("governance_role", ""))
    pub_gate_st = str(obj.get("publication_gate_status", ""))
    if gov_role != "CANDIDATE_INVENTORY_ONLY_NEVER_SELF_AUTHORIZING":
        violations.append(
            {
                "path": expected_self_rel,
                "rule": "PR_LOCAL_SELF_APPROVAL_CLAIM_FORBIDDEN",
                "detail": f"governance_role={gov_role!r}",
            }
        )
    if pub_gate_st != "HOLD_PENDING_INDEPENDENT_OWNER_APPROVAL":
        violations.append(
            {
                "path": expected_self_rel,
                "rule": "PR_LOCAL_SELF_APPROVAL_CLAIM_FORBIDDEN",
                "detail": f"publication_gate_status={pub_gate_st!r}",
            }
        )

    if obj.get("schema_version") not in ("W07_PUBLIC_SAFE_RELEASE_ALLOWLIST_V1_1", "W07_PUBLIC_SAFE_RELEASE_ALLOWLIST_V2"):
        violations.append(
            {
                "path": expected_self_rel,
                "rule": "INVALID_ALLOWLIST_SCHEMA_VERSION",
                "detail": repr(obj.get("schema_version")),
            }
        )
    if (
        obj.get("task_id") != "W07-KEY-PIN-MIGRATION-IMPLEMENTATION-01"
        or obj.get("authorizing_decision_id") != "OD-W07-KEY-PIN-MIGRATION-01"
        or obj.get("target_public_repository") != "namnh102/wanderai"
        or obj.get("repository_visibility") != "PUBLIC"
        or obj.get("allowlist_self_path") != expected_self_rel
        or obj.get("dev_authorized") is not False
        or obj.get("final_50_or_g5_authorized") is not False
    ):
        violations.append(
            {
                "path": expected_self_rel,
                "rule": "ALLOWLIST_PROVENANCE_OR_SAFETY_LOCK_MISMATCH",
                "detail": "Provenance or safety lock fields violated",
            }
        )
    if HEX40_RE.fullmatch(str(obj.get("baseline_develop_commit", ""))) is None:
        violations.append(
            {
                "path": expected_self_rel,
                "rule": "INVALID_ALLOWLIST_BASELINE_COMMIT_SHA",
                "detail": repr(obj.get("baseline_develop_commit")),
            }
        )

    rows = obj.get("allowlisted_files")
    if type(rows) is not list or len(rows) == 0:
        violations.append(
            {
                "path": expected_self_rel,
                "rule": "INVALID_ALLOWLIST_FILES_ARRAY",
                "detail": "allowlisted_files must be a non-empty list",
            }
        )
        return ({}, obj, violations)

    excl_cnt = obj.get("allowlisted_file_count_excluding_self")
    incl_cnt = obj.get("total_staged_public_file_count_including_self")
    if type(excl_cnt) is not int or excl_cnt != len(rows) or type(incl_cnt) is not int or incl_cnt != len(rows) + 1:
        violations.append(
            {
                "path": expected_self_rel,
                "rule": "ALLOWLIST_COUNT_MISMATCH",
                "detail": f"len={len(rows)}, excl={excl_cnt!r}, incl={incl_cnt!r}",
            }
        )

    allow_map: dict[str, dict[str, Any]] = {}
    ordered_paths: list[str] = []
    for idx, row in enumerate(rows):
        if type(row) is not dict or set(row.keys()) != EXPECTED_ALLOWLIST_ROW_KEYS:
            violations.append(
                {
                    "path": expected_self_rel,
                    "rule": "INVALID_ALLOWLIST_ROW_SCHEMA",
                    "detail": f"row[{idx}] invalid keys",
                }
            )
            continue
        rpath = str(row["destination_repo_path"])
        rsha = str(row["sha256"])
        rsize = row["size_bytes"]
        rgop = row["allowed_git_operation"]
        rst = str(row["owner_public_release_approval_status"])

        if not _is_valid_norm_rel_posix_path(rpath) or rpath == expected_self_rel:
            violations.append({"path": expected_self_rel, "rule": "INVALID_ALLOWLIST_ROW_PATH", "detail": repr(rpath)})
            continue
        if _has_unexpected_hidden_segment(rpath):
            violations.append({"path": rpath, "rule": "UNEXPECTED_HIDDEN_OR_DOTFILE_FORBIDDEN", "detail": rpath})
            continue
        if rpath in allow_map:
            violations.append({"path": expected_self_rel, "rule": "DUPLICATE_ALLOWLIST_PATH", "detail": rpath})
            continue
        if HEX64_RE.fullmatch(rsha) is None:
            violations.append({"path": rpath, "rule": "INVALID_ALLOWLIST_ROW_SHA256", "detail": rsha})
        if rsha in FORBIDDEN_WITHHELD_ARTIFACT_SHA256:
            violations.append({"path": rpath, "rule": "FORBIDDEN_WITHHELD_SHA256_IN_ALLOWLIST", "detail": rsha})
        if type(rsize) is bool or type(rsize) is not int or rsize <= 0:
            violations.append({"path": rpath, "rule": "INVALID_ALLOWLIST_ROW_SIZE", "detail": repr(rsize)})
        if rgop not in ("A", "M"):
            violations.append({"path": rpath, "rule": "INVALID_ALLOWLIST_ROW_GIT_OPERATION", "detail": repr(rgop)})
        if rst != "CANDIDATE_PENDING_INDEPENDENT_OWNER_APPROVAL":
            violations.append(
                {
                    "path": rpath,
                    "rule": "PR_LOCAL_SELF_APPROVAL_CLAIM_FORBIDDEN",
                    "detail": f"owner_public_release_approval_status={rst!r}",
                }
            )

        ordered_paths.append(rpath)
        allow_map[rpath] = {"sha256": rsha, "size_bytes": rsize, "git_op": rgop}

    if ordered_paths != sorted(ordered_paths):
        violations.append(
            {
                "path": expected_self_rel,
                "rule": "UNSORTED_ALLOWLIST_PATHS",
                "detail": "allowlisted_files must be sorted canonically by destination_repo_path",
            }
        )

    return (allow_map, obj, violations)


def load_and_verify_signed_owner_approval_v2(
    *,
    root: Path,
    trusted_owner_approval_json: Path | None,
    sandbox_trust_anchor: EphemeralSandboxPublicationTrustAnchor | None = None,
) -> tuple[dict[str, Any] | None, str, list[dict[str, str]]]:
    """Verify Ed25519-signed Owner Approval Record V2 strictly against pinned or sandbox Trust Anchor (`PUB-R1-OWNER-02`).

    NEVER accepts unsigned JSON.
    NEVER trusts `owner_ed25519_pubkey_hex` declared inside the JSON without an independent Trust Anchor.
    """
    is_sandbox = sandbox_trust_anchor is not None
    scope = "DISPOSABLE_TEST_SANDBOX" if is_sandbox else "LIVE_PUBLICATION_GATE"

    if sandbox_trust_anchor is not None:
        anchor_pk: str | None = assert_valid_ed25519_pubkey_hex(
            sandbox_trust_anchor.owner_ed25519_pubkey_hex,
            field_name="sandbox_trust_anchor.owner_ed25519_pubkey_hex",
            reject_disclosed_test_keys=True,
        )
    elif PINNED_LIVE_PUBLICATION_OWNER_ED25519_PUBKEY_HEX is not None:
        anchor_pk = assert_valid_ed25519_pubkey_hex(
            PINNED_LIVE_PUBLICATION_OWNER_ED25519_PUBKEY_HEX,
            field_name="PINNED_LIVE_PUBLICATION_OWNER_ED25519_PUBKEY_HEX",
            reject_disclosed_test_keys=True,
        )
    else:
        anchor_pk = None

    if trusted_owner_approval_json is None:
        return (None, scope, [])

    real_root = Path(os.path.realpath(root))
    if trusted_owner_approval_json.is_symlink() or not trusted_owner_approval_json.is_file():
        return (
            None,
            scope,
            [
                {
                    "path": str(trusted_owner_approval_json),
                    "rule": "MISSING_OR_SYMLINK_OWNER_APPROVAL_RECORD",
                    "detail": "Trusted Owner approval JSON missing or symlink",
                }
            ],
        )

    real_app = Path(os.path.realpath(trusted_owner_approval_json))
    try:
        real_app.relative_to(real_root)
        return (
            None,
            scope,
            [
                {
                    "path": str(trusted_owner_approval_json),
                    "rule": "UNTRUSTED_IN_TREE_APPROVAL_RECORD_FORBIDDEN",
                    "detail": "Owner approval record cannot reside inside the candidate/PR checkout tree",
                }
            ],
        )
    except ValueError:
        pass

    source_label = f"out_of_band_file:{real_app.name}"
    try:
        obj = _parse_json_strict_unique_keys(real_app.read_text(encoding="utf-8"), label=source_label)
    except Exception as exc:
        return (None, scope, [{"path": source_label, "rule": "INVALID_OWNER_APPROVAL_JSON", "detail": str(exc)}])

    if type(obj) is not dict:
        return (None, scope, [{"path": source_label, "rule": "INVALID_OWNER_APPROVAL_SCHEMA", "detail": "Root not object"}])

    # Explicit check for unsigned external JSON BEFORE schema/key checks so old unsigned V1/V2 JSONs get a clear rule!
    raw_sig = obj.get("owner_detached_signature_hex")
    if raw_sig is None or (isinstance(raw_sig, str) and not raw_sig.strip()):
        return (
            None,
            scope,
            [
                {
                    "path": source_label,
                    "rule": "UNSIGNED_EXTERNAL_APPROVAL_JSON_FORBIDDEN",
                    "detail": "Arbitrary out-of-root unsigned approval JSON is rejected; Owner Ed25519 signature is mandatory",
                }
            ],
        )

    # Explicit check against self-declared/rogue public key when live trust anchor is unprovisioned!
    if anchor_pk is None:
        return (
            None,
            scope,
            [
                {
                    "path": source_label,
                    "rule": "SELF_DECLARED_PUBKEY_WITHOUT_TRUSTED_ANCHOR_FORBIDDEN",
                    "detail": (
                        "PINNED_LIVE_PUBLICATION_OWNER_ED25519_PUBKEY_HEX is None (unprovisioned); "
                        "cannot verify approval signature against a public key declared by the JSON itself"
                    ),
                }
            ],
        )

    violations: list[dict[str, str]] = []
    actual_keys = set(obj.keys())
    if actual_keys != EXPECTED_OWNER_APPROVAL_V2_KEYS:
        missing = sorted(EXPECTED_OWNER_APPROVAL_V2_KEYS - actual_keys)
        extra = sorted(actual_keys - EXPECTED_OWNER_APPROVAL_V2_KEYS)
        violations.append(
            {
                "path": source_label,
                "rule": "INVALID_OWNER_APPROVAL_V2_SCHEMA",
                "detail": f"missing={missing}, extra={extra}",
            }
        )
        return (None, scope, violations)

    declared_pk = str(obj.get("owner_ed25519_pubkey_hex", "")).strip()
    if not hmac.compare_digest(declared_pk, anchor_pk):
        violations.append(
            {
                "path": source_label,
                "rule": "ROGUE_SELF_SIGNED_APPROVAL_PUBKEY_MISMATCH",
                "detail": f"declared pubkey {declared_pk[:16]}... != pinned trusted anchor {anchor_pk[:16]}...",
            }
        )
        return (None, scope, violations)

    unsigned_body = {k: v for k, v in obj.items() if k != "owner_detached_signature_hex"}
    try:
        verify_detached_ed25519_hex(
            pubkey_hex=anchor_pk,
            domain_tag=ED25519_DOMAIN_PUBLIC_RELEASE_APPROVAL_V2,
            payload_bytes=_canonical_json_bytes(unsigned_body),
            signature_hex=raw_sig,
            context_label="owner_public_release_approval_v2",
        )
    except Exception as exc:
        violations.append(
            {
                "path": source_label,
                "rule": "OWNER_APPROVAL_ED25519_SIGNATURE_INVALID",
                "detail": str(exc),
            }
        )
        return (None, scope, violations)

    if (
        obj.get("schema_version") != "W07_OWNER_PUBLIC_RELEASE_APPROVAL_RECORD_V2"
        or obj.get("approval_gate_id") != "GATE-PUB-ALLOWLIST-01"
        or obj.get("authorizing_owner_decision_id") != "OD-W07-KEY-PIN-MIGRATION-01"
        or obj.get("target_public_repository") != "namnh102/wanderai"
        or obj.get("target_base_branch") != "develop"
        or obj.get("approval_status") != "OWNER_SIGNED_EXACT_COMMIT_AND_HASH_SET"
    ):
        violations.append(
            {
                "path": source_label,
                "rule": "OWNER_APPROVAL_RECORD_STATUS_OR_PROVENANCE_INVALID",
                "detail": f"approval_status={obj.get('approval_status')!r}",
            }
        )

    if HEX40_RE.fullmatch(str(obj.get("expected_base_develop_commit_sha", ""))) is None:
        violations.append({"path": source_label, "rule": "INVALID_OWNER_APPROVAL_BASE_COMMIT_SHA", "detail": "Invalid 40-hex"})
    if HEX40_RE.fullmatch(str(obj.get("approved_candidate_commit_sha", ""))) is None:
        violations.append({"path": source_label, "rule": "INVALID_OWNER_APPROVAL_CANDIDATE_COMMIT_SHA", "detail": "Invalid 40-hex"})
    if HEX64_RE.fullmatch(str(obj.get("approved_allowlist_manifest_sha256", ""))) is None:
        violations.append({"path": source_label, "rule": "INVALID_OWNER_APPROVAL_MANIFEST_SHA256", "detail": "Invalid 64-hex"})
    if type(obj.get("require_complete_approved_fileset")) is not bool:
        violations.append({"path": source_label, "rule": "INVALID_OWNER_APPROVAL_COMPLETE_SET_FLAG", "detail": "Must be bool"})

    app_on = str(obj.get("approved_on_utc_date", ""))
    exp_on = str(obj.get("expires_on_utc_date", ""))
    if ISO_DATE_RE.fullmatch(app_on) is None or ISO_DATE_RE.fullmatch(exp_on) is None:
        violations.append({"path": source_label, "rule": "INVALID_OWNER_APPROVAL_DATES", "detail": f"{app_on!r}..{exp_on!r}"})
    else:
        d_app = _dt.date.fromisoformat(app_on)
        d_exp = _dt.date.fromisoformat(exp_on)
        try:
            if is_sandbox and sandbox_trust_anchor is not None and sandbox_trust_anchor.sandbox_utc_date is not None:
                eff_today = _dt.date.fromisoformat(sandbox_trust_anchor.sandbox_utc_date)
            else:
                eff_today = _read_trusted_live_utc_date()
        except Exception as exc:
            violations.append({"path": source_label, "rule": "UNTRUSTED_RUNTIME_CLOCK", "detail": str(exc)})
            return (None, scope, violations)

        if d_exp < d_app or (d_exp - d_app).days > MAX_APPROVAL_WINDOW_DAYS or eff_today < d_app or eff_today > d_exp:
            violations.append(
                {
                    "path": source_label,
                    "rule": "EXPIRED_OR_OUT_OF_WINDOW_OWNER_APPROVAL_RECORD",
                    "detail": f"today={eff_today.isoformat()}, window={app_on}..{exp_on}",
                }
            )

    files_map = obj.get("approved_pr_files")
    if type(files_map) is not dict or len(files_map) == 0:
        violations.append({"path": source_label, "rule": "EMPTY_OR_INVALID_APPROVED_PR_FILES", "detail": "Empty"})
    else:
        for fpath, spec in files_map.items():
            if not _is_valid_norm_rel_posix_path(str(fpath)) or type(spec) is not dict:
                violations.append({"path": str(fpath), "rule": "INVALID_APPROVED_PR_FILE_ENTRY", "detail": "Invalid entry"})
                continue
            if (
                set(spec.keys()) != {"sha256", "size_bytes", "git_op"}
                or HEX64_RE.fullmatch(str(spec.get("sha256", ""))) is None
                or spec.get("sha256") in FORBIDDEN_WITHHELD_ARTIFACT_SHA256
                or type(spec.get("size_bytes")) is bool
                or type(spec.get("size_bytes")) is not int
                or spec["size_bytes"] <= 0
                or spec.get("git_op") not in ("A", "M")
            ):
                violations.append({"path": str(fpath), "rule": "INVALID_APPROVED_PR_FILE_SPEC", "detail": repr(spec)})

    return (obj if not violations else None, scope, violations)


def _derive_git_diff_against_base(
    root: Path,
    *,
    trusted_base_ref: str,
    candidate_commit_ref: str = "HEAD",
    git_objects_only: bool = False,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]], dict[str, str], list[dict[str, str]]]:
    """Derive exact Git tree diff `<merge_base>..<candidate_commit>` (`0` candidate code executed!)."""
    violations: list[dict[str, str]] = []
    non_am_ops: list[dict[str, str]] = []
    real_root = Path(os.path.realpath(root))

    cp_top = _run_git(real_root, ["rev-parse", "--show-toplevel"], text=True)
    if cp_top.returncode != 0:
        return ({}, [], {}, [{"path": str(real_root), "rule": "NOT_A_GIT_REPOSITORY", "detail": cp_top.stderr.strip()}])
    if Path(os.path.realpath(cp_top.stdout.strip())) != real_root:
        return ({}, [], {}, [{"path": str(real_root), "rule": "GIT_ROOT_MISMATCH", "detail": cp_top.stdout.strip()}])

    if not git_objects_only:
        cp_st = _run_git(real_root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"], text=False)
        if cp_st.returncode != 0:
            violations.append({"path": "<git_status>", "rule": "GIT_STATUS_FAILED", "detail": "git status failed"})
        elif cp_st.stdout:
            for ent in (e.decode("utf-8", errors="replace") for e in cp_st.stdout.split(b"\x00") if e):
                violations.append(
                    {
                        "path": ent[3:] if len(ent) > 3 else ent,
                        "rule": "DIRTY_OR_UNTRACKED_WORKTREE_FORBIDDEN",
                        "detail": f"porcelain={ent!r}",
                    }
                )

    cp_base = _run_git(real_root, ["rev-parse", "--verify", f"{trusted_base_ref}^{{commit}}"], text=True)
    if cp_base.returncode != 0:
        return (
            {},
            [],
            {},
            [{"path": trusted_base_ref, "rule": "UNRESOLVED_TRUSTED_BASE_REF", "detail": cp_base.stderr.strip()}],
        )
    base_commit = cp_base.stdout.strip()

    cp_cand = _run_git(real_root, ["rev-parse", "--verify", f"{candidate_commit_ref}^{{commit}}"], text=True)
    if cp_cand.returncode != 0:
        return (
            {},
            [],
            {},
            [{"path": candidate_commit_ref, "rule": "UNRESOLVED_CANDIDATE_COMMIT", "detail": cp_cand.stderr.strip()}],
        )
    cand_commit = cp_cand.stdout.strip()

    cp_mb = _run_git(real_root, ["merge-base", base_commit, cand_commit], text=True)
    if cp_mb.returncode != 0:
        return (
            {},
            [],
            {},
            [{"path": trusted_base_ref, "rule": "GIT_MERGE_BASE_FAILED", "detail": cp_mb.stderr.strip()}],
        )
    merge_base = cp_mb.stdout.strip()

    # Check rename/copy detector as well
    cp_ren = _run_git(real_root, ["diff", "--name-status", "--find-renames=1%", "-z", merge_base, cand_commit], text=False)
    if cp_ren.returncode == 0 and cp_ren.stdout:
        toks = [t.decode("utf-8", errors="replace") for t in cp_ren.stdout.split(b"\x00") if t]
        idx = 0
        while idx < len(toks):
            st = toks[idx]
            if st.startswith(("R", "C")):
                old_p = toks[idx + 1] if idx + 1 < len(toks) else ""
                new_p = toks[idx + 2] if idx + 2 < len(toks) else ""
                non_am_ops.append({"old_path": old_p, "new_path": new_p, "status": st})
                idx += 3
            else:
                idx += 2

    cp_raw = _run_git(real_root, ["diff", "--raw", "--no-renames", "-z", merge_base, cand_commit], text=False)
    if cp_raw.returncode != 0:
        return ({}, [], {}, [{"path": "<git_diff>", "rule": "GIT_RAW_DIFF_FAILED", "detail": "git diff --raw failed"}])

    changed: dict[str, dict[str, Any]] = {}
    parts = cp_raw.stdout.split(b"\x00")
    i = 0
    while i < len(parts) - 1:
        meta = parts[i].decode("utf-8", errors="replace")
        if not meta.startswith(":"):
            i += 1
            continue
        rel_path = parts[i + 1].decode("utf-8", errors="replace")
        i += 2
        m_tokens = meta[1:].split()
        if len(m_tokens) < 5:
            violations.append({"path": rel_path, "rule": "MALFORMED_GIT_DIFF_ENTRY", "detail": meta})
            continue
        old_mode, new_mode, _old_oid, _new_oid, status = m_tokens[:5]

        if old_mode == "120000" or new_mode == "120000":
            violations.append(
                {"path": rel_path, "rule": "SYMLINK_FORBIDDEN_IN_GIT_DIFF", "detail": f"mode={old_mode}->{new_mode}"}
            )
            continue
        if old_mode == "160000" or new_mode == "160000":
            violations.append(
                {"path": rel_path, "rule": "SUBMODULE_GITLINK_FORBIDDEN", "detail": f"mode={old_mode}->{new_mode}"}
            )
            continue

        if status not in ("A", "M"):
            non_am_ops.append({"old_path": rel_path, "new_path": rel_path, "status": status})
            continue

        cp_blob = _run_git(real_root, ["cat-file", "-p", f"{cand_commit}:{rel_path}"], text=False)
        if cp_blob.returncode != 0:
            violations.append({"path": rel_path, "rule": "GIT_BLOB_READ_FAILED", "detail": "cat-file failed"})
            continue
        blob_bytes = cp_blob.stdout

        if not git_objects_only:
            disk_p = real_root / rel_path
            if disk_p.is_symlink():
                violations.append({"path": rel_path, "rule": "SYMLINK_FORBIDDEN", "detail": "Worktree symlink"})
                continue
            if disk_p.is_file() and disk_p.read_bytes() != blob_bytes:
                violations.append(
                    {
                        "path": rel_path,
                        "rule": "WORKTREE_HEAD_BLOB_MISMATCH",
                        "detail": "Working tree bytes differ from committed candidate blob",
                    }
                )

        changed[rel_path] = {
            "git_op": status,
            "bytes": blob_bytes,
            "sha256": _sha256_bytes(blob_bytes),
            "size_bytes": len(blob_bytes),
        }

    git_meta = {
        "trusted_base_ref": trusted_base_ref,
        "base_commit_sha": base_commit,
        "merge_base_commit_sha": merge_base,
        "candidate_commit_sha": cand_commit,
        "git_objects_only": str(git_objects_only),
    }
    return (changed, non_am_ops, git_meta, violations)


def _derive_git_staged_pre_commit_files(root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    violations: list[dict[str, str]] = []
    real_root = Path(os.path.realpath(root))
    cp_raw = _run_git(real_root, ["diff", "--cached", "--raw", "--no-renames", "-z"], text=False)
    if cp_raw.returncode != 0:
        return ({}, [{"path": "<git_staged>", "rule": "GIT_CACHED_DIFF_FAILED", "detail": "git diff --cached failed"}])

    changed: dict[str, dict[str, Any]] = {}
    parts = cp_raw.stdout.split(b"\x00")
    i = 0
    while i < len(parts) - 1:
        meta = parts[i].decode("utf-8", errors="replace")
        if not meta.startswith(":"):
            i += 1
            continue
        rel_path = parts[i + 1].decode("utf-8", errors="replace")
        i += 2
        m_tokens = meta[1:].split()
        if len(m_tokens) < 5:
            continue
        old_mode, new_mode, _old_oid, _new_oid, status = m_tokens[:5]
        if old_mode == "120000" or new_mode == "120000":
            violations.append({"path": rel_path, "rule": "SYMLINK_FORBIDDEN_IN_GIT_DIFF", "detail": f"mode={new_mode}"})
            continue
        if old_mode == "160000" or new_mode == "160000":
            violations.append({"path": rel_path, "rule": "SUBMODULE_GITLINK_FORBIDDEN", "detail": f"mode={new_mode}"})
            continue
        if status not in ("A", "M"):
            violations.append(
                {
                    "path": rel_path,
                    "rule": "FORBIDDEN_GIT_FILE_OPERATION",
                    "detail": f"staged operation={status} forbidden in W07 pre-commit",
                }
            )
            continue
        cp_blob = _run_git(real_root, ["cat-file", "-p", f":{rel_path}"], text=False)
        if cp_blob.returncode != 0:
            violations.append({"path": rel_path, "rule": "GIT_INDEX_BLOB_READ_FAILED", "detail": "cat-file :path failed"})
            continue
        b = cp_blob.stdout
        changed[rel_path] = {
            "git_op": status,
            "bytes": b,
            "sha256": _sha256_bytes(b),
            "size_bytes": len(b),
        }
    return (changed, violations)


def evaluate_public_release_gate(
    root: Path,
    *,
    allowlist_json_path: Path | None = None,
    git_diff_base: str | None = None,
    candidate_commit_ref: str = "HEAD",
    git_objects_only: bool = False,
    git_pre_commit: bool = False,
    require_external_trusted_verifier: bool = False,
    force_w07_scope: bool = False,
    require_owner_approval: bool = True,
    offline_candidate_audit: bool = False,
    trusted_owner_approval_json: Path | None = None,
    sandbox_trust_anchor: EphemeralSandboxPublicationTrustAnchor | None = None,
) -> tuple[int, dict[str, Any]]:
    """Evaluate W07 Trusted Publication Boundary Gate (`PUB-R1-TRUST-01..04`)."""
    real_root = Path(os.path.realpath(root))
    real_self = Path(os.path.realpath(__file__))
    violations: list[dict[str, str]] = []

    # PUB-R1-TRUST-01: Authoritative runs MUST execute an external/protected-base verifier, NEVER candidate code!
    if require_external_trusted_verifier:
        try:
            real_self.relative_to(real_root)
            return (
                1,
                {
                    "tool_version": TOOL_VERSION,
                    "scan_status": "BLOCKED_CANDIDATE_SELF_EXECUTION_FORBIDDEN",
                    "verdict_class": "BLOCKED",
                    "w07_release_approved": False,
                    "live_publication_authorized": False,
                    "violation_count": 1,
                    "violations": [
                        {
                            "path": str(real_self),
                            "rule": "CANDIDATE_SELF_EXECUTION_FORBIDDEN",
                            "detail": (
                                "Authoritative publication gate cannot execute a verifier script residing inside "
                                "the untrusted candidate checkout; run from external Owner root or protected base."
                            ),
                        }
                    ],
                },
            )
        except ValueError:
            pass

    git_meta: dict[str, str] | None = None
    non_am_ops: list[dict[str, str]] = []
    candidate_files: dict[str, dict[str, Any]] = {}
    check_complete_set = True

    if git_diff_base is not None:
        candidate_files, non_am_ops, git_meta, diff_v = _derive_git_diff_against_base(
            real_root,
            trusted_base_ref=git_diff_base,
            candidate_commit_ref=candidate_commit_ref,
            git_objects_only=git_objects_only,
        )
        violations.extend(diff_v)
        if not candidate_files and not non_am_ops and not violations:
            violations.append(
                {
                    "path": "<pr_diff>",
                    "rule": "EMPTY_PR_DIFF_AGAINST_BASE",
                    "detail": "Zero changed files between merge_base and candidate commit",
                }
            )
    elif git_pre_commit:
        check_complete_set = False
        candidate_files, stg_v = _derive_git_staged_pre_commit_files(real_root)
        violations.extend(stg_v)
    else:
        for p in sorted(real_root.rglob("*"), key=lambda x: x.relative_to(real_root).as_posix()):
            rel_parts = p.relative_to(real_root).parts
            if ".git" in rel_parts or "__pycache__" in rel_parts or p.suffix in (".pyc", ".pyo"):
                continue
            rel = p.relative_to(real_root).as_posix()
            if p.is_symlink():
                violations.append({"path": rel, "rule": "SYMLINK_FORBIDDEN", "detail": "Filesystem symlink prohibited"})
                continue
            if p.is_file():
                b = p.read_bytes()
                candidate_files[rel] = {
                    "git_op": "A",
                    "bytes": b,
                    "sha256": _sha256_bytes(b),
                    "size_bytes": len(b),
                }

    # =========================================================================
    # STEP 1: UNIVERSAL RESTRICTED-CONTENT & SECRET DENYLIST (100% OF PRs!)
    # =========================================================================
    touches_w07_scope = force_w07_scope or (git_diff_base is None)
    for rel in candidate_files:
        if _is_w07_governed_or_gate_protected_path(rel):
            touches_w07_scope = True
    for op in non_am_ops:
        if _is_w07_governed_or_gate_protected_path(op["old_path"]) or _is_w07_governed_or_gate_protected_path(op["new_path"]):
            touches_w07_scope = True

    for rel, info in sorted(candidate_files.items()):
        violations.extend(_scan_single_file_denylist(rel, info["bytes"], check_hidden=touches_w07_scope))

    # =========================================================================
    # STEP 2A: ORDINARY UNRELATED PRODUCT PR (PUB-R1-CI-03)
    # =========================================================================
    if git_diff_base is not None and not touches_w07_scope:
        if violations:
            return (
                1,
                {
                    "tool_version": TOOL_VERSION,
                    "pr_classification": "ORDINARY_NON_W07_PRODUCT_PR",
                    "scan_status": "BLOCKED_RESTRICTED_OR_UNAPPROVED_CONTENT",
                    "verdict_class": "BLOCKED",
                    "w07_release_approved": False,
                    "live_publication_authorized": False,
                    "git_diff_metadata": git_meta,
                    "scanned_file_count": len(candidate_files),
                    "violation_count": len(violations),
                    "violations": violations,
                },
            )
        return (
            0,
            {
                "tool_version": TOOL_VERSION,
                "pr_classification": "ORDINARY_NON_W07_PRODUCT_PR",
                "scan_status": "PASS_NON_W07_RESTRICTED_SCAN_ONLY_NOT_W07_APPROVED",
                "verdict_class": "PASS_NON_W07_RESTRICTED_SCAN_ONLY",
                "w07_release_approved": False,
                "live_publication_authorized": False,
                "owner_approval_verified": False,
                "git_diff_metadata": git_meta,
                "scanned_file_count": len(candidate_files),
                "violation_count": 0,
                "violations": [],
            },
        )

    # =========================================================================
    # STEP 2B: W07 GOVERNED OR GATE-PROTECTED SCOPE (FULL EXACT-SET GATE!)
    # =========================================================================
    pr_classification = "W07_GOVERNED_OR_GATE_PROTECTED_PR"
    for op in non_am_ops:
        if op["status"].startswith(("R", "C")):
            violations.append(
                {
                    "path": f"{op['old_path']} -> {op['new_path']}",
                    "rule": "FORBIDDEN_GIT_RENAME_OR_COPY_OPERATION",
                    "detail": f"status={op['status']}",
                }
            )
        else:
            violations.append(
                {
                    "path": op["old_path"],
                    "rule": "FORBIDDEN_GIT_FILE_OPERATION",
                    "detail": f"operation={op['status']} (deletes/typechanges prohibited in W07 scope)",
                }
            )

    # Load candidate allowlist manifest (from Git object in git_objects_only mode, else from disk)
    allowlist_rel = DEFAULT_ALLOWLIST_REL_PATH
    allowlist_raw: bytes | None = None
    if git_objects_only and git_meta is not None:
        if allowlist_rel in candidate_files:
            allowlist_raw = candidate_files[allowlist_rel]["bytes"]
        else:
            cp_al = _run_git(real_root, ["cat-file", "-p", f"{git_meta['candidate_commit_sha']}:{allowlist_rel}"], text=False)
            if cp_al.returncode == 0:
                allowlist_raw = cp_al.stdout
    else:
        eff_allowlist_path = allowlist_json_path if allowlist_json_path is not None else (real_root / DEFAULT_ALLOWLIST_REL_PATH)
        try:
            allowlist_rel = Path(os.path.realpath(eff_allowlist_path)).relative_to(real_root).as_posix()
        except ValueError:
            pass
        if eff_allowlist_path.is_file() and not eff_allowlist_path.is_symlink():
            allowlist_raw = eff_allowlist_path.read_bytes()

    if allowlist_raw is None:
        violations.append(
            {
                "path": allowlist_rel,
                "rule": "MISSING_OR_SYMLINK_ALLOWLIST_MANIFEST",
                "detail": "Candidate allowlist JSON missing or symlink",
            }
        )
        return (
            1,
            {
                "tool_version": TOOL_VERSION,
                "pr_classification": pr_classification,
                "scan_status": "BLOCKED_RESTRICTED_OR_UNAPPROVED_CONTENT",
                "verdict_class": "BLOCKED",
                "w07_release_approved": False,
                "live_publication_authorized": False,
                "scanned_file_count": len(candidate_files),
                "violation_count": len(violations),
                "violations": violations,
            },
        )

    allowlist_sha = _sha256_bytes(allowlist_raw)
    allow_map, allow_obj, allow_violations = validate_candidate_allowlist_manifest_strict(
        allowlist_raw, expected_self_rel=allowlist_rel
    )
    violations.extend(allow_violations)

    owner_approval_obj, eval_scope, app_violations = load_and_verify_signed_owner_approval_v2(
        root=real_root,
        trusted_owner_approval_json=trusted_owner_approval_json,
        sandbox_trust_anchor=sandbox_trust_anchor,
    )
    violations.extend(app_violations)

    expected_full_candidate_map: dict[str, dict[str, Any]] = {
        **allow_map,
        allowlist_rel: {
            "sha256": allowlist_sha,
            "size_bytes": len(allowlist_raw),
            "git_op": "A",
        },
    }

    for rel, info in sorted(candidate_files.items()):
        if rel not in expected_full_candidate_map:
            violations.append(
                {
                    "path": rel,
                    "rule": "OUT_OF_SCOPE_UNALLOWLISTED_FILE",
                    "detail": "File is outside the allowlisted W07 release set (zero path exemptions)",
                }
            )
            continue
        exp_spec = expected_full_candidate_map[rel]
        if not hmac.compare_digest(info["sha256"], exp_spec["sha256"]):
            violations.append(
                {
                    "path": rel,
                    "rule": "ALLOWLIST_SHA256_MISMATCH",
                    "detail": f"expected {exp_spec['sha256']}, got {info['sha256']}",
                }
            )
        if info["size_bytes"] != exp_spec["size_bytes"]:
            violations.append(
                {
                    "path": rel,
                    "rule": "ALLOWLIST_SIZE_MISMATCH",
                    "detail": f"expected {exp_spec['size_bytes']}, got {info['size_bytes']}",
                }
            )
        if git_diff_base is not None and info["git_op"] != exp_spec["git_op"]:
            violations.append(
                {
                    "path": rel,
                    "rule": "GIT_OPERATION_TYPE_MISMATCH",
                    "detail": f"expected git_op={exp_spec['git_op']}, got {info['git_op']}",
                }
            )

    if check_complete_set and allow_map:
        for m_rel in sorted(set(expected_full_candidate_map.keys()) - set(candidate_files.keys())):
            if git_meta is not None:
                cp_pre = _run_git(
                    real_root,
                    ["cat-file", "-p", f"{git_meta['candidate_commit_sha']}:{m_rel}"],
                    text=False,
                )
                if cp_pre.returncode == 0:
                    pre_bytes = cp_pre.stdout
                    pre_sha = _sha256_bytes(pre_bytes)
                    exp_spec = expected_full_candidate_map[m_rel]
                    if hmac.compare_digest(pre_sha, exp_spec["sha256"]) and len(pre_bytes) == exp_spec["size_bytes"]:
                        continue
                    violations.append(
                        {
                            "path": m_rel,
                            "rule": "ALLOWLIST_SHA256_MISMATCH",
                            "detail": (
                                f"pre-bootstrapped file at candidate commit has sha256={pre_sha} (size={len(pre_bytes)}), "
                                f"expected {exp_spec['sha256']} (size={exp_spec['size_bytes']})"
                            ),
                        }
                    )
                    continue
            violations.append(
                {
                    "path": m_rel,
                    "rule": "MISSING_ALLOWLISTED_FILE",
                    "detail": "Allowlisted file missing from candidate tree / PR diff",
                }
            )

    if owner_approval_obj is not None:
        if not hmac.compare_digest(str(owner_approval_obj["approved_allowlist_manifest_sha256"]), allowlist_sha):
            violations.append(
                {
                    "path": allowlist_rel,
                    "rule": "APPROVED_MANIFEST_DIGEST_MISMATCH",
                    "detail": (
                        f"owner_approved={owner_approval_obj['approved_allowlist_manifest_sha256']} != actual={allowlist_sha}"
                    ),
                }
            )
        if str(owner_approval_obj["approved_allowlist_manifest_path"]) != allowlist_rel:
            violations.append(
                {
                    "path": allowlist_rel,
                    "rule": "APPROVED_MANIFEST_PATH_MISMATCH",
                    "detail": str(owner_approval_obj["approved_allowlist_manifest_path"]),
                }
            )

        if git_meta is not None:
            exp_base = str(owner_approval_obj["expected_base_develop_commit_sha"])
            exp_cand = str(owner_approval_obj["approved_candidate_commit_sha"])
            if git_meta["merge_base_commit_sha"] != exp_base or git_meta["base_commit_sha"] != exp_base:
                violations.append(
                    {
                        "path": "<git_base>",
                        "rule": "BASE_DEVELOP_COMMIT_SHA_MISMATCH",
                        "detail": f"expected={exp_base}, actual_base={git_meta['base_commit_sha']}, merge_base={git_meta['merge_base_commit_sha']}",
                    }
                )
            if git_meta["candidate_commit_sha"] != exp_cand:
                violations.append(
                    {
                        "path": "<git_candidate>",
                        "rule": "CANDIDATE_COMMIT_SHA_MISMATCH",
                        "detail": f"approved_candidate={exp_cand} != actual_candidate={git_meta['candidate_commit_sha']}",
                    }
                )
        elif str(allow_obj.get("baseline_develop_commit", "")) != str(
            owner_approval_obj["expected_base_develop_commit_sha"]
        ):
            violations.append(
                {
                    "path": allowlist_rel,
                    "rule": "BASE_DEVELOP_COMMIT_SHA_MISMATCH",
                    "detail": "Candidate allowlist baseline_develop_commit != Owner approval expected_base_develop_commit_sha",
                }
            )

        approved_files: dict[str, dict[str, Any]] = owner_approval_obj["approved_pr_files"]
        for rel, info in sorted(candidate_files.items()):
            if rel not in approved_files:
                violations.append(
                    {
                        "path": rel,
                        "rule": "UNAPPROVED_FILE_NOT_IN_OWNER_APPROVAL_SET",
                        "detail": "File is not authorized by Owner Ed25519-signed approval record",
                    }
                )
                continue
            ap_spec = approved_files[rel]
            if not hmac.compare_digest(info["sha256"], str(ap_spec["sha256"])):
                violations.append(
                    {
                        "path": rel,
                        "rule": "OWNER_APPROVED_FILE_SHA256_MISMATCH",
                        "detail": f"owner_approved={ap_spec['sha256']}, actual={info['sha256']}",
                    }
                )
            if info["size_bytes"] != int(ap_spec["size_bytes"]):
                violations.append(
                    {
                        "path": rel,
                        "rule": "OWNER_APPROVED_FILE_SIZE_MISMATCH",
                        "detail": f"owner_approved={ap_spec['size_bytes']}, actual={info['size_bytes']}",
                    }
                )
            if git_diff_base is not None and info["git_op"] != ap_spec["git_op"]:
                violations.append(
                    {
                        "path": rel,
                        "rule": "OWNER_APPROVED_GIT_OP_MISMATCH",
                        "detail": f"owner_approved={ap_spec['git_op']}, actual={info['git_op']}",
                    }
                )

        if owner_approval_obj.get("require_complete_approved_fileset") is True and check_complete_set:
            for m_rel in sorted(set(approved_files.keys()) - set(candidate_files.keys())):
                violations.append(
                    {
                        "path": m_rel,
                        "rule": "MISSING_APPROVED_RELEASE_FILE",
                        "detail": "Owner-approved file was omitted or deleted from candidate/PR",
                    }
                )

    if violations:
        return (
            1,
            {
                "tool_version": TOOL_VERSION,
                "evaluation_scope": eval_scope,
                "pr_classification": pr_classification,
                "scan_status": "BLOCKED_RESTRICTED_OR_UNAPPROVED_CONTENT",
                "verdict_class": "BLOCKED",
                "w07_release_approved": False,
                "live_publication_authorized": False,
                "owner_approval_verified": False,
                "git_diff_metadata": git_meta,
                "scanned_file_count": len(candidate_files),
                "violation_count": len(violations),
                "violations": violations,
            },
        )

    if owner_approval_obj is None:
        if offline_candidate_audit and not require_owner_approval:
            return (
                0,
                {
                    "tool_version": TOOL_VERSION,
                    "evaluation_scope": "OFFLINE_PRE_PUBLICATION_CANDIDATE_AUDIT",
                    "pr_classification": pr_classification,
                    "scan_status": "HOLD_PENDING_OWNER_APPROVAL_CANDIDATE_CLEAN",
                    "verdict_class": "LIVE_HOLD",
                    "w07_release_approved": False,
                    "live_publication_authorized": False,
                    "owner_approval_verified": False,
                    "git_diff_metadata": git_meta,
                    "allowlist_manifest_sha256": allowlist_sha,
                    "scanned_file_count": len(candidate_files),
                    "violation_count": 0,
                    "violations": [],
                },
            )
        hold_code = (
            "HOLD_UNPROVISIONED_OWNER_PUBLICATION_TRUST_ANCHOR"
            if (PINNED_LIVE_PUBLICATION_OWNER_ED25519_PUBKEY_HEX is None and sandbox_trust_anchor is None)
            else "HOLD_PENDING_OWNER_APPROVAL"
        )
        return (
            2,
            {
                "tool_version": TOOL_VERSION,
                "evaluation_scope": eval_scope,
                "pr_classification": pr_classification,
                "scan_status": hold_code,
                "verdict_class": "LIVE_HOLD",
                "w07_release_approved": False,
                "live_publication_authorized": False,
                "owner_approval_verified": False,
                "git_diff_metadata": git_meta,
                "allowlist_manifest_sha256": allowlist_sha,
                "scanned_file_count": len(candidate_files),
                "violation_count": 0,
                "violations": [],
            },
        )

    if eval_scope == "DISPOSABLE_TEST_SANDBOX":
        return (
            0,
            {
                "tool_version": TOOL_VERSION,
                "evaluation_scope": "DISPOSABLE_TEST_SANDBOX",
                "pr_classification": pr_classification,
                "scan_status": "PASS_TESTED_OFFLINE_SANDBOX_W07_APPROVAL_VERIFIED",
                "verdict_class": "PASS_TESTED_OFFLINE",
                "w07_release_approved": True,
                "live_publication_authorized": False,
                "owner_approval_verified": True,
                "approval_proof_type": "EPHEMERAL_SANDBOX_ED25519_TEST_ONLY_NEVER_LIVE",
                "approval_gate_id": owner_approval_obj["approval_gate_id"],
                "git_diff_metadata": git_meta,
                "allowlist_manifest_sha256": allowlist_sha,
                "scanned_file_count": len(candidate_files),
                "violation_count": 0,
                "violations": [],
            },
        )

    return (
        0,
        {
            "tool_version": TOOL_VERSION,
            "evaluation_scope": "LIVE_PUBLICATION_GATE",
            "pr_classification": pr_classification,
            "scan_status": "PASS_LIVE_OWNER_SIGNED_W07_PUBLICATION_VERIFIED",
            "verdict_class": "PASS_LIVE_AUTHORIZED",
            "w07_release_approved": True,
            "live_publication_authorized": True,
            "owner_approval_verified": True,
            "approval_proof_type": "CRYPTOGRAPHIC_ED25519_AGAINST_PINNED_LIVE_OWNER_ANCHOR",
            "approval_gate_id": owner_approval_obj["approval_gate_id"],
            "git_diff_metadata": git_meta,
            "allowlist_manifest_sha256": allowlist_sha,
            "scanned_file_count": len(candidate_files),
            "violation_count": 0,
            "violations": [],
        },
    )


def generate_prepublication_exact_byte_manifest(
    *,
    candidate_staging_dir: Path,
    current_origin_develop_sha: str,
    private_lane_dev5_sha256: str = "e7656acb6bdd0ecbc5f35a2026e275fd31e02489eee838e641114f981522312d",
    t0_public_attestation_sha256: str = "19a684f5b066496dfd8a75efc35ba935ef9493451b98ea038eeb967bc1f1b000",
) -> dict[str, Any]:
    """Generate offline exact-byte pre-publication manifest verified by non-PR-controlled external verifier (`PUB-R1-PUBLISH-04`)."""
    real_cand = Path(os.path.realpath(candidate_staging_dir))
    real_self = Path(os.path.realpath(__file__))
    try:
        real_self.relative_to(real_cand)
        raise RuntimeError("PREPUBLICATION_VERIFIER_MUST_RUN_FROM_OUTSIDE_CANDIDATE_STAGING_DIR")
    except ValueError:
        pass

    rc, audit_rep = evaluate_public_release_gate(
        real_cand,
        require_external_trusted_verifier=True,
        require_owner_approval=False,
        offline_candidate_audit=True,
    )
    if rc != 0:
        raise RuntimeError(f"Pre-publication candidate audit failed: {audit_rep}")

    all_paths = sorted(
        (p for p in real_cand.rglob("*") if p.is_file() or p.is_symlink()),
        key=lambda p: p.relative_to(real_cand).as_posix(),
    )
    hidden_paths: list[str] = []
    entries: list[dict[str, Any]] = []
    for p in all_paths:
        rel = p.relative_to(real_cand).as_posix()
        if any(seg.startswith(".") for seg in rel.split("/")):
            hidden_paths.append(rel)
        raw = p.read_bytes()
        entries.append(
            {
                "destination_repo_path": rel,
                "size_bytes": len(raw),
                "sha256": _sha256_bytes(raw),
            }
        )

    if hidden_paths != [GATE_WORKFLOW_REL_PATH]:
        raise RuntimeError(f"UNEXPECTED_DOTFILES_IN_PREPUBLICATION_TREE: {hidden_paths}")

    skel_sha = _sha256_bytes(
        (real_cand / "tools/w07_stage1/baselines/w07_zh_methodology_skeleton.py").read_bytes()
    )
    lg_sha = _sha256_bytes(
        (real_cand / "tools/w07_stage1/baselines/w07_dev1_os_aware_log_guard_reference.py").read_bytes()
    )
    pins_sha = _sha256_bytes(
        (real_cand / "tools/w07_stage1/baselines/W07_TRUSTED_AUTHORITY_PINS_v1.json").read_bytes()
    )

    body = {
        "schema_version": "W07_PREPUBLICATION_EXACT_BYTE_MANIFEST_V1",
        "generated_by_trusted_verifier_version": TOOL_VERSION,
        "trusted_verifier_sha256": _sha256_bytes(real_self.read_bytes()),
        "verifier_executed_outside_candidate_tree": True,
        "candidate_code_executed_count": 0,
        "target_public_repository": "namnh102/wanderai",
        "current_origin_develop_sha": current_origin_develop_sha,
        "candidate_file_count": len(entries),
        "hidden_or_dot_paths_audit": {
            "unexpected_hidden_files_count": 0,
            "sole_explicit_dot_directory_workflow": GATE_WORKFLOW_REL_PATH,
        },
        "excluded_sensitive_categories_verified_absent": {
            "quarantined_dev5_and_dev6_absent": True,
            "t0_private_and_unsigned_draft_absent": True,
            "host_local_win32_metadata_absent": True,
            "withheld_local_path_python_verifiers_absent": True,
            "unredacted_authority_markdown_originals_absent": True,
        },
        "frozen_baseline_hash_receipts": {
            "frozen_zh_skeleton_sha256": skel_sha,
            "os_aware_log_guard_sha256": lg_sha,
            "null_authority_pins_template_sha256": pins_sha,
            "withheld_private_dev5_manifest_sha256": private_lane_dev5_sha256,
            "t0_public_attestation_sha256": t0_public_attestation_sha256,
        },
        "live_publication_status": "LIVE_HOLD",
        "live_hold_reasons": [
            "PINNED_LIVE_PUBLICATION_OWNER_ED25519_PUBKEY_UNPROVISIONED",
            "DEVELOP_BRANCH_TRUSTED_VERIFIER_BOOTSTRAP_AND_RULESET_NOT_YET_APPLIED",
            "GATE_PUB_ALLOWLIST_01_AWAITING_OWNER_EXACT_FILE_SET_APPROVAL",
        ],
        "candidate_files": entries,
    }
    return {
        **body,
        "prepublication_manifest_canonical_sha256": _sha256_bytes(_canonical_json_bytes(body)),
    }


def install_local_git_hooks(root: Path, *, external_trusted_verifier_path: Path | None = None) -> dict[str, str]:
    """Install local client-side `pre-commit` & `pre-push` defense-in-depth hooks (never claimed to prevent first disclosure)."""
    real_root = Path(os.path.realpath(root))
    hooks_dir = real_root / ".git" / "hooks"
    if not hooks_dir.is_dir():
        raise FileNotFoundError(f"Git hooks directory not found: {hooks_dir}")

    ext_ver = (
        str(Path(os.path.realpath(external_trusted_verifier_path)))
        if external_trusted_verifier_path is not None
        else "${W07_EXTERNAL_TRUSTED_VERIFIER_PY:-}"
    )

    pre_commit_sh = (
        "#!/bin/sh\n"
        "# Client-side defense-in-depth pre-commit check (NOT authoritative pre-publication gate)\n"
        "set -eu\n"
        'REPO_ROOT="$(git rev-parse --show-toplevel)"\n'
        'PY_BIN="${PYTHON_BIN:-python}"\n'
        f'VERIFIER_PY="{ext_ver}"\n'
        'if [ -z "${VERIFIER_PY}" ]; then VERIFIER_PY="${REPO_ROOT}/scripts/check_w07_public_release_denylist.py"; fi\n'
        '"${PY_BIN}" -B -W error "${VERIFIER_PY}" \\\n'
        '  --root "${REPO_ROOT}" \\\n'
        "  --git-pre-commit \\\n"
        "  --offline-candidate-audit\n"
    )
    pre_push_sh = (
        "#!/bin/sh\n"
        "# Client-side defense-in-depth pre-push check (requires EXTERNAL trusted verifier & signed V2 Owner approval)\n"
        "set -eu\n"
        'REPO_ROOT="$(git rev-parse --show-toplevel)"\n'
        'PY_BIN="${PYTHON_BIN:-python}"\n'
        'BASE_REF="${W07_TRUSTED_DEVELOP_BASE_REF:-origin/develop}"\n'
        f'VERIFIER_PY="{ext_ver}"\n'
        'if [ -z "${VERIFIER_PY}" ]; then\n'
        '  echo "BLOCKED: set W07_EXTERNAL_TRUSTED_VERIFIER_PY outside repo before git push" >&2\n'
        "  exit 1\n"
        "fi\n"
        'if [ -n "${W07_TRUSTED_OWNER_APPROVAL_JSON:-}" ]; then\n'
        '  "${PY_BIN}" -B -W error "${VERIFIER_PY}" \\\n'
        '    --root "${REPO_ROOT}" \\\n'
        "    --require-external-trusted-verifier \\\n"
        '    --git-diff-base "${BASE_REF}" \\\n'
        "    --git-objects-only \\\n"
        "    --require-owner-approval \\\n"
        '    --trusted-owner-approval-json "${W07_TRUSTED_OWNER_APPROVAL_JSON}"\n'
        "else\n"
        '  "${PY_BIN}" -B -W error "${VERIFIER_PY}" \\\n'
        '    --root "${REPO_ROOT}" \\\n'
        "    --require-external-trusted-verifier \\\n"
        '    --git-diff-base "${BASE_REF}" \\\n'
        "    --git-objects-only \\\n"
        "    --require-owner-approval\n"
        "fi\n"
    )

    pc_path = hooks_dir / "pre-commit"
    pp_path = hooks_dir / "pre-push"
    pc_path.write_bytes(pre_commit_sh.encode("utf-8"))
    pp_path.write_bytes(pre_push_sh.encode("utf-8"))
    for hp in (pc_path, pp_path):
        hp.chmod(hp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return {"pre_commit_hook": str(pc_path), "pre_push_hook": str(pp_path)}


def scan_Candidate_tree(
    root: Path,
    *,
    rel_paths: list[str] | None = None,
    allowlist_json_path: Path | None = None,
    trusted_owner_approval_json: Path | None = None,
    git_diff_base: str | None = None,
    require_owner_approval: bool = False,
    sandbox_trust_anchor: EphemeralSandboxPublicationTrustAnchor | None = None,
) -> dict[str, Any]:
    _rc, rep = evaluate_public_release_gate(
        root,
        allowlist_json_path=allowlist_json_path,
        git_diff_base=git_diff_base,
        require_owner_approval=require_owner_approval,
        offline_candidate_audit=(not require_owner_approval),
        trusted_owner_approval_json=trusted_owner_approval_json,
        sandbox_trust_anchor=sandbox_trust_anchor,
    )
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="W07 Authoritative Trusted Publication Boundary Verifier (v2.0.0)")
    ap.add_argument("--root", type=Path, required=True, help="Candidate repo or staging root to inspect as inert data")
    ap.add_argument("--allowlist-json", type=Path, default=None)
    ap.add_argument("--git-diff-base", type=str, default=None, help="Trusted base ref or SHA (e.g. origin/develop)")
    ap.add_argument("--candidate-commit-ref", type=str, default="HEAD", help="Candidate commit SHA or ref")
    ap.add_argument("--git-objects-only", action="store_true", help="Inspect git blobs only without checking out PR files")
    ap.add_argument("--git-pre-commit", action="store_true")
    ap.add_argument("--git-pre-push", action="store_true")
    ap.add_argument("--ci-pr-gate", action="store_true")
    ap.add_argument("--require-external-trusted-verifier", action="store_true")
    ap.add_argument("--force-w07-scope", action="store_true")
    ap.add_argument("--require-owner-approval", action="store_true")
    ap.add_argument("--offline-candidate-audit", action="store_true")
    ap.add_argument("--trusted-owner-approval-json", type=Path, default=None)
    ap.add_argument("--ephemeral-sandbox-owner-pubkey-hex", type=str, default=None)
    ap.add_argument("--ephemeral-sandbox-utc-date", type=str, default=None)
    ap.add_argument("--emit-prepublication-manifest", type=Path, default=None)
    ap.add_argument("--current-origin-develop-sha", type=str, default="b124d2c8e8be788c54227c9e1ae1af8df8a35d60")
    ap.add_argument("--install-local-hooks", action="store_true")
    ap.add_argument("--external-verifier-for-hooks", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.install_local_hooks:
        installed = install_local_git_hooks(args.root, external_trusted_verifier_path=args.external_verifier_for_hooks)
        print(json.dumps({"status": "LOCAL_GIT_HOOKS_INSTALLED", **installed}, indent=2, sort_keys=True))
        return 0

    if args.emit_prepublication_manifest is not None:
        man = generate_prepublication_exact_byte_manifest(
            candidate_staging_dir=args.root,
            current_origin_develop_sha=args.current_origin_develop_sha,
        )
        args.emit_prepublication_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.emit_prepublication_manifest.write_text(
            json.dumps(man, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps({"status": "PREPUBLICATION_EXACT_BYTE_MANIFEST_EMITTED", "sha256": man["prepublication_manifest_canonical_sha256"]}, indent=2))
        return 0

    if (args.ci_pr_gate or args.git_pre_push) and args.offline_candidate_audit:
        print(json.dumps({"scan_status": "BLOCKED_INVALID_FLAG_COMBINATION"}, indent=2))
        return 1
    if args.ci_pr_gate and not args.git_diff_base:
        print(json.dumps({"scan_status": "BLOCKED_MISSING_GIT_DIFF_BASE"}, indent=2))
        return 1
    if args.ci_pr_gate and args.ephemeral_sandbox_owner_pubkey_hex is not None:
        print(json.dumps({"scan_status": "BLOCKED_SANDBOX_ANCHOR_FORBIDDEN_IN_CI_PR_GATE"}, indent=2))
        return 1

    sbx_anchor: EphemeralSandboxPublicationTrustAnchor | None = None
    if args.ephemeral_sandbox_owner_pubkey_hex is not None:
        sbx_anchor = EphemeralSandboxPublicationTrustAnchor(
            owner_ed25519_pubkey_hex=args.ephemeral_sandbox_owner_pubkey_hex,
            sandbox_utc_date=args.ephemeral_sandbox_utc_date,
        )

    eff_req_owner = True
    if args.offline_candidate_audit and not args.require_owner_approval:
        eff_req_owner = False

    eff_ext = args.require_external_trusted_verifier or args.ci_pr_gate

    rc, report = evaluate_public_release_gate(
        args.root,
        allowlist_json_path=args.allowlist_json,
        git_diff_base=args.git_diff_base,
        candidate_commit_ref=args.candidate_commit_ref,
        git_objects_only=args.git_objects_only or args.ci_pr_gate,
        git_pre_commit=args.git_pre_commit,
        require_external_trusted_verifier=eff_ext,
        force_w07_scope=args.force_w07_scope,
        require_owner_approval=eff_req_owner,
        offline_candidate_audit=args.offline_candidate_audit,
        trusted_owner_approval_json=args.trusted_owner_approval_json,
        sandbox_trust_anchor=sbx_anchor,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return rc


if __name__ == "__main__":
    sys.exit(main())
