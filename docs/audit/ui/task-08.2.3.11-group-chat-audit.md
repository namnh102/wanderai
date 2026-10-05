# GoMate Group Chat — Capability & Realtime UX Audit (TASK 08.2.3.11)

**Status:** APPROVED ARCHITECTURAL AUDIT & UX SPECIFICATION  
**Task:** TASK 08.2.3.11 — GOMATE GROUP CHAT: MESSAGE, DELIVERY & REALTIME UX CONTRACT V1  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:**
- Database Schema: `apps/backend/prisma/schema.prisma` (`model Message`, `model Group`, `model GroupMember`, `model Trip`, `model TripMember`, `model User`)
- Foundation Contract: `docs/design/gomate-group-foundation-contract-v1.md`
- Core Contract: `docs/design/gomate-group-chat-contract-v1.md`
- Master Visual Artifacts:
  - Mobile Master (Chat Ready): [`group-chat-mobile-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-v1.png) ($390 \times 844$)
  - Mobile Send Failure State: [`group-chat-mobile-send-failed-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-send-failed-v1.png) ($390 \times 844$)
  - Mobile Reconnecting State: [`group-chat-mobile-reconnecting-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-reconnecting-v1.png) ($390 \times 844$)
  - Desktop Master Workstation: [`group-chat-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-desktop-v1.png) ($1440 \times 900$)

---

## 1. Executive Summary & Audit Verdict

TASK 08.2.3.11 executes an exhaustive audit of the GoMate messaging capabilities and locks the UX, delivery, and realtime contracts for Group Chat.

### Primary Audit Verdict:
1. **Database Reality:**
   - `model Message` exists in `apps/backend/prisma/schema.prisma` with 5 columns: `id`, `groupId`, `userId`, `content`, `createdAt`.
   - It possesses cascade deletion on `Group` deletion (`onDelete: Cascade`), but **defaults to RESTRICT on `User` deletion**.
   - The table lacks an index on `[groupId, createdAt]`, which represents a database performance optimization gap for history queries.
2. **Backend & Mobile Reality:**
   - **0 NestJS chat controllers or services exist** in `apps/backend/src/modules/`.
   - **0 WebSocket gateways, Socket.IO clients, or ws dependencies exist** in `package.json`. Realtime transport is `MISSING / FUTURE`.
   - **0 Flutter group chat screens or socket blocs exist** in `apps/mobile/lib/features/`.
3. **Text-Only V1 Contract Locked:**
   - Because `model Message` only stores `content String`, V1 is strictly a **plain text messenger**.
   - Media attachments, voice notes, stickers, reactions, replies, message editing, message deletion, and live GPS sharing are **unsupported schema gaps**.
4. **Delivery & Offline Integrity Locked:**
   - Client delivery states: `COMPOSING` $\rightarrow$ `SENDING` $\rightarrow$ (`SENT` | `FAILED` $\rightarrow$ `RETRY`).
   - Read receipts and typing indicators are omitted from master mockups to prevent feature overclaim.
   - Offline and reconnecting states preserve historical messages without claiming fake background synchronization.

---

## 2. Technical Evidence & Inspection Logs

### 2.1. Prisma Schema Audit (`apps/backend/prisma/schema.prisma`)
```prisma
model Message {
  id        String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  groupId   String   @map("group_id") @db.Uuid
  userId    String   @map("user_id") @db.Uuid
  content   String
  createdAt DateTime @default(now()) @map("created_at") @db.Timestamptz

  group Group @relation(fields: [groupId], references: [id], onDelete: Cascade)
  user  User  @relation(fields: [userId], references: [id])

  @@map("messages")
}
```

### 2.2. Backend Modules & Dependency Audit
- Scanned: `apps/backend/src/modules/`
  - Modules found: `ai-proxy`, `auth`, `destinations`, `health`, `places`, `reviews`, `trips`, `users`, `videos`.
  - Zero `groups`, `messages`, `chat`, or `websocket` modules exist.
