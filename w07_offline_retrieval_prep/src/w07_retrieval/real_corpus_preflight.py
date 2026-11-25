"""Enforceable receipt-gated preflight & genuine acceptance checks for STUB-01..STUB-05.

Supports two explicitly selected authorization modes for read-only 137-document preflight
(`STUB-01..STUB-05`, covering `FX-01..FX-05`):
1. `ED25519_SIGNED_V1` (default legacy mode requiring a detached Ed25519 signature verified
   against `PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX`), and
2. `OWNER_CHAT_READONLY_V1` (scoped non-cryptographic Owner chat-approval mode authorized by
   `OD-W07-G15-STUB01-05-CHAT-AUTH-WAIVER-V1-20261121-01` solely for one offline read-only
   pass of `STUB-01..STUB-05` on the 137-document Primary Arm P corpus; explicitly records
   `identity_authentication = "NOT_CRYPTOGRAPHICALLY_VERIFIED"` and never claims cryptographic
   Owner identity verification).

CRITICAL GOVERNANCE & SECURITY INVARIANTS:
1. Plain environment variables (`W07_G15_FROZEN=1`, `W07_OWNER_AUTHORIZED=1`,
   `W07_STUB_01_05_AUTHORIZED=1`) NEVER unlock `STUB-01..STUB-05` in either mode.
2. `STUB-06`, formal `G3/G4` (`w07_retrieval.runner.validate_formal_execution_gate`),
   `G2/G2A/G2B`, `G5`, `G6`, `FINAL-50`, `DEV`/`T0`, and live API calls remain strictly
   in `HOLD` (`False`) and cannot use `OWNER_CHAT_READONLY_V1`.
3. Scientific bindings (`F-01` & `F-02`):
   - `STUB-01` (`F-01`) cross-checks the 7-artifact bundle manifest AND the on-disk files
     against the pinned 7-artifact table (`PINNED_LIVE_137_CORPUS_7_ARTIFACTS`).
   - `STUB-03` (`F-02`) verifies that the computed sanitized view `V` digest equals the
     pinned SHA-256 (`046424e521f967f6c5575da1eeb914e5d340a118861c0cf04ca45256b364533d`
     on the live 137-doc profile using the exact `G15-R01` `\\n<<<DOC>>>\\n` serialization),
     and scopes the 4-branch check strictly to sanitizer repeatability.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from w07_retrieval.chunker_c0 import C0Chunker, chunk_corpus_c0
from w07_retrieval.chunker_c1 import BOILERPLATE_FOOTER_ALLOWLIST, chunk_corpus_c1
from w07_retrieval.runner import (
    EXPECTED_CITY_COUNTS,
    EXPECTED_ELIGIBLE_DOC_COUNT,
    EXPECTED_R_AUDIT_REMAINING,
    EXPECTED_R_AUDIT_REMOVED,
    EXPECTED_SANITIZED_VIEW_V_137_SHA256,
    FORBIDDEN_SYNTHETIC_PATH_TOKENS,
    KNOWN_PROTECTED_ARTIFACT_SHA256S,
    _verify_ed25519_signature,
    validate_synthetic_prep_boundaries,
)
from w07_retrieval.sanitizer import (
    KNOWN_FAMILIES,
    SanitizationResult,
    intervals_contain,
    project_v_span_to_s,
    sanitize_canonical_to_view,
)
from w07_retrieval.schema import (
    PINNED_SNAPSHOT_ID,
    PINNED_TOKENIZER_SHA256,
    CanonicalDocument,
    load_canonical_document,
    load_corpus_jsonl,
)
from w07_retrieval.visibility import load_minilm_tokenizer, resolve_snapshot_dir

StubPreflightAuthMode = Literal["ED25519_SIGNED_V1", "OWNER_CHAT_READONLY_V1"]
VALID_STUB_PREFLIGHT_AUTH_MODES: Tuple[str, ...] = (
    "ED25519_SIGNED_V1",
    "OWNER_CHAT_READONLY_V1",
)

APPROVED_ANNEX_V0_2_2_SHA256 = (
    "e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940"
)
APPROVED_ANNEX_V0_2_2_BYTES = 71761
PARENT_ANNEX_V0_2_1_SHA256 = (
    "842530dd737e2b2371280a4091ca760e540ec783d6ae654d462e33e148075740"
)
PROTOCOL_V1_0_LF_SHA256 = (
    "5056c5c2373ee9584b8850ba49411160cc2c382ad6315aaada4c05fb9b0030c2"
)
APPROVED_TECH_FREEZE_DECISION_ID = "OD-W07-G15-TECH-FREEZE-V022-20261121-01"
APPROVED_TECH_FREEZE_DECISION_SHA256 = (
    "ee6b7bdb6354f51f6da784adeeceb7418d17bb2c63acfcf59f37d9c7a38bcff3"
)
APPROVED_TECH_FREEZE_RECEIPT_SCHEMA = (
    "GOMATE_W07_G15_TECH_FREEZE_OWNER_CHAT_APPROVAL_RECEIPT_V1"
)
APPROVED_TECH_FREEZE_RECEIPT_SHA256 = (
    "1db438d30ad042296fca38abd882de0d1951d4dc1ff83c31b86a41d5765b6937"
)
PINNED_LIVE_137_SANITIZED_VIEW_V_SHA256 = EXPECTED_SANITIZED_VIEW_V_137_SHA256

# Scoped Owner Chat-Approval Waiver v1.0 constants (2026-11-21)
OWNER_CHAT_AUTH_WAIVER_DECISION_ID = (
    "OD-W07-G15-STUB01-05-CHAT-AUTH-WAIVER-V1-20261121-01"
)
OWNER_CHAT_AUTH_WAIVER_MD_SHA256 = (
    "f01ccab9028a5e1952cfd5e53b3d7b6bc40a1937bc117d0fd804dbc61fc7699b"
)
OWNER_CHAT_AUTH_WAIVER_MD_BYTES = 9793
OWNER_CHAT_AUTH_POLICY_RECEIPT_SCHEMA_V1 = (
    "GOMATE_W07_STUB01_05_OWNER_CHAT_AUTH_POLICY_V1"
)
OWNER_CHAT_AUTH_POLICY_RECEIPT_SHA256 = (
    "aa0881be1438dee8b3088b91a558abe5fbb0b85444bb2af86748ee61f5f294be"
)
OWNER_CHAT_AUTH_POLICY_RECEIPT_BYTES = 2465
ORIGINAL_STUB01_05_EXEC_DECISION_ID = (
    "OD-W07-G15-STUB01-05-READONLY-EXEC-20261121-01"
)
ORIGINAL_STUB01_05_EXEC_DECISION_SHA256 = (
    "4e3ec73d0f04c2e7966a2ac759e0daf68d2a22f84f9b581eba2659450d9336a2"
)
PINNED_STAGE_A_CORPUS_BUNDLE_MANIFEST_SHA256 = (
    "9d417dc01692a58fa91e918a578470fcc1f3c89857cffe70e20f274960213096"
)

# Remains None while legacy signed mode is unprovisioned.
PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX: Optional[str] = None

STUB01_05_AUTH_RECEIPT_SCHEMA_V1 = (
    "W07_G15_STUB01_05_READONLY_CORPUS_AUTH_RECEIPT_V1"
)
STUB01_05_CORPUS_BUNDLE_SCHEMA_V1 = (
    "W07_G15_STUB01_05_CORPUS_BUNDLE_MANIFEST_V1"
)
STUB01_05_AUTHORIZED_SCOPE = (
    "READONLY_137_CORPUS_STUB_01_TO_05_PREFLIGHT_ONLY"
)
ED25519_STUB01_05_PREFLIGHT_DOMAIN_ASCII = (
    "W07-G15-STUB01-05-READONLY-CORPUS-AUTH-V1"
)
ED25519_STUB01_05_PREFLIGHT_DOMAIN_TAG = (
    b"W07-G15-STUB01-05-READONLY-CORPUS-AUTH-V1\x00"
)
ALLOWED_READONLY_STUB_IDS: Tuple[str, ...] = (
    "STUB-01",
    "STUB-02",
    "STUB-03",
    "STUB-04",
    "STUB-05",
)
FOUR_BRANCH_SANITIZER_CHECK_SCOPE = (
    "SANITIZER_REPEATABILITY_ONLY_NOT_INDEPENDENT_PRODUCTION_RETRIEVAL_PATHS"
)

_HEX40_RE = re.compile(r"\A[0-9a-f]{40}\Z")
_HEX64_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_HEX128_RE = re.compile(r"\A[0-9a-f]{128}\Z")


@dataclass(frozen=True)
class PinnedArtifactSpec:
    """Exact artifact identity, byte length, SHA-256, and Git blob SHA-1 from frozen authority."""

    artifact_id: str
    canonical_repo_path: str
    filename: str
    size_bytes: int
    sha256: str
    git_blob_sha1: str


PINNED_LIVE_137_CORPUS_7_ARTIFACTS: Tuple[PinnedArtifactSpec, ...] = (
    PinnedArtifactSpec(
        artifact_id="w07_review_target_60_pois_v1",
        canonical_repo_path="data/evaluation/w07/w07_review_target_60_pois_v1.json",
        filename="w07_review_target_60_pois_v1.json",
        size_bytes=44621,
        sha256="3a065165d038f300f5dc422180fcaf3cef265ac1a100ea8e841daaba1a82d5d4",
        git_blob_sha1="0cfe3ac65058875a810e2355346c27ebe43b1100",
    ),
    PinnedArtifactSpec(
        artifact_id="w07_b1b_source_decisions_v1",
        canonical_repo_path="data/evaluation/w07/w07_b1b_source_decisions_v1.json",
        filename="w07_b1b_source_decisions_v1.json",
        size_bytes=607671,
        sha256="edbec84b6161862d439ce2b5d9687b15bd181656b7fa8ff145a713f74afe1249",
        git_blob_sha1="2197326f459a69d07472f14c5e463e62a0de7277",
    ),
    PinnedArtifactSpec(
        artifact_id="w07_b1b_acquisition_summary_v1",
        canonical_repo_path="data/evaluation/w07/w07_b1b_acquisition_summary_v1.json",
        filename="w07_b1b_acquisition_summary_v1.json",
        size_bytes=94595,
        sha256="1cf83d3b143f9ceba85ea0c592bf2d339b28d1f0734507aea4c46648dc05e1a0",
        git_blob_sha1="391c14218017b27290cdd7378068d42638aa543a",
    ),
    PinnedArtifactSpec(
        artifact_id="poi_knowledge_acquired_v1",
        canonical_repo_path="data/curated/w07/poi_knowledge_" + "acquired_v1.jsonl",
        filename="poi_knowledge_" + "acquired_v1.jsonl",
        size_bytes=594824,
        sha256="9b0ed36e060924057872a2e8fe9941940f7bc3455f2c9cad21cdc9a9c1141fda",
        git_blob_sha1="cbb6da5e498ffd050e345ee97010bcd60a0aeab8",
    ),
    PinnedArtifactSpec(
        artifact_id="w07_b1a_existing_poi_knowledge_audit_v1",
        canonical_repo_path="data/evaluation/w07/w07_b1a_existing_poi_knowledge_audit_v1.json",
        filename="w07_b1a_existing_poi_knowledge_audit_v1.json",
        size_bytes=270704,
        sha256="433c722dd2f03946ab0a15830b53ef628d76937fa2e8e63a9939e73bb469e563",
        git_blob_sha1="29c1050fd29274d03fdb3f91312520d555a701ee",
    ),
    PinnedArtifactSpec(
        artifact_id="w07_b1_fix_01b_reingestion_v1",
        canonical_repo_path="data/evaluation/w07/w07_b1_fix_01b_reingestion_v1.json",
        filename="w07_b1_fix_01b_reingestion_v1.json",
        size_bytes=11368,
        sha256="38516e31df5f35f7efed2c5a1c355a44778acfdaef8b5c29354c3d56a32bfc71",
        git_blob_sha1="f9f2785210a07d222d1b8112bbf8bfd4792152d5",
    ),
    PinnedArtifactSpec(
        artifact_id="gomate_places_freeze_v2",
        canonical_repo_path="data/curated/gomate_places_" + "freeze_v2.json",
        filename="gomate_places_" + "freeze_v2.json",
        size_bytes=1024733,
        sha256="f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444",
        git_blob_sha1="4eebbfbe62de231ad490ba1694edd144a715f6ab",
    ),
)

PINNED_LIVE_7_ARTIFACT_SHA256S: frozenset[str] = frozenset(
    spec.sha256 for spec in PINNED_LIVE_137_CORPUS_7_ARTIFACTS
)


@dataclass(frozen=True)
class CorpusPreflightExpectations:
    """Target numeric, hash, and structural invariants for STUB-01..STUB-05 verification."""

    profile_name: str
    expected_artifact_count: int
    expected_pinned_artifacts: Tuple[PinnedArtifactSpec, ...]
    expected_eligible_doc_count: int
    expected_city_counts: Dict[str, int]
    expected_source_type_counts: Dict[str, int]
    expected_reference_only_admitted: int
    expected_total_canonical_s_chars: int
    expected_removed_r_audit_chars: int
    expected_retained_view_v_chars: int
    expected_r_audit_tags_removed: int
    expected_r_audit_docs_with_tags: int
    expected_r_audit_families: frozenset[str]
    expected_sanitized_view_v_sha256: str
    expected_empty_parent_headings_propagated: int
    expected_allowlisted_footer_drops: int
    expected_c1_chunk_count: Optional[int]
    expected_c1_max_token_ceiling: int
    overture_target_doc_id: str


LIVE_137_CORPUS_EXPECTATIONS = CorpusPreflightExpectations(
    profile_name="LIVE_FROZEN_137_ARM_P_CORPUS",
    expected_artifact_count=7,
    expected_pinned_artifacts=PINNED_LIVE_137_CORPUS_7_ARTIFACTS,
    expected_eligible_doc_count=EXPECTED_ELIGIBLE_DOC_COUNT,
    expected_city_counts=dict(EXPECTED_CITY_COUNTS),
    expected_source_type_counts={
        "overture_places_parquet": 23,
        "wikidata_entity": 28,
        "wikipedia_article": 26,
        "wikivoyage_poi_listing": 20,
        "osm_useful_structured": 40,
    },
    expected_reference_only_admitted=0,
    expected_total_canonical_s_chars=295644,
    expected_removed_r_audit_chars=4216,
    expected_retained_view_v_chars=291428,
    expected_r_audit_tags_removed=EXPECTED_R_AUDIT_REMOVED,
    expected_r_audit_docs_with_tags=23,
    expected_r_audit_families=KNOWN_FAMILIES,
    expected_sanitized_view_v_sha256=PINNED_LIVE_137_SANITIZED_VIEW_V_SHA256,
    expected_empty_parent_headings_propagated=21,
    # Derived paired-accounting repair after hierarchy-first C1 fix: retaining structural
    # empty parent `== Tham khảo ==` shifts 59 empty headings from (20+25+14) -> (21+24+14).
    expected_allowlisted_footer_drops=24,
    expected_c1_chunk_count=None,
    expected_c1_max_token_ceiling=128,
    overture_target_doc_id="w07-b1b-doc-overture-f0d424bd-e55bab3c",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def compute_git_blob_sha1(data: bytes) -> str:
    """Compute standard Git blob SHA-1 digest: sha1('blob <len>\\0' + data)."""
    header = f"blob {len(data)}\x00".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def canonical_stub01_05_auth_signing_bytes(receipt_payload: Dict[str, Any]) -> bytes:
    """Build domain-separated canonical UTF-8 JSON bytes for STUB-01..05 Ed25519 signature."""
    unsigned = {
        k: v
        for k, v in receipt_payload.items()
        if k != "owner_detached_signature_hex"
    }
    body = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return ED25519_STUB01_05_PREFLIGHT_DOMAIN_TAG + body


def verify_archived_v0_2_2_tech_freeze_baseline(
    *,
    annex_v0_2_2_path: Path,
    tech_freeze_receipt_path: Path,
    tech_freeze_decision_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Verify exact immutable bytes of archived Annex v0.2.2 and Owner chat-approval receipt."""
    annex_p = Path(annex_v0_2_2_path)
    receipt_p = Path(tech_freeze_receipt_path)
    if not annex_p.is_file() or annex_p.is_symlink():
        raise PermissionError(
            f"STUB01_05_BLOCKED_MISSING_V022_ANNEX: Annex v0.2.2 file not found: {annex_p}"
        )
    if not receipt_p.is_file() or receipt_p.is_symlink():
        raise PermissionError(
            f"STUB01_05_BLOCKED_MISSING_V022_RECEIPT: Tech-freeze receipt not found: {receipt_p}"
        )

    annex_bytes = annex_p.read_bytes()
    annex_sha = _sha256_bytes(annex_bytes)
    if (
        len(annex_bytes) != APPROVED_ANNEX_V0_2_2_BYTES
        or annex_sha != APPROVED_ANNEX_V0_2_2_SHA256
    ):
        raise PermissionError(
            "STUB01_05_BLOCKED_V022_ANNEX_HASH_MISMATCH: archived Annex v0.2.2 bytes "
            f"(len={len(annex_bytes)}, sha256={annex_sha}) do not match Owner-approved "
            f"baseline ({APPROVED_ANNEX_V0_2_2_BYTES} B, {APPROVED_ANNEX_V0_2_2_SHA256})."
        )

    receipt_bytes = receipt_p.read_bytes()
    receipt_sha = _sha256_bytes(receipt_bytes)
    if receipt_sha != APPROVED_TECH_FREEZE_RECEIPT_SHA256:
        raise PermissionError(
            "STUB01_05_BLOCKED_V022_RECEIPT_HASH_MISMATCH: tech-freeze receipt SHA-256 "
            f"({receipt_sha}) != expected ({APPROVED_TECH_FREEZE_RECEIPT_SHA256})."
        )

    receipt_obj = json.loads(receipt_bytes.decode("utf-8"))
    if receipt_obj.get("schema") != APPROVED_TECH_FREEZE_RECEIPT_SCHEMA:
        raise PermissionError("STUB01_05_BLOCKED_V022_RECEIPT_SCHEMA_MISMATCH")
    if receipt_obj.get("decision_id") != APPROVED_TECH_FREEZE_DECISION_ID:
        raise PermissionError("STUB01_05_BLOCKED_V022_DECISION_ID_MISMATCH")
    if receipt_obj.get("approved_annex_sha256") != APPROVED_ANNEX_V0_2_2_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_V022_RECEIPT_ANNEX_LINK_MISMATCH")
    if receipt_obj.get("parent_annex_v0_2_1_sha256") != PARENT_ANNEX_V0_2_1_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_V022_PARENT_HASH_MISMATCH")
    if receipt_obj.get("protocol_v1_0_lf_sha256") != PROTOCOL_V1_0_LF_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_V022_PROTOCOL_HASH_MISMATCH")
    if receipt_obj.get("erratum_e01_tokenizer_sha256") != PINNED_TOKENIZER_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_V022_TOKENIZER_HASH_MISMATCH")
    if receipt_obj.get("ratified_decisions") != [
        "OD-G15-01",
        "OD-G15-02",
        "OD-G15-03",
        "OD-G15-04",
    ]:
        raise PermissionError("STUB01_05_BLOCKED_V022_RATIFIED_DECISIONS_MISMATCH")
    if receipt_obj.get("od_g15_05") != "HOLD":
        raise PermissionError("STUB01_05_BLOCKED_OD_G15_05_MUST_BE_HOLD")

    decision_sha: Optional[str] = None
    if tech_freeze_decision_path is not None:
        dec_p = Path(tech_freeze_decision_path)
        if not dec_p.is_file() or dec_p.is_symlink():
            raise PermissionError(
                f"STUB01_05_BLOCKED_MISSING_V022_DECISION: decision file not found: {dec_p}"
            )
        decision_sha = _sha256_file(dec_p)
        if decision_sha != APPROVED_TECH_FREEZE_DECISION_SHA256:
            raise PermissionError(
                "STUB01_05_BLOCKED_V022_DECISION_HASH_MISMATCH: decision SHA-256 "
                f"({decision_sha}) != expected ({APPROVED_TECH_FREEZE_DECISION_SHA256})."
            )

    return {
        "approved_annex_v0_2_2_sha256": annex_sha,
        "approved_annex_v0_2_2_bytes": len(annex_bytes),
        "tech_freeze_receipt_sha256": receipt_sha,
        "tech_freeze_decision_sha256": decision_sha,
        "parent_annex_v0_2_1_sha256": PARENT_ANNEX_V0_2_1_SHA256,
        "protocol_v1_0_lf_sha256": PROTOCOL_V1_0_LF_SHA256,
        "erratum_e01_tokenizer_sha256": PINNED_TOKENIZER_SHA256,
    }


