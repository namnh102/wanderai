"""Tests for W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-PROVIDER-READINESS-AND-PRICING-PREP (including Corrective 01)."""

from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
import re
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import PlanBeforeLiveProtocolError  # noqa: E402
from app.evaluation.dev_selection_harness import (  # noqa: E402
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import prepare_w06_dev_select_amendment_01_provider_readiness_pricing as prep_mod  # noqa: E402
from prepare_w06_dev_select_execution_environment_amendment_01 import (  # noqa: E402
    NetworkKillSwitchGuard,
)


def _load_json(rel_path: str) -> tuple[dict, str]:
    path = REPO_ROOT / rel_path
    assert path.is_file(), f"Missing required file: {rel_path}"
    raw = normalize_lf_bytes(path.read_bytes())
    return json.loads(raw.decode("utf-8")), sha256_bytes(raw)


def test_upstream_authorities_and_scientific_bundle_unchanged() -> None:
    """Verify approval receipt, decision, canary, prep, primary results, and scientific bundle are unchanged."""
    with NetworkKillSwitchGuard():
        app_json, app_sha = _load_json(prep_mod.APPROVAL_RECEIPT_REL_PATH)
        assert app_sha == prep_mod.EXPECTED_APPROVAL_RECEIPT_FILE_SHA256
        assert (
            app_json["approval_receipt_internal_sha256"]
            == prep_mod.EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256
        )

        dec_json, dec_sha = _load_json(prep_mod.DECISION_ARTIFACT_REL_PATH)
        assert dec_sha == prep_mod.EXPECTED_DECISION_ARTIFACT_FILE_SHA256
        assert (
            dec_json["decision_artifact_internal_sha256"]
            == prep_mod.EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256
        )

        can_json, can_sha = _load_json(prep_mod.CANARY_MANIFEST_REL_PATH)
        assert can_sha == prep_mod.EXPECTED_CANARY_MANIFEST_FILE_SHA256
        assert (
            can_json["canary_manifest_internal_sha256"]
            == prep_mod.EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256
        )

        p_json, p_sha = _load_json(prep_mod.PREP_ARTIFACT_REL_PATH)
        assert p_sha == prep_mod.EXPECTED_PREP_ARTIFACT_FILE_SHA256
        assert (
            p_json["prep_artifact_internal_sha256"]
            == prep_mod.EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256
        )

        rec_json, rec_sha = _load_json(
            prep_mod.PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH
        )
        assert rec_sha == prep_mod.EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256
        assert (
            rec_json["results_freeze_receipt_sha256"]
            == prep_mod.EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256
        )

        man_json, man_sha = _load_json(prep_mod.PRIMARY_RESULTS_MANIFEST_REL_PATH)
        assert man_sha == prep_mod.EXPECTED_PRIMARY_RESULTS_MANIFEST_FILE_SHA256
        assert (
            man_json["results_manifest_sha256"]
            == prep_mod.EXPECTED_PRIMARY_RESULTS_MANIFEST_INTERNAL_SHA256
        )

        assert (
            compute_scientific_code_bundle_sha256()
            == prep_mod.EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        )


def test_primary_metric_authority_and_erroneous_report_rejection() -> None:
    """Verify primary metrics are 1/60, 8/60, 0/60 and erroneous 0/60, 43/60, 0/60 is rejected."""
    with NetworkKillSwitchGuard():
        auth = prep_mod.read_and_crosscheck_primary_metric_authority(REPO_ROOT)
        for metric_name in (
            "VALID_RUN_AND_SCHEMA",
            "EXACT_GROUNDING_PASS",
            "FINAL_CORE_PASS",
        ):
            rates = auth["verified_metrics"][metric_name]["rates_by_candidate"]
            assert rates == {"C1": "1/60", "C2": "8/60", "C3": "0/60"}
            assert (
                auth["verified_metrics"][metric_name]["cross_checked_identical"]
                is True
            )

        with pytest.raises(
            PlanBeforeLiveProtocolError,
            match="REPORT_CORRECTION_FIREWALL_VIOLATION",
        ):
            prep_mod.validate_primary_metric_tuple(
                {"C1": "0/60", "C2": "43/60", "C3": "0/60"}
            )

        with pytest.raises(PlanBeforeLiveProtocolError):
            prep_mod.validate_primary_metric_tuple(
                {"C1": "2/60", "C2": "8/60", "C3": "0/60"}
            )


def test_exact_candidates_policy_and_call_budget_invariance() -> None:
    """Verify exact frozen candidates, Option B / 180s / 2000ms / retry0, and 9 + 180 = 189 (63/candidate)."""
    prep_json, _ = _load_json(prep_mod.PROVIDER_READINESS_PRICING_PREP_REL_PATH)
    assert prep_json["exact_frozen_candidates"] == {
        "C1": {"provider": "GOOGLE", "model": "gemini-3.8-flash"},
        "C2": {"provider": "OPENAI", "model": "gpt-6.1-sol"},
        "C3": {"provider": "ANTHROPIC", "model": "claude-sonnet-5-5"},
    }
    pol = prep_json["immutable_approved_amendment_policy"]
    assert (
        pol["track_classification"]
        == "SECONDARY_POST_HOC_EXECUTION_ENVIRONMENT_STABILIZATION_TRACK"
    )
    assert pol["fairness_policy"] == "OPTION_B_CONSERVATIVE_RELIABILITY_ENVIRONMENT"
    assert pol["timeout_policy"] == "T3_CANDIDATE_180S"
    assert pol["timeout_ms"] == 180000
    assert pol["pacing_policy"] == "P1_FIXED_2000MS_INTER_CALL_DELAY"
    assert pol["inter_call_delay_ms"] == 2000
    assert pol["pacing_fixed"] is True
    assert pol["pacing_deterministic"] is True
    assert pol["pacing_adaptive"] is False
    assert pol["pacing_response_dependent"] is False
    assert pol["retry_policy"] == "R0_STRICT_ZERO_RETRY"
    assert pol["automatic_retry"] == 0
    assert pol["sdk_retry"] == 0
    assert pol["transport_retry"] == 0
    assert pol["manual_retry"] == 0
    assert pol["repair"] == 0
    assert pol["fallback"] is False
    assert (
        pol["fixture_policy"]
        == "POLICY_F3_ENGINEERING_READINESS_SUBSET_PLUS_AMENDED_COMPARATIVE_SET"
    )
    assert pol["call_budget_policy"] == "S2_READINESS_CANARY_PLUS_COMPARATIVE_180"
    assert pol["canary_calls"] == 9
    assert pol["comparative_calls"] == 180
    assert pol["maximum_generation_calls"] == 189
    assert pol["canary_calls"] + pol["comparative_calls"] == 189
    assert pol["maximum_calls_per_candidate"] == 63


def test_public_pricing_snapshot_sources_models_and_google_billing_surface_guard() -> None:
    """Verify official allowlisted domains, exact model IDs, timestamps, and fail-closed Google billing guard."""
    snap_json, _ = _load_json(prep_mod.PUBLIC_PRICING_SNAPSHOT_REL_PATH)
    assert snap_json["contains_copyrighted_full_webpage_dump"] is False
    assert snap_json["forbidden_google_cloud_domain_used"] is False
    assert snap_json["live_provider_calls_new"] == 0
    assert snap_json["env_file_read"] is False
    assert snap_json["api_keys_inspected"] is False

    cands = snap_json["candidates"]
    assert cands["C1"]["exact_model_id"] == "gemini-3.8-flash"
    assert cands["C2"]["exact_model_id"] == "gpt-6.1-sol"
    assert cands["C3"]["exact_model_id"] == "claude-sonnet-5-5"

    for cid in ("C1", "C2", "C3"):
        assert cands[cid]["retrieval_timestamp_utc"].endswith("Z")
        assert cands[cid]["selected_as_applicable_to_frozen_w06_config"] is True

    assert (
        cands["C1"]["selected_unit_pricing_usd_per_1m_tokens"][
            "input_usd_per_1m_tokens"
        ]
        == "0.75"
    )
    assert (
        cands["C1"]["selected_unit_pricing_usd_per_1m_tokens"][
            "output_including_thinking_usd_per_1m_tokens"
        ]
        == "3.75"
    )
    assert (
        cands["C2"]["selected_unit_pricing_usd_per_1m_tokens"][
            "input_usd_per_1m_tokens"
        ]
        == "2.00"
    )
    assert (
        cands["C2"]["selected_unit_pricing_usd_per_1m_tokens"][
            "output_including_reasoning_usd_per_1m_tokens"
        ]
        == "10.00"
    )
    assert (
        cands["C2"]["selected_unit_pricing_usd_per_1m_tokens"][
            "cached_input_usd_per_1m_tokens"
        ]
        == "0.10"
    )
    assert (
        cands["C3"]["selected_unit_pricing_usd_per_1m_tokens"][
            "input_usd_per_1m_tokens"
        ]
        == "2.00"
    )
    assert (
        cands["C3"]["selected_unit_pricing_usd_per_1m_tokens"][
            "output_including_thinking_usd_per_1m_tokens"
        ]
        == "10.00"
    )
    assert (
        cands["C3"]["non_applicable_pricing_dimensions"]["prompt_caching"][
            "applicable_to_frozen_w06_config"
        ]
        is False
    )

    # Reject non-allowlisted domains or cloud.google.com for C1
    bad_records = copy.deepcopy(cands)
    bad_records["C1"]["official_source_url"] = (
        "https://cloud.google.com/vertex-ai/pricing"
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError, match="cloud.google.com is forbidden"
    ):
        prep_mod.validate_pricing_source_urls(bad_records)

    bad_records_2 = copy.deepcopy(cands)
    bad_records_2["C2"]["official_source_url"] = (
        "https://reddit.com/r/openai/pricing"
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="Disallowed direct pricing authority domain",
    ):
        prep_mod.validate_pricing_source_urls(bad_records_2)

    # Verify Google billing surface fail-closed behavior when ambiguous or Vertex AI
    ambiguous = prep_mod.resolve_google_billing_surface_or_fail_closed(
        vertexai_enabled=True,
        endpoint_path="/v1beta/models/gemini-3.8-flash:generateContent",
        observed_quota_metric="aiplatform.googleapis.com/generate_content_requests",
        observed_rate_limit_doc_url="https://cloud.google.com/vertex-ai/docs/quotas",
    )
    assert (
        ambiguous["pricing_status"]
        == "BILLING_SURFACE_NOT_YET_DETERMINISTICALLY_RESOLVED"
    )


def test_anthropic_direct_authority_boundary_and_redirect_handling() -> None:
    """Verify Anthropic direct authority allowlist excludes platform.claude.com while allowing bound redirects and binding exact C3 anthropic.com sources."""
    assert prep_mod.ALLOWLISTED_PRICING_DOMAINS_BY_PROVIDER["ANTHROPIC"] == (
        "docs.anthropic.com",
        "anthropic.com",
    )
    assert (
        "platform.claude.com"
        not in prep_mod.ALLOWLISTED_PRICING_DOMAINS_BY_PROVIDER["ANTHROPIC"]
    )

    snap_json, _ = _load_json(prep_mod.PUBLIC_PRICING_SNAPSHOT_REL_PATH)
    cands = snap_json["candidates"]
    c3 = cands["C3"]

    assert (
        c3["exact_model_official_source_url"]
        == "https://www.anthropic.com/claude/sonnet"
    )
    assert (
        "https://www.anthropic.com/claude/sonnet"
        in c3["additional_official_source_urls"]
    )
    assert (
        "https://www.anthropic.com/claude-sonnet-5-5"
        in c3["additional_official_source_urls"]
    )
    ev = c3["exact_model_anthropic_com_evidence"]
    assert ev["verified_api_model_id"] == "claude-sonnet-5-5"
    assert ev["verified_input_usd_per_1m_tokens"] == "2.00"
    assert ev["verified_output_usd_per_1m_tokens"] == "10.00"
    assert ev["verified_cache_read_usd_per_1m_tokens_non_applicable"] == "0.10"

    # Legitimate docs.anthropic.com -> platform.claude.com redirect passes
    prep_mod.validate_pricing_source_urls(cands)

    # Arbitrary direct platform.claude.com URL in official_source_url is rejected
    bad_direct = copy.deepcopy(cands)
    bad_direct["C3"]["official_source_url"] = (
        "https://platform.claude.com/docs/en/about-claude/pricing"
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="Disallowed direct pricing authority domain 'platform.claude.com'",
    ):
        prep_mod.validate_pricing_source_urls(bad_direct)

    # Arbitrary direct platform.claude.com URL in additional_official_source_urls is rejected
    bad_additional = copy.deepcopy(cands)
    bad_additional["C3"]["additional_official_source_urls"].append(
        "https://platform.claude.com/arbitrary-page"
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="Disallowed direct pricing authority domain 'platform.claude.com'",
    ):
        prep_mod.validate_pricing_source_urls(bad_additional)

    # Unbound redirect entry (not tied to an allowlisted direct source URL) is rejected
    bad_redirect_unbound = copy.deepcopy(cands)
    bad_redirect_unbound["C3"]["official_redirect_resolutions"].append(
        {
            "allowlisted_source_url": "https://docs.anthropic.com/en/docs/unlisted-page",
            "resolved_destination_url": "https://platform.claude.com/docs/en/unlisted-page",
        }
    )
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="is not bound to an allowlisted direct source URL",
    ):
        prep_mod.validate_pricing_source_urls(bad_redirect_unbound)


