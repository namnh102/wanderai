# GoMate Thesis Research Roadmap V1
## 14-Week Academic Milestones, Experimental Methodology & Scientific Evaluation Pipeline

- **Document Reference:** `docs/roadmap/gomate-thesis-research-roadmap-v1.md`
- **Scope:** Academic Research, Experimental Design, Dataset Governance & Evaluation Pipeline
- **Status:** **THESIS RESEARCH ROADMAP LOCKED**
- **Date:** October 7, 2026
- **Companion Specifications:**
  - `docs/roadmap/gomate-master-implementation-roadmap-v1.md`
  - `docs/roadmap/gomate-product-research-alignment-matrix-v1.md`
  - `docs/roadmap/gomate-implementation-dependency-dag-v1.md`

---

## 1. Executive Summary & Research Mandate

While the **Product Engineering Roadmap** (`TASK 08.3`) schedules production software delivery across 23 vertical slices, this **Thesis Research Roadmap** governs the academic contributions, experimental methodologies, algorithmic benchmarks, and empirical evaluations required for a successful scientific defense.

### 1.1. Core Research Contributions
1. **Grounded Multi-Modal Travel Copilot:** RAG and LLM agent orchestration with hard constraint satisfaction (budget, opening hours, geographic routing, verified OSM provenance).
2. **Preference-Driven Algorithmic Recommendation:** Content-based and hybrid vector matching over structured traveler preferences, evaluated against standardized offline ranking metrics and cold-start splits.
3. **Privacy-Preserving Social Discovery:** Mathematical travel compatibility scoring with double opt-in mutual consent and formal privacy guarantees (zero location radar, zero unverified presence).

### 1.2. The Triple Boundary Invariant
To prevent scope distortion, GoMate strictly separates three distinct software/research artifacts:

$$\text{PRODUCT CAPABILITY} \quad \neq \quad \text{RESEARCH EXPERIMENT} \quad \neq \quad \text{EVALUATION ARTIFACT}$$

- **Product Capability:** Production-grade software running inside the mobile app or backend service (e.g. `WP-PROF-01`, `WP-WANDY-01`).
- **Research Experiment:** Algorithmic pipelines, offline ranking scripts, and ablation models running in Python / Jupyter notebooks or CLI harnesses (e.g. `REC-01`, `REC-02`).
  - *Critical Example:* Conducting offline content-based ranking experiments (`REC-01`) is a **mandatory thesis requirement**, while Capability `1.5 Personalized Recommendations` in the mobile app strictly remains **`FUTURE`** for the product MVP.
- **Evaluation Artifact:** Standardized test splits, ground-truth benchmark datasets, metric evaluation reports, and reproducibility packages (e.g. `REC-EVAL-01`, `AGENT-EVAL-01`).

---

## 2. Research & Evaluation Track Work Packages

```
┌────────────────────────────────────────────────────────────────────────┐
│                   THESIS RESEARCH & EVALUATION PACKAGES                │
├───────────────┬────────────────────────────────────────────────────────┤
│ Package ID    │ Research Focus & Scientific Deliverable                │
├───────────────┼────────────────────────────────────────────────────────┤
│ DATA-01       │ Persona archetypes, data source contracts & metrics    │
│ DATA-02       │ POI, review, and preference normalization pipelines   │
│ DATA-03       │ Synthetic & public preference dataset generation       │
│ REC-01        │ Content-based recommender baseline (Cosine/TF-IDF)     │
│ REC-02        │ Collaborative filtering baseline (Conditional on data) │
│ REC-EVAL-01   │ Offline recommender evaluation & cold-start analysis   │
│ AGENT-EVAL-01 │ Itinerary planning constraint & grounding evaluation   │
│ RAG-EVAL-01   │ RAG retrieval hit rate, citation & factuality audit    │
│ MATCH-EVAL-01 │ Buddy compatibility ranking & privacy safety audit     │
│ E2E-THESIS-01 │ End-to-end research workflow integration validation    │
│ FREEZE-EVAL-01│ Code/feature freeze & final dissertation evaluation    │
└───────────────┴────────────────────────────────────────────────────────┘
```

### Detailed Package Specifications

#### DATA-01: Personas, Sources & Metric Contract Definition
- **Objective:** Establish the scientific evaluation framework: define 8 standardized traveler personas (e.g., Solo Backpacker, Cultural Explorer, Family Leisure, Budget Foodie), formalize OSM/Wikivoyage data schema contracts, and define mathematical formulations for evaluation metrics.
- **Deliverables:** `recommendation/benchmarks/personas.json`, mathematical definitions of NDCG@K, Recall@K, Precision@K, HitRate@K, Coverage, Diversity, and Constraint Violation Rate.

