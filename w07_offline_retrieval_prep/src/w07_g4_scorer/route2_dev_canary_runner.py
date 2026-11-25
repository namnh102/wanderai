"""Offline mock-only Stage-1 DEV canary batch runner with S/V boundary, Ed25519 receipts, crash-safe partial-batch accounting, idempotent resume, and cleanup."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from w07_g4_scorer.contracts import sha256_bytes
from w07_g4_scorer.judge_gates import (
    ACTIVE_SUPPORTED_JUDGE_MODELS,
    validate_judge_api_config,
)
from w07_g4_scorer.route2_aiproxy import (
    assert_cloud_payload_v_boundary,
    build_sanitized_v_cloud_request_payload,
    project_cloud_quote_locally_to_canonical_s,
    validate_route2_authorization_bundle,
)

MAX_STAGE1_CANARY_QUERIES = 5
MAX_SCHEMA_RETRIES_PER_ITEM = 1
MAX_BATCH_RETRY_FRACTION = 0.15
MAX_FAILED_BATCHES = 1
DEFAULT_DEV_CANARY_HARD_CAP_USD = 2.00
ANTHROPIC_100K_CLIFF_TOKENS = 100000
SPEND_LEDGER_SCHEMA_V2 = "GOMATE_W07_ROUTE2_CANARY_SPEND_LEDGER_V2"


class MockBatchTransportProtocol(Protocol):
    """Protocol strictly for offline mock/record-replay batch transports (NEVER live HTTP)."""

    is_offline_mock_transport: bool
    provider: str

    def count_tokens_mock(self, wire_items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        ...

    def submit_batch(self, wire_items: Sequence[Mapping[str, Any]], *, batch_label: str) -> dict[str, Any]:
        ...

    def fetch_batch_results(self, batch_id: str) -> dict[str, Any]:
        ...

    def delete_batch(self, batch_id: str) -> dict[str, Any]:
        ...

    def delete_file(self, file_id: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ProviderRateProfile:
    """Attested Batch API token pricing & exact snapshot expectations for metering."""

    provider: str
    model_id: str
    expected_snapshot_id: str
    batch_input_usd_per_1m: float
    batch_output_usd_per_1m: float

    def __post_init__(self) -> None:
        if self.provider not in ("openai", "anthropic", "google"):
            raise ValueError(f"Unsupported provider in rate profile: {self.provider!r}")
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError("ProviderRateProfile.model_id must be non-empty")
        if not isinstance(self.expected_snapshot_id, str) or not self.expected_snapshot_id.strip():
            raise ValueError("ProviderRateProfile.expected_snapshot_id must be non-empty")
        for label, rate in (
            ("batch_input_usd_per_1m", self.batch_input_usd_per_1m),
            ("batch_output_usd_per_1m", self.batch_output_usd_per_1m),
        ):
            if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(float(rate)) or float(rate) < 0.0:
                raise ValueError(f"INVALID_RATE_PROFILE:{label}={rate!r}")


def format_provider_batch_item(
    *,
    provider: str,
    model_id: str,
    packet_item_uuid: str,
    prompt_order: str,
    wire_user_prompt: str,
    system_prompt: str,
    response_schema: Mapping[str, Any],
    doc_record_for_leak_check: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build exact AUTO-R09 compliant provider batch wire item with S/V firewall verification."""
    if provider == "openai":
        if model_id in ACTIVE_SUPPORTED_JUDGE_MODELS:
            spec = ACTIVE_SUPPORTED_JUDGE_MODELS[model_id]
            assert spec["provider_api_profile"].startswith("OPENAI_GPT6")
        wire_item = {
            "custom_id": f"{packet_item_uuid}::{prompt_order}",
            "method": "POST",
            "url": "/v1/responses",
            "body": {
                "model": model_id,
                "reasoning": {"effort": "low"},
                "max_output_tokens": 1024,
                "store": False,
                "input": [
                    {"role": "developer", "content": system_prompt},
                    {"role": "user", "content": wire_user_prompt},
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "w07_judge_s4",
                        "strict": True,
                        "schema": dict(response_schema),
                    }
                },
            },
        }
    elif provider == "anthropic":
        if model_id in ACTIVE_SUPPORTED_JUDGE_MODELS:
            spec = ACTIVE_SUPPORTED_JUDGE_MODELS[model_id]
            assert spec["provider_api_profile"] == "ANTHROPIC_CLAUDE_5_5_ADAPTIVE_EFFORT"
        wire_item = {
            "custom_id": f"{packet_item_uuid}::{prompt_order}",
            "params": {
                "model": model_id,
                "max_tokens": 1024,
                "anthropic_version": "2026-10-21",
                "output_config": {
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": dict(response_schema)},
                },
                "system": system_prompt,
                "messages": [{"role": "user", "content": wire_user_prompt}],
            },
        }
    elif provider == "google":
        wire_item = {
            "custom_id": f"{packet_item_uuid}::{prompt_order}",
            "request": {
                "model": f"models/{model_id}",
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": wire_user_prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": 1024,
                    "thinkingConfig": {"thinkingLevel": "LOW"},
                    "responseMimeType": "application/json",
                },
            },
        }
    else:
        raise ValueError(f"Unsupported batch provider: {provider!r}")

    assert_cloud_payload_v_boundary(wire_item, doc_record_for_leak_check=doc_record_for_leak_check)
    return wire_item


