# W5-HASH-ERRATUM-01 — Formal Historical W5 Hash-Basis Erratum

- **Erratum ID**: `W5-HASH-ERRATUM-01`
- **Status**: `ACTIVE`
- **Source Audit ID**: `W5-HASH-AUDIT-01` (`data/evaluation/reca_w5/audits/w5_hash_eol_audit_v1.json`, `docs/research/w5_hash_eol_audit_v1.md`)
- **Source Audit Base SHA**: `1c7e43b39f4009e9620181d0c0c5a8151788abb7`
- **Erratum Base `develop` SHA**: `8f7db565e9ea70085a505745fd78326b49c1e243`
- **Classification**: `HISTORICAL_MANIFEST_INCONSISTENCY`
- **Content Integrity Failure**: `false`
- **Content Difference Found**: `false`
- **Representation-Only Difference Found**: `true`
- **Historical Hashes Rewritten**: `false`
- **Preregistration Modified**: `false`
- **Scientific Data Modified**: `false`
- **Scientific Result Impact**: `NONE`
- **Authoritative W5 Hash Basis**: `sha256_git_committed_blob_content`

---

## 1. What Was Observed

During forensic verification of the W5 evaluation artifact inventory (`W5-HASH-AUDIT-01`, inspecting **35** hashed artifacts and **83** stored SHA-256 hash references across manifests, documentation, scripts, and tests), **19** stored SHA-256 values inside two early pre-preregistration preparation manifests (`data/evaluation/reca_w5/w5_reproducibility_manifest_v1.json` and `data/evaluation/reca_w5/annotation/w5_annotation_manifest_v1.json`) did not match the SHA-256 computed directly over the committed Git blobs (`LF` line endings), even though every single one of those **19** stored values reproduced **100% identically** when `LF -> CRLF` normalization was applied to the committed Git blobs.

Meanwhile, the authoritative W5 preregistration manifest (`data/evaluation/reca_w5/rec_eval_01_prereg_manifest_v1.json`) explicitly declared `artifact_hash_basis = "sha256_git_committed_blob_content"` and matched the committed Git blob (`LF`) bytes across all **14** preregistered artifacts with zero discrepancy.

---

## 2. Why CRLF and LF Generate Different SHA-256 Digests

SHA-256 is a cryptographic hash function over raw byte sequences:

- Under Unix/Git-normalized line endings (`LF`), each line break is a single byte (`0x0A`, `\n`).
- Under Windows native text line endings (`CRLF`), each line break is two bytes (`0x0D 0x0A`, `\r\n`).

When a Python script on Windows writes a text or JSON file using `open(path, "w", encoding="utf-8")` without specifying `newline="\n"`, Python translates `\n` to `\r\n` on disk. If the script immediately hashes that working-tree file before Git commits it under `.gitattributes` (`* text=auto eol=lf`), the script records the `CRLF` working-tree SHA-256, whereas Git normalizes and stores the committed blob with `LF` line endings. Changing even a single `\r\n` to `\n` changes the byte stream length and produces a completely different SHA-256 digest despite identical semantic text and JSON data structures.

---

## 3. Which Legacy Manifests Are Affected

Exactly two **pre-preregistration** legacy preparation manifests contain target artifact hashes computed over pre-commit Windows `CRLF` working-tree bytes:

1. `data/evaluation/reca_w5/w5_reproducibility_manifest_v1.json` (generated during `W5-PREP-01` by `scripts/build_w5_eval_pool.py` — **5** target hash fields).
2. `data/evaluation/reca_w5/annotation/w5_annotation_manifest_v1.json` (generated during `W5-PREP-02` by `scripts/build_w5_annotation_package.py` — **14** target hash fields covering **10** unique target artifacts).

### Mandatory Legacy Manifest Interpretation

- **Preserved Unchanged**: The historical hash values in `w5_reproducibility_manifest_v1.json` and `w5_annotation_manifest_v1.json` are preserved byte-identically as historical provenance records and **must not be rewritten**.
- **Not Content Corruption**: They are **not** evidence of data tampering or content corruption (`content_difference_found = false`).
- **Deterministic Reproduction**: All 19 fields reproduce deterministically from the committed Git blobs via pure `LF -> CRLF` byte normalization (`representation_only_difference_found = true`, `unknown_hash_basis_count = 0`).
- **Non-Canonical Status**: They **must not** be treated as canonical committed-Git-blob hashes; any verification of committed Git blobs must use the authoritative preregistration manifest (`rec_eval_01_prereg_manifest_v1.json`) or the resolution index in Section 9 below.

