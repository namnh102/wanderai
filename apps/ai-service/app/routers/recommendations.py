"""FastAPI Router for Place Recommendations (REC-A)."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from recommendation.reca.engine import get_place_recommender

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


class PlaceRecommendationRequest(BaseModel):
    preferences: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User travel preference object containing 'interests', 'travelStyle', etc.",
        json_schema_extra={"example": {"interests": ["food_cuisine", "culture_history"]}},
    )
    destination: Optional[str] = Field(
        default=None,
        description="Optional destination filter (e.g. 'ha-noi', 'da-nang', 'ha-long')",
        json_schema_extra={"example": "da-nang"},
    )
    top_k: int = Field(default=10, ge=1, le=50, description="Number of recommendations to return")
    model: str = Field(
        default="rec-a1",
        description="Algorithm baseline to use ('rec-a1' for cosine, 'rec-a0' for taxonomy overlap)",
        json_schema_extra={"example": "rec-a1"},
    )


class ExplanationDto(BaseModel):
    reason_code: str
    matched_interests: List[str]
    matched_taxonomy: List[str]
    text: str


class RecommendedPlaceDto(BaseModel):
    place_id: str
    name: str
    destination: str
    destination_slug: str
    category: str
    score: float
    rank: int
    matched_interests: List[str]
    explanation: ExplanationDto
    strategy: str


class MetadataDto(BaseModel):
    algorithm: str
    model: str
    destination_filter: Optional[str]
    total_candidates: int
    returned_count: int
    cold_start: bool


class UnsupportedFeatureDto(BaseModel):
    feature: str
    status: str
    reason: str


class PlaceRecommendationResponse(BaseModel):
    recommendations: List[RecommendedPlaceDto]
    metadata: MetadataDto
    unsupported_user_features: List[UnsupportedFeatureDto]


@router.post("/places", response_model=PlaceRecommendationResponse)
async def recommend_places(request: PlaceRecommendationRequest):
    """Generate personalized or cold-start place recommendations from REC-A-CORE-V2."""
    try:
        recommender = get_place_recommender()
        result = recommender.recommend(
            preferences=request.preferences,
            destination=request.destination,
            top_k=request.top_k,
            model=request.model,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")
