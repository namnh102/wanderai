# GoMate — Primary User Journeys & End-to-End User Flows

**Tài liệu:** Đặc tả Chi tiết Các Luồng Người dùng Cốt lõi (Primary User Flows Specification)  
**Phiên bản:** 1.0.0  
**Ngày ban hành:** 2026-10-04  
**Phạm vi:** 10 luồng người dùng trung tâm trong GoMate (FLOW 01 đến FLOW 10)  

---

## Danh mục 10 Luồng Người dùng Cốt lõi

| Mã Luồng | Tên Luồng Trải nghiệm | Điểm bắt đầu (Entry) | Điểm kết thúc (Success) |
| :--- | :--- | :--- | :--- |
| **FLOW 01** | Khám phá điểm đến & địa điểm từ Trang chủ | Màn hình Trang chủ (`/`) | Trang Chi tiết Địa điểm (`/places/:id`) |
| **FLOW 02** | Tìm kiếm & Lọc địa điểm trên Bản đồ | Tab Bản đồ (`/map`) | Trang Chi tiết Địa điểm (`/places/:id`) |
| **FLOW 03** | Yêu cầu định vị GPS & Nhận khoảng cách | Nút "Vị trí của tôi" trên Bản đồ | Marker vị trí, vòng sai số & khoảng cách chuẩn |
| **FLOW 04** | Xử lý từ chối cấp quyền định vị | Nút "Vị trí của tôi" bị từ chối | Fallback êm thuận, SnackBar "Mở cài đặt" |
| **FLOW 05** | Kích hoạt chỉ đường sang ứng dụng Bản đồ ngoài | Trang Chi tiết Địa điểm | Mở Google Maps / Bản đồ hệ điều hành |
| **FLOW 06** | Hỏi đáp du lịch với Wandy AI có trích dẫn nguồn | Tab Wandy AI (`/ai`) | Tin nhắn trả lời kèm thẻ chip nguồn ODbL |
| **FLOW 07** | Tạo chuyến đi & Lập lịch trình tự động bằng AI | Wandy AI / Màn hình Chuyến đi | Lịch trình nhiều ngày được áp dụng an toàn |
| **FLOW 08** | Quản lý lịch trình & Khám phá địa điểm trong chuyến đi | Chi tiết Chuyến đi (`/trips/:id`) | Thêm địa điểm thành công vào lịch trình ngày |
| **FLOW 09** | Thêm địa điểm yêu thích vào chuyến đi đã có | Trang Chi tiết Địa điểm | Địa điểm được gán vào lịch trình ngày của chuyến đi |
| **FLOW 10** | Hỏi Wandy tư vấn ngữ cảnh cho chuyến đi hiện tại | Trang Chi tiết Chuyến đi | Wandy trả lời dựa trên bối cảnh chuyến đi |

---

## Chi tiết Từng Luồng Trải nghiệm

### FLOW 01: Khám phá Điểm đến & Địa điểm từ Trang chủ
- **1. Entry Point:** Người dùng mở ứng dụng, màn hình `HomeScreen` (`/`) hiển thị.
- **2. User Intent:** Người dùng muốn duyệt các điểm đến gợi ý hấp dẫn tại Việt Nam hoặc các địa điểm du lịch văn hóa nổi tiếng.
- **3. Primary Action:** Người dùng chạm vào một thẻ điểm đến (ví dụ: *Hà Nội*, *Đà Nẵng*) hoặc thẻ địa điểm nổi bật trên trang chủ.
- **4. Secondary Actions:** 
  - Cuộn ngang danh sách điểm đến.
  - Sử dụng thanh tìm kiếm để tìm điểm đến cụ thể.
  - Chạm banner Wandy Copilot để nhờ gợi ý.
