from fastapi import APIRouter, HTTPException
from app.schemas.planner import PlanRequest, PlanResponse
from app.services.agent import TravelAgent

router = APIRouter(prefix="/ai", tags=["planner"])
agent = TravelAgent()

@router.post("/plan", response_model=PlanResponse)
async def plan_endpoint(request: PlanRequest):
    try:
        response = await agent.handle_plan(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
