"""Independent Verifier for W06 DEV-Only Scenario Fixture Freeze (W06-DEV-FIXTURE-FREEZE-01).

Independently verifies:
- 80 total DEV fixtures (DEV-TUNE = 20, DEV-SELECT = 60)
- Exact IDs (W06-DEV-TUNE-001..020, W06-DEV-SELECT-001..060)
- BenchmarkScenarioInput schema validation and fixture_label values
- Exact DEV-TUNE and DEV-SELECT marginals
- Exact budget tier formulas (B1=500000*days, B2=1000000*days, B3=2000000*days, null=None)
- Date window (2026-11-02..2026-12-13), contiguous trip spans, and weekend exposure
- Canonical interest membership, sorting, and uniqueness
- Independent Rule A and Rule B (direct place_id set union) from gomate_places_freeze_v2.json
- EXCLUDED = 0
- All 80 DEV exact signatures unique (0 internal or cross-partition duplicates)
- Exact overlap with final 100 = 0
- DEV-TUNE near-overlap with final 100 = 0
- DEV-SELECT near-overlap with final 100 independently counted and rate verified
- Canonical UTF-8 LF JSON byte formatting and SHA256 hashes
- 1:1 semantic and hash agreement between DEV bundle, DEV manifest, overlap receipt, and freeze receipt
- No provider/model assignment or output fields in DEV bundle or manifest
- No final-100 scenario semantic dump in receipts or normal CLI output
- Two independent temporary-directory regeneration runs produce identical SHA256s
- All 10 pre-existing scientific authority files remain byte-identical
"""

from __future__ import annotations

from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.evaluation.planner_dev_fixture_generator import (  # noqa: E402
    DEV_FIXTURE_GENERATION_SEED,
    LOCKED_DEV_SELECT_MARGINALS,
    LOCKED_DEV_TUNE_MARGINALS,
    write_frozen_dev_fixture_files,
)
from app.schemas.planner_benchmark import (  # noqa: E402
    CANONICAL_BENCHMARK_INTERESTS,
    PRIMARY_BENCHMARK_DESTINATIONS,
    BenchmarkScenarioInput,
)
from recommendation.reca.contract import (  # noqa: E402
    CANONICAL_INTERESTS,
    poi_to_canonical_vector,
)

EXPECTED_AUTHORITY_HASHES: Dict[str, str] = {
    "data/evaluation/w06/w06_scenarios_freeze_v1.json": (
        "c03bc6dc300604ac395505d59b6413c1a47339b21408cfd637671e81d4b555a1"
    ),
    "data/evaluation/w06/w06_p11_assignment_manifest_v1.json": (
        "0aa9ae923d0e7f29df49735fa41e87530b1caf62418fcbec09a1eff81d83af62"
    ),
    "data/evaluation/w06/w06_model_arch_selection_method_lock_v1.json": (
        "6f30cdf90355dd720795de8e0b21beba45f527767892ca7eb88769141a64210c"
    ),
    "data/evaluation/w06/w06_scenario_method_lock_v1.json": (
        "5e5359f9f10a0248a9cf031f8e8b26c0314c46aecfe0d9df479388bbe4fd1af9"
    ),
    "data/evaluation/w06/w06_scenario_support_matrix_v1.json": (
        "68c2bfc2164e664b3856c31b99a92d75a588f64465526b47c9104918a51cedb4"
    ),
    "data/evaluation/w06/w06_measurement_contract_v1.json": (
        "0ddc1f8d879493517cee25f247d2365a0bacb816dc33b129b0c6110d4bfb8298"
    ),
    "apps/ai-service/app/evaluation/planner_scenario_generator.py": (
        "623c52cbdd98d181cd9cbbc1e68697a7299cb6c864628e97e743afd9e09ceae1"
    ),
    "scripts/audit_w06_scenario_generator_dryrun.py": (
        "2e5a218fc49d4af0052dffa49c14a8a7d5d9818847fd6d37f647422a9cadc6fc"
    ),
    "data/curated/gomate_places_freeze_v2.json": (
        "f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444"
    ),
    "apps/ai-service/recommendation/reca/contract.py": (
        "1a62c36a95092be35ab78dca43e20f646016e154746ee051a499bdebfc67538c"
    ),
}

