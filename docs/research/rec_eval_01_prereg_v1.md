# REC-EVAL-01 Scientific Preregistration V1

**Title:** REC-EVAL-01 Scientific Preregistration V1<br>
**Status:** `FROZEN_BEFORE_HUMAN_GT`<br>
**Preregistration Version:** `REC-EVAL-01-PREREG-V1`<br>
**Roadmap Package:** `REC-EVAL-01` (Offline Recommender Evaluation & Cold-Start Split)<br>
**Target Repository:** `d:\Do_an\wanderai`<br>
**Base Commit SHA:** `6ef96664c994cb2c1da4d94820ee78f4b4b48805`<br>
**Original Experiment Base Commit:** `6ef96664c994cb2c1da4d94820ee78f4b4b48805`<br>
**Source Implementation Commit SHA:** `35f82b30aa474d33036df656d70528dc20328d39`<br>
**Source Commit SHA:** `35f82b30aa474d33036df656d70528dc20328d39`<br>
**Artifact Hash Basis:** `sha256_git_committed_blob_content`<br>
**Methodology Owner & PASS/FAIL Gatekeeper:** ChatGPT<br>
**Implementation & Evidence Agent:** Antigravity<br>

---

## 1. Executive Summary & Scientific Purpose

This preregistration package establishes and freezes the formal scientific evaluation protocol for the **REC-EVAL-01** offline recommender evaluation milestone within the GoMate / WanderAI research track.

This protocol is frozen **BEFORE**:
1. Calibration execution begins.
2. Primary human relevance annotation commences.
3. Final human ground truth (`HUMAN-GT`) is constructed.
4. Real recommender model comparisons are executed.

### Critical Scientific Boundaries
* **Human Judgments Collected:** `0`
* **HUMAN-GT Available:** `NO`
* **Real NDCG / Metric Scores:** `NONE`
* **Real Model Comparison:** `NO`
* **Scientific Winner:** `UNKNOWN`
* **Calibration Status:** `NOT_STARTED`
* **Duplicate Policy Status:** `PENDING`
* **External Cross-Check Status:** `PENDING`

No synthetic relevance labels, rule-generated heuristics, or model predictions may serve as surrogate relevance ground truth. No scientific claims of algorithmic superiority may be made until all downstream gates (calibration, annotation, reliability gating, adjudication, duplicate resolution) are formally satisfied and audited.

---

## 2. Research Questions

This evaluation directly addresses four core research questions:

### RQ1 — Personalized Relevance (Primary Confirmatory Endpoint)
> *Does REC-A2 improve ranked recommendation relevance over the shared REC-A0/A1 baseline under the frozen REC-A evaluation protocol?*

* **Primary Empirical Evidence:** Graded Normalized Discounted Cumulative Gain at rank 10 ($NDCG@10$).
* **Role:** `PRIMARY_CONFIRMATORY`.
* **Secondary Evidence:** Precision@10, Pooled Recall@10, HitRate@10.

### RQ2 — Structural Diversity (Secondary Supporting Endpoint)
> *Does REC-A2 change list composition toward greater structural category diversity without demonstrated relevance degradation?*

* **Primary Empirical Evidence:** Category Intra-List Distance at rank 10 ($Category-ILD@10$).
* **Role:** `SECONDARY_SUPPORTING_STRUCTURAL_PROXY`.
* **Explicit Scientific Semantics:** `structural_category_diversity_proxy`.
* **Prohibitive Clarification:** This metric is strictly a structural category dispersion proxy across canonical catalog category labels. It is **explicitly NOT** a measure of semantic diversity, latent topic variety, human-perceived diversity, or traveler subjective satisfaction.

### RQ3 — Catalog Exposure (Secondary Supporting Endpoint)
> *Does REC-A2 change destination-normalized catalog coverage across the evaluation catalog?*

* **Primary Empirical Evidence:** Destination-Macro Catalog Coverage at rank 10 ($CatalogCoverage@10$), defined as the unweighted mean of destination-level unique POI coverage fractions across Hà Nội, Đà Nẵng, and Hạ Long.
* **Role:** `SECONDARY_SUPPORTING`.

### RQ4 — Cold-Start User Stratification (Exploratory Subgroup Analysis)
> *How do recommendation relevance and diversity trade-offs differ between single-interest (U1) and multi-interest (U2) cold-start traveler profiles?*

* **Role:** `EXPLORATORY_SUBGROUP_ANALYSIS`.
* **Strata:**
  * **U1:** Exactly one usable declared canonical interest.
  * **U2:** Two or more usable declared canonical interests.
* **Exclusion:** Unpersonalized zero-interest fallback profiles ($U0$) represent system fallback behavior and **must not** enter personalized relevance winner determinations. This exploratory question does not determine the final winner.

