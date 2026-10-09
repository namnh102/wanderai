#!/usr/bin/env python3
"""DATA-02 Deterministic Synthetic Travel Preference Generator.

Generates N = 300 synthetic user travel preference profiles from seed = 42
adhering strictly to docs/data/gomate-synthetic-preference-contract-v1.md.

Outputs:
1. data/research/preferences/synthetic_preferences_v1.jsonl
2. data/evaluation/synthetic/preferences_n300_seed42.json
3. Distribution analysis report
"""

import hashlib
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("synthetic_preference_generator")

SEED = 42
POPULATION_SIZE = 300
GENERATOR_VERSION = "preference-v1"

def generate_synthetic_preferences(n: int = POPULATION_SIZE, seed: int = SEED) -> list[dict[str, Any]]:
    rng = random.Random(seed)

    styles = ["BUDGET", "COMFORT", "BACKPACKER", "LUXURY"]
    style_weights = [0.40, 0.35, 0.15, 0.10]

    groups = ["COUPLE", "SOLO", "SMALL_GROUP", "FAMILY", "LARGE_GROUP"]
    group_weights = [0.30, 0.25, 0.25, 0.15, 0.05]

    paces = ["MODERATE", "RELAXED", "PACKED"]
    pace_weights = [0.50, 0.30, 0.20]

    interest_pool = [
        "food_cuisine", "culture_history", "nature_outdoor",
        "coffee_culture", "beach_island", "shopping_local", "nightlife_entertainment"
    ]
    interest_weights = [0.22, 0.20, 0.18, 0.15, 0.12, 0.07, 0.06]

    diet_pool = [
        ([], 0.80),
        (["vegetarian"], 0.10),
        (["vegan"], 0.04),
        (["seafood_allergy"], 0.04),
        (["halal"], 0.02),
    ]

    avoid_pool = [
        ([], 0.40),
        (["crowds"], 0.25),
        (["long_walks"], 0.15),
        (["heights"], 0.10),
        (["spicy_food"], 0.10),
    ]

    profiles = []
    for i in range(1, n + 1):
        uid = f"syn_usr_{i:04d}"
        style = rng.choices(styles, weights=style_weights, k=1)[0]
        group = rng.choices(groups, weights=group_weights, k=1)[0]
        pace = rng.choices(paces, weights=pace_weights, k=1)[0]

        # Budget by style
        if style == "BACKPACKER":
            b_min = rng.randint(4, 9) * 50_000      # 200k - 450k
            b_max = rng.randint(10, 24) * 50_000    # 500k - 1.2M
        elif style == "BUDGET":
            b_min = rng.randint(6, 14) * 50_000     # 300k - 700k
            b_max = rng.randint(16, 40) * 50_000    # 800k - 2.0M
        elif style == "COMFORT":
            b_min = rng.randint(20, 40) * 50_000    # 1.0M - 2.0M
            b_max = rng.randint(50, 110) * 50_000   # 2.5M - 5.5M
        else:  # LUXURY
            b_min = rng.randint(60, 120) * 50_000   # 3.0M - 6.0M
            b_max = rng.randint(140, 500) * 50_000  # 7.0M - 25.0M

        k_interests = rng.randint(2, 4)
        chosen_interests = []
        pool_copy = list(interest_pool)
        w_copy = list(interest_weights)
        for _ in range(k_interests):
            chosen = rng.choices(pool_copy, weights=w_copy, k=1)[0]
            idx = pool_copy.index(chosen)
            chosen_interests.append(chosen)
            pool_copy.pop(idx)
            w_copy.pop(idx)

        diet = rng.choices([d[0] for d in diet_pool], weights=[d[1] for d in diet_pool], k=1)[0]
        avoid = rng.choices([a[0] for a in avoid_pool], weights=[a[1] for a in avoid_pool], k=1)[0]

        profile = {
            "synthetic_user_id": uid,
            "travelStyle": style,
            "budgetMin": b_min,
            "budgetMax": b_max,
            "preferredGroup": group,
            "interests": chosen_interests,
            "pace": pace,
            "avoidances": avoid,
            "dietaryNeeds": diet,
            "isSynthetic": True,
            "seed": SEED,
            "generatorVersion": GENERATOR_VERSION,
        }
        profiles.append(profile)

    return profiles

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def analyze_distributions(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(profiles)
    styles = {}
    groups = {}
    paces = {}
    interests_freq = {}
    diets = {}
    avoidances = {}
    budget_stats = {"min_overall": 1e9, "max_overall": 0, "by_style": {}}

    for p in profiles:
        s = p["travelStyle"]
        g = p["preferredGroup"]
        pc = p["pace"]

        styles[s] = styles.get(s, 0) + 1
        groups[g] = groups.get(g, 0) + 1
        paces[pc] = paces.get(pc, 0) + 1

        for it in p["interests"]:
            interests_freq[it] = interests_freq.get(it, 0) + 1

        d_key = "+".join(sorted(p["dietaryNeeds"])) if p["dietaryNeeds"] else "NONE"
        diets[d_key] = diets.get(d_key, 0) + 1

        a_key = "+".join(sorted(p["avoidances"])) if p["avoidances"] else "NONE"
        avoidances[a_key] = avoidances.get(a_key, 0) + 1

        b_min = p["budgetMin"]
        b_max = p["budgetMax"]
        budget_stats["min_overall"] = min(budget_stats["min_overall"], b_min)
        budget_stats["max_overall"] = max(budget_stats["max_overall"], b_max)

        if s not in budget_stats["by_style"]:
            budget_stats["by_style"][s] = {"min_b": b_min, "max_b": b_max, "sum_min": 0, "sum_max": 0, "count": 0}
        bs = budget_stats["by_style"][s]
        bs["min_b"] = min(bs["min_b"], b_min)
        bs["max_b"] = max(bs["max_b"], b_max)
        bs["sum_min"] += b_min
        bs["sum_max"] += b_max
        bs["count"] += 1

    for s, bs in budget_stats["by_style"].items():
        bs["avg_min"] = round(bs["sum_min"] / bs["count"])
        bs["avg_max"] = round(bs["sum_max"] / bs["count"])

    return {
        "population_size": n,
        "seed": SEED,
        "generator_version": GENERATOR_VERSION,
        "travelStyle_distribution": {k: {"count": v, "pct": round(v / n * 100, 1)} for k, v in sorted(styles.items())},
        "preferredGroup_distribution": {k: {"count": v, "pct": round(v / n * 100, 1)} for k, v in sorted(groups.items())},
        "pace_distribution": {k: {"count": v, "pct": round(v / n * 100, 1)} for k, v in sorted(paces.items())},
        "interests_frequency": {k: {"count": v, "pct": round(v / n * 100, 1)} for k, v in sorted(interests_freq.items(), key=lambda x: -x[1])},
        "dietary_needs_distribution": {k: {"count": v, "pct": round(v / n * 100, 1)} for k, v in sorted(diets.items())},
        "avoidances_distribution": {k: {"count": v, "pct": round(v / n * 100, 1)} for k, v in sorted(avoidances.items())},
        "budget_statistics": budget_stats
    }

def main():
    repo_root = Path(__file__).resolve().parent.parent
    research_dir = repo_root / "data" / "research" / "preferences"
    research_dir.mkdir(parents=True, exist_ok=True)
    eval_dir = repo_root / "data" / "evaluation" / "synthetic"
    eval_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"GENERATING DETERMINISTIC SYNTHETIC PREFERENCES (N={POPULATION_SIZE}, SEED={SEED})")
    print("=" * 70)

    # 1. Generate run 1
    profiles_run1 = generate_synthetic_preferences(POPULATION_SIZE, SEED)

    # Write JSONL
    jsonl_path = research_dir / "synthetic_preferences_v1.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for p in profiles_run1:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    sha_jsonl = compute_sha256(jsonl_path)

    # Write JSON
    json_path = eval_dir / "preferences_n300_seed42.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(profiles_run1, f, indent=2, ensure_ascii=False)
    sha_json = compute_sha256(json_path)

    # 2. Reproducibility test
    profiles_run2 = generate_synthetic_preferences(POPULATION_SIZE, SEED)
    assert profiles_run1 == profiles_run2, "Deterministic reproducibility failed in memory comparison!"

    temp_path = research_dir / "temp_reproduce_test.jsonl"
    with open(temp_path, "w", encoding="utf-8") as f:
        for p in profiles_run2:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    sha_reproduce = compute_sha256(temp_path)
    temp_path.unlink()

    assert sha_jsonl == sha_reproduce, f"Reproducibility SHA mismatch: {sha_jsonl} vs {sha_reproduce}"
    print(f"[PASS] Reproducibility Check: Bit-exact match from seed {SEED}.")
    print(f"       JSONL: {jsonl_path.relative_to(repo_root)} (SHA-256: {sha_jsonl})")
    print(f"       JSON:  {json_path.relative_to(repo_root)} (SHA-256: {sha_json})")

    # 3. Distribution report
    dist_report = analyze_distributions(profiles_run1)
    report_path = research_dir / "synthetic_preferences_distribution_v1.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(dist_report, f, indent=2, ensure_ascii=False)
    print(f"       Report: {report_path.relative_to(repo_root)}")

    print("\nDISTRIBUTION SUMMARY:")
    print("Travel Styles:")
    for k, v in dist_report["travelStyle_distribution"].items():
        print(f"  - {k:<15}: {v['count']} ({v['pct']}%)")
    print("Pacing:")
    for k, v in dist_report["pace_distribution"].items():
        print(f"  - {k:<15}: {v['count']} ({v['pct']}%)")
    print("Group Configuration:")
    for k, v in dist_report["preferredGroup_distribution"].items():
        print(f"  - {k:<15}: {v['count']} ({v['pct']}%)")

if __name__ == "__main__":
    main()
