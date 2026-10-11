# GoMate — Product Information Architecture & Navigation Rules

**Tài liệu:** Kiến trúc Thông tin & Quy tắc Điều hướng (Information Architecture & Navigation Specification)  
**Phiên bản:** 1.0.0  
**Ngày ban hành:** 2026-10-04  
**Phạm vi:** Cấu trúc phân cấp thông tin và hệ thống điều hướng ứng dụng GoMate  

---

## 1. Cấu trúc Phân cấp Thông tin Toàn diện (Product Hierarchy)

```text
GoMate (Ứng dụng Du lịch Thông minh)
├── Khám phá (Tab 1 — Root: '/')
│   ├── Lời chào cá nhân hóa & Ngữ cảnh du lịch (Greeting & Context Card)
│   ├── Thanh tìm kiếm điểm đến & địa điểm (Global Destination Search)
│   ├── Lối tắt tương tác Wandy Copilot (Wandy AI Quick Entry Banner)
│   ├── Danh mục điểm đến gợi ý hàng đầu (Recommended Destinations Carousel)
│   ├── Danh sách địa điểm gần bạn (Nearby Places Section — GPS aware)
│   └── Địa điểm văn hóa / ẩm thực nổi bật (Featured Verified Places Grid)
│
├── Bản đồ (Tab 2 — Root: '/map')
│   ├── Thanh tìm kiếm địa điểm trên bản đồ (Place Search & Autocomplete)
│   ├── Thanh chip lọc danh mục du lịch (Category Filter Bar: Tất cả, Tham quan, Văn hóa, Thiên nhiên, Nhà hàng, Khách sạn)
│   ├── Bản đồ nền vệ tinh / OpenStreetMap Humanitarian (HOT & OSM-FR Basemap)
│   ├── Vòng tròn & Marker định vị người dùng (User Location Dot & Accuracy Circle)
│   ├── Bộ chọn bán kính tìm kiếm (Radius Selector: 1 km / 5 km / 10 km)
│   ├── Lớp Marker địa điểm du lịch theo màu danh mục (Category-Colored POI Markers)
│   ├── Tấm xem nhanh địa điểm (Place Preview Sheet — Trượt từ đáy)
│   └── Lối tắt mở màn hình chi tiết địa điểm (CTA "Xem chi tiết" → /places/:id)
│
├── Wandy AI (Tab 3 — Root: '/ai')
│   ├── Màn hình khởi tạo & Hành động nhanh (Wandy Empty State & Quick Prompt Chips)
│   ├── Khung hội thoại tương tác trực tiếp (Conversation Stream & History)
│   ├── Thẻ chip trích dẫn nguồn dữ liệu thực (Grounded Source Chips: OpenStreetMap, Wikivoyage)
│   ├── Hỗ trợ tìm kiếm & Đề xuất địa điểm dựa trên RAG (RAG-Augmented Place Suggestions)
│   ├── Kích hoạt luồng lập kế hoạch hành trình (Trip Planning Initiation Flow)
│   └── Tư vấn theo ngữ cảnh chuyến đi hiện tại (Trip-Aware Contextual Assistance)
│
├── An toàn (Tab 4 — Root: '/safety')
│   ├── Phím gọi khẩn cấp SOS & Số cứu hộ du lịch (Emergency Call & Hotline SOS)
│   ├── Hướng dẫn an toàn du lịch bản địa (Local Safety Advisory & Guidelines)
│   ├── Báo cáo vị trí an toàn cho người thân (Safety Check-in Simulation)
│   └── Cảnh báo thời tiết & Khuyến cáo di chuyển (Weather & Safety Alerts)
│
└── Chuyến đi (Tab 5 — Root: '/trips')
    ├── Danh sách chuyến đi của bạn (Trip List Screen — Sắp tới, Đã hoàn thành)
    ├── Nút tạo chuyến đi mới (Create Trip Action → /trips/create)
    ├── Màn hình tổng quan chi tiết chuyến đi (Trip Detail Screen → /trips/:id)
    │   ├── Lịch trình chi tiết theo từng ngày (Day-by-Day Itinerary Timeline)
    │   ├── Thẻ địa điểm trong lịch trình kèm giờ dự kiến (Itinerary Item Cards)
    │   ├── Thêm địa điểm thủ công vào ngày (Add Place to Day Modal)
    │   ├── Lập lịch trình tự động bằng AI (AI Trip Planner Button)
    │   ├── Tấm xem trước lịch trình AI & Ngân sách (AI Plan Preview Sheet)
    │   └── Chỉnh sửa, đổi thứ tự & xóa mục lịch trình (Edit / Reorder / Delete Itinerary Items)
    └── Chia sẻ & Mời bạn đồng hành (Trip Sharing & Buddy Invite Hook)
```

---

## 2. Phân loại Loại hình Màn hình (Screen Taxonomy)

