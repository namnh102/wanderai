from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import (  # noqa: E402
    validate_w07_review_corpus_v1 as w07_a2,
    verify_w07_data_strategy_amendment_01 as w07_b0,
)


def test_w07_b0_verifier_passes_and_deterministic_hashes_match() -> None:
    res = w07_b0.verify_amendment_01_artifacts(REPO_ROOT)
    assert res["status"] == "PASS"
    assert (
        res["W07_PRIMARY_CORPUS_STRATEGY"] == "EVIDENCE_GROUNDED_POI_KNOWLEDGE"
    )
    assert res["PRIMARY_W07_CORPUS"] == "OPEN_AND_OFFICIAL_POI_KNOWLEDGE"
    assert (
        res["FIRST_PARTY_REVIEW_COLLECTION_STATUS"]
        == "OPTIONAL_ENHANCEMENT_PENDING_RECRUITMENT"
    )
    assert (
        res["PUBLIC_REVIEW_ACQUISITION_STATUS"]
        == "CLOSED_NO_SUITABLE_PRIMARY_DATA"
    )
    assert res["GOOGLE_MAPS_ROLE"] == "RUNTIME_ENRICHMENT_ONLY"
    assert (
        res["SOCIAL_PLATFORM_ROLE"]
        == "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS"
    )
    assert res["W07_RETRIEVAL_EXPERIMENT_STATUS"] == "NOT_STARTED"
    assert res["W07_RAG_EXPERIMENT_STATUS"] == "NOT_STARTED"

    expected = w07_b0.build_amendment_01_payload(REPO_ROOT)
    on_disk = json.loads(
        (REPO_ROOT / w07_b0.AMENDMENT_JSON_RELPATH).read_text(encoding="utf-8")
    )
    assert (
        w07_a2.compute_internal_sha256(on_disk)
        == expected["artifact_sha256"]
        == res["amendment_internal_sha256"]
    )

    expected_md = w07_b0.render_amendment_01_markdown(expected)
    actual_md = (
        (REPO_ROOT / w07_b0.AMENDMENT_MD_RELPATH)
        .read_text(encoding="utf-8")
        .replace("\r\n", "\n")
    )
    assert actual_md == expected_md


def test_w07_b0_a4p_closure_and_strategy_transition_invariants() -> None:
    payload = json.loads(
        (REPO_ROOT / w07_b0.AMENDMENT_JSON_RELPATH).read_text(encoding="utf-8")
    )
    assert (
        payload["authoritative_base_develop_sha"]
        == "8304a71ee01d3edac224de6dc3d75beb0427fe16"
    )
    assert (
        payload["previous_accepted_gate"]
        == "W07-A4P-POSTMERGE-CHATGPT-AUDIT = PASS"
    )
    assert (
        payload["next_gate"]
        == "W07-B0-DATA-STRATEGY-AMENDMENT-01-CHATGPT-AUDIT"
    )

    a4p = payload["frozen_a4p_closure_summary"]
    assert a4p["PUBLIC_REVIEWS_DISCOVERED"] == 300536
    assert a4p["PUBLIC_UNIQUE_REVIEWS"] == 186170
    assert a4p["PUBLIC_REVIEWS_ACCEPTED"] == 0
    assert a4p["PUBLIC_REVIEWS_REJECTED"] == 124898
    assert a4p["PUBLIC_REVIEWS_QUARANTINED"] == 61272
    assert a4p["PUBLIC_POIS_COVERED"] == 0
    assert a4p["SOURCES_WITH_QUARANTINE_STATUS"] == 11
    assert a4p["REVIEW_BEARING_QUARANTINED_SOURCES"] == 3
    assert a4p["QUARANTINED_UNIQUE_REVIEW_COUNT"] == 61272
    assert (
        a4p["PUBLIC_UNIQUE_REVIEWS"]
        == a4p["PUBLIC_REVIEWS_ACCEPTED"]
        + a4p["PUBLIC_REVIEWS_REJECTED"]
        + a4p["PUBLIC_REVIEWS_QUARANTINED"]
    )
    assert (
        a4p["scientific_statement"]
        == "No suitable public review was found among the investigated sources under the frozen W07 rules."
    )
    assert a4p["broad_public_review_acquisition_reopened"] is False

    trans = payload["strategy_transition"]
    assert (
        trans["old_strategy"]
        == "POI-grounded review corpus -> retrieval -> RAG review summarization"
    )
    assert (
        trans["new_strategy"]
        == "canonical POI knowledge corpus -> retrieval -> grounded POI RAG"
    )


