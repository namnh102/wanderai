"""Contract and forensic boundary tests for W5-HASH-ERRATUM-01."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERRATUM_JSON_PATH = (
    ROOT / "data" / "evaluation" / "reca_w5" / "audits" / "w5_hash_basis_erratum_v1.json"
)
ERRATUM_MD_PATH = ROOT / "docs" / "research" / "w5_hash_basis_erratum_v1.md"
AUDIT_JSON_PATH = (
    ROOT / "data" / "evaluation" / "reca_w5" / "audits" / "w5_hash_eol_audit_v1.json"
)
PREREG_MANIFEST_PATH = (
    ROOT / "data" / "evaluation" / "reca_w5" / "rec_eval_01_prereg_manifest_v1.json"
)
REPRO_MANIFEST_PATH = (
    ROOT / "data" / "evaluation" / "reca_w5" / "w5_reproducibility_manifest_v1.json"
)
ANNOTATION_MANIFEST_PATH = (
    ROOT
    / "data"
    / "evaluation"
    / "reca_w5"
    / "annotation"
    / "w5_annotation_manifest_v1.json"
)
ROUND01_MANIFEST_PATH = (
    ROOT
    / "data"
    / "evaluation"
    / "reca_w5"
    / "calibration_submissions"
    / "w5_calibration_raw_manifest_v1.json"
)
ROUND01_INCIDENT_PATH = (
    ROOT
    / "data"
    / "evaluation"
    / "reca_w5"
    / "calibration_submissions"
    / "w5_calibration_round_01_integrity_incident_v1.json"
)
ROUND02_MANIFEST_PATH = (
    ROOT
    / "data"
    / "evaluation"
    / "reca_w5"
    / "calibration_round02_ops"
    / "w5_calibration_round02_manifest_v1.json"
)

EXPECTED_ROUND01_J1_SHA256 = (
    "7a3b58f20169c98a7b472952e480afb96d34e58613afa0032a58d540062393ba"
)
EXPECTED_ROUND01_J2_SHA256 = (
    "b8464c133df5757cd4c1e741a21a5b2392544a175dc2ec32e5d1e6a4d2721707"
)
EXPECTED_ROUND01_J3_SHA256 = (
    "b2094cafb458f0ebdea1dd28ec4d5ef723062e449c3b51602edaaee00a86ba3f"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_hash_erratum_01_erratum_id_and_status() -> None:
    """HASH-ERRATUM-01: erratum_id/status correct."""
    assert ERRATUM_JSON_PATH.is_file()
    assert ERRATUM_MD_PATH.is_file()
    erratum = _load_json(ERRATUM_JSON_PATH)
    assert erratum["erratum_id"] == "W5-HASH-ERRATUM-01"
    assert erratum["status"] == "ACTIVE"
    assert erratum["source_audit_id"] == "W5-HASH-AUDIT-01"
    assert (
        erratum["source_audit_base_sha"]
        == "1c7e43b39f4009e9620181d0c0c5a8151788abb7"
    )


def test_hash_erratum_02_source_audit_classification_matches_official_audit() -> None:
    """HASH-ERRATUM-02: source audit classification matches official audit."""
    erratum = _load_json(ERRATUM_JSON_PATH)
    audit = _load_json(AUDIT_JSON_PATH)
    assert erratum["classification"] == "HISTORICAL_MANIFEST_INCONSISTENCY"
    assert erratum["classification"] == audit["overall_classification"]
    assert erratum["hashed_artifact_count"] == 35
    assert erratum["stored_hash_reference_count"] == 83
    assert (
        erratum["hashed_artifact_count"]
        == audit["audit_scope"]["hashed_artifact_count"]
    )
    assert (
        erratum["stored_hash_reference_count"]
        == audit["audit_scope"]["stored_hash_reference_count"]
    )
    assert erratum["content_integrity_failure"] is False
    assert erratum["content_difference_found"] is False
    assert erratum["representation_only_difference_found"] is True
    assert erratum["unknown_hash_basis_count"] == 0


def test_hash_erratum_03_historical_hashes_rewritten_is_false() -> None:
    """HASH-ERRATUM-03: historical_hashes_rewritten == false."""
    erratum = _load_json(ERRATUM_JSON_PATH)
    assert erratum["historical_hashes_rewritten"] is False
    legacy = erratum["legacy_pre_prereg_manifests"]
    assert legacy["historical_hash_values_preserved_unchanged"] is True
    assert legacy["evidence_of_content_corruption"] is False
    assert legacy["reproduces_by_lf_to_crlf_normalization"] is True
    assert (
        legacy["must_not_be_treated_as_canonical_committed_git_blob_hashes"] is True
    )
    assert legacy["action"] == "DO_NOT_REWRITE"


def test_hash_erratum_04_preregistration_modified_is_false() -> None:
    """HASH-ERRATUM-04: preregistration_modified == false."""
    erratum = _load_json(ERRATUM_JSON_PATH)
    assert erratum["preregistration_modified"] is False
    assert (
        erratum["authoritative_preregistration"]["preregistration_modified"] is False
    )


def test_hash_erratum_05_scientific_data_modified_is_false() -> None:
    """HASH-ERRATUM-05: scientific_data_modified == false."""
    erratum = _load_json(ERRATUM_JSON_PATH)
    assert erratum["scientific_data_modified"] is False


def test_hash_erratum_06_scientific_result_impact_is_none() -> None:
    """HASH-ERRATUM-06: scientific_result_impact == NONE."""
    erratum = _load_json(ERRATUM_JSON_PATH)
    assert erratum["scientific_result_impact"] == "NONE"


def test_hash_erratum_07_authoritative_basis_is_committed_git_blob() -> None:
    """HASH-ERRATUM-07: authoritative basis == sha256_git_committed_blob_content."""
    erratum = _load_json(ERRATUM_JSON_PATH)
    prereg = _load_json(PREREG_MANIFEST_PATH)
    assert (
        erratum["authoritative_w5_hash_basis"]
        == "sha256_git_committed_blob_content"
    )
    assert (
        erratum["authoritative_preregistration"]["declared_hash_basis"]
        == "sha256_git_committed_blob_content"
    )
    assert prereg["artifact_hash_basis"] == "sha256_git_committed_blob_content"


def test_hash_erratum_08_legacy_manifests_byte_and_hash_unchanged() -> None:
    """HASH-ERRATUM-08: legacy manifests still byte/hash unchanged."""
    erratum = _load_json(ERRATUM_JSON_PATH)
    prereg = _load_json(PREREG_MANIFEST_PATH)

    repro_bytes = REPRO_MANIFEST_PATH.read_bytes()
    ann_bytes = ANNOTATION_MANIFEST_PATH.read_bytes()
    repro_sha = _sha256_bytes(repro_bytes)
    ann_sha = _sha256_bytes(ann_bytes)

    assert (
        repro_sha
        == prereg["artifact_hashes"]["w5_reproducibility_manifest_v1.json"]["sha256"]
    )
    assert (
        ann_sha
        == prereg["artifact_hashes"]["w5_annotation_manifest_v1.json"]["sha256"]
    )
    assert (
        repro_sha
        == erratum["legacy_pre_prereg_manifests"]["manifests"][
            "w5_reproducibility_manifest_v1.json"
        ]["committed_git_blob_sha256"]
    )
    assert (
        ann_sha
        == erratum["legacy_pre_prereg_manifests"]["manifests"][
            "w5_annotation_manifest_v1.json"
        ]["committed_git_blob_sha256"]
    )

    index = erratum["legacy_to_canonical_resolution_index"]
    assert index["total_mapped_fields"] == 19
    assert len(index["entries"]) == 19
    for entry in index["entries"]:
        target_path = ROOT / entry["target_artifact"]
        raw_lf = target_path.read_bytes()
        assert _sha256_bytes(raw_lf) == entry["canonical_committed_git_blob_lf_sha256"]
        raw_crlf = raw_lf.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        assert _sha256_bytes(raw_crlf) == entry["historical_stored_crlf_sha256"]
        assert entry["reproduces_via_lf_to_crlf_normalization"] is True


def test_hash_erratum_09_authoritative_prereg_manifest_unchanged() -> None:
    """HASH-ERRATUM-09: authoritative prereg manifest unchanged."""
    erratum = _load_json(ERRATUM_JSON_PATH)
    prereg = _load_json(PREREG_MANIFEST_PATH)
    assert len(prereg["artifact_hashes"]) == 14
    for key, item in prereg["artifact_hashes"].items():
        path = ROOT / item["path"]
        assert _sha256_bytes(path.read_bytes()) == item["sha256"], f"Mismatch on {key}"
        assert (
            erratum["authoritative_preregistration"]["artifact_hashes"][key]["sha256"]
            == item["sha256"]
        )


def test_hash_erratum_10_round01_j1_j2_j3_authoritative_hashes() -> None:
    """HASH-ERRATUM-10: Round01 J1/J2/J3 authoritative hashes match exact frozen bytes."""
    erratum = _load_json(ERRATUM_JSON_PATH)
    r1_manifest = _load_json(ROUND01_MANIFEST_PATH)
    r1_policy = erratum["round01_raw_forensic_hash_policy"]

    assert r1_policy["hash_basis"] == "RAW_RECEIVED_FILE_BYTES_SHA256"
    j_hashes = r1_policy["authoritative_raw_csv_sha256"]
    assert j_hashes["J1"]["sha256"] == EXPECTED_ROUND01_J1_SHA256
    assert j_hashes["J2"]["sha256"] == EXPECTED_ROUND01_J2_SHA256
    assert j_hashes["J3"]["sha256"] == EXPECTED_ROUND01_J3_SHA256

    for judge_id, expected_sha in (
        ("J1", EXPECTED_ROUND01_J1_SHA256),
        ("J2", EXPECTED_ROUND01_J2_SHA256),
        ("J3", EXPECTED_ROUND01_J3_SHA256),
    ):
        assert r1_manifest["judge_records"][judge_id]["sha256"] == expected_sha
        raw_v1_path = ROOT / j_hashes[judge_id]["raw_v1_path"]
        inbox_path = ROOT / j_hashes[judge_id]["inbox_path"]
        assert _sha256_bytes(raw_v1_path.read_bytes()) == expected_sha
        assert _sha256_bytes(inbox_path.read_bytes()) == expected_sha


def test_hash_erratum_11_round01_remains_invalidated_for_protocol() -> None:
    """HASH-ERRATUM-11: Round01 remains INVALIDATED_FOR_PROTOCOL."""
    erratum = _load_json(ERRATUM_JSON_PATH)
    r1_manifest = _load_json(ROUND01_MANIFEST_PATH)
    r1_incident = _load_json(ROUND01_INCIDENT_PATH)
    r1_policy = erratum["round01_raw_forensic_hash_policy"]

    assert r1_policy["file_integrity_status"] == "PASS"
    assert r1_policy["scientific_qualification_status"] == "FAIL"
    assert r1_policy["round_status"] == "INVALIDATED_FOR_PROTOCOL"
    assert r1_policy["scientific_use"] == "FORENSIC_NON_QUALIFYING_EVIDENCE_ONLY"
    assert r1_policy["qualifying_independent_human_judgments"] == 0
    assert r1_policy["calibration_review_eligible"] is False
    assert r1_policy["human_gt"] is False

    assert r1_manifest["round_status"] == "INVALIDATED_FOR_PROTOCOL"
    assert r1_manifest["qualifying_independent_human_judgments"] == 0
    assert r1_incident["round_status"] == "INVALIDATED_FOR_PROTOCOL"
    assert r1_incident["scientific_use"] == "FORENSIC_NON_QUALIFYING_EVIDENCE_ONLY"


def test_hash_erratum_12_round02_hashes_remain_unchanged() -> None:
    """HASH-ERRATUM-12: Round02 hashes remain unchanged."""
    erratum = _load_json(ERRATUM_JSON_PATH)
    r2_manifest = _load_json(ROUND02_MANIFEST_PATH)
    r2_policy = erratum["round02_hash_policy"]

    assert r2_policy["round_status"] == "PREPARED_NOT_STARTED"
    assert (
        r2_policy["primary_hash_basis"]
        == "COMMITTED_GIT_BLOB_UTF8_LF_NORMALIZED_SHA256"
    )
    assert (
        r2_policy["secondary_json_hash_basis"]
        == "CANONICAL_SORTED_COMPACT_JSON_UTF8_SHA256"
    )
    assert r2_policy["round02_hashes_unchanged"] is True
    assert r2_policy["round02_packages_regenerated"] is False
    assert r2_policy["actual_human_judgments_collected"] == 0
    assert r2_policy["human_gt"] is False
    assert r2_policy["primary_annotation_started"] is False
    assert r2_policy["recommender_evaluation_performed"] is False

    assert r2_manifest["status"] == "PREPARED_NOT_STARTED"
    for key, art in r2_manifest["artifacts"].items():
        p = ROOT / art["path"]
        assert _sha256_bytes(p.read_bytes()) == art["canonical_lf_sha256"], (
            f"Round02 mismatch {key}"
        )
    for judge_id, pkg in r2_manifest["judge_packages"].items():
        jp = ROOT / pkg["json_path"]
        cp = ROOT / pkg["csv_path"]
        assert _sha256_bytes(jp.read_bytes()) == pkg["json_canonical_lf_sha256"], (
            judge_id
        )
        assert _sha256_bytes(cp.read_bytes()) == pkg["csv_canonical_lf_sha256"], (
            judge_id
        )


def test_hash_erratum_13_no_historical_artifact_modified_by_branch() -> None:
    """HASH-ERRATUM-13: no historical artifact is modified by this PR."""
    audit = _load_json(AUDIT_JSON_PATH)
    historical_paths = list(audit["artifact_results"].keys())
    assert len(historical_paths) == 35
    for rel_path, entry in audit["artifact_results"].items():
        actual_sha = _sha256_bytes((ROOT / rel_path).read_bytes())
        assert actual_sha == entry["bases"]["GIT_BLOB_BYTES_SHA256"], (
            f"Historical artifact modified: {rel_path}"
        )

    base_sha = "8f7db565e9ea70085a505745fd78326b49c1e243"
    has_commit = subprocess.run(
        ["git", "cat-file", "-e", f"{base_sha}^{{commit}}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if has_commit.returncode != 0:
        subprocess.run(
            ["git", "fetch", "origin", base_sha, "--depth=1"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    diff_out = subprocess.check_output(
        [
            "git",
            "diff",
            "--name-only",
            base_sha,
            "--",
            *historical_paths,
        ],
        cwd=ROOT,
        text=True,
    ).splitlines()
    modified_historical = [line.strip() for line in diff_out if line.strip()]
    assert modified_historical == [], (
        f"Historical artifacts modified: {modified_historical}"
    )

    assert b"\r\n" not in ERRATUM_JSON_PATH.read_bytes()
    assert b"\r\n" not in ERRATUM_MD_PATH.read_bytes()
    assert b"\r\n" not in Path(__file__).read_bytes()
