# GOMATE W07 — `OD-G15-05` Relevance Truth Authority Decision Note: Controlling `2+1` Human Judges vs Signed, Supervisor-Confirmed AI-Proxy Amendment (`2026-11-21`)

- **Document ID:** `W07-G15-OD-G15-05-RELEVANCE-TRUTH-DECISION-NOTE-2026-11-21`
- **Current Gate State of `OD-G15-05`:** **`HOLD` (`UNRESOLVED SCIENTIFIC & GOVERNANCE BLOCKER`)**
- **Strict Non-Execution Attestation:** This decision note is a read-only scientific comparison prepared for the Project Owner, Thesis Supervisor, and Independent Auditor. **Zero relevance labels have been generated, zero `FINAL-50` queries have been authored or opened, and zero LLM / live API calls have been made (`\$0.00` spend).**

---

## 1. Why `OD-G15-05` Remains on `HOLD` After the `v0.2.2` Technical Freeze

On `2026-11-21`, the Project Owner chat-approved the bounded technical specification `GOMATE_W07_G15_TECHNICAL_ANNEX_V0_2_2_CANDIDATE_2026-11-21.md` (`71,761` B, SHA-256 `e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940`), locking `OD-G15-01` (`D01` corpus & `5×3` quota schema), `OD-G15-02` (`D03` `S -> V` stripper & `C0/C1` chunking), `OD-G15-03` (`D04/D05.1–D05.3/D06` `2×3` retrieval & `G4` scorer mechanics + Erratum `E01`), and `OD-G15-04` (`THRESH_STATIC_PRE_G3`).

However, **controlling authority `W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md` (`§0, §5, §8`, LF SHA-256 `5056c5c2373ee9584b8850ba49411160cc2c382ad6315aaada4c05fb9b0030c2`) remains unchanged**. Under literal `Protocol v1.0`:
- Primary relevance ground truth (`rel ∈ {0, 1, 2, NA}` and canonical evidence support spans `[start_char, end_char) ⊆ S`) **must** be produced by **`2` independent human annotators (`HUMAN_ANNOTATOR_01`, `HUMAN_ANNOTATOR_02`) plus `1` distinct human adjudicator (`HUMAN_ADJUDICATOR_03`)**, blinded to chunking/retrieval arm (`C0/C1`, `BM25/Dense/Hybrid RRF`).
- Because the `2+1` human roster is currently uncommitted and all AI-proxy candidate specifications (`G2A v2.0.1`, `G2B v1.1`, `AUTO-EVAL-01 v0.4.2`) remain unsigned drafts awaiting written Thesis Supervisor scope confirmation (`Block SV-01`), **`OD-G15-05` blocks full `G1.5` closure and all `G2/G2A/G2B`, `G3`, and `G4` formal benchmark executions**.

---

## 2. Side-by-Side Comparison of `OD-G15-05` Relevance Truth Routes

| Dimension | Route 1A: Literal `Protocol v1.0` (`Path A` — Exhaustive `2+1` Human) | Route 1B: Pooled `2+1` Human (`Option B` — `Method Amendment 01 v0.3.1`, `f5560a95...`) | Route 2: Signed, Supervisor-Confirmed AI-Proxy Amendment (`G2A v2.0.1` + `G2B v1.1` / `AUTO-EVAL-01 v0.4.2`) |
|---|---|---|---|
| **Controlling Authority Required** | Existing `Protocol v1.0` (`5056c5c2...`) + committed off-repo `2+1` human roster hash (`OD-G15-02`). No protocol amendment required. | Owner signature on `Method Amendment 01 v0.3.1` (`f5560a95...`) + committed off-repo `2+1` human roster hash. | **Written Thesis Supervisor confirmation (`Block SV-01`)** + Owner signature on versioned AI-proxy amendment + provider/data-rights/API clearance. |
| **Execution Chronology (`D05.4`)** | `G2` (`50 × 137` exhaustive pre-G3 grading) $\to$ `G3` (one-shot `2×3` ranking) $\to$ `G4` (exact scoring). | `G2A` (`FINAL-50` lock + fixed pre-rank $Q_{\text{ans}}$) $\to$ `G3` (sealed `2×3` ranking + rank-invariant union packet) $\to$ `G2B` (`2+1` human pooled grading + `Cert-1..4`) $\to$ `G4`. | `Stage-1 DEV-5` diagnostic calibration gate $\to$ `G2A` (`FINAL-50` lock + fixed pre-rank $Q_{\text{ans}}$) $\to$ `G3` (sealed `2×3` ranking + blind packet) $\to$ `G2B` (Dual-LLM `ORDER_A/ORDER_B` + deterministic span verifier) $\to$ `G4`. |
| **Human / API Workload** | `50 × 137 × 2 = 13,700` human pair votes + adjudication (`$0.00` API spend). | `~1,800–3,200` human pair votes across pooled top-$k$ union + pre-rank source-nominated docs (`$0.00` API spend). | `0` external human annotator hours; paid/quota-bound dual-provider API calls strictly capped by pre-authorized budget after `DEV-5` gate. |
| **Primary Estimand & Unjudged Residual Handling** | Exact `GoMate-nDCG@10` over fixed pre-rank $Q_{\text{ans}}$ (`0` `UNJUDGED` pairs). | Bounded `[nDCG_L@10, nDCG_U@10]` over fixed pre-rank $Q_{\text{ans}}$ tagged `NO_EXACT_FULL_SET_ESTIMATE` whenever $\text{IDCG}_L < \text{IDCG}_U$; coupled contrast bounds $[\Delta_{\min}, \Delta_{\max}]$ with winner rule $\Delta_{\min} \ge +0.030$. | Bounded `[LLMProxy-nDCG_L@10, LLMProxy-nDCG_U@10]` over fixed pre-rank $Q_{\text{ans}}$ (`UNJUDGED` never coerced to `0`; winner rule $\Delta_{\min} \ge +0.030$ else `NO_CLEAR_PROXY_WINNER`). |
| **Inter-Judge Reliability Gate** | Human quadratic weighted Cohen's $\kappa$ + raw agreement reported pre-adjudication (`Protocol v1.0 §5`). | Human quadratic weighted Cohen's $\kappa$ + `100%` `Cert-1..Cert-4` completion across pooled packet. | Dual-family/dual-order prompt-swap invariance $\ge 0.90$, quadratic $\kappa \ge 0.75$ across `ORDER_A`/`ORDER_B`, and `100%` deterministic `exact_quote ⊆ S` (`Cert-1..3 == 1.00`); disagreements untouched by human tie-breaking resolve conservatively or trigger `HOLD`. |

