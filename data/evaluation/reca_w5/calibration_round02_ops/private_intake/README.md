# W5 Calibration Round 02 — Local Private Intake Directory

**THIS DIRECTORY IS LOCAL PRIVATE INTAKE.**

**Partial human submissions MUST NOT be committed to GitHub.**

## Reason

If `J1` labels (or any partial subset of completed calibration files, notes, or summaries) are committed to Git or otherwise exposed before `J2` and `J3` complete their independent calibration sessions, Round 02 inter-judge independence can be contaminated (repeating the `INTER_JUDGE_LABEL_EXPOSURE` failure mode documented in `W5-CAL-INCIDENT-01`).

## Operational Firewall Rules

1. `.gitignore` in this directory ignores all files (`*`) except `.gitignore` and `README.md`.
2. When human judges privately submit their completed Round 02 calibration files and session attestations to the project owner, place them here locally:
   - `w5_calibration_round02_J1_completed.csv` (or `.json`) + `w5_calibration_round02_J1_attestation.json`
   - `w5_calibration_round02_J2_completed.csv` (or `.json`) + `w5_calibration_round02_J2_attestation.json`
   - `w5_calibration_round02_J3_completed.csv` (or `.json`) + `w5_calibration_round02_J3_attestation.json`
3. Use `python scripts/manage_w5_calibration_round02_execution.py validate-submission` and `check-lock-readiness --intake-dir data/evaluation/reca_w5/calibration_round02_ops/private_intake` locally to verify `READY_TO_LOCK` status without exposing any label values or distributions.
4. No real human submission file is created or committed during `W5-CAL-R02-EXEC-PREP-01`.
