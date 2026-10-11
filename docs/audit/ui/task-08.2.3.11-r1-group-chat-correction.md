# GoMate Group Chat — Runtime Honesty & Cursor Contract Micro-Fix (TASK 08.2.3.11-R1)

**Status:** APPROVED MICRO-CORRECTION & DESIGN LOCK  
**Task:** TASK 08.2.3.11-R1 — GOMATE GROUP CHAT RUNTIME HONESTY & CURSOR CONTRACT MICRO-FIX  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:**
- Database Schema: `apps/backend/prisma/schema.prisma` (`model Message`, `model Group`, `model GroupMember`, `model Trip`, `model TripMember`, `model User`)
- Core Contracts: `docs/design/gomate-group-chat-contract-v1.md`, `docs/design/gomate-group-foundation-contract-v1.md`
- Master Visual Artifacts:
  - Mobile Master R1 (Chat Ready): [`group-chat-mobile-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-r1.png) ($390 \times 844$)
  - Mobile Send Failure State R1: [`group-chat-mobile-send-failed-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-send-failed-r1.png) ($390 \times 844$)
  - Mobile Reconnecting State R1: [`group-chat-mobile-reconnecting-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-reconnecting-r1.png) ($390 \times 844$)
  - Desktop Master Workstation R1: [`group-chat-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-desktop-r1.png) ($1440 \times 900$)
  - Baseline V1 Visuals (Pre-Correction): [`group-chat-mobile-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-v1.png), [`group-chat-mobile-send-failed-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-send-failed-v1.png), [`group-chat-mobile-reconnecting-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-reconnecting-r1.png), [`group-chat-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-desktop-v1.png)

---

## 1. Executive Summary & Objective

TASK 08.2.3.11-R1 executes targeted micro-corrections for the **GoMate Group Chat Message, Delivery & Realtime UX Contract V1** prior to Design Lock.

No Flutter production code, NestJS backend, FastAPI AI service, Prisma schema, or API contracts are altered. This task specifically resolves 6 runtime honesty, semantic, and pagination cursor ambiguities identified during audit review, regenerates the 4 master mockups (`-r1.png`), and locks the architectural contract for downstream implementation.

---

## 2. Comprehensive Correction Audit Matrix (Before → Risk → Evidence → Correction → Locked Contract)

### 2.1. Correction #1 — Reconnect Contradiction & Send Disablement

- **Before:** V1 reconnect banner copy stated: *"Đang kết nối lại... Tin nhắn sẽ được gửi khi có mạng"*.
- **Risk:** Contradicted the architectural baseline by falsely promising an automatic offline message queue and deferred background synchronization that does not exist in V1.
- **Evidence:**
  - `apps/mobile/lib/` has zero offline sync queues or local message outbox storage.
  - `apps/backend/` has no queue workers for offline client dispatch.
  - Contract Section 12 explicitly notes that offline sends transition to `FAILED`.
- **Correction:**
  - Removed every claim of automatic deferred sending.
  - Updated banner copy to:
    $$\textbf{"Đang kết nối lại... Bạn vẫn có thể xem các tin nhắn đã tải."}$$
  - Locked Send behavior during `RECONNECTING` and `OFFLINE`:
    - Loaded history remains visible and readable.
    - Draft text in composer input field is preserved.
    - **Send button is DISABLED** (`btn-send-disabled`).
    - Zero automatic dispatch occurs.
- **Locked Contract:** Reconnection preserves local history and draft text, disables sending, and makes zero promises of background automatic dispatch.

---

### 2.2. Correction #2 — Send Failure Remains Separate & Explicit

- **Before / Context:** Dispatches failing due to active network timeouts or server 5xx errors.
- **Risk:** Risk of conflating active network dispatch failure with offline detection, or assuming the app will automatically poll-retry failed messages.
- **Evidence:** Network disconnect during HTTP request execution.
- **Correction:**
  - Confirmed separate lifecycle: `SENDING -> FAILED`.
  - Outgoing bubble displays warning indicator and explicit copy:
    $$\textbf{"Không gửi được · Thử lại"}$$
  - The failed message content is never deleted or discarded.
  - The user must **manually tap "Thử lại"** to re-attempt dispatch.