- **5. Loading State:** Hiển thị `Shimmer` placeholder dạng thẻ ảnh bo tròn $16\text{dp}$.
- **6. Empty State:** Nếu không có kết quả tìm kiếm, hiển thị `AppEmptyState` với thông báo *"Không tìm thấy điểm đến phù hợp"* và gợi ý xóa bộ lọc.
- **7. Error State:** Lỗi mạng hiển thị `AppErrorState` kèm nút *"Thử lại"*.
- **8. Success State:** 
  - Chạm thẻ điểm đến $\rightarrow$ Lọc danh sách địa điểm theo điểm đến đó hoặc mở bản đồ tại điểm đến.
  - Chạm thẻ địa điểm $\rightarrow$ Điều hướng bằng `context.push('/places/:id')` mở `PlaceDetailScreen`.
- **9. Back Behavior:** Bấm nút Back trên AppBar $\rightarrow$ Quay lại `HomeScreen` với vị trí cuộn được bảo toàn nguyên vẹn.
- **10. Cancellation Behavior:** Không áp dụng (luồng đọc dữ liệu).

---

### FLOW 02: Tìm kiếm & Lọc Địa điểm trên Bản đồ
- **1. Entry Point:** Người dùng chuyển sang tab `MapScreen` (`/map`).
- **2. User Intent:** Tìm kiếm một địa điểm cụ thể (ví dụ: *"Chùa Trấn Quốc"*) hoặc lọc các địa điểm theo chủ đề (*Văn hóa*, *Ẩm thực*, *Khách sạn*).
- **3. Primary Action:** 
  - Bước A: Chạm chip thể loại trên thanh bộ lọc (ví dụ: *"Văn hóa"*).
  - Bước B: Chạm vào marker địa điểm trên bản đồ.
  - Bước C: Tấm `PlacePreviewSheet` trượt lên từ đáy $\rightarrow$ Chạm nút Primary *"Xem chi tiết"*.
- **4. Secondary Actions:**
  - Nhập từ khóa tìm kiếm vào thanh Search bar ở đỉnh màn hình.
  - Thay đổi bán kính quét (1km / 5km / 10km).
  - Vuốt trượt bản đồ hoặc phóng to / thu nhỏ.
- **5. Loading State:** Icon spinner mờ trên huy hiệu số lượng địa điểm; bản đồ nền HOT/OSM-FR tải mượt mà không có watermark.
- **6. Empty State:** Khi danh mục hoặc từ khóa không có địa điểm trong bán kính, hiển thị chip badge *"0 địa điểm"* và bản đồ giữ nguyên, không giật camera.
- **7. Error State:** Lỗi API địa điểm hiển thị SnackBar cảnh báo nhẹ, các marker cũ được giữ nguyên trên bản đồ.
- **8. Success State:**
  - Chạm marker: Tấm `PlacePreviewSheet` hiện thông tin chính xác, trung thực (Tên, Ảnh, Khoảng cách tính bằng Haversine, Rating hoặc *"Chưa có đánh giá"*, Huy hiệu "Đã xác minh").
  - Bấm "Xem chi tiết": `context.push('/places/:id')` mở `PlaceDetailScreen`.
- **9. Back Behavior:**
  - Đóng Preview Sheet: Chạm ra ngoài vùng trống bản đồ hoặc chạm chip danh mục khác $\rightarrow$ Preview Sheet đóng sạch sẽ, không lưu vết cũ.
  - Quay lại từ `PlaceDetailScreen`: Bấm nút Back $\rightarrow$ Trở về bản đồ với đúng vị trí camera, mức zoom và marker đang được chọn.
- **10. Cancellation Behavior:** Bấm nút đóng (x) trên thanh tìm kiếm để xóa từ khóa và quay lại danh sách toàn bộ.

---

