# GoMate Group Chat — Message, Delivery & Realtime UX Contract V1

**Status:** APPROVED DESIGN & CONTRACT SPECIFICATION  
**Task:** TASK 08.2.3.11 — GOMATE GROUP CHAT: MESSAGE, DELIVERY & REALTIME UX CONTRACT V1  
**Module:** Travel Companion Group Chat (`/groups/:id/chat`)  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$), Tablet ($768 \times 1024$)  
**Source of Truth:**
- Database Schema: `apps/backend/prisma/schema.prisma` (`model Message`, `model Group`, `model GroupMember`, `model Trip`, `model TripMember`, `model User`)
- Foundation Contract: `docs/design/gomate-group-foundation-contract-v1.md`
- Foundation Audits: `docs/audit/ui/task-08.2.3.10-group-foundation-audit.md`, `docs/audit/ui/task-08.2.3.10-r1-group-foundation-correction.md`
- Master Visual Artifacts:
  - Mobile Master (Chat Ready): [`group-chat-mobile-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-v1.png) ($390 \times 844$)
  - Mobile Send Failure State: [`group-chat-mobile-send-failed-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-send-failed-v1.png) ($390 \times 844$)
  - Mobile Reconnecting State: [`group-chat-mobile-reconnecting-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-mobile-reconnecting-v1.png) ($390 \times 844$)
  - Desktop Master Workstation: [`group-chat-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.11/group-chat-desktop-v1.png) ($1440 \times 900$)

---

## 1. Product Role & Architectural Vision

The **Group Chat** module (`Trò chuyện nhóm đồng hành`) provides the real-time operational communication channel for travelers collaborating within a GoMate Companion Group.

Unlike public social media messengers (which prioritize viral stickers, read receipts, active status broadcasting, and continuous social presence), GoMate Group Chat is a **focused, privacy-respecting, trip-coordination workspace**:
1. **Trip Execution Focused:** The conversation exists to coordinate real-world travel schedules, meeting points, and logistics for the bound trip (`Trip`).
2. **Text-Only V1 Discipline:** Anchored strictly in current database schema capability (`model Message` contains only `content String`).
3. **Explicit Boundary Protection:** Phone numbers, ambient live GPS coordinates, and personal email addresses are **never automatically leaked or broadcasted** into the chat stream.

---

## 2. Current vs Target Capability Matrix