---

## 3. Hypotheses Structure & Inferential Framework

The evaluation separates confirmatory inference from secondary supporting and exploratory questions:

### A. Primary Confirmatory Hypothesis (RQ1 / NDCG@10)
Only the primary relevance endpoint ($NDCG@10$) is evaluated in a confirmatory hypothesis framework:
* **Null Hypothesis ($H_0$):** Destination-macro $\Delta_{NDCG@10} \le 0.0$.
* **Alternative Hypothesis ($H_1$):** Bootstrap evidence of a positive A2 relevance effect, operationalized when the pre-registered 95% bootstrap confidence interval lower bound strictly exceeds 0:
  $$CI_{lower}(\Delta_{NDCG@10}) > 0.0$$
* **Inferential Language Standard:** Results are interpreted as "bootstrap evidence of a positive effect" based on the pre-registered percentile confidence interval, rather than uncontextualized p-value significance claims.

### B. Secondary Supporting Endpoints (RQ2 / RQ3)
* **Category-ILD@10:** Measures whether REC-A2 produces higher structural category dispersion.
* **CatalogCoverage@10:** Measures whether REC-A2 achieves a positive destination-macro catalog coverage effect. Report HN/DN/HL individually as mandatory breakdowns.
* **Inferential Status:** These secondary endpoints are supporting only and are not evaluated as independently confirmatory significance tests. No multiplicity-controlled family-wise superiority claim is asserted across secondary metrics.

### C. Exploratory Question (RQ4 / U1 vs U2)
* Subgroup breakdowns across U1 (single-interest) and U2 (multi-interest) scenarios are designated as `EXPLORATORY_SUBGROUP_ANALYSIS`.
* Subgroup analyses provide diagnostic insight into algorithm behavior under constrained vs rich preference profiles; they do not determine the scientific winner.

---

## 4. Systems Under Comparison

The W5 evaluation compares exactly two algorithmic systems:

### 1. Scientific Baseline: `shared_a0_a1_baseline`
* **Definition:** Represents the effective shared baseline for the binary 7D preference model. Under the frozen binary 7-dimensional representation ($p_i \in \{0, 1\}^7$), REC-A0 (unweighted dot-product ranking) and REC-A1 (destination-filtered normalized cosine ranking) produce rank-equivalent orderings over candidate catalogs.
* **Implementation Note:** Concrete ranking evaluation executes `rec-a1` to instantiate this baseline.
* **Prohibition:** A0 and A1 **must not** be treated or counted as two independent competitive models in statistical inference or reporting.

### 2. Candidate System: `rec-a2`
* **Definition:** Deterministic Relevance-Preserving Multi-Interest Diversity Reranker.
* **Mechanism:** Selects high-relevance candidates matching declared user preferences while enforcing structural category dispersion to prevent single-category saturation in the top 10 recommendations.
* **Experimental Scope Exclusions:** Under this frozen W5 experiment, **no** collaborative filtering (CF), **no** latent semantic embeddings, **no** LLM-based reranking/prompts, **no** geographic distance reranking, and **no** machine-learned learning-to-rank (LTR) algorithms may be inserted or substituted.

---

## 5. Frozen Data Universe

All evaluation inputs, candidate pools, and catalogs derive immutably from the frozen curated catalog:

* **Curated Dataset Freeze:** `REC-A-CORE-V2` (`data/curated/gomate_places_freeze_v2.json`)
* **Total Core POIs:** `622`
  * **Hà Nội (`ha-noi`):** `145` POIs
  * **Đà Nẵng (`da-nang`):** `289` POIs
  * **Hạ Long (`ha-long`):** `188` POIs
* **Secondary POI Leakage:** `0` (Strictly verified: zero secondary/unverified places exist in the evaluation pool).
* **Primary Evaluation Scenarios:** `30`
  * **U1 Scenarios:** `15` (5 Hà Nội, 5 Đà Nẵng, 5 Hạ Long)
  * **U2 Scenarios:** `15` (4 Hà Nội, 6 Đà Nẵng, 5 Hạ Long)
  * **Destination Totals:** Hà Nội = 9, Đà Nẵng = 11, Hạ Long = 10
* **THIN Diagnostic Scenarios:** `6` (2 Hà Nội, 2 Đà Nẵng, 2 Hạ Long)
  * **Status:** `DIAGNOSTIC_ONLY`. THIN scenarios diagnose low-inventory edge cases and are strictly excluded from primary relevance superiority scoring.
* **Candidate Pool Records:** `474` unique `(scenario_id, place_id)` evaluation records across all 30 primary scenarios.
  * Sourced via `w5_candidate_pool_blinded_v1.json` and `w5_candidate_pool_internal_v1.json`.