### FLOW 03: Yêu cầu Định vị GPS & Nhận Khoảng cách Chính xác
- **1. Entry Point:** Màn hình `MapScreen`, người dùng chạm vào nút tròn "Vị trí của tôi" (Floating Action Button ở góc phải dưới).
- **2. User Intent:** Xác định vị trí thực tế của thiết bị để biết mình đang ở đâu và các địa điểm du lịch cách mình bao xa.
- **3. Primary Action:** Chạm nút "Vị trí của tôi" (`my_location_button`).
- **4. Secondary Actions:** Cho phép quyền vị trí trong hộp thoại cấp quyền của trình duyệt hoặc hệ điều hành.
- **5. Loading State:** Nút đổi sang trạng thái quay tròn nhẹ (`requesting`); không chặn các thao tác xem bản đồ khác.
- **6. Empty / Fallback State:** Nếu GPS thiết bị chưa bật, chuyển sang trạng thái nhắc bật dịch vụ vị trí.
- **7. Error State:** Nếu lỗi phần cứng hoặc mất sóng GPS, hiển thị Status Pill *"Không xác định được vị trí"*.
- **8. Success State:**
  - **Quality Gate:** Hệ thống kiểm tra sai số định vị.
    - Nếu $\le 50\text{m}$: Đổi nút sang trạng thái `success`, hiện Status Pill *"Đã xác định vị trí · ±X m"*.
    - Nếu $50\text{m} - 200\text{m}$: Hiện Status Pill *"Vị trí ước lượng · ±X m"*.
    - Nếu $> 200\text{m}$: Tự động thử lại tối đa 3 lần; nếu vẫn kém thì gắn nhãn *"Vị trí chưa chính xác"*.
  - **Hiển thị Bản đồ:** Marker chấm xanh có viền trắng và quầng sáng xuất hiện; vòng tròn sai số màu xanh mờ (`alpha: 0.12`) mở rộng theo đúng `accuracyMeters`.
  - **Camera:** Lướt êm ái 250ms (`easeInOutCubic`) đưa tâm màn hình về tọa độ người dùng, nâng zoom lên 15.0 nếu người dùng đang ở góc nhìn tổng quan.
  - **Khoảng cách:** Toàn bộ Preview Sheet và Place Detail tự động tính khoảng cách Haversine từ tọa độ thực này (ví dụ: `191m` hoặc `2.4 km`).
  - **Bảo toàn POI:** Toàn bộ 357 địa điểm trên bản đồ được giữ nguyên vẹn, **tuyệt đối không bị xóa**.
- **9. Back Behavior:** Status Pill tự động ẩn sau 5 giây hoặc đóng ngay lập tức khi chạm vào pill.
- **10. Cancellation Behavior:** Không áp dụng.

---

### FLOW 04: Xử lý Từ chối Cấp quyền Định vị (Permission Denied)
- **1. Entry Point:** Người dùng bấm nút "Vị trí của tôi", sau đó chọn "Chặn" (Block) hoặc "Từ chối" (Deny) quyền truy cập vị trí.
- **2. User Intent:** Người dùng không muốn chia sẻ vị trí nhưng vẫn muốn duyệt bản đồ bình thường.
- **3. Primary Action:** Người dùng tiếp tục duyệt bản đồ bằng thao tác vuốt chạm thủ công.
- **4. Secondary Actions:** Chạm nút "Mở cài đặt" trên SnackBar nếu muốn kích hoạt lại quyền.
- **5. Loading State:** Nút quay tròn ngắn rồi dừng lại.
- **6. Empty / Graceful Fallback State:**
  - Nút định vị đổi sang icon `location_disabled` (màu đỏ nhẹ của theme).
  - Status Pill hiển thị: *"Quyền vị trí bị từ chối"*.
  - **Tuyệt đối không sinh tọa độ giả** (Vị trí người dùng vẫn là `null`).
  - **Không có chấm xanh hay vòng tròn sai số ảo**.
  - Khoảng cách trên Preview Sheet và Place Detail hiển thị trung thực: *"Khoảng cách chưa xác định"*.
  - Camera bản đồ đứng yên tại chỗ, không giật màn hình.