def _enforce_dry_run_sandbox_no_real_corpus(
    *,
    corpus_bundle_manifest_path: Path,
    bundle_obj: Dict[str, Any],
) -> None:
    """Hard-block synthetic dry-run mode from ever reading real 137-doc files."""
    protected_digests = KNOWN_PROTECTED_ARTIFACT_SHA256S | PINNED_LIVE_7_ARTIFACT_SHA256S
    base_dir = corpus_bundle_manifest_path.parent
    corpus_rel = bundle_obj.get("primary_corpus_jsonl")
    if type(corpus_rel) is not str or not corpus_rel:
        raise PermissionError("STUB01_05_BLOCKED_INVALID_BUNDLE_CORPUS_PATH")
    corpus_path = (base_dir / corpus_rel).resolve()

    dummy_q = base_dir / "dry_run_no_queries.jsonl"
    try:
        validate_synthetic_prep_boundaries(
            corpus_path=corpus_path,
            queries_path=dummy_q,
            docs=None,
        )
    except PermissionError as exc:
        raise PermissionError(
            "STUB01_05_SANDBOX_ESCAPE_BLOCKED: synthetic test mode cannot access "
            f"real 137-doc corpus or protected artifacts ({exc})"
        ) from exc

    for entry in bundle_obj.get("artifacts", []):
        if type(entry) is not dict:
            continue
        rel_p = str(entry.get("relative_path", ""))
        lower_rel = rel_p.lower()
        for tok in FORBIDDEN_SYNTHETIC_PATH_TOKENS:
            if tok in lower_rel:
                raise PermissionError(
                    "STUB01_05_SANDBOX_ESCAPE_BLOCKED: artifact path matches protected token "
                    f"{tok!r} while running in synthetic test mode."
                )
        decl_sha = str(entry.get("sha256", ""))
        if decl_sha in protected_digests:
            raise PermissionError(
                "STUB01_05_SANDBOX_ESCAPE_BLOCKED: artifact SHA-256 matches protected "
                f"real-corpus digest {decl_sha} while running in synthetic test mode."
            )
        f_path = (base_dir / rel_p).resolve()
        if f_path.is_file():
            actual_sha = _sha256_file(f_path)
            if actual_sha in protected_digests:
                raise PermissionError(
                    "STUB01_05_SANDBOX_ESCAPE_BLOCKED: on-disk file SHA-256 matches "
                    f"protected real-corpus digest {actual_sha} in synthetic test mode."
                )

    if corpus_path.is_file():
        docs = load_corpus_jsonl(corpus_path)
        try:
            validate_synthetic_prep_boundaries(
                corpus_path=corpus_path,
                queries_path=dummy_q,
                docs=docs,
            )
        except PermissionError as exc:
            raise PermissionError(
                "STUB01_05_SANDBOX_ESCAPE_BLOCKED: corpus documents triggered protected "
                f"real-corpus boundary in synthetic test mode ({exc})"
            ) from exc


