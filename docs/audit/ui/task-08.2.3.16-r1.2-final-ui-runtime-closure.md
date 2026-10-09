# GoMate Profile & Settings — Final UI/Runtime Evidence Closure (TASK 08.2.3.16-R1.2)

**Status:** APPROVED FINAL RUNTIME CLOSURE & PERMANENT DESIGN LOCK  
**Task:** TASK 08.2.3.16-R1.2 — GOMATE PROFILE & SETTINGS: FINAL UI/RUNTIME EVIDENCE CLOSURE  
**Date:** October 7, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Mode:** MICRO CORRECTION ONLY (No redesign, no production changes, no schema changes)  
**Source of Truth:**
- Database Schema: [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) (`model User`, `model Profile`, `model TravelPreference`, `model SafetyContact`, `model Notification`)
- Backend Source Code: [`apps/backend/src/modules/users/`](file:///d:/Do_an/wanderai/apps/backend/src/modules/users/), [`apps/backend/src/modules/auth/`](file:///d:/Do_an/wanderai/apps/backend/src/modules/auth/)
- Mobile Client Code: [`apps/mobile/pubspec.yaml`](file:///d:/Do_an/wanderai/apps/mobile/pubspec.yaml), [`apps/mobile/lib/core/router/app_router.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/core/router/app_router.dart)
- Upstream Design Documents:
  - [`docs/design/gomate-profile-settings-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-profile-settings-contract-v1.md)
  - [`docs/audit/ui/task-08.2.3.16-profile-settings-audit.md`](file:///d:/Do_an/wanderai/docs/audit/ui/task-08.2.3.16-profile-settings-audit.md)
  - [`docs/audit/ui/task-08.2.3.16-r1-runtime-truthfulness-correction.md`](file:///d:/Do_an/wanderai/docs/audit/ui/task-08.2.3.16-r1-runtime-truthfulness-correction.md)

---

## 1. Executive Summary & Objective

TASK 08.2.3.16-R1.2 resolves the final 3 subtle runtime-truthfulness and visual consistency gaps identified in TASK 08.2.3.16 before final DESIGN LOCK and downstream progression:

1. **Unsupported Online/Presence Claim:** Removed the unbacked indicator `"Trạng thái: Đang hoạt động"` from desktop overview. The codebase has zero online status, presence gateway, or heartbeat tracking infrastructure.
2. **End-to-End Avatar Capability Delineation:** Disaggregated avatar support into 6 distinct technical dimensions. Because the repository supports only avatar string/URL persistence and lacks device photo pickers, binary upload endpoints, and persistent media storage, the camera overlay button and clickable `"Thay đổi ảnh đại diện"` text were removed from the CURRENT V1 mockup to eliminate false affordances.
3. **Single Canonical Primary Save Action:** Standardized mobile edit profile on exactly 1 Save CTA (`[Lưu thay đổi hồ sơ]` at the bottom). Removed the duplicate `[Lưu]` action from the AppBar.

---

## 2. Inconsistency Analysis & Evidence-Based Closures

### 2.1. Closure A — Removal of Unsupported Online/Presence Claim

#### Audit Evidence:
A repository-wide search was executed across `apps/` for all presence and activity tracking terms:
```bash
git grep -i -E "onlineStatus|presence|lastSeen|lastActive|heartbeat" apps/
# Result: 0 matches
```
- In `apps/backend/prisma/schema.prisma`, `model User` contains only: `id`, `email`, `passwordHash`, `role`, `isVerified`, `createdAt`, `updatedAt`, `deletedAt`. There is **zero presence column**.
- In `apps/backend/src/`, there is **zero WebSocket presence gateway**, zero Redis presence heartbeat store, and zero session activity tracker.
- This directly aligns with the previously locked Group Chat contract ([`gomate-group-chat-contract-v1.md#L52`](file:///d:/Do_an/wanderai/docs/design/gomate-group-chat-contract-v1.md#L52)) which classified Online Presence as `MISSING / FUTURE`.

#### Correction Applied:
- **Mockup:** In [`profile-desktop-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-desktop-overview-v1-r1.png), Col 2 "Thông tin cá nhân cơ bản" previously rendered:
  `Trạng thái: Đang hoạt động`
  This row has been **completely removed**.
- **Governance Rule:** In accordance with audit standards, this claim was **NOT** replaced with *"Ngoại tuyến"*, *"Không hoạt động"*, or *"Vừa truy cập"*, as those states also require runtime evidence that does not exist.
- Basic info grid now cleanly renders:
  - Họ và tên: **Lê Hoàng Nam**
  - Số điện thoại: **0912 345 678** [Riêng tư]
  - Vai trò: **Thành viên USER**

---

### 2.2. Closure B — End-to-End Avatar Capability Verification

#### Audit Evidence & 6-Dimension Breakdown:
A rigorous inspection was conducted across `apps/mobile/pubspec.yaml`, `apps/backend/package.json`, and backend controllers for:
`image_picker`, `file_picker`, `multipart`, `upload`, `avatar`, `cloudinary`, `firebase_storage`, `s3`.

| Dimension | Technical Reality in Codebase | Classification | Architectural Verdict |
| :--- | :--- | :---: | :--- |
| **1. Avatar Field Persistence** | `avatar String?` in `model Profile` ([`schema.prisma#L77`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L77)) | **CURRENT** | Supported in PostgreSQL database schema. |
| **2. Avatar URL Update** | `PUT /users/me` accepts `{ avatar?: string }` JSON body ([`users.controller.ts#L22`](file:///d:/Do_an/wanderai/apps/backend/src/modules/users/users.controller.ts#L22)) | **CURRENT** | Service performs Prisma `upsert` on `model Profile`. |
| **3. Device Image Selection** | Zero `image_picker` or `file_picker` in [`apps/mobile/pubspec.yaml`](file:///d:/Do_an/wanderai/apps/mobile/pubspec.yaml) | **MISSING** | Flutter client has no native camera or gallery picker package. |
| **4. Binary Image Upload** | Zero `multipart/form-data` endpoint, zero Multer interceptors in NestJS | **MISSING** | Backend cannot accept raw binary image streams. |
| **5. Persistent Media Storage** | Zero AWS S3, Cloudinary, or Firebase Storage SDKs in `apps/backend/` | **MISSING** | No cloud or file-system storage bucket exists for user uploads. |
| **6. Image Retrieval / Display** | `cached_network_image: ^3.3.0` in mobile, fallback to initial circle `N` | **PARTIAL** | Can render external HTTP(S) URLs, but defaults to initials circle. |

#### Architectural Rule:
> **Strict Invariant:** `"avatar writable via JSON URL" \ne "device camera/photo upload pipeline exists"`

#### Correction Applied:
- In [`profile-mobile-edit-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-edit-v1-r1.png), the avatar area previously rendered a floating camera icon badge and blue clickable text `"Thay đổi ảnh đại diện"`. This implied an active native image picking and upload workflow.
- **Mockup Fix:** The camera icon badge overlay and clickable upload link were **removed**. The avatar is displayed as an honest account initial circle `N` with neutral label: *"Ảnh đại diện (Khởi tạo từ tên tài khoản)"*.
- Native device photo selection and binary upload pipeline are formally specified as **DESIGN TARGET** in the contract.

---

### 2.3. Closure C — Single Primary Save Action Standardization

#### Contradiction Found:
In `profile-mobile-edit-v1-r1.png`, the UI contained two separate save actions:
1. `[Lưu]` text button in the top AppBar right corner.
2. `[Lưu thay đổi hồ sơ]` primary teal button at the bottom of the content container.

Having dual primary triggers created visual clutter and ambiguous action hierarchy.

#### Canonical Selection & Correction:
- **AppBar Standard:** `<` Back chevron + `"Chỉnh sửa hồ sơ"`. The `[Lưu]` button in the AppBar was **removed**.
- **Primary CTA Standard:** Single primary button `[Lưu thay đổi hồ sơ]` at the bottom of the screen with $100\%$ width.
- **Write Boundary Preserved:**
  - Persisted via `PUT /users/me`: `displayName` (required 2–50 chars), `bio` (optional, max 200 chars).
  - Read-Only: `phone` (with `Riêng tư` badge).
  - Non-readable metadata: DOB, nationality, languages omitted with honest disclosure note.

---

## 3. Regenerated Visual Evidence Artifacts

Only the 2 affected visual mockups were regenerated using headless Microsoft Edge (`--headless=new`, `--force-device-scale-factor=1`) at exact target resolutions:

| Artifact File | Viewport | Target Resolution | Changes Applied in R1.2 | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`profile-desktop-overview-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-desktop-overview-v1-r1.png) | Desktop | $1440 \times 900$ | Completely removed unsupported `"Trạng thái: Đang hoạt động"` presence claim; removed implementation terms (USER, TravelPreference, Comfort, Buddy, Tier 1); eliminated horizontal scrollbar via responsive 3-column grid ($300\text{px} + 1\text{fr} + 336\text{px}$). | **CURRENT MASTER** |
| [`profile-mobile-edit-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.16/profile-mobile-edit-v1-r1.png) | Mobile | $390 \times 844$ | 1. Removed duplicate AppBar `[Lưu]` button.<br>2. Removed camera badge overlay & fake clickable `"Thay đổi ảnh đại diện"` link.<br>3. Retained single primary bottom CTA `[Lưu thay đổi hồ sơ]`.<br>4. Resolved horizontal overflow & text clipping; canonical 16px side padding; 5-tab bottom navigation with equal width. | **CURRENT MASTER** |

All other 10 master artifacts (`profile-mobile-overview-v1-r1.png`, `profile-mobile-travel-preferences-v1-r1.png`, `settings-mobile-home-v1.png`, `settings-desktop-home-v1-r1.png`, `settings-mobile-privacy-v1-r1.png`, `settings-mobile-notifications-v1-r1.png`, `settings-mobile-location-v1.png`, `settings-mobile-account-security-v1-r1.png`, `settings-mobile-logout-confirm-v1.png`, `profile-mobile-loading-error-v1.png`) were **unaffected** by R1.2 and remain authoritative masters.

---

## 4. Verification & Acceptance Gate

| Verification Item | R1.2 Standard | Observed Status | Verdict |
| :--- | :--- | :--- | :---: |
| **1. Unsupported Presence Purged** | No user presence claims in UI | Removed from `profile-desktop-overview-v1-r1.png` | **PASS** |
| **2. Zero Fake Offline/LastSeen** | No substitute presence terms | Grid only shows Name, Phone, Role | **PASS** |
| **3. Avatar 6-Dimension Audit** | Disaggregated technical capabilities | Full table documented; no false equivalence | **PASS** |
| **4. Camera Overlay Affordance Purged** | No clickable camera icon on avatar | Removed from `profile-mobile-edit-v1-r1.png` | **PASS** |
| **5. Single Primary Save CTA** | Exactly 1 Save trigger on edit screen | AppBar [Lưu] purged; bottom CTA retained | **PASS** |
| **6. Write Boundary Maintained** | Only displayName, bio writable | Phone is read-only; DOB/nationality omitted | **PASS** |
| **7. Affected Artifacts Regenerated** | Exactly 2 affected PNGs updated | Verified dimensions $1440 \times 900$ and $390 \times 844$ | **PASS** |
| **8. Unaffected Masters Intact** | Remaining 10 PNGs untouched | Preserved on disk without drift | **PASS** |
| **9. Zero Production Changes** | `apps/` 100% clean | `git diff apps/` returns 0 lines | **PASS** |
| **10. Schema Untouched** | `schema.prisma` 100% clean | `git diff apps/backend/prisma/` returns 0 lines | **PASS** |
| **11. Weekly Report Unstaged** | `weekly-report-W01.docx` untouched | Preserved unstaged and uncommitted | **PASS** |
| **12. Git Push / Merge Prohibited** | Local commit only on feature branch | 0 pushes to origin, 0 merges into develop | **PASS** |

---

## 5. Final Verdict

All runtime-truthfulness contradictions, presence claims, avatar affordances, and duplicate save actions across **TASK 08.2.3.16** are permanently resolved. 

$$\mathbf{TASK\ 08.2.3.16\ =\ DESIGN\ LOCKED}$$

Execution halts here. TASK 08.2.3.17 (GoMate Authentication) will NOT be initiated until explicitly directed.
