# W5 Calibration Round 02 — Human Judge Operational Handout (`W5-CAL-R02-HANDOUT-V1`)

- **Round ID**: `W5-CAL-ROUND-02` (`W5-CALIBRATION-V2`)
- **Rubric Reference**: `data/evaluation/reca_w5/annotation/w5_rubric_v1.md` (`W5-RUBRIC-V1`)

---

## 1. Files You Receive

From the project owner, you receive **only your assigned judge package** (`J1`, `J2`, or `J3`):

1. Your assigned calibration file: `w5_calibration_round02_<Jk>_v2.csv` (or `w5_calibration_round02_<Jk>_v2.json`) containing **45 items** across 3 scenarios (`CAL2-HN-01`, `CAL2-DN-01`, `CAL2-HL-01`).
2. Your blank session attestation file: `w5_calibration_round02_<Jk>_attestation_template_v1.json`.
3. The frozen relevance rubric: `w5_rubric_v1.md` (`W5-RUBRIC-V1`).

---

## 2. How to Complete Your Calibration File

1. **Read `w5_rubric_v1.md` (`W5-RUBRIC-V1`) first.** Apply only the relevance criteria defined in `w5_rubric_v1.md`.
2. **Only two columns/fields are editable**:
   - `label`
   - `judge_note`
   Do **not** edit, reorder, delete, or reformat any other column or field (and do not insert spreadsheet formulas starting with `=`).
3. **Allowed `label` values are strictly**:
   - `0`
   - `1`
   - `2`
   - `NA` (exact uppercase `NA`)
   Every one of the **45** items must have a completed `label` (no blank labels, no decimals, no `true`/`false`, no `n/a` or `N/A`).

---

## 3. Mandatory Independence & Evidence Rules

- **Use ONLY the factual evidence inside your supplied package.** Judge each item strictly from the fields provided in your file (`name`, `category`, `address`, `opening_hours`, `osm_factual_tags_json`, `destination`, `declared_interests`).
- **Do NOT search Google, Google Maps, TripAdvisor, blogs, or any external web/search source.**
- **Do NOT use ChatGPT, Grok, Gemini, Claude, Copilot, or any AI/LLM** to suggest, draft, or decide any `label` or `judge_note`.
- **Do NOT ask another judge** for advice or interpretation on any item before all three submissions are locked.
- **Do NOT show another judge your labels** or inspect another judge's file.
- **Do NOT post or share examples, label counts, distributions, or summaries** in any chat, issue, pull request, or shared channel before the project owner confirms all three submissions are locked.
- **Submit your completed calibration file and completed attestation privately** (1-to-1) to the project owner only.

---

## 4. Completing Your Session Attestation

After finishing all 45 items, open your blank attestation JSON file (`w5_calibration_round02_<Jk>_attestation_template_v1.json`) and replace each `null` boolean field truthfully with `true` or `false` (and set `completed_at_utc` to the UTC ISO-8601 timestamp when you finished), then send both files privately to the project owner.
