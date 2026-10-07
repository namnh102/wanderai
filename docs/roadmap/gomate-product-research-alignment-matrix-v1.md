# GoMate Product vs. Research Alignment Matrix V1
## Cross-Mapping of Product Capabilities, Research Experiments, 14 Weekly Milestones & Evaluation Artifacts

- **Document Reference:** `docs/roadmap/gomate-product-research-alignment-matrix-v1.md`
- **Scope:** Formal Alignment between Product Engineering Roadmap and Academic Thesis Research
- **Status:** **ALIGNMENT MATRIX LOCKED**
- **Date:** October 7, 2026
- **Companion Specifications:**
  - `docs/roadmap/gomate-master-implementation-roadmap-v1.md`
  - `docs/roadmap/gomate-thesis-research-roadmap-v1.md`
  - `docs/audit/ui/task-08.2.4-global-capability-matrix.md`

---

## 1. Executive Summary & Alignment Principles

The GoMate project encompasses two intertwined but structurally distinct endeavors:
1. **The Product Engineering Effort:** Delivering a truthful, reliable, 14-module travel copilot app with 35 Product Target capabilities.
2. **The Academic Research Effort:** Conducting scientific experiments on preference-based recommendation, constraint-satisfying LLM planning, and privacy-preserving social discovery.

This matrix explicitly aligns every weekly milestone, research package, product work package, and capability ID to guarantee that neither effort distorts the other.

---

## 2. Master Alignment Matrix (Weeks 1 to 14)

| Week | Thesis Research Milestone | Research / Evaluation Packages | Product Work Packages Aligned | Product Capability IDs | Capability Tier Status | Scientific Artifact Produced |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- |
| **W01** | MVP Scoping, Personas & Metric Formalization | `DATA-01` | *Roadmap Governance* | All 90 Dimensions | `CURRENT: 36, TARGET: 35` | Formal Metric Formulas (NDCG, Recall, HitRate) |
| **W02** | POI & Review Normalization, Preference Ingestion | `DATA-02` | `WP-PROF-01` | `13.3`, `13.4` | `13.4: PRODUCT TARGET` | Normalized POI & Preference Vector Corpus |
| **W03** | Core Database Schemas, Data Contracts & Seed v1 | `DATA-03` | `WP-PROF-02`, `WP-AUTH-01` | `13.5`, `14.3`, `14.4` | `PRODUCT TARGET` | Frozen Evaluation Dataset `dataset_v1_seed42.json` |
| **W04** | Recommender Baseline Implementation | `REC-01`, `REC-02` | `WP-SEARCH-01` | `1.4` (`1.5` = Research) | `1.4: TARGET, 1.5: FUTURE` | Content-Based (`content_based.py`) & Pop Baselines |
| **W05** | Offline Recommender Evaluation & Cold-Start Split | `REC-EVAL-01` | `WP-MEDIA-01` | `3.1`, `3.10` | `3.10: PRODUCT TARGET` | Offline Ranking Benchmark & Cold-Start Tables |
| **W06** | Itinerary Planning Agent Constraint Benchmarking | `AGENT-EVAL-01` | `WP-WANDY-01` | `4.1`, `4.4`, `6.1–6.4` | `4.4: PRODUCT TARGET` | Constraint Satisfaction Evaluation Report |
| **W07** | RAG Grounding, Citations & Factuality Audit | `RAG-EVAL-01` | `WP-TRIP-01` | `4.2`, `5.4` | `5.4: PRODUCT TARGET` | Citation Precision & Hallucination Audit Report |
| **W08** | Buddy Matching Compatibility & Privacy Verification | `MATCH-EVAL-01` | `WP-BUDDY-01`, `WP-BUDDY-02` | `7.1–7.4` | `PRODUCT TARGET` | Compatibility NDCG@5 & Privacy Leak Verification |
| **W09** | Collaborative Social Travel & Safety Integration | *Social Eval* | `WP-GROUP-01`, `WP-SAFE-01`, `WP-MAP-01` | `8.1, 8.2, 12.4, 2.7` | `PRODUCT TARGET` | Group Governance & Offline Resilience Audit |
| **W10** | End-to-End Workflow Validation | `E2E-THESIS-01` | `WP-ITIN-01`, `WP-EXP-01, 02` | `9.1, 9.2, 10.1–10.4` | `PRODUCT TARGET` | Multi-User Collaboration Benchmark Log |
| **W11** | Feature Freeze & Comprehensive Re-Evaluation | `FREEZE-EVAL-01` | *Test Hardening* | All 35 Targets | `FREEZE LOCK` | Master Thesis Results Manifest & LaTeX Tables |
| **W12** | Latency Optimization & Constraint Hardening | *Optimization* | `WP-AUTH-02`, Index Tuning | `14.11` | `PRODUCT TARGET` | Latency Ablation & Index Benchmark Report |
| **W13** | Demonstration Rehearsal, Case Studies & Limits | *Case Studies* | *Demo Packaging* | All Shells | `PREVIEW READY` | 3 Qualitative Case Studies & Limitations Chapter |
| **W14** | Final Release & Scientific Defense Packaging | *Defense Release* | *Release Tag v1.0.0* | Final System | `RELEASE LOCKED` | Defense Slides, Reproducibility Package, Dissertation |

---

## 3. Product vs. Research Scope Boundary Invariant

### 3.1. Recommender Systems: Capability 1.5 vs. REC-01 / REC-EVAL-01
To preserve the integrity of the locked 90-capability product matrix, the project strictly distinguishes:

```
┌────────────────────────────────────────────────────────────────────────┐
│             PRODUCT CAPABILITY 1.5 vs. THESIS RESEARCH REC-01          │
├─────────────────────────┬──────────────────────────────────────────────┤
│ Product Dimension       │ Research Dimension                           │
├─────────────────────────┼──────────────────────────────────────────────┤
│ Capability: 1.5         │ Research Packages: REC-01, REC-EVAL-01       │
│ Label: Personalized Recs│ Label: Offline Recommender Evaluation        │
│ Classification: FUTURE  │ Classification: MANDATORY THESIS MILESTONE   │
│ Location: Flutter Home  │ Location: apps/ai-service/recommendation/    │
│ Scope: Live ML ranking  │ Scope: Offline benchmark over test personas  │
│ in client production UI │ computing NDCG@K, Recall@K, Cold-Start split │
│ Status: Deferred        │ Status: Required for Defense                 │
└─────────────────────────┴──────────────────────────────────────────────┘
```

**Governance Rule:**
Executing `REC-01` and `REC-EVAL-01` fulfills the academic requirement of evaluating personalized travel recommendation algorithms. It **does NOT** require modifying the Flutter Home screen to serve dynamic ML recommendations in the production MVP. Capability `1.5` remains legitimately classified as `FUTURE`.

---

## 4. Work Package Contribution to Academic Research Goals

This table demonstrates how each of the 23 Product Engineering Work Packages supports the academic thesis:

| Work Package ID | Core Product Deliverable | Direct Academic Research Contribution |
| :--- | :--- | :--- |
| **WP-PROF-01** | `PUT /users/me/preferences` & UI | Ingests structured traveler preference vectors required for recommendation and buddy matching algorithms. |
| **WP-PROF-02** | Privacy & Visibility controls | Implements traveler consent boundary required for the privacy evaluation chapter. |
| **WP-MEDIA-01**| Place media & CC attribution | Provides ground-truth data provenance supporting the "Data Honesty & Ethics" thesis contribution. |
| **WP-WANDY-01**| Guarded action bridge | Demonstrates human-in-the-loop agentic safety (Intent $\rightarrow$ Preview $\rightarrow$ Explicit Confirmation). |
| **WP-TRIP-01** | Itinerary reordering persistence | Enables interactive feedback loops for itinerary constraint re-evaluation. |
| **WP-SEARCH-01**| Global multi-destination search | Provides baseline keyword retrieval baseline to compare against vector RAG retrieval. |
| **WP-BUDDY-01**| Discovery & vector matching | Core scientific contribution: multi-attribute preference vector matching algorithm. |
| **WP-BUDDY-02**| Masked profile & double opt-in | Core scientific contribution: privacy-preserving dual-handshake social protocol. |
| **WP-GROUP-01**| Group space & roles | Collaborative social platform supporting multi-agent group travel experiments. |
| **WP-CHAT-01** | WebSocket chat timeline | Real-time synchronization layer for group coordination case studies. |
| **WP-ITIN-01** | Shared itinerary board & voting | Democratic consensus algorithm over collaborative travel itineraries. |
| **WP-ITIN-02** | Real-time concurrency lock | Distributed locking mechanism preventing race conditions in collaborative planning. |
| **WP-EXP-01**  | Shared expense ledger & splits | Multi-party financial ledger supporting travel settlement experiments. |
| **WP-EXP-02**  | Debt simplification matrix | Algorithmic contribution: minimum cash flow graph optimization. |
| **WP-SAFE-01** | Emergency modal & offline cache | Non-autonomous safety safeguard supporting the "Responsible Travel AI" chapter. |
| **WP-MAP-01**  | Offline basemap tile caching | Edge computing / offline resilience evaluation for travel field scenarios. |
| **WP-REMIND-01**| Local notification scheduler | Temporal constraint scheduling supporting pre-departure packing checklists. |
| **WP-AUTH-01–06**| Authentication hardening | Security hygiene framework guaranteeing reproducible, authenticated test sessions. |

---

## 5. Defense Readiness Evaluation Checkpoints

```
CHECKPOINT 1: ALGORITHMIC VALIDATION (End of Week 5)
- Offline recommender achieves target accuracy:
  • NDCG@5 $\ge 0.70$ on warm profiles.
  • Recall@5 $\ge 0.65$ on warm profiles.
  • Explicit reporting of cold-start performance degradation.

CHECKPOINT 2: AGENT GROUNDING & SAFETY (End of Week 7)
- Gemini itinerary planner achieves 100% verified POI grounding.
- Budget constraint violation rate $\le 5\%$.
- RAG citation precision $\ge 90\%$.

CHECKPOINT 3: SOCIAL PRIVACY & GROUP CONCURRENCY (End of Week 10)
- Buddy matching privacy leak count $= 0$.
- Shared itinerary voting conflict resolution verified under concurrent edits.
- Debt simplification reduces peer transactions by $\ge 40\%$ vs naive bilateral settlements.

CHECKPOINT 4: FINAL DEFENSE PACKAGING (End of Week 14)
- 100% reproducible benchmark suite running in Docker container.
- Complete dissertation results chapter with statistical significance tests ($p < 0.05$).
```

---

## 6. Conclusion & Alignment Sign-Off

This alignment matrix guarantees complete harmony between product implementation and academic research:
1. The **90-Capability Register** and **35 Product Targets** remain intact with zero classification distortion.
2. The **14 Weekly Thesis Milestones** are fully mapped to concrete engineering packages and research deliverables.
3. The **Scientific Evaluation Pipeline** (`DATA-*`, `REC-*`, `EVAL-*`) has a dedicated execution path that will deliver all empirical results required for the graduation thesis defense.
