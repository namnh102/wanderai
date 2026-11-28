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
        self.last_init_error: Optional[str] = None

    @property
    def is_initialized(self) -> bool:
        """Return True iff the underlying recommender model was loaded and fitted successfully."""
        return bool(
            self._is_initialized
            and self.model is not None
            and getattr(self.model, "is_fitted", False)
        )

    def initialize(self) -> bool:
        """Fit recommendation models from cached ViHoRec artifacts."""
        if self.is_initialized:
            return True
        try:
            dfs = self.loader.load_dataset()
            candidate_model = MostPopularRecommender()
            candidate_model.fit(train_df=dfs["train"], hotels_df=dfs["hotels"])
            if not candidate_model.is_fitted:
                raise ValueError("MostPopularRecommender could not be fitted from empty training split.")
            self.model = candidate_model
            self._is_initialized = True
            self.last_init_error = None
            logger.info("HotelRecommendationService initialized with MostPopularRecommender.")
            return True
        except Exception as e:
            logger.warning(f"Could not initialize HotelRecommendationService from ViHoRec data: {e}")
            self.model = None
            self._is_initialized = False
            self.last_init_error = str(e)
            return False

    def recommend_hotels(
        self,
        user_id: Optional[str] = None,
        city: Optional[str] = None,
        top_k: int = 5,
        strict: bool = False,
    ) -> List[Dict[str, Any]]:
        """Generate hotel recommendations, degrading cleanly if model initialization failed."""
        if not self.is_initialized:
            self.initialize()

        if not self.is_initialized or self.model is None:
            if strict:
                raise RuntimeError(
                    "HotelRecommendationService is not initialized: "
                    f"{self.last_init_error or 'recommender model unavailable'}"
                )
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
