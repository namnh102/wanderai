# TASK 08.2.2 — Design Consistency Audit & Authoritative UX Baseline

**Tài liệu:** Báo cáo Kiểm định Nhất quán Thiết kế & Thiết lập Baseline UX GoMate v2  
**Mã Task:** TASK 08.2.2  
**Ngày thực hiện:** 2026-10-04  
**Nhánh:** `feature/gomate-ux-review-v2`  
**Base:** `develop` (`937cde8`)  
**Mục tiêu:** Rà soát toàn diện 10 tài liệu UX/Design hiện có, đối chiếu v1 vs v2, phát hiện và giải quyết triệt để các xung đột/mâu thuẫn/trùng lặp, thiết lập một Nguồn Chân lý Duy nhất (Single Source of Truth) chuẩn bị cho Visual Mockups và UI Implementation.  

---

## 1. Danh mục Tài liệu Đã Rà soát (Reviewed Documents)

1. `docs/design/gomate-design-system-ux-spec-v1.md` (Đặc tả Design System v1 & đề cương ban đầu)
2. `docs/design/gomate-ux-architecture-v1.md` (Bản thiết kế kiến trúc UX tổng thể v1)
3. `docs/design/gomate-information-architecture.md` (Kiến trúc thông tin & phân cấp màn hình)
4. `docs/design/gomate-user-flows.md` (10 luồng người dùng cốt lõi FLOW 01 – FLOW 10)
5. `docs/design/gomate-screen-specification.md` (Đặc tả 11 màn hình trọng yếu A – K)
6. `docs/design/gomate-interaction-specification.md` (Đặc tả vi tương tác, cử chỉ & chuyển động camera)
7. `docs/design/gomate-responsive-specification.md` (Quy chuẩn tương thích đa màn hình & WCAG AA)
8. `docs/design/gomate-master-ux-plan-v2.md` (Kế hoạch sản phẩm & lộ trình UX v2.0 của nhóm)
9. `docs/design/gomate-screen-spec-v2.md` (Đặc tả phân hệ màn hình v2 UI-01 – UI-12)
10. `docs/design/gomate-implementation-sprint-01.md` (Kế hoạch thực thi Sprint 01)
11. **Mã nguồn thực tế:** `apps/mobile/lib/core/theme/`, `core/widgets/`, `core/router/app_router.dart`, `features/`.

---

## 2. Bảng Phân tích Xung đột & Giải pháp Chuẩn mực (Consistency Audit Matrix)

### A. Terminology Consistency (Nhất quán Thuật ngữ)
- **Xung đột A1 — Nhãn Tab 1:**
  - *Hiện trạng:* `app_router.dart` dùng nhãn `"Trang chủ"`; `gomate-information-architecture.md` và `gomate-master-ux-plan-v2.md` dùng `"Khám phá"`.
  - *Quyết định Chuẩn mực:* Nhãn hiển thị chính thức trên Navigation Bar là **"Khám phá"** (phù hợp với bản chất du lịch, truyền cảm hứng trải nghiệm hơn từ chung chung "Trang chủ"). Route path giữ nguyên là `/`.
  - *Tác động:* Cập nhật nhãn trong `app_router.dart` khi triển khai UI-01 App Shell.
- **Xung đột A2 — Định danh Trợ lý Wandy:**
  - *Hiện trạng:* `app_router.dart` dùng `"Wandy AI"`; `gomate-ux-architecture-v1.md` dùng `"Wandy Copilot"`; `gomate-master-ux-plan-v2.md` dùng `"Wandy"`.
  - *Quyết định Chuẩn mực:* Tên thương hiệu hiển thị trên Tab Bar là **"Wandy AI"** (ngắn gọn, định vị rõ tính năng AI); Trong giao diện hội thoại và danh xưng xưng hô là **"Wandy"** hoặc **"Wandy Copilot"**.
