"""Calculate Budget Tool — Tinh ngan sach du lich Viet Nam (VND)"""
from app.tools.base import BaseTool
from typing import Dict, Any


class CalculateBudgetTool(BaseTool):
    name = "calculate_budget"
    description = (
        "Uoc tinh ngan sach chuyen di du lich Viet Nam chi tiet theo VND. "
        "Tinh giao thong, noi o, an uong, hoat dong cho moi loai phong cach."
    )
    parameters = {
        "type": "object",
        "properties": {
            "destination": {
                "type": "string",
                "description": "Diem den du lich",
            },
            "days": {
                "type": "integer",
                "description": "So ngay du lich",
            },
            "people": {
                "type": "integer",
                "description": "So nguoi, mac dinh 1",
            },
            "style": {
                "type": "string",
                "enum": ["budget", "standard", "comfort"],
                "description": "budget=tiet kiem, standard=thuong, comfort=thoai mai",
            },
        },
        "required": ["destination", "days"],
    }

    # Chi phi trung binh 1 nguoi/ngay (VND) theo phong cach
    _COSTS = {
        "budget": {
            "transport_per_day": 80_000,   # xe may thue
            "accommodation": 150_000,       # hostel/homestay dorm
            "food_per_day": 100_000,        # com binh dan
            "activities_per_day": 50_000,
        },
        "standard": {
            "transport_per_day": 200_000,   # xe khach/grab
            "accommodation": 350_000,       # homestay private
            "food_per_day": 200_000,
            "activities_per_day": 150_000,
        },
        "comfort": {
            "transport_per_day": 500_000,   # limousine/xe rieng
            "accommodation": 800_000,       # khach san 3 sao
            "food_per_day": 400_000,
            "activities_per_day": 300_000,
        },
    }

    async def execute(self, params: Dict[str, Any]) -> dict:
        destination = params.get("destination", "")
        days = max(1, int(params.get("days", 1)))
        people = max(1, int(params.get("people", 1)))
        style = params.get("style", "standard")

        costs = self._COSTS.get(style, self._COSTS["standard"])

        transport_total = costs["transport_per_day"] * days * people
        accommodation_total = costs["accommodation"] * days  # chia phong
        food_total = costs["food_per_day"] * days * people
        activities_total = costs["activities_per_day"] * days * people

        total = transport_total + accommodation_total + food_total + activities_total

        def fmt(n: int) -> str:
            return f"{n:,}d".replace(",", ".")

        return {
            "destination": destination,
            "days": days,
            "people": people,
            "style": style,
            "total_vnd": total,
            "total_formatted": fmt(total),
            "per_person_vnd": total // people,
            "breakdown": {
                "transport": fmt(transport_total),
                "accommodation": fmt(accommodation_total),
                "food": fmt(food_total),
                "activities": fmt(activities_total),
            },
            "note": "Uoc tinh can ban, co the thay doi tuy dieu kien thuc te",
        }