---

## 6. User Strata Definitions

Traveler evaluation scenarios are partitioned into formal profile strata:

* **`U0` — Unpersonalized Baseline / Fallback:**
  * Zero declared canonical interests (`declared_interests = []`).
  * Represents system cold-start fallback behavior (popularity or editorial default).
  * **Exclusion:** Strictly excluded from personalized relevance superiority calculations.
* **`U1` — Single-Interest Cold-Start:**
  * Exactly one usable declared canonical interest (`len(declared_interests) == 1`).
  * Represents standard cold-start onboarding where a traveler selects one preference.
  * Primary evaluation stratum (15 scenarios).
* **`U2` — Multi-Interest Cold-Start:**
  * Two or more usable declared canonical interests (`len(declared_interests) >= 2`).
  * Evaluates richer preference representation and multi-intent diversification.
  * Primary evaluation stratum (15 scenarios).
* **`U_INVALID` — Malformed State:**
  * Unsupported, empty, or malformed preference payloads.
  * Handled via defensive validation; excluded from scientific evaluation.

---

## 7. Item Strata & Diagnostic Metric

Core places in `REC-A-CORE-V2` are partitioned by canonical 7D preference representation:

* **`I0` Items (Represented POIs):**
  * POIs possessing at least one nonzero component in their canonical 7D interest vector ($\|v_p\|_1 > 0$).
  * **Verified Count:** `405` POIs (65.11% of core catalog).
* **`I1` Items (Zero-Vector POIs):**
  * POIs possessing all-zero components in their canonical 7D interest vector ($\|v_p\|_1 = 0$), matching only destination criteria.
  * **Verified Count:** `217` POIs (34.89% of core catalog).

### Diagnostic Metric: $I1Exposure@10$
$$I1Exposure@10 = \frac{1}{10} \sum_{i=1}^{10} \mathbb{I}(\text{stratum}(item_i) == \text{'I1'})$$
* **Role:** `DIAGNOSTIC_ONLY`.
* **Prohibition:** $I1Exposure@10$ tracks how frequently unfeatured items enter top-10 recommendations due to tie-breaking or fallback. It **must not** be included in relevance superiority criteria or winner determination.

---

## 8. Ground-Truth Design & Human Relevance Protocol

Final relevance ground truth (`HUMAN-GT`) must derive exclusively from blind, independent human judging:

* **Prohibition on Synthetic Labels:** Synthetic relevance, LLM-generated labels, rule heuristics, or model scores **must not** serve as final ground truth.
* **Judge Panel:** Three independent human evaluators (`J1`, `J2`, `J3`).
* **Blinding Contract:** Judges receive blinded candidate packages (`w5_candidate_pool_blinded_v1.json`). Judges do not see algorithm names, system rankings, model scores, or control status.

### Relevance Scale Semantics
The annotation framework utilizes a **three-level ordinal relevance scale** accompanied by an explicit **non-ordinal missingness code**:

* **Three-Level Ordinal Scale:**
  * **`0` (NOT_RELEVANT):** No reasonable factual evidence indicates that this POI matches the declared interests in this destination scenario.
  * **`1` (RELEVANT):** Clear or reasonable factual evidence indicates that the POI matches at least one declared interest and could be an appropriate recommendation.
  * **`2` (HIGHLY_RELEVANT):** Strong, direct, and clearly supported factual evidence indicates that the POI matches the declared interests and would reasonably deserve prioritization.
* **Non-Ordinal Missingness Code:**
  * **`NA` (INSUFFICIENT_EVIDENCE):** The presented factual metadata is inadequate to make a responsible, evidence-grounded relevance judgment.

### Critical Semantic Guardrails
* **NA is NOT an ordinal relevance level:** NA has no position above, below, or between 0, 1, and 2.
* **NA != 0:** NA represents absence of factual evidence, not evidence of irrelevance. Under no circumstances may NA be cast to numeric 0.
* **Reliability Treatment:** NA observations are treated strictly as missing data in ordinal reliability calculations.

### Consensus & Adjudication Decision Table

Consensus ground-truth derivation follows this frozen decision policy:

| Case | Condition on Raw Primary Labels ($J_1, J_2, J_3$) | Consensus Action | Status | Adjudication Required |
| :---: | :--- | :--- | :--- | :---: |
| **Case A** | All 3 labels are numeric ($0, 1, 2$) **AND** $\max - \min < 2$ | $\text{label}_{GT} = \text{median}(J_1, J_2, J_3)$ | `RESOLVED_BY_MEDIAN` | **NO** |
| **Case B** | All 3 labels are numeric ($0, 1, 2$) **AND** $\max - \min = 2$ | Final relevance remains null | `PENDING_ADJUDICATION` | **YES** (Severe Disagreement) |
| **Case C** | **ANY** judge assigned `NA` ($\exists i: J_i = \text{NA}$) | Final relevance remains null (DO NOT compute median from the remaining numeric labels) | `PENDING_EVIDENCE_ADJUDICATION` | **YES** (Evidence Adjudication) |

