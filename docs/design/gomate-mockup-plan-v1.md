# GoMate — Visual Mockup Plan (v1.0)

**Tài liệu:** Kế hoạch Thiết kế Visual Mockups cho 4 Màn hình Cốt lõi (P0)  
**Phiên bản:** 1.0.0  
**Ngày ban hành:** 2026-10-04  
**Nhánh:** `feature/gomate-ux-review-v2`  
**Trạng thái:** Mockup Specification Baseline (Chỉ định kế hoạch chi tiết trước khi render mockup)  
**Phạm vi:** 4 màn hình cốt lõi P0: **Home**, **Map**, **Place Detail**, **Wandy AI** (Đầy đủ biến thể Mobile + Desktop và các trạng thái dữ liệu)  

---

## 1. Định hướng Thiết kế Thị giác Tổng hợp (Authoritative Design Direction)

GoMate mang phong cách thị giác:
- **Tươi sáng & Thuần Việt:** Gợi mở cảm giác du lịch Việt Nam tự nhiên, trong trẻo, sử dụng tiếng Việt thân thiện, mực thước.
- **Tối giản & Trầm tĩnh:** Hạn chế tối đa các chi tiết trang trí thừa (không neon, không kính mờ, không gradient chói, không shadow đậm).
- **Màu sắc cốt lõi:**
  - Nền chính: `#F8FAFC` (Xám trắng Slate-50).
  - Bề mặt thẻ: `#FFFFFF` (Trắng tinh) và điểm xuyết bề mặt ấm `#FFFCF7`.
  - Màu thương hiệu chính: `#0F766E` (Teal-700) tạo cảm giác an tâm, tin cậy.
  - Màu nhấn mềm: `#CCFBF1` (Teal-100) cho thẻ active hoặc badge.
  - Màu nhấn bản địa: Terracotta `#C96B4B` (Đất nung) và Warm sand `#E8D8C3` (Cát ấm).
- **Phân cấp thị giác:** Typography rõ ràng, dễ đọc, khoảng cách hào phóng ($16\text{dp} - 24\text{dp}$), bo góc thẻ vừa phải ($16\text{dp}$).

---

## 2. Kế hoạch Thiết kế Mockup cho 4 Màn hình Cốt lõi (P0)

---

### MÀN HÌNH 1: HOME SCREEN (TRANG CHỦ KHÁM PHÁ)

#### 1. Kích thước Viewport Mục tiêu
- **Mobile Viewport:** $390 \times 844\text{ px}$ (iPhone 13/14 tiêu chuẩn).
- **Desktop Viewport:** $1440 \times 900\text{ px}$ (Laptop màn hình rộng).

#### 2. Phân vùng Bố cục (Layout Regions)
- **Vùng 1 (Header & Greeting):** Lời chào cá nhân hóa (`"Xin chào bạn 👋"`) + Thương hiệu GoMate + Avatar hồ sơ.
- **Vùng 2 (Search Bar):** Ô tìm kiếm nhanh với placeholder: *"Tìm địa điểm, món ăn, khách sạn..."*.
- **Vùng 3 (Wandy Action Card):** Thẻ trợ lý nổi bật trên nền Teal nhạt (`#CCFBF1`) với thông điệp: *"✦ Lên kế hoạch chuyến đi cùng Wandy"* kèm các chip tác vụ nhanh.
- **Vùng 4 (Destination Carousel):** Băng chuyền cuộn ngang các điểm đến hàng đầu (Hà Nội, Đà Nẵng, Nha Trang, Hội An) với ảnh nền sắc nét và số lượng địa điểm đã xác minh.
- **Vùng 5 (Nearby Places Section):** Danh sách địa điểm gần bạn (khi đã có GPS fix).
- **Vùng 6 (Bottom Dock):** Navigation Bar 5 tab (Khám phá, Bản đồ, Wandy AI, An toàn, Chuyến đi).

#### 3. Thứ bậc Thành phần (Component Hierarchy)
```text
Scaffold
└── SafeArea
    └── ResponsiveWrapper (maxWidth: 720)
        └── CustomScrollView
            ├── SliverToBoxAdapter: GreetingHeader
            ├── SliverToBoxAdapter: AppSearchBar
            ├── SliverToBoxAdapter: WandyActionCard
            ├── SliverToBoxAdapter: SectionHeader("Điểm đến nổi bật")
            ├── SliverToBoxAdapter: DestinationCarousel
            ├── SliverToBoxAdapter: SectionHeader("Địa điểm gần bạn")
            └── SliverList: NearbyPlaceCardList
```

