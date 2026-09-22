from app.tools.base import BaseTool
from typing import Dict, Any

class SearchReviewsTool(BaseTool):
    name = "search_reviews"
    description = "Queries database for reviews of a place"
    parameters = {
        "type": "object",
        "properties": {
            "place_name": {"type": "string"}
        },
        "required": ["place_name"]
    }

    async def execute(self, params: Dict[str, Any]) -> dict:
        place_name = params.get("place_name")
        return {
            "place": place_name,
            "average_rating": 4.5,
            "reviews": [
                {"user": "Alice", "comment": f"Loved visiting {place_name}!", "rating": 5},
                {"user": "Bob", "comment": "It was okay, a bit crowded.", "rating": 4}
            ]
        }
