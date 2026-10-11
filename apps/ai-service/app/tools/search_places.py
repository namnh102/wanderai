"""Search Places Tool — Query DB that tu PostgreSQL"""
from app.tools.base import BaseTool
from app.config import settings
from typing import Dict, Any
import asyncpg


class SearchPlacesTool(BaseTool):
    name = "search_places"
    description = (
        "Tim dia diem du lich Viet Nam tu database. "
        "Dung khi nguoi dung hoi ve cac diem den, homestay, "
        "quan an, thang canh tai mot tinh/thanh pho."
    )
    parameters = {
        "type": "object",
        "properties": {
            "destination": {
                "type": "string",
                "description": "Ten tinh/thanh/dia diem (VD: Ha Giang, Da Nang, Sapa)",
            },
            "limit": {
                "type": "integer",
                "description": "So luong ket qua, mac dinh 5",
            },
        },
        "required": ["destination"],
    }

    async def execute(self, params: Dict[str, Any]) -> dict:
        destination = params.get("destination", "")
        limit = min(params.get("limit", 5), 10)

        try:
            conn = await asyncpg.connect(settings.DATABASE_URL)
            rows = await conn.fetch(
                """
                SELECT name, province, region, rating, review_count, cover_image
                FROM destinations
                WHERE deleted_at IS NULL
                  AND (
                    name ILIKE $1
                    OR province ILIKE $1
                    OR name_en ILIKE $1
                  )
                ORDER BY is_popular DESC, rating DESC
                LIMIT $2
                """,
                f"%{destination}%",
                limit,
            )
            await conn.close()

            places = [
                {
                    "name": r["name"],
                    "province": r["province"],
                    "region": r["region"],
                    "rating": float(r["rating"] or 0),
                    "review_count": r["review_count"] or 0,
                    "image": r["cover_image"] or "",
                }
                for r in rows
            ]

            return {
                "destination": destination,
                "count": len(places),
                "places": places,
            }

        except Exception as e:
            # Fallback neu DB loi
            return {
                "destination": destination,
                "count": 0,
                "places": [],
                "note": f"DB error: {str(e)[:100]}",
            }
