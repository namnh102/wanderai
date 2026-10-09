from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import health, chat, planner, recommendations

app = FastAPI(title="WanderAI AI Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(planner.router)
app.include_router(recommendations.router)
