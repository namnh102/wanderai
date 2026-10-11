# GoMate Synthetic Travel Preference Contract (V1)

**Document Version:** 1.0.0  
**Snapshot Date:** 2026-10-07  
**Branch / Worktree:** `feature/data-foundation-w2`  
**Task Reference:** TASK DATA-01B-R1 (Synthetic Preference Contract Specification)  
**Generator Identification:** `preference-v1` (Deterministic Pseudo-Random Generator)  
**Evaluation Role:** Offline Recommender (REC-A) & Buddy Matching Constraint Evaluation Only

---

## 1. Executive Summary & Scientific Disclaimer

This document defines the formal data contract, sampling distributions, and deterministic generation protocol for **$N = 300$ synthetic user travel preference profiles**.

> [!IMPORTANT]
> **SCIENTIFIC DISCLAIMER & SCOPE BOUNDARY:**  
> These synthetic profiles are **NOT claimed to represent the real demographic or statistical distribution of Vietnamese travelers**. They are designed exclusively as a reproducible, controlled academic benchmark fixture for testing recommendation ranking behavior, coverage, intra-list diversity, and traveler matching constraint satisfaction algorithms in the absence of live user traffic.

### Architecture Invariant
- **Week 2 Scope:** This representation is utilized exclusively in the research and evaluation pipelines (`apps/ai-service/recommendation/`).
- **No Schema Pollution:** Field `pace` is maintained purely within offline evaluation fixtures and AI service models. **`pace` is NOT added to `schema.prisma`** during Week 2.

---

## 2. Canonical Generator Parameters

```yaml
generator_metadata:
  population_size: 300
  random_seed: 42
  generator_version: "preference-v1"
  is_synthetic: true
  distribution_type: "parameterized_non_uniform"
  target_file: "data/evaluation/synthetic/preferences_n300_seed42.json"
```

---

## 3. Schema & Field Definitions

Each synthetic profile object strictly adheres to the following JSON schema:

| Field | Type | Allowed Values / Ranges | Description |
| :--- | :--- | :--- | :--- |
| `synthetic_user_id` | `string` | `"syn_usr_0001"` to `"syn_usr_0300"` | Deterministic synthetic identifier. |
| `travelStyle` | `string` | `BACKPACKER`, `BUDGET`, `COMFORT`, `LUXURY` | Primary travel travel style tier. |
| `budgetMin` | `integer` | $200,000$ to $6,000,000$ VND | Minimum planned budget (VND integer). |
| `budgetMax` | `integer` | $600,000$ to $25,000,000$ VND | Maximum planned budget (VND integer; $> \text{budgetMin}$). |
| `preferredGroup` | `string` | `SOLO`, `COUPLE`, `SMALL_GROUP`, `LARGE_GROUP`, `FAMILY` | Group travel configuration. |
| `interests` | `string[]` | 2 to 4 tags from Taxonomy Tier-1/Tier-2 | Multi-select interests matching POI categories. |
| `pace` | `string` | `RELAXED`, `MODERATE`, `PACKED` | Intended itinerary pacing (offline research only). |
| `avoidances` | `string[]` | 0 to 2 tags from avoidance vocabulary | Negative filters / constraints. |
| `dietaryNeeds` | `string[]` | 0 to 2 tags from dietary vocabulary | Specific food restrictions. |
| `isSynthetic` | `boolean` | `true` | Immutable audit flag. |
| `seed` | `integer` | `42` | Cryptographic PRNG seed. |
| `generatorVersion` | `string` | `"preference-v1"` | Generator version string. |

---

## 4. Parameterized Non-Uniform Sampling Distributions

To prevent artificial uniformity, parameters are sampled from non-uniform empirical probability distributions reflective of diverse travel styles:

### 4.1. Travel Style & Correlated Budget Ranges
Travel style governs the sampling bounds for `budgetMin` and `budgetMax` (all values rounded to nearest 50,000 VND):

