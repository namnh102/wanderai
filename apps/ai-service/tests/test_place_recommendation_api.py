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


# ─── W3-02: defensive boundary validation ───────────────────────────────────

@pytest.mark.parametrize(
    "alias,slug",
    [
        ("da-nang", "da-nang"),
        ("DANANG", "da-nang"),
        ("Đà Nẵng", "da-nang"),
        ("ha-noi", "ha-noi"),
        ("Hà Nội", "ha-noi"),
        ("hanoi", "ha-noi"),
        ("ha-long", "ha-long"),
        ("Hạ Long", "ha-long"),
        ("halong", "ha-long"),
    ],
)
def test_supported_destination_aliases_normalize(alias, slug):
    response = client.post(
        "/recommendations/places",
        json={"preferences": {"interests": ["food_cuisine"]}, "destination": alias, "top_k": 3},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["metadata"]["destination_filter"] == slug
    assert all(r["destination_slug"] == slug for r in data["recommendations"])


@pytest.mark.parametrize("bad", ["Paris", "quang-nam", "zzz", "da nang city"])
def test_unsupported_destination_rejected_not_widened(bad):
    response = client.post(
        "/recommendations/places",
        json={"preferences": {"interests": ["food_cuisine"]}, "destination": bad, "top_k": 3},
    )
    assert response.status_code == 422
    assert "Unsupported destination" in response.text


def test_omitted_destination_still_means_all_core_candidates():
    response = client.post(
        "/recommendations/places",
        json={"preferences": {"interests": ["food_cuisine"]}, "top_k": 3},
    )
    assert response.status_code == 200
    meta = response.json()["metadata"]
    assert meta["destination_filter"] is None
    assert meta["total_candidates"] == 622


@pytest.mark.parametrize("model", ["rec-a0", "rec-a1", "REC-A1"])
def test_supported_models_accepted(model):
    response = client.post(
        "/recommendations/places",
        json={"preferences": {"interests": ["food_cuisine"]}, "destination": "da-nang", "top_k": 3, "model": model},
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["model"] == model.lower()


@pytest.mark.parametrize("model", ["zzz", "rec-b1", ""])
def test_unsupported_model_rejected_not_defaulted(model):
    response = client.post(
        "/recommendations/places",
        json={"preferences": {"interests": ["food_cuisine"]}, "destination": "da-nang", "top_k": 3, "model": model},
    )
    assert response.status_code == 422
    assert "Unsupported model" in response.text


@pytest.mark.parametrize("top_k,expected", [(1, 200), (50, 200), (0, 422), (51, 422), (-1, 422)])
def test_top_k_boundaries_preserved(top_k, expected):
    response = client.post(
        "/recommendations/places",
        json={"preferences": {"interests": ["food_cuisine"]}, "destination": "da-nang", "top_k": top_k},
    )
    assert response.status_code == expected


def test_da_nang_candidate_universe_is_289_core_only():
    response = client.post(
        "/recommendations/places",
        json={"preferences": {"interests": ["culture_history", "food_cuisine"]}, "destination": "da-nang", "top_k": 50},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["total_candidates"] == 289
    names = {r["name"] for r in data["recommendations"]}
    assert "TASY STUDIO" not in names and "Mini-Golf Hoi An" not in names