- **Xung đột A3 — Huy hiệu Xác minh:**
  - *Hiện trạng:* Sử dụng đan xen giữa `"Đã xác minh"`, `"Verified"`, `"Chính thức"`.
  - *Quyết định Chuẩn mực:* Đồng nhất duy nhất một cụm từ tiếng Việt: **"Đã xác minh"** đi kèm icon `Icons.verified` màu Teal/Primary.

### B. Screen Naming & Identification (Nhất quán Định danh Màn hình)
- **Xung đột B1 — Danh mục Màn hình 11 màn hình (v1) vs 30 màn hình (v2):**
  - *Hiện trạng:* v1 nhóm thành 11 màn hình trọng yếu (A đến K), trong khi v2 liệt kê 30 màn hình rời rạc (tách nhỏ cả trang xem lại lịch trình, tạo nhắc nhở, cài đặt quyền...).
  - *Quyết định Chuẩn mực:* 
    - **Kiến trúc Route Flutter thực tế:** Giữ vững 5 Root Screens (`/`, `/map`, `/ai`, `/safety`, `/trips`) và các Pushed Detail Screens (`/places/:id`, `/trips/:id`, `/trips/create`, `/login`, `/register`).
    - Các màn hình phụ như Preview Sheet, AI Planner Preview, Bộ chọn chuyến đi được xác định là **Modal Bottom Sheets / Overlays** của các màn hình chính, không tạo thêm route dư thừa làm phân mảnh router.

### C. Route Consistency (Nhất quán Định tuyến)
- **Xung đột C1 — Vị trí màn hình An toàn vs Cá nhân:**
  - *Hiện trạng:* Tài liệu ban đầu (`gomate-design-system-ux-spec-v1.md` §2.1) từng dự kiến Tab 5 là "Cá nhân" chứa An toàn bên trong. Tuy nhiên, `app_router.dart` thực tế và `gomate-master-ux-plan-v2.md` xác lập Tab 4 là `/safety` (An toàn) và Tab 5 là `/trips` (Chuyến đi).
  - *Quyết định Chuẩn mực:* Giữ đúng cấu trúc router thực tế trong `app_router.dart`:
    - Tab 1: `/` (Khám phá)
    - Tab 2: `/map` (Bản đồ)
    - Tab 3: `/ai` (Wandy AI)
    - Tab 4: `/safety` (An toàn)
    - Tab 5: `/trips` (Chuyến đi)
    - Màn hình Hồ sơ cá nhân (Profile) / Cài đặt được bố trí mở từ Avatar góc trên phải của AppBar, không chiếm vị trí trên Bottom Navigation Bar.

### D. Component Naming Consistency (Nhất quán Định danh Thành phần)
- **Xung đột D1 — Tên gọi các Widget cốt lõi:**
  - *Hiện trạng:* Trong code hiện có `AppBadge`, `RatingView`, `ResponsiveWrapper`, `AppCard`, `AppButton`, `AppChip`, `AppLoading`, `AppEmptyState`, `AppErrorState`. Trong v2 xuất hiện thêm danh sách: `VerifiedBadge`, `DistanceView`, `SourceCitation`, `AppSearchBar`...
  - *Quyết định Chuẩn mực:*
    - Giữ nguyên các widget nền tảng (`AppButton`, `AppCard`, `AppChip`, `AppBadge`, `RatingView`, `ResponsiveWrapper`).
    - Các thành phần mới trong v2 được hiện thực hóa bằng cách mở rộng hoặc đóng gói từ widget nền tảng:
      - `VerifiedBadge` $\rightarrow$ `AppBadge.verified()`
      - `SourceCitation` $\rightarrow$ `SourceChip` (đã có trong `ai_chat`)
      - `DistanceView` $\rightarrow$ hàm `formatDistanceKm()` kết hợp `Text` phong cách GoMate.

