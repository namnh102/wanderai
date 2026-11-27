from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, health, planner, recommendations
from app.security.internal_auth import get_cors_origins


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    prewarm_flag = os.environ.get("AI_PREWARM_RAG_ON_STARTUP", "").strip().lower()
    if prewarm_flag in ("1", "true", "yes") and "PYTEST_CURRENT_TEST" not in os.environ:
        await chat.retrieve_grounding("Hạ Long")
    yield


app = FastAPI(title="WanderAI AI Service", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-WanderAI-Internal-Assertion"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(planner.router)
app.include_router(recommendations.router)
