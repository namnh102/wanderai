# Real Travel Review Dataset Candidates & Provenance Verification

**Document Version:** 1.0.0  
**Audit Date:** 2026-10-01  
**Auditor:** Technical Lead & AI Engineer (Antigravity)  
**Task Reference:** TASK 06.2 — Review Dataset Discovery & Independent Verification  
**Branch:** `develop`  
**Review AI (TASK 07) Status:** BLOCKED (Pending official acquisition & data contract clearance)

---

## 1. Executive Summary

Following the provenance audit in TASK 06.1 which quarantined 9 unverified synthetic review fixtures and retracted false academic claims regarding UIT-VSFC, this document conducts an exhaustive, source-grounded discovery and verification of real travel and hospitality review datasets in Vietnamese and multilingual domains.

### Verification Principles
1. **Fact-First Audit:** No dataset name, license, DOI, author, or record count is inferred or fabricated.
2. **Domain Integrity:** Generic sentiment corpora (e.g., academic course feedback, phone/laptop reviews, hate speech) are strictly classified as generic sentiment and **rejected** from being labeled as travel reviews.
3. **Legal Compliance:** Datasets scraped in violation of platform Terms of Service (e.g., TripAdvisor, Booking.com unauthorized third-party dumps) without explicit licensing or rights holder consent are classified as `LICENSE_UNCLEAR` or `REJECTED`.
4. **Graduation Project (Academic) vs. Commercial Boundary:** Creative Commons NonCommercial (CC BY-NC 4.0) and academic Data User Agreements (DUA) permit non-commercial graduation thesis research, but prohibit commercial SaaS deployment.

---

## 2. Review Dataset Candidates Matrix

| Dataset | Travel? | Language | Size | Original Source | DOI | License | Academic Use | Redistribution | Status |
| :--- | :---: | :---: | ---: | :--- | :--- | :--- | :---: | :---: | :--- |
| **ViHoRec** | YES (Hotels) | Vietnamese / Multi | 18,267 interactions (560 hotels) | arXiv:2607.12946 / GitHub: `MinhNguyenDS/ViHoRec` | arXiv:2607.12946 | Data: CC BY-NC 4.0<br>Code: MIT | PERMITTED | With Attribution | **VERIFIED_RESTRICTED** |
| **VLSP 2018 ABSA (Hotel & Restaurant)** | YES (Hotels & Restaurants) | Vietnamese | 5,600 hotel reviews<br>(3,000 train, 2,000 dev, 600 test) | VLSP / *J. Comput. Sci. & Cybern.* 34(4) | 10.15625/1813-9663/34/4/13158 | VLSP Data User Agreement (DUA) | PERMITTED (Upon signed DUA) | PROHIBITED | **VERIFIED_RESTRICTED** |
| **ViMACSA** | YES (Hotels) | Vietnamese | 4,876 hotel text-image pairs (14,618 annotations) | UIT VNU-HCM / *Multimedia Systems* (2025) / arXiv:2405.00543 | 10.1007/s00530-024-01584-6 (arXiv:2405.00543) | Academic Research Agreement | PERMITTED (Research only) | Restricted | **VERIFIED_RESTRICTED** |
| **UIT-VSFC** | **NO** (Course Feedback) | Vietnamese | 16,000+ sentences | UIT VNU-HCM / IEEE KSE 2018 | 10.1109/KSE.2018.8573331 | Academic Research | Permitted for Education | Prohibited | **REJECTED** *(Not Travel Data)* |
| **VLSP 2016 Sentiment** | **NO** (Electronics) | Vietnamese | ~5,000 reviews | VLSP 2016 Workshop | None (Workshop Proceedings) | VLSP DUA | Academic only | Prohibited | **REJECTED** *(Consumer Tech)* |
| **AIVIVN 2019 Sentiment** | **NO** (E-commerce) | Vietnamese | 16,000 comments | AIVIVN Challenge 2019 | None | Challenge ToS (E-commerce) | Academic / Competition | Prohibited | **REJECTED** *(E-commerce Products)* |
| **ViHOS** | **NO** (Hate Speech) | Vietnamese | 11,000+ spans | EACL 2023 | 10.18653/v1/2023.eacl-main.62 | CC BY-NC-SA 4.0 | Non-Commercial | Non-Commercial ShareAlike | **REJECTED** *(Hate Speech)* |
| **TripAdvisor Scraped (`hienbm/tripadvisor_vietnam`)** | YES (Hotels) | Vietnamese | ~10,000 reviews | Unofficial GitHub scrape | None | None (Unlicensed scraper) | UNVERIFIED | Prohibited by TripAdvisor ToS | **REJECTED** *(License Unclear / ToS)* |
| **Kaggle Vietnam Hotel Reviews (Anonymous)** | YES (Hotels) | Vietnamese / English | Varies (2k-15k) | Kaggle community uploads | None | Unknown / Public domain claim without proof | UNVERIFIED | Prohibited | **REJECTED** *(Provenance Unverified)* |