* **Adjudicator Output Policy:**
  * If the blind adjudicator resolves the item with a numeric label ($0, 1, 2$), that label becomes final consensus relevance.
  * If the adjudicator confirms factual context is insufficient, final relevance is set to `NA`.
  * Under no circumstances may numeric relevance be invented for unresolved evidence items.

---

## 9. Calibration Contract

Before annotating primary evaluation records, all judges must complete the calibration package:

* **Artifact:** `data/evaluation/reca_w5/annotation/w5_calibration_v1.json` (`W5-CALIBRATION-V1`)
* **Scenarios:** Dedicated scenarios `CAL-HN-01`, `CAL-DN-01`, `CAL-HL-01`.
* **Items:** 45 total calibration items (15 per destination scenario).
* **Isolation Guarantee:** Calibration scenarios and place IDs are strictly **disjoint** from the 30 primary scenarios and 474 primary candidate pool records.
* **Role:** `CALIBRATION_ONLY`.
* **Purpose:** Rubric alignment, anchor interpretation, and boundary discussion. Calibration results are not scored against models, do not create `HUMAN-GT`, and do not tune REC-A2.

---

## 10. Human Metadata Qualification

The factual context available to human judges was audited in `w5_metadata_sufficiency_v1.json`:

* **Total Records Audited:** `474`
* **Sufficient Factual Context:** `389` records (82.07%)
* **Limited Factual Context:** `85` records (17.93%)
* **Insufficient Factual Context:** `0` records (0.00%)
* **Prose Description Coverage:** `0` / 474 (0.00%)
* **Audit Gate Verdict:** `PASS_WITH_QUALIFICATION`
* **Operational Rule:** Because prose description coverage is 0% and 85 items possess limited factual context (only category or partial address), the `NA` label option must remain accessible to judges. Metadata sufficiency status must **never** be used as a proxy for relevance.

---

## 11. Primary Relevance Metric: $NDCG@10$

Ranked recommendation quality is measured primarily via Graded Normalized Discounted Cumulative Gain at rank 10:

### 1. Graded Gain Function
$$gain(rel) = 2^{rel} - 1$$
* $rel = 0 \implies gain = 0$
* $rel = 1 \implies gain = 1$
* $rel = 2 \implies gain = 3$

### 2. Discounted Cumulative Gain ($DCG@10$)
$$DCG@10 = \sum_{i=1}^{10} \frac{2^{rel_i} - 1}{\log_2(i + 1)}$$
where $rel_i$ is the ground-truth relevance grade of the item recommended at rank $i$.

### 3. Ideal Discounted Cumulative Gain ($IDCG@10$)
$$IDCG@10 = \sum_{i=1}^{\min(10, |\mathcal{P}_{sc}|)} \frac{2^{rel_{(i)}} - 1}{\log_2(i + 1)}$$
where $rel_{(i)}$ denotes the $i$-th highest relevance grade among all numerically judged items in the common scenario candidate pool $\mathcal{P}_{sc}$.

### 4. Normalized Score
$$NDCG@10 = \frac{DCG@10}{IDCG@10}$$

---

## 12. IDCG Zero Policy & Missingness Handling

* **Zero-Relevance Pools ($IDCG@10 = 0$):**
  * When no item in the candidate pool receives a relevance label $\ge 1$, $IDCG@10 = 0$.
  * Mathematical division by zero is avoided by assigning:
    $$NDCG@10 = \text{null (None)}, \quad \text{status} = \text{'NO_RELEVANT_ITEM_IN_JUDGED_POOL'}$$
  * **Prohibition:** $NDCG@10$ **must not** be set to 0. A scenario with zero relevant candidates in the pool does not indicate algorithmic ranking failure.
  * **Treatment:** Such scenarios are recorded in sample attrition and excluded from the $NDCG$ arithmetic mean.
* **Unresolved Ranked Items:**
  * If any item in a model's top 10 contains an `NA` judgment or missing label, the ranking cannot be scored honestly without bias.
  * Status: `NOT_SCORABLE_UNRESOLVED_TOPK`, $NDCG@10 = \text{null}$.
  * **Prohibition:** Never cast `NA` to 0. Never drop the item and shift subsequent ranks upward.

---

## 13. Secondary Relevance Metrics

All secondary relevance metrics apply binary relevance thresholding: an item is relevant if and only if $rel \ge 1$.