- **7. Error State:** Xuất hiện SnackBar thân thiện: *"GoMate cần quyền vị trí để hiển thị khoảng cách đến các địa điểm"* kèm nút hành động *"Mở cài đặt"* (kích hoạt `openAppSettings()`).
- **8. Success State:** Người dùng vẫn sử dụng bản đồ bình thường, xem danh mục, tìm kiếm và xem chi tiết địa điểm mà không gặp bất kỳ lỗi crash nào.
- **9. Back Behavior:** Bấm chạm vào Status Pill để tắt thông báo ngay lập tức.
- **10. Cancellation Behavior:** Người dùng bỏ qua SnackBar; ứng dụng không nhắc lại liên tục gây khó chịu.

---

### FLOW 05: Kích hoạt Chỉ đường sang Ứng dụng Bản đồ Ngoài
- **1. Entry Point:** Người dùng đang ở màn hình `PlaceDetailScreen` (`/places/:id`).
- **2. User Intent:** Cần dẫn đường thời gian thực (turn-by-turn navigation) từ vị trí hiện tại đến địa điểm du lịch bằng ô tô / xe máy / đi bộ.
- **3. Primary Action:** Chạm nút Primary Bottom Bar: *"Chỉ đường"*.
- **4. Secondary Actions:** Xem dòng ghi chú trên nút: *"Điều hướng sẽ mở ứng dụng bản đồ"*.
- **5. Loading State:** Hiển thị hiệu ứng nhấn nút ngắn; ứng dụng chuẩn bị URL điều hướng.
- **6. Empty State:** Nếu địa điểm không có tọa độ (trường hợp cực hiếm), nút "Chỉ đường" bị vô hiệu hóa mờ.
- **7. Error State:** Nếu thiết bị không có trình xử lý URL hoặc bị chặn popup trên web, hiển thị thông báo lỗi nhẹ: *"Không thể mở ứng dụng bản đồ trên thiết bị này"*.
- **8. Success State:**
  - **Hợp đồng URL Điều hướng Ngoài:**
    `https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>[&origin=<lat>,<lng>]&travelmode=driving`
  - Nếu người dùng đã có fix vị trí hợp lệ: Đính kèm tham số `origin=<lat>,<lng>`.
  - Nếu chưa có fix vị trí: Chỉ gửi tham số `destination=<lat>,<lng>` (Google Maps sẽ tự lấy vị trí của nó).
  - Thứ tự tọa độ luôn chuẩn xác: Vĩ độ trước, Kinh độ sau (`lat,lng`).
  - Mở trực tiếp ứng dụng Google Maps hoặc Apple Maps trên Native, mở tab mới trên Web/Desktop.
- **9. Back Behavior:** Khi người dùng chuyển ứng dụng quay lại GoMate, màn hình `PlaceDetailScreen` vẫn nguyên vẹn. Bấm Back quay lại `MapScreen` với góc nhìn bản đồ được bảo toàn.
- **10. Cancellation Behavior:** Người dùng đóng ứng dụng bản đồ ngoài để quay về GoMate.

---

### FLOW 06: Hỏi đáp Du lịch với Wandy AI có Trích dẫn Nguồn Thực
- **1. Entry Point:** Chuyển sang tab `AiChatScreen` (`/ai`) từ thanh Bottom Navigation Bar.
- **2. User Intent:** Nhờ Wandy tư vấn kinh nghiệm du lịch, các điểm tham quan văn hóa, hoặc giờ mở cửa/giá vé ở một điểm đến.
- **3. Primary Action:** 
  - Trường hợp 1: Chạm một thẻ gợi ý câu hỏi nhanh (ví dụ: *"Địa điểm văn hóa ở Hà Nội"*).
  - Trường hợp 2: Gõ câu hỏi vào ô nhập liệu ở đáy màn hình và bấm nút Gửi (icon Send).
- **4. Secondary Actions:**
  - Chạm vào một thẻ chip nguồn trích dẫn (`OpenStreetMap` hoặc `Wikivoyage`) để kiểm chứng liên kết gốc.
  - Sao chép câu trả lời.
- **5. Loading State:**
  - Bóng chat của Wandy xuất hiện với hiệu ứng 3 chấm nhảy (Typing Indicator).
  - Ô nhập liệu tạm thời khóa để tránh gửi trùng lặp; nút gửi đổi sang trạng thái bận.
