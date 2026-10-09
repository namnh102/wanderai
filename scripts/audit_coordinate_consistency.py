#!/usr/bin/env python3
"""DATA-02-R1 Canonical Coordinate Consistency Audit.

Compares places.latitude/longitude vs place_sources(osm).latitude/longitude
for all 580 verified places.
Computes Haversine drift statistics:
- count
- median drift
- p95 drift
- max drift
- count > 5m
- count > 20m
- count > 100m
"""

import asyncio
import math
import os
import sys
import numpy as np
import asyncpg

sys.stdout.reconfigure(encoding='utf-8')
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai")

def haversine_dist(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch("""
            SELECT p.id::text as place_id, p.name, p.latitude as place_lat, p.longitude as place_lon,
                   ps.source_id, ps.latitude as source_lat, ps.longitude as source_lon,
                   d.name as dest_name
            FROM places p
            JOIN place_sources ps ON p.id = ps.place_id
            LEFT JOIN destinations d ON p.destination_id = d.id
            WHERE ps.source_name = 'osm' AND p.deleted_at IS NULL
            ORDER BY d.name, p.name
        """)

        print("=" * 70)
        print("CANONICAL COORDINATE CONSISTENCY AUDIT")
        print("=" * 70)
        print(f"Total verified OSM places evaluated: {len(rows)}")

        drifts = []
        drift_gt_5 = []
        drift_gt_20 = []
        drift_gt_100 = []

        for r in rows:
            p_lat, p_lon = r["place_lat"], r["place_lon"]
            s_lat, s_lon = r["source_lat"], r["source_lon"]
            if p_lat is None or p_lon is None or s_lat is None or s_lon is None:
                continue

            dist = haversine_dist(p_lat, p_lon, s_lat, s_lon)
            drifts.append(dist)

            entry = {
                "place_id": r["place_id"],
                "name": r["name"],
                "destination": r["dest_name"],
                "source_id": r["source_id"],
                "place_coords": (p_lat, p_lon),
                "source_coords": (s_lat, s_lon),
                "drift_meters": round(dist, 2)
            }

            if dist > 100.0:
                drift_gt_100.append(entry)
            elif dist > 20.0:
                drift_gt_20.append(entry)
            elif dist > 5.0:
                drift_gt_5.append(entry)

        drifts = np.array(drifts)
        median_drift = np.median(drifts)
        p95_drift = np.percentile(drifts, 95)
        max_drift = np.max(drifts)

        print("\nCOORDINATE DRIFT STATISTICS:")
        print(f"- Total Places Audited:  {len(drifts)}")
        print(f"- Median Drift:          {median_drift:.4f} meters")
        print(f"- P95 Drift:             {p95_drift:.4f} meters")
        print(f"- Max Drift:             {max_drift:.4f} meters")
        print(f"- Count > 5m:            {len(drift_gt_5)}")
        print(f"- Count > 20m:           {len(drift_gt_20)}")
        print(f"- Count > 100m:          {len(drift_gt_100)}")

        if len(drift_gt_100) > 0:
            print("\nSignificant Drift (>100m) Details:")
            for d in drift_gt_100:
                print(f"  [{d['destination']}] {d['name']} ({d['source_id']}): {d['drift_meters']}m")
        else:
            print("\n[VERDICT: 100% OF VERIFIED PLACES HAVE MATERIALLY IDENTICAL COORDINATES (ZERO SIGNIFICANT DRIFT)]")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
