"""Targeted synthetic acceptance & fail-closed security tests for CORRECTIVE_REPLAY_01.

Verifies without touching or mutating the real 137-document corpus:
1. Exact live baseline SHA-256 bindings across all 13 Owner-pinned entries
   (`chunker_c1.py`, `real_corpus_preflight.py`, `visibility.py`, `runner.py`,
   Protocol v1.0, Annex v0.2.2, Stage A manifest, Waiver v1.0, preserved historical run).
2. Full synthetic end-to-end replay acceptance (`STUB-01..05` -> `EXECUTED_ONCE_PASS`)
   and stop-on-failure behavior (`STUB-02` failure -> `EXECUTED_ONCE_FAIL`, zero `STUB-03..05`).
3. Fail-closed blocks on duplicate replay #02 (`ALREADY_EXECUTED`), non-empty output dir,
   historical first-run overwrite attempts, wrong output paths, old `PROPOSED_PERMIT` draft,
   tampered decision/receipt/baseline digests, `STUB-06`/G3/G4/FINAL-50/network/API escalation,
   test keys, and plain env-var overrides.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Dict, Tuple

import pytest

from test_real_corpus_gated_stubs import (
    ARCHIVED_ANNEX_V022_PATH,
    ARCHIVED_CHAT_POLICY_RECEIPT_V1_PATH,
    ARCHIVED_CHAT_WAIVER_V1_PATH,
    ARCHIVED_RECEIPT_V022_PATH,
    _build_synthetic_dry_run_bundle_and_receipts,
)
from w07_retrieval.corrective_replay_01 import (
    CORRECTIVE_REPLAY_01_AUTH_MODE,
    CORRECTIVE_REPLAY_01_DECISION_ID,
    CORRECTIVE_REPLAY_01_DECISION_MD_SHA256,
    CORRECTIVE_REPLAY_01_ID,
    CORRECTIVE_REPLAY_01_RECEIPT_JSON_SHA256,
    PINNED_CORRECTIVE_REPLAY_01_OUTPUT_DIR,
    PINNED_PREVIOUS_REAL_RUN_SUMMARY_SHA256,
    PINNED_PREVIOUS_STUB01_PASS_SHA256,
    PINNED_PREVIOUS_STUB02_FAIL_SHA256,
    PINNED_REPLAY_01_BASELINE_SHA256,
    run_corrective_replay_01,
    validate_corrective_replay_01_gate,
)

DO_AN_ROOT = Path(__file__).resolve().parents[2]
REPLAY_PACK_DIR = DO_AN_ROOT / "W07_CORRECTIVE_REPLAY_01_PACK_2026-11-21"
REPLAY_DECISION_PATH = (
    REPLAY_PACK_DIR
    / "GOMATE_W07_CORRECTIVE_REPLAY_01_OWNER_APPROVAL_DECISION_2026-11-21.md"
)
REPLAY_RECEIPT_PATH = (
    REPLAY_PACK_DIR
    / "GOMATE_W07_CORRECTIVE_REPLAY_01_OWNER_CHAT_APPROVAL_RECEIPT_2026-11-21.json"
)
PROPOSED_PERMIT_JSON_PATH = (
    DO_AN_ROOT
    / "W07_STUB02_NARROW_CORRECTIVE_2026-11-21"
    / "GOMATE_W07_STUB01_05_CORRECTIVE_REPLAY_01_PROPOSED_POLICY_RECEIPT_2026-11-21.json"
)
PROTOCOL_V1_PATH = (
    DO_AN_ROOT
    / "wanderai"
    / "docs"
    / "research"
    / "W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md"
)
HISTORICAL_RUN_DIR = (
    DO_AN_ROOT / "W07_STUB01_05_REAL_CORPUS_PREFLIGHT_RUN_2026-11-21"
)
ORIG_EXEC_DECISION_PATH = (
    DO_AN_ROOT
    / "W07_STUB01_05_LOCAL_ACTIVATION_2026-11-21"
    / "GOMATE_W07_STUB01_05_OWNER_CHAT_EXECUTION_DECISION_2026-11-21.md"
)
PRIOR_RUN_ZIP_PATH = (
    DO_AN_ROOT / "GOMATE_W07_STUB01_05_REAL_CORPUS_PREFLIGHT_AUDIT_2026-11-21.zip"
)
PRIOR_CORRECTIVE_ZIP_PATH = (
    DO_AN_ROOT / "GOMATE_W07_STUB02_C1_NARROW_CORRECTIVE_AUDIT_2026-11-21.zip"
)


def _stage_synthetic_replay_fixture(
    tmp_path: Path,
) -> Tuple[Path, Path, Path, Path, Path, Dict]:
    """Create isolated synthetic dry-run bundle, policy receipt, historical dir, and replay approval receipt."""
    _, bundle_p, _, syn_expectations = _build_synthetic_dry_run_bundle_and_receipts(
        tmp_path
    )
    bundle_sha = hashlib.sha256(bundle_p.read_bytes()).hexdigest()

    base_policy_obj = json.loads(
        ARCHIVED_CHAT_POLICY_RECEIPT_V1_PATH.read_text(encoding="utf-8")
    )
    syn_policy_obj = dict(base_policy_obj)
    syn_policy_obj[
        "corpus_bundle_manifest_expected_sha256_reported_by_antigravity"
    ] = bundle_sha
    syn_policy_p = tmp_path / "syn_chat_policy.json"
    syn_policy_p.write_text(
        json.dumps(syn_policy_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "replay_01_out"
    hist_dir = tmp_path / "historical_first_run_copy"
    hist_dir.mkdir(parents=True, exist_ok=True)
    for fname, src_dir in (
        ("execution_summary.json", HISTORICAL_RUN_DIR),
        ("stub_01_result.json", HISTORICAL_RUN_DIR),
        ("stub_02_result.json", HISTORICAL_RUN_DIR),
    ):
        (hist_dir / fname).write_bytes((src_dir / fname).read_bytes())

    syn_replay_rec = json.loads(REPLAY_RECEIPT_PATH.read_text(encoding="utf-8"))
    syn_replay_rec["output_directory"] = str(out_dir)
    syn_replay_rec_p = tmp_path / "syn_replay_01_receipt.json"
    syn_replay_rec_p.write_text(
        json.dumps(syn_replay_rec, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_dir, syn_replay_rec_p, syn_policy_p, bundle_p, hist_dir, syn_expectations


def test_corrective_replay_01_owner_pack_and_pinned_hashes_match_live_host() -> None:
    """Verify Owner decision MD, JSON approval receipt, and all 13 live baseline hashes match exactly."""
    assert REPLAY_DECISION_PATH.is_file()
    assert REPLAY_RECEIPT_PATH.is_file()
    assert hashlib.sha256(REPLAY_DECISION_PATH.read_bytes()).hexdigest() == (
        CORRECTIVE_REPLAY_01_DECISION_MD_SHA256
    )
    assert hashlib.sha256(REPLAY_RECEIPT_PATH.read_bytes()).hexdigest() == (
        CORRECTIVE_REPLAY_01_RECEIPT_JSON_SHA256
    )

    rec_obj = json.loads(REPLAY_RECEIPT_PATH.read_text(encoding="utf-8"))
    assert rec_obj["replay_id"] == CORRECTIVE_REPLAY_01_ID
    assert rec_obj["auth_mode"] == CORRECTIVE_REPLAY_01_AUTH_MODE
    assert rec_obj["decision_id"] == CORRECTIVE_REPLAY_01_DECISION_ID
    assert rec_obj["authorizes_once"] is True
    assert Path(rec_obj["output_directory"]).resolve() == (
        PINNED_CORRECTIVE_REPLAY_01_OUTPUT_DIR.resolve()
    )
    assert rec_obj["baseline_sha256"] == PINNED_REPLAY_01_BASELINE_SHA256

    assert (
        hashlib.sha256(
            (HISTORICAL_RUN_DIR / "execution_summary.json").read_bytes()
        ).hexdigest()
        == PINNED_PREVIOUS_REAL_RUN_SUMMARY_SHA256
    )
    assert (
        hashlib.sha256(
            (HISTORICAL_RUN_DIR / "stub_01_result.json").read_bytes()
        ).hexdigest()
        == PINNED_PREVIOUS_STUB01_PASS_SHA256
    )
    assert (
        hashlib.sha256(
            (HISTORICAL_RUN_DIR / "stub_02_result.json").read_bytes()
        ).hexdigest()
        == PINNED_PREVIOUS_STUB02_FAIL_SHA256
    )


def test_corrective_replay_01_synthetic_acceptance_and_blocked_replay_02(
    tmp_path: Path,
) -> None:
    """Verify synthetic STUB-01..05 replay PASS, historical non-mutation, and duplicate replay #02 block."""
    out_dir, syn_rec_p, syn_policy_p, bundle_p, hist_dir, syn_exp = (
        _stage_synthetic_replay_fixture(tmp_path)
    )

    summary = run_corrective_replay_01(
        output_dir=out_dir,
        replay_decision_path=REPLAY_DECISION_PATH,
        replay_approval_receipt_path=syn_rec_p,
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        owner_chat_policy_receipt_path=syn_policy_p,
        chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
        original_exec_decision_path=ORIG_EXEC_DECISION_PATH,
        corpus_bundle_manifest_path=bundle_p,
        protocol_v1_path=PROTOCOL_V1_PATH,
        historical_run_dir=hist_dir,
        expectations=syn_exp,
        _synthetic_fixture_mode=True,
    )
    assert summary["overall_status"] == "EXECUTED_ONCE_PASS"
    assert summary["executed_stub_count"] == 5
    assert summary["replay_id"] == CORRECTIVE_REPLAY_01_ID
    assert summary["auth_mode"] == CORRECTIVE_REPLAY_01_AUTH_MODE
    assert summary["identity_authentication"] == "NOT_CRYPTOGRAPHICALLY_VERIFIED"
    assert summary["observable_counters"] == {
        "live_api_calls": 0,
        "network_requests": 0,
        "paid_api_spend_usd": 0.0,
    }
    assert summary["downstream_governance_hold"] == {
        "stub_06": "HOLD",
        "od_g15_05": "HOLD",
        "full_g15_closed": False,
        "g2_g3_g4_g5_g6_authorized": False,
        "final50_dev_t0_live_api_authorized": False,
        "public_push_merge_authorized": False,
    }
    assert (out_dir / "execution_summary.json").is_file()
    for idx in range(1, 6):
        assert (out_dir / f"stub_0{idx}_result.json").is_file()

    # Duplicate replay #02 into same output_dir is strictly blocked (ALREADY_EXECUTED)
    with pytest.raises(
        RuntimeError, match="CORRECTIVE_REPLAY_01_BLOCKED_ALREADY_EXECUTED"
    ):
        run_corrective_replay_01(
            output_dir=out_dir,
            replay_decision_path=REPLAY_DECISION_PATH,
            replay_approval_receipt_path=syn_rec_p,
            annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
            tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
            owner_chat_policy_receipt_path=syn_policy_p,
            chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
            original_exec_decision_path=ORIG_EXEC_DECISION_PATH,
            corpus_bundle_manifest_path=bundle_p,
            protocol_v1_path=PROTOCOL_V1_PATH,
            historical_run_dir=hist_dir,
            expectations=syn_exp,
            _synthetic_fixture_mode=True,
        )


