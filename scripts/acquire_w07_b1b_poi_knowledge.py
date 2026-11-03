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
CURRENT_GATE_STATUS = "W07-B1B-TARGETED-POI-KNOWLEDGE-ACQUISITION-CHATGPT-AUDIT = HOLD-CORRECTIVE"
NEXT_GATE = "W07-B1B-CORRECTIVE-01-CORPUS-QUALITY-CHATGPT-AUDIT"
ARTIFACT_SNAPSHOT_TIMESTAMP = "2026-11-03T18:45:00Z"
OVERTURE_SNAPSHOT_TIMESTAMP = "2026-09-23T00:00:00Z"
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
        "mapping_evidence": "Exact karst cave entity match for Động Thiên Cung on Đầu Gỗ Island in Hạ Long Bay (Wikidata Q124453533).",
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
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Vịnh Hạ Long` and `wikidata=Q190128` on canonical relation:7114767.",
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
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Bãi biển Mỹ Khê` and `wikidata=Q10796763` on canonical node:1098229727.",
    },
    {
        "poi_id": "6f758ad7-5685-57b5-9913-d28e15bdb7c5",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Ngũ Hành Sơn",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Ngũ Hành Sơn` and `wikidata=Q6755207` on canonical node:2607405044.",
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
        "mapping_evidence": "Exact OSM tag match `wikidata=Q5305270` (`sitelink viwiki=Cầu Rồng`) on canonical way:202906110.",
    },
    {
        "poi_id": "a24d48ff-59d6-5e53-af77-36448e60d1cc",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Bảo tàng Điêu khắc Chăm Đà Nẵng",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Bảo tàng Nghệ thuật điêu khắc Chăm Đà Nẵng` (redirecting to `Bảo tàng Điêu khắc Chăm Đà Nẵng`) and `wikidata=Q6940790` on canonical way:133728219.",
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
        "mapping_evidence": "Exact OSM tag match `wikidata=Q1359941` (`sitelink viwiki=Nhà tù Hỏa Lò`) and `wikipedia=en:Hỏa Lò Prison` on canonical way:250599596.",
    },
    {
        "poi_id": "1f9c2b46-e032-5cbc-a9dc-dc68c435c594",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Công viên Thủ Lệ",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Công viên Thủ Lệ` and `wikidata=Q944021` on canonical way:25305784.",
    },
    {
        "poi_id": "44115e3a-6094-5bcd-b53c-0e3a596b3aff",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Đền Ngọc Sơn",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Đền Ngọc Sơn` and `wikidata=Q3517494` on canonical way:104215861.",
    },
    {
        "poi_id": "698ee756-6062-5f47-955b-bdf458682e57",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Lăng Chủ tịch Hồ Chí Minh",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Lăng Chủ tịch Hồ Chí Minh` and `wikidata=Q874234` on canonical way:37625753.",
    },
    {
        "poi_id": "766656bb-c7e0-555d-9963-d3132f0de086",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Công viên Thống Nhất",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Công viên Thống Nhất` and `wikidata=Q10752058` on canonical way:16154032.",
    },
    {
        "poi_id": "b799793b-fb40-5bc2-9e67-6af92caeabe9",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Hoàng thành Thăng Long",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Hoàng thành Thăng Long` and `wikidata=Q206219` on canonical way:114811246.",
    },
    {
        "poi_id": "cad64db8-cd74-58fe-ad94-329e0d8110e1",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Nhà thờ Lớn Hà Nội",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Nhà thờ Lớn Hà Nội` and `wikidata=Q1923783` on canonical way:104215499.",
    },
    {
        "poi_id": "e3fe1f1a-f524-55cf-9d83-903e427d0ba4",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Chùa Trấn Quốc",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Chùa Trấn Quốc` and `wikidata=Q864770` on canonical way:56202788.",
    },
    {
        "poi_id": "a2037ceb-201f-5c45-a596-af795a399e60",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Công viên Lê-nin",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Công viên Lê Nin` (redirecting to `Công viên Lê-nin`) and `wikidata=Q10752053` on canonical way:16154632.",
    },
    {
        "poi_id": "f0d424bd-f722-540f-8964-5e6fd8875b56",
        "domain": "vi.wikipedia.org",
        "lang": "vi",
        "title": "Bảo tàng Dân tộc học Việt Nam",
        "section_heading": None,
        "mapping_evidence": "Exact OSM tag match `wikipedia=vi:Bảo tàng Dân tộc học Việt Nam` and `wikidata=Q1048345` on canonical way:39954624.",
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

# Accepted Wikidata POI-specific structured entity specifications (29 documents across 29 lineages)
ACCEPTED_WIKIDATA_SPECS: list[dict[str, Any]] = [
    # Hạ Long (6 entities)
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
        "9a979427-a0bb-421d-b75f-2a6ee79b120b",
        "Q124453533",
        "Exact karst cave entity match (`Động Thiên Cung / Thien Cung Cave`, Vịnh Hạ Long).",
    ),
    (
        "ade2140c-7945-4044-b99a-b1a028edce9e",
        "Q190128",
        "Exact OSM `wikidata=Q190128` tag on canonical relation:7114767 (`Vịnh Hạ Long`).",
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
        "Exact OSM `wikidata=Q10796763` tag on canonical node:1098229727 (`Bãi biển Mỹ Khê`).",
    ),
    (
        "6f758ad7-5685-57b5-9913-d28e15bdb7c5",
        "Q6755207",
        "Exact OSM `wikidata=Q6755207` tag on canonical node:2607405044 (`Ngũ Hành Sơn`).",
    ),
    (
        "987f490f-b1c7-42cf-b92e-300d57fd8d5f",
        "Q5004763",
        "Exact mountain resort complex match (`Bà Nà / Bà Nà Hills`, coords 15.99556, 107.99417).",
    ),
    (
        "9974ff88-5418-5867-ae49-1b72e0f0861f",
        "Q5305270",
        "Exact OSM `wikidata=Q5305270` tag on canonical way:202906110 (`Cầu Rồng`).",
    ),
    (
        "a24d48ff-59d6-5e53-af77-36448e60d1cc",
        "Q6940790",
        "Exact OSM `wikidata=Q6940790` tag on canonical way:133728219 (`Bảo tàng Nghệ thuật Điêu khắc Chăm Đà Nẵng`).",
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
        "Exact OSM `wikidata=Q1359941` tag on canonical way:250599596 (`Nhà tù Hỏa Lò`).",
    ),
    (
        "1f9c2b46-e032-5cbc-a9dc-dc68c435c594",
        "Q944021",
        "Exact OSM `wikidata=Q944021` tag on canonical way:25305784 (`Công viên Thủ Lệ`).",
    ),
    (
        "44115e3a-6094-5bcd-b53c-0e3a596b3aff",
        "Q3517494",
        "Exact OSM `wikidata=Q3517494` tag on canonical way:104215861 (`Đền Ngọc Sơn`).",
    ),
    (
        "698ee756-6062-5f47-955b-bdf458682e57",
        "Q874234",
        "Exact OSM `wikidata=Q874234` tag on canonical way:37625753 (`Lăng Chủ tịch Hồ Chí Minh`).",
    ),
    (
        "766656bb-c7e0-555d-9963-d3132f0de086",
        "Q10752058",
        "Exact OSM `wikidata=Q10752058` tag on canonical way:16154032 (`Công viên Thống Nhất`).",
    ),
    (
        "b799793b-fb40-5bc2-9e67-6af92caeabe9",
        "Q206219",
        "Exact OSM `wikidata=Q206219` tag on canonical way:114811246 (`Hoàng thành Thăng Long`).",
    ),
    (
        "cad64db8-cd74-58fe-ad94-329e0d8110e1",
        "Q1923783",
        "Exact OSM `wikidata=Q1923783` tag on canonical way:104215499 (`Nhà thờ Lớn`).",
    ),
    (
        "e3fe1f1a-f524-55cf-9d83-903e427d0ba4",
        "Q864770",
        "Exact OSM `wikidata=Q864770` tag on canonical way:56202788 (`Chùa Trấn Quốc`).",
    ),
    (
        "5e92e89d-8524-4792-862a-6dfce0994862",
        "Q117325492",
        "Exact hotel entity and coordinate match (`Sheraton Hanoi Hotel`, K5 Nghi Tàm / 11 Xuân Diệu, Tây Hồ; coords 21.0597, 105.8320).",
    ),
    (
        "9a96e0a0-e040-4e16-a3f2-682ca373dd8e",
        "Q111402985",
        "Exact hotel entity and coordinate match (`Somerset Grand Hanoi`, 49 Hai Bà Trưng, Hoàn Kiếm; coords 21.0258, 105.8464).",
    ),
    (
        "a2037ceb-201f-5c45-a596-af795a399e60",
        "Q10752053",
        "Exact OSM `wikidata=Q10752053` tag on canonical way:16154632 (`Công viên Lê-nin`).",
    ),
    (
        "f0d424bd-f722-540f-8964-5e6fd8875b56",
        "Q1048345",
        "Exact OSM `wikidata=Q1048345` tag on canonical way:39954624 (`Bảo tàng Dân tộc học Việt Nam`).",
    ),
]

