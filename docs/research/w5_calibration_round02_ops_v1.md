# W5 Human Calibration Round 02 Operations & Protocol V1

**Title:** W5 Human Calibration Round 02 Operations & Protocol V1<br>
**Document Version:** `W5-CAL-R02-OPS-DOC-V1`<br>
**Round ID:** `W5-CAL-ROUND-02`<br>
**Calibration Version:** `W5-CALIBRATION-V2`<br>
**Rubric Version:** `W5-RUBRIC-V1`<br>
**Presentation Version:** `W5-CAL-R02-OPS-V1`<br>
**Base Deterministic Seed:** `20261014`<br>
**Track:** `CALIBRATION_ONLY` (`excluded_from_final_metrics: true`)<br>
**Current Status:** `PREPARED_NOT_STARTED` (`0` human labels collected; `HUMAN-GT: false`)<br>
**Role Assignment Execution Status:** `NOT_STARTED` (`actual_human_roles_assigned: false`, `packages_distributed: false`)<br>
**Methodology Owner & Gatekeeper:** ChatGPT<br>
**Implementation & Evidence Agent:** Antigravity<br>

---

## 1. Why Round 02 Exists & Forensic Status of Round 01

* **Round 01 (`W5-CAL-ROUND-01`) Status:** `INVALIDATED_FOR_PROTOCOL` (`FORENSIC_NON_QUALIFYING_EVIDENCE_ONLY`).
* **Reason for Invalidation:** Post-submission session attestation audit established two protocol violations in Round 01:
  1. `AI_ASSISTED_OR_AI_GENERATED_LABELS` (labels were determined/generated with AI/LLM assistance rather than independent human judgment).
  2. `INTER_JUDGE_LABEL_EXPOSURE` (earlier judge label summaries were published before later judges finished, `J2` and `J3` were exposed to prior judge label summaries before completing their own files, and judge roles were self-selected).
* **Forensic Boundary:** The Round 01 raw CSV submissions (`data/evaluation/reca_w5/calibration_submissions/raw_v1/`) and incident record (`w5_calibration_round_01_integrity_incident_v1.json`) remain permanently frozen as forensic evidence only (`qualifying_independent_human_judgments = 0`).
* **Fresh Package Requirement:** Because `W5-CALIBRATION-V1` item labels and context were exposed during Round 01, a completely fresh calibration item universe (`W5-CALIBRATION-V2`) is required before collecting actual human calibration judgments.

---

## 2. Locked Round 02 Scenarios & Fresh Item Universe

Round 02 (`W5-CALIBRATION-V2`) comprises **3 fresh scenarios** (`15` items per scenario, `45` total items) covering all **7 canonical REC-A interest dimensions**:

| Scenario ID | Destination (`destination_slug`) | Declared Interests | Items | `I0` (Represented) | `I1` (Zero-Vector) | `SUFFICIENT_FACTUAL_CONTEXT` | `LIMITED_FACTUAL_CONTEXT` | `INSUFFICIENT_FACTUAL_CONTEXT` |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`CAL2-HN-01`** | `ha-noi` | `culture_history`, `nature_outdoor`, `nightlife_entertainment` | `15` | `10` | `5` | `13` | `2` | `0` |
| **`CAL2-DN-01`** | `da-nang` | `food_cuisine`, `beach_island` | `15` | `10` | `5` | `12` | `3` | `0` |
| **`CAL2-HL-01`** | `ha-long` | `coffee_culture`, `shopping_local` | `15` | `10` | `5` | `8` | `6` | `1` |
| **Total** | **3 Destinations** | **All 7 Canonical Interests Covered** | **`45`** | **`30`** | **`15`** | **`33`** | **`11`** | **`1`** |

### Mandatory Disjointness & Exclusion Guarantees
* **Source Universe:** `REC-A-CORE-V2` only (`is_rec_a_core_v2 == true` in `gomate_places_freeze_v2.json`; `0` secondary/non-core POI leakage).
* **Round 01 Overlap:** `0 / 45` (`0` overlap with `w5_calibration_v1.json`).
* **Primary Candidate Pool Overlap:** `0 / 255` unique primary pool places (`0 / 474` candidate records in `w5_candidate_pool_blinded_v1.json` and `w5_candidate_pool_internal_v1.json`).
* **Within-Round Uniqueness:** All `45` Round 02 `place_id`s are unique across `CAL2-HN-01`, `CAL2-DN-01`, and `CAL2-HL-01`.
* **No Expected Relevance Labels:** Selection uses deterministic stratified sampling (`seed = 20261014`) over objective structural attributes (`I0`/`I1`, `metadata_sufficiency`, and category round-robin). Zero expected or synthetic relevance labels exist anywhere.

---

## 3. Pre-Distribution Judge Role Assignment: Normative Requirement vs. Current Execution State

Contract artifact: `data/evaluation/reca_w5/calibration_round02_ops/w5_calibration_round02_role_assignment_contract_v1.json`

> [!IMPORTANT]
> **`REQUIREMENT != EXECUTED FACT`**<br>
> At `W5-CAL-R02-PREP-01` completion time, Round 02 is **prepared**, not executed:
> * The three judge roles (`J1`, `J2`, `J3`) are defined (`PRE_DISTRIBUTION_TEMPLATE`).
> * The blinded judge package files exist in `calibration_round02_ops/judge_packages/`.
> * **Actual humans are NOT yet assigned** (`assignment_execution_status = "NOT_STARTED"`, `actual_human_roles_assigned = false`, `distinct_actual_humans_confirmed = false`).
> * **No files have been distributed** (`packages_distributed = false`).
> * **Human label collection has NOT started** (`actual_human_judgments_collected = 0`).

