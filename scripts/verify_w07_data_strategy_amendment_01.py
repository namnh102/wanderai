"""W07-B0 — Data Strategy Amendment 01 (POI Knowledge RAG) Builder & Verifier (v1).

Formally amends the W07 scientific data strategy from a blocking review-corpus dependency
(`POI-grounded review corpus -> retrieval -> RAG review summarization`) to an
evidence-grounded canonical POI knowledge strategy
(`canonical POI knowledge corpus -> retrieval -> grounded POI RAG`) while preserving all
upstream W06, W07-0, W07-A1, W07-A2, W07-A3, W07-A4H, and W07-A4P artifacts unchanged.

Zero LLM calls, zero external network requests, zero scraping.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import (  # noqa: E402
    acquire_w07_public_reviews_v1 as w07_a4p,
    validate_w07_review_corpus_v1 as w07_a2,
)

AMENDMENT_JSON_RELPATH = "data/evaluation/w07/w07_data_strategy_amendment_01_v1.json"
AMENDMENT_MD_RELPATH = "docs/research/w07_data_strategy_amendment_01.md"

TASK_ID = "W07-B0-DATA-STRATEGY-AMENDMENT-01"
AMENDMENT_VERSION = "1.0.0"
AUTHORITATIVE_BASE_DEVELOP_SHA = "8304a71ee01d3edac224de6dc3d75beb0427fe16"
PREVIOUS_ACCEPTED_GATE = "W07-A4P-POSTMERGE-CHATGPT-AUDIT = PASS"
NEXT_GATE = "W07-B0-DATA-STRATEGY-AMENDMENT-01-CHATGPT-AUDIT"

# Expected frozen W07-A4P hashes (merged in 8304a71ee01d3edac224de6dc3d75beb0427fe16)
EXPECTED_W07_A4P_REPORT_INTERNAL_SHA256 = (
    "1ee567e59b7d4da8069f32d9734a9de95703d4955dd27cfa1db30f7a06422916"
)
EXPECTED_W07_A4P_REPORT_LF_SHA256 = (
    "b1380683b5a55d92fe467203b912af86fd945a31bc9160c789c57c3e55ae04ea"
)
EXPECTED_W07_A4P_RECEIPT_INTERNAL_SHA256 = (
    "929f7f55ebdec5387778c11080ae56db8cdf0204ac70bc11109bb59a601011c4"
)
EXPECTED_W07_A4P_RECEIPT_LF_SHA256 = (
    "bc5c8ace3618d5a67d16bf9bd5c298c52f132fc8fe575bd1678730f31b0b1d49"
)
EXPECTED_W07_A4P_MD_LF_SHA256 = (
    "ff6e8a3bd295910d149bd712512b025440d1ff74378c837bb0f9d05ece81885c"
)

# Canonical document and chunk schemas (Section 14)
REQUIRED_DOCUMENT_SCHEMA_FIELDS: tuple[str, ...] = (
    "document_id",
    "poi_id",
    "city",
    "source_type",
    "source_tier",
    "source_title",
    "source_url",
    "publisher",
    "language",
    "retrieved_at",
    "license_or_usage_class",
    "raw_text",
    "content_sha256",
    "provenance_status",
)

REQUIRED_CHUNK_SCHEMA_FIELDS: tuple[str, ...] = (
    "chunk_id",
    "document_id",
    "poi_id",
    "chunk_index",
    "chunk_text",
    "token_count",
    "section_title",
    "content_sha256",
)

SOURCE_TIERS: tuple[str, ...] = ("TIER_A", "TIER_B", "TIER_C", "TIER_D")

ELIGIBLE_EVIDENCE_CLASSES: tuple[str, ...] = (
    "OFFICIAL_TOURISM_AUTHORITY_PAGES",
    "OFFICIAL_ATTRACTION_OR_VENUE_WEBSITES",
    "GOVERNMENT_OR_LOCAL_TOURISM_PORTALS",
    "OPENLY_LICENSED_GEOGRAPHIC_OR_TOURISM_DATA",
    "OTHER_RESEARCH_USABLE_PUBLIC_DOCUMENTS_WITH_CLEAR_PROVENANCE",
)

ALLOWED_SCIENTIFIC_CLAIMS: tuple[str, ...] = (
    "Review-based W07 corpus construction was not feasible under the frozen constraints and available investigated sources.",
    "The project therefore adopts an evidence-grounded POI knowledge corpus as the primary W07 retrieval corpus.",
    "No suitable public review was found among the investigated sources under the frozen W07 rules.",
)

FORBIDDEN_SCIENTIFIC_CLAIMS: tuple[str, ...] = (
    "No usable tourism reviews exist anywhere.",
    "Google Maps cannot be used.",
    "First-party review collection failed scientifically.",
)

DEFERRED_METHOD_DECISIONS: tuple[str, ...] = (
    "embedding_model",
    "reranker",
    "vector_db",
    "chunk_size",
    "bm25_implementation",
    "llm_provider",
)


def verify_all_upstream_immutability(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """Verify W06, W07-0, W07-A1, W07-A2, W07-A3, W07-A4H, and W07-A4P remain untouched."""
    base_hashes = w07_a4p.verify_upstream_immutability(repo_root)

    a4p_report_path = repo_root / w07_a4p.PUBLIC_ACQUISITION_JSON_RELPATH
    a4p_receipt_path = repo_root / w07_a4p.PUBLIC_SOURCE_RECEIPTS_JSON_RELPATH
    a4p_md_path = repo_root / w07_a4p.PUBLIC_ACQUISITION_MD_RELPATH

    a4p_report_payload = json.loads(a4p_report_path.read_text(encoding="utf-8"))
    a4p_report_internal = w07_a2.compute_internal_sha256(a4p_report_payload)
    if a4p_report_internal != EXPECTED_W07_A4P_REPORT_INTERNAL_SHA256:
        raise ValueError(
            "FAIL CLOSED: W07-A4P report internal SHA256 mismatch: "
            f"{a4p_report_internal} != {EXPECTED_W07_A4P_REPORT_INTERNAL_SHA256}"
        )
    a4p_report_lf = w07_a2.compute_lf_normalized_sha256(a4p_report_path)
    if a4p_report_lf != EXPECTED_W07_A4P_REPORT_LF_SHA256:
        raise ValueError(
            "FAIL CLOSED: W07-A4P report LF SHA256 mismatch: "
            f"{a4p_report_lf} != {EXPECTED_W07_A4P_REPORT_LF_SHA256}"
        )

    a4p_receipt_payload = json.loads(a4p_receipt_path.read_text(encoding="utf-8"))
    a4p_receipt_internal = w07_a2.compute_internal_sha256(a4p_receipt_payload)
    if a4p_receipt_internal != EXPECTED_W07_A4P_RECEIPT_INTERNAL_SHA256:
        raise ValueError(
            "FAIL CLOSED: W07-A4P receipt internal SHA256 mismatch: "
            f"{a4p_receipt_internal} != {EXPECTED_W07_A4P_RECEIPT_INTERNAL_SHA256}"
        )
    a4p_receipt_lf = w07_a2.compute_lf_normalized_sha256(a4p_receipt_path)
    if a4p_receipt_lf != EXPECTED_W07_A4P_RECEIPT_LF_SHA256:
        raise ValueError(
            "FAIL CLOSED: W07-A4P receipt LF SHA256 mismatch: "
            f"{a4p_receipt_lf} != {EXPECTED_W07_A4P_RECEIPT_LF_SHA256}"
        )

    a4p_md_lf = w07_a2.compute_lf_normalized_sha256(a4p_md_path)
    if a4p_md_lf != EXPECTED_W07_A4P_MD_LF_SHA256:
        raise ValueError(
            "FAIL CLOSED: W07-A4P markdown LF SHA256 mismatch: "
            f"{a4p_md_lf} != {EXPECTED_W07_A4P_MD_LF_SHA256}"
        )

    return {
        **base_hashes,
        "w07_a4p_report_internal_sha256": a4p_report_internal,
        "w07_a4p_report_lf_sha256": a4p_report_lf,
        "w07_a4p_receipt_internal_sha256": a4p_receipt_internal,
        "w07_a4p_receipt_lf_sha256": a4p_receipt_lf,
        "w07_a4p_md_lf_sha256": a4p_md_lf,
    }


def inspect_existing_poi_knowledge_baseline(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Inspect existing local POI/document data across the 60 frozen W07 POIs and Freeze v2 (Section 12)."""
    manifest_path = repo_root / "data/evaluation/w07/w07_review_target_60_pois_v1.json"
    freeze_v2_path = repo_root / "data/curated/gomate_places_freeze_v2.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    freeze_v2 = json.loads(freeze_v2_path.read_text(encoding="utf-8"))
    freeze_by_id = {row["place_id"]: row for row in freeze_v2}

    norm_osm_by_id: dict[str, dict[str, Any]] = {}
    for rel_fp in (
        "data/processed/osm/hanoi_normalized_v1.json",
        "data/processed/osm/danang_normalized_v2.json",
        "data/processed/osm/halong_normalized_v1.json",
    ):
        rows = json.loads((repo_root / rel_fp).read_text(encoding="utf-8"))
        for r in rows:
            sid = r.get("source_id")
            if sid:
                norm_osm_by_id[str(sid)] = r

    pois = manifest["pois"]
    in_freeze_v2 = 0
    with_osm_id = 0
    with_overture_id = 0
    with_address = 0
    with_osm_website = 0
    with_osm_wikidata = 0
    with_osm_wikipedia = 0
    with_osm_opening_hours = 0
    with_osm_phone = 0

    by_city_counts: dict[str, int] = {"Hà Nội": 0, "Đà Nẵng": 0, "Hạ Long": 0}
    by_city_multi_source_or_rich_tag: dict[str, int] = {
        "Hà Nội": 0,
        "Đà Nẵng": 0,
        "Hạ Long": 0,
    }

    for p in pois:
        pid = p["poi_id"]
        city = p["city"]
        by_city_counts[city] = by_city_counts.get(city, 0) + 1
        if pid in freeze_by_id:
            in_freeze_v2 += 1
        if p.get("osm_id"):
            with_osm_id += 1
        if p.get("overture_id"):
            with_overture_id += 1
        if p.get("address"):
            with_address += 1

        osm_rec = norm_osm_by_id.get(str(p.get("osm_id") or ""), {})
        raw_tags = osm_rec.get("raw_tags") or {}
        has_web = bool(
            osm_rec.get("website")
            or raw_tags.get("website")
            or raw_tags.get("contact:website")
        )
        has_wd = bool(raw_tags.get("wikidata"))
        has_wp = any(str(k).startswith("wikipedia") for k in raw_tags)
        has_oh = bool(osm_rec.get("opening_hours") or raw_tags.get("opening_hours"))
        has_ph = bool(osm_rec.get("phone") or raw_tags.get("phone") or raw_tags.get("contact:phone"))

        if has_web:
            with_osm_website += 1
        if has_wd:
            with_osm_wikidata += 1
        if has_wp:
            with_osm_wikipedia += 1
        if has_oh:
            with_osm_opening_hours += 1
        if has_ph:
            with_osm_phone += 1

        if p.get("overture_id") or has_web or has_wd or has_wp:
            by_city_multi_source_or_rich_tag[city] = (
                by_city_multi_source_or_rich_tag.get(city, 0) + 1
            )

    return {
        "frozen_target_pois_total": len(pois),
        "frozen_target_pois_in_freeze_v2": in_freeze_v2,
        "frozen_target_pois_by_city": by_city_counts,
        "existing_local_poi_signals_on_60_pois": {
            "pois_with_verified_osm_id": with_osm_id,
            "pois_with_overture_gers_id": with_overture_id,
            "pois_with_street_address": with_address,
            "pois_with_osm_website_tag": with_osm_website,
            "pois_with_osm_wikidata_tag": with_osm_wikidata,
            "pois_with_osm_wikipedia_tag": with_osm_wikipedia,
            "pois_with_osm_opening_hours_tag": with_osm_opening_hours,
            "pois_with_osm_phone_tag": with_osm_phone,
            "pois_with_overture_or_external_link_by_city": by_city_multi_source_or_rich_tag,
        },
        "freeze_v2_repository_inventory": {
            "verified_osm_pois_total": 759,
            "rec_a_core_3_city_pois": 622,
            "overture_linked_pois_total": 247,
            "non_review_rag_documents_in_freeze_v2_manifest": 1223,
            "osm_metadata_documents_in_freeze_v2_manifest": 759,
            "wikivoyage_destination_chunks_in_freeze_v2_manifest": 464,
        },
    }