- **Locked Contract:** Manual retry only; zero silent automatic background retries.

---

### 2.3. Correction #3 — Removal of Technical Developer Text from Product UI

- **Before:** V1 mockups displayed developer tracking tags directly inside user-facing frames:
  - `"Xác thực thành viên JWT"` (Desktop stream header)
  - `"STATE: CHAT_READY · ARCHITECTURE LOCK · TASK 08.2.3.11"` (Desktop right column footer)
  - `"DEMO EVIDENCE · TEXT-ONLY V1 · NO ATTACHMENTS · NO READ RECEIPTS"` (Mobile chat stream tag)
  - `"RECONNECTING STATE · OFFLINE SAFE"` (Mobile reconnecting tag)
  - `"SEND_FAILED STATE · PRESERVED MESSAGE"` (Mobile send failure tag)
- **Risk:** Leaking internal architectural tickets and developer annotations into production UI frames degrades visual fidelity and realism.
- **Evidence:** Technical classifications belong strictly to contract and audit documents, never end-user production UI.
- **Correction:**
  - Purged all developer evidence tags and ticket references from within the application frames across all 4 mockups.
- **Locked Contract:** Production UI displays clean, authentic user interfaces. Technical annotations remain exclusively in audit documents.

---

### 2.4. Correction #4 — Removal of Ambiguous Desktop Badges

- **Before:** Desktop mockup displayed `"Chính thức"` on the Group Info card and `"Văn bản thuần · Text-only"` in the primary chat header.
- **Risk:**
  - `"Chính thức"` provided no user value and could falsely imply current production runtime availability.
  - `"Văn bản thuần · Text-only"` exposed an internal development scope boundary as user copy.
- **Evidence:** The absence of attachment controls (paperclips, cameras, microphones) in the composer communicates the V1 text-only capability naturally and sufficiently.
- **Correction:**
  - Removed `"Chính thức"` badge from the Group Info card.
  - Removed `"Văn bản thuần · Text-only"` badge from the primary desktop chat header.
- **Locked Contract:** Clean desktop header: `"Trò chuyện nhóm"` with member count; no redundant developer scope badges.

---

### 2.5. Correction #5 — Pagination Cursor Contract Standardization

- **Before:** Previous contract text referenced `createdAt + id` ordering but showed a raw `cursor=<oldestMessageId>` parameter in example endpoints.
- **Risk:** Ambiguity between whether the cursor is a plain UUID or a composite cursor, leading to pagination instability if multiple messages share the exact same timestamp.
- **Evidence:**
  - Primary ordering: `createdAt ASC`.
  - Tie-breaker: `id ASC`.
  - To paginate backward cleanly (`before`), the backend requires both timestamp and ID checkpoints.
- **Correction:**
  - Standardized on a **single unified OPAQUE CURSOR contract**:
    ```http
    GET /groups/:groupId/messages?before=<opaqueCursor>&limit=30
    ```
  - Response:
    ```json
    {
      "data": [...],
      "nextCursor": "<opaqueCursor>",
      "hasMore": true
    }
    ```
  - The client **MUST treat the cursor as an opaque string** and must not unpack or synthesize it.
- **Locked Contract:** Opaque cursor contract locked; ties broken deterministically; client treats cursor as opaque token.

---

### 2.6. Correction #6 — Exact Semantics of "Đã gửi"

- **Before:** Outgoing own messages displayed `"09:25 · Đã gửi"` without defining whether it implied delivery to peers or read receipt.
- **Risk:** Misinterpretation by developers or users that `"Đã gửi"` means the message was delivered to other members' devices or read by them.
- **Evidence:** `schema.prisma` has no `readAt`, `deliveredAt`, or receipt tables.
- **Correction:**
  - Formally locked the exact definition:
    $$\textbf{"Đã gửi"} \iff \textbf{Server ACK received} \ \wedge \ \textbf{Message row committed to PostgreSQL}$$
  - It **DOES NOT mean DELIVERED** to other peers' devices.
  - It **DOES NOT mean READ or SEEN** by any recipient.
  - Double checkmarks, "Delivered", and "Seen" labels are strictly prohibited in V1 mockups and UI.
