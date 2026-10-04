# TASK 08.2.1 — GoMate UX Architecture & Gap Analysis Audit

**Tài liệu:** Báo cáo Kiểm định Kiến trúc UX & Phân tích Khoảng cách Hiện trạng (UX Architecture Audit)  
**Mã Task:** TASK 08.2.1  
**Ngày thực hiện:** 2026-10-04  
**Nhánh:** `feature/gomate-ux-architecture`  
**Base Commit:** `develop` (`937cde8`)  
**Mục tiêu:** Đối chiếu mã nguồn Flutter hiện hữu với Kiến trúc UX Tổng thể, xác định nợ kỹ thuật, các màn hình cần bảo toàn vs cần nâng cấp, và thiết lập lộ trình thực thi theo thứ tự ưu tiên.  

---

## 1. Hiện trạng Mã nguồn & Màn hình Flutter (Current State)

### 1.1 Cấu hình Router (`apps/mobile/lib/core/router/app_router.dart`)
- **Kiến trúc GoRouter:** Sử dụng 1 root `GoRouter` với `_rootNavigatorKey` và `_shellNavigatorKey` được điều khiển bởi `RouterNotifier`.
- **Danh sách Route hiện có:**
  - `/login`: `LoginScreen` (Pushed)
  - `/register`: `RegisterScreen` (Pushed)
  - `/trips/create`: `TripFormScreen` (Pushed)
  - `/trips/:id`: `TripDetailScreen` (Pushed)
  - `/places/:id`: `PlaceDetailScreen` (Pushed)
  - `ShellRoute` (5 tabs):
    - `/`: `HomeScreen` (Tab 1 - Khám phá)
    - `/map`: `MapScreen` (Tab 2 - Bản đồ)
    - `/ai`: `AiChatScreen` (Tab 3 - Wandy AI)
    - `/safety`: `_PlaceholderScreen` (Tab 4 - An toàn, đang để placeholder)
    - `/trips`: `TripListScreen` (Tab 5 - Chuyến đi)

### 1.2 Đánh giá Hiện trạng Từng Màn hình

| Màn hình | Tệp tin thực thi | Mức độ hoàn thiện kỹ thuật | Đánh giá UX hiện tại |
| :--- | :--- | :---: | :--- |
| **Home (`/`)** | `features/home/presentation/home_screen.dart` | 75% | Tải được danh sách điểm đến từ backend. Responsive container đã áp dụng. Chưa có phần "Địa điểm gần bạn" kết nối GPS và lưới địa điểm văn hóa nổi bật. |
| **Map (`/map`)** | `features/map/presentation/map_screen.dart` | 95% | Rất hoàn thiện sau TASK 08.1.1 (HOT tiles sạch sẽ, marker phân màu, vị trí người dùng mượt mà, vòng sai số, status pill, preview sheet). Cần bổ sung UI chọn bán kính quét (1km/5km/10km). |
| **Place Detail (`/places/:id`)** | `features/places/presentation/place_detail_screen.dart` | 90% | Rất tốt sau TASK 08 (Hero, rating trung thực, địa chỉ OSM, mini-map, nguồn ODbL, nút Chỉ đường ngoài). Chưa gắn hành động "Thêm vào chuyến đi" (FLOW 09). |
| **Wandy AI (`/ai`)** | `features/ai_chat/presentation/ai_chat_screen.dart` | 85% | Chat mượt, trích dẫn nguồn ODbL (`SourceChip`) chuẩn sau TASK 07.5.1. Màn hình rỗng khởi tạo còn đơn giản; chưa có các chip hành động nhanh phân loại. |
| **Trip List (`/trips`)** | `features/trips/presentation/trip_list_screen.dart` | 75% | Liệt kê chuyến đi, nút tạo chuyến đi. Giao diện thẻ cơ bản, chưa có bộ lọc "Sắp tới" / "Lịch sử". |
| **Trip Detail (`/trips/:id`)** | `features/trips/presentation/trip_detail_screen.dart` | 85% | Quản lý lịch trình, tích hợp nút "Lập lịch trình bằng AI" với `AiPlannerPreviewSheet` rất chuẩn mực (preview-before-save, budget arithmetic). Chưa hỗ trợ thêm địa điểm thủ công mượt mà. |
| **Safety (`/safety`)** | `_PlaceholderScreen` trong `app_router.dart` | 15% | Đang là màn hình giữ chỗ tạm thời (`Tính năng đang phát triển...`). |
| **Auth (`/login`, `/register`)** | `features/auth/presentation/` | 80% | Đăng nhập/đăng ký hoạt động ổn định, JWT lưu cache. Cần tinh chỉnh visual theo GoMate Design System tokens. |

