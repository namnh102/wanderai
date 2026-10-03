"""AI Trip Planner — Generates structured itineraries using TripContext and Gemini."""
import uuid
import logging
import json
import re
from typing import Union
from fastapi import APIRouter, HTTPException
from google import genai
from google.genai import types

from app.config import settings
from app.prompts.planner_prompt import build_planner_prompt
from app.schemas.planner import (
    TripContextRequest,
    PlanRequest,
    PlanResponse,
    ItineraryDay,
    ItineraryItem,
    BudgetAnalysis,
)

router = APIRouter(prefix="/planner", tags=["Trip Planner"])

_client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
logger = logging.getLogger(__name__)

# Model id and output limit come from settings (PLANNER_MODEL / PLANNER_MAX_OUTPUT_TOKENS).
# Previous hardcoded value "gemini-2.0-flash" was retired by Google (404 NOT_FOUND).


def _clean_json_response(raw: str) -> str:
    """Extract clean JSON string from raw LLM output."""
    raw = raw.strip()
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break
    raw = raw.strip()

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        raw = raw[start:end]

    # Remove invalid trailing commas before closing braces/brackets
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    return raw


@router.post("", response_model=PlanResponse)
async def create_plan(req: Union[TripContextRequest, PlanRequest]):
    """Tạo lịch trình du lịch AI chi tiết theo từng ngày từ TripContext."""
    # Normalize inputs whether caller passes TripContextRequest or PlanRequest
    if isinstance(req, TripContextRequest):
        destination = req.destination
        days = req.days
        start_date = req.start_date
        end_date = req.end_date
        budget = req.budget
        currency = req.currency or "VND"
        travel_style = req.travel_style
        interests = req.interests
        notes = req.notes
        trip_id = req.trip_id
    else:
        destination = req.destination
        days = req.days
        start_date = req.start_date
        end_date = None
        budget = int(req.budget) if req.budget is not None else None
        currency = "VND"
        travel_style = req.style
        interests = req.interests
        notes = None
        trip_id = None

    if days < 1 or days > 14:
        raise HTTPException(status_code=400, detail="Số ngày chuyến đi phải từ 1 đến 14")

    prompt = build_planner_prompt(
        destination=destination,
        days=days,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        currency=currency,
        travel_style=travel_style,
        interests=interests,
        notes=notes,
    )

    try:
        raw_text = ""
        if _client:
            response = _client.models.generate_content(
                model=settings.PLANNER_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=settings.PLANNER_MAX_OUTPUT_TOKENS,
                    response_mime_type="application/json",
                    http_options=types.HttpOptions(timeout=settings.PLANNER_TIMEOUT_MS),
                ),
            )
            raw_text = response.text or ""
            finish = None
            try:
                finish = response.candidates[0].finish_reason
            except Exception:
                finish = None
            if finish is not None and "MAX_TOKENS" in str(finish):
                logger.error("Planner output truncated (MAX_TOKENS) model=%s", settings.PLANNER_MODEL)
                raise HTTPException(
                    status_code=502,
                    detail="AI tra ve ket qua khong day du. Vui long thu lai.",
                )
        else:
            # Fallback mock for testing when no Gemini key is present
            raw_text = json.dumps({
                "destination": destination,
                "total_days": days,
                "overview": f"Hành trình khám phá {destination} {days} ngày tuyệt vời.",
                "best_time_to_visit": "Quanh năm",
                "general_tips": ["Mang theo trang phục thoải mái"],
                "days": [
                    {
                        "day_number": i + 1,
                        "title": f"Ngày {i + 1}: Trải nghiệm {destination}",
                        "items": [
                            {
                                "order_index": 1,
                                "start_time": "08:30",
                                "end_time": "11:00",
                                "activity": f"Tham quan điểm nổi bật {destination}",
                                "place_name": destination,
                                "notes": "Điểm tham quan tiêu biểu",
                                "estimated_cost": 50000,
                                "transport_mode": "taxi"
                            }
                        ]
                    }
                    for i in range(days)
                ]
            })

        cleaned_json = _clean_json_response(raw_text)
        data = json.loads(cleaned_json)

        # Parse days and items with deterministic calculation
        raw_days = data.get("days", data.get("itinerary", []))
        itinerary_days: list[ItineraryDay] = []
        deterministic_total_cost = 0

        for idx, day_data in enumerate(raw_days):
            day_num = int(day_data.get("day_number", day_data.get("day", idx + 1)))
            day_title = str(day_data.get("title", f"Ngày {day_num}"))
            day_date = day_data.get("date")

            items: list[ItineraryItem] = []
            day_cost = 0

            raw_items = day_data.get("items", day_data.get("activities", []))
            for item_idx, itm in enumerate(raw_items):
                item_cost = int(itm.get("estimated_cost", itm.get("cost", 0)))
                # Guard against negative costs
                if item_cost < 0:
                    item_cost = 0

                day_cost += item_cost
                items.append(
                    ItineraryItem(
                        order_index=int(itm.get("order_index", item_idx + 1)),
                        start_time=itm.get("start_time", itm.get("time")),
                        end_time=itm.get("end_time"),
                        activity=str(itm.get("activity", itm.get("name", ""))),
                        place_name=itm.get("place_name", itm.get("address")),
                        notes=itm.get("notes", itm.get("tip")),
                        estimated_cost=item_cost,
                        transport_mode=itm.get("transport_mode", itm.get("type")),
                    )
                )

            deterministic_total_cost += day_cost
            itinerary_days.append(
                ItineraryDay(
                    day_number=day_num,
                    date=day_date,
                    title=day_title,
                    items=items,
                    day_cost=day_cost,
                )
            )

        # Budget analysis deterministically computed by code
        is_over = False
        variance = 0
        if budget is not None and budget > 0:
            is_over = deterministic_total_cost > budget
            variance = budget - deterministic_total_cost

        budget_analysis = BudgetAnalysis(
            total_budget=budget,
            estimated_cost=deterministic_total_cost,
            currency=currency,
            is_over_budget=is_over,
            variance=variance,
        )

        return PlanResponse(
            plan_id=trip_id or str(uuid.uuid4()),
            destination=destination,
            total_days=len(itinerary_days),
            overview=str(data.get("overview", f"Lịch trình khám phá {destination}")),
            best_time_to_visit=str(data.get("best_time_to_visit", "Thời điểm lý tưởng trong năm")),
            general_tips=list(data.get("general_tips", [])),
            budget_analysis=budget_analysis,
            days=itinerary_days,
        )

    except json.JSONDecodeError as e:
        logger.error("Planner returned invalid JSON: %s", e)
        raise HTTPException(
            status_code=502,
            detail="AI trả về định dạng không hợp lệ. Vui lòng thử lại.",
        )
    except HTTPException:
        raise
    except Exception as e:
        # Log details server-side only; never leak provider/stack details to the client.
        logger.exception("Planner provider/processing failure: %s", type(e).__name__)
        raise HTTPException(
            status_code=502,
            detail="Nhà cung cấp AI không phản hồi. Vui lòng thử lại sau.",
        )