Để đảm bảo hiệu năng, quản lý bộ nhớ và trải nghiệm mượt mà, toàn bộ các màn hình và thành phần giao diện trong GoMate được phân định thành 5 nhóm cấu trúc:

### 2.1 Root Screens (Màn hình Gốc thuộc ShellRoute)
- **Đặc điểm:** Nằm trong `ShellRoute`, gắn với Bottom Navigation Bar, luôn tồn tại trong suốt vòng đời ứng dụng.
- **Danh sách:**
  1. `HomeScreen` (`/`)
  2. `MapScreen` (`/map`)
  3. `AiChatScreen` (`/ai`)
  4. `SafetyScreen` (`/safety`)
  5. `TripListScreen` (`/trips`)
- **Cơ chế:** Khi chuyển qua lại giữa các tab, State được bảo toàn thông qua Riverpod providers; không unmount gây mất dữ liệu bản đồ hoặc đoạn hội thoại.

### 2.2 Pushed Detail Screens (Màn hình Chi tiết Đẩy đỉnh)
- **Đặc điểm:** Nằm ngoài `ShellRoute`, che khuất Bottom Navigation Bar khi mở, có AppBar với nút Back chuẩn mực (`← Quay lại`).
- **Danh sách:**
  1. `PlaceDetailScreen` (`/places/:id`)
  2. `TripDetailScreen` (`/trips/:id`)
  3. `TripFormScreen` (`/trips/create`)
  4. `LoginScreen` (`/login`), `RegisterScreen` (`/register`)
- **Cơ chế:** Được mở bằng `context.push()`. Khi pop (`context.pop()`), màn hình gốc bên dưới lộ ra ngay lập tức mà không phải re-initialize.

### 2.3 Modal / Bottom Sheet Screens (Tấm trượt Ngữ cảnh)
- **Đặc điểm:** Trượt lên từ đáy màn hình, giữ lại một phần giao diện phía sau, giải quyết tác vụ tức thì mà không chuyển trang.
- **Danh sách:**
  1. `PlacePreviewSheet`: Hiển thị tóm tắt địa điểm được chọn trên bản đồ (Tên, Ảnh, Khoảng cách, Đánh giá trung thực, nút "Xem chi tiết").
  2. `AiPlannerPreviewSheet`: Hiển thị toàn bộ lịch trình nhiều ngày và bảng tính toán chi phí trước khi người dùng bấm "Áp dụng".
  3. `AddPlaceToDaySheet`: Chọn địa điểm từ danh sách đã lưu để gán vào một ngày cụ thể của chuyến đi.
  4. `RadiusSelectorSheet`: Lựa chọn bán kính quét (1km / 5km / 10km).

### 2.4 Transient Overlays (Lớp phủ Trạng thái Tạm thời)
- **Đặc điểm:** Tự động ẩn hoặc đóng nhanh bằng một thao tác chạm; không cản trở thao tác trên bản đồ hay danh sách.
- **Danh sách:**
  1. `LocationStatusPill`: Viên thuốc hiển thị trạng thái định vị (`Đã xác định vị trí · ±25 m`), tự biến mất sau 5s hoặc chạm để đóng.
  2. `AppSnackBar`: Thông báo lỗi mạng hoặc lời nhắc *"Mở cài đặt"* khi quyền vị trí bị từ chối.
  3. `ConfirmationDialog`: Hộp thoại xác nhận ghi đè lịch trình cũ bằng lịch trình AI hoặc xác nhận xóa chuyến đi.

### 2.5 Reusable Core Components (Thành phần Tái sử dụng Trung tâm)
- **Danh sách:**
  1. `ResponsiveWrapper`: Đóng gói giới hạn chiều rộng tối đa (Max width: 640px Mobile, 720px Tablet, 800px Desktop).
  2. `RatingView`: Hiển thị đánh giá sao trung thực, luôn trả về *"Chưa có đánh giá"* khi rating là null.
  3. `AppBadge`: Huy hiệu "Đã xác minh" (Verified) dựa trên nguồn OpenStreetMap.
  4. `SourceChip`: Thẻ trích dẫn nguồn dữ liệu liên kết đến OpenStreetMap hoặc Wikivoyage.
  5. `AppButton`, `AppCard`, `AppChip`, `AppLoading`, `AppEmptyState`, `AppErrorState`.

---

## 3. Quy tắc Điều hướng Chi tiết (Navigation Rules)

GoMate sử dụng duy nhất một cấu trúc `GoRouter` trung tâm với persistent `_rootNavigatorKey` và `_shellNavigatorKey` được quản lý bởi `RouterNotifier`. **Tuyệt đối không tạo thêm GoRouter hoặc Navigator key phụ.**

### 3.1 Bảng Quy tắc Lựa chọn Phương thức Điều hướng

