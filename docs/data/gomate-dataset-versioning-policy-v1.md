# GoMate Dataset Versioning & Freeze Policy (V1)

**Document Version:** 1.0.0  
**Snapshot Date:** 2026-10-07  
**Branch / Worktree:** `feature/data-foundation-w2`  
**Task Reference:** TASK DATA-01B (Dataset Versioning Policy)  
**Governance Invariant:** No dataset is frozen without the mandatory 11-field metadata record and SHA-256 checksum.

---

## 1. Executive Summary

This policy establishes the formal dataset versioning, metadata documentation, and cryptographic locking standards for WanderAI (GoMate). To satisfy university academic thesis standards, every dataset frozen in DATA-02 and subsequent milestones must record a complete provenance envelope preventing silent drift, undocumented changes, or unreproducible experimental baselines.

---

## 2. Mandatory 11-Field Dataset Provenance Schema

Every frozen dataset artifact must be accompanied by a version manifest containing the following 11 standardized attributes:

```yaml
# Schema Specification for GoMate Frozen Datasets
dataset_name: string                # Unique machine identifier (e.g., "osm_places_hanoi_halong")
version_release: string             # Semantic or date-based version (e.g., "2026.10.07-v1")
source_url: string                  # Official canonical upstream URL or API endpoint
retrieved_at_utc: string            # ISO-8601 timestamp in UTC (e.g., "2026-10-07T16:00:00Z")
license: string                     # Legal license name and version (e.g., "ODbL 1.0", "CC BY-NC 4.0")
row_count: integer                  # Exact count of records / rows in the frozen artifact
geographic_scope: string            # Destination or bounding box (e.g., "Hanoi + Ha Long Bay")
schema_version: string              # Schema contract version (e.g., "gomate-poi-schema-v1.0")
sha256: string                      # 64-character hexadecimal SHA-256 cryptographic hash
transformation_script_version: string # Git commit or version of script used to produce the data
parent_source_dataset: string       # Upstream parent dataset name or "None" if raw
```

---

## 3. Catalog of Currently Frozen Datasets (Snapshot 2026-10-07)

The table below catalogs the three foundational datasets currently frozen under this policy:

| Field | 1. OpenStreetMap Verified Places | 2. Wikivoyage Knowledge Corpus | 3. ViHoRec RecSys Benchmark |
| :--- | :--- | :--- | :--- |
| **`dataset_name`** | `osm_places_pilot_curated` | `wikivoyage_pilot_articles` | `vihorec_collaborative_benchmark` |
| **`version_release`** | `2026.10.04-pilot` | `2026.10.04-r1` | `2026.07-official-clean` |
| **`source_url`** | `https://overpass-api.de/api/interpreter` | `https://en.wikivoyage.org/w/api.php` | `https://github.com/MinhNguyenDS/ViHoRec` |
| **`retrieved_at_utc`** | `2026-10-04T01:00:00Z` | `2026-10-04T02:00:00Z` | `2026-10-01T18:24:00Z` |
| **`license`** | `ODbL 1.0` (c) OSM contributors | `CC BY-SA 3.0` (c) Wikivoyage authors | `CC BY-NC 4.0` (Data) / `MIT` (Code) |
| **`row_count`** | 357 verified places (in DB) | 464 chunks across 10 destinations | 17,911 interactions (560 hotels) |
| **`geographic_scope`** | Đà Nẵng, Hà Nội, Hội An, Huế, Nha Trang | 10 Pilot Destinations (Vietnam overview + 9 cities) | 9 Vietnamese Tourism Cities |
| **`schema_version`** | `gomate-poi-v1.0` | `gomate-rag-chunk-v1.0` | `vihorec-official-v1` |
| **`sha256`** | Derived from `places_osm_enrichment.json` | Pinned by MediaWiki Page & Revision IDs | `6461d3f3abc15a79615cd09c46950dee...` (`interactions.csv`) |
| **`transformation_script_version`** | `data/pipelines/osm/enrich_osm.py@3ef04c1` | `apps/ai-service/app/rag/ingestion.py@3ef04c1` | Raw clean upstream files |
| **`parent_source_dataset`** | `osm_vietnam_overpass_raw` | `en.wikivoyage.org` | `Booking/Traveloka/iVIVU OTAs` |

---

## 4. Wikivoyage Destination Revision Registry

To eliminate reliance on mutable web text, Wikivoyage articles are pinned to their official MediaWiki Page IDs and Revision IDs:

```json
[
  {
    "destination": "Hanoi (MVP Core)",
    "page_id": 14044,
    "revision_id": 5379087,
    "revision_timestamp": "2026-10-04T19:36:46Z",
    "retrieved_at_utc": "2026-10-07T16:06:00Z",
    "license": "CC BY-SA 3.0",
    "source_url": "https://en.wikivoyage.org/wiki/Hanoi"
  },
  {
    "destination": "Ha Long Bay (MVP Core)",
    "page_id": 13946,
    "revision_id": 5294720,
    "revision_timestamp": "2026-06-19T01:33:57Z",
    "retrieved_at_utc": "2026-10-07T16:06:00Z",
    "license": "CC BY-SA 3.0",
    "source_url": "https://en.wikivoyage.org/wiki/Ha_Long_Bay"
  },
  {
    "destination": "Vietnam (National Overview)",
    "page_id": 37987,
    "revision_id": 5379188,
    "revision_timestamp": "2026-10-05T01:34:21Z",
    "retrieved_at_utc": "2026-10-07T16:06:00Z",
    "license": "CC BY-SA 3.0",
    "source_url": "https://en.wikivoyage.org/wiki/Vietnam"
  },
  {
    "destination": "Đà Nẵng",
    "page_id": 8966,
    "revision_id": 5350223,
    "revision_timestamp": "2026-09-12T03:29:07Z",
    "retrieved_at_utc": "2026-10-07T16:06:00Z",
    "license": "CC BY-SA 3.0",
    "source_url": "https://en.wikivoyage.org/wiki/Da_Nang"
  },
  {
    "destination": "Hội An",
    "page_id": 14789,
    "revision_id": 5366081,
    "revision_timestamp": "2026-09-18T04:33:37Z",
    "retrieved_at_utc": "2026-10-07T16:06:00Z",
    "license": "CC BY-SA 3.0",
    "source_url": "https://en.wikivoyage.org/wiki/Hoi_An"
  },
  {
    "destination": "Huế",
    "page_id": 15179,
    "revision_id": 5351860,
    "revision_timestamp": "2026-09-12T04:11:28Z",
    "retrieved_at_utc": "2026-10-07T16:06:00Z",
    "license": "CC BY-SA 3.0",
    "source_url": "https://en.wikivoyage.org/wiki/Hue"
  },
  {
    "destination": "Nha Trang",
    "page_id": 24530,
    "revision_id": 5354304,
    "revision_timestamp": "2026-09-12T05:16:24Z",
    "retrieved_at_utc": "2026-10-07T16:06:00Z",
    "license": "CC BY-SA 3.0",
    "source_url": "https://en.wikivoyage.org/wiki/Nha_Trang"
  },
  {
    "destination": "Đà Lạt",
    "page_id": 8893,
    "revision_id": 5347938,
    "revision_timestamp": "2026-09-12T01:19:42Z",
    "retrieved_at_utc": "2026-10-07T16:06:00Z",
    "license": "CC BY-SA 3.0",
    "source_url": "https://en.wikivoyage.org/wiki/Da_Lat"
  },
  {
    "destination": "Ninh Bình",
    "page_id": 24641,
    "revision_id": 5340950,
    "revision_timestamp": "2026-09-02T11:48:02Z",
    "retrieved_at_utc": "2026-10-07T16:06:00Z",
    "license": "CC BY-SA 3.0",
    "source_url": "https://en.wikivoyage.org/wiki/Ninh_Binh"
  },
  {
    "destination": "Phú Quốc",
    "page_id": 27550,
    "revision_id": 5369656,
    "revision_timestamp": "2026-09-22T12:08:03Z",
    "retrieved_at_utc": "2026-10-07T16:06:00Z",
    "license": "CC BY-SA 3.0",
    "source_url": "https://en.wikivoyage.org/wiki/Phu_Quoc"
  }
]
```

---

## 5. Verification Commands & Checksum Enforcement

To verify local dataset integrity prior to running model benchmarks or ETL stages:

```bash
# Verify ViHoRec CSV files
python -c "
import hashlib, os
files = {
    'hotels.csv': '64d4108855d1eec303253bcfae71596a8abc26733b7fade0dd33b9425b976b16',
    'interactions.csv': '6461d3f3abc15a79615cd09c46950dee4750575b951c4471a98b5c11fe40feeb',
    'train.csv': '781a3b99e5a020179e8f1c427c2acf858d1035385040114f88e76ab1320c915e',
    'val.csv': 'dcaeba814337360e1c483be1e3d61201ecbfb587555938114ae907bf8a15b948',
    'test.csv': 'eb2d913269c597d986e242b65c53f7067f765c68915005054fae99426e97afbc',
    'users.csv': '02926a6e666c7fcc23ae40733bbd1fe0b4565a25001ed3d85c9f14308ad6fbb3',
}
for fn, h in files.items():
    fp = os.path.join('data/restricted/vihorec', fn)
    with open(fp, 'rb') as f:
        curr = hashlib.sha256(f.read()).hexdigest()
    assert curr == h, f'Checksum mismatch in {fn}!'
print('All ViHoRec checksums verified PASS.')
"
```
