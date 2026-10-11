# GoMate Safety & Emergency — Authoritative Directory & Current-Governance Correction (TASK 08.2.3.15-R1)

**Status:** APPROVED ADDENDUM & DESIGN LOCK (R1 REVISION)  
**Task:** TASK 08.2.3.15-R1 — GOMATE SAFETY & EMERGENCY: AUTHORITATIVE DIRECTORY & CURRENT-GOVERNANCE CORRECTION  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Reference Design Contract:** [`docs/design/gomate-safety-emergency-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-safety-emergency-contract-v1.md)  
**Authoritative Source Card:** [`docs/design/data/gomate-emergency-contact-source-card-v1.md`](file:///d:/Do_an/wanderai/docs/design/data/gomate-emergency-contact-source-card-v1.md)  
**Primary Audit Document:** [`docs/audit/ui/task-08.2.3.15-safety-emergency-audit.md`](file:///d:/Do_an/wanderai/docs/audit/ui/task-08.2.3.15-safety-emergency-audit.md)  

---

## 1. Executive Context & Objective

TASK 08.2.3.15 established the baseline capability audit and safety contract for GoMate's root **An toàn (Safety & Emergency)** module. Following architectural review, TASK 08.2.3.15-R1 was initiated to execute targeted, authoritative corrections to Vietnam's national emergency taxonomy, regulatory governance assignments, operational metadata claims, offline telecom copy, and location permission state handling prior to final Design Lock.

```
+---------------------------------------------------------------------------------------------------+
|                                 TASK 08.2.3.15-R1 CORRECTION SCOPE                                |
+---------------------------------------------------------------------------------------------------+
| 1. National Directory Taxonomy: Separate Statutory Emergency (112-115) from Public Hotlines (111)  |
| 2. Add 112: National Search & Rescue / Civil Defence (VINASARCOM / Ministry of National Defence)  |
| 3. Correct 111 Governing Authority: Updated to Cục Bà mẹ và Trẻ em — Bộ Y tế                      |
| 4. 2026–2027 Integration Coexistence: Document 113 unification roadmap without retiring 114/115    |
| 5. Purge Blanket Badges: Replace global "24/7" / "Free" with per-entry verified operational rates |
| 6. Neutral Telecom Copy: Purge speculative "2G/3G/4G" promises in offline guidance                |
| 7. Location Permission Split: Differentiate temporary `denied` from permanent `deniedForever`     |
| 8. Regenerate 5 Affected Mockups: Update mobile home, emergency, denied, offline, and desktop     |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Before $\rightarrow$ Risk $\rightarrow$ Evidence $\rightarrow$ Correction Analysis

### 2.1. Omission of 112 (National Search & Rescue)

- **Before (Initial V1):** The emergency directory displayed 113, 114, and 115, completely omitting short-dial code `112`.
- **Life-Safety Risk:** Travelers trekking in mountainous regions (e.g. Sapa, Fansipan, Phong Nha), sea sports enthusiasts, or tourists stranded by flash floods and landslides require specialized search-and-rescue coordination across civil defense and armed forces. Omitting 112 leaves travelers without direct access to Vietnam's statutory rescue coordination center.
- **Authoritative Evidence:**
  - *Thông tư số 22/2014/TT-BTTTT* (Điều 9, Khoản 1): Formally reserves and regulates four emergency telecom numbers: `112`, `113`, `114`, `115`.
  - *Quyết định số 226/QĐ-TTg* của Thủ tướng Chính phủ: Phê duyệt Quy hoạch phát triển hệ thống thông tin cứu nạn khẩn cấp.
  - *VINASARCOM / Cục Cứu hộ - Cứu nạn (Bộ Quốc phòng)*: Operates 24/7, toll-free across all fixed and mobile carriers nationwide.
- **Correction Executed:**
  - Integrated `112` into Category A (Statutory National Emergency Services) across the data contract, source card, and UI mockups.
  - Clear operational scope: Maritime distress, mountain search, cave rescue, disaster evacuation.

---

### 2.2. Child Protection Hotline (111) Misclassification & Outdated Governance

- **Before (Initial V1):** `111` was grouped alongside 113, 114, and 115 under a single "National Emergency Services" banner, and attributed to *"Cục Trẻ em — Bộ Lao động - Thương binh và Xã hội"*.
- **Risk:**
  - *Telecommunications Misrepresentation:* Conflating a social welfare/protection hotline with blue-light emergency dispatch services distorts caller expectations during acute danger.
  - *Administrative Inaccuracy:* Attributing 111 to an outdated ministerial division contradicts current government organizational mandates.
- **Authoritative Evidence:**
  - *Quy hoạch Kho số Viễn thông (Thông tư 22/2014/TT-BTTTT):* 111 is designated as a national public welfare helpline, separate from emergency response dispatch numbers.
  - *Government Structural Realignment:* State management and operational oversight of the National Child Protection Hotline (111) belongs to **Cục Bà mẹ và Trẻ em — Bộ Y tế**.
- **Correction Executed:**
  - Created a dedicated section: **Đường dây nóng Bảo vệ & An sinh Xã hội** (Category B).
  - Explicitly updated governing agency text to **Cục Bà mẹ và Trẻ em — Bộ Y tế**.
  - Documented use cases: lost children during family travel, child abuse prevention, injury intervention.

---

### 2.3. Emergency Number Integration Roadmap (2026–2027 Coexistence Period)

- **Before (Initial V1):** No architectural guidance on Vietnam's ongoing 113/114/115 unification policy.
- **Risk:** Developers or designers might prematurely deprecate 114 and 115 under the assumption that 113 has already fully replaced them, stranding users unable to reach local fire or ambulance dispatch.
- **Authoritative Evidence:**
  - The Ministry of Public Security and Government IT modernization programs have initiated phased integration of emergency lines into unified 113 command centers.
  - However, full national transition remains an active multi-year program. In 2026–2027, provincial 114 and 115 centers operate in parallel with mutual dispatch interconnection.
- **Correction Executed:**
  - Formally specified `transitionStatus: "2026–2027 integration / coexistence period"`.
  - Locked contract invariant: **112, 113, 114, and 115 continue operating concurrently in GoMate V1.**
  - Added visible informational footnotes in client and desktop interfaces.

---

### 2.4. Purge Blanket "24/7" & "Miễn Phí" Claims (Per-Entry Metadata)

- **Before (Initial V1):** A global banner stated that all numbers on screen are "24/7 & Miễn phí", while the local Đà Nẵng visitor hotline (`0236 3550 111`) was listed directly underneath.
- **Consumer & Legal Risk:**
  - Đà Nẵng Visitor Center hotline (`0236 3550 111`) is a local fixed-line PSTN phone number operated by the Đà Nẵng Department of Tourism.
  - It operates during administrative hours and scheduled seasonal tourism shifts; it is **NOT** a 24/7/365 emergency center.
  - Calling `0236 3550 111` incurs standard telecommunications carrier landline rates; it is **NOT** toll-free.
  - Misleading travelers into believing a non-emergency desk is 24/7 free dispatch poses acute safety hazards.
- **Correction Executed:**
  - Completely purged global blanket badges.
  - Applied per-entry metadata badges:
    - 112, 113, 114, 115, 111: Display individual `[ 24/7 ]` and `[ Miễn phí ]` badges.
    - 0236 3550 111: Displays `[ Theo ca trực ]` and `[ Cước cố định ]` badges.

---

### 2.5. Neutral Telecom Copy (Purging "2G/3G/4G" Generation Commitments)

- **Before (Initial V1):** The offline safety screen claimed emergency calls function *"qua sóng di động 2G/3G/4G"*.
- **Technical Reality:**
  - Vietnam completed the 2G network sunset phase in late 2024 / 2025.
  - Promising 2G/3G fallback when legacy networks may be disabled or roaming on VoLTE/5G is technically inaccurate.
  - Furthermore, device emergency calling depends on carrier cellular coverage, active device hardware, and carrier roaming agreements.
- **Correction Executed:**
  - Adopted neutral, honest technical copy:
    > *"Cuộc gọi khẩn cấp sử dụng dịch vụ thoại của nhà mạng và không cần kết nối Internet. Khả năng gọi vẫn phụ thuộc vùng phủ sóng và dịch vụ viễn thông trên thiết bị."*

---

### 2.6. Location Permission State Split (`denied` vs. `deniedForever`)

- **Before (Initial V1):** The permission-denied mockup showed a single generic button `[ Cấp quyền vị trí ]`.
- **Platform Reality (Flutter `geolocator`):**
  - `LocationPermission.denied`: The user denied permission once. The OS allows the app to present the native runtime permission dialog again (`[ Cấp quyền vị trí ]`).
  - `LocationPermission.deniedForever`: The user checked "Don't ask again" or iOS permanently blocked the request. Calling `requestPermission()` will immediately return `deniedForever` without showing any OS dialog. The app **MUST** direct the user to system settings (`[ Mở Cài đặt hệ thống ]`).
- **Correction Executed:**
  - Sliced and documented the two distinct states.
  - Regenerated mockup `safety-mobile-location-permission-denied-v1-r1.png` specifically for `deniedForever`, providing the canonical `[ Mở Cài đặt hệ thống thiết bị ]` CTA while maintaining full fallback access to emergency hotlines (112, 113, 114, 115).

---

## 3. Visual Artifact Revision Matrix

5 affected mockups were regenerated at full native fidelity using Microsoft Edge headless rendering. 4 unaffected mockups are preserved from V1:

| Mockup Artifact | Status | R1 Revision Details | File Size | Dimensions |
| :--- | :---: | :--- | :---: | :---: |
| [`safety-mobile-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-home-v1-r1.png) | **REGENERATED** | Includes 112 in emergency SOS preview copy ("Cứu nạn 112, Cảnh sát 113, Cứu hỏa 114, Cấp cứu 115"). | 99.4 KB | $390 \times 844$ |
| [`safety-mobile-emergency-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1-r1.png) | **REGENERATED** | Added 112 rescue card; separated 111 under Cục Bà mẹ và Trẻ em — Bộ Y tế; per-entry badges for Đà Nẵng (Theo ca trực, Cước cố định); 2026–2027 coexistence footnote. | 114.2 KB | $390 \times 844$ |
| [`safety-mobile-emergency-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-confirm-v1.png) | **PRESERVED** | Confirmation modal for calling 115 with exact coordinates. Unchanged. | 87.2 KB | $390 \times 844$ |
| [`safety-mobile-trusted-contacts-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contacts-v1.png) | **PRESERVED** | List of trusted contacts with privacy banner. Unchanged. | 91.0 KB | $390 \times 844$ |
| [`safety-mobile-trusted-contact-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contact-add-v1.png) | **PRESERVED** | Add contact form with relationship chips and privacy card. Unchanged. | 78.4 KB | $390 \times 844$ |
| [`safety-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-v1.png) | **PRESERVED** | Foreground GPS coordinates, accuracy pill, mini-map, honesty notice. Unchanged. | 108.5 KB | $390 \times 844$ |
| [`safety-mobile-location-permission-denied-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-permission-denied-v1-r1.png) | **REGENERATED** | Explicit `deniedForever` state; primary CTA `[ Mở Cài đặt hệ thống thiết bị ]`; hotlines fallback card includes 112, 113, 114, 115. | 86.8 KB | $390 \times 844$ |
| [`safety-mobile-offline-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-offline-v1-r1.png) | **REGENERATED** | Neutral telecom copy (purged 2G/3G/4G text); added 112 card; cached GPS coordinates. | 101.3 KB | $390 \times 844$ |
| [`safety-desktop-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1-r1.png) | **REGENERATED** | 3-column desktop hub: 112 added to quick dial and emergency grid; 111 separated under Cục Bà mẹ và Trẻ em — Bộ Y tế; per-entry metadata; 2026–2027 coexistence roadmap card. | 134.1 KB | $1440 \times 900$ |

---

## 4. Locked Reference Data Specification (Authoritative Grounding)

```prisma
// Reference Data Schema: EmergencyDirectoryEntry (Post-R1 Locked Spec)
model EmergencyDirectoryEntry {
  id               String    @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  countryCode      String    @map("country_code") @db.VarChar(2) // "VN"
  regionCode       String?   @map("region_code") @db.VarChar(10) // "DAD", "HAN", null (national)
  category         String    @db.VarChar(50) // "emergency_rescue", "emergency_police", "emergency_fire", "emergency_medical", "protection_child", "tourist"
  displayName      String    @map("display_name") @db.VarChar(150)
  phoneNumber      String    @map("phone_number") @db.VarChar(30)
  sourceUrl        String    @map("source_url") @db.Text
  sourceName       String    @map("source_name") @db.VarChar(150)
  verifiedAt       DateTime  @map("verified_at") @db.Date
  isFreeCall       Boolean   @default(false) @map("is_free_call")
  operatingHours   String    @default("24/7") @map("operating_hours") @db.VarChar(50)
  transitionStatus String?   @map("transition_status") @db.VarChar(100) // "2026–2027 integration / coexistence period"

  @@index([countryCode, regionCode])
}
```

---

## 5. Verification & Acceptance Sign-off

- [x] **Directory Taxonomy Split:** Statutory services (112, 113, 114, 115) strictly differentiated from social protection lines (111).
- [x] **Search & Rescue Grounding:** 112 added with statutory citation (Thông tư 22/2014/TT-BTTTT & Quyết định 226/QĐ-TTg).
- [x] **111 Authority Corrected:** Updated from outdated MOLISA to **Cục Bà mẹ và Trẻ em — Bộ Y tế**.
- [x] **Transition Honesty:** 2026–2027 coexistence period documented; 114 and 115 remain active.
- [x] **Blanket Claims Purged:** Đà Nẵng hotline verified as shift-based & PSTN landline rate.
- [x] **Neutral Telecom Guidance:** Network generation speculation purged from offline UX.
- [x] **Permission Slicing:** Dedicated `deniedForever` CTA and fallback path verified.
- [x] **5 R1 Mockups Rendered & Inspected:** Headless Edge screenshots verified at 390x844 and 1440x900.
- [x] **Apps Code Untouched:** `git diff apps/` is strictly empty.
- [x] **Prisma Production Untouched:** Zero changes to `schema.prisma`.
- [x] **Branch Isolation:** `feature/gomate-visual-mockups` preserved; no merge, no push.