| Capability Dimension | Backend NestJS | Flutter Client | Database (`schema.prisma`) | Design Specification | Status | Evidence & Runtime Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Message Model** | Missing | Missing | `model Message` | Section 3 | **PARTIAL (DB Only)** | Model exists; no NestJS chat module or controller. |
| **Message History** | Missing | Missing | `model Message` | Section 6, 7 | **DESIGN TARGET** | Requires `GET /groups/:groupId/messages` cursor endpoint. |
| **Send Plain Text** | Missing | Missing | `Message.content` | Section 5, 8 | **DESIGN TARGET** | Plain UTF-8 text only; no media upload. |
| **Realtime Receive** | Missing | Missing | Missing Gateway | Section 11 | **MISSING / FUTURE** | Zero WebSocket gateway or Socket.IO packages in repo. |
| **Group Authorization**| Missing | Missing | `GroupMember` | Section 4 | **DESIGN TARGET** | Active `GroupMember` row required for read/write. |
| **Pagination** | Missing | Missing | Missing Endpoint | Section 7 | **DESIGN TARGET** | Cursor-based (`createdAt + id`) pagination target. |
| **Optimistic Send** | Missing | Missing | Missing Client Bloc | Section 9 | **DESIGN TARGET** | Local `SENDING` state transitioning on server ACK. |
| **Retry Failed Send** | Missing | Missing | Missing Client Bloc | Section 10 | **DESIGN TARGET** | Failed message retains text; offers `[Thử lại]` action. |
| **Idempotency** | Missing | Missing | **MISSING FROM DB** | Section 10 | **IMPLEMENTATION GAP** | Schema lacks `clientMessageId`; naive retry causes duplicate rows. |
| **Media Attachments** | Missing | Missing | **MISSING FROM DB** | Section 14 | **FUTURE / SCHEMA GAP** | No `attachmentUrl` or blob storage integration. |
| **Message Reply** | Missing | Missing | **MISSING FROM DB** | Section 14 | **FUTURE / SCHEMA GAP** | No `replyToId` foreign key column. |
| **Reactions / Emoji** | Missing | Missing | **MISSING FROM DB** | Section 14 | **FUTURE / SCHEMA GAP** | No `Reaction` model in database. |
| **Edit Message** | Missing | Missing | **MISSING FROM DB** | Section 14 | **FUTURE / SCHEMA GAP** | No `editedAt` column. |
| **Delete Message** | Missing | Missing | **MISSING FROM DB** | Section 14 | **FUTURE / SCHEMA GAP** | No `deletedAt` soft-delete column. |
| **Read Receipts** | Missing | Missing | **MISSING FROM DB** | Section 14 | **FUTURE / SCHEMA GAP** | No `readAt` / `Receipt` model; ticks forbidden in UI. |
| **Typing Indicator** | Missing | Missing | Missing Transport | Section 14 | **FUTURE** | Requires real-time WebSocket presence channel. |
| **Online Presence** | Missing | Missing | Missing Transport | Section 14 | **FUTURE** | No presence service; green online dots forbidden in UI. |
| **Push Notifications** | Missing | Missing | Missing Service | Section 17 | **DESIGN TARGET** | No FCM/APNs in repo; no instant delivery promises. |
| **User Block** | Missing | Missing | **MISSING FROM DB** | Section 16 | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserBlock`. |
| **User Report** | Missing | Missing | **MISSING FROM DB** | Section 16 | **UNSAFE / BLOCKED** | Requires new Prisma migration for `UserReport`. |

---

## 3. Exact Prisma Message Schema Audit

### 3.1. Verified Prisma Definition (`apps/backend/prisma/schema.prisma`)
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

### 3.2. Detailed Field Analysis Matrix

| Field | PostgreSQL Type | Nullable | Relation / Cascade | Current Capability | Architectural Gap & Limitation |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `id` | `UUID` | NO | Primary Key (`gen_random_uuid()`) | Unique message identifier | None. |
| `groupId` | `UUID` | NO | `Group` (`onDelete: Cascade`) | Links message to parent Group | Deleting a Group cleanly deletes all its messages. Missing composite index `[groupId, createdAt]` for pagination performance. |
| `userId` | `UUID` | NO | `User` (**NO onDelete**) | Links message to author | PostgreSQL defaults to `RESTRICT`. Deleting a User account with sent messages fails with FK error. |
| `content` | `TEXT` | NO | None | Stores plain text message | Prisma schema enforces no `VarChar` limit; requires application-layer length guard. |
| `createdAt`| `TIMESTAMPTZ` | NO | None (`default(now())`) | Creation timestamp | Serves as primary sorting field (`ASC`). Tie-breaker `id` required. |

---

## 4. Authorization Contract & Invariants

```
========================================================================
GROUP CHAT AUTHORIZATION INVARIANT
========================================================================

    [MATCHED BUDDY]        ──≠──> [GROUP CHAT ACCESS: DENIED]
    [TRIP MEMBER ONLY]     ──≠──> [GROUP CHAT ACCESS: DENIED]
    [ACTIVE GROUP MEMBER]  ──────> [GROUP CHAT ACCESS: GRANTED]

* In V1, "Active Group Member" is verified by the existence of a valid
  GroupMember row (@@unique([groupId, userId])).
