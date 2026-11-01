#!/usr/bin/env python3
"""W07-A2 Canonical 60-POI Intake Manifest + Targeted Review Corpus Validator (v1, Corrective 01).

Implements:
1. Deterministic 60-POI target manifest (`data/evaluation/w07/w07_review_target_60_pois_v1.json`)
   drawn from `data/curated/gomate_places_freeze_v2.json` with Corrective 01 final allocation:
   - Per city (Hà Nội = 20, Đà Nẵng = 20, Hạ Long = 20):
     - attractions/culture = 7
     - restaurants/cafes/markets = 7
     - hotels = 2
     - nature/beach = 3
     - other_tourism = 1
   - Global (60 POIs):
     - attractions/culture = 21
     - restaurants/cafes/markets = 21
     - hotels = 6
     - nature/beach = 9
     - other_tourism = 3
2. Single-authority source-ID binding: all form examples, templates, and summary tables
   derive `poi_id`, `osm_id`, `overture_id`, `source_ids`, coordinates, city, and category
   programmatically from the committed manifest.
3. Hardened first-party consent (`REJECT_MISSING_CONSENT_RECORD` when `consent_record_id` is
   missing on first-party consent rows) and strict PII quarantine (`QUARANTINE_PII_REVIEW_TEXT`
   when `review_text` contains an email address or phone number, preventing acceptance).
4. Strengthened Vietnamese & English consent wording requiring that the contributor
   personally visited or directly experienced the selected place/POI.
5. Immutability checks on W06, W07-0, and W07-A1 artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

MANIFEST_60_JSON_RELPATH = "data/evaluation/w07/w07_review_target_60_pois_v1.json"
INTAKE_STATUS_JSON_RELPATH = "data/evaluation/w07/w07_review_corpus_intake_status_v1.json"
CONTRIBUTOR_SPEC_MD_RELPATH = "docs/research/w07_review_contributor_form_spec.md"
PLACES_FREEZE_RELPATH = "data/curated/gomate_places_freeze_v2.json"

RESTRICTED_JSONL_RELPATH = "data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl"
RESTRICTED_CSV_TEMPLATE_RELPATH = (
    "data/restricted/w07_reviews/w07_contributor_intake_template_v1.csv"
)

W06_CLOSURE_JSON_RELPATH = "data/evaluation/w06/w06_scientific_closure_v1.json"
W07_0_AUDIT_JSON_RELPATH = "data/evaluation/w07/w07_data_rag_readiness_audit_v1.json"
W07_A1_FEASIBILITY_JSON_RELPATH = "data/evaluation/w07/w07_review_corpus_feasibility_v1.json"

AUTHORITATIVE_DEVELOP_BASE_SHA = "7a263ff289b79e198cfda94fea61e1c88dc86813"
PREVIOUS_GATE = (
    "W07-A2-CANONICAL-REVIEW-CORPUS-INTAKE-CHATGPT-AUDIT = HOLD-CORRECTIVE"
)
PREVIOUS_GATE_DECISION = "HOLD-CORRECTIVE"
NEXT_GATE = "W07-A2-CANONICAL-REVIEW-CORPUS-INTAKE-CORRECTIVE-01-CHATGPT-AUDIT"

EXPECTED_W06_CLOSURE_INTERNAL_SHA256 = (
    "7dec87d9b318165ba5233d1470df8f12dfbe99449bceabb86dc2322aaab89e12"
)
EXPECTED_W07_0_INTERNAL_SHA256 = (
    "7a951b5f93473998d4032aabfeaa250ac8e7ba2ea42cbdaf230389cd5fe3a6a9"
)
EXPECTED_W07_0_FILE_LF_SHA256 = (
    "2727cb23ea63af6eada16deba558a82f6329b13ebccb09133c32042466bd2b16"
)
EXPECTED_W07_A1_INTERNAL_SHA256 = (
    "6658b23c4f58f9dd05b7739e20eb7bd0543ed93f8dea76010e4ec3639eae6442"
)
EXPECTED_W07_A1_FILE_LF_SHA256 = (
    "1790ec89f6660217584db81f1983da88a5aa3d02e2b2190ad4d4d3672faa6c1b"
)

PRIMARY_ACQUISITION_STRATEGY = "HYBRID_TARGETED_COLLECTION"
GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE = 5
GOOGLE_PLACES_OFFLINE_CORPUS_ROLE = "NOT_APPROVED_PENDING_STORAGE_TERMS_REVIEW"
TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE = "NOT_RECOMMENDED"
AUXILIARY_ABSA_DATASET_ID = "phamluan/vn_msa_sar_v3"
AUXILIARY_ABSA_ROLE = "AUXILIARY_ABSA_ONLY"

CATEGORY_GROUP_MAP = {
    "attraction": "attractions_culture",
    "culture": "attractions_culture",
    "temple": "attractions_culture",
    "museum": "attractions_culture",
    "restaurant": "restaurants_cafes_markets",
    "cafe": "restaurants_cafes_markets",
    "market": "restaurants_cafes_markets",
    "hotel": "hotels",
    "nature": "nature_beach",
    "beach": "nature_beach",
    "park": "nature_beach",
    "nightlife": "other_tourism",
    "entertainment": "other_tourism",
}

PER_CITY_CATEGORY_GROUP_QUOTAS = {
    "attractions_culture": 7,
    "restaurants_cafes_markets": 7,
    "hotels": 2,
    "nature_beach": 3,
    "other_tourism": 1,
}

GLOBAL_CATEGORY_GROUP_QUOTAS = {
    "attractions_culture": 21,
    "restaurants_cafes_markets": 21,
    "hotels": 6,
    "nature_beach": 9,
    "other_tourism": 3,
}

CITY_CANONICAL_NAMES = {
    "ha-noi": "Hà Nội",
    "da-nang": "Đà Nẵng",
    "ha-long": "Hạ Long",
}

CITY_VALID_ALIASES = {
    "Hà Nội": {"hà nội", "ha noi", "hanoi", "tp. hà nội", "thành phố hà nội", "ha-noi"},
    "Đà Nẵng": {"đà nẵng", "da nang", "danang", "tp. đà nẵng", "thành phố đà nẵng", "da-nang"},
    "Hạ Long": {
        "hạ long",
        "ha long",
        "halong",
        "tp. hạ long",
        "thành phố hạ long",
        "quảng ninh",
        "quang ninh",
        "ha-long",
    },
}

# Frozen 60 canonical POI IDs in deterministic order:
# Each city (Hà Nội, Đà Nẵng, Hạ Long) has exactly:
#   7 attractions_culture + 7 restaurants_cafes_markets + 2 hotels + 3 nature_beach + 1 other_tourism = 20 POIs
# Global: 21 / 21 / 6 / 9 / 3 = 60 POIs.
FROZEN_60_CANONICAL_POI_IDS: tuple[str, ...] = (
    # Hà Nội — attractions/culture (7)
    "698ee756-6062-5f47-955b-bdf458682e57",  # Lăng Chủ tịch Hồ Chí Minh (attraction)
    "b799793b-fb40-5bc2-9e67-6af92caeabe9",  # Hoàng thành Thăng Long (culture)
    "0938eb59-ee1c-5879-a798-58b5fdd07bce",  # Nhà tù Hỏa Lò (culture)
    "44115e3a-6094-5bcd-b53c-0e3a596b3aff",  # Đền Ngọc Sơn (culture)
    "e3fe1f1a-f524-55cf-9d83-903e427d0ba4",  # Chùa Trấn Quốc (culture)
    "f0d424bd-f722-540f-8964-5e6fd8875b56",  # Bảo tàng Dân tộc học Việt Nam (culture)
    "cad64db8-cd74-58fe-ad94-329e0d8110e1",  # Nhà thờ Lớn (culture)
    # Hà Nội — restaurants/cafes/markets (7)
    "afb3793b-7227-4645-a68a-3647c7468638",  # Sen Tây Hồ (restaurant)
    "acb22336-1124-49d5-a279-6357c2b2b445",  # Quán Ăn Ngon - Phan Bội Châu (restaurant)
    "5350dd97-2f75-45fc-9fc1-1979b08670f7",  # Pho 10 (restaurant)
    "b0641225-0f38-4bcc-9f4c-34f65fa50d45",  # Cửa Hàng Bánh Tôm Hồ Tây (restaurant)
    "5bd45eb7-a691-4426-9691-a5a00f38d1ad",  # Highlands Coffee (cafe)
    "4146f2b7-8289-4309-b7e6-60ba7de3470e",  # Cà Phê Nola (cafe)
    "a2fc15de-d609-4d4f-abf1-9779d57901a6",  # Cà Phê Kafa (cafe)
    # Hà Nội — hotels (2)
    "5e92e89d-8524-4792-862a-6dfce0994862",  # Sheraton Hanoi (hotel)
    "9a96e0a0-e040-4e16-a3f2-682ca373dd8e",  # Somerset Grand Hanoi (hotel)
    # Hà Nội — nature/beach (3)
    "766656bb-c7e0-555d-9963-d3132f0de086",  # Công viên Thống Nhất (nature)
    "1f9c2b46-e032-5cbc-a9dc-dc68c435c594",  # Công viên Thủ Lệ (nature)
    "a2037ceb-201f-5c45-a596-af795a399e60",  # Công viên Lê-nin (nature)
    # Hà Nội — other tourism (1)
    "9b08dfe9-6f97-4d4b-94f6-f3548efd696c",  # Le Pub (nightlife)
    # Đà Nẵng — attractions/culture (7)
    "9974ff88-5418-5867-ae49-1b72e0f0861f",  # Cầu Rồng (attraction)
    "6f758ad7-5685-57b5-9913-d28e15bdb7c5",  # Ngũ Hành Sơn (attraction)
    "a24d48ff-59d6-5e53-af77-36448e60d1cc",  # Bảo tàng Nghệ thuật Điêu khắc Chăm Đà Nẵng (culture)
    "5fc0994a-e578-4a25-b375-7f079e6dc3ba",  # Chùa Linh Ứng (temple)
    "2f389152-5676-54be-b812-a1d561b7df15",  # Cầu Sông Hàn (attraction)
    "cb6cce60-8270-5f43-b9f7-42de2d7d7da3",  # Bảo tàng Đà Nẵng (culture)
    "a302989c-08f1-5ca2-8022-a84c1a424018",  # Chợ Cồn (attraction)
    # Đà Nẵng — restaurants/cafes/markets (7)
    "62a874a9-13e2-44d2-95b5-30e980b98965",  # Bánh Xèo Bà Dưỡng (restaurant)
    "61639da8-996a-43df-b6d3-928b6bdd70b9",  # My Quang Bà Mua (restaurant)
    "fd118580-b5da-467d-9873-0116ba435f37",  # Nhà hàng hải sản Bé Anh (restaurant)
    "9a2ca486-437d-4044-8541-d34d911d4fb4",  # Chợ Đêm Sơn Trà (market)
    "c2afbb07-aaf9-47c1-9877-d17e64422066",  # Chợ Bắc Mỹ An (market)
    "7ff87c59-62f1-4509-95f4-e83796b9a35c",  # Vincom Plaza (market)
    "8ebf0429-fabb-4701-bbc1-cb2fea86d587",  # Ca Phe 83 (cafe)
    # Đà Nẵng — hotels (2)
    "4608034c-6c43-4d54-a542-ead8e23b1338",  # InterContinental Danang Sun Peninsula Resort (hotel)
    "a32ce1b4-126b-4544-b5ea-4a7edbab6a0a",  # Furama Resort (hotel)
    # Đà Nẵng — nature/beach (3)
    "2f202acf-c2bb-526a-9803-aaca142ffdad",  # Bãi biển Mỹ Khê (beach)
    "49d739b9-e868-5391-9f80-bf9bed803b0f",  # Bãi tắm Non Nước (beach)
    "b5ea1253-6b6a-5f5a-b910-5ef18cd29c94",  # Ban Co Peak (nature)
    # Đà Nẵng — other tourism (1)
    "987f490f-b1c7-42cf-b92e-300d57fd8d5f",  # Sun World Bà Nà Hills (entertainment)
    # Hạ Long — attractions/culture (7)
    "ade2140c-7945-4044-b99a-b1a028edce9e",  # Vịnh Hạ Long (attraction)
    "8f2b5a69-1293-4efe-8fc5-3a74193edd0f",  # Bảo tàng Quảng Ninh (museum)
    "9a979427-a0bb-421d-b75f-2a6ee79b120b",  # Động Thiên Cung (attraction)
    "9fbcb0b4-27bc-4482-a8e3-8be6e3c72677",  # Hang Đầu Gỗ (attraction)
    "77af14b6-85ac-4c91-873a-e7da27d555f4",  # Hang Luồn Cave Entrance (attraction)
    "88652ea2-61a6-4022-85e5-84a0eb48d3f9",  # Hòn Đỉnh Hương (attraction)
    "871a6ee7-1d46-49bb-957a-ff50260b1f3b",  # Ha Long International Cruise Port (attraction)
    # Hạ Long — restaurants/cafes/markets (7)
    "b37d68ee-0cb3-49f0-a399-cac4c8e2732c",  # Nhà hàng Hồng Hạnh 3 (restaurant)
    "7d01af19-10bc-4679-8cfa-4396209dece4",  # Nhà hàng Ngọc Phương Nam 1 (restaurant)
    "065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5",  # Nhà hàng Buffet Sen Á Đông (restaurant)
    "96523873-1b85-4d2f-b85c-cb3f5593091b",  # Chợ Cái Dăm (market)
    "6215446b-2fdd-4014-aacf-23de6e45e264",  # Chợ Hạ Long II (market)
    "b57b3f7d-9704-44b0-8139-19bea1998391",  # Sữa chua trân châu Hạ Long cơ sở 00 (cafe)
    "85303289-9746-4a42-b0f0-a555ce2bfd0e",  # Highlands Coffee (cafe)
    # Hạ Long — hotels (2)
    "75a3fbd1-a24e-43c6-820a-72f95ebc05c0",  # Vinpearl Ha Long resort (hotel)
    "9740c851-5b06-432c-a243-071ad0906494",  # Novotel Ha Long (hotel)
    # Hạ Long — nature/beach (3)
    "708ee182-c879-477c-b920-516e2c99b0a6",  # Công viên Lán Bè (park)
    "0931b06b-4563-4af0-a3a4-75f1ad8392ee",  # Vườn hoa (park)
    "8fe33554-7a07-4eb2-870f-8af643d8c728",  # Vườn hoa Thị trấn Trới (park)
    # Hạ Long — other tourism (1)
    "1a95430d-289d-4663-91b8-ae64ede4f9a4",  # Sunworld (entertainment)
)

DETERMINISTIC_SELECTION_RATIONALE = (
    "Selected deterministically from REC-A core verified POIs in `data/curated/gomate_places_freeze_v2.json` "
    "under the Corrective 01 quota (`7` attractions/culture, `7` restaurants/cafes/markets, `2` hotels, "
    "`3` nature/beach, `1` other_tourism per city = `20` per city; `21 / 21 / 6 / 9 / 3 = 60` global). "
    "Reducing hotels from 15 to 6 (2 per city) eliminates excessive overnight-stay contributor burden "
    "while increasing day-visit landmarks (`attractions_culture` 18 -> 21, `restaurants_cafes_markets` "
    "18 -> 21, `nature_beach` 6 -> 9) that domestic students and travelers have genuinely visited and "
    "experienced first-hand. Within each city/category slice, POIs were chosen for: (1) stable Freeze v2 "
    "canonical UUID and verified OSM/Overture source IDs, (2) high real-world visitor recognition, "
    "(3) sub-category diversity across all 13 Freeze v2 raw categories, and (4) zero reliance on "
    "availability of scraped online reviews."
)

REQUIRED_REVIEW_SCHEMA_FIELDS: tuple[str, ...] = (
    "review_id",
    "poi_id",
    "upstream_place_id",
    "city",
    "source",
    "source_review_id",
    "rating",
    "rating_scale_max",
    "review_text",
    "language",
    "created_at",
    "collected_at",
    "source_ref",
    "provenance",
    "license_or_usage_class",
    "mapping_method",
    "mapping_confidence",
)

OPTIONAL_REVIEW_SCHEMA_FIELDS: tuple[str, ...] = (
    "author_anonymous_id",
    "visit_period",
    "consent_record_id",
)

FORBIDDEN_PII_FIELDS: tuple[str, ...] = (
    "contributor_real_name",
    "real_name",
    "author_name",
    "phone",
    "phone_number",
    "email",
    "account_handle",
)

FIRST_PARTY_CONSENT_CLASSES: frozenset[str] = frozenset(
    {
        "OWNER_FIRST_PARTY_CONSENT",
        "CC-BY-4.0_FIRST_PARTY_CONSENT",
    }
)

PUBLIC_PERMITTED_LICENSE_CLASSES: frozenset[str] = frozenset(
    {
        "APPROVED",
        "PUBLIC_RESEARCH_PERMITTED_APPROVED",
    }
)

APPROVED_LICENSE_OR_USAGE_CLASSES: frozenset[str] = (
    FIRST_PARTY_CONSENT_CLASSES | PUBLIC_PERMITTED_LICENSE_CLASSES
)

SUPPORTED_MAPPING_METHODS: frozenset[str] = frozenset(
    {
        "EXACT_PREBOUND_CANONICAL_POI",
        "EXACT_UPSTREAM_ID",
    }
)

FORBIDDEN_SOURCE_SUBSTRINGS: tuple[str, ...] = (
    "synthetic",
    "llm",
    "gpt",
    "gemini",
    "claude",
    "openai",
    "anthropic",
    "augmented",
    "vn_msa_sar",
    "vlsp2018",
    "pqthinh232",
    "thanthoai9x",
    "tripadvisor_content_api",
    "google_places_bulk_scrape",
)

HTML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMOJI_OR_PUNCT_ONLY_RE = re.compile(r"^[\W_]+$", re.UNICODE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?84|0)(?:[\s.\-]?\d){8,10}\b")

CONSENT_TEXT_VI = (
    "Việc gửi đánh giá địa điểm là hoàn toàn tự nguyện phục vụ đồ án tốt nghiệp đại học "
    "(GoMate / WanderAI). Nội dung đánh giá sẽ được ẩn danh hoàn toàn (không lưu họ tên, "
    "số điện thoại, email hay tài khoản cá nhân trong bộ dữ liệu khoa học) và được sử dụng "
    "cho mục đích nghiên cứu, đánh giá thực nghiệm và trình diễn học thuật phi thương mại. "
    "Người đóng góp xác nhận không đưa thông tin cá nhân nhạy cảm vào nội dung, xác nhận "
    "bản thân đã trực tiếp đến/trải nghiệm địa điểm được chọn, tự viết đánh giá, không sao chép "
    "từ Google Maps, Tripadvisor, Booking, Agoda hay Foody, không dùng AI (ChatGPT, Gemini, "
    "Claude) để tạo hoặc viết lại nội dung, và đồng ý cấp quyền tái sử dụng học thuật phi thương mại cho dự án."
)

CONSENT_TEXT_EN = (
    "Submission of this place review is completely voluntary for an academic graduation project "
    "(GoMate / WanderAI). Your review will be strictly anonymized (no real name, phone number, "
    "email, or social handle will be stored in the scientific corpus) and may be used for "
    "research, benchmark evaluation, and academic demonstration. Please do not submit any "
    "sensitive personal information. By checking the consent box, you confirm that you have "
    "personally visited or directly experienced the selected place (and personally visited or "
    "directly experienced the selected POI), that the review is your own original writing "
    "(not copied from Google Maps, Tripadvisor, Booking, Agoda, or Foody, and not generated "
    "or paraphrased by an AI/LLM), and that you grant permission for academic, non-commercial project reuse."
)


def _canonical_json_bytes(payload: dict[str, Any], exclude_key: str) -> bytes:
    body = {k: v for k, v in payload.items() if k != exclude_key}
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def compute_internal_sha256(payload: dict[str, Any], exclude_key: str = "artifact_sha256") -> str:
    return hashlib.sha256(_canonical_json_bytes(payload, exclude_key)).hexdigest()


def compute_w06_closure_internal_sha256(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    clone["closure_internal_sha256"] = ""
    raw = (json.dumps(clone, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_lf_normalized_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _normalize_text(text: str) -> str:
    s = unicodedata.normalize("NFC", text.lower().strip())
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def verify_prior_gates_immutability(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    w06_path = repo_root / W06_CLOSURE_JSON_RELPATH
    w07_0_path = repo_root / W07_0_AUDIT_JSON_RELPATH
    w07_a1_path = repo_root / W07_A1_FEASIBILITY_JSON_RELPATH

    w06_payload = json.loads(w06_path.read_text(encoding="utf-8"))
    w07_0_payload = json.loads(w07_0_path.read_text(encoding="utf-8"))
    w07_a1_payload = json.loads(w07_a1_path.read_text(encoding="utf-8"))

    w06_sha = compute_w06_closure_internal_sha256(w06_payload)
    w07_0_sha = compute_internal_sha256(w07_0_payload, "artifact_sha256")
    w07_0_lf = compute_lf_normalized_sha256(w07_0_path)
    w07_a1_sha = compute_internal_sha256(w07_a1_payload, "artifact_sha256")
    w07_a1_lf = compute_lf_normalized_sha256(w07_a1_path)

    if w06_sha != EXPECTED_W06_CLOSURE_INTERNAL_SHA256:
        raise ValueError(f"W06 closure internal SHA mismatch: {w06_sha}")
    if w07_0_sha != EXPECTED_W07_0_INTERNAL_SHA256 or w07_0_lf != EXPECTED_W07_0_FILE_LF_SHA256:
        raise ValueError(f"W07-0 audit SHA mismatch: internal={w07_0_sha} lf={w07_0_lf}")
    if (
        w07_a1_sha != EXPECTED_W07_A1_INTERNAL_SHA256
        or w07_a1_lf != EXPECTED_W07_A1_FILE_LF_SHA256
    ):
        raise ValueError(f"W07-A1 feasibility SHA mismatch: internal={w07_a1_sha} lf={w07_a1_lf}")

    return {
        "w06_closure_internal_sha256": w06_sha,
        "w07_0_audit_internal_sha256": w07_0_sha,
        "w07_0_audit_file_lf_sha256": w07_0_lf,
        "w07_a1_feasibility_internal_sha256": w07_a1_sha,
        "w07_a1_feasibility_file_lf_sha256": w07_a1_lf,
    }


def _extract_source_ids(src_poi: dict[str, Any]) -> tuple[str | None, str | None, list[str]]:
    osm_id: str | None = None
    overture_id: str | None = None
    source_ids: list[str] = []
    for s in src_poi.get("sources", []):
        sname = s.get("source_name")
        sid = str(s.get("source_id", ""))
        if sname and sid:
            source_ids.append(f"{sname}:{sid}")
            if sname == "osm" and osm_id is None:
                osm_id = sid
            elif sname == "overture" and overture_id is None:
                overture_id = sid
    return osm_id, overture_id, sorted(source_ids)


def build_w07_target_60_pois_manifest(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    verify_prior_gates_immutability(repo_root)
    places_v2_path = repo_root / PLACES_FREEZE_RELPATH
    places_v2 = json.loads(places_v2_path.read_text(encoding="utf-8"))
    by_id = {p["place_id"]: p for p in places_v2}

    if len(FROZEN_60_CANONICAL_POI_IDS) != 60 or len(set(FROZEN_60_CANONICAL_POI_IDS)) != 60:
        raise ValueError("FROZEN_60_CANONICAL_POI_IDS must contain exactly 60 unique IDs.")

    manifest_pois: list[dict[str, Any]] = []
    for idx, poi_id in enumerate(FROZEN_60_CANONICAL_POI_IDS, start=1):
        if poi_id not in by_id:
            raise ValueError(f"Canonical POI {poi_id} not found in gomate_places_freeze_v2.json")
        src_poi = by_id[poi_id]
        slug = src_poi["destination_slug"]
        city = CITY_CANONICAL_NAMES[slug]
        cat = src_poi["category"]
        cat_group = CATEGORY_GROUP_MAP[cat]

        osm_id, overture_id, source_ids = _extract_source_ids(src_poi)

        if not osm_id:
            raise ValueError(f"POI {poi_id} is missing osm_id")

        manifest_pois.append(
            {
                "selection_rank": idx,
                "poi_id": poi_id,
                "name": src_poi["name"],
                "city": city,
                "destination_slug": slug,
                "category": cat,
                "category_group": cat_group,
                "latitude": float(src_poi["latitude"]),
                "longitude": float(src_poi["longitude"]),
                "address": src_poi.get("address"),
                "osm_id": osm_id,
                "overture_id": overture_id,
                "source_ids": source_ids,
                "target_review_count_min": 5,
                "target_review_count_preferred": 8,
                "collection_status": "COLLECTION_IN_PROGRESS_0_OF_5",
            }
        )

    city_counts = Counter(p["city"] for p in manifest_pois)
    group_counts = Counter(p["category_group"] for p in manifest_pois)
    raw_cat_counts = dict(sorted(Counter(p["category"] for p in manifest_pois).items()))
    dual_source_count = sum(1 for p in manifest_pois if p["overture_id"] is not None)

    per_city_group_breakdown: dict[str, dict[str, int]] = {}
    for city_name in ("Hà Nội", "Đà Nẵng", "Hạ Long"):
        c_groups = Counter(p["category_group"] for p in manifest_pois if p["city"] == city_name)
        per_city_group_breakdown[city_name] = {
            grp: c_groups[grp] for grp in PER_CITY_CATEGORY_GROUP_QUOTAS
        }
        if per_city_group_breakdown[city_name] != PER_CITY_CATEGORY_GROUP_QUOTAS:
            raise ValueError(
                f"Per-city category group mismatch in {city_name}: "
                f"{per_city_group_breakdown[city_name]} != {PER_CITY_CATEGORY_GROUP_QUOTAS}"
            )

    if city_counts != {"Hà Nội": 20, "Đà Nẵng": 20, "Hạ Long": 20}:
        raise ValueError(f"Invalid city balance: {dict(city_counts)}")
    if dict(group_counts) != GLOBAL_CATEGORY_GROUP_QUOTAS:
        raise ValueError(f"Invalid global category group balance: {dict(group_counts)}")

    payload: dict[str, Any] = {
        "manifest_id": "w07_review_target_60_pois_v1",
        "manifest_version": "1.1.0-corrective-01",
        "task_id": "W07-A2-CORRECTIVE-01",
        "source_canonical_freeze": "data/curated/gomate_places_freeze_v2.json",
        "selection_policy": {
            "deterministic": True,
            "deterministic_selection_rationale": DETERMINISTIC_SELECTION_RATIONALE,
            "total_canonical_pois": 60,
            "per_city_category_group_quotas": dict(PER_CITY_CATEGORY_GROUP_QUOTAS),
            "global_category_group_quotas": dict(GLOBAL_CATEGORY_GROUP_QUOTAS),
            "target_review_count_min_per_poi": 5,
            "target_review_count_preferred_per_poi": 8,
            "scientific_minimum_total_reviews": 300,
            "preferred_total_reviews_for_60_pois": 480,
            "preferred_tier_corpus_range": "75-100 POIs / 600-1200 reviews",
            "entry_rule": (
                "No review may enter the primary W07 scientific corpus unless its `poi_id` "
                "is present in this frozen manifest."
            ),
            "single_source_id_authority_rule": (
                "This committed manifest is the single authority for `poi_id`, `osm_id`, "
                "`overture_id`, `source_ids`, coordinates, city, and category. All form "
                "examples, templates, and summary tables must obtain upstream IDs "
                "programmatically from this manifest."
            ),
            "mapping_rule": {
                "primary_expected_mapping_method": "EXACT_PREBOUND_CANONICAL_POI",
                "primary_expected_mapping_confidence": 1.0,
                "post_hoc_name_only_mapping_allowed": False,
            },
        },
        "summary_statistics": {
            "total_pois": 60,
            "pois_with_osm_id": 60,
            "pois_with_overture_id": dual_source_count,
            "city_distribution": {
                "Hà Nội": city_counts["Hà Nội"],
                "Đà Nẵng": city_counts["Đà Nẵng"],
                "Hạ Long": city_counts["Hạ Long"],
            },
            "per_city_category_group_distribution": per_city_group_breakdown,
            "category_group_distribution": {
                "attractions_culture": group_counts["attractions_culture"],
                "restaurants_cafes_markets": group_counts["restaurants_cafes_markets"],
                "hotels": group_counts["hotels"],
                "nature_beach": group_counts["nature_beach"],
                "other_tourism": group_counts["other_tourism"],
            },
            "raw_category_distribution": raw_cat_counts,
        },
        "pois": manifest_pois,
    }
    payload["manifest_sha256"] = compute_internal_sha256(payload, "manifest_sha256")
    return payload


def build_example_review_row(manifest_payload: dict[str, Any]) -> dict[str, Any]:
    """Programmatically construct the canonical example review row from manifest_payload['pois'][0]."""
    first_poi = manifest_payload["pois"][0]
    osm_prefixed = f"osm:{first_poi['osm_id']}"
    if osm_prefixed not in first_poi["source_ids"]:
        raise ValueError(
            f"Expected {osm_prefixed} in manifest source_ids {first_poi['source_ids']}"
        )
    return {
        "review_id": "w07_rev_hn_0001",
        "poi_id": first_poi["poi_id"],
        "upstream_place_id": osm_prefixed,
        "city": first_poi["city"],
        "source": "first_party_contributor_form_v1",
        "source_review_id": None,
        "rating": 5.0,
        "rating_scale_max": 5,
        "review_text": (
            "Không gian quảng trường Ba Đình và khu vực Lăng Bác rất trang nghiêm, "
            "sạch sẽ, xếp hàng buổi sáng sớm khá nhanh và trật tự."
        ),
        "language": "vi",
        "created_at": "2026-11-02",
        "collected_at": "2026-11-02T09:00:00Z",
        "source_ref": "gomate_w07_contributor_intake_v1#resp_0001",
        "provenance": "FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1",
        "license_or_usage_class": "OWNER_FIRST_PARTY_CONSENT",
        "mapping_method": "EXACT_PREBOUND_CANONICAL_POI",
        "mapping_confidence": 1.0,
        "author_anonymous_id": "contrib_9f86d081884c",
        "visit_period": "2025-10",
        "consent_record_id": "consent_2026_0001",
    }


def render_manifest_poi_markdown_table(manifest_payload: dict[str, Any]) -> list[str]:
    """Deterministically render the 60-POI markdown table directly from manifest_payload."""
    lines = [
        "| # | City | Category Group | Raw Category | `poi_id` | Name | `osm_id` | `overture_id` | Min Reviews |",
        "|---:|---|---|---|---|---|---|---|---:|",
    ]
    for p in manifest_payload["pois"]:
        ov = f"`{p['overture_id']}`" if p["overture_id"] else "`null`"
        lines.append(
            f"| {p['selection_rank']} | {p['city']} | `{p['category_group']}` | `{p['category']}` | "
            f"`{p['poi_id']}` | {p['name']} | `{p['osm_id']}` | {ov} | {p['target_review_count_min']} |"
        )
    return lines


def validate_review_rows(
    rows: list[dict[str, Any]],
    manifest_payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate candidate primary review rows against the frozen 60-POI manifest and Section 6, 7, 11-13 rules."""
    pois_by_id = {p["poi_id"]: p for p in manifest_payload["pois"]}
    accepted_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    quarantined_pii_rows: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    duplicate_records: list[dict[str, Any]] = []

    seen_review_ids: set[str] = set()
    seen_poi_exact_texts: dict[str, set[str]] = {}
    seen_poi_norm_texts: dict[str, set[str]] = {}
    global_norm_text_to_pois: dict[str, set[str]] = {}
    accepted_token_sets: list[tuple[str, str, set[str]]] = []
    opening_frames: Counter[str] = Counter()

    for idx, row in enumerate(rows):
        row_reasons: list[str] = []
        row_warnings: list[str] = []

        if not isinstance(row, dict):
            rejected_rows.append(
                {"row_index": idx, "review_id": None, "reasons": ["ROW_NOT_OBJECT"]}
            )
            continue

        # 1. Check required schema keys exist in dict (nullable fields allowed to be None)
        missing_keys = [k for k in REQUIRED_REVIEW_SCHEMA_FIELDS if k not in row]
        if missing_keys:
            row_reasons.append(f"MISSING_SCHEMA_KEYS:{','.join(missing_keys)}")

        # 2. Privacy / PII check on schema fields (Section 7 & 19)
        present_pii_keys = [k for k in FORBIDDEN_PII_FIELDS if k in row and row[k] is not None]
        if present_pii_keys:
            row_reasons.append(f"FORBIDDEN_PII_FIELD_PRESENT:{','.join(present_pii_keys)}")

        anon_author = row.get("author_anonymous_id")
        if anon_author is not None:
            if (
                not isinstance(anon_author, str)
                or EMAIL_RE.search(anon_author)
                or PHONE_RE.search(anon_author)
            ):
                row_reasons.append("PII_IN_AUTHOR_ANONYMOUS_ID")

        # 3. Review ID check
        review_id = row.get("review_id")
        if not isinstance(review_id, str) or not review_id.strip():
            row_reasons.append("MISSING_OR_EMPTY_REVIEW_ID")
        elif review_id in seen_review_ids:
            row_reasons.append("DUPLICATE_REVIEW_ID")
            duplicate_records.append(
                {"row_index": idx, "review_id": review_id, "duplicate_type": "DUPLICATE_REVIEW_ID"}
            )

        # 4. Canonical POI & upstream_place_id single-authority check (Section 4)
        poi_id = row.get("poi_id")
        target_poi = pois_by_id.get(poi_id) if isinstance(poi_id, str) else None
        if target_poi is None:
            row_reasons.append("UNKNOWN_CANONICAL_POI")
        else:
            upstream_pid = row.get("upstream_place_id")
            if upstream_pid is not None:
                if (
                    not isinstance(upstream_pid, str)
                    or upstream_pid not in target_poi["source_ids"]
                ):
                    row_reasons.append("UPSTREAM_PLACE_ID_NOT_IN_MANIFEST_SOURCE_IDS")

        # 5. City mismatch check
        city_val = row.get("city")
        if not isinstance(city_val, str) or not city_val.strip():
            row_reasons.append("MISSING_CITY")
        elif target_poi is not None:
            expected_city = target_poi["city"]
            valid_aliases = CITY_VALID_ALIASES[expected_city]
            if city_val.strip().lower() not in valid_aliases:
                row_reasons.append(f"CITY_MISMATCH:expected={expected_city},got={city_val}")

        # 6. Review text checks + PII quarantine in review_text (Sections 7, 11, 12)
        review_text = row.get("review_text")
        norm_text = ""
        if not isinstance(review_text, str):
            row_reasons.append("MISSING_REVIEW_TEXT")
        elif review_text.strip() == "":
            row_reasons.append("EMPTY_OR_WHITESPACE_REVIEW")
        else:
            text_no_urls = URL_RE.sub("", review_text).strip()
            if text_no_urls == "":
                row_reasons.append("URL_ONLY_REVIEW")
            elif EMOJI_OR_PUNCT_ONLY_RE.match(text_no_urls):
                row_reasons.append("EMOJI_ONLY_REVIEW")
            else:
                norm_text = _normalize_text(review_text)
                if not norm_text:
                    row_reasons.append("EMOJI_ONLY_REVIEW")
                elif target_poi is not None:
                    poi_exact_set = seen_poi_exact_texts.setdefault(poi_id, set())
                    poi_norm_set = seen_poi_norm_texts.setdefault(poi_id, set())
                    if review_text.strip() in poi_exact_set or norm_text in poi_norm_set:
                        row_reasons.append("EXACT_DUPLICATE_TEXT_FOR_SAME_POI")
                        duplicate_records.append(
                            {
                                "row_index": idx,
                                "review_id": review_id,
                                "poi_id": poi_id,
                                "duplicate_type": "EXACT_DUPLICATE_TEXT_FOR_SAME_POI",
                            }
                        )

                # Section 7 PII firewall: if review_text contains email or phone number,
                # classify as QUARANTINE_PII_REVIEW_TEXT and do NOT accept!
                if EMAIL_RE.search(review_text) or PHONE_RE.search(review_text):
                    row_reasons.append("QUARANTINE_PII_REVIEW_TEXT")
                    quarantined_pii_rows.append(
                        {
                            "row_index": idx,
                            "review_id": review_id if isinstance(review_id, str) else None,
                            "poi_id": poi_id if isinstance(poi_id, str) else None,
                            "classification": "QUARANTINE_PII_REVIEW_TEXT",
                        }
                    )

                # Quality warnings (Section 12: flag short reviews and HTML remnants)
                words = review_text.strip().split()
                if len(review_text.strip()) < 20 or len(words) < 5:
                    row_warnings.append("SHORT_REVIEW_FLAGGED_FOR_MANUAL_REVIEW")
                if HTML_TAG_RE.search(review_text) or "&nbsp;" in review_text:
                    row_warnings.append("HTML_OR_NOISE_REMNANTS")

        # 7. Rating & rating scale validation
        rating = row.get("rating")
        rating_scale_max = row.get("rating_scale_max")
        if (
            isinstance(rating_scale_max, bool)
            or not isinstance(rating_scale_max, (int, float))
            or float(rating_scale_max) not in (5.0, 10.0)
        ):
            row_reasons.append("INVALID_RATING_SCALE")
        if (
            isinstance(rating, bool)
            or not isinstance(rating, (int, float))
            or (
                isinstance(rating_scale_max, (int, float))
                and not isinstance(rating_scale_max, bool)
                and not (1.0 <= float(rating) <= float(rating_scale_max))
            )
        ):
            row_reasons.append("INVALID_RATING")

        # 8. Language validation
        language = row.get("language")
        if not isinstance(language, str) or language.strip().lower() not in {
            "vi",
            "en",
            "mixed_vi_en",
        }:
            row_reasons.append("INVALID_OR_MISSING_LANGUAGE")

        # 9. Provenance, source, collected_at, source_ref, & synthetic/LLM firewall
        source = row.get("source")
        provenance = row.get("provenance")
        source_ref = row.get("source_ref")
        collected_at = row.get("collected_at")
        license_cls = row.get("license_or_usage_class")
        consent_record_id = row.get("consent_record_id")

        if not isinstance(source, str) or not source.strip():
            row_reasons.append("MISSING_SOURCE")
        if not isinstance(provenance, str) or not provenance.strip():
            row_reasons.append("MISSING_PROVENANCE")
        if not isinstance(source_ref, str) or not source_ref.strip():
            row_reasons.append("MISSING_SOURCE_REF")
        if not isinstance(collected_at, str) or not collected_at.strip():
            row_reasons.append("MISSING_COLLECTED_AT")

        combined_meta = " ".join(
            str(x).lower() for x in (source, provenance, source_ref, license_cls) if x is not None
        )
        if any(tok in combined_meta for tok in FORBIDDEN_SOURCE_SUBSTRINGS):
            row_reasons.append("SYNTHETIC_OR_LLM_OR_DISALLOWED_SOURCE")

        if (
            not isinstance(license_cls, str)
            or license_cls.strip() not in APPROVED_LICENSE_OR_USAGE_CLASSES
        ):
            row_reasons.append("MISSING_OR_UNAPPROVED_USAGE_LICENSE_CLASS")
        elif license_cls.strip() in FIRST_PARTY_CONSENT_CLASSES:
            # Section 6: Harden first-party consent
            if not isinstance(consent_record_id, str) or not consent_record_id.strip():
                row_reasons.append("REJECT_MISSING_CONSENT_RECORD")
            if not isinstance(source, str) or not (
                "contributor" in source.lower() or "first_party" in source.lower()
            ):
                row_reasons.append("FIRST_PARTY_SOURCE_MISMATCH")
            if not isinstance(provenance, str) or not (
                "first_party" in provenance.lower() or "contributor" in provenance.lower()
            ):
                row_reasons.append("FIRST_PARTY_PROVENANCE_MISMATCH")

        # 10. Mapping method & confidence validation (Section 6 & 11)
        mapping_method = row.get("mapping_method")
        mapping_conf = row.get("mapping_confidence")
        if not isinstance(mapping_method, str) or mapping_method not in SUPPORTED_MAPPING_METHODS:
            row_reasons.append("UNSUPPORTED_MAPPING_METHOD")
        else:
            if (
                isinstance(mapping_conf, bool)
                or not isinstance(mapping_conf, (int, float))
                or float(mapping_conf) != 1.0
            ):
                row_reasons.append("MAPPING_CONFIDENCE_INCONSISTENT_WITH_METHOD")

        if row_reasons:
            rejected_rows.append(
                {
                    "row_index": idx,
                    "review_id": review_id if isinstance(review_id, str) else None,
                    "poi_id": poi_id if isinstance(poi_id, str) else None,
                    "reasons": row_reasons,
                }
            )
            continue

        # Accepted row bookkeeping
        assert isinstance(review_id, str)
        assert isinstance(poi_id, str)
        assert isinstance(review_text, str)
        seen_review_ids.add(review_id)
        seen_poi_exact_texts.setdefault(poi_id, set()).add(review_text.strip())
        seen_poi_norm_texts.setdefault(poi_id, set()).add(norm_text)

        prior_pois_for_norm = global_norm_text_to_pois.setdefault(norm_text, set())
        if prior_pois_for_norm and poi_id not in prior_pois_for_norm:
            row_warnings.append("NORMALIZED_DUPLICATE_ACROSS_DIFFERENT_POIS")
            duplicate_records.append(
                {
                    "row_index": idx,
                    "review_id": review_id,
                    "poi_id": poi_id,
                    "duplicate_type": "NORMALIZED_DUPLICATE_ACROSS_DIFFERENT_POIS",
                }
            )
        prior_pois_for_norm.add(poi_id)

        tok_set = set(norm_text.split())
        for prev_rev_id, _prev_poi_id, prev_tokens in accepted_token_sets:
            union = tok_set | prev_tokens
            if union and (len(tok_set & prev_tokens) / len(union)) >= 0.85:
                row_warnings.append(f"NEAR_DUPLICATE_JACCARD_GE_0_85:{prev_rev_id}")
                duplicate_records.append(
                    {
                        "row_index": idx,
                        "review_id": review_id,
                        "poi_id": poi_id,
                        "duplicate_type": "NEAR_DUPLICATE_JACCARD_GE_0_85",
                        "matched_review_id": prev_rev_id,
                    }
                )
                break
        accepted_token_sets.append((review_id, poi_id, tok_set))

        words_norm = norm_text.split()
        if len(words_norm) >= 5:
            frame = " ".join(words_norm[:5])
            opening_frames[frame] += 1
            if opening_frames[frame] >= 3:
                row_warnings.append("SUSPICIOUS_REPEATED_TEMPLATE_PREFIX")

        if row_warnings:
            warnings.append(
                {
                    "row_index": idx,
                    "review_id": review_id,
                    "poi_id": poi_id,
                    "warnings": row_warnings,
                }
            )

        accepted_rows.append(row)

    # Compute coverage metrics across the 60 target POIs
    poi_accepted_counts: Counter[str] = Counter(r["poi_id"] for r in accepted_rows)
    covered_pois = [pid for pid in FROZEN_60_CANONICAL_POI_IDS if poi_accepted_counts[pid] > 0]
    pois_meeting_min_5 = [
        pid for pid in FROZEN_60_CANONICAL_POI_IDS if poi_accepted_counts[pid] >= 5
    ]
    pois_under_5 = [pid for pid in FROZEN_60_CANONICAL_POI_IDS if poi_accepted_counts[pid] < 5]

    city_covered_pois: Counter[str] = Counter()
    city_pois_meeting_5: Counter[str] = Counter()
    city_accepted_reviews: Counter[str] = Counter()
    category_group_covered_pois: Counter[str] = Counter()
    category_group_accepted_reviews: Counter[str] = Counter()

    for pid in FROZEN_60_CANONICAL_POI_IDS:
        pmeta = pois_by_id[pid]
        c = pmeta["city"]
        grp = pmeta["category_group"]
        cnt = poi_accepted_counts[pid]
        if cnt > 0:
            city_covered_pois[c] += 1
            category_group_covered_pois[grp] += 1
        if cnt >= 5:
            city_pois_meeting_5[c] += 1
        city_accepted_reviews[c] += cnt
        category_group_accepted_reviews[grp] += cnt

    source_dist = dict(sorted(Counter(r["source"] for r in accepted_rows).items()))
    lang_dist = dict(sorted(Counter(r["language"] for r in accepted_rows).items()))
    rating_dist = dict(sorted(Counter(str(float(r["rating"])) for r in accepted_rows).items()))
    provenance_classes = dict(
        sorted(Counter(r["license_or_usage_class"] for r in accepted_rows).items())
    )

    scientific_minimum_ready = (
        len(accepted_rows) >= 300
        and len(covered_pois) == 60
        and city_covered_pois["Hà Nội"] == 20
        and city_covered_pois["Đà Nẵng"] == 20
        and city_covered_pois["Hạ Long"] == 20
        and len(pois_meeting_min_5) == 60
    )

    remaining_reviews_needed = sum(
        max(0, 5 - poi_accepted_counts[pid]) for pid in FROZEN_60_CANONICAL_POI_IDS
    )

    return {
        "total_input_rows": len(rows),
        "accepted_review_count": len(accepted_rows),
        "rejected_review_count": len(rejected_rows),
        "quarantined_pii_count": len(quarantined_pii_rows),
        "warning_count": len(warnings),
        "duplicate_count": len(duplicate_records),
        "covered_poi_count": len(covered_pois),
        "pois_meeting_min_5_reviews_count": len(pois_meeting_min_5),
        "pois_under_5_reviews_count": len(pois_under_5),
        "remaining_reviews_needed_for_scientific_minimum": remaining_reviews_needed,
        "remaining_pois_needing_reviews": len(pois_under_5),
        "city_coverage": {
            city: {
                "target_pois": 20,
                "covered_pois": city_covered_pois[city],
                "pois_meeting_min_5_reviews": city_pois_meeting_5[city],
                "accepted_reviews": city_accepted_reviews[city],
                "target_reviews_min": 100,
                "remaining_reviews_needed_min": sum(
                    max(0, 5 - poi_accepted_counts[pid])
                    for pid in FROZEN_60_CANONICAL_POI_IDS
                    if pois_by_id[pid]["city"] == city
                ),
            }
            for city in ("Hà Nội", "Đà Nẵng", "Hạ Long")
        },
        "category_group_coverage": {
            grp: {
                "target_pois": target_cnt,
                "covered_pois": category_group_covered_pois[grp],
                "accepted_reviews": category_group_accepted_reviews[grp],
                "target_reviews_min": target_cnt * 5,
            }
            for grp, target_cnt in GLOBAL_CATEGORY_GROUP_QUOTAS.items()
        },
        "source_distribution": source_dist,
        "language_distribution": lang_dist,
        "rating_distribution": rating_dist,
        "provenance_classes": provenance_classes,
        "CORPUS_SCIENTIFIC_MINIMUM_READY": scientific_minimum_ready,
        "corpus_collection_status": (
            "SCIENTIFIC_MINIMUM_READY"
            if scientific_minimum_ready
            else "COLLECTION_IN_PROGRESS"
        ),
        "freeze_status": (
            "SCIENTIFIC_MINIMUM_FROZEN"
            if scientific_minimum_ready
            else "PARTIAL_COLLECTION_NOT_SCIENTIFIC_FREEZE"
        ),
        "rejected_rows": rejected_rows,
        "quarantined_pii_rows": quarantined_pii_rows,
        "warnings": warnings,
        "duplicates": duplicate_records,
    }


