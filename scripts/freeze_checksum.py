"""Cross-platform checksum verification for Dataset Freeze V1 (legacy EOL erratum).

Policy (see docs/data/dataset-freeze-v1-eol-erratum.md):

* Raw working-tree bytes are hashed first. A match is a normal PASS.
* On mismatch, ONLY paths explicitly listed in
  data/manifests/dataset-freeze-v1-eol-compat.json may be re-checked against the
  historical CRLF byte representation. Anything else is a FAIL.
* The compat record is NOT part of Freeze V1 and never replaces a frozen hash:
  the historical hash must still be reproduced exactly from reconstructed bytes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PASS = "PASS"
LEGACY_EOL_COMPAT_PASS = "LEGACY_EOL_COMPAT_PASS"
FAIL = "FAIL"
MISSING = "MISSING"

DEFAULT_COMPAT_RELPATH = "data/manifests/dataset-freeze-v1-eol-compat.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def to_crlf(data: bytes) -> bytes:
    """Deterministic LF-canonical -> CRLF reconstruction (idempotent on CRLF input)."""
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def parse_manifest(manifest_path: Path) -> List[Tuple[str, str]]:
    entries = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                sha, rel = line.split("  ", 1)
                entries.append((sha, rel))
    return entries


def load_compat(compat_path: Optional[Path]) -> Dict[str, dict]:
    """Return {path: exception_record}. Missing file => no exceptions."""
    if compat_path is None or not Path(compat_path).exists():
        return {}
    with open(compat_path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    return {e["path"]: e for e in doc.get("exceptions", [])}


def verify_artifact(
    full_path: Path, rel_path: str, expected_sha: str, compat: Dict[str, dict]
) -> Tuple[str, str]:
    """Return (status, detail). Never silently normalises undocumented mismatches."""
    if not full_path.exists():
        return MISSING, f"{rel_path}: file missing"

    raw = full_path.read_bytes()
    actual = sha256_bytes(raw)
    if actual == expected_sha:
        return PASS, f"{rel_path}: raw sha matches"

    exc = compat.get(rel_path)
    if exc is None:
        return FAIL, (
            f"{rel_path}: SHA mismatch (expected {expected_sha}, got {actual}); "
            "no legacy EOL exception documented"
        )

    # The exception record must restate the same historical hash, and be a known form.
    if exc.get("historical_expected_sha256") != expected_sha:
        return FAIL, f"{rel_path}: compat record hash differs from frozen manifest hash"
    if exc.get("historical_eol_form") != "CRLF":
        return FAIL, f"{rel_path}: unsupported historical_eol_form {exc.get('historical_eol_form')!r}"

    reconstructed = sha256_bytes(to_crlf(raw))
    if reconstructed == expected_sha:
        return LEGACY_EOL_COMPAT_PASS, f"{rel_path}: matches historical CRLF bytes"
    return FAIL, (
        f"{rel_path}: content differs even after historical CRLF reconstruction "
        f"(expected {expected_sha}, got {reconstructed})"
    )


def verify_manifest(
    repo_root: Path, manifest_path: Path, compat_path: Optional[Path] = None
) -> List[Tuple[str, str, str]]:
    """Return [(rel_path, status, detail)] for every manifest entry."""
    compat = load_compat(compat_path)
    results = []
    for sha, rel in parse_manifest(manifest_path):
        status, detail = verify_artifact(repo_root / rel, rel, sha, compat)
        results.append((rel, status, detail))
    return results


if __name__ == "__main__":  # pragma: no cover
    root = Path(__file__).resolve().parent.parent
    res = verify_manifest(
        root,
        root / "data/manifests/dataset-freeze-v1.sha256",
        root / DEFAULT_COMPAT_RELPATH,
    )
    for rel, status, detail in res:
        print(f"{status:24s} {rel}")
    raise SystemExit(0 if all(s in (PASS, LEGACY_EOL_COMPAT_PASS) for _, s, _ in res) else 1)
