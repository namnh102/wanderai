# GOMATE W07 — `OD-G15-05` Human `2+1` Ground-Truth SOP & Phase-2 Benchmark Readiness

- **Status:** Preparation & Synthetic Dry-Run Package (**STUB-01..05 `PASS` untouched; `STUB-06` & formal `G2/G2A/G2B/G3/G4/FINAL-50` remain strictly `HOLD`**)
- **Controlling Authorities:**
  - `W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md` (`5056c5c2...`)
  - `GOMATE_W07_G15_TECHNICAL_ANNEX_V0_2_2_CANDIDATE_2026-11-21.md` (`e78013fd...`)
  - `W07_G15_OD_G15_05_RELEVANCE_TRUTH_DECISION_NOTE_2026-11-21.md` (`adb047a2...`)

---

## 1. Non-Re-Execution & Governance Boundary

1. `STUB-01..04` (`CORRECTIVE_REPLAY_01`) and `STUB-05` (`TARGETED_STUB05_ONLY_REPLAY_01`) passed independent audit (`PASS_WITH_EXPLICIT_EVIDENCE_SCOPE`) and are **permanently sealed**. Do **NOT** re-run any STUB.
2. Formal benchmark gates (`G2/G2A/G2B`, `G3`, `G4`, `STUB-06`, `FINAL-50`, `DEV-5`, `T0`, paid LLM judge runs, winner selection) remain strictly **`HOLD`** until `OD-G15-05` is formally signed off.

---

## 2. `OD-G15-05` Human `2+1` Ground-Truth Workflow (`w07_g4_scorer.human_annotation`)

Implemented in zero-ML-import module `src/w07_g4_scorer/human_annotation.py`:

### Step A — Off-Repo Roster Binding (`validate_human_roster_receipt`)
- Validates `GOMATE_W07_OD_G15_05_HUMAN_ROSTER_RECEIPT_V1` (template at `docs/W07_OD_G15_05_HUMAN_ROSTER_RECEIPT_TEMPLATE_V1.json`).
- Enforces **3 distinct humans**: `human_annotator_01_id`, `human_annotator_02_id`, `human_adjudicator_03_id`.
- Rejects placeholder IDs (`TEMPLATE_*`, `SYN_*`) and zeroed SHA-256 commitments whenever `require_formal_commitment=True`.

### Step B — Blind 7-Key Packet Split (`prepare_dual_blind_annotator_workbooks`)
- Consumes ONLY the 7-key blinded rows produced by `w07_retrieval.blind_packet` (`packet_item_uuid`, `query_id`, `query_text`, `document_id`, `source_type`, `language`, `canonical_text_S`).
- Rejects any leakage columns (`rank`, `score`, `cell_id`, `arm`, `retriever`, span fields).
- Emits identical randomized item orderings for `HUMAN_ANNOTATOR_01` and `HUMAN_ANNOTATOR_02`.

### Step C — Per-Annotator Validation & Rubric (`validate_single_annotator_submissions`)
Each `(query_id, document_id)` judgment MUST select strictly from `REL_2 | REL_1 | REL_0 | NA`:
- **`REL_2` (Direct Complete Support):** Document directly & unambiguously satisfies all requested evidence facets. Requires `>= 1` verbatim `evidence_quotes` (`exact_quote`, `start_char`, `end_char`) with `canonical_text_S[start:end] == exact_quote`.
- **`REL_1` (Partial / Contextual Support):** Document answers part of the facet or gives relevant partial evidence. Requires `>= 1` verbatim `evidence_quotes`.
- **`REL_0` (Non-Supporting / Off-Topic):** Requires empty `evidence_quotes`, AND **must** set integer `plausible_unsupported_lure ∈ {0, 1}` (`1` when an unanswerable/false-premise passage contains plausible lexical/surface lures without true support, supporting `FalseSupportExposure@10`).
- **`NA` (Unassessable / Ambiguous Defect):** Must not be coerced to `0` (`load_external_qrels` contract preserved).
- **Marker Cleanliness (`D03.3`):** No positive `evidence_quotes` span may overlap any deleted `[CORROBORATED: ...]` `R_AUDIT` interval (`EVIDENCE_SPAN_OVERLAPS_DELETED_R_AUDIT_MARKER`).

### Step D — Pre-Adjudication Agreement & Adjudication Queue (`build_adjudication_queue`)
- Computes pre-adjudication exact label agreement, full agreement, and quadratic weighted Cohen's $\kappa_w$ across shared `{REL_0:0, REL_1:1, REL_2:2}` items.
- Emits every disagreement (`GRADE_MISMATCH`, `NA_CONFLICT`, `LURE_MISMATCH`, `DISJOINT_EVIDENCE_SPANS`) into the blinded queue for **`HUMAN_ADJUDICATOR_03`**.

### Step E — Sealed `qrels` Compilation & `Cert-1..Cert-4` Check (`compile_adjudicated_qrels`)
- Requires 100% coverage of all discordant pairs by distinct `HUMAN_ADJUDICATOR_03`.
- Re-verifies every adjudicated span verbatim against `canonical_text_S` and `R_AUDIT` exclusion.
- Emits native `qrels_v1.jsonl` (verified via `w07_g4_scorer.contracts.load_external_qrels`) and checks `Cert-1..Cert-4` (`EXACT_CERTIFIABLE`, `BOUNDED_CONSERVATIVE`, or `BLOCKED_INCOMPLETE_POOL`).

---

## 3. End-to-End Synthetic Phase-2 Dry-Run Harness (`$0` / Offline)

Run the standalone offline pipeline (zero real 137-doc corpus access, zero `FINAL-50` queries, zero live API calls):

```powershell
Set-Location <W07_PREP_ROOT>
$env:PYTHONPATH = "src"
python scripts/run_w07_phase2_benchmark_dryrun.py --output-dir ./out/W07_PHASE2_SYNTHETIC_BENCHMARK_DRYRUN_2026-11-22
```

This exercises the exact target chronology in `synthetic-prep`:
1. **`G2A / D01` Synthetic 50-Query `5×3` Quota Manifest** (`validate_final50_strata_and_city_quota`, isolated synthetic IDs `synq_*`).
2. **`G3` (`synthetic-prep`) `2×3` Ranking (`C0/C1 × BM25/Dense/RRF`)** + 7-key blinded packet export.
3. **`G2B` Human `2+1` Workbook $\to$ Pre-Adjudication $\kappa_w$ $\to$ Adjudication Queue $\to$ Compiled `qrels_v1.jsonl`**.
4. **Decoupled Clean-Process `G4` Scorer (`enforce_clean_sys_modules=True`)** emitting `g4_dryrun_scorecard.json` (`HUMAN_ADJUDICATED_QRELS`, `Cert-1..4`, `K1..K5` contrasts, `FalseSupportExposure@10`, `g5_status = "HOLD"`).