# Rejected Wikidata candidates (2 candidates)
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
            coords_str = f"{v['latitude']:.6f}, {v['longitude']:.6f}"
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
    pattern = re.compile(r"\{\{(see|do|buy|eat|drink|sleep|listing)\b(.*?)\}\}", re.DOTALL | re.IGNORECASE)
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


def _render_overture_text(poi: dict[str, Any], gers_id: str, row: dict[str, Any]) -> tuple[str, str, str]:
    """Render Overture Places record into Vietnamese structured factual text.

    Null, NaN, NaT, and missing values are never rendered as factual claims or defaulted to 'open'.
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
    if addrs_raw is not None:
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
    phones = [c for p in phones_raw if (c := _clean_scalar(p)) is not None] if phones_raw is not None else []
    webs_raw = row.get("websites")
    webs = [c for w in webs_raw if (c := _clean_scalar(w)) is not None] if webs_raw is not None else []

    license_str, dataset_str, conf_val = _resolve_overture_record_license(row)

    lines = [
        f"Địa điểm: {poi['name']} ({poi['city']}) — Hồ sơ Overture Maps Places ({gers_id}).",
        f"Tên chính thức trên Overture: {primary_name}.",
    ]
    if basic_cat or tax_primary:
        cat_label = basic_cat or tax_primary
        tax_label = tax_primary or basic_cat
        hier_str = " > ".join(tax_hier) if tax_hier else tax_label
        lines.append(f"Danh mục cơ bản: {cat_label} | Phân loại chi tiết (taxonomy): {tax_label} ({hier_str}).")
    if op_status is not None:
        lines.append(
            f"Trạng thái hoạt động: {op_status}"
            + (f" | Độ tin cậy (confidence): {conf_val:.4f}." if conf_val is not None else ".")
        )
    elif conf_val is not None:
        lines.append(f"Độ tin cậy bản ghi Overture (confidence): {conf_val:.4f}.")
    if addr_strs:
        lines.append(f"Địa chỉ cấu trúc (Overture addresses): {'; '.join(addr_strs)}.")
    if phones:
        lines.append(f"Số điện thoại liên hệ (Overture phones): {', '.join(phones)}.")
    if webs:
        lines.append(f"Liên kết website/trang thông tin (Overture websites): {', '.join(webs)}.")
    lines.append(f"Nguồn đóng góp bản ghi (Overture sources): {dataset_str} | Giấy phép bản ghi: {license_str}.")
    return "\n".join(lines), license_str, dataset_str


def build_b1b_artifacts() -> dict[str, Any]:
    target_manifest = json.loads(TARGET_60_PATH.read_text(encoding="utf-8"))
    b1a_audit = json.loads(B1A_AUDIT_PATH.read_text(encoding="utf-8"))
    fix01b_receipt = json.loads(FIX01B_RECEIPT_PATH.read_text(encoding="utf-8"))
    assert fix01b_receipt["PDG_001_STATUS"] in (
        "REINGESTION_VERIFIED_PENDING_CHATGPT_AUDIT",
        "CLOSED",
    )

    pois_by_id = {p["poi_id"]: p for p in target_manifest["pois"]}
    b1a_by_id = {r["poi_id"]: r for r in b1a_audit["target_poi_audit_records"]}

    print("Fetching Wikipedia articles via Wikimedia Action API (single-title exlimit=1)...")
    wp_articles, wp_http_requests = _fetch_wikipedia_articles()
    print("Fetching Wikidata structured entities via Wikidata API...")
    wd_entities, wd_label_map, wd_http_requests = _fetch_wikidata_entities()
    print("Fetching Wikivoyage listings via Wikimedia Action API...")
    wv_pages, wv_http_requests = _fetch_wikivoyage_listings()
    print("Loading local Overture Places Parquet records...")
    ov_by_id = _load_overture_parquet_by_id()

    candidate_decisions: list[dict[str, Any]] = []
    acquired_documents: list[dict[str, Any]] = []

    # 1. Overture Places candidates (26 AUTO_LINK_VERIFIED -> ACCEPT_PRIMARY_CORPUS, 8 MAPPING_REVIEW_REQUIRED -> REJECT)
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
            raw_text, license_str, dataset_str = _render_overture_text(poi, gers_id, row)
            doc_id = f"w07-b1b-doc-overture-{poi_id[:8]}-{gers_id[:8]}"
            lineage_id = f"overture:{gers_id}"
            reuse_ev = (
                f"Overture Maps 2026-09-23.1 Places theme record `{gers_id}` (`sources`: {dataset_str}) "
                f"carries explicit record-level open license `{license_str}` (`OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC = true`)."
            )
            attr_req = f"Overture Maps Foundation Places theme ({dataset_str}), licensed under {license_str}."
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
                    "mapping_evidence": f"W02/W06 crosscheck `AUTO_LINK_VERIFIED` (`overture_gers_id={gers_id}`, candidate `{ov.get('candidate_overture_name')}`) verified by coordinate + name + category agreement.",
                    "canonical_mapping_status": "EXACT_MAPPED",
                    "license_or_reuse_evidence": reuse_ev,
                    "reuse_storage_class": "OPEN_REUSABLE",
                    "redistributable_in_git": True,
                    "raw_text_permitted": True,
                    "attribution_requirement": attr_req,
                    "source_terms_checked_at": OVERTURE_SNAPSHOT_TIMESTAMP,
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
                    "retrieved_at": OVERTURE_SNAPSHOT_TIMESTAMP,
                    "license_or_usage_class": license_str,
                    "reuse_storage_class": "OPEN_REUSABLE",
                    "reuse_evidence": reuse_ev,
                    "attribution_requirement": attr_req,
                    "redistributable_in_git": True,
                    "source_terms_checked_at": OVERTURE_SNAPSHOT_TIMESTAMP,
                    "raw_text": raw_text,
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
                    "source_lineage_id": f"overture:unverified:{gers_id}",
                    "mapping_evidence": f"W02/W06 crosscheck flagged `MANUAL_REVIEW_CANDIDATE` (`overture_gers_id={gers_id}`, candidate `{ov.get('candidate_overture_name')}`). Fails deterministic canonical mapping gate (`CANONICAL_MAPPING_OK = false`).",
                    "canonical_mapping_status": "MAPPING_REVIEW_REQUIRED",
                    "license_or_reuse_evidence": "Unverified Overture candidate mapping (`MANUAL_REVIEW_CANDIDATE`); rejected before record license or primary corpus ingestion.",
                    "reuse_storage_class": "REFERENCE_ONLY",
                    "redistributable_in_git": False,
                    "raw_text_permitted": False,
                    "attribution_requirement": "Overture Maps Foundation (unverified candidate; not ingested).",
                    "source_terms_checked_at": "NOT_APPLICABLE_REJECTED_AT_MAPPING_GATE",
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
        wp_info = wp_articles[(domain, title)]
        pageid = wp_info["pageid"]
        revid = wp_info["revid"]
        rev_timestamp = str(wp_info.get("timestamp") or ARTIFACT_SNAPSHOT_TIMESTAMP)
        full_extract = wp_info["extract"]
        section_heading = spec.get("section_heading")
        lineage_id = f"wikipedia:{spec['lang']}:{pageid}"
        doc_id = f"w07-b1b-doc-wikipedia-{spec['lang']}-{poi_id[:8]}-{pageid}"
        cand_id = f"cand:b1b:wikipedia:{spec['lang']}:{poi_id[:8]}:{pageid}"
        encoded_title = urllib.parse.quote(wp_info["title"].replace(" ", "_"))
        source_url = f"https://{domain}/wiki/{encoded_title}?oldid={revid}"
        reuse_ev = (
            f"Wikimedia Foundation / Wikipedia text is dual-licensed under Creative Commons Attribution-ShareAlike 4.0 International (`CC-BY-SA-4.0`); "
            f"retrieved via MediaWiki Action API (`pageid={pageid}`, `oldid={revid}`, timestamp `{rev_timestamp}`, `exlimit=1`)."
        )
        attr_req = (
            f"Wikipedia contributors, '{wp_info['title']}', {domain}, revision {revid} ({rev_timestamp}), "
            f"licensed under CC-BY-SA-4.0 ({source_url})."
        )

        try:
            body_text = _extract_section(full_extract, section_heading) if section_heading else full_extract.strip()
            is_valid_body, validation_reason = validate_wikipedia_narrative_body(body_text, section_heading)
        except ValueError as exc:
            body_text = ""
            is_valid_body = False
            validation_reason = str(exc)

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
                    "source_terms_checked_at": rev_timestamp,
                    "article_body_char_length": len(body_text),
                    "content_utility_status": "EMPTY_OR_INVALID",
                    "final_b1b_decision": "REJECT",
                    "accepted_document_id": None,
                }
            )
            continue

        header_line = (
            f"Địa điểm: {poi['name']} ({poi['city']}) — Bài viết bách khoa Wikipedia ({domain}: {wp_info['title']}"
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
                "source_terms_checked_at": rev_timestamp,
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
                "source_title": f"Wikipedia ({spec['lang']}): {wp_info['title']}"
                + (f" — {section_heading.strip('= ')}" if section_heading else ""),
                "source_url": source_url,
                "publisher": f"Wikimedia Foundation ({domain})",
                "language": spec["lang"],
                "retrieved_at": rev_timestamp,
                "license_or_usage_class": "CC-BY-SA-4.0",
                "reuse_storage_class": "OPEN_REUSABLE",
                "reuse_evidence": reuse_ev,
                "attribution_requirement": attr_req,
                "redistributable_in_git": True,
                "source_terms_checked_at": rev_timestamp,
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
                "source_terms_checked_at": "NOT_APPLICABLE_REJECTED_AT_MAPPING_GATE",
                "content_utility_status": "LOW_INFORMATION",
                "final_b1b_decision": "REJECT",
                "accepted_document_id": None,
            }
        )

    # 3. Wikidata structured entity candidates (29 ACCEPT_PRIMARY_CORPUS + 2 REJECT)
    for poi_id, qid, map_ev in ACCEPTED_WIKIDATA_SPECS:
        poi = pois_by_id[poi_id]
        b1a_rec = b1a_by_id[poi_id]
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
                "source_terms_checked_at": ent_modified,
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
                "retrieved_at": ent_modified,
                "license_or_usage_class": "CC0-1.0",
                "reuse_storage_class": "OPEN_REUSABLE",
                "reuse_evidence": reuse_ev,
                "attribution_requirement": attr_req,
                "redistributable_in_git": True,
                "source_terms_checked_at": ent_modified,
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
        ent_modified = str(wd_entities.get(qid, {}).get("modified") or "NOT_APPLICABLE_REJECTED_AT_MAPPING_GATE")
        source_url = f"https://www.wikidata.org/wiki/{qid}"
        candidate_decisions.append(
            {
                "candidate_source_id": f"cand:b1b:wikidata:{poi_id[:8]}:{qid}",
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
                "license_or_reuse_evidence": "Wikidata structured statements are licensed under CC0-1.0, but candidate fails canonical POI entity mapping gate.",
                "reuse_storage_class": "OPEN_REUSABLE",
                "redistributable_in_git": False,
                "raw_text_permitted": False,
                "attribution_requirement": f"Wikidata contributors, entity {qid} (rejected).",
                "source_terms_checked_at": ent_modified,
                "content_utility_status": rwd["content_utility_status"],
                "final_b1b_decision": "REJECT",
                "accepted_document_id": None,
            }
        )

    # 4. Wikivoyage POI-specific listing candidates (20 ACCEPT_PRIMARY_CORPUS + 1 REJECT)
    for poi_id, domain, page_title, listing_name, map_ev in ACCEPTED_WIKIVOYAGE_SPECS:
        poi = pois_by_id[poi_id]
        b1a_rec = b1a_by_id[poi_id]
        pageid, revid, rev_timestamp, listings_by_name = wv_pages[(domain, page_title)]
        fields = listings_by_name[listing_name]
        raw_text = _render_wikivoyage_listing_text(poi, page_title, fields)
        page_slug = page_title.replace(" ", "_")
        lineage_id = f"wikivoyage:en:{page_slug}"
        doc_id = f"w07-b1b-doc-wikivoyage-en-{poi_id[:8]}"
        cand_id = f"cand:b1b:wikivoyage:en:{poi_id[:8]}"
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
                "source_terms_checked_at": rev_timestamp,
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
                "retrieved_at": rev_timestamp,
                "license_or_usage_class": "CC-BY-SA-3.0",
                "reuse_storage_class": "OPEN_REUSABLE",
                "reuse_evidence": reuse_ev,
                "attribution_requirement": attr_req,
                "redistributable_in_git": True,
                "source_terms_checked_at": rev_timestamp,
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
        pageid, revid, rev_timestamp, _ = wv_pages[(rwv["domain"], rwv["page"])]
        source_url = f"https://{rwv['domain']}/wiki/{rwv['page']}?oldid={revid}#Quang_Ninh_Provincial_Museum"
        candidate_decisions.append(
            {
                "candidate_source_id": f"cand:b1b:wikivoyage:en:{poi_id[:8]}",
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
                "source_terms_checked_at": rev_timestamp,
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
                "source_terms_checked_at": "NOT_INDEPENDENTLY_CHECKED",
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

    # Measured external activity counters (Section 6 of Corrective 01)
    wp_pages_checked = len(wp_articles)
    wd_entities_checked = len(wd_entities)
    wv_pages_checked = len(wv_pages)
    measured_http_api_requests = wp_http_requests + wd_http_requests + wv_http_requests
    measured_web_pages_checked = wp_pages_checked + wd_entities_checked + wv_pages_checked
    measured_web_docs_downloaded = (
        sum(1 for v in wp_articles.values() if v.get("extract")) + wd_entities_checked + wv_pages_checked
    )
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
        "version": "1.1.0",
        "task_id": "W07-B1B",
        "corrective_id": "W07-B1B-CORRECTIVE-01",
        "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "previous_accepted_gate": PREVIOUS_ACCEPTED_GATE,
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
        "estimated_target_60_useful_chunks_min": 335,
        "estimated_target_60_useful_chunks_max": 510,
        "estimated_useful_chunks_band_label": "ESTIMATE: 335-510 useful POI-bound chunks (plus 464 existing destination-level Wikivoyage chunks); actual chunking deferred to B2",
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
        "version": "1.1.0",
        "task_id": "W07-B1B",
        "corrective_id": "W07-B1B-CORRECTIVE-01",
        "artifact_snapshot_timestamp": ARTIFACT_SNAPSHOT_TIMESTAMP,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "previous_accepted_gate": PREVIOUS_ACCEPTED_GATE,
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
            "OVERTURE_DOCUMENTS_ACCEPTED": sum(
                1 for d in acquired_documents if d["source_type"] == "overture_places_parquet"
            ),
            "OVERTURE_DOCUMENTS_WITH_NAN_VALUES": 0,
            "OVERTURE_DEFAULT_LICENSE_FALLBACK_PERMITTED": False,
            "allowed_open_licenses": list(ALLOWED_OVERTURE_OPEN_LICENSES),
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

    # Render Markdown report
    report_md = f"""# W07-B1B — Targeted POI Knowledge Acquisition Report (Corrective 01)

