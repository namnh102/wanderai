"""Focused unit and regression tests for offline_offset_trial."""

from __future__ import annotations

import copy
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

from fixtures.g4_fixtures import make_query_dict
from w07_g4_scorer.contracts import assert_g4_package_zero_ml_imports
from w07_g4_scorer.offline_offset_trial import (
    collect_ledger_superseded_pairs,
    find_verbatim_occurrences,
    replay_dual_judge_cohort_offline_offset_trial,
    replay_record_with_offline_offset_trial,
    select_current_epoch_attempts,
)
from w07_g4_scorer.route2_aiproxy import build_sanitized_v_cloud_request_payload


def _make_doc_fixture(
    *,
    canonical_s: str,
    sanitized_v: str | None = None,
    v_to_s_segments: list[tuple[int, int, int, int]] | None = None,
    removed_r_audit: list[tuple[int, int]] | None = None,
    city: str = "Hà Nội",
    poi_id: str = "poi-hn-01",
    doc_id: str = "doc-syn-01",
    prompt_order: str = "PROMPT_ORDER_CANONICAL",
    query_meta: dict[str, Any] | None = None,
    run_nonce: str = "0123456789abcdef0123456789abcdef",
) -> dict[str, Any]:
    v_text = sanitized_v if sanitized_v is not None else canonical_s
    v_segs = v_to_s_segments if v_to_s_segments is not None else [(0, len(v_text), 0, len(canonical_s))]
    r_audit = removed_r_audit if removed_r_audit is not None else []
    qmeta = query_meta or make_query_dict(
        query_id="q-syn-01",
        query_text="Địa chỉ và giờ mở cửa của địa điểm tại Hà Nội?",
        target_city=city,
        target_poi_ids=[poi_id],
    )
    pkt_uuid = hashlib.sha256(f"{qmeta['query_id']}::{doc_id}".encode("utf-8")).hexdigest()[:32]
    cid = f"{pkt_uuid}::{prompt_order}"
    wire = build_sanitized_v_cloud_request_payload(
        packet_item_uuid=pkt_uuid,
        query_text=qmeta["query_text"],
        sanitized_text_V=v_text,
        run_nonce=run_nonce,
        prompt_order=prompt_order,
    )
    return {
        "custom_id": cid,
        "packet_item_uuid": pkt_uuid,
        "prompt_order": prompt_order,
        "sanitized_text_V": v_text,
        "doc_canonical_S": canonical_s,
        "doc_v_to_s_segments": v_segs,
        "doc_removed_r_audit": r_audit,
        "doc_meta": {"city": city, "poi_id": poi_id},
        "doc_record_for_leak_check": {"document_id": doc_id, "poi_id": poi_id},
        "query_meta": qmeta,
        "wire": wire,
    }


def _make_attempt_rec(
    *,
    fx: dict[str, Any],
    provider: str = "openai",
    batch_id: str = "batch_active_01",
    attempt_no: int = 1,
    final_for_item: bool = False,
    local_validation: dict[str, Any],
    parsed_response: dict[str, Any] | None = None,
    projected_canonical_response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": "ITEM_ATTEMPT",
        "provider": provider,
        "batch_id": batch_id,
        "attempt_no": attempt_no,
        "custom_id": fx["custom_id"],
        "query_id": fx["query_meta"]["query_id"],
        "document_id": fx["doc_record_for_leak_check"]["document_id"],
        "prompt_order": fx["prompt_order"],
        "local_validation": copy.deepcopy(local_validation),
        "parsed_response": copy.deepcopy(parsed_response),
        "projected_canonical_response": copy.deepcopy(projected_canonical_response),
        "final_for_item": final_for_item,
    }


