"""Live Stage-1 DEV5 dual-judge batch runner for OpenAI (/v1/batches) and Anthropic (/v1/messages/batches).

Zero-ML / pure-stdlib module enforcing every audited W07 Route 2 invariant:
1. Phase-2 cryptographic + external trust-root + rate-evidence gating BEFORE any network call;
2. Strict DEV5 quarantine filter (only approved W07-STAGE1-DEV-CAND-Q01/Q02/Q03/Q04/Q06 paired
   with the 137 Arm P documents verified against SHA-256 046424e5...; Q05, FINAL, FINAL-50 hard-blocked);
3. Strict S/V cloud boundary (sanitized V + escaped delimiter + Unicode email redaction outbound only;
   exact safe_doc_v -> V -> S coordinate projection and canonical S checks 100% local in Python);
4. P1-C durable pre-submit intent (INTENT_PRE_SUBMIT) persisted under single-writer aggregate lock
   BEFORE any HTTP POST to /v1/batches or /v1/messages/batches, preserving combined <= $2.00 DEV cap;
5. Durable fsync raw outcome persistence BEFORE remote delete_batch / delete_file cleanup, idempotent
   resume across non-terminal IN_PROGRESS runs or crashes, <= 1 retry / <= 15% batch circuit breaker,
   model snapshot & <100K long-context cliff enforcement, and zero secret echoing in logs or errors.
"""

from __future__ import annotations

import copy
import hashlib
import http.client
import inspect
import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from w07_g4_scorer.contracts import sha256_bytes
from w07_g4_scorer.judge_gates import (
    EXPECTED_V_CORPUS_SHA256,
    evaluate_budget_and_retry_circuit_breakers,
    evaluate_prompt_order_bias,
)
from w07_g4_scorer.query_manifest import validate_sealed_query_metadata
from w07_g4_scorer.route2_aiproxy import (
    PINNED_STAGE1_SYSTEM_PROMPT_V1_1_SHA256,
    _assert_not_symlink_or_reparse,
    _assert_path_outside_repositories,
    _no_duplicate_keys_object_pairs_hook,
    _project_half_open_interval,
    _reject_nonstandard_json_constant,
    assert_cloud_payload_v_boundary,
    build_sanitized_v_cloud_request_payload,
    project_cloud_quote_locally_to_canonical_s,
    verify_stage1_rate_evidence_artifact,
)
from w07_g4_scorer.route2_dev_canary_runner import (
    ANTHROPIC_100K_CLIFF_TOKENS,
    DEFAULT_DEV_CANARY_HARD_CAP_USD,
    MAX_SCHEMA_RETRIES_PER_ITEM,
    MAX_STAGE1_CANARY_QUERIES,
    ProviderRateProfile,
    _append_jsonl_durable,
    _meter_usage_usd,
    format_provider_batch_item,
)

OPENAI_272K_CLIFF_TOKENS = 272_000
from w07_g4_scorer.route2_live_preflight import (
    NONTERMINAL_BATCH_STATUSES,
    PA1_DEV_HARD_CAP_USD,
    PA1_TOTAL_HARD_CAP_USD,
    TERMINAL_BATCH_STATUSES,
    _aggregate_ledger_lock,
    _load_or_init_aggregate_stage1_ledger_unlocked,
    _recompute_aggregate_ledger,
    _save_aggregate_ledger_atomic,
    authorize_stage1_live_canary_gate,
    link_stage1_dispatched_batch,
    load_or_init_aggregate_stage1_ledger,
    prepare_stage1_pre_submit_intent,
    reconcile_stage1_crash_intents,
)
from w07_g4_scorer.route2_live_probe_client import (
    ANTHROPIC_API_BASE,
    ANTHROPIC_API_VERSION,
    OPENAI_API_BASE,
    _default_urlopen,
)
from w07_g4_scorer.route2_secret_vault import (
    default_dpapi_vault_path,
    inspect_provider_secret_posture,
    redact_secret_text,
    resolve_provider_secret,
)

DEV5_LIVE_RUN_SCHEMA = "GOMATE_W07_STAGE1_DEV5_LIVE_RUN_V1"
DEV5_RUN_MANIFEST_SCHEMA = "GOMATE_W07_STAGE1_DEV5_RUN_MANIFEST_V1"
DEFAULT_STAGE1_SHARED_LEDGER_ROOT = Path(__file__).resolve().parents[3] / "_w07_auto_eval_isolated_logs"
DEFAULT_SHARED_BUDGET_LEDGER_FILENAME = "stage1_dev5_shared_budget_ledger.json"

_DISPATCH_LOCKS_GUARD = threading.Lock()
_DISPATCH_LOCKS: dict[str, threading.RLock] = {}

_DISPATCH_STAGE_VALUES: frozenset[str] = frozenset(
    {
        "PRE_SUBMIT_RESERVED",
        "UPLOAD_IN_FLIGHT",
        "INPUT_FILE_UPLOADED_PRE_BATCH_POST",
        "BATCH_POST_IN_FLIGHT",
        "BATCH_CREATE_4XX_REJECTED",
        "BATCH_DISPATCHED",
    }
)

PINNED_RESPONSE_SCHEMA_S4_SHA256 = "544062c5554fb2c4e987b4262db3522acbf77401226a15a52ea2f18a599a24d1"
APPROVED_STAGE1_DEV5_QUERY_IDS: tuple[str, ...] = (
    "W07-STAGE1-DEV-CAND-Q01",
    "W07-STAGE1-DEV-CAND-Q02",
    "W07-STAGE1-DEV-CAND-Q03",
    "W07-STAGE1-DEV-CAND-Q04",
    "W07-STAGE1-DEV-CAND-Q06",
)
DROPPED_DEV5_QUERY_IDS: frozenset[str] = frozenset({"W07-STAGE1-DEV-CAND-Q05"})
ALLOWED_DEV5_SLICE_MODES: tuple[str, ...] = (
    "canary_1x10",
    "dev5_canonical_685",
    "dev5_plus_20pct_swap",
)

LIVE_CUSTOM_ID_SAFE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
CANONICAL_UUID_32_RE = re.compile(r"^[0-9a-f]{32}$")
_ACTIVE_INTENT_STATUSES: frozenset[str] = frozenset({"INTENT_PRE_SUBMIT", "DISPATCHED", "UNRESOLVED_CRASH_RESERVED"})

UrlOpener = Callable[[urllib.request.Request, float], tuple[int, Mapping[str, str], bytes]]


class LiveTransportError(RuntimeError):
    """Sanitized HTTP/transport exception carrying provider/status without secret material."""

    def __init__(self, provider: str, operation: str, status_code: int | None, message: str) -> None:
        self.provider = provider
        self.operation = operation
        self.status_code = status_code
        self.message = message
        code_part = f"HTTP_{status_code}" if status_code is not None else "NETWORK_ERROR"
        super().__init__(f"{provider}:{operation}:{code_part}:{message}")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso_unix(ts: str | None) -> float | None:
    if not isinstance(ts, str) or not ts.strip():
        return None
    try:
        cleaned = ts.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        return datetime.fromisoformat(cleaned).timestamp()
    except ValueError:
        return None


def _save_json_atomic(path: Path, obj: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp.{os.getpid()}"
    payload = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)


def _validate_path_ancestors_outside_repos(target_path: Path) -> Path:
    for cand in (target_path, *target_path.parents):
        if cand.exists():
            _assert_not_symlink_or_reparse(cand)
    resolved = target_path.resolve()
    _assert_path_outside_repositories(resolved)
    return resolved


def resolve_stage1_shared_budget_ledger_path(*, shared_budget_ledger_path: Path | None = None) -> Path:
    """Resolve the single canonical DEV5 shared $2.00 budget ledger path independent of --output-dir."""
    cand = shared_budget_ledger_path or (DEFAULT_STAGE1_SHARED_LEDGER_ROOT / DEFAULT_SHARED_BUDGET_LEDGER_FILENAME)
    return _validate_path_ancestors_outside_repos(cand)


@contextmanager
def _dispatch_coordinator_lock(ledger_path: Path, *, timeout_seconds: float = 120.0) -> Iterator[None]:
    """Serialize cross-thread/cross-process dispatch cycles on a sidecar lock disjoint from ledger .lock."""
    resolved = ledger_path.resolve()
    key = str(resolved)
    with _DISPATCH_LOCKS_GUARD:
        tlock = _DISPATCH_LOCKS.setdefault(key, threading.RLock())
    lock_file = ledger_path.with_name(f"{ledger_path.name}.dispatch.lock")
    with tlock:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        with lock_file.open("a+b") as fh:
            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                fh.write(b"\x00")
                fh.flush()
            deadline = time.monotonic() + max(1.0, float(timeout_seconds))
            if os.name == "nt":
                while True:
                    try:
                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError(f"STAGE1_SHARED_DISPATCH_LOCK_TIMEOUT:{lock_file}")
                        time.sleep(0.02)
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


def openai_upload_filename_for_intent(client_idempotency_key: str) -> str:
    """Return deterministic unique OpenAI batch JSONL upload filename bound to client_idempotency_key."""
    return f"w07_dev5_{client_idempotency_key[:24]}.jsonl"


def record_stage1_dispatch_progress(
    *,
    ledger_path: Path,
    client_idempotency_key: str,
    dispatch_stage: str,
    input_file_id: str | None = None,
    input_upload_filename: str | None = None,
    input_jsonl_sha256: str | None = None,
    upload_started_at_utc: str | None = None,
    file_cleanup_status: str | None = None,
    pending_cleanup_file_ids: Sequence[str] | None = None,
    cleaned_file_ids: Sequence[str] | None = None,
    file_reconcile_exhaustive: bool | None = None,
    file_reconcile_stop_reason: str | None = None,
    source_output_dir: Path | None = None,
    wire_dispatch_tag: str | None = None,
) -> dict[str, Any]:
    """Atomically record durable upload/dispatch checkpoints (including UPLOAD_IN_FLIGHT) BEFORE HTTP requests."""
    if dispatch_stage not in _DISPATCH_STAGE_VALUES:
        raise ValueError(f"INVALID_DISPATCH_STAGE:{dispatch_stage!r}")
    with _aggregate_ledger_lock(ledger_path):
        ledger = _load_or_init_aggregate_stage1_ledger_unlocked(ledger_path)
        if client_idempotency_key not in ledger["intents"]:
            raise KeyError(f"UNKNOWN_PRE_SUBMIT_INTENT:{client_idempotency_key}")
        rec = ledger["intents"][client_idempotency_key]
        prev_stage = str(rec.get("dispatch_stage") or "")
        now_iso = _utc_now_iso()
        rec["dispatch_stage"] = dispatch_stage
        rec["dispatch_stage_updated_at_utc"] = now_iso
        # Pin fixed upload-start anchor once on entry to UPLOAD_IN_FLIGHT; never fabricate one during later
        # checkpoints on legacy ledgers that predate upload_started_at_utc.
        if upload_started_at_utc is not None and not rec.get("upload_started_at_utc"):
            rec["upload_started_at_utc"] = str(upload_started_at_utc)
        elif dispatch_stage == "UPLOAD_IN_FLIGHT" and prev_stage != "UPLOAD_IN_FLIGHT" and not rec.get("upload_started_at_utc"):
            rec["upload_started_at_utc"] = now_iso
        if input_file_id is not None:
            rec["input_file_id"] = input_file_id
        if input_upload_filename is not None:
            rec["input_upload_filename"] = str(input_upload_filename)
        if input_jsonl_sha256 is not None:
            rec["input_jsonl_sha256"] = str(input_jsonl_sha256)
        if file_cleanup_status is not None:
            rec["file_cleanup_status"] = str(file_cleanup_status)
        if pending_cleanup_file_ids is not None:
            rec["pending_cleanup_file_ids"] = list(dict.fromkeys(str(x) for x in pending_cleanup_file_ids if x))
        if cleaned_file_ids is not None:
            rec["cleaned_file_ids"] = list(dict.fromkeys(str(x) for x in cleaned_file_ids if x))
        if file_reconcile_exhaustive is not None:
            rec["file_reconcile_exhaustive"] = bool(file_reconcile_exhaustive)
        if file_reconcile_stop_reason is not None:
            rec["file_reconcile_stop_reason"] = str(file_reconcile_stop_reason)
        if source_output_dir is not None:
            rec["source_output_dir"] = str(source_output_dir.resolve())
        if wire_dispatch_tag is not None:
            rec["wire_dispatch_tag"] = str(wire_dispatch_tag)
        _recompute_aggregate_ledger(ledger)
        _save_aggregate_ledger_atomic(ledger_path, ledger)
        return dict(rec)


def record_stage1_recovery_linkage(
    *,
    ledger_path: Path,
    recovery_intent_key: str,
    recovery_epoch_id: str,
    recovery_mode: str,
    supersedes_intent_keys: Sequence[str],
    supersedes_batch_ids: Sequence[str],
    supersedes_run_ids: Sequence[str],
    recovered_error_signature: str,
    recovery_batch_id: str | None = None,
) -> dict[str, Any]:
    """Atomically link a new recovery intent to superseded terminal intent(s) without altering historical spend."""
    sup_keys = list(dict.fromkeys(str(k) for k in supersedes_intent_keys if k))
    sup_bids = list(dict.fromkeys(str(b) for b in supersedes_batch_ids if b))
    sup_runs = list(dict.fromkeys(str(r) for r in supersedes_run_ids if r))
    with _aggregate_ledger_lock(ledger_path):
        ledger = _load_or_init_aggregate_stage1_ledger_unlocked(ledger_path)
        intents = ledger.get("intents") or {}
        if recovery_intent_key not in intents:
            raise KeyError(f"UNKNOWN_RECOVERY_INTENT:{recovery_intent_key}")
        new_rec = intents[recovery_intent_key]
        new_rec["recovery_mode"] = str(recovery_mode)
        new_rec["recovery_epoch_id"] = str(recovery_epoch_id)
        new_rec["supersedes_intent_keys"] = sup_keys
        new_rec["supersedes_batch_ids"] = sup_bids
        new_rec["supersedes_run_ids"] = sup_runs
        new_rec["recovered_error_signature"] = str(recovered_error_signature)

        for old_k in sup_keys:
            old_rec = intents.get(old_k)
            if not isinstance(old_rec, dict):
                continue
            by_intents = list(old_rec.get("superseded_by_intent_keys") or [])
            if recovery_intent_key not in by_intents:
                by_intents.append(recovery_intent_key)
            old_rec["superseded_by_intent_keys"] = by_intents
            epochs = list(old_rec.get("recovery_epoch_ids") or [])
            if recovery_epoch_id not in epochs:
                epochs.append(recovery_epoch_id)
            old_rec["recovery_epoch_ids"] = epochs
            if recovery_batch_id:
                by_batches = list(old_rec.get("superseded_by_batch_ids") or [])
                if str(recovery_batch_id) not in by_batches:
                    by_batches.append(str(recovery_batch_id))
                old_rec["superseded_by_batch_ids"] = by_batches

        _recompute_aggregate_ledger(ledger)
        _save_aggregate_ledger_atomic(ledger_path, ledger)
        return dict(new_rec)


def to_wire_custom_id(
    packet_item_uuid: str,
    prompt_order: str,
    *,
    dispatch_tag: str | None = None,
) -> str:
    """Convert (uuid, prompt_order[, dispatch_tag]) into Anthropic/OpenAI-compliant ^[A-Za-z0-9_-]{1,64}$."""
    if prompt_order not in ("PROMPT_ORDER_CANONICAL", "PROMPT_ORDER_SWAPPED"):
        raise ValueError(f"INVALID_PROMPT_ORDER:{prompt_order!r}")
    wire = f"{packet_item_uuid}__{prompt_order}"
    if dispatch_tag is not None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,12}", dispatch_tag):
            raise ValueError(f"INVALID_DISPATCH_TAG:{dispatch_tag!r}")
        wire = f"{wire}__{dispatch_tag}"
    if not LIVE_CUSTOM_ID_SAFE_RE.fullmatch(wire):
        raise ValueError(f"INVALID_LIVE_WIRE_CUSTOM_ID:{wire!r}")
    return wire


def canonicalize_custom_id(custom_id: str) -> str:
    """Normalize live wire custom_id (uuid__ORDER[__tag]) or mock custom_id (uuid::ORDER) to uuid::ORDER."""
    if "::" in custom_id:
        parts = custom_id.split("::", 1)
    elif "__PROMPT_ORDER_" in custom_id:
        idx = custom_id.index("__PROMPT_ORDER_")
        tail = custom_id[idx + 2 :]
        order_part = tail.split("__", 1)[0]
        parts = [custom_id[:idx], order_part]
    else:
        return custom_id
    if parts[1] in ("PROMPT_ORDER_CANONICAL", "PROMPT_ORDER_SWAPPED"):
        return f"{parts[0]}::{parts[1]}"
    return custom_id


def _load_and_verify_prompt_and_schema(dev5_root: Path) -> tuple[str, dict[str, Any], dict[str, str]]:
    """Load Prompt v1.1 and Schema S-4 from DEV5 config dir and verify SHA-256 pins."""
    cfg_dir = dev5_root / "03_stage1_configs_and_cost_estimator"
    prompt_path = cfg_dir / "W07_DEV_STATIC_PROMPT_TEMPLATE_CANDIDATE_v1_1_offset01.json"
    schema_path = cfg_dir / "W07_DEV_RESPONSE_SCHEMA_CANDIDATE_v1.json"
    if not prompt_path.is_file():
        raise FileNotFoundError(f"MISSING_PROMPT_TEMPLATE:{prompt_path}")
    if not schema_path.is_file():
        raise FileNotFoundError(f"MISSING_RESPONSE_SCHEMA:{schema_path}")

    prompt_raw = prompt_path.read_bytes()
    prompt_obj = json.loads(prompt_raw.decode("utf-8"))
    system_prompt = prompt_obj.get("system_prompt")
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError("INVALID_EMPTY_SYSTEM_PROMPT")
    actual_sys_sha = sha256_bytes(system_prompt.encode("utf-8"))
    if actual_sys_sha != PINNED_STAGE1_SYSTEM_PROMPT_V1_1_SHA256:
        raise PermissionError(
            f"PINNED_PROMPT_V1_1_SHA_MISMATCH:{actual_sys_sha}!={PINNED_STAGE1_SYSTEM_PROMPT_V1_1_SHA256}"
        )

    schema_raw = schema_path.read_bytes()
    actual_schema_sha = sha256_bytes(schema_raw)
    if actual_schema_sha != PINNED_RESPONSE_SCHEMA_S4_SHA256:
        raise PermissionError(
            f"PINNED_SCHEMA_S4_SHA_MISMATCH:{actual_schema_sha}!={PINNED_RESPONSE_SCHEMA_S4_SHA256}"
        )
    response_schema = json.loads(schema_raw.decode("utf-8"))
    return (
        system_prompt,
        response_schema,
        {
            "prompt_file_sha256": sha256_bytes(prompt_raw),
            "system_prompt_sha256": actual_sys_sha,
            "response_schema_s4_sha256": actual_schema_sha,
        },
    )


