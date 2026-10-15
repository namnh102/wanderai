"""Adversarial Validation & Scientific Hardening Gate Tests (W06-INSTRUMENT-VALIDATION-01).

Covers W06-VAL-01 through W06-VAL-44 across Sections 3–27:
- Follow-up Note A resolution: core_scenario_pass_rate_all_assigned vs core_scenario_pass_rate_all_100 (null outside FINAL_100).
- Follow-up Note B resolution: future P11 assignment manifest schema, per-scenario 64-char lowercase hex scenario_sha256, and Policy A canonical byte enforcement.
- Adversarial evidence integrity tampering (scenario, parsed response, catalog, forged manifest SHAs, invalid run statuses, missing metadata).
- Adversarial grounding, destination, duplicate POI, zero POI_VISIT, and TRANSIT_ONLY anti-gaming cases.
- Adversarial schedule, HH:MM format, interval direction, intra-day vs cross-day overlap, and date alignment cases.
- Adversarial budget cases including budget=0 (compliant and violation without divide-by-zero or arbitrary 1.0) and arithmetic inconsistencies.
- Adversarial opening-hours 3-state semantics and exact 622/101/73/91/10 parser corpus reproduction.
- Exhaustive final core_scenario_pass truth table.
- Invalid-run denominator retention (N=100) and non-final denominator name safety (N=3).
- Count-based grounding aggregation vs mean-of-means, cluster bootstrap edge cases, Wilson CI edge cases, per-destination & equal-destination macro edge cases, FINAL_100 fail-closed rules, byte-level determinism, and production/scientific boundary isolation.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

import pytest
from pydantic import ValidationError

AI_SERVICE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = AI_SERVICE_ROOT.parent.parent
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.evaluation.opening_hours_evaluator import (  # noqa: E402
    OPENING_HOURS_PARSER_VERSION,
    build_opening_hours_parser_coverage_report,
    evaluate_poi_visit_opening_hours,
    parse_osm_opening_hours,
)
from app.evaluation.planner_benchmark_aggregator import (  # noqa: E402
    AGGREGATOR_VERSION,
    ASSIGNMENT_MANIFEST_CANONICAL_POLICY,
    ASSIGNMENT_MANIFEST_HASH_BASIS,
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    AssignedScenarioSpec,
    BenchmarkAssignmentManifest,
    aggregate_benchmark_evaluations,
    aggregate_evaluations_from_disk,
    canonicalize_assignment_manifest_bytes,
    compute_assignment_manifest_sha256,
    compute_scenario_cluster_bootstrap_grounding_ci95,
    compute_wilson_ci95,
    load_and_validate_assignment_manifest_bytes,
)
from app.evaluation.planner_benchmark_evaluator import (  # noqa: E402
    EVALUATOR_VERSION,
    ScenarioEvaluationResult,
    compute_catalog_sha256,
    evaluate_benchmark_scenario,
    evaluate_run_directory,
)
from app.schemas.planner_benchmark import (  # noqa: E402
    HASH_BASIS_VERSION,
    ActivityKind,
    BenchmarkBudgetAnalysis,
    BenchmarkCatalogPOI,
    BenchmarkItineraryDay,
    BenchmarkItineraryItem,
    BenchmarkPlanResponse,
    BenchmarkRunManifest,
    BenchmarkRunStatus,
    BenchmarkScenarioInput,
    BenchmarkUsageMetadata,
)
from app.services.planner_benchmark_runner import (  # noqa: E402
    MEASUREMENT_CONTRACT_SOURCE_COMMIT,
    canonical_json_bytes,
    sha256_bytes,
    write_canonical_json,
)

COVERAGE_01C_JSON_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_opening_hours_parser_coverage_v1.json"
)
VALIDATION_RECEIPT_JSON_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_instrument_validation_01_receipt_v1.json"
)
VALIDATION_DOC_MD_PATH = (
    REPO_ROOT / "docs" / "research" / "w06_instrument_validation_01_v1.md"
)
CONTRACT_JSON_PATH = (
    REPO_ROOT / "data" / "evaluation" / "w06" / "w06_measurement_contract_v1.json"
)
PLANNER_EVAL_DIR = REPO_ROOT / "data" / "evaluation" / "planner"


def _make_validation_catalog() -> Dict[str, BenchmarkCatalogPOI]:
    """Build deterministic catalog fixtures across ha-noi, da-nang, ha-long."""
    entries = [
        BenchmarkCatalogPOI(
            place_id="poi_dn_247",
            name="Cầu Rồng Đà Nẵng",
            category="attraction",
            destination_slug="da-nang",
            lat=16.0611,
            lng=108.2275,
            opening_hours="24/7",
        ),
        BenchmarkCatalogPOI(
            place_id="poi_dn_weekday",
            name="Bảo tàng Điêu khắc Chăm",
            category="museum",
            destination_slug="da-nang",
            lat=16.0604,
            lng=108.2230,
            opening_hours="Tu-Su 07:30-17:00; Mo off",
        ),
        BenchmarkCatalogPOI(
            place_id="poi_dn_missing_oh",
            name="Bãi biển Mỹ Khê",
            category="beach",
            destination_slug="da-nang",
            lat=16.0598,
            lng=108.2456,
            opening_hours=None,
        ),
        BenchmarkCatalogPOI(
            place_id="poi_dn_cross_midnight",
            name="Chợ Đêm Sơn Trà",
            category="night_market",
            destination_slug="da-nang",
            lat=16.0615,
            lng=108.2300,
            opening_hours="Mo-Su 18:00-02:00",
        ),
        BenchmarkCatalogPOI(
            place_id="poi_hn_247",
            name="Hồ Hoàn Kiếm",
            category="attraction",
            destination_slug="ha-noi",
            lat=21.0285,
            lng=105.8525,
            opening_hours="24/7",
        ),
        BenchmarkCatalogPOI(
            place_id="poi_hl_247",
            name="Vịnh Hạ Long",
            category="nature",
            destination_slug="ha-long",
            lat=20.9101,
            lng=107.1839,
            opening_hours="24/7",
        ),
    ]
    for dest in ("ha-noi", "da-nang", "ha-long"):
        for idx in range(1, 12):
            pid = f"poi_{dest}_{idx}"
            entries.append(
                BenchmarkCatalogPOI(
                    place_id=pid,
                    name=f"Địa điểm {dest} {idx}",
                    category="culture_history",
                    destination_slug=dest,
                    lat=16.0 + idx * 0.002,
                    lng=108.0 + idx * 0.002,
                    opening_hours="08:00-20:00",
                )
            )
    return {e.place_id: e for e in entries}


def _make_scenario(
    *,
    scenario_id: str = "VAL_SCEN_01",
    destination_slug: str = "da-nang",
    days: int = 1,
    start_date: str = "2026-07-07",
    end_date: Optional[str] = None,
    budget: Optional[int] = 1000000,
    allow_revisit_place_ids: bool = False,
) -> BenchmarkScenarioInput:
    dest_names = {"da-nang": "Đà Nẵng", "ha-noi": "Hà Nội", "ha-long": "Hạ Long"}
    if end_date is None:
        base_day = int(start_date.split("-")[2])
        end_date = f"{start_date[:8]}{base_day + days - 1:02d}"
    return BenchmarkScenarioInput(
        scenario_id=scenario_id,
        destination_slug=destination_slug,
        destination=dest_names[destination_slug],
        days=days,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        currency="VND",
        travel_style="solo",
        interests=["culture_history", "food_cuisine"],
        allow_revisit_place_ids=allow_revisit_place_ids,
    )


def _make_poi_item(
    order_index: int,
    start_time: str,
    end_time: str,
    place_id: str,
    place_name: str = "Địa điểm",
    estimated_cost: int = 100000,
) -> BenchmarkItineraryItem:
    return BenchmarkItineraryItem(
        order_index=order_index,
        start_time=start_time,
        end_time=end_time,
        activity_kind=ActivityKind.POI_VISIT,
        activity=f"Tham quan {place_name}",
        place_name=place_name,
        place_id=place_id,
        notes="Ghi chú",
        estimated_cost=estimated_cost,
        transport_mode="taxi",
    )


def _make_transit_item(
    order_index: int,
    start_time: str,
    end_time: str,
    place_name: Optional[str] = None,
    estimated_cost: int = 50000,
) -> BenchmarkItineraryItem:
    return BenchmarkItineraryItem(
        order_index=order_index,
        start_time=start_time,
        end_time=end_time,
        activity_kind=ActivityKind.TRANSIT_ONLY,
        activity="Di chuyển",
        place_name=place_name,
        place_id=None,
        notes="Di chuyển",
        estimated_cost=estimated_cost,
        transport_mode="taxi",
    )


def _make_plan_and_manifest(
    scenario: BenchmarkScenarioInput,
    days: List[BenchmarkItineraryDay],
    *,
    run_status: BenchmarkRunStatus = BenchmarkRunStatus.VALID,
    reported_estimated_cost: Optional[int] = None,
    total_days_override: Optional[int] = None,
    model_id: str = "gemini-3.5-flash",
    expected_model_id: str = "gemini-3.5-flash",
) -> Tuple[BenchmarkPlanResponse, BenchmarkRunManifest]:
    total_cost = (
        reported_estimated_cost
        if reported_estimated_cost is not None
        else sum(d.day_cost for d in days)
    )
    plan = BenchmarkPlanResponse(
        plan_id=f"plan_{scenario.scenario_id}",
        scenario_id=scenario.scenario_id,
        destination_slug=scenario.destination_slug,
        destination=scenario.destination,
        total_days=total_days_override if total_days_override is not None else len(days),
        overview="Lịch trình kiểm thử đối kháng W06.",
        best_time_to_visit="Tháng 3 - Tháng 8",
        general_tips=["Mang nước"],
        budget_analysis=BenchmarkBudgetAnalysis(
            total_budget=scenario.budget,
            estimated_cost=total_cost,
            currency="VND",
            is_over_budget=(
                total_cost > scenario.budget if scenario.budget is not None else False
            ),
            variance=(
                (scenario.budget - total_cost) if scenario.budget is not None else 0
            ),
        ),
        days=days,
    )
    scen_sha = sha256_bytes(canonical_json_bytes(scenario.model_dump()))
    parsed_sha = (
        sha256_bytes(canonical_json_bytes(plan.model_dump()))
        if run_status == BenchmarkRunStatus.VALID
        else None
    )
    cat_sha = compute_catalog_sha256()
    manifest = BenchmarkRunManifest(
        run_id=f"run_{scenario.scenario_id}",
        scenario_id=scenario.scenario_id,
        execution_timestamp_utc="2026-10-15T00:00:00Z",
        provider="google-genai",
        model_id=model_id,
        expected_model_id=expected_model_id,
        generation_parameters={"temperature": 0.0},
        execution_mode="LIVE_PROVIDER",
        latency_ms=100.0,
        usage_metadata=BenchmarkUsageMetadata(
            input_tokens=500, output_tokens=200, total_tokens=700
        ),
        code_commit_sha="8d599bd8fe1a167a64c375c43148928daeb94dca",
        scenario_sha256=scen_sha,
        catalog_sha256=cat_sha,
        benchmark_prompt_version="W06-BENCHMARK-PROMPT-01A-V1",
        raw_response_sha256=hashlib.sha256(b"raw").hexdigest(),
        parsed_response_sha256=parsed_sha,
        run_status=run_status,
    )
    return plan, manifest


def _build_batch_scenario_eval(
    scenario_id: str,
    destination_slug: str,
    *,
    run_status: BenchmarkRunStatus = BenchmarkRunStatus.VALID,
    budget: Optional[int] = 500000,
    item_cost: int = 100000,
    schedule_overlap: bool = False,
    grounded_count: int = 2,
    ungrounded_count: int = 0,
    oh_violation: bool = False,
    zero_poi_visits: bool = False,
) -> Tuple[AssignedScenarioSpec, ScenarioEvaluationResult]:
    cat = _make_validation_catalog()
    start_date = "2026-07-06" if oh_violation else "2026-07-07"
    scenario = _make_scenario(
        scenario_id=scenario_id,
        destination_slug=destination_slug,
        days=1,
        start_date=start_date,
        budget=budget,
    )

    items: List[BenchmarkItineraryItem] = []
    idx = 1
    if zero_poi_visits:
        items.append(_make_transit_item(1, "09:00", "10:00", place_name=None, estimated_cost=item_cost))
    else:
        for g in range(grounded_count):
            pid = (
                "poi_dn_weekday"
                if (oh_violation and g == 0 and destination_slug == "da-nang")
                else f"poi_{destination_slug}_{g + 1}"
            )
            s_t = "09:00" if (schedule_overlap and idx <= 2) else f"{7 + idx:02d}:00"
            e_t = "10:30" if (schedule_overlap and idx <= 2) else f"{7 + idx:02d}:45"
            items.append(_make_poi_item(idx, s_t, e_t, pid, f"Place {idx}", item_cost))
            idx += 1

        for u in range(ungrounded_count):
            items.append(
                _make_poi_item(
                    idx,
                    f"{18 + u:02d}:00",
                    f"{18 + u:02d}:45",
                    f"fake_ungrounded_{u}",
                    "Fake Place",
                    item_cost,
                )
            )
            idx += 1

    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date=start_date,
            title="Ngày 1",
            items=items,
            day_cost=sum(i.estimated_cost for i in items),
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days, run_status=run_status)
    ev = evaluate_benchmark_scenario(
        scenario,
        plan if run_status == BenchmarkRunStatus.VALID else None,
        manifest,
        core_catalog_by_id=cat,
        verify_hashes=(run_status == BenchmarkRunStatus.VALID),
    )
    spec = AssignedScenarioSpec(
        scenario_id=scenario_id,
        destination_slug=destination_slug,
        scenario_sha256=ev.scenario_sha256,
    )
    return spec, ev


def _build_synthetic_100_batch(
    *,
    invalid_count: int = 0,
    violation_count: int = 0,
) -> Tuple[BenchmarkAssignmentManifest, List[ScenarioEvaluationResult]]:
    specs: List[AssignedScenarioSpec] = []
    evals: List[ScenarioEvaluationResult] = []
    allocations = [("ha-noi", 34), ("da-nang", 33), ("ha-long", 33)]
    idx = 0
    for dest, count in allocations:
        for j in range(count):
            sid = f"SYNTH_VAL_100_{dest}_{j + 1:02d}"
            is_invalid = idx < invalid_count
            is_viol = (not is_invalid) and (idx < invalid_count + violation_count)
            spec, ev = _build_batch_scenario_eval(
                sid,
                dest,
                run_status=(
                    BenchmarkRunStatus.API_ERROR
                    if is_invalid
                    else BenchmarkRunStatus.VALID
                ),
                schedule_overlap=is_viol,
            )
            specs.append(spec)
            evals.append(ev)
            idx += 1

    manifest = BenchmarkAssignmentManifest(
        manifest_id="SYNTHETIC_VAL_100_MANIFEST",
        manifest_version="1.0.0",
        is_final_100_frozen=True,
        assigned_scenarios=specs,
    )
    return manifest, evals


# ==============================================================================
# SECTIONS 3, 13, 14 — FOLLOW-UP NOTE A & DENOMINATOR NAME SAFETY
# ==============================================================================


def test_w06_val_01_followup_note_a_nonfinal_n3_pass_rate_all_assigned_and_null_all_100():
    """W06-VAL-01: non-final N=3 (2 pass, 1 fail) populates core_scenario_pass_rate_all_assigned=2/3 and nulls _all_100."""
    s1, e1 = _build_batch_scenario_eval("val_n3_1", "ha-noi")
    s2, e2 = _build_batch_scenario_eval("val_n3_2", "da-nang")
    s3, e3 = _build_batch_scenario_eval("val_n3_3", "ha-long", schedule_overlap=True)

    manifest = BenchmarkAssignmentManifest(
        manifest_id="SYNTHETIC_N3_NONFINAL",
        is_final_100_frozen=False,
        assigned_scenarios=[s1, s2, s3],
    )
    agg = aggregate_benchmark_evaluations(manifest, [e1, e2, e3], final_100_mode=False)

    assert agg.final_100_mode is False
    assert agg.assigned_scenario_count == 3
    assert agg.core_scenario_pass_count == 2
    assert agg.core_scenario_pass_rate_all_assigned == round(2 / 3, 6)
    assert agg.core_scenario_pass_rate_all_assigned_ci95.k == 2
    assert agg.core_scenario_pass_rate_all_assigned_ci95.n == 3
    assert agg.core_scenario_pass_rate_all_100 is None
    assert agg.core_scenario_pass_rate_all_100_ci95 is None
    assert agg.core_scenario_pass_rate_all_100_status == "NOT_APPLICABLE_NON_FINAL_100_MODE"


def test_w06_val_02_followup_note_a_final_100_populates_both_assigned_and_all_100():
    """W06-VAL-02: FINAL_100 N=100 (80 valid pass, 20 invalid) keeps invalid runs in denominator (0.80) and conditional=1.0."""
    manifest, evals = _build_synthetic_100_batch(invalid_count=20, violation_count=0)
    agg = aggregate_benchmark_evaluations(manifest, evals, final_100_mode=True)

    assert agg.final_100_mode is True
    assert agg.assigned_scenario_count == 100
    assert agg.valid_run_count == 80
    assert agg.invalid_run_count == 20
    assert agg.valid_run_rate == 0.80
    assert agg.core_scenario_pass_count == 80
    assert agg.core_scenario_pass_rate_all_assigned == 0.80
    assert agg.core_scenario_pass_rate_all_assigned_ci95.n == 100
    assert agg.core_scenario_pass_rate_all_100 == 0.80
    assert agg.core_scenario_pass_rate_all_100_ci95 is not None
    assert agg.core_scenario_pass_rate_all_100_ci95.k == 80
    assert agg.core_scenario_pass_rate_all_100_ci95.n == 100
    assert agg.core_scenario_pass_rate_all_100_status == "FINAL_100_PRIMARY_METRIC"
    assert agg.conditional_core_pass_rate_on_valid_runs == 1.0


# ==============================================================================
# SECTIONS 4, 5, 20 — FOLLOW-UP NOTE B & MANIFEST CANONICAL HASH / TAMPERING
# ==============================================================================


def test_w06_val_03_followup_note_b_future_p11_manifest_requires_hash_basis_and_scenario_sha256():
    """W06-VAL-03: FINAL_100 manifest enforces hash_basis_version, assignment_manifest_hash_basis, and per-scenario SHA256."""
    manifest, evals = _build_synthetic_100_batch()
    assert manifest.is_final_100_frozen is True
    assert manifest.hash_basis_version == HASH_BASIS_VERSION == "W06-ARTIFACT-HASH-BASIS-V1"
    assert (
        manifest.assignment_manifest_hash_basis
        == ASSIGNMENT_MANIFEST_HASH_BASIS
        == "SHA256_CANONICAL_JSON_UTF8_LF_BYTES"
    )
    assert len(manifest.assigned_scenarios) == 100
    for spec in manifest.assigned_scenarios:
        assert spec.scenario_sha256 is not None
        assert len(spec.scenario_sha256) == 64
        assert spec.scenario_sha256 == spec.scenario_sha256.lower()

    # If is_final_100_frozen is False when final_100_mode=True is requested, reject
    unfrozen = manifest.model_copy(update={"is_final_100_frozen": False})
    with pytest.raises(ValueError, match="is_final_100_frozen == True"):
        aggregate_benchmark_evaluations(unfrozen, evals, final_100_mode=True)


def test_w06_val_04_followup_note_b_rejects_missing_malformed_or_uppercase_scenario_sha256():
    """W06-VAL-04: rejects missing scenario_sha256 in FINAL_100, malformed hex, or uppercase SHA256."""
    with pytest.raises(ValidationError, match="64 lowercase hexadecimal"):
        AssignedScenarioSpec(
            scenario_id="s_bad_len",
            destination_slug="da-nang",
            scenario_sha256="abc123",
        )

    uppercase_sha = "A" * 64
    with pytest.raises(ValidationError, match="64 lowercase hexadecimal"):
        AssignedScenarioSpec(
            scenario_id="s_upper",
            destination_slug="da-nang",
            scenario_sha256=uppercase_sha,
        )

    manifest, evals = _build_synthetic_100_batch()
    # Mutate scenario_sha256 to None in place and verify FINAL_100 validation rejects it
    manifest.assigned_scenarios[0].scenario_sha256 = None
    with pytest.raises(ValueError, match="scenario_sha256"):
        aggregate_benchmark_evaluations(manifest, evals, final_100_mode=True)


def test_w06_val_05_assignment_manifest_canonical_hash_and_policy_a_rejection(tmp_path: Path):
    """W06-VAL-05: canonical manifest hash changes on tampering and rejects non-canonical JSON in FINAL_100 under Policy A."""
    manifest, evals = _build_synthetic_100_batch()
    canonical_bytes = canonicalize_assignment_manifest_bytes(manifest)
    sha_orig = compute_assignment_manifest_sha256(manifest)
    assert sha_orig == sha256_bytes(canonical_bytes)
    assert canonical_bytes.endswith(b"\n")
    assert not canonical_bytes.endswith(b"\n\n")

    # Tamper one scenario destination => hash changes
    tampered_dest_manifest = copy.deepcopy(manifest)
    tampered_dest_manifest.assigned_scenarios[0].destination_slug = "da-nang"
    assert compute_assignment_manifest_sha256(tampered_dest_manifest) != sha_orig

    # Tamper one scenario SHA => hash changes
    tampered_sha_manifest = copy.deepcopy(manifest)
    tampered_sha_manifest.assigned_scenarios[0].scenario_sha256 = "f" * 64
    assert compute_assignment_manifest_sha256(tampered_sha_manifest) != sha_orig

    # Reorder JSON keys / non-canonical formatting => rejected under Policy A in FINAL_100 mode
    raw_dict = json.loads(canonical_bytes.decode("utf-8"))
    reordered_dict = {
        "assigned_scenarios": raw_dict["assigned_scenarios"],
        "manifest_id": raw_dict["manifest_id"],
        "manifest_version": raw_dict["manifest_version"],
        "is_final_100_frozen": raw_dict["is_final_100_frozen"],
        "hash_basis_version": raw_dict["hash_basis_version"],
        "assignment_manifest_hash_basis": raw_dict["assignment_manifest_hash_basis"],
    }
    non_canonical_bytes = json.dumps(reordered_dict, ensure_ascii=False, sort_keys=False, indent=2).encode("utf-8") + b"\n"
    assert non_canonical_bytes != canonical_bytes

    with pytest.raises(ValueError, match=ASSIGNMENT_MANIFEST_CANONICAL_POLICY):
        load_and_validate_assignment_manifest_bytes(non_canonical_bytes, final_100_mode=True)

    manifest_path = tmp_path / "non_canonical_final_100.json"
    manifest_path.write_bytes(non_canonical_bytes)
    evals_dir = tmp_path / "evals"
    evals_dir.mkdir()
    with pytest.raises(ValueError, match=ASSIGNMENT_MANIFEST_CANONICAL_POLICY):
        aggregate_evaluations_from_disk(
            assignment_manifest_path=manifest_path,
            evaluations_dir=evals_dir,
            output_path=tmp_path / "out.json",
            final_100_mode=True,
        )


# ==============================================================================
# SECTION 6 — ADVERSARIAL EVIDENCE INTEGRITY TESTS (A–J)
# ==============================================================================


def _write_valid_run_dir(tmp_path: Path, subdir_name: str) -> Path:
    run_dir = tmp_path / subdir_name
    scenario = _make_scenario(scenario_id=f"SCEN_{subdir_name}", destination_slug="da-nang", days=1)
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[_make_poi_item(1, "09:00", "10:30", "poi_dn_247")],
            day_cost=100000,
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    write_canonical_json(run_dir / "scenario_input.json", scenario.model_dump())
    write_canonical_json(run_dir / "parsed_plan_response.json", plan.model_dump())
    write_canonical_json(run_dir / "run_manifest.json", manifest.model_dump())
    return run_dir


def test_w06_val_06_evidence_integrity_scenario_input_tampered_after_run(tmp_path: Path):
    """W06-VAL-06 (6.A): scenario_input.json tampered after run => EVIDENCE_INTEGRITY_FAILURE."""
    run_dir = _write_valid_run_dir(tmp_path, "tamper_scen")
    scen_data = json.loads((run_dir / "scenario_input.json").read_text(encoding="utf-8"))
    scen_data["budget"] = 9999999
    write_canonical_json(run_dir / "scenario_input.json", scen_data)

    res = evaluate_run_directory(run_dir)
    assert res.evaluation_status == "EVIDENCE_INTEGRITY_FAILURE"
    assert res.evidence_integrity_valid is False
    assert "SCENARIO_SHA256_MISMATCH" in res.failure_reasons
    assert res.core_scenario_pass is False


def test_w06_val_07_evidence_integrity_parsed_plan_response_tampered(tmp_path: Path):
    """W06-VAL-07 (6.B): parsed_plan_response.json tampered after run => EVIDENCE_INTEGRITY_FAILURE."""
    run_dir = _write_valid_run_dir(tmp_path, "tamper_parsed")
    parsed_data = json.loads((run_dir / "parsed_plan_response.json").read_text(encoding="utf-8"))
    parsed_data["overview"] = "Tampered overview text"
    write_canonical_json(run_dir / "parsed_plan_response.json", parsed_data)

    res = evaluate_run_directory(run_dir)
    assert res.evaluation_status == "EVIDENCE_INTEGRITY_FAILURE"
    assert res.evidence_integrity_valid is False
    assert "PARSED_RESPONSE_SHA256_MISMATCH" in res.failure_reasons
    assert res.core_scenario_pass is False


def test_w06_val_08_evidence_integrity_source_catalog_tampered(tmp_path: Path):
    """W06-VAL-08 (6.C): source catalog bytes changed / wrong catalog hash => EVIDENCE_INTEGRITY_FAILURE."""
    run_dir = _write_valid_run_dir(tmp_path, "tamper_catalog")
    fake_catalog = tmp_path / "tampered_catalog.jsonl"
    fake_catalog.write_text('{"place_id":"tampered"}\n', encoding="utf-8")

    res = evaluate_run_directory(run_dir, catalog_path=fake_catalog)
    assert res.evaluation_status == "EVIDENCE_INTEGRITY_FAILURE"
    assert res.evidence_integrity_valid is False
    assert "CATALOG_SHA256_MISMATCH" in res.failure_reasons
    assert res.core_scenario_pass is False


def test_w06_val_09_evidence_integrity_run_manifest_scenario_sha256_forged(tmp_path: Path):
    """W06-VAL-09 (6.D): run_manifest scenario_sha256 forged => EVIDENCE_INTEGRITY_FAILURE."""
    run_dir = _write_valid_run_dir(tmp_path, "forged_scen_sha")
    manifest_data = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest_data["scenario_sha256"] = "0" * 64
    write_canonical_json(run_dir / "run_manifest.json", manifest_data)

    res = evaluate_run_directory(run_dir)
    assert res.evaluation_status == "EVIDENCE_INTEGRITY_FAILURE"
    assert res.evidence_integrity_valid is False
    assert "SCENARIO_SHA256_MISMATCH" in res.failure_reasons
    assert res.core_scenario_pass is False


def test_w06_val_10_evidence_integrity_run_manifest_parsed_response_sha256_forged(tmp_path: Path):
    """W06-VAL-10 (6.E): run_manifest parsed_response_sha256 forged => EVIDENCE_INTEGRITY_FAILURE."""
    run_dir = _write_valid_run_dir(tmp_path, "forged_parsed_sha")
    manifest_data = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest_data["parsed_response_sha256"] = "1" * 64
    write_canonical_json(run_dir / "run_manifest.json", manifest_data)

    res = evaluate_run_directory(run_dir)
    assert res.evaluation_status == "EVIDENCE_INTEGRITY_FAILURE"
    assert res.evidence_integrity_valid is False
    assert "PARSED_RESPONSE_SHA256_MISMATCH" in res.failure_reasons
    assert res.core_scenario_pass is False


def test_w06_val_11_run_status_model_id_mismatch_fails_closed():
    """W06-VAL-11 (6.F): wrong model ID => MODEL_ID_MISMATCH, invalid run, core_scenario_pass=False."""
    _, ev = _build_batch_scenario_eval(
        "s_model_mismatch",
        "da-nang",
        run_status=BenchmarkRunStatus.MODEL_ID_MISMATCH,
    )
    assert ev.run_status == "MODEL_ID_MISMATCH"
    assert ev.evaluation_status == "INVALID_RUN"
    assert ev.run_valid is False
    assert ev.core_scenario_pass is False


def test_w06_val_12_run_status_mock_or_fallback_run_fails_closed():
    """W06-VAL-12 (6.G): MOCK_OR_FALLBACK_RUN => invalid run, core_scenario_pass=False."""
    _, ev = _build_batch_scenario_eval(
        "s_mock",
        "da-nang",
        run_status=BenchmarkRunStatus.MOCK_OR_FALLBACK_RUN,
    )
    assert ev.run_status == "MOCK_OR_FALLBACK_RUN"
    assert ev.evaluation_status == "INVALID_RUN"
    assert ev.run_valid is False
    assert ev.core_scenario_pass is False


def test_w06_val_13_run_status_api_error_fails_closed():
    """W06-VAL-13 (6.H): API_ERROR => invalid run, core_scenario_pass=False."""
    _, ev = _build_batch_scenario_eval(
        "s_api_err",
        "da-nang",
        run_status=BenchmarkRunStatus.API_ERROR,
    )
    assert ev.run_status == "API_ERROR"
    assert ev.evaluation_status == "INVALID_RUN"
    assert ev.run_valid is False
    assert ev.core_scenario_pass is False


def test_w06_val_14_run_status_unparsable_model_output_fails_closed():
    """W06-VAL-14 (6.I): UNPARSABLE_MODEL_OUTPUT => invalid run, core_scenario_pass=False."""
    _, ev = _build_batch_scenario_eval(
        "s_unparsable",
        "da-nang",
        run_status=BenchmarkRunStatus.UNPARSABLE_MODEL_OUTPUT,
    )
    assert ev.run_status == "UNPARSABLE_MODEL_OUTPUT"
    assert ev.evaluation_status == "INVALID_RUN"
    assert ev.run_valid is False
    assert ev.core_scenario_pass is False


def test_w06_val_15_run_status_missing_required_run_metadata_fails_closed(tmp_path: Path):
    """W06-VAL-15 (6.J): MISSING_REQUIRED_RUN_METADATA and missing manifest fields fail closed."""
    _, ev = _build_batch_scenario_eval(
        "s_missing_meta",
        "da-nang",
        run_status=BenchmarkRunStatus.MISSING_REQUIRED_RUN_METADATA,
    )
    assert ev.run_status == "MISSING_REQUIRED_RUN_METADATA"
    assert ev.evaluation_status == "INVALID_RUN"
    assert ev.run_valid is False
    assert ev.core_scenario_pass is False

    # Also verify missing required key in run_manifest.json on disk raises ValidationError
    run_dir = _write_valid_run_dir(tmp_path, "missing_meta_key")
    manifest_data = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    del manifest_data["model_id"]
    write_canonical_json(run_dir / "run_manifest.json", manifest_data)
    with pytest.raises(ValidationError):
        evaluate_run_directory(run_dir)


# ==============================================================================
# SECTION 7 — GROUNDING ADVERSARIAL CASES
# ==============================================================================


def test_w06_val_16_grounding_fake_place_id_and_valid_name_with_fake_place_id_ungrounded():
    """W06-VAL-16: fake place_id and valid place_name + fake place_id both evaluate as ungrounded."""
    cat = _make_validation_catalog()
    scenario = _make_scenario(start_date="2026-07-07", days=1)
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[
                _make_poi_item(1, "09:00", "10:00", "fake_id_1", "Nonexistent Place"),
                # Exact valid catalog name ("Cầu Rồng Đà Nẵng") paired with fake place_id must still fail grounding!
                _make_poi_item(2, "10:30", "11:30", "fake_id_2", "Cầu Rồng Đà Nẵng"),
            ],
            day_cost=200000,
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

    assert res.grounded_item_count == 0
    assert res.ungrounded_item_count == 2
    assert res.grounded_poi_rate == 0.0
    assert res.all_pois_grounded is False
    assert res.core_scenario_pass is False
    assert "UNGROUNDED_POI_VISIT_ITEMS" in res.failure_reasons


def test_w06_val_17_grounding_poi_from_wrong_destination_fails():
    """W06-VAL-17: grounded POI from ha-noi used in da-nang scenario fails destination check."""
    cat = _make_validation_catalog()
    scenario = _make_scenario(destination_slug="da-nang", start_date="2026-07-07", days=1)
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[_make_poi_item(1, "09:00", "10:30", "poi_hn_247", "Hồ Hoàn Kiếm")],
            day_cost=100000,
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

    assert res.all_pois_grounded is True
    assert res.destination_incorrect_item_count == 1
    assert res.scenario_destination_valid is False
    assert "DESTINATION_MISMATCH" in res.failure_reasons
    assert res.core_scenario_pass is False


def test_w06_val_18_grounding_duplicate_place_id_forbidden_vs_allowed():
    """W06-VAL-18: duplicate place_id fails when revisit forbidden and passes when revisit allowed."""
    cat = _make_validation_catalog()
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[
                _make_poi_item(1, "09:00", "10:00", "poi_dn_247"),
                _make_poi_item(2, "11:00", "12:00", "poi_dn_247"),
            ],
            day_cost=200000,
        )
    ]

    scen_forbid = _make_scenario(allow_revisit_place_ids=False)
    plan_f, man_f = _make_plan_and_manifest(scen_forbid, days)
    res_f = evaluate_benchmark_scenario(scen_forbid, plan_f, man_f, core_catalog_by_id=cat)
    assert res_f.duplicate_poi_violation_count == 1
    assert res_f.duplicate_poi_pass is False
    assert res_f.core_scenario_pass is False

    scen_allow = _make_scenario(allow_revisit_place_ids=True)
    plan_a, man_a = _make_plan_and_manifest(scen_allow, days)
    res_a = evaluate_benchmark_scenario(scen_allow, plan_a, man_a, core_catalog_by_id=cat)
    assert res_a.duplicate_poi_violation_count == 0
    assert res_a.duplicate_poi_pass is True
    assert res_a.core_scenario_pass is True


def test_w06_val_19_grounding_zero_poi_visit_or_all_transit_only_fails():
    """W06-VAL-19: zero POI_VISIT items / all TRANSIT_ONLY itinerary fails core pass."""
    _, ev = _build_batch_scenario_eval("s_all_transit", "da-nang", zero_poi_visits=True)
    assert ev.poi_visit_item_count == 0
    assert ev.transit_only_item_count == 1
    assert ev.all_pois_grounded is False
    assert "ZERO_POI_VISIT_ITEMS" in ev.failure_reasons
    assert ev.core_scenario_pass is False


def test_w06_val_20_grounding_transit_only_named_poi_and_schema_rejections():
    """W06-VAL-20: TRANSIT_ONLY with named POI fails anti-gaming; TRANSIT_ONLY with place_id or bad activity_kind fails schema."""
    cat = _make_validation_catalog()
    scenario = _make_scenario(start_date="2026-07-07", days=1)
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[
                _make_poi_item(1, "09:00", "10:00", "poi_dn_247"),
                _make_transit_item(2, "10:00", "10:30", place_name="Chợ Hàn"),
            ],
            day_cost=150000,
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)
    assert res.transit_only_named_poi_violation_count == 1
    assert res.transit_only_pass is False
    assert "TRANSIT_ONLY_NAMED_POI_VIOLATION" in res.failure_reasons
    assert res.core_scenario_pass is False

    # TRANSIT_ONLY with non-null place_id => schema rejection
    with pytest.raises(ValidationError, match="TRANSIT_ONLY item must have place_id=null"):
        BenchmarkItineraryItem(
            order_index=1,
            start_time="09:00",
            end_time="10:00",
            activity_kind=ActivityKind.TRANSIT_ONLY,
            activity="Di chuyển",
            place_name=None,
            place_id="poi_dn_247",
            notes=None,
            estimated_cost=0,
            transport_mode="taxi",
        )

    # Unknown or missing activity_kind => schema rejection
    for bad_kind in ("FREE_TIME", None):
        with pytest.raises(ValidationError):
            BenchmarkItineraryItem.model_validate(
                {
                    "order_index": 1,
                    "start_time": "09:00",
                    "end_time": "10:00",
                    "activity_kind": bad_kind,
                    "activity": "Ăn trưa",
                    "place_name": "Quán ăn",
                    "place_id": "poi_dn_247",
                    "notes": None,
                    "estimated_cost": 50000,
                    "transport_mode": "walk",
                }
            )


# ==============================================================================
# SECTION 8 — SCHEDULE ADVERSARIAL CASES
# ==============================================================================


def test_w06_val_21_schedule_time_format_and_interval_direction_adversarial():
    """W06-VAL-21: '9:00' and '24:00' rejected; '23:59' valid; start==end and end<start invalid."""
    cat = _make_validation_catalog()
    scenario = _make_scenario(start_date="2026-07-07", days=1)

    for bad_start, bad_end, expected_reason in [
        ("9:00", "10:00", "TIME_PARSE_INVALID"),
        ("22:00", "24:00", "TIME_PARSE_INVALID"),
        ("10:00", "10:00", "TIME_INTERVAL_INVALID"),
        ("11:00", "10:00", "TIME_INTERVAL_INVALID"),
    ]:
        days = [
            BenchmarkItineraryDay(
                day_number=1,
                date="2026-07-07",
                title="Ngày 1",
                items=[_make_poi_item(1, bad_start, bad_end, "poi_dn_247")],
                day_cost=100000,
            )
        ]
        plan, manifest = _make_plan_and_manifest(scenario, days)
        res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)
        assert res.schedule_pass is False
        assert expected_reason in res.failure_reasons
        assert res.core_scenario_pass is False

    # "22:00" to "23:59" is valid
    valid_days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[_make_poi_item(1, "22:00", "23:59", "poi_dn_247")],
            day_cost=100000,
        )
    ]
    plan_v, man_v = _make_plan_and_manifest(scenario, valid_days)
    res_v = evaluate_benchmark_scenario(scenario, plan_v, man_v, core_catalog_by_id=cat)
    assert res_v.schedule_pass is True
    assert res_v.core_scenario_pass is True


def test_w06_val_22_schedule_intra_day_overlap_vs_back_to_back_vs_cross_day():
    """W06-VAL-22: 09:00-10:00 + 10:00-11:00 no overlap; 09:00-10:01 + 10:00-11:00 overlap; cross-day not overlap."""
    cat = _make_validation_catalog()

    # Back-to-back on same day + identical time slot on Day 2 => NO overlap
    scen_2d = _make_scenario(start_date="2026-07-07", days=2)
    days_ok = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[
                _make_poi_item(1, "09:00", "10:00", "poi_dn_247"),
                _make_poi_item(2, "10:00", "11:00", "poi_dn_weekday"),
            ],
            day_cost=200000,
        ),
        BenchmarkItineraryDay(
            day_number=2,
            date="2026-07-08",
            title="Ngày 2",
            items=[_make_poi_item(1, "09:00", "10:00", "poi_da-nang_1")],
            day_cost=100000,
        ),
    ]
    plan_ok, man_ok = _make_plan_and_manifest(scen_2d, days_ok)
    res_ok = evaluate_benchmark_scenario(scen_2d, plan_ok, man_ok, core_catalog_by_id=cat)
    assert res_ok.schedule_overlap_count == 0
    assert res_ok.schedule_pass is True
    assert res_ok.core_scenario_pass is True

    # 1-minute intra-day overlap: 09:00-10:01 and 10:00-11:00 => overlap
    scen_1d = _make_scenario(start_date="2026-07-07", days=1)
    days_ov = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[
                _make_poi_item(1, "09:00", "10:01", "poi_dn_247"),
                _make_poi_item(2, "10:00", "11:00", "poi_dn_weekday"),
            ],
            day_cost=200000,
        )
    ]
    plan_ov, man_ov = _make_plan_and_manifest(scen_1d, days_ov)
    res_ov = evaluate_benchmark_scenario(scen_1d, plan_ov, man_ov, core_catalog_by_id=cat)
    assert res_ov.schedule_overlap_count == 1
    assert res_ov.schedule_pass is False
    assert "SCHEDULE_OVERLAP" in res_ov.failure_reasons
    assert res_ov.core_scenario_pass is False


def test_w06_val_23_schedule_day_and_date_structure_adversarial():
    """W06-VAL-23: invalid calendar date, duplicate day_number, missing day, wrong final date all fail core pass."""
    cat = _make_validation_catalog()
    scenario = _make_scenario(start_date="2026-07-07", end_date="2026-07-08", days=2)

    # Case 1: invalid calendar date "2026-02-30"
    days_bad_date = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-02-30",
            title="Ngày 1",
            items=[_make_poi_item(1, "09:00", "10:00", "poi_dn_247")],
            day_cost=100000,
        ),
        BenchmarkItineraryDay(
            day_number=2,
            date="2026-07-08",
            title="Ngày 2",
            items=[_make_poi_item(1, "09:00", "10:00", "poi_dn_weekday")],
            day_cost=100000,
        ),
    ]
    p1, m1 = _make_plan_and_manifest(scenario, days_bad_date)
    r1 = evaluate_benchmark_scenario(scenario, p1, m1, core_catalog_by_id=cat)
    assert r1.scenario_date_alignment_pass is False
    assert r1.core_scenario_pass is False

    # Case 2: duplicate day_number [1, 1]
    days_dup_num = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[_make_poi_item(1, "09:00", "10:00", "poi_dn_247")],
            day_cost=100000,
        ),
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-08",
            title="Ngày 1 dup",
            items=[_make_poi_item(1, "09:00", "10:00", "poi_dn_weekday")],
            day_cost=100000,
        ),
    ]
    p2, m2 = _make_plan_and_manifest(scenario, days_dup_num)
    r2 = evaluate_benchmark_scenario(scenario, p2, m2, core_catalog_by_id=cat)
    assert r2.day_structure_pass is False
    assert r2.scenario_date_alignment_pass is False
    assert r2.core_scenario_pass is False

    # Case 3: missing day (only 1 day returned for 2-day scenario)
    days_missing = [days_dup_num[0]]
    p3, m3 = _make_plan_and_manifest(scenario, days_missing)
    r3 = evaluate_benchmark_scenario(scenario, p3, m3, core_catalog_by_id=cat)
    assert r3.day_count_pass is False
    assert r3.core_scenario_pass is False

    # Case 4: wrong final date (2026-07-09 instead of 2026-07-08)
    days_wrong_final = [
        days_dup_num[0],
        BenchmarkItineraryDay(
            day_number=2,
            date="2026-07-09",
            title="Ngày 2",
            items=[_make_poi_item(1, "09:00", "10:00", "poi_dn_weekday")],
            day_cost=100000,
        ),
    ]
    p4, m4 = _make_plan_and_manifest(scenario, days_wrong_final)
    r4 = evaluate_benchmark_scenario(scenario, p4, m4, core_catalog_by_id=cat)
    assert r4.scenario_date_alignment_pass is False
    assert r4.core_scenario_pass is False


# ==============================================================================
# SECTION 9 — BUDGET ADVERSARIAL CASES
# ==============================================================================


def test_w06_val_24_budget_null_positive_compliant_and_positive_exceeded():
    """W06-VAL-24: budget=None => NOT_APPLICABLE; budget>0 compliant => COMPLIANT; budget>0 exceeded => VIOLATION."""
    _, ev_null = _build_batch_scenario_eval("b_null", "da-nang", budget=None, item_cost=100000)
    assert ev_null.budget_status == "NOT_APPLICABLE"
    assert ev_null.estimated_budget_compliant is None
    assert ev_null.budget_overrun_fraction is None
    assert ev_null.budget_overrun_fraction_status == "NOT_APPLICABLE_NULL_BUDGET"
    assert ev_null.core_scenario_pass is True

    _, ev_ok = _build_batch_scenario_eval("b_ok", "da-nang", budget=300000, item_cost=100000, grounded_count=2)
    assert ev_ok.budget_status == "COMPLIANT"
    assert ev_ok.estimated_budget_compliant is True
    assert ev_ok.budget_overrun_fraction == 0.0
    assert ev_ok.budget_overrun_fraction_status == "COMPUTED_POSITIVE_BUDGET"
    assert ev_ok.core_scenario_pass is True

    _, ev_viol = _build_batch_scenario_eval("b_viol", "da-nang", budget=150000, item_cost=100000, grounded_count=2)
    assert ev_viol.budget_status == "VIOLATION"
    assert ev_viol.estimated_budget_compliant is False
    assert ev_viol.estimated_budget_violation_amount == 50000
    assert ev_viol.budget_overrun_fraction == round(50000 / 150000, 6)
    assert ev_viol.budget_overrun_fraction_status == "COMPUTED_POSITIVE_BUDGET"
    assert ev_viol.core_scenario_pass is False


def test_w06_val_25_budget_zero_compliant_and_zero_exceeded_no_divide_by_zero():
    """W06-VAL-25: budget=0 with cost=0 is COMPLIANT and cost>0 is VIOLATION; overrun fraction is None (never div-by-zero or 1.0)."""
    _, ev_z_ok = _build_batch_scenario_eval("b_zero_ok", "da-nang", budget=0, item_cost=0, grounded_count=2)
    assert ev_z_ok.budget_status == "COMPLIANT"
    assert ev_z_ok.estimated_budget_compliant is True
    assert ev_z_ok.estimated_budget_violation_amount == 0
    assert ev_z_ok.budget_overrun_fraction is None
    assert ev_z_ok.budget_overrun_fraction_status == "UNDEFINED_ZERO_BUDGET_DENOMINATOR"
    assert ev_z_ok.core_scenario_pass is True

    _, ev_z_viol = _build_batch_scenario_eval("b_zero_viol", "da-nang", budget=0, item_cost=50000, grounded_count=2)
    assert ev_z_viol.budget_status == "VIOLATION"
    assert ev_z_viol.estimated_budget_compliant is False
    assert ev_z_viol.estimated_budget_violation_amount == 100000
    assert ev_z_viol.budget_overrun_fraction is None
    assert ev_z_viol.budget_overrun_fraction_status == "UNDEFINED_ZERO_BUDGET_DENOMINATOR"
    assert "ESTIMATED_BUDGET_VIOLATION" in ev_z_viol.failure_reasons
    assert ev_z_viol.core_scenario_pass is False


def test_w06_val_26_budget_arithmetic_inconsistencies_fail_core_pass():
    """W06-VAL-26: sum(items) != day_cost or sum(day_cost) != budget_analysis.estimated_cost fails core pass."""
    cat = _make_validation_catalog()
    scenario = _make_scenario(start_date="2026-07-07", days=1, budget=500000)

    # Case 1: sum(items) == 100k != day_cost == 50k
    days_bad_day_cost = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[_make_poi_item(1, "09:00", "10:00", "poi_dn_247", estimated_cost=100000)],
            day_cost=50000,
        )
    ]
    p1, m1 = _make_plan_and_manifest(scenario, days_bad_day_cost, reported_estimated_cost=100000)
    r1 = evaluate_benchmark_scenario(scenario, p1, m1, core_catalog_by_id=cat)
    assert r1.arithmetic_self_consistency is False
    assert "ARITHMETIC_SELF_CONSISTENCY_FAILURE" in r1.failure_reasons
    assert r1.core_scenario_pass is False

    # Case 2: day_cost == 100k == sum(items), but budget_analysis.estimated_cost == 80k
    days_ok_day_cost = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[_make_poi_item(1, "09:00", "10:00", "poi_dn_247", estimated_cost=100000)],
            day_cost=100000,
        )
    ]
    p2, m2 = _make_plan_and_manifest(scenario, days_ok_day_cost, reported_estimated_cost=80000)
    r2 = evaluate_benchmark_scenario(scenario, p2, m2, core_catalog_by_id=cat)
    assert r2.arithmetic_self_consistency is False
    assert "ARITHMETIC_SELF_CONSISTENCY_FAILURE" in r2.failure_reasons
    assert r2.core_scenario_pass is False


# ==============================================================================
# SECTIONS 10 & 11 — OPENING-HOURS ADVERSARIAL & CORPUS REPRODUCTION
# ==============================================================================


def test_w06_val_27_opening_hours_compliant_and_known_violation_cases():
    """W06-VAL-27: 24/7 and supported open window => COMPLIANT; supported closed window => VIOLATION and core pass False."""
    ev_247 = evaluate_poi_visit_opening_hours(
        day_number=1,
        date_str="2026-07-07",
        date_context_trusted=True,
        order_index=1,
        place_id="poi_dn_247",
        is_grounded=True,
        opening_hours_raw="24/7",
        start_time="09:00",
        end_time="10:30",
    )
    assert ev_247.opening_hours_state == "COMPLIANT"

    ev_open = evaluate_poi_visit_opening_hours(
        day_number=1,
        date_str="2026-07-07",  # Tuesday
        date_context_trusted=True,
        order_index=1,
        place_id="poi_dn_weekday",
        is_grounded=True,
        opening_hours_raw="Tu-Su 07:30-17:00; Mo off",
        start_time="08:00",
        end_time="10:00",
    )
    assert ev_open.opening_hours_state == "COMPLIANT"

    ev_closed = evaluate_poi_visit_opening_hours(
        day_number=1,
        date_str="2026-07-06",  # Monday ('Mo off')
        date_context_trusted=True,
        order_index=1,
        place_id="poi_dn_weekday",
        is_grounded=True,
        opening_hours_raw="Tu-Su 07:30-17:00; Mo off",
        start_time="08:00",
        end_time="10:00",
    )
    assert ev_closed.opening_hours_state == "VIOLATION"

    _, scen_ev = _build_batch_scenario_eval("s_oh_viol", "da-nang", oh_violation=True)
    assert scen_ev.opening_hours_known_violation_count == 1
    assert scen_ev.core_scenario_pass is False


def test_w06_val_28_opening_hours_all_unsupported_and_missing_cases_return_unknown():
    """W06-VAL-28: missing, cross-midnight, open-ended +, PH/SH, solar-event, month/date, malformed all return UNKNOWN."""
    adversarial_oh_cases = [
        (None, "MISSING_OPENING_HOURS"),
        ("", "MISSING_OPENING_HOURS"),
        ("Mo-Su 18:00-02:00", "UNSUPPORTED_CROSS_MIDNIGHT_SYNTAX"),
        ("Mo-Su 15:00+", "UNSUPPORTED_OPEN_ENDED_PLUS"),
        ("Mo-Fr 08:00-17:00; PH off", "UNSUPPORTED_HOLIDAY_SELECTOR"),
        ("Mo-Fr 08:00-17:00; SH off", "UNSUPPORTED_HOLIDAY_SELECTOR"),
        ("sunrise-sunset", "UNSUPPORTED_SOLAR_EVENT_SYNTAX"),
        ("Jan-Mar 08:00-17:00", "UNSUPPORTED_DATE_OR_MONTH_SELECTOR"),
        ("completely malformed string ???", "UNSUPPORTED_SYNTAX"),
    ]
    for raw_oh, expected_reason in adversarial_oh_cases:
        ev = evaluate_poi_visit_opening_hours(
            day_number=1,
            date_str="2026-07-07",
            date_context_trusted=True,
            order_index=1,
            place_id="poi_test",
            is_grounded=True,
            opening_hours_raw=raw_oh,
            start_time="10:00",
            end_time="11:00",
        )
        assert ev.opening_hours_state == "UNKNOWN", f"Failed on {raw_oh!r}"
        assert ev.reason_code == expected_reason


def test_w06_val_29_opening_hours_unknown_neutral_and_no_evaluable_evidence_not_success():
    """W06-VAL-29: UNKNOWN alone is neutral for core_scenario_pass; NO_EVALUABLE_EVIDENCE is not labeled compliance success."""
    cat = _make_validation_catalog()
    scenario = _make_scenario(start_date="2026-07-07", days=1)
    days = [
        BenchmarkItineraryDay(
            day_number=1,
            date="2026-07-07",
            title="Ngày 1",
            items=[
                _make_poi_item(1, "09:00", "10:30", "poi_dn_missing_oh"),
                _make_poi_item(2, "19:00", "20:30", "poi_dn_cross_midnight"),
            ],
            day_cost=200000,
        )
    ]
    plan, manifest = _make_plan_and_manifest(scenario, days)
    res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

    assert res.opening_hours_unknown_items == 2
    assert res.opening_hours_evaluable_items == 0
    assert res.opening_hours_evidence_status == "NO_EVALUABLE_EVIDENCE"
    assert res.opening_hours_compliance_rate_on_evaluable_items is None
    assert res.core_scenario_pass is True


def test_w06_val_30_opening_hours_parser_corpus_exact_reproduction_622_101_73_91_10():
    """W06-VAL-30: recompute parser capability over frozen REC-A-CORE-V2 and verify exact 622/101/73/91/10 counts."""
    recomputed = build_opening_hours_parser_coverage_report()
    persisted = json.loads(COVERAGE_01C_JSON_PATH.read_text(encoding="utf-8"))

    assert recomputed == persisted
    assert recomputed["total_core_pois"] == 622
    assert recomputed["core_opening_hours_records"] == 101
    assert recomputed["unique_opening_hours_string_count"] == 73
    assert recomputed["parser_supported_record_count"] == 91
    assert recomputed["parser_unsupported_record_count"] == 10
    assert recomputed["unsupported_reason_counts"] == {
        "UNSUPPORTED_CROSS_MIDNIGHT_SYNTAX": 8,
        "UNSUPPORTED_HOLIDAY_SELECTOR": 1,
        "UNSUPPORTED_OPEN_ENDED_PLUS": 1,
    }


# ==============================================================================
# SECTION 12 — FINAL CORE PASS TRUTH TABLE
# ==============================================================================


def test_w06_val_31_final_core_pass_truth_table_exhaustive():
    """W06-VAL-31: verify truth table for (pre_opening_pass, date_alignment_pass, known_oh_violation_count) plus invalid/tampered."""
    cat = _make_validation_catalog()

    truth_cases = [
        # (pre_pass, date_aligned, oh_viol, expected_core_pass)
        (True, True, False, True),    # T, T, 0 => PASS
        (True, True, True, False),    # T, T, >0 => FAIL
        (True, False, False, False),  # T, F, 0 => FAIL
        (False, True, False, False),  # F, T, 0 => FAIL
        (False, False, False, False), # F, F, 0 => FAIL
        (False, True, True, False),   # F, T, >0 => FAIL
    ]

    for pre_pass, date_aligned, oh_viol, expected_core_pass in truth_cases:
        # Monday 2026-07-06 causes oh_viol on poi_dn_weekday when date_aligned is True
        start_date = "2026-07-06" if oh_viol else "2026-07-07"
        day_date = start_date if date_aligned else "2026-07-09"
        budget = 500000 if pre_pass else 10000  # 10k budget causes budget violation => pre_pass=False
        pid = "poi_dn_weekday" if oh_viol else "poi_dn_247"

        scenario = _make_scenario(start_date=start_date, days=1, budget=budget)
        days = [
            BenchmarkItineraryDay(
                day_number=1,
                date=day_date,
                title="Ngày 1",
                items=[
                    _make_poi_item(1, "09:00", "10:00", pid, estimated_cost=100000),
                    # Include an UNKNOWN opening-hours item to verify UNKNOWN alone never alters the Boolean formula
                    _make_poi_item(2, "11:00", "12:00", "poi_dn_missing_oh", estimated_cost=100000),
                ],
                day_cost=200000,
            )
        ]
        plan, manifest = _make_plan_and_manifest(scenario, days)
        res = evaluate_benchmark_scenario(scenario, plan, manifest, core_catalog_by_id=cat)

        assert res.core_scenario_pass_pre_opening_hours is pre_pass
        assert res.scenario_date_alignment_pass is date_aligned
        assert (res.opening_hours_known_violation_count > 0) is oh_viol
        assert res.opening_hours_unknown_items >= 1
        assert res.core_scenario_pass is expected_core_pass


# ==============================================================================
# SECTIONS 15, 16, 17, 18 — GROUNDING COUNTS, BOOTSTRAP, WILSON, MACRO
# ==============================================================================


def test_w06_val_32_grounding_count_aggregation_unequal_scenario_sizes():
    """W06-VAL-32: Scenario A (1/2) + Scenario B (8/8) => 9/10 = 0.9, never mean-of-means 0.75."""
    s_a, e_a = _build_batch_scenario_eval("scen_a", "da-nang", grounded_count=1, ungrounded_count=1)
    s_b, e_b = _build_batch_scenario_eval("scen_b", "ha-noi", grounded_count=8, ungrounded_count=0)

    manifest = BenchmarkAssignmentManifest(manifest_id="val-counts", assigned_scenarios=[s_a, s_b])
    agg = aggregate_benchmark_evaluations(manifest, [e_a, e_b])

    assert agg.grounded_item_count == 9
    assert agg.poi_visit_item_count == 10
    assert agg.grounded_poi_rate == 0.9
    assert agg.grounded_poi_rate != 0.75


def test_w06_val_33_cluster_bootstrap_single_cluster_and_identical_ratio_clusters():
    """W06-VAL-33: single scenario cluster and identical-ratio clusters yield zero-width CI at point estimate."""
    ci_single = compute_scenario_cluster_bootstrap_grounding_ci95([("s1", 3, 5)])
    assert ci_single is not None
    assert ci_single.cluster_count == 1
    assert ci_single.point_estimate == 0.6
    assert ci_single.lower == 0.6
    assert ci_single.upper == 0.6

    ci_identical = compute_scenario_cluster_bootstrap_grounding_ci95(
        [("s1", 1, 2), ("s2", 2, 4), ("s3", 5, 10)]
    )
    assert ci_identical is not None
    assert ci_identical.cluster_count == 3
    assert ci_identical.point_estimate == 0.5
    assert ci_identical.lower == 0.5
    assert ci_identical.upper == 0.5


def test_w06_val_34_cluster_bootstrap_extreme_size_asymmetry_and_zero_poi_denominator():
    """W06-VAL-34: one large scenario + many tiny scenarios resamples scenarios; zero POI denominator returns None."""
    clusters = [("s_big", 100, 100)] + [(f"s_tiny_{i}", 0, 1) for i in range(9)]
    ci = compute_scenario_cluster_bootstrap_grounding_ci95(clusters)
    assert ci is not None
    assert ci.resampling_unit == "scenario"
    assert ci.cluster_count == 10
    assert ci.grounded_item_count == 100
    assert ci.poi_visit_item_count == 109
    assert ci.point_estimate == round(100 / 109, 6)
    # In some bootstrap resamples s_big is not drawn at all => 0.0; in others drawn multiple times => >0.9
    assert ci.lower == 0.0
    assert ci.upper > 0.9

    assert compute_scenario_cluster_bootstrap_grounding_ci95([]) is None
    assert compute_scenario_cluster_bootstrap_grounding_ci95([("s0", 0, 0)]) is None


def test_w06_val_35_cluster_bootstrap_input_ordering_invariance_and_seed_determinism():
    """W06-VAL-35: cluster bootstrap is invariant to input ordering and byte-identical across repeated runs with seed 20261015."""
    clusters = [("s1", 2, 3), ("s2", 4, 4), ("s3", 1, 5), ("s4", 7, 8)]
    ci_1 = compute_scenario_cluster_bootstrap_grounding_ci95(clusters)
    ci_2 = compute_scenario_cluster_bootstrap_grounding_ci95(list(reversed(clusters)))
    assert ci_1 is not None and ci_2 is not None
    assert ci_1.seed == BOOTSTRAP_SEED == 20261015
    assert ci_1.iterations == BOOTSTRAP_ITERATIONS == 10000
    assert canonical_json_bytes(ci_1.model_dump()) == canonical_json_bytes(ci_2.model_dump())


def test_w06_val_36_wilson_ci_edge_cases_exact():
    """W06-VAL-36: Wilson 95% CI exact edge cases for 0/100, 100/100, 50/100, 1/1, 0/1, n=0 => None."""
    assert compute_wilson_ci95(0, 0) is None

    for k, n, exp_pt, exp_lo, exp_hi in [
        (0, 100, 0.0, 0.0, 0.036993),
        (100, 100, 1.0, 0.963007, 1.0),
        (50, 100, 0.5, 0.403832, 0.596168),
        (1, 1, 1.0, 0.206549, 1.0),
        (0, 1, 0.0, 0.0, 0.793451),
    ]:
        ci = compute_wilson_ci95(k, n)
        assert ci is not None
        assert not math.isnan(ci.point_estimate)
        assert not math.isnan(ci.lower)
        assert not math.isnan(ci.upper)
        assert 0.0 <= ci.lower <= ci.point_estimate <= ci.upper <= 1.0
        assert ci.point_estimate == exp_pt
        assert ci.lower == exp_lo
        assert ci.upper == exp_hi

    with pytest.raises(ValueError):
        compute_wilson_ci95(-1, 10)
    with pytest.raises(ValueError):
        compute_wilson_ci95(11, 10)


def test_w06_val_37_per_destination_unequal_counts_equal_weight_macro():
    """W06-VAL-37: equal-destination macro weights each destination 1/3 even with 10:1:1 scenario counts."""
    specs = []
    evals = []
    for i in range(10):
        s, e = _build_batch_scenario_eval(f"hn_{i}", "ha-noi")
        specs.append(s)
        evals.append(e)
    s_dn, e_dn = _build_batch_scenario_eval("dn_0", "da-nang", schedule_overlap=True)
    s_hl, e_hl = _build_batch_scenario_eval("hl_0", "ha-long", schedule_overlap=True)
    specs.extend([s_dn, s_hl])
    evals.extend([e_dn, e_hl])

    manifest = BenchmarkAssignmentManifest(manifest_id="val-macro-unequal", assigned_scenarios=specs)
    agg = aggregate_benchmark_evaluations(manifest, evals)

    assert agg.core_scenario_pass_rate_all_assigned == round(10 / 12, 6)
    assert agg.equal_destination_macro.equal_weight_per_destination == round(1 / 3, 6)
    assert agg.equal_destination_macro.core_scenario_pass_rate_macro == round(1 / 3, 6)


def test_w06_val_38_per_destination_undefined_metric_no_zero_imputation():
    """W06-VAL-38: undefined metric in one destination yields macro=None and UNDEFINED_MISSING_DESTINATION_EVIDENCE."""
    s_hn, e_hn = _build_batch_scenario_eval("hn_1", "ha-noi", budget=500000)
    s_dn, e_dn = _build_batch_scenario_eval("dn_1", "da-nang", budget=500000)
    s_hl, e_hl = _build_batch_scenario_eval("hl_1", "ha-long", budget=None)

    manifest = BenchmarkAssignmentManifest(
        manifest_id="val-macro-undef", assigned_scenarios=[s_hn, s_dn, s_hl]
    )
    agg = aggregate_benchmark_evaluations(manifest, [e_hn, e_dn, e_hl])

    assert agg.per_destination["ha-long"].estimated_budget_violation_rate is None
    assert agg.equal_destination_macro.estimated_budget_violation_rate_macro is None
    assert (
        agg.equal_destination_macro.metric_macro_status["estimated_budget_violation_rate_macro"]
        == "UNDEFINED_MISSING_DESTINATION_EVIDENCE"
    )


# ==============================================================================
# SECTION 19 — FINAL_100 ASSIGNMENT VALIDATION ADVERSARIAL CASES
# ==============================================================================


def test_w06_val_39_final_100_rejects_99_and_101_scenarios():
    """W06-VAL-39: FINAL_100 rejects 99 scenarios and 101 scenarios."""
    manifest, evals = _build_synthetic_100_batch()

    # 99 scenarios
    m99 = manifest.model_copy(update={"assigned_scenarios": manifest.assigned_scenarios[:99]})
    with pytest.raises(ValueError, match="FINAL_100 mode requires exactly 100"):
        aggregate_benchmark_evaluations(m99, evals[:99], final_100_mode=True)

    # 101 scenarios
    s_extra, e_extra = _build_batch_scenario_eval("SYNTH_VAL_101", "ha-noi")
    m101 = manifest.model_copy(
        update={"assigned_scenarios": list(manifest.assigned_scenarios) + [s_extra]}
    )
    with pytest.raises(ValueError, match="FINAL_100 mode requires exactly 100"):
        aggregate_benchmark_evaluations(m101, evals + [e_extra], final_100_mode=True)


def test_w06_val_40_final_100_rejects_wrong_allocations_34_34_32_and_33_34_33():
    """W06-VAL-40: FINAL_100 rejects 34/34/32 and 33/34/33 destination allocations."""
    # Case 1: 34/34/32 (change last ha-long to da-nang)
    m1, e1 = _build_synthetic_100_batch()
    m1.assigned_scenarios[-1].destination_slug = "da-nang"
    e1[-1].destination_slug = "da-nang"
    with pytest.raises(ValueError, match="FINAL_100 mode requires exact destination allocation"):
        aggregate_benchmark_evaluations(m1, e1, final_100_mode=True)

    # Case 2: 33/34/33 (change first ha-noi to da-nang)
    m2, e2 = _build_synthetic_100_batch()
    m2.assigned_scenarios[0].destination_slug = "da-nang"
    e2[0].destination_slug = "da-nang"
    with pytest.raises(ValueError, match="FINAL_100 mode requires exact destination allocation"):
        aggregate_benchmark_evaluations(m2, e2, final_100_mode=True)


def test_w06_val_41_final_100_rejects_duplicate_missing_extra_and_multi_result_scenarios():
    """W06-VAL-41: rejects duplicate assigned IDs, missing result, extra result, and duplicate result."""
    manifest, evals = _build_synthetic_100_batch()

    # Duplicate assigned ID
    dup_manifest = copy.deepcopy(manifest)
    dup_manifest.assigned_scenarios[1] = dup_manifest.assigned_scenarios[0]
    with pytest.raises(ValueError, match="Duplicate assigned scenario_id"):
        aggregate_benchmark_evaluations(dup_manifest, evals, final_100_mode=True)

    # Missing scenario result
    with pytest.raises(ValueError, match="Missing evaluation results for assigned scenarios"):
        aggregate_benchmark_evaluations(manifest, evals[:-1], final_100_mode=True)

    # Extra unassigned scenario result
    _, extra_ev = _build_batch_scenario_eval("UNASSIGNED_SCEN", "da-nang")
    with pytest.raises(ValueError, match="Unexpected evaluation result for unassigned scenario_id"):
        aggregate_benchmark_evaluations(manifest, evals + [extra_ev], final_100_mode=True)

    # Multiple results for one scenario
    with pytest.raises(ValueError, match="Multiple evaluation results provided for scenario_id"):
        aggregate_benchmark_evaluations(manifest, evals + [evals[0]], final_100_mode=True)


def test_w06_val_42_final_100_rejects_unsupported_destination_and_destination_mismatch():
    """W06-VAL-42: rejects unsupported destination (ha-giang/moc-chau) and destination mismatch between manifest and result."""
    with pytest.raises(ValidationError, match="Unsupported destination_slug"):
        AssignedScenarioSpec(
            scenario_id="s_hg",
            destination_slug="ha-giang",
            scenario_sha256="a" * 64,
        )

    manifest, evals = _build_synthetic_100_batch()
    bad_evals = copy.deepcopy(evals)
    bad_evals[0].destination_slug = "da-nang"  # manifest expects ha-noi
    with pytest.raises(ValueError, match="Destination mismatch"):
        aggregate_benchmark_evaluations(manifest, bad_evals, final_100_mode=True)


# ==============================================================================
# SECTIONS 21, 22, 23, 27 — DETERMINISM, PRODUCTION ISOLATION & RECEIPT GATE
# ==============================================================================


def test_w06_val_43_deterministic_byte_output_and_ordering_invariance_no_timestamps():
    """W06-VAL-43: repeated scenario evaluation and batch aggregation are byte-identical, order-invariant, and timestamp-free."""
    s1, e1_a = _build_batch_scenario_eval("det_1", "ha-noi", grounded_count=2)
    _, e1_b = _build_batch_scenario_eval("det_1", "ha-noi", grounded_count=2)
    assert canonical_json_bytes(e1_a.model_dump()) == canonical_json_bytes(e1_b.model_dump())

    s2, e2 = _build_batch_scenario_eval("det_2", "da-nang", grounded_count=3)
    s3, e3 = _build_batch_scenario_eval("det_3", "ha-long", grounded_count=1, ungrounded_count=1)

    m_forward = BenchmarkAssignmentManifest(
        manifest_id="det-order", assigned_scenarios=[s1, s2, s3]
    )
    m_reverse = BenchmarkAssignmentManifest(
        manifest_id="det-order", assigned_scenarios=[s3, s2, s1]
    )

    agg_forward = aggregate_benchmark_evaluations(
        m_forward, [e1_a, e2, e3], assignment_manifest_sha256="a" * 64
    )
    agg_reverse = aggregate_benchmark_evaluations(
        m_reverse, [e3, e2, e1_a], assignment_manifest_sha256="a" * 64
    )
    bytes_fwd = canonical_json_bytes(agg_forward.model_dump())
    bytes_rev = canonical_json_bytes(agg_reverse.model_dump())
    assert bytes_fwd == bytes_rev

    for payload in (e1_a.model_dump(), agg_forward.model_dump()):
        for k in payload:
            assert "timestamp" not in k.lower()
            assert "created_at" not in k.lower()


def test_w06_val_44_no_leakage_into_production_and_validation_gate_receipt_verified():
    """W06-VAL-44: verify zero production/W5/contract leakage, no real 100 scenarios or P11 manifest, and gate receipt PASS."""
    # 1. No real 100 scenarios generated on disk (only legacy 3 scenarios exist)
    scenario_files = sorted(p.name for p in PLANNER_EVAL_DIR.glob("*.json"))
    assert scenario_files == ["da_nang_4d.json", "ha_giang_3d.json", "moc_chau_3d.json"]

    # 2. Production planner and historical contract files untouched since 7fd5364ed4671c06b0c911b6fd53bd9f54cbc322
    res = subprocess.run(
        [
            "git",
            "diff",
            MEASUREMENT_CONTRACT_SOURCE_COMMIT,
            "--",
            "apps/ai-service/app/routers/planner.py",
            "apps/ai-service/app/schemas/planner.py",
            "apps/ai-service/app/prompts/planner_prompt.py",
            "data/evaluation/w06/w06_measurement_contract_v1.json",
            "docs/research/w06_measurement_contract_v1.md",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == ""

    # 3. Verify validation gate receipt and documentation
    assert VALIDATION_RECEIPT_JSON_PATH.exists()
    assert VALIDATION_DOC_MD_PATH.exists()

    receipt = json.loads(VALIDATION_RECEIPT_JSON_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_JSON_PATH.read_text(encoding="utf-8"))

    assert receipt["gate_id"] == "W06-INSTRUMENT-VALIDATION-01"
    assert receipt["gate_purpose"] == "PRE_SCENARIO_FREEZE_MEASUREMENT_SYSTEM_VALIDATION"
    assert receipt["base_develop_sha"] == "8d599bd8fe1a167a64c375c43148928daeb94dca"
    assert receipt["instrument_01a_status"] == "CLOSED"
    assert receipt["instrument_01b_status"] == "CLOSED"
    assert receipt["instrument_01c_status"] == "CLOSED"
    assert receipt["evaluator_version"] == EVALUATOR_VERSION
    assert receipt["aggregator_version"] == AGGREGATOR_VERSION
    assert receipt["opening_hours_parser_version"] == OPENING_HOURS_PARSER_VERSION

    assert receipt["adversarial_test_count"] == 44
    assert receipt["adversarial_test_pass_count"] == 44
    assert receipt["adversarial_test_fail_count"] == 0
    assert receipt["followup_note_a_status"] == "RESOLVED"
    assert receipt["followup_note_b_status"] == "RESOLVED"
    assert receipt["metric_name_ambiguity_resolved"] is True
    assert receipt["final_100_manifest_hash_contract_defined"] is True
    assert receipt["parser_corpus_reproduction_status"] == "EXACT_MATCH_622_101_73_91_10"
    assert receipt["evidence_integrity_gate_status"] == "PASS"
    assert receipt["determinism_gate_status"] == "PASS"
    assert receipt["denominator_gate_status"] == "PASS"
    assert receipt["bootstrap_gate_status"] == "PASS"
    assert receipt["opening_hours_gate_status"] == "PASS"
    assert receipt["overall_gate_status"] == "PASS"

    bounds = receipt["scientific_boundaries"]
    assert bounds["real_100_scenarios_generated"] is False
    assert bounds["real_100_assignment_manifest_created"] is False
    assert bounds["P11_implemented"] is False
    assert bounds["final_benchmark_executed"] is False
    assert bounds["scientific_performance_results_generated"] is False
    assert bounds["preregistration_created"] is False
    assert bounds["Gemini_called"] is False
    assert bounds["W5_modified"] is False
    assert bounds["production_planner_behavior_modified"] is False
    assert bounds["historical_measurement_contract_modified"] is False

    matrix = receipt["prerequisite_implementation_matrix"]
    contract_prereqs = {
        item["id"]: item["requirement"]
        for item in contract["required_instrumentation_prerequisites"]
    }
    assert list(matrix.keys()) == [f"P{i}" for i in range(1, 13)]
    for pid, req in contract_prereqs.items():
        assert matrix[pid]["contract_requirement"] == req
    assert matrix["P11"]["status"] == "NOT_IMPLEMENTED"
    for pid in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P12"):
        assert matrix[pid]["status"] == "IMPLEMENTED"
