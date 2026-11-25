# GOMATE W07 — One-Page Scope, Trigger & Evidence Checklist for Separate Owner Permission to Execute `STUB-01..STUB-05` on the Frozen 137-Document Corpus (`2026-11-21`)

- **Checklist ID:** `W07-G15-STUB01-05-READONLY-137-CORPUS-PERMISSION-CHECKLIST-V1.1`
- **Prerequisite Baseline (Satisfied `2026-11-21`):** Project Owner chat-approved `GOMATE_W07_G15_TECHNICAL_ANNEX_V0_2_2_CANDIDATE_2026-11-21.md` (`71,761` B, SHA-256 `e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940`, Decision `OD-W07-G15-TECH-FREEZE-V0261121-01`), ratifying `OD-G15-01..04` (`THRESH_STATIC_PRE_G3`) and Erratum `E01` (`tokenizer.json` SHA-256 `2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8`).
- **Versioned Addendum (`v1.1 — 2026-11-21` Scoped Chat-Approval Waiver `OD-W07-G15-STUB01-05-CHAT-AUTH-WAIVER-V1-20261121-01`):**
  - The Project Owner approved replacing local Ed25519 signing with the scoped non-cryptographic `OWNER_CHAT_READONLY_V1` policy branch (`GOMATE_W07_STUB01_05_OWNER_CHAT_AUTH_WAIVER_V1_0_2026-11-21.md` `f01ccab9...` and `GOMATE_W07_STUB01_05_OWNER_CHAT_AUTH_POLICY_RECEIPT_V1_2026-11-21.json` `aa0881be...`) **solely** for one offline read-only pass of `STUB-01..STUB-05` on the 137-document Primary Arm `P` corpus (`Stage A` sealed manifest SHA-256 `9d417dc01692a58fa91e918a578470fcc1f3c89857cffe70e20f274960213096`).
  - **Identity Assurance Limitation:** `OWNER_CHAT_READONLY_V1` records `identity_authentication = "NOT_CRYPTOGRAPHICALLY_VERIFIED"` (accountable chat decision + hashed local artifact evidence, not cryptographic identity authentication). Legacy `ED25519_SIGNED_V1` rules remain preserved below, and `STUB-06`, `G2..G6`, `FINAL-50`, `DEV-5`, `T0`, and live API remain strictly in `HOLD`.

---

## 1. Exact Scope of the Separate Permission Request (`What Is & Is Not Authorized`)

| Dimension | Allowed Under This Narrow Permission | Strictly Excluded (`HARD HOLD`) |
|---|---|---|
| **Authorized Tests** | **`STUB-01` through `STUB-05` only** (`FX-01-CORPUS-HASH`, `FX-02-CANONICAL-CONSERVATION`, `FX-03-AUDIT-TAG-MULTI-SPAN`, `FX-04-C1-TOKEN-CEILING`, `FX-05-C0-TRUNCATION-AND-MULTI-SPAN-VIS`) implemented in `src/w07_retrieval/real_corpus_preflight.py`. | **`STUB-06` (`FX-12..FX-16` G4 scorer)**, `run_benchmark(..., execution_mode="formal-execution")`, and all `G2`, `G2A`, `G2B`, `G3`, `G4`, `G5`, `G6`, `W08` executions. |
| **Data Access** | **Read-only (`O_RDONLY`) verification** of the 7 frozen W07 corpus/provenance files (`137` Arm `P` documents: `97` B1B + `40` useful OSM) and local cached MiniLM `tokenizer.json` (`2c3387be76557bd4...`). | Zero access to or authoring of `FINAL-50` queries; zero access to `DEV-5` or `T0` evaluation packets; zero index persistence or query-against-corpus retrieval scoring (`BM25`/`Dense`/`RRF`). |
| **Network & Budget** | `100%` offline (`HF_HUB_OFFLINE=1`, socket guard active, `0` outbound packets, `\$0.00` spend). | Zero live API calls, zero external LLM/judge calls, zero Git push/PR/merge. |

---

## 2. Trigger Preconditions Required Before Execution (`Fail-Closed Gate`)

`validate_stub01_05_readonly_preflight_gate()` in `src/w07_retrieval/real_corpus_preflight.py` enforces all 5 preconditions below before reading a single byte of the 137-document corpus (plain environment variables `W07_G15_FROZEN=1`, `W07_OWNER_AUTHORIZED=1`, `W07_STUB_01_05_AUTHORIZED=1` are rejected):

