from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import health, chat, planner, recommendations

app = FastAPI(title="WanderAI AI Service")

_allowed_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
] or ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-WanderAI-Internal-Assertion"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(planner.router)
app.include_router(recommendations.router)
