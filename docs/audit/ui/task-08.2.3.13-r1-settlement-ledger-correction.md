# GoMate Shared Expense — Settlement Source-of-Truth & Ledger Semantics Correction (TASK 08.2.3.13-R1)

**Status:** APPROVED ARCHITECTURAL ADDENDUM & DESIGN LOCK  
**Task:** TASK 08.2.3.13-R1 — GOMATE SHARED EXPENSE: SETTLEMENT SOURCE-OF-TRUTH & LEDGER SEMANTICS FIX  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Master Visual Evidence Artifacts:**
- Mobile Expense Detail R1: [`shared-expense-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-detail-r1.png) ($390 \times 844$)
- Mobile Balances & Settlements R1: [`shared-expense-mobile-balances-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-balances-r1.png) ($390 \times 844$)
- Mobile Overview V1: [`shared-expense-mobile-overview-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-overview-v1.png) ($390 \times 844$)
- Mobile Add Expense V1: [`shared-expense-mobile-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-add-v1.png) ($390 \times 844$)
- Mobile Empty State V1: [`shared-expense-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-empty-v1.png) ($390 \times 844$)
- Desktop Master Workstation V1: [`shared-expense-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-desktop-v1.png) ($1440 \times 900$)

---

## 1. Executive Summary

TASK 08.2.3.13-R1 executes targeted architectural and visual ledger corrections for the GoMate Shared Expense module before final Design Lock.

This addendum formalizes 5 critical micro-corrections:
1. **Settlement Data Architecture & Removal of Duplicate State:** `ExpenseSplit` is locked as an immutable allocation obligation; all settlement tracking fields are purged. `Settlement` is established as the sole canonical source of truth for debt clearance.
2. **Net Balance Formula with Explicit Settlement Signs:** Formalized the bidirectional sign conventions for outgoing vs. incoming settlements, guaranteeing zero-sum conservation at all times.
3. **Balances Screen Semantics Correction:** Fixed confusing banner copy in `shared-expense-mobile-balances-r1.png`, strictly distinguishing total actual expenses recorded ($1.200.000\text{ đ}$) from remaining outstanding debt ($500.000\text{ đ}$).
4. **Expense Detail Split Semantics Correction:** Purged misleading per-split settlement tags from `shared-expense-mobile-detail-r1.png` and removed fake OCR/receipt scanner advertisements from the production UI.
5. **User Account Deletion & Lifecycle Honesty:** Reconciled schema realities (`onDelete: Restrict`) and classified hard-deletion/anonymization as a `FUTURE ARCHITECTURE / POLICY GAP`.
6. **Settlement Authorization Rules:** Locked strict server validation preventing unrelated third parties from logging settlements between others.

---

## 2. Micro-Correction Breakdown (Before → Risk → Evidence → Correction → Locked Contract)

### 2.1. Settlement Data Architecture & Duplicate State Removal

- **Before:** V1 draft schema placed `status SettlementStatus @default(UNSETTLED)` and `settledAt DateTime?` directly on `model ExpenseSplit`, while concurrently defining a separate `model Settlement`.
- **Risk:**
  - Duplicate source of truth: A payment could be recorded in `Settlement` but fail to update an individual `ExpenseSplit.status`, or vice-versa.
  - Granularity mismatch: A reimbursement in group travel settles a traveler's net debt to another traveler across multiple past meals/rides, not necessarily a 1-to-1 match with a single bill's split.
  - Partial settlement impossibility: If a user owes $300\text{k}$ across two splits of $150\text{k}$ each, recording a single $200\text{k}$ settlement cannot map cleanly onto binary `SETTLED`/`UNSETTLED` enum flags.
