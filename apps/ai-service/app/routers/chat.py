from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agent import TravelAgent

router = APIRouter(prefix="/ai", tags=["chat"])
agent = TravelAgent()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        response = await agent.handle_chat(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
