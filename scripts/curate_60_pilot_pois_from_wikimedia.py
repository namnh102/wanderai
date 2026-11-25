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
DEFAULT_OUTPUT = REPO_ROOT / "data" / "enrichment" / "poi_enrichment_pilot_60_v1.json"

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

# Coordinate-verified curation & audit registry for the 9 Ha Long pilot POIs that lack direct
# OSM wikipedia/wikidata/wikimedia_commons tags. Each entry is gated by exact place_id,
# OSM source_id, and <= 50m Haversine distance against Freeze V2 before attaching any media/text.
HALONG_MISSING_PAIR_AUDIT_V1: dict[str, dict[str, Any]] = {
    "65562a67-84ff-44a0-990d-31917a2a9bd0": {
        "expected_name": "Tháp Đồng Hồ",
        "expected_osm_id": "way/674228542",
        "expected_lat": 20.9516105,
        "expected_lon": 107.0851999,
        "verification_status": "verified_media_and_article",
        "verification_note": (
            "Đã xác minh danh tính và tọa độ (sai lệch 0.0m so với OSM way/674228542 tại vòng xuyến "
            "giao Lê Thánh Tông - 25 Tháng 4 - Trần Hưng Đạo - phố Nhà Thờ - Tuệ Tĩnh); đối chiếu khớp "
            "bài viết Wikipedia 'Hạ Long (thành phố)' và ảnh Commons File:Cột Đồng Hồ - Vincom Hạ Long 2022.jpg."
        ),
        "description": (
            "Cột Đồng Hồ (Tháp Đồng Hồ) nằm tại khu vực trung tâm thành phố Hạ Long cạnh Vincom và "
            "tổ hợp Times Garden, là điểm mốc giao thông nối các tuyến đường Lê Thánh Tông, 25 Tháng 4, "
            "phố Nhà Thờ và phố Tuệ Tĩnh thuộc khu vực Bạch Đằng."
        ),
        "description_source_url": "https://vi.wikipedia.org/wiki/H%E1%BA%A1_Long_(th%C3%A0nh_ph%E1%BB%91)",
        "description_license": "CC BY-SA 4.0 (Wikipedia)",
        "commons_files": ["File:Cột Đồng Hồ - Vincom Hạ Long 2022.jpg"],
    },
    "34d89a3a-6272-4c3b-8c85-df92db91e3f6": {
        "expected_name": "Old Hon Gai Ferry Terminal",
        "expected_osm_id": "node/839480851",
        "expected_lat": 20.9580942,
        "expected_lon": 107.0672948,
        "verification_status": "verified_article_only_no_verified_image",
        "verification_note": (
            "Đã xác minh danh tính và tọa độ đầu bến phía Hòn Gai của Bến phà Bãi Cháy cũ (0.0m so với "
            "OSM node/839480851 bên bờ vịnh Cửa Lục, cách cầu Bãi Cháy 286m) và đối chiếu bài viết "
            "Wikipedia 'Hồng Gai'; chưa gắn ảnh vì File:Bãi Cháy.jpg trên Commons thiếu tọa độ GPS và "
            "chụp bờ phà phía Bãi Cháy đối diện thay vì đầu bến Hòn Gai."
        ),
        "description": (
            "Đầu bến phía Hòn Gai (Hồng Gai) của Bến phà Bãi Cháy từng là đầu mối giao thông quan trọng "
            "nối Hồng Gai với Bãi Cháy qua vịnh Cửa Lục, ngừng hoạt động năm 2007 sau khi được thay thế "
            "bằng cầu Bãi Cháy."
        ),
        "description_source_url": "https://vi.wikipedia.org/wiki/H%E1%BB%93ng_Gai",
        "description_license": "CC BY-SA 4.0 (Wikipedia)",
        "commons_files": [],
    },
    "8977e846-04cf-451c-9a2f-bb4c1ddf724f": {
        "expected_name": "Vinpearl Ferry Terminal",
        "expected_osm_id": "way/674647531",
        "expected_lat": 20.9473442,
        "expected_lon": 107.0246525,
        "verification_status": "unverified_secondary_media_and_article",
        "verification_note": (
            "Khớp tọa độ OSM way/674647531 trên đường Đỗ Sĩ Họa (Bãi Cháy), nhưng UNMATCHED trên Overture, "
            "không có mục Wikidata/Wikipedia riêng cho nhà ga bến tàu (Q111402972 cách 720m là khách sạn trên "
            "Đảo Rều; Q65165492 là Đảo Rều tại Cẩm Phả), và ảnh Commons gần nhất (File:越南 下龙湾码头 - panoramio.jpg, "
            "505m) chụp tòa khách sạn trên đảo thay vì nhà bến trên đất liền."
        ),
        "commons_files": [],
    },
    "e017ba7c-a9d6-40f2-8b6b-d2bcd4b12b2c": {
        "expected_name": "Thay Cave",
        "expected_osm_id": "node/4755942999",
        "expected_lat": 20.8682301,
        "expected_lon": 107.2011143,
        "verification_status": "unverified_secondary_media_and_article",
        "verification_note": (
            "Chỉ có stub OSM node/4755942999 (v1 năm 2017, natural=cave_entrance, gần Đảo Cống Đỏ); "
            "UNMATCHED trên Overture, không có mục Wikipedia/Wikidata (tránh nhầm với Hang Thầy/Chùa Thầy "
            "tại Quốc Oai, Hà Nội) và không có ảnh Commons định danh Hang Thầy (ảnh hang vô danh gần nhất "
            "cách 1.255m)."
        ),
        "commons_files": [],
    },
    "bfe45852-9a6d-4915-8b6b-c0b62c6f2b97": {
        "expected_name": "Senna Cruise",
        "expected_osm_id": "node/7168778356",
        "expected_lat": 20.9217133,
        "expected_lon": 106.9840436,
        "verification_status": "unverified_secondary_media_and_article",
        "verification_note": (
            "Điểm neo/check-in hãng tàu thương mại tại cảng Tuần Châu (OSM node/7168778356); UNMATCHED "
            "trên Overture, không có mục từ Wikipedia/Wikidata hoặc ảnh Commons của đơn vị này, và chính "
            "sách nguồn cấm thu thập/scrape website thương mại."
        ),
        "commons_files": [],
    },
    "d707d786-f31d-405c-a5ba-d1b4b500c7ab": {
        "expected_name": "Núi Sư Tử",
        "expected_osm_id": "node/13516003942",
        "expected_lat": 20.9825728,
        "expected_lon": 107.244281,
        "verification_status": "unverified_secondary_media_and_article",
        "verification_note": (
            "Node OSM node/13516003942 mới tạo 2026-02-01 (v1), tọa độ thực tế thuộc phường Quang Hanh "
            "(khu vực Cẩm Phả, cách trung tâm Hạ Long ~16km về phía Đông); UNMATCHED trên Overture và "
            "không có bất kỳ mục Wikipedia, Wikidata hay ảnh Commons nào trong bán kính 1,5km."
        ),
        "commons_files": [],
    },
    "749168c6-43e1-40bc-886a-5c39fe5b5c74": {
        "expected_name": "Nhạc nước",
        "expected_osm_id": "way/677038212",
        "expected_lat": 20.9500306,
        "expected_lon": 107.043202,
        "verification_status": "unverified_secondary_media_and_article",
        "verification_note": (
            "Tên chung 'Nhạc nước' (OSM way/677038212, amenity=fountain cạnh Quảng trường Mặt Trời, Bãi Cháy, "
            "khác với khu nhạc nước Tuần Châu cách ~7km); UNMATCHED trên Overture, thiếu tên định danh riêng "
            "và không có bài viết Wikipedia/Wikidata hay ảnh Commons chụp đài phun nước tại tọa độ này."
        ),
        "commons_files": [],
    },
    "317433c7-248e-4470-b4ee-fc7bee017aa3": {
        "expected_name": "Legend Pearl",
        "expected_osm_id": "way/683639731",
        "expected_lat": 20.9573534,
        "expected_lon": 106.9513676,
        "verification_status": "unverified_secondary_media_and_article",
        "verification_note": (
            "Cơ sở kinh doanh trang sức ngọc trai ven Quốc lộ 18 (OSM way/683639731; khớp Overture "
            "205b266d-9d1f-4a4b-90f4-58d5bac7dcba ở khoảng cách 13,2m nhưng lệch danh mục và không có mô tả/ảnh); "
            "không có bài Wikipedia/Wikidata, các ảnh trại ngọc trai trên Commons nằm ngoài vịnh cách >10km."
        ),
        "commons_files": [],
    },
    "205a8100-faa1-42f0-8fa7-8c46fd60bedc": {
        "expected_name": "Hòn Bằng",
        "expected_osm_id": "node/6304871405",
        "expected_lat": 20.9438694,
        "expected_lon": 107.1032461,
        "verification_status": "unverified_coordinate_landmass_conflict",
        "verification_note": (
            "Mâu thuẫn không gian: OSM node/6304871405 gắn nhãn place=island nhưng tọa độ (20.9438694, 107.1032461) "
            "nằm trên khu đất liền đô thị ven đường Trần Quốc Nghiễn - phố Hải Lộc (khu Hồng Hải, cạnh Cung Quy hoạch "
            "Quảng Ninh); UNMATCHED trên Overture và không có mục Wikipedia/Wikidata hay ảnh Commons xác thực."
        ),
        "commons_files": [],
    },
}


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
            _apply_verified_halong_audit_entry(rec, poi)
            if rec["images"] or rec["description"] or len(deferred) >= 5:
                chosen.append(rec)
            else:
                deferred.append(rec)

        while len(chosen) < per_city_target and deferred:
            chosen.append(deferred.pop(0))
        selected_pois.extend(chosen[:per_city_target])

    stats = _compute_summary(selected_pois)
    payload = {
        "schema_version": "GOMATE_POI_PILOT_60_ENRICHMENT_V1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_policy": "OSM_OVERTURE_WIKIPEDIA_WIKIDATA_COMMONS_ONLY_ZERO_SCRAPING",
        "no_fabricated_ratings_or_reviews": True,
        "summary": stats,
        "items": selected_pois,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return stats


def _compute_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_pilot_pois": len(items),
        "by_city": dict(Counter(p["destination_slug"] for p in items)),
        "with_cover_image": sum(1 for p in items if p.get("cover_image")),
        "with_description": sum(1 for p in items if p.get("description")),
        "with_opening_hours": sum(1 for p in items if p.get("opening_hours")),
        "total_images": sum(len(p.get("images") or []) for p in items),
        "tiers": dict(Counter(p["enrichment_tier"] for p in items)),
    }


