"""Hotel Recommendation Service Abstraction for WanderAI."""

import logging
from typing import List, Dict, Any, Optional

from recommendation.loader import ViHoRecLoader
from recommendation.baselines.most_pop import MostPopularRecommender

logger = logging.getLogger(__name__)


class HotelRecommendationService:
    """Service abstraction providing personalized and popularity-grounded hotel recommendations."""

    def __init__(self, loader: Optional[ViHoRecLoader] = None):
        self.loader = loader or ViHoRecLoader()
        self.model: Optional[MostPopularRecommender] = None
        self._is_initialized = False

    def initialize(self):
        """Fit recommendation models from cached ViHoRec artifacts."""
        if not self._is_initialized:
            try:
                dfs = self.loader.load_dataset()
                self.model = MostPopularRecommender()
                self.model.fit(train_df=dfs["train"], hotels_df=dfs["hotels"])
                self._is_initialized = True
                logger.info("HotelRecommendationService initialized with MostPopularRecommender.")
            except Exception as e:
                logger.warning(f"Could not initialize HotelRecommendationService from ViHoRec data: {e}")
                self.model = MostPopularRecommender()
                self._is_initialized = True

    def recommend_hotels(
        self,
        user_id: Optional[str] = None,
        city: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Generate hotel recommendations."""
        if not self._is_initialized:
            self.initialize()

        if self.model is None:
            return []

        raw_recs = self.model.recommend(
            user_id=user_id,
            top_k=top_k,
            filter_city=city,
            exclude_seen=True,
        )

        results = []
        for rank, (hotel_id, score) in enumerate(raw_recs, start=1):
            meta = self.model.hotel_metadata.get(hotel_id, {})
            results.append({
                "rank": rank,
                "hotel_id": hotel_id,
                "hotel_name": meta.get("hotel_name", f"Hotel {hotel_id}"),
                "city": meta.get("city", city or "Vietnam"),
                "star_rating": meta.get("star_rating", 0.0),
                "confidence_score": round(float(score), 4),
                "strategy": "most_popular_cold_start" if not user_id else "personalized_history_filter",
            })

        return results


_GLOBAL_REC_SERVICE: Optional[HotelRecommendationService] = None

def get_recommendation_service() -> HotelRecommendationService:
    """Singleton getter for HotelRecommendationService."""
    global _GLOBAL_REC_SERVICE
    if _GLOBAL_REC_SERVICE is None:
        _GLOBAL_REC_SERVICE = HotelRecommendationService()
        _GLOBAL_REC_SERVICE.initialize()
    return _GLOBAL_REC_SERVICE
