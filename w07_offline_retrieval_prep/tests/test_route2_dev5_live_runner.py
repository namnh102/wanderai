"""Offline tests for Stage-1 DEV-5 live OpenAI/Anthropic Batch transports, gates, P1-C recovery, and CLI."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

PREP_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = str(PREP_DIR / "scripts")
TESTS_DIR = str(PREP_DIR / "tests")
for _p in (SCRIPTS_DIR, TESTS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from provision_route2_activation_ceremony import (  # noqa: E402
    materialize_unsigned_activation_pack,
    sign_ceremony_with_pem_keys,
)
from route2_stage1_activation_session import main as activation_cli_main  # noqa: E402
from test_route2_preflight_vault_and_probe_client import (  # noqa: E402
    PROMPT_S4_SCHEMA,
    _make_strict_verdict_json,
)
from w07_g4_scorer.contracts import assert_g4_package_zero_ml_imports, sha256_bytes  # noqa: E402
from w07_g4_scorer.route2_aiproxy import AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER  # noqa: E402
import w07_g4_scorer.route2_dev5_live_runner as live_mod  # noqa: E402
from w07_g4_scorer.route2_dev5_live_runner import (  # noqa: E402
    APPROVED_STAGE1_DEV5_QUERY_IDS,
    AnthropicBatchLiveTransport,
    OpenAIBatchLiveTransport,
    PINNED_RESPONSE_SCHEMA_S4_SHA256,
    build_approved_dev5_canary_items,
    build_verified_live_wire_item,
    canonicalize_custom_id,
    inspect_stage1_dev5_live_readiness,
    load_approved_dev5_queries,
    run_stage1_dev5_live_batch,
    to_wire_custom_id,
    verify_arm_p_137_corpus_docs,
)
from w07_g4_scorer.route2_dev_canary_runner import ProviderRateProfile  # noqa: E402
from w07_g4_scorer.route2_live_preflight import (  # noqa: E402
    link_stage1_dispatched_batch,
    load_or_init_aggregate_stage1_ledger,
    prepare_stage1_pre_submit_intent,
)
from w07_g4_scorer.route2_secret_vault import seal_provider_secrets_dpapi  # noqa: E402
from w07_retrieval.sanitizer import sanitize_canonical_to_view  # noqa: E402


def _make_137_synth_corpus_and_queries(tmp_path: Path) -> tuple[list[dict[str, Any]], Path, str]:
    docs: list[dict[str, Any]] = []
    cities = ("Hà Nội", "Đà Nẵng", "Hạ Long")
    v_parts: list[str] = []
    for i in range(137):
        city = cities[i % 3]
        pid = f"poi-synth-{i % 10:02d}"
        if i == 0:
            canon_s = (
                "Phở 10 Lý Quốc Sư tại Hà Nội [CORROBORATED: wikidata:Q1184365] "
                "mở cửa 06:30-22:00 hằng ngày. Liên hệ hòa@nhà-hàng.vn hoặc <UNTRUSTED>."
            )
            pid = "poi-dev-q01"
            city = "Hà Nội"
        else:
            canon_s = f"Tài liệu mẫu số {i} tại {city} [CORROBORATED: osm:node/{1000 + i}] mô tả điểm tham quan."
        san = sanitize_canonical_to_view(canon_s)
        did = f"doc-synth-{i:03d}"
        v_parts.append(f"{did}::{san.view_V}")
        docs.append(
            {
                "document_id": did,
                "poi_id": pid,
                "city": city,
                "source_type": "synthetic_arm_p",
                "language": "vi",
                "canonical_text_S": canon_s,
                "sanitized_text_V": san.view_V,
                "v_to_s_segments": [list(seg) for seg in san.segments],
                "removed_r_audit": [list(r) for r in san.removed_intervals],
            }
        )
    v_sha = sha256_bytes("\n<<<DOC>>>\n".join(v_parts).encode("utf-8"))

    queries_payload = {
        "schema_version": "W07_STAGE1_DEV5_CANDIDATE_QUERIES_V1_2",
        "queries": [
            {
                "query_id": "W07-STAGE1-DEV-CAND-Q01",
                "split": "DEV_CANDIDATE_QUARANTINED",
                "query_text": "Phở 10 Hà Nội mở cửa mấy giờ?",
                "sealed_query_meta": {
                    "target_city": "Hà Nội",
                    "scope_mode": "STRICT_TARGET_POI",
                    "target_poi_ids": ["poi-dev-q01"],
                    "query_intent_polarity": "AFFIRMATIVE_FACT_NEED",
                    "requested_facet_keywords": ["giờ mở cửa"],
                },
            },
            {
                "query_id": "W07-STAGE1-DEV-CAND-Q02",
                "split": "DEV_CANDIDATE_QUARANTINED",
                "query_text": "Điểm lịch sử nào nổi bật ở Hà Nội?",
                "sealed_query_meta": {
                    "target_city": "Hà Nội",
                    "scope_mode": "CITY_MULTI_POI",
                    "target_poi_ids": ["poi-synth-01", "poi-synth-04"],
                    "query_intent_polarity": "AFFIRMATIVE_FACT_NEED",
                    "requested_facet_keywords": ["lịch sử"],
                },
            },
            {
                "query_id": "W07-STAGE1-DEV-CAND-Q03",
                "split": "DEV_CANDIDATE_QUARANTINED",
                "query_text": "Cảnh quan Đà Nẵng có gì nổi bật?",
                "sealed_query_meta": {
                    "target_city": "Đà Nẵng",
                    "scope_mode": "STRICT_TARGET_POI",
                    "target_poi_ids": ["poi-synth-02"],
                    "query_intent_polarity": "AFFIRMATIVE_FACT_NEED",
                    "requested_facet_keywords": ["cảnh quan"],
                },
            },
            {
                "query_id": "W07-STAGE1-DEV-CAND-Q04",
                "split": "DEV_CANDIDATE_QUARANTINED",
                "query_text": "Bảo tàng Đà Nẵng nằm ở đâu?",
                "sealed_query_meta": {
                    "target_city": "Đà Nẵng",
                    "scope_mode": "STRICT_TARGET_POI",
                    "target_poi_ids": ["poi-synth-05"],
                    "query_intent_polarity": "AFFIRMATIVE_FACT_NEED",
                    "requested_facet_keywords": ["địa chỉ"],
                },
            },
            {
                "query_id": "W07-STAGE1-DEV-CAND-Q06",
                "split": "DEV_CANDIDATE_QUARANTINED",
                "query_text": "Hạ Long có bãi đỗ xe qua đêm thời gian thực không?",
                "sealed_query_meta": {
                    "target_city": "Hạ Long",
                    "scope_mode": "STRICT_TARGET_POI",
                    "target_poi_ids": ["poi-synth-08"],
                    "query_intent_polarity": "BOOLEAN_ELIGIBILITY_OR_POLICY_CHECK",
                    "requested_facet_keywords": ["đỗ xe"],
                },
            },
        ],
    }
    q_path = tmp_path / "dev5_queries.json"
    q_path.write_text(json.dumps(queries_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return docs, q_path, v_sha


def _setup_phase2_pack_and_dev5_configs(
    tmp_path: Path,
    *,
    authorized_stage: str = "STAGE1_DEV_CANARY_ONLY",
    rate_input: float = 0.05,
    rate_output: float = 0.25,
) -> dict[str, Any]:
    real_dev5_cfg = Path(__file__).resolve().parents[2] / "W07_OWNER_DEV5_RUN_20261119" / "03_stage1_configs_and_cost_estimator"
    dev5_root = tmp_path / "dev5_root"
    cfg_dir = dev5_root / "03_stage1_configs_and_cost_estimator"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    real_prompt_p = real_dev5_cfg / "W07_DEV_STATIC_PROMPT_TEMPLATE_CANDIDATE_v1_1_offset01.json"
    real_schema_p = real_dev5_cfg / "W07_DEV_RESPONSE_SCHEMA_CANDIDATE_v1.json"
    assert real_prompt_p.is_file() and real_schema_p.is_file()
    (cfg_dir / real_prompt_p.name).write_bytes(real_prompt_p.read_bytes())
    (cfg_dir / real_schema_p.name).write_bytes(real_schema_p.read_bytes())

    keys_dir = tmp_path / "owner_keys"
    assert activation_cli_main(["owner-init-keypair", "--out-dir", str(keys_dir)]) == 0
    owner_pem = keys_dir / "owner_ed25519_private.pem"
    target_zip_sha = sha256_bytes(b"unit-test-verified-amendment02-zip")

    pack_dir = tmp_path / "pack"
    tr_dir = tmp_path / "ext_trust_root"
    evidence_dir = tmp_path / "ext_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    materialize_unsigned_activation_pack(pack_dir)

    p1_path = evidence_dir / "CHATGPT_PHASE1_VERDICT.json"
    p1_path.write_text(
        json.dumps(_make_strict_verdict_json(verdict="SCOPED_PASS", target_zip_sha=target_zip_sha), indent=2),
        encoding="utf-8",
    )
    p1_rep_sha = sha256_bytes(p1_path.read_bytes())

    p1_res = sign_ceremony_with_pem_keys(
        owner_private_pem_path=owner_pem,
        auditor_private_pem_path=None,
        trust_root_dir=tr_dir,
        pack_dir=pack_dir,
        gate_phase="PRE_PREFLIGHT_PROBE_ONLY",
        sv01_waiver_ratified=True,
        auditor_verdict_mode=AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER,
        auditor_report_artifact_path=p1_path,
        expected_target_zip_sha256=target_zip_sha,
    )

    rate_ev_path = evidence_dir / "provider_rate_evidence.json"
    rate_ev_path.write_text(
        json.dumps(
            {
                "schema_version": "GOMATE_W07_PROVIDER_RATE_EVIDENCE_V1",
                "owner_accepted_rates": True,
                "captured_at_utc": "2026-11-23T10:00:00Z",
                "providers": {
                    "openai": {
                        "model_snapshot_id": "gpt-6-luna",
                        "source_url": "https://platform.openai.com/pricing/",
                        "evidence_artifact_sha256": sha256_bytes(b"oai-pricing"),
                        "batch_input_usd_per_1m": rate_input,
                        "batch_output_usd_per_1m": rate_output,
                    },
                    "anthropic": {
                        "model_snapshot_id": "claude-haiku-5-5",
                        "source_url": "https://platform.claude.com/docs/en/pricing",
                        "evidence_artifact_sha256": sha256_bytes(b"ant-pricing"),
                        "batch_input_usd_per_1m": rate_input,
                        "batch_output_usd_per_1m": rate_output,
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    rate_ev_sha = sha256_bytes(rate_ev_path.read_bytes())

    raw_probe_p = pack_dir / "raw_probe_transcript.json"
    raw_probe_p.write_text(
        json.dumps(
            {
                "schema_version": "GOMATE_W07_ROUTE2_RAW_PROBE_TRANSCRIPT_V1",
                "max_item_tokens_measured": 34875,
                "projected_stage1_worst_case_usd": 1.32,
                "judge_snapshots": {"judge_A": "gpt-6-luna", "judge_B": "claude-haiku-5-5"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    raw_probe_sha = sha256_bytes(raw_probe_p.read_bytes())

    status_p = pack_dir / "provider_preflight_status.json"
    status_p.write_text(
        json.dumps(
            {
                "snapshots_verified_live": True,
                "vendor_count_tokens_verified": True,
                "raw_probe_transcript_sha256": raw_probe_sha,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    status_sha = sha256_bytes(status_p.read_bytes())

    vault_p = tmp_path / "ext_vault" / "vault.dpapi.json"
    seal_provider_secrets_dpapi(
        {
            "OPENAI_API_KEY": "SYNTH_OPENAI_UNIT_TEST_SECRET_99887766",
            "ANTHROPIC_API_KEY": "SYNTH_ANTHROPIC_UNIT_TEST_SECRET_112233",
        },
        vault_path=vault_p,
    )

    if authorized_stage == "PRE_PREFLIGHT_PROBE_ONLY":
        pins = p1_res["out_of_band_pins"]
        return {
            "dev5_root": dev5_root,
            "pack_dir": pack_dir,
            "trust_root_dir": tr_dir,
            "rate_evidence_path": rate_ev_path,
            "raw_probe_path": raw_probe_p,
            "vault_path": vault_p,
            "oob_owner_sha": pins["owner_pubkey_sha256"],
            "oob_manifest_sha": pins["trust_root_manifest_sha256"],
            "oob_report_sha": pins["auditor_report_sha256"],
            "target_zip_sha": target_zip_sha,
        }

    p2_path = evidence_dir / "CHATGPT_PHASE2_VERDICT.json"
    p2_path.write_text(
        json.dumps(
            _make_strict_verdict_json(
                verdict="PASS",
                authorized_stage="STAGE1_DEV_CANARY_ONLY",
                target_zip_sha=target_zip_sha,
                bound_preflight_artifacts={
                    "raw_probe_transcript_sha256": raw_probe_sha,
                    "provider_preflight_status_sha256": status_sha,
                    "rate_evidence_sha256": rate_ev_sha,
                    "phase1_auditor_verdict_sha256": p1_rep_sha,
                },
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    p2_res = sign_ceremony_with_pem_keys(
        owner_private_pem_path=owner_pem,
        auditor_private_pem_path=None,
        trust_root_dir=tr_dir,
        pack_dir=pack_dir,
        gate_phase="STAGE1_LIVE",
        sv01_waiver_ratified=True,
        auditor_verdict_mode=AUDITOR_VERDICT_MODE_TEXT_SHA256_OWNER,
        auditor_report_artifact_path=p2_path,
        expected_target_zip_sha256=target_zip_sha,
        raw_probe_transcript_path=raw_probe_p,
        preflight_status_path=status_p,
        rate_evidence_path=rate_ev_path,
    )
    pins2 = p2_res["out_of_band_pins"]
    return {
        "dev5_root": dev5_root,
        "pack_dir": pack_dir,
        "trust_root_dir": tr_dir,
        "rate_evidence_path": rate_ev_path,
        "raw_probe_path": raw_probe_p,
        "vault_path": vault_p,
        "oob_owner_sha": pins2["owner_pubkey_sha256"],
        "oob_manifest_sha": pins2["trust_root_manifest_sha256"],
        "oob_report_sha": pins2["auditor_report_sha256"],
        "target_zip_sha": target_zip_sha,
    }


@pytest.fixture(autouse=True)
def _isolate_shared_budget_ledger_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Prevent any unit test from reading or creating the host _w07_auto_eval_isolated_logs directory."""
    root = tmp_path / "_isolated_shared_ledger_root"
    monkeypatch.setattr(live_mod, "DEFAULT_STAGE1_SHARED_LEDGER_ROOT", root)
    return root


def _default_quote_for_doc(safe_doc_v: str) -> dict[str, Any]:
    return {"grade": "REL_0", "evidence_quote": None, "char_start": None, "char_end": None}


