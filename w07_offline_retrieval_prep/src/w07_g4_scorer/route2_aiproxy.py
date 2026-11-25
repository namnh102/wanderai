"""Harmonized OD-G15-05-AIPROXY (Route 2 Zero-Human AI-Proxy) pipeline, SV-01 dossier validator, and cost matrix."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from w07_g4_scorer.contracts import (
    ANNEX_G15_CONTRASTS_K1_K5,
    SHA256_HEX_RE,
    sha256_bytes,
)
from w07_g4_scorer.judge_gates import (
    EXPECTED_V_CORPUS_SHA256,
    build_prompt_order_pair,
    check_g5_gate_unlock,
    emit_blind_judge_packets,
    evaluate_budget_and_retry_circuit_breakers,
    evaluate_dual_judge_concordance,
    evaluate_prompt_order_bias,
    seal_expected_pairs_manifest,
    validate_judge_response,
    verify_sealed_expected_pairs_manifest,
)
from w07_g4_scorer.query_manifest import (
    ANNEX_G15_CITY_QUOTAS,
    validate_pre_g3_query_manifest,
)

ROUTE2_DECISION_ID = "OD-G15-05-AIPROXY"
ROUTE2_HARMONIZATION_ID = "W07-ROUTE2-AIPROXY-HARMONIZED-V1.1"
ROUTE2_BUNDLE_SCHEMA_VERSION = "GOMATE_W07_ROUTE2_AIPROXY_BUNDLE_V1_1"
ROUTE2_READINESS_SCHEMA_VERSION = "GOMATE_W07_ROUTE2_ACTIVATION_READINESS_REPORT_V1_1"
PROTOCOL_V1_0_SHA256 = "5056c5c2373ee9584b8850ba49411160cc2c382ad6315aaada4c05fb9b0030c2"
ANNEX_V0_2_2_SHA256 = "e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940"
AUTHOR_SAFE_60_POI_CATALOG_SHA256 = "53019a67eb90eeb772232b2c7130a3e0d1e725d5d6931c7ae3768885e4014152"
PINNED_STAGE1_SYSTEM_PROMPT_V1_1_SHA256 = "b02b56d2b843b442ecb65df92b35cb30593c4e8cb154b41e67ec9efa3b6241b6"

ROUTE2_AMENDMENT_02_ID = "W07-ROUTE2-AMENDMENT-02-TEXT-VERDICT-AND-SV01B"
AUDITOR_VERDICT_MODE_DUAL_ED25519 = "DUAL_ED25519_EXTERNAL_AUDITOR"
AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER = "AI_AUDIT_TEXT_OWNER_ATTESTED"
ALLOWED_AUDITOR_VERDICT_MODES: tuple[str, str] = (
    AUDITOR_VERDICT_MODE_DUAL_ED25519,
    AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER,
)
# Historical pre-Amendment-02 and negative audit reports can NEVER ratify Amendment 02 or unlock live execution.
FORBIDDEN_PRIOR_PRE_AMENDMENT_AUDIT_SHA256S: frozenset[str] = frozenset(
    {
        "4a787a0dcffca4cb79f9bde379966256284ad48601ec20b2f3fefd03e0d42da4",
        "821544d3ca496ec4fa1f7e62ae4a9f654068f64cdbb0e9acf286688e51f67bc1",
        "aa704b836e83789e26df5d83db83c5bb985c48efadca414a2fce67f980f3f871",
        "831085861392e75e69487a08a7f1519643ffbfdf4a0e1e46edc233c23d64de9f",
    }
)
REJECTED_PRIOR_AUDIT_ZIP_SHA256S: frozenset[str] = frozenset(
    {
        "36d541c61ba8ecab98ee1d8fcb2121fe85998a8464ce28eed4b06437bc913403",
        "a77a9345978419f34ba3eaa460600e31b9896787f8343b5fb0afb85fa7c48748",
    }
)

# Read-only Ed25519 live trust anchors remain None while Route 2 is in HOLD.
# Plain booleans or environment variables NEVER grant live execution or spending authority.
PINNED_LIVE_ROUTE2_OWNER_PUBKEY_HEX: str | None = None
PINNED_LIVE_ROUTE2_AUDITOR_PUBKEY_HEX: str | None = None

ROUTE2_TRUST_ROOT_DOMAIN_TAG = b"GOMATE_W07_ROUTE2_TRUST_ROOT_V1\x00"
ROUTE2_OWNER_ACTIVATION_DOMAIN_TAG = b"GOMATE_W07_ROUTE2_OWNER_ACTIVATION_V1\x00"
ROUTE2_OD_AE_05_DOMAIN_TAG = b"GOMATE_W07_ROUTE2_OD_AE_05_V1\x00"
ROUTE2_PROVIDER_PREFLIGHT_DOMAIN_TAG = b"GOMATE_W07_ROUTE2_PROVIDER_PREFLIGHT_V1\x00"
ROUTE2_AUDITOR_VERDICT_DOMAIN_TAG = b"GOMATE_W07_ROUTE2_AUDITOR_VERDICT_V1\x00"
ROUTE2_SV01_EVIDENCE_DOMAIN_TAG = b"GOMATE_W07_ROUTE2_SV01_EVIDENCE_V1\x00"

AUTHOR_SAFE_POI_KEYS: tuple[str, ...] = ("poi_id", "name", "city", "category", "category_group")
FORBIDDEN_G2A_INPUT_KEYS: frozenset[str] = frozenset(
    {
        "canonical_text_S",
        "raw_text",
        "answer_ready_confirmed_text",
        "v_text",
        "sanitized_doc_v",
        "safe_doc_v",
        "p0_flag",
        "is_p0",
        "zero_coverage_flag",
        "chunk_text",
        "rank_position",
        "retrieval_scores",
        "g3_rankings",
        "gold_relevance_labels",
    }
)
FORBIDDEN_CLOUD_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "canonical_text_S",
        "raw_text",
        "removed_r_audit",
        "removed_intervals",
        "v_to_s_segments",
        "document_id",
        "poi_id",
        "source_url",
        "source_lineage_id",
        "canonical_s_sha256",
        "rank",
        "cell_id",
        "system_id",
        "query_id",
        "query_family",
        "gold_relevance_labels",
    }
)
FORBIDDEN_CLOUD_TEXT_MARKERS: tuple[str, ...] = (
    "[CORROBORATED:",
    "[SOURCE_REPORTED_UNVERIFIED]",
    "[UNVERIFIED]",
    "[SUPPRESSED_FACT_CONFLICT]",
    "t0" + "_private",
    "w07-b1b-doc-",
    "tripadvisor.",
    "booking.com",
    "klook.com",
    "traveloka.com",
    "maps.google.",
)
_EMAIL_LOCAL_PART_RE = r"[\w\u0300-\u036f](?:[\w\u0300-\u036f\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f.%+\-]*[\w\u0300-\u036f])?"
_EMAIL_DOMAIN_LABEL_RE = r"[^\W_](?:[\w\u0300-\u036f\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f\-]*[\w\u0300-\u036f])?"
_EMAIL_TLD_RE = r"(?:xn--[A-Za-z0-9\-]{2,}|[^\W\d_]{2,})"
CLOUD_EMAIL_PII_RE = re.compile(
    rf"(?<![\w@]){_EMAIL_LOCAL_PART_RE}@{_EMAIL_DOMAIN_LABEL_RE}(?:\.{_EMAIL_DOMAIN_LABEL_RE})*\.{_EMAIL_TLD_RE}(?![\w])",
    re.UNICODE,
)
# Fail-closed fallback catching unresolved '@' or fullwidth '＠' candidate tokens (e.g. odd Unicode/IPv6/local@host)
# while permitting benign non-email evaluation labels like 'nDCG@10' or isolated spaced '@'.
UNRESOLVED_AT_EMAIL_FALLBACK_RE = re.compile(
    r"[^\s\"'<>()\[\]{},;:\\/@\uff20]+[@\uff20](?:\[[^\s\[\]]+\]|[^\s\"'<>()\[\]{},;:\\/@\uff20]*(?:[^\W\d_]|\.|xn--)[^\s\"'<>()\[\]{},;:\\/@\uff20]*)",
    re.UNICODE,
)
PROHIBITED_ANCHOR_MARKERS: tuple[str, ...] = (
    "[CORROBORATED:",
    "[SOURCE_REPORTED_UNVERIFIED]",
    "[UNVERIFIED]",
    "[SUPPRESSED_FACT_CONFLICT]",
    "[CONFLICT",
    "FC-001",
    "FC-002",
)
LIVE_VOLATILITY_RE = re.compile(
    r"\b(?:hôm nay|ngay lúc này|ngay bây giờ|thời gian thực|right now|live availability|current weather)\b",
    re.IGNORECASE,
)
WORD_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)

SUPERVISOR_ALLOWED_STATUSES: frozenset[str] = frozenset(
    {"OWNER_REPORTED_APPROVAL", "SUPERVISOR_WRITTEN_VERIFIED"}
)
ALLOWED_SEMANTIC_MODES: frozenset[str] = frozenset(
    {
        "OFFLINE_NO_SEMANTIC_VERIFIER",
        "SYNTHETIC_DECLARED_MOCK_TEST_ONLY",
        "AUTHORIZED_INDEPENDENT_BLIND_MODEL",
    }
)

FORBIDDEN_TOY_HASHES: frozenset[str] = frozenset(
    {c * 64 for c in "0123456789abcdef"} | {"deadbeef" * 8, "12345678" * 8}
)

ROUTE2_HARMONIZATION_MATRIX: tuple[dict[str, str], ...] = (
    {
        "axis": "authority_and_annex_baseline",
        "prior_conflict": "G2A v2.0.1, G2B v1.1, AUTO-EVAL-01 v0.4.2 referenced Annex v0.2.1 & $20 cap; OD-G15-05 Note referenced Annex v0.2.2; Budget40 raised total cap to $40",
        "harmonized_resolution": "Anchor to Protocol v1.0 (5056c5c2) + Technical Annex v0.2.2 (e78013fd, MiniLM tokenizer 2c3387be, STUB-01..05 sealed PASS). Preserve $20.00 baseline hard cap via PA-1 unless Owner signs Budget40 ($2.00 DEV / $36.00 warn / $40.00 cap) in external Ed25519 trust root.",
    },
    {
        "axis": "g2a_query_authorship_and_sv_boundary",
        "prior_conflict": "G2A-2 validates verbatim offsets on canonical S while OD-AE-05 permits uploading Tier-T1 sanitized V only and forbids raw S/R_AUDIT",
        "harmonized_resolution": "Strict S/V separation: outbound cloud payloads carry ONLY Tier-T1 sanitized V (safe_doc_v, hard-blocked if R_AUDIT/raw S/T0/T2/PII present); exact V->S projection and canonical S substring validation run 100% locally in Python; AI origin='AI_GENERATED_NO_HUMAN_REVIEW', human_ground_truth=False.",
    },
    {
        "axis": "execution_chronology_d054",
        "prior_conflict": "ORDER_A put G2B pre-G3 while ORDER_B & Decision Note put G3 pre-G2B",
        "harmonized_resolution": "Stage-1 off-FINAL 5-query DEV canary (quarantined packet, zero G3/FINAL-50) -> Stage-2 G2A PRE_G3_QUERY_LOCK -> G3 local CPU 2x3 sealed ranking -> G2B blind rank-invariant FX-11 judging -> G4 decoupled scorer.",
    },
    {
        "axis": "pooling_and_coverage_order_a_vs_b",
        "prior_conflict": "Protocol v1.0 pooled union vs Budget40 full 50x137 Cartesian ORDER_A vs ORDER_B top-k union",
        "harmonized_resolution": "Primary: ORDER_A (50x137=6,850/judge = 13,700 base votes, UNJUDGED=0) fits <= $20 cap under PA-1; fallback ORDER_B pre-sealed union pool (out-of-pool stays UNJUDGED (0,3)). Missing pairs trigger INCOMPLETE_SEALED_JUDGE_COVERAGE_HALT.",
    },
    {
        "axis": "judge_sampling_params_and_prompt_order_coverage",
        "prior_conflict": "Decision Note requested temperature=0 and per-pair ORDER_A/B rubric swaps; AUTO-R09 forbids cloud sampling params and cost budgets use stratified swaps",
        "harmonized_resolution": "Preserve AUTO-R09 (reasoning_effort='low', output_config.effort='low', thinking_level='LOW'; no temperature/top_p/top_k on cloud reasoning); replace full-pair swap claim with explicitly recorded stratified audit sampling: STRATIFIED_20PCT_DEV_AUDIT (137/685 pairs) in Stage-1 and STRATIFIED_200PAIR_FINAL_AUDIT (200/6,850 pairs) in FINAL, using PROMPT_ORDER_CANONICAL vs PROMPT_ORDER_SWAPPED with full_pair_invariance_claimed=False whenever coverage < 1.0.",
    },
    {
        "axis": "acceptance_and_kappa_thresholds",
        "prior_conflict": "judge_gates.py omitted Annex v0.2.2 delta_min >= +0.030; Decision Note mixed order-swap kappa >= 0.75 with cross-family kappa_w >= 0.40",
        "harmonized_resolution": "Require BOTH: stratified prompt-order swap agreement >= 0.90 (kappa_w_order >= 0.75) on DEV/audit slice AND cross-family kappa_w_AB >= 0.40, delta_min >= +0.030, p_mc_holm < 0.05, 95% CI > 0 on BOTH judges; else NO_CLEAR_PROXY_WINNER.",
    },
    {
        "axis": "external_t2_benchmark_isolation",
        "prior_conflict": "AUTO-EVAL-01 included ZaloLegalQA/EduCoQA while Clearance Matrix kept them HOLD due to unclear/NC licenses",
        "harmonized_resolution": "Mark external Track T2 optional and non-blocking for W07 Track T1 retrieval closure; never upload external benchmarks or commercial Tier-T2 text to cloud APIs.",
    },
)


def _norm_tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_TOKEN_RE.finditer(text)]


def compute_author_safe_poi_catalog_sha256(pois: Sequence[Mapping[str, Any]]) -> str:
    rows = [{k: row[k] for k in AUTHOR_SAFE_POI_KEYS} for row in pois]
    rows.sort(key=lambda x: str(x["poi_id"]))
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(encoded)


def check_corpus_v_token_overlap(
    query_text: str,
    corpus_v_texts: Sequence[str],
    *,
    ngram_size: int = 8,
) -> dict[str, Any]:
    """Deterministic >=N-token overlap firewall preventing verbatim passage leakage from corpus V."""
    if ngram_size < 3:
        raise ValueError("ngram_size must be >= 3")
    q_toks = _norm_tokens(query_text)
    if len(q_toks) < ngram_size:
        return {"leak_detected": False, "max_overlap_tokens": len(q_toks), "matched_ngram": None}
    q_ngrams = {tuple(q_toks[i : i + ngram_size]) for i in range(len(q_toks) - ngram_size + 1)}
    for v_txt in corpus_v_texts:
        v_toks = _norm_tokens(v_txt)
        if len(v_toks) < ngram_size:
            continue
        for i in range(len(v_toks) - ngram_size + 1):
            gram = tuple(v_toks[i : i + ngram_size])
            if gram in q_ngrams:
                return {
                    "leak_detected": True,
                    "max_overlap_tokens": ngram_size,
                    "matched_ngram": " ".join(gram),
                }
    return {"leak_detected": False, "max_overlap_tokens": 0, "matched_ngram": None}


def compute_s5_snapshot_audit_sha256(
    *,
    query_id: str,
    query_text: str,
    city: str,
    verifier_model_id: str,
    per_doc_outcomes: Sequence[Mapping[str, Any]],
) -> str:
    """Recompute S5 137-document closed-snapshot absence digest cleanly (ZH-SCI-02)."""
    norm_outcomes = [
        {
            "document_id": str(row["document_id"]),
            "canonical_s_sha256": str(row["canonical_s_sha256"]),
            "outcome": str(row["outcome"]),
        }
        for row in sorted(per_doc_outcomes, key=lambda r: str(r["document_id"]))
    ]
    payload = {
        "query_id": query_id,
        "query_sha256": sha256_bytes(query_text.encode("utf-8")),
        "city": city,
        "verifier_model_id": verifier_model_id,
        "per_doc_outcomes": norm_outcomes,
    }
    return sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _scan_forbidden_g2a_payload_keys(obj: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            ks = str(k)
            if ks in FORBIDDEN_G2A_INPUT_KEYS:
                hits.append(f"{path}.{ks}")
            hits.extend(_scan_forbidden_g2a_payload_keys(v, f"{path}.{ks}"))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            hits.extend(_scan_forbidden_g2a_payload_keys(item, f"{path}[{idx}]"))
    return hits


def validate_g2a_zero_human_proxy_batch(
    *,
    catalog_pois: Sequence[Mapping[str, Any]],
    candidate_queries: Sequence[Mapping[str, Any]],
    docs_by_id: Mapping[str, Mapping[str, Any]],
    source_verification_records: Mapping[str, Mapping[str, Any]],
    generator_model_family: str,
    verifier_model_family: str,
    judge_a_family: str,
    judge_b_family: str,
    semantic_verifier_mode: str = "OFFLINE_NO_SEMANTIC_VERIFIER",
    generator_role_exception_signed: bool = False,
    expected_catalog_sha256: str | None = AUTHOR_SAFE_60_POI_CATALOG_SHA256,
    enforce_final50_matrix: bool = False,
    route2_ai_proxy_approved: bool = False,
) -> dict[str, Any]:
    """Fail-closed validator for G2A-1 (corpus-blind AI generation) + G2A-2 (G3-blind canonical S verification)."""
    if semantic_verifier_mode not in ALLOWED_SEMANTIC_MODES:
        raise ValueError(f"Invalid semantic_verifier_mode: {semantic_verifier_mode!r}")

    leak_keys = _scan_forbidden_g2a_payload_keys(list(catalog_pois))
    if leak_keys:
        raise ValueError(f"G2A_FIREWALL_FORBIDDEN_CORPUS_KEYS_IN_CATALOG: {leak_keys[:5]}")

    for idx, poi in enumerate(catalog_pois):
        if set(poi.keys()) != set(AUTHOR_SAFE_POI_KEYS):
            raise ValueError(f"Catalog row {idx} keys must equal {AUTHOR_SAFE_POI_KEYS}, got {sorted(poi.keys())}")

    cat_sha = compute_author_safe_poi_catalog_sha256(catalog_pois)
    if expected_catalog_sha256 is not None and not hmac.compare_digest(cat_sha, expected_catalog_sha256):
        raise ValueError(f"G2A_CATALOG_SHA256_MISMATCH: expected {expected_catalog_sha256}, got {cat_sha}")

    # Enforce 4-way family isolation (except explicit signed exception for corpus-blind G2A-1 generator)
    families = {
        "generator": generator_model_family.strip().lower(),
        "verifier": verifier_model_family.strip().lower(),
        "judge_A": judge_a_family.strip().lower(),
        "judge_B": judge_b_family.strip().lower(),
    }
    for role, fam in families.items():
        if not fam or "minilm" in fam:
            raise ValueError(f"Invalid or dense-overlapping family on {role}: {fam!r}")
    if families["judge_A"] == families["judge_B"]:
        raise ValueError(f"G2B judge families must be distinct: {families['judge_A']!r}")
    if families["verifier"] in {families["judge_A"], families["judge_B"]}:
        raise ValueError("G2A-2 verifier family must differ from G2B judge_A and judge_B")
    if not generator_role_exception_signed and families["generator"] in {
        families["verifier"],
        families["judge_A"],
        families["judge_B"],
    }:
        raise ValueError(
            "G2A-1 generator family must differ from verifier/judge_A/judge_B unless signed generator_role_exception_signed=True"
        )

    approved_pois = {str(p["poi_id"]): dict(p) for p in catalog_pois}
    corpus_v_texts = [str(d.get("sanitized_text_V", d.get("canonical_text_S", ""))) for d in docs_by_id.values()]

    if enforce_final50_matrix:
        validate_pre_g3_query_manifest(
            [dict(q) for q in candidate_queries],
            approved_pois_by_id=approved_pois,
            route2_ai_proxy_approved=route2_ai_proxy_approved,
        )

    per_query_outcomes: dict[str, dict[str, Any]] = {}
    verified_count = 0
    provenance_verified_count = 0
    hold_count = 0

    for q in candidate_queries:
        qid = str(q["query_id"])
        qtext = str(q["query_text"])
        fam = str(q["query_family"])
        ans = str(q["pre_rank_answerability"])
        if q.get("question_origin") != "AI_GENERATED_NO_HUMAN_REVIEW" or q.get("human_ground_truth") is not False:
            raise ValueError(f"Route 2 requires question_origin='AI_GENERATED_NO_HUMAN_REVIEW' and human_ground_truth=False on {qid}")
        if q.get("creator_exposure_to_corpus") != "NO":
            raise ValueError(f"G2A-1 requires creator_exposure_to_corpus='NO' on {qid}")

        ngram_check = check_corpus_v_token_overlap(qtext, corpus_v_texts, ngram_size=8)
        if ngram_check["leak_detected"]:
            raise ValueError(f"G2A_CORPUS_V_8GRAM_LEAK on {qid}: {ngram_check['matched_ngram']!r}")

        if fam != "S5_UNANSWERABLE_OR_UNSTABLE" and LIVE_VOLATILITY_RE.search(qtext):
            raise ValueError(f"G2A_LIVE_FRESHNESS_CLAIM_FORBIDDEN_IN_S1_TO_S4 on {qid}")

        sv = source_verification_records.get(qid)
        if not isinstance(sv, Mapping):
            per_query_outcomes[qid] = {"verification_status": "HOLD_MISSING_SOURCE_RECORD"}
            hold_count += 1
            continue

        if fam != "S5_UNANSWERABLE_OR_UNSTABLE":
            if ans != "ANSWERABLE":
                raise ValueError(f"Stratum {fam} requires ANSWERABLE on {qid}")
            anchors = sv.get("evidence_anchors", [])
            if not isinstance(anchors, Sequence) or len(anchors) == 0:
                per_query_outcomes[qid] = {"verification_status": "HOLD_NO_ANCHOR"}
                hold_count += 1
                continue

            struct_ok = True
            struct_err: str | None = None
            for anc in anchors:
                did = str(anc["document_id"])
                if did not in docs_by_id:
                    struct_ok, struct_err = False, f"UNKNOWN_DOC:{did}"
                    break
                doc = docs_by_id[did]
                s_text = str(doc["canonical_text_S"])
                st = int(anc["s_char_start"])
                en = int(anc["s_char_end"])
                quote = str(anc["evidence_quote"])
                if not (0 <= st < en <= len(s_text)) or s_text[st:en] != quote:
                    struct_ok, struct_err = False, "CANONICAL_S_SUBSTRING_MISMATCH"
                    break
                if any(tok in quote for tok in PROHIBITED_ANCHOR_MARKERS):
                    struct_ok, struct_err = False, "PROHIBITED_AUDIT_OR_CONFLICT_MARKER_IN_ANCHOR"
                    break
                if doc.get("city") != q.get("target_city"):
                    struct_ok, struct_err = False, "CE9_CITY_MISMATCH"
                    break
                target_pids = q.get("target_poi_ids", [])
                if target_pids and doc.get("poi_id") not in set(target_pids):
                    struct_ok, struct_err = False, "CE9_POI_MISMATCH"
                    break

            if not struct_ok:
                per_query_outcomes[qid] = {"verification_status": "REJECTED_STRUCTURAL", "reason": struct_err}
                hold_count += 1
                continue

            if semantic_verifier_mode == "OFFLINE_NO_SEMANTIC_VERIFIER":
                per_query_outcomes[qid] = {
                    "verification_status": "ANCHOR_VERIFIED_SEMANTIC_UNVERIFIED",
                    "model_provenance_verified": False,
                    "blocking_reason": "ZH_SCI_01_REQUIRES_BLIND_SEMANTIC_VERIFIER_POST_ACTIVATION",
                }
                hold_count += 1
                continue

            verdict = sv.get("semantic_support_verdict")
            comp = sv.get("answer_completeness")
            if verdict != "ENTAILS_COMPLETE_ANSWER" or comp != "COMPLETE_DIRECT_ANSWER":
                per_query_outcomes[qid] = {
                    "verification_status": "UNCERTAIN_HOLD",
                    "model_provenance_verified": False,
                    "semantic_support_verdict": verdict,
                    "answer_completeness": comp,
                }
                hold_count += 1
                continue

            proof = sv.get("semantic_provenance_proof")
            if semantic_verifier_mode == "AUTHORIZED_INDEPENDENT_BLIND_MODEL":
                if not isinstance(proof, Mapping):
                    per_query_outcomes[qid] = {
                        "verification_status": "UNCERTAIN_HOLD",
                        "model_provenance_verified": False,
                        "blocking_reason": "MISSING_MODEL_BOUND_SEMANTIC_PROVENANCE_PROOF",
                    }
                    hold_count += 1
                    continue
                try:
                    prov_res = verify_g2a_semantic_provenance_proof(
                        proof=proof,
                        query_meta=q,
                        anchors=anchors,
                        docs_by_id=docs_by_id,
                        expected_verifier_family=families["verifier"],
                        expected_semantic_verdict=str(verdict),
                        expected_answer_completeness=str(comp),
                    )
                except (ValueError, PermissionError, KeyError, TypeError) as exc:
                    per_query_outcomes[qid] = {
                        "verification_status": "UNCERTAIN_HOLD",
                        "model_provenance_verified": False,
                        "blocking_reason": f"UNBOUND_SEMANTIC_PROVENANCE:{exc}",
                    }
                    hold_count += 1
                    continue
                per_query_outcomes[qid] = {
                    "verification_status": "VERIFIED_AS_PROXY",
                    "answerability_proxy": "SOURCE_ANCHORED_PROXY",
                    "model_provenance_verified": True,
                    "provenance": prov_res,
                }
                verified_count += 1
                provenance_verified_count += 1
            else:
                # SYNTHETIC_DECLARED_MOCK_TEST_ONLY: verify proof if attached, else honestly mark weaker unproven claim
                if isinstance(proof, Mapping):
                    try:
                        prov_res = verify_g2a_semantic_provenance_proof(
                            proof=proof,
                            query_meta=q,
                            anchors=anchors,
                            docs_by_id=docs_by_id,
                            expected_verifier_family=families["verifier"],
                            expected_semantic_verdict=str(verdict),
                            expected_answer_completeness=str(comp),
                        )
                    except (ValueError, PermissionError, KeyError, TypeError) as exc:
                        per_query_outcomes[qid] = {
                            "verification_status": "UNCERTAIN_HOLD",
                            "model_provenance_verified": False,
                            "blocking_reason": f"UNBOUND_SEMANTIC_PROVENANCE:{exc}",
                        }
                        hold_count += 1
                        continue
                    per_query_outcomes[qid] = {
                        "verification_status": "VERIFIED_AS_PROXY",
                        "answerability_proxy": "SOURCE_ANCHORED_PROXY",
                        "model_provenance_verified": True,
                        "provenance": prov_res,
                    }
                    provenance_verified_count += 1
                else:
                    per_query_outcomes[qid] = {
                        "verification_status": "VERIFIED_AS_PROXY",
                        "answerability_proxy": "SYNTHETIC_DECLARED_WEAKER_PROXY_UNPROVEN_MODEL",
                        "model_provenance_verified": False,
                    }
                verified_count += 1
        else:
            if ans != "UNANSWERABLE":
                raise ValueError(f"Stratum S5 requires UNANSWERABLE on {qid}")
            per_doc = sv.get("per_doc_outcomes", [])
            if len(per_doc) != len(docs_by_id):
                per_query_outcomes[qid] = {
                    "verification_status": "UNCERTAIN_HOLD",
                    "model_provenance_verified": False,
                    "reason": f"ZH_SCI_02_INCOMPLETE_DOC_AUDIT:{len(per_doc)}!={len(docs_by_id)}",
                }
                hold_count += 1
                continue
            seen_dids = {str(r["document_id"]) for r in per_doc}
            if seen_dids != set(docs_by_id.keys()):
                raise ValueError(f"ZH_SCI_02_DOC_SET_MISMATCH on {qid}")
            expected_audit_sha = compute_s5_snapshot_audit_sha256(
                query_id=qid,
                query_text=qtext,
                city=str(q["target_city"]),
                verifier_model_id=str(sv.get("verifier_model_id", "")),
                per_doc_outcomes=per_doc,
            )
            supplied_audit_sha = str(sv.get("audit_sha256", ""))
            if not hmac.compare_digest(expected_audit_sha, supplied_audit_sha):
                raise ValueError(f"ZH_SCI_02_AUDIT_SHA256_MISMATCH on {qid}")
            if sv.get("epistemic_scope") != "NOT_SUPPORTED_BY_FROZEN_137_DOC_SNAPSHOT_ONLY":
                raise ValueError(f"S5 must declare NOT_SUPPORTED_BY_FROZEN_137_DOC_SNAPSHOT_ONLY on {qid}")
            ambig = [r for r in per_doc if r.get("outcome") != "NO_SUPPORT_IN_CLOSED_SNAPSHOT"]
            if ambig or semantic_verifier_mode == "OFFLINE_NO_SEMANTIC_VERIFIER":
                per_query_outcomes[qid] = {
                    "verification_status": "UNCERTAIN_HOLD",
                    "model_provenance_verified": False,
                    "ambiguous_or_support_count": len(ambig),
                }
                hold_count += 1
            elif semantic_verifier_mode == "AUTHORIZED_INDEPENDENT_BLIND_MODEL":
                s5_ok = True
                s5_err = ""
                snap = str(sv.get("model_snapshot_id", "")).strip()
                if not snap or any(tok in snap.lower() for tok in ("placeholder", "unfrozen", "null", "fake")):
                    s5_ok, s5_err = False, "MISSING_OR_PLACEHOLDER_MODEL_SNAPSHOT_ID"
                else:
                    for r in per_doc:
                        did = str(r["document_id"])
                        doc = docs_by_id[did]
                        san_v = str(doc.get("sanitized_text_V", doc["canonical_text_S"]))
                        exp_v_sha = sha256_bytes(san_v.encode("utf-8"))
                        if r.get("sanitized_v_sha256") != exp_v_sha:
                            s5_ok, s5_err = False, f"S5_SANITIZED_V_SHA256_MISMATCH:{did}"
                            break
                        if r.get("blind_g3_rankings_excluded") is not True:
                            s5_ok, s5_err = False, f"S5_BLIND_G3_EXCLUSION_NOT_ATTESTED:{did}"
                            break
                        if not isinstance(r.get("wire_payload_sha256"), str) or not SHA256_HEX_RE.match(
                            str(r.get("wire_payload_sha256"))
                        ):
                            s5_ok, s5_err = False, f"S5_MISSING_WIRE_PAYLOAD_SHA256:{did}"
                            break
                        if not isinstance(r.get("raw_response_sha256"), str) or not SHA256_HEX_RE.match(
                            str(r.get("raw_response_sha256"))
                        ):
                            s5_ok, s5_err = False, f"S5_MISSING_RAW_RESPONSE_SHA256:{did}"
                            break
                if not s5_ok:
                    per_query_outcomes[qid] = {
                        "verification_status": "UNCERTAIN_HOLD",
                        "model_provenance_verified": False,
                        "blocking_reason": s5_err,
                    }
                    hold_count += 1
                else:
                    per_query_outcomes[qid] = {
                        "verification_status": "VERIFIED_AS_PROXY",
                        "answerability_proxy": "CLOSED_SNAPSHOT_UNSUPPORTED_PROXY",
                        "model_provenance_verified": True,
                        "model_snapshot_id": snap,
                    }
                    verified_count += 1
                    provenance_verified_count += 1
            else:
                has_s5_prov = all(
                    isinstance(r.get("sanitized_v_sha256"), str)
                    and isinstance(r.get("wire_payload_sha256"), str)
                    and isinstance(r.get("raw_response_sha256"), str)
                    for r in per_doc
                ) and bool(str(sv.get("model_snapshot_id", "")).strip())
                per_query_outcomes[qid] = {
                    "verification_status": "VERIFIED_AS_PROXY",
                    "answerability_proxy": (
                        "CLOSED_SNAPSHOT_UNSUPPORTED_PROXY"
                        if has_s5_prov
                        else "SYNTHETIC_DECLARED_WEAKER_PROXY_UNPROVEN_MODEL"
                    ),
                    "model_provenance_verified": has_s5_prov,
                }
                if has_s5_prov:
                    provenance_verified_count += 1
                verified_count += 1

    all_prov_verified = (
        hold_count == 0
        and verified_count == len(candidate_queries) > 0
        and provenance_verified_count == verified_count
    )
    return {
        "schema_version": "W07_G2A_ZERO_HUMAN_PROXY_VALIDATION_V2",
        "catalog_sha256": cat_sha,
        "total_queries": len(candidate_queries),
        "verified_as_proxy_count": verified_count,
        "model_provenance_verified_count": provenance_verified_count,
        "all_model_provenance_verified": all_prov_verified,
        "hold_or_rejected_count": hold_count,
        "all_verified_as_proxy": (hold_count == 0 and verified_count == len(candidate_queries) > 0),
        "semantic_verifier_mode": semantic_verifier_mode,
        "per_query_outcomes": per_query_outcomes,
    }


def _scan_forbidden_cloud_keys(obj: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            ks = str(k)
            if ks in FORBIDDEN_CLOUD_PAYLOAD_KEYS:
                hits.append(f"{path}.{ks}")
            hits.extend(_scan_forbidden_cloud_keys(v, f"{path}.{ks}"))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            hits.extend(_scan_forbidden_cloud_keys(item, f"{path}[{idx}]"))
    return hits


_SEALED_PROMPT_EXEMPT_RUBRIC_MARKERS: frozenset[str] = frozenset(
    {"[SOURCE_REPORTED_UNVERIFIED]", "[UNVERIFIED]", "[SUPPRESSED_FACT_CONFLICT]"}
)


def _strip_sealed_prompt_v11_from_payload(payload_obj: Any) -> tuple[Any, str | None]:
    """Extract & detach ONLY an exact cryptographic-SHA256-matched sealed Prompt v1.1 system channel."""
    if not isinstance(payload_obj, Mapping):
        return payload_obj, None

    def _matches_pinned(txt: Any) -> bool:
        return (
            isinstance(txt, str)
            and sha256_bytes(txt.encode("utf-8")) == PINNED_STAGE1_SYSTEM_PROMPT_V1_1_SHA256
        )

    out = dict(payload_obj)
    # 1. OpenAI count_tokens top-level `input: [{"role": "developer", "content": ...}, ...]`
    inp = out.get("input")
    if isinstance(inp, list) and len(inp) >= 2 and isinstance(inp[0], Mapping) and inp[0].get("role") == "developer":
        if _matches_pinned(inp[0].get("content")):
            out["input"] = [{"role": "developer", "content": "[PINNED_STAGE1_SYSTEM_PROMPT_V1_1]"}, *inp[1:]]
            return out, str(inp[0]["content"])
    # 2. OpenAI batch item `body.input`
    body = out.get("body")
    if isinstance(body, Mapping):
        b_inp = body.get("input")
        if (
            isinstance(b_inp, list)
            and len(b_inp) >= 2
            and isinstance(b_inp[0], Mapping)
            and b_inp[0].get("role") == "developer"
            and _matches_pinned(b_inp[0].get("content"))
        ):
            new_body = dict(body)
            new_body["input"] = [{"role": "developer", "content": "[PINNED_STAGE1_SYSTEM_PROMPT_V1_1]"}, *b_inp[1:]]
            out["body"] = new_body
            return out, str(b_inp[0]["content"])
    # 3. Anthropic top-level `system` or batch `params.system`
    if _matches_pinned(out.get("system")):
        sys_txt = str(out["system"])
        out["system"] = "[PINNED_STAGE1_SYSTEM_PROMPT_V1_1]"
        return out, sys_txt
    params = out.get("params")
    if isinstance(params, Mapping) and _matches_pinned(params.get("system")):
        new_params = dict(params)
        sys_txt = str(params["system"])
        new_params["system"] = "[PINNED_STAGE1_SYSTEM_PROMPT_V1_1]"
        out["params"] = new_params
        return out, sys_txt
    # 4. Google top-level `systemInstruction` or batch `request.systemInstruction`
    for container_key in (None, "request"):
        target = out if container_key is None else out.get(container_key)
        if not isinstance(target, Mapping):
            continue
        si = target.get("systemInstruction")
        if isinstance(si, Mapping) and isinstance(si.get("parts"), list) and len(si["parts"]) == 1:
            p0 = si["parts"][0]
            if isinstance(p0, Mapping) and _matches_pinned(p0.get("text")):
                sys_txt = str(p0["text"])
                new_si = {"parts": [{"text": "[PINNED_STAGE1_SYSTEM_PROMPT_V1_1]"}]}
                if container_key is None:
                    out["systemInstruction"] = new_si
                else:
                    new_sub = dict(target)
                    new_sub["systemInstruction"] = new_si
                    out[container_key] = new_sub
                return out, sys_txt
    return payload_obj, None


def assert_cloud_payload_v_boundary(
    payload_obj: Any,
    *,
    doc_record_for_leak_check: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail-closed outbound cloud firewall: ONLY Tier-T1 sanitized V allowed on cloud wires (NO S, R_AUDIT, T0, T2, PII)."""
    key_hits = _scan_forbidden_cloud_keys(payload_obj)
    if key_hits:
        raise PermissionError(f"CLOUD_DATA_BOUNDARY_FORBIDDEN_METADATA_KEYS: {key_hits[:5]}")

    sanitized_payload_obj, sealed_sys_txt = _strip_sealed_prompt_v11_from_payload(payload_obj)
    serialized_full = json.dumps(payload_obj, sort_keys=True, ensure_ascii=False)
    serialized = json.dumps(sanitized_payload_obj, sort_keys=True, ensure_ascii=False)
    low = serialized.lower()
    for marker in FORBIDDEN_CLOUD_TEXT_MARKERS:
        if marker.lower() in low:
            raise PermissionError(f"CLOUD_DATA_BOUNDARY_FORBIDDEN_MARKER: {marker!r}")

    if sealed_sys_txt is not None:
        sys_low = sealed_sys_txt.lower()
        for marker in FORBIDDEN_CLOUD_TEXT_MARKERS:
            if marker not in _SEALED_PROMPT_EXEMPT_RUBRIC_MARKERS and marker.lower() in sys_low:
                raise PermissionError(f"CLOUD_DATA_BOUNDARY_FORBIDDEN_MARKER: {marker!r}")

    email_hits = CLOUD_EMAIL_PII_RE.findall(serialized_full)
    if email_hits:
        raise PermissionError(f"CLOUD_DATA_BOUNDARY_PII_EMAIL_DETECTED: count={len(email_hits)}")

    fallback_at_hits = UNRESOLVED_AT_EMAIL_FALLBACK_RE.findall(serialized_full)
    if fallback_at_hits:
        raise PermissionError(
            f"CLOUD_DATA_BOUNDARY_UNRESOLVED_AT_EMAIL_CANDIDATE: count={len(fallback_at_hits)}"
        )

    if doc_record_for_leak_check is not None:
        raw_s = doc_record_for_leak_check.get("canonical_text_S")
        san_v = doc_record_for_leak_check.get("sanitized_text_V", doc_record_for_leak_check.get("view_V"))
        if isinstance(raw_s, str) and isinstance(san_v, str) and raw_s != san_v and raw_s in serialized_full:
            raise PermissionError("CLOUD_DATA_BOUNDARY_RAW_CANONICAL_S_DETECTED")
        rem_spans = doc_record_for_leak_check.get("removed_r_audit", [])
        if isinstance(raw_s, str) and isinstance(rem_spans, Sequence):
            for span in rem_spans:
                if isinstance(span, Sequence) and len(span) == 2:
                    rs, re_ = int(span[0]), int(span[1])
                    deleted_slice = raw_s[rs:re_]
                    if deleted_slice and deleted_slice in serialized_full:
                        raise PermissionError("CLOUD_DATA_BOUNDARY_EXCISED_R_AUDIT_SLICE_LEAKED")
        for sensitive_id_key in ("document_id", "poi_id", "source_url", "source_lineage_id"):
            val = doc_record_for_leak_check.get(sensitive_id_key)
            if isinstance(val, str) and len(val) >= 8 and val in serialized_full:
                raise PermissionError(f"CLOUD_DATA_BOUNDARY_SENSITIVE_ID_LEAKED:{sensitive_id_key}")

    return {"cloud_boundary_clean": True, "payload_sha256": sha256_bytes(serialized_full.encode("utf-8"))}


