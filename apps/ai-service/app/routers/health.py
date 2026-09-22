from fastapi import APIRouter
from app.config import settings

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "1.0.0",
        "llm_provider": settings.LLM_PROVIDER
    }
