# GoMate — Master Screen Hierarchy & Specification

**Tài liệu:** Đặc tả Chi tiết Các Màn hình Trọng yếu (Screen Specification)  
**Phiên bản:** 1.0.0  
**Ngày ban hành:** 2026-10-04  
**Phạm vi:** 11 màn hình trung tâm (Màn hình A đến K) với đầy đủ 13 tiêu chí kiến trúc  

---

## Danh mục 11 Màn hình Trọng yếu

| Mã | Tên Màn hình | Loại hình Màn hình | Route / Vị trí |
| :--- | :--- | :--- | :--- |
| **A** | Home Screen (Trang chủ Khám phá) | Root Screen | `/` |
| **B** | Map Screen (Bản đồ Tương tác) | Root Screen | `/map` |
| **C** | Place Preview Sheet (Tấm xem nhanh địa điểm) | Modal Bottom Sheet | Overlay trên `/map` |
| **D** | Place Detail Screen (Chi tiết địa điểm xác minh) | Pushed Detail Screen | `/places/:id` |
| **E** | Wandy Empty State (Khởi tạo Trợ lý AI) | Root Screen State | `/ai` (chưa có tin nhắn) |
| **F** | Wandy Conversation (Hội thoại AI & Trích dẫn Nguồn) | Root Screen State | `/ai` (đã có tin nhắn) |
| **G** | Trip List Screen (Danh sách chuyến đi) | Root Screen | `/trips` |
| **H** | Trip Detail Screen (Chi tiết hành trình chuyến đi) | Pushed Detail Screen | `/trips/:id` |
| **I** | AI Planner Preview Sheet (Xem trước lịch trình AI) | Modal Bottom Sheet | Overlay trên `/trips/:id` |
| **J** | Safety Screen (Trung tâm An toàn Du lịch) | Root Screen | `/safety` |
| **K** | Auth Screens (Đăng nhập / Đăng ký) | Pushed Screen | `/login`, `/register` |

---

## Đặc tả Chi tiết Từng Màn hình (13 Tiêu chí Chuẩn)

### Màn hình A: Home Screen (Trang chủ Khám phá)
1. **Mục đích (Purpose):** Cổng chào đón người dùng, cung cấp góc nhìn tổng quan về các điểm đến nổi tiếng, địa điểm du lịch gần bạn và lối tắt đến trợ lý Wandy.
2. **Mục tiêu người dùng chính (Primary User Goal):** Tìm kiếm cảm hứng du lịch, khám phá điểm đến mới hoặc tiếp tục chuyến đi đang lên kế hoạch.
3. **Primary CTA:** Thẻ banner nổi bật: *"Lên kế hoạch chuyến đi cùng Wandy"* (chuyển sang tab AI hoặc tạo chuyến đi).
4. **Secondary CTA:** Ô tìm kiếm địa điểm toàn cục; các thẻ điểm đến phổ biến (*Hà Nội*, *Đà Nẵng*, *Nha Trang*).
5. **Cấu trúc phân cấp thông tin (Information Hierarchy):**
   - Đỉnh: Lời chào cá nhân hóa (`"Xin chào bạn 👋"`) + Tên thương hiệu GoMate.
   - Thanh tìm kiếm địa điểm / điểm đến nhanh.
   - Thẻ ngữ cảnh Wandy AI Copilot nổi bật.
   - Băng chuyền điểm đến hàng đầu (Destination Carousel).
   - Danh sách địa điểm gần bạn (dựa trên GPS khi được cấp quyền).
   - Lưới địa điểm văn hóa / ẩm thực đặc sắc đã xác minh nguồn.
6. **Thành phần giao diện (Components):** `ResponsiveWrapper` (max 640px/720px/800px), `AppCard`, `AppButton`, `AppBadge`, `RatingView`.
7. **Điều hướng (Navigation):** Nằm trong `ShellRoute` (Tab 1). Chạm điểm đến $\rightarrow$ Lọc bản đồ; Chạm địa điểm $\rightarrow$ `context.push('/places/:id')`.
8. **Trạng thái Tải (Loading State):** `Shimmer` hiệu ứng ánh sáng trên các khung thẻ ảnh và văn bản.
9. **Trạng thái Rỗng (Empty State):** Khi không tải được điểm đến, hiển thị `AppEmptyState` thân thiện với nút tải lại.
10. **Trạng thái Lỗi (Error State):** `AppErrorState` kèm thông báo *"Không thể tải dữ liệu khám phá. Vui lòng kiểm tra kết nối mạng."*
11. **Trạng thái Quyền hạn (Permission State):** Mục "Gần bạn" hiển thị nhãn nhẹ nhắc bật định vị nếu người dùng chưa cấp quyền.
12. **Hành vi Tương thích (Responsive Behavior):** Co giãn mượt mà theo `ResponsiveWrapper`; trên tablet hiển thị lưới 2 cột, desktop hiển thị 3 cột điểm đến.
13. **Yếu tố Khả năng tiếp cận (Accessibility):** Tương phản chữ đạt chuẩn WCAG AA; ảnh có thẻ alt ngữ nghĩa cho screen reader.