def test_machine_to_human_markdown_cost_consistency_and_no_duplicate_constants() -> None:
    """Verify every Markdown cost cell equals canonical JSON cost_analysis and no duplicate cost constants exist in the renderer."""
    with NetworkKillSwitchGuard():
        snap_json, _ = _load_json(prep_mod.PUBLIC_PRICING_SNAPSHOT_REL_PATH)
        prep_json, _ = _load_json(
            prep_mod.PROVIDER_READINESS_PRICING_PREP_REL_PATH
        )
        cost_analysis = prep_json["cost_analysis"]

        # Verify exact authoritative JSON cost values
        assert cost_analysis["A_readiness_canary_9_calls"][
            "EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE"
        ]["by_candidate_usd"] == {
            "C1": "0.129986",
            "C2": "0.213327",
            "C3": "0.370762",
        }
        assert (
            cost_analysis["A_readiness_canary_9_calls"][
                "EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE"
            ]["total_usd"]
            == "0.714076"
        )
        assert cost_analysis["B_amended_comparative_180_calls"][
            "EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE"
        ]["by_candidate_usd"] == {
            "C1": "2.599729",
            "C2": "4.266544",
            "C3": "7.415247",
        }
        assert (
            cost_analysis["B_amended_comparative_180_calls"][
                "EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE"
            ]["total_usd"]
            == "14.281520"
        )
        assert cost_analysis["C_total_amendment_track_189_calls"][
            "EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE"
        ]["by_candidate_usd"] == {
            "C1": "2.729715",
            "C2": "4.479871",
            "C3": "7.786009",
        }
        assert (
            cost_analysis["C_total_amendment_track_189_calls"][
                "EXPECTED_OR_EMPIRICAL_PLANNING_ESTIMATE"
            ]["total_usd"]
            == "14.995596"
        )

        # Render markdown and compare with disk markdown
        rendered_md = prep_mod.build_markdown_report(snap_json, prep_json)
        disk_md = (
            REPO_ROOT / prep_mod.PROVIDER_READINESS_PRICING_PREP_DOC_REL_PATH
        ).read_text(encoding="utf-8")
        assert rendered_md == disk_md

        # Verify every single cell across all 3 scopes and 3 categories
        prep_mod.verify_markdown_cost_consistency(cost_analysis, disk_md)
        extracted = prep_mod.parse_markdown_cost_table_values(disk_md)
        assert len(extracted) == 9

        # Reject all 5 stale/drifted cost values anywhere in Markdown or script
        stale_values = (
            "0.129987",
            "2.599736",
            "14.281527",
            "2.729723",
            "14.995603",
        )
        script_src = Path(prep_mod.__file__).read_text(encoding="utf-8")
        for stale in stale_values:
            assert stale not in disk_md, f"Stale value {stale} found in Markdown"
            assert stale not in script_src, f"Stale value {stale} found in script"

        # Prove build_markdown_report contains zero hard-coded cost decimal literals
        renderer_src = inspect.getsource(prep_mod.build_markdown_report)
        assert re.search(r"\b\d+\.\d{4,6}\b", renderer_src) is None

        # Prove a single-digit drift in Markdown or JSON fails verification immediately
        drifted_md = disk_md.replace("`$0.129986`", "`$0.129987`", 1)
        with pytest.raises(
            PlanBeforeLiveProtocolError, match="Markdown vs JSON cost drift"
        ):
            prep_mod.verify_markdown_cost_consistency(cost_analysis, drifted_md)


