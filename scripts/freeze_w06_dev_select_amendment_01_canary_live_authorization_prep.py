#!/usr/bin/env python3
"""Strictly offline Amended Canary Live Authorization Prep generator and verifier for W06 DEV-SELECT Amendment 01.

TASK: W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-AMENDED-CANARY-LIVE-AUTHORIZATION-PREP

PURPOSE:
Create and statelessly verify the strictly offline authorization-prep candidate
(`W06-DEV-SELECT-AMENDMENT-01-CANARY-LIVE-AUTHORIZATION-PREP-V1`) for the approved
9-call readiness canary of the W06 secondary post-hoc execution-environment stabilization track:
1. `data/evaluation/w06/w06_dev_select_amendment_01_canary_authorization_prep_v1.json`
2. `docs/research/w06_dev_select_amendment_01_canary_live_authorization_prep.md`

STRICT FIREWALLS:
- Preparation ONLY (`CANARY_LIVE_AUTHORIZATION_PROPOSED = true`, while effective
  `AMENDED_CANARY_LIVE_AUTHORIZED = false` until PR CI, ChatGPT audit PASS, normal merge,
  post-merge CI, and explicit live-canary execution task).
- Binds `develop@df5a76d9d3734f77bf64abbe66d9d93492fabb3c`, PR #71 merge & post-merge CI
  (`run_id = 41112477246`), Owner Provider Readiness Attestation Receipt (`91702599...` / `137aae6b...`),
  Canary Assignment Manifest (`3ce0ebaa...` / `707d99fe...`), Amendment Decision (`2e421189...` / `38dc02de...`),
  Amendment Approval Receipt (`171564d0...` / `d32e1c61...`), Provider Readiness & Pricing Prep (`ef94513c...` / `07f61e21...`),
  Public Pricing Snapshot (`2302724e...` / `bcc8daeb...`), Amendment Prep (`e8786c4f...` / `49c24e65...`),
  Primary Freeze Receipt & Manifest (`c021094e...` / `7b270de4...` and `1d303e1c...` / `4e2f8f0d...`),
  Failure Diagnostic (`b7298835...` / `50952841...`), and Scientific Code Bundle (`0638f2fc...`).
- Freezes the exact 3 candidates (`C1 = gemini-3.8-flash`, `C2 = gpt-6.1-sol`, `C3 = claude-sonnet-5-5`),
  exact 3 fixtures (`W06-DEV-TUNE-007`, `W06-DEV-TUNE-011`, `W06-DEV-TUNE-015`), exact 9-cell execution
  order (`007/C1..C3`, `011/C1..C3`, `015/C1..C3`), frozen runtime policy (`timeout_ms = 180000`,
  `inter_call_delay_ms = 2000`, zero retries across all dimensions, `fallback = false`, 1 call per cell),
  per-cell operational PASS criterion, `9/9` (`ALL_9_CANARY_OPERATIONAL_PASS == true`) aggregate rule,
  and strict fail-stop rule.
- Preserves comparative firewall (`AMENDED_COMPARATIVE_LIVE_AUTHORIZED = false`, `COMPARATIVE_EXECUTED = false`;
  canary PASS does not auto-authorize comparative; C3 comparative readiness must be rechecked).
- Preserves winner/stochasticity/Final100/primary firewalls (`MODEL_WINNER_SELECTED = false`,
  `SELECTED_MODEL_ID = null`, `STOCHASTICITY_EXECUTION_STARTED = false`, `FINAL100_USED = false`,
  `FINAL100_STATUS = "NO-GO"`, primary strict rates `C1 = 1/60`, `C2 = 8/60`, `C3 = 0/60`).
- Executes ZERO live provider calls (`LIVE_PROVIDER_CALLS_NEW = 0`, `ENV_FILE_READ = false`,
  `API_KEYS_INSPECTED = false`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    PlanBeforeLiveProtocolError,
    assert_no_secrets_in_payload,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    EXPECTED_PORTABLE_SCHEMA_V2_SHA256,
    EXPECTED_SEMANTIC_SCHEMA_SHA256,
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    canonical_json_bytes,
    compute_provider_config_registry_sha256,
    compute_scientific_code_bundle_sha256,
    load_and_verify_candidate_registry,
    load_and_verify_frozen_dev_bundle,
    normalize_lf_bytes,
    sha256_bytes,
)
import diagnose_w06_dev_select_failures as _diag_mod  # noqa: E402
import freeze_w06_dev_select_amendment_01_owner_provider_readiness_attestation as _att_mod  # noqa: E402
import freeze_w06_dev_select_execution_environment_amendment_01_approval_receipt as _app_mod  # noqa: E402
import freeze_w06_dev_select_execution_environment_amendment_01_decision as _dec_mod  # noqa: E402
import freeze_w06_dev_select_live_results as _freeze_mod  # noqa: E402
import prepare_w06_dev_select_amendment_01_provider_readiness_pricing as _prp_mod  # noqa: E402
import prepare_w06_dev_select_execution_environment_amendment_01 as _prep_mod  # noqa: E402
from prepare_w06_dev_select_execution_environment_amendment_01 import (  # noqa: E402
    NetworkKillSwitchGuard,
)


# ==============================================================================
# 1. FROZEN AUTHORITIES & CONSTANTS
# ==============================================================================

TASK_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-AMENDED-CANARY-LIVE-AUTHORIZATION-PREP"
)
PREVIOUS_GATE_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-OWNER-PROVIDER-READINESS-ATTESTATION-POSTMERGE-CHATGPT-AUDIT"
)
PREVIOUS_GATE_DECISION = "PASS"
NEXT_GATE_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-AMENDED-CANARY-LIVE-AUTHORIZATION-PREP-CHATGPT-AUDIT"
)

CANARY_AUTH_PREP_ARTIFACT_ID = (
    "W06-DEV-SELECT-AMENDMENT-01-CANARY-LIVE-AUTHORIZATION-PREP-V1"
)
CANARY_AUTH_PREP_REL_PATH = (
    "data/evaluation/w06/w06_dev_select_amendment_01_canary_authorization_prep_v1.json"
)
CANARY_AUTH_PREP_DOC_REL_PATH = (
    "docs/research/w06_dev_select_amendment_01_canary_live_authorization_prep.md"
)

AUTHORITATIVE_BASE_DEVELOP_SHA = "df5a76d9d3734f77bf64abbe66d9d93492fabb3c"
OWNER_READINESS_ATTESTATION_PR_NUMBER = 71
OWNER_READINESS_ATTESTATION_PR_STATE = "MERGED"
OWNER_READINESS_ATTESTATION_MERGE_COMMIT_SHA = (
    "df5a76d9d3734f77bf64abbe66d9d93492fabb3c"
)
OWNER_READINESS_ATTESTATION_MERGE_PARENT_1 = (
    "ef78127ef06215849861e7d3358e24cb5222281e"
)
OWNER_READINESS_ATTESTATION_MERGE_PARENT_2 = (
    "aa70f7bdea7cefee40894ba3c20f00bf9f01491d"
)
OWNER_READINESS_ATTESTATION_POST_MERGE_CI_RUN_ID = 41112477246
OWNER_READINESS_ATTESTATION_POST_MERGE_CI_EVENT = "push"
OWNER_READINESS_ATTESTATION_POST_MERGE_CI_HEAD_SHA = (
    "df5a76d9d3734f77bf64abbe66d9d93492fabb3c"
)
OWNER_READINESS_ATTESTATION_POST_MERGE_CI_CONCLUSION = "success"
OWNER_READINESS_ATTESTATION_POST_MERGE_CI_REQUIRED_JOBS: dict[str, str] = {
    "ai-service": "success",
    "backend": "success",
    "data-contract": "success",
    "mobile": "success",
}

# Bound upstream artifact paths and hashes
OWNER_READINESS_ATTESTATION_REL_PATH = _att_mod.OWNER_READINESS_ATTESTATION_REL_PATH
EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256 = (
    "91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06"
)
EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256 = (
    "137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75"
)
OWNER_READINESS_ATTESTATION_DOC_REL_PATH = (
    _att_mod.OWNER_READINESS_ATTESTATION_DOC_REL_PATH
)
EXPECTED_OWNER_READINESS_ATTESTATION_DOC_SHA256 = (
    "ed5a565ecc08446c87e61b7f980283b3411881100fc270c3280ad1a6491ec29e"
)

CANARY_MANIFEST_REL_PATH = _dec_mod.CANARY_MANIFEST_REL_PATH
EXPECTED_CANARY_MANIFEST_FILE_SHA256 = (
    "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
)
EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256 = (
    "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
)

DECISION_ARTIFACT_REL_PATH = _dec_mod.DECISION_ARTIFACT_REL_PATH
EXPECTED_DECISION_ARTIFACT_FILE_SHA256 = (
    "2e4211893c1988230e2eeb2718195d48c093da87725cd2fa074e1743ee599ddf"
)
EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256 = (
    "38dc02de2e846d4cf72108e8beacffdcfcf6308879e0ea72cca3bb83bf71387a"
)

APPROVAL_RECEIPT_REL_PATH = _app_mod.APPROVAL_RECEIPT_REL_PATH
EXPECTED_APPROVAL_RECEIPT_FILE_SHA256 = (
    "171564d09b0011ddfc0e2b70ca2f9029bf6981b944527c09331fa7f6a0f914a5"
)
EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256 = (
    "d32e1c61b130a93c5ccbf18294fc1e972c36ba4e561b7fff51a9ea13b43aa991"
)

PROVIDER_READINESS_PRICING_PREP_REL_PATH = (
    _prp_mod.PROVIDER_READINESS_PRICING_PREP_REL_PATH
)
EXPECTED_PROVIDER_READINESS_PRICING_PREP_FILE_SHA256 = (
    "ef94513ceb5d64a84da2ee3a4890e563dde19fb597e27d3e545bdbe4add58006"
)
EXPECTED_PROVIDER_READINESS_PRICING_PREP_INTERNAL_SHA256 = (
    "07f61e211c6e77ee3ed08936b04ee07ac090398e50047c7534ab30d32d24506e"
)

PUBLIC_PRICING_SNAPSHOT_REL_PATH = _prp_mod.PUBLIC_PRICING_SNAPSHOT_REL_PATH
EXPECTED_PUBLIC_PRICING_SNAPSHOT_FILE_SHA256 = (
    "2302724e26c24c7eec09ecafaa3a707bc51a45e505d4954f3661601473946cf6"
)
EXPECTED_PUBLIC_PRICING_SNAPSHOT_INTERNAL_SHA256 = (
    "bcc8daeb0d5feae6426446ffc206726f8d91c07bdad3b82df2b8bcddcacb5ffe"
)

PREP_ARTIFACT_REL_PATH = _prep_mod.PREP_ARTIFACT_REL_PATH
EXPECTED_PREP_ARTIFACT_FILE_SHA256 = (
    "e8786c4f538b86c8aa1d6b2c0cfb4afd6b8b6a1efa5b51799e44bd6bdd5a9a91"
)
EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256 = (
    "49c24e65690cb4fb947d2733ddf8b019d863046cf955d9415eec1d16e9eaaf7a"
)

PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH = _freeze_mod.RESULTS_FREEZE_RECEIPT_REL_PATH
EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256 = (
    "c021094e26277d41664c4ae2f0560b7684435b6002c5b7ba742a17808c5b07a4"
)
EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256 = (
    "7b270de482f0b077e79bbba40a0c662851da46355a18b5e05f8fdf572880943a"
)

PRIMARY_RESULTS_MANIFEST_REL_PATH = _freeze_mod.RESULTS_MANIFEST_REL_PATH
EXPECTED_PRIMARY_RESULTS_MANIFEST_FILE_SHA256 = (
    "1d303e1c07b627c3f3eb87287b744f55ba3f6d3d85bd5cec36959b01919d26c0"
)
EXPECTED_PRIMARY_RESULTS_MANIFEST_INTERNAL_SHA256 = (
    "4e2f8f0df0a6e069d65b563b8221c3ba3086bb50ad73854e9cc592a9beb05011"
)

FAILURE_DIAGNOSTIC_REL_PATH = _diag_mod.DIAGNOSTIC_ARTIFACT_REL_PATH
EXPECTED_FAILURE_DIAGNOSTIC_FILE_SHA256 = (
    "b729883505ecfc98f15917347239ea6d09cede106691b155026891996391e692"
)
EXPECTED_FAILURE_DIAGNOSTIC_INTERNAL_SHA256 = (
    "509528413e1d9eb8408943867be21f83dc2dda72acd53fe9028e3c37c7db05c8"
)

EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)

AUTHORITATIVE_PRIMARY_METRIC_RATES: dict[str, str] = {
    "C1": "1/60",
    "C2": "8/60",
    "C3": "0/60",
}
REJECTED_ERRONEOUS_REPORT_METRIC_RATES: dict[str, str] = {
    "C1": "0/60",
    "C2": "43/60",
    "C3": "0/60",
}

FROZEN_CANDIDATES: dict[str, dict[str, str]] = {
    "C1": {"provider": "GOOGLE", "provider_slug": "google", "model": "gemini-3.8-flash"},
    "C2": {"provider": "OPENAI", "provider_slug": "openai", "model": "gpt-6.1-sol"},
    "C3": {
        "provider": "ANTHROPIC",
        "provider_slug": "anthropic",
        "model": "claude-sonnet-5-5",
    },
}

CANARY_FIXTURE_IDS: tuple[str, ...] = (
    "W06-DEV-TUNE-007",
    "W06-DEV-TUNE-011",
    "W06-DEV-TUNE-015",
)

EXPECTED_CANARY_9_CELL_ORDER: tuple[tuple[int, str, str, str, str], ...] = (
    (
        1,
        "007 / C1",
        "W06-DEV-TUNE-007",
        "C1",
        "W06-AMENDMENT-01-CANARY-01-P1-C1-W06-DEV-TUNE-007",
    ),
    (
        2,
        "007 / C2",
        "W06-DEV-TUNE-007",
        "C2",
        "W06-AMENDMENT-01-CANARY-02-P1-C2-W06-DEV-TUNE-007",
    ),
    (
        3,
        "007 / C3",
        "W06-DEV-TUNE-007",
        "C3",
        "W06-AMENDMENT-01-CANARY-03-P1-C3-W06-DEV-TUNE-007",
    ),
    (
        4,
        "011 / C1",
        "W06-DEV-TUNE-011",
        "C1",
        "W06-AMENDMENT-01-CANARY-04-P1-C1-W06-DEV-TUNE-011",
    ),
    (
        5,
        "011 / C2",
        "W06-DEV-TUNE-011",
        "C2",
        "W06-AMENDMENT-01-CANARY-05-P1-C2-W06-DEV-TUNE-011",
    ),
    (
        6,
        "011 / C3",
        "W06-DEV-TUNE-011",
        "C3",
        "W06-AMENDMENT-01-CANARY-06-P1-C3-W06-DEV-TUNE-011",
    ),
    (
        7,
        "015 / C1",
        "W06-DEV-TUNE-015",
        "C1",
        "W06-AMENDMENT-01-CANARY-07-P1-C1-W06-DEV-TUNE-015",
    ),
    (
        8,
        "015 / C2",
        "W06-DEV-TUNE-015",
        "C2",
        "W06-AMENDMENT-01-CANARY-08-P1-C2-W06-DEV-TUNE-015",
    ),
    (
        9,
        "015 / C3",
        "W06-DEV-TUNE-015",
        "C3",
        "W06-AMENDMENT-01-CANARY-09-P1-C3-W06-DEV-TUNE-015",
    ),
)

CANARY_PURPOSE = "OPERATIONAL_EXECUTION_ENVIRONMENT_READINESS_CHECK"
EFFECTIVE_AMENDMENT_STATUS = (
    "METHODOLOGY_APPROVED_OWNER_CANARY_READINESS_ATTESTED_CANARY_AUTHORIZATION_PROPOSED_LIVE_UNAUTHORIZED"
)

# Deterministic self-hashes for the canary live authorization prep artifact
EXPECTED_CANARY_AUTH_PREP_FILE_SHA256 = (
    "21f9432c4c8bfa0ba5f63bdd99e8ab8c15d2802918b7e0a9c21cb5c0ccc63b61"
)
EXPECTED_CANARY_AUTH_PREP_INTERNAL_SHA256 = (
    "0f1480969d506d5b6dc16951a45cf2f8aaf913a13c011f2add6ec3e31721af61"
)

IMMUTABLE_UPSTREAM_REL_PATHS: frozenset[str] = frozenset(
    {
        OWNER_READINESS_ATTESTATION_REL_PATH,
        OWNER_READINESS_ATTESTATION_DOC_REL_PATH,
        CANARY_MANIFEST_REL_PATH,
        DECISION_ARTIFACT_REL_PATH,
        APPROVAL_RECEIPT_REL_PATH,
        PROVIDER_READINESS_PRICING_PREP_REL_PATH,
        PUBLIC_PRICING_SNAPSHOT_REL_PATH,
        PREP_ARTIFACT_REL_PATH,
        PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH,
        PRIMARY_RESULTS_MANIFEST_REL_PATH,
        FAILURE_DIAGNOSTIC_REL_PATH,
        "data/evaluation/w06/w06_scenarios_freeze_v1.json",
        "data/evaluation/w06/w06_p11_assignment_manifest_v1.json",
    }
)


# ==============================================================================
# 2. LOW-LEVEL HELPERS & UPSTREAM AUTHORITY VERIFICATION
# ==============================================================================


def _load_lf_bytes_and_sha(path: Path) -> tuple[bytes, str]:
    if not path.is_file():
        raise PlanBeforeLiveProtocolError(
            f"MISSING_REQUIRED_AUTHORITY_FILE: {path.as_posix()}"
        )
    raw = normalize_lf_bytes(path.read_bytes())
    return raw, sha256_bytes(raw)


def _load_json_and_verify_hashes(
    *,
    path: Path,
    expected_file_sha256: str,
    internal_sha_key: str,
    expected_internal_sha256: str,
    label: str,
) -> dict[str, Any]:
    raw, file_sha = _load_lf_bytes_and_sha(path)
    if file_sha != expected_file_sha256:
        raise PlanBeforeLiveProtocolError(
            f"{label}_FILE_SHA256_MISMATCH: expected {expected_file_sha256}, got {file_sha}"
        )
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise PlanBeforeLiveProtocolError(f"{label}_NOT_JSON_OBJECT")
    internal_sha = payload.get(internal_sha_key)
    if internal_sha != expected_internal_sha256:
        raise PlanBeforeLiveProtocolError(
            f"{label}_INTERNAL_SHA256_MISMATCH: expected {expected_internal_sha256}, got {internal_sha}"
        )
    body = dict(payload)
    body.pop(internal_sha_key, None)
    recomputed_internal = sha256_bytes(canonical_json_bytes(body))
    if recomputed_internal != expected_internal_sha256:
        raise PlanBeforeLiveProtocolError(
            f"{label}_INTERNAL_SHA256_RECOMPUTE_MISMATCH: expected {expected_internal_sha256}, got {recomputed_internal}"
        )
    return payload


def compute_canary_auth_prep_internal_sha256(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("canary_live_authorization_prep_internal_sha256", None)
    return sha256_bytes(canonical_json_bytes(body))


def verify_all_upstream_authorities(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify all upstream frozen artifacts, git ancestry, and scientific code bundle hashes."""
    owner_attestation = _load_json_and_verify_hashes(
        path=repo_root / OWNER_READINESS_ATTESTATION_REL_PATH,
        expected_file_sha256=EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256,
        internal_sha_key="owner_readiness_attestation_internal_sha256",
        expected_internal_sha256=EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256,
        label="OWNER_READINESS_ATTESTATION",
    )
    _, owner_doc_sha = _load_lf_bytes_and_sha(
        repo_root / OWNER_READINESS_ATTESTATION_DOC_REL_PATH
    )
    if owner_doc_sha != EXPECTED_OWNER_READINESS_ATTESTATION_DOC_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"OWNER_READINESS_ATTESTATION_DOC_SHA256_MISMATCH: expected {EXPECTED_OWNER_READINESS_ATTESTATION_DOC_SHA256}, got {owner_doc_sha}"
        )

    canary_manifest = _load_json_and_verify_hashes(
        path=repo_root / CANARY_MANIFEST_REL_PATH,
        expected_file_sha256=EXPECTED_CANARY_MANIFEST_FILE_SHA256,
        internal_sha_key="canary_manifest_internal_sha256",
        expected_internal_sha256=EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
        label="CANARY_MANIFEST",
    )

    decision_artifact = _load_json_and_verify_hashes(
        path=repo_root / DECISION_ARTIFACT_REL_PATH,
        expected_file_sha256=EXPECTED_DECISION_ARTIFACT_FILE_SHA256,
        internal_sha_key="decision_artifact_internal_sha256",
        expected_internal_sha256=EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256,
        label="DECISION_ARTIFACT",
    )

    approval_receipt = _load_json_and_verify_hashes(
        path=repo_root / APPROVAL_RECEIPT_REL_PATH,
        expected_file_sha256=EXPECTED_APPROVAL_RECEIPT_FILE_SHA256,
        internal_sha_key="approval_receipt_internal_sha256",
        expected_internal_sha256=EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256,
        label="APPROVAL_RECEIPT",
    )

    pricing_prep = _load_json_and_verify_hashes(
        path=repo_root / PROVIDER_READINESS_PRICING_PREP_REL_PATH,
        expected_file_sha256=EXPECTED_PROVIDER_READINESS_PRICING_PREP_FILE_SHA256,
        internal_sha_key="provider_readiness_pricing_prep_sha256",
        expected_internal_sha256=EXPECTED_PROVIDER_READINESS_PRICING_PREP_INTERNAL_SHA256,
        label="PROVIDER_READINESS_PRICING_PREP",
    )

    pricing_snapshot = _load_json_and_verify_hashes(
        path=repo_root / PUBLIC_PRICING_SNAPSHOT_REL_PATH,
        expected_file_sha256=EXPECTED_PUBLIC_PRICING_SNAPSHOT_FILE_SHA256,
        internal_sha_key="public_pricing_snapshot_sha256",
        expected_internal_sha256=EXPECTED_PUBLIC_PRICING_SNAPSHOT_INTERNAL_SHA256,
        label="PUBLIC_PRICING_SNAPSHOT",
    )

    prep_artifact = _load_json_and_verify_hashes(
        path=repo_root / PREP_ARTIFACT_REL_PATH,
        expected_file_sha256=EXPECTED_PREP_ARTIFACT_FILE_SHA256,
        internal_sha_key="prep_artifact_internal_sha256",
        expected_internal_sha256=EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256,
        label="PREP_ARTIFACT",
    )

    primary_freeze_receipt = _load_json_and_verify_hashes(
        path=repo_root / PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH,
        expected_file_sha256=EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
        internal_sha_key="results_freeze_receipt_sha256",
        expected_internal_sha256=EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256,
        label="PRIMARY_RESULTS_FREEZE_RECEIPT",
    )

    primary_manifest = _load_json_and_verify_hashes(
        path=repo_root / PRIMARY_RESULTS_MANIFEST_REL_PATH,
        expected_file_sha256=EXPECTED_PRIMARY_RESULTS_MANIFEST_FILE_SHA256,
        internal_sha_key="results_manifest_sha256",
        expected_internal_sha256=EXPECTED_PRIMARY_RESULTS_MANIFEST_INTERNAL_SHA256,
        label="PRIMARY_RESULTS_MANIFEST",
    )

    failure_diagnostic = _load_json_and_verify_hashes(
        path=repo_root / FAILURE_DIAGNOSTIC_REL_PATH,
        expected_file_sha256=EXPECTED_FAILURE_DIAGNOSTIC_FILE_SHA256,
        internal_sha_key="diagnostic_artifact_sha256",
        expected_internal_sha256=EXPECTED_FAILURE_DIAGNOSTIC_INTERNAL_SHA256,
        label="FAILURE_DIAGNOSTIC",
    )

    # Verify scientific code bundle, candidate registry, provider config registry, schemas, and Final100/P11 firewalls
    code_bundle_sha = compute_scientific_code_bundle_sha256()
    if code_bundle_sha != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError(
            f"SCIENTIFIC_CODE_BUNDLE_SHA256_MISMATCH: expected {EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256}, got {code_bundle_sha}"
        )

    load_and_verify_frozen_dev_bundle()
    load_and_verify_candidate_registry()
    compute_provider_config_registry_sha256()

    _, final100_sha = _load_lf_bytes_and_sha(
        repo_root / "data/evaluation/w06/w06_scenarios_freeze_v1.json"
    )
    if final100_sha != FORBIDDEN_FINAL100_BUNDLE_SHA256:
        raise PlanBeforeLiveProtocolError("FINAL100_BUNDLE_HASH_MUTATED")

    _, p11_sha = _load_lf_bytes_and_sha(
        repo_root / "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
    )
    if p11_sha != FORBIDDEN_P11_MANIFEST_SHA256:
        raise PlanBeforeLiveProtocolError("P11_MANIFEST_HASH_MUTATED")

    # Verify git ancestry & PR #71 merge commit parents when git repo is available
    git_dir = repo_root / ".git"
    if git_dir.exists():
        res_anc = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                AUTHORITATIVE_BASE_DEVELOP_SHA,
                "HEAD",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if res_anc.returncode == 0:
            p1 = subprocess.run(
                ["git", "rev-parse", f"{OWNER_READINESS_ATTESTATION_MERGE_COMMIT_SHA}^1"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            p2 = subprocess.run(
                ["git", "rev-parse", f"{OWNER_READINESS_ATTESTATION_MERGE_COMMIT_SHA}^2"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            if p1 != OWNER_READINESS_ATTESTATION_MERGE_PARENT_1:
                raise PlanBeforeLiveProtocolError(
                    f"MERGE_PARENT_1_MISMATCH: expected {OWNER_READINESS_ATTESTATION_MERGE_PARENT_1}, got {p1}"
                )
            if p2 != OWNER_READINESS_ATTESTATION_MERGE_PARENT_2:
                raise PlanBeforeLiveProtocolError(
                    f"MERGE_PARENT_2_MISMATCH: expected {OWNER_READINESS_ATTESTATION_MERGE_PARENT_2}, got {p2}"
                )

    return {
        "owner_attestation": owner_attestation,
        "canary_manifest": canary_manifest,
        "decision_artifact": decision_artifact,
        "approval_receipt": approval_receipt,
        "pricing_prep": pricing_prep,
        "pricing_snapshot": pricing_snapshot,
        "prep_artifact": prep_artifact,
        "primary_freeze_receipt": primary_freeze_receipt,
        "primary_manifest": primary_manifest,
        "failure_diagnostic": failure_diagnostic,
        "scientific_code_bundle_sha256": code_bundle_sha,
    }


# ==============================================================================
# 3. CANARY EXECUTION CONTRACT, OPERATIONAL PASS & FAIL-STOP VALIDATION
# ==============================================================================


def build_frozen_canary_execution_contract(
    canary_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Construct the frozen canary execution contract bound to the Canary Assignment Manifest."""
    manifest_cells = canary_manifest.get("cells", [])
    if len(manifest_cells) != 9:
        raise PlanBeforeLiveProtocolError(
            f"CANARY_MANIFEST_CELL_COUNT_MISMATCH: expected 9, got {len(manifest_cells)}"
        )

    ordered_cells: list[dict[str, Any]] = []
    short_order_labels: list[str] = []
    for idx, (
        expected_order_index,
        expected_short_label,
        expected_fixture_id,
        expected_candidate_id,
        expected_cell_id,
    ) in enumerate(EXPECTED_CANARY_9_CELL_ORDER):
        cell = manifest_cells[idx]
        if (
            cell.get("order_index") != expected_order_index
            or cell.get("fixture_id") != expected_fixture_id
            or cell.get("candidate_id") != expected_candidate_id
            or cell.get("cell_id") != expected_cell_id
        ):
            raise PlanBeforeLiveProtocolError(
                f"CANARY_MANIFEST_ORDER_MISMATCH_AT_{expected_order_index}: got {cell.get('cell_id')}"
            )
        cand_spec = FROZEN_CANDIDATES[expected_candidate_id]
        if (
            cell.get("provider") != cand_spec["provider_slug"]
            or cell.get("requested_model_id") != cand_spec["model"]
            or cell.get("prompt_id") != "P1"
            or cell.get("attempt_number") != 1
            or cell.get("timeout_ms") != 180000
            or cell.get("automatic_retry") != 0
            or cell.get("transport_retry") != 0
            or cell.get("manual_retry") != 0
            or cell.get("retry") != 0
            or cell.get("llm_repair") != 0
            or cell.get("semantic_repair") != 0
            or cell.get("fallback") is not False
            or cell.get("max_output_tokens") != 16384
        ):
            raise PlanBeforeLiveProtocolError(
                f"CANARY_MANIFEST_CELL_POLICY_MISMATCH_AT_{expected_order_index}"
            )
        expected_delay = 2000 if expected_order_index < 9 else 0
        if cell.get("inter_call_delay_ms_before_next_cell") != expected_delay:
            raise PlanBeforeLiveProtocolError(
                f"CANARY_MANIFEST_CELL_DELAY_MISMATCH_AT_{expected_order_index}"
            )

        short_order_labels.append(expected_short_label)
        ordered_cells.append(
            {
                "order_index": expected_order_index,
                "order_code": cell["order_code"],
                "short_label": expected_short_label,
                "matrix_label": cell["matrix_label"],
                "cell_id": expected_cell_id,
                "fixture_id": expected_fixture_id,
                "canary_fixture_slot": cell["canary_fixture_slot"],
                "destination": cell["destination"],
                "destination_slug": cell["destination_slug"],
                "days": cell["days"],
                "interest_count": cell["interest_count"],
                "candidate_id": expected_candidate_id,
                "provider": cand_spec["provider"],
                "provider_slug": cand_spec["provider_slug"],
                "requested_model_id": cand_spec["model"],
                "prompt_id": "P1",
                "attempt_number": 1,
                "generation_calls_for_cell": 1,
                "timeout_ms": 180000,
                "inter_call_delay_ms_before_next_cell": expected_delay,
                "automatic_retry": 0,
                "transport_retry": 0,
                "manual_retry": 0,
                "retry": 0,
                "llm_repair": 0,
                "semantic_repair": 0,
                "fallback": False,
                "tools": False,
                "max_output_tokens": 16384,
                "sampling_reasoning_configuration": cell[
                    "sampling_reasoning_configuration"
                ],
                "primary_baseline_provider_config_sha256": cell[
                    "primary_baseline_provider_config_sha256"
                ],
                "scenario_sha256": cell["scenario_sha256"],
                "catalog_context_sha256": cell["catalog_context_sha256"],
                "system_prompt_sha256": cell["system_prompt_sha256"],
                "user_prompt_sha256": cell["user_prompt_sha256"],
                "portable_generation_schema_v2_sha256": cell[
                    "portable_generation_schema_v2_sha256"
                ],
                "semantic_schema_sha256": cell["semantic_schema_sha256"],
                "scientific_code_bundle_sha256": cell["scientific_code_bundle_sha256"],
            }
        )

    return {
        "canary_manifest_id": canary_manifest["manifest_id"],
        "canary_manifest_file": CANARY_MANIFEST_REL_PATH,
        "canary_manifest_file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
        "canary_manifest_internal_sha256": EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
        "candidates": {
            "C1": {
                "candidate_id": "C1",
                "provider": "GOOGLE",
                "provider_slug": "google",
                "exact_model_id": "gemini-3.8-flash",
                "assigned_canary_calls": 3,
            },
            "C2": {
                "candidate_id": "C2",
                "provider": "OPENAI",
                "provider_slug": "openai",
                "exact_model_id": "gpt-6.1-sol",
                "assigned_canary_calls": 3,
            },
            "C3": {
                "candidate_id": "C3",
                "provider": "ANTHROPIC",
                "provider_slug": "anthropic",
                "exact_model_id": "claude-sonnet-5-5",
                "assigned_canary_calls": 3,
            },
        },
        "candidate_substitution_permitted": False,
        "fourth_model_permitted": False,
        "exact_canary_fixtures": list(CANARY_FIXTURE_IDS),
        "fixture_count": 3,
        "additional_fixture_permitted": False,
        "replacement_fixture_permitted": False,
        "final100_scenario_permitted": False,
        "exact_9_cell_execution_order_labels": short_order_labels,
        "ordered_canary_cells": ordered_cells,
        "total_maximum_canary_generation_calls": 9,
        "calls_per_candidate": {"C1": 3, "C2": 3, "C3": 3},
        "frozen_runtime_policy": {
            "timeout_policy_id": "T3_CANDIDATE_180S",
            "timeout_ms": 180000,
            "pacing_policy_id": "P1_FIXED_2000MS_INTER_CALL_DELAY",
            "inter_call_delay_ms": 2000,
            "total_inter_cell_pacing_intervals": 8,
            "total_inter_cell_pacing_ms": 16000,
            "retry_policy_id": "R0_STRICT_ZERO_RETRY",
            "automatic_retry": 0,
            "transport_retry": 0,
            "manual_retry": 0,
            "llm_repair": 0,
            "semantic_repair": 0,
            "fallback": False,
            "generation_calls_per_assigned_cell": 1,
            "adaptive_pacing_permitted": False,
            "dynamic_timeout_permitted": False,
            "provider_specific_special_treatment_permitted": False,
            "retry_after_timeout_429_or_5xx_permitted": False,
        },
        "canary_purpose": {
            "classification": CANARY_PURPOSE,
            "is_operational_execution_environment_readiness_check": True,
            "is_planner_quality_model_selection": False,
            "is_scientific_superiority_evaluation": False,
            "is_comparative_benchmark": False,
            "is_final100_evaluation": False,
            "interpretable_as_candidate_superiority_evidence": False,
            "selection_weight": 0,
        },
        "operational_pass_criterion_per_cell": {
            "required_operational_conditions": {
                "correct_candidate_provider_model_config_used": True,
                "exactly_one_generation_call_attempted": True,
                "retry_count_equals_zero": True,
                "no_authentication_failure": True,
                "no_billing_or_credit_failure": True,
                "no_quota_or_rate_limit_rejection": True,
                "no_model_access_failure": True,
                "no_client_timeout": True,
                "no_provider_transport_failure": True,
                "no_http_4xx_failure": True,
                "no_http_5xx_failure": True,
                "provider_returns_response": True,
                "required_provider_model_identity_evidence_captured": True,
            },
            "planner_schema_validity_is_operational_pass_criterion": False,
            "final_core_quality_is_operational_pass_criterion": False,
            "diagnostic_schema_and_quality_recording_permitted_without_redefining_operational_pass": True,
        },
        "aggregate_canary_decision_rule": {
            "required_operational_pass_cells": 9,
            "total_assigned_canary_cells": 9,
            "required_operational_pass_fraction": "9/9",
            "required_condition": "ALL_9_CANARY_OPERATIONAL_PASS == true",
            "weaker_threshold_permitted": False,
            "eight_of_nine_permitted": False,
            "majority_permitted": False,
            "two_of_three_providers_permitted": False,
            "provider_average_permitted": False,
        },
        "fail_stop_rule": {
            "fail_closed_on_any_operational_cell_failure": True,
            "preserve_exact_failure_evidence": True,
            "retry_on_failure_permitted": False,
            "replace_fixture_on_failure_permitted": False,
            "rerun_same_cell_permitted": False,
            "continue_under_improvised_rule_permitted": False,
            "rerun_because_failure_may_have_been_temporary_permitted": False,
            "comparative_remains_unauthorized_on_failure": True,
            "return_to_chatgpt_audit_on_failure": True,
        },
    }


def evaluate_canary_cell_operational_pass(
    cell_observation: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate a single canary cell observation under the frozen operational PASS criterion.

    Note: Planner schema validity and final-core quality may be recorded diagnostically
    but NEVER redefine operational PASS.
    """
    required_true_keys = (
        "correct_candidate_provider_model_config_used",
        "no_authentication_failure",
        "no_billing_or_credit_failure",
        "no_quota_or_rate_limit_rejection",
        "no_model_access_failure",
        "no_client_timeout",
        "no_provider_transport_failure",
        "no_http_4xx_failure",
        "no_http_5xx_failure",
        "provider_returns_response",
        "required_provider_model_identity_evidence_captured",
    )
    failed_conditions: list[str] = []
    if cell_observation.get("generation_calls_attempted") != 1:
        failed_conditions.append("exactly_one_generation_call_attempted")
    if cell_observation.get("retry_count") != 0:
        failed_conditions.append("retry_count_equals_zero")
    for key in required_true_keys:
        if cell_observation.get(key) is not True:
            failed_conditions.append(key)

    operational_pass = len(failed_conditions) == 0
    return {
        "operational_pass": operational_pass,
        "failed_operational_conditions": failed_conditions,
        "fail_stop_triggered": not operational_pass,
        "diagnostic_only_schema_valid": cell_observation.get(
            "diagnostic_schema_valid"
        ),
        "diagnostic_only_final_core_pass": cell_observation.get(
            "diagnostic_final_core_pass"
        ),
    }


def evaluate_aggregate_canary_operational_decision(
    cell_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate aggregate canary operational PASS (`9/9` required; fail-closed on any failure)."""
    if len(cell_results) != 9:
        return {
            "ALL_9_CANARY_OPERATIONAL_PASS": False,
            "operational_pass_count": sum(
                1 for r in cell_results if r.get("operational_pass") is True
            ),
            "total_assigned_cells": 9,
            "observed_cell_count": len(cell_results),
            "aggregate_status": "FAIL_STOP_INCOMPLETE_OR_ABORTED",
            "comparative_authorized": False,
            "must_return_to_chatgpt_audit": True,
        }
    pass_count = sum(1 for r in cell_results if r.get("operational_pass") is True)
    all_9_pass = pass_count == 9
    return {
        "ALL_9_CANARY_OPERATIONAL_PASS": all_9_pass,
        "operational_pass_count": pass_count,
        "total_assigned_cells": 9,
        "observed_cell_count": 9,
        "operational_pass_fraction": f"{pass_count}/9",
        "aggregate_status": (
            "OPERATIONAL_PASS_9_OF_9_AWAITING_CHATGPT_AUDIT"
            if all_9_pass
            else "FAIL_STOP_OPERATIONAL_FAILURE"
        ),
        "comparative_authorized": False,
        "must_return_to_chatgpt_audit": True,
    }


def validate_canary_execution_contract(contract: dict[str, Any]) -> None:
    """Validate the frozen canary execution contract against all Section 4–11 invariants."""
    cands = contract.get("candidates", {})
    if set(cands.keys()) != {"C1", "C2", "C3"}:
        raise PlanBeforeLiveProtocolError("CANARY_CANDIDATE_KEYS_MISMATCH")
    for cid, spec in FROZEN_CANDIDATES.items():
        c = cands.get(cid, {})
        if (
            c.get("candidate_id") != cid
            or c.get("provider") != spec["provider"]
            or c.get("provider_slug") != spec["provider_slug"]
            or c.get("exact_model_id") != spec["model"]
            or c.get("assigned_canary_calls") != 3
        ):
            raise PlanBeforeLiveProtocolError(
                f"CANARY_CANDIDATE_SPEC_MISMATCH: {cid}"
            )
    if (
        contract.get("candidate_substitution_permitted") is not False
        or contract.get("fourth_model_permitted") is not False
    ):
        raise PlanBeforeLiveProtocolError("CANARY_MODEL_SUBSTITUTION_FORBIDDEN")

    if (
        contract.get("exact_canary_fixtures") != list(CANARY_FIXTURE_IDS)
        or contract.get("fixture_count") != 3
        or contract.get("additional_fixture_permitted") is not False
        or contract.get("replacement_fixture_permitted") is not False
        or contract.get("final100_scenario_permitted") is not False
    ):
        raise PlanBeforeLiveProtocolError("CANARY_FIXTURE_CONTRACT_MISMATCH")

    expected_labels = [row[1] for row in EXPECTED_CANARY_9_CELL_ORDER]
    if contract.get("exact_9_cell_execution_order_labels") != expected_labels:
        raise PlanBeforeLiveProtocolError("CANARY_9_CELL_ORDER_LABELS_MISMATCH")

    ordered_cells = contract.get("ordered_canary_cells", [])
    if len(ordered_cells) != 9:
        raise PlanBeforeLiveProtocolError("CANARY_ORDERED_CELLS_COUNT_MISMATCH")
    for idx, (
        expected_order_index,
        expected_short_label,
        expected_fixture_id,
        expected_candidate_id,
        expected_cell_id,
    ) in enumerate(EXPECTED_CANARY_9_CELL_ORDER):
        cell = ordered_cells[idx]
        spec = FROZEN_CANDIDATES[expected_candidate_id]
        expected_delay = 2000 if expected_order_index < 9 else 0
        if (
            cell.get("order_index") != expected_order_index
            or cell.get("short_label") != expected_short_label
            or cell.get("fixture_id") != expected_fixture_id
            or cell.get("candidate_id") != expected_candidate_id
            or cell.get("cell_id") != expected_cell_id
            or cell.get("provider") != spec["provider"]
            or cell.get("provider_slug") != spec["provider_slug"]
            or cell.get("requested_model_id") != spec["model"]
            or cell.get("generation_calls_for_cell") != 1
            or cell.get("timeout_ms") != 180000
            or cell.get("inter_call_delay_ms_before_next_cell") != expected_delay
            or cell.get("automatic_retry") != 0
            or cell.get("transport_retry") != 0
            or cell.get("manual_retry") != 0
            or cell.get("retry") != 0
            or cell.get("llm_repair") != 0
            or cell.get("semantic_repair") != 0
            or cell.get("fallback") is not False
            or cell.get("portable_generation_schema_v2_sha256")
            != EXPECTED_PORTABLE_SCHEMA_V2_SHA256
            or cell.get("semantic_schema_sha256") != EXPECTED_SEMANTIC_SCHEMA_SHA256
            or cell.get("scientific_code_bundle_sha256")
            != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"CANARY_ORDERED_CELL_MISMATCH_AT_{expected_order_index}"
            )

    if (
        contract.get("total_maximum_canary_generation_calls") != 9
        or contract.get("calls_per_candidate") != {"C1": 3, "C2": 3, "C3": 3}
    ):
        raise PlanBeforeLiveProtocolError("CANARY_CALL_BUDGET_MISMATCH")

    rt = contract.get("frozen_runtime_policy", {})
    if (
        rt.get("timeout_ms") != 180000
        or rt.get("inter_call_delay_ms") != 2000
        or rt.get("total_inter_cell_pacing_intervals") != 8
        or rt.get("total_inter_cell_pacing_ms") != 16000
        or rt.get("automatic_retry") != 0
        or rt.get("transport_retry") != 0
        or rt.get("manual_retry") != 0
        or rt.get("llm_repair") != 0
        or rt.get("semantic_repair") != 0
        or rt.get("fallback") is not False
        or rt.get("generation_calls_per_assigned_cell") != 1
        or rt.get("adaptive_pacing_permitted") is not False
        or rt.get("dynamic_timeout_permitted") is not False
        or rt.get("provider_specific_special_treatment_permitted") is not False
        or rt.get("retry_after_timeout_429_or_5xx_permitted") is not False
    ):
        raise PlanBeforeLiveProtocolError("CANARY_RUNTIME_POLICY_MISMATCH")

    purpose = contract.get("canary_purpose", {})
    if (
        purpose.get("classification") != CANARY_PURPOSE
        or purpose.get("is_operational_execution_environment_readiness_check")
        is not True
        or purpose.get("is_planner_quality_model_selection") is not False
        or purpose.get("is_scientific_superiority_evaluation") is not False
        or purpose.get("is_comparative_benchmark") is not False
        or purpose.get("is_final100_evaluation") is not False
        or purpose.get("interpretable_as_candidate_superiority_evidence") is not False
        or purpose.get("selection_weight") != 0
    ):
        raise PlanBeforeLiveProtocolError("CANARY_PURPOSE_MISMATCH")

    op_crit = contract.get("operational_pass_criterion_per_cell", {})
    req_conds = op_crit.get("required_operational_conditions", {})
    expected_cond_keys = {
        "correct_candidate_provider_model_config_used",
        "exactly_one_generation_call_attempted",
        "retry_count_equals_zero",
        "no_authentication_failure",
        "no_billing_or_credit_failure",
        "no_quota_or_rate_limit_rejection",
        "no_model_access_failure",
        "no_client_timeout",
        "no_provider_transport_failure",
        "no_http_4xx_failure",
        "no_http_5xx_failure",
        "provider_returns_response",
        "required_provider_model_identity_evidence_captured",
    }
    if set(req_conds.keys()) != expected_cond_keys or any(
        req_conds[k] is not True for k in expected_cond_keys
    ):
        raise PlanBeforeLiveProtocolError("CANARY_OPERATIONAL_PASS_CONDITIONS_MISMATCH")
    if (
        op_crit.get("planner_schema_validity_is_operational_pass_criterion")
        is not False
        or op_crit.get("final_core_quality_is_operational_pass_criterion") is not False
        or op_crit.get(
            "diagnostic_schema_and_quality_recording_permitted_without_redefining_operational_pass"
        )
        is not True
    ):
        raise PlanBeforeLiveProtocolError(
            "CANARY_OPERATIONAL_PASS_QUALITY_SEPARATION_MISMATCH"
        )

    agg = contract.get("aggregate_canary_decision_rule", {})
    if (
        agg.get("required_operational_pass_cells") != 9
        or agg.get("total_assigned_canary_cells") != 9
        or agg.get("required_operational_pass_fraction") != "9/9"
        or agg.get("required_condition") != "ALL_9_CANARY_OPERATIONAL_PASS == true"
        or agg.get("weaker_threshold_permitted") is not False
        or agg.get("eight_of_nine_permitted") is not False
        or agg.get("majority_permitted") is not False
        or agg.get("two_of_three_providers_permitted") is not False
        or agg.get("provider_average_permitted") is not False
    ):
        raise PlanBeforeLiveProtocolError("CANARY_AGGREGATE_DECISION_RULE_MISMATCH")

    fs = contract.get("fail_stop_rule", {})
    if (
        fs.get("fail_closed_on_any_operational_cell_failure") is not True
        or fs.get("preserve_exact_failure_evidence") is not True
        or fs.get("retry_on_failure_permitted") is not False
        or fs.get("replace_fixture_on_failure_permitted") is not False
        or fs.get("rerun_same_cell_permitted") is not False
        or fs.get("continue_under_improvised_rule_permitted") is not False
        or fs.get("rerun_because_failure_may_have_been_temporary_permitted")
        is not False
        or fs.get("comparative_remains_unauthorized_on_failure") is not True
        or fs.get("return_to_chatgpt_audit_on_failure") is not True
    ):
        raise PlanBeforeLiveProtocolError("CANARY_FAIL_STOP_RULE_MISMATCH")


def validate_authorization_and_scientific_firewalls(
    payload: dict[str, Any],
) -> None:
    """Validate proposed vs effective authorization semantics and all comparative/winner/Final100/primary firewalls."""
    if payload.get("CANARY_LIVE_AUTHORIZATION_PROPOSED") is not True:
        raise PlanBeforeLiveProtocolError(
            "CANARY_LIVE_AUTHORIZATION_PROPOSED_MUST_BE_TRUE"
        )
    if (
        payload.get("AMENDED_CANARY_LIVE_AUTHORIZED") is not False
        or payload.get("AMENDED_COMPARATIVE_LIVE_AUTHORIZED") is not False
        or payload.get("AMENDED_LIVE_AUTHORIZED") is not False
        or payload.get("AMENDED_LIVE_EXECUTED") is not False
        or payload.get("CANARY_EXECUTED") is not False
        or payload.get("COMPARATIVE_EXECUTED") is not False
        or payload.get("LIVE_PROVIDER_CALLS_NEW") != 0
        or payload.get("ENV_FILE_READ") is not False
        or payload.get("API_KEYS_INSPECTED") is not False
    ):
        raise PlanBeforeLiveProtocolError(
            "CANARY_AUTHORIZATION_PREP_MUST_NOT_AUTHORIZE_OR_EXECUTE_LIVE_CALLS"
        )

    auth_sem = payload.get("authorization_semantics", {})
    required_gates = auth_sem.get(
        "required_gates_before_effective_canary_live_authorization", []
    )
    expected_gates = [
        "1. This PREP PR passes exact-head CI",
        "2. ChatGPT independently audits the PREP PR",
        "3. ChatGPT returns PASS",
        "4. The authorization artifact PR is merged normally into develop",
        "5. Post-merge CI on develop succeeds",
        "6. ChatGPT explicitly issues the live-canary execution task",
    ]
    if (
        auth_sem.get("CANARY_LIVE_AUTHORIZATION_PROPOSED") is not True
        or auth_sem.get("AMENDED_CANARY_LIVE_AUTHORIZED") is not False
        or auth_sem.get("repository_authoritative_before_merge") is not False
        or required_gates != expected_gates
    ):
        raise PlanBeforeLiveProtocolError("AUTHORIZATION_SEMANTICS_MISMATCH")

    comp_fw = payload.get("comparative_execution_firewall", {})
    if (
        comp_fw.get("AMENDED_COMPARATIVE_LIVE_AUTHORIZED") is not False
        or comp_fw.get("COMPARATIVE_EXECUTED") is not False
        or comp_fw.get("comparative_180_authorized") is not False
        or comp_fw.get("canary_pass_auto_authorizes_comparative") is not False
        or comp_fw.get(
            "c3_comparative_readiness_must_be_rechecked_before_comparative_authorization"
        )
        is not True
    ):
        raise PlanBeforeLiveProtocolError("COMPARATIVE_FIREWALL_MISMATCH")

    if (
        payload.get("MODEL_WINNER_SELECTED") is not False
        or payload.get("SELECTED_MODEL_ID") is not None
        or payload.get("STOCHASTICITY_EXECUTION_STARTED") is not False
        or payload.get("FINAL100_USED") is not False
        or payload.get("FINAL100_STATUS") != "NO-GO"
        or payload.get("PRIMARY_EXPERIMENT_MUTATED") is not False
        or payload.get("PRIMARY_RESULTS_REPLACED") is not False
        or payload.get("PRIMARY_DENOMINATORS_CHANGED") is not False
    ):
        raise PlanBeforeLiveProtocolError("SCIENTIFIC_FIREWALL_VIOLATION")

    prim_fw = payload.get("primary_authority_firewall", {})
    if (
        prim_fw.get("authoritative_primary_strict_rates")
        != AUTHORITATIVE_PRIMARY_METRIC_RATES
        or prim_fw.get("rejected_erroneous_human_report_rates")
        != REJECTED_ERRONEOUS_REPORT_METRIC_RATES
        or prim_fw.get("erroneous_report_propagated") is not False
        or prim_fw.get("secondary_amendment_replaces_primary_experiment") is not False
    ):
        raise PlanBeforeLiveProtocolError("PRIMARY_AUTHORITY_FIREWALL_MISMATCH")


# ==============================================================================
# 4. ARTIFACT & MARKDOWN GENERATION
# ==============================================================================


def build_w06_canary_live_authorization_prep_payload(
    *,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Build the canonical JSON payload for W06 Amended Canary Live Authorization Prep."""
    with NetworkKillSwitchGuard():
        upstream = verify_all_upstream_authorities(repo_root=repo_root)
        owner_att = upstream["owner_attestation"]
        canary_manifest = upstream["canary_manifest"]

        if (
            owner_att.get("OWNER_PROVIDER_READINESS_ATTESTED") is not True
            or owner_att.get("C1_PROVIDER_READINESS") != "READY_FOR_CANARY"
            or owner_att.get("C2_PROVIDER_READINESS") != "READY_FOR_CANARY"
            or owner_att.get("C3_PROVIDER_READINESS") != "READY_FOR_CANARY"
            or owner_att.get("ALL_CANARY_PROVIDER_READINESS") != "READY"
        ):
            raise PlanBeforeLiveProtocolError(
                "OWNER_READINESS_ATTESTATION_NOT_READY_FOR_CANARY"
            )

        canary_contract = build_frozen_canary_execution_contract(canary_manifest)
        validate_canary_execution_contract(canary_contract)

        payload: dict[str, Any] = {
            "artifact_id": CANARY_AUTH_PREP_ARTIFACT_ID,
            "task_id": TASK_ID,
            "previous_gate": PREVIOUS_GATE_ID,
            "previous_gate_decision": PREVIOUS_GATE_DECISION,
            "authoritative_base_develop_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
            "effective_amendment_status": EFFECTIVE_AMENDMENT_STATUS,
            "bound_authorities": {
                "develop_base_sha": AUTHORITATIVE_BASE_DEVELOP_SHA,
                "owner_readiness_attestation_merge": {
                    "pr_number": OWNER_READINESS_ATTESTATION_PR_NUMBER,
                    "pr_state": OWNER_READINESS_ATTESTATION_PR_STATE,
                    "merge_commit_sha": OWNER_READINESS_ATTESTATION_MERGE_COMMIT_SHA,
                    "parent1": OWNER_READINESS_ATTESTATION_MERGE_PARENT_1,
                    "parent2": OWNER_READINESS_ATTESTATION_MERGE_PARENT_2,
                    "post_merge_ci_run_id": OWNER_READINESS_ATTESTATION_POST_MERGE_CI_RUN_ID,
                    "post_merge_ci_event": OWNER_READINESS_ATTESTATION_POST_MERGE_CI_EVENT,
                    "post_merge_ci_head_sha": OWNER_READINESS_ATTESTATION_POST_MERGE_CI_HEAD_SHA,
                    "post_merge_ci_conclusion": OWNER_READINESS_ATTESTATION_POST_MERGE_CI_CONCLUSION,
                    "post_merge_ci_required_jobs": dict(
                        OWNER_READINESS_ATTESTATION_POST_MERGE_CI_REQUIRED_JOBS
                    ),
                },
                "owner_provider_readiness_attestation": {
                    "path": OWNER_READINESS_ATTESTATION_REL_PATH,
                    "file_sha256": EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256,
                    "internal_sha256": EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256,
                    "doc_path": OWNER_READINESS_ATTESTATION_DOC_REL_PATH,
                    "doc_sha256": EXPECTED_OWNER_READINESS_ATTESTATION_DOC_SHA256,
                    "owner_observed_readiness_evidence_date": owner_att[
                        "owner_observed_readiness_evidence_date"
                    ],
                    "C1_PROVIDER_READINESS": owner_att["C1_PROVIDER_READINESS"],
                    "C2_PROVIDER_READINESS": owner_att["C2_PROVIDER_READINESS"],
                    "C3_PROVIDER_READINESS": owner_att["C3_PROVIDER_READINESS"],
                    "ALL_CANARY_PROVIDER_READINESS": owner_att[
                        "ALL_CANARY_PROVIDER_READINESS"
                    ],
                },
                "canary_assignment_manifest": {
                    "path": CANARY_MANIFEST_REL_PATH,
                    "file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
                    "internal_sha256": EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
                },
                "amendment_formal_decision": {
                    "path": DECISION_ARTIFACT_REL_PATH,
                    "file_sha256": EXPECTED_DECISION_ARTIFACT_FILE_SHA256,
                    "internal_sha256": EXPECTED_DECISION_ARTIFACT_INTERNAL_SHA256,
                },
                "amendment_approval_receipt": {
                    "path": APPROVAL_RECEIPT_REL_PATH,
                    "file_sha256": EXPECTED_APPROVAL_RECEIPT_FILE_SHA256,
                    "internal_sha256": EXPECTED_APPROVAL_RECEIPT_INTERNAL_SHA256,
                },
                "provider_readiness_pricing_prep": {
                    "path": PROVIDER_READINESS_PRICING_PREP_REL_PATH,
                    "file_sha256": EXPECTED_PROVIDER_READINESS_PRICING_PREP_FILE_SHA256,
                    "internal_sha256": EXPECTED_PROVIDER_READINESS_PRICING_PREP_INTERNAL_SHA256,
                },
                "public_pricing_snapshot": {
                    "path": PUBLIC_PRICING_SNAPSHOT_REL_PATH,
                    "file_sha256": EXPECTED_PUBLIC_PRICING_SNAPSHOT_FILE_SHA256,
                    "internal_sha256": EXPECTED_PUBLIC_PRICING_SNAPSHOT_INTERNAL_SHA256,
                },
                "amendment_prep": {
                    "path": PREP_ARTIFACT_REL_PATH,
                    "file_sha256": EXPECTED_PREP_ARTIFACT_FILE_SHA256,
                    "internal_sha256": EXPECTED_PREP_ARTIFACT_INTERNAL_SHA256,
                },
                "primary_results_freeze_receipt": {
                    "path": PRIMARY_RESULTS_FREEZE_RECEIPT_REL_PATH,
                    "file_sha256": EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_FILE_SHA256,
                    "internal_sha256": EXPECTED_PRIMARY_RESULTS_FREEZE_RECEIPT_INTERNAL_SHA256,
                },
                "primary_results_manifest": {
                    "path": PRIMARY_RESULTS_MANIFEST_REL_PATH,
                    "file_sha256": EXPECTED_PRIMARY_RESULTS_MANIFEST_FILE_SHA256,
                    "internal_sha256": EXPECTED_PRIMARY_RESULTS_MANIFEST_INTERNAL_SHA256,
                },
                "failure_diagnostic": {
                    "path": FAILURE_DIAGNOSTIC_REL_PATH,
                    "file_sha256": EXPECTED_FAILURE_DIAGNOSTIC_FILE_SHA256,
                    "internal_sha256": EXPECTED_FAILURE_DIAGNOSTIC_INTERNAL_SHA256,
                },
                "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            },
            "frozen_canary_execution_contract": canary_contract,
            "authorization_semantics": {
                "CANARY_LIVE_AUTHORIZATION_PROPOSED": True,
                "AMENDED_CANARY_LIVE_AUTHORIZED": False,
                "repository_authoritative_before_merge": False,
                "becomes_effective_only_after_audit_merge_postmerge_ci_and_explicit_execution_task": True,
                "required_gates_before_effective_canary_live_authorization": [
                    "1. This PREP PR passes exact-head CI",
                    "2. ChatGPT independently audits the PREP PR",
                    "3. ChatGPT returns PASS",
                    "4. The authorization artifact PR is merged normally into develop",
                    "5. Post-merge CI on develop succeeds",
                    "6. ChatGPT explicitly issues the live-canary execution task",
                ],
            },
            "comparative_execution_firewall": {
                "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
                "COMPARATIVE_EXECUTED": False,
                "comparative_180_authorized": False,
                "canary_pass_auto_authorizes_comparative": False,
                "c3_comparative_readiness_must_be_rechecked_before_comparative_authorization": True,
            },
            "primary_authority_firewall": {
                "authoritative_primary_strict_rates": dict(
                    AUTHORITATIVE_PRIMARY_METRIC_RATES
                ),
                "rejected_erroneous_human_report_rates": dict(
                    REJECTED_ERRONEOUS_REPORT_METRIC_RATES
                ),
                "erroneous_report_propagated": False,
                "secondary_amendment_replaces_primary_experiment": False,
                "PRIMARY_EXPERIMENT_MUTATED": False,
                "PRIMARY_RESULTS_REPLACED": False,
                "PRIMARY_DENOMINATORS_CHANGED": False,
            },
            "CANARY_LIVE_AUTHORIZATION_PROPOSED": True,
            "AMENDED_CANARY_LIVE_AUTHORIZED": False,
            "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_AUTHORIZED": False,
            "AMENDED_LIVE_EXECUTED": False,
            "CANARY_EXECUTED": False,
            "COMPARATIVE_EXECUTED": False,
            "LIVE_PROVIDER_CALLS_NEW": 0,
            "ENV_FILE_READ": False,
            "API_KEYS_INSPECTED": False,
            "MODEL_WINNER_SELECTED": False,
            "SELECTED_MODEL_ID": None,
            "STOCHASTICITY_EXECUTION_STARTED": False,
            "FINAL100_USED": False,
            "FINAL100_STATUS": "NO-GO",
            "PRIMARY_EXPERIMENT_MUTATED": False,
            "PRIMARY_RESULTS_REPLACED": False,
            "PRIMARY_DENOMINATORS_CHANGED": False,
            "NEXT_GATE": NEXT_GATE_ID,
        }

        validate_authorization_and_scientific_firewalls(payload)
        assert_no_secrets_in_payload(
            payload, context="canary_live_authorization_prep"
        )
        payload["canary_live_authorization_prep_internal_sha256"] = (
            compute_canary_auth_prep_internal_sha256(payload)
        )
        return payload


def render_w06_canary_live_authorization_prep_markdown(
    payload: dict[str, Any],
) -> str:
    """Render deterministic Markdown documentation from the canonical JSON payload."""
    ba = payload["bound_authorities"]
    contract = payload["frozen_canary_execution_contract"]
    rt = contract["frozen_runtime_policy"]
    op_crit = contract["operational_pass_criterion_per_cell"][
        "required_operational_conditions"
    ]
    agg = contract["aggregate_canary_decision_rule"]
    fs = contract["fail_stop_rule"]
    auth_sem = payload["authorization_semantics"]

    lines: list[str] = [
        "# W06 DEV-SELECT Execution-Environment Amendment 01 — Amended Canary Live Authorization Prep",
        "",
        "## 1. Gate & Authority Binding",
        "",
        f"- **Task ID:** `{payload['task_id']}`",
        f"- **Artifact ID:** `{payload['artifact_id']}`",
        f"- **Previous Gate:** `{payload['previous_gate']}` (`{payload['previous_gate_decision']}`)",
        f"- **Authoritative Base (`develop`):** `{payload['authoritative_base_develop_sha']}`",
        f"- **PR #71 Merge Commit:** `{ba['owner_readiness_attestation_merge']['merge_commit_sha']}` (`parent1 = {ba['owner_readiness_attestation_merge']['parent1']}`, `parent2 = {ba['owner_readiness_attestation_merge']['parent2']}`)",
        f"- **PR #71 Post-Merge CI:** `run_id = {ba['owner_readiness_attestation_merge']['post_merge_ci_run_id']}` (`event = {ba['owner_readiness_attestation_merge']['post_merge_ci_event']}`, `conclusion = {ba['owner_readiness_attestation_merge']['post_merge_ci_conclusion']}`)",
        f"- **Effective Amendment Status:** `{payload['effective_amendment_status']}`",
        f"- **Internal SHA256:** `{payload['canary_live_authorization_prep_internal_sha256']}`",
        "",
        "### Bound Upstream Artifacts",
        "",
        "| Authority | File SHA256 | Internal SHA256 |",
        "| --- | --- | --- |",
        f"| Owner Provider Readiness Attestation (`{ba['owner_provider_readiness_attestation']['path']}`) | `{ba['owner_provider_readiness_attestation']['file_sha256']}` | `{ba['owner_provider_readiness_attestation']['internal_sha256']}` |",
        f"| Canary Assignment Manifest (`{ba['canary_assignment_manifest']['path']}`) | `{ba['canary_assignment_manifest']['file_sha256']}` | `{ba['canary_assignment_manifest']['internal_sha256']}` |",
        f"| Amendment Formal Decision (`{ba['amendment_formal_decision']['path']}`) | `{ba['amendment_formal_decision']['file_sha256']}` | `{ba['amendment_formal_decision']['internal_sha256']}` |",
        f"| Amendment Approval Receipt (`{ba['amendment_approval_receipt']['path']}`) | `{ba['amendment_approval_receipt']['file_sha256']}` | `{ba['amendment_approval_receipt']['internal_sha256']}` |",
        f"| Provider Readiness & Pricing Prep (`{ba['provider_readiness_pricing_prep']['path']}`) | `{ba['provider_readiness_pricing_prep']['file_sha256']}` | `{ba['provider_readiness_pricing_prep']['internal_sha256']}` |",
        f"| Public Pricing Snapshot (`{ba['public_pricing_snapshot']['path']}`) | `{ba['public_pricing_snapshot']['file_sha256']}` | `{ba['public_pricing_snapshot']['internal_sha256']}` |",
        f"| Amendment Prep (`{ba['amendment_prep']['path']}`) | `{ba['amendment_prep']['file_sha256']}` | `{ba['amendment_prep']['internal_sha256']}` |",
        f"| Primary Results Freeze Receipt (`{ba['primary_results_freeze_receipt']['path']}`) | `{ba['primary_results_freeze_receipt']['file_sha256']}` | `{ba['primary_results_freeze_receipt']['internal_sha256']}` |",
        f"| Primary Results Manifest (`{ba['primary_results_manifest']['path']}`) | `{ba['primary_results_manifest']['file_sha256']}` | `{ba['primary_results_manifest']['internal_sha256']}` |",
        f"| Failure Diagnostic (`{ba['failure_diagnostic']['path']}`) | `{ba['failure_diagnostic']['file_sha256']}` | `{ba['failure_diagnostic']['internal_sha256']}` |",
        f"| Scientific Code Bundle | `{ba['scientific_code_bundle_sha256']}` | N/A |",
        "",
        "## 2. Frozen Canary Candidates & Fixtures",
        "",
        "- **C1:** `GOOGLE` / `gemini-3.8-flash` (`assigned_canary_calls = 3`)",
        "- **C2:** `OPENAI` / `gpt-6.1-sol` (`assigned_canary_calls = 3`)",
        "- **C3:** `ANTHROPIC` / `claude-sonnet-5-5` (`assigned_canary_calls = 3`)",
        f"- **Candidate Substitution Permitted:** `{contract['candidate_substitution_permitted']}`",
        f"- **Fourth Model Permitted:** `{contract['fourth_model_permitted']}`",
        f"- **Exact Canary Fixtures:** `{', '.join(contract['exact_canary_fixtures'])}`",
        f"- **Additional / Replacement / Final100 Fixtures Permitted:** `{contract['additional_fixture_permitted']}` / `{contract['replacement_fixture_permitted']}` / `{contract['final100_scenario_permitted']}`",
        "",
        "## 3. Exact 9-Cell Canary Execution Order",
        "",
        "| Order | Short Label | Cell ID | Fixture ID | Destination | Candidate | Provider | Model | Timeout (ms) | Delay Before Next (ms) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for cell in contract["ordered_canary_cells"]:
        lines.append(
            f"| {cell['order_index']} | `{cell['short_label']}` | `{cell['cell_id']}` | `{cell['fixture_id']}` | {cell['destination']} (`{cell['destination_slug']}`) | `{cell['candidate_id']}` | `{cell['provider']}` | `{cell['requested_model_id']}` | `{cell['timeout_ms']}` | `{cell['inter_call_delay_ms_before_next_cell']}` |"
        )

    lines.extend(
        [
            "",
            f"- **Total Maximum Canary Generation Calls:** `{contract['total_maximum_canary_generation_calls']}`",
            "",
            "## 4. Frozen Runtime Policy",
            "",
            f"- **Timeout:** `{rt['timeout_ms']} ms` (`{rt['timeout_policy_id']}`)",
            f"- **Fixed Inter-Call Delay:** `{rt['inter_call_delay_ms']} ms` (`{rt['pacing_policy_id']}`; `{rt['total_inter_cell_pacing_intervals']}` intervals = `{rt['total_inter_cell_pacing_ms']} ms`)",
            f"- **Automatic Retry:** `{rt['automatic_retry']}`",
            f"- **Transport Retry:** `{rt['transport_retry']}`",
            f"- **Manual Retry:** `{rt['manual_retry']}`",
            f"- **LLM Repair:** `{rt['llm_repair']}`",
            f"- **Semantic Repair:** `{rt['semantic_repair']}`",
            f"- **Fallback:** `{rt['fallback']}`",
            f"- **Generation Calls per Assigned Cell:** `{rt['generation_calls_per_assigned_cell']}`",
            f"- **Adaptive Pacing / Dynamic Timeout / Special Treatment / Retry After Error Permitted:** `{rt['adaptive_pacing_permitted']}` / `{rt['dynamic_timeout_permitted']}` / `{rt['provider_specific_special_treatment_permitted']}` / `{rt['retry_after_timeout_429_or_5xx_permitted']}`",
            "",
            "## 5. Canary Purpose, Operational PASS Criterion, Aggregate Decision & Fail-Stop Rule",
            "",
            f"- **Purpose:** `{contract['canary_purpose']['classification']}` (NOT planner-quality model selection, NOT scientific superiority evaluation, NOT comparative benchmark, NOT Final100 evaluation).",
            "- **Operational PASS Conditions per Cell:**",
        ]
    )
    for k, v in sorted(op_crit.items()):
        lines.append(f"  - `{k} = {v}`")
    lines.extend(
        [
            f"- **Planner Schema Validity / Final-Core Quality Redefines Operational PASS:** `{contract['operational_pass_criterion_per_cell']['planner_schema_validity_is_operational_pass_criterion']}` / `{contract['operational_pass_criterion_per_cell']['final_core_quality_is_operational_pass_criterion']}`",
            f"- **Aggregate Canary Decision Requirement:** `{agg['required_operational_pass_fraction']}` (`{agg['required_condition']}`; partial/majority/2-of-3/provider-average thresholds forbidden).",
            "- **Fail-Stop Rule:**",
            f"  - `fail_closed_on_any_operational_cell_failure = {fs['fail_closed_on_any_operational_cell_failure']}`",
            f"  - `preserve_exact_failure_evidence = {fs['preserve_exact_failure_evidence']}`",
            f"  - `retry_on_failure_permitted = {fs['retry_on_failure_permitted']}`",
            f"  - `replace_fixture_on_failure_permitted = {fs['replace_fixture_on_failure_permitted']}`",
            f"  - `rerun_same_cell_permitted = {fs['rerun_same_cell_permitted']}`",
            f"  - `continue_under_improvised_rule_permitted = {fs['continue_under_improvised_rule_permitted']}`",
            f"  - `rerun_because_failure_may_have_been_temporary_permitted = {fs['rerun_because_failure_may_have_been_temporary_permitted']}`",
            f"  - `comparative_remains_unauthorized_on_failure = {fs['comparative_remains_unauthorized_on_failure']}`",
            f"  - `return_to_chatgpt_audit_on_failure = {fs['return_to_chatgpt_audit_on_failure']}`",
            "",
            "## 6. Proposed vs Effective Authorization & Firewalls",
            "",
            f"- **`CANARY_LIVE_AUTHORIZATION_PROPOSED`:** `{payload['CANARY_LIVE_AUTHORIZATION_PROPOSED']}`",
            f"- **`AMENDED_CANARY_LIVE_AUTHORIZED`:** `{payload['AMENDED_CANARY_LIVE_AUTHORIZED']}`",
            f"- **`AMENDED_COMPARATIVE_LIVE_AUTHORIZED`:** `{payload['AMENDED_COMPARATIVE_LIVE_AUTHORIZED']}`",
            f"- **`CANARY_EXECUTED` / `COMPARATIVE_EXECUTED`:** `{payload['CANARY_EXECUTED']}` / `{payload['COMPARATIVE_EXECUTED']}`",
            f"- **`LIVE_PROVIDER_CALLS_NEW`:** `{payload['LIVE_PROVIDER_CALLS_NEW']}`",
            f"- **`ENV_FILE_READ` / `API_KEYS_INSPECTED`:** `{payload['ENV_FILE_READ']}` / `{payload['API_KEYS_INSPECTED']}`",
            f"- **`MODEL_WINNER_SELECTED` / `SELECTED_MODEL_ID`:** `{payload['MODEL_WINNER_SELECTED']}` / `{payload['SELECTED_MODEL_ID']}`",
            f"- **`STOCHASTICITY_EXECUTION_STARTED`:** `{payload['STOCHASTICITY_EXECUTION_STARTED']}`",
            f"- **`FINAL100_USED` / `FINAL100_STATUS`:** `{payload['FINAL100_USED']}` / `{payload['FINAL100_STATUS']}`",
            f"- **Primary Strict Rates Unchanged:** `C1 = {payload['primary_authority_firewall']['authoritative_primary_strict_rates']['C1']}`, `C2 = {payload['primary_authority_firewall']['authoritative_primary_strict_rates']['C2']}`, `C3 = {payload['primary_authority_firewall']['authoritative_primary_strict_rates']['C3']}`",
            "- **Required Gates Before Effective Live Canary Authorization:**",
        ]
    )
    for step in auth_sem["required_gates_before_effective_canary_live_authorization"]:
        lines.append(f"  - {step}")
    lines.extend(
        [
            "",
            f"- **Next Gate:** `{payload['NEXT_GATE']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _assert_writable_target_path(path: Path, repo_root: Path = REPO_ROOT) -> None:
    try:
        rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return
    if rel in IMMUTABLE_UPSTREAM_REL_PATHS:
        raise PlanBeforeLiveProtocolError(
            f"IMMUTABLE_UPSTREAM_ARTIFACT_MUTATION_FORBIDDEN: {rel}"
        )
    if rel.startswith("data/evaluation/w06/live_"):
        raise PlanBeforeLiveProtocolError(
            f"RAW_EVIDENCE_WRITE_FORBIDDEN: {rel}"
        )


def write_w06_canary_live_authorization_prep(
    *,
    repo_root: Path = REPO_ROOT,
    artifact_path: Path | None = None,
    doc_path: Path | None = None,
) -> dict[str, Any]:
    """Write the canonical JSON and Markdown artifacts for W06 Amended Canary Live Authorization Prep."""
    target_json = artifact_path or (repo_root / CANARY_AUTH_PREP_REL_PATH)
    target_doc = doc_path or (repo_root / CANARY_AUTH_PREP_DOC_REL_PATH)
    _assert_writable_target_path(target_json, repo_root=repo_root)
    _assert_writable_target_path(target_doc, repo_root=repo_root)

    payload = build_w06_canary_live_authorization_prep_payload(repo_root=repo_root)
    json_bytes = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    doc_text = render_w06_canary_live_authorization_prep_markdown(payload)
    doc_bytes = doc_text.encode("utf-8")

    target_json.parent.mkdir(parents=True, exist_ok=True)
    target_doc.parent.mkdir(parents=True, exist_ok=True)
    target_json.write_bytes(json_bytes)
    target_doc.write_bytes(doc_bytes)

    return {
        "canary_live_authorization_prep_path": CANARY_AUTH_PREP_REL_PATH,
        "canary_live_authorization_prep_file_sha256": sha256_bytes(json_bytes),
        "canary_live_authorization_prep_internal_sha256": payload[
            "canary_live_authorization_prep_internal_sha256"
        ],
        "canary_live_authorization_prep_doc_path": CANARY_AUTH_PREP_DOC_REL_PATH,
        "canary_live_authorization_prep_doc_sha256": sha256_bytes(doc_bytes),
    }


def verify_w06_canary_live_authorization_prep(
    *,
    repo_root: Path = REPO_ROOT,
    artifact_path: Path | None = None,
    doc_path: Path | None = None,
) -> dict[str, Any]:
    """Statelessly verify the persisted W06 Amended Canary Live Authorization Prep JSON and Markdown artifacts."""
    with NetworkKillSwitchGuard():
        target_json = artifact_path or (repo_root / CANARY_AUTH_PREP_REL_PATH)
        target_doc = doc_path or (repo_root / CANARY_AUTH_PREP_DOC_REL_PATH)

        raw_json, file_sha = _load_lf_bytes_and_sha(target_json)
        raw_doc, doc_sha = _load_lf_bytes_and_sha(target_doc)

        persisted = json.loads(raw_json.decode("utf-8"))
        if not isinstance(persisted, dict):
            raise PlanBeforeLiveProtocolError("CANARY_AUTH_PREP_NOT_JSON_OBJECT")

        internal_sha = persisted.get("canary_live_authorization_prep_internal_sha256")
        recomputed_internal = compute_canary_auth_prep_internal_sha256(persisted)
        if internal_sha != recomputed_internal:
            raise PlanBeforeLiveProtocolError(
                f"CANARY_AUTH_PREP_INTERNAL_SHA256_TAMPERED: stored={internal_sha}, recomputed={recomputed_internal}"
            )

        if (
            EXPECTED_CANARY_AUTH_PREP_FILE_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and file_sha != EXPECTED_CANARY_AUTH_PREP_FILE_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"CANARY_AUTH_PREP_FILE_SHA256_MISMATCH: expected {EXPECTED_CANARY_AUTH_PREP_FILE_SHA256}, got {file_sha}"
            )
        if (
            EXPECTED_CANARY_AUTH_PREP_INTERNAL_SHA256
            != "0000000000000000000000000000000000000000000000000000000000000000"
            and internal_sha != EXPECTED_CANARY_AUTH_PREP_INTERNAL_SHA256
        ):
            raise PlanBeforeLiveProtocolError(
                f"CANARY_AUTH_PREP_INTERNAL_SHA256_MISMATCH: expected {EXPECTED_CANARY_AUTH_PREP_INTERNAL_SHA256}, got {internal_sha}"
            )

        validate_canary_execution_contract(
            persisted.get("frozen_canary_execution_contract", {})
        )
        validate_authorization_and_scientific_firewalls(persisted)
        assert_no_secrets_in_payload(
            persisted, context="canary_live_authorization_prep"
        )

        expected_payload = build_w06_canary_live_authorization_prep_payload(
            repo_root=repo_root
        )
        if persisted != expected_payload:
            raise PlanBeforeLiveProtocolError(
                "CANARY_AUTH_PREP_PAYLOAD_DRIFT_FROM_DETERMINISTIC_BUILDER"
            )

        expected_doc_bytes = render_w06_canary_live_authorization_prep_markdown(
            persisted
        ).encode("utf-8")
        if raw_doc != expected_doc_bytes:
            raise PlanBeforeLiveProtocolError(
                "CANARY_AUTH_PREP_MARKDOWN_DRIFT_FROM_CANONICAL_JSON"
            )

        return {
            "artifact_id": persisted["artifact_id"],
            "task_id": persisted["task_id"],
            "authoritative_base_develop_sha": persisted[
                "authoritative_base_develop_sha"
            ],
            "canary_live_authorization_prep_file_sha256": file_sha,
            "canary_live_authorization_prep_internal_sha256": internal_sha,
            "canary_live_authorization_prep_doc_sha256": doc_sha,
            "owner_readiness_attestation_file_sha256": EXPECTED_OWNER_READINESS_ATTESTATION_FILE_SHA256,
            "owner_readiness_attestation_internal_sha256": EXPECTED_OWNER_READINESS_ATTESTATION_INTERNAL_SHA256,
            "canary_manifest_file_sha256": EXPECTED_CANARY_MANIFEST_FILE_SHA256,
            "canary_manifest_internal_sha256": EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256,
            "canary_live_authorization_proposed": persisted[
                "CANARY_LIVE_AUTHORIZATION_PROPOSED"
            ],
            "amended_canary_live_authorized": persisted[
                "AMENDED_CANARY_LIVE_AUTHORIZED"
            ],
            "amended_comparative_live_authorized": persisted[
                "AMENDED_COMPARATIVE_LIVE_AUTHORIZED"
            ],
            "amended_live_authorized": persisted["AMENDED_LIVE_AUTHORIZED"],
            "amended_live_executed": persisted["AMENDED_LIVE_EXECUTED"],
            "canary_executed": persisted["CANARY_EXECUTED"],
            "comparative_executed": persisted["COMPARATIVE_EXECUTED"],
            "live_provider_calls_new": persisted["LIVE_PROVIDER_CALLS_NEW"],
            "env_file_read": persisted["ENV_FILE_READ"],
            "api_keys_inspected": persisted["API_KEYS_INSPECTED"],
            "model_winner_selected": persisted["MODEL_WINNER_SELECTED"],
            "selected_model_id": persisted["SELECTED_MODEL_ID"],
            "stochasticity_execution_started": persisted[
                "STOCHASTICITY_EXECUTION_STARTED"
            ],
            "final100_used": persisted["FINAL100_USED"],
            "final100_status": persisted["FINAL100_STATUS"],
            "primary_experiment_mutated": persisted["PRIMARY_EXPERIMENT_MUTATED"],
            "primary_results_replaced": persisted["PRIMARY_RESULTS_REPLACED"],
            "primary_denominators_changed": persisted["PRIMARY_DENOMINATORS_CHANGED"],
            "next_gate": persisted["NEXT_GATE"],
            "status": "PASS",
            "verified": True,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify W06 Amended Canary Live Authorization Prep."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the JSON and Markdown artifacts before verifying.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify the persisted JSON and Markdown artifacts without writing.",
    )
    args = parser.parse_args(argv)

    if args.write and args.verify_only:
        parser.error("Cannot specify both --write and --verify-only.")

    if args.write:
        write_summary = write_w06_canary_live_authorization_prep(repo_root=REPO_ROOT)
        print(json.dumps(write_summary, indent=2, sort_keys=True))

    verify_summary = verify_w06_canary_live_authorization_prep(repo_root=REPO_ROOT)
    print(json.dumps(verify_summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
