"""Opaque-box E2E test infrastructure & subprocess CLI helpers.

Zero top-level imports of `w07_retrieval`, `w07_g4_scorer`, `tests.fixtures`,
or `apps.ai_service`. All pipeline verification executes through child Python
3.11.9 subprocesses against documented CLI and JSON/JSONL contracts.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
_REPO_PARENT = REPO_ROOT.parent
WANDERAI_ROOT = (
    _REPO_PARENT if (_REPO_PARENT / "apps" / "ai-service").is_dir() else (_REPO_PARENT / "wanderai")
)
WANDERAI_EXPECTED_HEAD = "9bab3e3301185124361f44ff8b41f3b0e46744b7"

EXPECTED_PYTHON = Path(sys.executable)
HF_SNAPSHOT_DIR = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
    / "snapshots"
    / "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
)
TOKENIZER_SHA256 = "2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8"
PROHIBITED_G4_MODULES = frozenset(
    {
        "torch",
        "transformers",
        "sentence_transformers",
        "tokenizers",
        "underthesea",
        "w07_retrieval",
        "apps.ai_service",
    }
)
ALL_SIX_CELLS = (
    "C0-BM25",
    "C0-Dense",
    "C0-RRF",
    "C1-BM25",
    "C1-Dense",
    "C1-RRF",
)
RANKING_ROW_KEYS = frozenset(
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
BLIND_PACKET_KEYS = frozenset(
    {
        "packet_item_uuid",
        "query_id",
        "query_text",
        "document_id",
        "source_type",
        "language",
        "canonical_text_S",
    }
)

_MINILM_TOKENIZER_CACHE: Any = None
_RUNNER_HELP_CACHE: Optional[str] = None
_SCORER_HELP_CACHE: Optional[str] = None


def _ensure_src_on_sys_path() -> None:
    src_str = str(SRC_ROOT)
    if SRC_ROOT.is_dir() and src_str not in sys.path:
        sys.path.append(src_str)


def _python_exe() -> str:
    if EXPECTED_PYTHON.is_file():
        return str(EXPECTED_PYTHON)
    return sys.executable


def build_safe_offline_env(
    *,
    extra_pythonpath: Optional[Sequence[Path | str]] = None,
    env_overrides: Optional[Dict[str, Optional[str]]] = None,
    strip_keys: Optional[Iterable[str]] = None,
) -> Dict[str, str]:
    """Construct an offline-pinned, cache-free, gate-locked child env."""
    env = os.environ.copy()
    env.pop("W07_G15_FROZEN", None)
    env.pop("W07_OWNER_AUTHORIZED", None)
    if strip_keys:
        for k in strip_keys:
            env.pop(k, None)

    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["HF_DATASETS_OFFLINE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env["TOKENIZERS_PARALLELISM"] = "false"

    pp_parts: List[str] = []
    if extra_pythonpath:
        pp_parts.extend(str(p) for p in extra_pythonpath)
    if env.get("PYTHONPATH"):
        pp_parts.append(env["PYTHONPATH"])
    pp_parts.append(str(SRC_ROOT))
    env["PYTHONPATH"] = os.pathsep.join(pp_parts)

    if env_overrides:
        for k, v in env_overrides.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
    return env


def require_retrieval_cli() -> None:
    """Anti-silent-skip readiness gate for M1 (`w07_retrieval.runner`)."""
    _ensure_src_on_sys_path()
    require_all = os.environ.get("W07_E2E_REQUIRE_ALL") == "1"
    pkg_spec = importlib.util.find_spec("w07_retrieval")
    if pkg_spec is None:
        if require_all:
            pytest.fail(
                "W07_E2E_REQUIRE_ALL=1 but w07_retrieval package is missing"
            )
        pytest.skip("PENDING_M1: w07_retrieval not yet implemented")
    runner_spec = importlib.util.find_spec("w07_retrieval.runner")
    assert runner_spec is not None, (
        "w07_retrieval package exists but w07_retrieval.runner is missing/unimportable"
    )


def require_scorer_cli() -> None:
    """Anti-silent-skip readiness gate for M2 (`w07_g4_scorer.scorer`)."""
    _ensure_src_on_sys_path()
    require_all = os.environ.get("W07_E2E_REQUIRE_ALL") == "1"
    pkg_spec = importlib.util.find_spec("w07_g4_scorer")
    if pkg_spec is None:
        if require_all:
            pytest.fail(
                "W07_E2E_REQUIRE_ALL=1 but w07_g4_scorer package is missing"
            )
        pytest.skip("PENDING_M2: w07_g4_scorer not yet implemented")
    scorer_spec = importlib.util.find_spec("w07_g4_scorer.scorer")
    assert scorer_spec is not None, (
        "w07_g4_scorer package exists but w07_g4_scorer.scorer is missing/unimportable"
    )


def require_packaging_scripts() -> Tuple[Path, Path]:
    """Anti-silent-skip readiness gate for M3 (`scripts/*.py`)."""
    require_all = os.environ.get("W07_E2E_REQUIRE_ALL") == "1"
    s1 = REPO_ROOT / "scripts" / "verify_non_mutation.py"
    s2 = REPO_ROOT / "scripts" / "build_audit_package.py"
    if not (s1.is_file() or s2.is_file()):
        if require_all:
            pytest.fail(
                "W07_E2E_REQUIRE_ALL=1 but scripts/verify_non_mutation.py & build_audit_package.py are missing"
            )
        pytest.skip("PENDING_M3: packaging/non-mutation scripts not yet implemented")
    assert s1.is_file() and s2.is_file(), (
        f"Partial scripts/ implementation detected: verify={s1.is_file()}, build={s2.is_file()}"
    )
    return s1, s2


def require_real_corpus_stubs() -> Path:
    """Anti-silent-skip readiness gate for `tests/test_real_corpus_gated_stubs.py`."""
    require_all = os.environ.get("W07_E2E_REQUIRE_ALL") == "1"
    stub_path = REPO_ROOT / "tests" / "test_real_corpus_gated_stubs.py"
    if not stub_path.is_file():
        if require_all:
            pytest.fail(
                "W07_E2E_REQUIRE_ALL=1 but tests/test_real_corpus_gated_stubs.py is missing"
            )
        pytest.skip(
            "PENDING_M1_M2: tests/test_real_corpus_gated_stubs.py not yet implemented"
        )
    return stub_path


def require_fx_test_file(rel_name: str) -> Path:
    """Anti-silent-skip readiness gate for M1/M2 unit test modules."""
    require_all = os.environ.get("W07_E2E_REQUIRE_ALL") == "1"
    path = REPO_ROOT / "tests" / rel_name
    if not path.is_file():
        if require_all:
            pytest.fail(f"W07_E2E_REQUIRE_ALL=1 but tests/{rel_name} is missing")
        pytest.skip(f"PENDING_M1_M2: tests/{rel_name} not yet implemented")
    return path


def get_runner_help() -> str:
    global _RUNNER_HELP_CACHE
    if _RUNNER_HELP_CACHE is None:
        proc = subprocess.run(
            [_python_exe(), "-B", "-m", "w07_retrieval.runner", "--help"],
            cwd=str(REPO_ROOT),
            env=build_safe_offline_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        _RUNNER_HELP_CACHE = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return _RUNNER_HELP_CACHE


def get_scorer_help() -> str:
    global _SCORER_HELP_CACHE
    if _SCORER_HELP_CACHE is None:
        proc = subprocess.run(
            [_python_exe(), "-B", "-m", "w07_g4_scorer.scorer", "--help"],
            cwd=str(REPO_ROOT),
            env=build_safe_offline_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        _SCORER_HELP_CACHE = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return _SCORER_HELP_CACHE


def scorer_supports_flag(flag: str) -> bool:
    return flag in get_scorer_help()


def runner_supports_flag(flag: str) -> bool:
    return flag in get_runner_help()


def run_retrieval_cli(
    corpus_path: Path,
    queries_path: Path,
    output_dir: Path,
    *,
    packet_salt: Optional[str] = None,
    snapshot_dir: Optional[Path | str] = HF_SNAPSHOT_DIR,
    cells: Optional[Sequence[str]] = None,
    extra_args: Optional[Sequence[str]] = None,
    extra_pythonpath: Optional[Sequence[Path | str]] = None,
    env_overrides: Optional[Dict[str, Optional[str]]] = None,
    strip_keys: Optional[Iterable[str]] = None,
    check: bool = True,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Invoke `python -B -m w07_retrieval.runner` in an isolated subprocess."""
    require_retrieval_cli()
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd: List[str] = [
        _python_exe(),
        "-B",
        "-m",
        "w07_retrieval.runner",
        "--corpus",
        str(corpus_path),
        "--queries",
        str(queries_path),
        "--output-dir",
        str(output_dir),
    ]
    if snapshot_dir is not None:
        cmd.extend(["--snapshot-dir", str(snapshot_dir)])
    if packet_salt is not None:
        cmd.extend(["--packet-salt", str(packet_salt)])
    if cells:
        cmd.append("--cells")
        cmd.extend(list(cells))
    if extra_args:
        cmd.extend(list(extra_args))

    env = build_safe_offline_env(
        extra_pythonpath=extra_pythonpath,
        env_overrides=env_overrides,
        strip_keys=strip_keys,
    )
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"w07_retrieval.runner failed (rc={proc.returncode}):\n"
            f"CMD: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def run_scorer_cli(
    rankings_path: Path,
    manifest_path: Path,
    qrels_path: Optional[Path],
    queries_path: Path,
    output_path: Path,
    *,
    removed_audit_spans: Optional[Path] = None,
    strict_full_pool: bool = False,
    enforce_final50_matrix: bool = False,
    judge_a_path: Optional[Path] = None,
    judge_b_path: Optional[Path] = None,
    judging_order: Optional[str] = None,
    expected_pairs_path: Optional[Path] = None,
    docs_path: Optional[Path] = None,
    extra_args: Optional[Sequence[str]] = None,
    extra_pythonpath: Optional[Sequence[Path | str]] = None,
    env_overrides: Optional[Dict[str, Optional[str]]] = None,
    check: bool = True,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Invoke `python -B -m w07_g4_scorer.scorer` in an isolated subprocess."""
    require_scorer_cli()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd: List[str] = [
        _python_exe(),
        "-B",
        "-m",
        "w07_g4_scorer.scorer",
        "--rankings",
        str(rankings_path),
        "--manifest",
        str(manifest_path),
        "--queries",
        str(queries_path),
        "--output",
        str(output_path),
    ]
    if qrels_path is not None:
        cmd.extend(["--qrels", str(qrels_path)])
    if judge_a_path is not None:
        cmd.extend(["--judge-a", str(judge_a_path)])
    if judge_b_path is not None:
        cmd.extend(["--judge-b", str(judge_b_path)])
    if judging_order is not None and scorer_supports_flag("--judging-order"):
        cmd.extend(["--judging-order", str(judging_order)])
    if expected_pairs_path is not None and scorer_supports_flag("--expected-pairs"):
        cmd.extend(["--expected-pairs", str(expected_pairs_path)])
    if docs_path is not None and scorer_supports_flag("--docs"):
        cmd.extend(["--docs", str(docs_path)])
    if removed_audit_spans is not None and scorer_supports_flag("--removed-audit-spans"):
        cmd.extend(["--removed-audit-spans", str(removed_audit_spans)])
    if strict_full_pool:
        cmd.append("--strict-full-pool")
    if enforce_final50_matrix and scorer_supports_flag("--enforce-final50-matrix"):
        cmd.append("--enforce-final50-matrix")
    if extra_args:
        cmd.extend(list(extra_args))

    env = build_safe_offline_env(
        extra_pythonpath=extra_pythonpath,
        env_overrides=env_overrides,
    )
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"w07_g4_scorer.scorer failed (rc={proc.returncode}):\n"
            f"CMD: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def run_python_probe(
    code_str: str,
    *,
    extra_pythonpath: Optional[Sequence[Path | str]] = None,
    env_overrides: Optional[Dict[str, Optional[str]]] = None,
    cwd: Optional[Path] = None,
    check: bool = True,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Run an isolated `python -B -c` subprocess under offline env guards."""
    cmd = [_python_exe(), "-B", "-c", code_str]
    env = build_safe_offline_env(
        extra_pythonpath=extra_pythonpath,
        env_overrides=env_overrides,
    )
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"python probe failed (rc={proc.returncode}):\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def run_pytest_subprocess(
    targets: Sequence[Path | str],
    *,
    extra_args: Optional[Sequence[str]] = None,
    env_overrides: Optional[Dict[str, Optional[str]]] = None,
    cwd: Optional[Path] = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Invoke pytest in an isolated cache-free subprocess."""
    cmd = [_python_exe(), "-B", "-m", "pytest", "-p", "no:cacheprovider"]
    if extra_args:
        cmd.extend(list(extra_args))
    cmd.extend(str(t) for t in targets)
    env = build_safe_offline_env(env_overrides=env_overrides)
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def cached_minilm_tokenizer() -> Any:
    """Load local cached MiniLM AutoTokenizer offline (zero w07_retrieval imports)."""
    global _MINILM_TOKENIZER_CACHE
    if _MINILM_TOKENIZER_CACHE is None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from transformers import AutoTokenizer

        _MINILM_TOKENIZER_CACHE = AutoTokenizer.from_pretrained(
            str(HF_SNAPSHOT_DIR),
            local_files_only=True,
        )
    return _MINILM_TOKENIZER_CACHE


# ---------------------------------------------------------------------------
# Defensive JSON / JSONL Artifact Readers & Structural Extractors
# ---------------------------------------------------------------------------


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    raw = path.read_text(encoding="utf-8")
    for line in raw.splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows_by_cell(rankings_rows: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rankings_rows:
        grouped.setdefault(row["cell_id"], []).append(row)
    for cell_rows in grouped.values():
        cell_rows.sort(key=lambda r: (r["query_id"], r["rank"]))
    return grouped


def rows_for_cell_query(
    rankings_rows: Sequence[Dict[str, Any]],
    cell_id: str,
    query_id: str,
) -> List[Dict[str, Any]]:
    matched = [
        r for r in rankings_rows if r["cell_id"] == cell_id and r["query_id"] == query_id
    ]
    matched.sort(key=lambda r: r["rank"])
    return matched


def _norm_key(key: str) -> str:
    return key.lower().replace("@", "_at_").replace("-", "_")


def extract_metric_value(obj: Any, candidate_names: Sequence[str]) -> Any:
    """Find a metric value across flat or nested dicts by normalized key aliases."""
    targets = set()
    for n in candidate_names:
        low = n.lower().replace("-", "_")
        targets.add(low)
        targets.add(low.replace("@", "_at_"))
        targets.add(low.replace("@", "_").replace("_at_", "_"))
        targets.add(low.replace("@", "at").replace("_", ""))

    def _walk(node: Any) -> Any:
        if isinstance(node, dict):
            for k, v in node.items():
                low = str(k).lower().replace("-", "_")
                variants = {
                    low,
                    low.replace("@", "_at_"),
                    low.replace("@", "_").replace("_at_", "_"),
                    low.replace("@", "at").replace("_", ""),
                }
                if variants & targets:
                    return v
            for v in node.values():
                if isinstance(v, (dict, list)):
                    hit = _walk(v)
                    if hit is not None:
                        return hit
        elif isinstance(node, list):
            for item in node:
                hit = _walk(item)
                if hit is not None:
                    return hit
        return None

    return _walk(obj)


def extract_cells_map(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Defensively extract per-cell metrics dictionary keyed by cell_id."""
    for container_key in (
        "cells",
        "per_cell",
        "cell_metrics",
        "results_by_cell",
        "cell_results",
        "systems",
    ):
        val = report.get(container_key)
        if isinstance(val, dict):
            return {str(k): v for k, v in val.items() if isinstance(v, dict)}
        if isinstance(val, list):
            out: Dict[str, Dict[str, Any]] = {}
            for item in val:
                if isinstance(item, dict) and "cell_id" in item:
                    out[str(item["cell_id"])] = item
            if out:
                return out
    direct = {
        c: report[c]
        for c in ALL_SIX_CELLS
        if c in report and isinstance(report[c], dict)
    }
    return direct


