"""FX-10: Shared-Lineage Non-Propagation & Epistemic Lineage Deduplication tests."""

from __future__ import annotations

from pathlib import Path

from fixtures.g4_fixtures import (
    build_fx10_shared_lineage_bundle,
    make_ranking_row,
    write_jsonl,
    write_sealed_rankings_bundle,
)
from w07_g4_scorer.contracts import (
    Cert4Status,
    QrelRecord,
    RelevanceState,
    compute_query_certificates,
    count_epistemic_lineages,
    load_external_qrels,
    resolve_qrel_state,
)
from w07_g4_scorer.scorer import score_g4_from_files


def test_fx10_shared_lineage_non_propagation_four_cases(tmp_path: Path) -> None:
    bundle = build_fx10_shared_lineage_bundle(tmp_path)
    docs = bundle["docs"]
    lineage_map = {did: d["source_lineage_id"] for did, d in docs.items()}

    # Case 1: Sibling A = REL_2, Sibling B omitted (UNJUDGED) across both wikivoyage & wikipedia lineages
    qrels_case1_path = write_jsonl(
        tmp_path / "qrels_case1.jsonl",
        [
            {
                "query_id": "q_wv",
                "document_id": "doc_wv_a",
                "label": "REL_2",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [[0, 12]],
                "source_lineage_id": "wikivoyage:en:Hanoi",
            },
            {
                "query_id": "q_wp",
                "document_id": "doc_wp_a",
                "label": "REL_2",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [[0, 12]],
                "source_lineage_id": "wikipedia:vi:4483",
            },
        ],
    )
    qrels_c1 = load_external_qrels(qrels_case1_path)
    assert resolve_qrel_state(qrels_c1, "q_wv", "doc_wv_a") == RelevanceState.REL_2
    assert resolve_qrel_state(qrels_c1, "q_wv", "doc_wv_b") == RelevanceState.UNJUDGED
    assert resolve_qrel_state(qrels_c1, "q_wp", "doc_wp_b") == RelevanceState.UNJUDGED

    # Cert-2 MUST fail (< 1.00) when unjudged sibling B appears in top-10 (blocks silent REL_0)
    cert_wv = compute_query_certificates(
        "q_wv",
        {"C1-RRF": ["doc_wv_a", "doc_wv_b"]},
        ["doc_wv_a", "doc_wv_b"],
        qrels_c1,
    )
    assert cert_wv.cert2_judged_at_10["C1-RRF"] == 0.5
    assert cert_wv.cert4_status == Cert4Status.INVALID_UNRESOLVED

    # Case 2: Sibling A = REL_2, Sibling B = NA
    qrels_case2_path = write_jsonl(
        tmp_path / "qrels_case2.jsonl",
        [
            {
                "query_id": "q_wv",
                "document_id": "doc_wv_a",
                "label": "REL_2",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [[0, 12]],
                "source_lineage_id": "wikivoyage:en:Hanoi",
            },
            {
                "query_id": "q_wv",
                "document_id": "doc_wv_b",
                "label": "NA",
                "evidence_s_spans": [],
                "source_lineage_id": "wikivoyage:en:Hanoi",
            },
        ],
    )
    qrels_c2 = load_external_qrels(qrels_case2_path)
    assert resolve_qrel_state(qrels_c2, "q_wv", "doc_wv_b") == RelevanceState.NA
    cert_na = compute_query_certificates(
        "q_wv",
        {"C1-RRF": ["doc_wv_a", "doc_wv_b"]},
        ["doc_wv_a", "doc_wv_b"],
        qrels_c2,
    )
    assert cert_na.cert2_judged_at_10["C1-RRF"] == 0.5
    assert cert_na.cert4_status == Cert4Status.INVALID_UNRESOLVED

    # Case 3: Sibling A = REL_2, Sibling B = REL_0 ONLY from explicit negative qrel
    qrels_case3_path = write_jsonl(
        tmp_path / "qrels_case3.jsonl",
        [
            {
                "query_id": "q_wv",
                "document_id": "doc_wv_a",
                "label": "REL_2",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [[0, 12]],
                "source_lineage_id": "wikivoyage:en:Hanoi",
            },
            {
                "query_id": "q_wv",
                "document_id": "doc_wv_b",
                "label": "REL_0",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [],
                "source_lineage_id": "wikivoyage:en:Hanoi",
            },
        ],
    )
    qrels_c3 = load_external_qrels(qrels_case3_path)
    assert resolve_qrel_state(qrels_c3, "q_wv", "doc_wv_b") == RelevanceState.REL_0
    cert_explicit_neg = compute_query_certificates(
        "q_wv",
        {"C1-RRF": ["doc_wv_a", "doc_wv_b"]},
        ["doc_wv_a", "doc_wv_b"],
        qrels_c3,
    )
    assert cert_explicit_neg.cert2_judged_at_10["C1-RRF"] == 1.0
    assert cert_explicit_neg.cert4_status == Cert4Status.EXACT_CERTIFIED

    # Case 4: Both A and B independently graded REL_2 -> both keep gain=3 for nDCG, epistemic_lineage_count == 1
    assert count_epistemic_lineages(["doc_wv_a", "doc_wv_b"], lineage_map) == 1
    assert count_epistemic_lineages(["doc_wp_a", "doc_wp_b"], lineage_map) == 1
    assert count_epistemic_lineages(["doc_wv_a", "doc_wv_b", "doc_wp_a", "doc_wp_b"], lineage_map) == 2

    qrels_case4_path = write_jsonl(
        tmp_path / "qrels_case4.jsonl",
        [
            {
                "query_id": "q_wv",
                "document_id": "doc_wv_a",
                "label": "REL_2",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [[0, 10]],
                "source_lineage_id": "wikivoyage:en:Hanoi",
            },
            {
                "query_id": "q_wv",
                "document_id": "doc_wv_b",
                "label": "REL_2",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [[0, 10]],
                "source_lineage_id": "wikivoyage:en:Hanoi",
            },
            {
                "query_id": "q_wv",
                "document_id": "doc_wp_a",
                "label": "REL_0",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [],
                "source_lineage_id": "wikipedia:vi:4483",
            },
            {
                "query_id": "q_wv",
                "document_id": "doc_wp_b",
                "label": "REL_0",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [],
                "source_lineage_id": "wikipedia:vi:4483",
            },
            {
                "query_id": "q_wp",
                "document_id": "doc_wp_a",
                "label": "REL_2",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [[0, 10]],
                "source_lineage_id": "wikipedia:vi:4483",
            },
            {
                "query_id": "q_wp",
                "document_id": "doc_wp_b",
                "label": "REL_2",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [[0, 10]],
                "source_lineage_id": "wikipedia:vi:4483",
            },
            {
                "query_id": "q_wp",
                "document_id": "doc_wv_a",
                "label": "REL_0",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [],
                "source_lineage_id": "wikivoyage:en:Hanoi",
            },
            {
                "query_id": "q_wp",
                "document_id": "doc_wv_b",
                "label": "REL_0",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [],
                "source_lineage_id": "wikivoyage:en:Hanoi",
            },
        ],
    )
    rows = [
        make_ranking_row(cell_id="C1-RRF", query_id="q_wv", rank=1, document_id="doc_wv_a", score=1.0),
        make_ranking_row(cell_id="C1-RRF", query_id="q_wv", rank=2, document_id="doc_wv_b", score=0.9),
        make_ranking_row(cell_id="C1-RRF", query_id="q_wp", rank=1, document_id="doc_wp_a", score=1.0),
        make_ranking_row(cell_id="C1-RRF", query_id="q_wp", rank=2, document_id="doc_wp_b", score=0.9),
    ]
    rankings_path, manifest_path = write_sealed_rankings_bundle(tmp_path, rows, cells=["C1-RRF"])
    report = score_g4_from_files(
        rankings_path=rankings_path,
        manifest_path=manifest_path,
        queries_path=bundle["queries_path"],
        qrels_path=qrels_case4_path,
    )
    c1_metrics = report["cell_metrics"]["C1-RRF"]
    assert abs(c1_metrics["ndcg10_lower"] - 1.0) < 1e-12
    assert abs(c1_metrics["ndcg10_upper"] - 1.0) < 1e-12
    assert abs(c1_metrics["epistemic_lineage_mean_at_10"] - 1.0) < 1e-12


