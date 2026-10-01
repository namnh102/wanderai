# RAG Travel Knowledge Source Candidates & Provenance Specification

**Document Version:** 2.0.0  
**Audit Date:** 2026-10-01  
**Auditor:** Technical Lead & AI Engineer (Antigravity)  
**Task Reference:** TASK 06.3 — RAG Source Verification  
**System Target:** WanderAI Retrieval-Augmented Generation (FastAPI AI Service & Travel Agent)

---

## 1. Objective & Governance Principles

Retrieval-Augmented Generation (RAG) grounds the WanderAI AI Travel Assistant (Wandy) in authentic, culturally accurate, and legally cleared travel knowledge across Vietnam.

### Mandatory Legal Boundaries:
1. **No Commercial Copyright Infringement:** Never scrape or ingest proprietary guidebooks (Lonely Planet, Rough Guides, Michelin) or copyrighted commercial travel blogs without written licensing.
2. **Distinct License Separation:** Never group Wikimedia or open projects under a vague generic label. Wikivoyage, Wikipedia, and OpenStreetMap operate under distinct, non-identical legal instruments with specific attribution and copyleft stipulations.
3. **Traceability:** Every retrieved vector chunk in PostgreSQL (`pgvector`) must record its immutable source URL, license identifier, attribution text, and ingestion timestamp.

---

## 2. In-Depth Legal & Retrieval Verification for Each Candidate

### Candidate 1: Wikivoyage (Vietnam Project & Provincial Guides)
* **Exact Source:** 
  * Portal: `https://en.wikivoyage.org/wiki/Vietnam` and `https://vi.wikivoyage.org/wiki/Việt_Nam`
  * Provincial/City Articles: Hanoi, Ho Chi Minh City, Da Nang, Hoi An, Hue, Nha Trang, Da Lat, Sa Pa, Ha Long, Ninh Binh, Phu Quoc, Phong Nha, Quy Nhon, Can Tho.
* **Exact License:** **Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0)** and **GNU Free Documentation License (GFDL)** unversioned.
* **Attribution Requirements:** **YES (MANDATORY)**. Must credit "Wikivoyage contributors" and provide a hyperlink to the original article and the CC BY-SA 3.0 license.
* **Derivative Works Allowed?** **YES**, provided that all derivative works or adaptations are distributed under the identical or compatible license (ShareAlike clause).
* **Redistribution Allowed?** **YES**, commercial and non-commercial redistribution is permitted with proper attribution and under ShareAlike.
* **Retrieval Method:** 
  * Official MediaWiki Action API (`action=query&prop=extracts|revisions&format=json`).
  * Wikimedia Enterprise / Static XML Dumps (`enwikivoyage-latest-pages-articles.xml.bz2`).
* **Storage Method:**
  * Raw XML/JSON dumps cached in gitignored `data/rag/raw/wikivoyage/`.
  * Chunked markdown documents parsed into 300–600 token segments stored in PostgreSQL `rag_documents` table with `source_type = 'wikivoyage'`, linked to 1536-dim or 768-dim embeddings in `pgvector`.

---

### Candidate 2: Wikipedia (Vietnamese Geography, UNESCO Heritage & Culture)
* **Exact Source:**
  * Vietnamese Wikipedia: `https://vi.wikipedia.org/wiki/Du_lịch_Việt_Nam`
  * Curated Articles: 8 UNESCO World Heritage Sites (Ha Long Bay, Phong Nha-Ke Bang, Trang An, Hue Monuments, Hoi An, My Son, Thang Long Citadel, Ho Dynasty Citadel), national parks, and cultural traditions.
* **Exact License:** **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)** (Updated across Wikimedia Foundation projects in June 2023; legacy contributions dual CC BY-SA 3.0).
* **Attribution Requirements:** **YES (MANDATORY)**. Must provide title, author/project ("Wikipedia contributors"), source URI, and CC BY-SA 4.0 license link.
* **Derivative Works Allowed?** **YES**, subject to the CC BY-SA 4.0 ShareAlike covenant.
* **Redistribution Allowed?** **YES**, permitted with attribution and ShareAlike.
* **Retrieval Method:**
  * Wikimedia REST API (`https://vi.wikipedia.org/api/rest_v1/page/summary/{title}`).
  * Targeted batch requests restricted to predefined lists of Vietnamese heritage sites.
