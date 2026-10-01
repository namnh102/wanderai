# Restricted Datasets Directory — Data Governance & Storage Policy

> [!CAUTION]
> **Dataset not included. Obtain access from original provider.**  
> In compliance with academic Data User Agreements (DUA) and Non-Commercial licensing (CC BY-NC 4.0), raw third-party datasets are **NEVER committed to this repository**. All raw assets are strictly excluded via `.gitignore`.

---

## 1. Governance Principles

1. **Zero Unauthorized Redistribution:**
   * Research datasets with redistribution prohibitions (such as VLSP 2018 ABSA and ViMACSA) must be requested directly by researchers from their respective creators.
   * Do not upload, commit, or mirror any files from this directory to GitHub, GitLab, Docker images, or public cloud storage buckets.
2. **Access Control:**
   * Local storage in `data/restricted/` is permitted only after formal access clearance has been approved.
   * Access is limited to authorized project developers running experiments locally on their development machines.

---

## 2. Directory Layout & Checksum Registry

When authorized access is obtained, place the uncompressed datasets into the corresponding subdirectories and verify their SHA-256 checksums:

```
data/restricted/
├── .gitignore
├── README.md
├── vlsp2018/
│   ├── vlsp2018_hotel_train.txt
│   ├── vlsp2018_hotel_dev.txt
│   ├── vlsp2018_hotel_test.txt
│   └── checksums.sha256
├── vihorec/
│   ├── interactions.csv
│   ├── hotels_metadata.csv
│   └── checksums.sha256
└── vimacsa/
    ├── annotations.json
    ├── images/
    └── checksums.sha256
```

---

## 3. Dataset Acquisition References & Checksums

### 1. VLSP 2018 ABSA (Hotel Domain)
* **Status:** `REQUEST_NOT_SENT`
* **Access Procedure:** Follow [`docs/data/access/vlsp2018-access-request.md`](../../docs/data/access/vlsp2018-access-request.md). Submit signed DUA to `vlsp.resources@gmail.com`.
* **Redistribution:** **STRICTLY PROHIBITED**.
* **Checksum Verification:**
  ```powershell
  Get-FileHash data/restricted/vlsp2018/* -Algorithm SHA256
  ```

### 2. ViHoRec (Hotel Recommendation Benchmark)
* **Status:** `PUBLIC_AVAILABLE_RESTRICTED` (CC BY-NC 4.0)
* **Access Procedure:** Follow [`docs/data/recommendation-dataset.md`](../../docs/data/recommendation-dataset.md). Clone or download from [`https://github.com/MinhNguyenDS/ViHoRec`](https://github.com/MinhNguyenDS/ViHoRec).
* **Usage Clause:** Non-commercial academic research only.
* **Target Directory:** `data/restricted/vihorec/`

### 3. ViMACSA (Multimodal Hotel Review Dataset)
* **Status:** `REQUEST_NOT_SENT`
* **Access Procedure:** Follow [`docs/data/access/vimacsa-access.md`](../../docs/data/access/vimacsa-access.md). Request from corresponding author at UIT NLP Group (`kietnv@uit.edu.vn`).
* **Redistribution:** **STRICTLY PROHIBITED**.
* **Target Directory:** `data/restricted/vimacsa/`

---

## 4. Verification Script

To verify local dataset files without exposing contents:

```bash
# Verify integrity of downloaded files against manifests
python scripts/verify_restricted_datasets.py
```
*(Verification script will check presence and SHA-256 integrity only when files are placed locally).*
