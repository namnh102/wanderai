# GoMate Buddy Profile — Safety Honesty Micro-Fix Report (TASK 08.2.3.8-R1)

**Status:** APPROVED DESIGN & CONTRACT MICRO-FIX (R1 LOCKED)  
**Task:** TASK 08.2.3.8-R1 — GOMATE BUDDY PROFILE SAFETY HONESTY MICRO-FIX  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Strict Implementation Invariant:** Zero modifications to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, Prisma schema, or API contracts.

---

## 1. Executive Summary & Purpose

TASK 08.2.3.8-R1 executes targeted micro-corrections for **Buddy Profile V1** before Design Lock, focusing exclusively on **Safety Honesty**, **Runtime Support Realism**, and **GPS Privacy Copy Reassurance**.

---

## 2. Item-by-Item Correction Matrix

### Item 1 — Mobile Top App Bar Report Action
- **Before:** V1 mobile mockup rendered a prominent action button `"Báo cáo"` (flag icon) on the top App Bar.
- **Risk:** Overclaims runtime functionality; suggests to users and reviewers that reporting/blocking is active and functional in production, when the database currently lacks the underlying tables.
- **Source Evidence:**
  - `apps/backend/prisma/schema.prisma`: Zero models for `UserReport` or `UserBlock`.
  - Safety module is scheduled for separate design and backend implementation.
- **Correction:** Removed the direct `"Báo cáo"` action from the mobile top App Bar.
- **Final Contract:** The mobile App Bar features only the back arrow and title `"Hồ sơ bạn đồng hành"`. Safety actions are deferred to the dedicated Safety ecosystem.
- **Visual Artifact:** Regenerated as `docs/audit/evidence/ui-08.2.3.8/buddy-mobile-profile-r1.png`.

---

### Item 2 — Desktop Safety Card Annotation
- **Before:** Desktop sidebar rendered a safety box with `"Mục tiêu thiết kế"`.
- **Risk:** Ambiguity regarding whether the action is blocked or partially available.
- **Source Evidence:**
  - `UserBlock` and `UserReport` are `UNSAFE / BLOCKED DEPENDENCY`.
- **Correction:** The badge was updated to explicitly read:
  $$\textbf{DESIGN TARGET — BLOCKED}$$
- **Final Contract:** Clearly indicates in desktop workstation view that blocking/reporting requires database migrations before production readiness.
- **Visual Artifact:** Regenerated as `docs/audit/evidence/ui-08.2.3.8/buddy-desktop-profile-r1.png`.

---

### Item 3 — GPS Privacy Copy Reassurance
- **Before:** Desktop locked section read:
  - Row label: `Vị trí thời gian thực (GPS)`
  - Value: `Tuyệt đối không chia sẻ`
- **Risk:** Sounds abrupt and could raise questions about whether GoMate secretly tracks or stores live coordinates.
- **Source Evidence:**
  - `docs/design/gomate-buddy-profile-contract-v1.md` Section 5 (Tier 4 sensitive fields).
  - GoMate does not track or store live user GPS in candidate profiles.
- **Correction:** Refined to explicit privacy reassurance:
  - Row label: `Vị trí thời gian thực`
  - Reassurance text: `GoMate không hiển thị vị trí này trong hồ sơ bạn đồng hành.`
- **Final Contract:** Transparent, professional privacy reassurance confirming that live location is never collected or displayed on buddy profiles.

---

## 3. Regenerated Visual Artifacts Verification

Both master visual artifacts were updated and regenerated in `docs/audit/evidence/ui-08.2.3.8/`:

| Mockup File | Viewport | Resolution | Architectural Audit & R1 Refinements | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`buddy-mobile-profile-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.8/buddy-mobile-profile-r1.png) | Mobile | $390 \times 844$ | Clean App Bar without functional "Báo cáo" button; verified badge "Tài khoản đã xác minh"; age band 25–29; 3 checked compatibility reasons; locked phone/itinerary; "Gửi lời mời kết nối" CTA + safety note. Zero scrollbars. | **PASS** |
| [`buddy-desktop-profile-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.8/buddy-desktop-profile-r1.png) | Desktop | $1440 \times 900$ | Canonical 5-tab root navigation (Chuyến đi active); breadcrumb; refined GPS reassurance copy; safety box badged `DESIGN TARGET — BLOCKED`; full compatibility, preferences, and action footer. Zero scrollbars. | **PASS** |

---

## 4. Capability Status Matrix (Post-R1 Lock)

| Capability Area | Capability Status | Implementation Reality |
| :--- | :---: | :--- |
| **Public Buddy Profile** | **DESIGN TARGET** | DB models exist; public read API and UI missing. |
| **Profile Bio** | **CURRENT (DB) / PARTIAL (API)**| Bio persisted in DB; public endpoint missing. |
| **Age Band Privacy** | **DESIGN TARGET** | Computed server-side; exact DOB masked (`25–29 tuổi`). |
| **Travel Preferences** | **PARTIAL (DB Only)** | Enums in DB; public read API missing. |
| **Compatibility Reasons**| **DESIGN TARGET** | Explainable overlap criteria locked in UI. |
| **Private Contact Unlock**| **PARTIAL (DB Only)** | Model has phone; unlock logic requires match state. |
| **Trip Detail Sharing** | **CURRENT (API) / PARTIAL (UI)**| API exists for invite by email; UI pending. |
| **Connection Request** | **PARTIAL (DB Only)** | DB model exists; request API controller missing. |
| **Block User** | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserBlock`. |
| **Report User** | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserReport`. |

---

## 5. Source Code Integrity Verification

```powershell
git diff apps/
# Result: EMPTY (0 files modified)
```

No changes were made to Flutter client, NestJS backend, AI service, Prisma schema, or API contracts.
File `docs/weekly-reports/W01/weekly-report-W01.docx` remains unstaged.