def _verify_bundle_artifacts_against_pinned_specs(
    *,
    corpus_bundle_manifest_path: Path,
    bundle_obj: Dict[str, Any],
    expected_artifact_count: int,
    expected_pinned_artifacts: Sequence[PinnedArtifactSpec],
) -> List[Dict[str, Any]]:
    """3-way cross-check (`F-01`): Pinned Authority Specs <=> Bundle Manifest <=> Disk Bytes."""
    base_dir = Path(corpus_bundle_manifest_path).parent
    if (
        not expected_pinned_artifacts
        or len(expected_pinned_artifacts) != expected_artifact_count
    ):
        raise ValueError(
            "STUB-01_INVALID_PINNED_AUTHORITY_TABLE: expected_pinned_artifacts "
            "must be non-empty and match expected_artifact_count."
        )

    expected_by_id: Dict[str, PinnedArtifactSpec] = {}
    for spec in expected_pinned_artifacts:
        if spec.artifact_id in expected_by_id:
            raise ValueError(
                f"STUB-01_INVALID_PINNED_AUTHORITY_TABLE: duplicate artifact_id {spec.artifact_id!r}"
            )
        expected_by_id[spec.artifact_id] = spec

    artifacts = bundle_obj.get("artifacts")
    if type(artifacts) is not list:
        raise ValueError("STUB-01_MANIFEST_ARTIFACT_LIST_INVALID: artifacts must be a list")

    manifest_by_id: Dict[str, Dict[str, Any]] = {}
    seen_rel_paths: set[str] = set()
    for idx, item in enumerate(artifacts):
        if type(item) is not dict:
            raise ValueError(f"STUB-01_MANIFEST_ITEM_INVALID at index {idx}")
        art_id = item.get("artifact_id")
        rel_p = item.get("relative_path")
        if type(art_id) is not str or not art_id:
            raise ValueError(
                f"STUB-01_MISSING_ARTIFACT_IDENTITY: manifest entry at index {idx} missing artifact_id"
            )
        if type(rel_p) is not str or not rel_p:
            raise ValueError(
                f"STUB-01_MISSING_RELATIVE_PATH: manifest entry {art_id!r} missing relative_path"
            )
        if art_id in manifest_by_id or rel_p in seen_rel_paths:
            raise ValueError(
                f"STUB-01_DUPLICATE_ARTIFACT_IDENTITY: duplicate artifact_id {art_id!r} or path {rel_p!r}"
            )
        manifest_by_id[art_id] = item
        seen_rel_paths.add(rel_p)

    missing_ids = sorted(set(expected_by_id.keys()) - set(manifest_by_id.keys()))
    if missing_ids:
        raise ValueError(
            f"STUB-01_MISSING_PINNED_ARTIFACTS: bundle manifest is missing pinned authority artifacts: {missing_ids}"
        )

    extra_ids = sorted(set(manifest_by_id.keys()) - set(expected_by_id.keys()))
    if extra_ids:
        raise ValueError(
            f"STUB-01_UNEXPECTED_EXTRA_ARTIFACTS: bundle manifest contains unapproved extra artifacts: {extra_ids}"
        )

    if len(artifacts) != expected_artifact_count:
        raise ValueError(
            f"STUB-01_ARTIFACT_COUNT_MISMATCH: expected {expected_artifact_count}, got {len(artifacts)}"
        )

    verified_artifacts: List[Dict[str, Any]] = []
    for art_id, pinned_spec in expected_by_id.items():
        item = manifest_by_id[art_id]
        rel_p = str(item["relative_path"])
        decl_repo_path = str(item.get("canonical_repo_path", ""))
        decl_filename = Path(rel_p).name
        decl_bytes = int(item.get("size_bytes", -1))
        decl_sha256 = str(item.get("sha256", ""))
        decl_git_sha1 = str(item.get("git_blob_sha1", ""))

        if (
            _HEX64_RE.fullmatch(decl_sha256) is None
            or _HEX40_RE.fullmatch(decl_git_sha1) is None
        ):
            raise ValueError(
                f"STUB-01_MALFORMED_MANIFEST_HASH for {art_id!r}: sha256 or git_blob_sha1 invalid"
            )

        if (
            decl_repo_path != pinned_spec.canonical_repo_path
            or decl_filename != pinned_spec.filename
            or decl_bytes != pinned_spec.size_bytes
            or decl_sha256 != pinned_spec.sha256
            or decl_git_sha1 != pinned_spec.git_blob_sha1
        ):
            raise ValueError(
                f"STUB-01_AUTHORITY_SPEC_MISMATCH for {art_id!r}: manifest declared "
                f"(repo_path={decl_repo_path!r}, filename={decl_filename!r}, "
                f"size_bytes={decl_bytes}, sha256={decl_sha256!r}, git_blob_sha1={decl_git_sha1!r}) "
                "which does not match pinned scientific authority spec "
                f"(repo_path={pinned_spec.canonical_repo_path!r}, filename={pinned_spec.filename!r}, "
                f"size_bytes={pinned_spec.size_bytes}, sha256={pinned_spec.sha256!r}, "
                f"git_blob_sha1={pinned_spec.git_blob_sha1!r})."
            )

        fpath = (base_dir / rel_p).resolve()
        if not fpath.is_file() or fpath.is_symlink():
            raise FileNotFoundError(f"STUB-01_MISSING_DISK_ARTIFACT: {fpath}")
        raw = fpath.read_bytes()
        actual_bytes = len(raw)
        actual_sha256 = _sha256_bytes(raw)
        actual_git_sha1 = compute_git_blob_sha1(raw)
        if (
            actual_bytes != pinned_spec.size_bytes
            or actual_sha256 != pinned_spec.sha256
            or actual_git_sha1 != pinned_spec.git_blob_sha1
        ):
            raise ValueError(
                f"STUB-01_DISK_FILE_MISMATCH_AGAINST_PINNED_AUTHORITY for {art_id!r} ({rel_p}): "
                f"expected ({pinned_spec.size_bytes}, {pinned_spec.sha256}, {pinned_spec.git_blob_sha1}), "
                f"got ({actual_bytes}, {actual_sha256}, {actual_git_sha1})"
            )
        verified_artifacts.append(
            {
                "artifact_id": art_id,
                "canonical_repo_path": pinned_spec.canonical_repo_path,
                "relative_path": rel_p,
                "size_bytes": actual_bytes,
                "sha256": actual_sha256,
                "git_blob_sha1": actual_git_sha1,
                "matched_pinned_authority": True,
            }
        )
    return verified_artifacts