def extract_contrasts_map(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Defensively extract K1..K5 contrasts dictionary."""
    for container_key in (
        "contrasts_k1_to_k5",
        "contrasts",
        "k1_k5",
        "pairwise_contrasts",
        "comparisons",
        "hypothesis_contrasts",
    ):
        val = report.get(container_key)
        if isinstance(val, dict):
            return {str(k): v for k, v in val.items() if isinstance(v, dict)}
        if isinstance(val, list):
            out: Dict[str, Dict[str, Any]] = {}
            for item in val:
                if isinstance(item, dict):
                    cid = item.get("contrast_id") or item.get("id") or item.get("name")
                    if cid:
                        out[str(cid)] = item
            if out:
                return out
    return {
        k: report[k]
        for k in ("K1", "K2", "K3", "K4", "K5")
        if k in report and isinstance(report[k], dict)
    }


def extract_per_query_map(report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Defensively extract per-query certificate/disposition mapping."""
    for container_key in (
        "query_disposition_table",
        "per_query",
        "queries",
        "query_metrics",
        "query_certificates",
        "disposition",
        "query_dispositions",
    ):
        val = report.get(container_key)
        if isinstance(val, dict):
            return {str(k): v for k, v in val.items() if isinstance(v, dict)}
        if isinstance(val, list):
            out: Dict[str, Dict[str, Any]] = {}
            for item in val:
                if isinstance(item, dict) and "query_id" in item:
                    out[str(item["query_id"])] = item
            if out:
                return out
    return {}


def extract_unanswerable_map(report: Dict[str, Any]) -> Dict[str, Any]:
    for key in (
        "unanswerable_safety",
        "unanswerable",
        "q_unans",
        "unanswerable_metrics",
        "unanswerable_exposure",
        "safety_exposure",
    ):
        if key in report and isinstance(report[key], dict):
            return report[key]
    return report


def iter_all_keys_and_strings(obj: Any) -> Iterable[str]:
    """Recursively yield all dict keys and string scalar values in JSON."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from iter_all_keys_and_strings(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_all_keys_and_strings(item)
    elif isinstance(obj, str):
        yield obj


def report_contains_token(report: Any, token: str) -> bool:
    needle = token.lower()
    return any(needle in s.lower() for s in iter_all_keys_and_strings(report))


def _judge_gate_halted(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    if node.get("confirmable") is False:
        return True
    status = node.get("status")
    if isinstance(status, str) and status in {
        "INCOMPLETE_SEALED_JUDGE_COVERAGE_HALT",
        "HALT_DEV_ERROR_CAP_EXCEEDED",
        "INCONCLUSIVE_INSUFFICIENT_JUDGE_COVERAGE",
    }:
        return True
    for key in ("judge_A_by_cell", "judge_B_by_cell", "judge_A", "judge_B"):
        sub = node.get(key)
        if isinstance(sub, dict):
            for cell_val in sub.values():
                if _judge_gate_halted(cell_val):
                    return True
    return False


def is_blocked_or_invalid_status(
    proc: subprocess.CompletedProcess[str],
    output_path: Path,
) -> bool:
    """Check whether scorer halted non-zero OR explicitly emitted blocked/unconfirmable status."""
    if proc.returncode != 0:
        return True
    if not output_path.is_file():
        return True
    report = read_json(output_path)
    headline = str(report.get("headline_status") or "")
    if (
        "INVALID_UNRESOLVED" in headline
        or "INCOMPLETE_SEALED_JUDGE_COVERAGE_HALT" in headline
    ):
        return True
    certs = report.get("certificates")
    if isinstance(certs, dict):
        c4_counts = certs.get("cert4_counts")
        if isinstance(c4_counts, dict) and int(c4_counts.get("INVALID_UNRESOLVED", 0)) > 0:
            return True
    disp = report.get("query_disposition_table")
    if isinstance(disp, list):
        for entry in disp:
            if isinstance(entry, dict) and entry.get("cert4_status") == "INVALID_UNRESOLVED":
                return True
    if report.get("confirmable") is False:
        return True
    if report.get("status") == "INCOMPLETE_SEALED_JUDGE_COVERAGE_HALT":
        return True
    if _judge_gate_halted(report.get("judge_gates")):
        return True
    return False


@pytest.fixture(scope="session", autouse=True)
def e2e_offline_session_guard() -> None:
    """Enforce Python 3.11.9 and gate-lock defaults at session start."""
    assert sys.version_info[:2] == (3, 11), (
        f"E2E suite requires Python 3.11.x (got {sys.version}); never use `py` launcher."
    )
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
