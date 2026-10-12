"""GoMate REC-A Place Recommender Engine.

Pure, testable recommendation component independent of HTTP/database state.
Reusable by both offline research experiments and online FastAPI runtime endpoints.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from recommendation.reca.contract import (
    CANONICAL_INTERESTS,
    INTEREST_INDEX,
    UNSUPPORTED_USER_FEATURES,
    SUPPORTED_MODELS,
    SUPPORTED_DESTINATIONS,
    MIN_TOP_K,
    MAX_TOP_K,
    normalize_destination,
    normalize_string,
    poi_to_canonical_vector,
    user_to_canonical_vector,
    extract_poi_taxonomy,
    l2_norm,
)
from recommendation.reca.models import (
    RecA0TaxonomyBaseline,
    RecA1CosineBaseline,
    RecA2DiversityReranker,
    ColdStartDiverseBaseline,
    build_explanation,
)


class PlaceRecommender:
    """Core recommendation engine for REC-A.

    Operates strictly on the 622 REC-A-CORE-V2 items from Dataset Freeze V2.
    """

    def __init__(self, places_source: Optional[Union[Path, str, List[Dict[str, Any]]]] = None):
        self.places_source = places_source
        self.core_places: List[Dict[str, Any]] = []
        self.secondary_places: List[Dict[str, Any]] = []
        self.poi_vectors: Dict[str, List[float]] = {}
        self.poi_taxonomy: Dict[str, List[str]] = {}
        self._is_loaded = False
        self.load()

    def _default_dataset_path(self) -> Path:
        """Find the authoritative Freeze V2 JSON artifact path."""
        # Try relative to repo root
        current_file = Path(__file__).resolve()
        # apps/ai-service/recommendation/reca/engine.py -> repo_root is 4 parents up
        repo_root = current_file.parent.parent.parent.parent.parent
        target = repo_root / "data" / "curated" / "gomate_places_freeze_v2.json"
        if target.exists():
            return target
        # Fallback to local cwd search
        cwd_target = Path("data/curated/gomate_places_freeze_v2.json")
        if cwd_target.exists():
            return cwd_target
        raise FileNotFoundError(f"Authoritative dataset freeze v2 not found at {target} or {cwd_target}")

    def load(self):
        """Load and index POIs from Freeze V2 artifact or supplied list."""
        if isinstance(self.places_source, list):
            raw_places = self.places_source
        else:
            path = Path(self.places_source) if self.places_source else self._default_dataset_path()
            with open(path, "r", encoding="utf-8") as f:
                raw_places = json.load(f)

        # Strict segregation: REC-A-CORE-V2 (622) vs Secondary Corpus (137)
        self.core_places = [p for p in raw_places if p.get("is_rec_a_core_v2") is True]
        self.secondary_places = [p for p in raw_places if p.get("is_rec_a_core_v2") is False]

        # Verify dataset invariants if loading full dataset
        if len(raw_places) == 759:
            assert len(self.core_places) == 622, f"Expected 622 core places, got {len(self.core_places)}"
            assert len(self.secondary_places) == 137, f"Expected 137 secondary places, got {len(self.secondary_places)}"

        # Precompute deterministic 7D vectors and taxonomy domains
        self.poi_vectors = {}
        self.poi_taxonomy = {}
        for p in self.core_places:
            pid = p["place_id"]
            vec, tax = poi_to_canonical_vector(p)
            self.poi_vectors[pid] = vec
            self.poi_taxonomy[pid] = tax

        self._is_loaded = True

    def recommend(
        self,
        preferences: Optional[Union[Dict[str, Any], List[str]]] = None,
        destination: Optional[str] = None,
        top_k: int = 10,
        model: Optional[str] = "rec-a1",
    ) -> Dict[str, Any]:
        """Generate ranked place recommendations with strict input validation.

        Args:
            preferences: Dict containing 'interests' key or list of canonical interest strings.
            destination: Optional destination filter ('ha-noi', 'da-nang', 'ha-long' or None for all).
            top_k: Number of recommendations to return (1 <= top_k <= 50, default 10).
            model: Algorithm baseline ('rec-a1' for cosine, 'rec-a0' for taxonomy overlap,
                   'rec-a2' for diversity reranker). If omitted or None, defaults to 'rec-a1'.

        Raises:
            ValueError: If model, destination, or top_k fail validation constraints.

        Returns:
            Dict containing recommendations, metadata, and unsupported user features.
        """
        if not self._is_loaded:
            self.load()

        # 1. Validate top_k (MIN_TOP_K <= top_k <= MAX_TOP_K, integer only)
        if isinstance(top_k, bool) or not isinstance(top_k, int):
            raise ValueError(f"Invalid top_k: expected integer, got {type(top_k).__name__}")
        if top_k < MIN_TOP_K or top_k > MAX_TOP_K:
            raise ValueError(
                f"Invalid top_k '{top_k}': must be between {MIN_TOP_K} and {MAX_TOP_K}"
            )

        # 2. Validate and normalize model
        if model is None:
            normalized_model = "rec-a1"
        elif not isinstance(model, str):
            raise ValueError(f"Invalid model type: expected string, got {type(model).__name__}")
        else:
            normalized_model = model.strip().lower()
            if normalized_model not in SUPPORTED_MODELS:
                raise ValueError(
                    f"Unsupported recommendation model '{model}'. Supported models: {', '.join(SUPPORTED_MODELS)}"
                )

        # 3. Validate and normalize destination
        if destination is None or (isinstance(destination, str) and not destination.strip()):
            dest_slug = None
        elif not isinstance(destination, str):
            raise ValueError(f"Invalid destination type: expected string, got {type(destination).__name__}")
        else:
            dest_slug = normalize_destination(destination)
            if dest_slug is None:
                raise ValueError(
                    f"Unsupported destination '{destination}'. Supported: {', '.join(SUPPORTED_DESTINATIONS)}"
                )

        # 4. Normalize and extract user canonical interests
        raw_interests: List[str] = []
        if isinstance(preferences, dict):
            raw_interests = preferences.get("interests") or []
        elif isinstance(preferences, list):
            raw_interests = preferences

        user_vec = user_to_canonical_vector(raw_interests)
        user_norm = l2_norm(user_vec)

        # 5. Filter eligible candidate universe by destination
        if dest_slug:
            candidates = [p for p in self.core_places if p.get("destination_slug") == dest_slug]
        else:
            candidates = list(self.core_places)

        # 6. Cold-Start Check: user has zero canonical interests
        if user_norm == 0.0:
            recs = ColdStartDiverseBaseline.rank(candidates, top_k=top_k)
            return {
                "recommendations": recs,
                "metadata": {
                    "algorithm": "COLD_START_DIVERSE_CATALOG_BASELINE",
                    "model": "cold-start-diverse",
                    "destination_filter": dest_slug,
                    "total_candidates": len(candidates),
                    "returned_count": len(recs),
                    "cold_start": True,
                },
                "unsupported_user_features": UNSUPPORTED_USER_FEATURES,
            }

        # 7. Score candidates using specified baseline / model
        if normalized_model == "rec-a0":
            scorer = RecA0TaxonomyBaseline
            model_name = scorer.name
            algorithm_desc = scorer.description
            strategy_name = f"{model_name}_content_match"
        elif normalized_model == "rec-a2":
            scorer = RecA1CosineBaseline  # A2 uses A1 cosine similarity as base relevance
            model_name = RecA2DiversityReranker.name
            algorithm_desc = RecA2DiversityReranker.description
            strategy_name = RecA2DiversityReranker.strategy
        else:
            scorer = RecA1CosineBaseline
            model_name = scorer.name
            algorithm_desc = scorer.description
            strategy_name = f"{model_name}_content_match"

        scored_items = []
        for p in candidates:
            pid = p["place_id"]
            p_vec = self.poi_vectors[pid]
            score, matched_interests = scorer.score(user_vec, p_vec)
            p_tax = self.poi_taxonomy[pid]

            scored_items.append({
                "place_id": pid,
                "name": p["name"],
                "destination": p.get("destination", ""),
                "destination_slug": p.get("destination_slug", ""),
                "category": p.get("category", ""),
                "score": score,
                "name_normalized": normalize_string(p.get("name", "")),
                "matched_interests": matched_interests,
                "matched_taxonomy": p_tax,
            })

        # 8. Selection / Reranking
        if normalized_model == "rec-a2":
            declared_interests = [
                ci for ci in CANONICAL_INTERESTS if user_vec[INTEREST_INDEX[ci]] > 0
            ]
            top_items = RecA2DiversityReranker.rerank(
                scored_items, declared_interests=declared_interests, top_k=top_k
            )
        else:
            # Baseline stable deterministic tie-break: (-score, name_normalized, place_id)
            scored_items.sort(
                key=lambda x: (-x["score"], x["name_normalized"], x["place_id"])
            )
            top_items = scored_items[:top_k]

        # 9. Build Top-K results with explanations
        recommendations = []
        for rank, item in enumerate(top_items, start=1):
            explanation = build_explanation(
                matched_interests=item["matched_interests"],
                matched_taxonomy=item["matched_taxonomy"],
                is_cold_start=False,
            )
            recommendations.append({
                "place_id": item["place_id"],
                "name": item["name"],
                "destination": item["destination"],
                "destination_slug": item["destination_slug"],
                "category": item["category"],
                "score": item["score"],
                "rank": rank,
                "matched_interests": item["matched_interests"],
                "explanation": explanation,
                "strategy": strategy_name,
            })

        return {
            "recommendations": recommendations,
            "metadata": {
                "algorithm": algorithm_desc,
                "model": model_name,
                "destination_filter": dest_slug,
                "total_candidates": len(candidates),
                "returned_count": len(recommendations),
                "cold_start": False,
            },
            "unsupported_user_features": UNSUPPORTED_USER_FEATURES,
        }


_GLOBAL_RECOMMENDER: Optional[PlaceRecommender] = None


def get_place_recommender() -> PlaceRecommender:
    """Singleton getter for PlaceRecommender."""
    global _GLOBAL_RECOMMENDER
    if _GLOBAL_RECOMMENDER is None:
        _GLOBAL_RECOMMENDER = PlaceRecommender()
    return _GLOBAL_RECOMMENDER