### E. Design-Token Consistency (Nhất quán Tokens Thiết kế)
- **Xung đột E1 — Màu sắc Thương hiệu Chính (Primary Color):**
  - *Hiện trạng:* Một số ví dụ viết trong văn bản v1 dùng mã `#0D9488` (Teal-600), trong khi code thực tế `app_colors.dart` và kế hoạch v2 dùng `#0F766E` (Teal-700).
  - *Quyết định Chuẩn mực:* **`Color(0xFF0F766E)` (Teal-700)** là Nguồn Chân lý Duy nhất cho `AppColors.primary`. Màu nhấn mềm là `Color(0xFFCCFBF1)` (`primaryContainer`).
- **Xung đột E2 — Bảng màu Nhấn Ấm áp (Warm Accents):**
  - *Hiện trạng:* v2 bổ sung các màu nhấn bản địa: Terracotta `#C96B4B`, Warm sand `#E8D8C3`, Warm surface `#FFFCF7`. Code `app_colors.dart` hiện tại chưa khai báo.
  - *Quyết định Chuẩn mực:* Bổ sung các token này vào `AppColors` trong Sprint 01 Task 1 dưới dạng Accent tokens mà không làm thay đổi các token cơ bản đang chạy.
- **Xung đột E3 — Bán kính Bo góc (Radius) & Khoảng đệm (Spacing):**
  - *Đánh giá:* Cả v1, v2 và mã nguồn `app_radius.dart`, `app_spacing.dart` **hoàn toàn đồng nhất 100%**:
    - Radius: $8, 12, 16, 20, 24, 999\text{ dp}$.
    - Spacing: $4, 8, 12, 16, 20, 24, 32, 40, 48\text{ dp}$.

### F. Responsive-Breakpoint Consistency (Nhất quán Điểm ngắt Màn hình)
- **Xung đột F1 — Định nghĩa Breakpoint & Container Width:**
  - *Đánh giá:* Cả hai tài liệu v1 và v2 đều thống nhất tuyệt đối:
    - Mobile: $< 720\text{ dp}$
    - Tablet: $720\text{ dp} - 1199\text{ dp}$
    - Desktop: $\ge 1200\text{ dp}$
  - *Quy tắc Độ rộng Nội dung:*
    - Trải nghiệm toàn màn hình (Full-bleed): Màn hình Bản đồ (`MapScreen`).
    - Trải nghiệm nội dung đọc (Readable-content): Khung giới hạn `maxWidth: 720px` (trung tâm) cho Trang chủ, Chi tiết địa điểm, Chuyến đi và Khung chat Wandy; Form đăng nhập `maxWidth: 420px`.

### G. Motion & Interaction Consistency (Nhất quán Chuyển động & Vi tương tác)
- **Quy chuẩn Chuẩn mực:**
  - Lướt Camera định vị bản đồ: Giữ nguyên chuẩn **$250\text{ ms}$, `Curves.easeInOutCubic`** bảo toàn mức zoom $\ge 14.0$ (đã nghiệm thu và kiểm thử tự động tại TASK 08.1.1).
  - Hiệu ứng phản hồi chạm (Micro-feedback): $120\text{ ms} - 150\text{ ms}$.
  - Trượt Bottom Sheet: $280\text{ ms} - 300\text{ ms}$.
  - Tự động đóng Status Pill: Đúng **$5.0\text{ giây}$** trên trạng thái thành công.

---

## 3. Thiết lập Thứ bậc Tài liệu Chuẩn mực (Canonical Hierarchy)

Nhằm chấm dứt tình trạng tài liệu chồng chéo và mâu thuẫn nguồn chân lý, dự án thiết lập Thứ bậc Quyền hạn duy nhất như sau:

```text
CẤP ĐỘ 1: ĐỊNH HƯỚNG SẢN PHẨM & LỘ TRÌNH (PRODUCT DIRECTION)
  └── gomate-master-ux-plan-v2.md (Tài liệu định hướng tổng thể & tầm nhìn)

CẤP ĐỘ 2: KIẾN TRÚC THÔNG TIN & ĐIỀU HƯỚNG (INFORMATION ARCHITECTURE)
  └── gomate-information-architecture.md (Thứ bậc màn hình, taxonomy, router contract)

CẤP ĐỘ 3: LUỒNG NGƯỜI DÙNG CHI TIẾT (USER FLOWS)
  └── gomate-user-flows.md (10 luồng người dùng cốt lõi FLOW 01 – FLOW 10)

CẤP ĐỘ 4: CẤU TRÚC & ĐẶC TẢ MÀN HÌNH (SCREEN SPECIFICATION)
  └── gomate-screen-specification.md (Chi tiết 13 thuộc tính của từng màn hình)
      [Tham chiếu bổ sung: gomate-screen-spec-v2.md cho mô tả giao diện mới]

CẤP ĐỘ 5: NGÔN NGỮ HÌNH ẢNH & THIẾT KẾ TOKENS (DESIGN TOKENS)
  └── apps/mobile/lib/core/theme/ (app_colors, app_typography, app_spacing, app_radius)
      [Đặc tả gốc: gomate-design-system-ux-spec-v1.md + bổ sung warm accents từ v2]

CẤP ĐỘ 6: THÀNH PHẦN TÁI SỬ DỤNG (COMPONENT SPECIFICATION)
  └── apps/mobile/lib/core/widgets/ (Standard component library)

CẤP ĐỘ 7: VI TƯƠNG TÁC & CHUYỂN ĐỘNG (INTERACTION & MOTION)
  └── gomate-interaction-specification.md (Chính sách camera, status pill, gestures)

CẤP ĐỘ 8: TƯƠNG THÍCH ĐA MÀN HÌNH & TIẾP CẬN (RESPONSIVE & ACCESSIBILITY)
  └── gomate-responsive-specification.md (Breakpoints, max-width, chuẩn WCAG 2.1 AA)

CẤP ĐỘ 9: KẾ HOẠCH TRIỂN KHAI THEO SPRINT (IMPLEMENTATION SPRINT)
  └── gomate-implementation-sprint-01.md (Phân rã task kỹ thuật thực thi)
```

---

## 4. Xác nhận Phân loại Ưu tiên Sản phẩm (Product Priority Matrix)

| Bậc Ưu tiên | Nhóm Tính năng | Danh sách Màn hình / Tính năng | Lý do & Rationale Kiến trúc |
| :--- | :--- | :--- | :--- |
| **P0 — Trải nghiệm Cốt lõi** | Core User Experience | 1. **Khám phá (Home)**<br>2. **Bản đồ (Map)**<br>3. **Chi tiết Địa điểm (Place Detail)**<br>4. **Wandy AI Copilot** | Đây là 4 trụ cột quyết định giá trị trực tiếp của GoMate: người dùng phải mở được app, tìm thấy địa điểm trên bản đồ, xem thông tin đã xác minh và tương tác với AI có trích dẫn nguồn. |
| **P1 — Quản lý Chuyến đi** | Trip Experience | 5. **Danh sách Chuyến đi (Trip List)**<br>6. **Chi tiết Lịch trình (Trip Detail)**<br>7. **Thêm Địa điểm vào Chuyến đi (Add to Trip)** | Hiện thực hóa giá trị "Lập kế hoạch du lịch": AI Trip Planner đã có lõi thuật toán tất định, cần luồng UI khép kín để lưu và quản lý lịch trình. |
| **P2 — Hỗ trợ & An toàn** | Supporting Experience | 8. **Trung tâm An toàn (Safety)**<br>9. **Đăng nhập (Login)**<br>10. **Đăng ký (Register)** | Đảm bảo tính hoàn chỉnh theo đề cương đồ án: cứu hộ khẩn cấp SOS và xác thực tài khoản an toàn. |
| **P3 — Trí tuệ Nâng cao** | Future Intelligence | 11. **Gợi ý Cá nhân hóa (Recommendation)**<br>12. **Kết nối Bạn đồng hành (Buddy Matching)**<br>13. **Agent Điều phối Đa bước** | Các tính năng nghiên cứu chuyên sâu, phụ thuộc vào tập dữ liệu ngoài và chỉ triển khai sau khi lớp UI/UX cơ sở đã vững chắc 100%. |