def test_corrective_replay_01_fail_closed_security_and_stop_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify negative blocks: env overrides, wrong paths/hashes, draft permit, scopes, and stop-on-fail."""
    out_dir, syn_rec_p, syn_policy_p, bundle_p, hist_dir, syn_exp = (
        _stage_synthetic_replay_fixture(tmp_path)
    )
    base_kwargs = dict(
        output_dir=out_dir,
        replay_decision_path=REPLAY_DECISION_PATH,
        replay_approval_receipt_path=syn_rec_p,
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        owner_chat_policy_receipt_path=syn_policy_p,
        chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
        original_exec_decision_path=ORIG_EXEC_DECISION_PATH,
        corpus_bundle_manifest_path=bundle_p,
        protocol_v1_path=PROTOCOL_V1_PATH,
        historical_run_dir=hist_dir,
        _synthetic_fixture_mode=True,
    )

    # 1. Env vars cannot bypass missing receipts
    for env_k in (
        "W07_G15_FROZEN",
        "W07_OWNER_AUTHORIZED",
        "W07_STUB_01_05_AUTHORIZED",
        "W07_CORRECTIVE_REPLAY_01_AUTHORIZED",
    ):
        monkeypatch.setenv(env_k, "1")
    with pytest.raises(
        PermissionError,
        match="CORRECTIVE_REPLAY_01_BLOCKED_MISSING_RECEIPTS.*Plain environment variables",
    ):
        validate_corrective_replay_01_gate(
            **{**base_kwargs, "replay_approval_receipt_path": None}
        )

    # 2. Test keys strictly forbidden
    with pytest.raises(PermissionError, match="CORRECTIVE_REPLAY_01_BLOCKED_TEST_KEY_FORBIDDEN"):
        validate_corrective_replay_01_gate(
            **base_kwargs, _test_only_trusted_owner_pubkey_hex="aa" * 32
        )

    # 3. STUB-06 / G3 / G4 / wider scope rejected
    with pytest.raises(PermissionError, match="CORRECTIVE_REPLAY_01_BLOCKED_FORBIDDEN_STUB_ID"):
        validate_corrective_replay_01_gate(**base_kwargs, requested_stubs=["STUB-06"])

    # 4. Old non-executable PROPOSED_PERMIT draft rejected
    if PROPOSED_PERMIT_JSON_PATH.is_file():
        with pytest.raises(
            PermissionError,
            match="CORRECTIVE_REPLAY_01_BLOCKED_PROPOSAL_DRAFT_NOT_AUTHORIZED",
        ):
            validate_corrective_replay_01_gate(
                **{**base_kwargs, "replay_approval_receipt_path": PROPOSED_PERMIT_JSON_PATH}
            )

    # 5. Live mode rejects synthetic / modified approval receipt digest
    with pytest.raises(
        PermissionError,
        match="CORRECTIVE_REPLAY_01_BLOCKED_APPROVAL_RECEIPT_HASH_MISMATCH",
    ):
        validate_corrective_replay_01_gate(
            **{
                **base_kwargs,
                "output_dir": PINNED_CORRECTIVE_REPLAY_01_OUTPUT_DIR,
                "previous_real_run_zip_path": PRIOR_RUN_ZIP_PATH,
                "prior_c1_corrective_zip_path": PRIOR_CORRECTIVE_ZIP_PATH,
                "_synthetic_fixture_mode": False,
            }
        )

    # 6. Wrong output path & historical run dir overwrite rejected
    with pytest.raises(PermissionError, match="CORRECTIVE_REPLAY_01_BLOCKED_OUTPUT_PATH_MISMATCH"):
        validate_corrective_replay_01_gate(**{**base_kwargs, "output_dir": tmp_path / "wrong_dir"})

    with pytest.raises(
        PermissionError,
        match="CORRECTIVE_REPLAY_01_BLOCKED_CANNOT_OVERWRITE_HISTORICAL_RUN",
    ):
        validate_corrective_replay_01_gate(**{**base_kwargs, "output_dir": hist_dir})

    # 7. Scope escalation flags in receipt rejected
    base_rec_obj = json.loads(syn_rec_p.read_text(encoding="utf-8"))
    for esc_key in ("formal_g3_g4_authorized", "final50_dev_t0_authorized", "stub06_authorized", "network_authorized"):
        bad_obj = dict(base_rec_obj)
        bad_obj[esc_key] = True
        bad_p = tmp_path / f"bad_{esc_key}.json"
        bad_p.write_text(json.dumps(bad_obj), encoding="utf-8")
        with pytest.raises(PermissionError, match="CORRECTIVE_REPLAY_01_BLOCKED_SCOPE_ESCALATION_FORBIDDEN"):
            validate_corrective_replay_01_gate(
                **{**base_kwargs, "replay_approval_receipt_path": bad_p}
            )

    # 8. Wrong baseline digest in receipt rejected
    bad_base_obj = dict(base_rec_obj)
    bad_base_obj["baseline_sha256"] = dict(base_rec_obj["baseline_sha256"])
    bad_base_obj["baseline_sha256"]["chunker_c1_corrected_sha256"] = "0" * 64
    bad_base_p = tmp_path / "bad_baseline.json"
    bad_base_p.write_text(json.dumps(bad_base_obj), encoding="utf-8")
    with pytest.raises(PermissionError, match="CORRECTIVE_REPLAY_01_BLOCKED_BASELINE_SHA256_MISMATCH"):
        validate_corrective_replay_01_gate(
            **{**base_kwargs, "replay_approval_receipt_path": bad_base_p}
        )

    # 8b. Wrong decision doc hash & non-empty output_dir rejected
    bad_dec_p = tmp_path / "bad_decision.md"
    bad_dec_p.write_text("tampered decision", encoding="utf-8")
    with pytest.raises(PermissionError, match="CORRECTIVE_REPLAY_01_BLOCKED_DECISION_DOC_HASH_MISMATCH"):
        validate_corrective_replay_01_gate(
            **{**base_kwargs, "replay_decision_path": bad_dec_p}
        )

    # 8c. Unapproved on-disk real_corpus_preflight.py SHA-256 rejected fail-closed
    with monkeypatch.context() as mp_src:
        mp_src.setattr(
            "w07_retrieval.corrective_replay_01.ALLOWED_ON_DISK_PREFLIGHT_SHA256S",
            frozenset({"0" * 64}),
        )
        with pytest.raises(PermissionError, match="CORRECTIVE_REPLAY_01_BLOCKED_SRC_SHA256_MISMATCH"):
            validate_corrective_replay_01_gate(**base_kwargs)

    non_empty_out = tmp_path / "non_empty_out"
    non_empty_out.mkdir(parents=True, exist_ok=True)
    (non_empty_out / "stray.txt").write_text("stray", encoding="utf-8")
    rec_non_empty = dict(base_rec_obj)
    rec_non_empty["output_directory"] = str(non_empty_out)
    rec_non_empty_p = tmp_path / "rec_non_empty.json"
    rec_non_empty_p.write_text(json.dumps(rec_non_empty), encoding="utf-8")
    with pytest.raises(PermissionError, match="CORRECTIVE_REPLAY_01_BLOCKED_OUTPUT_DIR_NOT_EMPTY"):
        validate_corrective_replay_01_gate(
            **{**base_kwargs, "output_dir": non_empty_out, "replay_approval_receipt_path": rec_non_empty_p}
        )

    # 9. Stop-on-failure check: if STUB-02 fails, replay stops at STUB-02 and blocks subsequent retry
    bad_stub02_exp = replace(syn_exp, expected_allowlisted_footer_drops=999)
    fail_sum = run_corrective_replay_01(
        output_dir=out_dir,
        replay_decision_path=REPLAY_DECISION_PATH,
        replay_approval_receipt_path=syn_rec_p,
        annex_v0_2_2_path=ARCHIVED_ANNEX_V022_PATH,
        tech_freeze_receipt_path=ARCHIVED_RECEIPT_V022_PATH,
        owner_chat_policy_receipt_path=syn_policy_p,
        chat_auth_waiver_path=ARCHIVED_CHAT_WAIVER_V1_PATH,
        original_exec_decision_path=ORIG_EXEC_DECISION_PATH,
        corpus_bundle_manifest_path=bundle_p,
        protocol_v1_path=PROTOCOL_V1_PATH,
        historical_run_dir=hist_dir,
        expectations=bad_stub02_exp,
        _synthetic_fixture_mode=True,
    )
    assert fail_sum["overall_status"] == "EXECUTED_ONCE_FAIL"
    assert fail_sum["stopped_on_stub"] == "STUB-02"
    assert fail_sum["executed_stub_count"] == 2
    assert (out_dir / "stub_01_result.json").is_file()
    assert (out_dir / "stub_02_result.json").is_file()
    assert not (out_dir / "stub_03_result.json").exists()
    with pytest.raises(RuntimeError, match="CORRECTIVE_REPLAY_01_BLOCKED_ALREADY_EXECUTED"):
        validate_corrective_replay_01_gate(**base_kwargs)
