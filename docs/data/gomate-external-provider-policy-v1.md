# GoMate External Provider & Data Source Governance Policy (v1)

**Effective Date:** 2026-10-07  
**Scope:** GoMate Research Dataset, Training Corpora, and Product Runtime  
**Status:** RATIFIED & LOCKED  

---

## 1. Executive Summary

This document establishes the official governance boundaries, licensing protocols, and usage restrictions for all external data providers across the GoMate engineering lifecycle. It strictly delineates between:
1. **Academic Research & Recommender Training Corpora** (strictly reproducible, open-license, multi-tenant audited).
2. **Product Runtime Enrichment** (future official API-driven dynamic features).
3. **UX & Product Benchmarking References** (conceptual UI references only; zero automated ingestion).

---

## 2. Canonical Source Matrix & Boundary Table

| Data Provider / Corpus | Primary Role | License / Access Status | Training & Dataset Freeze Permitted? | Runtime Integration Policy |
| :--- | :--- | :--- | :--- | :--- |
| **OpenStreetMap (OSM)** | **Canonical Ground Truth** for physical POIs, coordinates, taxonomy, and address metadata. | Open Database License (ODbL 1.0) | **YES** (Canonical primary authority for Freeze V1 and Freeze V2). | Permitted via local vector/geospatial database. Attribution required. |
| **Overture Maps Places** | **Secondary Provenance & Quality Cross-Check**. Never replaces canonical OSM Place ID. | Multi-License (`CDLA Permissive 2.0`, `Apache 2.0`, `CC0 1.0`). | **YES** (Auxiliary source linkage only when similarity $\ge 0.90$, distance $\le 50$m, approved license verified). | Permitted as secondary verification source. Zero fallback licensing permitted. |
| **Wikivoyage** | **RAG Narrative Knowledge Base**. Descriptive travel guides and cultural context. | Creative Commons Attribution-ShareAlike 3.0 (CC BY-SA 3.0). | **YES** (Pinned 464 chunks embedded via SentenceTransformers). | Permitted via vector similarity search in ai-service. Attribution required. |
| **ViHoRec 1.0.0** | **Collaborative Filtering RecSys Benchmark**. | Upstream Official Release; Non-commercial academic research. | **YES** (Locked local benchmark dataset for offline collaborative filtering evaluation). | Evaluation-only; not served in production customer runtime. |
| **Google Maps / Places** | **FUTURE Official Runtime Enrichment Only**. | Google Maps Platform Terms of Service. | **STRICTLY FORBIDDEN**. Zero scraping, zero review caching, zero rating ingestion into training corpus. | Official Google Places API runtime queries permitted in future phases for ephemeral display only (opening hours, live traffic). |
| **Tripadvisor** | **Product & UX Design Reference Only**. | Proprietary / Restricted. | **STRICTLY FORBIDDEN**. Zero automated scraping of POIs, reviews, ratings, or media assets. | Prohibited from automated backend ingestion or model training. |
| **VLSP 2018 (ABSA)** | **Aspect-Based Sentiment Analysis Benchmark**. | Data Use Agreement (DUA) Required. | **ACCESS_PENDING_DUA**. Ingestion forbidden until official academic DUA is signed. | Pending official university authorization. |

---

## 3. Strict Prohibitions

1. **Zero Google Scraping & Storage:**
   - Under no circumstances shall Google Maps or Google Places web pages or undocumented endpoints be scraped.
   - Google star ratings and reviews are strictly excluded from all offline recommender training corpora and RAG documents.
2. **Zero Tripadvisor Ingestion:**
   - No content from Tripadvisor shall be scraped, cached, or persisted into PostgreSQL or vector search.
3. **Zero Fabricated Ratings or Reviews:**
   - In GoMate research corpora (`dataset-freeze-v1` and `dataset-freeze-v2`), all OSM POIs maintain `rating = NULL` and `review_count = 0`.
   - Synthetic reviews or artificially inflated star ratings are strictly forbidden in production and evaluation databases.
4. **Strict Overture License Derivation:**
   - Overture Places records must have their license explicitly resolved from source records.
   - Any record with unresolved or unapproved license status is marked `LICENSE_UNRESOLVED` and barred from automatic database linking.

---

## 4. Audit & Verification

Compliance with this policy is enforced via automated CI regression tests in `tests/test_data02_contract.py` and `tests/test_data03_danang_freeze_v2.py`.
