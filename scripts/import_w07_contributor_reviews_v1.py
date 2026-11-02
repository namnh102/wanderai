#!/usr/bin/env python3
"""W07-A3 Contributor Review Collection Form Generator + Deterministic Importer (v1).

Responsibilities:
1. Programmatically generate and verify the three city-specific Google Forms definitions
   (`data/evaluation/w07/w07_contributor_collection_form_definition_v1.json`) and optional
   Google Apps Script form creator (`tools/w07/create_w07_contributor_forms.gs`) directly
   from the frozen W07-A2 manifest (`data/evaluation/w07/w07_review_target_60_pois_v1.json`).
   Fails closed if the W07-A2 manifest SHA256 does not equal
   `b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b`.
2. Deterministically import raw Google Forms CSV exports from
   `data/restricted/w07_reviews/raw_forms/` (or specified CSV paths) into
   `data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl`:
   - Strips any accidental or organization-forced contributor identity columns
     before constructing records.
   - Resolves human-readable `<POI name>` selections to canonical `poi_id` bound to the
     city form's 20 manifest POIs.
   - Requires explicit affirmative consent checkbox per review.
   - Deterministically generates non-reversible `consent_record_id` and `review_id`
     values so repeated imports of unchanged CSV exports are strictly idempotent.
   - Preserves `review_text` verbatim (never rewrites or redacts) and delegates validation
     to the W07-A2 validator (`scripts/validate_w07_review_corpus_v1.py`), quarantining
     any PII in `review_text` (`QUARANTINE_PII_REVIEW_TEXT`) and excluding it from the
     accepted scientific corpus.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_w07_review_corpus_v1 as w07_a2  # noqa: E402

FORM_DEFINITION_JSON_RELPATH = (
    "data/evaluation/w07/w07_contributor_collection_form_definition_v1.json"
)
APPS_SCRIPT_RELPATH = "tools/w07/create_w07_contributor_forms.gs"
RAW_FORMS_DIR_RELPATH = "data/restricted/w07_reviews/raw_forms"
CANONICAL_JSONL_RELPATH = w07_a2.RESTRICTED_JSONL_RELPATH

AUTHORITATIVE_DEVELOP_BASE_SHA = "82d2a0567f98c5e2ca368d2a2760e1029b709a56"
PREVIOUS_GATE = (
    "W07-A2-CANONICAL-REVIEW-CORPUS-INTAKE-POSTMERGE-CHATGPT-AUDIT = PASS"
)
NEXT_GATE = "W07-A3-CONTRIBUTOR-COLLECTION-LAUNCH-CHATGPT-AUDIT"

EXPECTED_A2_MANIFEST_INTERNAL_SHA256 = (
    "b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b"
)
EXPECTED_A2_MANIFEST_FILE_LF_SHA256 = (
    "3a065165d038f300f5dc422180fcaf3cef265ac1a100ea8e841daaba1a82d5d4"
)
EXPECTED_A2_INTAKE_STATUS_INTERNAL_SHA256 = (
    "4dd13bd7ad51ddfc3f501a11935f109928b2db8e9de52849da97d1a691ad2624"
)
EXPECTED_A2_INTAKE_STATUS_FILE_LF_SHA256 = (
    "69acd3bd814aa9ae166b2d715803ee227e47f3dd91aba05a4bd40dcffdee67ce"
)
EXPECTED_A2_CONTRIBUTOR_SPEC_LF_SHA256 = (
    "32bf0290f817fcab1d15a46e3c37e32902d7d617654b7a4eafc5198153fa4392"
)

FORM_PACKAGE_VERSION = "1.0.0"

CITY_FORM_CONFIGS: tuple[dict[str, str], ...] = (
    {
        "form_id": "w07_form_hanoi_v1",
        "city": "Hà Nội",
        "city_code": "hn",
        "destination_slug": "ha-noi",
        "form_title_vi": "[GoMate W07] Đánh giá địa điểm du lịch thực tế — Hà Nội (20 POI)",
        "form_title_en": "[GoMate W07] Authentic Visited Place Review — Hà Nội (20 POIs)",
        "raw_csv_filename": "hanoi_responses.csv",
    },
    {
        "form_id": "w07_form_danang_v1",
        "city": "Đà Nẵng",
        "city_code": "dn",
        "destination_slug": "da-nang",
        "form_title_vi": "[GoMate W07] Đánh giá địa điểm du lịch thực tế — Đà Nẵng (20 POI)",
        "form_title_en": "[GoMate W07] Authentic Visited Place Review — Đà Nẵng (20 POIs)",
        "raw_csv_filename": "danang_responses.csv",
    },
    {
        "form_id": "w07_form_halong_v1",
        "city": "Hạ Long",
        "city_code": "hl",
        "destination_slug": "ha-long",
        "form_title_vi": "[GoMate W07] Đánh giá địa điểm du lịch thực tế — Hạ Long (20 POI)",
        "form_title_en": "[GoMate W07] Authentic Visited Place Review — Hạ Long (20 POIs)",
        "raw_csv_filename": "halong_responses.csv",
    },
)

SEVEN_MANDATORY_CONSENT_AFFIRMATIONS: tuple[str, ...] = (
    "1. Tôi đã trực tiếp đến hoặc trực tiếp trải nghiệm địa điểm (POI) được chọn / I personally visited or directly experienced the selected POI.",
    "2. Nội dung đánh giá là do chính tôi tự viết / The review is my own original writing.",
    "3. Không sao chép từ Google Maps, Tripadvisor, Booking, Agoda, Foody hoặc người đánh giá khác / Not copied from Google Maps, Tripadvisor, Booking, Agoda, Foody, or another reviewer.",
    "4. Không sử dụng ChatGPT, Gemini, Claude hoặc công cụ AI khác để viết hay diễn đạt lại / Not written or rephrased by ChatGPT, Gemini, Claude, or another AI.",
    "5. Việc gửi đánh giá là hoàn toàn tự nguyện / Submission is completely voluntary.",
    "6. Đồng ý cho phép sử dụng ẩn danh phục vụ nghiên cứu, đánh giá thực nghiệm và trình diễn học thuật phi thương mại / Permission granted for anonymized academic/non-commercial research, evaluation, and demo use.",
    "7. Không đưa thông tin cá nhân nhạy cảm (số điện thoại, email, tên thật, tài khoản cá nhân) vào nội dung đánh giá / No sensitive personal information is included in the review text.",
)

CONSENT_CHECKBOX_OPTION_LABEL = (
    "Tôi xác nhận đầy đủ 7 cam kết trên (đã trực tiếp đến địa điểm, tự viết 100%, "
    "không sao chép, không dùng AI, tự nguyện cấp quyền nghiên cứu học thuật ẩn danh) / "
    "I affirm all 7 statements above."
)

IDENTITY_COLUMN_PATTERNS: tuple[str, ...] = (
    "email",
    "e-mail",
    "địa chỉ email",
    "real_name",
    "full_name",
    "author_name",
    "contributor_real_name",
    "họ và tên",
    "họ tên",
    "tên của bạn",
    "name",
    "phone",
    "phone_number",
    "số điện thoại",
    "điện thoại",
    "social",
    "account_handle",
    "facebook",
    "zalo",
    "instagram",
    "tiktok",
    "username",
    "home_address",
    "địa chỉ nhà",
    "student_id",
    "mssv",
    "mã sinh viên",
    "national_id",
    "cccd",
    "cmnd",
)

VISIT_PERIOD_RE = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2]|Q[1-4])$")
UUID_SUBSTRING_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


class ManifestAuthorityError(ValueError):
    """Raised when the W07-A2 manifest hash or POI authority check fails."""


def verify_and_load_a2_manifest(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify prior gates + W07-A2 manifest SHA256 fail-closed and return the manifest payload."""
    w07_a2.verify_prior_gates_immutability(repo_root)

    manifest_path = repo_root / w07_a2.MANIFEST_60_JSON_RELPATH
    intake_path = repo_root / w07_a2.INTAKE_STATUS_JSON_RELPATH
    spec_path = repo_root / w07_a2.CONTRIBUTOR_SPEC_MD_RELPATH

    if not manifest_path.exists():
        raise ManifestAuthorityError(f"Missing W07-A2 manifest: {manifest_path}")

    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    computed_internal_sha = w07_a2.compute_internal_sha256(
        manifest_payload, "manifest_sha256"
    )
    recorded_internal_sha = manifest_payload.get("manifest_sha256")
    file_lf_sha = w07_a2.compute_lf_normalized_sha256(manifest_path)

    if (
        computed_internal_sha != EXPECTED_A2_MANIFEST_INTERNAL_SHA256
        or recorded_internal_sha != EXPECTED_A2_MANIFEST_INTERNAL_SHA256
    ):
        raise ManifestAuthorityError(
            "FAIL CLOSED: W07-A2 manifest internal SHA256 mismatch: "
            f"computed={computed_internal_sha}, recorded={recorded_internal_sha}, "
            f"expected={EXPECTED_A2_MANIFEST_INTERNAL_SHA256}"
        )
    if file_lf_sha != EXPECTED_A2_MANIFEST_FILE_LF_SHA256:
        raise ManifestAuthorityError(
            "FAIL CLOSED: W07-A2 manifest file LF SHA256 mismatch: "
            f"got={file_lf_sha}, expected={EXPECTED_A2_MANIFEST_FILE_LF_SHA256}"
        )

    if intake_path.exists():
        intake_payload = json.loads(intake_path.read_text(encoding="utf-8"))
        intake_internal = w07_a2.compute_internal_sha256(
            intake_payload, "artifact_sha256"
        )
        intake_lf = w07_a2.compute_lf_normalized_sha256(intake_path)
        if (
            intake_internal != EXPECTED_A2_INTAKE_STATUS_INTERNAL_SHA256
            or intake_lf != EXPECTED_A2_INTAKE_STATUS_FILE_LF_SHA256
        ):
            raise ManifestAuthorityError(
                f"FAIL CLOSED: W07-A2 intake status SHA mismatch: internal={intake_internal}, lf={intake_lf}"
            )

    if spec_path.exists():
        spec_lf = w07_a2.compute_lf_normalized_sha256(spec_path)
        if spec_lf != EXPECTED_A2_CONTRIBUTOR_SPEC_LF_SHA256:
            raise ManifestAuthorityError(
                f"FAIL CLOSED: W07-A2 contributor spec LF SHA mismatch: got={spec_lf}"
            )

    pois = manifest_payload.get("pois", [])
    if len(pois) != 60 or len({p["poi_id"] for p in pois}) != 60:
        raise ManifestAuthorityError("FAIL CLOSED: W07-A2 manifest must contain 60 unique POIs.")

    return manifest_payload


