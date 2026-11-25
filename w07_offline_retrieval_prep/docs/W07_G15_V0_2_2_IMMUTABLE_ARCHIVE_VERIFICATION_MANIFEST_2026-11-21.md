# GOMATE W07 — G1.5 Annex v0.2.2 Immutable Archive Verification Manifest (`2026-11-21`)

- **Manifest ID:** `W07-G15-V022-IMMUTABLE-ARCHIVE-VERIFICATION-MANIFEST-2026-11-21`
- **Decision ID:** `OD-W07-G15-TECH-FREEZE-V022-20261121-01`
- **Classification:** `OWNER_CHAT_APPROVED_EXACT_HASH_BOUNDED_TECHNICAL_SPEC` (`OD-G15-01..04` under `THRESH_STATIC_PRE_G3` + Erratum `E01`)
- **Non-Rewrite Guarantee:** All 5 files from `GOMATE_W07_G15_OWNER_APPROVED_TECH_FREEZE_RECORD_2026-11-21.zip` (`35,637` B, SHA-256 `d778bbc56377bbe16670d0799106b02d06d411edf78a3011cf7bab224bb1909b`) were replicated as raw bytes (`content_rewritten = false`, `line_endings_converted = false`) into two Owner-controlled non-public local archive locations outside the `wanderai` Git repository, with pre-transfer and post-transfer byte lengths and SHA-256 digests verified identically.

---

## 1. Pre- and Post-Archive Byte & SHA-256 Verification Ledger

| Archived Artifact | Exact Bytes (Pre `==` Post) | Pre-Archive SHA-256 | Post-Archive Primary Storage SHA-256 | Post-Archive Prep Storage (`authorities_v0_2_2_tech_freeze/`) SHA-256 | Byte Identity |
|---|---:|---|---|---|---|
| `GOMATE_W07_G15_TECHNICAL_ANNEX_V0_2_2_CANDIDATE_2026-11-21.md` | `71,761` | `e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940` | `e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940` | `e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940` | **`VERIFIED (0 diffs)`** |
| `GOMATE_W07_G15_TECH_FREEZE_OWNER_DECISION_2026-11-21.md` | `5,291` | `ee6b7bdb6354f51f6da784adeeceb7418d17bb2c63acfcf59f37d9c7a38bcff3` | `ee6b7bdb6354f51f6da784adeeceb7418d17bb2c63acfcf59f37d9c7a38bcff3` | `ee6b7bdb6354f51f6da784adeeceb7418d17bb2c63acfcf59f37d9c7a38bcff3` | **`VERIFIED (0 diffs)`** |
| `GOMATE_W07_G15_TECH_FREEZE_OWNER_APPROVAL_RECEIPT_2026-11-21.json` | `2,072` | `1db438d30ad042296fca38abd882de0d1951d4dc1ff83c31b86a41d5765b6937` | `1db438d30ad042296fca38abd882de0d1951d4dc1ff83c31b86a41d5765b6937` | `1db438d30ad042296fca38abd882de0d1951d4dc1ff83c31b86a41d5765b6937` | **`VERIFIED (0 diffs)`** |
| `GOMATE_W07_G15_POST_FREEZE_ANTIGRAVITY_HANDOFF_2026-11-21.md` | `2,069` | `d02a53ebbbfb7304743980801e4edf7d0f9cee7f736fd6823fb88286209ea635` | `d02a53ebbbfb7304743980801e4edf7d0f9cee7f736fd6823fb88286209ea635` | `d02a53ebbbfb7304743980801e4edf7d0f9cee7f736fd6823fb88286209ea635` | **`VERIFIED (0 diffs)`** |
| `GOMATE_W07_G15_TECH_FREEZE_SHA256SUMS_2026-11-21.txt` | `509` | `8c849e2393cc4de2412292879518d5a1106604b5fa3c4f21deab5c24f000fc9a` | `8c849e2393cc4de2412292879518d5a1106604b5fa3c4f21deab5c24f000fc9a` | `8c849e2393cc4de2412292879518d5a1106604b5fa3c4f21deab5c24f000fc9a` | **`VERIFIED (0 diffs)`** |

---

## 2. Unchanged Controlling & Historical Authorities

| Immutable Authority | Size (Bytes) | Verified SHA-256 (Pre `==` Post) | Disposition |
|---|---:|---|---|
| `W07_B2_SCIENTIFIC_PROTOCOL_V1_0_OWNER_APPROVED_2026-11-04.md` | `24,725` (LF) / `25,088` (CRLF) | `5056c5c2373ee9584b8850ba49411160cc2c382ad6315aaada4c05fb9b0030c2` (LF) / `5056c5c26142c579e1033fe3557ca031c9a0d2f18a90c2015a0a3fe97a4fdbe2` (CRLF) | **UNCHANGED (`0` byte edits)** |
| `W07_B2_G1_5_EXECUTION_ANNEX_CANDIDATE_V0_2_1.md` (Both Stored Copies) | `68,620` | `842530dd737e2b2371280a4091ca760e540ec783d6ae654d462e33e148075740` | **UNCHANGED (`0` byte edits)** |
| `g15_r01_real_corpus_verification_receipt.json` (Historical Receipt) | `12,081` | `73ef28fba489a9702a2628450755fb6092bebc45b6dbf04eee04b0cfafd52e8a` | **UNCHANGED (Historical Evidence Only)** |
| `W07_B2_G1_5_TOKENIZER_SHA256_ERRATUM_PROPOSAL_V0_2_1_E01.md` / `.json` | `3,581` / `1,622` | `798c9fab3f53bc1de47327592119e1310fb589a9348c0239e2bab0eaf7c4af66` / `855d89db71386a345b32638455cc2aab0b2bc4ce0ab961729d9310803eb14399` | **RATIFIED IN `v0.2.2` (`2c3387be76557bd4...`)** |

---

## 3. Scope & Non-Authorization Boundary Recorded in Archive

- **Approved Technical Scope (`OD-G15-01..04`):** `D01` (137-doc Arm `P`, `P+C = NO-GO`, `5×3` `FINAL-50` quota schema only, `DEV <= 10`, `PRE_G3_QUERY_LOCK`), `D03` (`S -> V` `46/46` `R_AUDIT` stripper, $\Pi_{V \to S}$, `C0` vs `C1 <= 128` MiniLM tokens), `D04/D05.1–D05.3/D06` (`2×3` matrix, document collapse, tie rules, Erratum `E01` `tokenizer.json` SHA-256 `2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8`, 5-state relevance ontology, `G4` statistical & integrity contract), and `THRESH_STATIC_PRE_G3`.
- **Explicit Exclusions (`HOLD`):** `OD-G15-05 = HOLD`, `full_g15_closed = false`, `real_137_corpus_readonly_stubs_authorized = false`, `runtime_execution_authorization = false`, `formal_g3_benchmark_authorized = false`, `formal_g4_scoring_authorized = false`, `final50_authorized = false`, `dev5_authorized = false`, `live_api_authorized = false`, `git_push_pr_merge_authorized = false`.