def _validate_nonneg_int_token(val: Any, field: str) -> int:
    if type(val) is not int or val < 0:
        raise ValueError(f"INVALID_TOKEN_COUNT:{field}={val!r}")
    return val


def _meter_usage_usd(usage: Any, rate: ProviderRateProfile) -> float:
    """Strictly meter provider usage USD; NEVER infer zero bill from missing/malformed usage."""
    if not isinstance(usage, Mapping):
        raise ValueError("MISSING_OR_INVALID_USAGE_OBJECT")
    if "input_tokens" not in usage or "output_tokens" not in usage:
        raise ValueError("MISSING_REQUIRED_USAGE_TOKEN_FIELDS")
    in_tok = _validate_nonneg_int_token(usage["input_tokens"], "input_tokens")
    out_tok = _validate_nonneg_int_token(usage["output_tokens"], "output_tokens")
    for opt_field in ("cache_creation_input_tokens", "cache_read_input_tokens", "reasoning_tokens"):
        if opt_field in usage:
            _validate_nonneg_int_token(usage[opt_field], opt_field)
    cost = (in_tok * float(rate.batch_input_usd_per_1m) / 1_000_000.0) + (
        out_tok * float(rate.batch_output_usd_per_1m) / 1_000_000.0
    )
    if not math.isfinite(cost) or cost < 0.0:
        raise ValueError(f"NONFINITE_OR_NEGATIVE_USAGE_COST:{cost!r}")
    return round(cost, 8)