def build_amendment_01_payload(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build deterministic W07-B0 Data Strategy Amendment 01 payload."""
    upstream_hashes = verify_all_upstream_immutability(repo_root)
    baseline_inspection = inspect_existing_poi_knowledge_baseline(repo_root)

    payload: dict[str, Any] = {
        "artifact_id": "w07_data_strategy_amendment_01_v1",
        "version": AMENDMENT_VERSION,
        "task_id": TASK_ID,
        "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
        "previous_accepted_gate": PREVIOUS_ACCEPTED_GATE,
        "next_gate": NEXT_GATE,
        "W07_PRIMARY_CORPUS_STRATEGY": "EVIDENCE_GROUNDED_POI_KNOWLEDGE",
        "PRIMARY_W07_CORPUS": "OPEN_AND_OFFICIAL_POI_KNOWLEDGE",
        "FIRST_PARTY_REVIEW_COLLECTION_STATUS": "OPTIONAL_ENHANCEMENT_PENDING_RECRUITMENT",
        "PUBLIC_REVIEW_ACQUISITION_STATUS": "CLOSED_NO_SUITABLE_PRIMARY_DATA",
        "GOOGLE_MAPS_ROLE": "RUNTIME_ENRICHMENT_ONLY",
        "SOCIAL_PLATFORM_ROLE": "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS",
        "W07_RETRIEVAL_EXPERIMENT_STATUS": "NOT_STARTED",
        "W07_RAG_EXPERIMENT_STATUS": "NOT_STARTED",
        "frozen_a4p_closure_summary": {
            "PUBLIC_REVIEWS_DISCOVERED": 300536,
            "PUBLIC_UNIQUE_REVIEWS": 186170,
            "PUBLIC_REVIEWS_ACCEPTED": 0,
            "PUBLIC_REVIEWS_REJECTED": 124898,
            "PUBLIC_REVIEWS_QUARANTINED": 61272,
            "PUBLIC_POIS_COVERED": 0,
            "SOURCES_WITH_QUARANTINE_STATUS": 11,
            "REVIEW_BEARING_QUARANTINED_SOURCES": 3,
            "QUARANTINED_UNIQUE_REVIEW_COUNT": 61272,
            "investigated_sources_count": 18,
            "outcome_classification": "OUTCOME_C_ZERO_SUITABLE_PUBLIC_REVIEWS_FOUND",
            "scientific_statement": (
                "No suitable public review was found among the investigated sources under the frozen W07 rules."
            ),
            "broad_public_review_acquisition_reopened": False,
        },
        "strategy_transition": {
            "old_strategy": "POI-grounded review corpus -> retrieval -> RAG review summarization",
            "new_strategy": "canonical POI knowledge corpus -> retrieval -> grounded POI RAG",
            "amendment_rationale": (
                "W07-A4P investigated 18 public sources comprising 300,536 raw rows and 186,170 unique public reviews, "
                "but zero reviews satisfied the combined frozen requirements for clear academic reuse/provenance and "
                "high-confidence mapping to the 60 canonical POIs in Hà Nội, Đà Nẵng, and Hạ Long. Continuing broad "
                "public-review acquisition has diminishing scientific value. Meanwhile, first-party review collection "
                "(W07-A3 Google Forms and W07-A4H Assisted Collection) remains scientifically valid, but human contributor "
                "recruitment volume cannot be made a blocking gate for the core W07 retrieval and RAG thesis experiments. "
                "Amending the primary W07 corpus to an evidence-grounded canonical POI knowledge corpus preserves strict "
                "provenance, avoids fabricated or AI-generated reviews, avoids unauthorized commercial scraping, and "
                "enables rigorous offline evaluation of BM25, Dense, and Hybrid RRF retrieval and grounded RAG citation."
            ),
            "avoids_prohibited_shortcuts": [
                "No fabricated review data",
                "No AI-generated review augmentation",
                "No unauthorized commercial platform scraping",
                "No lowering of provenance or entity-mapping standards",
            ],
        },
        "core_scientific_corpus_definition": {
            "PRIMARY_W07_CORPUS": "OPEN_AND_OFFICIAL_POI_KNOWLEDGE",
            "W07_PRIMARY_CORPUS_STRATEGY": "EVIDENCE_GROUNDED_POI_KNOWLEDGE",
            "eligible_evidence_classes": list(ELIGIBLE_EVIDENCE_CLASSES),
            "canonical_poi_authority_path": "data/evaluation/w07/w07_review_target_60_pois_v1.json",
            "canonical_poi_authority_internal_sha256": upstream_hashes[
                "w07_a2_manifest_internal_sha256"
            ],
            "canonical_poi_identifiers_frozen": True,
            "every_primary_document_must_map_to_frozen_canonical_poi": True,
            "subset_coverage_permitted_if_justified_and_explicitly_reported": True,
        },
        "role_governance": {
            "first_party_reviews": {
                "status": "OPTIONAL_ENHANCEMENT_PENDING_RECRUITMENT",
                "scientifically_failed": False,
                "a3_google_forms_preserved": True,
                "a4h_assisted_collection_preserved": True,
                "blocking_for_core_w07_retrieval_or_rag": False,
                "policy": (
                    "Genuine first-party reviews collected via W07-A3 or W07-A4H may be incorporated later as an "
                    "optional supplementary layer without blocking primary POI-knowledge retrieval/RAG evaluation."
                ),
            },
            "public_reviews": {
                "status": "CLOSED_NO_SUITABLE_PRIMARY_DATA",
                "reopen_broad_acquisition": False,
                "policy": (
                    "W07-A4P is closed with 0 accepted primary reviews; auxiliary anonymized ABSA datasets remain "
                    "strictly separated from the primary POI corpus."
                ),
            },
            "google_maps": {
                "role_code": "RUNTIME_ENRICHMENT_ONLY",
                "detailed_role": "RUNTIME_POI_ENRICHMENT_ONLY",
                "allowed_future_runtime_fields": [
                    "rating",
                    "user_rating_count",
                    "limited_provider_authorized_review_display",
                    "place_metadata",
                    "attribution_or_source_link",
                ],
                "used_as_primary_frozen_scientific_corpus": False,
                "bulk_scraping_allowed": False,
            },
            "social_platforms": {
                "role_code": "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS",
                "detailed_role": "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
                "platforms": [
                    "TikTok",
                    "Facebook",
                    "Instagram",
                    "YouTube",
                    "social_posts_and_comments",
                ],
                "used_as_primary_w07_scientific_corpus": False,
                "used_as_relevance_ground_truth": False,
                "collected_in_b0": False,
                "future_reserved_task_id": "SOCIAL-FRESHNESS-01",
                "future_candidate_signals": [
                    "recent_mentions",
                    "trend_velocity",
                    "event_keywords",
                    "recent_content_count",
                    "engagement_signal",
                    "freshness_timestamp",
                    "source_urls",
                ],
                "future_use_cases": [
                    "trending_pois",
                    "recent_events",
                    "current_travel_interest",
                    "dynamic_homepage_hot_trending",
                    "supplementary_recommender_reranking_signal",
                ],
            },
            "openclaw_and_jev_roadmap": {
                "openclaw_implemented_in_b0": False,
                "jev_implemented_in_b0": False,
                "prerequisite_for_b0_or_b1": False,
                "openclaw_future_role": (
                    "Future orchestration of approved fresh-data and source-refresh workflows after core retrieval/RAG is stable."
                ),
                "jev_future_role": (
                    "Future enhancement evaluated only where it provides measurable value to GoMate."
                ),
            },
        },
        "research_questions": {
            "RQ_W07_RETRIEVAL": {
                "id": "RQ-W07-RETRIEVAL",
                "question": (
                    "Which retrieval strategy most effectively retrieves relevant, provenance-grounded POI information "
                    "for Vietnamese travel queries over the GoMate canonical POI knowledge corpus?"
                ),
                "candidate_strategies_for_later_comparison": [
                    "BM25",
                    "Dense Retrieval",
                    "Hybrid RRF",
                    "Optional Reranking",
                ],
                "primary_metric": "NDCG@10",
                "secondary_metrics": [
                    "Recall@K",
                    "MRR",
                    "HitRate@K",
                    "coverage",
                ],
                "experiment_status": "NOT_STARTED",
            },
            "RQ_W07_RAG": {
                "id": "RQ-W07-RAG",
                "question": (
                    "Can grounded generation using retrieved authoritative POI evidence answer travel questions with "
                    "higher factual support and citation correctness than generation without retrieval?"
                ),
                "evaluation_dimensions": [
                    "answer_correctness",
                    "groundedness",
                    "citation_correctness",
                    "unsupported_claim_rate",
                    "answer_completeness",
                ],
                "experiment_status": "NOT_STARTED",
            },
        },
        "human_relevance_ground_truth_policy": {
            "review_contributors_required_for_retrieval_gt": False,
            "annotation_unit": "query <-> source chunk relevance",
            "annotators": "Project researchers / team members following frozen annotation guidelines",
            "separated_from_user_review_collection": True,
            "social_signals_allowed_as_gt": False,
            "labels_created_in_b0": 0,
        },
        "baseline_poi_knowledge_inspection": baseline_inspection,
        "proposed_corpus_thresholds": {
            "replaces_former_300_review_threshold": True,
            "former_review_threshold_reference": "60 POIs x 5 reviews = 300 reviews (superseded for primary W07 gate)",
            "minimum_tier": {
                "min_canonical_pois": 30,
                "min_pois_per_city": 10,
                "all_three_target_cities_required": True,
                "target_cities": ["Hà Nội", "Đà Nẵng", "Hạ Long"],
                "min_independent_documents_per_poi_where_available": 2,
                "min_useful_chunks_after_cleaning": 150,
            },
            "preferred_tier": {
                "preferred_canonical_pois_min": 45,
                "preferred_canonical_pois_max": 60,
                "preferred_independent_documents_per_poi": 3,
                "preferred_useful_chunks_min": 300,
                "preferred_useful_chunks_max": 600,
            },
            "no_document_fabrication_rule": (
                "Do not fabricate or synthetically pad documents merely to hit a numerical threshold; "
                "report exact empirical coverage per city and category."
            ),
        },
        "source_hierarchy": {
            "tiers": [
                {
                    "tier": "TIER_A",
                    "rank": 1,
                    "name": "Official POI / venue website",
                    "description": "Official website or digital publication operated by the attraction, museum, hotel, or venue.",
                },
                {
                    "tier": "TIER_B",
                    "rank": 2,
                    "name": "Government / tourism-authority site",
                    "description": "National, provincial, or municipal tourism authority portals and heritage administration pages.",
                },
                {
                    "tier": "TIER_C",
                    "rank": 3,
                    "name": "Open-data / open-license geographic or tourism source",
                    "description": "OpenStreetMap (ODbL 1.0), Overture Maps (CDLA Permissive 2.0 / CC0 1.0), Wikidata (CC0), Wikimedia/Wikipedia/Wikivoyage (CC BY-SA).",
                },
                {
                    "tier": "TIER_D",
                    "rank": 4,
                    "name": "Other research-usable public source",
                    "description": "Publicly accessible travel/cultural reference documents with clear provenance and non-conflicting factual claims.",
                },
            ],
            "conflict_resolution_rule": (
                "Prefer higher authority tiers (TIER_A > TIER_B > TIER_C > TIER_D) when factual claims conflict; "
                "never treat low-authority social posts as canonical factual evidence."
            ),
        },
        "schemas": {
            "document_schema_fields": list(REQUIRED_DOCUMENT_SCHEMA_FIELDS),
            "chunk_schema_fields": list(REQUIRED_CHUNK_SCHEMA_FIELDS),
        },
        "method_drift_guard": {
            "method_choices_frozen_in_b0": False,
            "deferred_to_later_design_gates": list(DEFERRED_METHOD_DECISIONS),
        },
        "scientific_claims_policy": {
            "allowed_claims": list(ALLOWED_SCIENTIFIC_CLAIMS),
            "forbidden_claims": list(FORBIDDEN_SCIENTIFIC_CLAIMS),
        },
        "infrastructure_requirements_at_b0": {
            "GPU_REQUIRED_NOW": False,
            "SERVER_REQUIRED_NOW": False,
            "VECTOR_DB_SERVER_REQUIRED_NOW": False,
            "PAID_EMBEDDING_API_REQUIRED_NOW": False,
            "NEW_LLM_PROVIDER_CALLS": 0,
        },
        "upstream_immutability": upstream_hashes,
    }
    payload["artifact_sha256"] = w07_a2.compute_internal_sha256(payload)
    return payload


def validate_candidate_poi_knowledge_document(doc: dict[str, Any]) -> list[str]:
    """Validate a candidate POI knowledge document against the frozen Section 13 & 14 schema."""
    errors: list[str] = []
    missing = [f for f in REQUIRED_DOCUMENT_SCHEMA_FIELDS if f not in doc]
    if missing:
        errors.append(f"MISSING_REQUIRED_DOCUMENT_FIELDS:{','.join(missing)}")
        return errors

    for field in (
        "document_id",
        "poi_id",
        "city",
        "source_type",
        "source_tier",
        "source_title",
        "source_url",
        "publisher",
        "language",
        "retrieved_at",
        "license_or_usage_class",
        "raw_text",
        "content_sha256",
        "provenance_status",
    ):
        val = doc.get(field)
        if val is None or str(val).strip() == "":
            errors.append(f"EMPTY_DOCUMENT_FIELD:{field}")

    if doc.get("source_tier") not in SOURCE_TIERS:
        errors.append(f"INVALID_SOURCE_TIER:{doc.get('source_tier')}")

    if doc.get("source_type") not in ELIGIBLE_EVIDENCE_CLASSES:
        errors.append(f"INVALID_SOURCE_TYPE:{doc.get('source_type')}")

    return errors


def validate_candidate_poi_knowledge_chunk(chunk: dict[str, Any]) -> list[str]:
    """Validate a candidate POI knowledge chunk against the frozen Section 14 chunk schema."""
    errors: list[str] = []
    missing = [f for f in REQUIRED_CHUNK_SCHEMA_FIELDS if f not in chunk]
    if missing:
        errors.append(f"MISSING_REQUIRED_CHUNK_FIELDS:{','.join(missing)}")
        return errors

    for field in (
        "chunk_id",
        "document_id",
        "poi_id",
        "chunk_text",
        "section_title",
        "content_sha256",
    ):
        val = chunk.get(field)
        if val is None or str(val).strip() == "":
            errors.append(f"EMPTY_CHUNK_FIELD:{field}")

    if not isinstance(chunk.get("chunk_index"), int) or chunk["chunk_index"] < 0:
        errors.append("INVALID_CHUNK_INDEX")
    if not isinstance(chunk.get("token_count"), int) or chunk["token_count"] <= 0:
        errors.append("INVALID_TOKEN_COUNT")

    return errors


def render_amendment_01_markdown(payload: dict[str, Any]) -> str:
    """Render deterministic Markdown specification for W07-B0 (`docs/research/w07_data_strategy_amendment_01.md`)."""
    b = payload["baseline_poi_knowledge_inspection"]
    sig = b["existing_local_poi_signals_on_60_pois"]
    min_t = payload["proposed_corpus_thresholds"]["minimum_tier"]
    pref_t = payload["proposed_corpus_thresholds"]["preferred_tier"]
    infra = payload["infrastructure_requirements_at_b0"]

    lines: list[str] = [
        "# W07-B0 — Data Strategy Amendment 01: Canonical POI Knowledge RAG",
        "",
        "## 1. Authority & Context",
        "",
        f"- **Task ID:** `{payload['task_id']}`",
        f"- **Authoritative Base:** `develop@{payload['authoritative_base_develop_sha']}`",
        f"- **Previous Accepted Gate:** `{payload['previous_accepted_gate']}`",
        f"- **Next Gate:** `{payload['next_gate']}`",
        f"- **Frozen W07-A2 60-POI Manifest SHA256:** `{payload['upstream_immutability']['w07_a2_manifest_internal_sha256']}`",
        f"- **Frozen W07-A4P Report SHA256:** `{payload['upstream_immutability']['w07_a4p_report_internal_sha256']}`",
        f"- **Frozen W07-A4P Evidence Receipt SHA256:** `{payload['upstream_immutability']['w07_a4p_receipt_internal_sha256']}`",
        "",
        "## 2. Amendment Decision & Strategy Transition",
        "",
        f"- **Old Strategy:** `{payload['strategy_transition']['old_strategy']}`",
        f"- **New Strategy:** `{payload['strategy_transition']['new_strategy']}`",
        f"- `W07_PRIMARY_CORPUS_STRATEGY`: `{payload['W07_PRIMARY_CORPUS_STRATEGY']}`",
        f"- `PRIMARY_W07_CORPUS`: `{payload['PRIMARY_W07_CORPUS']}`",
        f"- `FIRST_PARTY_REVIEW_COLLECTION_STATUS`: `{payload['FIRST_PARTY_REVIEW_COLLECTION_STATUS']}`",
        f"- `PUBLIC_REVIEW_ACQUISITION_STATUS`: `{payload['PUBLIC_REVIEW_ACQUISITION_STATUS']}`",
        f"- `GOOGLE_MAPS_ROLE`: `{payload['GOOGLE_MAPS_ROLE']}`",
        f"- `SOCIAL_PLATFORM_ROLE`: `{payload['SOCIAL_PLATFORM_ROLE']}`",
        f"- `W07_RETRIEVAL_EXPERIMENT_STATUS`: `{payload['W07_RETRIEVAL_EXPERIMENT_STATUS']}`",
        f"- `W07_RAG_EXPERIMENT_STATUS`: `{payload['W07_RAG_EXPERIMENT_STATUS']}`",
        "",
        "### 2.1 Scientific Rationale",
        "",
        payload["strategy_transition"]["amendment_rationale"],
        "",
        "## 3. Core Scientific Corpus & Source Hierarchy",
        "",
        "- **Primary Corpus (`PRIMARY_W07_CORPUS`):** `OPEN_AND_OFFICIAL_POI_KNOWLEDGE`",
        "- **Frozen Target POI Universe:** `data/evaluation/w07/w07_review_target_60_pois_v1.json` (`60` canonical POIs: `20` Hà Nội, `20` Đà Nẵng, `20` Hạ Long).",
        "- **Eligible Evidence Classes:**",
    ]

    for cls_name in payload["core_scientific_corpus_definition"]["eligible_evidence_classes"]:
        lines.append(f"  - `{cls_name}`")

    lines.extend(
        [
            "",
            "### 3.1 Source Authority Hierarchy",
            "",
            "| Tier | Rank | Authority Class | Scope |",
            "|---|---:|---|---|",
        ]
    )
    for t in payload["source_hierarchy"]["tiers"]:
        lines.append(
            f"| `{t['tier']}` | {t['rank']} | {t['name']} | {t['description']} |"
        )

    lines.extend(
        [
            "",
            f"- **Conflict Resolution Rule:** {payload['source_hierarchy']['conflict_resolution_rule']}",
            "",
            "## 4. Role Governance Across Data Channels",
            "",
            "1. **First-Party Reviews (`OPTIONAL_ENHANCEMENT_PENDING_RECRUITMENT`):**",
            "   - W07-A3 Google Forms and W07-A4H Assisted Collection remain scientifically valid and preserved.",
            "   - First-party reviews are **not** marked as scientifically failed and may be added later when recruited, without blocking core W07 retrieval/RAG experiments.",
            "2. **Public Reviews (`CLOSED_NO_SUITABLE_PRIMARY_DATA`):**",
            "   - W07-A4P is closed (`300,536` discovered rows, `186,170` unique reviews, `0` accepted, `124,898` rejected, `61,272` quarantined). Broad public-review acquisition is not reopened.",
            "3. **Google Maps (`RUNTIME_ENRICHMENT_ONLY` / `RUNTIME_POI_ENRICHMENT_ONLY`):**",
            "   - Reserved for authorized runtime POI enrichment (`rating`, `user_rating_count`, limited provider-authorized review display, place metadata, attribution/source link); excluded from the primary frozen scientific corpus.",
            "4. **Social Platforms (`DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS` / `DYNAMIC_SOCIAL_FRESHNESS_LAYER`):**",
            "   - TikTok, Facebook, Instagram, YouTube, and social posts/comments are reserved for future task `SOCIAL-FRESHNESS-01` (trending POIs, recent events, dynamic homepage Hot Trending, supplementary recommender reranking signal) and must never become primary factual corpus or relevance ground truth.",
            "5. **OpenClaw & JEV Roadmap:**",
            "   - Neither is implemented in B0 or required for B0/B1 (`openclaw_implemented_in_b0 = false`, `jev_implemented_in_b0 = false`).",
            "",
            "## 5. Primary W07 Research Questions & Ground Truth Policy",
            "",
            f"- **`RQ-W07-RETRIEVAL`:** *{payload['research_questions']['RQ_W07_RETRIEVAL']['question']}*",
            "  - Candidate strategies (for later gates): `BM25`, `Dense Retrieval`, `Hybrid RRF`, `Optional Reranking`.",
            "  - Primary metric: `NDCG@10`; secondary metrics: `Recall@K`, `MRR`, `HitRate@K`, `coverage`.",
            f"- **`RQ-W07-RAG`:** *{payload['research_questions']['RQ_W07_RAG']['question']}*",
            "  - Evaluation dimensions (for later gates): `answer_correctness`, `groundedness`, `citation_correctness`, `unsupported_claim_rate`, `answer_completeness`.",
            "- **Human Relevance Ground Truth Policy:**",
            "  - Project researchers/team members judge `query <-> source chunk relevance` under frozen annotation guidelines, strictly separated from user review collection (`review_contributors_required_for_retrieval_gt = false`, `labels_created_in_b0 = 0`).",
            "",
            "## 6. Baseline Repository Inspection & Proposed Corpus Thresholds",
            "",
            f"- **Frozen 60 POIs in Freeze v2 (`data/curated/gomate_places_freeze_v2.json`):** `{b['frozen_target_pois_in_freeze_v2']} / {b['frozen_target_pois_total']}` (`20` Hà Nội, `20` Đà Nẵng, `20` Hạ Long).",
            f"- **Existing Local POI Signals on the 60 POIs:** `{sig['pois_with_verified_osm_id']}` verified OSM IDs, `{sig['pois_with_overture_gers_id']}` Overture GERS IDs, `{sig['pois_with_street_address']}` street addresses, `{sig['pois_with_osm_website_tag']}` OSM website tags, `{sig['pois_with_osm_wikidata_tag']}` Wikidata IDs, `{sig['pois_with_osm_wikipedia_tag']}` Wikipedia tags, `{sig['pois_with_osm_opening_hours_tag']}` opening hours.",
            f"- **Minimum Corpus Threshold:** `>= {min_t['min_canonical_pois']}` canonical POIs (`>= {min_t['min_pois_per_city']}` per city across all 3 target cities), `>= {min_t['min_independent_documents_per_poi_where_available']}` independently provenance-bound documents per covered POI where available, and `>= {min_t['min_useful_chunks_after_cleaning']}` useful chunks after cleaning/chunking.",
            f"- **Preferred Corpus Threshold:** `{pref_t['preferred_canonical_pois_min']}–{pref_t['preferred_canonical_pois_max']}` canonical POIs, `>= {pref_t['preferred_independent_documents_per_poi']}` documents per POI where feasible, and `{pref_t['preferred_useful_chunks_min']}–{pref_t['preferred_useful_chunks_max']}` high-quality chunks.",
            "",
            "## 7. Canonical Document & Chunk Schemas",
            "",
            "- **Document Schema (`14` fields):** "
            + ", ".join(f"`{f}`" for f in payload["schemas"]["document_schema_fields"]),
            "- **Chunk Schema (`8` fields):** "
            + ", ".join(f"`{f}`" for f in payload["schemas"]["chunk_schema_fields"]),
            "- **Deferred Method Decisions (Not Frozen in B0):** "
            + ", ".join(
                f"`{d}`"
                for d in payload["method_drift_guard"]["deferred_to_later_design_gates"]
            ),
            "",
            "## 8. Scientific Claims Firewall & Infrastructure at B0",
            "",
            "- **Allowed Scientific Claims:**",
        ]
    )

    for claim in payload["scientific_claims_policy"]["allowed_claims"]:
        lines.append(f"  - \"{claim}\"")

    lines.append("- **Forbidden Overclaims:**")
    for fclaim in payload["scientific_claims_policy"]["forbidden_claims"]:
        lines.append(f"  - ~~\"{fclaim}\"~~ *(Forbidden)*")

    lines.extend(
        [
            f"- `GPU_REQUIRED_NOW`: `{str(infra['GPU_REQUIRED_NOW']).lower()}`",
            f"- `SERVER_REQUIRED_NOW`: `{str(infra['SERVER_REQUIRED_NOW']).lower()}`",
            f"- `VECTOR_DB_SERVER_REQUIRED_NOW`: `{str(infra['VECTOR_DB_SERVER_REQUIRED_NOW']).lower()}`",
            f"- `PAID_EMBEDDING_API_REQUIRED_NOW`: `{str(infra['PAID_EMBEDDING_API_REQUIRED_NOW']).lower()}`",
            f"- `NEW_LLM_PROVIDER_CALLS`: `{infra['NEW_LLM_PROVIDER_CALLS']}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_amendment_01_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Write committed W07-B0 JSON and Markdown artifacts."""
    payload = build_amendment_01_payload(repo_root)
    json_path = repo_root / AMENDMENT_JSON_RELPATH
    md_path = repo_root / AMENDMENT_MD_RELPATH

    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    json_text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    json_path.write_text(json_text, encoding="utf-8", newline="\n")

    md_text = render_amendment_01_markdown(payload)
    md_path.write_text(md_text, encoding="utf-8", newline="\n")

    return verify_amendment_01_artifacts(repo_root)


def verify_amendment_01_artifacts(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify committed W07-B0 JSON and Markdown artifacts and upstream immutability."""
    upstream_hashes = verify_all_upstream_immutability(repo_root)
    expected_payload = build_amendment_01_payload(repo_root)

    json_path = repo_root / AMENDMENT_JSON_RELPATH
    md_path = repo_root / AMENDMENT_MD_RELPATH

    if not json_path.exists():
        raise FileNotFoundError(f"Missing W07-B0 JSON artifact: {json_path}")
    if not md_path.exists():
        raise FileNotFoundError(f"Missing W07-B0 Markdown artifact: {md_path}")

    on_disk = json.loads(json_path.read_text(encoding="utf-8"))
    computed_internal = w07_a2.compute_internal_sha256(on_disk)
    if computed_internal != on_disk.get("artifact_sha256"):
        raise ValueError(
            f"W07-B0 JSON internal SHA mismatch: {computed_internal} != {on_disk.get('artifact_sha256')}"
        )
    if computed_internal != expected_payload["artifact_sha256"]:
        raise ValueError(
            "W07-B0 JSON on-disk payload differs from deterministic builder output."
        )

    expected_md = render_amendment_01_markdown(expected_payload)
    actual_md = md_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if actual_md != expected_md:
        raise ValueError(
            "W07-B0 Markdown on-disk content differs from deterministic builder output."
        )

    # Fail-closed invariant checks
    if on_disk.get("W07_PRIMARY_CORPUS_STRATEGY") != "EVIDENCE_GROUNDED_POI_KNOWLEDGE":
        raise ValueError("FAIL CLOSED: W07_PRIMARY_CORPUS_STRATEGY mismatch.")
    if on_disk.get("PRIMARY_W07_CORPUS") != "OPEN_AND_OFFICIAL_POI_KNOWLEDGE":
        raise ValueError("FAIL CLOSED: PRIMARY_W07_CORPUS mismatch.")
    if (
        on_disk.get("FIRST_PARTY_REVIEW_COLLECTION_STATUS")
        != "OPTIONAL_ENHANCEMENT_PENDING_RECRUITMENT"
    ):
        raise ValueError("FAIL CLOSED: FIRST_PARTY_REVIEW_COLLECTION_STATUS mismatch.")
    if (
        on_disk.get("PUBLIC_REVIEW_ACQUISITION_STATUS")
        != "CLOSED_NO_SUITABLE_PRIMARY_DATA"
    ):
        raise ValueError("FAIL CLOSED: PUBLIC_REVIEW_ACQUISITION_STATUS mismatch.")
    if on_disk.get("GOOGLE_MAPS_ROLE") != "RUNTIME_ENRICHMENT_ONLY":
        raise ValueError("FAIL CLOSED: GOOGLE_MAPS_ROLE mismatch.")
    if (
        on_disk.get("SOCIAL_PLATFORM_ROLE")
        != "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS"
    ):
        raise ValueError("FAIL CLOSED: SOCIAL_PLATFORM_ROLE mismatch.")
    if on_disk.get("W07_RETRIEVAL_EXPERIMENT_STATUS") != "NOT_STARTED":
        raise ValueError("FAIL CLOSED: W07_RETRIEVAL_EXPERIMENT_STATUS must be NOT_STARTED.")
    if on_disk.get("W07_RAG_EXPERIMENT_STATUS") != "NOT_STARTED":
        raise ValueError("FAIL CLOSED: W07_RAG_EXPERIMENT_STATUS must be NOT_STARTED.")

    infra = on_disk.get("infrastructure_requirements_at_b0", {})
    if infra.get("GPU_REQUIRED_NOW") is not False:
        raise ValueError("FAIL CLOSED: GPU_REQUIRED_NOW must be false.")
    if infra.get("SERVER_REQUIRED_NOW") is not False:
        raise ValueError("FAIL CLOSED: SERVER_REQUIRED_NOW must be false.")
    if infra.get("VECTOR_DB_SERVER_REQUIRED_NOW") is not False:
        raise ValueError("FAIL CLOSED: VECTOR_DB_SERVER_REQUIRED_NOW must be false.")
    if infra.get("PAID_EMBEDDING_API_REQUIRED_NOW") is not False:
        raise ValueError("FAIL CLOSED: PAID_EMBEDDING_API_REQUIRED_NOW must be false.")
    if infra.get("NEW_LLM_PROVIDER_CALLS") != 0:
        raise ValueError("FAIL CLOSED: NEW_LLM_PROVIDER_CALLS must be 0.")

    return {
        "status": "PASS",
        "amendment_json_path": AMENDMENT_JSON_RELPATH,
        "amendment_internal_sha256": computed_internal,
        "amendment_file_lf_sha256": w07_a2.compute_lf_normalized_sha256(json_path),
        "amendment_md_path": AMENDMENT_MD_RELPATH,
        "amendment_md_lf_sha256": w07_a2.compute_lf_normalized_sha256(md_path),
        "W07_PRIMARY_CORPUS_STRATEGY": on_disk["W07_PRIMARY_CORPUS_STRATEGY"],
        "PRIMARY_W07_CORPUS": on_disk["PRIMARY_W07_CORPUS"],
        "FIRST_PARTY_REVIEW_COLLECTION_STATUS": on_disk[
            "FIRST_PARTY_REVIEW_COLLECTION_STATUS"
        ],
        "PUBLIC_REVIEW_ACQUISITION_STATUS": on_disk["PUBLIC_REVIEW_ACQUISITION_STATUS"],
        "GOOGLE_MAPS_ROLE": on_disk["GOOGLE_MAPS_ROLE"],
        "SOCIAL_PLATFORM_ROLE": on_disk["SOCIAL_PLATFORM_ROLE"],
        "W07_RETRIEVAL_EXPERIMENT_STATUS": on_disk["W07_RETRIEVAL_EXPERIMENT_STATUS"],
        "W07_RAG_EXPERIMENT_STATUS": on_disk["W07_RAG_EXPERIMENT_STATUS"],
        "infrastructure_requirements_at_b0": infra,
        "upstream_immutability": upstream_hashes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W07-B0 Data Strategy Amendment 01 Builder & Verifier (v1)."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write committed W07-B0 JSON and Markdown artifacts.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify committed W07-B0 artifacts and upstream immutability without writing.",
    )
    args = parser.parse_args(argv)

    if args.write:
        res = write_amendment_01_artifacts(REPO_ROOT)
    else:
        res = verify_amendment_01_artifacts(REPO_ROOT)

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
