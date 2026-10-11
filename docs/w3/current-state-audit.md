# W3 Current-State Audit (as of `develop` `ab55856`)

Method: repository evidence only (code, tests, run output). Claims not backed by a run are marked **unverified**.

## 1. Integration result
Merge chain #2 → #3 → #4 → #5 is complete locally. Three verification-only fixes were needed because the legacy Freeze V1/V2 manifests contain SHA-256 values computed on CRLF bytes while Git stores LF
(13 V1 files + 9 V2-only files; details in `docs/data/dataset-freeze-v1-eol-erratum.md`). No frozen artifact or hash was changed.

## 2. Verified findings
| # | Finding | Evidence |
|---|---|---|
| 1 | Freeze V1/V2 verify via one shared verifier; unknown mismatch fails | `scripts/freeze_checksum.py`, `tests/test_freeze_checksum_compat.py` |
| 2 | Backend compiles; ESLint 0 errors / 57 warnings; Prettier non-conformant in 44 files | `pnpm run typecheck`, `build`, `lint:check`, `prettier --check` |
| 3 | Backend has **no unit tests**; only e2e specs requiring PostgreSQL | `jest` → "No tests found"; `test/*.e2e-spec.ts` |
| 4 | Flutter analyze clean, 160 tests pass (OSM tile fetch noise in test logs is network-only) | `flutter analyze`, `flutter test` |
| 5 | AI service instantiates the Gemini client at import time, so importing `app.main` without `GEMINI_API_KEY` raises `ValueError` | `app/llm/gemini.py:9`; reproduced when exporting OpenAPI |
| 6 | Clean clones lack the licensed ViHoRec CSVs (git-ignored) → 7 deterministic root tests need local data | CI simulation with `data/restricted/vihorec` hidden |
| 7 | Mobile hardcodes `http://localhost:3000` / `:8000` | `apps/mobile/lib/core/constants/app_constants.dart` |
| 8 | `.env.example` held placeholder secrets only; unused variables remain listed (Supabase, Cloudinary, Google Maps) - kept, documented in runbook | `.env.example` |

## 3. Risks
- **R1** Live-DB behaviour (preferences e2e, RAG retrieval, freeze DB invariants) is **unverified** in this environment.
- **R2** CI workflow has never run on GitHub runners (commands validated locally only; first run may need small fixes, e.g. Flutter channel/SDK constraint, heavy `sentence-transformers` install).
- **R3** Hardcoded base URLs block device/emulator and deployed testing.
- **R4** Backend lint `lint` script mutates files (`--fix`); `lint:check` added for CI.
- **R5** Dependency freshness: 54 Flutter packages have newer incompatible versions; no major upgrades attempted (out of scope).

## 4. Deferred (not done in W3-00)
NestJS OpenAPI snapshot (needs DB-backed app boot), Prettier enforcement, backend unit tests, secrets scanning in CI, Dockerised dev stack.
