from pydantic import BaseModel, Field
from typing import List, Optional


class TripContextRequest(BaseModel):
    request_id: Optional[str] = None
    trip_id: Optional[str] = None
    destination: str
    days: int = Field(ge=1, le=14, description="Duration in days, between 1 and 14")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[int] = Field(default=None, ge=0)
    currency: str = "VND"
    travel_style: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    existing_itinerary_count: int = 0
    notes: Optional[str] = None


# Backward-compatible alias for existing test/proxy callers
class PlanRequest(BaseModel):
    request_id: Optional[str] = None
    destination: str
    days: int = 3
    budget: Optional[float] = None
    style: Optional[str] = "mixed"
    interests: List[str] = Field(default_factory=list)
    start_date: Optional[str] = None


class ScheduleViolation(BaseModel):
    code: str
    reason_code: str
    day_number: int
    order_index: int
    conflicting_order_index: Optional[int] = None
    activity: str
    place_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    message: str


class ItineraryItem(BaseModel):
    order_index: int = 1
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    activity: str
    place_id: Optional[str] = None
    place_name: Optional[str] = None
    notes: Optional[str] = None
    estimated_cost: Optional[int] = None
    cost_status: str = "UNKNOWN"
    transport_mode: Optional[str] = None
    violations: List[ScheduleViolation] = Field(default_factory=list)


class ItineraryDay(BaseModel):
    day_number: int
    date: Optional[str] = None
    title: str
    items: List[ItineraryItem] = Field(default_factory=list)
    day_cost: int = 0
    unknown_cost_item_count: int = 0


class BudgetAnalysis(BaseModel):
    total_budget: Optional[int] = None
    estimated_cost: int = 0
    known_cost_total: int = 0
    unknown_cost_item_count: int = 0
    cost_status: str = "COMPLETE"
    has_sufficient_budget_basis: bool = False
    currency: str = "VND"
    is_over_budget: bool = False
    variance: Optional[int] = None


class PlannerModelAttemptTelemetry(BaseModel):
    attempt: int
    started_offset_ms: float
    duration_ms: float
    status: str
    error_code: Optional[str] = None


class PlannerTimingTelemetry(BaseModel):
    request_id: str
    fastapi_total_ms: float
    rag_retrieval_ms: float = 0.0
    model_attempts: List[PlannerModelAttemptTelemetry] = Field(default_factory=list)
    model_total_ms: float = 0.0
    retry_count: int = 0
    retry_wait_ms: float = 0.0
    post_ai_schedule_validation_ms: float = 0.0


class PlanResponse(BaseModel):
    plan_id: str
    destination: str
    total_days: int
    overview: str
    best_time_to_visit: str
    general_tips: List[str] = Field(default_factory=list)
    budget_analysis: BudgetAnalysis
    schedule_violations: List[ScheduleViolation] = Field(default_factory=list)
    has_schedule_violations: bool = False
    timing_telemetry: Optional[PlannerTimingTelemetry] = None
    days: List[ItineraryDay] = Field(default_factory=list)
