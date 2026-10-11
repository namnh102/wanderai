"""Most Popular (MostPop) Recommendation Baseline."""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd


class MostPopularRecommender:
    """Recommender that ranks items by popularity (interaction frequency and average rating)."""

    def __init__(self, damping: float = 5.0):
        self.damping = damping  # Bayesian smoothing prior weight
        self.global_mean: float = 0.0
        self.item_scores: Dict[str, float] = {}
        self.hotel_metadata: Dict[str, Dict[str, Any]] = {}
        self.user_history: Dict[str, set] = {}

    def fit(self, train_df: pd.DataFrame, hotels_df: Optional[pd.DataFrame] = None):
        """Fit popularity model on training interactions."""
        self.global_mean = float(train_df["rating"].mean()) if "rating" in train_df else 5.0

        # Build user interaction history for exclusion
        self.user_history = {}
        for _, row in train_df.iterrows():
            u = str(row["user_id"])
            h = str(row["hotel_id"])
            if u not in self.user_history:
                self.user_history[u] = set()
            self.user_history[u].add(h)

        # Store hotel metadata if provided
        self.hotel_metadata = {}
        if hotels_df is not None:
            for _, row in hotels_df.iterrows():
                h_id = str(row["hotel_id"])
                self.hotel_metadata[h_id] = {
                    "hotel_name": row.get("name") or row.get("hotel_name") or h_id,
                    "city": row.get("city") or row.get("province") or "",
                    "star_rating": float(row.get("star_rating", 0.0)) if pd.notna(row.get("star_rating")) else 0.0,
                }

        # Calculate frequency and average rating per hotel
        stats = train_df.groupby("hotel_id").agg(
            count=("rating", "count"),
            sum_rating=("rating", "sum"),
        ).reset_index()

        self.item_scores = {}
        for _, row in stats.iterrows():
            h_id = str(row["hotel_id"])
            cnt = float(row["count"])
            sum_r = float(row["sum_rating"])
            # Damped / smoothed rating score combined with frequency log
            smoothed_rating = (sum_r + self.damping * self.global_mean) / (cnt + self.damping)
            # Popularity score incorporates frequency
            score = smoothed_rating * (1.0 + (cnt ** 0.5))
            self.item_scores[h_id] = score

        # Sort items by popularity score descending
        self.ranked_items = sorted(self.item_scores.keys(), key=lambda x: self.item_scores[x], reverse=True)
        return self

    def recommend(
        self,
        user_id: Optional[str] = None,
        top_k: int = 10,
        filter_city: Optional[str] = None,
        exclude_seen: bool = True,
    ) -> List[Tuple[str, float]]:
        """Generate top-K item recommendations with scores."""
        seen = set()
        if exclude_seen and user_id and str(user_id) in self.user_history:
            seen = self.user_history[str(user_id)]

        results = []
        for h_id in self.ranked_items:
            if h_id in seen:
                continue

            # Optional city filter
            if filter_city and h_id in self.hotel_metadata:
                meta_city = self.hotel_metadata[h_id].get("city", "")
                if filter_city.lower() not in meta_city.lower():
                    continue

            score = self.item_scores.get(h_id, 0.0)
            results.append((h_id, score))
            if len(results) >= top_k:
                break

        return results