---

## 2. Kiến trúc Mục tiêu (Desired State)

1. **Sản phẩm Du lịch Toàn diện:** 5 tab hoạt động đầy đủ, không còn màn hình placeholder.
2. **Luồng khép kín (End-to-End Synergy):**
   - Từ Bản đồ / Khám phá $\rightarrow$ Xem Place Detail $\rightarrow$ Thêm vào Chuyến đi (`FLOW 09`).
   - Từ Chuyến đi $\rightarrow$ Mở Wandy tư vấn ngữ cảnh $\rightarrow$ Cập nhật lịch trình (`FLOW 10`).
   - Màn hình An toàn (`/safety`) cung cấp danh bạ SOS cứu hộ thực tế tại Việt Nam.
3. **Tuân thủ Tuyệt đối Dữ liệu Trung thực:** Duy trì không bịa đặt dữ liệu (Zero fake ratings, zero fake addresses, clear OSM/Wikivoyage provenance).
4. **Bảo toàn Ngữ cảnh Tối đa:** Không một thao tác chuyển trang nào làm mất vị trí bản đồ hay cuộc trò chuyện Wandy.

---

## 3. Phân tích Khoảng cách (Gap Analysis)

| Khoảng cách (Gap) | Hiện trạng (Current) | Mục tiêu (Desired) | Mức độ ảnh hưởng UX |
| :--- | :--- | :--- | :---: |
| **GAP 01: Màn hình An toàn** | Tab `/safety` là `_PlaceholderScreen` với icon khiên. | Màn hình `SafetyScreen` với phím gọi SOS khẩn cấp (113, 114, 115), hướng dẫn du lịch an toàn bản địa. | **High** (Tính năng đề cương) |
| **GAP 02: Thêm địa điểm vào chuyến đi** | `PlaceDetailScreen` chỉ có nút "Chỉ đường"; chưa có nút "Thêm vào chuyến đi". | Bổ sung nút "Thêm vào chuyến đi", mở sheet chọn chuyến đi và ngày để gán địa điểm (`FLOW 09`). | **High** (Đứt gãy luồng người dùng) |
| **GAP 03: Bộ chọn bán kính trên Bản đồ** | Bản đồ quét bán kính ngầm định theo zoom; chưa có UI chọn 1km/5km/10km rõ ràng. | Thêm nút/chip chọn bán kính quét (1km/5km/10km) minh bạch cho người dùng. | **Medium** (Tùy biến bản đồ) |
| **GAP 04: Thẻ hành động nhanh Wandy** | `AiChatScreen` rỗng chỉ có vài dòng chữ text đơn giản. | Màn hình Wandy Empty State chuyên nghiệp với các chip chủ đề (*Lập lịch trình, Ẩm thực, Khám phá*). | **Medium** (Tương tác AI) |
| **GAP 05: Thêm địa điểm thủ công trong Chuyến đi** | `TripDetailScreen` chủ yếu dựa vào AI Planner; nút thêm thủ công chưa thuận tiện. | Thêm modal tìm kiếm địa điểm đã xác minh để thêm vào ngày cụ thể của lịch trình. | **Medium** (Tùy biến lịch trình) |
| **GAP 06: Trang chủ kết nối GPS** | `HomeScreen` chỉ tải danh sách điểm đến tĩnh. | Tận dụng `userLocationProvider` để hiển thị mục "Địa điểm gần bạn" khi có GPS. | **Low** (Tăng giá trị cá nhân hóa) |

---

## 4. Danh mục Cần Bảo Toàn vs Cần Tái thiết kế