#### 4. Kêu gọi Hành động (CTAs)
- **Primary CTA:** Thẻ Wandy Action Card $\rightarrow$ Chuyển tab sang Wandy AI hoặc mở bộ tạo lịch trình.
- **Secondary CTA:** Ô tìm kiếm địa điểm; các thẻ điểm đến nổi bật.

#### 5. Các Trạng thái Thiết kế Cần Mockup
1. **Default State (Đầy đủ dữ liệu):** Hiển thị lời chào, Wandy card, 4 điểm đến có ảnh và 3 địa điểm gần bạn kèm khoảng cách thực tế.
2. **Loading State:** Skeleton Shimmer trên ô tìm kiếm, thẻ Wandy và khung ảnh điểm đến.
3. **Empty State:** Khi không có kết quả tìm kiếm, hiển thị hình minh họa nhẹ nhàng và nút xóa tìm kiếm.
4. **Error State:** Banner lỗi mạng nhẹ ở đầu trang với nút *"Thử lại"*.
5. **Permission State (Chưa cấp quyền GPS):** Mục "Địa điểm gần bạn" hiển thị thẻ nhắc nhở nhẹ nhàng: *"Bật định vị để xem các địa điểm thú vị quanh bạn"* kèm nút *"Cho phép"*.

#### 6. Hành vi Tương thích (Responsive Behavior)
- **Mobile (<720px):** Toàn màn hình, đệm lề $16\text{dp}$, điểm đến cuộn ngang 1 hàng.
- **Desktop (≥1200px):** Căn giữa trong container $720\text{dp} - 800\text{dp}$, điểm đến chuyển thành lưới 3 cột trực quan.

---

### MÀN HÌNH 2: MAP SCREEN (BẢN ĐỒ TƯƠNG TÁC)

#### 1. Kích thước Viewport Mục tiêu
- **Mobile Viewport:** $390 \times 844\text{ px}$.
- **Desktop Viewport:** $1440 \times 900\text{ px}$.

#### 2. Phân vùng Bố cục (Layout Regions)
- **Vùng 1 (Bản đồ Toàn màn hình - Full-bleed):** OpenStreetMap Humanitarian (HOT) sắc nét, không watermark.
- **Vùng 2 (Top Floating Bar):** Thanh tìm kiếm địa điểm và thanh chip lọc danh mục (*Tất cả, Tham quan, Văn hóa, Thiên nhiên, Nhà hàng, Khách sạn*).
- **Vùng 3 (Map Markers & User Dot):** Các marker POI theo màu danh mục; chấm tròn vị trí người dùng màu xanh lam và vòng tròn sai số mờ.
- **Vùng 4 (Floating Controls):** Huy hiệu đếm số lượng địa điểm (`"357 địa điểm"`) và Nút tròn định vị "Vị trí của tôi" ở góc phải dưới.
- **Vùng 5 (Location Status Pill):** Viên thuốc trạng thái định vị nổi phía trên nút vị trí.
- **Vùng 6 (Bottom Sheet Area):** Tấm `PlacePreviewSheet` trượt từ đáy khi chọn marker.

#### 3. Thứ bậc Thành phần (Component Hierarchy)
```text
Stack
├── FlutterMap (TileLayer, CircleLayer, MarkerLayer)
├── Positioned Top: ResponsiveWrapper(maxWidth: 720) → Search & CategoryChipBar
├── Positioned Bottom-Right: PlaceCountBadge, LocationStatusPill, _LocationButton
└── Align Bottom-Center: PlacePreviewSheet (khi selectedPlace != null)
```

#### 4. Kêu gọi Hành động (CTAs)
- **Primary CTA:** Nút "Vị trí của tôi" (`my_location_button`) $\rightarrow$ Kích hoạt định vị và lướt camera.
- **Secondary CTA:** Nút "Xem chi tiết" trên `PlacePreviewSheet`; các chip lọc danh mục.

#### 5. Các Trạng thái Thiết kế Cần Mockup
1. **Default State (Vị trí chưa xác định):** Bản đồ mở tại trung tâm Hà Nội, nút định vị ở trạng thái nghỉ (`idle` xám), hiển thị các marker POI đầy đủ.
2. **Location Fixed State (Đã xác định vị trí):** Xuất hiện chấm xanh người dùng kèm vòng tròn sai số mờ bán kính $25\text{m}$, nút vị trí chuyển màu xanh lam, status pill hiển thị: `"Đã xác định vị trí · ±25 m"`.
3. **Marker Selected State (Đã chọn địa điểm):** Tấm `PlacePreviewSheet` trượt lên từ đáy, hiển thị tên Chùa Trấn Quốc, khoảng cách `"2.4 km"`, đánh giá *"Chưa có đánh giá"*, huy hiệu *"Đã xác minh"*, nút *"Xem chi tiết"*.
4. **Permission Denied State:** Nút vị trí đổi sang icon `location_disabled` đỏ, status pill hiển thị `"Quyền vị trí bị từ chối"`, xuất hiện SnackBar có nút *"Mở cài đặt"*.
5. **Empty State:** Khi chọn một danh mục không có địa điểm trong bán kính, hiển thị huy hiệu `"0 địa điểm"` mà không làm mất bản đồ.

