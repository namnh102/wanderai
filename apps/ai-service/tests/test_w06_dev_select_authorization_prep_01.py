"""W06-DEV-SELECT-AUTHORIZATION-PREP-01 test suite (DSAP-01..DSAP-40 + Section 22 adversarial checks).

Strictly offline (`LIVE_PROVIDER_CALLS_NEW = 0`, `PROVIDER_COST_USD_NEW = 0`).
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import socket
import sys
import urllib.request

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from app.evaluation.dev_live_runner import PlanBeforeLiveProtocolError  # noqa: E402
from app.evaluation.dev_selection_harness import (  # noqa: E402
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    normalize_lf_bytes,
    sha256_bytes,
)
from freeze_w06_dev_prompt_candidates import (  # noqa: E402
    EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
    P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256,
)
from freeze_w06_dev_select_plan import (  # noqa: E402
    CODE_BASIS_COMMIT_SHA as PLAN_CODE_BASIS_COMMIT_SHA,
    EXPECTED_CANDIDATE_REGISTRY_SHA256,
    EXPECTED_DEV_SELECT_PLAN_FILE_SHA256,
    EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256,
    EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256,
    EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256,
)
from prepare_w06_dev_select_authorization import (  # noqa: E402
    EXPECTED_MIN_RENDERED_USER_PROMPT_BYTES,
    EXPECTED_MAX_RENDERED_USER_PROMPT_BYTES,
    EXPECTED_P1_SYSTEM_PROMPT_BYTES,
    EXPECTED_PREP_ARTIFACT_FILE_SHA256,
    EXPECTED_PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256,
    EXPECTED_RUNTIME_SDK_VERSIONS,
    EXPECTED_TOTAL_RENDERED_USER_PROMPT_BYTES_60_FIXTURES,
    HARD_MAX_COST_USD,
    PREP_ARTIFACT_REL_PATH,
    PREP_REPORT_REL_PATH,
    PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT,
    SOURCE_DEVELOP_SHA,
    NetworkKillSwitchGuard,
    OutboundNetworkBlockedError,
    assert_prep_payload_secret_free,
    build_dev_select_authorization_prep_payload,
    check_key_presence_status_only,
    check_runtime_sdk_versions,
    validate_dev_select_authorization_prep_payload,
    verify_persisted_dev_select_authorization_prep,
    verify_pre_authorization_firewall,
    verify_source_develop_provenance,
)
from select_w06_dev_tune_prompt import (  # noqa: E402
    EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256,
)


@pytest.fixture(scope="module")
def persisted_prep_payload() -> dict:
    path = REPO_ROOT / PREP_ARTIFACT_REL_PATH
    raw = normalize_lf_bytes(path.read_bytes())
    return json.loads(raw.decode("utf-8"))


# ==============================================================================
# 1. DSAP-01..DSAP-40 FAIL-CLOSED VERIFICATION SUITE (SECTION 21)
# ==============================================================================


def test_dsap_01_to_40_persisted_prep_artifact_and_checks(
    persisted_prep_payload: dict,
) -> None:
    """Verify DSAP-01..DSAP-40 against the persisted DEV-SELECT authorization-prep artifact."""
    ver = verify_persisted_dev_select_authorization_prep(REPO_ROOT)
    assert ver["verified"] is True
    assert ver["prep_artifact_file_sha256"] == EXPECTED_PREP_ARTIFACT_FILE_SHA256

    # DSAP-01: source develop exact or ancestor valid
    prov = verify_source_develop_provenance(REPO_ROOT)
    assert prov["verified"] is True
    assert persisted_prep_payload["source_develop_sha"] == SOURCE_DEVELOP_SHA

    # DSAP-02..DSAP-04: plan internal SHA, plan file SHA, plan freeze receipt SHA exact
    assert (
        persisted_prep_payload["execution_plan_internal_sha256"]
        == EXPECTED_DEV_SELECT_PLAN_INTERNAL_SHA256
    )
    assert (
        persisted_prep_payload["execution_plan_file_sha256"]
        == EXPECTED_DEV_SELECT_PLAN_FILE_SHA256
    )
    assert (
        persisted_prep_payload["plan_freeze_receipt_file_sha256"]
        == EXPECTED_PLAN_FREEZE_RECEIPT_FILE_SHA256
    )

    # DSAP-05..DSAP-07: phase DEV_SELECT, assigned_cells 180, unique_run_ids 180
    assert persisted_prep_payload["phase"] == "DEV_SELECT"
    assert persisted_prep_payload["assigned_cells"] == 180
    assert persisted_prep_payload["unique_run_ids"] == 180
    assert persisted_prep_payload["unique_cell_keys"] == 180

    # DSAP-08..DSAP-10: selected prompt P1, semantic SHA exact, prompt-selection artifact exact
    assert persisted_prep_payload["selected_prompt_id"] == "P1"
    assert persisted_prep_payload["allowed_prompt_ids"] == ["P1"]
    assert persisted_prep_payload["forbidden_prompt_ids"] == ["P0", "P2"]
    assert (
        persisted_prep_payload["selected_prompt_semantic_sha256"]
        == P1_AUTHORITATIVE_SEMANTIC_PROMPT_SHA256
    )
    assert (
        persisted_prep_payload["prompt_selection_artifact_file_sha256"]
        == EXPECTED_PROMPT_SELECTION_ARTIFACT_FILE_SHA256
    )

    # DSAP-11..DSAP-16: candidates, registries, scientific bundle, schemas
    assert persisted_prep_payload["candidate_ids"] == ["C1", "C2", "C3"]
    assert (
        persisted_prep_payload["candidate_registry_sha256"]
        == EXPECTED_CANDIDATE_REGISTRY_SHA256
    )
    assert (
        persisted_prep_payload["provider_config_registry_sha256"]
        == EXPECTED_PROVIDER_CONFIG_REGISTRY_SHA256
    )
    assert (
        persisted_prep_payload["scientific_code_bundle_sha256"]
        == EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
    )
    assert (
        persisted_prep_payload["portable_schema_v2_sha256"]
        == EXPECTED_PORTABLE_SCHEMA_V2_SHA256
    )
    assert (
        persisted_prep_payload["semantic_schema_sha256"]
        == EXPECTED_SEMANTIC_SCHEMA_SHA256
    )

    # DSAP-17: plan_code_basis_commit_sha exact c0adf74ceda9ffaf8b4ec42d299932e33f448e6a
    assert (
        persisted_prep_payload["plan_code_basis_commit_sha"]
        == PLAN_CODE_BASIS_COMMIT_SHA
    )
    assert (
        persisted_prep_payload["plan_code_commit_sha"] == PLAN_CODE_BASIS_COMMIT_SHA
    )

    # DSAP-18..DSAP-24: attempts=1, retry=0, fallback=false, repair=disabled, tools=false, max_calls=180, reserve=0
    rp = persisted_prep_payload["retry_policy"]
    cb = persisted_prep_payload["call_budget_policy"]
    assert persisted_prep_payload["attempts_per_cell"] == 1
    assert persisted_prep_payload["retry_calls"] == 0
    assert rp["fallback"] is False
    assert rp["best_of"] is False
    assert rp["llm_repair"] == 0
    assert rp["deterministic_semantic_repair"] is False
    assert rp["tools"] is False
    assert persisted_prep_payload["maximum_live_generation_calls"] == 180
    assert cb["reserve_calls_beyond_180"] == 0

    # DSAP-25..DSAP-27: dev_tune_rerun, stochasticity, final100 unauthorized
    scope = persisted_prep_payload["authorization_scope"]
    assert scope["dev_tune_rerun_authorized"] is False
    assert scope["stochasticity_authorized"] is False
    assert scope["final100_authorized"] is False
    assert (
        persisted_prep_payload["final100_firewall"]["final100_bundle_sha256"]
        == FORBIDDEN_FINAL100_BUNDLE_SHA256
    )
    assert (
        persisted_prep_payload["final100_firewall"]["p11_assignment_manifest_sha256"]
        == FORBIDDEN_P11_MANIFEST_SHA256
    )

    # DSAP-28..DSAP-33: pre-authorization firewall & zero calls
    assert persisted_prep_payload["live_authorization_artifact_created"] is False
    assert persisted_prep_payload["stage_a_created"] is False
    assert persisted_prep_payload["live_execution_capability_issued"] is False
    assert persisted_prep_payload["production_provider_transport_constructed"] is False
    assert (
        persisted_prep_payload["pre_authorization_firewall"][
            "dev_select_live_result_directory_created"
        ]
        is False
    )
    assert persisted_prep_payload["live_provider_calls_new"] == 0
    assert persisted_prep_payload["provider_cost_usd_new"] == 0

    # DSAP-34..DSAP-37: key presence secret-free, SDK versions recorded, 60-fixture P1 cost workload, hard max cost truthful
    assert set(persisted_prep_payload["key_presence_status"].values()) <= {
        "PRESENT",
        "MISSING",
    }
    assert (
        persisted_prep_payload["runtime_sdk_version_evidence"][
            "expected_frozen_versions"
        ]
        == EXPECTED_RUNTIME_SDK_VERSIONS
    )
    byte_stats = persisted_prep_payload["cost_envelope"][
        "rendered_prompt_utf8_byte_statistics_across_60_dev_select_fixtures"
    ]
    assert byte_stats["fixture_count"] == 60
    assert byte_stats["prompt_id"] == "P1"
    assert byte_stats["total_cells"] == 180
    assert (
        byte_stats["min_rendered_user_prompt_utf8_bytes"]
        == EXPECTED_MIN_RENDERED_USER_PROMPT_BYTES
    )
    assert (
        byte_stats["max_rendered_user_prompt_utf8_bytes"]
        == EXPECTED_MAX_RENDERED_USER_PROMPT_BYTES
    )
    assert (
        byte_stats["total_rendered_user_prompt_utf8_bytes_60_fixtures"]
        == EXPECTED_TOTAL_RENDERED_USER_PROMPT_BYTES_60_FIXTURES
    )
    assert (
        byte_stats["p1_system_prompt_utf8_bytes"] == EXPECTED_P1_SYSTEM_PROMPT_BYTES
    )
    assert persisted_prep_payload["hard_max_cost_usd"] == HARD_MAX_COST_USD

    # DSAP-38..DSAP-40: exact authorization sentence, exact SHA256, status NOT_GRANTED
    assert (
        persisted_prep_payload["proposed_project_owner_authorization_text"]
        == PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT
    )
    assert (
        persisted_prep_payload["proposed_project_owner_authorization_text_sha256"]
        == EXPECTED_PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256
    )
    assert (
        hashlib.sha256(
            persisted_prep_payload["proposed_project_owner_authorization_text"].encode(
                "utf-8"
            )
        ).hexdigest()
        == EXPECTED_PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256
    )
    assert (
        persisted_prep_payload["project_owner_authorization_status"] == "NOT_GRANTED"
    )

    dsap_checks = persisted_prep_payload["dsap_checks"]
    assert len(dsap_checks) == 40
    assert all(v == "PASS" for v in dsap_checks.values())

    report_path = REPO_ROOT / PREP_REPORT_REL_PATH
    assert report_path.is_file()
    report_text = report_path.read_text(encoding="utf-8")
    assert PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT in report_text
    assert EXPECTED_PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT_SHA256 in report_text


# ==============================================================================
# 2. ADVERSARIAL / TAMPER TESTS (SECTION 22: ITEMS 1..26)
# ==============================================================================


@pytest.mark.parametrize(
    ("mutator_name", "mutate_fn"),
    [
        # 1. Wrong DEV-SELECT plan internal SHA
        (
            "wrong_plan_internal_sha",
            lambda p: p.__setitem__("execution_plan_internal_sha256", "0" * 64),
        ),
        # 2. Wrong DEV-SELECT plan file SHA
        (
            "wrong_plan_file_sha",
            lambda p: p.__setitem__("execution_plan_file_sha256", "1" * 64),
        ),
        # 3. Wrong plan-freeze receipt SHA
        (
            "wrong_plan_freeze_receipt_sha",
            lambda p: p.__setitem__("plan_freeze_receipt_file_sha256", "2" * 64),
        ),
        # 4. Prompt ID changed to P0
        (
            "prompt_id_p0",
            lambda p: p.__setitem__("selected_prompt_id", "P0"),
        ),
        # 5. Prompt ID changed to P2
        (
            "prompt_id_p2",
            lambda p: p.__setitem__("selected_prompt_id", "P2"),
        ),
        # 6. Wrong P1 semantic SHA
        (
            "wrong_p1_semantic_sha",
            lambda p: p.__setitem__("selected_prompt_semantic_sha256", "3" * 64),
        ),
        # 7. Wrong prompt-selection artifact SHA
        (
            "wrong_prompt_selection_artifact_sha",
            lambda p: p.__setitem__(
                "prompt_selection_artifact_file_sha256", "4" * 64
            ),
        ),
        # 8. Candidate list changed to [C1, C2]
        (
            "candidates_c1_c2_only",
            lambda p: p.__setitem__("candidate_ids", ["C1", "C2"]),
        ),
        # 9. Extra candidate C4 added
        (
            "extra_candidate_c4",
            lambda p: p.__setitem__("candidate_ids", ["C1", "C2", "C3", "C4"]),
        ),
        # 10. Assigned cells changed to 120 or 181
        (
            "assigned_cells_120",
            lambda p: p.__setitem__("assigned_cells", 120),
        ),
        (
            "assigned_cells_181",
            lambda p: p.__setitem__("assigned_cells", 181),
        ),
        # 11. Maximum generation calls changed to 181
        (
            "max_generation_calls_181",
            lambda p: p.__setitem__("maximum_live_generation_calls", 181),
        ),
        # 12. Retry calls changed to 1
        (
            "retry_calls_1",
            lambda p: p.__setitem__("retry_calls", 1),
        ),
        # 13. Fallback enabled
        (
            "fallback_enabled",
            lambda p: p["retry_policy"].__setitem__("fallback", True),
        ),
        # 14. Semantic repair enabled
        (
            "semantic_repair_enabled",
            lambda p: p["retry_policy"].__setitem__(
                "deterministic_semantic_repair", True
            ),
        ),
        # 15. Phase changed to DEV_TUNE
        (
            "phase_dev_tune",
            lambda p: p.__setitem__("phase", "DEV_TUNE"),
        ),
        # 16. Phase changed to STOCHASTICITY
        (
            "phase_stochasticity",
            lambda p: p.__setitem__("phase", "STOCHASTICITY"),
        ),
        # 17. Final100 authorized
        (
            "final100_authorized",
            lambda p: p["authorization_scope"].__setitem__(
                "final100_authorized", True
            ),
        ),
        # 18. DEV-TUNE rerun authorized
        (
            "dev_tune_rerun_authorized",
            lambda p: p["authorization_scope"].__setitem__(
                "dev_tune_rerun_authorized", True
            ),
        ),
        # 19. Stochasticity authorized
        (
            "stochasticity_authorized",
            lambda p: p["authorization_scope"].__setitem__(
                "stochasticity_authorized", True
            ),
        ),
        # 20. Project Owner status prematurely set to AUTHORIZED
        (
            "project_owner_status_authorized",
            lambda p: p.__setitem__(
                "project_owner_authorization_status", "AUTHORIZED"
            ),
        ),
        # 23. Authorization sentence text mutated by 1 character
        (
            "authorization_sentence_mutated_1_char",
            lambda p: p.__setitem__(
                "proposed_project_owner_authorization_text",
                PROPOSED_PROJECT_OWNER_AUTHORIZATION_TEXT[:-1] + "!",
            ),
        ),
        # 24. Authorization sentence SHA mismatch
        (
            "authorization_sentence_sha_mismatch",
            lambda p: p.__setitem__(
                "proposed_project_owner_authorization_text_sha256", "f" * 64
            ),
        ),
    ],
)
def test_adversarial_payload_mutations_rejected_fail_closed(
    persisted_prep_payload: dict,
    mutator_name: str,
    mutate_fn,
) -> None:
    """Verify Section 22 adversarial payload mutations (items 1..20, 23, 24) fail closed."""
    tampered = copy.deepcopy(persisted_prep_payload)
    mutate_fn(tampered)
    with pytest.raises(PlanBeforeLiveProtocolError):
        validate_dev_select_authorization_prep_payload(tampered, repo_root=REPO_ROOT)


def test_adversarial_21_22_stage_a_or_live_authorization_artifact_created_early(
    persisted_prep_payload: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify Section 22 items 21 & 22: Stage-A or DEV-SELECT live-authorization artifact created early fails closed."""
    # Item 21: Stage-A flag or file created early
    tampered_stage_a = copy.deepcopy(persisted_prep_payload)
    tampered_stage_a["stage_a_created"] = True
    with pytest.raises(PlanBeforeLiveProtocolError):
        validate_dev_select_authorization_prep_payload(
            tampered_stage_a, repo_root=REPO_ROOT
        )

    # Item 22: Live-authorization artifact created early
    tampered_auth = copy.deepcopy(persisted_prep_payload)
    tampered_auth["live_authorization_artifact_created"] = True
    with pytest.raises(PlanBeforeLiveProtocolError):
        validate_dev_select_authorization_prep_payload(
            tampered_auth, repo_root=REPO_ROOT
        )

    # Also test filesystem-level detection of unverified Stage-A or live_authorization files in a synthetic w06 directory
    w06_dir = tmp_path / "data" / "evaluation" / "w06"
    w06_dir.mkdir(parents=True)
    rogue_stage_a = w06_dir / "w06_dev_select_stage_a_freeze_receipt_v1.json"
    rogue_stage_a.write_text(
        json.dumps({"artifact_id": "W06-DEV-LIVE-STAGE-A-FREEZE-RECEIPT-V1"}),
        encoding="utf-8",
    )
    fw_stage_a = verify_pre_authorization_firewall(tmp_path)
    assert fw_stage_a["pre_authorization_firewall_intact"] is False
    assert fw_stage_a["dev_select_stage_a_receipt_created"] is True

    rogue_stage_a.unlink()
    rogue_auth = w06_dir / "w06_dev_select_live_authorization_v1.json"
    rogue_auth.write_text(
        json.dumps(
            {
                "authorization_id": "W06-DEV-SELECT-AUTH-ROGUE",
                "authorization_status": "AUTHORIZED",
            }
        ),
        encoding="utf-8",
    )
    fw_auth = verify_pre_authorization_firewall(tmp_path)
    assert fw_auth["pre_authorization_firewall_intact"] is False
    assert fw_auth["dev_select_live_authorization_artifact_created"] is True


