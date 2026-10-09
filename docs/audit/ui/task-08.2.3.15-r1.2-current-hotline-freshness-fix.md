# GoMate Safety & Emergency — Current Da Nang Hotline Freshness & Permission-State Completeness Fix (TASK 08.2.3.15-R1.2)

**Status:** APPROVED ADDENDUM & DESIGN LOCK (R1.2 REVISION)  
**Task:** TASK 08.2.3.15-R1.2 — GOMATE SAFETY & EMERGENCY: CURRENT DA NANG HOTLINE FRESHNESS & PERMISSION-STATE COMPLETENESS FIX  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Reference Design Contract:** [`docs/design/gomate-safety-emergency-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-safety-emergency-contract-v1.md)  
**Authoritative Source Card:** [`docs/design/data/gomate-emergency-contact-source-card-v1.md`](file:///d:/Do_an/wanderai/docs/design/data/gomate-emergency-contact-source-card-v1.md)  
**Primary Audit Document:** [`docs/audit/ui/task-08.2.3.15-safety-emergency-audit.md`](file:///d:/Do_an/wanderai/docs/audit/ui/task-08.2.3.15-safety-emergency-audit.md)  

---

## 1. Executive Context & Objectives

TASK 08.2.3.15-R1.2 executes a final data freshness, evidence classification, and visual completeness pass on GoMate's **An toàn (Safety & Emergency)** module prior to Design Lock:

```
+---------------------------------------------------------------------------------------------------+
|                               TASK 08.2.3.15-R1.2 HARDENING SCOPE                                 |
+---------------------------------------------------------------------------------------------------+
| 1. Da Nang Hotline Freshness: Update primary current hotline to *8899 (Sept 26, 2026 evidence)     |
| 2. Honest Treatment of 0236: Reclassify 0236 3550 111 as Legacy / Status UNKNOWN (no false claims)|
| 3. Maintain Zero Fabrication: Operating hours & charges for *8899 remain UNKNOWN (no false badges)|
| 4. Permission State Completeness: Create temporary denied mockup with 112/113/114/115 fallback     |
| 5. Repository Search & Classification: Audit all hits of 0236 and *8899 across the codebase        |
| 6. Superseded Artifact Registry: Formally mark pre-R1/stale visual artifacts as non-master        |
| 7. Regenerate Current Artifacts: Render mobile & desktop emergency directory with *8899           |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Detailed Evidence & Hotline Architecture Analysis

### 2.1. Da Nang Visitor Support Hotline Freshness (*8899)
- **Problem:** R1.1 displayed `0236 3550 111` as the primary contact number. While historically accurate, official September 26, 2026 publications from the Da Nang Department of Tourism / Da Nang Tourism Promotion Center (Danang FantastiCity) established **`*8899`** as the official visitor support hotline.
- **Current Canonical Production Hotline:** **`*8899`**
- **Physical Office Locations:**
  - **Primary Headquarters:** `18 Hùng Vương, phường Hải Châu, Đà Nẵng` (relocated from 108 Bạch Đằng in 2023).
  - **Regional Supporting Office (Documentation Note):** `49 Phan Châu Trinh, phường Hội An, Đà Nẵng` (collaboration office for the Da Nang - Hoi An corridor; omitted from primary UI to prevent cognitive clutter).

### 2.2. Honest Reclassification of Legacy Number (0236 3550 111)
- **Principle:** GoMate adheres strictly to the **Zero Fabrication Policy**. The product must **never** claim an official number is "disconnected", "canceled", or "invalid" unless an authoritative government announcement confirms termination.
- **Classification:**
  - **Category:** `LEGACY / HISTORICALLY SOURCED`
  - **Current Operational Status:** `UNKNOWN` ($\text{UNKNOWN} \neq \text{FALSE}$ and $\text{UNKNOWN} \neq \text{ACTIVE}$).
  - **UI Rule:** `0236 3550 111` is **NOT** rendered on production UI cards to ensure travelers are directed to the primary current service channel `*8899`. It is preserved in the Source Card matrix for auditing and historical traceability.

### 2.3. Operational Attributes of *8899 (Hours & Charges Remain UNKNOWN)
- **Principle:** Special short codes cannot be assumed to be toll-free or 24/7 without explicit published tariffs or regulations.
- **Data State:**
  - `operatingHours = UNKNOWN` (do not display "24/7" or "Giờ hành chính").
  - `chargeStatus = UNKNOWN` (do not display "Miễn phí" or "Có tính phí").
- **UI Label:** The neutral metadata pill `Thông tin hỗ trợ du khách` is retained, avoiding speculative badges.
- **CTA:** `[Gọi hỗ trợ]` (Mobile) / `[Mở số gọi *8899]` (Desktop) invoking explicit OS dialer handoff (`tel:*8899`).

---

## 3. Location Permission State Completeness

The GoMate Safety contract strictly distinguishes between temporary denial (`LocationPermission.denied`) and permanent denial (`LocationPermission.deniedForever`):

```
                       User requests GPS fix / taps location
                                        │
                                        ▼
                            Is Permission Granted?
                                 ├── Yes ──► Render Foreground GPS (±15 m)
                                 └── No
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
        Temporary: denied                    Permanent: deniedForever
  ┌───────────────────────────────┐     ┌───────────────────────────────┐
  │ System dialog CAN re-prompt   │     │ System dialog CANNOT prompt   │
  │ Primary CTA:                  │     │ Primary CTA:                  │
  │ [ Cấp quyền vị trí ứng dụng ] │     │ [ Mở Cài đặt hệ thống ]       │
  │ Secondary:                    │     │ Safe Emergency Fallback:      │
  │ [ Mở Cài đặt nếu cần thiết ]  │     │ 112, 113, 114, 115            │
  │ Safe Emergency Fallback:      │     └───────────────────────────────┘
  │ 112, 113, 114, 115            │
  └───────────────────────────────┘
```

### 3.1. Temporary Denied Visual Artifact (`safety-mobile-location-permission-denied-temporary-v1-final.png`)
- **Status Badge:** `Chưa cấp quyền` (Soft amber pill).
- **Heading:** `Quyền truy cập vị trí chưa được cấp`.
- **System State:** `LocationPermission.denied` (Hệ thống có thể yêu cầu cấp lại quyền trực tiếp trên ứng dụng).
- **Primary CTA:** `[ 📍 Cấp quyền vị trí cho ứng dụng ]` (Teal #00897B).
- **Secondary CTA:** `[ Mở Cài đặt nếu cần thiết ]` (Neutral outline).
- **Safe Fallback Emergency Access:** Full 4 statutory emergency services (`112`, `113`, `114`, `115`) displayed directly with instant tap-to-call chips.

---

## 4. Repository Search Results & Classification

A comprehensive audit was performed across the repository for all variants of the Da Nang visitor support numbers:

| Search Term | File Path | Line | Context / Match Content | Classification |
| :--- | :--- | :---: | :--- | :--- |
| `0236 3550 111` | `docs/design/data/gomate-emergency-contact-source-card-v1.md` | 129 | Legacy / Historical Hotline Record definition | **LEGACY / EVIDENCE** |
| `0236 3550 111` | `docs/design/data/gomate-emergency-contact-source-card-v1.md` | 146 | Authoritative Metadata Evidence Matrix row | **LEGACY / AUDIT MATRIX** |
| `0236 3550 111` | `docs/design/gomate-safety-emergency-contract-v1.md` | 134 | Section 4.5 Legacy hotline reference record | **LEGACY / CONTRACT RECORD** |
| `0236 3550 111` | `docs/audit/ui/task-08.2.3.15-safety-emergency-audit.md` | 120 | Section 3.3 Historical reference documentation | **AUDIT HISTORY** |
| `0236 3550 111` | `docs/audit/ui/task-08.2.3.15-r1-directory-authority-correction.md` | 83, 85, 87, 93 | R1 initial audit problem description | **AUDIT HISTORY** |
| `0236 3550 111` | `docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1.png` | Binary | Initial V1 desktop mockup (speculative badges) | **SUPERSEDED VISUAL** |
| `0236 3550 111` | `docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1.png`| Binary | Initial V1 mobile emergency directory | **SUPERSEDED VISUAL** |
| `*8899` | `docs/design/data/gomate-emergency-contact-source-card-v1.md` | 120, 145, 173 | Primary Current Hotline & Reference Schema | **CURRENT CANONICAL** |
| `*8899` | `docs/design/gomate-safety-emergency-contract-v1.md` | 128, 158, 332, 342 | Section 4.5, Schema, & Master Mockup Matrix | **CURRENT CANONICAL** |
| `*8899` | `docs/audit/ui/task-08.2.3.15-safety-emergency-audit.md` | 120, 183, 190 | Section 3.3 & Master Verification Table | **CURRENT CANONICAL** |
| `*8899` | `docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1-r1-final.png` | Binary | Mobile emergency card displaying *8899 | **CURRENT MASTER VISUAL** |
| `*8899` | `docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1-r1-final.png` | Binary | Desktop Safety Hub displaying *8899 | **CURRENT MASTER VISUAL** |

---

## 5. Master Visual Artifacts & Superseded Registry

### 5.1. Canonical Production Master Artifacts (10 Master Artifacts — R1.2 Revision)

| Mockup Artifact | Viewport | Target Resolution | Key R1.2 Visual Specifications |
| :--- | :---: | :---: | :--- |
| [`safety-mobile-emergency-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1-r1-final.png) | Mobile | $390 \times 844$ | 1. Đà Nẵng card: Displays **`*8899`** as primary hotline; neutral metadata label `Thông tin hỗ trợ du khách`; CTA `[Gọi hỗ trợ]`.<br>2. National emergency services: 112 (Bộ Quốc phòng chủ trì), 113, 114, 115.<br>3. Child protection hotline: 111 (Cục Bà mẹ và Trẻ em — Bộ Y tế).<br>4. Staged transition footnote (2027–2028). |
| [`safety-desktop-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1-r1-final.png) | Desktop | $1440 \times 900$ | 1. Đà Nẵng card: Displays **`*8899`** as primary hotline; neutral metadata label `Thông tin hỗ trợ du khách`; CTA `[Mở số gọi *8899]`.<br>2. 112 grid card: Bộ Quốc phòng chủ trì.<br>3. Col 3 roadmap note: Sourced transition stages (2027–2028). |
| [`safety-mobile-location-permission-denied-temporary-v1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-permission-denied-temporary-v1-final.png) | Mobile | $390 \times 844$ | 1. Status: `Quyền truy cập vị trí chưa được cấp` (`LocationPermission.denied`).<br>2. Primary CTA: `[ Cấp quyền vị trí cho ứng dụng ]`.<br>3. Secondary action: `[ Mở Cài đặt nếu cần thiết ]`.<br>4. Fallback emergency chips: 112, 113, 114, 115. |
| [`safety-mobile-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-home-v1-r1.png) | Mobile | $390 \times 844$ | Safety Home with 112, 113, 114, 115 representation (Locked R1). |
| [`safety-mobile-emergency-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-confirm-v1.png) | Mobile | $390 \times 844$ | Explicit OS dialer handoff confirmation sheet (Locked). |
| [`safety-mobile-trusted-contacts-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contacts-v1.png) | Mobile | $390 \times 844$ | Sensitive privacy locked trusted contacts (Locked). |
| [`safety-mobile-trusted-contact-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contact-add-v1.png) | Mobile | $390 \times 844$ | Add trusted contact form (Locked). |
| [`safety-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-v1.png) | Mobile | $390 \times 844$ | Honest foreground GPS fix reporting (Locked). |
| [`safety-mobile-location-permission-denied-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-permission-denied-v1-r1.png) | Mobile | $390 \times 844$ | Permanent denied (`deniedForever`) with settings-only CTA (Locked R1). |
| [`safety-mobile-offline-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-offline-v1-r1.png) | Mobile | $390 \times 844$ | Offline safety directory over carrier voice network (Locked R1). |

### 5.2. Superseded Artifact Registry (DO NOT USE AS MASTER)

| Superseded File | Superseded Reason | Canonical Master Replacement |
| :--- | :--- | :--- |
| `safety-mobile-emergency-v1.png` | Grouped 111 with 113/114/115; omitted 112; listed 0236 with speculative badges. | [`safety-mobile-emergency-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1-r1-final.png) |
| `safety-desktop-v1.png` | Grouped 111 with 113/114/115; omitted 112; listed 0236 with speculative badges. | [`safety-desktop-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1-r1-final.png) |
| `safety-mobile-home-v1.png` | Pre-R1 home layout lacking 112. | [`safety-mobile-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-home-v1-r1.png) |
| `safety-mobile-location-permission-denied-v1.png` | Missing 112 from emergency fallback list; generic permission prompt. | [`safety-mobile-location-permission-denied-temporary-v1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-permission-denied-temporary-v1-final.png) |
| `safety-mobile-offline-v1.png` | Included speculative 2G/3G/4G network copy; omitted 112. | [`safety-mobile-offline-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-offline-v1-r1.png) |

---

## 6. Acceptance Gate Verification

- [x] **Current Da Nang hotline = *8899:** Verified from official September 26, 2026 Da Nang tourism publication.
- [x] **0236 3550 111 retained only as legacy/unknown-current-status:** Reclassified honestly without unsupported disconnection claims.
- [x] **No unsupported statement that old number is disconnected:** Status documented as `UNKNOWN` (UNKNOWN != FALSE).
- [x] **Da Nang address = 18 Hùng Vương:** Retained as primary physical office.
- [x] **Operating hours remain UNKNOWN:** Preserved unless authoritative publication specifies exact hours.
- [x] **Telecom charge remains UNKNOWN:** Preserved unless authoritative tariff documentation exists.
- [x] **Mobile emergency current visual updated:** Regenerated showing `*8899` as primary hotline.
- [x] **Desktop Safety current visual updated:** Regenerated showing `*8899` as primary hotline.
- [x] **Temporary denied visual exists:** `safety-mobile-location-permission-denied-temporary-v1-final.png` created and verified.
- [x] **Temporary denied fallback includes 112/113/114/115:** All 4 statutory services available without GPS fix.
- [x] **deniedForever remains unchanged:** Locked in R1 as permanent settings-only CTA.
- [x] **Offline R1 remains neutral telecom copy:** Free of speculative network generation claims.
- [x] **112 legal basis R1.1 remains unchanged:** Grounded in NĐ 200/2025/NĐ-CP, QĐ 2023/QĐ-TTg, QĐ 2024/QĐ-TTg.
- [x] **111 taxonomy remains unchanged:** Separated as Category B (Cục Bà mẹ và Trẻ em — Bộ Y tế).
- [x] **Wandy boundary unchanged:** Advisory only; zero autonomous dialer or emergency dispatch action.
- [x] **No autonomous emergency actions:** OS dialer handoff strictly enforced.
- [x] **git diff apps/ EMPTY:** Codebase strictly untouched.
- [x] **schema.prisma untouched:** Production PostgreSQL schema unmodified.
- [x] **weekly-report-W01.docx untouched / unstaged:** Preserved unstaged.
- [x] **no merge:** Maintained on `feature/gomate-visual-mockups`.
- [x] **no push:** Local commits only.
