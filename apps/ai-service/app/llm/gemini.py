"""Gemini LLM Provider — Function Calling chuan voi fail-closed errors va session isolation."""
import asyncio
from dataclasses import dataclass, field
import json
import threading
import time
from typing import Any, List, Optional

from google import genai
from google.genai import types

from app.config import settings
from app.prompts.system_prompt import SYSTEM_PROMPT

_client = genai.Client(api_key=settings.GEMINI_API_KEY)
_MODEL = "gemini-3.5-flash"

# Architectural note: In-memory session storage is single-process only.
SESSION_STORAGE_LIMITATION = (
    "IN_MEMORY_SINGLE_PROCESS_ONLY__NOT_READY_FOR_MULTI_INSTANCE_PRODUCTION"
)
MAX_ACTIVE_SESSIONS = 500
DEFAULT_SESSION_TTL_SECONDS = 3600
MAX_HISTORY_ITEMS = 40


class SessionOwnershipError(Exception):
    """Raised when a caller attempts to access or delete a chat session owned by another user."""


class LLMProviderError(Exception):
    """Typed fail-closed upstream LLM provider error."""

    def __init__(self, status_code: int, error_code: str, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail


@dataclass
class _SessionRecord:
    owner_user_id: str
    history: List[Any] = field(default_factory=list)
    updated_at: float = field(default_factory=time.monotonic)


def _tool_to_function_declaration(tool) -> types.FunctionDeclaration:
    """Chuyen BaseTool sang Gemini FunctionDeclaration"""
    props = {}
    for k, v in tool.parameters.get("properties", {}).items():
        schema_kwargs = {
            "type": _map_type(v.get("type", "string")),
        }
        if v.get("description"):
            schema_kwargs["description"] = v["description"]
        if v.get("enum"):
            schema_kwargs["enum"] = v["enum"]
        props[k] = types.Schema(**schema_kwargs)

    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties=props,
            required=tool.parameters.get("required", []),
        ),
    )


def _map_type(t: str) -> types.Type:
    return {
        "string": types.Type.STRING,
        "integer": types.Type.INTEGER,
        "number": types.Type.NUMBER,
        "boolean": types.Type.BOOLEAN,
        "array": types.Type.ARRAY,
        "object": types.Type.OBJECT,
    }.get(t, types.Type.STRING)


def _sanitize_tool_result_for_llm(tool_name: str, result: Any) -> Any:
    """Prevent synthetic or unverified tool outputs from being fed to the model as grounded facts."""
    if not isinstance(result, dict):
        return result
    if result.get("synthetic") is True or result.get("verified") is False:
        return {
            "status": result.get("status", "UNVERIFIED_TOOL_OUTPUT"),
            "verified": False,
            "tool": tool_name,
            "error": result.get(
                "error",
                "Tool output is unverified or unavailable; do not invent facts, prices, ratings, or listings.",
            ),
        }
    return result


