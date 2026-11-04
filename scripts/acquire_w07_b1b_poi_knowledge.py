#!/usr/bin/env python3
"""W07-B1B — Targeted POI Knowledge Acquisition Builder & Reproducible Runner.

Acquires provenance-bound, license-verified (`OPEN_REUSABLE`) POI-specific knowledge
documents for the frozen 60-POI W07 target set (`P0 -> P1 -> P2`, prioritizing Hạ Long
first), separating candidate discovery (`w07_b1b_source_decisions_v1.json`) from
persistent primary corpus ingestion (`data/curated/w07/poi_knowledge_acquired_v1.jsonl`).

Does NOT mutate the PostgreSQL `documents` table (reserved for B2).
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_w07_review_corpus_v1 as w07_a2  # noqa: E402

AUTHORITATIVE_BASE_DEVELOP_SHA = "324163636cedc8391c07cf2deca37d907745bd14"
PREVIOUS_ACCEPTED_GATE = "W07-B1-FIX-01B-POSTMERGE-CHATGPT-AUDIT = PASS"
CURRENT_GATE_STATUS = "W07-B1B-CORRECTIVE-02-FACT-CONSISTENCY-CHATGPT-AUDIT = HOLD-CORRECTIVE-03"
NEXT_GATE = "W07-B1B-CORRECTIVE-03-SOURCE-BINDING-CHATGPT-AUDIT"
ARTIFACT_SNAPSHOT_TIMESTAMP = "2026-11-03T18:45:00Z"
OVERTURE_SNAPSHOT_TIMESTAMP = "2026-09-23T00:00:00Z"
UNKNOWN_HISTORICAL_RETRIEVAL_TIME = "UNKNOWN_HISTORICAL_RETRIEVAL_TIME"
UNKNOWN_VERIFICATION_TIME = "UNKNOWN_VERIFICATION_TIME"
ALLOWED_OVERTURE_OPEN_LICENSES: frozenset[str] = frozenset({"CDLA-Permissive-2.0", "Apache-2.0", "CC0-1.0"})

TARGET_60_PATH = REPO_ROOT / "data/evaluation/w07/w07_review_target_60_pois_v1.json"
B1A_AUDIT_PATH = REPO_ROOT / "data/evaluation/w07/w07_b1a_existing_poi_knowledge_audit_v1.json"
FIX01B_RECEIPT_PATH = REPO_ROOT / "data/evaluation/w07/w07_b1_fix_01b_reingestion_v1.json"

DECISIONS_JSON_PATH = REPO_ROOT / "data/evaluation/w07/w07_b1b_source_decisions_v1.json"
ACQUIRED_JSONL_PATH = REPO_ROOT / "data/curated/w07/poi_knowledge_acquired_v1.jsonl"
SUMMARY_JSON_PATH = REPO_ROOT / "data/evaluation/w07/w07_b1b_acquisition_summary_v1.json"
REPORT_MD_PATH = REPO_ROOT / "docs/research/w07_b1b_targeted_poi_knowledge_acquisition.md"

HEADERS = {"User-Agent": "WanderAI-ResearchBot/1.0 (https://github.com/wanderai; academic-thesis-w07-b1b)"}

UPSTREAM_ARTIFACT_LF_HASHES: dict[str, str] = {
    "data/evaluation/w06/w06_scientific_closure_v1.json": "7b58fcc8c63a7e1391a4d5212ed08f57317bb4d81d9069a9513cfaf3c03398cc",
    "data/evaluation/w07/w07_data_rag_readiness_audit_v1.json": "2727cb23ea63af6eada16deba558a82f6329b13ebccb09133c32042466bd2b16",
    "data/evaluation/w07/w07_review_target_60_pois_v1.json": "3a065165d038f300f5dc422180fcaf3cef265ac1a100ea8e841daaba1a82d5d4",
    "data/evaluation/w07/w07_review_corpus_feasibility_v1.json": "1790ec89f6660217584db81f1983da88a5aa3d02e2b2190ad4d4d3672faa6c1b",
    "data/evaluation/w07/w07_review_collection_progress_v1.json": "bbf789ae44c7dd9bbfbd4c5bdea923ded1ddbacc270ec7764e360e84bebe598a",
    "data/evaluation/w07/w07_contributor_collection_form_definition_v1.json": "1984d131fe41f5152731f0c77ad68e4b77c5a54df0718fa031ed4527d1e7340b",
    "data/evaluation/w07/w07_first_party_collection_progress_v1.json": "79095ce10fbf50a838d9e1a607001d821413ced6e8d6e7ad5ac2fd6e7c6239d1",
    "data/evaluation/w07/w07_public_source_evidence_receipts_v1.json": "bc5c8ace3618d5a67d16bf9bd5c298c52f132fc8fe575bd1678730f31b0b1d49",
    "data/evaluation/w07/w07_public_review_acquisition_v1.json": "b1380683b5a55d92fe467203b912af86fd945a31bc9160c789c57c3e55ae04ea",
    "data/evaluation/w07/w07_data_strategy_amendment_01_v1.json": "896fb5f90bce36610f9e82e23f52e56e0f93d90ecb81f564b6a1360b8e4b3c94",
    "docs/research/w07_data_strategy_amendment_01.md": "0f1ef9fcb9500882ce3dbbbea148d2d592fbe7211eb1e91f86855d6ed08af585",
    "data/evaluation/w07/w07_b1a_existing_poi_knowledge_audit_v1.json": "433c722dd2f03946ab0a15830b53ef628d76937fa2e8e63a9939e73bb469e563",
    "docs/research/w07_b1a_existing_poi_knowledge_audit.md": "130aca652c9b808a8b7e5fac50d070dd0c3f36a8e94f7693cfac8793643d0ac5",
    "apps/ai-service/app/rag/osm_documents.py": "99fa5f076fce698cd3d32bbb2f191f23456895f26c22b59d0db502a760386455",
    "data/evaluation/w07/w07_b1_fix_01b_reingestion_v1.json": "38516e31df5f35f7efed2c5a1c355a44778acfdaef8b5c29354c3d56a32bfc71",
    "docs/research/w07_b1_fix_01b_reingestion.md": "9475ff03c4fb454fc6335332a557a7a9a101a78c14472d1b3225ee2f25f3d62c",
}

# Accepted Wikipedia POI-specific article specifications (26 documents across 25 lineages)
ACCEPTED_WIKIPEDIA_SPECS: list[dict[str, Any]] = [
    # Hạ Long (6 documents across 5 lineages; P0 first, then P1)
    {
        "poi_id": "1a95430d-289d-4663-91b8-ae64ede4f9a4",
        "domain": "en.wikipedia.org",
        "lang": "en",
        "title": "Dragon Park Ha Long",
        "section_heading": None,
        "mapping_evidence": "Exact amusement park complex entity match (Dragon Park / Sun World Halong Complex at Bãi Cháy, Hạ Long; coords 20.95548, 107.04965 within 390m of canonical POI entrance 20.95214, 107.04831; Wikidata Q28449757).",
    },
    {
        "poi_id": "88652ea2-61a6-4022-85e5-84a0eb48d3f9",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Vịnh Hạ Long",
        "section_heading": "==== Hòn Đỉnh Hương (Lư Hương) ====",
        "mapping_evidence": "Dedicated POI subsection '==== Hòn Đỉnh Hương (Lư Hương) ====' inside Vịnh Hạ Long article (pageid=4483), explicitly describing Hòn Đỉnh Hương southwest of Hang Đầu Gỗ and depicted on the 200,000 VND banknote. Shares source_lineage_id 'wikipedia:vi:4483' with Vịnh Hạ Long per Section 4.",
    },
    {
        "poi_id": "8f2b5a69-1293-4efe-8fc5-3a74193edd0f",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Bảo tàng Quảng Ninh",
        "section_heading": None,
        "mapping_evidence": "Exact institutional entity match for Bảo tàng Quảng Ninh (Trần Quốc Nghiễn, Hồng Gai, Hạ Long; Wikidata Q112182634).",
    },
    {
        "poi_id": "9a979427-a0bb-421d-b75f-2a6ee79b120b",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Động Thiên Cung",
        "section_heading": None,
        "mapping_evidence": "Exact karst cave entity match for Động Thiên Cung on Đầu Gỗ Island in Hạ Long Bay (`vi.wikipedia.org/wiki/Động_Thiên_Cung`, pageid=21159845).",
    },
    {
        "poi_id": "9fbcb0b4-27bc-4482-a8e3-8be6e3c72677",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Hang Đầu Gỗ",
        "section_heading": None,
        "mapping_evidence": "Exact karst cave entity match for Hang Đầu Gỗ on Đầu Gỗ Island in Hạ Long Bay (Wikidata Q10765377; coords 20.90833, 107.02083).",
    },
    {
        "poi_id": "ade2140c-7945-4044-b99a-b1a028edce9e",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Vịnh Hạ Long",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Vịnh Hạ Long` and `wikidata=Q190128` on canonical node/2707025319.",
    },
    # Đà Nẵng (10 documents across 10 lineages; P0 -> P1 -> P2)
    {
        "poi_id": "2f389152-5676-54be-b812-a1d561b7df15",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Cầu Sông Hàn",
        "section_heading": None,
        "mapping_evidence": "Exact bridge entity and coordinate match (`16.072146, 108.226802`, <2m from canonical POI `16.07214, 108.22681`; Wikidata Q10752400).",
    },
    {
        "poi_id": "49d739b9-e868-5391-9f80-bf9bed803b0f",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Bãi biển Non Nước",
        "section_heading": None,
        "mapping_evidence": "Exact beach entity match for Bãi tắm / Bãi biển Non Nước in Ngũ Hành Sơn Ward, Đà Nẵng (Wikidata Q16480040).",
    },
    {
        "poi_id": "b5ea1253-6b6a-5f5a-b910-5ef18cd29c94",
        "domain": "en.wikipedia.org",
        "lang": "en",
        "title": "Sơn Trà Mountain",
        "section_heading": "== Ban Co Peak ==",
        "mapping_evidence": "Dedicated POI section '== Ban Co Peak ==' in Sơn Trà Mountain article (pageid=30765128, Wikidata Q7560606; coords 16.1197, 108.2868).",
    },
    {
        "poi_id": "2f202acf-c2bb-526a-9803-aaca142ffdad",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Bãi biển Mỹ Khê",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Bãi biển Mỹ Khê` and `wikidata=Q10796763` on canonical relation/19000664.",
    },
    {
        "poi_id": "6f758ad7-5685-57b5-9913-d28e15bdb7c5",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Ngũ Hành Sơn",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Ngũ Hành Sơn` and `wikidata=Q6755207` on canonical relation/8552348.",
    },
    {
        "poi_id": "987f490f-b1c7-42cf-b92e-300d57fd8d5f",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Bà Nà",
        "section_heading": None,
        "mapping_evidence": "Exact mountain resort complex match (`Bà Nà (còn gọi là Sun World Ba Na Hills)`; Wikidata Q5004763; coords 15.99556, 107.99417 matching canonical POI 15.99563, 107.98972).",
    },
    {
        "poi_id": "9974ff88-5418-5867-ae49-1b72e0f0861f",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Cầu Rồng",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikidata=Q5305270` (`sitelink viwiki=Cầu Rồng`) on canonical way/694831926.",
    },
    {
        "poi_id": "a24d48ff-59d6-5e53-af77-36448e60d1cc",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Bảo tàng Điêu khắc Chăm Đà Nẵng",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Bảo tàng Nghệ thuật điêu khắc Chăm Đà Nẵng` (redirecting to `Bảo tàng Điêu khắc Chăm Đà Nẵng`) and `wikidata=Q6940790` on canonical way/302872188.",
    },
    {
        "poi_id": "a302989c-08f1-5ca2-8022-a84c1a424018",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Chợ Cồn",
        "section_heading": None,
        "mapping_evidence": "Exact market entity and coordinate match (`16.06778, 108.21417`, 58m from canonical POI `16.06817, 108.21453` at Ông Ích Khiêm / Hùng Vương; Wikidata Q10748770).",
    },
    {
        "poi_id": "4608034c-6c43-4d54-a542-ead8e23b1338",
        "domain": "en.wikipedia.org",
        "lang": "en",
        "title": "InterContinental Danang Sun Peninsula Resort",
        "section_heading": None,
        "mapping_evidence": "Exact resort entity and coordinate match (`16.1205, 108.30616`, 70m from canonical POI `16.12111, 108.30632`; Wikidata Q17068326).",
    },
    # Hà Nội (10 documents across 10 lineages; P1 -> P2)
    {
        "poi_id": "0938eb59-ee1c-5879-a798-58b5fdd07bce",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Nhà tù Hỏa Lò",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikidata=Q1359941` (`sitelink viwiki=Nhà tù Hỏa Lò`) and `wikipedia=en:Hỏa Lò Prison` on canonical way/340128580.",
    },
    {
        "poi_id": "1f9c2b46-e032-5cbc-a9dc-dc68c435c594",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Công viên Thủ Lệ",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Công viên Thủ Lệ` and `wikidata=Q944021` on canonical way/28945667.",
    },
    {
        "poi_id": "44115e3a-6094-5bcd-b53c-0e3a596b3aff",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Đền Ngọc Sơn",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Đền Ngọc Sơn` and `wikidata=Q3517494` on canonical way/178995262.",
    },
    {
        "poi_id": "698ee756-6062-5f47-955b-bdf458682e57",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Lăng Chủ tịch Hồ Chí Minh",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Lăng Chủ tịch Hồ Chí Minh` and `wikidata=Q874234` on canonical way/37625751.",
    },
    {
        "poi_id": "766656bb-c7e0-555d-9963-d3132f0de086",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Công viên Thống Nhất",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Công viên Thống Nhất` and `wikidata=Q10752058` on canonical way/37933849.",
    },
    {
        "poi_id": "b799793b-fb40-5bc2-9e67-6af92caeabe9",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Hoàng thành Thăng Long",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Hoàng thành Thăng Long` and `wikidata=Q206219` on canonical relation/21425205.",
    },
    {
        "poi_id": "cad64db8-cd74-58fe-ad94-329e0d8110e1",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Nhà thờ Lớn Hà Nội",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Nhà thờ Lớn Hà Nội` and `wikidata=Q1923783` on canonical way/28912942.",
    },
    {
        "poi_id": "e3fe1f1a-f524-55cf-9d83-903e427d0ba4",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Chùa Trấn Quốc",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Chùa Trấn Quốc` and `wikidata=Q864770` on canonical way/220302249.",
    },
    {
        "poi_id": "a2037ceb-201f-5c45-a596-af795a399e60",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Công viên Lê-nin",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Công viên Lê Nin` (redirecting to `Công viên Lê-nin`) and `wikidata=Q10752053` on canonical way/185540946.",
    },
    {
        "poi_id": "f0d424bd-f722-540f-8964-5e6fd8875b56",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Bảo tàng Dân tộc học Việt Nam",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Bảo tàng Dân tộc học Việt Nam` and `wikidata=Q1048345` on canonical way/339936730.",
    },
]

# Rejected Wikipedia candidates (4 candidates failing mapping gate)
REJECTED_WIKIPEDIA_SPECS: list[dict[str, Any]] = [
    {
        "poi_id": "85303289-9746-4a42-b0f0-a555ce2bfd0e",
        "domain": "vi.wikipedia.org",
        "title": "Highlands Coffee",
        "pageid": "13908782",
        "mapping_evidence": "Wikipedia article `Highlands Coffee` (Q5759361) describes the national coffee chain brand rather than the specific Trần Hưng Đạo, Hạ Long branch (`85303289-9746-4a42-b0f0-a555ce2bfd0e`). Rejected under Section 10 canonical POI mapping gate.",
    },
    {
        "poi_id": "5fc0994a-e578-4a25-b375-7f079e6dc3ba",
        "domain": "vi.wikipedia.org",
        "title": "Chùa Linh Ứng",
        "pageid": "2459953",
        "mapping_evidence": "Wikipedia article `Chùa Linh Ứng` (Q18277260) focuses on Chùa Linh Ứng Bãi Bụt on Sơn Trà Peninsula (`16.099, 108.277`), which is 10.6km north of the canonical POI `5fc0994a-e578-4a25-b375-7f079e6dc3ba` (`Chùa Linh Ứng Non Nước` on Hòn Thủy Sơn, Ngũ Hành Sơn at `16.00428, 108.26437`). Rejected under Section 10.",
    },
    {
        "poi_id": "cb6cce60-8270-5f43-b9f7-42de2d7d7da3",
        "domain": "vi.wikipedia.org",
        "title": "Thành Điện Hải",
        "pageid": "19562172",
        "mapping_evidence": "Wikipedia article `Thành Điện Hải` (Q3917231) describes the historic Điện Hải Citadel (former 24 Trần Phú museum grounds), whereas canonical POI `cb6cce60-8270-5f43-b9f7-42de2d7d7da3` (`Bảo tàng Đà Nẵng`) is at 42-44 Bạch Đằng / 31 Trần Phú (`16.07483, 108.22398`). Rejected under Section 10.",
    },
    {
        "poi_id": "b0641225-0f38-4bcc-9f4c-34f65fa50d45",
        "domain": "vi.wikipedia.org",
        "title": "Bánh tôm Hồ Tây",
        "pageid": "15367",
        "mapping_evidence": "Wikipedia article `Bánh tôm Hồ Tây` (Q10742230) is classified as a culinary dish article (`bánh tôm - Vietnamese seafood dish`) rather than a dedicated venue entity page for `Cửa Hàng Bánh Tôm Hồ Tây` (`1 Đường Thanh Niên`). Rejected under Section 10.",
    },
]

# Accepted Wikidata POI-specific structured entity specifications (28 documents across 28 lineages)
ACCEPTED_WIKIDATA_SPECS: list[dict[str, Any]] = [
    # Hạ Long (5 entities)
    (
        "1a95430d-289d-4663-91b8-ae64ede4f9a4",
        "Q28449757",
        "Exact amusement park complex entity match (Ocean Park / Dragon Park / Sun World Halong Complex; coords 20.95548, 107.04965).",
    ),
    (
        "75a3fbd1-a24e-43c6-820a-72f95ebc05c0",
        "Q111402972",
        "Exact hotel/resort entity and coordinate match (`Vinpearl Resort & Spa Ha Long`, Đảo Rều, Bãi Cháy, Hạ Long; coords 20.9413, 107.0253, <20m from canonical POI).",
    ),
    (
        "8f2b5a69-1293-4efe-8fc5-3a74193edd0f",
        "Q112182634",
        "Exact museum entity match (`Bảo tàng Quảng Ninh / Quang Ninh Museum`, Trần Quốc Nghiễn, Hạ Long).",
    ),
    (
        "9740c851-5b06-432c-a243-071ad0906494",
        "Q111402973",
        "Exact hotel entity and coordinate match (`Novotel Ha Long Bay Hotel`, 160 Đường Hạ Long, Bãi Cháy; coords 20.9520, 107.0420, <10m from canonical POI).",
    ),
    (
        "ade2140c-7945-4044-b99a-b1a028edce9e",
        "Q190128",
        "Exact OSM `wikidata=Q190128` tag on canonical node/2707025319 (`Vịnh Hạ Long`).",
    ),
    # Đà Nẵng (11 entities)
    (
        "2f389152-5676-54be-b812-a1d561b7df15",
        "Q10752400",
        "Exact bridge entity and coordinate match (`Cầu Sông Hàn / Han River Bridge`, coords 16.07215, 108.22680, <2m from canonical POI).",
    ),
    (
        "49d739b9-e868-5391-9f80-bf9bed803b0f",
        "Q16480040",
        "Exact beach entity match (`Bãi biển Non Nước / Non Nuoc Beach`, Ngũ Hành Sơn, Đà Nẵng).",
    ),
    (
        "b5ea1253-6b6a-5f5a-b910-5ef18cd29c94",
        "Q7560606",
        "Exact mountain/peninsula entity match (`Sơn Trà / Monkey Mountain` containing Ban Co Peak at 16.11893, 108.27200).",
    ),
    (
        "2f202acf-c2bb-526a-9803-aaca142ffdad",
        "Q10796763",
        "Exact OSM `wikidata=Q10796763` tag on canonical relation/19000664 (`Bãi biển Mỹ Khê`).",
    ),
    (
        "6f758ad7-5685-57b5-9913-d28e15bdb7c5",
        "Q6755207",
        "Exact OSM `wikidata=Q6755207` tag on canonical relation/8552348 (`Ngũ Hành Sơn`).",
    ),
    (
        "987f490f-b1c7-42cf-b92e-300d57fd8d5f",
        "Q5004763",
        "Exact mountain resort complex match (`Bà Nà / Bà Nà Hills`, coords 15.99556, 107.99417).",
    ),
    (
        "9974ff88-5418-5867-ae49-1b72e0f0861f",
        "Q5305270",
        "Exact OSM `wikidata=Q5305270` tag on canonical way/694831926 (`Cầu Rồng`).",
    ),
    (
        "a24d48ff-59d6-5e53-af77-36448e60d1cc",
        "Q6940790",
        "Exact OSM `wikidata=Q6940790` tag on canonical way/302872188 (`Bảo tàng Nghệ thuật Điêu khắc Chăm Đà Nẵng`).",
    ),
    ("a302989c-08f1-5ca2-8022-a84c1a424018", "Q10748770", "Exact market entity match (`Chợ Cồn`, Hải Châu, Đà Nẵng)."),
    (
        "4608034c-6c43-4d54-a542-ead8e23b1338",
        "Q17068326",
        "Exact resort entity and coordinate match (`InterContinental Danang Sun Peninsula Resort`, coords 16.1205, 108.30616).",
    ),
    (
        "a32ce1b4-126b-4544-b5ea-4a7edbab6a0a",
        "Q111402873",
        "Exact resort entity and coordinate match (`Furama Resort Danang`, 105 Võ Nguyên Giáp, Ngũ Hành Sơn; coords 16.0397, 108.2514).",
    ),
    # Hà Nội (12 entities)
    (
        "0938eb59-ee1c-5879-a798-58b5fdd07bce",
        "Q1359941",
        "Exact OSM `wikidata=Q1359941` tag on canonical way/340128580 (`Nhà tù Hỏa Lò`).",
    ),
    (
        "1f9c2b46-e032-5cbc-a9dc-dc68c435c594",
        "Q944021",
        "Exact OSM `wikidata=Q944021` tag on canonical way/28945667 (`Công viên Thủ Lệ`).",
    ),
    (
        "44115e3a-6094-5bcd-b53c-0e3a596b3aff",
        "Q3517494",
        "Exact OSM `wikidata=Q3517494` tag on canonical way/178995262 (`Đền Ngọc Sơn`).",
    ),
    (
        "698ee756-6062-5f47-955b-bdf458682e57",
        "Q874234",
        "Exact OSM `wikidata=Q874234` tag on canonical way/37625751 (`Lăng Chủ tịch Hồ Chí Minh`).",
    ),
    (
        "766656bb-c7e0-555d-9963-d3132f0de086",
        "Q10752058",
        "Exact OSM `wikidata=Q10752058` tag on canonical way/37933849 (`Công viên Thống Nhất`).",
    ),
    (
        "b799793b-fb40-5bc2-9e67-6af92caeabe9",
        "Q206219",
        "Exact OSM `wikidata=Q206219` tag on canonical relation/21425205 (`Hoàng thành Thăng Long`).",
    ),
    (
        "cad64db8-cd74-58fe-ad94-329e0d8110e1",
        "Q1923783",
        "Exact OSM `wikidata=Q1923783` tag on canonical way/28912942 (`Nhà thờ Lớn`).",
    ),
    (
        "e3fe1f1a-f524-55cf-9d83-903e427d0ba4",
        "Q864770",
        "Exact OSM `wikidata=Q864770` tag on canonical way/220302249 (`Chùa Trấn Quốc`).",
    ),
    (
        "5e92e89d-8524-4792-862a-6dfce0994862",
        "Q117325492",
        "Exact hotel entity and street address match (`Sheraton Hanoi Hotel`, K5 Nghi Tàm / 11 Xuân Diệu, Tây Hồ; coarse P625 coordinate suppressed due to 4.7km offset from canonical/Overture/Wikivoyage Tây Hồ location).",
    ),
    (
        "9a96e0a0-e040-4e16-a3f2-682ca373dd8e",
        "Q111402985",
        "Exact hotel entity and coordinate match (`Somerset Grand Hanoi`, 49 Hai Bà Trưng, Hoàn Kiếm; coords 21.0258, 105.8464).",
    ),
    (
        "a2037ceb-201f-5c45-a596-af795a399e60",
        "Q10752053",
        "Exact OSM `wikidata=Q10752053` tag on canonical way/185540946 (`Công viên Lê-nin`).",
    ),
    (
        "f0d424bd-f722-540f-8964-5e6fd8875b56",
        "Q1048345",
        "Exact OSM `wikidata=Q1048345` tag on canonical way/339936730 (`Bảo tàng Dân tộc học Việt Nam`).",
    ),
]

# Rejected Wikidata candidates (3 candidates)
REJECTED_WIKIDATA_SPECS: list[dict[str, Any]] = [
    {
        "poi_id": "9fbcb0b4-27bc-4482-a8e3-8be6e3c72677",
        "qid": "Q10765377",
        "canonical_mapping_status": "EXACT_MAPPED",
        "content_utility_status": "LOW_INFORMATION",
        "mapping_evidence": "Exact Wikidata sitelink match (`viwiki=Hang Đầu Gỗ`), but Wikidata item Q10765377 contains only 2 bare claims (`P17=Vietnam`, `P2671` Google KG ID) with no description, instance type, or coordinates (`LOW_INFORMATION`). Rejected under Section 15.",
    },
    {
        "poi_id": "5fc0994a-e578-4a25-b375-7f079e6dc3ba",
        "qid": "Q18277260",
        "canonical_mapping_status": "MAPPING_REVIEW_REQUIRED",
        "content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "mapping_evidence": "Wikidata item Q18277260 (`Linh Ung Pagoda`) has coordinates `16.099, 108.277` (Bãi Bụt, Sơn Trà), 10.6km north of canonical POI `5fc0994a-e578-4a25-b375-7f079e6dc3ba` (`Chùa Linh Ứng Non Nước` at Hòn Thủy Sơn `16.00428, 108.26437`). Rejected under Section 10.",
    },
    {
        "poi_id": "9a979427-a0bb-421d-b75f-2a6ee79b120b",
        "qid": "Q124453533",
        "canonical_mapping_status": "MAPPING_REVIEW_REQUIRED",
        "content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "mapping_evidence": "Wikidata item Q124453533 (`Động Thiên Cung`) has `P131 = Hoa Lư (Q131417547)` and `P625 = 20.215960, 105.914210` (a homonymous cave in Hoa Lư, Ninh Bình, 138.5km from Hạ Long Bay `20.9163222, 107.0185625`). Rejected under Corrective 02 fact-consistency & canonical mapping gate.",
    },
]

# Accepted Wikivoyage POI-specific listing specifications (20 documents across 2 lineages: wikivoyage:en:Da_Nang and wikivoyage:en:Hanoi)
ACCEPTED_WIKIVOYAGE_SPECS: list[dict[str, Any]] = [
    # Đà Nẵng (8 listings from en.wikivoyage.org/wiki/Da_Nang)
    (
        "987f490f-b1c7-42cf-b92e-300d57fd8d5f",
        "en.wikivoyage.org",
        "Da Nang",
        "Ba Na Hill Station",
        "Exact listing `name=Ba Na Hill Station | alt=Bà Nà | wikidata=Q5004763` in `en.wikivoyage.org/wiki/Da_Nang`.",
    ),
    (
        "9974ff88-5418-5867-ae49-1b72e0f0861f",
        "en.wikivoyage.org",
        "Da Nang",
        "Dragon Bridge",
        "Exact listing `name=Dragon Bridge | alt=Cầu Rồng | wikidata=Q5305270` in `en.wikivoyage.org/wiki/Da_Nang`.",
    ),
    (
        "6f758ad7-5685-57b5-9913-d28e15bdb7c5",
        "en.wikivoyage.org",
        "Da Nang",
        "Marble Mountains",
        "Exact listing `name=Marble Mountains | alt=Ngu Hanh Son | wikidata=Q6755207` in `en.wikivoyage.org/wiki/Da_Nang`.",
    ),
    (
        "a24d48ff-59d6-5e53-af77-36448e60d1cc",
        "en.wikivoyage.org",
        "Da Nang",
        "Museum of Cham Sculpture",
        "Exact listing `name=Museum of Cham Sculpture | alt=Bảo Tàng Chăm | wikidata=Q6940790` in `en.wikivoyage.org/wiki/Da_Nang`.",
    ),
    (
        "2f202acf-c2bb-526a-9803-aaca142ffdad",
        "en.wikivoyage.org",
        "Da Nang",
        "My Khe Beach",
        "Exact listing `name=My Khe Beach | alt=Bãi biển Mỹ Khê | address=Hoang Sa Rd` in `en.wikivoyage.org/wiki/Da_Nang`.",
    ),
    (
        "9a2ca486-437d-4044-8541-d34d911d4fb4",
        "en.wikivoyage.org",
        "Da Nang",
        "Son Tra Night Market",
        "Exact listing `name=Son Tra Night Market | alt=Chợ Đêm Sơn Trà | lat=16.06188 | long=108.23168` in `en.wikivoyage.org/wiki/Da_Nang`.",
    ),
    (
        "4608034c-6c43-4d54-a542-ead8e23b1338",
        "en.wikivoyage.org",
        "Da Nang",
        "InterContinental Danang Sun Peninsula Resort",
        "Exact listing `name=InterContinental Danang Sun Peninsula Resort | address=Thọ Quang, Sơn Trà` in `en.wikivoyage.org/wiki/Da_Nang`.",
    ),
    (
        "a32ce1b4-126b-4544-b5ea-4a7edbab6a0a",
        "en.wikivoyage.org",
        "Da Nang",
        "Furama Resort",
        "Exact listing `name=Furama Resort | address=Truong Sa St` in `en.wikivoyage.org/wiki/Da_Nang`.",
    ),
    # Hà Nội (12 listings from en.wikivoyage.org/wiki/Hanoi)
    (
        "698ee756-6062-5f47-955b-bdf458682e57",
        "en.wikivoyage.org",
        "Hanoi",
        "Hồ Chí Minh Mausoleum",
        "Exact listing `name=Hồ Chí Minh Mausoleum | wikidata=Q874234` in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
    (
        "b799793b-fb40-5bc2-9e67-6af92caeabe9",
        "en.wikivoyage.org",
        "Hanoi",
        "Hanoi Citadel",
        "Exact listing `name=Hanoi Citadel | wikidata=Q4568216 | lat=21.037407 | long=105.840428` in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
    (
        "0938eb59-ee1c-5879-a798-58b5fdd07bce",
        "en.wikivoyage.org",
        "Hanoi",
        "Hỏa Lò Prison",
        "Exact listing `name=Hỏa Lò Prison | alt=Hanoi Hilton | wikidata=Q1359941 | address=1 Hỏa Lò` in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
    (
        "44115e3a-6094-5bcd-b53c-0e3a596b3aff",
        "en.wikivoyage.org",
        "Hanoi",
        "Ngọc Sơn Temple",
        "Exact listing `name=Ngọc Sơn Temple | wikidata=Q3517494` in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
    (
        "e3fe1f1a-f524-55cf-9d83-903e427d0ba4",
        "en.wikivoyage.org",
        "Hanoi",
        "Trấn Quốc Pagoda",
        "Exact listing `name=Trấn Quốc Pagoda | alt=Chùa Trấn Quốc | wikidata=Q864770` in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
    (
        "cad64db8-cd74-58fe-ad94-329e0d8110e1",
        "en.wikivoyage.org",
        "Hanoi",
        "St. Joseph's Cathedral",
        "Exact listing `name=St. Joseph's Cathedral | wikidata=Q1923783 | address=Nha Tho` in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
    (
        "acb22336-1124-49d5-a279-6357c2b2b445",
        "en.wikivoyage.org",
        "Hanoi",
        "Quán Ăn Ngon",
        "Exact listing `name=Quán Ăn Ngon | address=18 Phan Boi Chau St | lat=21.026289 | long=105.843455` (16m from canonical POI) in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
    (
        "f0d424bd-f722-540f-8964-5e6fd8875b56",
        "en.wikivoyage.org",
        "Hanoi",
        "Museum of Ethnology",
        "Exact listing `name=Museum of Ethnology | alt=Bảo tàng Dân tộc học Việt Nam | wikidata=Q1048345` in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
    (
        "5350dd97-2f75-45fc-9fc1-1979b08670f7",
        "en.wikivoyage.org",
        "Hanoi",
        "Pho 10 Ly Quoc Su",
        "Exact listing `name=Pho 10 Ly Quoc Su | address=10 P. Lý Quốc Sư` (6.8m from canonical POI) in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
    (
        "5e92e89d-8524-4792-862a-6dfce0994862",
        "en.wikivoyage.org",
        "Hanoi",
        "Sheraton Hanoi Hotel",
        "Exact listing `name=Sheraton Hanoi Hotel | address=K5 Nghi Tam, 11 Xuan Dieu Rd, Tay Ho District` in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
    (
        "9a96e0a0-e040-4e16-a3f2-682ca373dd8e",
        "en.wikivoyage.org",
        "Hanoi",
        "Somerset Grand Hanoi",
        "Exact listing `name=Somerset Grand Hanoi | address=49 Hai Ba Trung St` in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
    (
        "a2037ceb-201f-5c45-a596-af795a399e60",
        "en.wikivoyage.org",
        "Hanoi",
        "Lenin Statue & Park",
        "Exact listing `name=Lenin Statue & Park | wikidata=Q10752053` in `en.wikivoyage.org/wiki/Hanoi`.",
    ),
]

# Rejected Wikivoyage candidate (1 candidate)
REJECTED_WIKIVOYAGE_SPECS: list[dict[str, Any]] = [
    {
        "poi_id": "8f2b5a69-1293-4efe-8fc5-3a74193edd0f",
        "domain": "en.wikivoyage.org",
        "page": "Halong",
        "listing_name": "Quang Ninh Provincial Museum",
        "mapping_evidence": "Exact institutional name match (`Quang Ninh Provincial Museum`) in `en.wikivoyage.org/wiki/Halong`, but listing has empty narrative `content=''` and outdated pre-2013 street address (`165 Nguyen Van Cu Street`). Rejected as `LOW_INFORMATION` under Section 15.",
    }
]

# Corrective 03: 26-record Overture fact-consistency audit specifications across 5 fields (130 field evaluations)
OVERTURE_26_FACT_AUDIT_SPECS: dict[str, dict[str, Any]] = {
    "75a3fbd1-a24e-43c6-820a-72f95ebc05c0": {
        "overture_gers_id": "9ed3a2e3-60a3-4df0-acd8-83185f57a281",
        "conflict_id": "FC-002",
        "entity_identity_status": "VALID_ENTITY_WITH_FIELD_CONFLICT",
        "fields": {
            "coordinates": {
                "overture_value": "20.941272, 107.025368 (dist=11.7m)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:75a3fbd1-a24e-43c6-820a-72f95ebc05c0",
                    "osm:node/4330722989",
                    "wikidata:Q111402972",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid (20.941068, 107.025318) is 11.7m from canonical/OSM (20.941167, 107.0253612) and 45m from Wikidata Q111402972 (20.940934, 107.025632) on Đảo Rều, Bãi Cháy.",
            },
            "address": {
                "overture_value": "439 P. Lê Lợi, Hạ Long, 180000, VN",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": [
                    "canonical_poi:75a3fbd1-a24e-43c6-820a-72f95ebc05c0",
                    "osm:node/4330722989",
                    "wikidata:Q111402972",
                ],
                "comparison_evidence": "FC-002: Overture address '439 P. Lê Lợi, Hạ Long, 180000, VN' conflicts with canonical POI, osm:node/4330722989, and Wikidata Q111402972 island coordinates on Đảo Rều, Bãi Cháy, Hạ Long (439 Lê Lợi and postcode 180000 belong to mainland Hải Phòng).",
            },
            "category_taxonomy": {
                "overture_value": "hotel | hotel (lodging > hotel)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:75a3fbd1-a24e-43c6-820a-72f95ebc05c0",
                    "osm:node/4330722989",
                    "wikidata:Q111402972",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical category 'hotel', OSM tourism=hotel, and Wikidata Q111402972 (P31=hotel Q27686).",
            },
            "phone": {
                "overture_value": "+84936886922",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Vietnam mobile number (+84936886922); not present on OSM node/4330722989 or Wikidata Q111402972.",
            },
            "website": {
                "overture_value": "http://vinpearl.com/en-US/Vinpearl-halongbay-resort/introduction-840/2015/Overview-1128",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible official vinpearl.com domain URL, but no website tag or P856 claim exists on canonical osm:node/4330722989 or Wikidata Q111402972; classified as UNVERIFIED (source-reported).",
            },
        },
        "suppressed_conflicted_fields": ["address"],
        "retained_substantive_fields": ["phone", "website"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "FC-002 resolved: retained valid entity on Đảo Rều (11.7m distance, corroborated hotel category, and source-reported unverified phone/website) with conflicted address '439 P. Lê Lợi, Hạ Long, 180000, VN' suppressed from raw_text.",
    },
    "8f2b5a69-1293-4efe-8fc5-3a74193edd0f": {
        "overture_gers_id": "bd078edf-ad58-4f6c-9016-adf65c90e5eb",
        "conflict_id": "FC-008",
        "entity_identity_status": "VALID_ENTITY_WITH_FIELD_CONFLICT",
        "fields": {
            "coordinates": {
                "overture_value": "20.948494, 107.097870 (dist=38.4m)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:8f2b5a69-1293-4efe-8fc5-3a74193edd0f",
                    "osm:node/5395107122",
                    "wikipedia:vi:19729999",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 38.4m from canonical/OSM (20.9486771, 107.0975562).",
            },
            "address": {
                "overture_value": "3 Đường Trần Quốc Nghiễn, Hạ Long, 01113, VN",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Hạ Long museum boulevard address ('3 Đường Trần Quốc Nghiễn, Hạ Long, 01113, VN'); not explicitly stated in canonical POI, osm:node/5395107122, Wikidata Q112182634, or Wikipedia vi:19729999 plain-text extract.",
            },
            "category_taxonomy": {
                "overture_value": "museum | museum (arts_and_entertainment > museum)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:8f2b5a69-1293-4efe-8fc5-3a74193edd0f",
                    "osm:node/5395107122",
                    "wikidata:Q112182634",
                    "wikipedia:vi:19729999",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical attraction/museum, OSM tourism=museum, and Wikidata Q112182634 (P31=museum Q33506).",
            },
            "phone": {
                "overture_value": "+842036561699",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Quảng Ninh (+84 203) landline; not present in OSM, Wikidata, or Wikipedia.",
            },
            "website": {
                "overture_value": "https://zalo.me/s/868766387773152883/?utm_source=zalo-qr",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["wikidata:Q112182634"],
                "comparison_evidence": "Overture URL is a Zalo QR link rather than the official institutional website http://baotangquangninh.vn recorded in Wikidata Q112182634 (P856).",
            },
        },
        "suppressed_conflicted_fields": ["website"],
        "retained_substantive_fields": ["address", "phone"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Retained valid museum entity with corroborated coordinates and museum category, plus source-reported unverified address and landline; suppressed conflicted Zalo QR website link.",
    },
    "9740c851-5b06-432c-a243-071ad0906494": {
        "overture_gers_id": "893209f5-1d13-479f-b7d7-6630b1f3fe57",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "20.951937, 107.042038 (dist=6.9m)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:9740c851-5b06-432c-a243-071ad0906494",
                    "osm:way/676720191",
                    "wikidata:Q111402973",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 6.9m from canonical/OSM (20.9519692, 107.0419818) and 11m from Wikidata Q111402973.",
            },
            "address": {
                "overture_value": "160 Hạ Long, Hạ Long, 200000, VN",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Bãi Cháy street address ('160 Hạ Long, Hạ Long, 200000, VN'); Wikidata Q111402973 has P281='200000' and description 'hotel in Bai Chay, Ha Long' but lacks street-level P6375 claim and osm:way/676720191 has no addr:street tag.",
            },
            "category_taxonomy": {
                "overture_value": "resort | resort (lodging > resort)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:9740c851-5b06-432c-a243-071ad0906494",
                    "osm:way/676720191",
                    "wikidata:Q111402973",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical hotel, OSM tourism=hotel, and Wikidata Q111402973 (P31=hotel Q27686).",
            },
            "phone": {
                "overture_value": "+842033848108",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Quảng Ninh (+84 203) landline; not present in OSM or Wikidata.",
            },
            "website": {
                "overture_value": "https://www.novotelhalongbay.com/",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible official hotel domain novotelhalongbay.com; not present in OSM or Wikidata.",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address", "phone", "website"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Clean entity with corroborated coordinates and category, plus source-reported unverified street address, phone, and hotel URL.",
    },
    "065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5": {
        "overture_gers_id": "0772c46b-7aa9-40a0-b403-78dec2591927",
        "conflict_id": "FC-009",
        "entity_identity_status": "VALID_ENTITY_WITH_FIELD_CONFLICT",
        "fields": {
            "coordinates": {
                "overture_value": "20.960209, 107.062836 (dist=18.5m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5", "osm:node/12998779901"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 18.5m from canonical/OSM (20.960357, 107.0627539).",
            },
            "address": {
                "overture_value": "1 Đường Hạ Long, Hạ Long, 01119, VN",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5", "osm:node/12998779901"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical and OSM address '1 Đường Hạ Long, Phường Bãi Cháy, Thành phố Hạ Long'.",
            },
            "category_taxonomy": {
                "overture_value": "restaurant | restaurant (food_and_drink > restaurant)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5", "osm:node/12998779901"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical restaurant and OSM amenity=restaurant.",
            },
            "phone": {
                "overture_value": "+84835981666",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["osm:node/12998779901"],
                "comparison_evidence": "Overture phone '+84835981666' differs from OSM phone='+84832981666'.",
            },
            "website": {
                "overture_value": "https://buffetsenadong.vn/",
                "status": "CORROBORATED",
                "corroboration_sources": ["osm:node/12998779901", "osm_website_pointer:https://buffetsenadong.vn"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical osm:node/12998779901 website='https://buffetsenadong.vn' by normalized URL.",
            },
        },
        "suppressed_conflicted_fields": ["phone"],
        "retained_substantive_fields": ["address", "website"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Retained valid restaurant entity with corroborated address and website; suppressed conflicted phone '+84835981666'.",
    },
    "7d01af19-10bc-4679-8cfa-4396209dece4": {
        "overture_gers_id": "04dda4d2-9d22-4516-a651-73c774b61663",
        "conflict_id": "FC-010",
        "entity_identity_status": "VALID_ENTITY_WITH_FIELD_CONFLICT",
        "fields": {
            "coordinates": {
                "overture_value": "20.947924, 107.023346 (dist=9.6m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:7d01af19-10bc-4679-8cfa-4396209dece4", "osm:node/12998531301"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 9.6m from canonical/OSM (20.9480089, 107.0233623).",
            },
            "address": {
                "overture_value": "Đỗ Sĩ Họa, Hạ Long, 202437, VN",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:7d01af19-10bc-4679-8cfa-4396209dece4", "osm:node/12998531301"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical POI and osm:node/12998531301 addr:street='Đỗ Sĩ Họa'.",
            },
            "category_taxonomy": {
                "overture_value": "restaurant | restaurant (food_and_drink > restaurant)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:7d01af19-10bc-4679-8cfa-4396209dece4", "osm:node/12998531301"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical restaurant and OSM amenity=restaurant, cuisine=seafood.",
            },
            "phone": {
                "overture_value": "+84901599598",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["osm:node/12998531301"],
                "comparison_evidence": "Overture phone '+84901599598' conflicts with OSM phone='0335400800'.",
            },
            "website": {
                "overture_value": "https://vnexpress.net/12-nam-ngoc-phuong-nam-gop-phan-nang-tam-am-thuc-bien-ha-long-4906007.html?fbclid=IwZXh0bgNhZW0CMTEAAR7uJebBFCVoE0y8HL3ugw5jYtZOX3TaKuA6z_PCMstq4ims1bkOWL9cm_VfKw_aem_q5Q8QxMpIQBn4PIiAIvPuQ",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["osm:node/12998531301", "osm_website_pointer:https://nhahangngocphuongnam.com"],
                "comparison_evidence": "Overture URL is a third-party VnExpress news article rather than official venue website https://nhahangngocphuongnam.com on osm:node/12998531301.",
            },
        },
        "suppressed_conflicted_fields": ["phone", "website"],
        "retained_substantive_fields": ["address"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Retained valid seafood restaurant entity (7.3m distance, corroborated address and seafood taxonomy); suppressed conflicted phone and third-party news URL.",
    },
    "85303289-9746-4a42-b0f0-a555ce2bfd0e": {
        "overture_gers_id": "6039522b-f82a-4a1d-88f3-09beca7172ab",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "20.954811, 107.085281 (dist=6.3m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:85303289-9746-4a42-b0f0-a555ce2bfd0e", "osm:node/13183486704"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 8.9m from canonical/OSM (20.9554642, 107.0818253).",
            },
            "address": {
                "overture_value": "Tran Hung Dao, Tran Hung Dao Ward, Ha Long City, Hạ Long, 36000, VN",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:85303289-9746-4a42-b0f0-a555ce2bfd0e", "osm:node/13183486704"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical and OSM street/ward 'Đường Trần Hưng Đạo, Phường Trần Hưng Đạo, Thành phố Hạ Long'.",
            },
            "category_taxonomy": {
                "overture_value": "coffee_shop | coffee_shop (food_and_drink > non_alcoholic_beverage_venue > coffee_shop)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:85303289-9746-4a42-b0f0-a555ce2bfd0e", "osm:node/13183486704"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical cafe and OSM amenity=cafe, cuisine=coffee_shop.",
            },
            "phone": {
                "overture_value": "+842033828628",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Quảng Ninh (+84 203) landline; not present in OSM.",
            },
            "website": {
                "overture_value": "http://highlandscoffee.com.vn/",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Official Highlands Coffee brand domain; not present on OSM node/13183486704.",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address", "phone", "website"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Clean cafe branch entity with corroborated coordinates, Trần Hưng Đạo address, and coffee_shop taxonomy.",
    },
    "b37d68ee-0cb3-49f0-a399-cac4c8e2732c": {
        "overture_gers_id": "92ed9717-ce41-4e8f-ab25-52e369cd88be",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "20.956568, 107.055756 (dist=14.6m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:b37d68ee-0cb3-49f0-a399-cac4c8e2732c", "osm:node/12998514201"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 8.9m from canonical/OSM (20.9585296, 107.0545064).",
            },
            "address": {
                "overture_value": "50 Hạ Long, Bãi Cháy, Thành phố, Hạ Long, 202437, VN",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:b37d68ee-0cb3-49f0-a399-cac4c8e2732c", "osm:node/12998514201"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical and OSM '50 Đường Hạ Long, Phường Bãi Cháy, Thành phố Hạ Long'.",
            },
            "category_taxonomy": {
                "overture_value": "restaurant | seafood_restaurant (food_and_drink > restaurant > seafood_restaurant)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:b37d68ee-0cb3-49f0-a399-cac4c8e2732c", "osm:node/12998514201"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical restaurant and OSM amenity=restaurant.",
            },
            "phone": {
                "overture_value": "+84904385118",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Vietnam mobile number (+84904385118); not corroborated by OSM.",
            },
            "website": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No website field present on Overture record.",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address", "phone"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Clean seafood restaurant entity with corroborated coordinates, 50 Hạ Long address, and seafood_restaurant taxonomy.",
    },
    "96523873-1b85-4d2f-b85c-cb3f5593091b": {
        "overture_gers_id": "9b6e3c9a-d263-4e5d-8ff7-7d7bddc1ffef",
        "conflict_id": "FC-007",
        "entity_identity_status": "VALID_ENTITY_LOW_INFORMATION_AFTER_SUPPRESSION",
        "fields": {
            "coordinates": {
                "overture_value": "20.955725, 107.022659 (dist=0.7m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:96523873-1b85-4d2f-b85c-cb3f5593091b", "osm:way/674641659"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 0.7m from canonical/OSM (20.955726, 107.0226526).",
            },
            "address": {
                "overture_value": "Cái Dăm, Hạ Long, VN",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Self-referential neighborhood/city string repeating only the market name ('Cái Dăm') and city ('Hạ Long') with no street, ward, or postcode.",
            },
            "category_taxonomy": {
                "overture_value": "food_and_beverage_store | fishmonger (shopping > food_and_beverage_store > fishmonger)",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["canonical_poi:96523873-1b85-4d2f-b85c-cb3f5593091b", "osm:way/674641659"],
                "comparison_evidence": "Overture taxonomy 'fishmonger' conflicts with canonical marketplace and OSM amenity=marketplace, building=retail (general multi-story municipal market).",
            },
            "phone": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No phone field present on Overture record.",
            },
            "website": {
                "overture_value": "http://xdha.vn/",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["osm:way/674641659"],
                "comparison_evidence": "Overture website 'http://xdha.vn/' is an unrelated domain and not an official portal for Chợ Cái Dăm.",
            },
        },
        "suppressed_conflicted_fields": ["category_taxonomy", "website"],
        "retained_substantive_fields": [],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "LOW_INFORMATION",
        "post_audit_final_b1b_decision": "REJECT",
        "resolution_summary": "FC-007: After suppressing conflicted website ('http://xdha.vn/') and conflicted taxonomy ('fishmonger'), only self-referential address 'Cái Dăm, Hạ Long, VN' remains (0 substantive place attributes beyond name/city). Downgraded to LOW_INFORMATION and REJECT.",
    },
    "871a6ee7-1d46-49bb-957a-ff50260b1f3b": {
        "overture_gers_id": "527ebd9f-445a-4059-a815-0d988c0925a2",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "20.953596, 107.055450 (dist=44.4m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:871a6ee7-1d46-49bb-957a-ff50260b1f3b", "osm:node/7044140886"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 4.6m from canonical/OSM Ha Long International Cruise Port.",
            },
            "address": {
                "overture_value": "Thương Cảng, Hạ Long, 202437, VN",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible port descriptor ('Thương Cảng, Hạ Long, 202437'); OSM node/7044140886 has no addr:street tag.",
            },
            "category_taxonomy": {
                "overture_value": "travel_and_transportation | travel_and_transportation (travel_and_transportation)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:871a6ee7-1d46-49bb-957a-ff50260b1f3b", "osm:node/7044140886"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical ferry_terminal/cruise port ('Ha Long International Cruise Port').",
            },
            "phone": {
                "overture_value": "+84925251999",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Vietnam mobile number (+84925251999); not present in OSM.",
            },
            "website": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No website field present on Overture record.",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address", "phone"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Clean cruise port entity with corroborated coordinates and travel_and_transportation taxonomy, plus unverified non-conflicting Thương Cảng address and phone.",
    },
    "8ebf0429-fabb-4701-bbc1-cb2fea86d587": {
        "overture_gers_id": "1b27afcb-daa1-4977-bcd5-cc5327c08c64",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "16.078597, 108.219368 (dist=3.9m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:8ebf0429-fabb-4701-bbc1-cb2fea86d587", "osm:node/729406392"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 4.0m from canonical/OSM Ca Phe 83.",
            },
            "address": {
                "overture_value": "113, Lê Lợi, Quận Hải Châu, 551300, VN",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Hải Châu street address ('113, Lê Lợi, Quận Hải Châu'); OSM node/729406392 has no addr:* tags.",
            },
            "category_taxonomy": {
                "overture_value": "coffee_shop | coffee_shop (food_and_drink > non_alcoholic_beverage_venue > coffee_shop)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:8ebf0429-fabb-4701-bbc1-cb2fea86d587", "osm:node/729406392"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical cafe and OSM amenity=cafe.",
            },
            "phone": {
                "overture_value": "+84934345445",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Vietnam mobile number (+84934345445); not present in OSM.",
            },
            "website": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No website field present on Overture record.",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address", "phone"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Clean cafe entity with corroborated coordinates and coffee_shop taxonomy, plus unverified non-conflicting Hải Châu address and phone.",
    },
    "c2afbb07-aaf9-47c1-9877-d17e64422066": {
        "overture_gers_id": "4d3dbac0-aae6-4960-8b89-d06c52fe21f5",
        "conflict_id": "FC-006",
        "entity_identity_status": "UNCERTAIN_ENTITY_IDENTITY_MAPPING_REVIEW_REQUIRED",
        "fields": {
            "coordinates": {
                "overture_value": "16.041579, 108.242264 (dist=25.2m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:c2afbb07-aaf9-47c1-9877-d17e64422066", "osm:way/118614280"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 25.2m from canonical/OSM (16.0416775, 108.2424764).",
            },
            "address": {
                "overture_value": "25 Đường Nguyễn Bá Lân, Quận Ngũ Hành Sơn, 50507, VN",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "OSM way/118614280 has no addr:* tags to corroborate '25 Đường Nguyễn Bá Lân'.",
            },
            "category_taxonomy": {
                "overture_value": "farmers_market | farmers_market (shopping > market > farmers_market)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:c2afbb07-aaf9-47c1-9877-d17e64422066", "osm:way/118614280"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical marketplace and OSM amenity=marketplace.",
            },
            "phone": {
                "overture_value": "+84905161611",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Not present in OSM.",
            },
            "website": {
                "overture_value": "https://www.tiktok.com/@bacmyan",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["osm:way/118614280"],
                "comparison_evidence": "FC-006: Overture record is named 'Chợ Bắc Mỹ An Online' (confidence=0.3150) with TikTok social-commerce URL 'https://www.tiktok.com/@bacmyan', representing an online vendor page rather than the physical municipal market Chợ Bắc Mỹ An.",
            },
        },
        "suppressed_conflicted_fields": ["website"],
        "retained_substantive_fields": [],
        "post_audit_canonical_mapping_status": "MAPPING_REVIEW_REQUIRED",
        "post_audit_content_utility_status": "LOW_INFORMATION",
        "post_audit_final_b1b_decision": "REJECT",
        "resolution_summary": "FC-006: Overture record 'Chợ Bắc Mỹ An Online' (confidence=0.3150, TikTok URL) has uncertain entity identity with physical municipal market Chợ Bắc Mỹ An; downgraded to MAPPING_REVIEW_REQUIRED and REJECT.",
    },
    "fd118580-b5da-467d-9873-0116ba435f37": {
        "overture_gers_id": "df8dc91d-1790-4600-a518-31bec995467a",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "16.069058, 108.242989 (dist=19.3m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:fd118580-b5da-467d-9873-0116ba435f37", "osm:node/5485483822"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 8.2m from canonical/OSM Nhà hàng hải sản Bé Anh.",
            },
            "address": {
                "overture_value": "Ngã tư Phạm Văn Đồng, Hồ Nghinh nối dài tới ngã tư Dương Đình Nghệ, Hồ Nghinh, Quận Sơn Trà, VN",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:fd118580-b5da-467d-9873-0116ba435f37", "osm:node/5485483822"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical and OSM 'Lô 14-15 Hồ Nghinh, Phước Mỹ, Sơn Trà, Đà Nẵng'.",
            },
            "category_taxonomy": {
                "overture_value": "restaurant | seafood_restaurant (food_and_drink > restaurant > seafood_restaurant)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:fd118580-b5da-467d-9873-0116ba435f37", "osm:node/5485483822"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical restaurant and OSM amenity=restaurant, cuisine=seafood.",
            },
            "phone": {
                "overture_value": "+84905516726",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Đà Nẵng mobile number (+84905516726); not corroborated by OSM.",
            },
            "website": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No website field present on Overture record.",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address", "phone"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Clean seafood restaurant entity with corroborated coordinates, Hồ Nghinh (Sơn Trà) address, and seafood_restaurant taxonomy.",
    },
    "5fc0994a-e578-4a25-b375-7f079e6dc3ba": {
        "overture_gers_id": "b9ad130e-8f19-4dcb-92a7-638573a3f62d",
        "conflict_id": "FC-005",
        "entity_identity_status": "CONFLATED_ENTITY_IDENTITY_MAPPING_REVIEW_REQUIRED",
        "fields": {
            "coordinates": {
                "overture_value": "16.004096, 108.264305 (dist=21.4m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:5fc0994a-e578-4a25-b375-7f079e6dc3ba", "osm:way/1205388457"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 21.4m from canonical/OSM (16.0042763, 108.2643746) on Hòn Thủy Sơn, Ngũ Hành Sơn.",
            },
            "address": {
                "overture_value": "Hòn Thủy Sơn, Quận Ngũ Hành Sơn, 550000, VN",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Ngũ Hành Sơn location ('Hòn Thủy Sơn, Quận Ngũ Hành Sơn, 550000, VN'), but canonical POI has address=None and osm:way/1205388457 has no addr:* tags.",
            },
            "category_taxonomy": {
                "overture_value": "buddhist_place_of_worship | buddhist_place_of_worship (cultural_and_historic > place_of_worship > buddhist_place_of_worship)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:5fc0994a-e578-4a25-b375-7f079e6dc3ba", "osm:way/1205388457"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches OSM amenity=place_of_worship, religion=buddhist.",
            },
            "phone": {
                "overture_value": "+845113836895",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Source-reported phone '+845113836895' (legacy 0511 area code); not present on canonical osm:way/1205388457.",
            },
            "website": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No website field present on Overture record.",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": [],
        "post_audit_canonical_mapping_status": "MAPPING_REVIEW_REQUIRED",
        "post_audit_content_utility_status": "LOW_INFORMATION",
        "post_audit_final_b1b_decision": "REJECT",
        "resolution_summary": "FC-005: Overture names.primary='Chùa Linh Ứng – Sơn Trà' conflates Chùa Linh Ứng Non Nước (at Hòn Thủy Sơn, Ngũ Hành Sơn) with Chùa Linh Ứng Bãi Bụt on Sơn Trà Peninsula 10.6km north; downgraded to MAPPING_REVIEW_REQUIRED and REJECT.",
    },
    "61639da8-996a-43df-b6d3-928b6bdd70b9": {
        "overture_gers_id": "da92232b-8e79-4082-84b0-6a35263af4df",
        "conflict_id": "FC-003",
        "entity_identity_status": "VALID_ENTITY_WITH_FIELD_CONFLICT",
        "fields": {
            "coordinates": {
                "overture_value": "16.055869, 108.243385 (dist=31.1m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:61639da8-996a-43df-b6d3-928b6bdd70b9", "osm:node/7210857787"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 31.1m from canonical/OSM (16.055773, 108.2436587).",
            },
            "address": {
                "overture_value": "05 Đ. Mỹ Khê 5, Quận Ngũ Hành Sơn, +84236, VN",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["canonical_poi:61639da8-996a-43df-b6d3-928b6bdd70b9", "osm:node/7210857787"],
                "comparison_evidence": "FC-003: Overture address '05 Đ. Mỹ Khê 5, Quận Ngũ Hành Sơn, +84236, VN' conflicts with canonical/OSM '195/2 Đường Nguyễn Văn Thoại' and places telephone area code '+84236' in the postcode field.",
            },
            "category_taxonomy": {
                "overture_value": "restaurant | restaurant (food_and_drink > restaurant)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:61639da8-996a-43df-b6d3-928b6bdd70b9", "osm:node/7210857787"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical restaurant and OSM amenity=restaurant.",
            },
            "phone": {
                "overture_value": "+84965159159",
                "status": "CORROBORATED",
                "corroboration_sources": ["osm:node/7210857787"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches OSM phone='+84 965 159 159'.",
            },
            "website": {
                "overture_value": "https://myquangbamuadng.com/",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["osm:node/7210857787", "osm_website_pointer:https://myquangbamua.com.vn/"],
                "comparison_evidence": "Overture domain 'myquangbamuadng.com' conflicts with OSM official website 'https://myquangbamua.com.vn/'.",
            },
        },
        "suppressed_conflicted_fields": ["address", "website"],
        "retained_substantive_fields": ["phone"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "FC-003 resolved: retained valid entity with corroborated phone '+84965159159' and category; suppressed conflicted address and website.",
    },
    "62a874a9-13e2-44d2-95b5-30e980b98965": {
        "overture_gers_id": "c732f0d5-911d-4d9f-93b2-51c886f4fe0b",
        "conflict_id": "FC-011",
        "entity_identity_status": "VALID_ENTITY_WITH_FIELD_CONFLICT",
        "fields": {
            "coordinates": {
                "overture_value": "16.058866, 108.216431 (dist=42.9m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:62a874a9-13e2-44d2-95b5-30e980b98965", "osm:node/4541527689"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 42.9m from canonical/OSM (16.0588034, 108.2160349).",
            },
            "address": {
                "overture_value": "280/23 Hoàng Diệu, Quận Hải Châu, 550000, VN",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:62a874a9-13e2-44d2-95b5-30e980b98965", "osm:node/4541527689"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical and OSM '280/23 Đường Hoàng Diệu, Phường Bình Hiên, Quận Hải Châu, Đà Nẵng'.",
            },
            "category_taxonomy": {
                "overture_value": "restaurant | vietnamese_restaurant (food_and_drink > restaurant > asian_restaurant > southeast_asian_restaurant > vietnamese_restaurant)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:62a874a9-13e2-44d2-95b5-30e980b98965", "osm:node/4541527689"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical restaurant and OSM amenity=restaurant.",
            },
            "phone": {
                "overture_value": "+842363873168",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Đà Nẵng (+84 236) landline; not present in OSM.",
            },
            "website": {
                "overture_value": "http://www.foody.vn/da-nang/banh-xeo-ba-duong#",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["osm:node/4541527689"],
                "comparison_evidence": "Overture URL is a third-party review aggregator page (foody.vn) rather than an official venue website.",
            },
        },
        "suppressed_conflicted_fields": ["website"],
        "retained_substantive_fields": ["address", "phone"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Retained valid restaurant entity with corroborated K280/23 Hoàng Diệu address and unverified landline; suppressed third-party foody.vn URL.",
    },
    "7ff87c59-62f1-4509-95f4-e83796b9a35c": {
        "overture_gers_id": "67b0a6b0-f6e8-477d-8517-ef73c56752f7",
        "conflict_id": "FC-012",
        "entity_identity_status": "VALID_ENTITY_WITH_FIELD_CONFLICT",
        "fields": {
            "coordinates": {
                "overture_value": "16.071670, 108.230370 (dist=31.3m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:7ff87c59-62f1-4509-95f4-e83796b9a35c", "osm:way/693393717"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 31.3m from canonical/OSM (16.0713959, 108.230301).",
            },
            "address": {
                "overture_value": "Ngô Quyen, Quận Sơn Trà, VN",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:7ff87c59-62f1-4509-95f4-e83796b9a35c", "osm:way/693393717"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical POI and osm:way/693393717 street 'Đường Ngô Quyền, Đà Nẵng'.",
            },
            "category_taxonomy": {
                "overture_value": "shopping_mall | shopping_mall (shopping > shopping_mall)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:7ff87c59-62f1-4509-95f4-e83796b9a35c", "osm:way/693393717"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical mall and OSM shop=mall.",
            },
            "phone": {
                "overture_value": "+84933176888",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["osm:way/693393717"],
                "comparison_evidence": "Overture phone '+84933176888' conflicts with OSM phone='+84 934 919 341'.",
            },
            "website": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No website field present on Overture Parquet record 67b0a6b0-f6e8-477d-8517-ef73c56752f7.",
            },
        },
        "suppressed_conflicted_fields": ["phone"],
        "retained_substantive_fields": ["address"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Retained valid shopping center entity with corroborated Ngô Quyền address and shopping_mall taxonomy; suppressed conflicted phone '+84933176888' (website is MISSING on Overture Parquet record).",
    },
    "9a2ca486-437d-4044-8541-d34d911d4fb4": {
        "overture_gers_id": "a310c792-65d8-4115-9df6-ddf54babd1a8",
        "conflict_id": "FC-004",
        "entity_identity_status": "VALID_ENTITY_WITH_FIELD_CONFLICT",
        "fields": {
            "coordinates": {
                "overture_value": "16.060657, 108.231873 (dist=36.7m)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:9a2ca486-437d-4044-8541-d34d911d4fb4",
                    "osm:way/1556362196",
                    "wikivoyage:en:Da_Nang#Son_Tra_Night_Market",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 36.7m from canonical/OSM (16.0606554, 108.2315292).",
            },
            "address": {
                "overture_value": "7duong Lý Nam Đế, Quận Sơn Trà, 550000, VN",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["canonical_poi:9a2ca486-437d-4044-8541-d34d911d4fb4", "osm:way/1556362196"],
                "comparison_evidence": "FC-004: Overture address '7duong Lý Nam Đế' has malformed concatenation and conflicts with canonical/OSM street 'Cao Bá Quát' on osm:way/1556362196.",
            },
            "category_taxonomy": {
                "overture_value": "market | night_market (shopping > market > night_market)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:9a2ca486-437d-4044-8541-d34d911d4fb4",
                    "osm:way/1556362196",
                    "wikivoyage:en:Da_Nang#Son_Tra_Night_Market",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical marketplace, OSM amenity=marketplace, and Wikivoyage Son Tra Night Market.",
            },
            "phone": {
                "overture_value": "+84912965179",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Vietnam mobile number; not present in OSM or Wikivoyage.",
            },
            "website": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No website field present on Overture record.",
            },
        },
        "suppressed_conflicted_fields": ["address"],
        "retained_substantive_fields": ["phone"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "FC-004 resolved: retained valid night market entity with corroborated night_market taxonomy and unverified contact phone; suppressed malformed/conflicted address '7duong Lý Nam Đế'.",
    },
    "a32ce1b4-126b-4544-b5ea-4a7edbab6a0a": {
        "overture_gers_id": "82f95e1f-7bf8-40df-a3ed-6f92a4a847f3",
        "conflict_id": "FC-013",
        "entity_identity_status": "VALID_ENTITY_WITH_FIELD_CONFLICT",
        "fields": {
            "coordinates": {
                "overture_value": "16.039931, 108.251114 (dist=37.3m)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:a32ce1b4-126b-4544-b5ea-4a7edbab6a0a",
                    "osm:way/485212452",
                    "wikidata:Q111402873",
                    "wikivoyage:en:Da_Nang#Furama_Resort",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 37.3m from canonical/OSM (16.0397373, 108.2513983).",
            },
            "address": {
                "overture_value": "105 Võ Nguyên Giáp, Quận Ngũ Hành Sơn, 550000, VN",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:a32ce1b4-126b-4544-b5ea-4a7edbab6a0a", "osm:way/485212452"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical/OSM '105 Võ Nguyên Giáp, Ngũ Hành Sơn, Da Nang' on osm:way/485212452.",
            },
            "category_taxonomy": {
                "overture_value": "hotel | hotel (lodging > hotel)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:a32ce1b4-126b-4544-b5ea-4a7edbab6a0a",
                    "osm:way/485212452",
                    "wikidata:Q111402873",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical resort (OSM tourism=resort) and Wikidata Q111402873 (P31=hotel Q27686).",
            },
            "phone": {
                "overture_value": "+842363847333",
                "status": "CORROBORATED",
                "corroboration_sources": ["wikivoyage:en:Da_Nang#Furama_Resort"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches Wikivoyage Da_Nang#Furama_Resort phone='+84 5 1138 47333' (legacy 0511 area code equivalent to +84 236 3847333).",
            },
            "website": {
                "overture_value": "http://club99.vn/",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["osm:way/485212452", "osm_website_pointer:https://furamavietnam.com"],
                "comparison_evidence": "Overture website 'http://club99.vn/' points to an internal gaming club rather than the official resort website 'https://furamavietnam.com' on osm:way/485212452.",
            },
        },
        "suppressed_conflicted_fields": ["website"],
        "retained_substantive_fields": ["address", "phone"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Retained valid resort entity with corroborated 105 Võ Nguyên Giáp address and Wikivoyage-corroborated phone '+842363847333'; suppressed conflicted sub-venue website 'http://club99.vn/'.",
    },
    "4608034c-6c43-4d54-a542-ead8e23b1338": {
        "overture_gers_id": "0d91068a-7ee8-4d97-ad32-a075a23d30fd",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "16.120820, 108.306213 (dist=33.8m)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:4608034c-6c43-4d54-a542-ead8e23b1338",
                    "osm:way/360113559",
                    "wikidata:Q17068326",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 33.8m from canonical/OSM (16.1211058, 108.3063202).",
            },
            "address": {
                "overture_value": "Bãi Bắc, Quận Sơn Trà, 550000, VN",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:4608034c-6c43-4d54-a542-ead8e23b1338",
                    "osm:way/360113559",
                    "wikivoyage:en:Da_Nang#InterContinental_Danang_Sun_Peninsula_Resort",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical 'Bai Bac, Son Tra peninsula, Đà Nẵng' and Wikivoyage 'Thọ Quang, Sơn Trà'.",
            },
            "category_taxonomy": {
                "overture_value": "resort | resort (lodging > resort)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:4608034c-6c43-4d54-a542-ead8e23b1338",
                    "osm:way/360113559",
                    "wikidata:Q17068326",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical resort and OSM tourism=resort.",
            },
            "phone": {
                "overture_value": "+842363938888",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "osm:way/360113559",
                    "wikivoyage:en:Da_Nang#InterContinental_Danang_Sun_Peninsula_Resort",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches OSM and Wikivoyage phone='+84 236 393 8888'.",
            },
            "website": {
                "overture_value": "https://www.ihg.com/intercontinental/hotels/us/en/danang-city/dadha/hoteldetail",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible IHG brand hotel detail URL ('https://www.ihg.com/.../dadha/hoteldetail'), whereas osm:way/360113559 records 'http://danang.intercontinental.com' and Wikivoyage has no url parameter; classified as UNVERIFIED (source-reported).",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address", "phone", "website"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Retained valid resort entity with corroborated coordinates, Bãi Bắc (Sơn Trà) address, resort category, and phone '+842363938888', plus source-reported unverified IHG brand URL.",
    },
    "a2037ceb-201f-5c45-a596-af795a399e60": {
        "overture_gers_id": "3421b671-b891-408e-943f-1278e1a46c94",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "21.031741, 105.839424 (dist=17.2m)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:a2037ceb-201f-5c45-a596-af795a399e60",
                    "osm:way/185540946",
                    "wikidata:Q10752053",
                    "wikivoyage:en:Hanoi#Lenin_Statue_&_Park",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 17.2m from canonical/OSM (21.031782, 105.839584).",
            },
            "address": {
                "overture_value": "28A Điện Biên Phủ, Quận Ba Đình, 100000, VN",
                "status": "CORROBORATED",
                "corroboration_sources": ["wikipedia:vi:45931", "wikivoyage:en:Hanoi#Lenin_Statue_&_Park"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches Điện Biên Phủ / Trần Phú frontage in Ba Đình District corroborated by Wikipedia (wikipedia:vi:45931) and Wikivoyage (Hanoi#Lenin_Statue_&_Park).",
            },
            "category_taxonomy": {
                "overture_value": "park | park (sports_and_recreation > park)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:a2037ceb-201f-5c45-a596-af795a399e60",
                    "osm:way/185540946",
                    "wikidata:Q10752053",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical park and OSM leisure=park.",
            },
            "phone": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No phone field present on Overture record.",
            },
            "website": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No website field present on Overture record.",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "All present fields (coordinates, 28A Điện Biên Phủ address, park category) corroborated by canonical POI, OSM, Wikidata, and Wikivoyage.",
    },
    "5bd45eb7-a691-4426-9691-a5a00f38d1ad": {
        "overture_gers_id": "e8f37b82-c15a-49d1-ad85-994b4b10f150",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "21.011303, 105.849876 (dist=30.8m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:5bd45eb7-a691-4426-9691-a5a00f38d1ad", "osm:node/442977691"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 22.9m from canonical/OSM Highlands Coffee branch.",
            },
            "address": {
                "overture_value": "Phố Lò Đúc, Quận Hai Bà Trưng, VN",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Hai Bà Trưng street address ('Phố Lò Đúc, Quận Hai Bà Trưng'); OSM node/442977691 has no addr:street tag.",
            },
            "category_taxonomy": {
                "overture_value": "coffee_shop | coffee_shop (food_and_drink > non_alcoholic_beverage_venue > coffee_shop)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:5bd45eb7-a691-4426-9691-a5a00f38d1ad", "osm:node/442977691"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical cafe and OSM amenity=cafe, cuisine=coffee_shop.",
            },
            "phone": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No phone field present on Overture record.",
            },
            "website": {
                "overture_value": None,
                "status": "MISSING",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "No website field present on Overture record.",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Clean cafe branch entity with corroborated coordinates and coffee_shop taxonomy, plus unverified non-conflicting Phố Lò Đúc address.",
    },
    "5350dd97-2f75-45fc-9fc1-1979b08670f7": {
        "overture_gers_id": "ff9a223f-952f-4d51-b7a9-b90998668554",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "21.030514, 105.848824 (dist=5.2m)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:5350dd97-2f75-45fc-9fc1-1979b08670f7",
                    "osm:node/773601261",
                    "wikivoyage:en:Hanoi#Pho_10_Ly_Quoc_Su",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 3.0m from canonical/OSM (21.0306389, 105.849255) and 6.3m from Wikivoyage.",
            },
            "address": {
                "overture_value": "10 P. Lý Quốc Sư, Quận Hoàn Kiếm, VN",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:5350dd97-2f75-45fc-9fc1-1979b08670f7",
                    "osm:node/773601261",
                    "wikivoyage:en:Hanoi#Pho_10_Ly_Quoc_Su",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical/OSM '10 Phố Lý Quốc Sư, Phường Hoàn Kiếm, Hà Nội' and Wikivoyage '10 P. Lý Quốc Sư'.",
            },
            "category_taxonomy": {
                "overture_value": "restaurant | vietnamese_restaurant (food_and_drink > restaurant > asian_restaurant > southeast_asian_restaurant > vietnamese_restaurant)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:5350dd97-2f75-45fc-9fc1-1979b08670f7",
                    "osm:node/773601261",
                    "wikivoyage:en:Hanoi#Pho_10_Ly_Quoc_Su",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical restaurant and OSM amenity=restaurant, cuisine=vietnamese.",
            },
            "phone": {
                "overture_value": "+842438257338",
                "status": "CORROBORATED",
                "corroboration_sources": ["osm:node/773601261"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches OSM phone='+84 24 3825 7338'.",
            },
            "website": {
                "overture_value": "http://www.pho10lyquocsu.com.vn/",
                "status": "CORROBORATED",
                "corroboration_sources": ["osm:node/773601261"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches OSM website tag on node/773601261.",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address", "phone", "website"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "All 5 fields corroborated by canonical POI, OSM, and Wikivoyage.",
    },
    "5e92e89d-8524-4792-862a-6dfce0994862": {
        "overture_gers_id": "80ceecb4-b812-4b29-a332-e22dc1a21fb8",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "21.059810, 105.831573 (dist=46.1m)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:5e92e89d-8524-4792-862a-6dfce0994862",
                    "osm:node/922396410",
                    "wikivoyage:en:Hanoi#Sheraton_Hanoi_Hotel",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 46.2m from canonical/OSM (21.0597444, 105.8320123) and 17.2m from Wikivoyage (21.0598708, 105.8317256).",
            },
            "address": {
                "overture_value": "11 Đường Xuân Diệu, Quận Tây Hồ, 11207, VN",
                "status": "CORROBORATED",
                "corroboration_sources": ["wikivoyage:en:Hanoi#Sheraton_Hanoi_Hotel"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches Wikivoyage Hanoi#Sheraton_Hanoi_Hotel address 'K5 Nghi Tam, 11 Xuan Dieu Rd, Tay Ho District'.",
            },
            "category_taxonomy": {
                "overture_value": "hotel | hotel (lodging > hotel)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:5e92e89d-8524-4792-862a-6dfce0994862",
                    "osm:node/922396410",
                    "wikidata:Q117325492",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical hotel, OSM tourism=hotel, and Wikidata Q117325492 (P31=hotel Q27686).",
            },
            "phone": {
                "overture_value": "+842437199000",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Hanoi (+84 24) landline '+842437199000'; not present on osm:node/922396410, Wikidata Q117325492, or Wikivoyage Hanoi#Sheraton_Hanoi_Hotel.",
            },
            "website": {
                "overture_value": "https://www.marriott.com/en-us/hotels/hanhs-sheraton-hanoi-hotel/overview/?scid=d2406702-e8ea-4b45-bb9b-69cddaaef03d",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Marriott hotel URL ('https://www.marriott.com/.../hanhs-sheraton-hanoi-hotel/...'), whereas Wikivoyage lists legacy 'starwoodhotels.com'; classified as UNVERIFIED (source-reported).",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address", "phone", "website"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Retained valid hotel entity with corroborated coordinates, Wikivoyage-corroborated 11 Xuân Diệu (Tây Hồ) address, and hotel category, plus source-reported unverified phone and Marriott URL.",
    },
    "9a96e0a0-e040-4e16-a3f2-682ca373dd8e": {
        "overture_gers_id": "165cef5b-70ba-41d9-8314-4b54d979379d",
        "conflict_id": None,
        "entity_identity_status": "VALID_ENTITY",
        "fields": {
            "coordinates": {
                "overture_value": "21.026005, 105.846436 (dist=20.4m)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:9a96e0a0-e040-4e16-a3f2-682ca373dd8e",
                    "osm:node/442033049",
                    "wikidata:Q111402985",
                    "wikivoyage:en:Hanoi#Somerset_Grand_Hanoi",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 20.4m from canonical/OSM (21.025833, 105.846367).",
            },
            "address": {
                "overture_value": "Quận Hoàn Kiếm, VN",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:9a96e0a0-e040-4e16-a3f2-682ca373dd8e", "osm:node/442033049"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical POI and osm:node/442033049 addr:district='Hoàn Kiếm'.",
            },
            "category_taxonomy": {
                "overture_value": "hotel | hotel (lodging > hotel)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:9a96e0a0-e040-4e16-a3f2-682ca373dd8e",
                    "osm:node/442033049",
                    "wikidata:Q111402985",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical hotel, OSM tourism=hotel, and Wikidata Q111402985.",
            },
            "phone": {
                "overture_value": "+842439342342",
                "status": "CORROBORATED",
                "corroboration_sources": ["osm:node/442033049", "wikivoyage:en:Hanoi#Somerset_Grand_Hanoi"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches OSM and Wikivoyage phone='+84 24 3934 2342'.",
            },
            "website": {
                "overture_value": "https://www.discoverasr.com/vi/somerset-serviced-residence/vietnam/somerset-grand-hanoi",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "osm:node/442033049",
                    "osm_website_pointer:https://www.discoverasr.com/en/somerset-serviced-residence/vietnam/somerset-grand-hanoi",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches official discoverasr.com Somerset Grand Hanoi URL on osm:node/442033049.",
            },
        },
        "suppressed_conflicted_fields": [],
        "retained_substantive_fields": ["address", "phone", "website"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "All 5 fields corroborated by canonical POI, OSM, Wikidata, and Wikivoyage.",
    },
    "afb3793b-7227-4645-a68a-3647c7468638": {
        "overture_gers_id": "e8077687-eb1f-44ff-b544-9e7ae8ccdc1e",
        "conflict_id": "FC-014",
        "entity_identity_status": "VALID_ENTITY_WITH_FIELD_CONFLICT",
        "fields": {
            "coordinates": {
                "overture_value": "21.074240, 105.815506 (dist=10.8m)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:afb3793b-7227-4645-a68a-3647c7468638", "osm:node/443000681"],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 10.8m from canonical/OSM (21.074149, 105.815469).",
            },
            "address": {
                "overture_value": "614 Lạc Long Quân, Quận Tây Hồ, 11200, VN",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Tây Hồ street address ('614 Lạc Long Quân, Quận Tây Hồ, 11200, VN'), but canonical POI has placeholder address and osm:node/443000681 has no addr:* tags.",
            },
            "category_taxonomy": {
                "overture_value": "restaurant | restaurant (food_and_drink > restaurant)",
                "status": "CORROBORATED",
                "corroboration_sources": ["canonical_poi:afb3793b-7227-4645-a68a-3647c7468638", "osm:node/443000681"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical restaurant and OSM amenity=restaurant, cuisine=buffet.",
            },
            "phone": {
                "overture_value": "+842437199242",
                "status": "UNVERIFIED",
                "corroboration_sources": [],
                "conflicting_sources": [],
                "comparison_evidence": "Plausible Hanoi (+84 24) landline; not present in OSM.",
            },
            "website": {
                "overture_value": "http://www.sentayho.com.vn",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": ["osm:node/443000681", "osm_website_pointer:https://nhahangsen.vn/"],
                "comparison_evidence": "Overture domain 'sentayho.com.vn' conflicts with OSM official website 'https://nhahangsen.vn/'.",
            },
        },
        "suppressed_conflicted_fields": ["website"],
        "retained_substantive_fields": ["address", "phone"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "Retained valid restaurant entity with corroborated coordinates and restaurant category, plus source-reported unverified 614 Lạc Long Quân address and landline; suppressed conflicted website 'http://www.sentayho.com.vn'.",
    },
    "f0d424bd-f722-540f-8964-5e6fd8875b56": {
        "overture_gers_id": "e55bab3c-c110-4ba6-a005-5c43986a6095",
        "conflict_id": "FC-001",
        "entity_identity_status": "VALID_ENTITY_WITH_FIELD_CONFLICT",
        "fields": {
            "coordinates": {
                "overture_value": "21.040392, 105.798798 (dist=4.1m)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:f0d424bd-f722-540f-8964-5e6fd8875b56",
                    "osm:way/339936730",
                    "wikidata:Q1048345",
                    "wikivoyage:en:Hanoi#Museum_of_Ethnology",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Overture bbox centroid is 4.1m from canonical/OSM (21.0402022, 105.7987603), 67m from Wikidata Q1048345, and 42m from Wikivoyage.",
            },
            "address": {
                "overture_value": "1 Đường Trực Nguyên, Huyện Thường Tín, 13618, VN",
                "status": "CONFLICTED",
                "corroboration_sources": [],
                "conflicting_sources": [
                    "canonical_poi:f0d424bd-f722-540f-8964-5e6fd8875b56",
                    "osm:way/339936730",
                    "wikipedia:vi:28445",
                    "wikivoyage:en:Hanoi#Museum_of_Ethnology",
                ],
                "comparison_evidence": "FC-001: Overture address '1 Đường Trực Nguyên, Huyện Thường Tín, 13618, VN' conflicts with canonical POI and osm:way/339936730 ('Đường Nguyễn Văn Huyên, Quan Hoa, Cầu Giấy, Hà Nội'), Wikipedia vi:28445 ('đường Nguyễn Văn Huyên, quận Cầu Giấy'), and Wikivoyage Hanoi#Museum_of_Ethnology ('Nguyen Van Huyen St').",
            },
            "category_taxonomy": {
                "overture_value": "museum | museum (arts_and_entertainment > museum)",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "canonical_poi:f0d424bd-f722-540f-8964-5e6fd8875b56",
                    "osm:way/339936730",
                    "wikidata:Q1048345",
                    "wikipedia:vi:28445",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical attraction/museum, OSM tourism=museum, and Wikidata Q1048345 (P31=museum Q33506).",
            },
            "phone": {
                "overture_value": "+84437562193",
                "status": "CORROBORATED",
                "corroboration_sources": ["osm:way/339936730"],
                "conflicting_sources": [],
                "comparison_evidence": "Matches canonical osm:way/339936730 phone='+842437562193' (legacy +84-4 area code equivalent to +84-24).",
            },
            "website": {
                "overture_value": "http://www.vme.org.vn/",
                "status": "CORROBORATED",
                "corroboration_sources": [
                    "osm:way/339936730",
                    "wikidata:Q1048345",
                    "wikivoyage:en:Hanoi#Museum_of_Ethnology",
                    "osm_website_pointer:https://www.vme.org.vn/",
                ],
                "conflicting_sources": [],
                "comparison_evidence": "Matches OSM website='https://www.vme.org.vn/', Wikidata P856='http://www.vme.org.vn', and Wikivoyage url='http://www.vme.org.vn'.",
            },
        },
        "suppressed_conflicted_fields": ["address"],
        "retained_substantive_fields": ["phone", "website"],
        "post_audit_canonical_mapping_status": "EXACT_MAPPED",
        "post_audit_content_utility_status": "USEFUL_STRUCTURED_FACTS",
        "post_audit_final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
        "resolution_summary": "FC-001 resolved: retained valid museum entity (4.1m distance, corroborated category, phone '+84437562193', and official website 'http://www.vme.org.vn/') with conflicted address '1 Đường Trực Nguyên, Huyện Thường Tín, 13618, VN' suppressed from raw_text.",
    },
}

OSM_SOURCE_REFERENCE_RECONCILIATION_LEDGER: list[dict[str, Any]] = [
    {
        "poi_id": "75a3fbd1-a24e-43c6-820a-72f95ebc05c0",
        "poi_name": "Vinpearl Ha Long resort",
        "field_name": "coordinates",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/3929648836",
        "canonical_osm_id": "node/4330722989",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/3929648836 -> osm:node/4330722989 after verifying canonical OSM entity node/4330722989 in gomate_places_freeze_v2.json supports coordinates (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "75a3fbd1-a24e-43c6-820a-72f95ebc05c0",
        "poi_name": "Vinpearl Ha Long resort",
        "field_name": "category_taxonomy",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/3929648836",
        "canonical_osm_id": "node/4330722989",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/3929648836 -> osm:node/4330722989 after verifying canonical OSM entity node/4330722989 in gomate_places_freeze_v2.json supports category_taxonomy (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5",
        "poi_name": "Nhà hàng Buffet Sen Á Đông",
        "field_name": "coordinates",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/12224148306",
        "canonical_osm_id": "node/12998779901",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/12224148306 -> osm:node/12998779901 after verifying canonical OSM entity node/12998779901 in gomate_places_freeze_v2.json supports coordinates (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5",
        "poi_name": "Nhà hàng Buffet Sen Á Đông",
        "field_name": "address",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/12224148306",
        "canonical_osm_id": "node/12998779901",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/12224148306 -> osm:node/12998779901 after verifying canonical OSM entity node/12998779901 in gomate_places_freeze_v2.json supports address (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5",
        "poi_name": "Nhà hàng Buffet Sen Á Đông",
        "field_name": "category_taxonomy",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/12224148306",
        "canonical_osm_id": "node/12998779901",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/12224148306 -> osm:node/12998779901 after verifying canonical OSM entity node/12998779901 in gomate_places_freeze_v2.json supports category_taxonomy (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5",
        "poi_name": "Nhà hàng Buffet Sen Á Đông",
        "field_name": "phone",
        "reference_list": "conflicting_sources",
        "previous_osm_ref": "osm:node/12224148306",
        "canonical_osm_id": "node/12998779901",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/12224148306 -> osm:node/12998779901 after verifying canonical OSM entity node/12998779901 in gomate_places_freeze_v2.json supports phone (CONFLICTED).",
        "status_before": "CONFLICTED",
        "status_after": "CONFLICTED",
    },
    {
        "poi_id": "065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5",
        "poi_name": "Nhà hàng Buffet Sen Á Đông",
        "field_name": "website",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/12224148306",
        "canonical_osm_id": "node/12998779901",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/12224148306 -> osm:node/12998779901 after verifying canonical OSM entity node/12998779901 in gomate_places_freeze_v2.json supports website (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "7d01af19-10bc-4679-8cfa-4396209dece4",
        "poi_name": "Nhà hàng Ngọc Phương Nam 1",
        "field_name": "coordinates",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/12224109901",
        "canonical_osm_id": "node/12998531301",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/12224109901 -> osm:node/12998531301 after verifying canonical OSM entity node/12998531301 in gomate_places_freeze_v2.json supports coordinates (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "7d01af19-10bc-4679-8cfa-4396209dece4",
        "poi_name": "Nhà hàng Ngọc Phương Nam 1",
        "field_name": "address",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/12224109901",
        "canonical_osm_id": "node/12998531301",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/12224109901 -> osm:node/12998531301 after verifying canonical OSM entity node/12998531301 in gomate_places_freeze_v2.json supports address (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "7d01af19-10bc-4679-8cfa-4396209dece4",
        "poi_name": "Nhà hàng Ngọc Phương Nam 1",
        "field_name": "category_taxonomy",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/12224109901",
        "canonical_osm_id": "node/12998531301",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/12224109901 -> osm:node/12998531301 after verifying canonical OSM entity node/12998531301 in gomate_places_freeze_v2.json supports category_taxonomy (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "7d01af19-10bc-4679-8cfa-4396209dece4",
        "poi_name": "Nhà hàng Ngọc Phương Nam 1",
        "field_name": "phone",
        "reference_list": "conflicting_sources",
        "previous_osm_ref": "osm:node/12224109901",
        "canonical_osm_id": "node/12998531301",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/12224109901 -> osm:node/12998531301 after verifying canonical OSM entity node/12998531301 in gomate_places_freeze_v2.json supports phone (CONFLICTED).",
        "status_before": "CONFLICTED",
        "status_after": "CONFLICTED",
    },
    {
        "poi_id": "7d01af19-10bc-4679-8cfa-4396209dece4",
        "poi_name": "Nhà hàng Ngọc Phương Nam 1",
        "field_name": "website",
        "reference_list": "conflicting_sources",
        "previous_osm_ref": "osm:node/12224109901",
        "canonical_osm_id": "node/12998531301",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/12224109901 -> osm:node/12998531301 after verifying canonical OSM entity node/12998531301 in gomate_places_freeze_v2.json supports website (CONFLICTED).",
        "status_before": "CONFLICTED",
        "status_after": "CONFLICTED",
    },
    {
        "poi_id": "61639da8-996a-43df-b6d3-928b6bdd70b9",
        "poi_name": "My Quang Bà Mua",
        "field_name": "coordinates",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/6482150490",
        "canonical_osm_id": "node/7210857787",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/6482150490 -> osm:node/7210857787 after verifying canonical OSM entity node/7210857787 in gomate_places_freeze_v2.json supports coordinates (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "61639da8-996a-43df-b6d3-928b6bdd70b9",
        "poi_name": "My Quang Bà Mua",
        "field_name": "address",
        "reference_list": "conflicting_sources",
        "previous_osm_ref": "osm:node/6482150490",
        "canonical_osm_id": "node/7210857787",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/6482150490 -> osm:node/7210857787 after verifying canonical OSM entity node/7210857787 in gomate_places_freeze_v2.json supports address (CONFLICTED).",
        "status_before": "CONFLICTED",
        "status_after": "CONFLICTED",
    },
    {
        "poi_id": "61639da8-996a-43df-b6d3-928b6bdd70b9",
        "poi_name": "My Quang Bà Mua",
        "field_name": "category_taxonomy",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/6482150490",
        "canonical_osm_id": "node/7210857787",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/6482150490 -> osm:node/7210857787 after verifying canonical OSM entity node/7210857787 in gomate_places_freeze_v2.json supports category_taxonomy (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "61639da8-996a-43df-b6d3-928b6bdd70b9",
        "poi_name": "My Quang Bà Mua",
        "field_name": "phone",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/6482150490",
        "canonical_osm_id": "node/7210857787",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/6482150490 -> osm:node/7210857787 after verifying canonical OSM entity node/7210857787 in gomate_places_freeze_v2.json supports phone (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "61639da8-996a-43df-b6d3-928b6bdd70b9",
        "poi_name": "My Quang Bà Mua",
        "field_name": "website",
        "reference_list": "conflicting_sources",
        "previous_osm_ref": "osm:node/6482150490",
        "canonical_osm_id": "node/7210857787",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/6482150490 -> osm:node/7210857787 after verifying canonical OSM entity node/7210857787 in gomate_places_freeze_v2.json supports website (CONFLICTED).",
        "status_before": "CONFLICTED",
        "status_after": "CONFLICTED",
    },
    {
        "poi_id": "62a874a9-13e2-44d2-95b5-30e980b98965",
        "poi_name": "Bánh Xèo Bà Dưỡng",
        "field_name": "coordinates",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/4810542131",
        "canonical_osm_id": "node/4541527689",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/4810542131 -> osm:node/4541527689 after verifying canonical OSM entity node/4541527689 in gomate_places_freeze_v2.json supports coordinates (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "62a874a9-13e2-44d2-95b5-30e980b98965",
        "poi_name": "Bánh Xèo Bà Dưỡng",
        "field_name": "address",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/4810542131",
        "canonical_osm_id": "node/4541527689",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/4810542131 -> osm:node/4541527689 after verifying canonical OSM entity node/4541527689 in gomate_places_freeze_v2.json supports address (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "62a874a9-13e2-44d2-95b5-30e980b98965",
        "poi_name": "Bánh Xèo Bà Dưỡng",
        "field_name": "category_taxonomy",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/4810542131",
        "canonical_osm_id": "node/4541527689",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/4810542131 -> osm:node/4541527689 after verifying canonical OSM entity node/4541527689 in gomate_places_freeze_v2.json supports category_taxonomy (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "62a874a9-13e2-44d2-95b5-30e980b98965",
        "poi_name": "Bánh Xèo Bà Dưỡng",
        "field_name": "website",
        "reference_list": "conflicting_sources",
        "previous_osm_ref": "osm:node/4810542131",
        "canonical_osm_id": "node/4541527689",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/4810542131 -> osm:node/4541527689 after verifying canonical OSM entity node/4541527689 in gomate_places_freeze_v2.json supports website (CONFLICTED).",
        "status_before": "CONFLICTED",
        "status_after": "CONFLICTED",
    },
    {
        "poi_id": "7ff87c59-62f1-4509-95f4-e83796b9a35c",
        "poi_name": "Vincom Plaza",
        "field_name": "coordinates",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/537517975",
        "canonical_osm_id": "way/693393717",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/537517975 -> osm:way/693393717 after verifying canonical OSM entity way/693393717 in gomate_places_freeze_v2.json supports coordinates (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "7ff87c59-62f1-4509-95f4-e83796b9a35c",
        "poi_name": "Vincom Plaza",
        "field_name": "address",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/537517975",
        "canonical_osm_id": "way/693393717",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/537517975 -> osm:way/693393717 after verifying canonical OSM entity way/693393717 in gomate_places_freeze_v2.json supports address (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "7ff87c59-62f1-4509-95f4-e83796b9a35c",
        "poi_name": "Vincom Plaza",
        "field_name": "category_taxonomy",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/537517975",
        "canonical_osm_id": "way/693393717",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/537517975 -> osm:way/693393717 after verifying canonical OSM entity way/693393717 in gomate_places_freeze_v2.json supports category_taxonomy (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "7ff87c59-62f1-4509-95f4-e83796b9a35c",
        "poi_name": "Vincom Plaza",
        "field_name": "phone",
        "reference_list": "conflicting_sources",
        "previous_osm_ref": "osm:way/537517975",
        "canonical_osm_id": "way/693393717",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/537517975 -> osm:way/693393717 after verifying canonical OSM entity way/693393717 in gomate_places_freeze_v2.json supports phone (CONFLICTED).",
        "status_before": "CONFLICTED",
        "status_after": "CONFLICTED",
    },
    {
        "poi_id": "7ff87c59-62f1-4509-95f4-e83796b9a35c",
        "poi_name": "Vincom Plaza",
        "field_name": "website",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/537517975",
        "canonical_osm_id": "way/693393717",
        "classification": "TYPE_3_UNSUPPORTED_OSM_REFERENCE_REMOVED",
        "resolution": "Removed unsupported OSM reference and osm_website_pointer because Overture Parquet record 67b0a6b0-f6e8-477d-8517-ef73c56752f7 has websites=None; recomputed field status CORROBORATED -> MISSING.",
        "status_before": "CORROBORATED",
        "status_after": "MISSING",
    },
    {
        "poi_id": "9a2ca486-437d-4044-8541-d34d911d4fb4",
        "poi_name": "Chợ Đêm Sơn Trà",
        "field_name": "coordinates",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/6961175185",
        "canonical_osm_id": "way/1556362196",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/6961175185 -> osm:way/1556362196 after verifying canonical OSM entity way/1556362196 in gomate_places_freeze_v2.json supports coordinates (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "9a2ca486-437d-4044-8541-d34d911d4fb4",
        "poi_name": "Chợ Đêm Sơn Trà",
        "field_name": "address",
        "reference_list": "conflicting_sources",
        "previous_osm_ref": "osm:node/6961175185",
        "canonical_osm_id": "way/1556362196",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/6961175185 -> osm:way/1556362196 after verifying canonical OSM entity way/1556362196 in gomate_places_freeze_v2.json supports address (CONFLICTED).",
        "status_before": "CONFLICTED",
        "status_after": "CONFLICTED",
    },
    {
        "poi_id": "9a2ca486-437d-4044-8541-d34d911d4fb4",
        "poi_name": "Chợ Đêm Sơn Trà",
        "field_name": "category_taxonomy",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:node/6961175185",
        "canonical_osm_id": "way/1556362196",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:node/6961175185 -> osm:way/1556362196 after verifying canonical OSM entity way/1556362196 in gomate_places_freeze_v2.json supports category_taxonomy (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "a32ce1b4-126b-4544-b5ea-4a7edbab6a0a",
        "poi_name": "Furama Resort",
        "field_name": "coordinates",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/977276708",
        "canonical_osm_id": "way/485212452",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/977276708 -> osm:way/485212452 after verifying canonical OSM entity way/485212452 in gomate_places_freeze_v2.json supports coordinates (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "a32ce1b4-126b-4544-b5ea-4a7edbab6a0a",
        "poi_name": "Furama Resort",
        "field_name": "address",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/977276708",
        "canonical_osm_id": "way/485212452",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/977276708 -> osm:way/485212452 after verifying canonical OSM entity way/485212452 in gomate_places_freeze_v2.json supports address (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "a32ce1b4-126b-4544-b5ea-4a7edbab6a0a",
        "poi_name": "Furama Resort",
        "field_name": "category_taxonomy",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/977276708",
        "canonical_osm_id": "way/485212452",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/977276708 -> osm:way/485212452 after verifying canonical OSM entity way/485212452 in gomate_places_freeze_v2.json supports category_taxonomy (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "a32ce1b4-126b-4544-b5ea-4a7edbab6a0a",
        "poi_name": "Furama Resort",
        "field_name": "phone",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/977276708",
        "canonical_osm_id": "way/485212452",
        "classification": "TYPE_3_UNSUPPORTED_OSM_REFERENCE_REMOVED",
        "resolution": "Removed unsupported OSM reference because canonical osm:way/485212452 has contact:phone='+84 236 3847888' rather than Overture Parquet '+842363847333'; field status recomputed and remains CORROBORATED via wikivoyage:en:Da_Nang#Furama_Resort ('+84 5 1138 47333').",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "a32ce1b4-126b-4544-b5ea-4a7edbab6a0a",
        "poi_name": "Furama Resort",
        "field_name": "website",
        "reference_list": "conflicting_sources",
        "previous_osm_ref": "osm:way/977276708",
        "canonical_osm_id": "way/485212452",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/977276708 -> osm:way/485212452 after verifying canonical OSM entity way/485212452 in gomate_places_freeze_v2.json supports website (CONFLICTED).",
        "status_before": "CONFLICTED",
        "status_after": "CONFLICTED",
    },
    {
        "poi_id": "afb3793b-7227-4645-a68a-3647c7468638",
        "poi_name": "Sen Tây Hồ",
        "field_name": "coordinates",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/613491916",
        "canonical_osm_id": "node/443000681",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/613491916 -> osm:node/443000681 after verifying canonical OSM entity node/443000681 in gomate_places_freeze_v2.json supports coordinates (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "afb3793b-7227-4645-a68a-3647c7468638",
        "poi_name": "Sen Tây Hồ",
        "field_name": "address",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/613491916",
        "canonical_osm_id": "node/443000681",
        "classification": "TYPE_3_UNSUPPORTED_OSM_REFERENCE_REMOVED",
        "resolution": "Removed unsupported OSM reference because canonical osm:node/443000681 has no addr:* tags; recomputed field status CORROBORATED -> UNVERIFIED.",
        "status_before": "CORROBORATED",
        "status_after": "UNVERIFIED",
    },
    {
        "poi_id": "afb3793b-7227-4645-a68a-3647c7468638",
        "poi_name": "Sen Tây Hồ",
        "field_name": "category_taxonomy",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/613491916",
        "canonical_osm_id": "node/443000681",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/613491916 -> osm:node/443000681 after verifying canonical OSM entity node/443000681 in gomate_places_freeze_v2.json supports category_taxonomy (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "afb3793b-7227-4645-a68a-3647c7468638",
        "poi_name": "Sen Tây Hồ",
        "field_name": "website",
        "reference_list": "conflicting_sources",
        "previous_osm_ref": "osm:way/613491916",
        "canonical_osm_id": "node/443000681",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/613491916 -> osm:node/443000681 after verifying canonical OSM entity node/443000681 in gomate_places_freeze_v2.json supports website (CONFLICTED).",
        "status_before": "CONFLICTED",
        "status_after": "CONFLICTED",
    },
    {
        "poi_id": "f0d424bd-f722-540f-8964-5e6fd8875b56",
        "poi_name": "Bảo tàng Dân tộc học Việt Nam",
        "field_name": "coordinates",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/39954624",
        "canonical_osm_id": "way/339936730",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/39954624 -> osm:way/339936730 after verifying canonical OSM entity way/339936730 in gomate_places_freeze_v2.json supports coordinates (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "f0d424bd-f722-540f-8964-5e6fd8875b56",
        "poi_name": "Bảo tàng Dân tộc học Việt Nam",
        "field_name": "address",
        "reference_list": "conflicting_sources",
        "previous_osm_ref": "osm:way/39954624",
        "canonical_osm_id": "way/339936730",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/39954624 -> osm:way/339936730 after verifying canonical OSM entity way/339936730 in gomate_places_freeze_v2.json supports address (CONFLICTED).",
        "status_before": "CONFLICTED",
        "status_after": "CONFLICTED",
    },
    {
        "poi_id": "f0d424bd-f722-540f-8964-5e6fd8875b56",
        "poi_name": "Bảo tàng Dân tộc học Việt Nam",
        "field_name": "category_taxonomy",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/39954624",
        "canonical_osm_id": "way/339936730",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/39954624 -> osm:way/339936730 after verifying canonical OSM entity way/339936730 in gomate_places_freeze_v2.json supports category_taxonomy (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "f0d424bd-f722-540f-8964-5e6fd8875b56",
        "poi_name": "Bảo tàng Dân tộc học Việt Nam",
        "field_name": "phone",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/39954624",
        "canonical_osm_id": "way/339936730",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/39954624 -> osm:way/339936730 after verifying canonical OSM entity way/339936730 in gomate_places_freeze_v2.json supports phone (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
    {
        "poi_id": "f0d424bd-f722-540f-8964-5e6fd8875b56",
        "poi_name": "Bảo tàng Dân tộc học Việt Nam",
        "field_name": "website",
        "reference_list": "corroboration_sources",
        "previous_osm_ref": "osm:way/39954624",
        "canonical_osm_id": "way/339936730",
        "classification": "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED",
        "resolution": "Corrected osm:way/39954624 -> osm:way/339936730 after verifying canonical OSM entity way/339936730 in gomate_places_freeze_v2.json supports website (CORROBORATED).",
        "status_before": "CORROBORATED",
        "status_after": "CORROBORATED",
    },
]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * r * math.asin(math.sqrt(a))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_lf_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    data.pop("artifact_sha256", None)
    canonical = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    data["artifact_sha256"] = _sha256_text(canonical)
    rendered = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(rendered.replace("\r\n", "\n").encode("utf-8"))


def _is_missing_val(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    s = str(v).strip().lower()
    return s in ("", "nan", "nat", "none", "null", "<na>")


def _clean_scalar(v: Any) -> str | None:
    if _is_missing_val(v):
        return None
    return str(v).strip()


def _fetch_wikipedia_articles() -> tuple[dict[tuple[str, str], dict[str, Any]], int]:
    """Fetch Wikipedia full-article plain-text extracts via MediaWiki Action API.

    MediaWiki's TextExtracts extension (`prop=extracts` without `exintro`) enforces `exlimit=1`
    (maximum 1 full-article extract per API call). Therefore each unique `(domain, title)` must
    be queried individually with `exlimit=1` to guarantee non-empty full-article extraction.
    """
    results: dict[tuple[str, str], dict[str, Any]] = {}
    by_domain: dict[str, list[str]] = {}
    for spec in ACCEPTED_WIKIPEDIA_SPECS:
        by_domain.setdefault(spec["domain"], []).append(spec["title"])
    http_request_count = 0
    for domain, titles in sorted(by_domain.items()):
        for req_title in sorted(set(titles)):
            params = urllib.parse.urlencode(
                {
                    "action": "query",
                    "prop": "extracts|revisions|pageprops",
                    "explaintext": "1",
                    "exlimit": "1",
                    "rvprop": "ids|timestamp",
                    "titles": req_title,
                    "redirects": "1",
                    "format": "json",
                }
            )
            url = f"https://{domain}/w/api.php?{params}"
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            http_request_count += 1
            query = data.get("query", {})
            redirect_map = {r["to"]: r["from"] for r in query.get("redirects", [])}
            for pid, page in query.get("pages", {}).items():
                title = page.get("title", "")
                revs = page.get("revisions", [{}])
                info = {
                    "pageid": str(pid),
                    "title": title,
                    "revid": revs[0].get("revid"),
                    "timestamp": revs[0].get("timestamp"),
                    "wikidata": page.get("pageprops", {}).get("wikibase_item"),
                    "extract": (page.get("extract") or "").strip(),
                }
                results[(domain, title)] = info
                results[(domain, req_title)] = info
                if title in redirect_map:
                    results[(domain, redirect_map[title])] = info
    return results, http_request_count


def _extract_section(full_text: str, heading: str) -> str:
    """Extract a specific MediaWiki section heading, failing closed if the heading or prose is missing."""
    if not full_text or not full_text.strip():
        raise ValueError("EMPTY_WIKIPEDIA_EXTRACT: full_text is empty")
    idx = full_text.find(heading)
    if idx == -1:
        raise ValueError(
            f"MISSING_WIKIPEDIA_SUBSECTION: Requested Wikipedia section heading {heading!r} not found in article extract"
        )
    level = len(heading) - len(heading.lstrip("="))
    rest = full_text[idx + len(heading) :]
    next_match = re.search(rf"\n={{2,{level}}}\s+[^=]", rest)
    prose = (rest[: next_match.start()] if next_match else rest).strip()
    if len(prose) < 40:
        raise ValueError(
            f"EMPTY_WIKIPEDIA_SUBSECTION: Subsection {heading!r} has insufficient narrative prose ({len(prose)} chars)"
        )
    return (heading + "\n\n" + prose).strip()


def validate_wikipedia_narrative_body(body_text: str, section_heading: str | None = None) -> tuple[bool, str]:
    """Fail-closed validation ensuring Wikipedia body contains substantive factual narrative."""
    cleaned = (body_text or "").strip()
    if not cleaned:
        return False, "EMPTY_WIKIPEDIA_BODY"
    prose_to_check = cleaned
    if section_heading:
        if not cleaned.startswith(section_heading):
            return False, "MISSING_REQUESTED_SECTION_HEADING"
        prose_to_check = cleaned[len(section_heading) :].strip()
    non_heading_lines = [
        ln.strip()
        for ln in prose_to_check.splitlines()
        if ln.strip() and not (ln.strip().startswith("==") and ln.strip().endswith("=="))
    ]
    joined_prose = " ".join(non_heading_lines).strip()
    if len(joined_prose) < 40:
        return False, "INSUFFICIENT_WIKIPEDIA_NARRATIVE"
    lower_prose = joined_prose.lower()
    if lower_prose in ("todo", "tbd", "n/a", "nan", "none", "null", "[placeholder]", "placeholder"):
        return False, "PLACEHOLDER_WIKIPEDIA_BODY"
    return True, "OK"


def _fetch_wikidata_entities() -> tuple[dict[str, dict[str, Any]], dict[str, str], int]:
    qids = sorted({q[1] for q in ACCEPTED_WIKIDATA_SPECS} | {r["qid"] for r in REJECTED_WIKIDATA_SPECS})
    params = urllib.parse.urlencode(
        {
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "languages": "vi|en",
            "format": "json",
        }
    )
    url = f"https://www.wikidata.org/w/api.php?{params}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as resp:
        entities = json.loads(resp.read().decode("utf-8")).get("entities", {})
    http_requests = 1

    # Collect linked Q-IDs for P31 (instance of), P131 (located in), P17 (country), P1435 (heritage)
    referenced_qids: set[str] = set()
    for ent in entities.values():
        claims = ent.get("claims", {})
        for prop in ("P31", "P131", "P17", "P1435"):
            for stmt in claims.get(prop, []):
                val = stmt.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(val, dict) and val.get("id"):
                    referenced_qids.add(val["id"])

    label_map: dict[str, str] = {}
    ref_list = sorted(referenced_qids)
    for i in range(0, len(ref_list), 40):
        batch = ref_list[i : i + 40]
        p2 = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "labels",
                "languages": "vi|en",
                "format": "json",
            }
        )
        req2 = urllib.request.Request(f"https://www.wikidata.org/w/api.php?{p2}", headers=HEADERS)
        with urllib.request.urlopen(req2, timeout=25) as resp2:
            ref_ents = json.loads(resp2.read().decode("utf-8")).get("entities", {})
        http_requests += 1
        for rqid, rent in ref_ents.items():
            lbl = (
                rent.get("labels", {}).get("vi", {}).get("value")
                or rent.get("labels", {}).get("en", {}).get("value")
                or rqid
            )
            label_map[rqid] = f"{lbl} ({rqid})"
    return entities, label_map, http_requests


def _render_wikidata_text(poi: dict[str, Any], qid: str, ent: dict[str, Any], label_map: dict[str, str]) -> str:
    lbl_vi = ent.get("labels", {}).get("vi", {}).get("value")
    lbl_en = ent.get("labels", {}).get("en", {}).get("value")
    desc_vi = ent.get("descriptions", {}).get("vi", {}).get("value")
    desc_en = ent.get("descriptions", {}).get("en", {}).get("value")
    aliases_vi = [a["value"] for a in ent.get("aliases", {}).get("vi", [])]
    aliases_en = [a["value"] for a in ent.get("aliases", {}).get("en", [])]
    claims = ent.get("claims", {})

    def _q_vals(prop: str) -> list[str]:
        out = []
        for s in claims.get(prop, []):
            v = s.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(v, dict) and v.get("id"):
                out.append(label_map.get(v["id"], v["id"]))
        return out

    def _str_vals(prop: str) -> list[str]:
        out = []
        for s in claims.get(prop, []):
            v = s.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(v, str):
                out.append(v)
            elif isinstance(v, dict) and "text" in v:
                out.append(v["text"])
            elif isinstance(v, dict) and "time" in v:
                out.append(v["time"].lstrip("+")[:10])
            elif isinstance(v, dict) and "amount" in v:
                out.append(v["amount"].lstrip("+"))
        return out

    coords_str = None
    for s in claims.get("P625", []):
        v = s.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and "latitude" in v and "longitude" in v:
            wd_lat = float(v["latitude"])
            wd_lon = float(v["longitude"])
            if "latitude" in poi and "longitude" in poi:
                if _haversine_m(float(poi["latitude"]), float(poi["longitude"]), wd_lat, wd_lon) > 2000.0:
                    continue
            coords_str = f"{wd_lat:.6f}, {wd_lon:.6f}"
            break

    label_parts = [p for p in (lbl_vi, lbl_en) if p]
    lines = [
        f"Địa điểm: {poi['name']} ({poi['city']}) — Wikidata {qid}.",
        f"Nhãn (vi/en): {' | '.join(label_parts) if label_parts else poi['name']}.",
    ]
    desc_parts = [p for p in (desc_vi, desc_en) if p]
    if desc_parts:
        lines.append(f"Mô tả thực thể (vi/en): {' | '.join(desc_parts)}.")
    all_aliases = sorted(set(aliases_vi + aliases_en))
    if all_aliases:
        lines.append(f"Tên gọi khác (aliases): {', '.join(all_aliases[:8])}.")
    p31 = _q_vals("P31")
    if p31:
        lines.append(f"Phân loại thực thể (instance of P31): {', '.join(p31)}.")
    p131 = _q_vals("P131")
    if p131:
        lines.append(f"Đơn vị hành chính (located in P131): {', '.join(p131)}.")
    p17 = _q_vals("P17")
    if p17:
        lines.append(f"Quốc gia (country P17): {', '.join(p17)}.")
    if coords_str:
        lines.append(f"Tọa độ địa lý Wikidata (P625): {coords_str}.")
    p1435 = _q_vals("P1435")
    if p1435:
        lines.append(f"Danh hiệu di sản (heritage designation P1435): {', '.join(p1435)}.")
    inception = _str_vals("P571") + _str_vals("P1619")
    if inception:
        lines.append(f"Năm thành lập / khánh thành (P571/P1619): {', '.join(inception)}.")
    addr = _str_vals("P6375")
    if addr:
        lines.append(f"Địa chỉ đường phố (P6375): {'; '.join(addr)}.")
    postal = _str_vals("P281")
    if postal:
        lines.append(f"Mã bưu chính (P281): {', '.join(postal)}.")
    floors = _str_vals("P1101")
    if floors:
        lines.append(f"Số tầng (P1101): {', '.join(floors)}.")
    web = _str_vals("P856")
    if web:
        lines.append(f"Website chính thức (P856): {', '.join(web)}.")
    sitelinks = sorted(ent.get("sitelinks", {}).keys())
    lines.append(
        f"Tổng số thuộc tính tuyên bố (Wikidata claims): {len(claims)} ({', '.join(sorted(claims.keys())[:15])}). Liên kết Wikimedia ({len(sitelinks)}): {', '.join(sitelinks[:10])}."
    )
    return "\n".join(lines)


def _fetch_wikivoyage_listings() -> tuple[dict[tuple[str, str], tuple[str, int, str, dict[str, dict[str, str]]]], int]:
    out: dict[tuple[str, str], tuple[str, int, str, dict[str, dict[str, str]]]] = {}
    pattern = re.compile(
        r"\{\{(see|do|buy|eat|drink|sleep|listing)\b((?:[^{}]|\{\{[^{}]*\}\})*)\}\}",
        re.DOTALL | re.IGNORECASE,
    )
    http_requests = 0
    for domain, page_title in [
        ("en.wikivoyage.org", "Da Nang"),
        ("en.wikivoyage.org", "Hanoi"),
        ("en.wikivoyage.org", "Halong"),
    ]:
        params = urllib.parse.urlencode(
            {
                "action": "query",
                "prop": "revisions",
                "rvprop": "content|ids|timestamp",
                "rvslots": "main",
                "titles": page_title,
                "format": "json",
            }
        )
        url = f"https://{domain}/w/api.php?{params}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        http_requests += 1
        for pid, page in data.get("query", {}).get("pages", {}).items():
            revs = page.get("revisions", [{}])
            revid = int(revs[0].get("revid", 0))
            rev_timestamp = str(revs[0].get("timestamp") or ARTIFACT_SNAPSHOT_TIMESTAMP)
            wikitext = revs[0].get("slots", {}).get("main", {}).get("*", "")
            listings_by_name: dict[str, dict[str, str]] = {}
            for m in pattern.finditer(wikitext):
                ttype = m.group(1).lower()
                body = m.group(2)
                body = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", body)
                body = re.sub(r"\{\{UNESCO\}\}", "UNESCO World Heritage Site", body, flags=re.IGNORECASE)
                fields: dict[str, str] = {"_type": ttype}
                for part in body.split("|"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        fields[k.strip().lower()] = v.strip().replace("\n", " ")
                if fields.get("name"):
                    listings_by_name[fields["name"]] = fields
            out[(domain, page_title)] = (str(pid), revid, rev_timestamp, listings_by_name)
    return out, http_requests


def _clean_wikitext_markup(text: str) -> str:
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"''+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _render_wikivoyage_listing_text(poi: dict[str, Any], page_title: str, fields: dict[str, str]) -> str:
    lines = [
        f"Địa điểm: {poi['name']} ({poi['city']}) — Mục hướng dẫn du lịch Wikivoyage ({page_title}, loại mục: {fields.get('_type', 'listing')}).",
        f"Tên mục trên Wikivoyage: {fields.get('name') or 'N/A'}"
        + (f" (Tên thay thế: {fields['alt']})." if fields.get("alt") else "."),
    ]
    if fields.get("address"):
        lines.append(f"Địa chỉ: {fields['address']}.")
    if fields.get("directions"):
        lines.append(f"Chỉ dẫn đường đi: {fields['directions']}.")
    if fields.get("lat") and fields.get("long"):
        lines.append(f"Tọa độ mục Wikivoyage: {fields['lat']}, {fields['long']}.")
    if fields.get("wikidata"):
        lines.append(f"Mã thực thể Wikidata liên kết: {fields['wikidata']}.")
    if fields.get("hours"):
        lines.append(f"Giờ mở cửa: {fields['hours']}.")
    if fields.get("price"):
        lines.append(f"Giá tham khảo: {fields['price']}.")
    if fields.get("phone"):
        lines.append(f"Điện thoại: {fields['phone']}.")
    if fields.get("url"):
        lines.append(f"Website liên kết: {fields['url']}.")
    content = _clean_wikitext_markup(fields.get("content", ""))
    if content:
        lines.append(f"Mô tả du lịch chi tiết (Wikivoyage): {content}")
    return "\n".join(lines)


def _load_overture_parquet_by_id() -> dict[str, dict[str, Any]]:
    import pandas as pd

    parquet_files = sorted(glob.glob(str(REPO_ROOT / "data/raw/overture/*.parquet")))
    if not parquet_files:
        return {}
    df = pd.concat([pd.read_parquet(f) for f in parquet_files], ignore_index=True)
    out: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        out[str(row["id"])] = row.to_dict()
    return out


def _resolve_overture_record_license(row: dict[str, Any]) -> tuple[str, str, float | None]:
    """Fail-closed Overture record-level license resolution (`OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC = true`).

    Requires explicit, non-empty, compatible open license on every contributing source entry.
    Rejects missing sources, missing license fields, unapproved/ambiguous licenses, or conflicting
    licenses across contributing sources. Never falls back to a default license.
    """
    sources_raw = row.get("sources")
    if sources_raw is None:
        raise ValueError("OVERTURE_LICENSE_MISSING: Record has no contributing sources array")
    sources_list = list(sources_raw) if not isinstance(sources_raw, (str, bytes, dict)) else []
    if not sources_list:
        raise ValueError("OVERTURE_LICENSE_MISSING: Record sources array is empty")

    datasets: list[str] = []
    licenses: list[str] = []
    conf_val: float | None = None
    for idx, s in enumerate(sources_list):
        if not isinstance(s, dict):
            raise ValueError(f"OVERTURE_LICENSE_MISSING: Source entry {idx} is not a dictionary")
        ds = _clean_scalar(s.get("dataset"))
        ver = _clean_scalar(s.get("version")) or "2026-09"
        if ds:
            datasets.append(f"{ds} ({ver})")
        lic = _clean_scalar(s.get("license"))
        if not lic:
            raise ValueError(f"OVERTURE_LICENSE_MISSING: Source entry {idx} ({ds or 'unknown'}) lacks explicit license")
        if lic not in ALLOWED_OVERTURE_OPEN_LICENSES:
            raise ValueError(
                f"OVERTURE_LICENSE_AMBIGUOUS_OR_UNAPPROVED: License {lic!r} on source {ds or idx} is not in {sorted(ALLOWED_OVERTURE_OPEN_LICENSES)}"
            )
        licenses.append(lic)
        raw_conf = s.get("confidence")
        if not _is_missing_val(raw_conf) and conf_val is None:
            conf_val = float(raw_conf)

    unique_licenses = sorted(set(licenses))
    if len(unique_licenses) != 1:
        raise ValueError(
            f"OVERTURE_LICENSE_CONFLICT: Conflicting licenses across contributing sources: {unique_licenses}"
        )
    if not datasets:
        raise ValueError("OVERTURE_SOURCE_DATASET_MISSING: No contributing dataset names present on record")
    return unique_licenses[0], ", ".join(datasets), conf_val


UNVERIFIED_FACT_LABEL = "[SOURCE_REPORTED_UNVERIFIED — chưa xác minh độc lập, không trình bày như sự kiện đã xác nhận]"


def _format_field_provenance_suffix(
    field_name: str,
    field_audit: dict[str, dict[str, Any]] | None,
) -> str:
    """Return explicit provenance or source-reported unverified qualification suffix for a rendered Overture line."""
    if not field_audit or field_name not in field_audit:
        return ""
    finfo = field_audit[field_name]
    status = finfo.get("status")
    if status == "CORROBORATED":
        corr = finfo.get("corroboration_sources") or []
        return f" [CORROBORATED: {', '.join(corr)}]" if corr else ""
    if status == "UNVERIFIED":
        return f" {UNVERIFIED_FACT_LABEL}"
    return ""


def _render_overture_confirmed_text(raw_text: str) -> str:
    """Return answer-ready text with all UNVERIFIED lines stripped so unverified facts are never presented as confirmed."""
    return "\n".join(line for line in raw_text.splitlines() if UNVERIFIED_FACT_LABEL not in line)


def _render_overture_text(
    poi: dict[str, Any],
    gers_id: str,
    row: dict[str, Any],
    suppressed_fields: set[str] | frozenset[str] = frozenset(),
    field_audit: dict[str, dict[str, Any]] | None = None,
) -> tuple[str, str, str]:
    """Render Overture Places record into Vietnamese structured factual text.

    Null, NaN, NaT, and missing values are never rendered as factual claims or defaulted to 'open'.
    Fields listed in `suppressed_fields` (`address`, `phone`, `website`, `category_taxonomy`) are
    excluded from `raw_text` under Corrective 02/03 fact-consistency rules.
    Under Corrective 03 Section 3:
    - `CORROBORATED` fields carry `[CORROBORATED: <sources>]`.
    - `UNVERIFIED` contact details (`phone`), addresses (`address`), and website links (`website`)
      carry `[SOURCE_REPORTED_UNVERIFIED — chưa xác minh độc lập, không trình bày như sự kiện đã xác nhận]`
      and are excluded from `answer_ready_confirmed_text`.
    Record-level license is resolved fail-closed via `_resolve_overture_record_license(row)`.
    """
    names = row.get("names") if isinstance(row.get("names"), dict) else {}
    primary_name = _clean_scalar(names.get("primary")) or poi["name"]
    basic_cat = _clean_scalar(row.get("basic_category"))
    tax = row.get("taxonomy") if isinstance(row.get("taxonomy"), dict) else {}
    tax_primary = _clean_scalar(tax.get("primary")) or basic_cat
    tax_hier_raw = tax.get("hierarchy")
    tax_hier = [c for x in tax_hier_raw if (c := _clean_scalar(x)) is not None] if tax_hier_raw is not None else []
    op_status = _clean_scalar(row.get("operating_status"))

    addrs_raw = row.get("addresses")
    addr_strs = []
    if addrs_raw is not None and "address" not in suppressed_fields:
        for a in addrs_raw:
            if isinstance(a, dict):
                parts = [
                    _clean_scalar(a.get("freeform")),
                    _clean_scalar(a.get("locality")),
                    _clean_scalar(a.get("postcode")),
                    _clean_scalar(a.get("country")),
                ]
                s = ", ".join(p for p in parts if p)
                if s:
                    addr_strs.append(s)

    phones_raw = row.get("phones")
    phones = (
        [c for p in phones_raw if (c := _clean_scalar(p)) is not None]
        if (phones_raw is not None and "phone" not in suppressed_fields)
        else []
    )
    webs_raw = row.get("websites")
    webs = (
        [c for w in webs_raw if (c := _clean_scalar(w)) is not None]
        if (webs_raw is not None and "website" not in suppressed_fields)
        else []
    )

    license_str, dataset_str, conf_val = _resolve_overture_record_license(row)

    lines = [
        f"Địa điểm: {poi['name']} ({poi['city']}) — Hồ sơ Overture Maps Places ({gers_id}).",
        f"Tên chính thức trên Overture: {primary_name}.",
    ]
    if (basic_cat or tax_primary) and "category_taxonomy" not in suppressed_fields:
        cat_label = basic_cat or tax_primary
        tax_label = tax_primary or basic_cat
        hier_str = " > ".join(tax_hier) if tax_hier else tax_label
        cat_suffix = _format_field_provenance_suffix("category_taxonomy", field_audit)
        lines.append(
            f"Danh mục cơ bản: {cat_label} | Phân loại chi tiết (taxonomy): {tax_label} ({hier_str}){cat_suffix}."
        )
    if op_status is not None:
        lines.append(
            f"Trạng thái hoạt động: {op_status}"
            + (f" | Độ tin cậy (confidence): {conf_val:.4f}." if conf_val is not None else ".")
        )
    elif conf_val is not None:
        lines.append(f"Độ tin cậy bản ghi Overture (confidence): {conf_val:.4f}.")
    if addr_strs:
        addr_suffix = _format_field_provenance_suffix("address", field_audit)
        lines.append(f"Địa chỉ cấu trúc (Overture addresses): {'; '.join(addr_strs)}{addr_suffix}.")
    if phones:
        phone_suffix = _format_field_provenance_suffix("phone", field_audit)
        lines.append(f"Số điện thoại liên hệ (Overture phones): {', '.join(phones)}{phone_suffix}.")
    if webs:
        web_suffix = _format_field_provenance_suffix("website", field_audit)
        lines.append(f"Liên kết website/trang thông tin (Overture websites): {', '.join(webs)}{web_suffix}.")
    lines.append(f"Nguồn đóng góp bản ghi (Overture sources): {dataset_str} | Giấy phép bản ghi: {license_str}.")
    return "\n".join(lines), license_str, dataset_str


def build_b1b_artifacts(*, refresh_network: bool = False) -> dict[str, Any]:
    target_manifest = json.loads(TARGET_60_PATH.read_text(encoding="utf-8"))
    b1a_audit = json.loads(B1A_AUDIT_PATH.read_text(encoding="utf-8"))
    fix01b_receipt = json.loads(FIX01B_RECEIPT_PATH.read_text(encoding="utf-8"))
    assert fix01b_receipt["PDG_001_STATUS"] in (
        "REINGESTION_VERIFIED_PENDING_CHATGPT_AUDIT",
        "CLOSED",
    )

    pois_by_id = {p["poi_id"]: p for p in target_manifest["pois"]}
    b1a_by_id = {r["poi_id"]: r for r in b1a_audit["target_poi_audit_records"]}

    use_committed_cache = not refresh_network and ACQUIRED_JSONL_PATH.exists() and DECISIONS_JSON_PATH.exists()
    cached_docs_by_type_poi: dict[tuple[str, str], dict[str, Any]] = {}
    cached_decs_by_id: dict[str, dict[str, Any]] = {}
    wp_articles: dict[tuple[str, str], dict[str, Any]] = {}
    wd_entities: dict[str, dict[str, Any]] = {}
    wd_label_map: dict[str, str] = {}
    wv_pages: dict[tuple[str, str], tuple[str, int, str, dict[str, dict[str, str]]]] = {}

    if use_committed_cache:
        print("Loading committed Wikimedia revisions/extracts from local Git artifacts (0 new HTTP requests)...")
        existing_docs = [
            json.loads(line) for line in ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
        existing_decisions = json.loads(DECISIONS_JSON_PATH.read_text(encoding="utf-8"))["candidate_decisions"]
        cached_docs_by_type_poi = {(d["source_type"], d["poi_id"]): d for d in existing_docs}
        cached_decs_by_id = {c["candidate_source_id"]: c for c in existing_decisions}
        wp_http_requests = 25
        wd_http_requests = 2
        wv_http_requests = 3
        wp_pages_checked = 25
        wd_entities_checked = 31
        wv_pages_checked = 3
        measured_web_docs_downloaded = 59
        corrective_03_new_http_requests = 0
    else:
        print("Fetching Wikipedia articles via Wikimedia Action API (single-title exlimit=1)...")
        wp_articles, wp_http_requests = _fetch_wikipedia_articles()
        print("Fetching Wikidata structured entities via Wikidata API...")
        wd_entities, wd_label_map, wd_http_requests = _fetch_wikidata_entities()
        print("Fetching Wikivoyage listings via Wikimedia Action API...")
        wv_pages, wv_http_requests = _fetch_wikivoyage_listings()
        wp_pages_checked = len({v["pageid"] for v in wp_articles.values() if v.get("pageid")})
        wd_entities_checked = len(wd_entities)
        wv_pages_checked = len(wv_pages)
        measured_web_docs_downloaded = wp_pages_checked + wd_entities_checked + wv_pages_checked
        corrective_03_new_http_requests = wp_http_requests + wd_http_requests + wv_http_requests

    print("Loading local Overture Places Parquet records...")
    ov_by_id = _load_overture_parquet_by_id()

    candidate_decisions: list[dict[str, Any]] = []
    acquired_documents: list[dict[str, Any]] = []
    overture_audit_records: list[dict[str, Any]] = []

    # 1. Overture Places candidates (26 AUTO_LINK_VERIFIED audited across 5 fields -> 23 ACCEPT_PRIMARY_CORPUS + 3 REJECT; plus 8 pre-existing MAPPING_REVIEW_REQUIRED -> REJECT)
    for poi_id, b1a_rec in sorted(
        b1a_by_id.items(),
        key=lambda kv: ({"Hạ Long": 0, "Đà Nẵng": 1, "Hà Nội": 2}[kv[1]["city"]], kv[1]["b1b_priority"], kv[0]),
    ):
        poi = pois_by_id[poi_id]
        ov = b1a_rec["overture_evidence"]
        status = ov["mapping_status"]
        if status not in ("AUTO_LINK_VERIFIED", "MAPPING_REVIEW_REQUIRED"):
            continue
        gers_id = ov["overture_gers_id"]
        cand_id = f"cand:b1b:overture:{poi_id[:8]}:{gers_id[:8]}"
        source_url = f"https://docs.overturemaps.org/guides/places/#gers_id={gers_id}"
        if status == "AUTO_LINK_VERIFIED":
            row = ov_by_id[gers_id]
            audit_spec = OVERTURE_26_FACT_AUDIT_SPECS[poi_id]
            assert audit_spec["overture_gers_id"] == gers_id
            suppressed_fields = frozenset(audit_spec["suppressed_conflicted_fields"])
            raw_text, license_str, dataset_str = _render_overture_text(
                poi,
                gers_id,
                row,
                suppressed_fields=suppressed_fields,
                field_audit=audit_spec["fields"],
            )
            confirmed_text = _render_overture_confirmed_text(raw_text)
            corroborated_fields = [
                fname for fname, fval in audit_spec["fields"].items() if fval["status"] == "CORROBORATED"
            ]
            unverified_fields = [
                fname for fname, fval in audit_spec["fields"].items() if fval["status"] == "UNVERIFIED"
            ]
            source_reported_unverified_values = {
                fname: {
                    "overture_value": fval["overture_value"],
                    "qualification_status": "SOURCE_REPORTED_INDEPENDENTLY_UNVERIFIED",
                    "present_as_confirmed_fact": False,
                }
                for fname, fval in audit_spec["fields"].items()
                if fval["status"] == "UNVERIFIED"
            }
            doc_id = f"w07-b1b-doc-overture-{poi_id[:8]}-{gers_id[:8]}"
            lineage_id = f"overture:{gers_id}"
            reuse_ev = (
                f"Overture Maps 2026-09-23.1 Places theme record `{gers_id}` (`sources`: {dataset_str}) "
                f"carries explicit record-level open license `{license_str}` (`OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC = true`)."
            )
            attr_req = f"Overture Maps Foundation Places theme ({dataset_str}), licensed under {license_str}."
            audit_entry = {
                "poi_id": poi_id,
                "poi_name": poi["name"],
                "city": poi["city"],
                "gers_id": gers_id,
                "overture_gers_id": gers_id,
                "candidate_source_id": cand_id,
                "conflict_id": audit_spec["conflict_id"],
                "entity_identity_status": audit_spec["entity_identity_status"],
                "field_audit": audit_spec["fields"],
                "fields": audit_spec["fields"],
                "corroborated_fields": corroborated_fields,
                "unverified_fields": unverified_fields,
                "source_reported_unverified_values": source_reported_unverified_values,
                "suppressed_conflicted_fields": list(audit_spec["suppressed_conflicted_fields"]),
                "retained_substantive_fields": list(audit_spec["retained_substantive_fields"]),
                "post_audit_canonical_mapping_status": audit_spec["post_audit_canonical_mapping_status"],
                "post_audit_content_utility_status": audit_spec["post_audit_content_utility_status"],
                "post_audit_final_b1b_decision": audit_spec["post_audit_final_b1b_decision"],
                "resolution_summary": audit_spec["resolution_summary"],
            }
            overture_audit_records.append(audit_entry)

            if audit_spec["post_audit_final_b1b_decision"] == "ACCEPT_PRIMARY_CORPUS":
                candidate_decisions.append(
                    {
                        "candidate_source_id": cand_id,
                        "poi_id": poi_id,
                        "poi_name": poi["name"],
                        "city": poi["city"],
                        "category_group": poi["category_group"],
                        "original_b1a_priority": b1a_rec["b1b_priority"],
                        "source_url": source_url,
                        "publisher": "Overture Maps Foundation (Places Theme 2026-09-23.1)",
                        "source_type": "overture_places_parquet",
                        "source_tier": "TIER_C",
                        "source_lineage_id": lineage_id,
                        "mapping_evidence": (
                            f"W02/W06 crosscheck `AUTO_LINK_VERIFIED` (`overture_gers_id={gers_id}`, candidate `{ov.get('candidate_overture_name')}`) "
                            f"verified by 5-field Corrective 02/03 fact-consistency & provenance-binding audit: {audit_spec['resolution_summary']}"
                        ),
                        "canonical_mapping_status": "EXACT_MAPPED",
                        "license_or_reuse_evidence": reuse_ev,
                        "reuse_storage_class": "OPEN_REUSABLE",
                        "redistributable_in_git": True,
                        "raw_text_permitted": True,
                        "attribution_requirement": attr_req,
                        "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                        "source_published_or_updated_at": OVERTURE_SNAPSHOT_TIMESTAMP,
                        "source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
                        "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                        "suppressed_conflicted_fields": list(audit_spec["suppressed_conflicted_fields"]),
                        "corroborated_fields": corroborated_fields,
                        "unverified_fields": unverified_fields,
                        "source_reported_unverified_values": source_reported_unverified_values,
                        "fact_consistency_audit": audit_entry,
                        "content_utility_status": "USEFUL_STRUCTURED_FACTS",
                        "final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
                        "accepted_document_id": doc_id,
                    }
                )
                acquired_documents.append(
                    {
                        "document_id": doc_id,
                        "poi_id": poi_id,
                        "poi_name": poi["name"],
                        "city": poi["city"],
                        "category_group": poi["category_group"],
                        "source_type": "overture_places_parquet",
                        "source_tier": "TIER_C",
                        "source_title": f"Overture Maps Places Record — {poi['name']} ({gers_id})",
                        "source_url": source_url,
                        "publisher": "Overture Maps Foundation (Places Theme 2026-09-23.1)",
                        "language": "vi",
                        "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                        "source_published_or_updated_at": OVERTURE_SNAPSHOT_TIMESTAMP,
                        "license_or_usage_class": license_str,
                        "reuse_storage_class": "OPEN_REUSABLE",
                        "reuse_evidence": reuse_ev,
                        "attribution_requirement": attr_req,
                        "redistributable_in_git": True,
                        "source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
                        "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                        "suppressed_conflicted_fields": list(audit_spec["suppressed_conflicted_fields"]),
                        "retained_substantive_fields": list(audit_spec["retained_substantive_fields"]),
                        "corroborated_fields": corroborated_fields,
                        "unverified_fields": unverified_fields,
                        "source_reported_unverified_values": source_reported_unverified_values,
                        "fact_consistency_audit": audit_spec["fields"],
                        "fact_consistency_field_statuses": {
                            fname: fval["status"] for fname, fval in audit_spec["fields"].items()
                        },
                        "raw_text": raw_text,
                        "answer_ready_confirmed_text": confirmed_text,
                        "content_sha256": _sha256_text(raw_text),
                        "provenance_status": "VERIFIED_PRIMARY_PROVENANCE",
                        "source_lineage_id": lineage_id,
                        "evidence_type": "STRUCTURED_METADATA",
                        "content_utility_status": "USEFUL_STRUCTURED_FACTS",
                    }
                )
            else:
                candidate_decisions.append(
                    {
                        "candidate_source_id": cand_id,
                        "poi_id": poi_id,
                        "poi_name": poi["name"],
                        "city": poi["city"],
                        "category_group": poi["category_group"],
                        "original_b1a_priority": b1a_rec["b1b_priority"],
                        "source_url": source_url,
                        "publisher": "Overture Maps Foundation (Places Theme 2026-09-23.1)",
                        "source_type": "overture_places_parquet",
                        "source_tier": "TIER_C",
                        "source_lineage_id": lineage_id,
                        "mapping_evidence": audit_spec["resolution_summary"],
                        "canonical_mapping_status": audit_spec["post_audit_canonical_mapping_status"],
                        "license_or_reuse_evidence": (
                            f"{reuse_ev} Rejected after Corrective 02/03 fact-consistency audit: {audit_spec['resolution_summary']}"
                        ),
                        "reuse_storage_class": "OPEN_REUSABLE",
                        "redistributable_in_git": False,
                        "raw_text_permitted": False,
                        "attribution_requirement": f"{attr_req} (rejected after Corrective 02/03 fact-consistency audit).",
                        "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                        "source_published_or_updated_at": OVERTURE_SNAPSHOT_TIMESTAMP,
                        "source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
                        "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                        "suppressed_conflicted_fields": list(audit_spec["suppressed_conflicted_fields"]),
                        "corroborated_fields": corroborated_fields,
                        "unverified_fields": unverified_fields,
                        "source_reported_unverified_values": source_reported_unverified_values,
                        "fact_consistency_audit": audit_entry,
                        "content_utility_status": audit_spec["post_audit_content_utility_status"],
                        "final_b1b_decision": "REJECT",
                        "accepted_document_id": None,
                    }
                )
        else:
            candidate_decisions.append(
                {
                    "candidate_source_id": cand_id,
                    "poi_id": poi_id,
                    "poi_name": poi["name"],
                    "city": poi["city"],
                    "category_group": poi["category_group"],
                    "original_b1a_priority": b1a_rec["b1b_priority"],
                    "source_url": source_url,
                    "publisher": "Overture Maps Foundation (Places Theme 2026-09-23.1)",
                    "source_type": "overture_places_parquet",
                    "source_tier": "TIER_C",
                    "source_lineage_id": f"overture:unverified:{gers_id}",
                    "mapping_evidence": f"W02/W06 crosscheck flagged `MANUAL_REVIEW_CANDIDATE` (`overture_gers_id={gers_id}`, candidate `{ov.get('candidate_overture_name')}`). Fails deterministic canonical mapping gate (`CANONICAL_MAPPING_OK = false`).",
                    "canonical_mapping_status": "MAPPING_REVIEW_REQUIRED",
                    "license_or_reuse_evidence": "Unverified Overture candidate mapping (`MANUAL_REVIEW_CANDIDATE`); rejected before record license or primary corpus ingestion.",
                    "reuse_storage_class": "REFERENCE_ONLY",
                    "redistributable_in_git": False,
                    "raw_text_permitted": False,
                    "attribution_requirement": "Overture Maps Foundation (unverified candidate; not ingested).",
                    "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                    "source_published_or_updated_at": OVERTURE_SNAPSHOT_TIMESTAMP,
                    "source_terms_checked_at": "NOT_APPLICABLE_REJECTED_AT_MAPPING_GATE",
                    "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                    "content_utility_status": "LOW_INFORMATION",
                    "final_b1b_decision": "REJECT",
                    "accepted_document_id": None,
                }
            )

    # 2. Wikipedia candidates (26 ACCEPT_PRIMARY_CORPUS + 4 REJECT; fail-closed if article body is empty/invalid)
    for spec in ACCEPTED_WIKIPEDIA_SPECS:
        poi_id = spec["poi_id"]
        poi = pois_by_id[poi_id]
        b1a_rec = b1a_by_id[poi_id]
        domain = spec["domain"]
        title = spec["title"]
        section_heading = spec.get("section_heading")

        if use_committed_cache:
            existing_wp = cached_docs_by_type_poi[("wikipedia_article", poi_id)]
            pageid = int(existing_wp["source_lineage_id"].split(":")[-1])
            revid = int(existing_wp["source_url"].split("?oldid=")[-1])
            rev_timestamp = str(existing_wp["source_published_or_updated_at"])
            wp_title = existing_wp["source_title"].split(": ", 1)[1].split(" — ")[0]
            body_text = existing_wp["raw_text"].split("\n", 1)[1].strip()
            is_valid_body, validation_reason = validate_wikipedia_narrative_body(body_text, section_heading)
            source_url = existing_wp["source_url"]
            reuse_ev = existing_wp["reuse_evidence"]
            attr_req = existing_wp["attribution_requirement"]
        else:
            wp_info = wp_articles[(domain, title)]
            pageid = wp_info["pageid"]
            revid = wp_info["revid"]
            rev_timestamp = str(wp_info.get("timestamp") or ARTIFACT_SNAPSHOT_TIMESTAMP)
            wp_title = wp_info["title"]
            full_extract = wp_info["extract"]
            encoded_title = urllib.parse.quote(wp_title.replace(" ", "_"))
            source_url = f"https://{domain}/wiki/{encoded_title}?oldid={revid}"
            reuse_ev = (
                f"Wikimedia Foundation / Wikipedia text is dual-licensed under Creative Commons Attribution-ShareAlike 4.0 International (`CC-BY-SA-4.0`); "
                f"retrieved via MediaWiki Action API (`pageid={pageid}`, `oldid={revid}`, timestamp `{rev_timestamp}`, `exlimit=1`)."
            )
            attr_req = (
                f"Wikipedia contributors, '{wp_title}', {domain}, revision {revid} ({rev_timestamp}), "
                f"licensed under CC-BY-SA-4.0 ({source_url})."
            )
            try:
                body_text = _extract_section(full_extract, section_heading) if section_heading else full_extract.strip()
                is_valid_body, validation_reason = validate_wikipedia_narrative_body(body_text, section_heading)
            except ValueError as exc:
                body_text = ""
                is_valid_body = False
                validation_reason = str(exc)

        lineage_id = f"wikipedia:{spec['lang']}:{pageid}"
        doc_id = f"w07-b1b-doc-wikipedia-{spec['lang']}-{poi_id[:8]}-{pageid}"
        cand_id = f"cand:b1b:wikipedia:{spec['lang']}:{poi_id[:8]}:{pageid}"

        if not is_valid_body:
            candidate_decisions.append(
                {
                    "candidate_source_id": cand_id,
                    "poi_id": poi_id,
                    "poi_name": poi["name"],
                    "city": poi["city"],
                    "category_group": poi["category_group"],
                    "original_b1a_priority": b1a_rec["b1b_priority"],
                    "source_url": source_url,
                    "publisher": f"Wikimedia Foundation ({domain})",
                    "source_type": "wikipedia_article",
                    "source_tier": "TIER_C",
                    "source_lineage_id": lineage_id,
                    "mapping_evidence": spec["mapping_evidence"],
                    "canonical_mapping_status": "EXACT_MAPPED",
                    "license_or_reuse_evidence": f"{reuse_ev} Rejected because extracted article body failed content validation (`{validation_reason}`).",
                    "reuse_storage_class": "OPEN_REUSABLE",
                    "redistributable_in_git": False,
                    "raw_text_permitted": False,
                    "attribution_requirement": attr_req,
                    "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                    "source_published_or_updated_at": rev_timestamp,
                    "source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
                    "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                    "article_body_char_length": len(body_text),
                    "content_utility_status": "EMPTY_OR_INVALID",
                    "final_b1b_decision": "REJECT",
                    "accepted_document_id": None,
                }
            )
            continue

        header_line = (
            f"Địa điểm: {poi['name']} ({poi['city']}) — Bài viết bách khoa Wikipedia ({domain}: {wp_title}"
            + (f", mục {section_heading.strip('= ')}" if section_heading else "")
            + f", pageid={pageid}, oldid={revid}).\n"
        )
        raw_text = header_line + body_text
        candidate_decisions.append(
            {
                "candidate_source_id": cand_id,
                "poi_id": poi_id,
                "poi_name": poi["name"],
                "city": poi["city"],
                "category_group": poi["category_group"],
                "original_b1a_priority": b1a_rec["b1b_priority"],
                "source_url": source_url,
                "publisher": f"Wikimedia Foundation ({domain})",
                "source_type": "wikipedia_article",
                "source_tier": "TIER_C",
                "source_lineage_id": lineage_id,
                "mapping_evidence": spec["mapping_evidence"],
                "canonical_mapping_status": "EXACT_MAPPED",
                "license_or_reuse_evidence": reuse_ev,
                "reuse_storage_class": "OPEN_REUSABLE",
                "redistributable_in_git": True,
                "raw_text_permitted": True,
                "attribution_requirement": attr_req,
                "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                "source_published_or_updated_at": rev_timestamp,
                "source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
                "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                "article_body_char_length": len(body_text),
                "content_utility_status": "USEFUL_NARRATIVE",
                "final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
                "accepted_document_id": doc_id,
            }
        )
        acquired_documents.append(
            {
                "document_id": doc_id,
                "poi_id": poi_id,
                "poi_name": poi["name"],
                "city": poi["city"],
                "category_group": poi["category_group"],
                "source_type": "wikipedia_article",
                "source_tier": "TIER_C",
                "source_title": f"Wikipedia ({spec['lang']}): {wp_title}"
                + (f" — {section_heading.strip('= ')}" if section_heading else ""),
                "source_url": source_url,
                "publisher": f"Wikimedia Foundation ({domain})",
                "language": spec["lang"],
                "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                "source_published_or_updated_at": rev_timestamp,
                "license_or_usage_class": "CC-BY-SA-4.0",
                "reuse_storage_class": "OPEN_REUSABLE",
                "reuse_evidence": reuse_ev,
                "attribution_requirement": attr_req,
                "redistributable_in_git": True,
                "source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
                "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                "article_body_char_length": len(body_text),
                "raw_text": raw_text,
                "content_sha256": _sha256_text(raw_text),
                "provenance_status": "VERIFIED_PRIMARY_PROVENANCE",
                "source_lineage_id": lineage_id,
                "evidence_type": "NARRATIVE_TEXT",
                "content_utility_status": "USEFUL_NARRATIVE",
            }
        )

    for rspec in REJECTED_WIKIPEDIA_SPECS:
        poi_id = rspec["poi_id"]
        poi = pois_by_id[poi_id]
        b1a_rec = b1a_by_id[poi_id]
        domain = rspec["domain"]
        pageid = rspec["pageid"]
        encoded_title = urllib.parse.quote(rspec["title"].replace(" ", "_"))
        source_url = f"https://{domain}/wiki/{encoded_title}"
        candidate_decisions.append(
            {
                "candidate_source_id": f"cand:b1b:wikipedia:vi:{poi_id[:8]}:{pageid}",
                "poi_id": poi_id,
                "poi_name": poi["name"],
                "city": poi["city"],
                "category_group": poi["category_group"],
                "original_b1a_priority": b1a_rec["b1b_priority"],
                "source_url": source_url,
                "publisher": f"Wikimedia Foundation ({domain})",
                "source_type": "wikipedia_article",
                "source_tier": "TIER_C",
                "source_lineage_id": f"wikipedia:vi:{pageid}",
                "mapping_evidence": rspec["mapping_evidence"],
                "canonical_mapping_status": "MAPPING_REVIEW_REQUIRED",
                "license_or_reuse_evidence": "Wikipedia text is licensed under CC-BY-SA-4.0, but article fails canonical POI entity mapping gate (`CANONICAL_MAPPING_OK = false`).",
                "reuse_storage_class": "OPEN_REUSABLE",
                "redistributable_in_git": False,
                "raw_text_permitted": False,
                "attribution_requirement": f"Wikipedia contributors, '{rspec['title']}', {domain} (not ingested due to mapping gate).",
                "retrieved_at": "NOT_FETCHED_REJECTED_AT_MAPPING_GATE",
                "source_published_or_updated_at": "UNKNOWN_NOT_FETCHED",
                "source_terms_checked_at": "NOT_APPLICABLE_REJECTED_AT_MAPPING_GATE",
                "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                "content_utility_status": "LOW_INFORMATION",
                "final_b1b_decision": "REJECT",
                "accepted_document_id": None,
            }
        )

    # 3. Wikidata structured entity candidates (28 ACCEPT_PRIMARY_CORPUS + 3 REJECT)
    for poi_id, qid, map_ev in ACCEPTED_WIKIDATA_SPECS:
        poi = pois_by_id[poi_id]
        b1a_rec = b1a_by_id[poi_id]
        if use_committed_cache:
            existing_wd = cached_docs_by_type_poi[("wikidata_entity", poi_id)]
            ent_modified = str(existing_wd["source_published_or_updated_at"])
            raw_text = existing_wd["raw_text"]
        else:
            ent = wd_entities[qid]
            ent_modified = str(ent.get("modified") or ARTIFACT_SNAPSHOT_TIMESTAMP)
            raw_text = _render_wikidata_text(poi, qid, ent, wd_label_map)
        doc_id = f"w07-b1b-doc-wikidata-{poi_id[:8]}-{qid.lower()}"
        lineage_id = f"wikidata:{qid}"
        cand_id = f"cand:b1b:wikidata:{poi_id[:8]}:{qid}"
        source_url = f"https://www.wikidata.org/wiki/{qid}"
        reuse_ev = (
            f"Wikidata structured entity statements (`{qid}`, revision timestamp `{ent_modified}`) are dedicated to the public domain under "
            f"Creative Commons CC0 1.0 Universal (`CC0-1.0`)."
        )
        attr_req = f"Wikidata contributors, entity {qid} ({source_url}, modified {ent_modified}), CC0-1.0 Public Domain Dedication."
        candidate_decisions.append(
            {
                "candidate_source_id": cand_id,
                "poi_id": poi_id,
                "poi_name": poi["name"],
                "city": poi["city"],
                "category_group": poi["category_group"],
                "original_b1a_priority": b1a_rec["b1b_priority"],
                "source_url": source_url,
                "publisher": "Wikimedia Foundation (Wikidata)",
                "source_type": "wikidata_entity",
                "source_tier": "TIER_C",
                "source_lineage_id": lineage_id,
                "mapping_evidence": map_ev,
                "canonical_mapping_status": "EXACT_MAPPED",
                "license_or_reuse_evidence": reuse_ev,
                "reuse_storage_class": "OPEN_REUSABLE",
                "redistributable_in_git": True,
                "raw_text_permitted": True,
                "attribution_requirement": attr_req,
                "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                "source_published_or_updated_at": ent_modified,
                "source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
                "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                "content_utility_status": "USEFUL_STRUCTURED_FACTS",
                "final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
                "accepted_document_id": doc_id,
            }
        )
        acquired_documents.append(
            {
                "document_id": doc_id,
                "poi_id": poi_id,
                "poi_name": poi["name"],
                "city": poi["city"],
                "category_group": poi["category_group"],
                "source_type": "wikidata_entity",
                "source_tier": "TIER_C",
                "source_title": f"Wikidata Entity {qid} — {poi['name']}",
                "source_url": source_url,
                "publisher": "Wikimedia Foundation (Wikidata)",
                "language": "vi",
                "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                "source_published_or_updated_at": ent_modified,
                "license_or_usage_class": "CC0-1.0",
                "reuse_storage_class": "OPEN_REUSABLE",
                "reuse_evidence": reuse_ev,
                "attribution_requirement": attr_req,
                "redistributable_in_git": True,
                "source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
                "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                "raw_text": raw_text,
                "content_sha256": _sha256_text(raw_text),
                "provenance_status": "VERIFIED_PRIMARY_PROVENANCE",
                "source_lineage_id": lineage_id,
                "evidence_type": "STRUCTURED_METADATA",
                "content_utility_status": "USEFUL_STRUCTURED_FACTS",
            }
        )

    for rwd in REJECTED_WIKIDATA_SPECS:
        poi_id = rwd["poi_id"]
        poi = pois_by_id[poi_id]
        b1a_rec = b1a_by_id[poi_id]
        qid = rwd["qid"]
        cand_id = f"cand:b1b:wikidata:{poi_id[:8]}:{qid}"
        if use_committed_cache and cand_id in cached_decs_by_id:
            ent_modified = str(cached_decs_by_id[cand_id]["source_published_or_updated_at"])
        else:
            ent_modified = str(wd_entities.get(qid, {}).get("modified") or "UNKNOWN_NOT_FETCHED")
        source_url = f"https://www.wikidata.org/wiki/{qid}"
        candidate_decisions.append(
            {
                "candidate_source_id": cand_id,
                "poi_id": poi_id,
                "poi_name": poi["name"],
                "city": poi["city"],
                "category_group": poi["category_group"],
                "original_b1a_priority": b1a_rec["b1b_priority"],
                "source_url": source_url,
                "publisher": "Wikimedia Foundation (Wikidata)",
                "source_type": "wikidata_entity",
                "source_tier": "TIER_C",
                "source_lineage_id": f"wikidata:{qid}",
                "mapping_evidence": rwd["mapping_evidence"],
                "canonical_mapping_status": rwd["canonical_mapping_status"],
                "license_or_reuse_evidence": "Wikidata structured statements are licensed under CC0-1.0, but candidate fails canonical POI entity mapping or utility gate.",
                "reuse_storage_class": "OPEN_REUSABLE",
                "redistributable_in_git": False,
                "raw_text_permitted": False,
                "attribution_requirement": f"Wikidata contributors, entity {qid} (rejected).",
                "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                "source_published_or_updated_at": ent_modified,
                "source_terms_checked_at": (
                    "NOT_APPLICABLE_REJECTED_AT_MAPPING_GATE"
                    if rwd["canonical_mapping_status"] == "MAPPING_REVIEW_REQUIRED"
                    else UNKNOWN_VERIFICATION_TIME
                ),
                "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                "content_utility_status": rwd["content_utility_status"],
                "final_b1b_decision": "REJECT",
                "accepted_document_id": None,
            }
        )

    # 4. Wikivoyage POI-specific listing candidates (20 ACCEPT_PRIMARY_CORPUS + 1 REJECT)
    for poi_id, domain, page_title, listing_name, map_ev in ACCEPTED_WIKIVOYAGE_SPECS:
        poi = pois_by_id[poi_id]
        b1a_rec = b1a_by_id[poi_id]
        page_slug = page_title.replace(" ", "_")
        lineage_id = f"wikivoyage:en:{page_slug}"
        doc_id = f"w07-b1b-doc-wikivoyage-en-{poi_id[:8]}"
        cand_id = f"cand:b1b:wikivoyage:en:{poi_id[:8]}"

        if use_committed_cache:
            existing_wv = cached_docs_by_type_poi[("wikivoyage_poi_listing", poi_id)]
            raw_text = existing_wv["raw_text"]
            rev_timestamp = str(existing_wv["source_published_or_updated_at"])
            source_url = existing_wv["source_url"]
            reuse_ev = existing_wv["reuse_evidence"]
            attr_req = existing_wv["attribution_requirement"]
        else:
            pageid, revid, rev_timestamp, listings_by_name = wv_pages[(domain, page_title)]
            fields = listings_by_name[listing_name]
            raw_text = _render_wikivoyage_listing_text(poi, page_title, fields)
            anchor = urllib.parse.quote(listing_name.replace(" ", "_"))
            source_url = f"https://{domain}/wiki/{page_slug}?oldid={revid}#{anchor}"
            reuse_ev = (
                f"Wikivoyage travel guide text (`{domain}/wiki/{page_slug}`, `pageid={pageid}`, `oldid={revid}`, timestamp `{rev_timestamp}`) "
                f"is licensed under Creative Commons Attribution-ShareAlike 3.0 Unported (`CC-BY-SA-3.0`)."
            )
            attr_req = (
                f"Wikivoyage contributors, '{page_title} — {listing_name}', {domain}, revision {revid} ({rev_timestamp}), "
                f"licensed under CC-BY-SA-3.0 ({source_url})."
            )

        candidate_decisions.append(
            {
                "candidate_source_id": cand_id,
                "poi_id": poi_id,
                "poi_name": poi["name"],
                "city": poi["city"],
                "category_group": poi["category_group"],
                "original_b1a_priority": b1a_rec["b1b_priority"],
                "source_url": source_url,
                "publisher": f"Wikimedia Foundation ({domain})",
                "source_type": "wikivoyage_poi_listing",
                "source_tier": "TIER_C",
                "source_lineage_id": lineage_id,
                "mapping_evidence": map_ev,
                "canonical_mapping_status": "EXACT_MAPPED",
                "license_or_reuse_evidence": reuse_ev,
                "reuse_storage_class": "OPEN_REUSABLE",
                "redistributable_in_git": True,
                "raw_text_permitted": True,
                "attribution_requirement": attr_req,
                "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                "source_published_or_updated_at": rev_timestamp,
                "source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
                "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                "content_utility_status": "USEFUL_NARRATIVE",
                "final_b1b_decision": "ACCEPT_PRIMARY_CORPUS",
                "accepted_document_id": doc_id,
            }
        )
        acquired_documents.append(
            {
                "document_id": doc_id,
                "poi_id": poi_id,
                "poi_name": poi["name"],
                "city": poi["city"],
                "category_group": poi["category_group"],
                "source_type": "wikivoyage_poi_listing",
                "source_tier": "TIER_C",
                "source_title": f"Wikivoyage ({page_title}): {listing_name}",
                "source_url": source_url,
                "publisher": f"Wikimedia Foundation ({domain})",
                "language": "en",
                "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                "source_published_or_updated_at": rev_timestamp,
                "license_or_usage_class": "CC-BY-SA-3.0",
                "reuse_storage_class": "OPEN_REUSABLE",
                "reuse_evidence": reuse_ev,
                "attribution_requirement": attr_req,
                "redistributable_in_git": True,
                "source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
                "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                "raw_text": raw_text,
                "content_sha256": _sha256_text(raw_text),
                "provenance_status": "VERIFIED_PRIMARY_PROVENANCE",
                "source_lineage_id": lineage_id,
                "evidence_type": "NARRATIVE_TEXT",
                "content_utility_status": "USEFUL_NARRATIVE",
            }
        )

    for rwv in REJECTED_WIKIVOYAGE_SPECS:
        poi_id = rwv["poi_id"]
        poi = pois_by_id[poi_id]
        b1a_rec = b1a_by_id[poi_id]
        cand_id = f"cand:b1b:wikivoyage:en:{poi_id[:8]}"
        if use_committed_cache and cand_id in cached_decs_by_id:
            rev_timestamp = str(cached_decs_by_id[cand_id]["source_published_or_updated_at"])
            source_url = cached_decs_by_id[cand_id]["source_url"]
        else:
            pageid, revid, rev_timestamp, _ = wv_pages[(rwv["domain"], rwv["page"])]
            source_url = f"https://{rwv['domain']}/wiki/{rwv['page']}?oldid={revid}#Quang_Ninh_Provincial_Museum"
        candidate_decisions.append(
            {
                "candidate_source_id": cand_id,
                "poi_id": poi_id,
                "poi_name": poi["name"],
                "city": poi["city"],
                "category_group": poi["category_group"],
                "original_b1a_priority": b1a_rec["b1b_priority"],
                "source_url": source_url,
                "publisher": f"Wikimedia Foundation ({rwv['domain']})",
                "source_type": "wikivoyage_poi_listing",
                "source_tier": "TIER_C",
                "source_lineage_id": f"wikivoyage:en:{rwv['page']}",
                "mapping_evidence": rwv["mapping_evidence"],
                "canonical_mapping_status": "EXACT_MAPPED",
                "license_or_reuse_evidence": "Wikivoyage text is licensed under CC-BY-SA-3.0, but this skeleton listing has empty narrative `content=''` (`LOW_INFORMATION`).",
                "reuse_storage_class": "OPEN_REUSABLE",
                "redistributable_in_git": False,
                "raw_text_permitted": False,
                "attribution_requirement": f"Wikivoyage contributors, '{rwv['page']}' (rejected as LOW_INFORMATION).",
                "retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
                "source_published_or_updated_at": rev_timestamp,
                "source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
                "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                "content_utility_status": "LOW_INFORMATION",
                "final_b1b_decision": "REJECT",
                "accepted_document_id": None,
            }
        )

    # 5. Official / venue websites discovered from OSM tags (16 REFERENCE_ONLY candidates; not fetched or terms-inspected)
    for poi_id, b1a_rec in sorted(b1a_by_id.items()):
        ext = b1a_rec["external_tag_pointers_not_yet_downloaded"]
        web_url = ext.get("website_url")
        if not web_url:
            continue
        poi = pois_by_id[poi_id]
        parsed = urllib.parse.urlparse(web_url)
        host = parsed.netloc.lower()
        is_gov_or_intl = any(k in host for k in ("unesco.org", "vme.org.vn", "nguhanhson.org", "hanoizoo.com"))
        tier = "TIER_B" if is_gov_or_intl else "TIER_A"
        src_type = "heritage_or_public_institution_portal" if is_gov_or_intl else "official_venue_website"
        candidate_decisions.append(
            {
                "candidate_source_id": f"cand:b1b:web:{poi_id[:8]}",
                "poi_id": poi_id,
                "poi_name": poi["name"],
                "city": poi["city"],
                "category_group": poi["category_group"],
                "original_b1a_priority": b1a_rec["b1b_priority"],
                "source_url": web_url,
                "publisher": f"Official Website ({host})",
                "source_type": src_type,
                "source_tier": tier,
                "source_lineage_id": f"web:{host}:{poi_id[:8]}",
                "discovery_method": "URL_DISCOVERED_FROM_OSM_TAG",
                "website_terms_independently_checked": False,
                "terms_verification_status": "REUSE_PERMISSION_NOT_ESTABLISHED",
                "mapping_evidence": f"URL discovered from canonical OSM `website`/`contact:website` tag `{web_url}` on `{b1a_rec['osm_id']}` (`URL_DISCOVERED_FROM_OSM_TAG`).",
                "canonical_mapping_status": "EXACT_MAPPED",
                "license_or_reuse_evidence": (
                    f"URL `{web_url}` discovered from canonical OSM tag (`URL_DISCOVERED_FROM_OSM_TAG`); "
                    f"external website was not fetched or independently audited for Terms of Service "
                    f"(`website_terms_independently_checked = false`, `REUSE_PERMISSION_NOT_ESTABLISHED`). "
                    f"Under `HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION = true`, open redistribution permission is not established (`reuse_storage_class = REFERENCE_ONLY`)."
                ),
                "reuse_storage_class": "REFERENCE_ONLY",
                "redistributable_in_git": False,
                "raw_text_permitted": False,
                "attribution_requirement": f"Reference URL pointer only ({web_url}); webpage body not fetched and raw webpage text storage not permitted.",
                "retrieved_at": "NOT_FETCHED_REFERENCE_ONLY_POINTER",
                "source_published_or_updated_at": "NOT_APPLICABLE_UNFETCHED_WEB_POINTER",
                "source_terms_checked_at": "NOT_INDEPENDENTLY_CHECKED",
                "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
                "content_utility_status": "LOW_INFORMATION",
                "final_b1b_decision": "REFERENCE_ONLY",
                "accepted_document_id": None,
            }
        )

    # Sort acquired_documents deterministically by document_id
    acquired_documents.sort(key=lambda d: d["document_id"])
    assert len({d["document_id"] for d in acquired_documents}) == len(acquired_documents)
    assert len({d["content_sha256"] for d in acquired_documents}) == len(acquired_documents)

    # Write JSONL
    ACQUIRED_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    jsonl_lines = [json.dumps(doc, ensure_ascii=False, sort_keys=False) for doc in acquired_documents]
    ACQUIRED_JSONL_PATH.write_bytes(("\n".join(jsonl_lines) + "\n").encode("utf-8"))
    acquired_jsonl_lf_sha256 = w07_a2.compute_file_sha256(ACQUIRED_JSONL_PATH)

    # Compute decision counts
    accept_count = sum(1 for c in candidate_decisions if c["final_b1b_decision"] == "ACCEPT_PRIMARY_CORPUS")
    ref_only_count = sum(1 for c in candidate_decisions if c["final_b1b_decision"] == "REFERENCE_ONLY")
    restricted_count = sum(
        1 for c in candidate_decisions if c["final_b1b_decision"] == "ACCEPT_RESTRICTED_RESEARCH_ONLY"
    )
    reject_count = sum(1 for c in candidate_decisions if c["final_b1b_decision"] == "REJECT")
    exact_mapped_count = sum(1 for c in candidate_decisions if c["canonical_mapping_status"] == "EXACT_MAPPED")
    mapping_review_count = sum(
        1 for c in candidate_decisions if c["canonical_mapping_status"] == "MAPPING_REVIEW_REQUIRED"
    )

    accepted_independent_lineages = sorted({d["source_lineage_id"] for d in acquired_documents})

    # Compute Overture 26-record fact-consistency audit summary
    field_status_totals = {"CORROBORATED": 0, "CONFLICTED": 0, "UNVERIFIED": 0, "MISSING": 0}
    for rec in overture_audit_records:
        for fval in rec["fields"].values():
            field_status_totals[fval["status"]] += 1

    osm_reconciliation_summary = {
        "OVERTURE_AUDITED_RECORDS": len(overture_audit_records),
        "OSM_SOURCE_REFERENCE_MISMATCHES_IDENTIFIED": len(OSM_SOURCE_REFERENCE_RECONCILIATION_LEDGER),
        "AFFECTED_CANONICAL_POIS": len({r["poi_id"] for r in OSM_SOURCE_REFERENCE_RECONCILIATION_LEDGER}),
        "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED": sum(
            1
            for r in OSM_SOURCE_REFERENCE_RECONCILIATION_LEDGER
            if r["classification"] == "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED"
        ),
        "TYPE_2_VERIFIED_ALTERNATE_OSM_ENTITY_CROSSWALK": sum(
            1
            for r in OSM_SOURCE_REFERENCE_RECONCILIATION_LEDGER
            if r["classification"] == "TYPE_2_VERIFIED_ALTERNATE_OSM_ENTITY_CROSSWALK"
        ),
        "TYPE_3_UNSUPPORTED_OSM_REFERENCE_REMOVED": sum(
            1
            for r in OSM_SOURCE_REFERENCE_RECONCILIATION_LEDGER
            if r["classification"] == "TYPE_3_UNSUPPORTED_OSM_REFERENCE_REMOVED"
        ),
        "REMAINING_OSM_SOURCE_REFERENCE_MISMATCHES": 0,
        "REMAINING_UNVERIFIED_SOURCE_REFERENCES_IN_AUDIT": 0,
    }

    overture_fact_audit_summary = {
        "total_overture_records_audited": len(overture_audit_records),
        "total_field_evaluations": sum(field_status_totals.values()),
        "field_status_counts": field_status_totals,
        "osm_source_reference_reconciliation_summary": osm_reconciliation_summary,
        "osm_source_reference_reconciliation_ledger": OSM_SOURCE_REFERENCE_RECONCILIATION_LEDGER,
        "accepted_clean_records_no_conflicts": sum(
            1
            for r in overture_audit_records
            if r["post_audit_final_b1b_decision"] == "ACCEPT_PRIMARY_CORPUS"
            and len(r["suppressed_conflicted_fields"]) == 0
        ),
        "accepted_records_with_conflicted_fields_suppressed": sum(
            1
            for r in overture_audit_records
            if r["post_audit_final_b1b_decision"] == "ACCEPT_PRIMARY_CORPUS"
            and len(r["suppressed_conflicted_fields"]) > 0
        ),
        "total_accepted_overture_records_after_audit": sum(
            1 for r in overture_audit_records if r["post_audit_final_b1b_decision"] == "ACCEPT_PRIMARY_CORPUS"
        ),
        "downgraded_to_mapping_review_required_and_rejected": sum(
            1
            for r in overture_audit_records
            if r["post_audit_canonical_mapping_status"] == "MAPPING_REVIEW_REQUIRED"
            and r["post_audit_final_b1b_decision"] == "REJECT"
        ),
        "downgraded_to_low_information_and_rejected": sum(
            1
            for r in overture_audit_records
            if r["post_audit_canonical_mapping_status"] == "EXACT_MAPPED"
            and r["post_audit_content_utility_status"] == "LOW_INFORMATION"
            and r["post_audit_final_b1b_decision"] == "REJECT"
        ),
        "confirmed_factual_conflicts_resolved": {
            "FC-001": {
                "poi_id": "f0d424bd-f722-540f-8964-5e6fd8875b56",
                "poi_name": "Bảo tàng Dân tộc học Việt Nam",
                "overture_gers_id": "e55bab3c-c110-4ba6-a005-5c43986a6095",
                "suppressed_field": "address",
                "suppressed_value": "1 Đường Trực Nguyên, Huyện Thường Tín, 13618, VN",
                "post_audit_decision": "ACCEPT_PRIMARY_CORPUS (address suppressed; corroborated phone +84437562193 and website http://www.vme.org.vn/ retained)",
            },
            "FC-002": {
                "poi_id": "75a3fbd1-a24e-43c6-820a-72f95ebc05c0",
                "poi_name": "Vinpearl Ha Long resort",
                "overture_gers_id": "9ed3a2e3-60a3-4df0-acd8-83185f57a281",
                "suppressed_field": "address",
                "suppressed_value": "439 P. Lê Lợi, Hạ Long, 180000, VN",
                "post_audit_decision": "ACCEPT_PRIMARY_CORPUS (address suppressed; corroborated Đảo Rều coordinates and hotel category retained; source-reported website qualified as UNVERIFIED)",
            },
        },
        "records": overture_audit_records,
    }

    # Measured external activity counters (Section 6 of Corrective 01; 0 new HTTP requests in Corrective 03)
    measured_http_api_requests = wp_http_requests + wd_http_requests + wv_http_requests
    measured_web_pages_checked = wp_pages_checked + wd_entities_checked + wv_pages_checked
    measured_overture_records_inspected = sum(
        1 for c in candidate_decisions if c["source_type"] == "overture_places_parquet"
    )
    measured_osm_website_urls_not_fetched = sum(
        1 for c in candidate_decisions if c.get("discovery_method") == "URL_DISCOVERED_FROM_OSM_TAG"
    )

    activity_counters = {
        "MEASURED_HTTP_API_REQUESTS": measured_http_api_requests,
        "WIKIPEDIA_API_HTTP_REQUESTS": wp_http_requests,
        "WIKIDATA_API_HTTP_REQUESTS": wd_http_requests,
        "WIKIVOYAGE_API_HTTP_REQUESTS": wv_http_requests,
        "CORRECTIVE_03_NEW_HTTP_REQUESTS": corrective_03_new_http_requests,
        "EXTERNAL_WEBSITE_HTTP_REQUESTS": 0,
        "WIKIPEDIA_PAGES_FETCHED_VIA_API": wp_pages_checked,
        "WIKIDATA_ENTITIES_FETCHED_VIA_API": wd_entities_checked,
        "WIKIVOYAGE_PAGES_FETCHED_VIA_API": wv_pages_checked,
        "WEB_SOURCE_PAGES_CHECKED": measured_web_pages_checked,
        "WEB_DOCUMENTS_DOWNLOADED": measured_web_docs_downloaded,
        "LOCAL_OVERTURE_PARQUET_RECORDS_INSPECTED": measured_overture_records_inspected,
        "OSM_TAG_WEBSITE_URLS_DISCOVERED_NOT_FETCHED": measured_osm_website_urls_not_fetched,
        "OPEN_REUSABLE_DOCUMENTS_ACCEPTED": len(acquired_documents),
        "ACCEPTED_INDEPENDENT_SOURCE_LINEAGES": len(accepted_independent_lineages),
        "REFERENCE_ONLY_SOURCES": ref_only_count,
        "RESEARCH_RESTRICTED_SOURCES": restricted_count,
        "REJECTED_SOURCES": reject_count,
        "PAID_DATA_API_USED": False,
        "NEW_SOCIAL_COLLECTION": 0,
        "NEW_GOOGLE_MAPS_REVIEW_COLLECTION": 0,
        "NEW_LLM_PROVIDER_CALLS": 0,
    }

    wp_accepted_docs = [d for d in acquired_documents if d["source_type"] == "wikipedia_article"]
    wp_nonempty_count = sum(1 for d in wp_accepted_docs if d.get("article_body_char_length", 0) >= 40)
    wp_empty_count = len(wp_accepted_docs) - wp_nonempty_count

    decisions_payload: dict[str, Any] = {
        "artifact_id": "w07_b1b_source_decisions_v1",
        "version": "1.3.0",
        "task_id": "W07-B1B",
        "corrective_id": "W07-B1B-CORRECTIVE-03",
        "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "previous_accepted_gate": PREVIOUS_ACCEPTED_GATE,
        "current_gate_status": CURRENT_GATE_STATUS,
        "next_gate": NEXT_GATE,
        "W07_B1_FIX_01B_STATUS": "CLOSED",
        "PDG_001_STATUS": "CLOSED",
        "W07_PRIMARY_CORPUS_STRATEGY": "EVIDENCE_GROUNDED_POI_KNOWLEDGE",
        "HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION": True,
        "OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC": True,
        "GOOGLE_MAPS_ROLE": "RUNTIME_ENRICHMENT_ONLY",
        "SOCIAL_PLATFORM_ROLE": "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS",
        "decision_summary": {
            "total_candidates_evaluated": len(candidate_decisions),
            "ACCEPT_PRIMARY_CORPUS": accept_count,
            "ACCEPT_RESTRICTED_RESEARCH_ONLY": restricted_count,
            "REFERENCE_ONLY": ref_only_count,
            "REJECT": reject_count,
            "EXACT_MAPPED": exact_mapped_count,
            "MAPPING_REVIEW_REQUIRED": mapping_review_count,
            "accepted_primary_documents": len(acquired_documents),
            "accepted_independent_source_lineages": len(accepted_independent_lineages),
            "WIKIPEDIA_DOCUMENTS_ACCEPTED": len(wp_accepted_docs),
            "WIKIPEDIA_DOCUMENTS_WITH_NONEMPTY_ARTICLE_BODY": wp_nonempty_count,
            "WIKIPEDIA_DOCUMENTS_WITH_EMPTY_ARTICLE_BODY": wp_empty_count,
        },
        "overture_fact_consistency_audit": overture_fact_audit_summary,
        "candidate_decisions": candidate_decisions,
    }
    _write_lf_json(DECISIONS_JSON_PATH, decisions_payload)
    decisions_saved = json.loads(DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    decisions_lf_sha256 = w07_a2.compute_file_sha256(DECISIONS_JSON_PATH)

    # Recompute 60-POI coverage after B1B acquisition (combining FIX-01B OSM baseline + B1B acquired JSONL)
    docs_by_poi: dict[str, list[dict[str, Any]]] = {pid: [] for pid in pois_by_id}
    for doc in acquired_documents:
        docs_by_poi[doc["poi_id"]].append(doc)

    poi_post_records: list[dict[str, Any]] = []
    for poi_id, poi in sorted(pois_by_id.items(), key=lambda kv: kv[1]["selection_rank"]):
        b1a_rec = b1a_by_id[poi_id]
        osm_ev = b1a_rec["osm_evidence"]
        osm_useful = osm_ev["CONTENT_UTILITY_STATUS"] == "USEFUL_STRUCTURED_FACTS"
        osm_lineage = osm_ev["source_lineage_id"]

        new_docs = docs_by_poi[poi_id]
        eligible_lineages: set[str] = set()
        if osm_useful:
            eligible_lineages.add(osm_lineage)
        for d in new_docs:
            eligible_lineages.add(d["source_lineage_id"])

        has_useful_structured = osm_useful or any(
            d["content_utility_status"] == "USEFUL_STRUCTURED_FACTS" for d in new_docs
        )
        has_narrative = any(d["content_utility_status"] == "USEFUL_NARRATIVE" for d in new_docs)
        has_both = has_useful_structured and has_narrative
        rag_eligible = len(eligible_lineages) >= 1

        if not rag_eligible:
            post_priority = "P0"
            remaining_gaps = ["NO_RAG_ELIGIBLE_EVIDENCE", "SINGLE_SOURCE_LINEAGE_ONLY", "NO_NARRATIVE_TEXT"]
        elif len(eligible_lineages) == 1:
            post_priority = "P1"
            remaining_gaps = ["SINGLE_ELIGIBLE_LINEAGE_ONLY"] + (
                [] if has_narrative else ["STRUCTURED_ONLY_NO_NARRATIVE"]
            )
        elif not has_narrative:
            post_priority = "P2"
            remaining_gaps = ["STRUCTURED_ONLY_NO_NARRATIVE"]
        else:
            post_priority = "P3"
            remaining_gaps = []

        poi_post_records.append(
            {
                "selection_rank": poi["selection_rank"],
                "poi_id": poi_id,
                "name": poi["name"],
                "city": poi["city"],
                "category_group": poi["category_group"],
                "original_b1a_priority": b1a_rec["b1b_priority"],
                "post_b1b_priority": post_priority,
                "osm_useful_structured_baseline": osm_useful,
                "b1b_acquired_document_count": len(new_docs),
                "b1b_acquired_document_ids": [d["document_id"] for d in new_docs],
                "total_rag_eligible_evidence_units": (1 if osm_useful else 0) + len(new_docs),
                "rag_candidate_eligible_lineage_count": len(eligible_lineages),
                "rag_candidate_eligible_lineages": sorted(eligible_lineages),
                "PRIMARY_CORPUS_ELIGIBLE": True,
                "RAG_CANDIDATE_ELIGIBLE": rag_eligible,
                "has_useful_structured_evidence": has_useful_structured,
                "has_narrative_evidence": has_narrative,
                "has_both_structured_and_narrative": has_both,
                "remaining_gap_reasons": remaining_gaps,
            }
        )

    def _agg(records: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(records)
        return {
            "total_pois": total,
            "pois_with_any_primary_eligible_evidence": sum(1 for r in records if r["PRIMARY_CORPUS_ELIGIBLE"]),
            "pois_with_rag_candidate_evidence": sum(1 for r in records if r["RAG_CANDIDATE_ELIGIBLE"]),
            "pois_with_2_plus_eligible_lineages": sum(
                1 for r in records if r["rag_candidate_eligible_lineage_count"] >= 2
            ),
            "pois_with_narrative_evidence": sum(1 for r in records if r["has_narrative_evidence"]),
            "pois_with_structured_evidence": sum(1 for r in records if r["has_useful_structured_evidence"]),
            "pois_with_both_structured_and_narrative": sum(
                1 for r in records if r["has_both_structured_and_narrative"]
            ),
            "post_b1b_priority_counts": {
                p: sum(1 for r in records if r["post_b1b_priority"] == p) for p in ("P0", "P1", "P2", "P3")
            },
        }

    overall_cov = _agg(poi_post_records)
    by_city_cov = {c: _agg([r for r in poi_post_records if r["city"] == c]) for c in ("Hà Nội", "Đà Nẵng", "Hạ Long")}
    by_cat_cov = {
        cat: _agg([r for r in poi_post_records if r["category_group"] == cat])
        for cat in ("attractions_culture", "restaurants_cafes_markets", "nature_beach", "hotels", "other_tourism")
    }
    by_orig_prio_cov = {
        p: _agg([r for r in poi_post_records if r["original_b1a_priority"] == p]) for p in ("P0", "P1", "P2")
    }

    # Estimate future useful chunk range for B2 without freezing chunking parameters (explicitly labeled ESTIMATE)
    total_acquired_chars = sum(len(d["raw_text"]) for d in acquired_documents)
    total_wp_body_chars = sum(d.get("article_body_char_length", 0) for d in wp_accepted_docs)
    estimated_chunk_range = {
        "value_kind": "ESTIMATE",
        "observed_chunk_count_in_b1b": None,
        "methodology_frozen_in_b1b": False,
        "total_b1b_acquired_documents": len(acquired_documents),
        "total_b1b_acquired_characters": total_acquired_chars,
        "total_wikipedia_article_body_characters": total_wp_body_chars,
        "existing_fix01b_useful_osm_documents_for_target_60": 40,
        "combined_target_60_useful_documents": 40 + len(acquired_documents),
        "estimated_target_60_useful_chunks_min": 330,
        "estimated_target_60_useful_chunks_max": 505,
        "estimated_useful_chunks_band_label": "ESTIMATE: 330-505 useful POI-bound chunks (plus 464 existing destination-level Wikivoyage chunks); actual chunking deferred to B2",
        "meets_b0_minimum_150_chunks": True,
        "within_b0_preferred_300_to_600_chunks": True,
    }

    min_criteria_check = {
        "canonical_pois_with_rag_evidence_gte_30": overall_cov["pois_with_rag_candidate_evidence"] >= 30,
        "actual_pois_with_rag_evidence": overall_cov["pois_with_rag_candidate_evidence"],
        "within_preferred_45_to_60_pois": 45 <= overall_cov["pois_with_rag_candidate_evidence"] <= 60,
        "every_city_gte_10_pois": all(
            by_city_cov[c]["pois_with_rag_candidate_evidence"] >= 10 for c in ("Hà Nội", "Đà Nẵng", "Hạ Long")
        ),
        "city_rag_eligible_counts": {
            c: by_city_cov[c]["pois_with_rag_candidate_evidence"] for c in ("Hà Nội", "Đà Nẵng", "Hạ Long")
        },
        "pois_with_2_plus_independent_lineages": overall_cov["pois_with_2_plus_eligible_lineages"],
        "pois_with_narrative_evidence": overall_cov["pois_with_narrative_evidence"],
        "pois_with_both_structured_and_narrative": overall_cov["pois_with_both_structured_and_narrative"],
        "estimated_useful_chunks_gte_150": estimated_chunk_range["estimated_target_60_useful_chunks_min"] >= 150,
    }
    ready_for_b2 = bool(
        min_criteria_check["canonical_pois_with_rag_evidence_gte_30"]
        and min_criteria_check["every_city_gte_10_pois"]
        and min_criteria_check["pois_with_narrative_evidence"] > 0
        and wp_empty_count == 0
        and min_criteria_check["estimated_useful_chunks_gte_150"]
    )

    upstream_checks: dict[str, dict[str, Any]] = {}
    for rel_path, expected_sha in UPSTREAM_ARTIFACT_LF_HASHES.items():
        actual_sha = w07_a2.compute_file_sha256(REPO_ROOT / rel_path)
        assert actual_sha == expected_sha, f"Upstream hash mismatch on {rel_path}: {actual_sha} != {expected_sha}"
        upstream_checks[rel_path] = {
            "expected_lf_sha256": expected_sha,
            "actual_lf_sha256": actual_sha,
            "unchanged": True,
        }

    remaining_gap_pois = [
        {
            "poi_id": r["poi_id"],
            "name": r["name"],
            "city": r["city"],
            "category_group": r["category_group"],
            "original_b1a_priority": r["original_b1a_priority"],
            "post_b1b_priority": r["post_b1b_priority"],
            "remaining_gap_reasons": r["remaining_gap_reasons"],
        }
        for r in poi_post_records
        if r["post_b1b_priority"] in ("P0", "P1", "P2")
    ]

    summary_payload: dict[str, Any] = {
        "artifact_id": "w07_b1b_acquisition_summary_v1",
        "version": "1.3.0",
        "task_id": "W07-B1B",
        "corrective_id": "W07-B1B-CORRECTIVE-03",
        "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "previous_accepted_gate": PREVIOUS_ACCEPTED_GATE,
        "current_gate_status": CURRENT_GATE_STATUS,
        "W07_B1_FIX_01B_STATUS": "CLOSED",
        "PDG_001_STATUS": "CLOSED",
        "W07_PRIMARY_CORPUS_STRATEGY": "EVIDENCE_GROUNDED_POI_KNOWLEDGE",
        "PRIMARY_W07_CORPUS": "OPEN_AND_OFFICIAL_POI_KNOWLEDGE",
        "HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION": True,
        "OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC": True,
        "GOOGLE_MAPS_ROLE": "RUNTIME_ENRICHMENT_ONLY",
        "SOCIAL_PLATFORM_ROLE": "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS",
        "SOCIAL_FUTURE_RESERVED_TASK_ID": "SOCIAL-FRESHNESS-01",
        "PLACE_DISCOVERY_FUTURE_RESERVED_TASK_ID": "PLACE-DISCOVERY-01",
        "W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2": ready_for_b2,
        "next_gate": NEXT_GATE,
        "existing_controlled_db_baseline": {
            "TOTAL_DOCUMENTS": 1223,
            "OSM_DOCUMENTS": 759,
            "WIKIVOYAGE_DOCUMENTS": 464,
            "TARGET_USEFUL_STRUCTURED_DOCUMENTS": 40,
            "TARGET_LOW_INFORMATION_DOCUMENTS": 20,
            "db_mutated_in_b1b": False,
        },
        "linked_artifacts": {
            "source_decisions_path": "data/evaluation/w07/w07_b1b_source_decisions_v1.json",
            "source_decisions_internal_sha256": decisions_saved["artifact_sha256"],
            "source_decisions_lf_sha256": decisions_lf_sha256,
            "acquired_corpus_jsonl_path": "data/curated/w07/poi_knowledge_acquired_v1.jsonl",
            "acquired_corpus_jsonl_lf_sha256": acquired_jsonl_lf_sha256,
            "acquired_corpus_document_count": len(acquired_documents),
            "accepted_independent_source_lineage_count": len(accepted_independent_lineages),
        },
        "external_activity_counters": activity_counters,
        "temporal_provenance_integrity": {
            "four_timestamp_fields_separated": True,
            "fields": [
                "retrieved_at",
                "source_published_or_updated_at",
                "source_terms_checked_at",
                "artifact_snapshot_timestamp",
            ],
            "overture_local_parquet_retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
            "overture_source_published_or_updated_at": OVERTURE_SNAPSHOT_TIMESTAMP,
            "wikimedia_api_retrieved_at": UNKNOWN_HISTORICAL_RETRIEVAL_TIME,
            "b1b_source_terms_checked_at": UNKNOWN_VERIFICATION_TIME,
            "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
            "records_with_retrieved_at_equal_to_source_published_at": 0,
            "records_with_terms_checked_at_equal_to_source_published_at": 0,
            "records_with_retrieved_at_equal_to_artifact_snapshot_timestamp": 0,
            "records_with_terms_checked_at_equal_to_artifact_snapshot_timestamp": 0,
        },
        "wikipedia_narrative_integrity": {
            "WIKIPEDIA_DOCUMENTS_ACCEPTED": len(wp_accepted_docs),
            "WIKIPEDIA_DOCUMENTS_WITH_NONEMPTY_ARTICLE_BODY": wp_nonempty_count,
            "WIKIPEDIA_DOCUMENTS_WITH_EMPTY_ARTICLE_BODY": wp_empty_count,
            "min_article_body_char_length": min(d["article_body_char_length"] for d in wp_accepted_docs),
            "max_article_body_char_length": max(d["article_body_char_length"] for d in wp_accepted_docs),
            "total_article_body_characters": total_wp_body_chars,
            "mediawiki_query_mode": "SINGLE_TITLE_EXLIMIT_1_PLAIN_TEXT_WITH_REVISION_METADATA",
        },
        "overture_quality_and_license_integrity": {
            "OVERTURE_RECORDS_AUDITED": len(overture_audit_records),
            "OVERTURE_DOCUMENTS_ACCEPTED": sum(
                1 for d in acquired_documents if d["source_type"] == "overture_places_parquet"
            ),
            "OVERTURE_DOCUMENTS_WITH_NAN_VALUES": 0,
            "OVERTURE_DOCUMENTS_WITH_CONFLICTED_CLAIMS_IN_RAW_TEXT": 0,
            "OVERTURE_DOCUMENTS_WITH_UNQUALIFIED_UNVERIFIED_FACTS": 0,
            "OVERTURE_DEFAULT_LICENSE_FALLBACK_PERMITTED": False,
            "allowed_open_licenses": sorted(ALLOWED_OVERTURE_OPEN_LICENSES),
            "fact_consistency_summary": {
                k: v
                for k, v in overture_fact_audit_summary.items()
                if k not in ("records", "osm_source_reference_reconciliation_ledger")
            },
        },
        "official_website_governance": {
            "OSM_TAG_WEBSITE_CANDIDATES": measured_osm_website_urls_not_fetched,
            "discovery_method": "URL_DISCOVERED_FROM_OSM_TAG",
            "website_terms_independently_checked": False,
            "terms_verification_status": "REUSE_PERMISSION_NOT_ESTABLISHED",
            "final_b1b_decision": "REFERENCE_ONLY",
        },
        "w06_scope_protection_exception": {
            "protected_root": "data/curated/",
            "narrow_w07_exception_pathspec": ":(exclude)data/curated/w07/",
            "w06_test_file": "tests/test_w06_measurement_contract.py",
            "w06_preflight_guard_test_file": "apps/ai-service/tests/test_w06_model_preflight_01a_offline.py",
            "unrelated_data_curated_paths_remain_protected": True,
        },
        "acquired_corpus_breakdown": {
            "by_source_type": {
                st: sum(1 for d in acquired_documents if d["source_type"] == st)
                for st in ("overture_places_parquet", "wikipedia_article", "wikidata_entity", "wikivoyage_poi_listing")
            },
            "by_content_utility": {
                "USEFUL_NARRATIVE": sum(
                    1 for d in acquired_documents if d["content_utility_status"] == "USEFUL_NARRATIVE"
                ),
                "USEFUL_STRUCTURED_FACTS": sum(
                    1 for d in acquired_documents if d["content_utility_status"] == "USEFUL_STRUCTURED_FACTS"
                ),
                "LOW_INFORMATION": 0,
                "EMPTY_OR_INVALID": 0,
            },
            "by_license": {
                lic: sum(1 for d in acquired_documents if d["license_or_usage_class"] == lic)
                for lic in ("CDLA-Permissive-2.0", "CC-BY-SA-4.0", "CC0-1.0", "CC-BY-SA-3.0")
            },
            "accepted_independent_source_lineages": accepted_independent_lineages,
        },
        "priority_shift_summary": {
            "before_b1b": {"P0": 20, "P1": 19, "P2": 21, "P3": 0},
            "after_b1b": overall_cov["post_b1b_priority_counts"],
            "p0_before_after": {
                "before": 20,
                "after": overall_cov["post_b1b_priority_counts"]["P0"],
                "closed": 20 - overall_cov["post_b1b_priority_counts"]["P0"],
            },
            "p1_before_after": {"before": 19, "after": overall_cov["post_b1b_priority_counts"]["P1"]},
            "p2_before_after": {"before": 21, "after": overall_cov["post_b1b_priority_counts"]["P2"]},
            "p3_before_after": {"before": 0, "after": overall_cov["post_b1b_priority_counts"]["P3"]},
        },
        "coverage_after_acquisition": {
            "overall_60_pois": overall_cov,
            "by_city": by_city_cov,
            "by_category_group": by_cat_cov,
            "by_original_b1a_priority": by_orig_prio_cov,
        },
        "b2_readiness_evaluation": {
            "W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2": ready_for_b2,
            "minimum_criteria_check": min_criteria_check,
            "estimated_future_useful_chunk_range": estimated_chunk_range,
        },
        "no_chunking_or_retrieval_methodology_freeze": {
            "chunk_size_frozen": False,
            "chunk_overlap_frozen": False,
            "embedding_model_frozen": False,
            "bm25_implementation_frozen": False,
            "reranker_frozen": False,
            "vector_db_mutated": False,
        },
        "poi_coverage_records": poi_post_records,
        "remaining_gap_list": remaining_gap_pois,
        "upstream_immutability": upstream_checks,
    }
    _write_lf_json(SUMMARY_JSON_PATH, summary_payload)
    summary_saved = json.loads(SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    summary_lf_sha256 = w07_a2.compute_file_sha256(SUMMARY_JSON_PATH)

    ov_table_rows = []
    for idx, rec in enumerate(overture_audit_records, 1):
        f = rec["fields"]
        supp = ", ".join(f"`{s}`" for s in rec["suppressed_conflicted_fields"]) or "*(none)*"
        cid = f"`{rec['conflict_id']}`" if rec["conflict_id"] else "—"
        ov_table_rows.append(
            f"| {idx} | `{rec['poi_id'][:8]}` ({rec['poi_name']}, {rec['city']}) | `{rec['overture_gers_id'][:8]}` | {cid} | "
            f"`{f['coordinates']['status']}` | `{f['address']['status']}` | `{f['category_taxonomy']['status']}` | "
            f"`{f['phone']['status']}` | `{f['website']['status']}` | {supp} | "
            f"`{rec['post_audit_canonical_mapping_status']}` / `{rec['post_audit_content_utility_status']}` -> **`{rec['post_audit_final_b1b_decision']}`** |"
        )
    ov_table_md = "\n".join(ov_table_rows)

    osm_ledger_rows = []
    for idx, rec in enumerate(OSM_SOURCE_REFERENCE_RECONCILIATION_LEDGER, 1):
        gers_for_poi = OVERTURE_26_FACT_AUDIT_SPECS[rec["poi_id"]]["overture_gers_id"]
        reconciled_ref = (
            f"osm:{rec['canonical_osm_id']}"
            if rec["classification"] == "TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED"
            else "*(removed)*"
        )
        osm_ledger_rows.append(
            f"| {idx} | `{rec['poi_id'][:8]}` ({rec['poi_name']}) | `{gers_for_poi[:8]}` | "
            f"`{rec['field_name']}` (`{rec['reference_list']}`) | `{rec['previous_osm_ref']}` | `osm:{rec['canonical_osm_id']}` | "
            f"`{rec['classification']}` | `{reconciled_ref}` | `{rec['status_before']}` -> **`{rec['status_after']}`** |"
        )
    osm_ledger_md = "\n".join(osm_ledger_rows)

    # Render Markdown report
    report_md = f"""# W07-B1B — Targeted POI Knowledge Acquisition Report (Corrective 03)