---

### Màn hình B: Map Screen (Bản đồ Tương tác)
1. **Mục đích (Purpose):** Hiển thị không gian địa lý trực quan các địa điểm du lịch thực tế (357+ POI xác minh từ OpenStreetMap), vị trí hiện tại của người dùng và khoảng cách thực tế.
2. **Mục tiêu người dùng chính (Primary User Goal):** Tra cứu các địa điểm xung quanh trên bản đồ, lọc theo sở thích và xác định vị trí bản thân.
3. **Primary CTA:** Nút tròn Floating Action Button "Vị trí của tôi" (`my_location_button`) ở góc phải dưới.
4. **Secondary CTA:** Thanh chip lọc danh mục (*Tất cả*, *Tham quan*, *Văn hóa*, *Thiên nhiên*, *Nhà hàng*, *Khách sạn*); bộ chọn bán kính (1km / 5km / 10km).
5. **Cấu trúc phân cấp thông tin (Information Hierarchy):**
   - Đỉnh màn hình: Thanh tìm kiếm địa điểm có nút xóa từ khóa.
   - Phía dưới thanh tìm kiếm: Thanh chip lọc danh mục nằm ngang (cuộn ngang mượt mà).
   - Lớp bản đồ nền: OpenStreetMap Humanitarian (HOT) sắc nét, 100% không watermark.
   - Lớp vòng tròn sai số người dùng: `CircleLayer` bán kính `accuracyMeters` (màu xanh trong suốt `alpha: 0.12`).
   - Lớp marker người dùng: Điểm tròn màu xanh lam có viền trắng và quầng sáng (nằm trong `IgnorePointer`).
   - Lớp marker POI: Biểu tượng danh mục có màu sắc ngữ nghĩa đặc trưng (Văn hóa: Tím, Ẩm thực: Cam, Thiên nhiên: Xanh lá, Tham quan: Xanh ngọc).
   - Phía trên nút vị trí: Huy hiệu đếm số lượng địa điểm (`"357 địa điểm"`).
   - Góc dưới cùng: Dòng bản quyền dữ liệu *"© OpenStreetMap contributors"*.
6. **Thành phần giao diện (Components):** `FlutterMap`, `TileLayer`, `CircleLayer`, `MarkerLayer`, `_LocationButton`, `_CategoryChipBar`, `_StatusPill`.
7. **Điều hướng (Navigation):** Nằm trong `ShellRoute` (Tab 2). Chạm marker $\rightarrow$ Mở `PlacePreviewSheet`. Chuyển tab không làm mất vị trí bản đồ hay marker đã chọn.
8. **Trạng thái Tải (Loading State):** Icon quay nhẹ trong nút vị trí; các ô gạch bản đồ tải tuần tự không giật màn hình.
9. **Trạng thái Rỗng (Empty State):** Khi lọc danh mục không có POI nào trong bán kính, hiển thị huy hiệu *"0 địa điểm"* mà không làm mất bản đồ.
10. **Trạng thái Lỗi (Error State):** Gạch bản đồ bị lỗi mạng sẽ hiển thị màu nền trung tính nhẹ kèm thông báo mạng yếu; không gây crash app.
11. **Trạng thái Quyền hạn & Định vị (Location & Permission States):**
    - `unknown`: Nút màu xám nhạt, chưa có chấm xanh, không hiện pill.
    - `requesting`: Nút quay tròn tiến trình nhỏ.
    - `granted` / `good` ($\le 50\text{m}$): Nút xanh lam, marker xuất hiện, camera lướt êm ái, pill: `"Đã xác định vị trí · ±X m"`.
    - `approximate` ($50\text{m} - 200\text{m}$): Nút màu hổ phách cảnh báo, pill: `"Vị trí ước lượng · ±X m"`.
    - `poor` ($> 200\text{m}$): Tự động retry; nếu vẫn kém thì hiển thị pill: `"Vị trí chưa chính xác"`.
    - `denied`: Nút đỏ `location_disabled`, pill: `"Quyền vị trí bị từ chối"`, tọa độ giữ `null`, SnackBar có nút *"Mở cài đặt"*.
    - `unavailable`: Nút xám `location_off`, pill: `"Không xác định được vị trí"`, SnackBar nhắc bật GPS.
