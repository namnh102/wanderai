"""Synthetic unit tests for FX-06..FX-09 and 2x3 matrix CLI smoke verification."""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from fixtures.retrieval_fixtures import (
    FX06_GOLDEN_SAMPLES,
    build_fx08_collapse_corpus,
    build_fx09_137doc_bm25_zero_corpus,
    build_smoke_2x3_dataset,
)
from w07_retrieval.bm25 import BM25Index, analyze_text
from w07_retrieval.chunker_c0 import chunk_corpus_c0
from w07_retrieval.chunker_c1 import chunk_corpus_c1
from w07_retrieval.dense import (
    DenseIndex,
    MockEmbedder,
    OfflineDenseEmbedder,
    get_embedder,
)
from w07_retrieval.fusion import collapse_chunk_scores, fuse_rrf
from w07_retrieval.runner import run_benchmark
from w07_retrieval.sanitizer import sanitize_canonical_to_view
from w07_retrieval.schema import load_canonical_document
from w07_retrieval.visibility import load_minilm_tokenizer

EXPECTED_RANKING_KEYS = frozenset(
    {
        "cell_id",
        "chunker",
        "retriever",
        "query_id",
        "rank",
        "document_id",
        "score",
        "rep_chunk_id",
        "rep_chunk_index",
        "assembled_text",
        "assembled_segments",
        "c_full_s_spans",
        "c_vis_s_spans",
        "leg_ranks",
        "leg_rep_chunks",
    }
)


@pytest.mark.parametrize(("input_text", "expected_tokens"), FX06_GOLDEN_SAMPLES)
def test_fx06_bm25_analyzer_20_frozen_strings(
    input_text: str, expected_tokens: list[str]
) -> None:
    assert analyze_text(input_text) == expected_tokens


def test_fx06_missing_underthesea_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def _blocking_import(name: str, *args, **kwargs):
        if name == "underthesea" or name.startswith("underthesea."):
            raise ImportError("Simulated missing underthesea")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "underthesea", raising=False)
    monkeypatch.setattr(builtins, "__import__", _blocking_import)
    with pytest.raises((ImportError, RuntimeError)):
        analyze_text("Phở Hà Nội ngon tuyệt.")


def test_fx07_offline_dense_snapshot_no_mock_no_cutoff(snapshot_dir: Path) -> None:
    with pytest.raises(RuntimeError):
        MockEmbedder()
    with pytest.raises(RuntimeError):
        get_embedder()

    embedder = OfflineDenseEmbedder(snapshot_dir=snapshot_dir)
    assert embedder.snapshot_id == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"

    vecs_1 = embedder.encode(["Phở Hà Nội", "Vịnh Hạ Long"])
    vecs_2 = embedder.encode(["Phở Hà Nội", "Vịnh Hạ Long"])
    assert vecs_1.dtype == np.float32
    assert vecs_1.shape == (2, 384)
    assert np.allclose(np.linalg.norm(vecs_1, axis=1), 1.0, atol=1e-5)
    assert np.array_equal(vecs_1, vecs_2)

    # Verify min_similarity=0.3 is DISABLED: low-similarity unrelated docs are retained
    tok = load_minilm_tokenizer(snapshot_dir)
    docs = [
        load_canonical_document(
            {
                "document_id": f"doc-low-{i}",
                "source_type": "wikipedia_vi",
                "title": f"Quantum Mechanics Topic {i}",
                "language": "en",
                "source_lineage_id": f"lin-low-{i}",
                "poi_id": None,
                "city": None,
                "canonical_text_S": (
                    "== Physics ==\n"
                    f"Non-relativistic Schrodinger wave equation eigenvalue spectrum number {i} in Hilbert space."
                ),
            }
        )
        for i in range(1, 5)
    ]
    san_by_doc = {
        d.document_id: sanitize_canonical_to_view(d.canonical_text_S) for d in docs
    }
    chunks, _ = chunk_corpus_c1(docs, san_by_doc, tok)
    dense_idx = DenseIndex(chunks, embedder)
    scores = dense_idx.score_chunks("Quán phở bò ngon ở phố cổ Hà Nội mở cửa sáng")
    assert float(np.max(scores)) < 0.30
    ranked = collapse_chunk_scores(
        chunks, scores, retriever_name="Dense", min_score_exclusive=None
    )
    assert len(ranked) == 4