* **Storage Method:**
  * Pre-rendered plain text and AST sections stored in `data/rag/raw/wikipedia/`.
  * Ingested into `rag_documents` with `source_type = 'wikipedia'`, tagged with `destination_id` foreign keys.

---

### Candidate 3: OpenStreetMap (OSM) Descriptive & POI Metadata
* **Exact Source:** 
  * OpenStreetMap contributors via Overpass API queries (`https://overpass-api.de/api/interpreter`).
  * Geofabrik Vietnam regional extracts (`vietnam-latest.osm.pbf`).
* **Exact License:** **Open Data Commons Open Database License (ODbL) 1.0** for the database; individual contents licensed under the **Database Contents License (DbCL) 1.0**. *(Notice: ODbL is a database license, NOT a Creative Commons copyright license).*
* **Attribution Requirements:** **YES (MANDATORY)**. Must credit "© OpenStreetMap contributors" with a link to `https://www.openstreetmap.org/copyright`.
* **Derivative Works Allowed?** **YES**, but if a "Derivative Database" is produced and publicly distributed, it must be made available under the ODbL.
* **Redistribution Allowed?** **YES**, permitted under ODbL terms.
* **Retrieval Method:** 
  * Overpass QL bounding box and tag filters (`[out:json]; node["tourism"](bbox);`).
  * Direct extraction from already ingested `places` and `place_sources` database tables.
* **Storage Method:**
  * Already persisted in WanderAI PostgreSQL database (`places` table with PostGIS geometry).
  * Natural-language POI descriptors dynamically synthesized from structured tags (`name`, `category`, `cuisine`, `opening_hours`, `wheelchair`) for embedding generation.

---

### Candidate 4: Official Tourism Sources (Vietnam National Authority of Tourism)
* **Exact Source:**
  * Vietnam National Authority of Tourism (VNAT) / Ministry of Culture, Sports and Tourism.
  * Official Portal: `https://vietnam.travel` / `https://vietnamtourism.gov.vn`
* **Exact License:** **Governmental Public Information / All Rights Reserved Copyright**.
  * Official notices state: *"© Vietnam National Authority of Tourism. All rights reserved."*
* **Attribution Requirements:** Mandatory institutional acknowledgment if quotes or summaries are referenced.
* **Derivative Works Allowed?** **NO**. No contractual right to produce or publish derivative commercial guides from wholesale text.
* **Redistribution Allowed?** **NO**. Wholesale mirroring, mass crawling, or public republication of editorial articles is strictly prohibited.
* **Retrieval Method:**
  * Strictly manual extraction of non-copyrightable factual data points only (e.g., official dates of public national holidays, Lunar New Year dates, official festival schedules).
  * Zero automated site scraping or text corpus ingestion.
* **Storage Method:**
  * Structured factual calendars recorded as seed JSON configuration (`database/seed/festivals.json`).
  * No raw proprietary editorial text stored in vector databases.

---

## 3. RAG Knowledge Source Summary Matrix

| Source | Legal Instrument | License Type | Derivative Works? | Redistribution? | RAG Role in WanderAI |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **Wikivoyage** | CC BY-SA 3.0 / GFDL | Open Documentation | YES (ShareAlike) | YES (Attributed) | **Core Narrative Knowledge** (Itineraries, customs, dining, safety) |
| **Wikipedia** | CC BY-SA 4.0 | Open Encyclopedia | YES (ShareAlike) | YES (Attributed) | **Factual Heritage & History** (UNESCO monuments, geography) |
| **OpenStreetMap** | ODbL 1.0 / DbCL 1.0 | Open Database | YES (ShareAlike DB) | YES (Attributed) | **Geographic Grounding** (Coordinates, hours, amenities) |
| **VNAT (vietnam.travel)** | Copyright (All Rights Reserved) | Proprietary Public Info | **NO** | **NO** | **Factual Reference Only** (Official dates, national events calendar) |

---

## 4. Next Implementation Steps for RAG Milestone

1. Develop a Wikimedia API crawler with rate-limiting and user-agent compliance.
2. Build an AST markdown chunker with metadata headers preserving article context.
3. Test embedding quality using `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
4. Ensure all responses delivered by Wandy include proper attribution footers:
   * *"Sources: Wikivoyage contributors (CC BY-SA 3.0), © OpenStreetMap contributors (ODbL)."*