12. **Hành vi Tương thích (Responsive Behavior):** Trên màn hình lớn, bản đồ mở rộng toàn màn hình; thanh tìm kiếm và bộ lọc được căn giữa với `maxWidth: 720px`.
13. **Yếu tố Khả năng tiếp cận (Accessibility):** Mọi marker đều có nhãn ngữ nghĩa tên địa điểm; các nút điều khiển có kích thước tối thiểu $48 \times 48\text{ dp}$.

---

### Màn hình C: Place Preview Sheet (Tấm xem nhanh Địa điểm)
1. **Mục đích (Purpose):** Cung cấp bản tóm tắt nhanh về địa điểm ngay trên bản đồ mà không làm ngắt quãng dòng khám phá của người dùng.
2. **Mục tiêu người dùng chính (Primary User Goal):** Đánh giá sơ bộ xem địa điểm có hấp dẫn không (khoảng cách, thể loại, uy tín) trước khi quyết định xem chi tiết.
3. **Primary CTA:** Nút Primary nổi bật: *"Xem chi tiết"* (kích hoạt `context.push('/places/:id')`).
4. **Secondary CTA:** Nút đóng (x) ở góc trên phải của tấm trượt.
5. **Cấu trúc phân cấp thông tin (Information Hierarchy):**
   - Thanh kéo vuốt nhỏ ở đỉnh (Drag handle).
   - Tên địa điểm chuẩn tiếng Việt (In đậm, Headline Small).
   - Nhãn thể loại + Huy hiệu *"Đã xác minh"* (khi có nguồn OpenStreetMap hợp lệ).
   - Dòng đánh giá sao: Hiển thị rating thực tế hoặc nhãn chuẩn mực: *"Chưa có đánh giá"*.
   - Dòng khoảng cách: Tính toán theo Haversine từ vị trí người dùng (`"191m"` hoặc `"2.4 km"`). Nếu chưa có định vị: `"Khoảng cách chưa xác định"`.
   - Dòng địa chỉ tóm tắt: Trích xuất từ thẻ OSM `addr:*` hoặc thông báo *"Chưa có thông tin địa chỉ"*.
6. **Thành phần giao diện (Components):** `AppCard`, `AppBadge`, `RatingView`, `AppButton`, `PlacePreviewSheet`.
7. **Điều hướng (Navigation):** Modal Sheet trượt từ đáy. Bấm "Xem chi tiết" mở route `/places/:id`. Chạm chip danh mục khác trên bản đồ sẽ tự động dọn dẹp tấm sheet này.
8. **Trạng thái Tải (Loading State):** Không áp dụng (dữ liệu đã có sẵn từ marker được chọn).
9. **Trạng thái Rỗng (Empty State):** Không áp dụng.
10. **Trạng thái Lỗi (Error State):** Nếu thiếu dữ liệu, hiển thị các fallback trung thực, không bịa đặt.
11. **Trạng thái Quyền hạn (Permission State):** Thể hiện qua dòng khoảng cách: Có quyền GPS $\rightarrow$ hiện mét/km; Không có quyền $\rightarrow$ hiện *"Khoảng cách chưa xác định"*.
12. **Hành vi Tương thích (Responsive Behavior):** Trên màn hình máy tính để bàn (Desktop), tấm preview được bo hẹp với chiều rộng tối đa $480\text{dp}$ đặt nổi ở góc dưới bản đồ, tránh che toàn bộ tầm nhìn.
13. **Yếu tố Khả năng tiếp cận (Accessibility):** Có nút đóng tường minh; các trường thông tin được đọc tuần tự theo thứ tự logic.

---

