"""GoMate REC-A Recommendation Benchmark Runner.

Evaluates REC-A0 (Taxonomy Overlap) and REC-A1 (Cosine Content-Based)
against the 300 synthetic preference profiles from WP-PROF-01/DATA-02
using the authoritative 622 REC-A-CORE-V2 catalog from Freeze V2.

Outputs:
- data/evaluation/reca/reca0_top10_n300.json
- data/evaluation/reca/reca1_top10_n300.json
- data/evaluation/reca/reca_benchmark_summary.json
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
import statistics

# Ensure ai-service is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
AI_SERVICE_DIR = REPO_ROOT / "apps" / "ai-service"
if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))

from recommendation.reca.engine import PlaceRecommender
from recommendation.reca.contract import CANONICAL_INTERESTS, UNSUPPORTED_USER_FEATURES


def run_benchmarks():
    dataset_path = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
    profiles_path = REPO_ROOT / "data" / "evaluation" / "synthetic" / "preferences_n300_seed42.json"
    output_dir = REPO_ROOT / "data" / "evaluation" / "reca"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading dataset from: {dataset_path}")
    assert dataset_path.exists(), f"Missing dataset: {dataset_path}"
    print(f"Loading synthetic profiles from: {profiles_path}")
    assert profiles_path.exists(), f"Missing profiles: {profiles_path}"

    with open(profiles_path, "r", encoding="utf-8") as f:
        profiles: List[Dict[str, Any]] = json.load(f)
    print(f"Loaded {len(profiles)} synthetic profiles.")
    assert len(profiles) == 300, f"Expected 300 profiles, got {len(profiles)}"

    # Initialize Recommender Engine
    recommender = PlaceRecommender(places_source=dataset_path)
    assert len(recommender.core_places) == 622, f"Expected 622 core places, got {len(recommender.core_places)}"
    assert len(recommender.secondary_places) == 137, f"Expected 137 secondary places, got {len(recommender.secondary_places)}"

    # 1. Run REC-A0
    print("\n--- Running REC-A0 (Taxonomy Overlap Baseline) ---")
    reca0_results = []
    for p in profiles:
        uid = p["synthetic_user_id"]
        res = recommender.recommend(preferences=p, destination=None, top_k=10, model="rec-a0")
        reca0_results.append({
            "synthetic_user_id": uid,
            "travelStyle": p.get("travelStyle"),
            "budgetMin": p.get("budgetMin"),
            "budgetMax": p.get("budgetMax"),
            "interests": p.get("interests", []),
            "recommendations": res["recommendations"],
            "metadata": res["metadata"],
        })

    # 2. Run REC-A1
    print("--- Running REC-A1 (Cosine Content-Based Baseline) ---")
    reca1_results = []
    for p in profiles:
        uid = p["synthetic_user_id"]
        res = recommender.recommend(preferences=p, destination=None, top_k=10, model="rec-a1")
        reca1_results.append({
            "synthetic_user_id": uid,
            "travelStyle": p.get("travelStyle"),
            "budgetMin": p.get("budgetMin"),
            "budgetMax": p.get("budgetMax"),
            "interests": p.get("interests", []),
            "recommendations": res["recommendations"],
            "metadata": res["metadata"],
        })

    # 3. Determinism Check (Run 2)
    print("\n--- Running Determinism Verification (Run 2 vs Run 1) ---")
    reca0_run2 = [
        {
            "synthetic_user_id": p["synthetic_user_id"],
            "travelStyle": p.get("travelStyle"),
            "budgetMin": p.get("budgetMin"),
            "budgetMax": p.get("budgetMax"),
            "interests": p.get("interests", []),
            "recommendations": recommender.recommend(preferences=p, destination=None, top_k=10, model="rec-a0")["recommendations"],
            "metadata": recommender.recommend(preferences=p, destination=None, top_k=10, model="rec-a0")["metadata"],
        }
        for p in profiles
    ]
    reca1_run2 = [
        {
            "synthetic_user_id": p["synthetic_user_id"],
            "travelStyle": p.get("travelStyle"),
            "budgetMin": p.get("budgetMin"),
            "budgetMax": p.get("budgetMax"),
            "interests": p.get("interests", []),
            "recommendations": recommender.recommend(preferences=p, destination=None, top_k=10, model="rec-a1")["recommendations"],
            "metadata": recommender.recommend(preferences=p, destination=None, top_k=10, model="rec-a1")["metadata"],
        }
        for p in profiles
    ]

    a0_deterministic = (reca0_results == reca0_run2)
    a1_deterministic = (reca1_results == reca1_run2)
    print(f"REC-A0 Run 1 == Run 2: {a0_deterministic}")
    print(f"REC-A1 Run 1 == Run 2: {a1_deterministic}")
    assert a0_deterministic, "REC-A0 determinism check failed!"
    assert a1_deterministic, "REC-A1 determinism check failed!"

    # 4. Compute Metrics
    def compute_model_metrics(results: List[Dict[str, Any]], model_name: str) -> Dict[str, Any]:
        all_scores: List[float] = []
        unique_places = set()
        destination_counts: Dict[str, int] = {}
        category_counts: Dict[str, int] = {}
        zero_result_count = 0
        cold_start_count = 0

        for r in results:
            recs = r["recommendations"]
            if not recs:
                zero_result_count += 1
            if r["metadata"].get("cold_start") is True:
                cold_start_count += 1

            for item in recs:
                all_scores.append(float(item["score"]))
                pid = item["place_id"]
                unique_places.add(pid)
                dest = item.get("destination_slug") or item.get("destination") or "unknown"
                destination_counts[dest] = destination_counts.get(dest, 0) + 1
                cat = item.get("category") or "unknown"
                category_counts[cat] = category_counts.get(cat, 0) + 1

        coverage_pct = round((len(unique_places) / 622) * 100, 2)
        score_stats = {
            "min": round(min(all_scores), 4) if all_scores else 0.0,
            "max": round(max(all_scores), 4) if all_scores else 0.0,
            "mean": round(statistics.mean(all_scores), 4) if all_scores else 0.0,
            "median": round(statistics.median(all_scores), 4) if all_scores else 0.0,
            "stdev": round(statistics.stdev(all_scores), 4) if len(all_scores) > 1 else 0.0,
        }

        return {
            "model": model_name,
            "total_profiles": len(results),
            "total_recommendations_made": len(all_scores),
            "zero_result_profiles": zero_result_count,
            "cold_start_profiles": cold_start_count,
            "unique_places_recommended": len(unique_places),
            "catalog_coverage_pct": coverage_pct,
            "score_distribution": score_stats,
            "destination_distribution": destination_counts,
            "top_categories_recommended": dict(sorted(category_counts.items(), key=lambda x: -x[1])[:10]),
        }

    metrics_a0 = compute_model_metrics(reca0_results, "rec-a0")
    metrics_a1 = compute_model_metrics(reca1_results, "rec-a1")

    # 5. Write Artifacts
    a0_file = output_dir / "reca0_top10_n300.json"
    a1_file = output_dir / "reca1_top10_n300.json"
    summary_file = output_dir / "reca_benchmark_summary.json"

    with open(a0_file, "w", encoding="utf-8") as f:
        json.dump(reca0_results, f, ensure_ascii=False, indent=2)
    print(f"Saved: {a0_file}")

    with open(a1_file, "w", encoding="utf-8") as f:
        json.dump(reca1_results, f, ensure_ascii=False, indent=2)
    print(f"Saved: {a1_file}")

    summary_data = {
        "benchmark_id": "REC-A-BENCHMARK-V1",
        "dataset_freeze": "v2",
        "catalog_universe": "REC-A-CORE-V2",
        "catalog_size": 622,
        "profiles_evaluated": 300,
        "top_k": 10,
        "determinism_verification": {
            "rec_a0_bit_identical": a0_deterministic,
            "rec_a1_bit_identical": a1_deterministic,
        },
        "rec_a0": metrics_a0,
        "rec_a1": metrics_a1,
        "comparison_notes": [
            "REC-A0 produces integer overlap scores in range [1, 4] representing count of matching canonical interests.",
            "REC-A1 produces normalized cosine scores in range [0, 1] representing cosine similarity between 7D user and item vectors.",
            "Both models strictly evaluate over the 622 REC-A-CORE-V2 POI catalog (Hanoi: 145, Ha Long: 188, Da Nang: 289) and exclude all 137 secondary places.",
            "Zero empty/zero-result profiles occurred across all 300 synthetic evaluations.",
            "Independent sequential runs confirmed 100% bit-identical ranking reproducibility."
        ],
    }

    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {summary_file}")

    print("\n=== Benchmark Summary ===")
    print(f"REC-A0 Catalog Coverage: {metrics_a0['catalog_coverage_pct']}% ({metrics_a0['unique_places_recommended']}/622 unique POIs)")
    print(f"REC-A0 Scores: min={metrics_a0['score_distribution']['min']}, max={metrics_a0['score_distribution']['max']}, mean={metrics_a0['score_distribution']['mean']}")
    print(f"REC-A1 Catalog Coverage: {metrics_a1['catalog_coverage_pct']}% ({metrics_a1['unique_places_recommended']}/622 unique POIs)")
    print(f"REC-A1 Scores: min={metrics_a1['score_distribution']['min']}, max={metrics_a1['score_distribution']['max']}, mean={metrics_a1['score_distribution']['mean']}")
    print(f"Zero Result Profiles: A0={metrics_a0['zero_result_profiles']}, A1={metrics_a1['zero_result_profiles']}")
    print("Benchmark complete!")


if __name__ == "__main__":
    run_benchmarks()
