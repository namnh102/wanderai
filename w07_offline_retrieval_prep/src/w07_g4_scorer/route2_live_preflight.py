"""Two-phase PRE_PREFLIGHT -> STAGE1_LIVE gates, out-of-band root verification, and aggregate P1-C dispatch/budget ledger."""

from __future__ import annotations

import json
import math
import os
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from w07_g4_scorer.contracts import sha256_bytes
from w07_g4_scorer.route2_aiproxy import (
    assert_cloud_payload_v_boundary,
    build_sanitized_v_cloud_request_payload,
    validate_route2_live_activation_entrypoint,
)
from w07_g4_scorer.route2_dev_canary_runner import (
    ANTHROPIC_100K_CLIFF_TOKENS,
    DEFAULT_DEV_CANARY_HARD_CAP_USD,
    MAX_STAGE1_CANARY_QUERIES,
    ProviderRateProfile,
    _meter_usage_usd,
)

PA1_TOTAL_HARD_CAP_USD = 20.00
PA1_DEV_HARD_CAP_USD = 2.00
AGGREGATE_LIVE_LEDGER_SCHEMA = "GOMATE_W07_STAGE1_AGGREGATE_LIVE_LEDGER_V1"

NONTERMINAL_BATCH_STATUSES: frozenset[str] = frozenset(
    {
        "CREATED",
        "PENDING",
        "QUEUED",
        "VALIDATING",
        "IN_PROGRESS",
        "PROCESSING",
        "FINALIZING",
        "CANCELLING",
        "CANCELING",
        "RUNNING",
        "UNKNOWN",
    }
)
TERMINAL_BATCH_STATUSES: frozenset[str] = frozenset({"COMPLETED", "ENDED", "FAILED", "CANCELLED", "EXPIRED"})

_PATH_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, threading.RLock] = {}

REQUIRED_CREDENTIAL_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
}

LIVE_PREFLIGHT_ENDPOINTS: dict[str, dict[str, str]] = {
    "openai": {
        "models": "GET /v1/models",
        "count_tokens": "POST /v1/responses/input_tokens",
        "batch": "POST /v1/batches",
    },
    "anthropic": {
        "models": "GET /v1/models",
        "count_tokens": "POST /v1/messages/count_tokens",
        "batch": "POST /v1/messages/batches",
    },
    "google": {
        "models": "GET /v1beta/models",
        "count_tokens": "models.countTokens",
        "batch": "batchGenerateContent",
    },
}


class LivePreflightProbeClientProtocol(Protocol):
    """Read-only zero-generation model/token probe interface (batch submission strictly excluded)."""

    def probe_model_snapshot(self, *, provider: str, model_id: str) -> dict[str, Any]:
        ...

    def probe_input_tokens(self, *, provider: str, wire_request: Mapping[str, Any]) -> dict[str, Any]:
        ...


class LiveBatchReconcileProtocol(Protocol):
    """Reconciliation protocol for future live adapters supporting idempotency-key recovery & cleanup."""

    def lookup_batch_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any]:
        ...

    def fetch_batch_outcome(self, batch_id: str) -> dict[str, Any]:
        ...

    def delete_batch(self, batch_id: str) -> dict[str, Any]:
        ...

    def delete_file(self, file_id: str) -> dict[str, Any]:
        ...


def inspect_provider_credentials_readonly() -> dict[str, dict[str, Any]]:
    """Inspect presence of provider API key env vars WITHOUT ever exposing secret values."""
    out: dict[str, dict[str, Any]] = {}
    for provider, env_name in sorted(REQUIRED_CREDENTIAL_ENV_VARS.items()):
        raw = os.environ.get(env_name)
        present = bool(raw and raw.strip())
        out[provider] = {
            "env_var": env_name,
            "configured": present,
            "status": "CONFIGURED_UNVERIFIED_LIVE" if present else "UNSET_IN_ENVIRONMENT",
        }
    return out


