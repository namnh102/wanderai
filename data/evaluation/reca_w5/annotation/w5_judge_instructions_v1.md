# W5 Human Judge Instructions

**Rubric Version:** `W5-RUBRIC-V1`  
**Evaluation Scope:** 30 Primary Scenarios (474 Candidate Pool Items)  
**Assigned Roles:** Independent Human Evaluators (`J1`, `J2`, `J3`)

---

## 1. Mission Overview

You are evaluating candidate Places of Interest (POIs) recommended for travelers visiting specific destinations in Vietnam with explicit declared travel interests.

Your task is to assign an independent relevance grade to each POI based solely on the presented factual information.

---

## 2. Evaluation Rules

1. **Target Query:** For every item, read the `destination` and the list of `declared_interests`.
2. **Review Factual POI Details:**
   - Review the place name, street address, category, opening hours, and OSM factual tags (e.g., cuisine, tourism specialty, heritage designation, website).
   - If factual details indicate a match with the user's declared interests, assign `1` (Relevant) or `2` (Highly Relevant).
   - If factual details indicate no match, assign `0` (Not Relevant).
   - If factual metadata is too sparse or vague to responsibly assess relevance, assign `NA` (Insufficient Evidence).
3. **No Mechanical Category Matching:**
   - Do **NOT** use category labels blindly as the sole answer.
   - Example: A general supermarket might be categorized as `shop`, but unless it offers local specialties or culinary goods matching declared food interests, it should not automatically be rated `2`.
   - Consider the whole factual picture.
4. **Strict Independence:**
   - Do not collaborate with other judges during the annotation process.
   - Do not inspect another judge's completed files.
5. **No Model Guessing:**
   - Do not attempt to guess whether an item was produced by REC-A0, REC-A1, or REC-A2. The presentation order has been permuted deterministically to prevent bias.
6. **Recording Notes:**
   - You may optionally record brief notes in `judge_note` for difficult or boundary cases to assist in subsequent adjudication discussions.