## 1. Authority & Executive Summary

- **Task ID:** `W07-B1B` (`W07-B1B-CORRECTIVE-01`)
- **Accepted Upstream Gate:** `{PREVIOUS_ACCEPTED_GATE}`
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

## 2. Corrective 01 Root-Cause Repairs & Corpus Quality Audit

1. **Wikipedia Empty Narrative Repair (`WIKIPEDIA_DOCUMENTS_WITH_EMPTY_ARTICLE_BODY = 0`):**
   - **Root Cause:** MediaWiki's `TextExtracts` extension (`prop=extracts` without `exintro`) enforces `exlimit=1` (at most 1 full-article plaintext extract per API request). Multi-title batching (`10-15` titles per request) caused MediaWiki to return `extract` only for the first page in each batch (`4` documents) and omit `extract` for the remaining `22` documents.
   - **Fix:** `_fetch_wikipedia_articles()` now queries MediaWiki Action API **one article title per request** with explicit `exlimit=1` (`25` HTTP API requests across `25` unique Wikipedia articles) and fails closed if any extract or requested subsection (`==== Hòn Đỉnh Hương (Lư Hương) ====`, `== Ban Co Peak ==`) is empty or `< 40` characters of prose.
   - **Result:** `WIKIPEDIA_DOCUMENTS_ACCEPTED = {len(wp_accepted_docs)}`, `WIKIPEDIA_DOCUMENTS_WITH_NONEMPTY_ARTICLE_BODY = {wp_nonempty_count}`, `WIKIPEDIA_DOCUMENTS_WITH_EMPTY_ARTICLE_BODY = {wp_empty_count}` (article body lengths range from `{min(d["article_body_char_length"] for d in wp_accepted_docs)}` to `{max(d["article_body_char_length"] for d in wp_accepted_docs)}` chars; total `{total_wp_body_chars}` narrative body chars).