### 1. $Precision@10$
$$Precision@10 = \frac{1}{10} \sum_{i=1}^{10} \mathbb{I}(rel_i \ge 1)$$

### 2. $Pooled\ Recall@10$
$$Pooled\ Recall@10 = \frac{\sum_{i=1}^{10} \mathbb{I}(rel_i \ge 1)}{\sum_{p \in \mathcal{P}_{sc}} \mathbb{I}(rel_p \ge 1)}$$
* **Critical Terminology Guardrail:** This metric **must NEVER be termed "Full-Catalog Recall@10"**. Relevance judgments are pooled over the top candidates of evaluated systems and controls (474 records across 30 scenarios), not exhaustively across all 622 catalog POIs.

### 3. $HitRate@10$
$$HitRate@10 = \mathbb{I}\left(\sum_{i=1}^{10} \mathbb{I}(rel_i \ge 1) > 0\right)$$

---

## 14. Beyond-Accuracy & Diversity Metrics

### 1. $Category-ILD@10$ (Structural Diversity Proxy)
Measures pairwise category dispersion within the top 10 recommendations:
$$Category-ILD@10 = \frac{2}{K(K-1)} \sum_{i=1}^{K-1} \sum_{j=i+1}^K d_{cat}(c_i, c_j)$$
where $K = 10$, $c_i$ is the canonical catalog category of the item at rank $i$, and:
$$d_{cat}(c_i, c_j) = \begin{cases} 0 & \text{if } c_i = c_j \\ 1 & \text{if } c_i \ne c_j \end{cases}$$
* **Semantics:** Locked as `structural_category_diversity_proxy`.

### 2. $CatalogCoverage@10$ (Destination-Normalized Coverage)
For destination $d \in \{\text{ha-noi}, \text{da-nang}, \text{ha-long}\}$:
$$Coverage_d = \frac{|\bigcup_{s \in \mathcal{S}_d} \text{Top10}(s)|}{|\mathcal{C}_d|}$$
where $\mathcal{S}_d$ is the set of scenarios in destination $d$, and $|\mathcal{C}_d|$ is the catalog size ($145, 289, 188$).
* **Primary Aggregate (Macro-Coverage):**
  $$MacroCoverage = \frac{1}{3} (Coverage_{\text{ha-noi}} + Coverage_{\text{da-nang}} + Coverage_{\text{ha-long}})$$
* **Prohibition:** Must not be replaced by catalog-size-weighted global unique coverage. Equal destination weighting is mandatory.

---

## 15. Primary Aggregation Strategy

Evaluation is structured hierarchically at the scenario level:

1. **Scenario Score:** Compute metric $M(s)$ for each valid scenario $s$.
2. **Destination Mean:** Compute arithmetic mean of scorable scenarios within each destination:
   $$\bar{M}_d = \frac{1}{|\mathcal{S}_{d,valid}|} \sum_{s \in \mathcal{S}_{d,valid}} M(s)$$
3. **Primary Overall Macro-Score:**
   $$\bar{M}_{macro} = \frac{1}{3} (\bar{M}_{\text{ha-noi}} + \bar{M}_{\text{da-nang}} + \bar{M}_{\text{ha-long}})$$
* **Secondary Descriptive Score:** Unweighted all-scenario mean is reported as secondary.

---

## 16. Mandatory Reporting Breakdowns

All evaluation reports must present metrics across these required breakdowns:
1. **Overall Macro:** Equal-destination weighted average.
2. **Hà Nội (`ha-noi`):** Destination cohort.
3. **Đà Nẵng (`da-nang`):** Destination cohort.
4. **Hạ Long (`ha-long`):** Destination cohort.
5. **U1 Stratum:** Single-interest cold-start cohort.
6. **U2 Stratum:** Multi-interest cold-start cohort.

Every cell must report: total scenarios, scorable scenarios, and excluded/unresolved count.

---

## 17. Statistical Inference: Paired Stratified Bootstrap

Primary model comparison evaluates the paired difference:
$$\Delta_M = M(\text{REC-A2}) - M(\text{shared\_baseline})$$

### Bootstrap Protocol
* **Method:** Paired, scenario-level, destination-stratified bootstrap.
* **Replicates:** $B = 10,000$.
* **Seed:** `20261013`.
* **Resampling Procedure:**
  * For each destination $d \in \{\text{ha-noi}, \text{da-nang}, \text{ha-long}\}$:
    * Resample $N_d$ scenarios with replacement from $\mathcal{S}_{d,scorable}$.
    * Maintain exact paired alignment: for scenario $s$, pair $(M_{A2}(s), M_{baseline}(s))$.
    * Compute destination replicate delta $\Delta_{M,d}^{*b}$.
  * Compute replicate macro delta:
    $$\Delta_M^{*b} = \frac{1}{3} \sum_{d} \Delta_{M,d}^{*b}$$
