from app.tools.base import BaseTool
from typing import Dict, Any

class SearchHotelsTool(BaseTool):
    name = "search_hotels"
    description = "Queries database for hotel options by budget range"
    parameters = {
        "type": "object",
        "properties": {
            "destination": {"type": "string"},
            "min_budget": {"type": "number"},
            "max_budget": {"type": "number"}
        },
        "required": ["destination", "max_budget"]
    }

    async def execute(self, params: Dict[str, Any]) -> dict:
        dest = params.get("destination")
        max_b = params.get("max_budget")
        return {
            "hotels": [
                {"name": f"Budget Inn {dest}", "price_per_night": max_b * 0.5, "rating": 3.8},
                {"name": f"Grand {dest} Hotel", "price_per_night": max_b * 0.9, "rating": 4.6}
            ]
        }
