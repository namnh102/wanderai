"""Focused tests for the Freeze V1 legacy-EOL checksum verifier (W3-00-FIX1)."""

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.freeze_checksum import (  # noqa: E402
    FAIL, LEGACY_EOL_COMPAT_PASS, MISSING, PASS, to_crlf, verify_artifact, verify_manifest,
)

# sha256 of data/manifests/dataset-freeze-v1.sha256 at the pre-fix commit (218a5b8).
FREEZE_V1_MANIFEST_SHA256 = "2a1428f3d327cb500824316bfe4d4ee56bb2d73eedd06ecce8779ee410cce9f8"

LF_CONTENT = b'{"a": 1,\n "b": 2}\n'


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _compat(path, expected, form="CRLF"):
    return {path: {
        "path": path,
        "historical_expected_sha256": expected,
        "historical_eol_form": form,
        "canonical_git_eol_form": "LF",
    }}


def test_a_raw_lf_artifact_passes_normally(tmp_path):
    f = tmp_path / "x.json"
    f.write_bytes(LF_CONTENT)
    status, _ = verify_artifact(f, "x.json", _sha(LF_CONTENT), {})
    assert status == PASS


def test_b_documented_historical_crlf_artifact_passes_compat(tmp_path):
    f = tmp_path / "x.json"
    f.write_bytes(LF_CONTENT)  # repo stores LF
    expected = _sha(to_crlf(LF_CONTENT))  # frozen hash came from CRLF bytes
    status, _ = verify_artifact(f, "x.json", expected, _compat("x.json", expected))
    assert status == LEGACY_EOL_COMPAT_PASS
    # a genuine CRLF checkout of the same artifact passes too (raw match)
    f.write_bytes(to_crlf(LF_CONTENT))
    assert verify_artifact(f, "x.json", expected, {})[0] == PASS


def test_c_undocumented_eol_mismatch_fails(tmp_path):
    f = tmp_path / "x.json"
    f.write_bytes(LF_CONTENT)
    expected = _sha(to_crlf(LF_CONTENT))
    status, detail = verify_artifact(f, "x.json", expected, {})
    assert status == FAIL and "no legacy EOL exception" in detail
    # exception documented for a different path does not leak
    status, _ = verify_artifact(f, "x.json", expected, _compat("other.json", expected))
    assert status == FAIL


def test_d_content_mutation_fails(tmp_path):
    f = tmp_path / "x.json"
    expected = _sha(LF_CONTENT)
    f.write_bytes(LF_CONTENT.replace(b"2", b"3"))
    assert verify_artifact(f, "x.json", expected, {})[0] == FAIL


def test_e_compat_mapping_cannot_hide_changed_content(tmp_path):
    f = tmp_path / "x.json"
    expected = _sha(to_crlf(LF_CONTENT))
    compat = _compat("x.json", expected)
    f.write_bytes(LF_CONTENT.replace(b"2", b"3"))  # mutated AND documented path
    assert verify_artifact(f, "x.json", expected, compat)[0] == FAIL
    # compat record that restates a different hash is rejected
    f.write_bytes(LF_CONTENT)
    assert verify_artifact(f, "x.json", expected, _compat("x.json", "0" * 64))[0] == FAIL
    # unknown EOL form is rejected
    assert verify_artifact(f, "x.json", expected, _compat("x.json", expected, "CR"))[0] == FAIL
    assert verify_artifact(tmp_path / "nope", "nope", expected, {})[0] == MISSING


def test_f_freeze_v1_manifest_is_byte_for_byte_unchanged():
    manifest = REPO_ROOT / "data" / "manifests" / "dataset-freeze-v1.sha256"
    assert _sha(manifest.read_bytes()) == FREEZE_V1_MANIFEST_SHA256


