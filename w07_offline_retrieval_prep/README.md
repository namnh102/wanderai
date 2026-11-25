# GOMATE W07 Offline Retrieval Prep (`w07_offline_retrieval_prep`)

> **Governance Status Banner (`PRE_FREEZE_READY` / `G1.5 = HOLD`)**
> - `W07-B2-G1.5` (`Annex G1.5 v0.2.1`): **HOLD (NOT YET FROZEN)**
> - `G2 / G3 / G4 / G5 / G6`: **HOLD**
> - `AUTO-EVAL-01 v0.4.2`: **CANDIDATE_NOT_YET_APPROVED**
> - API Spend: **`$0.00`** · Network Calls: **`0`** · Product Runtime / Frozen Data Modifications: **`0`**
> - Real 137-document corpus / `DEV-5` / `T0` / `FINAL-50` access: **`0` executions**
> - Passing tests in this workspace establishes **`OFFLINE_PREP_SYNTHETIC_VERIFIED`** only — **never** a `G3` or `G4` scientific `PASS`.

## Overview

Standalone, zero-network, pre-freeze preparation package for the GOMATE W07 Retrieval Benchmark (`2×3`: `C0/C1 × BM25/Dense/Hybrid RRF`) and the strictly decoupled `G4` scorer in accordance with `Protocol v1.0` and `Candidate Annex G1.5 v0.2.1`.

- **`src/w07_retrieval/`** (`11` modules: `__init__.py`, `schema.py`, `sanitizer.py`, `chunker_c0.py`, `chunker_c1.py`, `visibility.py`, `bm25.py`, `dense.py`, `fusion.py`, `blind_packet.py`, `runner.py`): Standalone `2×3` offline retrieval engine. Canonical document loading resides in `schema.py`, two-layer 6-family `R_AUDIT` stripping in `sanitizer.py`, and chunking in `chunker_c0.py` / `chunker_c1.py`. Zero imports from product runtime (`apps.ai_service`) or `w07_g4_scorer`.
- **`src/w07_g4_scorer/`** (`7` modules: `__init__.py`, `contracts.py`, `query_manifest.py`, `metrics.py`, `stats.py`, `judge_gates.py`, `scorer.py`): Completely decoupled `G4` scorer (zero ML/retriever imports; verifies sealed `g3_sealed_rankings_v1.jsonl` SHA-256 and external-only qrels).
- **`docs/`**:
  - `docs/W07_B2_G1_5_TOKENIZER_SHA256_ERRATUM_PROPOSAL_V0_2_1_E01.md` & `docs/w07_b2_g1_5_tokenizer_sha256_erratum_v0_2_1_e01.json`: Versioned erratum proposal reconciling `Annex G1.5 v0.2.1` Line `241` with the on-disk and G1-audited `tokenizer.json` SHA-256 (`2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8`) without modifying the original authority document (`842530dd...`).
  - `docs/W07_REAL_CORPUS_STUB_ACTIVATION_CRITERIA_V1.md`: `HOLD` governance and post-G1.5 activation criteria for all `6` real-corpus test stubs (`STUB-01..STUB-06`).

## Offline Python 3.11.9 Invocation

Invoke the Python `3.11.9` interpreter with bytecode disabled and offline HuggingFace flags enabled:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_DATASETS_OFFLINE = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONHASHSEED = "0"
$env:TOKENIZERS_PARALLELISM = "false"

python -B -m pytest -p no:cacheprovider -v
```

## Pinned Offline Embedding Snapshot & Versioned Erratum (`v0.2.1-E01`)

- **Model**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- **Snapshot ID**: `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`
- **Local Cache Path**: `~/.cache/huggingface/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots/e8f8c211226b894fcb81acc59f3b34ba3efd5f42`
- **Verified `tokenizer.json` SHA-256 (`9,081,518` B)**: `2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8`
  *(Reconciled in `docs/W07_B2_G1_5_TOKENIZER_SHA256_ERRATUM_PROPOSAL_V0_2_1_E01.md` against `g1_corrective_02_manifest.json` `b03bea82...` L12; original `W07_B2_G1_5_EXECUTION_ANNEX_CANDIDATE_V0_2_1.md` remains untouched at `842530dd...`.)*

## CLI Usage & Mode Separation (`synthetic-prep` vs `formal-execution`)

### 1. Synthetic Preparation Mode (`--execution-mode synthetic-prep`, Default)

```powershell
python -B -m w07_retrieval.runner `
  --execution-mode synthetic-prep `
  --corpus path/to/synthetic_corpus.jsonl `
  --queries path/to/synthetic_queries.jsonl `
  --output-dir path/to/out_dir `
  --packet-salt YOUR_SALT
```

Hard-blocks the real 137-document corpus and protected artifacts, stamping `"execution_mode": "synthetic-prep"` and `"scientific_authority_status": "SYNTHETIC_PREP_ONLY_NOT_G3_PASS"` in `g3_sealed_rankings_v1_manifest.json`.

### 2. Formal Execution Mode (`--execution-mode formal-execution`, Fail-Closed Pre-Freeze)

```powershell
python -B -m w07_retrieval.runner `
  --execution-mode formal-execution `
  --corpus path/to/frozen_137_corpus.jsonl `
  --queries path/to/sealed_final50_queries.jsonl `
  --owner-auth-receipt path/to/owner_auth_receipt.json `
  --frozen-corpus-receipt path/to/frozen_corpus_receipt.json `
  --output-dir path/to/out_dir
```

Fails closed unless `PINNED_LIVE_OWNER_G3_PUBKEY_HEX` is provisioned and both `--owner-auth-receipt` (`W07_G15_OWNER_EXECUTION_AUTHORIZATION_RECEIPT_V1`, Ed25519-signed) and `--frozen-corpus-receipt` (`W07_FROZEN_137_CORPUS_RECEIPT_V1`) pass cryptographic and SHA-256 verification. Plain environment variables (`W07_G15_FROZEN=1`, `W07_OWNER_AUTHORIZED=1`) are strictly rejected.

### 3. Decoupled G4 Scorer (`w07_g4_scorer.scorer`)

```powershell
python -B -m w07_g4_scorer.scorer `
  --rankings path/to/g3_sealed_rankings_v1.jsonl `
  --manifest path/to/g3_sealed_rankings_v1_manifest.json `
  --qrels path/to/qrels.jsonl `
  --queries path/to/queries.jsonl `
  --output path/to/g4_report.json
```

## Real-Corpus Stub Gating (`STUB-01..STUB-06` in `HOLD`)

All `6` real-corpus test stubs (`5` in `tests/test_real_corpus_gated_stubs.py` and `1` in `tests/test_fx12_to_fx16_g4_scorer.py`) remain in **`HOLD` (`SKIPPED`)** and reject plain environment variable spoofing. Full post-G1.5 unlock criteria are specified in `docs/W07_REAL_CORPUS_STUB_ACTIVATION_CRITERIA_V1.md`.
