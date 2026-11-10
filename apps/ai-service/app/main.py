from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat, health, planner, recommendations
from app.security.internal_auth import get_cors_origins

app = FastAPI(title="WanderAI AI Service")

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