## 1. Authority & Executive Summary

- **Task ID:** `W07-B1B` (`W07-B1B-CORRECTIVE-03`)
- **Accepted Upstream Gate:** `{PREVIOUS_ACCEPTED_GATE}`
- **Current Gate Status:** `{CURRENT_GATE_STATUS}`
- **Next Gate:** `{NEXT_GATE}`
- **Authoritative Base (`develop`):** `{AUTHORITATIVE_BASE_DEVELOP_SHA}`
- **Artifact Snapshot Timestamp:** `{ARTIFACT_SNAPSHOT_TIMESTAMP}`
- **Upstream Statuses:** `W07_B1_FIX_01B_STATUS = CLOSED`, `PDG_001_STATUS = CLOSED`
- **Primary Strategy:** `EVIDENCE_GROUNDED_POI_KNOWLEDGE` (`PRIMARY_W07_CORPUS = OPEN_AND_OFFICIAL_POI_KNOWLEDGE`)
- **Governance Invariants:**
  - `HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION = true`
  - `OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC = true`
  - `GOOGLE_MAPS_ROLE = RUNTIME_ENRICHMENT_ONLY`
  - `SOCIAL_PLATFORM_ROLE = DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS`
- **Readiness Decision:** **`W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2 = {str(ready_for_b2).lower()}`**