- **6. Empty State:** Khi mở tab lần đầu, hiển thị màn hình rỗng thân thiện: Lời chào *"Xin chào, mình là Wandy!"* kèm 4 thẻ gợi ý chủ đề du lịch.
- **7. Error State:**
  - Nếu mất mạng hoặc AI Service timeout (>30s): Xuất hiện bóng chat lỗi lịch sự: *"Wandy hiện đang quá tải hoặc gặp gián đoạn kết nối. Vui lòng thử lại sau giây lát."* kèm nút *"Thử lại"*.
- **8. Success State:**
  - Phản hồi từ Wandy hiển thị mạch lạc, thuần Việt, đúng định dạng Markdown.
  - Phía dưới câu trả lời xuất hiện mục: **"Nguồn tham khảo:"** kèm các thẻ chip trích dẫn nguồn thực tế:
    - Chip `OpenStreetMap (way/123456)` $\rightarrow$ Chạm mở liên kết kiểm chứng ODbL.
    - Chip `Wikivoyage: Hà Nội` $\rightarrow$ Chạm mở bài viết cẩm nang du lịch.
  - Nếu thông tin chưa có trong hệ thống dữ liệu: Wandy trả lời trung thực *"Hiện tại mình chưa có thông tin chính thức về giá vé của địa điểm này"*, **tuyệt đối không bịa đặt**.
- **9. Back Behavior:** Chuyển sang tab khác (ví dụ: Bản đồ) rồi quay lại tab Wandy $\rightarrow$ Toàn bộ đoạn hội thoại và các thẻ chip nguồn vẫn được giữ nguyên vẹn.
- **10. Cancellation Behavior:** Không áp dụng.

---

### FLOW 07: Tạo Chuyến đi & Lập Lịch trình Tự động bằng AI (AI Trip Planner)
- **1. Entry Point:** 
  - Cách 1: Từ màn hình `TripDetailScreen` (`/trips/:id`), chạm nút *"Lập lịch trình bằng AI"*.
  - Cách 2: Từ hội thoại Wandy Copilot, người dùng yêu cầu *"Lên kế hoạch 3 ngày đi Đà Nẵng"* $\rightarrow$ Wandy gợi ý mở form tạo lịch trình.
- **2. User Intent:** Tự động lên lịch trình chi tiết theo từng ngày với các địa điểm du lịch phù hợp sở thích, đồng thời tính toán chi phí khớp với ngân sách đặt ra.
- **3. Primary Action:**
  - Bước A: Thiết lập bối cảnh chuyến đi (`TripContext`: Điểm đến, Số ngày, Ngân sách tổng, Sở thích du lịch).
  - Bước B: Bấm xác nhận chạy thuật toán lập kế hoạch AI.
  - Bước C: Tấm trượt `AiPlannerPreviewSheet` hiển thị lịch trình dự kiến $\rightarrow$ Bấm nút *"Áp dụng vào chuyến đi"*.
- **4. Secondary Actions:**
  - Chỉnh sửa ghi chú yêu cầu thêm cho AI trước khi tạo.
  - Xem trước bảng phân bổ ngân sách ước tính và cảnh báo vượt ngân sách.
  - Bấm nút *"Hủy"* nếu chưa ưng ý lịch trình AI đề xuất.
- **5. Loading State:**
  - Màn hình hiển thị hộp thoại tiến trình: *"Wandy đang phân tích địa điểm và tính toán chi phí..."* kèm thanh tiến trình và thông báo thời gian ước tính (~30 giây).
  - Không cho phép người dùng bấm gửi liên tục; có nút "Hủy tác vụ" nếu người dùng không muốn chờ.
- **6. Empty State:** Nếu điểm đến chưa có đủ địa điểm trong cơ sở dữ liệu để tạo đủ ngày, AI trả về thông báo nhã nhặn đề xuất giảm số ngày hoặc đổi điểm đến.
- **7. Error State:**
  - Nếu AI Service trả về lỗi hoặc timeout: Hiển thị thông báo *"Nhà cung cấp AI không phản hồi. Dữ liệu chuyến đi của bạn được giữ nguyên trạng, không có thay đổi nào được ghi."*