- **Evidence:** [`docs/design/gomate-shared-expense-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-shared-expense-contract-v1.md#L113-L178).
- **Correction:**
  - Completely remove `enum SettlementStatus`.
  - Remove `status` and `settledAt` from `model ExpenseSplit`.
  - `ExpenseSplit` represents solely the immutable allocation obligation ($\text{shareAmount}$) incurred when an expense is logged.
  - `model Settlement` is the **SOLE** canonical source of truth for financial reconciliation between two travelers.
- **Locked Contract:**
  ```prisma
  model ExpenseSplit {
    id          String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
    expenseId   String   @map("expense_id") @db.Uuid
    userId      String   @map("user_id") @db.Uuid
    shareAmount Int      @map("share_amount") // Immutable allocation obligation (> 0)
    createdAt   DateTime @default(now()) @map("created_at") @db.Timestamptz

    expense     Expense  @relation(fields: [expenseId], references: [id], onDelete: Cascade)
    user        User     @relation(fields: [userId], references: [id], onDelete: Restrict)

    @@unique([expenseId, userId])
    @@index([userId])
    @@map("expense_splits")
  }
  ```

---

### 2.2. Net Balance Formula with Explicit Settlement Signs

- **Before:** V1 defined `netBalance(u) = paidAmount(u) - owedAmount(u) + netSettlements(u)` without defining the exact sign conventions for outgoing vs. incoming settlements.
- **Risk:** Implementation ambiguities where developers might add incoming settlements or subtract outgoing settlements, inverting member debtor/creditor balances.
- **Correction:** Formalize explicit signed components:
  1. **Base Net Position (Trước quyết toán):**
     $$\text{baseNet}(u) = \text{paidAmount}(u) - \text{owedAmount}(u)$$
  2. **Outgoing Settlements (Tiền đã hoàn trả cho chủ nợ):**
     $$\text{outgoingSettlement}(u) = \sum \{ s.\text{amount} \mid s.\text{debtorId} = u \}$$
  3. **Incoming Settlements (Tiền đã nhận lại từ con nợ):**
     $$\text{incomingSettlement}(u) = \sum \{ s.\text{amount} \mid s.\text{creditorId} = u \}$$
  4. **Net Outstanding Balance (Vị thế công nợ còn lại):**
     $$\text{netOutstanding}(u) = \text{baseNet}(u) + \text{outgoingSettlement}(u) - \text{incomingSettlement}(u)$$
- **Mathematical Invariant Check (Canonical Demo Dataset):**
  - **Lê Hoàng Nam (Creditor):**
    - $\text{baseNet} = 900\text{k} - 400\text{k} = +500.000\text{ đ}$
    - Before settlement: $\text{netOutstanding} = +500.000\text{ đ}$ (Được nhận lại)
    - After Khánh pays $100\text{k}$ & Mai pays $400\text{k}$: $\text{incoming} = 500\text{k} \implies \text{netOutstanding} = +500\text{k} + 0 - 500\text{k} = \mathbf{0\text{ đ}}$.
  - **Trần Khánh (Debtor):**
    - $\text{baseNet} = 300\text{k} - 400\text{k} = -100.000\text{ đ}$
    - Before settlement: $\text{netOutstanding} = -100.000\text{ đ}$ (Cần trả)
    - After paying Nam $100\text{k}$: $\text{outgoing} = 100\text{k} \implies \text{netOutstanding} = -100\text{k} + 100\text{k} - 0 = \mathbf{0\text{ đ}}$.
  - **Nguyễn Thị Mai (Debtor):**
    - $\text{baseNet} = 0 - 400\text{k} = -400.000\text{ đ}$
    - Before settlement: $\text{netOutstanding} = -400.000\text{ đ}$ (Cần trả)
    - After paying Nam $400\text{k}$: $\text{outgoing} = 400\text{k} \implies \text{netOutstanding} = -400\text{k} + 400\text{k} - 0 = \mathbf{0\text{ đ}}$.
  - **Zero-Sum Conservation:**
    $$\sum_{u} \text{netOutstanding}(u) = 0\text{ VND} \quad \text{at all times.}$$

---

### 2.3. Balances Screen Semantics Correction (`shared-expense-mobile-balances-r1.png`)

- **Before:** V1 mockup showed copy *"Tổng chi phí cần hoàn tất: 1.200.000 đ"* alongside *"Sổ quỹ cân đối (0 đ)"*.
- **Risk:**
  - $1.200.000\text{ đ}$ is the total actual spending of the trip, NOT the outstanding debt.
  - Claiming "Sổ quỹ cân đối (0 đ)" while Khánh still owes $100\text{k}$ and Mai still owes $400\text{k}$ misled users into thinking all debts were already settled.
- **Evidence:** [`shared-expense-mobile-balances-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-balances-v1.png).
- **Correction:**
  - Regenerated mockup: [`shared-expense-mobile-balances-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-balances-r1.png).
  - Metric 1: *"Tổng chi tiêu đã ghi nhận: 1.200.000 đ"*
  - Metric 2: *"Công nợ còn cần quyết toán: 500.000 đ"* (Sum of outstanding debts: $|-100\text{k}| + |-400\text{k}| = 500\text{k}$).
  - Accounting invariant note: *"Bảo toàn giá trị: Tổng vị thế ròng = 0 đ"*
  - Sub-label: *"2 khoản nợ chưa quyết toán"*.
- **Status:** **PASS** (Pixel-perfect render, $390 \times 844$).

---

### 2.4. Expense Detail Split Semantics Correction (`shared-expense-mobile-detail-r1.png`)

- **Before:** V1 mockup displayed status pills next to individual participant rows:
  - Lê Hoàng Nam: `Đã ứng trước (+600k)`
  - Trần Khánh: `Chưa hoàn tiền`
  - Nguyễn Thị Mai: `Chưa hoàn tiền`
  - Notes box included a feature promotional paragraph: *"Ảnh hóa đơn & quét OCR biên lai sẽ được bổ sung trong bản nâng cấp tương lai"*.
- **Risk:**
  - An individual expense bill does not track who has or hasn't settled offline; settlements clear net balances at the Trip level.
  - Promoting unimplemented OCR inside production cards violates GoMate Runtime Honesty guidelines.
- **Evidence:** [`shared-expense-mobile-detail-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-detail-v1.png).
- **Correction:**
  - Regenerated mockup: [`shared-expense-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-detail-r1.png).
  - Payer card: *"Lê Hoàng Nam (Bạn) / Đã thanh toán: 900.000 đ · Ứng trước ròng: 600.000 đ"*.
  - Split breakdown card: Titled *"Phân chia nghĩa vụ chi phí"*, showing neutral participant rows:
    - Lê Hoàng Nam: $300.000\text{ đ}$ (Phần chia 1/3)
    - Trần Khánh: $300.000\text{ đ}$ (Phần chia 1/3)
    - Nguyễn Thị Mai: $300.000\text{ đ}$ (Phần chia 1/3)
  - Notes box: Contains only user notes (*"Bao gồm nước uống và món tráng miệng theo set ăn gia đình Bếp Cuốn"*), zero fake OCR advertisements.
- **Status:** **PASS** (Pixel-perfect render, $390 \times 844$).

---

### 2.5. User Account Deletion & Lifecycle Honesty

- **Before:** V1 contract claimed that on user account deletion, foreign keys would use `SET NULL` on display fields or retain an immutable snapshot name.
- **Risk:** Contradicted the Prisma schema target, where all User relations use `onDelete: Restrict`. Claiming snapshot support existed was technically dishonest.
- **Correction:**
  - Reconciled with target schema: User foreign keys (`paidByUserId`, `userId`, `debtorId`, `creditorId`) strictly enforce `onDelete: Restrict`.
  - A user with active or historical financial records **cannot be hard-deleted** without violating foreign key constraints.
  - Hard-deletion, anonymization, and decoupled snapshots are officially classified as **`FUTURE ARCHITECTURE / POLICY GAP`**.
  - Member leaving trip: Preserves `ExpenseSplit` records intact; debts are not erased; member card shows `(Đã rời chuyến đi)`.

---

### 2.6. Settlement Authorization Contract

- **Trip Owner (`trip.userId === req.user.id`):** May record any valid settlement between trip members (to assist non-tech users or rectify errors).
- **Involved Debtor (`debtorId === req.user.id`):** May record settlement where they reimbursed their creditor.
- **Involved Creditor (`creditorId === req.user.id`):** May record settlement confirming receipt from a debtor.
- **Third-Party Member:** CANNOT record a settlement between two other members (`403 Forbidden`).
- **GroupMember-only / Matched Buddy / Stranger:** Blocked with `403 Forbidden`.
- **Identity Invariant:** `createdByUserId` is strictly server-injected from the authenticated JWT session.
- **Amount Validation:** `amount > 0` and must not exceed the current outstanding net debt between `debtorId` and `creditorId`.

---

### 2.7. Desktop V1 Verification

- **Audit:** Desktop master workstation [`shared-expense-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-desktop-v1.png) was thoroughly re-audited.
- **Findings:**
  - In Column 2, expense items already display neutral split allocations: *"Phân chia: 3 người · Chia đều 300.000 đ / người"*. Zero per-split settlement tags exist on Desktop.
  - In Column 3, settlement cards are trip-level proposals with `[Ghi nhận đã hoàn tiền]`.
  - Top navigation strictly follows canonical GoMate root IA.