### Màn hình D: Place Detail Screen (Chi tiết Địa điểm Xác minh)
1. **Mục đích (Purpose):** Cung cấp đầy đủ thông tin thực tế, minh bạch và có thể kiểm chứng về một địa điểm du lịch cụ thể.
2. **Mục tiêu người dùng chính (Primary User Goal):** Nắm rõ giờ mở cửa, cách liên hệ, địa chỉ chính xác, tọa độ và kích hoạt dẫn đường đến địa điểm.
3. **Primary CTA:** Nút cố định ở đáy màn hình: *"Chỉ đường"* (mở Google Maps hoặc ứng dụng bản đồ thiết bị).
4. **Secondary CTA:** Nút *"Thêm vào chuyến đi"* (gán địa điểm vào một ngày lịch trình).
5. **Cấu trúc phân cấp thông tin (Information Hierarchy):**
   - **Hero Section:** Tên địa điểm, Thể loại, Huy hiệu "Đã xác minh", Tên tiếng Anh (nếu có).
   - **Đánh giá (Rating):** Sao đánh giá thực tế hoặc *"Chưa có đánh giá"*.
   - **Địa chỉ (Address):** Địa chỉ chi tiết từ OpenStreetMap hoặc *"Chưa có thông tin địa chỉ."*.
   - **Giờ mở cửa (Opening Hours):** Giờ hoạt động thực tế hoặc *"Chưa có thông tin giờ mở cửa."*.
   - **Thông tin liên hệ (Contact):** Chỉ hiển thị khi có Website hoặc Số điện thoại thực tế; nếu không có thì **ẩn hoàn toàn** phần này.
   - **Vị trí & Bản đồ thu nhỏ (Location & Mini-Map):** Tọa độ GPS rõ ràng + Bản đồ tĩnh xem trước vị trí không có watermark.
   - **Nguồn gốc dữ liệu (Provenance):** *"Nguồn: OpenStreetMap"* kèm liên kết có thể bấm kiểm chứng ODbL; nếu chưa xác minh ghi rõ *"Chưa được xác minh nguồn dữ liệu"*.
   - **Thanh tác vụ đáy (Bottom Action Bar):** Dòng chú thích *"Điều hướng sẽ mở ứng dụng bản đồ"* nằm ngay trên nút *"Chỉ đường"*.
6. **Thành phần giao diện (Components):** `PlaceMiniMap`, `RatingView`, `AppBadge`, `AppButton`, `ResponsiveWrapper`.
7. **Điều hướng (Navigation):** Pushed Route (`/places/:id`). Bấm nút mũi tên quay lại trên AppBar để pop về màn hình trước đó mà không làm mất trạng thái.
8. **Trạng thái Tải (Loading State):** `AppLoading` với thông báo đang tải chi tiết địa điểm.
9. **Trạng thái Rỗng / Không tìm thấy (Empty State):** Khi ID không tồn tại hoặc bị lỗi, hiển thị `AppEmptyState` với nút *"Về bản đồ"*.
10. **Trạng thái Lỗi (Error State):** `AppErrorState` hiển thị lỗi kèm nút *"Thử lại"*.
11. **Trạng thái Quyền hạn (Permission State):** Khoảng cách từ vị trí hiện tại hiển thị nếu có GPS; nếu chưa có hiển thị *"Khoảng cách chưa xác định"*.
12. **Hành vi Tương thích (Responsive Behavior):** Đóng gói trong `ResponsiveWrapper(maxWidth: 720)` giúp giao diện không bị kéo giãn quá khổ trên màn hình lớn.
13. **Yếu tố Khả năng tiếp cận (Accessibility):** Liên kết OSM có nhãn ngữ nghĩa mở trình duyệt ngoài; độ tương phản các khối thông tin đạt chuẩn cao.

---

### Màn hình E: Wandy Empty State (Khởi tạo Trợ lý AI)
1. **Mục đích (Purpose):** Tạo cảm giác đón chào ấm áp và hướng dẫn người dùng cách tương tác hiệu quả với trợ lý du lịch Wandy.
2. **Mục tiêu người dùng chính (Primary User Goal):** Biết được Wandy có thể giúp gì và chọn nhanh một gợi ý câu hỏi để bắt đầu.
3. **Primary CTA:** Ô nhập liệu ở đáy màn hình: *"Hỏi Wandy bất cứ điều gì về chuyến đi..."* kèm nút gửi.
4. **Secondary CTA:** Các thẻ gợi ý câu hỏi nhanh (*"Địa điểm văn hóa ở Hà Nội"*, *"Lập lịch trình 3 ngày Đà Nẵng"*, *"Tìm quán ăn ngon gần Hồ Gươm"*).
5. **Cấu trúc phân cấp thông tin (Information Hierarchy):**
   - Đỉnh: AppBar hiển thị tên Wandy Copilot và biểu tượng lấp lánh (Sparkle).
   - Giữa màn hình: Avatar hoạt họa thân thiện của Wandy + Lời chào thuần Việt *"Xin chào, mình là Wandy! Người bạn đồng hành thông minh cho chuyến đi của bạn."*.
   - Lưới các chủ đề gợi ý (Gợi ý lịch trình, Khám phá địa điểm, Ẩm thực bản địa, Tư vấn an toàn).
   - Đáy màn hình: Khung nhập văn bản cố định.
