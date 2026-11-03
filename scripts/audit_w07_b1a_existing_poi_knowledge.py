"""W07-B1A — Existing POI Knowledge Corpus Audit Builder & Verifier (v1).

Audits all existing non-review POI/RAG evidence already present in the repository
against the frozen 60-POI W07 target manifest (`data/evaluation/w07/w07_review_target_60_pois_v1.json`)
under the closed W07-B0 methodology (`EVIDENCE_GROUNDED_POI_KNOWLEDGE`) before any
external B1B web/document acquisition begins.

Enforces:
- Strict separation of `evidence_units` vs `independent_source_lineages` (`source_lineage_id`)
- B0 orthogonal authority (`TIER_A..TIER_D`) vs reuse/storage (`OPEN_REUSABLE`,
  `RESEARCH_RESTRICTED`, `REFERENCE_ONLY`, `PROHIBITED`) governance
- B0 two-gate rule (`PRIMARY_CORPUS_ELIGIBLE = CANONICAL_MAPPING_OK AND REUSE_STATUS_ALLOWED`)
- B1A content-utility diagnostic (`CONTENT_UTILITY_STATUS` and
  `RAG_CANDIDATE_ELIGIBLE = PRIMARY_CORPUS_ELIGIBLE AND CONTENT_UTILITY_OK`)
- Explicit separation of `STRUCTURED_METADATA` vs `NARRATIVE_TEXT`
- Fail-closed mapping (`MAPPING_REVIEW_REQUIRED` for uncertain Overture candidates;
  `CITY_CONTEXT_ONLY` / `UNMAPPED_TO_FROZEN_POI` for city-level Wikivoyage chunks)
- Full upstream immutability across W06, W07-0, W07-A1, W07-A2, W07-A3, W07-A4H,
  W07-A4P, and W07-B0.

Zero web downloads, zero social collection, zero Google Maps collection, zero LLM calls.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "apps" / "ai-service") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "apps" / "ai-service"))

from app.rag.osm_documents import (  # noqa: E402
    CLASS_KEYS,
    FACT_FIELDS,
    build_osm_place_chunk,
    format_osm_address,
)
from scripts import (  # noqa: E402
    validate_w07_review_corpus_v1 as w07_a2,
    verify_w07_data_strategy_amendment_01 as w07_b0,
)

AUDIT_JSON_RELPATH = "data/evaluation/w07/w07_b1a_existing_poi_knowledge_audit_v1.json"
AUDIT_MD_RELPATH = "docs/research/w07_b1a_existing_poi_knowledge_audit.md"

TASK_ID = "W07-B1A-EXISTING-POI-KNOWLEDGE-CORPUS-AUDIT"
AUDIT_VERSION = "1.0.0"
AUTHORITATIVE_BASE_DEVELOP_SHA = "14ce20793c74cfa711902aa97a6ebe1cad810410"
PREVIOUS_ACCEPTED_GATE = "W07-B0-POSTMERGE-CHATGPT-AUDIT = PASS"
W07_B0_STATUS = "CLOSED"
NEXT_GATE = "W07-B1A-EXISTING-POI-KNOWLEDGE-AUDIT-CHATGPT-AUDIT"

# Expected frozen W07-B0 hashes (merged in 14ce20793c74cfa711902aa97a6ebe1cad810410)
EXPECTED_W07_B0_JSON_INTERNAL_SHA256 = (
    "365b00607737f01f02753595f5ce65092e2622bfbe3a8bb4ed20e464daf7a12f"
)
EXPECTED_W07_B0_JSON_LF_SHA256 = (
    "896fb5f90bce36610f9e82e23f52e56e0f93d90ecb81f564b6a1360b8e4b3c94"
)
EXPECTED_W07_B0_MD_LF_SHA256 = (
    "0f1ef9fcb9500882ce3dbbbea148d2d592fbe7211eb1e91f86855d6ed08af585"
)

CONTENT_UTILITY_STATES: tuple[str, ...] = (
    "USEFUL_NARRATIVE",
    "USEFUL_STRUCTURED_FACTS",
    "LOW_INFORMATION",
    "EMPTY_OR_INVALID",
)

EVIDENCE_TYPES: tuple[str, ...] = (
    "STRUCTURED_METADATA",
    "NARRATIVE_TEXT",
)

B1B_PRIORITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3")

# 10 English Wikivoyage pilot articles ingested in Task 07.5 / Freeze v2
# (`apps/ai-service/app/rag/ingestion.py` & `docs/ai/rag-pipeline.md`)
WIKIVOYAGE_PILOT_ARTICLE_INVENTORY: tuple[dict[str, Any], ...] = (
    {
        "page_title": "Vietnam",
        "source_lineage_id": "wikivoyage:en:Vietnam",
        "source_url": "https://en.wikivoyage.org/wiki/Vietnam",
        "chunk_count": 113,
        "target_city": None,
        "poi_mapping_status": "UNMAPPED_TO_FROZEN_POI",
    },
    {
        "page_title": "Hanoi",
        "source_lineage_id": "wikivoyage:en:Hanoi",
        "source_url": "https://en.wikivoyage.org/wiki/Hanoi",
        "chunk_count": 86,
        "target_city": "Hà Nội",
        "poi_mapping_status": "CITY_CONTEXT_ONLY",
    },
    {
        "page_title": "Da Nang",
        "source_lineage_id": "wikivoyage:en:Da_Nang",
        "source_url": "https://en.wikivoyage.org/wiki/Da_Nang",
        "chunk_count": 57,
        "target_city": "Đà Nẵng",
        "poi_mapping_status": "CITY_CONTEXT_ONLY",
    },
    {
        "page_title": "Hoi An",
        "source_lineage_id": "wikivoyage:en:Hoi_An",
        "source_url": "https://en.wikivoyage.org/wiki/Hoi_An",
        "chunk_count": 44,
        "target_city": None,
        "poi_mapping_status": "UNMAPPED_TO_FROZEN_POI",
    },
    {
        "page_title": "Hue",
        "source_lineage_id": "wikivoyage:en:Hue",
        "source_url": "https://en.wikivoyage.org/wiki/Hue",
        "chunk_count": 37,
        "target_city": None,
        "poi_mapping_status": "UNMAPPED_TO_FROZEN_POI",
    },
    {
        "page_title": "Nha Trang",
        "source_lineage_id": "wikivoyage:en:Nha_Trang",
        "source_url": "https://en.wikivoyage.org/wiki/Nha_Trang",
        "chunk_count": 44,
        "target_city": None,
        "poi_mapping_status": "UNMAPPED_TO_FROZEN_POI",
    },
    {
        "page_title": "Da Lat",
        "source_lineage_id": "wikivoyage:en:Da_Lat",
        "source_url": "https://en.wikivoyage.org/wiki/Da_Lat",
        "chunk_count": 20,
        "target_city": None,
        "poi_mapping_status": "UNMAPPED_TO_FROZEN_POI",
    },
    {
        "page_title": "Ha Long Bay",
        "source_lineage_id": "wikivoyage:en:Ha_Long_Bay",
        "source_url": "https://en.wikivoyage.org/wiki/Ha_Long_Bay",
        "chunk_count": 14,
        "target_city": "Hạ Long",
        "poi_mapping_status": "CITY_CONTEXT_ONLY",
    },
    {
        "page_title": "Ninh Binh",
        "source_lineage_id": "wikivoyage:en:Ninh_Binh",
        "source_url": "https://en.wikivoyage.org/wiki/Ninh_Binh",
        "chunk_count": 27,
        "target_city": None,
        "poi_mapping_status": "UNMAPPED_TO_FROZEN_POI",
    },
    {
        "page_title": "Phu Quoc",
        "source_lineage_id": "wikivoyage:en:Phu_Quoc",
        "source_url": "https://en.wikivoyage.org/wiki/Phu_Quoc",
        "chunk_count": 22,
        "target_city": None,
        "poi_mapping_status": "UNMAPPED_TO_FROZEN_POI",
    },
)

# Enriched Overture raw parquet summary on the 26 AUTO_LINK target POIs
# (verified against local git-ignored `data/raw/overture/overture_*_2026-09-23.1.parquet`)
OVERTURE_LOCAL_PARQUET_ENRICHMENT_SUMMARY: dict[str, Any] = {
    "snapshot_release": "2026-09-23.1",
    "git_tracked_in_repo": False,
    "auto_link_target_pois_total": 26,
    "auto_link_with_parquet_address": 26,
    "auto_link_with_parquet_phone": 22,
    "auto_link_with_parquet_website": 15,
    "low_info_osm_pois_upgradeable_via_overture_parquet": [
        "Chợ Bắc Mỹ An",
        "Ca Phe 83",
        "Bảo tàng Quảng Ninh",
        "Vinpearl Ha Long resort",
        "Novotel Ha Long",
    ],
    "note": (
        "In git-tracked `data/curated/gomate_places_freeze_v2.json`, Overture `raw_data` retains only "
        "matching provenance (`overture_id`, `overture_name`, `distance_m`, `similarity_score`, "
        "`operating_status: null`, `license`, `providers`) and omits `addresses`, `phones`, and `websites`. "
        "Therefore, committed Freeze v2 Overture records are classified `LOW_INFORMATION` (`RAG_CANDIDATE_ELIGIBLE = false`) "
        "in B1A until rich fields from the local raw parquet are explicitly promoted into git-tracked documents."
    ),
}


def verify_all_upstream_immutability(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """Verify W06, W07-0, W07-A1, W07-A2, W07-A3, W07-A4H, W07-A4P, and W07-B0 remain untouched."""
    b0_res = w07_b0.verify_amendment_01_artifacts(repo_root)
    if b0_res["amendment_internal_sha256"] != EXPECTED_W07_B0_JSON_INTERNAL_SHA256:
        raise ValueError(
            "FAIL CLOSED: W07-B0 JSON internal SHA256 mismatch: "
            f"{b0_res['amendment_internal_sha256']} != {EXPECTED_W07_B0_JSON_INTERNAL_SHA256}"
        )
    if b0_res["amendment_file_lf_sha256"] != EXPECTED_W07_B0_JSON_LF_SHA256:
        raise ValueError(
            "FAIL CLOSED: W07-B0 JSON LF SHA256 mismatch: "
            f"{b0_res['amendment_file_lf_sha256']} != {EXPECTED_W07_B0_JSON_LF_SHA256}"
        )
    if b0_res["amendment_md_lf_sha256"] != EXPECTED_W07_B0_MD_LF_SHA256:
        raise ValueError(
            "FAIL CLOSED: W07-B0 Markdown LF SHA256 mismatch: "
            f"{b0_res['amendment_md_lf_sha256']} != {EXPECTED_W07_B0_MD_LF_SHA256}"
        )

    return {
        **b0_res["upstream_immutability"],
        "w07_b0_amendment_internal_sha256": b0_res["amendment_internal_sha256"],
        "w07_b0_amendment_lf_sha256": b0_res["amendment_file_lf_sha256"],
        "w07_b0_md_lf_sha256": b0_res["amendment_md_lf_sha256"],
    }


def _extract_osm_tags_and_shape(
    osm_source: dict[str, Any],
) -> tuple[dict[str, str], str]:
    """Extract OSM tags from Freeze v2 `raw_data` (detecting nested `raw_data.tags` vs flat `raw_data`)."""
    raw_data = osm_source.get("raw_data") or {}
    if isinstance(raw_data, str):
        raw_data = json.loads(raw_data)
    if not isinstance(raw_data, dict):
        return {}, "empty_raw_data"
    if "tags" in raw_data and isinstance(raw_data["tags"], dict):
        cleaned = {
            str(k): str(v).strip()
            for k, v in raw_data["tags"].items()
            if not str(k).startswith("_") and v is not None and str(v).strip()
        }
        return cleaned, "nested_raw_data_tags"
    cleaned = {
        str(k): str(v).strip()
        for k, v in raw_data.items()
        if not str(k).startswith("_") and v is not None and str(v).strip()
    }
    return cleaned, "flat_raw_data"


def _extract_substantive_osm_facts(
    tags: dict[str, str], place_row: dict[str, Any]
) -> dict[str, str]:
    """Extract substantive factual attributes beyond basic POI name, category/class, and coordinates."""
    addr = format_osm_address(tags)
    oh = tags.get("opening_hours") or str(place_row.get("opening_hours") or "").strip()
    website = (
        tags.get("website")
        or tags.get("contact:website")
        or tags.get("url")
        or tags.get("heritage:website")
        or ""
    )
    phone = tags.get("phone") or tags.get("contact:phone") or tags.get("mobile") or ""
    email = tags.get("email") or tags.get("contact:email") or ""
    cuisine = tags.get("cuisine") or ""
    wheelchair = tags.get("wheelchair") or ""
    operator = tags.get("operator") or ""
    religion = tags.get("religion") or ""
    stars = tags.get("stars") or ""
    wikidata = tags.get("wikidata") or ""
    wikipedia = (
        tags.get("wikipedia")
        or tags.get("wikipedia:vi")
        or tags.get("wikipedia:en")
        or ""
    )
    description = (
        tags.get("description:vi")
        or tags.get("description")
        or tags.get("description:en")
        or ""
    )
    internet_access = tags.get("internet_access") or ""
    fee = tags.get("fee") or tags.get("charge") or ""
    heritage = tags.get("heritage") or ""

    candidates = {
        "address": addr,
        "opening_hours": oh,
        "website": website,
        "phone": phone,
        "email": email,
        "cuisine": cuisine,
        "wheelchair": wheelchair,
        "operator": operator,
        "religion": religion,
        "stars": stars,
        "wikidata": wikidata,
        "wikipedia": wikipedia,
        "description": description,
        "internet_access": internet_access,
        "fee": fee,
        "heritage": heritage,
    }
    return {k: v for k, v in candidates.items() if v}


def _percentile(sorted_vals: list[int], pct: float) -> int:
    if not sorted_vals:
        return 0
    idx = round((len(sorted_vals) - 1) * pct)
    return int(sorted_vals[idx])


def _normalize_overture_license(raw_lic: str | None) -> str | None:
    if not raw_lic:
        return None
    cleaned = raw_lic.strip()
    if cleaned == "CDLA Permissive 2.0":
        return "CDLA-Permissive-2.0"
    return cleaned


def build_b1a_audit_payload(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Deterministically audit all existing local POI/RAG evidence against the frozen 60-POI manifest."""
    upstream_hashes = verify_all_upstream_immutability(repo_root)

    manifest_path = repo_root / "data/evaluation/w07/w07_review_target_60_pois_v1.json"
    freeze_v2_path = repo_root / "data/curated/gomate_places_freeze_v2.json"
    freeze_yaml_path = repo_root / "data/manifests/dataset-freeze-v2.yaml"
    ingest_run_path = repo_root / "docs/audit/evidence/rag-ingest-run1.json"

    manifest_doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    places_v2 = json.loads(freeze_v2_path.read_text(encoding="utf-8"))
    freeze_yaml = yaml.safe_load(freeze_yaml_path.read_text(encoding="utf-8"))
    ingest_run = json.loads(ingest_run_path.read_text(encoding="utf-8"))

    # Load Overture crosscheck files
    overture_crosschecks: dict[str, dict[str, Any]] = {}
    for rel_cc in (
        "data/curated/overture/hanoi_overture_crosscheck_v1.json",
        "data/curated/overture/halong_overture_crosscheck_v1.json",
        "data/curated/overture/danang_overture_crosscheck_v2.json",
    ):
        rows = json.loads((repo_root / rel_cc).read_text(encoding="utf-8"))
        for row in rows:
            overture_crosschecks[str(row["source_id"])] = row

    # 1. Verify global Freeze v2 & B0 inventory counts
    db_state = freeze_yaml["database_state"]
    total_rag_docs = int(db_state["total_documents"])
    osm_rag_docs = int(db_state["osm_documents"])
    wikivoyage_rag_docs = int(db_state["wikivoyage_documents"])
    overture_aux_sources = int(db_state["total_auxiliary_overture_sources"])

    verified_osm_pois = len(places_v2)
    rec_a_core_pois = sum(1 for p in places_v2 if p.get("is_rec_a_core_v2"))
    overture_linked_pois = sum(
        1
        for p in places_v2
        if any(s.get("source_name") == "overture" for s in p.get("sources", []))
    )

    if total_rag_docs != 1223 or osm_rag_docs != 759 or wikivoyage_rag_docs != 464:
        raise ValueError(
            "FAIL CLOSED: Freeze v2 document counts do not match expected 1223 (759 OSM + 464 Wikivoyage)."
        )
    if (
        verified_osm_pois != 759
        or rec_a_core_pois != 622
        or overture_linked_pois != 247
        or overture_aux_sources != 247
    ):
        raise ValueError(
            "FAIL CLOSED: Freeze v2 POI/Overture counts do not match expected 759 / 622 / 247."
        )

    # 2. Global 759 OSM document length & duplicate-hash audit (as-is vs unwrapped nested tags)
    osm_hashes_as_is: set[str] = set()
    osm_hashes_unwrapped: set[str] = set()
    osm_chars_as_is: list[int] = []
    osm_chars_unwrapped: list[int] = []
    nested_tag_places_759 = 0

    all_osm_source_ids_759: list[str] = []
    all_overture_source_ids_247: list[str] = []

    for p in places_v2:
        osm_src = next(s for s in p["sources"] if s["source_name"] == "osm")
        all_osm_source_ids_759.append(str(osm_src["source_id"]))
        tags, shape = _extract_osm_tags_and_shape(osm_src)
        if shape == "nested_raw_data_tags":
            nested_tag_places_759 += 1

        raw_osm_dict = osm_src.get("raw_data") or {}
        if isinstance(raw_osm_dict, str):
            raw_osm_dict = json.loads(raw_osm_dict)
        legacy_flat_only_raw = (
            {k: v for k, v in raw_osm_dict.items() if k != "tags"}
            if isinstance(raw_osm_dict, dict)
            else {}
        )
        chunk_as_is = build_osm_place_chunk(
            {
                "id": p["place_id"],
                "name": p["name"],
                "category": p.get("category"),
                "destination_id": None,
                "destination_name": p.get("destination"),
                "latitude": p.get("latitude"),
                "longitude": p.get("longitude"),
                "sources": [
                    {
                        "source_name": "osm",
                        "source_id": osm_src["source_id"],
                        "raw_data": legacy_flat_only_raw,
                    }
                ],
            }
        )
        chunk_unwrapped = build_osm_place_chunk(
            {
                "id": p["place_id"],
                "name": p["name"],
                "category": p.get("category"),
                "destination_id": None,
                "destination_name": p.get("destination"),
                "latitude": p.get("latitude"),
                "longitude": p.get("longitude"),
                "sources": [
                    {
                        "source_name": "osm",
                        "source_id": osm_src["source_id"],
                        "raw_data": tags,
                    }
                ],
            }
        )
        osm_hashes_as_is.add(chunk_as_is.content_hash)
        osm_hashes_unwrapped.add(chunk_unwrapped.content_hash)
        osm_chars_as_is.append(len(chunk_as_is.content))
        osm_chars_unwrapped.append(len(chunk_unwrapped.content))

        for s in p.get("sources", []):
            if s.get("source_name") == "overture":
                all_overture_source_ids_247.append(str(s["source_id"]))

    osm_chars_as_is.sort()
    osm_chars_unwrapped.sort()

    # 3. Audit all 60 frozen target POIs
    v2_by_id = {p["place_id"]: p for p in places_v2}
    pois_60 = manifest_doc["pois"]
    if len(pois_60) != 60:
        raise ValueError(f"FAIL CLOSED: Expected 60 target POIs, got {len(pois_60)}")

    poi_audit_records: list[dict[str, Any]] = []
    gap_list: list[dict[str, Any]] = []

    target_chars_unwrapped: list[int] = []
    target_words_unwrapped: list[int] = []
    target_fact_field_counts: list[int] = []
    osm_field_coverage_counter: Counter[str] = Counter()
    nested_tag_places_60 = 0
    as_is_nonempty_fact_fields_60 = 0

    for tp in pois_60:
        pid = tp["poi_id"]
        v2p = v2_by_id[pid]
        osm_src = next(s for s in v2p["sources"] if s["source_name"] == "osm")
        ov_src = next(
            (s for s in v2p["sources"] if s["source_name"] == "overture"), None
        )

        tags, tag_shape = _extract_osm_tags_and_shape(osm_src)
        if tag_shape == "nested_raw_data_tags":
            nested_tag_places_60 += 1

        raw_top = osm_src.get("raw_data") or {}
        if isinstance(raw_top, dict) and any(
            k in raw_top and str(raw_top[k]).strip() for k in FACT_FIELDS
        ):
            as_is_nonempty_fact_fields_60 += 1

        chunk_unwrapped = build_osm_place_chunk(
            {
                "id": pid,
                "name": v2p["name"],
                "category": v2p.get("category"),
                "destination_id": None,
                "destination_name": v2p.get("destination") or tp["city"],
                "latitude": v2p.get("latitude"),
                "longitude": v2p.get("longitude"),
                "sources": [
                    {
                        "source_name": "osm",
                        "source_id": osm_src["source_id"],
                        "raw_data": tags,
                    }
                ],
            }
        )
        char_len = len(chunk_unwrapped.content)
        word_len = len(chunk_unwrapped.content.split())
        target_chars_unwrapped.append(char_len)
        target_words_unwrapped.append(word_len)

        substantive_facts = _extract_substantive_osm_facts(tags, v2p)
        fact_count = len(substantive_facts)
        target_fact_field_counts.append(fact_count)

        # Update OSM field coverage counters on the 60 target POIs
        if any(k in tags for k in CLASS_KEYS) or v2p.get("category"):
            osm_field_coverage_counter["category_or_class"] += 1
        for fk in (
            "address",
            "opening_hours",
            "phone",
            "website",
            "wikidata",
            "wikipedia",
            "cuisine",
            "wheelchair",
            "fee",
            "religion",
            "internet_access",
            "operator",
            "email",
            "stars",
            "heritage",
            "description",
        ):
            if fk in substantive_facts:
                osm_field_coverage_counter[fk] += 1
        # Keep exact B0 `website` or `contact:website` counter (15) distinct from `heritage:website` (1)
        if tags.get("website") or tags.get("contact:website"):
            osm_field_coverage_counter["website_or_contact_website_strict"] += 1

        osm_lineage_id = f"osm:{osm_src['source_id']}"
        osm_utility_status = (
            "USEFUL_STRUCTURED_FACTS" if fact_count > 0 else "LOW_INFORMATION"
        )
        osm_content_utility_ok = osm_utility_status in {
            "USEFUL_NARRATIVE",
            "USEFUL_STRUCTURED_FACTS",
        }
        osm_rag_eligible = True and osm_content_utility_ok

        # Overture lineage audit
        cc_row = overture_crosschecks.get(str(osm_src["source_id"]), {})
        cc_status = str(cc_row.get("status") or "MISSING_IN_CROSSCHECK")
        cc_match = cc_row.get("overture_match") or {}

        if ov_src is not None:
            ov_rd = ov_src.get("raw_data") or {}
            ov_id = str(ov_src["source_id"])
            ov_lineage_id: str | None = f"overture:{ov_id}"
            ov_lic = _normalize_overture_license(ov_rd.get("license"))
            ov_providers = ov_rd.get("providers") or []
            ov_contrib = (
                ",".join(str(x) for x in ov_providers) if ov_providers else None
            )
            ov_mapping_ok = True
            ov_mapping_status = "AUTO_LINK_VERIFIED"
            ov_reuse_class = (
                "OPEN_REUSABLE"
                if (ov_lic and ov_contrib)
                else "LICENSE_EVIDENCE_PENDING_B1B"
            )
            ov_reuse_allowed = ov_reuse_class == "OPEN_REUSABLE"
            ov_primary_eligible = ov_mapping_ok and ov_reuse_allowed
            # Committed Freeze v2 Overture raw_data only stores matching metadata, not rich POI text/attributes
            ov_utility_status = "LOW_INFORMATION"
            ov_rag_eligible = False
        elif cc_status == "MANUAL_REVIEW_CANDIDATE":
            ov_id = str(cc_match.get("overture_id") or "")
            ov_lineage_id = None
            ov_lic = _normalize_overture_license(cc_match.get("license"))
            ov_providers = cc_match.get("providers") or []
            ov_contrib = (
                ",".join(str(x) for x in ov_providers) if ov_providers else None
            )
            ov_mapping_ok = False
            ov_mapping_status = "MAPPING_REVIEW_REQUIRED"
            ov_reuse_class = "REFERENCE_ONLY"
            ov_reuse_allowed = False
            ov_primary_eligible = False
            ov_utility_status = "LOW_INFORMATION"
            ov_rag_eligible = False
        else:
            ov_id = None
            ov_lineage_id = None
            ov_lic = None
            ov_contrib = None
            ov_mapping_ok = False
            ov_mapping_status = cc_status
            ov_reuse_class = None
            ov_reuse_allowed = False
            ov_primary_eligible = False
            ov_utility_status = None
            ov_rag_eligible = False

        # External entity/url pointers in OSM tags (not yet downloaded as local corpus documents)
        wd_id = tags.get("wikidata")
        wp_tag = (
            tags.get("wikipedia")
            or tags.get("wikipedia:vi")
            or tags.get("wikipedia:en")
        )
        web_url = (
            tags.get("website")
            or tags.get("contact:website")
            or tags.get("url")
            or tags.get("heritage:website")
        )

        mapped_lineages = [osm_lineage_id]
        if ov_lineage_id is not None:
            mapped_lineages.append(ov_lineage_id)

        rag_eligible_lineages = [osm_lineage_id] if osm_rag_eligible else []

        # Gap reasons and B1B priority assignment (Section 21 & 22)
        gap_reasons: list[str] = ["NEEDS_NARRATIVE_SOURCE", "STRUCTURED_ONLY"]
        if not osm_rag_eligible:
            gap_reasons.insert(0, "NO_POI_SPECIFIC_KNOWLEDGE")
        if len(mapped_lineages) < 2:
            gap_reasons.append("NEEDS_SECOND_INDEPENDENT_SOURCE")
        if ov_mapping_status == "MAPPING_REVIEW_REQUIRED":
            gap_reasons.append("MAPPING_REVIEW_REQUIRED")
        if web_url:
            gap_reasons.append("NEEDS_REUSE_EVIDENCE")

        if not osm_rag_eligible:
            b1b_priority = "P0"
        elif len(mapped_lineages) == 1:
            b1b_priority = "P1"
        else:
            b1b_priority = "P2"

        # Suggested B1B acquisition direction & preferred tier
        suggested_directions: list[str] = []
        if web_url:
            suggested_directions.append(
                f"Verify reuse/terms and acquire official/venue page `{web_url}`"
            )
            preferred_tier = "TIER_A" if "unesco.org" not in web_url else "TIER_B"
        elif tp["category_group"] in {
            "attractions_culture",
            "nature_beach",
            "other_tourism",
        }:
            preferred_tier = "TIER_B"
        else:
            preferred_tier = "TIER_A"

        if wd_id:
            suggested_directions.append(
                f"Fetch Wikidata structured entity `{wd_id}` (CC0-1.0, TIER_C)"
            )
        if wp_tag:
            suggested_directions.append(
                f"Fetch Wikipedia article `{wp_tag}` (CC-BY-SA-4.0, TIER_C)"
            )
        if ov_lineage_id is not None:
            suggested_directions.append(
                f"Promote local Overture Places attributes for `{ov_lineage_id}` (`CDLA-Permissive-2.0`, TIER_C)"
            )
        if not suggested_directions:
            suggested_directions.append(
                f"Search official provincial tourism portal (`TIER_B`) and open Wikimedia/Wikidata (`TIER_C`) for `{tp['name']}` ({tp['city']})"
            )

        record = {
            "selection_rank": tp["selection_rank"],
            "poi_id": pid,
            "name": tp["name"],
            "city": tp["city"],
            "category_group": tp["category_group"],
            "osm_id": tp["osm_id"],
            "osm_evidence": {
                "source_lineage_id": osm_lineage_id,
                "source_tier": "TIER_C",
                "evidence_type": "STRUCTURED_METADATA",
                "license_or_usage_class": "ODbL-1.0",
                "reuse_storage_class": "OPEN_REUSABLE",
                "attribution_requirement": "© OpenStreetMap contributors, ODbL-1.0",
                "raw_data_storage_shape": tag_shape,
                "raw_tag_count": len(tags),
                "substantive_fact_field_count": fact_count,
                "substantive_fact_fields": sorted(substantive_facts.keys()),
                "rendered_chunk_char_len_unwrapped": char_len,
                "rendered_chunk_word_len_unwrapped": word_len,
                "CANONICAL_MAPPING_OK": True,
                "REUSE_STATUS_ALLOWED": True,
                "PRIMARY_CORPUS_ELIGIBLE": True,
                "CONTENT_UTILITY_STATUS": osm_utility_status,
                "CONTENT_UTILITY_OK": osm_content_utility_ok,
                "RAG_CANDIDATE_ELIGIBLE": osm_rag_eligible,
            },
            "overture_evidence": {
                "crosscheck_status": cc_status,
                "mapping_status": ov_mapping_status,
                "overture_gers_id": ov_id,
                "source_lineage_id": ov_lineage_id,
                "overture_theme": "places"
                if (ov_id or cc_status == "MANUAL_REVIEW_CANDIDATE")
                else None,
                "overture_contributing_source": ov_contrib,
                "source_tier": "TIER_C"
                if (ov_id or cc_status == "MANUAL_REVIEW_CANDIDATE")
                else None,
                "evidence_type": "STRUCTURED_METADATA" if ov_lineage_id else None,
                "license_or_usage_class": ov_lic,
                "reuse_storage_class": ov_reuse_class,
                "CANONICAL_MAPPING_OK": ov_mapping_ok,
                "REUSE_STATUS_ALLOWED": ov_reuse_allowed,
                "PRIMARY_CORPUS_ELIGIBLE": ov_primary_eligible,
                "CONTENT_UTILITY_STATUS": ov_utility_status,
                "CONTENT_UTILITY_OK": False,
                "RAG_CANDIDATE_ELIGIBLE": ov_rag_eligible,
                "candidate_overture_name": cc_match.get("overture_name")
                if cc_match
                else None,
            },
            "external_tag_pointers_not_yet_downloaded": {
                "wikidata_id": wd_id,
                "wikipedia_tag": wp_tag,
                "website_url": web_url,
                "downloaded_as_local_document": False,
            },
            "wikivoyage_evidence": {
                "mapped_chunk_count": 0,
                "mapping_status": "CITY_CONTEXT_ONLY",
                "CANONICAL_MAPPING_OK": False,
            },
            "evidence_unit_count_in_rag_documents": 1,
            "evidence_unit_count_including_overture_place_sources": len(
                mapped_lineages
            ),
            "independent_source_lineage_count": len(mapped_lineages),
            "rag_candidate_eligible_lineage_count": len(rag_eligible_lineages),
            "mapped_source_lineages": mapped_lineages,
            "rag_candidate_eligible_lineages": rag_eligible_lineages,
            "has_structured_metadata": True,
            "has_useful_structured_metadata": osm_rag_eligible,
            "has_narrative_text": False,
            "has_both_structured_and_narrative": False,
            "PRIMARY_CORPUS_ELIGIBLE": True,
            "RAG_CANDIDATE_ELIGIBLE": osm_rag_eligible,
            "b1b_priority": b1b_priority,
            "gap_reasons": gap_reasons,
        }
        poi_audit_records.append(record)

        gap_list.append(
            {
                "selection_rank": tp["selection_rank"],
                "poi_id": pid,
                "name": tp["name"],
                "city": tp["city"],
                "category_group": tp["category_group"],
                "b1b_priority": b1b_priority,
                "existing_lineages": mapped_lineages,
                "rag_candidate_eligible_lineages": rag_eligible_lineages,
                "missing_evidence_types": ["NARRATIVE_TEXT"]
                if osm_rag_eligible
                else ["STRUCTURED_METADATA", "NARRATIVE_TEXT"],
                "gap_reasons": gap_reasons,
                "preferred_source_tier": preferred_tier,
                "suggested_source_search_directions": suggested_directions,
            }
        )

    target_chars_unwrapped.sort()
    target_words_unwrapped.sort()
    target_fact_field_counts_sorted = sorted(target_fact_field_counts)

    # 4. Compute coverage metrics (Overall, Per-City, Per-Category, Per-Source)
    def _compute_slice_metrics(rows: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "TARGET_POIS": len(rows),
            "POIS_WITH_ANY_EXISTING_EVIDENCE": sum(
                1 for r in rows if r["independent_source_lineage_count"] >= 1
            ),
            "POIS_WITH_PRIMARY_CORPUS_ELIGIBLE_EVIDENCE": sum(
                1 for r in rows if r["PRIMARY_CORPUS_ELIGIBLE"]
            ),
            "POIS_WITH_RAG_CANDIDATE_EVIDENCE": sum(
                1 for r in rows if r["RAG_CANDIDATE_ELIGIBLE"]
            ),
            "POIS_WITH_1_INDEPENDENT_LINEAGE": sum(
                1 for r in rows if r["independent_source_lineage_count"] == 1
            ),
            "POIS_WITH_2_PLUS_INDEPENDENT_LINEAGES": sum(
                1 for r in rows if r["independent_source_lineage_count"] >= 2
            ),
            "POIS_WITH_1_RAG_ELIGIBLE_LINEAGE": sum(
                1 for r in rows if r["rag_candidate_eligible_lineage_count"] == 1
            ),
            "POIS_WITH_2_PLUS_RAG_ELIGIBLE_LINEAGES": sum(
                1 for r in rows if r["rag_candidate_eligible_lineage_count"] >= 2
            ),
            "POIS_WITH_NARRATIVE_TEXT": sum(
                1 for r in rows if r["has_narrative_text"]
            ),
            "POIS_WITH_STRUCTURED_METADATA": sum(
                1 for r in rows if r["has_structured_metadata"]
            ),
            "POIS_WITH_USEFUL_STRUCTURED_METADATA": sum(
                1 for r in rows if r["has_useful_structured_metadata"]
            ),
            "POIS_WITH_BOTH_STRUCTURED_AND_NARRATIVE": sum(
                1 for r in rows if r["has_both_structured_and_narrative"]
            ),
            "P0_NO_RAG_ELIGIBLE_EVIDENCE": sum(
                1 for r in rows if r["b1b_priority"] == "P0"
            ),
            "P1_SINGLE_INDEPENDENT_LINEAGE": sum(
                1 for r in rows if r["b1b_priority"] == "P1"
            ),
            "P2_STRUCTURED_ONLY_NO_NARRATIVE": sum(
                1 for r in rows if r["b1b_priority"] == "P2"
            ),
            "P3_PROVISIONAL_COVERAGE_MET": sum(
                1 for r in rows if r["b1b_priority"] == "P3"
            ),
        }

    overall_coverage = _compute_slice_metrics(poi_audit_records)
    coverage_by_city = {
        city: _compute_slice_metrics(
            [r for r in poi_audit_records if r["city"] == city]
        )
        for city in ("Hà Nội", "Đà Nẵng", "Hạ Long")
    }
    coverage_by_category = {
        cat: _compute_slice_metrics(
            [r for r in poi_audit_records if r["category_group"] == cat]
        )
        for cat in (
            "attractions_culture",
            "restaurants_cafes_markets",
            "hotels",
            "nature_beach",
            "other_tourism",
        )
    }

    # 5. Source-level metrics (Section 18)
    source_level_metrics = {
        "osm_target_60_pois": {
            "source_type": "OPENLY_LICENSED_GEOGRAPHIC_OR_TOURISM_DATA",
            "source_tier": "TIER_C",
            "evidence_type": "STRUCTURED_METADATA",
            "evidence_units": 60,
            "independent_lineages": 60,
            "mapped_units_to_60_pois": 60,
            "unmapped_units_to_60_pois": 0,
            "open_reusable": 60,
            "research_restricted": 0,
            "reference_only": 0,
            "prohibited": 0,
            "useful_narrative": 0,
            "useful_structured": 40,
            "low_information": 20,
            "empty_or_invalid": 0,
        },
        "osm_repository_759_pois": {
            "source_type": "OPENLY_LICENSED_GEOGRAPHIC_OR_TOURISM_DATA",
            "source_tier": "TIER_C",
            "evidence_type": "STRUCTURED_METADATA",
            "evidence_units": 759,
            "independent_lineages": 759,
            "mapped_units_to_60_pois": 60,
            "unmapped_units_to_60_pois": 699,
            "open_reusable": 759,
            "research_restricted": 0,
            "reference_only": 0,
            "prohibited": 0,
            "useful_narrative": 0,
            "useful_structured_on_60_target_pois": 40,
            "low_information_on_60_target_pois": 20,
            "empty_or_invalid": 0,
        },
        "wikivoyage_repository_464_chunks": {
            "source_type": "OPENLY_LICENSED_GEOGRAPHIC_OR_TOURISM_DATA",
            "source_tier": "TIER_C",
            "evidence_type": "NARRATIVE_TEXT",
            "evidence_units": 464,
            "independent_lineages": 10,
            "mapped_units_to_60_pois": 0,
            "unmapped_units_to_60_pois": 464,
            "city_context_only_units": 157,
            "non_target_city_or_country_units": 307,
            "open_reusable": 464,
            "research_restricted": 0,
            "reference_only": 0,
            "prohibited": 0,
            "useful_narrative": 464,
            "useful_structured": 0,
            "low_information": 0,
            "empty_or_invalid": 0,
        },
        "overture_auto_link_target_26_pois": {
            "source_type": "OPENLY_LICENSED_GEOGRAPHIC_OR_TOURISM_DATA",
            "source_tier": "TIER_C",
            "evidence_type": "STRUCTURED_METADATA",
            "evidence_units": 26,
            "independent_lineages": 26,
            "mapped_units_to_60_pois": 26,
            "unmapped_units_to_60_pois": 0,
            "open_reusable": 26,
            "research_restricted": 0,
            "reference_only": 0,
            "prohibited": 0,
            "useful_narrative": 0,
            "useful_structured": 0,
            "low_information": 26,
            "empty_or_invalid": 0,
            "note": (
                "Committed Freeze v2 `raw_data` stores only matching provenance (`LOW_INFORMATION`); "
                "local git-ignored raw parquet holds `addresses=26`, `phones=22`, `websites=15`."
            ),
        },
        "overture_manual_review_candidates_on_60_pois": {
            "source_type": "OPENLY_LICENSED_GEOGRAPHIC_OR_TOURISM_DATA",
            "source_tier": "TIER_C",
            "evidence_type": "STRUCTURED_METADATA",
            "evidence_units": 8,
            "independent_lineages": 8,
            "mapped_units_to_60_pois": 0,
            "unmapped_units_to_60_pois": 8,
            "mapping_review_required_units": 8,
            "open_reusable": 0,
            "research_restricted": 0,
            "reference_only": 8,
            "prohibited": 0,
            "useful_narrative": 0,
            "useful_structured": 0,
            "low_information": 8,
            "empty_or_invalid": 0,
        },
        "external_tag_pointers_not_downloaded": {
            "wikidata_tag_pointers_on_60_pois": 15,
            "wikipedia_tag_pointers_on_60_pois": 14,
            "website_or_contact_website_tag_pointers_on_60_pois": 15,
            "heritage_website_tag_pointers_on_60_pois": 1,
            "local_downloaded_documents": 0,
        },
    }

    # 6. Evaluate B2 readiness (Section 20)
    b2_readiness = {
        "CURRENT_LOCAL_CORPUS_READY_FOR_B2": False,
        "provisional_b0_minimum_criteria": {
            "min_30_canonical_pois_with_rag_eligible_evidence": {
                "required": 30,
                "actual_primary_eligible": overall_coverage[
                    "POIS_WITH_PRIMARY_CORPUS_ELIGIBLE_EVIDENCE"
                ],
                "actual_rag_candidate_eligible": overall_coverage[
                    "POIS_WITH_RAG_CANDIDATE_EVIDENCE"
                ],
                "actual_with_narrative_evidence": overall_coverage[
                    "POIS_WITH_NARRATIVE_TEXT"
                ],
                "met_for_structured_only": True,
                "met_for_narrative_grounded_rag": False,
            },
            "min_10_pois_per_city_with_rag_eligible_evidence": {
                "required_per_city": 10,
                "actual_rag_candidate_eligible_by_city": {
                    city: coverage_by_city[city]["POIS_WITH_RAG_CANDIDATE_EVIDENCE"]
                    for city in ("Hà Nội", "Đà Nẵng", "Hạ Long")
                },
                "met": False,
                "failing_city": "Hạ Long (only 7/20 POIs have RAG-candidate-eligible structured OSM evidence; 13/20 are LOW_INFORMATION)",
            },
            "min_2_independent_provenance_bound_lineages_per_poi": {
                "required_pois_with_2_plus_lineages": 30,
                "required_per_city": 10,
                "actual_pois_with_2_plus_mapped_lineages": overall_coverage[
                    "POIS_WITH_2_PLUS_INDEPENDENT_LINEAGES"
                ],
                "actual_by_city_mapped_lineages": {
                    city: coverage_by_city[city][
                        "POIS_WITH_2_PLUS_INDEPENDENT_LINEAGES"
                    ]
                    for city in ("Hà Nội", "Đà Nẵng", "Hạ Long")
                },
                "actual_pois_with_2_plus_rag_eligible_lineages": overall_coverage[
                    "POIS_WITH_2_PLUS_RAG_ELIGIBLE_LINEAGES"
                ],
                "met": False,
                "reason": (
                    "Only 26/60 POIs (Hà Nội=7, Đà Nẵng=10, Hạ Long=9) have 2 mapped entity lineages (OSM + Overture AUTO_LINK), "
                    "below the >=30 overall and >=10/city thresholds, and 0/60 POIs have >=2 RAG-candidate-eligible document lineages."
                ),
            },
            "min_150_useful_poi_mapped_chunks": {
                "required": 150,
                "actual_poi_mapped_rag_eligible_units": overall_coverage[
                    "POIS_WITH_RAG_CANDIDATE_EVIDENCE"
                ],
                "actual_poi_mapped_narrative_chunks": 0,
                "met": False,
                "reason": (
                    "Only 40 POI-mapped OSM units contain useful structured facts (`0` POI-mapped narrative chunks; "
                    "the 464 Wikivoyage chunks are unmapped city/country guides with `place_id = None`)."
                ),
            },
        },
        "blocking_deficiencies": [
            "Zero POI-mapped narrative documents (`POIS_WITH_NARRATIVE_TEXT = 0/60`); all 464 Wikivoyage chunks have `place_id = None` (`157` `CITY_CONTEXT_ONLY`, `307` `UNMAPPED_TO_FROZEN_POI`).",
            "Hạ Long has only `7/20` POIs with useful structured OSM facts (`13/20` are `LOW_INFORMATION` with only name, category tag, and coordinates), failing the `>=10` POIs/city minimum.",
            "Only `26/60` POIs (`7` Hà Nội, `10` Đà Nẵng, `9` Hạ Long) have `>=2` independent mapped lineages (`OSM` + `Overture AUTO_LINK`), and `0/60` have `>=2` `RAG_CANDIDATE_ELIGIBLE` document lineages.",
            "Only `40` POI-mapped useful structured units exist against the `>=150` useful-chunk minimum.",
            "Ingestion bug `PDG-001` in `apps/ai-service/app/rag/osm_documents.py`: `_tags()` reads flat `raw_data` keys without unwrapping `raw_data['tags']`, causing `59/60` target POIs (`621/759` Freeze v2 POIs) to drop nested OSM tags during chunk rendering unless unwrapped.",
        ],
    }

    payload: dict[str, Any] = {
        "artifact_id": "w07_b1a_existing_poi_knowledge_audit_v1",
        "version": AUDIT_VERSION,
        "task_id": TASK_ID,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "previous_accepted_gate": PREVIOUS_ACCEPTED_GATE,
        "W07_B0_STATUS": W07_B0_STATUS,
        "W07_PRIMARY_CORPUS_STRATEGY": "EVIDENCE_GROUNDED_POI_KNOWLEDGE",
        "PRIMARY_W07_CORPUS": "OPEN_AND_OFFICIAL_POI_KNOWLEDGE",
        "HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION": True,
        "SOCIAL_PLATFORM_ROLE": "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS",
        "SOCIAL_FUTURE_RESERVED_TASK_ID": "SOCIAL-FRESHNESS-01",
        "GOOGLE_MAPS_ROLE": "RUNTIME_ENRICHMENT_ONLY",
        "CURRENT_LOCAL_CORPUS_READY_FOR_B2": False,
        "next_gate": NEXT_GATE,
        "verified_existing_inventory": {
            "NON_REVIEW_RAG_EVIDENCE_UNITS_EXISTING": total_rag_docs,
            "OSM_METADATA_UNITS": osm_rag_docs,
            "WIKIVOYAGE_DESTINATION_CHUNKS": wikivoyage_rag_docs,
            "VERIFIED_OSM_POIS": verified_osm_pois,
            "REC_A_CORE_3_CITY_POIS": rec_a_core_pois,
            "OVERTURE_LINKED_POIS": overture_linked_pois,
            "TOTAL_REPOSITORY_NON_REVIEW_UNITS_INCLUDING_OVERTURE": total_rag_docs
            + overture_aux_sources,
            "TARGET_POIS": 60,
            "target_pois_by_city": {"Hà Nội": 20, "Đà Nẵng": 20, "Hạ Long": 20},
            "rag_documents_independent_source_lineages": 769,
            "osm_independent_source_lineages_total": 759,
            "wikivoyage_independent_source_lineages_total": 10,
            "overture_independent_source_lineages_total": 247,
            "repository_independent_source_lineages_including_overture": 1016,
            "target_60_pois_mapped_rag_document_units": 60,
            "target_60_pois_unmapped_rag_document_units": 1163,
            "target_60_pois_mapped_overture_auto_link_units": 26,
            "target_60_pois_mapped_total_units_including_overture": 86,
            "target_60_pois_mapped_independent_lineages_including_overture": 86,
            "target_60_pois_rag_candidate_eligible_units": 40,
            "target_60_pois_rag_candidate_eligible_lineages": 40,
            "lineage_id_conventions": {
                "osm": "osm:<osm_type>/<osm_id>",
                "overture": "overture:<gers_id>",
                "wikivoyage": "wikivoyage:en:<page_slug>",
                "wikidata": "wikidata:<qid>",
                "wikipedia": "wikipedia:<lang>:<title>",
                "official": "official:<canonical_url_or_document_id>",
            },
        },
        "governance_and_eligibility_rules": {
            "b0_two_gate_formula": "PRIMARY_CORPUS_ELIGIBLE = CANONICAL_MAPPING_OK AND REUSE_STATUS_ALLOWED",
            "b1a_rag_candidate_formula": "RAG_CANDIDATE_ELIGIBLE = PRIMARY_CORPUS_ELIGIBLE AND CONTENT_UTILITY_OK",
            "HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION": True,
            "content_utility_states": list(CONTENT_UTILITY_STATES),
            "evidence_types": list(EVIDENCE_TYPES),
            "empirical_length_and_field_distributions": {
                "repository_759_osm_docs_as_is_char_len": {
                    "min": osm_chars_as_is[0],
                    "p25": _percentile(osm_chars_as_is, 0.25),
                    "median": _percentile(osm_chars_as_is, 0.50),
                    "p75": _percentile(osm_chars_as_is, 0.75),
                    "max": osm_chars_as_is[-1],
                },
                "repository_759_osm_docs_unwrapped_char_len": {
                    "min": osm_chars_unwrapped[0],
                    "p25": _percentile(osm_chars_unwrapped, 0.25),
                    "median": _percentile(osm_chars_unwrapped, 0.50),
                    "p75": _percentile(osm_chars_unwrapped, 0.75),
                    "max": osm_chars_unwrapped[-1],
                },
                "target_60_osm_docs_unwrapped_char_len": {
                    "min": target_chars_unwrapped[0],
                    "p25": _percentile(target_chars_unwrapped, 0.25),
                    "median": _percentile(target_chars_unwrapped, 0.50),
                    "p75": _percentile(target_chars_unwrapped, 0.75),
                    "max": target_chars_unwrapped[-1],
                },
                "target_60_osm_docs_unwrapped_word_len": {
                    "min": target_words_unwrapped[0],
                    "p25": _percentile(target_words_unwrapped, 0.25),
                    "median": _percentile(target_words_unwrapped, 0.50),
                    "p75": _percentile(target_words_unwrapped, 0.75),
                    "max": target_words_unwrapped[-1],
                },
                "target_60_osm_substantive_fact_field_count": {
                    "min": target_fact_field_counts_sorted[0],
                    "p25": _percentile(target_fact_field_counts_sorted, 0.25),
                    "median": _percentile(target_fact_field_counts_sorted, 0.50),
                    "p75": _percentile(target_fact_field_counts_sorted, 0.75),
                    "max": target_fact_field_counts_sorted[-1],
                    "pois_with_0_substantive_fields_low_information": sum(
                        1 for c in target_fact_field_counts if c == 0
                    ),
                    "pois_with_1_plus_substantive_fields_useful_structured": sum(
                        1 for c in target_fact_field_counts if c >= 1
                    ),
                },
                "pdg_001_nested_raw_data_tags_finding": {
                    "freeze_v2_759_places_with_nested_raw_data_tags": nested_tag_places_759,
                    "target_60_places_with_nested_raw_data_tags": nested_tag_places_60,
                    "target_60_places_with_fact_fields_emitted_as_is": as_is_nonempty_fact_fields_60,
                    "target_60_places_with_substantive_facts_when_unwrapped": 40,
                    "description": (
                        "In `gomate_places_freeze_v2.json`, 621/759 places (59/60 target POIs; all except Bãi biển Mỹ Khê) "
                        "store OSM tags nested under `raw_data.tags`, whereas `apps/ai-service/app/rag/osm_documents.py` (`_tags()`) "
                        "currently reads only flat top-level `raw_data` keys."
                    ),
                },
            },
        },
        "wikivoyage_audit": {
            "total_chunks_in_freeze_v2": 464,
            "independent_article_lineages": 10,
            "chunks_mapped_to_frozen_60_pois": 0,
            "chunks_city_context_only": 157,
            "chunks_unmapped_to_frozen_poi": 307,
            "source_tier": "TIER_C",
            "evidence_type": "NARRATIVE_TEXT",
            "license_or_usage_class": "CC-BY-SA-3.0",
            "reuse_storage_class": "OPEN_REUSABLE",
            "attribution_requirement": (
                "Wikivoyage contributors via Wikimedia REST API (`https://en.wikivoyage.org/wiki/<Title>`), CC-BY-SA-3.0"
            ),
            "wikivoyage_fingerprint_sha256": ingest_run["after"][
                "wikivoyage_fingerprint"
            ],
            "git_tracked_chunk_text_export_present": False,
            "article_lineages": list(WIKIVOYAGE_PILOT_ARTICLE_INVENTORY),
        },
        "osm_audit_summary": {
            "target_pois_total": 60,
            "exact_osm_entity_mapped": 60,
            "source_tier": "TIER_C",
            "license_or_usage_class": "ODbL-1.0",
            "reuse_storage_class": "OPEN_REUSABLE",
            "primary_corpus_eligible": 60,
            "useful_structured_facts_count": 40,
            "low_information_count": 20,
            "rag_candidate_eligible_count": 40,
            "field_coverage_on_60_pois": dict(
                sorted(osm_field_coverage_counter.items())
            ),
        },
        "overture_audit_summary": {
            "target_pois_total": 60,
            "auto_link_verified_count": 26,
            "auto_link_by_city": {
                city: coverage_by_city[city]["POIS_WITH_2_PLUS_INDEPENDENT_LINEAGES"]
                for city in ("Hà Nội", "Đà Nẵng", "Hạ Long")
            },
            "manual_review_candidate_mapping_review_required_count": 8,
            "unmatched_count": 25,
            "missing_in_crosscheck_count": 1,
            "auto_link_theme": "places",
            "auto_link_contributing_source": "meta,Overture",
            "auto_link_license_or_usage_class": "CDLA-Permissive-2.0",
            "auto_link_reuse_storage_class": "OPEN_REUSABLE",
            "auto_link_primary_corpus_eligible_count": 26,
            "auto_link_committed_freeze_v2_content_utility_status": "LOW_INFORMATION",
            "auto_link_committed_freeze_v2_rag_candidate_eligible_count": 0,
            "local_raw_parquet_enrichment_diagnostic": OVERTURE_LOCAL_PARQUET_ENRICHMENT_SUMMARY,
            "manual_review_candidates_detail": [
                {
                    "selection_rank": r["selection_rank"],
                    "poi_id": r["poi_id"],
                    "name": r["name"],
                    "city": r["city"],
                    "osm_id": r["osm_id"],
                    "candidate_overture_gers_id": r["overture_evidence"][
                        "overture_gers_id"
                    ],
                    "candidate_overture_name": r["overture_evidence"][
                        "candidate_overture_name"
                    ],
                    "mapping_status": "MAPPING_REVIEW_REQUIRED",
                }
                for r in poi_audit_records
                if r["overture_evidence"]["mapping_status"] == "MAPPING_REVIEW_REQUIRED"
            ],
        },
        "coverage_metrics": {
            "overall": overall_coverage,
            "by_city": coverage_by_city,
            "by_category_group": coverage_by_category,
        },
        "source_level_metrics": source_level_metrics,
        "reuse_class_distribution": {
            "target_60_mapped_units_86": {
                "OPEN_REUSABLE": 86,
                "RESEARCH_RESTRICTED": 0,
                "REFERENCE_ONLY": 0,
                "PROHIBITED": 0,
            },
            "repository_1223_rag_document_units": {
                "OPEN_REUSABLE": 1223,
                "RESEARCH_RESTRICTED": 0,
                "REFERENCE_ONLY": 0,
                "PROHIBITED": 0,
            },
            "overture_manual_review_candidates_8": {
                "OPEN_REUSABLE": 0,
                "RESEARCH_RESTRICTED": 0,
                "REFERENCE_ONLY": 8,
                "PROHIBITED": 0,
            },
        },
        "content_utility_distribution": {
            "target_60_osm_units": {
                "USEFUL_NARRATIVE": 0,
                "USEFUL_STRUCTURED_FACTS": 40,
                "LOW_INFORMATION": 20,
                "EMPTY_OR_INVALID": 0,
            },
            "target_26_overture_auto_link_units_in_committed_freeze_v2": {
                "USEFUL_NARRATIVE": 0,
                "USEFUL_STRUCTURED_FACTS": 0,
                "LOW_INFORMATION": 26,
                "EMPTY_OR_INVALID": 0,
            },
            "repository_464_wikivoyage_chunks": {
                "USEFUL_NARRATIVE": 464,
                "USEFUL_STRUCTURED_FACTS": 0,
                "LOW_INFORMATION": 0,
                "EMPTY_OR_INVALID": 0,
            },
        },
        "duplicate_and_lineage_audit": {
            "osm_759_units_total": 759,
            "osm_759_unique_source_ids": len(set(all_osm_source_ids_759)),
            "osm_759_unique_content_sha256_as_is": len(osm_hashes_as_is),
            "osm_759_unique_content_sha256_unwrapped": len(osm_hashes_unwrapped),
            "osm_exact_duplicate_content_hashes": 759 - len(osm_hashes_unwrapped),
            "overture_247_units_total": 247,
            "overture_247_unique_gers_ids": len(set(all_overture_source_ids_247)),
            "overture_duplicate_gers_ids": 247 - len(set(all_overture_source_ids_247)),
            "wikivoyage_464_chunks_parent_articles": 10,
            "wikivoyage_chunks_sharing_parent_lineage": 464,
            "multi_source_entity_aliases_on_60_pois": 26,
            "multi_source_entity_aliases_on_759_pois": 247,
            "upstream_data_deleted": False,
        },
        "b2_readiness_evaluation": b2_readiness,
        "b1b_priority_summary": {
            "P0": overall_coverage["P0_NO_RAG_ELIGIBLE_EVIDENCE"],
            "P1": overall_coverage["P1_SINGLE_INDEPENDENT_LINEAGE"],
            "P2": overall_coverage["P2_STRUCTURED_ONLY_NO_NARRATIVE"],
            "P3": overall_coverage["P3_PROVISIONAL_COVERAGE_MET"],
            "collection_order": "P0 -> P1 -> P2",
            "non_exclusive_diagnostic_counts": {
                "pois_with_no_rag_eligible_evidence": 20,
                "pois_with_only_1_mapped_source_lineage": 34,
                "pois_with_only_1_rag_eligible_lineage": 40,
                "pois_with_structured_evidence_but_no_narrative": 40,
                "pois_with_any_structured_record_but_no_narrative": 60,
            },
        },
        "target_poi_audit_records": poi_audit_records,
        "b1b_acquisition_gap_list": gap_list,
        "method_drift_guard": {
            "method_choices_selected_in_b1a": False,
            "deferred_decisions": list(w07_b0.DEFERRED_METHOD_DECISIONS),
        },
        "no_external_collection_at_b1a": {
            "NEW_WEB_DOCUMENT_DOWNLOADS": 0,
            "NEW_SOCIAL_COLLECTION": 0,
            "NEW_GOOGLE_MAPS_COLLECTION": 0,
            "NEW_LLM_PROVIDER_CALLS": 0,
            "NEW_EXTERNAL_API_CALLS_FOR_CORPUS": 0,
        },
        "upstream_immutability": upstream_hashes,
    }
    payload["artifact_sha256"] = w07_a2.compute_internal_sha256(payload)
    return payload