def build_form_definition_payload(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Programmatically construct the three city-specific Google Forms definitions from the frozen A2 manifest."""
    manifest = verify_and_load_a2_manifest(repo_root)
    pois = manifest["pois"]

    city_forms: list[dict[str, Any]] = []
    for cfg in CITY_FORM_CONFIGS:
        city_name = cfg["city"]
        city_pois_raw = [p for p in pois if p["city"] == city_name]
        if len(city_pois_raw) != 20:
            raise ManifestAuthorityError(
                f"Expected exactly 20 POIs for {city_name}, found {len(city_pois_raw)}"
            )

        form_pois: list[dict[str, Any]] = []
        dropdown_options: list[dict[str, str]] = []
        for idx, p in enumerate(city_pois_raw, start=1):
            human_label = p["name"]
            disambiguated_label = f"{p['name']} [{p['category']}] — {p['poi_id']}"
            form_pois.append(
                {
                    "city_item_index": idx,
                    "selection_rank": p["selection_rank"],
                    "poi_id": p["poi_id"],
                    "name": p["name"],
                    "city": p["city"],
                    "destination_slug": p["destination_slug"],
                    "category": p["category"],
                    "category_group": p["category_group"],
                    "osm_id": p["osm_id"],
                    "overture_id": p["overture_id"],
                    "source_ids": p["source_ids"],
                    "dropdown_display_label": human_label,
                    "dropdown_disambiguated_label": disambiguated_label,
                }
            )
            dropdown_options.append(
                {
                    "display_label": human_label,
                    "canonical_poi_id": p["poi_id"],
                    "osm_id": p["osm_id"],
                    "category": p["category"],
                }
            )

        # Verify all 20 human-readable POI names within this city form are unique
        if len({fp["dropdown_display_label"] for fp in form_pois}) != 20:
            raise ManifestAuthorityError(
                f"Duplicate POI display names detected inside city form {city_name}"
            )

        questions: list[dict[str, Any]] = [
            {
                "question_id": "poi_selection",
                "title_vi": "1. Chọn địa điểm (POI) bạn đã trực tiếp đến trải nghiệm",
                "title_en": "1. Select the place (POI) you personally visited",
                "help_text_vi": (
                    f"Chỉ chọn 1 địa điểm tại {city_name} mà bạn đã thực sự ghé thăm. "
                    "Mỗi lần gửi biểu mẫu tương ứng với 1 đánh giá cho 1 địa điểm."
                ),
                "field_type": "DROPDOWN",
                "required": True,
                "binds_to_schema_field": "poi_id",
                "options": dropdown_options,
            },
            {
                "question_id": "rating",
                "title_vi": "2. Điểm đánh giá tổng thể (1 = Rất tệ, 5 = Rất tốt)",
                "title_en": "2. Overall rating (1 = Poor, 5 = Excellent)",
                "help_text_vi": "Chọn số nguyên từ 1 đến 5 sao.",
                "field_type": "LINEAR_SCALE_INTEGER",
                "required": True,
                "scale_min": 1,
                "scale_max": 5,
                "allowed_values": [1, 2, 3, 4, 5],
                "binds_to_schema_field": "rating",
            },
            {
                "question_id": "review_text",
                "title_vi": "3. Nội dung đánh giá thực tế của riêng bạn",
                "title_en": "3. Your own authentic review",
                "help_text_vi": (
                    "Hãy viết cảm nhận cụ thể của chính bạn về không gian, dịch vụ, trải nghiệm thực tế "
                    "(khuyến nghị tối thiểu 1–3 câu, >= 20 ký tự và >= 5 từ). Không sao chép từ mạng, "
                    "không dùng AI, và KHÔNG ghi số điện thoại hay email vào nội dung."
                ),
                "field_type": "PARAGRAPH_TEXT",
                "required": True,
                "binds_to_schema_field": "review_text",
            },
            {
                "question_id": "visit_period",
                "title_vi": "4. Thời điểm ghé thăm (Không bắt buộc)",
                "title_en": "4. Visit period (Optional)",
                "help_text_vi": "Định dạng gợi ý: YYYY-MM (ví dụ: 2025-08) hoặc YYYY-Q1..Q4 (ví dụ: 2025-Q3).",
                "field_type": "SHORT_TEXT",
                "required": False,
                "suggested_formats": ["YYYY-MM", "YYYY-Q1", "YYYY-Q2", "YYYY-Q3", "YYYY-Q4"],
                "binds_to_schema_field": "visit_period",
            },
            {
                "question_id": "consent",
                "title_vi": "5. Cam kết tính xác thực và đồng thuận nghiên cứu học thuật",
                "title_en": "5. Authenticity affirmation and academic research consent",
                "help_text_vi": w07_a2.CONSENT_TEXT_VI,
                "help_text_en": w07_a2.CONSENT_TEXT_EN,
                "field_type": "CHECKBOX_REQUIRED",
                "required": True,
                "checkbox_option_label": CONSENT_CHECKBOX_OPTION_LABEL,
                "binds_to_schema_field": "consent_record_id",
            },
        ]

        city_forms.append(
            {
                "form_id": cfg["form_id"],
                "form_version": FORM_PACKAGE_VERSION,
                "city": city_name,
                "city_code": cfg["city_code"],
                "destination_slug": cfg["destination_slug"],
                "form_title_vi": cfg["form_title_vi"],
                "form_title_en": cfg["form_title_en"],
                "raw_csv_default_relpath": f"{RAW_FORMS_DIR_RELPATH}/{cfg['raw_csv_filename']}",
                "poi_count": len(form_pois),
                "pois": form_pois,
                "question_definitions": questions,
                "consent_text": {
                    "vi": w07_a2.CONSENT_TEXT_VI,
                    "en": w07_a2.CONSENT_TEXT_EN,
                    "seven_mandatory_affirmations": list(SEVEN_MANDATORY_CONSENT_AFFIRMATIONS),
                    "required_checkbox_label": CONSENT_CHECKBOX_OPTION_LABEL,
                },
                "response_schema": {
                    "one_response_equals": "ONE_REVIEW_OF_ONE_POI",
                    "allow_multiple_submissions_per_contributor": True,
                    "csv_columns_expected": [
                        "Timestamp",
                        "1. Chọn địa điểm (POI) bạn đã trực tiếp đến trải nghiệm",
                        "2. Điểm đánh giá tổng thể (1 = Rất tệ, 5 = Rất tốt)",
                        "3. Nội dung đánh giá thực tế của riêng bạn",
                        "4. Thời điểm ghé thăm (Không bắt buộc)",
                        "5. Cam kết tính xác thực và đồng thuận nghiên cứu học thuật",
                    ],
                    "programmatic_column_aliases": {
                        "timestamp": ["Timestamp", "Dấu thời gian", "timestamp", "created_at"],
                        "poi_selection": [
                            "1. Chọn địa điểm (POI) bạn đã trực tiếp đến trải nghiệm",
                            "poi_selection",
                            "poi_id",
                            "poi_name",
                            "Địa điểm (POI)",
                        ],
                        "rating": [
                            "2. Điểm đánh giá tổng thể (1 = Rất tệ, 5 = Rất tốt)",
                            "rating",
                            "Điểm đánh giá (1-5)",
                        ],
                        "review_text": [
                            "3. Nội dung đánh giá thực tế của riêng bạn",
                            "review_text",
                            "Nội dung đánh giá",
                        ],
                        "visit_period": [
                            "4. Thời điểm ghé thăm (Không bắt buộc)",
                            "visit_period",
                            "Thời điểm ghé thăm",
                        ],
                        "consent": [
                            "5. Cam kết tính xác thực và đồng thuận nghiên cứu học thuật",
                            "consent",
                            "consent_confirmed",
                            "Đồng ý cam kết học thuật",
                        ],
                    },
                },
                "manifest_sha_binding": EXPECTED_A2_MANIFEST_INTERNAL_SHA256,
            }
        )

    payload: dict[str, Any] = {
        "artifact_id": "w07_contributor_collection_form_definition_v1",
        "form_version": FORM_PACKAGE_VERSION,
        "task_id": "W07-A3",
        "authoritative_develop_base_sha": AUTHORITATIVE_DEVELOP_BASE_SHA,
        "previous_gate": PREVIOUS_GATE,
        "next_gate": NEXT_GATE,
        "manifest_sha_binding": {
            "manifest_path": w07_a2.MANIFEST_60_JSON_RELPATH,
            "manifest_internal_sha256": EXPECTED_A2_MANIFEST_INTERNAL_SHA256,
            "manifest_file_lf_sha256": EXPECTED_A2_MANIFEST_FILE_LF_SHA256,
            "fail_closed_on_mismatch": True,
        },
        "collection_surface": {
            "primary_platform": "Google Forms",
            "total_city_forms": 3,
            "pois_per_city_form": 20,
            "total_canonical_pois": 60,
            "response_granularity": "ONE_REVIEW_OF_ONE_POI_PER_FORM_SUBMISSION",
            "repeat_submissions_allowed_for_other_visited_pois": True,
        },
        "privacy_first_configuration": {
            "email_collection": "OFF",
            "require_google_sign_in_limit_1_response": False,
            "prohibited_identity_fields": [
                "real_name",
                "email",
                "phone",
                "social_account",
                "exact_home_address",
                "student_id",
                "national_id",
            ],
            "organizational_forced_identity_policy": (
                "If organizational Google settings force email/name collection, raw CSV exports "
                "remain git-ignored under data/restricted/w07_reviews/raw_forms/ and all identity "
                "columns are stripped by scripts/import_w07_contributor_reviews_v1.py before any "
                "scientific record is constructed or written to w07_canonical_reviews_v1.jsonl."
            ),
        },
        "consent_specification": {
            "consent_required_before_acceptance": True,
            "consent_text_vi": w07_a2.CONSENT_TEXT_VI,
            "consent_text_en": w07_a2.CONSENT_TEXT_EN,
            "seven_mandatory_affirmations": list(SEVEN_MANDATORY_CONSENT_AFFIRMATIONS),
            "checkbox_option_label": CONSENT_CHECKBOX_OPTION_LABEL,
        },
        "city_forms": city_forms,
    }
    payload["artifact_sha256"] = w07_a2.compute_internal_sha256(
        payload, "artifact_sha256"
    )
    return payload


def build_google_apps_script_source(form_def_payload: dict[str, Any]) -> str:
    """Generate the optional Owner-only Google Apps Script (`tools/w07/create_w07_contributor_forms.gs`)."""
    embedded_forms = []
    for cf in form_def_payload["city_forms"]:
        embedded_forms.append(
            {
                "form_id": cf["form_id"],
                "city": cf["city"],
                "title": cf["form_title_vi"],
                "raw_csv_default_relpath": cf["raw_csv_default_relpath"],
                "pois": [p["dropdown_display_label"] for p in cf["pois"]],
            }
        )
    embedded_json = json.dumps(embedded_forms, ensure_ascii=False, indent=2)
    consent_vi = json.dumps(form_def_payload["consent_specification"]["consent_text_vi"], ensure_ascii=False)
    consent_en = json.dumps(form_def_payload["consent_specification"]["consent_text_en"], ensure_ascii=False)
    checkbox_label = json.dumps(
        form_def_payload["consent_specification"]["checkbox_option_label"],
        ensure_ascii=False,
    )

    return f"""/**
 * W07-A3 Optional Owner Utility: Google Forms Generator for GoMate / WanderAI
 *
 * Authority:
 *   Bound to W07-A2 Manifest SHA256: {EXPECTED_A2_MANIFEST_INTERNAL_SHA256}
 *   Form Definition SHA256: {form_def_payload['artifact_sha256']}
 *
 * IMPORTANT:
 *   - Owner utility ONLY. Never executed in CI.
 *   - Does NOT store credentials or call any paid API.
 *   - Creates 3 city-specific Google Forms (Hà Nội, Đà Nẵng, Hạ Long), each containing
 *     exactly 20 canonical POIs rendered as human-readable <POI name>.
 *   - Configures privacy-first settings: Email collection OFF, Limit to 1 response OFF.
 *
 * Usage (in https://script.google.com):
 *   1. Create a new Apps Script project and paste this file into Code.gs.
 *   2. Select `createW07ContributorForms` and click Run.
 *   3. Copy the published Responder URLs from the Execution Log.
 */

const W07_A2_MANIFEST_SHA256 = "{EXPECTED_A2_MANIFEST_INTERNAL_SHA256}";
const W07_FORM_VERSION = "{FORM_PACKAGE_VERSION}";
const W07_CONSENT_TEXT_VI = {consent_vi};
const W07_CONSENT_TEXT_EN = {consent_en};
const W07_CONSENT_CHECKBOX_LABEL = {checkbox_label};

const W07_CITY_FORMS = {embedded_json};

function createW07ContributorForms() {{
  const results = [];
  for (let i = 0; i < W07_CITY_FORMS.length; i++) {{
    const spec = W07_CITY_FORMS[i];
    const form = FormApp.create(spec.title);
    form.setDescription(
      "Khảo sát thu thập đánh giá thực tế phục vụ nghiên cứu học thuật đồ án tốt nghiệp GoMate / WanderAI.\\n\\n" +
      "Mỗi lần gửi biểu mẫu tương ứng với 01 đánh giá cho 01 địa điểm (POI) tại " + spec.city + " mà bạn đã trực tiếp ghé thăm. " +
      "Bạn có thể gửi lại biểu mẫu nhiều lần cho các địa điểm khác mà bạn đã trải nghiệm.\\n\\n" +
      "Quyền riêng tư: Biểu mẫu KHÔNG thu thập họ tên, email, số điện thoại hay tài khoản cá nhân.\\n" +
      "Manifest SHA256: " + W07_A2_MANIFEST_SHA256
    );
    form.setCollectEmail(false);
    form.setRequireLogin(false);
    form.setLimitOneResponsePerUser(false);
    form.setShowLinkToRespondAgain(true);

    // 1. Required POI selection dropdown (20 canonical POIs for this city)
    const poiItem = form.addListItem();
    poiItem
      .setTitle("1. Chọn địa điểm (POI) bạn đã trực tiếp đến trải nghiệm")
      .setHelpText("Chỉ chọn 1 địa điểm tại " + spec.city + " mà bạn đã thực sự ghé thăm.")
      .setChoiceValues(spec.pois)
      .setRequired(true);

    // 2. Required integer rating 1-5
    const ratingItem = form.addScaleItem();
    ratingItem
      .setTitle("2. Điểm đánh giá tổng thể (1 = Rất tệ, 5 = Rất tốt)")
      .setBounds(1, 5)
      .setLabels("Rất tệ", "Rất tốt")
      .setRequired(true);

    // 3. Required review_text
    const textItem = form.addParagraphTextItem();
    textItem
      .setTitle("3. Nội dung đánh giá thực tế của riêng bạn")
      .setHelpText(
        "Hãy viết cảm nhận cụ thể của chính bạn (khuyến nghị >= 20 ký tự, >= 5 từ). " +
        "Không sao chép từ Google Maps/Tripadvisor/Booking/Agoda/Foody, không dùng AI, " +
        "và KHÔNG ghi số điện thoại hay email vào nội dung."
      )
      .setRequired(true);

    // 4. Optional visit_period
    const visitItem = form.addTextItem();
    visitItem
      .setTitle("4. Thời điểm ghé thăm (Không bắt buộc)")
      .setHelpText("Định dạng gợi ý: YYYY-MM (ví dụ: 2025-08) hoặc YYYY-Q1..Q4 (ví dụ: 2025-Q3).")
      .setRequired(false);

    // 5. Required consent checkbox
    const consentItem = form.addCheckboxItem();
    consentItem
      .setTitle("5. Cam kết tính xác thực và đồng thuận nghiên cứu học thuật")
      .setHelpText(W07_CONSENT_TEXT_VI + "\\n\\n" + W07_CONSENT_TEXT_EN)
      .setChoices([consentItem.createChoice(W07_CONSENT_CHECKBOX_LABEL)])
      .setRequired(true);

    const summary = {{
      form_id: spec.form_id,
      city: spec.city,
      poi_count: spec.pois.length,
      edit_url: form.getEditUrl(),
      published_url: form.getPublishedUrl(),
      raw_csv_target: spec.raw_csv_default_relpath
    }};
    results.push(summary);
    Logger.log(JSON.stringify(summary, null, 2));
  }}
  return results;
}}
"""


def write_form_definition_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Write the form-definition JSON artifact and the optional Google Apps Script generator."""
    payload = build_form_definition_payload(repo_root)
    form_def_path = repo_root / FORM_DEFINITION_JSON_RELPATH
    form_def_path.parent.mkdir(parents=True, exist_ok=True)
    form_def_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    gs_source = build_google_apps_script_source(payload)
    gs_path = repo_root / APPS_SCRIPT_RELPATH
    gs_path.parent.mkdir(parents=True, exist_ok=True)
    gs_path.write_text(gs_source, encoding="utf-8", newline="\n")

    raw_forms_dir = repo_root / RAW_FORMS_DIR_RELPATH
    raw_forms_dir.mkdir(parents=True, exist_ok=True)

    return verify_form_definition_artifacts(repo_root)


def verify_form_definition_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify the committed W07-A3 form-definition JSON and Apps Script against the frozen A2 manifest."""
    expected_payload = build_form_definition_payload(repo_root)
    form_def_path = repo_root / FORM_DEFINITION_JSON_RELPATH
    gs_path = repo_root / APPS_SCRIPT_RELPATH

    if not form_def_path.exists():
        raise FileNotFoundError(f"Missing form definition artifact: {form_def_path}")
    if not gs_path.exists():
        raise FileNotFoundError(f"Missing Apps Script generator: {gs_path}")

    disk_payload = json.loads(form_def_path.read_text(encoding="utf-8"))
    disk_internal_sha = w07_a2.compute_internal_sha256(disk_payload, "artifact_sha256")
    if disk_internal_sha != disk_payload.get("artifact_sha256"):
        raise ValueError("Form definition internal SHA256 does not match its recorded artifact_sha256.")
    if disk_internal_sha != expected_payload["artifact_sha256"]:
        raise ValueError(
            "Form definition artifact on disk is out of sync with build_form_definition_payload()."
        )

    city_counts = {
        cf["city"]: cf["poi_count"] for cf in disk_payload.get("city_forms", [])
    }
    if city_counts != {"Hà Nội": 20, "Đà Nẵng": 20, "Hạ Long": 20}:
        raise ValueError(f"Invalid city POI counts in form definition: {city_counts}")

    return {
        "status": "PASS",
        "form_definition_path": FORM_DEFINITION_JSON_RELPATH,
        "form_definition_internal_sha256": disk_internal_sha,
        "form_definition_file_lf_sha256": w07_a2.compute_lf_normalized_sha256(form_def_path),
        "apps_script_path": APPS_SCRIPT_RELPATH,
        "apps_script_lf_sha256": w07_a2.compute_lf_normalized_sha256(gs_path),
        "manifest_internal_sha256": EXPECTED_A2_MANIFEST_INTERNAL_SHA256,
        "city_form_poi_counts": city_counts,
    }


def _is_identity_column(col_name: str) -> bool:
    norm = col_name.strip().lower()
    if norm in {
        "poi_selection",
        "poi_id",
        "poi_name",
        "1. chọn địa điểm (poi) bạn đã trực tiếp đến trải nghiệm",
        "địa điểm (poi)",
    }:
        return False
    return any(pat in norm for pat in IDENTITY_COLUMN_PATTERNS)


def strip_raw_identity_columns(
    raw_row: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Strip any contributor identity columns from a raw CSV export row before processing."""
    sanitized: dict[str, Any] = {}
    stripped_cols: list[str] = []
    for k, v in raw_row.items():
        if k is None:
            continue
        if _is_identity_column(str(k)):
            stripped_cols.append(str(k))
        else:
            sanitized[str(k).strip()] = v
    return sanitized, stripped_cols


def _pick_field(row: dict[str, Any], aliases: list[str], prefix_num: str | None = None) -> str:
    for alias in aliases:
        if alias in row and row[alias] is not None:
            return str(row[alias]).strip()
    lower_map = {k.lower(): v for k, v in row.items() if v is not None}
    for alias in aliases:
        if alias.lower() in lower_map:
            return str(lower_map[alias.lower()]).strip()
    if prefix_num is not None:
        for k, v in row.items():
            if k.strip().startswith(prefix_num) and v is not None:
                return str(v).strip()
    return ""


def _normalize_timestamp_to_date_and_iso(raw_ts: str) -> tuple[str, str]:
    """Deterministically normalize a Google Forms timestamp string to (YYYY-MM-DD, ISO-8601 UTC)."""
    ts = raw_ts.strip()
    if not ts:
        return ("", "")

    # Try common ISO and Google Forms formats
    candidates = (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d",
    )
    for fmt in candidates:
        try:
            parsed = dt.datetime.strptime(ts, fmt)
            date_str = parsed.strftime("%Y-%m-%d")
            iso_str = parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
            return (date_str, iso_str)
        except ValueError:
            continue

    # Fallback: if prefix looks like YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}", ts):
        date_str = ts[:10]
        return (date_str, f"{date_str}T00:00:00Z")

    return ("2026-11-02", "2026-11-02T00:00:00Z")


def _is_consent_affirmed(raw_consent: str) -> bool:
    val = raw_consent.strip().lower()
    if not val:
        return False
    if val in {"false", "no", "0", "không", "khong", "none", "null", "n/a"}:
        return False
    affirmative_tokens = (
        "true",
        "yes",
        "1",
        "đồng ý",
        "dong y",
        "tôi xác nhận",
        "toi xac nhan",
        "i affirm",
        "cam kết",
        "cam ket",
        "trực tiếp đến",
        "personally visited",
    )
    return any(tok in val for tok in affirmative_tokens)


def resolve_canonical_poi(
    raw_poi_selection: str,
    city_name: str,
    manifest_payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve a form POI selection (`<POI name>`, `<POI name> ... — <poi_id>`, or `poi_id`) to a manifest POI."""
    selection = raw_poi_selection.strip()
    if not selection:
        return None

    city_pois = [p for p in manifest_payload["pois"] if p["city"] == city_name]
    city_by_id = {p["poi_id"].lower(): p for p in city_pois}
    city_by_name = {p["name"].strip().lower(): p for p in city_pois}

    # 1. Exact UUID match in city form
    if selection.lower() in city_by_id:
        return city_by_id[selection.lower()]

    # 2. Embedded UUID in disambiguated label
    uuid_match = UUID_SUBSTRING_RE.search(selection)
    if uuid_match:
        candidate_id = uuid_match.group(1).lower()
        return city_by_id.get(candidate_id)

    # 3. Exact human-readable <POI name> match within this city's 20 POIs
    if selection.lower() in city_by_name:
        return city_by_name[selection.lower()]

    # 4. Prefix match before " [" or " —"
    for sep in (" [", " —", " - "):
        if sep in selection:
            prefix = selection.split(sep, 1)[0].strip().lower()
            if prefix in city_by_name:
                return city_by_name[prefix]

    return None


def generate_consent_record_id(
    *,
    form_version: str,
    city_form_id: str,
    response_timestamp: str,
    poi_id: str,
    rating_str: str,
    review_text: str,
    visit_period: str | None,
) -> str:
    """Deterministically generate a non-reversible `consent_record_id` without contributor identity."""
    record_payload = {
        "city_form_id": city_form_id,
        "form_version": form_version,
        "poi_id": poi_id,
        "rating": rating_str.strip(),
        "response_timestamp": response_timestamp.strip(),
        "review_text_sha256": hashlib.sha256(review_text.encode("utf-8")).hexdigest(),
        "visit_period": (visit_period or "").strip(),
    }
    record_digest = hashlib.sha256(
        json.dumps(record_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()

    binding_payload = {
        "city_form_id": city_form_id,
        "form_version": form_version,
        "poi_id": poi_id,
        "response_record_digest": record_digest,
        "response_timestamp": response_timestamp.strip(),
    }
    final_digest = hashlib.sha256(
        json.dumps(binding_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return f"consent_w07_v1_{final_digest[:24]}"


def generate_deterministic_review_id(
    *,
    form_version: str,
    city_form_id: str,
    city_code: str,
    poi_id: str,
    response_timestamp: str,
    rating_str: str,
    review_text: str,
) -> str:
    """Deterministically generate `review_id` so repeated imports of the same export are idempotent."""
    seed_payload = {
        "city_form_id": city_form_id,
        "form_version": form_version,
        "poi_id": poi_id,
        "rating": rating_str.strip(),
        "response_timestamp": response_timestamp.strip(),
        "review_text_sha256": hashlib.sha256(review_text.encode("utf-8")).hexdigest(),
    }
    digest = hashlib.sha256(
        json.dumps(seed_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return f"w07_rev_{city_code}_{digest[:16]}"


def generate_author_anonymous_id(
    *,
    city_form_id: str,
    response_timestamp: str,
    poi_id: str,
) -> str:
    """Generate a non-reversible anonymous contributor session token containing zero PII."""
    seed = f"{FORM_PACKAGE_VERSION}|{city_form_id}|{response_timestamp.strip()}|{poi_id}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"contrib_{digest[:12]}"


def convert_raw_form_row_to_candidate_review(
    raw_row: dict[str, Any],
    *,
    city_name: str,
    manifest_payload: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Convert one raw Google Forms response dict into a candidate W07 schema row + stripped identity column list."""
    cfg_by_city = {c["city"]: c for c in CITY_FORM_CONFIGS}
    if city_name not in cfg_by_city:
        raise ValueError(f"Unsupported city_name: {city_name}")
    city_cfg = cfg_by_city[city_name]
    city_form_id = city_cfg["form_id"]
    city_code = city_cfg["city_code"]

    sanitized_row, stripped_identity_cols = strip_raw_form_identity(raw_row)

    raw_ts = _pick_field(
        sanitized_row,
        ["Timestamp", "Dấu thời gian", "timestamp", "created_at", "collected_at"],
    )
    raw_poi = _pick_field(
        sanitized_row,
        [
            "1. Chọn địa điểm (POI) bạn đã trực tiếp đến trải nghiệm",
            "poi_selection",
            "poi_id",
            "poi_name",
            "Địa điểm (POI)",
        ],
        prefix_num="1.",
    )
    raw_rating = _pick_field(
        sanitized_row,
        [
            "2. Điểm đánh giá tổng thể (1 = Rất tệ, 5 = Rất tốt)",
            "rating",
            "Điểm đánh giá (1-5)",
        ],
        prefix_num="2.",
    )
    # Preserve review_text verbatim (only strip surrounding CSV cell whitespace if needed, never rewrite content)
    raw_review_text = ""
    for alias in (
        "3. Nội dung đánh giá thực tế của riêng bạn",
        "review_text",
        "Nội dung đánh giá",
    ):
        if alias in sanitized_row and sanitized_row[alias] is not None:
            raw_review_text = str(sanitized_row[alias])
            break
    else:
        for k, v in sanitized_row.items():
            if k.strip().startswith("3.") and v is not None:
                raw_review_text = str(v)
                break

    raw_visit_period = _pick_field(
        sanitized_row,
        [
            "4. Thời điểm ghé thăm (Không bắt buộc)",
            "visit_period",
            "Thời điểm ghé thăm",
        ],
        prefix_num="4.",
    )
    raw_consent = _pick_field(
        sanitized_row,
        [
            "5. Cam kết tính xác thực và đồng thuận nghiên cứu học thuật",
            "consent",
            "consent_confirmed",
            "Đồng ý cam kết học thuật",
        ],
        prefix_num="5.",
    )

    target_poi = resolve_canonical_poi(raw_poi, city_name, manifest_payload)
    resolved_poi_id = target_poi["poi_id"] if target_poi is not None else raw_poi.strip()
    upstream_place_id = (
        f"osm:{target_poi['osm_id']}" if target_poi is not None else None
    )

    created_date, collected_iso = _normalize_timestamp_to_date_and_iso(raw_ts)
    if not created_date:
        created_date = "2026-11-02"
    if not collected_iso:
        collected_iso = "2026-11-02T00:00:00Z"

    parsed_rating: float | str | None
    try:
        r_float = float(raw_rating)
        # Rating must be an integer 1..5 in contributor forms
        if r_float.is_integer():
            parsed_rating = float(int(r_float))
        else:
            parsed_rating = -1.0  # trigger INVALID_RATING in validator for non-integer form ratings
    except (TypeError, ValueError):
        parsed_rating = None

    consent_ok = _is_consent_affirmed(raw_consent)
    consent_record_id = (
        generate_consent_record_id(
            form_version=FORM_PACKAGE_VERSION,
            city_form_id=city_form_id,
            response_timestamp=raw_ts or collected_iso,
            poi_id=resolved_poi_id,
            rating_str=raw_rating,
            review_text=raw_review_text,
            visit_period=raw_visit_period or None,
        )
        if consent_ok and resolved_poi_id
        else None
    )

    review_id = generate_deterministic_review_id(
        form_version=FORM_PACKAGE_VERSION,
        city_form_id=city_form_id,
        city_code=city_code,
        poi_id=resolved_poi_id or "unknown_poi",
        response_timestamp=raw_ts or collected_iso,
        rating_str=raw_rating,
        review_text=raw_review_text,
    )

    visit_period_val = raw_visit_period.strip() if raw_visit_period.strip() else None

    # Allow test overrides for source/provenance if present in raw_row (to test synthetic source rejection)
    source_val = str(sanitized_row.get("source", "first_party_contributor_form_v1")).strip()
    provenance_val = str(
        sanitized_row.get("provenance", "FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1")
    ).strip()
    license_val = str(
        sanitized_row.get("license_or_usage_class", "OWNER_FIRST_PARTY_CONSENT")
    ).strip()

    candidate_row: dict[str, Any] = {
        "review_id": review_id,
        "poi_id": resolved_poi_id,
        "upstream_place_id": upstream_place_id,
        "city": city_name,
        "source": source_val,
        "source_review_id": None,
        "rating": parsed_rating,
        "rating_scale_max": 5,
        "review_text": raw_review_text,
        "language": str(sanitized_row.get("language", "vi")).strip() or "vi",
        "created_at": created_date,
        "collected_at": collected_iso,
        "source_ref": f"{city_form_id}#{review_id}",
        "provenance": provenance_val,
        "license_or_usage_class": license_val,
        "mapping_method": "EXACT_PREBOUND_CANONICAL_POI",
        "mapping_confidence": 1.0,
        "author_anonymous_id": generate_author_anonymous_id(
            city_form_id=city_form_id,
            response_timestamp=raw_ts or collected_iso,
            poi_id=resolved_poi_id,
        ),
        "visit_period": visit_period_val,
        "consent_record_id": consent_record_id,
    }
    return candidate_row, stripped_identity_cols


def strip_raw_form_identity(
    raw_row: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Alias for strip_raw_identity_columns."""
    return strip_raw_identity_columns(raw_row)


def import_contributor_csv_files(
    csv_city_pairs: list[tuple[Path, str]],
    *,
    output_jsonl_path: Path,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Deterministically import one or more (csv_path, city_name) exports into `output_jsonl_path`.

    Idempotency guarantee:
    - Existing valid rows in `output_jsonl_path` are loaded first.
    - Incoming rows are converted deterministically; if a converted row has a `review_id`
      already present in the batch or existing file with identical content, it is merged
      without creating a duplicate scientific review.
    - All combined rows are validated through `w07_a2.validate_review_rows()`.
    - Only `accepted_rows` (excluding rejected and PII-quarantined rows) are written to
      `output_jsonl_path`, sorted deterministically by `(poi_id, review_id)`.
    """
    manifest = verify_and_load_a2_manifest(repo_root)

    existing_rows_by_id: dict[str, dict[str, Any]] = {}
    if output_jsonl_path.exists():
        for line in output_jsonl_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                obj = json.loads(line)
                rid = obj.get("review_id")
                if isinstance(rid, str) and rid:
                    existing_rows_by_id[rid] = obj

    incoming_candidates: list[dict[str, Any]] = []
    stripped_columns_seen: set[str] = set()
    idempotent_skipped_count = 0
    seen_incoming_ids: set[str] = set()

    for csv_path, city_name in csv_city_pairs:
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                candidate, stripped_cols = convert_raw_form_row_to_candidate_review(
                    raw_row,
                    city_name=city_name,
                    manifest_payload=manifest,
                )
                stripped_columns_seen.update(stripped_cols)
                rid = candidate["review_id"]
                if rid in existing_rows_by_id or rid in seen_incoming_ids:
                    idempotent_skipped_count += 1
                    continue
                seen_incoming_ids.add(rid)
                incoming_candidates.append(candidate)

    combined_candidates = list(existing_rows_by_id.values()) + incoming_candidates
    validation_report = w07_a2.validate_review_rows(combined_candidates, manifest)

    # Rebuild accepted rows map from combined_candidates that did not appear in rejected_rows
    rejected_indices = {r["row_index"] for r in validation_report["rejected_rows"]}
    accepted_rows = [
        row for idx, row in enumerate(combined_candidates) if idx not in rejected_indices
    ]
    accepted_rows.sort(key=lambda r: (str(r.get("poi_id", "")), str(r.get("review_id", ""))))

    output_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in accepted_rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    output_sha256 = w07_a2.compute_lf_normalized_sha256(output_jsonl_path)

    return {
        "status": "PASS",
        "output_jsonl_path": str(output_jsonl_path),
        "output_jsonl_lf_sha256": output_sha256,
        "existing_accepted_before_import": len(existing_rows_by_id),
        "new_unique_candidates_processed": len(incoming_candidates),
        "idempotent_duplicate_rows_skipped": idempotent_skipped_count,
        "stripped_identity_columns": sorted(stripped_columns_seen),
        "accepted_review_count": validation_report["accepted_review_count"],
        "rejected_review_count": validation_report["rejected_review_count"],
        "quarantined_pii_count": validation_report["quarantined_pii_count"],
        "rejected_rows": validation_report["rejected_rows"],
        "quarantined_pii_rows": validation_report["quarantined_pii_rows"],
        "CORPUS_SCIENTIFIC_MINIMUM_READY": validation_report[
            "CORPUS_SCIENTIFIC_MINIMUM_READY"
        ],
    }


def discover_default_raw_csv_pairs(repo_root: Path = REPO_ROOT) -> list[tuple[Path, str]]:
    raw_dir = repo_root / RAW_FORMS_DIR_RELPATH
    pairs: list[tuple[Path, str]] = []
    for cfg in CITY_FORM_CONFIGS:
        p = raw_dir / cfg["raw_csv_filename"]
        if p.exists():
            pairs.append((p, cfg["city"]))
    return pairs


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="W07-A3 Google Forms definition generator and deterministic contributor review importer."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--write-form-defs",
        action="store_true",
        help="Generate and write W07-A3 form definitions JSON and Google Apps Script utility.",
    )
    group.add_argument(
        "--verify-form-defs",
        action="store_true",
        help="Verify committed W07-A3 form definitions and prior W06/W07 hashes.",
    )
    group.add_argument(
        "--import-raw-dir",
        action="store_true",
        help="Import any present raw CSV exports from data/restricted/w07_reviews/raw_forms/.",
    )
    group.add_argument(
        "--csv",
        type=Path,
        help="Import a single Google Forms CSV export (requires --city).",
    )
    parser.add_argument(
        "--city",
        type=str,
        choices=["Hà Nội", "Đà Nẵng", "Hạ Long"],
        help="City name when using --csv.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=REPO_ROOT / CANONICAL_JSONL_RELPATH,
        help="Target restricted canonical JSONL path.",
    )
    args = parser.parse_args(argv)

    if args.write_form_defs:
        res = write_form_definition_artifacts(REPO_ROOT)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.verify_form_defs:
        res = verify_form_definition_artifacts(REPO_ROOT)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.import_raw_dir:
        pairs = discover_default_raw_csv_pairs(REPO_ROOT)
        res = import_contributor_csv_files(
            pairs,
            output_jsonl_path=args.output_jsonl,
            repo_root=REPO_ROOT,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.csv is not None:
        if not args.city:
            parser.error("--city is required when using --csv.")
        res = import_contributor_csv_files(
            [(args.csv, args.city)],
            output_jsonl_path=args.output_jsonl,
            repo_root=REPO_ROOT,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
