"""Baseline Recommendation Models for REC-A.

Implements:
- REC-A0: Taxonomy Match Overlap Baseline
- REC-A1: Cosine Content-Based Baseline
- ColdStartDiverseBaseline: Deterministic Catalog-Diverse Fallback (NOT popularity)
"""

from typing import List, Dict, Any, Tuple
from recommendation.reca.contract import (
    CANONICAL_INTERESTS,
    INTEREST_LABELS_VI,
    cosine_similarity,
    normalize_string,
)


def build_explanation(
    matched_interests: List[str],
    matched_taxonomy: List[str],
    is_cold_start: bool = False,
) -> Dict[str, Any]:
    """Generate deterministic machine-readable explanation and factual text."""
    if is_cold_start or not matched_interests:
        return {
            "reason_code": "COLD_START_DIVERSE_FALLBACK",
            "matched_interests": [],
            "matched_taxonomy": matched_taxonomy,
            "text": "Địa điểm tiêu biểu tại điểm đến dành cho bạn khám phá.",
        }

    # Format human text deterministically from matched interests
    labels = [INTEREST_LABELS_VI[k] for k in matched_interests if k in INTEREST_LABELS_VI]
    if len(labels) == 1:
        interest_text = labels[0]
    elif len(labels) == 2:
        interest_text = f"{labels[0]} và {labels[1]}"
    else:
        interest_text = ", ".join(labels[:-1]) + f" và {labels[-1]}"

    return {
        "reason_code": "PREFERENCE_TAXONOMY_MATCH",
        "matched_interests": matched_interests,
        "matched_taxonomy": matched_taxonomy,
        "text": f"Phù hợp vì bạn quan tâm đến {interest_text}.",
    }


class RecA0TaxonomyBaseline:
    """REC-A0: Simple deterministic overlap between user interests and POI canonical interest dimensions."""

    name = "rec-a0"
    description = "Taxonomy Match Overlap Baseline"

    @staticmethod
    def score(
        user_vector: List[float],
        poi_vector: List[float],
    ) -> Tuple[float, List[str]]:
        """Compute dot-product overlap score and list of matched canonical interests."""
        score = sum(u * v for u, v in zip(user_vector, poi_vector))
        matched = [
            CANONICAL_INTERESTS[i]
            for i, (u, v) in enumerate(zip(user_vector, poi_vector))
            if u > 0 and v > 0
        ]
        return float(round(score, 6)), matched


class RecA1CosineBaseline:
    """REC-A1: Cosine similarity between user preference vector and POI content vector."""

    name = "rec-a1"
    description = "Cosine Content-Based Baseline"

    @staticmethod
    def score(
        user_vector: List[float],
        poi_vector: List[float],
    ) -> Tuple[float, List[str]]:
        """Compute cosine similarity score and list of matched canonical interests."""
        score = cosine_similarity(user_vector, poi_vector)
        matched = [
            CANONICAL_INTERESTS[i]
            for i, (u, v) in enumerate(zip(user_vector, poi_vector))
            if u > 0 and v > 0
        ]
        return float(round(score, 6)), matched


class ColdStartDiverseBaseline:
    """Deterministic non-personalized diverse catalog fallback for cold-start users.

    Guarantees broad category coverage without fabricating popularity or rating signals.
    """

    name = "cold-start-diverse"
    description = "COLD_START_DIVERSE_CATALOG_BASELINE"

    PRIORITY_DOMAINS = [
        "CULTURE_HERITAGE",
        "NATURE_SCENERY",
        "FOOD_BEVERAGE",
        "SHOPPING_COMMERCE",
        "ATTRACTIONS_LEISURE",
        "HOSPITALITY",
        "TRANSPORT_HUBS",
    ]

    @classmethod
    def rank(
        cls,
        candidates: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Rank candidates across diverse taxonomy categories using round-robin stratification."""
        from recommendation.reca.contract import extract_poi_taxonomy

        # Group candidates by macro domain
        grouped: Dict[str, List[Dict[str, Any]]] = {dom: [] for dom in cls.PRIORITY_DOMAINS}
        for p in candidates:
            t1, _, _ = extract_poi_taxonomy(p)
            if t1 in grouped:
                grouped[t1].append(p)
            else:
                grouped.setdefault("ATTRACTIONS_LEISURE", []).append(p)

        # Sort each domain group deterministically by (name, place_id)
        for dom in cls.PRIORITY_DOMAINS:
            grouped[dom].sort(
                key=lambda x: (normalize_string(x.get("name", "")), x.get("place_id", ""))
            )

        # Round-robin selection
        selected = []
        selected_ids = set()
        ptr = {dom: 0 for dom in cls.PRIORITY_DOMAINS}

        while len(selected) < top_k:
            added_in_round = False
            for dom in cls.PRIORITY_DOMAINS:
                items = grouped[dom]
                idx = ptr[dom]
                while idx < len(items) and items[idx]["place_id"] in selected_ids:
                    idx += 1
                if idx < len(items):
                    item = items[idx]
                    ptr[dom] = idx + 1
                    selected_ids.add(item["place_id"])
                    selected.append(item)
                    added_in_round = True
                    if len(selected) >= top_k:
                        break
            if not added_in_round:
                break

        # Build output objects with pseudo-score reflecting rank
        ranked_results = []
        total_selected = len(selected)
        for rank, p in enumerate(selected, start=1):
            t1, _, _ = extract_poi_taxonomy(p)
            # Normalizing rank to [1.0, 0.1]
            pseudo_score = round(1.0 - (rank - 1) / max(total_selected, 1) * 0.9, 4)
            explanation = build_explanation(
                matched_interests=[],
                matched_taxonomy=[t1],
                is_cold_start=True,
            )
            ranked_results.append({
                "place_id": p["place_id"],
                "name": p["name"],
                "destination": p.get("destination", ""),
                "destination_slug": p.get("destination_slug", ""),
                "category": p.get("category", ""),
                "score": pseudo_score,
                "rank": rank,
                "matched_interests": [],
                "explanation": explanation,
                "strategy": "COLD_START_DIVERSE_CATALOG_BASELINE",
            })

        return ranked_results