---

## 5. Định hướng Ngôn ngữ Thị giác Hợp nhất (Consolidated Visual Direction)

- **Cảm giác Chủ đạo (Brand Mood):** Thuần Việt, sáng sủa, điềm tĩnh, đáng tin cậy, ấm áp và hiện đại. Mang hơi thở du lịch khám phá mà không gây rối rắm thị giác.
- **Bảng màu:**
  - Nền chính: Xám trắng dịu (`#F8FAFC`), bề mặt thẻ trắng tinh (`#FFFFFF`), bề mặt ấm áp nhẹ (`#FFFCF7`).
  - Màu thương hiệu chính: Xanh mòng két (`#0F766E` Teal-700), màu thương hiệu mềm (`#CCFBF1`).
  - Màu nhấn bản địa: Đất nung Terracotta (`#C96B4B`) và Cát ấm (`#E8D8C3`).
  - Màu ngữ nghĩa danh mục: Văn hóa (Tím Indigo), Ẩm thực (Cam), Thiên nhiên (Xanh lá), Khách sạn (Teal).
- **Tránh tuyệt đối (Anti-Patterns):**
  - Không dùng nền tối viễn tưởng (Dark neon AI mode).
  - Không lạm dụng hiệu ứng kính mờ (Excessive Glassmorphism) gây giảm hiệu năng render.
  - Không dùng gradient lòe loẹt hoặc bóng đổ đen dày (Harsh black shadows).
  - Không xếp lồng thẻ quá nhiều lớp (Nested-card overload).

---

## 6. Đánh giá 12 Nguyên tắc Thiết kế UX (UX Principles Review)

| # | Nguyên tắc Thiết kế | Trạng thái | Ghi chú & Tinh chỉnh Định hướng |
| :---: | :--- | :---: | :--- |
| 1 | **One primary action per context** | **KEEP** | Mỗi vùng màn hình chỉ có duy nhất một nút Primary nổi bật; nút phụ dùng Outlined/Ghost. |
| 2 | **Progressive disclosure** | **KEEP** | Hiển thị thông tin then chốt trước, chi tiết mở rộng khi người dùng tương tác. |
| 3 | **Vietnamese-first UX** | **REFINE** | Tinh chỉnh toàn bộ bản sao (copywriting) tự nhiên, thuần Việt, chuẩn dấu và thân thiện. |
| 4 | **Truthful data presentation** | **KEEP** | Rating null $\rightarrow$ "Chưa có đánh giá"; Địa chỉ thiếu $\rightarrow$ "Chưa có thông tin địa chỉ". Cấm bịa đặt. |
| 5 | **Clear data provenance** | **KEEP** | Luôn hiển thị nguồn dữ liệu OpenStreetMap kèm liên kết kiểm chứng ODbL. |
| 6 | **Predictable navigation** | **KEEP** | Giữ vững GoRouter duy nhất, bảo toàn vị trí bản đồ và lịch sử chat khi chuyển trang. |
| 7 | **Location transparency** | **KEEP** | Công khai sai số mét (`±X m`), vòng tròn sai số mờ dưới POI, phân loại rõ GPS vs mạng. |
| 8 | **Grounded AI with Source Disclosure**| **REFINE** | Thẻ chip nguồn có thể bấm mở; AI thừa nhận khi không có dữ liệu thay vì sinh ảo giác. |
| 9 | **Actionable error recovery** | **KEEP** | Lỗi vị trí luôn có nút CTA "Mở cài đặt"; lỗi mạng luôn có nút "Thử lại". |
| 10 | **Minimal interruption** | **REFINE** | Hạn chế Dialog chặn; ưu tiên Bottom Sheet và Status Pill tự tắt sau 5s. |
| 11 | **Comfortable touch targets** | **KEEP** | Kích thước tương tác tối thiểu $44 \times 44\text{ dp}$ (chuẩn WCAG AA). |
| 12 | **Low cognitive load** | **NEW** | Giới hạn số lượng lựa chọn cùng lúc; phân nhóm thông tin bằng khoảng đệm tự nhiên thay vì viền dày. |

