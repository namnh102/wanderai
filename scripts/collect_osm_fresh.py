#!/usr/bin/env python3
"""Canonical OSM Fresh Collector for GoMate DATA-02.

Queries the selected canonical Overpass endpoint:
https://overpass-api.de/api/interpreter

Collects raw OSM snapshots for Hanoi and Ha Long.
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
logger = logging.getLogger("osm_fresh_collector")

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "GoMate-Thesis-DataFoundation/1.0 (academic-reproducible-research; contact: thesis@wanderai.vn)"

def compute_sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def execute_overpass_query(query_str: str, max_retries: int = 4) -> tuple[bytes, dict]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

    backoffs = [5, 15, 30, 60]
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
    queries_dir = repo_root / "data" / "queries" / "osm"
    raw_dir = repo_root / "data" / "raw" / "osm"
    raw_dir.mkdir(parents=True, exist_ok=True)

    today_str = "2026-10-07"
    regions = [
        ("hanoi", queries_dir / "hanoi_v1.overpassql", raw_dir / f"hanoi_{today_str}.json"),
        ("halong", queries_dir / "halong_v1.overpassql", raw_dir / f"halong_{today_str}.json")
    ]

    collection_summary = {}

    for region_name, query_file, output_file in regions:
        print("=" * 70)
        print(f"COLLECTING FRESH OSM REGION: {region_name.upper()}")
        print(f"Query file:  {query_file}")
        print(f"Output file: {output_file}")
        print("=" * 70)

        if not query_file.exists():
            raise FileNotFoundError(f"Missing query file: {query_file}")

        query_text = query_file.read_text(encoding="utf-8")
        raw_bytes, meta = execute_overpass_query(query_text)

        # Write immutable raw snapshot
        with open(output_file, "wb") as f:
            f.write(raw_bytes)

        sha = compute_sha256_bytes(raw_bytes)
        file_size = len(raw_bytes)

        meta["sha256"] = sha
        meta["bytes"] = file_size
        meta["output_file"] = str(output_file.relative_to(repo_root)).replace("\\", "/")

        collection_summary[region_name] = meta
        print(f"[PASS] {region_name.upper()} raw snapshot saved:")
        print(f"       File:     {meta['output_file']}")
        print(f"       Bytes:    {file_size}")
        print(f"       Elements: {meta['element_count']}")
        print(f"       osm_base: {meta['osm_base']}")
        print(f"       SHA-256:  {sha}")

        # Rate-limiting pause between regions
        time.sleep(5)

    summary_file = raw_dir / f"collection_metadata_{today_str}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(collection_summary, f, indent=2, ensure_ascii=False)
    print(f"\nCollection metadata logged to: {summary_file}")

if __name__ == "__main__":
    run_collection()
