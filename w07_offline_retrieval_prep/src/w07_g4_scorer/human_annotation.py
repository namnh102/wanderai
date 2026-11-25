"""OD-G15-05 Human 2+1 blind annotation, adjudication queue, and sealed qrel compiler.

Zero-ML-import module compliant with `w07_g4_scorer.contracts.assert_g4_package_zero_ml_imports`:
uses only Python stdlib and `w07_g4_scorer` contract/metric helpers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from w07_g4_scorer.contracts import (
    QrelRecord,
    RelevanceState,
    compute_query_certificates,
    load_external_qrels,
    merge_intervals,
    sha256_bytes,
)
from w07_g4_scorer.judge_gates import quadratic_weighted_kappa

HUMAN_ROSTER_RECEIPT_SCHEMA_V1 = "GOMATE_W07_OD_G15_05_HUMAN_ROSTER_RECEIPT_V1"
BLIND_WORKBOOK_SCHEMA_V1 = "GOMATE_W07_OD_G15_05_BLIND_WORKBOOK_V1"
ADJUDICATION_QUEUE_SCHEMA_V1 = "GOMATE_W07_OD_G15_05_ADJUDICATION_QUEUE_V1"
HUMAN_QREL_COMPILATION_SCHEMA_V1 = "GOMATE_W07_OD_G15_05_HUMAN_QRELS_RECEIPT_V1"

ALLOWED_OD_G15_05_ROUTES: tuple[str, ...] = (
    "ROUTE_1A_EXHAUSTIVE_2PLUS1_HUMAN",
    "ROUTE_1B_POOLED_2PLUS1_HUMAN_OPTION_B",
)

BLIND_PACKET_7_KEYS: frozenset[str] = frozenset(
    {
        "packet_item_uuid",
        "query_id",
        "query_text",
        "document_id",
        "source_type",
        "language",
        "canonical_text_S",
    }
)

FORBIDDEN_BLIND_PACKET_LEAK_KEYS: frozenset[str] = frozenset(
    {
        "rank",
        "score",
        "rrf_score",
        "cell_id",
        "arm",
        "retriever",
        "retriever_name",
        "c_full_s_spans",
        "c_vis_s_spans",
        "c_vis_s_spans_dense",
    }
)

VALID_HUMAN_LABELS: frozenset[str] = frozenset(
    {
        RelevanceState.REL_2.value,
        RelevanceState.REL_1.value,
        RelevanceState.REL_0.value,
        RelevanceState.NA.value,
    }
)

_GRADE_TO_INT: dict[str, int] = {
    RelevanceState.REL_0.value: 0,
    RelevanceState.REL_1.value: 1,
    RelevanceState.REL_2.value: 2,
}

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_PLACEHOLDER_PREFIXES: tuple[str, ...] = (
    "TEMPLATE_",
    "UNCOMMITTED_",
    "PLACEHOLDER_",
    "SYN_",
)


@dataclass(frozen=True)
class ValidatedHumanVote:
    """Single validated human annotation or adjudication vote for one blinded pair."""

    packet_item_uuid: str
    query_id: str
    document_id: str
    annotator_id: str
    label: RelevanceState
    plausible_unsupported_lure: int | None
    evidence_s_spans: tuple[tuple[int, int], ...]
    evidence_quotes: tuple[dict[str, Any], ...]
    rationale: str | None = None


CONTROLLING_PROTOCOL_V1_LF_SHA256 = (
    "5056c5c2373ee9584b8850ba49411160cc2c382ad6315aaada4c05fb9b0030c2"
)
CONTROLLING_PROTOCOL_V1_CRLF_SHA256 = (
    "5056c5c26142c579e1033fe3557ca031c9a0d2f18a90c2015a0a3fe97a4fdbe2"
)
METHOD_AMENDMENT_01_V0_3_1_ID = "W07_B2_METHOD_AMENDMENT_01_V0_3_1_OPTION_B"
METHOD_AMENDMENT_01_V0_3_1_DRAFT_SHA256 = (
    "f5560a95a6893dbc09681004875500f822a45451b9891086c8b3636ec71561d6"
)
ANNEX_V0_2_2_CANDIDATE_SHA256 = (
    "e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940"
)
FORMAL_ROUTE1B_APPROVAL_SCHEMA_V1 = "GOMATE_W07_ROUTE_1B_FORMAL_APPROVAL_BUNDLE_V1"
_FORBIDDEN_UNSIGNED_TOKENS = (
    "NOT_EFFECTIVE",
    "UNSIGNED",
    "REVIEW_DRAFT",
    "TEMPLATE_",
    "SYN_",
    "AWAITING_",
    "[BLANK",
)


def build_synthetic_mode_disclosure(
    component: str,
    *,
    note: str = "Synthetic offline preparation artifact; not formal OD-G15-05 ground truth.",
) -> dict[str, Any]:
    """Return explicit provenance tag distinguishing synthetic prep from formal Route 1B."""
    return {
        "execution_classification": "SYNTHETIC_PREP_ONLY",
        "contains_synthetic_data": True,
        "component": _require_non_empty_str(component, "MISSING_DISCLOSURE_COMPONENT"),
        "not_formal_ground_truth": True,
        "od_g15_05_hold_unchanged": True,
        "note": note,
    }


def _has_unsigned_marker(val: str) -> bool:
    upper = val.strip().upper()
    return any(tok in upper for tok in _FORBIDDEN_UNSIGNED_TOKENS)


def validate_formal_route1b_authorization_bundle(
    bundle_obj: Mapping[str, Any],
    *,
    require_formal_execution: bool = False,
) -> dict[str, Any]:
    """Validate Route 1B (Method Amendment 01 v0.3.1) governance bundle.

    When `require_formal_execution=True`, fails closed on any synthetic marker,
    unsigned draft/placeholder field, missing ChatGPT audit PASS, unratified
    Protocol/Annex/Amendment hash, uncommitted 2+1 human roster, missing G3 code
    freeze commit SHA, invalid capacity envelope, paid API allowance, or non-HOLD G5.
    """
    if not isinstance(bundle_obj, Mapping):
        raise ValueError("INVALID_ROUTE1B_BUNDLE_TYPE")
    if bundle_obj.get("schema_version") != FORMAL_ROUTE1B_APPROVAL_SCHEMA_V1:
        raise ValueError(
            f"INVALID_ROUTE1B_SCHEMA_VERSION: expected {FORMAL_ROUTE1B_APPROVAL_SCHEMA_V1!r}"
        )

    route = _require_non_empty_str(
        bundle_obj.get("od_g15_05_route"), "INVALID_OD_G15_05_ROUTE"
    )
    if route != "ROUTE_1B_POOLED_2PLUS1_HUMAN_OPTION_B":
        raise ValueError(
            f"INVALID_ROUTE1B_ROUTE: expected 'ROUTE_1B_POOLED_2PLUS1_HUMAN_OPTION_B', got {route!r}"
        )

    disclosure = bundle_obj.get("synthetic_mode_disclosure")
    if not isinstance(disclosure, Mapping):
        raise ValueError("MISSING_SYNTHETIC_MODE_DISCLOSURE")
    exec_class = _require_non_empty_str(
        disclosure.get("execution_classification"), "MISSING_EXECUTION_CLASSIFICATION"
    )
    contains_syn = disclosure.get("contains_synthetic_data")
    if type(contains_syn) is not bool:
        raise ValueError("INVALID_CONTAINS_SYNTHETIC_DATA_FLAG")

    roster = validate_human_roster_receipt(
        bundle_obj.get("human_roster_receipt", {}),
        require_formal_commitment=require_formal_execution,
    )
    if roster["od_g15_05_route"] != route:
        raise ValueError("ROSTER_ROUTE_MISMATCH_WITH_ROUTE1B_BUNDLE")

    amendment = bundle_obj.get("method_amendment")
    if not isinstance(amendment, Mapping):
        raise ValueError("MISSING_METHOD_AMENDMENT_BLOCK")
    amendment_id = _require_non_empty_str(
        amendment.get("amendment_id"), "MISSING_METHOD_AMENDMENT_ID"
    )
    if amendment_id != METHOD_AMENDMENT_01_V0_3_1_ID:
        raise ValueError(f"UNEXPECTED_AMENDMENT_ID: {amendment_id!r}")
    amendment_sha = _require_non_empty_str(
        amendment.get("amendment_sha256"), "MISSING_METHOD_AMENDMENT_SHA256"
    )
    if _SHA256_HEX_RE.fullmatch(amendment_sha) is None:
        raise ValueError("INVALID_METHOD_AMENDMENT_SHA256")

    proto_sha = _require_non_empty_str(
        bundle_obj.get("controlling_protocol_sha256"), "MISSING_PROTOCOL_SHA256"
    )
    if proto_sha not in {
        CONTROLLING_PROTOCOL_V1_LF_SHA256,
        CONTROLLING_PROTOCOL_V1_CRLF_SHA256,
    }:
        raise ValueError("CONTROLLING_PROTOCOL_SHA256_MISMATCH")

    annex = bundle_obj.get("g15_annex")
    if not isinstance(annex, Mapping):
        raise ValueError("MISSING_G15_ANNEX_BLOCK")
    annex_sha = _require_non_empty_str(annex.get("annex_sha256"), "MISSING_ANNEX_SHA256")
    if _SHA256_HEX_RE.fullmatch(annex_sha) is None:
        raise ValueError("INVALID_ANNEX_SHA256")

    ops = bundle_obj.get("operational_gates")
    if not isinstance(ops, Mapping):
        raise ValueError("MISSING_OPERATIONAL_GATES_BLOCK")

    if require_formal_execution:
        if exec_class != "FORMAL_ROUTE_1B_REAL_CORPUS" or contains_syn:
            raise PermissionError(
                "FORMAL_ROUTE1B_BLOCKED_SYNTHETIC_DISCLOSURE: formal mode refuses synthetic artifacts"
            )
        if annex_sha == "0" * 64 or amendment_sha == "0" * 64:
            raise PermissionError("FORMAL_ROUTE1B_BLOCKED_ZERO_SHA256")

        annex_status = _require_non_empty_str(
            annex.get("activation_status"), "MISSING_ANNEX_ACTIVATION_STATUS"
        )
        if annex_status != "OWNER_APPROVED_EFFECTIVE":
            raise PermissionError(
                f"FORMAL_ROUTE1B_BLOCKED_ANNEX_STATUS: {annex_status!r}"
            )

        audit_status = _require_non_empty_str(
            amendment.get("chatgpt_audit_status"), "MISSING_CHATGPT_AUDIT_STATUS"
        )
        if audit_status != "PASS":
            raise PermissionError(
                f"FORMAL_ROUTE1B_BLOCKED_CHATGPT_AUDIT: {audit_status!r}"
            )

        amend_status = _require_non_empty_str(
            amendment.get("activation_status"), "MISSING_AMENDMENT_ACTIVATION_STATUS"
        )
        if amend_status != "OWNER_SIGNED_EFFECTIVE":
            raise PermissionError(
                f"FORMAL_ROUTE1B_BLOCKED_AMENDMENT_UNSIGNED: {amend_status!r}"
            )

        owner_sig = _require_non_empty_str(
            amendment.get("owner_signature_ref"), "MISSING_OWNER_SIGNATURE_REF"
        )
        approval_date = _require_non_empty_str(
            amendment.get("approval_date_ict"), "MISSING_APPROVAL_DATE_ICT"
        )
        if _has_unsigned_marker(owner_sig) or _has_unsigned_marker(approval_date):
            raise PermissionError(
                "FORMAL_ROUTE1B_BLOCKED_AMENDMENT_PLACEHOLDER_SIGNATURE"
            )

        cap_votes = ops.get("capacity_envelope_max_votes")
        if type(cap_votes) is not int or cap_votes < 1000:
            raise PermissionError(
                f"FORMAL_ROUTE1B_BLOCKED_CAPACITY_ENVELOPE: invalid {cap_votes!r}"
            )
        git_sha = _require_non_empty_str(
            ops.get("g3_code_freeze_git_sha"), "MISSING_G3_CODE_FREEZE_GIT_SHA"
        )
        if (
            len(git_sha) != 40
            or git_sha == "0" * 40
            or not all(c in "0123456789abcdef" for c in git_sha.lower())
            or _has_unsigned_marker(git_sha)
        ):
            raise PermissionError(
                f"FORMAL_ROUTE1B_BLOCKED_INVALID_G3_GIT_SHA: {git_sha!r}"
            )
        if ops.get("g3_no_final_exposure_attested") is not True:
            raise PermissionError("FORMAL_ROUTE1B_BLOCKED_NO_FINAL_EXPOSURE_ATTESTATION")
        if ops.get("g5_status") != "HOLD":
            raise PermissionError("FORMAL_ROUTE1B_BLOCKED_G5_MUST_REMAIN_HOLD")
        if ops.get("paid_llm_api_allowed") is not False:
            raise PermissionError("FORMAL_ROUTE1B_BLOCKED_PAID_API_PROHIBITED")

    return {
        "schema_version": FORMAL_ROUTE1B_APPROVAL_SCHEMA_V1,
        "od_g15_05_route": route,
        "execution_classification": exec_class,
        "contains_synthetic_data": contains_syn,
        "formal_execution_authorized": require_formal_execution,
        "controlling_protocol_sha256": proto_sha,
        "method_amendment_id": amendment_id,
        "method_amendment_sha256": amendment_sha,
        "annex_sha256": annex_sha,
        "roster": roster,
    }


def _require_non_empty_str(val: Any, error_code: str) -> str:
    if type(val) is not str or not val.strip():
        raise ValueError(f"{error_code}: expected non-empty string, got {val!r}")
    return val.strip()


def validate_human_roster_receipt(
    roster_obj: Mapping[str, Any],
    *,
    require_formal_commitment: bool = False,
) -> dict[str, str]:
    """Validate off-repo 2+1 human annotator & adjudicator roster receipt."""
    if not isinstance(roster_obj, Mapping):
        raise ValueError("INVALID_ROSTER_RECEIPT_TYPE")
    if roster_obj.get("schema_version") != HUMAN_ROSTER_RECEIPT_SCHEMA_V1:
        raise ValueError(
            f"INVALID_ROSTER_SCHEMA_VERSION: expected {HUMAN_ROSTER_RECEIPT_SCHEMA_V1!r}"
        )

    route = _require_non_empty_str(
        roster_obj.get("od_g15_05_route"), "INVALID_OD_G15_05_ROUTE"
    )
    if route not in ALLOWED_OD_G15_05_ROUTES:
        raise ValueError(
            f"INVALID_OD_G15_05_ROUTE: {route!r} not in {ALLOWED_OD_G15_05_ROUTES}"
        )

    a1 = _require_non_empty_str(
        roster_obj.get("human_annotator_01_id"), "MISSING_HUMAN_ANNOTATOR_01_ID"
    )
    a2 = _require_non_empty_str(
        roster_obj.get("human_annotator_02_id"), "MISSING_HUMAN_ANNOTATOR_02_ID"
    )
    adj = _require_non_empty_str(
        roster_obj.get("human_adjudicator_03_id"), "MISSING_HUMAN_ADJUDICATOR_03_ID"
    )
    if len({a1, a2, adj}) != 3:
        raise ValueError(
            "DUPLICATE_HUMAN_ROSTER_IDS: human_annotator_01, human_annotator_02, and "
            "human_adjudicator_03 must all be distinct individuals"
        )

    commitment_sha = roster_obj.get("roster_identity_commitment_sha256")
    if type(commitment_sha) is not str or _SHA256_HEX_RE.fullmatch(commitment_sha) is None:
        raise ValueError(
            "INVALID_ROSTER_COMMITMENT_SHA256: expected 64-char lowercase hex digest"
        )

    if require_formal_commitment:
        for role_id in (a1, a2, adj):
            if role_id.startswith(_PLACEHOLDER_PREFIXES):
                raise PermissionError(
                    f"FORMAL_ROSTER_BLOCKED_PLACEHOLDER_ID: {role_id!r} cannot unlock formal G2/G2B"
                )
        if commitment_sha == "0" * 64:
            raise PermissionError(
                "FORMAL_ROSTER_BLOCKED_UNCOMMITTED_HASH: placeholder zero SHA-256 rejected"
            )
        if roster_obj.get("roster_status") != "COMMITTED_BY_OWNER":
            raise PermissionError(
                "FORMAL_ROSTER_BLOCKED_STATUS: roster_status must be 'COMMITTED_BY_OWNER'"
            )

    return {
        "od_g15_05_route": route,
        "human_annotator_01_id": a1,
        "human_annotator_02_id": a2,
        "human_adjudicator_03_id": adj,
        "roster_identity_commitment_sha256": commitment_sha,
    }


def load_and_verify_blind_packet_rows(
    packet_rows_or_path: Path | str | Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Load strict 7-key blinded packet rows and fail closed on leakage or duplicates."""
    raw_rows: list[Mapping[str, Any]]
    if isinstance(packet_rows_or_path, (Path, str)):
        p = Path(packet_rows_or_path)
        if not p.is_file():
            raise FileNotFoundError(f"Blind packet JSONL not found: {p}")
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not lines:
            raise ValueError(f"EMPTY_BLIND_PACKET_JSONL: {p}")
        raw_rows = [json.loads(ln) for ln in lines]
    else:
        raw_rows = list(packet_rows_or_path)
        if not raw_rows:
            raise ValueError("EMPTY_BLIND_PACKET_ROWS")

    verified: list[dict[str, str]] = []
    seen_uuids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()

    for idx, row in enumerate(raw_rows, start=1):
        if not isinstance(row, Mapping):
            raise ValueError(f"INVALID_BLIND_PACKET_ROW_TYPE_AT_{idx}")
        keys = set(row.keys())
        leak_hits = sorted(keys & FORBIDDEN_BLIND_PACKET_LEAK_KEYS)
        if leak_hits:
            raise ValueError(
                f"BLIND_PACKET_LEAKAGE_DETECTED_AT_{idx}: forbidden columns {leak_hits}"
            )
        if keys != BLIND_PACKET_7_KEYS:
            raise ValueError(
                f"BLIND_PACKET_SCHEMA_MISMATCH_AT_{idx}: expected {sorted(BLIND_PACKET_7_KEYS)}, got {sorted(keys)}"
            )

        clean_row = {
            k: _require_non_empty_str(row[k], f"EMPTY_BLIND_FIELD_{k}_AT_{idx}")
            for k in BLIND_PACKET_7_KEYS
        }
        uid = clean_row["packet_item_uuid"]
        pair = (clean_row["query_id"], clean_row["document_id"])
        if uid in seen_uuids:
            raise ValueError(f"DUPLICATE_PACKET_ITEM_UUID: {uid!r}")
        if pair in seen_pairs:
            raise ValueError(f"DUPLICATE_QUERY_DOC_PAIR_IN_PACKET: {pair!r}")
        seen_uuids.add(uid)
        seen_pairs.add(pair)
        verified.append(clean_row)

    return verified


