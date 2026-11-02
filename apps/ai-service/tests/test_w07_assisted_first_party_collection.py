"""Offline deterministic tests for W07-A4H Assisted First-Party Review Collection Pipeline.

NOTE: All review records used in these tests are clearly labeled synthetic TEST FIXTURES
running in memory or pytest `tmp_path` and are NEVER written to the restricted corpus.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from scripts import (
    import_w07_assisted_reviews_v1 as w07_a4h,
    import_w07_contributor_reviews_v1 as w07_a3_import,
    report_w07_review_collection_progress as w07_a3_progress,
    run_w07_data_rag_readiness_audit as w07_0_audit,
    run_w07_review_corpus_feasibility as w07_a1,
    validate_w07_review_corpus_v1 as w07_a2,
    verify_w06_scientific_closure as w06_closure,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _make_assisted_csv_row(
    *,
    contributor_code: str = "W07C001",
    poi_id: str = "698ee756-6062-5f47-955b-bdf458682e57",
    city: str = "Hà Nội",
    rating: str = "5",
    review_text: str = (
        "TEST_FIXTURE_ONLY: Khu vực quảng trường Ba Đình rộng rãi, sạch sẽ, "
        "trải nghiệm tham quan buổi sáng rất trang nghiêm và trật tự."
    ),
    visit_period: str = "2025-10",
    collection_channel: str = "ZALO",
    capture_mode: str = "CONTRIBUTOR_WRITTEN_VERBATIM",
    review_text_approved: str = "true",
    consent_confirmed: str = "Tôi đồng ý",
    consent_timestamp: str = "2026-11-02T09:00:00Z",
    consent_evidence_type: str = "CHAT_WRITTEN_CONSENT",
    consent_evidence_ref: str = "zalo_thread_w07c001_20261102_001",
    collector_code: str = "OWNER_01",
    collected_at: str = "2026-11-02T09:05:00Z",
    **extra_cols: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "contributor_code": contributor_code,
        "poi_id": poi_id,
        "city": city,
        "rating": rating,
        "review_text": review_text,
        "visit_period": visit_period,
        "collection_channel": collection_channel,
        "capture_mode": capture_mode,
        "review_text_approved": review_text_approved,
        "consent_confirmed": consent_confirmed,
        "consent_timestamp": consent_timestamp,
        "consent_evidence_type": consent_evidence_type,
        "consent_evidence_ref": consent_evidence_ref,
        "collector_code": collector_code,
        "collected_at": collected_at,
    }
    row.update(extra_cols)
    return row


def _make_raw_form_response(
    *,
    timestamp: str,
    poi_name: str,
    rating: str,
    review_text: str,
    visit_period: str = "2025-10",
) -> dict[str, Any]:
    return {
        "Timestamp": timestamp,
        "1. Chọn địa điểm (POI) bạn đã trực tiếp đến trải nghiệm": poi_name,
        "2. Điểm đánh giá tổng thể (1 = Rất tệ, 5 = Rất tốt)": rating,
        "3. Nội dung đánh giá thực tế của riêng bạn": review_text,
        "4. Thời điểm ghé thăm (Không bắt buộc)": visit_period,
        "5. Cam kết tính xác thực và đồng thuận nghiên cứu học thuật": (
            w07_a3_import.CONSENT_CHECKBOX_OPTION_LABEL
        ),
    }


def test_01_valid_contributor_written_review_accepted() -> None:
    """Scenario 1: Valid contributor-written review (`CONTRIBUTOR_WRITTEN_VERBATIM`) is accepted."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    raw = _make_assisted_csv_row(
        capture_mode="CONTRIBUTOR_WRITTEN_VERBATIM",
        review_text_approved="",  # implied true by direct written submission + explicit consent
    )
    cand, reasons, stripped = w07_a4h.convert_assisted_csv_row_to_candidate(
        raw,
        manifest_payload=manifest,
    )
    assert reasons == []
    assert stripped == []
    assert cand["source"] == "assisted_first_party"
    assert cand["provenance"] == "FIRST_PARTY_ASSISTED_COLLECTION_CONSENT_V1"
    assert cand["license_or_usage_class"] == "OWNER_FIRST_PARTY_CONSENT"
    assert cand["mapping_method"] == "EXACT_PREBOUND_CANONICAL_POI"
    assert cand["mapping_confidence"] == 1.0
    assert cand["review_text_approved"] is True
    assert cand["consent_record_id"] is not None
    assert cand["consent_record_id"].startswith("consent_w07_assisted_v1_")

    val = w07_a4h.validate_assisted_candidates([(cand, reasons)], manifest)
    assert val["accepted_review_count"] == 1
    assert val["rejected_review_count"] == 0