def test_epoch_and_current_attempt_selection_respects_superseded_and_latest_retry(tmp_path: Path) -> None:
    log_path = tmp_path / "ant_raw_log.jsonl"
    cid_a = "aaaa::PROMPT_ORDER_CANONICAL"
    cid_b = "bbbb::PROMPT_ORDER_CANONICAL"
    rows = [
        {
            "event_type": "ITEM_ATTEMPT",
            "batch_id": "msgbatch_old_sup",
            "attempt_no": 1,
            "custom_id": cid_a,
            "local_validation": {"state": "ERROR", "error_code": "invalid_request_error"},
            "final_for_item": False,
        },
        {
            "event_type": "ITEM_ATTEMPT",
            "batch_id": "msgbatch_old_sup",
            "attempt_no": 1,
            "custom_id": cid_b,
            "local_validation": {"state": "ERROR", "error_code": "invalid_request_error"},
            "final_for_item": False,
        },
        {
            "event_type": "ANTHROPIC_RECOVERY_EPOCH",
            "supersedes_batch_ids": ["msgbatch_old_sup"],
            "recovered_custom_ids": [cid_a, cid_b],
        },
        {
            "event_type": "ITEM_ATTEMPT",
            "batch_id": "msgbatch_rec_p1",
            "attempt_no": 1,
            "custom_id": cid_a,
            "local_validation": {"state": "ERROR", "error_code": "MISSING_QUOTE_OR_OFFSETS"},
            "parsed_response": {"grade": "REL_1", "evidence_quote": "quote a", "char_start": None, "char_end": None},
            "final_for_item": False,
        },
        {
            "event_type": "ITEM_ATTEMPT",
            "batch_id": "msgbatch_rec_p1",
            "attempt_no": 1,
            "custom_id": cid_b,
            "local_validation": {"state": "REL_0", "error_code": None},
            "final_for_item": True,
        },
        {
            "event_type": "ITEM_ATTEMPT",
            "batch_id": "msgbatch_rec_retry1",
            "attempt_no": 2,
            "custom_id": cid_a,
            "local_validation": {"state": "ERROR", "error_code": "MALFORMED_JSON_OUTPUT:EMPTY_RESPONSE_TEXT"},
            "parsed_response": None,
            "final_for_item": True,
        },
    ]
    log_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    ledger = {
        "intents": {
            "k1": {
                "provider": "anthropic",
                "status": "SETTLED",
                "supersedes_batch_ids": ["msgbatch_old_sup"],
                "submitted_custom_ids": [cid_a, cid_b],
            },
            "k_cancelled": {
                "provider": "anthropic",
                "status": "CANCELLED_UNSUBMITTED",
                "supersedes_batch_ids": ["msgbatch_rec_p1"],
                "submitted_custom_ids": [cid_b],
            },
        }
    }
    sup_pairs = collect_ledger_superseded_pairs(ledger, "anthropic")
    sel = select_current_epoch_attempts(log_path, superseded_batch_item_pairs=sup_pairs)
    assert sel["superseded_rows_skipped"] == 2
    assert sel["active_rows_seen"] == 3
    assert sel["current_attempts"][cid_a]["batch_id"] == "msgbatch_rec_retry1"
    assert sel["current_attempts"][cid_a]["attempt_no"] == 2
    assert (
        sel["current_attempts"][cid_a]["local_validation"]["error_code"]
        == "MALFORMED_JSON_OUTPUT:EMPTY_RESPONSE_TEXT"
    )
    assert sel["current_attempts"][cid_b]["local_validation"]["state"] == "REL_0"