1. `[ ]` **Independent Auditor Preflight Clearance:** ChatGPT audits the post-freeze `STUB-01..05` implementation and synthetic dry-run package (`READY_FOR_CHATGPT_G15_POST_FREEZE_STUB_PREFLIGHT_AUDIT_ONLY`) and issues a `PASS` verdict for the gate mechanics.
2. `[ ]` **Immutable `v0.2.2` Archive Integrity:** `verify_archived_v0_2_2_tech_freeze_baseline()` confirms `GOMATE_W07_G15_TECHNICAL_ANNEX_V0_2_2_CANDIDATE_2026-11-21.md` (`71,761` B, SHA-256 `e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940`) and `GOMATE_W07_G15_TECH_FREEZE_OWNER_APPROVAL_RECEIPT_2026-11-21.json` (`2,072` B, SHA-256 `1db438d30ad042296fca38abd882de0d1951d4dc1ff83c31b86a41d5765b6937`).
3. `[ ]` **Pinned Live Owner Public Key Provisioned:** Project Owner provisions `PINNED_LIVE_OWNER_STUB01_05_PUBKEY_HEX` (64-hex Ed25519 public key) in `src/w07_retrieval/real_corpus_preflight.py`.
4. `[ ]` **Frozen 7-File Corpus Bundle Manifest (`W07_G15_STUB01_05_CORPUS_BUNDLE_MANIFEST_V1`):** Lists exact byte sizes, SHA-256 digests, and Git blob SHA-1s of the 7 frozen corpus/provenance files (`97` B1B `9b0ed36e...`, `40` useful OSM `433c722d...`, `759` places v2 `f7517938...`, `60` target POIs `3a065165...`, B1B summary `1cf83d3b...`, 137-doc provenance `849e6b11...`, B1-FIX-01B receipt `38516e31...`).
5. `[ ]` **Detached Ed25519-Signed Owner Receipt (`W07_G15_STUB01_05_READONLY_CORPUS_AUTH_RECEIPT_V1`):** Signed under domain tag `W07-G15-STUB01-05-READONLY-CORPUS-AUTH-V1\x00` with `authorized_scope == "READONLY_137_CORPUS_STUB_01_TO_05_PREFLIGHT_ONLY"`, `authorized_stubs == ["STUB-01", "STUB-02", "STUB-03", "STUB-04", "STUB-05"]`, `real_137_corpus_readonly_stubs_authorized == true`, `stub_06_formal_g3_g4_authorized == false`, and `final50_or_dev_or_live_api_authorized == false`.

---

## 3. Required Post-Run Acceptance Evidence & Pass Criteria

When unlocked by the Owner receipt above, the one-shot read-only run must emit a deterministic JSON acceptance receipt + pytest log verifying:

| Stub | Required Pass Evidence on Frozen 137-Doc Arm `P` Corpus |
|---|---|
| **`STUB-01` (`FX-01`, `F-01`)** | `7/7` frozen artifact entries in both the bundle manifest and on-disk files cross-checked against `PINNED_LIVE_137_CORPUS_7_ARTIFACTS` (exact `artifact_id`, `canonical_repo_path`, `filename`, byte size, SHA-256, and Git blob SHA-1 from `Annex v0.2.2 §0.1` / `G15-R01`; fail-closed if missing, extra, or hash-mismatched); `137` eligible Arm `P` docs (`59 Hà Nội`, `52 Đà Nẵng`, `26 Hạ Long`; `97` B1B + `40` useful OSM); `0` `REFERENCE_ONLY` docs admitted. |
| **`STUB-02` (`FX-02`)** | Exact canonical code-point conservation: `295,644` total `S` code points `- 4,216` removed `R_AUDIT` code points `== 291,428` `V` code points; `21` empty parent headings propagated into child breadcrumbs; `38` omitted empty footers strictly inside the 10-item allowlist. |
| **`STUB-03` (`FX-03`, `F-02`)** | `46/46` `[CORROBORATED: ...]` tags removed across `23` Overture docs and `6` reference families (`0` remaining); computed sanitized view `V` SHA-256 equals pinned digest `046424e521f967f6c5575da1eeb914e5d340a118861c0cf04ca45256b364533d` (`\n<<<DOC>>>\n` serialization), with 4-branch sanitizer repeatability verified (without claiming four independent production retrieval paths); `100%` $\Pi_{V \to S}$ boundary and multi-tag straddle round-trips exact with `0` deleted tag offsets in projected spans. |
| **`STUB-04` (`FX-04`)** | Pinned MiniLM `tokenizer.json` SHA-256 `2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8` verified; `1,002` `C1` chunks with `100%` `token_count_with_special <= 128`, `0` violations, and `coverage_lost_due_to_chunking == 0`. |
| **`STUB-05` (`FX-05`)** | On `w07-b1b-doc-overture-f0d424bd-e55bab3c` (`>128` tokens under `C0`), `SYNTHETIC_HEADER -> ∅`, truncated tail span yields `EvidenceSpanHit == 1` & `VisibleEvidenceSpanHit == 0`, token `128/129` cutoff straddle yields `VisibleEvidenceSpanHit == 0`, and early multi-interval `R_AUDIT` straddle yields `VisibleEvidenceSpanHit == 1` (`0` deleted tag chars in $C_{\text{vis}}$). |
| **Non-Mutation** | Pre- and post-run `verify_non_mutation.py` `PASS` (`0` bytes modified in the 7 frozen corpus files, `Annex v0.2.1` `842530dd...`, `Annex v0.2.2` `e78013fd...`, `Protocol v1.0` `5056c5c2...`, or `wanderai` Git state). |
