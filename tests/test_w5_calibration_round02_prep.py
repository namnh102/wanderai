"""Tests for W5 Calibration Round 02 Preparation (W5-CAL-R02-PREP-01).

Covers all required tests R02-PREP-01 through R02-PREP-20:
- R02-PREP-01: round/version identifiers correct
- R02-PREP-02: exactly 3 scenarios
- R02-PREP-03: 15 items per scenario / 45 total
- R02-PREP-04: 45 unique Round 02 place_ids
- R02-PREP-05: 0 overlap with Round 01 calibration place_ids
- R02-PREP-06: 0 overlap with primary W5 candidate pool place_ids
- R02-PREP-07: all places belong to REC-A-CORE-V2
- R02-PREP-08: all 7 canonical interests covered across scenarios
- R02-PREP-09: all labels and notes null
- R02-PREP-10: same canonical membership across J1/J2/J3
- R02-PREP-11: judge presentation order differs deterministically
- R02-PREP-12: no model/rank/score/control leakage
- R02-PREP-13: actual human judgments collected = 0
- R02-PREP-14: HUMAN-GT = false
- R02-PREP-15: Round 01 remains invalidated and unchanged
- R02-PREP-16: missing/failed human attestation => NON_QUALIFYING
- R02-PREP-17: valid attestation contract requires actual_human_judge=true
- R02-PREP-18: AI/LLM use => NON_QUALIFYING
- R02-PREP-19: prior label exposure => NON_QUALIFYING
- R02-PREP-20: primary annotation remains NOT_STARTED
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from recommendation.reca.contract import CANONICAL_INTERESTS  # noqa: E402
from scripts.prepare_w5_calibration_round02 import (  # noqa: E402
    ALLOWED_JUDGES,
    BLINDED_POOL_PATH,
    CALIBRATION_VERSION,
    CSV_ALL_COLUMNS,
    FORBIDDEN_LEAKAGE_KEYS,
    FREEZE_V2_PATH,
    INTERNAL_POOL_PATH,
    PRESENTATION_VERSION,
    REQUIRED_ATTESTATION_BOOLEANS,
    ROUND01_CALIBRATION_PATH,
    ROUND02_ATTESTATION_TEMPLATE_PATH,
    ROUND02_CALIBRATION_PATH,
    ROUND02_MANIFEST_PATH,
    ROUND02_PACKAGES_DIR,
    ROUND02_ROLE_CONTRACT_PATH,
    ROUND02_SEED,
    ROUND02_SUBMISSION_CONTRACT_PATH,
    ROUND_ID,
    RUBRIC_VERSION,
    build_canonical_round02_calibration_doc,
    build_round02_judge_package,
    canonical_json_sha256,
    canonical_lf_sha256_file,
    validate_round02_package_or_submission,
    validate_round02_session_attestation,
)

EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "reca_w5"
ANNOTATION_DIR = EVAL_DIR / "annotation"
SUBMISSIONS_DIR = EVAL_DIR / "calibration_submissions"
RAW_V1_DIR = SUBMISSIONS_DIR / "raw_v1"
INCIDENT_PATH = SUBMISSIONS_DIR / "w5_calibration_round_01_integrity_incident_v1.json"
ROUND02_OPS_DOC_PATH = REPO_ROOT / "docs" / "research" / "w5_calibration_round02_ops_v1.md"

EXPECTED_ROUND01_RAW_HASHES = {
    "J1": "7a3b58f20169c98a7b472952e480afb96d34e58613afa0032a58d540062393ba",
    "J2": "b8464c133df5757cd4c1e741a21a5b2392544a175dc2ec32e5d1e6a4d2721707",
    "J3": "b2094cafb458f0ebdea1dd28ec4d5ef723062e449c3b51602edaaee00a86ba3f",
}


def _load_json(path: Path) -> Any:
    assert path.exists(), f"Missing file: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_attestation(judge_id: str = "J1") -> dict[str, Any]:
    return {
        "judge_id": judge_id,
        "round_id": ROUND_ID,
        "calibration_version": CALIBRATION_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "presentation_version": PRESENTATION_VERSION,
        "actual_human_judge": True,
        "ai_llm_used_for_label_decisions": False,
        "external_search_used": False,
        "inspected_other_judge_labels_before_submission": False,
        "exposed_to_other_judge_label_summary_before_submission": False,
        "direct_label_discussion_before_all_submissions_locked": False,
        "assigned_role_before_distribution": True,
        "completed_all_required_items": True,
    }


def test_r02_prep_01_round_and_version_identifiers() -> None:
    """R02-PREP-01: Round and version identifiers are exact across all Round 02 artifacts."""
    canonical = _load_json(ROUND02_CALIBRATION_PATH)
    manifest = _load_json(ROUND02_MANIFEST_PATH)
    role_contract = _load_json(ROUND02_ROLE_CONTRACT_PATH)
    att_template = _load_json(ROUND02_ATTESTATION_TEMPLATE_PATH)
    sub_contract = _load_json(ROUND02_SUBMISSION_CONTRACT_PATH)

    assert canonical["round_id"] == "W5-CAL-ROUND-02"
    assert canonical["calibration_version"] == "W5-CALIBRATION-V2"
    assert canonical["rubric_version"] == "W5-RUBRIC-V1"
    assert canonical["track"] == "CALIBRATION_ONLY"
    assert canonical["excluded_from_final_metrics"] is True
    assert canonical["base_seed"] == 20261014

    assert manifest["round_id"] == "W5-CAL-ROUND-02"
    assert manifest["calibration_version"] == "W5-CALIBRATION-V2"
    assert manifest["rubric_version"] == "W5-RUBRIC-V1"
    assert manifest["presentation_version"] == "W5-CAL-R02-OPS-V1"
    assert manifest["track"] == "CALIBRATION_ONLY"
    assert manifest["excluded_from_final_metrics"] is True
    assert manifest["status"] == "PREPARED_NOT_STARTED"

    assert role_contract["round_id"] == "W5-CAL-ROUND-02"
    assert role_contract["calibration_version"] == "W5-CALIBRATION-V2"
    assert role_contract["pre_distribution_assignment_required"] is True
    assert role_contract["personal_identifiable_information_stored_in_repo"] is False

    assert att_template["round_id"] == "W5-CAL-ROUND-02"
    assert att_template["calibration_version"] == "W5-CALIBRATION-V2"
    assert sub_contract["round_id"] == "W5-CAL-ROUND-02"
    assert sub_contract["calibration_version"] == "W5-CALIBRATION-V2"
    assert ROUND02_OPS_DOC_PATH.exists()


def test_r02_prep_02_exactly_3_scenarios() -> None:
    """R02-PREP-02: Exactly 3 locked Round 02 scenarios exist with exact destinations and interests."""
    canonical = _load_json(ROUND02_CALIBRATION_PATH)
    scenarios = canonical["scenarios"]
    assert canonical["scenario_count"] == 3
    assert len(scenarios) == 3

    expected = [
        (
            "CAL2-HN-01",
            "ha-noi",
            ["culture_history", "nature_outdoor", "nightlife_entertainment"],
        ),
        ("CAL2-DN-01", "da-nang", ["food_cuisine", "beach_island"]),
        ("CAL2-HL-01", "ha-long", ["coffee_culture", "shopping_local"]),
    ]
    actual = [
        (sc["scenario_id"], sc["destination"], sc["declared_interests"])
        for sc in scenarios
    ]
    assert actual == expected


def test_r02_prep_03_15_items_per_scenario_45_total() -> None:
    """R02-PREP-03: 15 items per scenario and 45 total items."""
    canonical = _load_json(ROUND02_CALIBRATION_PATH)
    assert canonical["total_items"] == 45
    total = 0
    for sc in canonical["scenarios"]:
        assert sc["item_count"] == 15
        assert len(sc["items"]) == 15
        total += len(sc["items"])
    assert total == 45


def test_r02_prep_04_45_unique_round02_place_ids() -> None:
    """R02-PREP-04: All 45 Round 02 place_ids and judge_item_ids are unique."""
    canonical = _load_json(ROUND02_CALIBRATION_PATH)
    place_ids = [
        it["place_id"] for sc in canonical["scenarios"] for it in sc["items"]
    ]
    item_ids = [
        it["judge_item_id"] for sc in canonical["scenarios"] for it in sc["items"]
    ]
    assert len(place_ids) == 45
    assert len(set(place_ids)) == 45
    assert len(set(item_ids)) == 45


def test_r02_prep_05_zero_overlap_with_round01_calibration_place_ids() -> None:
    """R02-PREP-05: 0 overlap with Round 01 (W5-CALIBRATION-V1) place_ids."""
    round01 = _load_json(ROUND01_CALIBRATION_PATH)
    round02 = _load_json(ROUND02_CALIBRATION_PATH)
    manifest = _load_json(ROUND02_MANIFEST_PATH)

    r01_ids = {it["place_id"] for sc in round01["scenarios"] for it in sc["items"]}
    r02_ids = {it["place_id"] for sc in round02["scenarios"] for it in sc["items"]}
    assert len(r01_ids) == 45
    assert len(r02_ids) == 45
    assert (r01_ids & r02_ids) == set()
    assert manifest["sampling_and_exclusion_audit"]["round01_place_overlap"] == 0


def test_r02_prep_06_zero_overlap_with_primary_candidate_pool_place_ids() -> None:
    """R02-PREP-06: 0 overlap with primary W5 candidate pool place_ids."""
    blinded = _load_json(BLINDED_POOL_PATH)
    internal = _load_json(INTERNAL_POOL_PATH)
    round02 = _load_json(ROUND02_CALIBRATION_PATH)
    manifest = _load_json(ROUND02_MANIFEST_PATH)

    prim_ids = {it["place_id"] for sc in blinded for it in sc["items"]} | {
        it["place_id"] for sc in internal for it in sc["items"]
    }
    r02_ids = {it["place_id"] for sc in round02["scenarios"] for it in sc["items"]}
    assert len(prim_ids) == 255
    assert (prim_ids & r02_ids) == set()
    assert manifest["sampling_and_exclusion_audit"]["primary_pool_place_overlap"] == 0


def test_r02_prep_07_all_places_belong_to_rec_a_core_v2() -> None:
    """R02-PREP-07: All 45 Round 02 places belong to REC-A-CORE-V2 in their scenario destination."""
    freeze = _load_json(FREEZE_V2_PATH)
    freeze_by_id = {p["place_id"]: p for p in freeze}
    round02 = _load_json(ROUND02_CALIBRATION_PATH)
    manifest = _load_json(ROUND02_MANIFEST_PATH)

    for sc in round02["scenarios"]:
        dst = sc["destination"]
        for it in sc["items"]:
            pid = it["place_id"]
            assert pid in freeze_by_id
            place = freeze_by_id[pid]
            assert place.get("is_rec_a_core_v2") is True
            assert place.get("destination_slug") == dst

    assert manifest["sampling_and_exclusion_audit"]["secondary_non_core_poi_leakage"] == 0


def test_r02_prep_08_all_7_canonical_interests_covered() -> None:
    """R02-PREP-08: All 7 canonical REC-A interest dimensions are covered across scenarios."""
    round02 = _load_json(ROUND02_CALIBRATION_PATH)
    manifest = _load_json(ROUND02_MANIFEST_PATH)

    covered = [
        interest
        for sc in round02["scenarios"]
        for interest in sc["declared_interests"]
    ]
    assert len(covered) == 7
    assert set(covered) == set(CANONICAL_INTERESTS)
    assert manifest["canonical_interest_coverage"]["all_7_covered"] is True


def test_r02_prep_09_all_labels_and_notes_null() -> None:
    """R02-PREP-09: All labels and judge_notes are null in canonical and J1/J2/J3 packages."""
    round02 = _load_json(ROUND02_CALIBRATION_PATH)
    for sc in round02["scenarios"]:
        for it in sc["items"]:
            assert it["label"] is None
            assert it["judge_note"] is None

    for jid in ALLOWED_JUDGES:
        json_path = ROUND02_PACKAGES_DIR / f"w5_calibration_round02_{jid}_v2.json"
        csv_path = ROUND02_PACKAGES_DIR / f"w5_calibration_round02_{jid}_v2.csv"
        pkg = _load_json(json_path)
        res = validate_round02_package_or_submission(
            pkg, canonical_doc=round02, validate_empty_package=True
        )
        assert res["status"] == "PASS"
        assert res["label_counts"]["null"] == 45

        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            assert tuple(reader.fieldnames or ()) == CSV_ALL_COLUMNS
            rows = list(reader)
        assert len(rows) == 45
        for r in rows:
            assert r["label"] == ""
            assert r["judge_note"] == ""


def test_r02_prep_10_same_canonical_membership_across_judges() -> None:
    """R02-PREP-10: J1, J2, and J3 receive the exact same 45 canonical items."""
    round02 = _load_json(ROUND02_CALIBRATION_PATH)
    canonical_membership = {
        (sc["scenario_id"], it["judge_item_id"], it["place_id"])
        for sc in round02["scenarios"]
        for it in sc["items"]
    }
    assert len(canonical_membership) == 45

    for jid in ALLOWED_JUDGES:
        pkg = _load_json(ROUND02_PACKAGES_DIR / f"w5_calibration_round02_{jid}_v2.json")
        pkg_membership = {
            (sc["scenario_id"], it["judge_item_id"], it["place_id"])
            for sc in pkg["scenarios"]
            for it in sc["items"]
        }
        assert pkg_membership == canonical_membership


def test_r02_prep_11_judge_presentation_order_differs_deterministically() -> None:
    """R02-PREP-11: J1, J2, and J3 presentation orders differ deterministically and are reproducible."""
    round02 = _load_json(ROUND02_CALIBRATION_PATH)
    manifest = _load_json(ROUND02_MANIFEST_PATH)

    rebuilt_doc, _ = build_canonical_round02_calibration_doc()
    assert canonical_json_sha256(rebuilt_doc) == canonical_json_sha256(round02)

    orders_by_judge: dict[str, list[str]] = {}
    for jid in ALLOWED_JUDGES:
        pkg = _load_json(ROUND02_PACKAGES_DIR / f"w5_calibration_round02_{jid}_v2.json")
        rebuilt_pkg = build_round02_judge_package(round02, jid)
        assert canonical_json_sha256(pkg) == canonical_json_sha256(rebuilt_pkg)

        item_order = [
            it["judge_item_id"] for sc in pkg["scenarios"] for it in sc["items"]
        ]
        orders_by_judge[jid] = item_order
        order_sha = hashlib.sha256(
            json.dumps(item_order, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert manifest["presentation_order_hashes"][jid] == order_sha

    assert orders_by_judge["J1"] != orders_by_judge["J2"]
    assert orders_by_judge["J1"] != orders_by_judge["J3"]
    assert orders_by_judge["J2"] != orders_by_judge["J3"]


def test_r02_prep_12_no_model_rank_score_control_or_cross_judge_leakage() -> None:
    """R02-PREP-12: No model, rank, score, control, expected relevance, or cross-judge leakage."""
    forbidden_substrings = (
        "rec-a0",
        "rec-a1",
        "rec-a2",
        "rec_a0",
        "rec_a1",
        "rec_a2",
        "expected_relevance",
        "expected_label",
        "ground_truth",
        "is_control",
        "source_systems",
        "similarity_score",
        "confidence_score",
    )
    for jid in ALLOWED_JUDGES:
        other_judges = [other for other in ALLOWED_JUDGES if other != jid]
        json_path = ROUND02_PACKAGES_DIR / f"w5_calibration_round02_{jid}_v2.json"
        csv_path = ROUND02_PACKAGES_DIR / f"w5_calibration_round02_{jid}_v2.csv"
        raw_text = json_path.read_text(encoding="utf-8")
        lower_text = raw_text.lower()

        for tok in forbidden_substrings:
            assert tok not in lower_text, f"Forbidden token {tok!r} found in {json_path.name}"

        for other in other_judges:
            assert f'"{other}"' not in raw_text
            assert f":{other}:" not in raw_text

        pkg = json.loads(raw_text)
        for sc in pkg["scenarios"]:
            for it in sc["items"]:
                assert set(it.keys()).isdisjoint(FORBIDDEN_LEAKAGE_KEYS)
                assert set(it["factual_context"].keys()).isdisjoint(FORBIDDEN_LEAKAGE_KEYS)

        csv_text = csv_path.read_text(encoding="utf-8")
        for other in other_judges:
            assert f"{other}," not in csv_text


def test_r02_prep_13_actual_human_judgments_collected_is_zero() -> None:
    """R02-PREP-13: actual_human_judgments_collected == 0 and qualifying == 0."""
    manifest = _load_json(ROUND02_MANIFEST_PATH)
    assert manifest["actual_human_judgments_collected"] == 0
    assert manifest["qualifying_independent_human_judgments"] == 0
    assert manifest["calibration_review_eligible"] is False


def test_r02_prep_14_human_gt_is_false() -> None:
    """R02-PREP-14: human_gt == false and no recommender evaluation performed."""
    manifest = _load_json(ROUND02_MANIFEST_PATH)
    assert manifest["human_gt"] is False
    assert manifest["recommender_evaluation_performed"] is False
    assert manifest["scientific_winner"] == "UNKNOWN"


def test_r02_prep_15_round01_remains_invalidated_and_unchanged() -> None:
    """R02-PREP-15: Round 01 incident and raw files remain invalidated and byte-identical."""
    incident = _load_json(INCIDENT_PATH)
    assert incident["round_id"] == "W5-CAL-ROUND-01"
    assert incident["round_status"] == "INVALIDATED_FOR_PROTOCOL"
    assert incident["scientific_use"] == "FORENSIC_NON_QUALIFYING_EVIDENCE_ONLY"
    assert incident["qualifying_independent_human_judgments"] == 0
    assert incident["fresh_round_required"] is True
    assert incident["next_round_policy"]["fresh_calibration_package_required"] is True

    for jid, expected_sha in EXPECTED_ROUND01_RAW_HASHES.items():
        raw_path = RAW_V1_DIR / f"{jid}_w5_calibration_raw_v1.csv"
        actual_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        assert actual_sha == expected_sha


def test_r02_prep_16_missing_or_failed_attestation_is_non_qualifying() -> None:
    """R02-PREP-16: Missing or incomplete human attestation => NON_QUALIFYING."""
    res_none = validate_round02_session_attestation(None, expected_judge_id="J1")
    assert res_none["qualification_status"] == "NON_QUALIFYING"
    assert res_none["valid"] is False

    template_doc = _load_json(ROUND02_ATTESTATION_TEMPLATE_PATH)
    blank_att = copy.deepcopy(template_doc["per_judge_attestation_template"])
    blank_att["judge_id"] = "J1"
    res_blank = validate_round02_session_attestation(blank_att, expected_judge_id="J1")
    assert res_blank["qualification_status"] == "NON_QUALIFYING"
    assert res_blank["valid"] is False

    for key in REQUIRED_ATTESTATION_BOOLEANS:
        missing_one = _valid_attestation("J1")
        missing_one.pop(key)
        res_missing = validate_round02_session_attestation(
            missing_one, expected_judge_id="J1"
        )
        assert res_missing["qualification_status"] == "NON_QUALIFYING"
        assert res_missing["valid"] is False


def test_r02_prep_17_valid_attestation_requires_actual_human_judge_true() -> None:
    """R02-PREP-17: Valid attestation contract requires actual_human_judge=True and pre-assigned role."""
    valid_att = _valid_attestation("J1")
    res_valid = validate_round02_session_attestation(valid_att, expected_judge_id="J1")
    assert res_valid["qualification_status"] == "QUALIFYING"
    assert res_valid["valid"] is True
    assert res_valid["reasons"] == []

    not_human = _valid_attestation("J1")
    not_human["actual_human_judge"] = False
    res_not_human = validate_round02_session_attestation(
        not_human, expected_judge_id="J1"
    )
    assert res_not_human["qualification_status"] == "NON_QUALIFYING"
    assert res_not_human["valid"] is False

    self_selected = _valid_attestation("J1")
    self_selected["assigned_role_before_distribution"] = False
    res_self = validate_round02_session_attestation(
        self_selected, expected_judge_id="J1"
    )
    assert res_self["qualification_status"] == "NON_QUALIFYING"
    assert res_self["valid"] is False


def test_r02_prep_18_ai_llm_use_makes_submission_non_qualifying() -> None:
    """R02-PREP-18: AI/LLM use => NON_QUALIFYING even if all 45 labels are valid."""
    att_ai = _valid_attestation("J1")
    att_ai["ai_llm_used_for_label_decisions"] = True
    res_att = validate_round02_session_attestation(att_ai, expected_judge_id="J1")
    assert res_att["qualification_status"] == "NON_QUALIFYING"
    assert res_att["valid"] is False

    pkg = _load_json(ROUND02_PACKAGES_DIR / "w5_calibration_round02_J1_v2.json")
    completed_pkg = copy.deepcopy(pkg)
    for sc in completed_pkg["scenarios"]:
        for it in sc["items"]:
            it["label"] = 1
            it["judge_note"] = "Human note"

    sub_res = validate_round02_package_or_submission(
        completed_pkg, validate_empty_package=False, attestation_doc=att_ai
    )
    assert sub_res["file_integrity_status"] == "PASS"
    assert sub_res["qualification_status"] == "NON_QUALIFYING"
    assert sub_res["status"] == "NON_QUALIFYING"


def test_r02_prep_19_prior_label_exposure_makes_submission_non_qualifying() -> None:
    """R02-PREP-19: Prior label exposure or discussion or external search => NON_QUALIFYING."""
    for violation_key in (
        "inspected_other_judge_labels_before_submission",
        "exposed_to_other_judge_label_summary_before_submission",
        "direct_label_discussion_before_all_submissions_locked",
        "external_search_used",
    ):
        bad_att = _valid_attestation("J2")
        bad_att[violation_key] = True
        res = validate_round02_session_attestation(bad_att, expected_judge_id="J2")
        assert res["qualification_status"] == "NON_QUALIFYING"
        assert res["valid"] is False


def test_r02_prep_20_primary_annotation_remains_not_started() -> None:
    """R02-PREP-20: Primary annotation remains NOT_STARTED with all 474 labels null per judge."""
    manifest = _load_json(ROUND02_MANIFEST_PATH)
    assert manifest["primary_annotation_started"] is False

    for jid in ALLOWED_JUDGES:
        pkg = _load_json(ANNOTATION_DIR / f"w5_judge_{jid}_v1.json")
        for sc in pkg["scenarios"]:
            for it in sc["items"]:
                assert it["label"] is None
                assert it["judge_note"] is None


def test_r02_prep_21_manifest_hashes_and_lf_invariants() -> None:
    """Verify all Round 02 artifacts use LF line endings and match manifest canonical hashes."""
    manifest = _load_json(ROUND02_MANIFEST_PATH)
    for info in manifest["artifacts"].values():
        path = REPO_ROOT / info["path"]
        raw_bytes = path.read_bytes()
        assert b"\r\n" not in raw_bytes, f"CRLF found in {path}"
        assert canonical_lf_sha256_file(path) == info["canonical_lf_sha256"]
        assert canonical_json_sha256(_load_json(path)) == info["canonical_json_sha256"]

    for jid in ALLOWED_JUDGES:
        jrec = manifest["judge_packages"][jid]
        json_path = REPO_ROOT / jrec["json_path"]
        csv_path = REPO_ROOT / jrec["csv_path"]
        assert b"\r\n" not in json_path.read_bytes()
        assert b"\r\n" not in csv_path.read_bytes()
        assert canonical_lf_sha256_file(json_path) == jrec["json_canonical_lf_sha256"]
        assert canonical_json_sha256(_load_json(json_path)) == jrec["json_canonical_object_sha256"]
        assert canonical_lf_sha256_file(csv_path) == jrec["csv_canonical_lf_sha256"]

    assert ROUND02_SEED == 20261014