def test_openai_long_context_and_hard_maximum_status() -> None:
    """Verify OpenAI long-context surcharge status is NOT_APPLICABLE_PROVEN and HARD_MAXIMUM_STATUS is NOT_DEFENSIBLY_COMPUTABLE."""
    prep_json, _ = _load_json(prep_mod.PROVIDER_READINESS_PRICING_PREP_REL_PATH)
    lc = prep_json["openai_long_context_check"]
    assert lc["openai_long_context_surcharge_status"] == "NOT_APPLICABLE_PROVEN"
    assert lc["threshold_input_tokens"] == 272000

    ca = prep_json["cost_analysis"]
    assert ca["planning_envelope_is_hard_maximum"] is False
    assert ca["hard_maximum_status"] == "NOT_DEFENSIBLY_COMPUTABLE"
    assert (
        ca["HISTORICAL_OBSERVED_COST_REFERENCE"]["authoritative_cost_cells"] == 9
    )
    assert (
        ca["HISTORICAL_OBSERVED_COST_REFERENCE"][
            "total_canonical_receipt_cost_usd"
        ]
        == "0.6468966"
    )
    assert (
        ca["HISTORICAL_OBSERVED_COST_REFERENCE"][
            "blind_scaling_to_189_calls_performed"
        ]
        is False
    )

    for scope_key in (
        "A_readiness_canary_9_calls",
        "B_amended_comparative_180_calls",
        "C_total_amendment_track_189_calls",
    ):
        block = ca[scope_key]
        assert (
            block["HARD_MAXIMUM"]["hard_maximum_status"]
            == "NOT_DEFENSIBLY_COMPUTABLE"
        )
        assert block["HARD_MAXIMUM"]["hard_maximum_usd"] is None
        assert (
            block["CONSERVATIVE_PLANNING_ENVELOPE"]["is_hard_maximum"] is False
        )