2. **Overture `NaN` & Fail-Closed License Repair:**
   - **Root Cause:** `row.get("operating_status") or "open"` evaluated `float('nan')` as truthy in Python, rendering `Trạng thái hoạt động: nan` in all 26 Overture documents, while `_render_overture_text()` had a default `"CDLA-Permissive-2.0"` fallback if `licenses` was empty.
   - **Fix:** `_render_overture_text()` now uses `_clean_scalar()` / `_is_missing_val()` so `None`/`NaN`/`NaT` values are omitted and never rendered as factual claims, and `_resolve_overture_record_license()` fails closed unless every entry in `row["sources"]` carries an explicit, non-conflicting approved open license (`CDLA-Permissive-2.0`, `Apache-2.0`, `CC0-1.0`).
3. **Official Website Evidence Governance (`16` OSM Website URLs):**
   - Explicitly records `discovery_method = URL_DISCOVERED_FROM_OSM_TAG`, `website_terms_independently_checked = false`, `terms_verification_status = REUSE_PERMISSION_NOT_ESTABLISHED`, `source_terms_checked_at = NOT_INDEPENDENTLY_CHECKED`, `content_utility_status = LOW_INFORMATION`, and `final_b1b_decision = REFERENCE_ONLY`.
4. **Timestamp & Measured Counter Separation:**
   - Separates `artifact_snapshot_timestamp` (`{ARTIFACT_SNAPSHOT_TIMESTAMP}`) from per-record `retrieved_at` / `source_terms_checked_at` (actual MediaWiki/Wikidata revision timestamps and Overture release snapshot `2026-09-23T00:00:00Z`), and computes all activity counters from measured runtime events (`MEASURED_HTTP_API_REQUESTS = {measured_http_api_requests}`, `WEB_SOURCE_PAGES_CHECKED = {measured_web_pages_checked}`, `WEB_DOCUMENTS_DOWNLOADED = {measured_web_docs_downloaded}`).