def test_compat_record_is_minimal_and_consistent():
    compat_doc = json.loads(
        (REPO_ROOT / "data/manifests/dataset-freeze-v1-eol-compat.json").read_text(encoding="utf-8")
    )
    manifest = REPO_ROOT / "data" / "manifests" / "dataset-freeze-v1.sha256"
    frozen = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.strip():
            sha, rel = line.split("  ", 1)
            frozen[rel] = sha
    for e in compat_doc["exceptions"]:
        assert e["path"] in frozen
        assert e["historical_expected_sha256"] == frozen[e["path"]]
        assert e["historical_eol_form"] == "CRLF" and e["canonical_git_eol_form"] == "LF"
        # must actually need the exception: canonical LF bytes alone must not match
        raw = (REPO_ROOT / e["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert _sha(raw) != e["historical_expected_sha256"], f"{e['path']} does not need exception"


def test_real_freeze_v1_verification_reports_statuses():
    res = verify_manifest(
        REPO_ROOT,
        REPO_ROOT / "data/manifests/dataset-freeze-v1.sha256",
        REPO_ROOT / "data/manifests/dataset-freeze-v1-eol-compat.json",
    )
    statuses = {s for _, s, _ in res}
    assert statuses <= {PASS, LEGACY_EOL_COMPAT_PASS}, [r for r in res if r[1] not in (PASS, LEGACY_EOL_COMPAT_PASS)]


# ---------------------------------------------------------------------------
# W3-00-FIX2: Freeze V2 coverage (V1 and V2 compat records are separate files)
# ---------------------------------------------------------------------------
from scripts.freeze_checksum import (  # noqa: E402
    DEFAULT_COMPAT_RELPATHS, DEFAULT_COMPAT_V2_RELPATH, load_compat,
)

V2_COMPAT = REPO_ROOT / DEFAULT_COMPAT_V2_RELPATH
LOCKED_V2_ARTIFACT_SHA = "93681135d94b379f28802aa75204a0a4c7bec4039f85d28e76ae6737e792e245"
LOCKED_LINEAGE_SHA = "076aeb3804320ba7f0b2f8da846aae3e18d083cf74c10e8c336e448a33464561"

# Canonical (LF) sha256 of the committed bytes, pinned at the pre-FIX2 commit (9861547).
CANONICAL_LF_SHA256 = {
    "data/manifests/dataset-freeze-v1.sha256": FREEZE_V1_MANIFEST_SHA256,
    "data/manifests/dataset-freeze-v2.sha256": "cc9f2e2489418dfd2d7b6066758f7ec72441429f0c64b752e7ada44b3f343e95",
    "data/curated/gomate_places_freeze_v1.json": "2f18aa340bdaf0bab6a43a9d7fdc0e9006882c73a96e86ba8a99a2fa8294174d",
    "data/curated/gomate_places_freeze_v2.json": "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444",
    "data/manifests/freeze-v1-to-v2-place-lineage.json": "c07ab0f2a16217a539cce202f0d5f20b86b39c653e9fa999cd69372d41a34670",
}


def test_v2_documented_legacy_eol_passes_compat(tmp_path):
    f = tmp_path / "v2.json"
    f.write_bytes(LF_CONTENT)
    expected = _sha(to_crlf(LF_CONTENT))
    compat = {"v2.json": {
        "path": "v2.json", "historical_expected_sha256": expected,
        "historical_eol_form": "CRLF", "canonical_repository_eol_form": "LF", "reason": "t",
    }}
    assert verify_artifact(f, "v2.json", expected, compat)[0] == LEGACY_EOL_COMPAT_PASS
    f.write_bytes(LF_CONTENT.replace(b"2", b"9"))
    assert verify_artifact(f, "v2.json", expected, compat)[0] == FAIL


def test_v2_compat_is_separate_minimal_and_consistent():
    doc = json.loads(V2_COMPAT.read_text(encoding="utf-8"))
    v1_paths = set(load_compat(REPO_ROOT / "data/manifests/dataset-freeze-v1-eol-compat.json"))
    frozen = {}
    for line in (REPO_ROOT / "data/manifests/dataset-freeze-v2.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            sha, rel = line.split(None, 1)
            frozen[rel.strip()] = sha
    assert len(doc["exceptions"]) == 9
    for e in doc["exceptions"]:
        assert e["path"] in frozen and e["path"] not in v1_paths  # no duplication of V1
        assert e["historical_expected_sha256"] == frozen[e["path"]]
        assert e["historical_eol_form"] == "CRLF" and e["canonical_repository_eol_form"] == "LF"
        assert e["reason"]
        raw = (REPO_ROOT / e["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert _sha(raw) != e["historical_expected_sha256"], f"{e['path']} does not need exception"


def test_v2_locked_artifacts_reproduce_authoritative_hashes():
    compat = load_compat([REPO_ROOT / p for p in DEFAULT_COMPAT_RELPATHS])
    for rel, locked in (
        ("data/curated/gomate_places_freeze_v2.json", LOCKED_V2_ARTIFACT_SHA),
        ("data/manifests/freeze-v1-to-v2-place-lineage.json", LOCKED_LINEAGE_SHA),
    ):
        status, detail = verify_artifact(REPO_ROOT / rel, rel, locked, compat)
        assert status in (PASS, LEGACY_EOL_COMPAT_PASS), detail
        # and a one-byte content change must not be hidden
        mutated = tmp_bytes = (REPO_ROOT / rel).read_bytes()
        assert _sha(to_crlf(mutated)) == locked
        assert _sha(to_crlf(mutated + b" ")) != locked


def test_v1_v2_frozen_artifacts_and_manifests_unchanged():
    for rel, pinned in CANONICAL_LF_SHA256.items():
        raw = (REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
        assert _sha(raw) == pinned, f"{rel} changed"
