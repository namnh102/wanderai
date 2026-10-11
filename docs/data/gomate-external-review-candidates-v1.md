# GoMate External Review Dataset Candidates & Provenance Matrix (V1)

**Document Version:** 1.0.0  
**Audit Snapshot Date:** 2026-10-07  
**Branch / Worktree:** `feature/data-foundation-w2`  
**Task Reference:** TASK DATA-01A (External Review Dataset Candidate Preparation)  
**Safety Protocol:** Zero downloads; zero scraping; candidate search and documentation only.  
**Licensing Invariant:** `UNKNOWN LICENSE => CANDIDATE / DO NOT INGEST`.

---

## 1. Executive Summary

This document establishes the evaluation matrix, licensing taxonomy, and acquisition protocols for external travel and hospitality review datasets. Following the strict data provenance governance of WanderAI (GoMate), external review datasets are classified into three operational categories:
1. `VERIFIED_RESTRICTED`: Legally verified for non-commercial academic graduation research (e.g., CC BY-NC 4.0 or signed Data User Agreement), but prohibited from commercial redistribution or public re-hosting.
2. `CANDIDATE / DO NOT INGEST`: Identified in literature or academic repositories with unverified, ambiguous, or proprietary upstream terms (e.g., third-party web scrapes, community dumps). Requires human legal clearance before any ETL.
3. `REJECTED`: Corpora outside the travel domain (e.g., student course evaluations, electronics reviews, toxic comments) or in violation of platform Terms of Service (e.g., unauthorized TripAdvisor/Booking.com web scraping).

---

## 2. External Review Dataset Candidate Matrix

The table below compiles candidate datasets identified in academic literature, research workshops, and open data repositories.

