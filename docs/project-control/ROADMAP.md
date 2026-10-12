# ROADMAP (W3 → W14)

Source: `docs/roadmap/gomate-thesis-research-roadmap-v1.md` and `gomate-master-implementation-roadmap-v1.md`.
Calendar dates are **not recorded in the repository**; only the week numbering and gates are. The owner must supply dates.

| Week | Focus | Packages | Gate |
|---|---|---|---|
| W3 | Core architecture, privacy controls, dataset freeze, integration baseline | W3-00 to W3-06 and `DATA-03` (engineering/integration gate **CLOSED**). `WP-AUTH-01` remains a product target / later work; `WP-PROF-02` remains a product target / before Buddy work. Their non-completion does not reopen W3. | integration baseline (CLOSED) |
| W4 | Recommendation baseline | `REC-01`, `REC-02` | REC baseline |
| W5 | Offline recommender evaluation, cold start | `REC-EVAL-01` | REC-EVAL |
| W6 | Itinerary agent constraint benchmark | `AGENT-EVAL-01`, `WP-WANDY-01` | AGENT-EVAL |
| W7 | RAG grounding, citations, factuality | `RAG-EVAL-01` | RAG-EVAL |
| W8 | Buddy matching + privacy verification | `MATCH-EVAL-01`, `WP-BUDDY-01/02` | MATCH-EVAL |
| W9 | Social collaboration, safety, map | `WP-GROUP-01`, `WP-SAFE-01`, `WP-MAP-01` | - |
| W10 | End-to-end workflow validation | `E2E-THESIS-01`, `WP-ITIN-01`, `WP-EXP-01` | E2E-THESIS |
| W11 | **Feature freeze** + comprehensive evaluation | `FREEZE-EVAL-01` | FREEZE-EVAL |
| W12 | Performance optimization, constraint hardening | - | GATE-OPT |
| W13 | Demo rehearsal, case studies, limitations | - | DEMO-READY |
| W14 | **Final submission** (manifest, code, demo, report) | - | THESIS-DEF |

Main deadlines: **W11 feature freeze**, **W14 final submission**.
A live recommendation flow exists in the app (NestJS -> FastAPI -> REC-A) with `rec-a0` / `rec-a1` as baseline implementations. It must NOT be described as scientifically validated personalization: W4 / W5 remain the research methodology and scientific evaluation milestones (Triple Boundary rule).