FORBIDDEN_PROVIDER_KEYS: Tuple[str, ...] = (
    "gemini",
    "openai",
    "claude",
    "anthropic",
    "grok",
    "provider",
    "model_output",
    "winning_model",
    "selected_model",
)


def _canonical_json_lf_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lf_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return _sha256_bytes(raw)


def _build_independent_catalog_index(catalog_path: Path) -> Dict[str, Dict[str, Set[str]]]:
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    places = payload["places"] if isinstance(payload, dict) and "places" in payload else payload
    index: Dict[str, Dict[str, Set[str]]] = {
        dest: {interest: set() for interest in CANONICAL_INTERESTS}
        for dest in ("ha-noi", "da-nang", "ha-long")
    }
    for poi in places:
        if not poi.get("is_rec_a_core_v2", False):
            continue
        dest = poi.get("destination_slug")
        if dest not in index:
            continue
        pid = poi["place_id"]
        vec, _ = poi_to_canonical_vector(poi)
        for idx, interest in enumerate(CANONICAL_INTERESTS):
            if vec[idx] > 0.0:
                index[dest][interest].add(pid)
    return index


def _derive_budget_tier(budget: Optional[int], days: int) -> Optional[str]:
    if budget is None:
        return None
    if days <= 0 or budget % days != 0:
        raise ValueError(f"Budget {budget} not divisible by days {days}")
    daily = budget // days
    mapping = {500000: "B1", 1000000: "B2", 2000000: "B3"}
    if daily not in mapping:
        raise ValueError(f"Invalid daily nominal budget: {daily}")
    return mapping[daily]


def _derive_weekend_exposure(start_date_str: str, end_date_str: str, days: int) -> bool:
    s_dt = datetime.date.fromisoformat(start_date_str)
    e_dt = datetime.date.fromisoformat(end_date_str)
    w_start = datetime.date.fromisoformat("2026-11-02")
    w_end = datetime.date.fromisoformat("2026-12-13")
    if s_dt < w_start or e_dt > w_end:
        raise ValueError(f"Trip dates {start_date_str}..{end_date_str} outside allowed window")
    if e_dt != s_dt + datetime.timedelta(days=days - 1):
        raise ValueError(f"Non-contiguous trip dates {start_date_str}..{end_date_str} for days={days}")
    return any((s_dt + datetime.timedelta(days=i)).weekday() in (5, 6) for i in range(days))


