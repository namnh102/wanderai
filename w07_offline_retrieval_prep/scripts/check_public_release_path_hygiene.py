"""Pre-publication local machine path & denylist hygiene checker for GOMATE W07.

Enforces the exact personal-path, secret, and local-drive regexes from
`scripts/check_w07_public_release_denylist.py` on `develop@880ce7763c3006aaf59eff8ad2e2ebd9688ca371`
before any public release or PR proposal:
1. All public-release candidate files (`pyproject.toml`, `README.md`, `src/w07_retrieval/**`,
   `src/w07_g4_scorer/**`, `docs/**`, `tests/conftest.py`, `tests/fixtures/**`, and unit tests
   `tests/test_fx*.py`, `tests/test_auto_eval_guardrails.py`, `tests/test_real_corpus_gated_stubs.py`,
   plus this script) MUST have ZERO matches (`violations == []`).
2. Local-only audit harness & execution evidence files (`evidence/**`,
   `scripts/verify_non_mutation.py`, `scripts/build_audit_package.py`, `tests/e2e/**`,
   `tests/test_tier5_adversarial.py`) are explicitly classified as
   `LOCAL_AUDIT_HARNESS_WITHHELD_FROM_PUBLIC_PR` and blocked if `--strict-all` is set.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DEFAULT_PREP_DIR = Path(__file__).resolve().parents[1]

SECRET_OR_PERSONAL_PATH_RE = re.compile(
    r"(?i)"
    r"([A-Za-z]:[\\/]+Users[\\/]+)"
    r"|(file:///[A-Za-z]:/Users/)"
    r"|(\.gemini[\\/]+antigravity[\\/]+brain)"
    r"|(sk-ant-[A-Za-z0-9_-]{8,})"
    r"|(sk-proj-[A-Za-z0-9_-]{8,})"
    r"|(AIzaSy[A-Za-z0-9_-]{10,})"
    r"|(BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY)"
)
LOCAL_DRIVE_DO_AN_RE = re.compile(r"(?i)[A-Za-z]:[\\/]+do_an\b")

LOCAL_ONLY_HARNESS_PREFIXES: tuple[str, ...] = (
    "authorities_v0_2_2_tech_freeze/",
    "evidence/",
    "tests/e2e/",
)
LOCAL_ONLY_HARNESS_EXACT: frozenset[str] = frozenset(
    {
        "scripts/verify_non_mutation.py",
        "scripts/build_audit_package.py",
        "tests/test_tier5_adversarial.py",
    }
)


def is_local_only_harness_path(rel_posix: str) -> bool:
    """Return True if rel_posix is a local-only offline audit harness or evidence file."""
    if rel_posix in LOCAL_ONLY_HARNESS_EXACT:
        return True
    return any(rel_posix.startswith(pfx) for pfx in LOCAL_ONLY_HARNESS_PREFIXES)


def scan_text_for_local_machine_paths(text: str) -> list[dict[str, Any]]:
    """Scan text line-by-line for personal profile paths, secrets, or local drive paths."""
    hits: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        m_personal = SECRET_OR_PERSONAL_PATH_RE.search(line)
        if m_personal is not None:
            hits.append(
                {
                    "line": line_no,
                    "rule": "SECRET_OR_PERSONAL_PATH_RE",
                    "matched": m_personal.group(0),
                }
            )
        m_drive = LOCAL_DRIVE_DO_AN_RE.search(line)
        if m_drive is not None:
            hits.append(
                {
                    "line": line_no,
                    "rule": "LOCAL_DRIVE_DO_AN_RE",
                    "matched": m_drive.group(0),
                }
            )
    return hits


def check_prep_dir_path_hygiene(
    prep_dir: Path = DEFAULT_PREP_DIR,
    *,
    strict_all: bool = False,
) -> dict[str, Any]:
    """Audit prep_dir for local machine path hygiene prior to any public release proposal."""
    if not prep_dir.is_dir():
        raise FileNotFoundError(f"Prep directory not found: {prep_dir}")

    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from build_audit_package import _collect_allowlisted_files

    allowlisted_paths = _collect_allowlisted_files(prep_dir)
    public_candidate_files: list[str] = []
    public_candidate_violations: list[dict[str, Any]] = []
    withheld_local_harness_files: list[dict[str, Any]] = []

    for fpath in allowlisted_paths:
        rel_posix = fpath.relative_to(prep_dir).as_posix()
        text = fpath.read_text(encoding="utf-8", errors="replace")
        file_hits = scan_text_for_local_machine_paths(text)

        if is_local_only_harness_path(rel_posix) and not strict_all:
            withheld_local_harness_files.append(
                {
                    "file": rel_posix,
                    "disposition": "LOCAL_AUDIT_HARNESS_WITHHELD_FROM_PUBLIC_PR",
                    "local_path_occurrence_count": len(file_hits),
                }
            )
        else:
            public_candidate_files.append(rel_posix)
            if file_hits:
                public_candidate_violations.append(
                    {
                        "file": rel_posix,
                        "hits": file_hits,
                    }
                )

    ok = len(public_candidate_violations) == 0
    return {
        "status": "PASS" if ok else "FAIL",
        "public_candidate_clean": ok,
        "public_candidate_file_count": len(public_candidate_files),
        "public_candidate_files": public_candidate_files,
        "public_candidate_violations": public_candidate_violations,
        "withheld_local_harness_file_count": len(withheld_local_harness_files),
        "withheld_local_harness_files": withheld_local_harness_files,
        "strict_all": strict_all,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify local machine path hygiene before any W07 public release proposal."
    )
    parser.add_argument(
        "--prep-dir",
        type=Path,
        default=DEFAULT_PREP_DIR,
        help="Path to w07_offline_retrieval_prep directory.",
    )
    parser.add_argument(
        "--strict-all",
        action="store_true",
        default=False,
        help="Fail if even local-only harness/evidence files exist with local machine paths.",
    )
    args = parser.parse_args(argv)

    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    report = check_prep_dir_path_hygiene(
        prep_dir=args.prep_dir,
        strict_all=args.strict_all,
    )
    sys.stdout.write(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