def test_02_transcription_without_final_approval_rejected() -> None:
    """Scenario 2: Oral/transcribed modes without explicit final-text approval are rejected (`REJECT_TEXT_NOT_CONTRIBUTOR_APPROVED`)."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    for mode in (
        "COLLECTOR_TRANSCRIBED_VERBATIM",
        "COLLECTOR_TRANSCRIBED_AND_CONTRIBUTOR_APPROVED",
    ):
        for unapproved_val in ("", "false", "no", "0", "chưa"):
            raw = _make_assisted_csv_row(
                capture_mode=mode,
                review_text_approved=unapproved_val,
                review_text=(
                    f"TEST_FIXTURE_ONLY: Đánh giá ghi âm miệng chế độ {mode} "
                    f"với trạng thái duyệt '{unapproved_val}' phải bị từ chối."
                ),
            )
            cand, reasons, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
                raw,
                manifest_payload=manifest,
            )
            assert "REJECT_TEXT_NOT_CONTRIBUTOR_APPROVED" in reasons
            val = w07_a4h.validate_assisted_candidates([(cand, reasons)], manifest)
            assert val["accepted_review_count"] == 0
            assert val["rejected_review_count"] == 1
            assert (
                "REJECT_TEXT_NOT_CONTRIBUTOR_APPROVED"
                in val["rejected_rows"][0]["reasons"]
            )


def test_03_transcription_with_approval_accepted() -> None:
    """Scenario 3: Transcription modes with explicit contributor final-text approval are accepted."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    pois = manifest["pois"]

    cand1, reasons1, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        _make_assisted_csv_row(
            contributor_code="W07C002",
            poi_id=pois[0]["poi_id"],
            city=pois[0]["city"],
            capture_mode="COLLECTOR_TRANSCRIBED_VERBATIM",
            review_text_approved="true",
            review_text=(
                "TEST_FIXTURE_ONLY: Ghi chép nguyên văn lời kể của người đóng góp "
                "sau khi đi thăm Lăng Bác và đã gửi lại văn bản để xác nhận."
            ),
        ),
        manifest_payload=manifest,
    )
    cand2, reasons2, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        _make_assisted_csv_row(
            contributor_code="W07C002",
            poi_id=pois[1]["poi_id"],
            city=pois[1]["city"],
            capture_mode="COLLECTOR_TRANSCRIBED_AND_CONTRIBUTOR_APPROVED",
            review_text_approved="Tôi duyệt",
            review_text=(
                "TEST_FIXTURE_ONLY: Khu di tích Hoàng thành Thăng Long rất rộng, "
                "người thu thập gõ lại dấu câu và người đóng góp đã duyệt nguyên văn."
            ),
        ),
        manifest_payload=manifest,
    )
    assert reasons1 == []
    assert reasons2 == []
    val = w07_a4h.validate_assisted_candidates(
        [(cand1, reasons1), (cand2, reasons2)],
        manifest,
    )
    assert val["accepted_review_count"] == 2
    assert val["rejected_review_count"] == 0


def test_04_missing_consent_rejected() -> None:
    """Scenario 4: Missing or negative consent is rejected (`REJECT_MISSING_CONSENT_CONFIRMATION` + `REJECT_MISSING_CONSENT_RECORD`)."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    for bad_consent in ("", "false", "no", "0", "không", "silence"):
        cand, reasons, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
            _make_assisted_csv_row(consent_confirmed=bad_consent),
            manifest_payload=manifest,
        )
        assert "REJECT_MISSING_CONSENT_CONFIRMATION" in reasons
        assert cand["consent_record_id"] is None
        val = w07_a4h.validate_assisted_candidates([(cand, reasons)], manifest)
        assert val["accepted_review_count"] == 0
        assert "REJECT_MISSING_CONSENT_CONFIRMATION" in val["rejected_rows"][0]["reasons"]
        assert "REJECT_MISSING_CONSENT_RECORD" in val["rejected_rows"][0]["reasons"]


def test_05_unsupported_verbal_only_consent_rejected() -> None:
    """Scenario 5: Undocumented verbal-only or unsupported consent evidence type is rejected."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    for bad_ev_type in ("VERBAL_ONLY", "ORAL_ONLY", "IMPLIED_SILENCE", "PHONE_AUDIO_ONLY", ""):
        cand, reasons, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
            _make_assisted_csv_row(consent_evidence_type=bad_ev_type),
            manifest_payload=manifest,
        )
        assert cand["consent_record_id"] is None
        val = w07_a4h.validate_assisted_candidates([(cand, reasons)], manifest)
        assert val["accepted_review_count"] == 0
        row_reasons = val["rejected_rows"][0]["reasons"]
        assert any(
            r.startswith("REJECT_VERBAL_ONLY_OR_FORBIDDEN_CONSENT")
            or r.startswith("REJECT_UNSUPPORTED_CONSENT_EVIDENCE_TYPE")
            for r in row_reasons
        )