---

## 4. Why No Scientific Content Changed

1. **Zero Semantic or Structural Difference**: Parsing the `LF` committed Git blobs and the `CRLF`-normalized byte streams yields identical JSON ASTs (`CANONICAL_JSON_SHA256`), identical Markdown text, and identical Python ASTs.
2. **Candidate Pools, Scenarios, and Rubric Untouched**: None of the 357 curated POIs, 12 primary scenarios (`302` scenario-POI candidate records), 3 thin diagnostic scenarios, `W5-RUBRIC-V1` criteria, or recommender algorithms (`REC-A1`, `REC-A2`) were altered in any way.
3. **Zero Impact on Experimental Outcomes**: Because `HUMAN-GT` remains `false`, qualifying independent human judgments remain `0`, and no recommender comparison has been performed, `scientific_result_impact = "NONE"`.

---

## 5. Which Manifest Is Authoritative for the W5 Scientific Freeze

The sole authoritative W5 preregistration manifest is:

- **Manifest**: `data/evaluation/reca_w5/rec_eval_01_prereg_manifest_v1.json`
- **Declared Hash Basis**: `sha256_git_committed_blob_content`
- **Source Commit SHA**: `35f82b30aa474d33036df656d70528dc20328d39`

All **14** preregistered artifacts in `rec_eval_01_prereg_manifest_v1.json` (including `gomate_places_freeze_v2.json`, `w5_primary_scenarios_v1.json`, `w5_thin_diagnostic_scenarios_v1.json`, `w5_candidate_pool_internal_v1.json`, `w5_candidate_pool_blinded_v1.json`, `w5_reproducibility_manifest_v1.json`, `w5_rubric_v1.md`, `w5_judge_instructions_v1.md`, `w5_calibration_v1.json`, `w5_annotation_manifest_v1.json`, `w5_metadata_sufficiency_v1.json`, `w5_merged_ground_truth_template_v1.json`, `scripts/evaluate_w5_recommenders.py`, and `scripts/analyze_w5_judgments.py`) match `GIT_BLOB_BYTES_SHA256`, `WORKING_TREE_BYTES_SHA256`, and `LF_NORMALIZED_UTF8_SHA256` simultaneously across platforms.

---

## 6. How Round 01 Raw CSV Submissions Are Treated (Forensic Exception)

Round 01 raw CSV submissions (`data/evaluation/reca_w5/calibration_submissions/raw_v1/` and `inbox/`) are intentionally governed by a separate forensic preservation rule:

- **Declared Hash Basis**: `RAW_RECEIVED_FILE_BYTES_SHA256`
- **Gitattributes Policy**: `data/evaluation/reca_w5/calibration_submissions/.gitattributes` (`*.csv -text whitespace=cr-at-eol`), which disables Git EOL conversion so the exact received `CRLF` bytes are preserved in both Git blobs and working-tree checkouts on all platforms.
- **Authoritative Round 01 Raw CSV Hashes** (from `data/evaluation/reca_w5/calibration_submissions/w5_calibration_raw_manifest_v1.json`):
  - **J1** (`J1_w5_calibration_raw_v1.csv` / `w5_calibration_J1_completed.csv`):
    `7a3b58f20169c98a7b472952e480afb96d34e58613afa0032a58d540062393ba`
  - **J2** (`J2_w5_calibration_raw_v1.csv` / `w5_calibration_J2_completed.csv`):
    `b8464c133df5757cd4c1e741a21a5b2392544a175dc2ec32e5d1e6a4d2721707`
  - **J3** (`J3_w5_calibration_raw_v1.csv` / `w5_calibration_J3_completed.csv`):
    `b2094cafb458f0ebdea1dd28ec4d5ef723062e449c3b51602edaaee00a86ba3f`
