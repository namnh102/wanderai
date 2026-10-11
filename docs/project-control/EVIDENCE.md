# EVIDENCE (W3-00)

## Branch heads and integration commits (local, unpushed)
| Step | Commit |
|---|---|
| `origin/develop` baseline | `1befc68b3607c0460d22e51ae8f31b5a282e71ab` |
| PR #2 `feature/data-foundation-w2` (`c2acc02`) merged | `218a5b8` |
| FIX1 legacy Freeze V1 EOL verifier | `92ca9f6` |
| PR #3 `feature/profile-preferences` (`b661c6b`) merged | `5f2cfe2` |
| PR #4 `feature/mvp-three-city-freeze-v2` (`e464062`) merged | `9861547` |
| FIX2 Freeze V2 EOL verifier | `7e3c792` |
| PR #5 `feature/rec-a-content-baseline-v1` (`db91e77`) merged | `3075bf1` |
| FIX3 REC-A integrity assertion uses shared verifier | `ab55856` (= `develop`) |

GitHub PRs #2-#5 are not merged on GitHub yet (nothing pushed).

## Test results at `ab55856`
| Suite | Result |
|---|---|
| Root `pytest tests` | 64 passed, 1 BLOCKED_BY_ENVIRONMENT (`test_live_database_invariants`, ConnectionRefused) |
| `apps/ai-service` pytest | 77 passed, 13 skipped, 2 BLOCKED_BY_ENVIRONMENT (DB: `test_rag_retrieval_da_nang_culinary`, `test_synthetic_documents_never_reach_the_provider`) |
| REC-A baseline `tests/test_reca_baseline.py` | 19 passed |
| Backend `tsc --noEmit` / `nest build` | pass |
| Backend ESLint | 0 errors, 57 warnings |
| Backend e2e (incl. preferences) | BLOCKED_BY_ENVIRONMENT (no PostgreSQL) |
| Flutter `analyze` | no issues |
| Flutter `test` | 160 passed |
| Ruff (`E9,F63,F7,F82`) | pass |
| FastAPI OpenAPI snapshot `--check` | up to date |
| CI simulation (restricted data hidden, CI deselects) | 57 passed, 8 deselected |

## Dataset hashes
- Freeze V2 artifact `gomate_places_freeze_v2.json`: `93681135d94b379f28802aa75204a0a4c7bec4039f85d28e76ae6737e792e245` (CRLF form; git blob LF sha256 `f7517938598e…`)
- Lineage `freeze-v1-to-v2-place-lineage.json`: `076aeb3804320ba7f0b2f8da846aae3e18d083cf74c10e8c336e448a33464561` (git blob LF sha256 `c07ab0f2a162…`)
- Manifest files (LF sha256): V1 `2a1428f3d327…`, V2 `cc9f2e248941…`
- `git diff 9861547..ab55856 -- <5 frozen files>` and `git diff 3075bf1..ab55856 -- data/` showed no content change.
