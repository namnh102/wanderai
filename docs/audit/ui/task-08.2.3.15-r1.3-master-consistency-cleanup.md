# GoMate Safety & Emergency — Final Master Consistency Cleanup (TASK 08.2.3.15-R1.3)

**Status:** APPROVED MASTER CONSISTENCY AUDIT & FINAL DESIGN LOCK (R1.3)  
**Task:** TASK 08.2.3.15-R1.3 — GOMATE SAFETY & EMERGENCY: FINAL MASTER CONSISTENCY CLEANUP  
**Date:** October 6, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Reference Design Contract:** [`docs/design/gomate-safety-emergency-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-safety-emergency-contract-v1.md)  
**Authoritative Source Card:** [`docs/design/data/gomate-emergency-contact-source-card-v1.md`](file:///d:/Do_an/wanderai/docs/design/data/gomate-emergency-contact-source-card-v1.md)  
**Primary Audit Document:** [`docs/audit/ui/task-08.2.3.15-safety-emergency-audit.md`](file:///d:/Do_an/wanderai/docs/audit/ui/task-08.2.3.15-safety-emergency-audit.md)  

---

## 1. Executive Context & Objectives

Following the acceptance of TASK 08.2.3.15-R1.2, this task executes the **final master consistency cleanup** across documentation and visual evidence artifacts before the GoMate Safety & Emergency module is permanently **DESIGN LOCKED**.

```
+---------------------------------------------------------------------------------------------------+
|                               TASK 08.2.3.15-R1.3 CLEANUP SCOPE                                   |
+---------------------------------------------------------------------------------------------------+
| 1. Mobile Home Blanket-Claim Ambiguity: Remove "& du lịch" from 24/7/free governed copy            |
| 2. Da Nang Address Standard Wording: Standardize to "18 Hùng Vương, phường Hải Châu, Đà Nẵng"    |
| 3. Master Table Duplicate Cleanup: Ensure exactly one master row per canonical artifact          |
| 4. Repository Search & Classification: Classify all historical, legacy, and current matches       |
| 5. Regenerate Affected Visuals: Re-render Home, Mobile Emergency, and Desktop Hub                |
| 6. Source Integrity: Ensure zero changes to apps/, schema.prisma, and unstaged weekly report     |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Safety Home Copy Correction (Eliminating Blanket-Claim Ambiguity)

### 2.1. Problem Analysis
In prior revisions, the Mobile Safety Home SOS card visually combined:
- Subtitle: `"Đầu số quốc gia 112, 113, 114, 115 & du lịch"`
- Badges: `[ Khẩn cấp 24/7 ]`, `[ Miễn phí ]`

Because the local Da Nang visitor support hotline (`*8899`) is classified as:
- `operatingHours = UNKNOWN`
- `chargeStatus = UNKNOWN`

placing `"& du lịch"` in text directly governed by the `24/7` and `Miễn phí` badges inadvertently created an unsubstantiated blanket claim violating the **Zero Fabrication Policy**.

### 2.2. Corrected Production Copy & Governance
The SOS card copy on Safety Home is strictly scoped to statutory national services:

| Element | Production Value | Governance Scope |
| :--- | :--- | :--- |
| **Card Title** | `Hỗ trợ khẩn cấp (SOS)` | Primary life-safety action card |
| **Supporting Line** | `Đầu số khẩn cấp quốc gia 112, 113, 114, 115` | Strictly national statutory services |
| **Badges** | `Khẩn cấp 24/7` | Visually & semantically scoped **only** to 112–115 |
| **Body / Hint** | `Truy cập nhanh danh bạ cứu trợ quốc gia và các kênh hỗ trợ du khách địa phương.` | Clarifies destination contains both national & local hotlines |
| **Primary CTA** | `[ Mở danh bạ cứu trợ khẩn cấp › ]` | Direct navigation to Emergency Directory |

---

## 3. Current Da Nang Administrative & Address Wording

### 3.1. Standardized Current 2026 Office Addresses
To align with official September 26, 2026 Da Nang tourism publications ([`danangfantasticity.com`](https://danangfantasticity.com)), address metadata is standardized:
- **Primary Headquarters:** `18 Hùng Vương, phường Hải Châu, Đà Nẵng`
- **Secondary Regional Office (Documentation Only):** `49 Phan Châu Trinh, phường Hội An, Đà Nẵng`

### 3.2. Purging of Stale Administrative Strings
The following stale strings were audited and purged from active production metadata:
- `"Phường Hải Châu 1"` $\rightarrow$ updated to canonical `"phường Hải Châu, Đà Nẵng"`
- `"Quận Hải Châu"` $\rightarrow$ updated to canonical `"phường Hải Châu, Đà Nẵng"`
- `"Phường Minh An"` $\rightarrow$ updated to canonical `"phường Hội An, Đà Nẵng"`
- `"TP. Hội An"` $\rightarrow$ updated to canonical `"phường Hội An, Đà Nẵng"`

Historical audit logs (e.g. R1.1 evidence notes recording the 2023 move) retain historical wording solely as **HISTORICAL EVIDENCE** without affecting current master contracts.

---

## 4. Current Hotline Architecture Locked

The hotline classification established in R1.2 remains permanently locked:
- **Primary Current Hotline:** `*8899`
  - `operatingHours = UNKNOWN`
  - `chargeStatus = UNKNOWN`
  - Rendered with neutral metadata pill: `Thông tin hỗ trợ du khách`
- **Legacy Hotline:** `0236 3550 111`
  - Classification: `LEGACY / HISTORICALLY SOURCED`
  - `currentOperationalStatus = UNKNOWN`
  - Preserved in audit source cards; **not rendered** on primary UI.

---

## 5. Master Artifact Registry (Exactly 10 Canonical Artifacts)

All duplicate rows in the audit documentation have been resolved. The canonical master artifact list consists of exactly 10 artifacts:

| # | Master Mockup File | Viewport | Target Resolution | Architectural Status |
| :-: | :--- | :---: | :---: | :---: |
| 1 | [`safety-mobile-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-home-v1-r1.png) | Mobile | $390 \times 844$ | **PASS (LOCKED R1.3)** |
| 2 | [`safety-mobile-emergency-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1-r1-final.png) | Mobile | $390 \times 844$ | **PASS (LOCKED R1.3)** |
| 3 | [`safety-mobile-emergency-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-confirm-v1.png) | Mobile | $390 \times 844$ | **PASS (LOCKED)** |
| 4 | [`safety-mobile-trusted-contacts-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contacts-v1.png) | Mobile | $390 \times 844$ | **PASS (LOCKED)** |
| 5 | [`safety-mobile-trusted-contact-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contact-add-v1.png) | Mobile | $390 \times 844$ | **PASS (LOCKED)** |
| 6 | [`safety-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-v1.png) | Mobile | $390 \times 844$ | **PASS (LOCKED)** |
| 7 | [`safety-mobile-location-permission-denied-temporary-v1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-permission-denied-temporary-v1-final.png) | Mobile | $390 \times 844$ | **PASS (LOCKED R1.2)** |
| 8 | [`safety-mobile-location-permission-denied-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-permission-denied-v1-r1.png) | Mobile | $390 \times 844$ | **PASS (LOCKED R1)** |
| 9 | [`safety-mobile-offline-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-offline-v1-r1.png) | Mobile | $390 \times 844$ | **PASS (LOCKED R1)** |
| 10 | [`safety-desktop-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1-r1-final.png) | Desktop | $1440 \times 900$ | **PASS (LOCKED R1.3)** |

### 5.1. Superseded Artifact Registry (Historical Audit Only)
The following pre-R1/stale visual artifacts remain preserved strictly for review history:
- `safety-mobile-emergency-v1.png` (Superseded by `safety-mobile-emergency-v1-r1-final.png`)
- `safety-desktop-v1.png` (Superseded by `safety-desktop-v1-r1-final.png`)
- `safety-mobile-home-v1.png` (Superseded by `safety-mobile-home-v1-r1.png`)
- `safety-mobile-location-permission-denied-v1.png` (Superseded by `safety-mobile-location-permission-denied-temporary-v1-final.png`)
- `safety-mobile-offline-v1.png` (Superseded by `safety-mobile-offline-v1-r1.png`)

---

## 6. Repository Consistency Search & Classification

All repository search patterns specified in TASK 08.2.3.15-R1.3 were executed across `docs/` and classified:

| Search Pattern | File Location & Line | Context | Classification | Action Taken |
| :--- | :--- | :--- | :--- | :--- |
| `Hải Châu 1` | `task-08.2.3.15-r1.1-source-evidence-hardening.md:65` | Historical audit record of 2023 HQ relocation | **HISTORICAL** | Preserved as audit evidence |
| `Quận Hải Châu`| `task-08.2.3.15-r1.1-source-evidence-hardening.md:65` | Historical audit record of 2023 HQ relocation | **HISTORICAL** | Preserved as audit evidence |
| `Minh An` | *(None in active docs)* | Regional collaboration office | **AUDITED / PURGED** | Zero stale active hits |
| `0236 3550 111`| `task-08.2.3.15-r1-directory-authority-correction.md:83,85,87,93` | Initial problem audit report | **HISTORICAL** | Preserved as audit history |
| `0236 3550 111`| `task-08.2.3.15-r1.1-source-evidence-hardening.md:145` | Reclassification notice | **HISTORICAL** | Preserved as audit history |
| `0236 3550 111`| `task-08.2.3.15-r1.2-current-hotline-freshness-fix.md:23,37,43,48` | Legacy status determination | **HISTORICAL** | Preserved as audit history |
| `0236 3550 111`| `gomate-emergency-contact-source-card-v1.md:129,152,182` | Authoritative source card legacy record | **LEGACY EVIDENCE** | Retained with `status=UNKNOWN` |
| `0236 3550 111`| `gomate-safety-emergency-contract-v1.md:135,163` | Section 4.5 & Schema legacy field | **LEGACY CONTRACT** | Preserved in contract |
| `0236 3550 111`| `safety-emergency-audit.md:120,211` | Audit documentation & checklist | **HISTORICAL AUDIT** | Preserved in audit record |
| `*8899` | `gomate-safety-emergency-contract-v1.md:129,133,134,162,334,342` | Primary current hotline specification | **CURRENT CANONICAL** | Master contract specification |
| `*8899` | `gomate-emergency-contact-source-card-v1.md:120,125,151,181` | Authoritative source card primary entry | **CURRENT CANONICAL** | Master source card entry |
| `*8899` | `safety-emergency-audit.md:121,184,192,210,217,218` | Master audit & verification records | **CURRENT CANONICAL** | Master audit verification |
| `*8899` | `safety-mobile-emergency-v1-r1-final.png` | Mobile Emergency UI primary card | **CURRENT MASTER** | Rendered master visual |
| `*8899` | `safety-desktop-v1-r1-final.png` | Desktop Safety Hub UI primary card | **CURRENT MASTER** | Rendered master visual |
| `safety-mobile-emergency-v1-r1-final` | All contract, source card, and audit registries | Primary mobile directory mockup | **CURRENT MASTER** | Canonical artifact entry |
| `safety-desktop-v1-r1-final` | All contract, source card, and audit registries | Primary desktop hub mockup | **CURRENT MASTER** | Canonical artifact entry |

---

## 7. Regenerated Visual Artifacts

The following mockups were regenerated via Playwright / Chromium headless rendering script (`scratch/render_safety_r1_3.py`) at native specifications and visually verified:

1. **`safety-mobile-home-v1-r1.png` ($390 \times 844$):**
   - Title: `Hỗ trợ khẩn cấp (SOS)`
   - Supporting Line: `Đầu số khẩn cấp quốc gia 112, 113, 114, 115`
   - Badges: `Khẩn cấp 24/7` (strictly national scope)
   - Body: `Truy cập nhanh danh bạ cứu trợ quốc gia và các kênh hỗ trợ du khách địa phương.`
   - Location Card: `Phường Hải Châu, TP. Đà Nẵng`
   - CTA: `[ Mở danh bạ cứu trợ khẩn cấp › ]`
2. **`safety-mobile-emergency-v1-r1-final.png` ($390 \times 844$):**
   - Đà Nẵng Tourist Support Card: Displays `*8899` with badge `Thông tin hỗ trợ du khách` and standardized address `18 Hùng Vương, phường Hải Châu, Đà Nẵng`.
   - Statutory Emergency Grid: 112, 113, 114, 115 with 24/7 & free-call badges.
3. **`safety-desktop-v1-r1-final.png` ($1440 \times 900$):**
   - Đà Nẵng Tourist Support Card: Displays `*8899` with badge `Thông tin hỗ trợ du khách` and standardized address `18 Hùng Vương, phường Hải Châu, Đà Nẵng`.
   - Location Safety Widget: Foreground GPS fix with locality `Phường Hải Châu, TP. Đà Nẵng, Việt Nam`.

---

## 8. Final Design Acceptance Gate (TASK 08.2.3.15-R1.3)

- [x] **Safety Home no longer implies tourist hotline is 24/7/free:** Scoped strictly to national numbers.
- [x] **24/7/free claims visually scoped to verified national numbers:** 112, 113, 114, 115 only.
- [x] **Current Da Nang primary hotline remains *8899:** Verified from official September 26, 2026 publication.
- [x] **Current primary address uses "18 Hùng Vương, phường Hải Châu, Đà Nẵng":** Standardized across all documents and mockups.
- [x] **Secondary office current wording uses "49 Phan Châu Trinh, phường Hội An, Đà Nẵng":** Standardized in reference source card.
- [x] **Operating hours of *8899 remain UNKNOWN:** Neutral metadata label `Thông tin hỗ trợ du khách`.
- [x] **Telecom charge of *8899 remains UNKNOWN:** No speculative free/paid badges.
- [x] **0236 3550 111 remains legacy / current status UNKNOWN:** Retained in audit source card; not rendered on primary UI.
- [x] **Exactly one current Mobile Emergency master row:** `safety-mobile-emergency-v1-r1-final.png` (*8899, 18 Hùng Vương, phường Hải Châu, Đà Nẵng, PASS / LOCKED R1.3).
- [x] **Exactly one current Desktop Safety master row:** `safety-desktop-v1-r1-final.png` (*8899, 18 Hùng Vương, phường Hải Châu, Đà Nẵng, PASS / LOCKED R1.3).
- [x] **Old artifact rows are explicitly historical/superseded:** Documented in Superseded Artifact Registry.
- [x] **Temporary denied state remains locked:** `safety-mobile-location-permission-denied-temporary-v1-final.png` preserved.
- [x] **deniedForever remains locked:** `safety-mobile-location-permission-denied-v1-r1.png` preserved.
- [x] **Offline R1 remains locked:** `safety-mobile-offline-v1-r1.png` with neutral carrier copy preserved.
- [x] **112/113/114/115 architecture unchanged:** Grounded in statutory legal basis; 112 under Bộ Quốc phòng.
- [x] **111 taxonomy unchanged:** Category B (Cục Bà mẹ và Trẻ em — Bộ Y tế).
- [x] **Wandy emergency boundary unchanged:** Advisory only; zero autonomous dispatch.
- [x] **No production code changes:** Zero modifications to `apps/`.
- [x] **schema.prisma untouched:** Production schema pristine.
- [x] **weekly-report-W01.docx untouched / unstaged:** Preserved unstaged.
- [x] **no merge:** Maintained on `feature/gomate-visual-mockups`.
- [x] **no push:** Local commits only.