class _SimulatedProviderServer:
    """In-memory deterministic OpenAI + Anthropic Batch HTTP responder verifying durability & auth headers."""

    def __init__(
        self,
        *,
        ledger_path: Path,
        output_dir: Path | None = None,
        oai_mode: str = "completed",
        ant_mode: str = "ended",
    ) -> None:
        self.ledger_path = ledger_path
        self.output_dir = output_dir or ledger_path.parent
        self.oai_mode = oai_mode
        self.ant_mode = ant_mode
        self.calls: list[dict[str, Any]] = []
        self.oai_files: dict[str, bytes] = {}
        self.oai_file_records: dict[str, dict[str, Any]] = {}
        self.oai_batches: dict[str, dict[str, Any]] = {}
        self.ant_batches: dict[str, dict[str, Any]] = {}
        self.ant_results_bytes: dict[str, bytes] = {}
        self.deleted_files: list[str] = []
        self.deleted_ant_batches: list[str] = []
        self.oai_batch_seq = 0
        self.ant_batch_seq = 0
        self.file_seq = 0
        self.fail_custom_ids_once: set[str] = set()
        self.positive_quote_by_cid: dict[str, str] = {}
        self.fail_all_oai_items = False
        self.inject_snapshot_drift: str | None = None
        self.inject_cliff_tokens: int | None = None
        self.on_create_oai_crash: bool = False
        self.on_create_ant_crash: bool = False
        self.fail_oai_batch_post_4xx: bool = False
        self.fail_oai_delete_file_500: bool = False
        self.fail_oai_delete_file_ids: set[str] = set()
        self.fail_oai_batch_post_timeout_no_accept: bool = False
        self.fail_oai_upload_lost_response: bool = False
        self.fail_oai_list_files_500: bool = False
        self.oai_list_files_page_size: int = 100
        self.inject_oai_list_files_missing_cursor: bool = False
        self.inject_oai_list_files_repeat_cursor: bool = False
        self.inject_oai_list_files_has_more_mode: str | None = None
        self.require_complete_marker_before_delete: bool = True
        self.output_dir_raw_outcomes = self.output_dir / "raw_batch_outcomes"

    def add_unrelated_anthropic_fixture(
        self,
        *,
        batch_id: str,
        item_count: int,
        processing_status: str = "in_progress",
        created_at: str = "2026-11-23T12:00:00Z",
        dispatch_tag: str = "deadbe",
    ) -> None:
        res_url = f"https://api.anthropic.com/v1/messages/batches/{batch_id}/results"
        reqs = [
            {
                "custom_id": f"{i:032x}__PROMPT_ORDER_CANONICAL__{dispatch_tag}",
                "params": {
                    "messages": [
                        {"role": "user", "content": "<UNTRUSTED_CORPUS_DOCUMENT_0>\nDummy\n</UNTRUSTED_CORPUS_DOCUMENT_0>"}
                    ]
                },
            }
            for i in range(item_count)
        ]
        self.ant_results_bytes[batch_id] = self._build_ant_results_jsonl(reqs)
        status_lower = processing_status.lower()
        self.ant_batches[batch_id] = {
            "id": batch_id,
            "type": "message_batch",
            "created_at": created_at,
            "processing_status": status_lower,
            "results_url": res_url if status_lower == "ended" else None,
            "request_counts": {
                "processing": item_count if status_lower != "ended" else 0,
                "succeeded": item_count if status_lower == "ended" else 0,
                "errored": 0,
                "canceled": 0,
                "expired": 0,
            },
            "_ready_url": res_url,
            "_polls": 0,
            "_unrelated_fixture": True,
        }

    def opener(self, req: urllib.request.Request, timeout: float) -> tuple[int, dict[str, str], bytes]:
        del timeout
        url = req.full_url
        method = req.get_method()
        raw_data = req.data if isinstance(req.data, (bytes, bytearray)) else b""
        self.calls.append({"method": method, "url": url})

        if url.startswith("https://api.openai.com"):
            assert req.get_header("Authorization") == "Bearer SYNTH_OPENAI_UNIT_TEST_SECRET_99887766"
            if url.endswith("/v1/files") and method == "POST":
                # Extract uploaded filename & JSONL from multipart body cleanly
                fn_marker = b'filename="'
                fn_start = raw_data.index(fn_marker) + len(fn_marker)
                fn_end = raw_data.index(b'"', fn_start)
                uploaded_fn = raw_data[fn_start:fn_end].decode("utf-8")
                if self.ledger_path.is_file():
                    led_pre = json.loads(self.ledger_path.read_text(encoding="utf-8"))
                    matching_intents = [
                        v for v in (led_pre.get("intents") or {}).values()
                        if v.get("input_upload_filename") == uploaded_fn
                    ]
                    assert len(matching_intents) == 1, f"Missing durable UPLOAD_IN_FLIGHT checkpoint for {uploaded_fn}"
                    assert matching_intents[0]["dispatch_stage"] == "UPLOAD_IN_FLIGHT"
                    assert matching_intents[0]["file_cleanup_status"] == "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE"

                self.file_seq += 1
                fid = f"file-oai-in-{self.file_seq}"
                marker = b"Content-Type: application/jsonl\r\n\r\n"
                start = raw_data.index(marker) + len(marker)
                end = raw_data.rindex(b"\r\n--")
                raw_jsonl = bytes(raw_data[start:end])
                self.oai_files[fid] = raw_jsonl
                self.oai_file_records[fid] = {
                    "id": fid,
                    "object": "file",
                    "purpose": "batch",
                    "filename": uploaded_fn,
                    "bytes": len(raw_jsonl),
                    "created_at": int(live_mod._parse_iso_unix(live_mod._utc_now_iso()) or 0),
                }
                if self.fail_oai_upload_lost_response:
                    raise TimeoutError("SIMULATED_LOST_RESPONSE_AFTER_UPLOAD_ACCEPTED")
                return 200, {}, json.dumps(self.oai_file_records[fid]).encode("utf-8")

            if "/v1/files?" in url and method == "GET":
                if self.fail_oai_list_files_500:
                    return 500, {}, json.dumps({"error": "temporary file listing outage"}).encode("utf-8")
                all_recs = list(self.oai_file_records.values())
                if self.inject_oai_list_files_missing_cursor:
                    # Simulate malformed server pagination: has_more=True without cursor/id.
                    return 200, {}, json.dumps({"object": "list", "data": [], "has_more": True}).encode("utf-8")
                if self.inject_oai_list_files_repeat_cursor:
                    # Simulate repeated cursor loop: every page returns the exact same last id with has_more=True.
                    return 200, {}, json.dumps(
                        {
                            "object": "list",
                            "data": [{"id": "file-loop-cursor", "filename": "other.jsonl"}],
                            "has_more": True,
                        }
                    ).encode("utf-8")
                after_val: str | None = None
                if "after=" in url:
                    after_val = url.split("after=", 1)[1].split("&", 1)[0]
                start_idx = 0
                if after_val is not None:
                    for i, rec in enumerate(all_recs):
                        if rec.get("id") == after_val:
                            start_idx = i + 1
                            break
                psize = max(1, int(self.oai_list_files_page_size))
                page_recs = all_recs[start_idx : start_idx + psize]
                has_more = (start_idx + psize) < len(all_recs)
                payload_obj: dict[str, Any] = {"object": "list", "data": page_recs}
                mode = self.inject_oai_list_files_has_more_mode
                if mode == "omit":
                    pass
                elif mode == "none":
                    payload_obj["has_more"] = None
                elif mode == "str_false":
                    payload_obj["has_more"] = "false"
                elif mode == "int_zero":
                    payload_obj["has_more"] = 0
                else:
                    payload_obj["has_more"] = has_more
                return 200, {}, json.dumps(payload_obj).encode("utf-8")

            if url.endswith("/v1/batches") and method == "POST":
                # P1-C invariant: INTENT_PRE_SUBMIT & durable input_file_id MUST exist on disk BEFORE POST /v1/batches!
                assert self.ledger_path.is_file()
                ledger = json.loads(self.ledger_path.read_text(encoding="utf-8"))
                body = json.loads(raw_data.decode("utf-8"))
                idemp_key = body["metadata"]["client_idempotency_key"]
                assert idemp_key in ledger["intents"]
                assert ledger["intents"][idemp_key]["status"] == "INTENT_PRE_SUBMIT"
                assert ledger["intents"][idemp_key]["input_file_id"] == body["input_file_id"]
                assert ledger["intents"][idemp_key]["wire_dispatch_tag"] == idemp_key[:6]

                if self.fail_oai_batch_post_4xx:
                    return 400, {}, json.dumps({"error": {"message": "bad batch payload"}}).encode("utf-8")
                if self.fail_oai_batch_post_timeout_no_accept:
                    raise TimeoutError("SIMULATED_TIMEOUT_BEFORE_SERVER_ACCEPTANCE")

                self.oai_batch_seq += 1
                bid = f"batch_oai_{self.oai_batch_seq}"
                in_fid = body["input_file_id"]
                in_lines = [json.loads(ln) for ln in self.oai_files[in_fid].decode("utf-8").splitlines() if ln.strip()]
                for ln in in_lines:
                    assert ln["custom_id"].endswith(f"__{idemp_key[:6]}")
                out_fid = f"file-oai-out-{self.oai_batch_seq}"
                self.oai_files[out_fid] = self._build_oai_output_jsonl(in_lines)
                self.oai_batches[bid] = {
                    "id": bid,
                    "object": "batch",
                    "status": "validating",
                    "input_file_id": in_fid,
                    "output_file_id": None if self.oai_mode != "completed" else out_fid,
                    "error_file_id": None,
                    "metadata": body["metadata"],
                    "request_counts": {"total": len(in_lines), "completed": len(in_lines), "failed": 0},
                    "_ready_out_fid": out_fid,
                    "_polls": 0,
                }
                if self.on_create_oai_crash:
                    raise TimeoutError("SIMULATED_HTTP_TIMEOUT_AFTER_SERVER_ACCEPTANCE")
                return 200, {}, json.dumps(self.oai_batches[bid]).encode("utf-8")

            if "/v1/batches?" in url and method == "GET":
                return 200, {}, json.dumps({"data": list(self.oai_batches.values()), "has_more": False}).encode("utf-8")

            if "/v1/batches/" in url and method == "GET":
                bid = url.rsplit("/v1/batches/", 1)[1]
                b = self.oai_batches[bid]
                b["_polls"] += 1
                if self.oai_mode == "completed":
                    b["status"] = "completed"
                    b["output_file_id"] = b["_ready_out_fid"]
                elif self.oai_mode == "always_in_progress":
                    b["status"] = "in_progress"
                elif self.oai_mode == "poll_then_completed":
                    if b["_polls"] >= 2:
                        b["status"] = "completed"
                        b["output_file_id"] = b["_ready_out_fid"]
                    else:
                        b["status"] = "in_progress"
                return 200, {}, json.dumps(b).encode("utf-8")

            if "/v1/files/" in url and url.endswith("/content") and method == "GET":
                fid = url.split("/v1/files/", 1)[1].split("/content", 1)[0]
                return 200, {}, self.oai_files[fid]

            if "/v1/files/" in url and method == "DELETE":
                fid = url.rsplit("/v1/files/", 1)[1]
                if self.fail_oai_delete_file_500 or fid in self.fail_oai_delete_file_ids:
                    return 500, {}, json.dumps({"error": "temporary delete outage"}).encode("utf-8")
                self.deleted_files.append(fid)
                self.oai_file_records.pop(fid, None)
                return 200, {}, json.dumps({"id": fid, "deleted": True}).encode("utf-8")

        if url.startswith("https://api.anthropic.com"):
            assert req.get_header("X-api-key") == "SYNTH_ANTHROPIC_UNIT_TEST_SECRET_112233"
            assert req.get_header("Anthropic-version") == "2026-10-21"
            if url.endswith("/v1/messages/batches") and method == "POST":
                assert self.ledger_path.is_file()
                ledger = json.loads(self.ledger_path.read_text(encoding="utf-8"))
                ant_intents = [v for v in ledger["intents"].values() if v["provider"] == "anthropic" and v["status"] == "INTENT_PRE_SUBMIT"]
                assert len(ant_intents) >= 1

                body = json.loads(raw_data.decode("utf-8"))
                reqs = body["requests"]
                tag_suffix = f"__{ant_intents[-1]['wire_dispatch_tag']}"
                assert all(r["custom_id"].endswith(tag_suffix) for r in reqs)
                self.ant_batch_seq += 1
                bid = f"msgbatch_ant_{self.ant_batch_seq}"
                res_url = f"https://api.anthropic.com/v1/messages/batches/{bid}/results"
                self.ant_results_bytes[bid] = self._build_ant_results_jsonl(reqs)
                self.ant_batches[bid] = {
                    "id": bid,
                    "type": "message_batch",
                    "created_at": live_mod._utc_now_iso(),
                    "processing_status": "in_progress" if self.ant_mode != "ended" else "ended",
                    "results_url": res_url if self.ant_mode == "ended" else None,
                    "request_counts": {"processing": 0 if self.ant_mode == "ended" else len(reqs), "succeeded": len(reqs) if self.ant_mode == "ended" else 0, "errored": 0, "canceled": 0, "expired": 0},
                    "_ready_url": res_url,
                    "_polls": 0,
                }
                if self.on_create_ant_crash:
                    raise TimeoutError("SIMULATED_ANT_TIMEOUT_AFTER_SERVER_ACCEPTANCE")
                return 200, {}, json.dumps(self.ant_batches[bid]).encode("utf-8")

            if "/v1/messages/batches?" in url and method == "GET":
                return 200, {}, json.dumps({"data": list(self.ant_batches.values()), "has_more": False}).encode("utf-8")

            if url.endswith("/results") and method == "GET":
                bid = url.split("/v1/messages/batches/", 1)[1].split("/results", 1)[0]
                return 200, {}, self.ant_results_bytes[bid]

            if "/v1/messages/batches/" in url and method == "GET":
                bid = url.rsplit("/v1/messages/batches/", 1)[1]
                b = self.ant_batches[bid]
                if not b.get("_unrelated_fixture"):
                    b["_polls"] += 1
                    if self.ant_mode == "ended":
                        b["processing_status"] = "ended"
                        b["results_url"] = b["_ready_url"]
                    elif self.ant_mode == "always_in_progress":
                        b["processing_status"] = "in_progress"
                    elif self.ant_mode == "poll_then_ended":
                        if b["_polls"] >= 2:
                            b["processing_status"] = "ended"
                            b["results_url"] = b["_ready_url"]
                        else:
                            b["processing_status"] = "in_progress"
                return 200, {}, json.dumps(b).encode("utf-8")

            if "/v1/messages/batches/" in url and method == "DELETE":
                bid = url.rsplit("/v1/messages/batches/", 1)[1]
                # Raw results AND verified .jsonl_complete marker MUST ALREADY be persisted BEFORE DELETE!
                assert (self.output_dir_raw_outcomes / f"anthropic_{bid}.json").is_file()
                if self.require_complete_marker_before_delete:
                    assert (self.output_dir_raw_outcomes / f"anthropic_{bid}.jsonl_complete.json").is_file()
                self.deleted_ant_batches.append(bid)
                return 200, {}, json.dumps({"id": bid, "type": "message_batch_deleted"}).encode("utf-8")

        raise AssertionError(f"Unexpected mock HTTP call: {method} {url}")

    @staticmethod
    def _extract_safe_doc_from_wire(wire_user_text: str) -> str:
        lines = wire_user_text.splitlines()
        start_idx = next(i for i, ln in enumerate(lines) if ln.startswith("<UNTRUSTED_CORPUS_DOCUMENT_")) + 1
        end_idx = next(i for i, ln in enumerate(lines) if ln.startswith("</UNTRUSTED_CORPUS_DOCUMENT_"))
        return "\n".join(lines[start_idx:end_idx])

    def _build_oai_output_jsonl(self, in_lines: list[dict[str, Any]]) -> bytes:
        out_rows: list[str] = []
        in_tok = self.inject_cliff_tokens if self.inject_cliff_tokens is not None else 400
        snap = self.inject_snapshot_drift or "gpt-6-luna"
        for it in in_lines:
            wire_cid = it["custom_id"]
            canon_cid = canonicalize_custom_id(wire_cid)
            if self.fail_all_oai_items or canon_cid in self.fail_custom_ids_once:
                self.fail_custom_ids_once.discard(canon_cid)
                txt = '{"grade": "REL_2", "evidence_quote": "NON_EXISTENT", "char_start": 0, "char_end": 12}'
            elif canon_cid in self.positive_quote_by_cid:
                quote = self.positive_quote_by_cid[canon_cid]
                safe_doc = self._extract_safe_doc_from_wire(it["body"]["input"][1]["content"])
                s_off = safe_doc.index(quote)
                txt = json.dumps(
                    {"grade": "REL_2", "evidence_quote": quote, "char_start": s_off, "char_end": s_off + len(quote)},
                    ensure_ascii=False,
                )
            else:
                txt = json.dumps(_default_quote_for_doc(""), ensure_ascii=False)
            out_rows.append(
                json.dumps(
                    {
                        "id": f"req_{wire_cid}",
                        "custom_id": wire_cid,
                        "response": {
                            "status_code": 200,
                            "request_id": f"r_{wire_cid}",
                            "body": {
                                "model": snap,
                                "output": [{"type": "message", "content": [{"type": "output_text", "text": txt}]}],
                                "usage": {"input_tokens": in_tok, "output_tokens": 50},
                            },
                        },
                        "error": None,
                    }
                )
            )
        return ("\n".join(out_rows) + "\n").encode("utf-8")

    def _build_ant_results_jsonl(self, reqs: list[dict[str, Any]]) -> bytes:
        out_rows: list[str] = []
        in_tok = self.inject_cliff_tokens if self.inject_cliff_tokens is not None else 420
        for it in reqs:
            wire_cid = it["custom_id"]
            canon_cid = canonicalize_custom_id(wire_cid)
            if canon_cid in self.positive_quote_by_cid:
                quote = self.positive_quote_by_cid[canon_cid]
                safe_doc = self._extract_safe_doc_from_wire(it["params"]["messages"][0]["content"])
                s_off = safe_doc.index(quote)
                txt = json.dumps(
                    {"grade": "REL_2", "evidence_quote": quote, "char_start": s_off, "char_end": s_off + len(quote)},
                    ensure_ascii=False,
                )
            else:
                txt = json.dumps(_default_quote_for_doc(""), ensure_ascii=False)
            out_rows.append(
                json.dumps(
                    {
                        "custom_id": wire_cid,
                        "result": {
                            "type": "succeeded",
                            "message": {
                                "id": f"msg_{wire_cid}",
                                "model": "claude-haiku-5-5",
                                "content": [{"type": "text", "text": txt}],
                                "usage": {"input_tokens": in_tok, "output_tokens": 60},
                            },
                        },
                    }
                )
            )
        return ("\n".join(out_rows) + "\n").encode("utf-8")


def test_dev5_live_gate_quarantine_filter_and_zero_ml_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert_g4_package_zero_ml_imports()
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    out_dir = tmp_path / "isolated_out"

    # 1. allow_live_network=False is blocked fail-closed.
    with pytest.raises(PermissionError, match="HOLD_STAGE1_LIVE_REQUIRES_ALLOW_LIVE_NETWORK"):
        run_stage1_dev5_live_batch(
            activation_pack_dir=env["pack_dir"],
            external_trust_root_dir=env["trust_root_dir"],
            dev5_root=env["dev5_root"],
            corpus_docs=docs,
            queries_json_path=q_path,
            rate_evidence_path=env["rate_evidence_path"],
            output_dir=out_dir,
            allow_live_network=False,
        )

    # 2. Phase-1 PRE_PREFLIGHT_PROBE_ONLY receipt cannot authorize STAGE1_LIVE.
    p1 = _setup_phase2_pack_and_dev5_configs(tmp_path / "p1_only", authorized_stage="PRE_PREFLIGHT_PROBE_ONLY")
    with pytest.raises(
        PermissionError,
        match="MISSING_SIGNED_RECEIPT_FILE|HOLD_PHASE_MISMATCH|NOT_YET_AUTHORIZED|STAGE1_DEV_CANARY_ONLY|PREFLIGHT_SCOPE",
    ):
        run_stage1_dev5_live_batch(
            activation_pack_dir=p1["pack_dir"],
            external_trust_root_dir=p1["trust_root_dir"],
            dev5_root=p1["dev5_root"],
            corpus_docs=docs,
            queries_json_path=q_path,
            rate_evidence_path=p1["rate_evidence_path"],
            output_dir=tmp_path / "out_p1",
            allow_live_network=True,
            out_of_band_owner_pubkey_sha256=p1["oob_owner_sha"],
            out_of_band_manifest_sha256=p1["oob_manifest_sha"],
            out_of_band_auditor_report_sha256=p1["oob_report_sha"],
            expected_target_zip_sha256=p1["target_zip_sha"],
            raw_probe_transcript_path=p1["raw_probe_path"],
        )

    # 3. Dropped Q05 and FINAL queries are strictly blocked by DEV-5 loader.
    bad_q = json.loads(q_path.read_text(encoding="utf-8"))
    bad_q["queries"][0]["query_id"] = "W07-STAGE1-DEV-CAND-Q05"
    bad_qp = tmp_path / "bad_q05.json"
    bad_qp.write_text(json.dumps(bad_q), encoding="utf-8")
    with pytest.raises(PermissionError, match="DROPPED_DEV5_QUERY_BLOCKED"):
        load_approved_dev5_queries(bad_qp)

    bad_final = json.loads(q_path.read_text(encoding="utf-8"))
    bad_final["queries"][0]["query_id"] = "FINAL-01"
    bad_final["queries"][0]["split"] = "FINAL"
    bad_fp = tmp_path / "bad_final.json"
    bad_fp.write_text(json.dumps(bad_final), encoding="utf-8")
    with pytest.raises(PermissionError, match="FINAL_CONTAMINATION_BLOCKED"):
        load_approved_dev5_queries(bad_fp)

    # 4. Dry-run inspect verifies Phase-2 pack and DEV-5 plan with 0 live calls.
    rep = inspect_stage1_dev5_live_readiness(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=out_dir,
        slice_mode="canary_1x10",
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
        vault_path=env["vault_path"],
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )
    assert rep["live_api_calls_executed"] == 0
    assert rep["phase2_authorization"]["batch_generation_authorized"] is True
    assert rep["fits_combined_dev_cap"] is True
    assert rep["planned_batches"]["openai"]["pending_to_send_items"] == 10
    assert rep["planned_batches"]["anthropic"]["pending_to_send_items"] == 10


