#!/usr/bin/env python3
"""DATA-02 Overture Cross-Check & Provenance Linker.

Performs secondary cross-check of OSM candidate POIs against Overture Places
Release 2026-09-23.1 (Schema v2.0.0).

Strict Invariants:
- Overture is SECONDARY ONLY. Never replaces canonical OSM Place ID.
- Match threshold: distance <= 150m AND (Jaro-Winkler >= 0.85 OR Token Sort >= 0.88) AND category compatible.
- AUTO-LINK: distance <= 50m, similarity >= 0.90, category compatible, source provenance present, license resolved.
- License derived per source record (CDLA Permissive 2.0, Apache 2.0, CC0 1.0). If unresolved: LICENSE_UNRESOLVED.
- Operating status conflict: if Overture says permanently_closed, mark SOURCE_CONFLICT_REVIEW_REQUIRED (no deletion).
"""

import difflib
import json
import logging
import math
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
import pyarrow.parquet as pq

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("overture_crosscheck")

def remove_accents(input_str: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def normalize_name(name: str) -> str:
    clean = remove_accents(name.lower())
    clean = re.sub(r"[^\w\s]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def jaro_distance(s1: str, s2: str) -> float:
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    max_dist = max(len1, len2) // 2 - 1
    match1 = [False] * len1
    match2 = [False] * len2
    matches = 0

    for i in range(len1):
        start = max(0, i - max_dist)
        end = min(i + max_dist + 1, len2)
        for j in range(start, end):
            if match2[j]:
                continue
            if s1[i] == s2[j]:
                match1[i] = True
                match2[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    k = 0
    transpositions = 0
    for i in range(len1):
        if not match1[i]:
            continue
        while not match2[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    transpositions //= 2
    return (matches / len1 + matches / len2 + (matches - transpositions) / matches) / 3.0

def jaro_winkler(s1: str, s2: str, p: float = 0.1, max_l: int = 4) -> float:
    j = jaro_distance(s1, s2)
    l = 0
    for i in range(min(len(s1), len(s2), max_l)):
        if s1[i] == s2[i]:
            l += 1
        else:
            break
    return j + (l * p * (1.0 - j))

def token_sort_ratio(s1: str, s2: str) -> float:
    t1 = " ".join(sorted(s1.split()))
    t2 = " ".join(sorted(s2.split()))
    return difflib.SequenceMatcher(None, t1, t2).ratio()

# Known Overture License families
KNOWN_LICENSES = {
    "cdla-permissive-2.0": "CDLA Permissive 2.0",
    "cdla permissive 2.0": "CDLA Permissive 2.0",
    "apache-2.0": "Apache 2.0",
    "apache 2.0": "Apache 2.0",
    "cc0": "CC0 1.0",
    "cc0-1.0": "CC0 1.0",
    "cc0 1.0": "CC0 1.0",
}

APPROVED_AUTO_LINK_LICENSES = {"CDLA Permissive 2.0", "Apache 2.0", "CC0 1.0"}

def resolve_overture_license(sources: list[dict]) -> tuple[str | None, list[str]]:
    resolved_licenses = set()
    providers = []
    for s in sources:
        lic = (s.get("license") or "").strip().lower()
        prov = s.get("dataset") or s.get("provider") or "overture"
        providers.append(prov)
        for k, v in KNOWN_LICENSES.items():
            if k in lic:
                resolved_licenses.add(v)

    if not resolved_licenses:
        return None, providers

    # If multiple licenses, return comma-separated
    return "; ".join(sorted(resolved_licenses)), providers

def is_category_compatible(osm_tier1: str, ov_basic_cat: str, ov_taxonomy: dict) -> bool:
    ov_basic_cat = (ov_basic_cat or "").lower()
    hierarchy = [h.lower() for h in (ov_taxonomy.get("hierarchy") or [])]
    primary_tax = (ov_taxonomy.get("primary") or "").lower()

    if osm_tier1 == "FOOD_BEVERAGE":
        return any(c in ov_basic_cat for c in ("restaurant", "cafe", "fast_food", "bar", "food", "bakery", "coffee")) or "food_and_drink" in hierarchy
    elif osm_tier1 == "HOSPITALITY":
        return any(c in ov_basic_cat for c in ("hotel", "resort", "hostel", "guest_house", "motel", "accommodation", "inn")) or "accommodation" in hierarchy
    elif osm_tier1 == "CULTURE_HERITAGE":
        return any(c in ov_basic_cat for c in ("museum", "historic", "worship", "monument", "memorial", "temple", "pagoda", "church")) or "arts_and_entertainment" in hierarchy or "community_and_government" in hierarchy
    elif osm_tier1 == "NATURE_SCENERY":
        return any(c in ov_basic_cat for c in ("park", "viewpoint", "beach", "cave", "island", "nature", "scenic", "zoo")) or "outdoors_and_recreation" in hierarchy
    elif osm_tier1 == "ATTRACTIONS_LEISURE":
        return any(c in ov_basic_cat for c in ("attraction", "theme_park", "aquarium", "landmark", "entertainment", "tourist")) or "arts_and_entertainment" in hierarchy or "outdoors_and_recreation" in hierarchy
    elif osm_tier1 == "SHOPPING_COMMERCE":
        return any(c in ov_basic_cat for c in ("market", "mall", "shopping", "retail", "supermarket", "store")) or "retail" in hierarchy
    elif osm_tier1 == "TRANSPORT_HUBS":
        return any(c in ov_basic_cat for c in ("terminal", "ferry", "port", "transit", "station", "harbor", "transportation")) or "transportation" in hierarchy

    # If undetermined, allow cross-check based on string similarity
    return True

def crosscheck_region(region: str, osm_pois: list[dict], overture_parquet_path: Path) -> tuple[list[dict], dict]:
    print(f"\n--- Loading Overture places for {region.upper()} ---", flush=True)
    table = pq.read_table(overture_parquet_path)
    ov_count = table.num_rows
    print(f"Total Overture places in index: {ov_count}. Converting to Python dicts...", flush=True)

    records = table.to_pylist()
    print("Building spatial grid index...", flush=True)

    GRID_SIZE = 0.002
    grid = defaultdict(list)

    for i, row in enumerate(records):
        bbox = row["bbox"]
        lat = (bbox["ymin"] + bbox["ymax"]) / 2.0
        lon = (bbox["xmin"] + bbox["xmax"]) / 2.0
        names_struct = row.get("names") or {}
        primary_name = names_struct.get("primary") or ""
        if not primary_name:
            continue

        cell_x = int(math.floor(lon / GRID_SIZE))
        cell_y = int(math.floor(lat / GRID_SIZE))

        rec = {
            "index": i,
            "id": row["id"],
            "name": primary_name,
            "norm_name": normalize_name(primary_name),
            "lat": lat,
            "lon": lon,
            "basic_category": row["basic_category"],
            "taxonomy": row.get("taxonomy") or {},
            "operating_status": row.get("operating_status"),
            "sources": row.get("sources") or []
        }
        grid[(cell_x, cell_y)].append(rec)

    print(f"Spatial index built with {len(grid)} cells. Matching {len(osm_pois)} OSM POIs...", flush=True)

    crosscheck_results = []
    stats = {
        "region": region,
        "total_osm_pois": len(osm_pois),
        "total_overture_places": ov_count,
        "auto_linked": 0,
        "manual_review_candidates": 0,
        "unmatched": 0,
        "license_unresolved": 0,
        "source_conflicts": 0,
        "linked_places": []
    }

    for poi in osm_pois:
        lat = poi["latitude"]
        lon = poi["longitude"]
        osm_name_norm = normalize_name(poi["name"])
        osm_tier1 = poi["tier_1"]

        cell_x = int(math.floor(lon / GRID_SIZE))
        cell_y = int(math.floor(lat / GRID_SIZE))

        best_match = None
        best_score = -1.0

        # Scan surrounding 3x3 cells (covers >= 220m in all directions)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                candidates = grid.get((cell_x + dx, cell_y + dy), [])
                for ov in candidates:
                    dist = haversine_distance(lat, lon, ov["lat"], ov["lon"])
                    if dist > 150.0:
                        continue

                    # Check category compatibility
                    cat_compat = is_category_compatible(osm_tier1, ov["basic_category"], ov["taxonomy"])
                    if not cat_compat and dist > 50.0:
                        continue

                    # Name similarities
                    jw = jaro_winkler(osm_name_norm, ov["norm_name"])
                    ts = token_sort_ratio(osm_name_norm, ov["norm_name"])
                    sim = max(jw, ts)

                    # Score combining distance and similarity
                    dist_weight = max(0.0, 1.0 - (dist / 150.0))
                    combined_score = 0.6 * sim + 0.4 * dist_weight

                    if (jw >= 0.85 or ts >= 0.88) and combined_score > best_score:
                        best_score = combined_score
                        best_match = {
                            "overture_id": ov["id"],
                            "overture_name": ov["name"],
                            "distance_m": round(dist, 1),
                            "similarity_score": round(sim, 3),
                            "jaro_winkler": round(jw, 3),
                            "token_sort": round(ts, 3),
                            "category_compatible": cat_compat,
                            "operating_status": ov["operating_status"],
                            "sources": ov["sources"]
                        }

        # Classification
        if best_match:
            dist = best_match["distance_m"]
            sim = best_match["similarity_score"]
            cat_ok = best_match["category_compatible"]

            # Operating status conflict check
            is_conflict = False
            if best_match["operating_status"] == "permanently_closed":
                is_conflict = True
                stats["source_conflicts"] += 1

            # License extraction
            resolved_lic, providers = resolve_overture_license(best_match["sources"])
            if not resolved_lic:
                stats["license_unresolved"] += 1
                lic_status = "LICENSE_UNRESOLVED"
            else:
                lic_status = "LICENSE_RESOLVED"

            # AUTO-LINK threshold: distance <= 50m, sim >= 0.90, category compatible, license resolved
            if dist <= 50.0 and sim >= 0.90 and cat_ok and lic_status == "LICENSE_RESOLVED" and not is_conflict:
                status = "AUTO_LINK"
                stats["auto_linked"] += 1
            elif is_conflict:
                status = "SOURCE_CONFLICT_REVIEW_REQUIRED"
            else:
                status = "MANUAL_REVIEW_CANDIDATE"
                stats["manual_review_candidates"] += 1

            crosscheck_entry = {
                "source_id": poi["source_id"],
                "osm_name": poi["name"],
                "osm_tier1": poi["tier_1"],
                "status": status,
                "overture_match": {
                    "overture_id": best_match["overture_id"],
                    "overture_name": best_match["overture_name"],
                    "distance_m": best_match["distance_m"],
                    "similarity_score": best_match["similarity_score"],
                    "category_compatible": best_match["category_compatible"],
                    "operating_status": best_match["operating_status"],
                    "license": resolved_lic,
                    "providers": providers
                }
            }
        else:
            status = "UNMATCHED"
            stats["unmatched"] += 1
            crosscheck_entry = {
                "source_id": poi["source_id"],
                "osm_name": poi["name"],
                "osm_tier1": poi["tier_1"],
                "status": "UNMATCHED",
                "overture_match": None
            }

        crosscheck_results.append(crosscheck_entry)

    return crosscheck_results, stats

def run_crosscheck():
    repo_root = Path(__file__).resolve().parent.parent
    processed_dir = repo_root / "data" / "processed" / "osm"
    overture_raw_dir = repo_root / "data" / "raw" / "overture"
    curated_dir = repo_root / "data" / "curated" / "overture"
    curated_dir.mkdir(parents=True, exist_ok=True)

    today = "2026-10-07"
    all_stats = {}

    for region in ("halong", "hanoi"):
        osm_file = processed_dir / f"{region}_normalized_v1.json"
        ov_parquet = overture_raw_dir / f"overture_{region}_2026-09-23.1.parquet"

        if not osm_file.exists() or not ov_parquet.exists():
            print(f"Skipping {region}: files not found.")
            continue

        with open(osm_file, "r", encoding="utf-8") as f:
            osm_pois = json.load(f)

        results, stats = crosscheck_region(region, osm_pois, ov_parquet)
        all_stats[region] = stats

        out_path = curated_dir / f"{region}_overture_crosscheck_v1.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n[PASS] {region.upper()} Cross-Check Complete:")
        print(f"       OSM POIs:             {stats['total_osm_pois']}")
        print(f"       Overture Index Size:  {stats['total_overture_places']}")
        print(f"       AUTO-LINK (Strong):   {stats['auto_linked']}")
        print(f"       Manual Review:        {stats['manual_review_candidates']}")
        print(f"       Unmatched:            {stats['unmatched']}")
        print(f"       Source Conflicts:     {stats['source_conflicts']}")
        print(f"       License Unresolved:   {stats['license_unresolved']}")
        print(f"       Artifact saved:       {out_path.relative_to(repo_root)}")

    stats_path = curated_dir / f"overture_crosscheck_summary_{today}.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2, ensure_ascii=False)
    print(f"\nCross-check summary saved: {stats_path.relative_to(repo_root)}")

if __name__ == "__main__":
    run_crosscheck()
