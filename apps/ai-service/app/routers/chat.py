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


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat voi AI Wandy — co kha nang goi tools that su"""

    session_id = request.session_id or str(uuid.uuid4())

    result = await gemini_provider.chat_with_tools(
        message=request.message,
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
    )


@router.delete("/{session_id}")
async def clear_chat(session_id: str):
    """Xoa lich su chat"""
    gemini_provider.clear_session(session_id)
    return {"message": "Chat history cleared"}
