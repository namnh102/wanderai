"""Test suite for W5 human annotation package and reliability tooling.

Covers all required ANN-* test specifications:
- ANN-RUBRIC-01: rubric contains only 0/1/2/NA labels
- ANN-LABEL-01: all generated judge labels are null
- ANN-LABEL-02: all generated judge notes are null
- ANN-BLIND-01: judge packages contain no model identity
- ANN-BLIND-02: judge packages contain no rank/score/strategy/control fields
- ANN-BLIND-03: engineered taxonomy/canonical fields absent
- ANN-ORDER-01: J1/J2/J3 use different deterministic seeds
- ANN-ORDER-02: same candidate membership for all judges
- ANN-ORDER-03: re-running builder gives identical package hashes
- ANN-FACT-01: factual context uses explicit allowlist
- ANN-FACT-02: tier_1/tier_2 never exposed
- ANN-META-01: all 474 canonical judgment records receive a sufficiency status
- ANN-CAL-01: exactly 3 calibration scenarios
- ANN-CAL-02: calibration excluded from final metrics
- ANN-AGG-01: median cases work
- ANN-AGG-02: 0/1/2 flags severe disagreement
- ANN-AGG-03: 0/0/2 flags severe disagreement
- ANN-AGG-04: 0/2/2 flags severe disagreement
- ANN-NA-01: NA is never converted to 0
- ANN-ALPHA-01: known synthetic perfect agreement -> alpha = 1
- ANN-ALPHA-02: synthetic disagreement produces alpha < 1
- ANN-DATA-01: canonical pool membership unchanged
- ANN-DATA-02: Freeze V2 unchanged
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts.analyze_w5_judgments import (
    aggregate_three_judgments,
    calculate_krippendorff_alpha_ci,
    calculate_krippendorff_alpha_ordinal,
    compute_agreement_statistics,
    interpret_reliability_gate,
    validate_judgment_label,
)
from scripts.build_w5_annotation_package import (
    BASE_SEED,
    EXCLUDED_FIELDS,
    FACTUAL_TAG_ALLOWLIST,
    RUBRIC_VERSION,
)

ANNOTATION_DIR = os.path.join(REPO_ROOT, "data", "evaluation", "reca_w5", "annotation")
EVAL_DIR = os.path.join(REPO_ROOT, "data", "evaluation", "reca_w5")
FREEZE_PATH = os.path.join(REPO_ROOT, "data", "curated", "gomate_places_freeze_v2.json")

EXPECTED_W5_PREP_01_HASHES = {
    "w5_primary_scenarios_v1.json": "4f0c77dccc2c0bae32f5d87f1364a8e1487a83e9b7344a9d8d3c9d0528bc29fb",
    "w5_thin_diagnostic_scenarios_v1.json": "538233a937acdd38ea208980a9ba629391b61e721363189f10f6087186fcfa77",
    "w5_candidate_pool_internal_v1.json": "32b25ef8ffc19d671513f771d3d3a0d23ceb9d0cf614ace1eded94d8c84126c6",
    "w5_candidate_pool_blinded_v1.json": "8f178e06b1b93e59b3a53f1b2bf1b6ecc697ccfa610d56783b613b6aa2f06ec7",
    "w5_reproducibility_manifest_v1.json": "ae2cbb97689148274723617e00a833093971c5f7cc11c7cdec39ec19619f6388",
}


def test_ann_rubric_01_labels() -> None:
    """ANN-RUBRIC-01: rubric contains only 0/1/2/NA labels."""
    rubric_path = os.path.join(ANNOTATION_DIR, "w5_rubric_v1.md")
    assert os.path.exists(rubric_path), f"Rubric missing at {rubric_path}"
    content = open(rubric_path, encoding="utf-8").read()

    assert RUBRIC_VERSION in content
    assert "NOT_RELEVANT" in content
    assert "HIGHLY_RELEVANT" in content
    assert "INSUFFICIENT_EVIDENCE" in content
    assert "NA != 0" in content

    # Check annotation template allowed labels
    tmpl_path = os.path.join(ANNOTATION_DIR, "w5_annotation_template_v1.json")
    tmpl = json.load(open(tmpl_path, encoding="utf-8"))
    assert tmpl["allowed_labels"] == [0, 1, 2, "NA"]


def test_ann_label_01_all_judge_labels_null() -> None:
    """ANN-LABEL-01: all generated judge labels are null."""
    for jid in ["J1", "J2", "J3"]:
        path = os.path.join(ANNOTATION_DIR, f"w5_judge_{jid}_v1.json")
        pkg = json.load(open(path, encoding="utf-8"))
        for sc in pkg["scenarios"]:
            for item in sc["items"]:
                assert item["label"] is None, f"Found non-null label in {jid} scenario {sc['scenario_id']}"


def test_ann_label_02_all_judge_notes_null() -> None:
    """ANN-LABEL-02: all generated judge notes are null."""
    for jid in ["J1", "J2", "J3"]:
        path = os.path.join(ANNOTATION_DIR, f"w5_judge_{jid}_v1.json")
        pkg = json.load(open(path, encoding="utf-8"))
        for sc in pkg["scenarios"]:
            for item in sc["items"]:
                assert item["judge_note"] is None, f"Found non-null judge_note in {jid}"


def test_ann_blind_01_no_model_identity() -> None:
    """ANN-BLIND-01: judge packages contain no model identity."""
    forbidden_tokens = ["rec-a0", "rec-a1", "rec-a2", "rec_a0", "rec_a1", "rec_a2", "model_a0", "model_a1", "model_a2"]
    for jid in ["J1", "J2", "J3"]:
        path = os.path.join(ANNOTATION_DIR, f"w5_judge_{jid}_v1.json")
        text = open(path, encoding="utf-8").read().lower()
        for tok in forbidden_tokens:
            assert tok not in text, f"Found forbidden model token '{tok}' in {jid}"


def test_ann_blind_02_no_rank_score_control() -> None:
    """ANN-BLIND-02: judge packages contain no rank/score/strategy/control fields."""
    forbidden_keys = {"rank", "score", "strategy", "control", "is_control", "source_systems"}
    for jid in ["J1", "J2", "J3"]:
        path = os.path.join(ANNOTATION_DIR, f"w5_judge_{jid}_v1.json")
        pkg = json.load(open(path, encoding="utf-8"))
        for sc in pkg["scenarios"]:
            for item in sc["items"]:
                for fk in forbidden_keys:
                    assert fk not in item, f"Forbidden key '{fk}' in item {item.get('place_id')}"
                fc = item.get("factual_context", {})
                for fk in forbidden_keys:
                    assert fk not in fc, f"Forbidden key '{fk}' in factual_context of {item.get('place_id')}"


def test_ann_blind_03_no_engineered_taxonomy() -> None:
    """ANN-BLIND-03: engineered taxonomy/canonical fields absent."""
    for jid in ["J1", "J2", "J3"]:
        path = os.path.join(ANNOTATION_DIR, f"w5_judge_{jid}_v1.json")
        pkg = json.load(open(path, encoding="utf-8"))
        for sc in pkg["scenarios"]:
            for item in sc["items"]:
                fc = item.get("factual_context", {})
                osm_tags = fc.get("osm_factual_tags", {})
                for ef in EXCLUDED_FIELDS:
                    assert ef not in item, f"Excluded field '{ef}' present in judge item"
                    assert ef not in fc, f"Excluded field '{ef}' present in factual context"
                    assert ef not in osm_tags, f"Excluded field '{ef}' present in osm_factual_tags"


def test_ann_order_01_different_seeds() -> None:
    """ANN-ORDER-01: J1/J2/J3 use different deterministic seeds."""
    manifest_path = os.path.join(ANNOTATION_DIR, "w5_annotation_manifest_v1.json")
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    assert manifest["base_seed"] == BASE_SEED

    # Check that SHA256 of the 3 packages differ
    j1_hash = manifest["judge_packages"]["J1"]["sha256"]
    j2_hash = manifest["judge_packages"]["J2"]["sha256"]
    j3_hash = manifest["judge_packages"]["J3"]["sha256"]

    assert j1_hash != j2_hash
    assert j2_hash != j3_hash
    assert j1_hash != j3_hash


def test_ann_order_02_same_candidate_membership() -> None:
    """ANN-ORDER-02: same candidate membership for all judges."""
    packages = {}
    for jid in ["J1", "J2", "J3"]:
        path = os.path.join(ANNOTATION_DIR, f"w5_judge_{jid}_v1.json")
        packages[jid] = json.load(open(path, encoding="utf-8"))

    # Verify scenario counts and total items match exactly
    for jid in ["J1", "J2", "J3"]:
        assert packages[jid]["scenario_count"] == 30
        assert packages[jid]["total_items"] == 474

    # Verify per-scenario item set equality
    for i in range(30):
        sc_id = packages["J1"]["scenarios"][i]["scenario_id"]
        set_j1 = set(it["place_id"] for it in packages["J1"]["scenarios"][i]["items"])
        set_j2 = set(it["place_id"] for it in packages["J2"]["scenarios"][i]["items"])
        set_j3 = set(it["place_id"] for it in packages["J3"]["scenarios"][i]["items"])

        assert set_j1 == set_j2, f"Membership mismatch between J1 and J2 in {sc_id}"
        assert set_j1 == set_j3, f"Membership mismatch between J1 and J3 in {sc_id}"

    # Verify that candidate order differs across scenarios (not identical across all 30)
    order_differences = 0
    for i in range(30):
        seq_j1 = [it["place_id"] for it in packages["J1"]["scenarios"][i]["items"]]
        seq_j2 = [it["place_id"] for it in packages["J2"]["scenarios"][i]["items"]]
        seq_j3 = [it["place_id"] for it in packages["J3"]["scenarios"][i]["items"]]
        if seq_j1 != seq_j2 or seq_j2 != seq_j3:
            order_differences += 1
    assert order_differences > 0, "Orders were unexpectedly identical across all scenarios"


def test_ann_order_03_reproducible_builder() -> None:
    """ANN-ORDER-03: re-running builder gives identical package hashes."""
    paths = [
        os.path.join(ANNOTATION_DIR, f"w5_judge_{jid}_v1.json") for jid in ["J1", "J2", "J3"]
    ]
    # Backup all files in ANNOTATION_DIR so tracked git artifacts are not left modified
    backup = {
        fname: open(os.path.join(ANNOTATION_DIR, fname), "rb").read()
        for fname in os.listdir(ANNOTATION_DIR)
        if os.path.isfile(os.path.join(ANNOTATION_DIR, fname))
    }
    # Compare canonical LF-normalized content for cross-platform reproducibility
    initial_hashes = [
        hashlib.sha256(backup[os.path.basename(p)].replace(b"\r\n", b"\n")).hexdigest()
        for p in paths
    ]

    try:
        # Re-run builder
        res = subprocess.run(["python", "scripts/build_w5_annotation_package.py"], cwd=REPO_ROOT, check=True)
        assert res.returncode == 0

        re_run_hashes = [
            hashlib.sha256(open(p, "rb").read().replace(b"\r\n", b"\n")).hexdigest()
            for p in paths
        ]
        assert initial_hashes == re_run_hashes
    finally:
        # Restore original file bytes so git status remains clean
        for fname, raw_bytes in backup.items():
            with open(os.path.join(ANNOTATION_DIR, fname), "wb") as f:
                f.write(raw_bytes)


def test_ann_fact_01_factual_context_allowlist() -> None:
    """ANN-FACT-01: factual context uses explicit allowlist."""
    pkg = json.load(open(os.path.join(ANNOTATION_DIR, "w5_judge_J1_v1.json"), encoding="utf-8"))
    for sc in pkg["scenarios"]:
        for item in sc["items"]:
            fc = item["factual_context"]
            assert "name" in fc
            assert "category" in fc
            assert "destination" in fc
            assert "latitude" in fc
            assert "longitude" in fc
            osm_tags = fc.get("osm_factual_tags", {})
            for k in osm_tags:
                assert k in FACTUAL_TAG_ALLOWLIST, f"Tag '{k}' not in allowlist"


def test_ann_fact_02_tier1_tier2_never_exposed() -> None:
    """ANN-FACT-02: tier_1/tier_2 never exposed."""
    for fname in ["w5_judge_J1_v1.json", "w5_judge_J2_v1.json", "w5_judge_J3_v1.json", "w5_calibration_v1.json"]:
        content = open(os.path.join(ANNOTATION_DIR, fname), encoding="utf-8").read()
        assert "tier_1" not in content
        assert "tier_2" not in content


def test_ann_meta_01_all_474_have_sufficiency() -> None:
    """ANN-META-01: all 474 canonical judgment records receive a sufficiency status."""
    meta_path = os.path.join(ANNOTATION_DIR, "w5_metadata_sufficiency_v1.json")
    meta = json.load(open(meta_path, encoding="utf-8"))

    assert meta["total_records"] == 474
    counts = meta["sufficiency_counts"]
    assert counts["SUFFICIENT_FACTUAL_CONTEXT"] + counts["LIMITED_FACTUAL_CONTEXT"] + counts["INSUFFICIENT_FACTUAL_CONTEXT"] == 474
    assert counts["INSUFFICIENT_FACTUAL_CONTEXT"] == 0
    assert len(meta["records"]) == 474
    assert meta["human_judging_metadata_gate_recommendation"] == "PASS_WITH_QUALIFICATION"
    assert meta["human_judging_metadata_gate"] == "PASS_WITH_QUALIFICATION"

    for rec in meta["records"]:
        assert rec["sufficiency_status"] in {"SUFFICIENT_FACTUAL_CONTEXT", "LIMITED_FACTUAL_CONTEXT", "INSUFFICIENT_FACTUAL_CONTEXT"}
        assert len(rec["sufficiency_reason"]) > 0


def test_ann_cal_01_dedicated_scenario_ids() -> None:
    """ANN-CAL-01: dedicated calibration scenario IDs not in primary manifest."""
    cal_path = os.path.join(ANNOTATION_DIR, "w5_calibration_v1.json")
    primary_path = os.path.join(EVAL_DIR, "w5_primary_scenarios_v1.json")

    cal = json.load(open(cal_path, encoding="utf-8"))
    primary = json.load(open(primary_path, encoding="utf-8"))

    cal_ids = [sc["scenario_id"] for sc in cal["scenarios"]]
    primary_ids = [sc["scenario_id"] for sc in primary]

    assert cal_ids == ["CAL-HN-01", "CAL-DN-01", "CAL-HL-01"]
    assert len(set(cal_ids) & set(primary_ids)) == 0, "Calibration scenario ID collides with primary scenarios!"


def test_ann_cal_02_disjoint_from_primary_pool() -> None:
    """ANN-CAL-02: calibration place IDs have zero intersection with primary candidate pool."""
    cal_path = os.path.join(ANNOTATION_DIR, "w5_calibration_v1.json")
    blinded_pool_path = os.path.join(EVAL_DIR, "w5_candidate_pool_blinded_v1.json")

    cal = json.load(open(cal_path, encoding="utf-8"))
    pool = json.load(open(blinded_pool_path, encoding="utf-8"))

    cal_pids = set(it["place_id"] for sc in cal["scenarios"] for it in sc["items"])
    pool_pids = set(it["place_id"] for sc in pool for it in sc["items"])

    assert len(cal_pids) == 45, f"Expected 45 unique calibration places, got {len(cal_pids)}"
    overlap = cal_pids & pool_pids
    assert len(overlap) == 0, f"Found place_id overlap between calibration and primary pool: {overlap}"


def test_ann_cal_03_excluded_from_final_metrics() -> None:
    """ANN-CAL-03: calibration excluded from final metrics and all labels null."""
    cal_path = os.path.join(ANNOTATION_DIR, "w5_calibration_v1.json")
    cal = json.load(open(cal_path, encoding="utf-8"))

    assert cal["track"] == "CALIBRATION_ONLY"
    assert cal["excluded_from_final_metrics"] is True
    assert cal["scenario_count"] == 3
    assert cal["total_items"] == 45

    destinations = [sc["destination"] for sc in cal["scenarios"]]
    assert destinations == ["ha-noi", "da-nang", "ha-long"]

    for sc in cal["scenarios"]:
        assert len(sc["items"]) == 15
        for it in sc["items"]:
            assert it["label"] is None
            assert it["judge_note"] is None
            assert "name" in it
            assert "category" in it
            assert "factual_context" in it


def test_ann_agg_01_median_cases() -> None:
    """ANN-AGG-01: median cases work for non-severe numeric disagreement (range < 2)."""
    test_cases = [
        (0, 0, 0, 0),
        (0, 0, 1, 0),
        (0, 1, 1, 1),
        (1, 1, 2, 1),
        (1, 2, 2, 2),
        (2, 2, 2, 2),
    ]
    for j1, j2, j3, expected_median in test_cases:
        res = aggregate_three_judgments(j1, j2, j3)
        assert res["final_relevance"] == expected_median
        assert res["provisional_median"] == expected_median
        assert res["severe_disagreement"] is False
        assert res["adjudication_required"] is False
        assert res["judgment_status"] == "RESOLVED_BY_MEDIAN"


def test_ann_agg_02_severe_disagreement_012() -> None:
    """ANN-AGG-02: [0, 1, 2] flags severe disagreement -> final_relevance is None."""
    res = aggregate_three_judgments(0, 1, 2)
    assert res["severe_disagreement"] is True
    assert res["adjudication_required"] is True
    assert res["judgment_status"] == "PENDING_ADJUDICATION"
    assert res["agreement_range"] == 2
    assert res["final_relevance"] is None
    assert res["provisional_median"] == 1


def test_ann_agg_03_severe_disagreement_002() -> None:
    """ANN-AGG-03: [0, 0, 2] flags severe disagreement -> final_relevance is None."""
    res = aggregate_three_judgments(0, 0, 2)
    assert res["severe_disagreement"] is True
    assert res["adjudication_required"] is True
    assert res["judgment_status"] == "PENDING_ADJUDICATION"
    assert res["agreement_range"] == 2
    assert res["final_relevance"] is None
    assert res["provisional_median"] == 0


def test_ann_agg_04_severe_disagreement_022() -> None:
    """ANN-AGG-04: [0, 2, 2] flags severe disagreement -> final_relevance is None."""
    res = aggregate_three_judgments(0, 2, 2)
    assert res["severe_disagreement"] is True
    assert res["adjudication_required"] is True
    assert res["judgment_status"] == "PENDING_ADJUDICATION"
    assert res["agreement_range"] == 2
    assert res["final_relevance"] is None
    assert res["provisional_median"] == 2


def test_ann_agg_05_severe_disagreement_permuted() -> None:
    """ANN-AGG-05: Order permutations of severe disagreement all yield None final_relevance."""
    for triple in [(2, 0, 1), (1, 2, 0), (2, 0, 0), (2, 2, 0)]:
        res = aggregate_three_judgments(*triple)
        assert res["severe_disagreement"] is True
        assert res["adjudication_required"] is True
        assert res["judgment_status"] == "PENDING_ADJUDICATION"
        assert res["final_relevance"] is None


def test_ann_na_01_na_never_converted_to_zero() -> None:
    """ANN-NA-01: [1, 1, 'NA'] -> final None, PENDING_EVIDENCE_ADJUDICATION."""
    res = aggregate_three_judgments(1, 1, "NA")
    assert res["final_relevance"] is None
    assert res["judgment_status"] == "PENDING_EVIDENCE_ADJUDICATION"
    assert res["adjudication_required"] is True
    assert res["severe_disagreement"] is False
    assert res["provisional_median"] is None


def test_ann_na_02_na_middle_no_median() -> None:
    """ANN-NA-02: [2, 'NA', 1] -> final None, no numeric median."""
    res = aggregate_three_judgments(2, "NA", 1)
    assert res["final_relevance"] is None
    assert res["judgment_status"] == "PENDING_EVIDENCE_ADJUDICATION"
    assert res["adjudication_required"] is True
    assert res["provisional_median"] is None


def test_ann_na_03_none_first_pending_evidence() -> None:
    """ANN-NA-03: [None, 1, 1] -> final None, PENDING_EVIDENCE_ADJUDICATION."""
    res = aggregate_three_judgments(None, 1, 1)
    assert res["final_relevance"] is None
    assert res["judgment_status"] == "PENDING_EVIDENCE_ADJUDICATION"
    assert res["adjudication_required"] is True
    assert res["provisional_median"] is None


MALFORMED_JUDGMENT_VALUES = [
    True,
    False,
    "0",
    "1",
    "2",
    1.0,
    1.5,
    2.0,
    -1,
    3,
    "bad",
    "INSUFFICIENT_EVIDENCE",
    [],
    {},
]


def test_ann_malformed_01_aggregate_three_judgments() -> None:
    """ANN-MALFORMED-01: aggregate_three_judgments strictly rejects malformed values."""
    for bad in MALFORMED_JUDGMENT_VALUES:
        with pytest.raises(ValueError):
            aggregate_three_judgments(bad, 1, 2)
        with pytest.raises(ValueError):
            aggregate_three_judgments(1, bad, 2)
        with pytest.raises(ValueError):
            aggregate_three_judgments(1, 2, bad)


def test_ann_malformed_02_krippendorff_alpha_ordinal() -> None:
    """ANN-MALFORMED-02: calculate_krippendorff_alpha_ordinal strictly rejects malformed values."""
    for bad in MALFORMED_JUDGMENT_VALUES:
        with pytest.raises(ValueError):
            calculate_krippendorff_alpha_ordinal([[bad, 1, 2], [0, 1, 2]])


def test_ann_malformed_03_krippendorff_alpha_ci() -> None:
    """ANN-MALFORMED-03: calculate_krippendorff_alpha_ci strictly rejects malformed values."""
    for bad in MALFORMED_JUDGMENT_VALUES:
        with pytest.raises(ValueError):
            calculate_krippendorff_alpha_ci([[bad, 1, 2], [0, 1, 2]], replicates=10)


def test_ann_malformed_04_compute_agreement_statistics() -> None:
    """ANN-MALFORMED-04: compute_agreement_statistics strictly rejects malformed values."""
    for bad in MALFORMED_JUDGMENT_VALUES:
        with pytest.raises(ValueError):
            compute_agreement_statistics([(bad, 1, 2), (0, 1, 2)])


def test_ann_malformed_05_validate_judgment_label() -> None:
    """ANN-MALFORMED-05: validate_judgment_label contract."""
    assert validate_judgment_label(0) == 0
    assert validate_judgment_label(1) == 1
    assert validate_judgment_label(2) == 2
    assert validate_judgment_label("NA") is None
    assert validate_judgment_label(None) is None
    for bad in MALFORMED_JUDGMENT_VALUES:
        with pytest.raises(ValueError):
            validate_judgment_label(bad)


def test_ann_alpha_01_perfect_agreement() -> None:
    """ANN-ALPHA-01: known synthetic perfect agreement -> alpha = 1."""
    synthetic_perfect = [
        [0, 0, 0],
        [1, 1, 1],
        [2, 2, 2],
        [0, 0, 0],
        [1, 1, 1],
        [2, 2, 2],
    ]
    alpha = calculate_krippendorff_alpha_ordinal(synthetic_perfect)
    assert alpha == 1.0
    assert interpret_reliability_gate(alpha) == "GOOD"


def test_ann_alpha_02_synthetic_disagreement() -> None:
    """ANN-ALPHA-02: synthetic disagreement produces alpha < 1."""
    synthetic_disagree = [
        [0, 2, 1],
        [2, 0, 1],
        [1, 2, 0],
        [0, 1, 2],
    ]
    alpha = calculate_krippendorff_alpha_ordinal(synthetic_disagree)
    assert alpha < 1.0


def test_ann_alpha_03_reference_fixture() -> None:
    """ANN-ALPHA-03: frozen hand-check/reference fixture yields ~0.6868."""
    fixture = [
        [0, 0, 1],
        [1, 1, 2],
        [2, 2, 2],
    ]
    alpha = calculate_krippendorff_alpha_ordinal(fixture)
    # Expected: approximately 0.6868
    assert abs(alpha - 0.6868) < 1e-3, f"Expected ~0.6868, got {alpha}"


def test_ann_alpha_04_bootstrap_ci_deterministic() -> None:
    """ANN-ALPHA-04: deterministic unit-level bootstrap CI on repeated runs."""
    fixture = [
        [0, 0, 1],
        [1, 1, 2],
        [2, 2, 2],
    ]
    ci1 = calculate_krippendorff_alpha_ci(fixture, replicates=1000, seed=20261013)
    ci2 = calculate_krippendorff_alpha_ci(fixture, replicates=1000, seed=20261013)

    assert ci1 == ci2, f"Bootstrap CI non-deterministic: {ci1} vs {ci2}"
    assert len(ci1) == 2
    assert ci1[0] <= ci1[1]


def test_ann_data_01_canonical_pool_unchanged() -> None:
    """ANN-DATA-01: canonical pool membership unchanged."""
    for fname, expected_hash in EXPECTED_W5_PREP_01_HASHES.items():
        path = os.path.join(EVAL_DIR, fname)
        assert os.path.exists(path), f"Missing {fname}"
        h = hashlib.sha256(open(path, "rb").read()).hexdigest()
        assert h == expected_hash, f"Hash mismatch for {fname}: got {h}, expected {expected_hash}"


def test_ann_data_02_freeze_v2_unchanged() -> None:
    """ANN-DATA-02: Freeze V2 unchanged."""
    assert os.path.exists(FREEZE_PATH), f"Missing freeze file {FREEZE_PATH}"
    freeze_hash = hashlib.sha256(open(FREEZE_PATH, "rb").read()).hexdigest()
    assert freeze_hash == "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444"
    # Confirm git diff for data/curated is empty
    res = subprocess.run(["git", "diff", "--", "data/curated/"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    assert res.stdout.strip() == "", "data/curated has uncommitted changes"

