# Historical W5 Hash & EOL Reproducibility Audit V1 (`W5-HASH-AUDIT-01`)

* **Audit ID:** `W5-HASH-AUDIT-01`
* **Base `develop` Commit SHA:** `1c7e43b39f4009e9620181d0c0c5a8151788abb7`
* **Audit Branch:** `audit/w5-hash-eol-01`
* **Machine-Readable Audit Artifact:** `data/evaluation/reca_w5/audits/w5_hash_eol_audit_v1.json`
* **Audit Tooling:** `scripts/audit_w5_hash_eol.py`
* **Overall Scientific Impact Classification:** `HISTORICAL_MANIFEST_INCONSISTENCY`
* **Content Difference Found:** `NO` (`false`)
* **Representation-Only Difference Found:** `YES` (`true`)
* **Formal Amendment Recommended:** `YES` (`true`)
* **Historical Artifacts Modified:** `NO` (`false`)
* **Scientific Data Modified:** `NO` (`false`)

---

## 1. Executive Summary

This read-only forensic audit (`W5-HASH-AUDIT-01`) investigates all SHA256 hashes stored, referenced, or asserted across the W5 evaluation pipeline (`W5-PREP-01`, `W5-PREP-02`, `W5-METH-LOCK-01`, `W5-GATE-DUP-01`, `R8B-CONTINGENCY-01`, `W5-CAL-OPS-PREP-01`, `W5-CAL-INCIDENT-01`, and `W5-CAL-R02-PREP-01`) at `develop` commit `1c7e43b39f4009e9620181d0c0c5a8151788abb7`.

### Key Findings
1. **Zero Content Differences (`CONTENT_DIFFERENCE = false`):** Every single historical W5 artifact has 100% intact semantic and textual content. No historical artifact has suffered data corruption, unauthorized editing, or unrecorded content drift.
2. **Exact Root Cause of Historical Manifest Discrepancies (`REPRESENTATION_ONLY_DIFFERENCE = true`):**
   * Two early pre-preregistration builder manifests—`data/evaluation/reca_w5/w5_reproducibility_manifest_v1.json` (5 hashes) and `data/evaluation/reca_w5/annotation/w5_annotation_manifest_v1.json` (10 unique artifact hashes across 14 fields)—recorded SHA256 digests computed over **pre-commit Windows `CRLF` working-tree bytes** (`open(..., "w", encoding="utf-8")` without `newline="\n"`), whereas root `.gitattributes` (`* text=auto eol=lf`) normalized those files to **`LF`** when committed to the Git object database.
   * Applying a pure `LF -> CRLF` newline transformation (`CRLF_NORMALIZED_UTF8_SHA256`) to the committed Git blobs reproduces **100% (19/19)** of the stored hash entries in `w5_reproducibility_manifest_v1.json` and `w5_annotation_manifest_v1.json`.
3. **Authoritative Preregistration Manifest Is 100% Reproducible on Committed Git Blobs (`MATCH_MULTIPLE_EQUIVALENT_BASES`):**
   * `data/evaluation/reca_w5/rec_eval_01_prereg_manifest_v1.json` (and Section 25 of `docs/research/rec_eval_01_prereg_v1.md`) explicitly declares `"artifact_hash_basis": "sha256_git_committed_blob_content"` at `source_commit_sha = 35f82b30aa474d33036df656d70528dc20328d39`.
   * All **14/14** stored hashes in `rec_eval_01_prereg_manifest_v1.json` match `GIT_BLOB_BYTES_SHA256`, `WORKING_TREE_BYTES_SHA256`, and `LF_NORMALIZED_UTF8_SHA256` simultaneously.