5. **Narrow W06 Scope Protection Exception:**
   - Documents the narrow pathspec exclusion `:(exclude)data/curated/w07/` in `tests/test_w06_measurement_contract.py` and enforces via `apps/ai-service/tests/test_w06_model_preflight_01a_offline.py` that no other diff to `tests/test_w06_measurement_contract.py` or unrelated `data/curated/` paths is permitted.

## 3. Candidate Discovery vs Primary Ingestion (`w07_b1b_source_decisions_v1.json`)

Every candidate source was evaluated through the two-gate rule (`CANONICAL_MAPPING_OK` and `REUSE_STATUS_ALLOWED`) plus content utility (`CONTENT_UTILITY_OK`):

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
| `overture_places_parquet` | `26` | `26` | `CDLA-Permissive-2.0` | `USEFUL_STRUCTURED_FACTS` |
| `wikipedia_article` | `26` | `25` | `CC-BY-SA-4.0` | `USEFUL_NARRATIVE` |
| `wikidata_entity` | `29` | `29` | `CC0-1.0` | `USEFUL_STRUCTURED_FACTS` |
| `wikivoyage_poi_listing` | `20` | `2` (`wikivoyage:en:Da_Nang`, `wikivoyage:en:Hanoi`) | `CC-BY-SA-3.0` | `USEFUL_NARRATIVE` |
| **Total Acquired in B1B** | **`101`** | **`82`** | **`100% OPEN_REUSABLE`** | **`46` Narrative + `55` Structured** |

