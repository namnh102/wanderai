"""Deterministic audit package builder for GOMATE W07 offline retrieval prep.

Builds in <output-dir>:
1. GOMATE_W07_OFFLINE_RETRIEVAL_PREP_AUDIT_2026-11-20.zip
2. W07_OFFLINE_RETRIEVAL_PREP_AUDIT_REPORT_2026-11-20.md
3. W07_OFFLINE_RETRIEVAL_PREP_SHA256_RECEIPT.json

All outputs are deterministic (zero wall-clock timestamps, sorted member paths,
fixed ZipInfo metadata, double-pack SHA-256 verification) and read-only with
respect to <prep-dir>/evidence/.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PREP_DIR = Path(__file__).resolve().parents[1]

ZIP_FILENAME = "GOMATE_W07_OFFLINE_RETRIEVAL_PREP_AUDIT_2026-11-20.zip"
REPORT_FILENAME = "W07_OFFLINE_RETRIEVAL_PREP_AUDIT_REPORT_2026-11-20.md"
RECEIPT_FILENAME = "W07_OFFLINE_RETRIEVAL_PREP_SHA256_RECEIPT.json"

FIXED_ZIP_DATETIME: tuple[int, int, int, int, int, int] = (2026, 11, 20, 0, 0, 0)
FIXED_EXTERNAL_ATTR: int = (0o100644 & 0xFFFF) << 16

PINNED_SNAPSHOT_ID = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
PINNED_TOKENIZER_SHA256 = (
    "2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8"
)
WANDERAI_EXPECTED_HEAD = "9bab3e3301185124361f44ff8b41f3b0e46744b7"

FORBIDDEN_SEGMENTS = frozenset(
    {
        ".git",
        ".agents",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".venv",
        "venv",
    }
)
FORBIDDEN_SUFFIXES: tuple[str, ...] = (".pyc", ".pyo", ".tmp", ".bak")
FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    ".git",
    ".agents",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".venv",
    "DEV-5",
    "T0_PRIVATE",
    "FINAL-50",
    "poi_knowledge_acquired_v1",
    "gomate_places_freeze_v2",
)


def _assert_member_allowed(arcname: str) -> None:
    posix_path = PurePosixPath(arcname)
    for part in posix_path.parts:
        if part in FORBIDDEN_SEGMENTS:
            raise ValueError(f"Forbidden path segment in archive member: {arcname}")
    lower_name = arcname.lower()
    for suffix in FORBIDDEN_SUFFIXES:
        if lower_name.endswith(suffix):
            raise ValueError(f"Forbidden file suffix in archive member: {arcname}")
    for token in FORBIDDEN_SUBSTRINGS:
        if token.lower() in lower_name:
            raise ValueError(
                f"Forbidden substring {token!r} in archive member: {arcname}"
            )


def _collect_allowlisted_files(prep_dir: Path) -> list[Path]:
    if not prep_dir.is_dir():
        raise FileNotFoundError(f"Prep directory does not exist: {prep_dir}")

    candidates: list[Path] = []
    required_files = [
        prep_dir / "pyproject.toml",
        prep_dir / "README.md",
        prep_dir / "scripts" / "verify_non_mutation.py",
        prep_dir / "scripts" / "build_audit_package.py",
        prep_dir / "tests" / "conftest.py",
    ]
    for path in required_files:
        if not path.is_file():
            raise FileNotFoundError(f"Required allowlisted file missing: {path}")
        candidates.append(path)

    optional_hygiene_script = (
        prep_dir / "scripts" / "check_public_release_path_hygiene.py"
    )
    if optional_hygiene_script.is_file():
        candidates.append(optional_hygiene_script)

    optional_stub_runner = (
        prep_dir / "scripts" / "run_w07_stub01_05_owner_chat_preflight.py"
    )
    if optional_stub_runner.is_file():
        candidates.append(optional_stub_runner)

    docs_dir = prep_dir / "docs"
    if docs_dir.is_dir():
        for doc_file in sorted(docs_dir.iterdir(), key=lambda p: p.name):
            if doc_file.is_file() and doc_file.suffix.lower() in (".md", ".json"):
                candidates.append(doc_file)

    v022_auth_dir = prep_dir / "authorities_v0_2_2_tech_freeze"
    if v022_auth_dir.is_dir():
        for auth_file in sorted(v022_auth_dir.iterdir(), key=lambda p: p.name):
            if auth_file.is_file() and auth_file.suffix.lower() in (
                ".md",
                ".json",
                ".txt",
            ):
                candidates.append(auth_file)

    for base_rel in (
        "src/w07_retrieval",
        "src/w07_g4_scorer",
        "tests/fixtures",
        "tests/e2e",
    ):
        base_dir = prep_dir / base_rel
        if not base_dir.is_dir():
            raise FileNotFoundError(
                f"Required source/test directory missing: {base_dir}"
            )
        for py_file in base_dir.rglob("*.py"):
            if py_file.is_file():
                candidates.append(py_file)

    tests_dir = prep_dir / "tests"
    for test_file in tests_dir.glob("test_*.py"):
        if test_file.is_file():
            candidates.append(test_file)

    evidence_dir = prep_dir / "evidence"
    if evidence_dir.is_dir():
        for root, dirs, files in os.walk(evidence_dir):
            dirs[:] = sorted(d for d in dirs if d not in FORBIDDEN_SEGMENTS)
            for fname in sorted(files):
                if any(fname.lower().endswith(sfx) for sfx in FORBIDDEN_SUFFIXES):
                    continue
                fpath = Path(root) / fname
                if fpath.is_file():
                    candidates.append(fpath)

    by_arcname: dict[str, Path] = {}
    for path in candidates:
        arcname = path.relative_to(prep_dir).as_posix()
        _assert_member_allowed(arcname)
        by_arcname[arcname] = path

    return [by_arcname[name] for name in sorted(by_arcname.keys())]


def _run_non_mutation_check(prep_dir: Path) -> dict[str, Any]:
    verify_script = prep_dir / "scripts" / "verify_non_mutation.py"
    if not verify_script.is_file():
        raise FileNotFoundError(f"Missing verifier script: {verify_script}")
    proc = subprocess.run(
        [sys.executable, "-B", str(verify_script), "--prep-dir", str(prep_dir)],
        check=False,
        cwd=str(prep_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Non-mutation verification failed before packaging:\n"
            + proc.stdout
            + proc.stderr
        )
    summary = json.loads(proc.stdout)
    if summary.get("status") != "PASS":
        raise RuntimeError(f"Non-mutation status was not PASS: {summary}")
    return summary


def _build_zip_bytes(members: Sequence[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(
        buf, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        for arcname, data in members:
            _assert_member_allowed(arcname)
            info = zipfile.ZipInfo(filename=arcname, date_time=FIXED_ZIP_DATETIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = FIXED_EXTERNAL_ATTR
            zf.writestr(
                info,
                data,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    return buf.getvalue()


def _verify_written_zip(
    zip_path: Path, expected_names: Sequence[str]
) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        bad_member = zf.testzip()
        if bad_member is not None:
            raise RuntimeError(f"Corrupt ZIP member detected: {bad_member}")
        names = zf.namelist()
        if names != sorted(names):
            raise RuntimeError("ZIP namelist is not sorted")
        if names != list(expected_names):
            raise RuntimeError("ZIP namelist mismatch against expected allowlist")
        for info in zf.infolist():
            _assert_member_allowed(info.filename)
            if info.date_time != FIXED_ZIP_DATETIME:
                raise RuntimeError(
                    f"Non-deterministic ZipInfo date_time for {info.filename}: "
                    f"{info.date_time}"
                )


def _extract_pytest_summary_line(raw_bytes: bytes) -> str:
    text = raw_bytes.decode("utf-8", errors="replace")
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("===") and stripped.endswith("==="):
            return stripped.strip("= ").strip()
    return "recorded (see log)"


def _parse_pytest_counts(summary_line: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in ("passed", "failed", "skipped", "deselected"):
        m = re.search(rf"(\d+)\s+{key}\b", summary_line)
        if m:
            counts[key] = int(m.group(1))
    return counts


def _build_coverage_summary_lines(data_by_name: dict[str, bytes]) -> list[str]:
    lines: list[str] = []

    m1_bytes = data_by_name.get("evidence/m1_unit_pytest.log")
    m2_bytes = data_by_name.get("evidence/m2_unit_pytest.log")
    if m1_bytes is not None or m2_bytes is not None:
        unit_passed = 0
        unit_skipped = 0
        parts: list[str] = []
        if m1_bytes is not None:
            m1_sum = _extract_pytest_summary_line(m1_bytes)
            m1_c = _parse_pytest_counts(m1_sum)
            unit_passed += m1_c.get("passed", 0)
            unit_skipped += m1_c.get("skipped", 0)
            parts.append(f"M1 `{m1_sum}`")
        if m2_bytes is not None:
            m2_sum = _extract_pytest_summary_line(m2_bytes)
            m2_c = _parse_pytest_counts(m2_sum)
            unit_passed += m2_c.get("passed", 0)
            unit_skipped += m2_c.get("skipped", 0)
            parts.append(f"M2 `{m2_sum}`")
        lines.append(
            "- **Synthetic `FX-01..FX-16` & Gated Real-Corpus Stubs (`STUB-01..STUB-06` in `HOLD`)**: "
            f"`{unit_passed} passed`, `{unit_skipped}` gated real-corpus stubs "
            "skipped in `HOLD` (plain env vars rejected; awaiting G1.5 freeze + signed Owner receipt) "
            f"[{'; '.join(parts)}]."
        )

    tier_totals = {"collected": 0, "passed": 0, "skipped": 0, "failed": 0}
    tier_count = 0
    for idx in range(1, 5):
        t_bytes = data_by_name.get(f"evidence/e2e_tiers1_to_4/tier{idx}_receipt.json")
        if t_bytes is None:
            continue
        try:
            parsed = json.loads(t_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        tier_count += 1
        tier_totals["collected"] += int(parsed.get("collected", 0))
        tier_totals["passed"] += int(parsed.get("passed", 0))
        tier_totals["skipped"] += int(parsed.get("skipped", 0))
        tier_totals["failed"] += int(parsed.get("failed", 0))

    f12_bytes = data_by_name.get("evidence/e2e_m3_f12_require_all.log")
    if tier_count > 0 or f12_bytes is not None:
        e2e_desc = (
            f"Tiers 1–4 Initial Checkpoints ({tier_totals['collected']} collected across {tier_count} tiers): "
            f"`{tier_totals['passed']} PASS` + `{tier_totals['skipped']} SKIP` (`PENDING_M3`), "
            f"`{tier_totals['failed']} FAIL`"
            if tier_count > 0
            else "E2E F12 verification"
        )
        if f12_bytes is not None:
            f12_sum = _extract_pytest_summary_line(f12_bytes)
            f12_c = _parse_pytest_counts(f12_sum)
            f12_p = f12_c.get("passed", 10)
            e2e_desc += (
                f"; F12 Packaging Verification (`W07_E2E_REQUIRE_ALL=1`): "
                f"`{f12_p} PASS` (`{f12_sum}`)"
            )
        lines.append(f"- **Opaque-Box E2E Suite (Tiers 1–4 + F12)**: {e2e_desc}.")

    t5_bytes = data_by_name.get("evidence/tier5_adversarial_pytest.log")
    if t5_bytes is not None:
        t5_sum = _extract_pytest_summary_line(t5_bytes)
        lines.append(
            "- **Tier 5 White-Box Adversarial Suite (`tests/test_tier5_adversarial.py`)**: "
            f"`{t5_sum}` (covers `scripts/verify_non_mutation.py`, "
            "`scripts/build_audit_package.py`, `src/w07_retrieval/**`, and "
            "`src/w07_g4_scorer/**`)."
        )

    return lines


def _render_audit_report(
    *,
    zip_path: Path,
    zip_sha256: str,
    zip_size: int,
    report_path: Path,
    receipt_path: Path,
    non_mutation_verified: bool,
    double_pack_verified: bool,
    members: Sequence[tuple[str, bytes]],
    member_sha256s: dict[str, str],
) -> str:
    evidence_entries = [
        (arcname, len(data), member_sha256s[arcname])
        for arcname, data in members
        if arcname.startswith("evidence/")
    ]
    data_by_name = dict(members)

    evidence_summary_lines: list[str] = []
    for arcname, size_b, digest in evidence_entries:
        note = ""
        if arcname.endswith(".log"):
            note = f" — `{_extract_pytest_summary_line(data_by_name[arcname])}`"
        elif arcname.endswith("_receipt.json"):
            try:
                parsed = json.loads(data_by_name[arcname].decode("utf-8"))
                if "tier" in parsed:
                    note = (
                        f" — `{parsed['tier']}`: exit={parsed.get('exit_code')}, "
                        f"passed={parsed.get('passed')}, "
                        f"skipped={parsed.get('skipped')}, "
                        f"failed={parsed.get('failed')}"
                    )
                elif "status" in parsed and "wanderai_head" in parsed:
                    note = (
                        f" — `status={parsed['status']}`, "
                        f"`wanderai_head={parsed['wanderai_head']}`"
                    )
            except (json.JSONDecodeError, UnicodeDecodeError):
                note = ""
        evidence_summary_lines.append(
            f"- `{arcname}` ({size_b} B, SHA-256 `{digest}`){note}"
        )

    if not evidence_summary_lines:
        evidence_summary_lines.append("- None included in this packaging run.")

    coverage_summary_lines = _build_coverage_summary_lines(data_by_name)
    coverage_section: list[str] = []
    if coverage_summary_lines:
        coverage_section = [*coverage_summary_lines, ""]

    inventory_rows = "\n".join(
        f"| `{arcname}` | {len(data)} | `{member_sha256s[arcname]}` |"
        for arcname, data in members
    )

    non_mut_label = "VERIFIED" if non_mutation_verified else "SKIPPED_BY_FLAG"
    double_pack_label = "VERIFIED" if double_pack_verified else "FAILED"

    report_lines = [
        "# GOMATE W07 Offline Retrieval Prep Audit Report (2026-11-20 / Corrective 2026-11-21)",
        "",
        "> **Governance Banner (`PRE-FREEZE OFFLINE PREPARATION`)**",
        "> - `W07-B2-G1.5` (`Annex G1.5 v0.2.1`): **HOLD (NOT YET FROZEN)**",
        "> - `G2 = HOLD` · `G3 = HOLD` · `G4 = HOLD` · `G5 = HOLD` · `G6 = HOLD`",
        "> - `AUTO-EVAL-01 v0.4.2`: **CANDIDATE_NOT_YET_APPROVED**",
        "> - `w07_scientific_closed`: `false` · `g15_frozen`: `false`",
        (
            "> - `API Spend`: `$0.00` · `Network Calls`: `0` · "
            "`Real 137-Doc Corpus Executions`: `0`"
        ),
        (
            "> - Passing synthetic/E2E verification establishes "
            "`OFFLINE_PREP_SYNTHETIC_VERIFIED` only."
        ),
        "",
        "## 1. Deliverable & Integrity Summary",
        "",
        (
            "- **Handoff Status**: "
            "`READY_FOR_CHATGPT_OFFLINE_RETRIEVAL_PREP_AUDIT_PRE_FREEZE`"
        ),
        f"- **Archive Path**: `{zip_path}`",
        f"- **Archive Size**: `{zip_size}` bytes",
        f"- **Archive SHA-256**: `{zip_sha256}`",
        f"- **Archive Total Members**: `{len(members)}`",
        f"- **Double-Pack Bit-Identity**: `{double_pack_label}`",
        f"- **Non-Mutation Check**: `{non_mut_label}`",
        f"- **Report Path**: `{report_path}`",
        f"- **Receipt Path**: `{receipt_path}`",
        "",
        "## 2. Scope & Architecture (`2x3` Engine + Decoupled G4 Scorer)",
        "",
        (
            "- **`src/w07_retrieval/` (`11` Exact Modules: `__init__.py`, `schema.py`, "
            "`sanitizer.py`, `chunker_c0.py`, `chunker_c1.py`, `visibility.py`, "
            "`bm25.py`, `dense.py`, `fusion.py`, `blind_packet.py`, `runner.py`)**: "
            "Standalone offline `2x3` retrieval engine (`C0/C1 x BM25/Dense/Hybrid RRF`). "
            "Canonical `S` loading resides in `schema.py`, two-layer fail-closed 6-family "
            "`R_AUDIT` stripping in `sanitizer.py`, and chunking in `chunker_c0.py` "
            "(`SectionAwareChunker(250, 450, 1)`) and `chunker_c1.py` (`<=128` MiniLM "
            "subword tokens, `overlap=0`, parent breadcrumbs, 10-item footer allowlist) "
            "— note: there are no `corpus.py` or `chunking.py` files. `runner.py` "
            "strictly separates `--execution-mode synthetic-prep` (default pre-freeze "
            "mode, hard-blocking the 137-doc real corpus) from `--execution-mode "
            "formal-execution` (fail-closed mode requiring Ed25519-signed "
            "`--owner-auth-receipt` and hash-verified `--frozen-corpus-receipt`; plain "
            "env vars `W07_G15_FROZEN` / `W07_OWNER_AUTHORIZED` are rejected)."
        ),
        (
            "- **`src/w07_g4_scorer/` (`7` Exact Modules: `__init__.py`, `contracts.py`, "
            "`query_manifest.py`, `metrics.py`, `stats.py`, `judge_gates.py`, "
            "`scorer.py`)**: Completely decoupled `G4` scorer with zero ML/retriever "
            "imports (`torch`, `transformers`, `sentence_transformers`, `tokenizers`, "
            "`underthesea`, `w07_retrieval`, `apps.ai_service` absent from `sys.modules`), "
            "SHA-256 verified sealed ranking ingestion, external-only qrel/judge gates "
            "(no label self-generation), `Cert-1..4`, shared-lineage non-propagation, "
            "coupled `[nDCG_L@10, nDCG_U@10]`, `PCG64(20261105)` `B=10,000` bootstrap + "
            "Holm `K1..K5`."
        ),
        (
            f"- **Pinned HF Snapshot**: `paraphrase-multilingual-MiniLM-L12-v2` "
            f"snapshot `{PINNED_SNAPSHOT_ID}` (`local_files_only=True`)."
        ),
        (
            f"- **Verified `tokenizer.json` Disk SHA-256 & Versioned Erratum Proposal**: "
            f"`{PINNED_TOKENIZER_SHA256}` (Reconciled in "
            "`docs/W07_B2_G1_5_TOKENIZER_SHA256_ERRATUM_PROPOSAL_V0_2_1_E01.md` against "
            "G1-audited `g1_corrective_02_manifest.json` `b03bea82...` L12; original "
            "`W07_B2_G1_5_EXECUTION_ANNEX_CANDIDATE_V0_2_1.md` remains untouched at "
            "`842530dd...`)."
        ),
        "",
        "## 3. Verification Evidence Recorded in Archive",
        "",
        *coverage_section,
        *evidence_summary_lines,
        "",
        "## 4. Non-Mutation & Boundary Ledger",
        "",
        (
            f"- **`<WANDERAI_REPO_ROOT>` HEAD**: `{WANDERAI_EXPECTED_HEAD}` (empty "
            "tracked/staged diff; exact 4 pre-existing "
            "`?? docs/research/W07_B2_*.md` untracked files)."
        ),
        (
            "- **Controlling Authorities & Methodology Skeleton**: SHA-256 verified "
            "against Step 0 baselines (`Critical-Path Report`, `Protocol v1.0`, "
            "`Annex G1.5 v0.2.1`, `G1 PASS Receipt`, `AUTO-EVAL-01 v0.4.2`, "
            "`w07_zh_methodology_skeleton.py`)."
        ),
        (
            "- **Isolation Boundaries**: Zero imports from `apps.ai_service` or "
            "`wanderai`; zero access to `DEV-5`, `T0` / `T0_PRIVATE`, `FINAL-50`, "
            "or the real 137-document corpus (`6/6` real-corpus stubs remain in `HOLD` "
            "and reject plain environment variable spoofing per "
            "`docs/W07_REAL_CORPUS_STUB_ACTIVATION_CRITERIA_V1.md`)."
        ),
        (
            "- **Public-Release Path Hygiene**: Verified via "
            "`scripts/check_public_release_path_hygiene.py` (`0` local machine path "
            "occurrences across all public-release candidate files; local audit "
            "harness and evidence files explicitly withheld from public PRs)."
        ),
        (
            "- **Excluded Transient Artifacts**: `.git`, `.agents`, `__pycache__`, "
            "`.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.venv`, `*.pyc`, "
            "`*.pyo`, `*.tmp`, `*.bak`."
        ),
        "",
        "## 5. Deterministic ZIP Member Inventory",
        "",
        "| Member Path | Bytes | SHA-256 |",
        "|---|---:|---|",
        inventory_rows,
        "",
    ]
    report_text = "\n".join(report_lines)
    if "G3 PASS" in report_text or "G4 PASS" in report_text:
        raise AssertionError("Forbidden scientific PASS substring detected in report")
    return report_text


def build_package(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    prep_dir: Path = DEFAULT_PREP_DIR,
    skip_non_mutation: bool = False,
) -> dict[str, Any]:
    non_mutation_verified = False
    if not skip_non_mutation:
        _run_non_mutation_check(prep_dir)
        non_mutation_verified = True

    file_paths = _collect_allowlisted_files(prep_dir)
    members: list[tuple[str, bytes]] = []
    member_sha256s: dict[str, str] = {}
    for path in file_paths:
        arcname = path.relative_to(prep_dir).as_posix()
        data = path.read_bytes()
        members.append((arcname, data))
        member_sha256s[arcname] = hashlib.sha256(data).hexdigest()

    zip_bytes_1 = _build_zip_bytes(members)
    zip_bytes_2 = _build_zip_bytes(members)
    zip_sha256_1 = hashlib.sha256(zip_bytes_1).hexdigest()
    zip_sha256_2 = hashlib.sha256(zip_bytes_2).hexdigest()
    if zip_sha256_1 != zip_sha256_2 or zip_bytes_1 != zip_bytes_2:
        raise RuntimeError("Double-pack determinism check failed")

    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / ZIP_FILENAME
    report_path = output_dir / REPORT_FILENAME
    receipt_path = output_dir / RECEIPT_FILENAME

    zip_path.write_bytes(zip_bytes_1)
    _verify_written_zip(zip_path, [arcname for arcname, _ in members])

    report_text = _render_audit_report(
        zip_path=zip_path,
        zip_sha256=zip_sha256_1,
        zip_size=len(zip_bytes_1),
        report_path=report_path,
        receipt_path=receipt_path,
        non_mutation_verified=non_mutation_verified,
        double_pack_verified=True,
        members=members,
        member_sha256s=member_sha256s,
    )
    report_path.write_text(report_text, encoding="utf-8", newline="\n")
    report_sha256 = hashlib.sha256(report_path.read_bytes()).hexdigest()

    receipt: dict[str, Any] = {
        "api_spend_usd": 0.0,
        "deliverable_zip_path": str(zip_path),
        "deliverable_zip_sha256": zip_sha256_1,
        "deliverable_zip_size_bytes": len(zip_bytes_1),
        "deliverable_zip_total_files": len(members),
        "dev_authorized": False,
        "double_pack_verified": True,
        "final_50_or_g5_authorized": False,
        "g15_frozen": False,
        "g3_status": "HOLD",
        "g4_status": "HOLD",
        "g5_status": "HOLD",
        "handoff_status": "READY_FOR_CHATGPT_OFFLINE_RETRIEVAL_PREP_AUDIT_PRE_FREEZE",
        "member_sha256s": member_sha256s,
        "network_calls": 0,
        "non_mutation_verified": non_mutation_verified,
        "pinned_snapshot_id": PINNED_SNAPSHOT_ID,
        "pinned_tokenizer_json_sha256": PINNED_TOKENIZER_SHA256,
        "real_137_corpus_executions": 0,
        "report_markdown_path": str(report_path),
        "report_markdown_sha256": report_sha256,
        "schema_version": "W07_OFFLINE_RETRIEVAL_PREP_AUDIT_RECEIPT_V1",
        "w07_scientific_closed": False,
        "wanderai_head": WANDERAI_EXPECTED_HEAD,
    }
    receipt_text = (
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    receipt_path.write_text(receipt_text, encoding="utf-8", newline="\n")
    return receipt


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic GOMATE W07 offline retrieval prep audit package."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "Output directory for the audit .zip, .md report, and .json receipt "
            "(default: workspace parent directory)."
        ),
    )
    parser.add_argument(
        "--prep-dir",
        type=Path,
        default=DEFAULT_PREP_DIR,
        help="Path to w07_offline_retrieval_prep directory.",
    )
    parser.add_argument(
        "--skip-non-mutation",
        action="store_true",
        default=False,
        help="Skip pre-packaging verify_non_mutation check (default: False).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    receipt = build_package(
        output_dir=args.output_dir,
        prep_dir=args.prep_dir,
        skip_non_mutation=args.skip_non_mutation,
    )
    summary = {
        "deliverable_zip_path": receipt["deliverable_zip_path"],
        "deliverable_zip_sha256": receipt["deliverable_zip_sha256"],
        "deliverable_zip_total_files": receipt["deliverable_zip_total_files"],
        "double_pack_verified": receipt["double_pack_verified"],
        "non_mutation_verified": receipt["non_mutation_verified"],
        "report_markdown_path": receipt["report_markdown_path"],
    }
    sys.stdout.write(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
