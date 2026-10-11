# GoMate Buddy Match Request & Mutual Consent Lifecycle — Runtime Honesty & Integration Contract Correction (TASK 08.2.3.9-R1)

**Status:** APPROVED MICRO-CORRECTION & CONTRACT LOCK  
**Task:** TASK 08.2.3.9-R1 — GOMATE BUDDY MATCH CONSENT RUNTIME HONESTY & INTEGRATION CONTRACT FIX  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Strict Implementation Invariant:** Zero modifications to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`, Prisma schema, or API contracts.

---

## 1. Executive Summary

TASK 08.2.3.9-R1 executes targeted micro-corrections for the **Buddy Match Request & Mutual Consent Lifecycle V1** prior to Design Lock. It addresses 8 specific inconsistencies related to runtime honesty, API-privacy collisions, third-party assumptions, notification overclaims, and copy boundaries.

---

## 2. Itemized Corrections (Before $\rightarrow$ Risk $\rightarrow$ Source Evidence $\rightarrow$ Correction $\rightarrow$ Final Contract)

### Fix #1: Notification Overclaim in Pending State
- **Before:** Sender pending banner read: *"Bạn sẽ nhận được thông báo khi lời mời được chấp nhận."*
- **Risk:** Falsely promises real-time push notification delivery when backend has zero push services.
- **Source Evidence:** `apps/backend/src/modules/` contains no push notification module (no FCM, no APNs).
- **Correction:** Replaced with truthful status check copy:
  $$\textbf{"Đang chờ Lê Hoàng Nam phản hồi. Bạn có thể kiểm tra trạng thái tại mục Lời mời đồng hành."}$$
- **Final Contract:** Push notifications remain `DESIGN TARGET — REQUIRES NOTIFICATION SERVICE`. Mockup regenerated: [`buddy-mobile-request-pending-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-pending-r1.png).

---

### Fix #2: Canonical Verification Copy
- **Before:** Incoming request card displayed ambiguous label `"Đã xác minh"`.
- **Risk:** Ambiguity over whether identity, government ID, or just email/account registration was verified.
- **Source Evidence:** `model User { isVerified Boolean }` in `prisma/schema.prisma` reflects basic account authentication.
- **Correction:** Standardized label across all surfaces to:
  $$\textbf{"Tài khoản đã xác minh"}$$
- **Final Contract:** Never use `"Đã xác minh"` or `"Đã xác minh danh tính"` for basic `isVerified`. Mockup regenerated: [`buddy-mobile-request-received-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-received-r1.png).

---

### Fix #3: Trip Invite Contract Mismatch & Safe Adapter Architecture
- **Before:** "Mời vào chuyến đi" was classified as `CURRENT API / PARTIAL UI` referencing `POST /trips/:id/members`.
- **Risk:** `POST /trips/:id/members` requires `{ email: string }`, but `User.email` is **Tier 4 — SYSTEM PRIVATE / NEVER EXPOSED / NEVER DISCOVERABLE**. Supplying email to the Buddy frontend breaks GoMate's fundamental privacy architecture.
- **Source Evidence:** `apps/backend/src/modules/trips/trips.controller.ts` lines 24–28 & 96–105 (`InviteMemberDto` requires `email`).
- **Correction:** Reclassified "Mời vào chuyến đi" to:
  $$\textbf{PARTIAL / DESIGN TARGET — REQUIRES SAFE USER-ID OR MATCH-ID ADAPTER}$$
- **Final Contract:** Backend must introduce safe adapter `POST /trips/:tripId/members/from-match` (`{ matchId }`) or `POST /trips/:tripId/members/by-user` (`{ userId }`). Email must never be returned or exposed to Buddy UI.

---

### Fix #4: Accepted Contact Action & Demo Data Disclaimer
- **Before:** Unlocked phone box rendered action button `"Gọi / Zalo"` without a disclaimer on the realistic phone number.
- **Risk:** Assumes unverified third-party app installation, phone-Zalo linkage, and deep-link protocol; implies the mock number belongs to a real person.
- **Source Evidence:** No Zalo SDK or deep-link handler exists in `apps/mobile/`.
- **Correction:** 
  1. Removed `"Gọi / Zalo"`. Replaced with honest interaction `[Sao chép số]`.
  2. Added explicit visual demo data disclaimer:
     $$\textbf{"Dữ liệu mẫu hiển thị · Không phải số thực tế (Visual demo data)"}$$
- **Final Contract:** Contact unlock exposes phone number cleanly. Copy action is classified as DESIGN TARGET. Mockup regenerated: [`buddy-mobile-match-accepted-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-match-accepted-r1.png).

---

