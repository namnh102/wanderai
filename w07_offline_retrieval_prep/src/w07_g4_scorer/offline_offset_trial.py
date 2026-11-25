"""Offline-only trial helper for verbatim unique-quote offset recovery and epoch replay.

This module provides a strictly read-only, non-live offline diagnostic pipeline
for route2 batch judge logs. It never sends network requests, never writes to
live logs or budget ledgers, and keeps all trial outputs strictly separated from
authoritative runtime records.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from w07_g4_scorer.judge_gates import (
    ALLOWED_JUDGE_SCHEMA_KEYS,
    evaluate_prompt_order_bias,
    quadratic_weighted_kappa,
    validate_judge_response,
)
from w07_g4_scorer.query_manifest import validate_sealed_query_metadata
from w07_g4_scorer.route2_aiproxy import (
    _project_half_open_interval,
    project_cloud_quote_locally_to_canonical_s,
)
from w07_g4_scorer.route2_dev5_live_runner import canonicalize_custom_id

VALID_NON_ERROR_STATES: frozenset[str] = frozenset({"REL_0", "REL_1", "REL_2", "NA"})

OFFSET_REPAIR_ELIGIBLE_ERROR_CODES: frozenset[str] = frozenset(
    {
        "SAFE_DOC_V_QUOTE_MISMATCH",
        "MISSING_QUOTE_OR_OFFSETS",
        "UNVERIFIED_POSITIVE_QUOTE:OFFSET_SUBSTRING_MISMATCH",
        "UNVERIFIED_POSITIVE_QUOTE:OUT_OF_RANGE_OFFSET",
        "NON_INTEGER_OFFSET_TYPE",
        "BOOLEAN_OFFSET_FORBIDDEN",
    }
)

EMPTY_RESPONSE_TEXT_ERROR_CODE = "MALFORMED_JSON_OUTPUT:EMPTY_RESPONSE_TEXT"


def collect_ledger_superseded_pairs(ledger: Mapping[str, Any], provider: str) -> list[tuple[str, str]]:
    """Collect (old_batch_id, canonical_custom_id) pairs superseded by active recovery intents."""
    pairs: list[tuple[str, str]] = []
    for ent in (ledger.get("intents") or {}).values():
        if ent.get("provider") != provider or ent.get("status") == "CANCELLED_UNSUBMITTED":
            continue
        sup_bids = ent.get("supersedes_batch_ids") or []
        sub_cids = ent.get("submitted_custom_ids") or ent.get("custom_ids") or []
        if sup_bids and sub_cids:
            for old_bid in sup_bids:
                for raw_cid in sub_cids:
                    pairs.append((str(old_bid), canonicalize_custom_id(str(raw_cid))))
    return pairs


def select_current_epoch_attempts(
    log_records: Sequence[Mapping[str, Any]] | Path,
    *,
    superseded_batch_ids: Sequence[str] = (),
    superseded_batch_item_pairs: Sequence[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Select the current active epoch and latest active attempt per custom_id.

    Follows the same precedence rules as the runner log index:
    1. All ``ANTHROPIC_RECOVERY_EPOCH`` records mark old batch IDs (or specific
       ``(batch_id, canonical_custom_id)`` pairs when ``recovered_custom_ids``
       is present) as superseded.
    2. Only non-superseded ``ITEM_ATTEMPT`` rows enter the active epoch.
    3. For each ``canonical_custom_id``, the latest active attempt by
       ``(attempt_no, chronological_index)`` is selected regardless of whether
       ``final_for_item`` is True or pending retry.
    """
    if isinstance(log_records, Path):
        rows: list[Mapping[str, Any]] = [
            json.loads(line)
            for line in log_records.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        rows = list(log_records)

    sup_batches: set[str] = {str(b) for b in superseded_batch_ids if b}
    sup_pairs: set[tuple[str, str]] = {
        (str(b), canonicalize_custom_id(str(c)))
        for b, c in superseded_batch_item_pairs
        if b and c
    }

    item_rows: list[Mapping[str, Any]] = []
    for rec in rows:
        ev_type = rec.get("event_type")
        if ev_type == "ANTHROPIC_RECOVERY_EPOCH":
            sbids = list(rec.get("supersedes_batch_ids") or [])
            if not sbids and rec.get("supersedes_batch_id"):
                sbids = [rec["supersedes_batch_id"]]
            rcids = rec.get("recovered_custom_ids")
            if isinstance(rcids, list) and rcids:
                for sb in sbids:
                    for cid_raw in rcids:
                        sup_pairs.add((str(sb), canonicalize_custom_id(str(cid_raw))))
            else:
                for sb in sbids:
                    sup_batches.add(str(sb))
            continue
        if ev_type == "ITEM_ATTEMPT":
            item_rows.append(rec)

    current_by_cid: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}
    attempt_counts: dict[str, int] = {}
    superseded_rows_skipped = 0
    active_rows_seen = 0

    for idx, rec in enumerate(item_rows):
        cid = canonicalize_custom_id(str(rec["custom_id"]))
        batch_id = str(rec.get("batch_id") or "")
        if batch_id in sup_batches or (batch_id, cid) in sup_pairs:
            superseded_rows_skipped += 1
            continue
        active_rows_seen += 1
        attempt_counts[cid] = attempt_counts.get(cid, 0) + 1
        raw_att = rec.get("attempt_no")
        att_no = raw_att if type(raw_att) is int and raw_att >= 1 else 1
        sort_key = (att_no, idx)
        prev = current_by_cid.get(cid)
        if prev is None or sort_key >= prev[0]:
            current_by_cid[cid] = (sort_key, copy.deepcopy(dict(rec)))

    return {
        "current_attempts": {cid: pair[1] for cid, pair in current_by_cid.items()},
        "attempt_counts": attempt_counts,
        "active_rows_seen": active_rows_seen,
        "superseded_rows_skipped": superseded_rows_skipped,
        "superseded_batches": sorted(sup_batches),
        "superseded_pairs_count": len(sup_pairs),
    }


