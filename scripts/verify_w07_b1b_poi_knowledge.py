#!/usr/bin/env python3
"""W07-B1B — Offline Fail-Closed Verifier for Targeted POI Knowledge Acquisition."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import acquire_w07_b1b_poi_knowledge as b1b  # noqa: E402
from scripts import validate_w07_review_corpus_v1 as w07_a2  # noqa: E402

REQUIRED_CANDIDATE_FIELDS: tuple[str, ...] = (
    "candidate_source_id",
    "poi_id",
    "poi_name",
    "city",
    "category_group",
    "source_url",
    "publisher",
    "source_type",
    "source_tier",
    "source_lineage_id",
    "mapping_evidence",
    "canonical_mapping_status",
    "license_or_reuse_evidence",
    "reuse_storage_class",
    "redistributable_in_git",
    "raw_text_permitted",
    "attribution_requirement",
    "source_terms_checked_at",
    "final_b1b_decision",
)

REQUIRED_DOCUMENT_FIELDS: tuple[str, ...] = (
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
    "reuse_storage_class",
    "reuse_evidence",
    "attribution_requirement",
    "redistributable_in_git",
    "source_terms_checked_at",
    "raw_text",
    "content_sha256",
    "provenance_status",
    "source_lineage_id",
)

ALLOWED_DECISIONS = {
    "ACCEPT_PRIMARY_CORPUS",
    "ACCEPT_RESTRICTED_RESEARCH_ONLY",
    "REFERENCE_ONLY",
    "REJECT",
}

ALLOWED_REUSE_CLASSES = {
    "OPEN_REUSABLE",
    "RESEARCH_RESTRICTED",
    "REFERENCE_ONLY",
    "PROHIBITED",
}


def _verify_internal_sha256(payload: dict[str, Any], label: str) -> None:
    expected = payload.get("artifact_sha256")
    if not expected:
        raise ValueError(f"{label}: missing artifact_sha256")
    copy_data = dict(payload)
    copy_data.pop("artifact_sha256", None)
    canonical = json.dumps(copy_data, ensure_ascii=False, indent=2, sort_keys=True)
    actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if actual != expected:
        raise ValueError(f"{label}: internal artifact_sha256 mismatch ({actual} != {expected})")


def verify_b1b_artifacts() -> dict[str, Any]:
    for path in (b1b.DECISIONS_JSON_PATH, b1b.ACQUIRED_JSONL_PATH, b1b.SUMMARY_JSON_PATH, b1b.REPORT_MD_PATH):
        if not path.exists():
            raise FileNotFoundError(f"Missing required W07-B1B deliverable: {path}")

    target_manifest = json.loads(b1b.TARGET_60_PATH.read_text(encoding="utf-8"))
    target_pois = {p["poi_id"]: p for p in target_manifest["pois"]}
    if len(target_pois) != 60:
        raise ValueError(f"Expected 60 frozen target POIs, found {len(target_pois)}")

    decisions = json.loads(b1b.DECISIONS_JSON_PATH.read_text(encoding="utf-8"))
    summary = json.loads(b1b.SUMMARY_JSON_PATH.read_text(encoding="utf-8"))
    report_md = b1b.REPORT_MD_PATH.read_text(encoding="utf-8")

    _verify_internal_sha256(decisions, "w07_b1b_source_decisions_v1.json")
    _verify_internal_sha256(summary, "w07_b1b_acquisition_summary_v1.json")

    # Check header & authority invariants
    for obj, name in ((decisions, "decisions"), (summary, "summary")):
        if obj.get("authoritative_base_develop_sha") != b1b.AUTHORITATIVE_BASE_DEVELOP_SHA:
            raise ValueError(f"{name}: authoritative_base_develop_sha mismatch")
        if obj.get("previous_accepted_gate") != b1b.PREVIOUS_ACCEPTED_GATE:
            raise ValueError(f"{name}: previous_accepted_gate mismatch")
        if obj.get("W07_B1_FIX_01B_STATUS") != "CLOSED":
            raise ValueError(f"{name}: W07_B1_FIX_01B_STATUS must be CLOSED")
        if obj.get("PDG_001_STATUS") != "CLOSED":
            raise ValueError(f"{name}: PDG_001_STATUS must be CLOSED")
        if obj.get("W07_PRIMARY_CORPUS_STRATEGY") != "EVIDENCE_GROUNDED_POI_KNOWLEDGE":
            raise ValueError(f"{name}: W07_PRIMARY_CORPUS_STRATEGY mismatch")
        if obj.get("HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION") is not True:
            raise ValueError(f"{name}: HIGH_AUTHORITY_DOES_NOT_IMPLY_REUSE_PERMISSION must be True")
        if obj.get("OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC") is not True:
            raise ValueError(f"{name}: OVERTURE_LICENSE_IS_THEME_AND_SOURCE_SPECIFIC must be True")
        if obj.get("GOOGLE_MAPS_ROLE") != "RUNTIME_ENRICHMENT_ONLY":
            raise ValueError(f"{name}: GOOGLE_MAPS_ROLE mismatch")
        if obj.get("SOCIAL_PLATFORM_ROLE") != "DYNAMIC_FRESHNESS_LAYER_NOT_PRIMARY_CORPUS":
            raise ValueError(f"{name}: SOCIAL_PLATFORM_ROLE mismatch")

    if summary.get("SOCIAL_FUTURE_RESERVED_TASK_ID") != "SOCIAL-FRESHNESS-01":
        raise ValueError("summary: SOCIAL_FUTURE_RESERVED_TASK_ID mismatch")
    if summary.get("PLACE_DISCOVERY_FUTURE_RESERVED_TASK_ID") != "PLACE-DISCOVERY-01":
        raise ValueError("summary: PLACE_DISCOVERY_FUTURE_RESERVED_TASK_ID mismatch")
    if summary.get("next_gate") != b1b.NEXT_GATE:
        raise ValueError("summary: next_gate mismatch")

    # Verify candidate_decisions
    candidates = decisions.get("candidate_decisions", [])
    if not candidates:
        raise ValueError("No candidate_decisions found")
    cand_ids = set()
    accepted_doc_ids_from_decisions = set()
    for c in candidates:
        missing = [f for f in REQUIRED_CANDIDATE_FIELDS if f not in c or c[f] is None or c[f] == ""]
        if missing:
            raise ValueError(f"Candidate {c.get('candidate_source_id')} missing required fields: {missing}")
        cid = c["candidate_source_id"]
        if cid in cand_ids:
            raise ValueError(f"Duplicate candidate_source_id: {cid}")
        cand_ids.add(cid)
        if c["poi_id"] not in target_pois:
            raise ValueError(f"Candidate {cid} maps to unknown poi_id {c['poi_id']}")
        if c["reuse_storage_class"] not in ALLOWED_REUSE_CLASSES:
            raise ValueError(f"Candidate {cid} has invalid reuse_storage_class {c['reuse_storage_class']}")
        if c["final_b1b_decision"] not in ALLOWED_DECISIONS:
            raise ValueError(f"Candidate {cid} has invalid final_b1b_decision {c['final_b1b_decision']}")

        if c["final_b1b_decision"] == "ACCEPT_PRIMARY_CORPUS":
            if c["canonical_mapping_status"] != "EXACT_MAPPED":
                raise ValueError(f"Accepted candidate {cid} must be EXACT_MAPPED")
            if c["reuse_storage_class"] != "OPEN_REUSABLE":
                raise ValueError(f"Accepted candidate {cid} must be OPEN_REUSABLE")
            if c["redistributable_in_git"] is not True or c["raw_text_permitted"] is not True:
                raise ValueError(
                    f"Accepted candidate {cid} must have redistributable_in_git=True and raw_text_permitted=True"
                )
            if c.get("content_utility_status") not in ("USEFUL_NARRATIVE", "USEFUL_STRUCTURED_FACTS"):
                raise ValueError(f"Accepted candidate {cid} has non-useful content_utility_status")
            accepted_doc_ids_from_decisions.add(c["accepted_document_id"])
        else:
            if c["redistributable_in_git"] is not False or c["raw_text_permitted"] is not False:
                raise ValueError(
                    f"Non-accepted candidate {cid} must have redistributable_in_git=False and raw_text_permitted=False"
                )

    # Verify JSONL documents
    raw_lines = [line for line in b1b.ACQUIRED_JSONL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    docs = [json.loads(line) for line in raw_lines]
    if len(docs) != len(accepted_doc_ids_from_decisions):
        raise ValueError(
            f"JSONL document count ({len(docs)}) != accepted decision count ({len(accepted_doc_ids_from_decisions)})"
        )

    seen_doc_ids = set()
    seen_hashes = set()
    for d in docs:
        missing = [f for f in REQUIRED_DOCUMENT_FIELDS if f not in d or d[f] is None or d[f] == ""]
        if missing:
            raise ValueError(f"Document {d.get('document_id')} missing required B0 schema fields: {missing}")
        did = d["document_id"]
        if did in seen_doc_ids:
            raise ValueError(f"Duplicate document_id in JSONL: {did}")
        seen_doc_ids.add(did)
        if did not in accepted_doc_ids_from_decisions:
            raise ValueError(f"Document {did} in JSONL not backed by ACCEPT_PRIMARY_CORPUS decision")
        if d["poi_id"] not in target_pois:
            raise ValueError(f"Document {did} maps to unknown poi_id {d['poi_id']}")
        if d["reuse_storage_class"] != "OPEN_REUSABLE" or d["redistributable_in_git"] is not True:
            raise ValueError(f"Document {did} in Git JSONL must be OPEN_REUSABLE and redistributable_in_git=True")
        computed_sha = hashlib.sha256(d["raw_text"].encode("utf-8")).hexdigest()
        if computed_sha != d["content_sha256"]:
            raise ValueError(f"Document {did} content_sha256 mismatch")
        if computed_sha in seen_hashes:
            raise ValueError(f"Duplicate content_sha256 in JSONL: {computed_sha}")
        seen_hashes.add(computed_sha)

    # Verify lineage vs evidence unit separation (Section 4)
    unique_lineages = {d["source_lineage_id"] for d in docs}
    if len(unique_lineages) >= len(docs):
        raise ValueError("Expected multiple Wikivoyage/Wikipedia extracts from same page to share source_lineage_id")
    if len(docs) != 101 or len(unique_lineages) != 82:
        raise ValueError(f"Expected 101 documents and 82 unique lineages, got {len(docs)} and {len(unique_lineages)}")

    # Verify linked_artifacts hashes in summary
    linked = summary["linked_artifacts"]
    if linked["source_decisions_internal_sha256"] != decisions["artifact_sha256"]:
        raise ValueError("summary linked source_decisions_internal_sha256 mismatch")
    if linked["source_decisions_lf_sha256"] != w07_a2.compute_file_sha256(b1b.DECISIONS_JSON_PATH):
        raise ValueError("summary linked source_decisions_lf_sha256 mismatch")
    if linked["acquired_corpus_jsonl_lf_sha256"] != w07_a2.compute_file_sha256(b1b.ACQUIRED_JSONL_PATH):
        raise ValueError("summary linked acquired_corpus_jsonl_lf_sha256 mismatch")

    # Verify activity counters & zero-violation guards
    counters = summary["external_activity_counters"]
    if counters["PAID_DATA_API_USED"] is not False:
        raise ValueError("PAID_DATA_API_USED must be False")
    if counters["NEW_SOCIAL_COLLECTION"] != 0:
        raise ValueError("NEW_SOCIAL_COLLECTION must be 0")
    if counters["NEW_GOOGLE_MAPS_REVIEW_COLLECTION"] != 0:
        raise ValueError("NEW_GOOGLE_MAPS_REVIEW_COLLECTION must be 0")
    if counters["NEW_LLM_PROVIDER_CALLS"] != 0:
        raise ValueError("NEW_LLM_PROVIDER_CALLS must be 0")
    if counters["OPEN_REUSABLE_DOCUMENTS_ACCEPTED"] != len(docs):
        raise ValueError("OPEN_REUSABLE_DOCUMENTS_ACCEPTED mismatch")
    if counters["REFERENCE_ONLY_SOURCES"] != 16:
        raise ValueError("Expected 16 REFERENCE_ONLY_SOURCES")
    if counters["RESEARCH_RESTRICTED_SOURCES"] != 0:
        raise ValueError("Expected 0 RESEARCH_RESTRICTED_SOURCES")
    if counters["REJECTED_SOURCES"] != 15:
        raise ValueError("Expected 15 REJECTED_SOURCES")

    # Verify coverage & readiness
    ov_cov = summary["coverage_after_acquisition"]["overall_60_pois"]
    if ov_cov["total_pois"] != 60:
        raise ValueError("Expected 60 total POIs")
    if ov_cov["pois_with_rag_candidate_evidence"] != 52:
        raise ValueError(
            f"Expected 52 POIs with RAG candidate evidence, got {ov_cov['pois_with_rag_candidate_evidence']}"
        )
    if ov_cov["pois_with_2_plus_eligible_lineages"] != 45:
        raise ValueError(
            f"Expected 45 POIs with >=2 eligible lineages, got {ov_cov['pois_with_2_plus_eligible_lineages']}"
        )
    if ov_cov["pois_with_narrative_evidence"] != 32:
        raise ValueError(f"Expected 32 POIs with narrative evidence, got {ov_cov['pois_with_narrative_evidence']}")
    if ov_cov["pois_with_structured_evidence"] != 50:
        raise ValueError(f"Expected 50 POIs with structured evidence, got {ov_cov['pois_with_structured_evidence']}")
    if ov_cov["pois_with_both_structured_and_narrative"] != 30:
        raise ValueError(
            f"Expected 30 POIs with both structured and narrative, got {ov_cov['pois_with_both_structured_and_narrative']}"
        )
    if summary["W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2"] is not True:
        raise ValueError("W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2 must be True")

    # Verify no chunking/retrieval methodology frozen
    no_freeze = summary["no_chunking_or_retrieval_methodology_freeze"]
    if any(bool(v) for v in no_freeze.values()):
        raise ValueError(f"Chunking/retrieval methodology must not be frozen in B1B: {no_freeze}")

    # Verify upstream immutability
    for rel_path, expected_sha in b1b.UPSTREAM_ARTIFACT_LF_HASHES.items():
        actual_sha = w07_a2.compute_file_sha256(REPO_ROOT / rel_path)
        if actual_sha != expected_sha:
            raise ValueError(f"Upstream artifact modified: {rel_path} ({actual_sha} != {expected_sha})")

    # Verify report contains hashes
    if decisions["artifact_sha256"] not in report_md or summary["artifact_sha256"] not in report_md:
        raise ValueError("Markdown report does not match JSON artifact hashes")

    return {
        "status": "PASS",
        "candidates_evaluated": len(candidates),
        "accepted_primary_documents": len(docs),
        "accepted_independent_lineages": len(unique_lineages),
        "pois_with_rag_evidence": ov_cov["pois_with_rag_candidate_evidence"],
        "W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2": summary["W07_B1B_CORPUS_ACQUISITION_READY_FOR_B2"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify W07-B1B POI Knowledge Acquisition Artifacts")
    parser.add_argument("--verify-only", action="store_true", help="Run offline verification only")
    parser.parse_args(argv)
    res = verify_b1b_artifacts()
    print(f"PASS: W07-B1B verification succeeded: {json.dumps(res)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