========================================================================
```

### 4.1. Read Authorization (Loading Chat & History)
1. **Server Verification:** Before returning any message stream or historical page, the backend server **must query `GroupMember`** for `(groupId, currentUser.id)`.
2. **Access Denial:**
   - If no record exists: HTTP `403 Forbidden` (`ERR_FORBIDDEN_GROUP_ACCESS`).
   - Client UI displays clean access denial:
     $$\textbf{"Bạn không còn quyền truy cập cuộc trò chuyện này."}$$
   - Zero message history or sender metadata is disclosed.

### 4.2. Send Authorization (Posting New Messages)
1. **Session-Bound Identity:** The sender's `userId` **must strictly originate from the verified session/JWT token**.
2. **Impersonation Prevention:** Client payloads containing a manual `userId` field are rejected or discarded.
3. **Membership Check:** The API guard asserts that `currentUser.id` is an active `GroupMember` of `groupId`.

---

## 5. Text-Only V1 Contract

Because `model Message` only persists `content String`:
1. **Supported Message Payload:** Plain UTF-8 text only.
2. **Unsupported Media:** Images, video, audio clips, voice notes, stickers, file attachments, and GPS coordinate pins are **strictly unsupported in V1**.
3. **UI Standard:** The message composer contains a text input field and a Send button. **Zero attachment buttons (paperclips, cameras, microphones)** are rendered as active or current features.

---

## 6. History & Ordering Contract

1. **Ordering Standard:**
   $$\textbf{Primary Sort: } \text{createdAt ASC} \quad \big| \quad \textbf{Tie-Breaker: } \text{id ASC}$$
2. **History Loading:**
   - Upon entering the chat screen, the client requests the latest page of messages.
   - The messages within that page are displayed in chronological order (oldest at top, newest at bottom).
   - The scroll view defaults to the bottom (latest message).
3. **Upward Loading:**
   - Older messages are fetched on-demand upon scrolling upward (pull down to load earlier history).
   - Fetching unlimited full history in a single request is prohibited.

---

## 7. Pagination Contract (Recommended Target)

Since no backend chat controller exists, the target API contract specifies **cursor-based pagination** for stable infinite scrolling:

```http
GET /groups/:groupId/messages?cursor=<cursorId>&limit=30
Authorization: Bearer <token>
```

- **Query Parameters:**
  - `cursor`: The `id` of the oldest currently loaded message (fetching older messages before this point).
  - `limit`: Default `30`, Maximum `50`.
- **Response Structure (Target):**
  ```json
  {
    "data": [
      {
        "id": "18f2d59e-e67c-47ea-a841-38148b308da2",
        "groupId": "7b8e192c-63b7-4c4f-9e73-98f5a4387d81",
        "userId": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
        "content": "Chào mọi người! Mình đã xem qua lịch trình rồi nhé.",
        "createdAt": "2026-10-05T09:15:00.000Z",
        "author": {
          "id": "4fa85f64-5717-4562-b3fc-2c963f66afa7",
          "name": "Lê Hoàng Nam",
          "avatarUrl": null
        }
      }
    ],
    "nextCursor": "18f2d59e-e67c-47ea-a841-38148b308da2",
    "hasMore": true
  }
  ```

---

## 8. Delivery State Machine

```
========================================================================
CLIENT-VISIBLE MESSAGE DELIVERY LIFECYCLE
========================================================================

    [COMPOSING]
        │
        ▼ (User taps Send button)
    [SENDING] (Local optimistic bubble, light sending status)
        │
        ├───> [SENT] (Server ACK: confirmed Message.id & createdAt)
        │
        └───> [FAILED] (Network disconnect, timeout, or 5xx error)
                 │
                 ▼
              [RETRY] (User taps "Thử lại", re-attempts dispatch)

* Note: READ / SEEN states do NOT exist in V1 (No read receipt models).
========================================================================
```

---

## 9. Optimistic Send Contract

To ensure responsiveness:
1. When the user taps Send, the client immediately creates a temporary local bubble with state `SENDING`.
2. The input field in the composer is cleared.
3. Upon receiving the server response, the temporary bubble is updated with the persistent `id` and `createdAt` returned by Postgres, and transitions to `SENT`.
4. If the server returns an error or times out, the bubble transitions to `FAILED`.

---

## 10. Retry & Idempotency Gap

1. **Failure Display:**
   - Outgoing bubble displays warning indicator and text:
     $$\textbf{"Không gửi được · Thử lại"}$$
   - The failed message content is never discarded or wiped automatically.
2. **Idempotency Architectural Gap:**
   - `model Message` currently lacks a `clientMessageId` or `idempotencyKey` column.
   - **Risk:** A network drop occurring *after* the server writes to DB but *before* the client receives the ACK could cause duplicate messages if the user taps "Thử lại".
   - **Specification Lock:** `IDEMPOTENCY = IMPLEMENTATION GAP`. Future backend implementation must implement deduplication via client-supplied idempotency key (or Redis short-term cache).

---

## 11. Realtime Transport Boundary

1. **Current Reality:** Zero WebSocket gateways, Socket.IO clients, or ws packages exist in the repository. Realtime receive is `MISSING / FUTURE`.
2. **Target Dual-Channel Architecture:**
   - **HTTP REST:** Used for initial history loading, cursor pagination, and fallback message submission.
   - **WebSocket Gateway (`/groups/ws`):** Used for real-time broadcast of new messages (`message.created`).
3. **Gateway Authorization:** A client joining `group:{groupId}` must pass a valid JWT; the gateway verifies `GroupMember` authorization before admitting the socket to the room.

---

## 12. Reconnect & Offline UX

1. **Connection State Indicators:**
   - `CONNECTED`: Normal real-time streaming; no intrusive status banner.
   - `RECONNECTING`: Subtle amber banner below app bar:
     $$\textbf{"⟳ Đang kết nối lại... Tin nhắn sẽ được gửi khi có mạng"}$$
   - `OFFLINE`: Amber banner: `"Không có kết nối mạng"`.
2. **Offline Data Integrity:**
   - Existing loaded messages remain fully readable while offline.
   - No fake "offline background synchronization" is promised. Outgoing attempts offline immediately transition to `FAILED` with retry action.

---

## 13. Membership Loss & Disband Lifecycles

1. **Member Leaves Group:**
   - The user's `GroupMember` row is deleted.
   - Historical `Message` rows remain stored in DB (`userId` foreign key).
   - Display rule: In client rendering, author displays as `[Thành viên đã rời nhóm]` (`DESIGN TARGET`).
2. **Member Removed while Chat Open:**
   - The next authorization poll or real-time event revokes session rights.
   - The composer is disabled and replaced by:
     $$\textbf{"Bạn không còn là thành viên của nhóm này."}$$
3. **Group Disbanded (Deleted):**
   - Cascade delete removes `Message` rows from Postgres.
   - Client displays: `"Nhóm đồng hành này đã được giải tán."` Composer disabled.

---

## 14. Missing / Unsupported Capabilities (Out of Scope for V1)

The following features have **zero database schema support** and are strictly classified as `FUTURE / SCHEMA GAP`:
- **Read Receipts:** No `Seen`, `Đã xem`, or double checkmarks.
- **Typing Indicators:** No `"Nam đang nhập..."`.
- **Online Presence:** No active presence indicators or green dots.
- **Media Attachments:** No images, videos, audio, or files.
- **Message Editing:** No edit action (`editedAt` missing).
- **Message Deletion:** No client delete action (`deletedAt` missing).
- **Threaded Replies:** No `replyToId`.
- **Reactions:** No emoji reaction models.

---

## 15. Privacy & Sensitive Field Boundaries

Group Chat is a multi-user space; data protection is enforced as follows:
1. **Email:** Strictly Tier 4 — NEVER exposed anywhere in chat headers, bubbles, or info sheets.
2. **Phone Number:** Never displayed in chat. (Phone access is exclusively peer-to-peer between Matched Buddies).
3. **GPS / Location:** Live coordinates are **never broadcasted** in the chat stream.
4. **Emergency / Safety Contacts:** Private to the individual; never shared in group chats.

---

## 16. Safety & Moderation Boundaries

- User blocking (`model UserBlock`) and user reporting (`model UserReport`) are missing from the database.
- Chat moderation and block/report actions are classified as **`UNSAFE / BLOCKED DEPENDENCY`**.
- Mockups do not render active report or block buttons inside the chat stream.

---

## 17. Notification Boundary

- Push notification services (FCM/APNs) are absent.
- The chat UI **does not promise push notifications** (e.g. *"Bạn sẽ nhận thông báo tức thời khi có tin nhắn mới"*).
- Updates rely on active in-app socket streaming or pull refresh.

---

## 18. Multi-Platform Responsive Specifications

- **Mobile Viewport ($390 \times 844$):**
  - Full-height flexbox column: Status bar ($44\text{px}$), App bar ($56\text{px}$), Scrollable chat stream, Text composer ($64\text{px}$), Home indicator ($20\text{px}$).
  - Own bubbles aligned right (`#0F766E`, white text); other member bubbles aligned left (`#FFFFFF`, border `#E2E8F0`).