def _independent_marginal_counts(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    dest_c = {d: 0 for d in ("ha-noi", "da-nang", "ha-long")}
    days_c = {str(d): 0 for d in (2, 3, 4)}
    k_c = {str(k): 0 for k in (1, 2, 3)}
    b_c = {"B1": 0, "B2": 0, "B3": 0, "null": 0}
    s_c = {s: 0 for s in ("BACKPACKER", "BUDGET", "COMFORT", "LUXURY")}
    wk_c = {"weekend_exposed": 0, "non_weekend_exposed": 0}
    for r in records:
        dest_c[r["destination_slug"]] += 1
        days_c[str(r["days"])] += 1
        k_c[str(r["interest_count"])] += 1
        b_c[r["budget_tier_or_null"] or "null"] += 1
        s_c[r["travel_style"]] += 1
        wk_c["weekend_exposed" if r["weekend_exposure"] else "non_weekend_exposed"] += 1
    return {
        "destination": dest_c,
        "days": days_c,
        "interest_count": k_c,
        "budget": b_c,
        "travel_style": s_c,
        "weekend": wk_c,
    }


def verify_w06_dev_fixture_freeze_independently(
    *,
    dev_bundle_path: Optional[Path] = None,
    dev_manifest_path: Optional[Path] = None,
    overlap_receipt_path: Optional[Path] = None,
    freeze_receipt_path: Optional[Path] = None,
    run_determinism_check: bool = True,
) -> Dict[str, Any]:
    """Perform an independent end-to-end verification of the frozen W06 DEV fixture artifacts."""
    errors: List[str] = []

    # 1. Verify all 10 pre-existing scientific authority hashes
    authority_status: Dict[str, bool] = {}
    for rel_path, expected_sha in EXPECTED_AUTHORITY_HASHES.items():
        p = REPO_ROOT / rel_path
        if not p.exists():
            errors.append(f"Missing frozen authority file: {rel_path}")
            authority_status[rel_path] = False
            continue
        actual_sha = _lf_sha256(p)
        ok = actual_sha == expected_sha
        authority_status[rel_path] = ok
        if not ok:
            errors.append(
                f"Authority hash mismatch for {rel_path}: {actual_sha} != {expected_sha}"
            )

    bundle_p = dev_bundle_path or (
        REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_fixtures_freeze_v1.json"
    )
    manifest_p = dev_manifest_path or (
        REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_fixture_manifest_v1.json"
    )
    overlap_p = overlap_receipt_path or (
        REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_final_overlap_receipt_v1.json"
    )
    receipt_p = freeze_receipt_path or (
        REPO_ROOT / "data" / "evaluation" / "w06" / "w06_dev_fixture_freeze_01_receipt_v1.json"
    )

    for label, p in (
        ("dev_bundle", bundle_p),
        ("dev_manifest", manifest_p),
        ("overlap_receipt", overlap_p),
        ("freeze_receipt", receipt_p),
    ):
        if not p.exists():
            errors.append(f"Missing target artifact {label} at {p}")
    if errors:
        return {"status": "FAIL", "errors": errors}

    # 2. Verify canonical UTF-8 LF JSON byte formatting of all 4 DEV files
    bundle_raw = bundle_p.read_bytes()
    manifest_raw = manifest_p.read_bytes()
    overlap_raw = overlap_p.read_bytes()
    receipt_raw = receipt_p.read_bytes()

    bundle_data = json.loads(bundle_raw.decode("utf-8"))
    manifest_data = json.loads(manifest_raw.decode("utf-8"))
    overlap_data = json.loads(overlap_raw.decode("utf-8"))
    receipt_data = json.loads(receipt_raw.decode("utf-8"))

    for label, raw_b, parsed in (
        ("dev_bundle", bundle_raw, bundle_data),
        ("dev_manifest", manifest_raw, manifest_data),
        ("overlap_receipt", overlap_raw, overlap_data),
        ("freeze_receipt", receipt_raw, receipt_data),
    ):
        if b"\r" in raw_b:
            errors.append(f"{label} contains CR bytes; must be LF-only UTF-8")
        if raw_b != _canonical_json_lf_bytes(parsed):
            errors.append(f"{label} is not serialized as canonical sorted-key UTF-8 LF JSON")

    bundle_sha = _sha256_bytes(bundle_raw)
    manifest_sha = _sha256_bytes(manifest_raw)
    overlap_sha = _sha256_bytes(overlap_raw)
    receipt_sha = _sha256_bytes(receipt_raw)

    # 3. Independently load final-100 signatures without printing final semantics
    final_bundle_p = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_scenarios_freeze_v1.json"
    p11_p = REPO_ROOT / "data" / "evaluation" / "w06" / "w06_p11_assignment_manifest_v1.json"
    final_scenarios = json.loads(final_bundle_p.read_text(encoding="utf-8"))["scenarios"]
    p11_assignments = json.loads(p11_p.read_text(encoding="utf-8"))["assignments"]

    final_exact_sigs: Set[Tuple[str, int, Tuple[str, ...], Optional[str], bool, str]] = set()
    final_near_keys: Set[Tuple[str, int, Tuple[str, ...], Optional[str]]] = set()
    final_scenario_ids: Set[str] = set()
    final_scenario_shas: Set[str] = set()

    for f_scen, p11_item in zip(final_scenarios, p11_assignments):
        final_scenario_ids.add(f_scen["scenario_id"])
        final_scenario_shas.add(p11_item["scenario_sha256"])
        f_dest = f_scen["destination_slug"]
        f_days = int(f_scen["days"])
        f_ints = tuple(sorted(f_scen["interests"]))
        f_b = _derive_budget_tier(f_scen["budget"], f_days)
        f_wk = _derive_weekend_exposure(f_scen["start_date"], f_scen["end_date"], f_days)
        f_style = f_scen["travel_style"]
        final_exact_sigs.add((f_dest, f_days, f_ints, f_b, f_wk, f_style))
        for d_dev in (2, 3, 4):
            if abs(d_dev - f_days) <= 1:
                final_near_keys.add((f_dest, d_dev, f_ints, f_b))

    # 4. Independently build catalog interest index
    catalog_index = _build_independent_catalog_index(
        REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
    )

    # 5. Verify DEV bundle top-level metadata and all 80 fixtures
    if bundle_data.get("artifact_id") != "W06-DEV-FIXTURES-FREEZE-01":
        errors.append(f"Unexpected bundle artifact_id: {bundle_data.get('artifact_id')}")
    if bundle_data.get("seed") != DEV_FIXTURE_GENERATION_SEED:
        errors.append(f"Unexpected bundle seed: {bundle_data.get('seed')}")
    if (
        bundle_data.get("fixture_count") != 80
        or bundle_data.get("dev_tune_count") != 20
        or bundle_data.get("dev_select_count") != 60
    ):
        errors.append("Bundle fixture counts mismatch (expected 80 / 20 / 60)")

    fixtures = bundle_data.get("fixtures", [])
    manifest_fixtures = manifest_data.get("fixtures", [])
    if len(fixtures) != 80:
        errors.append(f"Expected 80 fixtures in bundle, got {len(fixtures)}")
    if len(manifest_fixtures) != 80:
        errors.append(f"Expected 80 fixtures in manifest, got {len(manifest_fixtures)}")

    expected_tune_ids = [f"W06-DEV-TUNE-{i:03d}" for i in range(1, 21)]
    expected_select_ids = [f"W06-DEV-SELECT-{i:03d}" for i in range(1, 61)]
    actual_ids = [f.get("scenario_id") for f in fixtures]
    if actual_ids[:20] != expected_tune_ids:
        errors.append("DEV-TUNE IDs do not match exact W06-DEV-TUNE-001..020 sequence")
    if actual_ids[20:] != expected_select_ids:
        errors.append("DEV-SELECT IDs do not match exact W06-DEV-SELECT-001..060 sequence")

    rule_a_failures = 0
    rule_b_failures = 0
    excluded_count = 0
    seen_dev_sigs: Set[Tuple[str, int, Tuple[str, ...], Optional[str], bool, str]] = set()
    dev_duplicate_sigs = 0
    final_exact_overlap_count = 0
    dev_tune_near_overlap_count = 0
    dev_select_near_overlap_count = 0

    tune_records: List[Dict[str, Any]] = []
    select_records: List[Dict[str, Any]] = []
    combo_reuse: Counter[Tuple[str, Tuple[str, ...]]] = Counter()

    for idx, (f_obj, m_obj) in enumerate(zip(fixtures, manifest_fixtures), start=1):
        try:
            validated = BenchmarkScenarioInput.model_validate(f_obj)
            dumped = validated.model_dump(mode="json")
            if dumped != f_obj:
                errors.append(f"Fixture {idx} dict differs from validated BenchmarkScenarioInput dump")
        except Exception as exc:
            errors.append(f"Fixture {idx} failed BenchmarkScenarioInput validation: {exc}")
            continue

        for k_name in f_obj.keys():
            if any(tok in k_name.lower() for tok in FORBIDDEN_PROVIDER_KEYS):
                errors.append(f"Forbidden provider/model key {k_name!r} in bundle fixture {idx}")
        for k_name in m_obj.keys():
            if any(tok in k_name.lower() for tok in FORBIDDEN_PROVIDER_KEYS):
                errors.append(f"Forbidden provider/model key {k_name!r} in manifest fixture {idx}")

        is_tune = idx <= 20
        expected_part = "DEV_TUNE" if is_tune else "DEV_SELECT"
        expected_part_idx = idx if is_tune else (idx - 20)
        expected_label = "W06_DEV_TUNE" if is_tune else "W06_DEV_SELECT"

        if f_obj.get("fixture_label") != expected_label:
            errors.append(
                f"Fixture {idx} fixture_label {f_obj.get('fixture_label')!r} != {expected_label!r}"
            )
        if f_obj.get("currency") != "VND" or f_obj.get("allow_revisit_place_ids") is not False:
            errors.append(f"Fixture {idx} currency or allow_revisit_place_ids invalid")

        dest = f_obj["destination_slug"]
        if f_obj["destination"] != PRIMARY_BENCHMARK_DESTINATIONS.get(dest):
            errors.append(f"Fixture {idx} destination display name mismatch for {dest}")
        days = int(f_obj["days"])
        interests = list(f_obj["interests"])
        if interests != sorted(interests) or len(set(interests)) != len(interests):
            errors.append(f"Fixture {idx} interests not sorted/unique: {interests}")
        if not (1 <= len(interests) <= 3) or any(
            i not in CANONICAL_BENCHMARK_INTERESTS for i in interests
        ):
            errors.append(f"Fixture {idx} non-canonical interests: {interests}")

        b_tier = _derive_budget_tier(f_obj["budget"], days)
        wk = _derive_weekend_exposure(f_obj["start_date"], f_obj["end_date"], days)
        style = f_obj["travel_style"]
        ints_tuple = tuple(interests)

        # Independent Rule A & Rule B check from catalog
        dest_sets = catalog_index[dest]
        counts = [len(dest_sets[i]) for i in ints_tuple]
        sum_supp = sum(counts)
        union_supp = len(set().union(*(dest_sets[i] for i in ints_tuple)))
        r_a = all(c >= days for c in counts)
        r_b = (union_supp >= 2 * days) and (sum_supp >= 2 * days)
        if not r_a:
            rule_a_failures += 1
        if not r_b:
            rule_b_failures += 1
        if not (r_a and r_b):
            sc = "EXCLUDED"
            excluded_count += 1
        elif any(days <= c < 2 * days for c in counts):
            sc = "STRESS"
        else:
            sc = "CLEAR"

        sig_tuple = (dest, days, ints_tuple, b_tier, wk, style)
        if sig_tuple in seen_dev_sigs:
            dev_duplicate_sigs += 1
        seen_dev_sigs.add(sig_tuple)

        if sig_tuple in final_exact_sigs:
            final_exact_overlap_count += 1

        is_near = (dest, days, ints_tuple, b_tier) in final_near_keys
        if is_tune and is_near:
            dev_tune_near_overlap_count += 1
        elif (not is_tune) and is_near:
            dev_select_near_overlap_count += 1

        combo_reuse[(dest, ints_tuple)] += 1

        # Verify manifest 1:1 agreement
        scen_sha = _sha256_bytes(_canonical_json_lf_bytes(f_obj))
        expected_sig_list = [dest, days, list(ints_tuple), b_tier, wk, style]
        if (
            m_obj.get("partition") != expected_part
            or m_obj.get("partition_index") != expected_part_idx
            or m_obj.get("global_index") != idx
            or m_obj.get("scenario_id") != f_obj["scenario_id"]
            or m_obj.get("scenario_sha256") != scen_sha
            or m_obj.get("destination_slug") != dest
            or m_obj.get("days") != days
            or m_obj.get("interest_count") != len(ints_tuple)
            or m_obj.get("sorted_interests") != list(ints_tuple)
            or m_obj.get("budget_tier_or_null") != b_tier
            or m_obj.get("travel_style") != style
            or m_obj.get("weekend_exposure") != wk
            or m_obj.get("support_class") != sc
            or m_obj.get("canonical_signature") != expected_sig_list
        ):
            errors.append(f"Manifest entry {idx} semantic/hash mismatch against bundle fixture")

        rec = {
            "destination_slug": dest,
            "days": days,
            "interest_count": len(ints_tuple),
            "budget_tier_or_null": b_tier,
            "travel_style": style,
            "weekend_exposure": wk,
        }
        if is_tune:
            tune_records.append(rec)
        else:
            select_records.append(rec)

    # 6. Verify exact marginals
    actual_tune_marginals = _independent_marginal_counts(tune_records)
    actual_select_marginals = _independent_marginal_counts(select_records)
    if actual_tune_marginals != LOCKED_DEV_TUNE_MARGINALS:
        errors.append(
            f"DEV-TUNE marginals mismatch: {actual_tune_marginals} != {LOCKED_DEV_TUNE_MARGINALS}"
        )
    if actual_select_marginals != LOCKED_DEV_SELECT_MARGINALS:
        errors.append(
            f"DEV-SELECT marginals mismatch: {actual_select_marginals} != {LOCKED_DEV_SELECT_MARGINALS}"
        )

    if rule_a_failures != 0:
        errors.append(f"Rule A failures: {rule_a_failures}")
    if rule_b_failures != 0:
        errors.append(f"Rule B failures: {rule_b_failures}")
    if excluded_count != 0:
        errors.append(f"EXCLUDED combinations used: {excluded_count}")
    if dev_duplicate_sigs != 0 or len(seen_dev_sigs) != 80:
        errors.append(
            f"Duplicate DEV exact signatures found: {dev_duplicate_sigs} (unique={len(seen_dev_sigs)})"
        )
    if final_exact_overlap_count != 0:
        errors.append(f"Exact overlap with final 100 found: {final_exact_overlap_count}")
    if dev_tune_near_overlap_count != 0:
        errors.append(f"DEV-TUNE near-overlap with final 100 found: {dev_tune_near_overlap_count}")

    expected_select_near_rate = round(dev_select_near_overlap_count / 60, 6)

    # 7. Verify overlap receipt and freeze receipt fields and leakage absence
    if (
        overlap_data.get("task_id") != "W06-DEV-FIXTURE-FREEZE-01"
        or overlap_data.get("final_bundle_sha256")
        != EXPECTED_AUTHORITY_HASHES["data/evaluation/w06/w06_scenarios_freeze_v1.json"]
        or overlap_data.get("dev_bundle_sha256") != bundle_sha
        or overlap_data.get("dev_manifest_sha256") != manifest_sha
        or overlap_data.get("dev_fixture_seed") != DEV_FIXTURE_GENERATION_SEED
        or overlap_data.get("total_dev_count") != 80
        or overlap_data.get("dev_tune_count") != 20
        or overlap_data.get("dev_select_count") != 60
        or overlap_data.get("all_dev_exact_overlap_with_final") != 0
        or overlap_data.get("dev_tune_near_overlap_with_final") != 0
        or overlap_data.get("dev_select_near_overlap_with_final") != dev_select_near_overlap_count
        or overlap_data.get("dev_select_near_overlap_rate") != expected_select_near_rate
        or overlap_data.get("all_dev_unique_exact_signatures") is not True
        or overlap_data.get("final_semantics_printed_to_operator_logs") is not False
    ):
        errors.append("Overlap receipt field verification failed")

    # Verify receipts do not contain any final-100 scenario IDs or per-scenario SHA256s
    overlap_text = overlap_raw.decode("utf-8")
    receipt_text = receipt_raw.decode("utf-8")
    for fid in final_scenario_ids:
        if fid in overlap_text or fid in receipt_text:
            errors.append(f"Final scenario ID {fid} leaked in receipt")
            break
    for fsha in final_scenario_shas:
        if fsha in overlap_text or fsha in receipt_text:
            errors.append("Final per-scenario SHA256 leaked in receipt")
            break

    if (
        receipt_data.get("base_develop_sha") != "2873b161b241573cf9d5db2df64b3e1594a1a595"
        or receipt_data.get("seed") != DEV_FIXTURE_GENERATION_SEED
        or receipt_data.get("provider_calls") != 0
        or receipt_data.get("winning_model_selected") is not False
        or receipt_data.get("preregistration_created") is not False
        or receipt_data.get("final_benchmark_executed") is not False
        or receipt_data.get("generated_artifacts", {}).get("dev_bundle_sha256") != bundle_sha
        or receipt_data.get("generated_artifacts", {}).get("dev_manifest_sha256") != manifest_sha
        or receipt_data.get("generated_artifacts", {}).get("overlap_receipt_sha256") != overlap_sha
    ):
        errors.append("DEV freeze receipt field verification failed")

    # 8. Two-run temporary directory determinism check
    det_run_1_sha: Optional[str] = None
    det_run_2_sha: Optional[str] = None
    det_match = False
    if run_determinism_check:
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            r1 = write_frozen_dev_fixture_files(output_dir=Path(tmp1))
            r2 = write_frozen_dev_fixture_files(output_dir=Path(tmp2))
            det_run_1_sha = _sha256_bytes(Path(r1["bundle_path"]).read_bytes())
            det_run_2_sha = _sha256_bytes(Path(r2["bundle_path"]).read_bytes())
            m1_sha = _sha256_bytes(Path(r1["manifest_path"]).read_bytes())
            m2_sha = _sha256_bytes(Path(r2["manifest_path"]).read_bytes())
            o1_sha = _sha256_bytes(Path(r1["overlap_path"]).read_bytes())
            o2_sha = _sha256_bytes(Path(r2["overlap_path"]).read_bytes())
            f1_sha = _sha256_bytes(Path(r1["receipt_path"]).read_bytes())
            f2_sha = _sha256_bytes(Path(r2["receipt_path"]).read_bytes())
            det_match = (
                det_run_1_sha == det_run_2_sha == bundle_sha
                and m1_sha == m2_sha == manifest_sha
                and o1_sha == o2_sha == overlap_sha
                and f1_sha == f2_sha == receipt_sha
            )
            if not det_match:
                errors.append("Two-run temporary-directory determinism check failed")

    max_combo_reuse = max(combo_reuse.values()) if combo_reuse else 0
    mean_combo_reuse = (
        round(sum(combo_reuse.values()) / len(combo_reuse), 6) if combo_reuse else 0.0
    )

    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "seed": DEV_FIXTURE_GENERATION_SEED,
        "total_dev_count": len(fixtures),
        "dev_tune_count": len(tune_records),
        "dev_select_count": len(select_records),
        "dev_bundle_sha256": bundle_sha,
        "dev_manifest_sha256": manifest_sha,
        "overlap_receipt_sha256": overlap_sha,
        "freeze_receipt_sha256": receipt_sha,
        "dev_tune_marginals": actual_tune_marginals,
        "dev_select_marginals": actual_select_marginals,
        "rule_a_failures": rule_a_failures,
        "rule_b_failures": rule_b_failures,
        "excluded_count": excluded_count,
        "dev_duplicate_exact_signatures": dev_duplicate_sigs,
        "final_exact_overlap_count": final_exact_overlap_count,
        "dev_tune_near_overlap_count": dev_tune_near_overlap_count,
        "dev_select_near_overlap_count": dev_select_near_overlap_count,
        "dev_select_near_overlap_rate": expected_select_near_rate,
        "max_interest_combination_reuse": max_combo_reuse,
        "mean_interest_combination_reuse": mean_combo_reuse,
        "determinism_run_1_dev_bundle_sha": det_run_1_sha,
        "determinism_run_2_dev_bundle_sha": det_run_2_sha,
        "determinism_match": det_match,
        "authorities_unchanged": all(authority_status.values()),
    }


def main() -> int:
    report = verify_w06_dev_fixture_freeze_independently(run_determinism_check=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