---

## 7. Bảng Kiểm kê Thành phần Chuẩn hóa (Authoritative Component Inventory)

| Phân nhóm | Tên Thành phần | Trạng thái Hiện tại | Định hướng Xử lý |
| :--- | :--- | :--- | :--- |
| **Foundation** | `AppColors`, `AppTypography`, `AppSpacing`, `AppRadius` | Đã có trong `core/theme/` | **Reusable as-is** (bổ sung thêm 3 token màu nhấn ấm v2). |
| **Navigation** | `NavigationBar` (Bottom Nav) | Đã có trong `app_router.dart` | **Needs visual refactor** (cập nhật nhãn "Khám phá", bo góc thanh dock). |
| **Navigation** | `_MainScaffold` | Đã có | **Reusable as-is** (chuẩn bị thêm `NavigationRail` cho tablet). |
| **Input** | `AppSearchBar` (Thanh tìm kiếm) | Viết nội bộ trong Map/Home | **Needs redesign** (hợp nhất thành widget chuẩn dùng chung). |
| **Input** | `AppChip` (Chip lọc danh mục) | Đã có trong `core/widgets/` | **Reusable as-is**. |
| **Input** | `RadiusSelector` (Bộ chọn bán kính) | Chưa có UI chuyên biệt | **Missing** (cần xây dựng cho Map). |
| **Content** | `AppCard` (Thẻ nội dung) | Đã có trong `core/widgets/` | **Reusable as-is**. |
| **Content** | `AppBadge` (Huy hiệu xác minh) | Đã có trong `core/widgets/` | **Reusable as-is**. |
| **Content** | `RatingView` (Đánh giá trung thực) | Đã có trong `core/widgets/` | **Reusable as-is** (rất ổn định, trung thực tuyệt đối). |
| **Content** | `PlacePreviewSheet` | Đã có trong `map/` | **Reusable as-is** (đáp ứng đầy đủ tiêu chí không stale). |
| **Feedback** | `AppLoading`, `AppEmptyState`, `AppErrorState` | Đã có trong `core/widgets/` | **Reusable as-is**. |
| **Feedback** | `LocationStatusPill` | Đã có trong `map/` | **Reusable as-is** (tự tắt sau 5s, chạm đóng). |
| **Location** | `user_location_marker` & `CircleLayer` | Đã có trong `map/` | **Reusable as-is** (không chặn POI, chuẩn Haversine). |
| **Location** | `_LocationButton` (Đa trạng thái) | Đã có trong `map/` | **Reusable as-is** (6 trạng thái token). |
| **AI** | `ChatMessageBubble` & `SourceChip` | Đã có trong `ai_chat/` | **Reusable as-is**. |
| **AI** | `AiPlannerPreviewSheet` | Đã có trong `trips/` | **Reusable as-is** (preview-before-save). |
| **AI** | `WandyActionCard` | Chưa có widget chuẩn trên Home| **Missing** (cần xây dựng cho Home Screen). |

---

## 8. Ma trận Màn hình Chính thức (Canonical Screen Matrix)

