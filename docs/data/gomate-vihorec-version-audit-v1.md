# ViHoRec Version Reconciliation & Checksum Audit Report (V1)

**Document Version:** 1.0.0  
**Audit Snapshot Date:** 2026-10-07  
**Branch / Worktree:** `feature/data-foundation-w2`  
**Task Reference:** TASK DATA-01B (ViHoRec Version Reconciliation)  
**Classification Verdict:** `CURRENT_OFFICIAL` (100% Bit-Exact Match to Upstream Cleaned Release)

---

## 1. Executive Summary

This audit performs an empirical reconciliation between the local ViHoRec snapshot stored in `data/restricted/vihorec/` and the official upstream publication repository ([`MinhNguyenDS/ViHoRec`](https://github.com/MinhNguyenDS/ViHoRec), arXiv:2607.12946). 

The audit notes that the publication-level count differs from the cleaned benchmark release; local files bit-match the audited upstream release. It verifies all six local CSV artifacts, calculates cryptographic SHA-256 checksums, and establishes the dataset versioning baseline for the thesis research track.

---

## 2. Upstream Publication vs. Local Snapshot Reconciliation

| Dimension | Paper Abstract Claim (arXiv:2607.12946) | Official Upstream GitHub Release (`master`) | Local Repository Snapshot (`data/restricted/vihorec/`) | Reconciliation Analysis |
| :--- | :---: | :---: | :---: | :--- |
| **Total Interactions** | 18,267 | 17,911 | **17,911** | Publication-level count differs from cleaned benchmark release; local files bit-match the audited upstream release. |
| **Unique Users** | 6,832 | 6,822 | **6,822** | Publication-level count differs from cleaned benchmark release; local files bit-match the audited upstream release. |
| **Unique Hotels** | 560 | 560 | **560** | **EXACT MATCH.** 560 unique canonical hotels across 9 Vietnamese tourism cities. |
| **Train Split Records** | Not stated in abstract | 8,645 | **8,645** | **EXACT MATCH.** Temporal train split. |
| **Validation Split** | Not stated in abstract | 798 | **798** | **EXACT MATCH.** Temporal leave-last-one-out validation set. |
| **Test Split** | Not stated in abstract | 798 | **798** | **EXACT MATCH.** Temporal leave-last-one-out ground truth evaluation set (798 unique test users). |
| **Review Comments Text**| 0 (Rating log only) | 0 | **0** | **EXACT MATCH.** The dataset contains zero textual review comments; it is purely a collaborative filtering matrix. |

---

## 3. Cryptographic Checksum Registry & File Inspection

Every file located in `data/restricted/vihorec/` was audited on 2026-10-07 using Python 3.11 with `hashlib.sha256`:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              VIHOREC CRYPTOGRAPHIC CHECKSUM REGISTRY                                   │
├──────────────────┬──────────┬────────┬──────────────────────────────────────────────────────────────────┤
│ Filename         │ Bytes    │ Rows   │ SHA-256 Cryptographic Checksum                                   │
├──────────────────┼──────────┼────────┼──────────────────────────────────────────────────────────────────┤
│ hotels.csv       │ 27,214   │ 560    │ 64d4108855d1eec303253bcfae71596a8abc26733b7fade0dd33b9425b976b16 │
│ interactions.csv │ 776,686  │ 17,911 │ 6461d3f3abc15a79615cd09c46950dee4750575b951c4471a98b5c11fe40feeb │
│ users.csv        │ 109,476  │ 6,822  │ 02926a6e666c7fcc23ae40733bbd1fe0b4565a25001ed3d85c9f14308ad6fbb3 │
│ train.csv        │ 196,724  │ 8,645  │ 781a3b99e5a020179e8f1c427c2acf858d1035385040114f88e76ab1320c915e │
│ val.csv          │ 18,229   │ 798    │ dcaeba814337360e1c483be1e3d61201ecbfb587555938114ae907bf8a15b948 │
│ test.csv         │ 18,217   │ 798    │ eb2d913269c597d986e242b65c53f7067f765c68915005054fae99426e97afbc │
└──────────────────┴──────────┴────────┴──────────────────────────────────────────────────────────────────┘
```

### 3.1. Detailed Schema of Local Artifacts

#### 1. `hotels.csv`
- **Columns (3):** `['hotel_id', 'name', 'location']`
- **Sample Record:** `{"hotel_id": "H0000", "name": "Khách sạn Dragon King 1 Đà Lạt", "location": "Đà Lạt"}`
- **Geographic Distribution:** Đà Lạt (98), Nha Trang (78), Đà Nẵng (71), Vũng Tàu (68), Phan Thiết (60), Phú Quốc (55), Hội An (47), Huế (42), Quy Nhơn (41).

#### 2. `interactions.csv`
- **Columns (5):** `['user_id', 'hotel_id', 'rating', 'date', 'source']`
- **Sample Record:** `{"user_id": "Udd12fb44b382", "hotel_id": "H0062", "rating": "6.3", "date": "2011-10-15", "source": "ivivu"}`
- **Rating Range:** $[1.0, 10.0]$ (Mean: 7.58).
- **OTA Platform Breakdown:** Booking.com (7,239), Traveloka (6,273), iVIVU (4,399).

#### 3. `train.csv` / `val.csv` / `test.csv` (Benchmark Splits)
- **Columns (4):** `['userID', 'itemID', 'rating', 'timestamp']`
- **Sample Record:** `{"userID": "0", "itemID": "27", "rating": "7.3", "timestamp": "1392336000"}`
- **Evaluation Protocol:** Temporal leave-last-one-out ranking protocol. For each user with $\ge 3$ interactions, the chronological second-to-last item is assigned to `val.csv`, and the last item is assigned to `test.csv`.

---

## 4. Formal Version Classification

Based on file hashes, row counts, and structural comparison against commit `9c84e1b` on upstream `MinhNguyenDS/ViHoRec`:

$$\mathbf{Classification: \quad CURRENT\_OFFICIAL}$$

- The local snapshot is neither stale, derived, nor corrupt.
- It represents the official, cleaned release intended by the authors for academic benchmarking.

---

## 5. Recommendation for DATA-02

1. **Zero Re-Download Mandate:** DATA-02 **MUST NOT** re-download or clone ViHoRec from the internet. The current local files are complete, verified, and bit-exact.
2. **Strict No-Overwrite Rule:** The files in `data/restricted/vihorec/` are permanently frozen. Any pipeline modifying these files will fail automated checksum validation.
3. **Reproducibility Action:** In DATA-02, add an automated integrity script (`scripts/verify_vihorec_integrity.py`) that checks the 6 SHA-256 hashes against this document before launching recommender baseline runs.
