"""Verification tests for W06-MEASUREMENT-AUDIT-01 (Freeze Current Planner Measurement Capability & Evidence Gaps)."""
import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_JSON_PATH = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_capability_audit_v1.json"
AUDIT_MD_PATH = REPO_ROOT / "docs" / "research" / "w06_measurement_capability_audit_v1.md"
FREEZE_V2_PATH = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
PLANNER_DIR = REPO_ROOT / "data" / "evaluation" / "planner"
EVALUATOR_PATH = PLANNER_DIR / "evaluate_planner.py"
PLANNER_ROUTER_PATH = REPO_ROOT / "apps" / "ai-service" / "app" / "routers" / "planner.py"
PLANNER_SCHEMA_PATH = REPO_ROOT / "apps" / "ai-service" / "app" / "schemas" / "planner.py"
SYNTHETIC_PREFS_PATH = REPO_ROOT / "data" / "evaluation" / "synthetic" / "preferences_n300_seed42.json"
SYNTHETIC_PREFS_JSONL_PATH = REPO_ROOT / "data" / "research" / "preferences" / "synthetic_preferences_v1.jsonl"
ROADMAP_PATH = REPO_ROOT / "docs" / "roadmap" / "gomate-thesis-research-roadmap-v1.md"

EXPECTED_BASE_DEVELOP_SHA = "4de240aeaa5277420695ed5f1de85f7b67cd6c54"
ALLOWED_STATUSES = {"SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_EVALUABLE", "UNKNOWN"}
REQUIRED_MATRIX_ROWS = [
    "CATALOG_GROUNDING",
    "NO_DUPLICATE_POI",
    "DESTINATION_CORRECTNESS",
    "CATEGORY_DIVERSITY",
    "GEO_DISTANCE",
    "TRAVEL_TIME",
    "OPENING_HOURS",
    "SCHEDULE_OVERLAP",
    "BUDGET",
    "PREFERENCE_SATISFACTION",
    "REPRODUCIBILITY",
    "MOCK_RUN_DETECTION",
]


