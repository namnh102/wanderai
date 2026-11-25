"""Targeted synthetic acceptance & fail-closed security tests for TARGETED_STUB05_ONLY_REPLAY."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import socket
from typing import Any, Dict, Tuple

import pytest

from test_real_corpus_gated_stubs import (
    ARCHIVED_ANNEX_V022_PATH,
    ARCHIVED_CHAT_POLICY_RECEIPT_V1_PATH,
    ARCHIVED_CHAT_WAIVER_V1_PATH,
    ARCHIVED_RECEIPT_V022_PATH,
    _build_synthetic_dry_run_bundle_and_receipts,
)
from w07_retrieval.real_corpus_preflight import LIVE_137_CORPUS_EXPECTATIONS
from w07_retrieval.targeted_stub05_only_replay import (
    PINNED_CORRECTIVE_AUDIT_ZIP_SHA256,
    PINNED_CORRECTIVE_REPLAY_01_DIR,
    PINNED_OWNER_ORDER_MD_SHA256,
    PINNED_PERMIT_RECEIPT_SHA256,
    PINNED_TARGET_OVERTURE_DOC_ID,
    PINNED_TARGETED_REPLAY_BASELINE_SHA256,
    PINNED_TARGETED_STUB05_OUTPUT_DIR,
    TARGETED_REPLAY_AUTH_MODE,
    TARGETED_REPLAY_DECISION_ID,
    TARGETED_REPLAY_ID,
    run_targeted_stub05_only_replay,
    validate_targeted_stub05_only_gate,
)

PREP_ROOT = Path(__file__).resolve().parents[1]
DO_AN_ROOT = PREP_ROOT.parent
PACK_DIR = DO_AN_ROOT / "W07_STUB05_TARGETED_REPLAY_01_PACK_2026-11-21"
OWNER_ORDER_MD_PATH = (
    PACK_DIR / "GOMATE_OWNER_APPROVED_PARALLEL_EXECUTION_ORDER_2026-11-21.md"
)
PERMIT_RECEIPT_PATH = (
    PACK_DIR / "GOMATE_W07_STUB05_TARGETED_REPLAY_01_PERMIT_RECEIPT_2026-11-21.json"
)
PROTOCOL_V1_PATH = (
    DO_AN_ROOT
    / "W07_B2_G1_5_ANNEX_CORRECTIVE_02"
    / "01_controlling_authorities_and_audit_receipts"
    / "W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md"
)
ORIG_EXEC_DECISION_PATH = (
    DO_AN_ROOT
    / "W07_STUB01_05_LOCAL_ACTIVATION_2026-11-21"
    / "GOMATE_W07_STUB01_05_OWNER_CHAT_EXECUTION_DECISION_2026-11-21.md"
)
CORRECTIVE_AUDIT_ZIP_PATH = (
    DO_AN_ROOT / "GOMATE_W07_STUB05_NARROW_HARNESS_CORRECTIVE_AUDIT_2026-11-21.zip"
)


def _stage_synthetic_targeted_fixture(
    tmp_path: Path,
    *,
    inject_newline_before_r_audit: bool = False,
    break_target_doc: bool = False,
) -> Tuple[Path, Path, Path, Path, Path, Any]:
    """Create isolated synthetic dry-run bundle, policy receipt, replay-01 copy, and permit."""
    _, bundle_p, _, syn_expectations = _build_synthetic_dry_run_bundle_and_receipts(
        tmp_path
    )

    if inject_newline_before_r_audit or break_target_doc:
        bundle_obj = json.loads(bundle_p.read_text(encoding="utf-8"))
        jsonl_rel = bundle_obj["primary_corpus_jsonl"]
        jsonl_p = (bundle_p.parent / jsonl_rel).resolve()
        lines = jsonl_p.read_text(encoding="utf-8").splitlines()
        new_lines = []
        for raw in lines:
            rec = json.loads(raw)
            if rec.get("document_id") == syn_expectations.overture_target_doc_id:
                if break_target_doc:
                    rec["canonical_text_S"] = "Tài liệu ngắn không có thẻ cần kiểm tra."
                else:
                    tag_nl = (
                        "[CORROBORATED: canonical_poi:00000000-0000-0000-0000-000000000001, "
                        "osm:node/101, wikidata:Q101, wikipedia:vi:Van_Mieu]"
                    )
                    filler_nl = (
                        "Văn Miếu Quốc Tử Giám tại Hà Nội lưu giữ bia tiến sĩ đá cổ và kiến trúc truyền thống Việt Nam. "
                        * 14
                    )
                    rec["canonical_text_S"] = (
                        f"Bảo tàng giới thiệu khu di tích (museum) {tag_nl}.\n"
                        f"Độ tin cậy nguồn (confidence): 0.8500. {filler_nl}"
                        "Mã ARCHIVE-TAIL-9981."
                    )
            new_lines.append(json.dumps(rec, ensure_ascii=False))
        jsonl_bytes = ("\n".join(new_lines) + "\n").encode("utf-8")
        jsonl_p.write_bytes(jsonl_bytes)
        for art in bundle_obj["artifacts"]:
            if art["canonical_repo_path"] == jsonl_rel or jsonl_p.name in art["relative_path"]:
                art["sha256"] = hashlib.sha256(jsonl_bytes).hexdigest()
                art["size_bytes"] = len(jsonl_bytes)
        bundle_p.write_text(
            json.dumps(bundle_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
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

    out_dir = tmp_path / "targeted_stub05_out"
    replay01_copy = tmp_path / "replay_01_preserved_copy"
    replay01_copy.mkdir(parents=True, exist_ok=True)
    for fname in (
        "execution_summary.json",
        "stub_01_result.json",
        "stub_02_result.json",
        "stub_03_result.json",
        "stub_04_result.json",
        "stub_05_result.json",
    ):
        (replay01_copy / fname).write_bytes(
            (PINNED_CORRECTIVE_REPLAY_01_DIR / fname).read_bytes()
        )

    syn_permit = json.loads(PERMIT_RECEIPT_PATH.read_text(encoding="utf-8"))
    syn_permit["output_directory"] = str(out_dir)
    syn_permit["target_document_id"] = syn_expectations.overture_target_doc_id
    syn_permit_p = tmp_path / "syn_targeted_permit.json"
    syn_permit_p.write_text(
        json.dumps(syn_permit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return out_dir, syn_permit_p, syn_policy_p, bundle_p, replay01_copy, syn_expectations


def _run_params(
    *,
    out_dir: Path,
    permit_p: Path,
    policy_p: Path,
    bundle_p: Path,
    replay01_copy: Path,
    syn_exp: Any,
) -> Dict[str, Any]:
    return {
        "requested_stubs": ("STUB-05",),
        "output_dir": out_dir,
        "owner_order_md_path": OWNER_ORDER_MD_PATH,
        "permit_receipt_path": permit_p,
        "annex_v0_2_2_path": ARCHIVED_ANNEX_V022_PATH,
        "tech_freeze_receipt_path": ARCHIVED_RECEIPT_V022_PATH,
        "owner_chat_policy_receipt_path": policy_p,
        "chat_auth_waiver_path": ARCHIVED_CHAT_WAIVER_V1_PATH,
        "original_exec_decision_path": ORIG_EXEC_DECISION_PATH,
        "corpus_bundle_manifest_path": bundle_p,
        "protocol_v1_path": PROTOCOL_V1_PATH,
        "corrective_audit_zip_path": CORRECTIVE_AUDIT_ZIP_PATH,
        "corrective_replay_01_dir": replay01_copy,
        "expectations": syn_exp,
        "_synthetic_fixture_mode": True,
    }


def test_targeted_stub05_pack_and_pinned_hashes_match_live_host() -> None:
    """Verify Owner Execution Order MD, Permit Receipt JSON, and all 18 pinned baseline hashes match host."""
    assert OWNER_ORDER_MD_PATH.is_file()
    assert PERMIT_RECEIPT_PATH.is_file()
    assert CORRECTIVE_AUDIT_ZIP_PATH.is_file()
    assert (
        hashlib.sha256(OWNER_ORDER_MD_PATH.read_bytes()).hexdigest()
        == PINNED_OWNER_ORDER_MD_SHA256
    )
    assert (
        hashlib.sha256(PERMIT_RECEIPT_PATH.read_bytes()).hexdigest()
        == PINNED_PERMIT_RECEIPT_SHA256
    )
    assert (
        hashlib.sha256(CORRECTIVE_AUDIT_ZIP_PATH.read_bytes()).hexdigest()
        == PINNED_CORRECTIVE_AUDIT_ZIP_SHA256
    )
    rec = json.loads(PERMIT_RECEIPT_PATH.read_text(encoding="utf-8"))
    assert rec["replay_id"] == TARGETED_REPLAY_ID
    assert rec["decision_id"] == TARGETED_REPLAY_DECISION_ID
    assert rec["auth_mode"] == TARGETED_REPLAY_AUTH_MODE
    assert rec["allowed_stubs"] == ["STUB-05"]
    assert rec["target_document_id"] == PINNED_TARGET_OVERTURE_DOC_ID
    assert rec["baseline_sha256"] == PINNED_TARGETED_REPLAY_BASELINE_SHA256
    assert (
        Path(rec["output_directory"]).resolve()
        == PINNED_TARGETED_STUB05_OUTPUT_DIR.resolve()
    )


def test_targeted_stub05_synthetic_acceptance_and_single_use_lock(tmp_path: Path) -> None:
    """Verify single-stub STUB-05 synthetic PASS, single-use lock creation, and replay #02 rejection."""
    out_dir, syn_permit_p, syn_policy_p, bundle_p, replay01_copy, syn_exp = (
        _stage_synthetic_targeted_fixture(tmp_path, inject_newline_before_r_audit=True)
    )
    kwargs = _run_params(
        out_dir=out_dir,
        permit_p=syn_permit_p,
        policy_p=syn_policy_p,
        bundle_p=bundle_p,
        replay01_copy=replay01_copy,
        syn_exp=syn_exp,
    )

    summary = run_targeted_stub05_only_replay(**kwargs)
    assert summary["overall_status"] == "EXECUTED_ONCE_PASS"
    assert summary["executed_stub_count"] == 1
    assert summary["executed_stub_id"] == "STUB-05"
    assert summary["stub01_04_rerun"] is False
    assert summary["target_document_id"] == syn_exp.overture_target_doc_id
    assert summary["replay_consumed_guard"]["single_use_consumed"] is True
    assert summary["replay_consumed_guard"]["future_auto_replay_blocked"] is True
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
    assert (out_dir / "stub_05_result.json").is_file()
    assert (out_dir / "single_use_consumed_lock.json").is_file()

    stub05_obj = json.loads((out_dir / "stub_05_result.json").read_text(encoding="utf-8"))
    metrics = stub05_obj["metrics"]
    assert stub05_obj["status"] == "PASS"
    assert metrics["tail_span_evidence_hit"] is True
    assert metrics["tail_span_visible_hit"] is False
    assert metrics["cutoff_straddle_evidence_hit"] is True
    assert metrics["cutoff_straddle_visible_hit"] is False
    assert metrics["deleted_tag_chars_in_c_vis"] == 0
    assert (
        metrics["early_r_audit_straddle_scope"]
        == "MARKER_ADJACENCY_AND_PROJECTION_FIDELITY_NOT_SUBSTANTIVE_LEXICAL_EVIDENCE"
    )
    assert metrics["early_r_audit_straddle_blind_crossed_newline"] is True
    assert metrics["early_r_audit_newline_negative_evidence_hit"] is False
    assert metrics["early_r_audit_newline_negative_visible_hit"] is False
    assert metrics["early_r_audit_straddle_visible_hit"] is True

    # Attempt #02 against consumed output dir MUST fail closed
    with pytest.raises(RuntimeError, match="TARGETED_STUB05_REPLAY_BLOCKED_ALREADY_EXECUTED"):
        run_targeted_stub05_only_replay(**kwargs)


