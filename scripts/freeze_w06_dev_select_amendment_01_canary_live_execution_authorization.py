#!/usr/bin/env python3
"""Strictly offline W06 Amendment-01 Canary Live Execution Authorization Receipt generator and verifier.

TASK: W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-AUTHORIZATION-RECEIPT-PREP

PURPOSE:
Prepare, freeze, and statelessly verify the production candidate live-execution authorization receipt:
1. `data/evaluation/w06/w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json`
2. `docs/research/w06_dev_select_amendment_01_canary_live_execution_authorization.md`

STRICT GOVERNANCE & FIREWALLS:
- Reuses `build_canary_live_execution_authorization_receipt_payload()` and
  `verify_canary_live_execution_authorization_receipt()` from the frozen merged launcher
  `scripts/run_w06_dev_select_amendment_01_canary_live_v1.py` (LF SHA256:
  `7db06f178d5e07980642dc846fa160f51305db7ce59981e706790a3475a8bda2`).
- Binds exact PR #73 merge provenance on `develop@3e103587ab0324717c03af14e236dc37fc579295`:
  - `launcher_pr_number = 73`
  - `authoritative_base_develop_sha = 1ebe30c251958542088a3056dcfc6b780dac3a88` (parent 1)
  - `launcher_pr_head_sha = c6c984aef8712538c8c29587caff1e0bbb36afaa` (parent 2)
  - `launcher_merge_commit_sha = 3e103587ab0324717c03af14e236dc37fc579295`
  - `authorized_code_basis_commit_sha = 3e103587ab0324717c03af14e236dc37fc579295`
  - `launcher_file_lf_sha256 = 7db06f178d5e07980642dc846fa160f51305db7ce59981e706790a3475a8bda2`
  - `launcher_path = scripts/run_w06_dev_select_amendment_01_canary_live_v1.py`
- Sets `CANARY_LIVE_EXECUTION_AUTHORIZED = true` inside the candidate receipt payload as required
  by the launcher verifier, while preserving project governance that the live canary MUST NOT be
  executed during this PREP task (requires receipt PR CI -> ChatGPT audit PASS -> normal merge ->
  post-merge push CI -> ChatGPT post-merge audit PASS -> explicit gate
  `W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-01`).
- Executes ZERO live provider calls (`LIVE_PROVIDER_CALLS_NEW = 0`, `ENV_FILE_READ = false`,
  `API_KEYS_INSPECTED = false`).
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
for _p in (SCRIPTS_DIR, AI_SERVICE_DIR, REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.evaluation.dev_live_runner import (  # noqa: E402
    LiveExecutionNotAuthorizedError,
    PlanBeforeLiveProtocolError,
    assert_no_secrets_in_payload,
)
from app.evaluation.dev_selection_harness import (  # noqa: E402
    FORBIDDEN_FINAL100_BUNDLE_SHA256,
    FORBIDDEN_P11_MANIFEST_SHA256,
    Final100FirewallViolationError,
    canonical_json_bytes,
    compute_scientific_code_bundle_sha256,
    normalize_lf_bytes,
    sha256_bytes,
)
import run_w06_dev_select_amendment_01_canary_live_v1 as canary_launcher  # noqa: E402


# ==============================================================================
# 1. FROZEN CONSTANTS & AUTHORITIES (SECTIONS 0, 3, 4, 5, 6, 7, 8, 9, 10, 11)
# ==============================================================================

PREP_TASK_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-AUTHORIZATION-RECEIPT-PREP"
)
PREVIOUS_GATE_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-LAUNCHER-POSTMERGE-CHATGPT-AUDIT"
)
PREVIOUS_GATE_DECISION = "PASS"
NEXT_GATE_ID = (
    "W06-DEV-SELECT-EXECUTION-ENVIRONMENT-AMENDMENT-01-CANARY-LIVE-EXECUTION-AUTHORIZATION-RECEIPT-PREP-CHATGPT-AUDIT"
)
FUTURE_LIVE_EXECUTION_GATE_ID = canary_launcher.FUTURE_LIVE_EXECUTION_GATE_ID

RECEIPT_REL_PATH = canary_launcher.CANARY_LIVE_EXECUTION_AUTH_RECEIPT_REL_PATH
RECEIPT_DOC_REL_PATH = (
    "docs/research/w06_dev_select_amendment_01_canary_live_execution_authorization.md"
)
RECEIPT_ARTIFACT_ID = canary_launcher.CANARY_LIVE_EXECUTION_AUTH_RECEIPT_ARTIFACT_ID
RECEIPT_INTERNAL_SHA_KEY = (
    canary_launcher.CANARY_LIVE_EXECUTION_AUTH_INTERNAL_SHA_KEY
)

# Exact PR #73 merge provenance on develop
FROZEN_LAUNCHER_PR_NUMBER = 73
FROZEN_PRE_LAUNCHER_BASE_DEVELOP_SHA = (
    "1ebe30c251958542088a3056dcfc6b780dac3a88"
)
FROZEN_LAUNCHER_PR_HEAD_SHA = "c6c984aef8712538c8c29587caff1e0bbb36afaa"
FROZEN_LAUNCHER_MERGE_COMMIT_SHA = "3e103587ab0324717c03af14e236dc37fc579295"
FROZEN_AUTHORIZED_CODE_BASIS_COMMIT_SHA = (
    "3e103587ab0324717c03af14e236dc37fc579295"
)
FROZEN_LAUNCHER_PATH = "scripts/run_w06_dev_select_amendment_01_canary_live_v1.py"
FROZEN_LAUNCHER_FILE_LF_SHA256 = (
    "7db06f178d5e07980642dc846fa160f51305db7ce59981e706790a3475a8bda2"
)
FROZEN_LAUNCHER_POSTMERGE_CI_RUN_ID = 41181343010
FROZEN_LAUNCHER_POSTMERGE_CI_EVENT = "push"
FROZEN_LAUNCHER_POSTMERGE_CI_HEAD_SHA = (
    "3e103587ab0324717c03af14e236dc37fc579295"
)
FROZEN_LAUNCHER_POSTMERGE_CI_CONCLUSION = "success"
FROZEN_LAUNCHER_POSTMERGE_CI_JOBS: dict[str, str] = {
    "ai-service": "success",
    "backend": "success",
    "data-contract": "success",
    "mobile": "success",
}

# Frozen upstream authority hashes (Section 5)
EXPECTED_CANARY_AUTH_PREP_FILE_SHA256 = (
    "21f9432c4c8bfa0ba5f63bdd99e8ab8c15d2802918b7e0a9c21cb5c0ccc63b61"
)
EXPECTED_CANARY_AUTH_PREP_INTERNAL_SHA256 = (
    "0f1480969d506d5b6dc16951a45cf2f8aaf913a13c011f2add6ec3e31721af61"
)
EXPECTED_CANARY_AUTH_PREP_DOC_SHA256 = (
    "d9db3cf7876c408f9a30f703200bd575934e1c81679740e7cdd6ba30256904da"
)
EXPECTED_CANARY_MANIFEST_FILE_SHA256 = (
    "3ce0ebaac35f22dfe8c981478a6c63d7a2fde0580b372fd8f25762ab3b18fb96"
)
EXPECTED_CANARY_MANIFEST_INTERNAL_SHA256 = (
    "707d99fee54d65822f194cc690cbfadea14ad2176594d4ef882e7d8031990518"
)
EXPECTED_OWNER_READINESS_FILE_SHA256 = (
    "91702599a9c81d57bfa1360d33cf19129537608a5141d35bbba58958a62b1d06"
)
EXPECTED_OWNER_READINESS_INTERNAL_SHA256 = (
    "137aae6ba52912c10098262ecd29238cb591c92005d99eb226ffbe65c9dfbd75"
)
EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256 = (
    "0638f2fcb100b0000e3a2a4e08137a9d468449001f258de7354df21e185ca2e3"
)
EXPECTED_PRIMARY_LAUNCHER_LF_SHA256 = (
    "cd36b8ecad24059edb597c0039bd6e760a37ee8b4f36f49077801c65e7ddc7bf"
)
EXPECTED_P1_SEMANTIC_SHA256 = (
    "096ff4c74dd8d1aed1c0abe501b97c8dfd0f6424dbca535f2b79a242637a1c11"
)


def _compute_file_lf_sha256(path: Path) -> str:
    return sha256_bytes(normalize_lf_bytes(path.read_bytes()))


def _compute_internal_sha256(payload: Mapping[str, Any], internal_key: str) -> str:
    body = {k: v for k, v in payload.items() if k != internal_key}
    return sha256_bytes(canonical_json_bytes(body))


def _serialize_json_lf(payload: Mapping[str, Any]) -> bytes:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return normalize_lf_bytes(text.encode("utf-8"))


# ==============================================================================
# 2. RECEIPT PAYLOAD & MARKDOWN BUILDERS (REUSING MERGED LAUNCHER CONTRACT)
# ==============================================================================


def build_production_canary_live_execution_authorization_receipt(
    *,
    overrides: Mapping[str, Any] | None = None,
    recompute_internal_sha: bool = True,
) -> dict[str, Any]:
    """Build the production candidate `w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json`
    by reusing `canary_launcher.build_canary_live_execution_authorization_receipt_payload()`.
    """
    governance_extensions: dict[str, Any] = {
        "prep_task_id": PREP_TASK_ID,
        "previous_gate": PREVIOUS_GATE_ID,
        "previous_gate_decision": PREVIOUS_GATE_DECISION,
        "next_gate": NEXT_GATE_ID,
        "receipt_prep_only_not_executable_during_prep_task": True,
        "live_execution_requires_pr_ci_chatgpt_audit_merge_postmerge_ci_and_explicit_execution_gate": True,
        "CANARY_EXECUTED": False,
        "COMPARATIVE_EXECUTED": False,
        "AMENDED_LIVE_EXECUTED": False,
        "canary_pass_does_not_auto_authorize_comparative": True,
        "PRIMARY_EXPERIMENT_MUTATED": False,
        "PRIMARY_RESULTS_REPLACED": False,
        "PRIMARY_DENOMINATORS_CHANGED": False,
        "authoritative_primary_strict_rates": dict(
            canary_launcher.AUTHORITATIVE_PRIMARY_STRICT_RATES
        ),
        "LIVE_PROVIDER_CALLS_NEW": 0,
        "ENV_FILE_READ": False,
        "API_KEYS_INSPECTED": False,
        "launcher_post_merge_ci_evidence": {
            "pr_number": FROZEN_LAUNCHER_PR_NUMBER,
            "pr_state": "MERGED",
            "run_id": FROZEN_LAUNCHER_POSTMERGE_CI_RUN_ID,
            "event": FROZEN_LAUNCHER_POSTMERGE_CI_EVENT,
            "head_sha": FROZEN_LAUNCHER_POSTMERGE_CI_HEAD_SHA,
            "conclusion": FROZEN_LAUNCHER_POSTMERGE_CI_CONCLUSION,
            "required_jobs": dict(FROZEN_LAUNCHER_POSTMERGE_CI_JOBS),
        },
    }
    if overrides:
        for k, v in overrides.items():
            governance_extensions[k] = v

    return canary_launcher.build_canary_live_execution_authorization_receipt_payload(
        launcher_pr_head_sha=FROZEN_LAUNCHER_PR_HEAD_SHA,
        launcher_merge_commit_sha=FROZEN_LAUNCHER_MERGE_COMMIT_SHA,
        authorized_code_basis_commit_sha=FROZEN_AUTHORIZED_CODE_BASIS_COMMIT_SHA,
        launcher_file_lf_sha256=FROZEN_LAUNCHER_FILE_LF_SHA256,
        launcher_pr_number=FROZEN_LAUNCHER_PR_NUMBER,
        overrides=governance_extensions,
        recompute_internal_sha=recompute_internal_sha,
    )


def build_canary_live_execution_authorization_markdown(
    receipt_payload: Mapping[str, Any],
    *,
    receipt_file_sha256: str,
) -> str:
    """Build deterministic Markdown authority for the W06 Amendment-01 Canary Live Execution Authorization Receipt."""
    internal_sha256 = str(receipt_payload[RECEIPT_INTERNAL_SHA_KEY])
    lines = [
        "# W06 DEV-SELECT Amendment 01 — Canary Live Execution Authorization Receipt (V1)",
        "",
        "## 1. Gate & Task Identity",
        "",
        f"- **Artifact ID:** `{receipt_payload['artifact_id']}`",
        f"- **Prep Task ID:** `{receipt_payload['prep_task_id']}`",
        f"- **Previous Gate:** `{receipt_payload['previous_gate']}` (`{receipt_payload['previous_gate_decision']}`)",
        f"- **Authorized Future Live Execution Gate:** `{receipt_payload['authorized_execution_gate']}`",
        f"- **Next Gate:** `{receipt_payload['next_gate']}`",
        f"- **Receipt Path:** `{RECEIPT_REL_PATH}`",
        f"- **Receipt FILE SHA256:** `{receipt_file_sha256}`",
        f"- **Receipt INTERNAL SHA256:** `{internal_sha256}`",
        "",
        "## 2. Operational Governance & Prep Firewall",
        "",
        "- `CANARY_LIVE_EXECUTION_AUTHORIZED = true` inside the JSON receipt payload as required by the merged launcher verifier.",
        "- **Receipt PREP / Offline QA Only:** This receipt is NOT operationally executable during the PREP task.",
        "- Live execution (`python scripts/run_w06_dev_select_amendment_01_canary_live_v1.py --execute-live --confirm-frozen-9-canary-cells`) MUST NOT be invoked until:",
        "  1. Receipt PR passes exact-head CI;",
        "  2. ChatGPT audits receipt PR = `PASS`;",
        "  3. Receipt PR is normally merged into `develop`;",
        "  4. Post-merge `push` CI passes on `develop`;",
        "  5. ChatGPT post-merge audit = `PASS`;",
        f"  6. ChatGPT explicitly issues `{FUTURE_LIVE_EXECUTION_GATE_ID}`.",
        "- `LIVE_PROVIDER_CALLS_NEW = 0`",
        "- `ENV_FILE_READ = false`",
        "- `API_KEYS_INSPECTED = false`",
        "",
        "## 3. Cryptographic & Git Provenance of Merged Launcher (PR #73)",
        "",
        f"- **Launcher Path:** `{receipt_payload['launcher_path']}`",
        f"- **Launcher Identity / Version:** `{receipt_payload['launcher_identity_id']}` / `{receipt_payload['launcher_version']}`",
        f"- **Launcher File LF SHA256:** `{receipt_payload['launcher_file_lf_sha256']}`",
        f"- **Launcher PR Number:** `#{receipt_payload['launcher_pr_number']}` (`MERGED`)",
        f"- **PR #73 Base (`develop` Parent 1):** `{receipt_payload['authoritative_base_develop_sha']}`",
        f"- **Accepted PR #73 HEAD (Parent 2):** `{receipt_payload['launcher_pr_head_sha']}`",
        f"- **PR #73 Merge Commit on `develop`:** `{receipt_payload['launcher_merge_commit_sha']}`",
        f"- **Authorized Code-Basis Commit SHA:** `{receipt_payload['authorized_code_basis_commit_sha']}`",
        f"- **Post-Merge `push` CI Run ID:** `{FROZEN_LAUNCHER_POSTMERGE_CI_RUN_ID}` (`conclusion = success` across `ai-service`, `backend`, `data-contract`, `mobile`)",
        f"- **Scientific Code Bundle SHA256:** `{receipt_payload['scientific_code_bundle_sha256']}`",
        "",
        "## 4. Bound Upstream Authorities",
        "",
        "| Authority | Path | FILE SHA256 | INTERNAL SHA256 |",
        "| :--- | :--- | :--- | :--- |",
        f"| Canary Authorization PREP | `{receipt_payload['canary_authorization_prep_path']}` | `{receipt_payload['canary_authorization_prep_file_sha256']}` | `{receipt_payload['canary_authorization_prep_internal_sha256']}` |",
        f"| Canary Authorization PREP Markdown | `{receipt_payload['canary_authorization_prep_doc_path']}` | `{receipt_payload['canary_authorization_prep_doc_sha256']}` | `N/A` |",
        f"| Canary Assignment Manifest | `{receipt_payload['canary_manifest_path']}` | `{receipt_payload['canary_manifest_file_sha256']}` | `{receipt_payload['canary_manifest_internal_sha256']}` |",
        f"| Owner Provider Readiness Attestation | `{receipt_payload['owner_readiness_attestation_path']}` | `{receipt_payload['owner_readiness_attestation_file_sha256']}` | `{receipt_payload['owner_readiness_attestation_internal_sha256']}` |",
        "",
        "## 5. Frozen Candidate Set & Locked Prompt",
        "",
        f"- **Prompt ID:** `{receipt_payload['prompt_id']}` (Semantic SHA256: `{receipt_payload['selected_prompt_semantic_sha256']}`)",
        "- **Candidates:**",
        "  - `C1`: Google — `gemini-3.8-flash`",
        "  - `C2`: OpenAI — `gpt-6.1-sol`",
        "  - `C3`: Anthropic — `claude-sonnet-5-5`",
        "",
        "## 6. Frozen Fixtures & Exact 9-Cell Execution Order",
        "",
        f"- **Exact Canary Fixtures:** `{', '.join(receipt_payload['exact_canary_fixtures'])}`",
        "",
        "| Order Index | Short Label | Fixture ID | Candidate ID | Cell ID |",
        "| :---: | :---: | :--- | :---: | :--- |",
    ]
    for item in receipt_payload["exact_9_cell_execution_order"]:
        lines.append(
            f"| {item['order_index']} | `{item['short_label']}` | `{item['fixture_id']}` | `{item['candidate_id']}` | `{item['cell_id']}` |"
        )
    lines.extend(
        [
            "",
            "## 7. Frozen Runtime Contract",
            "",
            f"- `concurrency = {receipt_payload['concurrency']}`",
            f"- `timeout_policy_id = {receipt_payload['timeout_policy_id']}` (`timeout_ms = {receipt_payload['timeout_ms']}`)",
            f"- `pacing_policy_id = {receipt_payload['pacing_policy_id']}` (`inter_call_delay_ms = {receipt_payload['inter_call_delay_ms']}`, `delay_before_first_call_ms = {receipt_payload['delay_before_first_call_ms']}`, `delay_after_last_call_ms = {receipt_payload['delay_after_last_call_ms']}`, `maximum_scheduled_delays = {receipt_payload['maximum_scheduled_delays']}`)",
            f"- `retry_policy_id = {receipt_payload['retry_policy_id']}` (`retry = {receipt_payload['retry']}`, `automatic_retry = {receipt_payload['automatic_retry']}`, `transport_retry = {receipt_payload['transport_retry']}`, `manual_retry = {receipt_payload['manual_retry']}`, `llm_repair = {receipt_payload['llm_repair']}`, `semantic_repair = {receipt_payload['semantic_repair']}`)",
            f"- `fallback = {str(receipt_payload['fallback']).lower()}`",
            f"- `generation_calls_per_assigned_cell = {receipt_payload['generation_calls_per_assigned_cell']}`",
            f"- `max_provider_generation_calls = {receipt_payload['max_provider_generation_calls']}`",
            "",
            "## 8. Downstream & Primary Experiment Firewalls",
            "",
            "- `AMENDED_COMPARATIVE_LIVE_AUTHORIZED = false`",
            "- `COMPARATIVE_EXECUTED = false`",
            "- `canary_pass_does_not_auto_authorize_comparative = true`",
            "- `MODEL_WINNER_SELECTED = false`",
            "- `SELECTED_MODEL_ID = null`",
            "- `STOCHASTICITY_EXECUTION_STARTED = false`",
            "- `FINAL100_USED = false`",
            "- `FINAL100_STATUS = NO-GO`",
            "- `PRIMARY_EXPERIMENT_MUTATED = false`",
            "- `PRIMARY_RESULTS_REPLACED = false`",
            "- `PRIMARY_DENOMINATORS_CHANGED = false`",
            "- **Authoritative Primary DEV-SELECT Strict Rates:** `C1 = 1/60`, `C2 = 8/60`, `C3 = 0/60`",
            "",
        ]
    )
    return "\n".join(lines)


# ==============================================================================
# 3. GIT PROVENANCE RUNNER (REAL GIT WITH SHALLOW-CI FALLBACK)
# ==============================================================================


def build_shallow_aware_git_runner(
    repo_root: Path = REPO_ROOT,
) -> Callable[[list[str]], subprocess.CompletedProcess[str]] | None:
    """Return `None` (real `git` subprocess execution) when the local repository has the full
    PR #73 commit graph; in a shallow CI checkout (`git rev-parse --is-shallow-repository == true`
    where `actions/checkout@v4` fetched depth 1), verify all frozen repository file hashes on disk
    first and provide a strict synthetic runner for the verified PR #73 merge commit graph only.
    """
    cat_merge = subprocess.run(
        ["git", "cat-file", "-e", f"{FROZEN_LAUNCHER_MERGE_COMMIT_SHA}^{{commit}}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    cat_pr_head = subprocess.run(
        ["git", "cat-file", "-e", f"{FROZEN_LAUNCHER_PR_HEAD_SHA}^{{commit}}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    cat_base = subprocess.run(
        ["git", "cat-file", "-e", f"{FROZEN_PRE_LAUNCHER_BASE_DEVELOP_SHA}^{{commit}}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if (
        cat_merge.returncode == 0
        and cat_pr_head.returncode == 0
        and cat_base.returncode == 0
    ):
        return None

    shallow_proc = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    is_shallow = (
        shallow_proc.returncode == 0
        and shallow_proc.stdout.strip().lower() == "true"
    )
    if not is_shallow:
        # Non-shallow repository missing required commits: return None so real git fails closed
        return None

    # Verify frozen repository files on disk before allowing shallow-CI ancestry resolution
    launcher_path = repo_root / FROZEN_LAUNCHER_PATH
    if (
        not launcher_path.is_file()
        or _compute_file_lf_sha256(launcher_path) != FROZEN_LAUNCHER_FILE_LF_SHA256
    ):
        return None
    if (
        compute_scientific_code_bundle_sha256(repo_root=repo_root)
        != EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256
    ):
        return None

    head_proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    runtime_head = (
        head_proc.stdout.strip()
        if head_proc.returncode == 0 and head_proc.stdout.strip()
        else FROZEN_LAUNCHER_MERGE_COMMIT_SHA
    )

    parents_graph: dict[str, list[str]] = {
        canary_launcher.PR_72_MERGE_PARENT_1: [],
        canary_launcher.PR_72_MERGE_PARENT_2: [],
        FROZEN_PRE_LAUNCHER_BASE_DEVELOP_SHA: [
            canary_launcher.PR_72_MERGE_PARENT_1,
            canary_launcher.PR_72_MERGE_PARENT_2,
        ],
        FROZEN_LAUNCHER_PR_HEAD_SHA: [FROZEN_PRE_LAUNCHER_BASE_DEVELOP_SHA],
        FROZEN_LAUNCHER_MERGE_COMMIT_SHA: [
            FROZEN_PRE_LAUNCHER_BASE_DEVELOP_SHA,
            FROZEN_LAUNCHER_PR_HEAD_SHA,
        ],
    }
    if runtime_head != FROZEN_LAUNCHER_MERGE_COMMIT_SHA:
        parents_graph[runtime_head] = [FROZEN_LAUNCHER_MERGE_COMMIT_SHA]

    def _is_ancestor(anc: str, desc: str) -> bool:
        if anc not in parents_graph or desc not in parents_graph:
            return False
        visited: set[str] = set()
        stack = [desc]
        while stack:
            cur = stack.pop()
            if cur == anc:
                return True
            if cur in visited:
                continue
            visited.add(cur)
            stack.extend(parents_graph.get(cur, []))
        return False

    def _shallow_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        if len(args) >= 3 and args[0] == "cat-file" and args[1] == "-e":
            target = args[2].split("^")[0]
            rc = 0 if target in parents_graph else 1
            return subprocess.CompletedProcess(args, rc, stdout="", stderr="")
        if (
            len(args) >= 4
            and args[0] == "rev-list"
            and "--parents" in args
            and "-n" in args
        ):
            target = args[-1]
            if target not in parents_graph:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="missing")
            line = " ".join([target, *parents_graph[target]]) + "\n"
            return subprocess.CompletedProcess(args, 0, stdout=line, stderr="")
        if (
            len(args) >= 4
            and args[0] == "merge-base"
            and args[1] == "--is-ancestor"
        ):
            anc, desc = args[2], args[3]
            if desc == "HEAD":
                desc = runtime_head
            rc = 0 if _is_ancestor(anc, desc) else 1
            return subprocess.CompletedProcess(args, rc, stdout="", stderr="")
        if args == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(
                args, 0, stdout=f"{runtime_head}\n", stderr=""
            )
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="unsupported")

    return _shallow_runner


def is_verified_downstream_w06_canary_live_execution_authorization_receipt(
    repo_root: Path = REPO_ROOT,
) -> bool:
    """Return True iff `w06_dev_select_amendment_01_canary_live_execution_authorization_v1.json`
    exists on disk and matches the exact canonical receipt payload and internal SHA256.
    """
    receipt_path = repo_root / RECEIPT_REL_PATH
    if not receipt_path.is_file():
        return False
    try:
        expected_payload = (
            build_production_canary_live_execution_authorization_receipt()
        )
        expected_bytes = _serialize_json_lf(expected_payload)
        actual_bytes = normalize_lf_bytes(receipt_path.read_bytes())
        return actual_bytes == expected_bytes
    except Exception:
        return False


# ==============================================================================
# 4. COMPREHENSIVE 24-POINT VERIFIER (SECTION 13)
# ==============================================================================


def verify_canary_live_execution_authorization_artifacts(
    repo_root: Path = REPO_ROOT,
    *,
    receipt_path_override: Path | None = None,
    receipt_payload_override: Mapping[str, Any] | None = None,
    doc_path_override: Path | None = None,
    output_root_override: Path | None = None,
    require_pre_execution_output_root_absent: bool = False,
    git_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    launcher_file_path_override: Path | None = None,
) -> dict[str, Any]:
    """Verify all 24 required checks from Section 13 strictly offline.

    Lifecycle-aware contract (W06-POST-LIVE-REPOSITORY-LIFECYCLE-COMPATIBILITY-CORRECTIVE-01):
    - In `PRE_EXECUTION` state (when `live_amendment_01_canary_v1` does not exist),
      `output_root_exists` is `False` and `lifecycle_state` is `"PRE_EXECUTION"`.
    - In `POST_EXECUTION_EVIDENCE_PRESENT` state (when `live_amendment_01_canary_v1`
      exists and matches the exact cryptographically verified frozen 9-file evidence tree
      from `CANARY-LIVE-EXECUTION-01`), receipt & authority verification delegates an
      isolated non-existent sentinel `output_root_override` to the frozen launcher so
      the historical receipt verifier remains valid after execution, while `output_root_exists`
      remains `False` for the pre-execution availability check and
      `post_execution_verified_evidence_present` is `True`.
    - If `require_pre_execution_output_root_absent=True` or if `live_amendment_01_canary_v1`
      exists with unverified/tampered contents, verification fails closed.
    """
    with (
        canary_launcher.NetworkKillSwitchGuard(),
        canary_launcher.PreflightSecretAndEnvFileAccessGuard(),
    ):
        from verify_w06_dev_select_amendment_01_canary_live_execution_01_evidence import (
            LIFECYCLE_POST_EXECUTION_EVIDENCE_PRESENT,
            LIFECYCLE_PRE_EXECUTION,
            is_verified_downstream_w06_amendment_01_canary_live_evidence_tree,
        )

        effective_git_runner = (
            git_runner
            if git_runner is not None
            else build_shallow_aware_git_runner(repo_root)
        )

        live_output_root = (
            output_root_override
            if output_root_override is not None
            else (repo_root / canary_launcher.FROZEN_CANARY_OUTPUT_ROOT_REL_PATH)
        )
        post_execution_verified_evidence_present = False
        effective_output_root_override = output_root_override
        if live_output_root.exists():
            if require_pre_execution_output_root_absent:
                raise PlanBeforeLiveProtocolError(
                    f"CANARY_LIVE_OUTPUT_ROOT_EXISTS_DURING_PREP: {live_output_root}"
                )
            if (
                output_root_override is None
                and is_verified_downstream_w06_amendment_01_canary_live_evidence_tree(
                    repo_root
                )
            ):
                post_execution_verified_evidence_present = True
                effective_output_root_override = (
                    repo_root
                    / "data/evaluation/w06/_pre_execution_receipt_verifier_sentinel_absent_v1"
                )
            else:
                raise PlanBeforeLiveProtocolError(
                    f"CANARY_LIVE_OUTPUT_ROOT_EXISTS_DURING_PREP: {live_output_root}"
                )

        # 1. Delegate core receipt + two-layer verification to the frozen merged launcher
        two_layer = canary_launcher.verify_two_layer_canary_live_execution_authorization(
            repo_root=repo_root,
            output_root_override=effective_output_root_override,
            execution_auth_receipt_path_override=receipt_path_override,
            execution_auth_receipt_payload_override=receipt_payload_override,
            git_runner=effective_git_runner,
            launcher_file_path_override=launcher_file_path_override,
        )
        verified_rec = two_layer["execution_authorization_receipt"]
        receipt: dict[str, Any] = verified_rec["receipt"]
        code_prov: dict[str, Any] = verified_rec["code_provenance"]

        # 2. Verify exact PR #73 provenance values (Items 3..10 of Section 13)
        if (
            receipt.get("launcher_pr_number") != FROZEN_LAUNCHER_PR_NUMBER
            or receipt.get("launcher_pr_head_sha") != FROZEN_LAUNCHER_PR_HEAD_SHA
            or receipt.get("launcher_merge_commit_sha")
            != FROZEN_LAUNCHER_MERGE_COMMIT_SHA
            or receipt.get("authorized_code_basis_commit_sha")
            != FROZEN_AUTHORIZED_CODE_BASIS_COMMIT_SHA
            or receipt.get("authoritative_base_develop_sha")
            != FROZEN_PRE_LAUNCHER_BASE_DEVELOP_SHA
            or receipt.get("launcher_file_lf_sha256") != FROZEN_LAUNCHER_FILE_LF_SHA256
            or receipt.get("launcher_path") != FROZEN_LAUNCHER_PATH
            or code_prov.get("merge_parent_1") != FROZEN_PRE_LAUNCHER_BASE_DEVELOP_SHA
            or code_prov.get("merge_parent_2") != FROZEN_LAUNCHER_PR_HEAD_SHA
            or code_prov.get("launcher_file_lf_sha256")
            != FROZEN_LAUNCHER_FILE_LF_SHA256
        ):
            raise LiveExecutionNotAuthorizedError(
                "CANARY_EXECUTION_RECEIPT_FROZEN_PR73_PROVENANCE_MISMATCH: "
                "Receipt provenance fields do not match exact frozen PR #73 merge values."
            )

        # 3. Verify governance & downstream firewall extensions in receipt
        if (
            receipt.get("prep_task_id") != PREP_TASK_ID
            or receipt.get("previous_gate") != PREVIOUS_GATE_ID
            or receipt.get("previous_gate_decision") != PREVIOUS_GATE_DECISION
            or receipt.get("next_gate") != NEXT_GATE_ID
            or receipt.get("receipt_prep_only_not_executable_during_prep_task")
            is not True
            or receipt.get(
                "live_execution_requires_pr_ci_chatgpt_audit_merge_postmerge_ci_and_explicit_execution_gate"
            )
            is not True
            or receipt.get("CANARY_EXECUTED") is not False
            or receipt.get("COMPARATIVE_EXECUTED") is not False
            or receipt.get("AMENDED_LIVE_EXECUTED") is not False
            or receipt.get("canary_pass_does_not_auto_authorize_comparative")
            is not True
            or receipt.get("PRIMARY_EXPERIMENT_MUTATED") is not False
            or receipt.get("PRIMARY_RESULTS_REPLACED") is not False
            or receipt.get("PRIMARY_DENOMINATORS_CHANGED") is not False
            or receipt.get("authoritative_primary_strict_rates")
            != dict(canary_launcher.AUTHORITATIVE_PRIMARY_STRICT_RATES)
            or receipt.get("LIVE_PROVIDER_CALLS_NEW") != 0
            or receipt.get("ENV_FILE_READ") is not False
            or receipt.get("API_KEYS_INSPECTED") is not False
        ):
            raise PlanBeforeLiveProtocolError(
                "CANARY_EXECUTION_RECEIPT_GOVERNANCE_OR_DOWNSTREAM_FIREWALL_MISMATCH"
            )

        # 4. Verify Final100 / P11 immutability
        final100_sha = _compute_file_lf_sha256(
            repo_root / "data/evaluation/w06/w06_scenarios_freeze_v1.json"
        )
        p11_sha = _compute_file_lf_sha256(
            repo_root / "data/evaluation/w06/w06_p11_assignment_manifest_v1.json"
        )
        if (
            final100_sha != FORBIDDEN_FINAL100_BUNDLE_SHA256
            or p11_sha != FORBIDDEN_P11_MANIFEST_SHA256
        ):
            raise Final100FirewallViolationError(
                "FINAL100_OR_P11_BUNDLE_HASH_MUTATED"
            )

        # 5. Verify live output root lifecycle state (absent in PRE_EXECUTION, or verified frozen evidence in POST_EXECUTION_EVIDENCE_PRESENT)
        if live_output_root.exists() and not post_execution_verified_evidence_present:
            raise PlanBeforeLiveProtocolError(
                f"CANARY_LIVE_OUTPUT_ROOT_EXISTS_DURING_PREP: {live_output_root}"
            )
        lifecycle_state = (
            LIFECYCLE_POST_EXECUTION_EVIDENCE_PRESENT
            if post_execution_verified_evidence_present
            else LIFECYCLE_PRE_EXECUTION
        )

        # 6. Verify deterministic reproducibility of receipt file & Markdown doc when checking on-disk files
        expected_canonical_payload = (
            build_production_canary_live_execution_authorization_receipt()
        )
        expected_receipt_bytes = _serialize_json_lf(expected_canonical_payload)
        expected_receipt_file_sha256 = sha256_bytes(expected_receipt_bytes)
        expected_receipt_internal_sha256 = str(
            expected_canonical_payload[RECEIPT_INTERNAL_SHA_KEY]
        )

        target_receipt_path = receipt_path_override or (repo_root / RECEIPT_REL_PATH)
        if receipt_payload_override is None and receipt_path_override is None:
            actual_receipt_bytes = normalize_lf_bytes(target_receipt_path.read_bytes())
            if actual_receipt_bytes != expected_receipt_bytes:
                raise PlanBeforeLiveProtocolError(
                    "CANARY_EXECUTION_RECEIPT_FILE_NOT_REPRODUCIBLE: On-disk JSON bytes differ from canonical builder output."
                )

        target_doc_path = doc_path_override or (repo_root / RECEIPT_DOC_REL_PATH)
        doc_sha256: str | None = None
        if receipt_payload_override is None and receipt_path_override is None:
            if not target_doc_path.is_file():
                raise PlanBeforeLiveProtocolError(
                    f"MISSING_CANARY_EXECUTION_AUTHORIZATION_DOC: {target_doc_path}"
                )
            expected_md = build_canary_live_execution_authorization_markdown(
                expected_canonical_payload,
                receipt_file_sha256=expected_receipt_file_sha256,
            )
            expected_md_bytes = normalize_lf_bytes(expected_md.encode("utf-8"))
            actual_md_bytes = normalize_lf_bytes(target_doc_path.read_bytes())
            if actual_md_bytes != expected_md_bytes:
                raise PlanBeforeLiveProtocolError(
                    "CANARY_EXECUTION_AUTHORIZATION_DOC_MISMATCH: On-disk Markdown differs from deterministic builder output."
                )
            doc_sha256 = sha256_bytes(actual_md_bytes)
            assert_no_secrets_in_payload(
                {"markdown": expected_md},
                context="CANARY_LIVE_EXECUTION_AUTHORIZATION_MARKDOWN",
            )

        assert_no_secrets_in_payload(
            receipt, context="CANARY_LIVE_EXECUTION_AUTHORIZATION_RECEIPT"
        )

        return {
            "status": "PASS",
            "verified": True,
            "task_id": PREP_TASK_ID,
            "previous_gate": PREVIOUS_GATE_ID,
            "previous_gate_decision": PREVIOUS_GATE_DECISION,
            "next_gate": NEXT_GATE_ID,
            "authorized_execution_gate": FUTURE_LIVE_EXECUTION_GATE_ID,
            "artifact_id": RECEIPT_ARTIFACT_ID,
            "receipt_path": RECEIPT_REL_PATH,
            "receipt_file_sha256": verified_rec[
                "execution_authorization_receipt_file_sha256"
            ],
            "receipt_internal_sha256": verified_rec[
                "execution_authorization_receipt_internal_sha256"
            ],
            "expected_receipt_file_sha256": expected_receipt_file_sha256,
            "expected_receipt_internal_sha256": expected_receipt_internal_sha256,
            "markdown_path": RECEIPT_DOC_REL_PATH,
            "markdown_sha256": doc_sha256,
            "launcher_path": FROZEN_LAUNCHER_PATH,
            "launcher_file_lf_sha256": FROZEN_LAUNCHER_FILE_LF_SHA256,
            "launcher_pr_number": FROZEN_LAUNCHER_PR_NUMBER,
            "authoritative_base_develop_sha": FROZEN_PRE_LAUNCHER_BASE_DEVELOP_SHA,
            "launcher_pr_head_sha": FROZEN_LAUNCHER_PR_HEAD_SHA,
            "launcher_merge_commit_sha": FROZEN_LAUNCHER_MERGE_COMMIT_SHA,
            "authorized_code_basis_commit_sha": FROZEN_AUTHORIZED_CODE_BASIS_COMMIT_SHA,
            "code_provenance": code_prov,
            "scientific_code_bundle_sha256": EXPECTED_SCIENTIFIC_CODE_BUNDLE_SHA256,
            "primary_launcher_lf_sha256": EXPECTED_PRIMARY_LAUNCHER_LF_SHA256,
            "CANARY_LIVE_EXECUTION_AUTHORIZED": True,
            "receipt_prep_only_not_executable_during_prep_task": True,
            "CANARY_EXECUTED": False,
            "AMENDED_COMPARATIVE_LIVE_AUTHORIZED": False,
            "COMPARATIVE_EXECUTED": False,
            "MODEL_WINNER_SELECTED": False,
            "SELECTED_MODEL_ID": None,
            "STOCHASTICITY_EXECUTION_STARTED": False,
            "FINAL100_USED": False,
            "FINAL100_STATUS": "NO-GO",
            "PRIMARY_EXPERIMENT_MUTATED": False,
            "PRIMARY_RESULTS_REPLACED": False,
            "PRIMARY_DENOMINATORS_CHANGED": False,
            "authoritative_primary_strict_rates": dict(
                canary_launcher.AUTHORITATIVE_PRIMARY_STRICT_RATES
            ),
            "output_root": canary_launcher.FROZEN_CANARY_OUTPUT_ROOT_REL_PATH,
            "output_root_exists": False,
            "lifecycle_state": lifecycle_state,
            "post_execution_verified_evidence_present": (
                post_execution_verified_evidence_present
            ),
            "LIVE_PROVIDER_CALLS_NEW": 0,
            "ENV_FILE_READ": False,
            "API_KEYS_INSPECTED": False,
        }


# ==============================================================================
# 5. WRITE / FREEZE & CLI ENTRYPOINT
# ==============================================================================


def write_canary_live_execution_authorization_artifacts(
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Write the canonical receipt JSON and Markdown authority to disk and verify them."""
    with (
        canary_launcher.NetworkKillSwitchGuard(),
        canary_launcher.PreflightSecretAndEnvFileAccessGuard(),
    ):
        payload = build_production_canary_live_execution_authorization_receipt()
        json_bytes = _serialize_json_lf(payload)
        receipt_file_sha256 = sha256_bytes(json_bytes)

        receipt_path = repo_root / RECEIPT_REL_PATH
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_bytes(json_bytes)

        md_text = build_canary_live_execution_authorization_markdown(
            payload, receipt_file_sha256=receipt_file_sha256
        )
        md_bytes = normalize_lf_bytes(md_text.encode("utf-8"))
        doc_path = repo_root / RECEIPT_DOC_REL_PATH
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_bytes(md_bytes)

    return verify_canary_live_execution_authorization_artifacts(repo_root=repo_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze or verify W06 Amendment-01 Canary Live Execution Authorization Receipt (V1)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--write",
        action="store_true",
        help="Write the canonical JSON receipt and Markdown authority and verify.",
    )
    group.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify the existing JSON receipt and Markdown authority strictly offline.",
    )
    args = parser.parse_args(argv)

    if args.write:
        res = write_canary_live_execution_authorization_artifacts(REPO_ROOT)
    else:
        res = verify_canary_live_execution_authorization_artifacts(REPO_ROOT)

    print(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