### Fix #5: Chat Entry Boundary Honesty
- **Before:** Accepted screen rendered a secondary action button `"Nhắn tin"`.
- **Risk:** Implies direct in-app messaging is functional in the current runtime.
- **Source Evidence:** `model Group` and `model Message` exist in schema, but NestJS has no WebSocket gateway or chat controller.
- **Correction:** Removed `"Nhắn tin"` button from the master accepted screen. Bottom action bar renders only `[+ Mời vào chuyến đi (Mục tiêu thiết kế)]`.
- **Final Contract:** Chat entry is strictly deferred to the dedicated Group Chat design task.

---

### Fix #6: GPS Scope Scoped to Buddy Connection
- **Before:** Desktop safety sidebar used global phrasing: *"Vị trí thời gian thực (GPS) tuyệt đối không bao giờ được chia sẻ."*
- **Risk:** Creates an unintended contractual conflict with future emergency Safety SOS features that may require explicit, user-controlled location sharing.
- **Source Evidence:** Architectural boundary between Buddy discovery and Safety SOS.
- **Correction:** Scoped copy specifically to Buddy companions:
  $$\textbf{"Vị trí thời gian thực không được chia sẻ trong kết nối bạn đồng hành."}$$
- **Final Contract:** Global safety module is not restricted. Mockup regenerated: [`buddy-desktop-requests-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-desktop-requests-r1.png).

---

### Fix #7: Configurable Rejection Cooldown Rule
- **Before:** Contract asserted a hard-coded "30-day cooldown" after rejection.
- **Risk:** Hard-codes an arbitrary duration not backed by backend logic, Prisma columns (`updatedAt` is missing), or formal product approval.
- **Source Evidence:** `model Match` lacks `updatedAt` field; backend has no rejection query filter.
- **Correction:** Reclassified from fixed 30-day rule to:
  $$\textbf{"Configurable rejection cooldown — TBD" (DESIGN TARGET / PRODUCT POLICY REQUIRED)}$$
- **Final Contract:** Policy duration will be determined upon backend implementation with appropriate database schema migration.

---

### Fix #8: Rejection Copy & Notification Absence
- **Before:** Rejection screen stated: *"Đối phương sẽ không nhận được thông báo mang tính tiêu cực..."*
- **Risk:** Implies the system selectively filters push notifications when no notification service exists at all.
- **Source Evidence:** Absence of notification service in backend.
- **Correction:** Replaced with neutral, supportive privacy copy:
  $$\textbf{"Bạn đã từ chối lời mời. Thông tin cá nhân của bạn vẫn được giữ kín. Người này không bị chặn trong hệ thống GoMate."}$$
- **Final Contract:** Rejection remains calm, private, and distinct from safety blocking. Mockup regenerated: [`buddy-mobile-request-rejected-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-rejected-r1.png).

---

## 3. Final Capability Matrix

| Capability Area | Current Status | Locked Contract Status |
| :--- | :--- | :--- |
| **Match Model** | Model in `schema.prisma` | **PARTIAL (DB Only)** |
| **Send / Accept / Reject** | Missing controllers/blocs | **DESIGN TARGET** |
| **Cancel Sent Request** | No `CANCELLED` enum | **BLOCKED (Schema)** |
| **Reverse Request Handling**| `(B, A)` allowed in PostgreSQL | **BLOCKED (Logic)** |
| **Phone Unlock** | Phone in `Profile` table | **PARTIAL (DB) / DESIGN TARGET (Logic)** |
| **Trip Invite from Buddy** | `POST :id/members` requires email | **PARTIAL / API ADAPTER REQUIRED** |
| **Direct Chat** | DB tables exist | **PARTIAL (DB) / FUTURE** |
| **Push Notifications** | No FCM/APNs | **DESIGN TARGET** |
| **User Block / Report** | Missing models | **UNSAFE / BLOCKED** |

---

## 4. Master Mockups Regenerated

| Mockup Artifact | Viewport | Target Resolution | Key R1 Refinement |
| :--- | :---: | :---: | :--- |
| [`buddy-mobile-request-pending-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-pending-r1.png) | Mobile | $390 \times 844$ | Truthful status check banner; no push notification promise. |
| [`buddy-mobile-request-received-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-received-r1.png) | Mobile | $390 \times 844$ | Standardized canonical `"Tài khoản đã xác minh"` badge. |
| [`buddy-mobile-match-accepted-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-match-accepted-r1.png) | Mobile | $390 \times 844$ | Zalo removed; `[Sao chép số]`; demo disclaimer; chat CTA removed. |
| [`buddy-mobile-request-rejected-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-mobile-request-rejected-r1.png) | Mobile | $390 \times 844$ | Neutral privacy copy; no negative notification claims. |
| [`buddy-desktop-requests-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.9/buddy-desktop-requests-r1.png) | Desktop | $1440 \times 900$ | Scoped GPS rule to Buddy connection; canonical verified badge. |

---

## 5. Source Code Integrity Verification

Command executed:
```bash
git diff apps/
```
Output:
```
(empty - 0 lines modified)
```
No application code, backend endpoints, Flutter widgets, or database schemas were modified.
