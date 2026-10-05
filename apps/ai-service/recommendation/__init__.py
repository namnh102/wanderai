"""Recommendation package for WanderAI."""

from recommendation.loader import ViHoRecLoader
from recommendation.metrics import precision_at_k, recall_at_k, ndcg_at_k
from recommendation.evaluator import RecommendationEvaluator
from recommendation.service import HotelRecommendationService, get_recommendation_service
from recommendation.baselines.most_pop import MostPopularRecommender

__all__ = [
    "ViHoRecLoader",
    "precision_at_k",
    "recall_at_k",
    "ndcg_at_k",
    "RecommendationEvaluator",
    "HotelRecommendationService",
    "get_recommendation_service",
    "MostPopularRecommender",
]