- **8. Success State:**
  - **Nguyên tắc "Xem trước trước khi ghi" (Preview-before-save):**
    - Mở tấm `AiPlannerPreviewSheet` hiển thị đầy đủ danh sách ngày (Ngày 1, Ngày 2, Ngày 3), danh sách địa điểm trong từng buổi (Sáng, Chiều, Tối), và bảng tính toán chi phí tất định (`Deterministic Budget Arithmetic`).
    - Hiển thị rõ: *Ngân sách dự kiến*, *Chi phí ước tính*, *Chênh lệch*, Cảnh báo nếu vượt ngân sách.
    - Tại thời điểm này, **chưa có bất kỳ dòng dữ liệu nào được ghi vào cơ sở dữ liệu**.
  - **Ghi Đè Nguyên Tử (Atomic Apply):**
    - Khi người dùng bấm *"Áp dụng vào chuyến đi"*: Nếu chuyến đi đã có lịch trình cũ, hiển thị hộp thoại xác nhận ghi đè.
    - Khi xác nhận: Gọi API `/itinerary/bulk` lưu nguyên tử toàn bộ lịch trình.
    - Màn hình `TripDetailScreen` cập nhật ngay lập tức với lịch trình mới.
- **9. Back Behavior:** Bấm nút Back hoặc vuốt đóng sheet xem trước $\rightarrow$ Toàn bộ kế hoạch nháp bị hủy bỏ an toàn; chuyến đi giữ nguyên trạng thái trước đó.
- **10. Cancellation Behavior:** Bấm "Hủy" trên modal xem trước $\rightarrow$ Hộp thoại đóng lại, không có dữ liệu nào bị xáo trộn.

---

### FLOW 08: Quản lý Lịch trình & Khám phá Địa điểm trong Chuyến đi
- **1. Entry Point:** Tab `TripListScreen` (`/trips`) $\rightarrow$ Chạm chọn một chuyến đi để vào `TripDetailScreen` (`/trips/:id`).
- **2. User Intent:** Xem lịch trình chi tiết của chuyến đi theo ngày, điều chỉnh giờ giấc, hoặc xem thông tin của một địa điểm trong lịch trình.
- **3. Primary Action:** Chạm vào một thẻ địa điểm trong lịch trình ngày $\rightarrow$ Mở `PlaceDetailScreen` (`/places/:id`).
- **4. Secondary Actions:**
  - Chuyển tab ngày (Ngày 1, Ngày 2, Ngày 3).
  - Bấm icon xóa hoặc đổi thứ tự mục lịch trình.
  - Bấm nút *"Thêm địa điểm"* vào ngày để tìm kiếm và bổ sung thủ công.
- **5. Loading State:** Skeleton Shimmer các thẻ lịch trình dọc theo trục thời gian (Timeline).
- **6. Empty State:** Ngày chưa có địa điểm nào hiển thị thông báo nhẹ: *"Chưa có hoạt động nào trong ngày này"* kèm nút bấm *"Thêm địa điểm ngay"*.
- **7. Error State:** Lỗi tải dữ liệu hiển thị `AppErrorState` có nút bấm thử lại.
- **8. Success State:** Người dùng duyệt toàn bộ lịch trình trực quan, thấy rõ thời gian, tên địa điểm, chi phí dự tính và ghi chú cá nhân.
- **9. Back Behavior:** Từ `PlaceDetailScreen` bấm nút Back $\rightarrow$ Quay lại đúng ngày đang xem trong `TripDetailScreen`. Từ `TripDetailScreen` bấm Back $\rightarrow$ Quay lại danh sách chuyến đi.
- **10. Cancellation Behavior:** Thao tác xóa mục lịch trình có SnackBar hoàn tác (Undo) trong 4 giây.

---

