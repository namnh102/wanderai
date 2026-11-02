from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import (  # noqa: E402
    acquire_w07_public_reviews_v1 as w07_a4p,
    import_w07_contributor_reviews_v1 as w07_a3_import,
    validate_w07_review_corpus_v1 as w07_a2,
)


def test_w07_a4p_committed_artifacts_and_upstream_immutability_pass() -> None:
    res = w07_a4p.verify_public_acquisition_artifacts(REPO_ROOT)
    assert res["status"] == "PASS"
    assert (
        res["outcome_classification"]
        == "OUTCOME_C_ZERO_SUITABLE_PUBLIC_REVIEWS_FOUND"
    )
    assert res["PUBLIC_REVIEWS_DISCOVERED"] == 300536
    assert res["PUBLIC_UNIQUE_REVIEWS"] == 186170
    assert res["PUBLIC_REVIEWS_ACCEPTED"] == 0
    assert res["PUBLIC_REVIEWS_REJECTED"] == 124898
    assert res["PUBLIC_REVIEWS_QUARANTINED"] == 61272
    assert res["PUBLIC_POIS_COVERED"] == 0
    assert res["CORPUS_SCIENTIFIC_MINIMUM_READY"] is False

    upstream = res["upstream_immutability"]
    assert (
        upstream["w07_a2_manifest_internal_sha256"]
        == "b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b"
    )
    assert (
        upstream["w07_a3_form_definition_internal_sha256"]
        == "9c17cfc51c41295c8338b40544324454a36a7276bb2339edd3a0b59c88c6de8a"
    )
    assert (
        upstream["w07_a3_apps_script_lf_sha256"]
        == "5e87dcf74d2bc4840792701bbd852c75781ef6ba938ac8c1eacad6d2a430be71"
    )
    assert (
        upstream["w07_a4h_template_lf_sha256"]
        == "747da9d0b0033ae5ca7649bf456fde59f79f895f1248985ab1f521b43ca42bd9"
    )
    assert (
        upstream["w07_a4h_progress_internal_sha256"]
        == "b34e32af7aba9b5ee95d13f30781fbef3e15a4cb9b6a26c7b97fa1489f13ecdb"
    )
    assert (
        upstream["w07_a4h_progress_lf_sha256"]
        == "79095ce10fbf50a838d9e1a607001d821413ced6e8d6e7ad5ac2fd6e7c6239d1"
    )
    assert (
        upstream["w07_a4h_guide_lf_sha256"]
        == "4e8e133c877ec748fd7bdc66b2f3b50ab72c46686018899b1758779d18409814"
    )


def test_w07_a4p_source_manifests_completeness_and_math_invariants() -> None:
    report = json.loads(
        (REPO_ROOT / w07_a4p.PUBLIC_ACQUISITION_JSON_RELPATH).read_text(
            encoding="utf-8"
        )
    )
    assert report["investigated_sources_count"] == 18
    sources = report["investigated_sources"]
    assert len(sources) == 18

    required_keys = {
        "source_id",
        "source_name",
        "source_url",
        "doi",
        "access_date",
        "discovered_in_stage",
        "license",
        "upstream_origin",
        "research_reuse_assessment",
        "download_or_crawl_mechanism",
        "classification",
        "quarantine_status",
        "original_rows",
        "unique_reviews",
        "accepted",
        "rejected",
        "quarantined",
        "target_pois_covered",
        "mapping_breakdown",
        "audit_notes",
    }

    for src in sources:
        assert required_keys.issubset(src.keys())
        assert src["classification"] in w07_a4p.SOURCE_CLASSIFICATIONS
        assert (
            src["accepted"] + src["rejected"] + src["quarantined"]
            == src["unique_reviews"]
        )
        mb = src["mapping_breakdown"]
        assert sum(mb.values()) == src["unique_reviews"]
        if src["quarantine_status"] == "QUARANTINE_REUSE_UNCLEAR":
            assert src["accepted"] == 0

    assert (
        report["PUBLIC_REVIEWS_ACCEPTED"]
        + report["PUBLIC_REVIEWS_REJECTED"]
        + report["PUBLIC_REVIEWS_QUARANTINED"]
        == report["PUBLIC_UNIQUE_REVIEWS"]
    )
    assert len(report["REVIEWS_PER_POI"]) == 60
    assert report["BULK_SCRAPING_EXECUTED"] is False
    assert report["LLM_GENERATED_PUBLIC_REVIEWS"] == 0
    assert report["NEW_LLM_PROVIDER_CALLS"] == 0