* **Confidence Interval:** 95% percentile interval $[P_{2.5}(\Delta^*), P_{97.5}(\Delta^*)]$.
* **Point Estimate:** The observed sample point delta $\Delta_M^{obs}$ is the primary effect estimate. The bootstrap mean is reported only as a diagnostic distribution check.

---

## 18. Missing Destination Inference Policy

* If any required destination ($HN, DN, HL$) has zero paired scorable scenarios due to unresolved judgments or zero-relevance pools:
  * **Status:** `PRIMARY_INFERENCE_NOT_ESTIMABLE`
  * **Prohibition:** Missing destination deltas **must NEVER be imputed as 0**.
  * **Scientific Verdict:** Mandates `INCONCLUSIVE` with explicit cause `PRIMARY_INFERENCE_NOT_ESTIMABLE`.

---

## 19. Final Scientific Verdict Rules & Interpretation

Final verdict classification between REC-A2 and shared baseline is governed by four mutually exclusive rules:

| Verdict Label | Authoritative Trigger Condition |
| :--- | :--- |
| **`A2_RELEVANCE_SUPERIOR`** | 95% CI lower bound for destination-macro $\Delta_{NDCG@10} > 0.0$ |
| **`BASELINE_PREFERRED`** | 95% CI upper bound for destination-macro $\Delta_{NDCG@10} < 0.0$ |
| **`A2_DIVERSITY_TRADEOFF`** | 95% CI for $\Delta_{NDCG@10}$ spans 0.0 **AND** either:<br>(1) $\Delta_{ILD}$ CI lower bound $> 0.0$ and $\Delta_{Cov}$ point delta $\ge 0.0$, OR<br>(2) $\Delta_{Cov}$ CI lower bound $> 0.0$ and $\Delta_{ILD}$ point delta $\ge 0.0$ |
| **`INCONCLUSIVE`** | All other outcomes (e.g., CI spans 0 with no diversity/coverage gains, CI spans 0 with mixed degradation, or primary inference is not estimable) |

### Strict Inferential Interpretation Guardrails
* **No Equivalence Claim:** When the 95% CI for $\Delta_{NDCG@10}$ contains 0, it means that the relevance difference is not demonstrated / remains inconclusive.
* **Prohibition on "Parity" or "Non-Inferiority":** An interval containing zero does NOT establish relevance parity, equivalence, or non-inferiority. No non-inferiority margin has been preregistered.
* **Meaning of `A2_DIVERSITY_TRADEOFF`:** Indicates pre-registered evidence of improved structural diversity or coverage, while the primary relevance difference remains inconclusive.
* **Baseline Preference Requirement:** Evidence of baseline preference (or A2 relevance degradation) requires $CI_{upper}(\Delta_{NDCG@10}) < 0.0$, matching the metric runner logic.
* **Immutable Guardrail:** No composite utility scores. No altering or softening of verdict rules once human judgments are collected.

---

## 20. Reliability Analysis & Adjudication Contract

### Inter-Rater Reliability Protocol
* **Metric:** Ordinal Krippendorff's Alpha ($\alpha$) computed over the 3-judge rating matrix.
* **Input Data:** Raw independent $J_1, J_2, J_3$ labels **before** adjudication.
* **Ordinal Categories:** Strictly numeric $0, 1, 2$. Missing code `NA` is treated as a missing observation, not a fourth ordinal level.
* **Bootstrap Uncertainty:** 95% bootstrap confidence interval (10,000 unit resamples, seed `20261013`).
* **Operational Reliability Gates:**
  * $\alpha \ge 0.80$: `GOOD` (Authoritative agreement).
  * $0.67 \le \alpha < 0.80$: `USABLE_WITH_QUALIFICATION` (Sufficient for exploratory evaluation with caveats).
  * $\alpha < 0.67$: `STOP_REVIEW_RUBRIC` (Inadmissible agreement; annotation must halt).
* **Execution Blocker:** If the reliability gate is not satisfied, final model comparison **must not proceed**.

### Adjudication Contract
* **Scope:** Severe disagreements ($\|j_a - j_b\| = 2$) and designated unresolvable cases (Case B and Case C).
* **Adjudicator Visibility:** Scenario destination, declared interests, factual POI metadata, anonymous judge ratings, rubric.
* **Adjudicator Blindness:** Adjudicator is strictly blinded to algorithm identity, recommendation rank, score, system strategy, and control status.

---

## 21. HUMAN-GT Freeze Contract & Rubric Versioning

