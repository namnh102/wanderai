# CURRENT STATE (W3 closed; pre-A8 project-control sync)

_Docs-only sync. Historical W3-00 integration evidence is preserved in `EVIDENCE.md`._

## Engineering baseline
- **W3: FINAL PASS / CLOSED.**
- **Audited engineering baseline before this docs-only sync:** `develop` = `5b3763846a248c8b11928980b87cd191725a5054`.
  This docs-only sync creates a newer Git SHA **without changing runtime behavior**; the SHA above remains the audited engineering/runtime baseline.
- `origin/main` = `5f6ae8ca6ede40d40114be5617f53a4a0c0b9fce`. Local `main` may be stale and is not used.
- **W3-06 (W3 Exit Gate): PASS.** PR #12 merged to `develop`.
- **Post-merge CI (historical): run `38257917425`**, head `5b3763846a248c8b11928980b87cd191725a5054`.
  Jobs: backend PASS, ai-service PASS, mobile PASS, data-contract PASS.
- Exit gate documentation: `docs/w3/w3-06-w3-exit-gate.md` and `docs/w3/evidence/`.

## Verified counts at the audited baseline
| Area | State |
|---|---|
| Backend | 13 suites, 153 / 153 e2e tests PASS |
| Mobile | 215 PASS, 1 SKIP, 0 FAIL |
| Android debug APK | PASS |
| Places in DB | 882 total, 759 verified canonical |
| REC-A-CORE-V2 | 622 (Ha Noi 145, Da Nang 289, Ha Long 188) |
| Secondary | 137; secondary -> REC-A leakage = 0 |
| Map verified discovery | Ha Noi 145, Da Nang 293, Ha Long 188 |

## Recommender status
- Official models: `rec-a0` and `rec-a1` (baseline implementations; served NestJS -> FastAPI -> REC-A).
- A0 and A1 use different formulas but currently produce one effective ranking under the existing POI representation.
- A2 is a research candidate only. It is NOT implemented and NOT the selected final model.
- CF remains conditional / external only.
- N300 = ENGINEERING_ONLY. No scientific human ground truth exists yet.
- A live baseline feature must not be described as scientifically validated personalization.

## Research status (external workflow)
External research workflow currently records: R1 PASS, R2 CONDITIONAL PASS, R3 PASS.
Formal repo-native research gate records are still pending.

## Accepted deferred items
- `REAL_GPS_EMULATOR` = NOT_VERIFIED.
- RAG live-DB known test: DEFERRED / PRE-EXISTING.
- WP-AUTH-01 and WP-PROF-02 remain product targets / later work (not delivered; they do not reopen W3).

## Legacy audit status
- A0 to A6: CLOSED. A7: CLOSED - PASS WITH QUALIFICATIONS.
- No old engineering component has been reopened.

## Next gate
Pre-A8 project-control sync (this task, awaiting audit) -> A8 (not started). R4: not started.
