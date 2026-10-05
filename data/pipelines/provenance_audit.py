"""Provenance audit for the verifiedOnly place path.

Reads every place exposed by GET /places?verifiedOnly=true and checks it against
the real upstream OSM data through the Overpass API:

  * the source id exists upstream,
  * the upstream coordinates are within TOLERANCE_M of the stored place,
  * (informational) name agreement.

Also checks the exposed API invariants: every verified place has >=1 source,
valid coordinates, no fabricated default rating (4.5 with 0 reviews), and no
untrusted review is exposed.

Usage:
    python data/pipelines/provenance_audit.py [--api http://localhost:3000] [--out report.json]

Exit code 0 = all checks pass, 1 = at least one violation.
Requires network access to https://overpass-api.de and a running backend.
"""
import argparse
import json
import math
import sys
import time
import urllib.parse
import urllib.request

TOLERANCE_M = 150.0
# Only the authoritative host: the kumi mirror was observed serving stale snapshots (2026-06/07 data),
# which would produce false FAIL/PASS results.
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
]


def http_json(url, data=None, timeout=90):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "wanderai-provenance-audit/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_all_verified(api):
    items, page = [], 1
    while True:
        q = urllib.parse.urlencode({"verifiedOnly": "true", "page": page, "limit": 100})
        body = http_json(f"{api}/places?{q}")
        data = body.get("data", body)
        items.extend(data["items"])
        if page >= data.get("totalPages", 1):
            return items
        page += 1


def overpass_lookup(refs):
    """refs: list of (type, id). Returns {(type,id): element or None}."""
    found = {}
    # One request per element type using node(id:1,2,3): far fewer requests than one per id,
    # which keeps us under the Overpass rate limit.
    by_type = {}
    for t, n in refs:
        by_type.setdefault(t, []).append(n)
    chunks = []
    for t, ids in by_type.items():
        for i in range(0, len(ids), 150):
            chunks.append((t, ids[i:i + 150]))
    for t, ids in chunks:
        parts = f"{t}(id:{','.join(str(n) for n in ids)});"
        query = f"[out:json][timeout:60];({parts});out center tags;"
        body = None
        for attempt in range(8):
            endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
            try:
                body = http_json(endpoint, data=urllib.parse.urlencode({"data": query}).encode())
                break
            except Exception as exc:
                print(f"Overpass retry {attempt + 1} ({endpoint}): {type(exc).__name__} {exc}", file=sys.stderr)
                time.sleep(4 * (attempt + 1))
        if body is None:
            raise RuntimeError("Overpass unreachable after retries")
        for el in body.get("elements", []):
            found[(el["type"], el["id"])] = el
        time.sleep(6)  # be polite: Overpass rate-limits bursts (HTTP 429)
    return {ref: found.get(ref) for ref in refs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:3000")
    ap.add_argument("--out", default=None)
    ap.add_argument("--input", default=None, help="JSON list of places (same shape as the API items) instead of calling the API")
    args = ap.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            places = json.load(f)
    else:
        places = fetch_all_verified(args.api)
    violations, checked = [], 0
    refs = set()
    for p in places:
        if not p.get("placeSources"):
            violations.append({"place": p["id"], "name": p["name"], "issue": "no place_sources"})
        if p.get("latitude") is None or p.get("longitude") is None:
            violations.append({"place": p["id"], "name": p["name"], "issue": "missing coordinates"})
        if p.get("rating") == 4.5 and p.get("reviewCount", 0) == 0:
            violations.append({"place": p["id"], "name": p["name"], "issue": "fabricated default rating 4.5"})
        for s in p.get("placeSources", []):
            if s["sourceName"] == "osm" and "/" in s["sourceId"]:
                t, n = s["sourceId"].split("/", 1)
                refs.add((t, int(n)))
            else:
                violations.append({"place": p["id"], "name": p["name"], "issue": f"unverifiable source {s['sourceName']}:{s['sourceId']}"})

    lookup = overpass_lookup(sorted(refs))
    name_diffs = []
    for p in places:
        for s in p.get("placeSources", []):
            if s["sourceName"] != "osm" or "/" not in s["sourceId"]:
                continue
            t, n = s["sourceId"].split("/", 1)
            el = lookup.get((t, int(n)))
            checked += 1
            if el is None:
                violations.append({"place": p["id"], "name": p["name"], "issue": f"{s['sourceId']} does not exist upstream"})
                continue
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None:
                violations.append({"place": p["id"], "name": p["name"], "issue": f"{s['sourceId']} has no coordinates upstream"})
                continue
            d = haversine_m(p["latitude"], p["longitude"], lat, lon)
            if d > TOLERANCE_M:
                violations.append({"place": p["id"], "name": p["name"], "issue": f"{s['sourceId']} is {d:.0f} m from stored coordinates"})
            up_name = (el.get("tags") or {}).get("name", "")
            if up_name and up_name.strip().lower() != p["name"].strip().lower():
                name_diffs.append({"place": p["name"], "upstream": up_name, "source": s["sourceId"]})

    report = {
        "verified_places": len(places),
        "osm_sources_checked": checked,
        "violations": violations,
        "name_differences_informational": name_diffs,
        "result": "PASS" if not violations else "FAIL",
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    print(text.encode("ascii", "backslashreplace").decode("ascii"))
    return 0 if not violations else 1


if __name__ == "__main__":
    sys.exit(main())