#### 6. Hành vi Tương thích (Responsive Behavior)
- **Mobile:** Tấm preview trượt chiếm toàn bộ chiều rộng đáy màn hình.
- **Desktop:** Bản đồ mở rộng $100\%$ màn hình; các nút điều khiển và thanh tìm kiếm căn giữa; tấm Preview Sheet thu gọn thành Card nổi kích thước $420\text{px}$ đặt ở góc trái/dưới bản đồ.

---

### MÀN HÌNH 3: PLACE DETAIL SCREEN (CHI TIẾT ĐỊA ĐIỂM XÁC MINH)

#### 1. Kích thước Viewport Mục tiêu
- **Mobile Viewport:** $390 \times 844\text{ px}$.
- **Desktop Viewport:** $1440 \times 900\text{ px}$.

#### 2. Phân vùng Bố cục (Layout Regions)
- **Vùng 1 (Top AppBar):** Nút quay lại (`← Quay lại`), tiêu đề *"Chi tiết địa điểm"*, nút lưu/chia sẻ.
- **Vùng 2 (Hero Section):** Ảnh đại diện địa điểm chất lượng cao, tên tiếng Việt lớn (H1), nhãn thể loại, huy hiệu *"Đã xác minh"*.
- **Vùng 3 (Fact Sheet):** Đánh giá trung thực (`RatingView`), địa chỉ chi tiết từ OSM, giờ mở cửa.
- **Vùng 4 (Mini-Map & Coordinates):** Bản đồ thu nhỏ không watermark hiển thị ghim địa điểm và tọa độ GPS chính xác.
- **Vùng 5 (Data Provenance Section):** Khối thông tin nguồn: *"Nguồn: OpenStreetMap"* kèm liên kết ODbL có thể kiểm chứng.
- **Vùng 6 (Fixed Bottom Bar):** Dòng chữ *"Điều hướng sẽ mở ứng dụng bản đồ"* và 2 nút: Nút Primary *"Chỉ đường"* và nút Secondary *"Thêm vào chuyến đi"*.

#### 3. Thứ bậc Thành phần (Component Hierarchy)
```text
Scaffold
├── AppBar(title: "Chi tiết địa điểm", leading: BackButton)
├── ResponsiveWrapper(maxWidth: 720)
│   └── SingleChildScrollView
│       ├── HeroImage & PlaceTitleBlock
│       ├── RatingView & VerifiedBadge
│       ├── AddressSection
│       ├── OpeningHoursSection
│       ├── ContactSection (ẩn nếu không có số/web)
│       ├── PlaceMiniMap (tọa độ GPS + HOT tiles)
│       └── ProvenanceCitationBlock (OpenStreetMap ODbL)
└── BottomActionBar: NavigationHintText + AppButton("Chỉ đường") + AppButton.outlined("Thêm vào chuyến đi")
```

#### 4. Kêu gọi Hành động (CTAs)
- **Primary CTA:** Nút *"Chỉ đường"* (mở Google Maps ngoài có gắn `origin` nếu có fix vị trí).
- **Secondary CTA:** Nút *"Thêm vào chuyến đi"* (mở modal chọn chuyến đi `FLOW 09`).

#### 5. Các Trạng thái Thiết kế Cần Mockup
1. **Data-Rich State (Đầy đủ dữ liệu):** Địa điểm có đủ địa chỉ phố, giờ mở cửa thực tế, khoảng cách `2.4 km` và nguồn OpenStreetMap.
2. **Missing Facts State (Thiếu dữ liệu - Trung thực):** Địa điểm không có giờ mở cửa hiển thị: *"Chưa có thông tin giờ mở cửa."*; không có địa chỉ hiển thị: *"Chưa có thông tin địa chỉ."*; không có rating hiển thị: *"Chưa có đánh giá"*.
3. **Loading State:** `AppLoading` căn giữa toàn màn hình với spinner Teal.
4. **Error / Not Found State:** `AppEmptyState` với thông báo *"Không tìm thấy thông tin địa điểm"* kèm nút *"Về bản đồ"*.

#### 6. Hành vi Tương thích (Responsive Behavior)
- **Mobile:** Cuộn dọc 1 cột mượt mà, thanh nút bấm cố định ở đáy.
- **Desktop:** Khung nội dung căn giữa với `maxWidth: 720px`, bản đồ mini mở rộng vừa vặn khung thẻ.