def test_live_happy_path_firewall_retry_cleanup_and_idempotent_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    out_dir = tmp_path / "live_happy"
    ledger_path = live_mod.resolve_stage1_shared_budget_ledger_path()

    # Build 10-doc canary items manually just to verify wire custom_id & Unicode email/delimiter escaping.
    qs = load_approved_dev5_queries(q_path)
    preview_items = build_approved_dev5_canary_items(
        dev5_queries=qs,
        corpus_docs=docs,
        slice_mode="canary_1x10",
        packet_salt="salt-1",
        run_nonce_seed="seed-1",
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
    )
    ant_wire = build_verified_live_wire_item(
        provider="anthropic",
        model_id="claude-haiku-5-5",
        item=preview_items[0],
        system_prompt=(env["dev5_root"] / "03_stage1_configs_and_cost_estimator" / "W07_DEV_STATIC_PROMPT_TEMPLATE_CANDIDATE_v1_1_offset01.json").read_text(encoding="utf-8") and json.loads((env["dev5_root"] / "03_stage1_configs_and_cost_estimator" / "W07_DEV_STATIC_PROMPT_TEMPLATE_CANDIDATE_v1_1_offset01.json").read_text(encoding="utf-8"))["system_prompt"],
        response_schema=PROMPT_S4_SCHEMA,
    )
    assert "::" not in ant_wire["wire_custom_id"]
    assert "[REDACTED_EMAIL]" in ant_wire["safe_doc_v"]
    assert "hòa@nhà-hàng.vn" not in json.dumps(ant_wire["wire_item"], ensure_ascii=False)
    assert "doc-synth-000" not in json.dumps(ant_wire["wire_item"], ensure_ascii=False)

    sim = _SimulatedProviderServer(
        ledger_path=ledger_path,
        output_dir=out_dir,
        oai_mode="poll_then_completed",
        ant_mode="poll_then_ended",
    )
    # Inject 1/10 (10% <= 15%) OpenAI schema error on first item so single retry executes cleanly.
    first_canon_cid = f"{hashlib_uuid_for(q0_id='W07-STAGE1-DEV-CAND-Q01', d0_id='doc-synth-000')}::PROMPT_ORDER_CANONICAL"
    # Even simpler: fail whichever OpenAI item arrives for doc-synth-001! Let's deterministically use fail_custom_ids_once by running packet salt OR matching index.
    # Let's resolve exact custom_id using _load_or_init_run_manifest determinism after run_nonce_seed, OR fail index 1 via wrapper? Better: resolve exact canon_cid using the exact salt formula!
    import hashlib
    qids = [q["query_id"] for q in qs]
    q_digest = sha256_bytes(json.dumps(qids, separators=(",", ":")).encode("utf-8"))
    pkt_salt = sha256_bytes(f"GOMATE_W07_DEV5_PACKET_SALT|{v_sha}|{q_digest}".encode("utf-8"))[:32]
    pkt0_uuid = hashlib.sha256(f"{pkt_salt}|W07-STAGE1-DEV-CAND-Q01|doc-synth-000".encode("utf-8")).hexdigest()[:32]
    sim.fail_custom_ids_once.add(f"{pkt0_uuid}::PROMPT_ORDER_CANONICAL")
    sim.positive_quote_by_cid[f"{pkt0_uuid}::PROMPT_ORDER_CANONICAL"] = "mở cửa 06:30-22:00 hằng ngày"

    summary = run_stage1_dev5_live_batch(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=out_dir,
        slice_mode="canary_1x10",
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
        allow_live_network=True,
        poll_interval_seconds=0.01,
        max_wait_seconds=5.0,
        sleep_fn=lambda _s: None,
        vault_path=env["vault_path"],
        url_opener=sim.opener,
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )
    assert summary["overall_status"] == "COMPLETED"
    assert summary["providers"]["openai"]["settled_items"] == 10
    assert summary["providers"]["anthropic"]["settled_items"] == 10
    assert summary["providers"]["openai"]["grade_counts"].get("REL_2") == 1
    assert summary["providers"]["anthropic"]["grade_counts"].get("REL_2") == 1
    oai_settled = [
        json.loads(ln)
        for ln in (out_dir / "openai_raw_log.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(ln).get("final_for_item") and json.loads(ln)["custom_id"] == f"{pkt0_uuid}::PROMPT_ORDER_CANONICAL"
    ]
    assert len(oai_settled) == 1
    proj_oai = oai_settled[0]["projected_canonical_response"]
    assert docs[0]["canonical_text_S"][proj_oai["char_start"] : proj_oai["char_end"]] == "mở cửa 06:30-22:00 hằng ngày"
    assert summary["total_unresolved_reserve_usd"] == 0.0
    assert summary["total_confirmed_spent_usd"] > 0.0
    # 2 OpenAI batches (pass1 + 1-item retry) => 4 deleted files (2 in + 2 out); 1 Anthropic batch deleted.
    assert len(sim.deleted_files) == 4
    assert len(sim.deleted_ant_batches) == 1

    # Re-running the exact same command does ZERO HTTP calls and spends $0.00!
    calls_before = len(sim.calls)
    res_idemp = run_stage1_dev5_live_batch(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=out_dir,
        slice_mode="canary_1x10",
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
        allow_live_network=True,
        vault_path=env["vault_path"],
        url_opener=sim.opener,
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )
    assert res_idemp["dispatched_this_run"] == []
    assert len(sim.calls) == calls_before


def hashlib_uuid_for(*, q0_id: str, d0_id: str) -> str:
    return f"{q0_id}_{d0_id}"


def test_combined_2usd_cap_crash_recovery_nonterminal_resume_and_slice_upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)

    # 1. Combined two-provider $2.00 cap MUST block BEFORE any HTTP POST if pre-existing reserve + new > $2.00.
    monkeypatch.setattr(live_mod, "DEFAULT_STAGE1_SHARED_LEDGER_ROOT", tmp_path / "shared_cap")
    env_ok = _setup_phase2_pack_and_dev5_configs(tmp_path / "cap")
    out_cap = tmp_path / "out_cap"
    out_cap.mkdir(parents=True, exist_ok=True)
    agg_ledger = live_mod.resolve_stage1_shared_budget_ledger_path()
    prepare_stage1_pre_submit_intent(
        ledger_path=agg_ledger,
        run_id="prior-reserve",
        rate_profile=ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 0.05, 0.25),
        custom_ids=["existing-1"],
        batch_reserved_worst_case_usd=1.99,
    )
    sim_never = _SimulatedProviderServer(ledger_path=agg_ledger, output_dir=out_cap)
    with pytest.raises(PermissionError, match="STAGE1_COMBINED_TWO_PROVIDER_DEV_CAP_EXCEEDED"):
        led = json.loads(agg_ledger.read_text(encoding="utf-8"))
        k0 = next(iter(led["intents"]))
        led["intents"][k0]["status"] = "SETTLED"
        led["intents"][k0]["confirmed_cost_usd"] = 1.995
        led["total_unresolved_reserve_usd"] = 0.0
        led["total_confirmed_spent_usd"] = 1.995
        led["effective_committed_usd"] = 1.995
        agg_ledger.write_text(json.dumps(led), encoding="utf-8")

        run_stage1_dev5_live_batch(
            activation_pack_dir=env_ok["pack_dir"],
            external_trust_root_dir=env_ok["trust_root_dir"],
            dev5_root=env_ok["dev5_root"],
            corpus_docs=docs,
            queries_json_path=q_path,
            rate_evidence_path=env_ok["rate_evidence_path"],
            output_dir=out_cap,
            slice_mode="canary_1x10",
            allow_live_network=True,
            vault_path=env_ok["vault_path"],
            url_opener=sim_never.opener,
            out_of_band_owner_pubkey_sha256=env_ok["oob_owner_sha"],
            out_of_band_manifest_sha256=env_ok["oob_manifest_sha"],
            out_of_band_auditor_report_sha256=env_ok["oob_report_sha"],
            expected_target_zip_sha256=env_ok["target_zip_sha"],
            raw_probe_transcript_path=env_ok["raw_probe_path"],
        )
    assert len(sim_never.calls) == 0

    # 2. Non-terminal AWAITING_BATCH_COMPLETION -> re-run / resume finishes cleanly WITHOUT duplicate submit!
    monkeypatch.setattr(live_mod, "DEFAULT_STAGE1_SHARED_LEDGER_ROOT", tmp_path / "shared_async")
    out_async = tmp_path / "out_async"
    sim_async = _SimulatedProviderServer(
        ledger_path=live_mod.resolve_stage1_shared_budget_ledger_path(),
        output_dir=out_async,
        oai_mode="always_in_progress",
        ant_mode="always_in_progress",
    )
    res_wait = run_stage1_dev5_live_batch(
        activation_pack_dir=env_ok["pack_dir"],
        external_trust_root_dir=env_ok["trust_root_dir"],
        dev5_root=env_ok["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env_ok["rate_evidence_path"],
        output_dir=out_async,
        slice_mode="canary_1x10",
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
        allow_live_network=True,
        max_wait_seconds=0.0,
        poll_interval_seconds=0.0,
        vault_path=env_ok["vault_path"],
        url_opener=sim_async.opener,
        out_of_band_owner_pubkey_sha256=env_ok["oob_owner_sha"],
        out_of_band_manifest_sha256=env_ok["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env_ok["oob_report_sha"],
        expected_target_zip_sha256=env_ok["target_zip_sha"],
        raw_probe_transcript_path=env_ok["raw_probe_path"],
    )
    assert res_wait["overall_status"] == "AWAITING_BATCH_COMPLETION"
    assert res_wait["total_unresolved_reserve_usd"] > 0.0
    assert sim_async.oai_batch_seq == 1 and sim_async.ant_batch_seq == 1

    # Now provider finishes -> resume completes without creating batch #2!
    sim_async.oai_mode = "completed"
    sim_async.ant_mode = "ended"
    res_done = run_stage1_dev5_live_batch(
        activation_pack_dir=env_ok["pack_dir"],
        external_trust_root_dir=env_ok["trust_root_dir"],
        dev5_root=env_ok["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env_ok["rate_evidence_path"],
        output_dir=out_async,
        slice_mode="canary_1x10",
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
        allow_live_network=True,
        resume_only=True,
        vault_path=env_ok["vault_path"],
        url_opener=sim_async.opener,
        out_of_band_owner_pubkey_sha256=env_ok["oob_owner_sha"],
        out_of_band_manifest_sha256=env_ok["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env_ok["oob_report_sha"],
        expected_target_zip_sha256=env_ok["target_zip_sha"],
        raw_probe_transcript_path=env_ok["raw_probe_path"],
    )
    assert res_done["overall_status"] == "COMPLETED"
    assert sim_async.oai_batch_seq == 1 and sim_async.ant_batch_seq == 1
    assert res_done["dispatched_this_run"] == []

    # 3. Upgrading slice in SAME output_dir from canary_1x10 -> dev5_plus_20pct_swap (822 items)
    # skips the 10 already-settled items cleanly and sends ONLY 812!
    res_full = run_stage1_dev5_live_batch(
        activation_pack_dir=env_ok["pack_dir"],
        external_trust_root_dir=env_ok["trust_root_dir"],
        dev5_root=env_ok["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env_ok["rate_evidence_path"],
        output_dir=out_async,
        slice_mode="dev5_plus_20pct_swap",
        allow_live_network=True,
        vault_path=env_ok["vault_path"],
        url_opener=sim_async.opener,
        out_of_band_owner_pubkey_sha256=env_ok["oob_owner_sha"],
        out_of_band_manifest_sha256=env_ok["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env_ok["oob_report_sha"],
        expected_target_zip_sha256=env_ok["target_zip_sha"],
        raw_probe_transcript_path=env_ok["raw_probe_path"],
    )
    assert res_full["overall_status"] == "COMPLETED"
    assert res_full["dispatched_this_run"][0]["item_count"] == 812
    assert res_full["dispatched_this_run"][1]["item_count"] == 812
    assert res_full["providers"]["openai"]["settled_items"] == 822
    assert res_full["providers"]["anthropic"]["settled_items"] == 822
    assert res_full["prompt_order_bias"]["openai"]["exact_swap_agreement"] == 1.0
    assert res_full["prompt_order_bias"]["openai"]["declared_coverage_mode"] == "STRATIFIED_20PCT_DEV_AUDIT"

    # 4. Pre-submit crash recovery on OpenAI: HTTP POST succeeded server-side, client crashed BEFORE link!
    monkeypatch.setattr(live_mod, "DEFAULT_STAGE1_SHARED_LEDGER_ROOT", tmp_path / "shared_oai_crash")
    out_crash = tmp_path / "out_crash"
    sim_crash = _SimulatedProviderServer(ledger_path=live_mod.resolve_stage1_shared_budget_ledger_path(), output_dir=out_crash)
    sim_crash.on_create_oai_crash = True
    with pytest.raises(live_mod.LiveTransportError, match="SIMULATED_HTTP_TIMEOUT_AFTER_SERVER_ACCEPTANCE"):
        run_stage1_dev5_live_batch(
            activation_pack_dir=env_ok["pack_dir"],
            external_trust_root_dir=env_ok["trust_root_dir"],
            dev5_root=env_ok["dev5_root"],
            corpus_docs=docs,
            queries_json_path=q_path,
            rate_evidence_path=env_ok["rate_evidence_path"],
            output_dir=out_crash,
            slice_mode="canary_1x10",
            providers=("openai",),
            allow_live_network=True,
            vault_path=env_ok["vault_path"],
            url_opener=sim_crash.opener,
            out_of_band_owner_pubkey_sha256=env_ok["oob_owner_sha"],
            out_of_band_manifest_sha256=env_ok["oob_manifest_sha"],
            out_of_band_auditor_report_sha256=env_ok["oob_report_sha"],
            expected_target_zip_sha256=env_ok["target_zip_sha"],
            raw_probe_transcript_path=env_ok["raw_probe_path"],
        )
    # Recover cleanly without sending a second batch!
    sim_crash.on_create_oai_crash = False
    res_rec = run_stage1_dev5_live_batch(
        activation_pack_dir=env_ok["pack_dir"],
        external_trust_root_dir=env_ok["trust_root_dir"],
        dev5_root=env_ok["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env_ok["rate_evidence_path"],
        output_dir=out_crash,
        slice_mode="canary_1x10",
        providers=("openai",),
        allow_live_network=True,
        vault_path=env_ok["vault_path"],
        url_opener=sim_crash.opener,
        out_of_band_owner_pubkey_sha256=env_ok["oob_owner_sha"],
        out_of_band_manifest_sha256=env_ok["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env_ok["oob_report_sha"],
        expected_target_zip_sha256=env_ok["target_zip_sha"],
        raw_probe_transcript_path=env_ok["raw_probe_path"],
    )
    assert sim_crash.oai_batch_seq == 1
    assert res_rec["providers"]["openai"]["settled_items"] == 10
    assert res_rec["total_unresolved_reserve_usd"] == 0.0

    # 5. Pre-submit crash recovery on Anthropic: POST succeeded server-side, client crashed BEFORE link!
    monkeypatch.setattr(live_mod, "DEFAULT_STAGE1_SHARED_LEDGER_ROOT", tmp_path / "shared_ant_crash")
    out_ant_crash = tmp_path / "out_ant_crash"
    sim_ant_crash = _SimulatedProviderServer(ledger_path=live_mod.resolve_stage1_shared_budget_ledger_path(), output_dir=out_ant_crash)
    sim_ant_crash.on_create_ant_crash = True
    with pytest.raises(live_mod.LiveTransportError, match="SIMULATED_ANT_TIMEOUT_AFTER_SERVER_ACCEPTANCE"):
        run_stage1_dev5_live_batch(
            activation_pack_dir=env_ok["pack_dir"],
            external_trust_root_dir=env_ok["trust_root_dir"],
            dev5_root=env_ok["dev5_root"],
            corpus_docs=docs,
            queries_json_path=q_path,
            rate_evidence_path=env_ok["rate_evidence_path"],
            output_dir=out_ant_crash,
            slice_mode="canary_1x10",
            providers=("anthropic",),
            allow_live_network=True,
            vault_path=env_ok["vault_path"],
            url_opener=sim_ant_crash.opener,
            out_of_band_owner_pubkey_sha256=env_ok["oob_owner_sha"],
            out_of_band_manifest_sha256=env_ok["oob_manifest_sha"],
            out_of_band_auditor_report_sha256=env_ok["oob_report_sha"],
            expected_target_zip_sha256=env_ok["target_zip_sha"],
            raw_probe_transcript_path=env_ok["raw_probe_path"],
        )
    sim_ant_crash.on_create_ant_crash = False
    res_ant_rec = run_stage1_dev5_live_batch(
        activation_pack_dir=env_ok["pack_dir"],
        external_trust_root_dir=env_ok["trust_root_dir"],
        dev5_root=env_ok["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env_ok["rate_evidence_path"],
        output_dir=out_ant_crash,
        slice_mode="canary_1x10",
        providers=("anthropic",),
        allow_live_network=True,
        vault_path=env_ok["vault_path"],
        url_opener=sim_ant_crash.opener,
        out_of_band_owner_pubkey_sha256=env_ok["oob_owner_sha"],
        out_of_band_manifest_sha256=env_ok["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env_ok["oob_report_sha"],
        expected_target_zip_sha256=env_ok["target_zip_sha"],
        raw_probe_transcript_path=env_ok["raw_probe_path"],
    )
    assert sim_ant_crash.ant_batch_seq == 1
    assert len(sim_ant_crash.deleted_ant_batches) == 1
    assert res_ant_rec["providers"]["anthropic"]["settled_items"] == 10
    assert res_ant_rec["total_unresolved_reserve_usd"] == 0.0


def test_circuit_breaker_snapshot_drift_cliff_and_secret_redaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)

    # 1. > 15% batch errors triggers BATCH_ABORT_EXCESSIVE_RETRY_RATE AFTER spend reconcile & cleanup!
    monkeypatch.setattr(live_mod, "DEFAULT_STAGE1_SHARED_LEDGER_ROOT", tmp_path / "shared_cb")
    out_cb = tmp_path / "out_cb"
    cb_ledger_path = live_mod.resolve_stage1_shared_budget_ledger_path()
    sim_cb = _SimulatedProviderServer(ledger_path=cb_ledger_path, output_dir=out_cb)
    sim_cb.fail_all_oai_items = True
    with pytest.raises(RuntimeError, match="BATCH_ABORT_EXCESSIVE_RETRY_RATE"):
        run_stage1_dev5_live_batch(
            activation_pack_dir=env["pack_dir"],
            external_trust_root_dir=env["trust_root_dir"],
            dev5_root=env["dev5_root"],
            corpus_docs=docs,
            queries_json_path=q_path,
            rate_evidence_path=env["rate_evidence_path"],
            output_dir=out_cb,
            slice_mode="canary_1x10",
            providers=("openai",),
            allow_live_network=True,
            vault_path=env["vault_path"],
            url_opener=sim_cb.opener,
            out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
            out_of_band_manifest_sha256=env["oob_manifest_sha"],
            out_of_band_auditor_report_sha256=env["oob_report_sha"],
            expected_target_zip_sha256=env["target_zip_sha"],
            raw_probe_transcript_path=env["raw_probe_path"],
        )
    assert sim_cb.oai_batch_seq == 1  # ZERO retry batch submitted!
    assert len(sim_cb.deleted_files) == 2  # Cleanup STILL executed!
    cb_ledger = load_or_init_aggregate_stage1_ledger(cb_ledger_path)
    assert cb_ledger["total_confirmed_spent_usd"] > 0.0 and cb_ledger["total_unresolved_reserve_usd"] == 0.0

    # 2. Snapshot drift aborts cleanly after cleanup.
    monkeypatch.setattr(live_mod, "DEFAULT_STAGE1_SHARED_LEDGER_ROOT", tmp_path / "shared_snap")
    out_snap = tmp_path / "out_snap"
    sim_snap = _SimulatedProviderServer(ledger_path=live_mod.resolve_stage1_shared_budget_ledger_path(), output_dir=out_snap)
    sim_snap.inject_snapshot_drift = "gpt-6-luna-unexpected-2026-12"
    with pytest.raises(RuntimeError, match="MODEL_SNAPSHOT_DRIFT_ABORT"):
        run_stage1_dev5_live_batch(
            activation_pack_dir=env["pack_dir"],
            external_trust_root_dir=env["trust_root_dir"],
            dev5_root=env["dev5_root"],
            corpus_docs=docs,
            queries_json_path=q_path,
            rate_evidence_path=env["rate_evidence_path"],
            output_dir=out_snap,
            slice_mode="canary_1x10",
            providers=("openai",),
            allow_live_network=True,
            vault_path=env["vault_path"],
            url_opener=sim_snap.opener,
            out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
            out_of_band_manifest_sha256=env["oob_manifest_sha"],
            out_of_band_auditor_report_sha256=env["oob_report_sha"],
            expected_target_zip_sha256=env["target_zip_sha"],
            raw_probe_transcript_path=env["raw_probe_path"],
        )
    assert len(sim_snap.deleted_files) == 2

    # 3. Anthropic >=100K long-context cliff aborts cleanly after remote batch delete.
    monkeypatch.setattr(live_mod, "DEFAULT_STAGE1_SHARED_LEDGER_ROOT", tmp_path / "shared_cliff")
    out_cliff = tmp_path / "out_cliff"
    sim_cliff = _SimulatedProviderServer(ledger_path=live_mod.resolve_stage1_shared_budget_ledger_path(), output_dir=out_cliff)
    sim_cliff.inject_cliff_tokens = 100_500
    with pytest.raises(PermissionError, match="LONG_CONTEXT_CLIFF_ABORT"):
        run_stage1_dev5_live_batch(
            activation_pack_dir=env["pack_dir"],
            external_trust_root_dir=env["trust_root_dir"],
            dev5_root=env["dev5_root"],
            corpus_docs=docs,
            queries_json_path=q_path,
            rate_evidence_path=env["rate_evidence_path"],
            output_dir=out_cliff,
            slice_mode="canary_1x10",
            providers=("anthropic",),
            allow_live_network=True,
            vault_path=env["vault_path"],
            url_opener=sim_cliff.opener,
            out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
            out_of_band_manifest_sha256=env["oob_manifest_sha"],
            out_of_band_auditor_report_sha256=env["oob_report_sha"],
            expected_target_zip_sha256=env["target_zip_sha"],
            raw_probe_transcript_path=env["raw_probe_path"],
        )
    assert len(sim_cliff.deleted_ant_batches) == 1

    # 4. Secret redaction masks API token on transport failures.
    secret_val = "SYNTH_OPENAI_UNIT_TEST_SECRET_99887766"

    def _leak_opener(req: urllib.request.Request, timeout: float) -> tuple[int, dict[str, str], bytes]:
        del req, timeout
        raise ConnectionError(f"Socket failed with Bearer {secret_val}")

    tr_bad = OpenAIBatchLiveTransport(secret_resolver=lambda _p: secret_val, url_opener=_leak_opener)
    with pytest.raises(live_mod.LiveTransportError) as exc_info:
        tr_bad.lookup_batch_by_idempotency_key("abc")
    assert secret_val not in str(exc_info.value)
    assert "[REDACTED_API_KEY]" in str(exc_info.value)


def _run_canary(
    *,
    env: dict[str, Any],
    docs: list[dict[str, Any]],
    q_path: Path,
    out_dir: Path,
    providers: tuple[str, ...] = ("openai", "anthropic"),
    slice_mode: str = "canary_1x10",
    canary_doc_ids: list[str] | None = None,
    resume_only: bool = False,
    poll_interval_seconds: float = 0.01,
    max_wait_seconds: float = 5.0,
    url_opener: Any = None,
    transports_by_provider: dict[str, Any] | None = None,
    shared_budget_ledger_path: Path | None = None,
) -> dict[str, Any]:
    return run_stage1_dev5_live_batch(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=out_dir,
        shared_budget_ledger_path=shared_budget_ledger_path,
        slice_mode=slice_mode,
        providers=providers,
        canary_1x10_doc_ids=canary_doc_ids if canary_doc_ids is not None else [d["document_id"] for d in docs[:10]],
        allow_live_network=True,
        resume_only=resume_only,
        poll_interval_seconds=poll_interval_seconds,
        max_wait_seconds=max_wait_seconds,
        sleep_fn=lambda _s: None,
        vault_path=env["vault_path"],
        url_opener=url_opener,
        transports_by_provider=transports_by_provider,
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )


def test_finding1_anthropic_never_matches_unrelated_same_count_batch_and_recovers_by_dispatch_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit Finding 1: never bind IN_PROGRESS/ENDED unrelated same-count batch on same Anthropic account."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    shared_ledger = tmp_path / "f1_shared" / "shared_budget_ledger.json"
    out_f1 = tmp_path / "out_f1"
    out_f1.mkdir(parents=True, exist_ok=True)

    # Seed crashed intent deterministically matching out_f1's manifest items + dispatch_tag.
    _sys_p, _s4, prompt_pins = live_mod._load_and_verify_prompt_and_schema(env["dev5_root"])
    qs = load_approved_dev5_queries(q_path)
    manifest = live_mod._load_or_init_run_manifest(
        manifest_path=out_f1 / "dev5_run_manifest.json",
        slice_mode="canary_1x10",
        queries=qs,
        prompt_pins=prompt_pins,
    )
    items = build_approved_dev5_canary_items(
        dev5_queries=qs,
        corpus_docs=docs,
        slice_mode="canary_1x10",
        packet_salt=str(manifest["packet_salt"]),
        run_nonce_seed=str(manifest["run_nonce_seed"]),
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
    )
    canon_cids = [it["custom_id"] for it in items]
    rp_ant = ProviderRateProfile("anthropic", "claude-haiku-5-5", "claude-haiku-5-5", 0.05, 0.25)
    intent = prepare_stage1_pre_submit_intent(
        ledger_path=shared_ledger,
        run_id="f1-crash-run",
        rate_profile=rp_ant,
        custom_ids=canon_cids,
        batch_reserved_worst_case_usd=0.02,
    )
    idemp_key = str(intent["client_idempotency_key"])
    dispatch_tag = idemp_key[:6]
    live_mod.record_stage1_dispatch_progress(
        ledger_path=shared_ledger,
        client_idempotency_key=idemp_key,
        dispatch_stage="BATCH_POST_IN_FLIGHT",
        source_output_dir=out_f1,
        wire_dispatch_tag=dispatch_tag,
    )

    sim = _SimulatedProviderServer(ledger_path=shared_ledger, output_dir=out_f1, ant_mode="always_in_progress")
    same_ts = live_mod._utc_now_iso()
    # Put two UNRELATED batches (same 10 items, same created_at) into the same Anthropic account!
    sim.add_unrelated_anthropic_fixture(
        batch_id="unrelated_fixture_in_progress",
        item_count=10,
        processing_status="in_progress",
        created_at=same_ts,
        dispatch_tag="bad001",
    )
    sim.add_unrelated_anthropic_fixture(
        batch_id="unrelated_fixture_ended",
        item_count=10,
        processing_status="ended",
        created_at=same_ts,
        dispatch_tag="bad002",
    )
    # Also seed our OWN real batch while it is still IN_PROGRESS (cannot be guessed before ENDED + custom_ids!).
    own_reqs = [
        {
            "custom_id": to_wire_custom_id(it["packet_item_uuid"], it["prompt_order"], dispatch_tag=dispatch_tag),
            "params": {
                "messages": [{"role": "user", "content": "<UNTRUSTED_CORPUS_DOCUMENT_0>\nDummy\n</UNTRUSTED_CORPUS_DOCUMENT_0>"}]
            },
        }
        for it in items
    ]
    real_bid = "msgbatch_real_own_1"
    real_res_url = f"https://api.anthropic.com/v1/messages/batches/{real_bid}/results"
    sim.ant_results_bytes[real_bid] = sim._build_ant_results_jsonl(own_reqs)
    sim.ant_batches[real_bid] = {
        "id": real_bid,
        "type": "message_batch",
        "created_at": same_ts,
        "processing_status": "in_progress",
        "results_url": None,
        "request_counts": {"processing": 10, "succeeded": 0, "errored": 0, "canceled": 0, "expired": 0},
        "_ready_url": real_res_url,
        "_polls": 0,
    }

    # Step 1: Must hold reserve FAIL-CLOSED as UNRESOLVED_CRASH_RESERVED without binding unrelated fixtures!
    res_wait = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_f1,
        providers=("anthropic",),
        resume_only=True,
        max_wait_seconds=0.0,
        poll_interval_seconds=0.0,
        url_opener=sim.opener,
        shared_budget_ledger_path=shared_ledger,
    )
    assert res_wait["overall_status"] == "AWAITING_BATCH_COMPLETION"
    assert res_wait["total_unresolved_reserve_usd"] == pytest.approx(0.02, abs=1e-6)
    led_now = json.loads(shared_ledger.read_text(encoding="utf-8"))
    assert led_now["intents"][idemp_key]["status"] == "UNRESOLVED_CRASH_RESERVED"
    assert led_now["intents"][idemp_key].get("batch_id") is None
    assert sim.deleted_ant_batches == []

    # Step 2: Once our real batch reaches ENDED + results_url, exact wire_custom_id set matches ONLY msgbatch_real_own_1!
    sim.ant_mode = "ended"
    sim.ant_batches[real_bid]["processing_status"] = "ended"
    sim.ant_batches[real_bid]["results_url"] = real_res_url
    sim.ant_batches[real_bid]["request_counts"] = {
        "processing": 0, "succeeded": 10, "errored": 0, "canceled": 0, "expired": 0
    }
    res_done = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_f1,
        providers=("anthropic",),
        resume_only=True,
        max_wait_seconds=0.0,
        poll_interval_seconds=0.0,
        url_opener=sim.opener,
        shared_budget_ledger_path=shared_ledger,
    )
    assert res_done["overall_status"] == "COMPLETED"
    assert res_done["providers"]["anthropic"]["settled_items"] == 10
    assert res_done["total_unresolved_reserve_usd"] == 0.0
    assert sim.deleted_ant_batches == [real_bid]
    led_final = json.loads(shared_ledger.read_text(encoding="utf-8"))
    assert led_final["intents"][idemp_key]["batch_id"] == real_bid


def test_finding2_crash_after_raw_backup_zero_and_partial_jsonl_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit Finding 2: crash right after raw backup JSON (0 lines OR 5/10 lines) replays missing JSONL items."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    real_append = live_mod._append_jsonl_durable

    class _SimulatedLogCrash(RuntimeError):
        pass

    # Subcase A: Crash BEFORE writing line 1 (backup_path exists, 0 JSONL lines, no .jsonl_complete.json).
    out_zero = tmp_path / "out_f2_zero"
    led_zero = tmp_path / "f2_zero_shared" / "shared.json"
    sim_zero = _SimulatedProviderServer(ledger_path=led_zero, output_dir=out_zero)

    def _crash_first_line(path: Path, rec: dict[str, Any]) -> None:
        del path, rec
        raise _SimulatedLogCrash("POWER_LOSS_BEFORE_FIRST_JSONL_LINE")

    monkeypatch.setattr(live_mod, "_append_jsonl_durable", _crash_first_line)
    with pytest.raises(_SimulatedLogCrash, match="POWER_LOSS_BEFORE_FIRST_JSONL_LINE"):
        _run_canary(
            env=env, docs=docs, q_path=q_path, out_dir=out_zero,
            providers=("openai",), url_opener=sim_zero.opener, shared_budget_ledger_path=led_zero,
        )
    assert (out_zero / "raw_batch_outcomes" / "openai_batch_oai_1.json").is_file()
    assert not (out_zero / "raw_batch_outcomes" / "openai_batch_oai_1.jsonl_complete.json").is_file()
    assert not (out_zero / "openai_raw_log.jsonl").is_file()

    # Resume replays ALL 10 missing items with ZERO extra batch submissions!
    monkeypatch.setattr(live_mod, "_append_jsonl_durable", real_append)
    res_zero = _run_canary(
        env=env, docs=docs, q_path=q_path, out_dir=out_zero,
        providers=("openai",), url_opener=sim_zero.opener, shared_budget_ledger_path=led_zero,
    )
    assert res_zero["overall_status"] == "COMPLETED"
    assert sim_zero.oai_batch_seq == 1
    assert res_zero["providers"]["openai"]["settled_items"] == 10
    assert (out_zero / "raw_batch_outcomes" / "openai_batch_oai_1.jsonl_complete.json").is_file()
    zero_lines = [json.loads(ln) for ln in (out_zero / "openai_raw_log.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(zero_lines) == 10
    assert len({r["custom_id"] for r in zero_lines}) == 10

    # Subcase B: Crash AFTER writing 5 of 10 JSONL lines -> supplements ONLY 5 missing items cleanly!
    out_part = tmp_path / "out_f2_partial"
    led_part = tmp_path / "f2_part_shared" / "shared.json"
    sim_part = _SimulatedProviderServer(ledger_path=led_part, output_dir=out_part)
    append_count = {"n": 0}

    def _crash_after_five(path: Path, rec: dict[str, Any]) -> None:
        if append_count["n"] >= 5:
            raise _SimulatedLogCrash("POWER_LOSS_AFTER_5_JSONL_LINES")
        real_append(path, rec)
        append_count["n"] += 1

    monkeypatch.setattr(live_mod, "_append_jsonl_durable", _crash_after_five)
    with pytest.raises(_SimulatedLogCrash, match="POWER_LOSS_AFTER_5_JSONL_LINES"):
        _run_canary(
            env=env, docs=docs, q_path=q_path, out_dir=out_part,
            providers=("openai",), url_opener=sim_part.opener, shared_budget_ledger_path=led_part,
        )
    assert len((out_part / "openai_raw_log.jsonl").read_text(encoding="utf-8").splitlines()) == 5
    assert not (out_part / "raw_batch_outcomes" / "openai_batch_oai_1.jsonl_complete.json").is_file()

    monkeypatch.setattr(live_mod, "_append_jsonl_durable", real_append)
    res_part = _run_canary(
        env=env, docs=docs, q_path=q_path, out_dir=out_part,
        providers=("openai",), url_opener=sim_part.opener, shared_budget_ledger_path=led_part,
    )
    assert res_part["overall_status"] == "COMPLETED"
    assert sim_part.oai_batch_seq == 1
    part_lines = [json.loads(ln) for ln in (out_part / "openai_raw_log.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(part_lines) == 10
    assert len({r["custom_id"] for r in part_lines}) == 10
    assert (out_part / "raw_batch_outcomes" / "openai_batch_oai_1.jsonl_complete.json").is_file()

    # Subcase C: Once .jsonl_complete.json + all 10 items exist, replay is strictly idempotent (zero appends!).
    monkeypatch.setattr(live_mod, "_append_jsonl_durable", _crash_first_line)
    res_idemp = _run_canary(
        env=env, docs=docs, q_path=q_path, out_dir=out_part,
        providers=("openai",), url_opener=sim_part.opener, shared_budget_ledger_path=led_part,
    )
    assert res_idemp["overall_status"] == "COMPLETED"
    assert sim_part.oai_batch_seq == 1

    # Subcase D: Partial crash (5/10) across a batch with >15% schema errors still trips circuit breaker on resume!
    monkeypatch.setattr(live_mod, "_append_jsonl_durable", real_append)
    out_cb_part = tmp_path / "out_f2_cb_partial"
    led_cb_part = tmp_path / "f2_cb_shared" / "shared.json"
    sim_cb_part = _SimulatedProviderServer(ledger_path=led_cb_part, output_dir=out_cb_part)
    sim_cb_part.fail_all_oai_items = True
    append_count["n"] = 0
    monkeypatch.setattr(live_mod, "_append_jsonl_durable", _crash_after_five)
    with pytest.raises(_SimulatedLogCrash):
        _run_canary(
            env=env, docs=docs, q_path=q_path, out_dir=out_cb_part,
            providers=("openai",), url_opener=sim_cb_part.opener, shared_budget_ledger_path=led_cb_part,
        )
    monkeypatch.setattr(live_mod, "_append_jsonl_durable", real_append)
    with pytest.raises(RuntimeError, match="BATCH_ABORT_EXCESSIVE_RETRY_RATE"):
        _run_canary(
            env=env, docs=docs, q_path=q_path, out_dir=out_cb_part,
            providers=("openai",), url_opener=sim_cb_part.opener, shared_budget_ledger_path=led_cb_part,
        )
    assert sim_cb_part.oai_batch_seq == 1
    assert (out_cb_part / "raw_batch_outcomes" / "openai_batch_oai_1.jsonl_complete.json").is_file()


def test_finding3_shared_2usd_cap_across_output_dirs_and_concurrent_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit Finding 3: single shared $2.00 cap enforced across distinct --output-dir & concurrent threads/PIDs."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)

    # Calibrate unit rates so a single OpenAI canary_1x10 batch reserves ~$1.20 (<= $2.00, 2x = ~$2.40 > $2.00).
    env = _setup_phase2_pack_and_dev5_configs(tmp_path / "f3_env", rate_input=16.0, rate_output=22.0)
    shared_root = tmp_path / "canonical_shared_root"
    monkeypatch.setattr(live_mod, "DEFAULT_STAGE1_SHARED_LEDGER_ROOT", shared_root)
    shared_ledger = live_mod.resolve_stage1_shared_budget_ledger_path()

    # Subcase A: Two DIFFERENT --output-dir paths share the exact same $2.00 ledger!
    dir_a = tmp_path / "run_dir_a"
    dir_b = tmp_path / "run_dir_b"
    sim_a = _SimulatedProviderServer(ledger_path=shared_ledger, output_dir=dir_a)
    sim_a.inject_cliff_tokens = 7500  # 10*7500=75k in_tok (~$1.2011 billed on dir_a, <= $2.00, leaving < $0.80 headroom!)
    res_a = _run_canary(
        env=env, docs=docs, q_path=q_path, out_dir=dir_a, providers=("openai",), url_opener=sim_a.opener,
    )
    assert res_a["overall_status"] == "COMPLETED"
    assert res_a["shared_budget_ledger_path"] == str(shared_ledger)
    assert shared_ledger.is_file()

    # Dry-run inspect from a DIFFERENT --output-dir sees dir_a's committed spend and warns fits_combined_dev_cap=False.
    rep_b = inspect_stage1_dev5_live_readiness(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=dir_b,
        slice_mode="canary_1x10",
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
        vault_path=env["vault_path"],
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )
    assert rep_b["existing_ledger_summary"]["total_confirmed_spent_usd"] == pytest.approx(
        res_a["total_confirmed_spent_usd"], abs=1e-6
    )
    assert rep_b["fits_combined_dev_cap"] is False

    # Executing in dir_b MUST fail closed before making ANY HTTP call!
    sim_b = _SimulatedProviderServer(ledger_path=shared_ledger, output_dir=dir_b)
    with pytest.raises(PermissionError, match="STAGE1_COMBINED_TWO_PROVIDER_DEV_CAP_EXCEEDED"):
        _run_canary(
            env=env, docs=docs, q_path=q_path, out_dir=dir_b, providers=("openai",), url_opener=sim_b.opener,
        )
    assert len(sim_b.calls) == 0

    # Subcase B: Two simultaneous threads (Barrier(2)) racing on different --output-dirs!
    thread_shared_root = tmp_path / "thread_shared_root"
    monkeypatch.setattr(live_mod, "DEFAULT_STAGE1_SHARED_LEDGER_ROOT", thread_shared_root)
    thread_ledger = live_mod.resolve_stage1_shared_budget_ledger_path()
    t_dir_1 = tmp_path / "thread_out_1"
    t_dir_2 = tmp_path / "thread_out_2"

    sim_thr = _SimulatedProviderServer(ledger_path=thread_ledger, output_dir=t_dir_1, oai_mode="poll_then_completed")
    sim_thr.require_complete_marker_before_delete = False
    sim_thr.inject_cliff_tokens = 7500  # Confirmed spend ~$1.20 even if thread 1 finishes before thread 2 wakes.
    barrier = threading.Barrier(2)
    results: list[tuple[str, Any]] = []
    res_lock = threading.Lock()

    def _worker(tag: str, out_p: Path) -> None:
        barrier.wait(timeout=5.0)
        try:
            r = run_stage1_dev5_live_batch(
                activation_pack_dir=env["pack_dir"],
                external_trust_root_dir=env["trust_root_dir"],
                dev5_root=env["dev5_root"],
                corpus_docs=docs,
                queries_json_path=q_path,
                rate_evidence_path=env["rate_evidence_path"],
                output_dir=out_p,
                shared_budget_ledger_path=thread_ledger,
                slice_mode="canary_1x10",
                providers=("openai",),
                canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
                allow_live_network=True,
                poll_interval_seconds=0.02,
                max_wait_seconds=5.0,
                vault_path=env["vault_path"],
                url_opener=sim_thr.opener,
                out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
                out_of_band_manifest_sha256=env["oob_manifest_sha"],
                out_of_band_auditor_report_sha256=env["oob_report_sha"],
                expected_target_zip_sha256=env["target_zip_sha"],
                raw_probe_transcript_path=env["raw_probe_path"],
            )
            with res_lock:
                results.append(("ok", r))
        except Exception as exc:  # noqa: BLE001
            with res_lock:
                results.append(("err", f"{type(exc).__name__}:{exc}"))

    t1 = threading.Thread(target=_worker, args=("t1", t_dir_1))
    t2 = threading.Thread(target=_worker, args=("t2", t_dir_2))
    t1.start()
    t2.start()
    t1.join(timeout=15.0)
    t2.join(timeout=15.0)
    assert len(results) == 2
    ok_res = [x[1] for x in results if x[0] == "ok"]
    err_res = [x[1] for x in results if x[0] == "err"]
    assert len(ok_res) == 1
    assert len(err_res) == 1
    assert "STAGE1_COMBINED_TWO_PROVIDER_DEV_CAP_EXCEEDED" in err_res[0]
    assert sim_thr.oai_batch_seq == 1

    # Subcase C: Real two-process (distinct OS PIDs) concurrency test on shared OS file lock!
    proc_dir = tmp_path / "proc_race"
    proc_dir.mkdir(parents=True, exist_ok=True)
    proc_ledger = proc_dir / "shared_proc_ledger.json"
    (proc_dir / "corpus.json").write_text(json.dumps({"docs": docs, "v_sha": v_sha}), encoding="utf-8")
    worker_py = proc_dir / "proc_worker.py"
    worker_py.write_text(
        """
import json, sys, time
from pathlib import Path
PREP = Path(sys.argv[1])
sys.path.insert(0, str(PREP / "src"))
import w07_g4_scorer.route2_dev5_live_runner as m
cfg = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
corpus_bundle = json.loads(Path(cfg["corpus_path"]).read_text(encoding="utf-8"))
m.EXPECTED_V_CORPUS_SHA256 = corpus_bundle["v_sha"]

class _FakeOai:
    can_submit_billable_batches = True
    def __init__(self, state_path: Path, cid_idx: str):
        self.state_path = state_path
        self.cid_idx = cid_idx
        self.polls = 0
    def submit_batch(self, *, run_id, client_idempotency_key, wire_items, expected_snapshot_id=None, **kw):
        if "on_before_file_upload" in kw and kw["on_before_file_upload"]:
            kw["on_before_file_upload"](m.openai_upload_filename_for_intent(client_idempotency_key), "0" * 64)
        if "on_input_file_uploaded" in kw and kw["on_input_file_uploaded"]:
            kw["on_input_file_uploaded"](f"file-in-{self.cid_idx}")
        if "on_before_batch_create" in kw and kw["on_before_batch_create"]:
            kw["on_before_batch_create"]()
        count_file = self.state_path / "submits.log"
        with open(count_file, "a", encoding="utf-8") as fh:
            fh.write(f"{self.cid_idx}:{client_idempotency_key}\\n")
        (self.state_path / f"items_{self.cid_idx}.json").write_text(
            json.dumps([it["custom_id"] for it in wire_items]), encoding="utf-8"
        )
        return {"provider": "openai", "batch_id": f"batch_{self.cid_idx}", "input_file_id": f"file-in-{self.cid_idx}", "batch_status": "VALIDATING"}
    def lookup_batch_by_idempotency_key(self, k):
        return {"found": False, "authoritative_non_acceptance": False}
    def fetch_batch_outcome(self, bid):
        self.polls += 1
        if self.polls == 1:
            return {"provider": "openai", "batch_id": bid, "batch_status": "IN_PROGRESS", "items": []}
        idx = bid.split("_", 1)[1]
        cids = json.loads((self.state_path / f"items_{idx}.json").read_text(encoding="utf-8"))
        return {
            "provider": "openai",
            "batch_id": bid,
            "batch_status": "COMPLETED",
            "items": [
                {
                    "custom_id": m.canonicalize_custom_id(wc),
                    "wire_custom_id": wc,
                    "model_snapshot_id": "gpt-6-luna",
                    "usage": {"input_tokens": 7500, "output_tokens": 40},
                    "parsed_response": {"grade": "REL_0", "evidence_quote": None, "char_start": None, "char_end": None},
                    "provider_error": None,
                }
                for wc in cids
            ],
        }
    def delete_batch(self, bid):
        return {"batch_id": bid, "deleted": True}
    def delete_file(self, fid):
        return {"file_id": fid, "deleted": True}

Path(cfg["ready_file"]).write_text("ready", encoding="utf-8")
go_p = Path(cfg["go_file"])
while not go_p.exists():
    time.sleep(0.01)

try:
    res = m.run_stage1_dev5_live_batch(
        activation_pack_dir=Path(cfg["pack_dir"]),
        external_trust_root_dir=Path(cfg["trust_root_dir"]),
        dev5_root=Path(cfg["dev5_root"]),
        corpus_docs=corpus_bundle["docs"],
        queries_json_path=Path(cfg["q_path"]),
        rate_evidence_path=Path(cfg["rate_evidence_path"]),
        output_dir=Path(cfg["out_dir"]),
        shared_budget_ledger_path=Path(cfg["shared_ledger"]),
        slice_mode="canary_1x10",
        providers=("openai",),
        canary_1x10_doc_ids=[d["document_id"] for d in corpus_bundle["docs"][:10]],
        allow_live_network=True,
        poll_interval_seconds=0.02,
        max_wait_seconds=5.0,
        transports_by_provider={"openai": _FakeOai(Path(cfg["state_dir"]), cfg["pid_tag"])},
        out_of_band_owner_pubkey_sha256=cfg["oob_owner_sha"],
        out_of_band_manifest_sha256=cfg["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=cfg["oob_report_sha"],
        expected_target_zip_sha256=cfg["target_zip_sha"],
        raw_probe_transcript_path=Path(cfg["raw_probe_path"]),
    )
    print("STATUS:" + res["overall_status"])
except Exception as exc:
    print(f"EXC:{type(exc).__name__}:{exc}", file=sys.stderr)
    sys.exit(2)
""".strip(),
        encoding="utf-8",
    )
    state_dir = proc_dir / "state"
    state_dir.mkdir()
    go_file = proc_dir / "go.flag"
    procs = []
    for idx in ("p1", "p2"):
        cfg_p = proc_dir / f"cfg_{idx}.json"
        cfg_p.write_text(
            json.dumps(
                {
                    "corpus_path": str(proc_dir / "corpus.json"),
                    "pack_dir": str(env["pack_dir"]),
                    "trust_root_dir": str(env["trust_root_dir"]),
                    "dev5_root": str(env["dev5_root"]),
                    "q_path": str(q_path),
                    "rate_evidence_path": str(env["rate_evidence_path"]),
                    "out_dir": str(proc_dir / f"out_{idx}"),
                    "shared_ledger": str(proc_ledger),
                    "state_dir": str(state_dir),
                    "pid_tag": idx,
                    "ready_file": str(proc_dir / f"ready_{idx}"),
                    "go_file": str(go_file),
                    "oob_owner_sha": env["oob_owner_sha"],
                    "oob_manifest_sha": env["oob_manifest_sha"],
                    "oob_report_sha": env["oob_report_sha"],
                    "target_zip_sha": env["target_zip_sha"],
                    "raw_probe_path": str(env["raw_probe_path"]),
                }
            ),
            encoding="utf-8",
        )
        procs.append(
            subprocess.Popen(
                [sys.executable, str(worker_py), str(PREP_DIR), str(cfg_p)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    # Wait until both child PIDs are poised right before run_stage1_dev5_live_batch, then release go_file.
    import time as _time

    deadline = _time.monotonic() + 10.0
    while not ((proc_dir / "ready_p1").exists() and (proc_dir / "ready_p2").exists()):
        assert _time.monotonic() < deadline
        _time.sleep(0.01)
    go_file.write_text("GO", encoding="utf-8")
    proc_outcomes = [(p.communicate(timeout=20.0), p.returncode) for p in procs]
    rcs = sorted(rc for _io, rc in proc_outcomes)
    assert rcs == [0, 2], f"Expected 1 winner (0) and 1 cap-blocked loser (2), got: {proc_outcomes}"
    sub_lines = (state_dir / "submits.log").read_text(encoding="utf-8").splitlines()
    assert len(sub_lines) == 1
    proc_led_data = json.loads(proc_ledger.read_text(encoding="utf-8"))
    assert float(proc_led_data["effective_committed_usd"]) <= 2.0


def test_finding4_openai_input_file_id_durable_before_batch_post_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit Finding 4: persist input_file_id durably BEFORE POST /v1/batches & clean orphan files on recovery."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)

    # Case A: Crash IMMEDIATELY after POST /v1/files, BEFORE POST /v1/batches runs.
    out_a = tmp_path / "out_f4_a"
    led_a = tmp_path / "f4_a_shared" / "shared.json"
    sim_a = _SimulatedProviderServer(ledger_path=led_a, output_dir=out_a)
    real_oai_a = OpenAIBatchLiveTransport(
        secret_resolver=lambda _p: "SYNTH_OPENAI_UNIT_TEST_SECRET_99887766",
        url_opener=sim_a.opener,
    )

    class _CrashPreBatchPostTransport:
        can_submit_billable_batches = True

        def __getattr__(self, name: str) -> Any:
            return getattr(real_oai_a, name)

        def submit_batch(
            self,
            *,
            on_input_file_uploaded: Any = None,
            on_before_batch_create: Any = None,
            on_batch_create_4xx: Any = None,
            **kwargs: Any,
        ) -> dict[str, Any]:
            def _crash_now() -> None:
                raise RuntimeError("SIMULATED_CRASH_AFTER_UPLOAD_BEFORE_BATCH_POST")

            del on_before_batch_create
            return real_oai_a.submit_batch(
                on_input_file_uploaded=on_input_file_uploaded,
                on_before_batch_create=_crash_now,
                on_batch_create_4xx=on_batch_create_4xx,
                **kwargs,
            )

    with pytest.raises(RuntimeError, match="SIMULATED_CRASH_AFTER_UPLOAD_BEFORE_BATCH_POST"):
        _run_canary(
            env=env,
            docs=docs,
            q_path=q_path,
            out_dir=out_a,
            providers=("openai",),
            transports_by_provider={"openai": _CrashPreBatchPostTransport()},
            shared_budget_ledger_path=led_a,
        )
    assert sim_a.oai_batch_seq == 0
    led_a_data = json.loads(led_a.read_text(encoding="utf-8"))
    k_a = next(iter(led_a_data["intents"]))
    assert led_a_data["intents"][k_a]["input_file_id"] == "file-oai-in-1"
    assert led_a_data["intents"][k_a]["dispatch_stage"] == "INPUT_FILE_UPLOADED_PRE_BATCH_POST"
    assert led_a_data["effective_committed_usd"] > 0.0

    # Recovery deletes the orphan input file and authoritatively releases reserve with zero batch created.
    res_a = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_a,
        providers=("openai",),
        resume_only=True,
        url_opener=sim_a.opener,
        shared_budget_ledger_path=led_a,
    )
    assert sim_a.oai_batch_seq == 0
    assert sim_a.deleted_files == ["file-oai-in-1"]
    assert res_a["total_unresolved_reserve_usd"] == 0.0
    led_a_after = json.loads(led_a.read_text(encoding="utf-8"))
    assert led_a_after["intents"][k_a]["status"] == "CANCELLED_UNSUBMITTED"

    # Case B: POST /v1/batches returns 400 AND initial DELETE fails 500 -> ledger saves stage & cleans on resume!
    out_b = tmp_path / "out_f4_b"
    led_b = tmp_path / "f4_b_shared" / "shared.json"
    sim_b = _SimulatedProviderServer(ledger_path=led_b, output_dir=out_b)
    sim_b.fail_oai_batch_post_4xx = True
    sim_b.fail_oai_delete_file_500 = True
    with pytest.raises(live_mod.LiveTransportError, match="HTTP_400"):
        _run_canary(
            env=env, docs=docs, q_path=q_path, out_dir=out_b,
            providers=("openai",), url_opener=sim_b.opener, shared_budget_ledger_path=led_b,
        )
    led_b_data = json.loads(led_b.read_text(encoding="utf-8"))
    k_b = next(iter(led_b_data["intents"]))
    assert led_b_data["intents"][k_b]["dispatch_stage"] == "BATCH_CREATE_4XX_REJECTED"
    assert led_b_data["intents"][k_b]["input_file_id"] == "file-oai-in-1"
    assert sim_b.deleted_files == []

    # Recovery retries DELETE and releases reserve cleanly once 200.
    sim_b.fail_oai_delete_file_500 = False
    res_b = _run_canary(
        env=env, docs=docs, q_path=q_path, out_dir=out_b,
        providers=("openai",), resume_only=True, url_opener=sim_b.opener, shared_budget_ledger_path=led_b,
    )
    assert sim_b.deleted_files == ["file-oai-in-1"]
    assert res_b["total_unresolved_reserve_usd"] == 0.0
    led_b_after = json.loads(led_b.read_text(encoding="utf-8"))
    assert led_b_after["intents"][k_b]["status"] == "CANCELLED_UNSUBMITTED"

    # Case C: Network timeout DURING POST /v1/batches (BATCH_POST_IN_FLIGHT) stays FAIL-CLOSED if lookup misses!
    out_c = tmp_path / "out_f4_c"
    led_c = tmp_path / "f4_c_shared" / "shared.json"
    sim_c = _SimulatedProviderServer(ledger_path=led_c, output_dir=out_c)
    sim_c.fail_oai_batch_post_timeout_no_accept = True
    with pytest.raises(live_mod.LiveTransportError, match="SIMULATED_TIMEOUT_BEFORE_SERVER_ACCEPTANCE"):
        _run_canary(
            env=env, docs=docs, q_path=q_path, out_dir=out_c,
            providers=("openai",), url_opener=sim_c.opener, shared_budget_ledger_path=led_c,
        )
    led_c_data = json.loads(led_c.read_text(encoding="utf-8"))
    k_c = next(iter(led_c_data["intents"]))
    assert led_c_data["intents"][k_c]["dispatch_stage"] == "BATCH_POST_IN_FLIGHT"
    res_c = _run_canary(
        env=env, docs=docs, q_path=q_path, out_dir=out_c,
        providers=("openai",), resume_only=True, url_opener=sim_c.opener, shared_budget_ledger_path=led_c,
    )
    assert res_c["total_unresolved_reserve_usd"] > 0.0
    assert sim_c.deleted_files == []


def test_fix02_1_resume_822_with_canary_1x10_stops_before_markers_or_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX02 (1): resuming an 822-item intent with canary_1x10 fails closed BEFORE .jsonl_complete, JSONL writes, or cleanup."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    out_dir = tmp_path / "out_fix02_1"
    shared_ledger = tmp_path / "fix02_1_shared" / "shared.json"

    # 1. Dispatch full 822-item batch (dev5_plus_20pct_swap) and leave AWAITING_BATCH_COMPLETION.
    sim = _SimulatedProviderServer(
        ledger_path=shared_ledger,
        output_dir=out_dir,
        oai_mode="always_in_progress",
        ant_mode="always_in_progress",
    )
    res_wait = run_stage1_dev5_live_batch(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=out_dir,
        shared_budget_ledger_path=shared_ledger,
        slice_mode="dev5_plus_20pct_swap",
        allow_live_network=True,
        max_wait_seconds=0.0,
        poll_interval_seconds=0.0,
        vault_path=env["vault_path"],
        url_opener=sim.opener,
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )
    assert res_wait["overall_status"] == "AWAITING_BATCH_COMPLETION"
    assert sim.oai_batch_seq == 1 and sim.ant_batch_seq == 1
    assert res_wait["dispatched_this_run"][0]["item_count"] == 822
    assert res_wait["dispatched_this_run"][1]["item_count"] == 822

    # 2. Both batches complete on providers, but operator mistakenly resumes with smaller canary_1x10!
    sim.oai_mode = "completed"
    sim.ant_mode = "ended"
    with pytest.raises(PermissionError, match="RESUME_SLICE_MISSING_CONTEXT_FOR_INTENT"):
        _run_canary(
            env=env,
            docs=docs,
            q_path=q_path,
            out_dir=out_dir,
            slice_mode="canary_1x10",
            resume_only=True,
            max_wait_seconds=0.0,
            poll_interval_seconds=0.0,
            url_opener=sim.opener,
            shared_budget_ledger_path=shared_ledger,
        )
    # Zero markers, zero JSONL rows, zero remote cleanups, reserve remains held!
    outcomes_dir = out_dir / "raw_batch_outcomes"
    assert not outcomes_dir.exists() or list(outcomes_dir.glob("*.jsonl_complete.json")) == []
    assert not (out_dir / "openai_raw_log.jsonl").exists()
    assert not (out_dir / "anthropic_raw_log.jsonl").exists()
    assert sim.deleted_files == []
    assert sim.deleted_ant_batches == []
    led_mid = json.loads(shared_ledger.read_text(encoding="utf-8"))
    assert led_mid["effective_committed_usd"] > 0.0

    # 3. Even if an incomplete 822-item backup JSON already exists on disk (no .jsonl_complete.json),
    # resuming with canary_1x10 STILL stops BEFORE marking complete, writing partial JSONL, or cleaning up!
    real_oai_outcome = live_mod.OpenAIBatchLiveTransport(
        secret_resolver=lambda _p: "SYNTH_OPENAI_UNIT_TEST_SECRET_99887766",
        url_opener=sim.opener,
    ).fetch_batch_outcome("batch_oai_1")
    assert len(real_oai_outcome["items"]) == 822
    outcomes_dir.mkdir(parents=True, exist_ok=True)
    (outcomes_dir / "openai_batch_oai_1.json").write_text(json.dumps(real_oai_outcome), encoding="utf-8")
    del_calls_before_b = len(sim.deleted_files) + len(sim.deleted_ant_batches)
    with pytest.raises(PermissionError, match="RESUME_SLICE_MISSING_CONTEXT_FOR_INTENT"):
        _run_canary(
            env=env,
            docs=docs,
            q_path=q_path,
            out_dir=out_dir,
            slice_mode="canary_1x10",
            resume_only=True,
            max_wait_seconds=0.0,
            poll_interval_seconds=0.0,
            url_opener=sim.opener,
            shared_budget_ledger_path=shared_ledger,
        )
    assert list(outcomes_dir.glob("*.jsonl_complete.json")) == []
    assert not (out_dir / "openai_raw_log.jsonl").exists()
    assert len(sim.deleted_files) + len(sim.deleted_ant_batches) == del_calls_before_b

    # 4. Now resume with matching dev5_plus_20pct_swap -> settles ALL 822 items, creates 822-count markers, & cleans up!
    res_ok = run_stage1_dev5_live_batch(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=out_dir,
        shared_budget_ledger_path=shared_ledger,
        slice_mode="dev5_plus_20pct_swap",
        allow_live_network=True,
        resume_only=True,
        vault_path=env["vault_path"],
        url_opener=sim.opener,
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )
    assert res_ok["overall_status"] == "COMPLETED"
    assert res_ok["providers"]["openai"]["settled_items"] == 822
    assert res_ok["providers"]["anthropic"]["settled_items"] == 822
    assert len((out_dir / "openai_raw_log.jsonl").read_text(encoding="utf-8").splitlines()) == 822
    assert len((out_dir / "anthropic_raw_log.jsonl").read_text(encoding="utf-8").splitlines()) == 822
    oai_marker = json.loads((outcomes_dir / "openai_batch_oai_1.jsonl_complete.json").read_text(encoding="utf-8"))
    ant_marker = json.loads((outcomes_dir / "anthropic_msgbatch_ant_1.jsonl_complete.json").read_text(encoding="utf-8"))
    assert oai_marker["verified_item_count"] == 822
    assert ant_marker["verified_item_count"] == 822
    assert len(sim.deleted_files) == 2
    assert sim.deleted_ant_batches == ["msgbatch_ant_1"]
    assert res_ok["total_unresolved_reserve_usd"] == 0.0


def test_fix02_2_upload_in_flight_lost_response_stays_unverified_until_provider_reconciled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX02 (2): durable UPLOAD_IN_FLIGHT + upload filename before POST /v1/files; unverified cleanup until reconciled."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)

    # Case A: OpenAI RECEIVES the uploaded file, then client loses connection BEFORE receiving/saving input_file_id!
    out_u = tmp_path / "out_fix02_2"
    shared_u = tmp_path / "fix02_2_shared" / "shared.json"
    sim = _SimulatedProviderServer(ledger_path=shared_u, output_dir=out_u)
    sim.fail_oai_upload_lost_response = True
    sim.fail_oai_list_files_500 = True

    with pytest.raises(live_mod.LiveTransportError, match="SIMULATED_LOST_RESPONSE_AFTER_UPLOAD_ACCEPTED"):
        _run_canary(
            env=env,
            docs=docs,
            q_path=q_path,
            out_dir=out_u,
            providers=("openai",),
            url_opener=sim.opener,
            shared_budget_ledger_path=shared_u,
        )

    # Server actually created the orphan file, while client NEVER saved input_file_id.
    assert len(sim.oai_file_records) == 1
    assert sim.oai_batch_seq == 0
    led_0 = json.loads(shared_u.read_text(encoding="utf-8"))
    k0 = next(iter(led_0["intents"]))
    ent_0 = led_0["intents"][k0]
    assert ent_0["dispatch_stage"] == "UPLOAD_IN_FLIGHT"
    assert ent_0["input_upload_filename"] == live_mod.openai_upload_filename_for_intent(k0)
    assert ent_0.get("input_file_id") is None
    assert len(ent_0.get("input_jsonl_sha256", "")) == 64
    assert ent_0["file_cleanup_status"] == "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE"
    assert led_0["effective_committed_usd"] > 0.0

    # Resume attempt 1: GET /v1/files is unreachable (500) -> cleanup STAYS unverified & reserve held!
    res_1 = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_u,
        providers=("openai",),
        resume_only=True,
        url_opener=sim.opener,
        shared_budget_ledger_path=shared_u,
    )
    assert res_1["overall_status"] == "AWAITING_BATCH_COMPLETION"
    assert res_1["total_unresolved_reserve_usd"] > 0.0
    assert sim.deleted_files == []
    led_1 = json.loads(shared_u.read_text(encoding="utf-8"))
    assert led_1["intents"][k0]["status"] == "UNRESOLVED_CRASH_RESERVED"
    assert led_1["intents"][k0]["file_cleanup_status"] == "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE"

    # Resume attempt 2: GET /v1/files discovers file-oai-in-1, but DELETE temporarily returns 500 -> STILL unverified!
    sim.fail_oai_list_files_500 = False
    sim.fail_oai_delete_file_500 = True
    res_2 = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_u,
        providers=("openai",),
        resume_only=True,
        url_opener=sim.opener,
        shared_budget_ledger_path=shared_u,
    )
    assert res_2["total_unresolved_reserve_usd"] > 0.0
    assert sim.deleted_files == []
    led_2 = json.loads(shared_u.read_text(encoding="utf-8"))
    assert led_2["intents"][k0]["input_file_id"] == "file-oai-in-1"
    assert led_2["intents"][k0]["file_cleanup_status"] == "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE"
    assert led_2["intents"][k0]["status"] == "UNRESOLVED_CRASH_RESERVED"

    # Resume attempt 3: DELETE succeeds -> orphan file cleaned, status CLEANED_ORPHAN_FILE_VERIFIED, reserve released!
    sim.fail_oai_delete_file_500 = False
    res_3 = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_u,
        providers=("openai",),
        resume_only=True,
        url_opener=sim.opener,
        shared_budget_ledger_path=shared_u,
    )
    assert sim.deleted_files == ["file-oai-in-1"]
    assert sim.oai_file_records == {}
    assert res_3["total_unresolved_reserve_usd"] == 0.0
    led_3 = json.loads(shared_u.read_text(encoding="utf-8"))
    assert led_3["intents"][k0]["status"] == "CANCELLED_UNSUBMITTED"
    assert led_3["intents"][k0]["file_cleanup_status"] == "CLEANED_ORPHAN_FILE_VERIFIED"
    assert "file-oai-in-1" in str(led_3["intents"][k0]["non_acceptance_evidence"])

    # Case B: UPLOAD_IN_FLIGHT crash where provider NEVER created the file -> verified absent on GET /v1/files!
    out_abs = tmp_path / "out_fix02_2_absent"
    shared_abs = tmp_path / "fix02_2_absent_shared" / "shared.json"
    out_abs.mkdir(parents=True, exist_ok=True)
    sim_abs = _SimulatedProviderServer(ledger_path=shared_abs, output_dir=out_abs)
    _sp_b, _s4_b, pins_b = live_mod._load_and_verify_prompt_and_schema(env["dev5_root"])
    qs_b = load_approved_dev5_queries(q_path)
    man_b = live_mod._load_or_init_run_manifest(
        manifest_path=out_abs / "dev5_run_manifest.json",
        slice_mode="canary_1x10",
        queries=qs_b,
        prompt_pins=pins_b,
    )
    abs_items = build_approved_dev5_canary_items(
        dev5_queries=qs_b,
        corpus_docs=docs,
        slice_mode="canary_1x10",
        packet_salt=str(man_b["packet_salt"]),
        run_nonce_seed=str(man_b["run_nonce_seed"]),
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
    )
    abs_intent = prepare_stage1_pre_submit_intent(
        ledger_path=shared_abs,
        run_id="upload-absent-run",
        rate_profile=ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 0.05, 0.25),
        custom_ids=[it["custom_id"] for it in abs_items],
        batch_reserved_worst_case_usd=0.05,
    )
    k_abs = str(abs_intent["client_idempotency_key"])
    live_mod.record_stage1_dispatch_progress(
        ledger_path=shared_abs,
        client_idempotency_key=k_abs,
        dispatch_stage="UPLOAD_IN_FLIGHT",
        input_upload_filename=live_mod.openai_upload_filename_for_intent(k_abs),
        input_jsonl_sha256="a" * 64,
        file_cleanup_status="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE",
        source_output_dir=out_abs,
        wire_dispatch_tag=k_abs[:6],
    )
    res_abs = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_abs,
        providers=("openai",),
        resume_only=True,
        url_opener=sim_abs.opener,
        shared_budget_ledger_path=shared_abs,
    )
    assert res_abs["total_unresolved_reserve_usd"] == 0.0
    led_abs = json.loads(shared_abs.read_text(encoding="utf-8"))
    assert led_abs["intents"][k_abs]["status"] == "CANCELLED_UNSUBMITTED"
    assert led_abs["intents"][k_abs]["file_cleanup_status"] == "VERIFIED_NO_REMOTE_FILE"
    assert sim_abs.deleted_files == []


def test_fix03_1_upload_in_flight_page6_and_cursor_anomalies_stay_unverified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX03 (1): page limit (file on page 6), missing cursor, and repeated cursor keep UNVERIFIED cleanup & reserve."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    _sp, _s4, pins = live_mod._load_and_verify_prompt_and_schema(env["dev5_root"])
    qs = load_approved_dev5_queries(q_path)

    def _seed_upload_in_flight_case(tag: str) -> tuple[Path, Path, str, str]:
        out_p = tmp_path / f"out_f3_{tag}"
        shared_p = tmp_path / f"shared_f3_{tag}" / "shared.json"
        out_p.mkdir(parents=True, exist_ok=True)
        man = live_mod._load_or_init_run_manifest(
            manifest_path=out_p / "dev5_run_manifest.json",
            slice_mode="canary_1x10",
            queries=qs,
            prompt_pins=pins,
        )
        c_items = build_approved_dev5_canary_items(
            dev5_queries=qs,
            corpus_docs=docs,
            slice_mode="canary_1x10",
            packet_salt=str(man["packet_salt"]),
            run_nonce_seed=str(man["run_nonce_seed"]),
            canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
        )
        intent = prepare_stage1_pre_submit_intent(
            ledger_path=shared_p,
            run_id=f"fix03-{tag}",
            rate_profile=ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 0.05, 0.25),
            custom_ids=[it["custom_id"] for it in c_items],
            batch_reserved_worst_case_usd=0.05,
        )
        k = str(intent["client_idempotency_key"])
        up_fn = live_mod.openai_upload_filename_for_intent(k)
        live_mod.record_stage1_dispatch_progress(
            ledger_path=shared_p,
            client_idempotency_key=k,
            dispatch_stage="UPLOAD_IN_FLIGHT",
            input_upload_filename=up_fn,
            input_jsonl_sha256="b" * 64,
            file_cleanup_status="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE",
            source_output_dir=out_p,
            wire_dispatch_tag=k[:6],
        )
        return out_p, shared_p, k, up_fn

    # Subcase A: File sits on PAGE 6 (10 unrelated files across pages 1..5 at 2/page, target on page 6).
    out_p6, shared_p6, k_p6, fn_p6 = _seed_upload_in_flight_case("page6")
    sim_p6 = _SimulatedProviderServer(ledger_path=shared_p6, output_dir=out_p6)
    sim_p6.oai_list_files_page_size = 2
    for idx in range(1, 11):
        sim_p6.oai_file_records[f"file-other-{idx:02d}"] = {
            "id": f"file-other-{idx:02d}",
            "object": "file",
            "purpose": "batch",
            "filename": f"unrelated_{idx}.jsonl",
            "created_at": 1795000000 + idx,
        }
    sim_p6.oai_file_records["file-oai-page6"] = {
        "id": "file-oai-page6",
        "object": "file",
        "purpose": "batch",
        "filename": fn_p6,
        "created_at": int(live_mod._parse_iso_unix(live_mod._utc_now_iso()) or 0),
    }

    # Direct transport lookup at default max_pages=5 reports exhaustive=False and stop_reason=PAGE_LIMIT_EXCEEDED!
    tr_default = OpenAIBatchLiveTransport(
        secret_resolver=lambda _p: "SYNTH_OPENAI_UNIT_TEST_SECRET_99887766",
        url_opener=sim_p6.opener,
    )
    scan_5 = tr_default.lookup_uploaded_files_by_filename(fn_p6)
    assert scan_5["exhaustive"] is False
    assert scan_5["pages_scanned"] == 5
    assert scan_5["stop_reason"] == "PAGE_LIMIT_EXCEEDED"
    assert scan_5["files"] == []

    # Resuming under default 5-page limit MUST keep UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE & full reserve!
    res_p6_blocked = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_p6,
        providers=("openai",),
        resume_only=True,
        url_opener=sim_p6.opener,
        shared_budget_ledger_path=shared_p6,
    )
    assert res_p6_blocked["total_unresolved_reserve_usd"] == pytest.approx(0.05, abs=1e-6)
    assert sim_p6.deleted_files == []
    assert "file-oai-page6" in sim_p6.oai_file_records
    led_p6_blocked = json.loads(shared_p6.read_text(encoding="utf-8"))
    ent_blocked = led_p6_blocked["intents"][k_p6]
    assert ent_blocked["status"] == "UNRESOLVED_CRASH_RESERVED"
    assert ent_blocked["file_cleanup_status"] == "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE"
    assert ent_blocked["file_reconcile_exhaustive"] is False
    assert ent_blocked["file_reconcile_stop_reason"] == "PAGE_LIMIT_EXCEEDED"

    # With list_files_max_pages=10 reaching page 6, reconciler discovers & deletes file-oai-page6 exhaustively!
    tr_wide = OpenAIBatchLiveTransport(
        secret_resolver=lambda _p: "SYNTH_OPENAI_UNIT_TEST_SECRET_99887766",
        url_opener=sim_p6.opener,
        list_files_max_pages=10,
    )
    res_p6_done = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_p6,
        providers=("openai",),
        resume_only=True,
        transports_by_provider={"openai": tr_wide},
        shared_budget_ledger_path=shared_p6,
    )
    assert sim_p6.deleted_files == ["file-oai-page6"]
    assert "file-oai-page6" not in sim_p6.oai_file_records
    assert res_p6_done["total_unresolved_reserve_usd"] == 0.0
    led_p6_done = json.loads(shared_p6.read_text(encoding="utf-8"))
    assert led_p6_done["intents"][k_p6]["status"] == "CANCELLED_UNSUBMITTED"
    assert led_p6_done["intents"][k_p6]["file_cleanup_status"] == "CLEANED_ORPHAN_FILE_VERIFIED"
    assert led_p6_done["intents"][k_p6]["file_reconcile_exhaustive"] is True

    # Subcase B: Missing pagination cursor while has_more=True keeps UNVERIFIED status & reserve!
    out_mc, shared_mc, k_mc, _fn_mc = _seed_upload_in_flight_case("missing_cur")
    sim_mc = _SimulatedProviderServer(ledger_path=shared_mc, output_dir=out_mc)
    sim_mc.inject_oai_list_files_missing_cursor = True
    res_mc = _run_canary(
        env=env, docs=docs, q_path=q_path, out_dir=out_mc,
        providers=("openai",), resume_only=True, url_opener=sim_mc.opener, shared_budget_ledger_path=shared_mc,
    )
    assert res_mc["total_unresolved_reserve_usd"] == pytest.approx(0.05, abs=1e-6)
    led_mc = json.loads(shared_mc.read_text(encoding="utf-8"))
    assert led_mc["intents"][k_mc]["status"] == "UNRESOLVED_CRASH_RESERVED"
    assert led_mc["intents"][k_mc]["file_cleanup_status"] == "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE"
    assert led_mc["intents"][k_mc]["file_reconcile_stop_reason"] == "MISSING_PAGINATION_CURSOR"

    # Subcase C: Repeated cursor loop while has_more=True terminates cleanly and keeps UNVERIFIED status & reserve!
    out_rc, shared_rc, k_rc, _fn_rc = _seed_upload_in_flight_case("repeat_cur")
    sim_rc = _SimulatedProviderServer(ledger_path=shared_rc, output_dir=out_rc)
    sim_rc.inject_oai_list_files_repeat_cursor = True
    res_rc = _run_canary(
        env=env, docs=docs, q_path=q_path, out_dir=out_rc,
        providers=("openai",), resume_only=True, url_opener=sim_rc.opener, shared_budget_ledger_path=shared_rc,
    )
    assert res_rc["total_unresolved_reserve_usd"] == pytest.approx(0.05, abs=1e-6)
    led_rc = json.loads(shared_rc.read_text(encoding="utf-8"))
    assert led_rc["intents"][k_rc]["status"] == "UNRESOLVED_CRASH_RESERVED"
    assert led_rc["intents"][k_rc]["file_cleanup_status"] == "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE"
    assert led_rc["intents"][k_rc]["file_reconcile_stop_reason"] == "REPEATED_PAGINATION_CURSOR"


def test_fix03_2_two_matching_files_first_delete_fails_then_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX03 (2): two matching files persist all pending IDs, survive 1st delete failure, and clean remaining on resume."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    _sp, _s4, pins = live_mod._load_and_verify_prompt_and_schema(env["dev5_root"])
    qs = load_approved_dev5_queries(q_path)

    out_dir = tmp_path / "out_fix03_two_files"
    shared_ledger = tmp_path / "shared_fix03_two_files" / "shared.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    man = live_mod._load_or_init_run_manifest(
        manifest_path=out_dir / "dev5_run_manifest.json",
        slice_mode="canary_1x10",
        queries=qs,
        prompt_pins=pins,
    )
    c_items = build_approved_dev5_canary_items(
        dev5_queries=qs,
        corpus_docs=docs,
        slice_mode="canary_1x10",
        packet_salt=str(man["packet_salt"]),
        run_nonce_seed=str(man["run_nonce_seed"]),
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
    )
    intent = prepare_stage1_pre_submit_intent(
        ledger_path=shared_ledger,
        run_id="fix03-two-files",
        rate_profile=ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 0.05, 0.25),
        custom_ids=[it["custom_id"] for it in c_items],
        batch_reserved_worst_case_usd=0.05,
    )
    k0 = str(intent["client_idempotency_key"])
    up_fn = live_mod.openai_upload_filename_for_intent(k0)
    live_mod.record_stage1_dispatch_progress(
        ledger_path=shared_ledger,
        client_idempotency_key=k0,
        dispatch_stage="UPLOAD_IN_FLIGHT",
        input_upload_filename=up_fn,
        input_jsonl_sha256="c" * 64,
        file_cleanup_status="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE",
        source_output_dir=out_dir,
        wire_dispatch_tag=k0[:6],
    )

    sim = _SimulatedProviderServer(ledger_path=shared_ledger, output_dir=out_dir)
    now_ts = int(live_mod._parse_iso_unix(live_mod._utc_now_iso()) or 0)
    # Seed TWO matching orphan files on OpenAI with identical upload_filename; fail deleting the 1st file!
    sim.oai_file_records["file-oai-dup-1"] = {
        "id": "file-oai-dup-1",
        "object": "file",
        "purpose": "batch",
        "filename": up_fn,
        "created_at": now_ts,
    }
    sim.oai_file_records["file-oai-dup-2"] = {
        "id": "file-oai-dup-2",
        "object": "file",
        "purpose": "batch",
        "filename": up_fn,
        "created_at": now_ts + 1,
    }
    sim.fail_oai_delete_file_ids.add("file-oai-dup-1")

    # Run 1: 1st file delete fails (500), 2nd file delete succeeds & updates cleaned_file_ids incrementally!
    res_1 = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_dir,
        providers=("openai",),
        resume_only=True,
        url_opener=sim.opener,
        shared_budget_ledger_path=shared_ledger,
    )
    assert res_1["total_unresolved_reserve_usd"] == pytest.approx(0.05, abs=1e-6)
    assert sim.deleted_files == ["file-oai-dup-2"]
    assert "file-oai-dup-1" in sim.oai_file_records
    led_1 = json.loads(shared_ledger.read_text(encoding="utf-8"))
    ent_1 = led_1["intents"][k0]
    assert ent_1["status"] == "UNRESOLVED_CRASH_RESERVED"
    assert ent_1["file_cleanup_status"] == "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE"
    assert ent_1["pending_cleanup_file_ids"] == ["file-oai-dup-1"]
    assert ent_1["cleaned_file_ids"] == ["file-oai-dup-2"]
    assert ent_1["file_reconcile_exhaustive"] is True

    # Run 2: Clear 1st file delete fault & resume -> deletes ONLY remaining file-oai-dup-1 and releases reserve!
    sim.fail_oai_delete_file_ids.clear()
    res_2 = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_dir,
        providers=("openai",),
        resume_only=True,
        url_opener=sim.opener,
        shared_budget_ledger_path=shared_ledger,
    )
    assert sim.deleted_files == ["file-oai-dup-2", "file-oai-dup-1"]
    assert sim.oai_file_records == {}
    assert res_2["total_unresolved_reserve_usd"] == 0.0
    led_2 = json.loads(shared_ledger.read_text(encoding="utf-8"))
    ent_2 = led_2["intents"][k0]
    assert ent_2["status"] == "CANCELLED_UNSUBMITTED"
    assert ent_2["file_cleanup_status"] == "CLEANED_ORPHAN_FILE_VERIFIED"
    assert ent_2["pending_cleanup_file_ids"] == []
    assert ent_2["cleaned_file_ids"] == ["file-oai-dup-2", "file-oai-dup-1"]
    assert ent_2["file_reconcile_exhaustive"] is True


def test_fix04_1_fixed_upload_timestamp_and_legacy_ledger_without_upload_started_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX04 (1): fixed upload_started_at_utc survives checkpoint drift; legacy ledgers without it match by filename."""
    from datetime import datetime, timezone

    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    _sp, _s4, pins = live_mod._load_and_verify_prompt_and_schema(env["dev5_root"])
    qs = load_approved_dev5_queries(q_path)

    # Subcase A: Upload lost-response crash pins upload_started_at_utc at T0 and NEVER drifts on later checkpoints.
    out_a = tmp_path / "out_fix04_a"
    shared_a = tmp_path / "shared_fix04_a" / "shared.json"
    sim_a = _SimulatedProviderServer(ledger_path=shared_a, output_dir=out_a)
    sim_a.fail_oai_upload_lost_response = True
    sim_a.fail_oai_list_files_500 = True

    with pytest.raises(live_mod.LiveTransportError, match="SIMULATED_LOST_RESPONSE_AFTER_UPLOAD_ACCEPTED"):
        _run_canary(
            env=env,
            docs=docs,
            q_path=q_path,
            out_dir=out_a,
            providers=("openai",),
            url_opener=sim_a.opener,
            shared_budget_ledger_path=shared_a,
        )

    led_a0 = json.loads(shared_a.read_text(encoding="utf-8"))
    k_a = next(iter(led_a0["intents"]))
    ent_a0 = led_a0["intents"][k_a]
    t0_iso = ent_a0["upload_started_at_utc"]
    assert isinstance(t0_iso, str) and t0_iso
    t0_unix = int(live_mod._parse_iso_unix(t0_iso) or 0)
    assert t0_unix > 0
    assert "file-oai-in-1" in sim_a.oai_file_records
    sim_a.oai_file_records["file-oai-in-1"]["created_at"] = t0_unix

    # Drift dispatch_stage_updated_at_utc forward by +7200s and call record_stage1_dispatch_progress again
    # (even passing a later upload_started_at_utc): original t0_iso must remain fixed.
    future_iso = datetime.fromtimestamp(t0_unix + 7200, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_mod.record_stage1_dispatch_progress(
        ledger_path=shared_a,
        client_idempotency_key=k_a,
        dispatch_stage="UPLOAD_IN_FLIGHT",
        source_output_dir=out_a,
        upload_started_at_utc=future_iso,
    )
    led_a_drift = json.loads(shared_a.read_text(encoding="utf-8"))
    assert led_a_drift["intents"][k_a]["upload_started_at_utc"] == t0_iso
    led_a_drift["intents"][k_a]["dispatch_stage_updated_at_utc"] = future_iso
    shared_a.write_text(json.dumps(led_a_drift, indent=2), encoding="utf-8")

    # Failed resume under 500 still preserves t0_iso and holds reserve.
    res_a1 = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_a,
        providers=("openai",),
        resume_only=True,
        url_opener=sim_a.opener,
        shared_budget_ledger_path=shared_a,
    )
    assert res_a1["total_unresolved_reserve_usd"] > 0.0
    assert json.loads(shared_a.read_text(encoding="utf-8"))["intents"][k_a]["upload_started_at_utc"] == t0_iso

    # Recovery: orphan file created at T0 (< dispatch_stage_updated_at_utc at T0+7200) IS discovered & cleaned!
    sim_a.fail_oai_list_files_500 = False
    res_a2 = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_a,
        providers=("openai",),
        resume_only=True,
        url_opener=sim_a.opener,
        shared_budget_ledger_path=shared_a,
    )
    assert sim_a.deleted_files == ["file-oai-in-1"]
    assert sim_a.oai_file_records == {}
    assert res_a2["total_unresolved_reserve_usd"] == 0.0
    led_a2 = json.loads(shared_a.read_text(encoding="utf-8"))
    assert led_a2["intents"][k_a]["upload_started_at_utc"] == t0_iso
    assert led_a2["intents"][k_a]["status"] == "CANCELLED_UNSUBMITTED"
    assert led_a2["intents"][k_a]["file_cleanup_status"] == "CLEANED_ORPHAN_FILE_VERIFIED"

    # Subcase B: Legacy ledger missing upload_started_at_utc entirely matches by upload filename without clock exclusion.
    out_b = tmp_path / "out_fix04_b"
    shared_b = tmp_path / "shared_fix04_b" / "shared.json"
    out_b.mkdir(parents=True, exist_ok=True)
    man_b = live_mod._load_or_init_run_manifest(
        manifest_path=out_b / "dev5_run_manifest.json",
        slice_mode="canary_1x10",
        queries=qs,
        prompt_pins=pins,
    )
    items_b = build_approved_dev5_canary_items(
        dev5_queries=qs,
        corpus_docs=docs,
        slice_mode="canary_1x10",
        packet_salt=str(man_b["packet_salt"]),
        run_nonce_seed=str(man_b["run_nonce_seed"]),
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
    )
    intent_b = prepare_stage1_pre_submit_intent(
        ledger_path=shared_b,
        run_id="fix04-legacy",
        rate_profile=ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 0.05, 0.25),
        custom_ids=[it["custom_id"] for it in items_b],
        batch_reserved_worst_case_usd=0.05,
    )
    k_b = str(intent_b["client_idempotency_key"])
    fn_b = live_mod.openai_upload_filename_for_intent(k_b)
    live_mod.record_stage1_dispatch_progress(
        ledger_path=shared_b,
        client_idempotency_key=k_b,
        dispatch_stage="UPLOAD_IN_FLIGHT",
        input_upload_filename=fn_b,
        input_jsonl_sha256="c" * 64,
        file_cleanup_status="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE",
        source_output_dir=out_b,
        wire_dispatch_tag=k_b[:6],
    )

    def _strip_upload_started_to_legacy(json_path: Path) -> None:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        changed = False
        if isinstance(raw, dict):
            if isinstance(raw.get("intents"), dict) and k_b in raw["intents"]:
                rec_b = raw["intents"][k_b]
                rec_b.pop("upload_started_at_utc", None)
                rec_b["dispatch_stage_updated_at_utc"] = "2030-01-01T00:00:00Z"
                changed = True
            if raw.get("client_idempotency_key") == k_b:
                raw.pop("upload_started_at_utc", None)
                raw["dispatch_stage_updated_at_utc"] = "2030-01-01T00:00:00Z"
                changed = True
        if changed:
            json_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    _strip_upload_started_to_legacy(shared_b)
    for jp in out_b.rglob("*.json"):
        _strip_upload_started_to_legacy(jp)

    sim_b = _SimulatedProviderServer(ledger_path=shared_b, output_dir=out_b)
    sim_b.oai_file_records["file-oai-legacy-1"] = {
        "id": "file-oai-legacy-1",
        "object": "file",
        "purpose": "batch",
        "filename": fn_b,
        "created_at": 1700000000,
    }
    sim_b.fail_oai_list_files_500 = True
    res_b1 = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_b,
        providers=("openai",),
        resume_only=True,
        url_opener=sim_b.opener,
        shared_budget_ledger_path=shared_b,
    )
    assert res_b1["total_unresolved_reserve_usd"] == pytest.approx(0.05, abs=1e-6)
    led_b1 = json.loads(shared_b.read_text(encoding="utf-8"))
    assert "upload_started_at_utc" not in led_b1["intents"][k_b]

    sim_b.fail_oai_list_files_500 = False
    res_b2 = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_b,
        providers=("openai",),
        resume_only=True,
        url_opener=sim_b.opener,
        shared_budget_ledger_path=shared_b,
    )
    assert sim_b.deleted_files == ["file-oai-legacy-1"]
    assert sim_b.oai_file_records == {}
    assert res_b2["total_unresolved_reserve_usd"] == 0.0
    led_b2 = json.loads(shared_b.read_text(encoding="utf-8"))
    assert led_b2["intents"][k_b]["status"] == "CANCELLED_UNSUBMITTED"
    assert led_b2["intents"][k_b]["file_cleanup_status"] == "CLEANED_ORPHAN_FILE_VERIFIED"
    assert led_b2["intents"][k_b]["file_reconcile_exhaustive"] is True


def test_fix04_2_list_files_missing_or_nonbool_has_more_keeps_unverified_and_reserve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX04 (2): END_OF_LIST requires data list and explicit bool has_more=False; missing or non-bool stays unverified."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    _sp, _s4, pins = live_mod._load_and_verify_prompt_and_schema(env["dev5_root"])
    qs = load_approved_dev5_queries(q_path)

    def _seed_has_more_case(tag: str) -> tuple[Path, Path, str, str]:
        out_p = tmp_path / f"out_f4_{tag}"
        shared_p = tmp_path / f"shared_f4_{tag}" / "shared.json"
        out_p.mkdir(parents=True, exist_ok=True)
        man = live_mod._load_or_init_run_manifest(
            manifest_path=out_p / "dev5_run_manifest.json",
            slice_mode="canary_1x10",
            queries=qs,
            prompt_pins=pins,
        )
        c_items = build_approved_dev5_canary_items(
            dev5_queries=qs,
            corpus_docs=docs,
            slice_mode="canary_1x10",
            packet_salt=str(man["packet_salt"]),
            run_nonce_seed=str(man["run_nonce_seed"]),
            canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
        )
        intent = prepare_stage1_pre_submit_intent(
            ledger_path=shared_p,
            run_id=f"fix04-{tag}",
            rate_profile=ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 0.05, 0.25),
            custom_ids=[it["custom_id"] for it in c_items],
            batch_reserved_worst_case_usd=0.05,
        )
        k = str(intent["client_idempotency_key"])
        up_fn = live_mod.openai_upload_filename_for_intent(k)
        live_mod.record_stage1_dispatch_progress(
            ledger_path=shared_p,
            client_idempotency_key=k,
            dispatch_stage="UPLOAD_IN_FLIGHT",
            input_upload_filename=up_fn,
            input_jsonl_sha256="d" * 64,
            file_cleanup_status="UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE",
            source_output_dir=out_p,
            wire_dispatch_tag=k[:6],
        )
        return out_p, shared_p, k, up_fn

    saved_states: dict[str, tuple[_SimulatedProviderServer, Path, Path, str, str]] = {}
    for mode, expected_reason in (
        ("omit", "MISSING_HAS_MORE_FLAG"),
        ("none", "MISSING_HAS_MORE_FLAG"),
        ("str_false", "INVALID_HAS_MORE_TYPE:str"),
        ("int_zero", "INVALID_HAS_MORE_TYPE:int"),
    ):
        out_m, shared_m, k_m, fn_m = _seed_has_more_case(mode)
        sim_m = _SimulatedProviderServer(ledger_path=shared_m, output_dir=out_m)
        sim_m.inject_oai_list_files_has_more_mode = mode
        if mode == "int_zero":
            sim_m.oai_file_records["file-oai-hm-match"] = {
                "id": "file-oai-hm-match",
                "object": "file",
                "purpose": "batch",
                "filename": fn_m,
                "created_at": int(live_mod._parse_iso_unix(live_mod._utc_now_iso()) or 0),
            }
        saved_states[mode] = (sim_m, out_m, shared_m, k_m, fn_m)

        tr = OpenAIBatchLiveTransport(
            secret_resolver=lambda _p: "SYNTH_OPENAI_UNIT_TEST_SECRET_99887766",
            url_opener=sim_m.opener,
        )
        scan = tr.lookup_uploaded_files_by_filename(fn_m)
        assert scan["exhaustive"] is False
        assert scan["stop_reason"] == expected_reason

        res_m = _run_canary(
            env=env,
            docs=docs,
            q_path=q_path,
            out_dir=out_m,
            providers=("openai",),
            resume_only=True,
            url_opener=sim_m.opener,
            shared_budget_ledger_path=shared_m,
        )
        assert res_m["total_unresolved_reserve_usd"] == pytest.approx(0.05, abs=1e-6)
        led_m = json.loads(shared_m.read_text(encoding="utf-8"))
        ent_m = led_m["intents"][k_m]
        assert ent_m["status"] == "UNRESOLVED_CRASH_RESERVED"
        assert ent_m["file_cleanup_status"] == "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE"
        assert ent_m["file_reconcile_exhaustive"] is False
        assert ent_m["file_reconcile_stop_reason"] == expected_reason

    # When explicit bool has_more=False returns with valid data list, END_OF_LIST releases reserve cleanly.
    sim_omit, out_omit, shared_omit, k_omit, fn_omit = saved_states["omit"]
    sim_omit.inject_oai_list_files_has_more_mode = None
    tr_omit = OpenAIBatchLiveTransport(
        secret_resolver=lambda _p: "SYNTH_OPENAI_UNIT_TEST_SECRET_99887766",
        url_opener=sim_omit.opener,
    )
    scan_ok = tr_omit.lookup_uploaded_files_by_filename(fn_omit)
    assert scan_ok["exhaustive"] is True
    assert scan_ok["stop_reason"] == "END_OF_LIST"
    res_omit_ok = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_omit,
        providers=("openai",),
        resume_only=True,
        url_opener=sim_omit.opener,
        shared_budget_ledger_path=shared_omit,
    )
    assert res_omit_ok["total_unresolved_reserve_usd"] == 0.0
    led_omit_ok = json.loads(shared_omit.read_text(encoding="utf-8"))
    assert led_omit_ok["intents"][k_omit]["status"] == "CANCELLED_UNSUBMITTED"
    assert led_omit_ok["intents"][k_omit]["file_cleanup_status"] == "VERIFIED_NO_REMOTE_FILE"
    assert led_omit_ok["intents"][k_omit]["file_reconcile_exhaustive"] is True
    assert led_omit_ok["intents"][k_omit]["file_reconcile_stop_reason"] == "END_OF_LIST"

    sim_iz, out_iz, shared_iz, k_iz, _fn_iz = saved_states["int_zero"]
    sim_iz.inject_oai_list_files_has_more_mode = None
    res_iz_ok = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_iz,
        providers=("openai",),
        resume_only=True,
        url_opener=sim_iz.opener,
        shared_budget_ledger_path=shared_iz,
    )
    assert res_iz_ok["total_unresolved_reserve_usd"] == 0.0
    assert "file-oai-hm-match" not in sim_iz.oai_file_records
    led_iz_ok = json.loads(shared_iz.read_text(encoding="utf-8"))
    assert led_iz_ok["intents"][k_iz]["status"] == "CANCELLED_UNSUBMITTED"
    assert led_iz_ok["intents"][k_iz]["file_cleanup_status"] == "CLEANED_ORPHAN_FILE_VERIFIED"
    assert led_iz_ok["intents"][k_iz]["file_reconcile_exhaustive"] is True
    assert led_iz_ok["intents"][k_iz]["file_reconcile_stop_reason"] == "END_OF_LIST"


def _make_mock_urlopen(sim: _SimulatedProviderServer, call_log: list[dict[str, Any]]) -> Any:
    """Wrap _SimulatedProviderServer.opener behind stdlib urllib.request.urlopen contract."""
    import email.message
    import io

    class _FakeUrlopenResponse:
        def __init__(self, status_code: int, hdrs: dict[str, str], body: bytes) -> None:
            self.status = int(status_code)
            self.headers = dict(hdrs)
            self._body = bytes(body)

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> "_FakeUrlopenResponse":
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

    def _mock_urlopen(
        req: urllib.request.Request,
        timeout: float | None = None,
        context: Any = None,
    ) -> _FakeUrlopenResponse:
        call_log.append(
            {
                "method": req.get_method(),
                "url": req.full_url,
                "timeout": timeout,
                "has_ssl_context": context is not None,
            }
        )
        assert timeout is not None and isinstance(timeout, (int, float))
        assert context is not None
        status_code, hdrs, body = sim.opener(req, float(timeout))
        if int(status_code) >= 400:
            msg = email.message.Message()
            for hk, hv in dict(hdrs).items():
                msg[str(hk)] = str(hv)
            raise urllib.error.HTTPError(
                req.full_url,
                int(status_code),
                "Mock HTTP Error",
                msg,
                io.BytesIO(bytes(body)),
            )
        return _FakeUrlopenResponse(int(status_code), dict(hdrs), bytes(body))

    return _mock_urlopen


def test_fix05_1_default_urlopen_openai_upload_reconcile_and_anthropic_preserve_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX05 (1): default url_opener=None adapts timeout by keyword to _default_urlopen; custom 2-arg opener works."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)

    # A. Custom timeout_seconds propagates via _default_urlopen(req, timeout=...) to urllib.request.urlopen
    #    for BOTH OpenAI and Anthropic without passing any url_opener.
    out_custom = tmp_path / "out_fix05_custom_timeout"
    shared_custom = tmp_path / "shared_fix05_custom_timeout" / "shared.json"
    sim_custom = _SimulatedProviderServer(ledger_path=shared_custom, output_dir=out_custom)
    urlopen_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(urllib.request, "urlopen", _make_mock_urlopen(sim_custom, urlopen_calls))

    tr_oai_custom = OpenAIBatchLiveTransport(
        secret_resolver=lambda _p: "SYNTH_OPENAI_UNIT_TEST_SECRET_99887766",
        url_opener=None,
        timeout_seconds=37.5,
    )
    tr_ant_custom = AnthropicBatchLiveTransport(
        secret_resolver=lambda _p: "SYNTH_ANTHROPIC_UNIT_TEST_SECRET_112233",
        url_opener=None,
        timeout_seconds=41.25,
    )

    res_custom = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_custom,
        providers=("openai", "anthropic"),
        transports_by_provider={"openai": tr_oai_custom, "anthropic": tr_ant_custom},
        shared_budget_ledger_path=shared_custom,
    )
    assert res_custom["overall_status"] == "COMPLETED"
    assert res_custom["providers"]["openai"]["settled_items"] == 10
    assert res_custom["providers"]["anthropic"]["settled_items"] == 10

    # Exercise reconcile list endpoints (GET /v1/batches, GET /v1/files?purpose=batch, GET /v1/messages/batches)
    # plus HTTPError handling (via _default_urlopen) directly with default opener.
    oai_batch_lookup = tr_oai_custom.lookup_batch_by_idempotency_key("nonexistent-idempotency-key")
    assert oai_batch_lookup["found"] is False
    oai_files_lookup = tr_oai_custom.lookup_uploaded_files_by_filename("missing_upload_file.jsonl")
    assert oai_files_lookup["exhaustive"] is True
    assert oai_files_lookup["stop_reason"] == "END_OF_LIST"
    ant_batch_lookup = tr_ant_custom.lookup_batch_by_idempotency_key(
        "nonexistent-idempotency-key", expected_custom_ids=["cid-1"]
    )
    assert ant_batch_lookup["found"] is False
    # Also verify non-200 HTTPError goes cleanly through _default_urlopen.
    sim_custom.oai_file_records["file-err-500"] = {"id": "file-err-500", "filename": "x.jsonl"}
    sim_custom.fail_oai_delete_file_ids.add("file-err-500")
    with pytest.raises(live_mod.LiveTransportError) as err_info:
        tr_oai_custom.delete_file("file-err-500")
    assert err_info.value.status_code == 500

    oai_calls = [c for c in urlopen_calls if c["url"].startswith("https://api.openai.com")]
    ant_calls = [c for c in urlopen_calls if c["url"].startswith("https://api.anthropic.com")]
    assert any(c["method"] == "POST" and c["url"].endswith("/v1/files") for c in oai_calls)
    assert any(c["method"] == "POST" and c["url"].endswith("/v1/batches") for c in oai_calls)
    assert any(c["method"] == "GET" and "/v1/batches?limit=100" in c["url"] for c in oai_calls)
    assert any(c["method"] == "GET" and "/v1/files?purpose=batch" in c["url"] for c in oai_calls)
    assert any(c["method"] == "DELETE" and "/v1/files/" in c["url"] for c in oai_calls)
    assert all(c["timeout"] == 37.5 and c["has_ssl_context"] for c in oai_calls)

    assert any(c["method"] == "POST" and c["url"].endswith("/v1/messages/batches") for c in ant_calls)
    assert any(c["method"] == "GET" and "/v1/messages/batches?limit=100" in c["url"] for c in ant_calls)
    assert any(c["method"] == "DELETE" and "/v1/messages/batches/" in c["url"] for c in ant_calls)
    assert all(c["timeout"] == 41.25 and c["has_ssl_context"] for c in ant_calls)

    # B. Pure default run_stage1_dev5_live_batch path (url_opener=None, transports_by_provider=None)
    #    uses default timeout=60.0 and settles both providers cleanly through urllib.request.urlopen.
    out_def = tmp_path / "out_fix05_default_60"
    shared_def = tmp_path / "shared_fix05_default_60" / "shared.json"
    sim_def = _SimulatedProviderServer(ledger_path=shared_def, output_dir=out_def)
    def_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(urllib.request, "urlopen", _make_mock_urlopen(sim_def, def_calls))

    res_def = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_def,
        providers=("openai", "anthropic"),
        url_opener=None,
        transports_by_provider=None,
        shared_budget_ledger_path=shared_def,
    )
    assert res_def["overall_status"] == "COMPLETED"
    assert res_def["total_unresolved_reserve_usd"] == 0.0
    assert any(c["method"] == "POST" and c["url"].endswith("/v1/files") for c in def_calls)
    assert any(c["method"] == "POST" and c["url"].endswith("/v1/messages/batches") for c in def_calls)
    assert all(c["timeout"] == 60.0 for c in def_calls)

    # C. Explicit two-positional-arg url_opener interface remains preserved.
    pos_calls: list[float] = []

    def _positional_only_opener(req: urllib.request.Request, timeout_pos: float, /) -> tuple[int, dict[str, str], bytes]:
        pos_calls.append(timeout_pos)
        return 200, {}, json.dumps({"object": "list", "data": [], "has_more": False}).encode("utf-8")

    tr_pos_oai = OpenAIBatchLiveTransport(
        secret_resolver=lambda _p: "SYNTH_OPENAI_UNIT_TEST_SECRET_99887766",
        url_opener=_positional_only_opener,
        timeout_seconds=19.5,
    )
    assert tr_pos_oai.lookup_batch_by_idempotency_key("k-pos")["found"] is False
    tr_pos_ant = AnthropicBatchLiveTransport(
        secret_resolver=lambda _p: "SYNTH_ANTHROPIC_UNIT_TEST_SECRET_112233",
        url_opener=_positional_only_opener,
        timeout_seconds=21.5,
    )
    assert tr_pos_ant.lookup_batch_by_idempotency_key("k-pos", expected_custom_ids=["cid-1"])["found"] is False
    assert pos_calls == [19.5, 21.5]


def test_fix05_2_resume_upload_in_flight_batch_id_null_via_default_urlopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX05 (2): resume from UPLOAD_IN_FLIGHT + batch_id=null ledger (TypeError crash shape) via default urlopen."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    _sp, _s4, pins = live_mod._load_and_verify_prompt_and_schema(env["dev5_root"])
    qs = load_approved_dev5_queries(q_path)

    def _seed_real_crash_ledger_shape(tag: str) -> tuple[Path, Path, str, str]:
        out_dir = tmp_path / f"out_fix05_resume_{tag}"
        shared_ledger = tmp_path / f"shared_fix05_resume_{tag}" / "stage1_dev5_shared_budget_ledger.json"
        out_dir.mkdir(parents=True, exist_ok=True)
        man = live_mod._load_or_init_run_manifest(
            manifest_path=out_dir / "dev5_run_manifest.json",
            slice_mode="dev5_plus_20pct_swap",
            queries=qs,
            prompt_pins=pins,
        )
        items_822 = build_approved_dev5_canary_items(
            dev5_queries=qs,
            corpus_docs=docs,
            slice_mode="dev5_plus_20pct_swap",
            packet_salt=str(man["packet_salt"]),
            run_nonce_seed=str(man["run_nonce_seed"]),
        )
        assert len(items_822) == 822
        intent = prepare_stage1_pre_submit_intent(
            ledger_path=shared_ledger,
            run_id="dev5-dev5_plus_20pct_swap-pass1-20261123T174107Z",
            rate_profile=ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 0.05, 0.25),
            custom_ids=[it["custom_id"] for it in items_822],
            batch_reserved_worst_case_usd=0.617744,
        )
        k = str(intent["client_idempotency_key"])
        up_fn = live_mod.openai_upload_filename_for_intent(k)
        # Match exact live crash ledger shape: UPLOAD_IN_FLIGHT, batch_id=None, reconcile_error from old TypeError.
        led = json.loads(shared_ledger.read_text(encoding="utf-8"))
        rec = led["intents"][k]
        rec.update(
            {
                "batch_id": None,
                "cleanup_error": None,
                "cleanup_status": "NOT_STARTED",
                "status": "UNRESOLVED_CRASH_RESERVED",
                "dispatch_stage": "UPLOAD_IN_FLIGHT",
                "dispatch_stage_updated_at_utc": "2026-11-23T17:41:08Z",
                "upload_started_at_utc": "2026-11-23T17:41:08Z",
                "input_upload_filename": up_fn,
                "input_jsonl_sha256": "7f4a28f1ddc99557b4311fb4c1f8ea63cd0a282599e9bf7e52dbe7206264b15e",
                "file_cleanup_status": "UNVERIFIED_FILE_CLEANUP_PENDING_RECONCILE",
                "reconcile_error": "openai:list_batches:NETWORK_ERROR:TypeError:_default_urlopen() takes 1 positional argument but 2 were given",
                "reserved_worst_case_usd": 0.617744,
                "unresolved_reserve_usd": 0.617744,
                "confirmed_cost_usd": 0.0,
                "source_output_dir": str(out_dir.resolve()),
                "wire_dispatch_tag": k[:6],
            }
        )
        led["total_unresolved_reserve_usd"] = 0.617744
        led["effective_committed_usd"] = 0.617744
        shared_ledger.write_text(json.dumps(led, indent=2), encoding="utf-8")
        return out_dir, shared_ledger, k, up_fn

    # Subcase A: Crashed before HTTP /v1/files accepted (no orphan file on server).
    # resume_only=True via default url_opener=None queries /v1/batches + /v1/files cleanly, releases reserve,
    # and subsequent run cleanly submits & completes 822 items for both OpenAI and Anthropic!
    out_a, shared_a, k_a, _fn_a = _seed_real_crash_ledger_shape("no_orphan")
    sim_a = _SimulatedProviderServer(ledger_path=shared_a, output_dir=out_a)
    calls_a: list[dict[str, Any]] = []
    monkeypatch.setattr(urllib.request, "urlopen", _make_mock_urlopen(sim_a, calls_a))

    res_a_resume = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_a,
        providers=("openai", "anthropic"),
        slice_mode="dev5_plus_20pct_swap",
        resume_only=True,
        url_opener=None,
        transports_by_provider=None,
        shared_budget_ledger_path=shared_a,
    )
    assert res_a_resume["total_unresolved_reserve_usd"] == 0.0
    led_a1 = json.loads(shared_a.read_text(encoding="utf-8"))
    ent_a1 = led_a1["intents"][k_a]
    assert ent_a1["status"] == "CANCELLED_UNSUBMITTED"
    assert ent_a1["file_cleanup_status"] == "VERIFIED_NO_REMOTE_FILE"
    assert ent_a1["file_reconcile_exhaustive"] is True
    assert ent_a1["file_reconcile_stop_reason"] == "END_OF_LIST"
    assert ent_a1["upload_started_at_utc"] == "2026-11-23T17:41:08Z"
    assert any(c["method"] == "GET" and "/v1/batches?limit=100" in c["url"] and c["timeout"] == 60.0 for c in calls_a)
    assert any(c["method"] == "GET" and "/v1/files?purpose=batch" in c["url"] and c["timeout"] == 60.0 for c in calls_a)

    # Next non-resume run dispatches & settles full 822 items via default opener cleanly.
    res_a_full = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_a,
        providers=("openai", "anthropic"),
        slice_mode="dev5_plus_20pct_swap",
        resume_only=False,
        url_opener=None,
        transports_by_provider=None,
        shared_budget_ledger_path=shared_a,
    )
    assert res_a_full["overall_status"] == "COMPLETED"
    assert res_a_full["providers"]["openai"]["settled_items"] == 822
    assert res_a_full["providers"]["anthropic"]["settled_items"] == 822
    assert res_a_full["total_unresolved_reserve_usd"] == 0.0

    # Subcase B: UPLOAD_IN_FLIGHT + batch_id=null WITH an orphan file already on OpenAI -> deletes via default urlopen.
    out_b, shared_b, k_b, fn_b = _seed_real_crash_ledger_shape("with_orphan")
    sim_b = _SimulatedProviderServer(ledger_path=shared_b, output_dir=out_b)
    sim_b.oai_file_records["file-oai-orphan-null"] = {
        "id": "file-oai-orphan-null",
        "object": "file",
        "purpose": "batch",
        "filename": fn_b,
        "created_at": int(live_mod._parse_iso_unix("2026-11-23T17:41:09Z") or 0),
    }
    calls_b: list[dict[str, Any]] = []
    monkeypatch.setattr(urllib.request, "urlopen", _make_mock_urlopen(sim_b, calls_b))

    res_b_resume = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_b,
        providers=("openai", "anthropic"),
        slice_mode="dev5_plus_20pct_swap",
        resume_only=True,
        url_opener=None,
        transports_by_provider=None,
        shared_budget_ledger_path=shared_b,
    )
    assert sim_b.deleted_files == ["file-oai-orphan-null"]
    assert sim_b.oai_file_records == {}
    assert res_b_resume["total_unresolved_reserve_usd"] == 0.0
    led_b1 = json.loads(shared_b.read_text(encoding="utf-8"))
    ent_b1 = led_b1["intents"][k_b]
    assert ent_b1["status"] == "CANCELLED_UNSUBMITTED"
    assert ent_b1["file_cleanup_status"] == "CLEANED_ORPHAN_FILE_VERIFIED"
    assert ent_b1["file_reconcile_exhaustive"] is True
    assert ent_b1["cleaned_file_ids"] == ["file-oai-orphan-null"]
    assert any(c["method"] == "DELETE" and "/v1/files/file-oai-orphan-null" in c["url"] and c["timeout"] == 60.0 for c in calls_b)


def test_fix06_1_anthropic_submit_strips_params_version_keeps_header_and_pinned_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX06 (1): Anthropic submit_batch copies params, pops anthropic_version, preserves HTTP header & pinned fields."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    sys_prompt, schema_s4, pins = live_mod._load_and_verify_prompt_and_schema(env["dev5_root"])
    qs = load_approved_dev5_queries(q_path)

    out_dir = tmp_path / "out_fix06_1"
    shared_ledger = tmp_path / "shared_fix06_1" / "shared.json"
    sim = _SimulatedProviderServer(ledger_path=shared_ledger, output_dir=out_dir)
    captured_ant_posts: list[dict[str, Any]] = []
    urlopen_calls: list[dict[str, Any]] = []
    base_mock_urlopen = _make_mock_urlopen(sim, urlopen_calls)

    def _capturing_urlopen(
        req: urllib.request.Request,
        timeout: float | None = None,
        context: Any = None,
    ) -> Any:
        if req.full_url == "https://api.anthropic.com/v1/messages/batches" and req.get_method() == "POST":
            hdrs_ci = {str(k).lower(): str(v) for k, v in req.header_items()}
            captured_ant_posts.append(
                {
                    "headers": hdrs_ci,
                    "body": json.loads((req.data or b"").decode("utf-8")),
                    "timeout": timeout,
                }
            )
        return base_mock_urlopen(req, timeout=timeout, context=context)

    monkeypatch.setattr(urllib.request, "urlopen", _capturing_urlopen)

    # 1. Direct transport submit_batch copies caller params without mutating caller dict.
    out_dir.mkdir(parents=True, exist_ok=True)
    man = live_mod._load_or_init_run_manifest(
        manifest_path=out_dir / "dev5_run_manifest.json",
        slice_mode="canary_1x10",
        queries=qs,
        prompt_pins=pins,
    )
    canary_items = build_approved_dev5_canary_items(
        dev5_queries=qs,
        corpus_docs=docs,
        slice_mode="canary_1x10",
        packet_salt=str(man["packet_salt"]),
        run_nonce_seed=str(man["run_nonce_seed"]),
        canary_1x10_doc_ids=[d["document_id"] for d in docs[:10]],
    )
    direct_wire = build_verified_live_wire_item(
        provider="anthropic",
        model_id="claude-haiku-5-5",
        item=canary_items[0],
        system_prompt=sys_prompt,
        response_schema=schema_s4,
        dispatch_tag="d1rect",
    )["wire_item"]
    assert direct_wire["params"]["anthropic_version"] == "2026-10-21"
    pre_intent = prepare_stage1_pre_submit_intent(
        ledger_path=shared_ledger,
        run_id="fix06-direct-check",
        rate_profile=ProviderRateProfile("anthropic", "claude-haiku-5-5", "claude-haiku-5-5", 0.05, 0.25),
        custom_ids=[canary_items[0]["custom_id"]],
        batch_reserved_worst_case_usd=0.01,
    )
    live_mod.record_stage1_dispatch_progress(
        ledger_path=shared_ledger,
        client_idempotency_key=str(pre_intent["client_idempotency_key"]),
        dispatch_stage="PRE_SUBMIT_RESERVED",
        source_output_dir=out_dir,
        wire_dispatch_tag="d1rect",
    )
    tr_ant = AnthropicBatchLiveTransport(
        secret_resolver=lambda _p: "SYNTH_ANTHROPIC_UNIT_TEST_SECRET_112233",
        url_opener=None,
        timeout_seconds=45.0,
    )
    tr_ant.submit_batch(
        run_id="fix06-direct-check",
        client_idempotency_key=str(pre_intent["client_idempotency_key"]),
        wire_items=[direct_wire],
        expected_snapshot_id="claude-haiku-5-5",
    )
    # Caller copy MUST still keep its original params intact (no in-place mutation).
    assert direct_wire["params"]["anthropic_version"] == "2026-10-21"

    # 2. End-to-end canary via default url_opener=None also strips params.anthropic_version on the wire.
    out_e2e = tmp_path / "out_fix06_e2e"
    shared_e2e = tmp_path / "shared_fix06_e2e" / "shared.json"
    sim_e2e = _SimulatedProviderServer(ledger_path=shared_e2e, output_dir=out_e2e)
    base_e2e_urlopen = _make_mock_urlopen(sim_e2e, urlopen_calls)

    def _e2e_urlopen(req: urllib.request.Request, timeout: float | None = None, context: Any = None) -> Any:
        if req.full_url == "https://api.anthropic.com/v1/messages/batches" and req.get_method() == "POST":
            hdrs_ci = {str(k).lower(): str(v) for k, v in req.header_items()}
            captured_ant_posts.append(
                {
                    "headers": hdrs_ci,
                    "body": json.loads((req.data or b"").decode("utf-8")),
                    "timeout": timeout,
                }
            )
        return base_e2e_urlopen(req, timeout=timeout, context=context)

    monkeypatch.setattr(urllib.request, "urlopen", _e2e_urlopen)
    res = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_e2e,
        providers=("anthropic",),
        url_opener=None,
        transports_by_provider=None,
        shared_budget_ledger_path=shared_e2e,
    )
    assert res["overall_status"] == "COMPLETED"
    assert res["providers"]["anthropic"]["settled_items"] == 10
    assert len(captured_ant_posts) == 2

    for post_call in captured_ant_posts:
        assert post_call["headers"]["anthropic-version"] == "2026-10-21"
        assert post_call["headers"]["x-api-key"] == "SYNTH_ANTHROPIC_UNIT_TEST_SECRET_112233"
        assert post_call["headers"]["content-type"] == "application/json"
        reqs = post_call["body"]["requests"]
        assert len(reqs) >= 1
        for r_item in reqs:
            params = r_item["params"]
            assert "anthropic_version" not in params
            assert params["model"] == "claude-haiku-5-5"
            assert params["max_tokens"] == 1024
            assert params["system"] == sys_prompt
            assert sha256_bytes(params["system"].encode("utf-8")) == pins["system_prompt_sha256"]
            assert params["output_config"] == {
                "effort": "low",
                "format": {"type": "json_schema", "schema": schema_s4},
            }
            assert len(params["messages"]) == 1 and params["messages"][0]["role"] == "user"
            assert "<UNTRUSTED_CORPUS_DOCUMENT_" in params["messages"][0]["content"]


def test_fix06_2_anthropic_recovery_fixture_preserves_openai_history_linkage_and_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX06 (2): fixture of DEV5 real incident recovers Anthropic-only (10-item smoke then 812 remainder), keeping OpenAI & history."""
    docs, q_path, v_sha = _make_137_synth_corpus_and_queries(tmp_path)
    monkeypatch.setattr(live_mod, "EXPECTED_V_CORPUS_SHA256", v_sha)
    env = _setup_phase2_pack_and_dev5_configs(tmp_path)
    _sp, _s4, pins = live_mod._load_and_verify_prompt_and_schema(env["dev5_root"])
    qs = load_approved_dev5_queries(q_path)

    out_dir = tmp_path / "out_fix06_recovery"
    shared_ledger = tmp_path / "shared_fix06_recovery" / "stage1_dev5_shared_budget_ledger.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    man = live_mod._load_or_init_run_manifest(
        manifest_path=out_dir / "dev5_run_manifest.json",
        slice_mode="dev5_plus_20pct_swap",
        queries=qs,
        prompt_pins=pins,
    )
    items_822 = build_approved_dev5_canary_items(
        dev5_queries=qs,
        corpus_docs=docs,
        slice_mode="dev5_plus_20pct_swap",
        packet_salt=str(man["packet_salt"]),
        run_nonce_seed=str(man["run_nonce_seed"]),
    )
    assert len(items_822) == 822

    old_ant_batch_id = "msgbatch_01VmF5Kf8DLp4DC7gWHWt6GV"
    old_oai_batch_id = "batch_6b04806364b08190a3a65fdd4669630c"
    old_oai_file_id = "file-GeWKeoye2pnuESjtbg9u8Z"

    # Build exact DEV5 shared ledger fixture matching the observed real state:
    # - prior cancelled OpenAI UPLOAD_IN_FLIGHT intent ($0.00)
    # - failed terminal Anthropic batch intent ($0.614057 confirmed worst-case)
    # - active OpenAI batch intent ($0.617744 unresolved reserve)
    oai_cancel_intent = prepare_stage1_pre_submit_intent(
        ledger_path=shared_ledger,
        run_id="dev5-dev5_plus_20pct_swap-pass1-20261123T174107Z",
        rate_profile=ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 0.05, 0.25),
        custom_ids=[it["custom_id"] for it in items_822],
        batch_reserved_worst_case_usd=0.617744,
    )
    k_oai_cancel = str(oai_cancel_intent["client_idempotency_key"])

    ant_old_intent = prepare_stage1_pre_submit_intent(
        ledger_path=shared_ledger,
        run_id="dev5-dev5_plus_20pct_swap-pass1-20261123T180515Z",
        rate_profile=ProviderRateProfile("anthropic", "claude-haiku-5-5", "claude-haiku-5-5", 0.05, 0.25),
        custom_ids=[it["custom_id"] for it in items_822],
        batch_reserved_worst_case_usd=0.614057,
    )
    k_ant_old = str(ant_old_intent["client_idempotency_key"])

    oai_active_intent = prepare_stage1_pre_submit_intent(
        ledger_path=shared_ledger,
        run_id="dev5-dev5_plus_20pct_swap-pass1-20261123T180515Z",
        rate_profile=ProviderRateProfile("openai", "gpt-6-luna", "gpt-6-luna", 0.05, 0.25),
        custom_ids=[it["custom_id"] for it in items_822],
        batch_reserved_worst_case_usd=0.617744,
    )
    k_oai_active = str(oai_active_intent["client_idempotency_key"])

    led_init = json.loads(shared_ledger.read_text(encoding="utf-8"))
    led_init["intents"][k_oai_cancel].update(
        {
            "status": "CANCELLED_UNSUBMITTED",
            "dispatch_stage": "UPLOAD_IN_FLIGHT",
            "batch_id": None,
            "confirmed_cost_usd": 0.0,
            "unresolved_reserve_usd": 0.0,
            "file_cleanup_status": "VERIFIED_NO_REMOTE_FILE",
            "source_output_dir": str(out_dir.resolve()),
        }
    )
    led_init["intents"][k_ant_old].update(
        {
            "status": "SETTLED_MISSING_USAGE_WORST_CASE_RESERVED",
            "dispatch_stage": "BATCH_DISPATCHED",
            "batch_id": old_ant_batch_id,
            "confirmed_cost_usd": 0.614057,
            "unresolved_reserve_usd": 0.0,
            "cleanup_status": "COMPLETED",
            "source_output_dir": str(out_dir.resolve()),
            "wire_dispatch_tag": k_ant_old[:6],
        }
    )
    led_init["intents"][k_oai_active].update(
        {
            "status": "NONTERMINAL_RESERVED_IN_PROGRESS",
            "dispatch_stage": "BATCH_DISPATCHED",
            "batch_id": old_oai_batch_id,
            "input_file_id": old_oai_file_id,
            "confirmed_cost_usd": 0.0,
            "unresolved_reserve_usd": 0.617744,
            "cleanup_status": "DEFERRED_NONTERMINAL",
            "source_output_dir": str(out_dir.resolve()),
            "wire_dispatch_tag": k_oai_active[:6],
        }
    )
    led_init["total_confirmed_spent_usd"] = 0.614057
    led_init["total_unresolved_reserve_usd"] = 0.617744
    led_init["effective_committed_usd"] = 1.231801
    led_init["providers_committed_usd"] = {"anthropic": 0.614057, "openai": 0.617744}
    shared_ledger.write_text(json.dumps(led_init, indent=2), encoding="utf-8")

    # Seed existing anthropic_raw_log.jsonl with 1644 lines (822 invalid_request_error + 822 BATCH_ABORT_EXCESSIVE_RETRY_RATE).
    ant_raw_log = out_dir / "anthropic_raw_log.jsonl"
    historical_lines: list[str] = []
    invalid_err_str = (
        "{'type': 'errored', 'error': {'type': 'error', 'error': "
        "{'details': None, 'type': 'invalid_request_error', "
        "'message': 'anthropic_version: Extra inputs are not permitted'}, 'request_id': None}}"
    )
    for it in items_822:
        historical_lines.append(
            json.dumps(
                {
                    "event_type": "ITEM_ATTEMPT",
                    "recorded_at_utc": "2026-11-23T18:06:50Z",
                    "provider": "anthropic",
                    "batch_id": old_ant_batch_id,
                    "attempt_no": 1,
                    "custom_id": it["custom_id"],
                    "wire_custom_id": f"{it['wire_custom_id']}__{k_ant_old[:6]}",
                    "packet_item_uuid": it["packet_item_uuid"],
                    "query_id": it["query_meta"]["query_id"],
                    "document_id": it["doc_record_for_leak_check"]["document_id"],
                    "prompt_order": it["prompt_order"],
                    "model_snapshot_id": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                    "item_cost_usd": 0.0,
                    "parsed_response": None,
                    "projected_canonical_response": None,
                    "local_validation": {"confirmed_gain": 0, "error_code": invalid_err_str, "max_admissible_gain": 3, "state": "ERROR"},
                    "final_for_item": False,
                }
            )
        )
    for it in items_822:
        historical_lines.append(
            json.dumps(
                {
                    "event_type": "ITEM_ATTEMPT",
                    "recorded_at_utc": "2026-11-23T18:06:51Z",
                    "provider": "anthropic",
                    "batch_id": old_ant_batch_id,
                    "attempt_no": 2,
                    "custom_id": it["custom_id"],
                    "wire_custom_id": f"{it['wire_custom_id']}__{k_ant_old[:6]}",
                    "packet_item_uuid": it["packet_item_uuid"],
                    "query_id": it["query_meta"]["query_id"],
                    "document_id": it["doc_record_for_leak_check"]["document_id"],
                    "prompt_order": it["prompt_order"],
                    "local_validation": {
                        "state": "ERROR",
                        "confirmed_gain": 0,
                        "max_admissible_gain": 3,
                        "error_code": "BATCH_ABORT_EXCESSIVE_RETRY_RATE",
                    },
                    "final_for_item": True,
                }
            )
        )
    assert len(historical_lines) == 1644
    ant_raw_log.write_text("\n".join(historical_lines) + "\n", encoding="utf-8")

    # Configure mock provider server + enforce Anthropic params MUST NOT include anthropic_version.
    sim = _SimulatedProviderServer(ledger_path=shared_ledger, output_dir=out_dir)
    # Seed OpenAI batch on sim too for end-of-test dual-judge completion check after Anthropic recovery.
    sim.oai_batches[old_oai_batch_id] = {
        "id": old_oai_batch_id,
        "object": "batch",
        "status": "completed",
        "input_file_id": old_oai_file_id,
        "output_file_id": "file-oai-out-fixture",
        "error_file_id": None,
        "request_counts": {"total": 822, "completed": 822, "failed": 0},
        "_ready_out_fid": "file-oai-out-fixture",
        "_polls": 0,
    }
    oai_wire_lines = [
        build_verified_live_wire_item(
            provider="openai",
            model_id="gpt-6-luna",
            item=it,
            system_prompt=_sp,
            response_schema=_s4,
            dispatch_tag=k_oai_active[:6],
        )["wire_item"]
        for it in items_822
    ]
    sim.oai_files["file-oai-out-fixture"] = sim._build_oai_output_jsonl(oai_wire_lines)

    urlopen_calls: list[dict[str, Any]] = []
    base_mock_urlopen = _make_mock_urlopen(sim, urlopen_calls)

    def _strict_mock_urlopen(req: urllib.request.Request, timeout: float | None = None, context: Any = None) -> Any:
        if req.full_url == "https://api.anthropic.com/v1/messages/batches" and req.get_method() == "POST":
            body_obj = json.loads((req.data or b"").decode("utf-8"))
            for r_item in body_obj.get("requests", []):
                assert "anthropic_version" not in r_item["params"], "BUG: anthropic_version leaked into params!"
        return base_mock_urlopen(req, timeout=timeout, context=context)

    monkeypatch.setattr(urllib.request, "urlopen", _strict_mock_urlopen)

    # A. Fail-closed checks:
    # A1. Normal run WITHOUT recovery flag does NOT resend Anthropic error items.
    res_no_flag = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_dir,
        providers=("anthropic",),
        slice_mode="dev5_plus_20pct_swap",
        url_opener=None,
        shared_budget_ledger_path=shared_ledger,
    )
    assert res_no_flag["dispatched_this_run"] == []
    assert [c for c in urlopen_calls if "messages/batches" in c["url"]] == []

    # A2. Recovery with OpenAI in providers is blocked fail-closed.
    with pytest.raises(PermissionError, match="ANTHROPIC_RECOVERY_REQUIRES_PROVIDERS_ANTHROPIC_ONLY"):
        run_stage1_dev5_live_batch(
            activation_pack_dir=env["pack_dir"],
            external_trust_root_dir=env["trust_root_dir"],
            dev5_root=env["dev5_root"],
            corpus_docs=docs,
            queries_json_path=q_path,
            rate_evidence_path=env["rate_evidence_path"],
            output_dir=out_dir,
            shared_budget_ledger_path=shared_ledger,
            slice_mode="canary_1x10",
            providers=("openai", "anthropic"),
            recover_anthropic_extra_input_batch_ids=(old_ant_batch_id,),
            allow_live_network=True,
            vault_path=env["vault_path"],
            out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
            out_of_band_manifest_sha256=env["oob_manifest_sha"],
            out_of_band_auditor_report_sha256=env["oob_report_sha"],
            expected_target_zip_sha256=env["target_zip_sha"],
            raw_probe_transcript_path=env["raw_probe_path"],
        )

    # A3. Unknown batch ID or OpenAI batch ID is rejected before any network call.
    with pytest.raises(KeyError, match="UNKNOWN_ANTHROPIC_RECOVERY_BATCH_ID"):
        inspect_stage1_dev5_live_readiness(
            activation_pack_dir=env["pack_dir"],
            external_trust_root_dir=env["trust_root_dir"],
            dev5_root=env["dev5_root"],
            corpus_docs=docs,
            queries_json_path=q_path,
            rate_evidence_path=env["rate_evidence_path"],
            output_dir=out_dir,
            shared_budget_ledger_path=shared_ledger,
            slice_mode="canary_1x10",
            providers=("anthropic",),
            recover_anthropic_extra_input_batch_ids=(old_oai_batch_id,),
            vault_path=env["vault_path"],
            out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
            out_of_band_manifest_sha256=env["oob_manifest_sha"],
            out_of_band_auditor_report_sha256=env["oob_report_sha"],
            expected_target_zip_sha256=env["target_zip_sha"],
            raw_probe_transcript_path=env["raw_probe_path"],
        )

    # B. Step 1 of recovery plan: dry-run inspect on small sample (canary_1x10) under $2.00 cap.
    canary_10_docs = [d["document_id"] for d in docs[:10]]
    dry_smoke = inspect_stage1_dev5_live_readiness(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=out_dir,
        shared_budget_ledger_path=shared_ledger,
        slice_mode="canary_1x10",
        providers=("anthropic",),
        canary_1x10_doc_ids=canary_10_docs,
        recover_anthropic_extra_input_batch_ids=(old_ant_batch_id,),
        vault_path=env["vault_path"],
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )
    assert dry_smoke["planned_batches"]["anthropic"]["pending_to_send_items"] == 10
    assert dry_smoke["fits_combined_dev_cap"] is True
    assert dry_smoke["recovery_plan"]["target_batches"][0]["supersedes_batch_id"] == old_ant_batch_id
    # Dry-run inspect must not mutate raw log line count.
    assert len(ant_raw_log.read_text(encoding="utf-8").splitlines()) == 1644

    # C. Step 2 of recovery plan: small-sample live smoke recovery (canary_1x10 = 10 items).
    urlopen_calls.clear()
    res_smoke = run_stage1_dev5_live_batch(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=out_dir,
        shared_budget_ledger_path=shared_ledger,
        slice_mode="canary_1x10",
        providers=("anthropic",),
        canary_1x10_doc_ids=canary_10_docs,
        recover_anthropic_extra_input_batch_ids=(old_ant_batch_id,),
        allow_live_network=True,
        poll_interval_seconds=0.01,
        max_wait_seconds=5.0,
        sleep_fn=lambda _s: None,
        vault_path=env["vault_path"],
        url_opener=None,
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )
    assert len(res_smoke["dispatched_this_run"]) == 1
    assert res_smoke["dispatched_this_run"][0]["item_count"] == 10
    assert res_smoke["dispatched_this_run"][0]["batch_id"] == "msgbatch_ant_1"
    assert res_smoke["providers"]["anthropic"]["settled_items"] == 10
    assert res_smoke["providers"]["anthropic"]["grade_counts"].get("ERROR", 0) == 0
    # Zero OpenAI HTTP calls during Anthropic-only recovery!
    assert [c for c in urlopen_calls if "api.openai.com" in c["url"]] == []

    # D. Step 3: dry-run inspect on full 822 slice shows 10 already settled and ONLY 812 remaining!
    dry_rem = inspect_stage1_dev5_live_readiness(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=out_dir,
        shared_budget_ledger_path=shared_ledger,
        slice_mode="dev5_plus_20pct_swap",
        providers=("anthropic",),
        recover_anthropic_extra_input_batch_ids=(old_ant_batch_id,),
        vault_path=env["vault_path"],
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )
    assert dry_rem["planned_batches"]["anthropic"]["already_settled_items"] == 10
    assert dry_rem["planned_batches"]["anthropic"]["pending_to_send_items"] == 812
    assert dry_rem["planned_batches"]["anthropic"]["reserved_worst_case_usd"] > 0.0
    assert dry_rem["fits_combined_dev_cap"] is True
    assert dry_rem["projected_total_committed_usd"] <= 2.0

    # E. Step 4: execute remaining 812 Anthropic recovery items with full lineage & OpenAI preservation.
    urlopen_calls.clear()
    res_rem = run_stage1_dev5_live_batch(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=out_dir,
        shared_budget_ledger_path=shared_ledger,
        slice_mode="dev5_plus_20pct_swap",
        providers=("anthropic",),
        recover_anthropic_extra_input_batch_ids=(old_ant_batch_id,),
        allow_live_network=True,
        poll_interval_seconds=0.01,
        max_wait_seconds=5.0,
        sleep_fn=lambda _s: None,
        vault_path=env["vault_path"],
        url_opener=None,
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )
    assert len(res_rem["dispatched_this_run"]) == 1
    assert res_rem["dispatched_this_run"][0]["item_count"] == 812
    assert res_rem["dispatched_this_run"][0]["batch_id"] == "msgbatch_ant_2"
    assert res_rem["dispatched_this_run"][0]["reserved_worst_case_usd"] == pytest.approx(
        dry_rem["planned_batches"]["anthropic"]["reserved_worst_case_usd"], abs=1e-6
    )
    assert res_rem["dispatched_this_run"][0]["reserved_worst_case_usd"] > 0.4
    assert res_rem["providers"]["anthropic"]["settled_items"] == 822
    assert res_rem["providers"]["anthropic"]["remaining_unsettled_items"] == 0
    assert res_rem["providers"]["anthropic"]["grade_counts"].get("ERROR", 0) == 0
    assert res_rem["recovery_summary"][0]["supersedes_batch_ids"] == [old_ant_batch_id]
    assert res_rem["recovery_summary"][0]["supersedes_intent_keys"] == [k_ant_old]
    assert res_rem["recovery_summary"][0]["historical_error_rows_preserved"] == 1644
    assert [c for c in urlopen_calls if "api.openai.com" in c["url"]] == []

    # Verify shared ledger keeps historical spend/OpenAI reserve untouched AND adds new recovery intents + linkage!
    led_final = json.loads(shared_ledger.read_text(encoding="utf-8"))
    k_smoke = res_smoke["dispatched_this_run"][0]["client_idempotency_key"]
    k_rem = res_rem["dispatched_this_run"][0]["client_idempotency_key"]
    assert led_final["intents"][k_oai_active]["batch_id"] == old_oai_batch_id
    assert led_final["intents"][k_oai_active]["status"] == "NONTERMINAL_RESERVED_IN_PROGRESS"
    assert led_final["intents"][k_oai_active]["unresolved_reserve_usd"] == pytest.approx(0.617744, abs=1e-6)

    old_ant_ent = led_final["intents"][k_ant_old]
    assert old_ant_ent["batch_id"] == old_ant_batch_id
    assert old_ant_ent["status"] == "SETTLED_MISSING_USAGE_WORST_CASE_RESERVED"
    assert old_ant_ent["confirmed_cost_usd"] == pytest.approx(0.614057, abs=1e-6)
    assert old_ant_ent["superseded_by_intent_keys"] == [k_smoke, k_rem]
    assert old_ant_ent["superseded_by_batch_ids"] == ["msgbatch_ant_1", "msgbatch_ant_2"]

    for rk in (k_smoke, k_rem):
        r_ent = led_final["intents"][rk]
        assert r_ent["supersedes_intent_keys"] == [k_ant_old]
        assert r_ent["supersedes_batch_ids"] == [old_ant_batch_id]
        assert r_ent["recovery_mode"] == "ANTHROPIC_EXTRA_INPUT_VERSION_FIX06"
        assert r_ent["reserved_worst_case_usd"] > 0.0
        assert r_ent["confirmed_cost_usd"] > 0.0

    # Verify all 1644 historical lines preserved verbatim + 2 epoch rows + 822 valid recovered rows = 2468 lines.
    raw_lines_after = ant_raw_log.read_text(encoding="utf-8").splitlines()
    assert raw_lines_after[:1644] == historical_lines
    assert len(raw_lines_after) == 1644 + 2 + 822
    epoch_rows = [json.loads(ln) for ln in raw_lines_after[1644:] if json.loads(ln).get("event_type") == "ANTHROPIC_RECOVERY_EPOCH"]
    assert len(epoch_rows) == 2
    assert epoch_rows[0]["supersedes_batch_id"] == old_ant_batch_id
    assert epoch_rows[0]["recovered_item_count"] == 10
    assert epoch_rows[1]["supersedes_batch_id"] == old_ant_batch_id
    assert epoch_rows[1]["recovered_item_count"] == 812

    # F. Normal --resume-only on BOTH providers settles OpenAI's active batch WITHOUT re-running Anthropic!
    res_dual = _run_canary(
        env=env,
        docs=docs,
        q_path=q_path,
        out_dir=out_dir,
        providers=("openai", "anthropic"),
        slice_mode="dev5_plus_20pct_swap",
        resume_only=True,
        url_opener=None,
        shared_budget_ledger_path=shared_ledger,
    )
    assert res_dual["overall_status"] == "COMPLETED"
    assert res_dual["providers"]["openai"]["settled_items"] == 822
    assert res_dual["providers"]["anthropic"]["settled_items"] == 822
    assert res_dual["total_unresolved_reserve_usd"] == 0.0
    assert res_dual["effective_committed_usd"] <= 2.0

    # G. Idempotency + preserving already-settled OpenAI results: calling recovery again sends 0 items and keeps openai_raw_log byte-identical.
    oai_raw_path = out_dir / "openai_raw_log.jsonl"
    oai_bytes_before = oai_raw_path.read_bytes()
    ant_bytes_before = ant_raw_log.read_bytes()
    res_idem = run_stage1_dev5_live_batch(
        activation_pack_dir=env["pack_dir"],
        external_trust_root_dir=env["trust_root_dir"],
        dev5_root=env["dev5_root"],
        corpus_docs=docs,
        queries_json_path=q_path,
        rate_evidence_path=env["rate_evidence_path"],
        output_dir=out_dir,
        shared_budget_ledger_path=shared_ledger,
        slice_mode="dev5_plus_20pct_swap",
        providers=("anthropic",),
        recover_anthropic_extra_input_batch_ids=(old_ant_batch_id,),
        allow_live_network=True,
        poll_interval_seconds=0.01,
        max_wait_seconds=5.0,
        sleep_fn=lambda _s: None,
        vault_path=env["vault_path"],
        url_opener=None,
        out_of_band_owner_pubkey_sha256=env["oob_owner_sha"],
        out_of_band_manifest_sha256=env["oob_manifest_sha"],
        out_of_band_auditor_report_sha256=env["oob_report_sha"],
        expected_target_zip_sha256=env["target_zip_sha"],
        raw_probe_transcript_path=env["raw_probe_path"],
    )
    assert res_idem["dispatched_this_run"] == []
    assert res_idem["providers"]["anthropic"]["settled_items"] == 822
    assert oai_raw_path.read_bytes() == oai_bytes_before
    assert ant_raw_log.read_bytes() == ant_bytes_before


def test_fix06_3_cli_recover_anthropic_flag_parsing() -> None:
    """FIX06 (3): CLI exposes --recover-anthropic-batch-id repeatable flag defaulting empty."""
    import run_route2_stage1_dev5_live as live_cli

    p = live_cli._build_parser()
    a_default = p.parse_args(["--dry-run-inspect", "--oob-manifest-sha256", "a" * 64])
    assert a_default.recover_anthropic_batch_ids == []

    a_rec = p.parse_args(
        [
            "--execute-live-batch",
            "--allow-live-network",
            "--providers",
            "anthropic",
            "--recover-anthropic-batch-id",
            "msgbatch_01VmF5Kf8DLp4DC7gWHWt6GV",
            "--oob-manifest-sha256",
            "a" * 64,
        ]
    )
    assert a_rec.providers == ["anthropic"]
    assert a_rec.recover_anthropic_batch_ids == ["msgbatch_01VmF5Kf8DLp4DC7gWHWt6GV"]
