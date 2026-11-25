"""Tier 5 white-box adversarial coverage tests for scripts/*.py, w07_retrieval, and w07_g4_scorer."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fixtures.g4_fixtures import (
    build_fx15_smoke_bundle,
    build_synthetic_final50_manifest,
    make_query_dict,
    make_query_spec,
    make_ranking_row,
    write_jsonl,
    write_sealed_rankings_bundle,
)

from w07_g4_scorer import (
    Cert4Status,
    QrelRecord,
    RelevanceState,
    assert_g4_package_zero_ml_imports,
    check_g5_gate_unlock,
    compute_span_hits_at_10,
    coupled_ndcg10_bounds,
    coupled_pairwise_contrast_bounds,
    evaluate_budget_and_retry_circuit_breakers,
    evaluate_dual_judge_concordance,
    evaluate_winner_gate,
    exact_ndcg10_bounds,
    holm_bonferroni,
    load_external_qrels,
    load_query_manifest,
    load_sealed_rankings,
    paired_bootstrap_and_sign_flip,
    quadratic_weighted_kappa,
    recall_at_k,
    resolve_qrel_state,
    score_g4,
    score_g4_from_files,
    score_validated_judge_rankings,
    seal_expected_pairs_manifest,
    validate_dev_isolation,
    validate_final50_strata_and_city_quota,
    validate_judge_api_config,
    validate_judge_response,
    validate_pre_g3_query_manifest,
    validate_sealed_query_metadata,
    verify_judge_quote_against_chunk,
    verify_rankings_manifest,
    verify_sealed_expected_pairs_manifest,
)
from w07_g4_scorer import (
    intervals_contain as g4_intervals_contain,
)
from w07_g4_scorer import (
    merge_intervals as g4_merge_intervals,
)
from w07_g4_scorer import (
    subtract_intervals as g4_subtract_intervals,
)
from w07_g4_scorer.judge_gates import (
    assert_distinct_non_deprecated_judge_pair,
    assert_supported_non_deprecated_judge_model,
    assert_valid_model_snapshot_identity,
    build_pinned_judge_api_config,
)
from w07_g4_scorer.metrics import conservative_ndcg10_enclosure, span_hit_matches
from w07_g4_scorer.stats import PairedStatsResult

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
VERIFY_SCRIPT = SCRIPTS_ROOT / "verify_non_mutation.py"
BUILD_SCRIPT = SCRIPTS_ROOT / "build_audit_package.py"


def _load_script_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _safe_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("W07_G15_FROZEN", None)
    env.pop("W07_OWNER_AUTHORIZED", None)
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["HF_DATASETS_OFFLINE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env["TOKENIZERS_PARALLELISM"] = "false"
    return env


def _run_g4_clean_subprocess(script: str) -> subprocess.CompletedProcess[str]:
    env = _safe_env()
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT / "src"), str(REPO_ROOT / "tests")])
    return subprocess.run(
        [sys.executable, "-B", "-c", script],
        check=False,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


def _run_verify(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(VERIFY_SCRIPT), *args],
        check=False,
        cwd=str(REPO_ROOT),
        env=_safe_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


def _stage_minimal_prep_dir(base: Path) -> Path:
    prep = base / "prep"
    (prep / "scripts").mkdir(parents=True)
    (prep / "src" / "w07_retrieval").mkdir(parents=True)
    (prep / "src" / "w07_g4_scorer").mkdir(parents=True)
    (prep / "tests" / "fixtures").mkdir(parents=True)
    (prep / "tests" / "e2e").mkdir(parents=True)
    (prep / "evidence" / "e2e_tiers1_to_4").mkdir(parents=True)

    (prep / "pyproject.toml").write_text("[project]\nname='w07'\n", encoding="utf-8")
    (prep / "README.md").write_text("# W07\n", encoding="utf-8")
    shutil.copy2(VERIFY_SCRIPT, prep / "scripts" / "verify_non_mutation.py")
    shutil.copy2(BUILD_SCRIPT, prep / "scripts" / "build_audit_package.py")
    (prep / "tests" / "conftest.py").write_text("# conftest\n", encoding="utf-8")
    (prep / "tests" / "test_sample.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    (prep / "src" / "w07_retrieval" / "__init__.py").write_text("", encoding="utf-8")
    (prep / "src" / "w07_g4_scorer" / "__init__.py").write_text("", encoding="utf-8")
    (prep / "tests" / "fixtures" / "__init__.py").write_text("", encoding="utf-8")
    (prep / "tests" / "e2e" / "__init__.py").write_text("", encoding="utf-8")
    (prep / "evidence" / "m1_unit_pytest.log").write_text(
        "=== 48 passed, 5 skipped in 1.00s ===\n", encoding="utf-8"
    )
    (prep / "evidence" / "e2e_tiers1_to_4" / "tier1_receipt.json").write_text(
        json.dumps({"tier": "tier1", "exit_code": 0, "passed": 60, "skipped": 0, "failed": 0}),
        encoding="utf-8",
    )
    (prep / "evidence" / "broken_receipt.json").write_text("{not-json", encoding="utf-8")
    (prep / "evidence" / "no_banner.log").write_text("plain log line\n", encoding="utf-8")
    return prep


@pytest.fixture(scope="module")
def minilm_tok(snapshot_dir: Path) -> Any:
    from w07_retrieval.visibility import load_minilm_tokenizer

    return load_minilm_tokenizer(snapshot_dir)


# ---------------------------------------------------------------------------
# 1. scripts/verify_non_mutation.py
# ---------------------------------------------------------------------------


def test_t5_verify_non_mutation_tracked_staged_and_missing_git_repo(tmp_path: Path) -> None:
    vnm = _load_script_module("verify_non_mutation_mod", VERIFY_SCRIPT)
    missing_info = vnm._check_wanderai_git(tmp_path / "does_not_exist")
    assert missing_info["ok"] is False
    assert missing_info["error"] == "missing_wanderai_dir"

    repo = tmp_path / "fake_wanderai"
    repo.mkdir()
    subprocess.check_call(["git", "-C", str(repo), "init", "-q"])
    subprocess.check_call(["git", "-C", str(repo), "config", "user.email", "t@example.com"])
    subprocess.check_call(["git", "-C", str(repo), "config", "user.name", "Test"])
    tracked = repo / "tracked.py"
    tracked.write_text("x = 1\n", encoding="utf-8")
    subprocess.check_call(["git", "-C", str(repo), "add", "tracked.py"])
    subprocess.check_call(["git", "-C", str(repo), "commit", "-q", "-m", "init"])

    tracked.write_text("x = 2\n", encoding="utf-8")
    proc_diff = _run_verify(["--wanderai-dir", str(repo)])
    assert proc_diff.returncode == 1
    git_info = json.loads(proc_diff.stdout)["checks"]["wanderai_git"]
    assert git_info["diff_ok"] is False
    assert git_info["diff_files"] == ["tracked.py"]
    assert git_info["cached_diff_ok"] is True
    assert git_info["status_ok"] is False

    subprocess.check_call(["git", "-C", str(repo), "add", "tracked.py"])
    git_cached = vnm._check_wanderai_git(repo)
    assert git_cached["ok"] is False
    assert git_cached["diff_ok"] is True
    assert git_cached["cached_diff_ok"] is False
    assert git_cached["cached_diff_files"] == ["tracked.py"]


def test_t5_verify_non_mutation_skeleton_missing_and_corrupt(tmp_path: Path) -> None:
    vnm = _load_script_module("verify_non_mutation_mod", VERIFY_SCRIPT)
    miss = vnm._verify_file_sha256(tmp_path / "missing_skel.py", vnm.SKELETON_SHA256)
    assert miss["ok"] is False and miss["error"] == "missing_or_not_file"

    bad_skel = tmp_path / "w07_zh_methodology_skeleton.py"
    bad_skel.write_text("print('tampered')\n", encoding="utf-8")
    proc_corrupt = _run_verify(["--skeleton-path", str(bad_skel)])
    assert proc_corrupt.returncode == 1
    assert (
        json.loads(proc_corrupt.stdout)["checks"]["skeleton_copies"][0]["error"]
        == "sha256_mismatch"
    )


def test_t5_verify_non_mutation_prep_dir_final50_missing_src_and_prohibited_refs(
    tmp_path: Path,
) -> None:
    vnm = _load_script_module("verify_non_mutation_mod", VERIFY_SCRIPT)

    empty_prep = tmp_path / "empty_prep"
    empty_prep.mkdir()
    no_src = vnm._check_src_hygiene(empty_prep)
    assert no_src["ok"] is False and no_src["error"] == "missing_src_dir"

    bad_prep = tmp_path / "bad_prep"
    (bad_prep / "src" / "pkg").mkdir(parents=True)
    (bad_prep / "FINAL-50_staged").mkdir()
    (bad_prep / "src" / "pkg" / "bad.py").write_text(
        (
            "import apps.ai_service.rag\n"
            "from wanderai.core import helper\n"
            "PATH_A = 'T0_PRIVATE/x'\n"
            "PATH_B = 'DEV-5/y'\n"
            "PATH_C = 'poi_knowledge_acquired_v1.jsonl'\n"
            "PATH_D = 'gomate_places_freeze_v2.json'\n"
        ),
        encoding="utf-8",
    )
    proc_bad = _run_verify(["--prep-dir", str(bad_prep)])
    assert proc_bad.returncode == 1
    s_bad = json.loads(proc_bad.stdout)
    assert s_bad["checks"]["final50_absence"]["ok"] is False
    assert any("FINAL-50_staged" in h for h in s_bad["checks"]["final50_absence"]["hits"])
    v_types = {(v["type"], v["detail"]) for v in s_bad["checks"]["src_hygiene"]["violations"]}
    assert ("forbidden_import", "apps.ai_service.rag") in v_types
    assert ("forbidden_import_from", "wanderai.core") in v_types
    assert ("forbidden_reference", "T0_PRIVATE") in v_types
    assert ("forbidden_reference", "DEV-5") in v_types
    assert ("forbidden_reference", "poi_knowledge_acquired_v1.jsonl") in v_types
    assert ("forbidden_reference", "gomate_places_freeze_v2.json") in v_types


def test_t5_verify_non_mutation_authority_dir_partial_unexpected_corrupt_and_valid(
    tmp_path: Path,
) -> None:
    vnm = _load_script_module("verify_non_mutation_mod", VERIFY_SCRIPT)

    miss_auth = vnm._check_authority_dir(tmp_path / "missing_auth")
    assert miss_auth["ok"] is False and miss_auth["error"] == "missing_authority_dir"

    auth_dir = tmp_path / "auth"
    auth_dir.mkdir()
    sources = [
        vnm.DEFAULT_CRITICAL_PATH_REPORT,
        vnm.DEFAULT_WANDERAI_DIR
        / "docs"
        / "research"
        / "W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md",
        vnm.DEFAULT_ANNEX_CANDIDATE_COPIES[0],
        vnm.DEFAULT_G1_RECEIPT_PATH,
        vnm.DEFAULT_AUTO_EVAL_PATH,
    ]
    for src_p in sources:
        shutil.copy2(src_p, auth_dir / src_p.name)

    proc_ok = _run_verify(["--authority-dir", str(auth_dir)])
    assert proc_ok.returncode == 0
    assert json.loads(proc_ok.stdout)["checks"]["authority_dir"]["ok"] is True

    extra = auth_dir / "unexpected.md"
    extra.write_text("extra\n", encoding="utf-8")
    extra_res = vnm._check_authority_dir(auth_dir)
    assert extra_res["ok"] is False and extra_res["unexpected_files"] == ["unexpected.md"]
    extra.unlink()

    removed_name = sources[-1].name
    saved_bytes = (auth_dir / removed_name).read_bytes()
    (auth_dir / removed_name).unlink()
    partial_res = vnm._check_authority_dir(auth_dir)
    assert partial_res["ok"] is False and partial_res["missing_files"] == [removed_name]

    (auth_dir / removed_name).write_bytes(saved_bytes + b"tamper")
    tamper_res = vnm._check_authority_dir(auth_dir)
    assert tamper_res["ok"] is False
    bad_entry = next(item for item in tamper_res["files"] if item["path"].endswith(removed_name))
    assert bad_entry["error"] == "sha256_mismatch"


def test_t5_verify_non_mutation_output_alias_and_lf_determinism(tmp_path: Path) -> None:
    out1 = tmp_path / "nested" / "r1.json"
    out2 = tmp_path / "nested" / "r2.json"
    p1 = _run_verify(["--output", str(out1)])
    p2 = _run_verify(["--json-out", str(out2)])
    assert p1.returncode == 0 and p2.returncode == 0
    b1 = out1.read_bytes()
    b2 = out2.read_bytes()
    assert b1 == b2
    assert b"\r\n" not in b1
    assert b1.decode("utf-8") == p1.stdout


# ---------------------------------------------------------------------------
# 2. scripts/build_audit_package.py
# ---------------------------------------------------------------------------


def test_t5_build_audit_package_denylist_and_missing_required_paths(tmp_path: Path) -> None:
    bap = _load_script_module("build_audit_package_mod", BUILD_SCRIPT)

    for bad_member in (
        ".git/HEAD",
        ".agents/teamwork/handoff.md",
        "src/w07_retrieval/__pycache__/x.py",
        "tests/.pytest_cache/v",
        ".ruff_cache/x",
        ".mypy_cache/x",
        ".venv/site.py",
        "venv/site.py",
        "src/a.pyc",
        "src/a.pyo",
        "evidence/tmp.tmp",
        "evidence/old.bak",
        "evidence/DEV-5_slice.jsonl",
        "evidence/T0_PRIVATE_secret.json",
        "evidence/FINAL-50_leak.jsonl",
        "evidence/final-50_leak.json",
        "evidence/dev-5_leak.json",
        "evidence/t0_private_leak.json",
        "evidence/poi_knowledge_acquired_v1.jsonl",
        "evidence/gomate_places_freeze_v2.json",
    ):
        with pytest.raises(ValueError):
            bap._assert_member_allowed(bad_member)

    prep = _stage_minimal_prep_dir(tmp_path)
    for leak_name, token in (
        ("T0_PRIVATE_leak.txt", "T0_PRIVATE"),
        ("final-50_leak.json", "FINAL-50"),
        ("dev-5_leak.json", "DEV-5"),
        ("t0_private_leak.json", "T0_PRIVATE"),
    ):
        leak = prep / "evidence" / leak_name
        leak.write_text("secret\n", encoding="utf-8")
        with pytest.raises(ValueError, match=token):
            bap.build_package(output_dir=tmp_path / "out_bad_leak", prep_dir=prep, skip_non_mutation=True)
        leak.unlink()

    venv_dir = prep / "tests" / "e2e" / ".venv"
    venv_dir.mkdir()
    (venv_dir / "bad.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        bap.build_package(output_dir=tmp_path / "out_bad2", prep_dir=prep, skip_non_mutation=True)
    shutil.rmtree(venv_dir)

    f50 = prep / "FINAL-50_bad.txt"
    f50.write_text("no\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Non-mutation verification failed"):
        bap.build_package(output_dir=tmp_path / "out_bad3", prep_dir=prep, skip_non_mutation=False)
    f50.unlink()

    (prep / "pyproject.toml").unlink()
    with pytest.raises(FileNotFoundError):
        bap.build_package(output_dir=tmp_path / "out_bad4", prep_dir=prep, skip_non_mutation=True)


def test_t5_build_audit_package_evidence_non_mutation_zipinfo_and_receipt(
    tmp_path: Path,
) -> None:
    bap = _load_script_module("build_audit_package_mod", BUILD_SCRIPT)
    prep = _stage_minimal_prep_dir(tmp_path)

    ev_files = sorted((prep / "evidence").rglob("*"))
    before_stats = {
        p: (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in ev_files
        if p.is_file()
    }

    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"
    receipt1 = bap.build_package(output_dir=out1, prep_dir=prep, skip_non_mutation=False)
    receipt2 = bap.build_package(output_dir=out2, prep_dir=prep, skip_non_mutation=False)

    after_stats = {
        p: (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in ev_files
        if p.is_file()
    }
    assert before_stats == after_stats

    zip1 = out1 / bap.ZIP_FILENAME
    zip2 = out2 / bap.ZIP_FILENAME
    assert zip1.read_bytes() == zip2.read_bytes()
    assert receipt1["deliverable_zip_sha256"] == receipt2["deliverable_zip_sha256"]

    with zipfile.ZipFile(zip1, "r") as zf:
        assert zf.testzip() is None
        names = zf.namelist()
        assert names == sorted(names)
        assert len(names) == receipt1["deliverable_zip_total_files"]
        for info in zf.infolist():
            assert info.date_time == (2026, 11, 20, 0, 0, 0)
            assert info.create_system == 3
            assert info.compress_type == zipfile.ZIP_DEFLATED
            assert info.external_attr == ((0o100644 & 0xFFFF) << 16)
            assert receipt1["member_sha256s"][info.filename] == hashlib.sha256(
                zf.read(info.filename)
            ).hexdigest()

    assert receipt1["schema_version"] == "W07_OFFLINE_RETRIEVAL_PREP_AUDIT_RECEIPT_V1"
    assert receipt1["api_spend_usd"] == 0.0
    assert receipt1["network_calls"] == 0
    assert receipt1["real_137_corpus_executions"] == 0
    assert receipt1["dev_authorized"] is False
    assert receipt1["final_50_or_g5_authorized"] is False
    assert receipt1["g15_frozen"] is False
    assert receipt1["g3_status"] == "HOLD"
    assert receipt1["g4_status"] == "HOLD"
    assert receipt1["g5_status"] == "HOLD"
    assert receipt1["w07_scientific_closed"] is False
    assert receipt1["double_pack_verified"] is True
    assert receipt1["non_mutation_verified"] is True
    assert receipt1["handoff_status"] == "READY_FOR_CHATGPT_OFFLINE_RETRIEVAL_PREP_AUDIT_PRE_FREEZE"

    md_path = out1 / bap.REPORT_FILENAME
    md_bytes = md_path.read_bytes()
    assert hashlib.sha256(md_bytes).hexdigest() == receipt1["report_markdown_sha256"]
    md_text = md_bytes.decode("utf-8")
    assert "G3 PASS" not in md_text and "G4 PASS" not in md_text
    assert "`VERIFIED`" in md_text

    out_skip = tmp_path / "out_skip"
    r_skip = bap.build_package(output_dir=out_skip, prep_dir=prep, skip_non_mutation=True)
    assert r_skip["non_mutation_verified"] is False
    assert "SKIPPED_BY_FLAG" in (out_skip / bap.REPORT_FILENAME).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 3. src/w07_retrieval/** (imports kept local to preserve pytest order-independence)
# ---------------------------------------------------------------------------


def test_t5_sanitizer_zero_ws_adjacent_utf8_and_interval_edges() -> None:
    from w07_retrieval.sanitizer import (
        cp_to_utf8_byte_offsets,
        intervals_contain,
        merge_intervals,
        project_v_span_to_s,
        sanitize_canonical_to_view,
        subtract_intervals,
    )

    with pytest.raises(TypeError):
        sanitize_canonical_to_view(123)  # type: ignore[arg-type]

    empty_res = sanitize_canonical_to_view("")
    assert empty_res.view_V == "" and empty_res.segments == [] and empty_res.removed_intervals == []

    tag_only = "[CORROBORATED: osm:node/1]"
    tag_only_res = sanitize_canonical_to_view(tag_only)
    assert tag_only_res.view_V == "" and tag_only_res.removed_intervals == [(0, len(tag_only))]

    s = (
        "🏛️Phở"
        "[CORROBORATED:osm:node/1,wikidata:Q2]"
        "[CORROBORATED:wikipedia:vi:Hà_Nội]"
        "Bò"
    )
    res = sanitize_canonical_to_view(s)
    assert res.view_V == "🏛️PhởBò"
    assert len(res.removed_intervals) == 2
    assert res.removed_intervals[0][1] == res.removed_intervals[1][0]
    assert res.families == ["osm", "wikidata", "wikipedia"]

    iv = project_v_span_to_s(0, len(res.view_V), res.segments)
    assert len(iv) == 2
    bmap = cp_to_utf8_byte_offsets(s)
    s_utf8 = s.encode("utf-8")
    assert b"".join(s_utf8[bmap[a] : bmap[b]] for a, b in iv).decode("utf-8") == res.view_V

    for bad in (
        "x [CORROBORATED] y",
        "x [CORROBORATED: osm:node/1 [CORROBORATED: osm:node/2]",
        "x [CORROBORATED: wikidata:Q1, unknown:abc] y",
    ):
        with pytest.raises(ValueError):
            sanitize_canonical_to_view(bad)

    with pytest.raises(ValueError):
        project_v_span_to_s(5, 3, res.segments)
    assert project_v_span_to_s(2, 2, res.segments) == []
    assert merge_intervals([(4, 4), (5, 2), (1, 3), (3, 6)]) == [(1, 6)]
    assert subtract_intervals([(0, 10)], [(2, 4), (7, 9)]) == [(0, 2), (4, 7), (9, 10)]
    assert intervals_contain([], []) is True
    assert intervals_contain([(0, 5)], [(0, 6)]) is False


def test_t5_chunker_c1_token_boundary_vietnamese_empty_parent_and_footers(
    minilm_tok: Any,
) -> None:
    from w07_retrieval.chunker_c1 import BOILERPLATE_FOOTER_ALLOWLIST, C1Chunker
    from w07_retrieval.sanitizer import sanitize_canonical_to_view
    from w07_retrieval.schema import load_canonical_document

    c1 = C1Chunker()

    def _doc(doc_id: str, text_s: str, source_type: str = "wikipedia_vi") -> Any:
        return load_canonical_document(
            {
                "document_id": doc_id,
                "source_type": source_type,
                "title": "Địa điểm",
                "language": "vi",
                "canonical_text_S": text_s,
            }
        )

    ws_doc = _doc("t5-ws", "   \n\t  ")
    ws_res = c1.chunk_document_detailed(
        ws_doc, sanitize_canonical_to_view(ws_doc.canonical_text_S), minilm_tok
    )
    assert ws_res.chunks == [] and ws_res.coverage_lost_due_to_chunking == 0
    assert ws_res.omitted_ws_cp == len(ws_doc.canonical_text_S)

    c1_small = C1Chunker(max_tokens=18)
    long_title_doc = load_canonical_document(
        {
            "document_id": "t5-long-hdr",
            "source_type": "wikipedia_vi",
            "title": " ".join(f"word{i}" for i in range(20)),
            "language": "vi",
            "canonical_text_S": "== Mục ==\nNội dung ngắn.",
        }
    )
    with pytest.raises(ValueError, match="zero body token budget"):
        c1_small.chunk_document_detailed(
            long_title_doc, sanitize_canonical_to_view(long_title_doc.canonical_text_S), minilm_tok
        )

    unbroken = "ệđ🏛️" * 4
    unb_doc = _doc("t5-unbroken", f"== M ==\n{unbroken}")
    unb_res = c1_small.chunk_document_detailed(
        unb_doc, sanitize_canonical_to_view(unb_doc.canonical_text_S), minilm_tok, max_vis_tokens=18
    )
    assert len(unb_res.chunks) == 2
    assert unb_res.coverage_lost_due_to_chunking == 0
    assert all(ch.token_count_with_special <= 18 for ch in unb_res.chunks)
    assert "".join(ch.assembled_text.split("\n", 1)[1] for ch in unb_res.chunks) == unbroken

    footer_lines = "\n".join(f"== {name} ==\n" for name in sorted(BOILERPLATE_FOOTER_ALLOWLIST))
    complex_s = (
        "== P1 ==\n"
        "=== P2 ===\n"
        "==== C1 ====\nNội dung.\n"
        "=== P3 ===\n"
        "==== Xem thêm ====\n"
        "== Tham khảo ==\nGiữ lại.\n"
        + footer_lines
    )
    comp_doc = _doc("t5-complex-parent", complex_s)
    comp_res = c1.chunk_document_detailed(
        comp_doc, sanitize_canonical_to_view(complex_s), minilm_tok
    )
    assert comp_res.coverage_lost_due_to_chunking == 0
    breadcrumbs = [
        (c.section_heading, c.section_breadcrumb, c.metadata["heading_only"])
        for c in comp_res.chunks
    ]
    assert ("C1", "P1 > P2 > C1", False) in breadcrumbs
    assert ("P3", "P1 > P3", True) in breadcrumbs
    assert ("Tham khảo", "Tham khảo", False) in breadcrumbs
    assert {e["heading"] for e in comp_res.omitted_boilerplate_headings} == BOILERPLATE_FOOTER_ALLOWLIST

    osm_single = _doc("t5-osm-1line", "Hồ Tây.", source_type="osm_useful_structured")
    osm_res = c1.chunk_document_detailed(
        osm_single, sanitize_canonical_to_view(osm_single.canonical_text_S), minilm_tok
    )
    assert len(osm_res.chunks) == 1
    assert osm_res.chunks[0].assembled_text.startswith("Địa điểm | OSM_Facts\n")

    ov_doc = _doc("t5-overture-line", "0.8542. Note.\nDòng hai.", source_type="overture_places_parquet")
    ov_res = c1.chunk_document_detailed(
        ov_doc, sanitize_canonical_to_view(ov_doc.canonical_text_S), minilm_tok
    )
    assert len(ov_res.chunks) == 1 and ov_res.coverage_lost_due_to_chunking == 0


def test_t5_chunker_c0_provenance_whitespace_and_visibility_edges(minilm_tok: Any) -> None:
    from w07_retrieval.chunker_c0 import C0Chunker
    from w07_retrieval.sanitizer import sanitize_canonical_to_view
    from w07_retrieval.schema import load_canonical_document
    from w07_retrieval.visibility import (
        _clone_tokenizer,
        compute_provenance_visible_s_spans,
    )

    text_s = (
        "Câu một có đủ mười từ tiếng Việt rõ ràng để giữ lại.  "
        "Câu hai cũng có đủ mười từ tiếng Việt rõ ràng để giữ lại."
    )
    doc = load_canonical_document(
        {
            "document_id": "t5-c0-ws",
            "source_type": "wikipedia_vi",
            "title": "Mẫu",
            "language": "vi",
            "canonical_text_S": text_s,
        }
    )
    san = sanitize_canonical_to_view(text_s)
    chunks = C0Chunker().chunk_document(doc, san, minilm_tok)
    assert len(chunks) == 1
    assert len([s for s in chunks[0].assembled_segments if s["kind"] == "CANONICAL_BODY_V"]) == 2
    assert len([s for s in chunks[0].assembled_segments if s["kind"] == "SYNTHETIC_HEADER"]) == 2

    assert (
        compute_provenance_visible_s_spans(
            chunks[0].assembled_text, chunks[0].assembled_segments, [(0, 0), (0, 5)], 0, san.segments
        )
        == []
    )
    assert (
        compute_provenance_visible_s_spans(
            "Header only",
            [{"kind": "SYNTHETIC_HEADER", "a_start": 0, "a_end": 11}],
            [(0, 0), (0, 6), (7, 11), (0, 0)],
            128,
            san.segments,
        )
        == []
    )
    with pytest.raises(TypeError):
        _clone_tokenizer("not_a_tokenizer", max_tokens=128)


def test_t5_bm25_zero_match_all_empty_nfc_aggregation_and_tiebreak() -> None:
    import numpy as np

    from w07_retrieval.bm25 import BM25Index, analyze_text
    from w07_retrieval.schema import ChunkRecord

    with pytest.raises(TypeError):
        analyze_text(None)  # type: ignore[arg-type]

    assert analyze_text("HO\u0300A BI\u0300NH 19.500") == analyze_text("hòa bình 19.500")

    empty_idx = BM25Index([])
    assert empty_idx.avgdl == 0.0
    assert empty_idx.score_chunks("hà nội").shape == (0,)

    def _dummy_chunk(cid: str, did: str, text: str) -> ChunkRecord:
        return ChunkRecord(
            chunk_id=cid,
            document_id=did,
            chunker="C1",
            chunk_index=0,
            title=did,
            poi_id=None,
            source_type="wikipedia_vi",
            language="vi",
            section_heading="H",
            section_breadcrumb="H",
            assembled_text=text,
            assembled_segments=[{"kind": "SYNTHETIC_HEADER", "a_start": 0, "a_end": len(text)}],
            heading_spans=[],
            body_v_span=None,
            c_full_s_spans=[],
            c_vis_s_spans_dense=[],
            c_vis_s_spans_bm25=[],
            token_count_with_special=2,
            word_count=0,
            content_hash="0" * 64,
        )

    punct_idx = BM25Index([_dummy_chunk("c1", "d1", "!!!"), _dummy_chunk("c2", "d2", "   ")])
    assert punct_idx.avgdl == 0.0
    assert np.array_equal(punct_idx.score_chunks("hà nội"), np.zeros(2, dtype=np.float64))

    norm_idx = BM25Index(
        [_dummy_chunk("c1", "d1", "phở bò hà nội"), _dummy_chunk("c2", "d2", "bún chả")],
        query_term_aggregation="multiset",
    )
    uniq_idx = BM25Index(
        [_dummy_chunk("c1", "d1", "phở bò hà nội"), _dummy_chunk("c2", "d2", "bún chả")],
        query_term_aggregation="unique",
    )
    assert norm_idx.idf("nonexistent_xyz") == 0.0
    assert norm_idx.idf("phở") > 0.0
    assert np.array_equal(norm_idx.score_chunks("???"), np.zeros(2, dtype=np.float64))
    assert norm_idx.score_chunks("phở phở phở")[0] == pytest.approx(
        3.0 * uniq_idx.score_chunks("phở phở phở")[0], rel=1e-12
    )

    bad_agg = BM25Index(
        [_dummy_chunk("c1", "d1", "phở")],
        query_term_aggregation="invalid",  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="Unknown query_term_aggregation"):
        bad_agg.score_chunks("phở")


def test_t5_dense_hard_blocking_and_fail_closed_snapshot_guards(tmp_path: Path) -> None:
    from w07_retrieval.dense import (
        DenseIndex,
        MockEmbedder,
        OfflineDenseEmbedder,
        assert_not_mock_embedder,
        get_embedder,
    )

    with pytest.raises(RuntimeError):
        MockEmbedder()
    mock_inst = MockEmbedder.__new__(MockEmbedder)
    with pytest.raises(RuntimeError):
        mock_inst.embed_text("hi")
    with pytest.raises(RuntimeError):
        mock_inst.embed_batch(["hi"])
    with pytest.raises(RuntimeError):
        get_embedder("paraphrase-multilingual-MiniLM-L12-v2", fallback=True)

    class _NamedMock:
        model_name = "ok"

    class _ModelMockAttr:
        model_name = "mock-minilm"

    class _PlainObj:
        model_name = "paraphrase"

    for bad_emb in (
        mock_inst,
        _NamedMock(),
        _ModelMockAttr(),
        _PlainObj(),
        OfflineDenseEmbedder.__new__(OfflineDenseEmbedder),
    ):
        with pytest.raises(RuntimeError):
            assert_not_mock_embedder(bad_emb)
        with pytest.raises(RuntimeError):
            DenseIndex([], bad_emb)  # type: ignore[arg-type]

    with pytest.raises(FileNotFoundError):
        OfflineDenseEmbedder(snapshot_dir=tmp_path / "missing_snap")

    snap_no_cfg = tmp_path / "snap_no_cfg"
    snap_no_cfg.mkdir()
    with pytest.raises(FileNotFoundError, match="config.json"):
        OfflineDenseEmbedder(snapshot_dir=snap_no_cfg)

    snap_no_tok = tmp_path / "snap_no_tok"
    snap_no_tok.mkdir()
    (snap_no_tok / "config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="tokenizer.json"):
        OfflineDenseEmbedder(snapshot_dir=snap_no_tok)

    snap_bad_sha = tmp_path / "snap_bad_sha"
    snap_bad_sha.mkdir()
    (snap_bad_sha / "config.json").write_text("{}", encoding="utf-8")
    (snap_bad_sha / "tokenizer.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        OfflineDenseEmbedder(snapshot_dir=snap_bad_sha, verify_tokenizer_sha256=True)


def test_t5_fusion_collapse_validation_tiebreaks_and_rrf_edges() -> None:
    from w07_retrieval.fusion import RankedDocument, collapse_chunk_scores, fuse_rrf
    from w07_retrieval.schema import ChunkRecord

    def _mk_chunk(
        did: str, cidx: int, cid: str, vis_d: list[list[int]], vis_b: list[list[int]]
    ) -> ChunkRecord:
        return ChunkRecord(
            chunk_id=cid,
            document_id=did,
            chunker="C0",
            chunk_index=cidx,
            title=did,
            poi_id=None,
            source_type="wikipedia_vi",
            language="vi",
            section_heading="H",
            section_breadcrumb="H",
            assembled_text="txt",
            assembled_segments=[{"kind": "SYNTHETIC_HEADER", "a_start": 0, "a_end": 3}],
            heading_spans=[],
            body_v_span=None,
            c_full_s_spans=[[0, 10]],
            c_vis_s_spans_dense=vis_d,
            c_vis_s_spans_bm25=vis_b,
            token_count_with_special=5,
            word_count=1,
            content_hash="0" * 64,
        )

    c_a1 = _mk_chunk("doc-a", 1, "c-a1", [[0, 2]], [[0, 10]])
    c_a0 = _mk_chunk("doc-a", 0, "c-a0", [[0, 3]], [[0, 10]])
    c_b0 = _mk_chunk("doc-b", 0, "c-b0", [[0, 4]], [[0, 10]])
    c_c0 = _mk_chunk("doc-c", 0, "c-c0", [[0, 5]], [[0, 10]])

    with pytest.raises(ValueError, match="Length mismatch"):
        collapse_chunk_scores([c_a0], [1.0, 2.0], retriever_name="BM25")
    with pytest.raises(ValueError, match="Unsupported retriever_name"):
        collapse_chunk_scores([c_a0], [1.0], retriever_name="RRF")  # type: ignore[arg-type]

    bm25_collapsed = collapse_chunk_scores(
        [c_a1, c_b0, c_a0, c_c0], [0.5, 0.5, 0.5, 0.0], retriever_name="BM25", min_score_exclusive=0.0
    )
    assert [(r.document_id, r.rep_chunk.chunk_id, r.c_vis_s_spans) for r in bm25_collapsed] == [
        ("doc-a", "c-a0", [[0, 10]]),
        ("doc-b", "c-b0", [[0, 10]]),
    ]

    dense_collapsed = collapse_chunk_scores(
        [c_a0, c_c0], [0.0, -0.5], retriever_name="Dense", min_score_exclusive=None
    )
    assert [(r.document_id, r.score, r.c_vis_s_spans) for r in dense_collapsed] == [
        ("doc-a", 0.0, [[0, 3]]),
        ("doc-c", -0.5, [[0, 5]]),
    ]

    assert fuse_rrf([], []) == []

    def _rdoc(
        rank: int, did: str, leg: str, chunk: ChunkRecord, vis: list[list[int]]
    ) -> RankedDocument:
        return RankedDocument(
            rank=rank,
            document_id=did,
            score=1.0 / rank,
            rep_chunk=chunk,
            primary_leg=leg,  # type: ignore[arg-type]
            leg_ranks={leg: rank},
            leg_rep_chunks={
                leg: {"chunk_id": chunk.chunk_id, "chunk_index": chunk.chunk_index, "score": 1.0 / rank}
            },
            c_full_s_spans=[[0, 10]],
            c_vis_s_spans=vis,
        )

    bm_list = [
        _rdoc(1, "doc-x", "BM25", c_a0, [[0, 10]]),
        _rdoc(2, "doc-z", "BM25", c_c0, [[0, 10]]),
        _rdoc(3, "doc-y", "BM25", c_b0, [[0, 10]]),
    ]
    dn_list = [
        _rdoc(1, "doc-y", "Dense", c_b0, [[0, 4]]),
        _rdoc(2, "doc-z", "Dense", c_c0, [[0, 5]]),
        _rdoc(3, "doc-x", "Dense", c_a0, [[0, 3]]),
    ]
    fused = fuse_rrf(bm_list, dn_list, rrf_k=60, candidate_depth=50)
    assert [(r.document_id, r.primary_leg, r.c_vis_s_spans) for r in fused] == [
        ("doc-y", "Dense", [[0, 4]]),
        ("doc-x", "BM25", [[0, 10]]),
        ("doc-z", "Dense", [[0, 5]]),
    ]


def test_t5_blind_packet_rank_invariance_salt_validation_and_doc_edges() -> None:
    from w07_retrieval.blind_packet import (
        BLIND_PACKET_ALLOWLIST_KEYS,
        build_blind_packet_rows_for_query,
        export_blind_packet_jsonl,
        export_multi_query_blind_packet_jsonl,
    )

    corpus_lookup = {
        "d2": {"source_type": "b1b", "language": "vi", "S": "Văn bản hai"},
        "d1": {"source_type": "b1b", "language": "en", "canonical_text_S": "Doc one"},
    }
    r1 = build_blind_packet_rows_for_query("Q1", "q?", ["d1", "d2", "d1"], corpus_lookup, "SALT")
    r2 = build_blind_packet_rows_for_query(
        "Q1", "q?", [{"document_id": "d2"}, {"document_id": "d1"}], corpus_lookup, "SALT"
    )
    assert r1 == r2 and len(r1) == 2
    assert all(set(row.keys()) == BLIND_PACKET_ALLOWLIST_KEYS for row in r1)
    assert build_blind_packet_rows_for_query("Q1", "q?", [], corpus_lookup, "SALT") == []

    for bad_salt in ("", None):
        with pytest.raises(ValueError, match="packet_salt"):
            build_blind_packet_rows_for_query("Q1", "q?", ["d1"], corpus_lookup, bad_salt)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="packet_salt"):
            export_blind_packet_jsonl("Q1", "q?", ["d1"], corpus_lookup, bad_salt)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="packet_salt"):
            export_multi_query_blind_packet_jsonl(
                {"Q1": "q?"}, {"Q1": ["d1"]}, corpus_lookup, bad_salt  # type: ignore[arg-type]
            )

    with pytest.raises(KeyError):
        build_blind_packet_rows_for_query(
            "Q1", "q?", ["bad"], {"bad": {"source_type": "b1b", "language": "vi"}}, "SALT"
        )


def test_t5_schema_malformed_missing_fields_and_osm_edges(tmp_path: Path) -> None:
    from w07_retrieval.schema import (
        ProvenanceSegment,
        build_osm_canonical_text,
        extract_osm_tags,
        format_osm_address,
        load_canonical_document,
        load_corpus_jsonl,
        load_queries_jsonl,
    )

    with pytest.raises(ValueError):
        ProvenanceSegment("SYNTHETIC_HEADER", 5, 2)
    with pytest.raises(ValueError):
        ProvenanceSegment("SYNTHETIC_HEADER", 0, 2, s_start=0, s_end=2)
    with pytest.raises(ValueError):
        ProvenanceSegment("CANONICAL_HEADING_S", 0, 2, s_start=0, s_end=3)
    with pytest.raises(ValueError):
        ProvenanceSegment("CANONICAL_HEADING_S", 0, 2, s_start=0, s_end=2, v_start=0)
    with pytest.raises(ValueError):
        ProvenanceSegment("CANONICAL_BODY_V", 0, 2, v_start=0, v_end=5)
    with pytest.raises(ValueError):
        ProvenanceSegment("UNKNOWN_KIND", 0, 2)  # type: ignore[arg-type]

    with pytest.raises(FileNotFoundError):
        load_corpus_jsonl(tmp_path / "missing_corpus.jsonl")
    with pytest.raises(FileNotFoundError):
        load_queries_jsonl(tmp_path / "missing_queries.jsonl")

    for name, content in (
        ("empty.jsonl", "\n   \n"),
        ("bad_json.jsonl", "{not json\n"),
        ("non_dict.jsonl", "[1, 2, 3]\n"),
        (
            "dup_doc.jsonl",
            json.dumps({"document_id": "d1", "canonical_text_S": "A"})
            + "\n"
            + json.dumps({"document_id": "d1", "canonical_text_S": "B"})
            + "\n",
        ),
    ):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            load_corpus_jsonl(p)

    for name, content in (
        ("q_empty.jsonl", "\n"),
        ("q_bad.jsonl", "{bad\n"),
        ("q_list.jsonl", "[]\n"),
        ("q_missing_key.jsonl", json.dumps({"query_id": "Q1"}) + "\n"),
        ("q_empty_val.jsonl", json.dumps({"query_id": "Q1", "query_text": ""}) + "\n"),
        (
            "q_dup.jsonl",
            json.dumps({"query_id": "Q1", "query_text": "a"})
            + "\n"
            + json.dumps({"query_id": "Q1", "query_text": "b"})
            + "\n",
        ),
    ):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            load_queries_jsonl(p)

    with pytest.raises(ValueError, match="missing canonical text"):
        load_canonical_document({"document_id": "d-no-txt"})
    with pytest.raises(ValueError, match="missing verified OSM source"):
        build_osm_canonical_text({"name": "X", "sources": []})

    osm_content_doc = load_canonical_document(
        {
            "document_id": "osm-direct",
            "source_type": "osm_useful_structured",
            "content": "Hồ Tây tại Hà Nội.",
        }
    )
    assert osm_content_doc.text_field_used == "osm_useful_structured.content"
    assert extract_osm_tags(
        '{"tags": {"_priv": "1", "addr:street": "Hàng Bài", "empty": "  ", "arr": [1]}}'
    ) == {"addr:street": "Hàng Bài"}
    assert (
        format_osm_address(
            {"addr:street": "Hàng Bài", "addr:suburb": "Hoàn Kiếm", "addr:province": "Hà Nội"}
        )
        == "Hàng Bài, Hoàn Kiếm, Hà Nội"
    )
    txt, meta = build_osm_canonical_text(
        {
            "name": "Quán Mẫu",
            "sources": [
                {"source_name": "osm", "source_id": "way/9", "raw_data": {}},
                {"source_name": "osm", "source_id": "node/1", "raw_data": {"tourism": "cafe"}},
            ],
        }
    )
    assert meta["source_id"] == "node/1"
    assert "Quán Mẫu là một địa điểm." in txt


# ---------------------------------------------------------------------------
# 4. src/w07_g4_scorer/** (contracts, query_manifest, judge_gates, metrics, stats, scorer)
# ---------------------------------------------------------------------------


def test_t5_contracts_interval_algebra_edge_cases() -> None:
    assert g4_merge_intervals([]) == []
    assert g4_merge_intervals([(0, 0), (5, 5)]) == []
    assert g4_merge_intervals([(5, 10), (0, 5)]) == [(0, 10)]
    assert g4_merge_intervals([(0, 10), (3, 7), (8, 12)]) == [(0, 12)]

    assert g4_subtract_intervals([], [(0, 5)]) == []
    assert g4_subtract_intervals([(0, 20)], []) == [(0, 20)]
    assert g4_subtract_intervals([(0, 20)], [(5, 10), (7, 15)]) == [(0, 5), (15, 20)]
    assert g4_subtract_intervals([(0, 10)], [(0, 5), (5, 10)]) == []

    assert g4_intervals_contain([], []) is True
    assert g4_intervals_contain([], [(3, 3)]) is True
    assert g4_intervals_contain([(0, 10)], [(0, 5), (5, 10)]) is True
    assert g4_intervals_contain([(0, 5), (5, 10)], [(2, 8)]) is True
    assert g4_intervals_contain([(0, 4), (6, 10)], [(2, 8)]) is False

    for bad in ([0], (0, 1, 2), (True, 5), (0, False), (-1, 5), (5, 3)):
        with pytest.raises(ValueError):
            g4_merge_intervals([bad])  # type: ignore[list-item]


def test_t5_contracts_manifest_tamper_missing_and_row_mismatches(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        verify_rankings_manifest(tmp_path / "missing.jsonl", tmp_path / "missing.json")

    rows = [make_ranking_row(cell_id="C1-RRF", query_id="q1", rank=1, document_id="d1")]
    rk_path, mf_path = write_sealed_rankings_bundle(tmp_path, rows, cells=["C1-RRF"])
    with pytest.raises(FileNotFoundError):
        verify_rankings_manifest(rk_path, tmp_path / "no_manifest.json")

    base_mf = json.loads(mf_path.read_text(encoding="utf-8"))
    for bad_mf, err_re in [
        ({**base_mf, "rankings_file": "other.jsonl"}, "RANKINGS_FILENAME_MISMATCH"),
        ({**base_mf, "rankings_sha256": "xyz"}, "MALFORMED_RANKINGS_SHA256"),
        ({**base_mf, "row_count": -1}, "INVALID_MANIFEST_ROW_COUNT"),
        ({**base_mf, "row_count": True}, "INVALID_MANIFEST_ROW_COUNT"),
        ({**base_mf, "cells": []}, "INVALID_MANIFEST_CELLS"),
        ({**base_mf, "snapshot_id": 123}, "INVALID_MANIFEST_SNAPSHOT_ID"),
    ]:
        bad_mf_path = tmp_path / "bad_mf.json"
        bad_mf_path.write_text(json.dumps(bad_mf), encoding="utf-8")
        with pytest.raises(ValueError, match=err_re):
            verify_rankings_manifest(rk_path, bad_mf_path)

    mismatch_mf = {**base_mf, "row_count": 2}
    mismatch_mf_path = tmp_path / "mismatch_count.json"
    mismatch_mf_path.write_text(json.dumps(mismatch_mf), encoding="utf-8")
    with pytest.raises(ValueError, match="RANKING_ROW_COUNT_MISMATCH"):
        load_sealed_rankings(rk_path, mismatch_mf_path)

    mismatch_cells_mf = {**base_mf, "cells": ["C1-RRF", "C1-BM25"]}
    mismatch_cells_path = tmp_path / "mismatch_cells.json"
    mismatch_cells_path.write_text(json.dumps(mismatch_cells_mf), encoding="utf-8")
    with pytest.raises(ValueError, match="RANKING_CELLS_MISMATCH"):
        load_sealed_rankings(rk_path, mismatch_cells_path)

    dup_rank_rows = [
        make_ranking_row(cell_id="C1-RRF", query_id="q1", rank=1, document_id="d1"),
        make_ranking_row(cell_id="C1-RRF", query_id="q1", rank=1, document_id="d2"),
    ]
    dr_rk, dr_mf = write_sealed_rankings_bundle(tmp_path / "dup_rank", dup_rank_rows, cells=["C1-RRF"])
    with pytest.raises(ValueError, match="DUPLICATE_CELL_QUERY_RANK"):
        load_sealed_rankings(dr_rk, dr_mf)

    dup_doc_rows = [
        make_ranking_row(cell_id="C1-RRF", query_id="q1", rank=1, document_id="d1"),
        make_ranking_row(cell_id="C1-RRF", query_id="q1", rank=2, document_id="d1"),
    ]
    dd_rk, dd_mf = write_sealed_rankings_bundle(tmp_path / "dup_doc", dup_doc_rows, cells=["C1-RRF"])
    with pytest.raises(ValueError, match="DUPLICATE_CELL_QUERY_DOCUMENT"):
        load_sealed_rankings(dd_rk, dd_mf)


def test_t5_contracts_external_qrels_lure_coercion_lineage_and_ml_guards(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError):
        load_external_qrels(tmp_path / "missing_qrels.jsonl")
    empty_q = tmp_path / "empty_qrels.jsonl"
    empty_q.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="EMPTY_EXTERNAL_QRELS_FILE"):
        load_external_qrels(empty_q)

    bad_rows = [
        {"query_id": "q1", "document_id": "d1", "label": "REL_0"},
        {"query_id": "q1", "document_id": "d1", "label": "REL_0", "plausible_unsupported_lure": True},
        {"query_id": "q1", "document_id": "d1", "label": "REL_1", "plausible_unsupported_lure": 1},
        {"query_id": "q1", "document_id": "d1", "label": "REL_2", "plausible_unsupported_lure": 1},
        {"query_id": "q1", "document_id": "d1", "label": "N/A"},
        {"query_id": "q1", "document_id": "d1", "label": "unjudged"},
        {"query_id": "q1", "document_id": "d1", "label": "NA", "plausible_unsupported_lure": 2},
        {"query_id": "q1", "document_id": "d1", "label": "REL_0", "plausible_unsupported_lure": 0, "fillna": 0},
        {
            "query_id": "q1",
            "document_id": "d1",
            "label": "REL_0",
            "plausible_unsupported_lure": 0,
            "source_lineage_id": "   ",
        },
    ]
    for idx, row in enumerate(bad_rows):
        p = write_jsonl(tmp_path / f"bad_qr_{idx}.jsonl", [row])
        with pytest.raises(ValueError):
            load_external_qrels(p)

    dup_p = write_jsonl(
        tmp_path / "dup_qr.jsonl",
        [
            {"query_id": "q1", "document_id": "d1", "label": "REL_2", "plausible_unsupported_lure": 0},
            {"query_id": "q1", "document_id": "d1", "label": "REL_0", "plausible_unsupported_lure": 0},
        ],
    )
    with pytest.raises(ValueError, match="DUPLICATE_QREL_PAIR"):
        load_external_qrels(dup_p)

    qrels = {("q1", "sib_a"): QrelRecord("q1", "sib_a", RelevanceState.REL_2, 0, ((0, 5),), "lin:shared")}
    assert resolve_qrel_state(qrels, "q1", "sib_a") == RelevanceState.REL_2
    assert resolve_qrel_state(qrels, "q1", "sib_b") == RelevanceState.UNJUDGED

    assert_g4_package_zero_ml_imports()
    proc = _run_g4_clean_subprocess(
        
            "import sys\n"
            "from w07_g4_scorer import assert_g4_package_zero_ml_imports, assert_zero_ml_imports\n"
            "assert_g4_package_zero_ml_imports()\n"
            "assert_zero_ml_imports()\n"
            "sys.modules['torch_unrelated_safe_pkg'] = object()\n"
            "assert_zero_ml_imports()\n"
            "sys.modules['torch.nn'] = object()\n"
            "try:\n"
            "    assert_zero_ml_imports()\n"
            "except RuntimeError as exc:\n"
            "    assert 'FORBIDDEN_ML_OR_RETRIEVER_IMPORT' in str(exc), str(exc)\n"
            "else:\n"
            "    raise AssertionError('Expected RuntimeError for torch.nn')\n"
        
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_t5_query_manifest_step_s0_matrix_cluster_and_dev_isolation(tmp_path: Path) -> None:
    valid_q = make_query_dict(query_id="q0", target_city="Hà Nội", target_poi_ids=["poi-hn-01"])
    approved = {
        "poi-hn-01": {"poi_id": "poi-hn-01", "city": "Hà Nội"},
        "poi-dn-01": {"poi_id": "poi-dn-01", "city": "Đà Nẵng"},
    }

    s0_errors = [
        ("MISSING_TARGET_POI_IDS", {k: v for k, v in valid_q.items() if k != "target_poi_ids"}),
        ("DUPLICATE_TARGET_POI_ID_ELEMENT", {**valid_q, "target_poi_ids": ["poi-hn-01", "poi-hn-01"]}),
        ("INVALID_APPROVED_POIS_REGISTRY", valid_q, {}),
        ("UNAPPROVED_TARGET_POI_ID", {**valid_q, "target_poi_ids": ["poi-hn-99"]}, approved),
        ("TARGET_POI_CITY_MISMATCH", {**valid_q, "target_poi_ids": ["poi-dn-01"]}, approved),
        ("MISSING_REQUESTED_FACET_KEYWORDS", {k: v for k, v in valid_q.items() if k != "requested_facet_keywords"}),
        ("MALFORMED_REQUESTED_FACET_KEYWORD_ELEMENT", {**valid_q, "requested_facet_keywords": ["ok", "  "]}),
        ("INVALID_PRE_RANK_ANSWERABILITY", {**valid_q, "pre_rank_answerability": "WRONG_STATE"}),
        ("INVALID_PRE_RANK_ANSWERABILITY", {**valid_q, "pre_rank_answerability": "AMBIGUOUS"}),
        (
            "MISSING_OR_INVALID_QUERY_INTENT_POLARITY",
            {k: v for k, v in valid_q.items() if k != "query_intent_polarity"}
            | {"polarity": "AFFIRMATIVE_FACT_NEED"},
        ),
    ]
    for case in s0_errors:
        exp_code, qm = case[0], case[1]
        reg = case[2] if len(case) == 3 else None
        err = validate_sealed_query_metadata(qm, approved_pois_by_id=reg)
        assert err is not None and err["error_code"] == exp_code

    assert validate_sealed_query_metadata({**valid_q, "scope_mode": "CITY_MULTI_POI", "target_poi_ids": []}) is None
    assert (
        validate_sealed_query_metadata(
            {**valid_q, "scope_mode": "CITY_MULTI_POI", "target_poi_ids": ["poi-hn-01", "poi-hn-02"]}
        )
        is None
    )

    rows, pois50 = build_synthetic_final50_manifest()
    city_dup = copy.deepcopy(rows)
    hn_ans = [r for r in city_dup if r["target_city"] == "Hà Nội" and r["pre_rank_answerability"] == "ANSWERABLE"]
    hn_ans[0]["scope_mode"] = "CITY_MULTI_POI"
    hn_ans[0]["target_poi_ids"] = []
    hn_ans[1]["scope_mode"] = "CITY_MULTI_POI"
    hn_ans[1]["target_poi_ids"] = []
    hn_ans[1]["fact_cluster_id"] = hn_ans[0]["fact_cluster_id"]
    with pytest.raises(ValueError, match="Duplicate atomic"):
        validate_final50_strata_and_city_quota(city_dup, approved_pois_by_id=pois50)

    bad_ans = copy.deepcopy(rows)
    s5_row = next(r for r in bad_ans if r["query_family"] == "S5_UNANSWERABLE_OR_UNSTABLE")
    s5_row["pre_rank_answerability"] = "ANSWERABLE"
    with pytest.raises(ValueError, match="Stratum-answerability mismatch"):
        validate_pre_g3_query_manifest(bad_ans, approved_pois_by_id=pois50)

    json_list_path = tmp_path / "final50.json"
    json_list_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    specs, summary = load_query_manifest(
        json_list_path, enforce_final50_matrix=True, approved_pois_by_id=pois50
    )
    assert len(specs) == 50 and summary["matrix_summary"]["q_ans_count"] == 40

    with pytest.raises(ValueError, match="exceeds maximum"):
        validate_dev_isolation([make_query_dict(query_id=f"d_{i}", split="DEV") for i in range(11)], rows)
    with pytest.raises(ValueError, match="cannot have split='FINAL'"):
        validate_dev_isolation([make_query_dict(query_id="d_fin", split="FINAL")], rows)
    with pytest.raises(ValueError, match="DEV_FINAL_TEXT_OVERLAP"):
        validate_dev_isolation(
            [make_query_dict(query_id="d_txt", split="DEV", query_text=f"  {rows[0]['query_text'].upper()}  ")],
            rows,
        )


def test_t5_judge_gates_s1_s4_gspan_ce9_ce4_and_rel1() -> None:
    s_text = "Phở Thìn [SUPPRESSED_FACT_CONFLICT: 2024] mở cửa lúc 06:00."
    doc = {"canonical_text_S": s_text, "city": "Hà Nội", "poi_id": "poi-hn-01"}
    q_aff = make_query_dict(query_id="q1", target_city="Hà Nội", target_poi_ids=["poi-hn-01"])

    assert (
        verify_judge_quote_against_chunk(s_text, "   ", 0, 3, [], [(0, len(s_text))], [(0, len(s_text))])["reason"]
        == "EMPTY_QUOTE"
    )
    assert (
        verify_judge_quote_against_chunk(
            s_text, "Phở", True, 3, [], [(0, len(s_text))], [(0, len(s_text))]  # type: ignore[arg-type]
        )["reason"]
        == "NON_INTEGER_OR_BOOLEAN_OFFSET"
    )
    assert (
        verify_judge_quote_against_chunk(s_text, "Phở", 0, 999, [], [(0, len(s_text))], [(0, len(s_text))])["reason"]
        == "OUT_OF_RANGE_OFFSET"
    )
    assert (
        verify_judge_quote_against_chunk(s_text, "XYZ", 0, 3, [], [(0, len(s_text))], [(0, len(s_text))])["reason"]
        == "OFFSET_SUBSTRING_MISMATCH"
    )

    tag = "[SUPPRESSED_FACT_CONFLICT: 2024]"
    t_s = s_text.index(tag)
    assert (
        verify_judge_quote_against_chunk(
            s_text, tag, t_s, t_s + len(tag), [], [(0, len(s_text))], [(0, len(s_text))]
        )["reason"]
        == "PROHIBITED_AUDIT_OR_UNVERIFIED_TAG_OVERLAP"
    )

    q_tail = "mở cửa lúc 06:00."
    tail_s = s_text.index(q_tail)
    span_res = verify_judge_quote_against_chunk(
        s_text, q_tail, tail_s, tail_s + len(q_tail), [], [(0, len(s_text))], [(0, 10)]
    )
    assert span_res["valid_canonical_quote"] is True
    assert span_res["in_returned_chunk"] is True
    assert span_res["in_encoder_visible_prefix"] is False
    assert span_res["utf8_byte_end"] - span_res["utf8_byte_start"] > len(q_tail)

    for raw, exp_err in [
        (123, "NON_STRING_RAW_RESPONSE"),
        (json.dumps({"grade": "REL_3"}), "INVALID_GRADE_ENUM"),
        (json.dumps({"grade": "REL_0", "rationale": 42}), "INVALID_RATIONALE_TYPE"),
        (json.dumps({"grade": "NA", "char_start": 0}), "INVALID_NON_POSITIVE_FIELD_TYPES"),
        (
            json.dumps({"grade": "REL_1", "evidence_quote": 99, "char_start": 0, "char_end": 3}),
            "INVALID_QUOTE_TYPE",
        ),
    ]:
        res = validate_judge_response(raw, doc, [], q_aff)
        assert res["state"] == "ERROR" and res["error_code"] == exp_err

    na_ok = validate_judge_response(json.dumps({"grade": "NA", "evidence_quote": ""}), doc, [], q_aff)
    assert na_ok["state"] == "NA" and na_ok["unresolved"] is True and na_ok["max_admissible_gain"] == 3

    rel1_ok = validate_judge_response(
        json.dumps({"grade": "REL_1", "evidence_quote": q_tail, "char_start": tail_s, "char_end": tail_s + len(q_tail)}),
        doc,
        [],
        q_aff,
    )
    assert rel1_ok["state"] == "REL_1" and rel1_ok["confirmed_gain"] == 1 and rel1_ok["max_admissible_gain"] == 1

    doc_wrong_poi = {"canonical_text_S": s_text, "city": "Hà Nội", "poi_id": "poi-hn-99"}
    res_poi = validate_judge_response(
        json.dumps({"grade": "REL_2", "evidence_quote": q_tail, "char_start": tail_s, "char_end": tail_s + len(q_tail)}),
        doc_wrong_poi,
        [],
        q_aff,
    )
    assert res_poi["error_code"] == "SAFETY_BLOCK_NON_TARGET_POI_CE9" and res_poi["max_admissible_gain"] == 0


def test_t5_judge_gates_order_ab_halts_kappa_concordance_and_r09_r10() -> None:
    docs = {
        f"d{i}": {"canonical_text_S": f"Địa điểm {i} mở cửa 08:00.", "city": "Hà Nội", "poi_id": "poi-hn-01"}
        for i in range(1, 7)
    }
    q_meta = [
        make_query_dict(query_id=f"q{i}", target_city="Hà Nội", target_poi_ids=["poi-hn-01"])
        for i in range(1, 7)
    ]
    rankings_rrf = {f"q{i}": [f"d{i}"] + [f"d{j}" for j in range(1, 7) if j != i] for i in range(1, 7)}
    rankings_bm25 = {f"q{i}": [f"d{(i % 6) + 1}", f"d{i}"] for i in range(1, 7)}

    resp_ok: dict[tuple[str, str], str] = {}
    for i in range(1, 7):
        for j in range(1, 7):
            if i == j:
                txt = docs[f"d{j}"]["canonical_text_S"]
                resp_ok[(f"q{i}", f"d{j}")] = json.dumps(
                    {"grade": "REL_2", "evidence_quote": txt, "char_start": 0, "char_end": len(txt)}
                )
            else:
                resp_ok[(f"q{i}", f"d{j}")] = json.dumps({"grade": "REL_0"})

    dual_ok = evaluate_dual_judge_concordance(
        queries_meta=q_meta,
        docs_by_id=docs,
        removed_by_doc_id={},
        rankings_by_cell={"C1-RRF": rankings_rrf, "C1-BM25": rankings_bm25},
        judge_a_responses=resp_ok,
        judge_b_responses=resp_ok,
    )
    assert dual_ok["quadratic_weighted_kappa"] == 1.0
    assert dual_ok["k1_k5_concordance"]["K1"]["verdict"] == "SUPPORTED_AI_PROXY_CONCORDANT"

    resp_err = dict(resp_ok)
    resp_err[("q1", "d2")] = "{bad_json"
    halt_dev = score_validated_judge_rankings(
        q_meta, docs, {}, resp_err, rankings_rrf, dev_error_cap=0.01
    )
    assert halt_dev["status"] == "HALT_DEV_ERROR_CAP_EXCEEDED" and halt_dev["confirmable"] is False

    resp_na = dict(resp_ok)
    for j in range(1, 7):
        resp_na[("q1", f"d{j}")] = json.dumps({"grade": "NA"})
    halt_tau = score_validated_judge_rankings(
        q_meta, docs, {}, resp_na, rankings_rrf, tau_unresolved=0.05
    )
    assert halt_tau["status"] == "INCONCLUSIVE_INSUFFICIENT_JUDGE_COVERAGE"
    assert halt_tau["halt_reason"] == "TAU_UNRESOLVED_EXCEEDED"

    for j in range(1, 7):
        resp_na[("q2", f"d{j}")] = json.dumps({"grade": "NA"})
    halt_zidcg = score_validated_judge_rankings(
        q_meta, docs, {}, resp_na, rankings_rrf, tau_unresolved=0.50
    )
    assert halt_zidcg["status"] == "INCONCLUSIVE_INSUFFICIENT_JUDGE_COVERAGE"
    assert halt_zidcg["halt_reason"] == "ZERO_IDCG_INCOMPLETE_GT_20PCT"

    incomplete_a = {k: v for k, v in resp_ok.items() if k != ("q1", "d1")}
    dual_halt = evaluate_dual_judge_concordance(
        queries_meta=q_meta,
        docs_by_id=docs,
        removed_by_doc_id={},
        rankings_by_cell={"C1-RRF": rankings_rrf, "C1-BM25": rankings_bm25},
        judge_a_responses=incomplete_a,
        judge_b_responses=resp_ok,
    )
    assert dual_halt["LLMJudged-nDCG@10_judge_A"] is None
    assert dual_halt["k1_k5_concordance"] == {}

    assert quadratic_weighted_kappa([0, 0, 0], [0, 0, 0]) == 1.0
    assert quadratic_weighted_kappa([0, 0, 0], [2, 2, 2]) == 0.0
    with pytest.raises(ValueError):
        quadratic_weighted_kappa([], [])
    with pytest.raises(ValueError):
        quadratic_weighted_kappa([0, 3], [0, 1])

    sha = "a" * 64
    for mid in ("claude-haiku-5-5", "gemini-3.8-flash", "gpt-6-luna"):
        cfg = build_pinned_judge_api_config(
            mid,
            prompt_template_sha256=sha,
            response_schema_sha256=sha,
            blind_packet_manifest_sha256=sha,
            raw_response_log_path="evidence/j.jsonl",
        )
        assert validate_judge_api_config(cfg)["model_id"] == mid

    with pytest.raises(ValueError, match="Offline CPU model"):
        assert_supported_non_deprecated_judge_model(
            "qwen2.5-7b-instruct-gguf", local_ram_benchmark_passed=False
        )
    cfg_local = build_pinned_judge_api_config(
        "qwen2.5-7b-instruct-gguf",
        prompt_template_sha256=sha,
        response_schema_sha256=sha,
        blind_packet_manifest_sha256=sha,
        raw_response_log_path="evidence/local.jsonl",
        local_ram_benchmark_passed=True,
    )
    assert (
        validate_judge_api_config(cfg_local, local_ram_benchmark_passed=True)["provider_api_profile"]
        == "LOCAL_LLAMA_CPP_GGUF_GREEDY"
    )

    with pytest.raises(ValueError, match="share model family"):
        assert_distinct_non_deprecated_judge_pair("claude-haiku-5-5", "claude-sonnet-5-5")

    with pytest.raises(ValueError, match="UNFILLED_BLANK_MODEL_SNAPSHOT"):
        assert_valid_model_snapshot_identity("gpt-6-luna", "[BLANK]")
    with pytest.raises(ValueError, match="UNALLOWLISTED_VENDOR_MODEL_SNAPSHOT_ID"):
        assert_valid_model_snapshot_identity("gpt-6-luna", "gpt-6-luna-unknown")
    with pytest.raises(ValueError, match="UNAPPROVED_MODEL_SNAPSHOT_ID"):
        assert_valid_model_snapshot_identity(
            "gpt-6.1-sol", "gpt-6.1-sol", approved_model_snapshot_id="gpt-6.1-sol-2026-08-05"
        )

    bad_cfg = copy.deepcopy(cfg)
    bad_cfg["api_params"]["temperature"] = 0.0
    bad_cfg["config_manifest_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="FORBIDDEN_PROVIDER_API_PARAM"):
        validate_judge_api_config(bad_cfg)

    ep_a = seal_expected_pairs_manifest(
        judging_order="ORDER_A",
        expected_pairs=[("q1", "d1")],
        query_manifest_sha256="b" * 64,
        sanitized_v_corpus_sha256="c" * 64,
        sealed_at_utc="2026-11-20T10:00:00Z",
        g3_rankings_bundle_sha256=None,
        expected_v_corpus_sha256=None,
    )
    assert verify_sealed_expected_pairs_manifest(
        ep_a, earliest_judge_dispatch_utc="2026-11-20T10:00:01Z", expected_v_corpus_sha256=None
    ) == {("q1", "d1")}
    with pytest.raises(ValueError, match="TEMPORAL_SEALING_VIOLATION"):
        verify_sealed_expected_pairs_manifest(
            ep_a, earliest_judge_dispatch_utc="2026-11-20T10:00:00Z", expected_v_corpus_sha256=None
        )

    assert (
        evaluate_budget_and_retry_circuit_breakers(
            1.0, 2.0, 10.0, sync_or_fast_tier_requested=True
        )["halt_code"]
        == "ABORT_UNAPPROVED_SYNC_OR_FAST_TIER"
    )
    assert (
        evaluate_budget_and_retry_circuit_breakers(1.0, 2.0, 10.0, failed_batches=2)["halt_code"]
        == "HOLD_PROVIDER_INSTABILITY"
    )
    assert evaluate_budget_and_retry_circuit_breakers(1.0, 2.0, 10.0)["allowed"] is True
    assert (
        check_g5_gate_unlock(
            {"HumanGraded-GoMate-nDCG@10": "NOT_PERFORMED"}, separate_signed_g5_protocol=True
        )
        is True
    )


def test_t5_metrics_bounds_span_hits_and_recall_edges() -> None:
    assert span_hit_matches([(10, 25)], [(10, 20)], [(24, 30)]) is False
    assert span_hit_matches([(0, 10)], [(10, 20)], [(10, 20)]) is False

    canon = "abcd efg hij klmno"
    assert (
        span_hit_matches(
            [(0, 18)], [(0, 18)], [], is_split_atomic_gt128=True, canonical_text_S=canon, has_contradiction=True
        )
        is False
    )
    assert (
        span_hit_matches(
            [(0, 5)], [(0, 5)], [], is_split_atomic_gt128=True, canonical_text_S="     "
        )
        is False
    )
    c20 = "abcdefghij" * 2
    assert (
        span_hit_matches(
            [(0, 8), (12, 20)], [(0, 20)], [], is_split_atomic_gt128=True, canonical_text_S=c20
        )
        is True
    )
    assert (
        span_hit_matches(
            [(0, 8), (13, 20)], [(0, 20)], [], is_split_atomic_gt128=True, canonical_text_S=c20
        )
        is False
    )

    q_alt = make_query_spec(
        query_id="q_alt",
        required_evidence_facets=[
            {"alternatives": [{"doc_id": "d1", "spans": [[0, 5]]}]},
            {"document_id": "d2", "s_spans": [[0, 5]]},
        ],
    )
    rows = [
        make_ranking_row(
            cell_id="C1-RRF",
            query_id="q_alt",
            rank=1,
            document_id="d1",
            c_full_s_spans=[[0, 5]],
            c_vis_s_spans=[[0, 5]],
        ),
        make_ranking_row(
            cell_id="C1-RRF",
            query_id="q_alt",
            rank=2,
            document_id="d2",
            c_full_s_spans=[[0, 5]],
            c_vis_s_spans=[[0, 5]],
        ),
    ]
    assert compute_span_hits_at_10(rows, q_alt, {}) == {
        "evidence_span_hit_at_10": 1.0,
        "visible_evidence_span_hit_at_10": 1.0,
    }
    assert compute_span_hits_at_10(rows, make_query_spec(query_id="q_none"), {}) == {
        "evidence_span_hit_at_10": None,
        "visible_evidence_span_hit_at_10": None,
    }
    assert recall_at_k(["d1"], {"d1": QrelRecord("q", "d1", RelevanceState.REL_0, 0, (), None)}) is None

    ex_inc = exact_ndcg10_bounds(["d1"], ["d1", "d2"], {"d1": 0}, zero_capped_doc_ids={"d1"})
    assert ex_inc["status"] == "ZERO_IDCG_INCOMPLETE" and ex_inc["lower"] == 0.0 and ex_inc["upper"] == 1.0
    cons_inc = conservative_ndcg10_enclosure(["d1"], ["d1", "d2"], {"d1": 0}, zero_capped_doc_ids={"d1"})
    assert cons_inc["status"] == "ZERO_IDCG_INCOMPLETE" and cons_inc["lower"] == 0.0 and cons_inc["upper"] == 1.0

    q_unres = {"d1": QrelRecord("q", "d1", RelevanceState.NA, None, (), None)}
    with pytest.raises(ValueError, match="CERT2_INCOMPLETE_UNRESOLVED_TOP10"):
        coupled_ndcg10_bounds(["d1"], ["d1", "d2"], q_unres, strict_cert2=True)
    non_strict = coupled_ndcg10_bounds(["d1"], ["d1", "d2"], q_unres, strict_cert2=False)
    assert non_strict["dcg"] is None and non_strict["ndcg_u"] == 1.0

    q_zpe = {"d1": QrelRecord("q", "d1", RelevanceState.REL_0, 0, (), None)}
    assert coupled_ndcg10_bounds(["d1"], ["d1"], q_zpe)["status"] == Cert4Status.ZERO_POSITIVE_EXACT.value
    with pytest.raises(ValueError, match="INVALID_UNRESOLVED"):
        coupled_ndcg10_bounds(["d1"], ["d1", "d2"], q_zpe)

    q_p203 = {
        "d1": QrelRecord("q", "d1", RelevanceState.REL_0, 0, (), None),
        "d2": QrelRecord("q", "d2", RelevanceState.REL_2, 0, ((0, 5),), None),
    }
    p203 = coupled_ndcg10_bounds(["d1"], ["d1", "d2", "d3_unjudged"], q_p203, strict_cert2=True)
    assert p203["ndcg_l"] == 0.0 and p203["ndcg_u"] == 0.0
    assert p203["status"] == Cert4Status.BOUNDED_NOT_EXACT.value

    with pytest.raises(ValueError):
        coupled_pairwise_contrast_bounds({}, {}, {}, {})
    with pytest.raises(ValueError, match="Non-positive IDCG"):
        coupled_pairwise_contrast_bounds({"q1": 0.0}, {"q1": 0.0}, {"q1": 0.0}, {"q1": 1.0})


def test_t5_stats_bca_holm_and_winner_gate_boundaries() -> None:
    for bad in ([], [[0.1, 0.2]], [float("nan")], [float("inf")]):
        with pytest.raises(ValueError):
            paired_bootstrap_and_sign_flip(bad)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        paired_bootstrap_and_sign_flip([0.1, 0.2], b_resamples=0)

    n1 = paired_bootstrap_and_sign_flip([0.04])
    assert n1.ci_method == "DEGENERATE_CONSTANT" and n1.ci_low == 0.04 and n1.ci_high == 0.04

    assert holm_bonferroni({}) == {}
    for bad_p in (float("inf"), float("-inf"), float("nan"), -1e-6, 1.0001, False):
        with pytest.raises(ValueError):
            holm_bonferroni({"K1": bad_p})  # type: ignore[dict-item]

    st_ok = PairedStatsResult(
        n=40,
        mean_delta=0.04,
        percentile_ci_low=0.01,
        percentile_ci_high=0.07,
        bca_ci_low=0.005,
        bca_ci_high=0.07,
        ci_low=0.005,
        ci_high=0.07,
        ci_method="BCA_AND_PERCENTILE",
        p_mc=0.001,
        test_method="MONTE_CARLO_SIGN_FLIP",
        p0=0.5,
        acceleration=0.0,
    )
    assert (
        evaluate_winner_gate(
            "K1",
            "A",
            "B",
            delta_min=0.030,
            delta_max=0.040,
            d_low_vec=[0.03],
            stats_res=st_ok,
            p_mc_holm=0.0499,
            vis_span_delta=0.0,
            fse_a=0.20,
            fse_b=0.10,
        ).decision
        == "A_OVER_B"
    )

    assert (
        evaluate_winner_gate(
            "K1",
            "A",
            "B",
            delta_min=0.030,
            delta_max=0.040,
            d_low_vec=[0.03],
            stats_res=st_ok,
            p_mc_holm=0.05,
            vis_span_delta=0.0,
            fse_a=0.10,
            fse_b=0.10,
        ).decision
        == "NO_CLEAR_WINNER"
    )

    assert (
        evaluate_winner_gate(
            "K1",
            "A",
            "B",
            delta_min=0.030,
            delta_max=0.040,
            d_low_vec=[0.03],
            stats_res=st_ok,
            p_mc_holm=0.01,
            vis_span_delta=0.0,
            fse_a=0.201,
            fse_b=0.10,
        ).decision
        == "NO_CLEAR_WINNER"
    )

    st_bca_neg = PairedStatsResult(
        n=40,
        mean_delta=0.04,
        percentile_ci_low=0.01,
        percentile_ci_high=0.07,
        bca_ci_low=-0.001,
        bca_ci_high=0.07,
        ci_low=-0.001,
        ci_high=0.07,
        ci_method="BCA_AND_PERCENTILE",
        p_mc=0.001,
        test_method="MONTE_CARLO_SIGN_FLIP",
        p0=0.5,
        acceleration=0.0,
    )
    assert (
        evaluate_winner_gate(
            "K1",
            "A",
            "B",
            delta_min=0.035,
            delta_max=0.040,
            d_low_vec=[0.035],
            stats_res=st_bca_neg,
            p_mc_holm=0.01,
            vis_span_delta=0.0,
            fse_a=0.0,
            fse_b=0.0,
        ).decision
        == "NO_CLEAR_WINNER"
    )

    st_pct_only = PairedStatsResult(
        n=40,
        mean_delta=0.04,
        percentile_ci_low=0.01,
        percentile_ci_high=0.07,
        bca_ci_low=None,
        bca_ci_high=None,
        ci_low=0.01,
        ci_high=0.07,
        ci_method="PERCENTILE_FALLBACK_BCA_UNDEFINED",
        p_mc=0.001,
        test_method="MONTE_CARLO_SIGN_FLIP",
        p0=1.0,
        acceleration=None,
    )
    assert (
        evaluate_winner_gate(
            "K1",
            "A",
            "B",
            delta_min=0.035,
            delta_max=0.040,
            d_low_vec=[0.035],
            stats_res=st_pct_only,
            p_mc_holm=0.01,
            vis_span_delta=0.0,
            fse_a=0.0,
            fse_b=0.0,
        ).decision
        == "A_OVER_B"
    )

    ev_bni = evaluate_winner_gate(
        "K2",
        "A",
        "B",
        delta_min=0.0299,
        delta_max=0.030,
        d_low_vec=[0.0299],
        stats_res=st_ok,
        p_mc_holm=0.001,
        vis_span_delta=0.0,
        fse_a=0.0,
        fse_b=0.0,
    )
    assert ev_bni.decision == "NO_CLEAR_WINNER" and ev_bni.bounds_non_identifying is True
    assert "BOUNDS_NON_IDENTIFYING" in ev_bni.flags


def test_t5_scorer_strict_pool_qans_lineage_none_judges_and_cli(tmp_path: Path) -> None:
    bundle = build_fx15_smoke_bundle(tmp_path)

    mf, rows = load_sealed_rankings(bundle["rankings_path"], bundle["manifest_path"])
    q_specs, _ = load_query_manifest(bundle["queries_path"])
    qrels = load_external_qrels(bundle["qrels_path"])

    # Clean isolated subprocess verifies enforce_clean_sys_modules=True regardless of pytest order.
    clean_strict_script = "\n".join(
        [
            "from pathlib import Path",
            "from w07_g4_scorer import load_external_qrels, load_query_manifest, load_sealed_rankings, score_g4",
            f"rk = Path({str(bundle['rankings_path'])!r})",
            f"mfp = Path({str(bundle['manifest_path'])!r})",
            f"qp = Path({str(bundle['queries_path'])!r})",
            f"qrp = Path({str(bundle['qrels_path'])!r})",
            "mf, rows = load_sealed_rankings(rk, mfp)",
            "q_specs, _ = load_query_manifest(qp)",
            "qrels = load_external_qrels(qrp)",
            "try:",
            "    score_g4(",
            "        manifest=mf, ranking_rows=rows, query_specs=q_specs, qrels=qrels,",
            "        pool_doc_ids_by_q={'q_ans_1': ['d_pos_1', 'd_pos_2', 'd_neg_1', 'd_lure_1', 'd_unjudged_pool']},",
            "        strict_full_pool=True, enforce_clean_sys_modules=True,",
            "    )",
            "except ValueError as exc:",
            "    assert 'G4_BLOCKER_STRICT_FULL_POOL_CERT_FAILED' in str(exc), str(exc)",
            "else:",
            "    raise AssertionError('Expected strict_full_pool ValueError')",
        ]
    )
    proc_strict = _run_g4_clean_subprocess(clean_strict_script)
    assert proc_strict.returncode == 0, proc_strict.stdout + proc_strict.stderr

    qrels_with_unjudged = dict(qrels)
    qrels_with_unjudged[("q_ans_1", "d_unjudged_pool")] = QrelRecord(
        "q_ans_1", "d_unjudged_pool", RelevanceState.UNJUDGED, None, (), None
    )
    with pytest.raises(ValueError, match="G4_BLOCKER_STRICT_FULL_POOL_CERT_FAILED"):
        score_g4(
            manifest=mf,
            ranking_rows=rows,
            query_specs=q_specs,
            qrels=qrels_with_unjudged,
            strict_full_pool=True,
            enforce_clean_sys_modules=False,
        )

    qrels_missing = {k: v for k, v in qrels.items() if k != ("q_ans_1", "d_pos_1")}
    with pytest.raises(ValueError, match="G4_BLOCKER_INVALID_UNRESOLVED"):
        score_g4(
            manifest=mf,
            ranking_rows=rows,
            query_specs=q_specs,
            qrels=qrels_missing,
            enforce_clean_sys_modules=False,
        )

    q_single = [make_query_spec(query_id="q_lin", target_city="Hà Nội", target_poi_ids=["poi-hn-01"])]
    r_lin = [
        make_ranking_row(cell_id="C1-RRF", query_id="q_lin", rank=1, document_id="d_a", score=1.0),
        make_ranking_row(cell_id="C1-RRF", query_id="q_lin", rank=2, document_id="d_b", score=0.9),
    ]
    rk_lin, mf_lin = write_sealed_rankings_bundle(tmp_path / "lin_none", r_lin, cells=["C1-RRF"])
    mf_obj, r_objs = load_sealed_rankings(rk_lin, mf_lin)
    rep_lin = score_g4(
        manifest=mf_obj,
        ranking_rows=r_objs,
        query_specs=q_single,
        qrels={
            ("q_lin", "d_a"): QrelRecord("q_lin", "d_a", RelevanceState.REL_2, 0, ((0, 5),), None),
            ("q_lin", "d_b"): QrelRecord("q_lin", "d_b", RelevanceState.REL_2, 0, ((0, 5),), None),
        },
        docs_by_id={"d_a": {"source_lineage_id": None}, "d_b": {"source_lineage_id": None}},
        enforce_clean_sys_modules=False,
    )
    assert abs(rep_lin["cell_metrics"]["C1-RRF"]["epistemic_lineage_mean_at_10"] - 2.0) < 1e-12
    assert rep_lin["g5_status"] == "HOLD"

    rem_path = tmp_path / "removed.json"
    rem_path.write_text(json.dumps({"d1": [[10, 15]]}), encoding="utf-8")
    docs_j = {
        "d1": {"document_id": "d1", "canonical_text_S": "Hồ Tây Hà Nội mở cửa.", "city": "Hà Nội", "poi_id": "poi-hn-01"},
        "d2": {"document_id": "d2", "canonical_text_S": "Bãi biển Đà Nẵng.", "city": "Đà Nẵng", "poi_id": "poi-dn-01"},
    }
    docs_list_path = tmp_path / "docs_list.json"
    docs_list_path.write_text(json.dumps(list(docs_j.values()), ensure_ascii=False), encoding="utf-8")
    q_j_path = write_jsonl(
        tmp_path / "q_j.jsonl",
        [make_query_dict(query_id="qj1", target_city="Hà Nội", target_poi_ids=["poi-hn-01"])],
    )
    r_j = [
        make_ranking_row(cell_id="C1-RRF", query_id="qj1", rank=1, document_id="d1", score=1.0),
        make_ranking_row(cell_id="C1-BM25", query_id="qj1", rank=1, document_id="d2", score=1.0),
    ]
    rk_j, mf_j = write_sealed_rankings_bundle(tmp_path / "judge_rk", r_j, cells=["C1-RRF", "C1-BM25"])
    judge_a_p = write_jsonl(
        tmp_path / "judge_a.jsonl",
        [
            {
                "query_id": "qj1",
                "document_id": "d1",
                "raw_json_str": json.dumps(
                    {"grade": "REL_2", "evidence_quote": "Hồ Tây Hà", "char_start": 0, "char_end": 9}
                ),
            },
            {"query_id": "qj1", "document_id": "d2", "response_json": {"grade": "REL_0"}},
        ],
    )
    judge_b_p = write_jsonl(
        tmp_path / "judge_b.jsonl",
        [
            {"query_id": "qj1", "document_id": "d1", "grade": "REL_2", "evidence_quote": "Hồ Tây Hà", "char_start": 0, "char_end": 9},
            {"query_id": "qj1", "document_id": "d2", "grade": "REL_0"},
        ],
    )

    rep_single = score_g4_from_files(
        rankings_path=rk_j,
        manifest_path=mf_j,
        queries_path=q_j_path,
        removed_audit_spans_path=rem_path,
        docs_path=docs_list_path,
        judge_a_path=judge_a_p,
        enforce_clean_sys_modules=False,
    )
    assert rep_single["g5_status"] == "HOLD"
    assert rep_single["judge_gates"]["epistemic_tier"] == "AI_PROXY_SINGLE_LLM"

    out_dual = tmp_path / "dual_report.json"
    clean_cli_script = "\n".join(
        [
            "from w07_g4_scorer.scorer import main as scorer_main",
            "rc = scorer_main(",
            "    [",
            f"        '--rankings', {str(rk_j)!r},",
            f"        '--manifest', {str(mf_j)!r},",
            f"        '--queries', {str(q_j_path)!r},",
            f"        '--docs', {str(docs_list_path)!r},",
            f"        '--judge-a', {str(judge_a_p)!r},",
            f"        '--judge-b', {str(judge_b_p)!r},",
            f"        '--output', {str(out_dual)!r},",
            "    ],",
            "    enforce_clean_sys_modules=True,",
            ")",
            "assert rc == 0, f'Expected rc==0, got {rc}'",
        ]
    )
    proc_cli = _run_g4_clean_subprocess(clean_cli_script)
    assert proc_cli.returncode == 0, proc_cli.stdout + proc_cli.stderr
    assert out_dual.is_file()
    rep_dual = json.loads(out_dual.read_text(encoding="utf-8"))
    assert rep_dual["g5_status"] == "HOLD"
    assert rep_dual["judge_gates"]["quadratic_weighted_kappa"] == 1.0