def test_w07_b0_role_governance_and_social_freshness_separation() -> None:
    payload = json.loads(
        (REPO_ROOT / w07_b0.AMENDMENT_JSON_RELPATH).read_text(encoding="utf-8")
    )
    roles = payload["role_governance"]

    fp = roles["first_party_reviews"]
    assert fp["status"] == "OPTIONAL_ENHANCEMENT_PENDING_RECRUITMENT"
    assert fp["scientifically_failed"] is False
    assert fp["a3_google_forms_preserved"] is True
    assert fp["a4h_assisted_collection_preserved"] is True
    assert fp["blocking_for_core_w07_retrieval_or_rag"] is False

    pub = roles["public_reviews"]
    assert pub["status"] == "CLOSED_NO_SUITABLE_PRIMARY_DATA"
    assert pub["reopen_broad_acquisition"] is False

    gmaps = roles["google_maps"]
    assert gmaps["role_code"] == "RUNTIME_ENRICHMENT_ONLY"
    assert gmaps["detailed_role"] == "RUNTIME_POI_ENRICHMENT_ONLY"
    assert gmaps["used_as_primary_frozen_scientific_corpus"] is False
    assert gmaps["bulk_scraping_allowed"] is False

    social = roles["social_platforms"]
    assert (
        social["role_code"] == "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS"
    )
    assert social["detailed_role"] == "DYNAMIC_SOCIAL_FRESHNESS_LAYER"
    assert social["used_as_primary_w07_scientific_corpus"] is False
    assert social["used_as_relevance_ground_truth"] is False
    assert social["collected_in_b0"] is False
    assert social["future_reserved_task_id"] == "SOCIAL-FRESHNESS-01"
    for p in ("TikTok", "Facebook", "Instagram", "YouTube"):
        assert p in social["platforms"]

    oc_jev = roles["openclaw_and_jev_roadmap"]
    assert oc_jev["openclaw_implemented_in_b0"] is False
    assert oc_jev["jev_implemented_in_b0"] is False
    assert oc_jev["prerequisite_for_b0_or_b1"] is False


def test_w07_b0_research_questions_gt_policy_and_corpus_thresholds() -> None:
    payload = json.loads(
        (REPO_ROOT / w07_b0.AMENDMENT_JSON_RELPATH).read_text(encoding="utf-8")
    )
    rqs = payload["research_questions"]
    rq_ret = rqs["RQ_W07_RETRIEVAL"]
    assert rq_ret["id"] == "RQ-W07-RETRIEVAL"
    assert rq_ret["primary_metric"] == "NDCG@10"
    assert set(rq_ret["secondary_metrics"]) == {
        "Recall@K",
        "MRR",
        "HitRate@K",
        "coverage",
    }
    assert set(rq_ret["candidate_strategies_for_later_comparison"]) == {
        "BM25",
        "Dense Retrieval",
        "Hybrid RRF",
        "Optional Reranking",
    }
    assert rq_ret["experiment_status"] == "NOT_STARTED"

    rq_rag = rqs["RQ_W07_RAG"]
    assert rq_rag["id"] == "RQ-W07-RAG"
    assert set(rq_rag["evaluation_dimensions"]) == {
        "answer_correctness",
        "groundedness",
        "citation_correctness",
        "unsupported_claim_rate",
        "answer_completeness",
    }
    assert rq_rag["experiment_status"] == "NOT_STARTED"

    gt = payload["human_relevance_ground_truth_policy"]
    assert gt["review_contributors_required_for_retrieval_gt"] is False
    assert gt["annotation_unit"] == "query <-> source chunk relevance"
    assert gt["separated_from_user_review_collection"] is True
    assert gt["social_signals_allowed_as_gt"] is False
    assert gt["labels_created_in_b0"] == 0

    baseline = payload["baseline_poi_knowledge_inspection"]
    assert baseline["frozen_target_pois_total"] == 60
    assert baseline["frozen_target_pois_in_freeze_v2"] == 60
    assert baseline["frozen_target_pois_by_city"] == {
        "Hà Nội": 20,
        "Đà Nẵng": 20,
        "Hạ Long": 20,
    }
    sig = baseline["existing_local_poi_signals_on_60_pois"]
    assert sig["pois_with_verified_osm_id"] == 60
    assert sig["pois_with_overture_gers_id"] == 26
    assert sig["pois_with_street_address"] == 41

    thresh = payload["proposed_corpus_thresholds"]
    assert thresh["replaces_former_300_review_threshold"] is True
    assert thresh["minimum_tier"]["min_canonical_pois"] == 30
    assert thresh["minimum_tier"]["all_three_target_cities_required"] is True
    assert (
        thresh["minimum_tier"][
            "min_independent_documents_per_poi_where_available"
        ]
        == 2
    )
    assert thresh["minimum_tier"]["min_useful_chunks_after_cleaning"] == 150
    assert thresh["preferred_tier"]["preferred_canonical_pois_min"] == 45
    assert thresh["preferred_tier"]["preferred_canonical_pois_max"] == 60
    assert thresh["preferred_tier"]["preferred_independent_documents_per_poi"] == 3
    assert thresh["preferred_tier"]["preferred_useful_chunks_min"] == 300
    assert thresh["preferred_tier"]["preferred_useful_chunks_max"] == 600