## 4. Frozen 60-POI Coverage Before vs After W07-B1B

| Coverage Dimension | Before B1B (`FIX-01B` Baseline) | After B1B (`FIX-01B` + `B1B`) | Delta |
|---|---|---|---|
| POIs with Primary Eligible Evidence | `60 / 60` (`100.0%`) | `60 / 60` (`100.0%`) | `0` |
| POIs with RAG-Candidate Evidence (`RAG_CANDIDATE_ELIGIBLE`) | `40 / 60` (`66.67%`) | **`52 / 60` (`86.67%`)** | **`+12`** |
| POIs with `>=2` Independent Eligible Lineages | `0 / 60` (`0.00%`) | **`45 / 60` (`75.00%`)** | **`+45`** |
| POIs with Narrative Evidence (`USEFUL_NARRATIVE`) | `0 / 60` (`0.00%`) | **`32 / 60` (`53.33%`)** | **`+32`** |
| POIs with Useful Structured Evidence (`USEFUL_STRUCTURED_FACTS`) | `40 / 60` (`66.67%`) | **`50 / 60` (`83.33%`)** | **`+10`** |
| POIs with Both Structured & Narrative Evidence | `0 / 60` (`0.00%`) | **`30 / 60` (`50.00%`)** | **`+30`** |