def test_06_unknown_poi_and_name_only_mapping_rejected() -> None:
    """Scenario 6: Unknown `poi_id` or attempting to map by POI name instead of UUID is rejected (`UNKNOWN_CANONICAL_POI`)."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    for bad_poi in ("00000000-0000-0000-0000-000000000000", "Lăng Chủ tịch Hồ Chí Minh", ""):
        cand, reasons, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
            _make_assisted_csv_row(poi_id=bad_poi),
            manifest_payload=manifest,
        )
        assert "UNKNOWN_CANONICAL_POI" in reasons
        val = w07_a4h.validate_assisted_candidates([(cand, reasons)], manifest)
        assert val["accepted_review_count"] == 0
        assert "UNKNOWN_CANONICAL_POI" in val["rejected_rows"][0]["reasons"]


def test_07_city_mismatch_rejected() -> None:
    """Scenario 7: City mismatch against `manifest[poi_id].city` is rejected (`CITY_MISMATCH`)."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    cand, reasons, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        _make_assisted_csv_row(
            poi_id="698ee756-6062-5f47-955b-bdf458682e57",  # Hà Nội POI
            city="Đà Nẵng",
        ),
        manifest_payload=manifest,
    )
    assert any(r.startswith("CITY_MISMATCH") for r in reasons)
    val = w07_a4h.validate_assisted_candidates([(cand, reasons)], manifest)
    assert val["accepted_review_count"] == 0
    assert any(r.startswith("CITY_MISMATCH") for r in val["rejected_rows"][0]["reasons"])


