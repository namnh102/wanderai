#!/usr/bin/env python3
"""W07-A4H Assisted First-Party Review Collection Importer & Combined Pilot Progress Tracker (v1, Corrective 01).

Responsibilities:
1. Verify upstream scientific immutability (W06, W07-0, W07-A1, W07-A2 60-POI manifest,
   and W07-A3 Google Forms definitions, Apps Script generator, and progress artifact).
2. Deterministically import assisted first-party review CSV files modeled on the 16-column
   `data/templates/w07_assisted_first_party_review_template_v1.csv` into
   `data/restricted/w07_reviews/w07_assisted_candidate_reviews_v1.jsonl` without
   modifying or overwriting the W07-A3 Google Forms corpus
   (`data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl`).
3. Corrective 01 Hardening:
   - Strict `language` validation (`vi`, `en`, `mixed_vi_en`) with zero implicit `"vi"` default
     (`REJECT_INVALID_OR_MISSING_LANGUAGE`).
   - Fail-closed timestamp parsing for `consent_timestamp` and `collected_at` with zero fixed-date
     fallback (`REJECT_MISSING_CONSENT_TIMESTAMP`, `REJECT_INVALID_CONSENT_TIMESTAMP`,
     `REJECT_MISSING_COLLECTED_AT`, `REJECT_INVALID_COLLECTED_AT`).
   - Explicit `created_at` semantics: `created_at = date review was collected/submitted into assisted intake`
     (derived strictly from valid normalized `collected_at`, never claimed to be the visit date;
     `visit_period` remains separate).
   - Unconditional internal assignment of `source`, `provenance`, `license_or_usage_class`,
     `mapping_method`, and `mapping_confidence` (never accepted from CSV input).
   - Unexpected-column firewall (`REJECT_UNEXPECTED_INPUT_COLUMN`) rejecting any non-identity column
     outside the 16 canonical template columns (including `source`, `provenance`,
     `license_or_usage_class`, `mapping_method`, `mapping_confidence`, `review_id`, `consent_record_id`).
4. Generate and verify the combined first-party progress artifact
   `data/evaluation/w07/w07_first_party_collection_progress_v1.json` across both
   first-party channels (`DIRECT_GOOGLE_FORM` + `ASSISTED_FIRST_PARTY_COLLECTION`).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import (  # noqa: E402
    import_w07_contributor_reviews_v1 as w07_a3_import,
    report_w07_review_collection_progress as w07_a3_progress,
    validate_w07_review_corpus_v1 as w07_a2,
)

ASSISTED_TEMPLATE_CSV_RELPATH = (
    "data/templates/w07_assisted_first_party_review_template_v1.csv"
)
ASSISTED_CANDIDATE_JSONL_RELPATH = (
    "data/restricted/w07_reviews/w07_assisted_candidate_reviews_v1.jsonl"
)
RAW_ASSISTED_CSV_DEFAULT_RELPATH = (
    "data/restricted/w07_reviews/raw_assisted/assisted_reviews.csv"
)
RESTRICTED_IDENTITY_MAP_RELPATH = (
    "data/restricted/w07_reviews/contributors/contributor_identity_map.csv"
)
RESTRICTED_CONSENT_EVIDENCE_DIR_RELPATH = (
    "data/restricted/w07_reviews/consent_evidence"
)
COMBINED_FIRST_PARTY_PROGRESS_JSON_RELPATH = (
    "data/evaluation/w07/w07_first_party_collection_progress_v1.json"
)
ASSISTED_COLLECTION_GUIDE_MD_RELPATH = (
    "docs/research/w07_assisted_first_party_collection_guide.md"
)

AUTHORITATIVE_DEVELOP_BASE_SHA = "61e58f0fed2539971584c49cd7a2dac159554ff7"
PREVIOUS_GATES: tuple[str, ...] = (
    "W07-A3-CONTRIBUTOR-COLLECTION-LAUNCH-POSTMERGE-CHATGPT-AUDIT = PASS",
    "W07-A3-OWNER-GOOGLE-FORMS-RUNTIME-PREFLIGHT-CHATGPT-AUDIT = PASS",
    "W07-A4H-ASSISTED-FIRST-PARTY-COLLECTION-PIPELINE-CHATGPT-AUDIT = HOLD-CORRECTIVE",
)
NEXT_GATE = "W07-A4H-ASSISTED-FIRST-PARTY-COLLECTION-CORRECTIVE-01-CHATGPT-AUDIT"

EXPECTED_A3_FORM_DEF_INTERNAL_SHA256 = (
    "9c17cfc51c41295c8338b40544324454a36a7276bb2339edd3a0b59c88c6de8a"
)
EXPECTED_A3_APPS_SCRIPT_LF_SHA256 = (
    "5e87dcf74d2bc4840792701bbd852c75781ef6ba938ac8c1eacad6d2a430be71"
)
EXPECTED_A3_PROGRESS_INTERNAL_SHA256 = (
    "a7eb47e50735a6f184f4ae717976b7a8bf7d1258a6d4763031c62fd691d38e70"
)

ASSISTED_ACQUISITION_CHANNEL = "ASSISTED_FIRST_PARTY_COLLECTION"
DIRECT_FORM_ACQUISITION_CHANNEL = "DIRECT_GOOGLE_FORM"

ASSISTED_SOURCE_VALUE = "assisted_first_party"
ASSISTED_PROVENANCE_CLASS = "FIRST_PARTY_ASSISTED_COLLECTION_CONSENT_V1"
GOOGLE_FORMS_PROVENANCE_CLASS = "FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1"
ASSISTED_LICENSE_OR_USAGE_CLASS = "OWNER_FIRST_PARTY_CONSENT"
ASSISTED_MAPPING_METHOD = "EXACT_PREBOUND_CANONICAL_POI"
ASSISTED_MAPPING_CONFIDENCE = 1.0

CREATED_AT_SEMANTIC_DEFINITION = (
    "created_at = date review was collected/submitted into assisted intake "
    "(derived strictly from valid normalized collected_at; never claimed to be the visit date; "
    "visit_period remains separate)"
)

CONSENT_PROTOCOL_VERSION = "W07_ASSISTED_CONSENT_V1"
ASSISTED_IMPORTER_VERSION = "1.1.0-corrective-01"

REQUIRED_TEMPLATE_COLUMNS: tuple[str, ...] = (
    "contributor_code",
    "poi_id",
    "city",
    "rating",
    "review_text",
    "language",
    "visit_period",
    "collection_channel",
    "capture_mode",
    "review_text_approved",
    "consent_confirmed",
    "consent_timestamp",
    "consent_evidence_type",
    "consent_evidence_ref",
    "collector_code",
    "collected_at",
)

ALLOWED_LANGUAGE_VALUES: tuple[str, ...] = (
    "vi",
    "en",
    "mixed_vi_en",
)

SUPPORTED_CAPTURE_MODES: tuple[str, ...] = (
    "CONTRIBUTOR_WRITTEN_VERBATIM",
    "COLLECTOR_TRANSCRIBED_VERBATIM",
    "COLLECTOR_TRANSCRIBED_AND_CONTRIBUTOR_APPROVED",
)

TRANSCRIPTION_CAPTURE_MODES: frozenset[str] = frozenset(
    {
        "COLLECTOR_TRANSCRIBED_VERBATIM",
        "COLLECTOR_TRANSCRIBED_AND_CONTRIBUTOR_APPROVED",
    }
)

FORBIDDEN_CAPTURE_MODES: frozenset[str] = frozenset(
    {
        "COLLECTOR_PARAPHRASED",
        "AI_REWRITTEN",
        "AI_GENERATED",
        "COPIED_ONLINE_REVIEW",
        "OWNER_INVENTED",
        "COLLECTOR_INVENTED",
    }
)

SUPPORTED_COLLECTION_CHANNELS: tuple[str, ...] = (
    "ZALO",
    "MESSENGER",
    "DIRECT_CHAT",
    "IN_PERSON_INTERVIEW",
    "PHONE_WITH_WRITTEN_CONFIRMATION",
)

SUPPORTED_CONSENT_EVIDENCE_TYPES: tuple[str, ...] = (
    "CHAT_WRITTEN_CONSENT",
    "DIGITAL_TEXT_CONSENT",
    "IN_PERSON_WRITTEN_CONSENT",
)

FORBIDDEN_CONSENT_EVIDENCE_TYPES: frozenset[str] = frozenset(
    {
        "VERBAL_ONLY",
        "ORAL_ONLY",
        "UNDOCUMENTED_VERBAL",
        "IMPLIED_SILENCE",
        "SILENCE",
        "NONE",
        "NO_CONSENT",
    }
)

FORBIDDEN_COPIED_ONLINE_SUBSTRINGS: tuple[str, ...] = (
    "copied_online",
    "google_maps",
    "google maps",
    "tripadvisor",
    "booking.com",
    "booking_review",
    "agoda",
    "foody",
    "scraped",
    "web_scrape",
    "online_copy",
)

FORBIDDEN_AI_SUBSTRINGS: tuple[str, ...] = (
    "chatgpt",
    "gemini",
    "claude",
    "openai",
    "anthropic",
    "llm",
    "synthetic",
    "ai_generated",
    "ai_rewritten",
    "ai_paraphrase",
    "collector_paraphrased",
    "owner_invented",
)

ASSISTED_IDENTITY_COLUMN_PATTERNS: tuple[str, ...] = (
    "real_name",
    "full_name",
    "author_name",
    "contributor_real_name",
    "contributor_name",
    "họ và tên",
    "họ tên",
    "tên thật",
    "email",
    "e-mail",
    "phone",
    "phone_number",
    "số điện thoại",
    "điện thoại",
    "facebook",
    "zalo_id",
    "zalo_handle",
    "zalo_phone",
    "messenger_id",
    "account_handle",
    "social_account",
    "home_address",
    "địa chỉ nhà",
    "student_id",
    "mssv",
    "mã sinh viên",
    "national_id",
    "cccd",
    "cmnd",
)

CONTRIBUTOR_CODE_RE = re.compile(r"^W07C\d{3,6}$")
COLLECTOR_CODE_RE = re.compile(r"^[A-Z0-9_]{2,32}$")

CITY_CODE_BY_CANONICAL_CITY: dict[str, str] = {
    "Hà Nội": "hn",
    "Đà Nẵng": "dn",
    "Hạ Long": "hl",
}

RECRUITMENT_MESSAGE_VI = (
    "Bọn mình đang làm đồ án GoMate về gợi ý du lịch. Nếu bạn từng đi một trong các địa điểm "
    "trong danh sách, mình muốn xin đánh giá thật của bạn (1–5 điểm + vài câu cảm nhận). "
    "Nội dung sẽ ẩn danh và chỉ dùng cho đồ án/nghiên cứu. Chỉ đánh giá địa điểm bạn thực sự từng trải nghiệm."
)

CONSENT_SCRIPT_VI = (
    "Bạn xác nhận rằng bạn đã trực tiếp đến/trải nghiệm địa điểm này, nội dung đánh giá là ý kiến "
    "của chính bạn, không sao chép từ Google Maps/Tripadvisor/Booking/Agoda/Foody và không dùng AI "
    "(ChatGPT, Gemini, Claude). Việc tham gia là hoàn toàn tự nguyện và bạn đồng ý cho đồ án GoMate "
    "sử dụng nội dung này dưới dạng ẩn danh cho nghiên cứu, đánh giá và demo học thuật phi thương mại. "
    "Nếu đồng ý, bạn nhắn giúp mình: \"Tôi đồng ý\" hoặc \"Đồng ý\" nhé."
)

TRANSCRIPTION_APPROVAL_SCRIPT_VI = (
    "Mình vừa ghi lại nguyên văn đánh giá của bạn cho địa điểm [Tên POI] (Điểm: [1–5]/5) như sau:\n"
    "\"[Nội dung đánh giá cuối cùng]\"\n"
    "Bạn kiểm tra giúp mình xem nội dung đã đúng hoàn toàn ý của bạn chưa, và nhắn xác nhận "
    "\"Tôi duyệt nội dung và đồng ý\" để mình lưu vào bộ dữ liệu nghiên cứu ẩn danh nhé."
)


def verify_upstream_a2_and_a3_immutability(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify W06, W07-0, W07-A1, W07-A2, and W07-A3 committed artifacts remain unchanged."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(repo_root)
    a3_form_res = w07_a3_import.verify_form_definition_artifacts(repo_root)
    a3_prog_res = w07_a3_progress.verify_collection_progress_artifact(repo_root)

    if a3_form_res["form_definition_internal_sha256"] != EXPECTED_A3_FORM_DEF_INTERNAL_SHA256:
        raise ValueError(
            "FAIL CLOSED: W07-A3 form definition internal SHA256 mismatch: "
            f"{a3_form_res['form_definition_internal_sha256']}"
        )
    if a3_form_res["apps_script_lf_sha256"] != EXPECTED_A3_APPS_SCRIPT_LF_SHA256:
        raise ValueError(
            "FAIL CLOSED: W07-A3 Apps Script LF SHA256 mismatch: "
            f"{a3_form_res['apps_script_lf_sha256']}"
        )
    if a3_prog_res["progress_internal_sha256"] != EXPECTED_A3_PROGRESS_INTERNAL_SHA256:
        raise ValueError(
            "FAIL CLOSED: W07-A3 progress internal SHA256 mismatch: "
            f"{a3_prog_res['progress_internal_sha256']}"
        )

    return {
        "a2_manifest_internal_sha256": manifest["manifest_sha256"],
        "a3_form_definition_internal_sha256": a3_form_res["form_definition_internal_sha256"],
        "a3_apps_script_lf_sha256": a3_form_res["apps_script_lf_sha256"],
        "a3_progress_internal_sha256": a3_prog_res["progress_internal_sha256"],
    }


def verify_assisted_template_csv(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify the committed assisted CSV template has the exact 16 required columns and zero real reviews."""
    template_path = repo_root / ASSISTED_TEMPLATE_CSV_RELPATH
    if not template_path.exists():
        raise FileNotFoundError(f"Missing assisted template CSV: {template_path}")

    with template_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError("Assisted CSV template is empty (missing header row).")

    header = [c.strip() for c in rows[0]]
    if tuple(header) != REQUIRED_TEMPLATE_COLUMNS:
        raise ValueError(
            f"Assisted CSV template header mismatch: got={header}, expected={list(REQUIRED_TEMPLATE_COLUMNS)}"
        )

    for col in header:
        if _is_assisted_identity_column(col):
            raise ValueError(f"Forbidden identity column in assisted template header: {col}")

    data_rows = [r for r in rows[1:] if any(cell.strip() for cell in r)]
    if data_rows:
        raise ValueError(
            f"Assisted CSV template must be header-only in committed repo, found {len(data_rows)} data rows."
        )

    return {
        "template_path": ASSISTED_TEMPLATE_CSV_RELPATH,
        "template_lf_sha256": w07_a2.compute_lf_normalized_sha256(template_path),
        "column_count": len(REQUIRED_TEMPLATE_COLUMNS),
        "columns": list(REQUIRED_TEMPLATE_COLUMNS),
        "data_row_count": len(data_rows),
    }


