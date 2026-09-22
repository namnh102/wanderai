from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class ChatRequest(BaseModel):
    message: str
    session_id: str
    user_id: Optional[str] = None

class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any]

class ChatResponse(BaseModel):
    response: str
    tool_calls: List[ToolCall] = []
    sources: List[str] = []
