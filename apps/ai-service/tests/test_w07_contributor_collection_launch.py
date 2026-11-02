"""Offline deterministic tests for W07-A3 Contributor Review Collection Launch & Pilot Pipeline.

NOTE: All review records used in these tests are clearly labeled synthetic TEST FIXTURES
running in memory or pytest `tmp_path` and are NEVER written to the restricted corpus.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import (
    import_w07_contributor_reviews_v1 as w07_a3_import,
    report_w07_review_collection_progress as w07_a3_progress,
    run_w07_data_rag_readiness_audit as w07_0_audit,
    run_w07_review_corpus_feasibility as w07_a1,
    validate_w07_review_corpus_v1 as w07_a2,
    verify_w06_scientific_closure as w06_closure,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _make_raw_form_response(
    *,
    timestamp: str = "2026-11-02 10:15:00",
    poi_selection: str = "Lăng Chủ tịch Hồ Chí Minh",
    rating: str = "5",
    review_text: str = (
        "TEST_FIXTURE_ONLY: Khu vực quảng trường Ba Đình rộng rãi, sạch sẽ, "
        "trải nghiệm tham quan buổi sáng rất trang nghiêm."
    ),
    visit_period: str = "2025-10",
    consent: str = w07_a3_import.CONSENT_CHECKBOX_OPTION_LABEL,
    **extra_cols: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "Timestamp": timestamp,
        "1. Chọn địa điểm (POI) bạn đã trực tiếp đến trải nghiệm": poi_selection,
        "2. Điểm đánh giá tổng thể (1 = Rất tệ, 5 = Rất tốt)": rating,
        "3. Nội dung đánh giá thực tế của riêng bạn": review_text,
        "4. Thời điểm ghé thăm (Không bắt buộc)": visit_period,
        "5. Cam kết tính xác thực và đồng thuận nghiên cứu học thuật": consent,
    }
    row.update(extra_cols)
    return row


def test_w07_a3_three_forms_20_pois_and_no_poi_outside_manifest() -> None:
    """Test 1 & 3: Three city forms × 20 POIs each, all 60 derived strictly from the A2 manifest."""
    res = w07_a3_import.verify_form_definition_artifacts(REPO_ROOT)
    assert res["status"] == "PASS"
    assert res["city_form_poi_counts"] == {"Hà Nội": 20, "Đà Nẵng": 20, "Hạ Long": 20}
    assert (
        res["form_definition_internal_sha256"]
        == "9c17cfc51c41295c8338b40544324454a36a7276bb2339edd3a0b59c88c6de8a"
    )

    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    manifest_ids = {p["poi_id"] for p in manifest["pois"]}
    form_def = json.loads(
        (REPO_ROOT / w07_a3_import.FORM_DEFINITION_JSON_RELPATH).read_text(
            encoding="utf-8"
        )
    )

    seen_form_poi_ids: set[str] = set()
    assert len(form_def["city_forms"]) == 3
    for cf in form_def["city_forms"]:
        assert cf["poi_count"] == 20
        assert len(cf["pois"]) == 20
        assert cf["manifest_sha_binding"] == w07_a3_import.EXPECTED_A2_MANIFEST_INTERNAL_SHA256
        for p in cf["pois"]:
            assert p["poi_id"] in manifest_ids
            assert p["city"] == cf["city"]
            seen_form_poi_ids.add(p["poi_id"])

    assert len(seen_form_poi_ids) == 60
    assert seen_form_poi_ids == manifest_ids


def test_w07_a3_manifest_hash_binding_fails_closed_on_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 2: If the W07-A2 manifest SHA differs from expected, verify_and_load_a2_manifest fails closed."""
    monkeypatch.setattr(
        w07_a3_import,
        "EXPECTED_A2_MANIFEST_INTERNAL_SHA256",
        "0" * 64,
    )
    with pytest.raises(w07_a3_import.ManifestAuthorityError, match="FAIL CLOSED"):
        w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)


