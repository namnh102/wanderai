"""W07-B1B tests: Targeted POI knowledge acquisition, Corrective 01, 02 & 03 source ID binding, fact consistency, unverified fact handling, and temporal provenance."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "apps" / "ai-service") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "apps" / "ai-service"))

from scripts import (  # noqa: E402
    acquire_w07_b1b_poi_knowledge as b1b_acquire,
    validate_w07_review_corpus_v1 as w07_a2,
    verify_w07_b1b_poi_knowledge as b1b_verify,
)


def _resign(payload: dict) -> dict:
    out = copy.deepcopy(payload)
    out.pop("artifact_sha256", None)
    canonical = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True)
    out["artifact_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return out


def test_01_b1b_verification_passes():
    result = b1b_verify.verify_b1b_artifacts()
    assert result["status"] == "PASS"
    assert result["candidates_evaluated"] == 132
    assert result["accepted_primary_documents"] == 97
    assert result["accepted_independent_lineages"] == 78
    assert result["wikipedia_documents_accepted"] == 26
    assert result["wikipedia_documents_with_empty_body"] == 0
    assert result["overture_records_audited"] == 26
    assert result["overture_documents_accepted"] == 23
    assert result["osm_source_reference_mismatches_reconciled"] == 43
    assert result["remaining_osm_source_reference_mismatches"] == 0
    assert result["pois_with_rag_evidence"] == 51
    assert result["W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2"] is True


def test_02_source_decisions_schema_and_two_gate_rules():
    decisions = json.loads(b1b_acquire.DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    assert decisions["HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION"] is True
    assert decisions["OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC"] is True
    assert decisions["artifact_snapshot_timestamp"] == b1b_acquire.ARTIFACT_SNAPSHOT_TIMESTAMP

    dec_sum = decisions["decision_summary"]
    assert dec_sum["WIKIPEDIA_DOCUMENTS_ACCEPTED"] == 26
    assert dec_sum["WIKIPEDIA_DOCUMENTS_WITH_NONEMPTY_ARTICLE_BODY"] == 26
    assert dec_sum["WIKIPEDIA_DOCUMENTS_WITH_EMPTY_ARTICLE_BODY"] == 0

    records = decisions["candidate_decisions"]
    assert len(records) == 132

    jsonl_lines = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    jsonl_lineages = {doc["source_lineage_id"] for doc in jsonl_lines}
    jsonl_urls = {doc["source_url"] for doc in jsonl_lines}

    for rec in records:
        for field in b1b_verify.REQUIRED_CANDIDATE_FIELDS:
            assert field in rec and rec[field] is not None and rec[field] != ""
        b1b_verify.validate_temporal_provenance(rec, is_document=False)
        dec = rec["final_b1b_decision"]
        if dec == "ACCEPT_PRIMARY_CORPUS":
            assert rec["canonical_mapping_status"] == "EXACT_MAPPED"
            assert rec["reuse_storage_class"] == "OPEN_REUSABLE"
            assert rec["redistributable_in_git"] is True
            assert rec["raw_text_permitted"] is True
            assert rec["content_utility_status"] in ("USEFUL_NARRATIVE", "USEFUL_STRUCTURED_FACTS")
            assert rec["source_lineage_id"] in jsonl_lineages
        elif dec == "REFERENCE_ONLY":
            assert rec["source_tier"] in ("TIER_A", "TIER_B")
            assert rec["reuse_storage_class"] == "REFERENCE_ONLY"
            assert rec["redistributable_in_git"] is False
            assert rec["raw_text_permitted"] is False
            assert rec["source_lineage_id"] not in jsonl_lineages
            assert rec["source_url"] not in jsonl_urls
        elif dec == "REJECT":
            assert rec["redistributable_in_git"] is False
            assert rec["raw_text_permitted"] is False
            assert rec["canonical_mapping_status"] != "EXACT_MAPPED" or rec["content_utility_status"] in (
                "LOW_INFORMATION",
                "EMPTY_OR_INVALID",
            )


def test_03_acquired_jsonl_schema_temporal_provenance_and_hashes():
    raw_lines = [
        line for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(raw_lines) == 97

    seen_doc_ids: set[str] = set()
    for line in raw_lines:
        doc = json.loads(line)
        for field in b1b_verify.REQUIRED_DOCUMENT_FIELDS:
            assert field in doc and doc[field] is not None and doc[field] != ""
        assert doc["document_id"] not in seen_doc_ids
        seen_doc_ids.add(doc["document_id"])

        assert doc["reuse_storage_class"] == "OPEN_REUSABLE"
        assert doc["redistributable_in_git"] is True
        assert doc["provenance_status"] == "VERIFIED_PRIMARY_PROVENANCE"
        assert doc["content_utility_status"] in ("USEFUL_NARRATIVE", "USEFUL_STRUCTURED_FACTS")
        expected_sha = hashlib.sha256(doc["raw_text"].encode("utf-8")).hexdigest()
        assert doc["content_sha256"] == expected_sha
        b1b_verify.validate_temporal_provenance(doc, is_document=True)
        b1b_verify.validate_document_content_utility(doc)


def test_04_accepted_wikipedia_documents_have_nonempty_body_beyond_header():
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wp_docs = [d for d in docs if d["source_type"] == "wikipedia_article"]
    assert len(wp_docs) == 26
    for d in wp_docs:
        lines = d["raw_text"].splitlines()
        assert len(lines) >= 2
        assert lines[0].startswith("Địa điểm: ")
        body = "\n".join(lines[1:]).strip()
        assert len(body) >= 40
        assert d["article_body_char_length"] == len(body)
        ok, reason = b1b_acquire.validate_wikipedia_narrative_body(body)
        assert ok is True, f"{d['document_id']} failed narrative validation: {reason}"


def test_05_negative_empty_and_header_only_wikipedia_rejected(monkeypatch, tmp_path):
    header_only_doc = {
        "document_id": "w07-b1b-doc-wikipedia-vi-test0000-12345",
        "poi_id": "04fd8fb6-4b11-4be8-82dd-d8fb4bc83cf0",
        "city": "Đà Nẵng",
        "source_type": "wikipedia_article",
        "source_tier": "TIER_C",
        "source_title": "Wikipedia (vi): Bảo tàng Điêu khắc Chăm Đà Nẵng",
        "source_url": "https://vi.wikipedia.org/wiki/Test?oldid=1",
        "publisher": "Wikimedia Foundation (vi.wikipedia.org)",
        "language": "vi",
        "retrieved_at": b1b_acquire.UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
        "source_published_or_updated_at": "2026-10-01T00:00:00Z",
        "license_or_usage_class": "CC-BY-SA-4.0",
        "reuse_storage_class": "OPEN_REUSABLE",
        "reuse_evidence": "CC-BY-SA-4.0",
        "attribution_requirement": "Wikipedia contributors",
        "redistributable_in_git": True,
        "source_terms_checked_at": b1b_acquire.UNKNOWN_VERIFICATION_TIME,
        "artifact_snapshot_timestamp": "2026-11-03T18:45:00Z",
        "raw_text": "Địa điểm: Bảo tàng Điêu khắc Chăm (Đà Nẵng) — Bài viết bách khoa Wikipedia (vi.wikipedia.org: Test, pageid=1, oldid=1).\n",
        "content_sha256": "",
        "provenance_status": "VERIFIED_PRIMARY_PROVENANCE",
        "source_lineage_id": "wikipedia:vi:1",
        "content_utility_status": "USEFUL_NARRATIVE",
    }
    with pytest.raises(ValueError, match="empty body after stripping generated provenance header line"):
        b1b_verify.validate_document_content_utility(header_only_doc)

    # Also test that full artifact verifier fails if a Wikipedia document in JSONL has an empty body
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for d in docs:
        if d["source_type"] == "wikipedia_article":
            header_line = d["raw_text"].splitlines()[0] + "\n"
            d["raw_text"] = header_line
            d["content_sha256"] = hashlib.sha256(header_line.encode("utf-8")).hexdigest()
            break
    bad_jsonl = tmp_path / "empty_wp.jsonl"
    bad_jsonl.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in docs) + "\n", encoding="utf-8")
    monkeypatch.setattr(b1b_acquire, "ACQUIRED_JSONL_PATH", bad_jsonl)
    with pytest.raises(ValueError, match="empty body after stripping generated provenance header line"):
        b1b_verify.verify_b1b_artifacts()


def test_06_negative_wikipedia_subsection_extraction_fails_closed():
    full_text = (
        "Intro paragraph about Ha Long Bay.\n\n== History ==\nSome history text with sufficient length for testing."
    )
    with pytest.raises(ValueError, match="Requested Wikipedia section heading"):
        b1b_acquire._extract_section(full_text, "==== Hòn Đỉnh Hương (Lư Hương) ====")

    with pytest.raises(ValueError, match="full_text is empty"):
        b1b_acquire._extract_section("", "== Ban Co Peak ==")

    ok, reason = b1b_acquire.validate_wikipedia_narrative_body(
        "== Other Heading ==\nThis text is long enough to be over forty characters in total length.",
        "== Ban Co Peak ==",
    )
    assert ok is False
    assert reason == "MISSING_REQUESTED_SECTION_HEADING"


def test_07_overture_nan_none_never_rendered_and_verifier_rejects_nan():
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ov_docs = [d for d in docs if d["source_type"] == "overture_places_parquet"]
    assert len(ov_docs) == 23
    for d in ov_docs:
        assert ": nan" not in d["raw_text"].lower()
        assert ": none" not in d["raw_text"].lower()
        assert ": null" not in d["raw_text"].lower()

    # Unit test _render_overture_text with float('nan') and None fields
    poi = {"name": "Test POI", "city": "Đà Nẵng", "category": "restaurant", "sub_category": "cafe"}
    row = {
        "names": {"primary": "Test POI"},
        "categories": {"primary": "cafe", "alternate": [float("nan"), None]},
        "operating_status": float("nan"),
        "websites": [float("nan")],
        "phones": [None],
        "socials": ["nan"],
        "addresses": [{"freeform": float("nan"), "locality": "Đà Nẵng", "region": float("nan")}],
        "sources": [{"dataset": "meta", "license": "CDLA-Permissive-2.0"}],
    }
    raw_text, lic, ds = b1b_acquire._render_overture_text(poi, "08f0000000000001", row)
    assert lic == "CDLA-Permissive-2.0"
    assert "nan" not in raw_text.lower()
    assert "Trạng thái hoạt động:" not in raw_text

    # Negative test: verifier rejects structured document containing ': nan'
    bad_ov_doc = dict(ov_docs[0])
    bad_ov_doc["raw_text"] = bad_ov_doc["raw_text"] + "\nTrạng thái hoạt động: nan"
    with pytest.raises(ValueError, match="forbidden NaN/null/placeholder pattern"):
        b1b_verify.validate_document_content_utility(bad_ov_doc)


def test_08_negative_overture_license_fails_closed():
    with pytest.raises(ValueError, match="OVERTURE_LICENSE_MISSING"):
        b1b_acquire._resolve_overture_record_license({"sources": []})

    with pytest.raises(ValueError, match="OVERTURE_LICENSE_MISSING"):
        b1b_acquire._resolve_overture_record_license({"sources": [{"dataset": "meta", "license": None}]})

    with pytest.raises(ValueError, match="OVERTURE_LICENSE_AMBIGUOUS_OR_UNAPPROVED"):
        b1b_acquire._resolve_overture_record_license(
            {"sources": [{"dataset": "proprietary", "license": "All-Rights-Reserved"}]}
        )

    with pytest.raises(ValueError, match="OVERTURE_LICENSE_CONFLICT"):
        b1b_acquire._resolve_overture_record_license(
            {
                "sources": [
                    {"dataset": "meta", "license": "CDLA-Permissive-2.0"},
                    {"dataset": "other", "license": "CC0-1.0"},
                ]
            }
        )


def test_09_official_website_governance_and_reference_only_separation():
    decisions = json.loads(b1b_acquire.DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    web_cands = [
        c
        for c in decisions["candidate_decisions"]
        if c["source_type"] in ("official_venue_website", "heritage_or_public_institution_portal")
    ]
    assert len(web_cands) == 16
    for c in web_cands:
        assert c["discovery_method"] == "URL_DISCOVERED_FROM_OSM_TAG"
        assert c["website_terms_independently_checked"] is False
        assert c["terms_verification_status"] == "REUSE_PERMISSION_NOT_ESTABLISHED"
        assert c["source_terms_checked_at"] == "NOT_INDEPENDENTLY_CHECKED"
        assert c["content_utility_status"] == "LOW_INFORMATION"
        assert c["final_b1b_decision"] == "REFERENCE_ONLY"
        assert c["redistributable_in_git"] is False
        assert c["raw_text_permitted"] is False
        assert "Inspected `" not in c["license_or_reuse_evidence"]


def test_10_lineage_coverage_and_b2_readiness_estimate():
    summary = json.loads(b1b_acquire.SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    linked = summary["linked_artifacts"]
    breakdown = summary["acquired_corpus_breakdown"]
    overall = summary["coverage_after_acquisition"]["overall_60_pois"]
    est_chunks = summary["b2_readiness_evaluation"]["estimated_future_useful_chunk_range"]

    assert linked["acquired_corpus_document_count"] == 97
    assert linked["accepted_independent_source_lineage_count"] == 78
    assert breakdown["by_source_type"] == {
        "overture_places_parquet": 23,
        "wikipedia_article": 26,
        "wikidata_entity": 28,
        "wikivoyage_poi_listing": 20,
    }
    assert overall["pois_with_rag_candidate_evidence"] == 51
    assert overall["pois_with_2_plus_eligible_lineages"] == 42
    assert overall["pois_with_narrative_evidence"] == 32
    assert overall["pois_with_structured_evidence"] == 48
    assert overall["pois_with_both_structured_and_narrative"] == 29
    assert summary["W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2"] is True

    assert est_chunks["value_kind"] == "ESTIMATE"
    assert est_chunks["observed_chunk_count_in_b1b"] is None
    assert est_chunks["methodology_frozen_in_b1b"] is False


def test_11_w06_scope_protection_remains_active_for_unrelated_curated_paths():
    w06_test_path = REPO_ROOT / "tests" / "test_w06_measurement_contract.py"
    w06_text = w06_test_path.read_text(encoding="utf-8")
    assert '"data/curated/",' in w06_text
    assert '":(exclude)data/curated/w07/",' in w06_text

    summary = json.loads(b1b_acquire.SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    exc = summary["w06_scope_protection_exception"]
    assert exc["protected_root"] == "data/curated/"
    assert exc["narrow_w07_exception_pathspec"] == ":(exclude)data/curated/w07/"
    assert exc["unrelated_data_curated_paths_remain_protected"] is True


def test_12_verifier_rejects_tampered_artifacts_and_upstream_immutable(monkeypatch, tmp_path):
    bad_jsonl = tmp_path / "bad_acquired.jsonl"
    raw_lines = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    raw_lines[0]["reuse_storage_class"] = "REFERENCE_ONLY"
    bad_jsonl.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in raw_lines) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(b1b_acquire, "ACQUIRED_JSONL_PATH", bad_jsonl)
    with pytest.raises(ValueError, match="must be OPEN_REUSABLE"):
        b1b_verify.verify_b1b_artifacts()

    for rel_path, expected_sha in b1b_acquire.UPSTREAM_ARTIFACT_LF_HASHES.items():
        actual_sha = w07_a2.compute_file_sha256(REPO_ROOT / rel_path)
        assert actual_sha == expected_sha, f"Upstream artifact modified: {rel_path}"


def test_13_fc001_and_fc002_conflicted_addresses_excluded_from_acquired_jsonl():
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    all_raw = "\n".join(d["raw_text"] for d in docs)
    assert "1 Đường Trực Nguyên, Huyện Thường Tín, 13618, VN" not in all_raw
    assert "1 Đường Trực Nguyên" not in all_raw
    assert "Huyện Thường Tín" not in all_raw
    assert "439 P. Lê Lợi, Hạ Long, 180000, VN" not in all_raw
    assert "439 P. Lê Lợi" not in all_raw

    fc001_docs = [
        d
        for d in docs
        if d["poi_id"] == "f0d424bd-f722-540f-8964-5e6fd8875b56" and d["source_type"] == "overture_places_parquet"
    ]
    assert len(fc001_docs) == 1
    assert "address" in fc001_docs[0]["suppressed_conflicted_fields"]
    assert "Địa chỉ cấu trúc (Overture addresses):" not in fc001_docs[0]["raw_text"]
    assert "http://www.vme.org.vn/" in fc001_docs[0]["raw_text"]

    fc002_docs = [
        d
        for d in docs
        if d["poi_id"] == "75a3fbd1-a24e-43c6-820a-72f95ebc05c0" and d["source_type"] == "overture_places_parquet"
    ]
    assert len(fc002_docs) == 1
    assert "address" in fc002_docs[0]["suppressed_conflicted_fields"]
    assert "Địa chỉ cấu trúc (Overture addresses):" not in fc002_docs[0]["raw_text"]
    assert "vinpearl.com" in fc002_docs[0]["raw_text"]
    assert b1b_acquire.UNVERIFIED_FACT_LABEL in fc002_docs[0]["raw_text"]
    assert "vinpearl.com" not in fc002_docs[0]["answer_ready_confirmed_text"]


def test_14_negative_verifier_rejects_conflicted_field_rendered_in_raw_text():
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    fc001_doc = next(
        copy.deepcopy(d)
        for d in docs
        if d["poi_id"] == "f0d424bd-f722-540f-8964-5e6fd8875b56" and d["source_type"] == "overture_places_parquet"
    )
    fc001_doc["raw_text"] += "\nĐịa chỉ cấu trúc (Overture addresses): 1 Đường Trực Nguyên, Huyện Thường Tín, 13618, VN"
    with pytest.raises(ValueError, match="CONFLICTED|suppressed conflicted field"):
        b1b_verify.validate_document_content_utility(fc001_doc)


def test_15_negative_verifier_rejects_overture_record_with_all_substantive_fields_suppressed():
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ov_doc = next(copy.deepcopy(d) for d in docs if d["source_type"] == "overture_places_parquet")
    kept_lines = [
        line
        for line in ov_doc["raw_text"].splitlines()
        if not line.startswith("Địa chỉ cấu trúc (Overture addresses):")
        and not line.startswith("Số điện thoại liên hệ (Overture phones):")
        and not line.startswith("Liên kết website/trang thông tin (Overture websites):")
    ]
    ov_doc["raw_text"] = "\n".join(kept_lines)
    ov_doc["retained_substantive_fields"] = []
    ov_doc["unverified_fields"] = []
    ov_doc["content_utility_status"] = "USEFUL_STRUCTURED_FACTS"
    with pytest.raises(
        ValueError,
        match="all substantive place attributes suppressed/missing and must be downgraded to LOW_INFORMATION",
    ):
        b1b_verify.validate_document_content_utility(ov_doc)


def test_16_negative_verifier_rejects_unchecked_field_labeled_corroborated():
    decisions = json.loads(b1b_acquire.DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    summary = json.loads(b1b_acquire.SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tampered_decisions = copy.deepcopy(decisions)
    rec0 = tampered_decisions["overture_fact_consistency_audit"]["records"][0]
    rec0["field_audit"]["phone"]["status"] = "CORROBORATED"
    rec0["field_audit"]["phone"]["corroboration_sources"] = []
    with pytest.raises(
        ValueError,
        match="UNVERIFIED_PROMOTED_TO_CORROBORATED|CORROBORATED field must have >=1 corroboration_sources",
    ):
        b1b_verify.validate_overture_fact_consistency_audit(tampered_decisions, summary, docs)


def test_17_negative_temporal_provenance_rejects_conflated_or_fabricated_timestamps():
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wp_doc = next(copy.deepcopy(d) for d in docs if d["source_type"] == "wikipedia_article")
    ov_doc = next(copy.deepcopy(d) for d in docs if d["source_type"] == "overture_places_parquet")

    # 1. retrieved_at == source_published_or_updated_at
    bad_wp_retrieved = copy.deepcopy(wp_doc)
    bad_wp_retrieved["retrieved_at"] = bad_wp_retrieved["source_published_or_updated_at"]
    with pytest.raises(ValueError, match="retrieved_at .* must not equal source_published_or_updated_at"):
        b1b_verify.validate_temporal_provenance(bad_wp_retrieved, is_document=True)

    # 2. source_terms_checked_at == source_published_or_updated_at
    bad_wp_terms = copy.deepcopy(wp_doc)
    bad_wp_terms["source_terms_checked_at"] = bad_wp_terms["source_published_or_updated_at"]
    with pytest.raises(ValueError, match="source_terms_checked_at .* must not equal source_published_or_updated_at"):
        b1b_verify.validate_temporal_provenance(bad_wp_terms, is_document=True)

    # 3. retrieved_at == artifact_snapshot_timestamp (conflated snapshot timestamp)
    bad_wp_snapshot = copy.deepcopy(wp_doc)
    bad_wp_snapshot["retrieved_at"] = bad_wp_snapshot["artifact_snapshot_timestamp"]
    with pytest.raises(ValueError, match="retrieved_at .* must not equal artifact_snapshot_timestamp"):
        b1b_verify.validate_temporal_provenance(bad_wp_snapshot, is_document=True)

    # 4. Overture record fabricates an ISO retrieved_at when historical download time was not recorded
    bad_ov_fabricated = copy.deepcopy(ov_doc)
    bad_ov_fabricated["retrieved_at"] = "2026-10-01T12:00:00Z"
    with pytest.raises(ValueError, match="UNKNOWN_HISTORICAL_RETRIEVAL_TIME"):
        b1b_verify.validate_temporal_provenance(bad_ov_fabricated, is_document=True)

    # 5. Wikimedia historical record fabricates an ISO retrieved_at without separate HTTP receipt
    bad_wp_fabricated = copy.deepcopy(wp_doc)
    bad_wp_fabricated["retrieved_at"] = "2026-11-03T18:10:00Z"
    with pytest.raises(ValueError, match="UNKNOWN_HISTORICAL_RETRIEVAL_TIME"):
        b1b_verify.validate_temporal_provenance(bad_wp_fabricated, is_document=True)


def test_18_every_osm_reference_matches_canonical_poi_osm_id():
    target_manifest = json.loads(b1b_acquire.TARGET_60_PATH.read_text(encoding="utf-8"))
    canonical_osm_by_poi = {p["poi_id"]: p["osm_id"] for p in target_manifest["pois"]}
    decisions = json.loads(b1b_acquire.DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # Verify full provenance binding passes
    b1b_verify.validate_source_reference_binding(decisions, docs)

    audit_records = decisions["overture_fact_consistency_audit"]["records"]
    assert len(audit_records) == 26
    osm_refs_checked = 0
    for rec in audit_records:
        pid = rec["poi_id"]
        expected_osm = f"osm:{canonical_osm_by_poi[pid]}"
        for fname, finfo in rec["field_audit"].items():
            for ref in finfo["corroboration_sources"] + finfo["conflicting_sources"]:
                if ref.startswith("osm:"):
                    assert ref == expected_osm, f"Mismatched OSM reference on {pid}.{fname}: {ref} != {expected_osm}"
                    osm_refs_checked += 1
    assert osm_refs_checked > 0


def test_19_negative_verifier_rejects_mismatched_osm_id_without_crosswalk():
    decisions = json.loads(b1b_acquire.DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tampered_decisions = copy.deepcopy(decisions)
    rec0 = tampered_decisions["overture_fact_consistency_audit"]["records"][0]
    rec0["field_audit"]["coordinates"]["corroboration_sources"] = [
        f"canonical_poi:{rec0['poi_id']}",
        "osm:node/3929648836",
    ]
    with pytest.raises(ValueError, match="OSM_SOURCE_REFERENCE_MISMATCH"):
        b1b_verify.validate_source_reference_binding(tampered_decisions, docs)


def test_20_negative_verifier_rejects_unverified_arbitrary_source_string():
    decisions = json.loads(b1b_acquire.DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tampered_decisions = copy.deepcopy(decisions)
    rec0 = tampered_decisions["overture_fact_consistency_audit"]["records"][0]
    rec0["field_audit"]["website"]["status"] = "CORROBORATED"
    rec0["field_audit"]["website"]["corroboration_sources"] = ["official_resort_site:https://vinpearl.com"]
    with pytest.raises(ValueError, match="UNVERIFIED_OR_ARBITRARY_SOURCE_REFERENCE"):
        b1b_verify.validate_source_reference_binding(tampered_decisions, docs)


def test_21_unverified_contact_address_website_explicitly_qualified_and_excluded_from_confirmed_text():
    docs = [
        json.loads(line)
        for line in b1b_acquire.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ov_docs = [d for d in docs if d["source_type"] == "overture_places_parquet"]
    assert len(ov_docs) == 23

    unverified_count = 0
    for d in ov_docs:
        raw_lines = d["raw_text"].splitlines()
        confirmed_lines = d["answer_ready_confirmed_text"].splitlines()
        for fname in ("address", "phone", "website"):
            finfo = d["fact_consistency_audit"][fname]
            prefix = b1b_verify.OVERTURE_FIELD_LINE_PREFIXES[fname]
            matching_raw = [ln for ln in raw_lines if ln.startswith(prefix)]
            matching_confirmed = [ln for ln in confirmed_lines if ln.startswith(prefix)]
            if finfo["status"] == "UNVERIFIED":
                unverified_count += 1
                assert fname in d["unverified_fields"]
                assert fname not in d["corroborated_fields"]
                assert d["source_reported_unverified_values"][fname]["present_as_confirmed_fact"] is False
                assert len(matching_raw) == 1
                assert b1b_acquire.UNVERIFIED_FACT_LABEL in matching_raw[0]
                assert "[CORROBORATED:" not in matching_raw[0]
                assert len(matching_confirmed) == 0
            elif finfo["status"] == "CORROBORATED":
                assert fname in d["corroborated_fields"]
                assert fname not in d["unverified_fields"]
                assert len(matching_raw) == 1
                assert "[CORROBORATED:" in matching_raw[0]
                assert b1b_acquire.UNVERIFIED_FACT_LABEL not in matching_raw[0]
                assert len(matching_confirmed) == 1
    assert unverified_count > 0

    # Negative test: stripping UNVERIFIED_FACT_LABEL from an UNVERIFIED phone/address/website line fails closed
    doc_with_unverified = next(copy.deepcopy(d) for d in ov_docs if d["unverified_fields"])
    doc_with_unverified["raw_text"] = doc_with_unverified["raw_text"].replace(
        f" {b1b_acquire.UNVERIFIED_FACT_LABEL}", ""
    )
    with pytest.raises(ValueError, match="UNQUALIFIED_UNVERIFIED_FACT_IN_RAW_TEXT"):
        b1b_verify.validate_document_content_utility(doc_with_unverified)


def test_22_markdown_report_consistency_with_json_and_manifest():
    target_manifest = json.loads(b1b_acquire.TARGET_60_PATH.read_text(encoding="utf-8"))
    decisions = json.loads(b1b_acquire.DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    summary = json.loads(b1b_acquire.SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    report_md = b1b_acquire.REPORT_MD_PATH.read_text(encoding="utf-8")

    b1b_verify.validate_markdown_report_consistency(
        report_md,
        target_manifest,
        decisions,
        summary,
        decisions_lf_sha256=b1b_verify.w07_a2.compute_file_sha256(b1b_acquire.DECISIONS_JSON_PATH),
        acquired_jsonl_lf_sha256=b1b_verify.w07_a2.compute_file_sha256(b1b_acquire.ACQUIRED_JSONL_PATH),
        summary_lf_sha256=b1b_verify.w07_a2.compute_file_sha256(b1b_acquire.SUMMARY_JSON_PATH),
    )

    # DRIFT-01: Vincom Plaza (7ff87c59-62f1-4509-95f4-e83796b9a35c) must be Đà Nẵng, never Hạ Long
    assert (
        "`7ff87c59-62f1-4509-95f4-e83796b9a35c` (`Vincom Plaza`, Đà Nẵng)" in report_md
    )
    assert (
        "`7ff87c59-62f1-4509-95f4-e83796b9a35c` (`Vincom Plaza`, Hạ Long)" not in report_md
    )

    # DRIFT-02: Priority Distribution Shift post-B1B city splits
    assert (
        "| `P1` | `1` RAG-eligible lineage (`SINGLE_ELIGIBLE_LINEAGE_ONLY`) | `19` | **`9`** (`2` Hà Nội, `3` Đà Nẵng, `4` Hạ Long) |"
        in report_md
    )
    assert (
        "| `P2` | `>=2` RAG-eligible lineages, structured only (`STRUCTURED_ONLY_NO_NARRATIVE`) | `21` | **`13`** (`2` Hà Nội, `4` Đà Nẵng, `7` Hạ Long) |"
        in report_md
    )

    # DRIFT-03: Coverage by City table rows for Đà Nẵng and Hạ Long
    assert (
        "| **Đà Nẵng** | `20` | **`19 / 20` (`95.0%`)** | `16 / 20` (`80.0%`) | `12 / 20` (`60.0%`) | `19 / 20` (`95.0%`) | `12 / 20` (`60.0%`) | `1 / 3 / 4 / 12` |"
        in report_md
    )
    assert (
        "| **Hạ Long** | `20` | **`14 / 20` (`70.0%`)** | `10 / 20` (`50.0%`) | `6 / 20` (`30.0%`) | `11 / 20` (`55.0%`) | `3 / 20` (`15.0%`) | `6 / 4 / 7 / 3` |"
        in report_md
    )

    # Deterministic generator output matches committed Markdown report byte-for-byte
    rendered_md = b1b_acquire.render_b1b_report_markdown(
        target_manifest=target_manifest,
        decisions_saved=decisions,
        summary_saved=summary,
        decisions_lf_sha256=b1b_verify.w07_a2.compute_file_sha256(b1b_acquire.DECISIONS_JSON_PATH),
        acquired_jsonl_lf_sha256=b1b_verify.w07_a2.compute_file_sha256(b1b_acquire.ACQUIRED_JSONL_PATH),
        summary_lf_sha256=b1b_verify.w07_a2.compute_file_sha256(b1b_acquire.SUMMARY_JSON_PATH),
    )
    assert rendered_md == report_md


def test_23_negative_report_verifier_rejects_wrong_poi_city_and_statistical_drifts(
    monkeypatch, tmp_path
):
    target_manifest = json.loads(b1b_acquire.TARGET_60_PATH.read_text(encoding="utf-8"))
    decisions = json.loads(b1b_acquire.DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    summary = json.loads(b1b_acquire.SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    report_md = b1b_acquire.REPORT_MD_PATH.read_text(encoding="utf-8")
    decisions_sha = b1b_verify.w07_a2.compute_file_sha256(b1b_acquire.DECISIONS_JSON_PATH)
    acquired_sha = b1b_verify.w07_a2.compute_file_sha256(b1b_acquire.ACQUIRED_JSONL_PATH)
    summary_sha = b1b_verify.w07_a2.compute_file_sha256(b1b_acquire.SUMMARY_JSON_PATH)

    # 1. Negative test: Report POI has the wrong city (DRIFT-01 in Type-3 bullet or Overture table)
    drift_01_bullet = report_md.replace(
        "`7ff87c59-62f1-4509-95f4-e83796b9a35c` (`Vincom Plaza`, Đà Nẵng)",
        "`7ff87c59-62f1-4509-95f4-e83796b9a35c` (`Vincom Plaza`, Hạ Long)",
    )
    assert drift_01_bullet != report_md
    with pytest.raises(ValueError, match="REPORT_POI_CITY_MISMATCH"):
        b1b_verify.validate_markdown_report_consistency(
            drift_01_bullet,
            target_manifest,
            decisions,
            summary,
            decisions_lf_sha256=decisions_sha,
            acquired_jsonl_lf_sha256=acquired_sha,
            summary_lf_sha256=summary_sha,
        )

    drift_01_table = report_md.replace(
        "`7ff87c59` (Vincom Plaza, Đà Nẵng)",
        "`7ff87c59` (Vincom Plaza, Hạ Long)",
    )
    assert drift_01_table != report_md
    with pytest.raises(ValueError, match="REPORT_POI_CITY_MISMATCH"):
        b1b_verify.validate_markdown_report_consistency(
            drift_01_table,
            target_manifest,
            decisions,
            summary,
            decisions_lf_sha256=decisions_sha,
            acquired_jsonl_lf_sha256=acquired_sha,
            summary_lf_sha256=summary_sha,
        )

    # 2. Negative test: City-level P0/P1/P2/P3 totals in the report disagree with JSON (DRIFT-02 / DRIFT-03)
    drift_02_priority_shift = report_md.replace(
        "**`9`** (`2` Hà Nội, `3` Đà Nẵng, `4` Hạ Long)",
        "**`9`** (`2` Hà Nội, `4` Đà Nẵng, `3` Hạ Long)",
    )
    assert drift_02_priority_shift != report_md
    with pytest.raises(ValueError, match="REPORT_CITY_PRIORITY_TOTALS_MISMATCH"):
        b1b_verify.validate_markdown_report_consistency(
            drift_02_priority_shift,
            target_manifest,
            decisions,
            summary,
            decisions_lf_sha256=decisions_sha,
            acquired_jsonl_lf_sha256=acquired_sha,
            summary_lf_sha256=summary_sha,
        )

    drift_02_city_table_priority = report_md.replace(
        "| **Đà Nẵng** | `20` | **`19 / 20` (`95.0%`)** | `16 / 20` (`80.0%`) | `12 / 20` (`60.0%`) | `19 / 20` (`95.0%`) | `12 / 20` (`60.0%`) | `1 / 3 / 4 / 12` |",
        "| **Đà Nẵng** | `20` | **`19 / 20` (`95.0%`)** | `16 / 20` (`80.0%`) | `12 / 20` (`60.0%`) | `19 / 20` (`95.0%`) | `12 / 20` (`60.0%`) | `1 / 4 / 3 / 12` |",
    )
    assert drift_02_city_table_priority != report_md
    with pytest.raises(ValueError, match="REPORT_CITY_PRIORITY_TOTALS_MISMATCH"):
        b1b_verify.validate_markdown_report_consistency(
            drift_02_city_table_priority,
            target_manifest,
            decisions,
            summary,
            decisions_lf_sha256=decisions_sha,
            acquired_jsonl_lf_sha256=acquired_sha,
            summary_lf_sha256=summary_sha,
        )

    # 3. Negative test: Eligible-lineage coverage values disagree with JSON (DRIFT-03)
    drift_03_eligible_lineage = report_md.replace(
        "| **Đà Nẵng** | `20` | **`19 / 20` (`95.0%`)** | `16 / 20` (`80.0%`) | `12 / 20` (`60.0%`) | `19 / 20` (`95.0%`) | `12 / 20` (`60.0%`) | `1 / 3 / 4 / 12` |",
        "| **Đà Nẵng** | `20` | **`19 / 20` (`95.0%`)** | `15 / 20` (`75.0%`) | `12 / 20` (`60.0%`) | `19 / 20` (`95.0%`) | `12 / 20` (`60.0%`) | `1 / 3 / 4 / 12` |",
    )
    assert drift_03_eligible_lineage != report_md
    with pytest.raises(ValueError, match="REPORT_ELIGIBLE_LINEAGE_COVERAGE_MISMATCH"):
        b1b_verify.validate_markdown_report_consistency(
            drift_03_eligible_lineage,
            target_manifest,
            decisions,
            summary,
            decisions_lf_sha256=decisions_sha,
            acquired_jsonl_lf_sha256=acquired_sha,
            summary_lf_sha256=summary_sha,
        )

    # 4. Negative test: Report generation / committed Markdown reintroduces drift relative to generator or via verify_b1b_artifacts
    drift_04_generator = report_md + "\n<!-- drifted -->\n"
    with pytest.raises(ValueError, match="REPORT_GENERATOR_DRIFT_DETECTED"):
        b1b_verify.validate_markdown_report_consistency(
            drift_04_generator,
            target_manifest,
            decisions,
            summary,
            decisions_lf_sha256=decisions_sha,
            acquired_jsonl_lf_sha256=acquired_sha,
            summary_lf_sha256=summary_sha,
        )

    drifted_md_path = tmp_path / "drifted_report.md"
    drifted_md_path.write_text(drift_01_bullet, encoding="utf-8")
    monkeypatch.setattr(b1b_verify.b1b, "REPORT_MD_PATH", drifted_md_path)
    with pytest.raises(ValueError, match="REPORT_POI_CITY_MISMATCH"):
        b1b_verify.verify_b1b_artifacts()

