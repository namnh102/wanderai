# W5 Human Calibration Operational Protocol V1

**Title:** W5 Human Calibration Operational Protocol V1<br>
**Document Version:** `W5-CAL-OPS-DOC-V1`<br>
**Presentation Version:** `W5-CAL-OPS-V1`<br>
**Calibration Source Version:** `W5-CALIBRATION-V1`<br>
**Rubric Version:** `W5-RUBRIC-V1`<br>
**Pool Version:** `W5-POOL-V1`<br>
**Retained Preregistration:** `REC-EVAL-01-PREREG-V1`<br>
**Target Repository:** `d:\Do_an\wanderai`<br>
**Base Commit SHA:** `8e6e35c51c66aacabe6aada52e59457978fdb9b3`<br>
**Methodology Owner & Gatekeeper:** ChatGPT<br>
**Implementation & Evidence Agent:** Antigravity<br>

---

## 1. Purpose & Calibration-Only Scope

This document defines the blinded, reproducible operational protocol for executing the three-judge human calibration phase (`W5-CALIBRATION-V1`) prior to launching primary relevance annotation for `REC-EVAL-01`.

### Calibration-Only Contract
* **Role / Track:** `CALIBRATION_ONLY` (`excluded_from_final_metrics: true`)
* **Purpose:**
  * Rubric alignment
  * Anchor interpretation
  * Boundary discussion
* **Calibration Scenarios:** 3 dedicated scenarios:
  * `CAL-HN-01` (`ha-noi`: `["food_cuisine", "nightlife_entertainment"]`, 15 items)
  * `CAL-DN-01` (`da-nang`: `["food_cuisine", "beach_island"]`, 15 items)
  * `CAL-HL-01` (`ha-long`: `["culture_history", "coffee_culture"]`, 15 items)
* **Total Calibration Items:** `45` unique items (`15` per scenario)
* **Strict Disjointness from Primary Evaluation:**
  * **Scenario Overlap with 30 Primary Scenarios:** `0`
  * **Place ID Overlap with 474 Primary Candidate Pool Records:** `0`

Calibration does **not** create `HUMAN-GT` and does **not** determine the recommender model winner. Calibration items are strictly excluded from final recommender evaluation metrics (`NDCG@10`, `Precision@10`, `Pooled Recall@10`, `HitRate@10`, `Category-ILD@10`, `CatalogCoverage@10`, `I1Exposure@10`) and winner determination.

### Current Execution State
* **Calibration Status:** `NOT_STARTED`
* **Human Judgments Collected:** `0`
* **Human Ground Truth (`HUMAN-GT`):** `NO`
* **R8B Status:** `CLOSED_BY_CONTINGENCY` (`CLOSED_WITHOUT_EXTERNAL_REPORT`)
* **Final Method Decision:** `METHOD_RETAINED`
* **Duplicate Policy Status:** `CLOSED_NO_PRIMARY_EVAL_IMPACT`
* **Scientific Winner:** `UNKNOWN`

---

## 2. Judge Pseudonyms & Privacy Boundary

All human evaluators are identified exclusively by fixed pseudonyms throughout the repository, operational packages, session logs, and audit reports:

* **`J1`** — Independent Human Judge 1
* **`J2`** — Independent Human Judge 2
* **`J3`** — Independent Human Judge 3

**Privacy & Anonymity Rule:** Real person names, email addresses, or personal identifiers must **never** be committed to the repository.

---

## 3. Judge Independence & Non-Contamination Requirements

1. **Strict Pre-Submission Independence:** Each judge (`J1`, `J2`, `J3`) must complete all 45 calibration judgments independently.
2. **No Discussion Before All Three Submissions Complete:** Judges are strictly prohibited from discussing scenarios, Places of Interest (POIs), edge cases, or label interpretations with one another until all three completed submissions and session logs have been validated and locked by the coordinator.
3. **No Peer Label Inspection:** No judge may view another judge's in-progress or completed calibration package prior to the post-submission calibration review phase.
4. **No LLM Labeling:** No Large Language Model (LLM), automated script, or heuristic rule may be used to generate, suggest, or pre-fill human relevance labels.
5. **Closed Factual Context Only:** Judges must rely strictly on the factual context presented inside their assigned calibration package. External web searches, map lookups, review portals, or external databases must not be consulted during calibration.