#### DATA-02: POI, Review & Preference Normalization
- **Objective:** Ingest and normalize verified OpenStreetMap POIs, clean review corpora, extract aspect tags (food, culture, scenery, price), and normalize preference vector dimensions (budget range, pace, travel style, interests).
- **Deliverables:** Normalized PostGIS place dataset and feature vectors in `apps/ai-service/recommendation/data/`.

#### DATA-03: Synthetic / Public Preference Dataset Generation
- **Objective:** Generate a reproducible, versioned preference dataset with explicit seeds, provenance metadata, and demographic distributions to benchmark recommendation algorithms when real user-item interaction matrices are sparse.
- **Deliverables:** `dataset_v1_seed42.json` with train/validation/test splits (80/10/10) and cold-start partition.

#### REC-01: Content-Based Recommender Baseline
- **Objective:** Implement a deterministic Content-Based Filtering (CBF) engine computing cosine similarity between normalized traveler preference vectors and POI feature vectors.
- **Deliverables:** `apps/ai-service/recommendation/baselines/content_based.py` with feature weighting (travelStyle: 0.35, interests: 0.35, budget: 0.20, pace: 0.10).

#### REC-02: Collaborative Filtering Baseline (Data-Conditional)
- **Objective:** Implement a baseline Matrix Factorization / Item-KNN model *strictly if* a licensed public interaction dataset (e.g. Travelogue / TripAdvisor dump) is integrated; otherwise evaluate Most-Popular (`most_pop.py`) as the non-personalized baseline.
- **Deliverables:** Baseline benchmark comparator script.

#### REC-EVAL-01: Offline Recommender Evaluation & Cold-Start Analysis
- **Objective:** Execute exhaustive offline evaluation over top-$K$ recommendations ($K \in \{3, 5, 10\}$):
  - **Ranking Accuracy:** NDCG@K, Recall@K, Precision@K, HitRate@K.
  - **Catalog Properties:** Catalog Coverage (Gini index), Intra-List Diversity (cosine dissimilarity).
  - **Cold-Start Analysis:** Explicit performance breakdown on zero-history traveler profiles.
- **Deliverables:** Automated benchmarking suite `recommendation/evaluator.py` generating LaTeX result tables.

#### AGENT-EVAL-01: Itinerary Agent Constraint & Grounding Evaluation
- **Objective:** Empirically evaluate the Gemini itinerary planning agent across 100 test prompts:
  - **Constraint Satisfaction:** Total budget compliance ($|\text{Cost} - \text{Budget}| \le \text{Threshold}$), opening hours compliance, time-slot overlap conflicts.
  - **Grounding Integrity:** 100% of generated POIs must map to verified PostGIS IDs (zero fabricated places).
  - **Performance:** End-to-end generation latency and prompt token efficiency.
- **Deliverables:** `apps/ai-service/tests/test_planner_evaluation.py` and benchmark report.

#### RAG-EVAL-01: RAG Retrieval, Citation Precision & Factuality Audit
- **Objective:** Benchmark Wandy AI copilot retrieval performance:
  - Retrieval Recall@K and Hit Rate over pgvector document chunks.
  - Citation Precision (percentage of citations directly supporting generated claims).
  - Factuality Error Rate (rate of unsupported or hallucinatory claims).
- **Deliverables:** Automated RAG test harness evaluating 50 standardized travel advisory queries.

#### MATCH-EVAL-01: Buddy Compatibility & Privacy Safety Evaluation
- **Objective:** Evaluate the travel buddy matching algorithm:
  - Compatibility ranking NDCG@5 and Precision@5 against synthetic persona compatibility matrix.
  - Privacy Safety Invariant: 0 leaks of masked phone numbers or un-shared private attributes across 1,000 simulated requests.
  - Consent Handshake Invariant: 0 state transitions to `MATCHED` without explicit dual opt-in.
- **Deliverables:** `apps/backend/test/buddy-privacy-eval.spec.ts`.

#### E2E-THESIS-01: End-to-End Research Workflow Integration
- **Objective:** Connect all research components into a unified demonstration workflow:
  $$\text{Discover} \longrightarrow \text{Preference Ingestion} \longrightarrow \text{Itinerary Planning} \longrightarrow \text{Buddy Matching} \longrightarrow \text{Group Space}$$