def test_w07_a4p_mapping_hierarchy_allows_exact_geo_manual_and_rejects_name_only() -> None:
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    poi0 = manifest["pois"][0]  # Lăng Chủ tịch Hồ Chí Minh

    # 1. EXACT_UPSTREAM_ID
    res_exact = w07_a4p.map_public_record_to_frozen_poi(
        {
            "upstream_place_id": poi0["source_ids"][0],
            "place_name": "Different Alias",
        },
        manifest_payload=manifest,
    )
    assert res_exact["accepted_mapping"] is True
    assert res_exact["mapping_method"] == "EXACT_UPSTREAM_ID"
    assert res_exact["poi_id"] == poi0["poi_id"]
    assert res_exact["mapping_confidence"] == 1.0

    # 2. GEO_NAME_HIGH_CONFIDENCE (within 150m + high name similarity + matching city)
    res_geo = w07_a4p.map_public_record_to_frozen_poi(
        {
            "place_name": poi0["name"],
            "latitude": float(poi0["latitude"]) + 0.0002,
            "longitude": float(poi0["longitude"]) + 0.0002,
            "city": poi0["city"],
        },
        manifest_payload=manifest,
    )
    assert res_geo["accepted_mapping"] is True
    assert res_geo["mapping_method"] == "GEO_NAME_HIGH_CONFIDENCE"
    assert res_geo["poi_id"] == poi0["poi_id"]
    assert res_geo["mapping_confidence"] >= 0.80

    # 3. MANUAL_VERIFIED lookup table
    res_manual = w07_a4p.map_public_record_to_frozen_poi(
        {
            "source": "academic_benchmark_v1",
            "source_place_id": "bench_place_001",
        },
        manifest_payload=manifest,
        manual_verified_lookup={
            ("academic_benchmark_v1", "bench_place_001"): poi0["poi_id"]
        },
    )
    assert res_manual["accepted_mapping"] is True
    assert res_manual["mapping_method"] == "MANUAL_VERIFIED"
    assert res_manual["poi_id"] == poi0["poi_id"]

    # 4. NAME_ONLY_AUTOMATIC (matching name without coordinates or upstream ID -> REJECTED)
    res_name_only = w07_a4p.map_public_record_to_frozen_poi(
        {
            "place_name": poi0["name"],
            "latitude": None,
            "longitude": None,
        },
        manifest_payload=manifest,
    )
    assert res_name_only["accepted_mapping"] is False
    assert res_name_only["mapping_method"] == "NAME_ONLY_AUTOMATIC"
    assert res_name_only["poi_id"] is None

    # 5. UNMAPPABLE (no place metadata or distant coordinates)
    res_unmappable = w07_a4p.map_public_record_to_frozen_poi(
        {
            "place_name": "Khách sạn Phú Quốc Resort",
            "latitude": 10.21,
            "longitude": 103.96,
        },
        manifest_payload=manifest,
    )
    assert res_unmappable["accepted_mapping"] is False
    assert res_unmappable["mapping_method"] == "UNMAPPABLE"
    assert res_unmappable["poi_id"] is None