| dataset_name | publisher | official_url | language | review_text | rating | place_mapping | license | redistribution | research_use | status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :--- |
| **ViHoRec** | Minh Hoang Nguyen (arXiv:2607.12946) | `https://github.com/MinhNguyenDS/ViHoRec` | Vietnamese / Multilingual | **NO** (Interaction logs only) | **YES** (1.0 - 10.0 continuous) | Hotel Name & City (560 hotels) | CC BY-NC 4.0 (Data) / MIT (Code) | PERMITTED (With Attribution) | PERMITTED (Academic only) | **VERIFIED_RESTRICTED** |
| **VLSP 2018 ABSA (Hotel)** | VLSP Campaign Organizers (*J. Comput. Sci. & Cybern.*) | `https://vlsp.org.vn/resources-vlsp2018` | Vietnamese | **YES** (5,600 reviews) | **YES** (Aspect Polarity: Pos/Neg/Neu) | **NO** (Unlinked text sentences) | VLSP Data User Agreement (DUA) | **PROHIBITED** | PERMITTED (Upon signed DUA) | **VERIFIED_RESTRICTED** |
| **VLSP 2018 ABSA (Restaurant)** | VLSP Campaign Organizers | `https://vlsp.org.vn/resources-vlsp2018` | Vietnamese | **YES** (Food/dining reviews) | **YES** (Aspect Polarity) | **NO** (Unlinked text sentences) | VLSP Data User Agreement (DUA) | **PROHIBITED** | PERMITTED (Upon signed DUA) | **VERIFIED_RESTRICTED** |
| **ViMACSA** | UIT VNU-HCM (*Multimedia Systems*, 2025) | `https://arxiv.org/abs/2405.00543` | Vietnamese | **YES** (4,876 text-image pairs) | **YES** (14,618 aspect labels) | Hotel Name only (No GPS) | Academic Research Agreement | **RESTRICTED** | PERMITTED (By author approval) | **VERIFIED_RESTRICTED** |
| **CX Vietnamese Hotel Online Reviews** | Mendeley Data (DOI: 10.17632/dp8s59xnb7.1) | `https://data.mendeley.com/datasets/dp8s59xnb7/1` | Vietnamese | **YES** (20,551 customer reviews) | **YES** (1–5 Star Rating) | Hotel Name & 7 Major Cities | CC BY 4.0 (Mendeley deposit; upstream TripAdvisor scrape) | Permitted by Mendeley; Contested by TripAdvisor ToS | Unverified upstream terms | **CANDIDATE / DO NOT INGEST** |
| **visolex/VLSP2018-ABSA-Hotel** | Community Hugging Face Mirror | `https://huggingface.co/datasets/visolex/VLSP2018-ABSA-Hotel` | Vietnamese | **YES** (5,600 reviews) | **YES** (Aspect Polarity) | **NO** | Unknown / Claimed Open (Bypasses VLSP DUA) | Unauthorized Mirror | High legal risk | **CANDIDATE / DO NOT INGEST** |
| **VNBooking Reviews** | Kaggle Community Dump | `https://www.kaggle.com` | Vietnamese | **YES** (~5,000 hotel reviews) | **YES** (Rating score) | Partial Hotel Name | Unknown / Community Upload | Unknown | Unverified | **CANDIDATE / DO NOT INGEST** |
| **HotelRec** | Wang et al. (EMNLP 2019) | `https://github.com/nihalb/HotelRec` | English / Multilingual | **YES** (50M reviews, 140k hotels) | **YES** (1–5 Stars) | Hotel Name & Country | Academic Research License | Restricted | PERMITTED (Academic research) | **CANDIDATE / DO NOT INGEST** |
| **Yelp Open Dataset** | Yelp Inc. | `https://www.yelp.com/dataset` | English | **YES** (6.9M reviews) | **YES** (1–5 Stars) | Business UUID, Lat, Lon (US/CA) | Yelp Dataset License (Non-Commercial) | **PROHIBITED** | PERMITTED (Academic research) | **CANDIDATE / DO NOT INGEST** *(Non-Vietnam)* |
| **TripAdvisor Scrape (`hienbm/tripadvisor_vietnam`)** | Unofficial GitHub User | `https://github.com/hienbm/tripadvisor_vietnam` | Vietnamese | **YES** (~10,000 reviews) | **YES** | Hotel Name only | None / Unlicensed | Unauthorized | Unverified / Violates ToS | **REJECTED** |
| **UIT-VSFC** | UIT VNU-HCM (IEEE KSE 2018) | `https://github.com/uitnlp/vietnamese-students-feedback-corpus` | Vietnamese | **YES** (16,175 sentences) | **YES** (Sentiment) | **NONE** (University course feedback) | Academic Research Only | Prohibited | Educational only | **REJECTED** *(Not Travel Data)* |
| **VLSP 2016 Sentiment** | VLSP Workshop 2016 | `https://vlsp.org.vn` | Vietnamese | **YES** (5,000 reviews) | **YES** (Polarity) | **NONE** (Electronics: phones, laptops) | VLSP DUA | Prohibited | Academic only | **REJECTED** *(Consumer Tech)* |
| **AIVIVN 2019 Sentiment** | AIVIVN Challenge | `https://www.aivivn.com` | Vietnamese | **YES** (16,000 comments) | **YES** (Polarity) | **NONE** (E-commerce retail items) | Challenge ToS | Prohibited | Competition only | **REJECTED** *(E-Commerce)* |
| **ViHOS** | Phan et al. (EACL 2023) | `https://github.com/khoa-nt/ViHOS` | Vietnamese | **YES** (11,000+ spans) | **NO** (Hate/Toxicity) | **NONE** (Social media spans) | CC BY-NC-SA 4.0 | Non-Commercial | Academic only | **REJECTED** *(Toxic Content)* |

---

## 3. Detailed Candidate Dossiers

### 3.1. ViHoRec (Vietnamese Hotel Recommendation Benchmark)
- **Publication:** Minh Hoang Nguyen, *"ViHoRec: A Quality-Controlled Vietnamese Hotel Recommendation Dataset and Cold-Start Benchmark"*, arXiv:2607.12946.
- **Repository:** `https://github.com/MinhNguyenDS/ViHoRec`
- **Data Modality:** Tabular interaction records + hotel metadata. **Zero review text**.
- **Scope:** 17,911 interactions, 6,832 users, 560 hotels across 9 Vietnamese tourism cities (Đà Lạt, Nha Trang, Đà Nẵng, Vũng Tàu, Phan Thiết, Phú Quốc, Hội An, Huế, Quy Nhơn).
- **Licensing:** CC BY-NC 4.0 (Data) / MIT (Code).
- **Thesis Assessment:** Excellent for offline recommender benchmarks (NDCG@10, Recall@10, HitRate@10). Unusable for textual NLP or aspect-based sentiment tasks.