- **Deliverables:** End-to-end integration test suite and demo walkthrough script.

#### FREEZE-EVAL-01: Code Freeze & Final Dissertation Artifact Generation
- **Objective:** Freeze all codebase commits, run final automated evaluation suites, generate final high-resolution figures, KaTeX metric tables, and the thesis appendix artifact package.
- **Deliverables:** `thesis_results_manifest.json`, reproducible dockerized benchmark container.

---

## 3. The 14 Weekly Thesis Milestones

```
┌────────────────────────────────────────────────────────────────────────┐
│                   THE 14 WEEKLY THESIS MILESTONE CALENDAR              │
├──────┬───────────────────────────────────────────────────┬─────────────┤
│ Week │ Research & Engineering Focus                      │ Key Gate    │
├──────┼───────────────────────────────────────────────────┼─────────────┤
│ W01  │ MVP Scoping, Personas, Data Contracts & Metrics   │ DATA-01     │
│ W02  │ POI & Review Normalization, Preference Ingestion  │ DATA-02     │
│ W03  │ Core Database Schemas, Data Contracts & Seed v1   │ DATA-03     │
│ W04  │ Recommender Baseline Implementation (CBF & Pop)   │ REC-01      │
│ W05  │ Offline Recommender Evaluation & Cold-Start Split │ REC-EVAL-01 │
│ W06  │ Itinerary Planning Agent Constraint Benchmarking  │ AGENT-EVAL  │
│ W07  │ RAG Retrieval Hit Rate, Citations & Factuality    │ RAG-EVAL-01 │
│ W08  │ Buddy Matching Compatibility & Privacy Audit      │ MATCH-EVAL  │
│ W09  │ Collaborative Social Travel & Safety Integration  │ WP-GROUP-01 │
│ W10  │ End-to-End Flow: Discover $\rightarrow$ Plan $\rightarrow$ Group     │ E2E-THESIS  │
│ W11  │ Feature Freeze & Comprehensive Re-Evaluation     │ FREEZE-EVAL │
│ W12  │ Latency Optimization, UX Polish & Constraint Fixes│ GATE-OPT    │
│ W13  │ Demonstration Rehearsal, Case Studies & Limits    │ DEMO-READY  │
│ W14  │ Final Submission: Manifest, Code, Demo & Report   │ THESIS-DEF  │
└──────┴───────────────────────────────────────────────────┴─────────────┘
```

### Detailed Week-by-Week Roadmap

#### Week 1: Research Scoping, Personas & Metric Formalization (`DATA-01`)
- **Research Deliverables:** Formal definition of 8 traveler personas, literature review baseline selection, KaTeX formulations for NDCG, Recall, Precision, and Constraint Satisfaction.
- **Engineering Coordination:** Repository audit lock, Global Design Review lock (`TASK 08.2.4-R1`), Implementation Roadmap lock (`TASK 08.3`).

#### Week 2: Data Engineering & Preference Vector Schema (`DATA-02`, `WP-PROF-01`)
- **Research Deliverables:** Ingested and cleansed OSM POIs, categorized aspect review corpus, preference normalization script.
- **Engineering Deliverables:** `WP-PROF-01` (Travel Preference Persistence `PUT /users/me/preferences` & Flutter settings editor).

#### Week 3: Core Architecture, Privacy Controls & Dataset Freeze (`DATA-03`, `WP-PROF-02`)
- **Research Deliverables:** Frozen synthetic preference evaluation dataset `dataset_v1_seed42.json` with train/test splits.
- **Engineering Deliverables:** `WP-PROF-02` (Privacy & Discoverability controls), `WP-AUTH-01` (Secure token storage & silent refresh queue).

#### Week 4: Recommendation Algorithm Baseline Implementation (`REC-01`, `REC-02`)
- **Research Deliverables:** Implemented Content-Based Filtering algorithm (`content_based.py`) and non-personalized Most-Popular baseline (`most_pop.py`).
- **Engineering Coordination:** `WP-SEARCH-01` (Global cross-destination search query).

#### Week 5: Offline Recommender Evaluation & Cold-Start Analysis (`REC-EVAL-01`)
- **Research Deliverables:** Benchmark execution generating NDCG@K, Recall@K, HitRate@K, Coverage, and Diversity tables across warm vs cold-start splits.
- **Engineering Deliverables:** `WP-MEDIA-01` (Place media ingestion & CC license provenance).

