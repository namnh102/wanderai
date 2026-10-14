# W5 Human Calibration Submission Receipt V1

**Title:** W5 Human Calibration Submission Receipt V1<br>
**Receipt Version:** `W5-CAL-SUBMISSION-RECEIPT-V1`<br>
**Manifest Version:** `W5-CAL-RAW-MANIFEST-V1`<br>
**Calibration Version:** `W5-CALIBRATION-V1`<br>
**Rubric Version:** `W5-RUBRIC-V1`<br>
**Presentation Version:** `W5-CAL-OPS-V1`<br>
**Date of Receipt:** `2026-10-14`<br>
**Submission State:** `RAW_SUBMISSIONS_FROZEN`<br>
**Target Repository:** `d:\Do_an\wanderai`<br>
**Base Develop Commit:** `c403d33eb704e66a7b0d40d1ee1552cb46a4c287`<br>
**Methodology Owner & Gatekeeper:** ChatGPT<br>
**Validation & Evidence Agent:** Antigravity<br>

---

## 1. Receipt Summary & Scope

Three independent human calibration submissions (`J1`, `J2`, `J3`) for the `W5-CALIBRATION-V1` package (`CAL-HN-01`, `CAL-DN-01`, `CAL-HL-01`; 15 items per scenario, 45 items per judge, 135 total raw human calibration judgments) were received in `data/evaluation/reca_w5/calibration_submissions/inbox/`, validated against the frozen operational contract (`W5-CAL-OPS-V1`), and frozen byte-identically in `data/evaluation/reca_w5/calibration_submissions/raw_v1/`.

* **Track / Role:** `CALIBRATION_ONLY` (`excluded_from_final_metrics: true`)
* **Judges:** `J1`, `J2`, `J3` (pseudonyms only; zero personal names stored)
* **Items per Judge:** `45`
* **Total Raw Human Calibration Judgments:** `135`
* **Primary Scenario Overlap:** `0/30`
* **Primary Candidate Pool Place Overlap:** `0/255` (`0/474` candidate records)

---

## 2. Submission Validation & Frozen File Hashes

Each received CSV submission was validated using `scripts/validate_w5_calibration_submission.py` against the canonical calibration source (`w5_calibration_v1.json`) and its corresponding deterministic judge presentation package (`w5_calibration_J{1,2,3}_v1.csv`).

| Judge ID | Frozen Raw File | Inbox Receipt File | Byte Size | Raw SHA256 | Rows | Labels | Notes | Read-Only Context Match | Validator Status |
| :---: | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **`J1`** | `raw_v1/J1_w5_calibration_raw_v1.csv` | `inbox/w5_calibration_J1_completed.csv` | `18002` | `7a3b58f20169c98a7b472952e480afb96d34e58613afa0032a58d540062393ba` | `45` | `45` | `45` | `EXACT_MATCH` | `PASS` |
| **`J2`** | `raw_v1/J2_w5_calibration_raw_v1.csv` | `inbox/w5_calibration_J2_completed.csv` | `18007` | `b8464c133df5757cd4c1e741a21a5b2392544a175dc2ec32e5d1e6a4d2721707` | `45` | `45` | `45` | `EXACT_MATCH` | `PASS` |
| **`J3`** | `raw_v1/J3_w5_calibration_raw_v1.csv` | `inbox/w5_calibration_J3_completed.csv` | `17556` | `b2094cafb458f0ebdea1dd28ec4d5ef723062e449c3b51602edaaee00a86ba3f` | `45` | `45` | `45` | `EXACT_MATCH` | `PASS` |

All three submissions satisfied:
* Exact `judge_id`, `calibration_version` (`W5-CALIBRATION-V1`), `rubric_version` (`W5-RUBRIC-V1`), and `presentation_version` (`W5-CAL-OPS-V1`).
* Exact 45-item canonical membership and judge-specific deterministic presentation ordering (zero missing, extra, or duplicate items).
* Exact immutability across all 20 `CSV_READ_ONLY_COLUMNS` (`only label and judge_note modified`).
* Strict label validity (`0`, `1`, `2`, `NA`), zero spreadsheet formulas, and zero forbidden leakage fields.

---

## 3. Raw Label Distributions per Judge

| Judge ID | Label `0` (`NOT_RELEVANT`) | Label `1` (`RELEVANT`) | Label `2` (`HIGHLY_RELEVANT`) | Label `NA` (`INSUFFICIENT_EVIDENCE`) | Total Judgments | Non-Blank Notes |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`J1`** | `30` | `7` | `3` | `5` | `45` | `45` |
| **`J2`** | `31` | `7` | `3` | `4` | `45` | `45` |
| **`J3`** | `29` | `9` | `3` | `4` | `45` | `45` |
| **Total** | **`90`** | **`23`** | **`9`** | **`13`** | **`135`** | **`135`** |

---

## 4. Descriptive Raw Agreement Summary (Pre-Review)

Across the 45 canonical calibration items evaluated independently by `J1`, `J2`, and `J3`:

* **Same Canonical Item Membership Across Judges:** `YES` (`45` items)
* **Exact Unanimous Items (all 3 judges identical in `{0, 1, 2, NA}`):** `42`
* **Disagreement Items (not all 3 judges identical):** `3`
* **Items with Any `NA` Label:** `5`
* **Numeric Adjacent Disagreements (numeric range `== 1`, no `NA`):** `2`
* **Numeric Severe Range-2 Disagreements (numeric range `== 2`):** `0`
* **Consensus or Majority-Vote Labels Generated:** `NO`

*(Per operational protocol, item-level disagreement identities are not exposed to judges in this receipt while raw submissions are being frozen.)*

---

## 5. Session Log & Independence Attestation Status

* **`J1` Session Log / Attestation:** `PENDING`
* **`J2` Session Log / Attestation:** `PENDING`
* **`J3` Session Log / Attestation:** `PENDING`
* **Overall `session_integrity_status`:** `PENDING_ATTESTATION`

No session logs were fabricated. `PENDING_ATTESTATION` does not alter the frozen raw calibration labels, and final `W5-CAL-REVIEW` closure remains gated until judge session attestations are recorded.

---

## 6. Scientific Boundary Statements

* **No disagreement resolution has occurred.**
* **No rubric change has occurred.** (`W5-RUBRIC-V1` remains unchanged.)
* **No HUMAN-GT has been created.** (`HUMAN-GT: NO`)
* **No recommender evaluation has been performed.** (`REC-A0`, `REC-A1`, and `REC-A2` remain untouched; `scientific_winner: UNKNOWN`.)
* **R8B Status:** `CLOSED_BY_CONTINGENCY` (`METHOD_RETAINED`)
* **Duplicate Policy Status:** `CLOSED_NO_PRIMARY_EVAL_IMPACT`