6. **Thành phần giao diện (Components):** `AppCard`, `AppChip`, `ResponsiveWrapper`, ô nhập liệu `TextField`.
7. **Điều hướng (Navigation):** Nằm trong `ShellRoute` (Tab 3).
8. **Trạng thái Tải (Loading State):** Không áp dụng cho màn hình khởi tạo rỗng.
9. **Trạng thái Rỗng (Empty State):** Chính là trạng thái mặc định của màn hình này.
10. **Trạng thái Lỗi (Error State):** Không áp dụng.
11. **Trạng thái Quyền hạn (Permission State):** Không yêu cầu quyền hệ thống.
12. **Hành vi Tương thích (Responsive Behavior):** Khung chat căn giữa với chiều rộng tối đa $720\text{dp}$.
13. **Yếu tố Khả năng tiếp cận (Accessibility):** Các thẻ chip gợi ý có thể duyệt bằng phím Tab trên web; ô nhập liệu có nhãn hướng dẫn rõ ràng.

---

### Màn hình F: Wandy Conversation (Hội thoại AI & Trích dẫn Nguồn)
1. **Mục đích (Purpose):** Duy trì luồng hội thoại liên tục, cung cấp câu trả lời thông minh được tăng cường bởi dữ liệu thực tế (RAG Grounded).
2. **Mục tiêu người dùng chính (Primary User Goal):** Đọc câu trả lời chi tiết của Wandy, kiểm tra nguồn gốc dữ liệu và tiếp tục hỏi sâu hơn.
3. **Primary CTA:** Nút gửi tin nhắn (Send icon) sau khi nhập nội dung vào ô chat.
4. **Secondary CTA:** Các thẻ chip nguồn trích dẫn (`SourceChip`) nằm ngay dưới câu trả lời của trợ lý.
5. **Cấu trúc phân cấp thông tin (Information Hierarchy):**
   - Danh sách tin nhắn cuộn dọc (Tin nhắn người dùng bên phải, màu nền Primary nhạt; Tin nhắn Wandy bên trái, màu nền Surface sạch sẽ).
   - Nội dung câu trả lời định dạng Markdown (gạch đầu dòng, in đậm tên địa điểm).
   - Mục **"Nguồn tham khảo:"** xuất hiện ngay dưới câu trả lời với các thẻ chip nguồn thực tế (`OpenStreetMap`, `Wikivoyage`).
   - Ô nhập liệu cố định ở đáy màn hình.
6. **Thành phần giao diện (Components):** `ChatMessageBubble`, `SourceChip`, `TypingIndicator`, `ResponsiveWrapper`.
7. **Điều hướng (Navigation):** Tab 3 trong `ShellRoute`. Chạm thẻ chip nguồn mở trình duyệt ngoài kiểm chứng dữ liệu ODbL.
8. **Trạng thái Tải (Loading State):** Hiển thị bóng chat Wandy với hiệu ứng 3 chấm nhảy (Typing Indicator) trong lúc đợi mô hình xử lý.
9. **Trạng thái Rỗng (Empty State):** Khi xóa hội thoại, quay về Màn hình E.
10. **Trạng thái Lỗi (Error State):** Khi AI Service timeout (>30s) hoặc mất mạng, hiển thị bóng chat lỗi với thông báo nhẹ nhàng kèm nút *"Thử lại"*.
11. **Trạng thái Quyền hạn (Permission State):** Nếu người dùng hỏi các câu hỏi cần định vị (ví dụ *"Quán ăn gần tôi"*), Wandy hỏi xin quyền vị trí lịch sự trước khi gợi ý.
12. **Hành vi Tương thích (Responsive Behavior):** Chiều rộng tối đa khung chat $720\text{dp}$; tự động cuộn xuống tin nhắn mới nhất.
13. **Yếu tố Khả năng tiếp cận (Accessibility):** Tin nhắn được cấu trúc bằng ngữ nghĩa văn bản rõ ràng; hỗ trợ phóng to kích thước chữ mà không vỡ layout.

---

