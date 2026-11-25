"""Contracts, 5-state ontology, shared-lineage non-propagation, SHA-256 verification, and Cert-1..4."""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import math
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "torch",
    "transformers",
    "sentence_transformers",
    "tokenizers",
    "underthesea",
    "w07_retrieval",
    "apps.ai_service",
)

ALLOWED_PACKAGE_IMPORT_ROOTS: frozenset[str] = frozenset(sys.stdlib_module_names) | frozenset(
    {"__future__", "numpy", "scipy", "w07_g4_scorer"}
)

SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

LOCKED_CELLS: tuple[str, ...] = (
    "C0-BM25",
    "C0-Dense",
    "C0-RRF",
    "C1-BM25",
    "C1-Dense",
    "C1-RRF",
)

ANNEX_G15_CONTRASTS_K1_K5: dict[str, tuple[str, str]] = {
    "K1": ("C1-RRF", "C1-BM25"),
    "K2": ("C1-RRF", "C1-Dense"),
    "K3": ("C1-Dense", "C0-Dense"),
    "K4": ("C1-RRF", "C0-RRF"),
    "K5": ("C1-BM25", "C0-BM25"),
}
LOCKED_CONTRASTS_K1_K5: dict[str, tuple[str, str]] = ANNEX_G15_CONTRASTS_K1_K5


