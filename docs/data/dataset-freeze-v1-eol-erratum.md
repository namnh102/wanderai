# Dataset Freeze V1 — EOL Erratum (verification compatibility)

**Status:** erratum to verification only. Dataset Freeze V1 is **immutable and unchanged**.

## What happened
- A historical subset of Freeze V1 textual artifacts had their SHA-256 values in
  `data/manifests/dataset-freeze-v1.sha256` computed over **CRLF** bytes
  (Windows working copies at freeze time).
- Git stored those files as **LF** blobs. The other artifacts (4 files) were hashed over LF bytes.
- A clean checkout (Linux/CI, or Windows with `core.autocrlf=false`) therefore cannot
  reproduce 13 of the 23 manifest hashes from raw bytes, although the semantic content is identical.

## What this erratum does NOT do
- No hash in `dataset-freeze-v1.sha256` is modified.
- No Freeze V1 artifact (`gomate_places_freeze_v1.json`, synthetic preferences, OSM raw/processed, …) is rewritten or regenerated.
- No POI or synthetic preference value is changed.

## Compatibility mechanism
- Record: `data/manifests/dataset-freeze-v1-eol-compat.json` — a **verifier compatibility record, not part of Freeze V1**.
  Each exception states `path`, `historical_expected_sha256`, `historical_eol_form` (`CRLF`) and
  `canonical_git_eol_form` (`LF`). Only the 13 paths proven to need it are listed.
- Verifier: `scripts/freeze_checksum.py`.
  1. Hash raw bytes; match ⇒ `PASS`.
  2. Mismatch on an **explicitly listed** path ⇒ reconstruct CRLF bytes deterministically
     (`LF→CRLF`) and compare to the frozen hash; match ⇒ `LEGACY_EOL_COMPAT_PASS`.
  3. Any other mismatch (unlisted path, changed content, hash restated differently, unknown EOL form) ⇒ `FAIL`.
- There is no general CRLF fallback.

## Evidence (exact Git blob bytes at the time of the fix)
Four paths match raw/LF (`hanoi_v1.overpassql`, `halong_v1.overpassql`, `hanoi_2026-10-07.json`,
`halong_2026-10-07.json`); the 13 compat paths match only the CRLF form; 6 restricted ViHoRec CSVs
are git-ignored (licensing) and verified from the local working tree only.

## Policy going forward
- `.gitattributes` sets `* text=auto eol=lf`. Repository text is LF on every platform.
- **New freezes must hash canonical repository (LF) bytes** and must not add compat entries.
- Local `core.autocrlf` is not part of the solution.
