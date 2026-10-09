#!/usr/bin/env python3
"""Bounded Overture Places Fetcher for GoMate DATA-02.

Queries Overture Release 2026-09-23.1 GeoParquet for bounded MVP areas only:
- Hanoi bbox: [20.95, 21.15] N, [105.75, 105.95] E
- Ha Long bbox: [20.85, 21.05] N, [106.95, 107.25] E

Saves bounded local snapshots in data/raw/overture/ for immutable reproducibility.
"""

import json
import logging
import sys
from pathlib import Path
import pyarrow.dataset as ds
import pyarrow.fs as pafs
import pyarrow.compute as pc
import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("overture_fetcher")

OVERTURE_S3_URI = "overturemaps-us-west-2/release/2026-09-23.1/theme=places/type=place"

BOUNDS = {
    "halong": {"min_lat": 20.85, "max_lat": 21.05, "min_lon": 106.95, "max_lon": 107.25},
    "hanoi": {"min_lat": 20.95, "max_lat": 21.15, "min_lon": 105.75, "max_lon": 105.95}
}

COLUMNS = [
    "id", "names", "basic_category", "taxonomy", "operating_status",
    "sources", "addresses", "websites", "phones", "bbox"
]

def fetch_bounded_overture():
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "data" / "raw" / "overture"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Connecting to Overture Maps S3 bucket (release 2026-09-23.1)...")
    s3 = pafs.S3FileSystem(anonymous=True, region="us-west-2")
    dataset = ds.dataset(OVERTURE_S3_URI, filesystem=s3, format="parquet")

    for region, b in BOUNDS.items():
        out_file = out_dir / f"overture_{region}_2026-09-23.1.parquet"
        if out_file.exists():
            logger.info(f"Existing bounded snapshot found: {out_file}. Skipping fetch.")
            continue

        logger.info(f"Scanning Overture Places GeoParquet for {region.upper()} bbox...")
        filt = (
            (pc.field("bbox", "xmin") >= b["min_lon"]) &
            (pc.field("bbox", "xmax") <= b["max_lon"]) &
            (pc.field("bbox", "ymin") >= b["min_lat"]) &
            (pc.field("bbox", "ymax") <= b["max_lat"])
        )

        table = dataset.to_table(filter=filt, columns=COLUMNS)
        logger.info(f"Loaded {table.num_rows} records for {region.upper()}. Writing to {out_file}...")
        pq.write_table(table, out_file)
        logger.info(f"Saved: {out_file} ({out_file.stat().st_size} bytes)")

if __name__ == "__main__":
    fetch_bounded_overture()