---

## 4. Blinding & Read-Only Context Immutability

To prevent confirmation bias, position bias, and system leakage, all judge-visible calibration packages enforce strict blinding and read-only context immutability:

### A. What Judges May See (Approved Factual Context Only)
Each calibration item exposes only approved factual fields:
* `judge_id` (`J1`, `J2`, or `J3`)
* `calibration_version` (`W5-CALIBRATION-V1`)
* `rubric_version` (`W5-RUBRIC-V1`)
* `presentation_version` (`W5-CAL-OPS-V1`)
* `scenario_id` (`CAL-HN-01`, `CAL-DN-01`, or `CAL-HL-01`)
* `presentation_index` (`1..15` within scenario) and `global_presentation_index` (`1..45` across package)
* `calibration_item_id` / `judge_item_id` (e.g., `CAL-HN-01-J05`)
* `place_id` (canonical UUID)
* `destination` (`ha-noi`, `da-nang`, or `ha-long`)
* `declared_interests` (scenario travel interest list)
* `name` (curated POI display name)
* `category` (curated primary category)
* `factual_context`:
  * `name`, `category`, `destination`, `destination_slug`
  * `address` (when available)
  * `latitude`, `longitude` (WGS84 coordinates)
  * `opening_hours` (when available)
  * `osm_source` (`source_name`, `source_id`)
  * `osm_factual_tags` (allowlisted raw factual OSM tags)
* Editable fields initialized to `null` (JSON) or blank `""` (CSV):
  * `label`
  * `judge_note`

### B. Read-Only Context Immutability Contract
* **Read-Only Policy:** `EXACT_MATCH_TO_FROZEN_PRESENTATION_PACKAGE`
* **Editable Fields:** Only `label` and `judge_note` may be modified in a completed submission.
* **Read-Only Mutation Handling:** `REJECT`
* **Enforcement Mechanism:** Scientific protection is enforced programmatically by `scripts/validate_w5_calibration_submission.py`, which verifies that every top-level, scenario-level, item-level, `factual_context`, and CSV `READ-ONLY CONTEXT` field matches the judge's deterministic reference presentation package. No spreadsheet-level XLSX cell locking is claimed; any mutation to a read-only field in JSON or CSV causes immediate validator rejection.

### C. What Judges Must NOT See (Forbidden Leakage Fields)
Judge-visible packages strip and forbid all model, ranking, scoring, control, and internal diagnostic fields:
* `model`, `model_id`, `model_identity`, `source_systems`
* `strategy`
* `rank`
* `score`, `confidence_score`, `similarity_score`
* `baseline_membership`, `a2_membership`
* `is_control`, `control_flag`
* `canonical_interest_vector`, `canonical_active_interests`, `matched_interests`
* `metadata_sufficiency`, `sufficiency_status`, `sufficiency_reason`
* `duplicate_group`, `duplicate_equivalence_group`, `duplicate_group_status`
* `recommendation_explanation`
* `tier_1`, `tier_2`, `legacy_category`

### D. Deterministic Independent Presentation Ordering
All three judge packages (`J1`, `J2`, `J3`) contain the exact same 45 canonical calibration items, but items within each scenario are ordered independently per judge using a SHA256-derived deterministic key:

$$\text{order\_key}(\text{scenario\_id}, \text{judge\_id}, \text{judge\_item\_id}) = \text{SHA256}(\texttt{"20261013:"} \parallel \text{scenario\_id} \parallel \texttt{":"} \parallel \text{judge\_id} \parallel \texttt{":calibration-presentation:"} \parallel \text{judge\_item\_id})$$

* Python's randomized `hash()` is **never** used.
* No model or ranking information is used when ordering.

---

## 5. Allowed Labels & `NA` Semantics

Judges must assign exactly one label from the frozen rubric (`W5-RUBRIC-V1`) to each of the 45 calibration items:

| Label | JSON Type & Value | CSV Representation | Designation | Operational Definition |
| :---: | :---: | :---: | :--- | :--- |
| **`0`** | integer `0` | `0` | `NOT_RELEVANT` | No reasonable factual evidence indicates that the POI matches the declared interests in this destination scenario. |
| **`1`** | integer `1` | `1` | `RELEVANT` | Clear or reasonable factual evidence indicates that the POI matches at least one declared interest and is a credible option. |
| **`2`** | integer `2` | `2` | `HIGHLY_RELEVANT` | Strong, direct, and clearly supported factual evidence indicates that the POI matches the declared interests and deserves prioritization. |
| **`NA`** | string `"NA"` | `NA` | `INSUFFICIENT_EVIDENCE` | The provided factual metadata is insufficient to make a responsible, evidence-grounded relevance judgment. |

### Critical Semantic Rule: `NA != 0`
* **`NA` is a non-ordinal insufficient-evidence code.**
* **`NA != 0` (`NA` is NOT zero):** `NA` represents absence of sufficient factual evidence in the package, **not** evidence of irrelevance (`0`).
* `NA` must never be cast to `0` or treated as an ordinal rank below `0`.

---

## 6. Operational Package Inventory

All operational calibration artifacts reside in `data/evaluation/reca_w5/calibration_ops/`:

1. **Judge Presentation Packages (JSON):**
   * `data/evaluation/reca_w5/calibration_ops/w5_calibration_J1_v1.json`
   * `data/evaluation/reca_w5/calibration_ops/w5_calibration_J2_v1.json`
   * `data/evaluation/reca_w5/calibration_ops/w5_calibration_J3_v1.json`
2. **Human-Friendly Presentation Packages (CSV):**
   * `data/evaluation/reca_w5/calibration_ops/w5_calibration_J1_v1.csv`
   * `data/evaluation/reca_w5/calibration_ops/w5_calibration_J2_v1.csv`
   * `data/evaluation/reca_w5/calibration_ops/w5_calibration_J3_v1.csv`
   * Each CSV preserves the exact 45-item membership and presentation order of its corresponding JSON package.
   * Columns `1..20` (`judge_id` through `osm_factual_tags_json`) are **READ-ONLY CONTEXT** columns enforced by the submission validator.
   * Columns `21..22` (`label`, `judge_note`) are **EDITABLE** columns (initialized blank `""`, with zero spreadsheet formulas).
3. **Machine-Readable Submission Contract:**
   * `data/evaluation/reca_w5/calibration_ops/w5_calibration_submission_contract_v1.json`
4. **Session Log Template:**
   * `data/evaluation/reca_w5/calibration_ops/w5_calibration_session_log_template_v1.json`

---

## 7. Operational Procedures

### A. Session Procedure (Pre-Annotation & Execution)
1. **Distribution:** Each judge (`J1`, `J2`, `J3`) receives only:
   * `data/evaluation/reca_w5/annotation/w5_rubric_v1.md`
   * `data/evaluation/reca_w5/annotation/w5_judge_instructions_v1.md`
   * `docs/research/w5_calibration_ops_v1.md`
   * Their own assigned package (`w5_calibration_J<k>_v1.json` or `w5_calibration_J<k>_v1.csv`)
   * A copy of `w5_calibration_session_log_template_v1.json`
2. **Session Start:** The judge records `judge_id` (`"J1"`, `"J2"`, or `"J3"`) and the UTC ISO-8601 timestamp in `started_at` within their session log.
3. **Independent Annotation:** Working alone without external search or LLM assistance, the judge evaluates all 45 items across `CAL-HN-01`, `CAL-DN-01`, and `CAL-HL-01`, entering `0`, `1`, `2`, or `NA` in `label` and optional text in `judge_note` (recommended whenever `NA` or a boundary judgment is assigned).

### B. Version Recording Procedure
Every submission and session log must preserve and record exact version identifiers:
* `calibration_version`: `"W5-CALIBRATION-V1"`
* `rubric_version`: `"W5-RUBRIC-V1"`
* `presentation_version`: `"W5-CAL-OPS-V1"`

Any version mismatch is automatically rejected by `scripts/validate_w5_calibration_submission.py`.

