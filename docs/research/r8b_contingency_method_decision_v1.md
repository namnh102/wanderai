# R8B Contingency & Final Method Decision V1

**Title:** R8B Contingency & Final Method Decision V1<br>
**Status:** `CLOSED_WITHOUT_EXTERNAL_REPORT`<br>
**Final Method Decision:** `METHOD_RETAINED`<br>
**Contingency Status:** `EXTERNAL_CROSS_CHECK_NOT_COMPLETED_AT_METHOD_FREEZE`<br>
**Closure Reason:** `PROJECT_OWNER_ELECTED_TO_PROCEED_WITHOUT_WAITING_FURTHER`<br>
**Artifact Version:** `R8B-CONTINGENCY-V1`<br>
**Target Repository:** `d:\Do_an\wanderai`<br>
**Base Commit SHA:** `e21f5d60c58d8ff1a63a85e14169190b8f5879ee`<br>
**Retained Preregistration:** `REC-EVAL-01-PREREG-V1`<br>
**Methodology Owner & Gatekeeper:** ChatGPT<br>
**Implementation & Evidence Agent:** Antigravity<br>

---

## 1. Purpose

`R8B` was a planned external cross-check dependency that required either completion or formal contingency resolution before primary human annotation. Specifically, an independent external perspective ("Researcher-1") was invited to challenge and review the preregistered experimental design, metric definitions, and candidate pooling strategy (`REC-EVAL-01-PREREG-V1`) prior to human calibration and primary relevance annotation.

---

## 2. Evidence Availability

* **Researcher-1 Report Received:** `NO`
* **External Cross-Check Completed:** `NO`
* **External Agreement Claimed:** `NO`
* **External Validation Claimed:** `NO`
* **External Recommendations Received:** `NONE`

No external research report, written feedback, or structured evaluation from Researcher-1 was received or committed to the repository.

---

## 3. Closure Rationale

No Researcher-1 report was received before the project owner elected to proceed without waiting further.

The project therefore closes the dependency using the preregistered contingency path before launching human calibration.

### Negative Boundary
* No endorsement or approval from Researcher-1 is claimed or implied.
* No claim is made that an external review concluded successfully.
* No independent external verification is claimed.
* No synthetic or fabricated external review comments have been created.

---

## 4. Internal Evidence State & Algorithm Definitions

Before executing this contingency closure, all internal scientific gates and preparatory milestones were audited and confirmed:

* **Internal Research Milestones (R1–R8A):** `COMPLETE`
  * **`REC-A0`:** Unweighted dot-product ranking under binary 7D preference representation.
  * **`REC-A1`:** Destination-filtered normalized cosine ranking under the same binary 7D representation.
  * **`A0/A1` Equivalence:** Rank-equivalent under the frozen representation and represented by the single scientific comparator `shared_a0_a1_baseline`.
  * **`REC-A2`:** Deterministic Relevance-Preserving Multi-Interest Diversity Reranker. (`REC-A2` does not perform geographic reranking, time/context reranking, semantic embeddings, collaborative filtering, or learned ranking.)
  * **Evaluation Pool Builder (`W5-PREP-01`):** Candidate pool and deterministic control sampling verified.
  * **Human Relevance Package (`W5-PREP-02`):** Three-judge blinded human relevance protocol, rubric, and calibration split generated.
  * **Metric Runner (`W5-PREP-03`):** Evaluation runner with destination-stratified paired bootstrap verified.
* **W5 Methodology Preregistration (`REC-EVAL-01-PREREG-V1`):** `CLOSED`
* **W5 Duplicate Equivalence Evidence Gate (`W5-GATE-DUP`):** `CLOSED` (`CLOSED_NO_PRIMARY_EVAL_IMPACT`)
* **Human Relevance Labels Collected:** `0`
* **Human Ground Truth (`HUMAN-GT`):** `NO`
* **Calibration Execution:** `NOT_STARTED`
* **Real Model Comparison:** `NO`
* **Scientific Winner:** `UNKNOWN`

---

## 5. Final Methodology Decision: METHOD_RETAINED

Because no external findings or objections were received to motivate altering the preregistered design, the formal decision is:

$$\text{Final Decision} = \mathbf{METHOD\_RETAINED}$$

