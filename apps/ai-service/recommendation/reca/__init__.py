"""GoMate REC-A Recommendation Package."""

from recommendation.reca.contract import (
    CANONICAL_INTERESTS,
    UNSUPPORTED_USER_FEATURES,
    INTEREST_LABELS_VI,
    poi_to_canonical_vector,
    user_to_canonical_vector,
    normalize_destination,
)
from recommendation.reca.models import (
    RecA0TaxonomyBaseline,
    RecA1CosineBaseline,
    ColdStartDiverseBaseline,
    build_explanation,
)
from recommendation.reca.engine import PlaceRecommender, get_place_recommender

__all__ = [
    "CANONICAL_INTERESTS",
    "UNSUPPORTED_USER_FEATURES",
    "INTEREST_LABELS_VI",
    "poi_to_canonical_vector",
    "user_to_canonical_vector",
    "normalize_destination",
    "RecA0TaxonomyBaseline",
    "RecA1CosineBaseline",
    "ColdStartDiverseBaseline",
    "build_explanation",
    "PlaceRecommender",
    "get_place_recommender",
]