- **Conclusion:** Desktop V1 requires **zero visual modification** and remains 100% compliant with R1 architecture.

---

## 3. R1 Mockup Audit & Evidence Table

| Mockup Artifact | Resolution | Core Verification Points | Status |
| :--- | :---: | :--- | :---: |
| [`shared-expense-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-detail-r1.png) | $390 \times 844$ | 1. Hero: $900.000\text{ đ}$, Ăn tối Bếp Cuốn Đà Nẵng.<br>2. Payer card: Nam (Đã thanh toán 900k · Ứng trước ròng 600k).<br>3. Split breakdown: Neutral rows (Nam 300k, Khánh 300k, Mai 300k), no per-split settlement status pills.<br>4. Notes: Clean meal note, zero fake OCR advertisement.<br>5. Buttons: Edit & Delete. | **PASS** |
| [`shared-expense-mobile-balances-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-balances-r1.png) | $390 \times 844$ | 1. Header banner: Tổng chi tiêu đã ghi nhận $1.200.000\text{ đ}$ \| Công nợ còn cần quyết toán $500.000\text{ đ}$.<br>2. Invariant note: Bảo toàn giá trị: Tổng vị thế ròng = 0 đ · 2 khoản nợ chưa quyết toán.<br>3. Balances: Nam (+500k), Khánh (-100k), Mai (-400k).<br>4. Settlements: Khánh $\rightarrow$ Nam (100k), Mai $\rightarrow$ Nam (400k) with `[Ghi nhận đã hoàn tiền]`.<br>5. Disclaimer & 5-tab root navigation. | **PASS** |

---

## 4. Acceptance Sign-Off

All requirements of TASK 08.2.3.13-R1 have been strictly fulfilled:
- [x] Duplicate settlement state removed from `model ExpenseSplit`.
- [x] `model Settlement` confirmed as sole source of truth for debt reconciliation.
- [x] Explicit sign balance formula documented and verified.
- [x] Balances screen copy updated: $1.2\text{M}$ spent vs. $500\text{k}$ outstanding debt.
- [x] Expense detail split rows neutral; fake OCR ads purged.
- [x] User account deletion reconciled as `FUTURE ARCHITECTURE / POLICY GAP`.
- [x] Settlement authorization rules locked with server identity invariants.
- [x] Zero changes to `apps/` or production code (`git diff apps/` empty).
- [x] `docs/weekly-reports/W01/weekly-report-W01.docx` untouched and unstaged.
- [x] Design Lock ready.