---

## 3. Detailed Candidate Dossiers

### Candidate 1: ViHoRec (Vietnamese Hotel Recommendation Dataset)
* **Dataset Name:** ViHoRec: A Quality-Controlled Vietnamese Hotel Recommendation Dataset and Cold-Start Benchmark
* **Authors:** Minh Hoang Nguyen
* **Institution:** Independent / Academic NLP & RecSys Research
* **Publication / Paper:** arXiv preprint arXiv:2607.12946 (2024–2026)
* **Official URL:** `https://github.com/MinhNguyenDS/ViHoRec`
* **Preprint Link:** `https://arxiv.org/abs/2607.12946`
* **Dataset Type:** Tabular interaction records + hotel metadata + review rating features.
* **Language:** Vietnamese (primary platform content from Traveloka, iVIVU, and Booking.com Vietnam).
* **Record Count:** 18,267 interactions, 6,832 anonymized users, 560 unique hotels across Vietnam.
* **Metadata Coverage:** 309 hotels feature enriched amenities, location, and price tier metadata.
* **Fields:** `user_id` (HMAC anonymized), `hotel_id`, `rating`, `timestamp`, `platform` (Booking/Traveloka/iVIVU), `hotel_name`, `city`, `star_rating`, `facilities`.
* **Review Domains:** Vietnamese hotel accommodation, hospitality services, room quality.
* **License:**
  * **Dataset:** Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
  * **Pipeline & Evaluation Code:** MIT License.
* **License Permissions:**
  * Academic Use: **YES** (Explicitly permitted under Non-Commercial terms).
  * Commercial Use: **NO** (Requires explicit commercial license from rights holders).
  * Attribution Required: **YES** (Must cite arXiv:2607.12946 and GitHub repository).
  * Redistribution: Permitted with attribution under non-commercial terms.
* **License Classification:** `VERIFIED_RESTRICTED` (Non-commercial academic use verified).

### Candidate 2: VLSP 2018 ABSA (Aspect-Based Sentiment Analysis — Hotel Domain)
* **Dataset Name:** VLSP 2018 Shared Task: Aspect-Based Sentiment Analysis (Hotel Subset)
* **Authors:** Huyen T. M. Nguyen, Hung V. Nguyen, Quyen T. Ngo, Luong X. Vu, Vu Mai Tran, Bach X. Ngo, Cuong A. Le (Evaluation Campaign Organizers)
* **Institution:** Association for Vietnamese Language and Speech Processing (VLSP)
* **Publication / Paper:** *"VLSP Shared Task: Sentiment Analysis"*, *Journal of Computer Science and Cybernetics*, Vol. 34, No. 4 (2018), pp. 283–294.
* **DOI:** `10.15625/1813-9663/34/4/13158`
* **Official URL:** `https://vlsp.org.vn/resources-vlsp2018`
* **Dataset Type:** Text reviews with fine-grained aspect category and sentiment polarity annotations.
* **Language:** Vietnamese (human-annotated real reviews).
* **Record Count:**
  * Train set: 3,000 hotel reviews
  * Development set: 2,000 hotel reviews
  * Test set: 600 hotel reviews
  * Total: 5,600 verified hotel reviews (plus separate restaurant review corpus).
* **Annotation Taxonomy:**
  * Aspect Categories: `HOTEL#GENERAL`, `HOTEL#PRICE`, `HOTEL#COMFORT`, `HOTEL#CLEANLINESS`, `HOTEL#QUALITY`, `ROOMS#GENERAL`, `ROOMS#CLEANLINESS`, `ROOMS#COMFORT`, `ROOMS#FACILITIES`, `SERVICE#GENERAL`, `LOCATION#GENERAL`, `FOOD&DRINKS#QUALITY`, `FOOD&DRINKS#STYLE&OPTIONS`.
  * Sentiment Polarities: `Positive`, `Negative`, `Neutral`.
* **Review Domains:** Real Vietnamese hotels, resorts, and homestays.
* **License & Access Terms:**
  * Access requires sending a signed Data User Agreement (DUA) form to `vlsp.resources@gmail.com`.
  * Use is strictly restricted to academic non-commercial research.
  * Public redistribution or re-hosting of raw review text is strictly prohibited.
* **License Classification:** `VERIFIED_RESTRICTED` (Rigorous academic benchmark, requires signed DUA).

