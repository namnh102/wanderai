# GOMATE W07 — `Route 1B` Human Annotator & Adjudicator Rubric Card (`V1`)

- **Target Roles:** `HUMAN_ANNOTATOR_01`, `HUMAN_ANNOTATOR_02`, `HUMAN_ADJUDICATOR_03`
- **Governing Rules:** `W07-B2 Protocol v1.0`, `Annex v0.2.2`, `Method Amendment 01 v0.3.1` (`f5560a95...`)
- **Strict Blindness:** Workbooks contain **ONLY** query text, scope/facets, document text (`canonical_text_S`), source type, language, and packet UUID. You **do NOT** see retriever arm (`C0/C1`, `BM25/Dense/RRF`), rank, score, or `pre_rank_answerability`.

---

## 1. Four Mutually Exclusive Labels (`REL_2 | REL_1 | REL_0 | NA`)

| Label | Definition (Judge Strictly on Visible `canonical_text_S` Text) | Evidence Quote Requirement | `plausible_unsupported_lure` |
|---|---|---|---|
| **`REL_2`** | **Direct Complete Support:** `canonical_text_S` directly, unambiguously, and completely answers **every requested facet** of the query without guessing or outside knowledge. | **`>= 1` verbatim quote** (`exact_quote`, `start_char`, `end_char`) matching `canonical_text_S[start:end]` | Leave `null` (or `0`) |
| **`REL_1`** | **Partial / Contextual Support:** `canonical_text_S` directly supports **some** requested facet(s) or gives relevant verifiable context for the query, but misses another key facet (e.g., answers opening hours but not ticket price). | **`>= 1` verbatim quote** matching `canonical_text_S[start:end]` | Leave `null` (or `0`) |
| **`REL_0`** | **Non-Supporting / False Premise / Off-Topic:** Does not establish factual support for the query (including unanswerable / false-premise queries). | **Empty list `[]`** (no support quotes) | **REQUIRED integer `1` or `0`** |
| **`NA`** | **Unassessable / Technical Defect Only:** Text is garbled, corrupted, or language/encoding makes judgment impossible. **NEVER** use `NA` simply because the doc is unhelpful — use `REL_0` for unhelpful docs! | Empty list `[]` | `null` (or `0`/`1` only if defect analysis notes lure) |

---

## 2. Mandatory Quality & Integrity Invariants (`Fail-Closed` by Scorer)

1. **Exact Character Quote Verification:** Every quote in `evidence_quotes` must satisfy:
   $$\texttt{canonical\_text\_S[start\_char : end\_char]} == \texttt{exact\_quote}$$
   Never paraphrase, normalize whitespace inside `exact_quote`, or cite text from memory.
2. **Forbidden `R_AUDIT` Marker Exclusion (`D03.3`):**
   - `canonical_text_S` still displays inline verification tags such as `[CORROBORATED: osm:...]` or `[AUDIT_TAG: ...]` cleanly removed from index view `V`.
   - Your `evidence_quotes` **MUST NOT** overlap any deleted `R_AUDIT` marker range (`EVIDENCE_SPAN_OVERLAPS_DELETED_R_AUDIT_MARKER` rejects the submission). Select only the factual travel sentence itself!
3. **`plausible_unsupported_lure` on Every `REL_0` Item (`G15-F06`):**
   - Set **`1`** when the passage discusses the same city/place or looks topically enticing (high lexical bait — e.g., mentions "bãi biển Mỹ Khê" and "vé", or a plausible claim without establishing the queried condition) so an LLM/reader might falsely treat it as supporting.
   - Set **`0`** when the passage is clearly unrelated or obviously lacks plausible bait.
4. **Zero Sibling Propagation (`G15-F02`):**
   - Grade each `(query_id, document_id)` independently on its own `canonical_text_S`. Never copy a score from another document sharing a POI name or lineage without verifying the exact text in front of you.
5. **Independent Dual-Blind Rule:**
   - `ANNOTATOR_01` and `ANNOTATOR_02` work **completely independently** with zero cross-communication until both workbooks are locked and `build_adjudication_queue` exports disagreements.

---

## 3. Adjudication Rules (`HUMAN_ADJUDICATOR_03`)

`build_adjudication_queue` flags every pair where `ANNOTATOR_01` and `ANNOTATOR_02` differ on:
- `GRADE_MISMATCH` (`REL_0/1/2` difference)
- `NA_CONFLICT` (`NA` vs `REL_*`)
- `LURE_MISMATCH` (both `REL_0` with `lure 0` vs `1`)
- `DISJOINT_EVIDENCE_SPANS` (both positive `REL_1`/`REL_2` but quoted completely non-overlapping text offsets)

For each discordant item, `HUMAN_ADJUDICATOR_03` selects the final authoritative label, `plausible_unsupported_lure` (for `REL_0`), verified verbatim `evidence_quotes`, and a concise written `rationale`.
