import math
from app.tools.base import BaseTool
from typing import Dict, Any

class CalculateRouteTool(BaseTool):
    name = "calculate_route"
    description = "Calculates distance and time between coordinates using haversine formula"
    parameters = {
        "type": "object",
        "properties": {
            "lat1": {"type": "number"},
            "lon1": {"type": "number"},
            "lat2": {"type": "number"},
            "lon2": {"type": "number"}
        },
        "required": ["lat1", "lon1", "lat2", "lon2"]
    }

    async def execute(self, params: Dict[str, Any]) -> dict:
        lat1 = params.get("lat1")
        lon1 = params.get("lon1")
        lat2 = params.get("lat2")
        lon2 = params.get("lon2")
        
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2) * math.sin(dlat/2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dlon/2) * math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        
        # Assuming average speed of 50 km/h
        time_hours = distance / 50
        
        return {
            "distance_km": round(distance, 2),
            "estimated_time_hours": round(time_hours, 2)
        }