def find_verbatim_occurrences(safe_doc_v: str, quote: str) -> list[int]:
    """Find every verbatim start codepoint index of ``quote`` in ``safe_doc_v`` (overlap-safe)."""
    if type(safe_doc_v) is not str or type(quote) is not str or quote == "":
        return []
    starts: list[int] = []
    pos = safe_doc_v.find(quote)
    while pos != -1:
        starts.append(pos)
        pos = safe_doc_v.find(quote, pos + 1)
    return starts


def _is_http_503_error(error_code: str, outcome_item: Mapping[str, Any] | None) -> bool:
    if isinstance(outcome_item, Mapping):
        pe = outcome_item.get("provider_error")
        if isinstance(pe, Mapping) and pe.get("status_code") == 503:
            return True
        if isinstance(pe, str) and "503" in pe and "server_is_overloaded" in pe:
            return True
    return "503" in error_code and ("server_is_overloaded" in error_code or "service_unavailable_error" in error_code)


def _norm_preserved_error_bucket(error_code: str, outcome_item: Mapping[str, Any] | None) -> str:
    if _is_http_503_error(error_code, outcome_item):
        return "HTTP_503_SERVER_OVERLOADED"
    if error_code == EMPTY_RESPONSE_TEXT_ERROR_CODE:
        return "EMPTY_RESPONSE_TEXT"
    return error_code