def build_live_count_tokens_wire_request(
    *,
    provider: str,
    model_id: str,
    packet_item_uuid: str,
    query_meta: Mapping[str, Any],
    sanitized_text_V: str,
    run_nonce: str,
    system_prompt: str,
    response_schema: Mapping[str, Any],
    doc_record_for_leak_check: Mapping[str, Any],
    prompt_order: str = "PROMPT_ORDER_CANONICAL",
) -> dict[str, Any]:
    """Build zero-generation count_tokens payload strictly over sanitized Tier-T1 V with non-null leak check."""
    if doc_record_for_leak_check is None or not isinstance(doc_record_for_leak_check, Mapping):
        raise ValueError("NON_NULL_DOC_RECORD_REQUIRED_FOR_FIREWALL")
    qid = str(query_meta.get("query_id", ""))
    if query_meta.get("split") != "DEV" or "FINAL" in qid.upper():
        raise PermissionError(f"STAGE1_PREFLIGHT_FINAL_CONTAMINATION_BLOCKED:{qid!r}")

    safe_wire = build_sanitized_v_cloud_request_payload(
        packet_item_uuid=packet_item_uuid,
        query_text=str(query_meta["query_text"]),
        sanitized_text_V=sanitized_text_V,
        run_nonce=run_nonce,
        prompt_order=prompt_order,
        doc_record_for_leak_check=doc_record_for_leak_check,
    )
    user_txt = safe_wire["wire_user_prompt"]

    if provider == "openai":
        req = {
            "model": model_id,
            "input": [
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": user_txt},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "w07_judge_s4",
                    "strict": True,
                    "schema": dict(response_schema),
                }
            },
        }
    elif provider == "anthropic":
        req = {
            "model": model_id,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_txt}],
            "output_config": {
                "effort": "low",
                "format": {"type": "json_schema", "schema": dict(response_schema)},
            },
        }
    elif provider == "google":
        req = {
            "model": f"models/{model_id}",
            "contents": [{"role": "user", "parts": [{"text": user_txt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
        }
    else:
        raise ValueError(f"Unsupported preflight provider: {provider!r}")

    assert_cloud_payload_v_boundary(req, doc_record_for_leak_check=doc_record_for_leak_check)
    return req


def verify_live_account_preflight_prerequisites(
    *,
    activation_pack_dir: Path,
    external_trust_root_dir: Path,
    out_of_band_owner_pubkey_sha256: str | None = None,
    out_of_band_auditor_pubkey_sha256: str | None = None,
    out_of_band_manifest_sha256: str | None = None,
    out_of_band_auditor_report_sha256: str | None = None,
    allow_live_network: bool = False,
    required_providers: Sequence[str] = ("openai", "anthropic"),
    requested_dev_cap_usd: float = PA1_DEV_HARD_CAP_USD,
    requested_total_cap_usd: float = PA1_TOTAL_HARD_CAP_USD,
) -> dict[str, Any]:
    """Phase-1 PRE_PREFLIGHT gate: permits ONLY read-only model/token probes; NEVER permits batch generation."""
    if not allow_live_network:
        raise PermissionError("HOLD_LIVE_PREFLIGHT_REQUIRES_EXPLICIT_ALLOW_LIVE_NETWORK")
    if requested_dev_cap_usd > DEFAULT_DEV_CANARY_HARD_CAP_USD:
        raise PermissionError("HOLD_DEV_CAP_CANNOT_EXCEED_2_USD")

    auth = validate_route2_live_activation_entrypoint(
        activation_pack_dir=activation_pack_dir,
        external_trust_root_dir=external_trust_root_dir,
        gate_phase="PRE_PREFLIGHT_PROBE_ONLY",
        out_of_band_owner_pubkey_sha256=out_of_band_owner_pubkey_sha256,
        out_of_band_auditor_pubkey_sha256=out_of_band_auditor_pubkey_sha256,
        out_of_band_manifest_sha256=out_of_band_manifest_sha256,
        out_of_band_auditor_report_sha256=out_of_band_auditor_report_sha256,
    )
    cap_regime = auth["selected_cap_regime"]
    if cap_regime == "UNAMENDED_20USD" and requested_total_cap_usd > PA1_TOTAL_HARD_CAP_USD:
        raise PermissionError("HOLD_PA1_CAP_EXCEEDS_20_USD_WITHOUT_SIGNED_BUDGET40")

    creds = inspect_provider_credentials_readonly()
    missing = [p for p in required_providers if not creds.get(p, {}).get("configured", False)]
    if missing:
        raise PermissionError(f"HOLD_PROVIDER_API_CREDENTIALS_UNSET:{','.join(missing)}")

    return {
        "gate_phase": "PRE_PREFLIGHT_PROBE_ONLY",
        "preflight_probes_authorized": auth["preflight_probes_authorized"],
        "batch_generation_authorized": False,
        "selected_cap_regime": cap_regime,
        "dev_hard_cap_usd": requested_dev_cap_usd,
        "total_hard_cap_usd": requested_total_cap_usd,
        "authorized_stage": auth["cryptographic_verification"]["authorized_stage"],
        "credentials_status": creds,
    }


def run_authorized_provider_preflight_probes(
    *,
    activation_pack_dir: Path,
    external_trust_root_dir: Path,
    probe_client: LivePreflightProbeClientProtocol,
    rate_profiles: Sequence[ProviderRateProfile],
    canary_items: Sequence[Mapping[str, Any]],
    system_prompt: str,
    response_schema: Mapping[str, Any],
    out_of_band_owner_pubkey_sha256: str | None = None,
    out_of_band_auditor_pubkey_sha256: str | None = None,
    out_of_band_manifest_sha256: str | None = None,
    out_of_band_auditor_report_sha256: str | None = None,
    raw_probe_transcript_path: Path | None = None,
    allow_live_network: bool = False,
) -> dict[str, Any]:
    """Run read-only model/token probes under Phase-1 PRE_PREFLIGHT gate and emit signed-ready transcript SHA."""
    if hasattr(probe_client, "submit_batch") or getattr(probe_client, "can_submit_billable_batches", False):
        raise PermissionError("PREFLIGHT_FORBIDS_BILLABLE_BATCH_GENERATION_CLIENT")

    prereq = verify_live_account_preflight_prerequisites(
        activation_pack_dir=activation_pack_dir,
        external_trust_root_dir=external_trust_root_dir,
        out_of_band_owner_pubkey_sha256=out_of_band_owner_pubkey_sha256,
        out_of_band_auditor_pubkey_sha256=out_of_band_auditor_pubkey_sha256,
        out_of_band_manifest_sha256=out_of_band_manifest_sha256,
        out_of_band_auditor_report_sha256=out_of_band_auditor_report_sha256,
        allow_live_network=allow_live_network,
        required_providers=tuple(sorted({rp.provider for rp in rate_profiles})),
    )

    qids = {str(item["query_meta"]["query_id"]) for item in canary_items}
    if not qids or len(qids) > MAX_STAGE1_CANARY_QUERIES:
        raise PermissionError(f"STAGE1_PREFLIGHT_QUERY_QUOTA_EXCEEDED:{len(qids)}")

    provider_reports: dict[str, Any] = {}
    judge_snapshots: dict[str, str] = {}
    projected_total_dev_usd = 0.0
    max_tokens_seen = 0
    probe_events: list[dict[str, Any]] = []

    for rp in rate_profiles:
        snap_info = probe_client.probe_model_snapshot(provider=rp.provider, model_id=rp.model_id)
        observed_snap = str(snap_info.get("model_snapshot_id", ""))
        if not observed_snap or observed_snap != rp.expected_snapshot_id:
            raise PermissionError(
                f"PREFLIGHT_SNAPSHOT_MISMATCH:{rp.provider}:expected={rp.expected_snapshot_id!r}:got={observed_snap!r}"
            )
        if snap_info.get("accessible") is not True:
            raise PermissionError(f"PREFLIGHT_MODEL_NOT_ACCESSIBLE:{rp.provider}:{rp.model_id}")

        item_tokens: list[int] = []
        item_wire_hashes: list[str] = []
        for row in canary_items:
            wire_req = build_live_count_tokens_wire_request(
                provider=rp.provider,
                model_id=rp.model_id,
                packet_item_uuid=str(row["packet_item_uuid"]),
                query_meta=row["query_meta"],
                sanitized_text_V=str(row["sanitized_text_V"]),
                run_nonce=str(row["run_nonce"]),
                system_prompt=system_prompt,
                response_schema=response_schema,
                doc_record_for_leak_check=row["doc_record_for_leak_check"],
                prompt_order=str(row.get("prompt_order", "PROMPT_ORDER_CANONICAL")),
            )
            w_sha = sha256_bytes(json.dumps(wire_req, sort_keys=True, ensure_ascii=False).encode("utf-8"))
            tok_res = probe_client.probe_input_tokens(provider=rp.provider, wire_request=wire_req)
            cnt = tok_res.get("input_tokens")
            if type(cnt) is not int or cnt <= 0:
                raise ValueError(f"PREFLIGHT_INVALID_INPUT_TOKEN_COUNT:{cnt!r}")
            item_tokens.append(cnt)
            item_wire_hashes.append(w_sha)
            probe_events.append(
                {
                    "provider": rp.provider,
                    "model_snapshot_id": observed_snap,
                    "packet_item_uuid": str(row["packet_item_uuid"]),
                    "wire_request_sha256": w_sha,
                    "measured_input_tokens": cnt,
                }
            )

        prov_max = max(item_tokens)
        max_tokens_seen = max(max_tokens_seen, prov_max)
        if prov_max >= ANTHROPIC_100K_CLIFF_TOKENS:
            raise PermissionError(f"PREFLIGHT_100K_CLIFF_EXCEEDED:{rp.provider}:{prov_max}")

        in_sum = sum(item_tokens)
        est_out = len(item_tokens) * 1024
        worst_usd = (in_sum * rp.batch_input_usd_per_1m / 1_000_000.0) + (
            est_out * rp.batch_output_usd_per_1m / 1_000_000.0
        )
        projected_total_dev_usd += worst_usd
        role_key = "judge_A" if rp.provider == "openai" else ("judge_B" if rp.provider == "anthropic" else rp.provider)
        judge_snapshots[role_key] = observed_snap
        provider_reports[rp.provider] = {
            "model_id": rp.model_id,
            "model_snapshot_id": observed_snap,
            "measured_item_count": len(item_tokens),
            "total_input_tokens": in_sum,
            "max_item_input_tokens": prov_max,
            "below_100k_cliff": prov_max < ANTHROPIC_100K_CLIFF_TOKENS,
            "worst_case_stage1_usd": round(worst_usd, 6),
            "wire_requests_sha256": item_wire_hashes,
            "tokens_sha256": sha256_bytes(json.dumps(item_tokens).encode("utf-8")),
        }

    if projected_total_dev_usd > PA1_DEV_HARD_CAP_USD:
        raise PermissionError(
            f"PREFLIGHT_STAGE1_PROJECTED_COST_EXCEEDS_2_USD:{projected_total_dev_usd:.6f}"
        )

    raw_transcript = {
        "schema_version": "GOMATE_W07_ROUTE2_RAW_PROBE_TRANSCRIPT_V1",
        "max_item_tokens_measured": max_tokens_seen,
        "projected_stage1_worst_case_usd": round(projected_total_dev_usd, 6),
        "live_account_rates_verified": False,
        "account_pricing_status": "UNVERIFIED_CALLER_ESTIMATE_ONLY",
        "judge_snapshots": judge_snapshots,
        "providers": provider_reports,
        "events": probe_events,
    }
    raw_bytes = (json.dumps(raw_transcript, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    transcript_sha = sha256_bytes(raw_bytes)
    if raw_probe_transcript_path is not None:
        raw_probe_transcript_path.parent.mkdir(parents=True, exist_ok=True)
        raw_probe_transcript_path.write_bytes(raw_bytes)

    return {
        "schema_version": "GOMATE_W07_ROUTE2_LIVE_PREFLIGHT_REPORT_V2",
        "prerequisites": prereq,
        "batch_generation_authorized": False,
        "max_item_tokens_measured": max_tokens_seen,
        "projected_stage1_worst_case_usd": round(projected_total_dev_usd, 6),
        "fits_dev_2usd_cap": projected_total_dev_usd <= PA1_DEV_HARD_CAP_USD,
        "live_account_rates_verified": False,
        "account_pricing_status": "UNVERIFIED_CALLER_ESTIMATE_ONLY",
        "judge_snapshots": judge_snapshots,
        "raw_probe_transcript_sha256": transcript_sha,
        "providers": provider_reports,
    }


def authorize_stage1_live_canary_gate(
    *,
    activation_pack_dir: Path,
    external_trust_root_dir: Path,
    out_of_band_owner_pubkey_sha256: str | None = None,
    out_of_band_auditor_pubkey_sha256: str | None = None,
    out_of_band_manifest_sha256: str | None = None,
    out_of_band_auditor_report_sha256: str | None = None,
    expected_target_zip_sha256: str | None = None,
    raw_probe_transcript_path: Path | None = None,
    requested_dev_cap_usd: float = PA1_DEV_HARD_CAP_USD,
    requested_total_cap_usd: float = PA1_TOTAL_HARD_CAP_USD,
) -> dict[str, Any]:
    """Phase-2 STAGE1_LIVE gate: opens ONLY after attested probe transcript SHA + STAGE1_DEV_CANARY_ONLY Owner sig."""
    if requested_dev_cap_usd > PA1_DEV_HARD_CAP_USD:
        raise PermissionError("HOLD_DEV_CAP_CANNOT_EXCEED_2_USD")
    auth = validate_route2_live_activation_entrypoint(
        activation_pack_dir=activation_pack_dir,
        external_trust_root_dir=external_trust_root_dir,
        gate_phase="STAGE1_LIVE",
        out_of_band_owner_pubkey_sha256=out_of_band_owner_pubkey_sha256,
        out_of_band_auditor_pubkey_sha256=out_of_band_auditor_pubkey_sha256,
        out_of_band_manifest_sha256=out_of_band_manifest_sha256,
        out_of_band_auditor_report_sha256=out_of_band_auditor_report_sha256,
        expected_target_zip_sha256=expected_target_zip_sha256,
    )
    if auth["selected_cap_regime"] == "UNAMENDED_20USD" and requested_total_cap_usd > PA1_TOTAL_HARD_CAP_USD:
        raise PermissionError("HOLD_PA1_CAP_EXCEEDS_20_USD_WITHOUT_SIGNED_BUDGET40")
    if raw_probe_transcript_path is not None:
        if not raw_probe_transcript_path.is_file():
            raise PermissionError(f"MISSING_RAW_PROBE_TRANSCRIPT_FILE:{raw_probe_transcript_path}")
        pf = json.loads((activation_pack_dir / "receipts" / "provider_preflight_receipt.json").read_text(encoding="utf-8"))
        actual_t_sha = sha256_bytes(raw_probe_transcript_path.read_bytes())
        if actual_t_sha != pf.get("raw_probe_transcript_sha256"):
            raise PermissionError("RAW_PROBE_TRANSCRIPT_SHA256_MISMATCH")
    return {
        "gate_phase": "STAGE1_LIVE",
        "batch_generation_authorized": True,
        "selected_cap_regime": auth["selected_cap_regime"],
        "dev_hard_cap_usd": requested_dev_cap_usd,
        "total_hard_cap_usd": requested_total_cap_usd,
        "judge_snapshots_pinned": auth["cryptographic_verification"]["judge_snapshots_pinned"],
    }


@contextmanager
def _aggregate_ledger_lock(ledger_path: Path) -> Iterator[None]:
    """Single-writer serialization across threads (RLock) and OS processes (msvcrt/fcntl) via sidecar lock file."""
    key = str(ledger_path.resolve())
    with _PATH_LOCKS_GUARD:
        tlock = _PATH_LOCKS.setdefault(key, threading.RLock())
    lock_file = ledger_path.with_name(f"{ledger_path.name}.lock")
    with tlock:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        with lock_file.open("a+b") as fh:
            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                fh.write(b"\x00")
                fh.flush()
            if os.name == "nt":
                # Windows LK_NBLCK bounded retry loop across processes
                for attempt in range(300):
                    try:
                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        if attempt == 299:
                            raise
                        time.sleep(0.01)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _save_aggregate_ledger_atomic(path: Path, ledger: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_p = path.with_suffix(".json.tmp")
    raw = (json.dumps(dict(ledger), indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    with tmp_p.open("wb") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_p, path)


def _recompute_aggregate_ledger(ledger: dict[str, Any]) -> dict[str, float]:
    intents: dict[str, dict[str, Any]] = ledger.setdefault("intents", {})
    confirmed = 0.0
    reserved = 0.0
    per_provider: dict[str, float] = {}
    for rec in intents.values():
        prov = str(rec.get("provider", "unknown"))
        c_usd = float(rec.get("confirmed_cost_usd", 0.0))
        r_usd = float(rec.get("unresolved_reserve_usd", 0.0))
        confirmed += c_usd
        reserved += r_usd
        per_provider[prov] = round(per_provider.get(prov, 0.0) + c_usd + r_usd, 8)
    confirmed_r = round(confirmed, 8)
    reserved_r = round(reserved, 8)
    effective_r = round(confirmed_r + reserved_r, 8)
    ledger["total_confirmed_spent_usd"] = confirmed_r
    ledger["total_unresolved_reserve_usd"] = reserved_r
    ledger["effective_committed_usd"] = effective_r
    ledger["providers_committed_usd"] = per_provider
    return {
        "total_confirmed_spent_usd": confirmed_r,
        "total_unresolved_reserve_usd": reserved_r,
        "effective_committed_usd": effective_r,
    }


def _load_or_init_aggregate_stage1_ledger_unlocked(
    ledger_path: Path,
    *,
    dev_hard_cap_usd: float = PA1_DEV_HARD_CAP_USD,
    total_hard_cap_usd: float = PA1_TOTAL_HARD_CAP_USD,
) -> dict[str, Any]:
    if dev_hard_cap_usd > PA1_DEV_HARD_CAP_USD or total_hard_cap_usd < dev_hard_cap_usd:
        raise PermissionError("INVALID_AGGREGATE_STAGE1_BUDGET_BOUNDS")
    if ledger_path.is_file():
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
        if type(data) is not dict or data.get("schema_version") != AGGREGATE_LIVE_LEDGER_SCHEMA:
            raise ValueError("INVALID_AGGREGATE_LIVE_LEDGER_SCHEMA")
        data.setdefault("intents", {})
        data.setdefault("cleanup_failures", [])
    else:
        data = {
            "schema_version": AGGREGATE_LIVE_LEDGER_SCHEMA,
            "dev_hard_cap_usd": dev_hard_cap_usd,
            "total_hard_cap_usd": total_hard_cap_usd,
            "total_confirmed_spent_usd": 0.0,
            "total_unresolved_reserve_usd": 0.0,
            "effective_committed_usd": 0.0,
            "providers_committed_usd": {},
            "intents": {},
            "cleanup_failures": [],
        }
        _save_aggregate_ledger_atomic(ledger_path, data)
    _recompute_aggregate_ledger(data)
    return data


def load_or_init_aggregate_stage1_ledger(
    ledger_path: Path,
    *,
    dev_hard_cap_usd: float = PA1_DEV_HARD_CAP_USD,
    total_hard_cap_usd: float = PA1_TOTAL_HARD_CAP_USD,
) -> dict[str, Any]:
    """Load persistent cross-provider aggregate DEV spend ledger under single-writer serialization."""
    with _aggregate_ledger_lock(ledger_path):
        return _load_or_init_aggregate_stage1_ledger_unlocked(
            ledger_path, dev_hard_cap_usd=dev_hard_cap_usd, total_hard_cap_usd=total_hard_cap_usd
        )


def prepare_stage1_pre_submit_intent(
    *,
    ledger_path: Path,
    run_id: str,
    rate_profile: ProviderRateProfile,
    custom_ids: Sequence[str],
    batch_reserved_worst_case_usd: float,
    dev_hard_cap_usd: float = PA1_DEV_HARD_CAP_USD,
    total_hard_cap_usd: float = PA1_TOTAL_HARD_CAP_USD,
) -> dict[str, Any]:
    """P1-C: Atomically write durable PRE_SUBMIT intent + reserve across ALL providers BEFORE submit_batch()."""
    if (
        isinstance(batch_reserved_worst_case_usd, bool)
        or not math.isfinite(batch_reserved_worst_case_usd)
        or batch_reserved_worst_case_usd < 0.0
    ):
        raise ValueError("INVALID_RESERVED_WORST_CASE_USD")
    if not custom_ids:
        raise ValueError("PRE_SUBMIT_INTENT_REQUIRES_NON_EMPTY_CUSTOM_IDS")

    idemp_key = sha256_bytes(
        json.dumps(
            {
                "run_id": run_id,
                "provider": rate_profile.provider,
                "snapshot": rate_profile.expected_snapshot_id,
                "custom_ids": sorted(set(str(c) for c in custom_ids)),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )

    with _aggregate_ledger_lock(ledger_path):
        ledger = _load_or_init_aggregate_stage1_ledger_unlocked(
            ledger_path, dev_hard_cap_usd=dev_hard_cap_usd, total_hard_cap_usd=total_hard_cap_usd
        )
        if idemp_key in ledger["intents"]:
            existing = ledger["intents"][idemp_key]
            raise RuntimeError(f"DUPLICATE_IDEMPOTENCY_KEY_REQUIRES_RECONCILIATION:{idemp_key}:status={existing['status']}")

        totals = _recompute_aggregate_ledger(ledger)
        projected = round(totals["effective_committed_usd"] + float(batch_reserved_worst_case_usd), 8)
        cap_dev = float(ledger["dev_hard_cap_usd"])
        cap_tot = float(ledger["total_hard_cap_usd"])
        if projected > cap_dev + 1e-12:
            raise PermissionError(
                f"STAGE1_AGGREGATE_DEV_CAP_EXCEEDED: committed={totals['effective_committed_usd']:.6f} + reserve={batch_reserved_worst_case_usd:.6f} > {cap_dev:.2f}"
            )
        if projected > cap_tot + 1e-12:
            raise PermissionError(f"STAGE1_AGGREGATE_TOTAL_CAP_EXCEEDED:{projected:.6f}>{cap_tot:.2f}")

        rec = {
            "client_idempotency_key": idemp_key,
            "run_id": run_id,
            "provider": rate_profile.provider,
            "model_snapshot_id": rate_profile.expected_snapshot_id,
            "status": "INTENT_PRE_SUBMIT",
            "batch_id": None,
            "submitted_custom_ids": sorted(str(c) for c in custom_ids),
            "reserved_worst_case_usd": round(float(batch_reserved_worst_case_usd), 8),
            "confirmed_cost_usd": 0.0,
            "unresolved_reserve_usd": round(float(batch_reserved_worst_case_usd), 8),
            "missing_usage_fallback_used": False,
            "cleanup_status": "NOT_STARTED",
            "cleanup_error": None,
        }
        ledger["intents"][idemp_key] = rec
        _recompute_aggregate_ledger(ledger)
        _save_aggregate_ledger_atomic(ledger_path, ledger)
        return dict(rec)


def link_stage1_dispatched_batch(
    *,
    ledger_path: Path,
    client_idempotency_key: str,
    batch_id: str,
    input_file_id: str | None = None,
) -> dict[str, Any]:
    """Bind provider batch_id to an existing durable PRE_SUBMIT intent atomically under single-writer lock."""
    with _aggregate_ledger_lock(ledger_path):
        ledger = _load_or_init_aggregate_stage1_ledger_unlocked(ledger_path)
        if client_idempotency_key not in ledger["intents"]:
            raise KeyError(f"UNKNOWN_PRE_SUBMIT_INTENT:{client_idempotency_key}")
        rec = ledger["intents"][client_idempotency_key]
        if rec["status"] not in ("INTENT_PRE_SUBMIT", "DISPATCHED"):
            raise RuntimeError(f"CANNOT_LINK_SETTLED_INTENT:{rec['status']}")
        rec["status"] = "DISPATCHED"
        rec["batch_id"] = batch_id
        rec["input_file_id"] = input_file_id
        rec["cleanup_status"] = "PENDING"
        _recompute_aggregate_ledger(ledger)
        _save_aggregate_ledger_atomic(ledger_path, ledger)
        return dict(rec)


def _settle_intent_from_outcome(
    *,
    ledger: dict[str, Any],
    rec: dict[str, Any],
    outcome: Mapping[str, Any],
    rate_profile: ProviderRateProfile,
    reconciler: LiveBatchReconcileProtocol,
    ledger_path: Path,
) -> None:
    b_status = str(outcome.get("batch_status", "UNKNOWN")).strip().upper()
    bid = str(rec.get("batch_id") or outcome.get("batch_id") or "")
    out_fid = outcome.get("output_file_id")
    in_fid = rec.get("input_file_id")
    raw_items = outcome.get("items", [])

    # Fail-closed guard #2: non-terminal or unrecognized statuses NEVER settle to $0 and NEVER trigger cleanup.
    if b_status in NONTERMINAL_BATCH_STATUSES or b_status not in TERMINAL_BATCH_STATUSES:
        rec["status"] = f"NONTERMINAL_RESERVED_{b_status}"
        rec["confirmed_cost_usd"] = 0.0
        rec["unresolved_reserve_usd"] = round(float(rec["reserved_worst_case_usd"]), 8)
        rec["missing_usage_fallback_used"] = False
        rec["cleanup_status"] = "DEFERRED_NONTERMINAL"
        _recompute_aggregate_ledger(ledger)
        _save_aggregate_ledger_atomic(ledger_path, ledger)
        return

    total_billed = 0.0
    missing_usage = False

    if not isinstance(raw_items, Sequence):
        missing_usage = True
    elif raw_items:
        for item in raw_items:
            usage_obj = item.get("usage") if isinstance(item, Mapping) else None
            if (
                not isinstance(usage_obj, Mapping)
                or "input_tokens" not in usage_obj
                or "output_tokens" not in usage_obj
            ):
                missing_usage = True
                break
            total_billed += _meter_usage_usd(usage_obj, rate_profile)
    elif "batch_billing_usage" in outcome:
        if outcome["batch_billing_usage"] is None:
            missing_usage = True
        else:
            total_billed += _meter_usage_usd(outcome["batch_billing_usage"], rate_profile)
    elif b_status in ("CANCELLED", "EXPIRED") and outcome.get("authoritatively_unbilled") is True and not outcome.get("billed", False):
        total_billed = 0.0
        missing_usage = False
    else:
        # Terminal status COMPLETED/ENDED/FAILED or unattested CANCELLED without usage breakdown -> reserve worst-case!
        missing_usage = True

    if missing_usage:
        fallback_usd = float(rec["reserved_worst_case_usd"])
        rec["confirmed_cost_usd"] = round(fallback_usd, 8)
        rec["unresolved_reserve_usd"] = 0.0
        rec["missing_usage_fallback_used"] = True
        rec["status"] = "SETTLED_MISSING_USAGE_WORST_CASE_RESERVED"
    else:
        rec["confirmed_cost_usd"] = round(total_billed, 8)
        rec["unresolved_reserve_usd"] = 0.0
        rec["missing_usage_fallback_used"] = False
        rec["status"] = "SETTLED" if b_status in ("COMPLETED", "ENDED") else f"SETTLED_{b_status}"

    _recompute_aggregate_ledger(ledger)
    _save_aggregate_ledger_atomic(ledger_path, ledger)

    if bid:
        cleanup_errs: list[str] = []
        try:
            db = reconciler.delete_batch(bid)
            if not db.get("deleted"):
                cleanup_errs.append(f"delete_batch({bid})=False")
        except Exception as exc:
            cleanup_errs.append(f"delete_batch({bid}):{exc}")
        for fid in (in_fid, out_fid):
            if isinstance(fid, str) and fid:
                try:
                    df = reconciler.delete_file(fid)
                    if not df.get("deleted"):
                        cleanup_errs.append(f"delete_file({fid})=False")
                except Exception as exc:
                    cleanup_errs.append(f"delete_file({fid}):{exc}")
        if cleanup_errs:
            rec["cleanup_status"] = "CLEANUP_FAILED"
            rec["cleanup_error"] = "; ".join(cleanup_errs)
            ledger["cleanup_failures"].append({"batch_id": bid, "errors": cleanup_errs})
            _save_aggregate_ledger_atomic(ledger_path, ledger)
            raise RuntimeError(f"LIVE_CLEANUP_INCOMPLETE:{bid}:{cleanup_errs[0]}")
        rec["cleanup_status"] = "COMPLETED"
        _save_aggregate_ledger_atomic(ledger_path, ledger)


def reconcile_stage1_crash_intents(
    *,
    ledger_path: Path,
    rate_profiles_by_provider: Mapping[str, ProviderRateProfile],
    reconciler: LiveBatchReconcileProtocol,
) -> dict[str, Any]:
    """Recover dangling/nonterminal intents fail-closed under single-writer lock; never drop reserves without proof."""
    with _aggregate_ledger_lock(ledger_path):
        ledger = _load_or_init_aggregate_stage1_ledger_unlocked(ledger_path)
        for idemp_key, rec in sorted(ledger.get("intents", {}).items()):
            st = str(rec.get("status", ""))
            if st not in ("INTENT_PRE_SUBMIT", "DISPATCHED", "UNRESOLVED_CRASH_RESERVED") and not st.startswith(
                "NONTERMINAL_RESERVED_"
            ):
                continue
            prov = str(rec["provider"])
            rp = rate_profiles_by_provider[prov]
            bid = rec.get("batch_id")

            if bid is None:
                try:
                    found = reconciler.lookup_batch_by_idempotency_key(idemp_key)
                except Exception as exc:
                    rec["status"] = "UNRESOLVED_CRASH_RESERVED"
                    rec["confirmed_cost_usd"] = 0.0
                    rec["unresolved_reserve_usd"] = round(float(rec["reserved_worst_case_usd"]), 8)
                    rec["reconcile_error"] = str(exc)
                    _recompute_aggregate_ledger(ledger)
                    _save_aggregate_ledger_atomic(ledger_path, ledger)
                    continue

                if not found.get("found"):
                    ev = found.get("non_acceptance_evidence")
                    has_ev = (isinstance(ev, str) and bool(ev.strip())) or (isinstance(ev, Mapping) and len(ev) > 0)
                    if found.get("authoritative_non_acceptance") is True and has_ev:
                        rec["status"] = "CANCELLED_UNSUBMITTED"
                        rec["confirmed_cost_usd"] = 0.0
                        rec["unresolved_reserve_usd"] = 0.0
                        rec["non_acceptance_evidence"] = ev
                    else:
                        # Fail-closed guard #1: single ambiguous lookup miss keeps full reserve!
                        rec["status"] = "UNRESOLVED_CRASH_RESERVED"
                        rec["confirmed_cost_usd"] = 0.0
                        rec["unresolved_reserve_usd"] = round(float(rec["reserved_worst_case_usd"]), 8)
                        rec["missing_lookup_count"] = int(rec.get("missing_lookup_count", 0)) + 1
                    _recompute_aggregate_ledger(ledger)
                    _save_aggregate_ledger_atomic(ledger_path, ledger)
                    continue

                bid = str(found["batch_id"])
                rec["batch_id"] = bid
                rec["status"] = "DISPATCHED"
                rec["cleanup_status"] = "PENDING"
                _recompute_aggregate_ledger(ledger)
                _save_aggregate_ledger_atomic(ledger_path, ledger)

            outcome = reconciler.fetch_batch_outcome(str(bid))
            _settle_intent_from_outcome(
                ledger=ledger,
                rec=rec,
                outcome=outcome,
                rate_profile=rp,
                reconciler=reconciler,
                ledger_path=ledger_path,
            )

        return _load_or_init_aggregate_stage1_ledger_unlocked(ledger_path)
