# W5 Relevance Annotation Rubric

**Version:** `W5-RUBRIC-V1`  
**Operational Framework:** Locked R7 Human-Validation Methodology  
**Relevance Scale:** Ordinal (`0`, `1`, `2`) + Explicit Evidence Failure (`NA`)

---

## 1. Core Principle

Judges must evaluate each candidate Place of Interest (POI) strictly with respect to:
1. The **Scenario Destination** (e.g. Hà Nội, Đà Nẵng, Hạ Long)
2. The **Declared User Interests** (e.g. `['food_cuisine']`, `['culture_history', 'nature_outdoor']`)
3. The **Factual POI Information** presented in the package

Judges must **never** infer or guess which recommendation algorithm or model generated the candidate.
Judges must **never** treat the category label mechanically as the final answer. For example, `category=cafe` does not automatically warrant label `2` for an interest in `coffee_culture`; full factual context (cuisine, specialty, description, address) should be evaluated.

---

## 2. Ordinal Relevance Scale

| Label | Designation | Authoritative Definition |
| :---: | :--- | :--- |
| **`0`** | **NOT_RELEVANT** | No reasonable factual evidence indicates that this POI matches the declared interests in this destination scenario. Recommending this item would be perceived as unhelpful, out-of-scope, or irrelevant to the user's declared travel goals. |
| **`1`** | **RELEVANT** | There is clear or reasonable factual evidence that the POI matches at least one declared interest and could be an appropriate recommendation. It provides a credible, valid option satisfying user preferences. |
| **`2`** | **HIGHLY_RELEVANT** | There is strong, direct, and clearly supported factual evidence that the POI matches the declared interests and would reasonably deserve prioritization. It exemplifies a top-tier recommendation for the specified travel intent. |
| **`NA`** | **INSUFFICIENT_EVIDENCE** | The presented factual metadata is insufficient to make a responsible, evidence-grounded relevance judgment (e.g., place is an unverified point with no descriptive details, ambiguity prevents determining what the venue is). |

---

## 3. Critical Scientific Boundaries

> [!IMPORTANT]
> **`NA != 0` (NA is NOT zero)**  
> An `NA` label represents an absence of factual evidence, not evidence of irrelevance.  
> Under no circumstances may `NA` be silently cast to numeric `0`. Doing so distorts recall and biases NDCG metrics. Any item receiving an `NA` judgment triggers adjudication or exclusion from numeric ranking calculations.

- **Independent Judging:** Each judge must complete their assigned package independently without consulting peer judges or viewing peer labels.
- **No External Searching:** Judges must rely strictly on the factual context provided in the evaluation package. External search engines or LLMs must not be queried during annotation.