def test_08_same_contributor_same_poi_duplicate_rejected_but_multi_poi_allowed() -> None:
    """Scenario 8: Same contributor + same POI is rejected (`REJECT_DUPLICATE_CONTRIBUTOR_POI`), while same contributor reviewing multiple visited POIs is accepted."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    poi_1 = manifest["pois"][0]
    poi_2 = manifest["pois"][1]

    c1, r1, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        _make_assisted_csv_row(
            contributor_code="W07C005",
            poi_id=poi_1["poi_id"],
            city=poi_1["city"],
            review_text=(
                "TEST_FIXTURE_ONLY: Đánh giá thứ nhất của W07C005 cho Lăng Chủ tịch Hồ Chí Minh "
                "vào dịp mùa thu tháng 10."
            ),
        ),
        manifest_payload=manifest,
    )
    # Same contributor W07C005 submitting a second review for the SAME POI poi_1 -> must be rejected!
    c1_dup, r1_dup, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        _make_assisted_csv_row(
            contributor_code="W07C005",
            poi_id=poi_1["poi_id"],
            city=poi_1["city"],
            rating="4",
            review_text=(
                "TEST_FIXTURE_ONLY: Đánh giá thứ hai khác nội dung của cùng W07C005 cho cùng "
                "địa điểm Lăng Chủ tịch Hồ Chí Minh."
            ),
        ),
        manifest_payload=manifest,
    )
    # Same contributor W07C005 reviewing a DIFFERENT POI poi_2 -> must be accepted!
    c2, r2, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        _make_assisted_csv_row(
            contributor_code="W07C005",
            poi_id=poi_2["poi_id"],
            city=poi_2["city"],
            rating="5",
            review_text=(
                "TEST_FIXTURE_ONLY: Đánh giá hợp lệ của cùng W07C005 cho địa điểm thứ hai là "
                "Hoàng thành Thăng Long với khuôn viên cổ kính."
            ),
        ),
        manifest_payload=manifest,
    )

    val = w07_a4h.validate_assisted_candidates(
        [(c1, r1), (c1_dup, r1_dup), (c2, r2)],
        manifest,
    )
    assert val["accepted_review_count"] == 2
    assert val["rejected_review_count"] == 1
    assert "REJECT_DUPLICATE_CONTRIBUTOR_POI" in val["rejected_rows"][0]["reasons"]


def test_09_and_10_deterministic_consent_id_and_review_id() -> None:
    """Scenarios 9 & 10: `consent_record_id` and `review_id` are strictly deterministic and bind required fields."""
    cid_a = w07_a4h.generate_assisted_consent_record_id(
        contributor_code="W07C010",
        poi_id="698ee756-6062-5f47-955b-bdf458682e57",
        consent_timestamp="2026-11-02T10:00:00Z",
        consent_evidence_type="CHAT_WRITTEN_CONSENT",
        consent_evidence_ref="zalo_msg_w07c010_01",
    )
    cid_b = w07_a4h.generate_assisted_consent_record_id(
        contributor_code="w07c010",
        poi_id="698ee756-6062-5f47-955b-bdf458682e57",
        consent_timestamp="2026-11-02T10:00:00Z",
        consent_evidence_type="chat_written_consent",
        consent_evidence_ref="  zalo_msg_w07c010_01  ",
    )
    cid_diff = w07_a4h.generate_assisted_consent_record_id(
        contributor_code="W07C011",
        poi_id="698ee756-6062-5f47-955b-bdf458682e57",
        consent_timestamp="2026-11-02T10:00:00Z",
        consent_evidence_type="CHAT_WRITTEN_CONSENT",
        consent_evidence_ref="zalo_msg_w07c010_01",
    )
    assert cid_a == cid_b
    assert cid_a != cid_diff
    assert cid_a.startswith("consent_w07_assisted_v1_")
    assert "zalo_msg" not in cid_a

    rid_a = w07_a4h.generate_assisted_review_id(
        contributor_code="W07C010",
        poi_id="698ee756-6062-5f47-955b-bdf458682e57",
        city_code="hn",
        rating_str="5",
        review_text="TEST_FIXTURE_ONLY: Đánh giá kiểm tra tính tất định của review_id.",
        visit_period="2025-10",
        capture_mode="CONTRIBUTOR_WRITTEN_VERBATIM",
    )
    rid_b = w07_a4h.generate_assisted_review_id(
        contributor_code="w07c010",
        poi_id="698ee756-6062-5f47-955b-bdf458682e57",
        city_code="HN",
        rating_str="5",
        review_text="TEST_FIXTURE_ONLY: Đánh giá kiểm tra tính tất định của review_id.",
        visit_period="2025-10",
        capture_mode="contributor_written_verbatim",
    )
    assert rid_a == rid_b
    assert rid_a.startswith("w07_arev_hn_")


def test_11_repeated_import_idempotent(tmp_path: Path) -> None:
    """Scenario 11: Repeated import of the same unchanged assisted CSV produces identical IDs and identical JSONL."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    poi_1 = manifest["pois"][0]
    poi_2 = manifest["pois"][20]  # Đà Nẵng POI

    csv_path = tmp_path / "assisted_batch.csv"
    output_jsonl = tmp_path / "w07_assisted_candidate_reviews_v1.jsonl"

    rows = [
        _make_assisted_csv_row(
            contributor_code="W07C001",
            poi_id=poi_1["poi_id"],
            city=poi_1["city"],
            rating="5",
            review_text=(
                "TEST_FIXTURE_ONLY: Không gian quảng trường Ba Đình rất trang nghiêm, "
                "sạch sẽ và an ninh tốt."
            ),
        ),
        _make_assisted_csv_row(
            contributor_code="W07C001",
            poi_id=poi_2["poi_id"],
            city=poi_2["city"],
            rating="5",
            review_text=(
                "TEST_FIXTURE_ONLY: Cầu Rồng Đà Nẵng buổi tối cuối tuần phun lửa và phun nước "
                "rất sôi động, không khí ven sông Hàn thoáng mát."
            ),
        ),
    ]

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(w07_a4h.REQUIRED_TEMPLATE_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)

    run1 = w07_a4h.import_assisted_csv_files(
        [csv_path],
        output_jsonl_path=output_jsonl,
        repo_root=REPO_ROOT,
    )
    assert run1["accepted_review_count"] == 2
    assert run1["idempotent_duplicate_rows_skipped"] == 0
    content1 = output_jsonl.read_text(encoding="utf-8")

    run2 = w07_a4h.import_assisted_csv_files(
        [csv_path],
        output_jsonl_path=output_jsonl,
        repo_root=REPO_ROOT,
    )
    assert run2["accepted_review_count"] == 2
    assert run2["idempotent_duplicate_rows_skipped"] == 2
    assert run2["output_jsonl_lf_sha256"] == run1["output_jsonl_lf_sha256"]
    assert output_jsonl.read_text(encoding="utf-8") == content1