def test_vietnamese_unicode_offset_recovery_matches_codepoints_and_projects_canonical_s() -> None:
    text = "Tổng quan: Địa điểm Phở 10 — Phố Hỏa Lò, Hoàn Kiếm, Hà Nội mở cửa 06:30–22:00 hằng ngày."
    quote = "Phố Hỏa Lò, Hoàn Kiếm, Hà Nội"
    assert len(text.encode("utf-8")) > len(text)
    fx = _make_doc_fixture(canonical_s=text)
    sdv = fx["wire"]["safe_doc_v"]
    exact_start = sdv.index(quote)
    exact_end = exact_start + len(quote)

    # Simulate UTF-8 byte-offset / off-by-k drift from cloud judge
    byte_shifted_start = len(sdv[:exact_start].encode("utf-8"))
    byte_shifted_end = byte_shifted_start + len(quote.encode("utf-8"))
    assert byte_shifted_start != exact_start

    rec = _make_attempt_rec(
        fx=fx,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "SAFE_DOC_V_QUOTE_MISMATCH"},
        parsed_response={"grade": "REL_1", "evidence_quote": quote, "char_start": byte_shifted_start, "char_end": byte_shifted_end},
    )
    res = replay_record_with_offline_offset_trial(
        record=rec,
        safe_doc_v=sdv,
        safe_to_v_segments=fx["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx["sanitized_text_V"],
        doc_canonical_S=fx["doc_canonical_S"],
        doc_v_to_s_segments=fx["doc_v_to_s_segments"],
        doc_removed_r_audit=fx["doc_removed_r_audit"],
        doc_meta=fx["doc_meta"],
        query_meta=fx["query_meta"],
    )
    assert res["changed"] is True
    assert res["trial_action"] == "REPAIRED_TO_VALID"
    assert res["after_state"] == "REL_1"
    assert res["computed_safe_doc_v_span"] == [exact_start, exact_end]
    replayed = res["replayed_record"]
    assert replayed["local_validation"]["confirmed_gain"] == 1
    assert replayed["projected_canonical_response"] == {
        "grade": "REL_1",
        "evidence_quote": quote,
        "char_start": exact_start,
        "char_end": exact_end,
    }

    # Strict verbatim rule: NFD quote MUST NOT match NFC text
    nfd_quote = unicodedata.normalize("NFD", quote)
    assert nfd_quote != quote
    rec_nfd = _make_attempt_rec(
        fx=fx,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "SAFE_DOC_V_QUOTE_MISMATCH"},
        parsed_response={"grade": "REL_1", "evidence_quote": nfd_quote, "char_start": 0, "char_end": 10},
    )
    res_nfd = replay_record_with_offline_offset_trial(
        record=rec_nfd,
        safe_doc_v=sdv,
        safe_to_v_segments=fx["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx["sanitized_text_V"],
        doc_canonical_S=fx["doc_canonical_S"],
        doc_v_to_s_segments=fx["doc_v_to_s_segments"],
        doc_removed_r_audit=fx["doc_removed_r_audit"],
        doc_meta=fx["doc_meta"],
        query_meta=fx["query_meta"],
    )
    assert res_nfd["changed"] is False
    assert res_nfd["trial_action"] == "PRESERVED_QUOTE_NOT_FOUND"
    assert res_nfd["replayed_record"]["local_validation"]["state"] == "ERROR"


def test_missing_offsets_unique_quote_recovered_while_empty_quote_preserved() -> None:
    text = "Ngũ Hành Sơn gồm năm ngọn núi đá vôi tại Đà Nẵng và có nhiều hang động lịch sử."
    quote = "Ngũ Hành Sơn gồm năm ngọn núi đá vôi tại Đà Nẵng"
    fx = _make_doc_fixture(canonical_s=text, city="Đà Nẵng", poi_id="poi-dn-01")
    sdv = fx["wire"]["safe_doc_v"]

    rec_missing = _make_attempt_rec(
        fx=fx,
        provider="anthropic",
        attempt_no=2,
        final_for_item=True,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "MISSING_QUOTE_OR_OFFSETS"},
        parsed_response={"grade": "REL_2", "evidence_quote": quote, "char_start": None, "char_end": None},
    )
    res = replay_record_with_offline_offset_trial(
        record=rec_missing,
        safe_doc_v=sdv,
        safe_to_v_segments=fx["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx["sanitized_text_V"],
        doc_canonical_S=fx["doc_canonical_S"],
        doc_v_to_s_segments=fx["doc_v_to_s_segments"],
        doc_removed_r_audit=fx["doc_removed_r_audit"],
        doc_meta=fx["doc_meta"],
        query_meta=fx["query_meta"],
    )
    assert res["changed"] is True
    assert res["trial_action"] == "REPAIRED_TO_VALID"
    assert res["after_state"] == "REL_2"
    assert res["replayed_record"]["local_validation"]["confirmed_gain"] == 3
    assert res["computed_safe_doc_v_span"] == [0, len(quote)]

    # Empty or whitespace quote must NOT be repaired
    for bad_q in ("", "   ", None):
        rec_empty_q = _make_attempt_rec(
            fx=fx,
            local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "MISSING_QUOTE_OR_OFFSETS"},
            parsed_response={"grade": "REL_1", "evidence_quote": bad_q, "char_start": None, "char_end": None},
        )
        res_bad = replay_record_with_offline_offset_trial(
            record=rec_empty_q,
            safe_doc_v=sdv,
            safe_to_v_segments=fx["wire"]["safe_to_v_segments"],
            doc_sanitized_V=fx["sanitized_text_V"],
            doc_canonical_S=fx["doc_canonical_S"],
            doc_v_to_s_segments=fx["doc_v_to_s_segments"],
            doc_removed_r_audit=fx["doc_removed_r_audit"],
            doc_meta=fx["doc_meta"],
            query_meta=fx["query_meta"],
        )
        assert res_bad["changed"] is False
        assert res_bad["trial_action"] == "PRESERVED_EMPTY_OR_MISSING_QUOTE"
        assert res_bad["replayed_record"]["local_validation"]["error_code"] == "MISSING_QUOTE_OR_OFFSETS"