def test_provider_readiness_not_yet_attested_and_scientific_firewalls() -> None:
    """Verify provider readiness remains NOT_YET_ATTESTED, owner action has not occurred, and all live/scientific firewall flags hold."""
    prep_json, _ = _load_json(prep_mod.PROVIDER_READINESS_PRICING_PREP_REL_PATH)
    prm = prep_json["provider_readiness_matrix"]
    assert prm["C1_PROVIDER_READINESS"] == "NOT_YET_ATTESTED"
    assert prm["C2_PROVIDER_READINESS"] == "NOT_YET_ATTESTED"
    assert prm["C3_PROVIDER_READINESS"] == "NOT_YET_ATTESTED"
    assert prm["owner_action_occurred"] is False

    oat = prep_json["owner_attestation_template"]
    assert oat["owner_action_requested_in_this_prep_task"] is False
    assert oat["owner_attestation_executed"] is False
    for forbidden in (
        "api_key",
        "api_key_prefix",
        "secret",
        "organization_id",
        "billing_account_id",
        "credit_card_information",
    ):
        assert forbidden in oat["forbidden_fields_never_recorded"]

    flags = prep_json["scientific_and_execution_firewall_flags"]
    assert flags["AMENDMENT_METHODOLOGY_SELECTED"] is True
    assert flags["AMENDMENT_APPROVED"] is True
    assert (
        flags["effective_amendment_status"]
        == "METHODOLOGY_APPROVED_LIVE_UNAUTHORIZED"
    )
    assert flags["AMENDED_CANARY_LIVE_AUTHORIZED"] is False
    assert flags["AMENDED_COMPARATIVE_LIVE_AUTHORIZED"] is False
    assert flags["AMENDED_LIVE_AUTHORIZED"] is False
    assert flags["AMENDED_LIVE_EXECUTED"] is False
    assert flags["CANARY_EXECUTED"] is False
    assert flags["COMPARATIVE_EXECUTED"] is False
    assert flags["LIVE_PROVIDER_CALLS_NEW"] == 0
    assert flags["MODEL_WINNER_SELECTED"] is False
    assert flags["SELECTED_MODEL_ID"] is None
    assert flags["STOCHASTICITY_EXECUTION_STARTED"] is False
    assert flags["FINAL100_USED"] is False
    assert flags["FINAL100_STATUS"] == "NO-GO"
    assert flags["PRIMARY_EXPERIMENT_MUTATED"] is False
    assert flags["PRIMARY_RESULTS_REPLACED"] is False
    assert flags["PRIMARY_DENOMINATORS_CHANGED"] is False
    assert flags["OWNER_ACTION_OCCURRED"] is False
    assert flags["ENV_FILE_READ"] is False
    assert flags["API_KEYS_INSPECTED"] is False