def test_12_phone_and_email_pii_quarantine() -> None:
    """Scenario 12: Phone or email inside `review_text` triggers `QUARANTINE_PII_REVIEW_TEXT` without rewriting text."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    raw_phone = _make_assisted_csv_row(
        contributor_code="W07C020",
        review_text=(
            "TEST_FIXTURE_ONLY: Địa điểm đẹp, liên hệ mình qua số 0912 345 678 "
            "để ghép đoàn đi chung nhé."
        ),
    )
    raw_email = _make_assisted_csv_row(
        contributor_code="W07C021",
        review_text=(
            "TEST_FIXTURE_ONLY: Trải nghiệm rất tốt, gửi ảnh cho mình qua hòm thư "
            "traveller_hn@example.com nhé."
        ),
    )
    c_phone, r_phone, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        raw_phone, manifest_payload=manifest
    )
    c_email, r_email, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        raw_email, manifest_payload=manifest
    )
    # Verbatim text must NOT be rewritten
    assert "0912 345 678" in c_phone["review_text"]
    assert "traveller_hn@example.com" in c_email["review_text"]

    val = w07_a4h.validate_assisted_candidates(
        [(c_phone, r_phone), (c_email, r_email)],
        manifest,
    )
    assert val["accepted_review_count"] == 0
    assert val["rejected_review_count"] == 2
    assert val["quarantined_pii_count"] == 2
    for rej in val["rejected_rows"]:
        assert "QUARANTINE_PII_REVIEW_TEXT" in rej["reasons"]


def test_13_and_14_forbidden_ai_source_and_copied_online_provenance_rejected() -> None:
    """Scenarios 13 & 14: Forbidden AI/LLM generation or paraphrase and copied-online reviews are rejected."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)

    for bad_mode in (
        "AI_GENERATED",
        "AI_REWRITTEN",
        "COLLECTOR_PARAPHRASED",
        "COPIED_ONLINE_REVIEW",
    ):
        cand, reasons, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
            _make_assisted_csv_row(capture_mode=bad_mode),
            manifest_payload=manifest,
        )
        val = w07_a4h.validate_assisted_candidates([(cand, reasons)], manifest)
        assert val["accepted_review_count"] == 0
        row_reasons = val["rejected_rows"][0]["reasons"]
        assert any(
            r.startswith("REJECT_FORBIDDEN_CAPTURE_MODE")
            or r == "SYNTHETIC_OR_LLM_OR_DISALLOWED_SOURCE"
            or r == "REJECT_COPIED_ONLINE_PROVENANCE"
            for r in row_reasons
        )

    # Also test copied online provenance in metadata/evidence_ref
    for online_platform in ("google_maps_copy", "tripadvisor_review", "booking.com", "agoda", "foody"):
        cand_copy, reasons_copy, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
            _make_assisted_csv_row(consent_evidence_ref=online_platform),
            manifest_payload=manifest,
        )
        assert "REJECT_COPIED_ONLINE_PROVENANCE" in reasons_copy