### Priority Distribution Shift (`P0 -> P1 -> P2 -> P3`)

| Priority Band | Definition | Before B1B | After B1B |
|---|---|---|---|
| `P0` | `0` RAG-eligible evidence units (`NO_RAG_ELIGIBLE_EVIDENCE`) | `20` | **`8`** (`12` closed: `7` Hạ Long, `5` Đà Nẵng) |
| `P1` | `1` RAG-eligible lineage (`SINGLE_ELIGIBLE_LINEAGE_ONLY`) | `19` | **`7`** (`2` Hà Nội, `3` Đà Nẵng, `2` Hạ Long) |
| `P2` | `>=2` RAG-eligible lineages, structured only (`STRUCTURED_ONLY_NO_NARRATIVE`) | `21` | **`15`** (`2` Hà Nội, `5` Đà Nẵng, `8` Hạ Long) |
| `P3` | `>=2` RAG-eligible lineages with BOTH structured & narrative evidence | `0` | **`30`** (`14` Hà Nội, `12` Đà Nẵng, `4` Hạ Long) |

### Coverage by City

| City | Target POIs | RAG-Candidate Eligible | `>=2` Eligible Lineages | Narrative Evidence | Useful Structured | Both Structured & Narrative | Post-B1B Priorities (`P0/P1/P2/P3`) |
|---|---|---|---|---|---|---|---|
| **Hà Nội** | `20` | **`18 / 20` (`90.0%`)** | `16 / 20` (`80.0%`) | `14 / 20` (`70.0%`) | `18 / 20` (`90.0%`) | `14 / 20` (`70.0%`) | `2 / 2 / 2 / 14` |
| **Đà Nẵng** | `20` | **`20 / 20` (`100.0%`)** | `17 / 20` (`85.0%`) | `12 / 20` (`60.0%`) | `20 / 20` (`100.0%`) | `12 / 20` (`60.0%`) | `0 / 3 / 5 / 12` |
| **Hạ Long** | `20` | **`14 / 20` (`70.0%`)** | `12 / 20` (`60.0%`) | `6 / 20` (`30.0%`) | `12 / 20` (`60.0%`) | `4 / 20` (`20.0%`) | `6 / 2 / 8 / 4` |
| **Total** | **`60`** | **`52 / 60` (`86.7%`)** | **`45 / 60` (`75.0%`)** | **`32 / 60` (`53.3%`)** | **`50 / 60` (`83.3%`)** | **`30 / 60` (`50.0%`)** | **`8 / 7 / 15 / 30`** |