- **Desktop Viewport ($1440 \times 900$):**
  - 3-column workstation layout:
    - Left ($340\text{px}$): Group info, linked trip metadata, privacy notice.
    - Center ($740\text{px}$): Stream header (`Văn bản thuần`), chronological message feed, full-width text composer.
    - Right ($340\text{px}$): Downstream modules (`Lịch trình chung · Sắp có`, `Chi tiêu chuyến đi · Sắp có`), Leave group action.
- **Tablet Viewport ($768 \times 1024$):** 2-column layout (Left: Member summary, Right: Chat stream and composer).

---

## 19. Accessibility & Vietnamese-First Standards

- Minimum touch target for Send button and interactive links: $\ge 44 \times 44\text{ dp}$.
- Screen reader semantic labels:
  - Send button: `"Gửi tin nhắn"`
  - Failed message: `"Tin nhắn gửi thất bại. Nút Thử lại."`
  - Reconnecting banner: `"Đang kết nối lại mạng"`
- Color is not the sole indicator of failure: Failed bubble features a warning icon `⚠️`, distinct border, and descriptive text `"Không gửi được · Thử lại"`.

---

## 20. Current vs Future Evolution Path

```
========================================================================
GROUP CHAT EVOLUTION PATHWAY
========================================================================

    [CURRENT DB FOUNDATION]
    - model Message (id, groupId, userId, content, createdAt)
    - Cascade deletion on Group delete
    - Text-only content

        │
        ▼ (TASK 08.2.3.11: DESIGN CONTRACT LOCK)
    - Authorization guards: GroupMember only
    - Delivery states: SENDING -> SENT / FAILED -> RETRY
    - Reconnect banner & offline safety
    - Honest visual master mockups

        │
        ▼ (FUTURE BACKEND & PRISMA MIGRATIONS)
    - Migration: clientMessageId (Idempotency Key)
    - Migration: attachmentUrl, attachmentType (Media Support)
    - Gateway: WebSocket Socket.IO / ws implementation
    - Service: FCM / APNs Push Notifications
    - Migration: UserBlock, UserReport (Safety & Moderation)
========================================================================
```