4. **Round 01 Raw Forensic CSV Submissions Are Byte-Identical Across All Platforms (`MATCH_MULTIPLE_EQUIVALENT_BASES`):**
   * `data/evaluation/reca_w5/calibration_submissions/.gitattributes` specifies `*.csv -text whitespace=cr-at-eol`, preventing Git from normalizing line endings on the received forensic CSV files.
   * For `J1`, `J2`, and `J3` (both `raw_v1/` and `inbox/`), the frozen hashes (`7a3b58f2...`, `b8464c13...`, `b2094caf...`) match `GIT_BLOB_BYTES_SHA256`, `WORKING_TREE_BYTES_SHA256`, and `CRLF_NORMALIZED_UTF8_SHA256` simultaneously.
5. **Round 02 Positive Control Reproduces 100% Under Declared Policy (`PASS`):**
   * `data/evaluation/reca_w5/calibration_round02_ops/w5_calibration_round02_manifest_v1.json` explicitly enforces `LF_ONLY_FOR_ALL_NEW_ROUND02_ARTIFACTS` and records both `COMMITTED_GIT_BLOB_UTF8_LF_NORMALIZED_SHA256` and `CANONICAL_SORTED_COMPACT_JSON_UTF8_SHA256`. All 7 control artifacts and 3 operational contracts match `GIT_BLOB_BYTES_SHA256`, `WORKING_TREE_BYTES_SHA256`, and `LF_NORMALIZED_UTF8_SHA256` (plus `CANONICAL_JSON_SHA256` for all JSON artifacts).

---

## 2. Repository EOL Configuration & Scope Inventory

### 2.1 `.gitattributes` Rules
| File Path | Rule | Operational Effect |
| :--- | :--- | :--- |
| `.gitattributes` | `* text=auto eol=lf` | All standard text files (`.json`, `.md`, `.py`, `.csv` outside `calibration_submissions/`) are stored as `LF` blobs in Git and checked out as `LF` in the working tree on all platforms. |
| `data/evaluation/reca_w5/calibration_submissions/.gitattributes` | `*.csv -text whitespace=cr-at-eol` | Treats received calibration submission CSVs as binary (`-text`) so Git preserves exact received `CRLF` byte streams in both the Git blob and working tree. |

### 2.2 Inspected Hash-Bearing Artifacts, Scripts, Documentation, and Tests
* **Manifests & Incident Contracts (7):**
  1. `data/evaluation/reca_w5/rec_eval_01_prereg_manifest_v1.json` (14 artifact hashes)
  2. `data/evaluation/reca_w5/w5_reproducibility_manifest_v1.json` (5 artifact hashes)
  3. `data/evaluation/reca_w5/annotation/w5_annotation_manifest_v1.json` (10 unique artifact hashes across 14 fields)
  4. `data/evaluation/reca_w5/w5_duplicate_equivalence_evidence_v1.json` (2 canonical artifact hashes)
  5. `data/evaluation/reca_w5/calibration_submissions/w5_calibration_raw_manifest_v1.json` (3 raw CSV hashes across 6 `raw_v1`/`inbox` paths)
  6. `data/evaluation/reca_w5/calibration_submissions/w5_calibration_round_01_integrity_incident_v1.json` (3 forensic preservation hashes)
  7. `data/evaluation/reca_w5/calibration_round02_ops/w5_calibration_round02_manifest_v1.json` (10 LF file hashes + 7 canonical JSON hashes + 6 non-file seed/order hashes)
* **Research Documentation (3):**
  1. `docs/research/rec_eval_01_prereg_v1.md` (Section 25 table of 14 preregistered SHA256 hashes)
  2. `docs/research/w5_calibration_submission_receipt_v1.md` (Section 2 table of 3 Round 01 raw CSV SHA256 hashes)
  3. `docs/data/dataset-freeze-v1-eol-erratum.md` (Legacy Freeze V1/V2 CRLF-vs-LF compatibility policy reference)