- **File Integrity vs. Scientific Qualification**:
  - **File Integrity**: `PASS` (exact received bytes frozen and verified).
  - **Scientific Qualification**: `FAIL` (`round_status = "INVALIDATED_FOR_PROTOCOL"`, `scientific_use = "FORENSIC_NON_QUALIFYING_EVIDENCE_ONLY"`, `qualifying_independent_human_judgments = 0`, `calibration_review_eligible = false`, `human_gt = false`).
  - These files are preserved strictly as forensic evidence of the invalidated Round 01 session (`W5-CAL-INCIDENT-01`) and **must never be interpreted as valid or qualifying human relevance labels**.

---

## 7. How Round 02 Prevents Recurrence

Round 02 (`W5-CAL-ROUND-02`, manifest `data/evaluation/reca_w5/calibration_round02_ops/w5_calibration_round02_manifest_v1.json`, status `PREPARED_NOT_STARTED`) prevents any `LF` vs. `CRLF` ambiguity by construction:

1. **Explicit LF-Only Generation**: `scripts/prepare_w5_calibration_round02.py` writes all JSON and CSV files with explicit `newline="\n"` and `lineterminator="\n"`.
2. **Dual Cross-Platform Hash Policy**:
   - **Primary Hash Basis**: `COMMITTED_GIT_BLOB_UTF8_LF_NORMALIZED_SHA256`
   - **Secondary JSON Hash Basis**: `CANONICAL_SORTED_COMPACT_JSON_UTF8_SHA256`
   - **Line Ending Policy**: `LF_ONLY_FOR_ALL_NEW_ROUND02_ARTIFACTS`
3. All **7** Round 02 control artifacts (`w5_calibration_v2.json` and `J1`/`J2`/`J3` JSON + CSV judge packages) and **3** Round 02 operational contracts match `GIT_BLOB_BYTES_SHA256`, `WORKING_TREE_BYTES_SHA256`, and `LF_NORMALIZED_UTF8_SHA256` simultaneously.

---

## 8. Compact Summary Table & Mandatory Rules for Future Developers and Researchers

| Artifact class | Historical basis | Canonical interpretation | Action |
| :--- | :--- | :--- | :--- |
| Legacy PREP manifests | `PRECOMMIT_WINDOWS_CRLF_BYTES` | historical provenance only | `DO NOT REWRITE` |
| Authoritative prereg manifest | `COMMITTED_GIT_BLOB_BYTES` | canonical W5 scientific freeze | `USE AS AUTHORITATIVE` |
| Round01 raw CSV | `RAW_RECEIVED_FILE_BYTES` | forensic evidence only | `PRESERVE EXACT BYTES` |
| Round02 artifacts | `LF Git blob + canonical JSON` | cross-platform canonical | `USE DECLARED POLICY` |

### Exact Rules Future Developers and Researchers Must Follow

1. **RULE-01 (Authoritative Freeze)**: Always use `data/evaluation/reca_w5/rec_eval_01_prereg_manifest_v1.json` (`artifact_hash_basis = "sha256_git_committed_blob_content"`) as the authoritative hash reference for preregistered W5 evaluation artifacts.
2. **RULE-02 (Legacy Provenance Preservation)**: Never edit or re-freeze `w5_reproducibility_manifest_v1.json` or `w5_annotation_manifest_v1.json`. When inspecting their 19 target hash fields, resolve them via `data/evaluation/reca_w5/audits/w5_hash_basis_erratum_v1.json` (`legacy_to_canonical_resolution_index`).
3. **RULE-03 (Round 01 Forensic Quarantine)**: Preserve Round 01 raw CSV files (`J1`, `J2`, `J3`) byte-identically under `RAW_RECEIVED_FILE_BYTES_SHA256`, and never use Round 01 labels for reliability (`alpha`), rubric tuning, `HUMAN-GT`, or recommender evaluation.
4. **RULE-04 (Future Artifact Authoring)**: All new evaluation generators, manifests, and annotation packages must write `LF` line endings explicitly (`newline="\n"`, `lineterminator="\n"`) and record `COMMITTED_GIT_BLOB_UTF8_LF_NORMALIZED_SHA256` (plus `CANONICAL_SORTED_COMPACT_JSON_UTF8_SHA256` for JSON artifacts).

---

## 9. Legacy-to-Canonical Resolution Index (19 Fields)