def test_fx08_doc_collapse_returns_all_10_distinct_docs(snapshot_dir: Path) -> None:
    tok = load_minilm_tokenizer(snapshot_dir)
    docs = build_fx08_collapse_corpus()
    san_by_doc = {
        d.document_id: sanitize_canonical_to_view(d.canonical_text_S) for d in docs
    }
    chunks, _ = chunk_corpus_c0(docs, san_by_doc, tok)
    doc01_chunks = [c for c in chunks if c.document_id == "doc-01-dominant"]
    assert len(doc01_chunks) >= 50

    query = "phở bò gia truyền phố cổ Hà Nội"
    bm25_idx = BM25Index(chunks)
    bm25_scores = bm25_idx.score_chunks(query)
    bm25_ranked = collapse_chunk_scores(
        chunks, bm25_scores, retriever_name="BM25", min_score_exclusive=0.0
    )
    assert len(bm25_ranked) == 10
    assert len({r.document_id for r in bm25_ranked}) == 10

    embedder = OfflineDenseEmbedder(snapshot_dir=snapshot_dir)
    dense_idx = DenseIndex(chunks, embedder)
    dense_scores = dense_idx.score_chunks(query)
    dense_ranked = collapse_chunk_scores(
        chunks, dense_scores, retriever_name="Dense", min_score_exclusive=None
    )
    assert len(dense_ranked) == 10
    assert len({r.document_id for r in dense_ranked}) == 10


def test_fx09_bm25_zero_score_excluded_and_rrf_zero_contribution(
    snapshot_dir: Path,
) -> None:
    tok = load_minilm_tokenizer(snapshot_dir)
    docs = build_fx09_137doc_bm25_zero_corpus()
    san_by_doc = {
        d.document_id: sanitize_canonical_to_view(d.canonical_text_S) for d in docs
    }
    chunks, _ = chunk_corpus_c1(docs, san_by_doc, tok)

    query = "bún chả Hương Liên Lê Văn Hưu"
    bm25_idx = BM25Index(chunks)
    bm25_scores = bm25_idx.score_chunks(query)
    bm25_ranked = collapse_chunk_scores(
        chunks, bm25_scores, retriever_name="BM25", min_score_exclusive=0.0
    )
    assert len(bm25_ranked) == 2
    assert {r.document_id for r in bm25_ranked} == {"doc-match-001", "doc-match-002"}

    embedder = OfflineDenseEmbedder(snapshot_dir=snapshot_dir)
    dense_idx = DenseIndex(chunks, embedder)
    dense_scores = dense_idx.score_chunks(query)
    dense_ranked = collapse_chunk_scores(
        chunks, dense_scores, retriever_name="Dense", min_score_exclusive=None
    )
    assert len(dense_ranked) == 137

    rrf_ranked = fuse_rrf(bm25_ranked, dense_ranked, rrf_k=60, candidate_depth=50)
    zero_bm25_in_dense_top50 = [
        r
        for r in rrf_ranked
        if r.document_id.startswith("doc-zero-") and r.leg_ranks["Dense"] is not None
    ]
    assert len(zero_bm25_in_dense_top50) >= 1
    for entry in zero_bm25_in_dense_top50:
        assert entry.leg_ranks["BM25"] is None
        r_d = entry.leg_ranks["Dense"]
        assert r_d is not None
        assert entry.score == pytest.approx(1.0 / (60 + r_d), abs=1e-12)


