# W5 Calibration Round 01 Submission Receipt & Protocol Invalidation Report V1

**Title:** W5 Calibration Round 01 Submission Receipt & Protocol Invalidation Report V1<br>
**Receipt Version:** `W5-CAL-SUBMISSION-RECEIPT-V1`<br>
**Manifest Version:** `W5-CAL-RAW-MANIFEST-V1`<br>
**Incident Artifact:** `W5-CAL-INTEGRITY-INCIDENT-V1` (`w5_calibration_round_01_integrity_incident_v1.json`)<br>
**Round:** `W5-CAL-ROUND-01`<br>
**Calibration Version:** `W5-CALIBRATION-V1`<br>
**Rubric Version:** `W5-RUBRIC-V1`<br>
**Presentation Version:** `W5-CAL-OPS-V1`<br>
**Date:** `2026-10-14`<br>
**File Integrity Status:** `PASS` (`RAW_SUBMISSIONS_FROZEN`)<br>
**Session / Scientific Integrity Status:** `FAIL` (`FAILED`)<br>
**Round Status:** `INVALIDATED_FOR_PROTOCOL`<br>
**Calibration Qualification:** `INVALIDATED` (`calibration_qualification_eligible: false`, `calibration_review_eligible: false`)<br>
**Methodology Owner & Gatekeeper:** ChatGPT<br>
**Validation & Evidence Agent:** Antigravity<br>

---

## 1. Executive Summary: File Integrity vs. Session Integrity

Three raw calibration CSV submissions (`J1`, `J2`, `J3`; 45 items per file, `135` total raw labels received) were received in `data/evaluation/reca_w5/calibration_submissions/inbox/` and preserved byte-identically in `data/evaluation/reca_w5/calibration_submissions/raw_v1/`.

* **FILE INTEGRITY: `PASS`** — The three received CSV files are authentic received artifacts that pass all structural and schema checks in `scripts/validate_w5_calibration_submission.py`. Their raw bytes and SHA256 hashes are preserved without alteration.
* **SESSION / SCIENTIFIC INTEGRITY: `FAIL`** — Post-submission attestation verification established that labels were determined/generated with AI/LLM assistance and that `J2` and `J3` were exposed to prior judge label summaries before completing their own files.
* **ROUND DECISION: `INVALIDATED_FOR_PROTOCOL`**
  * **Total Raw Labels Received:** `135`
  * **Qualifying Independent Human Judgments:** `0`
  * **Calibration Qualification / Review Eligible:** `NO` (`false`)

Because the frozen protocol (`W5-METH-LOCK-01` / `W5-CAL-OPS-V1`) requires **3 actual human judges**, **no LLM-generated relevance labels**, and **no pre-submission exposure to other judges' labels**, Round 01 (`W5-CAL-ROUND-01`) is invalidated for protocol and **MUST NOT** be used for:
1. Rubric qualification
2. Rubric freeze
3. Human reliability conclusions
4. `HUMAN-GT`
5. Primary annotation decisions
6. Recommender model comparison

---

## 2. Preserved Raw File Evidence (`FILE INTEGRITY: PASS`)

The received CSV submissions are preserved byte-identically as forensic repository evidence and must never be edited, deleted, relabeled, reordered, or regenerated.

| Judge Pseudonym | Frozen Raw File | Inbox Receipt File | Byte Size | Raw SHA256 | Rows | Raw Labels | Notes | Read-Only Context Match | File Validator Status | Qualifying Human Judge |
| :---: | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`J1`** | `raw_v1/J1_w5_calibration_raw_v1.csv` | `inbox/w5_calibration_J1_completed.csv` | `18002` | `7a3b58f20169c98a7b472952e480afb96d34e58613afa0032a58d540062393ba` | `45` | `45` | `45` | `EXACT_MATCH` | `PASS` | `NO` |
| **`J2`** | `raw_v1/J2_w5_calibration_raw_v1.csv` | `inbox/w5_calibration_J2_completed.csv` | `18007` | `b8464c133df5757cd4c1e741a21a5b2392544a175dc2ec32e5d1e6a4d2721707` | `45` | `45` | `45` | `EXACT_MATCH` | `PASS` | `NO` |
| **`J3`** | `raw_v1/J3_w5_calibration_raw_v1.csv` | `inbox/w5_calibration_J3_completed.csv` | `17556` | `b2094cafb458f0ebdea1dd28ec4d5ef723062e449c3b51602edaaee00a86ba3f` | `45` | `45` | `45` | `EXACT_MATCH` | `PASS` | `NO` |

---

## 3. Verified Session & Attestation Facts (`SESSION / SCIENTIFIC INTEGRITY: FAIL`)

Detection stage: `POST_SUBMISSION_PRE_CALIBRATION_REVIEW`