| Màn hình | Route | Ưu tiên | Trạng thái Hiện tại | Trạng thái Mục tiêu | Primary CTA |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **Home** | `/` | **P0** | Đã kết nối API Destinations | Giao diện chuẩn GoMate v2 (Greeting, Search, Wandy Card, Destinations) | Tìm kiếm / Nhờ Wandy |
| **Map** | `/map` | **P0** | Rất tốt (HOT tiles, GPS fix, Status Pill, Preview) | Giữ nguyên logic; bổ sung UI chọn bán kính | Vị trí của tôi |
| **Place Detail** | `/places/:id` | **P0** | Factual facts, Mini-map, Nguồn ODbL, Chỉ đường | Bổ sung nút "Thêm vào chuyến đi" (`FLOW 09`) | Chỉ đường (Google Maps) |
| **Wandy AI** | `/ai` | **P0** | Chat mượt, trích dẫn nguồn OSM/Wikivoyage | Làm phong phú Wandy Landing với Prompt Chips gợi ý | Gửi tin nhắn / Chọn prompt |
| **Trip List** | `/trips` | **P1** | Danh sách chuyến đi cơ bản | Thẻ chuyến đi sinh động hơn kèm trạng thái | Tạo chuyến đi mới |
| **Trip Detail** | `/trips/:id` | **P1** | Lịch trình theo ngày + AI Planner modal | Bổ sung thêm địa điểm thủ công mượt mà | Lập lịch trình bằng AI |
| **Safety** | `/safety` | **P2** | Đang là Placeholder | Danh bạ SOS cứu hộ du lịch (113, 114, 115) + Mẹo an toàn | Gọi cứu hộ khẩn cấp |
| **Login** | `/login` | **P2** | Hoạt động tốt | Tinh chỉnh form gọn gàng theo chuẩn token v2 | Đăng nhập |
| **Register** | `/register` | **P2** | Hoạt động tốt | Tinh chỉnh form gọn gàng theo chuẩn token v2 | Đăng ký tài khoản |

---

## 9. Hợp đồng Chống thoái lui Tuyệt đối (Non-Regression Contract)

Mọi bản thiết kế và triển khai tiếp theo **phải bảo toàn 14 ràng buộc bất biến** sau:

1. **RouterNotifier + Persistent GoRouter:** Giữ vững 1 instance GoRouter duy nhất, không tạo Navigator key phụ.
2. **Triệt tiêu lỗi GlobalKey:** Bảo toàn cấu trúc shell/root navigator keys đã giải quyết dứt điểm lỗi trùng key.
3. **Bản đồ HOT / OSM-FR:** Duy trì gạch nền OpenStreetMap Humanitarian không watermark, tải mượt tại Việt Nam.
4. **Minh bạch Nguồn dữ liệu:** Nguồn OpenStreetMap và giấy phép ODbL luôn hiển thị rõ ràng trên chi tiết địa điểm.
5. **Trung thực về Đánh giá:** Tuyệt đối không hiển thị sao giả khi dữ liệu chưa có (luôn là *"Chưa có đánh giá"*).
6. **Trung thực về Địa chỉ:** Địa chỉ thiếu luôn là *"Chưa có thông tin địa chỉ."*, không tự ghép chuỗi bừa bãi.
7. **Khoảng cách Tính tại Thiết bị:** Tính bằng công thức Haversine trực tiếp từ vị trí người dùng; bỏ qua khoảng cách từ tâm server.
8. **Định vị & Vòng tròn Sai số:** Vòng tròn mờ bán kính `accuracyMeters` nằm dưới POI và bọc `IgnorePointer` để không chặn tap.
9. **Camera Ổn định:** Không tự động recenter khi mở bản đồ hoặc khi chạm marker; chỉ lướt êm 250ms khi bấm định vị.
10. **Bảo toàn Dữ liệu POI:** Bấm định vị không bao giờ re-query tâm bản đồ làm mất 357 địa điểm đã tải.
11. **Trích dẫn Nguồn RAG Wandy:** Phản hồi của Wandy luôn đính kèm thẻ chip nguồn có thể bấm kiểm chứng.
12. **AI Planner Preview-Before-Save:** Toàn bộ lịch trình và ngân sách phải hiển thị xem trước; không ghi DB khi đang preview.
13. **Ghi đè Lịch trình Nguyên tử (Atomic Apply):** Lưu lịch trình bằng transaction duy nhất qua `/itinerary/bulk`.
14. **Bảo toàn API Contracts:** Không thay đổi bất kỳ payload hay interface nào của backend hiện tại.