* **Scripts & Test Suites (16):**
  * `scripts/build_w5_eval_pool.py`, `scripts/build_w5_annotation_package.py`, `scripts/evaluate_w5_recommenders.py`, `scripts/analyze_w5_judgments.py`, `scripts/validate_w5_calibration_submission.py`, `scripts/prepare_w5_calibration_round02.py`, `scripts/freeze_checksum.py`
  * `tests/test_w5_preregistration.py`, `tests/test_w5_eval_pool.py`, `tests/test_w5_annotation_package.py`, `tests/test_w5_metric_runner.py`, `tests/test_w5_duplicate_gate.py`, `tests/test_r8b_contingency.py`, `tests/test_w5_calibration_ops.py`, `tests/test_w5_calibration_submissions.py`, `tests/test_w5_calibration_round02_prep.py`

---

## 3. Five-Base Hash Matrix for All 35 Hashed W5 Artifacts

For every hashed artifact at `1c7e43b39f4009e9620181d0c0c5a8151788abb7`:
* **Base A (`GIT_BLOB`):** `SHA256(git show <commit>:<path>)`
* **Base B (`WORK_TREE`):** `SHA256(Path(path).read_bytes())`
* **Base C (`LF_NORM`):** `SHA256(bytes.replace(b"\r\n", b"\n"))`
* **Base D (`CRLF_NORM`):** `SHA256(bytes.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))`
* **Base E (`CANON_JSON`):** `SHA256(json.dumps(json.loads(bytes), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))`

