# GoMate Safety & Emergency — Capability & Architectural Audit (TASK 08.2.3.15 / R1 Revision)

**Status:** APPROVED ARCHITECTURAL AUDIT & CONTRACT LOCK (R1 REVISION)  
**Task:** TASK 08.2.3.15-R1 — GOMATE SAFETY & EMERGENCY: AUTHORITATIVE DIRECTORY & CURRENT-GOVERNANCE CORRECTION  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:**
- Database Schema: [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) (`model SafetyContact`, `model SafetyCheckin`, `model EmergencyEvent`, lines 598–645)
- Backend Source Code: [`apps/backend/src/`](file:///d:/Do_an/wanderai/apps/backend/src/)
- Mobile Client Code: [`apps/mobile/lib/core/router/app_router.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/core/router/app_router.dart)
- Mobile Client Location: [`apps/mobile/lib/features/location/providers/user_location_provider.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/location/providers/user_location_provider.dart)
- Mobile Client Dependencies: [`apps/mobile/pubspec.yaml`](file:///d:/Do_an/wanderai/apps/mobile/pubspec.yaml)
- Primary Design Contract: [`docs/design/gomate-safety-emergency-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-safety-emergency-contract-v1.md)
- Authoritative Source Card: [`docs/design/data/gomate-emergency-contact-source-card-v1.md`](file:///d:/Do_an/wanderai/docs/design/data/gomate-emergency-contact-source-card-v1.md)
- Master Visual Evidence Artifacts:
  - Mobile Safety Home V1 (R1): [`safety-mobile-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-home-v1-r1.png) ($390 \times 844$)
  - Mobile Emergency Directory V1 (R1): [`safety-mobile-emergency-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1-r1.png) ($390 \times 844$)
  - Mobile Emergency Confirmation V1: [`safety-mobile-emergency-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-confirm-v1.png) ($390 \times 844$)
  - Mobile Trusted Contacts V1: [`safety-mobile-trusted-contacts-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contacts-v1.png) ($390 \times 844$)
  - Mobile Add Trusted Contact V1: [`safety-mobile-trusted-contact-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contact-add-v1.png) ($390 \times 844$)
  - Mobile Location Safety V1: [`safety-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-v1.png) ($390 \times 844$)
  - Mobile Location Permission Denied V1 (R1): [`safety-mobile-location-permission-denied-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-permission-denied-v1-r1.png) ($390 \times 844$)
  - Mobile Offline Safety V1 (R1): [`safety-mobile-offline-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-offline-v1-r1.png) ($390 \times 844$)
  - Desktop Safety Master V1 (R1): [`safety-desktop-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1-r1.png) ($1440 \times 900$)

---

## 1. Executive Summary & Audit Verdict

TASK 08.2.3.15 executes a comprehensive codebase capability audit and architectural design lock for the **GoMate Safety & Emergency** module.

### Key Audit Findings:
1. **Existing Safety Tab Status (Static Placeholder):**
   - The Flutter mobile client declares `/safety` in [`apps/mobile/lib/core/router/app_router.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/core/router/app_router.dart#L126), but binds it directly to `_PlaceholderScreen(title: 'An toàn', icon: Icons.shield)`.
   - Clicking the `An toàn` tab in the running app displays an icon and text: *"Tính năng đang phát triển..."*.
   - **Verdict:** Root tab destination exists in the navigation shell, but the screen is a **STATIC PLACEHOLDER SCREEN**.
2. **Database Schema Reality (`schema.prisma` lines 598–645):**
   - 3 safety models exist in PostgreSQL schema: `model SafetyContact`, `model SafetyCheckin`, `model EmergencyEvent`.
   - However, **zero backend controllers or services** exist in `apps/backend/src/` referencing these models.
   - **Verdict:** Schema definitions exist, but backend runtime is **MISSING**.
3. **Emergency Dialer Launching (`url_launcher`):**
   - `url_launcher: ^6.2.0` is installed and verified operational via `tel:` intent in place details.
   - **Verdict:** CURRENT capability for launching the native phone dialer with user confirmation.
4. **Location Safety Reality (`geolocator`):**
   - `geolocator: ^13.0.2` is installed and provides high-precision foreground GPS coordinates with accuracy radius ($\pm\text{meters}$).
   - Background tracking and live location streaming are **100% MISSING**.
   - **Verdict:** FOREGROUND GPS IS CURRENT; BACKGROUND AND LIVE SHARING ARE MISSING / FUTURE.
5. **Critical Safety Principle Locked:**
   - **AI MUST NEVER be a required intermediary for urgent emergency action.**
   - Wandy AI provides static safety guides and preparedness checklists, but cannot trigger autonomous calls, messages, or GPS broadcasts.
6. **Zero Fabrication Policy & Authoritative Directory Correction (R1):**
   - Statutory National Emergency Services (112, 113, 114, 115) sourced from Circular No. 22/2014/TT-BTTTT.
   - 112 added with official governance: VINASARCOM / Cục Cứu hộ - Cứu nạn (Bộ Quốc phòng), 24/7, Free call.
   - 111 separated into National Public Safety / Protection Hotlines and updated to current governing authority: **Cục Bà mẹ và Trẻ em — Bộ Y tế**.
   - 2026–2027 transition coexistence note documented: 114 and 115 continue operating concurrently alongside 113.
   - Sourced per-entry metadata replaces blanket claims: Đà Nẵng hotline (0236 3550 111) is shift-based and standard PSTN rate (NOT 24/7, NOT free).
   - Documented in [`docs/design/data/gomate-emergency-contact-source-card-v1.md`](file:///d:/Do_an/wanderai/docs/design/data/gomate-emergency-contact-source-card-v1.md).
7. **Social Safety Gap (Block & Report):**
   - `UserBlock` and `UserReport` models are absent from `schema.prisma`.
   - **Verdict:** SCHEMA GAP / SAFETY DEPENDENCY (decoupled from the Emergency SOS Hub).

---

## 2. Technical Evidence & Codebase Inspection Logs

### 2.1. Mobile Client Inspection
- File: [`apps/mobile/lib/core/router/app_router.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/core/router/app_router.dart)
  - Lines 18–46: Definition of `_PlaceholderScreen`:
    ```dart
    class _PlaceholderScreen extends StatelessWidget {
      final String title;
      final IconData icon;
      // ... renders 'Tính năng đang phát triển...'
    }
    ```
  - Line 126: `GoRoute(path: '/safety', builder: (_, __) => const _PlaceholderScreen(title: 'An toàn', icon: Icons.shield)),`
  - Lines 173–177: NavigationDestination with `Icons.shield_outlined` / `Icons.shield` labeled `'An toàn'`.
- File: [`apps/mobile/pubspec.yaml`](file:///d:/Do_an/wanderai/apps/mobile/pubspec.yaml)
  - `geolocator: ^13.0.2` (Present)
  - `url_launcher: ^6.2.0` (Present)
  - `flutter_map: ^7.0.0` (Present)
  - Telephony direct call plugins (`flutter_phone_direct_caller`): **MISSING**
  - SMS plugins (`flutter_sms`): **MISSING**
  - Background location plugins (`background_locator`, `workmanager`): **MISSING**

### 2.2. Backend Inspection
- File: [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma)
  - Lines 602–613: `model SafetyContact { id, userId, name, phone, relation, createdAt, user }`
  - Lines 615–626: `model SafetyCheckin { id, userId, latitude, longitude, note, createdAt, user }`
  - Lines 628–645: `enum EmergencyStatus { ACTIVE, RESOLVED, FALSE_ALARM }`, `model EmergencyEvent { id, userId, latitude, longitude, status, message, resolvedAt, createdAt }`
- Search for controllers/services in `apps/backend/src/`:
  - Command: `Get-ChildItem -Path apps/backend/src -Recurse -Include *.ts | Select-String -Pattern "SafetyContact|SafetyCheckin|EmergencyEvent"`
  - Result: **0 matches**. The tables in `schema.prisma` have zero operational NestJS controllers, DTOs, or modules.
- Search for moderation models (`UserBlock`, `UserReport`):
  - Command: `Select-String -Path apps/backend/prisma/schema.prisma -Pattern "Block|Report"`
  - Result: **0 matches**.

### 2.3. AI Service Inspection (`apps/ai-service/`)
- RAG evaluation chunker includes "safety" as a topic for travel tips (e.g. taxi safety in Vietnam from Wikivoyage).
- Zero SOS handling, zero dispatch endpoints.

---

## 3. Core Architectural Decisions

### 3.1. Safety is a First-Class Root Destination
- Unlike contextual trip features (Itinerary, Expense, Chat), Safety is not buried inside a trip.
- A traveler in danger can tap `An toàn` directly from any screen in the app.

### 3.2. Emergency Path Decoupled from AI
$$\text{User} \quad \mathbf{\longrightarrow} \quad \text{Safety} \quad \mathbf{\longrightarrow} \quad \text{Emergency Action (OS Dialer)}$$
AI must never delay, filter, or reason over life-threatening emergency situations.

### 3.3. Authoritative Emergency Directory (Zero Fabrication)
- Emergency numbers must be backed by official statutory sources.
- Vietnam National Hotlines: `113` (Police), `114` (Fire/Rescue), `115` (Ambulance), `111` (Child Protection).
- Local Tourism Hotline: `0236 3550 111` (Đà Nẵng Visitor Support Center).
- All numbers documented in [`gomate-emergency-contact-source-card-v1.md`](file:///d:/Do_an/wanderai/docs/design/data/gomate-emergency-contact-source-card-v1.md).

### 3.4. Emergency Action Semantics (Explicit OS Dialer Handoff)
- Every call action requires an explicit confirmation bottom sheet displaying target number and current GPS coordinates.
- System opens the native OS phone dialer (`tel:115`) via `url_launcher`.
- Silent background calling without dialer interaction is strictly prohibited.

### 3.5. Sensitive Privacy Lock for Trusted Contacts
- Saved in `model SafetyContact`.
- Completely isolated from Group Chat, Buddy Discovery, public profile, and Trip members.
- Deleting a trip does **NOT** delete personal trusted contacts.
- Capped at 3 contacts in V1.

### 3.6. Location Safety Honesty (Foreground Fix Only)
- Reads current GPS fix via `geolocator` while app is in foreground.
- Renders explicit accuracy status: `±15 m (Tốt)`.
- Background tracking and continuous live location sharing are rejected as current capabilities and classified as future targets.

### 3.7. Offline Readiness
- 113, 114, 115 operate over cellular mobile networks without needing 4G or Wifi.
- Client bundles static numbers in cache, ensuring zero dead-ends during network loss.

---

## 4. Capability Matrix (24 Dimensions)

| Dimension | Database | Backend | Flutter | AI Service | Design Contract | Status | Evidence |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. Safety Root Tab** | N/A | N/A | Partial | N/A | Section 1 | **PLACEHOLDER** | `_PlaceholderScreen` in `app_router.dart` line 126. |
| **2. Emergency Directory Data** | Missing | Missing | Missing | N/A | Section 4 | **REFERENCE DATA** | Authoritative source card defined; statutory numbers. |
| **3. Emergency Dialer Launch** | N/A | N/A | Current | N/A | Section 5 | **CURRENT** | `url_launcher` with `tel:` intent in place details. |
| **4. Direct Background Call** | Excluded | Excluded | Excluded | Excluded | Section 5 | **PROHIBITED** | User retains final OS dialer confirmation authority. |
| **5. Trusted Contact DB Model** | Partial | Missing | Missing | N/A | Section 6 | **SCHEMA ONLY** | `model SafetyContact` in `schema.prisma` lines 602–613. |
| **6. Trusted Contact API** | Missing | Missing | Missing | N/A | Section 6 | **DESIGN TARGET** | No controller/service in `apps/backend/src/`. |
| **7. Trusted Contact UI** | Missing | Missing | Missing | N/A | Section 6 | **DESIGN LOCKED** | 2 mobile mockups locked; zero Flutter code today. |
| **8. Trusted Contact Privacy**| Locked | Locked | Locked | Locked | Section 6 | **STRICTLY PRIVATE**| Creator-only; isolated from social and trip members. |
| **9. Foreground GPS Reading** | N/A | N/A | Current | N/A | Section 7 | **CURRENT** | `user_location_provider.dart` using `geolocator`. |
| **10. Location Permission Flow** | N/A | N/A | Current | N/A | Section 7 | **CURRENT** | `checkPermission()` & `requestPermission()`. |
| **11. Location Accuracy Grading** | N/A | N/A | Current | N/A | Section 7 | **CURRENT** | `LocationAccuracyQuality` (good, approx, poor). |
| **12. Live Location Sharing** | Missing | Missing | Missing | N/A | Section 8 | **FUTURE SPEC** | Requires websocket / sync server; ephemeral opt-in. |
| **13. Background Location Tracking**| Missing | Missing | Missing | N/A | Section 7 | **EXCLUDED** | No background service or permissions in manifest. |
| **14. Location Persistence** | Partial | Missing | Missing | N/A | Section 7 | **SCHEMA ONLY** | `model SafetyCheckin` in `schema.prisma` line 615. |
| **15. SOS Action Hub** | Missing | Missing | Missing | N/A | Section 9 | **DESIGN LOCKED** | Multi-channel action hub (Hotlines, Contacts, GPS). |
| **16. Autonomous Emergency Chain** | Excluded | Excluded | Excluded | Excluded | Section 9 | **PROHIBITED** | No automated mass actions on single click. |
| **17. Emergency SMS Sending** | Missing | Missing | Missing | N/A | Section 9 | **FUTURE SPEC** | No SMS plugins in `pubspec.yaml`. |
| **18. Offline Emergency Directory**| Missing | Missing | Missing | N/A | Section 10 | **DESIGN LOCKED** | Static numbers cached in client bundle. |
| **19. Wandy Safety Assistance** | N/A | N/A | N/A | Partial | Section 3 | **DESIGN LOCKED** | RAG guides on safety; advisory checklists only. |
| **20. Wandy Autonomous Dispatch** | Excluded | Excluded | Excluded | Excluded | Section 3 | **PROHIBITED** | Wandy cannot trigger calls, SMS, or GPS sharing. |
| **21. User Block Capability** | Missing | Missing | Missing | N/A | Section 12 | **SCHEMA GAP** | No `model UserBlock` in `schema.prisma`. |
| **22. User Report Capability** | Missing | Missing | Missing | N/A | Section 12 | **SCHEMA GAP** | No `model UserReport` in `schema.prisma`. |
| **23. Message Report Capability** | Missing | Missing | Missing | N/A | Section 12 | **SCHEMA GAP** | No message moderation in Group Chat. |
| **24. Trip Deletion Impact** | Locked | Locked | Locked | N/A | Section 6 | **DESIGN LOCKED** | Deleting trips preserves personal trusted contacts. |

---

## 5. Master Mockup Verification (9 Master Artifacts — R1 Revision)

All 9 master mockups were rendered via headless Microsoft Edge browser at native resolutions and verified in `docs/audit/evidence/ui-08.2.3.15/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`safety-mobile-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-home-v1-r1.png) | Mobile | $390 \times 844$ | 1. Status bar `9:41 5G 100%` + App bar `An toàn & Cứu trợ`.<br>2. Emergency SOS card displaying national services (112, 113, 114, 115) with `[ Mở danh bạ cứu trợ khẩn cấp › ]`.<br>3. Location safety card: Coordinates, locality, accuracy `±15 m (Tốt)`.<br>4. Trusted contacts summary (2/3 contacts) with private lock tag.<br>5. Travel safety handbook card.<br>6. Product disclaimer footnote.<br>7. Canonical 5-tab root navigation with `An toàn` active. | **PASS (LOCKED R1)** |
| [`safety-mobile-emergency-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1-r1.png) | Mobile | $390 \times 844$ | 1. App bar `< Danh bạ cứu trợ & bảo vệ` + Subtitle.<br>2. Sourced free-call notice for 112, 113, 114, 115, 111.<br>3. National emergency services section: 112 (Cứu nạn), 113 (Công an), 114 (Cứu nạn & PCCC), 115 (Cấp cứu) with individual 24/7 & free badges.<br>4. Separated National Child Protection Hotline section: 111 (Cục Bà mẹ và Trẻ em — Bộ Y tế).<br>5. Local tourist support: 0236 3550 111 (Đà Nẵng Visitor Center) with accurate "Theo ca trực" & "Cước cố định" badges.<br>6. Transition roadmap footnote for 2026–2027 coexistence.<br>7. Canonical 5-tab bottom navigation. | **PASS (LOCKED R1)** |
| [`safety-mobile-emergency-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-confirm-v1.png) | Mobile | $390 \times 844$ | 1. Dark semi-transparent modal overlay.<br>2. Confirmation sheet: `Gọi Cấp cứu Y tế 115?`.<br>3. Exact GPS coordinates and locality display for dispatcher communication.<br>4. Primary CTA: `[ Mở trình quay số 115 ]` (Red).<br>5. Secondary: `[ Hủy bỏ ]`. Zero silent calling. | **PASS (LOCKED)** |
| [`safety-mobile-trusted-contacts-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contacts-v1.png) | Mobile | $390 \times 844$ | 1. App bar `< Người liên hệ tin cậy` with `+ Thêm`.<br>2. Sensitive privacy guarantee banner (creator-only, hidden from group/profile).<br>3. 2 contact cards with `[ Mở cuộc gọi ]`, `[ Sửa ]`, `[ Xóa ]`.<br>4. Clarification note: Calls open OS dialer; deleting trips preserves contacts.<br>5. Canonical 5-tab bottom navigation. | **PASS (LOCKED)** |
| [`safety-mobile-trusted-contact-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contact-add-v1.png) | Mobile | $390 \times 844$ | 1. App bar `Hủy`, `Thêm người liên hệ`, `Lưu`.<br>2. Form inputs: Full Name \*, Phone Number \*, Relationship chips.<br>3. Privacy commitment card explaining data protection.<br>4. Primary CTA: `[ Lưu người liên hệ tin cậy ]`. Clean layout contained in $844\text{px}$. | **PASS (LOCKED)** |
| [`safety-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-v1.png) | Mobile | $390 \times 844$ | 1. Mini map visual snippet with user marker and pulse halo.<br>2. GPS data: Coordinates `16.054400° N, 108.202200° E`, accuracy `±15 m (Tốt)`, timestamp.<br>3. Technical honesty disclosure: Foreground read only, no background tracking, no live sharing.<br>4. Actions: `[ Làm mới tọa độ GPS ]`, `[ Sao chép tọa độ ]`.<br>5. Canonical 5-tab bottom navigation. | **PASS (LOCKED)** |
| [`safety-mobile-location-permission-denied-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-permission-denied-v1-r1.png) | Mobile | $390 \times 844$ | 1. Orange shield icon + `Quyền truy cập vị trí đang bị tắt vĩnh viễn`.<br>2. Clear status: `deniedForever` explaining why system dialog cannot re-prompt.<br>3. Action button: `[ Mở Cài đặt hệ thống thiết bị ]` (strictly differentiated from temporary denial).<br>4. Safe Fallback section: Direct access to 112, 113, 114, 115 hotlines maintained (never traps user).<br>5. Canonical 5-tab bottom navigation. | **PASS (LOCKED R1)** |
| [`safety-mobile-offline-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-offline-v1-r1.png) | Mobile | $390 \times 844$ | 1. Offline status badge and banner.<br>2. Neutral telecom capability notice (phone call requires carrier network coverage, independent of Internet; omitted speculative 2G/3G/4G text).<br>3. Static cached emergency hotlines: 112, 113, 114, 115.<br>4. Cached last-known GPS fix.<br>5. Canonical 5-tab bottom navigation. | **PASS (LOCKED R1)** |
| [`safety-desktop-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1-r1.png) | Desktop | $1440 \times 900$ | 1. Top nav: Logo `GoMate` + badge `Safety Hub` + Canonical 5 tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi`, `An toàn` [Active]) + User pill.<br>2. Col 1 ($280\text{px}$): Safety menu & quick hotline box (112, 113, 114, 115, 111).<br>3. Col 2 ($780\text{px}$): National Emergency Grid (112, 113, 114, 115) + Separate row for 111 & Đà Nẵng hotline (with per-entry metadata, no global 24/7 or free claims) + Foreground Location Safety card.<br>4. Col 3 ($340\text{px}$): Trusted contacts widget + Wandy Safety Copilot card (advisory only) + 2026–2027 transition roadmap note.<br>5. Zero debug labels; perfectly contained in $900\text{px}$. | **PASS (LOCKED R1)** |

---

## 6. Design Acceptance Gate (TASK 08.2.3.15 & R1 Revision)

- [x] **Repository capability audit complete:** Identified `_PlaceholderScreen`, audited Prisma models and backend gap.
- [x] **Existing Safety tab truthfully classified:** Formally documented as STATIC PLACEHOLDER SCREEN.
- [x] **Emergency number sources documented:** Created [`gomate-emergency-contact-source-card-v1.md`](file:///d:/Do_an/wanderai/docs/design/data/gomate-emergency-contact-source-card-v1.md).
- [x] **Statutory National Directory Complete (R1):** Sourced 112 (Search & Rescue / VINASARCOM), 113 (Police), 114 (Fire/Rescue), 115 (Ambulance).
- [x] **Taxonomy split (R1):** 111 separated from statutory emergency services into National Public Safety / Protection Hotlines.
- [x] **111 Governing authority corrected (R1):** Updated to **Cục Bà mẹ và Trẻ em — Bộ Y tế**.
- [x] **2026–2027 Coexistence transition documented (R1):** 114 and 115 continue operating concurrently with 113.
- [x] **Per-entry metadata enforced (R1):** Đà Nẵng hotline (0236 3550 111) correctly labeled shift-based & PSTN landline charge (no blanket 24/7 / free claim).
- [x] **Neutral telecom copy (R1):** Removed generation-specific "2G/3G/4G" promises.
- [x] **Permission state split (R1):** Differentiated `denied` (`[ Cấp quyền vị trí ]`) vs `deniedForever` (`[ Mở Cài đặt hệ thống ]`).
- [x] **Emergency calls require explicit tap:** Explicit confirmation sheet before handoff.
- [x] **No autonomous emergency call:** Silent background calling strictly forbidden.
- [x] **Trusted contacts separated:** Distinct from Buddy / GroupMember / TripMember.
- [x] **Trusted contact privacy locked:** Isolated from social features and group chats.
- [x] **Current location != live sharing:** Foreground single fix strictly separated from live broadcast.
- [x] **Background location not assumed:** Truthfully excluded from V1 capabilities.
- [x] **Location consent explicit:** Requires OS permission and explicit refresh tap.
- [x] **Location sharing OFF by default:** Future sharing requires duration and instant revocation.
- [x] **Wandy cannot trigger emergency side effects:** Wandy locked to informational guidance only.
- [x] **Offline/failure UX defined:** Emergency calls work via cellular without Internet; permission denied state provides safe hotline fallback.
- [x] **UserBlock/UserReport gaps audited:** Classified as SCHEMA GAP / SAFETY DEPENDENCY.
- [x] **Canonical 5-tab IA preserved:** `Khám phá` | `Bản đồ` | `Wandy AI` | `Chuyến đi` | `An toàn` [Active].
- [x] **No technical debug text in UI:** Clean customer copy, zero stacktraces or HTTP error codes.
- [x] **No production code changes:** `git diff apps/` is strictly empty.
- [x] **No Prisma changes:** `apps/backend/prisma/schema.prisma` is unmodified.
- [x] **No API changes:** API contracts intact.
- [x] **No merge:** Working branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