def _apply_verified_halong_audit_entry(rec: dict[str, Any], freeze_poi: dict[str, Any]) -> bool:
    """Verify place_id, name, OSM source_id, and coordinates before attaching audited Ha Long data."""
    entry = HALONG_MISSING_PAIR_AUDIT_V1.get(rec["place_id"])
    if not entry:
        return False

    osm_ids = {
        src.get("source_id")
        for src in (freeze_poi.get("sources") or [])
        if src.get("source_name") == "osm" and src.get("source_id")
    }
    lat, lon = freeze_poi.get("latitude"), freeze_poi.get("longitude")
    if (
        freeze_poi.get("name") != entry["expected_name"]
        or entry["expected_osm_id"] not in osm_ids
        or lat is None
        or lon is None
    ):
        rec["verification_status"] = "identity_mismatch_skipped"
        rec["verification_note"] = "Không khớp tên hoặc source_id OSM trong Freeze V2; bỏ qua gắn dữ liệu."
        return False

    drift_m = _haversine_m(float(lat), float(lon), float(entry["expected_lat"]), float(entry["expected_lon"]))
    if drift_m > 50.0:
        rec["verification_status"] = "coordinate_drift_exceeded_skipped"
        rec["verification_note"] = f"Độ lệch tọa độ {drift_m:.1f}m vượt ngưỡng 50m; bỏ qua gắn dữ liệu."
        return False

    if entry.get("description") and not rec.get("description"):
        rec["description"] = entry["description"]
        rec["description_source_url"] = entry["description_source_url"]
        rec["description_license"] = entry["description_license"]

    if entry.get("commons_files") and not rec.get("images"):
        verified_imgs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for cf in entry["commons_files"]:
            info = _fetch_commons_file_info(cf)
            if info and info["url"] not in seen:
                seen.add(info["url"])
                verified_imgs.append(info)
        if verified_imgs:
            rec["cover_image"] = verified_imgs[0]["url"]
            rec["images"] = [im["url"] for im in verified_imgs[:4]]
            rec["image_attributions"] = verified_imgs[:4]

    has_img = bool(rec.get("cover_image"))
    has_desc = bool(rec.get("description"))
    rec["enrichment_tier"] = (
        "media_and_article"
        if (has_img and has_desc)
        else ("media_or_article" if (has_img or has_desc) else "osm_factual_only")
    )
    rec["verification_status"] = entry["verification_status"]
    rec["verification_note"] = entry["verification_note"]
    return has_img or has_desc