| # | Artifact Path | Blob EOL | Trailing NL | `GIT_BLOB` / `WORK_TREE` (`A == B`) | `LF_NORM` (`C`) | `CRLF_NORM` (`D`) | `CANON_JSON` (`E`) |
| :---: | :--- | :---: | :---: | :--- | :--- | :--- | :--- |
| 1 | `data/curated/gomate_places_freeze_v2.json` | `LF` | `YES` | `f7517938598e...` | `f7517938598e...` | `93681135d94b...` | `fa3f46ce8862...` |
| 2 | `data/evaluation/reca_w5/w5_primary_scenarios_v1.json` | `LF` | `YES` | `4f0c77dccc2c...` | `4f0c77dccc2c...` | `98a86723e7a2...` | `66a8813f28a3...` |
| 3 | `data/evaluation/reca_w5/w5_thin_diagnostic_scenarios_v1.json` | `LF` | `YES` | `538233a937ac...` | `538233a937ac...` | `c90773202aab...` | `7b70b0f1b61d...` |
| 4 | `data/evaluation/reca_w5/w5_candidate_pool_internal_v1.json` | `LF` | `YES` | `32b25ef8ffc1...` | `32b25ef8ffc1...` | `29c3c8192f8d...` | `92cd87ab024d...` |
| 5 | `data/evaluation/reca_w5/w5_candidate_pool_blinded_v1.json` | `LF` | `YES` | `8f178e06b1b9...` | `8f178e06b1b9...` | `8a4dce96ea15...` | `7c1c13df5df4...` |
| 6 | `data/evaluation/reca_w5/w5_reproducibility_manifest_v1.json` | `LF` | `YES` | `ae2cbb976891...` | `ae2cbb976891...` | `4755ce7d1f18...` | `1c6bf4be7ab9...` |
| 7 | `data/evaluation/reca_w5/annotation/w5_rubric_v1.md` | `LF` | `YES` | `98601330b366...` | `98601330b366...` | `b1c799247ce3...` | `N/A` |
| 8 | `data/evaluation/reca_w5/annotation/w5_judge_instructions_v1.md` | `LF` | `YES` | `5d579d4c0b76...` | `5d579d4c0b76...` | `70d802364c80...` | `N/A` |
| 9 | `data/evaluation/reca_w5/annotation/w5_judge_J1_v1.json` | `LF` | `NO` | `11a28f8f026e...` | `11a28f8f026e...` | `96ee07983640...` | `6f53a4e15ee5...` |
| 10 | `data/evaluation/reca_w5/annotation/w5_judge_J2_v1.json` | `LF` | `NO` | `63dafdf77e50...` | `63dafdf77e50...` | `2e0a256a37b0...` | `07e8c98081e4...` |
| 11 | `data/evaluation/reca_w5/annotation/w5_judge_J3_v1.json` | `LF` | `NO` | `9959326d1e30...` | `9959326d1e30...` | `827e32b7e8cf...` | `977b6f4cd6b5...` |
| 12 | `data/evaluation/reca_w5/annotation/w5_calibration_v1.json` | `LF` | `NO` | `598bde75d464...` | `598bde75d464...` | `740d81e3c3a6...` | `24c283978a6a...` |
| 13 | `data/evaluation/reca_w5/annotation/w5_annotation_template_v1.json` | `LF` | `NO` | `9badb4f3c41c...` | `9badb4f3c41c...` | `bdc92d7885d7...` | `62a9cf21e2b8...` |
| 14 | `data/evaluation/reca_w5/annotation/w5_merged_ground_truth_template_v1.json` | `LF` | `NO` | `3f33c6f866de...` | `3f33c6f866de...` | `624ab8203809...` | `e2e57cd04073...` |
| 15 | `data/evaluation/reca_w5/annotation/w5_adjudication_template_v1.json` | `LF` | `NO` | `9d811ef8f9c1...` | `9d811ef8f9c1...` | `f092b918a339...` | `09ec7272e313...` |
| 16 | `data/evaluation/reca_w5/annotation/w5_metadata_sufficiency_v1.json` | `LF` | `NO` | `c58f9a709cb3...` | `c58f9a709cb3...` | `302a47f2c774...` | `f9918b35cc93...` |
| 17 | `data/evaluation/reca_w5/annotation/w5_annotation_manifest_v1.json` | `LF` | `NO` | `9fa7e9e66f33...` | `9fa7e9e66f33...` | `075d4b456800...` | `7062d2638764...` |
| 18 | `scripts/evaluate_w5_recommenders.py` | `LF` | `YES` | `ec494c7b8f2c...` | `ec494c7b8f2c...` | `32248a8e79f3...` | `N/A` |
| 19 | `scripts/analyze_w5_judgments.py` | `LF` | `YES` | `f2f748c8ae6e...` | `f2f748c8ae6e...` | `938c149efaa6...` | `N/A` |
| 20 | `data/evaluation/reca_w5/calibration_submissions/raw_v1/J1_w5_calibration_raw_v1.csv` | `CRLF` | `YES` | `7a3b58f20169...` | `4c99262bf1a5...` | `7a3b58f20169...` | `N/A` |
| 21 | `data/evaluation/reca_w5/calibration_submissions/raw_v1/J2_w5_calibration_raw_v1.csv` | `CRLF` | `YES` | `b8464c133df5...` | `0315a560f0bf...` | `b8464c133df5...` | `N/A` |
| 22 | `data/evaluation/reca_w5/calibration_submissions/raw_v1/J3_w5_calibration_raw_v1.csv` | `CRLF` | `YES` | `b2094cafb458...` | `428bd2b741bc...` | `b2094cafb458...` | `N/A` |
| 23 | `data/evaluation/reca_w5/calibration_submissions/inbox/w5_calibration_J1_completed.csv` | `CRLF` | `YES` | `7a3b58f20169...` | `4c99262bf1a5...` | `7a3b58f20169...` | `N/A` |
| 24 | `data/evaluation/reca_w5/calibration_submissions/inbox/w5_calibration_J2_completed.csv` | `CRLF` | `YES` | `b8464c133df5...` | `0315a560f0bf...` | `b8464c133df5...` | `N/A` |
| 25 | `data/evaluation/reca_w5/calibration_submissions/inbox/w5_calibration_J3_completed.csv` | `CRLF` | `YES` | `b2094cafb458...` | `428bd2b741bc...` | `b2094cafb458...` | `N/A` |
| 26 | `data/evaluation/reca_w5/annotation/w5_calibration_v2.json` | `LF` | `YES` | `8be5eb82004e...` | `8be5eb82004e...` | `e4083e2b6fa8...` | `abaa039c910c...` |
| 27 | `data/evaluation/reca_w5/calibration_round02_ops/w5_calibration_round02_role_assignment_contract_v1.json` | `LF` | `YES` | `3ede436168d0...` | `3ede436168d0...` | `6f41e87451b1...` | `a6766d71b72b...` |
| 28 | `data/evaluation/reca_w5/calibration_round02_ops/w5_calibration_round02_session_attestation_template_v1.json` | `LF` | `YES` | `7894325132c4...` | `7894325132c4...` | `b53f8a48cb60...` | `24b4a692ce4e...` |
| 29 | `data/evaluation/reca_w5/calibration_round02_ops/w5_calibration_round02_submission_contract_v1.json` | `LF` | `YES` | `90c38df02aab...` | `90c38df02aab...` | `318f8786e100...` | `36716fb40f2a...` |
| 30 | `data/evaluation/reca_w5/calibration_round02_ops/judge_packages/w5_calibration_round02_J1_v2.json` | `LF` | `YES` | `de3435fabb5e...` | `de3435fabb5e...` | `8d0501f74c60...` | `f10c7ea2fa86...` |
| 31 | `data/evaluation/reca_w5/calibration_round02_ops/judge_packages/w5_calibration_round02_J1_v2.csv` | `LF` | `YES` | `052f8e0a166a...` | `052f8e0a166a...` | `c85219d20389...` | `N/A` |
| 32 | `data/evaluation/reca_w5/calibration_round02_ops/judge_packages/w5_calibration_round02_J2_v2.json` | `LF` | `YES` | `30f7766dc3f9...` | `30f7766dc3f9...` | `519462f18a91...` | `4c5006f513a4...` |
| 33 | `data/evaluation/reca_w5/calibration_round02_ops/judge_packages/w5_calibration_round02_J2_v2.csv` | `LF` | `YES` | `7483e0db085d...` | `7483e0db085d...` | `e38bf3ab1594...` | `N/A` |
| 34 | `data/evaluation/reca_w5/calibration_round02_ops/judge_packages/w5_calibration_round02_J3_v2.json` | `LF` | `YES` | `8a4f24135489...` | `8a4f24135489...` | `0a4052b0290d...` | `b1dd5934a657...` |
| 35 | `data/evaluation/reca_w5/calibration_round02_ops/judge_packages/w5_calibration_round02_J3_v2.csv` | `LF` | `YES` | `08599d1b1c3b...` | `08599d1b1c3b...` | `3f89c3b6ef7f...` | `N/A` |

