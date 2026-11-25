"""Pre-freeze non-mutation & boundary hygiene verifier for GOMATE W07.

Verifies that:
1. <WANDERAI_REPO_ROOT> remains at exact Step 0 git HEAD with empty tracked diffs
   and only the 4 pre-existing untracked docs/research/W07_B2_*.md files.
2. Controlling authority documents and w07_zh_methodology_skeleton.py match
   their Step 0 SHA-256 digests.
3. No FINAL-50 artifacts exist at top-level <WORKSPACE_PARENT> or inside <prep-dir>.
4. <prep-dir>/src/**/*.py contains zero imports from apps.ai_service or wanderai
   and zero references to T0_PRIVATE, DEV-5, poi_knowledge_acquired_v1.jsonl,
   or gomate_places_freeze_v2.json.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

WANDERAI_EXPECTED_HEAD = "9bab3e3301185124361f44ff8b41f3b0e46744b7"
_PREP_PARENT = Path(__file__).resolve().parents[2]
DEFAULT_WANDERAI_DIR = (
    _PREP_PARENT if (_PREP_PARENT / "apps" / "ai-service").is_dir() else (_PREP_PARENT / "wanderai")
)
DEFAULT_PREP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DO_AN_DIR = DEFAULT_WANDERAI_DIR.parent
DEFAULT_CRITICAL_PATH_REPORT = (
    DEFAULT_DO_AN_DIR / "W07_SCIENTIFIC_CRITICAL_PATH_REVIEW_REPORT_2026-11-20.md"
)

CRITICAL_PATH_REPORT_SHA256 = (
    "1d460ecbf67d538ed5ec94083c2d35381e2296a7a3682af6f2e961c287c2c939"
)
PROTOCOL_V1_SHA256 = (
    "5056c5c2373ee9584b8850ba49411160cc2c382ad6315aaada4c05fb9b0030c2"
)
ANNEX_G15_SHA256 = (
    "842530dd737e2b2371280a4091ca760e540ec783d6ae654d462e33e148075740"
)
G1_PASS_RECEIPT_SHA256 = (
    "97c194ba35d154b3e8fa551553bf3990859bbf9635ab8987f60713e5ef383b99"
)
AUTO_EVAL_SHA256 = (
    "c33b69881cc98efbaa851c341efb6c9a35c2a9c29f868418a99988305cb2c7ae"
)
SKELETON_SHA256 = (
    "8514189f20d4ddffefcaad2b767b42391e8e47c970689ff0bf090686dc96da6a"
)
ANNEX_V022_TECH_FREEZE_SHA256 = (
    "e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940"
)
TECH_FREEZE_OWNER_DECISION_SHA256 = (
    "ee6b7bdb6354f51f6da784adeeceb7418d17bb2c63acfcf59f37d9c7a38bcff3"
)
TECH_FREEZE_OWNER_RECEIPT_SHA256 = (
    "1db438d30ad042296fca38abd882de0d1951d4dc1ff83c31b86a41d5765b6937"
)
DEFAULT_V022_ARCHIVE_DIRS: tuple[Path, ...] = (
    DEFAULT_DO_AN_DIR / "W07_G15_OWNER_APPROVED_TECH_FREEZE_ARCHIVE_2026-11-21",
    DEFAULT_PREP_DIR / "authorities_v0_2_2_tech_freeze",
)

DEFAULT_ANNEX_CANDIDATE_COPIES: tuple[Path, ...] = (
    DEFAULT_DO_AN_DIR
    / "W07_B2_G1_5_ANNEX_CORRECTIVE_02"
    / "00_deliverables_v0_2_1"
    / "W07_B2_G1_5_EXECUTION_ANNEX_CANDIDATE_V0_2_1.md",
)
DEFAULT_G1_RECEIPT_PATH = (
    DEFAULT_DO_AN_DIR
    / "W07_B2_G1_5_ANNEX_CORRECTIVE_02"
    / "01_controlling_authorities_and_audit_receipts"
    / "GOMATE_W07_B2_G1_INDEPENDENT_SCIENTIFIC_PASS_RECEIPT_2026-11-12.md"
)
DEFAULT_AUTO_EVAL_PATH = (
    DEFAULT_DO_AN_DIR
    / "W07_AUTO_EVAL_01_AUTOMATED_EVALUATION_CONTRACT_AND_OWNER_DECISION_PACK_V0_4_2.md"
)
DEFAULT_SKELETON_COPIES: tuple[Path, ...] = (
    DEFAULT_DO_AN_DIR
    / "W07_OWNER_DEV5_RUN_20261119"
    / "07_readonly_frozen_and_audited_baselines"
    / "w07_zh_methodology_skeleton.py",
    DEFAULT_DO_AN_DIR
    / "W07_REP01_20261119"
    / "07_readonly_frozen_and_audited_baselines"
    / "w07_zh_methodology_skeleton.py",
)

EXPECTED_AUTHORITY_DIR_FILES: dict[str, str] = {
    "W07_SCIENTIFIC_CRITICAL_PATH_REVIEW_REPORT_2026-11-20.md": (
        CRITICAL_PATH_REPORT_SHA256
    ),
    "W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md": (
        PROTOCOL_V1_SHA256
    ),
    "W07_B2_G1_5_EXECUTION_ANNEX_CANDIDATE_V0_2_1.md": ANNEX_G15_SHA256,
    "GOMATE_W07_B2_G1_INDEPENDENT_SCIENTIFIC_PASS_RECEIPT_2026-11-12.md": (
        G1_PASS_RECEIPT_SHA256
    ),
    (
        "W07_AUTO_EVAL_01_AUTOMATED_EVALUATION_CONTRACT_"
        "AND_OWNER_DECISION_PACK_V0_4_2.md"
    ): AUTO_EVAL_SHA256,
}

EXPECTED_WANDERAI_PORCELAIN_LINES: tuple[str, ...] = (
    "?? docs/research/W07_B2_G1_5_ANTY_READONLY_SOURCE_HANDOFF_TASK_2026-11-05.md",
    "?? docs/research/W07_B2_G1_5_PREFREEZE_REVIEW_REGISTER_2026-11-05.md",
    "?? docs/research/W07_B2_G1_READONLY_PREFLIGHT_ANTY_TASK_2026-11-04.md",
    "?? docs/research/W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md",
)

FORBIDDEN_SRC_IMPORTS: tuple[str, ...] = ("apps.ai_service", "wanderai")
FORBIDDEN_SRC_REFERENCES: tuple[str, ...] = (
    "T0_PRIVATE",
    "DEV-5",
    "poi_knowledge_acquired_v1.jsonl",
    "gomate_places_freeze_v2.json",
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _verify_file_sha256(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not path.is_file():
        return {
            "path": str(path),
            "expected_sha256": expected_sha256,
            "actual_sha256": None,
            "ok": False,
            "error": "missing_or_not_file",
        }
    actual = _sha256_file(path)
    ok = actual == expected_sha256
    result: dict[str, Any] = {
        "path": str(path),
        "expected_sha256": expected_sha256,
        "actual_sha256": actual,
        "ok": ok,
    }
    if not ok:
        result["error"] = "sha256_mismatch"
    return result


def _run_git(wanderai_dir: Path, git_args: Sequence[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", "-C", str(wanderai_dir), *git_args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _check_wanderai_git(wanderai_dir: Path) -> dict[str, Any]:
    if not wanderai_dir.is_dir():
        return {
            "ok": False,
            "wanderai_dir": str(wanderai_dir),
            "head": "",
            "expected_head": WANDERAI_EXPECTED_HEAD,
            "error": "missing_wanderai_dir",
        }

    rc_head, out_head, err_head = _run_git(wanderai_dir, ["rev-parse", "HEAD"])
    actual_head = out_head.strip()
    head_ok = rc_head == 0 and actual_head == WANDERAI_EXPECTED_HEAD

    rc_diff, out_diff, err_diff = _run_git(wanderai_dir, ["diff", "--name-only"])
    diff_files = sorted(
        line.strip() for line in out_diff.splitlines() if line.strip()
    )
    diff_ok = rc_diff == 0 and len(diff_files) == 0

    rc_cached, out_cached, err_cached = _run_git(
        wanderai_dir, ["diff", "--cached", "--name-only"]
    )
    cached_files = sorted(
        line.strip() for line in out_cached.splitlines() if line.strip()
    )
    cached_ok = rc_cached == 0 and len(cached_files) == 0

    rc_status, out_status, err_status = _run_git(
        wanderai_dir, ["status", "--porcelain=v1", "-uall"]
    )
    status_lines = sorted(
        line.rstrip("\r") for line in out_status.splitlines() if line.strip()
    )
    expected_lines = sorted(EXPECTED_WANDERAI_PORCELAIN_LINES)
    status_ok = rc_status == 0 and status_lines == expected_lines

    ok = head_ok and diff_ok and cached_ok and status_ok
    result: dict[str, Any] = {
        "ok": ok,
        "wanderai_dir": str(wanderai_dir),
        "head": actual_head,
        "expected_head": WANDERAI_EXPECTED_HEAD,
        "head_ok": head_ok,
        "diff_files": diff_files,
        "diff_ok": diff_ok,
        "cached_diff_files": cached_files,
        "cached_diff_ok": cached_ok,
        "status_lines": status_lines,
        "expected_status_lines": expected_lines,
        "status_ok": status_ok,
    }
    git_errors = [
        err.strip()
        for err in (err_head, err_diff, err_cached, err_status)
        if err.strip()
    ]
    if git_errors:
        result["git_stderr"] = git_errors
    return result


def _check_authority_dir(authority_dir: Path) -> dict[str, Any]:
    if not authority_dir.is_dir():
        return {
            "ok": False,
            "authority_dir": str(authority_dir),
            "error": "missing_authority_dir",
            "files": [],
            "unexpected_files": [],
        }

    entries = sorted(authority_dir.iterdir(), key=lambda p: p.name)
    actual_names = [p.name for p in entries]
    expected_names = sorted(EXPECTED_AUTHORITY_DIR_FILES.keys())
    unexpected = [
        p.name for p in entries if p.name not in EXPECTED_AUTHORITY_DIR_FILES
    ]
    missing = [
        name for name in expected_names if name not in actual_names
    ]

    file_checks: list[dict[str, Any]] = []
    for name in expected_names:
        file_checks.append(
            _verify_file_sha256(
                authority_dir / name, EXPECTED_AUTHORITY_DIR_FILES[name]
            )
        )

    ok = (
        len(unexpected) == 0
        and len(missing) == 0
        and all(item["ok"] for item in file_checks)
    )
    return {
        "ok": ok,
        "authority_dir": str(authority_dir),
        "missing_files": missing,
        "unexpected_files": unexpected,
        "files": file_checks,
    }


def _check_final50_absence(do_an_dir: Path, prep_dir: Path) -> dict[str, Any]:
    hits: list[str] = []
    if do_an_dir.is_dir():
        with os.scandir(do_an_dir) as it:
            for entry in sorted(it, key=lambda e: e.name):
                if "final-50" in entry.name.lower() or "final_50" in entry.name.lower():
                    hits.append(str(Path(do_an_dir) / entry.name))
    else:
        return {
            "ok": False,
            "error": "missing_do_an_dir",
            "top_level_dir": str(do_an_dir),
            "hits": hits,
        }

    if prep_dir.is_dir():
        for root, dirs, files in os.walk(prep_dir):
            dirs[:] = sorted(d for d in dirs if d != ".git")
            for name in sorted(dirs) + sorted(files):
                if "final-50" in name.lower() or "final_50" in name.lower():
                    hits.append(str(Path(root) / name))

    return {
        "ok": len(hits) == 0,
        "top_level_dir": str(do_an_dir),
        "prep_dir": str(prep_dir),
        "hits": sorted(hits),
    }


def _check_src_hygiene(prep_dir: Path) -> dict[str, Any]:
    src_dir = prep_dir / "src"
    if not src_dir.is_dir():
        return {
            "ok": False,
            "src_dir": str(src_dir),
            "error": "missing_src_dir",
            "violations": ["missing_src_dir"],
            "scanned_files": 0,
        }

    py_files = sorted(src_dir.rglob("*.py"), key=lambda p: p.as_posix())
    violations: list[dict[str, Any]] = []

    for py_path in py_files:
        rel = py_path.relative_to(prep_dir).as_posix()
        text = py_path.read_text(encoding="utf-8")

        for ref in FORBIDDEN_SRC_REFERENCES:
            if ref in text:
                violations.append(
                    {"file": rel, "type": "forbidden_reference", "detail": ref}
                )

        tree = ast.parse(text, filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in FORBIDDEN_SRC_IMPORTS:
                        if alias.name == prefix or alias.name.startswith(prefix + "."):
                            violations.append(
                                {
                                    "file": rel,
                                    "type": "forbidden_import",
                                    "detail": alias.name,
                                    "line": node.lineno,
                                }
                            )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for prefix in FORBIDDEN_SRC_IMPORTS:
                    if node.module == prefix or node.module.startswith(prefix + "."):
                        violations.append(
                            {
                                "file": rel,
                                "type": "forbidden_import_from",
                                "detail": node.module,
                                "line": node.lineno,
                            }
                        )

    return {
        "ok": len(violations) == 0,
        "src_dir": str(src_dir),
        "scanned_files": len(py_files),
        "violations": violations,
    }


def run_verification(
    *,
    wanderai_dir: Path = DEFAULT_WANDERAI_DIR,
    critical_path_report: Path = DEFAULT_CRITICAL_PATH_REPORT,
    authority_dir: Path | None = None,
    skeleton_path: Path | None = None,
    prep_dir: Path = DEFAULT_PREP_DIR,
    do_an_dir: Path = DEFAULT_DO_AN_DIR,
) -> dict[str, Any]:
    git_check = _check_wanderai_git(wanderai_dir)

    authority_checks: list[dict[str, Any]] = [
        _verify_file_sha256(critical_path_report, CRITICAL_PATH_REPORT_SHA256),
        _verify_file_sha256(
            DEFAULT_WANDERAI_DIR
            / "docs"
            / "research"
            / "W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md",
            PROTOCOL_V1_SHA256,
        ),
        _verify_file_sha256(DEFAULT_G1_RECEIPT_PATH, G1_PASS_RECEIPT_SHA256),
        _verify_file_sha256(DEFAULT_AUTO_EVAL_PATH, AUTO_EVAL_SHA256),
    ]
    for annex_copy in DEFAULT_ANNEX_CANDIDATE_COPIES:
        authority_checks.append(_verify_file_sha256(annex_copy, ANNEX_G15_SHA256))
    for v022_dir in DEFAULT_V022_ARCHIVE_DIRS:
        if v022_dir.is_dir():
            authority_checks.append(
                _verify_file_sha256(
                    v022_dir
                    / "GOMATE_W07_G15_TECHNICAL_ANNEX_V0_2_2_CANDIDATE_2026-11-21.md",
                    ANNEX_V022_TECH_FREEZE_SHA256,
                )
            )
            authority_checks.append(
                _verify_file_sha256(
                    v022_dir
                    / "GOMATE_W07_G15_TECH_FREEZE_OWNER_DECISION_2026-11-21.md",
                    TECH_FREEZE_OWNER_DECISION_SHA256,
                )
            )
            authority_checks.append(
                _verify_file_sha256(
                    v022_dir
                    / "GOMATE_W07_G15_TECH_FREEZE_OWNER_APPROVAL_RECEIPT_2026-11-21.json",
                    TECH_FREEZE_OWNER_RECEIPT_SHA256,
                )
            )

    authority_dir_check: dict[str, Any] | None = None
    if authority_dir is not None:
        authority_dir_check = _check_authority_dir(authority_dir)

    skeleton_targets: Sequence[Path] = (
        (skeleton_path,) if skeleton_path is not None else DEFAULT_SKELETON_COPIES
    )
    skeleton_checks = [
        _verify_file_sha256(target, SKELETON_SHA256) for target in skeleton_targets
    ]

    final50_check = _check_final50_absence(do_an_dir, prep_dir)
    src_hygiene_check = _check_src_hygiene(prep_dir)

    all_ok = (
        git_check["ok"]
        and all(item["ok"] for item in authority_checks)
        and (authority_dir_check is None or authority_dir_check["ok"])
        and all(item["ok"] for item in skeleton_checks)
        and final50_check["ok"]
        and src_hygiene_check["ok"]
    )

    checks_payload: dict[str, Any] = {
        "authorities": authority_checks,
        "final50_absence": final50_check,
        "skeleton_copies": skeleton_checks,
        "src_hygiene": src_hygiene_check,
        "wanderai_git": git_check,
    }
    if authority_dir_check is not None:
        checks_payload["authority_dir"] = authority_dir_check

    return {
        "checks": checks_payload,
        "status": "PASS" if all_ok else "FAIL",
        "wanderai_head": git_check.get("head", ""),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify GOMATE W07 pre-freeze non-mutation and boundary hygiene."
    )
    parser.add_argument(
        "--wanderai-dir",
        type=Path,
        default=DEFAULT_WANDERAI_DIR,
        help="Path to <WANDERAI_REPO_ROOT> git repository.",
    )
    parser.add_argument(
        "--critical-path-report",
        type=Path,
        default=DEFAULT_CRITICAL_PATH_REPORT,
        help="Path to W07_SCIENTIFIC_CRITICAL_PATH_REVIEW_REPORT_2026-11-20.md.",
    )
    parser.add_argument(
        "--authority-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory override containing the 5 expected authority .md files."
        ),
    )
    parser.add_argument(
        "--skeleton-path",
        type=Path,
        default=None,
        help="Optional override path for w07_zh_methodology_skeleton.py.",
    )
    parser.add_argument(
        "--prep-dir",
        type=Path,
        default=DEFAULT_PREP_DIR,
        help="Path to w07_offline_retrieval_prep repository.",
    )
    parser.add_argument(
        "--output",
        "--json-out",
        dest="json_out",
        type=Path,
        default=None,
        help="Optional output path for deterministic JSON receipt.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    summary = run_verification(
        wanderai_dir=args.wanderai_dir,
        critical_path_report=args.critical_path_report,
        authority_dir=args.authority_dir,
        skeleton_path=args.skeleton_path,
        prep_dir=args.prep_dir,
    )
    payload = json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    sys.stdout.write(payload)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload, encoding="utf-8", newline="\n")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