def test_2x3_matrix_cli_smoke(tmp_path: Path, snapshot_dir: Path) -> None:
    corpus_records, query_records = build_smoke_2x3_dataset()
    corpus_path = tmp_path / "corpus.jsonl"
    queries_path = tmp_path / "queries.jsonl"
    out_dir = tmp_path / "out"

    corpus_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in corpus_records) + "\n",
        encoding="utf-8",
    )
    queries_path.write_text(
        "\n".join(json.dumps(q, ensure_ascii=False) for q in query_records) + "\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["HF_DATASETS_OFFLINE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env["TOKENIZERS_PARALLELISM"] = "false"
    src_root = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = (
        src_root
        if not env.get("PYTHONPATH")
        else f"{src_root}{os.pathsep}{env['PYTHONPATH']}"
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "w07_retrieval.runner",
            "--corpus",
            str(corpus_path),
            "--queries",
            str(queries_path),
            "--output-dir",
            str(out_dir),
            "--snapshot-dir",
            str(snapshot_dir),
            "--packet-salt",
            "SMOKE_SALT",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0

    rankings_path = out_dir / "g3_sealed_rankings_v1.jsonl"
    manifest_path = out_dir / "g3_sealed_rankings_v1_manifest.json"
    chunks_path = out_dir / "chunks_manifest.jsonl"
    packet_path = out_dir / "blind_annotation_packet.jsonl"
    assert rankings_path.is_file()
    assert manifest_path.is_file()
    assert chunks_path.is_file()
    assert packet_path.is_file()

    rankings_bytes = rankings_path.read_bytes()
    assert b"\r\n" not in rankings_bytes
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["rankings_file"] == "g3_sealed_rankings_v1.jsonl"
    assert manifest["rankings_sha256"] == hashlib.sha256(rankings_bytes).hexdigest()
    assert manifest["snapshot_id"] == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"

    rows = [json.loads(ln) for ln in rankings_bytes.decode("utf-8").splitlines() if ln]
    assert len(rows) == manifest["row_count"]
    assert {r["cell_id"] for r in rows} == {
        "C0-BM25",
        "C0-Dense",
        "C0-RRF",
        "C1-BM25",
        "C1-Dense",
        "C1-RRF",
    }
    for row in rows:
        assert set(row.keys()) == EXPECTED_RANKING_KEYS

    chunk_rows = [json.loads(ln) for ln in chunks_path.read_text(encoding="utf-8").splitlines() if ln]
    c1_rows = [c for c in chunk_rows if c["chunker"] == "C1"]
    assert len(c1_rows) > 0
    assert all(c["token_count_with_special"] <= 128 for c in c1_rows)

    pkt_rows = [json.loads(ln) for ln in packet_path.read_text(encoding="utf-8").splitlines() if ln]
    assert len(pkt_rows) > 0
    for prow in pkt_rows:
        assert set(prow.keys()) == {
            "packet_item_uuid",
            "query_id",
            "query_text",
            "document_id",
            "source_type",
            "language",
            "canonical_text_S",
        }

    # Verify zero coupling in a clean subprocess & AST scan (order-independent across full pytest runs)
    decouple_proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            (
                "import sys, w07_retrieval; "
                "import w07_retrieval.schema, w07_retrieval.sanitizer, "
                "w07_retrieval.chunker_c0, w07_retrieval.chunker_c1, "
                "w07_retrieval.visibility, w07_retrieval.bm25, "
                "w07_retrieval.dense, w07_retrieval.fusion, "
                "w07_retrieval.blind_packet, w07_retrieval.runner; "
                "assert not any(m == 'apps.ai_service' or m.startswith('apps.ai_service.') "
                "or m == 'w07_g4_scorer' or m.startswith('w07_g4_scorer.') for m in sys.modules)"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert decouple_proc.returncode == 0

    retrieval_pkg_dir = Path(src_root) / "w07_retrieval"
    for py_file in sorted(retrieval_pkg_dir.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(("apps.ai_service", "w07_g4_scorer", "wanderai"))
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(("apps.ai_service", "w07_g4_scorer", "wanderai"))


def test_fx07_dense_index_rejects_non_offline_stub_and_runner_dedups_cells(
    tmp_path: Path, snapshot_dir: Path
) -> None:
    tok = load_minilm_tokenizer(snapshot_dir)
    doc = load_canonical_document(
        {
            "document_id": "stub-guard-doc",
            "source_type": "wikipedia_vi",
            "title": "Hồ Tây",
            "language": "vi",
            "canonical_text_S": "== Giới thiệu ==\nHồ Tây là hồ nước ngọt lớn nhất tại thủ đô Hà Nội.",
        }
    )
    san = sanitize_canonical_to_view(doc.canonical_text_S)
    chunks, _ = chunk_corpus_c1([doc], {doc.document_id: san}, tok)

    class CustomDummyEncoder:
        model_name = "custom-encoder"

        def encode(self, texts: list[str]) -> np.ndarray:
            arr = np.ones((len(texts), 384), dtype=np.float32)
            return arr / np.linalg.norm(arr, axis=1, keepdims=True)

    with pytest.raises(RuntimeError):
        DenseIndex(chunks, CustomDummyEncoder())  # type: ignore[arg-type]

    uninit_embedder = OfflineDenseEmbedder.__new__(OfflineDenseEmbedder)
    with pytest.raises(RuntimeError):
        DenseIndex(chunks, uninit_embedder)

    # Verify runner deduplicates --cells preserving order
    corpus_records, query_records = build_smoke_2x3_dataset()
    corpus_path = tmp_path / "corpus.jsonl"
    queries_path = tmp_path / "queries.jsonl"
    out_dir = tmp_path / "dedup_out"
    corpus_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in corpus_records) + "\n",
        encoding="utf-8",
    )
    queries_path.write_text(
        "\n".join(json.dumps(q, ensure_ascii=False) for q in query_records) + "\n",
        encoding="utf-8",
    )

    summary = run_benchmark(
        corpus_path=corpus_path,
        queries_path=queries_path,
        output_dir=out_dir,
        snapshot_dir=snapshot_dir,
        cells=["C1-BM25", "C0-BM25", "C1-BM25"],
    )
    assert summary["cells"] == ["C1-BM25", "C0-BM25"]
    manifest = json.loads(
        (out_dir / "g3_sealed_rankings_v1_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["cells"] == ["C1-BM25", "C0-BM25"]
