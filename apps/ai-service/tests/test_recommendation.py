"""Tests for Recommendation Module: Loader, Metrics, MostPop, and Evaluator."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
from pathlib import Path
import re
import sys
import tempfile
import threading
import urllib.error

import pandas as pd
import pytest

from recommendation.baselines.most_pop import MostPopularRecommender
from recommendation.loader import (
    DATASET_FILES,
    EXPECTED_SHA256,
    VIHOREC_PINNED_REVISION,
    VIHOREC_UPSTREAM_REPO,
    ViHoRecLoader,
)
from recommendation.metrics import ndcg_at_k, precision_at_k, recall_at_k
from recommendation.service import HotelRecommendationService

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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
    assert model.is_fitted is True

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


def test_most_pop_recommender_unfitted_safe_handling():
    model = MostPopularRecommender()
    assert model.is_fitted is False
    assert model.ranked_items == []
    assert model.recommend(user_id="u1", top_k=5) == []

    # Empty DataFrame leaves recommender cleanly unfitted
    model.fit(pd.DataFrame())
    assert model.is_fitted is False
    assert model.recommend(user_id="u1", top_k=5) == []


def test_vihorec_pinned_source_urls_and_hashes_match_integrity_verifier():
    from scripts.verify_vihorec_integrity import EXPECTED_HASHES

    assert VIHOREC_UPSTREAM_REPO == "MinhDS/ViHoRec"
    assert re.fullmatch(r"[0-9a-f]{40}", VIHOREC_PINNED_REVISION) is not None

    expected_by_filename = {f"{name}.csv": digest for name, digest in EXPECTED_SHA256.items()}
    assert expected_by_filename == EXPECTED_HASHES

    for name, url in DATASET_FILES.items():
        assert name in EXPECTED_SHA256
        assert url.startswith(
            f"https://huggingface.co/datasets/{VIHOREC_UPSTREAM_REPO}/resolve/{VIHOREC_PINNED_REVISION}/"
        )
        assert "/Master/" not in url
        assert "/resolve/main/" not in url


def test_vihorec_loader_rejects_corrupt_download_and_cached_mismatch(tmp_path, monkeypatch):
    class _FakeResp(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=30: _FakeResp(b"corrupted,csv,content\n1,2,3\n"),
    )
    loader = ViHoRecLoader(cache_dir=str(tmp_path), max_download_attempts=1)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        loader.download_if_missing()
    assert list(tmp_path.iterdir()) == []

    # Pre-existing corrupt file in cache must also be rejected
    bad_cached = tmp_path / "interactions.csv"
    bad_cached.write_bytes(b"tampered-cached-bytes\n")
    with pytest.raises(ValueError, match="Cached ViHoRec interactions.csv SHA-256 mismatch"):
        loader.download_if_missing()


def test_vihorec_loader_concurrent_two_threads_empty_cache(tmp_path, monkeypatch):
    class _FakeResp(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()

    synthetic_payloads_by_name = {
        name: f"col_a,col_b\n{name},1\n{name},2\n".encode("utf-8")
        for name in DATASET_FILES
    }
    synthetic_hashes = {
        name: hashlib.sha256(raw).hexdigest()
        for name, raw in synthetic_payloads_by_name.items()
    }
    url_to_name = {url: name for name, url in DATASET_FILES.items()}
    barriers = {name: threading.Barrier(2, timeout=5.0) for name in DATASET_FILES}

    monkeypatch.setattr("recommendation.loader.EXPECTED_SHA256", synthetic_hashes)

    created_tmp_paths = []
    tmp_lock = threading.Lock()
    real_mkstemp = tempfile.mkstemp

    def _tracking_mkstemp(*args, **kwargs):
        fd, path = real_mkstemp(*args, **kwargs)
        with tmp_lock:
            created_tmp_paths.append(path)
        return fd, path

    monkeypatch.setattr("recommendation.loader.tempfile.mkstemp", _tracking_mkstemp)

    def _concurrent_urlopen(req, timeout=30):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        name = url_to_name[url]
        barriers[name].wait()
        return _FakeResp(synthetic_payloads_by_name[name])

    monkeypatch.setattr("urllib.request.urlopen", _concurrent_urlopen)

    def _worker():
        loader = ViHoRecLoader(cache_dir=str(tmp_path), verify_checksums=True, max_download_attempts=1)
        return loader.download_if_missing()

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(_worker)
        fut_b = pool.submit(_worker)
        paths_a = fut_a.result(timeout=10.0)
        paths_b = fut_b.result(timeout=10.0)

    assert paths_a == paths_b
    assert set(paths_a.keys()) == set(DATASET_FILES.keys())

    # Every write created a distinct temp filename inside the exact cache directory
    assert len(created_tmp_paths) == 2 * len(DATASET_FILES)
    assert len(set(created_tmp_paths)) == len(created_tmp_paths)
    assert all(Path(p).parent == tmp_path for p in created_tmp_paths)

    # Zero temporary files left behind and all 6 final CSVs match SHA-256
    remaining_files = sorted(p.name for p in tmp_path.iterdir())
    assert remaining_files == sorted(f"{name}.csv" for name in DATASET_FILES)
    for name, expected_sha in synthetic_hashes.items():
        final_csv = tmp_path / f"{name}.csv"
        actual_sha = hashlib.sha256(final_csv.read_bytes()).hexdigest()
        assert actual_sha == expected_sha


def test_hotel_recommendation_service_uninitialized_failure_and_recovery():
    class _ToggleLoader:
        def __init__(self):
            self.should_fail = True

        def load_dataset(self):
            if self.should_fail:
                raise urllib.error.HTTPError(
                    url="https://invalid.example/vihorec",
                    code=404,
                    msg="Not Found",
                    hdrs=None,
                    fp=None,
                )
            return {
                "train": pd.DataFrame([
                    {"user_id": "u1", "hotel_id": "H0001", "rating": 9.2},
                    {"user_id": "u2", "hotel_id": "H0001", "rating": 8.8},
                    {"user_id": "u3", "hotel_id": "H0002", "rating": 7.5},
                ]),
                "hotels": pd.DataFrame([
                    {"hotel_id": "H0001", "name": "Da Nang Riverside", "city": "Đà Nẵng", "star_rating": 4.0},
                    {"hotel_id": "H0002", "name": "Hanoi Old Quarter", "city": "Hà Nội", "star_rating": 3.0},
                ]),
            }

    toggle_loader = _ToggleLoader()
    service = HotelRecommendationService(loader=toggle_loader)

    assert service.initialize() is False
    assert service.is_initialized is False
    assert service.model is None
    assert service.last_init_error is not None and "404" in service.last_init_error

    # Non-strict callers receive an empty list instead of AttributeError
    assert service.recommend_hotels(city="Đà Nẵng", top_k=3) == []
    assert service.is_initialized is False

    # Strict callers receive an explicit RuntimeError
    with pytest.raises(RuntimeError, match="HotelRecommendationService is not initialized"):
        service.recommend_hotels(city="Đà Nẵng", top_k=3, strict=True)

    # Once data becomes available, subsequent calls self-heal cleanly
    toggle_loader.should_fail = False
    recovered = service.recommend_hotels(city="Đà Nẵng", top_k=3)
    assert service.is_initialized is True
    assert service.last_init_error is None
    assert len(recovered) == 1
    assert recovered[0]["hotel_id"] == "H0001"
    assert recovered[0]["hotel_name"] == "Da Nang Riverside"


def test_vihorec_loader_statistics():
    loader = ViHoRecLoader()
    stats = loader.get_audit_statistics()

    assert stats["dataset_name"] == "ViHoRec"
    assert stats["upstream_repo"] == VIHOREC_UPSTREAM_REPO
    assert stats["pinned_revision"] == VIHOREC_PINNED_REVISION
    assert stats["total_interactions"] >= 17000
    assert stats["unique_users"] >= 6000
    assert stats["unique_hotels"] >= 500
    assert stats["benchmark_split"]["train_records"] > 0
    assert stats["benchmark_split"]["test_records"] > 0
    assert stats["matrix_sparsity_percent"] > 99.0


def test_hotel_recommendation_service():
    service = HotelRecommendationService()
    assert service.initialize() is True
    assert service.is_initialized is True
    recs = service.recommend_hotels(city=None, top_k=3)
    assert len(recs) == 3
    for r in recs:
        assert "hotel_id" in r
        assert "hotel_name" in r
        assert "confidence_score" in r
        assert r["confidence_score"] > 0
