# GOMATE W07 — `Route 1B` Formal Approval Conditions & Human `2+1` Labeling Package (`V1`)

- **Package Status:** `PREPARATION_READY_FOR_OWNER_AND_CHATGPT_SIGNOFF` (**Formal `G2/G2A/G2B/G3/G4/FINAL-50/G5` remain `HOLD`**)
- **Prior Preflight Baseline:** `STUB-01..05` = `PASS_WITH_EXPLICIT_EVIDENCE_SCOPE` (permanently sealed — **do NOT re-run**); `synthetic-prep` = `PASS_SCOPED_SYNTHETIC_PREPARATION`; anchor repo (`9bab3e33...`) untouched.
- **Selected Route (`OD-G15-05`):** **`ROUTE_1B_POOLED_2PLUS1_HUMAN_OPTION_B`** (`Method Amendment 01 v0.3.1`, Option B Two-Stage Blinded Pooled Human Evaluation)
- **Machine-Checked Bundle Template:** [`W07_ROUTE_1B_FORMAL_APPROVAL_BUNDLE_TEMPLATE_V1.json`](W07_ROUTE_1B_FORMAL_APPROVAL_BUNDLE_TEMPLATE_V1.json)
- **Field Annotator Card:** [`W07_ROUTE_1B_ANNOTATOR_RUBRIC_AND_WORKFLOW_CARD_V1.md`](W07_ROUTE_1B_ANNOTATOR_RUBRIC_AND_WORKFLOW_CARD_V1.md)
- **Preflight Gate Checker:** [`scripts/prepare_w07_route1b_formal_pack.py`](../scripts/prepare_w07_route1b_formal_pack.py) (`validate_formal_route1b_authorization_bundle(..., require_formal_execution=True)`)

---

## 1. Mandatory Hash & Method Authorities Required Before Opening `G2A / G3 / G2B / G4`

| Authority Layer | Exact Required Artifact | Exact Verified SHA-256 | Current State | Unlock Action Required |
|---|---|---|---|---|
| **Protocol** | `W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md` | `5056c5c2373ee9584b8850ba49411160cc2c382ad6315aaada4c05fb9b0030c2` (LF) | `OWNER_APPROVED` | Preserve unchanged (`0` byte edits) |
| **G1.5 Tech Freeze** | `GOMATE_W07_G15_TECHNICAL_ANNEX_V0_2_2_CANDIDATE_2026-11-21.md` | `e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940` | `OD-G15-01..04 TECH FREEZE` | Promote cleanly to effective `v1.0` once `OD-G15-05` closes |
| **Route 1B Amendment** | `W07_B2_METHOD_AMENDMENT_01_V0_3_1_OPTION_B_REVIEW_DRAFT_NOT_EFFECTIVE.md` | `f5560a95a6893dbc09681004875500f822a45451b9891086c8b3636ec71561d6` | **`NOT_EFFECTIVE` (Draft)** | 1) Independent ChatGPT re-audit **`PASS`**<br>2) Explicit **Project Owner** signature & `OWNER_SIGNED_EFFECTIVE` |
| **2+1 Human Staffing** | Off-repo signed roster (`GOMATE_W07_OD_G15_05_HUMAN_ROSTER_RECEIPT_V1`) | Non-zero SHA-256 of off-repo roster record (`roster_status = COMMITTED_BY_OWNER`) | **`HOLD` (`TEMPLATE_UNSIGNED`)** | Bind **3 distinct humans**: `HUMAN_ANNOTATOR_01`, `HUMAN_ANNOTATOR_02`, `HUMAN_ADJUDICATOR_03` (zero `TEMPLATE_*` / `SYN_*` IDs) |
| **G3 Code Freeze** | Audited G3 commit SHA + `FX-01..16` + DEV audit | Non-zero 40-char Git commit SHA (`g3_no_final_exposure_attested = true`) | **`HOLD`** | Freeze exact G3 commit before inspecting any `FINAL-50` query |

> [!CAUTION]
> Any execution initiated without `validate_formal_route1b_authorization_bundle(..., require_formal_execution=True)` returning `formal_execution_authorized = True` is **NON-CONFIRMATORY** and will fail closed at code/validator level (`PermissionError`). Any artifact generated in offline preparation carries explicit `synthetic_mode_disclosure.execution_classification = "SYNTHETIC_PREP_ONLY"`.

---

## 2. Exact Staged Route 1B Execution Sequence (`§8` Amended)

1. **`G1.5` Full Closure (`OD-G15-05` Exit):**
   - Sign off `Method Amendment 01 v0.3.1` (`f5560a95...`) after independent ChatGPT audit `PASS`.
   - Record off-repo `2+1` human roster receipt (`COMMITTED_BY_OWNER`).
   - Run `python scripts/prepare_w07_route1b_formal_pack.py --bundle <signed_bundle.json> --formal-gate` -> must pass with zero warnings.
