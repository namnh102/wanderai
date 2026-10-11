# DECISIONS

| # | Decision | Detail |
|---|---|---|
| D1 | Freeze V2 locked | Hà Nội core 145, Hạ Long core 188, Đà Nẵng core 289; REC-A-CORE-V2 = 622; secondary corpus = 137; total verified = 759. Freeze V2 SHA256 `93681135d94b379f28802aa75204a0a4c7bec4039f85d28e76ae6737e792e245`; lineage SHA256 `076aeb3804320ba7f0b2f8da846aae3e18d083cf74c10e8c336e448a33464561`. Never regenerated or edited. |
| D2 | Freeze V1 immutable | V1 manifest hashes are never rewritten. Legacy CRLF-vs-LF hash discrepancy is handled only by explicit verifier compatibility records (`dataset-freeze-v{1,2}-eol-compat.json`) - see `docs/data/dataset-freeze-v1-eol-erratum.md`. New freezes hash canonical LF bytes. |
| D3 | EOL policy | `.gitattributes`: `* text=auto eol=lf`. No reliance on local `core.autocrlf`. No mass renormalisation. |
| D4 | Canonical interests | `food_cuisine`, `culture_history`, `nature_outdoor`, `coffee_culture`, `beach_island`, `shopping_local`, `nightlife_entertainment`. |
| D5 | REC metrics | NDCG@K, Recall@K, Precision@K, HitRate@K, Coverage, Diversity, cold-start splits (`REC-EVAL-01`). REC-A is content-based; REC-B/collaborative is conditional on data and not started. |
| D6 | Source governance | Only licensed/open sources (OSM, Overture with approved licenses, Wikivoyage). No scraping of commercial providers; unlicensed data excluded; restricted ViHoRec files stay git-ignored. |
| D7 | No fake rating/review | Ratings stay NULL unless a real source exists; UI shows "Chưa có đánh giá". No synthetic reviews in evaluation corpus. |
| D8 | AI proposes, user decides | AI output (planner, recommendations) is a proposal; applying it requires explicit user confirmation. |
| D9 | Test honesty | Tests needing PostgreSQL/Redis or licensed data are labelled `BLOCKED_BY_ENVIRONMENT`, never skipped silently or counted as PASS. |
| D10 | CI scope | Mandatory CI makes no Gemini/OpenAI calls and needs no database; dummy API key only. |