| Legacy Manifest | Field Key | Target Artifact | Historical CRLF SHA-256 (`PRECOMMIT_WINDOWS_CRLF_BYTES`) | Canonical Git-Blob LF SHA-256 (`sha256_git_committed_blob_content`) | In Prereg Manifest |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `w5_reproducibility_manifest_v1.json` | `freeze_checksum` | `data/curated/gomate_places_freeze_v2.json` | `93681135d94b379f28802aa75204a0a4c7bec4039f85d28e76ae6737e792e245` | `f7517938598e3923906763f8f31334a500ee88bc06232f2992d38e2fcb28a444` | `YES` |
| `w5_reproducibility_manifest_v1.json` | `primary_scenario_manifest_sha256` | `data/evaluation/reca_w5/w5_primary_scenarios_v1.json` | `98a86723e7a2d16fbb2acebe1a39379f525a973cc0d854191318931484e9d553` | `4f0c77dccc2c0bae32f5d87f1364a8e1487a83e9b7344a9d8d3c9d0528bc29fb` | `YES` |
| `w5_reproducibility_manifest_v1.json` | `thin_diagnostic_manifest_sha256` | `data/evaluation/reca_w5/w5_thin_diagnostic_scenarios_v1.json` | `c90773202aab20e6e30fd8c9cd37157c6d1a4fcb6bf7b718d023c32a6fc50f69` | `538233a937acdd38ea208980a9ba629391b61e721363189f10f6087186fcfa77` | `YES` |
| `w5_reproducibility_manifest_v1.json` | `internal_pool_sha256` | `data/evaluation/reca_w5/w5_candidate_pool_internal_v1.json` | `29c3c8192f8d39e733b6753d3c4ccdd19025324b673ce7b8601a0ca15843bd24` | `32b25ef8ffc19d671513f771d3d3a0d23ceb9d0cf614ace1eded94d8c84126c6` | `YES` |
| `w5_reproducibility_manifest_v1.json` | `blinded_pool_sha256` | `data/evaluation/reca_w5/w5_candidate_pool_blinded_v1.json` | `8a4dce96ea156ae6ef3d79a31863d441a3d77df914f3b500f872475102d965be` | `8f178e06b1b93e59b3a53f1b2bf1b6ecc697ccfa610d56783b613b6aa2f06ec7` | `YES` |
| `annotation/w5_annotation_manifest_v1.json` | `artifact_hashes.w5_rubric_v1.md` | `data/evaluation/reca_w5/annotation/w5_rubric_v1.md` | `b1c799247ce39763a941fafdc929780c32007e88a5fdc4bf62c41ee34a7b510e` | `98601330b366ea99b2254509adf84762375460ab66a93ef3af2ef32df63ef8a4` | `YES` |
| `annotation/w5_annotation_manifest_v1.json` | `artifact_hashes.w5_judge_instructions_v1.md` | `data/evaluation/reca_w5/annotation/w5_judge_instructions_v1.md` | `70d802364c80197993f7ca8e08b6385a7cd72f5eaa5d915a1dfa61c2e7e49dde` | `5d579d4c0b76a9c37eadac869db6e4f6abaa6c8c36f146d3176452d1fc56b4bb` | `YES` |
| `annotation/w5_annotation_manifest_v1.json` | `artifact_hashes.w5_judge_J1_v1.json` | `data/evaluation/reca_w5/annotation/w5_judge_J1_v1.json` | `96ee079836407c423a7b2cfb3559f11ead970d92c24f5d6c839796a372faa687` | `11a28f8f026ef5c70ed03d896c94270d9c8c3252bdc70e1bc838705425c61b5b` | `NO (pre-prereg judge pkg)` |
| `annotation/w5_annotation_manifest_v1.json` | `artifact_hashes.w5_judge_J2_v1.json` | `data/evaluation/reca_w5/annotation/w5_judge_J2_v1.json` | `2e0a256a37b0634a4641495da36e234df790444de5b3821035c3f3261ab7f703` | `63dafdf77e50d7c437996b738a750daf895a8d8192b7eeec6ca73ecc09728f3e` | `NO (pre-prereg judge pkg)` |
| `annotation/w5_annotation_manifest_v1.json` | `artifact_hashes.w5_judge_J3_v1.json` | `data/evaluation/reca_w5/annotation/w5_judge_J3_v1.json` | `827e32b7e8cf4572a455a117236cafb57de1c1b5cac1c6e96902725f8e722c7f` | `9959326d1e306b9c52e3632cb67c4320df9e633881c14f02961bd6e9b2a19b8e` | `NO (pre-prereg judge pkg)` |
| `annotation/w5_annotation_manifest_v1.json` | `artifact_hashes.w5_calibration_v1.json` | `data/evaluation/reca_w5/annotation/w5_calibration_v1.json` | `740d81e3c3a613575a687af9291102d27e9dd8c61f1fc8f40e913c4c2ccfbc60` | `598bde75d464f3e58299522090833a8521a59d4c0755e13399ad46050a2ca823` | `YES` |
| `annotation/w5_annotation_manifest_v1.json` | `artifact_hashes.w5_annotation_template_v1.json` | `data/evaluation/reca_w5/annotation/w5_annotation_template_v1.json` | `bdc92d7885d7043311303d7bbd8a168e088c8c3a5cc361b7983154daa4e390fd` | `9badb4f3c41c3b86ebe5246a7abd22d68ac57234a62aeb1525d8116566d482c5` | `NO (template)` |
| `annotation/w5_annotation_manifest_v1.json` | `artifact_hashes.w5_merged_ground_truth_template_v1.json` | `data/evaluation/reca_w5/annotation/w5_merged_ground_truth_template_v1.json` | `624ab82038099b33d775610001bb99b8b5f6321a10381f068483b12619e5be30` | `3f33c6f866dec90f33212c5851a389ecc0b0f10d6e9da8ab8077aa8e305ab830` | `YES` |
| `annotation/w5_annotation_manifest_v1.json` | `artifact_hashes.w5_adjudication_template_v1.json` | `data/evaluation/reca_w5/annotation/w5_adjudication_template_v1.json` | `f092b918a339151f012d724809c687ccf276ce20cf6b08bde7bcccbe3bb752b2` | `9d811ef8f9c1ff6e248fedd4ae5f4b0d409937abab8ba80c68a9ab227604c775` | `NO (template)` |
| `annotation/w5_annotation_manifest_v1.json` | `artifact_hashes.w5_metadata_sufficiency_v1.json` | `data/evaluation/reca_w5/annotation/w5_metadata_sufficiency_v1.json` | `302a47f2c774ccf51302a8a6ae1b991a92c1cd93e5bf19579bae245547f4224b` | `c58f9a709cb338596536fae78ae444e9c8de9e070cf3b8449cbba64fe05fa989` | `YES` |
| `annotation/w5_annotation_manifest_v1.json` | `judge_packages.J1.sha256` | `data/evaluation/reca_w5/annotation/w5_judge_J1_v1.json` | `96ee079836407c423a7b2cfb3559f11ead970d92c24f5d6c839796a372faa687` | `11a28f8f026ef5c70ed03d896c94270d9c8c3252bdc70e1bc838705425c61b5b` | `NO (pre-prereg judge pkg)` |
| `annotation/w5_annotation_manifest_v1.json` | `judge_packages.J2.sha256` | `data/evaluation/reca_w5/annotation/w5_judge_J2_v1.json` | `2e0a256a37b0634a4641495da36e234df790444de5b3821035c3f3261ab7f703` | `63dafdf77e50d7c437996b738a750daf895a8d8192b7eeec6ca73ecc09728f3e` | `NO (pre-prereg judge pkg)` |
| `annotation/w5_annotation_manifest_v1.json` | `judge_packages.J3.sha256` | `data/evaluation/reca_w5/annotation/w5_judge_J3_v1.json` | `827e32b7e8cf4572a455a117236cafb57de1c1b5cac1c6e96902725f8e722c7f` | `9959326d1e306b9c52e3632cb67c4320df9e633881c14f02961bd6e9b2a19b8e` | `NO (pre-prereg judge pkg)` |
| `annotation/w5_annotation_manifest_v1.json` | `calibration_package.sha256` | `data/evaluation/reca_w5/annotation/w5_calibration_v1.json` | `740d81e3c3a613575a687af9291102d27e9dd8c61f1fc8f40e913c4c2ccfbc60` | `598bde75d464f3e58299522090833a8521a59d4c0755e13399ad46050a2ca823` | `YES` |
