"""CLI and programmatic runner for the 2x3 offline retrieval engine.

Enforces strict separation between:
- `synthetic-prep` (default pre-freeze mode for synthetic unit/E2E verification; hard-blocks real 137-document corpus and quarantined evaluation artifacts), and
- `formal-execution` (fail-closed mode requiring a cryptographically signed Owner authorization receipt and a hash-verified frozen 137-document corpus receipt; plain environment variables such as W07_G15_FROZEN=1 / W07_OWNER_AUTHORIZED=1 are strictly rejected).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence

from w07_retrieval.blind_packet import export_multi_query_blind_packet_jsonl
from w07_retrieval.bm25 import BM25Index
from w07_retrieval.chunker_c0 import chunk_corpus_c0
from w07_retrieval.chunker_c1 import chunk_corpus_c1
from w07_retrieval.dense import DenseIndex, OfflineDenseEmbedder
from w07_retrieval.fusion import (
    RRF_CANDIDATE_DEPTH,
    RRF_K,
    RankedDocument,
    collapse_chunk_scores,
    fuse_rrf,
)
from w07_retrieval.sanitizer import SanitizationResult, sanitize_canonical_to_view
from w07_retrieval.schema import (
    PINNED_SNAPSHOT_ID,
    PINNED_TOKENIZER_SHA256,
    CanonicalDocument,
    ChunkRecord,
    QueryRecord,
    RankingRow,
    load_corpus_jsonl,
    load_queries_jsonl,
)
from w07_retrieval.visibility import load_minilm_tokenizer, resolve_snapshot_dir

ExecutionMode = Literal["synthetic-prep", "formal-execution"]
VALID_EXECUTION_MODES: tuple[str, ...] = ("synthetic-prep", "formal-execution")

ALL_CELLS: tuple[str, ...] = (
    "C0-BM25",
    "C0-Dense",
    "C0-RRF",
    "C1-BM25",
    "C1-Dense",
    "C1-RRF",
)

# Live Owner Ed25519 trust anchor for formal G3 execution remains None (unprovisioned)
# while G1.5 is in PRE-FREEZE HOLD. Plain environment variables NEVER unlock this gate.
PINNED_LIVE_OWNER_G3_PUBKEY_HEX: Optional[str] = None

OWNER_AUTH_RECEIPT_SCHEMA_V1 = "W07_G15_OWNER_EXECUTION_AUTHORIZATION_RECEIPT_V1"
FROZEN_CORPUS_RECEIPT_SCHEMA_V1 = "W07_FROZEN_137_CORPUS_RECEIPT_V1"
ED25519_FORMAL_EXECUTION_DOMAIN_ASCII = "W07-G15-G3-FORMAL-EXECUTION-AUTH-V1"
ED25519_FORMAL_EXECUTION_DOMAIN_TAG = b"W07-G15-G3-FORMAL-EXECUTION-AUTH-V1\x00"

EXPECTED_ELIGIBLE_DOC_COUNT = 137
EXPECTED_CITY_COUNTS: Dict[str, int] = {
    "Hà Nội": 59,
    "Đà Nẵng": 52,
    "Hạ Long": 26,
}
EXPECTED_R_AUDIT_REMOVED = 46
EXPECTED_R_AUDIT_REMAINING = 0
EXPECTED_SANITIZED_VIEW_V_137_SHA256 = (
    "046424e521f967f6c5575da1eeb914e5d340a118861c0cf04ca45256b364533d"
)

FORBIDDEN_SYNTHETIC_PATH_TOKENS: tuple[str, ...] = (
    "poi_knowledge_" + "acquired_v1",
    "w07_b1a_existing_" + "poi_knowledge_audit_v1",
    "gomate_places_" + "freeze_v2",
    "w07_frozen_137_" + "doc_provenance_v1",
    "w07_review_target_" + "60_pois_v1",
    "g15_r01_real_" + "corpus",
    "final" + "-50",
    "final" + "_50",
    "dev" + "-5",
    "dev" + "_5",
    "t0" + "_private",
)

KNOWN_PROTECTED_ARTIFACT_SHA256S: frozenset[str] = frozenset(
    {
        "9b0ed36e060924057872a2e8fe9941940f7bc3455f2c9cad21cdc9a9c1141fda",
        "433c722dd2f03946ab0a15830b53ef628d76937fa2e8e63a9939e73bb469e563",
        "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444",
        "849e6b113cf0c2b795966d2e5532747cf136c85bc763afe18d29276253a196f2",
        "3a065165d038f300f5dc422180fcaf3cef265ac1a100ea8e841daaba1a82d5d4",
        "e7656acb6bdd0ecbc5f35a2026e275fd31e02489eee838e641114f981522312d",
        "9bb5de093a6e75f16f2ef796f8a44a25a4ae3dbbeb44b53a6d55c0ab206c23b0",
    }
)

_HEX64_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_HEX128_RE = re.compile(r"\A[0-9a-f]{128}\Z")


def _enforce_offline_env() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_owner_auth_signing_bytes(receipt_payload: Dict[str, Any]) -> bytes:
    """Build domain-separated canonical UTF-8 JSON bytes for Owner Ed25519 signature verification."""
    unsigned = {
        k: v
        for k, v in receipt_payload.items()
        if k != "owner_detached_signature_hex"
    }
    body = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return ED25519_FORMAL_EXECUTION_DOMAIN_TAG + body


def _verify_ed25519_signature(
    *,
    pubkey_hex: str,
    signature_hex: str,
    message: bytes,
) -> None:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise RuntimeError(
            f"cryptography package is required for formal-execution Ed25519 verification: {exc}"
        ) from exc

    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
        pub.verify(bytes.fromhex(signature_hex), message)
    except (ValueError, InvalidSignature) as exc:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_INVALID_ED25519_SIGNATURE: "
            "Owner detached Ed25519 signature verification failed."
        ) from exc


def validate_synthetic_prep_boundaries(
    *,
    corpus_path: Path,
    queries_path: Path,
    docs: Optional[Sequence[CanonicalDocument]] = None,
) -> None:
    """Enforce that `synthetic-prep` never touches the real 137-document corpus or protected artifacts."""
    for label, target in (("corpus_path", corpus_path), ("queries_path", queries_path)):
        lower_path = str(target).lower()
        for token in FORBIDDEN_SYNTHETIC_PATH_TOKENS:
            if token in lower_path:
                raise PermissionError(
                    f"SYNTHETIC_PREP_PROTECTED_ARTIFACT_FORBIDDEN: {label} ({target.name!r}) "
                    f"matches protected token {token!r}; real corpus and quarantined evaluation "
                    "artifacts are forbidden in synthetic-prep mode."
                )
        if target.is_file():
            digest = _sha256_file(target)
            if digest in KNOWN_PROTECTED_ARTIFACT_SHA256S:
                raise PermissionError(
                    f"SYNTHETIC_PREP_PROTECTED_DIGEST_FORBIDDEN: {label} SHA-256 ({digest}) "
                    "matches a frozen W07 real-corpus or quarantined artifact."
                )

    if docs is not None:
        if len(docs) == EXPECTED_ELIGIBLE_DOC_COUNT:
            raise PermissionError(
                "SYNTHETIC_PREP_REAL_137_CORPUS_FORBIDDEN: 137-document corpus cannot be "
                "indexed or evaluated in synthetic-prep mode (requires formal-execution "
                "with signed Owner authorization and frozen corpus receipts after G1.5 freeze)."
            )
        for doc in docs:
            if doc.document_id.startswith("w07-b1b-doc-"):
                raise PermissionError(
                    f"SYNTHETIC_PREP_REAL_B1B_DOC_FORBIDDEN: document_id {doc.document_id!r} "
                    "belongs to the frozen W07-B1B corpus and is forbidden in synthetic-prep mode."
                )


def validate_formal_execution_gate(
    *,
    corpus_path: Path,
    queries_path: Path,
    owner_auth_receipt_path: Optional[Path],
    frozen_corpus_receipt_path: Optional[Path],
    _test_only_trusted_owner_pubkey_hex: Optional[str] = None,
) -> Dict[str, Any]:
    """Fail-closed gate for `formal-execution` mode.

    Plain environment variables (W07_G15_FROZEN, W07_OWNER_AUTHORIZED) NEVER grant
    formal execution authority. Requires both a hash-verified frozen corpus receipt
    and a cryptographically verified Owner Ed25519 authorization receipt.
    """
    env_spoof_present = (
        os.environ.get("W07_G15_FROZEN") == "1"
        or os.environ.get("W07_OWNER_AUTHORIZED") == "1"
    )
    if owner_auth_receipt_path is None or frozen_corpus_receipt_path is None:
        spoof_note = (
            " Plain environment variables (W07_G15_FROZEN / W07_OWNER_AUTHORIZED) "
            "were detected and rejected: environment flags cannot simulate Owner authority."
            if env_spoof_present
            else ""
        )
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_MISSING_RECEIPTS: formal-execution requires both "
            "--owner-auth-receipt and --frozen-corpus-receipt files." + spoof_note
        )

    owner_p = Path(owner_auth_receipt_path)
    frozen_p = Path(frozen_corpus_receipt_path)
    if not owner_p.is_file() or owner_p.is_symlink():
        raise PermissionError(
            f"FORMAL_EXECUTION_BLOCKED_MISSING_RECEIPTS: owner_auth_receipt not found or not regular file: {owner_p}"
        )
    if not frozen_p.is_file() or frozen_p.is_symlink():
        raise PermissionError(
            f"FORMAL_EXECUTION_BLOCKED_MISSING_RECEIPTS: frozen_corpus_receipt not found or not regular file: {frozen_p}"
        )
    if not corpus_path.is_file():
        raise FileNotFoundError(f"Corpus file not found: {corpus_path}")
    if not queries_path.is_file():
        raise FileNotFoundError(f"Queries file not found: {queries_path}")

    try:
        frozen_raw = json.loads(frozen_p.read_text(encoding="utf-8"))
        owner_raw = json.loads(owner_p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PermissionError(
            f"FORMAL_EXECUTION_BLOCKED_MALFORMED_RECEIPT_JSON: {exc}"
        ) from exc

    if type(frozen_raw) is not dict or type(owner_raw) is not dict:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_MALFORMED_RECEIPT_JSON: receipt root must be a JSON object."
        )

    # 1. Validate frozen corpus receipt
    if frozen_raw.get("schema_version") != FROZEN_CORPUS_RECEIPT_SCHEMA_V1:
        raise PermissionError(
            f"FORMAL_EXECUTION_BLOCKED_INVALID_CORPUS_RECEIPT_SCHEMA: expected {FROZEN_CORPUS_RECEIPT_SCHEMA_V1!r}"
        )
    if frozen_raw.get("g15_frozen") is not True:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_G15_NOT_FROZEN: frozen_corpus_receipt.g15_frozen is not True."
        )
    if frozen_raw.get("eligible_document_count") != EXPECTED_ELIGIBLE_DOC_COUNT:
        raise PermissionError(
            f"FORMAL_EXECUTION_BLOCKED_CORPUS_COUNT_MISMATCH: expected {EXPECTED_ELIGIBLE_DOC_COUNT} docs."
        )
    if frozen_raw.get("city_counts") != EXPECTED_CITY_COUNTS:
        raise PermissionError(
            f"FORMAL_EXECUTION_BLOCKED_CITY_COUNTS_MISMATCH: expected {EXPECTED_CITY_COUNTS}."
        )
    if (
        frozen_raw.get("r_audit_tags_removed") != EXPECTED_R_AUDIT_REMOVED
        or frozen_raw.get("r_audit_tags_remaining") != EXPECTED_R_AUDIT_REMAINING
    ):
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_R_AUDIT_RECEIPT_MISMATCH: expected 46 removed / 0 remaining."
        )
    if frozen_raw.get("sanitized_view_v_sha256") != EXPECTED_SANITIZED_VIEW_V_137_SHA256:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_SANITIZED_V_HASH_MISMATCH: sanitized_view_v_sha256 mismatch."
        )
    if frozen_raw.get("pinned_tokenizer_json_sha256") != PINNED_TOKENIZER_SHA256:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_TOKENIZER_SHA256_MISMATCH: frozen_corpus_receipt tokenizer SHA-256 mismatch."
        )
    annex_sha = frozen_raw.get("annex_g15_sha256")
    if type(annex_sha) is not str or _HEX64_RE.fullmatch(annex_sha) is None:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_INVALID_ANNEX_SHA256: invalid annex_g15_sha256 in frozen_corpus_receipt."
        )

    actual_corpus_sha = _sha256_file(corpus_path)
    actual_queries_sha = _sha256_file(queries_path)
    actual_frozen_receipt_sha = _sha256_file(frozen_p)

    if frozen_raw.get("corpus_sha256") != actual_corpus_sha:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_CORPUS_HASH_MISMATCH: frozen_corpus_receipt.corpus_sha256 "
            f"({frozen_raw.get('corpus_sha256')!r}) != actual corpus SHA-256 ({actual_corpus_sha!r})."
        )

    # 2. Validate Owner execution authorization receipt
    if owner_raw.get("schema_version") != OWNER_AUTH_RECEIPT_SCHEMA_V1:
        raise PermissionError(
            f"FORMAL_EXECUTION_BLOCKED_INVALID_OWNER_RECEIPT_SCHEMA: expected {OWNER_AUTH_RECEIPT_SCHEMA_V1!r}"
        )
    if (
        owner_raw.get("g15_annex_frozen") is not True
        or owner_raw.get("owner_authorized_g3_execution") is not True
    ):
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_NOT_AUTHORIZED: Owner receipt does not grant G1.5 freeze & G3 execution."
        )
    if owner_raw.get("authorized_execution_mode") != "formal-execution":
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_MODE_MISMATCH: authorized_execution_mode must be 'formal-execution'."
        )
    if (
        owner_raw.get("tokenizer_erratum_resolved") is not True
        or owner_raw.get("pinned_tokenizer_json_sha256") != PINNED_TOKENIZER_SHA256
    ):
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_TOKENIZER_ERRATUM_UNRESOLVED: Owner receipt must confirm "
            "tokenizer.json SHA-256 erratum resolution."
        )
    if owner_raw.get("annex_g15_sha256") != annex_sha:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_ANNEX_HASH_MISMATCH: Owner receipt annex_g15_sha256 mismatch."
        )
    if owner_raw.get("corpus_sha256") != actual_corpus_sha:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_CORPUS_HASH_MISMATCH: Owner receipt corpus_sha256 mismatch."
        )
    if owner_raw.get("queries_sha256") != actual_queries_sha:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_QUERIES_HASH_MISMATCH: Owner receipt queries_sha256 mismatch."
        )
    if owner_raw.get("frozen_corpus_receipt_sha256") != actual_frozen_receipt_sha:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_FROZEN_RECEIPT_BINDING_MISMATCH: Owner receipt "
            "frozen_corpus_receipt_sha256 does not match frozen_corpus_receipt file."
        )
    if owner_raw.get("ed25519_domain_tag") != ED25519_FORMAL_EXECUTION_DOMAIN_ASCII:
        raise PermissionError(
            f"FORMAL_EXECUTION_BLOCKED_DOMAIN_TAG_MISMATCH: expected {ED25519_FORMAL_EXECUTION_DOMAIN_ASCII!r}"
        )

    pubkey_hex = owner_raw.get("owner_ed25519_pubkey_hex")
    sig_hex = owner_raw.get("owner_detached_signature_hex")
    if type(pubkey_hex) is not str or _HEX64_RE.fullmatch(pubkey_hex) is None:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_MALFORMED_PUBKEY: owner_ed25519_pubkey_hex must be 64 lowercase hex chars."
        )
    if type(sig_hex) is not str or _HEX128_RE.fullmatch(sig_hex) is None:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_MISSING_OR_MALFORMED_SIGNATURE: owner_detached_signature_hex must be 128 lowercase hex chars."
        )

    effective_trusted_pubkey = (
        _test_only_trusted_owner_pubkey_hex
        if _test_only_trusted_owner_pubkey_hex is not None
        else PINNED_LIVE_OWNER_G3_PUBKEY_HEX
    )
    if effective_trusted_pubkey is None:
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_UNPINNED_LIVE_OWNER_KEY: PINNED_LIVE_OWNER_G3_PUBKEY_HEX is None "
            "(pre-freeze HOLD). Self-declared public keys without a pinned Owner trust anchor are rejected."
        )
    if not hmac.compare_digest(pubkey_hex.lower(), effective_trusted_pubkey.lower()):
        raise PermissionError(
            "FORMAL_EXECUTION_BLOCKED_PUBKEY_MISMATCH: receipt owner_ed25519_pubkey_hex does not match pinned Owner trust anchor."
        )

    signing_bytes = canonical_owner_auth_signing_bytes(owner_raw)
    _verify_ed25519_signature(
        pubkey_hex=pubkey_hex,
        signature_hex=sig_hex,
        message=signing_bytes,
    )

    return {
        "execution_mode": "formal-execution",
        "formal_g15_frozen_verified": True,
        "owner_authorization_verified": True,
        "owner_auth_receipt_sha256": _sha256_file(owner_p),
        "frozen_corpus_receipt_sha256": actual_frozen_receipt_sha,
        "corpus_sha256": actual_corpus_sha,
        "queries_sha256": actual_queries_sha,
        "trust_anchor_mode": (
            "EPHEMERAL_UNIT_TEST_SANDBOX_ONLY"
            if _test_only_trusted_owner_pubkey_hex is not None
            else "PINNED_LIVE_OWNER_TRUST_ANCHOR"
        ),
    }


def _write_jsonl_lf(path: Path, records: Sequence[dict[str, Any]]) -> bytes:
    payload = "\n".join(
        json.dumps(rec, ensure_ascii=False, sort_keys=True) for rec in records
    )
    if payload:
        payload += "\n"
    raw_bytes = payload.encode("utf-8")
    path.write_bytes(raw_bytes)
    return raw_bytes


def run_benchmark(
    *,
    corpus_path: Path,
    queries_path: Path,
    output_dir: Path,
    snapshot_dir: Optional[Path] = None,
    packet_salt: Optional[str] = None,
    cells: Optional[Sequence[str]] = None,
    pool_depth: int = 10,
    execution_mode: ExecutionMode = "synthetic-prep",
    owner_auth_receipt_path: Optional[Path] = None,
    frozen_corpus_receipt_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute the standalone offline 2x3 retrieval pipeline and write sealed artifacts."""
    _enforce_offline_env()

    if execution_mode not in VALID_EXECUTION_MODES:
        raise ValueError(
            f"Invalid execution_mode {execution_mode!r}; valid choices: {VALID_EXECUTION_MODES}"
        )

    c_path = Path(corpus_path)
    q_path = Path(queries_path)

    formal_gate_receipt: Optional[Dict[str, Any]] = None
    if execution_mode == "formal-execution":
        formal_gate_receipt = validate_formal_execution_gate(
            corpus_path=c_path,
            queries_path=q_path,
            owner_auth_receipt_path=owner_auth_receipt_path,
            frozen_corpus_receipt_path=frozen_corpus_receipt_path,
        )
    else:
        validate_synthetic_prep_boundaries(
            corpus_path=c_path,
            queries_path=q_path,
            docs=None,
        )

    selected_cells = (
        list(dict.fromkeys(cells)) if cells is not None else list(ALL_CELLS)
    )
    for c in selected_cells:
        if c not in ALL_CELLS:
            raise ValueError(f"Unknown cell_id {c!r}; valid choices: {ALL_CELLS}")

    docs: List[CanonicalDocument] = load_corpus_jsonl(c_path)
    queries: List[QueryRecord] = load_queries_jsonl(q_path)

    if execution_mode == "synthetic-prep":
        validate_synthetic_prep_boundaries(
            corpus_path=c_path,
            queries_path=q_path,
            docs=docs,
        )

    sanitized_by_doc: Dict[str, SanitizationResult] = {
        doc.document_id: sanitize_canonical_to_view(doc.canonical_text_S)
        for doc in docs
    }

    if execution_mode == "formal-execution":
        if len(docs) != EXPECTED_ELIGIBLE_DOC_COUNT:
            raise PermissionError(
                f"FORMAL_EXECUTION_BLOCKED_DOC_COUNT: expected {EXPECTED_ELIGIBLE_DOC_COUNT} docs, got {len(docs)}"
            )
        total_removed = sum(
            len(res.removed_tags) for res in sanitized_by_doc.values()
        )
        if total_removed != EXPECTED_R_AUDIT_REMOVED:
            raise PermissionError(
                f"FORMAL_EXECUTION_BLOCKED_R_AUDIT_COUNT: expected {EXPECTED_R_AUDIT_REMOVED} removed tags, got {total_removed}"
            )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    resolved_snap = resolve_snapshot_dir(snapshot_dir)
    tokenizer = load_minilm_tokenizer(resolved_snap, verify_sha256=True)

    needs_dense = any(c.endswith("-Dense") or c.endswith("-RRF") for c in selected_cells)
    embedder: Optional[OfflineDenseEmbedder] = (
        OfflineDenseEmbedder(snapshot_dir=resolved_snap) if needs_dense else None
    )
    snapshot_id = embedder.snapshot_id if embedder is not None else (
        resolved_snap.name or PINNED_SNAPSHOT_ID
    )

    active_arms: list[Literal["C0", "C1"]] = []
    if any(c.startswith("C0-") for c in selected_cells):
        active_arms.append("C0")
    if any(c.startswith("C1-") for c in selected_cells):
        active_arms.append("C1")

    chunks_by_arm: Dict[str, List[ChunkRecord]] = {}
    if "C0" in active_arms:
        c0_chunks, _ = chunk_corpus_c0(docs, sanitized_by_doc, tokenizer)
        chunks_by_arm["C0"] = c0_chunks
    if "C1" in active_arms:
        c1_chunks, _ = chunk_corpus_c1(docs, sanitized_by_doc, tokenizer)
        chunks_by_arm["C1"] = c1_chunks

    ranking_dicts: List[Dict[str, Any]] = []
    pooled_by_query: Dict[str, List[Dict[str, Any]]] = {q.query_id: [] for q in queries}

    for arm in active_arms:
        arm_chunks = chunks_by_arm[arm]
        need_bm25 = f"{arm}-BM25" in selected_cells or f"{arm}-RRF" in selected_cells
        need_dense = f"{arm}-Dense" in selected_cells or f"{arm}-RRF" in selected_cells

        bm25_index = BM25Index(arm_chunks) if need_bm25 else None
        dense_index = (
            DenseIndex(arm_chunks, embedder)
            if (need_dense and embedder is not None)
            else None
        )

        for q in queries:
            bm25_ranked: Optional[List[RankedDocument]] = None
            dense_ranked: Optional[List[RankedDocument]] = None

            if bm25_index is not None:
                bm25_scores = bm25_index.score_chunks(q.query_text)
                bm25_ranked = collapse_chunk_scores(
                    arm_chunks,
                    bm25_scores,
                    retriever_name="BM25",
                    min_score_exclusive=0.0,
                )

            if dense_index is not None:
                dense_scores = dense_index.score_chunks(q.query_text)
                dense_ranked = collapse_chunk_scores(
                    arm_chunks,
                    dense_scores,
                    retriever_name="Dense",
                    min_score_exclusive=None,
                )

            cell_results: Dict[str, tuple[Literal["BM25", "Dense", "RRF"], List[RankedDocument]]] = {}
            if f"{arm}-BM25" in selected_cells and bm25_ranked is not None:
                cell_results[f"{arm}-BM25"] = ("BM25", bm25_ranked)
            if f"{arm}-Dense" in selected_cells and dense_ranked is not None:
                cell_results[f"{arm}-Dense"] = ("Dense", dense_ranked)
            if f"{arm}-RRF" in selected_cells:
                assert bm25_ranked is not None and dense_ranked is not None
                rrf_ranked = fuse_rrf(
                    bm25_ranked,
                    dense_ranked,
                    rrf_k=RRF_K,
                    candidate_depth=RRF_CANDIDATE_DEPTH,
                )
                cell_results[f"{arm}-RRF"] = ("RRF", rrf_ranked)

            for cell_id, (retriever_name, entries) in cell_results.items():
                for entry in entries:
                    row_obj = RankingRow(
                        cell_id=cell_id,
                        chunker=arm,
                        retriever=retriever_name,
                        query_id=q.query_id,
                        rank=entry.rank,
                        document_id=entry.document_id,
                        score=entry.score,
                        rep_chunk_id=entry.rep_chunk.chunk_id,
                        rep_chunk_index=entry.rep_chunk.chunk_index,
                        assembled_text=entry.rep_chunk.assembled_text,
                        assembled_segments=entry.rep_chunk.assembled_segments,
                        c_full_s_spans=entry.c_full_s_spans,
                        c_vis_s_spans=entry.c_vis_s_spans,
                        leg_ranks=entry.leg_ranks,
                        leg_rep_chunks=entry.leg_rep_chunks,
                    )
                    row_dict = row_obj.to_dict()
                    ranking_dicts.append(row_dict)
                    if pool_depth <= 0 or entry.rank <= pool_depth:
                        pooled_by_query[q.query_id].append(row_dict)

    ranking_dicts.sort(key=lambda r: (r["cell_id"], r["query_id"], r["rank"]))

    rankings_path = out_dir / "g3_sealed_rankings_v1.jsonl"
    rankings_bytes = _write_jsonl_lf(rankings_path, ranking_dicts)
    rankings_sha256 = hashlib.sha256(rankings_bytes).hexdigest()

    authority_status = (
        "FORMAL_G3_SEALED_EXECUTION"
        if execution_mode == "formal-execution"
        else "SYNTHETIC_PREP_ONLY_NOT_G3_PASS"
    )
    manifest: Dict[str, Any] = {
        "rankings_file": "g3_sealed_rankings_v1.jsonl",
        "rankings_sha256": rankings_sha256,
        "row_count": len(ranking_dicts),
        "cells": selected_cells,
        "snapshot_id": snapshot_id,
        "execution_mode": execution_mode,
        "scientific_authority_status": authority_status,
        "formal_g15_frozen_verified": bool(
            formal_gate_receipt and formal_gate_receipt.get("formal_g15_frozen_verified")
        ),
        "owner_authorization_verified": bool(
            formal_gate_receipt and formal_gate_receipt.get("owner_authorization_verified")
        ),
    }
    manifest_path = out_dir / "g3_sealed_rankings_v1_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    all_chunk_dicts = [
        ch.to_manifest_dict()
        for arm in active_arms
        for ch in chunks_by_arm[arm]
    ]
    all_chunk_dicts.sort(
        key=lambda c: (c["chunker"], c["document_id"], c["chunk_index"], c["chunk_id"])
    )
    chunks_manifest_path = out_dir / "chunks_manifest.jsonl"
    _write_jsonl_lf(chunks_manifest_path, all_chunk_dicts)

    packet_path: Optional[Path] = None
    if packet_salt:
        query_lookup = {q.query_id: q.query_text for q in queries}
        corpus_lookup = {doc.document_id: doc for doc in docs}
        pkt_text = export_multi_query_blind_packet_jsonl(
            queries=query_lookup,
            rankings_by_query=pooled_by_query,
            corpus_lookup=corpus_lookup,
            packet_salt=packet_salt,
        )
        if pkt_text:
            pkt_text += "\n"
        packet_path = out_dir / "blind_annotation_packet.jsonl"
        packet_path.write_bytes(pkt_text.encode("utf-8"))

    return {
        "rankings_path": str(rankings_path),
        "manifest_path": str(manifest_path),
        "chunks_manifest_path": str(chunks_manifest_path),
        "packet_path": str(packet_path) if packet_path is not None else None,
        "rankings_sha256": rankings_sha256,
        "row_count": len(ranking_dicts),
        "cells": selected_cells,
        "snapshot_id": snapshot_id,
        "execution_mode": execution_mode,
        "scientific_authority_status": authority_status,
        "formal_g15_frozen_verified": manifest["formal_g15_frozen_verified"],
        "owner_authorization_verified": manifest["owner_authorization_verified"],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="GOMATE W07 Offline 2x3 Retrieval Benchmark Runner (Pre-Freeze)"
    )
    parser.add_argument("--corpus", type=Path, required=True, help="Path to corpus.jsonl")
    parser.add_argument("--queries", type=Path, required=True, help="Path to queries.jsonl")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory")
    parser.add_argument(
        "--execution-mode",
        "--mode",
        dest="execution_mode",
        choices=list(VALID_EXECUTION_MODES),
        default="synthetic-prep",
        help=(
            "Execution mode: 'synthetic-prep' (default pre-freeze synthetic testing) or "
            "'formal-execution' (requires signed Owner receipt and frozen corpus receipt; "
            "plain env vars rejected)."
        ),
    )
    parser.add_argument(
        "--owner-auth-receipt",
        type=Path,
        default=None,
        help="Path to signed W07_G15_OWNER_EXECUTION_AUTHORIZATION_RECEIPT_V1 JSON (required for formal-execution).",
    )
    parser.add_argument(
        "--frozen-corpus-receipt",
        type=Path,
        default=None,
        help="Path to verified W07_FROZEN_137_CORPUS_RECEIPT_V1 JSON (required for formal-execution).",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=None,
        help="Optional path to local HuggingFace MiniLM snapshot",
    )
    parser.add_argument(
        "--packet-salt",
        type=str,
        default=None,
        help="Optional salt to emit blind_annotation_packet.jsonl",
    )
    parser.add_argument(
        "--cells",
        nargs="+",
        choices=list(ALL_CELLS),
        default=list(ALL_CELLS),
        help="Subset of 2x3 retrieval cells to run",
    )
    parser.add_argument(
        "--pool-depth",
        type=int,
        default=10,
        help="Top-N rank depth per cell pooled into blind packet (<=0 pools all)",
    )
    args = parser.parse_args(argv)

    summary = run_benchmark(
        corpus_path=args.corpus,
        queries_path=args.queries,
        output_dir=args.output_dir,
        snapshot_dir=args.snapshot_dir,
        packet_salt=args.packet_salt,
        cells=args.cells,
        pool_depth=args.pool_depth,
        execution_mode=args.execution_mode,
        owner_auth_receipt_path=args.owner_auth_receipt,
        frozen_corpus_receipt_path=args.frozen_corpus_receipt,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