def prepare_dual_blind_annotator_workbooks(
    packet_rows_or_path: Path | str | Sequence[Mapping[str, Any]],
    *,
    roster_obj: Mapping[str, Any],
    query_metadata_by_id: Mapping[str, Mapping[str, Any]] | None = None,
    require_formal_roster: bool = False,
) -> dict[str, Any]:
    """Emit two independent blinded workbooks sharing exact 7-key item blinding."""
    roster = validate_human_roster_receipt(
        roster_obj, require_formal_commitment=require_formal_roster
    )
    rows = load_and_verify_blind_packet_rows(packet_rows_or_path)
    packet_bytes = (
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n"
    ).encode("utf-8")
    packet_sha = sha256_bytes(packet_bytes)

    def _build_workbook(annotator_id: str, slot: str) -> dict[str, Any]:
        tasks: list[dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            qmeta = (query_metadata_by_id or {}).get(row["query_id"], {})
            task: dict[str, Any] = {
                "sequence_no": idx,
                "packet_item_uuid": row["packet_item_uuid"],
                "query_id": row["query_id"],
                "query_text": row["query_text"],
                "document_id": row["document_id"],
                "source_type": row["source_type"],
                "language": row["language"],
                "canonical_text_S": row["canonical_text_S"],
                "rubric_options": ["REL_2", "REL_1", "REL_0", "NA"],
                "query_scope_mode": qmeta.get("scope_mode"),
                "requested_facet_keywords": list(qmeta.get("requested_facet_keywords", ())),
                # Strictly omit `pre_rank_answerability` per Method Amendment 01 v0.3.1 Section 4
                # Blank response template fields to be filled strictly by human annotator
                "label": None,
                "plausible_unsupported_lure": None,
                "evidence_quotes": [],
                "annotator_notes": "",
            }
            tasks.append(task)
        return {
            "schema_version": BLIND_WORKBOOK_SCHEMA_V1,
            "od_g15_05_route": roster["od_g15_05_route"],
            "annotator_slot": slot,
            "annotator_id": annotator_id,
            "blind_packet_sha256": packet_sha,
            "anti_leakage_attestation": {
                "pre_rank_answerability_withheld": True,
                "rank_score_cell_stripped": True,
            },
            "item_count": len(tasks),
            "tasks": tasks,
        }

    return {
        "roster": roster,
        "blind_packet_sha256": packet_sha,
        "item_count": len(rows),
        "annotator_01_workbook": _build_workbook(
            roster["human_annotator_01_id"], "HUMAN_ANNOTATOR_01"
        ),
        "annotator_02_workbook": _build_workbook(
            roster["human_annotator_02_id"], "HUMAN_ANNOTATOR_02"
        ),
    }


def _intervals_overlap(a: Sequence[tuple[int, int]], b: Sequence[tuple[int, int]]) -> bool:
    for s1, e1 in a:
        for s2, e2 in b:
            if max(s1, s2) < min(e1, e2):
                return True
    return False


def _verify_vote_evidence_and_lure(
    *,
    canonical_text_s: str,
    label: RelevanceState,
    raw_lure: Any,
    raw_quotes: Any,
    raw_spans: Any,
    removed_audit_spans: Sequence[tuple[int, int]] = (),
    context_tag: str,
) -> tuple[int | None, tuple[tuple[int, int], ...], tuple[dict[str, Any], ...]]:
    # 1. Plausible unsupported lure validation
    if label == RelevanceState.REL_0:
        if type(raw_lure) is bool or type(raw_lure) is not int or raw_lure not in (0, 1):
            raise ValueError(
                f"MISSING_OR_INVALID_LURE_ON_REL_0_{context_tag}: {raw_lure!r} (must be int 0 or 1)"
            )
        lure_val: int | None = raw_lure
    elif label in (RelevanceState.REL_1, RelevanceState.REL_2):
        if raw_lure is not None:
            if type(raw_lure) is bool or type(raw_lure) is not int or raw_lure != 0:
                raise ValueError(
                    f"INVALID_LURE_ON_POSITIVE_{context_tag}: {raw_lure!r}"
                )
        lure_val = None if raw_lure is None else 0
    else:
        if raw_lure is not None:
            if type(raw_lure) is bool or type(raw_lure) is not int or raw_lure not in (0, 1):
                raise ValueError(f"INVALID_LURE_ON_NA_{context_tag}: {raw_lure!r}")
        lure_val = raw_lure

    # 2. Verbatim evidence quotes & canonical_text_S [start_char, end_char) validation
    if raw_quotes is None:
        raw_quotes = []
    if not isinstance(raw_quotes, list):
        raise ValueError(f"INVALID_EVIDENCE_QUOTES_TYPE_{context_tag}")

    verified_quotes: list[dict[str, Any]] = []
    derived_intervals: list[tuple[int, int]] = []
    text_len = len(canonical_text_s)

    for q_idx, item in enumerate(raw_quotes):
        if not isinstance(item, Mapping):
            raise ValueError(f"INVALID_QUOTE_ENTRY_TYPE_{context_tag}_Q{q_idx}")
        quote_str = item.get("exact_quote")
        s_off = item.get("start_char")
        e_off = item.get("end_char")
        if type(quote_str) is not str or not quote_str:
            raise ValueError(f"EMPTY_EXACT_QUOTE_{context_tag}_Q{q_idx}")
        if (
            type(s_off) is bool
            or type(e_off) is bool
            or type(s_off) is not int
            or type(e_off) is not int
        ):
            raise ValueError(f"INVALID_QUOTE_OFFSETS_{context_tag}_Q{q_idx}")
        if s_off < 0 or e_off <= s_off or e_off > text_len:
            raise ValueError(
                f"OUT_OF_BOUNDS_QUOTE_OFFSET_{context_tag}_Q{q_idx}: [{s_off}, {e_off}) vs len={text_len}"
            )
        actual_sub = canonical_text_s[s_off:e_off]
        if actual_sub != quote_str:
            raise ValueError(
                f"QUOTE_CANONICAL_S_MISMATCH_{context_tag}_Q{q_idx}: "
                f"expected S[{s_off}:{e_off}] == exact_quote"
            )
        verified_quotes.append(
            {"exact_quote": quote_str, "start_char": s_off, "end_char": e_off}
        )
        derived_intervals.append((s_off, e_off))

    # Optional explicit evidence_s_spans must agree cleanly with quote spans if both given
    explicit_intervals: list[tuple[int, int]] = []
    if raw_spans is not None:
        if not isinstance(raw_spans, list):
            raise ValueError(f"INVALID_EVIDENCE_S_SPANS_TYPE_{context_tag}")
        for sp in raw_spans:
            if not isinstance(sp, (list, tuple)) or len(sp) != 2:
                raise ValueError(f"INVALID_EVIDENCE_S_SPAN_{context_tag}: {sp!r}")
            a, b = sp[0], sp[1]
            if type(a) is bool or type(b) is bool or type(a) is not int or type(b) is not int:
                raise ValueError(f"NON_INT_EVIDENCE_S_SPAN_{context_tag}: {sp!r}")
            if a < 0 or b <= a or b > text_len:
                raise ValueError(
                    f"OUT_OF_BOUNDS_EVIDENCE_S_SPAN_{context_tag}: [{a}, {b})"
                )
            explicit_intervals.append((a, b))

    merged_quotes = merge_intervals(derived_intervals)
    merged_explicit = merge_intervals(explicit_intervals)

    if label in (RelevanceState.REL_1, RelevanceState.REL_2):
        if not merged_quotes:
            raise ValueError(
                f"MISSING_VERBATIM_EVIDENCE_QUOTES_ON_POSITIVE_{context_tag}: "
                "REL_1/REL_2 requires >= 1 verbatim exact_quote with canonical_text_S offsets"
            )
        if merged_explicit and merged_explicit != merged_quotes:
            raise ValueError(
                f"EVIDENCE_SPAN_QUOTE_MISMATCH_{context_tag}: {merged_explicit} != {merged_quotes}"
            )
        final_spans = merged_quotes
    else:
        if merged_quotes or merged_explicit:
            raise ValueError(
                f"UNEXPECTED_SUPPORT_EVIDENCE_ON_NON_SUPPORTING_{context_tag}"
            )
        final_spans = []

    if final_spans and removed_audit_spans and _intervals_overlap(final_spans, removed_audit_spans):
        raise ValueError(
            f"EVIDENCE_SPAN_OVERLAPS_DELETED_R_AUDIT_MARKER_{context_tag}"
        )

    return lure_val, tuple(final_spans), tuple(verified_quotes)


def validate_single_annotator_submissions(
    packet_rows_or_path: Path | str | Sequence[Mapping[str, Any]],
    submissions: Sequence[Mapping[str, Any]],
    *,
    expected_annotator_id: str,
    removed_audit_spans_by_doc: Mapping[str, Sequence[tuple[int, int]]] | None = None,
) -> dict[tuple[str, str], ValidatedHumanVote]:
    """Validate one human annotator's full blinded packet submissions."""
    rows = load_and_verify_blind_packet_rows(packet_rows_or_path)
    by_uuid = {r["packet_item_uuid"]: r for r in rows}
    rem_map = {
        did: merge_intervals(list(sps))
        for did, sps in (removed_audit_spans_by_doc or {}).items()
    }

    validated: dict[tuple[str, str], ValidatedHumanVote] = {}
    seen_uuids: set[str] = set()

    for idx, sub in enumerate(submissions, start=1):
        if not isinstance(sub, Mapping):
            raise ValueError(f"INVALID_SUBMISSION_TYPE_AT_{idx}")
        if "fillna" in sub or "coerced" in sub:
            raise ValueError(f"FORBIDDEN_COERCION_FLAG_AT_{idx}")

        uid = _require_non_empty_str(
            sub.get("packet_item_uuid"), f"MISSING_UUID_AT_{idx}"
        )
        if uid not in by_uuid:
            raise ValueError(f"UNKNOWN_PACKET_ITEM_UUID_AT_{idx}: {uid!r}")
        if uid in seen_uuids:
            raise ValueError(f"DUPLICATE_SUBMISSION_UUID: {uid!r}")
        seen_uuids.add(uid)

        packet_row = by_uuid[uid]
        qid = _require_non_empty_str(sub.get("query_id"), f"MISSING_QID_AT_{idx}")
        did = _require_non_empty_str(sub.get("document_id"), f"MISSING_DID_AT_{idx}")
        if (qid, did) != (packet_row["query_id"], packet_row["document_id"]):
            raise ValueError(
                f"PACKET_PAIR_MISMATCH_AT_{idx}: {(qid, did)} != {(packet_row['query_id'], packet_row['document_id'])}"
            )

        ann_id = _require_non_empty_str(
            sub.get("annotator_id"), f"MISSING_ANNOTATOR_ID_AT_{idx}"
        )
        if ann_id != expected_annotator_id:
            raise ValueError(
                f"ANNOTATOR_ID_MISMATCH_AT_{idx}: {ann_id!r} != {expected_annotator_id!r}"
            )

        raw_label = sub.get("label")
        if type(raw_label) is not str or raw_label not in VALID_HUMAN_LABELS:
            raise ValueError(
                f"INVALID_HUMAN_LABEL_AT_{idx}: {raw_label!r} (must be REL_2|REL_1|REL_0|NA)"
            )
        state = RelevanceState(raw_label)

        lure_val, spans, quotes = _verify_vote_evidence_and_lure(
            canonical_text_s=packet_row["canonical_text_S"],
            label=state,
            raw_lure=sub.get("plausible_unsupported_lure"),
            raw_quotes=sub.get("evidence_quotes"),
            raw_spans=sub.get("evidence_s_spans"),
            removed_audit_spans=rem_map.get(did, ()),
            context_tag=f"{expected_annotator_id}_{qid}_{did}",
        )

        validated[(qid, did)] = ValidatedHumanVote(
            packet_item_uuid=uid,
            query_id=qid,
            document_id=did,
            annotator_id=expected_annotator_id,
            label=state,
            plausible_unsupported_lure=lure_val,
            evidence_s_spans=spans,
            evidence_quotes=quotes,
            rationale=sub.get("rationale") if isinstance(sub.get("rationale"), str) else None,
        )

    if len(validated) != len(rows):
        missing = sorted(
            {(r["query_id"], r["document_id"]) for r in rows} - set(validated.keys())
        )
        raise ValueError(
            f"INCOMPLETE_ANNOTATOR_SUBMISSIONS for {expected_annotator_id!r}: missing {len(missing)} items"
        )

    return validated


def build_adjudication_queue(
    packet_rows_or_path: Path | str | Sequence[Mapping[str, Any]],
    votes_a: Mapping[tuple[str, str], ValidatedHumanVote],
    votes_b: Mapping[tuple[str, str], ValidatedHumanVote],
) -> dict[str, Any]:
    """Compare two validated blinded annotator sets, compute kappa_w, and emit adjudication queue."""
    rows = load_and_verify_blind_packet_rows(packet_rows_or_path)
    expected_keys = {(r["query_id"], r["document_id"]) for r in rows}
    if set(votes_a.keys()) != expected_keys or set(votes_b.keys()) != expected_keys:
        raise ValueError("VOTE_SETS_DO_NOT_MATCH_BLIND_PACKET_KEYS")

    exact_label_matches = 0
    exact_full_matches = 0
    grades_a: list[int] = []
    grades_b: list[int] = []
    disagreement_items: list[dict[str, Any]] = []

    for row in rows:
        pair = (row["query_id"], row["document_id"])
        va = votes_a[pair]
        vb = votes_b[pair]

        if va.label.value in _GRADE_TO_INT and vb.label.value in _GRADE_TO_INT:
            grades_a.append(_GRADE_TO_INT[va.label.value])
            grades_b.append(_GRADE_TO_INT[vb.label.value])

        reasons: list[str] = []
        if va.label != vb.label:
            if va.label == RelevanceState.NA or vb.label == RelevanceState.NA:
                reasons.append("NA_CONFLICT")
            else:
                reasons.append("GRADE_MISMATCH")
        else:
            exact_label_matches += 1
            if (
                va.label == RelevanceState.REL_0
                and va.plausible_unsupported_lure != vb.plausible_unsupported_lure
            ):
                reasons.append("LURE_MISMATCH")
            elif va.label in (RelevanceState.REL_1, RelevanceState.REL_2):
                # Same positive grade, check whether evidence intervals intersect at all
                if not _intervals_overlap(va.evidence_s_spans, vb.evidence_s_spans):
                    reasons.append("DISJOINT_EVIDENCE_SPANS")

        if not reasons:
            exact_full_matches += 1
            continue

        disagreement_items.append(
            {
                "packet_item_uuid": row["packet_item_uuid"],
                "query_id": row["query_id"],
                "query_text": row["query_text"],
                "document_id": row["document_id"],
                "source_type": row["source_type"],
                "language": row["language"],
                "canonical_text_S": row["canonical_text_S"],
                "disagreement_reasons": reasons,
                "annotator_01_vote": {
                    "annotator_id": va.annotator_id,
                    "label": va.label.value,
                    "plausible_unsupported_lure": va.plausible_unsupported_lure,
                    "evidence_s_spans": [list(sp) for sp in va.evidence_s_spans],
                    "evidence_quotes": list(va.evidence_quotes),
                },
                "annotator_02_vote": {
                    "annotator_id": vb.annotator_id,
                    "label": vb.label.value,
                    "plausible_unsupported_lure": vb.plausible_unsupported_lure,
                    "evidence_s_spans": [list(sp) for sp in vb.evidence_s_spans],
                    "evidence_quotes": list(vb.evidence_quotes),
                },
                "adjudicated_label": None,
                "adjudicated_plausible_unsupported_lure": None,
                "adjudicated_evidence_quotes": [],
                "adjudication_rationale": "",
            }
        )

    total = len(rows)
    kappa_w = quadratic_weighted_kappa(grades_a, grades_b) if grades_a else None
    return {
        "schema_version": ADJUDICATION_QUEUE_SCHEMA_V1,
        "total_items": total,
        "exact_label_agreement_count": exact_label_matches,
        "exact_full_agreement_count": exact_full_matches,
        "exact_label_agreement_rate": round(exact_label_matches / total, 6),
        "exact_full_agreement_rate": round(exact_full_matches / total, 6),
        "pre_adjudication_kappa_w_shared_012": (
            round(kappa_w, 6) if kappa_w is not None else None
        ),
        "shared_012_count": len(grades_a),
        "disagreements_count": len(disagreement_items),
        "disagreement_items": disagreement_items,
    }


def compile_adjudicated_qrels(
    *,
    packet_rows_or_path: Path | str | Sequence[Mapping[str, Any]],
    votes_a: Mapping[tuple[str, str], ValidatedHumanVote],
    votes_b: Mapping[tuple[str, str], ValidatedHumanVote],
    adjudicator_resolutions: Sequence[Mapping[str, Any]],
    roster_obj: Mapping[str, Any],
    removed_audit_spans_by_doc: Mapping[str, Sequence[tuple[int, int]]] | None = None,
    source_lineage_by_doc: Mapping[str, str | None] | None = None,
    top10_by_q_cell: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    all_doc_ids: Sequence[str] | None = None,
    pool_doc_ids_by_q: Mapping[str, Sequence[str]] | None = None,
    answerable_qids: Sequence[str] | None = None,
    qrels_out_path: Path | None = None,
    require_formal_roster: bool = False,
) -> dict[str, Any]:
    """Compile validated 2+1 adjudicated ground truth into native G4 QrelRecord JSONL."""
    roster = validate_human_roster_receipt(
        roster_obj, require_formal_commitment=require_formal_roster
    )
    adj_id = roster["human_adjudicator_03_id"]
    rows = load_and_verify_blind_packet_rows(packet_rows_or_path)
    queue = build_adjudication_queue(rows, votes_a, votes_b)

    rem_map = {
        did: merge_intervals(list(sps))
        for did, sps in (removed_audit_spans_by_doc or {}).items()
    }
    row_by_pair = {(r["query_id"], r["document_id"]): r for r in rows}

    discordant_pairs = {
        (item["query_id"], item["document_id"])
        for item in queue["disagreement_items"]
    }
    res_by_pair: dict[tuple[str, str], ValidatedHumanVote] = {}

    for idx, res in enumerate(adjudicator_resolutions, start=1):
        if not isinstance(res, Mapping):
            raise ValueError(f"INVALID_ADJUDICATION_ENTRY_TYPE_AT_{idx}")
        res_adj_id = _require_non_empty_str(
            res.get("adjudicator_id"), f"MISSING_ADJUDICATOR_ID_AT_{idx}"
        )
        if res_adj_id != adj_id:
            raise ValueError(
                f"ADJUDICATOR_ID_MISMATCH_AT_{idx}: {res_adj_id!r} != {adj_id!r}"
            )
        if res_adj_id in (
            roster["human_annotator_01_id"],
            roster["human_annotator_02_id"],
        ):
            raise ValueError("ADJUDICATOR_MUST_BE_DISTINCT_FROM_ANNOTATORS")

        qid = _require_non_empty_str(res.get("query_id"), f"MISSING_ADJ_QID_AT_{idx}")
        did = _require_non_empty_str(res.get("document_id"), f"MISSING_ADJ_DID_AT_{idx}")
        pair = (qid, did)
        if pair not in row_by_pair:
            raise ValueError(f"UNKNOWN_ADJUDICATION_PAIR_AT_{idx}: {pair!r}")
        if pair in res_by_pair:
            raise ValueError(f"DUPLICATE_ADJUDICATION_PAIR: {pair!r}")

        pkt_row = row_by_pair[pair]
        uid = _require_non_empty_str(
            res.get("packet_item_uuid"), f"MISSING_ADJ_UUID_AT_{idx}"
        )
        if uid != pkt_row["packet_item_uuid"]:
            raise ValueError(f"ADJUDICATION_UUID_MISMATCH_AT_{idx}")

        raw_label = res.get("label")
        if type(raw_label) is not str or raw_label not in VALID_HUMAN_LABELS:
            raise ValueError(
                f"INVALID_ADJUDICATED_LABEL_AT_{idx}: {raw_label!r}"
            )
        state = RelevanceState(raw_label)

        lure_val, spans, quotes = _verify_vote_evidence_and_lure(
            canonical_text_s=pkt_row["canonical_text_S"],
            label=state,
            raw_lure=res.get("plausible_unsupported_lure"),
            raw_quotes=res.get("evidence_quotes"),
            raw_spans=res.get("evidence_s_spans"),
            removed_audit_spans=rem_map.get(did, ()),
            context_tag=f"ADJ_{qid}_{did}",
        )
        res_by_pair[pair] = ValidatedHumanVote(
            packet_item_uuid=uid,
            query_id=qid,
            document_id=did,
            annotator_id=adj_id,
            label=state,
            plausible_unsupported_lure=lure_val,
            evidence_s_spans=spans,
            evidence_quotes=quotes,
            rationale=res.get("rationale") if isinstance(res.get("rationale"), str) else None,
        )

    missing_adj = sorted(discordant_pairs - set(res_by_pair.keys()))
    if missing_adj:
        raise ValueError(
            f"UNRESOLVED_ADJUDICATION_ITEMS: {len(missing_adj)} discordant pairs missing: {missing_adj[:5]}"
        )

    qrel_dicts: list[dict[str, Any]] = []
    lineage_map = dict(source_lineage_by_doc or {})
    qrel_records_by_q: dict[tuple[str, str], QrelRecord] = {}

    for pair in sorted(row_by_pair.keys()):
        qid, did = pair
        va = votes_a[pair]
        vb = votes_b[pair]
        if pair in res_by_pair:
            chosen = res_by_pair[pair]
            final_label = chosen.label
            final_lure = chosen.plausible_unsupported_lure
            final_spans = list(chosen.evidence_s_spans)
            resolution_mode = "HUMAN_ADJUDICATOR_03"
        else:
            final_label = va.label
            final_lure = va.plausible_unsupported_lure
            # For agreed REL_1/REL_2 with overlapping support, preserve verified union of spans
            final_spans = (
                merge_intervals(list(va.evidence_s_spans) + list(vb.evidence_s_spans))
                if final_label in (RelevanceState.REL_1, RelevanceState.REL_2)
                else []
            )
            resolution_mode = "DUAL_HUMAN_AGREEMENT"

        lineage = lineage_map.get(did)
        record_obj: dict[str, Any] = {
            "query_id": qid,
            "document_id": did,
            "label": final_label.value,
            "evidence_s_spans": [[a, b] for a, b in final_spans],
            "resolution_mode": resolution_mode,
        }
        if final_lure is not None:
            record_obj["plausible_unsupported_lure"] = final_lure
        if isinstance(lineage, str) and lineage.strip():
            record_obj["source_lineage_id"] = lineage.strip()
        qrel_dicts.append(record_obj)
        qrel_records_by_q[pair] = QrelRecord(
            query_id=qid,
            document_id=did,
            label=final_label,
            plausible_unsupported_lure=final_lure,
            evidence_s_spans=tuple(final_spans),
            source_lineage_id=lineage.strip() if isinstance(lineage, str) and lineage.strip() else None,
        )

    qrels_bytes = (
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in qrel_dicts) + "\n"
    ).encode("utf-8")
    qrels_sha = sha256_bytes(qrels_bytes)
    if qrels_out_path is not None:
        qrels_out_path.parent.mkdir(parents=True, exist_ok=True)
        qrels_out_path.write_bytes(qrels_bytes)
        # Round-trip sanity check with G4 contracts loader
        reloaded = load_external_qrels(qrels_out_path)
        if len(reloaded) != len(qrel_dicts):
            raise AssertionError("Compiled qrels round-trip verification mismatch")

    cert_summary: dict[str, Any] | None = None
    if top10_by_q_cell is not None:
        doc_universe = sorted(
            set(all_doc_ids or ()) | {r["document_id"] for r in rows}
        )
        per_q_certs = {}
        for qid in sorted({r["query_id"] for r in rows}):
            cert = compute_query_certificates(
                qid,
                top10_by_q_cell.get(qid, {}),
                doc_universe,
                qrel_records_by_q,
                pool_doc_ids=(
                    pool_doc_ids_by_q.get(qid) if pool_doc_ids_by_q else None
                ),
            )
            min_cert2 = (
                min(cert.cert2_judged_at_10.values())
                if cert.cert2_judged_at_10
                else 1.0
            )
            per_q_certs[qid] = {
                "cert4_status": cert.cert4_status.value,
                "cert1_top10_in_pool": cert.cert1_top10_in_pool,
                "cert2_min_judged_at_10": min_cert2,
                "cert3_full_pool_closed": cert.cert3_full_pool_closed,
                "known_count": cert.known_count,
                "unjudged_count": cert.unjudged_count,
                "zero_exact_empty_z": cert.zero_exact_empty_z,
            }
        ans_set = (
            set(answerable_qids)
            if answerable_qids is not None
            else set(per_q_certs.keys())
        )
        cert_summary = {
            "query_count": len(per_q_certs),
            "answerable_count": len(ans_set),
            "per_query": per_q_certs,
            "all_cert1_to_cert3_and_cert4_valid": all(
                v["cert1_top10_in_pool"] >= 1.0 - 1e-12
                and v["cert3_full_pool_closed"] >= 1.0 - 1e-12
                and (
                    qid not in ans_set
                    or (
                        v["cert2_min_judged_at_10"] >= 1.0 - 1e-12
                        and v["cert4_status"] != "INVALID_UNRESOLVED"
                    )
                )
                for qid, v in per_q_certs.items()
            ),
        }

    return {
        "schema_version": HUMAN_QREL_COMPILATION_SCHEMA_V1,
        "od_g15_05_route": roster["od_g15_05_route"],
        "roster": roster,
        "total_qrels_compiled": len(qrel_dicts),
        "qrels_jsonl_sha256": qrels_sha,
        "adjudication_stats": {
            "pre_adjudication_kappa_w_shared_012": queue[
                "pre_adjudication_kappa_w_shared_012"
            ],
            "exact_label_agreement_rate": queue["exact_label_agreement_rate"],
            "exact_full_agreement_rate": queue["exact_full_agreement_rate"],
            "disagreements_resolved": len(discordant_pairs),
        },
        "cert_summary": cert_summary,
        "qrel_rows": qrel_dicts,
    }
