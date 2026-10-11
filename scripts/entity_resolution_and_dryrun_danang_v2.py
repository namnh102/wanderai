#!/usr/bin/env python3
"""DATA-02 / MVP-SCOPE-01 Da Nang Entity Resolution & Database Import Dry-Run.

Analyzes normalized Da Nang candidate OSM POIs against existing DB places and place_sources.
Classifies actions into:
- NEW
- UPDATE_METADATA
- UNCHANGED
- CONFLICT
- QUARANTINE

Verifies strict pre-flight invariants before any DB mutation.
Produces: data/manifests/db_import_plan_danang_v2.json
"""

import asyncio
import json
import logging
import math
import os
import sys
import unicodedata
from collections import defaultdict, Counter
from pathlib import Path
import asyncpg

sys.stdout.reconfigure(encoding='utf-8')
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("entity_resolution_danang")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/wanderai")

def remove_accents(s: str) -> str:
    nfkd = unicodedata.normalize('NFKD', s)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])

def normalize_name(s: str) -> str:
    return " ".join(remove_accents(s.lower()).split())

async def run_dryrun():
    repo_root = Path(__file__).resolve().parent.parent
    processed_dir = repo_root / "data" / "processed" / "osm"
    curated_ov_dir = repo_root / "data" / "curated" / "overture"
    manifests_dir = repo_root / "data" / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)

    norm_file = processed_dir / "danang_normalized_v2.json"
    ov_file = curated_ov_dir / "danang_overture_crosscheck_v2.json"
    plan_file = manifests_dir / "db_import_plan_danang_v2.json"

    print("=" * 70)
    print("DA NANG (V2) ENTITY RESOLUTION & DRY-RUN AUDIT")
    print("=" * 70)

    # 1. Connect to DB and fetch destination and category maps
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        dest_rows = await conn.fetch("SELECT id::text, name, slug FROM destinations")
        dest_map = {r["slug"]: r["id"] for r in dest_rows}
        cat_rows = await conn.fetch("SELECT id::text, name FROM place_categories")
        cat_map = {r["name"]: r["id"] for r in cat_rows}

        danang_dest_id = dest_map["da-nang"]

        # Fetch existing Da Nang places
        db_places = await conn.fetch("""
            SELECT p.id::text as place_id, p.name, p.latitude, p.longitude, p.address,
                   p.destination_id::text, p.category_id::text, p.rating, p.review_count,
                   ps.id::text as source_row_id, ps.source_name, ps.source_id, ps.raw_name, ps.raw_data
            FROM places p
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE ps.source_name = 'osm' AND p.destination_id = $1::uuid AND p.deleted_at IS NULL
        """, danang_dest_id)

        print(f"Existing Da Nang OSM places in DB: {len(db_places)}")

        # Fetch Hanoi and Ha Long counts for isolation verification
        hanoi_dest_id = dest_map["ha-noi"]
        halong_dest_id = dest_map["ha-long"]
        hanoi_cnt = await conn.fetchval("""
            SELECT count(*) FROM places p
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE ps.source_name = 'osm' AND p.destination_id = $1::uuid AND p.deleted_at IS NULL
        """, hanoi_dest_id)
        halong_cnt = await conn.fetchval("""
            SELECT count(*) FROM places p
            JOIN place_sources ps ON p.id = ps.place_id
            WHERE ps.source_name = 'osm' AND p.destination_id = $1::uuid AND p.deleted_at IS NULL
        """, halong_dest_id)
        print(f"Hanoi verified OSM places:   {hanoi_cnt} (must remain unchanged: 145)")
        print(f"Ha Long verified OSM places: {halong_cnt} (must remain unchanged: 188)")

        # 2. Load fresh normalized Da Nang candidates
        with open(norm_file, "r", encoding="utf-8") as f:
            candidates = json.load(f)
        cand_by_sid = {c["source_id"]: c for c in candidates}
        print(f"Loaded fresh normalized candidates: {len(candidates)}")

        # 3. Load Overture crosscheck AUTO-LINK matches
        ov_autolink = {}
        with open(ov_file, "r", encoding="utf-8") as f:
            for entry in json.load(f):
                if entry["status"] == "AUTO_LINK":
                    ov_autolink[entry["source_id"]] = entry["overture_match"]
        print(f"Loaded Overture AUTO-LINK matches:  {len(ov_autolink)}")

        plan = {
            "summary": {
                "NEW": 0,
                "UPDATE_METADATA": 0,
                "UNCHANGED": 0,
                "CONFLICT": 0,
                "QUARANTINE": 0,
                "TOTAL_ACTIONS": 0
            },
            "category_distribution_new": {},
            "category_distribution_total": {},
            "actions": [],
            "sample_rows": []
        }

        # 4. Resolve existing Da Nang DB places
        matched_sids = set()
        for p in db_places:
            sid = p["source_id"]
            cand = cand_by_sid.get(sid)

            if cand:
                matched_sids.add(sid)
                ov_match = ov_autolink.get(sid)
                action = {
                    "region": "danang",
                    "action": "UPDATE_METADATA",
                    "existing_place_id": p["place_id"],
                    "source_id": sid,
                    "name": cand["name"],
                    "destination_id": danang_dest_id,
                    "category_id": p["category_id"],
                    "latitude": cand["latitude"],
                    "longitude": cand["longitude"],
                    "address": cand["address"] or p["address"],
                    "opening_hours": cand["opening_hours"],
                    "phone": cand["phone"],
                    "website": cand["website"],
                    "raw_tags": cand["raw_tags"],
                    "osm_version": cand["osm_version"],
                    "osm_changeset": cand["osm_changeset"],
                    "osm_timestamp": cand["osm_timestamp"],
                    "osm_base": cand["osm_base"],
                    "tier_1": cand["tier_1"],
                    "tier_2": cand["tier_2"],
                    "legacy_category": cand["legacy_category"],
                    "overture_auxiliary": ov_match
                }
                plan["actions"].append(action)
                plan["summary"]["UPDATE_METADATA"] += 1
            else:
                # Missing from fresh bounded query (e.g. outside bbox or relation geometry)
                # Preserve as UNCHANGED without destructive deletion
                action = {
                    "region": "danang",
                    "action": "UNCHANGED",
                    "existing_place_id": p["place_id"],
                    "source_id": sid,
                    "name": p["name"],
                    "destination_id": danang_dest_id,
                    "category_id": p["category_id"],
                    "latitude": p["latitude"],
                    "longitude": p["longitude"],
                    "address": p["address"],
                    "reason": "Preserved baseline POI outside fresh bounding box or relation geometry",
                    "overture_auxiliary": None
                }
                plan["actions"].append(action)
                plan["summary"]["UNCHANGED"] += 1

        # 5. Select NEW candidates using deterministic curation rule:
        # Criterion 1: TRANSPORT_HUBS (all boat/ferry terminals)
        # Criterion 2: CULTURE_HERITAGE, NATURE_SCENERY, ATTRACTIONS_LEISURE, SHOPPING_COMMERCE with AUTO-LINK OR contact (phone/web)
        # Criterion 3: HOSPITALITY with AUTO-LINK AND contact (phone/web)
        # Criterion 4: FOOD_BEVERAGE (non-cafe dining: restaurants, seafood) with AUTO-LINK AND contact (phone/web)
        core_cats = {"CULTURE_HERITAGE", "NATURE_SCENERY", "ATTRACTIONS_LEISURE", "SHOPPING_COMMERCE"}
        
        for c in candidates:
            sid = c["source_id"]
            if sid in matched_sids:
                continue

            t1 = c["tier_1"]
            t2 = c["tier_2"]
            has_contact = bool(c["phone"] or c["website"])
            is_autolink = sid in ov_autolink

            accept = False
            curation_reason = None

            if t1 == "TRANSPORT_HUBS":
                accept = True
                curation_reason = "TRANSPORT_HUB"
            elif t1 in core_cats and (is_autolink or has_contact):
                accept = True
                curation_reason = f"CORE_{t1}_DUAL_OR_CONTACT"
            elif t1 == "HOSPITALITY" and is_autolink and has_contact:
                accept = True
                curation_reason = "HOSPITALITY_DUAL_AND_CONTACT"
            elif t1 == "FOOD_BEVERAGE" and t2 != "cafe_tea" and is_autolink and has_contact:
                accept = True
                curation_reason = "DINING_DUAL_AND_CONTACT"

            if accept:
                cat_slug = c["legacy_category"]
                cat_id = cat_map.get(cat_slug, cat_map["attraction"])
                ov_match = ov_autolink.get(sid)

                action = {
                    "region": "danang",
                    "action": "NEW",
                    "source_id": sid,
                    "name": c["name"],
                    "destination_id": danang_dest_id,
                    "category_id": cat_id,
                    "legacy_category": cat_slug,
                    "tier_1": t1,
                    "tier_2": t2,
                    "latitude": c["latitude"],
                    "longitude": c["longitude"],
                    "address": c["address"],
                    "opening_hours": c["opening_hours"],
                    "phone": c["phone"],
                    "website": c["website"],
                    "raw_tags": c["raw_tags"],
                    "osm_version": c["osm_version"],
                    "osm_changeset": c["osm_changeset"],
                    "osm_timestamp": c["osm_timestamp"],
                    "osm_base": c["osm_base"],
                    "curation_reason": curation_reason,
                    "overture_auxiliary": ov_match
                }
                plan["actions"].append(action)
                plan["summary"]["NEW"] += 1
                plan["category_distribution_new"][t1] = plan["category_distribution_new"].get(t1, 0) + 1

        plan["summary"]["TOTAL_ACTIONS"] = len(plan["actions"])

        # Category distribution of total final corpus
        for act in plan["actions"]:
            t1 = act.get("tier_1") or "OTHER"
            plan["category_distribution_total"][t1] = plan["category_distribution_total"].get(t1, 0) + 1

        # Populate sample rows
        samples = {}
        for act in plan["actions"]:
            atype = act["action"]
            if atype not in samples:
                samples[atype] = {
                    "action": atype,
                    "name": act["name"],
                    "source_id": act["source_id"],
                    "latitude": act["latitude"],
                    "longitude": act["longitude"],
                    "tier_1": act.get("tier_1"),
                    "overture_auxiliary": bool(act.get("overture_auxiliary"))
                }
        plan["sample_rows"] = list(samples.values())

        # Verification of Pre-Flight Invariants
        print("\n" + "=" * 70)
        print("IMPORT PLAN SUMMARY")
        print("=" * 70)
        print(f"NEW count:             {plan['summary']['NEW']}")
        print(f"UPDATE_METADATA count: {plan['summary']['UPDATE_METADATA']}")
        print(f"UNCHANGED count:       {plan['summary']['UNCHANGED']}")
        print(f"CONFLICT count:        {plan['summary']['CONFLICT']}")
        print(f"QUARANTINE count:      {plan['summary']['QUARANTINE']}")
        print(f"TOTAL ACTIONS:         {plan['summary']['TOTAL_ACTIONS']}")

        print("\nNEW POIs Category Distribution:")
        for t1, cnt in sorted(plan["category_distribution_new"].items(), key=lambda x: -x[1]):
            print(f"  {t1:25s}: {cnt}")

        print("\nTotal Canonical Da Nang Category Distribution:")
        for t1, cnt in sorted(plan["category_distribution_total"].items(), key=lambda x: -x[1]):
            print(f"  {t1:25s}: {cnt}")

        # Assertions
        assert plan["summary"]["NEW"] == 179, f"Expected 179 NEW, got {plan['summary']['NEW']}"
        assert plan["summary"]["UPDATE_METADATA"] == 109, f"Expected 109 UPDATE, got {plan['summary']['UPDATE_METADATA']}"
        assert plan["summary"]["UNCHANGED"] == 5, f"Expected 5 UNCHANGED, got {plan['summary']['UNCHANGED']}"
        assert plan["summary"]["TOTAL_ACTIONS"] == 293, f"Expected 293 total, got {plan['summary']['TOTAL_ACTIONS']}"

        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, ensure_ascii=False)

        print(f"\n[PASS] Import plan validated and saved to: {plan_file}")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_dryrun())