---

## 3. Mandatory Scientific Claim Limitations Under Any AI-Proxy Amendment (`Route 2`)

If the Project Owner and Thesis Supervisor elect Route 2 (AI-proxy amendment) rather than Route 1A/1B (`2+1` human judges), the following **five non-negotiable scientific claim limitations** must be enforced in code, receipts, and thesis prose:

1. **Explicit `NOT_PERFORMED` Declaration for Human Ground-Truth Endpoints:**
   - The thesis and all `G4` scorecards must record: `human_2plus1_annotation = NOT_PERFORMED`, `human_inter_annotator_kappa = NOT_PERFORMED`, and `human_adjudicated_GoMate_nDCG10 = NOT_PERFORMED`. AI-proxy outputs may never be presented as human relevance truth.
2. **Mandatory Proxy-Qualified Metric Naming:**
   - Primary and diagnostic retrieval metrics must carry explicit proxy/deterministic prefixes (`LLMProxy-GoMate-nDCG@10`, `LLMProxy-MRR@10`, `LLMProxy-Recall@10`, `CanonicalOffsetContainment@10`, `VisibleCanonicalOffsetContainment@10`) and must downgrade the decision verdict token from `CLEAR_WINNER` / `NO_CLEAR_WINNER` to `CLEAR_PROXY_WINNER` / `NO_CLEAR_PROXY_WINNER`.
3. **LLM Judge Circularity & Shared Pretraining Bias Disclosure:**
   - Even with cross-family judges, rank-invariant 7-key packet blinding (`D05.3`), and deterministic verbatim substring checks (`exact_quote ⊆ S`), LLM judges share surface-lexical and semantic affinities with neural/lexical retrievers. Therefore, proxy `nDCG@10` measures **agreement with an automated rubric-guided proxy judge + verbatim span containment**, not independent human utility.
4. **Prompt-Order & Positional Sensitivity Constraints:**
   - Every pooled `(query, document)` pair must be evaluated under swapped rubric/option orderings (`ORDER_A` and `ORDER_B`) with `temperature = 0`. Any pair failing deterministic quote verification (`exact_quote not in S`) or order-swap consistency cannot be silently coerced to `rel = 0` or `rel = 2` to inflate a contrast.
5. **Unanswerable Safety (`FalseSupportExposure@10`) & `G5` Separation:**
   - Under `D06.4` (`G15-F06`), `AnyResult@10` on `S5` unanswerable queries is a structural retrieval property (always `1.00` for unthresholded Dense/RRF), whereas `FalseSupportExposure@10` (`rel=0` with `plausible_unsupported_lure=1`) is an annotation-dependent diagnostic. Under Route 2, lure flags are `LLMProxy-FalseSupportExposure@10` only, and **`G5` (downstream RAG generation / abstention behavior) remains strictly in `HOLD`**.

---

## 4. Action Required from Project Owner to Exit `OD-G15-05` `HOLD`

To unlock `OD-G15-05` in a future governance step, the Project Owner must select **one** of:
- **Choice `OD-G15-05-HUMAN` (`Route 1A` or `Route 1B`):** Commit the off-repo `2+1` human annotator/adjudicator roster hash (`OD-G15-02`) and (if choosing pooled grading) sign `W07_B2_METHOD_AMENDMENT_01_V0_3_1_OPTION_B_REVIEW_DRAFT_NOT_EFFECTIVE.md` (`f5560a95...`); **OR**
- **Choice `OD-G15-05-AIPROXY` (`Route 2`):** Furnish signed Thesis Supervisor confirmation (`Block SV-01` accepting reduced `LLMProxy-*` claim scope) and sign a versioned AI-proxy amendment (`G2A/G2B` / `AUTO-EVAL-01`) before authorizing any `DEV-5` or `FINAL-50` execution.