*(Full 64-character hex digests for all 5 bases of all 35 artifacts are recorded in `data/evaluation/reca_w5/audits/w5_hash_eol_audit_v1.json`.)*

---

## 4. Classification of Stored Historical Hashes & Root Cause Analysis

### 4.1 `w5_reproducibility_manifest_v1.json` (5 Hashes — `MATCH_CRLF_NORMALIZED_BYTES`)
| Manifest Key | Target Artifact | Stored SHA256 | Classification | Difference Type | Root Cause |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `freeze_checksum` | `data/curated/gomate_places_freeze_v2.json` | `93681135d94b379f28802aa75204a0a4c7bec4039f85d28e76ae6737e792e245` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `primary_scenario_manifest_sha256` | `data/evaluation/reca_w5/w5_primary_scenarios_v1.json` | `98a86723e7a2d16fbb2acebe1a39379f525a973cc0d854191318931484e9d553` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `thin_diagnostic_manifest_sha256` | `data/evaluation/reca_w5/w5_thin_diagnostic_scenarios_v1.json` | `c90773202aab20e6e30fd8c9cd37157c6d1a4fcb6bf7b718d023c32a6fc50f69` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `internal_pool_sha256` | `data/evaluation/reca_w5/w5_candidate_pool_internal_v1.json` | `29c3c8192f8d39e733b6753d3c4ccdd19025324b673ce7b8601a0ca15843bd24` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `blinded_pool_sha256` | `data/evaluation/reca_w5/w5_candidate_pool_blinded_v1.json` | `8a4dce96ea156ae6ef3d79a31863d441a3d77df914f3b500f872475102d965be` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |

