# VLSP 2018 Aspect-Based Sentiment Analysis — Academic Access Request Dossier

**Dataset Name:** VLSP 2018 Shared Task: Aspect-Based Sentiment Analysis (Hotel Subset)  
**Provider:** Association for Vietnamese Language and Speech Processing (VLSP)  
**Official Portal:** `https://vlsp.org.vn/resources-vlsp2018`  
**Official Contact:** `vlsp.resources@gmail.com`  
**Document Status:** `REQUEST_NOT_SENT` (Request package drafted; awaiting human project members' review and signature)  
**Target Milestone:** TASK 07 — Review Intelligence & Aspect Extraction  

---

## 1. Project & Institutional Identification

* **Project Name:** WanderAI — Intelligent AI Travel Assistant & Itinerary Planner for Vietnam
* **Nature of Project:** Academic University Graduation Capstone Project (Đồ án tốt nghiệp đại học ngành Kỹ thuật Phần mềm / Trí tuệ Nhân tạo)
* **Research Team:**
  * Member A: Infrastructure, Backend Architecture, System Engineering
  * Member B: AI Engineering, NLP Modeling, Data Pipeline
* **Supervising Institution:** Vietnam National University / Academic Department of Information Technology

---

## 2. Research Purpose & Requested Subset

* **Requested Subset:** 
  * VLSP 2018 ABSA **Hotel Domain Dataset** (Train: 3,000 sentences/reviews; Dev: 2,000 sentences/reviews; Test: 600 sentences/reviews).
  * Annotation schemas for Aspect Category Detection (ACD) and Sentiment Polarity Classification (SPC).
* **Research Purpose:**
  1. Fine-tuning low-parameter Vietnamese language models (PhoBERT / ViDeBERTa / ViT5) to recognize hotel aspects (e.g., `ROOMS#CLEANLINESS`, `SERVICE#GENERAL`, `HOTEL#PRICE`, `LOCATION#GENERAL`).
  2. Grounding the WanderAI travel assistant with objective, multi-attribute sentiment summaries so travelers receive balanced pros/cons of Vietnamese accommodations without hallucination.
  3. Benchmarking aspect detection accuracy against published VLSP 2018 baselines.

---

## 3. Strict Compliance & Legal Undertakings

In accordance with the VLSP Data User Agreement (DUA):

1. **Non-Commercial Restriction:**
   * The dataset will be utilized exclusively for academic non-commercial research and thesis evaluation.
   * Under no circumstances will the dataset or derived checkpoints be incorporated into a commercial paid product, SaaS subscription, or commercial API.
2. **Redistribution Prohibition:**
   * Raw reviews, annotations, and test split keys **WILL NOT** be committed to public GitHub repositories, hosted on public servers, or distributed to third parties.
   * All raw data will be stored exclusively in a secure, local, gitignored directory (`data/restricted/vlsp2018/`).
3. **Mandatory Attribution / Citation:**
   * Any academic paper, thesis dissertation, or technical report arising from this research will prominently cite the official VLSP 2018 overview publication:
     ```bibtex
     @article{nguyen2018vlsp,
       title={VLSP Shared Task: Sentiment Analysis},
       author={Nguyen, Huyen T. M. and Nguyen, Hung V. and Ngo, Quyen T. and Vu, Luong X. and Tran, Vu Mai and Ngo, Bach X. and Le, Cuong A.},
       journal={Journal of Computer Science and Cybernetics},
       volume={34},
       number={4},
       pages={283--294},
       year={2018},
       doi={10.15625/1813-9663/34/4/13158}
     }
     ```
4. **Data Storage & Destruction Policy:**
   * Data storage location: `data/restricted/vlsp2018/` (strictly excluded by root `.gitignore`).
   * Backups will be encrypted at rest.
   * Access to raw files is restricted to authorized project team members.
   * The raw corpus will be securely deleted upon completion and defense of the university capstone thesis, or upon request by the VLSP committee.

---

## 4. Formal Request Form & Submission Checklist

Human project members must execute the following steps to transition status from `REQUEST_NOT_SENT` to `REQUEST_SENT`:

- [ ] Download the official agreement document: `DUA_VLSP2018.pdf` from `https://vlsp.org.vn/resources-vlsp2018`.
- [ ] Fill in institutional details, supervisor's name, and student researcher signatures.
- [ ] Scan the signed document to PDF (`WanderAI_VLSP2018_DUA_Signed.pdf`).
- [ ] Send email to `vlsp.resources@gmail.com` with:
  * Subject: `[Data Request] VLSP 2018 ABSA Hotel Dataset - WanderAI Academic Capstone`
  * Body describing thesis objective, supervisor endorsement, and attached signed DUA.
- [ ] Update this dossier status to `REQUEST_SENT` with timestamp and ticket reference.
- [ ] Upon receipt of the download link, update status to `ACCESS_GRANTED`, verify SHA-256 checksums, and store under `data/restricted/vlsp2018/`.

---

## 5. Current Clearance State

* **Current Status:** `REQUEST_NOT_SENT`
* **Access Block:** TASK 07 Review AI fine-tuning remains blocked until official approval is returned by VLSP organizers.