def test_w07_b0_schemas_hierarchy_method_guard_claims_and_infrastructure() -> None:
    payload = json.loads(
        (REPO_ROOT / w07_b0.AMENDMENT_JSON_RELPATH).read_text(encoding="utf-8")
    )

    tiers = payload["source_hierarchy"]["tiers"]
    assert [t["tier"] for t in tiers] == ["TIER_A", "TIER_B", "TIER_C", "TIER_D"]
    assert [t["rank"] for t in tiers] == [1, 2, 3, 4]

    doc_fields = payload["schemas"]["document_schema_fields"]
    chunk_fields = payload["schemas"]["chunk_schema_fields"]
    assert len(doc_fields) == 14
    assert len(chunk_fields) == 8

    valid_doc = {
        "document_id": "doc_poi01_osm_01",
        "poi_id": "698ee756-6062-5f47-955b-bdf458682e57",
        "city": "Hà Nội",
        "source_type": "OPENLY_LICENSED_GEOGRAPHIC_OR_TOURISM_DATA",
        "source_tier": "TIER_C",
        "source_title": "Lăng Chủ tịch Hồ Chí Minh — OpenStreetMap & Wikidata Record",
        "source_url": "https://www.openstreetmap.org/way/37625751",
        "publisher": "OpenStreetMap Contributors",
        "language": "vi",
        "retrieved_at": "2026-10-07T09:52:02Z",
        "license_or_usage_class": "ODbL-1.0",
        "raw_text": "Lăng Chủ tịch Hồ Chí Minh tại số 1 Đường Hùng Vương, Phường Ba Đình, Hà Nội.",
        "content_sha256": "a" * 64,
        "provenance_status": "VERIFIED_PUBLIC_OPEN_DATA",
    }
    assert w07_b0.validate_candidate_poi_knowledge_document(valid_doc) == []

    invalid_doc = {**valid_doc, "source_tier": "TIER_SOCIAL"}
    assert "INVALID_SOURCE_TIER:TIER_SOCIAL" in (
        w07_b0.validate_candidate_poi_knowledge_document(invalid_doc)
    )

    valid_chunk = {
        "chunk_id": "chunk_poi01_000",
        "document_id": "doc_poi01_osm_01",
        "poi_id": "698ee756-6062-5f47-955b-bdf458682e57",
        "chunk_index": 0,
        "chunk_text": "Lăng Chủ tịch Hồ Chí Minh tại số 1 Đường Hùng Vương, Phường Ba Đình, Hà Nội.",
        "token_count": 18,
        "section_title": "Overview",
        "content_sha256": "b" * 64,
    }
    assert w07_b0.validate_candidate_poi_knowledge_chunk(valid_chunk) == []

    invalid_chunk = {**valid_chunk, "token_count": 0}
    assert "INVALID_TOKEN_COUNT" in (
        w07_b0.validate_candidate_poi_knowledge_chunk(invalid_chunk)
    )

    guard = payload["method_drift_guard"]
    assert guard["method_choices_frozen_in_b0"] is False
    assert set(guard["deferred_to_later_design_gates"]) == {
        "embedding_model",
        "reranker",
        "vector_db",
        "chunk_size",
        "bm25_implementation",
        "llm_provider",
    }

    claims = payload["scientific_claims_policy"]
    assert (
        "Review-based W07 corpus construction was not feasible under the frozen constraints and available investigated sources."
        in claims["allowed_claims"]
    )
    assert (
        "The project therefore adopts an evidence-grounded POI knowledge corpus as the primary W07 retrieval corpus."
        in claims["allowed_claims"]
    )
    assert set(claims["forbidden_claims"]) == {
        "No usable tourism reviews exist anywhere.",
        "Google Maps cannot be used.",
        "First-party review collection failed scientifically.",
    }

    infra = payload["infrastructure_requirements_at_b0"]
    assert infra["GPU_REQUIRED_NOW"] is False
    assert infra["SERVER_REQUIRED_NOW"] is False
    assert infra["VECTOR_DB_SERVER_REQUIRED_NOW"] is False
    assert infra["PAID_EMBEDDING_API_REQUIRED_NOW"] is False
    assert infra["NEW_LLM_PROVIDER_CALLS"] == 0