def test_targeted_stub05_preserves_fail_honestly_and_still_locks_once(tmp_path: Path) -> None:
    """Verify STUB-05 failure is recorded honestly as EXECUTED_ONCE_FAIL and consumes the lock."""
    out_dir, syn_permit_p, syn_policy_p, bundle_p, replay01_copy, syn_exp = (
        _stage_synthetic_targeted_fixture(tmp_path, break_target_doc=True)
    )
    kwargs = _run_params(
        out_dir=out_dir,
        permit_p=syn_permit_p,
        policy_p=syn_policy_p,
        bundle_p=bundle_p,
        replay01_copy=replay01_copy,
        syn_exp=syn_exp,
    )
    summary = run_targeted_stub05_only_replay(**kwargs)
    assert summary["overall_status"] == "EXECUTED_ONCE_FAIL"
    assert summary["stub_05_result"]["status"] == "FAIL"
    assert "R_AUDIT" in summary["stub_05_result"]["error_code"]
    assert (out_dir / "single_use_consumed_lock.json").is_file()

    with pytest.raises(RuntimeError, match="TARGETED_STUB05_REPLAY_BLOCKED_ALREADY_EXECUTED"):
        run_targeted_stub05_only_replay(**kwargs)


def test_targeted_stub05_fail_closed_security_and_scope_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify fail-closed blocks on STUB-01..04, STUB-06, env spoofs, test keys, collisions, tampering, and network."""
    out_dir, syn_permit_p, syn_policy_p, bundle_p, replay01_copy, syn_exp = (
        _stage_synthetic_targeted_fixture(tmp_path)
    )
    base_kwargs = _run_params(
        out_dir=out_dir,
        permit_p=syn_permit_p,
        policy_p=syn_policy_p,
        bundle_p=bundle_p,
        replay01_copy=replay01_copy,
        syn_exp=syn_exp,
    )
    validate_kwargs = {k: v for k, v in base_kwargs.items()}

    # 1. STUB-01..04 and STUB-06 blocked
    for forbidden_stubs in (("STUB-01",), ("STUB-04",), ("STUB-01", "STUB-05"), ("STUB-06",)):
        kw = dict(validate_kwargs, requested_stubs=forbidden_stubs)
        with pytest.raises(PermissionError, match="FORBIDDEN_STUB_SELECTION"):
            validate_targeted_stub05_only_gate(**kw)

    # 2. Test pubkey forbidden
    with pytest.raises(PermissionError, match="TEST_KEY_FORBIDDEN"):
        validate_targeted_stub05_only_gate(
            **dict(validate_kwargs, _test_only_trusted_owner_pubkey_hex="ab" * 32)
        )

    # 3. Env var spoofing alone blocked
    monkeypatch.setenv("W07_TARGETED_STUB05_ONLY_AUTHORIZED", "1")
    monkeypatch.setenv("W07_OWNER_AUTHORIZED", "1")
    with pytest.raises(PermissionError, match="MISSING_RECEIPTS"):
        validate_targeted_stub05_only_gate(
            **dict(validate_kwargs, owner_order_md_path=None, permit_receipt_path=None)
        )

    # 4. Prior run dir collisions blocked
    with pytest.raises(PermissionError, match="CANNOT_OVERWRITE_PRIOR_RUN"):
        validate_targeted_stub05_only_gate(
            **dict(validate_kwargs, output_dir=replay01_copy)
        )

    # 5. Live unpinned output dir blocked when _synthetic_fixture_mode=False
    with pytest.raises(PermissionError, match="HASH_MISMATCH|UNPINNED"):
        validate_targeted_stub05_only_gate(
            **dict(
                validate_kwargs,
                _synthetic_fixture_mode=False,
                expectations=LIVE_137_CORPUS_EXPECTATIONS,
            )
        )

    # 6. Tampered baseline SHA-256 rejected
    bad_permit = json.loads(syn_permit_p.read_text(encoding="utf-8"))
    bad_permit["baseline_sha256"]["chunker_c1_sha256"] = "0" * 64
    bad_permit_p = tmp_path / "bad_permit.json"
    bad_permit_p.write_text(json.dumps(bad_permit), encoding="utf-8")
    with pytest.raises(PermissionError, match="BASELINE_SHA256_MISMATCH"):
        validate_targeted_stub05_only_gate(**dict(validate_kwargs, permit_receipt_path=bad_permit_p))

    # 7. Tampered CORRECTIVE_REPLAY_01 consumed lock rejected (cannot unlock Replay 01)
    tampered_r01 = tmp_path / "tampered_replay01"
    shutil.copytree(replay01_copy, tampered_r01)
    r01_sum_p = tampered_r01 / "execution_summary.json"
    r01_sum = json.loads(r01_sum_p.read_text(encoding="utf-8"))
    r01_sum["replay_consumed_guard"]["single_use_consumed"] = False
    r01_sum_p.write_text(json.dumps(r01_sum), encoding="utf-8")
    with pytest.raises(PermissionError, match="REPLAY01_HASH_MISMATCH"):
        validate_targeted_stub05_only_gate(**dict(validate_kwargs, corrective_replay_01_dir=tampered_r01))

    # 8. Outbound non-loopback socket connection blocked during execution
    def _evil_exec(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        socket.create_connection(("example.com", 443), timeout=1)
        return {}

    monkeypatch.setattr(
        "w07_retrieval.targeted_stub05_only_replay.execute_stub05_fx05_overture_visibility",
        _evil_exec,
    )
    res_net = run_targeted_stub05_only_replay(**base_kwargs)
    assert res_net["overall_status"] == "EXECUTED_ONCE_FAIL"
    assert res_net["observable_counters"]["network_requests"] == 1
    assert "OUTBOUND_NETWORK_BLOCKED" in res_net["stub_05_result"]["error_code"]
