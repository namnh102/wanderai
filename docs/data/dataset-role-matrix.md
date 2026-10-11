# WanderAI Dataset Role & Architectural Mapping Matrix

**Document Version:** 1.0.0  
**Audit Date:** 2026-10-01  
**Auditor:** Technical Lead & AI Engineer (Antigravity)  
**Task Reference:** TASK 06.3 — Dataset Acquisition & Access Clearance  
**Governance:** Strict domain segregation to prevent data contamination across AI subsystems.

---

## 1. Architectural Dataset Role Matrix

The following matrix formally defines the single authorized primary role and capability boundaries for every external dataset integrated or evaluated in WanderAI:

| Dataset | Primary Role | Text Review | Sentiment Labels | Aspect Labels | Recommendation | RAG | License / Access Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **OpenStreetMap (OSM)** | **Places / GIS** (Canonical Place Registry) | NO | NO | NO | Feature Input | Metadata Context | **ODbL 1.0**<br>(Public / Open Data) |
| **Wikivoyage** | **RAG Knowledge Base** (Travel Guides & Etiquette) | NO | NO | NO | NO | **PRIMARY** | **CC BY-SA 3.0**<br>(Open / Attribution Required) |
| **Wikipedia (Vietnam)** | **RAG Knowledge Base** (Heritage & Geography) | NO | NO | NO | NO | **SECONDARY** | **CC BY-SA 3.0 / 4.0**<br>(Open / Attribution Required) |
| **ViHoRec** | **Recommendation Engine** (Cold-Start & Ranking) | NO | NO | NO | **PRIMARY** | NO | **CC BY-NC 4.0 (Data) / MIT (Code)**<br>(Academic Non-Commercial Only) |
| **VLSP 2018 ABSA (Hotel)** | **Review Intelligence** (Aspect-Based Sentiment) | **YES** | **YES** | **YES** | NO | NO | **VLSP Academic DUA**<br>(Signed Request Required) |
| **ViMACSA** | **Advanced Multimodal Review AI** (Text + Images) | **YES** | **YES** | **YES** | NO | NO | **Academic Research Agreement**<br>(Author Request Required) |
| *WanderAI Native User Reviews* | **Production Review Service** (Real App Users) | **YES** | Inferred | Inferred | Post-MVP Signals | Context | **WanderAI Proprietary Terms**<br>(First-Party Authenticated Data) |

---

## 2. Conceptual Classification Breakdown

### 1. OpenStreetMap (OSM) → Places & Geographic Foundation
* **Assigned Layer:** Relational PostGIS Database (`destinations`, `places`, `place_sources`).
* **Role:** Serves as the ground truth source for geographic coordinates, bounding boxes, categories (`amenity`, `tourism`, `historic`), opening hours, and contact details.
* **Non-Permitted Role:** Does NOT provide qualitative traveler sentiment, subjective star ratings, or user reviews.

### 2. Wikivoyage & Wikipedia → Retrieval-Augmented Generation (RAG)
* **Assigned Layer:** Vector Store (`embeddings` table via `pgvector` in PostgreSQL).
* **Role:** Supplies rich unstructured descriptive knowledge regarding cultural customs, regional cuisine, transit advice, seasonal weather warnings, and history to Wandy (AI Travel Assistant).
* **Non-Permitted Role:** Does NOT serve as individual user ratings or recommendation interaction logs.

### 3. ViHoRec → Recommendation & Personalization Engine
* **Assigned Layer:** Offline Recommendation Pipeline (`apps/ai-service/recommendation/`).
* **Role:** Powers collaborative filtering baselines (BPR-MF, ItemKNN, Neural Matrix Factorization) to solve the hospitality cold-start recommendation problem across 560 Vietnamese hotels.
* **Non-Permitted Role:** Strictly forbidden from being used as a text NLP sentiment or aspect extraction benchmark, as released files contain no review sentences.

### 4. VLSP 2018 ABSA (Hotel Subset) → Review Intelligence & Aspect Extraction
* **Assigned Layer:** Review AI Service (`apps/ai-service/sentiment/` - TASK 07).
* **Role:** Provides 5,600 human-annotated Vietnamese hotel review sentences with 13 aspect categories and polarities (Positive, Negative, Neutral). Used as the gold standard for fine-tuning aspect extraction models.
* **Non-Permitted Role:** Strictly forbidden from being committed to public Git repositories or repurposed for commercial SaaS marketing without explicit VLSP licensing.

### 5. ViMACSA → Advanced Multimodal Review AI
* **Assigned Layer:** Future Multimodal Travel Media Feed.
* **Role:** Validates visual claims against review sentiment (e.g., matching text complaints about room quality with photographic evidence).
* **Non-Permitted Role:** Excluded from the initial text-only baseline; reserved for multimodal expansion.

---

## 3. Disallowed Cross-Contaminations

1. **No Fake Review Generation:**
   LLMs must never synthesize artificial customer reviews to populate the database.
2. **No Misattributed Non-Travel Data:**
   Academic datasets from education (UIT-VSFC) or consumer electronics (VLSP 2016) must never be re-labeled as travel or hotel data.
3. **No Unlicensed Scrapes in Production:**
   TripAdvisor or OTA scraping dumps with unverified provenance are permanently barred from the WanderAI repository and databases.