- **Locked Contract:** "Đã gửi" represents server-persisted confirmation only.

---

### 2.7. Correction #7 — Plain-Text Security & Untrusted Input Rendering

- **Before:** Text-only V1 was specified without explicitly addressing input sanitization and security rendering rules.
- **Risk:** Cross-Site Scripting (XSS) or arbitrary markup interpretation vulnerabilities in Flutter Web or mobile rendering.
- **Evidence:** `model Message.content` stores arbitrary raw user input strings.
- **Correction:**
  - Defined explicit security rendering rules:
    1. `Message.content` must be treated as **untrusted user text**.
    2. Client must render content strictly as plain text (or safe styled text); **it must NOT interpret raw HTML, scripts, or executable markup**.
    3. Full Unicode and Vietnamese character diacritics must be preserved without corruption.
    4. Client and API layers must validate non-empty text (trimming whitespace).
- **Locked Contract:** Untrusted plain text security rule locked.

---

## 3. Master Mockup Verification (R1 Refined Artifacts)

| Mockup File | Viewport | Dimensions | Verified R1 Honesty Corrections | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`group-chat-mobile-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-r1.png) | Mobile | $390 \times 844$ | 1. Clean production UI: Internal tags (`DEMO EVIDENCE`) removed.<br>2. Text-only message stream: Other member bubbles (Nam, Mai) with display names and roles; Own bubble right-aligned (`#0F766E`) with `"09:25 · Đã gửi"`.<br>3. Text composer with placeholder `"Nhập tin nhắn..."` and active Send button.<br>4. Zero attachment buttons, zero read receipts (no ticks/seen), zero online presence, zero typing indicators. | **PASS** |
| [`group-chat-mobile-send-failed-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-send-failed-r1.png) | Mobile | $390 \times 844$ | 1. Previous messages completely preserved.<br>2. Latest outgoing bubble has explicit warning state: `⚠️ Không gửi được · Thử lại`.<br>3. Input field remains functional; typed content is not deleted.<br>4. Clean production UI: Zero developer evidence tags inside frame. | **PASS** |
| [`group-chat-mobile-reconnecting-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-reconnecting-r1.png) | Mobile | $390 \times 844$ | 1. Honest reconnecting banner below app bar: `⟳ Đang kết nối lại... Bạn vẫn có thể xem các tin nhắn đã tải.` (NO false auto-send promises).<br>2. Existing cached message history remains fully readable.<br>3. Draft text is preserved in composer.<br>4. **Send button is DISABLED** (`btn-send-disabled`), accurately conveying lack of offline queue. | **PASS** |
| [`group-chat-desktop-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-desktop-r1.png) | Desktop | $1440 \times 900$ | 1. Top navigation: GoMate navbar with 5 canonical tabs (Chuyến đi active).<br>2. Breadcrumb: `Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhóm đồng hành › Trò chuyện nhóm`.<br>3. Col 1 ($340\text{px}$): Group info (clean, `"Chính thức"` removed), linked trip metadata, 3 members with verified badges, privacy notice.<br>4. Col 2 ($740\text{px}$): Clean stream header (`"Trò chuyện nhóm"`, no `"Văn bản thuần"` badge, no JWT wording), chronological text message feed (others left, own right), full-width text composer with Send button. Zero attachments, zero read receipts.<br>5. Col 3 ($340\text{px}$): Downstream modules (`Lịch trình chung · Sắp có`, `Chi tiêu chuyến đi · Sắp có`), Leave group danger zone.<br>6. Zero internal task or architecture tags. Zero scrollbars. | **PASS** |

---

## 4. Final Capability Matrix

| Khả năng Chức năng | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Đặc tả Design | Trạng thái Khóa R1 | Minh chứng & Ghi chú Vận hành |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Model Message** | Thiếu | Thiếu | `model Message` | Contract Section 3 | **PARTIAL (DB Only)** | Model có sẵn; chưa có controller NestJS. |
| **Lịch sử tin nhắn** | Thiếu | Thiếu | `model Message` | Contract Section 6, 7 | **DESIGN TARGET** | Yêu cầu endpoint `GET /groups/:id/messages`. |
| **Gửi text thuần** | Thiếu | Thiếu | `Message.content` | Contract Section 5, 8 | **DESIGN TARGET** | Plain UTF-8 text; không upload file. |
| **Nhận Realtime** | Thiếu | Thiếu | Thiếu Gateway | Contract Section 11 | **MISSING / FUTURE** | Chưa có WebSocket gateway hoặc Socket.IO. |
| **Xác thực Group** | Thiếu | Thiếu | `GroupMember` | Contract Section 4 | **DESIGN TARGET** | Bắt buộc có bản ghi `GroupMember` hợp lệ. |
| **Phân trang con trỏ** | Thiếu | Thiếu | Thiếu Endpoint | Contract Section 7 | **DESIGN TARGET** | Phân trang cursor dựa trên `createdAt + id`. |
| **Gửi lạc quan (Optimistic)**| Thiếu | Thiếu | Thiếu Client Bloc | Contract Section 9 | **DESIGN TARGET** | State `SENDING` chuyển sang `SENT` khi nhận ACK. |
| **Gửi lại tin lỗi (Retry)**| Thiếu | Thiếu | Thiếu Client Bloc | Contract Section 10 | **DESIGN TARGET** | Giữ nội dung tin nhắn, bấm `[Thử lại]`. |
| **Tính bất biến (Idempotency)**| Thiếu | Thiếu | **CHƯA CÓ TRONG DB** | Contract Section 10 | **IMPLEMENTATION GAP** | Thiếu `clientMessageId`; cần xử lý ở tầng backend. |
| **Tệp đính kèm Media** | Thiếu | Thiếu | **CHƯA CÓ TRONG DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | Thiếu `attachmentUrl`; cấm render nút upload. |
| **Trả lời tin nhắn (Reply)**| Thiếu | Thiếu | **CHƯA CÓ TRONG DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | Thiếu `replyToId`. |
| **Cảm xúc Emoji** | Thiếu | Thiếu | **CHƯA CÓ TRONG DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | Thiếu bảng `Reaction`. |
| **Sửa tin nhắn (Edit)** | Thiếu | Thiếu | **CHƯA CÓ TRONG DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | Thiếu `editedAt`. |
| **Xóa tin nhắn (Delete)** | Thiếu | Thiếu | **CHƯA CÓ TRONG DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | Thiếu `deletedAt`. |
| **Biên nhận đọc (Seen)** | Thiếu | Thiếu | **CHƯA CÓ TRONG DB** | Contract Section 14 | **FUTURE / SCHEMA GAP** | Thiếu `readAt`; cấm render dấu tích xanh. |
| **Chỉ báo đang gõ** | Thiếu | Thiếu | Thiếu Gateway | Contract Section 14 | **FUTURE** | Chưa có socket channel phát sóng typing. |
| **Trạng thái Online** | Thiếu | Thiếu | Thiếu Gateway | Contract Section 14 | **FUTURE** | Chưa có presence service; cấm render chấm xanh. |
| **Thông báo đẩy (Push)**| Thiếu | Thiếu | Thiếu Service | Contract Section 17 | **DESIGN TARGET** | Chưa có hạ tầng FCM/APNs. |
| **Chặn người dùng** | Thiếu | Thiếu | **CHƯA CÓ TRONG DB** | Contract Section 16 | **UNSAFE / BLOCKED** | Yêu cầu Prisma migration bảng `UserBlock`. |
| **Báo cáo vi phạm** | Thiếu | Thiếu | **CHƯA CÓ TRONG DB** | Contract Section 16 | **UNSAFE / BLOCKED** | Yêu cầu Prisma migration bảng `UserReport`. |

---

## 5. Design Acceptance Gate (TASK 08.2.3.11-R1)

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
