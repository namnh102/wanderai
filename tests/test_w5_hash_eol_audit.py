"""Tests for Historical W5 Hash & EOL Reproducibility Audit (W5-HASH-AUDIT-01).

Covers all required tests HASH-AUDIT-01 through HASH-AUDIT-10:
- HASH-AUDIT-01: Git blob hash calculation is deterministic.
- HASH-AUDIT-02: working-tree byte hash is independently measured.
- HASH-AUDIT-03: LF normalization behaves deterministically.
- HASH-AUDIT-04: CRLF normalization behaves deterministically.
- HASH-AUDIT-05: canonical JSON hashing is deterministic.
- HASH-AUDIT-06: Round 01 raw files are not modified.
- HASH-AUDIT-07: Round 02 package files are not modified.
- HASH-AUDIT-08: classification is evidence-derived.
- HASH-AUDIT-09: CONTENT_INTEGRITY_FAILURE is not emitted solely due to EOL transformation.
- HASH-AUDIT-10: historical_artifacts_modified == false.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_w5_hash_eol import (  # noqa: E402
    ALLOWED_HASH_CLASSIFICATIONS,
    ALLOWED_IMPACT_CLASSIFICATIONS,
    AUDIT_ID,
    AUDIT_JSON_OUTPUT_PATH,
    BASE_DEVELOP_SHA,
    EXPECTED_ROUND01_RAW_HASHES,
    EXPECTED_ROUND02_CONTROL_HASHES,
    HASHED_ARTIFACT_RELPATHS,
    build_audit_report,
    classify_stored_hash,
    compute_artifact_hash_bases,
    compute_canonical_json_sha256,
    compute_crlf_normalized_sha256,
    compute_git_blob_sha256,
    compute_lf_normalized_sha256,
    compute_working_tree_sha256,
    determine_overall_classification,
    verify_no_historical_artifacts_modified,
)

AUDIT_DOC_PATH = REPO_ROOT / "docs" / "research" / "w5_hash_eol_audit_v1.md"


def _load_audit_json() -> dict[str, Any]:
    assert AUDIT_JSON_OUTPUT_PATH.exists(), f"Missing {AUDIT_JSON_OUTPUT_PATH}"
    return json.loads(AUDIT_JSON_OUTPUT_PATH.read_text(encoding="utf-8"))


def test_hash_audit_01_git_blob_hash_calculation_is_deterministic() -> None:
    """HASH-AUDIT-01: Git blob hash calculation is deterministic and matches git show content SHA256."""
    relpath = "data/evaluation/reca_w5/w5_primary_scenarios_v1.json"
    sha_1 = compute_git_blob_sha256(relpath, ref=BASE_DEVELOP_SHA)
    sha_2 = compute_git_blob_sha256(relpath, ref=BASE_DEVELOP_SHA)
    assert sha_1 == sha_2
    assert sha_1 == "4f0c77dccc2c0bae32f5d87f1364a8e1487a83e9b7344a9d8d3c9d0528bc29fb"

    # Also verify for CRLF-stored Round 01 raw CSV
    r01_rel = "data/evaluation/reca_w5/calibration_submissions/raw_v1/J1_w5_calibration_raw_v1.csv"
    assert compute_git_blob_sha256(r01_rel, ref=BASE_DEVELOP_SHA) == EXPECTED_ROUND01_RAW_HASHES["J1"]


def test_hash_audit_02_working_tree_byte_hash_is_independently_measured(
    tmp_path: Path,
) -> None:
    """HASH-AUDIT-02: Working-tree byte hash is independently measured from local filesystem bytes."""
    lf_file = tmp_path / "sample_lf.txt"
    crlf_file = tmp_path / "sample_crlf.txt"
    lf_bytes = b"line1\nline2\n"
    crlf_bytes = b"line1\r\nline2\r\n"
    lf_file.write_bytes(lf_bytes)
    crlf_file.write_bytes(crlf_bytes)

    wt_lf = compute_working_tree_sha256(lf_file)
    wt_crlf = compute_working_tree_sha256(crlf_file)
    assert wt_lf == hashlib.sha256(lf_bytes).hexdigest()
    assert wt_crlf == hashlib.sha256(crlf_bytes).hexdigest()
    assert wt_lf != wt_crlf


def test_hash_audit_03_lf_normalization_behaves_deterministically() -> None:
    """HASH-AUDIT-03: LF normalization converts CRLF -> LF deterministically and is idempotent on LF."""
    lf_payload = b'{\n  "a": 1,\n  "b": "hello"\n}\n'
    crlf_payload = b'{\r\n  "a": 1,\r\n  "b": "hello"\r\n}\r\n'
    expected = hashlib.sha256(lf_payload).hexdigest()

    assert compute_lf_normalized_sha256(lf_payload) == expected
    assert compute_lf_normalized_sha256(crlf_payload) == expected


def test_hash_audit_04_crlf_normalization_behaves_deterministically() -> None:
    """HASH-AUDIT-04: CRLF normalization converts logical line endings to CRLF deterministically and is idempotent."""
    lf_payload = b'{\n  "a": 1,\n  "b": "hello"\n}\n'
    crlf_payload = b'{\r\n  "a": 1,\r\n  "b": "hello"\r\n}\r\n'
    expected = hashlib.sha256(crlf_payload).hexdigest()

    assert compute_crlf_normalized_sha256(lf_payload) == expected
    assert compute_crlf_normalized_sha256(crlf_payload) == expected

    # Verify historical W5-PREP-01 and W5-PREP-02 CRLF hashes are reproduced from Git LF blobs
    bases_scn = compute_artifact_hash_bases(
        "data/evaluation/reca_w5/w5_primary_scenarios_v1.json", ref=BASE_DEVELOP_SHA
    )["bases"]
    assert (
        bases_scn["CRLF_NORMALIZED_UTF8_SHA256"]
        == "98a86723e7a2d16fbb2acebe1a39379f525a973cc0d854191318931484e9d553"
    )
    bases_cal1 = compute_artifact_hash_bases(
        "data/evaluation/reca_w5/annotation/w5_calibration_v1.json", ref=BASE_DEVELOP_SHA
    )["bases"]
    assert (
        bases_cal1["CRLF_NORMALIZED_UTF8_SHA256"]
        == "740d81e3c3a613575a687af9291102d27e9dd8c61f1fc8f40e913c4c2ccfbc60"
    )


def test_hash_audit_05_canonical_json_hashing_is_deterministic() -> None:
    """HASH-AUDIT-05: Canonical JSON hashing is invariant to key order, indentation, and LF/CRLF line endings."""
    json_a = b'{\n  "z": 1,\n  "a": [\n    "x",\n    "y"\n  ],\n  "vi": "H\xc3\xa0 N\xe1\xbb\x99i"\n}\n'
    json_b = b'{"a":["x","y"],"vi":"H\xc3\xa0 N\xe1\xbb\x99i","z":1}\r\n'

    h_a = compute_canonical_json_sha256(json_a)
    h_b = compute_canonical_json_sha256(json_b)
    assert h_a == h_b


def test_hash_audit_06_round_01_raw_files_are_not_modified() -> None:
    """HASH-AUDIT-06: Round 01 raw CSV submissions and inbox copies are unmodified and match frozen hashes."""
    audit = _load_audit_json()
    r01 = audit["round01_raw_hash_analysis"]
    assert r01["raw_files_modified"] is False
    assert r01["labels_reinterpreted"] is False

    for jid, expected_sha in EXPECTED_ROUND01_RAW_HASHES.items():
        raw_path = (
            REPO_ROOT
            / "data"
            / "evaluation"
            / "reca_w5"
            / "calibration_submissions"
            / "raw_v1"
            / f"{jid}_w5_calibration_raw_v1.csv"
        )
        inbox_path = (
            REPO_ROOT
            / "data"
            / "evaluation"
            / "reca_w5"
            / "calibration_submissions"
            / "inbox"
            / f"w5_calibration_{jid}_completed.csv"
        )
        assert compute_working_tree_sha256(raw_path) == expected_sha
        assert compute_working_tree_sha256(inbox_path) == expected_sha
        j_entry = r01["judges"][jid]
        assert j_entry["matches_git_blob_bytes"] is True
        assert j_entry["matches_working_tree_bytes"] is True
        assert j_entry["matches_crlf_normalized_bytes"] is True
        assert j_entry["matches_lf_normalized_bytes"] is False
        assert j_entry["classification"] == "MATCH_MULTIPLE_EQUIVALENT_BASES"
        assert j_entry["matched_bases"] == [
            "GIT_BLOB_BYTES_SHA256",
            "WORKING_TREE_BYTES_SHA256",
            "CRLF_NORMALIZED_UTF8_SHA256",
        ]


def test_hash_audit_07_round_02_package_files_are_not_modified() -> None:
    """HASH-AUDIT-07: Round 02 canonical and judge package files are unmodified and match control hashes."""
    audit = _load_audit_json()
    r02 = audit["round02_control_analysis"]
    assert r02["round02_historical_content_modified"] is False
    assert r02["all_control_hashes_reproduce_exactly"] is True
    assert r02["control_status"] == "PASS_EXACT_MATCH_ALL_7_CONTROL_ARTIFACTS"

    for key, (relpath, expected_sha) in EXPECTED_ROUND02_CONTROL_HASHES.items():
        full_path = REPO_ROOT / relpath
        assert compute_working_tree_sha256(full_path) == expected_sha
        assert compute_git_blob_sha256(relpath, ref=BASE_DEVELOP_SHA) == expected_sha
        ctrl = r02["control_artifacts"][key]
        assert ctrl["reproduces_exact_under_declared_policy"] is True
        assert ctrl["classification"] == "MATCH_MULTIPLE_EQUIVALENT_BASES"
        assert ctrl["matched_bases"] == [
            "GIT_BLOB_BYTES_SHA256",
            "WORKING_TREE_BYTES_SHA256",
            "LF_NORMALIZED_UTF8_SHA256",
        ]


def test_hash_audit_08_classification_is_evidence_derived() -> None:
    """HASH-AUDIT-08: Stored hash classifications are strictly derived from computed hash bases."""
    sample_bases = {
        "GIT_BLOB_BYTES_SHA256": "aaaa",
        "WORKING_TREE_BYTES_SHA256": "aaaa",
        "LF_NORMALIZED_UTF8_SHA256": "aaaa",
        "CRLF_NORMALIZED_UTF8_SHA256": "bbbb",
        "CANONICAL_JSON_SHA256": "cccc",
    }

    res_multi = classify_stored_hash("aaaa", sample_bases)
    assert res_multi["classification"] == "MATCH_MULTIPLE_EQUIVALENT_BASES"
    assert res_multi["matched_bases"] == [
        "GIT_BLOB_BYTES_SHA256",
        "WORKING_TREE_BYTES_SHA256",
        "LF_NORMALIZED_UTF8_SHA256",
    ]

    res_crlf = classify_stored_hash("bbbb", sample_bases)
    assert res_crlf["classification"] == "MATCH_CRLF_NORMALIZED_BYTES"
    assert res_crlf["matched_bases"] == ["CRLF_NORMALIZED_UTF8_SHA256"]

    res_cjson = classify_stored_hash("cccc", sample_bases)
    assert res_cjson["classification"] == "MATCH_CANONICAL_JSON"
    assert res_cjson["matched_bases"] == ["CANONICAL_JSON_SHA256"]

    res_nomatch = classify_stored_hash("dddd", sample_bases)
    assert res_nomatch["classification"] == "NO_MATCH"
    assert res_nomatch["matched_bases"] == []

    res_na = classify_stored_hash("eeee", sample_bases, is_file_hash=False)
    assert res_na["classification"] == "NOT_APPLICABLE"


def test_hash_audit_09_content_integrity_failure_not_emitted_for_eol_transformation() -> None:
    """HASH-AUDIT-09: CONTENT_INTEGRITY_FAILURE is never emitted solely due to LF vs CRLF differences."""
    synthetic_eol_entries = [
        {
            "source_type": "MANIFEST",
            "classification": "MATCH_CRLF_NORMALIZED_BYTES",
            "difference_category": "REPRESENTATION_ONLY_DIFFERENCE",
        },
        {
            "source_type": "MANIFEST",
            "classification": "MATCH_MULTIPLE_EQUIVALENT_BASES",
            "difference_category": "NO_DIFFERENCE",
        },
    ]
    overall, recommend_amendment = determine_overall_classification(synthetic_eol_entries)
    assert overall != "CONTENT_INTEGRITY_FAILURE"
    assert overall == "HISTORICAL_MANIFEST_INCONSISTENCY"
    assert recommend_amendment is True

    # Conversely, if an actual content difference is present, CONTENT_INTEGRITY_FAILURE is emitted
    synthetic_corrupt_entries = [
        {
            "source_type": "MANIFEST",
            "classification": "NO_MATCH",
            "difference_category": "CONTENT_DIFFERENCE",
            "reconciled_by_lf_manifest_regeneration": False,
        }
    ]
    overall_corrupt, _ = determine_overall_classification(synthetic_corrupt_entries)
    assert overall_corrupt == "CONTENT_INTEGRITY_FAILURE"


def test_hash_audit_10_historical_artifacts_modified_is_false() -> None:
    """HASH-AUDIT-10: historical_artifacts_modified == false and scientific_data_modified == false."""
    assert verify_no_historical_artifacts_modified(ref=BASE_DEVELOP_SHA) is True

    audit = _load_audit_json()
    assert audit["audit_id"] == AUDIT_ID
    assert audit["base_develop_sha"] == BASE_DEVELOP_SHA
    assert audit["historical_artifacts_modified"] is False
    assert audit["scientific_data_modified"] is False
    assert audit["overall_classification"] in ALLOWED_IMPACT_CLASSIFICATIONS
    assert audit["overall_classification"] == "HISTORICAL_MANIFEST_INCONSISTENCY"
    assert audit["formal_amendment_recommended"] is True
    assert audit["root_cause_findings"]["content_difference_found"] is False
    assert audit["root_cause_findings"]["representation_only_difference_found"] is True
    assert audit["root_cause_findings"]["unknown_hash_basis_count"] == 0
    assert len(audit["artifact_results"]) == len(HASHED_ARTIFACT_RELPATHS) == 35

    for entry in audit["stored_hash_classifications"]:
        assert entry["classification"] in ALLOWED_HASH_CLASSIFICATIONS

    # Verify live report matches committed JSON artifact
    live_report = build_audit_report(ref=BASE_DEVELOP_SHA)
    assert live_report == audit

    # Verify Markdown documentation exists and contains key audit conclusions
    assert AUDIT_DOC_PATH.exists()
    doc_text = AUDIT_DOC_PATH.read_text(encoding="utf-8")
    assert "W5-HASH-AUDIT-01" in doc_text
    assert "HISTORICAL_MANIFEST_INCONSISTENCY" in doc_text
    assert "REPRESENTATION_ONLY_DIFFERENCE" in doc_text

    # Verify git diff against BASE_DEVELOP_SHA over all 35 historical hashed artifacts is empty
    res = subprocess.run(
        ["git", "diff", "--name-only", BASE_DEVELOP_SHA, "--", *HASHED_ARTIFACT_RELPATHS],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    changed = sorted(line.strip() for line in res.stdout.splitlines() if line.strip())
    assert changed == [], f"Unexpected modified historical file(s): {changed}"
