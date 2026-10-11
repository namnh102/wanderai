#!/usr/bin/env python3
"""Bounded Overture Places Fetcher for Da Nang (MVP-SCOPE-01).

Queries Overture Release 2026-09-23.1 GeoParquet for bounded Da Nang area:
- bbox: [15.95, 16.20] N, [107.95, 108.35] E

Saves bounded local snapshot in data/raw/overture/overture_danang_2026-09-23.1.parquet
"""

import logging
import sys
from pathlib import Path
import pyarrow.dataset as ds
import pyarrow.fs as pafs
import pyarrow.compute as pc
import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("danang_overture_fetcher")

OVERTURE_S3_URI = "overturemaps-us-west-2/release/2026-09-23.1/theme=places/type=place"

BOUNDS = {
    "min_lat": 15.95,
    "max_lat": 16.20,
    "min_lon": 107.95,
    "max_lon": 108.35
}

COLUMNS = [
    "id", "names", "basic_category", "taxonomy", "operating_status",
    "sources", "addresses", "websites", "phones", "bbox"
]

def fetch_bounded_overture_danang():
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "data" / "raw" / "overture"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "overture_danang_2026-09-23.1.parquet"

    if out_file.exists():
        logger.info(f"Existing bounded snapshot found: {out_file}. Size: {out_file.stat().st_size} bytes.")
        table = pq.read_table(out_file)
        logger.info(f"Records in existing snapshot: {table.num_rows}")
        return

    logger.info("Connecting to Overture Maps S3 bucket (release 2026-09-23.1)...")
    s3 = pafs.S3FileSystem(anonymous=True, region="us-west-2")
    dataset = ds.dataset(OVERTURE_S3_URI, filesystem=s3, format="parquet")

    logger.info(f"Scanning Overture Places GeoParquet for DA NANG bbox: {BOUNDS}...")
    filt = (
        (pc.field("bbox", "xmin") >= BOUNDS["min_lon"]) &
        (pc.field("bbox", "xmax") <= BOUNDS["max_lon"]) &
        (pc.field("bbox", "ymin") >= BOUNDS["min_lat"]) &
        (pc.field("bbox", "ymax") <= BOUNDS["max_lat"])
    )

    table = dataset.to_table(filter=filt, columns=COLUMNS)
    logger.info(f"Loaded {table.num_rows} records for DA NANG. Writing to {out_file}...")
    pq.write_table(table, out_file)
    logger.info(f"Saved: {out_file} ({out_file.stat().st_size} bytes, {table.num_rows} rows)")

if __name__ == "__main__":
    fetch_bounded_overture_danang()