| Travel Style | Probability $P(S)$ | `budgetMin` Range (VND) | `budgetMax` Range (VND) |
| :--- | :---: | :--- | :--- |
| **`BUDGET`** | 0.40 (40%) | $[300,000, 700,000]$ | $[800,000, 2,000,000]$ |
| **`COMFORT`** | 0.35 (35%) | $[1,000,000, 2,000,000]$ | $[2,500,000, 5,500,000]$ |
| **`BACKPACKER`** | 0.15 (15%) | $[200,000, 450,000]$ | $[500,000, 1,200,000]$ |
| **`LUXURY`** | 0.10 (10%) | $[3,000,000, 6,000,000]$ | $[7,000,000, 25,000,000]$ |

### 4.2. Preferred Group Size Distribution
- `COUPLE`: 30% ($P = 0.30$)
- `SOLO`: 25% ($P = 0.25$) — primary candidate pool for buddy matching
- `SMALL_GROUP` (3–5): 25% ($P = 0.25$)
- `FAMILY`: 15% ($P = 0.15$)
- `LARGE_GROUP` (6+): 5% ($P = 0.05$)

### 4.3. Travel Pace Distribution
- `MODERATE`: 50% ($P = 0.50$, 4–5 POIs/day)
- `RELAXED`: 30% ($P = 0.30$, 2–3 POIs/day)
- `PACKED`: 20% ($P = 0.20$, 6+ POIs/day)

### 4.4. Interest Sampling Weights
Users are assigned between 2 and 4 distinct interests without replacement:
- `food_cuisine`: Weight 0.22 (Popular Vietnamese street food and dining)
- `culture_history`: Weight 0.20 (Museums, pagodas, temples)
- `nature_outdoor`: Weight 0.18 (Parks, mountains, bays)
- `coffee_culture`: Weight 0.15 (Specialty cafes)
- `beach_island`: Weight 0.12 (Coastal attractions)
- `shopping_local`: Weight 0.07 (Markets and crafts)
- `nightlife_entertainment`: Weight 0.06 (Pubs and walking streets)

### 4.5. Constraints & Negative Filters
- **Dietary Needs:**
  - `[]` (None): 80% ($P = 0.80$)
  - `["vegetarian"]`: 10% ($P = 0.10$)
  - `["vegan"]`: 4% ($P = 0.04$)
  - `["seafood_allergy"]`: 4% ($P = 0.04$)
  - `["halal"]`: 2% ($P = 0.02$)
- **Avoidances:**
  - `[]` (None): 40% ($P = 0.40$)
  - `["crowds"]`: 25% ($P = 0.25$)
  - `["long_walks"]`: 15% ($P = 0.15$)
  - `["heights"]`: 10% ($P = 0.10$)
  - `["spicy_food"]`: 10% ($P = 0.10$)

---

## 5. Reference Deterministic Generation Implementation

The canonical generator code below guarantees exact bit-for-bit reproducibility when executed with `seed = 42`:

```python
"""Reference deterministic generator for GoMate Synthetic Travel Preferences."""
import json
import random
from typing import List, Dict, Any

SEED = 42
POPULATION_SIZE = 300
GENERATOR_VERSION = "preference-v1"


def generate_synthetic_preferences(n: int = POPULATION_SIZE, seed: int = SEED) -> List[Dict[str, Any]]:
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
        # Sample without replacement using weights
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
```

---

## 6. Sample Verified Output Record

```json
{
  "synthetic_user_id": "syn_usr_0001",
  "travelStyle": "COMFORT",
  "budgetMin": 1450000,
  "budgetMax": 4200000,
  "preferredGroup": "SOLO",
  "interests": ["culture_history", "coffee_culture", "food_cuisine"],
  "pace": "MODERATE",
  "avoidances": ["crowds"],
  "dietaryNeeds": [],
  "isSynthetic": true,
  "seed": 42,
  "generatorVersion": "preference-v1"
}
```
