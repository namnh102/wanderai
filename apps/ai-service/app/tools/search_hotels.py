from typing import Any, Dict

from app.tools.base import BaseTool


class SearchHotelsTool(BaseTool):
    name = "search_hotels"
    description = "Queries database for hotel options by budget range (currently unavailable: no verified inventory connected)"
    parameters = {
        "type": "object",
        "properties": {
            "destination": {"type": "string"},
            "min_budget": {"type": "number"},
            "max_budget": {"type": "number"},
        },
        "required": ["destination", "max_budget"],
    }

    async def execute(self, params: Dict[str, Any]) -> dict:
        dest = params.get("destination", "")
        return {
            "status": "UNVERIFIED_INVENTORY_UNAVAILABLE",
            "verified": False,
            "synthetic": True,
            "destination": dest,
            "hotels": [],
            "error": (
                "No verified hotel inventory source is connected; "
                "do not present hotel listings, prices, or ratings."
            ),
        }