def test_15_identity_fields_stripped_and_never_stored() -> None:
    """Scenario 15: Accidental identity columns (`real_name`, `email`, `phone`, `Facebook`, `zalo_id`, `messenger_id`, `student_id`, `national_id`) are stripped."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    raw = _make_assisted_csv_row(
        **{
            "real_name": "Trần Thị B",
            "email": "tranthib@example.edu.vn",
            "phone": "0987654321",
            "Facebook": "fb.com/tranthib",
            "zalo_id": "zalo_tranthib_99",
            "messenger_id": "m.me/tranthib",
            "student_id": "20210999",
            "national_id": "001202009999",
        }
    )
    cand, reasons, stripped = w07_a4h.convert_assisted_csv_row_to_candidate(
        raw,
        manifest_payload=manifest,
    )
    assert reasons == []
    assert set(stripped) == {
        "real_name",
        "email",
        "phone",
        "Facebook",
        "zalo_id",
        "messenger_id",
        "student_id",
        "national_id",
    }
    serialized = json.dumps(cand, ensure_ascii=False)
    for forbidden_val in (
        "Trần Thị B",
        "tranthib@example.edu.vn",
        "0987654321",
        "fb.com/tranthib",
        "zalo_tranthib_99",
        "m.me/tranthib",
        "20210999",
        "001202009999",
        "zalo_thread_w07c001_20261102_001",  # raw consent_evidence_ref must also never appear in JSONL!
    ):
        assert forbidden_val not in serialized


def test_16_17_18_mixed_form_and_assisted_pilot_gate_city_and_poi_math() -> None:
    """Scenarios 16, 17, 18: 30-review mixed form+assisted pilot gate, city coverage math (>=10/city), and >=15 distinct POI math."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    pois_by_city = {
        city: [p for p in manifest["pois"] if p["city"] == city]
        for city in ("Hà Nội", "Đà Nẵng", "Hạ Long")
    }

    distinct_themes = [
        "kiến trúc cổ kính và không gian thoáng đãng buổi sáng",
        "dịch vụ chu đáo, lối đi bộ sạch sẽ và nhiều bảng chỉ dẫn",
        "trải nghiệm văn hóa đặc sắc, rất đáng để ghé thăm cùng gia đình",
        "góc chụp ảnh đẹp, không khí trong lành và yên bình",
        "ấn tượng với cách bài trí hiện vật và thuyết minh chi tiết",
        "đồ ăn hợp khẩu vị, phục vụ nhanh nhẹn và giá cả hợp lý",
        "vị trí thuận tiện di chuyển, cảnh quan xung quanh rất bắt mắt",
        "buổi chiều mát mẻ, ngắm hoàng hôn tuyệt đẹp và thư giãn",
        "khuôn viên nhiều cây xanh, bảo tồn tốt nét đặc trưng truyền thống",
        "nhân viên thân thiện, hướng dẫn tận tình cho khách du lịch",
    ]

    # Build 15 Direct Google Form reviews (5 per city across POIs 0..4)
    form_rows: list[dict[str, Any]] = []
    for c_idx, (city, city_pois) in enumerate(pois_by_city.items()):
        for p_idx in range(5):
            poi = city_pois[p_idx]
            raw_form = _make_raw_form_response(
                timestamp=f"2026-11-02 08:{c_idx:02d}:{p_idx:02d}",
                poi_name=poi["name"],
                rating=str(((c_idx + p_idx) % 5) + 1),
                review_text=(
                    f"TEST_FIXTURE_FORM_{city}_{p_idx}: Địa điểm {poi['name']} có "
                    f"{distinct_themes[p_idx]}."
                ),
            )
            cand_form, _ = w07_a3_import.convert_raw_form_row_to_candidate_review(
                raw_form,
                city_name=city,
                manifest_payload=manifest,
            )
            form_rows.append(cand_form)

    # Build 15 Assisted First-Party reviews (5 per city across POIs 0..4, from contributor W07C001..W07C003)
    assisted_rows: list[dict[str, Any]] = []
    for c_idx, (city, city_pois) in enumerate(pois_by_city.items()):
        for p_idx in range(5):
            poi = city_pois[p_idx]
            cand_ass, reasons, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
                _make_assisted_csv_row(
                    contributor_code=f"W07C00{c_idx + 1}",
                    poi_id=poi["poi_id"],
                    city=city,
                    rating=str(((c_idx + p_idx + 2) % 5) + 1),
                    review_text=(
                        f"TEST_FIXTURE_ASSISTED_{city}_{p_idx}: Ghé thăm {poi['name']} tại {city} "
                        f"với {distinct_themes[p_idx + 5]}."
                    ),
                ),
                manifest_payload=manifest,
            )
            assert reasons == []
            assisted_rows.append(cand_ass)

    # Scenario 16: 15 Form + 15 Assisted = 30 total (10/city, 15 distinct POIs) -> Pilot READY!
    report_mixed_30 = w07_a4h.build_combined_first_party_progress_report(
        form_rows=form_rows,
        assisted_rows=assisted_rows,
        manifest_payload=manifest,
    )
    assert report_mixed_30["combined_summary_counts"]["accepted_review_count"] == 30
    assert (
        report_mixed_30["combined_summary_counts"]["direct_google_form_accepted_count"]
        == 15
    )
    assert (
        report_mixed_30["combined_summary_counts"][
            "assisted_first_party_accepted_count"
        ]
        == 15
    )
    assert report_mixed_30["reviews_by_city"] == {
        "Hà Nội": 10,
        "Đà Nẵng": 10,
        "Hạ Long": 10,
    }
    assert report_mixed_30["combined_summary_counts"]["covered_poi_count"] == 15
    assert report_mixed_30["provenance_distribution"] == {
        "FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1": 15,
        "FIRST_PARTY_ASSISTED_COLLECTION_CONSENT_V1": 15,
    }
    assert (
        report_mixed_30["pilot_gate_evaluation"]["COLLECTION_PIPELINE_PILOT_READY"]
        is True
    )
    assert (
        report_mixed_30["scientific_minimum_evaluation"][
            "CORPUS_SCIENTIFIC_MINIMUM_READY"
        ]
        is False
    )
    # Verify no raw review text leaks into the combined progress JSON
    serialized_prog = json.dumps(report_mixed_30, ensure_ascii=False)
    assert "TEST_FIXTURE_FORM" not in serialized_prog
    assert "TEST_FIXTURE_ASSISTED" not in serialized_prog

    # Scenario 17: Pilot city coverage math — if 30 reviews are imbalanced (e.g. 11 Hà Nội, 10 Đà Nẵng, 9 Hạ Long),
    # pilot gate must be FALSE even though total == 30 and distinct POIs >= 15!
    extra_hn_cand, extra_reasons, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        _make_assisted_csv_row(
            contributor_code="W07C099",
            poi_id=pois_by_city["Hà Nội"][5]["poi_id"],
            city="Hà Nội",
            rating="5",
            review_text=(
                "TEST_FIXTURE_EXTRA_HN: Đánh giá bổ sung tại Hà Nội để kiểm tra trường hợp "
                "tổng đủ 30 nhưng Hạ Long chỉ có 9 đánh giá."
            ),
        ),
        manifest_payload=manifest,
    )
    assert extra_reasons == []
    report_city_imbalance = w07_a4h.build_combined_first_party_progress_report(
        form_rows=form_rows,
        assisted_rows=assisted_rows[:-1] + [extra_hn_cand],
        manifest_payload=manifest,
    )
    assert report_city_imbalance["combined_summary_counts"]["accepted_review_count"] == 30
    assert report_city_imbalance["reviews_by_city"] == {
        "Hà Nội": 11,
        "Đà Nẵng": 10,
        "Hạ Long": 9,
    }
    assert (
        report_city_imbalance["pilot_gate_evaluation"]["pilot_criteria_checks"][
            "accepted_reviews_gte_30"
        ]
        is True
    )
    assert (
        report_city_imbalance["pilot_gate_evaluation"]["pilot_criteria_checks"][
            "each_city_gte_10"
        ]
        is False
    )
    assert (
        report_city_imbalance["pilot_gate_evaluation"][
            "COLLECTION_PIPELINE_PILOT_READY"
        ]
        is False
    )

    # Scenario 18: >=15 distinct POI math — if 30 reviews (10/city) cover only 14 distinct POIs
    # (5 Hà Nội, 5 Đà Nẵng, 4 Hạ Long POIs), pilot gate must be FALSE!
    form_rows_14_pois = list(form_rows[:-1])
    # Replace the last Hạ Long form review (which was on POI index 4) with a review on POI index 0
    hl_poi_0 = pois_by_city["Hạ Long"][0]
    replacement_hl_form, _ = w07_a3_import.convert_raw_form_row_to_candidate_review(
        _make_raw_form_response(
            timestamp="2026-11-02 09:59:59",
            poi_name=hl_poi_0["name"],
            rating="4",
            review_text=(
                "TEST_FIXTURE_HL_DUP_POI: Đánh giá thứ ba cho Vịnh Hạ Long để tổng số POI "
                "khác nhau giảm từ 15 xuống 14 địa điểm."
            ),
        ),
        city_name="Hạ Long",
        manifest_payload=manifest,
    )
    form_rows_14_pois.append(replacement_hl_form)

    assisted_rows_14_pois = list(assisted_rows[:-1])
    replacement_hl_ass, rep_reasons, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        _make_assisted_csv_row(
            contributor_code="W07C088",
            poi_id=hl_poi_0["poi_id"],
            city="Hạ Long",
            rating="5",
            review_text=(
                "TEST_FIXTURE_HL_DUP_POI_2: Đánh giá thứ tư từ người đóng góp khác cho "
                "cùng Vịnh Hạ Long để giữ nguyên 10 đánh giá tại Hạ Long trên 4 POI."
            ),
        ),
        manifest_payload=manifest,
    )
    assert rep_reasons == []
    assisted_rows_14_pois.append(replacement_hl_ass)

    report_14_pois = w07_a4h.build_combined_first_party_progress_report(
        form_rows=form_rows_14_pois,
        assisted_rows=assisted_rows_14_pois,
        manifest_payload=manifest,
    )
    assert report_14_pois["combined_summary_counts"]["accepted_review_count"] == 30
    assert report_14_pois["reviews_by_city"] == {
        "Hà Nội": 10,
        "Đà Nẵng": 10,
        "Hạ Long": 10,
    }
    assert report_14_pois["combined_summary_counts"]["covered_poi_count"] == 14
    assert (
        report_14_pois["pilot_gate_evaluation"]["pilot_criteria_checks"][
            "distinct_pois_gte_15"
        ]
        is False
    )
    assert (
        report_14_pois["pilot_gate_evaluation"]["COLLECTION_PIPELINE_PILOT_READY"]
        is False
    )


