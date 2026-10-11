# ViMACSA Dataset — Access Clearance & Usage Specification

**Dataset Name:** ViMACSA: Multimodal Aspect-Category Sentiment Analysis Dataset for Vietnamese Hotel Reviews  
**Originating Authors:** Quy Hoang Nguyen, Minh-Van Truong Nguyen, Kiet Van Nguyen  
**Institution:** University of Information Technology, Vietnam National University Ho Chi Minh City (UIT VNU-HCM)  
**Publication Reference:** *"New Benchmark Dataset and Fine-Grained Cross-Modal Fusion Framework for Vietnamese Multimodal Aspect-Category Sentiment Analysis"*, *Multimedia Systems* (Springer, 2025). DOI: `10.1007/s00530-024-01584-6` (Preprint: `arXiv:2405.00543`).  
**Document Status:** `REQUEST_NOT_SENT` (Academic research protocol drafted)  
**Target Milestone:** Advanced Multimodal Review Intelligence (Future Milestone)  

---

## 1. Dataset Characteristics & Research Scope

* **Modality:** Multimodal — Pairs of Vietnamese natural-language customer reviews and corresponding hotel facility/room photographs.
* **Volume:** 4,876 text-image pairs featuring 14,618 fine-grained aspect annotations across hotel amenities, cleanliness, services, and decor.
* **Intended Use in WanderAI:**
  * Multimodal verification of place amenities (e.g., verifying if user reviews praising a pool or balcony match accompanying visual imagery).
  * Fine-tuning multimodal sentiment fusion models for rich media presentation in mobile travel feeds.

---

## 2. Access Terms & Legal Procedure

Based on the publisher's official Data Availability Statement (*Multimedia Systems*, Springer 2025):
> *"The datasets generated during and/or analysed during the current study are available from the corresponding author on reasonable request."*

### Key Requirements
1. **Academic Request Protocol:**
   * Access requires submitting a formal research request to the corresponding author (Dr. Kiet Van Nguyen / Quy Hoang Nguyen, NLP@UIT, `kietnv@uit.edu.vn`).
   * The request must outline the graduation thesis context, institutional affiliation, and non-commercial research objectives.
2. **Local Storage Permissibility:**
   * Raw text annotations and associated image files may be stored locally on restricted research workstations under `data/restricted/vimacsa/`.
   * Raw image assets and text reviews **MUST NOT** be committed to public version control or mirrored on public S3/cloud buckets.
3. **Redistribution Prohibition:**
   * Redistribution, public re-uploading, or scraping of the original photo URLs is strictly prohibited.
4. **Attribution Requirement:**
   * All reports, papers, and presentations utilizing ViMACSA must cite:
     ```bibtex
     @article{nguyen2025vimacsa,
       title={New benchmark dataset and fine-grained cross-modal fusion framework for Vietnamese multimodal aspect-category sentiment analysis},
       author={Nguyen, Quy Hoang and Nguyen, Minh-Van Truong and Nguyen, Kiet Van},
       journal={Multimedia Systems},
       year={2025},
       publisher={Springer},
       doi={10.1007/s00530-024-01584-6}
     }
     ```

---

## 3. Storage & Safety Policy

* **Directory:** `data/restricted/vimacsa/` (strictly excluded by root `.gitignore`).
* **Media Handling:** All image files associated with hotel reviews are subject to original user copyright; they are solely accessed under the research exemption of the academic data request.
* **No Unverified Downloads:** No scripts or scraping routines will attempt to download ViMACSA assets until the authors grant access.

---

## 4. Current Access State

* **Access Status:** `REQUEST_NOT_SENT`
* **Action Required:** When multimodal review features are prioritized, Human Member B will submit a formal academic request to UIT NLP Group.
