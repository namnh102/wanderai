"""Targeted regression tests for GOMATE W07 Offline Retrieval Prep Corrective 01.

Covers all 5 corrective requirements on Python 3.11:
1. Strict separation of `synthetic-prep` vs `formal-execution` in `w07_retrieval.runner`,
   fail-closed receipt & Ed25519 verification, and rejection of plain environment variable spoofing.
2. Versioned erratum proposal `v0.2.1-E01` for `tokenizer.json` SHA-256 in Candidate Annex G1.5 v0.2.1
   with zero mutation to the original authority document.
3. All 6 real-corpus stubs (`STUB-01..STUB-06`) kept in `HOLD` (`SKIPPED`) even under env-var spoofing,
   with complete post-G1.5 activation criteria.
4. Normalized module filenames (`schema.py`, `sanitizer.py`, `chunker_c0.py`, `chunker_c1.py`) and
   exact E2E count disclosure (`154 PASS + 10 SKIP` in Tiers 1-4 and `10 PASS` in F12) in audit report.
5. Pre-publication local machine path hygiene (`scripts/check_public_release_path_hygiene.py`).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from conftest import PINNED_SNAPSHOT_ID, PINNED_TOKENIZER_SHA256, is_real_corpus_authorized
from test_real_corpus_gated_stubs import REAL_CORPUS_STUB_ACTIVATION_CRITERIA_V1
from w07_retrieval.runner import (
    FROZEN_CORPUS_RECEIPT_SCHEMA_V1,
    OWNER_AUTH_RECEIPT_SCHEMA_V1,
    PINNED_LIVE_OWNER_G3_PUBKEY_HEX,
    VALID_EXECUTION_MODES,
    run_benchmark,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, rel_path: str) -> Any:
    script_path = REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, str(script_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_c01_item1_runner_mode_separation_cli_and_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify synthetic-prep vs formal-execution separation and fail-closed CLI behavior."""
    assert VALID_EXECUTION_MODES == ("synthetic-prep", "formal-execution")
    assert PINNED_LIVE_OWNER_G3_PUBKEY_HEX is None

    c_path = tmp_path / "syn_corpus.jsonl"
    q_path = tmp_path / "syn_queries.jsonl"
    c_path.write_text(
        json.dumps(
            {
                "document_id": "syn-1",
                "title": "Bảo tàng Dân tộc học",
                "language": "vi",
                "canonical_text_S": "Bảo tàng Dân tộc học Việt Nam mở cửa từ 8h30 đến 17h30.",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    q_path.write_text(
        json.dumps(
            {"query_id": "q-1", "query_text": "Bảo tàng Dân tộc học mở cửa mấy giờ"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    # 1. Synthetic-prep succeeds on synthetic BM25 cell and stamps manifest
    out_syn = tmp_path / "out_syn"
    res = run_benchmark(
        corpus_path=c_path,
        queries_path=q_path,
        output_dir=out_syn,
        cells=["C1-BM25"],
        execution_mode="synthetic-prep",
    )
    assert res["execution_mode"] == "synthetic-prep"
    assert res["scientific_authority_status"] == "SYNTHETIC_PREP_ONLY_NOT_G3_PASS"
    assert res["formal_g15_frozen_verified"] is False
    assert res["owner_authorization_verified"] is False
    manifest = json.loads(
        (out_syn / "g3_sealed_rankings_v1_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["execution_mode"] == "synthetic-prep"
    assert manifest["scientific_authority_status"] == "SYNTHETIC_PREP_ONLY_NOT_G3_PASS"

    # 2. CLI --execution-mode formal-execution fails closed even when env vars are set
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["W07_G15_FROZEN"] = "1"
    env["W07_OWNER_AUTHORIZED"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "w07_retrieval.runner",
            "--execution-mode",
            "formal-execution",
            "--corpus",
            str(c_path),
            "--queries",
            str(q_path),
            "--output-dir",
            str(tmp_path / "out_formal_fail"),
            "--cells",
            "C1-BM25",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert proc.returncode != 0
    assert "FORMAL_EXECUTION_BLOCKED_MISSING_RECEIPTS" in (proc.stdout + proc.stderr)
    assert "environment flags cannot simulate Owner authority" in (
        proc.stdout + proc.stderr
    )


def test_c01_item2_versioned_tokenizer_erratum_proposal_and_snapshot_match(
    snapshot_dir: Path,
) -> None:
    """Verify versioned erratum v0.2.1-E01 matches on-disk snapshot and preserves original authority."""
    erratum_md = (
        REPO_ROOT
        / "docs"
        / "W07_B2_G1_5_TOKENIZER_SHA256_ERRATUM_PROPOSAL_V0_2_1_E01.md"
    )
    erratum_json = (
        REPO_ROOT
        / "docs"
        / "w07_b2_g1_5_tokenizer_sha256_erratum_v0_2_1_e01.json"
    )
    assert erratum_md.is_file()
    assert erratum_json.is_file()

    payload = json.loads(erratum_json.read_text(encoding="utf-8"))
    assert payload["erratum_id"] == "W07-B2-G15-ERRATUM-V0.2.1-E01"
    assert payload["original_authority_modified"] is False
    assert (
        payload["original_authority_sha256"]
        == "842530dd737e2b2371280a4091ca760e540ec783d6ae654d462e33e148075740"
    )
    assert payload["snapshot_id"] == PINNED_SNAPSHOT_ID
    assert (
        payload["verified_actual_tokenizer_json_sha256"] == PINNED_TOKENIZER_SHA256
    )

    tok_path = snapshot_dir / "tokenizer.json"
    assert tok_path.stat().st_size == payload["verified_actual_tokenizer_json_bytes"]
    assert (
        hashlib.sha256(tok_path.read_bytes()).hexdigest()
        == payload["verified_actual_tokenizer_json_sha256"]
    )
    assert OWNER_AUTH_RECEIPT_SCHEMA_V1 == "W07_G15_OWNER_EXECUTION_AUTHORIZATION_RECEIPT_V1"
    assert FROZEN_CORPUS_RECEIPT_SCHEMA_V1 == "W07_FROZEN_137_CORPUS_RECEIPT_V1"


def test_c01_item3_all_six_real_corpus_stubs_remain_hold_under_env_spoof() -> None:
    """Verify all 6 real-corpus stubs (5 in M1 + 1 in M2) stay SKIPPED even when env vars are '1'."""
    criteria_md = REPO_ROOT / "docs" / "W07_REAL_CORPUS_STUB_ACTIVATION_CRITERIA_V1.md"
    assert criteria_md.is_file()
    md_text = criteria_md.read_text(encoding="utf-8")
    for stub_id in REAL_CORPUS_STUB_ACTIVATION_CRITERIA_V1:
        assert stub_id in md_text

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT / "src"), str(REPO_ROOT / "tests")]
    )
    env["W07_G15_FROZEN"] = "1"
    env["W07_OWNER_AUTHORIZED"] = "1"

    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-rs",
            "-k",
            "test_gated_real_",
            str(REPO_ROOT / "tests" / "test_real_corpus_gated_stubs.py"),
            str(
                REPO_ROOT
                / "tests"
                / "test_fx12_to_fx16_g4_scorer.py::test_gated_real_137_corpus_g4_scorer_stub"
            ),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "6 skipped" in proc.stdout
    assert "failed" not in proc.stdout.lower()
    assert is_real_corpus_authorized() is False


def test_c01_item4_report_filename_normalization_and_e2e_counts() -> None:
    """Verify build_audit_package report lists exact module names and 154 PASS + 10 SKIP / 10 PASS F12."""
    bap = _load_script("build_audit_package_c01", "scripts/build_audit_package.py")
    data_by_name = {
        "evidence/m1_unit_pytest.log": b"=== 48 passed, 5 skipped in 10.0s ===\n",
        "evidence/m2_unit_pytest.log": b"=== 15 passed, 1 skipped in 2.0s ===\n",
        "evidence/e2e_tiers1_to_4/tier1_receipt.json": json.dumps(
            {"tier": "tier1", "collected": 60, "passed": 55, "skipped": 5, "failed": 0, "exit_code": 0}
        ).encode("utf-8"),
        "evidence/e2e_tiers1_to_4/tier2_receipt.json": json.dumps(
            {"tier": "tier2", "collected": 83, "passed": 78, "skipped": 5, "failed": 0, "exit_code": 0}
        ).encode("utf-8"),
        "evidence/e2e_tiers1_to_4/tier3_receipt.json": json.dumps(
            {"tier": "tier3", "collected": 14, "passed": 14, "skipped": 0, "failed": 0, "exit_code": 0}
        ).encode("utf-8"),
        "evidence/e2e_tiers1_to_4/tier4_receipt.json": json.dumps(
            {"tier": "tier4", "collected": 7, "passed": 7, "skipped": 0, "failed": 0, "exit_code": 0}
        ).encode("utf-8"),
        "evidence/e2e_m3_f12_require_all.log": b"=== 10 passed, 133 deselected in 6.79s ===\n",
        "evidence/tier5_adversarial_pytest.log": b"=== 24 passed in 33.19s ===\n",
    }
    members = [(k, v) for k, v in sorted(data_by_name.items())]
    shas = {k: hashlib.sha256(v).hexdigest() for k, v in members}
    rendered = bap._render_audit_report(
        zip_path=Path("audit.zip"),
        zip_sha256="a" * 64,
        zip_size=1234,
        report_path=Path("report.md"),
        receipt_path=Path("receipt.json"),
        non_mutation_verified=True,
        double_pack_verified=True,
        members=members,
        member_sha256s=shas,
    )
    for exact_mod in (
        "schema.py",
        "sanitizer.py",
        "chunker_c0.py",
        "chunker_c1.py",
        "visibility.py",
        "bm25.py",
        "dense.py",
        "fusion.py",
        "blind_packet.py",
        "runner.py",
        "contracts.py",
        "query_manifest.py",
        "metrics.py",
        "stats.py",
        "judge_gates.py",
        "scorer.py",
    ):
        assert exact_mod in rendered
    assert "no `corpus.py` or `chunking.py` files" in rendered
    assert "`154 PASS` + `10 SKIP` (`PENDING_M3`), `0 FAIL`" in rendered
    assert "F12 Packaging Verification (`W07_E2E_REQUIRE_ALL=1`): `10 PASS`" in rendered


def test_c01_item5_public_release_path_hygiene_scanner() -> None:
    """Verify check_public_release_path_hygiene passes on public candidates and flags local paths."""
    hygiene = _load_script(
        "check_public_release_path_hygiene_c01",
        "scripts/check_public_release_path_hygiene.py",
    )
    report = hygiene.check_prep_dir_path_hygiene(REPO_ROOT, strict_all=False)
    assert report["status"] == "PASS", f"Violations: {report['public_candidate_violations']}"
    assert report["public_candidate_clean"] is True
    assert report["public_candidate_violations"] == []
    assert report["public_candidate_file_count"] >= 30

    # Verify positive detection of Windows user profile and local drive paths
    sample_local_user = "C:" + "\\Users\\alice\\project"
    sample_local_drive = "D:" + "\\Do_an\\workspace"
    hits_user = hygiene.scan_text_for_local_machine_paths(sample_local_user)
    hits_drive = hygiene.scan_text_for_local_machine_paths(sample_local_drive)
    assert len(hits_user) == 1 and hits_user[0]["rule"] == "SECRET_OR_PERSONAL_PATH_RE"
    assert len(hits_drive) == 1 and hits_drive[0]["rule"] == "LOCAL_DRIVE_DO_AN_RE"