def test_19_upstream_w06_w07_0_a1_a2_and_a3_hashes_unchanged() -> None:
    """Scenario 19: All upstream W06, W07-0, W07-A1, W07-A2, and W07-A3 artifact hashes remain unchanged."""
    verify_res = w07_a4h.verify_combined_first_party_progress_artifact(REPO_ROOT)
    assert verify_res["status"] == "PASS"
    assert verify_res["accepted_review_count"] == 0
    assert verify_res["direct_google_form_accepted_count"] == 0
    assert verify_res["assisted_first_party_accepted_count"] == 0
    assert verify_res["COLLECTION_PIPELINE_PILOT_READY"] is False
    assert verify_res["CORPUS_SCIENTIFIC_MINIMUM_READY"] is False

    assert (
        w06_closure.compute_closure_internal_sha256(w06_closure.build_closure_payload())
        == w07_a2.EXPECTED_W06_CLOSURE_INTERNAL_SHA256
    )
    assert w07_0_audit.verify_w07_audit_artifacts(REPO_ROOT)["status"] == "PASS"
    assert w07_a1.verify_w07_a1_artifacts(REPO_ROOT)["status"] == "PASS"
    assert w07_a2.verify_w07_a2_artifacts(REPO_ROOT)["status"] == "PASS"
    assert w07_a3_import.verify_form_definition_artifacts(REPO_ROOT)["status"] == "PASS"
    assert (
        w07_a3_progress.verify_collection_progress_artifact(REPO_ROOT)["status"]
        == "PASS"
    )


