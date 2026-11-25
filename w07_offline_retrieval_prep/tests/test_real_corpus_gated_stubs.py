"""Gated real-corpus test stubs (STUB-01..STUB-06) kept in HOLD + synthetic dry-run & F-01/F-02 binding tests.

CRITICAL GOVERNANCE GUARDRAIL:
1. This module performs ZERO reads of the real 137-document corpus.
2. Plain environment variables (W07_G15_FROZEN="1", W07_OWNER_AUTHORIZED="1",
   W07_STUB_01_05_AUTHORIZED="1") CANNOT unlock these stubs or simulate Owner authority.
3. STUB-01..STUB-05 are genuinely implemented in `w07_retrieval.real_corpus_preflight`
   and exercised here against synthetic dry-run fixtures only; live 137-doc execution
   remains strictly in HOLD (`PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX is None`) until a
   separate Owner execution authorization receipt is issued.
4. STUB-06 (formal G3/G4 benchmark scorer) remains strictly in HOLD awaiting OD-G15-05
   resolution, PRE_G3_QUERY_LOCK, and formal G3 execution authority.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from conftest import (
    PINNED_TOKENIZER_SHA256,
    REAL_CORPUS_STUB01_05_GATE_REASON,
    is_real_corpus_authorized,
    is_real_corpus_stub01_05_authorized,
)
from w07_retrieval.chunker_c0 import C0Chunker
from w07_retrieval.chunker_c1 import chunk_corpus_c1
from w07_retrieval.real_corpus_preflight import (
    APPROVED_ANNEX_V0_2_2_BYTES,
    APPROVED_ANNEX_V0_2_2_SHA256,
    APPROVED_TECH_FREEZE_DECISION_SHA256,
    APPROVED_TECH_FREEZE_RECEIPT_SHA256,
    ED25519_STUB01_05_PREFLIGHT_DOMAIN_ASCII,
    FOUR_BRANCH_SANITIZER_CHECK_SCOPE,
    LIVE_137_CORPUS_EXPECTATIONS,
    PARENT_ANNEX_V0_2_1_SHA256,
    PINNED_LIVE_137_CORPUS_7_ARTIFACTS,
    PINNED_LIVE_137_SANITIZED_VIEW_V_SHA256,
    PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX,
    PROTOCOL_V1_0_LF_SHA256,
    STUB01_05_AUTH_RECEIPT_SCHEMA_V1,
    STUB01_05_AUTHORIZED_SCOPE,
    STUB01_05_CORPUS_BUNDLE_SCHEMA_V1,
    CorpusPreflightExpectations,
    PinnedArtifactSpec,
    canonical_stub01_05_auth_signing_bytes,
    compute_canonical_view_v_sha256,
    compute_git_blob_sha1,
    execute_stub01_fx01_hash_and_arm_p_counts,
    execute_stub02_fx02_canonical_conservation,
    execute_stub03_fx03_audit_tags_and_v_hash,
    execute_stub04_fx04_c1_token_ceiling,
    execute_stub05_fx05_overture_visibility,
    validate_stub01_05_readonly_preflight_gate,
    verify_archived_v0_2_2_tech_freeze_baseline,
)
from w07_retrieval.runner import (
    ED25519_FORMAL_EXECUTION_DOMAIN_ASCII,
    EXPECTED_CITY_COUNTS,
    EXPECTED_ELIGIBLE_DOC_COUNT,
    EXPECTED_R_AUDIT_REMAINING,
    EXPECTED_R_AUDIT_REMOVED,
    EXPECTED_SANITIZED_VIEW_V_137_SHA256,
    FROZEN_CORPUS_RECEIPT_SCHEMA_V1,
    OWNER_AUTH_RECEIPT_SCHEMA_V1,
    PINNED_LIVE_OWNER_G3_PUBKEY_HEX,
    canonical_owner_auth_signing_bytes,
    run_benchmark,
    validate_formal_execution_gate,
    validate_synthetic_prep_boundaries,
)
from w07_retrieval.sanitizer import (
    KNOWN_FAMILIES,
    intervals_contain,
    sanitize_canonical_to_view,
)
from w07_retrieval.schema import load_corpus_jsonl
from w07_retrieval.visibility import load_minilm_tokenizer, resolve_snapshot_dir

PREP_ROOT = Path(__file__).resolve().parents[1]
ARCHIVED_V022_DIR = PREP_ROOT / "authorities_v0_2_2_tech_freeze"
ARCHIVED_ANNEX_V022_PATH = (
    ARCHIVED_V022_DIR / "GOMATE_W07_G15_TECHNICAL_ANNEX_V0_2_2_CANDIDATE_2026-11-21.md"
)
ARCHIVED_DECISION_V022_PATH = (
    ARCHIVED_V022_DIR / "GOMATE_W07_G15_TECH_FREEZE_OWNER_DECISION_2026-11-21.md"
)
ARCHIVED_RECEIPT_V022_PATH = (
    ARCHIVED_V022_DIR / "GOMATE_W07_G15_TECH_FREEZE_OWNER_APPROVAL_RECEIPT_2026-11-21.json"
)
ARCHIVED_CHAT_WAIVER_V1_PATH = (
    ARCHIVED_V022_DIR / "GOMATE_W07_STUB01_05_OWNER_CHAT_AUTH_WAIVER_V1_0_2026-11-21.md"
)
ARCHIVED_CHAT_POLICY_RECEIPT_V1_PATH = (
    ARCHIVED_V022_DIR / "GOMATE_W07_STUB01_05_OWNER_CHAT_AUTH_POLICY_RECEIPT_V1_2026-11-21.json"
)

REAL_CORPUS_STUB_ACTIVATION_CRITERIA_V1: Dict[str, Dict[str, Any]] = {
    "STUB-01": {
        "test_function": "tests/test_real_corpus_gated_stubs.py::test_gated_real_corpus_fx01_hash_and_arm_p_counts",
        "implementation_entry": "w07_retrieval.real_corpus_preflight::execute_stub01_fx01_hash_and_arm_p_counts",
        "target_fx_id": "FX-01-CORPUS-HASH",
        "current_status": "HOLD",
        "unlock_prerequisites": [
            "Archived Owner-approved Annex v0.2.2 (e78013fd...) + tech-freeze receipt (1db438d3...)",
            "PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX provisioned in w07_retrieval.real_corpus_preflight",
            "Separate Ed25519-signed W07_G15_STUB01_05_READONLY_CORPUS_AUTH_RECEIPT_V1",
            "Hash-verified W07_G15_STUB01_05_CORPUS_BUNDLE_MANIFEST_V1 bound to PINNED_LIVE_137_CORPUS_7_ARTIFACTS",
        ],
        "pass_assertions_when_unlocked": [
            "Bundle manifest AND on-disk files match all 7 pinned scientific authority entries (exact artifact_id, canonical_repo_path, filename, byte size, SHA-256, and Git blob SHA-1 from Annex v0.2.2 §0.1 / G15-R01; fail-closed on missing, extra, or hash-mismatched artifacts)",
            "137 eligible Arm P documents (59 Hà Nội, 52 Đà Nẵng, 26 Hạ Long)",
            "0 REFERENCE_ONLY documents admitted into Primary Arm P",
        ],
    },
    "STUB-02": {
        "test_function": "tests/test_real_corpus_gated_stubs.py::test_gated_real_corpus_fx02_canonical_conservation",
        "implementation_entry": "w07_retrieval.real_corpus_preflight::execute_stub02_fx02_canonical_conservation",
        "target_fx_id": "FX-02-CANONICAL-CONSERVATION",
        "current_status": "HOLD",
        "unlock_prerequisites": [
            "STUB-01 prerequisites satisfied for STUB-02",
        ],
        "pass_assertions_when_unlocked": [
            "286,004 preserved body + 8,679 heading/header + 961 omitted whitespace (857 inter-chunk + 104 empty-section/preamble) == 295,644 canonical code points",
            "21 empty parent headings preserved in child section_breadcrumb",
            "24 omitted allowlisted empty leaf footers strictly belong to the 10-item allowlist (+ 14 preserved heading-only leaves = 38 empty non-parent headings; 21 + 24 + 14 = 59)",
        ],
    },
    "STUB-03": {
        "test_function": "tests/test_real_corpus_gated_stubs.py::test_gated_real_corpus_fx03_audit_tags_and_v_hash",
        "implementation_entry": "w07_retrieval.real_corpus_preflight::execute_stub03_fx03_audit_tags_and_v_hash",
        "target_fx_id": "FX-03-AUDIT-TAG-MULTI-SPAN",
        "current_status": "HOLD",
        "unlock_prerequisites": [
            "STUB-01 prerequisites satisfied for STUB-03",
        ],
        "pass_assertions_when_unlocked": [
            "46/46 [CORROBORATED: ...] R_AUDIT tags removed across 23 Overture documents (4,216 code points removed, 291,428 retained, 0 remaining)",
            "23/23 Overture source-confidence lines and 3/3 Wikipedia editorial brackets retained",
            "Computed sanitized view V SHA-256 equals pinned digest 046424e521f967f6c5575da1eeb914e5d340a118861c0cf04ca45256b364533d (and 4-branch sanitizer repeatability check is uniform without claiming four independent production retrieval paths)",
            "Pi_{V->S} UTF-8 & code-point round-trip exact across 138 real boundary cuts and 15 multi-tag straddles",
        ],
    },
    "STUB-04": {
        "test_function": "tests/test_real_corpus_gated_stubs.py::test_gated_real_corpus_fx04_c1_token_ceiling",
        "implementation_entry": "w07_retrieval.real_corpus_preflight::execute_stub04_fx04_c1_token_ceiling",
        "target_fx_id": "FX-04-C1-TOKEN-CEILING",
        "current_status": "HOLD",
        "unlock_prerequisites": [
            "STUB-01 prerequisites satisfied for STUB-04",
            "Pinned MiniLM tokenizer.json SHA-256 == 2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8 verified",
        ],
        "pass_assertions_when_unlocked": [
            "1,002 C1 chunks across 137 Arm P documents (80/74/750/55/43 by source family)",
            "100% of C1 chunks satisfy len(encode(A(c), add_special_tokens=True, truncation=False)) <= 128",
            "0 truncated C1 chunks and coverage_lost_due_to_chunking == 0",
        ],
    },
    "STUB-05": {
        "test_function": "tests/test_real_corpus_gated_stubs.py::test_gated_real_corpus_fx05_overture_visibility",
        "implementation_entry": "w07_retrieval.real_corpus_preflight::execute_stub05_fx05_overture_visibility",
        "target_fx_id": "FX-05-C0-TRUNCATION-AND-MULTI-SPAN-VIS",
        "current_status": "HOLD",
        "unlock_prerequisites": [
            "STUB-01 and STUB-04 prerequisites satisfied for STUB-05",
        ],
        "pass_assertions_when_unlocked": [
            "On w07-b1b-doc-overture-f0d424bd-e55bab3c (>128 tokens), truncated tail fact yields EvidenceSpanHit@10 == 1 and VisibleEvidenceSpanHit@10 == 0 even if echoed in SYNTHETIC_HEADER",
            "Span straddling token 128/129 cutoff yields VisibleEvidenceSpanHit@10 == 0",
            "Early span straddling deleted 4-family R_AUDIT tag yields VisibleEvidenceSpanHit@10 == 1 via G_sub subseteq C_vis(c) with 0 deleted tag chars in C_vis(c)",
        ],
    },
    "STUB-06": {
        "test_function": "tests/test_fx12_to_fx16_g4_scorer.py::test_gated_real_137_corpus_g4_scorer_stub",
        "implementation_entry": "w07_g4_scorer.scorer::run_g4_scorer",
        "target_fx_id": "FX-12..FX-16-REAL-CORPUS-G4-SCORER",
        "current_status": "HOLD",
        "unlock_prerequisites": [
            "OD-G15-05 resolved (human 2+1 roster OR Supervisor-confirmed signed AI-proxy amendment)",
            "STUB-01..STUB-05 prerequisites satisfied",
            "PRE_G3_QUERY_LOCK sealed on 50 FINAL queries (5x3 matrix: 40 Q_ans + 10 Q_unans)",
            "One-shot G3 sealed rankings g3_sealed_rankings_v1.jsonl + formal G3 authority manifest",
            "Sealed G2B relevance judgments / qrels verified under Cert-1..4 or ORDER_A/ORDER_B",
        ],
        "pass_assertions_when_unlocked": [
            "Zero-retriever/zero-ML-import G4 execution verified via sys.modules & AST checks",
            "Coupled [nDCG_L@10, nDCG_U@10], EvidenceSpanHit@10, VisibleEvidenceSpanHit@10, FalseSupportExposure@10 computed over fixed pre-rank denominators",
            "PCG64(20261105) B=10,000 Monte Carlo sign-flip + paired bootstrap + Holm-Bonferroni K1..K5 contrasts evaluated with NO_CLEAR_WINNER / NO_CLEAR_PROXY_WINNER enforcement",
        ],
    },
}


def _sign_stub_auth_receipt(
    priv: Ed25519PrivateKey,
    base_receipt: Dict[str, Any],
    bundle_manifest_path: Path,
) -> Path:
    rec = dict(base_receipt)
    rec["corpus_bundle_manifest_sha256"] = hashlib.sha256(
        bundle_manifest_path.read_bytes()
    ).hexdigest()
    rec["owner_detached_signature_hex"] = priv.sign(
        canonical_stub01_05_auth_signing_bytes(rec)
    ).hex()
    out_p = bundle_manifest_path.parent / f"signed_{bundle_manifest_path.stem}_auth.json"
    out_p.write_text(
        json.dumps(rec, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_p


def _build_synthetic_dry_run_bundle_and_receipts(
    tmp_path: Path,
) -> Tuple[Path, Path, str, CorpusPreflightExpectations]:
    """Create a synthetic 7-artifact corpus bundle and Ed25519-signed dry-run STUB-01..05 receipt."""
    bundle_dir = tmp_path / "synthetic_stub01_05_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    repeated_clause = (
        "Văn Miếu Quốc Tử Giám tại Hà Nội lưu giữ bia tiến sĩ đá cổ và kiến trúc truyền thống Việt Nam. "
    )
    tag_1 = (
        "[CORROBORATED: canonical_poi:00000000-0000-0000-0000-000000000001, "
        "osm:node/101, wikidata:Q101, wikipedia:vi:Van_Mieu]"
    )
    overture_body_1 = (
        f"Quần thể di tích lịch sử tại trung tâm thủ đô {tag_1} "
        + (repeated_clause * 14)
        + "Điểm thông tin cuối đoạn bị cắt sau ngưỡng một trăm hai mươi tám token."
    )
    doc1_s = (
        "## Lịch sử\n"
        "### Bia tiến sĩ\n"
        f"{overture_body_1}\n"
        "## Tham khảo\n"
    )

    tag_2 = (
        "[CORROBORATED: wikivoyage:en:Da_Nang#See, "
        "osm_website_pointer:https://danang.gov.vn]"
    )
    doc2_s = (
        "## Kiến trúc\n"
        f"Cầu Rồng bắc qua sông Hàn phun lửa cuối tuần {tag_2} "
        "và kết nối trục đường biển Mỹ Khê [Nguồn biên tập viên].\n"
        "Nguồn dữ liệu: Overture Maps (confidence=0.95).\n"
        "## Liên kết ngoài\n"
    )

    doc3_s = (
        "POI: Vịnh Hạ Long | Thành phố: Hạ Long | Nhóm: danh thắng tự nhiên\n"
        "Vịnh Hạ Long có hàng nghìn đảo đá vôi và hang Sửng Sốt trên vùng vịnh biển Quảng Ninh."
    )

    docs_raw = [
        {
            "document_id": "syn-preflight-overture-hn-01",
            "title": "Văn Miếu Quốc Tử Giám",
            "source_type": "b1b",
            "city": "Hà Nội",
            "canonical_text_S": doc1_s,
            "metadata": {"city": "Hà Nội", "arm_disposition": "PRIMARY_ARM_P"},
        },
        {
            "document_id": "syn-preflight-overture-dn-02",
            "title": "Cầu Rồng Đà Nẵng",
            "source_type": "b1b",
            "city": "Đà Nẵng",
            "canonical_text_S": doc2_s,
            "metadata": {"city": "Đà Nẵng", "arm_disposition": "PRIMARY_ARM_P"},
        },
        {
            "document_id": "syn-preflight-osm-hl-03",
            "title": "Vịnh Hạ Long",
            "source_type": "osm_useful_structured",
            "city": "Hạ Long",
            "canonical_text_S": doc3_s,
            "metadata": {"city": "Hạ Long", "arm_disposition": "PRIMARY_ARM_P"},
        },
    ]

    corpus_jsonl_path = bundle_dir / "synthetic_arm_p_corpus.jsonl"
    corpus_jsonl_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in docs_raw) + "\n",
        encoding="utf-8",
    )

    aux_specs: List[Tuple[str, str, Path]] = [
        (
            "syn_artifact_01_primary_corpus",
            "data/curated/w07/synthetic_arm_p_corpus.jsonl",
            corpus_jsonl_path,
        )
    ]
    for idx in range(2, 8):
        p = bundle_dir / f"synthetic_bundle_aux_{idx:02d}.json"
        p.write_text(
            json.dumps({"synthetic_artifact_index": idx, "status": "dry_run_only"}, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        aux_specs.append(
            (
                f"syn_artifact_{idx:02d}",
                f"data/evaluation/w07/{p.name}",
                p,
            )
        )

    artifacts_manifest = []
    pinned_specs_list: List[PinnedArtifactSpec] = []
    for art_id, canon_repo_path, fpath in aux_specs:
        raw_b = fpath.read_bytes()
        sha256_hex = hashlib.sha256(raw_b).hexdigest()
        git_sha1_hex = compute_git_blob_sha1(raw_b)
        artifacts_manifest.append(
            {
                "artifact_id": art_id,
                "canonical_repo_path": canon_repo_path,
                "relative_path": fpath.name,
                "size_bytes": len(raw_b),
                "sha256": sha256_hex,
                "git_blob_sha1": git_sha1_hex,
            }
        )
        pinned_specs_list.append(
            PinnedArtifactSpec(
                artifact_id=art_id,
                canonical_repo_path=canon_repo_path,
                filename=fpath.name,
                size_bytes=len(raw_b),
                sha256=sha256_hex,
                git_blob_sha1=git_sha1_hex,
            )
        )

    bundle_manifest_obj = {
        "schema_version": STUB01_05_CORPUS_BUNDLE_SCHEMA_V1,
        "primary_corpus_jsonl": corpus_jsonl_path.name,
        "artifacts": artifacts_manifest,
    }
    bundle_manifest_path = bundle_dir / "synthetic_corpus_bundle_manifest.json"
    bundle_manifest_path.write_text(
        json.dumps(bundle_manifest_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    bundle_sha = hashlib.sha256(bundle_manifest_path.read_bytes()).hexdigest()

    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("22" * 32))
    pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    stub_auth_obj: Dict[str, Any] = {
        "schema_version": STUB01_05_AUTH_RECEIPT_SCHEMA_V1,
        "approved_annex_v0_2_2_sha256": APPROVED_ANNEX_V0_2_2_SHA256,
        "tech_freeze_owner_receipt_sha256": APPROVED_TECH_FREEZE_RECEIPT_SHA256,
        "parent_annex_v0_2_1_sha256": PARENT_ANNEX_V0_2_1_SHA256,
        "protocol_v1_0_lf_sha256": PROTOCOL_V1_0_LF_SHA256,
        "pinned_tokenizer_json_sha256": PINNED_TOKENIZER_SHA256,
        "authorized_scope": STUB01_05_AUTHORIZED_SCOPE,
        "authorized_stubs": ["STUB-01", "STUB-02", "STUB-03", "STUB-04", "STUB-05"],
        "real_137_corpus_readonly_stubs_authorized": True,
        "stub_06_formal_g3_g4_authorized": False,
        "final50_or_dev_or_live_api_authorized": False,
        "corpus_bundle_manifest_sha256": bundle_sha,
        "ed25519_domain_tag": ED25519_STUB01_05_PREFLIGHT_DOMAIN_ASCII,
        "owner_ed25519_pubkey_hex": pub_hex,
    }
    sig = priv.sign(canonical_stub01_05_auth_signing_bytes(stub_auth_obj)).hex()
    stub_auth_obj["owner_detached_signature_hex"] = sig

    stub_auth_path = bundle_dir / "synthetic_stub01_05_owner_auth_receipt.json"
    stub_auth_path.write_text(
        json.dumps(stub_auth_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    total_s = len(doc1_s) + len(doc2_s) + len(doc3_s)
    removed_c = len(tag_1) + len(tag_2)
    retained_v = total_s - removed_c

    loaded_docs = load_corpus_jsonl(corpus_jsonl_path)
    sanitized_by_doc = {
        d.document_id: sanitize_canonical_to_view(d.canonical_text_S)
        for d in loaded_docs
    }
    expected_syn_v_sha256 = compute_canonical_view_v_sha256(
        loaded_docs, sanitized_by_doc
    )
    tok = load_minilm_tokenizer(resolve_snapshot_dir(None), verify_sha256=True)
    syn_c1_chunks, _ = chunk_corpus_c1(loaded_docs, sanitized_by_doc, tok)

    expectations = CorpusPreflightExpectations(
        profile_name="SYNTHETIC_DRY_RUN_3DOC_6FAMILY_PROFILE",
        expected_artifact_count=7,
        expected_pinned_artifacts=tuple(pinned_specs_list),
        expected_eligible_doc_count=3,
        expected_city_counts={"Hà Nội": 1, "Đà Nẵng": 1, "Hạ Long": 1},
        expected_source_type_counts={"b1b": 2, "osm_useful_structured": 1},
        expected_reference_only_admitted=0,
        expected_total_canonical_s_chars=total_s,
        expected_removed_r_audit_chars=removed_c,
        expected_retained_view_v_chars=retained_v,
        expected_r_audit_tags_removed=2,
        expected_r_audit_docs_with_tags=2,
        expected_r_audit_families=KNOWN_FAMILIES,
        expected_sanitized_view_v_sha256=expected_syn_v_sha256,
        expected_empty_parent_headings_propagated=1,
        expected_allowlisted_footer_drops=2,
        expected_c1_chunk_count=len(syn_c1_chunks),
        expected_c1_max_token_ceiling=128,
        overture_target_doc_id="syn-preflight-overture-hn-01",
    )
    return stub_auth_path, bundle_manifest_path, pub_hex, expectations


def test_archived_v0_2_2_tech_freeze_baseline_and_receipt_separation() -> None:
    """Verify archived Annex v0.2.2 bytes and confirm the chat receipt does not unlock STUB-01..05."""
    assert PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX is None
    assert PINNED_LIVE_OWNER_G3_PUBKEY_HEX is None

    info = verify_archived_v0_2_2_tech_freeze_baseline(
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        tech_freeze_decision_path=ARCHIVED_DECISION_V022_PATH,
    )
    assert info["approved_annex_v0_2_2_bytes"] == APPROVED_ANNEX_V0_2_2_BYTES
    assert info["approved_annex_v0_2_2_sha256"] == APPROVED_ANNEX_V0_2_2_SHA256
    assert info["tech_freeze_receipt_sha256"] == APPROVED_TECH_FREEZE_RECEIPT_SHA256
    assert info["tech_freeze_decision_sha256"] == APPROVED_TECH_FREEZE_DECISION_SHA256
    assert info["parent_annex_v0_2_1_sha256"] == PARENT_ANNEX_V0_2_1_SHA256
    assert info["protocol_v1_0_lf_sha256"] == PROTOCOL_V1_0_LF_SHA256


def test_real_corpus_gate_rejects_plain_env_var_spoofing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Plain environment variables NEVER unlock STUB-01..05, STUB-06, or formal-execution."""
    assert PINNED_LIVE_OWNER_G3_PUBKEY_HEX is None
    assert PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX is None

    for k in ("W07_G15_FROZEN", "W07_OWNER_AUTHORIZED", "W07_STUB_01_05_AUTHORIZED"):
        monkeypatch.delenv(k, raising=False)
    assert is_real_corpus_authorized() is False
    assert is_real_corpus_stub01_05_authorized() is False

    for k in ("W07_G15_FROZEN", "W07_OWNER_AUTHORIZED", "W07_STUB_01_05_AUTHORIZED"):
        monkeypatch.setenv(k, "1")
    assert is_real_corpus_authorized() is False
    assert is_real_corpus_stub01_05_authorized() is False

    with pytest.raises(
        PermissionError,
        match="STUB01_05_BLOCKED_MISSING_RECEIPTS.*Plain environment variables",
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-01",
            annex_v0_2_2_path=None,
            tech_freeze_receipt_path=None,
            stub_auth_receipt_path=None,
            corpus_bundle_manifest_path=None,
        )

    c_path = tmp_path / "synthetic_corpus.jsonl"
    q_path = tmp_path / "synthetic_queries.jsonl"
    c_path.write_text(
        json.dumps({"document_id": "d1", "canonical_text_S": "Hồ Gươm Hà Nội."}) + "\n",
        encoding="utf-8",
    )
    q_path.write_text(
        json.dumps({"query_id": "q1", "query_text": "Hồ Gươm"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        PermissionError,
        match="FORMAL_EXECUTION_BLOCKED_MISSING_RECEIPTS.*environment flags cannot simulate Owner authority",
    ):
        run_benchmark(
            corpus_path=c_path,
            queries_path=q_path,
            output_dir=tmp_path / "out",
            cells=["C1-BM25"],
            execution_mode="formal-execution",
        )


def test_stub01_to_stub05_synthetic_dry_run_acceptance_end_to_end(
    tmp_path: Path,
) -> None:
    """Execute genuine STUB-01..STUB-05 implementations on synthetic dry-run fixtures with signed receipts."""
    stub_auth_p, bundle_p, pub_hex, syn_expectations = (
        _build_synthetic_dry_run_bundle_and_receipts(tmp_path)
    )

    r1 = execute_stub01_fx01_hash_and_arm_p_counts(
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        stub_auth_receipt_path=stub_auth_p,
        corpus_bundle_manifest_path=bundle_p,
        expectations=syn_expectations,
        _test_only_trusted_owner_pubkey_hex=pub_hex,
    )
    assert r1["status"] == "PASS"
    assert r1["verified_artifact_count"] == 7
    assert r1["pinned_authority_cross_check_passed"] is True
    assert r1["eligible_document_count"] == 3
    assert r1["reference_only_admitted"] == 0

    r2 = execute_stub02_fx02_canonical_conservation(
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        stub_auth_receipt_path=stub_auth_p,
        corpus_bundle_manifest_path=bundle_p,
        expectations=syn_expectations,
        _test_only_trusted_owner_pubkey_hex=pub_hex,
    )
    assert r2["status"] == "PASS"
    assert r2["empty_parent_headings_propagated"] == 1
    assert r2["allowlisted_footer_drops"] == 2

    r3 = execute_stub03_fx03_audit_tags_and_v_hash(
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        stub_auth_receipt_path=stub_auth_p,
        corpus_bundle_manifest_path=bundle_p,
        expectations=syn_expectations,
        _test_only_trusted_owner_pubkey_hex=pub_hex,
    )
    assert r3["status"] == "PASS"
    assert r3["r_audit_tags_removed"] == 2
    assert r3["r_audit_tags_remaining"] == 0
    assert r3["pinned_v_sha256_verified"] is True
    assert r3["computed_view_v_sha256"] == syn_expectations.expected_sanitized_view_v_sha256
    assert r3["four_branch_check_scope"] == FOUR_BRANCH_SANITIZER_CHECK_SCOPE
    assert r3["boundary_roundtrips_verified"] == 2

    r4 = execute_stub04_fx04_c1_token_ceiling(
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        stub_auth_receipt_path=stub_auth_p,
        corpus_bundle_manifest_path=bundle_p,
        expectations=syn_expectations,
        _test_only_trusted_owner_pubkey_hex=pub_hex,
    )
    assert r4["status"] == "PASS"
    assert r4["max_token_count_with_special"] <= 128
    assert r4["ceiling_violations_gt_128"] == 0
    assert r4["coverage_lost_due_to_chunking"] == 0

    r5 = execute_stub05_fx05_overture_visibility(
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        stub_auth_receipt_path=stub_auth_p,
        corpus_bundle_manifest_path=bundle_p,
        expectations=syn_expectations,
        _test_only_trusted_owner_pubkey_hex=pub_hex,
    )
    assert r5["status"] == "PASS"
    assert r5["c0_chunk_token_count"] > 128
    assert r5["tail_span_evidence_hit"] is True
    assert r5["tail_span_visible_hit"] is False
    assert r5["cutoff_straddle_evidence_hit"] is True
    assert r5["cutoff_straddle_visible_hit"] is False
    assert r5["early_r_audit_straddle_intervals"] == 2
    assert r5["early_r_audit_straddle_visible_hit"] is True
    assert (
        r5["early_r_audit_straddle_scope"]
        == "MARKER_ADJACENCY_AND_PROJECTION_FIDELITY_NOT_SUBSTANTIVE_LEXICAL_EVIDENCE"
    )
    assert r5["early_r_audit_straddle_blind_crossed_newline"] is False
    assert r5["deleted_tag_chars_in_c_vis"] == 0


def test_stub01_f01_scientific_binding_and_negative_cases(
    tmp_path: Path,
) -> None:
    """F-01: Verify STUB-01 cross-checks manifest and disk files against pinned 7-artifact authority table."""
    # 1. Verify LIVE_137_CORPUS_EXPECTATIONS binds the exact 7 audited frozen artifacts
    assert len(PINNED_LIVE_137_CORPUS_7_ARTIFACTS) == 7
    assert (
        LIVE_137_CORPUS_EXPECTATIONS.expected_pinned_artifacts
        == PINNED_LIVE_137_CORPUS_7_ARTIFACTS
    )
    live_by_id = {s.artifact_id: s for s in PINNED_LIVE_137_CORPUS_7_ARTIFACTS}
    assert set(live_by_id.keys()) == {
        "w07_review_target_60_pois_v1",
        "w07_b1b_source_decisions_v1",
        "w07_b1b_acquisition_summary_v1",
        "poi_knowledge_acquired_v1",
        "w07_b1a_existing_poi_knowledge_audit_v1",
        "w07_b1_fix_01b_reingestion_v1",
        "gomate_places_freeze_v2",
    }
    assert (
        live_by_id["poi_knowledge_acquired_v1"].sha256
        == "9b0ed36e060924057872a2e8fe9941940f7bc3455f2c9cad21cdc9a9c1141fda"
    )
    assert (
        live_by_id["poi_knowledge_acquired_v1"].git_blob_sha1
        == "cbb6da5e498ffd050e345ee97010bcd60a0aeab8"
    )
    assert live_by_id["poi_knowledge_acquired_v1"].size_bytes == 594824

    stub_auth_p, bundle_p, pub_hex, syn_expectations = (
        _build_synthetic_dry_run_bundle_and_receipts(tmp_path)
    )
    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("22" * 32))
    base_auth_obj = json.loads(stub_auth_p.read_text(encoding="utf-8"))
    base_bundle_obj = json.loads(bundle_p.read_text(encoding="utf-8"))

    # Negative Case F-01a: Missing 1 of the 7 pinned artifacts in manifest
    missing_bundle_obj = dict(base_bundle_obj)
    missing_bundle_obj["artifacts"] = list(base_bundle_obj["artifacts"][:-1])
    missing_bundle_p = bundle_p.parent / "missing_artifact_bundle.json"
    missing_bundle_p.write_text(json.dumps(missing_bundle_obj), encoding="utf-8")
    missing_auth_p = _sign_stub_auth_receipt(priv, base_auth_obj, missing_bundle_p)
    with pytest.raises(ValueError, match="STUB-01_MISSING_PINNED_ARTIFACTS"):
        execute_stub01_fx01_hash_and_arm_p_counts(
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=missing_auth_p,
            corpus_bundle_manifest_path=missing_bundle_p,
            expectations=syn_expectations,
            _test_only_trusted_owner_pubkey_hex=pub_hex,
        )

    # Negative Case F-01b: Extra unapproved 8th artifact added to manifest
    extra_file = bundle_p.parent / "synthetic_bundle_aux_08.json"
    extra_raw = b'{"extra": true}\n'
    extra_file.write_bytes(extra_raw)
    extra_bundle_obj = dict(base_bundle_obj)
    extra_bundle_obj["artifacts"] = [
        *base_bundle_obj["artifacts"],
        {
            "artifact_id": "syn_artifact_08_unapproved",
            "canonical_repo_path": "data/evaluation/w07/synthetic_bundle_aux_08.json",
            "relative_path": extra_file.name,
            "size_bytes": len(extra_raw),
            "sha256": hashlib.sha256(extra_raw).hexdigest(),
            "git_blob_sha1": compute_git_blob_sha1(extra_raw),
        },
    ]
    extra_bundle_p = bundle_p.parent / "extra_artifact_bundle.json"
    extra_bundle_p.write_text(json.dumps(extra_bundle_obj), encoding="utf-8")
    extra_auth_p = _sign_stub_auth_receipt(priv, base_auth_obj, extra_bundle_p)
    with pytest.raises(ValueError, match="STUB-01_UNEXPECTED_EXTRA_ARTIFACTS"):
        execute_stub01_fx01_hash_and_arm_p_counts(
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=extra_auth_p,
            corpus_bundle_manifest_path=extra_bundle_p,
            expectations=syn_expectations,
            _test_only_trusted_owner_pubkey_hex=pub_hex,
        )

    # Negative Case F-01c: Self-consistent manifest + disk tampering (file on disk is
    # modified AND manifest hashes/sizes are updated to match the modified file, but
    # they diverge from the pinned scientific authority table in expectations!)
    aux7_path = bundle_p.parent / "synthetic_bundle_aux_07.json"
    orig_aux7_bytes = aux7_path.read_bytes()
    try:
        forged_bytes = b'{"synthetic_artifact_index": 7, "status": "FORGED_ON_DISK"}\n'
        aux7_path.write_bytes(forged_bytes)
        forged_bundle_obj = json.loads(bundle_p.read_text(encoding="utf-8"))
        for entry in forged_bundle_obj["artifacts"]:
            if entry["artifact_id"] == "syn_artifact_07":
                entry["size_bytes"] = len(forged_bytes)
                entry["sha256"] = hashlib.sha256(forged_bytes).hexdigest()
                entry["git_blob_sha1"] = compute_git_blob_sha1(forged_bytes)
        forged_bundle_p = bundle_p.parent / "forged_self_consistent_bundle.json"
        forged_bundle_p.write_text(json.dumps(forged_bundle_obj), encoding="utf-8")
        forged_auth_p = _sign_stub_auth_receipt(priv, base_auth_obj, forged_bundle_p)

        with pytest.raises(ValueError, match="STUB-01_AUTHORITY_SPEC_MISMATCH"):
            execute_stub01_fx01_hash_and_arm_p_counts(
                annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
                tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
                stub_auth_receipt_path=forged_auth_p,
                corpus_bundle_manifest_path=forged_bundle_p,
                expectations=syn_expectations,
                _test_only_trusted_owner_pubkey_hex=pub_hex,
            )

        # Negative Case F-01d: Manifest keeps pinned authority hashes, but disk file is modified
        with pytest.raises(
            ValueError, match="STUB-01_DISK_FILE_MISMATCH_AGAINST_PINNED_AUTHORITY"
        ):
            execute_stub01_fx01_hash_and_arm_p_counts(
                annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
                tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
                stub_auth_receipt_path=stub_auth_p,
                corpus_bundle_manifest_path=bundle_p,
                expectations=syn_expectations,
                _test_only_trusted_owner_pubkey_hex=pub_hex,
            )
    finally:
        aux7_path.write_bytes(orig_aux7_bytes)


def test_stub03_f02_pinned_v_sha256_binding_and_negative_cases(
    tmp_path: Path,
) -> None:
    """F-02: Verify STUB-03 enforces exact equality against pinned V SHA-256 and scopes 4-branch check."""
    assert (
        LIVE_137_CORPUS_EXPECTATIONS.expected_sanitized_view_v_sha256
        == PINNED_LIVE_137_SANITIZED_VIEW_V_SHA256
        == "046424e521f967f6c5575da1eeb914e5d340a118861c0cf04ca45256b364533d"
    )

    stub_auth_p, bundle_p, pub_hex, syn_expectations = (
        _build_synthetic_dry_run_bundle_and_receipts(tmp_path)
    )

    # Negative Case F-02a: All 4 sanitizer branches agree with each other, but computed V
    # digest does not equal the pinned expected_sanitized_view_v_sha256 -> fail closed!
    wrong_v_expectations = replace(
        syn_expectations,
        expected_sanitized_view_v_sha256=PINNED_LIVE_137_SANITIZED_VIEW_V_SHA256,
    )
    with pytest.raises(ValueError, match="STUB-03_PINNED_V_SHA256_MISMATCH"):
        execute_stub03_fx03_audit_tags_and_v_hash(
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=stub_auth_p,
            corpus_bundle_manifest_path=bundle_p,
            expectations=wrong_v_expectations,
            _test_only_trusted_owner_pubkey_hex=pub_hex,
        )

    # Negative Case F-02b: Missing or malformed expected_sanitized_view_v_sha256 -> fail closed!
    malformed_v_expectations = replace(
        syn_expectations,
        expected_sanitized_view_v_sha256="",
    )
    with pytest.raises(ValueError, match="STUB-03_MISSING_PINNED_V_SHA256"):
        execute_stub03_fx03_audit_tags_and_v_hash(
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=stub_auth_p,
            corpus_bundle_manifest_path=bundle_p,
            expectations=malformed_v_expectations,
            _test_only_trusted_owner_pubkey_hex=pub_hex,
        )


def test_stub01_to_stub05_fail_closed_security_and_anti_sandbox_escape(
    tmp_path: Path,
) -> None:
    """Verify STUB-01..05 receipt gate rejects unauthorized, escalated, tampered, or real-corpus calls."""
    stub_auth_p, bundle_p, pub_hex, _ = _build_synthetic_dry_run_bundle_and_receipts(
        tmp_path
    )

    with pytest.raises(
        PermissionError, match="STUB01_05_BLOCKED_UNPINNED_LIVE_OWNER_KEY"
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-01",
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=stub_auth_p,
            corpus_bundle_manifest_path=bundle_p,
        )

    with pytest.raises(
        PermissionError,
        match="STUB01_05_BLOCKED_TECH_FREEZE_RECEIPT_NOT_EXECUTION_PERMIT",
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-01",
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            corpus_bundle_manifest_path=bundle_p,
            _test_only_trusted_owner_pubkey_hex=pub_hex,
        )

    with pytest.raises(
        PermissionError, match="STUB01_05_BLOCKED_FORBIDDEN_STUB_ID"
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-06",
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=stub_auth_p,
            corpus_bundle_manifest_path=bundle_p,
            _test_only_trusted_owner_pubkey_hex=pub_hex,
        )

    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("22" * 32))
    escalated_obj = json.loads(stub_auth_p.read_text(encoding="utf-8"))
    escalated_obj["stub_06_formal_g3_g4_authorized"] = True
    escalated_obj["owner_detached_signature_hex"] = priv.sign(
        canonical_stub01_05_auth_signing_bytes(escalated_obj)
    ).hex()
    escalated_p = tmp_path / "escalated_stub_auth.json"
    escalated_p.write_text(json.dumps(escalated_obj), encoding="utf-8")
    with pytest.raises(
        PermissionError, match="STUB01_05_BLOCKED_SCOPE_ESCALATION_FORBIDDEN"
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-01",
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=escalated_p,
            corpus_bundle_manifest_path=bundle_p,
            _test_only_trusted_owner_pubkey_hex=pub_hex,
        )

    escaped_bundle_obj = json.loads(bundle_p.read_text(encoding="utf-8"))
    escaped_bundle_obj["artifacts"][0]["sha256"] = (
        "9b0ed36e060924057872a2e8fe9941940f7bc3455f2c9cad21cdc9a9c1141fda"
    )
    escaped_bundle_p = bundle_p.parent / "escaped_bundle_manifest.json"
    escaped_bundle_p.write_text(json.dumps(escaped_bundle_obj), encoding="utf-8")
    escaped_auth_obj = json.loads(stub_auth_p.read_text(encoding="utf-8"))
    escaped_auth_obj["corpus_bundle_manifest_sha256"] = hashlib.sha256(
        escaped_bundle_p.read_bytes()
    ).hexdigest()
    escaped_auth_obj["owner_detached_signature_hex"] = priv.sign(
        canonical_stub01_05_auth_signing_bytes(escaped_auth_obj)
    ).hex()
    escaped_auth_p = tmp_path / "escaped_stub_auth.json"
    escaped_auth_p.write_text(json.dumps(escaped_auth_obj), encoding="utf-8")

    with pytest.raises(
        PermissionError, match="STUB01_05_SANDBOX_ESCAPE_BLOCKED"
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-01",
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=escaped_auth_p,
            corpus_bundle_manifest_path=escaped_bundle_p,
            _test_only_trusted_owner_pubkey_hex=pub_hex,
        )


