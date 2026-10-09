# GoMate Shared Expense — Trip Expense Ledger, Split & Settlement Contract V1

**Status:** APPROVED ARCHITECTURAL CONTRACT & DESIGN LOCK  
**Task:** TASK 08.2.3.13 — GOMATE SHARED EXPENSE: TRIP EXPENSE LEDGER, SPLIT & SETTLEMENT CONTRACT V1  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$), Tablet ($768 \times 1024$)  
**Source of Truth:**
- Database Schema: [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) (`model Trip`, `model TripMember`, `model Itinerary`, `model ItineraryItem`, `model Group`, `model GroupMember`, `model User`)
- Backend Code: [`apps/backend/src/modules/trips/trips.controller.ts`](file:///d:/Do_an/wanderai/apps/backend/src/modules/trips/trips.controller.ts), [`apps/backend/src/modules/trips/trips.service.ts`](file:///d:/Do_an/wanderai/apps/backend/src/modules/trips/trips.service.ts)
- Mobile Client Code: [`apps/mobile/lib/features/trips/`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/trips/)
- Core Upstream Contracts:
  - [`docs/design/gomate-trip-user-flow-spec-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-trip-user-flow-spec-v1.md)
  - [`docs/design/gomate-trip-visual-spec-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-trip-visual-spec-v1.md)
  - [`docs/design/gomate-group-foundation-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-group-foundation-contract-v1.md)
  - [`docs/design/gomate-group-chat-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-group-chat-contract-v1.md)
  - [`docs/design/gomate-shared-itinerary-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-shared-itinerary-contract-v1.md)
- Master Visual Evidence Artifacts:
  - Mobile Overview V1: [`shared-expense-mobile-overview-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-overview-v1.png) ($390 \times 844$)
  - Mobile Add Expense V1: [`shared-expense-mobile-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-add-v1.png) ($390 \times 844$)
  - Mobile Expense Detail R1: [`shared-expense-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-detail-r1.png) ($390 \times 844$) *(Replaces V1: neutral split shares, removes fake OCR ad)*
  - Mobile Balances & Settlements R1: [`shared-expense-mobile-balances-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-balances-r1.png) ($390 \times 844$) *(Replaces V1: honest 1.2M spent vs 500k debt copy, zero-sum conservation)*
  - Mobile Empty State V1: [`shared-expense-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-empty-v1.png) ($390 \times 844$)
  - Desktop Master Workstation V1: [`shared-expense-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-desktop-v1.png) ($1440 \times 900$)

---

## 1. Product Role & Mission

The **GoMate Shared Expense** module governs the actual group expenditure ledger, transparent cost-splitting, net balance calculation, and manual debt settlement reconciliation across all participants of a shared Trip.

### Conceptual Lifecycle:
$$\text{ACTUAL EXPENSE} \longrightarrow \text{WHO PAID} \longrightarrow \text{WHO PARTICIPATED} \longrightarrow \text{SPLIT MODE} \longrightarrow \text{INDIVIDUAL SHARES} \longrightarrow \text{NET BALANCES} \longrightarrow \text{WHO OWES WHOM} \longrightarrow \text{SETTLEMENT RECORD}$$

This module provides financial clarity, prevents interpersonal disputes, and gives travelers an auditable shared ledger without acting as an e-wallet or money transmitter.

---

## 2. Current Capability Audit (Repository Reality)

A comprehensive inspection of the current codebase confirms the exact runtime baseline:

1. **Database Schema (`schema.prisma`):**
   - **`model Expense`:** **MISSING** (Schema Gap).
   - **`model ExpenseSplit`:** **MISSING** (Schema Gap).
   - **`model Settlement`:** **MISSING** (Schema Gap).
   - There are **ZERO expense tables**, zero split tables, and zero ledger models in PostgreSQL.
2. **Backend API (`apps/backend/src/modules/trips/`):**
   - Endpoints for expenses, debts, or settlement reconciliation: **MISSING** (API Gap).
   - Object/file storage for receipt photos (S3/GCS/MinIO/Multer): **MISSING** (Infrastructure Gap).
   - Payment gateway integrations (MoMo/VNPay/ZaloPay/Stripe): **MISSING / EXCLUDED BY DESIGN**.
   - OCR receipt parsing engine: **MISSING / FUTURE**.
3. **Mobile Client (`apps/mobile/lib/features/trips/`):**
   - Features present: Trip CRUD, Itinerary timeline, AI Planner preview, Place details.
   - Expense screens, ledger widgets, and debt settlement UI: **MISSING** in production code.

**Classification:** The entire Shared Expense module is a **DESIGN TARGET / ARCHITECTURAL SPECIFICATION**. Zero production runtime code exists today.

---

## 3. Expense Ledger vs. Itinerary Estimated Cost (Critical Boundary)

A strict architectural boundary is locked between planning estimates and actual expenditures:

$$\textbf{ItineraryItem.estimatedCost} \quad \ne \quad \textbf{Shared Expense Ledger}$$

| Dimension | Itinerary Estimated Cost (`ItineraryItem.estimatedCost`) | Shared Expense Ledger (`Expense` / `ExpenseSplit`) |
| :--- | :--- | :--- |
| **Nature** | Informational, speculative planning estimate | Canonical, historical financial record |
| **Data Source** | AI Planner suggestion or user estimate | Actual money spent by a specific traveler |
| **Timing** | Defined before the trip begins | Recorded during or after an activity occurs |
| **Attribution** | Anonymous to the trip itinerary | Attributed to exact payer (`paidByUserId`) and participants |
| **Balance Impact** | Zero effect on who owes whom | Deterministically alters member net balances |
| **Automation** | Calculated automatically by AI or manual input | **NEVER automatically converted from Itinerary** |

> [!IMPORTANT]
> **No Automatic Conversion:** The system must NEVER automatically create expenses from itinerary items. Any future feature such as *"Tạo khoản chi từ hoạt động lịch trình"* requires explicit human confirmation, selection of the actual payer, and verification of the final bill amount.

---

## 4. Canonical Ownership (Trip-Owned Ledger)

The financial ledger belongs strictly and immutably to [`model Trip`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L399-L425):

$$\textbf{Trip} \longrightarrow \textbf{Expense Ledger (Expenses, Splits, Settlements)}$$

1. **No Group Ownership:** A Companion Group ([`model Group`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L558-L569)) does **NOT** own the expense database tables. A Group is purely a social chat and contextual UI entry point linked via `Group.tripId`.
2. **Group Deletion Invariant:** If a companion Group is deleted or archived, the canonical Trip expense ledger **remains 100% intact and auditable**.
3. **Leaving Group Invariant:** If a traveler leaves a companion Group, their historical expense participations, payments, and debts in the Trip ledger **are NEVER erased or altered**.

---

## 5. Required Target Data Model (Target Schema Specification)

To operationalize the module downstream without schema contradictions, the target relational schema is specified as follows:

```prisma
// Target Schema Specification (TASK 08.2.3.13)
enum ExpenseCategory {
  FOOD           // Ăn uống
  TRANSPORT      // Di chuyển
  ACCOMMODATION  // Lưu trú
  TICKET         // Vé tham quan
  SHOPPING       // Mua sắm
  OTHER          // Khác
}

enum SplitType {
  EQUAL          // Chia đều
  CUSTOM         // Tùy chỉnh số tiền
}

// NOTE: SettlementStatus enum is REMOVED in R1.
// ExpenseSplit does NOT track individual settlement status.
// model Settlement is the SOLE canonical source of truth for debt reconciliation.

model Expense {
  id              String          @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  tripId          String          @map("trip_id") @db.Uuid
  paidByUserId    String          @map("paid_by_user_id") @db.Uuid
  title           String          @db.VarChar(200)
  amount          Int             // Integer VND (> 0)
  currency        String          @default("VND") @db.VarChar(10)
  category        ExpenseCategory @default(OTHER)
  splitType       SplitType       @default(EQUAL) @map("split_type")
  expenseDate     DateTime        @default(now()) @map("expense_date") @db.Date
  notes           String?         @db.Text
  createdByUserId String          @map("created_by_user_id") @db.Uuid
  createdAt       DateTime        @default(now()) @map("created_at") @db.Timestamptz
  updatedAt       DateTime        @updatedAt @map("updated_at") @db.Timestamptz
  deletedAt       DateTime?       @map("deleted_at") @db.Timestamptz

  trip            Trip            @relation(fields: [tripId], references: [id], onDelete: Cascade)
  payer           User            @relation("ExpensePayer", fields: [paidByUserId], references: [id], onDelete: Restrict)
  creator         User            @relation("ExpenseCreator", fields: [createdByUserId], references: [id], onDelete: Restrict)
  splits          ExpenseSplit[]

  @@index([tripId])
  @@map("expenses")
}

model ExpenseSplit {
  id              String           @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  expenseId       String           @map("expense_id") @db.Uuid
  userId          String           @map("user_id") @db.Uuid
  shareAmount     Int              @map("share_amount") // Integer VND (> 0) - Immutable allocation obligation
  createdAt       DateTime         @default(now()) @map("created_at") @db.Timestamptz

  expense         Expense          @relation(fields: [expenseId], references: [id], onDelete: Cascade)
  user            User             @relation(fields: [userId], references: [id], onDelete: Restrict)

  @@unique([expenseId, userId])
  @@index([userId])
  @@map("expense_splits")
}

model Settlement {
  id              String          @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  tripId          String          @map("trip_id") @db.Uuid
  debtorId        String          @map("debtor_id") @db.Uuid   // Người hoàn tiền
  creditorId      String          @map("creditor_id") @db.Uuid // Người nhận tiền
  amount          Int             // Integer VND (> 0) - Offline reimbursement amount
  currency        String          @default("VND") @db.VarChar(10)
  notes           String?         @db.Text
  settledAt       DateTime        @default(now()) @map("settled_at") @db.Timestamptz
  createdByUserId String          @map("created_by_user_id") @db.Uuid

  trip            Trip            @relation(fields: [tripId], references: [id], onDelete: Cascade)
  debtor          User            @relation("SettlementDebtor", fields: [debtorId], references: [id], onDelete: Restrict)
  creditor        User            @relation("SettlementCreditor", fields: [creditorId], references: [id], onDelete: Restrict)
  creator         User            @relation("SettlementCreator", fields: [createdByUserId], references: [id], onDelete: Restrict)

  @@index([tripId])
  @@map("settlements")
}
```

---

## 6. Access Control & Authorization Matrix

Access to the shared expense ledger requires strict server-side validation against [`model Trip`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L399-L425) and [`model TripMember`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L83-L94):

| User Persona | View Ledger | Add Expense | Edit/Delete Expense | Record Settlement | Rationale & Security Boundary |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Trip Owner** (`trip.userId === req.user.id`) | **YES** | **YES** | **YES** (All) | **YES** (All)* | Trip administrator and primary financial trustee. |
| **Trip Member** (`TripMember.tripId === trip.id`) | **YES** | **YES** | **YES** (Own only)* | **YES** (Involved)* | Active member participating in trip expenses. |
| **GroupMember only** (No `TripMember` record) | **NO (403)**| **NO (403)**| **NO (403)** | **NO (403)** | Group chat membership does NOT grant financial access. |
| **Matched Buddy** (No trip invitation) | **NO (403)**| **NO (403)**| **NO (403)** | **NO (403)** | Consent match does NOT grant access to private trips. |
| **Unrelated Stranger** | **NO (403)**| **NO (403)**| **NO (403)** | **NO (403)** | Blocked by `findById` trip authorization guard. |

### Settlement Authorization Rules & Server Invariants:
1. **Trip Owner Authority:** The Trip Owner may record any valid settlement within the trip to resolve bookkeeping errors or assist members.
2. **Member Invariant (Involved Parties Only):** A regular TripMember may record a settlement **only if** they are a direct participant:
   $$\text{req.user.id} == \text{debtorId} \quad \lor \quad \text{req.user.id} == \text{creditorId}$$
   An unrelated TripMember cannot record a settlement between two other members (`403 Forbidden`).
3. **Identity Invariant:** `createdByUserId` is strictly server-injected from the authenticated JWT session (`req.user.id`). Client-supplied creator IDs are ignored.
4. **Amount Invariant:** `settlement.amount > 0` and must not exceed the current outstanding net debt between `debtorId` and `creditorId`.
5. **Expense Edit/Delete Authority:** A TripMember may edit or delete an expense only if `expense.createdByUserId === req.user.id`. The Trip Owner can edit/delete any expense to maintain ledger health.

---

## 7. Expense Entity Contract

Every expense entry must validate the following invariants:
1. `title`: Required, non-empty, max 200 characters.
2. `amount`: Required integer $> 0$.
3. `currency`: Defaults to `Trip.currency` (VND).
4. `paidByUserId`: Must reference an active participant of the trip (`trip.userId` or active `TripMember`).
5. `category`: One of `FOOD`, `TRANSPORT`, `ACCOMMODATION`, `TICKET`, `SHOPPING`, `OTHER`.
6. `expenseDate`: Date format `YYYY-MM-DD`, defaulting to current date.
7. `createdByUserId`: Server-injected from authenticated JWT token (`req.user.id`).

---

## 8. Participants & Scope of Splitting

An expense does not automatically apply to all trip members. The payer selects participants per bill:
- **All Members:** Default option (e.g., group dinner, airport shuttle).
- **Selected Members:** Subset of participants (e.g., coffee for 2 members, special attraction ticket for 1 member).

**Invariant:** Only selected participants receive an `ExpenseSplit` record. Non-participants incur $0\text{ VND}$ debt and their balances remain completely unaffected by that specific expense.

---

## 9. Split Mode — Equal Split (Chia Đều)

In `EQUAL` mode, the total bill is divided evenly among all $N$ selected participants:

$$\text{baseShare} = \lfloor \frac{\text{amount}}{N} \rfloor$$
$$\text{remainder} = \text{amount} \pmod N$$

### Deterministic Remainder Assignment:
Because VND does not use fractional cents, any integer remainder $(1 \le \text{remainder} < N)$ is assigned deterministically to the first $\text{remainder}$ participants ordered by `userId ASC`:
- First $\text{remainder}$ participants: $\text{share} = \text{baseShare} + 1\text{ VND}$.
- Remaining participants: $\text{share} = \text{baseShare}\text{ VND}$.

$$\sum_{i=1}^N \text{share}_i = \text{amount} \quad \text{(Zero VND lost)}$$

*Example:* $100.000\text{ VND}$ split among 3 members: Member 1 gets $33.334\text{ đ}$, Member 2 gets $33.333\text{ đ}$, Member 3 gets $33.333\text{ đ}$. Total $= 100.000\text{ đ}$.

---

## 10. Split Mode — Custom Amount (Tùy Chỉnh Số Tiền)

In `CUSTOM` mode, the creator specifies exact integer amounts for each participant.

### Strict Validation Rule:
$$\sum_{i=1}^N \text{shareAmount}_i = \text{expense.amount}$$

If the sum of shares does not equal the expense total, the client disables the save action and displays an explicit validation banner:
$$\textbf{"Tổng phần chia phải bằng đúng tổng khoản chi."}$$
Server-side validation rejects any non-matching payload with `400 Bad Request`.

---

## 11. Money Invariants & Representation

1. **Integer Arithmetic Only:** All monetary figures in VND are stored and manipulated as integers (`Int`). Zero floating-point arithmetic is permitted.
2. **Positive Amounts:** `expense.amount > 0` and `shareAmount > 0`. Zero or negative expense amounts are prohibited.
3. **Zero-Sum Ledger Conservation:** At all times, across all expenses and settlements:
   $$\sum_{u \in \text{TripParticipants}} \text{netBalance}(u) = 0$$

---

## 12. Currency Boundary

1. **Canonical Currency:** All expenses inherit `Trip.currency` (default `"VND"`).
2. **No Automatic FX:** Because no foreign exchange rate provider exists in the repository, multi-currency conversion (e.g. USD $\rightarrow$ VND) is **EXCLUDED** from V1.
3. **Classification:** Multi-currency support is classified as **FUTURE INFRASTRUCTURE**.

---

## 13. Balance Algorithm (Công Thức Tính Toán Công Nợ)

For each participant $u$ in the trip, the ledger calculates their net financial position deterministically from raw immutable records:

### 1. Base Expense Positions:
- **Total Paid by User:**
  $$\text{paidAmount}(u) = \sum \{ \text{expense.amount} \mid \text{expense.paidByUserId} = u \}$$
- **Total Owed by User (Sum of Expense Obligations):**
  $$\text{owedAmount}(u) = \sum \{ \text{split.shareAmount} \mid \text{split.userId} = u \}$$
- **Base Net Position (Trước quyết toán):**
  $$\text{baseNet}(u) = \text{paidAmount}(u) - \text{owedAmount}(u)$$

### 2. Settlement Adjustments:
Reimbursements occur via `Settlement` records (where debtor $D$ pays creditor $C$):
- **Outgoing Settlements (Tiền đã hoàn trả cho chủ nợ):**
  $$\text{outgoingSettlement}(u) = \sum \{ s.\text{amount} \mid s.\text{debtorId} = u \}$$
- **Incoming Settlements (Tiền đã nhận lại từ người nợ):**
  $$\text{incomingSettlement}(u) = \sum \{ s.\text{amount} \mid s.\text{creditorId} = u \}$$

### 3. Net Outstanding Balance (Vị thế công nợ còn lại):
$$\text{netOutstanding}(u) = \text{paidAmount}(u) - \text{owedAmount}(u) + \text{outgoingSettlement}(u) - \text{incomingSettlement}(u)$$
$$\text{netOutstanding}(u) = \text{baseNet}(u) + \text{outgoingSettlement}(u) - \text{incomingSettlement}(u)$$

### 4. Semantic Interpretation:
- $\text{netOutstanding}(u) > 0$: **Được nhận lại** (Creditor — other members still owe this user money).
- $\text{netOutstanding}(u) < 0$: **Cần trả** (Debtor — this user still owes money to the group).
- $\text{netOutstanding}(u) = 0$: **Cân đối** (Fully balanced — all obligations cleared).

### 5. Mathematical Zero-Sum Conservation Invariant:
At all times (before, during, and after any number of partial or full settlements):
$$\sum_{u \in \text{TripParticipants}} \text{netOutstanding}(u) = 0\text{ VND}$$

### 6. Outstanding Debt Aggregate vs. Total Actual Spending:
- **Total Actual Spending (Tổng chi tiêu đã ghi nhận):**
  $$\text{totalSpent} = \sum \text{expense.amount} = 1.200.000\text{ đ}$$
- **Total Outstanding Debt (Công nợ còn cần quyết toán):**
  $$\text{totalOutstandingDebt} = \sum_{u, \text{netOutstanding}(u) < 0} |\text{netOutstanding}(u)| = |-100.000| + |-400.000| = 500.000\text{ đ}$$
These two metrics represent distinct financial dimensions and MUST NEVER be conflated in UI copy.

---

## 14. Minimal Settlement Algorithm (Thuật Toán Đề Xuất Quyết Toán)

To minimize interpersonal friction and bank transactions, GoMate uses a greedy settlement resolution algorithm:

1. Separate participants into **Creditors** ($\text{netBalance} > 0$) and **Debtors** ($\text{netBalance} < 0$).
2. Sort creditors descending by balance; sort debtors ascending by balance.
3. While both lists are non-empty:
   - Match the largest debtor $D$ with the largest creditor $C$.
   - $\text{settlementAmount} = \min(|D.\text{balance}|, C.\text{balance})$.
   - Propose: $D \longrightarrow C : \text{settlementAmount}$.
   - Update balances: $D.\text{balance} \mathrel{+}= \text{settlementAmount}$, $C.\text{balance} \mathrel{-}= \text{settlementAmount}$.
   - Remove any participant whose balance reaches $0$.

This guarantees at most $N - 1$ settlement transactions for $N$ members.

---

## 15. Settlement Lifecycle & Payment Boundary

### CRITICAL DISTINCTION:
$$\textbf{"Ghi nhận đã hoàn tiền" } \ne \textbf{ Thanh toán tiền điện tử}$$

1. **Sole Source of Truth for Debt Clearance:** `model Settlement` is the **only** canonical entity that records debt reimbursement in GoMate. `ExpenseSplit` records are immutable allocation shares and never hold settlement statuses or timestamps.
2. **Ledger Impact:** Recording a settlement directly updates `outgoingSettlement(debtor)` and `incomingSettlement(creditor)`. It decreases the debtor's debt and the creditor's receivable without modifying historical expense records.
3. **Manual Record Only:** GoMate is an **expense tracking ledger**, NOT an e-wallet, payment gateway, or banking app.
4. **Zero Financial Transfer:** Clicking *"Ghi nhận đã hoàn tiền"* records a ledger settlement event indicating that money changed hands offline (via cash, external bank transfer, or mutual agreement).
5. **No Third-Party Claims:** The UI strictly omits any fake branding for MoMo, ZaloPay, VNPay, PayPal, or card charging.
6. **Server-Side Validation Rules:**
   - `amount > 0` (Integer VND).
   - `debtorId !== creditorId`.
   - `amount <= currentNetDebt(debtor, creditor)`: The system rejects over-settlement.
   - `createdByUserId` must be Trip Owner, the debtor, or the creditor.
7. **Settlement Confirmation Modal:**
   - Dialog Title: *"Xác nhận ghi nhận đã hoàn tiền?"*
   - Details: `Người hoàn tiền: [Tên]` $\rightarrow$ `Người nhận: [Tên]` · `Số tiền: [X đ]`.
   - Actions: `[Xác nhận]` | `[Hủy]`.

---

## 16. Canonical Mathematical Demo Dataset (100% Reconciled)

All master mockups across mobile and desktop are strictly synchronized to the following canonical dataset:

### Trip Context:
- **Trip:** "Khám phá Đà Nẵng 4N3Đ" (15/10 - 18/10/2026)
- **Total Budget:** $5.000.000\text{ VND}$
- **Planned Itinerary Estimate:** $2.800.000\text{ VND}$ *(Separate planning info)*
- **Participants:**
  1. **Lê Hoàng Nam** (Chủ chuyến đi / Trip Owner · Viewer)
  2. **Trần Khánh** (Thành viên / TripMember)
  3. **Nguyễn Thị Mai** (Thành viên / TripMember)

### Ledger Events:
1. **Expense #1:**
   - Title: *"Ăn tối Bếp Cuốn Đà Nẵng"*
   - Category: `Ăn uống` · Date: 15/10/2026
   - Total Amount: **$900.000\text{ đ}$**
   - Paid by: **Lê Hoàng Nam**
   - Participants: Nam ($300\text{k}$), Khánh ($300\text{k}$), Mai ($300\text{k}$) — Equal Split
2. **Expense #2:**
   - Title: *"Taxi ra Bán đảo Sơn Trà"*
   - Category: `Di chuyển` · Date: 15/10/2026
   - Total Amount: **$300.000\text{ đ}$**
   - Paid by: **Trần Khánh**
   - Participants: Nam ($100\text{k}$), Khánh ($100\text{k}$), Mai ($100\text{k}$) — Equal Split

### Mathematical Reconciliation:
- **Total Actual Spent (Tổng chi tiêu đã ghi nhận):** $900.000 + 300.000 = \mathbf{1.200.000\text{ VND}}$ ($24\%$ of $5\text{M}$ budget).
- **Total Outstanding Debt (Công nợ còn cần quyết toán):** $|-100.000| + |-400.000| = \mathbf{500.000\text{ VND}}$.
- **Remaining Actual Budget:** $5.000.000 - 1.200.000 = \mathbf{+3.800.000\text{ VND}}$.
- **Member Balances:**
  - **Nam:** Paid $900\text{k}$ · Shares: $300\text{k} + 100\text{k} = 400\text{k} \implies \mathbf{+500.000\text{ đ}}$ (Được nhận lại)
  - **Khánh:** Paid $300\text{k}$ · Shares: $300\text{k} + 100\text{k} = 400\text{k} \implies \mathbf{-100.000\text{ đ}}$ (Cần trả)
  - **Mai:** Paid $0\text{ đ}$ · Shares: $300\text{k} + 100\text{k} = 400\text{k} \implies \mathbf{-400.000\text{ đ}}$ (Cần trả)
- **Conservation Check:**
  $$\sum \text{netOutstanding} = +500.000 + (-100.000) + (-400.000) = \mathbf{0\text{ VND}}$$
- **Canonical UI Copy Alignment (Balances Screen R1):**
  - Metric 1: *"Tổng chi tiêu đã ghi nhận: 1.200.000 đ"*
  - Metric 2: *"Công nợ còn cần quyết toán: 500.000 đ"*
  - Accounting invariant note: *"Bảo toàn giá trị: Tổng vị thế ròng = 0 đ"*
  - Debt counter: *"2 khoản nợ chưa quyết toán"*
- **Canonical UI Copy Alignment (Expense Detail Screen R1):**
  - Payer card: *"Lê Hoàng Nam (Bạn) / Đã thanh toán: 900.000 đ · Ứng trước ròng: 600.000 đ"*
  - Split rows: Neutral allocation obligations (Nam: $300\text{k}$, Khánh: $300\text{k}$, Mai: $300\text{k}$), without confusing per-split "Chưa hoàn tiền" labels.
- **Minimal Settlements:**
  1. Trần Khánh $\longrightarrow$ Lê Hoàng Nam : **$100.000\text{ đ}$**
  2. Nguyễn Thị Mai $\longrightarrow$ Lê Hoàng Nam : **$400.000\text{ đ}$**

---

## 17. Expense Create, Edit & Delete Lifecycle

1. **Create Flow:**
   - Form fields: Title \*, Amount \*, Category, Payer \*, Participants \*, Split Mode \*, Date, Notes.
   - Realtime preview of per-person shares.
   - Explicit confirmation CTA `[Lưu khoản chi vào sổ quỹ]`.
2. **Edit Flow:**
   - Modifying any financial field (amount, payer, participant list, split mode) triggers a full recalculation of shares.
   - Silent balance updates are prohibited.
3. **Delete Flow:**
   - Destructive action requiring explicit confirmation modal:
     - Title: *"Xóa khoản chi này?"*
     - Supporting copy: *"Khoản chi và các phần chia liên quan sẽ bị loại khỏi sổ quỹ và tự động cập nhật lại công nợ cả nhóm."*
     - Primary: `[Xóa]` (Danger red) | Secondary: `[Hủy]`.

---

## 18. Membership Lifecycle & Historical Debt Preservation

1. **Member Leaves Trip:**
   - If a member leaves or is removed from a trip, their historical `ExpenseSplit` and payment records **MUST NOT be deleted**.
   - Leaving the trip does **NOT** forgive outstanding debt.
   - The member's name remains visible on historical ledger cards with an inactive status tag: `(Đã rời chuyến đi)`.
2. **User Account Deletion (Architecture & Policy Reality):**
   - **Schema Reality:** Target schema uses `onDelete: Restrict` for all user foreign keys (`paidByUserId`, `userId`, `debtorId`, `creditorId`).
   - Consequently, a User account with recorded financial transactions **CANNOT be hard-deleted** from PostgreSQL without violating relational integrity.
   - **Policy Classification:** Hard user deletion, snapshot name decoupling, and GDPR "right to be forgotten" in financial ledgers are classified as **`FUTURE ARCHITECTURE / POLICY GAP`**.
   - The system does **NOT** claim immutable snapshot support or automatic nullification exists in V1.

---

## 19. Privacy & Safety Boundary

1. **Exposed Ledger Data:**
   - Display name, profile avatar, expense title, amount, category, date, personal share, and trip-level settlement records.
2. **Strictly Concealed Private Data:**
   - **NEVER EXPOSED:** Email address, phone number, bank account details, credit card numbers, password/JWT tokens, live GPS coordinates, or emergency contacts.

---

## 20. Receipt & Attachment Boundary

1. **Current Infrastructure Reality:** No object storage service (S3/MinIO) or file upload endpoint exists in the repository.
2. **Boundary Rules:**
   - Photo attachment / receipt upload is classified as **FUTURE CAPABILITY**.
   - OCR automatic bill scanning is classified as **FUTURE AI SERVICE**.
   - **Honest Production UI:** Production screens show clean manual expense entry and clean notes without promotional paragraphs for unimplemented OCR or camera scanning.

---

## 21. Integration Boundary with Shared Itinerary

- The Itinerary timeline ([TASK 08.2.3.12](file:///d:/Do_an/wanderai/docs/design/gomate-shared-itinerary-contract-v1.md)) displays planned activities and daily estimated costs.
- The Expense workstation displays a quick-nav link: `[Xem Lịch trình chung]`.
- Summary cards clearly label: *"Kế hoạch dự tính: 2.800.000 đ (thông tin tham chiếu độc lập)"*.

---

## 22. Integration Boundary with Companion Group

- Companion Group Chat ([TASK 08.2.3.11](file:///d:/Do_an/wanderai/docs/design/gomate-group-chat-contract-v1.md)) displays a contextual link to `[Chi tiêu chuyến đi]`.
- When an expense is logged or a settlement is recorded, an automated system notification message may be posted into the group chat stream in the future.
- Deleting the Group chat room does **NOT** alter or delete the Trip expense ledger.

---

## 23. Wandy AI Financial Boundary

Wandy AI Copilot serves as an informational assistant:
- **Allowed Future Capabilities:** Summarize total spending, compare actual vs. planned budget, identify highest-cost categories, and explain who owes whom.
- **Strictly Prohibited Autonomous Actions:** Wandy **MUST NOT** create expenses, edit amounts, alter payers, modify participant splits, or settle debts without explicit human confirmation.

---

## 24. Error & Loading State Machine

The client application must handle the following explicit UI states:
- `LOADING`: Shimmer card placeholders for ledger items and balance metrics.
- `EMPTY`: Renders [`shared-expense-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-empty-v1.png) when $0$ expenses exist.
- `LOADED`: Standard interactive ledger view.
- `SAVE_FAILED`: Friendly banner: *"Không thể lưu khoản chi. Vui lòng kiểm tra kết nối mạng và thử lại."*
- `ACCESS_DENIED`: Friendly error: *"Bạn không có quyền truy cập sổ chi tiêu của chuyến đi này."*
- `VALIDATION_FAILED`: Form banner: *"Tổng phần chia phải bằng đúng tổng khoản chi."*
- `SETTLEMENT_CONFIRM`: Confirmation sheet before recording offline debt clearance.

Raw database errors (Prisma, SQL, 500) are never exposed to users.

---

## 25. Accessibility Standards (WCAG 2.1 AA)

1. **Touch Targets:** All interactive buttons and filter chips $\ge 44 \times 44\text{ dp}$.
2. **Color Independence:** Financial balances are NEVER conveyed by color alone. Every credit/debt badge includes unambiguous text:
   - Green text: `"+500.000 đ · Được nhận lại"`
   - Amber text: `"-100.000 đ · Cần trả"`
3. **Screen Reader Labels:** Numeric amounts include full currency words (e.g. `aria-label="Một triệu hai trăm nghìn đồng"`).

---

## 26. Multi-Platform Responsive Specifications

- **Mobile Viewport ($390 \times 844$):** Single-column stacked layout with top summary, balance card, category filters, expense card list, and canonical 5-tab root navigation.
- **Desktop Viewport ($1440 \times 900$):** High-density 3-column workstation:
  - Column 1 ($330\text{px}$): Trip members with net balance pills, category filter navigation, and quick links.
  - Column 2 ($740\text{px}$ flex): Sổ quỹ chi tiêu thực tế with search, expense cards, and balance reconciliation bar.
  - Column 3 ($330\text{px}$): Budget vs. actual summary card, minimal settlement suggestions, and Wandy AI assistant card.
- **Tablet Viewport ($768 \times 1024$):** 2-column layout combining left sidebar with main ledger and responsive right modal.

---

## 27. Current vs. Future Capability Matrix

| Dimension | Current Runtime Status | Architectural Contract V1 / R1 | Future Target |
| :--- | :---: | :---: | :--- |
| **Expense Data Model** | **MISSING** | **SCHEMA SPECIFICATION** | PostgreSQL `model Expense` migration |
| **Expense Split Model** | **MISSING** | **SCHEMA SPECIFICATION** | PostgreSQL `model ExpenseSplit` (immutable share obligations) |
| **Per-Split Settlement Status** | **EXCLUDED** | **REMOVED FROM V1** | Anti-pattern eliminated; zero status columns in `ExpenseSplit` |
| **Settlement Model** | **MISSING** | **SCHEMA SPECIFICATION** | PostgreSQL `model Settlement` (sole canonical truth) |
| **Trip-Level Settlement Record**| **MISSING** | **DESIGN LOCKED** | Offline reconciliation marking between debtor and creditor |
| **Equal Split (Chia đều)**| **MISSING** | **DESIGN LOCKED** | Backend deterministic remainder split |
| **Custom Split (Tùy chỉnh)**| **MISSING**| **DESIGN LOCKED** | Client/server zero-sum validation |
| **Balance Calculation** | **MISSING** | **DESIGN LOCKED** | Explicit sign formula: $\text{baseNet} + \text{outgoing} - \text{incoming}$ |
| **Settlement Suggestions** | **MISSING**| **DESIGN LOCKED** | Greedy $N-1$ transaction minimizer |
| **User Deletion / History** | **RESTRICTED**| **FUTURE ARCHITECTURE / POLICY GAP** | Snapshot decoupling / anonymization policy |
| **E-Wallet / Card Payment**| **EXCLUDED**| **OUT OF SCOPE** | Payment gateway integration |
| **Receipt Photo Upload** | **MISSING** | **FUTURE SPECIFICATION** | S3 / MinIO object storage |
| **Receipt OCR Scanner** | **MISSING** | **FUTURE SPECIFICATION** | Multimodal Gemini receipt parser |
| **Push Notifications** | **MISSING** | **FUTURE SPECIFICATION** | FCM/APNs debt reminder alerts |
| **Multi-Currency / FX** | **MISSING** | **FUTURE SPECIFICATION** | Live exchange rate provider |