### Rubric Versioning Contract
* **Current Pre-Calibration Rubric:** `W5-RUBRIC-V1`.
* **Immutability of V1:** W5-RUBRIC-V1 is immutable and must never be edited in place after preregistration.
* **Clarification via Calibration:** If calibration reveals wording ambiguities, a **new versioned artifact** (e.g., `W5-RUBRIC-V1.1`) will be created through a formal methodology amendment.
* **Final Primary Rubric:** Primary human judging will use one final frozen rubric version.

### Future HUMAN-GT Requirements
The future human ground truth artifact must fulfill all of the following requirements:
* **`gt_version`:** `HUMAN-GT-V1`
* **`status`:** `FROZEN`
* **`pool_version`:** `W5-POOL-V1`
* **`rubric_version`:** Reference the exact final frozen rubric version used for primary annotation (not rigidly hard-coded to V1).
* **`metadata_version`:** `W5-METADATA-V1`
* **Item Universe:** Exactly 474 unique `(scenario_id, place_id)` keys.
* **Completeness:** Reliability gate PASSED or qualified; all severe disagreements and NA cases adjudicated.
* **Immutability:** No post-freeze modifications permitted except through versioned errata artifacts.

---

## 22. Downstream Dependencies & External Cross-Checks

* **Duplicate Policy Dependency (`W5-GATE-DUP`):**
  * Current status: `duplicate_policy_status = PENDING`.
  * No duplicate pairs or duplicate equivalence maps are activated in this task.
  * Closing `W5-GATE-DUP` is a mandatory prerequisite for running final scientific scoring.
* **External Research Cross-Check:**
  * `R8A`: COMPLETE.
  * `Researcher-1 / R8B`: `PENDING` (must be formally resolved or designated contingency before primary human annotation begins).

---

## 23. Methodology Amendment From Initial Roadmap

### Historical Repository Evidence
The project documentation reflects evolving metric definitions across several milestones:
* `docs/roadmap/gomate-thesis-research-roadmap-v1.md` (Week 5: Offline Recommender Evaluation & Cold-Start Analysis `REC-EVAL-01`): Defined broad metric families evaluating $NDCG@K$, $Recall@K$, $HitRate@K$, Coverage, and Diversity across warm vs cold-start splits.
* `docs/roadmap/gomate-product-research-alignment-matrix-v1.md` (Section 3.1: Capability 1.5 vs REC-01 / REC-EVAL-01): Classified offline evaluation as a mandatory thesis milestone computing $NDCG@K$ and $Recall@K$.
* `docs/recommendation/recommendation-pipeline.md` (Section 4): Documented historical ViHoRec engineering benchmark results evaluated at both K=5 and K=10 ($P@5, R@5, NDCG@5, P@10, R@10, NDCG@10$).
* `docs/audit/task-07.1-regression-audit.md`: Recorded regression verification of the historical ViHoRec K=5 and K=10 checkpoints.
* `docs/project-control/DECISIONS.md` (Decision D5): Recorded adoption of $NDCG@K$, $Recall@K$, $Precision@K$, $HitRate@K$, Coverage, and Diversity.

### Scientific Refinement & Amendment
The initial roadmap defined metric families parametrized by $K$, and historical engineering evaluations explored K=5 and K=10. Subsequent rigorous methodology review by the research team established that evaluating top-10 recommendation lists required stronger statistical validity and relevance grounding. The protocol was formally amended as follows:
1. **Selection of $K=10$:** The evaluation freezes $K=10$ as the primary list length for this experiment, representing the standard top-10 recommendation list presented to travelers.
2. **Pooled Recall Terminology:** Formally retitled from generic "Recall@10" to **"Pooled Recall@10"** to acknowledge that relevance is evaluated over a pooled candidate set rather than an exhaustive 622-item catalog census.
3. **Graded Human Relevance:** Upgraded to a 3-level ordinal scale ($0, 1, 2$) plus explicit non-ordinal missingness code (`NA`), with independent 3-judge panels and Krippendorff alpha reliability gating.
4. **Stratified Cold-Start Splits:** Operationalized concrete U1 (single-interest) and U2 (multi-interest) cohorts, excluding unpersonalized U0 from relevance superiority claims.
5. **Statistical Rigor:** Implemented paired, destination-stratified bootstrap (10,000 replicates) with strict destination-macro weighting and non-imputation missingness policies.

*This amendment represents a scientific refinement and hardening of evaluation rigor, building constructively upon the roadmap.*

---

## 24. Threats to Validity & Known Limitations

