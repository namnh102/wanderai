"""Read-only zero-generation HTTPS probe client implementing LivePreflightProbeClientProtocol.

Strictly implements ONLY model snapshot inspection (GET /v1/models) and token counting
(POST /v1/responses/input_tokens for OpenAI; POST /v1/messages/count_tokens for Anthropic).
Does NOT define ``submit_batch`` and sets ``can_submit_billable_batches = False`` so no
billable batch submission can ever occur through this client.
Uses Python stdlib HTTP/TLS only so ``assert_g4_package_zero_ml_imports()`` remains clean.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from w07_g4_scorer.contracts import sha256_bytes
from w07_g4_scorer.route2_aiproxy import assert_cloud_payload_v_boundary
from w07_g4_scorer.route2_secret_vault import redact_secret_text, resolve_provider_secret

OPENAI_API_BASE = "https://api.openai.com"
ANTHROPIC_API_BASE = "https://api.anthropic.com"
ANTHROPIC_API_VERSION = "2026-10-21"


def _default_urlopen(req: urllib.request.Request, *, timeout: float) -> tuple[int, dict[str, str], bytes]:
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = int(getattr(resp, "status", 200))
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return status, hdrs, resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        hdrs = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
        return int(exc.code), hdrs, body


def _safe_header_summary(headers: Mapping[str, str]) -> dict[str, str]:
    """Capture only benign operational headers (request-id, org/rate metadata); never auth headers."""
    allow_prefixes = ("x-request-id", "request-id", "anthropic-ratelimit-", "x-ratelimit-", "openai-processing-ms")
    return {
        k: v
        for k, v in sorted(headers.items())
        if any(k == p or k.startswith(p) for p in allow_prefixes)
    }


class Route2LivePreflightProbeClient:
    """Strict read-only zero-generation provider probe implementing LivePreflightProbeClientProtocol."""

    can_submit_billable_batches: bool = False

    def __init__(
        self,
        *,
        secret_resolver: Callable[[str], str] | None = None,
        url_opener: Callable[[urllib.request.Request, float], tuple[int, dict[str, str], bytes]] | None = None,
        timeout_seconds: float = 30.0,
        anthropic_version: str = ANTHROPIC_API_VERSION,
        openai_base_url: str = OPENAI_API_BASE,
        anthropic_base_url: str = ANTHROPIC_API_BASE,
    ) -> None:
        self._secret_resolver = secret_resolver or (lambda prov: resolve_provider_secret(prov))
        self._url_opener = url_opener or (lambda req, to: _default_urlopen(req, timeout=to))
        self._timeout_seconds = float(timeout_seconds)
        self._anthropic_version = str(anthropic_version)
        self._openai_base_url = openai_base_url.rstrip("/")
        self._anthropic_base_url = anthropic_base_url.rstrip("/")

    def _request_json(
        self,
        *,
        provider: str,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None = None,
    ) -> tuple[int, dict[str, str], dict[str, Any], str]:
        secret = self._secret_resolver(provider)
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "gomate-w07-route2-preflight/1.0",
        }
        if provider == "openai":
            headers["Authorization"] = f"Bearer {secret}"
        elif provider == "anthropic":
            headers["x-api-key"] = secret
            headers["anthropic-version"] = self._anthropic_version
        else:
            raise ValueError(f"UNSUPPORTED_PROBE_PROVIDER:{provider!r}")

        data_bytes: bytes | None = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data_bytes = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        req = urllib.request.Request(url=url, data=data_bytes, headers=headers, method=method.upper())
        try:
            status, resp_headers, raw_body = self._url_opener(req, self._timeout_seconds)
        except Exception as exc:
            clean_msg = redact_secret_text(str(exc), (secret,))
            raise RuntimeError(f"PREFLIGHT_HTTP_TRANSPORT_ERROR:{provider}:{type(exc).__name__}:{clean_msg}") from None

        raw_sha = sha256_bytes(raw_body)
        try:
            decoded = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            decoded = {"raw_text_preview": redact_secret_text(raw_body[:400].decode("utf-8", errors="replace"), (secret,))}
        if not isinstance(decoded, dict):
            decoded = {"value": decoded}
        return status, resp_headers, decoded, raw_sha

    def probe_model_snapshot(self, *, provider: str, model_id: str) -> dict[str, Any]:
        """Execute zero-generation GET /v1/models/{model_id} (fallback list) and verify exact snapshot echo."""
        encoded_id = urllib.parse.quote(model_id, safe="")
        if provider == "openai":
            url_one = f"{self._openai_base_url}/v1/models/{encoded_id}"
            url_list = f"{self._openai_base_url}/v1/models"
        elif provider == "anthropic":
            url_one = f"{self._anthropic_base_url}/v1/models/{encoded_id}"
            url_list = f"{self._anthropic_base_url}/v1/models?limit=100"
        else:
            raise ValueError(f"UNSUPPORTED_PROBE_PROVIDER:{provider!r}")

        status, hdrs, body, raw_sha = self._request_json(provider=provider, method="GET", url=url_one)
        if status == 200 and isinstance(body.get("id"), str):
            out: dict[str, Any] = {
                "accessible": True,
                "provider": provider,
                "requested_model_id": model_id,
                "model_snapshot_id": str(body["id"]),
                "endpoint": f"GET /v1/models/{model_id}",
                "http_status": status,
                "raw_response_sha256": raw_sha,
                "safe_headers": _safe_header_summary(hdrs),
            }
            for k in ("created", "created_at", "owned_by", "display_name", "max_input_tokens", "max_tokens", "type"):
                if k in body:
                    out[k] = body[k]
            return out

        if status in (401, 403):
            raise PermissionError(f"PREFLIGHT_AUTH_DENIED:{provider}:{model_id}:http={status}")

        # Fallback: inspect model catalog list if single retrieve endpoint rejected alias / returned 404.
        st_list, hdrs_list, body_list, raw_list_sha = self._request_json(
            provider=provider,
            method="GET",
            url=url_list,
        )
        if st_list != 200:
            err_msg = body.get("error", {}) if isinstance(body, Mapping) else {}
            raise RuntimeError(
                f"PREFLIGHT_MODEL_PROBE_FAILED:{provider}:{model_id}:single_http={status}:list_http={st_list}:detail={err_msg!r}"
            )
        rows = body_list.get("data", [])
        match = next((r for r in rows if isinstance(r, Mapping) and str(r.get("id")) == model_id), None)
        if match is None:
            return {
                "accessible": False,
                "provider": provider,
                "requested_model_id": model_id,
                "model_snapshot_id": "",
                "endpoint": "GET /v1/models",
                "http_status": st_list,
                "raw_response_sha256": raw_list_sha,
                "catalog_count": len(rows) if isinstance(rows, list) else 0,
            }
        out = {
            "accessible": True,
            "provider": provider,
            "requested_model_id": model_id,
            "model_snapshot_id": str(match["id"]),
            "endpoint": "GET /v1/models",
            "http_status": st_list,
            "raw_response_sha256": raw_list_sha,
            "safe_headers": _safe_header_summary(hdrs_list),
        }
        for k in ("created", "created_at", "owned_by", "display_name", "max_input_tokens", "max_tokens", "type"):
            if k in match:
                out[k] = match[k]
        return out

    def probe_input_tokens(self, *, provider: str, wire_request: Mapping[str, Any]) -> dict[str, Any]:
        """Execute zero-generation token counting endpoint after re-verifying S/V boundary."""
        assert_cloud_payload_v_boundary(wire_request)
        if provider == "openai":
            url = f"{self._openai_base_url}/v1/responses/input_tokens"
            body_payload = {
                "model": wire_request["model"],
                "input": wire_request["input"],
                "text": wire_request["text"],
            }
            status, hdrs, body, raw_sha = self._request_json(
                provider="openai",
                method="POST",
                url=url,
                payload=body_payload,
            )
            if status != 200 or type(body.get("input_tokens")) is not int:
                raise RuntimeError(f"OPENAI_INPUT_TOKENS_FAILED:http={status}:body={body!r}")
            return {
                "provider": "openai",
                "endpoint": "POST /v1/responses/input_tokens",
                "http_status": status,
                "input_tokens": int(body["input_tokens"]),
                "raw_response_sha256": raw_sha,
                "safe_headers": _safe_header_summary(hdrs),
            }

        if provider == "anthropic":
            url = f"{self._anthropic_base_url}/v1/messages/count_tokens"
            primary_payload = {
                "model": wire_request["model"],
                "system": wire_request["system"],
                "messages": wire_request["messages"],
            }
            if "output_config" in wire_request:
                primary_payload["output_config"] = wire_request["output_config"]

            used_mode = "WITH_OUTPUT_CONFIG"
            status, hdrs, body, raw_sha = self._request_json(
                provider="anthropic",
                method="POST",
                url=url,
                payload=primary_payload,
            )
            if status == 400 and "output_config" in primary_payload:
                fallback_payload = {
                    "model": wire_request["model"],
                    "system": wire_request["system"],
                    "messages": wire_request["messages"],
                }
                used_mode = "WITHOUT_OUTPUT_CONFIG_FALLBACK"
                status, hdrs, body, raw_sha = self._request_json(
                    provider="anthropic",
                    method="POST",
                    url=url,
                    payload=fallback_payload,
                )
            if status != 200 or type(body.get("input_tokens")) is not int:
                raise RuntimeError(f"ANTHROPIC_COUNT_TOKENS_FAILED:http={status}:body={body!r}")
            return {
                "provider": "anthropic",
                "endpoint": "POST /v1/messages/count_tokens",
                "payload_mode": used_mode,
                "http_status": status,
                "input_tokens": int(body["input_tokens"]),
                "raw_response_sha256": raw_sha,
                "safe_headers": _safe_header_summary(hdrs),
            }

        raise ValueError(f"UNSUPPORTED_PROBE_PROVIDER:{provider!r}")
