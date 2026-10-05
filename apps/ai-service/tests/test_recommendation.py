"""Tests for Recommendation Module: Loader, Metrics, MostPop, and Evaluator."""

import pytest
import pandas as pd
from recommendation.metrics import precision_at_k, recall_at_k, ndcg_at_k
from recommendation.baselines.most_pop import MostPopularRecommender
from recommendation.loader import ViHoRecLoader
from recommendation.evaluator import RecommendationEvaluator
from recommendation.service import HotelRecommendationService


def test_metrics_precision_recall_ndcg():
    actual = ["hotel_a", "hotel_b"]
    predicted = ["hotel_a", "hotel_c", "hotel_b", "hotel_d", "hotel_e"]

    # Precision@2: 1/2 = 0.5
    assert precision_at_k(actual, predicted, k=2) == 0.5
    # Precision@5: 2/5 = 0.4
    assert precision_at_k(actual, predicted, k=5) == 0.4

    # Recall@2: 1/2 = 0.5
    assert recall_at_k(actual, predicted, k=2) == 0.5
    # Recall@3: 2/2 = 1.0
    assert recall_at_k(actual, predicted, k=3) == 1.0

    # NDCG
    perfect_pred = ["hotel_a", "hotel_b", "hotel_c"]
    assert ndcg_at_k(actual, perfect_pred, k=2) == 1.0
    
    # Degraded prediction NDCG < 1.0
    n = ndcg_at_k(actual, predicted, k=5)
    assert 0.0 < n < 1.0


def test_most_pop_recommender():
    train_data = pd.DataFrame([
        {"user_id": "u1", "hotel_id": "h_popular", "rating": 9.0},
        {"user_id": "u2", "hotel_id": "h_popular", "rating": 9.5},
        {"user_id": "u3", "hotel_id": "h_popular", "rating": 8.5},
        {"user_id": "u1", "hotel_id": "h_mid", "rating": 8.0},
        {"user_id": "u4", "hotel_id": "h_rare", "rating": 7.0},
    ])
    hotels_data = pd.DataFrame([
        {"hotel_id": "h_popular", "name": "Grand Da Nang Hotel", "city": "Đà Nẵng", "star_rating": 5.0},
        {"hotel_id": "h_mid", "name": "Hanoi Boutique", "city": "Hà Nội", "star_rating": 4.0},
        {"hotel_id": "h_rare", "name": "Hue Homestay", "city": "Huế", "star_rating": 3.0},
    ])

    model = MostPopularRecommender()
    model.fit(train_data, hotels_data)

    # h_popular should be ranked #1
    recs = model.recommend(user_id="u5", top_k=2)  # new user
    assert len(recs) == 2
    assert recs[0][0] == "h_popular"

    # User u1 has already seen h_popular and h_mid
    recs_u1 = model.recommend(user_id="u1", top_k=2, exclude_seen=True)
    rec_ids_u1 = [h for h, _ in recs_u1]
    assert "h_popular" not in rec_ids_u1
    assert "h_mid" not in rec_ids_u1
    assert "h_rare" in rec_ids_u1

    # City filter test
    recs_danang = model.recommend(user_id="u5", filter_city="Đà Nẵng")
    assert len(recs_danang) == 1
    assert recs_danang[0][0] == "h_popular"


def test_vihorec_loader_statistics():
    loader = ViHoRecLoader()
    stats = loader.get_audit_statistics()
    
    assert stats["dataset_name"] == "ViHoRec"
    assert stats["total_interactions"] >= 17000
    assert stats["unique_users"] >= 6000
    assert stats["unique_hotels"] >= 500
    assert stats["benchmark_split"]["train_records"] > 0
    assert stats["benchmark_split"]["test_records"] > 0
    assert stats["matrix_sparsity_percent"] > 99.0


def test_hotel_recommendation_service():
    service = HotelRecommendationService()
    service.initialize()
    recs = service.recommend_hotels(city=None, top_k=3)
    assert len(recs) == 3
    for r in recs:
        assert "hotel_id" in r
        assert "hotel_name" in r
        assert "confidence_score" in r
        assert r["confidence_score"] > 0