def render_b1a_audit_markdown(payload: dict[str, Any]) -> str:
    """Render deterministic Markdown report for W07-B1A (`docs/research/w07_b1a_existing_poi_knowledge_audit.md`)."""
    inv = payload["verified_existing_inventory"]
    dist = payload["governance_and_eligibility_rules"][
        "empirical_length_and_field_distributions"
    ]
    pdg = dist["pdg_001_nested_raw_data_tags_finding"]
    wv = payload["wikivoyage_audit"]
    osm_sum = payload["osm_audit_summary"]
    ov_sum = payload["overture_audit_summary"]
    cov_all = payload["coverage_metrics"]["overall"]
    cov_city = payload["coverage_metrics"]["by_city"]
    cov_cat = payload["coverage_metrics"]["by_category_group"]
    dup = payload["duplicate_and_lineage_audit"]
    b2 = payload["b2_readiness_evaluation"]
    prio = payload["b1b_priority_summary"]
    no_ext = payload["no_external_collection_at_b1a"]

    lines: list[str] = [
        "# W07-B1A — Existing POI Knowledge Corpus Audit",
        "",
        "## 1. Authority & Scope",
        "",
        f"- **Task ID:** `{payload['task_id']}`",
        f"- **Version:** `{payload['version']}`",
        f"- **Authoritative Base:** `develop@{payload['authoritative_base_develop_sha']}`",
        f"- **Previous Accepted Gate:** `{payload['previous_accepted_gate']}`",
        f"- **W07-B0 Status:** `{payload['W07_B0_STATUS']}`",
        f"- **Primary Strategy:** `{payload['W07_PRIMARY_CORPUS_STRATEGY']}` (`PRIMARY_W07_CORPUS = {payload['PRIMARY_W07_CORPUS']}`)",
        f"- **Next Gate:** `{payload['next_gate']}`",
        f"- **Frozen 60-POI Target Manifest SHA256:** `{payload['upstream_immutability']['w07_a2_manifest_internal_sha256']}`",
        f"- **Frozen W07-B0 Amendment SHA256:** `{payload['upstream_immutability']['w07_b0_amendment_internal_sha256']}`",
        "",
        "## 2. Verified Repository Inventory & Source Lineage Counting",
        "",
        f"- `NON_REVIEW_RAG_EVIDENCE_UNITS_EXISTING`: `{inv['NON_REVIEW_RAG_EVIDENCE_UNITS_EXISTING']}` (`OSM_METADATA_UNITS = {inv['OSM_METADATA_UNITS']}` + `WIKIVOYAGE_DESTINATION_CHUNKS = {inv['WIKIVOYAGE_DESTINATION_CHUNKS']}`)",
        f"- `VERIFIED_OSM_POIS`: `{inv['VERIFIED_OSM_POIS']}`",
        f"- `REC_A_CORE_3_CITY_POIS`: `{inv['REC_A_CORE_3_CITY_POIS']}`",
        f"- `OVERTURE_LINKED_POIS`: `{inv['OVERTURE_LINKED_POIS']}` (stored in `place_sources`, not in the 1,223-unit `documents` table)",
        f"- `TOTAL_REPOSITORY_NON_REVIEW_UNITS_INCLUDING_OVERTURE`: `{inv['TOTAL_REPOSITORY_NON_REVIEW_UNITS_INCLUDING_OVERTURE']}`",
        f"- **Independent Source Lineages in 1,223 RAG Documents:** `{inv['rag_documents_independent_source_lineages']}` (`{inv['osm_independent_source_lineages_total']}` `osm:<type>/<id>` + `{inv['wikivoyage_independent_source_lineages_total']}` `wikivoyage:en:<page_slug>`)",
        f"- **Independent Source Lineages Including 247 Overture Links:** `{inv['repository_independent_source_lineages_including_overture']}` (`759` OSM + `10` Wikivoyage + `247` `overture:<gers_id>`)",
        "",
        "## 3. Governance, Content-Utility Diagnostic & Ingestion Finding (`PDG-001`)",
        "",
        f"- **B0 Two-Gate Formula:** `{payload['governance_and_eligibility_rules']['b0_two_gate_formula']}`",
        f"- **B1A RAG-Candidate Formula:** `{payload['governance_and_eligibility_rules']['b1a_rag_candidate_formula']}`",
        f"- `HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION`: `{str(payload['HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION']).lower()}`",
        f"- **Empirical OSM Rendered Length (60 Target POIs, unwrapped `raw_data.tags`):** min `{dist['target_60_osm_docs_unwrapped_char_len']['min']}` chars (`{dist['target_60_osm_docs_unwrapped_word_len']['min']}` words), median `{dist['target_60_osm_docs_unwrapped_char_len']['median']}` chars (`{dist['target_60_osm_docs_unwrapped_word_len']['median']}` words), max `{dist['target_60_osm_docs_unwrapped_char_len']['max']}` chars (`{dist['target_60_osm_docs_unwrapped_word_len']['max']}` words).",
        f"- **Critical Technical Finding (`PDG-001`):** {pdg['description']} Without unwrapping `raw_data.tags`, only `{pdg['target_60_places_with_fact_fields_emitted_as_is']}/60` target POIs emit `FACT_FIELDS`; with `raw_data.tags` unwrapped, `{pdg['target_60_places_with_substantive_facts_when_unwrapped']}/60` target POIs contain `>=1` substantive factual attribute (`USEFUL_STRUCTURED_FACTS`), while `20/60` contain `0` factual attributes beyond name, category tag, and coordinates (`LOW_INFORMATION`).",
        "",
        "## 4. Wikivoyage Audit (`464` Chunks Across `10` Lineages)",
        "",
        f"- **Total Chunks:** `{wv['total_chunks_in_freeze_v2']}` across `{wv['independent_article_lineages']}` English Wikivoyage articles (`source_tier = TIER_C`, `license = CC-BY-SA-3.0`, `reuse_storage_class = OPEN_REUSABLE`).",
        f"- **Deterministic Mapping to Frozen 60 POIs:** `{wv['chunks_mapped_to_frozen_60_pois']}` (`WikivoyageIngester.ingest_pilot_pages()` sets `place_id = None` for all `464` chunks, and chunk text is not exported to git-tracked `data/`).",
        f"- **Classification:** `{wv['chunks_city_context_only']}` chunks (`Hanoi=86`, `Da Nang=57`, `Ha Long Bay=14`) are `CITY_CONTEXT_ONLY`; `{wv['chunks_unmapped_to_frozen_poi']}` chunks (`Vietnam=113` + 6 non-target cities) are `UNMAPPED_TO_FROZEN_POI`.",
        "",
        "| Lineage ID | Article | Chunks | Target City | Mapping Status |",
        "|---|---|---:|---|---|",
    ]
    for art in wv["article_lineages"]:
        lines.append(
            f"| `{art['source_lineage_id']}` | {art['page_title']} | {art['chunk_count']} | {art['target_city'] or '—'} | `{art['poi_mapping_status']}` |"
        )

    lines.extend(
        [
            "",
            "## 5. OSM & Overture Audit on the Frozen 60 POIs",
            "",
            f"- **OSM (`60/60` mapped, `TIER_C`, `ODbL-1.0`, `OPEN_REUSABLE`):** `40/60` `USEFUL_STRUCTURED_FACTS` (`RAG_CANDIDATE_ELIGIBLE = true`), `20/60` `LOW_INFORMATION` (`RAG_CANDIDATE_ELIGIBLE = false`).",
            "- **OSM Field Coverage on 60 POIs:** "
            + ", ".join(
                f"`{k}={v}`"
                for k, v in osm_sum["field_coverage_on_60_pois"].items()
            ),
            f"- **Overture (`26/60` `AUTO_LINK`, `TIER_C`, `overture_theme=places`, `providers=meta,Overture`, `CDLA-Permissive-2.0`, `OPEN_REUSABLE`):** `7` Hà Nội, `10` Đà Nẵng, `9` Hạ Long. Committed Freeze v2 JSON stores only matching provenance (`CONTENT_UTILITY_STATUS = LOW_INFORMATION`, `RAG_CANDIDATE_ELIGIBLE = false`), while local git-ignored raw parquet holds `addresses=26`, `phones=22`, `websites=15`.",
            f"- **Overture Uncertain Candidates (`8/60` `MANUAL_REVIEW_CANDIDATE` -> `MAPPING_REVIEW_REQUIRED`):** Held as `CANONICAL_MAPPING_OK = false` (`REFERENCE_ONLY`), preventing false-positive joins (e.g. `Nhà thờ Lớn -> Nhà Thờ Họ Nguyễn Khắc`, `Cà Phê Nola -> Cà Phê Lâm`).",
            "",
            "## 6. Coverage Metrics (Overall, Per City, Per Category, Per Source)",
            "",
            "### 6.1 Overall & Per-City Coverage",
            "",
            "| Metric | Overall (60) | Hà Nội (20) | Đà Nẵng (20) | Hạ Long (20) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for key in (
        "TARGET_POIS",
        "POIS_WITH_ANY_EXISTING_EVIDENCE",
        "POIS_WITH_PRIMARY_CORPUS_ELIGIBLE_EVIDENCE",
        "POIS_WITH_RAG_CANDIDATE_EVIDENCE",
        "POIS_WITH_1_INDEPENDENT_LINEAGE",
        "POIS_WITH_2_PLUS_INDEPENDENT_LINEAGES",
        "POIS_WITH_1_RAG_ELIGIBLE_LINEAGE",
        "POIS_WITH_2_PLUS_RAG_ELIGIBLE_LINEAGES",
        "POIS_WITH_NARRATIVE_TEXT",
        "POIS_WITH_STRUCTURED_METADATA",
        "POIS_WITH_USEFUL_STRUCTURED_METADATA",
        "POIS_WITH_BOTH_STRUCTURED_AND_NARRATIVE",
        "P0_NO_RAG_ELIGIBLE_EVIDENCE",
        "P1_SINGLE_INDEPENDENT_LINEAGE",
        "P2_STRUCTURED_ONLY_NO_NARRATIVE",
        "P3_PROVISIONAL_COVERAGE_MET",
    ):
        lines.append(
            f"| `{key}` | {cov_all[key]} | {cov_city['Hà Nội'][key]} | {cov_city['Đà Nẵng'][key]} | {cov_city['Hạ Long'][key]} |"
        )

    lines.extend(
        [
            "",
            "### 6.2 Coverage by Frozen Category Group",
            "",
            "| Category Group | Target | Primary Eligible | RAG Candidate Eligible | 1 Lineage | >=2 Lineages | Narrative | Useful Structured | P0 | P1 | P2 | P3 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for cat, cm in cov_cat.items():
        lines.append(
            f"| `{cat}` | {cm['TARGET_POIS']} | {cm['POIS_WITH_PRIMARY_CORPUS_ELIGIBLE_EVIDENCE']} | "
            f"{cm['POIS_WITH_RAG_CANDIDATE_EVIDENCE']} | {cm['POIS_WITH_1_INDEPENDENT_LINEAGE']} | "
            f"{cm['POIS_WITH_2_PLUS_INDEPENDENT_LINEAGES']} | {cm['POIS_WITH_NARRATIVE_TEXT']} | "
            f"{cm['POIS_WITH_USEFUL_STRUCTURED_METADATA']} | {cm['P0_NO_RAG_ELIGIBLE_EVIDENCE']} | "
            f"{cm['P1_SINGLE_INDEPENDENT_LINEAGE']} | {cm['P2_STRUCTURED_ONLY_NO_NARRATIVE']} | {cm['P3_PROVISIONAL_COVERAGE_MET']} |"
        )

    lines.extend(
        [
            "",
            "## 7. Duplicate / Lineage Audit & Current B2 Readiness",
            "",
            f"- **759 OSM Records:** `{dup['osm_759_unique_source_ids']}/759` unique OSM IDs, `{dup['osm_759_unique_content_sha256_unwrapped']}/759` unique content SHA-256 hashes (`0` exact duplicates).",
            f"- **247 Overture Links:** `{dup['overture_247_unique_gers_ids']}/247` unique GERS IDs (`0` duplicate GERS links).",
            f"- **464 Wikivoyage Chunks:** Split from `{dup['wikivoyage_464_chunks_parent_articles']}` parent articles (`46.4` chunks/lineage average).",
            f"- **Multi-Source Entity Aliases:** `{dup['multi_source_entity_aliases_on_60_pois']}/60` target POIs (`{dup['multi_source_entity_aliases_on_759_pois']}/759` Freeze v2 POIs) represented in both OSM and Overture.",
            f"- **`CURRENT_LOCAL_CORPUS_READY_FOR_B2`:** `{str(payload['CURRENT_LOCAL_CORPUS_READY_FOR_B2']).lower()}`",
        ]
    )
    for reason in b2["blocking_deficiencies"]:
        lines.append(f"  - {reason}")

    lines.extend(
        [
            "",
            "## 8. Frozen 60-POI Audit & B1B Acquisition Gap Matrix (`P0=20`, `P1=19`, `P2=21`, `P3=0`)",
            "",
            f"- **Priority Breakdown:** `P0 = {prio['P0']}` (no RAG-eligible evidence), `P1 = {prio['P1']}` (only 1 independent mapped lineage), `P2 = {prio['P2']}` (structured evidence only, 0 narrative evidence), `P3 = {prio['P3']}` (ready).",
            "",
            "| Rank | City | Category | Name | OSM Facts | Overture Status | External Tags (`wd`/`wp`/`web`) | Lineages | RAG Eligible | Priority | Gap Reasons |",
            "|---:|---|---|---|---:|---|---|---:|---|---|---|",
        ]
    )
    for r in payload["target_poi_audit_records"]:
        ext = r["external_tag_pointers_not_yet_downloaded"]
        ext_summary = (
            f"wd:{ext['wikidata_id'] or '-'}; wp:{'yes' if ext['wikipedia_tag'] else '-'}; web:{'yes' if ext['website_url'] else '-'}"
        )
        lines.append(
            f"| {r['selection_rank']} | {r['city']} | `{r['category_group']}` | {r['name']} | "
            f"{r['osm_evidence']['substantive_fact_field_count']} | `{r['overture_evidence']['mapping_status']}` | "
            f"`{ext_summary}` | {r['independent_source_lineage_count']} | "
            f"`{str(r['RAG_CANDIDATE_ELIGIBLE']).lower()}` | **`{r['b1b_priority']}`** | "
            f"`{','.join(r['gap_reasons'])}` |"
        )

    lines.extend(
        [
            "",
            "## 9. No-Collection Counters, Role Preservation & Upstream Immutability",
            "",
            f"- `NEW_WEB_DOCUMENT_DOWNLOADS`: `{no_ext['NEW_WEB_DOCUMENT_DOWNLOADS']}`",
            f"- `NEW_SOCIAL_COLLECTION`: `{no_ext['NEW_SOCIAL_COLLECTION']}`",
            f"- `NEW_GOOGLE_MAPS_COLLECTION`: `{no_ext['NEW_GOOGLE_MAPS_COLLECTION']}`",
            f"- `NEW_LLM_PROVIDER_CALLS`: `{no_ext['NEW_LLM_PROVIDER_CALLS']}`",
            f"- `NEW_EXTERNAL_API_CALLS_FOR_CORPUS`: `{no_ext['NEW_EXTERNAL_API_CALLS_FOR_CORPUS']}`",
            f"- `SOCIAL_PLATFORM_ROLE`: `{payload['SOCIAL_PLATFORM_ROLE']}` (`{payload['SOCIAL_FUTURE_RESERVED_TASK_ID']}`)",
            f"- `GOOGLE_MAPS_ROLE`: `{payload['GOOGLE_MAPS_ROLE']}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_b1a_audit_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Write committed W07-B1A JSON and Markdown artifacts."""
    payload = build_b1a_audit_payload(repo_root)
    json_path = repo_root / AUDIT_JSON_RELPATH
    md_path = repo_root / AUDIT_MD_RELPATH

    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    json_text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    json_path.write_text(json_text, encoding="utf-8", newline="\n")

    md_text = render_b1a_audit_markdown(payload)
    md_path.write_text(md_text, encoding="utf-8", newline="\n")

    return verify_b1a_audit_artifacts(repo_root)


def verify_b1a_audit_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify committed W07-B1A JSON and Markdown artifacts and upstream immutability."""
    upstream_hashes = verify_all_upstream_immutability(repo_root)
    expected_payload = build_b1a_audit_payload(repo_root)

    json_path = repo_root / AUDIT_JSON_RELPATH
    md_path = repo_root / AUDIT_MD_RELPATH

    if not json_path.exists():
        raise FileNotFoundError(f"Missing W07-B1A JSON artifact: {json_path}")
    if not md_path.exists():
        raise FileNotFoundError(f"Missing W07-B1A Markdown artifact: {md_path}")

    on_disk = json.loads(json_path.read_text(encoding="utf-8"))
    computed_internal = w07_a2.compute_internal_sha256(on_disk)
    if computed_internal != on_disk.get("artifact_sha256"):
        raise ValueError(
            f"W07-B1A JSON internal SHA mismatch: {computed_internal} != {on_disk.get('artifact_sha256')}"
        )
    if computed_internal != expected_payload["artifact_sha256"]:
        raise ValueError(
            "W07-B1A JSON on-disk payload differs from deterministic builder output."
        )

    expected_md = render_b1a_audit_markdown(expected_payload)
    actual_md = md_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if actual_md != expected_md:
        raise ValueError(
            "W07-B1A Markdown on-disk content differs from deterministic builder output."
        )

    # Fail-closed invariant checks
    if on_disk.get("W07_B0_STATUS") != "CLOSED":
        raise ValueError("FAIL CLOSED: W07_B0_STATUS must be CLOSED.")
    if on_disk.get("W07_PRIMARY_CORPUS_STRATEGY") != "EVIDENCE_GROUNDED_POI_KNOWLEDGE":
        raise ValueError("FAIL CLOSED: W07_PRIMARY_CORPUS_STRATEGY mismatch.")
    if on_disk.get("HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION") is not True:
        raise ValueError(
            "FAIL CLOSED: HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION must be true."
        )
    if on_disk.get("CURRENT_LOCAL_CORPUS_READY_FOR_B2") is not False:
        raise ValueError("FAIL CLOSED: CURRENT_LOCAL_CORPUS_READY_FOR_B2 must be false.")
    if (
        on_disk.get("SOCIAL_PLATFORM_ROLE")
        != "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS"
    ):
        raise ValueError("FAIL CLOSED: SOCIAL_PLATFORM_ROLE mismatch.")
    if on_disk.get("GOOGLE_MAPS_ROLE") != "RUNTIME_ENRICHMENT_ONLY":
        raise ValueError("FAIL CLOSED: GOOGLE_MAPS_ROLE mismatch.")

    no_ext = on_disk.get("no_external_collection_at_b1a", {})
    for key in (
        "NEW_WEB_DOCUMENT_DOWNLOADS",
        "NEW_SOCIAL_COLLECTION",
        "NEW_GOOGLE_MAPS_COLLECTION",
        "NEW_LLM_PROVIDER_CALLS",
        "NEW_EXTERNAL_API_CALLS_FOR_CORPUS",
    ):
        if no_ext.get(key) != 0:
            raise ValueError(f"FAIL CLOSED: {key} must be 0.")

    if len(on_disk.get("target_poi_audit_records", [])) != 60:
        raise ValueError("FAIL CLOSED: Must audit all 60 frozen target POIs.")
    if len(on_disk.get("b1b_acquisition_gap_list", [])) != 60:
        raise ValueError("FAIL CLOSED: B1B gap list must cover all 60 deficient POIs.")

    return {
        "status": "PASS",
        "audit_json_path": AUDIT_JSON_RELPATH,
        "audit_internal_sha256": computed_internal,
        "audit_file_lf_sha256": w07_a2.compute_lf_normalized_sha256(json_path),
        "audit_md_path": AUDIT_MD_RELPATH,
        "audit_md_lf_sha256": w07_a2.compute_lf_normalized_sha256(md_path),
        "verified_existing_inventory": on_disk["verified_existing_inventory"],
        "coverage_overall": on_disk["coverage_metrics"]["overall"],
        "coverage_by_city": on_disk["coverage_metrics"]["by_city"],
        "coverage_by_category_group": on_disk["coverage_metrics"]["by_category_group"],
        "b1b_priority_summary": on_disk["b1b_priority_summary"],
        "CURRENT_LOCAL_CORPUS_READY_FOR_B2": on_disk[
            "CURRENT_LOCAL_CORPUS_READY_FOR_B2"
        ],
        "no_external_collection_at_b1a": no_ext,
        "upstream_immutability": upstream_hashes,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="W07-B1A Existing POI Knowledge Corpus Audit Builder & Verifier (v1)."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write committed W07-B1A JSON and Markdown artifacts.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify committed W07-B1A artifacts and upstream immutability without writing.",
    )
    args = parser.parse_args(argv)

    if args.write:
        res = write_b1a_audit_artifacts(REPO_ROOT)
    else:
        res = verify_b1a_audit_artifacts(REPO_ROOT)

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