def test_adversarial_25_secret_key_value_or_prefix_leak_in_key_presence_output(
    persisted_prep_payload: dict,
) -> None:
    """Verify Section 22 item 25: secret key value or prefix leak in key-presence output fails closed."""
    fake_env = {
        "GEMINI_API_KEY": "AIzaSyFAKE_SECRET_KEY_VALUE_1234567890",
        "OPENAI_API_KEY": "sk-proj-FAKE_SECRET_OPENAI_KEY_1234567890",
        "ANTHROPIC_API_KEY": "sk-ant-api03-FAKE_SECRET_ANTHROPIC_KEY_123456",
    }
    kp = check_key_presence_status_only(
        REPO_ROOT, env_override=fake_env, include_dotenv_files=False
    )
    assert kp == {
        "GEMINI_API_KEY": "PRESENT",
        "OPENAI_API_KEY": "PRESENT",
        "ANTHROPIC_API_KEY": "PRESENT",
    }
    serialized = json.dumps(kp)
    for secret_val in fake_env.values():
        assert secret_val not in serialized
        assert secret_val[:6] not in serialized

    tampered = copy.deepcopy(persisted_prep_payload)
    tampered["key_presence_status"]["OPENAI_API_KEY"] = "sk-proj-LEAKED_PREFIX"
    with pytest.raises(PlanBeforeLiveProtocolError):
        assert_prep_payload_secret_free(tampered, context="TEST_SECRET_LEAK")


def test_adversarial_26_outbound_network_attempt_during_prep_or_verify() -> None:
    """Verify Section 22 item 26: any outbound network attempt during prep or verify-only is blocked fail-closed."""
    with NetworkKillSwitchGuard() as guard:
        with pytest.raises(OutboundNetworkBlockedError):
            s = socket.socket()
            try:
                s.connect(("example.com", 443))
            finally:
                s.close()

        with pytest.raises(OutboundNetworkBlockedError):
            urllib.request.urlopen("https://example.com")

        with pytest.raises(OutboundNetworkBlockedError):
            httpx.get("https://example.com")

        assert len(guard.blocked_attempts) == 3