def test_w07_a3_response_to_canonical_row_conversion_and_consent_required() -> None:
    """Test 4, 5, 6, 7: Raw form response -> canonical row, required consent, deterministic consent_record_id & review_id."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)

    raw_valid = _make_raw_form_response()
    row1, stripped1 = w07_a3_import.convert_raw_form_row_to_candidate_review(
        raw_valid,
        city_name="Hà Nội",
        manifest_payload=manifest,
    )
    row2, _ = w07_a3_import.convert_raw_form_row_to_candidate_review(
        raw_valid,
        city_name="Hà Nội",
        manifest_payload=manifest,
    )

    assert stripped1 == []
    assert row1["poi_id"] == "698ee756-6062-5f47-955b-bdf458682e57"
    assert row1["upstream_place_id"] == "osm:way/37625751"
    assert row1["city"] == "Hà Nội"
    assert row1["rating"] == 5.0
    assert row1["rating_scale_max"] == 5
    assert row1["provenance"] == "FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1"
    assert row1["license_or_usage_class"] == "OWNER_FIRST_PARTY_CONSENT"
    assert row1["mapping_method"] == "EXACT_PREBOUND_CANONICAL_POI"
    assert row1["mapping_confidence"] == 1.0
    assert row1["consent_record_id"] is not None
    assert row1["consent_record_id"].startswith("consent_w07_v1_")
    assert row1["review_id"].startswith("w07_rev_hn_")

    # Deterministic IDs across repeated calls
    assert row1["consent_record_id"] == row2["consent_record_id"]
    assert row1["review_id"] == row2["review_id"]

    # Missing/unconfirmed consent -> consent_record_id is None -> rejected by A2 validator
    raw_no_consent = _make_raw_form_response(
        timestamp="2026-11-02 10:20:00",
        consent="",
        review_text="TEST_FIXTURE_ONLY: Đánh giá không tích ô đồng thuận bắt buộc.",
    )
    row_no_consent, _ = w07_a3_import.convert_raw_form_row_to_candidate_review(
        raw_no_consent,
        city_name="Hà Nội",
        manifest_payload=manifest,
    )
    assert row_no_consent["consent_record_id"] is None

    val_report = w07_a2.validate_review_rows([row1, row_no_consent], manifest)
    assert val_report["accepted_review_count"] == 1
    assert val_report["rejected_review_count"] == 1
    assert (
        "REJECT_MISSING_CONSENT_RECORD"
        in val_report["rejected_rows"][0]["reasons"]
    )


def test_w07_a3_raw_identity_removal_and_pii_quarantine_and_synthetic_rejection() -> None:
    """Test 9, 10, 11: Raw identity columns stripped; PII in review_text quarantined; synthetic source rejected."""
    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)

    # Raw export with organization-forced identity columns
    raw_with_identity = _make_raw_form_response(
        **{
            "Email Address": "student123@university.edu.vn",
            "Họ và tên": "Nguyễn Văn A",
            "Số điện thoại": "0912345678",
            "MSSV": "20221234",
            "Facebook": "fb.com/nguyenvana",
        }
    )
    converted, stripped_cols = w07_a3_import.convert_raw_form_row_to_candidate_review(
        raw_with_identity,
        city_name="Hà Nội",
        manifest_payload=manifest,
    )
    assert set(stripped_cols) == {
        "Email Address",
        "Họ và tên",
        "Số điện thoại",
        "MSSV",
        "Facebook",
    }
    serialized = json.dumps(converted, ensure_ascii=False)
    assert "student123@university.edu.vn" not in serialized
    assert "Nguyễn Văn A" not in serialized
    assert "0912345678" not in serialized
    assert "20221234" not in serialized

    # PII inside review_text must NOT be auto-redacted and must be quarantined as QUARANTINE_PII_REVIEW_TEXT
    raw_pii_text = _make_raw_form_response(
        timestamp="2026-11-02 11:00:00",
        review_text=(
            "TEST_FIXTURE_ONLY: Địa điểm rất đẹp, gọi cho tôi số 0988 111 222 "
            "hoặc gửi thư tới contact_me@example.org nhé."
        ),
    )
    converted_pii, _ = w07_a3_import.convert_raw_form_row_to_candidate_review(
        raw_pii_text,
        city_name="Hà Nội",
        manifest_payload=manifest,
    )
    # Verbatim text preserved (no silent rewriting)
    assert "0988 111 222" in converted_pii["review_text"]
    assert "contact_me@example.org" in converted_pii["review_text"]

    # Synthetic / LLM source rejected
    raw_synth = _make_raw_form_response(
        timestamp="2026-11-02 11:05:00",
        review_text="TEST_FIXTURE_ONLY: Đánh giá thử nghiệm kiểm tra bộ lọc nguồn tổng hợp AI.",
        source="chatgpt_synthetic_generator",
    )
    converted_synth, _ = w07_a3_import.convert_raw_form_row_to_candidate_review(
        raw_synth,
        city_name="Hà Nội",
        manifest_payload=manifest,
    )

    val_report = w07_a2.validate_review_rows(
        [converted, converted_pii, converted_synth],
        manifest,
    )
    assert val_report["accepted_review_count"] == 1
    assert val_report["rejected_review_count"] == 2
    assert val_report["quarantined_pii_count"] == 1
    reasons_flat = {
        r for row_rej in val_report["rejected_rows"] for r in row_rej["reasons"]
    }
    assert "QUARANTINE_PII_REVIEW_TEXT" in reasons_flat
    assert "SYNTHETIC_OR_LLM_OR_DISALLOWED_SOURCE" in reasons_flat


def test_w07_a3_importer_idempotency_on_repeated_csv_imports(
    tmp_path: Path,
) -> None:
    """Test 8: Importing the same CSV export twice produces identical JSONL with zero duplicates."""
    csv_path = tmp_path / "hanoi_responses.csv"
    output_jsonl = tmp_path / "w07_canonical_reviews_v1.jsonl"

    rows_to_write = [
        _make_raw_form_response(
            timestamp="2026-11-02 09:00:00",
            poi_selection="Lăng Chủ tịch Hồ Chí Minh",
            rating="5",
            review_text=(
                "TEST_FIXTURE_ONLY: Không gian quảng trường Ba Đình trang nghiêm, "
                "lối đi bộ sạch sẽ và hướng dẫn rất rõ ràng."
            ),
            **{"Email Address": "hidden_owner@example.com"},
        ),
        _make_raw_form_response(
            timestamp="2026-11-02 09:10:00",
            poi_selection="Hoàng thành Thăng Long",
            rating="4",
            review_text=(
                "TEST_FIXTURE_ONLY: Khu di tích lịch sử rộng lớn, nhiều hiện vật khảo cổ "
                "giá trị và nhiều cây xanh mát mẻ."
            ),
            **{"Email Address": "hidden_owner2@example.com"},
        ),
        # Also include a PII-containing row to verify it is excluded from output_jsonl
        _make_raw_form_response(
            timestamp="2026-11-02 09:20:00",
            poi_selection="Nhà tù Hỏa Lò",
            rating="5",
            review_text=(
                "TEST_FIXTURE_ONLY: Thuyết minh tự động rất hay, liên hệ 0909123456 để đặt đoàn."
            ),
            **{"Email Address": "hidden_owner3@example.com"},
        ),
    ]

    fieldnames = list(rows_to_write[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_to_write)

    first_run = w07_a3_import.import_contributor_csv_files(
        [(csv_path, "Hà Nội")],
        output_jsonl_path=output_jsonl,
        repo_root=REPO_ROOT,
    )
    assert first_run["accepted_review_count"] == 2
    assert first_run["quarantined_pii_count"] == 1
    assert first_run["idempotent_duplicate_rows_skipped"] == 0
    assert first_run["stripped_identity_columns"] == ["Email Address"]

    first_content = output_jsonl.read_text(encoding="utf-8")
    assert "hidden_owner" not in first_content
    assert "0909123456" not in first_content

    # Second import of the exact same CSV
    second_run = w07_a3_import.import_contributor_csv_files(
        [(csv_path, "Hà Nội")],
        output_jsonl_path=output_jsonl,
        repo_root=REPO_ROOT,
    )
    assert second_run["accepted_review_count"] == 2
    assert second_run["idempotent_duplicate_rows_skipped"] == 2
    assert second_run["output_jsonl_lf_sha256"] == first_run["output_jsonl_lf_sha256"]
    assert output_jsonl.read_text(encoding="utf-8") == first_content


def test_w07_a3_progress_tracker_math_and_pilot_vs_scientific_boundaries() -> None:
    """Test 12, 13, 14: Progress tracker math, pilot gate true/false boundaries, and separation from scientific minimum."""
    # Verify committed baseline progress artifact (0 reviews)
    baseline_verify = w07_a3_progress.verify_collection_progress_artifact(REPO_ROOT)
    assert baseline_verify["status"] == "PASS"
    assert (
        baseline_verify["progress_internal_sha256"]
        == "a7eb47e50735a6f184f4ae717976b7a8bf7d1258a6d4763031c62fd691d38e70"
    )
    assert baseline_verify["accepted_review_count"] == 0
    assert baseline_verify["remaining_reviews_to_300"] == 300
    assert baseline_verify["COLLECTION_PIPELINE_PILOT_READY"] is False
    assert baseline_verify["CORPUS_SCIENTIFIC_MINIMUM_READY"] is False

    manifest = w07_a3_import.verify_and_load_a2_manifest(REPO_ROOT)
    pois_by_city = {
        city: [p for p in manifest["pois"] if p["city"] == city]
        for city in ("Hà Nội", "Đà Nẵng", "Hạ Long")
    }

    # Build a 30-review pilot fixture: 5 POIs per city × 2 reviews per POI = 10 reviews/city, 15 distinct POIs, 30 reviews total
    pilot_rows: list[dict[str, Any]] = []
    for city, city_pois in pois_by_city.items():
        for p_idx in range(5):
            poi = city_pois[p_idx]
            for r_idx in (1, 2):
                raw = _make_raw_form_response(
                    timestamp=f"2026-11-02 12:{p_idx:02d}:{r_idx:02d}",
                    poi_selection=poi["name"],
                    rating=str(((p_idx + r_idx) % 5) + 1),
                    review_text=(
                        f"TEST_FIXTURE_ONLY: Đánh giá thực tế lần {r_idx} cho địa điểm "
                        f"{poi['name']} tại {city} với không gian rất ấn tượng và đáng nhớ."
                    ),
                )
                cand, _ = w07_a3_import.convert_raw_form_row_to_candidate_review(
                    raw,
                    city_name=city,
                    manifest_payload=manifest,
                )
                pilot_rows.append(cand)

    # 1. With 29 reviews (missing 1 review in Hạ Long -> 9 in Hạ Long), pilot gate must be FALSE
    report_29 = w07_a3_progress.build_collection_progress_report(
        pilot_rows[:-1],
        manifest,
    )
    assert report_29["summary_counts"]["accepted_review_count"] == 29
    assert report_29["pilot_gate_evaluation"]["COLLECTION_PIPELINE_PILOT_READY"] is False
    assert (
        report_29["scientific_minimum_evaluation"]["CORPUS_SCIENTIFIC_MINIMUM_READY"]
        is False
    )

    # 2. With 29 valid reviews + 1 PII-quarantined review (30 candidate rows), pilot gate must still be FALSE
    pii_cand, _ = w07_a3_import.convert_raw_form_row_to_candidate_review(
        _make_raw_form_response(
            timestamp="2026-11-02 15:00:00",
            poi_selection=pois_by_city["Hạ Long"][4]["name"],
            review_text="TEST_FIXTURE_ONLY: Liên hệ số điện thoại 0912345678 tại điểm tham quan.",
        ),
        city_name="Hạ Long",
        manifest_payload=manifest,
    )
    report_29_plus_pii = w07_a3_progress.build_collection_progress_report(
        pilot_rows[:-1] + [pii_cand],
        manifest,
    )
    assert report_29_plus_pii["summary_counts"]["accepted_review_count"] == 29
    assert report_29_plus_pii["summary_counts"]["quarantined_pii_count"] == 1
    assert (
        report_29_plus_pii["pilot_gate_evaluation"]["COLLECTION_PIPELINE_PILOT_READY"]
        is False
    )

    # 3. With all 30 valid reviews (10/city, 15 distinct POIs), COLLECTION_PIPELINE_PILOT_READY is TRUE,
    #    while CORPUS_SCIENTIFIC_MINIMUM_READY remains FALSE!
    report_30 = w07_a3_progress.build_collection_progress_report(
        pilot_rows,
        manifest,
    )
    assert report_30["summary_counts"]["accepted_review_count"] == 30
    assert report_30["summary_counts"]["covered_poi_count"] == 15
    assert report_30["summary_counts"]["pois_with_0_reviews_count"] == 45
    assert report_30["summary_counts"]["pois_with_1_to_4_reviews_count"] == 15
    assert report_30["summary_counts"]["pois_with_5_or_more_reviews_count"] == 0
    assert report_30["summary_counts"]["remaining_reviews_to_300"] == 270
    assert report_30["reviews_by_city"] == {"Hà Nội": 10, "Đà Nẵng": 10, "Hạ Long": 10}
    assert report_30["pilot_gate_evaluation"]["COLLECTION_PIPELINE_PILOT_READY"] is True
    assert (
        report_30["scientific_minimum_evaluation"]["CORPUS_SCIENTIFIC_MINIMUM_READY"]
        is False
    )
    # Verify raw review_text never leaks into the progress report
    assert "TEST_FIXTURE_ONLY" not in json.dumps(report_30, ensure_ascii=False)


def test_w07_a3_preserves_w06_w07_0_w07_a1_and_w07_a2_immutability() -> None:
    """Test 15: Prior W06, W07-0, W07-A1, and W07-A2 artifacts and hashes remain unchanged."""
    shas = w07_a2.verify_prior_gates_immutability(REPO_ROOT)
    assert (
        shas["w06_closure_internal_sha256"]
        == w07_a2.EXPECTED_W06_CLOSURE_INTERNAL_SHA256
    )
    assert shas["w07_0_audit_internal_sha256"] == w07_a2.EXPECTED_W07_0_INTERNAL_SHA256
    assert (
        shas["w07_a1_feasibility_internal_sha256"]
        == w07_a2.EXPECTED_W07_A1_INTERNAL_SHA256
    )

    assert (
        w06_closure.compute_closure_internal_sha256(
            w06_closure.build_closure_payload()
        )
        == w07_a2.EXPECTED_W06_CLOSURE_INTERNAL_SHA256
    )
    assert w07_0_audit.verify_w07_audit_artifacts(REPO_ROOT)["status"] == "PASS"
    assert w07_a1.verify_w07_a1_artifacts(REPO_ROOT)["status"] == "PASS"

    a2_res = w07_a2.verify_w07_a2_artifacts(REPO_ROOT)
    assert a2_res["status"] == "PASS"
    assert (
        a2_res["manifest_internal_sha256"]
        == w07_a3_import.EXPECTED_A2_MANIFEST_INTERNAL_SHA256
    )
    assert (
        a2_res["manifest_file_lf_sha256"]
        == w07_a3_import.EXPECTED_A2_MANIFEST_FILE_LF_SHA256
    )
    assert (
        a2_res["intake_status_internal_sha256"]
        == w07_a3_import.EXPECTED_A2_INTAKE_STATUS_INTERNAL_SHA256
    )
    assert (
        a2_res["contributor_spec_md_lf_sha256"]
        == w07_a3_import.EXPECTED_A2_CONTRIBUTOR_SPEC_LF_SHA256
    )