2. **`G2A` (`PRE_G3_QUERY_LOCK`):**
   - Author the **corpus-blind `FINAL-50` queries** matching exact `5×3` strata/city quotas (`validate_pre_g3_query_manifest`, `40 Q_ans + 10 S5 Q_unans`), plus `<= 10 DEV` queries for `DEV_TIMING_PILOT_T0` (with zero overlap against `FINAL-50`).
   - Perform independent pre-rank source-only verification (`Q_ans` / `Q_unans` denominator lock + seed witness docs `G2ASeedDocs(q)`).
   - **Rule (`Method Amendment 01 v0.3.1 §4`):** Seal `pre_rank_answerability` internally for `G4` denominator; **`prepare_dual_blind_annotator_workbooks` now structurally omits `pre_rank_answerability`** so human judges never see it before `G2B` closure.
3. **`G3` Implementation & `DEV_TIMING_PILOT_T0`:**
   - Implement/verify `2×3` (`C0/C1 × BM25/Dense/RRF`) against `FX-01..16` on DEV/synthetic/pre-registered real-corpus smoke ONLY.
   - Measure median annotation rate (sec/pair) on `DEV <= 10` (`DEV_TIMING_PILOT_T0`) to set `capacity_envelope_max_votes` objectively. Freeze Git SHA.
4. **`SEALED_FINAL_POOL_EXPORT` (Separate Owner Approval):**
   - Single read-only run producing `g3_sealed_rankings_v1.jsonl` + 7-key rank-invariant `blind_annotation_packet.jsonl` for pooled union $P_q = \bigcup_{s=1}^6 \text{Top10Docs}(s,q) \cup \text{TargetPOISweep}(q) \cup \text{G2ASeedDocs}(q)$.
   - Compute exact $\sum_{q=1}^{50} |P_q|$. If $2 \times \sum |P_q| > \text{capacity\_envelope\_max\_votes}$, pause in `HOLD_CAPACITY_EXCEEDED` for schedule extension (**never truncate $P_q$ or coerce `UNJUDGED -> 0`**).
5. **`G2B` (`2+1` Blinded Human Grading & Adjudication):**
   - `HUMAN_ANNOTATOR_01` and `HUMAN_ANNOTATOR_02` grade 100% of items independently using the 7-key blind workbook (`REL_2`, `REL_1`, `REL_0` + `plausible_unsupported_lure ∈ {0,1}`, `NA`, verbatim quotes on `canonical_text_S` outside deleted `[CORROBORATED: ...]` `R_AUDIT` intervals).
   - Compute pre-adjudication agreement & weighted Cohen's $\kappa_w$ (`build_adjudication_queue`).
   - `HUMAN_ADJUDICATOR_03` independently resolves 100% of discordant items (`GRADE_MISMATCH`, `NA_CONFLICT`, `LURE_MISMATCH`, `DISJOINT_EVIDENCE_SPANS`).
   - Compile `qrels_v1.jsonl` + certify `Cert-1..Cert-4` (`compile_adjudicated_qrels`).
6. **`G4` Decoupled Scoring (`enforce_clean_sys_modules=True`):**
   - Score exact SHA-locked `g3_sealed_rankings_v1.jsonl` + `qrels_v1.jsonl`. Report conservative interval $[\overline{\text{nDCG}}_L, \overline{\text{nDCG}}_U]$ (`NO_EXACT_FULL_SET_ESTIMATE` whenever `Cert-4 = BOUNDED_NOT_EXACT`), paired bootstrap CIs, Holm-corrected permutation tests, `VisibleEvidenceSpanHit@10`, and `FalseSupportExposure@10`. `G5/G6` stay `HOLD`.

---

## 3. Human Staffing & Workload Envelope Request (To Owner)

| Resource Need | Specification | Volume Range Formula (Pre-`T0` Planning Only) | Budget / API Policy |
|---|---|---|---|
| **Human Annotator 01** | Native Vietnamese reader (English capable for `S4` queries), corpus/rank-blind | Pooled pairs $N = \sum_{q=1}^{50} |P_q| \le 6,850$ (expected hypothesis `900–1,600` pairs at `18–32`/query, **unverified until `T0`/export**) | **\$0 paid LLM APIs** (human effort only) |
| **Human Annotator 02** | Independent second human (no discussion with Annotator 01 prior to closure) | Same $N$ independent votes (`2 × N` total initial votes) | **\$0 paid LLM APIs** |
| **Human Adjudicator 03** | Distinct third reviewer (senior/research lead), blinded to system ranks & `pre_rank_answerability` | Discordant subset (~5–15% of $N$, determined only after `build_adjudication_queue`) | **\$0 paid LLM APIs** |

> [!IMPORTANT]
> **Hard Epistemic Rule:** Synthetic dry-run outputs (`run_w07_phase2_benchmark_dryrun.py`) prove tooling & schema mechanics only. They MUST NEVER be reported as empirical W07 retrieval findings or substitute for the 3 distinct humans listed above.