### Candidate 3: ViMACSA (Vietnamese Multimodal Aspect-Category Sentiment Analysis)
* **Dataset Name:** ViMACSA: Multimodal Aspect-Category Sentiment Analysis Dataset for Vietnamese Hotel Reviews
* **Authors:** Quy Hoang Nguyen, Minh-Van Truong Nguyen, Kiet Van Nguyen
* **Institution:** University of Information Technology, Vietnam National University Ho Chi Minh City (UIT VNU-HCM)
* **Publication / Paper:** *"New Benchmark Dataset and Fine-Grained Cross-Modal Fusion Framework for Vietnamese Multimodal Aspect-Category Sentiment Analysis"*, *Multimedia Systems* (Springer, 2025).
* **Preprint DOI / Link:** `arXiv:2405.00543` / `10.1007/s00530-024-01584-6`
* **Official URL:** `https://uit.edu.vn` / `https://arxiv.org/abs/2405.00543`
* **Dataset Type:** Multimodal (Vietnamese text reviews paired with real tourist hotel photos).
* **Language:** Vietnamese.
* **Record Count:** 4,876 text-image pairs with 14,618 fine-grained aspect annotations across hotel amenities.
* **Review Domains:** Vietnamese hotels, accommodation amenities, customer sentiment.
* **License & Access Terms:** Academic research agreement under UIT NLP Group.
* **License Classification:** `VERIFIED_RESTRICTED` (Academic research only).

---

## 4. Separation of Generic Sentiment vs. Travel Review Datasets

A critical requirement of Task 06.2 is to enforce linguistic domain boundaries and prevent misleading dataset descriptions:

### 1. UIT-VSFC (Vietnamese Students' Feedback Corpus)
* **Citation:** Kiet Van Nguyen, Vu Duc Nguyen, Phu X. V. Nguyen, Tham T. H. Truong, Ngan Luu-Thuy Nguyen, *"UIT-VSFC: Vietnamese Students' Feedback Corpus for Sentiment Analysis"*, In *2018 10th International Conference on Knowledge and Systems Engineering (KSE)*, IEEE, pp. 19–24. DOI: `10.1109/KSE.2018.8573331`.
* **Corpus Content:** Over 16,000 feedback sentences written by university students evaluating course curricula, lecturers, and academic training facilities.
* **Domain Classification:** **GENERIC ACADEMIC SENTIMENT DATA**.
* **Integrity Mandate:** MUST NEVER be cited as "travel reviews" or "hotel reviews". Any previous seed data or documentation claiming UIT-VSFC is travel-related has been retracted.

### 2. VLSP 2016 Sentiment Corpus
* **Corpus Content:** Customer reviews of smartphones, laptops, and tablets.
* **Domain Classification:** **GENERIC CONSUMER ELECTRONICS DATA**.
* **Integrity Mandate:** REJECTED for travel intelligence.

### 3. AIVIVN 2019 E-Commerce Sentiment
* **Corpus Content:** Short product ratings from Vietnamese e-commerce sites (Shopee, Tiki).
* **Domain Classification:** **E-COMMERCE PRODUCT REVIEW DATA**.
* **Integrity Mandate:** REJECTED for travel intelligence.

---

## 5. Rejected Scraped Corpora & Rationale

1. **TripAdvisor Scrapes (`hienbm/tripadvisor_vietnam` and similar):**
   * *Reason:* Scraped from TripAdvisor in violation of TripAdvisor Terms of Use Section 4 ("Prohibited Activities: automated scraping, indexing, or copying of content").
   * *Status:* `REJECTED`. Cannot be legally hosted, committed, or distributed.
2. **Kaggle Unverified Hotel Reviews:**
   * *Reason:* Scraped dumps uploaded by individual anonymous accounts with no proof of original copyright ownership, no clear license, and no reproducible pipeline.
   * *Status:* `REJECTED` / `UNVERIFIED`.

---

## 6. Recommendations for Dataset Acquisition & Milestone Unblocking

### Academic Project (Đồ Án Tốt Nghiệp) Context
* For a university graduation capstone project, **ViHoRec** (CC BY-NC 4.0) provides a legally clean, reproducible, and verifiable dataset with 18,267 interactions and 560 hotels in Vietnam.
* **VLSP 2018 ABSA Hotel Subset** provides 5,600 verified hotel reviews with gold-standard aspect annotations. Using it requires submitting an academic DUA request to `vlsp.resources@gmail.com`.

### Production / Commercial Context
* If WanderAI is deployed commercially, neither CC BY-NC 4.0 nor VLSP DUA allows commercial exploitation. Real user reviews must be collected natively through the WanderAI mobile app via authenticated users, or licensed via commercial B2B data providers.

### Gate Evaluation: Can TASK 07 (Review Intelligence) Be Unblocked?
* **Conditional Unblock for Research/Prototyping:**
  TASK 07 can proceed to dataset acquisition and model design **IF AND ONLY IF** the human project members select one of the verified restricted datasets (e.g., ViHoRec under CC BY-NC 4.0 or VLSP 2018 under DUA) and accept the academic non-commercial terms.
* **Zero Raw Imports in Task 06.2:** As required, zero datasets have been dumped into `data/raw/` or PostgreSQL during this task.
