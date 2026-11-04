#!/usr/bin/env python3
"""W07-B1B — Offline Fail-Closed Verifier for Targeted POI Knowledge Acquisition (Corrective 02)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import acquire_w07_b1b_poi_knowledge as b1b  # noqa: E402
from scripts import validate_w07_review_corpus_v1 as w07_a2  # noqa: E402

REQUIRED_CANDIDATE_FIELDS: tuple[str, ...] = (
    "candidate_source_id",
    "poi_id",
    "poi_name",
    "city",
    "category_group",
    "source_url",
    "publisher",
    "source_type",
    "source_tier",
    "source_lineage_id",
    "mapping_evidence",
    "canonical_mapping_status",
    "license_or_reuse_evidence",
    "reuse_storage_class",
    "redistributable_in_git",
    "raw_text_permitted",
    "attribution_requirement",
    "retrieved_at",
    "source_published_or_updated_at",
    "source_terms_checked_at",
    "artifact_snapshot_timestamp",
    "final_b1b_decision",
)

REQUIRED_DOCUMENT_FIELDS: tuple[str, ...] = (
    "document_id",
    "poi_id",
    "city",
    "source_type",
    "source_tier",
    "source_title",
    "source_url",
    "publisher",
    "language",
    "retrieved_at",
    "source_published_or_updated_at",
    "license_or_usage_class",
    "reuse_storage_class",
    "reuse_evidence",
    "attribution_requirement",
    "redistributable_in_git",
    "source_terms_checked_at",
    "artifact_snapshot_timestamp",
    "raw_text",
    "content_sha256",
    "provenance_status",
    "source_lineage_id",
)

ALLOWED_DECISIONS = {
    "ACCEPT_PRIMARY_CORPUS",
    "ACCEPT_RESTRICTED_RESEARCH_ONLY",
    "REFERENCE_ONLY",
    "REJECT",
}

ALLOWED_REUSE_CLASSES = {
    "OPEN_REUSABLE",
    "RESEARCH_RESTRICTED",
    "REFERENCE_ONLY",
    "PROHIBITED",
}

ALLOWED_FACT_AUDIT_STATUSES = {
    "CORROBORATED",
    "CONFLICTED",
    "UNVERIFIED",
    "MISSING",
}

REQUIRED_OVERTURE_AUDIT_FIELDS: tuple[str, ...] = (
    "coordinates",
    "address",
    "category_taxonomy",
    "phone",
    "website",
)

OVERTURE_FIELD_LINE_PREFIXES: dict[str, str] = {
    "address": "Địa chỉ cấu trúc (Overture addresses):",
    "phone": "Số điện thoại liên hệ (Overture phones):",
    "website": "Liên kết website/trang thông tin (Overture websites):",
    "category_taxonomy": "Danh mục cơ bản:",
}

OVERTURE_SUBSTANTIVE_ATTRIBUTE_PREFIXES: tuple[str, ...] = (
    "Địa chỉ cấu trúc (Overture addresses):",
    "Số điện thoại liên hệ (Overture phones):",
    "Liên kết website/trang thông tin (Overture websites):",
)

FORBIDDEN_RAW_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r":\s*nan\b", re.IGNORECASE),
    re.compile(r":\s*nat\b", re.IGNORECASE),
    re.compile(r":\s*none\b", re.IGNORECASE),
    re.compile(r":\s*null\b", re.IGNORECASE),
    re.compile(r"^\s*(?:todo|tbd|n/a|placeholder)\s*$", re.IGNORECASE),
)

SUBSTANTIVE_STRUCTURED_PREFIXES: tuple[str, ...] = (
    "Danh mục cơ bản:",
    "Trạng thái hoạt động:",
    "Độ tin cậy bản ghi Overture (confidence):",
    "Địa chỉ cấu trúc (Overture addresses):",
    "Số điện thoại liên hệ (Overture phones):",
    "Liên kết website/trang thông tin (Overture websites):",
    "Nguồn đóng góp bản ghi (Overture sources):",
    "Mô tả thực thể (vi/en):",
    "Tên gọi khác (aliases):",
    "Phân loại thực thể (instance of P31):",
    "Đơn vị hành chính (located in P131):",
    "Quốc gia (country P17):",
    "Tọa độ địa lý Wikidata (P625):",
    "Danh hiệu di sản (heritage designation P1435):",
    "Năm thành lập / khánh thành (P571/P1619):",
    "Địa chỉ đường phố (P6375):",
    "Mã bưu chính (P281):",
    "Số tầng (P1101):",
    "Website chính thức (P856):",
)

ISO_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _verify_internal_sha256(payload: dict[str, Any], label: str) -> None:
    expected = payload.get("artifact_sha256")
    if not expected:
        raise ValueError(f"{label}: missing artifact_sha256")
    copy_data = dict(payload)
    copy_data.pop("artifact_sha256", None)
    canonical = json.dumps(copy_data, ensure_ascii=False, indent=2, sort_keys=True)
    actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if actual != expected:
        raise ValueError(f"{label}: internal artifact_sha256 mismatch ({actual} != {expected})")


def validate_temporal_provenance(record: dict[str, Any], *, is_document: bool = True) -> None:
    """Fail-closed temporal provenance validator enforcing 4 separated timestamp concepts."""
    rid = record.get("document_id") or record.get("candidate_source_id") or "<unknown>"
    for key in (
        "retrieved_at",
        "source_published_or_updated_at",
        "source_terms_checked_at",
        "artifact_snapshot_timestamp",
    ):
        val = record.get(key)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"Record {rid}: missing or empty temporal provenance field {key!r}")

    retrieved_at = record["retrieved_at"]
    published_at = record["source_published_or_updated_at"]
    terms_checked_at = record["source_terms_checked_at"]
    snapshot_at = record["artifact_snapshot_timestamp"]

    if snapshot_at != b1b.ARTIFACT_SNAPSHOT_TIMESTAMP:
        raise ValueError(
            f"Record {rid}: artifact_snapshot_timestamp ({snapshot_at!r}) != {b1b.ARTIFACT_SNAPSHOT_TIMESTAMP!r}"
        )

    # Never conflate retrieved_at or source_terms_checked_at with source_published_or_updated_at
    if retrieved_at == published_at:
        raise ValueError(
            f"Record {rid}: retrieved_at ({retrieved_at!r}) must not equal source_published_or_updated_at ({published_at!r})"
        )
    if terms_checked_at == published_at:
        raise ValueError(
            f"Record {rid}: source_terms_checked_at ({terms_checked_at!r}) must not equal source_published_or_updated_at ({published_at!r})"
        )

    source_type = record.get("source_type")
    if source_type == "overture_places_parquet":
        if retrieved_at != b1b.UNKNOWN_HISTORICAL_RETRIEVAL_TIME:
            raise ValueError(
                f"Record {rid}: Overture local Parquet record must use retrieved_at={b1b.UNKNOWN_HISTORICAL_RETRIEVAL_TIME!r}, got {retrieved_at!r}"
            )
        if published_at != b1b.OVERTURE_SNAPSHOT_TIMESTAMP:
            raise ValueError(
                f"Record {rid}: Overture record must use source_published_or_updated_at={b1b.OVERTURE_SNAPSHOT_TIMESTAMP!r}, got {published_at!r}"
            )
        allowed_ov_terms = (
            (b1b.B1B_TERMS_CHECKED_AT,)
            if is_document
            else (b1b.B1B_TERMS_CHECKED_AT, "NOT_APPLICABLE_REJECTED_AT_MAPPING_GATE")
        )
        if terms_checked_at not in allowed_ov_terms:
            raise ValueError(
                f"Record {rid}: Overture record must use source_terms_checked_at in {allowed_ov_terms!r}, got {terms_checked_at!r}"
            )
    elif source_type in ("wikipedia_article", "wikidata_entity", "wikivoyage_poi_listing"):
        if is_document or record.get("final_b1b_decision") == "ACCEPT_PRIMARY_CORPUS":
            if retrieved_at != b1b.B1B_API_RETRIEVED_AT:
                raise ValueError(
                    f"Record {rid}: Wikimedia API-fetched record must have retrieved_at={b1b.B1B_API_RETRIEVED_AT!r}, got {retrieved_at!r}"
                )
            if terms_checked_at != b1b.B1B_TERMS_CHECKED_AT:
                raise ValueError(
                    f"Record {rid}: Wikimedia API-fetched record must have source_terms_checked_at={b1b.B1B_TERMS_CHECKED_AT!r}, got {terms_checked_at!r}"
                )
            if not ISO_UTC_RE.match(published_at):
                raise ValueError(
                    f"Record {rid}: Wikimedia record source_published_or_updated_at must be ISO-8601 UTC revision timestamp, got {published_at!r}"
                )
    elif source_type in ("official_venue_website", "heritage_or_public_institution_portal"):
        if terms_checked_at != "NOT_INDEPENDENTLY_CHECKED":
            raise ValueError(
                f"Record {rid}: uninspected website candidate must have source_terms_checked_at='NOT_INDEPENDENTLY_CHECKED'"
            )


def validate_document_content_utility(
    doc: dict[str, Any],
    *,
    expected_section_heading: str | None = None,
) -> None:
    """Fail-closed content utility validator for an accepted primary corpus document."""
    did = doc.get("document_id", "<unknown>")
    raw_text = str(doc.get("raw_text") or "")
    if not raw_text.strip():
        raise ValueError(f"Document {did}: raw_text is empty")

    for pat in FORBIDDEN_RAW_TEXT_PATTERNS:
        if pat.search(raw_text):
            raise ValueError(
                f"Document {did}: raw_text contains forbidden NaN/null/placeholder pattern ({pat.pattern})"
            )

    lines = raw_text.splitlines()
    if not lines or not lines[0].startswith("Địa điểm: "):
        raise ValueError(f"Document {did}: missing generated provenance header line ('Địa điểm: ...')")

    body_text = "\n".join(lines[1:]).strip()
    body_lines = [line.strip() for line in lines[1:] if line.strip()]
    if not body_text or not body_lines:
        raise ValueError(f"Document {did}: empty body after stripping generated provenance header line")

    source_type = doc.get("source_type")
    utility = doc.get("content_utility_status")

    if source_type == "wikipedia_article":
        if utility != "USEFUL_NARRATIVE":
            raise ValueError(f"Document {did}: wikipedia_article must have USEFUL_NARRATIVE, got {utility}")
        ok, reason = b1b.validate_wikipedia_narrative_body(body_text, expected_section_heading)
        if not ok:
            raise ValueError(f"Document {did}: invalid Wikipedia narrative body ({reason})")
        recorded_len = doc.get("article_body_char_length")
        if recorded_len is not None and recorded_len != len(body_text):
            raise ValueError(
                f"Document {did}: article_body_char_length ({recorded_len}) != actual body length ({len(body_text)})"
            )

    elif source_type == "wikivoyage_poi_listing":
        if utility != "USEFUL_NARRATIVE":
            raise ValueError(f"Document {did}: wikivoyage_poi_listing must have USEFUL_NARRATIVE, got {utility}")
        desc_lines = [
            line.split("Mô tả du lịch chi tiết (Wikivoyage):", 1)[1].strip()
            for line in body_lines
            if line.startswith("Mô tả du lịch chi tiết (Wikivoyage):")
        ]
        if not desc_lines or len(desc_lines[0]) < 25:
            raise ValueError(
                f"Document {did}: Wikivoyage listing lacks genuine POI-specific narrative prose (>=25 chars)"
            )
        if re.fullmatch(r"(?:todo|tbd|n/a|none|null|nan|\W)+", desc_lines[0], flags=re.IGNORECASE):
            raise ValueError(f"Document {did}: Wikivoyage narrative description is placeholder-only")

    elif source_type in ("overture_places_parquet", "wikidata_entity"):
        if utility != "USEFUL_STRUCTURED_FACTS":
            raise ValueError(f"Document {did}: {source_type} must have USEFUL_STRUCTURED_FACTS, got {utility}")
        substantive_facts = []
        for line in body_lines:
            for prefix in SUBSTANTIVE_STRUCTURED_PREFIXES:
                if line.startswith(prefix):
                    val = line[len(prefix) :].strip()
                    if val and val.lower() not in ("nan", "nat", "none", "null", "n/a"):
                        substantive_facts.append(val)
        if not substantive_facts:
            raise ValueError(f"Document {did}: structured document has 0 substantive sourced facts beyond name/header")

        if source_type == "overture_places_parquet":
            lic = doc.get("license_or_usage_class")
            if lic not in b1b.ALLOWED_OVERTURE_OPEN_LICENSES:
                raise ValueError(f"Document {did}: Overture document has unapproved license {lic!r}")

            suppressed = set(doc.get("suppressed_conflicted_fields") or [])
            audit_map = doc.get("fact_consistency_audit") or {}
            for field_name, field_info in audit_map.items():
                if isinstance(field_info, dict) and field_info.get("status") == "CONFLICTED":
                    if field_name not in suppressed:
                        raise ValueError(
                            f"Document {did}: field {field_name!r} is marked CONFLICTED in fact_consistency_audit but missing from suppressed_conflicted_fields"
                        )
                    conflicted_val = str(field_info.get("overture_value") or "").strip()
                    if conflicted_val and conflicted_val in raw_text:
                        raise ValueError(
                            f"Document {did}: CONFLICTED value {conflicted_val!r} for field {field_name!r} is still rendered in raw_text"
                        )

            for field_name in suppressed:
                prefix = OVERTURE_FIELD_LINE_PREFIXES.get(field_name)
                if prefix and any(line.startswith(prefix) for line in body_lines):
                    raise ValueError(
                        f"Document {did}: suppressed conflicted field {field_name!r} ({prefix}) is still rendered in raw_text"
                    )

            substantive_overture_lines = [
                line
                for line in body_lines
                if any(line.startswith(prefix) for prefix in OVERTURE_SUBSTANTIVE_ATTRIBUTE_PREFIXES)
            ]
            retained_fields = doc.get("retained_substantive_fields")
            if not substantive_overture_lines or (isinstance(retained_fields, list) and len(retained_fields) == 0):
                raise ValueError(
                    f"Document {did}: Overture document has all substantive place attributes suppressed/missing and must be downgraded to LOW_INFORMATION"
                )
    else:
        raise ValueError(f"Document {did}: unsupported primary corpus source_type {source_type!r}")


def validate_overture_fact_consistency_audit(
    decisions: dict[str, Any],
    summary: dict[str, Any],
    docs: list[dict[str, Any]],
) -> None:
    """Fail-closed validator for the 26-record Overture fact-consistency audit and conflict handling."""
    dec_audit = decisions.get("overture_fact_consistency_audit")
    sum_audit = summary.get("overture_fact_consistency_audit") or summary.get(
        "overture_quality_and_license_integrity", {}
    ).get("fact_consistency_summary")
    if not isinstance(dec_audit, dict) or not isinstance(sum_audit, dict):
        raise ValueError("Missing overture_fact_consistency_audit in decisions or summary JSON")

    for label, audit_obj in (("decisions", dec_audit), ("summary", sum_audit)):
        if audit_obj.get("total_overture_records_audited") != 26:
            raise ValueError(f"{label}: expected total_overture_records_audited == 26")
        if audit_obj.get("total_field_evaluations") != 130:
            raise ValueError(f"{label}: expected total_field_evaluations == 130")

    audit_records = dec_audit.get("records")
    if not isinstance(audit_records, list) or len(audit_records) != 26:
        raise ValueError("decisions.overture_fact_consistency_audit.records must contain 26 records")

    ov_docs_by_poi = {d["poi_id"]: d for d in docs if d.get("source_type") == "overture_places_parquet"}
    all_raw_text = "\n".join(d.get("raw_text", "") for d in docs)

    # Explicit FC-001 and FC-002 conflict suppression checks
    for forbidden_str in (
        "1 Đường Trực Nguyên",
        "Huyện Thường Tín",
        "13618",
        "439 P. Lê Lợi",
    ):
        if forbidden_str in all_raw_text:
            raise ValueError(f"Conflicted Overture address substring {forbidden_str!r} leaked into accepted raw_text")

    status_counts = {"CORROBORATED": 0, "CONFLICTED": 0, "UNVERIFIED": 0, "MISSING": 0}
    audit_by_poi: dict[str, dict[str, Any]] = {}

    for rec in audit_records:
        poi_id = rec.get("poi_id")
        gers_id = rec.get("gers_id")
        if not poi_id or not gers_id:
            raise ValueError(f"Overture audit record missing poi_id or gers_id: {rec}")
        audit_by_poi[poi_id] = rec
        field_audit = rec.get("field_audit")
        if not isinstance(field_audit, dict) or tuple(field_audit.keys()) != REQUIRED_OVERTURE_AUDIT_FIELDS:
            raise ValueError(
                f"Overture audit record {gers_id} must evaluate exact fields {REQUIRED_OVERTURE_AUDIT_FIELDS}"
            )

        suppressed = set(rec.get("suppressed_conflicted_fields") or [])
        for fname, finfo in field_audit.items():
            st = finfo.get("status")
            if st not in ALLOWED_FACT_AUDIT_STATUSES:
                raise ValueError(f"Overture audit {gers_id}.{fname}: invalid status {st!r}")
            status_counts[st] += 1
            if not str(finfo.get("comparison_evidence") or "").strip():
                raise ValueError(f"Overture audit {gers_id}.{fname}: missing comparison_evidence")
            corr = finfo.get("corroboration_sources")
            conf = finfo.get("conflicting_sources")
            if not isinstance(corr, list) or not isinstance(conf, list):
                raise ValueError(f"Overture audit {gers_id}.{fname}: corroboration/conflicting_sources must be lists")

            if st == "CORROBORATED":
                if len(corr) == 0:
                    raise ValueError(
                        f"Overture audit {gers_id}.{fname}: CORROBORATED field must have >=1 corroboration_sources (never mark an unchecked value as CORROBORATED)"
                    )
                if len(conf) != 0:
                    raise ValueError(
                        f"Overture audit {gers_id}.{fname}: CORROBORATED field must not have conflicting_sources"
                    )
            elif st == "CONFLICTED":
                if len(conf) == 0:
                    raise ValueError(
                        f"Overture audit {gers_id}.{fname}: CONFLICTED field must have >=1 conflicting_sources"
                    )
                if fname not in suppressed:
                    raise ValueError(
                        f"Overture audit {gers_id}.{fname}: CONFLICTED field must be listed in suppressed_conflicted_fields"
                    )
            elif st in ("UNVERIFIED", "MISSING"):
                if len(corr) != 0:
                    raise ValueError(
                        f"Overture audit {gers_id}.{fname}: {st} field must have empty corroboration_sources"
                    )

        post_map = rec.get("post_audit_canonical_mapping_status")
        post_util = rec.get("post_audit_content_utility_status")
        post_dec = rec.get("post_audit_final_b1b_decision")
        retained = rec.get("retained_substantive_fields") or []

        if post_map != "EXACT_MAPPED" or post_util != "USEFUL_STRUCTURED_FACTS":
            if post_dec != "REJECT":
                raise ValueError(f"Overture audit {gers_id}: non-exact or non-useful record must have REJECT decision")
            if poi_id in ov_docs_by_poi:
                raise ValueError(f"Rejected Overture record {gers_id} ({poi_id}) must not appear in accepted JSONL")
        else:
            if len(retained) == 0:
                raise ValueError(
                    f"Overture audit {gers_id}: accepted record has 0 retained_substantive_fields and must be downgraded to LOW_INFORMATION"
                )
            if post_dec != "ACCEPT_PRIMARY_CORPUS":
                raise ValueError(f"Overture audit {gers_id}: expected ACCEPT_PRIMARY_CORPUS")
            if poi_id not in ov_docs_by_poi:
                raise ValueError(f"Accepted Overture record {gers_id} ({poi_id}) missing from accepted JSONL")

    if dec_audit.get("field_status_counts") != status_counts:
        raise ValueError(
            f"Overture audit field_status_counts mismatch: {dec_audit.get('field_status_counts')} != {status_counts}"
        )

    # Check FC-001 and FC-002 specifically in audit table
    fc001 = audit_by_poi.get("f0d424bd-f722-540f-8964-5e6fd8875b56")
    fc002 = audit_by_poi.get("75a3fbd1-a24e-43c6-820a-72f95ebc05c0")
    if not fc001 or fc001["field_audit"]["address"]["status"] != "CONFLICTED":
        raise ValueError("FC-001 (Vietnam Museum of Ethnology) address must be marked CONFLICTED")
    if not fc002 or fc002["field_audit"]["address"]["status"] != "CONFLICTED":
        raise ValueError("FC-002 (Vinpearl Resort & Spa Ha Long) address must be marked CONFLICTED")


def verify_b1b_artifacts() -> dict[str, Any]:
    for path in (b1b.DECISIONS_JSON_PATH, b1b.ACQUIRED_JSONL_PATH, b1b.SUMMARY_JSON_PATH, b1b.REPORT_MD_PATH):
        if not path.exists():
            raise FileNotFoundError(f"Missing required W07-B1B deliverable: {path}")

    target_manifest = json.loads(b1b.TARGET_60_PATH.read_text(encoding="utf-8"))
    target_pois = {p["poi_id"]: p for p in target_manifest["pois"]}
    if len(target_pois) != 60:
        raise ValueError(f"Expected 60 frozen target POIs, found {len(target_pois)}")

    decisions = json.loads(b1b.DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    summary = json.loads(b1b.SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    report_md = b1b.REPORT_MD_PATH.read_text(encoding="utf-8")

    _verify_internal_sha256(decisions, "w07_b1b_source_decisions_v1.json")
    _verify_internal_sha256(summary, "w07_b1b_acquisition_summary_v1.json")

    # Check header & authority invariants
    for obj, name in ((decisions, "decisions"), (summary, "summary")):
        if obj.get("authoritative_base_develop_sha") != b1b.AUTHORITATIVE_BASE_DEVELOP_SHA:
            raise ValueError(f"{name}: authoritative_base_develop_sha mismatch")
        if obj.get("previous_accepted_gate") != b1b.PREVIOUS_ACCEPTED_GATE:
            raise ValueError(f"{name}: previous_accepted_gate mismatch")
        if obj.get("artifact_snapshot_timestamp") != b1b.ARTIFACT_SNAPSHOT_TIMESTAMP:
            raise ValueError(f"{name}: artifact_snapshot_timestamp mismatch")
        if obj.get("W07_B1_FIX_01B_STATUS") != "CLOSED":
            raise ValueError(f"{name}: W07_B1_FIX_01B_STATUS must be CLOSED")
        if obj.get("PDG_001_STATUS") != "CLOSED":
            raise ValueError(f"{name}: PDG_001_STATUS must be CLOSED")
        if obj.get("W07_PRIMARY_CORPUS_STRATEGY") != "EVIDENCE_GROUNDED_POI_KNOWLEDGE":
            raise ValueError(f"{name}: W07_PRIMARY_CORPUS_STRATEGY mismatch")
        if obj.get("HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION") is not True:
            raise ValueError(f"{name}: HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION must be True")
        if obj.get("OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC") is not True:
            raise ValueError(f"{name}: OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC must be True")
        if obj.get("GOOGLE_MAPS_ROLE") != "RUNTIME_ENRICHMENT_ONLY":
            raise ValueError(f"{name}: GOOGLE_MAPS_ROLE mismatch")
        if obj.get("SOCIAL_PLATFORM_ROLE") != "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS":
            raise ValueError(f"{name}: SOCIAL_PLATFORM_ROLE mismatch")

    if summary.get("SOCIAL_FUTURE_RESERVED_TASK_ID") != "SOCIAL-FRESHNESS-01":
        raise ValueError("summary: SOCIAL_FUTURE_RESERVED_TASK_ID mismatch")
    if summary.get("PLACE_DISCOVERY_FUTURE_RESERVED_TASK_ID") != "PLACE-DISCOVERY-01":
        raise ValueError("summary: PLACE_DISCOVERY_FUTURE_RESERVED_TASK_ID mismatch")
    if summary.get("next_gate") != b1b.NEXT_GATE:
        raise ValueError("summary: next_gate mismatch")

    # Build lookup of expected Wikipedia section headings by (poi_id, lang)
    wp_section_by_poi: dict[str, str | None] = {
        spec["poi_id"]: spec.get("section_heading") for spec in b1b.ACCEPTED_WIKIPEDIA_SPECS
    }

    # Verify candidate_decisions
    candidates = decisions.get("candidate_decisions", [])
    if not candidates:
        raise ValueError("No candidate_decisions found")
    cand_ids = set()
    accepted_doc_ids_from_decisions = set()
    for c in candidates:
        missing = [f for f in REQUIRED_CANDIDATE_FIELDS if f not in c or c[f] is None or c[f] == ""]
        if missing:
            raise ValueError(f"Candidate {c.get('candidate_source_id')} missing required fields: {missing}")
        cid = c["candidate_source_id"]
        if cid in cand_ids:
            raise ValueError(f"Duplicate candidate_source_id: {cid}")
        cand_ids.add(cid)
        if c["poi_id"] not in target_pois:
            raise ValueError(f"Candidate {cid} maps to unknown poi_id {c['poi_id']}")
        if c["reuse_storage_class"] not in ALLOWED_REUSE_CLASSES:
            raise ValueError(f"Candidate {cid} has invalid reuse_storage_class {c['reuse_storage_class']}")
        if c["final_b1b_decision"] not in ALLOWED_DECISIONS:
            raise ValueError(f"Candidate {cid} has invalid final_b1b_decision {c['final_b1b_decision']}")

        validate_temporal_provenance(c, is_document=False)

        # Section 5: Official website governance check
        if c["source_type"] in ("official_venue_website", "heritage_or_public_institution_portal"):
            if c.get("discovery_method") != "URL_DISCOVERED_FROM_OSM_TAG":
                raise ValueError(f"Website candidate {cid} must have discovery_method=URL_DISCOVERED_FROM_OSM_TAG")
            if c.get("website_terms_independently_checked") is not False:
                raise ValueError(f"Website candidate {cid} must have website_terms_independently_checked=False")
            if c.get("terms_verification_status") != "REUSE_PERMISSION_NOT_ESTABLISHED":
                raise ValueError(
                    f"Website candidate {cid} must have terms_verification_status=REUSE_PERMISSION_NOT_ESTABLISHED"
                )
            if c.get("source_terms_checked_at") != "NOT_INDEPENDENTLY_CHECKED":
                raise ValueError(f"Website candidate {cid} must have source_terms_checked_at=NOT_INDEPENDENTLY_CHECKED")
            if c.get("content_utility_status") == "USEFUL_NARRATIVE":
                raise ValueError(f"Uninspected website candidate {cid} must not be marked USEFUL_NARRATIVE")
            if c.get("final_b1b_decision") != "REFERENCE_ONLY":
                raise ValueError(f"Website candidate {cid} must have final_b1b_decision=REFERENCE_ONLY")
            if "Inspected `" in c.get("license_or_reuse_evidence", ""):
                raise ValueError(f"Website candidate {cid} must not claim website terms were inspected")

        if c["final_b1b_decision"] == "ACCEPT_PRIMARY_CORPUS":
            if c["canonical_mapping_status"] != "EXACT_MAPPED":
                raise ValueError(f"Accepted candidate {cid} must be EXACT_MAPPED")
            if c["reuse_storage_class"] != "OPEN_REUSABLE":
                raise ValueError(f"Accepted candidate {cid} must be OPEN_REUSABLE")
            if c["redistributable_in_git"] is not True or c["raw_text_permitted"] is not True:
                raise ValueError(
                    f"Accepted candidate {cid} must have redistributable_in_git=True and raw_text_permitted=True"
                )
            if c.get("content_utility_status") not in ("USEFUL_NARRATIVE", "USEFUL_STRUCTURED_FACTS"):
                raise ValueError(f"Accepted candidate {cid} has non-useful content_utility_status")
            accepted_doc_ids_from_decisions.add(c["accepted_document_id"])
        else:
            if c["redistributable_in_git"] is not False or c["raw_text_permitted"] is not False:
                raise ValueError(
                    f"Non-accepted candidate {cid} must have redistributable_in_git=False and raw_text_permitted=False"
                )

    # Verify JSONL documents
    raw_lines = [line for line in b1b.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    docs = [json.loads(line) for line in raw_lines]
    if len(docs) != len(accepted_doc_ids_from_decisions):
        raise ValueError(
            f"JSONL document count ({len(docs)}) != accepted decision count ({len(accepted_doc_ids_from_decisions)})"
        )

    seen_doc_ids = set()
    seen_hashes = set()
    wp_docs_count = 0
    for d in docs:
        missing = [f for f in REQUIRED_DOCUMENT_FIELDS if f not in d or d[f] is None or d[f] == ""]
        if missing:
            raise ValueError(f"Document {d.get('document_id')} missing required B0 schema fields: {missing}")
        did = d["document_id"]
        if did in seen_doc_ids:
            raise ValueError(f"Duplicate document_id in JSONL: {did}")
        seen_doc_ids.add(did)
        if did not in accepted_doc_ids_from_decisions:
            raise ValueError(f"Document {did} in JSONL not backed by ACCEPT_PRIMARY_CORPUS decision")
        if d["poi_id"] not in target_pois:
            raise ValueError(f"Document {did} maps to unknown poi_id {d['poi_id']}")
        if d["reuse_storage_class"] != "OPEN_REUSABLE" or d["redistributable_in_git"] is not True:
            raise ValueError(f"Document {did} in Git JSONL must be OPEN_REUSABLE and redistributable_in_git=True")
        computed_sha = hashlib.sha256(d["raw_text"].encode("utf-8")).hexdigest()
        if computed_sha != d["content_sha256"]:
            raise ValueError(f"Document {did} content_sha256 mismatch")
        if computed_sha in seen_hashes:
            raise ValueError(f"Duplicate content_sha256 in JSONL: {computed_sha}")
        seen_hashes.add(computed_sha)

        validate_temporal_provenance(d, is_document=True)
        expected_heading = wp_section_by_poi.get(d["poi_id"]) if d["source_type"] == "wikipedia_article" else None
        validate_document_content_utility(d, expected_section_heading=expected_heading)
        if d["source_type"] == "wikipedia_article":
            wp_docs_count += 1

    # Section 1–3 (Corrective 02): Verify 26-record Overture fact-consistency audit
    validate_overture_fact_consistency_audit(decisions, summary, docs)

    # Section 1 (Corrective 01): Wikipedia empty body check
    dec_sum = decisions["decision_summary"]
    if dec_sum.get("WIKIPEDIA_DOCUMENTS_ACCEPTED") != wp_docs_count or wp_docs_count != 26:
        raise ValueError(f"Expected 26 accepted Wikipedia documents, got {wp_docs_count}")
    if dec_sum.get("WIKIPEDIA_DOCUMENTS_WITH_NONEMPTY_ARTICLE_BODY") != 26:
        raise ValueError("Expected WIKIPEDIA_DOCUMENTS_WITH_NONEMPTY_ARTICLE_BODY == 26")
    if dec_sum.get("WIKIPEDIA_DOCUMENTS_WITH_EMPTY_ARTICLE_BODY") != 0:
        raise ValueError("Expected WIKIPEDIA_DOCUMENTS_WITH_EMPTY_ARTICLE_BODY == 0")

    wp_integrity = summary.get("wikipedia_narrative_integrity", {})
    if wp_integrity.get("WIKIPEDIA_DOCUMENTS_WITH_EMPTY_ARTICLE_BODY") != 0:
        raise ValueError("summary wikipedia_narrative_integrity must have 0 empty article bodies")
    if wp_integrity.get("WIKIPEDIA_DOCUMENTS_WITH_NONEMPTY_ARTICLE_BODY") != 26:
        raise ValueError("summary wikipedia_narrative_integrity must have 26 non-empty article bodies")

    # Verify lineage vs evidence unit separation (post-Corrective-02 recomputed counts)
    unique_lineages = {d["source_lineage_id"] for d in docs}
    if len(unique_lineages) >= len(docs):
        raise ValueError("Expected multiple Wikivoyage/Wikipedia extracts from same page to share source_lineage_id")
    if len(docs) != 97 or len(unique_lineages) != 78:
        raise ValueError(f"Expected 97 documents and 78 unique lineages, got {len(docs)} and {len(unique_lineages)}")

    # Verify linked_artifacts hashes in summary
    linked = summary["linked_artifacts"]
    if linked["source_decisions_internal_sha256"] != decisions["artifact_sha256"]:
        raise ValueError("summary linked source_decisions_internal_sha256 mismatch")
    if linked["source_decisions_lf_sha256"] != w07_a2.compute_file_sha256(b1b.DECISIONS_JSON_PATH):
        raise ValueError("summary linked source_decisions_lf_sha256 mismatch")
    if linked["acquired_corpus_jsonl_lf_sha256"] != w07_a2.compute_file_sha256(b1b.ACQUIRED_JSONL_PATH):
        raise ValueError("summary linked acquired_corpus_jsonl_lf_sha256 mismatch")

    # Verify activity counters & zero-violation guards
    counters = summary["external_activity_counters"]
    if counters["PAID_DATA_API_USED"] is not False:
        raise ValueError("PAID_DATA_API_USED must be False")
    if counters["NEW_SOCIAL_COLLECTION"] != 0:
        raise ValueError("NEW_SOCIAL_COLLECTION must be 0")
    if counters["NEW_GOOGLE_MAPS_REVIEW_COLLECTION"] != 0:
        raise ValueError("NEW_GOOGLE_MAPS_REVIEW_COLLECTION must be 0")
    if counters["NEW_LLM_PROVIDER_CALLS"] != 0:
        raise ValueError("NEW_LLM_PROVIDER_CALLS must be 0")
    if counters["EXTERNAL_WEBSITE_HTTP_REQUESTS"] != 0:
        raise ValueError("EXTERNAL_WEBSITE_HTTP_REQUESTS must be 0")
    if counters["OPEN_REUSABLE_DOCUMENTS_ACCEPTED"] != len(docs):
        raise ValueError("OPEN_REUSABLE_DOCUMENTS_ACCEPTED mismatch")
    if counters["REFERENCE_ONLY_SOURCES"] != 16:
        raise ValueError("Expected 16 REFERENCE_ONLY_SOURCES")
    if counters["RESEARCH_RESTRICTED_SOURCES"] != 0:
        raise ValueError("Expected 0 RESEARCH_RESTRICTED_SOURCES")
    if counters["REJECTED_SOURCES"] != 19:
        raise ValueError(f"Expected 19 REJECTED_SOURCES, got {counters['REJECTED_SOURCES']}")
    if (
        counters["WEB_SOURCE_PAGES_CHECKED"]
        != counters["WIKIPEDIA_PAGES_FETCHED_VIA_API"]
        + counters["WIKIDATA_ENTITIES_FETCHED_VIA_API"]
        + counters["WIKIVOYAGE_PAGES_FETCHED_VIA_API"]
    ):
        raise ValueError("WEB_SOURCE_PAGES_CHECKED does not equal sum of measured API page/entity fetches")

    # Recompute narrative & structured coverage directly from validated documents
    validated_narrative_pois = {d["poi_id"] for d in docs if d["content_utility_status"] == "USEFUL_NARRATIVE"}
    ov_cov = summary["coverage_after_acquisition"]["overall_60_pois"]
    if ov_cov["total_pois"] != 60:
        raise ValueError("Expected 60 total POIs")
    if ov_cov["pois_with_rag_candidate_evidence"] != 51:
        raise ValueError(
            f"Expected 51 POIs with RAG candidate evidence, got {ov_cov['pois_with_rag_candidate_evidence']}"
        )
    if ov_cov["pois_with_2_plus_eligible_lineages"] != 42:
        raise ValueError(
            f"Expected 42 POIs with >=2 eligible lineages, got {ov_cov['pois_with_2_plus_eligible_lineages']}"
        )
    if ov_cov["pois_with_narrative_evidence"] != len(validated_narrative_pois) or len(validated_narrative_pois) != 32:
        raise ValueError(
            f"Expected 32 validated narrative POIs, got {ov_cov['pois_with_narrative_evidence']} vs {len(validated_narrative_pois)}"
        )
    if ov_cov["pois_with_structured_evidence"] != 48:
        raise ValueError(f"Expected 48 POIs with structured evidence, got {ov_cov['pois_with_structured_evidence']}")
    if ov_cov["pois_with_both_structured_and_narrative"] != 29:
        raise ValueError(
            f"Expected 29 POIs with both structured and narrative, got {ov_cov['pois_with_both_structured_and_narrative']}"
        )
    if summary["W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2"] is not True:
        raise ValueError("W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2 must be True")

    # Section 9: Verify future chunk range is explicitly labeled as ESTIMATE
    est_chunks = summary["b2_readiness_evaluation"]["estimated_future_useful_chunk_range"]
    if est_chunks.get("value_kind") != "ESTIMATE" or est_chunks.get("observed_chunk_count_in_b1b") is not None:
        raise ValueError("estimated_future_useful_chunk_range must be explicitly labeled value_kind=ESTIMATE")

    # Verify no chunking/retrieval methodology frozen
    no_freeze = summary["no_chunking_or_retrieval_methodology_freeze"]
    if any(bool(v) for v in no_freeze.values()):
        raise ValueError(f"Chunking/retrieval methodology must not be frozen in B1B: {no_freeze}")

    # Verify upstream immutability
    for rel_path, expected_sha in b1b.UPSTREAM_ARTIFACT_LF_HASHES.items():
        actual_sha = w07_a2.compute_file_sha256(REPO_ROOT / rel_path)
        if actual_sha != expected_sha:
            raise ValueError(f"Upstream artifact modified: {rel_path} ({actual_sha} != {expected_sha})")

    # Verify report contains hashes
    if decisions["artifact_sha256"] not in report_md or summary["artifact_sha256"] not in report_md:
        raise ValueError("Markdown report does not match JSON artifact hashes")

    return {
        "status": "PASS",
        "candidates_evaluated": len(candidates),
        "accepted_primary_documents": len(docs),
        "accepted_independent_lineages": len(unique_lineages),
        "wikipedia_documents_accepted": wp_docs_count,
        "wikipedia_documents_with_empty_body": 0,
        "overture_records_audited": 26,
        "overture_documents_accepted": len([d for d in docs if d["source_type"] == "overture_places_parquet"]),
        "pois_with_rag_evidence": ov_cov["pois_with_rag_candidate_evidence"],
        "W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2": summary["W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify W07-B1B POI Knowledge Acquisition Artifacts")
    parser.add_argument("--verify-only", action="store_true", help="Run offline verification only")
    parser.parse_args(argv)
    res = verify_b1b_artifacts()
    print(f"PASS: W07-B1B verification succeeded: {json.dumps(res)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
