# TASKS

## Current
**W3-00 - Integration baseline & project readiness** (in progress; at review gate)
- [x] Preflight, merge PR #2 → #3 → #4 → #5 (local, no rebase/squash)
- [x] W3-00-FIX1 (V1 EOL verifier), FIX2 (V2), FIX3 (REC-A assertion)
- [x] Integration test matrix (see EVIDENCE.md)
- [x] Tooling audit; `typecheck` / `lint:check` scripts; Ruff; OpenAPI snapshot (FastAPI); CI workflow; env hygiene
- [x] Project-control docs and `docs/w3/*`
- [ ] Review gate: owner approval before push
- [ ] CI first run on GitHub (not yet executed)
- [ ] Re-run live DB tests once the W3 developer environment (PostgreSQL + Redis) exists

## Next (NOT started)
- W3-01 - product/runtime integration (to be defined after the W3-00 review gate; first thesis-critical package per roadmap is `WP-PROF-01` follow-up / `WP-AUTH-01`).