@pytest.fixture(scope="module")
def audit_doc() -> dict:
    assert AUDIT_JSON_PATH.exists(), f"Missing audit JSON: {AUDIT_JSON_PATH}"
    assert AUDIT_MD_PATH.exists(), f"Missing audit MD: {AUDIT_MD_PATH}"
    return json.loads(AUDIT_JSON_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def freeze_v2_places() -> list[dict]:
    return json.loads(FREEZE_V2_PATH.read_text(encoding="utf-8"))


def test_w06_audit_01_base_commit_recorded_correctly(audit_doc: dict):
    """W06-AUDIT-01: base commit recorded correctly."""
    assert audit_doc["audit_id"] == "W06-MEASUREMENT-AUDIT-01"
    assert audit_doc["base_develop_sha"] == EXPECTED_BASE_DEVELOP_SHA
    assert EXPECTED_BASE_DEVELOP_SHA in AUDIT_MD_PATH.read_text(encoding="utf-8")


def test_w06_audit_02_no_scientific_benchmark_result_claimed(audit_doc: dict):
    """W06-AUDIT-02: no scientific benchmark result is claimed."""
    assert audit_doc["scientific_results_generated"] is False
    assert audit_doc["preregistration_created"] is False
    assert audit_doc["repository_mutation_scope"] == "AUDIT_ARTIFACTS_AND_TESTS_ONLY"
    validity = audit_doc["current_instrument_validity"]
    assert validity["can_current_evaluator_produce_a_scientific_w06_pass_rate"] == "NO"


def _ensure_commit_present(commit_sha: str) -> None:
    res = subprocess.run(
        ["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if res.returncode != 0:
        subprocess.run(
            ["git", "fetch", "origin", commit_sha, "--depth=1"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )


def test_w06_audit_03_no_planner_behavior_modified(audit_doc: dict):
    """W06-AUDIT-03: no planner behavior is modified relative to base develop SHA."""
    assert audit_doc["planner_behavior_modified"] is False
    _ensure_commit_present(EXPECTED_BASE_DEVELOP_SHA)
    res = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            EXPECTED_BASE_DEVELOP_SHA,
            "--",
            "apps/ai-service/app/routers/planner.py",
            "apps/ai-service/app/schemas/planner.py",
            "apps/ai-service/app/prompts/planner_prompt.py",
            "apps/ai-service/app/config.py",
            "apps/backend/src/modules/trips/trips.service.ts",
            "apps/backend/src/modules/ai-proxy/ai-proxy.service.ts",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""


def test_w06_audit_04_no_evaluator_or_scenario_behavior_modified(audit_doc: dict):
    """W06-AUDIT-04: no evaluator or scenario behavior is modified relative to base develop SHA."""
    assert audit_doc["evaluator_behavior_modified"] is False
    assert audit_doc["scenarios_modified"] is False
    _ensure_commit_present(EXPECTED_BASE_DEVELOP_SHA)
    res = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            EXPECTED_BASE_DEVELOP_SHA,
            "--",
            "data/evaluation/planner/",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""


def test_w06_audit_05_scenario_inventory_matches_repository(audit_doc: dict):
    """W06-AUDIT-05: scenario inventory matches repository."""
    scenario_files = sorted(PLANNER_DIR.glob("*.json"))
    sc_audit = audit_doc["scenario_audit"]
    assert sc_audit["current_scenario_count"] == len(scenario_files) == 3

    actual_by_id = {}
    for sf in scenario_files:
        raw = json.loads(sf.read_text(encoding="utf-8"))
        actual_by_id[raw["scenario_id"]] = (sf.relative_to(REPO_ROOT).as_posix(), raw)

    recorded_by_id = {s["scenario_id"]: s for s in sc_audit["scenarios"]}
    assert set(recorded_by_id.keys()) == set(actual_by_id.keys()) == {
        "eval_da_nang_4d",
        "eval_ha_giang_3d",
        "eval_moc_chau_3d",
    }

    for sc_id, (rel_path, raw) in actual_by_id.items():
        rec = recorded_by_id[sc_id]
        assert rec["file_path"] == rel_path
        assert rec["destination"] == raw["request"]["destination"]
        assert rec["number_of_days"] == raw["request"]["days"]
        assert rec["expected_constraints"] == raw["expected_constraints"]

    assert recorded_by_id["eval_da_nang_4d"]["grounding_scope"] == "SUPPORTED"
    assert recorded_by_id["eval_ha_giang_3d"]["grounding_scope"] == "OUT_OF_CATALOG_SCOPE"
    assert recorded_by_id["eval_moc_chau_3d"]["grounding_scope"] == "OUT_OF_CATALOG_SCOPE"


def test_w06_audit_06_catalog_destination_counts_reproducible(audit_doc: dict, freeze_v2_places: list[dict]):
    """W06-AUDIT-06: catalog destination counts are reproducible."""
    cat = audit_doc["catalog_data_capability_audit"]
    core_places = [p for p in freeze_v2_places if p.get("is_rec_a_core_v2") is True]
    non_core_places = [p for p in freeze_v2_places if not p.get("is_rec_a_core_v2")]

    assert cat["total_pois"] == len(freeze_v2_places) == 759
    assert cat["core_pois"] == len(core_places) == 622
    assert cat["non_core_secondary_pois"] == len(non_core_places) == 137

    total_by_slug = Counter(p["destination_slug"] for p in freeze_v2_places)
    core_by_slug = Counter(p["destination_slug"] for p in core_places)
    non_core_by_slug = Counter(p["destination_slug"] for p in non_core_places)

    for slug, entry in cat["by_destination_counts"].items():
        assert entry["total_pois"] == total_by_slug[slug]
        assert entry["rec_a_core_pois"] == core_by_slug[slug]
        assert entry["non_core_pois"] == non_core_by_slug[slug]

    dn_split = cat["da_nang_split_verified"]
    assert dn_split["rec_a_core_count"] == core_by_slug["da-nang"] == 289
    assert dn_split["non_core_count"] == non_core_by_slug["da-nang"] == 4
    assert dn_split["all_destination_map_count"] == total_by_slug["da-nang"] == 293
    assert dn_split["matches_289_plus_4_equals_293"] is True


def test_w06_audit_07_opening_hours_coverage_reproducible(audit_doc: dict, freeze_v2_places: list[dict]):
    """W06-AUDIT-07: opening-hours coverage is reproducible."""
    cat = audit_doc["catalog_data_capability_audit"]
    oh = cat["opening_hours"]
    core_places = [p for p in freeze_v2_places if p.get("is_rec_a_core_v2") is True]

    all_with_oh = [p for p in freeze_v2_places if p.get("opening_hours")]
    core_with_oh = [p for p in core_places if p.get("opening_hours")]

    assert oh["all_pois_count"] == len(all_with_oh) == 101
    assert oh["core_pois_count"] == len(core_with_oh) == 101
    assert oh["all_pois_pct"] == round(len(all_with_oh) / len(freeze_v2_places) * 100, 2)
    assert oh["core_pois_pct"] == round(len(core_with_oh) / len(core_places) * 100, 2)
    assert oh["parser_exists"] is False

    oh_by_dest = Counter(p["destination_slug"] for p in all_with_oh)
    for slug, count in oh["by_destination"].items():
        assert count == oh_by_dest.get(slug, 0)


def test_w06_audit_08_numeric_price_evidence_reproducible(audit_doc: dict, freeze_v2_places: list[dict]):
    """W06-AUDIT-08: numeric-price, fee, and charge tag evidence is reproducible."""
    cat = audit_doc["catalog_data_capability_audit"]
    core_places = [p for p in freeze_v2_places if p.get("is_rec_a_core_v2") is True]

    structured_price_count = sum(
        1 for p in freeze_v2_places if p.get("price_min") is not None or p.get("price_max") is not None
    )
    assert cat["numeric_price"]["structured_price_min_max_in_freeze_v2_count"] == structured_price_count == 0

    def extract_tag_places(subset: list[dict], tag_key: str) -> dict[str, str]:
        found = {}
        for p in subset:
            for s in p.get("sources", []):
                rd = s.get("raw_data") or {}
                tags = rd.get("tags") if isinstance(rd.get("tags"), dict) else rd
                if isinstance(tags, dict) and tag_key in tags:
                    found[p["place_id"]] = str(tags[tag_key])
        return found

    all_fee = extract_tag_places(freeze_v2_places, "fee")
    core_fee = extract_tag_places(core_places, "fee")
    all_charge = extract_tag_places(freeze_v2_places, "charge")
    core_charge = extract_tag_places(core_places, "charge")

    assert cat["fee_tag"]["all_pois_count"] == len(all_fee) == 23
    assert cat["fee_tag"]["core_pois_count"] == len(core_fee) == 12
    assert cat["charge_tag"]["all_pois_count"] == len(all_charge) == 6
    assert cat["charge_tag"]["core_pois_count"] == len(core_charge) == 4


def test_w06_audit_09_preference_synthetic_and_real_counts_reproducible(audit_doc: dict):
    """W06-AUDIT-09: preference synthetic/real counts are reproducible."""
    pref_audit = audit_doc["preference_evidence_audit"]
    prefs_json = json.loads(SYNTHETIC_PREFS_PATH.read_text(encoding="utf-8"))
    prefs_jsonl = [
        json.loads(line)
        for line in SYNTHETIC_PREFS_JSONL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(prefs_json) == len(prefs_jsonl) == 300
    syn_count = sum(1 for r in prefs_json if r.get("isSynthetic") is True)
    real_count = sum(1 for r in prefs_json if not r.get("isSynthetic"))

    assert pref_audit["preference_records_total"] == len(prefs_json) == 300
    assert pref_audit["preference_records_marked_synthetic"] == syn_count == 300
    assert pref_audit["preference_records_verified_real_user"] == real_count == 0
    assert pref_audit["preference_ground_truth_status"] == "NO_REAL_USER_GT_AVAILABLE"


def test_w06_audit_10_measurement_capability_statuses_use_allowed_vocabulary(audit_doc: dict):
    """W06-AUDIT-10: measurement capability statuses use only SUPPORTED / PARTIALLY_SUPPORTED / NOT_EVALUABLE / UNKNOWN."""
    matrix = audit_doc["measurement_capability_matrix"]
    assert list(matrix.keys()) == REQUIRED_MATRIX_ROWS
    for row_key, row_val in matrix.items():
        assert row_val["status"] in ALLOWED_STATUSES, f"Invalid status on {row_key}: {row_val['status']}"
        for col in ("status", "evidence", "blocking_gap", "safe_interpretation"):
            assert col in row_val and isinstance(row_val[col], str) and row_val[col].strip()


def test_w06_audit_11_haversine_lat_lng_not_labeled_travel_time(audit_doc: dict):
    """W06-AUDIT-11: Haversine/lat-lng measurement is labeled GEO_DISTANCE_PROXY and not travel time."""
    matrix = audit_doc["measurement_capability_matrix"]
    geo_row = matrix["GEO_DISTANCE"]
    travel_row = matrix["TRAVEL_TIME"]

    assert "GEO_DISTANCE_PROXY" in geo_row["evidence"] or "GEO_DISTANCE_PROXY" in geo_row["safe_interpretation"]
    assert travel_row["status"] == "NOT_EVALUABLE"
    assert "GEO_DISTANCE_PROXY" in travel_row["safe_interpretation"]
    assert audit_doc["catalog_data_capability_audit"]["routing_or_travel_time_data"]["exists"] is False


def test_w06_audit_12_mock_fallback_path_documented(audit_doc: dict):
    """W06-AUDIT-12: mock/fallback path is documented and matches planner.py & schema."""
    model_audit = audit_doc["model_and_reproducibility_audit"]
    mock_info = model_audit["mock_or_fallback_behavior"]
    assert mock_info["exists"] is True
    assert mock_info["can_response_schema_distinguish_real_vs_mock_run"] is False

    planner_src = PLANNER_ROUTER_PATH.read_text(encoding="utf-8")
    assert "_client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None" in planner_src
    assert "# Fallback mock for testing when no Gemini key is present" in planner_src

    schema_src = PLANNER_SCHEMA_PATH.read_text(encoding="utf-8")
    assert "place_id" not in schema_src


def test_w06_audit_13_100_scenario_claim_is_repo_evidenced_or_unsupported(audit_doc: dict):
    """W06-AUDIT-13: 100-scenario claim is either repo-evidenced or explicitly UNSUPPORTED_EXTERNAL_CLAIM."""
    claim_audit = audit_doc["roadmap_100_scenario_claim_audit"]
    assert claim_audit["claim_status"] in {
        "REPO_CONFIRMED_100_SCENARIO_REQUIREMENT",
        "NO_AUTHORITATIVE_100_SCENARIO_REQUIREMENT_FOUND",
    }
    assert claim_audit["claim_status"] == "REPO_CONFIRMED_100_SCENARIO_REQUIREMENT"
    roadmap_text = ROADMAP_PATH.read_text(encoding="utf-8")
    assert "Empirically evaluate the Gemini itinerary planning agent across 100 test prompts" in roadmap_text
    assert "Evaluation of Gemini itinerary planner over 100 benchmark trips" in roadmap_text
    assert claim_audit["implementation_reality"]["current_scenario_files_in_repo"] == 3
