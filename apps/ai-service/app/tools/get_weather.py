import httpx
from app.tools.base import BaseTool
from typing import Dict, Any

class GetWeatherTool(BaseTool):
    name = "get_weather"
    description = "Calls Open-Meteo free API for weather forecast"
    parameters = {
        "type": "object",
        "properties": {
            "latitude": {"type": "number"},
            "longitude": {"type": "number"}
        },
        "required": ["latitude", "longitude"]
    }

    async def execute(self, params: Dict[str, Any]) -> dict:
        lat = params.get("latitude")
        lon = params.get("longitude")
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.json()
            return {"error": "Failed to fetch weather"}
