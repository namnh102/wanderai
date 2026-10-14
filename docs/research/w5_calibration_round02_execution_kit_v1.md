# W5 Calibration Round 02 — Safe Human Collection Execution Kit (`W5-CAL-R02-EXEC-V1`)

- **Execution Kit Version**: `W5-CAL-R02-EXEC-V1`
- **Round ID**: `W5-CAL-ROUND-02`
- **Calibration Version**: `W5-CALIBRATION-V2`
- **Rubric Version**: `W5-RUBRIC-V1` (`data/evaluation/reca_w5/annotation/w5_rubric_v1.md` — authoritative and unmodified)
- **Presentation Version**: `W5-CAL-R02-OPS-V1`
- **Current Official State**: `PREPARED_NOT_STARTED` (`actual_human_judgments_collected = 0`, `qualifying_independent_human_judgments = 0`, `human_gt = false`, `primary_annotation_started = false`, `recommender_evaluation_performed = false`)

---

## 1. Mandatory Operational Sequence

The project owner must follow this strict state transition sequence without skipping or reordering steps:

```text
PREPARED_NOT_STARTED
    ->
ASSIGN 3 DISTINCT ACTUAL HUMANS
    ->
PRIVATE PACKAGE DISTRIBUTION
    ->
INDEPENDENT CALIBRATION
    ->
PRIVATE SUBMISSION
    ->
FILE VALIDATION
    ->
ATTESTATION VALIDATION
    ->
ALL 3 SUBMISSIONS LOCKED
    ->
CAL-REVIEW
```

### Critical Stage Gates

- **`CAL-REVIEW` does NOT start automatically.** Even after all three submissions pass validation and are locked (`READY_TO_LOCK`), `CAL-REVIEW` requires an explicit subsequent task and methodology gate.
- **Primary annotation does NOT start automatically.** No primary evaluation scenario (`30` scenarios / `302` primary candidate records) may be annotated until Round 02 calibration is reviewed and approved by the methodology gatekeeper.
- **`HUMAN-GT` is NOT created during calibration.** Calibration Round 02 (`CAL2-HN-01`, `CAL2-DN-01`, `CAL2-HL-01`; `45` items) is strictly `CALIBRATION_ONLY` (`excluded_from_final_metrics = true`) and never enters final recommender evaluation metrics.
- **No Rubric Modification or Rewriting.** Judges and operators must use `data/evaluation/reca_w5/annotation/w5_rubric_v1.md` (`W5-RUBRIC-V1`) verbatim. This guide intentionally adds no new rubric examples or relevance definitions.

---

## 2. Step-by-Step Project Owner Protocol

### Step 0 — Verify Pre-Collection Readiness

Before assigning any human judges or distributing any files, run:

```bash
python scripts/manage_w5_calibration_round02_execution.py check-readiness
```

Confirm `"overall_status": "PASS"`, `"round_status": "PREPARED_NOT_STARTED"`, and `"actual_human_judgments_collected": 0`.

### Step 1 — Assign 3 Distinct Actual Human Judges (`J1`, `J2`, `J3`)

1. The project owner assigns **three distinct real human individuals** to roles `J1`, `J2`, and `J3` **off-repository** before distributing any files (`data/evaluation/reca_w5/calibration_round02_ops/w5_calibration_round02_role_assignment_contract_v1.json`).
2. Self-selection of `judge_id` is prohibited.
3. Never commit personal names, emails, or contact details to the Git repository; repository artifacts use only pseudonyms `J1`, `J2`, and `J3`.

### Step 2 — Private Package Distribution (Single Package per Judge)

Distribute to each assigned human judge **privately** (1-to-1 channel) **only**:

- **For Judge `J1`**:
  - Package: `data/evaluation/reca_w5/calibration_round02_ops/judge_packages/w5_calibration_round02_J1_v2.csv` (or `.json`)
  - Blank Attestation: `data/evaluation/reca_w5/calibration_round02_ops/execution_templates/w5_calibration_round02_J1_attestation_template_v1.json`
  - Frozen Rubric: `data/evaluation/reca_w5/annotation/w5_rubric_v1.md`
  - Judge Handout: `docs/research/w5_calibration_round02_judge_handout_v1.md`
- **For Judge `J2`**:
  - Package: `data/evaluation/reca_w5/calibration_round02_ops/judge_packages/w5_calibration_round02_J2_v2.csv` (or `.json`)
  - Blank Attestation: `data/evaluation/reca_w5/calibration_round02_ops/execution_templates/w5_calibration_round02_J2_attestation_template_v1.json`
  - Frozen Rubric: `data/evaluation/reca_w5/annotation/w5_rubric_v1.md`
  - Judge Handout: `docs/research/w5_calibration_round02_judge_handout_v1.md`
- **For Judge `J3`**:
  - Package: `data/evaluation/reca_w5/calibration_round02_ops/judge_packages/w5_calibration_round02_J3_v2.csv` (or `.json`)
  - Blank Attestation: `data/evaluation/reca_w5/calibration_round02_ops/execution_templates/w5_calibration_round02_J3_attestation_template_v1.json`
  - Frozen Rubric: `data/evaluation/reca_w5/annotation/w5_rubric_v1.md`
  - Judge Handout: `docs/research/w5_calibration_round02_judge_handout_v1.md`

Never send `J2` or `J3` files to `J1` (or vice versa), and never distribute packages in a shared group folder where judges can view another judge's file.

### Step 3 — Private Intake Storage (Firewall Against Early Exposure)

As each judge privately returns their completed file and attestation to the project owner, store them **only** inside the local git-ignored intake directory:

- `data/evaluation/reca_w5/calibration_round02_ops/private_intake/`

Expected filenames inside `private_intake/` for automated lock-readiness checking:

- `w5_calibration_round02_J1_completed.csv` (or `.json`) and `w5_calibration_round02_J1_attestation.json`
- `w5_calibration_round02_J2_completed.csv` (or `.json`) and `w5_calibration_round02_J2_attestation.json`
- `w5_calibration_round02_J3_completed.csv` (or `.json`) and `w5_calibration_round02_J3_attestation.json`

**DO NOT commit partial submissions (`J1` alone or `J1`+`J2` before `J3` completes) to Git or push them to GitHub.**

### Step 4 — Per-Judge File + Attestation Validation

Validate each received submission and its paired attestation privately using:

```bash
python scripts/manage_w5_calibration_round02_execution.py \
  validate-submission \
  --judge J1 \
  --submission data/evaluation/reca_w5/calibration_round02_ops/private_intake/w5_calibration_round02_J1_completed.csv \
  --attestation data/evaluation/reca_w5/calibration_round02_ops/private_intake/w5_calibration_round02_J1_attestation.json
```

- A submission is `QUALIFYING` **only if both** `file_validation_status == "PASS"` **and** `attestation_validation_status == "PASS"`.
- Validation output intentionally suppresses all label values, label distributions, and item ratings to prevent cross-judge contamination.

### Step 5 — Check Lock Readiness Across All 3 Judges

Once all three judges (`J1`, `J2`, `J3`) have submitted their completed files and attestations into `private_intake/`, run:

```bash
python scripts/manage_w5_calibration_round02_execution.py \
  check-lock-readiness \
  --intake-dir data/evaluation/reca_w5/calibration_round02_ops/private_intake
```

- Returns `"lock_readiness_status": "READY_TO_LOCK"` **only** when three distinct judges (`J1`, `J2`, `J3`) are present and all three have `qualification_status == "QUALIFYING"`.
- Does **not** compute Krippendorff's alpha, aggregate labels, resolve disagreements, create `HUMAN-GT`, commit files, or start `CAL-REVIEW`.