class GeminiProvider:
    """Goi Gemini API voi Function Calling, fail-closed error mapping va session isolation."""

    storage_limitation: str = SESSION_STORAGE_LIMITATION

    def __init__(
        self,
        max_sessions: int = MAX_ACTIVE_SESSIONS,
        session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    ):
        self._sessions: dict[str, _SessionRecord] = {}
        self._lock = threading.RLock()
        self._max_sessions = max_sessions
        self._session_ttl_seconds = session_ttl_seconds

    def _evict_expired_and_overflow_locked(self, now: Optional[float] = None) -> None:
        current = now if now is not None else time.monotonic()
        expired_keys = [
            sid
            for sid, rec in self._sessions.items()
            if (current - rec.updated_at) > self._session_ttl_seconds
        ]
        for sid in expired_keys:
            self._sessions.pop(sid, None)

        while len(self._sessions) > self._max_sessions:
            oldest_sid = min(
                self._sessions.keys(),
                key=lambda k: self._sessions[k].updated_at,
            )
            self._sessions.pop(oldest_sid, None)

    def _authorize_and_snapshot_history(
        self,
        session_id: str,
        user_id: Optional[str],
    ) -> List[Any]:
        normalized_owner = (user_id or "").strip() or "__anonymous__"
        now = time.monotonic()
        with self._lock:
            self._evict_expired_and_overflow_locked(now)
            record = self._sessions.get(session_id)
            if record is not None:
                if record.owner_user_id != normalized_owner:
                    raise SessionOwnershipError(
                        "Session belongs to a different authenticated user."
                    )
                record.updated_at = now
                return list(record.history)
            return []

    def _commit_turn(
        self,
        session_id: str,
        user_id: Optional[str],
        user_content: Any,
        model_content: Any,
    ) -> None:
        normalized_owner = (user_id or "").strip() or "__anonymous__"
        now = time.monotonic()
        with self._lock:
            self._evict_expired_and_overflow_locked(now)
            record = self._sessions.get(session_id)
            if record is None:
                record = _SessionRecord(
                    owner_user_id=normalized_owner,
                    history=[],
                    updated_at=now,
                )
                self._sessions[session_id] = record
            elif record.owner_user_id != normalized_owner:
                raise SessionOwnershipError(
                    "Session belongs to a different authenticated user."
                )

            record.history.append(user_content)
            record.history.append(model_content)
            if len(record.history) > MAX_HISTORY_ITEMS:
                record.history = record.history[-MAX_HISTORY_ITEMS:]
            record.updated_at = now
            self._evict_expired_and_overflow_locked(now)

    async def chat(
        self,
        message: str,
        session_id: str = "default",
        user_id: Optional[str] = None,
    ) -> str:
        result = await self.chat_with_tools(
            message,
            tools=[],
            session_id=session_id,
            user_id=user_id,
        )
        return result["response"]

    async def chat_with_tools(
        self,
        message: str,
        tools: list,
        session_id: str = "default",
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Chat voi Gemini + Function Calling.
        Returns: {"response": str, "tool_calls": list[dict]}
        Raises:
            SessionOwnershipError: when session_id belongs to another user.
            LLMProviderError: when Gemini fails, times out, hits quota, or returns empty text.
        """
        # Ownership check is performed outside the provider try/except block
        history_snapshot = self._authorize_and_snapshot_history(session_id, user_id)

        try:
            gemini_tools = None
            tool_map = {}
            if tools:
                declarations = [_tool_to_function_declaration(t) for t in tools]
                gemini_tools = [types.Tool(function_declarations=declarations)]
                tool_map = {t.name: t for t in tools}

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
                max_output_tokens=4096,
                tools=gemini_tools or [],
            )

            user_turn = types.Content(role="user", parts=[types.Part(text=message)])
            contents = list(history_snapshot) + [user_turn]

            tool_calls_log = []
            response = None

            # Vong lap Agent: toi da 5 buoc
            for _iteration in range(5):
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda c=contents, cfg=config: _client.models.generate_content(
                        model=_MODEL,
                        contents=c,
                        config=cfg,
                    ),
                )

                if not response or not response.candidates:
                    break

                candidate = response.candidates[0]
                if not candidate.content or not candidate.content.parts:
                    break

                fn_calls_in_response = []
                for part in candidate.content.parts:
                    if part.function_call:
                        fn_calls_in_response.append(part.function_call)

                if not fn_calls_in_response:
                    break

                fn_response_parts = []
                for fn in fn_calls_in_response:
                    tool_name = fn.name
                    tool_args = dict(fn.args) if fn.args else {}

                    tool_log = {"tool": tool_name, "args": tool_args, "result": None}

                    if tool_name in tool_map:
                        try:
                            raw_result = await tool_map[tool_name].execute(tool_args)
                            result = _sanitize_tool_result_for_llm(tool_name, raw_result)
                            tool_log["result"] = result
                        except Exception as e:
                            result = {
                                "status": "TOOL_EXECUTION_ERROR",
                                "verified": False,
                                "error": f"Tool {tool_name} failed ({type(e).__name__}).",
                            }
                            tool_log["result"] = result
                    else:
                        result = {
                            "status": "TOOL_NOT_FOUND",
                            "verified": False,
                            "error": f"Tool {tool_name} not found",
                        }
                        tool_log["result"] = result

                    tool_calls_log.append(tool_log)

                    fn_response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=tool_name,
                                response={
                                    "result": json.dumps(
                                        result, ensure_ascii=False, default=str
                                    )
                                },
                            )
                        )
                    )

                contents.append(candidate.content)
                contents.append(types.Content(role="user", parts=fn_response_parts))

            final_text = ""
            if response and response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts or []:
                    if part.text:
                        final_text += part.text

            final_text = final_text.strip()
            if not final_text:
                raise LLMProviderError(
                    status_code=502,
                    error_code="EMPTY_MODEL_RESPONSE",
                    detail="Dịch vụ AI không trả về nội dung hợp lệ. Vui lòng thử lại sau.",
                )

            model_turn = types.Content(
                role="model", parts=[types.Part(text=final_text)]
            )
            self._commit_turn(session_id, user_id, user_turn, model_turn)

            return {
                "response": final_text,
                "tool_calls": tool_calls_log,
            }

        except (SessionOwnershipError, LLMProviderError):
            raise
        except Exception as e:
            msg = str(e).upper()
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg or "QUOTA" in msg:
                raise LLMProviderError(
                    status_code=429,
                    error_code="RATE_LIMITED",
                    detail="Hệ thống AI đang quá tải yêu cầu (429). Vui lòng đợi một lát rồi thử lại.",
                ) from e
            if (
                "503" in msg
                or "UNAVAILABLE" in msg
                or "DEADLINE_EXCEEDED" in msg
                or "TIMEOUT" in msg
                or isinstance(e, TimeoutError)
            ):
                raise LLMProviderError(
                    status_code=503,
                    error_code="PROVIDER_UNAVAILABLE",
                    detail="Dịch vụ AI tạm thời không khả dụng (503). Vui lòng thử lại sau.",
                ) from e
            raise LLMProviderError(
                status_code=502,
                error_code="PROVIDER_ERROR",
                detail="Dịch vụ AI gặp sự cố khi xử lý yêu cầu. Vui lòng thử lại sau.",
            ) from e

    def clear_session(self, session_id: str, user_id: Optional[str] = None) -> None:
        normalized_owner = (user_id or "").strip()
        if not normalized_owner:
            raise SessionOwnershipError(
                "Authenticated user_id is required to clear a chat session."
            )
        now = time.monotonic()
        with self._lock:
            self._evict_expired_and_overflow_locked(now)
            record = self._sessions.get(session_id)
            if record is None:
                return
            if record.owner_user_id != normalized_owner:
                raise SessionOwnershipError(
                    "Session belongs to a different authenticated user."
                )
            self._sessions.pop(session_id, None)


# Singleton
gemini_provider = GeminiProvider()