def validate_review_jsonl_file(
    jsonl_path: Path,
    manifest_payload: dict[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                rows.append(json.loads(stripped))
    return validate_review_rows(rows, manifest_payload)


def build_w07_a2_intake_status_payload(
    manifest_payload: dict[str, Any],
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    prior_shas = verify_prior_gates_immutability(repo_root)
    restricted_jsonl_path = repo_root / RESTRICTED_JSONL_RELPATH
    val_report = validate_review_jsonl_file(restricted_jsonl_path, manifest_payload)
    example_row = build_example_review_row(manifest_payload)

    payload: dict[str, Any] = {
        "artifact_id": "w07_review_corpus_intake_status_v1",
        "artifact_version": "1.1.0-corrective-01",
        "task_id": "W07-A2-CORRECTIVE-01",
        "task_title": "CANONICAL 60-POI INTAKE + TARGETED REVIEW CORPUS ACQUISITION (CORRECTIVE 01)",
        "authority_and_gates": {
            "previous_gate": PREVIOUS_GATE,
            "previous_gate_decision": PREVIOUS_GATE_DECISION,
            "authoritative_develop_base_sha": AUTHORITATIVE_DEVELOP_BASE_SHA,
            "next_gate": NEXT_GATE,
            "w06_status": "CLOSED_IMMUTABLE",
            "w07_0_status": "COMPLETE_IMMUTABLE",
            "w07_a1_status": "COMPLETE_IMMUTABLE",
            **prior_shas,
        },
        "target_manifest_binding": {
            "manifest_path": MANIFEST_60_JSON_RELPATH,
            "manifest_sha256": manifest_payload["manifest_sha256"],
            "total_target_pois": 60,
            "deterministic_selection_rationale": DETERMINISTIC_SELECTION_RATIONALE,
            "city_distribution": manifest_payload["summary_statistics"]["city_distribution"],
            "per_city_category_group_distribution": manifest_payload["summary_statistics"][
                "per_city_category_group_distribution"
            ],
            "category_group_distribution": manifest_payload["summary_statistics"][
                "category_group_distribution"
            ],
            "raw_category_distribution": manifest_payload["summary_statistics"][
                "raw_category_distribution"
            ],
            "canonical_example_review_row": example_row,
        },
        "primary_review_schema_spec": {
            "required_fields": list(REQUIRED_REVIEW_SCHEMA_FIELDS),
            "optional_fields": list(OPTIONAL_REVIEW_SCHEMA_FIELDS),
            "forbidden_pii_fields": list(FORBIDDEN_PII_FIELDS),
            "primary_mapping_method": "EXACT_PREBOUND_CANONICAL_POI",
            "primary_mapping_confidence": 1.0,
            "post_hoc_name_only_mapping_allowed": False,
            "first_party_consent_enforcement": {
                "applicable_classes": sorted(FIRST_PARTY_CONSENT_CLASSES),
                "consent_record_id_required": True,
                "missing_consent_record_action": "REJECT_MISSING_CONSENT_RECORD",
                "public_permitted_consent_record_id_nullable": True,
            },
            "pii_review_text_firewall": {
                "email_or_phone_in_review_text_action": "QUARANTINE_PII_REVIEW_TEXT",
                "accepted_into_scientific_corpus": False,
                "counts_toward_scientific_minimum": False,
                "auto_rewrite_or_redact_review_text": False,
            },
        },
        "channel_a_public_research_permitted_acquisition_audit": {
            "sources_checked": [
                {
                    "source": "gomate_places_freeze_v2.json (OpenStreetMap + Overture Maps)",
                    "research_reuse_status": "APPROVED_METADATA_ONLY",
                    "primary_review_text_rows_found": 0,
                    "note": "Provides canonical place_id, coordinates, category, and osm/overture IDs for all 60 POIs, but 0 user review texts.",
                },
                {
                    "source": "MinhDS/ViHoRec (data/restricted/vihorec/)",
                    "research_reuse_status": "CC-BY-NC-4.0_RATINGS_ONLY",
                    "primary_review_text_rows_found": 0,
                    "note": "17,911 numeric hotel interactions; 0 user review texts.",
                },
                {
                    "source": "phamluan/vn_msa_sar_v3 + VLSP2018-ABSA + pqthinh232 + mendeley:10.17632/dp8s59xnb7.1 + hienbm/tripadvisor_vietnam",
                    "research_reuse_status": "AUXILIARY_ONLY_UNMAPPABLE_TO_60_POIS",
                    "primary_review_text_rows_found": 0,
                    "note": "Place identities, addresses, and coordinates were stripped prior to release; 0 rows map to the 60 canonical POIs.",
                },
                {
                    "source": "ThanThoai9x/vietnamese-food-images",
                    "research_reuse_status": "REJECTED_ZERO_GEOGRAPHIC_OVERLAP",
                    "primary_review_text_rows_found": 0,
                    "note": "100% Hồ Chí Minh City (34,104 / 34,104 rows across 9 HCMC districts); 0 rows in Hà Nội, Đà Nẵng, or Hạ Long.",
                },
                {
                    "source": "Google Maps / Tripadvisor / Booking / Agoda / Foody public web pages",
                    "research_reuse_status": "NOT_APPROVED_NO_SCRAPING",
                    "primary_review_text_rows_found": 0,
                    "note": "Public visibility does not grant research dataset redistribution rights; scraping is strictly prohibited.",
                },
            ],
            "PUBLIC_PRIMARY_REVIEWS_ACQUIRED": 0,
            "NEW_PRIMARY_REVIEWS_ACQUIRED": 0,
        },
        "channel_b_contributor_intake_package": {
            "contributor_form_spec_path": CONTRIBUTOR_SPEC_MD_RELPATH,
            "restricted_jsonl_path": RESTRICTED_JSONL_RELPATH,
            "restricted_csv_template_path": RESTRICTED_CSV_TEMPLATE_RELPATH,
            "consent_text_vi": CONSENT_TEXT_VI,
            "consent_text_en": CONSENT_TEXT_EN,
            "anonymization_rule": (
                "External contributor identities (name, email, phone, handle) are never imported "
                "into `w07_canonical_reviews_v1.jsonl`; only a deterministic salted hash "
                "`author_anonymous_id = contrib_<sha256[:12]>` and non-empty `consent_record_id` are stored."
            ),
        },
        "current_validation_and_readiness_summary": {
            "corpus_collection_status": val_report["corpus_collection_status"],
            "freeze_status": val_report["freeze_status"],
            "CORPUS_SCIENTIFIC_MINIMUM_READY": val_report["CORPUS_SCIENTIFIC_MINIMUM_READY"],
            "accepted_review_count": val_report["accepted_review_count"],
            "rejected_review_count": val_report["rejected_review_count"],
            "quarantined_pii_count": val_report["quarantined_pii_count"],
            "warning_count": val_report["warning_count"],
            "duplicate_count": val_report["duplicate_count"],
            "covered_poi_count": val_report["covered_poi_count"],
            "pois_meeting_min_5_reviews_count": val_report["pois_meeting_min_5_reviews_count"],
            "remaining_reviews_needed_for_scientific_minimum": val_report[
                "remaining_reviews_needed_for_scientific_minimum"
            ],
            "remaining_pois_needing_reviews": val_report["remaining_pois_needing_reviews"],
            "city_coverage": val_report["city_coverage"],
            "category_group_coverage": val_report["category_group_coverage"],
            "source_distribution": val_report["source_distribution"],
        },
        "owner_action_pack": {
            "status": "ACTION_REQUIRED_TO_REACH_300_REVIEWS",
            "reviews_still_needed_min": val_report[
                "remaining_reviews_needed_for_scientific_minimum"
            ],
            "pois_still_under_5_reviews": val_report["remaining_pois_needing_reviews"],
            "city_gaps": {
                "Hà Nội": {"pois_needing_reviews": 20, "reviews_needed_min": 100},
                "Đà Nẵng": {"pois_needing_reviews": 20, "reviews_needed_min": 100},
                "Hạ Long": {"pois_needing_reviews": 20, "reviews_needed_min": 100},
            },
            "category_group_gaps": {
                "attractions_culture": {"pois_needing_reviews": 21, "reviews_needed_min": 105},
                "restaurants_cafes_markets": {
                    "pois_needing_reviews": 21,
                    "reviews_needed_min": 105,
                },
                "hotels": {"pois_needing_reviews": 6, "reviews_needed_min": 30},
                "nature_beach": {"pois_needing_reviews": 9, "reviews_needed_min": 45},
                "other_tourism": {"pois_needing_reviews": 3, "reviews_needed_min": 15},
            },
            "recommended_contributor_plan": {
                "suggested_contributors_range": "30-50 contributors (students, alumni, local travelers)",
                "suggested_reviews_per_contributor": (
                    "6-10 genuine reviews per contributor covering ONLY canonical POIs "
                    "they have personally visited or directly experienced (e.g., 30 contributors x 10 "
                    "reviews or 50 contributors x 6 reviews = 300 genuine reviews)."
                ),
                "strict_authenticity_rules": [
                    "Contributor must have personally visited or directly experienced the selected POI.",
                    "Do NOT copy reviews from Google Maps, Tripadvisor, Booking, Agoda, or Foody.",
                    "Do NOT invent a visit to a place never visited.",
                    "Do NOT use ChatGPT, Gemini, Claude, or any LLM to generate or paraphrase reviews.",
                ],
            },
            "form_fields_required": [
                "1. Canonical POI Selection (`[City] Name (Category) — poi_id`, chosen from the 60 frozen POIs)",
                "2. Genuine Review Text (`review_text`, Vietnamese or English, recommended >= 20 chars / >= 5 words, zero email/phone PII)",
                "3. Overall Rating (`rating`, integer/float 1 to 5 on `rating_scale_max = 5`)",
                "4. Language (`vi`, `en`, or `mixed_vi_en`)",
                "5. Visit Period (`visit_period`, optional, e.g., `2025-07` or `2026-Q1`)",
                "6. Personal Visit, Originality & Academic Reuse Consent Checkbox (`consent_record_id` recorded on submission)",
            ],
            "validation_command_after_intake": (
                "python scripts/validate_w07_review_corpus_v1.py "
                "--validate-jsonl data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl"
            ),
        },
        "firewalls_and_infrastructure": {
            "PRIMARY_ACQUISITION_STRATEGY": PRIMARY_ACQUISITION_STRATEGY,
            "AUXILIARY_ABSA_DATASET": AUXILIARY_ABSA_DATASET_ID,
            "AUXILIARY_ABSA_ROLE": AUXILIARY_ABSA_ROLE,
            "AUXILIARY_ALLOWED_IN_PRIMARY_CORPUS": False,
            "GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE": GOOGLE_PLACES_MAX_REVIEWS_PER_PLACE,
            "GOOGLE_PLACES_OFFLINE_CORPUS_ROLE": GOOGLE_PLACES_OFFLINE_CORPUS_ROLE,
            "TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE": (
                TRIPADVISOR_CONTENT_API_ACADEMIC_CORPUS_ROLE
            ),
            "LLM_GENERATED_PRIMARY_REVIEWS": 0,
            "NEW_PRIMARY_REVIEWS_ACQUIRED": 0,
            "NEW_LLM_PROVIDER_CALLS": 0,
            "SCRAPING_EXECUTED": False,
            "gpu_required": False,
            "vps_required": False,
            "vector_db_required_in_w07_a2": False,
            "paid_api_required": False,
            "proxy_required": False,
        },
    }
    payload["artifact_sha256"] = compute_internal_sha256(payload, "artifact_sha256")
    return payload


def render_contributor_form_spec_markdown(
    manifest_payload: dict[str, Any],
    status_payload: dict[str, Any],
) -> str:
    example_row = build_example_review_row(manifest_payload)
    lines = [
        "# W07-A2 — Canonical 60-POI Contributor Review Form Specification & Intake Guide",
        "",
        "## 0. Authority & Scope",
        "",
        f"- **Previous Gate:** `{status_payload['authority_and_gates']['previous_gate']}`",
        f"- **Authoritative Base:** `develop@{status_payload['authority_and_gates']['authoritative_develop_base_sha']}`",
        f"- **Target 60-POI Manifest (Single Authority):** `{MANIFEST_60_JSON_RELPATH}` (SHA256: `{manifest_payload['manifest_sha256']}`)",
        f"- **Restricted Primary Corpus Path (gitignored):** `{RESTRICTED_JSONL_RELPATH}`",
        f"- **Restricted CSV Intake Template (gitignored):** `{RESTRICTED_CSV_TEMPLATE_RELPATH}`",
        f"- **Primary Acquisition Strategy:** `{PRIMARY_ACQUISITION_STRATEGY}`",
        f"- **Next Gate:** `{status_payload['authority_and_gates']['next_gate']}`",
        "",
        "---",
        "",
        "## 1. Consent Language (Academic Graduation Project — Corrective 01)",
        "",
        "### Vietnamese Consent Text (Displayed at Top of Form & Required Checkbox)",
        "",
        f"> {CONSENT_TEXT_VI}",
        "",
        "### English Consent Text",
        "",
        f"> {CONSENT_TEXT_EN}",
        "",
        "---",
        "",
        "## 2. Google Forms / Microsoft Forms / CSV Field Specification",
        "",
        "Create a zero-cost Google Form, Microsoft Form, or shared spreadsheet with the following 6 fields:",
        "",
        "| # | Form Field | Schema Field Mapping | Type & Validation | Required |",
        "|---:|---|---|---|---|",
        "| 1 | **Canonical Place (`poi_id`)** | `poi_id` + `city` | Dropdown of the 60 frozen POIs formatted as `[City] Name (Category) — poi_id` | **Yes** |",
        "| 2 | **Your Genuine Review (`review_text`)** | `review_text` | Paragraph text (`>= 20` characters and `>= 5` words recommended; zero email/phone PII; describe real visit experience) | **Yes** |",
        "| 3 | **Overall Rating (`1–5`)** | `rating` (`rating_scale_max = 5`) | Linear scale `1` to `5` (`1 = Poor`, `5 = Excellent`) | **Yes** |",
        "| 4 | **Review Language** | `language` | Multiple choice: `vi` (Tiếng Việt), `en` (English), `mixed_vi_en` | **Yes** |",
        "| 5 | **Visit Period (Optional)** | `visit_period` | Short text (`YYYY-MM` or `YYYY-Q1..Q4`, e.g. `2025-08`) | Optional |",
        "| 6 | **Personal Visit, Originality & Academic Reuse Consent** | `license_or_usage_class = OWNER_FIRST_PARTY_CONSENT` + `consent_record_id` | Required checkbox confirming: (a) contributor personally visited or directly experienced the selected place/POI, (b) own writing not copied from Google Maps/Tripadvisor/Booking/Agoda/Foody, (c) not AI/LLM-generated, (d) anonymized academic reuse permitted | **Yes** |",
        "",
        "### Strict Authenticity, Consent & PII Firewall Rules",
        "- **Personal visit requirement:** Contributors must have **personally visited or directly experienced the selected POI** (`đã trực tiếp đến/trải nghiệm địa điểm`).",
        "- **Mandatory consent record (`REJECT_MISSING_CONSENT_RECORD`):** Every first-party row (`OWNER_FIRST_PARTY_CONSENT` or `CC-BY-4.0_FIRST_PARTY_CONSENT`) must carry a non-empty `consent_record_id`, contributor `source`, and first-party `provenance`.",
        "- **No platform copying:** Contributors must **never** copy or translate reviews from Google Maps, Tripadvisor, Booking.com, Agoda, or Foody.",
        "- **Zero LLM generation (`LLM_GENERATED_PRIMARY_REVIEWS = 0`):** LLMs (ChatGPT, Gemini, Claude, etc.) must **never** be used to write, rewrite, or paraphrase reviews.",
        "- **PII Quarantine (`QUARANTINE_PII_REVIEW_TEXT`):** Reviews containing an email address or phone number inside `review_text` are automatically quarantined/rejected (`QUARANTINE_PII_REVIEW_TEXT`), never rewritten automatically, and never counted toward `accepted_review_count` or `CORPUS_SCIENTIFIC_MINIMUM_READY`.",
        "",
        "---",
        "",
        "## 3. Primary Review JSONL Schema (`w07_canonical_reviews_v1.jsonl`)",
        "",
        "Every accepted row in `data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl` must conform to this exact 17-field primary schema (plus 3 optional fields), where `upstream_place_id` is derived programmatically from `manifest[poi_id].source_ids`:",
        "",
        "```json",
        json.dumps(example_row, ensure_ascii=False, indent=2),
        "```",
        "",
        "---",
        "",
        "## 4. Frozen 60 Canonical POIs (`20` Hà Nội, `20` Đà Nẵng, `20` Hạ Long; `21 / 21 / 6 / 9 / 3` Category Allocation)",
        "",
        f"**Deterministic Selection Rationale:** {DETERMINISTIC_SELECTION_RATIONALE}",
        "",
        *render_manifest_poi_markdown_table(manifest_payload),
        "",
        "---",
        "",
        "## 5. Owner Action Pack (Low-Burden Collection Plan)",
        "",
        "- **Current Status:** `COLLECTION_IN_PROGRESS` (`0 / 300` primary reviews collected; `CORPUS_SCIENTIFIC_MINIMUM_READY = false`).",
        "- **Remaining Gap to Scientific Minimum:** `300` reviews across `60` canonical POIs (`>= 5` reviews/POI: `100` Hà Nội, `100` Đà Nẵng, `100` Hạ Long; `105` attractions/culture, `105` restaurants/cafes/markets, `30` hotels, `45` nature/beach, `15` other tourism).",
        "- **Recommended Low-Burden Distribution:**",
        "  - Invite **30 to 50 contributors** (classmates, university students, local travelers).",
        "  - Each contributor submits **6 to 10 genuine reviews** for POIs from the 60-POI table that they have personally visited or directly experienced in Hà Nội, Đà Nẵng, or Hạ Long.",
        "  - Run offline validation after importing responses:",
        "    ```bash",
        "    python scripts/validate_w07_review_corpus_v1.py --validate-jsonl data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl",
        "    ```",
        "",
    ]
    return "\n".join(lines)


def initialize_restricted_intake_files(
    manifest_payload: dict[str, Any],
    repo_root: Path = REPO_ROOT,
) -> None:
    jsonl_path = repo_root / RESTRICTED_JSONL_RELPATH
    csv_path = repo_root / RESTRICTED_CSV_TEMPLATE_RELPATH
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    if not jsonl_path.exists():
        jsonl_path.write_text("", encoding="utf-8", newline="\n")

    with csv_path.open("w", encoding="utf-8", newline="\n") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "selection_rank",
                "poi_id",
                "city",
                "name",
                "category",
                "category_group",
                "osm_id",
                "overture_id",
                "upstream_place_id",
                "target_review_count_min",
                "review_id",
                "rating_1_to_5",
                "language_vi_or_en",
                "visit_period_optional",
                "review_text",
                "consent_record_id",
                "author_anonymous_id",
            ]
        )
        for p in manifest_payload["pois"]:
            writer.writerow(
                [
                    p["selection_rank"],
                    p["poi_id"],
                    p["city"],
                    p["name"],
                    p["category"],
                    p["category_group"],
                    p["osm_id"],
                    p["overture_id"] or "",
                    f"osm:{p['osm_id']}",
                    p["target_review_count_min"],
                    "",
                    "",
                    "vi",
                    "",
                    "",
                    "",
                    "",
                ]
            )


def write_w07_a2_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    manifest_payload = build_w07_target_60_pois_manifest(repo_root)
    initialize_restricted_intake_files(manifest_payload, repo_root)
    status_payload = build_w07_a2_intake_status_payload(manifest_payload, repo_root)
    spec_md = render_contributor_form_spec_markdown(manifest_payload, status_payload)

    manifest_path = repo_root / MANIFEST_60_JSON_RELPATH
    status_path = repo_root / INTAKE_STATUS_JSON_RELPATH
    spec_path = repo_root / CONTRIBUTOR_SPEC_MD_RELPATH

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_path.write_bytes(
        (json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    status_path.write_bytes(
        (json.dumps(status_payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    spec_path.write_bytes(spec_md.encode("utf-8"))
    return {
        "manifest": manifest_payload,
        "status": status_payload,
    }


def verify_w07_a2_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    expected_manifest = build_w07_target_60_pois_manifest(repo_root)
    expected_status = build_w07_a2_intake_status_payload(expected_manifest, repo_root)
    expected_md = render_contributor_form_spec_markdown(expected_manifest, expected_status)

    manifest_path = repo_root / MANIFEST_60_JSON_RELPATH
    status_path = repo_root / INTAKE_STATUS_JSON_RELPATH
    spec_path = repo_root / CONTRIBUTOR_SPEC_MD_RELPATH

    for p in (manifest_path, status_path, spec_path):
        if not p.exists():
            raise FileNotFoundError(f"Missing required W07-A2 artifact: {p}")

    disk_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if disk_manifest != expected_manifest:
        raise ValueError("On-disk 60-POI manifest differs from deterministic build.")
    if disk_manifest.get("manifest_sha256") != compute_internal_sha256(
        disk_manifest, "manifest_sha256"
    ):
        raise ValueError("60-POI manifest internal SHA256 mismatch.")

    disk_status = json.loads(status_path.read_text(encoding="utf-8"))
    if disk_status != expected_status:
        raise ValueError("On-disk W07-A2 intake status JSON differs from deterministic build.")
    if disk_status.get("artifact_sha256") != compute_internal_sha256(
        disk_status, "artifact_sha256"
    ):
        raise ValueError("W07-A2 intake status internal SHA256 mismatch.")

    disk_md = spec_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if disk_md != expected_md.replace("\r\n", "\n"):
        raise ValueError("On-disk contributor form spec Markdown differs from deterministic build.")

    # Verify example row upstream_place_id is in manifest[poi_id].source_ids
    ex_row = disk_status["target_manifest_binding"]["canonical_example_review_row"]
    manifest_by_id = {p["poi_id"]: p for p in disk_manifest["pois"]}
    if ex_row["upstream_place_id"] not in manifest_by_id[ex_row["poi_id"]]["source_ids"]:
        raise ValueError("Example review row upstream_place_id is not in manifest source_ids.")

    return {
        "status": "PASS",
        "manifest_path": MANIFEST_60_JSON_RELPATH,
        "manifest_internal_sha256": disk_manifest["manifest_sha256"],
        "manifest_file_lf_sha256": compute_lf_normalized_sha256(manifest_path),
        "intake_status_path": INTAKE_STATUS_JSON_RELPATH,
        "intake_status_internal_sha256": disk_status["artifact_sha256"],
        "intake_status_file_lf_sha256": compute_lf_normalized_sha256(status_path),
        "contributor_spec_md_path": CONTRIBUTOR_SPEC_MD_RELPATH,
        "contributor_spec_md_lf_sha256": compute_lf_normalized_sha256(spec_path),
        "CORPUS_SCIENTIFIC_MINIMUM_READY": disk_status[
            "current_validation_and_readiness_summary"
        ]["CORPUS_SCIENTIFIC_MINIMUM_READY"],
        "corpus_collection_status": disk_status["current_validation_and_readiness_summary"][
            "corpus_collection_status"
        ],
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Generate, verify, or validate W07-A2 canonical 60-POI review corpus intake."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--write",
        action="store_true",
        help="Write W07-A2 manifest, intake status, contributor spec, and restricted templates.",
    )
    group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify committed W07-A2 artifacts and prior W06/W07-0/W07-A1 hashes.",
    )
    group.add_argument(
        "--validate-jsonl",
        type=Path,
        help="Validate a JSONL review file against the frozen 60-POI manifest.",
    )
    group.add_argument(
        "--print-manifest-table",
        action="store_true",
        help="Print the 60-POI Markdown table directly from the committed manifest.",
    )
    args = parser.parse_args(argv)

    if args.print_manifest_table:
        manifest_path = REPO_ROOT / MANIFEST_60_JSON_RELPATH
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        print("\n".join(render_manifest_poi_markdown_table(manifest_payload)))
        return 0

    if args.validate_jsonl is not None:
        manifest_payload = build_w07_target_60_pois_manifest(REPO_ROOT)
        report = validate_review_jsonl_file(args.validate_jsonl, manifest_payload)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.write:
        write_w07_a2_artifacts(REPO_ROOT)
    result = verify_w07_a2_artifacts(REPO_ROOT)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
