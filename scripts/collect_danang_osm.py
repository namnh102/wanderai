#!/usr/bin/env python3
"""Canonical Da Nang OSM Fresh Collector for GoMate MVP-SCOPE-01 Dataset Freeze V2.

Queries canonical Overpass endpoint:
https://overpass-api.de/api/interpreter

Collects raw OSM snapshot for Da Nang using data/queries/osm/danang_v2.overpassql.
Preserves raw response unchanged and computes cryptographic SHA-256.
"""

import hashlib
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("danang_osm_collector")

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "GoMate-Thesis-DataFoundation/1.0 (academic-reproducible-research; contact: thesis@wanderai.vn)"

def compute_sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def execute_overpass_query(query_str: str, max_retries: int = 5) -> tuple[bytes, dict]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    backoffs = [5, 15, 30, 60, 120]
    last_err = None

    for attempt in range(max_retries):
        logger.info(f"Querying Overpass API (attempt {attempt + 1}/{max_retries})...")
        try:
            req_time_utc = datetime.now(timezone.utc).isoformat()
            resp = requests.post(
                OVERPASS_ENDPOINT,
                data={"data": query_str},
                headers=headers,
                timeout=120
            )

            if resp.status_code == 200:
                raw_bytes = resp.content
                # Parse to ensure valid JSON and extract osm_base
                parsed = json.loads(raw_bytes.decode('utf-8'))
                osm_base = parsed.get("osm3s", {}).get("timestamp_osm_base", "UNKNOWN")
                element_count = len(parsed.get("elements", []))
                logger.info(f"Query succeeded: {element_count} elements returned. osm_base={osm_base}")
                metadata = {
                    "overpass_endpoint": OVERPASS_ENDPOINT,
                    "query_timestamp_utc": req_time_utc,
                    "osm_base": osm_base,
                    "element_count": element_count,
                    "status_code": resp.status_code
                }
                return raw_bytes, metadata
            elif resp.status_code == 429 or resp.status_code >= 500:
                logger.warning(f"Overpass returned HTTP {resp.status_code}. Backing off {backoffs[attempt]}s...")
                time.sleep(backoffs[attempt])
            else:
                resp.raise_for_status()

        except Exception as e:
            logger.warning(f"Network error on attempt {attempt + 1}: {e}")
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(backoffs[attempt])

    raise RuntimeError(f"Overpass collection failed after {max_retries} attempts: {last_err}")

def run_collection():
    repo_root = Path(__file__).resolve().parent.parent
    query_file = repo_root / "data" / "queries" / "osm" / "danang_v2.overpassql"
    raw_dir = repo_root / "data" / "raw" / "osm"
    raw_dir.mkdir(parents=True, exist_ok=True)

    today_str = "2026-10-07"
    raw_output_file = raw_dir / f"danang_{today_str}_v2.json"
    metadata_output_file = raw_dir / f"danang_collection_metadata_{today_str}_v2.json"

    print("=" * 70)
    print("COLLECTING FRESH OSM REGION: DA NANG (V2)")
    print(f"Query file:          {query_file}")
    print(f"Raw output file:     {raw_output_file}")
    print(f"Metadata output:     {metadata_output_file}")
    print("=" * 70)

    if not query_file.exists():
        raise FileNotFoundError(f"Missing query file: {query_file}")

    query_text = query_file.read_text(encoding="utf-8")
    raw_bytes, meta = execute_overpass_query(query_text)

    # Write immutable raw snapshot
    with open(raw_output_file, "wb") as f:
        f.write(raw_bytes)

    sha = compute_sha256_bytes(raw_bytes)
    file_size = len(raw_bytes)

    meta["sha256"] = sha
    meta["bytes"] = file_size
    meta["output_file"] = str(raw_output_file.relative_to(repo_root)).replace("\\", "/")
    meta["query_file"] = str(query_file.relative_to(repo_root)).replace("\\", "/")
    meta["region"] = "danang"
    meta["bbox"] = {
        "south": 15.95,
        "west": 107.95,
        "north": 16.20,
        "east": 108.35
    }

    print(f"[PASS] DA NANG raw snapshot saved:")
    print(f"       File:     {meta['output_file']}")
    print(f"       Bytes:    {file_size}")
    print(f"       Elements: {meta['element_count']}")
    print(f"       osm_base: {meta['osm_base']}")
    print(f"       SHA-256:  {sha}")

    with open(metadata_output_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"\nCollection metadata logged to: {metadata_output_file}")

if __name__ == "__main__":
    run_collection()