def _validate_owner_chat_readonly_v1_branch(
    *,
    requested_stub_id: str,
    baseline_info: Dict[str, Any],
    auth_p: Path,
    auth_obj: Dict[str, Any],
    bundle_p: Path,
    bundle_obj: Dict[str, Any],
    chat_auth_waiver_path: Optional[Path],
    original_exec_decision_path: Optional[Path],
    _test_only_trusted_owner_pubkey_hex: Optional[str],
    _synthetic_fixture_mode: bool,
) -> Dict[str, Any]:
    """Validate `OWNER_CHAT_READONLY_V1` policy receipt and preflight invariants."""
    if _test_only_trusted_owner_pubkey_hex is not None:
        raise PermissionError(
            "STUB01_05_BLOCKED_TEST_KEY_FORBIDDEN_IN_CHAT_MODE: "
            "_test_only_trusted_owner_pubkey_hex is forbidden in OWNER_CHAT_READONLY_V1."
        )

    if (
        auth_obj.get("schema_version") == STUB01_05_AUTH_RECEIPT_SCHEMA_V1
        or "_template_status" in auth_obj
    ):
        raise PermissionError(
            "STUB01_05_BLOCKED_UNSIGNED_ED25519_TEMPLATE_NOT_CHAT_POLICY: "
            "the legacy Ed25519 receipt template cannot be used as an OWNER_CHAT_READONLY_V1 policy receipt."
        )

    if chat_auth_waiver_path is None:
        raise PermissionError(
            "STUB01_05_BLOCKED_MISSING_CHAT_WAIVER_MD: OWNER_CHAT_READONLY_V1 requires "
            "chat_auth_waiver_path (GOMATE_W07_STUB01_05_OWNER_CHAT_AUTH_WAIVER_V1_0_2026-11-21.md)."
        )
    waiver_p = Path(chat_auth_waiver_path)
    if not waiver_p.is_file() or waiver_p.is_symlink():
        raise PermissionError(
            f"STUB01_05_BLOCKED_MISSING_CHAT_WAIVER_MD: waiver file not found: {waiver_p}"
        )
    waiver_bytes = waiver_p.read_bytes()
    waiver_sha = _sha256_bytes(waiver_bytes)
    if (
        len(waiver_bytes) != OWNER_CHAT_AUTH_WAIVER_MD_BYTES
        or waiver_sha != OWNER_CHAT_AUTH_WAIVER_MD_SHA256
    ):
        raise PermissionError(
            "STUB01_05_BLOCKED_CHAT_WAIVER_HASH_MISMATCH: waiver SHA-256/size "
            f"({len(waiver_bytes)} B, {waiver_sha}) != expected "
            f"({OWNER_CHAT_AUTH_WAIVER_MD_BYTES} B, {OWNER_CHAT_AUTH_WAIVER_MD_SHA256})."
        )

    orig_dec_sha: Optional[str] = None
    if original_exec_decision_path is not None:
        orig_p = Path(original_exec_decision_path)
        if not orig_p.is_file() or orig_p.is_symlink():
            raise PermissionError(
                f"STUB01_05_BLOCKED_MISSING_ORIG_EXEC_DECISION: {orig_p}"
            )
        orig_dec_sha = _sha256_file(orig_p)
        if orig_dec_sha != ORIGINAL_STUB01_05_EXEC_DECISION_SHA256:
            raise PermissionError(
                "STUB01_05_BLOCKED_ORIG_EXEC_DECISION_HASH_MISMATCH: "
                f"({orig_dec_sha}) != ({ORIGINAL_STUB01_05_EXEC_DECISION_SHA256})."
            )

    policy_bytes = auth_p.read_bytes()
    policy_sha = _sha256_bytes(policy_bytes)
    if not _synthetic_fixture_mode:
        if (
            len(policy_bytes) != OWNER_CHAT_AUTH_POLICY_RECEIPT_BYTES
            or policy_sha != OWNER_CHAT_AUTH_POLICY_RECEIPT_SHA256
        ):
            raise PermissionError(
                "STUB01_05_BLOCKED_CHAT_POLICY_RECEIPT_HASH_MISMATCH: policy receipt "
                f"({len(policy_bytes)} B, {policy_sha}) != pinned pack digest "
                f"({OWNER_CHAT_AUTH_POLICY_RECEIPT_BYTES} B, {OWNER_CHAT_AUTH_POLICY_RECEIPT_SHA256})."
            )

    if auth_obj.get("schema_version") != OWNER_CHAT_AUTH_POLICY_RECEIPT_SCHEMA_V1:
        raise PermissionError(
            f"STUB01_05_BLOCKED_INVALID_CHAT_POLICY_SCHEMA: expected {OWNER_CHAT_AUTH_POLICY_RECEIPT_SCHEMA_V1!r}"
        )
    if auth_obj.get("authorization_mode") != "OWNER_CHAT_READONLY_V1":
        raise PermissionError("STUB01_05_BLOCKED_CHAT_POLICY_MODE_MISMATCH")
    if auth_obj.get("decision_id") != OWNER_CHAT_AUTH_WAIVER_DECISION_ID:
        raise PermissionError("STUB01_05_BLOCKED_CHAT_POLICY_DECISION_ID_MISMATCH")
    if (
        auth_obj.get("original_execution_decision_id")
        != ORIGINAL_STUB01_05_EXEC_DECISION_ID
        or auth_obj.get("original_execution_decision_sha256")
        != ORIGINAL_STUB01_05_EXEC_DECISION_SHA256
    ):
        raise PermissionError(
            "STUB01_05_BLOCKED_ORIG_EXEC_DECISION_BINDING_MISMATCH"
        )
    if auth_obj.get("approved_annex_v0_2_2_sha256") != APPROVED_ANNEX_V0_2_2_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_ANNEX_V022_BINDING_MISMATCH")
    if (
        auth_obj.get("technical_freeze_owner_receipt_sha256")
        != APPROVED_TECH_FREEZE_RECEIPT_SHA256
    ):
        raise PermissionError("STUB01_05_BLOCKED_TECH_FREEZE_RECEIPT_BINDING_MISMATCH")
    if auth_obj.get("protocol_v1_lf_sha256") != PROTOCOL_V1_0_LF_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_PROTOCOL_V1_BINDING_MISMATCH")
    if auth_obj.get("pinned_tokenizer_json_sha256") != PINNED_TOKENIZER_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_TOKENIZER_SHA256_MISMATCH")
    if (
        auth_obj.get("pinned_sanitized_v_sha256")
        != PINNED_LIVE_137_SANITIZED_VIEW_V_SHA256
    ):
        raise PermissionError("STUB01_05_BLOCKED_PINNED_V_SHA256_BINDING_MISMATCH")
    if auth_obj.get("authorized_scope") != STUB01_05_AUTHORIZED_SCOPE:
        raise PermissionError(
            f"STUB01_05_BLOCKED_SCOPE_MISMATCH: expected {STUB01_05_AUTHORIZED_SCOPE!r}"
        )
    if auth_obj.get("authorized_stubs") != list(ALLOWED_READONLY_STUB_IDS):
        raise PermissionError(
            f"STUB01_05_BLOCKED_INVALID_AUTHORIZED_STUBS_LIST: expected exact {list(ALLOWED_READONLY_STUB_IDS)}"
        )
    if requested_stub_id not in auth_obj["authorized_stubs"]:
        raise PermissionError(
            f"STUB01_05_BLOCKED_STUB_NOT_IN_RECEIPT: {requested_stub_id!r}"
        )
    if auth_obj.get("authorized_execution_passes") != 1:
        raise PermissionError("STUB01_05_BLOCKED_EXECUTION_PASSES_MUST_BE_1")
    if auth_obj.get("authorized_docs_count") != EXPECTED_ELIGIBLE_DOC_COUNT:
        raise PermissionError("STUB01_05_BLOCKED_AUTHORIZED_DOCS_COUNT_MUST_BE_137")
    if auth_obj.get("authorized_arm") != "P":
        raise PermissionError("STUB01_05_BLOCKED_AUTHORIZED_ARM_MUST_BE_P")
    if auth_obj.get("real_137_corpus_readonly_stubs_authorized_by_chat") is not True:
        raise PermissionError(
            "STUB01_05_BLOCKED_NOT_AUTHORIZED: real_137_corpus_readonly_stubs_authorized_by_chat is not True."
        )

    for false_flag in (
        "stub_06_formal_g3_g4_authorized",
        "g2_g3_g4_g5_g6_authorized",
        "final50_dev_t0_live_api_authorized",
        "dataset_mutation_authorized",
        "public_push_merge_authorized",
        "scientific_methodology_amended",
        "cryptographic_owner_identity_verified",
        "owner_signature_present",
        "treat_as_cryptographic_signature",
    ):
        if auth_obj.get(false_flag) is not False:
            raise PermissionError(
                f"STUB01_05_BLOCKED_SCOPE_ESCALATION_FORBIDDEN: {false_flag} must be boolean False."
            )
    if auth_obj.get("od_g15_05") != "HOLD":
        raise PermissionError("STUB01_05_BLOCKED_OD_G15_05_MUST_BE_HOLD")

    if bundle_obj.get("schema_version") != STUB01_05_CORPUS_BUNDLE_SCHEMA_V1:
        raise PermissionError(
            f"STUB01_05_BLOCKED_INVALID_BUNDLE_SCHEMA: expected {STUB01_05_CORPUS_BUNDLE_SCHEMA_V1!r}"
        )

    actual_bundle_sha = _sha256_file(bundle_p)
    expected_bundle_sha = auth_obj.get(
        "corpus_bundle_manifest_expected_sha256_reported_by_antigravity"
    )
    if (
        type(expected_bundle_sha) is not str
        or _HEX64_RE.fullmatch(expected_bundle_sha) is None
        or actual_bundle_sha != expected_bundle_sha
    ):
        raise PermissionError(
            "STUB01_05_BLOCKED_BUNDLE_MANIFEST_HASH_MISMATCH: policy receipt expected "
            f"{expected_bundle_sha!r}, actual manifest SHA-256 is {actual_bundle_sha!r}."
        )
    if (
        not _synthetic_fixture_mode
        and actual_bundle_sha != PINNED_STAGE_A_CORPUS_BUNDLE_MANIFEST_SHA256
    ):
        raise PermissionError(
            "STUB01_05_BLOCKED_STAGE_A_MANIFEST_HASH_MISMATCH: live manifest SHA-256 "
            f"({actual_bundle_sha}) != pinned Stage A SHA-256 ({PINNED_STAGE_A_CORPUS_BUNDLE_MANIFEST_SHA256})."
        )

    if _synthetic_fixture_mode:
        _enforce_dry_run_sandbox_no_real_corpus(
            corpus_bundle_manifest_path=bundle_p,
            bundle_obj=bundle_obj,
        )
    else:
        # Precheck all 7 frozen artifacts on disk against PINNED_LIVE_137_CORPUS_7_ARTIFACTS
        # before opening any corpus records (§B.2 & §B.6).
        _verify_bundle_artifacts_against_pinned_specs(
            corpus_bundle_manifest_path=bundle_p,
            bundle_obj=bundle_obj,
            expected_artifact_count=7,
            expected_pinned_artifacts=PINNED_LIVE_137_CORPUS_7_ARTIFACTS,
        )

    return {
        "stub_id": requested_stub_id,
        "authorization_mode": "OWNER_CHAT_READONLY_V1",
        "identity_authentication": "NOT_CRYPTOGRAPHICALLY_VERIFIED",
        "authorization_assurance": (
            "ACCOUNTABLE_CHAT_DECISION_AND_HASHED_LOCAL_EVIDENCE__NOT_CRYPTOGRAPHIC_IDENTITY_AUTH"
        ),
        "decision_id": OWNER_CHAT_AUTH_WAIVER_DECISION_ID,
        "original_execution_decision_id": ORIGINAL_STUB01_05_EXEC_DECISION_ID,
        "original_execution_decision_sha256": (
            orig_dec_sha or ORIGINAL_STUB01_05_EXEC_DECISION_SHA256
        ),
        "chat_auth_waiver_sha256": waiver_sha,
        "policy_receipt_sha256": policy_sha,
        "authorized_scope": STUB01_05_AUTHORIZED_SCOPE,
        "approved_annex_v0_2_2_sha256": baseline_info["approved_annex_v0_2_2_sha256"],
        "tech_freeze_receipt_sha256": baseline_info["tech_freeze_receipt_sha256"],
        "corpus_bundle_manifest_sha256": actual_bundle_sha,
        "code_sha256": _sha256_file(Path(__file__).resolve()),
        "stub_06_formal_g3_g4_authorized": False,
        "g2_g3_g4_g5_g6_authorized": False,
        "final50_dev_t0_live_api_authorized": False,
        "od_g15_05": "HOLD",
        "trust_anchor_mode": (
            "SYNTHETIC_FIXTURE_CHAT_POLICY_TEST_ONLY"
            if _synthetic_fixture_mode
            else "OWNER_CHAT_READONLY_V1_LOCAL_HOST_EVIDENCE"
        ),
    }