### 4.1 Các Thành phần & Hành vi TUYỆT ĐỐI BẢO TOÀN (Do NOT Regress)
1. **Kiến trúc Router trung tâm:** `RouterNotifier` với persistent navigator keys. **Cấm** tạo thêm GoRouter hay duplicate keys.
2. **Dữ liệu Bản đồ & Gạch nền HOT:** Bản đồ OpenStreetMap Humanitarian (HOT) không watermark, URL tiles sạch sẽ.
3. **Location Quality Gate:** Logic phân loại sai số $\le 50\text{m}$, $50-200\text{m}$, $>200\text{m}$, vòng tròn sai số `CircleLayer` mờ dưới POI, không cản trở tap marker.
4. **Chính sách Camera Bản đồ:** Không di chuyển camera khi chọn POI, không giật camera khi quay về từ Place Detail, lướt êm ái 250ms khi bấm định vị.
5. **Bảo toàn dữ liệu POI khi định vị:** Không gọi `moveCenter` làm mất 357 địa điểm trên bản đồ.
6. **Bộ định dạng Khoảng cách:** `formatDistanceKm` tính toán chuẩn xác từ thiết bị bằng Haversine, loại bỏ số liệu tính từ tâm bản đồ của server.
7. **Trích dẫn Nguồn thực tế:** Mọi phản hồi AI và chi tiết địa điểm đều giữ nguyên thẻ chip `SourceChip` liên kết OpenStreetMap / Wikivoyage.
8. **Invariants của AI Planner:** Nguyên tắc xem trước trước khi ghi (`preview-before-save`), tính toán chi phí tất định (`deterministic budget arithmetic`), ghi đè nguyên tử (`atomic apply`).

### 4.2 Các Thành phần CẦN NÂNG CẤP / PHÁT TRIỂN TIẾP (Screens to Build/Refactor)
1. **Màn hình An toàn (`SafetyScreen`):** Xây dựng mới hoàn chỉnh thay thế placeholder.
2. **Luồng Thêm Địa điểm vào Chuyến đi (`SelectTripBottomSheet`):** Bổ sung tương tác từ `PlaceDetailScreen`.
3. **Màn hình Khởi tạo Wandy (`WandyEmptyState`):** Làm phong phú thêm các gợi ý tương tác và prompt chips.
4. **Bộ chọn Bán kính Bản đồ (`RadiusSelector`):** Bổ sung widget chọn bán kính mượt mà trên bản đồ.

---

## 5. Lộ trình Thực thi theo Thứ tự Ưu tiên (Recommended Implementation Order)

```text
Giai đoạn 1: Hoàn thiện tính năng lõi còn thiếu (Core Feature Completion)
  ├── 1. Xây dựng SafetyScreen (/safety) thay thế placeholder (GAP 01)
  └── 2. Xây dựng SelectTripBottomSheet trên Place Detail (GAP 02)

Giai đoạn 2: Tối ưu hóa Tương tác & Khả năng Khám phá (Discovery Polish)
  ├── 3. Bổ sung Bộ chọn Bán kính quét trên Bản đồ (GAP 03)
  └── 4. Nâng cấp Wandy Empty State với Prompt Chips thông minh (GAP 04)

Giai đoạn 3: Tinh chỉnh Chi tiết Chuyến đi & Cá nhân hóa (Trip Polish)
  ├── 5. Nâng cấp bộ chọn thêm địa điểm thủ công trong Trip Detail (GAP 05)
  └── 6. Tích hợp danh sách "Gần bạn" trên Trang chủ khi có GPS (GAP 06)
```

---

## 6. Kết luận Kiểm định

Kiến trúc hiện tại của GoMate (sau TASK 07.6, TASK 08, TASK 08.1 và TASK 08.1.1) đã có nền móng rất vững chắc về hệ thống Design System tokens, độ ổn định của bản đồ, tính toàn vẹn của dữ liệu và kiến trúc điều hướng.

Bộ tài liệu kiến trúc UX v1.0 vừa thiết lập đã xác định rõ ràng bức tranh tổng thể, các hợp đồng bảo toàn dữ liệu và các luồng tương tác chi tiết. Quá trình phát triển tiếp theo sẽ bám sát lộ trình 3 giai đoạn nêu trên mà không làm gián đoạn hay thoái lui bất kỳ tính năng nào đã được kiểm chứng.
