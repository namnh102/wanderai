# RAG Travel Knowledge Source Candidates & Provenance Specification

**Document Version:** 1.0.0  
**Audit Date:** 2026-10-01  
**Auditor:** Technical Lead & AI Engineer (Antigravity)  
**Task Reference:** TASK 06.2 — Optional Second Track: RAG Preparation  
**System Target:** WanderAI Retrieval-Augmented Generation (FastAPI AI Service & Travel Agent)

---

## 1. Objective & Legal Boundaries

Retrieval-Augmented Generation (RAG) grounds the WanderAI AI Travel Agent (Wandy) in factual, cultural, geographic, and practical travel context across Vietnam. 

### Mandatory Legal & Quality Principles
1. **Strict Copyright Compliance:** DO NOT ingest copyrighted commercial travel guidebooks (e.g., Lonely Planet, Rough Guides, Michelin Guide) without explicit written licenses.
2. **Open & Official Provenance:** Ingest only sources that are:
   - Released under permissible open documentation licenses (e.g., CC BY-SA, ODbL).
   - Official public tourism information published by governmental bodies for informational public use.
   - Structured open geographic data (OpenStreetMap).
3. **Traceability:** Every ingested chunk in the future vector store (`pgvector` via `embeddings` table) must store its origin `source_url`, `license`, `retrieved_at`, and `provenance_id`.

---

## 2. Open Knowledge Source Candidates

| Source | Knowledge Scope | Language | License / Rights | Legal Classification | Suitability for RAG |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Wikivoyage (Vietnam Portal & Sub-pages)** | Comprehensive travel itineraries, culture, etiquette, climate, transport, safety, regional cuisine | English & Vietnamese | **CC BY-SA 3.0** / GFDL | **VERIFIED_OPEN** | **Highest Priority** (Structured, factual, free for adaptation with attribution) |
| **Wikipedia (Vietnam Geography, Heritage & Culture)** | UNESCO heritage sites, historical monuments, provincial geography, cultural festivals | Vietnamese & English | **CC BY-SA 3.0 / 4.0** | **VERIFIED_OPEN** | **High Priority** (Deep factual grounding for POIs and destinations) |
| **OpenStreetMap Descriptive & POI Metadata** | Verified tourism POIs, opening hours, wheelchair accessibility, cuisine types, addresses | Multilingual (Tags) | **ODbL 1.0** (Open Database License) | **VERIFIED_OPEN** | **High Priority** (Already integrated in `places` / PostGIS) |
| **Vietnam National Authority of Tourism (vietnam.travel)** | Official national destination guides, cultural events calendar, travel advisories | English & Vietnamese | Official Public Domain / Informational Use | **VERIFIED_RESTRICTED** | **Medium Priority** (Fair use / factual extraction only; no wholesale content scraping) |
| **Provincial Tourism Portals (e.g., Danang FantastiCity, Hanoi Tourism)** | Local festival schedules, official emergency contacts, heritage walking routes | Vietnamese | Public Informational | **VERIFIED_RESTRICTED** | **Medium Priority** (Contact/emergency metadata extraction) |

---

## 3. Deep Dive into Primary RAG Candidates

### Candidate 1: Wikivoyage (Vietnam Project)
* **Official URL:** `https://en.wikivoyage.org/wiki/Vietnam` / `https://vi.wikivoyage.org/`
* **License:** Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0).
* **Coverage:**
  * Regions: Northern Vietnam, Central Vietnam, Southern Vietnam, Northwest, Northeast, Red River Delta, Central Highlands, Mekong Delta.
  * Cities & Towns: Hanoi, Ho Chi Minh City, Da Nang, Hoi An, Hue, Nha Trang, Da Lat, Sa Pa, Ha Long, Ninh Binh, Phu Quoc, Phong Nha, Quy Nhon, Can Tho.
  * Practical Information: Visa requirements, currency (VND) handling, tipping customs, SIM cards, safety warnings (taxi scams, crosswalk etiquette), health/vaccinations.
* **Ingestion Strategy:**
  * Wikivoyage XML Dumps (regularly published by Wikimedia Foundation) or MediaWiki API.
  * Semantic chunking by section (`== Understand ==`, `== Get in ==`, `== See ==`, `== Do ==`, `== Eat ==`, `== Drink ==`, `== Sleep ==`, `== Stay safe ==`).
* **Compliance Note:** Responses synthesizing Wikivoyage data must acknowledge Wikivoyage contributors under CC BY-SA 3.0.

### Candidate 2: Wikipedia (Heritage & Tourism Articles)
* **Official URL:** `https://vi.wikipedia.org/wiki/Du_lịch_Việt_Nam` and specific landmark articles.
* **License:** CC BY-SA 3.0 / 4.0.
* **Coverage:**
  * 8 UNESCO World Heritage Sites in Vietnam (Ha Long Bay, Phong Nha-Ke Bang, Trang An, Hue Monuments, Hoi An Ancient Town, My Son Sanctuary, Imperial Citadel of Thang Long, Ho Dynasty Citadel).
  * Intangible cultural heritages (Ca tru, Quan ho, Nha nhac, Bai choi).
  * National parks (Cat Tien, Ba Be, Cuc Phuong, Bach Ma).
* **Ingestion Strategy:** Target specific curated lists of national heritage sites and natural attractions to provide rich context without crawling irrelevant general articles.

### Candidate 3: OpenStreetMap Tourism Tags (ODbL 1.0)
* **Source:** WanderAI Canonical Places Database (`places` table seeded from OSM Overpass API in Task 06).
* **Content:**
  * Coordinates, category, tags (`cuisine`, `opening_hours`, `wheelchair`, `contact:website`, `wikipedia`, `wikidata`).
* **Ingestion Strategy:**
  * Automated template synthesis into natural language knowledge chunks:  
    *Example:* `"Bảo tàng Chứng tích Chiến tranh nằm tại Quận 3, TP. Hồ Chí Minh. Giờ mở cửa: 07:30 - 17:30. Thể loại: Bảo tàng lịch sử/du lịch."`
  * Embedded directly into pgvector for nearest-neighbor semantic search.

---

## 4. Ingestion Architecture & Chunking Guidelines

When RAG pipeline implementation begins in future tasks:

1. **Deterministic Document Parsing:**
   * Markdown/MediaWiki AST parser preserving headings, lists, and tables.
   * Chunk size target: 300–600 tokens with 50-token overlap.
2. **Metadata Envelope for Every Chunk:**
   ```json
   {
     "chunk_id": "wv-danang-eat-01",
     "source_name": "Wikivoyage",
     "source_url": "https://en.wikivoyage.org/wiki/Da_Nang",
     "license": "CC BY-SA 3.0",
     "destination_id": "danang-uuid",
     "topic": "culinary",
     "language": "en",
     "content": "Da Nang is famous for Mi Quang (turmeric noodles) and Banh xeo..."
   }
   ```
3. **Embedding Model Compatibility:**
   * Vietnamese-capable multilingual embeddings: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` or `bkai-foundation-models/vietnamese-bi-encoder`.
4. **Vector Storage:**
   * PostgreSQL `pgvector` with HNSW cosine distance indexing (`vector_cosine_ops`).

---

## 5. Summary & Next Steps

* Task 06.2 establishes that **Wikivoyage** + **Wikipedia** + **OpenStreetMap** represent the cleanest, fully legal open knowledge base for WanderAI's RAG system.
* No unauthorized commercial travel guides will be ingested.
* Actual RAG ingestion and vector indexing will be executed during the dedicated RAG Milestone.