def test_preserves_already_valid_and_exact_offset_records_even_if_quote_repeats() -> None:
    text = "Địa chỉ: 1 Phố Hỏa Lò, Hà Nội. Nhắc lại: Địa chỉ: 1 Phố Hỏa Lò, Hà Nội."
    quote = "Địa chỉ: 1 Phố Hỏa Lò, Hà Nội."
    second_start = text.rindex(quote)
    second_end = second_start + len(quote)
    fx = _make_doc_fixture(canonical_s=text)
    sdv = fx["wire"]["safe_doc_v"]
    assert len(find_verbatim_occurrences(sdv, quote)) == 2

    # Already-valid record pointing at occurrence #2 must remain untouched even though quote repeats
    orig_proj = {"grade": "REL_1", "evidence_quote": quote, "char_start": second_start, "char_end": second_end}
    orig_lv = {"state": "REL_1", "confirmed_gain": 1, "max_admissible_gain": 1, "error_code": None, "flags": []}
    rec_valid = _make_attempt_rec(
        fx=fx,
        final_for_item=True,
        local_validation=orig_lv,
        parsed_response=orig_proj,
        projected_canonical_response=orig_proj,
    )
    res = replay_record_with_offline_offset_trial(
        record=rec_valid,
        safe_doc_v=sdv,
        safe_to_v_segments=fx["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx["sanitized_text_V"],
        doc_canonical_S=fx["doc_canonical_S"],
        doc_v_to_s_segments=fx["doc_v_to_s_segments"],
        doc_removed_r_audit=fx["doc_removed_r_audit"],
        doc_meta=fx["doc_meta"],
        query_meta=fx["query_meta"],
    )
    assert res["changed"] is False
    assert res["trial_action"] == "KEPT_ALREADY_VALID"
    assert res["replayed_record"]["projected_canonical_response"] == orig_proj
    assert res["replayed_record"]["local_validation"] == orig_lv

    # Unique quote with already-exact offsets where a retry pass re-validates cleanly
    uniq_text = "Giờ mở cửa Bảo tàng Đà Nẵng: 08:00 - 17:00 hằng ngày."
    uniq_quote = "08:00 - 17:00 hằng ngày"
    fx_u = _make_doc_fixture(canonical_s=uniq_text, city="Đà Nẵng", poi_id="poi-dn-01")
    u_start = uniq_text.index(uniq_quote)
    u_end = u_start + len(uniq_quote)
    rec_u_valid = _make_attempt_rec(
        fx=fx_u,
        final_for_item=True,
        local_validation={"state": "REL_1", "confirmed_gain": 1, "max_admissible_gain": 1, "error_code": None},
        parsed_response={"grade": "REL_1", "evidence_quote": uniq_quote, "char_start": u_start, "char_end": u_end},
        projected_canonical_response={"grade": "REL_1", "evidence_quote": uniq_quote, "char_start": u_start, "char_end": u_end},
    )
    res_u = replay_record_with_offline_offset_trial(
        record=rec_u_valid,
        safe_doc_v=fx_u["wire"]["safe_doc_v"],
        safe_to_v_segments=fx_u["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx_u["sanitized_text_V"],
        doc_canonical_S=fx_u["doc_canonical_S"],
        doc_v_to_s_segments=fx_u["doc_v_to_s_segments"],
        doc_removed_r_audit=fx_u["doc_removed_r_audit"],
        doc_meta=fx_u["doc_meta"],
        query_meta=fx_u["query_meta"],
    )
    assert res_u["changed"] is False
    assert res_u["trial_action"] == "KEPT_ALREADY_VALID"
    assert res_u["replayed_record"]["projected_canonical_response"]["char_start"] == u_start

    # Exact-offset payload passed through retry path computes identical [u_start, u_end)
    rec_exact_retry = _make_attempt_rec(
        fx=fx_u,
        final_for_item=False,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "SAFE_DOC_V_QUOTE_MISMATCH"},
        parsed_response={"grade": "REL_1", "evidence_quote": uniq_quote, "char_start": u_start, "char_end": u_end},
    )
    res_exact_retry = replay_record_with_offline_offset_trial(
        record=rec_exact_retry,
        safe_doc_v=fx_u["wire"]["safe_doc_v"],
        safe_to_v_segments=fx_u["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx_u["sanitized_text_V"],
        doc_canonical_S=fx_u["doc_canonical_S"],
        doc_v_to_s_segments=fx_u["doc_v_to_s_segments"],
        doc_removed_r_audit=fx_u["doc_removed_r_audit"],
        doc_meta=fx_u["doc_meta"],
        query_meta=fx_u["query_meta"],
    )
    assert res_exact_retry["changed"] is True
    assert res_exact_retry["trial_action"] == "REPAIRED_TO_VALID"
    assert res_exact_retry["computed_safe_doc_v_span"] == [u_start, u_end]


def test_repeated_quote_overlapping_and_disjoint_preserved_as_error() -> None:
    # Case 1: Disjoint repeated quote
    text_disjoint = "Mục A: Chùa Trấn Quốc ở Hồ Tây. Mục B: Chùa Trấn Quốc ở Hồ Tây."
    quote_disjoint = "Chùa Trấn Quốc ở Hồ Tây"
    fx1 = _make_doc_fixture(canonical_s=text_disjoint)
    rec1 = _make_attempt_rec(
        fx=fx1,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "SAFE_DOC_V_QUOTE_MISMATCH"},
        parsed_response={"grade": "REL_1", "evidence_quote": quote_disjoint, "char_start": 0, "char_end": 10},
    )
    res1 = replay_record_with_offline_offset_trial(
        record=rec1,
        safe_doc_v=fx1["wire"]["safe_doc_v"],
        safe_to_v_segments=fx1["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx1["sanitized_text_V"],
        doc_canonical_S=fx1["doc_canonical_S"],
        doc_v_to_s_segments=fx1["doc_v_to_s_segments"],
        doc_removed_r_audit=fx1["doc_removed_r_audit"],
        doc_meta=fx1["doc_meta"],
        query_meta=fx1["query_meta"],
    )
    assert res1["changed"] is False
    assert res1["trial_action"] == "PRESERVED_REPEATED_QUOTE"
    assert res1["quote_occurrence_count"] == 2
    assert res1["replayed_record"]["local_validation"]["state"] == "ERROR"
    assert res1["replayed_record"]["local_validation"]["error_code"] == "SAFE_DOC_V_QUOTE_MISMATCH"

    # Case 2: Overlapping repeated substring ("ha ha ha" / "ababab")
    text_overlap = "Điểm nổi bật: ababab tại khu vực trung tâm."
    quote_overlap = "abab"
    assert find_verbatim_occurrences(text_overlap, quote_overlap) == [14, 16]
    fx2 = _make_doc_fixture(canonical_s=text_overlap)
    rec2 = _make_attempt_rec(
        fx=fx2,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "MISSING_QUOTE_OR_OFFSETS"},
        parsed_response={"grade": "REL_1", "evidence_quote": quote_overlap, "char_start": None, "char_end": None},
    )
    res2 = replay_record_with_offline_offset_trial(
        record=rec2,
        safe_doc_v=fx2["wire"]["safe_doc_v"],
        safe_to_v_segments=fx2["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx2["sanitized_text_V"],
        doc_canonical_S=fx2["doc_canonical_S"],
        doc_v_to_s_segments=fx2["doc_v_to_s_segments"],
        doc_removed_r_audit=fx2["doc_removed_r_audit"],
        doc_meta=fx2["doc_meta"],
        query_meta=fx2["query_meta"],
    )
    assert res2["changed"] is False
    assert res2["trial_action"] == "PRESERVED_REPEATED_QUOTE"
    assert res2["quote_occurrence_count"] == 2


def test_preserves_quote_not_found_empty_text_and_http_503() -> None:
    fx = _make_doc_fixture(canonical_s="Bảo tàng Lịch sử nằm tại trung tâm thành phố Hà Nội.")
    sdv = fx["wire"]["safe_doc_v"]

    # 1. Quote not found
    rec_absent = _make_attempt_rec(
        fx=fx,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "SAFE_DOC_V_QUOTE_MISMATCH"},
        parsed_response={"grade": "REL_1", "evidence_quote": "Chuỗi không tồn tại trong tài liệu", "char_start": 0, "char_end": 12},
    )
    res_absent = replay_record_with_offline_offset_trial(
        record=rec_absent,
        safe_doc_v=sdv,
        safe_to_v_segments=fx["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx["sanitized_text_V"],
        doc_canonical_S=fx["doc_canonical_S"],
        doc_v_to_s_segments=fx["doc_v_to_s_segments"],
        doc_removed_r_audit=fx["doc_removed_r_audit"],
        doc_meta=fx["doc_meta"],
        query_meta=fx["query_meta"],
    )
    assert res_absent["changed"] is False
    assert res_absent["trial_action"] == "PRESERVED_QUOTE_NOT_FOUND"
    assert res_absent["replayed_record"]["local_validation"]["error_code"] == "SAFE_DOC_V_QUOTE_MISMATCH"

    # 2. Empty response text
    rec_empty = _make_attempt_rec(
        fx=fx,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "MALFORMED_JSON_OUTPUT:EMPTY_RESPONSE_TEXT"},
        parsed_response=None,
    )
    res_empty = replay_record_with_offline_offset_trial(
        record=rec_empty,
        safe_doc_v=sdv,
        safe_to_v_segments=fx["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx["sanitized_text_V"],
        doc_canonical_S=fx["doc_canonical_S"],
        doc_v_to_s_segments=fx["doc_v_to_s_segments"],
        doc_removed_r_audit=fx["doc_removed_r_audit"],
        doc_meta=fx["doc_meta"],
        query_meta=fx["query_meta"],
    )
    assert res_empty["changed"] is False
    assert res_empty["trial_action"] == "PRESERVED_EMPTY_RESPONSE_TEXT"
    assert res_empty["replayed_record"]["local_validation"]["error_code"] == "MALFORMED_JSON_OUTPUT:EMPTY_RESPONSE_TEXT"

    # 3. HTTP 503
    err_503 = "{'status_code': 503, 'body': {'error': {'code': 'server_is_overloaded', 'type': 'service_unavailable_error'}}}"
    rec_503 = _make_attempt_rec(
        fx=fx,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": err_503},
        parsed_response=None,
    )
    res_503 = replay_record_with_offline_offset_trial(
        record=rec_503,
        safe_doc_v=sdv,
        safe_to_v_segments=fx["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx["sanitized_text_V"],
        doc_canonical_S=fx["doc_canonical_S"],
        doc_v_to_s_segments=fx["doc_v_to_s_segments"],
        doc_removed_r_audit=fx["doc_removed_r_audit"],
        doc_meta=fx["doc_meta"],
        query_meta=fx["query_meta"],
        outcome_item={"provider_error": {"status_code": 503}},
    )
    assert res_503["changed"] is False
    assert res_503["trial_action"] == "PRESERVED_HTTP_503"
    assert res_503["replayed_record"]["local_validation"]["error_code"] == err_503


def test_unique_quote_match_succeeds_but_fails_downstream_projection_or_gates() -> None:
    # A. Quote uniquely matches in safe_doc_v, but straddles [REDACTED_EMAIL] -> SPAN_STRADDLES_ESCAPED_DELIMITER
    v_with_email = "Liên hệ quầy vé: info@museum.example.vn hằng ngày từ 08:00."
    fx_a = _make_doc_fixture(canonical_s=v_with_email, sanitized_v=v_with_email)
    sdv_a = fx_a["wire"]["safe_doc_v"]
    assert "[REDACTED_EMAIL]" in sdv_a
    straddle_q_a = "quầy vé: [REDACTED_EMAIL] hằng ngày"
    assert find_verbatim_occurrences(sdv_a, straddle_q_a) == [sdv_a.index(straddle_q_a)]

    rec_a = _make_attempt_rec(
        fx=fx_a,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "MISSING_QUOTE_OR_OFFSETS"},
        parsed_response={"grade": "REL_1", "evidence_quote": straddle_q_a, "char_start": None, "char_end": None},
    )
    res_a = replay_record_with_offline_offset_trial(
        record=rec_a,
        safe_doc_v=sdv_a,
        safe_to_v_segments=fx_a["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx_a["sanitized_text_V"],
        doc_canonical_S=fx_a["doc_canonical_S"],
        doc_v_to_s_segments=fx_a["doc_v_to_s_segments"],
        doc_removed_r_audit=fx_a["doc_removed_r_audit"],
        doc_meta=fx_a["doc_meta"],
        query_meta=fx_a["query_meta"],
    )
    assert res_a["changed"] is False
    assert res_a["trial_action"] == "QUOTE_MATCHED_DOWNSTREAM_FAILED"
    assert res_a["after_state"] == "ERROR"
    assert res_a["after_error_code"] == "SPAN_STRADDLES_ESCAPED_DELIMITER"
    assert res_a["replayed_record"]["local_validation"]["confirmed_gain"] == 0

    # B. Quote uniquely matches in safe_doc_v and projects to V, but straddles excised R_AUDIT span in V -> S
    prefix_s = "Đoạn đầu mô tả "
    excised_s = "[R_AUDIT]nội dung kiểm tra[/R_AUDIT]"
    suffix_s = " giờ mở cửa 08:00."
    canon_s_b = prefix_s + excised_s + suffix_s
    sanitized_v_b = prefix_s + suffix_s
    # Map sanitized_V [0:len(prefix_s)] -> S [0:len(prefix_s)], and [len(prefix_s):] -> S [len(prefix_s)+len(excised_s):]
    v_to_s_b = [
        (0, len(prefix_s), 0, len(prefix_s)),
        (len(prefix_s), len(sanitized_v_b), len(prefix_s) + len(excised_s), len(canon_s_b)),
    ]
    r_audit_b = [(len(prefix_s), len(prefix_s) + len(excised_s))]
    fx_b = _make_doc_fixture(
        canonical_s=canon_s_b,
        sanitized_v=sanitized_v_b,
        v_to_s_segments=v_to_s_b,
        removed_r_audit=r_audit_b,
    )
    sdv_b = fx_b["wire"]["safe_doc_v"]
    straddle_q_b = "mô tả  giờ mở cửa"
    assert len(find_verbatim_occurrences(sdv_b, straddle_q_b)) == 1
    rec_b = _make_attempt_rec(
        fx=fx_b,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "SAFE_DOC_V_QUOTE_MISMATCH"},
        parsed_response={"grade": "REL_1", "evidence_quote": straddle_q_b, "char_start": 0, "char_end": 5},
    )
    res_b = replay_record_with_offline_offset_trial(
        record=rec_b,
        safe_doc_v=sdv_b,
        safe_to_v_segments=fx_b["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx_b["sanitized_text_V"],
        doc_canonical_S=fx_b["doc_canonical_S"],
        doc_v_to_s_segments=fx_b["doc_v_to_s_segments"],
        doc_removed_r_audit=fx_b["doc_removed_r_audit"],
        doc_meta=fx_b["doc_meta"],
        query_meta=fx_b["query_meta"],
    )
    assert res_b["changed"] is False
    assert res_b["trial_action"] == "QUOTE_MATCHED_DOWNSTREAM_FAILED"
    assert res_b["after_state"] == "ERROR"
    assert res_b["after_error_code"] == "SPAN_STRADDLES_EXCISED_R_AUDIT_TAG"
    assert res_b["replayed_record"]["local_validation"]["confirmed_gain"] == 0

    # C. Quote uniquely matches & projects V->S cleanly, yet fails CE9 non-target POI gate downstream
    wrong_poi_q = make_query_dict(
        query_id="q-ce9",
        query_text="Giờ mở cửa của địa điểm poi-hn-01?",
        target_city="Hà Nội",
        target_poi_ids=["poi-hn-01"],
    )
    ce9_text = "Địa điểm khác mở cửa 09:00 hằng ngày."
    fx_c = _make_doc_fixture(canonical_s=ce9_text, city="Hà Nội", poi_id="poi-hn-99", query_meta=wrong_poi_q)
    rec_c = _make_attempt_rec(
        fx=fx_c,
        local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "SAFE_DOC_V_QUOTE_MISMATCH"},
        parsed_response={"grade": "REL_1", "evidence_quote": ce9_text, "char_start": 1, "char_end": 5},
    )
    res_c = replay_record_with_offline_offset_trial(
        record=rec_c,
        safe_doc_v=fx_c["wire"]["safe_doc_v"],
        safe_to_v_segments=fx_c["wire"]["safe_to_v_segments"],
        doc_sanitized_V=fx_c["sanitized_text_V"],
        doc_canonical_S=fx_c["doc_canonical_S"],
        doc_v_to_s_segments=fx_c["doc_v_to_s_segments"],
        doc_removed_r_audit=fx_c["doc_removed_r_audit"],
        doc_meta=fx_c["doc_meta"],
        query_meta=fx_c["query_meta"],
    )
    assert res_c["changed"] is False
    assert res_c["trial_action"] == "QUOTE_MATCHED_DOWNSTREAM_FAILED"
    assert res_c["after_state"] == "ERROR"
    assert res_c["after_error_code"] == "SAFETY_BLOCK_NON_TARGET_POI_CE9"
    assert res_c["replayed_record"]["local_validation"]["max_admissible_gain"] == 0


def test_dual_judge_cohort_replay_summary_and_zero_ml_imports() -> None:
    assert_g4_package_zero_ml_imports()

    fx_canon = _make_doc_fixture(
        canonical_s="Địa điểm Phở 10 ở Hà Nội mở cửa 06:30 mỗi sáng.",
        doc_id="d1",
        prompt_order="PROMPT_ORDER_CANONICAL",
    )
    fx_swap = _make_doc_fixture(
        canonical_s="Địa điểm Phở 10 ở Hà Nội mở cửa 06:30 mỗi sáng.",
        doc_id="d1",
        prompt_order="PROMPT_ORDER_SWAPPED",
    )
    q_txt = "Địa điểm Phở 10 ở Hà Nội"
    items = [fx_canon, fx_swap]
    wire_ctx = {
        ("openai", fx_canon["custom_id"]): fx_canon["wire"],
        ("anthropic", fx_canon["custom_id"]): fx_canon["wire"],
        ("openai", fx_swap["custom_id"]): fx_swap["wire"],
        ("anthropic", fx_swap["custom_id"]): fx_swap["wire"],
    }
    oai_att = {
        fx_canon["custom_id"]: _make_attempt_rec(
            fx=fx_canon,
            local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "SAFE_DOC_V_QUOTE_MISMATCH"},
            parsed_response={"grade": "REL_1", "evidence_quote": q_txt, "char_start": 1, "char_end": 10},
        ),
        fx_swap["custom_id"]: _make_attempt_rec(
            fx=fx_swap,
            final_for_item=True,
            local_validation={"state": "REL_0", "confirmed_gain": 0, "max_admissible_gain": 0, "error_code": None},
            parsed_response={"grade": "REL_0", "evidence_quote": None, "char_start": None, "char_end": None},
            projected_canonical_response={"grade": "REL_0", "evidence_quote": None, "char_start": None, "char_end": None},
        ),
    }
    ant_att = {
        fx_canon["custom_id"]: _make_attempt_rec(
            fx=fx_canon,
            provider="anthropic",
            final_for_item=True,
            local_validation={"state": "REL_1", "confirmed_gain": 1, "max_admissible_gain": 1, "error_code": None},
            parsed_response={"grade": "REL_1", "evidence_quote": q_txt, "char_start": 0, "char_end": len(q_txt)},
            projected_canonical_response={"grade": "REL_1", "evidence_quote": q_txt, "char_start": 0, "char_end": len(q_txt)},
        ),
        fx_swap["custom_id"]: _make_attempt_rec(
            fx=fx_swap,
            provider="anthropic",
            final_for_item=True,
            local_validation={"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "MISSING_QUOTE_OR_OFFSETS"},
            parsed_response={"grade": "REL_2", "evidence_quote": q_txt, "char_start": None, "char_end": None},
        ),
    }

    replay = replay_dual_judge_cohort_offline_offset_trial(
        items=items,
        openai_attempts_by_cid=oai_att,
        anthropic_attempts_by_cid=ant_att,
        wire_context_by_prov_cid=wire_ctx,
    )
    assert replay["before_summary"]["total"]["both_valid"] == 0
    assert replay["after_summary"]["canonical"]["both_valid"] == 1
    assert replay["after_summary"]["swapped"]["both_valid"] == 1
    assert replay["after_summary"]["total"]["both_valid"] == 2
    assert replay["deltas"]["canonical"]["both_valid_delta"] == 1
    assert replay["deltas"]["swapped"]["both_valid_delta"] == 1
