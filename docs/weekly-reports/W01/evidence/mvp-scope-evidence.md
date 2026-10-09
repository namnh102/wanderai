# MVP & Geographic Scope Evidence — W1

> Audit date: 2026-10-05. Method: `git grep -i "mvp|city scope|pilot|phạm vi"` at commit `2d15a64` and at `HEAD`, plus reading ADR-001..ADR-005.

## 1. MVP lock in W1
| Check | Result |
|---|---|
| Decision log / ADR that locks MVP in 27/09–03/10 | **Not found.** ADRs in W1: ADR-001 (PostgreSQL), ADR-002 (real data), ADR-003 (trip context), ADR-005 (map provider, 2026-10-02). None defines MVP scope. |
| Document with the words "MVP scope" | None. "MVP" appears only incidentally (`docs/ai/ai-chat.md` "MVP slice"; ADR-005 "MVP/thesis scope"; `auth-flow.md`). |
| Issue / milestone | None (see §3). |
| Proposal alignment | Proposal requires MVP lock in W1. **STATUS: NOT VERIFIED (no formal lock found).** |

Partial, indirect evidence (not a lock): `AGENTS.md`/`CONTRIBUTING.md` (`9b36f9d`, 2026-09-29) fix the technology stack (Flutter, NestJS, FastAPI, PostgreSQL+PostGIS+pgvector). `docs/project-status.md` (from `8592aea`) lists milestones. The code produced in the window covers auth, AI chat, trip CRUD, AI planner (commit `9a0d2f0`), RAG/MostPop baseline (`960f90e`) and map (`8abee0b`); **no travel-buddy matching code exists in W1**; the Flutter Companion screen was a placeholder (`docs/daily-reports/2026-10-01.md`, "Remaining Limitations").

Mapping to the three proposal research capabilities at end of W1:
| Capability | Evidence at `2d15a64` | Level |
|---|---|---|
| AI itinerary planning | `9a0d2f0`, `docs/ai/ai-planner.md`; live run failed on 2026-10-03 (TASK 07.1: retired Gemini model, token limit) | PARTIAL (works with mocks, failed live) |
| Recommendation | `960f90e`, MostPop baseline on external ViHoRec (benchmark file in repo) | PARTIAL (baseline only) |
| Travel-buddy matching + consent | none | NOT STARTED |

## 2. Geographic scope in W1
| Check | Result |
|---|---|
| Decision "Hà Nội + Hạ Long" in W1 | **Not found.** Zero mentions of Hạ Long in any W1 decision, ADR, manifest or pipeline config. Hạ Long appears only in synthetic seed data and as 1 of 10 Wikivoyage RAG pages (14 chunks). |
| Decision "Hà Nội + Hạ Long" at `HEAD` (2026-10-05) | **Not found either** (`git grep` over `docs`, `data`, `AGENTS.md`, `README.md` finds no scope decision). |
| What the repo shows in W1 | Overpass pilot boxes for **5 cities**: Đà Nẵng, Hà Nội, Hội An, Nha Trang, Huế (`data/pipelines/osm/config.py`, commit `ffe7b97`, 2026-10-01). Curated dataset: Đà Nẵng 55, Hà Nội 50, others 1 each. |
| Conflict with proposal | Proposal §4 limits scope to 1–2 cities; the 5-box pilot exceeds this, although 105/108 records fall in 2 cities (Đà Nẵng, Hà Nội). |

**Conclusion:** City scope as a *formal decision* — NOT VERIFIED. The W1 report records only the observed pilot extraction (5 boxes; effectively Đà Nẵng + Hà Nội). "Hà Nội + Hạ Long" is treated as a post-W1 intended direction supplied by the task description; no repository evidence of when it was decided → see "Post-W1 Scope Clarification" in the weekly report.

## 3. Issues / PRs / milestones
`gh issue list --state all` and `gh pr list --state all` on `namnh102/wanderai` (authenticated as `namnh102`) returned **empty output, exit code 0**. `.github/` does not exist at `2d15a64`. `git tag` is empty. **No Issue/PR/Milestone evidence exists.**
