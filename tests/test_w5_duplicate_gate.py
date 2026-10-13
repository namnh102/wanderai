"""Tests for W5 Duplicate Equivalence Evidence and Evaluation Impact Gate (W5-GATE-DUP-01).

Validates DUP-01 to DUP-18 specifications and hardened evidence claims:
- DUP-01: Historical candidate groups recovered from repository evidence.
- DUP-01A: Historical map parsed via AST from commit exactly equals evidence group mapping.
- DUP-01B: Exactly 3 historical candidate groups and 6 unique place IDs.
- DUP-02: Evidence artifact version and status valid.
- DUP-03: Each candidate pair has exactly one classification.
- DUP-04: Active duplicate map contains only CONFIRMED_EQUIVALENT groups.
- DUP-05: No AMBIGUOUS pair enters active map.
- DUP-06: No NOT_CONFIRMED pair enters active map.
- DUP-07: All mapped place_ids exist in Freeze V2.
- DUP-08: Mapped pair members share the documented destination.
- DUP-09: Primary intersection is recomputed from frozen 474 pool.
- DUP-10: Reported intersection count equals computed count.
- DUP-11: Affected scenario list equals computed scenarios.
- DUP-12: No frozen candidate pool bytes changed.
- DUP-13: No primary scenario bytes changed.
- DUP-14: No Freeze V2 bytes changed.
- DUP-15: Human judgments remain zero.
- DUP-16: No recommender code modified.
- DUP-17: Branch decision: intersection 0 -> PASS & CLOSED_NO_PRIMARY_EVAL_IMPACT.
- DUP-18: No duplicate-aware metric scoring is activated.
- DUP-EVIDENCE-01: Stored DN-01 website strings differ; no claim of identical URLs or web resolution.
- DUP-EVIDENCE-02: Documented normalized names match exact evidence artifact values.
- DUP-CLAIM-01: Documentation contains scoped known-group conclusion.
- DUP-CLAIM-02: Documentation does not claim global duplicate-free catalog or uncorrupted evaluation.
- DUP-CONTROL-01: Documentation reports control non-selection descriptively, not causally attributed to I1.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent

EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "reca_w5"
EVIDENCE_PATH = EVAL_DIR / "w5_duplicate_equivalence_evidence_v1.json"
MAP_PATH = EVAL_DIR / "w5_duplicate_equivalence_map_v1.json"
GATE_RESULT_PATH = EVAL_DIR / "w5_duplicate_gate_result_v1.json"
GATE_DOC_PATH = REPO_ROOT / "docs" / "research" / "w5_duplicate_gate_v1.md"

FREEZE_V2_PATH = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
INTERNAL_POOL_PATH = EVAL_DIR / "w5_candidate_pool_internal_v1.json"
BLINDED_POOL_PATH = EVAL_DIR / "w5_candidate_pool_blinded_v1.json"
PRIMARY_SCENARIOS_PATH = EVAL_DIR / "w5_primary_scenarios_v1.json"
PREREG_MANIFEST_PATH = EVAL_DIR / "rec_eval_01_prereg_manifest_v1.json"

EXPECTED_FREEZE_V2_SHA256 = "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444"
EXPECTED_INTERNAL_POOL_SHA256 = "32b25ef8ffc19d671513f771d3d3a0d23ceb9d0cf614ace1eded94d8c84126c6"
EXPECTED_BLINDED_POOL_SHA256 = "8f178e06b1b93e59b3a53f1b2bf1b6ecc697ccfa610d56783b613b6aa2f06ec7"
EXPECTED_PRIMARY_SCENARIOS_SHA256 = "4f0c77dccc2c0bae32f5d87f1364a8e1487a83e9b7344a9d8d3c9d0528bc29fb"

BASE_DEVELOP_COMMIT = "a2e132dd9383ae7c9f6ea535972903d603831064"
HISTORICAL_COMMIT = "0edcf343cdeef72aa980417d5f628cd79de4ca74"


def _ensure_commit(commit_sha: str) -> None:
    """Ensure commit is available locally; shallow-fetches from origin in CI if missing."""
    res = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if res.returncode != 0:
        subprocess.run(
            ["git", "fetch", "origin", commit_sha, "--depth=1"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )


def _sha256_bytes(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> Any:
    assert path.exists(), f"File not found: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_dup_01_historical_candidate_recovery() -> None:
    """DUP-01: Historical candidate groups are recovered from repository evidence."""
    # Ensure historical commit is available in local git repository
    _ensure_commit(HISTORICAL_COMMIT)

    res = subprocess.run(
        ["git", "show", f"{HISTORICAL_COMMIT}:scripts/build_w5_eval_pool.py"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        check=True,
    )
    assert "REC_A_CORE_DUPLICATE_MAP" in res.stdout
    assert "DUP-CORE-DN-01" in res.stdout
    assert "DUP-CORE-DN-02" in res.stdout
    assert "DUP-CORE-HL-01" in res.stdout

    # Verify audit documentation also references the Đà Nẵng duplicate core pairs
    audit_doc = REPO_ROOT / "docs" / "w3" / "w3-03-place-data-gap-audit.md"
    assert audit_doc.exists()
    audit_text = audit_doc.read_text(encoding="utf-8")
    assert "6db09251-706a-4225-8ee5-4d22165f6b3f" in audit_text
    assert "408aaa5a-7e34-41eb-b39f-acfa4393fc5f" in audit_text
    assert "098e6a53-5ce5-4d20-b75e-4a00d00bb8cf" in audit_text
    assert "83d8e5c4-b91e-415e-9fd6-fd2a887cb4c0" in audit_text

    # Current builder script must NOT have hardcoded duplicate mappings
    builder_source = (REPO_ROOT / "scripts" / "build_w5_eval_pool.py").read_text(encoding="utf-8")
    assert "REC_A_CORE_DUPLICATE_MAP" not in builder_source
    assert "DUP-CORE-DN-01" not in builder_source
    assert "DUP-CORE-HL-01" not in builder_source


def test_dup_01a_historical_map_parsed_exact_equality() -> None:
    """DUP-01A: Historical map parsed via AST from commit exactly equals evidence group mapping."""
    _ensure_commit(HISTORICAL_COMMIT)

    res = subprocess.run(
        ["git", "show", f"{HISTORICAL_COMMIT}:scripts/build_w5_eval_pool.py"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        check=True,
    )

    tree = ast.parse(res.stdout)
    historical_map = None
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "REC_A_CORE_DUPLICATE_MAP":
                    historical_map = ast.literal_eval(stmt.value)
                    break

    assert isinstance(historical_map, dict), "Failed to AST-parse REC_A_CORE_DUPLICATE_MAP"

    historical_group_map: Dict[str, Set[str]] = {}
    for pid, gid in historical_map.items():
        historical_group_map.setdefault(gid, set()).add(pid)

    ev = _load_json(EVIDENCE_PATH)
    evidence_group_map = {g["candidate_group_id"]: set(g["place_ids"]) for g in ev["groups"]}

    assert historical_group_map == evidence_group_map, (
        f"Historical parsed groups {historical_group_map} != evidence groups {evidence_group_map}"
    )


def test_dup_01b_group_and_place_counts() -> None:
    """DUP-01B: Exactly 3 historical candidate groups and 6 unique place IDs."""
    ev = _load_json(EVIDENCE_PATH)
    mp = _load_json(MAP_PATH)

    ev_pids = {pid for g in ev["groups"] for pid in g["place_ids"]}
    mp_pids = {pid for g in mp["groups"] for pid in g["place_ids"]}

    assert len(ev["groups"]) == 3
    assert len(ev_pids) == 6
    assert len(mp["groups"]) == 3
    assert len(mp_pids) == 6


def test_dup_02_evidence_artifact_validity() -> None:
    """DUP-02: Evidence artifact version and status valid."""
    ev = _load_json(EVIDENCE_PATH)
    assert ev["artifact_version"] == "W5-DUP-EVIDENCE-V1"
    assert ev["status"] == "EVIDENCE_REVIEWED"
    assert ev["source_freeze"] == "REC-A-CORE-V2"
    assert ev["source_develop_commit"] == "a2e132dd9383ae7c9f6ea535972903d603831064"
    assert ev["candidate_pair_origin"] == "HISTORICAL_REPOSITORY_EVIDENCE"
    assert ev["new_pair_discovery_performed"] is False
    assert ev["human_relevance_labels_used"] is False
    assert ev["web_evidence_used"] is False
    assert ev["freeze_v2_canonical_sha256"] == EXPECTED_FREEZE_V2_SHA256
    assert ev["candidate_pool_internal_canonical_sha256"] == EXPECTED_INTERNAL_POOL_SHA256
    assert isinstance(ev["groups"], list)
    assert len(ev["groups"]) == 3


def test_dup_03_classification_cardinality() -> None:
    """DUP-03: Each candidate pair has exactly one classification."""
    ev = _load_json(EVIDENCE_PATH)
    valid_classifications = {"CONFIRMED_EQUIVALENT", "AMBIGUOUS", "NOT_CONFIRMED"}
    for g in ev["groups"]:
        assert "classification" in g
        assert g["classification"] in valid_classifications
        assert isinstance(g["place_ids"], list)
        assert len(g["place_ids"]) == 2
        assert len(set(g["place_ids"])) == 2
        assert bool(g.get("classification_reason"))
        assert "evidence_fields" in g
        assert "source_history_provenance" in g


def test_dup_04_map_contains_only_confirmed() -> None:
    """DUP-04: Active duplicate map contains only CONFIRMED_EQUIVALENT groups."""
    ev = _load_json(EVIDENCE_PATH)
    mp = _load_json(MAP_PATH)

    assert mp["artifact_version"] == "W5-DUP-MAP-V1"
    assert mp["evidence_version"] == "W5-DUP-EVIDENCE-V1"

    confirmed_in_ev = {
        g["candidate_group_id"]: set(g["place_ids"])
        for g in ev["groups"]
        if g["classification"] == "CONFIRMED_EQUIVALENT"
    }

    assert len(mp["groups"]) == len(confirmed_in_ev)
    for g in mp["groups"]:
        gid = g["equivalence_group_id"]
        assert gid in confirmed_in_ev
        assert set(g["place_ids"]) == confirmed_in_ev[gid]


def test_dup_05_no_ambiguous_in_map() -> None:
    """DUP-05: No AMBIGUOUS pair enters active map."""
    ev = _load_json(EVIDENCE_PATH)
    mp = _load_json(MAP_PATH)

    ambiguous_gids = {
        g["candidate_group_id"]
        for g in ev["groups"]
        if g["classification"] == "AMBIGUOUS"
    }

    mapped_gids = {g["equivalence_group_id"] for g in mp["groups"]}
    assert len(ambiguous_gids.intersection(mapped_gids)) == 0


def test_dup_06_no_not_confirmed_in_map() -> None:
    """DUP-06: No NOT_CONFIRMED pair enters active map."""
    ev = _load_json(EVIDENCE_PATH)
    mp = _load_json(MAP_PATH)

    not_confirmed_gids = {
        g["candidate_group_id"]
        for g in ev["groups"]
        if g["classification"] == "NOT_CONFIRMED"
    }

    mapped_gids = {g["equivalence_group_id"] for g in mp["groups"]}
    assert len(not_confirmed_gids.intersection(mapped_gids)) == 0


def test_dup_07_all_mapped_places_exist_in_freeze_v2() -> None:
    """DUP-07: All mapped place_ids exist in Freeze V2."""
    freeze_v2 = _load_json(FREEZE_V2_PATH)
    all_freeze_pids = {p["place_id"] for p in freeze_v2}

    mp = _load_json(MAP_PATH)
    for g in mp["groups"]:
        for pid in g["place_ids"]:
            assert pid in all_freeze_pids, f"Mapped place_id {pid} missing from Freeze V2"


def test_dup_08_mapped_members_share_destination() -> None:
    """DUP-08: Mapped pair members share the documented destination."""
    freeze_v2 = _load_json(FREEZE_V2_PATH)
    dest_map = {p["place_id"]: p.get("destination_slug") for p in freeze_v2}

    mp = _load_json(MAP_PATH)
    for g in mp["groups"]:
        expected_dest = g["destination"]
        for pid in g["place_ids"]:
            assert dest_map[pid] == expected_dest, (
                f"Place {pid} destination {dest_map[pid]} != expected {expected_dest}"
            )


def test_dup_09_primary_intersection_recomputed() -> None:
    """DUP-09: Primary intersection is recomputed from frozen 474 pool."""
    internal_pool = _load_json(INTERNAL_POOL_PATH)
    pool_pids: Set[str] = set()
    for scn in internal_pool:
        for it in scn["items"]:
            pool_pids.add(it["place_id"])

    mp = _load_json(MAP_PATH)
    confirmed_pids: Set[str] = set()
    for g in mp["groups"]:
        confirmed_pids.update(g["place_ids"])

    intersection = pool_pids.intersection(confirmed_pids)
    assert len(intersection) == 0


def test_dup_10_reported_intersection_count_matches_computed() -> None:
    """DUP-10: Reported intersection count in gate result equals computed count."""
    internal_pool = _load_json(INTERNAL_POOL_PATH)
    pool_pids = {it["place_id"] for scn in internal_pool for it in scn["items"]}

    mp = _load_json(MAP_PATH)
    confirmed_pids = {pid for g in mp["groups"] for pid in g["place_ids"]}
    computed_intersection_count = len(pool_pids.intersection(confirmed_pids))

    gr = _load_json(GATE_RESULT_PATH)
    assert gr["primary_pool_intersection_count"] == computed_intersection_count
    assert gr["primary_pool_intersection_count"] == 0


def test_dup_11_affected_scenarios_matches_computed() -> None:
    """DUP-11: Affected scenario list equals computed scenarios."""
    internal_pool = _load_json(INTERNAL_POOL_PATH)
    mp = _load_json(MAP_PATH)
    confirmed_pids = {pid for g in mp["groups"] for pid in g["place_ids"]}

    computed_affected: List[str] = []
    for scn in internal_pool:
        scn_pids = {it["place_id"] for it in scn["items"]}
        if scn_pids.intersection(confirmed_pids):
            computed_affected.append(scn["scenario_id"])

    gr = _load_json(GATE_RESULT_PATH)
    assert gr["affected_primary_scenarios"] == computed_affected
    assert gr["affected_primary_scenarios"] == []


def test_dup_12_frozen_candidate_pool_bytes_unchanged() -> None:
    """DUP-12: No frozen candidate pool bytes changed."""
    assert _sha256_bytes(INTERNAL_POOL_PATH) == EXPECTED_INTERNAL_POOL_SHA256
    assert _sha256_bytes(BLINDED_POOL_PATH) == EXPECTED_BLINDED_POOL_SHA256
    _ensure_commit(BASE_DEVELOP_COMMIT)
    res = subprocess.run(
        ["git", "diff", BASE_DEVELOP_COMMIT, "--", str(INTERNAL_POOL_PATH), str(BLINDED_POOL_PATH)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == "", "Frozen candidate pool files modified relative to base commit!"


def test_dup_13_primary_scenarios_bytes_unchanged() -> None:
    """DUP-13: No primary scenario bytes changed."""
    assert _sha256_bytes(PRIMARY_SCENARIOS_PATH) == EXPECTED_PRIMARY_SCENARIOS_SHA256
    _ensure_commit(BASE_DEVELOP_COMMIT)
    res = subprocess.run(
        ["git", "diff", BASE_DEVELOP_COMMIT, "--", str(PRIMARY_SCENARIOS_PATH)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == "", "Primary scenarios file modified relative to base commit!"


def test_dup_14_freeze_v2_bytes_unchanged() -> None:
    """DUP-14: No Freeze V2 bytes changed."""
    assert _sha256_bytes(FREEZE_V2_PATH) == EXPECTED_FREEZE_V2_SHA256
    _ensure_commit(BASE_DEVELOP_COMMIT)
    res = subprocess.run(
        ["git", "diff", BASE_DEVELOP_COMMIT, "--", str(FREEZE_V2_PATH)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == "", "Freeze V2 file modified relative to base commit!"


def test_dup_15_human_judgments_remain_zero() -> None:
    """DUP-15: Human judgments remain zero."""
    manifest = _load_json(PREREG_MANIFEST_PATH)
    assert manifest["human_judgments_collected"] == 0
    assert manifest["human_gt_available"] is False

    gr = _load_json(GATE_RESULT_PATH)
    assert gr["human_labels_used"] is False


def test_dup_16_no_recommender_code_modified() -> None:
    """DUP-16: No recommender code modified."""
    gr = _load_json(GATE_RESULT_PATH)
    assert gr["recommender_modified"] is False
    assert gr["frozen_pool_modified"] is False

    _ensure_commit(BASE_DEVELOP_COMMIT)
    res = subprocess.run(
        ["git", "diff", BASE_DEVELOP_COMMIT, "--", "apps/ai-service/recommendation"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == "", "Recommender code was modified relative to base commit!"


def test_dup_17_gate_status_and_policy_status_branch() -> None:
    """DUP-17: Branch decision verified for gate status and policy status."""
    gr = _load_json(GATE_RESULT_PATH)
    assert gr["gate"] == "W5-GATE-DUP"
    assert gr["gate_version"] == "W5-GATE-DUP-V1"
    assert gr["preregistration_version"] == "REC-EVAL-01-PREREG-V1"

    if gr["primary_pool_intersection_count"] == 0:
        assert gr["status"] == "PASS"
        assert gr["duplicate_policy_status"] == "CLOSED_NO_PRIMARY_EVAL_IMPACT"
    else:
        assert gr["status"] == "BLOCKED"
        assert gr["duplicate_policy_status"] == "BLOCKED_REQUIRES_SCORING_POLICY"


def test_dup_18_no_duplicate_aware_metric_scoring_activated() -> None:
    """DUP-18: No duplicate-aware metric scoring is activated by this task."""
    runner_path = REPO_ROOT / "scripts" / "evaluate_w5_recommenders.py"
    assert runner_path.exists()
    _ensure_commit(BASE_DEVELOP_COMMIT)
    res = subprocess.run(
        ["git", "diff", BASE_DEVELOP_COMMIT, "--", str(runner_path)],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == "", "Evaluation runner script modified relative to base commit!"

    # Dry-run validation executes and verifies duplicate_policy_status remains PENDING in runner
    from scripts.evaluate_w5_recommenders import run_dry_run_validation
    val_res = run_dry_run_validation(repo_root=REPO_ROOT)
    assert val_res["status"] == "VALIDATION_PASSED"
    assert val_res["duplicate_policy_status"] == "PENDING"


def test_dup_evidence_01_dn01_website_strings_differ() -> None:
    """DUP-EVIDENCE-01: Stored DN-01 website strings differ; no claim of identical URLs or web resolution."""
    ev = _load_json(EVIDENCE_PATH)
    dn01 = next(g for g in ev["groups"] if g["candidate_group_id"] == "DUP-CORE-DN-01")
    items = dn01["evidence_fields"]["items"]
    urls = [it.get("website") for it in items]
    assert len(urls) == 2
    assert urls[0] != urls[1], f"Expected distinct stored website strings, got {urls[0]} == {urls[1]}"

    reason = dn01["classification_reason"]
    assert "differ" in reason.lower()
    assert "no external web resolution" in reason.lower()

    # Documentation check
    doc_text = GATE_DOC_PATH.read_text(encoding="utf-8")
    assert "Stored URL strings differ" in doc_text
    assert "no web resolution performed" in doc_text or "no external web resolution was performed" in doc_text


def test_dup_evidence_02_documented_normalized_names_match_artifact() -> None:
    """DUP-EVIDENCE-02: Documented normalized names match exact evidence artifact values."""
    ev = _load_json(EVIDENCE_PATH)
    dn02 = next(g for g in ev["groups"] if g["candidate_group_id"] == "DUP-CORE-DN-02")
    norm_name_items = [it["normalized_name"] for it in dn02["evidence_fields"]["items"]]
    assert all(n == "đen linh chua linh tu" for n in norm_name_items)

    doc_text = GATE_DOC_PATH.read_text(encoding="utf-8")
    assert "đen linh chua linh tu" in doc_text
    # Ensure ASCII 'den linh chua linh tu' is not documented as the normalized name
    assert "`den linh chua linh tu`" not in doc_text


def test_dup_claim_01_scoped_known_group_conclusion() -> None:
    """DUP-CLAIM-01: Documentation contains scoped known-group conclusion."""
    doc_text = GATE_DOC_PATH.read_text(encoding="utf-8")
    expected_scoped_claim = (
        "REC-EVAL-01 primary scoring is not affected by the three known confirmed "
        "duplicate-equivalence groups reviewed in W5-GATE-DUP-V1."
    )
    assert expected_scoped_claim in doc_text

    expected_formal_stmt = (
        "Known confirmed duplicate-equivalent records reviewed by this gate do not "
        "intersect the frozen primary W5 judgment universe; therefore no duplicate "
        "correction is required for REC-EVAL-01 primary scoring."
    )
    assert expected_formal_stmt in doc_text


def test_dup_claim_02_no_global_duplicate_free_or_uncorrupted_claim() -> None:
    """DUP-CLAIM-02: Documentation does NOT claim global duplicate-free catalog or uncorrupted evaluation."""
    doc_text = GATE_DOC_PATH.read_text(encoding="utf-8")
    assert "uncorrupted by duplicate place records" not in doc_text
    assert "scientifically uncorrupted" not in doc_text

    for line in doc_text.splitlines():
        if "duplicate-free" in line.lower():
            assert "not claim" in line.lower() or "does not claim" in line.lower(), (
                f"Unsupported global duplicate-free claim in line: {line}"
            )


def test_dup_control_01_no_zero_vector_control_ineligibility_claim() -> None:
    """DUP-CONTROL-01: Documentation reports control non-selection descriptively, not causally attributed to I1."""
    doc_text = GATE_DOC_PATH.read_text(encoding="utf-8")
    assert "cannot be sampled as control" not in doc_text
    assert "ineligible for control" not in doc_text
    assert "not sampled among random controls" not in doc_text

    assert "seed 20261013" in doc_text
    assert "I0 and I1 strata" in doc_text or "draws from both" in doc_text