### Màn hình G: Trip List Screen (Danh sách Chuyến đi)
1. **Mục đích (Purpose):** Quản lý toàn bộ các chuyến đi du lịch của người dùng (chuyến đi sắp tới, đang đi hoặc đã hoàn thành).
2. **Mục tiêu người dùng chính (Primary User Goal):** Xem lại hành trình đã lên kế hoạch hoặc tạo một chuyến đi mới.
3. **Primary CTA:** Nút nổi (+) Floating Action Button hoặc nút *"Tạo chuyến đi mới"* (mở `/trips/create`).
4. **Secondary CTA:** Chuyển đổi tab lọc: *"Sắp tới"* và *"Lịch sử"*.
5. **Cấu trúc phân cấp thông tin (Information Hierarchy):**
   - Đỉnh: Tiêu đề trang `"Chuyến đi của bạn"` + Bộ lọc trạng thái chuyến đi.
   - Thẻ chuyến đi chính (Trip Card): Tên chuyến đi, Điểm đến, Thời gian (Từ ngày - Đến ngày), Số lượng địa điểm đã lưu, Tổng ngân sách dự tính.
   - Thanh tiến trình hoàn thành lịch trình.
6. **Thành phần giao diện (Components):** `AppCard`, `AppBadge`, `AppButton`, `ResponsiveWrapper`.
7. **Điều hướng (Navigation):** Tab 5 trong `ShellRoute`. Chạm vào thẻ chuyến đi $\rightarrow$ `context.push('/trips/:id')`.
8. **Trạng thái Tải (Loading State):** Skeleton Shimmer các thẻ chuyến đi.
9. **Trạng thái Rỗng (Empty State):** Khi chưa có chuyến đi nào, hiển thị hình minh họa vali du lịch cùng lời mời gọi: *"Bạn chưa có chuyến đi nào. Hãy bắt đầu lên kế hoạch ngay hôm nay!"* kèm nút bấm *"Tạo chuyến đi đầu tiên"*.
10. **Trạng thái Lỗi (Error State):** `AppErrorState` kèm nút tải lại dữ liệu.
11. **Trạng thái Quyền hạn (Permission State):** Không yêu cầu quyền hệ thống.
12. **Hành vi Tương thích (Responsive Behavior):** Trên tablet/desktop hiển thị dạng lưới thẻ 2 cột cân đối.
13. **Yếu tố Khả năng tiếp cận (Accessibility):** Các thẻ chuyến đi có nhãn tóm tắt đầy đủ ngày giờ và điểm đến cho trình đọc màn hình.

---

### Màn hình H: Trip Detail Screen (Chi tiết Hành trình Chuyến đi)
1. **Mục đích (Purpose):** Trung tâm điều khiển toàn bộ lịch trình chuyến đi, quản lý từng ngày, từng địa điểm tham quan và cân đối ngân sách thực tế.
2. **Mục tiêu người dùng chính (Primary User Goal):** Xem lịch trình theo ngày, bổ sung địa điểm mới, hoặc kích hoạt AI tự động lập lịch trình tối ưu.
3. **Primary CTA:** Nút nổi bật: *"Lập lịch trình bằng AI"* (khi chưa có lịch trình hoặc muốn lập lại).
4. **Secondary CTA:** Nút *"Thêm địa điểm"* vào từng ngày; nút *"Chỉnh sửa thông tin chuyến đi"*.
5. **Cấu trúc phân cấp thông tin (Information Hierarchy):**
   - **Header Chuyến đi:** Tên chuyến đi, Điểm đến, Khoảng thời gian, Ngân sách tổng.
   - **Thanh chọn Ngày (Day Selector Tabs):** Băng chuyền ngang chọn Ngày 1, Ngày 2, Ngày 3... kèm ngày tháng thực tế.
   - **Tổng quan Ngân sách Ngày:** Tổng chi phí ước tính của các hoạt động trong ngày so với định mức ngân sách.
   - **Trục thời gian Hoạt động (Day Timeline):** Danh sách các địa điểm trong ngày (Buổi sáng, Buổi chiều, Buổi tối). Mỗi mục gồm: Giờ dự kiến, Tên địa điểm, Địa chỉ tóm tắt, Chi phí dự tính.
   - **Nút hành động nhanh:** Nút thêm địa điểm thủ công vào cuối mỗi ngày.
6. **Thành phần giao diện (Components):** `ItineraryTimelineItem`, `AppCard`, `AppButton`, `ResponsiveWrapper`.
7. **Điều hướng (Navigation):** Pushed Route (`/trips/:id`). Chạm vào thẻ địa điểm trong lịch trình $\rightarrow$ `context.push('/places/:id')`. Bấm nút Back trên AppBar để trở về danh sách chuyến đi.
8. **Trạng thái Tải (Loading State):** Skeleton trục thời gian lịch trình.
9. **Trạng thái Rỗng (Empty State):** Ngày chưa có hoạt động hiển thị thông điệp nhẹ: *"Ngày này chưa có kế hoạch"* kèm nút *"Thêm địa điểm"* hoặc *"Nhờ Wandy gợi ý"*.
10. **Trạng thái Lỗi (Error State):** `AppErrorState` khi không tải được chi tiết chuyến đi.
11. **Trạng thái Quyền hạn (Permission State):** Không yêu cầu quyền hệ thống.
12. **Hành vi Tương thích (Responsive Behavior):** Khung hiển thị tối đa $720\text{dp}$; trục thời gian canh lề gọn gàng, dễ đọc.
13. **Yếu tố Khả năng tiếp cận (Accessibility):** Các mục lịch trình có thể sắp xếp lại thứ tự; nút xóa có hộp thoại xác nhận tránh bấm nhầm.

