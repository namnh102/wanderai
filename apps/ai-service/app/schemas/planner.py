from pydantic import BaseModel, Field
from typing import List, Optional


class TripContextRequest(BaseModel):
    trip_id: Optional[str] = None
    destination: str
    days: int = Field(ge=1, le=14, description="Duration in days, between 1 and 14")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[int] = Field(default=None, ge=0)
    currency: str = "VND"
    travel_style: Optional[str] = None
    interests: List[str] = []
    existing_itinerary_count: int = 0
    notes: Optional[str] = None


# Backward-compatible alias for existing test/proxy callers
class PlanRequest(BaseModel):
    destination: str
    days: int = 3
    budget: Optional[float] = None
    style: Optional[str] = "mixed"
    interests: List[str] = []
    start_date: Optional[str] = None


class ItineraryItem(BaseModel):
    order_index: int = 1
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    activity: str
    place_name: Optional[str] = None
    notes: Optional[str] = None
    estimated_cost: int = 0
    transport_mode: Optional[str] = None


class ItineraryDay(BaseModel):
    day_number: int
    date: Optional[str] = None
    title: str
    items: List[ItineraryItem] = []
    day_cost: int = 0


class BudgetAnalysis(BaseModel):
    total_budget: Optional[int] = None
    estimated_cost: int = 0
    currency: str = "VND"
    is_over_budget: bool = False
    variance: int = 0


class PlanResponse(BaseModel):
    plan_id: str
    destination: str
    total_days: int
    overview: str
    best_time_to_visit: str
    general_tips: List[str] = []
    budget_analysis: BudgetAnalysis
    days: List[ItineraryDay] = []
