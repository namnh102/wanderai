"""TASK 07.4 - Real OSM data enrichment (attractions, beaches, culture, nature, ...).

Every record comes straight from an Overpass API response. No OSM id is ever typed in by hand or
generated; the output keeps the raw tags, the exact query and the upstream data timestamp.

Usage:
    python data/pipelines/osm/enrich_osm.py            # collect (live Overpass) -> raw snapshot + curated file
    python data/pipelines/osm/enrich_osm.py --from-raw # rebuild curated file from an existing raw snapshot (offline)

Outputs:
    data/raw/osm_enrichment.json                 raw Overpass elements + query + timestamps
    data/curated/places_osm_enrichment.json      canonical place records (with place_sources) to import
"""
import argparse
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from data.pipelines.osm.config import PILOT_REGIONS  # noqa: E402
from data.pipelines.osm.parse_osm import map_category, format_address, is_valid_coordinate  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("osm_enrichment")

MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
UA = {"User-Agent": "WanderAI-TourismPipeline/1.0 (academic project; contact: support@wanderai.vn)"}
RAW_PATH = ROOT / "data" / "raw" / "osm_enrichment.json"
OUT_PATH = ROOT / "data" / "curated" / "places_osm_enrichment.json"
CANONICAL_PATH = ROOT / "data" / "curated" / "places_canonical.json"
DENYLIST_PATH = ROOT / "data" / "manifests" / "osm-invalid-sources.json"
NAMESPACE = uuid.UUID("6f1d8a0e-0b7e-4c53-9e2c-5a1c4f0a7d11")  # fixed namespace -> deterministic place ids

# Categories this task adds, and the per-region cap (ranked by documentation quality, see score()).
CAPS = {"attraction": 25, "culture": 25, "beach": 10, "nature": 15, "entertainment": 10}


def build_query(bbox: dict) -> str:
    b = f"({bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']})"
    return (
        "[out:json][timeout:120];("
        f'nwr["tourism"~"^(attraction|museum|viewpoint|gallery|theme_park|zoo|aquarium)$"]["name"]{b};'
        f'nwr["natural"="beach"]["name"]{b};'
        f'nwr["historic"~"^(monument|castle|ruins|archaeological_site|memorial)$"]["name"]{b};'
        f'nwr["amenity"="place_of_worship"]["name"]["wikidata"]{b};'
        f'nwr["leisure"="park"]["name"]["wikidata"]{b};'
        ");out center tags;"
    )


def overpass(query: str, primary_only: bool = False) -> tuple[dict, str]:
    """Returns (json, endpoint). Mirrors can serve different data snapshots; primary_only pins the authoritative host."""
    last = None
    hosts = MIRRORS[:1] if primary_only else MIRRORS
    for attempt in range(1, 9):
        url = hosts[(attempt - 1) % len(hosts)]
        try:
            r = httpx.post(url, data={"data": query}, headers=UA, timeout=180)
            if r.status_code == 200:
                return r.json(), url
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        wait = min(15 * attempt, 90)
        log.warning("Overpass retry %s (%s) in %ss", attempt, last, wait)
        time.sleep(wait)
    raise RuntimeError(f"Overpass failed: {last}")


def collect(only: list[str] | None = None, primary_only: bool = False) -> dict:
    if only and RAW_PATH.exists():
        snapshot = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    else:
        snapshot = {
            "source": "OpenStreetMap via Overpass API",
            "license": "ODbL 1.0 (c) OpenStreetMap contributors",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "regions": {},
        }
    for name, bbox in PILOT_REGIONS.items():
        if only and name not in only:
            continue
        q = build_query(bbox)
        log.info("Querying %s", name)
        data, endpoint = overpass(q, primary_only)
        snapshot["regions"][name] = {
            "endpoint": endpoint,
            "query": q,
            "osm_base_timestamp": (data.get("osm3s") or {}).get("timestamp_osm_base"),
            "elements": data.get("elements", []),
        }
        log.info("%s: %d raw elements", name, len(snapshot["regions"][name]["elements"]))
        time.sleep(8)
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    return snapshot


def score(tags: dict) -> int:
    s = 0
    for k, w in (("wikidata", 3), ("wikipedia", 2), ("name:en", 2), ("website", 1), ("image", 1), ("opening_hours", 1)):
        if tags.get(k):
            s += w
    return s


def build_curated(snapshot: dict) -> list[dict]:
    known = set()
    if CANONICAL_PATH.exists():
        for p in json.loads(CANONICAL_PATH.read_text(encoding="utf-8")):
            for s in p.get("sources", []):
                known.add((s["source_name"], s["source_id"]))
    deny = set()
    if DENYLIST_PATH.exists():
        deny = {(s["source_name"], s["source_id"]) for s in json.loads(DENYLIST_PATH.read_text(encoding="utf-8"))["invalid_sources"]}

    per_group: dict[tuple, list] = {}
    seen = set()
    for region, blob in snapshot["regions"].items():
        for el in blob["elements"]:
            tags = el.get("tags") or {}
            name = (tags.get("name") or "").strip()
            lat, lon = el.get("lat"), el.get("lon")
            if lat is None and el.get("center"):
                lat, lon = el["center"].get("lat"), el["center"].get("lon")
            if not name or not is_valid_coordinate(lat, lon):
                continue
            sid = f"{el['type']}/{el['id']}"
            key = ("osm", sid)
            if key in seen or key in known or key in deny:
                continue
            seen.add(key)
            cat = map_category({**tags, "_": ""})
            if cat not in CAPS:
                continue
            per_group.setdefault((region, cat), []).append((score(tags), name, el, lat, lon, tags, sid, blob.get("osm_base_timestamp")))

    out = []
    for (region, cat), rows in sorted(per_group.items()):
        rows.sort(key=lambda r: (-r[0], r[1]))
        for _, name, el, lat, lon, tags, sid, base_ts in rows[: CAPS[cat]]:
            out.append({
                "id": str(uuid.uuid5(NAMESPACE, sid)),
                "name": name,
                "name_en": tags.get("name:en"),
                "category": cat,
                "address": format_address(tags) or f"{name}, {region}",
                "city": region,
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "rating": None,
                "review_count": 0,
                "sources": [{
                    "source_name": "osm",
                    "source_id": sid,
                    "raw_name": name,
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "raw_data": tags,
                    "confidence_score": 1.0,
                    "osm_base_timestamp": base_ts,
                }],
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-raw", action="store_true")
    ap.add_argument("--regions", nargs="*", help="re-collect only these regions (merged into the existing raw snapshot)")
    ap.add_argument("--primary-only", action="store_true", help="use only overpass-api.de (the host the provenance audit checks)")
    args = ap.parse_args()
    snapshot = json.loads(RAW_PATH.read_text(encoding="utf-8")) if args.from_raw else collect(args.regions, args.primary_only)
    curated = build_curated(snapshot)
    OUT_PATH.write_text(json.dumps(curated, ensure_ascii=False, indent=2), encoding="utf-8")
    by = {}
    for p in curated:
        by[(p["city"], p["category"])] = by.get((p["city"], p["category"]), 0) + 1
    log.info("Curated %d places -> %s", len(curated), OUT_PATH)
    for k, v in sorted(by.items()):
        log.info("  %s / %s: %d", k[0], k[1], v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
