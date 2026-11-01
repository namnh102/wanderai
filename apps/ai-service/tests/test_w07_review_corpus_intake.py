"""Offline deterministic tests for W07-A2 Canonical 60-POI Intake & Review Validator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import (
    run_w07_data_rag_readiness_audit as w07_0_audit,
    run_w07_review_corpus_feasibility as w07_a1,
    validate_w07_review_corpus_v1 as w07_a2,
    verify_w06_scientific_closure as w06_closure,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _make_valid_review(
    review_id: str = "w07_rev_0001",
    poi_id: str = "698ee756-6062-5f47-955b-bdf458682e57",
    city: str = "Hà Nội",
    text: str = "Khu vực quảng trường Ba Đình và Lăng Bác rất trang nghiêm, sạch sẽ và an ninh tốt.",
    rating: float = 5.0,
    **overrides: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "review_id": review_id,
        "poi_id": poi_id,
        "upstream_place_id": "osm:way/37629144",
        "city": city,
        "source": "first_party_contributor_form_v1",
        "source_review_id": None,
        "rating": rating,
        "rating_scale_max": 5,
        "review_text": text,
        "language": "vi",
        "created_at": "2026-11-02",
        "collected_at": "2026-11-02T09:00:00Z",
        "source_ref": f"gomate_w07_contributor_intake_v1#{review_id}",
        "provenance": "FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1",
        "license_or_usage_class": "OWNER_FIRST_PARTY_CONSENT",
        "mapping_method": "EXACT_PREBOUND_CANONICAL_POI",
        "mapping_confidence": 1.0,
        "author_anonymous_id": "contrib_9f86d081884c",
        "visit_period": "2025-10",
        "consent_record_id": f"consent_{review_id}",
    }
    row.update(overrides)
    return row


def test_w07_a2_verifier_and_hashes_match() -> None:
    res = w07_a2.verify_w07_a2_artifacts(REPO_ROOT)
    assert res["status"] == "PASS"
    assert (
        res["manifest_internal_sha256"]
        == "1e7e59304c182cfe3f4a8518e18df2ab1dde3b9dee5850f081fc390f1d13cd8d"
    )
    assert (
        res["manifest_file_lf_sha256"]
        == "78b9b125f0b31c637f7a97b44cc2152f910bb28597f919e5a6f0a822bc942043"
    )
    assert (
        res["intake_status_internal_sha256"]
        == "9368e7e50ae3e82828f688c1903d196fadcb9cec91ee97d2ad3d597f08c5abca"
    )
    assert (
        res["intake_status_file_lf_sha256"]
        == "46756e8f9a068a187ff46518412a7672a0eab74357ce43e09db5cf54fa298da6"
    )
    assert (
        res["contributor_spec_md_lf_sha256"]
        == "414f5a1994a9502dcaf22e1cd4b886fcea821750819efd5f23179ee7bcd6f9ac"
    )
    assert res["CORPUS_SCIENTIFIC_MINIMUM_READY"] is False
    assert res["corpus_collection_status"] == "COLLECTION_IN_PROGRESS"


def test_w07_a2_manifest_60_pois_city_and_category_balance() -> None:
    manifest_path = REPO_ROOT / w07_a2.MANIFEST_60_JSON_RELPATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pois = manifest["pois"]
    assert len(pois) == 60
    assert len({p["poi_id"] for p in pois}) == 60
    assert manifest["summary_statistics"]["city_distribution"] == {
        "Hà Nội": 20,
        "Đà Nẵng": 20,
        "Hạ Long": 20,
    }
    assert manifest["summary_statistics"]["category_group_distribution"] == {
        "attractions_culture": 18,
        "restaurants_cafes_markets": 18,
        "hotels": 15,
        "nature_beach": 6,
        "other_tourism": 3,
    }
    for p in pois:
        for req_field in (
            "poi_id",
            "name",
            "city",
            "category",
            "latitude",
            "longitude",
            "osm_id",
            "overture_id",
            "source_ids",
            "target_review_count_min",
            "target_review_count_preferred",
            "collection_status",
        ):
            assert req_field in p
        assert p["target_review_count_min"] == 5
        assert p["target_review_count_preferred"] == 8
        assert p["osm_id"]


def test_w07_a2_validator_rejects_all_invalid_conditions() -> None:
    manifest = w07_a2.build_w07_target_60_pois_manifest(REPO_ROOT)
    rows = [
        _make_valid_review(review_id="valid_1"),
        # 1. Unknown canonical POI
        _make_valid_review(
            review_id="bad_poi",
            poi_id="00000000-0000-0000-0000-000000000000",
        ),
        # 2. City mismatch
        _make_valid_review(
            review_id="bad_city",
            city="Đà Nẵng",
            text="Đánh giá có nội dung riêng nhưng bị ghi sai tên thành phố của địa điểm.",
        ),
        # 3. Missing review text
        _make_valid_review(
            review_id="missing_text",
            text=None,  # type: ignore[arg-type]
        ),
        # 4. Empty/whitespace review
        _make_valid_review(
            review_id="ws_text",
            text="   \t\n  ",
        ),
        # 5. URL-only review
        _make_valid_review(
            review_id="url_only",
            text="https://example.com/review/123",
        ),
        # 6. Emoji-only review
        _make_valid_review(
            review_id="emoji_only",
            text="😍😍😍👍👍👍",
        ),
        # 7. Duplicate review_id
        _make_valid_review(
            review_id="valid_1",
            text="Một đánh giá hoàn toàn khác nhưng bị trùng mã review_id.",
        ),
        # 8. Exact duplicate text for same POI
        _make_valid_review(
            review_id="dup_same_poi",
            text="Khu vực quảng trường Ba Đình và Lăng Bác rất trang nghiêm, sạch sẽ và an ninh tốt.",
        ),
        # 9. Invalid rating
        _make_valid_review(
            review_id="bad_rating",
            rating=6.0,
            text="Đánh giá có điểm số vượt quá thang điểm 5 sao quy định.",
        ),
        # 10. Invalid rating scale
        _make_valid_review(
            review_id="bad_scale",
            rating_scale_max=100,
            text="Đánh giá dùng thang điểm 100 không hợp lệ trong hệ thống.",
        ),
        # 11. Missing provenance
        _make_valid_review(
            review_id="no_prov",
            provenance="",
            text="Đánh giá bị thiếu thông tin nguồn gốc provenance rõ ràng.",
        ),
        # 12. Missing/unapproved license class
        _make_valid_review(
            review_id="bad_license",
            license_or_usage_class="SCRAPED_UNKNOWN_WEB",
            text="Đánh giá thu thập từ nguồn không rõ giấy phép nghiên cứu.",
        ),
        # 13. Synthetic / LLM / auxiliary dataset source forbidden
        _make_valid_review(
            review_id="llm_synth",
            source="gemini_synthetic_generator",
            text="Đánh giá do mô hình ngôn ngữ lớn sinh tự động bị cấm tuyệt đối.",
        ),
        _make_valid_review(
            review_id="aux_leak",
            source="phamluan/vn_msa_sar_v3",
            text="Dữ liệu phụ trợ ABSA không được phép trộn vào kho RAG chính.",
        ),
        # 14. Unsupported mapping method & confidence mismatch
        _make_valid_review(
            review_id="bad_map_method",
            mapping_method="NAME_ONLY_FUZZY_MATCH",
            text="Ánh xạ chỉ dựa trên tên địa điểm bị cấm theo quy tắc mục 6.",
        ),
        _make_valid_review(
            review_id="bad_map_conf",
            mapping_confidence=0.85,
            text="Độ tin cậy ánh xạ nhỏ hơn 1.0 cho POI đã khóa trước.",
        ),
        # 15. PII in scientific row
        _make_valid_review(
            review_id="pii_leak",
            email="user@example.com",
            text="Đánh giá chứa trường email cá nhân không được phép lưu.",
        ),
    ]

    report = w07_a2.validate_review_rows(rows, manifest)
    assert report["accepted_review_count"] == 1
    assert report["rejected_review_count"] == 17
    assert report["duplicate_count"] == 2
    assert report["CORPUS_SCIENTIFIC_MINIMUM_READY"] is False


def test_w07_a2_validator_flags_short_and_near_duplicate_warnings() -> None:
    manifest = w07_a2.build_w07_target_60_pois_manifest(REPO_ROOT)
    rows = [
        # Short review (< 20 chars / < 5 words) should be accepted but flagged with warning
        _make_valid_review(
            review_id="short_ok",
            text="Rất đẹp và sạch!",
        ),
        _make_valid_review(
            review_id="base_near_dup",
            text="Khách sạn có phòng ốc rộng rãi sạch sẽ nhân viên nhiệt tình gần biển Mỹ Khê.",
        ),
        _make_valid_review(
            review_id="second_near_dup",
            poi_id="9974ff88-5418-5867-ae49-1b72e0f0861f",
            city="Đà Nẵng",
            text="Khách sạn có phòng ốc rộng rãi sạch sẽ nhân viên nhiệt tình gần biển Mỹ Khê Đà Nẵng.",
        ),
    ]
    report = w07_a2.validate_review_rows(rows, manifest)
    assert report["accepted_review_count"] == 3
    assert report["rejected_review_count"] == 0
    assert report["warning_count"] == 2


def test_w07_a2_readiness_threshold_requires_all_60_pois_with_5_reviews() -> None:
    manifest = w07_a2.build_w07_target_60_pois_manifest(REPO_ROOT)
    rows: list[dict[str, Any]] = []
    for poi in manifest["pois"]:
        pid = poi["poi_id"]
        city = poi["city"]
        for r_idx in range(1, 6):
            rows.append(
                _make_valid_review(
                    review_id=f"rev_{pid[:8]}_{r_idx}",
                    poi_id=pid,
                    city=city,
                    text=(
                        f"Trải nghiệm thực tế lần {r_idx} tại địa điểm {poi['name']} ở {city}: "
                        f"không gian ấn tượng, dịch vụ chu đáo, đáng để ghé thăm trong hành trình."
                    ),
                    rating=float((r_idx % 5) + 1),
                )
            )

    # With 299 rows (last POI has 4 reviews), readiness must be False
    partial_report = w07_a2.validate_review_rows(rows[:-1], manifest)
    assert partial_report["accepted_review_count"] == 299
    assert partial_report["covered_poi_count"] == 60
    assert partial_report["pois_meeting_min_5_reviews_count"] == 59
    assert partial_report["CORPUS_SCIENTIFIC_MINIMUM_READY"] is False
    assert partial_report["freeze_status"] == "PARTIAL_COLLECTION_NOT_SCIENTIFIC_FREEZE"

    # With all 300 rows (60 POIs x 5 reviews), readiness must be True
    full_report = w07_a2.validate_review_rows(rows, manifest)
    assert full_report["accepted_review_count"] == 300
    assert full_report["covered_poi_count"] == 60
    assert full_report["pois_meeting_min_5_reviews_count"] == 60
    assert full_report["CORPUS_SCIENTIFIC_MINIMUM_READY"] is True
    assert full_report["freeze_status"] == "SCIENTIFIC_MINIMUM_FROZEN"
    assert full_report["remaining_reviews_needed_for_scientific_minimum"] == 0


def test_w07_a2_preserves_w06_w07_0_and_w07_a1_immutability() -> None:
    shas = w07_a2.verify_prior_gates_immutability(REPO_ROOT)
    assert shas["w06_closure_internal_sha256"] == w07_a2.EXPECTED_W06_CLOSURE_INTERNAL_SHA256
    assert shas["w07_0_audit_internal_sha256"] == w07_a2.EXPECTED_W07_0_INTERNAL_SHA256
    assert shas["w07_a1_feasibility_internal_sha256"] == w07_a2.EXPECTED_W07_A1_INTERNAL_SHA256
    assert w06_closure.compute_closure_internal_sha256(
        w06_closure.build_closure_payload()
    ) == w07_a2.EXPECTED_W06_CLOSURE_INTERNAL_SHA256
    assert w07_0_audit.verify_w07_audit_artifacts(REPO_ROOT)["status"] == "PASS"
    assert w07_a1.verify_w07_a1_artifacts(REPO_ROOT)["status"] == "PASS"
