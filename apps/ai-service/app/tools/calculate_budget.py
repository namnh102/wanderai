from app.tools.base import BaseTool
from typing import Dict, Any

class CalculateBudgetTool(BaseTool):
    name = "calculate_budget"
    description = "Estimates trip cost breakdown (transport, hotel, food, activities)"
    parameters = {
        "type": "object",
        "properties": {
            "days": {"type": "integer"},
            "style": {"type": "string", "enum": ["budget", "standard", "luxury"]}
        },
        "required": ["days", "style"]
    }

    async def execute(self, params: Dict[str, Any]) -> dict:
        days = params.get("days", 1)
        style = params.get("style", "standard")
        
        multipliers = {"budget": 50, "standard": 100, "luxury": 300}
        base_daily = multipliers.get(style, 100)
        
        return {
            "total_estimated_usd": days * base_daily * 2,
            "breakdown": {
                "transport": days * (base_daily * 0.2),
                "hotel": days * (base_daily * 0.8),
                "food": days * (base_daily * 0.5),
                "activities": days * (base_daily * 0.5)
            }
        }