def test_w07_a4p_multi_image_dedup_and_candidate_filtering_rules() -> None:
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    poi0 = manifest["pois"][0]

    raw_rows = [
        # Two photo rows for the same review_id -> collapsed to 1 unique review
        {
            "source": "open_tourism_cc_by",
            "source_classification": "APPROVED_PUBLIC_SOURCE",
            "license_or_usage_class": "CC-BY-4.0",
            "source_review_id": "rev_1001",
            "upstream_place_id": poi0["source_ids"][0],
            "review_text": "Khuôn viên Lăng Bác rất trang nghiêm, sạch đẹp và hàng cây xanh mát.",
            "rating": None,
            "language": None,
            "created_at": None,
        },
        {
            "source": "open_tourism_cc_by",
            "source_classification": "APPROVED_PUBLIC_SOURCE",
            "license_or_usage_class": "CC-BY-4.0",
            "source_review_id": "rev_1001",
            "upstream_place_id": poi0["source_ids"][0],
            "review_text": "Khuôn viên Lăng Bác rất trang nghiêm, sạch đẹp và hàng cây xanh mát.",
            "rating": None,
            "language": None,
            "created_at": None,
        },
        # Duplicate text with a different source_review_id -> rejected by normalized text dedup
        {
            "source": "open_tourism_cc_by",
            "source_classification": "APPROVED_PUBLIC_SOURCE",
            "license_or_usage_class": "CC-BY-4.0",
            "source_review_id": "rev_1002",
            "upstream_place_id": poi0["source_ids"][0],
            "review_text": "  Khuôn viên Lăng Bác rất trang nghiêm, sạch đẹp và hàng cây xanh mát.  ",
        },
        # Ambiguous license -> QUARANTINE_REUSE_UNCLEAR (never accepted)
        {
            "source": "unlicensed_repo",
            "source_classification": "AUXILIARY_ONLY",
            "license_or_usage_class": "UNSPECIFIED_ON_HF_CARD",
            "source_review_id": "rev_2001",
            "upstream_place_id": poi0["source_ids"][0],
            "review_text": "Trải nghiệm tham quan quảng trường Ba Đình vào buổi sáng sớm rất tuyệt vời.",
        },
        # Name-only automatic mapping -> rejected
        {
            "source": "open_tourism_cc_by",
            "source_classification": "APPROVED_PUBLIC_SOURCE",
            "license_or_usage_class": "CC-BY-4.0",
            "source_review_id": "rev_3001",
            "place_name": poi0["name"],
            "review_text": "Đi bộ quanh khu di tích rất thú vị và nhiều thông tin lịch sử bổ ích.",
        },
        # Synthetic/LLM row -> rejected
        {
            "source": "open_tourism_cc_by",
            "source_classification": "APPROVED_PUBLIC_SOURCE",
            "license_or_usage_class": "CC-BY-4.0",
            "source_review_id": "rev_4001",
            "upstream_place_id": poi0["source_ids"][0],
            "is_llm_rewritten": True,
            "review_text": "Đoạn đánh giá được viết lại bằng mô hình ngôn ngữ lớn cho địa điểm này.",
        },
    ]

    result = w07_a4p.evaluate_and_filter_public_candidates(
        raw_rows,
        manifest_payload=manifest,
    )

    assert result["raw_rows_input"] == 6
    assert result["collapsed_multi_image_or_same_id_rows"] == 1
    assert result["unique_reviews_evaluated"] == 5
    assert len(result["accepted_candidates"]) == 1
    assert len(result["quarantined_rows"]) == 1
    assert (
        result["quarantined_rows"][0]["quarantine_reason"]
        == "QUARANTINE_REUSE_UNCLEAR"
    )
    assert len(result["rejected_rows"]) == 3

    accepted = result["accepted_candidates"][0]
    assert set(accepted.keys()) == set(w07_a4p.PRIMARY_CANDIDATE_SCHEMA_FIELDS)
    assert accepted["poi_id"] == poi0["poi_id"]
    assert accepted["mapping_method"] == "EXACT_UPSTREAM_ID"
    assert accepted["provenance"] == "PUBLIC_OPEN_LICENSED_DATASET_V1"
    assert (
        accepted["provenance"]
        not in w07_a4p.FORBIDDEN_FIRST_PARTY_PROVENANCE_CLASSES
    )
    assert "consent_record_id" not in accepted
    # Verify missing upstream values are preserved as None rather than fabricated
    assert accepted["rating"] is None
    assert accepted["rating_scale_max"] is None
    assert accepted["language"] is None
    assert accepted["created_at"] is None


def test_w07_a4p_forbids_first_party_provenance_on_public_reviews() -> None:
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    poi0 = manifest["pois"][0]

    for forbidden_prov in w07_a4p.FORBIDDEN_FIRST_PARTY_PROVENANCE_CLASSES:
        with pytest.raises(
            ValueError, match="Public review cannot use first-party provenance class"
        ):
            w07_a4p.evaluate_and_filter_public_candidates(
                [
                    {
                        "source": "open_tourism_cc_by",
                        "source_classification": "APPROVED_PUBLIC_SOURCE",
                        "license_or_usage_class": "CC-BY-4.0",
                        "source_review_id": "rev_prov_test",
                        "upstream_place_id": poi0["source_ids"][0],
                        "provenance": forbidden_prov,
                        "review_text": "Khu di tích lịch sử rất trang nghiêm và đáng tham quan tại Hà Nội.",
                    }
                ],
                manifest_payload=manifest,
            )


def test_w07_a4p_markdown_and_json_deterministic_hashes_match() -> None:
    expected_report = w07_a4p.build_public_acquisition_report(REPO_ROOT)
    on_disk_json = json.loads(
        (REPO_ROOT / w07_a4p.PUBLIC_ACQUISITION_JSON_RELPATH).read_text(
            encoding="utf-8"
        )
    )
    assert (
        w07_a2.compute_internal_sha256(on_disk_json)
        == expected_report["artifact_sha256"]
    )

    expected_md = w07_a4p.render_public_acquisition_markdown(expected_report)
    actual_md = (
        (REPO_ROOT / w07_a4p.PUBLIC_ACQUISITION_MD_RELPATH)
        .read_text(encoding="utf-8")
        .replace("\r\n", "\n")
    )
    assert actual_md == expected_md
