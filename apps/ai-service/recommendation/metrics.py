"""Evaluation metrics for Recommendation Systems."""

import math
from typing import List, Sequence, Set


def precision_at_k(actual: Sequence[str], predicted: Sequence[str], k: int) -> float:
    """Compute Precision@K."""
    if k <= 0 or not predicted:
        return 0.0
    pred_k = predicted[:k]
    actual_set = set(actual)
    hits = sum(1 for item in pred_k if item in actual_set)
    return hits / float(k)


def recall_at_k(actual: Sequence[str], predicted: Sequence[str], k: int) -> float:
    """Compute Recall@K."""
    if not actual:
        return 0.0
    k = min(k, len(predicted))
    pred_k = predicted[:k]
    actual_set = set(actual)
    hits = sum(1 for item in pred_k if item in actual_set)
    return hits / float(len(actual_set))


def ndcg_at_k(actual: Sequence[str], predicted: Sequence[str], k: int) -> float:
    """Compute Normalized Discounted Cumulative Gain at K (NDCG@K) with binary relevance."""
    if not actual or not predicted or k <= 0:
        return 0.0

    actual_set = set(actual)
    pred_k = predicted[:k]

    # DCG
    dcg = 0.0
    for i, item in enumerate(pred_k):
        if item in actual_set:
            dcg += 1.0 / math.log2(i + 2)

    # IDCG (ideal DCG with all actual items at the top up to k)
    idcg = 0.0
    num_relevant = min(len(actual_set), k)
    for i in range(num_relevant):
        idcg += 1.0 / math.log2(i + 2)

    if idcg == 0.0:
        return 0.0

    return dcg / idcg