To maintain scientific integrity, the following limitations are explicitly preregistered:
1. **Destination Scope:** Evaluation is conducted across three Vietnamese destinations (Hà Nội, Đà Nẵng, Hạ Long); findings may not generalize immediately to rural or emerging tourism regions.
2. **Scenario Sample Size:** The primary evaluation cohort comprises 30 scenarios (15 U1, 15 U2); statistical power is constrained by sample size.
3. **Candidate Pooling Incompleteness:** Human judging is performed over the pooled candidate set (474 records), not the full $30 \times 622 = 18,660$ possible pairs. True full-catalog recall is unknown.
4. **Metadata Sparsity:** 85 of 474 candidate records possess limited factual metadata, and 0 have prose descriptions, necessitating the `NA` label option.
5. **Structural Diversity Proxy:** $Category-ILD@10$ measures dispersion across coarse catalog categories and does not capture nuanced experiential or semantic diversity.
6. **Zero-Vector POIs:** 217 of 622 POIs in `REC-A-CORE-V2` have zero canonical 7D preference vectors ($I1$ items), relying on fallback selection.
7. **Absence of User Interaction Logs:** Natural user click and booking interactions are unavailable offline, precluding native collaborative filtering.
8. **Catalog Scope:** Conclusions apply strictly to the frozen `REC-A-CORE-V2` catalog and content-based recommendation mechanisms.

---

## 25. Artifact & Provenance Checksums

All configuration and baseline inputs are locked against the following single-valued SHA256 checksums, computed from committed Git blob content at source implementation commit `35f82b30aa474d33036df656d70528dc20328d39` (original experiment base commit `6ef96664c994cb2c1da4d94820ee78f4b4b48805`):

| Artifact Path | Description | Canonical Committed Blob SHA256 |
| :--- | :--- | :--- |
| `data/curated/gomate_places_freeze_v2.json` | Curated POI Catalog Freeze V2 (622 core places) | `f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444` |
| `data/evaluation/reca_w5/w5_primary_scenarios_v1.json` | 30 Primary Scenarios (15 U1, 15 U2) | `4f0c77dccc2c0bae32f5d87f1364a8e1487a83e9b7344a9d8d3c9d0528bc29fb` |
| `data/evaluation/reca_w5/w5_thin_diagnostic_scenarios_v1.json` | 6 THIN Diagnostic Scenarios | `538233a937acdd38ea208980a9ba629391b61e721363189f10f6087186fcfa77` |
| `data/evaluation/reca_w5/w5_candidate_pool_internal_v1.json` | Internal Candidate Pool Manifest (474 records) | `32b25ef8ffc19d671513f771d3d3a0d23ceb9d0cf614ace1eded94d8c84126c6` |
| `data/evaluation/reca_w5/w5_candidate_pool_blinded_v1.json` | Blinded Candidate Pool Presentation | `8f178e06b1b93e59b3a53f1b2bf1b6ecc697ccfa610d56783b613b6aa2f06ec7` |
| `data/evaluation/reca_w5/w5_reproducibility_manifest_v1.json` | Reproducibility & Control Seed Manifest | `ae2cbb97689148274723617e00a833093971c5f7cc11c7cdec39ec19619f6388` |
| `data/evaluation/reca_w5/annotation/w5_rubric_v1.md` | Relevance Rubric Specification (0/1/2/NA) | `98601330b366ea99b2254509adf84762375460ab66a93ef3af2ef32df63ef8a4` |
| `data/evaluation/reca_w5/annotation/w5_judge_instructions_v1.md` | Human Judge Instructions | `5d579d4c0b76a9c37eadac869db6e4f6abaa6c8c36f146d3176452d1fc56b4bb` |
| `data/evaluation/reca_w5/annotation/w5_calibration_v1.json` | 45-Item Calibration Package (Disjoint) | `598bde75d464f3e58299522090833a8521a59d4c0755e13399ad46050a2ca823` |
| `data/evaluation/reca_w5/annotation/w5_annotation_manifest_v1.json` | Annotation Presentation Manifest | `9fa7e9e66f331e881cdb6cae0d29eecdfd77fe6cfa2108dad07a68c3fadde106` |
| `data/evaluation/reca_w5/annotation/w5_metadata_sufficiency_v1.json` | Factual Context Sufficiency Audit | `c58f9a709cb338596536fae78ae444e9c8de9e070cf3b8449cbba64fe05fa989` |
| `data/evaluation/reca_w5/annotation/w5_merged_ground_truth_template_v1.json` | Consolidated Ground Truth Schema Template | `3f33c6f866dec90f33212c5851a389ecc0b0f10d6e9da8ab8077aa8e305ab830` |
| `scripts/evaluate_w5_recommenders.py` | Metric Runner & Scientific Evaluation Pipeline | `ec494c7b8f2cea7eb28e78816c4ad2ae88e52aa5221878cf686d7796e85527d6` |
| `scripts/analyze_w5_judgments.py` | Reliability Tooling & Krippendorff Alpha Calculator | `f2f748c8ae6e178ae7f380b662eebb3a37c4166e5cbbed0a60cdf5cd2190d82c` |
