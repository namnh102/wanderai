"""Chat Router — API endpoint cho AI chat"""
import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.llm.gemini import gemini_provider

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tools_used: list[str] = []


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat với AI Wandy — trả lời câu hỏi du lịch Việt Nam"""

    # Tạo session_id mới nếu chưa có
    session_id = request.session_id or str(uuid.uuid4())

    # Gọi Gemini
    reply = await gemini_provider.chat(request.message, session_id)

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        tools_used=[],
    )


@router.delete("/{session_id}")
async def clear_chat(session_id: str):
    """Xóa lịch sử chat"""
    gemini_provider.clear_session(session_id)
    return {"message": "Chat history cleared"}