Invalidity reasons:
* `AI_ASSISTED_OR_AI_GENERATED_LABELS`
* `INTER_JUDGE_LABEL_EXPOSURE`

### 3.1 `J1` Attestation Facts
* Completed own 45 labels before `J2`/`J3` submitted: `YES`
* Inspected completed `J2`/`J3` files before own submission: `NO`
* External web/search used: `NO`
* AI/LLM used to determine labels: `YES`
* Pre-submission direct discussion with `J2`/`J3`: `NO`
* After submission, saw summary messages from others: `YES`
* Published some own label summaries before `J2`/`J3` completed: `YES`
* Role assignment: `SELF_SELECTED`
* Qualifying independent human judge: `NO`

### 3.2 `J2` Attestation Facts
* Completed all 45 labels without opening completed `J1`/`J3` files: `YES`
* External web/search used: `NO`
* Labels were AI-generated / decided by an AI assistant: `YES`
* Prior label exposure before judging: `YES` (exposed to `J1` summary containing some specific labels)
* Pre-submission direct discussion with `J1`/`J3`: `NO`
* Role assignment: `SELF_SELECTED`
* Qualifying independent human judge: `NO`

### 3.3 `J3` Attestation Facts
* Completed all 45 labels without opening completed `J1`/`J2` files: `YES`
* External web/search used: `NO`
* Labels were AI-generated / decided by an AI assistant: `YES`
* Prior label exposure before judging: `YES` (exposed to `J1`/`J2` summaries containing some specific labels)
* Pre-submission direct discussion with `J1`/`J2`: `NO`
* Role assignment: `SELF_SELECTED`
* Qualifying independent human judge: `NO`

---

## 4. Non-Qualifying Contaminated Round Diagnostics

### 4.1 Raw Label Counts per File (Forensic Traceability Only)

| File ID | Label `0` | Label `1` | Label `2` | Label `NA` | Total Raw Labels | Non-Blank Notes |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`J1`** | `30` | `7` | `3` | `5` | `45` | `45` |
| **`J2`** | `31` | `7` | `3` | `4` | `45` | `45` |
| **`J3`** | `29` | `9` | `3` | `4` | `45` | `45` |
| **Total Raw Labels** | **`90`** | **`23`** | **`9`** | **`13`** | **`135`** | **`135`** |

### 4.2 Descriptive Diagnostics (`NON_QUALIFYING_CONTAMINATED_ROUND_DIAGNOSTICS`)

The following descriptive counts are retained strictly for forensic traceability of the invalidated Round 01 files:
* **Diagnostic Status:** `NON_QUALIFYING_CONTAMINATED_ROUND_DIAGNOSTICS`
* **Unanimous items across raw files:** `42`
* **Disagreement items across raw files:** `3`
* **Items with any `NA` label:** `5`
* **Numeric adjacent disagreements (`range == 1`):** `2`
* **Numeric severe disagreements (`range == 2`):** `0`
* **Consensus generated:** `NO`
* **Krippendorff's alpha calculated:** `NO` (prohibited on invalidated contaminated round)

These numbers **MUST NOT** be used to infer inter-rater reliability, agreement quality, or rubric quality.

---

## 5. Next Round Policy (`W5-CAL-ROUND-02`)

`W5-CAL-ROUND-02` is required before any calibration review or primary annotation can proceed. Round 02 must enforce:
1. **3 actual human judges** making their own relevance judgments directly from the rubric and frozen item context.
2. **No AI/LLM assistance** for label decisions (`ai_llm_assistance_allowed: false`).
3. **No external search** (`external_search_allowed: false`).
4. **No exposure to another judge's labels or label summaries** before all 3 submissions are locked (`prior_label_exposure_allowed: false`).
5. **Judge roles (`J1`, `J2`, `J3`) assigned BEFORE files are distributed** (`pre_assigned_judge_roles_required: true`).
6. **Fresh calibration package/version preferred** because `W5-CALIBRATION-V1` item labels were exposed during Round 01.

*(Round 02 is not created in this task.)*

---

## 6. Scientific Boundary Statements

* **Qualifying Independent Human Judgments:** `0`
* **Calibration Review Eligible:** `NO` (`false`)
* **Primary Annotation Started:** `NO` (`false`)
* **Rubric Changed:** `NO` (`false`)
* **`HUMAN-GT` Created:** `NO` (`false`)
* **Recommender Evaluation Performed:** `NO` (`false`)
* **Scientific Winner:** `UNKNOWN`
* **R8B Status:** `CLOSED_BY_CONTINGENCY` (`METHOD_RETAINED`)
* **Duplicate Policy Status:** `CLOSED_NO_PRIMARY_EVAL_IMPACT`