def validate_stub01_05_readonly_preflight_gate(
    *,
    requested_stub_id: str,
    annex_v0_2_2_path: Optional[Path],
    tech_freeze_receipt_path: Optional[Path],
    stub_auth_receipt_path: Optional[Path],
    corpus_bundle_manifest_path: Optional[Path],
    auth_mode: StubPreflightAuthMode = "ED25519_SIGNED_V1",
    chat_auth_waiver_path: Optional[Path] = None,
    original_exec_decision_path: Optional[Path] = None,
    _test_only_trusted_owner_pubkey_hex: Optional[str] = None,
    _synthetic_fixture_mode: bool = False,
) -> Dict[str, Any]:
    """Fail-closed permission check for read-only 137-doc preflight stubs STUB-01..STUB-05.

    Supports two explicitly selected modes:
    - `ED25519_SIGNED_V1` (default legacy signed receipt path), and
    - `OWNER_CHAT_READONLY_V1` (scoped Owner chat-approval policy path).
    Plain environment variables NEVER grant execution authority in either mode.
    """
    if auth_mode not in VALID_STUB_PREFLIGHT_AUTH_MODES:
        raise PermissionError(
            f"STUB01_05_BLOCKED_INVALID_AUTH_MODE: {auth_mode!r} not in {VALID_STUB_PREFLIGHT_AUTH_MODES}"
        )

    if requested_stub_id not in ALLOWED_READONLY_STUB_IDS:
        raise PermissionError(
            f"STUB01_05_BLOCKED_FORBIDDEN_STUB_ID: {requested_stub_id!r} is not in "
            f"{ALLOWED_READONLY_STUB_IDS} (STUB-06 and G3/G4 cannot be unlocked by this gate)."
        )

    env_spoof = any(
        os.environ.get(k) == "1"
        for k in (
            "W07_G15_FROZEN",
            "W07_OWNER_AUTHORIZED",
            "W07_STUB_01_05_AUTHORIZED",
        )
    )
    if (
        annex_v0_2_2_path is None
        or tech_freeze_receipt_path is None
        or stub_auth_receipt_path is None
        or corpus_bundle_manifest_path is None
    ):
        spoof_msg = (
            " Plain environment variables (W07_G15_FROZEN / W07_OWNER_AUTHORIZED / "
            "W07_STUB_01_05_AUTHORIZED) were detected and rejected."
            if env_spoof
            else ""
        )
        raise PermissionError(
            "STUB01_05_BLOCKED_MISSING_RECEIPTS: STUB-01..05 require archived Annex v0.2.2, "
            "the v0.2.2 tech-freeze receipt, an authorization/policy receipt, "
            "and a corpus bundle manifest." + spoof_msg
        )

    baseline_info = verify_archived_v0_2_2_tech_freeze_baseline(
        annex_v0_2_2_path=Path(annex_v0_2_2_path),
        tech_freeze_receipt_path=Path(tech_freeze_receipt_path),
    )

    auth_p = Path(stub_auth_receipt_path)
    bundle_p = Path(corpus_bundle_manifest_path)
    if not auth_p.is_file() or auth_p.is_symlink():
        raise PermissionError(
            f"STUB01_05_BLOCKED_MISSING_RECEIPTS: stub_auth_receipt not found: {auth_p}"
        )
    if not bundle_p.is_file() or bundle_p.is_symlink():
        raise PermissionError(
            f"STUB01_05_BLOCKED_MISSING_RECEIPTS: corpus_bundle_manifest not found: {bundle_p}"
        )

    try:
        auth_obj = json.loads(auth_p.read_text(encoding="utf-8"))
        bundle_obj = json.loads(bundle_p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PermissionError(
            f"STUB01_05_BLOCKED_MALFORMED_RECEIPT_JSON: {exc}"
        ) from exc

    if type(auth_obj) is not dict or type(bundle_obj) is not dict:
        raise PermissionError("STUB01_05_BLOCKED_MALFORMED_RECEIPT_JSON")

    if auth_obj.get("schema") == APPROVED_TECH_FREEZE_RECEIPT_SCHEMA:
        raise PermissionError(
            "STUB01_05_BLOCKED_TECH_FREEZE_RECEIPT_NOT_EXECUTION_PERMIT: "
            "GOMATE_W07_G15_TECH_FREEZE_OWNER_APPROVAL_RECEIPT_2026-11-21.json sets "
            "real_137_corpus_readonly_stubs_authorized=false and has no Ed25519 signature; "
            "a separate Owner execution authorization receipt is required."
        )

    if auth_mode == "OWNER_CHAT_READONLY_V1":
        return _validate_owner_chat_readonly_v1_branch(
            requested_stub_id=requested_stub_id,
            baseline_info=baseline_info,
            auth_p=auth_p,
            auth_obj=auth_obj,
            bundle_p=bundle_p,
            bundle_obj=bundle_obj,
            chat_auth_waiver_path=chat_auth_waiver_path,
            original_exec_decision_path=original_exec_decision_path,
            _test_only_trusted_owner_pubkey_hex=_test_only_trusted_owner_pubkey_hex,
            _synthetic_fixture_mode=_synthetic_fixture_mode,
        )

    # Legacy ED25519_SIGNED_V1 branch (unchanged)
    if auth_obj.get("schema_version") != STUB01_05_AUTH_RECEIPT_SCHEMA_V1:
        raise PermissionError(
            f"STUB01_05_BLOCKED_INVALID_AUTH_SCHEMA: expected {STUB01_05_AUTH_RECEIPT_SCHEMA_V1!r}"
        )
    if auth_obj.get("approved_annex_v0_2_2_sha256") != APPROVED_ANNEX_V0_2_2_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_ANNEX_V022_BINDING_MISMATCH")
    if auth_obj.get("tech_freeze_owner_receipt_sha256") != APPROVED_TECH_FREEZE_RECEIPT_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_TECH_FREEZE_RECEIPT_BINDING_MISMATCH")
    if auth_obj.get("parent_annex_v0_2_1_sha256") != PARENT_ANNEX_V0_2_1_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_PARENT_ANNEX_V021_BINDING_MISMATCH")
    if auth_obj.get("protocol_v1_0_lf_sha256") != PROTOCOL_V1_0_LF_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_PROTOCOL_V1_BINDING_MISMATCH")
    if auth_obj.get("pinned_tokenizer_json_sha256") != PINNED_TOKENIZER_SHA256:
        raise PermissionError("STUB01_05_BLOCKED_TOKENIZER_SHA256_MISMATCH")
    if auth_obj.get("authorized_scope") != STUB01_05_AUTHORIZED_SCOPE:
        raise PermissionError(
            f"STUB01_05_BLOCKED_SCOPE_MISMATCH: expected {STUB01_05_AUTHORIZED_SCOPE!r}"
        )
    if auth_obj.get("real_137_corpus_readonly_stubs_authorized") is not True:
        raise PermissionError(
            "STUB01_05_BLOCKED_NOT_AUTHORIZED: real_137_corpus_readonly_stubs_authorized is not True."
        )
    if auth_obj.get("stub_06_formal_g3_g4_authorized") is not False:
        raise PermissionError(
            "STUB01_05_BLOCKED_SCOPE_ESCALATION_FORBIDDEN: stub_06_formal_g3_g4_authorized must be False."
        )
    if auth_obj.get("final50_or_dev_or_live_api_authorized") is not False:
        raise PermissionError(
            "STUB01_05_BLOCKED_SCOPE_ESCALATION_FORBIDDEN: final50_or_dev_or_live_api_authorized must be False."
        )

    authorized_stubs = auth_obj.get("authorized_stubs")
    if (
        type(authorized_stubs) is not list
        or not authorized_stubs
        or any(s not in ALLOWED_READONLY_STUB_IDS for s in authorized_stubs)
    ):
        raise PermissionError(
            "STUB01_05_BLOCKED_INVALID_AUTHORIZED_STUBS_LIST: authorized_stubs must be a "
            f"non-empty subset of {ALLOWED_READONLY_STUB_IDS}."
        )
    if requested_stub_id not in authorized_stubs:
        raise PermissionError(
            f"STUB01_05_BLOCKED_STUB_NOT_IN_RECEIPT: {requested_stub_id!r} not in {authorized_stubs}."
        )

    if bundle_obj.get("schema_version") != STUB01_05_CORPUS_BUNDLE_SCHEMA_V1:
        raise PermissionError(
            f"STUB01_05_BLOCKED_INVALID_BUNDLE_SCHEMA: expected {STUB01_05_CORPUS_BUNDLE_SCHEMA_V1!r}"
        )

    actual_bundle_sha = _sha256_file(bundle_p)
    if auth_obj.get("corpus_bundle_manifest_sha256") != actual_bundle_sha:
        raise PermissionError(
            "STUB01_05_BLOCKED_BUNDLE_MANIFEST_HASH_MISMATCH: receipt corpus_bundle_manifest_sha256 "
            f"({auth_obj.get('corpus_bundle_manifest_sha256')!r}) != actual ({actual_bundle_sha!r})."
        )

    if auth_obj.get("ed25519_domain_tag") != ED25519_STUB01_05_PREFLIGHT_DOMAIN_ASCII:
        raise PermissionError("STUB01_05_BLOCKED_DOMAIN_TAG_MISMATCH")

    pubkey_hex = auth_obj.get("owner_ed25519_pubkey_hex")
    sig_hex = auth_obj.get("owner_detached_signature_hex")
    if type(pubkey_hex) is not str or _HEX64_RE.fullmatch(pubkey_hex) is None:
        raise PermissionError("STUB01_05_BLOCKED_MALFORMED_PUBKEY")
    if type(sig_hex) is not str or _HEX128_RE.fullmatch(sig_hex) is None:
        raise PermissionError("STUB01_05_BLOCKED_MISSING_OR_MALFORMED_SIGNATURE")

    effective_trusted_pubkey = (
        _test_only_trusted_owner_pubkey_hex
        if _test_only_trusted_owner_pubkey_hex is not None
        else PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX
    )
    if effective_trusted_pubkey is None:
        raise PermissionError(
            "STUB01_05_BLOCKED_UNPINNED_LIVE_OWNER_KEY: PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX "
            "is None (HOLD awaiting separate Owner STUB-01..05 execution permission)."
        )
    if not hmac.compare_digest(pubkey_hex.lower(), effective_trusted_pubkey.lower()):
        raise PermissionError("STUB01_05_BLOCKED_PUBKEY_MISMATCH")

    signing_bytes = canonical_stub01_05_auth_signing_bytes(auth_obj)
    try:
        _verify_ed25519_signature(
            pubkey_hex=pubkey_hex,
            signature_hex=sig_hex,
            message=signing_bytes,
        )
    except PermissionError as exc:
        raise PermissionError(
            "STUB01_05_BLOCKED_INVALID_ED25519_SIGNATURE: detached signature failed verification."
        ) from exc

    if _test_only_trusted_owner_pubkey_hex is not None:
        _enforce_dry_run_sandbox_no_real_corpus(
            corpus_bundle_manifest_path=bundle_p,
            bundle_obj=bundle_obj,
        )

    return {
        "stub_id": requested_stub_id,
        "authorization_mode": "ED25519_SIGNED_V1",
        "identity_authentication": "ED25519_SIGNATURE_VERIFIED",
        "authorized_scope": STUB01_05_AUTHORIZED_SCOPE,
        "approved_annex_v0_2_2_sha256": baseline_info["approved_annex_v0_2_2_sha256"],
        "tech_freeze_receipt_sha256": baseline_info["tech_freeze_receipt_sha256"],
        "stub_auth_receipt_sha256": _sha256_file(auth_p),
        "corpus_bundle_manifest_sha256": actual_bundle_sha,
        "trust_anchor_mode": (
            "SYNTHETIC_DRY_RUN_SANDBOX_ONLY"
            if _test_only_trusted_owner_pubkey_hex is not None
            else "PINNED_LIVE_OWNER_TRUST_ANCHOR"
        ),
    }


def _load_bundle_and_corpus(
    corpus_bundle_manifest_path: Path,
) -> Tuple[Dict[str, Any], Path, List[CanonicalDocument]]:
    """Load bundle manifest and assemble CanonicalDocument list read-only in memory."""
    bundle_p = Path(corpus_bundle_manifest_path)
    base_dir = bundle_p.parent
    bundle_obj = json.loads(bundle_p.read_text(encoding="utf-8"))
    corpus_rel = bundle_obj.get("primary_corpus_jsonl")
    if type(corpus_rel) is not str or not corpus_rel:
        raise ValueError("Missing primary_corpus_jsonl in bundle manifest")
    corpus_p = (base_dir / corpus_rel).resolve()

    by_id: Dict[str, Path] = {}
    for item in bundle_obj.get("artifacts", []):
        if type(item) is dict and "artifact_id" in item and "relative_path" in item:
            by_id[str(item["artifact_id"])] = (
                base_dir / str(item["relative_path"])
            ).resolve()

    live_required_ids = {
        "poi_knowledge_acquired_v1",
        "w07_b1a_existing_poi_knowledge_audit_v1",
        "w07_review_target_60_pois_v1",
        "gomate_places_freeze_v2",
    }
    if live_required_ids.issubset(by_id.keys()):
        target_60 = json.loads(
            by_id["w07_review_target_60_pois_v1"].read_text(encoding="utf-8")
        )
        b1a_audit = json.loads(
            by_id["w07_b1a_existing_poi_knowledge_audit_v1"].read_text(encoding="utf-8")
        )
        places_freeze = json.loads(
            by_id["gomate_places_freeze_v2"].read_text(encoding="utf-8")
        )
        b1b_lines = [
            json.loads(ln)
            for ln in by_id["poi_knowledge_acquired_v1"]
            .read_text(encoding="utf-8")
            .splitlines()
            if ln.strip()
        ]
        target_by_id = {p["poi_id"]: p for p in target_60["pois"]}
        places_by_id = {p["place_id"]: p for p in places_freeze}
        useful_osm_ids = [
            r["poi_id"]
            for r in b1a_audit["target_poi_audit_records"]
            if r["osm_evidence"]["CONTENT_UTILITY_STATUS"] == "USEFUL_STRUCTURED_FACTS"
        ]

        docs: List[CanonicalDocument] = []
        for rec in b1b_lines:
            pid = rec.get("poi_id")
            city_fb = target_by_id[pid]["city"] if pid in target_by_id else None
            docs.append(load_canonical_document(rec, city_fallback=city_fb))

        for pid in useful_osm_ids:
            v2p = places_by_id[pid]
            tp = target_by_id[pid]
            osm_rec = {
                "document_id": f"osm-place-{pid}",
                "source_type": "osm_useful_structured",
                "poi_id": pid,
                "city": tp["city"],
                "title": v2p["name"],
                "place": v2p,
            }
            docs.append(load_canonical_document(osm_rec, city_fallback=tp["city"]))

        return bundle_obj, corpus_p, docs

    docs = load_corpus_jsonl(corpus_p)
    return bundle_obj, corpus_p, docs


def execute_stub01_fx01_hash_and_arm_p_counts(
    *,
    annex_v0_2_2_path: Path,
    tech_freeze_receipt_path: Path,
    stub_auth_receipt_path: Path,
    corpus_bundle_manifest_path: Path,
    expectations: CorpusPreflightExpectations = LIVE_137_CORPUS_EXPECTATIONS,
    auth_mode: StubPreflightAuthMode = "ED25519_SIGNED_V1",
    chat_auth_waiver_path: Optional[Path] = None,
    original_exec_decision_path: Optional[Path] = None,
    _test_only_trusted_owner_pubkey_hex: Optional[str] = None,
    _synthetic_fixture_mode: bool = False,
) -> Dict[str, Any]:
    """STUB-01 (`FX-01-CORPUS-HASH`): Cross-check 7-artifact manifest & disk files against pinned authority table (`F-01`)."""
    gate = validate_stub01_05_readonly_preflight_gate(
        requested_stub_id="STUB-01",
        annex_v0_2_2_path=annex_v0_2_2_path,
        tech_freeze_receipt_path=tech_freeze_receipt_path,
        stub_auth_receipt_path=stub_auth_receipt_path,
        corpus_bundle_manifest_path=corpus_bundle_manifest_path,
        auth_mode=auth_mode,
        chat_auth_waiver_path=chat_auth_waiver_path,
        original_exec_decision_path=original_exec_decision_path,
        _test_only_trusted_owner_pubkey_hex=_test_only_trusted_owner_pubkey_hex,
        _synthetic_fixture_mode=_synthetic_fixture_mode,
    )
    bundle_p = Path(corpus_bundle_manifest_path)
    bundle_obj = json.loads(bundle_p.read_text(encoding="utf-8"))

    verified_artifacts = _verify_bundle_artifacts_against_pinned_specs(
        corpus_bundle_manifest_path=bundle_p,
        bundle_obj=bundle_obj,
        expected_artifact_count=expectations.expected_artifact_count,
        expected_pinned_artifacts=expectations.expected_pinned_artifacts,
    )

    _, _, docs = _load_bundle_and_corpus(corpus_bundle_manifest_path)

    city_counts: Dict[str, int] = {}
    source_type_counts: Dict[str, int] = {}
    reference_only_admitted = 0
    for doc in docs:
        city = str(doc.city or doc.metadata.get("city", ""))
        city_counts[city] = city_counts.get(city, 0) + 1
        st = doc.source_type
        source_type_counts[st] = source_type_counts.get(st, 0) + 1
        if (
            doc.metadata.get("arm_disposition") == "REFERENCE_ONLY"
            or st == "REFERENCE_ONLY"
        ):
            reference_only_admitted += 1

    if len(docs) != expectations.expected_eligible_doc_count:
        raise ValueError(
            f"STUB-01 eligible doc count mismatch: expected {expectations.expected_eligible_doc_count}, got {len(docs)}"
        )
    if city_counts != expectations.expected_city_counts:
        raise ValueError(
            f"STUB-01 city_counts mismatch: expected {expectations.expected_city_counts}, got {city_counts}"
        )
    if source_type_counts != expectations.expected_source_type_counts:
        raise ValueError(
            f"STUB-01 source_type_counts mismatch: expected {expectations.expected_source_type_counts}, got {source_type_counts}"
        )
    if reference_only_admitted != expectations.expected_reference_only_admitted:
        raise ValueError(
            f"STUB-01 reference_only_admitted mismatch: expected 0, got {reference_only_admitted}"
        )

    b1b_count = sum(
        cnt for st, cnt in source_type_counts.items() if st != "osm_useful_structured"
    )
    osm_count = source_type_counts.get("osm_useful_structured", 0)

    return {
        "stub_id": "STUB-01",
        "target_fx_id": "FX-01-CORPUS-HASH",
        "status": "PASS",
        "profile_name": expectations.profile_name,
        "gate": gate,
        "verified_artifact_count": len(verified_artifacts),
        "verified_artifacts": verified_artifacts,
        "pinned_authority_cross_check_passed": True,
        "eligible_document_count": len(docs),
        "b1b_document_count": b1b_count,
        "osm_useful_document_count": osm_count,
        "city_counts": city_counts,
        "source_type_counts": source_type_counts,
        "reference_only_admitted": reference_only_admitted,
    }


def execute_stub02_fx02_canonical_conservation(
    *,
    annex_v0_2_2_path: Path,
    tech_freeze_receipt_path: Path,
    stub_auth_receipt_path: Path,
    corpus_bundle_manifest_path: Path,
    snapshot_dir: Optional[Path] = None,
    expectations: CorpusPreflightExpectations = LIVE_137_CORPUS_EXPECTATIONS,
    auth_mode: StubPreflightAuthMode = "ED25519_SIGNED_V1",
    chat_auth_waiver_path: Optional[Path] = None,
    original_exec_decision_path: Optional[Path] = None,
    _test_only_trusted_owner_pubkey_hex: Optional[str] = None,
    _synthetic_fixture_mode: bool = False,
) -> Dict[str, Any]:
    """STUB-02 (`FX-02-CANONICAL-CONSERVATION`): Verify S/V character conservation, breadcrumbs, and footers."""
    gate = validate_stub01_05_readonly_preflight_gate(
        requested_stub_id="STUB-02",
        annex_v0_2_2_path=annex_v0_2_2_path,
        tech_freeze_receipt_path=tech_freeze_receipt_path,
        stub_auth_receipt_path=stub_auth_receipt_path,
        corpus_bundle_manifest_path=corpus_bundle_manifest_path,
        auth_mode=auth_mode,
        chat_auth_waiver_path=chat_auth_waiver_path,
        original_exec_decision_path=original_exec_decision_path,
        _test_only_trusted_owner_pubkey_hex=_test_only_trusted_owner_pubkey_hex,
        _synthetic_fixture_mode=_synthetic_fixture_mode,
    )
    _, _, docs = _load_bundle_and_corpus(corpus_bundle_manifest_path)
    resolved_snap = resolve_snapshot_dir(snapshot_dir)
    tokenizer = load_minilm_tokenizer(resolved_snap, verify_sha256=True)

    sanitized_by_doc: Dict[str, SanitizationResult] = {
        doc.document_id: sanitize_canonical_to_view(doc.canonical_text_S)
        for doc in docs
    }
    c1_chunks, c1_audit = chunk_corpus_c1(docs, sanitized_by_doc, tokenizer)

    total_s_chars = int(c1_audit["total_s_cp"])
    removed_r_audit_chars = sum(
        r_end - r_start
        for res in sanitized_by_doc.values()
        for r_start, r_end in res.removed_intervals
    )
    total_v_chars = int(c1_audit["total_v_cp"])
    if total_s_chars - removed_r_audit_chars != total_v_chars:
        raise ValueError(
            f"STUB-02 S->V conservation failure: {total_s_chars} - {removed_r_audit_chars} != {total_v_chars}"
        )

    preserved_body_v = int(c1_audit["body_cp"])
    preserved_heading_v = int(c1_audit["heading_header_cp"])
    omitted_ws_v = int(c1_audit["omitted_ws_cp"])
    if preserved_body_v + preserved_heading_v + omitted_ws_v != total_v_chars:
        raise ValueError(
            "STUB-02 C1 partition conservation failure: "
            f"{preserved_body_v} + {preserved_heading_v} + {omitted_ws_v} != {total_v_chars}"
        )

    # Canonical S partition accounting (pre-strip body = preserved_body_v + removed_r_audit_chars)
    canonical_body_s = preserved_body_v + removed_r_audit_chars
    if canonical_body_s + preserved_heading_v + omitted_ws_v != total_s_chars:
        raise ValueError(
            "STUB-02 Canonical S partition conservation failure: "
            f"{canonical_body_s} + {preserved_heading_v} + {omitted_ws_v} != {total_s_chars}"
        )

    propagated_list = c1_audit["empty_parent_headings_propagated"]
    omitted_boilerplate_list = c1_audit["omitted_boilerplate_headings"]
    unique_empty_parents = len(
        {
            (str(item["document_id"]), str(p_h))
            for item in propagated_list
            for p_h in item.get("parents", [])
        }
    )
    allowlisted_footers = len(omitted_boilerplate_list)
    heading_only_chunks = sum(
        1 for ch in c1_chunks if ch.metadata.get("heading_only") is True
    )
    for item in omitted_boilerplate_list:
        h_txt = item.get("heading")
        if h_txt not in BOILERPLATE_FOOTER_ALLOWLIST:
            raise ValueError(f"Non-allowlisted footer heading dropped: {h_txt!r}")

    if total_s_chars != expectations.expected_total_canonical_s_chars:
        raise ValueError(
            f"STUB-02 total_s_chars mismatch: expected {expectations.expected_total_canonical_s_chars}, got {total_s_chars}"
        )
    if total_v_chars != expectations.expected_retained_view_v_chars:
        raise ValueError(
            f"STUB-02 total_v_chars mismatch: expected {expectations.expected_retained_view_v_chars}, got {total_v_chars}"
        )
    if unique_empty_parents != expectations.expected_empty_parent_headings_propagated:
        raise ValueError(
            "STUB-02 empty_parent_headings_propagated mismatch: "
            f"expected {expectations.expected_empty_parent_headings_propagated}, got {unique_empty_parents}"
        )
    if allowlisted_footers != expectations.expected_allowlisted_footer_drops:
        raise ValueError(
            f"STUB-02 allowlisted_footers mismatch: expected {expectations.expected_allowlisted_footer_drops}, got {allowlisted_footers}"
        )

    return {
        "stub_id": "STUB-02",
        "target_fx_id": "FX-02-CANONICAL-CONSERVATION",
        "status": "PASS",
        "profile_name": expectations.profile_name,
        "gate": gate,
        "total_canonical_s_chars": total_s_chars,
        "canonical_body_s_chars": canonical_body_s,
        "removed_r_audit_chars": removed_r_audit_chars,
        "total_view_v_chars": total_v_chars,
        "preserved_body_v_chars": preserved_body_v,
        "preserved_heading_v_chars": preserved_heading_v,
        "omitted_whitespace_v_chars": omitted_ws_v,
        "empty_parent_headings_propagated": unique_empty_parents,
        "child_sections_inheriting_parent_breadcrumbs": len(propagated_list),
        "allowlisted_footer_drops": allowlisted_footers,
        "non_allowlisted_empty_headings_preserved_as_chunks": heading_only_chunks,
        "c1_chunk_count": len(c1_chunks),
    }


def compute_canonical_view_v_sha256(
    docs: Sequence[CanonicalDocument],
    sanitized_by_doc: Dict[str, SanitizationResult],
) -> str:
    """Compute canonical view V SHA-256 using the exact audited G15-R01 serialization formula.

    Matches `verify_v0_2_1_real_corpus_g15_r01.py` (line 548):
    `\\n<<<DOC>>>\\n`.join(f"{did}::{view_V}" for did in arm_p_docs).encode("utf-8")
    which yields `046424e521f967f6c5575da1eeb914e5d340a118861c0cf04ca45256b364533d`
    on the frozen 137-document Primary Arm P corpus.
    """
    canonical_v_payload = "\n<<<DOC>>>\n".join(
        f"{doc.document_id}::{sanitized_by_doc[doc.document_id].view_V}"
        for doc in docs
    ).encode("utf-8")
    return hashlib.sha256(canonical_v_payload).hexdigest()


def execute_stub03_fx03_audit_tags_and_v_hash(
    *,
    annex_v0_2_2_path: Path,
    tech_freeze_receipt_path: Path,
    stub_auth_receipt_path: Path,
    corpus_bundle_manifest_path: Path,
    expectations: CorpusPreflightExpectations = LIVE_137_CORPUS_EXPECTATIONS,
    auth_mode: StubPreflightAuthMode = "ED25519_SIGNED_V1",
    chat_auth_waiver_path: Optional[Path] = None,
    original_exec_decision_path: Optional[Path] = None,
    _test_only_trusted_owner_pubkey_hex: Optional[str] = None,
    _synthetic_fixture_mode: bool = False,
) -> Dict[str, Any]:
    """STUB-03 (`FX-03-AUDIT-TAG-MULTI-SPAN`): Verify R_AUDIT stripping, pinned V SHA-256 (`F-02`), and Pi_{V->S} round-trips."""
    gate = validate_stub01_05_readonly_preflight_gate(
        requested_stub_id="STUB-03",
        annex_v0_2_2_path=annex_v0_2_2_path,
        tech_freeze_receipt_path=tech_freeze_receipt_path,
        stub_auth_receipt_path=stub_auth_receipt_path,
        corpus_bundle_manifest_path=corpus_bundle_manifest_path,
        auth_mode=auth_mode,
        chat_auth_waiver_path=chat_auth_waiver_path,
        original_exec_decision_path=original_exec_decision_path,
        _test_only_trusted_owner_pubkey_hex=_test_only_trusted_owner_pubkey_hex,
        _synthetic_fixture_mode=_synthetic_fixture_mode,
    )
    if (
        type(expectations.expected_sanitized_view_v_sha256) is not str
        or _HEX64_RE.fullmatch(expectations.expected_sanitized_view_v_sha256) is None
    ):
        raise ValueError(
            "STUB-03_MISSING_PINNED_V_SHA256: expectations.expected_sanitized_view_v_sha256 "
            "must be a valid 64-hex SHA-256 digest."
        )

    _, _, docs = _load_bundle_and_corpus(corpus_bundle_manifest_path)

    branch_hashes: Dict[str, str] = {}
    sanitized_master: Dict[str, SanitizationResult] = {}
    for branch in ("C0-BM25", "C0-Dense", "C1-BM25", "C1-Dense"):
        branch_sanitized = {
            doc.document_id: sanitize_canonical_to_view(doc.canonical_text_S)
            for doc in docs
        }
        if branch == "C0-BM25":
            sanitized_master = branch_sanitized
        branch_hashes[branch] = compute_canonical_view_v_sha256(docs, branch_sanitized)

    unique_hashes = set(branch_hashes.values())
    if len(unique_hashes) != 1:
        raise ValueError(f"STUB-03 4-branch sanitizer repeatability divergence: {branch_hashes}")

    computed_v_sha256 = next(iter(unique_hashes))
    if computed_v_sha256 != expectations.expected_sanitized_view_v_sha256:
        raise ValueError(
            "STUB-03_PINNED_V_SHA256_MISMATCH: computed sanitized view V SHA-256 "
            f"({computed_v_sha256!r}) != pinned expected_sanitized_view_v_sha256 "
            f"({expectations.expected_sanitized_view_v_sha256!r})."
        )

    total_removed_tags = 0
    total_removed_chars = 0
    docs_with_tags = 0
    observed_families: set[str] = set()
    boundary_roundtrips = 0
    straddle_roundtrips = 0

    for doc in docs:
        res = sanitized_master[doc.document_id]
        if "[CORROBORATED" in res.view_V:
            raise ValueError(f"Unstripped R_AUDIT marker remained in {doc.document_id}")
        if res.removed_intervals:
            docs_with_tags += 1
        observed_families.update(res.families)
        deleted_codepoints: set[int] = set()
        for r_start, r_end in res.removed_intervals:
            total_removed_tags += 1
            total_removed_chars += r_end - r_start
            deleted_codepoints.update(range(r_start, r_end))

        v_len = len(res.view_V)
        cut_offsets_v: List[int] = []
        shift = 0
        for r_start, r_end in res.removed_intervals:
            v_cut = r_start - shift
            cut_offsets_v.append(v_cut)
            shift += r_end - r_start
            for width in (5, 15, 35) if expectations.profile_name == "LIVE_FROZEN_137_ARM_P_CORPUS" else (12,):
                v_left = max(0, v_cut - width)
                v_right = min(v_len, v_cut + width)
                if v_left < v_cut < v_right:
                    proj = project_v_span_to_s(v_left, v_right, res.segments)
                    reconstructed = "".join(doc.canonical_text_S[a:b] for a, b in proj)
                    if reconstructed != res.view_V[v_left:v_right]:
                        raise ValueError(f"Pi_{{V->S}} round-trip mismatch in {doc.document_id}")
                    for a, b in proj:
                        if any(cp in deleted_codepoints for cp in range(a, b)):
                            raise ValueError(
                                f"Projected span overlapped deleted R_AUDIT tag in {doc.document_id}"
                            )
                    boundary_roundtrips += 1

        if len(cut_offsets_v) >= 2:
            v_first = max(0, cut_offsets_v[0] - 10)
            v_last = min(v_len, cut_offsets_v[-1] + 10)
            if v_first < v_last:
                proj_multi = project_v_span_to_s(v_first, v_last, res.segments)
                if len(proj_multi) < 2:
                    raise ValueError(
                        f"Expected multi-interval projection across multiple tags in {doc.document_id}"
                    )
                reconstructed_m = "".join(doc.canonical_text_S[a:b] for a, b in proj_multi)
                if reconstructed_m != res.view_V[v_first:v_last]:
                    raise ValueError(
                        f"Multi-tag straddle round-trip mismatch in {doc.document_id}"
                    )
                straddle_roundtrips += 1

    if total_removed_tags != expectations.expected_r_audit_tags_removed:
        raise ValueError(
            f"STUB-03 removed tag count mismatch: expected {expectations.expected_r_audit_tags_removed}, got {total_removed_tags}"
        )
    if total_removed_chars != expectations.expected_removed_r_audit_chars:
        raise ValueError(
            f"STUB-03 removed char count mismatch: expected {expectations.expected_removed_r_audit_chars}, got {total_removed_chars}"
        )
    if docs_with_tags != expectations.expected_r_audit_docs_with_tags:
        raise ValueError(
            f"STUB-03 docs_with_tags mismatch: expected {expectations.expected_r_audit_docs_with_tags}, got {docs_with_tags}"
        )
    if frozenset(observed_families) != expectations.expected_r_audit_families:
        raise ValueError(
            f"STUB-03 observed families mismatch: expected {sorted(expectations.expected_r_audit_families)}, got {sorted(observed_families)}"
        )

    return {
        "stub_id": "STUB-03",
        "target_fx_id": "FX-03-AUDIT-TAG-MULTI-SPAN",
        "status": "PASS",
        "profile_name": expectations.profile_name,
        "gate": gate,
        "r_audit_tags_removed": total_removed_tags,
        "r_audit_tags_remaining": EXPECTED_R_AUDIT_REMAINING,
        "removed_r_audit_chars": total_removed_chars,
        "docs_with_tags": docs_with_tags,
        "observed_families": sorted(observed_families),
        "computed_view_v_sha256": computed_v_sha256,
        "pinned_expected_view_v_sha256": expectations.expected_sanitized_view_v_sha256,
        "pinned_v_sha256_verified": True,
        "four_branch_sanitizer_repeatability_hashes": branch_hashes,
        "four_branch_check_scope": FOUR_BRANCH_SANITIZER_CHECK_SCOPE,
        "boundary_roundtrips_verified": boundary_roundtrips,
        "multi_tag_straddle_roundtrips_verified": straddle_roundtrips,
    }


def execute_stub04_fx04_c1_token_ceiling(
    *,
    annex_v0_2_2_path: Path,
    tech_freeze_receipt_path: Path,
    stub_auth_receipt_path: Path,
    corpus_bundle_manifest_path: Path,
    snapshot_dir: Optional[Path] = None,
    expectations: CorpusPreflightExpectations = LIVE_137_CORPUS_EXPECTATIONS,
    auth_mode: StubPreflightAuthMode = "ED25519_SIGNED_V1",
    chat_auth_waiver_path: Optional[Path] = None,
    original_exec_decision_path: Optional[Path] = None,
    _test_only_trusted_owner_pubkey_hex: Optional[str] = None,
    _synthetic_fixture_mode: bool = False,
) -> Dict[str, Any]:
    """STUB-04 (`FX-04-C1-TOKEN-CEILING`): Verify 100% of C1 chunks satisfy <=128 MiniLM tokens and 0 coverage loss."""
    gate = validate_stub01_05_readonly_preflight_gate(
        requested_stub_id="STUB-04",
        annex_v0_2_2_path=annex_v0_2_2_path,
        tech_freeze_receipt_path=tech_freeze_receipt_path,
        stub_auth_receipt_path=stub_auth_receipt_path,
        corpus_bundle_manifest_path=corpus_bundle_manifest_path,
        auth_mode=auth_mode,
        chat_auth_waiver_path=chat_auth_waiver_path,
        original_exec_decision_path=original_exec_decision_path,
        _test_only_trusted_owner_pubkey_hex=_test_only_trusted_owner_pubkey_hex,
        _synthetic_fixture_mode=_synthetic_fixture_mode,
    )
    _, _, docs = _load_bundle_and_corpus(corpus_bundle_manifest_path)
    resolved_snap = resolve_snapshot_dir(snapshot_dir)
    tok_json_path = resolved_snap / "tokenizer.json"
    actual_tok_sha = _sha256_file(tok_json_path)
    if actual_tok_sha != PINNED_TOKENIZER_SHA256:
        raise ValueError(
            f"STUB-04 tokenizer.json SHA-256 mismatch: expected {PINNED_TOKENIZER_SHA256}, got {actual_tok_sha}"
        )
    tokenizer = load_minilm_tokenizer(resolved_snap, verify_sha256=True)

    sanitized_by_doc = {
        doc.document_id: sanitize_canonical_to_view(doc.canonical_text_S)
        for doc in docs
    }
    c1_chunks, c1_audit = chunk_corpus_c1(docs, sanitized_by_doc, tokenizer)

    if (
        expectations.expected_c1_chunk_count is not None
        and len(c1_chunks) != expectations.expected_c1_chunk_count
    ):
        raise ValueError(
            f"STUB-04 C1 chunk count mismatch: expected {expectations.expected_c1_chunk_count}, got {len(c1_chunks)}"
        )

    max_tokens = 0
    min_tokens = 128
    violations = 0
    by_source_type: Dict[str, int] = {}
    for ch in c1_chunks:
        by_source_type[ch.source_type] = by_source_type.get(ch.source_type, 0) + 1
        enc = tokenizer.encode(ch.assembled_text, add_special_tokens=True)
        tok_len = len(enc.ids)
        if tok_len != ch.token_count_with_special:
            raise ValueError(
                f"STUB-04 token count mismatch on {ch.chunk_id}: {tok_len} != {ch.token_count_with_special}"
            )
        if tok_len > max_tokens:
            max_tokens = tok_len
        if tok_len < min_tokens:
            min_tokens = tok_len
        if tok_len > expectations.expected_c1_max_token_ceiling:
            violations += 1
        if ch.c_vis_s_spans_dense != ch.c_vis_s_spans_bm25:
            violations += 1

    coverage_lost_chars = int(c1_audit["coverage_lost_due_to_chunking"])
    if violations != 0 or coverage_lost_chars != 0:
        raise ValueError(
            f"STUB-04 C1 ceiling/coverage violation: violations={violations}, coverage_lost={coverage_lost_chars}"
        )

    return {
        "stub_id": "STUB-04",
        "target_fx_id": "FX-04-C1-TOKEN-CEILING",
        "status": "PASS",
        "profile_name": expectations.profile_name,
        "gate": gate,
        "pinned_snapshot_id": PINNED_SNAPSHOT_ID,
        "verified_tokenizer_json_sha256": actual_tok_sha,
        "c1_chunk_count": len(c1_chunks),
        "c1_chunks_by_source_type": by_source_type,
        "min_token_count_with_special": min_tokens,
        "max_token_count_with_special": max_tokens,
        "ceiling_violations_gt_128": violations,
        "coverage_lost_due_to_chunking": coverage_lost_chars,
    }


def execute_stub05_fx05_overture_visibility(
    *,
    annex_v0_2_2_path: Path,
    tech_freeze_receipt_path: Path,
    stub_auth_receipt_path: Path,
    corpus_bundle_manifest_path: Path,
    snapshot_dir: Optional[Path] = None,
    expectations: CorpusPreflightExpectations = LIVE_137_CORPUS_EXPECTATIONS,
    auth_mode: StubPreflightAuthMode = "ED25519_SIGNED_V1",
    chat_auth_waiver_path: Optional[Path] = None,
    original_exec_decision_path: Optional[Path] = None,
    _test_only_trusted_owner_pubkey_hex: Optional[str] = None,
    _synthetic_fixture_mode: bool = False,
) -> Dict[str, Any]:
    """STUB-05 (`FX-05-C0-TRUNCATION-AND-MULTI-SPAN-VIS`): Verify C0 >128 truncation, SYNTHETIC_HEADER->empty, and multi-interval C_vis."""
    gate = validate_stub01_05_readonly_preflight_gate(
        requested_stub_id="STUB-05",
        annex_v0_2_2_path=annex_v0_2_2_path,
        tech_freeze_receipt_path=tech_freeze_receipt_path,
        stub_auth_receipt_path=stub_auth_receipt_path,
        corpus_bundle_manifest_path=corpus_bundle_manifest_path,
        auth_mode=auth_mode,
        chat_auth_waiver_path=chat_auth_waiver_path,
        original_exec_decision_path=original_exec_decision_path,
        _test_only_trusted_owner_pubkey_hex=_test_only_trusted_owner_pubkey_hex,
        _synthetic_fixture_mode=_synthetic_fixture_mode,
    )
    _, _, docs = _load_bundle_and_corpus(corpus_bundle_manifest_path)
    resolved_snap = resolve_snapshot_dir(snapshot_dir)
    tokenizer = load_minilm_tokenizer(resolved_snap, verify_sha256=True)

    target_docs = [
        d for d in docs if d.document_id == expectations.overture_target_doc_id
    ]
    if len(target_docs) != 1:
        raise ValueError(
            f"STUB-05 target Overture document {expectations.overture_target_doc_id!r} not found in corpus"
        )
    raw_target_doc = target_docs[0]
    raw_sanitized = sanitize_canonical_to_view(raw_target_doc.canonical_text_S)
    if not raw_sanitized.removed_intervals:
        raise ValueError("STUB-05 target document must contain at least one R_AUDIT tag")

    c0_chunks, _ = chunk_corpus_c0(
        [raw_target_doc], {raw_target_doc.document_id: raw_sanitized}, tokenizer
    )
    trunc_chunks = [c for c in c0_chunks if c.token_count_with_special > 128]
    if trunc_chunks:
        target_doc = raw_target_doc
        sanitized = raw_sanitized
    else:
        # Per Annex v0.2.2 §8 FX-05 and verify_v0_2_1_real_corpus_g15_r01.py (L596),
        # extend real Overture doc `w07-b1b-doc-overture-f0d424bd-e55bab3c` in memory
        # past 128 tokens without mutating the source document or disk.
        extended_s = (
            raw_target_doc.canonical_text_S
            + "\n"
            + (
                "Thông tin bổ sung lịch sử trưng bày dân tộc học Việt Nam tại Hà Nội. "
                * 25
            )
            + "Mã lưu trữ đặc biệt cuối trang: ARCHIVE-TAIL-9981."
        )
        target_doc = replace(raw_target_doc, canonical_text_S=extended_s)
        sanitized = sanitize_canonical_to_view(target_doc.canonical_text_S)
        c0_chunks, _ = chunk_corpus_c0(
            [target_doc], {target_doc.document_id: sanitized}, tokenizer
        )
        trunc_chunks = [c for c in c0_chunks if c.token_count_with_special > 128]
        if not trunc_chunks:
            raise ValueError(
                f"STUB-05 expected at least one C0 chunk >128 MiniLM tokens on {target_doc.document_id}"
            )
    ch = trunc_chunks[0]

    synthetic_segs = [
        seg for seg in ch.assembled_segments if seg.get("kind") == "SYNTHETIC_HEADER"
    ]
    if not synthetic_segs:
        raise ValueError("STUB-05 expected SYNTHETIC_HEADER segment in C0 chunk")
    for seg in synthetic_segs:
        if "s_start" in seg or "s_end" in seg or "v_start" in seg or "v_end" in seg:
            raise ValueError(
                "SYNTHETIC_HEADER segment must map to empty canonical offsets"
            )

    c_full_tuples = [(int(a), int(b)) for a, b in ch.c_full_s_spans]
    c_vis_tuples = [(int(a), int(b)) for a, b in ch.c_vis_s_spans_dense]

    deleted_tag_offsets = {
        cp
        for r_start, r_end in sanitized.removed_intervals
        for cp in range(r_start, r_end)
    }
    vis_offsets = {cp for a, b in c_vis_tuples for cp in range(a, b)}
    full_offsets = {cp for a, b in c_full_tuples for cp in range(a, b)}
    if not vis_offsets.issubset(full_offsets):
        raise ValueError("STUB-05 C_vis(c) must be a subset of C_full(c)")
    if vis_offsets & deleted_tag_offsets:
        raise ValueError(
            "STUB-05 C_vis(c) must contain 0 deleted R_AUDIT tag code points"
        )

    tail_only_offsets = sorted(full_offsets - vis_offsets)
    if not tail_only_offsets:
        raise ValueError(
            "STUB-05 expected non-empty truncated tail offsets in C_full(c) \\ C_vis(c)"
        )
    tail_span = [(tail_only_offsets[0], tail_only_offsets[0] + 1)]
    tail_ev_hit = intervals_contain(c_full_tuples, tail_span)
    tail_vis_hit = intervals_contain(c_vis_tuples, tail_span)
    if not (tail_ev_hit is True and tail_vis_hit is False):
        raise ValueError(
            f"STUB-05 tail truncation check failed: ev_hit={tail_ev_hit}, vis_hit={tail_vis_hit}"
        )

    max_vis_cp = max(vis_offsets)
    straddle_cutoff_span = [(max_vis_cp, tail_only_offsets[0] + 1)]
    cutoff_ev_hit = intervals_contain(c_full_tuples, straddle_cutoff_span)
    cutoff_vis_hit = intervals_contain(c_vis_tuples, straddle_cutoff_span)
    if not (cutoff_ev_hit is True and cutoff_vis_hit is False):
        raise ValueError(
            f"STUB-05 token 128/129 cutoff straddle check failed: ev_hit={cutoff_ev_hit}, vis_hit={cutoff_vis_hit}"
        )

    first_r_start, _ = sanitized.removed_intervals[0]
    v_cut = first_r_start
    blind_left = max(0, v_cut - 8)
    blind_right = min(len(sanitized.view_V), v_cut + 8)
    blind_g_sub = project_v_span_to_s(blind_left, blind_right, sanitized.segments)
    # Detect purely from V whether [blind_left, blind_right) crosses an inter-sentence
    # C0 separator normalized to SYNTHETIC_HEADER -> empty (C0 only preserves literal " ").
    blind_crossed_newline = any(
        sm.start() >= blind_left
        and sm.end() <= blind_right
        and sanitized.view_V[sm.start() : sm.end()] != " "
        and ("\n" in sanitized.view_V[sm.start() : sm.end()] or "\r" in sanitized.view_V[sm.start() : sm.end()])
        for sm in C0Chunker.SENTENCE_SPLIT_PATTERN.finditer(sanitized.view_V)
    )

    # Negative fixture check: if the fixed v_cut +/- 8 window crosses an inter-sentence
    # newline stripped by C0Chunker (normalized to a SYNTHETIC_HEADER separator -> empty),
    # BOTH C_full and C_vis MUST reject containment (never coerce `\n` into canonical provenance).
    newline_neg_ev_hit: Optional[bool] = None
    newline_neg_vis_hit: Optional[bool] = None
    if blind_crossed_newline:
        newline_neg_ev_hit = intervals_contain(c_full_tuples, blind_g_sub)
        newline_neg_vis_hit = intervals_contain(c_vis_tuples, blind_g_sub)
        if not (newline_neg_ev_hit is False and newline_neg_vis_hit is False):
            raise ValueError(
                "STUB-05 newline-normalized C0 negative straddle check failed "
                "(normalized separator leaked into canonical spans): "
                f"ev_hit={newline_neg_ev_hit}, vis_hit={newline_neg_vis_hit}"
            )

    # Pre-registered bounded positive boundary fixture derived solely from V (never C_full/C_vis):
    # clamp v_cut +/- 8 strictly inside the same non-newline line segment around R_1 to verify
    # marker-adjacency & Pi_{V->S} projection fidelity without crossing normalized sentence breaks.
    left_slice = sanitized.view_V[blind_left:v_cut]
    pre_nl = max(left_slice.rfind("\n"), left_slice.rfind("\r"))
    v_left = blind_left + pre_nl + 1 if pre_nl != -1 else blind_left

    right_slice = sanitized.view_V[v_cut:blind_right]
    post_nl_stops = [
        pos for pos in (right_slice.find("\n"), right_slice.find("\r")) if pos != -1
    ]
    v_right = v_cut + min(post_nl_stops) if post_nl_stops else blind_right

    if not (v_left < v_cut < v_right):
        raise ValueError(
            "STUB-05 clamped marker-adjacency boundary window collapsed before newline: "
            f"v_left={v_left}, v_cut={v_cut}, v_right={v_right}"
        )

    early_g_sub = project_v_span_to_s(v_left, v_right, sanitized.segments)
    if len(early_g_sub) < 2:
        raise ValueError(
            "STUB-05 expected multi-interval canonical span across deleted R_AUDIT tag"
        )
    early_ev_hit = intervals_contain(c_full_tuples, early_g_sub)
    early_vis_hit = intervals_contain(c_vis_tuples, early_g_sub)
    if not (early_ev_hit is True and early_vis_hit is True):
        raise ValueError(
            f"STUB-05 early multi-interval R_AUDIT straddle failed: ev_hit={early_ev_hit}, vis_hit={early_vis_hit}"
        )

    return {
        "stub_id": "STUB-05",
        "target_fx_id": "FX-05-C0-TRUNCATION-AND-MULTI-SPAN-VIS",
        "status": "PASS",
        "profile_name": expectations.profile_name,
        "gate": gate,
        "target_document_id": target_doc.document_id,
        "raw_target_doc_removed_tags": len(raw_sanitized.removed_intervals),
        "c0_chunk_token_count": ch.token_count_with_special,
        "tail_span_evidence_hit": tail_ev_hit,
        "tail_span_visible_hit": tail_vis_hit,
        "cutoff_straddle_evidence_hit": cutoff_ev_hit,
        "cutoff_straddle_visible_hit": cutoff_vis_hit,
        "early_r_audit_straddle_scope": (
            "MARKER_ADJACENCY_AND_PROJECTION_FIDELITY_NOT_SUBSTANTIVE_LEXICAL_EVIDENCE"
        ),
        "early_r_audit_positive_window_v": [v_left, v_right],
        "early_r_audit_positive_g_sub_s": [[a, b] for a, b in early_g_sub],
        "early_r_audit_straddle_intervals": len(early_g_sub),
        "early_r_audit_straddle_visible_hit": early_vis_hit,
        "early_r_audit_straddle_blind_crossed_newline": blind_crossed_newline,
        "early_r_audit_newline_negative_window_v": [blind_left, blind_right],
        "early_r_audit_newline_negative_evidence_hit": newline_neg_ev_hit,
        "early_r_audit_newline_negative_visible_hit": newline_neg_vis_hit,
        "deleted_tag_chars_in_c_vis": len(vis_offsets & deleted_tag_offsets),
    }