def assert_zero_ml_imports() -> None:
    """Fail closed if any ML or retrieval package is present in sys.modules."""
    hits = sorted(
        mod_name
        for mod_name in sys.modules
        if any(mod_name == prefix or mod_name.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    if hits:
        raise RuntimeError(f"FORBIDDEN_ML_OR_RETRIEVER_IMPORT: {hits}")


def assert_g4_package_zero_ml_imports() -> None:
    """Static AST scan of all src/w07_g4_scorer/*.py imports verifying only stdlib+numpy+scipy+w07_g4_scorer."""
    pkg_dir = Path(__file__).resolve().parent
    forbidden_hits: list[str] = []
    disallowed_hits: list[str] = []

    for py_file in sorted(pkg_dir.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod_name = alias.name
                    root = mod_name.split(".", 1)[0]
                    if any(
                        mod_name == prefix or mod_name.startswith(prefix + ".")
                        for prefix in FORBIDDEN_IMPORT_PREFIXES
                    ):
                        forbidden_hits.append(f"{py_file.name}:{node.lineno}:{mod_name}")
                    elif root not in ALLOWED_PACKAGE_IMPORT_ROOTS:
                        disallowed_hits.append(f"{py_file.name}:{node.lineno}:{mod_name}")
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    continue
                mod_name = node.module or ""
                if not mod_name:
                    continue
                root = mod_name.split(".", 1)[0]
                if any(
                    mod_name == prefix or mod_name.startswith(prefix + ".")
                    for prefix in FORBIDDEN_IMPORT_PREFIXES
                ):
                    forbidden_hits.append(f"{py_file.name}:{node.lineno}:{mod_name}")
                elif root not in ALLOWED_PACKAGE_IMPORT_ROOTS:
                    disallowed_hits.append(f"{py_file.name}:{node.lineno}:{mod_name}")

    if forbidden_hits:
        raise RuntimeError(f"FORBIDDEN_ML_OR_RETRIEVER_IMPORT_IN_AST: {forbidden_hits}")
    if disallowed_hits:
        raise RuntimeError(f"DISALLOWED_EXTERNAL_IMPORT_IN_G4_PACKAGE: {disallowed_hits}")


class RelevanceState(str, Enum):
    """Five mutually exclusive relevance states; NA and UNJUDGED never coerce to 0."""

    REL_2 = "REL_2"
    REL_1 = "REL_1"
    REL_0 = "REL_0"
    NA = "NA"
    UNJUDGED = "UNJUDGED"


GAIN_MAP: dict[RelevanceState, int] = {
    RelevanceState.REL_2: 3,
    RelevanceState.REL_1: 1,
    RelevanceState.REL_0: 0,
}


class Cert4Status(str, Enum):
    """Four-state IDCG completeness classification per Annex G1.5 v0.2.1."""

    EXACT_CERTIFIED = "EXACT_CERTIFIED"
    BOUNDED_NOT_EXACT = "BOUNDED_NOT_EXACT"
    ZERO_POSITIVE_EXACT = "ZERO_POSITIVE_EXACT"
    INVALID_UNRESOLVED = "INVALID_UNRESOLVED"


@dataclass(frozen=True)
class RankingManifest:
    rankings_file: str
    rankings_sha256: str
    row_count: int
    cells: tuple[str, ...]
    snapshot_id: str


@dataclass(frozen=True)
class RankingRow:
    cell_id: str
    chunker: str
    retriever: str
    query_id: str
    rank: int
    document_id: str
    score: float
    rep_chunk_id: str
    rep_chunk_index: int
    assembled_text: str
    assembled_segments: tuple[dict[str, Any], ...]
    c_full_s_spans: tuple[tuple[int, int], ...]
    c_vis_s_spans: tuple[tuple[int, int], ...]
    leg_ranks: dict[str, int]
    leg_rep_chunks: dict[str, str]


@dataclass(frozen=True)
class QrelRecord:
    query_id: str
    document_id: str
    label: RelevanceState
    plausible_unsupported_lure: int | None
    evidence_s_spans: tuple[tuple[int, int], ...]
    source_lineage_id: str | None


@dataclass(frozen=True)
class CertResult:
    query_id: str
    cert1_top10_in_pool: float
    cert2_judged_at_10: dict[str, float]
    cert3_full_pool_closed: float
    cert4_status: Cert4Status
    idcg_l: float
    idcg_u: float
    known_count: int
    unjudged_count: int
    zero_exact_empty_z: bool


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_interval_pair(item: Any, field_name: str = "interval") -> tuple[int, int]:
    if not isinstance(item, (tuple, list)) or len(item) != 2:
        raise ValueError(f"Malformed {field_name}: expected 2-element sequence, got {item!r}")
    a, b = item[0], item[1]
    if type(a) is bool or type(b) is bool or type(a) is not int or type(b) is not int:
        raise ValueError(f"Boolean or non-int endpoints forbidden in {field_name}: {item!r}")
    if a < 0 or a > b:
        raise ValueError(f"Invalid interval bounds in {field_name}: {item!r}")
    return (a, b)


def merge_intervals(intervals: Iterable[tuple[int, int] | list[int]]) -> list[tuple[int, int]]:
    validated = [_validate_interval_pair(sp) for sp in intervals]
    cleaned = sorted((a, b) for a, b in validated if a < b)
    if not cleaned:
        return []
    merged: list[tuple[int, int]] = [cleaned[0]]
    for a, b in cleaned[1:]:
        if a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def subtract_intervals(
    base: Iterable[tuple[int, int] | list[int]],
    cut: Iterable[tuple[int, int] | list[int]],
) -> list[tuple[int, int]]:
    base_clean = merge_intervals(base)
    cut_clean = merge_intervals(cut)
    result: list[tuple[int, int]] = []
    for a, b in base_clean:
        cur = [(a, b)]
        for ca, cb in cut_clean:
            nxt: list[tuple[int, int]] = []
            for x, y in cur:
                if cb <= x or ca >= y:
                    nxt.append((x, y))
                else:
                    if x < ca:
                        nxt.append((x, ca))
                    if cb < y:
                        nxt.append((cb, y))
            cur = nxt
        result.extend(cur)
    return merge_intervals(result)


def intervals_contain(
    container: Iterable[tuple[int, int] | list[int]],
    target: Iterable[tuple[int, int] | list[int]],
) -> bool:
    return len(subtract_intervals(target, container)) == 0


def _dcg10_raw(gains: Sequence[int]) -> float:
    return sum(g / math.log2(idx + 2) for idx, g in enumerate(gains[:10]) if g > 0)


def _idcg10_raw(all_gains: Sequence[int]) -> float:
    top_ideal = sorted(all_gains, reverse=True)[:10]
    return _dcg10_raw(top_ideal)


def verify_rankings_manifest(rankings_path: Path | str, manifest_path: Path | str) -> RankingManifest:
    """Verify g3_sealed_rankings_v1.jsonl raw bytes against g3_sealed_rankings_v1_manifest.json."""
    r_path = Path(rankings_path)
    m_path = Path(manifest_path)
    if not r_path.is_file():
        raise FileNotFoundError(f"Rankings file not found: {r_path}")
    if not m_path.is_file():
        raise FileNotFoundError(f"Manifest file not found: {m_path}")

    manifest_raw = json.loads(m_path.read_text(encoding="utf-8"))
    if type(manifest_raw) is not dict:
        raise ValueError("INVALID_RANKINGS_MANIFEST: top-level JSON must be an object")

    expected_sha = manifest_raw.get("rankings_sha256")
    if type(expected_sha) is not str or SHA256_HEX_RE.match(expected_sha) is None:
        raise ValueError(f"MALFORMED_RANKINGS_SHA256: {expected_sha!r}")

    rankings_file = manifest_raw.get("rankings_file")
    if type(rankings_file) is not str or not rankings_file.strip():
        raise ValueError("INVALID_RANKINGS_FILE_FIELD")
    if Path(rankings_file).name != r_path.name:
        raise ValueError(
            f"RANKINGS_FILENAME_MISMATCH: manifest specifies {rankings_file!r}, got {r_path.name!r}"
        )

    row_count = manifest_raw.get("row_count")
    if type(row_count) is bool or type(row_count) is not int or row_count < 0:
        raise ValueError(f"INVALID_MANIFEST_ROW_COUNT: {row_count!r}")

    cells_raw = manifest_raw.get("cells")
    if type(cells_raw) is not list or not cells_raw or any(type(c) is not str or not c.strip() for c in cells_raw):
        raise ValueError(f"INVALID_MANIFEST_CELLS: {cells_raw!r}")

    snapshot_id = manifest_raw.get("snapshot_id", "")
    if type(snapshot_id) is not str:
        raise ValueError(f"INVALID_MANIFEST_SNAPSHOT_ID: {snapshot_id!r}")

    raw_bytes = r_path.read_bytes()
    actual_sha = sha256_bytes(raw_bytes)
    if not hmac.compare_digest(actual_sha, expected_sha):
        raise ValueError(
            f"RANKINGS_SHA256_MISMATCH: expected {expected_sha}, got {actual_sha} (tamper detected)"
        )

    return RankingManifest(
        rankings_file=rankings_file,
        rankings_sha256=expected_sha,
        row_count=row_count,
        cells=tuple(cells_raw),
        snapshot_id=snapshot_id,
    )


def load_sealed_rankings(
    rankings_path: Path | str,
    manifest_path: Path | str,
) -> tuple[RankingManifest, list[RankingRow]]:
    """Verify SHA-256 first, then parse and validate sealed G3 rankings JSONL."""
    manifest = verify_rankings_manifest(rankings_path, manifest_path)
    r_path = Path(rankings_path)
    raw_text = r_path.read_text(encoding="utf-8")
    lines = [ln for ln in raw_text.splitlines() if ln.strip()]

    rows: list[RankingRow] = []
    seen_cell_q_rank: set[tuple[str, str, int]] = set()
    seen_cell_q_doc: set[tuple[str, str, str]] = set()

    for line_no, line in enumerate(lines, start=1):
        try:
            obj = json.loads(line)
        except Exception as exc:
            raise ValueError(f"INVALID_RANKING_JSON_LINE_{line_no}: {exc}") from exc
        if type(obj) is not dict:
            raise ValueError(f"INVALID_RANKING_ROW_TYPE_LINE_{line_no}")

        cell_id = obj.get("cell_id")
        chunker = obj.get("chunker")
        retriever = obj.get("retriever")
        query_id = obj.get("query_id")
        rank = obj.get("rank")
        document_id = obj.get("document_id")
        score = obj.get("score")
        rep_chunk_id = obj.get("rep_chunk_id")
        rep_chunk_index = obj.get("rep_chunk_index")
        assembled_text = obj.get("assembled_text", "")
        assembled_segments = obj.get("assembled_segments", [])
        c_full_raw = obj.get("c_full_s_spans", [])
        c_vis_raw = obj.get("c_vis_s_spans", [])
        leg_ranks = obj.get("leg_ranks", {})
        leg_rep_chunks = obj.get("leg_rep_chunks", {})

        if type(cell_id) is not str or not cell_id.strip():
            raise ValueError(f"INVALID_CELL_ID_LINE_{line_no}")
        if chunker not in ("C0", "C1"):
            raise ValueError(f"INVALID_CHUNKER_LINE_{line_no}: {chunker!r}")
        if retriever not in ("BM25", "Dense", "RRF"):
            raise ValueError(f"INVALID_RETRIEVER_LINE_{line_no}: {retriever!r}")
        if type(query_id) is not str or not query_id.strip():
            raise ValueError(f"INVALID_QUERY_ID_LINE_{line_no}")
        if type(rank) is bool or type(rank) is not int or rank < 1:
            raise ValueError(f"INVALID_RANK_LINE_{line_no}: {rank!r}")
        if type(document_id) is not str or not document_id.strip():
            raise ValueError(f"INVALID_DOCUMENT_ID_LINE_{line_no}")
        if type(score) is bool or not isinstance(score, (int, float)) or not math.isfinite(float(score)):
            raise ValueError(f"INVALID_SCORE_LINE_{line_no}: {score!r}")
        if type(rep_chunk_id) is not str or not rep_chunk_id.strip():
            raise ValueError(f"INVALID_REP_CHUNK_ID_LINE_{line_no}")
        if type(rep_chunk_index) is bool or type(rep_chunk_index) is not int or rep_chunk_index < 0:
            raise ValueError(f"INVALID_REP_CHUNK_INDEX_LINE_{line_no}: {rep_chunk_index!r}")
        if type(assembled_text) is not str:
            raise ValueError(f"INVALID_ASSEMBLED_TEXT_LINE_{line_no}")
        if type(assembled_segments) is not list or any(type(seg) is not dict for seg in assembled_segments):
            raise ValueError(f"INVALID_ASSEMBLED_SEGMENTS_LINE_{line_no}")
        if type(c_full_raw) is not list or type(c_vis_raw) is not list:
            raise ValueError(f"INVALID_SPAN_LIST_LINE_{line_no}")
        if type(leg_ranks) is not dict or type(leg_rep_chunks) is not dict:
            raise ValueError(f"INVALID_LEG_METADATA_LINE_{line_no}")

        c_full = tuple(merge_intervals([_validate_interval_pair(sp, "c_full_s_spans") for sp in c_full_raw]))
        c_vis = tuple(merge_intervals([_validate_interval_pair(sp, "c_vis_s_spans") for sp in c_vis_raw]))

        rk_key = (cell_id, query_id, rank)
        if rk_key in seen_cell_q_rank:
            raise ValueError(f"DUPLICATE_CELL_QUERY_RANK: {rk_key}")
        seen_cell_q_rank.add(rk_key)

        doc_key = (cell_id, query_id, document_id)
        if doc_key in seen_cell_q_doc:
            raise ValueError(f"DUPLICATE_CELL_QUERY_DOCUMENT (collapse invariant violated): {doc_key}")
        seen_cell_q_doc.add(doc_key)

        rows.append(
            RankingRow(
                cell_id=cell_id,
                chunker=chunker,
                retriever=retriever,
                query_id=query_id,
                rank=rank,
                document_id=document_id,
                score=float(score),
                rep_chunk_id=rep_chunk_id,
                rep_chunk_index=rep_chunk_index,
                assembled_text=assembled_text,
                assembled_segments=tuple(assembled_segments),
                c_full_s_spans=c_full,
                c_vis_s_spans=c_vis,
                leg_ranks=dict(leg_ranks),
                leg_rep_chunks=dict(leg_rep_chunks),
            )
        )

    if len(rows) != manifest.row_count:
        raise ValueError(
            f"RANKING_ROW_COUNT_MISMATCH: manifest={manifest.row_count}, actual={len(rows)}"
        )
    cells_present = {r.cell_id for r in rows}
    if cells_present != set(manifest.cells):
        raise ValueError(
            f"RANKING_CELLS_MISMATCH: manifest={sorted(manifest.cells)}, actual={sorted(cells_present)}"
        )

    return manifest, rows


def load_external_qrels(qrels_path: Path | str) -> dict[tuple[str, str], QrelRecord]:
    """Load externally supplied qrels; strictly forbid label self-generation, NA->0, UNJUDGED->0, fillna(0)."""
    q_path = Path(qrels_path)
    if not q_path.is_file():
        raise FileNotFoundError(f"External qrels file not found: {q_path}")
    lines = [ln for ln in q_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise ValueError("EMPTY_EXTERNAL_QRELS_FILE: G4 cannot run without external relevance judgments")

    out: dict[tuple[str, str], QrelRecord] = {}
    valid_labels = {st.value: st for st in RelevanceState}

    for line_no, line in enumerate(lines, start=1):
        try:
            obj = json.loads(line)
        except Exception as exc:
            raise ValueError(f"INVALID_QREL_JSON_LINE_{line_no}: {exc}") from exc
        if type(obj) is not dict:
            raise ValueError(f"INVALID_QREL_ROW_TYPE_LINE_{line_no}")
        if "row_index_fallback" in obj or "fillna" in obj:
            raise ValueError(f"FORBIDDEN_QREL_FALLBACK_FIELD_LINE_{line_no}")

        qid = obj.get("query_id")
        did = obj.get("document_id")
        raw_label = obj.get("label")
        if type(qid) is not str or not qid.strip():
            raise ValueError(f"INVALID_QREL_QUERY_ID_LINE_{line_no}: {qid!r}")
        if type(did) is not str or not did.strip():
            raise ValueError(f"INVALID_QREL_DOCUMENT_ID_LINE_{line_no}: {did!r}")
        if type(raw_label) is not str or raw_label not in valid_labels:
            raise ValueError(
                f"INVALID_OR_UNRESOLVED_QREL_LABEL_LINE_{line_no}: {raw_label!r} "
                "(must be canonical 'REL_2'|'REL_1'|'REL_0'|'NA'|'UNJUDGED'; no fillna(0) or coercion)"
            )
        state = valid_labels[raw_label]

        lure = obj.get("plausible_unsupported_lure")
        if state == RelevanceState.REL_0:
            if type(lure) is bool or type(lure) is not int or lure not in (0, 1):
                raise ValueError(
                    f"MISSING_OR_INVALID_LURE_ON_REL_0_LINE_{line_no}: {lure!r} (must be integer 0 or 1)"
                )
        elif state in (RelevanceState.REL_1, RelevanceState.REL_2):
            if lure is not None:
                if type(lure) is bool or type(lure) is not int or lure != 0:
                    raise ValueError(
                        f"INVALID_LURE_ON_POSITIVE_QREL_LINE_{line_no}: {lure!r} (positive docs cannot have lure=1)"
                    )
        else:
            if lure is not None:
                if type(lure) is bool or type(lure) is not int or lure not in (0, 1):
                    raise ValueError(f"INVALID_LURE_ON_UNRESOLVED_QREL_LINE_{line_no}: {lure!r}")

        ev_raw = obj.get("evidence_s_spans", [])
        if type(ev_raw) is not list:
            raise ValueError(f"INVALID_EVIDENCE_S_SPANS_LINE_{line_no}")
        ev_spans = tuple(merge_intervals([_validate_interval_pair(sp, "evidence_s_spans") for sp in ev_raw]))

        lineage = obj.get("source_lineage_id")
        if lineage is not None and (type(lineage) is not str or not lineage.strip()):
            raise ValueError(f"INVALID_SOURCE_LINEAGE_ID_LINE_{line_no}: {lineage!r}")

        key = (qid, did)
        if key in out:
            raise ValueError(f"DUPLICATE_QREL_PAIR: {key}")
        out[key] = QrelRecord(
            query_id=qid,
            document_id=did,
            label=state,
            plausible_unsupported_lure=lure,
            evidence_s_spans=ev_spans,
            source_lineage_id=lineage,
        )

    return out


def resolve_qrel_state(
    qrels: Mapping[tuple[str, str], QrelRecord],
    query_id: str,
    document_id: str,
) -> RelevanceState:
    """Resolve explicit (query_id, document_id) state without sibling lineage propagation."""
    rec = qrels.get((query_id, document_id))
    if rec is None:
        return RelevanceState.UNJUDGED
    return rec.label


def count_epistemic_lineages(
    doc_ids: Sequence[str],
    lineage_by_doc_id: Mapping[str, str | None],
) -> int:
    """Deduplicate corroboration count by source_lineage_id (FX-10)."""
    lineages: set[str] = set()
    for did in doc_ids:
        lin = lineage_by_doc_id.get(did)
        if isinstance(lin, str) and lin.strip():
            lineages.add(lin.strip())
        else:
            lineages.add(f"__doc__:{did}")
    return len(lineages)


def compute_query_certificates(
    query_id: str,
    top10_by_cell: Mapping[str, Sequence[str]],
    all_doc_ids: Sequence[str],
    qrels: Mapping[tuple[str, str], QrelRecord],
    *,
    pool_doc_ids: Iterable[str] | None = None,
    strict_full_pool: bool = False,
    pool_votes_complete_by_pair: Mapping[tuple[str, str], bool] | None = None,
) -> CertResult:
    """Compute Cert-1..Cert-4 for a single query per Annex G1.5 v0.2.1 D05.2."""
    all_docs_unique = list(dict.fromkeys(all_doc_ids))
    if pool_doc_ids is not None:
        pool_set = set(pool_doc_ids)
    elif strict_full_pool:
        pool_set = {did for (q, did) in qrels if q == query_id}
    else:
        pool_set = set(all_docs_unique)

    # Cert-1: Top10InPool(q)
    total_top10 = 0
    in_pool_top10 = 0
    cert2_by_cell: dict[str, float] = {}

    for cell_id, ranked_docs in top10_by_cell.items():
        top10 = list(ranked_docs[:10])
        total_top10 += len(top10)
        in_pool_top10 += sum(1 for did in top10 if did in pool_set)

        if not top10:
            cert2_by_cell[cell_id] = 1.0
            continue
        closed_top10 = 0
        for did in top10:
            rec = qrels.get((query_id, did))
            if rec is None:
                continue
            if rec.label in (RelevanceState.REL_1, RelevanceState.REL_2):
                closed_top10 += 1
            elif rec.label == RelevanceState.REL_0 and rec.plausible_unsupported_lure in (0, 1):
                closed_top10 += 1
        cert2_by_cell[cell_id] = closed_top10 / float(len(top10))

    cert1 = (in_pool_top10 / float(total_top10)) if total_top10 > 0 else 1.0

    # Cert-3: FullPoolClosed(q)
    if not pool_set:
        cert3 = 1.0
    else:
        closed_pool = 0
        for did in pool_set:
            rec = qrels.get((query_id, did))
            if rec is None or rec.label == RelevanceState.UNJUDGED:
                continue
            if pool_votes_complete_by_pair is not None and not pool_votes_complete_by_pair.get((query_id, did), False):
                continue
            closed_pool += 1
        cert3 = closed_pool / float(len(pool_set))

    # Cert-4: IDCG_Certificate(q)
    k_gains: list[int] = []
    z_count = 0
    for did in all_docs_unique:
        rec = qrels.get((query_id, did))
        if rec is not None and rec.label in GAIN_MAP:
            k_gains.append(GAIN_MAP[rec.label])
        else:
            z_count += 1

    idcg_l = _idcg10_raw(k_gains + [0] * z_count)
    idcg_u = _idcg10_raw(k_gains + [3] * z_count)
    min_cert2 = min(cert2_by_cell.values()) if cert2_by_cell else 1.0

    if z_count == 0 and idcg_u == 0.0:
        cert4 = Cert4Status.ZERO_POSITIVE_EXACT
    elif (idcg_l == 0.0 and idcg_u > 0.0) or min_cert2 < 1.0 - 1e-12:
        cert4 = Cert4Status.INVALID_UNRESOLVED
    elif abs(idcg_u - idcg_l) <= 1e-12 and idcg_l > 0.0:
        cert4 = Cert4Status.EXACT_CERTIFIED
    else:
        cert4 = Cert4Status.BOUNDED_NOT_EXACT

    return CertResult(
        query_id=query_id,
        cert1_top10_in_pool=cert1,
        cert2_judged_at_10=cert2_by_cell,
        cert3_full_pool_closed=cert3,
        cert4_status=cert4,
        idcg_l=idcg_l,
        idcg_u=idcg_u,
        known_count=len(k_gains),
        unjudged_count=z_count,
        zero_exact_empty_z=(z_count == 0 and idcg_u == 0.0),
    )
