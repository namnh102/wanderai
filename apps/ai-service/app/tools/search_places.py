from app.tools.base import BaseTool
from typing import Dict, Any

class SearchPlacesTool(BaseTool):
    name = "search_places"
    description = "Queries database for places by destination and category"
    parameters = {
        "type": "object",
        "properties": {
            "destination": {"type": "string", "description": "The city or area to search in"},
            "category": {"type": "string", "description": "Type of place (e.g., historical, food, nature)"}
        },
        "required": ["destination"]
    }

    async def execute(self, params: Dict[str, Any]) -> dict:
        destination = params.get("destination")
        category = params.get("category", "all")
        return {
            "places": [
                {"name": f"Mock Place 1 in {destination}", "category": category, "rating": 4.5},
                {"name": f"Mock Place 2 in {destination}", "category": category, "rating": 4.2}
            ]
        }
