# W06 Benchmark Run Evidence Directory (`data/evaluation/w06/runs/`)

This directory is the default local runtime root for single-scenario evidence directories produced by `scripts/run_w06_planner_benchmark.py` (`W06-INSTRUMENT-01A`).

## Evidence Structure per Run Directory

Each run directory persists:
- `scenario_input.json` — canonical UTF-8 LF JSON of `BenchmarkScenarioInput` (`SHA256_CANONICAL_JSON_UTF8_LF_BYTES`)
- `raw_provider_response.txt` — exact unmodified UTF-8 bytes returned by the live model provider (`SHA256_EXACT_PERSISTED_UTF8_BYTES`; CRLF preserved verbatim if present; persisted even when JSON parsing or schema validation fails)
- `parsed_plan_response.json` — canonical UTF-8 LF JSON of `BenchmarkPlanResponse` (`SHA256_CANONICAL_JSON_UTF8_LF_BYTES`; written only when `run_status == "VALID"`)
- `run_manifest.json` — deterministic cryptographic run manifest (`BenchmarkRunManifest`, `SHA256_CANONICAL_JSON_UTF8_LF_BYTES`) recording `W06-MEASUREMENT-CONTRACT-01` v1.1.0 metadata, latency, nullable authoritative token usage (`input_tokens`, `output_tokens`, `total_tokens`), and artifact-specific SHA256 digests under `hash_basis_version = "W06-ARTIFACT-HASH-BASIS-V1"` (`hash_basis_by_artifact`)

## Git Policy

- Ad-hoc local execution directories under `data/evaluation/w06/runs/*` are ignored by `.gitignore` and must **not** be committed as scientific results during `W06-INSTRUMENT-01A`.
- Automated unit tests use temporary directories (`tmp_path`) only.