### FLOW 09: Thêm Địa điểm Yêu thích vào Chuyến đi (Add to Trip)
- **1. Entry Point:** Màn hình `PlaceDetailScreen` (`/places/:id`), người dùng chạm nút hành động Secondary: *"Thêm vào chuyến đi"*.
- **2. User Intent:** Lưu địa điểm đang xem vào một chuyến đi cụ thể trong lịch trình tương lai của mình.
- **3. Primary Action:**
  - Bước A: Chạm nút *"Thêm vào chuyến đi"*.
  - Bước B: Tấm trượt `SelectTripBottomSheet` hiển thị danh sách các chuyến đi đang mở.
  - Bước C: Chọn chuyến đi và chọn Ngày muốn thêm (ví dụ: *Chuyến đi Đà Nẵng - Ngày 2*).
  - Bước D: Bấm xác nhận *"Lưu vào lịch trình"*.
- **4. Secondary Actions:** Có lối tắt *"Tạo chuyến đi mới"* ngay trong tấm trượt nếu người dùng chưa có chuyến đi nào phù hợp.
- **5. Loading State:** Nút xác nhận hiển thị spinner xoay nhẹ trong 0.5s khi ghi dữ liệu.
- **6. Empty State:** Nếu người dùng chưa có chuyến đi nào, tấm trượt hiển thị thông báo kèm nút *"Tạo chuyến đi đầu tiên"*.
- **7. Error State:** Lỗi mạng hiển thị SnackBar: *"Không thể thêm địa điểm vào chuyến đi. Vui lòng kiểm tra kết nối."*
- **8. Success State:** SnackBar thông báo thành công: *"Đã thêm Chùa Trấn Quốc vào Ngày 2 của chuyến đi!"* kèm nút bấm *"Xem chuyến đi"*.
- **9. Back Behavior:** Tấm trượt đóng lại, người dùng tiếp tục xem thông tin trên màn hình `PlaceDetailScreen`.
- **10. Cancellation Behavior:** Chạm vùng mờ bên ngoài tấm trượt để hủy thao tác thêm.

---

### FLOW 10: Hỏi Wandy Tư vấn Ngữ cảnh cho Chuyến đi Hiện tại
- **1. Entry Point:** Tại màn hình `TripDetailScreen` (`/trips/:id`), chạm vào biểu tượng nổi hoặc banner Wandy: *"Hỏi Wandy về chuyến đi này"*.
- **2. User Intent:** Nhờ AI đánh giá lịch trình hiện tại (ví dụ: *"Lịch trình Ngày 1 có bị quá dày không?"*, *"Gợi ý quán ăn tối gần địa điểm cuối cùng của Ngày 2"*).
- **3. Primary Action:** Chọn câu hỏi gợi ý theo ngữ cảnh hoặc gõ câu hỏi thắc mắc riêng về chuyến đi.
- **4. Secondary Actions:** Yêu cầu Wandy điều chỉnh thay thế một địa điểm cụ thể trong lịch trình.
- **5. Loading State:** Hiển thị bong bóng suy nghĩ của Wandy với chú thích: *"Wandy đang đọc lịch trình và phân tích vị trí các điểm đến..."*
- **6. Empty State:** Không áp dụng.
- **7. Error State:** Lỗi AI hiển thị thông báo lỗi thân thiện và giữ nguyên giao diện chuyến đi.
- **8. Success State:** Wandy trả lời chính xác dựa trên danh sách các địa điểm thực tế của chuyến đi, khoảng cách di chuyển giữa các điểm và đưa ra lời khuyên thiết thực (ví dụ cảnh báo thời gian di chuyển giữa 2 điểm quá xa hoặc gợi ý quán ăn uy tín gần kề kèm trích dẫn nguồn OpenStreetMap).
- **9. Back Behavior:** Bấm nút đóng khung tư vấn để quay lại màn hình chi tiết chuyến đi.
- **10. Cancellation Behavior:** Người dùng đóng khung chat mà không áp dụng các gợi ý của Wandy.