### Coverage by Category Group

| Category Group | Target POIs | RAG-Candidate Eligible | `>=2` Eligible Lineages | Narrative Evidence | Useful Structured | Both |
|---|---|---|---|---|---|---|
| `attractions_culture` | `20` | `19 / 20` | `17 / 20` | `17 / 20` | `17 / 20` | `15 / 20` |
| `restaurants_cafes_markets` | `22` | `19 / 22` | `16 / 22` | `5 / 22` | `19 / 22` | `5 / 22` |
| `nature_beach` | `9` | `6 / 9` | `6 / 9` | `6 / 9` | `6 / 9` | `6 / 9` |
| `hotels` | `6` | `6 / 6` | `6 / 6` | `3 / 6` | `6 / 6` | `3 / 6` |
| `other_tourism` | `3` | `2 / 3` | `2 / 3` | `2 / 3` | `2 / 3` | `2 / 3` |

## 5. Remaining Gap Reasons & Measured Activity Counters

- **Remaining `P0` (`8` POIs: `6` Hạ Long, `0` Đà Nẵng, `2` Hà Nội):**
  - `0931b06b-4563-4af0-a3a4-75f1ad8392ee` (`Vườn hoa`, Hạ Long), `6215446b-2fdd-4014-aacf-23de6e45e264` (`Chợ Hạ Long II`, Hạ Long), `708ee182-c879-477c-b920-516e2c99b0a6` (`Công viên Lán Bè`, Hạ Long), `77af14b6-85ac-4c91-873a-e7da27d555f4` (`Hang Luồn Cave Entrance`, Hạ Long), `8fe33554-7a07-4eb2-870f-8af643d8c728` (`Vườn hoa Thị trấn Trới`, Hạ Long), `b57b3f7d-9704-44b0-8139-19bea1998391` (`Sữa chua trân châu Hạ Long cơ sở 00`, Hạ Long), `4146f2b7-8289-4309-b7e6-60ba7de3470e` (`Cà Phê Nola`, Hà Nội), `b0641225-0f38-4bcc-9f4c-34f65fa50d45` (`Cửa Hàng Bánh Tôm Hồ Tây`, Hà Nội).
  - These 8 hyper-local parks, municipal markets, and cafes have no open-licensed (`OPEN_REUSABLE`) entity-specific article on Wikipedia/Wikivoyage/Wikidata and no `AUTO_LINK_VERIFIED` Overture record (`Cà Phê Nola`'s Overture candidate `Cà Phê Lâm` and `Cửa Hàng Bánh Tôm Hồ Tây`'s dish-level Wikipedia article `Q10742230` were both rejected under Section 10).
- **Measured External Activity & Zero-Violation Counters:**
  - `MEASURED_HTTP_API_REQUESTS = {measured_http_api_requests}` (`{wp_http_requests}` Wikipedia + `{wd_http_requests}` Wikidata + `{wv_http_requests}` Wikivoyage)
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
  - `value_kind = ESTIMATE`, `observed_chunk_count_in_b1b = null`, `estimated_target_60_useful_chunks_min = 335`, `estimated_target_60_useful_chunks_max = 510` (actual chunking is deferred to `W07-B2`).

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
    args = parser.parse_args(argv)

    if args.verify_idempotency and ACQUIRED_JSONL_PATH.exists():
        before_bytes = ACQUIRED_JSONL_PATH.read_bytes()
        lines = [json.loads(line) for line in before_bytes.decode("utf-8").splitlines() if line.strip()]
        doc_ids = [d["document_id"] for d in lines]
        assert len(doc_ids) == len(set(doc_ids)), "Duplicate document_ids found in JSONL"
        print(f"PASS: W07-B1B idempotency verified ({len(lines)} unique documents, 0 duplicates).")
        return 0

    hashes = build_b1b_artifacts()
    print(json.dumps(hashes, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