def test_w07_b0_upstream_immutability_across_w06_and_all_w07_stages() -> None:
    hashes = w07_b0.verify_all_upstream_immutability(REPO_ROOT)
    assert (
        hashes["w06_closure_internal_sha256"]
        == "7dec87d9b318165ba5233d1470df8f12dfbe99449bceabb86dc2322aaab89e12"
    )
    assert (
        hashes["w07_0_audit_internal_sha256"]
        == "7a951b5f93473998d4032aabfeaa250ac8e7ba2ea42cbdaf230389cd5fe3a6a9"
    )
    assert (
        hashes["w07_a1_feasibility_internal_sha256"]
        == "6658b23c4f58f9dd05b7739e20eb7bd0543ed93f8dea76010e4ec3639eae6442"
    )
    assert (
        hashes["w07_a2_manifest_internal_sha256"]
        == "b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b"
    )
    assert (
        hashes["w07_a2_intake_status_internal_sha256"]
        == "4dd13bd7ad51ddfc3f501a11935f109928b2db8e9de52849da97d1a691ad2624"
    )
    assert (
        hashes["w07_a3_form_definition_internal_sha256"]
        == "9c17cfc51c41295c8338b40544324454a36a7276bb2339edd3a0b59c88c6de8a"
    )
    assert (
        hashes["w07_a3_apps_script_lf_sha256"]
        == "5e87dcf74d2bc4840792701bbd852c75781ef6ba938ac8c1eacad6d2a430be71"
    )
    assert (
        hashes["w07_a3_progress_internal_sha256"]
        == "a7eb47e50735a6f184f4ae717976b7a8bf7d1258a6d4763031c62fd691d38e70"
    )
    assert (
        hashes["w07_a4h_template_lf_sha256"]
        == "747da9d0b0033ae5ca7649bf456fde59f79f895f1248985ab1f521b43ca42bd9"
    )
    assert (
        hashes["w07_a4h_progress_internal_sha256"]
        == "b34e32af7aba9b5ee95d13f30781fbef3e15a4cb9b6a26c7b97fa1489f13ecdb"
    )
    assert (
        hashes["w07_a4h_progress_lf_sha256"]
        == "79095ce10fbf50a838d9e1a607001d821413ced6e8d6e7ad5ac2fd6e7c6239d1"
    )
    assert (
        hashes["w07_a4h_guide_lf_sha256"]
        == "4e8e133c877ec748fd7bdc66b2f3b50ab72c46686018899b1758779d18409814"
    )
    assert (
        hashes["w07_a4p_report_internal_sha256"]
        == "1ee567e59b7d4da8069f32d9734a9de95703d4955dd27cfa1db30f7a06422916"
    )
    assert (
        hashes["w07_a4p_report_lf_sha256"]
        == "b1380683b5a55d92fe467203b912af86fd945a31bc9160c789c57c3e55ae04ea"
    )
    assert (
        hashes["w07_a4p_receipt_internal_sha256"]
        == "929f7f55ebdec5387778c11080ae56db8cdf0204ac70bc11109bb59a601011c4"
    )
    assert (
        hashes["w07_a4p_receipt_lf_sha256"]
        == "bc5c8ace3618d5a67d16bf9bd5c298c52f132fc8fe575bd1678730f31b0b1d49"
    )
    assert (
        hashes["w07_a4p_md_lf_sha256"]
        == "ff6e8a3bd295910d149bd712512b025440d1ff74378c837bb0f9d05ece81885c"
    )