def _is_assisted_identity_column(col_name: str) -> bool:
    norm = col_name.strip().lower()
    if norm in set(REQUIRED_TEMPLATE_COLUMNS):
        return False
    return any(pat in norm for pat in ASSISTED_IDENTITY_COLUMN_PATTERNS)


def partition_assisted_input_columns(
    raw_row: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Partition raw CSV row columns into `(canonical_sanitized, stripped_identity_cols, unexpected_cols)`.

    Section 7 Unexpected-column firewall:
    - Columns in the 16 `REQUIRED_TEMPLATE_COLUMNS` are retained in `canonical_sanitized`.
    - Known accidental identity columns (`_is_assisted_identity_column`) are stripped and recorded in `stripped_identity_cols`.
    - Any other column (such as `source`, `provenance`, `license_or_usage_class`, `mapping_method`,
      `mapping_confidence`, `review_id`, `consent_record_id`, or unknown columns) is rejected via
      `unexpected_cols` (`REJECT_UNEXPECTED_INPUT_COLUMN`) and never copied into `canonical_sanitized`.
    """
    canonical_set = set(REQUIRED_TEMPLATE_COLUMNS)
    sanitized: dict[str, Any] = {}
    stripped_identity: list[str] = []
    unexpected: list[str] = []

    for k, v in raw_row.items():
        if k is None:
            if v is not None and any(str(cell).strip() for cell in (v if isinstance(v, list) else [v])):
                unexpected.append("<extra_unnamed_column>")
            continue
        k_clean = str(k).strip()
        if k_clean in canonical_set:
            sanitized[k_clean] = v
        elif _is_assisted_identity_column(k_clean):
            stripped_identity.append(k_clean)
        else:
            unexpected.append(k_clean)

    return sanitized, stripped_identity, unexpected


def strip_assisted_identity_columns(
    raw_row: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Strip known accidental identity columns and return `(canonical_sanitized, stripped_identity_cols)`."""
    sanitized, stripped_identity, _ = partition_assisted_input_columns(raw_row)
    return sanitized, stripped_identity


def parse_strict_assisted_timestamp(raw_ts: str) -> tuple[str, str] | None:
    """Strictly parse an assisted timestamp string into `(YYYY-MM-DD, YYYY-MM-DDTHH:MM:SSZ)`.

    Section 4 & 5:
    - Fail-closed on empty or malformed timestamps (returns `None`).
    - Never uses any hard-coded date/time fallback.
    """
    ts = raw_ts.strip()
    if not ts:
        return None

    # 1. Exact format candidates (without silent truncation of trailing garbage)
    exact_formats = (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d",
    )
    for fmt in exact_formats:
        try:
            parsed = dt.datetime.strptime(ts, fmt)
            return (
                parsed.strftime("%Y-%m-%d"),
                parsed.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        except ValueError:
            continue

    # 2. ISO-8601 with explicit timezone offset
    if "T" in ts and (ts.endswith("Z") or "+" in ts[10:] or "-" in ts[10:]):
        iso_candidate = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
        try:
            parsed_tz = dt.datetime.fromisoformat(iso_candidate)
            if parsed_tz.tzinfo is not None:
                parsed_utc = parsed_tz.astimezone(dt.timezone.utc)
                return (
                    parsed_utc.strftime("%Y-%m-%d"),
                    parsed_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
        except ValueError:
            return None

    return None


def normalize_contributor_code(raw_code: str) -> str | None:
    """Normalize and validate pseudonymous contributor code (`W07C001`..`W07C999999`)."""
    val = raw_code.strip().upper()
    if not val:
        return None
    if w07_a2.EMAIL_RE.search(val) or w07_a2.PHONE_RE.search(val):
        return None
    if not CONTRIBUTOR_CODE_RE.match(val):
        return None
    return val


def validate_language_value(raw_lang: str) -> str | None:
    """Validate `language` strictly against `ALLOWED_LANGUAGE_VALUES` (`vi`, `en`, `mixed_vi_en`).

    Sections 2 & 3:
    - No automatic default to `"vi"`.
    - Returns normalized allowed string if valid, else `None`.
    """
    val = raw_lang.strip().lower()
    if val in ALLOWED_LANGUAGE_VALUES:
        return val
    return None


def _is_explicit_consent_confirmed(raw_val: str) -> bool:
    val = raw_val.strip().lower()
    if not val:
        return False
    if val in {
        "false",
        "no",
        "0",
        "không",
        "khong",
        "none",
        "null",
        "n/a",
        "silence",
        "im lặng",
        "chưa",
        "chua",
    }:
        return False
    affirmative = {
        "true",
        "yes",
        "1",
        "tôi đồng ý",
        "toi dong y",
        "đồng ý",
        "dong y",
        "tôi xác nhận",
        "toi xac nhan",
        "tôi duyệt nội dung và đồng ý",
        "toi duyet noi dung va dong y",
        "confirmed",
        "agreed",
        "i agree",
    }
    if val in affirmative:
        return True
    return any(tok in val for tok in ("tôi đồng ý", "toi dong y", "đồng ý", "dong y"))


def _is_review_text_approved(raw_val: str, *, capture_mode: str, consent_ok: bool) -> bool:
    val = raw_val.strip().lower()
    explicit_false = {"false", "no", "0", "không", "khong", "chưa", "chua", "rejected", "unapproved"}
    explicit_true = {
        "true",
        "yes",
        "1",
        "approved",
        "đã duyệt",
        "da duyet",
        "tôi duyệt",
        "toi duyet",
        "tôi đồng ý",
        "toi dong y",
        "đồng ý",
        "dong y",
    }
    if val in explicit_false:
        return False
    if val in explicit_true:
        return True
    # Section 12: For CONTRIBUTOR_WRITTEN_VERBATIM, review_text_approved=true may be implied by
    # direct written submission plus explicit consent if the cell was left blank.
    if capture_mode == "CONTRIBUTOR_WRITTEN_VERBATIM" and val == "" and consent_ok:
        return True
    # For transcription modes, explicit final-text approval is mandatory!
    return False


def generate_assisted_consent_record_id(
    *,
    consent_protocol_version: str = CONSENT_PROTOCOL_VERSION,
    contributor_code: str,
    poi_id: str,
    consent_timestamp: str,
    consent_evidence_type: str,
    consent_evidence_ref: str,
) -> str:
    """Deterministically generate a non-reversible `consent_record_id` for assisted collection (Section 11).

    Binds:
    - consent_protocol_version
    - contributor_code
    - poi_id
    - consent_timestamp
    - consent_evidence_type
    - normalized_consent_evidence_digest (SHA256 of normalized consent_evidence_ref)
    Never encodes name, phone, email, or account handle.
    """
    norm_ref = re.sub(r"\s+", " ", consent_evidence_ref.strip()).lower()
    evidence_digest = hashlib.sha256(norm_ref.encode("utf-8")).hexdigest()
    binding_payload = {
        "consent_evidence_type": consent_evidence_type.strip().upper(),
        "consent_protocol_version": consent_protocol_version.strip(),
        "consent_timestamp": consent_timestamp.strip(),
        "contributor_code": contributor_code.strip().upper(),
        "normalized_consent_evidence_digest": evidence_digest,
        "poi_id": poi_id.strip().lower(),
    }
    canon = json.dumps(
        binding_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(canon).hexdigest()
    return f"consent_w07_assisted_v1_{digest[:24]}"


def generate_assisted_review_id(
    *,
    contributor_code: str,
    poi_id: str,
    city_code: str,
    rating_str: str,
    review_text: str,
    language: str,
    visit_period: str | None,
    capture_mode: str,
) -> str:
    """Deterministically generate `review_id` from non-sensitive scientific fields (Section 15)."""
    seed_payload = {
        "capture_mode": capture_mode.strip().upper(),
        "city_code": city_code.strip().lower(),
        "contributor_code": contributor_code.strip().upper(),
        "importer_version": ASSISTED_IMPORTER_VERSION,
        "language": language.strip().lower(),
        "poi_id": poi_id.strip().lower(),
        "rating": rating_str.strip(),
        "review_text_sha256": hashlib.sha256(review_text.encode("utf-8")).hexdigest(),
        "visit_period": (visit_period or "").strip(),
    }
    canon = json.dumps(
        seed_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(canon).hexdigest()
    return f"w07_arev_{city_code.strip().lower()}_{digest[:16]}"


def generate_assisted_author_anonymous_id(contributor_code: str) -> str:
    """Deterministic pseudonymous contributor identifier preserving same-contributor grouping across POIs."""
    norm_code = contributor_code.strip().upper()
    return f"contrib_{norm_code.lower()}"


def convert_assisted_csv_row_to_candidate(
    raw_row: dict[str, Any],
    *,
    manifest_payload: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Convert one assisted CSV row into `(candidate_row, assisted_rejection_reasons, stripped_identity_cols)`.

    Enforces Corrective 01 rules:
    - Unexpected non-identity columns trigger `REJECT_UNEXPECTED_INPUT_COLUMN`.
    - `language` must be explicitly `vi`, `en`, or `mixed_vi_en` (`REJECT_INVALID_OR_MISSING_LANGUAGE`).
    - `consent_timestamp` and `collected_at` must be present and strictly parsable (`REJECT_MISSING_CONSENT_TIMESTAMP`,
      `REJECT_INVALID_CONSENT_TIMESTAMP`, `REJECT_MISSING_COLLECTED_AT`, `REJECT_INVALID_COLLECTED_AT`).
    - `source`, `provenance`, `license_or_usage_class`, `mapping_method`, and `mapping_confidence` are assigned
      internally and unconditionally.
    """
    sanitized, stripped_cols, unexpected_cols = partition_assisted_input_columns(raw_row)
    reasons: list[str] = []

    if unexpected_cols:
        reasons.append("REJECT_UNEXPECTED_INPUT_COLUMN")
        for ucol in sorted(set(unexpected_cols)):
            reasons.append(f"REJECT_UNEXPECTED_INPUT_COLUMN:{ucol}")

    raw_contrib = str(sanitized.get("contributor_code") or "").strip()
    norm_contrib = normalize_contributor_code(raw_contrib)
    if norm_contrib is None:
        reasons.append("REJECT_INVALID_CONTRIBUTOR_CODE")

    raw_poi_id = str(sanitized.get("poi_id") or "").strip()
    pois_by_id = {p["poi_id"]: p for p in manifest_payload["pois"]}
    target_poi = pois_by_id.get(raw_poi_id)
    if target_poi is None:
        reasons.append("UNKNOWN_CANONICAL_POI")

    raw_city = str(sanitized.get("city") or "").strip()
    canonical_city = target_poi["city"] if target_poi is not None else raw_city
    if not raw_city:
        reasons.append("MISSING_CITY")
    elif target_poi is not None:
        valid_aliases = w07_a2.CITY_VALID_ALIASES[target_poi["city"]]
        if raw_city.lower() not in valid_aliases:
            reasons.append(f"CITY_MISMATCH:expected={target_poi['city']},got={raw_city}")

    raw_rating = str(sanitized.get("rating") or "").strip()
    parsed_rating: float | None = None
    try:
        r_float = float(raw_rating)
        if r_float.is_integer() and 1.0 <= r_float <= 5.0:
            parsed_rating = float(int(r_float))
        else:
            parsed_rating = -1.0
            reasons.append("INVALID_RATING")
    except (TypeError, ValueError):
        parsed_rating = None
        reasons.append("INVALID_RATING")

    raw_review_text = (
        str(sanitized["review_text"])
        if "review_text" in sanitized and sanitized["review_text"] is not None
        else ""
    )

    # Corrective 01 Sections 2 & 3: Strict language validation with zero default to "vi"
    raw_language = str(sanitized.get("language") or "").strip()
    validated_language = validate_language_value(raw_language)
    if validated_language is None:
        reasons.append("REJECT_INVALID_OR_MISSING_LANGUAGE")

    raw_visit_period = str(sanitized.get("visit_period") or "").strip()
    raw_channel = str(sanitized.get("collection_channel") or "").strip().upper()
    raw_capture_mode = str(sanitized.get("capture_mode") or "").strip().upper()
    raw_text_approved = str(sanitized.get("review_text_approved") or "").strip()
    raw_consent_confirmed = str(sanitized.get("consent_confirmed") or "").strip()
    raw_consent_ts = str(sanitized.get("consent_timestamp") or "").strip()
    raw_evidence_type = str(sanitized.get("consent_evidence_type") or "").strip().upper()
    raw_evidence_ref = str(sanitized.get("consent_evidence_ref") or "").strip()
    raw_collector_code = str(sanitized.get("collector_code") or "").strip().upper()
    raw_collected_at = str(sanitized.get("collected_at") or "").strip()

    # Authenticity & Copy Firewall (Section 4 & 17)
    meta_lower = " ".join(
        str(sanitized.get(k, "")).lower()
        for k in (
            "collection_channel",
            "capture_mode",
            "consent_evidence_type",
            "consent_evidence_ref",
        )
    )
    if any(tok in meta_lower for tok in FORBIDDEN_COPIED_ONLINE_SUBSTRINGS) or (
        raw_capture_mode == "COPIED_ONLINE_REVIEW"
    ):
        reasons.append("REJECT_COPIED_ONLINE_PROVENANCE")

    if any(tok in meta_lower for tok in FORBIDDEN_AI_SUBSTRINGS) or raw_capture_mode in {
        "AI_GENERATED",
        "AI_REWRITTEN",
    }:
        reasons.append("SYNTHETIC_OR_LLM_OR_DISALLOWED_SOURCE")

    if raw_capture_mode in FORBIDDEN_CAPTURE_MODES:
        reasons.append(f"REJECT_FORBIDDEN_CAPTURE_MODE:{raw_capture_mode}")
    elif raw_capture_mode not in SUPPORTED_CAPTURE_MODES:
        reasons.append(f"REJECT_UNSUPPORTED_CAPTURE_MODE:{raw_capture_mode or 'EMPTY'}")

    if raw_channel not in SUPPORTED_COLLECTION_CHANNELS:
        reasons.append(f"REJECT_UNSUPPORTED_COLLECTION_CHANNEL:{raw_channel or 'EMPTY'}")

    if not raw_collector_code or not COLLECTOR_CODE_RE.match(raw_collector_code):
        reasons.append("REJECT_MISSING_OR_INVALID_COLLECTOR_CODE")

    # Consent verification (Sections 9, 10, 11)
    consent_ok = _is_explicit_consent_confirmed(raw_consent_confirmed)
    if not consent_ok:
        reasons.append("REJECT_MISSING_CONSENT_CONFIRMATION")

    if raw_evidence_type in FORBIDDEN_CONSENT_EVIDENCE_TYPES:
        reasons.append(f"REJECT_VERBAL_ONLY_OR_FORBIDDEN_CONSENT:{raw_evidence_type}")
    elif raw_evidence_type not in SUPPORTED_CONSENT_EVIDENCE_TYPES:
        reasons.append(
            f"REJECT_UNSUPPORTED_CONSENT_EVIDENCE_TYPE:{raw_evidence_type or 'EMPTY'}"
        )

    # Corrective 01 Sections 4 & 5: Fail-closed timestamp parsing for consent_timestamp and collected_at
    parsed_consent_ts: tuple[str, str] | None = None
    if not raw_consent_ts:
        reasons.append("REJECT_MISSING_CONSENT_TIMESTAMP")
    else:
        parsed_consent_ts = parse_strict_assisted_timestamp(raw_consent_ts)
        if parsed_consent_ts is None:
            reasons.append("REJECT_INVALID_CONSENT_TIMESTAMP")

    parsed_collected_at: tuple[str, str] | None = None
    if not raw_collected_at:
        reasons.append("REJECT_MISSING_COLLECTED_AT")
    else:
        parsed_collected_at = parse_strict_assisted_timestamp(raw_collected_at)
        if parsed_collected_at is None:
            reasons.append("REJECT_INVALID_COLLECTED_AT")

    if not raw_evidence_ref:
        reasons.append("REJECT_MISSING_CONSENT_EVIDENCE_REF")

    # Final-text approval check (Section 12)
    text_approved_ok = _is_review_text_approved(
        raw_text_approved,
        capture_mode=raw_capture_mode,
        consent_ok=consent_ok,
    )
    if not text_approved_ok:
        reasons.append("REJECT_TEXT_NOT_CONTRIBUTOR_APPROVED")

    # Derive created_at and collected_at strictly from valid parsed_collected_at (no fallback!)
    created_date = parsed_collected_at[0] if parsed_collected_at is not None else ""
    collected_iso = parsed_collected_at[1] if parsed_collected_at is not None else ""
    effective_consent_iso = (
        parsed_consent_ts[1] if parsed_consent_ts is not None else ""
    )

    can_build_consent_id = (
        consent_ok
        and norm_contrib is not None
        and target_poi is not None
        and raw_evidence_type in SUPPORTED_CONSENT_EVIDENCE_TYPES
        and parsed_consent_ts is not None
        and bool(raw_evidence_ref)
        and text_approved_ok
    )
    consent_record_id = (
        generate_assisted_consent_record_id(
            consent_protocol_version=CONSENT_PROTOCOL_VERSION,
            contributor_code=norm_contrib or "INVALID",
            poi_id=raw_poi_id,
            consent_timestamp=effective_consent_iso,
            consent_evidence_type=raw_evidence_type,
            consent_evidence_ref=raw_evidence_ref,
        )
        if can_build_consent_id
        else None
    )

    city_code = CITY_CODE_BY_CANONICAL_CITY.get(canonical_city, "unk")
    review_id = generate_assisted_review_id(
        contributor_code=norm_contrib or raw_contrib or "unknown_contrib",
        poi_id=raw_poi_id or "unknown_poi",
        city_code=city_code,
        rating_str=raw_rating,
        review_text=raw_review_text,
        language=validated_language or raw_language or "invalid_language",
        visit_period=raw_visit_period or None,
        capture_mode=raw_capture_mode or "UNKNOWN_MODE",
    )

    upstream_place_id = (
        f"osm:{target_poi['osm_id']}" if target_poi is not None else None
    )

    # Corrective 01 Section 6: Assign source, provenance, license_or_usage_class, mapping_method,
    # and mapping_confidence internally and unconditionally (never from CSV input).
    candidate_row: dict[str, Any] = {
        "review_id": review_id,
        "poi_id": raw_poi_id,
        "upstream_place_id": upstream_place_id,
        "city": raw_city
        if target_poi is None
        else (
            target_poi["city"]
            if raw_city.lower() in w07_a2.CITY_VALID_ALIASES[target_poi["city"]]
            else raw_city
        ),
        "source": ASSISTED_SOURCE_VALUE,
        "source_review_id": None,
        "rating": parsed_rating,
        "rating_scale_max": 5,
        "review_text": raw_review_text,
        "language": validated_language if validated_language is not None else raw_language,
        "created_at": created_date,
        "collected_at": collected_iso,
        "source_ref": f"w07_assisted_v1#{norm_contrib or 'unk'}#{review_id}",
        "provenance": ASSISTED_PROVENANCE_CLASS,
        "license_or_usage_class": ASSISTED_LICENSE_OR_USAGE_CLASS,
        "mapping_method": ASSISTED_MAPPING_METHOD,
        "mapping_confidence": ASSISTED_MAPPING_CONFIDENCE,
        "author_anonymous_id": (
            generate_assisted_author_anonymous_id(norm_contrib)
            if norm_contrib is not None
            else None
        ),
        "visit_period": raw_visit_period if raw_visit_period else None,
        "consent_record_id": consent_record_id,
        "contributor_code": norm_contrib,
        "collection_channel": raw_channel,
        "capture_mode": raw_capture_mode,
        "review_text_approved": text_approved_ok,
        "consent_evidence_type": raw_evidence_type,
        "collector_code": raw_collector_code,
    }
    return candidate_row, reasons, stripped_cols


def validate_assisted_candidates(
    candidates_with_pre_reasons: list[tuple[dict[str, Any], list[str]]],
    manifest_payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate assisted candidate rows using both W07-A2 base validation and W07-A4H assisted rules."""
    raw_rows = [c for c, _ in candidates_with_pre_reasons]
    base_report = w07_a2.validate_review_rows(raw_rows, manifest_payload)
    base_rejected_by_idx: dict[int, list[str]] = {
        r["row_index"]: list(r["reasons"]) for r in base_report["rejected_rows"]
    }
    base_warnings_by_idx: dict[int, list[str]] = {
        w["row_index"]: list(w["warnings"]) for w in base_report["warnings"]
    }

    accepted_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    manual_review_required_rows: list[dict[str, Any]] = []
    duplicate_records: list[dict[str, Any]] = list(base_report["duplicates"])

    seen_contributor_poi: set[tuple[str, str]] = set()
    seen_global_norm_text: dict[str, str] = {}

    for idx, (row, pre_reasons) in enumerate(candidates_with_pre_reasons):
        combined_reasons: list[str] = []
        for r in pre_reasons + base_rejected_by_idx.get(idx, []):
            if r not in combined_reasons:
                combined_reasons.append(r)

        # Ensure language failures always surface REJECT_INVALID_OR_MISSING_LANGUAGE
        lang_val = str(row.get("language") or "").strip()
        if validate_language_value(lang_val) is None:
            if "REJECT_INVALID_OR_MISSING_LANGUAGE" not in combined_reasons:
                combined_reasons.append("REJECT_INVALID_OR_MISSING_LANGUAGE")

        # Enforce immutable assisted provenance fields even if validate_assisted_candidates is called directly
        if row.get("source") != ASSISTED_SOURCE_VALUE:
            combined_reasons.append("REJECT_ASSISTED_SOURCE_IMMUTABILITY_VIOLATION")
        if row.get("provenance") != ASSISTED_PROVENANCE_CLASS:
            combined_reasons.append("REJECT_ASSISTED_PROVENANCE_IMMUTABILITY_VIOLATION")
        if row.get("license_or_usage_class") != ASSISTED_LICENSE_OR_USAGE_CLASS:
            combined_reasons.append("REJECT_ASSISTED_LICENSE_IMMUTABILITY_VIOLATION")
        if row.get("mapping_method") != ASSISTED_MAPPING_METHOD or float(
            row.get("mapping_confidence") or 0.0
        ) != float(ASSISTED_MAPPING_CONFIDENCE):
            combined_reasons.append("REJECT_ASSISTED_MAPPING_IMMUTABILITY_VIOLATION")

        rid = row.get("review_id")
        pid = str(row.get("poi_id") or "")
        contrib = str(row.get("contributor_code") or row.get("author_anonymous_id") or "").upper()
        norm_text = w07_a2._normalize_text(str(row.get("review_text") or ""))

        # Enforce 1 active review per (contributor_code, poi_id) (Section 7 & 18)
        if contrib and pid:
            cp_key = (contrib, pid)
            if cp_key in seen_contributor_poi:
                if "REJECT_DUPLICATE_CONTRIBUTOR_POI" not in combined_reasons:
                    combined_reasons.append("REJECT_DUPLICATE_CONTRIBUTOR_POI")
                duplicate_records.append(
                    {
                        "row_index": idx,
                        "review_id": rid,
                        "poi_id": pid,
                        "contributor_code": contrib,
                        "duplicate_type": "REJECT_DUPLICATE_CONTRIBUTOR_POI",
                    }
                )

        # Enforce exact duplicate normalized text rejection even across different POIs/contributors (Section 17 & 18)
        if norm_text:
            if norm_text in seen_global_norm_text:
                if "EXACT_DUPLICATE_NORMALIZED_TEXT" not in combined_reasons:
                    combined_reasons.append("EXACT_DUPLICATE_NORMALIZED_TEXT")
                duplicate_records.append(
                    {
                        "row_index": idx,
                        "review_id": rid,
                        "poi_id": pid,
                        "matched_review_id": seen_global_norm_text[norm_text],
                        "duplicate_type": "EXACT_DUPLICATE_NORMALIZED_TEXT",
                    }
                )

        if combined_reasons:
            rejected_rows.append(
                {
                    "row_index": idx,
                    "review_id": rid if isinstance(rid, str) else None,
                    "poi_id": pid or None,
                    "contributor_code": contrib or None,
                    "reasons": combined_reasons,
                }
            )
            continue

        # Check near-duplicate / suspicious template flags (Section 18: MANUAL_REVIEW_REQUIRED rather than silently accepted)
        row_warns = base_warnings_by_idx.get(idx, [])
        near_dup_warns = [
            w
            for w in row_warns
            if w.startswith("NEAR_DUPLICATE_JACCARD_GE_0_85")
            or w == "SUSPICIOUS_REPEATED_TEMPLATE_PREFIX"
        ]
        if near_dup_warns:
            manual_review_required_rows.append(
                {
                    "row_index": idx,
                    "review_id": rid,
                    "poi_id": pid,
                    "contributor_code": contrib,
                    "status": "MANUAL_REVIEW_REQUIRED",
                    "triggers": near_dup_warns,
                }
            )
            continue

        if contrib and pid:
            seen_contributor_poi.add((contrib, pid))
        if norm_text and isinstance(rid, str):
            seen_global_norm_text[norm_text] = rid

        accepted_rows.append(row)

    return {
        "total_input_rows": len(candidates_with_pre_reasons),
        "accepted_review_count": len(accepted_rows),
        "rejected_review_count": len(rejected_rows),
        "manual_review_required_count": len(manual_review_required_rows),
        "quarantined_pii_count": base_report["quarantined_pii_count"],
        "duplicate_count": len(duplicate_records),
        "accepted_rows": accepted_rows,
        "rejected_rows": rejected_rows,
        "manual_review_required_rows": manual_review_required_rows,
        "quarantined_pii_rows": base_report["quarantined_pii_rows"],
        "duplicates": duplicate_records,
    }


def compute_contributor_concentration_metrics(
    accepted_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute Section 19 contributor concentration diagnostics across accepted first-party reviews."""
    contrib_counts: Counter[str] = Counter()
    for idx, row in enumerate(accepted_rows):
        cid = (
            row.get("contributor_code")
            or row.get("author_anonymous_id")
            or f"anon_{idx}"
        )
        contrib_counts[str(cid)] += 1

    total_reviews = len(accepted_rows)
    unique_contributors = len(contrib_counts)
    counts_sorted = sorted(contrib_counts.values(), reverse=True)
    max_from_one = counts_sorted[0] if counts_sorted else 0
    max_share = round(max_from_one / total_reviews, 6) if total_reviews > 0 else 0.0
    mean_per_contrib = (
        round(total_reviews / unique_contributors, 4) if unique_contributors > 0 else 0.0
    )

    histogram = {
        str(k): v
        for k, v in sorted(Counter(contrib_counts.values()).items())
    }

    return {
        "unique_contributors_count": unique_contributors,
        "total_accepted_reviews": total_reviews,
        "mean_reviews_per_contributor": mean_per_contrib,
        "max_reviews_from_single_contributor": max_from_one,
        "max_contributor_share_of_corpus": max_share,
        "reviews_per_contributor_histogram": histogram,
        "per_contributor_review_counts": dict(sorted(contrib_counts.items())),
    }


def import_assisted_csv_files(
    csv_paths: list[Path],
    *,
    output_jsonl_path: Path,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Deterministically import assisted first-party CSV files into `output_jsonl_path`.

    Idempotency guarantee:
    - Existing valid rows in `output_jsonl_path` are loaded first.
    - Incoming CSV rows with an identical `review_id` already present in `existing_ids`
      or earlier in the same import batch are skipped as idempotent duplicates.
    - All unique candidate rows are validated via `validate_assisted_candidates()`.
    - Only `accepted_rows` (excluding rejected, PII-quarantined, and `MANUAL_REVIEW_REQUIRED` rows)
      are written to `output_jsonl_path`, sorted deterministically by `(poi_id, review_id)`.
    """
    verify_upstream_a2_and_a3_immutability(repo_root)
    manifest = w07_a3_import.verify_and_load_a2_manifest(repo_root)

    existing_candidates: list[tuple[dict[str, Any], list[str]]] = []
    existing_ids: set[str] = set()
    if output_jsonl_path.exists():
        for line in output_jsonl_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                obj = json.loads(line)
                rid = obj.get("review_id")
                if isinstance(rid, str) and rid and rid not in existing_ids:
                    existing_ids.add(rid)
                    existing_candidates.append((obj, []))

    incoming_candidates: list[tuple[dict[str, Any], list[str]]] = []
    seen_incoming_ids: set[str] = set()
    idempotent_skipped_count = 0
    stripped_columns_seen: set[str] = set()
    unexpected_columns_seen: set[str] = set()

    for csv_path in csv_paths:
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                if not any(
                    str(v).strip() for v in raw_row.values() if v is not None
                ):
                    continue
                _, _, row_unexpected = partition_assisted_input_columns(raw_row)
                unexpected_columns_seen.update(row_unexpected)
                cand, pre_reasons, stripped_cols = convert_assisted_csv_row_to_candidate(
                    raw_row,
                    manifest_payload=manifest,
                )
                stripped_columns_seen.update(stripped_cols)
                rid = cand["review_id"]
                if not pre_reasons and (rid in existing_ids or rid in seen_incoming_ids):
                    idempotent_skipped_count += 1
                    continue
                if not pre_reasons:
                    seen_incoming_ids.add(rid)
                incoming_candidates.append((cand, pre_reasons))

    combined = existing_candidates + incoming_candidates
    val_res = validate_assisted_candidates(combined, manifest)
    accepted_rows = list(val_res["accepted_rows"])
    accepted_rows.sort(
        key=lambda r: (str(r.get("poi_id", "")), str(r.get("review_id", "")))
    )

    output_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in accepted_rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    output_sha = w07_a2.compute_lf_normalized_sha256(output_jsonl_path)
    concentration = compute_contributor_concentration_metrics(accepted_rows)

    return {
        "status": "PASS",
        "output_jsonl_path": str(output_jsonl_path),
        "output_jsonl_lf_sha256": output_sha,
        "existing_accepted_before_import": len(existing_candidates),
        "new_unique_candidates_processed": len(incoming_candidates),
        "idempotent_duplicate_rows_skipped": idempotent_skipped_count,
        "stripped_identity_columns": sorted(stripped_columns_seen),
        "unexpected_input_columns_detected": sorted(unexpected_columns_seen),
        "accepted_review_count": val_res["accepted_review_count"],
        "rejected_review_count": val_res["rejected_review_count"],
        "manual_review_required_count": val_res["manual_review_required_count"],
        "quarantined_pii_count": val_res["quarantined_pii_count"],
        "duplicate_count": val_res["duplicate_count"],
        "rejected_rows": val_res["rejected_rows"],
        "manual_review_required_rows": val_res["manual_review_required_rows"],
        "quarantined_pii_rows": val_res["quarantined_pii_rows"],
        "contributor_concentration": concentration,
    }


def build_combined_first_party_progress_report(
    *,
    form_rows: list[dict[str, Any]],
    assisted_rows: list[dict[str, Any]],
    manifest_payload: dict[str, Any],
    importer_idempotency_verified: bool = True,
) -> dict[str, Any]:
    """Compute combined first-party progress across Google Forms + Assisted collection (Sections 19-22).

    Does NOT merge the raw/candidate JSONL files on disk; evaluates each first-party channel
    and computes aggregate accepted metrics.
    """
    form_val = w07_a2.validate_review_rows(form_rows, manifest_payload)
    form_rejected_idx = {r["row_index"] for r in form_val["rejected_rows"]}
    accepted_form_rows = [
        r
        for idx, r in enumerate(form_rows)
        if idx not in form_rejected_idx
        and r.get("provenance") == GOOGLE_FORMS_PROVENANCE_CLASS
    ]

    assisted_pairs = [(r, []) for r in assisted_rows]
    assisted_val = validate_assisted_candidates(assisted_pairs, manifest_payload)
    accepted_assisted_rows = [
        r
        for r in assisted_val["accepted_rows"]
        if r.get("provenance") == ASSISTED_PROVENANCE_CLASS
    ]

    # Combine accepted rows across both first-party channels while deduplicating any
    # cross-channel duplicate review_id or identical (poi_id, normalized_text)
    combined_accepted: list[dict[str, Any]] = []
    seen_rids: set[str] = set()
    seen_poi_norm: set[tuple[str, str]] = set()
    cross_channel_duplicates_skipped = 0

    for row in accepted_form_rows + accepted_assisted_rows:
        rid = str(row.get("review_id") or "")
        pid = str(row.get("poi_id") or "")
        ntext = w07_a2._normalize_text(str(row.get("review_text") or ""))
        if rid in seen_rids or (pid and ntext and (pid, ntext) in seen_poi_norm):
            cross_channel_duplicates_skipped += 1
            continue
        if rid:
            seen_rids.add(rid)
        if pid and ntext:
            seen_poi_norm.add((pid, ntext))
        combined_accepted.append(row)

    base_progress = w07_a3_progress.build_collection_progress_report(
        combined_accepted,
        manifest_payload,
        importer_idempotency_verified=importer_idempotency_verified,
    )

    form_by_city: dict[str, int] = {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0}
    assisted_by_city: dict[str, int] = {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0}
    for r in accepted_form_rows:
        c = str(r.get("city") or "")
        if c in form_by_city:
            form_by_city[c] += 1
    for r in accepted_assisted_rows:
        c = str(r.get("city") or "")
        if c in assisted_by_city:
            assisted_by_city[c] += 1

    capture_mode_dist = dict(
        sorted(Counter(str(r.get("capture_mode") or "UNKNOWN") for r in accepted_assisted_rows).items())
    )
    channel_dist = dict(
        sorted(Counter(str(r.get("collection_channel") or "UNKNOWN") for r in accepted_assisted_rows).items())
    )
    evidence_type_dist = dict(
        sorted(Counter(str(r.get("consent_evidence_type") or "UNKNOWN") for r in accepted_assisted_rows).items())
    )
    language_dist = dict(
        sorted(Counter(str(r.get("language") or "UNKNOWN") for r in combined_accepted).items())
    )
    provenance_dist = dict(
        sorted(Counter(str(r.get("provenance") or "UNKNOWN") for r in combined_accepted).items())
    )

    concentration = compute_contributor_concentration_metrics(combined_accepted)

    total_rejected = form_val["rejected_review_count"] + assisted_val["rejected_review_count"]
    total_quarantined_pii = (
        form_val["quarantined_pii_count"] + assisted_val["quarantined_pii_count"]
    )

    payload: dict[str, Any] = {
        "artifact_id": "w07_first_party_collection_progress_v1",
        "artifact_version": ASSISTED_IMPORTER_VERSION,
        "task_id": "W07-A4H-CORRECTIVE-01",
        "authoritative_develop_base_sha": AUTHORITATIVE_DEVELOP_BASE_SHA,
        "previous_gates": list(PREVIOUS_GATES),
        "next_gate": NEXT_GATE,
        "manifest_sha_binding": {
            "manifest_path": w07_a2.MANIFEST_60_JSON_RELPATH,
            "manifest_internal_sha256": w07_a3_import.EXPECTED_A2_MANIFEST_INTERNAL_SHA256,
            "manifest_file_lf_sha256": w07_a3_import.EXPECTED_A2_MANIFEST_FILE_LF_SHA256,
        },
        "a3_google_forms_immutability_binding": {
            "form_definition_path": w07_a3_import.FORM_DEFINITION_JSON_RELPATH,
            "form_definition_internal_sha256": EXPECTED_A3_FORM_DEF_INTERNAL_SHA256,
            "apps_script_path": w07_a3_import.APPS_SCRIPT_RELPATH,
            "apps_script_lf_sha256": EXPECTED_A3_APPS_SCRIPT_LF_SHA256,
            "a3_progress_path": w07_a3_progress.PROGRESS_JSON_RELPATH,
            "a3_progress_internal_sha256": EXPECTED_A3_PROGRESS_INTERNAL_SHA256,
        },
        "assisted_contract_invariants": {
            "template_column_count": len(REQUIRED_TEMPLATE_COLUMNS),
            "template_columns": list(REQUIRED_TEMPLATE_COLUMNS),
            "allowed_languages": list(ALLOWED_LANGUAGE_VALUES),
            "implicit_language_default_allowed": False,
            "missing_or_invalid_language_action": "REJECT_INVALID_OR_MISSING_LANGUAGE",
            "timestamp_fail_closed": True,
            "fixed_date_timestamp_fallback_allowed": False,
            "created_at_semantics": CREATED_AT_SEMANTIC_DEFINITION,
            "immutable_provenance_fields": {
                "source": ASSISTED_SOURCE_VALUE,
                "provenance": ASSISTED_PROVENANCE_CLASS,
                "license_or_usage_class": ASSISTED_LICENSE_OR_USAGE_CLASS,
                "mapping_method": ASSISTED_MAPPING_METHOD,
                "mapping_confidence": ASSISTED_MAPPING_CONFIDENCE,
            },
            "unexpected_non_identity_column_action": "REJECT_UNEXPECTED_INPUT_COLUMN",
        },
        "privacy_and_content_guarantee": {
            "raw_review_text_published_in_this_artifact": False,
            "contributor_real_identity_published_in_this_artifact": False,
            "candidate_jsonl_files_kept_separate_until_a5": True,
        },
        "first_party_source_channels": {
            DIRECT_FORM_ACQUISITION_CHANNEL: {
                "candidate_jsonl_relpath": w07_a2.RESTRICTED_JSONL_RELPATH,
                "source_value": "first_party_contributor_form_v1",
                "provenance_class": GOOGLE_FORMS_PROVENANCE_CLASS,
                "total_candidate_rows": len(form_rows),
                "accepted_review_count": len(accepted_form_rows),
                "rejected_review_count": form_val["rejected_review_count"],
                "quarantined_pii_count": form_val["quarantined_pii_count"],
                "reviews_by_city": form_by_city,
                "distinct_pois_covered_count": len({r["poi_id"] for r in accepted_form_rows}),
            },
            ASSISTED_ACQUISITION_CHANNEL: {
                "candidate_jsonl_relpath": ASSISTED_CANDIDATE_JSONL_RELPATH,
                "template_csv_relpath": ASSISTED_TEMPLATE_CSV_RELPATH,
                "source_value": ASSISTED_SOURCE_VALUE,
                "provenance_class": ASSISTED_PROVENANCE_CLASS,
                "total_candidate_rows": len(assisted_rows),
                "accepted_review_count": len(accepted_assisted_rows),
                "rejected_review_count": assisted_val["rejected_review_count"],
                "manual_review_required_count": assisted_val["manual_review_required_count"],
                "quarantined_pii_count": assisted_val["quarantined_pii_count"],
                "reviews_by_city": assisted_by_city,
                "distinct_pois_covered_count": len({r["poi_id"] for r in accepted_assisted_rows}),
                "capture_mode_distribution": capture_mode_dist,
                "collection_channel_distribution": channel_dist,
                "consent_evidence_type_distribution": evidence_type_dist,
            },
        },
        "combined_summary_counts": {
            "total_candidate_rows_evaluated": len(form_rows) + len(assisted_rows),
            "accepted_review_count": len(combined_accepted),
            "direct_google_form_accepted_count": len(accepted_form_rows),
            "assisted_first_party_accepted_count": len(accepted_assisted_rows),
            "cross_channel_duplicates_skipped": cross_channel_duplicates_skipped,
            "rejected_review_count": total_rejected,
            "manual_review_required_count": assisted_val["manual_review_required_count"],
            "quarantined_pii_count": total_quarantined_pii,
            "covered_poi_count": base_progress["summary_counts"]["covered_poi_count"],
            "pois_with_0_reviews_count": base_progress["summary_counts"][
                "pois_with_0_reviews_count"
            ],
            "pois_with_1_to_4_reviews_count": base_progress["summary_counts"][
                "pois_with_1_to_4_reviews_count"
            ],
            "pois_with_5_or_more_reviews_count": base_progress["summary_counts"][
                "pois_with_5_or_more_reviews_count"
            ],
            "remaining_reviews_to_pilot_30": base_progress["pilot_gate_evaluation"][
                "remaining_reviews_to_pilot_30"
            ],
            "remaining_reviews_to_300": base_progress["summary_counts"][
                "remaining_reviews_to_300"
            ],
        },
        "provenance_distribution": provenance_dist,
        "language_distribution": language_dist,
        "reviews_by_city": base_progress["reviews_by_city"],
        "reviews_by_category_group": base_progress["reviews_by_category_group"],
        "contributor_concentration_diagnostics": concentration,
        "pilot_gate_evaluation": {
            **base_progress["pilot_gate_evaluation"],
            "eligible_first_party_channels": [
                DIRECT_FORM_ACQUISITION_CHANNEL,
                ASSISTED_ACQUISITION_CHANNEL,
            ],
            "require_all_30_from_google_forms": False,
        },
        "scientific_minimum_evaluation": base_progress["scientific_minimum_evaluation"],
        "runtime_and_governance_counters": {
            "NEW_ASSISTED_REAL_REVIEWS_ACQUIRED": len(accepted_assisted_rows),
            "NEW_PRIMARY_REVIEWS_ACQUIRED": len(combined_accepted),
            "LLM_GENERATED_PRIMARY_REVIEWS": 0,
            "NEW_LLM_PROVIDER_CALLS": 0,
            "SCRAPING_EXECUTED": False,
        },
        "city_completion_summary": base_progress["city_completion_summary"],
        "sampling_stratum_completion_summary": base_progress[
            "sampling_stratum_completion_summary"
        ],
        "poi_coverage_buckets": base_progress["poi_coverage_buckets"],
        "exact_under_covered_pois": base_progress["exact_under_covered_pois"],
        "reviews_per_poi": base_progress["reviews_per_poi"],
    }
    payload["artifact_sha256"] = w07_a2.compute_internal_sha256(
        payload, "artifact_sha256"
    )
    return payload


def render_assisted_collection_guide_markdown(
    manifest_payload: dict[str, Any],
) -> str:
    """Deterministically render `docs/research/w07_assisted_first_party_collection_guide.md`."""
    lines: list[str] = [
        "# W07-A4H — Assisted First-Party Review Collection Guide (Corrective 01)",
        "",
        "## 0. Authority & Scope",
        "",
        "- **Previous Gates:**",
        f"  - `{PREVIOUS_GATES[0]}`",
        f"  - `{PREVIOUS_GATES[1]}`",
        f"  - `{PREVIOUS_GATES[2]}`",
        f"- **Authoritative Base:** `develop@{AUTHORITATIVE_DEVELOP_BASE_SHA}`",
        f"- **Next Gate:** `{NEXT_GATE}`",
        f"- **Frozen 60-POI Manifest (Single Authority):** `{w07_a2.MANIFEST_60_JSON_RELPATH}` (`{manifest_payload['manifest_sha256']}`)",
        f"- **Assisted Intake CSV Template (16 columns):** `{ASSISTED_TEMPLATE_CSV_RELPATH}`",
        f"- **Assisted Candidate Output JSONL (gitignored):** `{ASSISTED_CANDIDATE_JSONL_RELPATH}`",
        f"- **Optional Restricted Identity Map (gitignored):** `{RESTRICTED_IDENTITY_MAP_RELPATH}`",
        f"- **Optional Restricted Consent Evidence Folder (gitignored):** `{RESTRICTED_CONSENT_EVIDENCE_DIR_RELPATH}/`",
        f"- **Combined First-Party Progress Artifact:** `{COMBINED_FIRST_PARTY_PROGRESS_JSON_RELPATH}`",
        "",
        "---",
        "",
        "## 1. Provenance Separation, Immutable Provenance Fields & No Fake Form Submissions",
        "",
        "`ASSISTED_FIRST_PARTY_COLLECTION` is a legitimate parallel first-party channel alongside W07-A3 Google Forms (`DIRECT_GOOGLE_FORM`).",
        "",
        "| Channel | `source` | `provenance` | Candidate JSONL |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Google Forms (W07-A3)** | `first_party_contributor_form_v1` | `{GOOGLE_FORMS_PROVENANCE_CLASS}` | `{w07_a2.RESTRICTED_JSONL_RELPATH}` |",
        f"| **Assisted Collection (W07-A4H)** | `{ASSISTED_SOURCE_VALUE}` | `{ASSISTED_PROVENANCE_CLASS}` | `{ASSISTED_CANDIDATE_JSONL_RELPATH}` |",
        "",
        "### Strict Operational & Immutability Rules",
        "1. **Contributor must have personally visited/directly experienced the POI.**",
        "2. **Never submit assisted reviews into the Google Forms** pretending to originate from different browser sessions.",
        "3. **Never invent, rewrite, paraphrase with AI (ChatGPT/Gemini/Claude), or multiply one review into several reviews.**",
        "4. **Provenance fields are assigned internally and unconditionally by the importer:** `source = \"assisted_first_party\"`, `provenance = \"FIRST_PARTY_ASSISTED_COLLECTION_CONSENT_V1\"`, `license_or_usage_class = \"OWNER_FIRST_PARTY_CONSENT\"`, `mapping_method = \"EXACT_PREBOUND_CANONICAL_POI\"`, `mapping_confidence = 1.0`. Any unexpected non-identity column in the CSV (including `source`, `provenance`, `license_or_usage_class`, `mapping_method`, `mapping_confidence`, `review_id`, `consent_record_id`) is rejected with `REJECT_UNEXPECTED_INPUT_COLUMN`.",
        "5. **Keep Google Forms candidate JSONL and Assisted candidate JSONL separate** (W07-A5 will perform controlled merge & deduplication).",
        "",
        "---",
        "",
        "## 2. Step-by-Step Owner Workflow (Zero Python Editing Required)",
        "",
        "1. **Ask contributor which target POIs they genuinely visited** from the 60 canonical POIs in Hà Nội, Đà Nẵng, or Hạ Long (see Section 8 table below).",
        "2. **Assign or reuse a pseudonymous `contributor_code`** (`W07C001`, `W07C002`, `W07C003`, ...). The same person **must** keep the same `contributor_code` across all POIs they review. One contributor may review multiple POIs they genuinely visited, but at most **one** review per `(contributor_code, poi_id)`.",
        "3. **Ask for their integer rating (`1` to `5`)** for each visited POI.",
        "4. **Collect their review verbatim** (via Zalo, Messenger, direct chat, in-person interview, or phone conversation) and record the exact `language` of the **review text** (`vi`, `en`, or `mixed_vi_en` — based on the review text itself, NOT contributor nationality; never left blank).",
        "5. **Ask for optional `visit_period`** (`YYYY-MM` like `2025-08` or `YYYY-Q1..Q4` like `2025-Q3`).",
        "6. **Send the Vietnamese consent script** (Section 4 below).",
        "7. **Obtain explicit written/digital consent** (`\"Tôi đồng ý\"` or `\"Đồng ý\"`) and record a valid ISO-8601 `consent_timestamp`. Never infer consent from silence.",
        "8. **If collector transcribed an oral review**, send the exact final text back to the contributor (Section 5 below) and wait for their explicit final-text approval before setting `review_text_approved = true`.",
        "9. **Enter one 16-column CSV row per POI** into your local copy `data/restricted/w07_reviews/raw_assisted/assisted_reviews.csv` (copied from `data/templates/w07_assisted_first_party_review_template_v1.csv`), recording a valid ISO-8601 `collected_at` timestamp.",
        "10. **Run the deterministic assisted importer:**",
        "    ```bash",
        "    python scripts/import_w07_assisted_reviews_v1.py --import-csv data/restricted/w07_reviews/raw_assisted/assisted_reviews.csv",
        "    ```",
        "11. **Run the W07-A2 corpus validator on the assisted candidate JSONL:**",
        "    ```bash",
        "    python scripts/validate_w07_review_corpus_v1.py --validate-jsonl data/restricted/w07_reviews/w07_assisted_candidate_reviews_v1.jsonl",
        "    ```",
        "12. **Update the combined first-party progress tracker:**",
        "    ```bash",
        "    python scripts/import_w07_assisted_reviews_v1.py --write-progress",
        "    ```",
        "",
        "---",
        "",
        "## 3. Copy-Paste Vietnamese Recruitment Message",
        "",
        "> “Bọn mình đang làm đồ án GoMate về gợi ý du lịch. Nếu bạn từng đi một trong các địa điểm trong danh sách, mình muốn xin đánh giá thật của bạn (1–5 điểm + vài câu cảm nhận). Nội dung sẽ ẩn danh và chỉ dùng cho đồ án/nghiên cứu. Chỉ đánh giá địa điểm bạn thực sự từng trải nghiệm.”",
        "",
        "---",
        "",
        "## 4. Copy-Paste Vietnamese Consent Script",
        "",
        "> “Bạn xác nhận rằng bạn đã trực tiếp đến/trải nghiệm địa điểm này, nội dung đánh giá là ý kiến của chính bạn, không sao chép từ Google Maps/Tripadvisor/Booking/Agoda/Foody và không dùng AI (ChatGPT, Gemini, Claude). Việc tham gia là hoàn toàn tự nguyện và bạn đồng ý cho đồ án GoMate sử dụng nội dung này dưới dạng ẩn danh cho nghiên cứu, đánh giá và demo học thuật phi thương mại. Nếu đồng ý, bạn nhắn giúp mình: ‘Tôi đồng ý’ hoặc ‘Đồng ý’ nhé.”",
        "",
        "---",
        "",
        "## 5. Copy-Paste Final-Text Approval Script (Mandatory for Oral Transcription Modes)",
        "",
        "When `capture_mode` is `COLLECTOR_TRANSCRIBED_VERBATIM` or `COLLECTOR_TRANSCRIBED_AND_CONTRIBUTOR_APPROVED`, send the transcribed wording back to the contributor before importing:",
        "",
        "> “Mình vừa ghi lại nguyên văn đánh giá của bạn cho địa điểm [Tên POI] (Điểm: [1–5]/5) như sau:",
        "> ‘[Nội dung đánh giá cuối cùng]’",
        "> Bạn kiểm tra giúp mình xem nội dung đã đúng hoàn toàn ý của bạn chưa, và nhắn xác nhận ‘Tôi duyệt nội dung và đồng ý’ để mình lưu vào bộ dữ liệu nghiên cứu ẩn danh nhé.”",
        "",
        "---",
        "",
        "## 6. Supported 16-Column Template Specification (`w07_assisted_first_party_review_template_v1.csv`)",
        "",
        "| # | Column | Required | Allowed / Expected Values |",
        "|---:|:---|:---|:---|",
        "| 1 | `contributor_code` | **Yes** | Pseudonymous code `W07C001`, `W07C002`, ... (`^W07C\\d{3,6}$`). Never put real name, email, or phone. |",
        "| 2 | `poi_id` | **Yes** | Exact canonical UUID from the 60-POI manifest (do NOT use POI name). |",
        "| 3 | `city` | **Yes** | `Hà Nội`, `Đà Nẵng`, or `Hạ Long` (must match `manifest[poi_id].city`). |",
        "| 4 | `rating` | **Yes** | Integer `1`, `2`, `3`, `4`, or `5`. |",
        "| 5 | `review_text` | **Yes** | Authentic review text (`>= 20` chars and `>= 5` words recommended; zero phone/email PII). |",
        "| 6 | `language` | **Yes** | Exact review-text language: `vi`, `en`, or `mixed_vi_en`. Determined strictly from the **actual review text** (not contributor nationality). No implicit default to `vi`; blank or unsupported values are rejected with `REJECT_INVALID_OR_MISSING_LANGUAGE`. |",
        "| 7 | `visit_period` | Optional | `YYYY-MM` (e.g. `2025-08`) or `YYYY-Q1..Q4` (e.g. `2025-Q3`). Separate from `created_at` / `collected_at`. |",
        "| 8 | `collection_channel` | **Yes** | `ZALO`, `MESSENGER`, `DIRECT_CHAT`, `IN_PERSON_INTERVIEW`, or `PHONE_WITH_WRITTEN_CONFIRMATION`. |",
        "| 9 | `capture_mode` | **Yes** | `CONTRIBUTOR_WRITTEN_VERBATIM`, `COLLECTOR_TRANSCRIBED_VERBATIM`, or `COLLECTOR_TRANSCRIBED_AND_CONTRIBUTOR_APPROVED`. (Forbidden modes `COLLECTOR_PARAPHRASED`, `AI_REWRITTEN`, `AI_GENERATED`, `COPIED_ONLINE_REVIEW` are rejected). |",
        "| 10 | `review_text_approved` | **Yes** | `true` (may be implied for `CONTRIBUTOR_WRITTEN_VERBATIM` when `consent_confirmed=true`; **explicit `true` mandatory** for transcription modes, otherwise rejected with `REJECT_TEXT_NOT_CONTRIBUTOR_APPROVED`). |",
        "| 11 | `consent_confirmed` | **Yes** | `true`, `Tôi đồng ý`, or `Đồng ý`. |",
        "| 12 | `consent_timestamp` | **Yes** | Valid ISO-8601 or `YYYY-MM-DD HH:MM:SS` timestamp when consent was given. Fail-closed: missing -> `REJECT_MISSING_CONSENT_TIMESTAMP`; malformed -> `REJECT_INVALID_CONSENT_TIMESTAMP`. |",
        "| 13 | `consent_evidence_type` | **Yes** | `CHAT_WRITTEN_CONSENT`, `DIGITAL_TEXT_CONSENT`, or `IN_PERSON_WRITTEN_CONSENT`. (Verbal-only consent without written confirmation is rejected). |",
        "| 14 | `consent_evidence_ref` | **Yes** | Local reference token (e.g. `zalo_thread_w07c001_20261102_01`). Hashed with SHA-256 into `consent_record_id`; never published in the scientific JSONL. |",
        "| 15 | `collector_code` | **Yes** | Collector pseudonymous code (e.g. `OWNER_01`, `TEAM_01`). |",
        "| 16 | `collected_at` | **Yes** | Valid ISO-8601 or `YYYY-MM-DD HH:MM:SS` timestamp when recorded into the template. Fail-closed: missing -> `REJECT_MISSING_COLLECTED_AT`; malformed -> `REJECT_INVALID_COLLECTED_AT`. |",
        "",
        "### Timestamp & `created_at` Semantics",
        f"- `{CREATED_AT_SEMANTIC_DEFINITION}`.",
        "- No fixed-date fallback (such as `2026-11-02` or `2026-11-02T00:00:00Z`) is ever used.",
        "",
        "### Example Synthetic TEST FIXTURE Row (For Format Illustration Only — Do Not Import)",
        "",
        "```csv",
        ",".join(REQUIRED_TEMPLATE_COLUMNS),
        'W07C001,698ee756-6062-5f47-955b-bdf458682e57,Hà Nội,5,"TEST_FIXTURE_ONLY: Khu vực quảng trường Ba Đình rộng rãi, sạch sẽ, xếp hàng buổi sáng rất trật tự.",vi,2025-10,ZALO,CONTRIBUTOR_WRITTEN_VERBATIM,true,Tôi đồng ý,2026-11-02T09:00:00Z,CHAT_WRITTEN_CONSENT,zalo_msg_w07c001_001,OWNER_01,2026-11-02T09:05:00Z',
        "```",
        "",
        "---",
        "",
        "## 7. Optional Restricted Identity Map (Gitignored)",
        "",
        "If the Project Owner needs to remember which real person corresponds to `W07C001`, `W07C002`, ..., store a local-only file at:",
        "",
        f"`{RESTRICTED_IDENTITY_MAP_RELPATH}`",
        "",
        "- Covered by `data/restricted/*` in `.gitignore` and `data/restricted/.gitignore`.",
        "- Must **never** be committed to Git, **never** enter the scientific corpus, and is **never** required by CI.",
        "",
        "---",
        "",
        "## 8. Canonical 60-POI Lookup Table (Bound to W07-A2 Manifest)",
        "",
        *w07_a2.render_manifest_poi_markdown_table(manifest_payload),
        "",
    ]
    return "\n".join(lines)


def write_combined_first_party_progress_artifact(
    repo_root: Path = REPO_ROOT,
    *,
    form_jsonl_path: Path | None = None,
    assisted_jsonl_path: Path | None = None,
) -> dict[str, Any]:
    """Write and verify `data/evaluation/w07/w07_first_party_collection_progress_v1.json` and the guide."""
    verify_upstream_a2_and_a3_immutability(repo_root)
    verify_assisted_template_csv(repo_root)
    manifest = w07_a3_import.verify_and_load_a2_manifest(repo_root)

    guide_path = repo_root / ASSISTED_COLLECTION_GUIDE_MD_RELPATH
    guide_path.parent.mkdir(parents=True, exist_ok=True)
    guide_md = render_assisted_collection_guide_markdown(manifest)
    guide_path.write_text(guide_md, encoding="utf-8", newline="\n")

    target_form_jsonl = (
        form_jsonl_path
        if form_jsonl_path is not None
        else repo_root / w07_a2.RESTRICTED_JSONL_RELPATH
    )
    target_assisted_jsonl = (
        assisted_jsonl_path
        if assisted_jsonl_path is not None
        else repo_root / ASSISTED_CANDIDATE_JSONL_RELPATH
    )

    form_rows = w07_a3_progress.load_canonical_jsonl_rows(target_form_jsonl)
    assisted_rows = w07_a3_progress.load_canonical_jsonl_rows(target_assisted_jsonl)

    payload = build_combined_first_party_progress_report(
        form_rows=form_rows,
        assisted_rows=assisted_rows,
        manifest_payload=manifest,
    )

    out_path = repo_root / COMBINED_FIRST_PARTY_PROGRESS_JSON_RELPATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return verify_combined_first_party_progress_artifact(
        repo_root,
        form_jsonl_path=target_form_jsonl,
        assisted_jsonl_path=target_assisted_jsonl,
    )


def verify_combined_first_party_progress_artifact(
    repo_root: Path = REPO_ROOT,
    *,
    form_jsonl_path: Path | None = None,
    assisted_jsonl_path: Path | None = None,
) -> dict[str, Any]:
    """Verify committed `data/evaluation/w07/w07_first_party_collection_progress_v1.json` and upstream hashes."""
    upstream_shas = verify_upstream_a2_and_a3_immutability(repo_root)
    template_info = verify_assisted_template_csv(repo_root)
    manifest = w07_a3_import.verify_and_load_a2_manifest(repo_root)

    target_form_jsonl = (
        form_jsonl_path
        if form_jsonl_path is not None
        else repo_root / w07_a2.RESTRICTED_JSONL_RELPATH
    )
    target_assisted_jsonl = (
        assisted_jsonl_path
        if assisted_jsonl_path is not None
        else repo_root / ASSISTED_CANDIDATE_JSONL_RELPATH
    )

    form_rows = w07_a3_progress.load_canonical_jsonl_rows(target_form_jsonl)
    assisted_rows = w07_a3_progress.load_canonical_jsonl_rows(target_assisted_jsonl)

    expected_payload = build_combined_first_party_progress_report(
        form_rows=form_rows,
        assisted_rows=assisted_rows,
        manifest_payload=manifest,
    )

    out_path = repo_root / COMBINED_FIRST_PARTY_PROGRESS_JSON_RELPATH
    if not out_path.exists():
        raise FileNotFoundError(
            f"Missing combined first-party progress artifact: {out_path}"
        )

    guide_path = repo_root / ASSISTED_COLLECTION_GUIDE_MD_RELPATH
    if not guide_path.exists():
        raise FileNotFoundError(
            f"Missing assisted collection guide Markdown: {guide_path}"
        )
    expected_guide = render_assisted_collection_guide_markdown(manifest).replace("\r\n", "\n")
    disk_guide = guide_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if disk_guide != expected_guide:
        raise ValueError(
            "Assisted collection guide Markdown on disk differs from deterministic build."
        )

    disk_payload = json.loads(out_path.read_text(encoding="utf-8"))
    disk_internal_sha = w07_a2.compute_internal_sha256(disk_payload, "artifact_sha256")
    if disk_internal_sha != disk_payload.get("artifact_sha256"):
        raise ValueError(
            "Combined first-party progress internal SHA256 does not match recorded artifact_sha256."
        )
    if disk_internal_sha != expected_payload["artifact_sha256"]:
        raise ValueError(
            "Combined first-party progress artifact on disk is out of sync with build_combined_first_party_progress_report()."
        )

    return {
        "status": "PASS",
        "combined_progress_json_path": COMBINED_FIRST_PARTY_PROGRESS_JSON_RELPATH,
        "combined_progress_internal_sha256": disk_internal_sha,
        "combined_progress_file_lf_sha256": w07_a2.compute_lf_normalized_sha256(out_path),
        "assisted_template_csv_path": template_info["template_path"],
        "assisted_template_lf_sha256": template_info["template_lf_sha256"],
        "assisted_guide_md_path": ASSISTED_COLLECTION_GUIDE_MD_RELPATH,
        "assisted_guide_lf_sha256": w07_a2.compute_lf_normalized_sha256(guide_path),
        "accepted_review_count": disk_payload["combined_summary_counts"][
            "accepted_review_count"
        ],
        "direct_google_form_accepted_count": disk_payload["combined_summary_counts"][
            "direct_google_form_accepted_count"
        ],
        "assisted_first_party_accepted_count": disk_payload["combined_summary_counts"][
            "assisted_first_party_accepted_count"
        ],
        "COLLECTION_PIPELINE_PILOT_READY": disk_payload["pilot_gate_evaluation"][
            "COLLECTION_PIPELINE_PILOT_READY"
        ],
        "CORPUS_SCIENTIFIC_MINIMUM_READY": disk_payload[
            "scientific_minimum_evaluation"
        ]["CORPUS_SCIENTIFIC_MINIMUM_READY"],
        "upstream_immutability": upstream_shas,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="W07-A4H Assisted First-Party Review Importer & Combined Pilot Progress Tracker."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--import-csv",
        type=Path,
        help="Import an assisted first-party review CSV file into w07_assisted_candidate_reviews_v1.jsonl.",
    )
    group.add_argument(
        "--write-progress",
        action="store_true",
        help="Recompute and write data/evaluation/w07/w07_first_party_collection_progress_v1.json.",
    )
    group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify committed W07-A4H template, combined progress artifact, and upstream A2/A3 hashes.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=REPO_ROOT / ASSISTED_CANDIDATE_JSONL_RELPATH,
        help="Target restricted assisted candidate JSONL path.",
    )
    parser.add_argument(
        "--form-jsonl",
        type=Path,
        default=None,
        help="Optional override for Google Forms candidate JSONL path.",
    )
    args = parser.parse_args(argv)

    if args.import_csv is not None:
        res = import_assisted_csv_files(
            [args.import_csv],
            output_jsonl_path=args.output_jsonl,
            repo_root=REPO_ROOT,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.write_progress:
        res = write_combined_first_party_progress_artifact(
            REPO_ROOT,
            form_jsonl_path=args.form_jsonl,
            assisted_jsonl_path=args.output_jsonl,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    res = verify_combined_first_party_progress_artifact(
        REPO_ROOT,
        form_jsonl_path=args.form_jsonl,
        assisted_jsonl_path=args.output_jsonl,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
