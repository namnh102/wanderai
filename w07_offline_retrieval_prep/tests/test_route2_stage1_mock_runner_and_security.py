"""Security, S/V cloud boundary, Ed25519 trust-root, and mock-only Stage-1 DEV canary tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from fixtures.g4_fixtures import make_query_dict
from w07_retrieval.sanitizer import sanitize_canonical_to_view
from w07_g4_scorer.contracts import sha256_bytes
from w07_g4_scorer.route2_aiproxy import (
    ANNEX_V0_2_2_SHA256,
    PROTOCOL_V1_0_SHA256,
    ROUTE2_AUDITOR_VERDICT_DOMAIN_TAG,
    ROUTE2_HARMONIZATION_ID,
    ROUTE2_OD_AE_05_DOMAIN_TAG,
    ROUTE2_OWNER_ACTIVATION_DOMAIN_TAG,
    ROUTE2_PROVIDER_PREFLIGHT_DOMAIN_TAG,
    ROUTE2_SV01_EVIDENCE_DOMAIN_TAG,
    ROUTE2_TRUST_ROOT_DOMAIN_TAG,
    assert_cloud_payload_v_boundary,
    build_sanitized_v_cloud_request_payload,
    canonical_route2_signing_bytes,
    project_cloud_quote_locally_to_canonical_s,
    validate_route2_authorization_bundle,
)
from w07_g4_scorer.route2_dev_canary_runner import (
    ProviderRateProfile,
    run_stage1_dev_canary_mock_batch,
)

PROMPT_V1_1_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["grade", "evidence_quote", "char_start", "char_end"],
    "properties": {
        "grade": {"type": "string", "enum": ["REL_0", "REL_1", "REL_2", "NA"]},
        "evidence_quote": {"type": ["string", "null"]},
        "char_start": {"type": ["integer", "null"]},
        "char_end": {"type": ["integer", "null"]},
    },
}


def _sign_payload(sk: Ed25519PrivateKey, tag: bytes, body: dict[str, Any], sig_field: str) -> dict[str, Any]:
    out = dict(body)
    out[sig_field] = sk.sign(canonical_route2_signing_bytes(tag, out)).hex()
    return out


def _build_signed_stage1_bundle_and_trust(
    *,
    authorized_stage: str = "STAGE1_DEV_CANARY_ONLY",
    final_50_authorized: bool = False,
    anthropic_retention_ack: bool = True,
    cap_regime: str = "UNAMENDED_20USD",
    tamper_owner_sig: bool = False,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], str, str]:
    tpl = json.loads(
        (Path(__file__).resolve().parents[1] / "docs" / "W07_ROUTE2_AIPROXY_BUNDLE_TEMPLATE_V1.json").read_text(
            encoding="utf-8"
        )
    )
    tpl.update(
        {
            "explicit_frozen_rule_sv01_waiver_amendment_ratified": True,
            "owner_reported_supervisor_waiver_accepted_by_audit_and_owner": True,
            "chatgpt_audit_verdict": "PASS",
            "owner_signed_amendment_receipt_verified": True,
            "external_trust_root_provisioned": True,
            "od_ae_05_data_rights_and_batch_retention_signed": True,
            "live_account_rates_and_count_tokens_verified": True,
            "budget40_signed_activation_binding_verified": cap_regime == "BUDGET40_40USD",
        }
    )
    tpl["budget_caps"]["selected_cap_regime"] = cap_regime
    tpl["budget_caps"]["total_hard_cap_usd"] = 40.0 if cap_regime == "BUDGET40_40USD" else 20.0

    owner_sk = Ed25519PrivateKey.generate()
    owner_pk = owner_sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    aud_sk = Ed25519PrivateKey.generate()
    aud_pk = aud_sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    bundle_sha = sha256_bytes(json.dumps(tpl, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    oa = _sign_payload(
        owner_sk,
        ROUTE2_OWNER_ACTIVATION_DOMAIN_TAG,
        {
            "bound_bundle_sha256": bundle_sha,
            "authorized_stage": authorized_stage,
            "final_50_authorized": final_50_authorized,
        },
        "owner_detached_signature_hex",
    )
    if tamper_owner_sig:
        bad = list(oa["owner_detached_signature_hex"])
        bad[0] = "0" if bad[0] != "0" else "1"
        oa["owner_detached_signature_hex"] = "".join(bad)

    trust_artifacts = {
        "trust_root_anchor": _sign_payload(
            owner_sk,
            ROUTE2_TRUST_ROOT_DOMAIN_TAG,
            {
                "protocol_v1_sha256": PROTOCOL_V1_0_SHA256,
                "annex_v022_sha256": ANNEX_V0_2_2_SHA256,
                "harmonization_id": ROUTE2_HARMONIZATION_ID,
                "auditor_ed25519_pubkey_hex": aud_pk,
            },
            "owner_detached_signature_hex",
        ),
        "auditor_verdict_receipt": _sign_payload(
            aud_sk,
            ROUTE2_AUDITOR_VERDICT_DOMAIN_TAG,
            {"verdict": "PASS", "harmonization_id": ROUTE2_HARMONIZATION_ID},
            "auditor_detached_signature_hex",
        ),
        "owner_activation_receipt": oa,
        "od_ae_05_receipt": _sign_payload(
            owner_sk,
            ROUTE2_OD_AE_05_DOMAIN_TAG,
            {
                "tier_t1_sanitized_v_only": True,
                "raw_canonical_s_upload_forbidden": True,
                "anthropic_29day_non_zdr_batch_retention_accepted": anthropic_retention_ack,
                "mandatory_post_batch_delete": True,
            },
            "owner_detached_signature_hex",
        ),
        "provider_preflight_receipt": _sign_payload(
            owner_sk,
            ROUTE2_PROVIDER_PREFLIGHT_DOMAIN_TAG,
            {
                "max_item_tokens_measured": 78290,
                "count_tokens_verified": True,
                "live_account_rates_verified": True,
                "raw_probe_transcript_sha256": sha256_bytes(b"mock-stage1-probe-transcript"),
                "judge_snapshots": {"judge_A": "gpt-6-luna", "judge_B": "claude-haiku-5-5"},
            },
            "owner_detached_signature_hex",
        ),
        "sv01_resolution_receipt": _sign_payload(
            aud_sk,
            ROUTE2_SV01_EVIDENCE_DOMAIN_TAG,
            _sign_payload(
                owner_sk,
                ROUTE2_SV01_EVIDENCE_DOMAIN_TAG,
                {"resolution_mode": "RATIFIED_FROZEN_RULE_WAIVER_EXCEPTION", "epistemic_label_locked": "AI_PROXY_NOT_HUMAN"},
                "owner_detached_signature_hex",
            ),
            "auditor_detached_signature_hex",
        ),
    }
    return tpl, trust_artifacts, owner_pk, aud_pk


def test_cloud_sv_boundary_blocks_raw_s_raudit_t0_t2_and_pii_and_projects_locally() -> None:
    canon_s = "Hồ Hoàn Kiếm ở Hà Nội [CORROBORATED: wikidata:Q1184365] mở cửa 24 giờ hằng ngày."
    san = sanitize_canonical_to_view(canon_s)
    sanitized_v = san.view_V
    removed = list(san.removed_intervals)
    assert "[CORROBORATED:" not in sanitized_v
    v_to_s_segs = list(san.segments)

    doc_leak_meta = {
        "document_id": "w07-b1b-doc-overture-001",
        "poi_id": "poi-hn-01",
        "source_url": "https://example.org/hoankiem",
        "canonical_text_S": canon_s,
        "sanitized_text_V": sanitized_v,
        "removed_r_audit": removed,
    }
    nonce = "0123456789abcdef0123456789abcdef"

    # (a) Valid cloud payload from sanitized V contains ZERO S/R_AUDIT/IDs
    wire = build_sanitized_v_cloud_request_payload(
        packet_item_uuid="pkt-001",
        query_text="Hồ Hoàn Kiếm mở cửa mấy giờ?",
        sanitized_text_V=sanitized_v,
        run_nonce=nonce,
        doc_record_for_leak_check=doc_leak_meta,
    )
    assert wire["boundary_verified"] is True
    assert "[CORROBORATED:" not in wire["wire_user_prompt"]
    assert "w07-b1b-doc-overture-001" not in wire["wire_user_prompt"]

    # (b) Local S projection verifies exact quote offset strictly in Python without uploading S
    quote = "mở cửa 24 giờ"
    v_idx = wire["safe_doc_v"].index(quote)
    q_meta = make_query_dict(
        query_id="DEV-Q1",
        target_city="Hà Nội",
        target_poi_ids=["poi-hn-01"],
        query_intent_polarity="AFFIRMATIVE_FACT_NEED",
        split="DEV",
    )
    q_meta["query_text"] = "Hồ Hoàn Kiếm mở cửa mấy giờ?"
    local_verdict = project_cloud_quote_locally_to_canonical_s(
        cloud_response={
            "grade": "REL_2",
            "evidence_quote": quote,
            "char_start": v_idx,
            "char_end": v_idx + len(quote),
        },
        safe_doc_v=wire["safe_doc_v"],
        safe_to_v_segments=wire["safe_to_v_segments"],
        doc_sanitized_V=sanitized_v,
        doc_canonical_S=canon_s,
        doc_v_to_s_segments=v_to_s_segs,
        doc_removed_r_audit=removed,
        doc_meta={"city": "Hà Nội", "poi_id": "poi-hn-01"},
        query_meta=q_meta,
    )
    assert local_verdict["state"] == "REL_2"

    # (c) Span straddling excised R_AUDIT gap fails locally
    straddle = "Hà Nội  mở cửa"
    s_idx = wire["safe_doc_v"].index(straddle)
    bad_straddle = project_cloud_quote_locally_to_canonical_s(
        cloud_response={"grade": "REL_2", "evidence_quote": straddle, "char_start": s_idx, "char_end": s_idx + len(straddle)},
        safe_doc_v=wire["safe_doc_v"],
        safe_to_v_segments=wire["safe_to_v_segments"],
        doc_sanitized_V=sanitized_v,
        doc_canonical_S=canon_s,
        doc_v_to_s_segments=v_to_s_segs,
        doc_removed_r_audit=removed,
        doc_meta={"city": "Hà Nội", "poi_id": "poi-hn-01"},
        query_meta=q_meta,
    )
    assert bad_straddle["state"] == "ERROR"
    assert bad_straddle["error_code"] == "SPAN_STRADDLES_EXCISED_R_AUDIT_TAG"

    # (d) Passing raw S, R_AUDIT, document_id, T2 commercial URL, or email PII to outbound firewall MUST raise PermissionError
    with pytest.raises(PermissionError, match="CLOUD_DATA_BOUNDARY_UNSANITIZED_MARKERS_IN_V_INPUT"):
        build_sanitized_v_cloud_request_payload(
            packet_item_uuid="pkt-001",
            query_text="Hồ Hoàn Kiếm mở cửa mấy giờ?",
            sanitized_text_V=canon_s,
            run_nonce=nonce,
            doc_record_for_leak_check=doc_leak_meta,
        )
    for bad_obj, pattern in (
        ({"document_id": "d1", "text": "hello"}, "FORBIDDEN_METADATA_KEYS"),
        ({"wire": "Check https://www.tripadvisor.com/foo"}, "FORBIDDEN_MARKER"),
        ({"wire": "Contact user@example.org for details"}, "PII_EMAIL_DETECTED"),
    ):
        with pytest.raises(PermissionError, match=pattern):
            assert_cloud_payload_v_boundary(bad_obj, doc_record_for_leak_check=doc_leak_meta)


def test_cryptographic_receipts_block_tampered_sigs_unaccepted_retention_and_stage_escalation() -> None:
    # Corrupted signature blocked
    b_bad_sig, tr_bad_sig, opk, apk = _build_signed_stage1_bundle_and_trust(tamper_owner_sig=True)
    res_bad = validate_route2_authorization_bundle(
        b_bad_sig,
        trust_artifacts=tr_bad_sig,
        _test_only_trusted_owner_pubkey_hex=opk,
        _test_only_trusted_auditor_pubkey_hex=apk,
    )
    assert res_bad["live_execution_authorized"] is False
    assert any("ROUTE2_ED25519_SIGNATURE_VERIFICATION_FAILED" in b for b in res_bad["blockers"])

    # Missing Anthropic 29-day retention ack blocked
    b_no_ret, tr_no_ret, opk2, apk2 = _build_signed_stage1_bundle_and_trust(anthropic_retention_ack=False)
    res_no_ret = validate_route2_authorization_bundle(
        b_no_ret,
        trust_artifacts=tr_no_ret,
        _test_only_trusted_owner_pubkey_hex=opk2,
        _test_only_trusted_auditor_pubkey_hex=apk2,
    )
    assert res_no_ret["live_execution_authorized"] is False
    assert any("OD_AE_05_INCOMPLETE_RETENTION_OR_BOUNDARY_COMMITMENT" in b for b in res_no_ret["blockers"])

    # Stage-1 activation claiming final_50_authorized=True blocked
    b_esc, tr_esc, opk3, apk3 = _build_signed_stage1_bundle_and_trust(final_50_authorized=True)
    res_esc = validate_route2_authorization_bundle(
        b_esc,
        trust_artifacts=tr_esc,
        _test_only_trusted_owner_pubkey_hex=opk3,
        _test_only_trusted_auditor_pubkey_hex=apk3,
    )
    assert res_esc["live_execution_authorized"] is False
    assert any("OWNER_ACTIVATION_STAGE1_CANNOT_OPEN_FINAL50" in b for b in res_esc["blockers"])


class _MockBatchTransport:
    """Strictly offline mock/record-replay provider Batch transport (zero real HTTP calls)."""

    is_offline_mock_transport = True

    def __init__(
        self,
        *,
        provider: str,
        snapshot_id: str,
        scripted_batches: list[dict[str, Any]],
        fail_delete_batch: bool = False,
        large_token_count: int | None = None,
        batch_id_prefix: str = "mock-batch",
    ) -> None:
        self.provider = provider
        self.snapshot_id = snapshot_id
        self.scripted_batches = list(scripted_batches)
        self.fail_delete_batch = fail_delete_batch
        self.large_token_count = large_token_count
        self.batch_id_prefix = batch_id_prefix
        self.submitted_wire_items: list[list[dict[str, Any]]] = []
        self.deleted_batches: list[str] = []
        self.deleted_files: list[str] = []

    def count_tokens_mock(self, wire_items: list[dict[str, Any]]) -> dict[str, Any]:
        val = self.large_token_count if self.large_token_count is not None else 1200
        return {"per_item_input_tokens": [val for _ in wire_items]}

    def submit_batch(self, wire_items: list[dict[str, Any]], *, batch_label: str) -> dict[str, Any]:
        # Verify S/V cleanliness inside transport as defense-in-depth assertion
        for w in wire_items:
            assert_cloud_payload_v_boundary(w)
        self.submitted_wire_items.append(copy.deepcopy(wire_items))
        idx = len(self.submitted_wire_items) - 1
        return {
            "batch_id": f"{self.batch_id_prefix}-{self.provider}-{idx + 1}-{batch_label}",
            "input_file_id": f"file-in-{idx + 1}" if self.provider == "openai" else None,
        }

    def fetch_batch_results(self, batch_id: str) -> dict[str, Any]:
        idx = int(batch_id.split("-")[3]) - 1
        batch_spec = self.scripted_batches[idx]
        out = {
            "batch_status": batch_spec.get("batch_status", "COMPLETED"),
            "model_snapshot_id": batch_spec.get("model_snapshot_id", self.snapshot_id),
            "output_file_id": f"file-out-{idx + 1}" if self.provider == "openai" else None,
            "items": batch_spec["items"],
        }
        if "batch_billing_usage" in batch_spec:
            out["batch_billing_usage"] = batch_spec["batch_billing_usage"]
        return out

    def delete_batch(self, batch_id: str) -> dict[str, Any]:
        self.deleted_batches.append(batch_id)
        return {"batch_id": batch_id, "deleted": not self.fail_delete_batch}

    def delete_file(self, file_id: str) -> dict[str, Any]:
        self.deleted_files.append(file_id)
        return {"file_id": file_id, "deleted": True}


def _make_canary_items(n_items: int = 8, *, split: str = "DEV", qid_prefix: str = "DEV-Q") -> list[dict[str, Any]]:
    canon_s = "Hồ Hoàn Kiếm [CORROBORATED: wikidata:Q1184365] mở cửa 24 giờ hằng ngày."
    san = sanitize_canonical_to_view(canon_s)
    san_v = san.view_V
    v_to_s = list(san.segments)
    rem_spans = list(san.removed_intervals)
    items = []
    for i in range(n_items):
        qidx = (i % 5) + 1
        items.append(
            {
                "packet_item_uuid": f"uuid-{i:04d}",
                "prompt_order": "PROMPT_ORDER_CANONICAL",
                "run_nonce": f"{i:032x}",
                "sanitized_text_V": san_v,
                "doc_canonical_S": canon_s,
                "doc_v_to_s_segments": v_to_s,
                "doc_removed_r_audit": rem_spans,
                "doc_meta": {"city": "Hà Nội", "poi_id": "poi-hn-01"},
                "doc_record_for_leak_check": {
                    "document_id": f"w07-b1b-doc-test-{i}",
                    "poi_id": "poi-hn-01",
                    "canonical_text_S": canon_s,
                    "sanitized_text_V": san_v,
                    "removed_r_audit": [(13, 47)],
                },
                "query_meta": {
                    **make_query_dict(
                        query_id=f"{qid_prefix}{qidx}",
                        target_city="Hà Nội",
                        target_poi_ids=["poi-hn-01"],
                        query_intent_polarity="AFFIRMATIVE_FACT_NEED",
                        split=split,
                    ),
                    "query_text": "Hồ Hoàn Kiếm mở cửa mấy giờ?",
                },
            }
        )
    return items


def test_mock_canary_runner_happy_path_retries_metering_resume_and_cleanup(tmp_path: Path) -> None:
    bundle, trust, opk, apk = _build_signed_stage1_bundle_and_trust()
    items = _make_canary_items(8)
    quote = "mở cửa 24 giờ"
    q_start = items[0]["sanitized_text_V"].index(quote)
    ok_resp = {"grade": "REL_2", "evidence_quote": quote, "char_start": q_start, "char_end": q_start + len(quote)}

    # Batch 1: 1/8 item has schema error (12.5% <= 15%), triggers single retry batch for uuid-0000 only
    batch1_items = [
        {
            "custom_id": f"uuid-{i:04d}::PROMPT_ORDER_CANONICAL",
            "model_snapshot_id": "gpt-6-luna",
            "usage": {"input_tokens": 500, "output_tokens": 100},
            "parsed_response": {"grade": "REL_2", "evidence_quote": "NON_EXISTENT", "char_start": 0, "char_end": 12}
            if i == 0
            else ok_resp,
        }
        for i in range(8)
    ]
    batch2_items = [
        {
            "custom_id": "uuid-0000::PROMPT_ORDER_CANONICAL",
            "model_snapshot_id": "gpt-6-luna",
            "usage": {"input_tokens": 500, "output_tokens": 100},
            "parsed_response": ok_resp,
        }
    ]
    transport_oa = _MockBatchTransport(
        provider="openai", snapshot_id="gpt-6-luna", scripted_batches=[{"items": batch1_items}, {"items": batch2_items}]
    )
    raw_log = tmp_path / "oa_raw.jsonl"
    ledger_p = tmp_path / "oa_spend_ledger.json"
    rate = ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 0.05, 0.25)

    res1 = run_stage1_dev_canary_mock_batch(
        bundle=bundle,
        trust_artifacts=trust,
        canary_items=items,
        system_prompt="Grade strictly in S-4.",
        response_schema=PROMPT_V1_1_SCHEMA,
        rate_profile=rate,
        transport=transport_oa,
        raw_log_jsonl_path=raw_log,
        spend_ledger_path=ledger_p,
        _test_only_trusted_owner_pubkey_hex=opk,
        _test_only_trusted_auditor_pubkey_hex=apk,
    )
    assert res1["live_network_calls_executed"] == 0
    assert res1["settled_count"] == 8
    assert res1["skipped_resumed_count"] == 0
    assert len(res1["dispatched_batches"]) == 2
    assert len(transport_oa.deleted_batches) == 2
    assert len(transport_oa.deleted_files) == 4  # 2 input + 2 output files cleaned
    # Verify all settled entries projected cleanly to canonical S == REL_2 (not just logged as errors!)
    settled_rows = [json.loads(ln) for ln in raw_log.read_text(encoding="utf-8").splitlines() if json.loads(ln).get("final_for_item")]
    assert len(settled_rows) == 8
    assert all(r["local_validation"]["state"] == "REL_2" for r in settled_rows)
    # Actual usage cost for 9 total item responses @ (500*0.05 + 100*0.25)/1e6 = 9 * 0.00005 = 0.00045
    assert abs(res1["total_spent_usd"] - 0.00045) < 1e-8
    assert all("temperature" not in wi["body"] and wi["body"]["reasoning"] == {"effort": "low"} for wi in transport_oa.submitted_wire_items[0])

    # Idempotent resume: re-running same log/ledger dispatches ZERO new batches & adds $0.00
    res_resume = run_stage1_dev_canary_mock_batch(
        bundle=bundle,
        trust_artifacts=trust,
        canary_items=items,
        system_prompt="Grade strictly in S-4.",
        response_schema=PROMPT_V1_1_SCHEMA,
        rate_profile=rate,
        transport=transport_oa,
        raw_log_jsonl_path=raw_log,
        spend_ledger_path=ledger_p,
        _test_only_trusted_owner_pubkey_hex=opk,
        _test_only_trusted_auditor_pubkey_hex=apk,
    )
    assert res_resume["skipped_resumed_count"] == 8
    assert res_resume["dispatched_batches"] == []
    assert abs(res_resume["total_spent_usd"] - 0.00045) < 1e-8

    # Also test Anthropic wire path cleanly
    ant_items = [
        {
            "custom_id": f"uuid-{i:04d}::PROMPT_ORDER_CANONICAL",
            "model_snapshot_id": "claude-haiku-5-5",
            "usage": {"input_tokens": 400, "output_tokens": 80},
            "parsed_response": ok_resp,
        }
        for i in range(4)
    ]
    transport_ant = _MockBatchTransport(
        provider="anthropic", snapshot_id="claude-haiku-5-5", scripted_batches=[{"items": ant_items}]
    )
    res_ant = run_stage1_dev_canary_mock_batch(
        bundle=bundle,
        trust_artifacts=trust,
        canary_items=items[:4],
        system_prompt="Grade strictly in S-4.",
        response_schema=PROMPT_V1_1_SCHEMA,
        rate_profile=ProviderRateProfile("anthropic", "claude-haiku-5-5", "claude-haiku-5-5", 0.05, 0.25),
        transport=transport_ant,
        raw_log_jsonl_path=tmp_path / "ant_raw.jsonl",
        spend_ledger_path=tmp_path / "ant_ledger.json",
        _test_only_trusted_owner_pubkey_hex=opk,
        _test_only_trusted_auditor_pubkey_hex=apk,
    )
    assert res_ant["od_ae_05_retention_accepted_by_receipt"] is True
    assert transport_ant.submitted_wire_items[0][0]["params"]["output_config"]["effort"] == "low"
    assert "temperature" not in transport_ant.submitted_wire_items[0][0]["params"]


def test_mock_canary_runner_fail_closed_limits_snapshot_cap_retry_final_leak_and_cleanup(tmp_path: Path) -> None:
    bundle, trust, opk, apk = _build_signed_stage1_bundle_and_trust()
    rate = ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 0.05, 0.25)
    ok_items = _make_canary_items(4)

    # 1. Non-mock or live_network flag blocked
    class _FakeLive:
        is_offline_mock_transport = False
        provider = "openai"

    with pytest.raises(PermissionError, match="LIVE_API_FORBIDDEN"):
        run_stage1_dev_canary_mock_batch(
            bundle=bundle,
            trust_artifacts=trust,
            canary_items=ok_items,
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            rate_profile=rate,
            transport=_MockBatchTransport(provider="openai", snapshot_id="gpt-6-luna", scripted_batches=[]),
            raw_log_jsonl_path=tmp_path / "1.jsonl",
            spend_ledger_path=tmp_path / "1.json",
            allow_live_network=True,
            _test_only_trusted_owner_pubkey_hex=opk,
            _test_only_trusted_auditor_pubkey_hex=apk,
        )
    with pytest.raises(PermissionError, match="NON_MOCK_TRANSPORT_REJECTED"):
        run_stage1_dev_canary_mock_batch(
            bundle=bundle,
            trust_artifacts=trust,
            canary_items=ok_items,
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            rate_profile=rate,
            transport=_FakeLive(),  # type: ignore[arg-type]
            raw_log_jsonl_path=tmp_path / "2.jsonl",
            spend_ledger_path=tmp_path / "2.json",
            _test_only_trusted_owner_pubkey_hex=opk,
            _test_only_trusted_auditor_pubkey_hex=apk,
        )

    # 2. FINAL split/ID contamination blocked
    with pytest.raises(PermissionError, match="FINAL50_CONTAMINATION_BLOCKED"):
        run_stage1_dev_canary_mock_batch(
            bundle=bundle,
            trust_artifacts=trust,
            canary_items=_make_canary_items(2, split="FINAL", qid_prefix="FIN-Q"),
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            rate_profile=rate,
            transport=_MockBatchTransport(provider="openai", snapshot_id="gpt-6-luna", scripted_batches=[]),
            raw_log_jsonl_path=tmp_path / "3.jsonl",
            spend_ledger_path=tmp_path / "3.json",
            _test_only_trusted_owner_pubkey_hex=opk,
            _test_only_trusted_auditor_pubkey_hex=apk,
        )

    # 3. Model snapshot drift aborts cleanly and still runs cleanup in finally
    t_drift = _MockBatchTransport(
        provider="openai",
        snapshot_id="gpt-6-luna-2026-99-99",
        scripted_batches=[{"model_snapshot_id": "gpt-6-luna-drifted", "items": []}],
    )
    with pytest.raises(PermissionError, match="MODEL_SNAPSHOT_DRIFT_ABORT"):
        run_stage1_dev_canary_mock_batch(
            bundle=bundle,
            trust_artifacts=trust,
            canary_items=ok_items[:2],
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            rate_profile=rate,
            transport=t_drift,
            raw_log_jsonl_path=tmp_path / "4.jsonl",
            spend_ledger_path=tmp_path / "4.json",
            _test_only_trusted_owner_pubkey_hex=opk,
            _test_only_trusted_auditor_pubkey_hex=apk,
        )
    assert len(t_drift.deleted_batches) == 1

    # 4. Retry fraction > 15% aborts cleanly
    bad_batch = [
        {
            "custom_id": f"uuid-{i:04d}::PROMPT_ORDER_CANONICAL",
            "model_snapshot_id": "gpt-6-luna",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "parsed_response": {"grade": "REL_2", "evidence_quote": "BAD", "char_start": 0, "char_end": 3},
        }
        for i in range(4)
    ]
    with pytest.raises(PermissionError, match="BATCH_RETRY_FRACTION_EXCEEDED"):
        run_stage1_dev_canary_mock_batch(
            bundle=bundle,
            trust_artifacts=trust,
            canary_items=ok_items,
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            rate_profile=rate,
            transport=_MockBatchTransport(provider="openai", snapshot_id="gpt-6-luna", scripted_batches=[{"items": bad_batch}]),
            raw_log_jsonl_path=tmp_path / "5.jsonl",
            spend_ledger_path=tmp_path / "5.json",
            _test_only_trusted_owner_pubkey_hex=opk,
            _test_only_trusted_auditor_pubkey_hex=apk,
        )

    # 5. Pre-batch cap > $2.00 aborts cleanly
    high_rate = ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 50.0, 50.0)
    with pytest.raises(PermissionError, match="DEV_BUDGET_PRE_BATCH_CAP_EXCEEDED"):
        run_stage1_dev_canary_mock_batch(
            bundle=bundle,
            trust_artifacts=trust,
            canary_items=ok_items,
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            rate_profile=high_rate,
            transport=_MockBatchTransport(provider="openai", snapshot_id="gpt-6-luna", scripted_batches=[], large_token_count=90000),
            raw_log_jsonl_path=tmp_path / "6.jsonl",
            spend_ledger_path=tmp_path / "6.json",
            _test_only_trusted_owner_pubkey_hex=opk,
            _test_only_trusted_auditor_pubkey_hex=apk,
        )

    # 6. Cleanup incomplete fails closed
    clean_batch = [
        {
            "custom_id": f"uuid-{i:04d}::PROMPT_ORDER_CANONICAL",
            "model_snapshot_id": "gpt-6-luna",
            "usage": {"input_tokens": 100, "output_tokens": 10},
            "parsed_response": {"grade": "REL_0", "evidence_quote": None, "char_start": None, "char_end": None},
        }
        for i in range(2)
    ]
    with pytest.raises(RuntimeError, match="BATCH_CLEANUP_INCOMPLETE"):
        run_stage1_dev_canary_mock_batch(
            bundle=bundle,
            trust_artifacts=trust,
            canary_items=ok_items[:2],
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            rate_profile=rate,
            transport=_MockBatchTransport(
                provider="openai", snapshot_id="gpt-6-luna", scripted_batches=[{"items": clean_batch}], fail_delete_batch=True
            ),
            raw_log_jsonl_path=tmp_path / "7.jsonl",
            spend_ledger_path=tmp_path / "7.json",
            _test_only_trusted_owner_pubkey_hex=opk,
            _test_only_trusted_auditor_pubkey_hex=apk,
        )
    # Verify cleanup failure is durably recorded inside spend ledger
    cleanup_ledger = json.loads((tmp_path / "7.json").read_text(encoding="utf-8"))
    assert len(cleanup_ledger["cleanup_failures"]) == 1
    assert cleanup_ledger["cleanup_failures"][0]["stage"] == "delete_batch"
    assert abs(cleanup_ledger["total_spent_usd"] - 0.000015) < 1e-9


def test_partial_batch_cost_committed_before_retry_cap_or_failed_cancelled_exceptions(tmp_path: Path) -> None:
    bundle, trust, opk, apk = _build_signed_stage1_bundle_and_trust()
    rate = ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 1.0, 2.0)
    items = _make_canary_items(4)
    quote = "mở cửa 24 giờ"
    q_start = items[0]["sanitized_text_V"].index(quote)
    ok_resp = {"grade": "REL_2", "evidence_quote": quote, "char_start": q_start, "char_end": q_start + len(quote)}

    # Item 0..1 fail quote -> retry_fraction (2/4 = 50% > 15%) aborts cleanly AFTER full batch usage is committed!
    bad_retry_items = [
        {
            "custom_id": f"uuid-{i:04d}::PROMPT_ORDER_CANONICAL",
            "model_snapshot_id": "gpt-6-luna",
            "usage": {"input_tokens": 1000, "output_tokens": 500},  # each item = (1000*1 + 500*2)/1e6 = $0.002 -> 4*$0.002 = $0.008
            "parsed_response": {"grade": "REL_2", "evidence_quote": "WRONG", "char_start": 0, "char_end": 5}
            if i == 0
            else ok_resp,
        }
        for i in range(4)
    ]
    raw_log = tmp_path / "retry_partial.jsonl"
    ledger_p = tmp_path / "retry_partial_ledger.json"
    t1 = _MockBatchTransport(provider="openai", snapshot_id="gpt-6-luna", scripted_batches=[{"items": bad_retry_items}])
    with pytest.raises(PermissionError, match="BATCH_RETRY_FRACTION_EXCEEDED"):
        run_stage1_dev_canary_mock_batch(
            bundle=bundle,
            trust_artifacts=trust,
            canary_items=items,
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            rate_profile=rate,
            transport=t1,
            raw_log_jsonl_path=raw_log,
            spend_ledger_path=ledger_p,
            _test_only_trusted_owner_pubkey_hex=opk,
            _test_only_trusted_auditor_pubkey_hex=apk,
        )
    ledger_after_exc = json.loads(ledger_p.read_text(encoding="utf-8"))
    # Even though exception raised mid-loop, ALL 4 returned billable items ($0.008) MUST be committed!
    assert abs(ledger_after_exc["total_spent_usd"] - 0.008) < 1e-9
    assert len(t1.deleted_batches) == 1

    # Restart with corrected items: previously billed $0.008 MUST NOT reset or underestimate!
    clean_items = [
        {
            "custom_id": f"uuid-{i:04d}::PROMPT_ORDER_CANONICAL",
            "model_snapshot_id": "gpt-6-luna",
            "usage": {"input_tokens": 1000, "output_tokens": 500},
            "parsed_response": ok_resp,
        }
        for i in range(4)
    ]
    t2 = _MockBatchTransport(
        provider="openai",
        snapshot_id="gpt-6-luna",
        scripted_batches=[{"items": clean_items}],
        batch_id_prefix="mock-restart",
    )
    res_resume = run_stage1_dev_canary_mock_batch(
        bundle=bundle,
        trust_artifacts=trust,
        canary_items=items,
        system_prompt="S",
        response_schema=PROMPT_V1_1_SCHEMA,
        rate_profile=rate,
        transport=t2,
        raw_log_jsonl_path=raw_log,
        spend_ledger_path=ledger_p,
        _test_only_trusted_owner_pubkey_hex=opk,
        _test_only_trusted_auditor_pubkey_hex=apk,
    )
    assert abs(res_resume["total_spent_usd"] - 0.016) < 1e-9

    # Cancelled/Failed batch with partial items + top-level batch_billing_usage still bills exact partial cost & cleans up
    partial_cancel_batch = {
        "batch_status": "CANCELLED",
        "items": bad_retry_items[:2],  # 2 items * $0.002 = $0.004
        "batch_billing_usage": {"input_tokens": 500, "output_tokens": 250},  # + $0.001 => $0.005
    }
    ledger_cancel_p = tmp_path / "cancel_ledger.json"
    t_cancel = _MockBatchTransport(
        provider="openai", snapshot_id="gpt-6-luna", scripted_batches=[partial_cancel_batch]
    )
    with pytest.raises(RuntimeError, match="BATCH_CANCELLED"):
        run_stage1_dev_canary_mock_batch(
            bundle=bundle,
            trust_artifacts=trust,
            canary_items=items,
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            rate_profile=rate,
            transport=t_cancel,
            raw_log_jsonl_path=tmp_path / "cancel.jsonl",
            spend_ledger_path=ledger_cancel_p,
            _test_only_trusted_owner_pubkey_hex=opk,
            _test_only_trusted_auditor_pubkey_hex=apk,
        )
    cancel_ledger = json.loads(ledger_cancel_p.read_text(encoding="utf-8"))
    assert abs(cancel_ledger["total_spent_usd"] - 0.005) < 1e-9
    assert cancel_ledger["failed_batches"] == 1
    assert len(t_cancel.deleted_batches) == 1


def test_crash_injection_recovery_and_strict_usage_rate_validation(tmp_path: Path) -> None:
    bundle, trust, opk, apk = _build_signed_stage1_bundle_and_trust()
    rate = ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 1.0, 2.0)
    items = _make_canary_items(4)
    quote = "mở cửa 24 giờ"
    q_start = items[0]["sanitized_text_V"].index(quote)
    ok_resp = {"grade": "REL_2", "evidence_quote": quote, "char_start": q_start, "char_end": q_start + len(quote)}
    full_resp_items = [
        {
            "custom_id": f"uuid-{i:04d}::PROMPT_ORDER_CANONICAL",
            "model_snapshot_id": "gpt-6-luna",
            "usage": {"input_tokens": 1000, "output_tokens": 500},
            "parsed_response": ok_resp,
        }
        for i in range(4)
    ]

    # (a) Hard crash right after submit -> recovery fetches batch-1 once, bills once ($0.008), cleans up dangling batch, zero duplicate submit!
    t_crash1 = _MockBatchTransport(
        provider="openai", snapshot_id="gpt-6-luna", scripted_batches=[{"items": full_resp_items}]
    )
    raw1 = tmp_path / "crash1.jsonl"
    led1 = tmp_path / "crash1_ledger.json"
    with pytest.raises(RuntimeError, match="SIMULATED_HARD_CRASH_AFTER_SUBMIT"):
        run_stage1_dev_canary_mock_batch(
            bundle=bundle,
            trust_artifacts=trust,
            canary_items=items,
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            rate_profile=rate,
            transport=t_crash1,
            raw_log_jsonl_path=raw1,
            spend_ledger_path=led1,
            _test_only_trusted_owner_pubkey_hex=opk,
            _test_only_trusted_auditor_pubkey_hex=apk,
            _test_crash_hook="hard_crash_after_submit",
        )
    assert len(t_crash1.submitted_wire_items) == 1
    assert len(t_crash1.deleted_batches) == 0  # dangling batch on server!

    res_rec1 = run_stage1_dev_canary_mock_batch(
        bundle=bundle,
        trust_artifacts=trust,
        canary_items=items,
        system_prompt="S",
        response_schema=PROMPT_V1_1_SCHEMA,
        rate_profile=rate,
        transport=t_crash1,
        raw_log_jsonl_path=raw1,
        spend_ledger_path=led1,
        _test_only_trusted_owner_pubkey_hex=opk,
        _test_only_trusted_auditor_pubkey_hex=apk,
    )
    assert len(t_crash1.submitted_wire_items) == 1  # NO second batch submitted!
    assert len(t_crash1.deleted_batches) == 1  # Dangling batch cleaned up on recovery!
    assert res_rec1["settled_count"] == 4
    assert abs(res_rec1["total_spent_usd"] - 0.008) < 1e-9

    # (b) Mid-JSONL crash after first item -> item 0 settled, batch 1 cost ($0.008) preserved; restart only sends remaining 3 items ($0.006 => $0.014 total)
    remaining_3 = full_resp_items[1:]
    t_crash2 = _MockBatchTransport(
        provider="openai",
        snapshot_id="gpt-6-luna",
        scripted_batches=[{"items": full_resp_items}, {"items": remaining_3}],
    )
    raw2 = tmp_path / "crash2.jsonl"
    led2 = tmp_path / "crash2_ledger.json"
    with pytest.raises(RuntimeError, match="SIMULATED_CRASH_AFTER_FIRST_ITEM_JSONL"):
        run_stage1_dev_canary_mock_batch(
            bundle=bundle,
            trust_artifacts=trust,
            canary_items=items,
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            rate_profile=rate,
            transport=t_crash2,
            raw_log_jsonl_path=raw2,
            spend_ledger_path=led2,
            _test_only_trusted_owner_pubkey_hex=opk,
            _test_only_trusted_auditor_pubkey_hex=apk,
            _test_crash_hook="after_first_item_jsonl",
        )
    res_rec2 = run_stage1_dev_canary_mock_batch(
        bundle=bundle,
        trust_artifacts=trust,
        canary_items=items,
        system_prompt="S",
        response_schema=PROMPT_V1_1_SCHEMA,
        rate_profile=rate,
        transport=t_crash2,
        raw_log_jsonl_path=raw2,
        spend_ledger_path=led2,
        _test_only_trusted_owner_pubkey_hex=opk,
        _test_only_trusted_auditor_pubkey_hex=apk,
    )
    assert res_rec2["skipped_resumed_count"] == 1
    assert len(t_crash2.submitted_wire_items[1]) == 3
    assert abs(res_rec2["total_spent_usd"] - 0.014) < 1e-9

    # (c) Missing usage / negative / bool / NaN / inf guards (NEVER infer $0.00 from missing usage!)
    for bad_in, bad_out in ((-1.0, 1.0), (float("nan"), 1.0), (float("inf"), 1.0), (True, 1.0)):  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="INVALID_RATE_PROFILE"):
            ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", bad_in, bad_out)

    for bad_usage in (None, {}, {"input_tokens": 10}, {"input_tokens": -5, "output_tokens": 1}, {"input_tokens": True, "output_tokens": 1}):
        bad_resp = [
            {"custom_id": f"uuid-{i:04d}::PROMPT_ORDER_CANONICAL", "model_snapshot_id": "gpt-6-luna", "usage": bad_usage, "parsed_response": ok_resp}
            for i in range(2)
        ]
        with pytest.raises(ValueError, match="MISSING_|INVALID_TOKEN_COUNT"):
            run_stage1_dev_canary_mock_batch(
                bundle=bundle,
                trust_artifacts=trust,
                canary_items=items[:2],
                system_prompt="S",
                response_schema=PROMPT_V1_1_SCHEMA,
                rate_profile=rate,
                transport=_MockBatchTransport(provider="openai", snapshot_id="gpt-6-luna", scripted_batches=[{"items": bad_resp}]),
                raw_log_jsonl_path=tmp_path / f"badu_{abs(hash(str(bad_usage)))}.jsonl",
                spend_ledger_path=tmp_path / f"badu_{abs(hash(str(bad_usage)))}.json",
                _test_only_trusted_owner_pubkey_hex=opk,
                _test_only_trusted_auditor_pubkey_hex=apk,
            )


def test_live_entrypoint_external_trust_root_activation_ceremony_and_preflight_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ast
    import inspect
    import sys

    scripts_dir = str(Path(__file__).resolve().parents[1] / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
    from provision_route2_activation_ceremony import materialize_unsigned_activation_pack, sign_ceremony_with_pem_keys
    from w07_g4_scorer import route2_live_preflight
    from w07_g4_scorer.route2_aiproxy import (
        ROUTE2_TRUST_ROOT_DOMAIN_TAG,
        load_external_route2_trust_root,
        validate_route2_live_activation_entrypoint,
    )
    from w07_g4_scorer.route2_live_preflight import (
        authorize_stage1_live_canary_gate,
        run_authorized_provider_preflight_probes,
        verify_live_account_preflight_prerequisites,
    )

    # 0. P0-B static audit check: zero _test_only_trusted_* symbol anywhere inside production live entrypoints
    for fn_src in (
        inspect.getsource(load_external_route2_trust_root),
        inspect.getsource(validate_route2_live_activation_entrypoint),
        Path(route2_live_preflight.__file__).read_text(encoding="utf-8"),
    ):
        assert "_test_only_trusted" not in fn_src

    pack_dir = tmp_path / "pack"
    ext_tr = tmp_path / "external_trust_root"
    ext_tr.mkdir()
    index = materialize_unsigned_activation_pack(pack_dir)
    assert index["live_execution_authorized"] is False
    assert index["forged_signatures_count"] == 0
    assert index["blockers_count"] == 7

    # 1. Live entrypoint rejects _test_only_trusted_* kwargs AND rejects unpinned self-signed root (P0-B)
    with pytest.raises(TypeError):
        validate_route2_live_activation_entrypoint(  # type: ignore[call-arg]
            activation_pack_dir=pack_dir,
            external_trust_root_dir=ext_tr,
            _test_only_trusted_owner_pubkey_hex="a" * 64,
        )

    with pytest.raises(PermissionError, match="HOLD_OUT_OF_BAND_TRUST_ROOT_PIN_REQUIRED"):
        validate_route2_live_activation_entrypoint(activation_pack_dir=pack_dir, external_trust_root_dir=ext_tr)

    repo_bad_tr = Path(__file__).resolve().parents[1] / "docs"
    with pytest.raises(PermissionError, match="EXTERNAL_TRUST_ROOT_CANNOT_BE_INSIDE_REPO"):
        validate_route2_live_activation_entrypoint(
            activation_pack_dir=pack_dir,
            external_trust_root_dir=repo_bad_tr,
            out_of_band_manifest_sha256="b" * 64,
        )

    # 2. Provision genuine isolated Owner & Auditor PEM keys outside repo + derive independent out-of-band SHA-256 pins
    owner_sk = Ed25519PrivateKey.generate()
    aud_sk = Ed25519PrivateKey.generate()
    owner_pem = tmp_path / "owner_priv.pem"
    aud_pem = tmp_path / "auditor_priv.pem"
    owner_pem.write_bytes(owner_sk.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    aud_pem.write_bytes(aud_sk.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    owner_oob_sha = sha256_bytes(owner_sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    aud_oob_sha = sha256_bytes(aud_sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))

    gvhd_pdf_stub = tmp_path / "gvhd_signed_confirmation.txt"
    gvhd_pdf_stub.write_text("Supervisor approved OD-G15-05-AIPROXY on 2026-11-23.", encoding="utf-8")

    # 3. Attacker creates a self-signed external trust root in another folder -> REJECTED by Owner/Auditor out-of-band pins!
    atk_tr = tmp_path / "attacker_trust_root"
    atk_tr.mkdir()
    atk_sk = Ed25519PrivateKey.generate()
    atk_aud_sk = Ed25519PrivateKey.generate()
    atk_anchor = _sign_payload(
        atk_sk,
        ROUTE2_TRUST_ROOT_DOMAIN_TAG,
        {
            "protocol_v1_sha256": PROTOCOL_V1_0_SHA256,
            "annex_v022_sha256": ANNEX_V0_2_2_SHA256,
            "harmonization_id": ROUTE2_HARMONIZATION_ID,
            "auditor_ed25519_pubkey_hex": atk_aud_sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
        },
        "owner_detached_signature_hex",
    )
    (atk_tr / "trust_root_manifest.json").write_text(
        json.dumps(
            {
                "owner_ed25519_pubkey_hex": atk_sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
                "auditor_ed25519_pubkey_hex": atk_aud_sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
                "trust_root_anchor": atk_anchor,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PermissionError, match="OUT_OF_BAND_OWNER_PUBKEY_PIN_MISMATCH"):
        load_external_route2_trust_root(
            atk_tr,
            out_of_band_owner_pubkey_sha256=owner_oob_sha,
            out_of_band_auditor_pubkey_sha256=aud_oob_sha,
        )

    # Identical Owner & Auditor pubkeys ALSO rejected!
    same_tr = tmp_path / "same_key_tr"
    same_tr.mkdir()
    same_pk = owner_sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    (same_tr / "trust_root_manifest.json").write_text(
        json.dumps(
            {
                "owner_ed25519_pubkey_hex": same_pk,
                "auditor_ed25519_pubkey_hex": same_pk,
                "trust_root_anchor": _sign_payload(
                    owner_sk,
                    ROUTE2_TRUST_ROOT_DOMAIN_TAG,
                    {
                        "protocol_v1_sha256": PROTOCOL_V1_0_SHA256,
                        "annex_v022_sha256": ANNEX_V0_2_2_SHA256,
                        "harmonization_id": ROUTE2_HARMONIZATION_ID,
                        "auditor_ed25519_pubkey_hex": same_pk,
                    },
                    "owner_detached_signature_hex",
                ),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PermissionError, match="OWNER_AND_AUDITOR_KEYS_MUST_BE_DISTINCT"):
        load_external_route2_trust_root(
            same_tr,
            out_of_band_owner_pubkey_sha256=owner_oob_sha,
            out_of_band_auditor_pubkey_sha256=owner_oob_sha,
        )

    # 4. P0-A Phase 1: Sign ONLY PRE_PREFLIGHT_PROBE_ONLY (NO provider_preflight_receipt yet!) -> breaks circular deadlock!
    pre_unlocked = sign_ceremony_with_pem_keys(
        owner_private_pem_path=owner_pem,
        auditor_private_pem_path=aud_pem,
        trust_root_dir=ext_tr,
        pack_dir=pack_dir,
        gate_phase="PRE_PREFLIGHT_PROBE_ONLY",
        sv01_written_artifact_path=gvhd_pdf_stub,
        sv01_supervisor_identity="TS. GVHD Test",
    )
    assert pre_unlocked["preflight_probes_authorized"] is True
    assert pre_unlocked["batch_generation_authorized"] is False
    assert pre_unlocked["live_execution_authorized"] is False

    # PRE_PREFLIGHT_PROBE_ONLY scope MUST NEVER open STAGE1_LIVE batch generation (missing preflight receipt OR wrong stage)!
    with pytest.raises(PermissionError, match="MISSING_SIGNED_RECEIPT_FILE"):
        authorize_stage1_live_canary_gate(
            activation_pack_dir=pack_dir,
            external_trust_root_dir=ext_tr,
            out_of_band_owner_pubkey_sha256=owner_oob_sha,
            out_of_band_auditor_pubkey_sha256=aud_oob_sha,
        )
    # Even if an attacker plants a valid signed provider_preflight_receipt next to a STAGE1_PREFLIGHT_PROBE_ONLY Owner receipt,
    # STAGE1_LIVE still MUST reject because PREFLIGHT scope cannot open live generation!
    planted_pf = _sign_payload(
        owner_sk,
        ROUTE2_PROVIDER_PREFLIGHT_DOMAIN_TAG,
        {
            "max_item_tokens_measured": 2400,
            "count_tokens_verified": True,
            "live_account_rates_verified": True,
            "raw_probe_transcript_sha256": sha256_bytes(b"planted"),
            "judge_snapshots": {"judge_A": "gpt-6-luna", "judge_B": "claude-haiku-5-5"},
        },
        "owner_detached_signature_hex",
    )
    pf_tmp_path = pack_dir / "receipts" / "provider_preflight_receipt.json"
    pf_tmp_path.write_text(json.dumps(planted_pf), encoding="utf-8")
    with pytest.raises(PermissionError, match="ROUTE2_LIVE_EXECUTION_BLOCKED"):
        authorize_stage1_live_canary_gate(
            activation_pack_dir=pack_dir,
            external_trust_root_dir=ext_tr,
            out_of_band_owner_pubkey_sha256=owner_oob_sha,
            out_of_band_auditor_pubkey_sha256=aud_oob_sha,
        )
    pf_tmp_path.unlink()

    # 5. Live preflight MUST stay blocked without allow_live_network=True or API keys
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(PermissionError, match="HOLD_LIVE_PREFLIGHT_REQUIRES_EXPLICIT_ALLOW_LIVE_NETWORK"):
        verify_live_account_preflight_prerequisites(
            activation_pack_dir=pack_dir,
            external_trust_root_dir=ext_tr,
            out_of_band_owner_pubkey_sha256=owner_oob_sha,
            out_of_band_auditor_pubkey_sha256=aud_oob_sha,
            allow_live_network=False,
        )
    with pytest.raises(PermissionError, match="HOLD_PROVIDER_API_CREDENTIALS_UNSET"):
        verify_live_account_preflight_prerequisites(
            activation_pack_dir=pack_dir,
            external_trust_root_dir=ext_tr,
            out_of_band_owner_pubkey_sha256=owner_oob_sha,
            out_of_band_auditor_pubkey_sha256=aud_oob_sha,
            allow_live_network=True,
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder-configured")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-placeholder-configured")
    with pytest.raises(PermissionError, match="HOLD_PA1_CAP_EXCEEDS_20_USD"):
        verify_live_account_preflight_prerequisites(
            activation_pack_dir=pack_dir,
            external_trust_root_dir=ext_tr,
            out_of_band_owner_pubkey_sha256=owner_oob_sha,
            out_of_band_auditor_pubkey_sha256=aud_oob_sha,
            allow_live_network=True,
            requested_total_cap_usd=40.0,
        )

    class _MockProbeClient:
        def __init__(self, tok: int = 2400) -> None:
            self.tok = tok

        def probe_model_snapshot(self, *, provider: str, model_id: str) -> dict[str, Any]:
            return {
                "accessible": True,
                "model_snapshot_id": "gpt-6-luna-2026-09-22" if provider == "openai" else "claude-haiku-5-5",
            }

        def probe_input_tokens(self, *, provider: str, wire_request: Any) -> dict[str, Any]:
            assert_cloud_payload_v_boundary(wire_request)
            return {"input_tokens": self.tok}

    class _BadBatchingProbeClient(_MockProbeClient):
        def submit_batch(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # pragma: no cover
            return {}

    canary_rows = _make_canary_items(2)
    with pytest.raises(PermissionError, match="PREFLIGHT_FORBIDS_BILLABLE_BATCH_GENERATION_CLIENT"):
        run_authorized_provider_preflight_probes(
            activation_pack_dir=pack_dir,
            external_trust_root_dir=ext_tr,
            probe_client=_BadBatchingProbeClient(2400),
            rate_profiles=[ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna-2026-09-22", 0.05, 0.25)],
            canary_items=canary_rows,
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            out_of_band_owner_pubkey_sha256=owner_oob_sha,
            out_of_band_auditor_pubkey_sha256=aud_oob_sha,
            allow_live_network=True,
        )

    raw_transcript_path = tmp_path / "raw_probe_transcript.json"
    preflight_ok = run_authorized_provider_preflight_probes(
        activation_pack_dir=pack_dir,
        external_trust_root_dir=ext_tr,
        probe_client=_MockProbeClient(2400),
        rate_profiles=[
            ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna-2026-09-22", 0.05, 0.25),
            ProviderRateProfile("anthropic", "claude-haiku-5-5", "claude-haiku-5-5", 0.05, 0.25),
        ],
        canary_items=canary_rows,
        system_prompt="S",
        response_schema=PROMPT_V1_1_SCHEMA,
        out_of_band_owner_pubkey_sha256=owner_oob_sha,
        out_of_band_auditor_pubkey_sha256=aud_oob_sha,
        raw_probe_transcript_path=raw_transcript_path,
        allow_live_network=True,
    )
    assert preflight_ok["max_item_tokens_measured"] == 2400
    assert preflight_ok["batch_generation_authorized"] is False
    assert preflight_ok["live_account_rates_verified"] is False
    assert preflight_ok["account_pricing_status"] == "UNVERIFIED_CALLER_ESTIMATE_ONLY"
    assert raw_transcript_path.is_file()

    with pytest.raises(PermissionError, match="PREFLIGHT_100K_CLIFF_EXCEEDED"):
        run_authorized_provider_preflight_probes(
            activation_pack_dir=pack_dir,
            external_trust_root_dir=ext_tr,
            probe_client=_MockProbeClient(105000),
            rate_profiles=[ProviderRateProfile("anthropic", "claude-haiku-5-5", "claude-haiku-5-5", 0.05, 0.25)],
            canary_items=canary_rows,
            system_prompt="S",
            response_schema=PROMPT_V1_1_SCHEMA,
            out_of_band_owner_pubkey_sha256=owner_oob_sha,
            out_of_band_auditor_pubkey_sha256=aud_oob_sha,
            allow_live_network=True,
        )

    # 6. P0-A Phase 2: STAGE1_LIVE without timestamped rate evidence MUST remain BLOCKED (Audit §4)!
    with pytest.raises(PermissionError, match="HOLD_LIVE_ACCOUNT_RATES_AND_COUNT_TOKENS_NOT_VERIFIED"):
        sign_ceremony_with_pem_keys(
            owner_private_pem_path=owner_pem,
            auditor_private_pem_path=aud_pem,
            trust_root_dir=ext_tr,
            pack_dir=pack_dir,
            gate_phase="STAGE1_LIVE",
            sv01_written_artifact_path=gvhd_pdf_stub,
            sv01_supervisor_identity="TS. GVHD Test",
            raw_probe_transcript_path=raw_transcript_path,
        )

    rate_ev_path = tmp_path / "provider_rate_evidence.json"
    rate_ev_path.write_text(
        json.dumps(
            {
                "schema_version": "GOMATE_W07_PROVIDER_RATE_EVIDENCE_V1",
                "captured_at_utc": "2026-11-23T12:00:00Z",
                "owner_accepted_rates": True,
                "providers": {
                    "openai": {
                        "model_snapshot_id": "gpt-6-luna-2026-09-22",
                        "source_url": "https://platform.openai.com/docs/pricing",
                        "evidence_artifact_sha256": sha256_bytes(b"openai-pricing-capture"),
                        "batch_input_usd_per_1m": 0.05,
                        "batch_output_usd_per_1m": 0.25,
                    },
                    "anthropic": {
                        "model_snapshot_id": "claude-haiku-5-5",
                        "source_url": "https://docs.anthropic.com/en/docs/about-claude/pricing",
                        "evidence_artifact_sha256": sha256_bytes(b"anthropic-pricing-capture"),
                        "batch_input_usd_per_1m": 0.05,
                        "batch_output_usd_per_1m": 0.25,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    live_unlocked = sign_ceremony_with_pem_keys(
        owner_private_pem_path=owner_pem,
        auditor_private_pem_path=aud_pem,
        trust_root_dir=ext_tr,
        pack_dir=pack_dir,
        gate_phase="STAGE1_LIVE",
        sv01_written_artifact_path=gvhd_pdf_stub,
        sv01_supervisor_identity="TS. GVHD Test",
        raw_probe_transcript_path=raw_transcript_path,
        rate_evidence_path=rate_ev_path,
    )
    assert live_unlocked["live_execution_authorized"] is True
    assert live_unlocked["batch_generation_authorized"] is True
    assert live_unlocked["selected_cap_regime"] == "UNAMENDED_20USD"

    gate_live = authorize_stage1_live_canary_gate(
        activation_pack_dir=pack_dir,
        external_trust_root_dir=ext_tr,
        out_of_band_owner_pubkey_sha256=owner_oob_sha,
        out_of_band_auditor_pubkey_sha256=aud_oob_sha,
        out_of_band_manifest_sha256=live_unlocked["out_of_band_pins"]["trust_root_manifest_sha256"],
        raw_probe_transcript_path=raw_transcript_path,
    )
    assert gate_live["batch_generation_authorized"] is True
    assert gate_live["dev_hard_cap_usd"] == 2.0
    assert gate_live["total_hard_cap_usd"] == 20.0

    # Tampered raw transcript file fails checksum check
    bad_tr_path = tmp_path / "tampered_transcript.json"
    bad_tr_path.write_text('{"tampered": true}\n', encoding="utf-8")
    with pytest.raises(PermissionError, match="RAW_PROBE_TRANSCRIPT_SHA256_MISMATCH"):
        authorize_stage1_live_canary_gate(
            activation_pack_dir=pack_dir,
            external_trust_root_dir=ext_tr,
            out_of_band_owner_pubkey_sha256=owner_oob_sha,
            out_of_band_auditor_pubkey_sha256=aud_oob_sha,
            raw_probe_transcript_path=bad_tr_path,
        )


def test_p1c_pre_submit_intent_crash_reconcile_missing_usage_and_aggregate_budget(tmp_path: Path) -> None:
    from w07_g4_scorer.route2_live_preflight import (
        link_stage1_dispatched_batch,
        load_or_init_aggregate_stage1_ledger,
        prepare_stage1_pre_submit_intent,
        reconcile_stage1_crash_intents,
    )

    agg_ledger = tmp_path / "aggregate_stage1_live_ledger.json"
    rate_a = ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna-2026-09-22", 1.0, 2.0)
    rate_b = ProviderRateProfile("anthropic", "claude-haiku-5-5", "claude-haiku-5-5", 1.0, 2.0)

    # 1. Cross-provider aggregate DEV $2.00 budget: OpenAI reserves $1.20 + Anthropic reserves $0.75 = $1.95 <= $2.00
    i_a = prepare_stage1_pre_submit_intent(
        ledger_path=agg_ledger,
        run_id="run-01",
        rate_profile=rate_a,
        custom_ids=["a1", "a2"],
        batch_reserved_worst_case_usd=1.20,
    )
    i_b = prepare_stage1_pre_submit_intent(
        ledger_path=agg_ledger,
        run_id="run-01",
        rate_profile=rate_b,
        custom_ids=["b1", "b2"],
        batch_reserved_worst_case_usd=0.75,
    )
    assert i_a["status"] == "INTENT_PRE_SUBMIT"
    # Second attempt adding $0.10 across either provider exceeds $2.00 aggregate cap!
    with pytest.raises(PermissionError, match="STAGE1_AGGREGATE_DEV_CAP_EXCEEDED"):
        prepare_stage1_pre_submit_intent(
            ledger_path=agg_ledger,
            run_id="run-02",
            rate_profile=rate_b,
            custom_ids=["b3"],
            batch_reserved_worst_case_usd=0.10,
        )

    # Duplicate idempotency key blocked before re-submit
    with pytest.raises(RuntimeError, match="DUPLICATE_IDEMPOTENCY_KEY_REQUIRES_RECONCILIATION"):
        prepare_stage1_pre_submit_intent(
            ledger_path=agg_ledger,
            run_id="run-01",
            rate_profile=rate_a,
            custom_ids=["a1", "a2"],
            batch_reserved_worst_case_usd=0.01,
        )

    # Link only intent B -> intent A remains pre-submit crash (no batch_id yet in ledger!)
    link_stage1_dispatched_batch(
        ledger_path=agg_ledger,
        client_idempotency_key=i_b["client_idempotency_key"],
        batch_id="batch-b-1",
        input_file_id="fin-b-1",
    )

    class _MockReconciler:
        def __init__(self, *, fail_lookup_for: set[str] | None = None, fail_delete: bool = False) -> None:
            self.fail_lookup_for = fail_lookup_for or set()
            self.fail_delete = fail_delete
            self.deleted_batches: list[str] = []
            self.deleted_files: list[str] = []

        def lookup_batch_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any]:
            if idempotency_key in self.fail_lookup_for:
                raise TimeoutError("NETWORK_TIMEOUT")
            # Provider DID receive OpenAI pre-submit crash!
            return {"found": True, "batch_id": "batch-a-recovered"}

        def fetch_batch_outcome(self, batch_id: str) -> dict[str, Any]:
            if batch_id == "batch-a-recovered":
                # Completed batch on provider with MISSING usage object -> MUST fallback to $1.20 worst-case reserve, NOT $0!
                return {
                    "batch_id": batch_id,
                    "batch_status": "COMPLETED",
                    "billed": True,
                    "output_file_id": "fout-a-1",
                    "items": [{"custom_id": "a1", "usage": None}, {"custom_id": "a2", "usage": None}],
                }
            return {
                "batch_id": batch_id,
                "batch_status": "COMPLETED",
                "output_file_id": "fout-b-1",
                "items": [
                    {"custom_id": "b1", "usage": {"input_tokens": 1000, "output_tokens": 500}},
                    {"custom_id": "b2", "usage": {"input_tokens": 1000, "output_tokens": 500}},
                ],
            }

        def delete_batch(self, batch_id: str) -> dict[str, Any]:
            self.deleted_batches.append(batch_id)
            return {"deleted": not self.fail_delete}

        def delete_file(self, file_id: str) -> dict[str, Any]:
            self.deleted_files.append(file_id)
            return {"deleted": True}

    # 2. First simulate ambiguous unreachable lookup for intent A -> retains $1.20 unresolved reserve, settles B ($0.004)
    rec_ambig = _MockReconciler(fail_lookup_for={i_a["client_idempotency_key"]})
    state_ambig = reconcile_stage1_crash_intents(
        ledger_path=agg_ledger,
        rate_profiles_by_provider={"openai": rate_a, "anthropic": rate_b},
        reconciler=rec_ambig,
    )
    assert state_ambig["intents"][i_a["client_idempotency_key"]]["status"] == "UNRESOLVED_CRASH_RESERVED"
    assert abs(state_ambig["total_unresolved_reserve_usd"] - 1.20) < 1e-9
    assert abs(state_ambig["total_confirmed_spent_usd"] - 0.004) < 1e-9
    # Still blocks exceeding $2.00 while $1.20 reserve is held!
    with pytest.raises(PermissionError, match="STAGE1_AGGREGATE_DEV_CAP_EXCEEDED"):
        prepare_stage1_pre_submit_intent(
            ledger_path=agg_ledger,
            run_id="run-03",
            rate_profile=rate_b,
            custom_ids=["b4"],
            batch_reserved_worst_case_usd=0.85,
        )

    # 3. Provider recovery finds batch-a-recovered with missing usage -> charges $1.20 fallback reserve (NEVER $0.00!)
    rec_ok = _MockReconciler()
    state_final = reconcile_stage1_crash_intents(
        ledger_path=agg_ledger,
        rate_profiles_by_provider={"openai": rate_a, "anthropic": rate_b},
        reconciler=rec_ok,
    )
    a_ent = state_final["intents"][i_a["client_idempotency_key"]]
    assert a_ent["status"] == "SETTLED_MISSING_USAGE_WORST_CASE_RESERVED"
    assert a_ent["missing_usage_fallback_used"] is True
    assert abs(a_ent["confirmed_cost_usd"] - 1.20) < 1e-9
    assert abs(state_final["total_confirmed_spent_usd"] - 1.204) < 1e-9
    assert state_final["total_unresolved_reserve_usd"] == 0.0
    assert "batch-a-recovered" in rec_ok.deleted_batches

    # 4. Cleanup failure still records failure & cost atomically
    i_fail = prepare_stage1_pre_submit_intent(
        ledger_path=agg_ledger,
        run_id="run-04",
        rate_profile=rate_b,
        custom_ids=["b5"],
        batch_reserved_worst_case_usd=0.10,
    )
    link_stage1_dispatched_batch(
        ledger_path=agg_ledger,
        client_idempotency_key=i_fail["client_idempotency_key"],
        batch_id="batch-b-cleanup-fail",
    )
    with pytest.raises(RuntimeError, match="LIVE_CLEANUP_INCOMPLETE"):
        reconcile_stage1_crash_intents(
            ledger_path=agg_ledger,
            rate_profiles_by_provider={"openai": rate_a, "anthropic": rate_b},
            reconciler=_MockReconciler(fail_delete=True),
        )
    after_cleanup_fail = load_or_init_aggregate_stage1_ledger(agg_ledger)
    assert len(after_cleanup_fail["cleanup_failures"]) == 1
    assert after_cleanup_fail["intents"][i_fail["client_idempotency_key"]]["cleanup_status"] == "CLEANUP_FAILED"


def test_p1c_ambiguous_miss_nonterminal_statuses_and_concurrent_two_provider_lock(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from w07_g4_scorer.route2_live_preflight import (
        link_stage1_dispatched_batch,
        load_or_init_aggregate_stage1_ledger,
        prepare_stage1_pre_submit_intent,
        reconcile_stage1_crash_intents,
    )

    rate_a = ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna-2026-09-22", 1.0, 2.0)
    rate_b = ProviderRateProfile("anthropic", "claude-haiku-5-5", "claude-haiku-5-5", 1.0, 2.0)

    # 1. Fail-closed case A: Ambiguous lookup_batch_by_idempotency_key -> {found: False} WITHOUT authoritative proof
    # MUST keep full $1.20 reserve and enforce aggregate $2.00 cap!
    ledger1 = tmp_path / "ambig_miss_and_nonterminal.json"
    i_pre = prepare_stage1_pre_submit_intent(
        ledger_path=ledger1,
        run_id="run-ambig",
        rate_profile=rate_a,
        custom_ids=["q1"],
        batch_reserved_worst_case_usd=1.20,
    )
    k_pre = i_pre["client_idempotency_key"]

    class _ProgressionReconciler:
        def __init__(self) -> None:
            self.phase = "AMBIGUOUS_MISS"
            self.deleted_batches: list[str] = []
            self.deleted_files: list[str] = []

        def lookup_batch_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any]:
            if self.phase == "AMBIGUOUS_MISS":
                return {"found": False}  # eventual-consistency / ambiguous miss
            if self.phase == "AUTH_UNSUBMITTED":
                return {
                    "found": False,
                    "authoritative_non_acceptance": True,
                    "non_acceptance_evidence": "pre_http_abort_proof_001",
                }
            return {"found": True, "batch_id": "batch-late-visible"}

        def fetch_batch_outcome(self, batch_id: str) -> dict[str, Any]:
            if self.phase in ("IN_PROGRESS", "QUEUED", "PENDING", "PROCESSING"):
                return {"batch_id": batch_id, "batch_status": self.phase, "items": []}
            if self.phase == "FAILED_TERMINAL":
                return {"batch_id": batch_id, "batch_status": "FAILED", "output_file_id": "fout-fail", "items": []}
            return {
                "batch_id": batch_id,
                "batch_status": "COMPLETED",
                "output_file_id": "fout-ok",
                "items": [{"custom_id": "q1", "usage": {"input_tokens": 5000, "output_tokens": 1000}}],  # $0.007
            }

        def delete_batch(self, batch_id: str) -> dict[str, Any]:
            self.deleted_batches.append(batch_id)
            return {"deleted": True}

        def delete_file(self, file_id: str) -> dict[str, Any]:
            self.deleted_files.append(file_id)
            return {"deleted": True}

    rec = _ProgressionReconciler()
    s1 = reconcile_stage1_crash_intents(
        ledger_path=ledger1, rate_profiles_by_provider={"openai": rate_a, "anthropic": rate_b}, reconciler=rec
    )
    assert s1["intents"][k_pre]["status"] == "UNRESOLVED_CRASH_RESERVED"
    assert abs(s1["total_unresolved_reserve_usd"] - 1.20) < 1e-9
    assert abs(s1["effective_committed_usd"] - 1.20) < 1e-9
    assert rec.deleted_batches == []

    # Cap STILL holds $1.20 reserved -> requesting $0.85 MUST fail closed!
    with pytest.raises(PermissionError, match="STAGE1_AGGREGATE_DEV_CAP_EXCEEDED"):
        prepare_stage1_pre_submit_intent(
            ledger_path=ledger1, run_id="run-b", rate_profile=rate_b, custom_ids=["q2"], batch_reserved_worst_case_usd=0.85
        )

    # 2. Fail-closed case B: Eventual consistency finds batch_id, then returns IN_PROGRESS / QUEUED / PENDING / PROCESSING
    # MUST keep full $1.20 reserve AND NOT run cleanup!
    for nonterm in ("IN_PROGRESS", "QUEUED", "PENDING", "PROCESSING"):
        rec.phase = nonterm
        st_nt = reconcile_stage1_crash_intents(
            ledger_path=ledger1, rate_profiles_by_provider={"openai": rate_a, "anthropic": rate_b}, reconciler=rec
        )
        assert st_nt["intents"][k_pre]["status"] == f"NONTERMINAL_RESERVED_{nonterm}"
        assert st_nt["intents"][k_pre]["cleanup_status"] == "DEFERRED_NONTERMINAL"
        assert abs(st_nt["total_unresolved_reserve_usd"] - 1.20) < 1e-9
        assert abs(st_nt["effective_committed_usd"] - 1.20) < 1e-9
        assert st_nt["total_confirmed_spent_usd"] == 0.0
        assert rec.deleted_batches == []

    # 3. Once batch reaches terminal COMPLETED -> settles actual usage ($0.007), releases reserve, executes cleanup!
    rec.phase = "COMPLETED"
    st_done = reconcile_stage1_crash_intents(
        ledger_path=ledger1, rate_profiles_by_provider={"openai": rate_a, "anthropic": rate_b}, reconciler=rec
    )
    assert st_done["intents"][k_pre]["status"] == "SETTLED"
    assert st_done["intents"][k_pre]["cleanup_status"] == "COMPLETED"
    assert st_done["total_unresolved_reserve_usd"] == 0.0
    assert abs(st_done["total_confirmed_spent_usd"] - 0.007) < 1e-9
    assert rec.deleted_batches == ["batch-late-visible"]
    assert rec.deleted_files == ["fout-ok"]

    # 4. Terminal FAILED batch with empty usage reserves worst-case & cleans up; authoritative non-acceptance releases $0.00
    ledger_t2 = tmp_path / "failed_and_auth_unsub.json"
    i_f = prepare_stage1_pre_submit_intent(
        ledger_path=ledger_t2, run_id="r-fail", rate_profile=rate_a, custom_ids=["f1"], batch_reserved_worst_case_usd=0.60
    )
    link_stage1_dispatched_batch(
        ledger_path=ledger_t2, client_idempotency_key=i_f["client_idempotency_key"], batch_id="b-fail-1", input_file_id="fin-fail"
    )
    i_u = prepare_stage1_pre_submit_intent(
        ledger_path=ledger_t2, run_id="r-unsub", rate_profile=rate_b, custom_ids=["u1"], batch_reserved_worst_case_usd=0.50
    )
    rec_t2 = _ProgressionReconciler()
    rec_t2.phase = "AUTH_UNSUBMITTED"
    # Use a wrapper so dispatched batch returns FAILED_TERMINAL while pre-submit returns AUTH_UNSUBMITTED
    orig_fetch = rec_t2.fetch_batch_outcome

    def _fetch_fail(bid: str) -> dict[str, Any]:
        rec_t2.phase = "FAILED_TERMINAL"
        return orig_fetch(bid)

    rec_t2.fetch_batch_outcome = _fetch_fail  # type: ignore[method-assign]
    st_t2 = reconcile_stage1_crash_intents(
        ledger_path=ledger_t2, rate_profiles_by_provider={"openai": rate_a, "anthropic": rate_b}, reconciler=rec_t2
    )
    assert st_t2["intents"][i_f["client_idempotency_key"]]["status"] == "SETTLED_MISSING_USAGE_WORST_CASE_RESERVED"
    assert abs(st_t2["total_confirmed_spent_usd"] - 0.60) < 1e-9
    assert "b-fail-1" in rec_t2.deleted_batches
    assert st_t2["intents"][i_u["client_idempotency_key"]]["status"] == "CANCELLED_UNSUBMITTED"
    assert st_t2["total_unresolved_reserve_usd"] == 0.0

    # 5. Concurrent two-provider budget reservation stress test (single-writer lock MUST enforce $2.00 cap strictly)
    ledger_conc = tmp_path / "concurrent_two_providers.json"

    def _reserve_worker(idx: int) -> str:
        rp = rate_a if idx % 2 == 0 else rate_b
        try:
            prepare_stage1_pre_submit_intent(
                ledger_path=ledger_conc,
                run_id=f"conc-{idx}",
                rate_profile=rp,
                custom_ids=[f"c-{idx}"],
                batch_reserved_worst_case_usd=0.40,
            )
            return "RESERVED"
        except PermissionError as exc:
            assert "STAGE1_AGGREGATE_DEV_CAP_EXCEEDED" in str(exc)
            return "CAP_BLOCKED"

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(_reserve_worker, range(8)))  # 8 * $0.40 = $3.20 attempted vs $2.00 cap
    assert outcomes.count("RESERVED") == 5
    assert outcomes.count("CAP_BLOCKED") == 3
    final_conc = load_or_init_aggregate_stage1_ledger(ledger_conc)
    assert abs(final_conc["effective_committed_usd"] - 2.00) < 1e-9
    assert len(final_conc["intents"]) == 5



