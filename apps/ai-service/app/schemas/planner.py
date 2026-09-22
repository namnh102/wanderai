from pydantic import BaseModel
from typing import List, Optional

class ItineraryItem(BaseModel):
    time: str
    activity: str
    location: str
    description: str
    cost_estimate: float

class ItineraryDay(BaseModel):
    day: int
    date: str
    items: List[ItineraryItem]

class PlanRequest(BaseModel):
    destination: str
    days: int
    budget: float
    style: str
    interests: List[str] = []

class PlanResponse(BaseModel):
    destination: str
    total_days: int
    itinerary: List[ItineraryDay]
    total_budget_estimate: float