def _append_jsonl_durable(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def _save_spend_ledger_atomic(path: Path, ledger: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_p = path.with_suffix(".json.tmp")
    payload = json.dumps(dict(ledger), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    with tmp_p.open("w", encoding="utf-8") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_p, path)


def _recompute_ledger_totals(ledger: dict[str, Any]) -> float:
    total = 0.0
    recorded_summary: dict[str, Any] = {}
    batches: dict[str, dict[str, Any]] = ledger.setdefault("batches", {})
    for bid, b_rec in sorted(batches.items()):
        billed_map = b_rec.get("billed_item_costs", {})
        item_sum = sum(float(v["cost_usd"]) for v in billed_map.values())
        extra_sum = float(b_rec.get("extra_batch_billing_usd", 0.0))
        b_total = round(item_sum + extra_sum, 8)
        b_rec["batch_total_billed_usd"] = b_total
        total += b_total
        recorded_summary[bid] = {
            "attempt": b_rec.get("attempt"),
            "status": b_rec.get("status"),
            "items_submitted": len(b_rec.get("submitted_custom_ids", [])),
            "items_billed": len(billed_map),
            "batch_cost_usd": b_total,
            "cleanup_status": b_rec.get("cleanup_status"),
            "od_ae_05_retention_accepted": True,
        }
    orphan_map: dict[str, float] = ledger.setdefault("reconciled_orphan_raw_log_items", {})
    total += sum(float(v) for v in orphan_map.values())
    intent_reserve_total = round(
        sum(
            float(rec.get("reserved_worst_case_usd", 0.0))
            for rec in ledger.get("pending_submit_intents", {}).values()
            if rec.get("status") in ("INTENT_PRE_SUBMIT", "UNRESOLVED_CRASH_RESERVED")
        ),
        8,
    )
    total_rounded = round(total, 8)
    prior_total = float(ledger.get("total_spent_usd", 0.0))
    if total_rounded < prior_total - 1e-9:
        raise ValueError(f"LEDGER_SPEND_ROLLBACK_DETECTED: recomputed={total_rounded} < recorded={prior_total}")
    ledger["total_spent_usd"] = max(total_rounded, round(prior_total, 8))
    ledger["total_unresolved_reserve_usd"] = intent_reserve_total
    ledger["effective_committed_usd"] = round(float(ledger["total_spent_usd"]) + intent_reserve_total, 8)
    ledger["recorded_batches"] = recorded_summary
    return float(ledger["total_spent_usd"])


def _load_and_reconcile_ledger(
    *,
    raw_log_path: Path,
    spend_ledger_path: Path,
    rate_profile: ProviderRateProfile,
) -> tuple[dict[str, dict[str, Any]], set[tuple[str, str]], dict[str, Any]]:
    if spend_ledger_path.is_file():
        ledger = json.loads(spend_ledger_path.read_text(encoding="utf-8"))
        if type(ledger) is not dict or "recorded_batches" not in ledger:
            raise ValueError("Corrupted persistent spend ledger")
        ledger.setdefault("batches", {})
        ledger.setdefault("pending_submit_intents", {})
        ledger.setdefault("reconciled_orphan_raw_log_items", {})
        ledger.setdefault("cleanup_failures", [])
        ledger.setdefault("failed_batches", 0)
    else:
        ledger = {
            "schema_version": SPEND_LEDGER_SCHEMA_V2,
            "total_spent_usd": 0.0,
            "failed_batches": 0,
            "batches": {},
            "pending_submit_intents": {},
            "recorded_batches": {},
            "reconciled_orphan_raw_log_items": {},
            "cleanup_failures": [],
        }

    settled_items: dict[str, dict[str, Any]] = {}
    logged_pair_keys: set[tuple[str, str]] = set()
    dirty = False

    if raw_log_path.is_file():
        for raw_ln in raw_log_path.read_text(encoding="utf-8").splitlines():
            ln = raw_ln.strip()
            if not ln:
                continue
            obj = json.loads(ln)
            cid = obj.get("custom_id")
            bid = obj.get("batch_id")
            if isinstance(bid, str) and isinstance(cid, str):
                logged_pair_keys.add((bid, cid))
            if isinstance(cid, str) and obj.get("final_for_item") is True:
                settled_items[cid] = obj

            # Crash reconciliation: any item row already flushed to raw JSONL MUST be billed accurately.
            if isinstance(bid, str) and isinstance(cid, str) and "usage" in obj and obj.get("usage") is not None:
                recost_usd = _meter_usage_usd(obj["usage"], rate_profile)
                batches = ledger["batches"]
                if bid in batches:
                    billed_map = batches[bid].setdefault("billed_item_costs", {})
                    if cid not in billed_map or float(billed_map[cid]["cost_usd"]) < recost_usd - 1e-12:
                        billed_map[cid] = {
                            "cost_usd": recost_usd,
                            "usage": dict(obj["usage"]),
                            "model_snapshot_id": obj.get("model_snapshot_id"),
                            "reconciled_from_raw_log": True,
                        }
                        dirty = True
                else:
                    ok = f"{bid}::{cid}"
                    orphans = ledger["reconciled_orphan_raw_log_items"]
                    if float(orphans.get(ok, 0.0)) < recost_usd - 1e-12:
                        orphans[ok] = recost_usd
                        dirty = True

    _recompute_ledger_totals(ledger)
    if dirty or not spend_ledger_path.is_file():
        _save_spend_ledger_atomic(spend_ledger_path, ledger)
    return settled_items, logged_pair_keys, ledger


def _meter_batch_response_into_ledger(
    *,
    res: Mapping[str, Any],
    batch_id: str,
    rate_profile: ProviderRateProfile,
    ledger: dict[str, Any],
    spend_ledger_path: Path,
) -> float:
    """Commit ALL billable usage returned by provider BEFORE any validation exception can abort."""
    b_rec = ledger["batches"][batch_id]
    billed_map = b_rec.setdefault("billed_item_costs", {})
    raw_items = res.get("items", [])
    if not isinstance(raw_items, Sequence):
        raise ValueError(f"INVALID_BATCH_ITEMS_SEQUENCE:batch={batch_id}")

    for item in raw_items:
        if not isinstance(item, Mapping):
            raise ValueError(f"INVALID_BATCH_ITEM_OBJECT:batch={batch_id}")
        cid = str(item.get("custom_id", ""))
        if not cid:
            raise ValueError(f"MISSING_BATCH_ITEM_CUSTOM_ID:batch={batch_id}")
        item_cost = _meter_usage_usd(item.get("usage"), rate_profile)
        prior_cost = float(billed_map.get(cid, {}).get("cost_usd", 0.0))
        billed_map[cid] = {
            "cost_usd": max(prior_cost, item_cost),
            "usage": dict(item["usage"]),
            "model_snapshot_id": item.get("model_snapshot_id"),
        }

    if "batch_billing_usage" in res and res["batch_billing_usage"] is not None:
        extra_cost = _meter_usage_usd(res["batch_billing_usage"], rate_profile)
        b_rec["extra_batch_billing_usd"] = max(float(b_rec.get("extra_batch_billing_usd", 0.0)), extra_cost)

    if res.get("output_file_id"):
        b_rec["output_file_id"] = res.get("output_file_id")

    total_spent = _recompute_ledger_totals(ledger)
    b_rec["status"] = "METERED_PENDING_VALIDATION"
    _save_spend_ledger_atomic(spend_ledger_path, ledger)
    return total_spent


def _cleanup_batch_and_files(
    *,
    transport: MockBatchTransportProtocol,
    batch_id: str,
    input_file_id: str | None,
    output_file_id: str | None,
    ledger: dict[str, Any],
    spend_ledger_path: Path,
) -> dict[str, Any]:
    """Delete batch and files, durably recording any cleanup failure before raising."""
    b_rec = ledger["batches"][batch_id]
    del_files: list[dict[str, Any]] = []
    batch_deleted = False
    failures: list[dict[str, Any]] = []

    try:
        del_batch = transport.delete_batch(batch_id)
        if not isinstance(del_batch, Mapping) or not del_batch.get("deleted"):
            failures.append({"stage": "delete_batch", "target": batch_id, "error": "deleted=False"})
        else:
            batch_deleted = True
    except Exception as exc:
        failures.append({"stage": "delete_batch", "target": batch_id, "error": f"{type(exc).__name__}:{exc}"})

    for fid in (input_file_id, output_file_id):
        if isinstance(fid, str) and fid:
            try:
                df = transport.delete_file(fid)
                if not isinstance(df, Mapping) or not df.get("deleted"):
                    failures.append({"stage": "delete_file", "target": fid, "error": "deleted=False"})
                else:
                    del_files.append(dict(df))
            except Exception as exc:
                failures.append({"stage": "delete_file", "target": fid, "error": f"{type(exc).__name__}:{exc}"})

    if failures:
        b_rec["cleanup_status"] = "CLEANUP_FAILED"
        b_rec["cleanup_error"] = "; ".join(f"{f['stage']}({f['target']}):{f['error']}" for f in failures)
        ledger["cleanup_failures"].extend({"batch_id": batch_id, **f} for f in failures)
        _recompute_ledger_totals(ledger)
        _save_spend_ledger_atomic(spend_ledger_path, ledger)
        first = failures[0]
        if first["stage"] == "delete_batch":
            raise RuntimeError(f"BATCH_CLEANUP_INCOMPLETE:batch={batch_id}:{first['error']}")
        raise RuntimeError(f"FILE_CLEANUP_INCOMPLETE:file={first['target']}:{first['error']}")

    receipt = {
        "batch_id": batch_id,
        "batch_deleted": batch_deleted,
        "files_deleted": del_files,
        "od_ae_05_retention_policy_acknowledged": True,
    }
    b_rec["cleanup_status"] = "COMPLETED"
    b_rec["cleanup_receipt"] = receipt
    b_rec["cleanup_error"] = None
    _recompute_ledger_totals(ledger)
    _save_spend_ledger_atomic(spend_ledger_path, ledger)
    return receipt


def _recover_dispatched_pending_batches(
    *,
    transport: MockBatchTransportProtocol,
    rate_profile: ProviderRateProfile,
    ledger: dict[str, Any],
    settled_items: dict[str, dict[str, Any]],
    logged_pair_keys: set[tuple[str, str]],
    entries_by_cid: Mapping[str, Mapping[str, Any]],
    raw_log_jsonl_path: Path,
    spend_ledger_path: Path,
    max_failed_batches: int,
    dev_hard_cap_usd: float,
    cleanup_receipts: list[dict[str, Any]],
) -> None:
    """Recover any DISPATCHED batch left unsettled by an earlier crash before submitting new work."""
    pending_ids = [
        bid
        for bid, b_rec in sorted(ledger.get("batches", {}).items())
        if b_rec.get("status") in ("DISPATCHED", "METERED_PENDING_VALIDATION")
    ]
    for bid in pending_ids:
        b_rec = ledger["batches"][bid]
        in_fid = b_rec.get("input_file_id")
        out_fid = b_rec.get("output_file_id")
        if b_rec.get("status") == "METERED_PENDING_VALIDATION":
            if b_rec.get("cleanup_status") != "COMPLETED":
                cleanup_receipts.append(
                    _cleanup_batch_and_files(
                        transport=transport,
                        batch_id=bid,
                        input_file_id=in_fid,
                        output_file_id=out_fid,
                        ledger=ledger,
                        spend_ledger_path=spend_ledger_path,
                    )
                )
            b_rec["status"] = "RECOVERED_PARTIAL_SETTLED"
            _recompute_ledger_totals(ledger)
            _save_spend_ledger_atomic(spend_ledger_path, ledger)
            continue
        try:
            res = transport.fetch_batch_results(bid)
            out_fid = res.get("output_file_id") or out_fid
            _meter_batch_response_into_ledger(
                res=res,
                batch_id=bid,
                rate_profile=rate_profile,
                ledger=ledger,
                spend_ledger_path=spend_ledger_path,
            )
            b_status = str(res.get("batch_status", "COMPLETED")).upper()
            batch_snap = res.get("model_snapshot_id")
            if batch_snap != rate_profile.expected_snapshot_id:
                b_rec["status"] = "PARTIAL_ERROR_SETTLED"
                b_rec["error_code"] = "MODEL_SNAPSHOT_DRIFT_ABORT"
                _save_spend_ledger_atomic(spend_ledger_path, ledger)
                raise PermissionError(
                    f"MODEL_SNAPSHOT_DRIFT_ABORT: expected={rate_profile.expected_snapshot_id!r}, got={batch_snap!r}"
                )
            if b_status in ("FAILED", "CANCELLED", "EXPIRED"):
                ledger["failed_batches"] = int(ledger.get("failed_batches", 0)) + 1
                b_rec["status"] = f"{b_status}_SETTLED"
                b_rec["error_code"] = f"BATCH_{b_status}:{bid}"
                _recompute_ledger_totals(ledger)
                _save_spend_ledger_atomic(spend_ledger_path, ledger)
                if ledger["failed_batches"] > max_failed_batches:
                    raise PermissionError(f"MAX_FAILED_BATCHES_EXCEEDED:{ledger['failed_batches']}>{max_failed_batches}")
                raise RuntimeError(f"RECOVERED_BATCH_{b_status}:{bid}")

            if float(ledger["total_spent_usd"]) > dev_hard_cap_usd + 1e-12:
                b_rec["status"] = "PARTIAL_ERROR_SETTLED"
                b_rec["error_code"] = "DEV_BUDGET_ACTUAL_USAGE_CAP_EXCEEDED"
                _save_spend_ledger_atomic(spend_ledger_path, ledger)
                raise PermissionError(
                    f"DEV_BUDGET_ACTUAL_USAGE_CAP_EXCEEDED: {ledger['total_spent_usd']:.6f} > {dev_hard_cap_usd:.4f}"
                )

            settled_cids = list(b_rec.get("settled_custom_ids", []))
            for item in res.get("items", []):
                cid = str(item.get("custom_id", ""))
                entry = entries_by_cid.get(cid)
                if entry is None:
                    continue
                raw_payload = item.get("parsed_response", {})
                local_verdict = project_cloud_quote_locally_to_canonical_s(
                    cloud_response=raw_payload if isinstance(raw_payload, Mapping) else {},
                    safe_doc_v=entry["safe_wire"]["safe_doc_v"],
                    safe_to_v_segments=entry["safe_wire"]["safe_to_v_segments"],
                    doc_sanitized_V=str(entry["input_row"]["sanitized_text_V"]),
                    doc_canonical_S=str(entry["input_row"]["doc_canonical_S"]),
                    doc_v_to_s_segments=entry["input_row"]["doc_v_to_s_segments"],
                    doc_removed_r_audit=entry["input_row"]["doc_removed_r_audit"],
                    doc_meta=entry["input_row"]["doc_meta"],
                    query_meta=entry["input_row"]["query_meta"],
                )
                is_final = local_verdict["state"] != "ERROR"
                item_cost = float(b_rec["billed_item_costs"][cid]["cost_usd"])
                log_record = {
                    "batch_id": bid,
                    "custom_id": cid,
                    "attempt": b_rec.get("attempt", 1),
                    "model_snapshot_id": rate_profile.expected_snapshot_id,
                    "usage": dict(item["usage"]),
                    "cost_usd": item_cost,
                    "wire_payload_sha256": entry["safe_wire"]["wire_payload_sha256"],
                    "cloud_raw_response": raw_payload,
                    "local_validation": local_verdict,
                    "final_for_item": is_final,
                    "recovered_after_crash": True,
                }
                if (bid, cid) not in logged_pair_keys:
                    _append_jsonl_durable(raw_log_jsonl_path, log_record)
                    logged_pair_keys.add((bid, cid))
                if is_final:
                    settled_items[cid] = log_record
                    if cid not in settled_cids:
                        settled_cids.append(cid)

            b_rec["settled_custom_ids"] = settled_cids
            b_rec["status"] = "RECOVERED_SETTLED"
            _recompute_ledger_totals(ledger)
            _save_spend_ledger_atomic(spend_ledger_path, ledger)
        finally:
            if b_rec.get("cleanup_status") != "COMPLETED":
                cleanup_receipts.append(
                    _cleanup_batch_and_files(
                        transport=transport,
                        batch_id=bid,
                        input_file_id=in_fid,
                        output_file_id=out_fid,
                        ledger=ledger,
                        spend_ledger_path=spend_ledger_path,
                    )
                )


def run_stage1_dev_canary_mock_batch(
    *,
    bundle: Mapping[str, Any],
    trust_artifacts: Mapping[str, Mapping[str, Any]],
    canary_items: Sequence[Mapping[str, Any]],
    system_prompt: str,
    response_schema: Mapping[str, Any],
    rate_profile: ProviderRateProfile,
    transport: MockBatchTransportProtocol,
    raw_log_jsonl_path: Path,
    spend_ledger_path: Path,
    sealed_judge_api_config: dict[str, Any] | None = None,
    dev_hard_cap_usd: float = DEFAULT_DEV_CANARY_HARD_CAP_USD,
    max_schema_retries_per_item: int = MAX_SCHEMA_RETRIES_PER_ITEM,
    max_batch_retry_fraction: float = MAX_BATCH_RETRY_FRACTION,
    max_failed_batches: int = MAX_FAILED_BATCHES,
    allow_live_network: bool = False,
    _test_only_trusted_owner_pubkey_hex: str | None = None,
    _test_only_trusted_auditor_pubkey_hex: str | None = None,
    _test_crash_hook: str | None = None,
) -> dict[str, Any]:
    """Execute Stage-1 off-FINAL canary strictly over an offline mock/record-replay Batch transport."""
    if allow_live_network:
        raise PermissionError("LIVE_API_FORBIDDEN_IN_MOCK_CANARY_RUNNER")
    if getattr(transport, "is_offline_mock_transport", False) is not True:
        raise PermissionError("NON_MOCK_TRANSPORT_REJECTED: mock-only runner requires is_offline_mock_transport=True")
    if isinstance(dev_hard_cap_usd, bool) or not math.isfinite(dev_hard_cap_usd) or dev_hard_cap_usd <= 0.0:
        raise ValueError("dev_hard_cap_usd must be finite and > 0")
    if dev_hard_cap_usd > DEFAULT_DEV_CANARY_HARD_CAP_USD:
        raise PermissionError("DEV_CANARY_CAP_CANNOT_EXCEED_2_USD")
    if sealed_judge_api_config is not None:
        validate_judge_api_config(sealed_judge_api_config, approved_model_snapshot_id=rate_profile.expected_snapshot_id)

    auth = validate_route2_authorization_bundle(
        bundle,
        trust_artifacts=trust_artifacts,
        require_live_execution=True,
        _test_only_trusted_owner_pubkey_hex=_test_only_trusted_owner_pubkey_hex,
        _test_only_trusted_auditor_pubkey_hex=_test_only_trusted_auditor_pubkey_hex,
    )
    if auth["cryptographic_verification"].get("authorized_stage") != "STAGE1_DEV_CANARY_ONLY":
        raise PermissionError("STAGE1_CANARY_REQUIRES_STAGE1_SCOPED_OWNER_ACTIVATION")

    # Enforce strict Stage-1 off-FINAL query isolation (<= 5 DEV queries; ZERO FINAL queries)
    distinct_qids: set[str] = set()
    prepared_entries: dict[str, dict[str, Any]] = {}
    ordered_entries: list[dict[str, Any]] = []
    for row in canary_items:
        qmeta = row["query_meta"]
        qid = str(qmeta["query_id"])
        if qmeta.get("split") != "DEV" or "FINAL" in qid.upper():
            raise PermissionError(f"STAGE1_CANARY_FINAL50_CONTAMINATION_BLOCKED on {qid!r}")
        distinct_qids.add(qid)
        custom_id = f"{row['packet_item_uuid']}::{row.get('prompt_order', 'PROMPT_ORDER_CANONICAL')}"
        safe_wire = build_sanitized_v_cloud_request_payload(
            packet_item_uuid=str(row["packet_item_uuid"]),
            query_text=str(row["query_meta"]["query_text"]),
            sanitized_text_V=str(row["sanitized_text_V"]),
            run_nonce=str(row["run_nonce"]),
            prompt_order=str(row.get("prompt_order", "PROMPT_ORDER_CANONICAL")),
            doc_record_for_leak_check=row.get("doc_record_for_leak_check"),
        )
        wire_item = format_provider_batch_item(
            provider=rate_profile.provider,
            model_id=rate_profile.model_id,
            packet_item_uuid=str(row["packet_item_uuid"]),
            prompt_order=str(row.get("prompt_order", "PROMPT_ORDER_CANONICAL")),
            wire_user_prompt=safe_wire["wire_user_prompt"],
            system_prompt=system_prompt,
            response_schema=response_schema,
            doc_record_for_leak_check=row.get("doc_record_for_leak_check"),
        )
        ent = {"input_row": row, "safe_wire": safe_wire, "wire_item": wire_item, "custom_id": custom_id}
        prepared_entries[custom_id] = ent
        ordered_entries.append(ent)

    if not distinct_qids or len(distinct_qids) > MAX_STAGE1_CANARY_QUERIES:
        raise PermissionError(f"STAGE1_CANARY_QUERY_QUOTA_EXCEEDED: {len(distinct_qids)} not in [1, 5]")

    settled_items, logged_pair_keys, spend_ledger = _load_and_reconcile_ledger(
        raw_log_path=raw_log_jsonl_path,
        spend_ledger_path=spend_ledger_path,
        rate_profile=rate_profile,
    )
    cleanup_receipts: list[dict[str, Any]] = []

    if int(spend_ledger.get("failed_batches", 0)) > max_failed_batches:
        raise PermissionError(
            f"MAX_FAILED_BATCHES_EXCEEDED:{spend_ledger['failed_batches']}>{max_failed_batches}"
        )

    _recover_dispatched_pending_batches(
        transport=transport,
        rate_profile=rate_profile,
        ledger=spend_ledger,
        settled_items=settled_items,
        logged_pair_keys=logged_pair_keys,
        entries_by_cid=prepared_entries,
        raw_log_jsonl_path=raw_log_jsonl_path,
        spend_ledger_path=spend_ledger_path,
        max_failed_batches=max_failed_batches,
        dev_hard_cap_usd=dev_hard_cap_usd,
        cleanup_receipts=cleanup_receipts,
    )

    cum_spent_usd = float(spend_ledger["total_spent_usd"])
    failed_batches_count = int(spend_ledger.get("failed_batches", 0))
    if failed_batches_count > max_failed_batches:
        raise PermissionError(f"MAX_FAILED_BATCHES_EXCEEDED:{failed_batches_count}>{max_failed_batches}")

    pending_entries: list[dict[str, Any]] = []
    skipped_resumed: list[str] = []
    for ent in ordered_entries:
        if ent["custom_id"] in settled_items:
            skipped_resumed.append(ent["custom_id"])
        else:
            pending_entries.append(ent)

    token_meter_report: dict[str, Any] = {"skipped_all_settled": len(pending_entries) == 0}
    dispatched_batches: list[str] = []

    if pending_entries:
        token_info = transport.count_tokens_mock([e["wire_item"] for e in pending_entries])
        raw_counts = token_info.get("per_item_input_tokens", [])
        if not isinstance(raw_counts, Sequence) or len(raw_counts) != len(pending_entries):
            raise ValueError("MOCK_COUNT_TOKENS_LENGTH_MISMATCH")
        per_item_counts = [_validate_nonneg_int_token(x, "per_item_input_tokens") for x in raw_counts]
        max_item_tok = max(per_item_counts)
        if max_item_tok >= ANTHROPIC_100K_CLIFF_TOKENS:
            raise PermissionError(f"LONG_CONTEXT_CLIFF_EXCEEDED:{max_item_tok}>={ANTHROPIC_100K_CLIFF_TOKENS}")

        est_in_tok = sum(per_item_counts)
        est_max_out_tok = len(pending_entries) * 1024
        reserved_est_usd = (est_in_tok * float(rate_profile.batch_input_usd_per_1m) / 1_000_000.0) + (
            est_max_out_tok * float(rate_profile.batch_output_usd_per_1m) / 1_000_000.0
        )
        token_meter_report = {
            "count_tokens_sha256": sha256_bytes(json.dumps(token_info, sort_keys=True).encode("utf-8")),
            "total_input_tokens_estimated": est_in_tok,
            "max_item_input_tokens": max_item_tok,
            "reserved_worst_case_usd": round(reserved_est_usd, 6),
        }
        if cum_spent_usd + float(spend_ledger.get("total_unresolved_reserve_usd", 0.0)) + reserved_est_usd > dev_hard_cap_usd + 1e-12:
            raise PermissionError(
                f"DEV_BUDGET_PRE_BATCH_CAP_EXCEEDED: cum={cum_spent_usd:.4f} + reserve={float(spend_ledger.get('total_unresolved_reserve_usd', 0.0)) + reserved_est_usd:.4f} > {dev_hard_cap_usd:.4f}"
            )

        attempt = 0
        queue = list(pending_entries)
        initial_count = len(pending_entries)
        retry_count_total = 0

        while queue:
            attempt += 1
            batch_label = f"canary-attempt-{attempt}"
            q_cids = [e["custom_id"] for e in queue]
            intent_key = sha256_bytes(
                json.dumps(
                    {"provider": rate_profile.provider, "attempt": attempt, "cids": q_cids},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            spend_ledger.setdefault("pending_submit_intents", {})[intent_key] = {
                "intent_key": intent_key,
                "provider": rate_profile.provider,
                "attempt": attempt,
                "status": "INTENT_PRE_SUBMIT",
                "submitted_custom_ids": q_cids,
                "reserved_worst_case_usd": round(reserved_est_usd, 6),
                "batch_id": None,
            }
            _recompute_ledger_totals(spend_ledger)
            _save_spend_ledger_atomic(spend_ledger_path, spend_ledger)

            sub = transport.submit_batch([e["wire_item"] for e in queue], batch_label=batch_label)
            batch_id = str(sub["batch_id"])
            input_file_id = sub.get("input_file_id")
            if batch_id in spend_ledger["batches"]:
                raise RuntimeError(f"IDEMPOTENCY_DUPLICATE_BATCH_ID:{batch_id}")

            spend_ledger["pending_submit_intents"][intent_key]["status"] = "DISPATCHED_LINKED"
            spend_ledger["pending_submit_intents"][intent_key]["batch_id"] = batch_id
            spend_ledger["batches"][batch_id] = {
                "batch_id": batch_id,
                "intent_key": intent_key,
                "attempt": attempt,
                "status": "DISPATCHED",
                "submitted_custom_ids": q_cids,
                "input_file_id": input_file_id,
                "output_file_id": None,
                "reserved_worst_case_usd": round(reserved_est_usd, 6),
                "billed_item_costs": {},
                "extra_batch_billing_usd": 0.0,
                "batch_total_billed_usd": 0.0,
                "settled_custom_ids": [],
                "cleanup_status": "PENDING",
                "cleanup_receipt": None,
                "cleanup_error": None,
                "error_code": None,
            }
            _recompute_ledger_totals(spend_ledger)
            _save_spend_ledger_atomic(spend_ledger_path, spend_ledger)
            dispatched_batches.append(batch_id)

            if _test_crash_hook == "hard_crash_after_submit":
                raise RuntimeError("SIMULATED_HARD_CRASH_AFTER_SUBMIT")

            output_file_id: str | None = None
            b_rec = spend_ledger["batches"][batch_id]
            try:
                res = transport.fetch_batch_results(batch_id)
                output_file_id = res.get("output_file_id")
                b_status = str(res.get("batch_status", "COMPLETED")).upper()

                # Commit ALL billable usage returned by provider BEFORE any validation exception
                cum_spent_usd = _meter_batch_response_into_ledger(
                    res=res,
                    batch_id=batch_id,
                    rate_profile=rate_profile,
                    ledger=spend_ledger,
                    spend_ledger_path=spend_ledger_path,
                )

                if _test_crash_hook == "after_billing_before_jsonl":
                    raise RuntimeError("SIMULATED_CRASH_AFTER_BILLING_BEFORE_JSONL")

                batch_snap = res.get("model_snapshot_id")
                if batch_snap != rate_profile.expected_snapshot_id:
                    b_rec["status"] = "PARTIAL_ERROR_SETTLED"
                    b_rec["error_code"] = "MODEL_SNAPSHOT_DRIFT_ABORT"
                    _save_spend_ledger_atomic(spend_ledger_path, spend_ledger)
                    raise PermissionError(
                        f"MODEL_SNAPSHOT_DRIFT_ABORT: expected={rate_profile.expected_snapshot_id!r}, got={batch_snap!r}"
                    )

                if b_status in ("FAILED", "CANCELLED", "EXPIRED"):
                    failed_batches_count += 1
                    spend_ledger["failed_batches"] = failed_batches_count
                    b_rec["status"] = f"{b_status}_SETTLED"
                    b_rec["error_code"] = f"BATCH_{b_status}:{batch_id}"
                    _recompute_ledger_totals(spend_ledger)
                    _save_spend_ledger_atomic(spend_ledger_path, spend_ledger)
                    if failed_batches_count > max_failed_batches:
                        raise PermissionError(
                            f"MAX_FAILED_BATCHES_EXCEEDED:{failed_batches_count}>{max_failed_batches}"
                        )
                    raise RuntimeError(f"BATCH_{b_status}:{batch_id}")

                if cum_spent_usd > dev_hard_cap_usd + 1e-12:
                    b_rec["status"] = "PARTIAL_ERROR_SETTLED"
                    b_rec["error_code"] = "DEV_BUDGET_ACTUAL_USAGE_CAP_EXCEEDED"
                    _save_spend_ledger_atomic(spend_ledger_path, spend_ledger)
                    raise PermissionError(
                        f"DEV_BUDGET_ACTUAL_USAGE_CAP_EXCEEDED: {cum_spent_usd:.6f} > {dev_hard_cap_usd:.4f}"
                    )

                by_cid = {str(item["custom_id"]): item for item in res.get("items", [])}
                next_retry_queue: list[dict[str, Any]] = []
                batch_settled_cids = list(b_rec.get("settled_custom_ids", []))

                for idx_in_q, entry in enumerate(queue):
                    cid = entry["custom_id"]
                    item_resp = by_cid.get(cid)
                    if item_resp is None:
                        b_rec["status"] = "PARTIAL_ERROR_SETTLED"
                        b_rec["error_code"] = f"MISSING_BATCH_ITEM_RESPONSE:{cid}"
                        _save_spend_ledger_atomic(spend_ledger_path, spend_ledger)
                        raise RuntimeError(f"MISSING_BATCH_ITEM_RESPONSE:{cid}")
                    if item_resp.get("model_snapshot_id") != rate_profile.expected_snapshot_id:
                        b_rec["status"] = "PARTIAL_ERROR_SETTLED"
                        b_rec["error_code"] = f"ITEM_MODEL_SNAPSHOT_DRIFT_ABORT:{cid}"
                        _save_spend_ledger_atomic(spend_ledger_path, spend_ledger)
                        raise PermissionError(f"ITEM_MODEL_SNAPSHOT_DRIFT_ABORT on {cid}")

                    usage = item_resp["usage"]
                    item_cost = float(b_rec["billed_item_costs"][cid]["cost_usd"])
                    raw_payload = item_resp.get("parsed_response", {})
                    local_verdict = project_cloud_quote_locally_to_canonical_s(
                        cloud_response=raw_payload if isinstance(raw_payload, Mapping) else {},
                        safe_doc_v=entry["safe_wire"]["safe_doc_v"],
                        safe_to_v_segments=entry["safe_wire"]["safe_to_v_segments"],
                        doc_sanitized_V=str(entry["input_row"]["sanitized_text_V"]),
                        doc_canonical_S=str(entry["input_row"]["doc_canonical_S"]),
                        doc_v_to_s_segments=entry["input_row"]["doc_v_to_s_segments"],
                        doc_removed_r_audit=entry["input_row"]["doc_removed_r_audit"],
                        doc_meta=entry["input_row"]["doc_meta"],
                        query_meta=entry["input_row"]["query_meta"],
                    )
                    needs_retry = local_verdict["state"] == "ERROR" and attempt <= max_schema_retries_per_item
                    if needs_retry:
                        retry_count_total += 1
                        if retry_count_total / float(initial_count) > max_batch_retry_fraction + 1e-12:
                            b_rec["status"] = "PARTIAL_ERROR_SETTLED"
                            b_rec["error_code"] = "BATCH_RETRY_FRACTION_EXCEEDED"
                            _save_spend_ledger_atomic(spend_ledger_path, spend_ledger)
                            _append_jsonl_durable(
                                raw_log_jsonl_path,
                                {
                                    "batch_id": batch_id,
                                    "custom_id": cid,
                                    "attempt": attempt,
                                    "model_snapshot_id": rate_profile.expected_snapshot_id,
                                    "usage": dict(usage),
                                    "cost_usd": item_cost,
                                    "local_validation": local_verdict,
                                    "final_for_item": False,
                                    "halted": "BATCH_RETRY_FRACTION_EXCEEDED",
                                },
                            )
                            raise PermissionError(
                                f"BATCH_RETRY_FRACTION_EXCEEDED:{retry_count_total}/{initial_count}>{max_batch_retry_fraction}"
                            )
                        next_retry_queue.append(entry)
                        log_final = False
                    else:
                        log_final = True

                    log_record = {
                        "batch_id": batch_id,
                        "custom_id": cid,
                        "attempt": attempt,
                        "model_snapshot_id": rate_profile.expected_snapshot_id,
                        "usage": dict(usage),
                        "cost_usd": item_cost,
                        "wire_payload_sha256": entry["safe_wire"]["wire_payload_sha256"],
                        "cloud_raw_response": raw_payload,
                        "local_validation": local_verdict,
                        "final_for_item": log_final,
                    }
                    _append_jsonl_durable(raw_log_jsonl_path, log_record)
                    logged_pair_keys.add((batch_id, cid))
                    if log_final:
                        settled_items[cid] = log_record
                        if cid not in batch_settled_cids:
                            batch_settled_cids.append(cid)

                    if _test_crash_hook == "after_first_item_jsonl" and idx_in_q == 0:
                        raise RuntimeError("SIMULATED_CRASH_AFTER_FIRST_ITEM_JSONL")

                b_rec["settled_custom_ids"] = batch_settled_cids
                b_rec["status"] = "SETTLED"
                _recompute_ledger_totals(spend_ledger)
                _save_spend_ledger_atomic(spend_ledger_path, spend_ledger)
                queue = next_retry_queue
            finally:
                cleanup_receipts.append(
                    _cleanup_batch_and_files(
                        transport=transport,
                        batch_id=batch_id,
                        input_file_id=input_file_id,
                        output_file_id=output_file_id,
                        ledger=spend_ledger,
                        spend_ledger_path=spend_ledger_path,
                    )
                )

    final_total_usd = _recompute_ledger_totals(spend_ledger)
    return {
        "schema_version": "GOMATE_W07_ROUTE2_STAGE1_MOCK_CANARY_RUN_V2",
        "execution_mode": "OFFLINE_MOCK_OR_RECORD_REPLAY_ONLY",
        "live_network_calls_executed": 0,
        "provider": rate_profile.provider,
        "model_snapshot_id_pinned": rate_profile.expected_snapshot_id,
        "od_ae_05_retention_accepted_by_receipt": True,
        "settled_count": len(settled_items),
        "skipped_resumed_count": len(skipped_resumed),
        "dispatched_batches": dispatched_batches,
        "total_spent_usd": round(final_total_usd, 8),
        "dev_hard_cap_usd": dev_hard_cap_usd,
        "token_metering": token_meter_report,
        "cleanup_receipts": cleanup_receipts,
        "raw_log_jsonl_sha256": hashlib.sha256(raw_log_jsonl_path.read_bytes()).hexdigest()
        if raw_log_jsonl_path.is_file()
        else None,
    }