---

### Màn hình I: AI Planner Preview Sheet (Xem trước Lịch trình AI)
1. **Mục đích (Purpose):** Hiện thực hóa nguyên tắc **"Xem trước trước khi ghi" (Preview-before-save)**. Cho phép người dùng duyệt toàn bộ đề xuất của AI trước khi quyết định ghi vào cơ sở dữ liệu.
2. **Mục tiêu người dùng chính (Primary User Goal):** Đánh giá xem lịch trình AI gợi ý có hợp lý về thời gian và ngân sách hay không.
3. **Primary CTA:** Nút Primary ở đáy tấm trượt: *"Áp dụng vào chuyến đi"*.
4. **Secondary CTA:** Nút *"Hủy bỏ"* hoặc nút điều chỉnh lại yêu cầu cho AI.
5. **Cấu trúc phân cấp thông tin (Information Hierarchy):**
   - Đỉnh tấm trượt: Thanh kéo (Drag handle) + Tiêu đề *"Lịch trình đề xuất từ Wandy"*.
   - **Khối Tổng quan Ngân sách Tất định (Deterministic Budget Overview):**
     - Tổng ngân sách chuyến đi: `X đ`
     - Chi phí dự tính từ các hoạt động: `Y đ`
     - Chênh lệch còn lại: `Z đ`
     - Cảnh báo rõ ràng nếu chi phí vượt quá ngân sách đặt ra.
   - **Khối Lịch trình Chi tiết (Detailed Days Itinerary):** Duyệt từng ngày (Ngày 1, Ngày 2...), từng buổi và danh sách các địa điểm được AI chọn lọc từ kho dữ liệu đã xác minh.
   - **Thanh nút bấm đáy:** Nút "Áp dụng vào chuyến đi" và nút "Hủy".
6. **Thành phần giao diện (Components):** `DraggableScrollableSheet`, `AppCard`, `AppButton`, `AppBadge`.
7. **Điều hướng (Navigation):** Modal Sheet hiển thị đè lên `TripDetailScreen`. Bấm "Áp dụng" gọi API lưu dữ liệu và đóng sheet; bấm "Hủy" đóng sheet mà không lưu bất kỳ thay đổi nào.
8. **Trạng thái Tải (Loading State):** Hộp thoại hiển thị thông điệp *"Wandy đang lập lịch trình và cân đối ngân sách (~30s)..."* kèm thanh tiến trình.
9. **Trạng thái Rỗng (Empty State):** Nếu điểm đến không đủ dữ liệu để tạo lịch trình, thông báo lý do rõ ràng.
10. **Trạng thái Lỗi (Error State):** Lỗi AI không làm mất dữ liệu cũ của chuyến đi; hiển thị thông báo lỗi lịch sự kèm hướng dẫn thử lại.
11. **Trạng thái Quyền hạn (Permission State):** Không yêu cầu quyền hệ thống.
12. **Hành vi Tương thích (Responsive Behavior):** Trên màn hình lớn, modal có chiều rộng tối đa $640\text{dp}$ đặt giữa màn hình.
13. **Yếu tố Khả năng tiếp cận (Accessibility):** Thông tin chi phí được định dạng tiền tệ Việt Nam (`VND`) rõ ràng, dễ phân biệt; cảnh báo vượt ngân sách có icon cảnh báo đi kèm màu sắc.

---

