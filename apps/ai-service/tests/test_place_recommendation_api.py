"""Integration tests for Place Recommendations API in ai-service."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_personalized_recommendation_rec_a1():
    response = client.post(
        "/recommendations/places",
        json={
            "preferences": {"interests": ["culture_history", "food_cuisine"]},
            "destination": "da-nang",
            "top_k": 5,
            "model": "rec-a1",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert "recommendations" in data
    assert "metadata" in data
    assert "unsupported_user_features" in data

    recs = data["recommendations"]
    assert len(recs) == 5
    for r in recs:
        assert r["destination_slug"] == "da-nang"
        assert r["score"] > 0
        assert "explanation" in r
        assert r["explanation"]["reason_code"] == "PREFERENCE_TAXONOMY_MATCH"
        assert len(r["explanation"]["matched_interests"]) > 0

    assert data["metadata"]["model"] == "rec-a1"
    assert data["metadata"]["destination_filter"] == "da-nang"
    assert data["metadata"]["cold_start"] is False

    unsupported = data["unsupported_user_features"]
    feature_names = {u["feature"] for u in unsupported}
    assert {"budgetMin", "budgetMax", "preferredGroup", "avoidances", "dietaryNeeds"}.issubset(feature_names)


def test_personalized_recommendation_rec_a0():
    response = client.post(
        "/recommendations/places",
        json={
            "preferences": {"interests": ["coffee_culture", "beach_island"]},
            "destination": "ha-long",
            "top_k": 5,
            "model": "rec-a0",
        },
    )
    assert response.status_code == 200
    data = response.json()
    recs = data["recommendations"]
    assert len(recs) <= 5
    for r in recs:
        assert r["destination_slug"] == "ha-long"
    assert data["metadata"]["model"] == "rec-a0"


def test_cold_start_fallback_not_popularity():
    response = client.post(
        "/recommendations/places",
        json={
            "preferences": {"interests": []},
            "destination": "da-nang",
            "top_k": 5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["cold_start"] is True
    assert data["metadata"]["algorithm"] == "COLD_START_DIVERSE_CATALOG_BASELINE"

    recs = data["recommendations"]
    assert len(recs) == 5
    for r in recs:
        assert r["strategy"] == "COLD_START_DIVERSE_CATALOG_BASELINE"
        assert r["explanation"]["reason_code"] == "COLD_START_DIVERSE_FALLBACK"
        assert r["matched_interests"] == []