### 4.2 `annotation/w5_annotation_manifest_v1.json` (10 Unique Hashes across 14 Fields — `MATCH_CRLF_NORMALIZED_BYTES`)
| Manifest Key(s) | Target Artifact | Stored SHA256 | Classification | Difference Type | Root Cause |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `artifact_hashes.w5_rubric_v1.md` | `.../annotation/w5_rubric_v1.md` | `b1c799247ce39763a941fafdc929780c32007e88a5fdc4bf62c41ee34a7b510e` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `artifact_hashes.w5_judge_instructions_v1.md` | `.../annotation/w5_judge_instructions_v1.md` | `70d802364c80197993f7ca8e08b6385a7cd72f5eaa5d915a1dfa61c2e7e49dde` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `artifact_hashes.w5_judge_J1_v1.json` / `judge_packages.J1.sha256` | `.../annotation/w5_judge_J1_v1.json` | `96ee079836407c423a7b2cfb3559f11ead970d92c24f5d6c839796a372faa687` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `artifact_hashes.w5_judge_J2_v1.json` / `judge_packages.J2.sha256` | `.../annotation/w5_judge_J2_v1.json` | `2e0a256a37b0634a4641495da36e234df790444de5b3821035c3f3261ab7f703` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `artifact_hashes.w5_judge_J3_v1.json` / `judge_packages.J3.sha256` | `.../annotation/w5_judge_J3_v1.json` | `827e32b7e8cf4572a455a117236cafb57de1c1b5cac1c6e96902725f8e722c7f` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `artifact_hashes.w5_calibration_v1.json` / `calibration_package.sha256` | `.../annotation/w5_calibration_v1.json` | `740d81e3c3a613575a687af9291102d27e9dd8c61f1fc8f40e913c4c2ccfbc60` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `artifact_hashes.w5_annotation_template_v1.json` | `.../annotation/w5_annotation_template_v1.json` | `bdc92d7885d7043311303d7bbd8a168e088c8c3a5cc361b7983154daa4e390fd` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `artifact_hashes.w5_merged_ground_truth_template_v1.json` | `.../annotation/w5_merged_ground_truth_template_v1.json` | `624ab82038099b33d775610001bb99b8b5f6321a10381f068483b12619e5be30` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `artifact_hashes.w5_adjudication_template_v1.json` | `.../annotation/w5_adjudication_template_v1.json` | `f092b918a339151f012d724809c687ccf276ce20cf6b08bde7bcccbe3bb752b2` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |
| `artifact_hashes.w5_metadata_sufficiency_v1.json` | `.../annotation/w5_metadata_sufficiency_v1.json` | `302a47f2c774ccf51302a8a6ae1b991a92c1cd93e5bf19579bae245547f4224b` | `MATCH_CRLF_NORMALIZED_BYTES` | `REPRESENTATION_ONLY_DIFFERENCE` | `LF_VS_CRLF` |

### 4.3 `rec_eval_01_prereg_manifest_v1.json` & `w5_duplicate_equivalence_evidence_v1.json` (`MATCH_MULTIPLE_EQUIVALENT_BASES`)
* All **14** artifact hashes in `rec_eval_01_prereg_manifest_v1.json` (and `docs/research/rec_eval_01_prereg_v1.md`) and both canonical hashes in `w5_duplicate_equivalence_evidence_v1.json` match **`GIT_BLOB_BYTES_SHA256`**, **`WORKING_TREE_BYTES_SHA256`**, and **`LF_NORMALIZED_UTF8_SHA256`** simultaneously (`NO_DIFFERENCE`).

