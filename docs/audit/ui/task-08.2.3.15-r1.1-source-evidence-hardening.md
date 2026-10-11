# GoMate Safety & Emergency — Current Legal Basis, Source Evidence & Unknown-Metadata Hardening (TASK 08.2.3.15-R1.1)

**Status:** APPROVED ADDENDUM & DESIGN LOCK (R1.1 REVISION)  
**Task:** TASK 08.2.3.15-R1.1 — GOMATE SAFETY & EMERGENCY: CURRENT LEGAL BASIS, SOURCE EVIDENCE & UNKNOWN-METADATA HARDENING  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Reference Design Contract:** [`docs/design/gomate-safety-emergency-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-safety-emergency-contract-v1.md)  
**Authoritative Source Card:** [`docs/design/data/gomate-emergency-contact-source-card-v1.md`](file:///d:/Do_an/wanderai/docs/design/data/gomate-emergency-contact-source-card-v1.md)  
**Primary Audit Document:** [`docs/audit/ui/task-08.2.3.15-safety-emergency-audit.md`](file:///d:/Do_an/wanderai/docs/audit/ui/task-08.2.3.15-safety-emergency-audit.md)  

---

## 1. Executive Context & Objective

TASK 08.2.3.15-R1.1 executes a micro-correction and evidence-hardening pass on GoMate's **An toàn (Safety & Emergency)** module following the R1 revision. It resolves subtle legal basis, semantic scope, administrative governance, physical address, and metadata certainty issues across the design contracts and visual mockups:

```
+---------------------------------------------------------------------------------------------------+
|                               TASK 08.2.3.15-R1.1 HARDENING SCOPE                                 |
+---------------------------------------------------------------------------------------------------+
| 1. Update 112 Legal Basis: Replace 2016 historical QĐ 226 with current 2025 civil defense laws    |
| 2. Normalize 112 Governance: Canonical authority = "Bộ Quốc phòng" (Bộ Quốc phòng chủ trì)        |
| 3. Normalize 112 Scope: Broad statutory scope (sự cố, thiên tai, thảm họa, nguy cấp, trợ giúp)   |
| 4. Correct Đà Nẵng Address: Updated from 108 Bạch Đằng to current office: 18 Hùng Vương (2023)    |
| 5. Remove Unsourced Đà Nẵng Badges: Operating hours & charges = UNKNOWN (UNKNOWN != FALSE)        |
| 6. Harden Conceptual Schema: Replace rigid defaults with explicit UNKNOWN evidence state enums     |
| 7. Stage-Based Transition Note: Replaced informal string with official Stage 1 (2027) & 2 (2028)  |
| 8. Fix Internal Stale Copy: Fixed audit document sections 3.3 and 3.7 to include 112              |
| 9. Regenerate Affected Visuals: Mobile Emergency R1.1 Final & Desktop R1.1 Final                   |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Detailed Hardening Analysis

### 2.1. Update 112 Current Legal Basis (2025 Legislation)
- **Problem:** R1 documentation still cited historical Decision No. 226/QĐ-TTg (2016) as the primary authority for 112.
- **Current Legal Framework:**
  - **Nghị định số 200/2025/NĐ-CP** của Chính phủ: Quy định chi tiết một số điều của Luật Phòng thủ dân sự.
  - **Quyết định số 2023/QĐ-TTg ngày 15/09/2025** của Thủ tướng Chính phủ: Về việc sử dụng số điện thoại 112 tiếp nhận thông tin về sự cố, thiên tai, thảm họa, nguy cơ xảy ra và yêu cầu trợ giúp trên phạm vi toàn quốc.
  - **Quyết định số 2024/QĐ-TTg ngày 15/09/2025** của Thủ tướng Chính phủ: Ban hành Quy chế sử dụng số điện thoại 112.
  - **Thông tư số 22/2014/TT-BTTTT** của Bộ Thông tin và Truyền thông: Điều 9, Khoản 1.
- **Historical Demarcation:** Decision 226/QĐ-TTg (2016) is retained strictly under *"HISTORICAL / SUPERSEDED BACKGROUND"*.

### 2.2. Normalize 112 Governance
- **Problem:** Using "VINASARCOM / Bộ Quốc phòng" conflated the inter-agency steering committee with the statutory ministerial governing authority.
- **Correction:**
  - Canonical `governingAuthority`: **"Bộ Quốc phòng"** (Bộ Quốc phòng chủ trì).
  - Explicit `coordinationNote`: *"Liên thông với hệ thống 113, 114, 115 theo quy định hiện hành."*

### 2.3. Normalize 112 Display Scope
- **Problem:** Reducing 112 to "Search & Rescue" (Cứu nạn) narrowed its statutory role.
- **Statutory Mandate:** 112 receives information on:
  1. Sự cố (Incidents)
  2. Thiên tai (Natural disasters: typhoons, floods, landslides)
  3. Thảm họa (Catastrophes)
  4. Tai nạn / tình huống nguy cấp (Accidents / critical emergencies)
  5. Yêu cầu trợ giúp (Rescue and assistance requests)
- **UI Label:** `112 · Cứu nạn & tình huống nguy cấp`

### 2.4. Da Nang Visitor Center Physical Office Update
- **Problem:** Document and UI listed `108 Bạch Đằng, Đà Nẵng`.
- **Fact:** The Da Nang Visitor Center moved its headquarters to **18 Hùng Vương, Phường Hải Châu 1, Quận Hải Châu, TP. Đà Nẵng** in 2023.
- **Correction:** Removed `108 Bạch Đằng`; replaced with `18 Hùng Vương`.

### 2.5. Remove Unsourced Da Nang Operational Claims (UNKNOWN != FALSE)
- **Problem:** Asserting "Theo ca trực" (Shift-based) and "Cước cố định tiêu chuẩn" (Standard PSTN landline rate) without official documentation converted assumptions into purported facts.
- **Principle:** Where exact statutory evidence is absent:
  - `operatingHours = UNKNOWN`
  - `chargeStatus = UNKNOWN`
- **Correction:**
  - Purged "Theo ca trực", "Cước cố định", and "Không miễn phí".
  - UI renders neutral metadata label: `Thông tin hỗ trợ du khách`.

### 2.6. Hardening Conceptual Reference Data Schema
- **Problem:** Using `isFreeCall Boolean @default(false)` and `operatingHours String @default("24/7")` implicitly manufactured false claims when data was absent.
- **Correction:** Added explicit evidence state enums to conceptual schema (production `schema.prisma` remains strictly untouched):
  ```prisma
  enum MetadataEvidenceState {
    VERIFIED
    UNKNOWN
  }

  enum ChargeStatus {
    VERIFIED_FREE
    VERIFIED_CHARGED
    UNKNOWN
  }
  ```

### 2.7. Transition Roadmap Wording (Official Stages)
- **Problem:** Using `"2026–2027 integration / coexistence period"` read like an invented statutory code.
- **Official Roadmap:**
  - Giai đoạn 1 (Stage 1): Đến năm 2027.
  - Giai đoạn tiếp theo (Stage 2): 2027–2028.
- **Sourced Note:** *"Đề án tích hợp 113/114/115 đang được triển khai theo lộ trình; giai đoạn 1 đến năm 2027, giai đoạn tiếp theo 2027–2028."* (112, 113, 114, 115 remain concurrently active in GoMate V1).

### 2.8. Stale Audit Copy Cleansing
- **Section 3.3:** Corrected list from 113, 114, 115, 111 to Category A (112, 113, 114, 115) and Category B (111).
- **Section 3.7:** Corrected offline readiness to explicitly mention statutory emergency numbers (112, 113, 114, 115).

---

## 3. Visual Artifacts Regeneration Matrix (R1.1 Final)

| Mockup Artifact | Viewport | Resolution | R1.1 Final Corrections |
| :--- | :---: | :---: | :--- |
| [`safety-mobile-emergency-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1-r1-final.png) | Mobile | $390 \times 844$ | 1. 112 header: "Cứu nạn & nguy cấp", description "Bộ Quốc phòng chủ trì · Sự cố, thiên tai, nguy cấp".<br>2. Da Nang card: Address "18 Hùng Vương, Đà Nẵng", badge "Thông tin hỗ trợ du khách" (purged "Theo ca trực" & "Cước cố định").<br>3. Footnote: Sourced transition note ("Đề án tích hợp 113/114/115 đang được triển khai theo lộ trình; giai đoạn 1 đến năm 2027, giai đoạn tiếp theo 2027–2028"). |
| [`safety-desktop-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1-r1-final.png) | Desktop | $1440 \times 900$ | 1. 112 grid card: "Cứu nạn & tình huống nguy cấp", "Bộ Quốc phòng chủ trì · Sự cố, thiên tai, nguy cấp".<br>2. Da Nang card: "18 Hùng Vương, Đà Nẵng", badge "Thông tin hỗ trợ du khách" (no unsupported badges).<br>3. Col 3 roadmap note: Sourced transition text (Giai đoạn 1 đến 2027, giai đoạn tiếp theo 2027–2028). |

---

## 4. Acceptance Gate Verification

- [x] **112 uses current 2025 legal basis:** NĐ 200/2025/NĐ-CP, QĐ 2023/QĐ-TTg, QĐ 2024/QĐ-TTg.
- [x] **Decision 226 treated as historical only:** Documented under Historical/Superseded background.
- [x] **112 governing authority canonical = Bộ Quốc phòng:** Canonical authority is `Bộ Quốc phòng` (chủ trì); coordination note with 113, 114, 115.
- [x] **112 scope not artificially narrowed:** Covers sự cố, thiên tai, thảm họa, nguy cấp, yêu cầu trợ giúp.
- [x] **Da Nang address = 18 Hùng Vương:** Updated from outdated 108 Bạch Đằng.
- [x] **No unsupported Da Nang operating-hours claim:** Set to `UNKNOWN` (purged "Theo ca trực").
- [x] **No unsupported Da Nang telecom-charge claim:** Set to `UNKNOWN` (purged "Cước cố định" & "Không miễn phí").
- [x] **UNKNOWN metadata remains UNKNOWN:** UNKNOWN != FALSE; neutral label `Thông tin hỗ trợ du khách`.
- [x] **Conceptual schema can represent UNKNOWN:** Hardened with `ChargeStatus` and `MetadataEvidenceState` enums.
- [x] **Transition roadmap wording matches sourced stages:** Stage 1 until 2027, subsequent stage 2027–2028.
- [x] **Audit Section 3.3 includes 112 and separates 111:** Correct taxonomy applied.
- [x] **Offline section includes 112:** Statutory emergency services (112, 113, 114, 115) work over carrier voice.
- [x] **111 remains Cục Bà mẹ và Trẻ em — Bộ Y tế:** Verified authority retained.
- [x] **denied / deniedForever remains locked:** Distinct handling and CTAs preserved.
- [x] **Wandy emergency boundary unchanged:** Informational advice only; zero autonomous dispatch.
- [x] **No autonomous emergency actions:** Silent calling and automated mass actions strictly prohibited.
- [x] **git diff apps/ EMPTY:** Codebase strictly untouched.
- [x] **schema.prisma untouched:** Production PostgreSQL schema unmodified.
- [x] **weekly-report-W01.docx untouched / unstaged:** Preserved unstaged.
- [x] **no merge:** Maintained on `feature/gomate-visual-mockups`.
- [x] **no push:** Local commits only.

---

## 5. Subsequent Revision Addendum (TASK 08.2.3.15-R1.2)

For complete tracking of the Da Nang visitor support hotline update:
- In TASK 08.2.3.15-R1.2, official September 26, 2026 Da Nang tourism evidence established **`*8899`** as the current primary visitor support hotline.
- The historical fixed-line number `0236 3550 111` was reclassified as **Legacy / Historical Evidence (Current Operational Status = UNKNOWN)**.
- See full addendum in [`docs/audit/ui/task-08.2.3.15-r1.2-current-hotline-freshness-fix.md`](file:///d:/Do_an/wanderai/docs/audit/ui/task-08.2.3.15-r1.2-current-hotline-freshness-fix.md).