def build_sanitized_v_cloud_request_payload(
    *,
    packet_item_uuid: str,
    query_text: str,
    sanitized_text_V: str,
    run_nonce: str,
    prompt_order: str = "PROMPT_ORDER_CANONICAL",
    doc_record_for_leak_check: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct outbound cloud wire payload strictly from sanitized V, redacting delimiter injections & PII emails reversibly."""
    if not re.fullmatch(r"[0-9a-f]{32}", run_nonce):
        raise ValueError("run_nonce must be exact 32 lowercase hex chars")
    if prompt_order not in ("PROMPT_ORDER_CANONICAL", "PROMPT_ORDER_SWAPPED"):
        raise ValueError(f"Invalid prompt_order: {prompt_order!r}")
    if any(tok in sanitized_text_V for tok in PROHIBITED_ANCHOR_MARKERS[:4]):
        raise PermissionError("CLOUD_DATA_BOUNDARY_UNSANITIZED_MARKERS_IN_V_INPUT")

    open_tag = f"<UNTRUSTED_CORPUS_DOCUMENT_{run_nonce}>"
    close_tag = f"</UNTRUSTED_CORPUS_DOCUMENT_{run_nonce}>"
    escaped_token = "[ESCAPED_DELIMITER]"
    redacted_email_token = "[REDACTED_EMAIL]"
    wire_filter_re = re.compile(
        f"(?P<delim>{re.escape(open_tag)}|{re.escape(close_tag)})|(?P<email>{CLOUD_EMAIL_PII_RE.pattern})"
    )

    safe_parts: list[str] = []
    safe_to_v_segments: list[tuple[int, int, int, int]] = []
    escaped_delimiters: list[dict[str, Any]] = []
    redacted_emails: list[dict[str, Any]] = []
    v_pos = 0
    s_pos = 0
    for m in wire_filter_re.finditer(sanitized_text_V):
        if m.start() > v_pos:
            chunk = sanitized_text_V[v_pos:m.start()]
            safe_parts.append(chunk)
            safe_to_v_segments.append((s_pos, s_pos + len(chunk), v_pos, m.start()))
            s_pos += len(chunk)
        if m.lastgroup == "delim":
            safe_parts.append(escaped_token)
            escaped_delimiters.append({"safe_span": [s_pos, s_pos + len(escaped_token)], "v_span": [m.start(), m.end()]})
            s_pos += len(escaped_token)
        else:
            safe_parts.append(redacted_email_token)
            redacted_emails.append({"safe_span": [s_pos, s_pos + len(redacted_email_token)], "v_span": [m.start(), m.end()]})
            s_pos += len(redacted_email_token)
        v_pos = m.end()
    if v_pos < len(sanitized_text_V):
        tail = sanitized_text_V[v_pos:]
        safe_parts.append(tail)
        safe_to_v_segments.append((s_pos, s_pos + len(tail), v_pos, len(sanitized_text_V)))
    safe_doc_v = "".join(safe_parts)

    if prompt_order == "PROMPT_ORDER_CANONICAL":
        wire_user_prompt = (
            f"PACKET_ITEM_UUID: {packet_item_uuid}\n"
            f"QUERY_TEXT: {query_text}\n"
            f"{open_tag}\n{safe_doc_v}\n{close_tag}"
        )
    else:
        wire_user_prompt = (
            f"PACKET_ITEM_UUID: {packet_item_uuid}\n"
            f"{open_tag}\n{safe_doc_v}\n{close_tag}\n"
            f"QUERY_TEXT: {query_text}"
        )

    wire_obj = {
        "packet_item_uuid": packet_item_uuid,
        "prompt_order": prompt_order,
        "wire_user_prompt": wire_user_prompt,
    }
    boundary_check = assert_cloud_payload_v_boundary(wire_obj, doc_record_for_leak_check=doc_record_for_leak_check)
    return {
        **wire_obj,
        "safe_doc_v": safe_doc_v,
        "safe_to_v_segments": safe_to_v_segments,
        "escaped_delimiters": escaped_delimiters,
        "redacted_emails": redacted_emails,
        "boundary_verified": boundary_check["cloud_boundary_clean"],
        "wire_payload_sha256": boundary_check["payload_sha256"],
    }


def _project_half_open_interval(start: int, end: int, segs: Sequence[tuple[int, int, int, int]]) -> tuple[int, int] | None:
    if not (0 <= start < end):
        return None
    for src_a, src_b, dst_a, dst_b in segs:
        if src_a <= start and end <= src_b:
            delta_s = start - src_a
            delta_e = end - src_a
            if (dst_a + delta_e) <= dst_b:
                return dst_a + delta_s, dst_a + delta_e
    return None


def project_cloud_quote_locally_to_canonical_s(
    *,
    cloud_response: Mapping[str, Any],
    safe_doc_v: str,
    safe_to_v_segments: Sequence[tuple[int, int, int, int]],
    doc_sanitized_V: str,
    doc_canonical_S: str,
    doc_v_to_s_segments: Sequence[tuple[int, int, int, int]],
    doc_removed_r_audit: Sequence[tuple[int, int]],
    doc_meta: Mapping[str, Any],
    query_meta: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify & project cloud response spans strictly locally from safe_doc_v -> V -> canonical S."""
    fake_doc_local = {
        "canonical_text_S": doc_canonical_S,
        "city": doc_meta.get("city"),
        "poi_id": doc_meta.get("poi_id"),
    }
    grade = cloud_response.get("grade")
    if grade in ("REL_0", "NA"):
        return validate_judge_response(
            json.dumps(dict(cloud_response), ensure_ascii=False),
            fake_doc_local,
            list(doc_removed_r_audit),
            dict(query_meta),
        )
    if grade not in ("REL_1", "REL_2"):
        return {"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": f"INVALID_GRADE:{grade!r}"}

    quote = cloud_response.get("evidence_quote")
    c_start = cloud_response.get("char_start")
    c_end = cloud_response.get("char_end")
    if not isinstance(quote, str) or type(c_start) is not int or type(c_end) is not int:
        return {"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "MISSING_QUOTE_OR_OFFSETS"}
    if not (0 <= c_start < c_end <= len(safe_doc_v)) or safe_doc_v[c_start:c_end] != quote:
        return {"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "SAFE_DOC_V_QUOTE_MISMATCH"}

    v_span = _project_half_open_interval(c_start, c_end, safe_to_v_segments)
    if v_span is None or doc_sanitized_V[v_span[0] : v_span[1]] != quote:
        return {"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "SPAN_STRADDLES_ESCAPED_DELIMITER"}

    s_span = _project_half_open_interval(v_span[0], v_span[1], doc_v_to_s_segments)
    if s_span is None:
        return {"state": "ERROR", "confirmed_gain": 0, "max_admissible_gain": 3, "error_code": "SPAN_STRADDLES_EXCISED_R_AUDIT_TAG"}

    projected_resp = {
        "grade": grade,
        "evidence_quote": quote,
        "char_start": s_span[0],
        "char_end": s_span[1],
    }
    return validate_judge_response(
        json.dumps(projected_resp, ensure_ascii=False),
        fake_doc_local,
        list(doc_removed_r_audit),
        dict(query_meta),
    )


def build_g2a_semantic_provenance_proof(
    *,
    packet_item_uuid: str,
    run_nonce: str,
    query_meta: Mapping[str, Any],
    anchor_document_id: str,
    doc_record: Mapping[str, Any],
    verifier_model_id: str,
    model_snapshot_id: str,
    verifier_model_family: str,
    raw_cloud_response: Mapping[str, Any],
    prompt_order: str = "PROMPT_ORDER_CANONICAL",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Construct cryptographically bound G2A-2 semantic provenance proof & verified local S anchor."""
    canon_s = str(doc_record["canonical_text_S"])
    san_v = str(doc_record.get("sanitized_text_V", canon_s))
    v_to_s = list(doc_record.get("v_to_s_segments") or [(0, len(san_v), 0, len(canon_s))])
    rem = list(doc_record.get("removed_r_audit", []))
    wire = build_sanitized_v_cloud_request_payload(
        packet_item_uuid=packet_item_uuid,
        query_text=str(query_meta["query_text"]),
        sanitized_text_V=san_v,
        run_nonce=run_nonce,
        prompt_order=prompt_order,
        doc_record_for_leak_check=doc_record,
    )
    raw_resp_dict = dict(raw_cloud_response)
    quote = str(raw_resp_dict["evidence_quote"])
    c_start = int(raw_resp_dict["char_start"])
    c_end = int(raw_resp_dict["char_end"])
    v_span = _project_half_open_interval(c_start, c_end, wire["safe_to_v_segments"])
    if v_span is None:
        raise ValueError("G2A2_QUOTE_STRADDLES_ESCAPED_DELIMITER")
    s_span = _project_half_open_interval(v_span[0], v_span[1], v_to_s)
    if s_span is None:
        raise ValueError("G2A2_QUOTE_STRADDLES_EXCISED_R_AUDIT")
    if canon_s[s_span[0] : s_span[1]] != quote:
        raise ValueError("G2A2_LOCAL_CANONICAL_S_PROJECTION_MISMATCH")

    local_proj = project_cloud_quote_locally_to_canonical_s(
        cloud_response={"grade": "REL_2", "evidence_quote": quote, "char_start": c_start, "char_end": c_end},
        safe_doc_v=wire["safe_doc_v"],
        safe_to_v_segments=wire["safe_to_v_segments"],
        doc_sanitized_V=san_v,
        doc_canonical_S=canon_s,
        doc_v_to_s_segments=v_to_s,
        doc_removed_r_audit=rem,
        doc_meta={"city": doc_record.get("city"), "poi_id": doc_record.get("poi_id")},
        query_meta=query_meta,
    )
    if local_proj["state"] != "REL_2":
        raise ValueError(f"G2A2_LOCAL_PROJECTION_REJECTED:{local_proj.get('error_code')}")

    proof = {
        "schema_version": "W07_G2A2_SEMANTIC_PROVENANCE_PROOF_V1",
        "verifier_model_id": verifier_model_id,
        "model_snapshot_id": model_snapshot_id,
        "model_family": verifier_model_family,
        "blind_g3_rankings_excluded": True,
        "packet_item_uuid": packet_item_uuid,
        "run_nonce": run_nonce,
        "prompt_order": prompt_order,
        "anchor_document_id": anchor_document_id,
        "sanitized_v_sha256": sha256_bytes(san_v.encode("utf-8")),
        "wire_payload_sha256": wire["wire_payload_sha256"],
        "wire_user_prompt": wire["wire_user_prompt"],
        "raw_response_sha256": sha256_bytes(
            json.dumps(raw_resp_dict, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        "raw_cloud_response": raw_resp_dict,
    }
    anchor = {
        "document_id": anchor_document_id,
        "s_char_start": s_span[0],
        "s_char_end": s_span[1],
        "evidence_quote": quote,
    }
    return proof, anchor


def verify_g2a_semantic_provenance_proof(
    *,
    proof: Mapping[str, Any],
    query_meta: Mapping[str, Any],
    anchors: Sequence[Mapping[str, Any]],
    docs_by_id: Mapping[str, Mapping[str, Any]],
    expected_verifier_family: str,
    expected_semantic_verdict: str,
    expected_answer_completeness: str,
) -> dict[str, Any]:
    """Verify G2A-2 semantic verdict is bound to sanitized V wire payload, snapshot, cloud response, and local S projection."""
    if not isinstance(proof, Mapping):
        raise ValueError("G2A2_PROOF_MUST_BE_MAPPING")
    if proof.get("blind_g3_rankings_excluded") is not True:
        raise PermissionError("G2A2_BLIND_G3_EXCLUSION_NOT_ATTESTED")

    snap = str(proof.get("model_snapshot_id", "")).strip()
    vid = str(proof.get("verifier_model_id", "")).strip()
    if not vid or not snap or any(tok in snap.lower() for tok in ("placeholder", "unfrozen", "null", "fake")):
        raise ValueError("G2A2_MISSING_OR_PLACEHOLDER_MODEL_SNAPSHOT_ID")
    mfam = str(proof.get("model_family", "")).strip().lower()
    if not mfam or mfam != expected_verifier_family.strip().lower():
        raise ValueError(f"G2A2_VERIFIER_FAMILY_MISMATCH:{mfam!r}!={expected_verifier_family!r}")

    anchor_did = str(proof.get("anchor_document_id", ""))
    matching_anchors = [a for a in anchors if str(a.get("document_id")) == anchor_did]
    if not matching_anchors or anchor_did not in docs_by_id:
        raise ValueError(f"G2A2_UNKNOWN_OR_UNLINKED_ANCHOR_DOC:{anchor_did!r}")
    anchor = matching_anchors[0]
    doc = docs_by_id[anchor_did]

    canon_s = str(doc["canonical_text_S"])
    san_v = str(doc.get("sanitized_text_V", canon_s))
    v_to_s = list(doc.get("v_to_s_segments") or ([(0, len(san_v), 0, len(canon_s))] if san_v == canon_s else []))
    if not v_to_s:
        raise ValueError("G2A2_MISSING_V_TO_S_SEGMENTS_FOR_SANITIZED_DOC")
    rem = list(doc.get("removed_r_audit", []))

    exp_v_sha = sha256_bytes(san_v.encode("utf-8"))
    sup_v_sha = str(proof.get("sanitized_v_sha256", ""))
    if not hmac.compare_digest(exp_v_sha, sup_v_sha):
        raise ValueError("G2A2_SANITIZED_V_SHA256_MISMATCH")

    rebuilt_wire = build_sanitized_v_cloud_request_payload(
        packet_item_uuid=str(proof.get("packet_item_uuid", "")),
        query_text=str(query_meta["query_text"]),
        sanitized_text_V=san_v,
        run_nonce=str(proof.get("run_nonce", "")),
        prompt_order=str(proof.get("prompt_order", "PROMPT_ORDER_CANONICAL")),
        doc_record_for_leak_check=doc,
    )
    sup_wire_sha = str(proof.get("wire_payload_sha256", ""))
    if not hmac.compare_digest(rebuilt_wire["wire_payload_sha256"], sup_wire_sha):
        raise ValueError("G2A2_WIRE_PAYLOAD_SHA256_MISMATCH")
    if "wire_user_prompt" in proof and proof["wire_user_prompt"] != rebuilt_wire["wire_user_prompt"]:
        raise ValueError("G2A2_WIRE_USER_PROMPT_TEXT_MISMATCH")

    raw_resp = proof.get("raw_cloud_response")
    if not isinstance(raw_resp, Mapping):
        raise ValueError("G2A2_MISSING_RAW_CLOUD_RESPONSE")
    recomp_resp_sha = sha256_bytes(
        json.dumps(dict(raw_resp), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    if not hmac.compare_digest(recomp_resp_sha, str(proof.get("raw_response_sha256", ""))):
        raise ValueError("G2A2_RAW_RESPONSE_SHA256_MISMATCH")
    if (
        raw_resp.get("semantic_support_verdict") != expected_semantic_verdict
        or raw_resp.get("answer_completeness") != expected_answer_completeness
    ):
        raise ValueError("G2A2_RESPONSE_VERDICT_MISMATCH_WITH_RECORD")

    quote = raw_resp.get("evidence_quote")
    c_start = raw_resp.get("char_start")
    c_end = raw_resp.get("char_end")
    if not isinstance(quote, str) or type(c_start) is not int or type(c_end) is not int:
        raise ValueError("G2A2_RESPONSE_MISSING_QUOTE_OR_OFFSETS")
    v_span = _project_half_open_interval(c_start, c_end, rebuilt_wire["safe_to_v_segments"])
    if v_span is None:
        raise ValueError("G2A2_RESPONSE_STRADDLES_ESCAPED_DELIMITER")
    s_span = _project_half_open_interval(v_span[0], v_span[1], v_to_s)
    if s_span is None:
        raise ValueError("G2A2_RESPONSE_STRADDLES_EXCISED_R_AUDIT")
    if (s_span[0], s_span[1]) != (int(anchor["s_char_start"]), int(anchor["s_char_end"])) or quote != str(
        anchor["evidence_quote"]
    ):
        raise ValueError("G2A2_PROJECTED_SPAN_MISMATCH_WITH_ANCHOR")

    local_proj = project_cloud_quote_locally_to_canonical_s(
        cloud_response={"grade": "REL_2", "evidence_quote": quote, "char_start": c_start, "char_end": c_end},
        safe_doc_v=rebuilt_wire["safe_doc_v"],
        safe_to_v_segments=rebuilt_wire["safe_to_v_segments"],
        doc_sanitized_V=san_v,
        doc_canonical_S=canon_s,
        doc_v_to_s_segments=v_to_s,
        doc_removed_r_audit=rem,
        doc_meta={"city": doc.get("city"), "poi_id": doc.get("poi_id")},
        query_meta=query_meta,
    )
    if local_proj["state"] != "REL_2":
        raise ValueError(f"G2A2_LOCAL_PROJECTION_FAILED:{local_proj.get('error_code')}")

    return {
        "provenance_verified": True,
        "verifier_model_id": vid,
        "model_snapshot_id": snap,
        "sanitized_v_sha256": exp_v_sha,
        "wire_payload_sha256": sup_wire_sha,
        "raw_response_sha256": recomp_resp_sha,
        "projected_s_span": [s_span[0], s_span[1]],
    }


def canonical_route2_signing_bytes(domain_tag: bytes, payload: Mapping[str, Any]) -> bytes:
    """Domain-separated canonical UTF-8 JSON payload bytes for read-only Ed25519 verification."""
    unsigned = {
        k: v
        for k, v in payload.items()
        if k not in ("owner_detached_signature_hex", "auditor_detached_signature_hex", "signature_hex")
    }
    body = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return domain_tag + body


_ED25519_P = (1 << 255) - 19
_ED25519_L = (1 << 252) + 27742317777372353535851937790883648493
_ED25519_D = (-121665 * pow(121666, _ED25519_P - 2, _ED25519_P)) % _ED25519_P
_ED25519_D2 = (2 * _ED25519_D) % _ED25519_P
_ED25519_SQRT_M1 = pow(2, (_ED25519_P - 1) // 4, _ED25519_P)
_ED25519_NEUTRAL = (0, 1, 1, 0)


def _ed25519_recover_x(y: int, sign: int) -> int | None:
    """Recover affine x on Edwards25519 from y and sign bit per RFC 8032 Section 5.1.3."""
    if y >= _ED25519_P:
        return None
    y2 = (y * y) % _ED25519_P
    u = (y2 - 1) % _ED25519_P
    v = (_ED25519_D * y2 + 1) % _ED25519_P
    v3 = pow(v, 3, _ED25519_P)
    v7 = pow(v, 7, _ED25519_P)
    x = (u * v3 * pow((u * v7) % _ED25519_P, (_ED25519_P - 5) // 8, _ED25519_P)) % _ED25519_P
    vxx = (v * x * x) % _ED25519_P
    if vxx == u:
        pass
    elif vxx == (-u) % _ED25519_P:
        x = (x * _ED25519_SQRT_M1) % _ED25519_P
    else:
        return None
    if x == 0 and sign == 1:
        return None
    if (x & 1) != sign:
        x = _ED25519_P - x
    return x


def _ed25519_decompress_point(encoded: bytes) -> tuple[int, int, int, int] | None:
    if len(encoded) != 32:
        return None
    raw = int.from_bytes(encoded, "little")
    sign = (raw >> 255) & 1
    y = raw & ((1 << 255) - 1)
    x = _ed25519_recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, (x * y) % _ED25519_P)


def _ed25519_point_add(
    p1: tuple[int, int, int, int], p2: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    """Unified extended twisted Edwards point addition."""
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = ((y1 - x1) * (y2 - x2)) % _ED25519_P
    b = ((y1 + x1) * (y2 + x2)) % _ED25519_P
    c = (t1 * _ED25519_D2 * t2) % _ED25519_P
    d = (z1 * 2 * z2) % _ED25519_P
    e = (b - a) % _ED25519_P
    f = (d - c) % _ED25519_P
    g = (d + c) % _ED25519_P
    h = (b + a) % _ED25519_P
    return ((e * f) % _ED25519_P, (g * h) % _ED25519_P, (f * g) % _ED25519_P, (e * h) % _ED25519_P)


def _ed25519_scalar_mul(scalar: int, pt: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    acc = _ED25519_NEUTRAL
    cur = pt
    k = scalar
    while k > 0:
        if k & 1:
            acc = _ed25519_point_add(acc, cur)
        cur = _ed25519_point_add(cur, cur)
        k >>= 1
    return acc


def _ed25519_point_equal(p1: tuple[int, int, int, int], p2: tuple[int, int, int, int]) -> bool:
    return (p1[0] * p2[2] - p2[0] * p1[2]) % _ED25519_P == 0 and (
        p1[1] * p2[2] - p2[1] * p1[2]
    ) % _ED25519_P == 0


def _ed25519_base_point() -> tuple[int, int, int, int]:
    by = (4 * pow(5, _ED25519_P - 2, _ED25519_P)) % _ED25519_P
    bx = _ed25519_recover_x(by, 0)
    assert bx is not None
    return (bx, by, 1, (bx * by) % _ED25519_P)


_ED25519_B = _ed25519_base_point()


def _ed25519_verify_pure_python(*, pubkey_bytes: bytes, signature_bytes: bytes, message: bytes) -> bool:
    """Verify RFC 8032 Ed25519 signature using pure Python stdlib arithmetic (zero external deps)."""
    if len(pubkey_bytes) != 32 or len(signature_bytes) != 64:
        return False
    pt_a = _ed25519_decompress_point(pubkey_bytes)
    pt_r = _ed25519_decompress_point(signature_bytes[:32])
    if pt_a is None or pt_r is None:
        return False
    # Reject identity / low-order public keys for defense in depth.
    if _ed25519_point_equal(_ed25519_scalar_mul(8, pt_a), _ED25519_NEUTRAL):
        return False
    s_int = int.from_bytes(signature_bytes[32:], "little")
    if not (0 <= s_int < _ED25519_L):
        return False
    h_bytes = hashlib.sha512(signature_bytes[:32] + pubkey_bytes + message).digest()
    k_int = int.from_bytes(h_bytes, "little") % _ED25519_L
    lhs = _ed25519_scalar_mul(8, _ed25519_scalar_mul(s_int, _ED25519_B))
    rhs = _ed25519_scalar_mul(8, _ed25519_point_add(pt_r, _ed25519_scalar_mul(k_int, pt_a)))
    return _ed25519_point_equal(lhs, rhs)


def _verify_route2_ed25519_signature(*, pubkey_hex: str, signature_hex: str, message: bytes) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", pubkey_hex) or pubkey_hex in FORBIDDEN_TOY_HASHES:
        raise PermissionError("ROUTE2_INVALID_TRUSTED_PUBKEY_HEX")
    if not re.fullmatch(r"[0-9a-f]{128}", signature_hex):
        raise PermissionError("ROUTE2_INVALID_DETACHED_SIGNATURE_FORMAT")
    if not _ed25519_verify_pure_python(
        pubkey_bytes=bytes.fromhex(pubkey_hex),
        signature_bytes=bytes.fromhex(signature_hex),
        message=message,
    ):
        raise PermissionError("ROUTE2_ED25519_SIGNATURE_VERIFICATION_FAILED")


_ISO8601_UTC_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_AUDITOR_VERDICT_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "amendment_id",
        "verdict",
        "mode_label",
        "authorized_stage",
        "scope",
        "pre_preflight_probe_decision",
        "stage1_dev_canary_decision",
        "final_50_authorized",
        "target_zip_sha256",
        "bound_preflight_artifacts",
    }
)
_BOUND_PREFLIGHT_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "raw_probe_transcript_sha256",
        "provider_preflight_status_sha256",
        "rate_evidence_sha256",
        "phase1_auditor_verdict_sha256",
    }
)


def _no_duplicate_keys_object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for k, v in pairs:
        if k in obj:
            raise PermissionError(f"AUDITOR_VERDICT_JSON_DUPLICATE_KEY:{k!r}")
        obj[k] = v
    return obj


def _reject_nonstandard_json_constant(token: str) -> Any:
    raise PermissionError(f"AUDITOR_VERDICT_JSON_FORBIDDEN_CONSTANT:{token!r}")


def verify_ai_audit_text_report_artifact(
    report_path: Path,
    *,
    expected_report_sha256: str | None = None,
    expected_target_zip_sha256: str | None = None,
    expected_gate_phase: str = "PRE_PREFLIGHT_PROBE_ONLY",
    expected_bound_preflight: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Fail-closed strict JSON-only parser/validator for AI_AUDIT_TEXT_OWNER_ATTESTED verdict artifacts."""
    if expected_gate_phase not in ALLOWED_ACTIVATION_GATE_PHASES:
        raise ValueError(f"INVALID_GATE_PHASE:{expected_gate_phase!r}")
    if not isinstance(report_path, Path) or not report_path.is_file():
        raise PermissionError(f"MISSING_AUDITOR_REPORT_ARTIFACT_FILE:{report_path}")
    _assert_not_symlink_or_reparse(report_path)

    if report_path.suffix.lower() != ".json":
        raise PermissionError(f"AUDITOR_VERDICT_ARTIFACT_MUST_BE_STRICT_JSON_FILE:{report_path.name}")

    raw_bytes = report_path.read_bytes()
    actual_sha = sha256_bytes(raw_bytes)
    if (
        actual_sha in FORBIDDEN_TOY_HASHES
        or actual_sha in FORBIDDEN_PRIOR_PRE_AMENDMENT_AUDIT_SHA256S
    ):
        raise PermissionError("INVALID_OR_PRE_AMENDMENT_AUDITOR_REPORT_SHA256")
    if expected_report_sha256 is not None:
        if not SHA256_HEX_RE.match(expected_report_sha256) or not hmac.compare_digest(actual_sha, expected_report_sha256):
            raise PermissionError("AUDITOR_REPORT_ARTIFACT_FILE_SHA256_MISMATCH")

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PermissionError("AUDITOR_VERDICT_ARTIFACT_MUST_BE_STRICT_JSON") from exc

    stripped = text.strip()
    if not stripped.startswith("{") or not stripped.endswith("}"):
        raise PermissionError("AUDITOR_VERDICT_ARTIFACT_MUST_BE_STRICT_JSON")

    try:
        doc = json.loads(
            stripped,
            object_pairs_hook=_no_duplicate_keys_object_pairs_hook,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise PermissionError("AUDITOR_VERDICT_ARTIFACT_MUST_BE_STRICT_JSON") from exc

    if type(doc) is not dict:
        raise PermissionError("AUDITOR_VERDICT_ARTIFACT_MUST_BE_JSON_OBJECT")

    keys = set(doc.keys())
    if keys != _AUDITOR_VERDICT_REQUIRED_KEYS:
        missing = sorted(_AUDITOR_VERDICT_REQUIRED_KEYS - keys)
        extra = sorted(keys - _AUDITOR_VERDICT_REQUIRED_KEYS)
        raise PermissionError(f"AUDITOR_VERDICT_SCHEMA_KEY_MISMATCH:missing={missing}:extra={extra}")

    if doc["schema_version"] != "GOMATE_W07_INDEPENDENT_AUDIT_VERDICT_V1":
        raise PermissionError(f"AUDITOR_VERDICT_SCHEMA_VERSION_MISMATCH:{doc['schema_version']!r}")
    if doc["amendment_id"] != ROUTE2_AMENDMENT_02_ID:
        raise PermissionError(f"AI_AUDIT_REPORT_AMENDMENT_ID_MISMATCH:{doc['amendment_id']!r}")
    if doc["mode_label"] != AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER:
        raise PermissionError(f"AI_AUDIT_REPORT_MODE_LABEL_MISMATCH:{doc['mode_label']!r}")

    verdict = doc["verdict"]
    if type(verdict) is not str or verdict not in ("PASS", "SCOPED_PASS"):
        raise PermissionError(f"AI_AUDIT_REPORT_NON_PASS_VERDICT:{verdict!r}")

    if type(doc["final_50_authorized"]) is not bool or doc["final_50_authorized"] is not False:
        raise PermissionError("AI_AUDIT_REPORT_CANNOT_AUTHORIZE_FINAL50")

    auth_stage = doc["authorized_stage"]
    if type(auth_stage) is not str or auth_stage not in ("PRE_PREFLIGHT_PROBE_ONLY", "STAGE1_DEV_CANARY_ONLY"):
        raise PermissionError(f"AI_AUDIT_REPORT_INVALID_AUTHORIZED_STAGE:{auth_stage!r}")

    scope = doc["scope"]
    if type(scope) is not list or any(type(item) is not str for item in scope) or scope != [auth_stage]:
        raise PermissionError(f"AI_AUDIT_REPORT_INVALID_SCOPE:{scope!r}")

    if doc["pre_preflight_probe_decision"] != "GO":
        raise PermissionError(f"AI_AUDIT_REPORT_PREFLIGHT_NOT_GO:{doc['pre_preflight_probe_decision']!r}")

    expected_s1_decision = "HOLD" if auth_stage == "PRE_PREFLIGHT_PROBE_ONLY" else "GO"
    if doc["stage1_dev_canary_decision"] != expected_s1_decision:
        raise PermissionError(
            f"AI_AUDIT_REPORT_STAGE1_CANARY_DECISION_MISMATCH:stage={auth_stage}:got={doc['stage1_dev_canary_decision']!r}"
        )

    target_zip_sha = doc["target_zip_sha256"]
    if (
        type(target_zip_sha) is not str
        or not SHA256_HEX_RE.match(target_zip_sha)
        or target_zip_sha in FORBIDDEN_TOY_HASHES
        or target_zip_sha in REJECTED_PRIOR_AUDIT_ZIP_SHA256S
    ):
        raise PermissionError(f"AI_AUDIT_REPORT_INVALID_OR_REJECTED_TARGET_ZIP_SHA256:{target_zip_sha!r}")
    if expected_target_zip_sha256 is not None and not hmac.compare_digest(target_zip_sha, expected_target_zip_sha256):
        raise PermissionError("AI_AUDIT_REPORT_TARGET_ZIP_SHA256_MISMATCH")

    bound = doc["bound_preflight_artifacts"]
    bound_out: dict[str, str] | None = None
    if auth_stage == "PRE_PREFLIGHT_PROBE_ONLY":
        if bound is not None:
            raise PermissionError("AI_AUDIT_PHASE1_FORBIDS_BOUND_PREFLIGHT_ARTIFACTS")
    else:
        if type(bound) is not dict or set(bound.keys()) != _BOUND_PREFLIGHT_REQUIRED_KEYS:
            raise PermissionError("AI_AUDIT_PHASE2_REQUIRES_EXACT_BOUND_PREFLIGHT_ARTIFACTS")
        bound_out = {}
        for bk in sorted(_BOUND_PREFLIGHT_REQUIRED_KEYS):
            bval = bound[bk]
            if type(bval) is not str or not SHA256_HEX_RE.match(bval) or bval in FORBIDDEN_TOY_HASHES:
                raise PermissionError(f"AI_AUDIT_PHASE2_INVALID_BOUND_SHA256:{bk}")
            bound_out[bk] = bval
        p1_sha = bound_out["phase1_auditor_verdict_sha256"]
        if p1_sha in FORBIDDEN_PRIOR_PRE_AMENDMENT_AUDIT_SHA256S or hmac.compare_digest(p1_sha, actual_sha):
            raise PermissionError("AI_AUDIT_PHASE2_INVALID_PHASE1_VERDICT_REFERENCE")

    required_stage = "PRE_PREFLIGHT_PROBE_ONLY" if expected_gate_phase == "PRE_PREFLIGHT_PROBE_ONLY" else "STAGE1_DEV_CANARY_ONLY"
    if auth_stage != required_stage:
        raise PermissionError(f"AI_AUDIT_REPORT_STAGE_MISMATCH:expected={required_stage}:got={auth_stage}")

    if auth_stage == "STAGE1_DEV_CANARY_ONLY" and expected_bound_preflight is not None:
        assert bound_out is not None
        for bk in sorted(_BOUND_PREFLIGHT_REQUIRED_KEYS):
            exp_val = expected_bound_preflight.get(bk)
            if exp_val is not None and not hmac.compare_digest(bound_out[bk], str(exp_val)):
                raise PermissionError(f"AI_AUDIT_REPORT_BOUND_PREFLIGHT_MISMATCH:{bk}")

    return {
        "report_sha256": actual_sha,
        "verdict": verdict,
        "amendment_id": ROUTE2_AMENDMENT_02_ID,
        "mode_label": AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER,
        "authorized_stage": auth_stage,
        "scope": scope,
        "pre_preflight_probe_decision": "GO",
        "stage1_dev_canary_decision": expected_s1_decision,
        "target_zip_sha256": target_zip_sha,
        "bound_preflight_artifacts": bound_out,
    }


def verify_stage1_rate_evidence_artifact(
    rate_evidence_path: Path,
    *,
    expected_judge_snapshots: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Verify timestamped Owner-accepted provider rate source receipt before authorizing STAGE1_LIVE."""
    if not isinstance(rate_evidence_path, Path) or not rate_evidence_path.is_file():
        raise PermissionError(f"MISSING_STAGE1_RATE_EVIDENCE_FILE:{rate_evidence_path}")
    _assert_not_symlink_or_reparse(rate_evidence_path)

    raw_bytes = rate_evidence_path.read_bytes()
    actual_sha = sha256_bytes(raw_bytes)
    doc = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(doc, Mapping) or doc.get("schema_version") != "GOMATE_W07_PROVIDER_RATE_EVIDENCE_V1":
        raise PermissionError("INVALID_RATE_EVIDENCE_SCHEMA_VERSION")
    if doc.get("owner_accepted_rates") is not True:
        raise PermissionError("RATE_EVIDENCE_NOT_ACCEPTED_BY_OWNER")
    cap_at = doc.get("captured_at_utc")
    if not isinstance(cap_at, str) or not _ISO8601_UTC_Z_RE.match(cap_at):
        raise PermissionError(f"RATE_EVIDENCE_INVALID_UTC_TIMESTAMP:{cap_at!r}")

    provs = doc.get("providers")
    if not isinstance(provs, Mapping):
        raise PermissionError("RATE_EVIDENCE_MISSING_PROVIDERS")
    snap_role = {"openai": "judge_A", "anthropic": "judge_B"}
    for prov in ("openai", "anthropic"):
        rec = provs.get(prov)
        if not isinstance(rec, Mapping):
            raise PermissionError(f"RATE_EVIDENCE_MISSING_PROVIDER:{prov}")
        src_url = rec.get("source_url")
        if not isinstance(src_url, str) or not src_url.startswith("https://"):
            raise PermissionError(f"RATE_EVIDENCE_INVALID_SOURCE_URL:{prov}")
        ev_sha = rec.get("evidence_artifact_sha256")
        if type(ev_sha) is not str or not SHA256_HEX_RE.match(ev_sha) or ev_sha in FORBIDDEN_TOY_HASHES:
            raise PermissionError(f"RATE_EVIDENCE_MISSING_OR_TOY_HASH:{prov}")
        snap = rec.get("model_snapshot_id")
        if not isinstance(snap, str) or not snap.strip():
            raise PermissionError(f"RATE_EVIDENCE_MISSING_SNAPSHOT:{prov}")
        if expected_judge_snapshots is not None:
            rk = snap_role[prov]
            if rk in expected_judge_snapshots and expected_judge_snapshots[rk] != snap:
                raise PermissionError(f"RATE_EVIDENCE_SNAPSHOT_MISMATCH:{prov}:{snap!r}!={expected_judge_snapshots[rk]!r}")
        for r_key in ("batch_input_usd_per_1m", "batch_output_usd_per_1m"):
            r_val = rec.get(r_key)
            if isinstance(r_val, bool) or not isinstance(r_val, (int, float)) or not math.isfinite(float(r_val)) or float(r_val) <= 0.0:
                raise PermissionError(f"RATE_EVIDENCE_INVALID_RATE:{prov}:{r_key}={r_val!r}")

    return {
        "rate_evidence_sha256": actual_sha,
        "captured_at_utc": cap_at,
        "account_pricing_status": "OWNER_ATTESTED_TIMESTAMPED_RATE_EVIDENCE",
        "providers": dict(provs),
    }


ALLOWED_ACTIVATION_GATE_PHASES: tuple[str, str] = ("PRE_PREFLIGHT_PROBE_ONLY", "STAGE1_LIVE")


def _verify_receipts_with_resolved_keys(
    *,
    bundle: Mapping[str, Any],
    trust_artifacts: Mapping[str, Mapping[str, Any]],
    resolved_owner_pubkey_hex: str | None,
    resolved_auditor_pubkey_hex: str | None,
    verify_external_tr_path: bool,
    gate_phase: str = "STAGE1_LIVE",
    expected_out_of_band_auditor_report_sha256: str | None = None,
    expected_target_zip_sha256: str | None = None,
) -> dict[str, Any]:
    """Verify Ed25519 trust-root anchor and signed receipts for PRE_PREFLIGHT_PROBE_ONLY or STAGE1_LIVE."""
    if gate_phase not in ALLOWED_ACTIVATION_GATE_PHASES:
        raise ValueError(f"INVALID_GATE_PHASE:{gate_phase!r}")
    if not resolved_owner_pubkey_hex:
        raise PermissionError("HOLD_EXTERNAL_OWNER_TRUST_ROOT_NOT_PROVISIONED")

    required_keys: tuple[str, ...] = (
        (
            "trust_root_anchor",
            "owner_activation_receipt",
            "od_ae_05_receipt",
            "auditor_verdict_receipt",
            "sv01_resolution_receipt",
        )
        if gate_phase == "PRE_PREFLIGHT_PROBE_ONLY"
        else (
            "trust_root_anchor",
            "owner_activation_receipt",
            "od_ae_05_receipt",
            "provider_preflight_receipt",
            "auditor_verdict_receipt",
            "sv01_resolution_receipt",
        )
    )
    for k in required_keys:
        if not isinstance(trust_artifacts.get(k), Mapping):
            raise PermissionError(f"MISSING_SIGNED_RECEIPT:{k}")

    bundle_sha = sha256_bytes(
        json.dumps(dict(bundle), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )

    tr = trust_artifacts["trust_root_anchor"]
    _verify_route2_ed25519_signature(
        pubkey_hex=resolved_owner_pubkey_hex,
        signature_hex=str(tr.get("owner_detached_signature_hex", "")),
        message=canonical_route2_signing_bytes(ROUTE2_TRUST_ROOT_DOMAIN_TAG, tr),
    )
    if tr.get("protocol_v1_sha256") != PROTOCOL_V1_0_SHA256 or tr.get("annex_v022_sha256") != ANNEX_V0_2_2_SHA256:
        raise PermissionError("TRUST_ROOT_FROZEN_AUTHORITY_SHA256_MISMATCH")
    if tr.get("harmonization_id") != ROUTE2_HARMONIZATION_ID:
        raise PermissionError("TRUST_ROOT_HARMONIZATION_ID_MISMATCH")
    tr_path = tr.get("external_trust_root_path")
    if tr_path is not None and verify_external_tr_path:
        p_tr = Path(str(tr_path))
        if p_tr.is_symlink() or not p_tr.exists():
            raise PermissionError("EXTERNAL_TRUST_ROOT_PATH_MISSING_OR_SYMLINK")

    aud_mode = str(tr.get("auditor_verdict_mode", AUDITOR_VERDICT_MODE_DUAL_ED25519))
    if aud_mode not in ALLOWED_AUDITOR_VERDICT_MODES:
        raise PermissionError(f"INVALID_AUDITOR_VERDICT_MODE:{aud_mode!r}")

    av = trust_artifacts["auditor_verdict_receipt"]
    aud_pk = ""
    attested_rep_sha: str | None = None
    if aud_mode == AUDITOR_VERDICT_MODE_DUAL_ED25519:
        aud_pk = resolved_auditor_pubkey_hex or str(tr.get("auditor_ed25519_pubkey_hex", ""))
        if aud_pk == resolved_owner_pubkey_hex:
            raise PermissionError("OWNER_AND_AUDITOR_KEYS_MUST_BE_DISTINCT")
        _verify_route2_ed25519_signature(
            pubkey_hex=aud_pk,
            signature_hex=str(av.get("auditor_detached_signature_hex", "")),
            message=canonical_route2_signing_bytes(ROUTE2_AUDITOR_VERDICT_DOMAIN_TAG, av),
        )
        if av.get("verdict") != "PASS" or av.get("harmonization_id") != ROUTE2_HARMONIZATION_ID:
            raise PermissionError("AUDITOR_VERDICT_NOT_PASS_OR_VERSION_MISMATCH")
    else:
        if bundle.get("auditor_text_verdict_amendment_ratified") is not True:
            raise PermissionError("HOLD_AI_AUDIT_TEXT_AMENDMENT_NOT_RATIFIED")
        if tr.get("auditor_ed25519_pubkey_hex") is not None:
            raise PermissionError("TEXT_VERDICT_MODE_FORBIDS_FAKE_AUDITOR_ED25519_PUBKEY")
        if av.get("auditor_verdict_mode") != AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER:
            raise PermissionError("AUDITOR_RECEIPT_MODE_MISMATCH")
        if av.get("signature_authority") != "OWNER_ATTESTED_AI_TEXT_NOT_AUDITOR_ED25519":
            raise PermissionError("AUDITOR_RECEIPT_MISSING_HONEST_OWNER_ATTESTED_LABEL")
        if av.get("auditor_detached_signature_hex") is not None:
            raise PermissionError("TEXT_VERDICT_MODE_FORBIDS_FORGED_AUDITOR_ED25519_SIGNATURE")
        if av.get("verdict") != "PASS" or av.get("harmonization_id") != ROUTE2_HARMONIZATION_ID:
            raise PermissionError("AUDITOR_VERDICT_NOT_PASS_OR_VERSION_MISMATCH")
        if av.get("amendment_id") != ROUTE2_AMENDMENT_02_ID:
            raise PermissionError("AUDITOR_RECEIPT_AMENDMENT_ID_MISMATCH")
        rep_sha = av.get("auditor_report_sha256")
        if (
            type(rep_sha) is not str
            or not SHA256_HEX_RE.match(rep_sha)
            or rep_sha in FORBIDDEN_TOY_HASHES
            or rep_sha in FORBIDDEN_PRIOR_PRE_AMENDMENT_AUDIT_SHA256S
        ):
            raise PermissionError("INVALID_OR_PRE_AMENDMENT_AUDITOR_REPORT_SHA256")
        if gate_phase == "PRE_PREFLIGHT_PROBE_ONLY":
            if rep_sha != tr.get("auditor_report_sha256"):
                raise PermissionError("AUDITOR_REPORT_SHA256_TRUST_ROOT_MISMATCH")
        else:
            p1_ref_sha = av.get("phase1_auditor_verdict_sha256")
            if (
                type(p1_ref_sha) is not str
                or not SHA256_HEX_RE.match(p1_ref_sha)
                or p1_ref_sha in FORBIDDEN_TOY_HASHES
                or p1_ref_sha in FORBIDDEN_PRIOR_PRE_AMENDMENT_AUDIT_SHA256S
                or hmac.compare_digest(p1_ref_sha, rep_sha)
            ):
                raise PermissionError("AUDITOR_RECEIPT_INVALID_PHASE1_VERDICT_REFERENCE")
            if tr.get("phase1_auditor_report_sha256") != p1_ref_sha or tr.get("auditor_report_sha256") != p1_ref_sha:
                raise PermissionError("TRUST_ROOT_PHASE1_AUDITOR_REPORT_SHA256_MISMATCH")
        if expected_out_of_band_auditor_report_sha256 is not None and not hmac.compare_digest(
            rep_sha, expected_out_of_band_auditor_report_sha256
        ):
            raise PermissionError("OUT_OF_BAND_AUDITOR_REPORT_SHA256_PIN_MISMATCH")
        rcpt_zip_sha = av.get("target_audit_zip_sha256")
        if (
            type(rcpt_zip_sha) is not str
            or not SHA256_HEX_RE.match(rcpt_zip_sha)
            or rcpt_zip_sha in FORBIDDEN_TOY_HASHES
            or rcpt_zip_sha in REJECTED_PRIOR_AUDIT_ZIP_SHA256S
        ):
            raise PermissionError("AUDITOR_RECEIPT_INVALID_OR_REJECTED_TARGET_ZIP_SHA256")
        if expected_target_zip_sha256 is not None and not hmac.compare_digest(rcpt_zip_sha, expected_target_zip_sha256):
            raise PermissionError("TARGET_AUDIT_ZIP_SHA256_PIN_MISMATCH")
        expected_av_stage = (
            "PRE_PREFLIGHT_PROBE_ONLY" if gate_phase == "PRE_PREFLIGHT_PROBE_ONLY" else "STAGE1_DEV_CANARY_ONLY"
        )
        if av.get("authorized_stage") != expected_av_stage:
            raise PermissionError(
                f"AUDITOR_RECEIPT_STAGE_MISMATCH:expected={expected_av_stage}:got={av.get('authorized_stage')!r}"
            )
        _verify_route2_ed25519_signature(
            pubkey_hex=resolved_owner_pubkey_hex,
            signature_hex=str(av.get("owner_detached_signature_hex", "")),
            message=canonical_route2_signing_bytes(ROUTE2_AUDITOR_VERDICT_DOMAIN_TAG, av),
        )
        attested_rep_sha = rep_sha

    oa = trust_artifacts["owner_activation_receipt"]
    _verify_route2_ed25519_signature(
        pubkey_hex=resolved_owner_pubkey_hex,
        signature_hex=str(oa.get("owner_detached_signature_hex", "")),
        message=canonical_route2_signing_bytes(ROUTE2_OWNER_ACTIVATION_DOMAIN_TAG, oa),
    )
    if oa.get("bound_bundle_sha256") != bundle_sha:
        raise PermissionError("OWNER_ACTIVATION_BUNDLE_SHA256_MISMATCH")
    if oa.get("final_50_authorized") is not False:
        raise PermissionError("OWNER_ACTIVATION_STAGE1_CANNOT_OPEN_FINAL50")

    auth_stage = oa.get("authorized_stage")
    if gate_phase == "PRE_PREFLIGHT_PROBE_ONLY":
        if auth_stage not in ("STAGE1_PREFLIGHT_PROBE_ONLY", "STAGE1_DEV_CANARY_ONLY"):
            raise PermissionError(f"INVALID_PRE_PREFLIGHT_STAGE:{auth_stage!r}")
        if oa.get("preflight_probes_authorized") is False:
            raise PermissionError("OWNER_ACTIVATION_PREFLIGHT_PROBES_DENIED")
    else:
        if auth_stage == "STAGE1_PREFLIGHT_PROBE_ONLY":
            raise PermissionError("PREFLIGHT_SCOPE_CANNOT_OPEN_STAGE1_LIVE_BATCH")
        if auth_stage != "STAGE1_DEV_CANARY_ONLY":
            raise PermissionError(f"INVALID_STAGE1_LIVE_STAGE:{auth_stage!r}")

    od = trust_artifacts["od_ae_05_receipt"]
    _verify_route2_ed25519_signature(
        pubkey_hex=resolved_owner_pubkey_hex,
        signature_hex=str(od.get("owner_detached_signature_hex", "")),
        message=canonical_route2_signing_bytes(ROUTE2_OD_AE_05_DOMAIN_TAG, od),
    )
    if (
        od.get("tier_t1_sanitized_v_only") is not True
        or od.get("raw_canonical_s_upload_forbidden") is not True
        or od.get("anthropic_29day_non_zdr_batch_retention_accepted") is not True
        or od.get("mandatory_post_batch_delete") is not True
    ):
        raise PermissionError("OD_AE_05_INCOMPLETE_RETENTION_OR_BOUNDARY_COMMITMENT")

    judge_snapshots: dict[str, Any] = {}
    if gate_phase == "STAGE1_LIVE":
        pf = trust_artifacts["provider_preflight_receipt"]
        _verify_route2_ed25519_signature(
            pubkey_hex=resolved_owner_pubkey_hex,
            signature_hex=str(pf.get("owner_detached_signature_hex", "")),
            message=canonical_route2_signing_bytes(ROUTE2_PROVIDER_PREFLIGHT_DOMAIN_TAG, pf),
        )
        if int(pf.get("max_item_tokens_measured", 999999)) >= 100000:
            raise PermissionError("PROVIDER_PREFLIGHT_EXCEEDS_100K_CLIFF")
        if pf.get("count_tokens_verified") is not True or pf.get("live_account_rates_verified") is not True:
            raise PermissionError("PROVIDER_PREFLIGHT_COUNT_OR_RATES_UNVERIFIED")
        if verify_external_tr_path:
            re_sha = pf.get("rate_evidence_sha256")
            if (
                type(re_sha) is not str
                or not SHA256_HEX_RE.match(re_sha)
                or re_sha in FORBIDDEN_TOY_HASHES
                or pf.get("account_pricing_status") != "OWNER_ATTESTED_TIMESTAMPED_RATE_EVIDENCE"
            ):
                raise PermissionError("PROVIDER_PREFLIGHT_MISSING_RATE_EVIDENCE_ATTESTATION")
        probe_sha = pf.get("raw_probe_transcript_sha256")
        if type(probe_sha) is not str or not SHA256_HEX_RE.match(probe_sha) or probe_sha in FORBIDDEN_TOY_HASHES:
            raise PermissionError("PROVIDER_PREFLIGHT_MISSING_OR_INVALID_RAW_PROBE_SHA256")
        snaps = pf.get("judge_snapshots")
        if (
            not isinstance(snaps, Mapping)
            or not isinstance(snaps.get("judge_A"), str)
            or not snaps["judge_A"].strip()
            or not isinstance(snaps.get("judge_B"), str)
            or not snaps["judge_B"].strip()
        ):
            raise PermissionError("PROVIDER_PREFLIGHT_MISSING_PINNED_JUDGE_SNAPSHOTS")
        judge_snapshots = dict(snaps)
        if aud_mode == AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER:
            pf_status_sha = pf.get("provider_preflight_status_sha256")
            if (
                type(pf_status_sha) is not str
                or not SHA256_HEX_RE.match(pf_status_sha)
                or pf_status_sha in FORBIDDEN_TOY_HASHES
            ):
                raise PermissionError("PROVIDER_PREFLIGHT_MISSING_STATUS_SHA256")
            if (
                av.get("raw_probe_transcript_sha256") != probe_sha
                or av.get("provider_preflight_status_sha256") != pf_status_sha
                or av.get("rate_evidence_sha256") != pf.get("rate_evidence_sha256")
            ):
                raise PermissionError("AUDITOR_RECEIPT_PREFLIGHT_BINDING_MISMATCH")

    if aud_mode == AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER and verify_external_tr_path:
        art_path_raw = av.get("auditor_report_artifact_path")
        if not isinstance(art_path_raw, str) or not art_path_raw.strip():
            raise PermissionError("MISSING_AUDITOR_REPORT_ARTIFACT_PATH")
        art_p = Path(art_path_raw)
        bound_expected = (
            None
            if gate_phase == "PRE_PREFLIGHT_PROBE_ONLY"
            else {
                "raw_probe_transcript_sha256": str(av["raw_probe_transcript_sha256"]),
                "provider_preflight_status_sha256": str(av["provider_preflight_status_sha256"]),
                "rate_evidence_sha256": str(av["rate_evidence_sha256"]),
                "phase1_auditor_verdict_sha256": str(av["phase1_auditor_verdict_sha256"]),
            }
        )
        verify_ai_audit_text_report_artifact(
            art_p,
            expected_report_sha256=attested_rep_sha,
            expected_target_zip_sha256=av.get("target_audit_zip_sha256"),
            expected_gate_phase=gate_phase,
            expected_bound_preflight=bound_expected,
        )

    # SV-01 cryptographic proof check
    sv01_proof = trust_artifacts["sv01_resolution_receipt"]
    mode = sv01_proof.get("resolution_mode")
    if mode == "SUPERVISOR_WRITTEN_VERIFIED":
        _verify_route2_ed25519_signature(
            pubkey_hex=resolved_owner_pubkey_hex,
            signature_hex=str(sv01_proof.get("owner_detached_signature_hex", "")),
            message=canonical_route2_signing_bytes(ROUTE2_SV01_EVIDENCE_DOMAIN_TAG, sv01_proof),
        )
        if sv01_proof.get("supervisor_confirmed_artifact_sha256") != bundle.get("sv01_record", {}).get(
            "supervisor_confirmed_artifact_sha256"
        ):
            raise PermissionError("SV01_RECEIPT_ARTIFACT_SHA256_MISMATCH")
    elif mode == "RATIFIED_FROZEN_RULE_WAIVER_EXCEPTION":
        if sv01_proof.get("epistemic_label_locked") != "AI_PROXY_NOT_HUMAN":
            raise PermissionError("SV01_WAIVER_MUST_LOCK_AI_PROXY_NOT_HUMAN")
        _verify_route2_ed25519_signature(
            pubkey_hex=resolved_owner_pubkey_hex,
            signature_hex=str(sv01_proof.get("owner_detached_signature_hex", "")),
            message=canonical_route2_signing_bytes(ROUTE2_SV01_EVIDENCE_DOMAIN_TAG, sv01_proof),
        )
        if aud_mode == AUDITOR_VERDICT_MODE_DUAL_ED25519:
            _verify_route2_ed25519_signature(
                pubkey_hex=aud_pk,
                signature_hex=str(sv01_proof.get("auditor_detached_signature_hex", "")),
                message=canonical_route2_signing_bytes(ROUTE2_SV01_EVIDENCE_DOMAIN_TAG, sv01_proof),
            )
        else:
            if sv01_proof.get("auditor_detached_signature_hex") is not None:
                raise PermissionError("SV01_WAIVER_TEXT_VERDICT_MODE_FORBIDS_FORGED_AUDITOR_SIGNATURE")
            if sv01_proof.get("auditor_verdict_mode") != AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER:
                raise PermissionError("SV01_WAIVER_AUDITOR_MODE_MISMATCH")
            if sv01_proof.get("auditor_report_sha256") != attested_rep_sha:
                raise PermissionError("SV01_WAIVER_AUDITOR_REPORT_SHA256_MISMATCH")
    else:
        raise PermissionError(f"INVALID_SV01_RESOLUTION_MODE:{mode!r}")

    # Budget40 signed activation check if selected
    caps = bundle.get("budget_caps", {})
    if caps.get("selected_cap_regime") == "BUDGET40_40USD":
        b40_sig = oa.get("budget40_signed_binding_sha256")
        if type(b40_sig) is not str or not SHA256_HEX_RE.match(b40_sig):
            raise PermissionError("HOLD_BUDGET40_SIGNED_BINDING_MISSING_KEEP_20USD")

    return {
        "cryptographic_verification_passed": True,
        "gate_phase": gate_phase,
        "auditor_verdict_mode": aud_mode,
        "auditor_report_sha256": attested_rep_sha,
        "bundle_sha256": bundle_sha,
        "authorized_stage": auth_stage,
        "batch_generation_allowed": gate_phase == "STAGE1_LIVE",
        "sv01_resolution_mode": mode,
        "judge_snapshots_pinned": judge_snapshots,
    }


def verify_route2_cryptographic_activation_receipts(
    *,
    bundle: Mapping[str, Any],
    trust_artifacts: Mapping[str, Mapping[str, Any]],
    gate_phase: str = "STAGE1_LIVE",
    _test_only_trusted_owner_pubkey_hex: str | None = None,
    _test_only_trusted_auditor_pubkey_hex: str | None = None,
) -> dict[str, Any]:
    """Cryptographically verify external trust-root anchor and signed activation receipts."""
    if os.environ.get("W07_ROUTE2_FORCE_UNLOCK") == "1" or os.environ.get("W07_OWNER_AUTHORIZED") == "1":
        pass

    resolved_owner = (
        _test_only_trusted_owner_pubkey_hex
        if _test_only_trusted_owner_pubkey_hex is not None
        else PINNED_LIVE_ROUTE2_OWNER_PUBKEY_HEX
    )
    resolved_auditor = (
        _test_only_trusted_auditor_pubkey_hex
        if _test_only_trusted_auditor_pubkey_hex is not None
        else PINNED_LIVE_ROUTE2_AUDITOR_PUBKEY_HEX
    )
    return _verify_receipts_with_resolved_keys(
        bundle=bundle,
        trust_artifacts=trust_artifacts,
        resolved_owner_pubkey_hex=resolved_owner,
        resolved_auditor_pubkey_hex=resolved_auditor,
        verify_external_tr_path=(_test_only_trusted_owner_pubkey_hex is None),
        gate_phase=gate_phase,
    )


def validate_sv01_supervisor_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Enforce honest SV-01 advisor evidence tracking: never forge written confirmation."""
    if not isinstance(record, Mapping):
        raise ValueError("SV-01 record must be a mapping")
    status = record.get("supervisor_approval_status")
    if status not in SUPERVISOR_ALLOWED_STATUSES:
        raise ValueError(f"INVALID_SV01_STATUS: {status!r}; expected {sorted(SUPERVISOR_ALLOWED_STATUSES)!r}")

    written_on_disk = record.get("supervisor_written_evidence_on_disk")
    sig_ref = record.get("supervisor_signature_ref")
    artifact_sha = record.get("supervisor_confirmed_artifact_sha256")
    sup_id = record.get("supervisor_identity")

    if type(written_on_disk) is not bool:
        raise ValueError("supervisor_written_evidence_on_disk must be bool")

    if status == "OWNER_REPORTED_APPROVAL":
        if written_on_disk is not False:
            raise ValueError("OWNER_REPORTED_APPROVAL must have supervisor_written_evidence_on_disk=False")
        if sig_ref is not None or artifact_sha is not None:
            raise ValueError(
                "FORGED_SUPERVISOR_SIGNATURE_FORBIDDEN: OWNER_REPORTED_APPROVAL requires signature_ref=None & sha256=None"
            )
        return {
            "sv01_valid": True,
            "supervisor_approval_status": status,
            "written_verified": False,
            "requires_audit_and_owner_waiver": True,
        }

    if not written_on_disk:
        raise ValueError("SUPERVISOR_WRITTEN_VERIFIED requires supervisor_written_evidence_on_disk=True")
    if type(sup_id) is not str or not sup_id.strip() or "BLANK" in sup_id.upper() or "TEMPLATE" in sup_id.upper():
        raise ValueError(f"Invalid supervisor_identity for written verified SV-01: {sup_id!r}")
    if type(sig_ref) is not str or not sig_ref.strip() or "BLANK" in sig_ref.upper():
        raise ValueError(f"Invalid supervisor_signature_ref for written verified SV-01: {sig_ref!r}")
    if type(artifact_sha) is not str or SHA256_HEX_RE.match(artifact_sha) is None or artifact_sha in FORBIDDEN_TOY_HASHES:
        raise ValueError(f"Invalid supervisor_confirmed_artifact_sha256: {artifact_sha!r}")

    return {
        "sv01_valid": True,
        "supervisor_approval_status": status,
        "written_verified": True,
        "requires_audit_and_owner_waiver": False,
    }


def _evaluate_bundle_with_resolved_keys(
    bundle: Mapping[str, Any],
    *,
    trust_artifacts: Mapping[str, Mapping[str, Any]] | None,
    resolved_owner_pubkey_hex: str | None,
    resolved_auditor_pubkey_hex: str | None,
    verify_external_tr_path: bool,
    require_live_execution: bool = False,
    gate_phase: str = "STAGE1_LIVE",
    expected_out_of_band_auditor_report_sha256: str | None = None,
    expected_target_zip_sha256: str | None = None,
) -> dict[str, Any]:
    """Fail-closed activation gate evaluator shared across preflight probes and Stage-1 live execution."""
    if gate_phase not in ALLOWED_ACTIVATION_GATE_PHASES:
        raise ValueError(f"INVALID_GATE_PHASE:{gate_phase!r}")
    if not isinstance(bundle, Mapping):
        raise ValueError("Route 2 bundle must be a mapping")
    blockers: list[str] = []

    if bundle.get("decision_route") != ROUTE2_DECISION_ID:
        blockers.append(f"EXPECTED_DECISION_ROUTE:{ROUTE2_DECISION_ID}")
    if bundle.get("harmonization_id") != ROUTE2_HARMONIZATION_ID:
        blockers.append(f"HARMONIZATION_ID_MISMATCH:{bundle.get('harmonization_id')!r}!={ROUTE2_HARMONIZATION_ID!r}")
    if bundle.get("route1_human_labeling_stopped") is not True:
        blockers.append("ROUTE1_STOP_NOT_ATTESTED")
    if bundle.get("protocol_v1_sha256") != PROTOCOL_V1_0_SHA256:
        blockers.append("PROTOCOL_V1_SHA256_MISMATCH")
    if bundle.get("annex_v022_sha256") != ANNEX_V0_2_2_SHA256:
        blockers.append("ANNEX_V022_SHA256_MISMATCH")
    if bundle.get("g5_status") != "HOLD_NOT_AUTHORIZED_BY_THIS_AMENDMENT":
        blockers.append("G5_MUST_REMAIN_HOLD")

    sv01_res = validate_sv01_supervisor_record(bundle.get("sv01_record", {}))
    waiver_accepted = (
        bundle.get("explicit_frozen_rule_sv01_waiver_amendment_ratified") is True
        and bundle.get("owner_reported_supervisor_waiver_accepted_by_audit_and_owner") is True
    )
    if not sv01_res["written_verified"] and not waiver_accepted:
        blockers.append("SV01_OWNER_REPORTED_ONLY_WRITTEN_GVHD_EVIDENCE_OR_RATIFIED_WAIVER_REQUIRED")

    if bundle.get("auditor_verdict_mode", AUDITOR_VERDICT_MODE_DUAL_ED25519) == AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER:
        if bundle.get("auditor_text_verdict_amendment_ratified") is not True:
            blockers.append("HOLD_AI_AUDIT_TEXT_AMENDMENT_NOT_RATIFIED")

    if bundle.get("chatgpt_audit_verdict") != "PASS":
        blockers.append("AWAITING_CHATGPT_INDEPENDENT_AUDIT_PASS")
    if bundle.get("owner_signed_amendment_receipt_verified") is not True:
        blockers.append("AWAITING_OWNER_SIGNED_AMENDMENT_AND_TRUST_ROOT_RECEIPT")
    if bundle.get("external_trust_root_provisioned") is not True:
        blockers.append("HOLD_EXTERNAL_OWNER_TRUST_ROOT_NOT_PROVISIONED")
    if bundle.get("od_ae_05_data_rights_and_batch_retention_signed") is not True:
        blockers.append("HOLD_OD_AE_05_PROVIDER_RETENTION_SIGNOFF_PENDING")
    if gate_phase == "STAGE1_LIVE" and bundle.get("live_account_rates_and_count_tokens_verified") is not True:
        blockers.append("HOLD_LIVE_ACCOUNT_RATES_AND_COUNT_TOKENS_NOT_VERIFIED")

    caps = bundle.get("budget_caps", {})
    cap_regime = caps.get("selected_cap_regime", "UNAMENDED_20USD")
    if cap_regime == "UNAMENDED_20USD":
        if caps.get("dev_hard_cap_usd") != 2.0 or caps.get("total_hard_cap_usd") != 20.0:
            blockers.append("UNAMENDED_20USD_CAP_MISMATCH")
    elif cap_regime == "BUDGET40_40USD":
        if caps.get("dev_hard_cap_usd") != 2.0 or caps.get("total_hard_cap_usd") != 40.0:
            blockers.append("BUDGET40_CAP_MISMATCH")
        if bundle.get("budget40_signed_activation_binding_verified") is not True:
            blockers.append("HOLD_BUDGET40_SIGNED_BINDING_MISSING_KEEP_20USD")
    else:
        blockers.append(f"INVALID_CAP_REGIME:{cap_regime!r}")

    # Mandatory cryptographic check: plain boolean flags NEVER authorize probes or live spend
    crypto_info: dict[str, Any] = {"cryptographic_verification_passed": False}
    if trust_artifacts is None:
        blockers.append("UNAUTHENTICATED_BOOLEAN_CLAIM_WITHOUT_CRYPTOGRAPHIC_RECEIPT")
    else:
        try:
            crypto_info = _verify_receipts_with_resolved_keys(
                bundle=bundle,
                trust_artifacts=trust_artifacts,
                resolved_owner_pubkey_hex=resolved_owner_pubkey_hex,
                resolved_auditor_pubkey_hex=resolved_auditor_pubkey_hex,
                verify_external_tr_path=verify_external_tr_path,
                gate_phase=gate_phase,
                expected_out_of_band_auditor_report_sha256=expected_out_of_band_auditor_report_sha256,
                expected_target_zip_sha256=expected_target_zip_sha256,
            )
        except PermissionError as exc:
            blockers.append(f"CRYPTOGRAPHIC_RECEIPT_REJECTED:{exc}")

    phase_ok = len(blockers) == 0 and crypto_info["cryptographic_verification_passed"] is True
    preflight_ok = phase_ok and gate_phase in ("PRE_PREFLIGHT_PROBE_ONLY", "STAGE1_LIVE")
    batch_gen_ok = phase_ok and gate_phase == "STAGE1_LIVE"

    if require_live_execution and not phase_ok:
        raise PermissionError(f"ROUTE2_LIVE_EXECUTION_BLOCKED: {blockers[0]} ({len(blockers)} total blockers)")

    status_label = (
        "READY_FOR_STAGE1_CANARY"
        if batch_gen_ok
        else ("READY_FOR_PRE_PREFLIGHT_PROBES_ONLY" if preflight_ok else "HOLD")
    )
    return {
        "decision_route": ROUTE2_DECISION_ID,
        "harmonization_id": ROUTE2_HARMONIZATION_ID,
        "gate_phase": gate_phase,
        "preflight_probes_authorized": preflight_ok,
        "batch_generation_authorized": batch_gen_ok,
        "live_execution_authorized": batch_gen_ok,
        "cryptographic_verification": crypto_info,
        "formal_gates_status": status_label,
        "g5_status": "HOLD_NOT_AUTHORIZED_BY_THIS_AMENDMENT",
        "sv01_frozen_rules_require_written_evidence": True,
        "sv01": sv01_res,
        "selected_cap_regime": cap_regime,
        "blockers": blockers,
    }


def validate_route2_authorization_bundle(
    bundle: Mapping[str, Any],
    *,
    trust_artifacts: Mapping[str, Mapping[str, Any]] | None = None,
    require_live_execution: bool = False,
    gate_phase: str = "STAGE1_LIVE",
    _test_only_trusted_owner_pubkey_hex: str | None = None,
    _test_only_trusted_auditor_pubkey_hex: str | None = None,
) -> dict[str, Any]:
    """Test/mock-compatible authorization bundle checker (production paths must call validate_route2_live_activation_entrypoint)."""
    resolved_owner = (
        _test_only_trusted_owner_pubkey_hex
        if _test_only_trusted_owner_pubkey_hex is not None
        else PINNED_LIVE_ROUTE2_OWNER_PUBKEY_HEX
    )
    resolved_auditor = (
        _test_only_trusted_auditor_pubkey_hex
        if _test_only_trusted_auditor_pubkey_hex is not None
        else PINNED_LIVE_ROUTE2_AUDITOR_PUBKEY_HEX
    )
    return _evaluate_bundle_with_resolved_keys(
        bundle,
        trust_artifacts=trust_artifacts,
        resolved_owner_pubkey_hex=resolved_owner,
        resolved_auditor_pubkey_hex=resolved_auditor,
        verify_external_tr_path=(_test_only_trusted_owner_pubkey_hex is None),
        require_live_execution=require_live_execution,
        gate_phase=gate_phase,
    )


def _assert_not_symlink_or_reparse(path: Path) -> None:
    if path.is_symlink():
        raise PermissionError(f"SYMLINK_FORBIDDEN_IN_TRUST_PATH:{path}")
    lstat = os.lstat(path)
    attrs = getattr(lstat, "st_file_attributes", 0)
    if attrs & 0x0400:  # Windows FILE_ATTRIBUTE_REPARSE_POINT
        raise PermissionError(f"NTFS_REPARSE_POINT_FORBIDDEN_IN_TRUST_PATH:{path}")


def _assert_path_outside_repositories(path: Path) -> None:
    resolved = path.resolve()
    prep_root = Path(__file__).resolve().parents[2]
    for anc in (resolved, *resolved.parents):
        if anc == prep_root:
            raise PermissionError(f"EXTERNAL_TRUST_ROOT_CANNOT_BE_INSIDE_REPO:{resolved}")
        if len(anc.parts) > 1 and (anc / ".git").exists():
            raise PermissionError(f"EXTERNAL_TRUST_ROOT_CANNOT_BE_INSIDE_REPO:{resolved}")
        if anc.parent == prep_root.parent and (
            (anc / "pyproject.toml").exists() or (anc / "README.md").exists()
        ):
            raise PermissionError(f"EXTERNAL_TRUST_ROOT_CANNOT_BE_INSIDE_REPO:{resolved}")


def load_external_route2_trust_root(
    trust_root_dir: Path,
    *,
    out_of_band_owner_pubkey_sha256: str | None = None,
    out_of_band_auditor_pubkey_sha256: str | None = None,
    out_of_band_manifest_sha256: str | None = None,
    out_of_band_auditor_report_sha256: str | None = None,
    expect_manifest_report_pin_match: bool = True,
) -> dict[str, Any]:
    """Load and cryptographically verify an external trust root against mandatory out-of-band pins."""
    if not isinstance(trust_root_dir, Path):
        raise ValueError("trust_root_dir must be a pathlib.Path")
    has_key_pair_pins = bool(out_of_band_owner_pubkey_sha256 and out_of_band_auditor_pubkey_sha256)
    has_text_verdict_pins = bool(out_of_band_owner_pubkey_sha256 and out_of_band_auditor_report_sha256)
    has_code_pins = bool(PINNED_LIVE_ROUTE2_OWNER_PUBKEY_HEX and PINNED_LIVE_ROUTE2_AUDITOR_PUBKEY_HEX)
    if not (out_of_band_manifest_sha256 or has_key_pair_pins or has_text_verdict_pins or has_code_pins):
        raise PermissionError("HOLD_OUT_OF_BAND_TRUST_ROOT_PIN_REQUIRED")

    if not trust_root_dir.exists() or not trust_root_dir.is_dir():
        raise PermissionError(f"HOLD_EXTERNAL_OWNER_TRUST_ROOT_NOT_PROVISIONED:{trust_root_dir}")
    _assert_not_symlink_or_reparse(trust_root_dir)
    _assert_path_outside_repositories(trust_root_dir)

    manifest_path = trust_root_dir / "trust_root_manifest.json"
    if not manifest_path.is_file():
        raise PermissionError(f"HOLD_EXTERNAL_TRUST_ROOT_MANIFEST_MISSING:{manifest_path}")
    _assert_not_symlink_or_reparse(manifest_path)

    raw_bytes = manifest_path.read_bytes()
    actual_sha = sha256_bytes(raw_bytes)
    if out_of_band_manifest_sha256 is not None:
        if (
            not SHA256_HEX_RE.match(out_of_band_manifest_sha256)
            or out_of_band_manifest_sha256 in FORBIDDEN_TOY_HASHES
        ):
            raise PermissionError("INVALID_OUT_OF_BAND_MANIFEST_PIN_FORMAT")
        if not hmac.compare_digest(actual_sha, out_of_band_manifest_sha256):
            raise PermissionError("EXTERNAL_TRUST_ROOT_MANIFEST_SHA256_MISMATCH")

    manifest = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(manifest, Mapping):
        raise ValueError("Malformed trust_root_manifest.json")
    owner_pk = manifest.get("owner_ed25519_pubkey_hex")
    anchor = manifest.get("trust_root_anchor")
    if not isinstance(owner_pk, str) or not isinstance(anchor, Mapping):
        raise PermissionError("HOLD_EXTERNAL_TRUST_ROOT_KEYS_UNPROVISIONED")
    if not re.fullmatch(r"[0-9a-f]{64}", owner_pk):
        raise PermissionError("ROUTE2_INVALID_TRUSTED_PUBKEY_HEX")
    owner_pk_fp = sha256_bytes(bytes.fromhex(owner_pk))
    if out_of_band_owner_pubkey_sha256 is not None:
        if not hmac.compare_digest(owner_pk_fp, out_of_band_owner_pubkey_sha256):
            raise PermissionError("OUT_OF_BAND_OWNER_PUBKEY_PIN_MISMATCH")
    if PINNED_LIVE_ROUTE2_OWNER_PUBKEY_HEX is not None and not hmac.compare_digest(
        owner_pk, PINNED_LIVE_ROUTE2_OWNER_PUBKEY_HEX
    ):
        raise PermissionError("PINNED_LIVE_OWNER_PUBKEY_MISMATCH")

    aud_mode = str(anchor.get("auditor_verdict_mode", manifest.get("auditor_verdict_mode", AUDITOR_VERDICT_MODE_DUAL_ED25519)))
    if aud_mode not in ALLOWED_AUDITOR_VERDICT_MODES:
        raise PermissionError(f"INVALID_AUDITOR_VERDICT_MODE:{aud_mode!r}")

    aud_pk: str | None = None
    aud_pk_fp: str | None = None
    rep_sha: str | None = None

    if aud_mode == AUDITOR_VERDICT_MODE_DUAL_ED25519:
        if not (out_of_band_manifest_sha256 or has_key_pair_pins or has_code_pins):
            raise PermissionError("HOLD_OUT_OF_BAND_TRUST_ROOT_PIN_REQUIRED")
        aud_pk_raw = manifest.get("auditor_ed25519_pubkey_hex")
        if not isinstance(aud_pk_raw, str):
            raise PermissionError("HOLD_EXTERNAL_TRUST_ROOT_KEYS_UNPROVISIONED")
        if not re.fullmatch(r"[0-9a-f]{64}", aud_pk_raw):
            raise PermissionError("ROUTE2_INVALID_TRUSTED_PUBKEY_HEX")
        if owner_pk == aud_pk_raw:
            raise PermissionError("OWNER_AND_AUDITOR_KEYS_MUST_BE_DISTINCT")
        if anchor.get("auditor_ed25519_pubkey_hex") != aud_pk_raw:
            raise PermissionError("EXTERNAL_TRUST_ROOT_AUDITOR_PUBKEY_MISMATCH")
        aud_pk = aud_pk_raw
        aud_pk_fp = sha256_bytes(bytes.fromhex(aud_pk_raw))
        if out_of_band_auditor_pubkey_sha256 is not None:
            if not hmac.compare_digest(aud_pk_fp, out_of_band_auditor_pubkey_sha256):
                raise PermissionError("OUT_OF_BAND_AUDITOR_PUBKEY_PIN_MISMATCH")
        if PINNED_LIVE_ROUTE2_AUDITOR_PUBKEY_HEX is not None and not hmac.compare_digest(
            aud_pk_raw, PINNED_LIVE_ROUTE2_AUDITOR_PUBKEY_HEX
        ):
            raise PermissionError("PINNED_LIVE_AUDITOR_PUBKEY_MISMATCH")
    else:
        if not (out_of_band_manifest_sha256 or has_text_verdict_pins):
            raise PermissionError("HOLD_OUT_OF_BAND_OWNER_AND_AUDITOR_REPORT_PIN_REQUIRED")
        if manifest.get("auditor_ed25519_pubkey_hex") is not None or anchor.get("auditor_ed25519_pubkey_hex") is not None:
            raise PermissionError("TEXT_VERDICT_MODE_FORBIDS_FAKE_AUDITOR_ED25519_PUBKEY")
        rep_sha_raw = manifest.get("auditor_report_sha256")
        if (
            type(rep_sha_raw) is not str
            or not SHA256_HEX_RE.match(rep_sha_raw)
            or rep_sha_raw in FORBIDDEN_TOY_HASHES
            or rep_sha_raw in FORBIDDEN_PRIOR_PRE_AMENDMENT_AUDIT_SHA256S
        ):
            raise PermissionError("INVALID_OR_PRE_AMENDMENT_AUDITOR_REPORT_SHA256")
        if anchor.get("auditor_report_sha256") != rep_sha_raw:
            raise PermissionError("EXTERNAL_TRUST_ROOT_AUDITOR_REPORT_SHA256_MISMATCH")
        if manifest.get("phase1_auditor_report_sha256") != anchor.get("phase1_auditor_report_sha256"):
            raise PermissionError("EXTERNAL_TRUST_ROOT_PHASE1_AUDITOR_REPORT_MISMATCH")
        if expect_manifest_report_pin_match and out_of_band_auditor_report_sha256 is not None and not hmac.compare_digest(
            rep_sha_raw, out_of_band_auditor_report_sha256
        ):
            raise PermissionError("OUT_OF_BAND_AUDITOR_REPORT_SHA256_PIN_MISMATCH")
        rep_sha = rep_sha_raw

    _verify_route2_ed25519_signature(
        pubkey_hex=owner_pk,
        signature_hex=str(anchor.get("owner_detached_signature_hex", "")),
        message=canonical_route2_signing_bytes(ROUTE2_TRUST_ROOT_DOMAIN_TAG, anchor),
    )
    if anchor.get("protocol_v1_sha256") != PROTOCOL_V1_0_SHA256 or anchor.get("annex_v022_sha256") != ANNEX_V0_2_2_SHA256:
        raise PermissionError("TRUST_ROOT_FROZEN_AUTHORITY_SHA256_MISMATCH")
    return {
        "trust_root_manifest_sha256": actual_sha,
        "auditor_verdict_mode": aud_mode,
        "auditor_report_sha256": rep_sha,
        "owner_ed25519_pubkey_hex": owner_pk,
        "auditor_ed25519_pubkey_hex": aud_pk,
        "owner_pubkey_sha256": owner_pk_fp,
        "auditor_pubkey_sha256": aud_pk_fp,
        "trust_root_anchor": dict(anchor),
    }


def validate_route2_live_activation_entrypoint(
    *,
    activation_pack_dir: Path,
    external_trust_root_dir: Path,
    gate_phase: str = "STAGE1_LIVE",
    out_of_band_owner_pubkey_sha256: str | None = None,
    out_of_band_auditor_pubkey_sha256: str | None = None,
    out_of_band_manifest_sha256: str | None = None,
    out_of_band_auditor_report_sha256: str | None = None,
    expected_target_zip_sha256: str | None = None,
) -> dict[str, Any]:
    """Strict production activation entrypoint: requires out-of-band root pin & NEVER uses test key injections."""
    if gate_phase not in ALLOWED_ACTIVATION_GATE_PHASES:
        raise ValueError(f"INVALID_GATE_PHASE:{gate_phase!r}")
    tr_loaded = load_external_route2_trust_root(
        external_trust_root_dir,
        out_of_band_owner_pubkey_sha256=out_of_band_owner_pubkey_sha256,
        out_of_band_auditor_pubkey_sha256=out_of_band_auditor_pubkey_sha256,
        out_of_band_manifest_sha256=out_of_band_manifest_sha256,
        out_of_band_auditor_report_sha256=out_of_band_auditor_report_sha256,
        expect_manifest_report_pin_match=(gate_phase == "PRE_PREFLIGHT_PROBE_ONLY"),
    )
    bundle_path = activation_pack_dir / "bundle.json"
    if not bundle_path.is_file():
        raise PermissionError(f"MISSING_ACTIVATION_BUNDLE_JSON:{bundle_path}")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    receipt_names: tuple[str, ...] = (
        ("owner_activation_receipt", "od_ae_05_receipt", "auditor_verdict_receipt", "sv01_resolution_receipt")
        if gate_phase == "PRE_PREFLIGHT_PROBE_ONLY"
        else (
            "owner_activation_receipt",
            "od_ae_05_receipt",
            "provider_preflight_receipt",
            "auditor_verdict_receipt",
            "sv01_resolution_receipt",
        )
    )
    trust_artifacts: dict[str, Mapping[str, Any]] = {"trust_root_anchor": tr_loaded["trust_root_anchor"]}
    for rname in receipt_names:
        rp = activation_pack_dir / "receipts" / f"{rname}.json"
        if not rp.is_file():
            raise PermissionError(f"MISSING_SIGNED_RECEIPT_FILE:{rp}")
        _assert_not_symlink_or_reparse(rp)
        trust_artifacts[rname] = json.loads(rp.read_text(encoding="utf-8"))

    res = _evaluate_bundle_with_resolved_keys(
        bundle,
        trust_artifacts=trust_artifacts,
        resolved_owner_pubkey_hex=tr_loaded["owner_ed25519_pubkey_hex"],
        resolved_auditor_pubkey_hex=tr_loaded["auditor_ed25519_pubkey_hex"],
        verify_external_tr_path=True,
        require_live_execution=True,
        gate_phase=gate_phase,
        expected_out_of_band_auditor_report_sha256=out_of_band_auditor_report_sha256,
        expected_target_zip_sha256=expected_target_zip_sha256,
    )
    if (
        gate_phase == "STAGE1_LIVE"
        and tr_loaded["auditor_verdict_mode"] == AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER
    ):
        pf_doc = trust_artifacts["provider_preflight_receipt"]
        status_path = activation_pack_dir / "provider_preflight_status.json"
        if not status_path.is_file():
            raise PermissionError(f"MISSING_PROVIDER_PREFLIGHT_STATUS_FILE:{status_path}")
        _assert_not_symlink_or_reparse(status_path)
        status_bytes = status_path.read_bytes()
        if not hmac.compare_digest(sha256_bytes(status_bytes), str(pf_doc["provider_preflight_status_sha256"])):
            raise PermissionError("PROVIDER_PREFLIGHT_STATUS_FILE_SHA256_MISMATCH")
        status_parsed = json.loads(status_bytes.decode("utf-8"))
        if (
            status_parsed.get("snapshots_verified_live") is not True
            or status_parsed.get("vendor_count_tokens_verified") is not True
            or status_parsed.get("raw_probe_transcript_sha256") != pf_doc.get("raw_probe_transcript_sha256")
        ):
            raise PermissionError("PROVIDER_PREFLIGHT_STATUS_CONTENT_MISMATCH")
    return res


def compute_route2_cost_matrix(
    doc_utf8_bytes: Sequence[int],
    *,
    prompt_wrapper_utf8_bytes: int,
    schema_utf8_bytes: int,
    model_pairs: Sequence[Mapping[str, Any]],
    g2a_gen_calls: int = 100,
    g2a_verifier_calls: int = 1800,
    g2a_verifier_in_per_1m_usd: float = 0.05,
    g2a_verifier_out_per_1m_usd: float = 0.20,
    g2a_alt_verifier_in_per_1m_usd: float = 0.375,
    g2a_alt_verifier_out_per_1m_usd: float = 1.875,
    g2a_gen_flat_est_usd: float = 0.05,
    dev_hard_cap_usd: float = 2.00,
    baseline_20usd_cap_usd: float = 20.00,
    early_warning_usd: float = 36.00,
    total_hard_cap_usd: float = 40.00,
) -> dict[str, Any]:
    """Deterministic UTF-8 byte-ceiling & heuristic cost matrix comparing $20 baseline vs Budget40 ($40)."""
    if not doc_utf8_bytes:
        raise ValueError("doc_utf8_bytes must be non-empty")
    sorted_desc = sorted((int(x) for x in doc_utf8_bytes), reverse=True)
    n_docs = len(sorted_desc)
    mean_v = sum(sorted_desc) / float(n_docs)
    fixed_wrap = int(prompt_wrapper_utf8_bytes) + int(schema_utf8_bytes)

    mean_ceil_in = math.ceil(mean_v + fixed_wrap)
    mean_heur_in = math.ceil(mean_ceil_in / 3.2)
    max_ceil_in = sorted_desc[0] + fixed_wrap
    pool35_n = min(35, n_docs)
    pool35_ceil_in = math.ceil((sum(sorted_desc[:pool35_n]) / float(pool35_n)) + fixed_wrap)
    pool35_heur_in = math.ceil(pool35_ceil_in / 3.2)

    out_heur = 700
    out_pess = 1200

    def _calc_g2a(v_in_rate: float, v_out_rate: float) -> tuple[float, float]:
        vh = g2a_verifier_calls * ((mean_heur_in * v_in_rate / 1_000_000.0) + (out_heur * v_out_rate / 1_000_000.0))
        vp = g2a_verifier_calls * ((mean_ceil_in * v_in_rate / 1_000_000.0) + (out_pess * v_out_rate / 1_000_000.0))
        return round((vh * 1.05) + g2a_gen_flat_est_usd, 4), round((vp * 1.15) + (g2a_gen_flat_est_usd * 2.0), 4)

    g2a_econ_heur_usd, g2a_econ_pess_usd = _calc_g2a(g2a_verifier_in_per_1m_usd, g2a_verifier_out_per_1m_usd)
    g2a_flash38_heur_usd, g2a_flash38_pess_usd = _calc_g2a(g2a_alt_verifier_in_per_1m_usd, g2a_alt_verifier_out_per_1m_usd)

    def _cost_for_calls(
        calls_per_judge: int,
        in_heur: int,
        in_ceil: int,
        ja_in: float,
        ja_out: float,
        jb_in: float,
        jb_out: float,
        cap: float,
    ) -> dict[str, Any]:
        h_base = calls_per_judge * (
            (in_heur * (ja_in + jb_in) / 1_000_000.0) + (out_heur * (ja_out + jb_out) / 1_000_000.0)
        )
        p_base = calls_per_judge * (
            (in_ceil * (ja_in + jb_in) / 1_000_000.0) + (out_pess * (ja_out + jb_out) / 1_000_000.0)
        )
        cb = evaluate_budget_and_retry_circuit_breakers(0.0, p_base, cap, retry_reserve_fraction=0.15)
        return {
            "pairs_per_judge": calls_per_judge,
            "total_calls_2_judges": calls_per_judge * 2,
            "heuristic_nominal_5pct_usd": round(h_base * 1.05, 4),
            "pessimistic_byte_ceiling_15pct_usd": cb["reserved_total_usd"],
            "cap_usd": cap,
            "fits_cap_at_byte_ceiling": cb["allowed"],
            "halt_code": cb["halt_code"],
        }

    pair_reports: dict[str, Any] = {}
    for mp in model_pairs:
        pid = str(mp["pair_id"])
        ja_in, ja_out = float(mp["judge_a_batch_in_per_1m"]), float(mp["judge_a_batch_out_per_1m"])
        jb_in, jb_out = float(mp["judge_b_batch_in_per_1m"]), float(mp["judge_b_batch_out_per_1m"])

        stage1_single = _cost_for_calls(5 * n_docs, mean_heur_in, mean_ceil_in, ja_in, ja_out, jb_in, jb_out, dev_hard_cap_usd)
        stage1_strat20_swap = _cost_for_calls(
            (5 * n_docs) + n_docs, mean_heur_in, mean_ceil_in, ja_in, ja_out, jb_in, jb_out, dev_hard_cap_usd
        )
        stage1_full_swap = _cost_for_calls(
            10 * n_docs, mean_heur_in, mean_ceil_in, ja_in, ja_out, jb_in, jb_out, dev_hard_cap_usd
        )
        stage1_pool35_dual = _cost_for_calls(
            5 * pool35_n * 2, pool35_heur_in, pool35_ceil_in, ja_in, ja_out, jb_in, jb_out, dev_hard_cap_usd
        )
        final_order_a = _cost_for_calls(
            50 * n_docs, mean_heur_in, mean_ceil_in, ja_in, ja_out, jb_in, jb_out, total_hard_cap_usd
        )
        final_order_a_plus_200swap = _cost_for_calls(
            (50 * n_docs) + 200, mean_heur_in, mean_ceil_in, ja_in, ja_out, jb_in, jb_out, total_hard_cap_usd
        )
        final_order_b_u35 = _cost_for_calls(
            50 * pool35_n, pool35_heur_in, pool35_ceil_in, ja_in, ja_out, jb_in, jb_out, total_hard_cap_usd
        )

        cum_20_heur = round(
            stage1_strat20_swap["heuristic_nominal_5pct_usd"]
            + g2a_econ_heur_usd
            + final_order_a_plus_200swap["heuristic_nominal_5pct_usd"],
            4,
        )
        cum_20_pess = round(
            stage1_strat20_swap["pessimistic_byte_ceiling_15pct_usd"]
            + g2a_econ_pess_usd
            + final_order_a_plus_200swap["pessimistic_byte_ceiling_15pct_usd"],
            4,
        )
        cum_40_heur = round(
            stage1_strat20_swap["heuristic_nominal_5pct_usd"]
            + g2a_flash38_heur_usd
            + final_order_a_plus_200swap["heuristic_nominal_5pct_usd"],
            4,
        )
        cum_40_pess = round(
            stage1_strat20_swap["pessimistic_byte_ceiling_15pct_usd"]
            + g2a_flash38_pess_usd
            + final_order_a_plus_200swap["pessimistic_byte_ceiling_15pct_usd"],
            4,
        )
        pair_reports[pid] = {
            "judge_A": mp["judge_a_model_id"],
            "judge_B": mp["judge_b_model_id"],
            "stage1_single_5q_137d": stage1_single,
            "stage1_5q_137d_plus_20pct_swap": stage1_strat20_swap,
            "stage1_5q_137d_full_dual_swap": stage1_full_swap,
            "stage1_5q_pool35_dual_swap": stage1_pool35_dual,
            "final_order_a_50q_137d": final_order_a,
            "final_order_a_plus_200_swap": final_order_a_plus_200swap,
            "final_order_b_50q_u35": final_order_b_u35,
            "cumulative_with_g2a_econ_lite_order_a": {
                "g2a_2_model": "gemini-2.5-flash-lite (Paid Gemini Dev API Batch $0.05/$0.20)",
                "heuristic_nominal_5pct_usd": cum_20_heur,
                "pessimistic_byte_ceiling_15pct_usd": cum_20_pess,
                "fits_unamended_20usd_cap_at_byte_ceiling": cum_20_pess <= baseline_20usd_cap_usd,
                "headroom_below_20usd_cap_usd": round(baseline_20usd_cap_usd - cum_20_pess, 4),
            },
            "cumulative_with_g2a_flash38_order_a": {
                "g2a_2_model": "gemini-3.8-flash (Paid Batch $0.375/$1.875)",
                "heuristic_nominal_5pct_usd": cum_40_heur,
                "pessimistic_byte_ceiling_15pct_usd": cum_40_pess,
                "fits_unamended_20usd_cap_at_byte_ceiling": cum_40_pess <= baseline_20usd_cap_usd,
                "below_36usd_early_warning": cum_40_pess < early_warning_usd,
                "below_40usd_hard_cap": cum_40_pess <= total_hard_cap_usd,
            },
        }

    return {
        "schema_version": "W07_ROUTE2_DETERMINISTIC_COST_MATRIX_V2",
        "doc_count": n_docs,
        "mean_prompt_plus_schema_byte_ceiling_tokens": mean_ceil_in,
        "mean_prompt_plus_schema_heuristic_tokens": mean_heur_in,
        "max_prompt_plus_schema_byte_ceiling_tokens": max_ceil_in,
        "long_context_threshold_checks": {
            "max_single_item_byte_ceiling_tokens": max_ceil_in,
            "anthropic_haiku55_100k_cliff_tokens": 100000,
            "openai_gpt6luna_272k_cliff_tokens": 272000,
            "below_anthropic_100k_cliff": max_ceil_in < 100000,
            "below_openai_272k_cliff": max_ceil_in < 272000,
        },
        "order_a_contract_invariants": {
            "final_queries": 50,
            "frozen_docs": n_docs,
            "pairs_per_judge": 50 * n_docs,
            "base_dual_judge_calls": 2 * 50 * n_docs,
            "optional_prompt_order_swap_audit_pairs": 200,
            "max_schema_retries_per_item": 1,
            "max_batch_retry_fraction": 0.15,
            "max_failed_batches": 1,
        },
        "g2a_prep_econ_lite": {
            "verifier_model": "gemini-2.5-flash-lite ($0.05/$0.20 Dev API Batch)",
            "generator_calls": g2a_gen_calls,
            "verifier_calls": g2a_verifier_calls,
            "heuristic_nominal_usd": g2a_econ_heur_usd,
            "pessimistic_byte_ceiling_15pct_usd": g2a_econ_pess_usd,
        },
        "g2a_prep_flash38": {
            "verifier_model": "gemini-3.8-flash ($0.375/$1.875 Batch)",
            "generator_calls": g2a_gen_calls,
            "verifier_calls": g2a_verifier_calls,
            "heuristic_nominal_usd": g2a_flash38_heur_usd,
            "pessimistic_byte_ceiling_15pct_usd": g2a_flash38_pess_usd,
        },
        "model_pair_forecasts": pair_reports,
    }


def run_route2_aiproxy_offline_dryrun(
    *,
    catalog_pois: Sequence[Mapping[str, Any]],
    candidate_queries: Sequence[Mapping[str, Any]],
    docs_by_id: Mapping[str, Mapping[str, Any]],
    removed_by_doc_id: Mapping[str, list[tuple[int, int]]],
    source_verification_records: Mapping[str, Mapping[str, Any]],
    rankings_by_cell: Mapping[str, Mapping[str, list[str]]],
    judge_a_canonical_responses: dict[tuple[str, str], Any],
    judge_b_canonical_responses: dict[tuple[str, str], Any],
    judge_a_swapped_responses: dict[tuple[str, str], Any],
    judge_b_swapped_responses: dict[tuple[str, str], Any],
    expected_catalog_sha256: str | None = AUTHOR_SAFE_60_POI_CATALOG_SHA256,
    packet_salt: str = "SYNTHETIC_ROUTE2_DRYRUN_SALT",
    run_nonce: str = "0123456789abcdef0123456789abcdef",
) -> dict[str, Any]:
    """Run full offline Route 2 G2A -> FX-11 Blind Packet -> G2B Prompt-Order/Gates -> G4 Concordance dry-run."""
    g2a = validate_g2a_zero_human_proxy_batch(
        catalog_pois=catalog_pois,
        candidate_queries=candidate_queries,
        docs_by_id=docs_by_id,
        source_verification_records=source_verification_records,
        generator_model_family="xai_grok4",
        verifier_model_family="google_gemini3",
        judge_a_family="openai_gpt6",
        judge_b_family="anthropic_claude5",
        semantic_verifier_mode="SYNTHETIC_DECLARED_MOCK_TEST_ONLY",
        expected_catalog_sha256=expected_catalog_sha256,
    )

    doc_list = [
        {
            "source_type": "synthetic",
            "language": "vi",
            **dict(v),
            "document_id": str(did),
        }
        for did, v in sorted(docs_by_id.items())
    ]
    prompts_preview_count = 0
    for q in candidate_queries:
        pkts = emit_blind_judge_packets(str(q["query_id"]), str(q["query_text"]), doc_list, packet_salt)
        for row in pkts[:2]:
            pair = build_prompt_order_pair(row, run_nonce)
            assert "PROMPT_ORDER_CANONICAL" in pair and "PROMPT_ORDER_SWAPPED" in pair
            prompts_preview_count += 2

    q_list = [dict(q) for q in candidate_queries]
    docs_dict = {str(k): dict(v) for k, v in docs_by_id.items()}
    rem_dict = {str(k): list(v) for k, v in removed_by_doc_id.items()}

    order_bias_a = evaluate_prompt_order_bias(
        queries_meta=q_list,
        docs_by_id=docs_dict,
        removed_by_doc_id=rem_dict,
        canonical_responses=judge_a_canonical_responses,
        swapped_responses=judge_a_swapped_responses,
    )
    order_bias_b = evaluate_prompt_order_bias(
        queries_meta=q_list,
        docs_by_id=docs_dict,
        removed_by_doc_id=rem_dict,
        canonical_responses=judge_b_canonical_responses,
        swapped_responses=judge_b_swapped_responses,
    )
    combined_order_diag = {
        "prompt_order_gate_passed": bool(
            order_bias_a["prompt_order_gate_passed"] and order_bias_b["prompt_order_gate_passed"]
        ),
        "judge_A": order_bias_a,
        "judge_B": order_bias_b,
    }

    expected_pairs = {(str(q["query_id"]), str(did)) for q in q_list for did in docs_dict}
    ep_manifest = seal_expected_pairs_manifest(
        judging_order="ORDER_A",
        expected_pairs=expected_pairs,
        query_manifest_sha256=sha256_bytes(b"dryrun-queries"),
        sanitized_v_corpus_sha256=EXPECTED_V_CORPUS_SHA256,
        sealed_at_utc="2026-11-22T00:00:00Z",
    )
    verified_pairs = verify_sealed_expected_pairs_manifest(
        ep_manifest, earliest_judge_dispatch_utc="2026-11-22T00:01:00Z"
    )

    concordance = evaluate_dual_judge_concordance(
        queries_meta=q_list,
        docs_by_id=docs_dict,
        removed_by_doc_id=rem_dict,
        rankings_by_cell=rankings_by_cell,
        judge_a_responses=judge_a_canonical_responses,
        judge_b_responses=judge_b_canonical_responses,
        judging_order="ORDER_A",
        sealed_expected_pairs=verified_pairs,
        prompt_order_diagnostics=combined_order_diag,
    )

    g5_blocked = False
    try:
        check_g5_gate_unlock(concordance)
    except PermissionError:
        g5_blocked = True

    return {
        "execution_classification": "SYNTHETIC_AND_OFFLINE_DRYRUN_ONLY",
        "not_formal_ground_truth": True,
        "g2a_validation": g2a,
        "dual_order_prompt_previews_built": prompts_preview_count,
        "prompt_order_bias": combined_order_diag,
        "g4_concordance": concordance,
        "g5_fail_closed_hold_verified": g5_blocked,
    }
