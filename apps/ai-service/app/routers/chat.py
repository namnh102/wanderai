"""Chat Router — AI chat voi Function Calling that su"""
import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Any
from app.llm.gemini import gemini_provider
from app.tools.get_weather import GetWeatherTool
from app.tools.search_places import SearchPlacesTool
from app.tools.calculate_budget import CalculateBudgetTool
from app.tools.search_hotels import SearchHotelsTool
from app.services.rag import RAGService

router = APIRouter(prefix="/chat", tags=["Chat"])

# Danh sach tools that - Gemini se tu quyet dinh khi nao dung
_TOOLS = [
    GetWeatherTool(),
    SearchPlacesTool(),
    CalculateBudgetTool(),
    SearchHotelsTool(),
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


_rag_service: Optional[RAGService] = None


async def retrieve_grounding(message: str):
    """Retrieve verified knowledge (production retriever: no unsourced/synthetic documents).

    Returns (context_text, source_urls). Never raises: retrieval problems degrade to an ungrounded reply.
    """
    global _rag_service
    try:
        if _rag_service is None:
            _rag_service = RAGService()
        context, chunks = await _rag_service.search_with_sources(message, top_k=4)
    except Exception:  # noqa: BLE001
        return "", []
    sources = list(dict.fromkeys(c["source_url"] for c in chunks if c.get("source_url")))
    return context, sources


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
async def chat(request: ChatRequest):
    """Chat voi AI Wandy — co kha nang goi tools that su"""

    session_id = request.session_id or str(uuid.uuid4())

    context, sources = await retrieve_grounding(request.message)

    result = await gemini_provider.chat_with_tools(
        message=build_grounded_message(request.message, context),
        tools=_TOOLS,
        session_id=session_id,
    )

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
    )


@router.delete("/{session_id}")
async def clear_chat(session_id: str):
    """Xoa lich su chat"""
    gemini_provider.clear_session(session_id)
    return {"message": "Chat history cleared"}
