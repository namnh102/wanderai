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

The `R8B` milestone was conceived as an optional external research cross-check and challenge against the internal recommender evaluation methodology (`REC-EVAL-01-PREREG-V1`) prior to launching human calibration and primary relevance annotation. Specifically, an external perspective ("Researcher-1") was invited to review the experimental design, metric definitions, and candidate pooling strategy.

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

To maintain scientific momentum and proceed toward human calibration without unbounded blocking on external correspondence, the project formally closes the external cross-check dependency using this preregistered contingency decision.

### Negative Boundary
* No endorsement or approval from Researcher-1 is claimed or implied.
* No claim is made that an external review concluded successfully.
* No independent external verification was conducted.
* No synthetic or fabricated external review comments have been created.

---

## 4. Internal Evidence State

Before executing this contingency closure, all internal scientific gates and preparatory milestones were audited and confirmed:

* **Internal Research Milestones (R1–R8A):** `COMPLETE`
  * Content baseline (`REC-A0`), hybrid taxonomy (`REC-A1`), and contextual reranker (`REC-A2`) implementations frozen.
  * Evaluation pool builder and deterministic control sampling verified (`W5-PREP-01`).
  * Triple-blind annotation package, rubric, and calibration split generated (`W5-PREP-02`).
  * Metric runner with destination-stratified paired bootstrap verified (`W5-PREP-03`).
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
2. Scenario universe (30 primary scenarios: 15 U1 single-interest, 15 U2 multi-interest; 6 THIN diagnostic).
3. Candidate judgment pool (474 primary candidate records across 255 unique places).
4. Human annotation protocol (3 independent judges, ordinal scale $\{0, 1, 2\}$, non-ordinal missing code `NA`).
5. Metric hierarchy and formulas ($NDCG@10$ primary; Precision@10, Pooled Recall@10, HitRate@10 secondary; Category-ILD@10 supporting structural proxy; CatalogCoverage@10 supporting).
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
| **Primary Scenarios** | 30 scenarios (10 Hanoi, 10 Da Nang, 10 Ha Long) | Confirmatory evaluation set |
| **Subgroups** | 15 single-interest (U1), 15 multi-interest (U2) | Exploratory subgroup analysis |
| **Diagnostic Scenarios** | 6 THIN history scenarios | Diagnostic only; strictly excluded from winner verdict |
| **Primary Endpoint** | $NDCG@10$ ($\text{gain} = 2^{\text{rel}} - 1$) | Primary confirmatory endpoint |
| **Secondary Relevance** | Precision@10, Pooled Recall@10, HitRate@10 | Secondary confirmatory endpoints |
| **Supporting Diversity** | Category-ILD@10 | Structural category-diversity proxy only |
| **Supporting Coverage** | CatalogCoverage@10 | Equal-destination macro mean ratio |
| **Diagnostic Exposure** | I1Exposure@10 | Unindexed item diagnostic only |
| **Human Judges** | 3 independent, fully blinded human annotators | Triple-blind adjudication contract |
| **Label Space** | $\{0, 1, 2\}$ ordinal; `NA` non-ordinal | Strict data typing; booleans/floats rejected |
| **Statistical Test** | Paired, destination-stratified bootstrap | $B=10000$ replicates, seed `20261013` |
| **Candidate Universe** | 474 records in primary pool | 255 unique places from 622-item Freeze V2 |
| **Verdict Rules** | 4 preregistered mutually exclusive outcomes | Formal gatekeeping rules |

---

## 7. Scientific Interpretation

The decision `METHOD_RETAINED` carries specific scientific boundaries:

* **It does NOT imply that REC-A2 is superior.** The relative performance of the models remains unknown until human ground truth is collected and formal inference is computed.
* **It does NOT imply external consensus.** External researchers have not reviewed or endorsed this methodology.
* **It does NOT claim universal optimality.** The protocol is an offline laboratory experiment scoped to the GoMate 622-item Freeze V2 catalog.
* **It solely denotes:** In the absence of external challenge evidence, the rigorously preregistered, internally audited methodology (`REC-EVAL-01-PREREG-V1`) is retained in full without ad-hoc alterations.

---

## 8. Downstream Clearance

With `W5-GATE-DUP` closed (`CLOSED_NO_PRIMARY_EVAL_IMPACT`) and `R8B` closed by contingency (`METHOD_RETAINED`), all preregistered external and preparatory dependencies are cleared:

1. **W5 Calibration Operation:** `CLEARED_TO_PROCEED`.
2. **Primary Annotation:** Unblocked pending successful calibration qualification.
3. **Scientific Winner:** Remains `UNKNOWN`.