- `apps/backend/package.json` inspection:
  - Scanned for `@nestjs/websockets`, `socket.io`, `ws`.
  - Result: **0 WebSocket dependencies installed**.

### 2.3. Flutter Client Audit
- Scanned: `apps/mobile/lib/features/`
  - Only `ai_chat` exists (used exclusively for Wandy AI single-user assistant).
  - Zero group chat screens, socket clients, or stream repositories exist.
- `apps/mobile/pubspec.yaml` inspection:
  - Scanned for `web_socket_channel`, `socket_io_client`.
  - Result: **0 WebSocket packages installed**.

---

## 3. Schema Gap & Missing Feature Audit

| Message Feature | Schema Field | Status | Architectural Gap & Risk | Mitigation in Design Contract |
| :--- | :--- | :---: | :--- | :--- |
| **Media Attachments** | `attachmentUrl`, `attachmentType` | **MISSING** | Attempting to upload images/videos fails at DB layer. | Text-only V1 locked. Attachment button omitted from UI. |
| **Reply / Threading** | `replyToId` | **MISSING** | No parent message relation exists. | Threaded replies classified as `FUTURE`. |
| **Emoji Reactions** | `reactions` / `Reaction` model | **MISSING** | No reaction table or JSON column exists. | Reactions classified as `FUTURE`. |
| **Message Editing** | `editedAt` | **MISSING** | Cannot track if a message was altered. | Edit message classified as `FUTURE`. |
| **Message Deletion** | `deletedAt` | **MISSING** | Soft-delete impossible without schema change. | Delete message requires moderation contract. |
| **Read Receipts** | `readAt`, `Receipt` model | **MISSING** | No delivery or seen timestamps per member. | Ticks and "Seen by" forbidden in mockups. |
| **Typing Indicator** | WebSocket presence | **MISSING** | No socket channel exists to broadcast typing. | "Nam đang nhập..." omitted from UI. |
| **Online Presence** | Gateway presence | **MISSING** | No heartbeat or active status tracking. | "Online" / green dots omitted from UI. |
| **Idempotency Key** | `clientMessageId` | **MISSING** | Naive retry causes duplicate message rows. | Idempotency documented as implementation gap. |
| **Composite Index** | `@@index([groupId, createdAt])`| **MISSING** | History queries become slow with large message volume. | Recommended for future database migration. |

---

## 4. Authorization & Boundary Audit

1. **Authorization Separation:**
   $$\text{MATCHED} \centernot\implies \text{CHAT ACCESS} \qquad \text{TRIP\_MEMBER} \centernot\implies \text{CHAT ACCESS}$$
   Only verified `GroupMember` rows grant read or write permissions.
2. **Read Guard:** `GET /groups/:groupId/messages` must return `403 Forbidden` if `(groupId, currentUser.id)` does not exist in `GroupMember`.
3. **Send Guard:** `POST /groups/:groupId/messages` must bind `userId` strictly from session JWT; client-supplied sender IDs are ignored.

---

## 5. Comprehensive Capability Matrix