def test_tamper_detection_on_pricing_snapshot_and_prep_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify stateless verifier detects tampering on either JSON artifact."""
    res = prep_mod.verify_provider_readiness_pricing_prep_artifacts(REPO_ROOT)
    assert res["status"] == "PASS"

    snap_src = REPO_ROOT / prep_mod.PUBLIC_PRICING_SNAPSHOT_REL_PATH
    prep_src = REPO_ROOT / prep_mod.PROVIDER_READINESS_PRICING_PREP_REL_PATH

    snap_data = json.loads(snap_src.read_text(encoding="utf-8"))
    snap_data["candidates"]["C1"]["selected_unit_pricing_usd_per_1m_tokens"][
        "input_usd_per_1m_tokens"
    ] = "9.99"

    orig_read_bytes = Path.read_bytes

    def _tampered_snap_read_bytes(self: Path) -> bytes:
        if self.resolve() == snap_src.resolve():
            return json.dumps(snap_data, indent=2, sort_keys=True).encode(
                "utf-8"
            )
        return orig_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _tampered_snap_read_bytes)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="Public pricing snapshot byte/hash tamper detected",
    ):
        prep_mod.verify_provider_readiness_pricing_prep_artifacts(REPO_ROOT)

    prep_data = json.loads(prep_src.read_text(encoding="utf-8"))
    prep_data["provider_readiness_matrix"]["C1_PROVIDER_READINESS"] = "READY"

    def _tampered_prep_read_bytes(self: Path) -> bytes:
        if self.resolve() == prep_src.resolve():
            return json.dumps(prep_data, indent=2, sort_keys=True).encode(
                "utf-8"
            )
        return orig_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _tampered_prep_read_bytes)
    with pytest.raises(
        PlanBeforeLiveProtocolError,
        match="Provider readiness/pricing PREP artifact byte/hash tamper detected",
    ):
        prep_mod.verify_provider_readiness_pricing_prep_artifacts(REPO_ROOT)