def load_approved_dev5_queries(
    queries_json_path: Path,
    *,
    approved_pois_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Load ONLY Owner-approved DEV5 queries (Q01/Q02/Q03/Q04/Q06), blocking Q05 and FINAL."""
    if not queries_json_path.is_file():
        raise FileNotFoundError(f"MISSING_DEV5_QUERIES_FILE:{queries_json_path}")
    doc = json.loads(queries_json_path.read_text(encoding="utf-8"))
    raw_queries = doc.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise ValueError("INVALID_DEV5_QUERIES_LIST")
    if len(raw_queries) > MAX_STAGE1_CANARY_QUERIES:
        raise PermissionError(f"STAGE1_DEV_QUERY_LIMIT_EXCEEDED:{len(raw_queries)}")

    approved: list[dict[str, Any]] = []
    seen_qids: list[str] = []
    for raw_q in raw_queries:
        if not isinstance(raw_q, Mapping):
            raise ValueError("INVALID_DEV5_QUERY_ENTRY")
        qid = str(raw_q.get("query_id", ""))
        raw_split = str(raw_q.get("split", ""))
        if "FINAL" in qid.upper() or "FINAL" in raw_split.upper():
            raise PermissionError(f"FINAL_CONTAMINATION_BLOCKED_IN_DEV5_LOADER:{qid!r}")
        if qid in DROPPED_DEV5_QUERY_IDS:
            raise PermissionError(f"DROPPED_DEV5_QUERY_BLOCKED:{qid!r}")
        if qid not in APPROVED_STAGE1_DEV5_QUERY_IDS:
            raise PermissionError(f"UNAPPROVED_STAGE1_DEV5_QUERY_BLOCKED:{qid!r}")
        if raw_split not in ("DEV", "DEV_CANDIDATE_QUARANTINED"):
            raise PermissionError(f"DISALLOWED_QUERY_SPLIT_IN_DEV5:{qid}:{raw_split!r}")
        smeta = raw_q.get("sealed_query_meta")
        if not isinstance(smeta, Mapping):
            raise ValueError(f"MISSING_SEALED_QUERY_META:{qid}")

        promoted_q = {
            "query_id": qid,
            "split": "DEV",
            "source_split_before_phase2": raw_split,
            "query_text": str(raw_q["query_text"]),
            "question_origin": "AI_GENERATED_NO_HUMAN_REVIEW",
            "human_ground_truth": False,
            **dict(smeta),
        }
        meta_err = validate_sealed_query_metadata(promoted_q, approved_pois_by_id=approved_pois_by_id)
        if meta_err is not None:
            raise ValueError(f"INVALID_DEV5_QUERY_META:{qid}:{meta_err.get('error_code')}")
        if qid in seen_qids:
            raise ValueError(f"DUPLICATE_DEV5_QUERY_ID:{qid}")
        seen_qids.append(qid)
        approved.append(promoted_q)

    if set(seen_qids) != set(APPROVED_STAGE1_DEV5_QUERY_IDS):
        raise PermissionError(
            f"DEV5_APPROVED_QUERY_SET_MISMATCH:expected={sorted(APPROVED_STAGE1_DEV5_QUERY_IDS)},got={sorted(seen_qids)}"
        )
    order_rank = {qid: i for i, qid in enumerate(APPROVED_STAGE1_DEV5_QUERY_IDS)}
    approved.sort(key=lambda q: order_rank[q["query_id"]])
    return approved


def verify_arm_p_137_corpus_docs(
    corpus_docs: Sequence[Mapping[str, Any]],
    *,
    expected_v_sha256: str | None = None,
) -> list[dict[str, Any]]:
    """Verify the 137 Arm P corpus records (V clean, S->V lossless segments, exact V SHA-256 046424e5...)."""
    expected_sha = expected_v_sha256 or EXPECTED_V_CORPUS_SHA256
    if len(corpus_docs) != 137:
        raise ValueError(f"EXPECTED_137_ARM_P_DOCS_GOT:{len(corpus_docs)}")

    verified: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    v_parts: list[str] = []
    for raw_doc in corpus_docs:
        did = str(raw_doc.get("document_id", "")).strip()
        if not did or did in seen_ids:
            raise ValueError(f"INVALID_OR_DUPLICATE_DOCUMENT_ID:{did!r}")
        seen_ids.add(did)

        canon_s = raw_doc.get("canonical_text_S")
        san_v = raw_doc.get("sanitized_text_V")
        v_to_s = raw_doc.get("v_to_s_segments")
        rem_r = raw_doc.get("removed_r_audit")
        city = raw_doc.get("city")
        poi_id = raw_doc.get("poi_id")
        if not isinstance(canon_s, str) or not canon_s:
            raise ValueError(f"MISSING_CANONICAL_S:{did}")
        if not isinstance(san_v, str) or not san_v:
            raise ValueError(f"MISSING_SANITIZED_V:{did}")
        if "[CORROBORATED" in san_v:
            raise PermissionError(f"R_AUDIT_RESIDUAL_IN_SANITIZED_V:{did}")
        if not isinstance(city, str) or not city.strip():
            raise ValueError(f"MISSING_CITY_META:{did}")
        if not isinstance(poi_id, str) or not poi_id.strip():
            raise ValueError(f"MISSING_POI_META:{did}")
        if not isinstance(v_to_s, list) or not isinstance(rem_r, list):
            raise ValueError(f"MISSING_V_TO_S_OR_REMOVED_R:{did}")

        seg_tuples: list[tuple[int, int, int, int]] = []
        v_cursor = 0
        for seg in v_to_s:
            vs, ve, ss, se = int(seg[0]), int(seg[1]), int(seg[2]), int(seg[3])
            if vs != v_cursor or ve < vs or (ve - vs) != (se - ss):
                raise ValueError(f"CORRUPT_V_TO_S_SEGMENT:{did}:{(vs, ve, ss, se)}")
            if san_v[vs:ve] != canon_s[ss:se]:
                raise ValueError(f"V_S_SEGMENT_TEXT_MISMATCH:{did}:{(vs, ve, ss, se)}")
            seg_tuples.append((vs, ve, ss, se))
            v_cursor = ve
        if v_cursor != len(san_v):
            raise ValueError(f"V_SEGMENT_COVERAGE_GAP:{did}:{v_cursor}!={len(san_v)}")

        rem_tuples = [(int(a), int(b)) for a, b in rem_r]
        if len(san_v) + sum(b - a for a, b in rem_tuples) != len(canon_s):
            raise ValueError(f"V_S_LENGTH_CONSERVATION_FAILED:{did}")

        v_parts.append(f"{did}::{san_v}")
        verified.append(
            {
                "document_id": did,
                "poi_id": poi_id,
                "city": city,
                "source_type": str(raw_doc.get("source_type", "")),
                "language": str(raw_doc.get("language", "vi")),
                "canonical_text_S": canon_s,
                "sanitized_text_V": san_v,
                "v_to_s_segments": seg_tuples,
                "removed_r_audit": rem_tuples,
            }
        )

    actual_v_sha = sha256_bytes("\n<<<DOC>>>\n".join(v_parts).encode("utf-8"))
    if actual_v_sha != expected_sha:
        raise PermissionError(f"ARM_P_SANITIZED_V_SHA_MISMATCH:{actual_v_sha}!={expected_sha}")
    return verified


def _select_stratified_swap_indices(num_queries: int, num_docs: int) -> dict[int, set[int]]:
    """Select exact 20% (137/685) stratified swapped doc indices across 5 queries (28,28,27,27,27)."""
    if num_queries <= 0 or num_docs <= 0:
        raise ValueError("INVALID_STRATIFICATION_DIMS")
    return {q_idx: set(range(q_idx, num_docs, num_queries)) for q_idx in range(num_queries)}


def build_approved_dev5_canary_items(
    *,
    dev5_queries: Sequence[Mapping[str, Any]],
    corpus_docs: Sequence[Mapping[str, Any]],
    slice_mode: str = "dev5_plus_20pct_swap",
    packet_salt: str,
    run_nonce_seed: str,
    canary_1x10_doc_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Construct verified DEV5 items strictly from approved DEV queries and 137 Arm P sanitized V docs."""
    if slice_mode not in ALLOWED_DEV5_SLICE_MODES:
        raise ValueError(f"UNSUPPORTED_DEV5_SLICE_MODE:{slice_mode!r}")
    if len(dev5_queries) != 5:
        raise PermissionError(f"EXPECTED_5_APPROVED_DEV5_QUERIES_GOT:{len(dev5_queries)}")

    verified_docs = verify_arm_p_137_corpus_docs(corpus_docs)
    docs_by_id = {d["document_id"]: d for d in verified_docs}

    def _make_item(q_meta: Mapping[str, Any], doc: Mapping[str, Any], prompt_order: str) -> dict[str, Any]:
        qid = str(q_meta["query_id"])
        did = str(doc["document_id"])
        pkt_uuid = hashlib.sha256(f"{packet_salt}|{qid}|{did}".encode("utf-8")).hexdigest()[:32]
        wire_cid = to_wire_custom_id(pkt_uuid, prompt_order)
        canon_cid = canonicalize_custom_id(wire_cid)
        run_nonce = hashlib.sha256(f"{run_nonce_seed}|{wire_cid}".encode("utf-8")).hexdigest()[:32]
        leak_rec = {
            "document_id": did,
            "poi_id": doc["poi_id"],
            "canonical_text_S": doc["canonical_text_S"],
            "sanitized_text_V": doc["sanitized_text_V"],
            "removed_r_audit": doc["removed_r_audit"],
        }
        return {
            "packet_item_uuid": pkt_uuid,
            "wire_custom_id": wire_cid,
            "custom_id": canon_cid,
            "prompt_order": prompt_order,
            "run_nonce": run_nonce,
            "sanitized_text_V": doc["sanitized_text_V"],
            "doc_canonical_S": doc["canonical_text_S"],
            "doc_v_to_s_segments": list(doc["v_to_s_segments"]),
            "doc_removed_r_audit": list(doc["removed_r_audit"]),
            "doc_meta": {"city": doc["city"], "poi_id": doc["poi_id"]},
            "doc_record_for_leak_check": leak_rec,
            "query_meta": dict(q_meta),
        }

    items: list[dict[str, Any]] = []
    if slice_mode == "canary_1x10":
        q0 = dev5_queries[0]
        if canary_1x10_doc_ids is not None:
            if len(canary_1x10_doc_ids) != 10:
                raise ValueError(f"CANARY_1X10_REQUIRES_10_DOCS_GOT:{len(canary_1x10_doc_ids)}")
            selected_docs = [docs_by_id[did] for did in canary_1x10_doc_ids]
        else:
            selected_docs = verified_docs[:10]
        for d in selected_docs:
            items.append(_make_item(q0, d, "PROMPT_ORDER_CANONICAL"))
        return items

    for q_meta in dev5_queries:
        for d in verified_docs:
            items.append(_make_item(q_meta, d, "PROMPT_ORDER_CANONICAL"))

    if slice_mode == "dev5_plus_20pct_swap":
        swap_by_q = _select_stratified_swap_indices(len(dev5_queries), len(verified_docs))
        for q_idx, q_meta in enumerate(dev5_queries):
            for d_idx in sorted(swap_by_q[q_idx]):
                items.append(_make_item(q_meta, verified_docs[d_idx], "PROMPT_ORDER_SWAPPED"))

    return items


def build_verified_live_wire_item(
    *,
    provider: str,
    model_id: str,
    item: Mapping[str, Any],
    system_prompt: str,
    response_schema: Mapping[str, Any],
    dispatch_tag: str | None = None,
) -> dict[str, Any]:
    """Build single cloud batch item enforcing S/V firewall, AUTO-R09 params, and safe live custom_id."""
    cloud_wire = build_sanitized_v_cloud_request_payload(
        packet_item_uuid=str(item["packet_item_uuid"]),
        query_text=str(item["query_meta"]["query_text"]),
        sanitized_text_V=str(item["sanitized_text_V"]),
        run_nonce=str(item["run_nonce"]),
        prompt_order=str(item["prompt_order"]),
        doc_record_for_leak_check=item["doc_record_for_leak_check"],
    )
    formatted = format_provider_batch_item(
        provider=provider,
        model_id=model_id,
        packet_item_uuid=str(item["packet_item_uuid"]),
        prompt_order=str(item["prompt_order"]),
        wire_user_prompt=cloud_wire["wire_user_prompt"],
        system_prompt=system_prompt,
        response_schema=response_schema,
        doc_record_for_leak_check=item["doc_record_for_leak_check"],
    )
    wire_cid = to_wire_custom_id(
        str(item["packet_item_uuid"]),
        str(item["prompt_order"]),
        dispatch_tag=dispatch_tag,
    )
    formatted["custom_id"] = wire_cid
    assert_cloud_payload_v_boundary(formatted, doc_record_for_leak_check=item["doc_record_for_leak_check"])
    return {
        "wire_item": formatted,
        "wire_custom_id": wire_cid,
        "canonical_custom_id": canonicalize_custom_id(wire_cid),
        "safe_doc_v": cloud_wire["safe_doc_v"],
        "safe_to_v_segments": cloud_wire["safe_to_v_segments"],
        "wire_payload_sha256": cloud_wire["wire_payload_sha256"],
    }


def _clone_wire_item_with_dispatch_tag(
    wire_item: Mapping[str, Any],
    *,
    packet_item_uuid: str,
    prompt_order: str,
    dispatch_tag: str,
) -> dict[str, Any]:
    cloned = dict(wire_item)
    cloned["custom_id"] = to_wire_custom_id(packet_item_uuid, prompt_order, dispatch_tag=dispatch_tag)
    return cloned


def estimate_batch_worst_case_reserve_usd(
    *,
    provider: str,
    wire_items: Sequence[Mapping[str, Any]],
    rate_profile: ProviderRateProfile,
    max_output_tokens_per_item: int = 1024,
    retry_margin: float = 0.15,
) -> dict[str, Any]:
    """Compute conservative UTF-8 byte-ceiling worst-case USD reserve (1 UTF-8 byte == 1 token)."""
    if not wire_items:
        return {"items": 0, "worst_case_input_tokens": 0, "worst_case_output_tokens": 0, "reserved_worst_case_usd": 0.0, "max_item_input_tokens_ceiling": 0}
    cliff = ANTHROPIC_100K_CLIFF_TOKENS if provider == "anthropic" else OPENAI_272K_CLIFF_TOKENS
    total_in = 0
    max_item_in = 0
    for wi in wire_items:
        item_bytes = len(json.dumps(wi, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        if item_bytes >= cliff:
            raise PermissionError(f"PRE_SUBMIT_LONG_CONTEXT_CLIFF_EXCEEDED:{provider}:{item_bytes}>={cliff}")
        total_in += item_bytes
        if item_bytes > max_item_in:
            max_item_in = item_bytes
    total_out = len(wire_items) * max_output_tokens_per_item
    base_usd = _meter_usage_usd({"input_tokens": total_in, "output_tokens": total_out}, rate_profile)
    reserved_usd = round(base_usd * (1.0 + retry_margin), 6)
    return {
        "items": len(wire_items),
        "worst_case_input_tokens": total_in,
        "worst_case_output_tokens": total_out,
        "max_item_input_tokens_ceiling": max_item_in,
        "below_cliff": max_item_in < cliff,
        "reserved_worst_case_usd": reserved_usd,
    }


def _extract_openai_response_text(body: Mapping[str, Any]) -> str:
    if isinstance(body.get("output_text"), str) and body["output_text"]:
        return str(body["output_text"])
    parts: list[str] = []
    out_list = body.get("output")
    if isinstance(out_list, list):
        for entry in out_list:
            if not isinstance(entry, Mapping) or entry.get("type") != "message":
                continue
            content = entry.get("content")
            if isinstance(content, list):
                for blk in content:
                    if isinstance(blk, Mapping) and blk.get("type") == "output_text" and isinstance(blk.get("text"), str):
                        parts.append(blk["text"])
    return "".join(parts)


def _extract_anthropic_response_text(msg: Mapping[str, Any]) -> str:
    parts: list[str] = []
    content = msg.get("content")
    if isinstance(content, list):
        for blk in content:
            if isinstance(blk, Mapping) and blk.get("type") == "text" and isinstance(blk.get("text"), str):
                parts.append(blk["text"])
    return "".join(parts)


def _parse_judge_json_strict(raw_text: str) -> dict[str, Any]:
    """Parse strict single-object judge JSON rejecting duplicate keys, NaN/Infinity, and trailing junk."""
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("EMPTY_RESPONSE_TEXT")
    try:
        parsed = json.loads(
            raw_text.strip(),
            object_pairs_hook=_no_duplicate_keys_object_pairs_hook,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON_DECODE_ERROR:{exc}") from None
    if not isinstance(parsed, dict):
        raise ValueError(f"EXPECTED_JSON_OBJECT_GOT_{type(parsed).__name__}")
    return parsed


def _valid_int_usage(raw_usage: Any) -> dict[str, int] | None:
    if not isinstance(raw_usage, Mapping):
        return None
    in_tok = raw_usage.get("input_tokens")
    out_tok = raw_usage.get("output_tokens")
    if type(in_tok) is not int or type(out_tok) is not int or in_tok < 0 or out_tok < 0:
        return None
    cache_create = raw_usage.get("cache_creation_input_tokens") or 0
    cache_read = raw_usage.get("cache_read_input_tokens") or 0
    if type(cache_create) is not int or type(cache_read) is not int or cache_create < 0 or cache_read < 0:
        return None
    return {
        "input_tokens": in_tok + cache_create + cache_read,
        "output_tokens": out_tok,
    }


class _BaseHttpsBatchClient:
    """Shared stdlib HTTPS JSON/text requester with strict secret masking and origin enforcement."""

    def __init__(
        self,
        *,
        provider: str,
        api_base: str,
        secret_resolver: Callable[[str], str],
        url_opener: UrlOpener | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.provider = provider
        self.api_base = api_base.rstrip("/")
        parsed = urlparse(self.api_base)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"INVALID_HTTPS_API_BASE:{provider}:{api_base!r}")
        self._allowed_netloc = parsed.netloc
        self._secret_resolver = secret_resolver
        self._url_opener: UrlOpener = url_opener or (lambda req, to: _default_urlopen(req, timeout=to))
        self.timeout_seconds = float(timeout_seconds)

    def _request_bytes(
        self,
        *,
        method: str,
        url_or_path: str,
        operation: str,
        headers: Mapping[str, str],
        body_bytes: bytes | None = None,
    ) -> tuple[int, Mapping[str, str], bytes]:
        if url_or_path.startswith("https://"):
            parsed = urlparse(url_or_path)
            if parsed.netloc != self._allowed_netloc:
                raise PermissionError(f"DISALLOWED_EXTERNAL_HOST_FOR_SECRET:{parsed.netloc!r}")
            url = url_or_path
        else:
            url = f"{self.api_base}/{url_or_path.lstrip('/')}"

        secret = self._secret_resolver(self.provider)
        req = urllib.request.Request(url=url, data=body_bytes, method=method)
        for k, v in headers.items():
            req.add_header(k, v)
        if self.provider == "openai":
            req.add_header("Authorization", f"Bearer {secret}")
        elif self.provider == "anthropic":
            req.add_header("x-api-key", secret)
            req.add_header("anthropic-version", ANTHROPIC_API_VERSION)
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", "GoMate-W07-Stage1-LiveRunner/1.0")

        try:
            status, resp_headers, raw = self._url_opener(req, self.timeout_seconds)
            if not isinstance(raw, (bytes, bytearray)):
                raise TypeError("HTTP response body must be bytes")
            return int(status), dict(resp_headers), bytes(raw)
        except urllib.error.HTTPError as exc:
            err_raw = b""
            try:
                err_raw = exc.read()
            except Exception:
                pass
            snippet = redact_secret_text(err_raw.decode("utf-8", errors="replace")[:400], (secret,))
            raise LiveTransportError(self.provider, operation, int(exc.code), snippet) from None
        except Exception as exc:
            raise LiveTransportError(
                self.provider,
                operation,
                None,
                redact_secret_text(f"{type(exc).__name__}:{exc}", (secret,)),
            ) from None

    def _request_json(
        self,
        *,
        method: str,
        url_or_path: str,
        operation: str,
        json_body: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        allow_statuses: tuple[int, ...] = (200, 201),
    ) -> tuple[int, dict[str, Any]]:
        hdrs = dict(extra_headers or {})
        raw_body: bytes | None = None
        if json_body is not None:
            hdrs["Content-Type"] = "application/json"
            raw_body = json.dumps(json_body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        status, _rh, raw = self._request_bytes(
            method=method,
            url_or_path=url_or_path,
            operation=operation,
            headers=hdrs,
            body_bytes=raw_body,
        )
        text = raw.decode("utf-8", errors="replace")
        if status not in allow_statuses:
            secret = self._secret_resolver(self.provider)
            raise LiveTransportError(self.provider, operation, status, redact_secret_text(text[:400], (secret,)))
        try:
            obj = json.loads(text) if text.strip() else {}
        except json.JSONDecodeError as exc:
            raise LiveTransportError(self.provider, operation, status, f"NON_JSON_BODY:{exc}") from None
        if not isinstance(obj, dict):
            raise LiveTransportError(self.provider, operation, status, "EXPECTED_JSON_OBJECT")
        return status, obj


class OpenAIBatchLiveTransport(_BaseHttpsBatchClient):
    """Live OpenAI Files + /v1/batches (/v1/responses) transport implementing LiveBatchReconcileProtocol."""

    can_submit_billable_batches: bool = True
    is_offline_mock_transport: bool = False

    def __init__(
        self,
        *,
        secret_resolver: Callable[[str], str],
        url_opener: UrlOpener | None = None,
        api_base: str = OPENAI_API_BASE,
        timeout_seconds: float = 60.0,
        list_files_max_pages: int = 5,
    ) -> None:
        super().__init__(
            provider="openai",
            api_base=api_base,
            secret_resolver=secret_resolver,
            url_opener=url_opener,
            timeout_seconds=timeout_seconds,
        )
        self.list_files_max_pages = max(1, int(list_files_max_pages))

    def _upload_batch_jsonl_file(self, *, jsonl_bytes: bytes, filename: str) -> dict[str, Any]:
        boundary = f"----GoMateW07Boundary{uuid.uuid4().hex}"
        crlf = b"\r\n"
        body = (
            b"--" + boundary.encode("ascii") + crlf
            + b'Content-Disposition: form-data; name="purpose"' + crlf + crlf
            + b"batch" + crlf
            + b"--" + boundary.encode("ascii") + crlf
            + f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode("utf-8") + crlf
            + b"Content-Type: application/jsonl" + crlf + crlf
            + jsonl_bytes + crlf
            + b"--" + boundary.encode("ascii") + b"--" + crlf
        )
        status, _rh, raw = self._request_bytes(
            method="POST",
            url_or_path="/v1/files",
            operation="upload_file",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            body_bytes=body,
        )
        if status not in (200, 201):
            secret = self._secret_resolver("openai")
            raise LiveTransportError(
                "openai", "upload_file", status, redact_secret_text(raw.decode("utf-8", errors="replace")[:400], (secret,))
            )
        obj = json.loads(raw.decode("utf-8"))
        if not isinstance(obj, dict) or not isinstance(obj.get("id"), str):
            raise LiveTransportError("openai", "upload_file", status, "MISSING_FILE_ID_IN_UPLOAD_RESPONSE")
        return obj

    def submit_batch(
        self,
        *,
        run_id: str,
        client_idempotency_key: str,
        wire_items: Sequence[Mapping[str, Any]],
        expected_snapshot_id: str | None = None,
        on_before_file_upload: Callable[[str, str], None] | None = None,
        on_input_file_uploaded: Callable[[str], None] | None = None,
        on_before_batch_create: Callable[[], None] | None = None,
        on_batch_create_4xx: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        del expected_snapshot_id
        if not wire_items:
            raise ValueError("CANNOT_SUBMIT_EMPTY_OPENAI_BATCH")
        lines: list[str] = []
        for it in wire_items:
            cid = str(it.get("custom_id", ""))
            if not LIVE_CUSTOM_ID_SAFE_RE.fullmatch(cid):
                raise ValueError(f"UNSAFE_OPENAI_CUSTOM_ID:{cid!r}")
            body = it.get("body") or {}
            if body.get("store") is not False:
                raise PermissionError("OPENAI_BATCH_REQUIRES_STORE_FALSE")
            assert_cloud_payload_v_boundary(it)
            lines.append(json.dumps(it, separators=(",", ":"), ensure_ascii=False))
        jsonl_bytes = ("\n".join(lines) + "\n").encode("utf-8")
        upload_filename = openai_upload_filename_for_intent(client_idempotency_key)
        jsonl_sha = sha256_bytes(jsonl_bytes)
        # Persist UPLOAD_IN_FLIGHT + unique filename BEFORE initiating POST /v1/files so lost responses stay tracked.
        if on_before_file_upload is not None:
            on_before_file_upload(upload_filename, jsonl_sha)
        file_obj = self._upload_batch_jsonl_file(
            jsonl_bytes=jsonl_bytes,
            filename=upload_filename,
        )
        input_file_id = str(file_obj["id"])
        # Durably persist input_file_id BEFORE attempting POST /v1/batches so interrupted runs can clean up.
        if on_input_file_uploaded is not None:
            on_input_file_uploaded(input_file_id)
        if on_before_batch_create is not None:
            on_before_batch_create()
        try:
            _st, batch_obj = self._request_json(
                method="POST",
                url_or_path="/v1/batches",
                operation="create_batch",
                json_body={
                    "input_file_id": input_file_id,
                    "endpoint": "/v1/responses",
                    "completion_window": "24h",
                    "metadata": {
                        "client_idempotency_key": client_idempotency_key,
                        "run_id": run_id[:128],
                        "stage": "STAGE1_DEV5_CANARY",
                    },
                },
            )
        except LiveTransportError as exc:
            # Clean orphan uploaded file ONLY when provider definitively rejected POST /v1/batches (4xx).
            if exc.status_code is not None and 400 <= exc.status_code < 500:
                if on_batch_create_4xx is not None:
                    on_batch_create_4xx()
                try:
                    self.delete_file(input_file_id)
                except Exception:
                    pass
            raise
        return {
            "provider": "openai",
            "batch_id": str(batch_obj["id"]),
            "batch_status": str(batch_obj.get("status", "VALIDATING")).upper(),
            "input_file_id": input_file_id,
            "output_file_id": batch_obj.get("output_file_id"),
            "error_file_id": batch_obj.get("error_file_id"),
            "input_jsonl_sha256": sha256_bytes(jsonl_bytes),
        }

    def lookup_batch_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any]:
        after: str | None = None
        for _page in range(5):
            path = "/v1/batches?limit=100" + (f"&after={after}" if after else "")
            _st, page = self._request_json(method="GET", url_or_path=path, operation="list_batches")
            data = page.get("data") or []
            if isinstance(data, list):
                for b in data:
                    if not isinstance(b, Mapping):
                        continue
                    meta = b.get("metadata") or {}
                    if isinstance(meta, Mapping) and meta.get("client_idempotency_key") == idempotency_key:
                        return {
                            "found": True,
                            "batch_id": str(b["id"]),
                            "input_file_id": b.get("input_file_id"),
                            "output_file_id": b.get("output_file_id"),
                            "batch_status": str(b.get("status", "")).upper(),
                        }
            if not page.get("has_more") or not data:
                break
            after = str(data[-1]["id"])
        # Fail-closed on miss: eventual consistency never unlocks reserved budget without authoritative proof.
        return {"found": False, "authoritative_non_acceptance": False}

    def lookup_uploaded_files_by_filename(
        self,
        filename: str,
        *,
        created_after_unix: float | None = None,
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        """Paginate /v1/files?purpose=batch and explicitly distinguish exhaustive vs truncated scans."""
        limit = max(1, int(max_pages if max_pages is not None else self.list_files_max_pages))
        matches: list[dict[str, Any]] = []
        seen_cursors: set[str] = set()
        after: str | None = None
        exhaustive = False
        stop_reason = "PAGE_LIMIT_EXCEEDED"
        pages_scanned = 0

        for _page_idx in range(limit):
            pages_scanned += 1
            path = "/v1/files?purpose=batch&limit=100" + (f"&after={after}" if after else "")
            _st, page = self._request_json(method="GET", url_or_path=path, operation="list_files")
            data = page.get("data")
            if not isinstance(data, list):
                exhaustive = False
                stop_reason = "MALFORMED_DATA_FIELD"
                break
            for fobj in data:
                if not isinstance(fobj, Mapping):
                    continue
                if str(fobj.get("filename") or "") != filename:
                    continue
                raw_created = fobj.get("created_at")
                if created_after_unix is not None and isinstance(raw_created, (int, float)):
                    if float(raw_created) < (created_after_unix - 300.0):
                        continue
                matches.append(dict(fobj))

            if "has_more" not in page or page.get("has_more") is None:
                exhaustive = False
                stop_reason = "MISSING_HAS_MORE_FLAG"
                break
            raw_has_more = page.get("has_more")
            if type(raw_has_more) is not bool:
                exhaustive = False
                stop_reason = f"INVALID_HAS_MORE_TYPE:{type(raw_has_more).__name__}"
                break
            if raw_has_more is False:
                exhaustive = True
                stop_reason = "END_OF_LIST"
                break

            next_cursor: str | None = None
            if data and isinstance(data[-1], Mapping) and isinstance(data[-1].get("id"), str) and data[-1]["id"]:
                next_cursor = str(data[-1]["id"])
            elif isinstance(page.get("last_id"), str) and page["last_id"]:
                next_cursor = str(page["last_id"])

            if not next_cursor:
                exhaustive = False
                stop_reason = "MISSING_PAGINATION_CURSOR"
                break
            if next_cursor == after or next_cursor in seen_cursors:
                exhaustive = False
                stop_reason = "REPEATED_PAGINATION_CURSOR"
                break
            seen_cursors.add(next_cursor)
            after = next_cursor

        matches.sort(key=lambda item: (float(item.get("created_at") or 0.0), str(item.get("id") or "")))
        return {
            "files": matches,
            "exhaustive": exhaustive,
            "pages_scanned": pages_scanned,
            "stop_reason": stop_reason,
        }

    def _download_file_jsonl(self, file_id: str) -> list[dict[str, Any]]:
        status, _rh, raw = self._request_bytes(
            method="GET",
            url_or_path=f"/v1/files/{file_id}/content",
            operation="download_file_content",
            headers={"Accept": "application/jsonl"},
        )
        if status != 200:
            secret = self._secret_resolver("openai")
            raise LiveTransportError(
                "openai", "download_file_content", status, redact_secret_text(raw.decode("utf-8", errors="replace")[:400], (secret,))
            )
        rows: list[dict[str, Any]] = []
        for ln in raw.decode("utf-8").splitlines():
            stripped = ln.strip()
            if stripped:
                rows.append(json.loads(stripped))
        return rows

    def fetch_batch_outcome(self, batch_id: str) -> dict[str, Any]:
        _st, obj = self._request_json(method="GET", url_or_path=f"/v1/batches/{batch_id}", operation="get_batch")
        status_upper = str(obj.get("status", "UNKNOWN")).upper()
        base = {
            "provider": "openai",
            "batch_id": str(obj.get("id", batch_id)),
            "batch_status": status_upper,
            "input_file_id": obj.get("input_file_id"),
            "output_file_id": obj.get("output_file_id"),
            "error_file_id": obj.get("error_file_id"),
            "request_counts": obj.get("request_counts"),
            "batch_usage": obj.get("usage"),
        }
        if status_upper in NONTERMINAL_BATCH_STATUSES or status_upper not in TERMINAL_BATCH_STATUSES:
            return {**base, "items": []}

        parsed_items: list[dict[str, Any]] = []
        seen_cids: set[str] = set()
        out_fid = obj.get("output_file_id")
        if isinstance(out_fid, str) and out_fid:
            for row in self._download_file_jsonl(out_fid):
                wire_cid = str(row.get("custom_id", ""))
                canon_cid = canonicalize_custom_id(wire_cid)
                seen_cids.add(canon_cid)
                resp = row.get("response") or {}
                http_code = resp.get("status_code") if isinstance(resp, Mapping) else None
                body = resp.get("body") if isinstance(resp, Mapping) and isinstance(resp.get("body"), Mapping) else {}
                usage = _valid_int_usage(body.get("usage"))
                snap = body.get("model") or obj.get("model")
                raw_text = _extract_openai_response_text(body)
                parsed_resp: dict[str, Any] | None = None
                err_code: str | None = None
                if http_code != 200 or row.get("error"):
                    err_code = f"PROVIDER_ITEM_HTTP_{http_code}"
                else:
                    try:
                        parsed_resp = _parse_judge_json_strict(raw_text)
                    except ValueError as exc:
                        err_code = f"MALFORMED_JSON_OUTPUT:{exc}"
                parsed_items.append(
                    {
                        "custom_id": canon_cid,
                        "wire_custom_id": wire_cid,
                        "model_snapshot_id": str(snap) if isinstance(snap, str) and snap else None,
                        "usage": usage,
                        "parsed_response": parsed_resp,
                        "raw_text": raw_text,
                        "provider_error": row.get("error") or err_code,
                    }
                )

        err_fid = obj.get("error_file_id")
        if isinstance(err_fid, str) and err_fid:
            for row in self._download_file_jsonl(err_fid):
                wire_cid = str(row.get("custom_id", ""))
                canon_cid = canonicalize_custom_id(wire_cid)
                if canon_cid in seen_cids:
                    continue
                resp = row.get("response") or {}
                body = resp.get("body") if isinstance(resp, Mapping) and isinstance(resp.get("body"), Mapping) else {}
                usage = _valid_int_usage(body.get("usage"))
                parsed_items.append(
                    {
                        "custom_id": canon_cid,
                        "wire_custom_id": wire_cid,
                        "model_snapshot_id": str(body.get("model")) if isinstance(body.get("model"), str) else None,
                        "usage": usage,
                        "parsed_response": None,
                        "raw_text": "",
                        "provider_error": row.get("error") or resp or "BATCH_ITEM_FAILED",
                    }
                )
        return {**base, "items": parsed_items}

    def delete_file(self, file_id: str) -> dict[str, Any]:
        _st, obj = self._request_json(
            method="DELETE",
            url_or_path=f"/v1/files/{file_id}",
            operation="delete_file",
            allow_statuses=(200, 404),
        )
        if _st == 404:
            return {"file_id": file_id, "deleted": True, "already_absent": True}
        return {"file_id": file_id, "deleted": bool(obj.get("deleted", False))}

    def delete_batch(self, batch_id: str) -> dict[str, Any]:
        _st, obj = self._request_json(method="GET", url_or_path=f"/v1/batches/{batch_id}", operation="verify_batch_terminal_for_cleanup")
        status_upper = str(obj.get("status", "UNKNOWN")).upper()
        if status_upper not in TERMINAL_BATCH_STATUSES:
            return {"batch_id": batch_id, "deleted": False, "reason": f"NONTERMINAL:{status_upper}"}
        err_fid = obj.get("error_file_id")
        if isinstance(err_fid, str) and err_fid:
            self.delete_file(err_fid)
        return {
            "batch_id": batch_id,
            "deleted": True,
            "cleanup_mode": "OPENAI_TERMINAL_BATCH_IMMUTABLE_FILES_DELETED",
        }


class AnthropicBatchLiveTransport(_BaseHttpsBatchClient):
    """Live Anthropic /v1/messages/batches transport implementing LiveBatchReconcileProtocol & 29-day delete."""

    can_submit_billable_batches: bool = True
    is_offline_mock_transport: bool = False

    def __init__(
        self,
        *,
        secret_resolver: Callable[[str], str],
        url_opener: UrlOpener | None = None,
        api_base: str = ANTHROPIC_API_BASE,
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            provider="anthropic",
            api_base=api_base,
            secret_resolver=secret_resolver,
            url_opener=url_opener,
            timeout_seconds=timeout_seconds,
        )

    def submit_batch(
        self,
        *,
        run_id: str,
        client_idempotency_key: str,
        wire_items: Sequence[Mapping[str, Any]],
        expected_snapshot_id: str | None = None,
        on_before_batch_create: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        del run_id, client_idempotency_key, expected_snapshot_id
        if not wire_items:
            raise ValueError("CANNOT_SUBMIT_EMPTY_ANTHROPIC_BATCH")
        requests_payload: list[dict[str, Any]] = []
        for it in wire_items:
            cid = str(it.get("custom_id", ""))
            if not LIVE_CUSTOM_ID_SAFE_RE.fullmatch(cid):
                raise ValueError(f"UNSAFE_ANTHROPIC_CUSTOM_ID:{cid!r}")
            assert_cloud_payload_v_boundary(it)
            # Anthropic /v1/messages/batches rejects params.anthropic_version (sent via HTTP header only).
            clean_params = copy.deepcopy(dict(it["params"]))
            clean_params.pop("anthropic_version", None)
            requests_payload.append({"custom_id": cid, "params": clean_params})
        if on_before_batch_create is not None:
            on_before_batch_create()
        _st, obj = self._request_json(
            method="POST",
            url_or_path="/v1/messages/batches",
            operation="create_message_batch",
            json_body={"requests": requests_payload},
        )
        return {
            "provider": "anthropic",
            "batch_id": str(obj["id"]),
            "batch_status": str(obj.get("processing_status", "IN_PROGRESS")).upper(),
            "input_file_id": None,
            "output_file_id": None,
        }

    @staticmethod
    def _batch_total_request_count(batch_obj: Mapping[str, Any]) -> int:
        rc = batch_obj.get("request_counts") or {}
        if not isinstance(rc, Mapping):
            return 0
        return sum(
            int(rc.get(k) or 0)
            for k in ("processing", "succeeded", "errored", "canceled", "expired")
        )

    def lookup_batch_by_idempotency_key(
        self,
        idempotency_key: str,
        *,
        expected_custom_ids: Sequence[str] | None = None,
        dispatch_tag: str | None = None,
        intent_created_at_utc: str | None = None,
    ) -> dict[str, Any]:
        del idempotency_key
        if not expected_custom_ids:
            return {"found": False, "authoritative_non_acceptance": False}

        expected_wire: set[str] = set()
        for raw_cid in expected_custom_ids:
            canon = canonicalize_custom_id(str(raw_cid))
            if "::" in canon:
                pkt_u, order_p = canon.split("::", 1)
                expected_wire.add(to_wire_custom_id(pkt_u, order_p, dispatch_tag=dispatch_tag))
            else:
                expected_wire.add(str(raw_cid))

        intent_ts = _parse_iso_unix(intent_created_at_utc)
        exact_matches: list[Mapping[str, Any]] = []
        after_id: str | None = None
        for _page in range(5):
            path = "/v1/messages/batches?limit=100" + (f"&after_id={after_id}" if after_id else "")
            _st, page = self._request_json(method="GET", url_or_path=path, operation="list_message_batches")
            data = page.get("data") or []
            if isinstance(data, list):
                for b in data:
                    if not isinstance(b, Mapping):
                        continue
                    b_ts = _parse_iso_unix(b.get("created_at"))
                    if intent_ts is not None and b_ts is not None and b_ts < (intent_ts - 300.0):
                        continue
                    if self._batch_total_request_count(b) != len(expected_wire):
                        continue
                    # Fail-closed: NEVER guess an IN_PROGRESS batch by created_at + item count!
                    if str(b.get("processing_status", "")).upper() != "ENDED" or not isinstance(b.get("results_url"), str):
                        continue
                    out = self.fetch_batch_outcome(str(b["id"]))
                    got_wire = {str(it.get("wire_custom_id") or "") for it in out.get("items", [])}
                    if got_wire == expected_wire:
                        exact_matches.append(b)
            if not page.get("has_more") or not data:
                break
            after_id = str(data[-1]["id"])

        if len(exact_matches) == 1:
            matched = exact_matches[0]
            return {
                "found": True,
                "batch_id": str(matched["id"]),
                "batch_status": "ENDED",
            }
        # Zero matches or >1 ambiguous ended match: keep reserve fail-closed until verified!
        return {"found": False, "authoritative_non_acceptance": False}

    def fetch_batch_outcome(self, batch_id: str) -> dict[str, Any]:
        _st, obj = self._request_json(
            method="GET",
            url_or_path=f"/v1/messages/batches/{batch_id}",
            operation="get_message_batch",
        )
        status_upper = str(obj.get("processing_status", "UNKNOWN")).upper()
        base = {
            "provider": "anthropic",
            "batch_id": str(obj.get("id", batch_id)),
            "batch_status": status_upper,
            "input_file_id": None,
            "output_file_id": None,
            "results_url": obj.get("results_url"),
            "request_counts": obj.get("request_counts"),
        }
        if status_upper != "ENDED":
            return {**base, "items": []}

        results_url = obj.get("results_url") or f"/v1/messages/batches/{batch_id}/results"
        status, _rh, raw = self._request_bytes(
            method="GET",
            url_or_path=str(results_url),
            operation="download_message_batch_results",
            headers={"Accept": "application/x-jsonl"},
        )
        if status != 200:
            secret = self._secret_resolver("anthropic")
            raise LiveTransportError(
                "anthropic", "download_message_batch_results", status, redact_secret_text(raw.decode("utf-8", errors="replace")[:400], (secret,))
            )

        parsed_items: list[dict[str, Any]] = []
        for ln in raw.decode("utf-8").splitlines():
            stripped = ln.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            wire_cid = str(row.get("custom_id", ""))
            canon_cid = canonicalize_custom_id(wire_cid)
            res = row.get("result") or {}
            res_type = res.get("type") if isinstance(res, Mapping) else None
            if res_type == "succeeded" and isinstance(res.get("message"), Mapping):
                msg = res["message"]
                usage = _valid_int_usage(msg.get("usage"))
                snap = msg.get("model")
                raw_text = _extract_anthropic_response_text(msg)
                parsed_resp: dict[str, Any] | None = None
                err_code: str | None = None
                try:
                    parsed_resp = _parse_judge_json_strict(raw_text)
                except ValueError as exc:
                    err_code = f"MALFORMED_JSON_OUTPUT:{exc}"
                parsed_items.append(
                    {
                        "custom_id": canon_cid,
                        "wire_custom_id": wire_cid,
                        "model_snapshot_id": str(snap) if isinstance(snap, str) and snap else None,
                        "usage": usage,
                        "parsed_response": parsed_resp,
                        "raw_text": raw_text,
                        "provider_error": err_code,
                    }
                )
            else:
                parsed_items.append(
                    {
                        "custom_id": canon_cid,
                        "wire_custom_id": wire_cid,
                        "model_snapshot_id": None,
                        "usage": None,
                        "parsed_response": None,
                        "raw_text": "",
                        "provider_error": res if res else f"ANTHROPIC_RESULT_{res_type}",
                    }
                )
        return {**base, "items": parsed_items}

    def delete_batch(self, batch_id: str) -> dict[str, Any]:
        _st, obj = self._request_json(
            method="DELETE",
            url_or_path=f"/v1/messages/batches/{batch_id}",
            operation="delete_message_batch",
            allow_statuses=(200, 404),
        )
        if _st == 404:
            return {"batch_id": batch_id, "deleted": True, "already_absent": True}
        ok = obj.get("type") == "message_batch_deleted" or obj.get("id") == batch_id
        return {"batch_id": batch_id, "deleted": bool(ok)}

    def delete_file(self, file_id: str) -> dict[str, Any]:
        return {"file_id": file_id, "deleted": True, "note": "anthropic_inline_requests_no_file"}


class _CompositeLiveReconcileRouter:
    """Routes P1-C reconcile_stage1_crash_intents calls to the owning provider transport."""

    def __init__(
        self,
        *,
        ledger_path: Path,
        transports_by_provider: Mapping[str, Any],
        on_terminal_outcome: Callable[[str, dict[str, Any]], None] | None = None,
        active_reconcile_providers: Sequence[str] | None = None,
    ) -> None:
        self.ledger_path = ledger_path
        self.transports = dict(transports_by_provider)
        self.on_terminal_outcome = on_terminal_outcome
        self.active_reconcile_providers: set[str] | None = (
            {str(p) for p in active_reconcile_providers} if active_reconcile_providers is not None else None
        )
        self.captured_outcomes: dict[str, dict[str, Any]] = {}
        self.cleanup_log: list[dict[str, Any]] = []
        self.file_cleanup_updates: dict[str, dict[str, Any]] = {}
        self._cleanup_sidecar_path = ledger_path.with_name(f"{ledger_path.name}.file_cleanup.json")

    def _read_cleanup_sidecar(self) -> dict[str, dict[str, Any]]:
        if not self._cleanup_sidecar_path.is_file():
            return {}
        data = json.loads(self._cleanup_sidecar_path.read_text(encoding="utf-8"))
        return dict(data) if isinstance(data, dict) else {}

    def _write_cleanup_sidecar_entry(self, idempotency_key: str, entry: Mapping[str, Any]) -> None:
        all_entries = self._read_cleanup_sidecar()
        all_entries[idempotency_key] = dict(entry)
        _save_json_atomic(self._cleanup_sidecar_path, all_entries)

    def _delete_cleanup_sidecar_entry(self, idempotency_key: str) -> None:
        if not self._cleanup_sidecar_path.is_file():
            return
        all_entries = self._read_cleanup_sidecar()
        if idempotency_key in all_entries:
            all_entries.pop(idempotency_key, None)
            _save_json_atomic(self._cleanup_sidecar_path, all_entries)

    def _read_intents(self) -> dict[str, Any]:
        if not self.ledger_path.is_file():
            return {}
        data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        return dict(data.get("intents") or {})

    def _provider_for_batch_id(self, batch_id: str) -> str:
        for ent in self._read_intents().values():
            if ent.get("batch_id") == batch_id:
                return str(ent["provider"])
        if batch_id.startswith("msgbatch_"):
            return "anthropic"
        if batch_id.startswith("batch_"):
            return "openai"
        raise RuntimeError(f"UNKNOWN_PROVIDER_FOR_BATCH_ID:{batch_id!r}")

    def _provider_for_file_id(self, file_id: str) -> str:
        for ent in self._read_intents().values():
            if file_id in (ent.get("input_file_id"), ent.get("output_file_id"), ent.get("error_file_id")):
                return str(ent["provider"])
        if file_id.startswith("file-"):
            return "openai"
        return "openai"

    def lookup_batch_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any]:
        ent = self._read_intents().get(idempotency_key)
        if not isinstance(ent, Mapping):
            return {"found": False, "authoritative_non_acceptance": False}
        prov = str(ent["provider"])
        if self.active_reconcile_providers is not None and prov not in self.active_reconcile_providers:
            return {"found": False, "authoritative_non_acceptance": False}
        tr = self.transports[prov]
        if prov == "anthropic" and isinstance(tr, AnthropicBatchLiveTransport):
            return tr.lookup_batch_by_idempotency_key(
                idempotency_key,
                expected_custom_ids=ent.get("submitted_custom_ids") or ent.get("custom_ids"),
                dispatch_tag=ent.get("wire_dispatch_tag"),
                intent_created_at_utc=ent.get("dispatch_stage_updated_at_utc") or ent.get("created_at_utc"),
            )
        res = tr.lookup_batch_by_idempotency_key(idempotency_key)
        if res.get("found"):
            if not res.get("input_file_id") and ent.get("input_file_id"):
                res = {**res, "input_file_id": ent["input_file_id"]}
            return res

        d_stage = str(ent.get("dispatch_stage") or "")
        in_fid = ent.get("input_file_id")
        if prov == "openai" and d_stage in (
            "PRE_SUBMIT_RESERVED",
            "UPLOAD_IN_FLIGHT",
            "INPUT_FILE_UPLOADED_PRE_BATCH_POST",
            "BATCH_CREATE_4XX_REJECTED",
        ):
            sidecar_ent = self._read_cleanup_sidecar().get(idempotency_key) or {}
            if d_stage == "PRE_SUBMIT_RESERVED" and not in_fid and not ent.get("pending_cleanup_file_ids") and not sidecar_ent.get("pending_cleanup_file_ids"):
                self.file_cleanup_updates[idempotency_key] = {
                    "file_cleanup_status": "NONE_PRE_UPLOAD",
                    "pending_cleanup_file_ids": [],
                    "cleaned_file_ids": [],
                }
                return {
                    "found": False,
                    "authoritative_non_acceptance": True,
                    "non_acceptance_evidence": "pre_upload_abort_no_remote_file",
                }

            cleaned_ids = list(
                dict.fromkeys(
                    str(x)
                    for x in ([*(ent.get("cleaned_file_ids") or []), *(sidecar_ent.get("cleaned_file_ids") or [])])
                    if x
                )
            )
            cleaned_set = set(cleaned_ids)
            pending_candidates: list[str] = [
                *(ent.get("pending_cleanup_file_ids") or []),
                *(sidecar_ent.get("pending_cleanup_file_ids") or []),
            ]
            if isinstance(in_fid, str) and in_fid:
                pending_candidates.append(in_fid)
            pending_ids = list(
                dict.fromkeys(str(x) for x in pending_candidates if isinstance(x, str) and x and x not in cleaned_set)
            )

            upload_fn = str(
                ent.get("input_upload_filename")
                or sidecar_ent.get("input_upload_filename")
                or openai_upload_filename_for_intent(idempotency_key)
            )
            exhaustive_done = bool(
                ent.get("file_reconcile_exhaustive") or sidecar_ent.get("file_reconcile_exhaustive")
            )
            stop_reason: str | None = (
                ent.get("file_reconcile_stop_reason") or sidecar_ent.get("file_reconcile_stop_reason")
            )

            if d_stage == "UPLOAD_IN_FLIGHT" and not exhaustive_done:
                if not hasattr(tr, "lookup_uploaded_files_by_filename"):
                    chk = {
                        "input_upload_filename": upload_fn,
                        "pending_cleanup_file_ids": pending_ids,
                        "cleaned_file_ids": cleaned_ids,
                        "file_reconcile_exhaustive": False,
                        "file_reconcile_stop_reason": "LIST_FILES_UNSUPPORTED",
                        "file_cleanup_status": "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE",
                    }
                    self._write_cleanup_sidecar_entry(idempotency_key, chk)
                    self.file_cleanup_updates[idempotency_key] = chk
                    return {"found": False, "authoritative_non_acceptance": False}

                # Use ONLY fixed upload_started_at_utc anchor; for older ledgers missing it, rely strictly
                # on saved input_upload_filename without excluding files by mutable checkpoint timestamps.
                upload_started_raw = ent.get("upload_started_at_utc") or sidecar_ent.get("upload_started_at_utc")
                created_unix = _parse_iso_unix(upload_started_raw) if isinstance(upload_started_raw, str) else None
                try:
                    scan_res = tr.lookup_uploaded_files_by_filename(
                        upload_fn, created_after_unix=created_unix
                    )
                except LiveTransportError as exc:
                    chk = {
                        "input_upload_filename": upload_fn,
                        "pending_cleanup_file_ids": pending_ids,
                        "cleaned_file_ids": cleaned_ids,
                        "file_reconcile_exhaustive": False,
                        "file_reconcile_stop_reason": f"LIST_FILES_ERROR:{exc.status_code or 'NETWORK'}",
                        "file_cleanup_status": "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE",
                    }
                    self._write_cleanup_sidecar_entry(idempotency_key, chk)
                    self.file_cleanup_updates[idempotency_key] = chk
                    return {"found": False, "authoritative_non_acceptance": False}

                matched_files = scan_res.get("files") if isinstance(scan_res, Mapping) else scan_res
                exhaustive_done = bool(scan_res.get("exhaustive")) if isinstance(scan_res, Mapping) else False
                stop_reason = str(scan_res.get("stop_reason") or "UNKNOWN") if isinstance(scan_res, Mapping) else "UNKNOWN"
                for fobj in (matched_files or []):
                    if isinstance(fobj, Mapping) and isinstance(fobj.get("id"), str) and fobj["id"]:
                        fid_found = str(fobj["id"])
                        if fid_found not in cleaned_set and fid_found not in pending_ids:
                            pending_ids.append(fid_found)

            def _persist_cleanup_checkpoint(*, status_str: str, d_stage_out: str | None = None) -> dict[str, Any]:
                rep_fid = pending_ids[0] if pending_ids else (cleaned_ids[-1] if cleaned_ids else in_fid)
                chk_obj: dict[str, Any] = {
                    "input_upload_filename": upload_fn,
                    "pending_cleanup_file_ids": list(pending_ids),
                    "cleaned_file_ids": list(cleaned_ids),
                    "file_reconcile_exhaustive": exhaustive_done if d_stage == "UPLOAD_IN_FLIGHT" else True,
                    "file_reconcile_stop_reason": stop_reason or ("END_OF_LIST" if d_stage != "UPLOAD_IN_FLIGHT" else "UNKNOWN"),
                    "file_cleanup_status": status_str,
                }
                if isinstance(rep_fid, str) and rep_fid:
                    chk_obj["input_file_id"] = rep_fid
                if d_stage_out is not None:
                    chk_obj["dispatch_stage"] = d_stage_out
                self._write_cleanup_sidecar_entry(idempotency_key, chk_obj)
                self.file_cleanup_updates[idempotency_key] = chk_obj
                return chk_obj

            # Durably persist ALL pending IDs BEFORE attempting any delete_file calls.
            _persist_cleanup_checkpoint(status_str="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE")

            for m_fid in list(pending_ids):
                try:
                    del_res = self.delete_file(m_fid)
                except LiveTransportError:
                    _persist_cleanup_checkpoint(status_str="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE")
                    continue
                if del_res.get("deleted"):
                    pending_ids = [x for x in pending_ids if x != m_fid]
                    if m_fid not in cleaned_set:
                        cleaned_ids.append(m_fid)
                        cleaned_set.add(m_fid)
                    _persist_cleanup_checkpoint(status_str="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE")
                else:
                    _persist_cleanup_checkpoint(status_str="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE")

            # Mark verified/released ONLY once ALL pending files are deleted AND UPLOAD_IN_FLIGHT scan was exhaustive!
            if pending_ids or (d_stage == "UPLOAD_IN_FLIGHT" and not exhaustive_done):
                _persist_cleanup_checkpoint(status_str="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE")
                return {"found": False, "authoritative_non_acceptance": False}

            if cleaned_ids:
                d_stage_out = "INPUT_FILE_UPLOADED_PRE_BATCH_POST" if d_stage == "UPLOAD_IN_FLIGHT" else None
                _persist_cleanup_checkpoint(status_str="CLEANED_ORPHAN_FILE_VERIFIED", d_stage_out=d_stage_out)
                return {
                    "found": False,
                    "authoritative_non_acceptance": True,
                    "non_acceptance_evidence": f"pre_batch_abort_cleaned_input_files:{','.join(cleaned_ids)}",
                }

            _persist_cleanup_checkpoint(status_str="VERIFIED_NO_REMOTE_FILE")
            return {
                "found": False,
                "authoritative_non_acceptance": True,
                "non_acceptance_evidence": f"upload_in_flight_verified_absent_on_provider:{upload_fn}",
            }
        return res

    def fetch_batch_outcome(self, batch_id: str) -> dict[str, Any]:
        prov = self._provider_for_batch_id(batch_id)
        if self.active_reconcile_providers is not None and prov not in self.active_reconcile_providers:
            # Deferred provider (e.g., OpenAI active batch during Anthropic-only recovery): zero HTTP, reserve kept.
            return {"provider": prov, "batch_id": batch_id, "batch_status": "IN_PROGRESS", "items": []}
        outcome = self.transports[prov].fetch_batch_outcome(batch_id)
        status_upper = str(outcome.get("batch_status", "UNKNOWN")).upper()
        if status_upper in TERMINAL_BATCH_STATUSES:
            # Persist local responses & canonical-S validation BEFORE reconcile_stage1_crash_intents runs delete cleanup!
            if self.on_terminal_outcome is not None:
                self.on_terminal_outcome(prov, outcome)
            self.captured_outcomes[batch_id] = outcome
        return outcome

    def delete_batch(self, batch_id: str) -> dict[str, Any]:
        prov = self._provider_for_batch_id(batch_id)
        res = self.transports[prov].delete_batch(batch_id)
        self.cleanup_log.append({"kind": "batch", "provider": prov, "id": batch_id, **res})
        return res

    def delete_file(self, file_id: str) -> dict[str, Any]:
        prov = self._provider_for_file_id(file_id)
        res = self.transports[prov].delete_file(file_id)
        self.cleanup_log.append({"kind": "file", "provider": prov, "id": file_id, **res})
        return res


def _validate_live_output_dir(output_dir: Path) -> Path:
    for cand in (output_dir, *output_dir.parents):
        if cand.exists():
            _assert_not_symlink_or_reparse(cand)
    resolved = output_dir.resolve()
    _assert_path_outside_repositories(resolved)
    return resolved


def _load_or_init_run_manifest(
    *,
    manifest_path: Path,
    slice_mode: str,
    queries: Sequence[Mapping[str, Any]],
    prompt_pins: Mapping[str, str],
) -> dict[str, Any]:
    if manifest_path.is_file():
        _assert_not_symlink_or_reparse(manifest_path)
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("schema_version") != DEV5_RUN_MANIFEST_SCHEMA:
            raise ValueError(f"INVALID_RUN_MANIFEST_SCHEMA:{existing.get('schema_version')!r}")
        if existing.get("system_prompt_sha256") != prompt_pins["system_prompt_sha256"]:
            raise PermissionError("EXISTING_RUN_MANIFEST_PROMPT_SHA_MISMATCH")
        return existing

    qids = [str(q["query_id"]) for q in queries]
    queries_digest = sha256_bytes(json.dumps(qids, separators=(",", ":")).encode("utf-8"))
    packet_salt = sha256_bytes(
        f"GOMATE_W07_DEV5_PACKET_SALT|{EXPECTED_V_CORPUS_SHA256}|{queries_digest}".encode("utf-8")
    )[:32]
    manifest = {
        "schema_version": DEV5_RUN_MANIFEST_SCHEMA,
        "created_at_utc": _utc_now_iso(),
        "initial_slice_mode": slice_mode,
        "approved_query_ids": qids,
        "corpus_v_sha256": EXPECTED_V_CORPUS_SHA256,
        "packet_salt": packet_salt,
        "run_nonce_seed": os.urandom(16).hex(),
        **dict(prompt_pins),
    }
    _save_json_atomic(manifest_path, manifest)
    return manifest


_ANTHROPIC_EXTRA_INPUT_ERROR_SIGNATURE = "anthropic_version: Extra inputs are not permitted (invalid_request_error)"


def _is_recoverable_anthropic_extra_input_error_row(rec: Mapping[str, Any]) -> bool:
    lv = rec.get("local_validation") or {}
    if lv.get("state") != "ERROR":
        return False
    err_text = f"{lv.get('error_code') or ''} {rec.get('provider_error') or ''}"
    if "anthropic_version" in err_text and (
        "Extra inputs are not permitted" in err_text or "invalid_request_error" in err_text
    ):
        return True
    return str(lv.get("error_code") or "") == "BATCH_ABORT_EXCESSIVE_RETRY_RATE"


def _validate_anthropic_recovery_targets(
    *,
    recover_batch_ids: Sequence[str],
    ledger: Mapping[str, Any],
    raw_log_path: Path,
    clean_out: Path,
) -> tuple[tuple[str, ...], list[dict[str, Any]]]:
    """Fail-closed validation that requested Anthropic recovery batch ID(s) failed strictly on anthropic_version extra input."""
    norm_bids = tuple(dict.fromkeys(str(b).strip() for b in recover_batch_ids if str(b).strip()))
    if not norm_bids:
        return (), []
    if not raw_log_path.is_file():
        raise FileNotFoundError(f"MISSING_ANTHROPIC_RAW_LOG_FOR_RECOVERY:{raw_log_path}")

    rows_by_batch: dict[str, list[dict[str, Any]]] = {}
    for ln in raw_log_path.read_text(encoding="utf-8").splitlines():
        stripped = ln.strip()
        if not stripped:
            continue
        rec = json.loads(stripped)
        if rec.get("event_type") == "ITEM_ATTEMPT":
            rows_by_batch.setdefault(str(rec.get("batch_id") or ""), []).append(rec)

    clean_out_str = str(clean_out)
    intents = ledger.get("intents") or {}
    lineage: list[dict[str, Any]] = []
    for old_bid in norm_bids:
        matched_intent: tuple[str, Mapping[str, Any]] | None = None
        for ik, irec in sorted(intents.items()):
            if irec.get("provider") == "anthropic" and irec.get("batch_id") == old_bid:
                matched_intent = (ik, irec)
                break
        if matched_intent is None:
            raise KeyError(f"UNKNOWN_ANTHROPIC_RECOVERY_BATCH_ID:{old_bid}")
        old_k, old_ent = matched_intent
        src_dir = old_ent.get("source_output_dir")
        if isinstance(src_dir, str) and src_dir and src_dir != clean_out_str:
            raise PermissionError(f"RECOVERY_BATCH_OUTPUT_DIR_MISMATCH:{old_bid}:{src_dir}!={clean_out_str}")
        st = str(old_ent.get("status", ""))
        if st in _ACTIVE_INTENT_STATUSES or st.startswith("NONTERMINAL_RESERVED_"):
            raise PermissionError(f"RECOVERY_TARGET_BATCH_STILL_ACTIVE:{old_bid}:{st}")

        b_rows = rows_by_batch.get(old_bid, [])
        if not b_rows:
            raise ValueError(f"NO_RAW_LOG_RECORDS_FOR_RECOVERY_BATCH:{old_bid}")
        has_version_err_sig = any(
            "anthropic_version"
            in f"{(r.get('local_validation') or {}).get('error_code') or ''} {r.get('provider_error') or ''}"
            and "Extra inputs are not permitted"
            in f"{(r.get('local_validation') or {}).get('error_code') or ''} {r.get('provider_error') or ''}"
            for r in b_rows
        )
        if not has_version_err_sig or not all(_is_recoverable_anthropic_extra_input_error_row(r) for r in b_rows):
            raise PermissionError(f"RECOVERY_TARGET_BATCH_INELIGIBLE:{old_bid}")

        lineage.append(
            {
                "supersedes_batch_id": old_bid,
                "supersedes_intent_key": old_k,
                "supersedes_run_id": old_ent.get("run_id"),
                "supersedes_status": st,
                "supersedes_confirmed_cost_usd": old_ent.get("confirmed_cost_usd"),
                "historical_row_count": len(b_rows),
                "failed_item_count": len({canonicalize_custom_id(str(r["custom_id"])) for r in b_rows}),
                "error_signature": _ANTHROPIC_EXTRA_INPUT_ERROR_SIGNATURE,
            }
        )
    return norm_bids, lineage


def _ledger_recovery_superseded_pairs(ledger: Mapping[str, Any], prov: str) -> list[tuple[str, str]]:
    """Collect (old_batch_id, canonical_custom_id) pairs linked by accepted recovery intents in ledger."""
    pairs: list[tuple[str, str]] = []
    for ent in (ledger.get("intents") or {}).values():
        if ent.get("provider") != prov or ent.get("status") == "CANCELLED_UNSUBMITTED":
            continue
        sup_bids = ent.get("supersedes_batch_ids") or []
        sub_cids = ent.get("submitted_custom_ids") or ent.get("custom_ids") or []
        if sup_bids and sub_cids:
            for sb in sup_bids:
                for raw_c in sub_cids:
                    pairs.append((str(sb), canonicalize_custom_id(str(raw_c))))
    return pairs


def _load_raw_log_batch_state(
    raw_log_path: Path,
    *,
    superseded_batch_ids: Sequence[str] = (),
    superseded_batch_item_pairs: Sequence[tuple[str, str]] = (),
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, int],
    set[str],
    dict[tuple[str, str], list[dict[str, Any]]],
]:
    """Load settled items, attempt counts, retried custom_ids, and per-(batch_id, custom_id) rows."""
    settled: dict[str, dict[str, Any]] = {}
    attempts: dict[str, int] = {}
    retried_cids: set[str] = set()
    by_batch_cid: dict[tuple[str, str], list[dict[str, Any]]] = {}
    if not raw_log_path.is_file():
        return settled, attempts, retried_cids, by_batch_cid

    sup_batches: set[str] = {str(b) for b in superseded_batch_ids if b}
    sup_pairs: set[tuple[str, str]] = {
        (str(b), canonicalize_custom_id(str(c))) for b, c in superseded_batch_item_pairs if b and c
    }
    item_rows: list[dict[str, Any]] = []
    for ln in raw_log_path.read_text(encoding="utf-8").splitlines():
        stripped = ln.strip()
        if not stripped:
            continue
        rec = json.loads(stripped)
        ev_type = rec.get("event_type")
        if ev_type == "ANTHROPIC_RECOVERY_EPOCH":
            sbids = list(rec.get("supersedes_batch_ids") or [])
            if not sbids and rec.get("supersedes_batch_id"):
                sbids = [rec["supersedes_batch_id"]]
            rcids = rec.get("recovered_custom_ids")
            if isinstance(rcids, list) and rcids:
                for sb in sbids:
                    for c in rcids:
                        sup_pairs.add((str(sb), canonicalize_custom_id(str(c))))
            else:
                for sb in sbids:
                    sup_batches.add(str(sb))
            continue
        if ev_type == "ITEM_ATTEMPT":
            item_rows.append(rec)

    for rec in item_rows:
        cid = canonicalize_custom_id(str(rec["custom_id"]))
        b_id = str(rec.get("batch_id") or "")
        by_batch_cid.setdefault((b_id, cid), []).append(rec)
        if b_id in sup_batches or (b_id, cid) in sup_pairs:
            continue
        attempts[cid] = attempts.get(cid, 0) + 1
        if rec.get("attempt_no", 1) > 1:
            retried_cids.add(cid)
        if rec.get("final_for_item"):
            settled[cid] = rec
    return settled, attempts, retried_cids, by_batch_cid


def _load_raw_log_index(
    raw_log_path: Path,
    *,
    superseded_batch_ids: Sequence[str] = (),
    superseded_batch_item_pairs: Sequence[tuple[str, str]] = (),
) -> tuple[dict[str, dict[str, Any]], dict[str, int], set[str]]:
    """Load settled items and attempt counts from append-only raw JSONL log."""
    settled, attempts, retried_cids, _by_batch_cid = _load_raw_log_batch_state(
        raw_log_path,
        superseded_batch_ids=superseded_batch_ids,
        superseded_batch_item_pairs=superseded_batch_item_pairs,
    )
    return settled, attempts, retried_cids


def _resolve_verified_phase2_and_rates(
    *,
    activation_pack_dir: Path,
    external_trust_root_dir: Path,
    rate_evidence_path: Path,
    out_of_band_owner_pubkey_sha256: str | None,
    out_of_band_auditor_pubkey_sha256: str | None,
    out_of_band_manifest_sha256: str | None,
    out_of_band_auditor_report_sha256: str | None,
    expected_target_zip_sha256: str | None,
    raw_probe_transcript_path: Path | None,
    requested_dev_cap_usd: float,
    requested_total_cap_usd: float,
    rate_profiles_override: Mapping[str, ProviderRateProfile] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, ProviderRateProfile]]:
    if requested_dev_cap_usd > DEFAULT_DEV_CANARY_HARD_CAP_USD:
        raise PermissionError(f"HOLD_DEV_CAP_CANNOT_EXCEED_2_USD:{requested_dev_cap_usd}")
    auth = authorize_stage1_live_canary_gate(
        activation_pack_dir=activation_pack_dir,
        external_trust_root_dir=external_trust_root_dir,
        out_of_band_owner_pubkey_sha256=out_of_band_owner_pubkey_sha256,
        out_of_band_auditor_pubkey_sha256=out_of_band_auditor_pubkey_sha256,
        out_of_band_manifest_sha256=out_of_band_manifest_sha256,
        out_of_band_auditor_report_sha256=out_of_band_auditor_report_sha256,
        expected_target_zip_sha256=expected_target_zip_sha256,
        raw_probe_transcript_path=raw_probe_transcript_path,
        requested_dev_cap_usd=requested_dev_cap_usd,
        requested_total_cap_usd=requested_total_cap_usd,
    )
    if not auth.get("batch_generation_authorized"):
        raise PermissionError("HOLD_STAGE1_BATCH_GENERATION_NOT_AUTHORIZED")

    pinned_snaps = auth["judge_snapshots_pinned"]
    rate_ev = verify_stage1_rate_evidence_artifact(
        rate_evidence_path,
        expected_judge_snapshots=pinned_snaps,
    )
    prov_recs = rate_ev["providers"]
    derived_rates = {
        "openai": ProviderRateProfile(
            provider="openai",
            model_id=str(pinned_snaps["judge_A"]),
            expected_snapshot_id=str(prov_recs["openai"]["model_snapshot_id"]),
            batch_input_usd_per_1m=float(prov_recs["openai"]["batch_input_usd_per_1m"]),
            batch_output_usd_per_1m=float(prov_recs["openai"]["batch_output_usd_per_1m"]),
        ),
        "anthropic": ProviderRateProfile(
            provider="anthropic",
            model_id=str(pinned_snaps["judge_B"]),
            expected_snapshot_id=str(prov_recs["anthropic"]["model_snapshot_id"]),
            batch_input_usd_per_1m=float(prov_recs["anthropic"]["batch_input_usd_per_1m"]),
            batch_output_usd_per_1m=float(prov_recs["anthropic"]["batch_output_usd_per_1m"]),
        ),
    }
    if rate_profiles_override is not None:
        for prov in ("openai", "anthropic"):
            if prov in rate_profiles_override:
                cand = rate_profiles_override[prov]
                ref = derived_rates[prov]
                if (
                    cand.expected_snapshot_id != ref.expected_snapshot_id
                    or abs(cand.batch_input_usd_per_1m - ref.batch_input_usd_per_1m) > 1e-12
                    or abs(cand.batch_output_usd_per_1m - ref.batch_output_usd_per_1m) > 1e-12
                ):
                    raise PermissionError(f"RATE_OR_SNAPSHOT_MISMATCH_WITH_SIGNED_RECEIPT:{prov}")
                derived_rates[prov] = cand

    return auth, rate_ev, derived_rates


def inspect_stage1_dev5_live_readiness(
    *,
    activation_pack_dir: Path,
    external_trust_root_dir: Path,
    dev5_root: Path,
    corpus_docs: Sequence[Mapping[str, Any]],
    queries_json_path: Path,
    rate_evidence_path: Path,
    output_dir: Path,
    shared_budget_ledger_path: Path | None = None,
    slice_mode: str = "dev5_plus_20pct_swap",
    providers: Sequence[str] = ("openai", "anthropic"),
    canary_1x10_doc_ids: Sequence[str] | None = None,
    recover_anthropic_extra_input_batch_ids: Sequence[str] = (),
    vault_path: Path | None = None,
    out_of_band_owner_pubkey_sha256: str | None = None,
    out_of_band_auditor_pubkey_sha256: str | None = None,
    out_of_band_manifest_sha256: str | None = None,
    out_of_band_auditor_report_sha256: str | None = None,
    expected_target_zip_sha256: str | None = None,
    raw_probe_transcript_path: Path | None = None,
    requested_dev_cap_usd: float = PA1_DEV_HARD_CAP_USD,
    requested_total_cap_usd: float = PA1_TOTAL_HARD_CAP_USD,
) -> dict[str, Any]:
    """Read-only ($0.00 / zero HTTP calls) inspection of Phase-2 gates, approved DEV5 items, and spend ledger."""
    for prov in providers:
        if prov not in ("openai", "anthropic"):
            raise ValueError(f"UNSUPPORTED_LIVE_STAGE1_PROVIDER:{prov!r}")
    if recover_anthropic_extra_input_batch_ids and tuple(providers) != ("anthropic",):
        raise PermissionError("ANTHROPIC_RECOVERY_REQUIRES_PROVIDERS_ANTHROPIC_ONLY")

    clean_out = _validate_live_output_dir(output_dir)
    ledger_path = resolve_stage1_shared_budget_ledger_path(shared_budget_ledger_path=shared_budget_ledger_path)
    auth, rate_ev, rate_profiles = _resolve_verified_phase2_and_rates(
        activation_pack_dir=activation_pack_dir,
        external_trust_root_dir=external_trust_root_dir,
        rate_evidence_path=rate_evidence_path,
        out_of_band_owner_pubkey_sha256=out_of_band_owner_pubkey_sha256,
        out_of_band_auditor_pubkey_sha256=out_of_band_auditor_pubkey_sha256,
        out_of_band_manifest_sha256=out_of_band_manifest_sha256,
        out_of_band_auditor_report_sha256=out_of_band_auditor_report_sha256,
        expected_target_zip_sha256=expected_target_zip_sha256,
        raw_probe_transcript_path=raw_probe_transcript_path,
        requested_dev_cap_usd=requested_dev_cap_usd,
        requested_total_cap_usd=requested_total_cap_usd,
    )
    sys_prompt, schema_s4, prompt_pins = _load_and_verify_prompt_and_schema(dev5_root)
    queries = load_approved_dev5_queries(queries_json_path)
    manifest_file = clean_out / "dev5_run_manifest.json"
    if manifest_file.is_file():
        _assert_not_symlink_or_reparse(manifest_file)
        existing_man = json.loads(manifest_file.read_text(encoding="utf-8"))
        inspect_salt = str(existing_man.get("packet_salt") or "dryrun-inspect-salt")
        inspect_nonce = str(existing_man.get("run_nonce_seed") or "dryrun-inspect-nonce-seed")
    else:
        inspect_salt = "dryrun-inspect-salt"
        inspect_nonce = "dryrun-inspect-nonce-seed"
    items = build_approved_dev5_canary_items(
        dev5_queries=queries,
        corpus_docs=corpus_docs,
        slice_mode=slice_mode,
        packet_salt=inspect_salt,
        run_nonce_seed=inspect_nonce,
        canary_1x10_doc_ids=canary_1x10_doc_ids,
    )

    if ledger_path.is_file():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        pending_intents = {
            k: v
            for k, v in (ledger.get("intents") or {}).items()
            if str(v.get("status", "")) in _ACTIVE_INTENT_STATUSES
            or str(v.get("status", "")).startswith("NONTERMINAL_RESERVED_")
        }
    else:
        ledger = {
            "exists_on_disk": False,
            "total_confirmed_spent_usd": 0.0,
            "total_unresolved_reserve_usd": 0.0,
            "effective_committed_usd": 0.0,
            "intents": {},
        }
        pending_intents = {}

    validated_recovery_bids, validated_recovery_lineage = _validate_anthropic_recovery_targets(
        recover_batch_ids=recover_anthropic_extra_input_batch_ids,
        ledger=ledger,
        raw_log_path=clean_out / "anthropic_raw_log.jsonl",
        clean_out=clean_out,
    )

    per_provider_plan: dict[str, Any] = {}
    combined_reserve_usd = 0.0
    for prov in providers:
        rp = rate_profiles[prov]
        raw_log = clean_out / f"{prov}_raw_log.jsonl"
        sup_bids = validated_recovery_bids if prov == "anthropic" else ()
        sup_pairs = _ledger_recovery_superseded_pairs(ledger, prov)
        settled_idx, _attempts, _retried = _load_raw_log_index(
            raw_log,
            superseded_batch_ids=sup_bids,
            superseded_batch_item_pairs=sup_pairs,
        )
        to_send = [it for it in items if it["custom_id"] not in settled_idx]
        wire_entries = [
            build_verified_live_wire_item(
                provider=prov,
                model_id=rp.model_id,
                item=it,
                system_prompt=sys_prompt,
                response_schema=schema_s4,
                dispatch_tag="000000",
            )["wire_item"]
            for it in to_send
        ]
        res_est = estimate_batch_worst_case_reserve_usd(provider=prov, wire_items=wire_entries, rate_profile=rp)
        combined_reserve_usd = round(combined_reserve_usd + res_est["reserved_worst_case_usd"], 6)
        per_provider_plan[prov] = {
            "model_id": rp.model_id,
            "expected_snapshot_id": rp.expected_snapshot_id,
            "total_slice_items": len(items),
            "already_settled_items": len(settled_idx),
            "pending_to_send_items": len(wire_entries),
            **res_est,
        }

    eff_now = float(ledger.get("effective_committed_usd", 0.0))
    projected_total_committed = round(eff_now + combined_reserve_usd, 6)
    vp = vault_path or default_dpapi_vault_path()
    vault_posture = inspect_provider_secret_posture(vault_path=vp)

    report_obj: dict[str, Any] = {
        "mode": "DRY_RUN_INSPECT_ZERO_NETWORK",
        "live_api_calls_executed": 0,
        "live_spend_usd": 0.0,
        "phase2_authorization": {
            "gate_phase": auth["gate_phase"],
            "authorized_stage": str(auth.get("authorized_stage") or "STAGE1_DEV_CANARY_ONLY"),
            "batch_generation_authorized": auth["batch_generation_authorized"],
            "selected_cap_regime": auth["selected_cap_regime"],
            "judge_snapshots_pinned": auth["judge_snapshots_pinned"],
        },
        "rate_evidence": {
            "sha256": rate_ev["rate_evidence_sha256"],
            "captured_at_utc": rate_ev["captured_at_utc"],
        },
        "prompt_and_schema_pins": prompt_pins,
        "slice_mode": slice_mode,
        "approved_query_ids": [q["query_id"] for q in queries],
        "output_dir": str(clean_out),
        "shared_budget_ledger_path": str(ledger_path),
        "aggregate_ledger_path": str(ledger_path),
        "existing_ledger_summary": {
            "exists_on_disk": ledger.get("exists_on_disk", True),
            "total_intents": len(ledger.get("intents") or {}),
            "pending_or_nonterminal_intents": pending_intents,
            "total_confirmed_spent_usd": ledger.get("total_confirmed_spent_usd", 0.0),
            "total_unresolved_reserve_usd": ledger.get("total_unresolved_reserve_usd", 0.0),
            "effective_committed_usd": eff_now,
        },
        "planned_batches": per_provider_plan,
        "combined_worst_case_reserve_usd": combined_reserve_usd,
        "projected_total_committed_usd": projected_total_committed,
        "dev_hard_cap_usd": requested_dev_cap_usd,
        "fits_combined_dev_cap": projected_total_committed <= requested_dev_cap_usd + 1e-12,
        "secret_posture_no_values": vault_posture["providers"],
    }
    if validated_recovery_lineage:
        report_obj["recovery_plan"] = {
            "recovery_mode": "ANTHROPIC_EXTRA_INPUT_VERSION_FIX06",
            "target_batches": validated_recovery_lineage,
        }
    return report_obj


def run_stage1_dev5_live_batch(
    *,
    activation_pack_dir: Path,
    external_trust_root_dir: Path,
    dev5_root: Path,
    corpus_docs: Sequence[Mapping[str, Any]],
    queries_json_path: Path,
    rate_evidence_path: Path,
    output_dir: Path,
    shared_budget_ledger_path: Path | None = None,
    slice_mode: str = "dev5_plus_20pct_swap",
    providers: Sequence[str] = ("openai", "anthropic"),
    canary_1x10_doc_ids: Sequence[str] | None = None,
    recover_anthropic_extra_input_batch_ids: Sequence[str] = (),
    allow_live_network: bool = False,
    resume_only: bool = False,
    poll_interval_seconds: float = 15.0,
    max_wait_seconds: float = 300.0,
    sleep_fn: Callable[[float], None] = time.sleep,
    vault_path: Path | None = None,
    transports_by_provider: Mapping[str, Any] | None = None,
    url_opener: UrlOpener | None = None,
    rate_profiles_override: Mapping[str, ProviderRateProfile] | None = None,
    out_of_band_owner_pubkey_sha256: str | None = None,
    out_of_band_auditor_pubkey_sha256: str | None = None,
    out_of_band_manifest_sha256: str | None = None,
    out_of_band_auditor_report_sha256: str | None = None,
    expected_target_zip_sha256: str | None = None,
    raw_probe_transcript_path: Path | None = None,
    requested_dev_cap_usd: float = PA1_DEV_HARD_CAP_USD,
    requested_total_cap_usd: float = PA1_TOTAL_HARD_CAP_USD,
) -> dict[str, Any]:
    """Execute or resume Stage-1 DEV5 live dual-judge batches under fail-closed P0/P1-C controls."""
    if not allow_live_network:
        raise PermissionError("HOLD_STAGE1_LIVE_REQUIRES_ALLOW_LIVE_NETWORK")
    for prov in providers:
        if prov not in ("openai", "anthropic"):
            raise ValueError(f"UNSUPPORTED_LIVE_STAGE1_PROVIDER:{prov!r}")
    if recover_anthropic_extra_input_batch_ids and tuple(providers) != ("anthropic",):
        raise PermissionError("ANTHROPIC_RECOVERY_REQUIRES_PROVIDERS_ANTHROPIC_ONLY")

    clean_out = _validate_live_output_dir(output_dir)
    ledger_path = resolve_stage1_shared_budget_ledger_path(shared_budget_ledger_path=shared_budget_ledger_path)
    auth, rate_ev, rate_profiles = _resolve_verified_phase2_and_rates(
        activation_pack_dir=activation_pack_dir,
        external_trust_root_dir=external_trust_root_dir,
        rate_evidence_path=rate_evidence_path,
        out_of_band_owner_pubkey_sha256=out_of_band_owner_pubkey_sha256,
        out_of_band_auditor_pubkey_sha256=out_of_band_auditor_pubkey_sha256,
        out_of_band_manifest_sha256=out_of_band_manifest_sha256,
        out_of_band_auditor_report_sha256=out_of_band_auditor_report_sha256,
        expected_target_zip_sha256=expected_target_zip_sha256,
        raw_probe_transcript_path=raw_probe_transcript_path,
        requested_dev_cap_usd=requested_dev_cap_usd,
        requested_total_cap_usd=requested_total_cap_usd,
        rate_profiles_override=rate_profiles_override,
    )

    clean_out.mkdir(parents=True, exist_ok=True)
    sys_prompt, schema_s4, prompt_pins = _load_and_verify_prompt_and_schema(dev5_root)
    queries = load_approved_dev5_queries(queries_json_path)
    manifest = _load_or_init_run_manifest(
        manifest_path=clean_out / "dev5_run_manifest.json",
        slice_mode=slice_mode,
        queries=queries,
        prompt_pins=prompt_pins,
    )
    items = build_approved_dev5_canary_items(
        dev5_queries=queries,
        corpus_docs=corpus_docs,
        slice_mode=slice_mode,
        packet_salt=str(manifest["packet_salt"]),
        run_nonce_seed=str(manifest["run_nonce_seed"]),
        canary_1x10_doc_ids=canary_1x10_doc_ids,
    )
    items_by_canon_cid = {it["custom_id"]: it for it in items}

    vp = vault_path or default_dpapi_vault_path()
    if transports_by_provider is not None:
        transports = dict(transports_by_provider)
    else:
        resolver = lambda p: resolve_provider_secret(p, vault_path=vp)
        transports = {
            "openai": OpenAIBatchLiveTransport(secret_resolver=resolver, url_opener=url_opener),
            "anthropic": AnthropicBatchLiveTransport(secret_resolver=resolver, url_opener=url_opener),
        }
    for prov in providers:
        tr = transports.get(prov)
        if tr is None or not getattr(tr, "can_submit_billable_batches", False):
            raise PermissionError(f"PROVIDER_TRANSPORT_NOT_AUTHORIZED_FOR_BATCHES:{prov}")

    wire_context_by_prov_cid: dict[tuple[str, str], dict[str, Any]] = {}
    for prov in providers:
        rp = rate_profiles[prov]
        for it in items:
            wire_context_by_prov_cid[(prov, it["custom_id"])] = build_verified_live_wire_item(
                provider=prov,
                model_id=rp.model_id,
                item=it,
                system_prompt=sys_prompt,
                response_schema=schema_s4,
            )

    raw_logs_by_prov = {prov: clean_out / f"{prov}_raw_log.jsonl" for prov in providers}
    retry_failed_by_prov: dict[str, list[dict[str, Any]]] = {prov: [] for prov in providers}
    failed_batch_counts: dict[str, int] = {prov: 0 for prov in providers}
    snapshot_drift_errors: list[str] = []
    long_context_errors: list[str] = []
    retry_circuit_breaker_halts: list[str] = []

    validated_recovery_bids: tuple[str, ...] = ()
    validated_recovery_lineage: list[dict[str, Any]] = []
    if recover_anthropic_extra_input_batch_ids:
        existing_ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {}
        validated_recovery_bids, validated_recovery_lineage = _validate_anthropic_recovery_targets(
            recover_batch_ids=recover_anthropic_extra_input_batch_ids,
            ledger=existing_ledger,
            raw_log_path=clean_out / "anthropic_raw_log.jsonl",
            clean_out=clean_out,
        )
    recorded_recovery_epochs: set[str] = set()
    pending_recovery_batch_links: list[dict[str, Any]] = []
    active_prov_filter: set[str] = set(providers)

    def _superseded_scope_for_provider(prov: str) -> tuple[tuple[str, ...], list[tuple[str, str]]]:
        sup_bids = validated_recovery_bids if prov == "anthropic" else ()
        if not ledger_path.is_file():
            return sup_bids, []
        led_snap = json.loads(ledger_path.read_text(encoding="utf-8"))
        return sup_bids, _ledger_recovery_superseded_pairs(led_snap, prov)

    def _intent_recovery_meta_for_batch(batch_id: str) -> dict[str, Any] | None:
        if not ledger_path.is_file():
            return None
        led_snap = json.loads(ledger_path.read_text(encoding="utf-8"))
        for ik, ent in (led_snap.get("intents") or {}).items():
            if ent.get("batch_id") == batch_id and ent.get("supersedes_batch_ids"):
                return {
                    "recovery_intent_key": ik,
                    "recovery_epoch_id": ent.get("recovery_epoch_id"),
                    "recovery_mode": str(ent.get("recovery_mode") or "ANTHROPIC_EXTRA_INPUT_VERSION_FIX06"),
                    "recovery_run_id": ent.get("run_id"),
                    "supersedes_batch_ids": list(ent.get("supersedes_batch_ids") or []),
                    "supersedes_intent_keys": list(ent.get("supersedes_intent_keys") or []),
                    "supersedes_run_ids": list(ent.get("supersedes_run_ids") or []),
                    "recovered_error_signature": str(
                        ent.get("recovered_error_signature") or _ANTHROPIC_EXTRA_INPUT_ERROR_SIGNATURE
                    ),
                    "submitted_custom_ids": list(ent.get("submitted_custom_ids") or []),
                }
        return None

    def _append_anthropic_recovery_epoch_if_needed(
        *,
        recovery_intent_key: str,
        recovery_batch_id: str | None,
        recovery_run_id: str,
        recovery_epoch_id: str,
        supersedes_batch_ids: Sequence[str],
        supersedes_intent_keys: Sequence[str],
        recovered_cids: Sequence[str],
        error_signature: str,
    ) -> None:
        if recovery_intent_key in recorded_recovery_epochs:
            return
        ant_log = raw_logs_by_prov.get("anthropic") or (clean_out / "anthropic_raw_log.jsonl")
        if ant_log.is_file():
            for ln in ant_log.read_text(encoding="utf-8").splitlines():
                stripped = ln.strip()
                if not stripped:
                    continue
                row = json.loads(stripped)
                if (
                    row.get("event_type") == "ANTHROPIC_RECOVERY_EPOCH"
                    and row.get("recovery_intent_key") == recovery_intent_key
                ):
                    recorded_recovery_epochs.add(recovery_intent_key)
                    return
        sup_bids = [str(b) for b in supersedes_batch_ids if b]
        hist_rows = sum(int(x.get("historical_row_count", 0)) for x in validated_recovery_lineage)
        if hist_rows == 0 and ant_log.is_file() and sup_bids:
            sup_set = set(sup_bids)
            hist_rows = sum(
                1
                for ln in ant_log.read_text(encoding="utf-8").splitlines()
                if ln.strip()
                and json.loads(ln).get("event_type") == "ITEM_ATTEMPT"
                and str(json.loads(ln).get("batch_id") or "") in sup_set
            )
        _append_jsonl_durable(
            ant_log,
            {
                "event_type": "ANTHROPIC_RECOVERY_EPOCH",
                "recorded_at_utc": _utc_now_iso(),
                "provider": "anthropic",
                "recovery_mode": "ANTHROPIC_EXTRA_INPUT_VERSION_FIX06",
                "recovery_epoch_id": recovery_epoch_id,
                "recovery_intent_key": recovery_intent_key,
                "recovery_batch_id": recovery_batch_id,
                "recovery_run_id": recovery_run_id,
                "slice_mode": slice_mode,
                "supersedes_batch_id": sup_bids[0] if sup_bids else None,
                "supersedes_batch_ids": sup_bids,
                "supersedes_intent_keys": [str(k) for k in supersedes_intent_keys if k],
                "recovered_custom_ids": [canonicalize_custom_id(str(c)) for c in recovered_cids],
                "recovered_item_count": len(recovered_cids),
                "historical_error_rows_preserved": hist_rows,
                "error_signature": error_signature,
            },
        )
        recorded_recovery_epochs.add(recovery_intent_key)

    def _compute_projected_canonical_response(
        *,
        parsed_resp: Mapping[str, Any],
        local_val: Mapping[str, Any],
        ctx: Mapping[str, Any],
        item_entry: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        state = str(local_val.get("state", "ERROR"))
        if state in ("REL_0", "NA"):
            return {"grade": state, "evidence_quote": None, "char_start": None, "char_end": None}
        if state not in ("REL_1", "REL_2"):
            return None
        v_span = _project_half_open_interval(
            int(parsed_resp["char_start"]),
            int(parsed_resp["char_end"]),
            ctx["safe_to_v_segments"],
        )
        if v_span is None:
            return None
        s_span = _project_half_open_interval(v_span[0], v_span[1], item_entry["doc_v_to_s_segments"])
        if s_span is None:
            return None
        return {
            "grade": state,
            "evidence_quote": str(parsed_resp["evidence_quote"]),
            "char_start": s_span[0],
            "char_end": s_span[1],
        }

    def _expected_cids_for_intent(ent: Mapping[str, Any]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for raw_c in (ent.get("submitted_custom_ids") or ent.get("custom_ids") or []):
            canon = canonicalize_custom_id(str(raw_c))
            if canon not in seen:
                seen.add(canon)
                out.append(canon)
        return out

    def _expected_cids_for_batch(batch_id: str) -> list[str]:
        if not ledger_path.is_file():
            return []
        ledger_obj = json.loads(ledger_path.read_text(encoding="utf-8"))
        for ent in (ledger_obj.get("intents") or {}).values():
            if ent.get("batch_id") == batch_id:
                return _expected_cids_for_intent(ent)
        return []

    def _assert_current_slice_covers_intent_context(
        prov: str,
        expected_cids: Sequence[str],
        *,
        batch_id: str | None = None,
    ) -> None:
        missing_ctx = [
            cid
            for cid in expected_cids
            if cid not in items_by_canon_cid or (prov, cid) not in wire_context_by_prov_cid
        ]
        if missing_ctx:
            raise PermissionError(
                f"RESUME_SLICE_MISSING_CONTEXT_FOR_INTENT:{prov}:batch={batch_id}:"
                f"missing={len(missing_ctx)}/{len(expected_cids)}"
            )

    def _persist_terminal_outcome_before_cleanup(prov: str, outcome: dict[str, Any]) -> None:
        """Persist raw outcome JSON + verify ALL submitted_custom_ids BEFORE .jsonl_complete or remote delete."""
        batch_id = str(outcome.get("batch_id", "unknown"))
        backup_path = clean_out / "raw_batch_outcomes" / f"{prov}_{batch_id}.json"
        complete_marker_path = clean_out / "raw_batch_outcomes" / f"{prov}_{batch_id}.jsonl_complete.json"

        rp = rate_profiles[prov]
        raw_log_p = raw_logs_by_prov[prov]
        rec_meta_for_batch = _intent_recovery_meta_for_batch(batch_id) if prov == "anthropic" else None
        if rec_meta_for_batch is not None:
            pending_recovery_batch_links.append(
                {
                    "recovery_intent_key": str(rec_meta_for_batch["recovery_intent_key"]),
                    "recovery_epoch_id": str(rec_meta_for_batch.get("recovery_epoch_id") or f"rec_{batch_id}"),
                    "recovery_mode": str(rec_meta_for_batch["recovery_mode"]),
                    "supersedes_intent_keys": list(rec_meta_for_batch["supersedes_intent_keys"]),
                    "supersedes_batch_ids": list(rec_meta_for_batch["supersedes_batch_ids"]),
                    "supersedes_run_ids": list(rec_meta_for_batch["supersedes_run_ids"]),
                    "recovered_error_signature": str(rec_meta_for_batch["recovered_error_signature"]),
                    "recovery_batch_id": batch_id,
                }
            )
            _append_anthropic_recovery_epoch_if_needed(
                recovery_intent_key=str(rec_meta_for_batch["recovery_intent_key"]),
                recovery_batch_id=batch_id,
                recovery_run_id=str(rec_meta_for_batch.get("recovery_run_id") or ""),
                recovery_epoch_id=str(rec_meta_for_batch.get("recovery_epoch_id") or f"rec_{batch_id}"),
                supersedes_batch_ids=rec_meta_for_batch["supersedes_batch_ids"],
                supersedes_intent_keys=rec_meta_for_batch["supersedes_intent_keys"],
                recovered_cids=rec_meta_for_batch["submitted_custom_ids"],
                error_signature=str(rec_meta_for_batch["recovered_error_signature"]),
            )
        sup_bids, sup_pairs = _superseded_scope_for_provider(prov)
        settled_now, attempts_now, _retried_now, logged_by_batch_cid = _load_raw_log_batch_state(
            raw_log_p,
            superseded_batch_ids=sup_bids,
            superseded_batch_item_pairs=sup_pairs,
        )

        intent_cids = _expected_cids_for_batch(batch_id)
        out_items = list(outcome.get("items") or [])
        status_upper = str(outcome.get("batch_status", "UNKNOWN")).upper()
        if status_upper in ("FAILED", "CANCELLED", "EXPIRED") and not out_items:
            if complete_marker_path.is_file():
                return
            if intent_cids:
                _assert_current_slice_covers_intent_context(prov, intent_cids, batch_id=batch_id)
            failed_batch_counts[prov] = failed_batch_counts.get(prov, 0) + 1
            _save_json_atomic(
                complete_marker_path,
                {
                    "schema_version": "GOMATE_W07_JSONL_COMPLETE_V1",
                    "provider": prov,
                    "batch_id": batch_id,
                    "status": status_upper,
                    "recorded_at_utc": _utc_now_iso(),
                    "verified_item_count": 0,
                },
            )
            return

        authoritative_cids: list[str] = list(intent_cids)
        seen_auth: set[str] = set(authoritative_cids)
        for res_it in out_items:
            canon_cid = canonicalize_custom_id(str(res_it.get("custom_id", "")))
            if canon_cid and canon_cid not in seen_auth:
                seen_auth.add(canon_cid)
                authoritative_cids.append(canon_cid)

        all_batch_cids_logged = bool(authoritative_cids) and all(
            ((batch_id, cid) in logged_by_batch_cid or cid in settled_now)
            for cid in authoritative_cids
        )
        if complete_marker_path.is_file() and all_batch_cids_logged:
            return

        # Fail-closed BEFORE writing markers, appending partial JSONL, or allowing remote cleanup!
        _assert_current_slice_covers_intent_context(prov, authoritative_cids, batch_id=batch_id)

        if not backup_path.is_file():
            _save_json_atomic(backup_path, outcome)

        returned_cids = {canonicalize_custom_id(str(x.get("custom_id", ""))) for x in out_items}
        for exp_cid in intent_cids:
            if exp_cid not in returned_cids:
                out_items.append(
                    {
                        "custom_id": exp_cid,
                        "model_snapshot_id": None,
                        "usage": None,
                        "parsed_response": None,
                        "provider_error": "PROVIDER_DROPPED_BATCH_ITEM",
                    }
                )

        relevant_pairs: list[tuple[dict[str, Any], str]] = []
        for res_it in out_items:
            canon_cid = canonicalize_custom_id(str(res_it.get("custom_id", "")))
            if canon_cid in items_by_canon_cid and (prov, canon_cid) in wire_context_by_prov_cid:
                relevant_pairs.append((res_it, canon_cid))

        expected_batch_cids = list(authoritative_cids)

        batch_retryables: list[dict[str, Any]] = []
        cliff = ANTHROPIC_100K_CLIFF_TOKENS if prov == "anthropic" else OPENAI_272K_CLIFF_TOKENS
        for res_it, canon_cid in relevant_pairs:
            item_entry = items_by_canon_cid[canon_cid]
            ctx = wire_context_by_prov_cid[(prov, canon_cid)]

            snap = res_it.get("model_snapshot_id")
            if isinstance(snap, str) and snap and snap != rp.expected_snapshot_id:
                snapshot_drift_errors.append(f"{prov}:{canon_cid}:{snap}!={rp.expected_snapshot_id}")

            usage = res_it.get("usage")
            in_tok = int(usage["input_tokens"]) if isinstance(usage, Mapping) and isinstance(usage.get("input_tokens"), int) else 0
            out_tok = int(usage["output_tokens"]) if isinstance(usage, Mapping) and isinstance(usage.get("output_tokens"), int) else 0
            if in_tok >= cliff:
                long_context_errors.append(f"{prov}:{canon_cid}:input_tokens={in_tok}>={cliff}")

            existing_recs = logged_by_batch_cid.get((batch_id, canon_cid), [])
            if existing_recs:
                if not any(bool(r.get("final_for_item")) for r in existing_recs):
                    last_state = str((existing_recs[-1].get("local_validation") or {}).get("state", "ERROR"))
                    if last_state not in ("REL_0", "REL_1", "REL_2", "NA") and attempts_now.get(canon_cid, 1) <= MAX_SCHEMA_RETRIES_PER_ITEM:
                        batch_retryables.append(item_entry)
                continue
            if canon_cid in settled_now:
                continue

            item_cost_usd = _meter_usage_usd({"input_tokens": in_tok, "output_tokens": out_tok}, rp)
            parsed_resp = res_it.get("parsed_response")
            projected_canon: dict[str, Any] | None = None
            if isinstance(parsed_resp, Mapping) and not res_it.get("provider_error"):
                local_val = project_cloud_quote_locally_to_canonical_s(
                    cloud_response=parsed_resp,
                    safe_doc_v=ctx["safe_doc_v"],
                    safe_to_v_segments=ctx["safe_to_v_segments"],
                    doc_sanitized_V=item_entry["sanitized_text_V"],
                    doc_canonical_S=item_entry["doc_canonical_S"],
                    doc_v_to_s_segments=item_entry["doc_v_to_s_segments"],
                    doc_removed_r_audit=item_entry["doc_removed_r_audit"],
                    doc_meta=item_entry["doc_meta"],
                    query_meta=item_entry["query_meta"],
                )
                projected_canon = _compute_projected_canonical_response(
                    parsed_resp=parsed_resp,
                    local_val=local_val,
                    ctx=ctx,
                    item_entry=item_entry,
                )
            else:
                local_val = {
                    "state": "ERROR",
                    "confirmed_gain": 0,
                    "max_admissible_gain": 3,
                    "error_code": str(res_it.get("provider_error") or "MISSING_PARSED_RESPONSE"),
                }

            attempt_no = attempts_now.get(canon_cid, 0) + 1
            attempts_now[canon_cid] = attempt_no
            is_valid_non_error = local_val.get("state") in ("REL_0", "REL_1", "REL_2", "NA")
            can_retry = (not is_valid_non_error) and (attempt_no <= MAX_SCHEMA_RETRIES_PER_ITEM)
            final_for_item = is_valid_non_error or (not can_retry)

            rec_to_log = {
                "event_type": "ITEM_ATTEMPT",
                "recorded_at_utc": _utc_now_iso(),
                "provider": prov,
                "batch_id": batch_id,
                "attempt_no": attempt_no,
                "custom_id": canon_cid,
                "wire_custom_id": str(res_it.get("wire_custom_id") or ctx["wire_custom_id"]),
                "packet_item_uuid": item_entry["packet_item_uuid"],
                "query_id": item_entry["query_meta"]["query_id"],
                "document_id": item_entry["doc_record_for_leak_check"]["document_id"],
                "prompt_order": item_entry["prompt_order"],
                "model_snapshot_id": snap,
                "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
                "item_cost_usd": item_cost_usd,
                "parsed_response": parsed_resp,
                "projected_canonical_response": projected_canon,
                "local_validation": local_val,
                "final_for_item": final_for_item,
            }
            if rec_meta_for_batch is not None:
                rec_to_log["recovery_epoch_id"] = rec_meta_for_batch.get("recovery_epoch_id")
                rec_to_log["supersedes_batch_ids"] = list(rec_meta_for_batch["supersedes_batch_ids"])
                rec_to_log["supersedes_intent_keys"] = list(rec_meta_for_batch["supersedes_intent_keys"])
            _append_jsonl_durable(raw_log_p, rec_to_log)
            logged_by_batch_cid.setdefault((batch_id, canon_cid), []).append(rec_to_log)
            if can_retry:
                batch_retryables.append(item_entry)

        if relevant_pairs:
            settled_after, _att_after, _ret_after, logged_after = _load_raw_log_batch_state(
                raw_log_p,
                superseded_batch_ids=sup_bids,
                superseded_batch_item_pairs=sup_pairs,
            )
            missing_after = [
                cid for cid in expected_batch_cids
                if (batch_id, cid) not in logged_after and cid not in settled_after
            ]
            if missing_after:
                raise RuntimeError(f"INCOMPLETE_RAW_LOG_PERSISTENCE:{prov}:{batch_id}:{len(missing_after)}")

            err_rate = len(batch_retryables) / float(len(relevant_pairs))
            cb = evaluate_budget_and_retry_circuit_breakers(
                spent_usd=0.0,
                projected_batch_usd=0.0,
                hard_cap_usd=requested_dev_cap_usd,
                pass1_error_rate=err_rate,
                failed_batches=failed_batch_counts.get(prov, 0),
                max_failed_batches=1,
            )
            if not cb["allowed"]:
                for failed_it in batch_retryables:
                    fcid = failed_it["custom_id"]
                    if fcid not in settled_after:
                        _append_jsonl_durable(
                            raw_log_p,
                            {
                                "event_type": "ITEM_ATTEMPT",
                                "recorded_at_utc": _utc_now_iso(),
                                "provider": prov,
                                "batch_id": batch_id,
                                "attempt_no": attempts_now.get(fcid, 1) + 1,
                                "custom_id": fcid,
                                "wire_custom_id": wire_context_by_prov_cid[(prov, fcid)]["wire_custom_id"],
                                "packet_item_uuid": failed_it["packet_item_uuid"],
                                "query_id": failed_it["query_meta"]["query_id"],
                                "document_id": failed_it["doc_record_for_leak_check"]["document_id"],
                                "prompt_order": failed_it["prompt_order"],
                                "local_validation": {
                                    "state": "ERROR",
                                    "confirmed_gain": 0,
                                    "max_admissible_gain": 3,
                                    "error_code": str(cb["halt_code"]),
                                },
                                "final_for_item": True,
                            },
                        )
                _save_json_atomic(
                    complete_marker_path,
                    {
                        "schema_version": "GOMATE_W07_JSONL_COMPLETE_V1",
                        "provider": prov,
                        "batch_id": batch_id,
                        "recorded_at_utc": _utc_now_iso(),
                        "verified_item_count": len(expected_batch_cids),
                        "circuit_breaker_halted": True,
                        "halt_code": str(cb["halt_code"]),
                    },
                )
                retry_failed_by_prov[prov] = []
                retry_circuit_breaker_halts.append(f"{cb['halt_code']}:{prov}:error_rate={err_rate:.4f}")
                return

            _save_json_atomic(
                complete_marker_path,
                {
                    "schema_version": "GOMATE_W07_JSONL_COMPLETE_V1",
                    "provider": prov,
                    "batch_id": batch_id,
                    "recorded_at_utc": _utc_now_iso(),
                    "verified_item_count": len(expected_batch_cids),
                },
            )
            existing_retry_cids = {x["custom_id"] for x in retry_failed_by_prov[prov]}
            for r_it in batch_retryables:
                if r_it["custom_id"] not in existing_retry_cids:
                    retry_failed_by_prov[prov].append(r_it)
                    existing_retry_cids.add(r_it["custom_id"])

    reconciler = _CompositeLiveReconcileRouter(
        ledger_path=ledger_path,
        transports_by_provider=transports,
        on_terminal_outcome=_persist_terminal_outcome_before_cleanup,
        active_reconcile_providers=providers,
    )

    def _raise_if_safety_abort() -> None:
        if snapshot_drift_errors:
            raise RuntimeError(f"MODEL_SNAPSHOT_DRIFT_ABORT:{snapshot_drift_errors[0]}")
        if long_context_errors:
            raise PermissionError(f"LONG_CONTEXT_CLIFF_ABORT:{long_context_errors[0]}")
        if retry_circuit_breaker_halts:
            raise RuntimeError(retry_circuit_breaker_halts[0])

    def _replay_incomplete_backup_outcomes() -> None:
        outcomes_dir = clean_out / "raw_batch_outcomes"
        if not outcomes_dir.is_dir():
            return
        for prov in providers:
            for path in sorted(outcomes_dir.glob(f"{prov}_*.json")):
                if path.name.endswith(".jsonl_complete.json"):
                    continue
                outcome = json.loads(path.read_text(encoding="utf-8"))
                _persist_terminal_outcome_before_cleanup(prov, outcome)
                _raise_if_safety_abort()

    def _active_other_output_dir_intents(raw_ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
        clean_out_str = str(clean_out)
        other: list[dict[str, Any]] = []
        for ent in (raw_ledger.get("intents") or {}).values():
            st = str(ent.get("status", ""))
            is_act = st in _ACTIVE_INTENT_STATUSES or st.startswith("NONTERMINAL_RESERVED_")
            src_dir = ent.get("source_output_dir")
            if is_act and isinstance(src_dir, str) and src_dir and src_dir != clean_out_str:
                other.append(dict(ent))
        return other

    def _active_same_dir_intents(raw_ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
        clean_out_str = str(clean_out)
        prov_set = set(providers)
        active: list[dict[str, Any]] = []
        for ent in (raw_ledger.get("intents") or {}).values():
            st = str(ent.get("status", ""))
            prov = str(ent.get("provider", ""))
            src_dir = ent.get("source_output_dir")
            is_owner = (src_dir == clean_out_str) or (not src_dir)
            if prov in prov_set and is_owner and (st in _ACTIVE_INTENT_STATUSES or st.startswith("NONTERMINAL_RESERVED_")):
                active.append(dict(ent))
        return active

    def _build_dispatch_plans() -> tuple[list[tuple[str, str, list[dict[str, Any]], float]], float]:
        plans: list[tuple[str, str, list[dict[str, Any]], float]] = []
        run_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        total_reserve = 0.0
        for prov in providers:
            rp = rate_profiles[prov]
            sup_bids, sup_pairs = _superseded_scope_for_provider(prov)
            settled_idx, attempts_idx, _retried_idx = _load_raw_log_index(
                raw_logs_by_prov[prov],
                superseded_batch_ids=sup_bids,
                superseded_batch_item_pairs=sup_pairs,
            )
            pending_items = [
                it for it in items
                if it["custom_id"] not in settled_idx
                and attempts_idx.get(it["custom_id"], 0) < (1 + MAX_SCHEMA_RETRIES_PER_ITEM)
            ]
            if not pending_items:
                continue
            if prov == "anthropic" and validated_recovery_lineage:
                attempt_tag = "recovery-retry" if any(attempts_idx.get(it["custom_id"], 0) == 1 for it in pending_items) else "recovery"
            else:
                attempt_tag = "retry" if any(attempts_idx.get(it["custom_id"], 0) == 1 for it in pending_items) else "pass1"
            sized_wire_items = [
                _clone_wire_item_with_dispatch_tag(
                    wire_context_by_prov_cid[(prov, it["custom_id"])]["wire_item"],
                    packet_item_uuid=it["packet_item_uuid"],
                    prompt_order=it["prompt_order"],
                    dispatch_tag="000000",
                )
                for it in pending_items
            ]
            res_info = estimate_batch_worst_case_reserve_usd(
                provider=prov,
                wire_items=sized_wire_items,
                rate_profile=rp,
            )
            res_usd = float(res_info["reserved_worst_case_usd"])
            total_reserve = round(total_reserve + res_usd, 6)
            plans.append((prov, f"dev5-{slice_mode}-{attempt_tag}-{run_ts}", pending_items, res_usd))
        return plans, total_reserve

    def _reconcile_once() -> dict[str, Any]:
        state = reconcile_stage1_crash_intents(
            ledger_path=ledger_path,
            rate_profiles_by_provider=rate_profiles,
            reconciler=reconciler,
        )
        if reconciler.file_cleanup_updates:
            pending_upd = dict(reconciler.file_cleanup_updates)
            reconciler.file_cleanup_updates.clear()
            for k, upd in pending_upd.items():
                cur_ent = (state.get("intents") or {}).get(k) or {}
                d_stage_upd = str(upd.get("dispatch_stage") or cur_ent.get("dispatch_stage") or "UPLOAD_IN_FLIGHT")
                record_stage1_dispatch_progress(
                    ledger_path=ledger_path,
                    client_idempotency_key=k,
                    dispatch_stage=d_stage_upd,
                    input_file_id=upd.get("input_file_id"),
                    input_upload_filename=upd.get("input_upload_filename"),
                    input_jsonl_sha256=upd.get("input_jsonl_sha256"),
                    file_cleanup_status=upd.get("file_cleanup_status"),
                    pending_cleanup_file_ids=upd.get("pending_cleanup_file_ids"),
                    cleaned_file_ids=upd.get("cleaned_file_ids"),
                    file_reconcile_exhaustive=upd.get("file_reconcile_exhaustive"),
                    file_reconcile_stop_reason=upd.get("file_reconcile_stop_reason"),
                )
                if upd.get("file_cleanup_status") in (
                    "CLEANED_ORPHAN_FILE_VERIFIED",
                    "VERIFIED_NO_REMOTE_FILE",
                    "NONE_PRE_UPLOAD",
                ):
                    reconciler._delete_cleanup_sidecar_entry(k)
            state = json.loads(ledger_path.read_text(encoding="utf-8"))
        if pending_recovery_batch_links:
            queued_links = list(pending_recovery_batch_links)
            pending_recovery_batch_links.clear()
            for rlink in queued_links:
                record_stage1_recovery_linkage(ledger_path=ledger_path, **rlink)
            state = json.loads(ledger_path.read_text(encoding="utf-8"))
        _raise_if_safety_abort()
        return state

    def _reconcile_and_poll_until_settled_or_timeout() -> dict[str, Any]:
        deadline = time.monotonic() + max(0.0, float(max_wait_seconds))
        while True:
            with _dispatch_coordinator_lock(ledger_path):
                state = _reconcile_once()
            has_nonterminal = any(
                str(ent.get("status", "")).startswith("NONTERMINAL_RESERVED_")
                and (active_prov_filter is None or str(ent.get("provider", "")) in active_prov_filter)
                for ent in (state.get("intents") or {}).values()
            )
            if not has_nonterminal or time.monotonic() >= deadline:
                return state
            if poll_interval_seconds > 0:
                sleep_fn(float(poll_interval_seconds))
            else:
                return state

    def _reserve_and_submit_provider_batch(
        *,
        prov: str,
        run_id: str,
        batch_items: Sequence[Mapping[str, Any]],
        reserved_usd: float,
        extra_fields: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        rp = rate_profiles[prov]
        canon_cids = [str(it["custom_id"]) for it in batch_items]
        intent = prepare_stage1_pre_submit_intent(
            ledger_path=ledger_path,
            run_id=run_id,
            rate_profile=rp,
            custom_ids=canon_cids,
            batch_reserved_worst_case_usd=reserved_usd,
            dev_hard_cap_usd=requested_dev_cap_usd,
            total_hard_cap_usd=requested_total_cap_usd,
        )
        idemp_key = str(intent["client_idempotency_key"])
        dispatch_tag = idemp_key[:6]
        record_stage1_dispatch_progress(
            ledger_path=ledger_path,
            client_idempotency_key=idemp_key,
            dispatch_stage="PRE_SUBMIT_RESERVED",
            source_output_dir=clean_out,
            wire_dispatch_tag=dispatch_tag,
        )
        recovery_epoch_id: str | None = None
        if prov == "anthropic" and validated_recovery_lineage:
            recovery_epoch_id = f"rec_{idemp_key[:12]}"
            record_stage1_recovery_linkage(
                ledger_path=ledger_path,
                recovery_intent_key=idemp_key,
                recovery_epoch_id=recovery_epoch_id,
                recovery_mode="ANTHROPIC_EXTRA_INPUT_VERSION_FIX06",
                supersedes_intent_keys=[str(x["supersedes_intent_key"]) for x in validated_recovery_lineage],
                supersedes_batch_ids=[str(x["supersedes_batch_id"]) for x in validated_recovery_lineage],
                supersedes_run_ids=[str(x.get("supersedes_run_id") or "") for x in validated_recovery_lineage],
                recovered_error_signature=_ANTHROPIC_EXTRA_INPUT_ERROR_SIGNATURE,
            )
        tagged_wire_items = [
            _clone_wire_item_with_dispatch_tag(
                wire_context_by_prov_cid[(prov, str(it["custom_id"]))]["wire_item"],
                packet_item_uuid=str(it["packet_item_uuid"]),
                prompt_order=str(it["prompt_order"]),
                dispatch_tag=dispatch_tag,
            )
            for it in batch_items
        ]

        tr = transports[prov]
        submit_kwargs: dict[str, Any] = {
            "run_id": run_id,
            "client_idempotency_key": idemp_key,
            "wire_items": tagged_wire_items,
            "expected_snapshot_id": rp.expected_snapshot_id,
        }
        sig_params = inspect.signature(tr.submit_batch).parameters
        has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig_params.values())
        if "on_before_file_upload" in sig_params or (prov == "openai" and has_var_kw):
            submit_kwargs["on_before_file_upload"] = lambda fn, fsha, k=idemp_key, d=dispatch_tag: record_stage1_dispatch_progress(
                ledger_path=ledger_path,
                client_idempotency_key=k,
                dispatch_stage="UPLOAD_IN_FLIGHT",
                input_upload_filename=fn,
                input_jsonl_sha256=fsha,
                file_cleanup_status="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE",
                source_output_dir=clean_out,
                wire_dispatch_tag=d,
            )
        if "on_input_file_uploaded" in sig_params or (prov == "openai" and has_var_kw):
            submit_kwargs["on_input_file_uploaded"] = lambda fid, k=idemp_key, d=dispatch_tag: record_stage1_dispatch_progress(
                ledger_path=ledger_path,
                client_idempotency_key=k,
                dispatch_stage="INPUT_FILE_UPLOADED_PRE_BATCH_POST",
                input_file_id=fid,
                file_cleanup_status="UPLOADED_PENDING_BATCH_OR_CLEANUP",
                source_output_dir=clean_out,
                wire_dispatch_tag=d,
            )
        if "on_before_batch_create" in sig_params or has_var_kw:
            submit_kwargs["on_before_batch_create"] = lambda k=idemp_key, d=dispatch_tag: record_stage1_dispatch_progress(
                ledger_path=ledger_path,
                client_idempotency_key=k,
                dispatch_stage="BATCH_POST_IN_FLIGHT",
                source_output_dir=clean_out,
                wire_dispatch_tag=d,
            )
        if "on_batch_create_4xx" in sig_params or (prov == "openai" and has_var_kw):
            submit_kwargs["on_batch_create_4xx"] = lambda k=idemp_key, d=dispatch_tag: record_stage1_dispatch_progress(
                ledger_path=ledger_path,
                client_idempotency_key=k,
                dispatch_stage="BATCH_CREATE_4XX_REJECTED",
                file_cleanup_status="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE",
                source_output_dir=clean_out,
                wire_dispatch_tag=d,
            )

        sub_res = tr.submit_batch(**submit_kwargs)
        new_batch_id = str(sub_res["batch_id"])
        link_stage1_dispatched_batch(
            ledger_path=ledger_path,
            client_idempotency_key=idemp_key,
            batch_id=new_batch_id,
            input_file_id=sub_res.get("input_file_id"),
        )
        record_stage1_dispatch_progress(
            ledger_path=ledger_path,
            client_idempotency_key=idemp_key,
            dispatch_stage="BATCH_DISPATCHED",
            input_file_id=sub_res.get("input_file_id"),
            source_output_dir=clean_out,
            wire_dispatch_tag=dispatch_tag,
        )
        if prov == "anthropic" and validated_recovery_lineage and recovery_epoch_id is not None:
            sup_intent_keys = [str(x["supersedes_intent_key"]) for x in validated_recovery_lineage]
            sup_batch_ids = [str(x["supersedes_batch_id"]) for x in validated_recovery_lineage]
            sup_run_ids = [str(x.get("supersedes_run_id") or "") for x in validated_recovery_lineage]
            record_stage1_recovery_linkage(
                ledger_path=ledger_path,
                recovery_intent_key=idemp_key,
                recovery_epoch_id=recovery_epoch_id,
                recovery_mode="ANTHROPIC_EXTRA_INPUT_VERSION_FIX06",
                supersedes_intent_keys=sup_intent_keys,
                supersedes_batch_ids=sup_batch_ids,
                supersedes_run_ids=sup_run_ids,
                recovered_error_signature=_ANTHROPIC_EXTRA_INPUT_ERROR_SIGNATURE,
                recovery_batch_id=new_batch_id,
            )
            _append_anthropic_recovery_epoch_if_needed(
                recovery_intent_key=idemp_key,
                recovery_batch_id=new_batch_id,
                recovery_run_id=run_id,
                recovery_epoch_id=recovery_epoch_id,
                supersedes_batch_ids=sup_batch_ids,
                supersedes_intent_keys=sup_intent_keys,
                recovered_cids=canon_cids,
                error_signature=_ANTHROPIC_EXTRA_INPUT_ERROR_SIGNATURE,
            )
        entry = {
            "provider": prov,
            "run_id": run_id,
            "client_idempotency_key": idemp_key,
            "wire_dispatch_tag": dispatch_tag,
            "batch_id": new_batch_id,
            "input_file_id": sub_res.get("input_file_id"),
            "item_count": len(tagged_wire_items),
            "reserved_worst_case_usd": reserved_usd,
        }
        if recovery_epoch_id is not None:
            entry["recovery_mode"] = "ANTHROPIC_EXTRA_INPUT_VERSION_FIX06"
            entry["recovery_epoch_id"] = recovery_epoch_id
            entry["supersedes_batch_ids"] = [str(x["supersedes_batch_id"]) for x in validated_recovery_lineage]
            entry["supersedes_intent_keys"] = [str(x["supersedes_intent_key"]) for x in validated_recovery_lineage]
        if extra_fields:
            entry.update(extra_fields)
        return entry

    dispatched_this_run: list[dict[str, Any]] = []

    # 1. Under shared OS coordinator lock: initialize shared ledger, replay incomplete crash backups,
    #    block cross-output-dir interference / cap overflow, and reconcile existing crash intents once.
    with _dispatch_coordinator_lock(ledger_path):
        load_or_init_aggregate_stage1_ledger(
            ledger_path,
            dev_hard_cap_usd=requested_dev_cap_usd,
            total_hard_cap_usd=requested_total_cap_usd,
        )
        _replay_incomplete_backup_outcomes()

        raw_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        other_active = _active_other_output_dir_intents(raw_ledger)
        if other_active:
            eff_other = float(raw_ledger.get("effective_committed_usd", 0.0))
            if not resume_only:
                _plans, planned_usd = _build_dispatch_plans()
                if eff_other + planned_usd > requested_dev_cap_usd + 1e-12:
                    raise PermissionError(
                        f"STAGE1_COMBINED_TWO_PROVIDER_DEV_CAP_EXCEEDED:{eff_other + planned_usd:.4f}>{requested_dev_cap_usd:.4f}"
                    )
            other_dirs = sorted({str(e.get("source_output_dir")) for e in other_active})
            raise PermissionError(f"CONCURRENT_STAGE1_BATCH_ACTIVE_IN_OTHER_OUTPUT_DIR:{other_dirs}")

        for active_ent in _active_same_dir_intents(raw_ledger):
            _assert_current_slice_covers_intent_context(
                str(active_ent["provider"]),
                _expected_cids_for_intent(active_ent),
                batch_id=active_ent.get("batch_id"),
            )

        ledger_state = _reconcile_once()
        has_nonterminal = any(
            str(ent.get("status", "")).startswith("NONTERMINAL_RESERVED_")
            and (active_prov_filter is None or str(ent.get("provider", "")) in active_prov_filter)
            for ent in (ledger_state.get("intents") or {}).values()
        )

    # 2. If any prior intents are non-terminal in-progress, poll outside sleep until settled or max_wait expires.
    if has_nonterminal and max_wait_seconds > 0 and poll_interval_seconds > 0:
        sleep_fn(float(poll_interval_seconds))
        ledger_state = _reconcile_and_poll_until_settled_or_timeout()

    # 3. Under shared OS coordinator lock: validate combined $2.00 cap across all --output-dirs & reserve/submit.
    with _dispatch_coordinator_lock(ledger_path):
        ledger_state = json.loads(ledger_path.read_text(encoding="utf-8"))
        has_unresolved_any = bool(_active_same_dir_intents(ledger_state))
        if not resume_only and not has_unresolved_any:
            other_active_now = _active_other_output_dir_intents(ledger_state)
            provider_dispatch_plans, total_planned_new_reserve = _build_dispatch_plans()
            current_committed = float(ledger_state.get("effective_committed_usd", 0.0))
            if current_committed + total_planned_new_reserve > requested_dev_cap_usd + 1e-12:
                raise PermissionError(
                    f"STAGE1_COMBINED_TWO_PROVIDER_DEV_CAP_EXCEEDED:{current_committed + total_planned_new_reserve:.4f}>{requested_dev_cap_usd:.4f}"
                )
            if other_active_now and provider_dispatch_plans:
                other_dirs = sorted({str(e.get("source_output_dir")) for e in other_active_now})
                raise PermissionError(f"CONCURRENT_STAGE1_BATCH_ACTIVE_IN_OTHER_OUTPUT_DIR:{other_dirs}")

            for prov, run_id, pending_items, res_usd in provider_dispatch_plans:
                dispatched_this_run.append(
                    _reserve_and_submit_provider_batch(
                        prov=prov,
                        run_id=run_id,
                        batch_items=pending_items,
                        reserved_usd=res_usd,
                    )
                )

    # 4. Poll newly dispatched batches until completed or max_wait_seconds expires cleanly.
    if dispatched_this_run:
        ledger_state = _reconcile_and_poll_until_settled_or_timeout()

    # 5. Single bounded retry pass (<= 1 retry/item, <= 15% batch) under shared OS lock if pass1 had retryables.
    if not resume_only:
        retry_dispatched_now = False
        with _dispatch_coordinator_lock(ledger_path):
            ledger_state = json.loads(ledger_path.read_text(encoding="utf-8"))
            if not _active_same_dir_intents(ledger_state):
                retry_plans: list[tuple[str, list[dict[str, Any]], float]] = []
                total_retry_reserve = 0.0
                for prov in providers:
                    if retry_failed_by_prov.get(prov):
                        sup_bids, sup_pairs = _superseded_scope_for_provider(prov)
                        settled_idx, attempts_idx, _ = _load_raw_log_index(
                            raw_logs_by_prov[prov],
                            superseded_batch_ids=sup_bids,
                            superseded_batch_item_pairs=sup_pairs,
                        )
                        r_items = [
                            it for it in retry_failed_by_prov[prov]
                            if it["custom_id"] not in settled_idx and attempts_idx.get(it["custom_id"], 0) == 1
                        ]
                        if r_items:
                            rp = rate_profiles[prov]
                            w_items = [
                                _clone_wire_item_with_dispatch_tag(
                                    wire_context_by_prov_cid[(prov, it["custom_id"])]["wire_item"],
                                    packet_item_uuid=it["packet_item_uuid"],
                                    prompt_order=it["prompt_order"],
                                    dispatch_tag="000000",
                                )
                                for it in r_items
                            ]
                            r_usd = float(
                                estimate_batch_worst_case_reserve_usd(provider=prov, wire_items=w_items, rate_profile=rp)[
                                    "reserved_worst_case_usd"
                                ]
                            )
                            total_retry_reserve = round(total_retry_reserve + r_usd, 6)
                            retry_plans.append((prov, r_items, r_usd))

                if retry_plans:
                    current_committed = float(ledger_state.get("effective_committed_usd", 0.0))
                    if current_committed + total_retry_reserve > requested_dev_cap_usd + 1e-12:
                        raise PermissionError(
                            f"STAGE1_COMBINED_TWO_PROVIDER_DEV_CAP_EXCEEDED:{current_committed + total_retry_reserve:.4f}>{requested_dev_cap_usd:.4f}"
                        )
                    r_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    for prov, r_items, r_usd in retry_plans:
                        dispatched_this_run.append(
                            _reserve_and_submit_provider_batch(
                                prov=prov,
                                run_id=f"dev5-{slice_mode}-retry1-{r_ts}",
                                batch_items=r_items,
                                reserved_usd=r_usd,
                                extra_fields={"retry_pass": 1},
                            )
                        )
                    retry_dispatched_now = True

        if retry_dispatched_now:
            ledger_state = _reconcile_and_poll_until_settled_or_timeout()

    # 6. Build per-provider settlement summary + PromptOrderBias report when both canonical & swapped exist.
    provider_summaries: dict[str, Any] = {}
    prompt_order_bias_reports: dict[str, Any] = {}
    all_providers_settled = True
    docs_by_id = {d["document_id"]: d for d in verify_arm_p_137_corpus_docs(corpus_docs)}
    rem_by_id = {d["document_id"]: list(d["removed_r_audit"]) for d in docs_by_id.values()}
    canonical_total_pairs = len(queries) * len(docs_by_id)

    for prov in providers:
        sup_bids, sup_pairs = _superseded_scope_for_provider(prov)
        settled_idx, attempts_idx, _ = _load_raw_log_index(
            raw_logs_by_prov[prov],
            superseded_batch_ids=sup_bids,
            superseded_batch_item_pairs=sup_pairs,
        )
        remaining_unsettled = [it["custom_id"] for it in items if it["custom_id"] not in settled_idx]
        if remaining_unsettled:
            all_providers_settled = False

        canon_map: dict[tuple[str, str], str] = {}
        swap_map: dict[tuple[str, str], str] = {}
        grade_counts: dict[str, int] = {}
        for rec in settled_idx.values():
            st = str((rec.get("local_validation") or {}).get("state", "ERROR"))
            grade_counts[st] = grade_counts.get(st, 0) + 1
            proj = rec.get("projected_canonical_response")
            pair_payload = (
                json.dumps(proj, ensure_ascii=False)
                if isinstance(proj, Mapping)
                else json.dumps(
                    {
                        "grade": "ERROR",
                        "error_code": str((rec.get("local_validation") or {}).get("error_code") or "ITEM_ERROR"),
                    },
                    ensure_ascii=False,
                )
            )
            pair_key = (str(rec["query_id"]), str(rec["document_id"]))
            if rec.get("prompt_order") == "PROMPT_ORDER_CANONICAL":
                canon_map[pair_key] = pair_payload
            elif rec.get("prompt_order") == "PROMPT_ORDER_SWAPPED":
                swap_map[pair_key] = pair_payload

        overlap_count = len(set(canon_map) & set(swap_map))
        if overlap_count > 0:
            prompt_order_bias_reports[prov] = evaluate_prompt_order_bias(
                queries_meta=queries,
                docs_by_id=docs_by_id,
                removed_by_doc_id=rem_by_id,
                canonical_responses=canon_map,
                swapped_responses=swap_map,
                total_expected_pairs=canonical_total_pairs,
                declared_coverage_mode="STRATIFIED_20PCT_DEV_AUDIT"
                if slice_mode == "dev5_plus_20pct_swap"
                else "STRATIFIED_SAMPLE_AUDIT",
            )

        provider_summaries[prov] = {
            "expected_items": len(items),
            "settled_items": len(settled_idx),
            "remaining_unsettled_items": len(remaining_unsettled),
            "grade_counts": grade_counts,
            "raw_log_path": str(raw_logs_by_prov[prov]),
            "overlapping_swap_pairs": overlap_count,
        }

    still_active_intents = {
        k: v
        for k, v in (ledger_state.get("intents") or {}).items()
        if str(v.get("status", "")) in _ACTIVE_INTENT_STATUSES
        or str(v.get("status", "")).startswith("NONTERMINAL_RESERVED_")
    }
    if still_active_intents:
        overall_status = "AWAITING_BATCH_COMPLETION"
        all_providers_settled = False
    elif all_providers_settled:
        overall_status = "COMPLETED"
    else:
        overall_status = "PARTIAL_OR_RESUME_REQUIRED"

    summary = {
        "schema_version": DEV5_LIVE_RUN_SCHEMA,
        "recorded_at_utc": _utc_now_iso(),
        "overall_status": overall_status,
        "slice_mode": slice_mode,
        "gate_phase": auth["gate_phase"],
        "authorized_stage": str(auth.get("authorized_stage") or "STAGE1_DEV_CANARY_ONLY"),
        "selected_cap_regime": auth["selected_cap_regime"],
        "rate_evidence_sha256": rate_ev["rate_evidence_sha256"],
        "output_dir": str(clean_out),
        "shared_budget_ledger_path": str(ledger_path),
        "aggregate_ledger_path": str(ledger_path),
        "dispatched_this_run": dispatched_this_run,
        "active_or_pending_intents": still_active_intents,
        "cleanup_operations": reconciler.cleanup_log,
        "total_confirmed_spent_usd": ledger_state.get("total_confirmed_spent_usd", 0.0),
        "total_unresolved_reserve_usd": ledger_state.get("total_unresolved_reserve_usd", 0.0),
        "effective_committed_usd": ledger_state.get("effective_committed_usd", 0.0),
        "dev_hard_cap_usd": requested_dev_cap_usd,
        "providers": provider_summaries,
        "prompt_order_bias": prompt_order_bias_reports,
    }
    if validated_recovery_lineage or any(d.get("recovery_epoch_id") for d in dispatched_this_run):
        summary["recovery_targets"] = validated_recovery_lineage
        summary["recovery_summary"] = [
            {
                "recovery_mode": d.get("recovery_mode"),
                "recovery_epoch_id": d.get("recovery_epoch_id"),
                "recovery_intent_key": d.get("client_idempotency_key"),
                "recovery_batch_id": d.get("batch_id"),
                "recovery_run_id": d.get("run_id"),
                "recovered_item_count": d.get("item_count"),
                "reserved_worst_case_usd": d.get("reserved_worst_case_usd"),
                "supersedes_batch_ids": d.get("supersedes_batch_ids"),
                "supersedes_intent_keys": d.get("supersedes_intent_keys"),
                "historical_error_rows_preserved": sum(int(x.get("historical_row_count", 0)) for x in validated_recovery_lineage),
            }
            for d in dispatched_this_run
            if d.get("provider") == "anthropic" and d.get("recovery_epoch_id")
        ]
    _save_json_atomic(clean_out / "dev5_live_run_summary.json", summary)
    return summary


__all__ = [
    "ALLOWED_DEV5_SLICE_MODES",
    "APPROVED_STAGE1_DEV5_QUERY_IDS",
    "AnthropicBatchLiveTransport",
    "DEFAULT_SHARED_BUDGET_LEDGER_FILENAME",
    "DEFAULT_STAGE1_SHARED_LEDGER_ROOT",
    "DEV5_LIVE_RUN_SCHEMA",
    "DEV5_RUN_MANIFEST_SCHEMA",
    "DROPPED_DEV5_QUERY_IDS",
    "LiveTransportError",
    "OpenAIBatchLiveTransport",
    "PINNED_RESPONSE_SCHEMA_S4_SHA256",
    "build_approved_dev5_canary_items",
    "build_verified_live_wire_item",
    "canonicalize_custom_id",
    "estimate_batch_worst_case_reserve_usd",
    "inspect_stage1_dev5_live_readiness",
    "load_approved_dev5_queries",
    "openai_upload_filename_for_intent",
    "record_stage1_dispatch_progress",
    "record_stage1_recovery_linkage",
    "resolve_stage1_shared_budget_ledger_path",
    "run_stage1_dev5_live_batch",
    "to_wire_custom_id",
    "verify_arm_p_137_corpus_docs",
]
