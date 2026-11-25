# GOMATE W07 — Versioned Erratum Proposal `v0.2.1-E01` for `tokenizer.json` SHA-256 in Candidate Annex `G1.5 v0.2.1`

- **Erratum ID:** `W07-B2-G15-ERRATUM-V0.2.1-E01`
- **Target Candidate Authority Document:** `W07_B2_G1_5_EXECUTION_ANNEX_CANDIDATE_V0_2_1.md` (`68,620` bytes, SHA-256 `842530dd737e2b2371280a4091ca760e540ec783d6ae654d462e33e148075740`)
- **Original Authority Mutation Status:** **`UNMODIFIED_ON_DISK`** (`original_authority_modified = false`; original file remains byte-identical at `842530dd737e2b2371280a4091ca760e540ec783d6ae654d462e33e148075740`)
- **Governance Status:** **`PROPOSED_ERRATUM_AWAITING_OWNER_G15_FREEZE_SIGNOFF`** (`G1.5 = HOLD`)

---

## 1. Forensic Finding & Root-Cause Trace

During offline verification of the pinned `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` HuggingFace snapshot (`e8f8c211226b894fcb81acc59f3b34ba3efd5f42`), a single 56-hex-character transcription discrepancy was identified on **Line 241 (`§5.1 Environment & Pinned Dependency Facts`)** of `W07_B2_G1_5_EXECUTION_ANNEX_CANDIDATE_V0_2_1.md`:

1. **Historical `G1` Reproducibility Manifest (`2026-11-12`, Audited `PASS`):**
   - In `g1_corrective_02_manifest.json` (`260,489` bytes, SHA-256 `b03bea8212b8c755040a9ce35332b50483c5b8f44a01f3320a03f23d462465ab`, Line `12`), the machine-computed `tokenizer.json` digest was recorded as:
     ```json
     "tokenizer_json_sha256": "2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8"
     ```
   - This exact `g1_corrective_02_manifest.json` file was independently hash-verified and accepted in `GOMATE_W07_B2_G1_INDEPENDENT_SCIENTIFIC_PASS_RECEIPT_2026-11-12.md` (`10,444` bytes, SHA-256 `97c194ba35d154b3e8fa551553bf3990859bbf9635ab8987f60713e5ef383b99`).
2. **Candidate Annex `G1.5 v0.2.1` Drafting Transcription Error (`2026-11-13`):**
   - On Line `400` (`§8 FX-04-C1-TOKEN-CEILING`) of `W07_B2_G1_5_EXECUTION_ANNEX_CANDIDATE_V0_2_1.md`, the digest is cited by its 8-hex prefix `2c3387be...`.
   - On Line `241` (`§5.1`), the 8-hex prefix `2c3387be` was preserved, but the trailing 56 hex characters were erroneously transcribed as `9236fb79efbe8abbbdcbf2fd22cc182fd7eed2cfcd91fb54c6f7bb24` instead of the actual on-disk and G1-recorded suffix `76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8`.

---

## 2. Complete Pinned Snapshot `e8f8c211226b894fcb81acc59f3b34ba3efd5f42` File Manifest

All 9 files inside the cached HuggingFace snapshot `models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots/e8f8c211226b894fcb81acc59f3b34ba3efd5f42`:

| File Name | Size (Bytes) | Verified Raw SHA-256 |
|---|---:|---|
| `README.md` | `3,888` | `1e98ea05b0de579fcaad3d625b62ea55647142ed674d5f5ebf1440e4bbbb6f23` |
| `config.json` | `645` | `6300193cb75e01cf80c96decef7187dfb33094d97cc1490b7ead6ff134476e4e` |
| `config_sentence_transformers.json` | `122` | `b8c64b5cece00d8424b4896ea75b512b6008576088497609dfeb6bd63e6d36b8` |
| `model.safetensors` | `470,641,600` | `eaa086f0ffee582aeb45b36e34cdd1fe2d6de2bef61f8a559a1bbc9bd955917b` |
| `modules.json` | `229` | `8f4b264b80206c830bebbdcae377e137925650a433b689343a63bdc9b3145460` |
| `sentence_bert_config.json` | `53` | `70f4448f31320443fe3557cacea5abf2dcc4915dda8c80646bec9f3bb0aa5a1f` |
| `special_tokens_map.json` | `239` | `378eb3bf733eb16e65792d7e3fda5b8a4631387ca04d2015199c4d4f22ae554d` |
| **`tokenizer.json`** | **`9,081,518`** | **`2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8`** |
| `tokenizer_config.json` | `526` | `5036ea374ffedd706e3bef33e2e0d6953cb868ef8a490e76e32ba0faa37a6b9b` |

*(Note: For `tokenizer.json`, raw SHA-256 and LF-normalized SHA-256 are identical: `2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8`.)*

---

## 3. Proposed Clause Redline for `Annex G1.5` Freeze (`v0.2.1` $\to$ `v0.2.1-E01` / `v1.0-frozen`)

### Section `5.1`, Line `241`:
- **Current Text in `W07_B2_G1_5_EXECUTION_ANNEX_CANDIDATE_V0_2_1.md` (`842530dd...`, Line 241):**
  > `[-]` `- **Cached HuggingFace Snapshot:** sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 revision e8f8c211226b894fcb81acc59f3b34ba3efd5f42 (tokenizer.json SHA-256 2c3387be9236fb79efbe8abbbdcbf2fd22cc182fd7eed2cfcd91fb54c6f7bb24).`
- **Proposed Erratum Text (`W07-B2-G15-ERRATUM-V0.2.1-E01`):**
  > `[+]` `- **Cached HuggingFace Snapshot:** sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 revision e8f8c211226b894fcb81acc59f3b34ba3efd5f42 (tokenizer.json 9,081,518 B, SHA-256 2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8, matching G1-audited g1_corrective_02_manifest.json b03bea82... L12; supersedes v0.2.1 L241 typographical transcription 2c3387be9236fb79...).`

---

## 4. Project Owner Sign-Off Block (`[BLANK — AWAITING OWNER AT G1.5 FREEZE]`)

- **Decision Code:** `OD-G15-ERRATUM-TOK-01`
- **Owner Selection:** `[ ] APPROVE ERRATUM V0.2.1-E01 AT G1.5 FREEZE` / `[ ] HOLD`
- **Project Owner Signature & Date:** `[BLANK]`
