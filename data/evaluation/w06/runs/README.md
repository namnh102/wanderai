# W06 Benchmark Run Evidence Directory (`data/evaluation/w06/runs/`)

This directory is the default local runtime root for single-scenario evidence directories produced by `scripts/run_w06_planner_benchmark.py` (`W06-INSTRUMENT-01A`).

## Evidence Structure per Run Directory

Each run directory persists:
- `scenario_input.json` — canonical UTF-8 LF JSON of `BenchmarkScenarioInput`
- `raw_provider_response.txt` — exact unmodified UTF-8 bytes returned by the live model provider (preserved even when JSON parsing or schema validation fails)
- `parsed_plan_response.json` — canonical UTF-8 LF JSON of `BenchmarkPlanResponse` (written only when `run_status == "VALID"`)
- `run_manifest.json` — deterministic cryptographic run manifest (`BenchmarkRunManifest`) recording `W06-MEASUREMENT-CONTRACT-01` v1.1.0 metadata, latency, nullable authoritative token usage, and exact SHA256 digests (`EXACT_PERSISTED_UTF8_LF_BYTES_SHA256`)

## Git Policy

- Ad-hoc local execution directories under `data/evaluation/w06/runs/*` are ignored by `.gitignore` and must **not** be committed as scientific results during `W06-INSTRUMENT-01A`.
- Automated unit tests use temporary directories (`tmp_path`) only.