### 4.4 Alternate LF-Regenerated Manifest Allowlist Entries in `tests/test_w5_metric_runner.py`
* `tests/test_w5_metric_runner.py` defines 2-element sets for `w5_reproducibility_manifest_v1.json` (`{ae2cbb97..., d99f3187...}`) and `w5_annotation_manifest_v1.json` (`{9fa7e9e6..., e6f9839c...}`).
* `ae2cbb97...` and `9fa7e9e6...` are the committed `LF` Git blob hashes of those two manifests.
* `d99f3187...` and `e6f9839c...` are proven mathematically by `verify_lf_regenerated_manifest_hashes()` in `scripts/audit_w5_hash_eol.py` to be the exact `LF` SHA256 digests of those two manifests if their inner hashes are replaced with the `LF_NORMALIZED_UTF8_SHA256` digests of their respective target files.

---

## 5. Round 01 Raw File Special Audit (`W5-CAL-ROUND-01`)

Round 01 (`INVALIDATED_FOR_PROTOCOL`, `FORENSIC_NON_QUALIFYING_EVIDENCE_ONLY`) raw CSV files were audited strictly at the byte level without modifying files or reinterpreting labels:

| Judge | Raw File (`raw_v1/`) & Inbox Copy (`inbox/`) | Frozen Historical SHA256 | Matches Git Blob | Matches Working Tree | Matches `LF` Normalized | Matches `CRLF` Normalized | Classification |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **`J1`** | `J1_w5_calibration_raw_v1.csv` / `w5_calibration_J1_completed.csv` | `7a3b58f20169c98a7b472952e480afb96d34e58613afa0032a58d540062393ba` | **`YES`** | **`YES`** | `NO` (`4c99262b...`) | **`YES`** | `MATCH_MULTIPLE_EQUIVALENT_BASES` (`[GIT_BLOB, WORK_TREE, CRLF_NORM]`) |
| **`J2`** | `J2_w5_calibration_raw_v1.csv` / `w5_calibration_J2_completed.csv` | `b8464c133df5757cd4c1e741a21a5b2392544a175dc2ec32e5d1e6a4d2721707` | **`YES`** | **`YES`** | `NO` (`0315a560...`) | **`YES`** | `MATCH_MULTIPLE_EQUIVALENT_BASES` (`[GIT_BLOB, WORK_TREE, CRLF_NORM]`) |
| **`J3`** | `J3_w5_calibration_raw_v1.csv` / `w5_calibration_J3_completed.csv` | `b2094cafb458f0ebdea1dd28ec4d5ef723062e449c3b51602edaaee00a86ba3f` | **`YES`** | **`YES`** | `NO` (`428bd2b7...`) | **`YES`** | `MATCH_MULTIPLE_EQUIVALENT_BASES` (`[GIT_BLOB, WORK_TREE, CRLF_NORM]`) |

Because `data/evaluation/reca_w5/calibration_submissions/.gitattributes` sets `*.csv -text whitespace=cr-at-eol`, the received `CRLF` byte streams are stored verbatim in the Git object store and checked out verbatim on every operating system.

---

## 6. Round 02 Positive Control Analysis (`W5-CAL-ROUND-02`)

All 7 Round 02 control artifacts declared in `data/evaluation/reca_w5/calibration_round02_ops/w5_calibration_round02_manifest_v1.json` were verified against the 5 hash bases:

