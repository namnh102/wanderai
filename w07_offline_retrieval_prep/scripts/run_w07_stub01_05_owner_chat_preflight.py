"""One-shot local read-only STUB-01..05 preflight CLI runner under OWNER_CHAT_READONLY_V1.

Implements the CLI contract in `GOMATE_W07_STUB01_05_OWNER_CHAT_AUTH_IMPLEMENTATION_CONTRACT_V1_2026-11-21.md`:
1. Enforces one-shot deduplication (`ALREADY_EXECUTED` if `execution_summary.json` exists in `--output-dir`).
2. Disables all network/HF hub calls (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`) and wraps
   `socket.socket` to observably count and block any non-loopback network attempt (`0` requests).
3. Verifies the `OWNER_CHAT_READONLY_V1` authorization gate and 7 pinned source artifacts
   before invoking `STUB-01` .. `STUB-05` in order, stopping immediately on first failure.
4. Emits `stub_01_result.json` .. `stub_05_result.json` and `execution_summary.json` into
   an isolated private output directory outside the tracked repository.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import socket
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from pathlib import Path

PREP_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PREP_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from w07_retrieval.real_corpus_preflight import (  # noqa: E402
    ALLOWED_READONLY_STUB_IDS,
    LIVE_137_CORPUS_EXPECTATIONS,
    CorpusPreflightExpectations,
    StubPreflightAuthMode,
    execute_stub01_fx01_hash_and_arm_p_counts,
    execute_stub02_fx02_canonical_conservation,
    execute_stub03_fx03_audit_tags_and_v_hash,
    execute_stub04_fx04_c1_token_ceiling,
    execute_stub05_fx05_overture_visibility,
    validate_stub01_05_readonly_preflight_gate,
)

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def run_one_shot_stub01_05_preflight(
    *,
    output_dir: Path,
    annex_v0_2_2_path: Path,
    tech_freeze_receipt_path: Path,
    stub_auth_receipt_path: Path,
    corpus_bundle_manifest_path: Path,
    auth_mode: StubPreflightAuthMode = "OWNER_CHAT_READONLY_V1",
    chat_auth_waiver_path: Optional[Path] = None,
    original_exec_decision_path: Optional[Path] = None,
    snapshot_dir: Optional[Path] = None,
    expectations: CorpusPreflightExpectations = LIVE_137_CORPUS_EXPECTATIONS,
    _synthetic_fixture_mode: bool = False,
) -> Dict[str, Any]:
    """Execute STUB-01..STUB-05 once in order, writing per-stub JSONs and execution_summary.json."""
    out_p = Path(output_dir)
    summary_path = out_p / "execution_summary.json"
    if summary_path.exists():
        raise RuntimeError(
            f"ALREADY_EXECUTED: one-shot STUB-01..05 preflight receipt already exists at {summary_path}; "
            "duplicate execution is blocked."
        )
    for idx in range(1, 6):
        stub_file = out_p / f"stub_0{idx}_result.json"
        if stub_file.exists():
            raise RuntimeError(
                f"ALREADY_EXECUTED: existing stub result detected at {stub_file}; duplicate execution is blocked."
            )

    for env_k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        os.environ[env_k] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    network_counter = {"non_loopback_attempts": 0}
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_create_conn = socket.create_connection

    def _extract_host(addr: Any) -> Optional[str]:
        if isinstance(addr, tuple) and len(addr) >= 1 and isinstance(addr[0], str):
            return addr[0]
        return None

    def _guarded_connect(self: socket.socket, address: Any) -> Any:
        host = _extract_host(address)
        if host is not None and host not in _LOOPBACK_HOSTS:
            network_counter["non_loopback_attempts"] += 1
            raise RuntimeError(f"OUTBOUND_NETWORK_BLOCKED: target={host!r}")
        return orig_connect(self, address)

    def _guarded_connect_ex(self: socket.socket, address: Any) -> int:
        host = _extract_host(address)
        if host is not None and host not in _LOOPBACK_HOSTS:
            network_counter["non_loopback_attempts"] += 1
            raise RuntimeError(f"OUTBOUND_NETWORK_BLOCKED: target={host!r}")
        return orig_connect_ex(self, address)

    def _guarded_create_conn(address: Any, *args: Any, **kwargs: Any) -> Any:
        host = _extract_host(address)
        if host is not None and host not in _LOOPBACK_HOSTS:
            network_counter["non_loopback_attempts"] += 1
            raise RuntimeError(f"OUTBOUND_NETWORK_BLOCKED: target={host!r}")
        return orig_create_conn(address, *args, **kwargs)

    socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _guarded_connect_ex  # type: ignore[method-assign]
    socket.create_connection = _guarded_create_conn  # type: ignore[assignment]

    try:
        # Step 1: Pre-authorize all 5 stubs before running any scientific check
        last_gate_info: Dict[str, Any] = {}
        for stub_id in ALLOWED_READONLY_STUB_IDS:
            last_gate_info = validate_stub01_05_readonly_preflight_gate(
                requested_stub_id=stub_id,
                annex_v0_2_2_path=annex_v0_2_2_path,
                tech_freeze_receipt_path=tech_freeze_receipt_path,
                stub_auth_receipt_path=stub_auth_receipt_path,
                corpus_bundle_manifest_path=corpus_bundle_manifest_path,
                auth_mode=auth_mode,
                chat_auth_waiver_path=chat_auth_waiver_path,
                original_exec_decision_path=original_exec_decision_path,
                _synthetic_fixture_mode=_synthetic_fixture_mode,
            )

        out_p.mkdir(parents=True, exist_ok=True)
        preflight_module_path = (
            PREP_ROOT / "src" / "w07_retrieval" / "real_corpus_preflight.py"
        )
        code_sha256 = _sha256_file(preflight_module_path)
        manifest_sha256 = _sha256_file(Path(corpus_bundle_manifest_path))

        common_kwargs: Dict[str, Any] = {
            "annex_v0_2_2_path": annex_v0_2_2_path,
            "tech_freeze_receipt_path": tech_freeze_receipt_path,
            "stub_auth_receipt_path": stub_auth_receipt_path,
            "corpus_bundle_manifest_path": corpus_bundle_manifest_path,
            "expectations": expectations,
            "auth_mode": auth_mode,
            "chat_auth_waiver_path": chat_auth_waiver_path,
            "original_exec_decision_path": original_exec_decision_path,
            "_synthetic_fixture_mode": _synthetic_fixture_mode,
        }

        stub_dispatch: Sequence[Tuple[str, str, Callable[[], Dict[str, Any]]]] = (
            (
                "STUB-01",
                "stub_01_result.json",
                lambda: execute_stub01_fx01_hash_and_arm_p_counts(**common_kwargs),
            ),
            (
                "STUB-02",
                "stub_02_result.json",
                lambda: execute_stub02_fx02_canonical_conservation(
                    **common_kwargs, snapshot_dir=snapshot_dir
                ),
            ),
            (
                "STUB-03",
                "stub_03_result.json",
                lambda: execute_stub03_fx03_audit_tags_and_v_hash(**common_kwargs),
            ),
            (
                "STUB-04",
                "stub_04_result.json",
                lambda: execute_stub04_fx04_c1_token_ceiling(
                    **common_kwargs, snapshot_dir=snapshot_dir
                ),
            ),
            (
                "STUB-05",
                "stub_05_result.json",
                lambda: execute_stub05_fx05_overture_visibility(
                    **common_kwargs, snapshot_dir=snapshot_dir
                ),
            ),
        )

        per_stub_records: List[Dict[str, Any]] = []
        overall_status = "PASS"
        stopped_on_stub: Optional[str] = None

        for stub_id, filename, fn in stub_dispatch:
            started_at = _utc_iso_now()
            try:
                raw_metrics = fn()
                completed_at = _utc_iso_now()
                metrics_body = {
                    k: v for k, v in raw_metrics.items() if k != "gate"
                }
                ev_sha = _sha256_bytes(
                    json.dumps(
                        metrics_body, ensure_ascii=False, sort_keys=True
                    ).encode("utf-8")
                )
                stub_payload: Dict[str, Any] = {
                    "stub_id": stub_id,
                    "status": "PASS",
                    "metrics": metrics_body,
                    "evidence_sha256": ev_sha,
                    "code_sha256": code_sha256,
                    "manifest_sha256": manifest_sha256,
                    "error_code": None,
                    "started_at": started_at,
                    "completed_at": completed_at,
                }
            except Exception as exc:
                completed_at = _utc_iso_now()
                err_msg = f"{type(exc).__name__}: {exc}"
                ev_sha = _sha256_bytes(err_msg.encode("utf-8"))
                stub_payload = {
                    "stub_id": stub_id,
                    "status": "FAIL",
                    "metrics": {},
                    "evidence_sha256": ev_sha,
                    "code_sha256": code_sha256,
                    "manifest_sha256": manifest_sha256,
                    "error_code": err_msg,
                    "started_at": started_at,
                    "completed_at": completed_at,
                }
                overall_status = "FAIL"
                stopped_on_stub = stub_id

            stub_out_path = out_p / filename
            stub_bytes = (
                json.dumps(stub_payload, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            ).encode("utf-8")
            stub_out_path.write_bytes(stub_bytes)
            per_stub_records.append(
                {
                    "stub_id": stub_id,
                    "result_file": filename,
                    "status": stub_payload["status"],
                    "evidence_sha256": stub_payload["evidence_sha256"],
                    "result_file_sha256": _sha256_bytes(stub_bytes),
                    "error_code": stub_payload["error_code"],
                }
            )
            if overall_status != "PASS":
                break

        summary_obj: Dict[str, Any] = {
            "schema_version": "W07_STUB01_05_ONE_SHOT_EXECUTION_SUMMARY_V1",
            "overall_status": overall_status,
            "stopped_on_stub": stopped_on_stub,
            "executed_stub_count": len(per_stub_records),
            "authorization_mode": auth_mode,
            "identity_authentication": last_gate_info.get(
                "identity_authentication", "NOT_CRYPTOGRAPHICALLY_VERIFIED"
            ),
            "authorization_assurance": last_gate_info.get("authorization_assurance"),
            "decision_id": last_gate_info.get("decision_id"),
            "chat_auth_waiver_sha256": last_gate_info.get("chat_auth_waiver_sha256"),
            "policy_receipt_sha256": last_gate_info.get("policy_receipt_sha256"),
            "approved_annex_v0_2_2_sha256": last_gate_info.get(
                "approved_annex_v0_2_2_sha256"
            ),
            "tech_freeze_receipt_sha256": last_gate_info.get(
                "tech_freeze_receipt_sha256"
            ),
            "corpus_bundle_manifest_sha256": manifest_sha256,
            "real_corpus_preflight_code_sha256": code_sha256,
            "runner_cli_code_sha256": _sha256_file(Path(__file__).resolve()),
            "profile_name": expectations.profile_name,
            "host_environment": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
            },
            "observable_counters": {
                "live_api_calls": 0,
                "network_requests": network_counter["non_loopback_attempts"],
                "paid_api_spend_usd": 0.0,
            },
            "downstream_governance_hold": {
                "od_g15_05": "HOLD",
                "full_g15_closed": False,
                "stub_06_formal_g3_g4_authorized": False,
                "g2_g3_g4_g5_g6_authorized": False,
                "final50_dev_t0_live_api_authorized": False,
                "public_push_merge_authorized": False,
            },
            "stubs": per_stub_records,
        }
        summary_bytes = (
            json.dumps(summary_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        summary_path.write_bytes(summary_bytes)
        return summary_obj
    finally:
        socket.socket.connect = orig_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = orig_connect_ex  # type: ignore[method-assign]
        socket.create_connection = orig_create_conn  # type: ignore[assignment]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Execute one-shot W07 STUB-01..05 read-only corpus preflight under OWNER_CHAT_READONLY_V1."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--annex-v022", type=Path, required=True)
    parser.add_argument("--tech-freeze-receipt", type=Path, required=True)
    parser.add_argument("--policy-receipt", type=Path, required=True)
    parser.add_argument("--chat-auth-waiver", type=Path, required=True)
    parser.add_argument("--original-exec-decision", type=Path, default=None)
    parser.add_argument("--bundle-manifest", type=Path, required=True)
    parser.add_argument(
        "--auth-mode",
        choices=["OWNER_CHAT_READONLY_V1", "ED25519_SIGNED_V1"],
        default="OWNER_CHAT_READONLY_V1",
    )
    parser.add_argument("--snapshot-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    summary = run_one_shot_stub01_05_preflight(
        output_dir=args.output_dir,
        annex_v0_2_2_path=args.annex_v022,
        tech_freeze_receipt_path=args.tech_freeze_receipt,
        stub_auth_receipt_path=args.policy_receipt,
        corpus_bundle_manifest_path=args.bundle_manifest,
        auth_mode=args.auth_mode,
        chat_auth_waiver_path=args.chat_auth_waiver,
        original_exec_decision_path=args.original_exec_decision,
        snapshot_dir=args.snapshot_dir,
    )
    sys.stdout.write(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return 0 if summary["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