### Màn hình J: Safety Screen (Trung tâm An toàn Du lịch)
1. **Mục đích (Purpose):** Cung cấp các công cụ bảo vệ an toàn, số điện thoại khẩn cấp và thông tin hướng dẫn hữu ích cho du khách tại Việt Nam.
2. **Mục tiêu người dùng chính (Primary User Goal):** Gọi cứu hộ khẩn cấp khi gặp sự cố hoặc tra cứu hướng dẫn an toàn tại địa phương.
3. **Primary CTA:** Nút khẩn cấp SOS nổi bật: *"Gọi Cứu nạn Khẩn cấp"* (kết nối 115 / Đường dây nóng cứu hộ du lịch).
4. **Secondary CTA:** Các nút gọi nhanh Cảnh sát (113), Cứu hỏa (114); Nút chia sẻ vị trí an toàn cho người thân.
5. **Cấu trúc phân cấp thông tin (Information Hierarchy):**
   - Đỉnh: Biểu tượng khiên an toàn + Tiêu đề *"Trung tâm An toàn GoMate"*.
   - Khối phím bấm khẩn cấp SOS (Màu đỏ cảnh báo nhẹ, có xác nhận chống bấm nhầm).
   - Danh bạ đường dây nóng khẩn cấp tại Việt Nam (113, 114, 115, Tổng đài hỗ trợ du khách).
   - Thẻ hướng dẫn an toàn du lịch (Mẹo bảo quản tư trang, lưu ý thời tiết, số điện thoại hỗ trợ của điểm đến).
   - Tính năng Check-in vị trí an toàn (Mô phỏng gửi tin nhắn tọa độ cho người thân).
6. **Thành phần giao diện (Components):** `AppCard`, `AppButton`, `ResponsiveWrapper`.
7. **Điều hướng (Navigation):** Nằm trong `ShellRoute` (Tab 4).
8. **Trạng thái Tải (Loading State):** Không có tải dữ liệu nặng; thông tin danh bạ luôn sẵn sàng offline.
9. **Trạng thái Rỗng (Empty State):** Không áp dụng.
10. **Trạng thái Lỗi (Error State):** Không áp dụng.
11. **Trạng thái Quyền hạn (Permission State):** Yêu cầu quyền vị trí và quyền điện thoại khi kích hoạt tính năng gửi tọa độ SOS.
12. **Hành vi Tương thích (Responsive Behavior):** Bố cục gọn gàng trong khung $640\text{dp}$, các phím bấm khẩn cấp to bản, dễ bấm trong tình huống gấp.
13. **Yếu tố Khả năng tiếp cận (Accessibility):** Các nút SOS có vùng chạm lớn bản tối thiểu $56\text{dp}$, độ tương phản cực cao, biểu tượng đi kèm văn bản rõ ràng.

---

### Màn hình K: Auth Screens (Đăng nhập / Đăng ký)
1. **Mục đích (Purpose):** Xác thực người dùng, bảo vệ dữ liệu chuyến đi và đồng bộ hóa trải nghiệm cá nhân.
2. **Mục tiêu người dùng chính (Primary User Goal):** Đăng nhập nhanh chóng hoặc tạo tài khoản mới dễ dàng, bảo mật.
3. **Primary CTA:** Nút *"Đăng nhập"* hoặc *"Đăng ký tài khoản"*.
4. **Secondary CTA:** Liên kết chuyển đổi qua lại giữa Đăng nhập và Đăng ký; nút xem chính sách bảo mật.
5. **Cấu trúc phân cấp thông tin (Information Hierarchy):**
   - Đỉnh: Logo thương hiệu GoMate + Lời chào mừng.
   - Các trường nhập liệu: Email, Mật khẩu, Xác nhận mật khẩu (với form đăng ký).
   - Thông báo lỗi xác thực inline dưới từng trường nhập liệu.
   - Nút hành động chính.
   - Liên kết điều hướng phụ ở đáy trang.
6. **Thành phần giao diện (Components):** `TextField`, `AppButton`, `ResponsiveWrapper`.
7. **Điều hướng (Navigation):** Pushed Routes (`/login`, `/register`). Sau khi đăng nhập thành công, tự động chuyển về Trang chủ (`/`).
8. **Trạng thái Tải (Loading State):** Nút đăng nhập hiển thị spinner xoay nhẹ khi đang xác thực token JWT.
9. **Trạng thái Rỗng (Empty State):** Không áp dụng.
10. **Trạng thái Lỗi (Error State):** Báo lỗi rõ ràng bằng tiếng Việt (*"Email hoặc mật khẩu không chính xác"*, *"Mật khẩu cần tối thiểu 8 ký tự"*).
11. **Trạng thái Quyền hạn (Permission State):** Không yêu cầu quyền hệ thống.
12. **Hành vi Tương thích (Responsive Behavior):** Form đăng nhập căn giữa với chiều rộng tối đa $420\text{dp}$ trên máy tính.
13. **Yếu tố Khả năng tiếp cận (Accessibility):** Hỗ trợ tự động điền mật khẩu (Autofill); nút ẩn/hiện mật khẩu trực quan.