def _extract_parsed_response(
    record: Mapping[str, Any],
    outcome_item: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    pr = record.get("parsed_response")
    if isinstance(pr, Mapping):
        return pr
    if isinstance(outcome_item, Mapping) and isinstance(outcome_item.get("parsed_response"), Mapping):
        return outcome_item["parsed_response"]
    return None


def _compute_canonical_projection(
    *,
    parsed_resp: Mapping[str, Any],
    local_val: Mapping[str, Any],
    safe_to_v_segments: Sequence[tuple[int, int, int, int]],
    doc_v_to_s_segments: Sequence[tuple[int, int, int, int]],
) -> dict[str, Any] | None:
    state = str(local_val.get("state") or "ERROR")
    if state in ("REL_0", "NA"):
        return {"grade": state, "evidence_quote": None, "char_start": None, "char_end": None}
    if state not in ("REL_1", "REL_2"):
        return None
    v_span = _project_half_open_interval(
        int(parsed_resp["char_start"]),
        int(parsed_resp["char_end"]),
        safe_to_v_segments,
    )
    if v_span is None:
        return None
    s_span = _project_half_open_interval(v_span[0], v_span[1], doc_v_to_s_segments)
    if s_span is None:
        return None
    return {
        "grade": state,
        "evidence_quote": str(parsed_resp["evidence_quote"]),
        "char_start": s_span[0],
        "char_end": s_span[1],
    }


def _run_full_validator_chain(
    *,
    repaired_cloud_response: Mapping[str, Any],
    safe_doc_v: str,
    safe_to_v_segments: Sequence[tuple[int, int, int, int]],
    doc_sanitized_V: str,
    doc_canonical_S: str,
    doc_v_to_s_segments: Sequence[tuple[int, int, int, int]],
    doc_removed_r_audit: Sequence[tuple[int, int]],
    doc_meta: Mapping[str, Any],
    query_meta: Mapping[str, Any],
    approved_pois_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run extra-key/rationale checks plus full local projection and G-SPAN/CE9/CE4 gates."""
    if approved_pois_by_id is not None:
        meta_invalid = validate_sealed_query_metadata(dict(query_meta), approved_pois_by_id=approved_pois_by_id)
        if meta_invalid is not None:
            return meta_invalid

    extra_keys = set(repaired_cloud_response.keys()) - ALLOWED_JUDGE_SCHEMA_KEYS
    if extra_keys:
        return {
            "state": "ERROR",
            "confirmed_gain": 0,
            "max_admissible_gain": 3,
            "error_code": "UNEXPECTED_EXTRA_SCHEMA_KEYS",
        }
    if (
        "rationale" in repaired_cloud_response
        and repaired_cloud_response["rationale"] is not None
        and type(repaired_cloud_response["rationale"]) is not str
    ):
        return {
            "state": "ERROR",
            "confirmed_gain": 0,
            "max_admissible_gain": 3,
            "error_code": "INVALID_RATIONALE_TYPE",
        }

    proj_val = project_cloud_quote_locally_to_canonical_s(
        cloud_response=repaired_cloud_response,
        safe_doc_v=safe_doc_v,
        safe_to_v_segments=safe_to_v_segments,
        doc_sanitized_V=doc_sanitized_V,
        doc_canonical_S=doc_canonical_S,
        doc_v_to_s_segments=doc_v_to_s_segments,
        doc_removed_r_audit=doc_removed_r_audit,
        doc_meta=doc_meta,
        query_meta=query_meta,
    )
    if approved_pois_by_id is not None and proj_val.get("state") in ("REL_1", "REL_2"):
        v_span = _project_half_open_interval(
            int(repaired_cloud_response["char_start"]),
            int(repaired_cloud_response["char_end"]),
            safe_to_v_segments,
        )
        assert v_span is not None
        s_span = _project_half_open_interval(v_span[0], v_span[1], doc_v_to_s_segments)
        assert s_span is not None
        canonical_payload = {
            "grade": proj_val["state"],
            "evidence_quote": repaired_cloud_response["evidence_quote"],
            "char_start": s_span[0],
            "char_end": s_span[1],
        }
        return validate_judge_response(
            json.dumps(canonical_payload, ensure_ascii=False),
            {
                "canonical_text_S": doc_canonical_S,
                "city": doc_meta.get("city"),
                "poi_id": doc_meta.get("poi_id"),
            },
            list(doc_removed_r_audit),
            dict(query_meta),
            approved_pois_by_id=approved_pois_by_id,
        )
    return proj_val


def replay_record_with_offline_offset_trial(
    *,
    record: Mapping[str, Any],
    safe_doc_v: str,
    safe_to_v_segments: Sequence[tuple[int, int, int, int]],
    doc_sanitized_V: str,
    doc_canonical_S: str,
    doc_v_to_s_segments: Sequence[tuple[int, int, int, int]],
    doc_removed_r_audit: Sequence[tuple[int, int]],
    doc_meta: Mapping[str, Any],
    query_meta: Mapping[str, Any],
    outcome_item: Mapping[str, Any] | None = None,
    approved_pois_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Apply offline unique-quote Python offset recovery to one active attempt record.

    - Already-valid records are returned completely untouched.
    - Non-offset errors (empty text, HTTP 503, CE9/CE4, straddling spans) keep
      their original error status unchanged.
    - Offset errors are retried strictly when ``evidence_quote`` is non-empty
      and matches verbatim at exactly one codepoint span ``[start, end)`` in
      ``safe_doc_v``, then re-validated through the complete current validator chain.
    """
    out_rec = copy.deepcopy(dict(record))
    lv = dict(out_rec.get("local_validation") or {})
    orig_state = str(lv.get("state") or "ERROR")
    orig_err = "" if orig_state in VALID_NON_ERROR_STATES else str(lv.get("error_code") or "UNKNOWN_ERROR")
    orig_final = bool(out_rec.get("final_for_item", True))

    if orig_state in VALID_NON_ERROR_STATES and orig_final:
        return {
            "replayed_record": out_rec,
            "changed": False,
            "before_state": orig_state,
            "after_state": orig_state,
            "before_error_code": "",
            "after_error_code": "",
            "trial_action": "KEPT_ALREADY_VALID",
            "reason": "ALREADY_VALID_PRESERVED",
            "quote_occurrence_count": None,
            "computed_safe_doc_v_span": None,
        }

    norm_err = _norm_preserved_error_bucket(orig_err, outcome_item)
    if norm_err == "HTTP_503_SERVER_OVERLOADED":
        return {
            "replayed_record": out_rec,
            "changed": False,
            "before_state": orig_state,
            "after_state": orig_state,
            "before_error_code": norm_err,
            "after_error_code": norm_err,
            "trial_action": "PRESERVED_HTTP_503",
            "reason": "HTTP_503_PRESERVED",
            "quote_occurrence_count": None,
            "computed_safe_doc_v_span": None,
        }

    if orig_err == EMPTY_RESPONSE_TEXT_ERROR_CODE:
        return {
            "replayed_record": out_rec,
            "changed": False,
            "before_state": orig_state,
            "after_state": orig_state,
            "before_error_code": orig_err,
            "after_error_code": orig_err,
            "trial_action": "PRESERVED_EMPTY_RESPONSE_TEXT",
            "reason": "EMPTY_RESPONSE_TEXT_PRESERVED",
            "quote_occurrence_count": None,
            "computed_safe_doc_v_span": None,
        }

    if orig_err not in OFFSET_REPAIR_ELIGIBLE_ERROR_CODES:
        return {
            "replayed_record": out_rec,
            "changed": False,
            "before_state": orig_state,
            "after_state": orig_state,
            "before_error_code": orig_err,
            "after_error_code": orig_err,
            "trial_action": "PRESERVED_NON_OFFSET_ERROR",
            "reason": f"NON_OFFSET_ERROR_PRESERVED:{orig_err}",
            "quote_occurrence_count": None,
            "computed_safe_doc_v_span": None,
        }

    parsed_resp = _extract_parsed_response(out_rec, outcome_item)
    if not isinstance(parsed_resp, Mapping):
        return {
            "replayed_record": out_rec,
            "changed": False,
            "before_state": orig_state,
            "after_state": orig_state,
            "before_error_code": orig_err,
            "after_error_code": orig_err,
            "trial_action": "PRESERVED_MISSING_PARSED_RESPONSE",
            "reason": "MISSING_PARSED_RESPONSE_PRESERVED",
            "quote_occurrence_count": None,
            "computed_safe_doc_v_span": None,
        }

    raw_grade = parsed_resp.get("grade")
    if raw_grade not in ("REL_1", "REL_2"):
        return {
            "replayed_record": out_rec,
            "changed": False,
            "before_state": orig_state,
            "after_state": orig_state,
            "before_error_code": orig_err,
            "after_error_code": orig_err,
            "trial_action": "PRESERVED_NON_POSITIVE_RAW_GRADE",
            "reason": f"NON_POSITIVE_RAW_GRADE_PRESERVED:{raw_grade!r}",
            "quote_occurrence_count": None,
            "computed_safe_doc_v_span": None,
        }

    quote = parsed_resp.get("evidence_quote")
    if type(quote) is not str or quote == "" or not quote.strip():
        return {
            "replayed_record": out_rec,
            "changed": False,
            "before_state": orig_state,
            "after_state": orig_state,
            "before_error_code": orig_err,
            "after_error_code": orig_err,
            "trial_action": "PRESERVED_EMPTY_OR_MISSING_QUOTE",
            "reason": "EMPTY_OR_MISSING_QUOTE_PRESERVED",
            "quote_occurrence_count": 0,
            "computed_safe_doc_v_span": None,
        }

    starts = find_verbatim_occurrences(safe_doc_v, quote)
    occ_count = len(starts)
    if occ_count == 0:
        return {
            "replayed_record": out_rec,
            "changed": False,
            "before_state": orig_state,
            "after_state": orig_state,
            "before_error_code": orig_err,
            "after_error_code": orig_err,
            "trial_action": "PRESERVED_QUOTE_NOT_FOUND",
            "reason": "QUOTE_NOT_FOUND_PRESERVED",
            "quote_occurrence_count": 0,
            "computed_safe_doc_v_span": None,
        }
    if occ_count > 1:
        return {
            "replayed_record": out_rec,
            "changed": False,
            "before_state": orig_state,
            "after_state": orig_state,
            "before_error_code": orig_err,
            "after_error_code": orig_err,
            "trial_action": "PRESERVED_REPEATED_QUOTE",
            "reason": f"QUOTE_REPEATED_PRESERVED(count={occ_count})",
            "quote_occurrence_count": occ_count,
            "computed_safe_doc_v_span": None,
        }

    c_start = starts[0]
    c_end = c_start + len(quote)
    assert safe_doc_v[c_start:c_end] == quote

    old_cs = parsed_resp.get("char_start")
    old_ce = parsed_resp.get("char_end")
    repaired_resp = dict(parsed_resp)
    repaired_resp["evidence_quote"] = quote
    repaired_resp["char_start"] = c_start
    repaired_resp["char_end"] = c_end

    new_local_val = _run_full_validator_chain(
        repaired_cloud_response=repaired_resp,
        safe_doc_v=safe_doc_v,
        safe_to_v_segments=safe_to_v_segments,
        doc_sanitized_V=doc_sanitized_V,
        doc_canonical_S=doc_canonical_S,
        doc_v_to_s_segments=doc_v_to_s_segments,
        doc_removed_r_audit=doc_removed_r_audit,
        doc_meta=doc_meta,
        query_meta=query_meta,
        approved_pois_by_id=approved_pois_by_id,
    )
    new_state = str(new_local_val.get("state") or "ERROR")
    new_err = "" if new_state in VALID_NON_ERROR_STATES else str(new_local_val.get("error_code") or "UNKNOWN_ERROR")

    out_rec["parsed_response"] = repaired_resp
    out_rec["local_validation"] = new_local_val

    if new_state in VALID_NON_ERROR_STATES:
        proj_canon = _compute_canonical_projection(
            parsed_resp=repaired_resp,
            local_val=new_local_val,
            safe_to_v_segments=safe_to_v_segments,
            doc_v_to_s_segments=doc_v_to_s_segments,
        )
        out_rec["projected_canonical_response"] = proj_canon
        out_rec["final_for_item"] = True
        out_rec["offline_trial_offset_recovered"] = True
        return {
            "replayed_record": out_rec,
            "changed": True,
            "before_state": orig_state,
            "after_state": new_state,
            "before_error_code": orig_err,
            "after_error_code": "",
            "trial_action": "REPAIRED_TO_VALID",
            "reason": (
                f"UNIQUE_QUOTE_REPAIRED({orig_err}: [{old_cs},{old_ce}) -> [{c_start},{c_end}) => {new_state})"
            ),
            "quote_occurrence_count": 1,
            "computed_safe_doc_v_span": [c_start, c_end],
        }

    out_rec["projected_canonical_response"] = None
    out_rec["offline_trial_offset_recovered"] = False
    return {
        "replayed_record": out_rec,
        "changed": False,
        "before_state": orig_state,
        "after_state": new_state,
        "before_error_code": orig_err,
        "after_error_code": new_err,
        "trial_action": "QUOTE_MATCHED_DOWNSTREAM_FAILED",
        "reason": f"QUOTE_MATCHED_SAFE_DOC_V([{c_start},{c_end}) BUT_FAILED_DOWNSTREAM:{new_err})",
        "quote_occurrence_count": 1,
        "computed_safe_doc_v_span": [c_start, c_end],
    }


def _summarize_cohort_states(
    items: Sequence[Mapping[str, Any]],
    oai_by_cid: Mapping[str, Mapping[str, Any]],
    ant_by_cid: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    def _counts_for_slice(sub_items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        oai_valid = 0
        ant_valid = 0
        both_valid = 0
        oai_grades: dict[str, int] = {}
        ant_grades: dict[str, int] = {}
        paired_matrix: dict[str, int] = {}
        for it in sub_items:
            cid = str(it["custom_id"])
            vo = dict(oai_by_cid[cid].get("local_validation") or {})
            va = dict(ant_by_cid[cid].get("local_validation") or {})
            so = str(vo.get("state") or "ERROR")
            sa = str(va.get("state") or "ERROR")
            fo = bool(oai_by_cid[cid].get("final_for_item", True))
            fa = bool(ant_by_cid[cid].get("final_for_item", True))
            o_ok = so in VALID_NON_ERROR_STATES and fo
            a_ok = sa in VALID_NON_ERROR_STATES and fa
            if o_ok:
                oai_valid += 1
                oai_grades[so] = oai_grades.get(so, 0) + 1
            else:
                oai_grades["ERROR"] = oai_grades.get("ERROR", 0) + 1
            if a_ok:
                ant_valid += 1
                ant_grades[sa] = ant_grades.get(sa, 0) + 1
            else:
                ant_grades["ERROR"] = ant_grades.get("ERROR", 0) + 1
            if o_ok and a_ok:
                both_valid += 1
                pk = f"{so}__{sa}"
                paired_matrix[pk] = paired_matrix.get(pk, 0) + 1
        return {
            "expected": len(sub_items),
            "openai_valid": oai_valid,
            "anthropic_valid": ant_valid,
            "both_valid": both_valid,
            "openai_grades": dict(sorted(oai_grades.items())),
            "anthropic_grades": dict(sorted(ant_grades.items())),
            "paired_valid_matrix": dict(sorted(paired_matrix.items())),
        }

    canon_items = [it for it in items if it.get("prompt_order") == "PROMPT_ORDER_CANONICAL"]
    swap_items = [it for it in items if it.get("prompt_order") == "PROMPT_ORDER_SWAPPED"]
    return {
        "total": _counts_for_slice(items),
        "canonical": _counts_for_slice(canon_items),
        "swapped": _counts_for_slice(swap_items),
    }


def _evaluate_replay_metrics(
    *,
    items: Sequence[Mapping[str, Any]],
    oai_by_cid: Mapping[str, Mapping[str, Any]],
    ant_by_cid: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Compute within-judge prompt-order bias and canonical-slice dual-judge concordance."""
    queries_meta: list[dict[str, Any]] = []
    seen_q: set[str] = set()
    docs_by_id: dict[str, dict[str, Any]] = {}
    removed_by_doc_id: dict[str, list[tuple[int, int]]] = {}
    sealed_pairs: list[tuple[str, str]] = []

    canon_oai_json: dict[tuple[str, str], str] = {}
    swap_oai_json: dict[tuple[str, str], str] = {}
    canon_ant_json: dict[tuple[str, str], str] = {}
    swap_ant_json: dict[tuple[str, str], str] = {}

    def _to_canonical_json(rec: Mapping[str, Any]) -> str:
        proj = rec.get("projected_canonical_response")
        lv = dict(rec.get("local_validation") or {})
        st = str(lv.get("state") or "ERROR")
        if isinstance(proj, Mapping) and st in VALID_NON_ERROR_STATES and bool(rec.get("final_for_item", True)):
            return json.dumps(dict(proj), ensure_ascii=False)
        return json.dumps({"invalid_error": lv.get("error_code") or "ERROR"}, ensure_ascii=False)

    for it in items:
        qmeta = dict(it["query_meta"])
        qid = str(qmeta["query_id"])
        if qid not in seen_q:
            seen_q.add(qid)
            queries_meta.append(qmeta)
        did = str(it["doc_record_for_leak_check"]["document_id"])
        if did not in docs_by_id:
            docs_by_id[did] = {
                "document_id": did,
                "canonical_text_S": str(it["doc_canonical_S"]),
                "city": it["doc_meta"].get("city"),
                "poi_id": it["doc_meta"].get("poi_id"),
            }
            removed_by_doc_id[did] = list(it["doc_removed_r_audit"])
        pair = (qid, did)
        cid = str(it["custom_id"])
        if it.get("prompt_order") == "PROMPT_ORDER_CANONICAL":
            sealed_pairs.append(pair)
            canon_oai_json[pair] = _to_canonical_json(oai_by_cid[cid])
            canon_ant_json[pair] = _to_canonical_json(ant_by_cid[cid])
        elif it.get("prompt_order") == "PROMPT_ORDER_SWAPPED":
            swap_oai_json[pair] = _to_canonical_json(oai_by_cid[cid])
            swap_ant_json[pair] = _to_canonical_json(ant_by_cid[cid])

    bias_oai = evaluate_prompt_order_bias(
        queries_meta=queries_meta,
        docs_by_id=docs_by_id,
        removed_by_doc_id=removed_by_doc_id,
        canonical_responses={p: canon_oai_json[p] for p in swap_oai_json if p in canon_oai_json},
        swapped_responses=swap_oai_json,
        total_expected_pairs=len(canon_oai_json),
        declared_coverage_mode="STRATIFIED_20PCT_SAMPLE",
    )
    bias_ant = evaluate_prompt_order_bias(
        queries_meta=queries_meta,
        docs_by_id=docs_by_id,
        removed_by_doc_id=removed_by_doc_id,
        canonical_responses={p: canon_ant_json[p] for p in swap_ant_json if p in canon_ant_json},
        swapped_responses=swap_ant_json,
        total_expected_pairs=len(canon_ant_json),
        declared_coverage_mode="STRATIFIED_20PCT_SAMPLE",
    )

    grade_to_int = {"REL_0": 0, "REL_1": 1, "REL_2": 2}
    vec_a: list[int] = []
    vec_b: list[int] = []
    canon_total = 0
    unres_oai = 0
    unres_ant = 0
    for it in items:
        if it.get("prompt_order") != "PROMPT_ORDER_CANONICAL":
            continue
        canon_total += 1
        cid = str(it["custom_id"])
        rec_o = oai_by_cid[cid]
        rec_a = ant_by_cid[cid]
        so = str((rec_o.get("local_validation") or {}).get("state") or "ERROR")
        sa = str((rec_a.get("local_validation") or {}).get("state") or "ERROR")
        fo = bool(rec_o.get("final_for_item", True))
        fa = bool(rec_a.get("final_for_item", True))
        ok_o = so in grade_to_int and fo
        ok_a = sa in grade_to_int and fa
        if not ok_o:
            unres_oai += 1
        if not ok_a:
            unres_ant += 1
        if ok_o and ok_a:
            vec_a.append(grade_to_int[so])
            vec_b.append(grade_to_int[sa])

    kappa_w = round(float(quadratic_weighted_kappa(vec_a, vec_b)), 6) if vec_a else 0.0
    unres_rate_oai = round(unres_oai / float(canon_total), 6) if canon_total else 0.0
    unres_rate_ant = round(unres_ant / float(canon_total), 6) if canon_total else 0.0
    return {
        "prompt_order_bias_openai": {
            "paired_item_count": bias_oai["paired_item_count"],
            "valid_discrete_pair_count": bias_oai["valid_discrete_pair_count"],
            "flip_count": bias_oai["flip_count"],
            "exact_swap_agreement": bias_oai["exact_swap_agreement"],
            "quadratic_weighted_kappa_order": bias_oai["quadratic_weighted_kappa_order"],
            "prompt_order_gate_passed": bias_oai["prompt_order_gate_passed"],
            "prompt_order_disposition": bias_oai["prompt_order_disposition"],
            "error_or_na_pairs_count": len(bias_oai["error_or_na_pairs"]),
            "mismatch_pairs": bias_oai["mismatch_pairs"],
        },
        "prompt_order_bias_anthropic": {
            "paired_item_count": bias_ant["paired_item_count"],
            "valid_discrete_pair_count": bias_ant["valid_discrete_pair_count"],
            "flip_count": bias_ant["flip_count"],
            "exact_swap_agreement": bias_ant["exact_swap_agreement"],
            "quadratic_weighted_kappa_order": bias_ant["quadratic_weighted_kappa_order"],
            "prompt_order_gate_passed": bias_ant["prompt_order_gate_passed"],
            "prompt_order_disposition": bias_ant["prompt_order_disposition"],
            "error_or_na_pairs_count": len(bias_ant["error_or_na_pairs"]),
            "mismatch_pairs": bias_ant["mismatch_pairs"],
        },
        "dual_judge_concordance_canonical": {
            "kappa_w": kappa_w,
            "paired_resolved_count": len(vec_a),
            "canonical_expected_count": canon_total,
            "unresolved_rate_openai": unres_rate_oai,
            "unresolved_rate_anthropic": unres_rate_ant,
        },
    }


def replay_dual_judge_cohort_offline_offset_trial(
    *,
    items: Sequence[Mapping[str, Any]],
    openai_attempts_by_cid: Mapping[str, Mapping[str, Any]],
    anthropic_attempts_by_cid: Mapping[str, Mapping[str, Any]],
    wire_context_by_prov_cid: Mapping[tuple[str, str], Mapping[str, Any]],
    openai_outcomes_by_bid_cid: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    anthropic_outcomes_by_bid_cid: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
    approved_pois_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Replay all cohort items across both judges without modifying original inputs."""
    oai_before: dict[str, dict[str, Any]] = {}
    ant_before: dict[str, dict[str, Any]] = {}
    oai_after: dict[str, dict[str, Any]] = {}
    ant_after: dict[str, dict[str, Any]] = {}
    item_diffs: list[dict[str, Any]] = []
    action_counts_oai: dict[str, int] = {}
    action_counts_ant: dict[str, int] = {}

    for it in items:
        cid = str(it["custom_id"])
        rec_o_orig = copy.deepcopy(dict(openai_attempts_by_cid[cid]))
        rec_a_orig = copy.deepcopy(dict(anthropic_attempts_by_cid[cid]))
        oai_before[cid] = rec_o_orig
        ant_before[cid] = rec_a_orig

        ctx_o = wire_context_by_prov_cid[("openai", cid)]
        ctx_a = wire_context_by_prov_cid[("anthropic", cid)]
        oc_o = (openai_outcomes_by_bid_cid or {}).get((str(rec_o_orig.get("batch_id") or ""), cid))
        oc_a = (anthropic_outcomes_by_bid_cid or {}).get((str(rec_a_orig.get("batch_id") or ""), cid))

        res_o = replay_record_with_offline_offset_trial(
            record=rec_o_orig,
            safe_doc_v=str(ctx_o["safe_doc_v"]),
            safe_to_v_segments=ctx_o["safe_to_v_segments"],
            doc_sanitized_V=str(it["sanitized_text_V"]),
            doc_canonical_S=str(it["doc_canonical_S"]),
            doc_v_to_s_segments=it["doc_v_to_s_segments"],
            doc_removed_r_audit=it["doc_removed_r_audit"],
            doc_meta=it["doc_meta"],
            query_meta=it["query_meta"],
            outcome_item=oc_o,
            approved_pois_by_id=approved_pois_by_id,
        )
        res_a = replay_record_with_offline_offset_trial(
            record=rec_a_orig,
            safe_doc_v=str(ctx_a["safe_doc_v"]),
            safe_to_v_segments=ctx_a["safe_to_v_segments"],
            doc_sanitized_V=str(it["sanitized_text_V"]),
            doc_canonical_S=str(it["doc_canonical_S"]),
            doc_v_to_s_segments=it["doc_v_to_s_segments"],
            doc_removed_r_audit=it["doc_removed_r_audit"],
            doc_meta=it["doc_meta"],
            query_meta=it["query_meta"],
            outcome_item=oc_a,
            approved_pois_by_id=approved_pois_by_id,
        )

        oai_after[cid] = res_o["replayed_record"]
        ant_after[cid] = res_a["replayed_record"]
        ao = res_o["trial_action"]
        aa = res_a["trial_action"]
        action_counts_oai[ao] = action_counts_oai.get(ao, 0) + 1
        action_counts_ant[aa] = action_counts_ant.get(aa, 0) + 1

        was_both_valid = (
            res_o["before_state"] in VALID_NON_ERROR_STATES
            and bool(rec_o_orig.get("final_for_item", True))
            and res_a["before_state"] in VALID_NON_ERROR_STATES
            and bool(rec_a_orig.get("final_for_item", True))
        )
        now_both_valid = (
            res_o["after_state"] in VALID_NON_ERROR_STATES
            and bool(oai_after[cid].get("final_for_item", True))
            and res_a["after_state"] in VALID_NON_ERROR_STATES
            and bool(ant_after[cid].get("final_for_item", True))
        )

        if res_o["changed"] or res_a["changed"] or (not was_both_valid):
            item_diffs.append(
                {
                    "custom_id": cid,
                    "query_id": it["query_meta"]["query_id"],
                    "document_id": it["doc_record_for_leak_check"]["document_id"],
                    "poi_id": it["doc_meta"]["poi_id"],
                    "prompt_order": it["prompt_order"],
                    "any_changed": bool(res_o["changed"] or res_a["changed"]),
                    "paired_status_before": "BOTH_VALID" if was_both_valid else "INCOMPLETE",
                    "paired_status_after": "BOTH_VALID" if now_both_valid else "INCOMPLETE",
                    "became_both_valid": bool((not was_both_valid) and now_both_valid),
                    "openai_before": f"{res_o['before_state']}" + (f"({res_o['before_error_code']})" if res_o["before_error_code"] else ""),
                    "openai_after": f"{res_o['after_state']}" + (f"({res_o['after_error_code']})" if res_o["after_error_code"] else ""),
                    "openai_changed": res_o["changed"],
                    "openai_reason": res_o["reason"],
                    "openai_trial_span": res_o["computed_safe_doc_v_span"],
                    "anthropic_before": f"{res_a['before_state']}" + (f"({res_a['before_error_code']})" if res_a["before_error_code"] else ""),
                    "anthropic_after": f"{res_a['after_state']}" + (f"({res_a['after_error_code']})" if res_a["after_error_code"] else ""),
                    "anthropic_changed": res_a["changed"],
                    "anthropic_reason": res_a["reason"],
                    "anthropic_trial_span": res_a["computed_safe_doc_v_span"],
                }
            )

    before_summary = _summarize_cohort_states(items, oai_before, ant_before)
    after_summary = _summarize_cohort_states(items, oai_after, ant_after)
    deltas = {
        sl: {
            "openai_valid_delta": after_summary[sl]["openai_valid"] - before_summary[sl]["openai_valid"],
            "anthropic_valid_delta": after_summary[sl]["anthropic_valid"] - before_summary[sl]["anthropic_valid"],
            "both_valid_delta": after_summary[sl]["both_valid"] - before_summary[sl]["both_valid"],
        }
        for sl in ("total", "canonical", "swapped")
    }
    before_metrics = _evaluate_replay_metrics(items=items, oai_by_cid=oai_before, ant_by_cid=ant_before)
    after_metrics = _evaluate_replay_metrics(items=items, oai_by_cid=oai_after, ant_by_cid=ant_after)

    return {
        "schema_version": "GOMATE_W07_ROUTE2_OFFLINE_OFFSET_TRIAL_REPLAY_V1",
        "before_summary": before_summary,
        "after_summary": after_summary,
        "deltas": deltas,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "action_counts_openai": dict(sorted(action_counts_oai.items())),
        "action_counts_anthropic": dict(sorted(action_counts_ant.items())),
        "incomplete_and_changed_items": item_diffs,
        "replayed_openai_records": oai_after,
        "replayed_anthropic_records": ant_after,
    }