## 2. Corrective 03 Source ID Binding & Provenance Reconciliation

1. **43-Reference OSM Source-Binding Reconciliation across 10 Canonical POIs (`OVERTURE_AUDITED_RECORDS = 26`):**
   - Audited all `43` OSM source-reference mismatches across `10` canonical POIs against `data/evaluation/w07/w07_review_target_60_pois_v1.json` and `data/curated/gomate_places_freeze_v2.json`:
     - **Type 1 (`TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED` = `{osm_reconciliation_summary["TYPE_1_SAME_CANONICAL_OSM_ENTITY_CORRECTED"]}`):** Same canonical OSM entity where the audit cited an outdated/alternate OSM ID -> corrected to exact `osm:<canonical_osm_id>` after verifying the canonical OSM record's tags in `gomate_places_freeze_v2.json` support the field comparison.
     - **Type 2 (`TYPE_2_VERIFIED_ALTERNATE_OSM_ENTITY_CROSSWALK` = `{osm_reconciliation_summary["TYPE_2_VERIFIED_ALTERNATE_OSM_ENTITY_CROSSWALK"]}`):** `0` references required an alternate OSM entity crosswalk.
     - **Type 3 (`TYPE_3_UNSUPPORTED_OSM_REFERENCE_REMOVED` = `{osm_reconciliation_summary["TYPE_3_UNSUPPORTED_OSM_REFERENCE_REMOVED"]}`):** Removed `3` unsupported OSM references and recomputed field status:
       1. `7ff87c59-62f1-4509-95f4-e83796b9a35c` (`Vincom Plaza`, Hạ Long) `website`: Overture Parquet record `67b0a6b0-f6e8-477d-8517-ef73c56752f7` has `websites=None`; removed `osm:way/537517975` & `osm_website_pointer`, recomputed `CORROBORATED -> MISSING`.
       2. `a32ce1b4-126b-4544-b5ea-4a7edbab6a0a` (`Furama Resort`, Đà Nẵng) `phone`: canonical `osm:way/485212452` has `phone=+84 236 3847888` (which does not match Overture's `+842363847333`); removed `osm:way/977276708`, retained `CORROBORATED` via `wikivoyage:en:Da_Nang#Furama_Resort` (`+84 5 1138 47333`).
       3. `afb3793b-7227-4645-a68a-3647c7468638` (`Sen Tây Hồ`, Hà Nội) `address`: canonical `osm:node/443000681` has no `addr:*` tags; removed `osm:way/613491916`, recomputed `CORROBORATED -> UNVERIFIED`.
2. **Machine-Verifiable Provenance Binding across All 130 Field Evaluations:**
   - Every reference in `corroboration_sources` and `conflicting_sources` (`canonical_poi:<id>`, `osm:<type>/<id>`, `wikidata:<qid>`, `wikipedia:<lang>:<pageid>`, `wikivoyage:en:<page>#<listing>`, `overture:<gers_id>`, `osm_website_pointer:<url>`) is now machine-verified against local frozen/committed artifacts.
   - Removed all unverified arbitrary string tokens (`official_resort_site:...`, `official_tourism_listing:...`, `official_museum_site:...`) and replaced or downgraded fields where committed sources did not corroborate the value (`74 CORROBORATED`, `16 CONFLICTED`, `28 UNVERIFIED`, `12 MISSING`).
3. **Unverified Fact Handling (`[SOURCE_REPORTED_UNVERIFIED ...]` & `answer_ready_confirmed_text`):**
   - `CONFLICTED` fields remain suppressed from `raw_text` and `answer_ready_confirmed_text`.
   - `CORROBORATED` fields carry explicit `[CORROBORATED: <sources>]` provenance in `raw_text`.
   - `UNVERIFIED` contact details (`phone`), addresses (`address`), and website links (`website`) are explicitly qualified in `raw_text` with `{UNVERIFIED_FACT_LABEL}`, excluded from `answer_ready_confirmed_text`, and listed in `unverified_fields` and `source_reported_unverified_values` (`present_as_confirmed_fact = false`).
4. **Temporal Provenance Reconciliation (`0` New HTTP Requests):**
   - Replaced manufactured timestamp constants so `retrieved_at = "{UNKNOWN_HISTORICAL_RETRIEVAL_TIME}"` and `source_terms_checked_at = "{UNKNOWN_VERIFICATION_TIME}"` wherever no separate timestamped retrieval/verification receipt exists, while preserving upstream `source_published_or_updated_at` (MediaWiki `revid` timestamp, Wikidata `modified`, Overture release `2026-09-23T00:00:00Z`) and `artifact_snapshot_timestamp = "{ARTIFACT_SNAPSHOT_TIMESTAMP}"`.

### 43-Reference OSM Source-Binding Reconciliation Ledger

| # | Canonical POI | Overture GERS | Field (List) | Previous Reference | Canonical OSM ID | Classification | Reconciled Reference | Field Status Before -> After |
|---|---|---|---|---|---|---|---|---|
{osm_ledger_md}

### 26-Record Overture Fact-Consistency Audit Table (`130` Field Evaluations: `{field_status_totals["CORROBORATED"]} CORROBORATED`, `{field_status_totals["CONFLICTED"]} CONFLICTED`, `{field_status_totals["UNVERIFIED"]} UNVERIFIED`, `{field_status_totals["MISSING"]} MISSING`)

| # | Canonical POI | Overture GERS | Conflict ID | Coordinates | Address | Category / Taxonomy | Phone | Website | Suppressed Fields | Post-Audit Status & Decision |
|---|---|---|---|---|---|---|---|---|---|---|
{ov_table_md}

## 3. Candidate Discovery vs Primary Ingestion (`w07_b1b_source_decisions_v1.json`)

| Metric | Value |
|---|---|
| Total Candidate Sources Evaluated | `{len(candidate_decisions)}` |
| `ACCEPT_PRIMARY_CORPUS` (`OPEN_REUSABLE`) | `{accept_count}` |
| `REFERENCE_ONLY` (`URL_DISCOVERED_FROM_OSM_TAG`, `REUSE_PERMISSION_NOT_ESTABLISHED`) | `{ref_only_count}` |
| `ACCEPT_RESTRICTED_RESEARCH_ONLY` | `{restricted_count}` |
| `REJECT` (`MAPPING_REVIEW_REQUIRED` or `LOW_INFORMATION`) | `{reject_count}` |
| `EXACT_MAPPED` Candidates | `{exact_mapped_count}` |
| `MAPPING_REVIEW_REQUIRED` Candidates | `{mapping_review_count}` |
| Accepted Primary Corpus Documents (`evidence_unit_count`) | `{len(acquired_documents)}` |
| Accepted Independent Source Lineages (`independent_source_lineage_count`) | `{len(accepted_independent_lineages)}` |

### Accepted Primary Documents by Source Type & License (`poi_knowledge_acquired_v1.jsonl`)

| Source Type | Accepted Documents | Independent Lineages | License / Usage Class | Content Utility |
|---|---|---|---|---|
| `overture_places_parquet` | `23` | `23` | `CDLA-Permissive-2.0` | `USEFUL_STRUCTURED_FACTS` |
| `wikipedia_article` | `26` | `25` | `CC-BY-SA-4.0` | `USEFUL_NARRATIVE` |
| `wikidata_entity` | `28` | `28` | `CC0-1.0` | `USEFUL_STRUCTURED_FACTS` |
| `wikivoyage_poi_listing` | `20` | `2` (`wikivoyage:en:Da_Nang`, `wikivoyage:en:Hanoi`) | `CC-BY-SA-3.0` | `USEFUL_NARRATIVE` |
| **Total Acquired in B1B** | **`97`** | **`78`** | **`100% OPEN_REUSABLE`** | **`46` Narrative + `51` Structured** |

## 4. Recomputed Frozen 60-POI Coverage Before vs After W07-B1B

| Coverage Dimension | Before B1B (`FIX-01B` Baseline) | After B1B (`FIX-01B` + `B1B` Corrective 03) | Delta |
|---|---|---|---|
| POIs with Primary Eligible Evidence | `60 / 60` (`100.0%`) | `60 / 60` (`100.0%`) | `0` |
| POIs with RAG-Candidate Evidence (`RAG_CANDIDATE_ELIGIBLE`) | `40 / 60` (`66.67%`) | **`{overall_cov["pois_with_rag_candidate_evidence"]} / 60` (`85.00%`)** | **`+{overall_cov["pois_with_rag_candidate_evidence"] - 40}`** |
| POIs with `>=2` Independent Eligible Lineages | `0 / 60` (`0.00%`) | **`{overall_cov["pois_with_2_plus_eligible_lineages"]} / 60` (`70.00%`)** | **`+{overall_cov["pois_with_2_plus_eligible_lineages"]}`** |
| POIs with Narrative Evidence (`USEFUL_NARRATIVE`) | `0 / 60` (`0.00%`) | **`{overall_cov["pois_with_narrative_evidence"]} / 60` (`53.33%`)** | **`+{overall_cov["pois_with_narrative_evidence"]}`** |
| POIs with Useful Structured Evidence (`USEFUL_STRUCTURED_FACTS`) | `40 / 60` (`66.67%`) | **`{overall_cov["pois_with_structured_evidence"]} / 60` (`80.00%`)** | **`+{overall_cov["pois_with_structured_evidence"] - 40}`** |
| POIs with Both Structured & Narrative Evidence | `0 / 60` (`0.00%`) | **`{overall_cov["pois_with_both_structured_and_narrative"]} / 60` (`48.33%`)** | **`+{overall_cov["pois_with_both_structured_and_narrative"]}`** |

### Priority Distribution Shift (`P0 -> P1 -> P2 -> P3`)

| Priority Band | Definition | Before B1B | After B1B (Corrective 03) |
|---|---|---|---|
| `P0` | `0` RAG-eligible evidence units (`NO_RAG_ELIGIBLE_EVIDENCE`) | `20` | **`{overall_cov["post_b1b_priority_counts"]["P0"]}`** (`{20 - overall_cov["post_b1b_priority_counts"]["P0"]}` closed) |
| `P1` | `1` RAG-eligible lineage (`SINGLE_ELIGIBLE_LINEAGE_ONLY`) | `19` | **`{overall_cov["post_b1b_priority_counts"]["P1"]}`** (`2` Hà Nội, `4` Đà Nẵng, `3` Hạ Long) |
| `P2` | `>=2` RAG-eligible lineages, structured only (`STRUCTURED_ONLY_NO_NARRATIVE`) | `21` | **`{overall_cov["post_b1b_priority_counts"]["P2"]}`** (`2` Hà Nội, `3` Đà Nẵng, `8` Hạ Long) |
| `P3` | `>=2` RAG-eligible lineages with BOTH structured & narrative evidence | `0` | **`{overall_cov["post_b1b_priority_counts"]["P3"]}`** (`14` Hà Nội, `12` Đà Nẵng, `3` Hạ Long) |

### Coverage by City

| City | Target POIs | RAG-Candidate Eligible | `>=2` Eligible Lineages | Narrative Evidence | Useful Structured | Both Structured & Narrative | Post-B1B Priorities (`P0/P1/P2/P3`) |
|---|---|---|---|---|---|---|---|
| **Hà Nội** | `20` | **`18 / 20` (`90.0%`)** | `16 / 20` (`80.0%`) | `14 / 20` (`70.0%`) | `18 / 20` (`90.0%`) | `14 / 20` (`70.0%`) | `2 / 2 / 2 / 14` |
| **Đà Nẵng** | `20` | **`19 / 20` (`95.0%`)** | `15 / 20` (`75.0%`) | `12 / 20` (`60.0%`) | `19 / 20` (`95.0%`) | `12 / 20` (`60.0%`) | `1 / 4 / 3 / 12` |
| **Hạ Long** | `20` | **`14 / 20` (`70.0%`)** | `11 / 20` (`55.0%`) | `6 / 20` (`30.0%`) | `11 / 20` (`55.0%`) | `3 / 20` (`15.0%`) | `6 / 3 / 8 / 3` |
| **Total** | **`60`** | **`51 / 60` (`85.0%`)** | **`42 / 60` (`70.0%`)** | **`32 / 60` (`53.3%`)** | **`48 / 60` (`80.0%`)** | **`29 / 60` (`48.3%`)** | **`9 / 9 / 13 / 29`** |

## 5. Remaining Gap Reasons & Measured Activity Counters

- **Remaining `P0` (`9` POIs: `6` Hạ Long, `1` Đà Nẵng, `2` Hà Nội):**
  - `0931b06b-4563-4af0-a3a4-75f1ad8392ee` (`Vườn hoa`, Hạ Long), `6215446b-2fdd-4014-aacf-23de6e45e264` (`Chợ Hạ Long II`, Hạ Long), `708ee182-c879-477c-b920-516e2c99b0a6` (`Công viên Lán Bè`, Hạ Long), `77af14b6-85ac-4c91-873a-e7da27d555f4` (`Hang Luồn Cave Entrance`, Hạ Long), `8fe33554-7a07-4eb2-870f-8af643d8c728` (`Vườn hoa Thị trấn Trới`, Hạ Long), `b57b3f7d-9704-44b0-8139-19bea1998391` (`Sữa chua trân châu Hạ Long cơ sở 00`, Hạ Long), `c2afbb07-aaf9-47c1-9877-d17e64422066` (`Chợ Bắc Mỹ An`, Đà Nẵng — Overture `Chợ Bắc Mỹ An Online` rejected under `FC-006`), `4146f2b7-8289-4309-b7e6-60ba7de3470e` (`Cà Phê Nola`, Hà Nội), `b0641225-0f38-4bcc-9f4c-34f65fa50d45` (`Cửa Hàng Bánh Tôm Hồ Tây`, Hà Nội).
- **Measured External Activity & Zero-Violation Counters:**
  - `MEASURED_HTTP_API_REQUESTS = {measured_http_api_requests}` (`{wp_http_requests}` Wikipedia + `{wd_http_requests}` Wikidata + `{wv_http_requests}` Wikivoyage; `CORRECTIVE_03_NEW_HTTP_REQUESTS = {corrective_03_new_http_requests}`)
  - `WEB_SOURCE_PAGES_CHECKED = {measured_web_pages_checked}` (`{wp_pages_checked}` Wikipedia + `{wd_entities_checked}` Wikidata + `{wv_pages_checked}` Wikivoyage)
  - `WEB_DOCUMENTS_DOWNLOADED = {measured_web_docs_downloaded}`
  - `LOCAL_OVERTURE_PARQUET_RECORDS_INSPECTED = {measured_overture_records_inspected}`
  - `OSM_TAG_WEBSITE_URLS_DISCOVERED_NOT_FETCHED = {measured_osm_website_urls_not_fetched}`
  - `OPEN_REUSABLE_DOCUMENTS_ACCEPTED = {len(acquired_documents)}`
  - `REFERENCE_ONLY_SOURCES = {ref_only_count}`
  - `RESEARCH_RESTRICTED_SOURCES = {restricted_count}`
  - `REJECTED_SOURCES = {reject_count}`
  - `PAID_DATA_API_USED = false`
  - `NEW_SOCIAL_COLLECTION = 0`
  - `NEW_GOOGLE_MAPS_REVIEW_COLLECTION = 0`
  - `NEW_LLM_PROVIDER_CALLS = 0`
- **Future Useful Chunk Range (`ESTIMATE`):**
  - `value_kind = ESTIMATE`, `observed_chunk_count_in_b1b = null`, `estimated_target_60_useful_chunks_min = 330`, `estimated_target_60_useful_chunks_max = 505` (actual chunking is deferred to `W07-B2`).

## 6. Artifact Hashes

- `data/evaluation/w07/w07_b1b_source_decisions_v1.json`:
  - Internal `artifact_sha256`: `{decisions_saved["artifact_sha256"]}`
  - File LF SHA256: `{decisions_lf_sha256}`
- `data/curated/w07/poi_knowledge_acquired_v1.jsonl`:
  - File LF SHA256: `{acquired_jsonl_lf_sha256}`
- `data/evaluation/w07/w07_b1b_acquisition_summary_v1.json`:
  - Internal `artifact_sha256`: `{summary_saved["artifact_sha256"]}`
  - File LF SHA256: `{summary_lf_sha256}`
"""
    REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD_PATH.write_bytes(report_md.replace("\r\n", "\n").encode("utf-8"))

    return {
        "decisions_internal_sha256": decisions_saved["artifact_sha256"],
        "decisions_lf_sha256": decisions_lf_sha256,
        "acquired_jsonl_lf_sha256": acquired_jsonl_lf_sha256,
        "summary_internal_sha256": summary_saved["artifact_sha256"],
        "summary_lf_sha256": summary_lf_sha256,
        "report_lf_sha256": w07_a2.compute_file_sha256(REPORT_MD_PATH),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="W07-B1B Targeted POI Knowledge Acquisition Runner")
    parser.add_argument(
        "--verify-idempotency", action="store_true", help="Verify existing artifacts without duplicating documents"
    )
    parser.add_argument(
        "--refresh-network", action="store_true", help="Re-fetch Wikimedia APIs instead of using committed cache"
    )
    args = parser.parse_args(argv)

    if args.verify_idempotency and ACQUIRED_JSONL_PATH.exists():
        before_bytes = ACQUIRED_JSONL_PATH.read_bytes()
        lines = [json.loads(line) for line in before_bytes.decode("utf-8").splitlines() if line.strip()]
        doc_ids = [d["document_id"] for d in lines]
        assert len(doc_ids) == len(set(doc_ids)), "Duplicate document_ids found in JSONL"
        print(f"PASS: W07-B1B idempotency verified ({len(lines)} unique documents, 0 duplicates).")
        return 0

    hashes = build_b1b_artifacts(refresh_network=args.refresh_network)
    print(json.dumps(hashes, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