def test_fx10_docs_null_lineage_falls_back_to_qrels_lineage(tmp_path: Path) -> None:
    """docs_by_id with source_lineage_id=None must not mask qrels.source_lineage_id."""
    bundle = build_fx10_shared_lineage_bundle(tmp_path)
    docs_with_null_lineage = {
        "doc_wv_a": {**bundle["docs"]["doc_wv_a"], "source_lineage_id": None},
        "doc_wv_b": {**bundle["docs"]["doc_wv_b"], "source_lineage_id": None},
    }
    qrels_path = write_jsonl(
        tmp_path / "qrels_fallback.jsonl",
        [
            {
                "query_id": "q_wv",
                "document_id": "doc_wv_a",
                "label": "REL_2",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [[0, 10]],
                "source_lineage_id": "wikivoyage:en:Hanoi",
            },
            {
                "query_id": "q_wv",
                "document_id": "doc_wv_b",
                "label": "REL_2",
                "plausible_unsupported_lure": 0,
                "evidence_s_spans": [[0, 10]],
                "source_lineage_id": "wikivoyage:en:Hanoi",
            },
        ],
    )
    queries_path = write_jsonl(tmp_path / "queries_wv.jsonl", [bundle["queries"][0]])
    docs_path = write_jsonl(
        tmp_path / "docs_null_lineage.jsonl",
        list(docs_with_null_lineage.values()),
    )
    rows = [
        make_ranking_row(cell_id="C1-RRF", query_id="q_wv", rank=1, document_id="doc_wv_a", score=1.0),
        make_ranking_row(cell_id="C1-RRF", query_id="q_wv", rank=2, document_id="doc_wv_b", score=0.9),
    ]
    rankings_path, manifest_path = write_sealed_rankings_bundle(tmp_path, rows, cells=["C1-RRF"])
    report = score_g4_from_files(
        rankings_path=rankings_path,
        manifest_path=manifest_path,
        queries_path=queries_path,
        qrels_path=qrels_path,
        docs_path=docs_path,
    )
    assert abs(report["cell_metrics"]["C1-RRF"]["epistemic_lineage_mean_at_10"] - 1.0) < 1e-12
