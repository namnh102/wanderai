#!/usr/bin/env python3
"""Curate grounded, license-verified Product Pilot Enrichment for 60 Core V2 POIs.

Sources (strictly $0 / open / non-fabricated):
1. Frozen Freeze V2 OSM + Overture attributes (`data/curated/gomate_places_freeze_v2.json`, read-only).
2. Official Wikimedia REST & MediaWiki APIs (`vi.wikipedia.org`, `en.wikipedia.org`,
   `www.wikidata.org`, `commons.wikimedia.org`) for:
   - Grounded encyclopedia summary extract (`CC BY-SA 4.0` + canonical URL)
   - License-verified Commons image URLs (`imageinfo` `extmetadata` checked for CC/PD licenses)

Never touches W07 evaluation files, never uses paid APIs, never fabricates ratings or reviews.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FREEZE_V2 = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "curated" / "poi_enrichment_pilot_60_v1.json"

USER_AGENT = "GoMateTravelResearchBot/1.0 (https://github.com/namnh102/wanderai; academic-project)"

CATEGORY_PRIORITY = {
    "attraction": 10,
    "culture": 10,
    "museum": 10,
    "beach": 9,
    "temple": 9,
    "nature": 8,
    "park": 8,
    "market": 7,
    "cafe": 4,
    "restaurant": 4,
    "hotel": 3,
    "nightlife": 3,
    "entertainment": 5,
}

ALLOWED_IMAGE_LICENSES = (
    "cc",
    "public domain",
    "pd",
    "gfdl",
    "fal",
    "bsd",
    "mit",
    "ogl",
)


def _strip_html(raw: str | None) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(raw))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _http_get_json(url: str, *, timeout: float = 5.0) -> dict[str, Any] | None:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _extract_tags(place: dict[str, Any]) -> dict[str, str]:
    tags: dict[str, str] = {}
    for src in place.get("sources", []):
        if src.get("source_name") != "osm":
            continue
        raw = src.get("raw_data") or {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, str) and v.strip():
                    tags[k] = v.strip()
            nested = raw.get("tags") or {}
            if isinstance(nested, dict):
                for k, v in nested.items():
                    if isinstance(v, str) and v.strip():
                        tags[k] = v.strip()
    return tags


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _norm_tokens(text: str) -> set[str]:
    low = re.sub(r"[^\w\s]", " ", (text or "").lower())
    stop = {"tại", "ở", "và", "the", "of", "in", "hotel", "khách", "sạn", "nhà", "hàng", "công", "ty"}
    return {t for t in low.split() if len(t) >= 2 and t not in stop}


def _name_matches(a: str, b: str) -> bool:
    ta, tb = _norm_tokens(a), _norm_tokens(b)
    if not ta or not tb:
        return False
    inter = ta & tb
    return len(inter) >= 2 or (len(inter) >= 1 and min(len(ta), len(tb)) == 1)


def _is_license_free(lic_name: str) -> bool:
    low = (lic_name or "").lower()
    if "fair use" in low or "non-free" in low or "noncommercial" in low or "nc" in re.findall(r"[a-z]+", low):
        return False
    return any(tok in low for tok in ALLOWED_IMAGE_LICENSES)


def _fetch_commons_file_info(file_title: str, *, width: int = 960) -> dict[str, Any] | None:
    clean_title = file_title.strip()
    if not clean_title.lower().startswith("file:"):
        clean_title = f"File:{clean_title}"
    url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json"
        f"&titles={quote(clean_title)}&prop=imageinfo"
        f"&iiprop=url|mime|extmetadata&iiurlwidth={width}"
    )
    data = _http_get_json(url)
    if not data:
        return None
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = (info.get("mime") or "").lower()
        if not mime.startswith("image/") or "svg" in mime or "tiff" in mime:
            continue
        meta = info.get("extmetadata") or {}
        lic = _strip_html((meta.get("LicenseShortName") or {}).get("value"))
        if not _is_license_free(lic):
            continue
        thumb_or_url = info.get("thumburl") or info.get("url")
        if not thumb_or_url:
            continue
        return {
            "url": thumb_or_url,
            "fullUrl": info.get("url"),
            "commonsPageUrl": info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{quote(clean_title)}",
            "license": lic or "Wikimedia Commons Free License",
            "artist": _strip_html((meta.get("Artist") or {}).get("value"))[:140] or None,
            "title": clean_title,
        }
    return None


def _commons_category_files(cat_title: str, *, limit: int = 3) -> list[str]:
    clean = cat_title.strip()
    if not clean.lower().startswith("category:"):
        clean = f"Category:{clean}"
    url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json"
        f"&list=categorymembers&cmtitle={quote(clean)}&cmtype=file&cmlimit={limit}"
    )
    data = _http_get_json(url)
    if not data:
        return []
    return [m["title"] for m in ((data.get("query") or {}).get("categorymembers") or []) if m.get("title")]


def _fetch_wiki_summary(lang_title: str) -> dict[str, Any] | None:
    if ":" in lang_title:
        lang, title = lang_title.split(":", 1)
    else:
        lang, title = "vi", lang_title
    lang = lang.strip().lower()
    if lang not in {"vi", "en"}:
        return None
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title.strip().replace(' ', '_'))}"
    data = _http_get_json(url)
    if not data or data.get("type") == "disambiguation":
        return None
    extract = (data.get("extract") or "").strip()
    if not extract:
        return None
    canon_url = ((data.get("content_urls") or {}).get("desktop") or {}).get("page")
    orig_img = ((data.get("originalimage") or {}).get("source")) or ""
    page_img = data.get("title")
    file_from_url = None
    if orig_img and "/commons/" in orig_img:
        file_from_url = orig_img.rsplit("/", 1)[-1]
    elif orig_img and "/wikipedia/" in orig_img:
        file_from_url = orig_img.rsplit("/", 1)[-1]
    return {
        "lang": lang,
        "title": page_img,
        "extract": extract,
        "source_url": canon_url,
        "candidate_file": file_from_url,
    }


def _fetch_wikidata_entity(qid: str) -> dict[str, Any] | None:
    if not re.fullmatch(r"Q\d+", qid.strip()):
        return None
    data = _http_get_json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid.strip()}.json")
    entity = ((data or {}).get("entities") or {}).get(qid.strip())
    if not entity:
        return None
    claims = entity.get("claims") or {}
    p18_files: list[str] = []
    for cl in claims.get("P18", [])[:2]:
        val = ((cl.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(val, str) and val.strip():
            p18_files.append(val.strip())
    sitelinks = entity.get("sitelinks") or {}
    vi_title = (sitelinks.get("viwiki") or {}).get("title")
    en_title = (sitelinks.get("enwiki") or {}).get("title")
    desc_vi = ((entity.get("descriptions") or {}).get("vi") or {}).get("value")
    desc_en = ((entity.get("descriptions") or {}).get("en") or {}).get("value")
    return {
        "p18_files": p18_files,
        "vi_title": vi_title,
        "en_title": en_title,
        "desc_vi": desc_vi,
        "desc_en": desc_en,
    }


def _geosearch_wiki_or_commons(poi: dict[str, Any]) -> tuple[str | None, list[str]]:
    lat, lng = poi.get("latitude"), poi.get("longitude")
    if lat is None or lng is None:
        return None, []
    found_wiki = None
    for lang in ("vi", "en"):
        url = (
            f"https://{lang}.wikipedia.org/w/api.php?action=query&format=json"
            f"&list=geosearch&gscoord={lat}|{lng}&gsradius=500&gslimit=5"
        )
        data = _http_get_json(url)
        for item in ((data or {}).get("query") or {}).get("geosearch") or []:
            if _name_matches(poi["name"], item.get("title", "")):
                found_wiki = f"{lang}:{item['title']}"
                break
        if found_wiki:
            break

    commons_files: list[str] = []
    c_url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json"
        f"&list=geosearch&gsnamespace=6&gscoord={lat}|{lng}&gsradius=300&gslimit=6"
    )
    c_data = _http_get_json(c_url)
    for item in ((c_data or {}).get("query") or {}).get("geosearch") or []:
        title = item.get("title") or ""
        if title and (_name_matches(poi["name"], title) or (item.get("dist", 999) <= 120)):
            commons_files.append(title)
    return found_wiki, commons_files[:3]


def _score_candidate(poi: dict[str, Any]) -> tuple[int, int, str]:
    tags = _extract_tags(poi)
    cat_score = CATEGORY_PRIORITY.get(poi.get("category", ""), 1)
    media_signals = sum(
        3 if tags.get(k) else 0
        for k in ("image", "wikimedia_commons", "wikipedia", "wikidata")
    )
    attr_signals = sum(
        1 if tags.get(k) else 0
        for k in ("opening_hours", "website", "phone", "description", "description:en")
    )
    return (media_signals + cat_score + attr_signals, len(poi.get("sources", [])), poi["name"])


def curate_pilot_60(freeze_v2_path: Path, out_path: Path, *, per_city_target: int = 20) -> dict[str, Any]:
    fv2 = json.loads(freeze_v2_path.read_text(encoding="utf-8"))
    by_city: dict[str, list[dict[str, Any]]] = {"ha-noi": [], "da-nang": [], "ha-long": []}
    for x in fv2:
        if x.get("is_rec_a_core_v2") and x.get("destination_slug") in by_city:
            by_city[x["destination_slug"]].append(x)

    selected_pois: list[dict[str, Any]] = []
    for slug in ("ha-noi", "da-nang", "ha-long"):
        ranked = sorted(by_city[slug], key=_score_candidate, reverse=True)
        # Scan top candidates and pick exact 20 richest/verified per city (prefer those resolving Wiki/Commons media/articles)
        chosen: list[dict[str, Any]] = []
        deferred: list[dict[str, Any]] = []
        for idx, poi in enumerate(ranked[:30]):
            if len(chosen) >= per_city_target:
                break
            print(f"  [{slug}] {idx+1}/30: {poi['name']}", flush=True)
            tags = _extract_tags(poi)
            wiki_tag = tags.get("wikipedia")
            wikidata_tag = tags.get("wikidata")
            commons_tag = tags.get("wikimedia_commons")

            summary_info = None
            images_meta: list[dict[str, Any]] = []
            wiki_desc_short = tags.get("description:vi") or tags.get("description") or tags.get("description:en")
            desc_source_url = None
            desc_license = "ODbL 1.0 (OpenStreetMap)" if wiki_desc_short else None

            if not wiki_tag and not wikidata_tag and not commons_tag:
                geo_wiki, geo_files = _geosearch_wiki_or_commons(poi)
                if geo_wiki:
                    wiki_tag = geo_wiki
                for gf in geo_files[:2]:
                    info = _fetch_commons_file_info(gf)
                    if info:
                        images_meta.append(info)

            wd_info = _fetch_wikidata_entity(wikidata_tag) if wikidata_tag else None
            if not wiki_tag and wd_info:
                if wd_info.get("vi_title"):
                    wiki_tag = f"vi:{wd_info['vi_title']}"
                elif wd_info.get("en_title"):
                    wiki_tag = f"en:{wd_info['en_title']}"

            if wiki_tag:
                summary_info = _fetch_wiki_summary(wiki_tag)
                if summary_info:
                    wiki_desc_short = summary_info["extract"]
                    desc_source_url = summary_info.get("source_url")
                    desc_license = "CC BY-SA 4.0 (Wikipedia)"
                    if summary_info.get("candidate_file"):
                        info = _fetch_commons_file_info(summary_info["candidate_file"])
                        if info:
                            images_meta.append(info)

            if commons_tag:
                if commons_tag.lower().startswith("file:"):
                    info = _fetch_commons_file_info(commons_tag)
                    if info:
                        images_meta.append(info)
                else:
                    for cf in _commons_category_files(commons_tag, limit=3):
                        info = _fetch_commons_file_info(cf)
                        if info:
                            images_meta.append(info)

            if wd_info:
                for p18 in wd_info["p18_files"]:
                    info = _fetch_commons_file_info(p18)
                    if info:
                        images_meta.append(info)

            # Deduplicate image URLs keeping order, max 4
            seen_urls: set[str] = set()
            dedup_images: list[dict[str, Any]] = []
            for im in images_meta:
                if im["url"] not in seen_urls:
                    seen_urls.add(im["url"])
                    dedup_images.append(im)
            dedup_images = dedup_images[:4]

            if not wiki_desc_short and wd_info:
                fallback_wd = wd_info.get("desc_vi") or wd_info.get("desc_en")
                if fallback_wd:
                    wiki_desc_short = fallback_wd
                    desc_source_url = f"https://www.wikidata.org/wiki/{wikidata_tag}"
                    desc_license = "CC0 1.0 (Wikidata)"

            # Clean factual opening hours / website / phone from OSM tags
            hours = tags.get("opening_hours") or poi.get("opening_hours")
            website = tags.get("website") or tags.get("contact:website")
            phone = tags.get("phone") or tags.get("contact:phone")

            rec = {
                "place_id": poi["place_id"],
                "name": poi["name"],
                "destination_slug": slug,
                "category": poi["category"],
                "is_rec_a_core_v2": True,
                "description": wiki_desc_short,
                "description_source_url": desc_source_url,
                "description_license": desc_license,
                "cover_image": dedup_images[0]["url"] if dedup_images else None,
                "images": [im["url"] for im in dedup_images],
                "image_attributions": dedup_images,
                "opening_hours": hours,
                "website": website,
                "phone": phone,
                "osm_tags_used": {
                    k: tags[k]
                    for k in ("wikipedia", "wikidata", "wikimedia_commons", "image")
                    if tags.get(k)
                },
                "enrichment_tier": (
                    "media_and_article"
                    if dedup_images and wiki_desc_short
                    else ("media_or_article" if (dedup_images or wiki_desc_short) else "osm_factual_only")
                ),
            }
            if dedup_images or wiki_desc_short or len(deferred) >= 5:
                chosen.append(rec)
            else:
                deferred.append(rec)

        while len(chosen) < per_city_target and deferred:
            chosen.append(deferred.pop(0))
        selected_pois.extend(chosen[:per_city_target])

    stats = {
        "total_pilot_pois": len(selected_pois),
        "by_city": dict(Counter(p["destination_slug"] for p in selected_pois)),
        "with_cover_image": sum(1 for p in selected_pois if p["cover_image"]),
        "with_description": sum(1 for p in selected_pois if p["description"]),
        "with_opening_hours": sum(1 for p in selected_pois if p["opening_hours"]),
        "total_images": sum(len(p["images"]) for p in selected_pois),
        "tiers": dict(Counter(p["enrichment_tier"] for p in selected_pois)),
    }
    payload = {
        "schema_version": "GOMATE_POI_PILOT_60_ENRICHMENT_V1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_policy": "OSM_OVERTURE_WIKIPEDIA_WIKIDATA_COMMONS_ONLY_ZERO_SCRAPING",
        "no_fabricated_ratings_or_reviews": True,
        "summary": stats,
        "items": selected_pois,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-v2", type=Path, default=DEFAULT_FREEZE_V2)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    stats = curate_pilot_60(args.freeze_v2, args.output)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