| Control Artifact | Expected SHA256 | Matches `GIT_BLOB` | Matches `WORK_TREE` | Matches `LF_NORM` | Classification |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `w5_calibration_v2.json` | `8be5eb82004e9ffa67cd5c5ce5676a5ad7c63a4f4df017c355ca42692df39457` | **`YES`** | **`YES`** | **`YES`** | `MATCH_MULTIPLE_EQUIVALENT_BASES` (`[GIT_BLOB, WORK_TREE, LF_NORM]`) |
| `J1 JSON` (`w5_calibration_round02_J1_v2.json`) | `de3435fabb5e936042592319c1cb999ba3b0ca1a6c97def7258ad3deb022c051` | **`YES`** | **`YES`** | **`YES`** | `MATCH_MULTIPLE_EQUIVALENT_BASES` (`[GIT_BLOB, WORK_TREE, LF_NORM]`) |
| `J1 CSV` (`w5_calibration_round02_J1_v2.csv`) | `052f8e0a166a4d3eded6b46fafe716e0c9bb76e8b3476f7822361228c80e4e4c` | **`YES`** | **`YES`** | **`YES`** | `MATCH_MULTIPLE_EQUIVALENT_BASES` (`[GIT_BLOB, WORK_TREE, LF_NORM]`) |
| `J2 JSON` (`w5_calibration_round02_J2_v2.json`) | `30f7766dc3f9c5c817b6cd85b8733e5ca46a17ad23cb7ea55144c5e91d43fb85` | **`YES`** | **`YES`** | **`YES`** | `MATCH_MULTIPLE_EQUIVALENT_BASES` (`[GIT_BLOB, WORK_TREE, LF_NORM]`) |
| `J2 CSV` (`w5_calibration_round02_J2_v2.csv`) | `7483e0db085d42374f47e0d6054b72ca4194e14ff8a2fa0660bf0aafdaac0b1b` | **`YES`** | **`YES`** | **`YES`** | `MATCH_MULTIPLE_EQUIVALENT_BASES` (`[GIT_BLOB, WORK_TREE, LF_NORM]`) |
| `J3 JSON` (`w5_calibration_round02_J3_v2.json`) | `8a4f2413548938ad0ad9ee36c4f14977a072bffc00765adef5b20c0cb0cf53bc` | **`YES`** | **`YES`** | **`YES`** | `MATCH_MULTIPLE_EQUIVALENT_BASES` (`[GIT_BLOB, WORK_TREE, LF_NORM]`) |
| `J3 CSV` (`w5_calibration_round02_J3_v2.csv`) | `08599d1b1c3bf2c485d66220e2bab2692d91c74d359ea1e28979e33ab7ab8428` | **`YES`** | **`YES`** | **`YES`** | `MATCH_MULTIPLE_EQUIVALENT_BASES` (`[GIT_BLOB, WORK_TREE, LF_NORM]`) |

Furthermore, all secondary `canonical_json_sha256` / `json_canonical_object_sha256` values in the Round 02 manifest match `CANONICAL_JSON_SHA256` (`MATCH_CANONICAL_JSON`).

---

## 7. Overall Scientific Impact Classification & Recommendation

* **Overall Classification:** `HISTORICAL_MANIFEST_INCONSISTENCY`
  * **Rationale:** While `rec_eval_01_prereg_manifest_v1.json`, Round 01 raw forensic CSVs, and Round 02 packages all reproduce directly from committed Git blob and working-tree bytes, the two earlier sub-manifests (`w5_reproducibility_manifest_v1.json` and `w5_annotation_manifest_v1.json`) store `CRLF` working-tree hashes (`98a86723...`, `740d81e3...`, `b1c79924...`, etc.) for files that are stored and checked out as `LF` (`4f0c77dc...`, `598bde75...`, `98601330...`, etc.). Those two historical sub-manifests cannot be reconciled with the committed `LF` blobs or with `rec_eval_01_prereg_manifest_v1.json` without representation-specific (`LF -> CRLF`) interpretation.
* **Formal Amendment Recommended:** `YES` (`true`)
  * **Recommended Non-Mutating Remediation (Not Implemented in This Audit Task):** If desired by the methodology owner (ChatGPT), a non-mutating W5 EOL compatibility erratum record (analogous to `data/manifests/dataset-freeze-v2-eol-compat.json`) and explicit `newline="\n"` hardening in legacy builder scripts can be introduced under a dedicated amendment task without altering any frozen historical artifact bytes.