### C. Submission Procedure
1. Upon completing all 45 items, the judge runs the standalone validator against their completed file:
   ```bash
   python scripts/validate_w5_calibration_submission.py --package <path-to-completed-submission>
   ```
2. The validator verifies:
   * Correct `judge_id` (`J1`, `J2`, or `J3`)
   * Exact version match (`W5-CALIBRATION-V1`, `W5-RUBRIC-V1`, `W5-CAL-OPS-V1`)
   * Exact 45 canonical item membership and deterministic judge presentation order (no missing, extra, or duplicate items)
   * Exact immutability of all read-only context fields against the judge's frozen reference presentation package (`EXACT_MATCH_TO_FROZEN_PRESENTATION_PACKAGE`; only `label` and `judge_note` may change)
   * Strict label validity (`0`, `1`, `2`, or `"NA"`; rejecting `null`/blank, booleans `True`/`False`, floats, numeric strings `"0"`/`"1"`/`"2"` in JSON, and lowercase `"na"` or aliases)
   * Zero forbidden leakage fields and zero spreadsheet formulas

### D. Session Completion Procedure, Truthful External-Help Recording & Independence Attestation
1. Once the submission validator reports `PASS`, the judge computes the SHA256 digest of their completed submission file and records it in `submission_sha256` in their session log.
2. The judge records the UTC ISO-8601 timestamp in `completed_at`, records any ambiguity notes in `issues_reported`, keeps `discussion_started: false` at submission time, and completes `independence_attestation`.
3. **Truthful Recording of `external_help_used`:**
   * In `w5_calibration_session_log_template_v1.json`, `external_help_used` is initialized to `null`.
   * Upon completion, the judge must record the **actual** value truthfully.
   * **Expected compliant value:** `false`.
   * **If external help was actually used:** the judge must record `true` — do **not** falsify it to `false`.
   * Any session recording `external_help_used: true` must be flagged for `W5-CAL-REVIEW` before qualification (no automatic silent repair).
4. **Mandatory Independence Attestation:** Each judge must explicitly attest to all six operational integrity statements:
   * `"I completed calibration independently."`
   * `"I did not view another judge's labels."`
   * `"I did not see model identity, ranking, score, strategy, or control status."`
   * `"I did not use an LLM to generate relevance labels."`
   * `"I used only the factual evidence provided in the calibration package."`
   * `"I used NA when the provided evidence was insufficient."`

*(Note: In this `W5-CAL-OPS-PREP-01` operational readiness task, all human-execution fields and attestations remain strictly `null`.)*

### E. Post-Submission Calibration Review & Discussion Procedure
Calibration's frozen role is `CALIBRATION_ONLY` (for rubric alignment, anchor interpretation, and boundary discussion); it does not establish an automatic numeric reliability pass/fail gate. After all three judges complete their independent sessions, the following procedure governs post-submission review:

1. **Lock All Three Independent Submissions:** Lock all three completed judge submissions (`J1`, `J2`, `J3`) and their session logs (`submission_sha256`) before any inter-judge communication begins.
2. **Preserve Immutable Raw Calibration Labels:** Archive the pre-discussion calibration submissions as immutable audit records; judges must never retroactively modify their initial independent calibration files.
3. **Compute Descriptive Agreement / Disagreement Evidence Only If Authorized:** Descriptive agreement and disagreement patterns across the 45 calibration items may be summarized only when authorized for calibration review.
4. **Send Calibration Evidence to `W5-CAL-REVIEW`:** Submit the locked calibration evidence, boundary notes, and session logs (including any flagged `external_help_used` or `NA` ambiguity reports) to the formal `W5-CAL-REVIEW` gate.
5. **Gatekeeper Decision (`W5-CAL-REVIEW`):** The ChatGPT methodology gatekeeper reviews the calibration evidence and decides whether:
   * The rubric remains `W5-RUBRIC-V1`
   * Wording clarification or a versioned rubric amendment is required
   * Metadata amendment is required
   * Calibration must be rerun
6. **Hold Primary Annotation Until Gate Closure:** No primary annotation on the 474 primary candidate pool items may start until both `W5-CAL-REVIEW` and `RUBRIC-FREEZE` formally close.
