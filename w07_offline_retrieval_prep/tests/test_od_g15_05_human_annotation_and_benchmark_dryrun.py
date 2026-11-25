"""Tests for OD-G15-05 Human 2+1 annotation workflow and Phase-2 synthetic benchmark dry-run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from run_w07_phase2_benchmark_dryrun import run_phase2_synthetic_dryrun
from prepare_w07_route1b_formal_pack import run_route1b_pack_check
from w07_g4_scorer.contracts import assert_g4_package_zero_ml_imports, load_external_qrels
from w07_g4_scorer.human_annotation import (
    build_adjudication_queue,
    compile_adjudicated_qrels,
    load_and_verify_blind_packet_rows,
    prepare_dual_blind_annotator_workbooks,
    validate_formal_route1b_authorization_bundle,
    validate_human_roster_receipt,
    validate_single_annotator_submissions,
)

PREP_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROSTER_PATH = (
    PREP_ROOT / "docs" / "W07_OD_G15_05_HUMAN_ROSTER_RECEIPT_TEMPLATE_V1.json"
)
ROUTE1B_BUNDLE_TEMPLATE_PATH = (
    PREP_ROOT / "docs" / "W07_ROUTE_1B_FORMAL_APPROVAL_BUNDLE_TEMPLATE_V1.json"
)


def _sample_packet_and_roster() -> tuple[list[dict[str, str]], dict[str, str], dict[str, list[tuple[int, int]]]]:
    s_doc1 = "Hồ Hoàn Kiếm mở cửa cả ngày phục vụ người dân. [CORROBORATED: osm:node/101]\nThông tin bổ sung."
    s_doc2 = "Bãi biển Mỹ Khê nằm ở Đà Nẵng, miễn phí vào cửa và không có vé VIP ban đêm."
    tag_s = s_doc1.index("[CORROBORATED:")
    tag_e = s_doc1.index("]") + 1

    packet = [
        {
            "packet_item_uuid": "uuid_item_1",
            "query_id": "synq_1",
            "query_text": "Hồ Hoàn Kiếm mở cửa khi nào?",
            "document_id": "doc_1",
            "source_type": "overture_b1b_synthetic",
            "language": "vi",
            "canonical_text_S": s_doc1,
        },
        {
            "packet_item_uuid": "uuid_item_2",
            "query_id": "synq_2",
            "query_text": "Vé VIP ban đêm ở bãi biển Mỹ Khê giá bao nhiêu?",
            "document_id": "doc_2",
            "source_type": "osm_synthetic",
            "language": "vi",
            "canonical_text_S": s_doc2,
        },
    ]
    roster = {
        "schema_version": "GOMATE_W07_OD_G15_05_HUMAN_ROSTER_RECEIPT_V1",
        "roster_status": "COMMITTED_BY_OWNER",
        "od_g15_05_route": "ROUTE_1B_POOLED_2PLUS1_HUMAN_OPTION_B",
        "human_annotator_01_id": "ANNOTATOR_ALPHA",
        "human_annotator_02_id": "ANNOTATOR_BETA",
        "human_adjudicator_03_id": "ADJUDICATOR_GAMMA",
        "roster_identity_commitment_sha256": hashlib.sha256(b"committed-2plus1").hexdigest(),
    }
    rem = {"doc_1": [(tag_s, tag_e)], "doc_2": []}
    return packet, roster, rem


def test_g4_zero_ml_import_invariant_and_template_fail_closed() -> None:
    """Adding human_annotation.py preserves zero-ML-import invariant; template blocks formal gate."""
    assert_g4_package_zero_ml_imports()
    assert TEMPLATE_ROSTER_PATH.is_file()
    tmpl = json.loads(TEMPLATE_ROSTER_PATH.read_text(encoding="utf-8"))
    validate_human_roster_receipt(tmpl, require_formal_commitment=False)
    with pytest.raises(PermissionError, match="FORMAL_ROSTER_BLOCKED"):
        validate_human_roster_receipt(tmpl, require_formal_commitment=True)


def test_blind_packet_and_human_submission_negative_guards() -> None:
    """Reject ranking leakage, label coercion, bad quotes, R_AUDIT span overlap, missing lure, & conflict."""
    packet, roster, rem = _sample_packet_and_roster()

    # 1. Ranking/cell leak rejected
    leaked = [dict(packet[0], rank=1, cell_id="C1-RRF"), packet[1]]
    with pytest.raises(ValueError, match="BLIND_PACKET_LEAKAGE"):
        load_and_verify_blind_packet_rows(leaked)

    # 2. Missing lure on REL_0 rejected
    q1_quote = "Hồ Hoàn Kiếm mở cửa cả ngày phục vụ người dân."
    valid_a = [
        {
            "packet_item_uuid": "uuid_item_1",
            "query_id": "synq_1",
            "document_id": "doc_1",
            "annotator_id": "ANNOTATOR_ALPHA",
            "label": "REL_2",
            "plausible_unsupported_lure": None,
            "evidence_quotes": [
                {"exact_quote": q1_quote, "start_char": 0, "end_char": len(q1_quote)}
            ],
        },
        {
            "packet_item_uuid": "uuid_item_2",
            "query_id": "synq_2",
            "document_id": "doc_2",
            "annotator_id": "ANNOTATOR_ALPHA",
            "label": "REL_0",
            "plausible_unsupported_lure": 1,
            "evidence_quotes": [],
        },
    ]
    bad_no_lure = [valid_a[0], {**valid_a[1], "plausible_unsupported_lure": None}]
    with pytest.raises(ValueError, match="MISSING_OR_INVALID_LURE_ON_REL_0"):
        validate_single_annotator_submissions(
            packet, bad_no_lure, expected_annotator_id="ANNOTATOR_ALPHA", removed_audit_spans_by_doc=rem
        )

    # 3. Evidence quote touching deleted [CORROBORATED: ...] marker rejected
    tag_s, tag_e = rem["doc_1"][0]
    bad_r_audit_quote = packet[0]["canonical_text_S"][tag_s:tag_e]
    bad_r_sub = [
        {
            **valid_a[0],
            "evidence_quotes": [
                {"exact_quote": bad_r_audit_quote, "start_char": tag_s, "end_char": tag_e}
            ],
        },
        valid_a[1],
    ]
    with pytest.raises(ValueError, match="EVIDENCE_SPAN_OVERLAPS_DELETED_R_AUDIT_MARKER"):
        validate_single_annotator_submissions(
            packet, bad_r_sub, expected_annotator_id="ANNOTATOR_ALPHA", removed_audit_spans_by_doc=rem
        )

    # 4. Quote content mismatch rejected
    bad_quote_sub = [
        {
            **valid_a[0],
            "evidence_quotes": [
                {"exact_quote": "Wrong text", "start_char": 0, "end_char": 10}
            ],
        },
        valid_a[1],
    ]
    with pytest.raises(ValueError, match="QUOTE_CANONICAL_S_MISMATCH"):
        validate_single_annotator_submissions(
            packet, bad_quote_sub, expected_annotator_id="ANNOTATOR_ALPHA", removed_audit_spans_by_doc=rem
        )

    # 5. Unresolved disagreement cannot compile qrels
    val_a = validate_single_annotator_submissions(
        packet, valid_a, expected_annotator_id="ANNOTATOR_ALPHA", removed_audit_spans_by_doc=rem
    )
    sub_b = [
        {**valid_a[0], "annotator_id": "ANNOTATOR_BETA", "label": "REL_1"},
        {**valid_a[1], "annotator_id": "ANNOTATOR_BETA", "plausible_unsupported_lure": 0},
    ]
    val_b = validate_single_annotator_submissions(
        packet, sub_b, expected_annotator_id="ANNOTATOR_BETA", removed_audit_spans_by_doc=rem
    )
    queue = build_adjudication_queue(packet, val_a, val_b)
    assert queue["disagreements_count"] == 2
    assert {item["disagreement_reasons"][0] for item in queue["disagreement_items"]} == {
        "GRADE_MISMATCH",
        "LURE_MISMATCH",
    }
    with pytest.raises(ValueError, match="UNRESOLVED_ADJUDICATION_ITEMS"):
        compile_adjudicated_qrels(
            packet_rows_or_path=packet,
            votes_a=val_a,
            votes_b=val_b,
            adjudicator_resolutions=[],
            roster_obj=roster,
            removed_audit_spans_by_doc=rem,
        )


def test_adjudication_and_full_phase2_synthetic_dryrun_end_to_end(tmp_path: Path) -> None:
    """Verify full synthetic 50-query 2x3 -> blind 2+1 human adjudication -> decoupled G4 scorer."""
    out_dir = tmp_path / "phase2_dryrun_out"
    summary = run_phase2_synthetic_dryrun(out_dir)

    assert summary["status"] == "SYNTHETIC_PHASE2_DRYRUN_PASS"
    assert summary["matrix_summary"]["q_ans_count"] == 40
    assert summary["matrix_summary"]["q_unans_count"] == 10
    assert summary["g4_epistemic_tier"] == "HUMAN_ADJUDICATED_QRELS"
    assert summary["g4_g5_status"] == "HOLD"
    assert summary["cert_all_ready"] is True
    assert summary["adjudication_stats"]["disagreements_resolved"] > 0
    assert summary["adjudication_stats"]["pre_adjudication_kappa_w_shared_012"] is not None
    assert sorted(summary["g4_cells_scored"]) == [
        "C0-BM25",
        "C0-Dense",
        "C0-RRF",
        "C1-BM25",
        "C1-Dense",
        "C1-RRF",
    ]

    qrels_p = out_dir / "03_od_g15_05_human_2plus1" / "qrels_v1.jsonl"
    loaded_qrels = load_external_qrels(qrels_p)
    assert len(loaded_qrels) == summary["blind_packet_rows"]

    scorecard = json.loads(Path(summary["scorecard_path"]).read_text(encoding="utf-8"))
    assert scorecard["g5_status"] == "HOLD"
    assert scorecard["headline_status"] == "NO_EXACT_FULL_SET_ESTIMATE"
    assert scorecard["certificates"]["cert1_pass_rate"] == pytest.approx(1.0)
    assert scorecard["certificates"]["cert2_pass_rate"] == pytest.approx(1.0)
    assert 0.0 < scorecard["certificates"]["cert3_pass_rate"] <= 1.0
    assert len(scorecard["contrasts_k1_to_k5"]) == 5
    assert summary["synthetic_mode_disclosure"]["execution_classification"] == "SYNTHETIC_PREP_ONLY"
    assert summary["synthetic_mode_disclosure"]["not_formal_ground_truth"] is True
    assert summary["synthetic_mode_disclosure"]["od_g15_05_hold_unchanged"] is True

    # Method Amendment 01 v0.3.1 Section 4: annotator workbooks must never expose pre_rank_answerability
    wb1 = json.loads(
        (out_dir / "03_od_g15_05_human_2plus1" / "annotator_01_blind_workbook.json").read_text(
            encoding="utf-8"
        )
    )
    assert wb1["anti_leakage_attestation"]["pre_rank_answerability_withheld"] is True
    for task in wb1["tasks"]:
        assert "pre_rank_answerability" not in task
        assert "pre_rank_answerability_hint" not in task


def test_route1b_formal_authorization_bundle_fail_closed_and_positive() -> None:
    """Verify Route 1B bundle blocks unsigned/synthetic inputs and accepts complete signoff."""
    assert ROUTE1B_BUNDLE_TEMPLATE_PATH.is_file()
    tmpl = json.loads(ROUTE1B_BUNDLE_TEMPLATE_PATH.read_text(encoding="utf-8"))

    # Template validates cleanly in non-formal template-check mode and reports synthetic disclosure
    non_formal = validate_formal_route1b_authorization_bundle(
        tmpl, require_formal_execution=False
    )
    assert non_formal["formal_execution_authorized"] is False
    assert non_formal["execution_classification"] == "SYNTHETIC_PREP_ONLY"

    # Must block formal execution while template/unsigned/uncommitted
    with pytest.raises(PermissionError, match="FORMAL_"):
        validate_formal_route1b_authorization_bundle(tmpl, require_formal_execution=True)

    pack_status = run_route1b_pack_check(
        bundle_path=ROUTE1B_BUNDLE_TEMPLATE_PATH,
        formal_gate=False,
    )
    assert pack_status["status"] == "ROUTE1B_PACK_READY_FORMAL_GATE_HOLD"
    assert pack_status["formal_execution_authorized"] is False
    assert pack_status["immutable_hashes_verified"]["amendment_draft_hash_matches"] is True
    assert pack_status["anchor_repo_status"]["untouched"] is True

    # Build a complete valid mock formal bundle -> must fail on any single missing precondition
    valid_formal = json.loads(json.dumps(tmpl))
    valid_formal["synthetic_mode_disclosure"] = {
        "execution_classification": "FORMAL_ROUTE_1B_REAL_CORPUS",
        "contains_synthetic_data": False,
        "formal_execution_unlocked": True,
    }
    valid_formal["g15_annex"]["activation_status"] = "OWNER_APPROVED_EFFECTIVE"
    valid_formal["method_amendment"]["chatgpt_audit_status"] = "PASS"
    valid_formal["method_amendment"]["activation_status"] = "OWNER_SIGNED_EFFECTIVE"
    valid_formal["method_amendment"]["owner_signature_ref"] = "OWNER_SIG_20261122"
    valid_formal["method_amendment"]["approval_date_ict"] = "2026-11-22"
    valid_formal["human_roster_receipt"] = {
        "schema_version": "GOMATE_W07_OD_G15_05_HUMAN_ROSTER_RECEIPT_V1",
        "roster_status": "COMMITTED_BY_OWNER",
        "od_g15_05_route": "ROUTE_1B_POOLED_2PLUS1_HUMAN_OPTION_B",
        "human_annotator_01_id": "HUMAN_ALPHA_REAL",
        "human_annotator_02_id": "HUMAN_BETA_REAL",
        "human_adjudicator_03_id": "HUMAN_GAMMA_REAL",
        "roster_identity_commitment_sha256": hashlib.sha256(b"real-roster").hexdigest(),
    }
    valid_formal["operational_gates"] = {
        "stub_01_to_05_disposition": "PASS_PERMANENTLY_SEALED_DO_NOT_RERUN",
        "formal_g2a_query_authoring_unlocked": True,
        "formal_g3_benchmark_unlocked": True,
        "formal_g2b_human_grading_unlocked": True,
        "formal_g4_scoring_unlocked": True,
        "g3_code_freeze_git_sha": "a" * 40,
        "g3_no_final_exposure_attested": True,
        "capacity_envelope_max_votes": 3200,
        "g5_status": "HOLD",
        "paid_llm_api_allowed": False,
    }

    verified = validate_formal_route1b_authorization_bundle(
        valid_formal, require_formal_execution=True
    )
    assert verified["formal_execution_authorized"] is True
    assert verified["execution_classification"] == "FORMAL_ROUTE_1B_REAL_CORPUS"

    # Negative: missing ChatGPT PASS fails closed
    no_audit = json.loads(json.dumps(valid_formal))
    no_audit["method_amendment"]["chatgpt_audit_status"] = "PENDING"
    with pytest.raises(PermissionError, match="FORMAL_ROUTE1B_BLOCKED_CHATGPT_AUDIT"):
        validate_formal_route1b_authorization_bundle(no_audit, require_formal_execution=True)

    # Negative: paid API allowance fails closed
    paid_api = json.loads(json.dumps(valid_formal))
    paid_api["operational_gates"]["paid_llm_api_allowed"] = True
    with pytest.raises(PermissionError, match="FORMAL_ROUTE1B_BLOCKED_PAID_API_PROHIBITED"):
        validate_formal_route1b_authorization_bundle(paid_api, require_formal_execution=True)

    # Negative: G5 unlocked fails closed
    g5_open = json.loads(json.dumps(valid_formal))
    g5_open["operational_gates"]["g5_status"] = "OPEN"
    with pytest.raises(PermissionError, match="FORMAL_ROUTE1B_BLOCKED_G5_MUST_REMAIN_HOLD"):
        validate_formal_route1b_authorization_bundle(g5_open, require_formal_execution=True)

    # Negative: synthetic disclosure with formal execution fails closed
    syn_disclosed = json.loads(json.dumps(valid_formal))
    syn_disclosed["synthetic_mode_disclosure"]["contains_synthetic_data"] = True
    with pytest.raises(PermissionError, match="FORMAL_ROUTE1B_BLOCKED_SYNTHETIC_DISCLOSURE"):
        validate_formal_route1b_authorization_bundle(syn_disclosed, require_formal_execution=True)
