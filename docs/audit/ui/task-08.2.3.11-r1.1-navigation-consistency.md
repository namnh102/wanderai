# GoMate Group Chat — Global Navigation Consistency Micro-Fix Addendum (TASK 08.2.3.11-R1.1)

**Status:** APPROVED ARCHITECTURAL FIX & DESIGN LOCK  
**Task:** TASK 08.2.3.11-R1.1 — GOMATE GROUP CHAT: GLOBAL NAVIGATION CONSISTENCY MICRO-FIX  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewport:** Desktop ($1440 \times 900$)  
**Target Artifact:** [`group-chat-desktop-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-desktop-r1-final.png)  

---

## 1. Executive Summary & Problem Statement

During the review of TASK 08.2.3.11-R1, a micro-regression in Desktop Global Information Architecture (IA) was identified:
- In `group-chat-desktop-r1.png`, the 5th top navigation item was rendered as **`"Bạn đồng hành"`** (Travel Companion).
- This contradicts the canonical 5-tab root application architecture established and locked across the GoMate platform.

### Architectural Hazard
Elevating `"Bạn đồng hành"` to a root top-level navigation destination violates the GoMate domain model. In GoMate:
- **Buddy Discovery, Match Requests, Companion Groups, and Group Chat are contextual sub-capabilities of a Trip (`Chuyến đi`)**, not autonomous root destinations.
- Creating an independent root tab for companions causes domain confusion, lifecycle ambiguity, and decouples travelers from their active trip context.

---

## 2. Canonical GoMate Global Root Navigation Architecture

The GoMate global root navigation across web, desktop, and tablet consists strictly of **5 canonical destinations**:

| Index | Root Destination | Navigation Label | Canonical Role | Status in Group Chat |
| :---: | :--- | :--- | :--- | :---: |
| 1 | **Khám phá** | `Khám phá` | Destination discovery, curated POIs, community travel feeds | Inactive |
| 2 | **Bản đồ** | `Bản đồ` | Interactive PostGIS map, spatial discovery, geonavigation | Inactive |
| 3 | **Wandy AI** | `Wandy AI` | AI Travel Assistant, RAG-grounded copilot | Inactive |
| 4 | **Chuyến đi** | `Chuyến đi` | Trip planning, itinerary, companion groups, expenses | **ACTIVE** |
| 5 | **An toàn** | `An toàn` | Emergency SOS, local emergency contacts, embassy hotlines | Inactive |

> [!IMPORTANT]
> **Root IA Invariant:**
> $$\textbf{Buddy / Group} = \textbf{Contextual Trip Capability} \quad (\textbf{NOT Root Application Navigation})$$
> `"Bạn đồng hành"` MUST NEVER appear as a root application navigation tab.

---

## 3. Contextual Hierarchy & Breadcrumb Guarantee

Companion Groups and Group Chat are nested strictly within the active Trip hierarchy. The desktop interface guarantees clear spatial orientation via the breadcrumb bar:

```
Chuyến đi (Root)
    └── Khám phá Đà Nẵng 4N3Đ (Trip Workspace)
            └── Nhóm đồng hành (Companion Group Workspace)
                    └── Trò chuyện nhóm (Group Chat Stream)
```

**Verified Breadcrumb Copy:**  
`Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhóm đồng hành › Trò chuyện nhóm`

This contextual breadcrumb preserves full situational awareness while keeping the root navigation strictly canonical (`Khám phá` | `Bản đồ` | `Wandy AI` | `Chuyến đi` | `An toàn`).

---

## 4. Master Mockup Verification

The desktop workstation mockup was regenerated and verified at target resolution:

| Mockup Artifact | Viewport | Target Resolution | Architectural Verifications | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`group-chat-desktop-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-desktop-r1-final.png) | Desktop | $1440 \times 900$ | 1. **Root Navigation:** Top navbar renders exactly 5 canonical items (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` [Active], `An toàn`). 5th tab is restored to `An toàn` with shield icon.<br>2. **Active State:** `Chuyến đi` retains the active teal pill.<br>3. **Breadcrumb:** Accurately renders `Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhóm đồng hành › Trò chuyện nhóm`.<br>4. **Left Column ($340\text{px}$):** Clean group info, linked trip metadata, 3 members with verified checkmarks, privacy boundaries card.<br>5. **Center Column ($740\text{px}$):** Clean header `"Trò chuyện nhóm" · 3 thành viên`, full text-only chronological chat stream, full-width composer with placeholder and Send button. No JWT or developer annotations.<br>6. **Right Column ($340\text{px}$):** Downstream modules (`Lịch trình chung · Sắp có`, `Chi tiêu chuyến đi · Sắp có`), Leave group button.<br>7. **Resolution:** Exactly $1440 \times 900$ pixels. | **PASS** |
| [`group-chat-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-desktop-r1.png) | Desktop | $1440 \times 900$ | *Pre-IA correction artifact (5th tab was labeled "Bạn đồng hành"). Retained for audit history.* | **SUPERSEDED** |

---

## 5. Acceptance Gate Checklist

- [x] **Desktop root navigation = canonical GoMate IA:** Exactly 5 tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi`, `An toàn`).
- [x] **"Bạn đồng hành" removed as root tab:** Completely purged from desktop navbar.
- [x] **"An toàn" restored as root tab:** 5th tab accurately shows `{ICONS['shield_nav']} An toàn`.
- [x] **"Chuyến đi" active:** Active state preserved on 4th tab.
- [x] **Breadcrumb keeps Nhóm đồng hành context:** `Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhóm đồng hành › Trò chuyện nhóm`.
- [x] **No Group Chat business changes:** Text-only V1, group member authorization, delivery state machine unchanged.
- [x] **No mobile redesign:** Mobile mockups (`group-chat-mobile-r1.png`, `group-chat-mobile-send-failed-r1.png`, `group-chat-mobile-reconnecting-r1.png`) intact.
- [x] **No source changes:** Zero edits to `apps/mobile/`, `apps/backend/`, `apps/ai-service/`.
- [x] **No DB changes:** `schema.prisma` unmodified.
- [x] **No API changes:** API contracts unchanged.
- [x] **No merge:** Work remains isolated on `feature/gomate-visual-mockups`.
- [x] **No push:** Work remains local only.