---

### MÀN HÌNH 4: WANDY AI COPILOT SCREEN (TRỢ LÝ DU LỊCH AI)

#### 1. Kích thước Viewport Mục tiêu
- **Mobile Viewport:** $390 \times 844\text{ px}$.
- **Desktop Viewport:** $1440 \times 900\text{ px}$.

#### 2. Phân vùng Bố cục (Layout Regions)
- **Vùng 1 (Top AppBar):** Tên trợ lý `"Wandy Copilot"`, biểu tượng lấp lánh (Sparkle) và nút làm mới hội thoại.
- **Vùng 2 (Conversation Area):**
  - Trạng thái rỗng: Lời chào thân thiện của Wandy + 4 thẻ chủ đề gợi ý câu hỏi nhanh.
  - Trạng thái trò chuyện: Danh sách bóng chat câu hỏi (bên phải) và câu trả lời (bên trái).
- **Vùng 3 (Source Citations Area):** Nằm ngay dưới câu trả lời của Wandy với nhãn: *"Nguồn tham khảo:"* và các thẻ chip nguồn (`SourceChip: OpenStreetMap`, `Wikivoyage`).
- **Vùng 4 (Bottom Input Bar):** Ô nhập liệu văn bản bo tròn, nút gửi tin nhắn màu Teal.

#### 3. Thứ bậc Thành phần (Component Hierarchy)
```text
Scaffold
├── AppBar(title: "Wandy Copilot", leading: WandyAvatarIcon)
├── ResponsiveWrapper(maxWidth: 720)
│   └── Column
│       ├── Expanded: ListView (WandyLandingState HOẶC ChatMessageList)
│       │   └── ChatMessageBubble
│       │       ├── MarkdownBody(answerText)
│       │       └── SourceChipsRow (OpenStreetMap, Wikivoyage)
│       └── ChatInputBar (TextField + SendIconButton)
```

#### 4. Kêu gọi Hành động (CTAs)
- **Primary CTA:** Nút gửi tin nhắn (Send icon) sau khi nhập câu hỏi.
- **Secondary CTA:** Các thẻ chip nguồn trích dẫn; các thẻ gợi ý câu hỏi nhanh trên màn hình khởi tạo.

#### 5. Các Trạng thái Thiết kế Cần Mockup
1. **Landing Empty State:** Avatar Wandy to bản, lời chào thuần Việt, 4 thẻ gợi ý: *"Lập lịch trình 3 ngày"*, *"Địa điểm văn hóa Hà Nội"*, *"Quán cà phê yên tĩnh"*, *"Món ngon phố cổ"*.
2. **Conversation Active State:** Cuộc trò chuyện có câu hỏi người dùng và câu trả lời chi tiết của Wandy định dạng Markdown.
3. **Grounded with Sources State:** Câu trả lời của Wandy hiển thị hàng chip nguồn trích dẫn (`OpenStreetMap (way/37933256)`, `Wikivoyage: Hà Nội`) có biểu tượng icon nguồn rõ ràng.
4. **Typing Indicator State:** Hiệu ứng 3 chấm nhảy nhẹ nhàng trong bóng chat của Wandy khi mô hình đang sinh câu trả lời.
5. **Error State:** Bóng chat Wandy thông báo lịch sự khi kết nối gián đoạn kèm nút *"Thử lại"*.

#### 6. Hành vi Tương thích (Responsive Behavior)
- **Mobile:** Khung chat chiếm trọn màn hình, bàn phím ảo đẩy ô nhập liệu lên trên SafeArea.
- **Desktop:** Khung chat căn giữa với `maxWidth: 720px`, có bóng đổ nhẹ xung quanh viền container tạo cảm giác như một khung chat chuyên nghiệp.

---

## 3. Lộ trình Thực hiện Mockup Thị giác Tiếp theo

Khi bước vào giai đoạn thiết kế hình ảnh (Visual Mockups):
1. **Bước 1:** Thiết lập bộ Layout Mockup cho **Home Screen** (Mobile + Desktop).
2. **Bước 2:** Thiết lập bộ Layout Mockup cho **Map Screen** (Mobile + Desktop).
3. **Bước 3:** Thiết lập bộ Layout Mockup cho **Place Detail Screen** (Mobile + Desktop).
4. **Bước 4:** Thiết lập bộ Layout Mockup cho **Wandy AI Screen** (Mobile + Desktop).
5. **Kiểm tra Nghiệm thu:** Đảm bảo toàn bộ 4 mockup tuân thủ 100% tokens từ `app_colors.dart`, `app_typography.dart`, `app_spacing.dart`, `app_radius.dart` và 14 quy tắc chống thoái lui.
