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
    default_upstream = (
        "osm:way/37625751"
        if poi_id == "698ee756-6062-5f47-955b-bdf458682e57"
        else None
    )
    row: dict[str, Any] = {
        "review_id": review_id,
        "poi_id": poi_id,
        "upstream_place_id": default_upstream,
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
        == "b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b"
    )
    assert (
        res["manifest_file_lf_sha256"]
        == "3a065165d038f300f5dc422180fcaf3cef265ac1a100ea8e841daaba1a82d5d4"
    )
    assert (
        res["intake_status_internal_sha256"]
        == "4dd13bd7ad51ddfc3f501a11935f109928b2db8e9de52849da97d1a691ad2624"
    )
    assert (
        res["intake_status_file_lf_sha256"]
        == "69acd3bd814aa9ae166b2d715803ee227e47f3dd91aba05a4bd40dcffdee67ce"
    )
    assert (
        res["contributor_spec_md_lf_sha256"]
        == "32bf0290f817fcab1d15a46e3c37e32902d7d617654b7a4eafc5198153fa4392"
    )
    assert res["CORPUS_SCIENTIFIC_MINIMUM_READY"] is False
    assert res["corpus_collection_status"] == "COLLECTION_IN_PROGRESS"


def test_w07_a2_manifest_60_pois_city_and_category_balance_and_source_derivation() -> None:
    manifest_path = REPO_ROOT / w07_a2.MANIFEST_60_JSON_RELPATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    freeze_path = REPO_ROOT / w07_a2.PLACES_FREEZE_RELPATH
    freeze_by_id = {
        str(p["place_id"]): p
        for p in json.loads(freeze_path.read_text(encoding="utf-8"))
    }

    pois = manifest["pois"]
    # 3. 60 unique canonical POIs
    assert len(pois) == 60
    assert len({p["poi_id"] for p in pois}) == 60
    # 1. Final city balance = 20/20/20
    assert manifest["summary_statistics"]["city_distribution"] == {
        "Hà Nội": 20,
        "Đà Nẵng": 20,
        "Hạ Long": 20,
    }
    # 2. Final category balance = 21/21/6/9/3 global and 7/7/2/3/1 per city
    assert manifest["summary_statistics"]["category_group_distribution"] == {
        "attractions_culture": 21,
        "restaurants_cafes_markets": 21,
        "hotels": 6,
        "nature_beach": 9,
        "other_tourism": 3,
    }
    for city_name in ("Hà Nội", "Đà Nẵng", "Hạ Long"):
        assert manifest["summary_statistics"]["per_city_category_group_distribution"][
            city_name
        ] == {
            "attractions_culture": 7,
            "restaurants_cafes_markets": 7,
            "hotels": 2,
            "nature_beach": 3,
            "other_tourism": 1,
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
        # 4. Every POI exists in gomate_places_freeze_v2.json
        assert p["poi_id"] in freeze_by_id
        raw = freeze_by_id[p["poi_id"]]
        # 5. Every osm_id / source_ids in manifest is derived from gomate_places_freeze_v2.json
        expected_osm, expected_overture, expected_source_ids = w07_a2._extract_source_ids(
            raw
        )
        assert p["osm_id"] == expected_osm
        assert p["overture_id"] == expected_overture
        assert p["source_ids"] == expected_source_ids


def test_w07_a2_example_upstream_place_id_matches_manifest_and_stale_rejected() -> None:
    manifest = w07_a2.build_w07_target_60_pois_manifest(REPO_ROOT)
    poi_by_id = {p["poi_id"]: p for p in manifest["pois"]}
    example_row = w07_a2.build_example_review_row(manifest)

    # 6. Example upstream_place_id is in manifest[poi_id].source_ids
    assert example_row["poi_id"] == "698ee756-6062-5f47-955b-bdf458682e57"
    assert example_row["upstream_place_id"] == "osm:way/37625751"
    assert (
        example_row["upstream_place_id"]
        in poi_by_id[example_row["poi_id"]]["source_ids"]
    )

    spec_md = (REPO_ROOT / w07_a2.CONTRIBUTOR_SPEC_MD_RELPATH).read_text(encoding="utf-8")
    assert "osm:way/37625751" in spec_md
    assert "osm:way/37629144" not in spec_md

    # Stale osm:way/37629144 must be rejected by validator
    stale_row = _make_valid_review(
        review_id="stale_upstream",
        upstream_place_id="osm:way/37629144",
    )
    report = w07_a2.validate_review_rows([example_row, stale_row], manifest)
    assert report["accepted_review_count"] == 1
    assert report["rejected_review_count"] == 1
    assert (
        "UPSTREAM_PLACE_ID_NOT_IN_MANIFEST_SOURCE_IDS"
        in report["rejected_rows"][0]["reasons"]
    )


def test_w07_a2_first_party_consent_enforcement() -> None:
    manifest = w07_a2.build_w07_target_60_pois_manifest(REPO_ROOT)
    rows = [
        # 7. First-party consent without consent_record_id rejected
        _make_valid_review(
            review_id="missing_consent_owner",
            license_or_usage_class="OWNER_FIRST_PARTY_CONSENT",
            consent_record_id=None,
            text="Đánh giá đóng góp trực tiếp nhưng bị thiếu mã consent_record_id.",
        ),
        _make_valid_review(
            review_id="empty_consent_ccby",
            license_or_usage_class="CC-BY-4.0_FIRST_PARTY_CONSENT",
            consent_record_id="   ",
            text="Đánh giá đóng góp theo giấy phép CC-BY-4.0 nhưng consent_record_id rỗng.",
        ),
        # 8. First-party consent with consent_record_id accepted
        _make_valid_review(
            review_id="valid_first_party_owner",
            license_or_usage_class="OWNER_FIRST_PARTY_CONSENT",
            consent_record_id="consent_w07_valid_0001",
            text="Đánh giá đóng góp trực tiếp có đầy đủ mã đồng thuận hợp lệ.",
        ),
        # Public research-permitted source may keep consent_record_id = None
        _make_valid_review(
            review_id="valid_public_research",
            source="approved_public_research_dataset_v1",
            provenance="PUBLIC_RESEARCH_DATASET_EXPLICIT_LICENSE",
            license_or_usage_class="PUBLIC_RESEARCH_PERMITTED_APPROVED",
            mapping_method="EXACT_UPSTREAM_ID",
            consent_record_id=None,
            text="Đánh giá từ tập dữ liệu nghiên cứu công khai hợp lệ đã được phê duyệt.",
        ),
    ]
    report = w07_a2.validate_review_rows(rows, manifest)
    assert report["accepted_review_count"] == 2
    assert report["rejected_review_count"] == 2
    for rejected in report["rejected_rows"]:
        assert "REJECT_MISSING_CONSENT_RECORD" in rejected["reasons"]


def test_w07_a2_pii_firewall_in_review_text_and_readiness_exclusion() -> None:
    manifest = w07_a2.build_w07_target_60_pois_manifest(REPO_ROOT)
    # 9 & 10. Phone number and email address in review_text quarantined/rejected
    pii_phone_row = _make_valid_review(
        review_id="pii_phone_in_text",
        text="Địa điểm rất đẹp, liên hệ hướng dẫn viên số 0912 345 678 để đặt vé nhanh.",
    )
    pii_email_row = _make_valid_review(
        review_id="pii_email_in_text",
        text="Không gian tuyệt vời, gửi ảnh cho tôi qua địa chỉ traveller.test@gmail.com nhé.",
    )
    pii_report = w07_a2.validate_review_rows([pii_phone_row, pii_email_row], manifest)
    assert pii_report["accepted_review_count"] == 0
    assert pii_report["rejected_review_count"] == 2
    assert pii_report["quarantined_pii_count"] == 2
    for rej in pii_report["rejected_rows"]:
        assert "QUARANTINE_PII_REVIEW_TEXT" in rej["reasons"]

    # 11. Quarantined PII review does not count toward accepted_review_count or CORPUS_SCIENTIFIC_MINIMUM_READY
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
    # Replace the 300th review with a PII-containing review
    rows[-1]["review_text"] = (
        "Trải nghiệm thực tế tại địa điểm nhưng để lộ số điện thoại 0987654321 trong bài viết."
    )
    near_full_report = w07_a2.validate_review_rows(rows, manifest)
    assert near_full_report["accepted_review_count"] == 299
    assert near_full_report["quarantined_pii_count"] == 1
    assert near_full_report["pois_meeting_min_5_reviews_count"] == 59
    assert near_full_report["CORPUS_SCIENTIFIC_MINIMUM_READY"] is False


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
