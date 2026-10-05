"""Recommendation Benchmark Evaluator for ViHoRec."""

import os
import json
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from recommendation.metrics import precision_at_k, recall_at_k, ndcg_at_k
from recommendation.loader import ViHoRecLoader

logger = logging.getLogger(__name__)


class RecommendationEvaluator:
    """Evaluates recommendation models on the official ViHoRec temporal test split."""

    def __init__(self, loader: Optional[ViHoRecLoader] = None, results_dir: Optional[str] = None):
        self.loader = loader or ViHoRecLoader()
        if results_dir is None:
            current = os.path.abspath(os.path.dirname(__file__))
            results_dir = os.path.join(current, "results")
        self.results_dir = results_dir
        os.makedirs(self.results_dir, exist_ok=True)

    def evaluate(self, model: Any, k_list: List[int] = [5, 10], max_users: Optional[int] = None) -> Dict[str, Any]:
        """Evaluate model across test users using leave-last-one-out ground truth."""
        dfs = self.loader.load_dataset()
        test_df = dfs["test"]

        # Ground truth: dictionary of user_id -> list of relevant hotel_ids in test set
        ground_truth: Dict[str, List[str]] = {}
        for _, row in test_df.iterrows():
            u = str(row["user_id"])
            h = str(row["hotel_id"])
            if u not in ground_truth:
                ground_truth[u] = []
            ground_truth[u].append(h)

        test_users = list(ground_truth.keys())
        if max_users is not None and max_users < len(test_users):
            test_users = test_users[:max_users]

        max_k = max(k_list)
        metrics_by_k = {k: {"precision": [], "recall": [], "ndcg": []} for k in k_list}

        for user_id in test_users:
            actual = ground_truth[user_id]
            recs = model.recommend(user_id=user_id, top_k=max_k, exclude_seen=True)
            predicted = [h_id for h_id, _ in recs]

            for k in k_list:
                p = precision_at_k(actual, predicted, k)
                r = recall_at_k(actual, predicted, k)
                n = ndcg_at_k(actual, predicted, k)
                metrics_by_k[k]["precision"].append(p)
                metrics_by_k[k]["recall"].append(r)
                metrics_by_k[k]["ndcg"].append(n)

        # Aggregate mean metrics
        summary = {
            "num_evaluated_users": len(test_users),
            "total_test_users": len(ground_truth),
            "metrics": {},
        }

        for k in k_list:
            summary["metrics"][f"precision@{k}"] = round(float(np.mean(metrics_by_k[k]["precision"])), 5)
            summary["metrics"][f"recall@{k}"] = round(float(np.mean(metrics_by_k[k]["recall"])), 5)
            summary["metrics"][f"ndcg@{k}"] = round(float(np.mean(metrics_by_k[k]["ndcg"])), 5)

        return summary

    def save_results(self, model_name: str, results: Dict[str, Any]) -> str:
        """Save evaluation results to machine-readable JSON."""
        output_file = os.path.join(self.results_dir, f"{model_name.lower()}_benchmark.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "model_name": model_name,
                "dataset": "ViHoRec",
                "evaluation_protocol": "temporal_leave_last_one_out",
                **results,
            }, f, indent=2)
        return output_file
