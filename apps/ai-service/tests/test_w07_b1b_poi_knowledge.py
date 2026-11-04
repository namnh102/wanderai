"""W07-B1B tests: Targeted POI knowledge acquisition, Corrective 01 & Corrective 02 fact consistency and temporal provenance."""

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
        "retrieved_at": "2026-11-03T18:45:00Z",
        "source_published_or_updated_at": "2026-10-01T00:00:00Z",
        "license_or_usage_class": "CC-BY-SA-4.0",
        "reuse_storage_class": "OPEN_REUSABLE",
        "reuse_evidence": "CC-BY-SA-4.0",
        "attribution_requirement": "Wikipedia contributors",
        "redistributable_in_git": True,
        "source_terms_checked_at": "2026-11-03T18:45:00Z",
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
    # Strip all substantive place attributes (address, phone, website), leaving only header/category/status/confidence/sources
    kept_lines = [
        line
        for line in ov_doc["raw_text"].splitlines()
        if not line.startswith("Địa chỉ cấu trúc (Overture addresses):")
        and not line.startswith("Số điện thoại liên hệ (Overture phones):")
        and not line.startswith("Liên kết website/trang thông tin (Overture websites):")
    ]
    ov_doc["raw_text"] = "\n".join(kept_lines)
    ov_doc["retained_substantive_fields"] = []
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
    # Mark an unchecked phone field as CORROBORATED with empty corroboration_sources
    rec0 = tampered_decisions["overture_fact_consistency_audit"]["records"][0]
    rec0["field_audit"]["phone"]["status"] = "CORROBORATED"
    rec0["field_audit"]["phone"]["corroboration_sources"] = []
    with pytest.raises(ValueError, match="CORROBORATED field must have >=1 corroboration_sources"):
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

    # 3. Overture record fabricates an ISO retrieved_at when historical download time was not recorded
    bad_ov_fabricated = copy.deepcopy(ov_doc)
    bad_ov_fabricated["retrieved_at"] = "2026-10-01T12:00:00Z"
    with pytest.raises(ValueError, match="UNKNOWN_HISTORICAL_RETRIEVAL_TIME"):
        b1b_verify.validate_temporal_provenance(bad_ov_fabricated, is_document=True)