No modifications are made to:
1. Recommender systems under evaluation (`shared_a0_a1_baseline` vs `rec-a2`).
2. Scenario universe (30 primary scenarios across Hanoi = 9, Da Nang = 11, Ha Long = 10: 15 U1 single-interest, 15 U2 multi-interest; 6 THIN low-inventory diagnostic scenarios).
3. Candidate judgment pool (474 primary candidate records across 255 unique places).
4. Human annotation protocol (three-judge blinded human relevance protocol with 3 independent human judges, ordinal scale $\{0, 1, 2\}$, non-ordinal missing code `NA`).
5. Metric hierarchy and endpoint roles (`NDCG@10` as `PRIMARY_CONFIRMATORY`; `Precision@10` and `Pooled Recall@10` as `SECONDARY`; `HitRate@10` as `DIAGNOSTIC_SECONDARY`; `Category-ILD@10` as `SECONDARY_SUPPORTING_STRUCTURAL_PROXY`; `CatalogCoverage@10` as `SECONDARY_SUPPORTING`; `I1Exposure@10` as `DIAGNOSTIC_ONLY`).
6. Statistical inference ($B=10000$ paired, destination-stratified bootstrap replicates, seed `20261013`).
7. Formal verdict rules (`A2_RELEVANCE_SUPERIOR`, `BASELINE_PREFERRED`, `A2_DIVERSITY_TRADEOFF`, `INCONCLUSIVE`).
8. Duplicate policy (`CLOSED_NO_PRIMARY_EVAL_IMPACT`).
9. Algorithm implementations (`REC-A0`, `REC-A1`, `REC-A2`).

---

## 6. Locked Retained Experimental Protocol

The retained experimental contract is locked exactly as preregistered in `REC-EVAL-01-PREREG-V1`:

| Protocol Dimension | Specification | Role / Contract |
|---|---|---|
| **Systems Under Test** | `shared_a0_a1_baseline`, `rec-a2` | Frozen algorithms; A0/A1 represented by single shared baseline |
| **Primary Scenarios** | 30 scenarios (`ha-noi`: 9, `da-nang`: 11, `ha-long`: 10) | Primary evaluation scenario set |
| **Subgroups** | 15 single-interest (U1), 15 multi-interest (U2) | `EXPLORATORY_SUBGROUP` analysis |
| **THIN Scenarios** | 6 THIN low-inventory diagnostic scenarios | `DIAGNOSTIC_ONLY`; excluded from primary relevance superiority / winner determination |
| **Primary Endpoint** | `NDCG@10` ($\text{gain} = 2^{\text{rel}} - 1$) | `PRIMARY_CONFIRMATORY` |
| **Secondary Relevance** | `Precision@10`, `Pooled Recall@10` | `SECONDARY` |
| **Diagnostic Hit Rate** | `HitRate@10` | `DIAGNOSTIC_SECONDARY` |
| **Supporting Diversity** | `Category-ILD@10` | `SECONDARY_SUPPORTING_STRUCTURAL_PROXY` (`structural_category_diversity_proxy`) |
| **Supporting Coverage** | `CatalogCoverage@10` | `SECONDARY_SUPPORTING` (`destination_macro_mean`) |
| **Diagnostic Exposure** | `I1Exposure@10` (217 zero-vector POIs with all-zero canonical 7D interest vectors) | `DIAGNOSTIC_ONLY` |
| **Human Protocol** | Three-judge blinded human relevance protocol (3 independent human judges) | Blinded to algorithm/system identity, recommendation rank, model score, system strategy, and control status; adjudication separately blind to model identity/rank/score/strategy |
| **Label Space** | $\{0, 1, 2\}$ ordinal; `NA` non-ordinal | Strict data typing; booleans/floats rejected |
| **Statistical Test** | Paired, scenario-level, destination-stratified bootstrap | $B=10000$ replicates, seed `20261013` |
| **Candidate Universe** | 474 records in primary pool | 255 unique places from 622-item Freeze V2 (405 I0, 217 I1) |
| **Verdict Rules** | `A2_RELEVANCE_SUPERIOR`, `BASELINE_PREFERRED`, `A2_DIVERSITY_TRADEOFF`, `INCONCLUSIVE` | Formal gatekeeping rules |

---

## 7. Scientific Interpretation

The decision `METHOD_RETAINED` carries specific scientific boundaries:

* **It does NOT imply that REC-A2 is superior.** The relative performance of the models remains unknown until human ground truth is collected and formal inference is computed.
* **It does NOT imply external consensus.** External researchers have not reviewed or endorsed this methodology.
* **It does NOT claim universal optimality.** The protocol is an offline laboratory experiment scoped to the GoMate 622-item Freeze V2 catalog.
* **It solely denotes:** No external evidence was available to justify changing the already-preregistered protocol before human data collection.

---

## 8. Downstream Clearance

With `W5-GATE-DUP` closed (`CLOSED_NO_PRIMARY_EVAL_IMPACT`) and `R8B` closed by contingency (`METHOD_RETAINED`), all preregistered dependencies prior to calibration are resolved:

1. **W5 Calibration Operation:** `CLEARED_TO_PROCEED`.
2. **Primary Annotation:** Unblocked pending successful calibration qualification.
3. **Scientific Winner:** Remains `UNKNOWN`.