| Capability Area | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Design Specification | Status | Evidence & Runtime Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Message Model** | Missing | Missing | `model Message` | Contract Section 3 | **PARTIAL (DB Only)** | Model exists; no NestJS chat module or controller. |
| **Message History** | Missing | Missing | `model Message` | Contract Section 6, 7 | **DESIGN TARGET** | Requires `GET /groups/:groupId/messages` cursor endpoint. |
| **Send Plain Text** | Missing | Missing | `Message.content` | Contract Section 5, 8 | **DESIGN TARGET** | Plain UTF-8 text only; no media upload. |
| **Realtime Receive** | Missing | Missing | Missing Gateway | Contract Section 11 | **MISSING / FUTURE** | Zero WebSocket gateway or Socket.IO packages in repo. |
| **Group Authorization**| Missing | Missing | `GroupMember` | Contract Section 4 | **DESIGN TARGET** | Active `GroupMember` row required for read/write. |
| **Pagination** | Missing | Missing | Missing Endpoint | Contract Section 7 | **DESIGN TARGET** | Cursor-based (`createdAt + id`) pagination target. |
| **Optimistic Send** | Missing | Missing | Missing Client Bloc | Contract Section 9 | **DESIGN TARGET** | Local `SENDING` state transitioning on server ACK. |
| **Retry Failed Send** | Missing | Missing | Missing Client Bloc | Contract Section 10 | **DESIGN TARGET** | Failed message retains text; offers `[Thử lại]` action. |
| **Idempotency** | Missing | Missing | **MISSING FROM DB** | Contract Section 10 | **IMPLEMENTATION GAP** | Schema lacks `clientMessageId`; naive retry causes duplicate rows. |
| **Media Attachments** | Missing | Missing | **MISSING FROM DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | No `attachmentUrl` or blob storage integration. |
| **Message Reply** | Missing | Missing | **MISSING FROM DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | No `replyToId` foreign key column. |
| **Reactions / Emoji** | Missing | Missing | **MISSING FROM DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | No `Reaction` model in database. |
| **Edit Message** | Missing | Missing | **MISSING FROM DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | No `editedAt` column. |
| **Delete Message** | Missing | Missing | **MISSING FROM DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | No `deletedAt` soft-delete column. |
| **Read Receipts** | Missing | Missing | **MISSING FROM DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | No `readAt` / `Receipt` model; ticks forbidden in UI. |
| **Typing Indicator** | Missing | Missing | Missing Transport | Contract Section 14 | **FUTURE** | Requires real-time WebSocket presence channel. |
| **Online Presence** | Missing | Missing | Missing Transport | Contract Section 14 | **FUTURE** | No presence service; green online dots forbidden in UI. |
| **Push Notifications** | Missing | Missing | Missing Service | Contract Section 17 | **DESIGN TARGET** | No FCM/APNs in repo; no instant delivery promises. |
| **User Block** | Missing | Missing | **MISSING FROM DB** | Contract Section 16 | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserBlock`. |
| **User Report** | Missing | Missing | **MISSING FROM DB** | Contract Section 16 | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserReport`. |

---

## 6. Master Mockup Verification (4 Master Artifacts)

## 6. Master Mockup Verification (R1 Refined Artifacts)