def enrich_halong_missing_in_place(freeze_v2_path: Path, pilot_path: Path) -> dict[str, Any]:
    """Process Tháp Đồng Hồ first, then remaining Ha Long POIs missing both cover_image & description."""
    fv2 = json.loads(freeze_v2_path.read_text(encoding="utf-8"))
    freeze_by_id = {x["place_id"]: x for x in fv2}
    payload = json.loads(pilot_path.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = payload["items"]

    candidates = [
        item
        for item in items
        if item.get("destination_slug") == "ha-long"
        and ((not item.get("cover_image") and not item.get("description")) or item["place_id"] in HALONG_MISSING_PAIR_AUDIT_V1)
        and item["place_id"] in HALONG_MISSING_PAIR_AUDIT_V1
    ]
    # Enforce starting with Tháp Đồng Hồ (65562a67-84ff-44a0-990d-31917a2a9bd0)
    candidates.sort(key=lambda x: 0 if x["place_id"] == "65562a67-84ff-44a0-990d-31917a2a9bd0" else 1)

    for item in candidates:
        fpoi = freeze_by_id.get(item["place_id"], {})
        _apply_verified_halong_audit_entry(item, fpoi)

    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["summary"] = _compute_summary(items)
    pilot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return payload["summary"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-v2", type=Path, default=DEFAULT_FREEZE_V2)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--enrich-halong-missing",
        action="store_true",
        help="Verify & enrich Ha Long pilot POIs missing both cover_image and description in-place.",
    )
    args = parser.parse_args()
    if args.enrich_halong_missing:
        stats = enrich_halong_missing_in_place(args.freeze_v2, args.output)
    else:
        stats = curate_pilot_60(args.freeze_v2, args.output)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
