# GoMate Shared Expense — Capability & Architectural Audit (TASK 08.2.3.13)

**Status:** APPROVED ARCHITECTURAL AUDIT & CONTRACT LOCK  
**Task:** TASK 08.2.3.13 — GOMATE SHARED EXPENSE: TRIP EXPENSE LEDGER, SPLIT & SETTLEMENT CONTRACT V1  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:**
- Database Schema: [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) (`model Trip`, `model TripMember`, `model Itinerary`, `model ItineraryItem`, `model Group`, `model GroupMember`, `model Place`, `model User`)
- Backend Code: [`apps/backend/src/modules/trips/trips.controller.ts`](file:///d:/Do_an/wanderai/apps/backend/src/modules/trips/trips.controller.ts), [`apps/backend/src/modules/trips/trips.service.ts`](file:///d:/Do_an/wanderai/apps/backend/src/modules/trips/trips.service.ts)
- Mobile Code: [`apps/mobile/lib/features/trips/`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/trips/)
- Core Contract: [`docs/design/gomate-shared-expense-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-shared-expense-contract-v1.md)
- Master Visual Evidence Artifacts:
  - Mobile Master Overview V1: [`shared-expense-mobile-overview-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-overview-v1.png) ($390 \times 844$)
  - Mobile Master Add V1: [`shared-expense-mobile-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-add-v1.png) ($390 \times 844$)
  - Mobile Master Detail R1: [`shared-expense-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-detail-r1.png) ($390 \times 844$) *(Replaces V1: neutral split shares, removes fake OCR ad)*
  - Mobile Master Balances R1: [`shared-expense-mobile-balances-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-balances-r1.png) ($390 \times 844$) *(Replaces V1: honest 1.2M spent vs 500k debt copy, zero-sum conservation)*
  - Mobile Master Empty V1: [`shared-expense-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-empty-v1.png) ($390 \times 844$)
  - Desktop Master Workstation V1: [`shared-expense-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-desktop-v1.png) ($1440 \times 900$)

---

## 1. Executive Summary & Audit Verdict

TASK 08.2.3.13 executes an exhaustive capability and architectural audit of the Shared Expense experience for GoMate.

### Key Audit Findings:
1. **Repository Capability Reality (Total Schema Gap):**
   - Neither `model Expense`, `model ExpenseSplit`, nor `model Settlement` exists in [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma).
   - Zero REST endpoints for expense logging, editing, splitting, or settlement exist in [`trips.controller.ts`](file:///d:/Do_an/wanderai/apps/backend/src/modules/trips/trips.controller.ts).
   - Zero expense state management or UI exists in [`apps/mobile/lib/features/trips/`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/trips/).
   - **Verdict:** Shared Expense is an unbuilt, greenfield module. All specifications locked here represent the **Design Target and Business Contract V1**.
2. **Critical Distinction: Itinerary Estimate vs. Actual Ledger:**
   - [`ItineraryItem.estimatedCost`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L453-L470) represents **planning information only**.
   - Shared Expense represents **actual historical financial transactions**.
   - Automatic conversion is strictly forbidden.
3. **Canonical Ownership (Trip-Owned):**
   - The expense ledger belongs strictly to [`model Trip`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma#L399-L425).
   - Companion Groups are merely contextual entry points. Deleting or leaving a Group does not alter the Trip expense ledger or erase member debts.
4. **Settlement is NOT Payment Processing:**
   - GoMate does not process bank transactions, charge cards, or interface with e-wallets (MoMo/ZaloPay/VNPay).
   - *"Ghi nhận đã hoàn tiền"* is purely an internal manual ledger reconciliation record.
5. **Mathematical Consistency Lock:**
   - All 6 master mockups are mathematically synchronized to the canonical demo dataset:
     $$\text{Actual Spent: } 1.200.000\text{ đ} \quad (\text{Expense 1: } 900\text{k} + \text{Expense 2: } 300\text{k})$$
     $$\text{Nam: } +500.000\text{ đ} \quad \mid \quad \text{Khánh: } -100.000\text{ đ} \quad \mid \quad \text{Mai: } -400.000\text{ đ}$$
     $$\sum \text{netOutstanding} = +500.000 + (-100.000) + (-400.000) = \mathbf{0\text{ đ}}$$
6. **R1 Ledger & Settlement Architectural Correction:**
   - **Settlement Duplicate State Eliminated:** `ExpenseSplit` represents immutable allocation obligations only. Zero settlement columns exist in `ExpenseSplit`.
   - **Settlement as Sole Source of Truth:** `model Settlement` is the only canonical entity recording debt clearance.
   - **Explicit Sign Formula:** $\text{netOutstanding}(u) = \text{baseNet}(u) + \text{outgoingSettlement}(u) - \text{incomingSettlement}(u)$.
   - **Semantic Copy Reconciliation:** Total actual spending ($1.200.000\text{ đ}$) is strictly separated from outstanding debt to settle ($500.000\text{ đ}$).
   - **Lifecycle Honesty:** Hard user deletion is classified as a `FUTURE ARCHITECTURE / POLICY GAP` due to relational `onDelete: Restrict`.
   - **Visual R1 Mockups:** Verified clean renders for `shared-expense-mobile-detail-r1.png` and `shared-expense-mobile-balances-r1.png`.

---

## 2. Technical Evidence & Inspection Logs

### 2.1. Prisma Schema Audit (`apps/backend/prisma/schema.prisma`)

Grep command `Select-String -Path apps/backend/prisma/schema.prisma -Pattern "expense|settle|split|ledger|debt|paidBy"` produced **0 matches**.

Existing models inspected:
- `Trip` (id, userId, title, totalBudget, currency, status, etc.)
- `TripMember` (id, tripId, userId, role)
- `Itinerary` (id, tripId, dayNumber, date, title)
- `ItineraryItem` (id, itineraryId, orderIndex, activity, estimatedCost)
- `Group` (id, tripId, name)
- `GroupMember` (id, groupId, userId, role)

**Finding:** The database contains zero financial ledger models. Storing actual expenses requires a future migration.

### 2.2. Backend Trips Module Audit (`apps/backend/src/modules/trips/`)

Inspection of `trips.controller.ts` endpoints:
- `POST /trips`: createTrip
- `GET /trips`: findAll
- `GET /trips/:id`: findById
- `PUT /trips/:id`: updateTrip
- `DELETE /trips/:id`: deleteTrip
- `POST /trips/:id/itinerary`: addItineraryItem
- `DELETE /trips/:id/itinerary/:itemId`: deleteItineraryItem
- `POST /trips/:id/members`: addMember
- `POST /trips/:id/ai-plan`: generateAiPlan
- `POST /trips/:id/itinerary/bulk`: bulkSaveItinerary

**Finding:** There are zero endpoints for expenses, splits, or settlements.

### 2.3. Mobile Codebase Audit (`apps/mobile/lib/features/`)

Directory search across `apps/mobile/lib/` for `expense`, `chi tieu`, `ledger`, `settle` returned **0 matches**.
Existing features: `auth`, `home`, `map`, `places`, `location`, `ai_chat`, `trips`.
Under `features/trips`:
- `trip_models.dart`: Models for `Trip`, `TripMember`, `Itinerary`, `ItineraryItem`. Zero expense models.
- `trip_detail_screen.dart`: Renders trip overview and itinerary timeline. Zero expense widgets.

**Finding:** Mobile client currently has zero Shared Expense UI or state management.

### 2.4. Infrastructure & Third-Party Service Audit

- **File / Receipt Storage:** `package.json` contains no AWS S3 SDK, no Google Cloud Storage, no MinIO, and no Multer. Receipt upload is classified as **FUTURE CAPABILITY**.
- **OCR Engine:** No Tesseract or Google Cloud Vision dependencies exist. Receipt OCR scanning is classified as **FUTURE AI CAPABILITY**.
- **Payment Gateway:** No Stripe, VNPay, MoMo, or ZaloPay SDKs exist. Direct in-app payment is **EXCLUDED BY DESIGN**.
- **Push Notifications:** No FCM (`firebase-admin`) or APNs exists. Automated payment reminders are classified as **FUTURE CAPABILITY**.

---

## 3. Mathematical Demo Data Reconciliation

All visual mockups adhere to a single canonical mathematical dataset:

$$\text{Expense 1: Ăn tối Bếp Cuốn Đà Nẵng} = 900.000\text{ đ} \quad (\text{Lê Hoàng Nam trả}, \text{Chia đều Nam, Khánh, Mai: } 300\text{k/người})$$
$$\text{Expense 2: Taxi ra Bán đảo Sơn Trà} = 300.000\text{ đ} \quad (\text{Trần Khánh trả}, \text{Chia đều Nam, Khánh, Mai: } 100\text{k/người})$$

### Reconciliation Table:

| Member | Role | Total Paid | Total Share Owed | Net Balance | Semantic Status | Minimal Settlement Resolution |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Lê Hoàng Nam** | Chủ chuyến đi | $900.000\text{ đ}$ | $400.000\text{ đ}$ | **$+500.000\text{ đ}$** | **Được nhận lại** | Nhận $100\text{k}$ từ Khánh + $400\text{k}$ từ Mai |
| **Trần Khánh** | Thành viên | $300.000\text{ đ}$ | $400.000\text{ đ}$ | **$-100.000\text{ đ}$** | **Cần trả** | Chuyển $100.000\text{ đ}$ cho Nam |
| **Nguyễn Thị Mai** | Thành viên | $0\text{ đ}$ | $400.000\text{ đ}$ | **$-400.000\text{ đ}$** | **Cần trả** | Chuyển $400.000\text{ đ}$ cho Nam |
| **TỔNG CỘNG** | — | **$1.200.000\text{ đ}$** | **$1.200.000\text{ đ}$** | **$0\text{ đ}$** | **CÂN ĐỐI (100%)** | **Đã tối ưu: 2 giao dịch** |

### Budget Comparison:
- **Tổng ngân sách chuyến đi (`Trip.totalBudget`):** $5.000.000\text{ đ}$
- **Đã chi thực tế:** $1.200.000\text{ đ}$ ($24\%$ ngân sách)
- **Ngân sách còn lại thực tế:** $+3.800.000\text{ đ}$
- **Kế hoạch dự tính:** $2.800.000\text{ đ}$ *(Tham chiếu kế hoạch, tách biệt hoàn toàn sổ quỹ)*

---

## 4. Capability Matrix (21 Dimensions)

| Dimension | Database | Backend | Flutter | AI Service | Design Contract | Status | Evidence |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. Expense Model** | Missing | Missing | Missing | N/A | Section 5 | **SCHEMA GAP** | No `model Expense` in `schema.prisma`. |
| **2. Expense Split Model** | Missing | Missing | Missing | N/A | Section 5 | **SCHEMA GAP** | No `model ExpenseSplit` in `schema.prisma`. Per-split settlement fields removed in R1. |
| **3. Settlement Model** | Missing | Missing | Missing | N/A | Section 5 | **SCHEMA GAP** | No `model Settlement` in `schema.prisma`. Sole canonical truth for debt clearance. |
| **4. View Expense Ledger**| Missing | Missing | Missing | N/A | Section 6 | **DESIGN TARGET** | Access requires `Trip` or `TripMember` authorization. |
| **5. Create Expense** | Missing | Missing | Missing | N/A | Section 7, 17 | **DESIGN TARGET** | Form creates expense and splits atomically. |
| **6. Edit Expense** | Missing | Missing | Missing | N/A | Section 17 | **GAP / TARGET** | Requires recalculation of splits and net balances. |
| **7. Delete Expense** | Missing | Missing | Missing | N/A | Section 17 | **GAP / TARGET** | Destructive action with confirmation modal. |
| **8. Equal Split (Chia đều)**| Missing| Missing | Missing | N/A | Section 9 | **DESIGN LOCKED** | Formula: $\lfloor \text{amount}/N \rfloor$ + deterministic remainder. |
| **9. Custom Split (Tùy chỉnh)**| Missing| Missing | Missing | N/A | Section 10 | **DESIGN LOCKED** | Strict zero-sum validation: $\sum \text{shares} = \text{amount}$. |
| **10. Currency Representation**| Partial | Partial | Partial | N/A | Section 11, 12 | **DESIGN LOCKED** | Integer VND conceptually. Inherits `Trip.currency`. |
| **11. Net Balances** | Missing | Missing | Missing | N/A | Section 13 | **DESIGN LOCKED** | Formula: $\text{baseNet} + \text{outgoing} - \text{incoming}$. Sum $= 0$. |
| **12. Who Owes Whom** | Missing | Missing | Missing | N/A | Section 14 | **DESIGN LOCKED** | Greedy $N-1$ transaction minimization algorithm. |
| **13. Settlement Record**| Missing | Missing | Missing | N/A | Section 15 | **DESIGN LOCKED** | Manual ledger marking only. NOT payment processing. |
| **14. Receipt Upload** | Missing | Missing | Missing | N/A | Section 20 | **FUTURE** | No object storage (S3/MinIO) in repository. |
| **15. Receipt OCR Scan**| Missing | Missing | Missing | Missing | Section 20 | **FUTURE** | No OCR or multimodal vision integration in repo. |
| **16. Payment Integration**| Missing | Missing | Missing | N/A | Section 15 | **OUT OF SCOPE** | No MoMo/VNPay/ZaloPay. Explicitly excluded from V1. |
| **17. Expense Ownership** | Missing | Missing | Missing | N/A | Section 6, 17 | **SCHEMA GAP** | Target requires `createdByUserId` for author-only edit. |
| **18. Member Lifecycle & Deletion** | Partial | Partial | Partial | N/A | Section 18 | **POLICY GAP** | Leaving preserves splits. Target uses `onDelete: Restrict`; user deletion is a future gap. |
| **19. Budget Comparison**| Partial | Partial | Partial | N/A | Section 3, 16 | **DESIGN LOCKED** | Actual spent ($1.2\text{M}$) vs. Budget ($5\text{M}$) vs. Estimate ($2.8\text{M}$). |
| **20. Push Notifications**| Missing | Missing | Missing | N/A | Section 22 | **FUTURE** | No FCM/APNs in repo; no instant notification promises. |
| **21. Wandy AI Summary** | Missing | Missing | Missing | Missing | Section 23 | **FUTURE / BOUNDARY**| Wandy may summarize. Autonomous mutations forbidden. |

---

## 5. Master Mockup Verification (6 Master Artifacts)

All 6 master mockups were generated using headless Edge rendering at full scale and verified in `docs/audit/evidence/ui-08.2.3.13/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`shared-expense-mobile-overview-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-overview-v1.png) | Mobile | $390 \times 844$ | 1. Status bar `9:41 5G 100%` + App bar `Chi tiêu chuyến đi` with subtitle `Khám phá Đà Nẵng 4N3Đ`.<br>2. Segmented tab nav: `Sổ chi tiêu (2)` [Active] and `Tổng kết công nợ (2)`.<br>3. Summary card: Đã chi thực tế `1.200.000 đ`, Ngân sách `5.000.000 đ`, Còn lại `+3.800.000 đ` ($24\%$ fill). Reference note: `Kế hoạch dự tính: 2.800.000 đ`.<br>4. Personal balance card: `Bạn được nhận lại: +500.000 đ`.<br>5. Category filter chips: `Tất cả (2)` [Active], `Ăn uống (1)`, `Di chuyển (1)`, `Lưu trú (0)`, `Vé tham quan (0)`.<br>6. Ledger list: 2 cards with icons, amounts, payer details, and personal share tags.<br>7. CTA: `+ Thêm khoản chi mới` + Canonical 5-tab root navigation. | **PASS** |
| [`shared-expense-mobile-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-add-v1.png) | Mobile | $390 \times 844$ | 1. App bar with `Hủy` (left), title `Thêm khoản chi mới`, and `Lưu` (right).<br>2. Section 1: Title input `Ăn tối Bếp Cuốn Đà Nẵng`, amount `900.000 đ`, category chip `Ăn uống` [Active].<br>3. Section 2: Payer selector showing `Lê Hoàng Nam (Bạn · Chủ chuyến đi)`, participant checkboxes (Nam ✓, Khánh ✓, Mai ✓).<br>4. Section 3: Split mode `Chia đều (3 người)` [Active], split preview box ($300\text{k}$ each) with validation badge: `Tổng phần chia khớp chính xác 900.000 đ`.<br>5. Section 4: Notes and date `15/10/2026`.<br>6. Primary submit CTA: `Lưu khoản chi vào sổ quỹ`. Perfectly contained within $844\text{px}$. | **PASS** |
| [`shared-expense-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-detail-r1.png) | Mobile | $390 \times 844$ | 1. App bar with back button, `Chi tiết khoản chi`, and action overflow.<br>2. Hero card: Category tag `Ăn uống`, title `Ăn tối Bếp Cuốn Đà Nẵng`, big amount `900.000 đ`, date `15/10/2026`.<br>3. Payer card: Avatar + `Lê Hoàng Nam (Bạn)` · `Đã thanh toán: 900.000 đ · Ứng trước ròng: 600.000 đ`.<br>4. Split breakdown card: `Phân chia nghĩa vụ chi phí` (3 người · Chia đều), 3 participant rows with individual shares ($300\text{k}$ each) as neutral allocation obligations without confusing per-split "Chưa hoàn tiền" labels.<br>5. Notes box with clean user note, zero promotional advertisement for unimplemented OCR or camera scanning.<br>6. Action buttons: `Chỉnh sửa khoản chi` (outline teal) and `Xóa` (outline red). | **PASS** |
| [`shared-expense-mobile-balances-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-balances-r1.png) | Mobile | $390 \times 844$ | 1. App bar `Tổng kết công nợ` + Segmented tab `Tổng kết công nợ (2)` [Active].<br>2. Summary banner: `Tổng chi tiêu đã ghi nhận: 1.200.000 đ` \| `Công nợ còn cần quyết toán: 500.000 đ`. Subtitle: `Bảo toàn giá trị: Tổng vị thế ròng = 0 đ` · `2 khoản nợ chưa quyết toán`.<br>3. Member balance cards: Nam (`+500.000 đ` Được nhận lại), Khánh (`-100.000 đ` Cần trả), Mai (`-400.000 đ` Cần trả).<br>4. Settlement proposal cards: Proposal 1 (`Khánh → Nam : 100.000 đ`), Proposal 2 (`Mai → Nam : 400.000 đ`). Cleanly formatted with avatars and arrows.<br>5. Actions: Primary `[Ghi nhận đã hoàn tiền]`.<br>6. Disclaimer footer: `GoMate chỉ ghi nhận đối soát sổ sách nội bộ... không thực hiện giao dịch ngân hàng`.<br>7. Canonical 5-tab root navigation. | **PASS** |
| [`shared-expense-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-empty-v1.png) | Mobile | $390 \times 844$ | 1. App bar `Chi tiêu chuyến đi` + Trip subtitle.<br>2. Budget top banner: `Ngân sách: 5.000.000 đ` · `Đã chi thực tế: 0 đ`.<br>3. Centered empty container: Wallet illustration in soft teal circle.<br>4. Title: `Chưa có khoản chi nào`.<br>5. Copy: `Ghi lại chi phí ăn uống, di chuyển và mua sắm để cả nhóm dễ theo dõi, minh bạch ngân sách và quyết toán sau chuyến đi`.<br>6. Primary CTA: `+ Thêm khoản chi đầu tiên`.<br>7. Feature highlights box explaining equal/custom split and separation from 2.8M itinerary estimate. | **PASS** |
| [`shared-expense-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-desktop-v1.png) | Desktop | $1440 \times 900$ | 1. Top navbar: Logo `GoMate` + badge `Trip Workspace` + Canonical 5 tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi` [Active], `An toàn`) + User badge.<br>2. Breadcrumb: `Chuyến đi › Khám phá Đà Nẵng 4N3Đ › Nhóm đồng hành › Chi tiêu chuyến đi` + Owner badge.<br>3. Col 1 ($330\text{px}$): 3 members with net balance pills (+500k, -100k, -400k), category filter list with count badges, quick-links to Shared Itinerary and Group Chat.<br>4. Col 2 ($740\text{px}$): Header with search & `+ Thêm khoản chi mới`, 2 detailed expense cards with full breakdown, bottom reconciliation bar (`Tổng chi tiêu: 1.200.000 đ · Cân đối 100% khớp`).<br>5. Col 3 ($330\text{px}$): Budget card ($1.2\text{M} / 5\text{M}$, $24\%$, remaining $+3.8\text{M}$), 2 minimal settlement cards with `[Ghi nhận đã hoàn tiền]`, Wandy AI financial assistant card with disclaimer. Zero scrollbars. | **PASS** |

---

## 6. Design Acceptance Gate (TASK 08.2.3.13)

- [x] **Repository Expense capability audited:** Verified complete absence of expense tables and endpoints in repository.
- [x] **DB reality proven:** Grep of `schema.prisma` confirmed zero matches for expense/split/settlement.
- [x] **No fake Expense schema claimed:** Documented current state strictly as SCHEMA GAP; defined target models in contract.
- [x] **Expense != Itinerary estimated cost:** Strictly locked as separate planning vs. actual accounting domains.
- [x] **Trip owns expense ledger:** Canonical FK points strictly to `Trip.id` (not `Group.id`).
- [x] **Group does not own ledger:** Group deletion or leaving does not delete trip expenses or erase debts.
- [x] **Access matrix defined:** Locked to Trip Owner and active TripMembers; GroupMember-only and strangers receive 403 Forbidden.
- [x] **Equal split correct:** Deterministic remainder assignment defined ($\lfloor \text{amount}/N \rfloor$ + $1\text{ đ}$ for first $R$ users).
- [x] **Custom split validation defined:** Strict zero-sum rule ($\sum \text{shares} = \text{amount}$) with user-facing validation banner.
- [x] **Integer money policy defined:** Conceptually integer VND; zero floating-point arithmetic.
- [x] **Currency boundary defined:** Inherits `Trip.currency` (VND); no automatic FX conversion.
- [x] **All demo values reconcile:** $900\text{k} + 300\text{k} = 1.200.000\text{ đ}$; Nam $+500\text{k}$, Khánh $-100\text{k}$, Mai $-400\text{k}$.
- [x] **Net balances sum to zero:** $+500.000 + (-100.000) + (-400.000) = 0\text{ VND}$.
- [x] **Settlement algorithm defined:** Greedy $N-1$ transaction minimization algorithm specified.
- [x] **Settlement != payment processing:** Confirmed manual ledger marking only; zero money transmission.
- [x] **No fake MoMo/VNPay/ZaloPay integration:** Excluded from V1; zero fake payment badges.
- [x] **Receipt infra audited:** Confirmed zero object storage (S3/MinIO) in `package.json`.
- [x] **No fake OCR:** OCR receipt scanning classified as FUTURE AI CAPABILITY.
- [x] **Member leave preserves history:** Historical `ExpenseSplit` records remain auditable and debts are not erased.
- [x] **Ownership gap honestly classified:** Documented that `model ItineraryItem` and future `model Expense` require `createdByUserId`.
- [x] **Privacy boundary locked:** Sensitive bank accounts, emails, phones, and auth tokens strictly concealed.
- [x] **Wandy mutations require confirmation:** Wandy serves as informational copilot; autonomous financial mutations forbidden.
- [x] **Mobile Overview created:** [`shared-expense-mobile-overview-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-overview-v1.png) verified ($390 \times 844$).
- [x] **Mobile Add created:** [`shared-expense-mobile-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-add-v1.png) verified ($390 \times 844$).
- [x] **Mobile Detail R1 created:** [`shared-expense-mobile-detail-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-detail-r1.png) verified ($390 \times 844$, neutral split shares, no fake OCR ad).
- [x] **Mobile Balances R1 created:** [`shared-expense-mobile-balances-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-balances-r1.png) verified ($390 \times 844$, honest 1.2M spent vs 500k debt copy, zero-sum conservation).
- [x] **Mobile Empty created:** [`shared-expense-mobile-empty-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-mobile-empty-v1.png) verified ($390 \times 844$).
- [x] **Desktop Master created:** [`shared-expense-desktop-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.13/shared-expense-desktop-v1.png) verified ($1440 \times 900$).
- [x] **R1 Duplicate settlement state eliminated:** Zero settlement columns in `model ExpenseSplit`; `model Settlement` is sole source of truth.
- [x] **R1 Balance formula locked:** $\text{netOutstanding}(u) = \text{baseNet}(u) + \text{outgoingSettlement}(u) - \text{incomingSettlement}(u)$.
- [x] **R1 Settlement authorization locked:** Trip Owner (all valid), Debtor/Creditor (involved only), third-party TripMembers and GroupMember-only blocked (403).
- [x] **R1 User deletion gap classified:** Reconciled with `onDelete: Restrict` as `FUTURE ARCHITECTURE / POLICY GAP`.
- [x] **Canonical root IA preserved:** Top desktop nav and mobile bottom nav strictly render `Khám phá` | `Bản đồ` | `Wandy AI` | `Chuyến đi` [Active] | `An toàn`.
- [x] **No technical task IDs in product UI:** Zero Jira or developer ticket tags inside user-facing frames.
- [x] **No production source changes:** `git diff apps/` is strictly empty.
- [x] **No Prisma changes:** `apps/backend/prisma/schema.prisma` is unmodified.
- [x] **No API changes:** API contracts intact.
- [x] **No merge:** Working branch `feature/gomate-visual-mockups` preserved.
- [x] **No push:** Local commit only.