def test_20_near_duplicate_classified_as_manual_review_required() -> None:
    """Section 18: Suspicious near-identical reviews are classified as `MANUAL_REVIEW_REQUIRED` rather than silently accepted."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    poi_1 = manifest["pois"][0]
    poi_2 = manifest["pois"][1]

    c1, r1, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        _make_assisted_csv_row(
            contributor_code="W07C050",
            poi_id=poi_1["poi_id"],
            city=poi_1["city"],
            review_text=(
                "TEST_FIXTURE_ONLY: Không gian tham quan di tích lịch sử rất rộng rãi "
                "thoáng mát sạch sẽ nhiều cây xanh và hướng dẫn viên nhiệt tình chu đáo."
            ),
        ),
        manifest_payload=manifest,
    )
    # Near-duplicate (13 of 14 tokens identical -> Jaccard > 0.85)
    c2_near, r2_near, _ = w07_a4h.convert_assisted_csv_row_to_candidate(
        _make_assisted_csv_row(
            contributor_code="W07C051",
            poi_id=poi_2["poi_id"],
            city=poi_2["city"],
            review_text=(
                "TEST_FIXTURE_ONLY: Không gian tham quan di tích lịch sử rất rộng rãi "
                "thoáng mát sạch sẽ nhiều cây xanh và hướng dẫn viên nhiệt tình."
            ),
        ),
        manifest_payload=manifest,
    )

    val = w07_a4h.validate_assisted_candidates(
        [(c1, r1), (c2_near, r2_near)],
        manifest,
    )
    assert val["accepted_review_count"] == 1
    assert val["manual_review_required_count"] == 1
    assert (
        val["manual_review_required_rows"][0]["status"] == "MANUAL_REVIEW_REQUIRED"
    )