def test_runner_synthetic_vs_formal_mode_separation_and_cryptographic_receipt_checks(
    tmp_path: Path,
) -> None:
    """Verify synthetic-prep blocks protected artifacts and formal-execution verifies signed receipts."""
    c_path = tmp_path / "syn_corpus.jsonl"
    q_path = tmp_path / "syn_queries.jsonl"
    c_path.write_text(
        json.dumps({"document_id": "syn-doc-1", "canonical_text_S": "Cầu Rồng Đà Nẵng."})
        + "\n",
        encoding="utf-8",
    )
    q_path.write_text(
        json.dumps({"query_id": "syn-q-1", "query_text": "Cầu Rồng"}) + "\n",
        encoding="utf-8",
    )

    from w07_retrieval.schema import load_canonical_document

    b1b_doc = load_canonical_document(
        {
            "document_id": "w07-b1b-doc-overture-test",
            "canonical_text_S": "Test",
        }
    )
    with pytest.raises(PermissionError, match="SYNTHETIC_PREP_REAL_B1B_DOC_FORBIDDEN"):
        validate_synthetic_prep_boundaries(
            corpus_path=c_path, queries_path=q_path, docs=[b1b_doc]
        )

    docs_137 = [
        load_canonical_document(
            {"document_id": f"syn-{i}", "canonical_text_S": f"Doc {i}"}
        )
        for i in range(EXPECTED_ELIGIBLE_DOC_COUNT)
    ]
    with pytest.raises(PermissionError, match="SYNTHETIC_PREP_REAL_137_CORPUS_FORBIDDEN"):
        validate_synthetic_prep_boundaries(
            corpus_path=c_path, queries_path=q_path, docs=docs_137
        )

    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("11" * 32))
    pub_hex = (
        priv.public_key()
        .public_bytes(Encoding.Raw, PublicFormat.Raw)
        .hex()
    )
    corpus_sha = hashlib.sha256(c_path.read_bytes()).hexdigest()
    queries_sha = hashlib.sha256(q_path.read_bytes()).hexdigest()
    annex_sha = APPROVED_ANNEX_V0_2_2_SHA256

    frozen_rec = {
        "schema_version": FROZEN_CORPUS_RECEIPT_SCHEMA_V1,
        "g15_frozen": True,
        "annex_g15_sha256": annex_sha,
        "eligible_document_count": EXPECTED_ELIGIBLE_DOC_COUNT,
        "city_counts": EXPECTED_CITY_COUNTS,
        "r_audit_tags_removed": EXPECTED_R_AUDIT_REMOVED,
        "r_audit_tags_remaining": EXPECTED_R_AUDIT_REMAINING,
        "sanitized_view_v_sha256": EXPECTED_SANITIZED_VIEW_V_137_SHA256,
        "pinned_tokenizer_json_sha256": PINNED_TOKENIZER_SHA256,
        "corpus_sha256": corpus_sha,
    }
    frozen_p = tmp_path / "frozen_corpus_receipt.json"
    frozen_p.write_text(
        json.dumps(frozen_rec, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    frozen_rec_sha = hashlib.sha256(frozen_p.read_bytes()).hexdigest()

    owner_rec: Dict[str, Any] = {
        "schema_version": OWNER_AUTH_RECEIPT_SCHEMA_V1,
        "g15_annex_frozen": True,
        "owner_authorized_g3_execution": True,
        "authorized_execution_mode": "formal-execution",
        "tokenizer_erratum_resolved": True,
        "pinned_tokenizer_json_sha256": PINNED_TOKENIZER_SHA256,
        "annex_g15_sha256": annex_sha,
        "corpus_sha256": corpus_sha,
        "queries_sha256": queries_sha,
        "frozen_corpus_receipt_sha256": frozen_rec_sha,
        "ed25519_domain_tag": ED25519_FORMAL_EXECUTION_DOMAIN_ASCII,
        "owner_ed25519_pubkey_hex": pub_hex,
    }
    sig_bytes = priv.sign(canonical_owner_auth_signing_bytes(owner_rec))
    owner_rec["owner_detached_signature_hex"] = sig_bytes.hex()
    owner_p = tmp_path / "owner_auth_receipt.json"
    owner_p.write_text(
        json.dumps(owner_rec, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(
        PermissionError, match="FORMAL_EXECUTION_BLOCKED_UNPINNED_LIVE_OWNER_KEY"
    ):
        validate_formal_execution_gate(
            corpus_path=c_path,
            queries_path=q_path,
            owner_auth_receipt_path=owner_p,
            frozen_corpus_receipt_path=frozen_p,
        )

    gate_res = validate_formal_execution_gate(
        corpus_path=c_path,
        queries_path=q_path,
        owner_auth_receipt_path=owner_p,
        frozen_corpus_receipt_path=frozen_p,
        _test_only_trusted_owner_pubkey_hex=pub_hex,
    )
    assert gate_res["formal_g15_frozen_verified"] is True
    assert gate_res["owner_authorization_verified"] is True
    assert gate_res["trust_anchor_mode"] == "EPHEMERAL_UNIT_TEST_SANDBOX_ONLY"

    bad_sig_rec = dict(owner_rec)
    flipped = ("0" if sig_bytes.hex()[0] != "0" else "1") + sig_bytes.hex()[1:]
    bad_sig_rec["owner_detached_signature_hex"] = flipped
    bad_owner_p = tmp_path / "bad_owner_auth_receipt.json"
    bad_owner_p.write_text(
        json.dumps(bad_sig_rec, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    with pytest.raises(
        PermissionError, match="FORMAL_EXECUTION_BLOCKED_INVALID_ED25519_SIGNATURE"
    ):
        validate_formal_execution_gate(
            corpus_path=c_path,
            queries_path=q_path,
            owner_auth_receipt_path=bad_owner_p,
            frozen_corpus_receipt_path=frozen_p,
            _test_only_trusted_owner_pubkey_hex=pub_hex,
        )


def test_real_corpus_stub_activation_criteria_completeness() -> None:
    """Verify all 6 real-corpus stubs (STUB-01..STUB-06) remain HOLD with complete activation criteria."""
    assert set(REAL_CORPUS_STUB_ACTIVATION_CRITERIA_V1.keys()) == {
        f"STUB-0{i}" for i in range(1, 7)
    }
    for stub_id, spec in REAL_CORPUS_STUB_ACTIVATION_CRITERIA_V1.items():
        assert spec["current_status"] == "HOLD", f"{stub_id} must remain HOLD"
        assert "implementation_entry" in spec and spec["implementation_entry"]
        assert len(spec["unlock_prerequisites"]) >= 1
        assert len(spec["pass_assertions_when_unlocked"]) >= 2


def test_owner_chat_readonly_v1_auth01_to_auth10_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """AUTH-01..AUTH-10: Verify scoped OWNER_CHAT_READONLY_V1 contract, negative gates, and one-shot dedup."""
    import importlib.util

    runner_cli_path = (
        PREP_ROOT / "scripts" / "run_w07_stub01_05_owner_chat_preflight.py"
    )
    spec = importlib.util.spec_from_file_location(
        "run_w07_stub01_05_owner_chat_preflight", runner_cli_path
    )
    assert spec is not None and spec.loader is not None
    cli_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli_mod)
    run_one_shot_stub01_05_preflight = cli_mod.run_one_shot_stub01_05_preflight

    _, bundle_p, _, syn_expectations = _build_synthetic_dry_run_bundle_and_receipts(
        tmp_path
    )
    bundle_sha = hashlib.sha256(bundle_p.read_bytes()).hexdigest()

    base_policy_obj = json.loads(
        ARCHIVED_CHAT_POLICY_RECEIPT_V1_PATH.read_text(encoding="utf-8")
    )
    syn_policy_obj = dict(base_policy_obj)
    syn_policy_obj[
        "corpus_bundle_manifest_expected_sha256_reported_by_antigravity"
    ] = bundle_sha
    syn_policy_p = tmp_path / "syn_owner_chat_policy_receipt.json"
    syn_policy_p.write_text(
        json.dumps(syn_policy_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # AUTH-01: Valid OWNER_CHAT_READONLY_V1 on synthetic fixtures passes all 5 stubs + CLI one-shot
    out_dir_1 = tmp_path / "one_shot_out_1"
    summary = run_one_shot_stub01_05_preflight(
        output_dir=out_dir_1,
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        stub_auth_receipt_path=syn_policy_p,
        corpus_bundle_manifest_path=bundle_p,
        auth_mode="OWNER_CHAT_READONLY_V1",
        chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
        expectations=syn_expectations,
        _synthetic_fixture_mode=True,
    )
    assert summary["overall_status"] == "PASS"
    assert summary["executed_stub_count"] == 5
    assert summary["authorization_mode"] == "OWNER_CHAT_READONLY_V1"
    assert summary["identity_authentication"] == "NOT_CRYPTOGRAPHICALLY_VERIFIED"
    assert summary["observable_counters"]["live_api_calls"] == 0
    assert summary["observable_counters"]["network_requests"] == 0
    assert summary["downstream_governance_hold"]["od_g15_05"] == "HOLD"
    assert (
        summary["downstream_governance_hold"]["stub_06_formal_g3_g4_authorized"]
        is False
    )

    # AUTH-10: Retry after a completed pass in the same output_dir is blocked (ALREADY_EXECUTED)
    with pytest.raises(RuntimeError, match="ALREADY_EXECUTED"):
        run_one_shot_stub01_05_preflight(
            output_dir=out_dir_1,
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=syn_policy_p,
            corpus_bundle_manifest_path=bundle_p,
            auth_mode="OWNER_CHAT_READONLY_V1",
            chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
            expectations=syn_expectations,
            _synthetic_fixture_mode=True,
        )

    # AUTH-02: Missing/tampered waiver decision or policy receipt (or old unsigned Ed25519 template)
    bad_waiver_p = tmp_path / "bad_waiver.md"
    bad_waiver_p.write_text("tampered waiver", encoding="utf-8")
    with pytest.raises(
        PermissionError, match="STUB01_05_BLOCKED_CHAT_WAIVER_HASH_MISMATCH"
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-01",
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=syn_policy_p,
            corpus_bundle_manifest_path=bundle_p,
            auth_mode="OWNER_CHAT_READONLY_V1",
            chat_auth_waiver_path=bad_waiver_p,
            _synthetic_fixture_mode=True,
        )

    # In live mode (_synthetic_fixture_mode=False), any policy receipt whose raw SHA-256 != aa0881be... fails closed
    with pytest.raises(
        PermissionError, match="STUB01_05_BLOCKED_CHAT_POLICY_RECEIPT_HASH_MISMATCH"
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-01",
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=syn_policy_p,
            corpus_bundle_manifest_path=bundle_p,
            auth_mode="OWNER_CHAT_READONLY_V1",
            chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
            _synthetic_fixture_mode=False,
        )

    # Old unsigned Ed25519 template rejected in OWNER_CHAT_READONLY_V1
    unsigned_ed_tpl_p = tmp_path / "unsigned_ed25519_tpl.json"
    unsigned_ed_tpl_p.write_text(
        json.dumps(
            {
                "schema_version": STUB01_05_AUTH_RECEIPT_SCHEMA_V1,
                "_template_status": "UNSIGNED_NONEXECUTABLE_DRAFT__OWNER_MUST_SIGN_LOCALLY",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(
        PermissionError,
        match="STUB01_05_BLOCKED_UNSIGNED_ED25519_TEMPLATE_NOT_CHAT_POLICY",
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-01",
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=unsigned_ed_tpl_p,
            corpus_bundle_manifest_path=bundle_p,
            auth_mode="OWNER_CHAT_READONLY_V1",
            chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
            _synthetic_fixture_mode=True,
        )

    # AUTH-03: Wrong Annex / tech-freeze receipt / tokenizer / manifest SHA in policy receipt
    for field_name, bad_val, err_pat in (
        (
            "approved_annex_v0_2_2_sha256",
            "0" * 64,
            "STUB01_05_BLOCKED_ANNEX_V022_BINDING_MISMATCH",
        ),
        (
            "technical_freeze_owner_receipt_sha256",
            "0" * 64,
            "STUB01_05_BLOCKED_TECH_FREEZE_RECEIPT_BINDING_MISMATCH",
        ),
        (
            "pinned_tokenizer_json_sha256",
            "0" * 64,
            "STUB01_05_BLOCKED_TOKENIZER_SHA256_MISMATCH",
        ),
        (
            "corpus_bundle_manifest_expected_sha256_reported_by_antigravity",
            "0" * 64,
            "STUB01_05_BLOCKED_BUNDLE_MANIFEST_HASH_MISMATCH",
        ),
    ):
        bad_pol = dict(syn_policy_obj)
        bad_pol[field_name] = bad_val
        bad_pol_p = tmp_path / f"bad_{field_name}.json"
        bad_pol_p.write_text(json.dumps(bad_pol), encoding="utf-8")
        with pytest.raises(PermissionError, match=err_pat):
            validate_stub01_05_readonly_preflight_gate(
                requested_stub_id="STUB-01",
                annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
                tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
                stub_auth_receipt_path=bad_pol_p,
                corpus_bundle_manifest_path=bundle_p,
                auth_mode="OWNER_CHAT_READONLY_V1",
                chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
                _synthetic_fixture_mode=True,
            )

    # AUTH-04 & AUTH-08: F-01 (self-consistent tampered manifest) and F-02 (bad V SHA) fail under OWNER_CHAT_READONLY_V1
    bad_f01_expectations = replace(
        syn_expectations,
        expected_pinned_artifacts=(
            replace(syn_expectations.expected_pinned_artifacts[0], sha256="f" * 64),
            *syn_expectations.expected_pinned_artifacts[1:],
        ),
    )
    with pytest.raises(ValueError, match="STUB-01_AUTHORITY_SPEC_MISMATCH"):
        execute_stub01_fx01_hash_and_arm_p_counts(
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=syn_policy_p,
            corpus_bundle_manifest_path=bundle_p,
            expectations=bad_f01_expectations,
            auth_mode="OWNER_CHAT_READONLY_V1",
            chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
            _synthetic_fixture_mode=True,
        )

    bad_f02_expectations = replace(
        syn_expectations,
        expected_sanitized_view_v_sha256="046424e521f967f6c5575da1eeb914e5d340a118861c0cf04ca45256b364533d",
    )
    with pytest.raises(ValueError, match="STUB-03_PINNED_V_SHA256_MISMATCH"):
        execute_stub03_fx03_audit_tags_and_v_hash(
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=syn_policy_p,
            corpus_bundle_manifest_path=bundle_p,
            expectations=bad_f02_expectations,
            auth_mode="OWNER_CHAT_READONLY_V1",
            chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
            _synthetic_fixture_mode=True,
        )

    # AUTH-05 & AUTH-09: STUB-06 / G3 / G4 / FINAL-50 / API escalation blocked, and runner.py rejects chat policy
    with pytest.raises(
        PermissionError, match="STUB01_05_BLOCKED_FORBIDDEN_STUB_ID"
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-06",
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=syn_policy_p,
            corpus_bundle_manifest_path=bundle_p,
            auth_mode="OWNER_CHAT_READONLY_V1",
            chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
            _synthetic_fixture_mode=True,
        )

    for esc_flag in (
        "stub_06_formal_g3_g4_authorized",
        "g2_g3_g4_g5_g6_authorized",
        "final50_dev_t0_live_api_authorized",
    ):
        esc_pol = dict(syn_policy_obj)
        esc_pol[esc_flag] = True
        esc_p = tmp_path / f"esc_{esc_flag}.json"
        esc_p.write_text(json.dumps(esc_pol), encoding="utf-8")
        with pytest.raises(
            PermissionError, match="STUB01_05_BLOCKED_SCOPE_ESCALATION_FORBIDDEN"
        ):
            validate_stub01_05_readonly_preflight_gate(
                requested_stub_id="STUB-01",
                annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
                tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
                stub_auth_receipt_path=esc_p,
                corpus_bundle_manifest_path=bundle_p,
                auth_mode="OWNER_CHAT_READONLY_V1",
                chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
                _synthetic_fixture_mode=True,
            )

    # AUTH-09: runner.validate_formal_execution_gate rejects chat policy receipt and runner.py is unchanged
    runner_py_path = PREP_ROOT / "src" / "w07_retrieval" / "runner.py"
    runner_lf_bytes = runner_py_path.read_bytes().replace(b"\r\n", b"\n")
    assert (
        hashlib.sha256(runner_lf_bytes).hexdigest()
        == "bcc93c100c52dd08ee51737655c5bf9d8ac2e759a0bad8f0b24ee065befae10d"
    )
    dummy_q = tmp_path / "dummy_q.jsonl"
    dummy_q.write_text('{"query_id":"q1","query_text":"t"}\n', encoding="utf-8")
    with pytest.raises(
        PermissionError, match="FORMAL_EXECUTION_BLOCKED_INVALID_CORPUS_RECEIPT_SCHEMA"
    ):
        validate_formal_execution_gate(
            corpus_path=bundle_p,
            queries_path=dummy_q,
            owner_auth_receipt_path=ARCHIVED_CHAT_POLICY_RECEIPT_V1_PATH,
            frozen_corpus_receipt_path=bundle_p,
        )

    # AUTH-06: Env vars without policy receipt fail closed in OWNER_CHAT_READONLY_V1
    for k in ("W07_G15_FROZEN", "W07_OWNER_AUTHORIZED", "W07_STUB_01_05_AUTHORIZED"):
        monkeypatch.setenv(k, "1")
    with pytest.raises(
        PermissionError,
        match="STUB01_05_BLOCKED_MISSING_RECEIPTS.*Plain environment variables",
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-01",
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=None,
            corpus_bundle_manifest_path=bundle_p,
            auth_mode="OWNER_CHAT_READONLY_V1",
            chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
        )

    # AUTH-07: Legacy signed mode (ED25519_SIGNED_V1) rejects the chat policy receipt
    with pytest.raises(
        PermissionError, match="STUB01_05_BLOCKED_INVALID_AUTH_SCHEMA"
    ):
        validate_stub01_05_readonly_preflight_gate(
            requested_stub_id="STUB-01",
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=ARCHIVED_CHAT_POLICY_RECEIPT_V1_PATH,
            corpus_bundle_manifest_path=bundle_p,
            auth_mode="ED25519_SIGNED_V1",
        )


def test_stub02_c1_narrow_corrective_tham_khao_hierarchy_and_accounting(
    tmp_path: Path,
) -> None:
    """Verify STUB-02 pipeline retains allowlisted empty parent `== Tham khảo ==` & updates derived 24 drop expectation."""
    assert LIVE_137_CORPUS_EXPECTATIONS.expected_empty_parent_headings_propagated == 21
    assert LIVE_137_CORPUS_EXPECTATIONS.expected_allowlisted_footer_drops == 24

    _, bundle_p, _, syn_expectations = _build_synthetic_dry_run_bundle_and_receipts(
        tmp_path
    )
    bundle_obj = json.loads(bundle_p.read_text(encoding="utf-8"))
    corpus_p = bundle_p.parent / bundle_obj["primary_corpus_jsonl"]
    docs_raw = [
        json.loads(line)
        for line in corpus_p.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # Replace doc 1 footer `== Tham khảo ==` leaf with hierarchical `== Tham khảo == -> === Ghi chú === -> === Đọc thêm ===`
    # while doc 2 retains standalone leaf `== Liên kết ngoài ==`.
    docs_raw[0]["canonical_text_S"] = (
        "== Lịch sử ==\n"
        "### Bia tiến sĩ\n"
        "Văn Miếu tại Hà Nội lưu giữ tám mươi hai bia tiến sĩ.\n"
        "== Tham khảo ==\n"
        "=== Ghi chú ===\n"
        "=== Đọc thêm ===\n"
        "Tài liệu bảo tồn ghi nhận năm dựng bia cổ.\n"
    )
    corpus_p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in docs_raw)
        + "\n",
        encoding="utf-8",
    )

    loaded_docs = load_corpus_jsonl(corpus_p)
    sanitized_by_doc = {
        d.document_id: sanitize_canonical_to_view(d.canonical_text_S)
        for d in loaded_docs
    }
    raw_b = corpus_p.read_bytes()
    bundle_obj["artifacts"][0]["size_bytes"] = len(raw_b)
    bundle_obj["artifacts"][0]["sha256"] = hashlib.sha256(raw_b).hexdigest()
    bundle_obj["artifacts"][0]["git_blob_sha1"] = compute_git_blob_sha1(raw_b)
    bundle_p.write_text(
        json.dumps(bundle_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    new_pinned = (
        replace(
            syn_expectations.expected_pinned_artifacts[0],
            size_bytes=len(raw_b),
            sha256=hashlib.sha256(raw_b).hexdigest(),
            git_blob_sha1=compute_git_blob_sha1(raw_b),
        ),
        *syn_expectations.expected_pinned_artifacts[1:],
    )
    hier_expectations = replace(
        syn_expectations,
        expected_pinned_artifacts=new_pinned,
        expected_total_canonical_s_chars=sum(len(d.canonical_text_S) for d in loaded_docs),
        expected_removed_r_audit_chars=sum(
            b - a for r in sanitized_by_doc.values() for a, b in r.removed_intervals
        ),
        expected_retained_view_v_chars=sum(len(r.view_V) for r in sanitized_by_doc.values()),
        expected_r_audit_tags_removed=1,
        expected_r_audit_docs_with_tags=1,
        expected_r_audit_families=frozenset({"wikivoyage", "osm_website_pointer"}),
        expected_sanitized_view_v_sha256=compute_canonical_view_v_sha256(
            loaded_docs, sanitized_by_doc
        ),
        # Exact count: `== Lịch sử ==` + `== Tham khảo ==` -> 2 unique empty parents;
        # `== Liên kết ngoài ==` -> 1 omitted allowlisted leaf; `=== Ghi chú ===` -> 1 heading_only chunk.
        expected_empty_parent_headings_propagated=2,
        expected_allowlisted_footer_drops=1,
        expected_c1_chunk_count=None,
    )

    base_policy_obj = json.loads(
        ARCHIVED_CHAT_POLICY_RECEIPT_V1_PATH.read_text(encoding="utf-8")
    )
    syn_policy_obj = dict(base_policy_obj)
    syn_policy_obj[
        "corpus_bundle_manifest_expected_sha256_reported_by_antigravity"
    ] = hashlib.sha256(bundle_p.read_bytes()).hexdigest()
    syn_policy_p = tmp_path / "hier_owner_chat_policy_receipt.json"
    syn_policy_p.write_text(
        json.dumps(syn_policy_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    r2 = execute_stub02_fx02_canonical_conservation(
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        stub_auth_receipt_path=syn_policy_p,
        corpus_bundle_manifest_path=bundle_p,
        expectations=hier_expectations,
        auth_mode="OWNER_CHAT_READONLY_V1",
        chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
        _synthetic_fixture_mode=True,
    )
    assert r2["status"] == "PASS"
    assert r2["empty_parent_headings_propagated"] == 2
    assert r2["allowlisted_footer_drops"] == 1
    assert r2["non_allowlisted_empty_headings_preserved_as_chunks"] == 1

    r4 = execute_stub04_fx04_c1_token_ceiling(
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        stub_auth_receipt_path=syn_policy_p,
        corpus_bundle_manifest_path=bundle_p,
        expectations=hier_expectations,
        auth_mode="OWNER_CHAT_READONLY_V1",
        chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
        _synthetic_fixture_mode=True,
    )
    assert r4["status"] == "PASS"
    assert r4["ceiling_violations_gt_128"] == 0
    assert r4["coverage_lost_due_to_chunking"] == 0


def test_stub05_narrow_harness_newline_negative_and_lexical_straddle(
    tmp_path: Path,
) -> None:
    """STUB-05 narrow harness corrective: `.\n` negative fixture, bounded projection fidelity, & lexical mid-sentence straddle."""
    stub_auth_p, bundle_p, pub_hex, syn_expectations = (
        _build_synthetic_dry_run_bundle_and_receipts(tmp_path)
    )
    bundle_obj = json.loads(bundle_p.read_text(encoding="utf-8"))
    corpus_p = bundle_p.parent / bundle_obj["primary_corpus_jsonl"]
    tok = load_minilm_tokenizer(resolve_snapshot_dir(None), verify_sha256=True)

    # Subtest A: Synthetic mirror of `.\n` right after R_AUDIT tag (real corpus morphology)
    docs_nl = [
        json.loads(line)
        for line in corpus_p.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tag_nl = (
        "[CORROBORATED: canonical_poi:00000000-0000-0000-0000-000000000001, "
        "osm:node/101, wikidata:Q101, wikipedia:vi:Van_Mieu]"
    )
    filler_nl = (
        "Văn Miếu Quốc Tử Giám tại Hà Nội lưu giữ bia tiến sĩ đá cổ và kiến trúc truyền thống Việt Nam. "
        * 14
    )
    doc_nl_s = (
        f"Bảo tàng giới thiệu khu di tích (museum) {tag_nl}.\n"
        f"Độ tin cậy nguồn (confidence): 0.8500. {filler_nl}"
        "Mã ARCHIVE-TAIL-9981."
    )
    docs_nl[0]["canonical_text_S"] = doc_nl_s
    corpus_p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in docs_nl)
        + "\n",
        encoding="utf-8",
    )
    r5_nl = execute_stub05_fx05_overture_visibility(
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        stub_auth_receipt_path=stub_auth_p,
        corpus_bundle_manifest_path=bundle_p,
        expectations=syn_expectations,
        _test_only_trusted_owner_pubkey_hex=pub_hex,
    )
    assert r5_nl["status"] == "PASS"
    assert (
        r5_nl["early_r_audit_straddle_scope"]
        == "MARKER_ADJACENCY_AND_PROJECTION_FIDELITY_NOT_SUBSTANTIVE_LEXICAL_EVIDENCE"
    )
    assert r5_nl["early_r_audit_straddle_blind_crossed_newline"] is True
    assert r5_nl["early_r_audit_newline_negative_evidence_hit"] is False
    assert r5_nl["early_r_audit_newline_negative_visible_hit"] is False
    r1_s = doc_nl_s.index(tag_nl)
    r1_e = r1_s + len(tag_nl)
    assert r5_nl["early_r_audit_positive_window_v"] == [r1_s - 8, r1_s + 1]
    assert r5_nl["early_r_audit_positive_g_sub_s"] == [[r1_s - 8, r1_s], [r1_e, r1_e + 1]]
    assert r5_nl["early_r_audit_straddle_intervals"] == 2
    assert r5_nl["early_r_audit_straddle_visible_hit"] is True
    assert r5_nl["tail_span_evidence_hit"] is True
    assert r5_nl["tail_span_visible_hit"] is False
    assert r5_nl["cutoff_straddle_evidence_hit"] is True
    assert r5_nl["cutoff_straddle_visible_hit"] is False
    assert r5_nl["deleted_tag_chars_in_c_vis"] == 0

    # Subtest B: Multi-family mid-sentence case with real lexical material on both sides + negatives
    tag_lex = (
        "[CORROBORATED: canonical_poi:00000000-0000-0000-0000-000000000002, "
        "osm:way/202, wikidata:Q202, wikipedia:en:Museum]"
    )
    doc_lex_s = (
        f"Bảo tàng trưng bày hiện vật lịch sử {tag_lex} và tài liệu dân tộc học.\n"
        f"Độ tin cậy nguồn: 0.9100. {filler_nl}"
        "Mã cuối bị cắt: ARCHIVE-TAIL-9981."
    )
    docs_lex = list(docs_nl)
    docs_lex[0] = dict(docs_nl[0], canonical_text_S=doc_lex_s)
    corpus_p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in docs_lex)
        + "\n",
        encoding="utf-8",
    )
    r5_lex = execute_stub05_fx05_overture_visibility(
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        stub_auth_receipt_path=stub_auth_p,
        corpus_bundle_manifest_path=bundle_p,
        expectations=syn_expectations,
        _test_only_trusted_owner_pubkey_hex=pub_hex,
    )
    assert r5_lex["status"] == "PASS"
    assert r5_lex["early_r_audit_straddle_blind_crossed_newline"] is False
    assert r5_lex["early_r_audit_newline_negative_evidence_hit"] is None

    loaded_lex = load_corpus_jsonl(corpus_p)[0]
    san_lex = sanitize_canonical_to_view(loaded_lex.canonical_text_S)
    c0_lex = C0Chunker().chunk_document(loaded_lex, san_lex, tok, max_vis_tokens=128)[0]
    c_full_lex = [(int(a), int(b)) for a, b in c0_lex.c_full_s_spans]
    c_vis_lex = [(int(a), int(b)) for a, b in c0_lex.c_vis_s_spans_dense]

    pre_lex = "hiện vật lịch sử "
    post_lex = " và tài liệu"
    r_lex_s = doc_lex_s.index(tag_lex)
    r_lex_e = r_lex_s + len(tag_lex)
    lexical_straddle_spans = [
        (r_lex_s - len(pre_lex), r_lex_s),
        (r_lex_e, r_lex_e + len(post_lex)),
    ]
    assert doc_lex_s[lexical_straddle_spans[0][0] : lexical_straddle_spans[0][1]] == pre_lex
    assert doc_lex_s[lexical_straddle_spans[1][0] : lexical_straddle_spans[1][1]] == post_lex
    assert intervals_contain(c_full_lex, lexical_straddle_spans) is True
    assert intervals_contain(c_vis_lex, lexical_straddle_spans) is True

    # Negative: Newline break span MUST remain unmapped / rejected (never coerce `\n` to canonical provenance)
    nl_break_phrase = "dân tộc học.\nĐộ tin"
    nl_s = doc_lex_s.index(nl_break_phrase)
    assert intervals_contain(c_full_lex, [(nl_s, nl_s + len(nl_break_phrase))]) is False
    assert intervals_contain(c_vis_lex, [(nl_s, nl_s + len(nl_break_phrase))]) is False

    # Negative: Overclaimed / marker-contaminated / tail-truncated spans rejected appropriately
    assert intervals_contain(c_vis_lex, [(r_lex_s - 2, r_lex_s + 4)]) is False
    tail_s = doc_lex_s.index("ARCHIVE-TAIL-9981")
    assert intervals_contain(c_full_lex, [(tail_s, tail_s + 17)]) is True
    assert intervals_contain(c_vis_lex, [(tail_s, tail_s + 17)]) is False

    # Subtest C: Collapsed boundary (sentence `.` + R_AUDIT + immediate `\n`, zero same-line char) fails closed
    docs_collapsed = list(docs_nl)
    docs_collapsed[0] = dict(
        docs_nl[0],
        canonical_text_S=(
            f"Bảo tàng giới thiệu khu di tích.{tag_nl}\n"
            f"Độ tin cậy nguồn: 0.8500. {filler_nl}"
        ),
    )
    corpus_p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in docs_collapsed)
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError, match="STUB-05 clamped marker-adjacency boundary window collapsed"
    ):
        execute_stub05_fx05_overture_visibility(
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            stub_auth_receipt_path=stub_auth_p,
            corpus_bundle_manifest_path=bundle_p,
            expectations=syn_expectations,
            _test_only_trusted_owner_pubkey_hex=pub_hex,
        )


@pytest.mark.real_corpus_gated
@pytest.mark.skipif(
    not is_real_corpus_stub01_05_authorized(requested_stub_id="STUB-01"),
    reason=REAL_CORPUS_STUB01_05_GATE_REASON,
)
def test_gated_real_corpus_fx01_hash_and_arm_p_counts() -> None:
    """FX-01: Verify 7 frozen dataset SHA-256s, Git blob SHA-1s, and 137 Arm P docs (59 HN/52 DN/26 HL)."""
    res = execute_stub01_fx01_hash_and_arm_p_counts(
        annex_v0_2_2_path=Path(os.environ.get("W07_APPROVED_ANNEX_V022_PATH", str(ARCHIVED_ANNEX_V022_PATH))),
        tech_freeze_receipt_path=Path(os.environ.get("W07_TECH_FREEZE_RECEIPT_PATH", str(ARCHIVED_RECEIPT_V022_PATH))),
        stub_auth_receipt_path=Path(os.environ["W07_STUB01_05_AUTH_RECEIPT_PATH"]),
        corpus_bundle_manifest_path=Path(os.environ["W07_STUB01_05_BUNDLE_MANIFEST_PATH"]),
        expectations=LIVE_137_CORPUS_EXPECTATIONS,
    )
    assert res["status"] == "PASS"


@pytest.mark.real_corpus_gated
@pytest.mark.skipif(
    not is_real_corpus_stub01_05_authorized(requested_stub_id="STUB-02"),
    reason=REAL_CORPUS_STUB01_05_GATE_REASON,
)
def test_gated_real_corpus_fx02_canonical_conservation() -> None:
    """FX-02: Verify 286,004 + 8,679 + 961 (857+104) == 295,644 code points, 21 parent breadcrumbs, 38 footers."""
    res = execute_stub02_fx02_canonical_conservation(
        annex_v0_2_2_path=Path(os.environ.get("W07_APPROVED_ANNEX_V022_PATH", str(ARCHIVED_ANNEX_V022_PATH))),
        tech_freeze_receipt_path=Path(os.environ.get("W07_TECH_FREEZE_RECEIPT_PATH", str(ARCHIVED_RECEIPT_V022_PATH))),
        stub_auth_receipt_path=Path(os.environ["W07_STUB01_05_AUTH_RECEIPT_PATH"]),
        corpus_bundle_manifest_path=Path(os.environ["W07_STUB01_05_BUNDLE_MANIFEST_PATH"]),
        expectations=LIVE_137_CORPUS_EXPECTATIONS,
    )
    assert res["status"] == "PASS"


@pytest.mark.real_corpus_gated
@pytest.mark.skipif(
    not is_real_corpus_stub01_05_authorized(requested_stub_id="STUB-03"),
    reason=REAL_CORPUS_STUB01_05_GATE_REASON,
)
def test_gated_real_corpus_fx03_audit_tags_and_v_hash() -> None:
    """FX-03: Verify 46/46 R_AUDIT tags removed across 23 Overture docs and V SHA-256 046424e5..."""
    res = execute_stub03_fx03_audit_tags_and_v_hash(
        annex_v0_2_2_path=Path(os.environ.get("W07_APPROVED_ANNEX_V022_PATH", str(ARCHIVED_ANNEX_V022_PATH))),
        tech_freeze_receipt_path=Path(os.environ.get("W07_TECH_FREEZE_RECEIPT_PATH", str(ARCHIVED_RECEIPT_V022_PATH))),
        stub_auth_receipt_path=Path(os.environ["W07_STUB01_05_AUTH_RECEIPT_PATH"]),
        corpus_bundle_manifest_path=Path(os.environ["W07_STUB01_05_BUNDLE_MANIFEST_PATH"]),
        expectations=LIVE_137_CORPUS_EXPECTATIONS,
    )
    assert res["status"] == "PASS"


@pytest.mark.real_corpus_gated
@pytest.mark.skipif(
    not is_real_corpus_stub01_05_authorized(requested_stub_id="STUB-04"),
    reason=REAL_CORPUS_STUB01_05_GATE_REASON,
)
def test_gated_real_corpus_fx04_c1_token_ceiling() -> None:
    """FX-04: Verify 100% of C1 chunks on 137 Arm P docs have <=128 tokens and 0 coverage loss."""
    res = execute_stub04_fx04_c1_token_ceiling(
        annex_v0_2_2_path=Path(os.environ.get("W07_APPROVED_ANNEX_V022_PATH", str(ARCHIVED_ANNEX_V022_PATH))),
        tech_freeze_receipt_path=Path(os.environ.get("W07_TECH_FREEZE_RECEIPT_PATH", str(ARCHIVED_RECEIPT_V022_PATH))),
        stub_auth_receipt_path=Path(os.environ["W07_STUB01_05_AUTH_RECEIPT_PATH"]),
        corpus_bundle_manifest_path=Path(os.environ["W07_STUB01_05_BUNDLE_MANIFEST_PATH"]),
        expectations=LIVE_137_CORPUS_EXPECTATIONS,
    )
    assert res["status"] == "PASS"


@pytest.mark.real_corpus_gated
@pytest.mark.skipif(
    not is_real_corpus_stub01_05_authorized(requested_stub_id="STUB-05"),
    reason=REAL_CORPUS_STUB01_05_GATE_REASON,
)
def test_gated_real_corpus_fx05_overture_visibility() -> None:
    """FX-05: Verify w07-b1b-doc-overture-f0d424bd-e55bab3c SYNTHETIC_HEADER & 4-family straddle C_vis."""
    res = execute_stub05_fx05_overture_visibility(
        annex_v0_2_2_path=Path(os.environ.get("W07_APPROVED_ANNEX_V022_PATH", str(ARCHIVED_ANNEX_V022_PATH))),
        tech_freeze_receipt_path=Path(os.environ.get("W07_TECH_FREEZE_RECEIPT_PATH", str(ARCHIVED_RECEIPT_V022_PATH))),
        stub_auth_receipt_path=Path(os.environ["W07_STUB01_05_AUTH_RECEIPT_PATH"]),
        corpus_bundle_manifest_path=Path(os.environ["W07_STUB01_05_BUNDLE_MANIFEST_PATH"]),
        expectations=LIVE_137_CORPUS_EXPECTATIONS,
    )
    assert res["status"] == "PASS"