### 3.2. VLSP 2018 ABSA (Aspect-Based Sentiment Analysis — Hotel Subset)
- **Publication:** Huyen T. M. Nguyen et al., *"VLSP Shared Task: Sentiment Analysis"*, *Journal of Computer Science and Cybernetics*, 34(4), pp. 283–294, 2018. DOI: 10.15625/1813-9663/34/4/13158.
- **Official URL:** `https://vlsp.org.vn/resources-vlsp2018`
- **Data Modality:** Real Vietnamese hotel review texts with fine-grained aspect annotations across 13 aspect categories (`HOTEL#GENERAL`, `HOTEL#PRICE`, `HOTEL#COMFORT`, `HOTEL#CLEANLINESS`, `ROOMS#FACILITIES`, `SERVICE#GENERAL`, `LOCATION#GENERAL`, etc.) and 3 sentiment polarities (`Positive`, `Negative`, `Neutral`).
- **Volume:** 5,600 reviews (3,000 train, 2,000 dev, 600 test).
- **Licensing:** Requires sending a signed Data User Agreement (DUA) form to `vlsp.resources@gmail.com`. Strictly non-commercial research; redistribution prohibited.
- **Thesis Assessment:** Gold-standard benchmark for training GoMate review summarization and aspect sentiment extraction. Requires human supervisor signature on DUA.

### 3.3. ViMACSA (Multimodal Aspect-Category Sentiment Analysis)
- **Publication:** Quy Hoang Nguyen, Minh-Van Truong Nguyen, Kiet Van Nguyen, *"New Benchmark Dataset and Fine-Grained Cross-Modal Fusion Framework for Vietnamese Multimodal Aspect-Category Sentiment Analysis"*, *Multimedia Systems*, Springer, 2025. arXiv:2405.00543.
- **Volume:** 4,876 text-image pairs with 14,618 aspect annotations.
- **Licensing:** Academic Research Agreement from UIT NLP Group (`kietnv@uit.edu.vn`).
- **Thesis Assessment:** Valuable for future multimodal photo-review grounding. Requires author request.

### 3.4. CX Vietnamese Hotel Online Reviews (Mendeley Data)
- **Dataset Identification:** Mendeley Data, DOI: `10.17632/dp8s59xnb7.1`.
- **Publisher / Authors:** Academic researchers on Mendeley Data.
- **Volume:** 20,551 customer reviews from 3–5 star hotels across 7 Vietnamese cities.
- **Licensing Conflict:** Deposited under CC BY 4.0 on Mendeley Data, but raw content was scraped from TripAdvisor. Under TripAdvisor Terms of Use Section 4, automated scraping without consent is prohibited.
- **Compliance Ruling:** Classified as `CANDIDATE / DO NOT INGEST`. Must undergo faculty advisor review regarding fair-use doctrine before any local ingestion.

---

## 4. Separation of Travel vs Generic Sentiment Corpora

A core data governance rule for GoMate is the strict rejection of generic sentiment datasets falsely labeled as travel reviews:

| Dataset | Claimed Category | True Ground Truth | Verdict |
| :--- | :--- | :--- | :--- |
| **UIT-VSFC** | "Travel / Hotel reviews" | University student feedback on lecturers, curricula, and university classrooms (UIT VNU-HCM). Zero travel context. | **REJECTED** |
| **VLSP 2016** | "General sentiment" | Online reviews of smartphones, laptops, and computer hardware. | **REJECTED** |
| **AIVIVN 2019** | "Customer sentiment" | Shopee and Tiki e-commerce consumer goods comments. | **REJECTED** |
| **ViHOS** | "Social feedback" | Toxic, hateful, and offensive online social media text spans. | **REJECTED** |

---

## 5. Search Terms & Queries for Future Discovery

If additional candidate discovery is undertaken by researchers, the following structured search strings are recommended:

### Google Scholar / arXiv Queries
- `"Vietnamese" AND ("hotel reviews" OR "travel reviews") AND ("sentiment analysis" OR "recommender")`
- `"aspect-based sentiment analysis" AND "Vietnamese" AND "hospitality"`
- `"point of interest recommendation" AND "Vietnam" AND ("check-in" OR "trajectory")`

### Open Data & Hugging Face Queries
- `task:text-classification language:vi "hotel"`
- `task:tabular-recommendation "vietnam"`
- `dataset:tourism "vietnam"`

---

## 6. Academic (Thesis) vs. Commercial Deployment Boundary

1. **For Graduation Thesis (Đồ Án Tốt Nghiệp):**
   - ViHoRec (CC BY-NC 4.0) is 100% permitted for offline recommendation baselines.
   - VLSP 2018 ABSA is permitted for offline NLP evaluation once the human team submits the signed DUA.
2. **For Production Commercial SaaS:**
   - Neither CC BY-NC 4.0 nor VLSP DUA allows commercial hosting or runtime inference for paying customers.
   - Production reviews must be collected natively through authenticated GoMate mobile application users (`users -> reviews` relation in `schema.prisma`).