| Thao tác UX | Phương thức GoRouter | Ngữ cảnh áp dụng | Hành vi ngăn xếp (Stack Behavior) |
| :--- | :--- | :--- | :--- |
| **Chuyển Tab chính** | `context.go('/<tab>')` | Chuyển giữa 5 tab: Trang chủ, Bản đồ, Wandy, An toàn, Chuyến đi. | Thay thế route con trong ShellRoute; giữ nguyên Navigator State. |
| **Mở trang Chi tiết** | `context.push('/places/:id')`<br>`context.push('/trips/:id')` | Từ bản đồ bấm "Xem chi tiết"; từ danh sách chuyến đi bấm mở chuyến đi. | Đẩy lên đỉnh ngăn xếp; giữ nguyên màn hình Map/Trip bên dưới. |
| **Tạo mới thực thể** | `context.push('/trips/create')` | Bấm nút (+) tạo chuyến đi mới. | Đẩy trang form lên đỉnh; sau khi tạo xong pop về chi tiết hoặc danh sách. |
| **Quay lại (Back)** | `context.pop()` | Bấm nút mũi tên quay lại trên AppBar hoặc nút Back vật lý của thiết bị. | Đóng màn hình đỉnh, phục hồi toàn bộ vị trí scroll và trạng thái của màn hình dưới. |
| **Deep-link / Fallback**| `context.go('/')` | Mở ứng dụng từ liên kết ngoài hoặc khi không có lịch sử điều hướng để pop. | Đặt lại ngăn xếp về trang chủ an toàn. |
| **Xem trước / Tác vụ phụ**| `showModalBottomSheet()` | Mở Preview Sheet, AI Planner Preview, Bộ chọn bán kính. | Hiển thị trượt từ đáy; đóng bằng vuốt xuống hoặc bấm nút đóng. |
| **Cảnh báo nguy hiểm** | `showDialog()` | Xác nhận xóa chuyến đi, cảnh báo ghi đè lịch trình. | Hộp thoại modal chặn tương tác nền cho đến khi xác nhận/hủy. |

---

## 4. Hợp đồng Bảo toàn Dữ liệu & Trạng thái (State Preservation Contract)

Một trong những tiêu chí quan trọng nhất của GoMate là **không làm mất ngữ cảnh của người dùng khi di chuyển giữa các màn hình**.

### 4.1 Bảo toàn Trạng thái Bản đồ (Map State Preservation)
- **Tâm bản đồ & Mức Zoom:** Được lưu trữ trong `MapNotifier` (`mapProvider`). Khi người dùng chuyển sang tab khác rồi quay lại tab Bản đồ, hoặc khi mở `PlaceDetailScreen` rồi quay lại:
  - Bản đồ **không** bị reset về tọa độ mặc định.
  - Camera **không** bị giật nhảy.
- **Bộ lọc Thể loại (Category Filter):** Thể loại đang chọn (ví dụ: *Văn hóa*, *Nhà hàng*) được duy trì nguyên vẹn.
- **Tọa độ & Marker Người dùng:** Tọa độ GPS đã xác định (`userLocationProvider`) được lưu trong bộ nhớ; khi quay lại bản đồ, marker vị trí và vòng tròn sai số vẫn hiển thị đúng vị trí.
- **Tấm Preview Địa điểm:** Khi người dùng xem chi tiết rồi bấm quay lại, tấm Preview Sheet của địa điểm đó vẫn mở nguyên trạng (trừ khi người dùng chủ động bấm chip lọc danh mục khác).

### 4.2 Bảo toàn Hội thoại Wandy AI (Conversation Preservation)
- Toàn bộ danh sách tin nhắn, thẻ chip trích dẫn nguồn và trạng thái đang sinh dữ liệu được quản lý trong `aiChatProvider`.
- Người dùng chuyển sang tab Bản đồ để tra cứu địa điểm và quay lại tab Wandy: toàn bộ hội thoại được giữ nguyên vẹn 100%, không bị tải lại từ đầu.

### 4.3 Bảo toàn Chi tiết Chuyến đi & Lịch trình (Trip State Preservation)
- Trạng thái ngày đang chọn (ví dụ: Ngày 1, Ngày 2), bộ lọc chi phí và lịch trình tạm thời trong `tripDetailProvider` được duy trì khi người dùng nhấn xem chi tiết một địa điểm trong lịch trình rồi quay lại.
- Trạng thái AI Plan Preview chỉ bị hủy khi người dùng chủ động bấm nút "Hủy" hoặc vuốt đóng sheet.

### 4.4 Bảo toàn Vị trí Cuộn (Scroll Position Preservation)
- Sử dụng `PageStorageKey` trên các danh sách dài (`HomeScreen`, `TripListScreen`) để khi chuyển tab quay lại, vị trí cuộn của người dùng không bị nhảy lên đầu trang.