### Required Procedure Before Any Package Is Distributed
Before distributing any file, the project owner must:
1. **Choose 3 distinct actual human judges** and verify they understand the no-AI, no-external-search, and no-sharing rules.
2. **Map them privately to `J1`, `J2`, and `J3` BEFORE package distribution** (`must_be_assigned_before_package_distribution = true`; self-selection of roles is strictly prohibited).
3. **Give each person ONLY their own assigned package** (`other_judge_packages_must_be_withheld = true`):
   * Human assigned to **`J1`** receives **only** `w5_calibration_round02_J1_v2.csv` (or `.json`) + `w5_rubric_v1.md`.
   * Human assigned to **`J2`** receives **only** `w5_calibration_round02_J2_v2.csv` (or `.json`) + `w5_rubric_v1.md`.
   * Human assigned to **`J3`** receives **only** `w5_calibration_round02_J3_v2.csv` (or `.json`) + `w5_rubric_v1.md`.
4. **Preserve Pseudonymity:** Repository artifacts store only pseudonyms `J1`, `J2`, and `J3`. Personal names or contact details are never committed to the repository.

---

## 4. Strict Human Judging Rules (No AI, No Search, Full Bidirectional Independence)

Each of the 3 human judges (`J1`, `J2`, `J3`) must adhere strictly to the following protocol:

1. **Actual Human Judgment Only (`No-AI Rule`):**
   * Every relevance label (`0`, `1`, `2`, `NA`) and `judge_note` must be decided and written by the human judge personally (`actual_human_judge = true`).
   * Using ChatGPT, Grok, Claude, Gemini, Antigravity, Copilot, or any LLM/AI assistant to suggest, draft, or decide labels or notes is **strictly prohibited** (`ai_llm_used_for_label_decisions = false`).
2. **Provided Factual Context Only (`No-External-Search Rule`):**
   * Judges must rely solely on the factual fields presented in their assigned package (`destination`, `declared_interests`, `name`, `category`, `address`, `latitude`, `longitude`, `opening_hours`, `osm_source`, `osm_factual_tags`) and `w5_rubric_v1.md`.
   * Using Google Search, Google Maps, TripAdvisor, Facebook, or external websites is **strictly prohibited** (`external_search_used = false`).
   * When the provided factual evidence is insufficient to make a responsible relevance judgment, the judge must assign `NA` (`INSUFFICIENT_EVIDENCE`; `NA != 0`).
3. **Bidirectional Inter-Judge Independence (`No-Receiving AND No-Publishing Rule`):**
   * Judges must not inspect another judge's package or completed file (`inspected_other_judge_labels_before_submission = false`).
   * Judges must not be exposed to another judge's label summary before submission (`exposed_to_other_judge_label_summary_before_submission = false`).
   * Judges must not discuss items, labels, or rubric interpretations with other judges before all 3 submissions are locked (`direct_label_discussion_before_all_submissions_locked = false`).
   * **Prohibition on Publishing/Sharing Own Labels:** Before all 3 submissions are received and locked, a judge must **NEVER** publish or share (`published_or_shared_own_labels_or_summary_before_all_submissions_locked = false`):
     * individual item labels
     * screenshots containing labels or notes
     * label counts or distributions (e.g., counts of `0`/`1`/`2`/`NA`)
     * example ratings or rationales
     * summaries of their judgments in any group chat, forum, or channel

---

## 5. Private Submission & Mandatory Session Attestation Gate

Contract artifact: `data/evaluation/reca_w5/calibration_round02_ops/w5_calibration_round02_session_attestation_template_v1.json`

1. **Private Return:** Each judge must return their completed file and completed session attestation **privately** to the project owner (`submitted_privately_to_project_owner = true`). Labels remain strictly private until all 3 submissions are received and locked.
2. **Mandatory Attestation Fields (All 10 Qualification-Critical Booleans):** For a judge's submission to be `QUALIFYING`, their machine-readable attestation must record these exact boolean values:
   * `actual_human_judge: true`
   * `ai_llm_used_for_label_decisions: false`
   * `external_search_used: false`
   * `inspected_other_judge_labels_before_submission: false`
   * `exposed_to_other_judge_label_summary_before_submission: false`
   * `direct_label_discussion_before_all_submissions_locked: false`
   * `assigned_role_before_distribution: true`
   * `completed_all_required_items: true`
   * `submitted_privately_to_project_owner: true`
   * `published_or_shared_own_labels_or_summary_before_all_submissions_locked: false`
3. **Automatic Disqualification (`NON_QUALIFYING`):** Any submission with a missing attestation, null/non-boolean field, or any boolean violating the 10 required values above is automatically marked `NON_QUALIFYING` by `validate_round02_session_attestation()`.

---

## 6. Post-Submission Gate & Scientific Firewall

After all 3 human submissions and their 3 session attestations arrive:
1. **Submission Freeze & Validation Task:** Raw Round 02 files and attestations are validated and frozen byte-identically without editing any label or note.
2. **Gatekeeper Audit (`ChatGPT`):** ChatGPT audits both file integrity and session attestation integrity before any calibration agreement analysis (`W5-CAL-REVIEW`) is authorized.
3. **No Automatic Progression:**
   * Primary pool annotation (`474` candidate records across 30 primary scenarios) does **NOT** start automatically.
   * `HUMAN-GT` remains `false`.
   * Recommender comparison (`REC-A0` / `REC-A1` / `REC-A2`) remains `NOT_PERFORMED` (`scientific_winner = UNKNOWN`).