All 4 master mockups were updated and verified at `docs/audit/evidence/ui-08.2.3.11/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`group-chat-mobile-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-r1.png) | Mobile | $390 \times 844$ | 1. Status bar `9:41 5G 100%` + App bar `"Nhóm Đà Nẵng 4N3Đ"` with avatar `ĐN` and info icon.<br>2. Date separator `"Hôm nay, 5 tháng 10"`.<br>3. Clean production UI: Internal tags (`DEMO EVIDENCE`) completely removed from application frame.<br>4. Text-only message stream: Other member bubbles (Nam, Mai) with display names and roles; Own bubble right-aligned (`#0F766E`) with `"09:25 · Đã gửi"`.<br>5. Text composer with placeholder `"Nhập tin nhắn..."` and active Send button.<br>6. **CRITICAL CHECKS:** Zero attachment buttons, zero read receipts (no ticks/seen), zero online presence, zero typing indicators. | **PASS** |
| [`group-chat-mobile-send-failed-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-send-failed-r1.png) | Mobile | $390 \times 844$ | 1. Previous messages completely preserved.<br>2. Latest outgoing bubble has explicit warning state: `⚠️ Không gửi được · Thử lại`.<br>3. Input field remains functional; typed content is not deleted.<br>4. Clean production UI: Zero developer evidence tags inside frame. | **PASS** |
| [`group-chat-mobile-reconnecting-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-reconnecting-r1.png) | Mobile | $390 \times 844$ | 1. Honest reconnecting banner below app bar: `⟳ Đang kết nối lại... Bạn vẫn có thể xem các tin nhắn đã tải.` (NO false auto-send promises).<br>2. Existing cached message history remains fully readable.<br>3. Draft text is preserved in composer.<br>4. **Send button is DISABLED** (`btn-send-disabled`), accurately conveying lack of offline queue. | **PASS** |
| [`group-chat-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-desktop-r1.png) | Desktop | $1440 \times 900$ | 1. Top navigation: GoMate navbar with 5 canonical tabs (Chuyến đi active).<br>2. Breadcrumb: `Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhóm đồng hành › Trò chuyện nhóm`.<br>3. Col 1 ($340\text{px}$): Group info (clean, `"Chính thức"` removed), linked trip metadata, 3 members with verified badges, privacy notice.<br>4. Col 2 ($740\text{px}$): Clean stream header (`"Trò chuyện nhóm"`, no `"Văn bản thuần"` badge, no JWT wording), chronological text message feed (others left, own right), full-width text composer with Send button. Zero attachments, zero read receipts.<br>5. Col 3 ($340\text{px}$): Downstream modules (`Lịch trình chung · Sắp có`, `Chi tiêu chuyến đi · Sắp có`), Leave group danger zone.<br>6. Zero internal task or architecture tags. Zero scrollbars. | **PASS** |

*(Pre-correction V1 artifacts preserved for historical comparison: [`group-chat-mobile-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-v1.png), [`group-chat-mobile-send-failed-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-send-failed-v1.png), [`group-chat-mobile-reconnecting-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-reconnecting-v1.png), [`group-chat-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-desktop-v1.png).)*

---

## 7. Design Acceptance Gate (TASK 08.2.3.11-R1)

- [x] **No auto-send promise while reconnecting:** Copy locked to *"Đang kết nối lại... Bạn vẫn có thể xem các tin nhắn đã tải."*
- [x] **Reconnecting Send is disabled:** Send button rendered disabled in reconnecting state.
- [x] **Draft remains preserved:** Text typed into input remains intact during reconnection.
- [x] **Existing history remains readable:** Cached messages visible and legible.
- [x] **Send failure remains explicit retry:** Outgoing failure shows `"Không gửi được · Thử lại"`; no silent auto-retry.
- [x] **No technical labels inside product frame:** `DEMO EVIDENCE`, `STATE: CHAT_READY`, etc., removed.
- [x] **No JWT wording shown to end user:** Removed `"Xác thực thành viên JWT"` from desktop header.
- [x] **No TASK/STATE labels shown to end user:** Developer annotations purged from user-facing cards.
- [x] **"Chính thức" badge removed:** Omitted from Desktop Group info card.
- [x] **Text-only developer badge removed:** Omitted from Desktop primary stream header.
- [x] **Cursor uses opaque (createdAt, id) contract:** Standardized on `GET /groups/:groupId/messages?before=<opaqueCursor>&limit=30`.
- [x] **"Đã gửi" means server ACK only:** Persisted to Postgres; does not imply delivered/read/seen.
- [x] **No Delivered/Read/Seen implication:** No double checkmarks or read ticks.
- [x] **Plain text treated as untrusted text:** Safe rendering; no execution of raw HTML/scripts.
- [x] **Mobile ready R1 generated:** [`group-chat-mobile-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-r1.png) verified ($390 \times 844$).
- [x] **Mobile failed R1 generated:** [`group-chat-mobile-send-failed-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-send-failed-r1.png) verified ($390 \times 844$).
- [x] **Mobile reconnect R1 generated:** [`group-chat-mobile-reconnecting-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-reconnecting-r1.png) verified ($390 \times 844$).
- [x] **Desktop R1 generated:** [`group-chat-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-desktop-r1.png) verified ($1440 \times 900$).
- [x] **No source changes:** `git diff apps/` is empty.
- [x] **No DB changes:** `schema.prisma` unmodified.
- [x] **No API changes:** API contracts intact.
- [x] **No merge:** Branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