#### Week 6: Itinerary Agent Constraint Satisfaction Benchmarking (`AGENT-EVAL-01`, `WP-WANDY-01`)
- **Research Deliverables:** Evaluation of Gemini itinerary planner over 100 benchmark trips: budget violation rate, schedule conflict rate, valid POI grounding rate ($= 100\%$).
- **Engineering Deliverables:** `WP-WANDY-01` (Guarded Action Bridge: Intent $\rightarrow$ Preview $\rightarrow$ Explicit Confirmation).

#### Week 7: RAG Grounding, Citations & Factuality Audit (`RAG-EVAL-01`)
- **Research Deliverables:** Benchmark Wandy RAG: citation precision rate, source chunk recall, factuality audit over 50 travel queries.
- **Engineering Deliverables:** `WP-TRIP-01` (Drag-and-drop itinerary reordering persistence).

#### Week 8: Buddy Matching Compatibility & Privacy Verification (`MATCH-EVAL-01`, `WP-BUDDY-01`, `WP-BUDDY-02`)
- **Research Deliverables:** Compatibility ranking evaluation (NDCG@5, Precision@5) + formal privacy audit proving 0 phone leaks.
- **Engineering Deliverables:** `WP-BUDDY-01` (Discovery grid) and `WP-BUDDY-02` (Masked profile & double opt-in handshake).

#### Week 9: Social Collaborative Travel Integration (`WP-GROUP-01`, `WP-SAFE-01`, `WP-MAP-01`)
- **Research Deliverables:** Evaluation of group coordination workflows and privacy boundaries.
- **Engineering Deliverables:** `WP-GROUP-01` (Group space & roles), `WP-SAFE-01` (Emergency confirmation modal & offline cache), `WP-MAP-01` (Offline tile caching).

#### Week 10: End-to-End Workflow Validation (`E2E-THESIS-01`, `WP-ITIN-01`, `WP-EXP-01`)
- **Research Deliverables:** Empirical run-through of the complete thesis pipeline: Discover $\rightarrow$ Preference Ingestion $\rightarrow$ Recommendation $\rightarrow$ AI Planning $\rightarrow$ Buddy Match $\rightarrow$ Group Itinerary $\rightarrow$ Split Expense.
- **Engineering Deliverables:** `WP-ITIN-01` (Shared itinerary voting), `WP-EXP-01` & `WP-EXP-02` (Shared expense ledger & debt simplification).

#### Week 11: Feature Freeze & Comprehensive Evaluation Benchmark (`FREEZE-EVAL-01`)
- **Research Deliverables:** **FEATURE FREEZE.** Final execution of all evaluation suites across Recommendation, Planning, RAG, and Matching. Generation of master thesis results tables and statistical significance tests.
- **Engineering Deliverables:** Zero new features; test suite consolidation.

#### Week 12: Performance Optimization & Constraint Hardening
- **Research Deliverables:** Latency ablation analysis, caching efficiency report, constraint tightening for edge cases.
- **Engineering Deliverables:** `WP-AUTH-02` (Rate limiting), query indexing optimization, bug fixes.

#### Week 13: Demonstration Rehearsal, Case Studies & Thesis Limitations
- **Research Deliverables:** Documented case studies (3 distinct traveler journeys), discussion of academic limitations (synthetic data constraints, cold-start boundaries, API rate limits).
- **Engineering Deliverables:** Live demo rehearsal on physical device and web preview.

#### Week 14: Final Release & Scientific Defense Packaging
- **Research Deliverables:** Final dataset manifest, reproducible code repository, demonstration video recording, evaluation metrics appendix, and dissertation sign-off.
- **Engineering Deliverables:** Final release tag `v1.0.0-thesis-release`.

---

## 4. Priority Override Rule for Academic Milestones

In the event of time pressure or resource constraints:
$$\mathbf{THESIS\ RESEARCH\ PATH\ >\ SECONDARY\ PRODUCT\ POLISH}$$

1. If recommender evaluation (`REC-EVAL-01`) or agent evaluation (`AGENT-EVAL-01`) is delayed, secondary product features (e.g., Apple Social OAuth `WP-AUTH-05`, packing checklist reminders `WP-REMIND-01`) must be deprioritized.
2. The core thesis narrative—*provenance-grounded AI planning, preference vector recommendation, and privacy-preserving buddy matching*—must have empirical evaluation data before Week 11.
