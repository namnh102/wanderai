"""AI Trip Planner — Tao lich trinh du lich tu dong bang Gemini"""
import uuid
import json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from google import genai
from google.genai import types
from app.config import settings

router = APIRouter(prefix="/planner", tags=["Trip Planner"])

_client = genai.Client(api_key=settings.GEMINI_API_KEY)
_MODEL = "gemini-3.6-flash"


class PlanRequest(BaseModel):
    destination: str                  # "Đà Nẵng"
    days: int                         # 3
    budget: Optional[int] = None      # 3000000 (VND)
    style: Optional[str] = "mixed"   # "adventure" | "relaxed" | "family" | "couple" | "mixed"
    interests: Optional[List[str]] = []  # ["beach", "food", "culture", "mountain", "shopping"]
    start_date: Optional[str] = None  # "2024-04-01"


class Activity(BaseModel):
    time: str         # "07:00"
    name: str         # "Chùa Linh Ứng"
    type: str         # "attraction" | "food" | "transport" | "accommodation" | "shopping"
    address: str      # "Bán đảo Sơn Trà, Đà Nẵng"
    duration: str     # "2 tiếng"
    cost: int         # 0 (VND)
    tip: str          # "Nên đến sớm trước 8h để tránh đông"


class DayPlan(BaseModel):
    day: int
    title: str
    activities: List[Activity]
    day_total_cost: int


class PlanResponse(BaseModel):
    plan_id: str
    destination: str
    days: int
    total_cost_min: int
    total_cost_max: int
    overview: str
    itinerary: List[DayPlan]
    general_tips: List[str]
    best_time_to_visit: str


def _build_planner_prompt(req: PlanRequest) -> str:
    style_map = {
        "adventure": "phượt/khám phá/mạo hiểm",
        "relaxed": "nghỉ dưỡng/thư giãn",
        "family": "gia đình có trẻ em",
        "couple": "cặp đôi/lãng mạn",
        "mixed": "kết hợp đa dạng"
    }
    interest_map = {
        "beach": "biển và bãi tắm",
        "food": "ẩm thực địa phương",
        "culture": "văn hóa và lịch sử",
        "mountain": "núi và thiên nhiên",
        "shopping": "mua sắm và chợ"
    }

    style_str = style_map.get(req.style, "kết hợp đa dạng")
    interest_str = ", ".join([interest_map.get(i, i) for i in req.interests]) if req.interests else "đa dạng"
    budget_str = f"{req.budget:,} VND" if req.budget else "không giới hạn"

    return f"""Bạn là chuyên gia du lịch Việt Nam. Hãy tạo lịch trình chi tiết cho chuyến đi sau:

THÔNG TIN CHUYẾN ĐI:
- Điểm đến: {req.destination}
- Số ngày: {req.days} ngày
- Ngân sách: {budget_str}
- Phong cách: {style_str}
- Sở thích: {interest_str}

YÊU CẦU OUTPUT: Trả về JSON hợp lệ với cấu trúc sau (KHÔNG có markdown, KHÔNG có ```json):
{{
  "overview": "Mô tả tổng quan chuyến đi 2-3 câu",
  "total_cost_min": 2000000,
  "total_cost_max": 4000000,
  "best_time_to_visit": "Tháng 3-8 là tốt nhất",
  "general_tips": [
    "Tip thực tế 1",
    "Tip thực tế 2",
    "Tip thực tế 3"
  ],
  "itinerary": [
    {{
      "day": 1,
      "title": "Ngày 1: Tên chủ đề ngày",
      "day_total_cost": 500000,
      "activities": [
        {{
          "time": "07:00",
          "name": "Tên địa điểm/hoạt động",
          "type": "attraction",
          "address": "Địa chỉ cụ thể",
          "duration": "2 tiếng",
          "cost": 0,
          "tip": "Mẹo thực tế cho hoạt động này"
        }}
      ]
    }}
  ]
}}

QUY TẮC:
- Mỗi ngày có 5-7 hoạt động (sáng/trưa/chiều/tối)
- Chi phí (cost) phải là số nguyên VND thực tế
- type phải là một trong: attraction, food, transport, accommodation, shopping
- address phải là địa chỉ thực tế ở Việt Nam
- tip phải hữu ích và cụ thể
- Tổng chi phí phải phù hợp với ngân sách {budget_str}
- PHẢI tạo đủ {req.days} ngày
- Chỉ trả về JSON, không có text khác"""


@router.post("", response_model=PlanResponse)
async def create_plan(req: PlanRequest):
    """Tạo lịch trình du lịch AI chi tiết theo từng ngày"""

    if req.days < 1 or req.days > 14:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Số ngày phải từ 1 đến 14")

    prompt = _build_planner_prompt(req)

    try:
        response = _client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                max_output_tokens=4096,
            ),
        )
        raw = response.text.strip()

        # Làm sạch JSON: bỏ markdown wrapper nếu có
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

        # Tìm JSON object trong response (bắt đầu từ { đầu tiên)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            raw = raw[start:end]

        # Fix trailing commas (JSON không cho phép)
        import re
        raw = re.sub(r',\s*}', '}', raw)
        raw = re.sub(r',\s*]', ']', raw)

        data = json.loads(raw)

        # Parse itinerary
        itinerary = []
        for day_data in data.get("itinerary", []):
            activities = []
            for act in day_data.get("activities", []):
                activities.append(Activity(
                    time=str(act.get("time", "09:00")),
                    name=str(act.get("name", "")),
                    type=str(act.get("type", "attraction")),
                    address=str(act.get("address", "")),
                    duration=str(act.get("duration", "1 tiếng")),
                    cost=int(act.get("cost", 0)),
                    tip=str(act.get("tip", "")),
                ))
            itinerary.append(DayPlan(
                day=int(day_data.get("day", 1)),
                title=str(day_data.get("title", f"Ngày {day_data.get('day', 1)}")),
                activities=activities,
                day_total_cost=int(day_data.get("day_total_cost", 0)),
            ))

        return PlanResponse(
            plan_id=str(uuid.uuid4()),
            destination=req.destination,
            days=req.days,
            total_cost_min=int(data.get("total_cost_min", 0)),
            total_cost_max=int(data.get("total_cost_max", 0)),
            overview=str(data.get("overview", "")),
            itinerary=itinerary,
            general_tips=list(data.get("general_tips", [])),
            best_time_to_visit=str(data.get("best_time_to_visit", "")),
        )

    except json.JSONDecodeError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"AI trả về JSON không hợp lệ: {str(e)}")
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Lỗi tạo lịch trình: {str(e)}")
