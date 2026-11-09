"""Chat Router — AI chat voi Function Calling that su, fail-closed RAG/LLM va session isolation."""
from typing import Any, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.llm.gemini import LLMProviderError, SessionOwnershipError, gemini_provider
from app.security.internal_auth import InternalPrincipal, require_internal_principal
from app.services.rag import RAGService, RetrievalResult, RetrievalStatus
from app.tools.calculate_budget import CalculateBudgetTool
from app.tools.get_weather import GetWeatherTool
from app.tools.search_places import SearchPlacesTool

router = APIRouter(prefix="/chat", tags=["Chat"])

# Production toolset excludes SearchHotelsTool because no verified hotel inventory is connected.
_TOOLS = [
    GetWeatherTool(),
    SearchPlacesTool(),
    CalculateBudgetTool(),
]


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class ToolCallLog(BaseModel):
    tool: str
    args: dict
    result: Any


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tools_used: List[str] = []
    tool_calls: List[ToolCallLog] = []
    # Source URLs of the RAG documents that grounded this reply (OpenStreetMap / Wikivoyage); empty if none.
    sources: List[str] = []
    retrieval_status: RetrievalStatus = "ok"


_rag_service: Optional[RAGService] = None


async def retrieve_grounding(message: str) -> RetrievalResult:
    """Retrieve verified knowledge with explicit tri-state status (ok | empty | error)."""
    global _rag_service
    try:
        if _rag_service is None:
            _rag_service = RAGService()
        return await _rag_service.retrieve_with_status(message, top_k=4)
    except Exception as e:  # noqa: BLE001
        return RetrievalResult(
            status="error",
            context="",
            chunks=[],
            sources=[],
            error_type=type(e).__name__,
        )


def _normalize_retrieval_result(raw: Any) -> RetrievalResult:
    """Normalize either RetrievalResult or legacy (context, sources) 2-tuple from test mocks."""
    if isinstance(raw, RetrievalResult):
        return raw
    if isinstance(raw, tuple) and len(raw) == 2:
        context, sources = raw
        src_list = list(sources or [])
        ctx_str = context or ""
        status: RetrievalStatus = "ok" if (ctx_str or src_list) else "empty"
        return RetrievalResult(
            status=status,
            context=ctx_str,
            chunks=[],
            sources=src_list,
        )
    return RetrievalResult(
        status="error",
        context="",
        chunks=[],
        sources=[],
        error_type="InvalidRetrievalResultType",
    )


NO_CONTEXT_INSTRUCTION = (
    "Không có dữ liệu truy xuất cho câu hỏi này. Chỉ nêu thông tin thực tế về địa điểm nếu có kết quả tool; "
    "không bịa giờ mở cửa, giá vé hay đánh giá. Nếu thiếu, nói rõ là chưa có thông tin trong dữ liệu hiện có."
)


def build_grounded_message(message: str, context: str) -> str:
    if not context:
        return f"{NO_CONTEXT_INSTRUCTION}\n\nCâu hỏi của người dùng: {message}"
    return (
        "Dữ liệu truy xuất từ nguồn mở (OpenStreetMap, Wikivoyage). Khi nói về các địa điểm/thông tin có trong dữ liệu này, "
        "chỉ dùng đúng dữ liệu bên dưới; không bịa thêm giờ mở cửa, giá vé hay thông tin không có trong dữ liệu.\n\n"
        f"{context}\n\nCâu hỏi của người dùng: {message}"
    )


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    principal: InternalPrincipal = Depends(require_internal_principal),
):
    """Chat voi AI Wandy — yeu cau xac thuc noi bo, fail-closed khi RAG/LLM loi."""
    if request.user_id is not None and request.user_id != principal.user_id:
        raise HTTPException(
            status_code=403,
            detail="Request user_id does not match authenticated principal.",
        )

    if (
        request.session_id
        and principal.bound_session_id
        and request.session_id != principal.bound_session_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Request session_id does not match signed assertion session binding.",
        )

    session_id = request.session_id or principal.bound_session_id or str(uuid.uuid4())

    raw_grounding = await retrieve_grounding(request.message)
    grounding = _normalize_retrieval_result(raw_grounding)

    if grounding.status == "error":
        raise HTTPException(
            status_code=503,
            detail="Kho dữ liệu tri thức du lịch tạm thời không khả dụng. Vui lòng thử lại sau.",
        )

    context = grounding.context if grounding.status == "ok" else ""
    sources = list(grounding.sources) if grounding.status == "ok" else []

    try:
        result = await gemini_provider.chat_with_tools(
            message=build_grounded_message(request.message, context),
            tools=_TOOLS,
            session_id=session_id,
            user_id=principal.user_id,
        )
    except SessionOwnershipError as exc:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền truy cập phiên trò chuyện này.",
        ) from exc
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc

    reply = result["response"]
    raw_tool_calls = result.get("tool_calls", [])

    tool_logs = [
        ToolCallLog(
            tool=tc["tool"],
            args=tc.get("args", {}),
            result=tc.get("result"),
        )
        for tc in raw_tool_calls
    ]
    tools_used = [tc["tool"] for tc in raw_tool_calls]

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        tools_used=tools_used,
        tool_calls=tool_logs,
        sources=sources,
        retrieval_status=grounding.status,
    )


@router.delete("/{session_id}")
async def clear_chat(
    session_id: str,
    user_id: Optional[str] = Query(default=None),
    principal: InternalPrincipal = Depends(require_internal_principal),
):
    """Xoa lich su chat — chi cho phep chu so huu session xoa."""
    if user_id is not None and user_id != principal.user_id:
        raise HTTPException(
            status_code=403,
            detail="Query user_id does not match authenticated principal.",
        )
    if principal.bound_session_id and principal.bound_session_id != session_id:
        raise HTTPException(
            status_code=403,
            detail="Path session_id does not match signed assertion session binding.",
        )

    try:
        gemini_provider.clear_session(session_id, user_id=principal.user_id)
    except SessionOwnershipError as exc:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền xóa phiên trò chuyện này.",
        ) from exc

    return {"message": "Chat history cleared"}
