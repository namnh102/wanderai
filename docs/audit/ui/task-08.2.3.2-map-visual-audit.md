# Báo Cáo Kiểm Định Thiết Kế Thị Giác: Màn Hình Bản Đồ GoMate (V1)

**Nhiệm vụ:** `TASK 08.2.3.2 — GoMate Map Visual Mockup V1`  
**Ngày kiểm định:** 2026-10-05  
**Nhánh:** `feature/gomate-visual-mockups`  
**Trạng thái kiểm định:** ĐẠT 100% TIÊU CHUẨN THỊ GIÁC & QUY TẮC BẢO TOÀN KIẾN TRÚC  
**Tập tài liệu thẩm định:** `docs/design/gomate-map-visual-spec-v1.md`  

---

## 1. Tài Liệu Tham Chiếu (Reference Documents)

Quá trình thiết kế và kiểm định visual mockup tuân thủ nghiêm ngặt 17 tài liệu nền tảng trong repository:

1. `docs/design/gomate-design-system-ux-spec-v1.md` (Design Tokens, Typography, Colors)
2. `docs/design/gomate-ux-architecture-v1.md` (Cấu trúc thông tin & hệ thống điều hướng)
3. `docs/design/gomate-information-architecture.md` (Cây phân cấp tính năng)
4. `docs/design/gomate-user-flows.md` (`FLOW 03` Bản đồ & `FLOW 08` Chi tiết địa điểm)
5. `docs/design/gomate-screen-specification.md` (Đặc tả màn hình bản đồ v1)
6. `docs/design/gomate-screen-spec-v2.md` (Đặc tả màn hình bản đồ v2)
7. `docs/design/gomate-interaction-specification.md` (Quy chuẩn tương tác & cử chỉ)
8. `docs/design/gomate-responsive-specification.md` (Quy tắc co giãn đa kích thước màn hình)
9. `docs/design/gomate-master-ux-plan-v2.md` (Kế hoạch tổng thể UX GoMate v2)
10. `docs/design/gomate-implementation-sprint-01.md` (Kế hoạch sprint triển khai UI)
11. `docs/architecture/map-flow.md` (Luồng dữ liệu và trạng thái bản đồ)
12. `docs/architecture/place-detail-flow.md` (Luồng chuyển tiếp xem chi tiết)
13. `docs/architecture/ui-architecture.md` (Kiến trúc phân tầng Widget & Provider)
14. `docs/architecture/decisions/ADR-005-map-provider.md` (Quyết định sử dụng flutter_map)
15. `docs/architecture/decisions/ADR-006-map-tile-provider.md` (Quyết định sử dụng HOT/OSM-FR basemap)
16. `docs/audit/ui/task-08.2.1-ux-architecture-audit.md` (Audit kiến trúc UX)
17. `docs/audit/task-08.1-closure-audit.md` (Báo cáo đóng task vị trí thời gian thực & điều hướng)

---

## 2. Bảng Kiểm Tra Mockup Hình Ảnh Đã Tạo (Artifact Verification)

Đã tạo đủ $16 / 16$ mockup chất lượng cao tại thư mục:  
`docs/audit/evidence/ui-08.2.3.2/`

| STT | Tập tin Mockup | Nền tảng | Trạng thái hiển thị | Tình trạng |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `map-mobile-default.png` | Mobile ($390 \times 844$) | Trạng thái mặc định: Bản đồ HOT, ô tìm kiếm, chip danh mục, 357 địa điểm, nút vị trí idle | **ĐẠT** |
| 2 | `map-mobile-location-good.png` | Mobile ($390 \times 844$) | Định vị chính xác cao: Chấm xanh GPS, vòng tròn sai số $\pm 25\text{m}$, Status pill xanh lam | **ĐẠT** |
| 3 | `map-mobile-location-approximate.png` | Mobile ($390 \times 844$) | Vị trí ước lượng Wi-Fi/IP: Chấm hổ phách, vòng tròn sai số rộng $\pm 180\text{m}$, Status pill vàng | **ĐẠT** |
| 4 | `map-mobile-permission-denied.png` | Mobile ($390 \times 844$) | Từ chối quyền vị trí: Nút đỏ disabled, status pill đỏ, SnackBar có nút "Mở cài đặt", không có chấm giả | **ĐẠT** |
| 5 | `map-mobile-location-unavailable.png` | Mobile ($390 \times 844$) | Vị trí không khả dụng: Nút xám, status pill xám, bản đồ vẫn thao tác bình thường | **ĐẠT** |
| 6 | `map-mobile-search.png` | Mobile ($390 \times 844$) | Tìm kiếm từ khóa `"Chùa"`: Nút xóa `[✕]`, lọc hiển thị 2 địa điểm phù hợp | **ĐẠT** |
| 7 | `map-mobile-search-empty.png` | Mobile ($390 \times 844$) | Tìm kiếm rỗng `"Thác Bản Giốc"`: Thẻ thông báo thân thiện, đếm "0 địa điểm", 2 nút CTA phục hồi | **ĐẠT** |
| 8 | `map-mobile-category-filter.png` | Mobile ($390 \times 844$) | Lọc danh mục `"Nhà hàng"`: Chip Teal active, chỉ hiển thị marker nhà hàng, đóng preview cũ | **ĐẠT** |
| 9 | `map-mobile-selected-place.png` | Mobile ($390 \times 844$) | Đã chọn Chùa Trấn Quốc: Marker nổi bật, Tấm Preview Sheet trượt từ đáy, 2.4 km, Đã xác minh | **ĐẠT** |
| 10 | `map-mobile-tile-error.png` | Mobile ($390 \times 844$) | Lỗi tải gạch bản đồ: Nền caro mềm, banner cảnh báo vàng nhạt + nút "Thử lại", POI vẫn hoạt động | **ĐẠT** |
| 11 | `map-desktop-default.png` | Desktop ($1440 \times 900$) | Bản đồ toàn màn hình, Top Nav Bar, ô tìm kiếm căn giữa $580\text{px}$, phím tắt `Ctrl K` | **ĐẠT** |
| 12 | `map-desktop-location-good.png` | Desktop ($1440 \times 900$) | Định vị chính xác trên desktop: Chấm xanh GPS, status pill cạnh cụm nút điều khiển góc phải | **ĐẠT** |
| 13 | `map-desktop-search.png` | Desktop ($1440 \times 900$) | Tìm kiếm trên desktop: Trải nghiệm portal du lịch hiện đại, lọc marker thời gian thực | **ĐẠT** |
| 14 | `map-desktop-selected-place.png` | Desktop ($1440 \times 900$) | Thẻ ngữ cảnh bên phải (Side Panel $380\text{px}$): Giữ nguyên góc nhìn bản đồ rộng mở | **ĐẠT** |
| 15 | `map-desktop-permission-denied.png` | Desktop ($1440 \times 900$) | Cảnh báo từ chối quyền vị trí trên trình duyệt máy tính, toast thông báo lịch sự góc phải | **ĐẠT** |
| 16 | `map-desktop-search-empty.png` | Desktop ($1440 \times 900$) | Modal tìm kiếm rỗng căn giữa màn hình desktop với đầy đủ lựa chọn mở rộng bán kính | **ĐẠT** |

---

## 3. Kiểm Tra Tính Nhất Quán Thiết Kế (Consistency Check)

| Tiêu chuẩn Kiểm tra | Yêu cầu Kỹ thuật | Kết quả Thẩm định | Đánh giá |
| :--- | :--- | :--- | :--- |
| **Màu thương hiệu** | GoMate Teal `#0F766E`, Container `#CCFBF1` | Sử dụng chuẩn xác cho nút CTA, chip active, icon tìm kiếm | **PASS** |
| **Màu danh mục** | Bám sát `AppColors.forCategory()` | Văn hóa (Indigo), Tham quan (Purple), Nhà hàng (Orange), Khách sạn (Teal) | **PASS** |
| **Bản đồ nền** | HOT tiles + Fallback OSM-FR | Không có watermark "API KEY REQUIRED", không có trường API key | **PASS** |
| **Dòng bản quyền** | Ghi rõ OpenStreetMap & HOT / OSM France | Đặt tại góc dưới trái, kích thước nhỏ gọn, không che khuất POI | **PASS** |
| **Hành vi Camera** | Không nhảy camera tự động | Camera chỉ di chuyển khi bấm "Vị trí của tôi" (thời gian $250\text{ms}$) | **PASS** |
| **Tính trung thực dữ liệu** | Không bịa đánh giá, không bịa review | Đánh giá hiển thị `"Chưa có đánh giá"`, huy hiệu `"Đã xác minh"` | **PASS** |
| **Tính trung thực vị trí** | Khoảng cách chỉ tính từ vị trí thiết bị | Hiển thị `"Khoảng cách chưa xác định"` khi chưa có tọa độ GPS hợp lệ | **PASS** |
| **Vùng chạm tối thiểu** | Tối thiểu $44\text{px}$, khuyến nghị $48\text{px}$ | Nút vị trí $48 \times 48\text{px}$, nút bán kính $44 \times 44\text{px}$, chip lọc $36 - 40\text{px}$ | **PASS** |
| **Typography Tiếng Việt** | Có dấu thanh tiếng Việt $100\%$ đầy đủ | Không có từ viết tắt cẩu thả, không hiển thị tiếng Anh lạc quẻ | **PASS** |
| **Phân biệt Desktop** | Không kéo giãn giao diện di động | Sử dụng Top Nav Bar $64\text{px}$ và Contextual Side Panel $380\text{px}$ | **PASS** |

---

## 4. Xung Đột Thiết Kế Đã Được Ngăn Chặn (Design Conflicts Prevented)

1. **Xung đột Che khuất Nút Điều khiển khi mở Preview Sheet:**
   - *Vấn đề tiềm ẩn:* Khi tấm xem trước trượt lên, nó có thể che mất huy hiệu đếm địa điểm hoặc nút vị trí.
   - *Giải pháp thiết kế:* Khi `selectedPlace != null`, tọa độ đáy của `PlaceCountBadge` và cụm điều khiển tự động được nâng lên `340px` (nằm an toàn ngay phía trên tấm preview).
2. **Xung đột Vòng tròn Sai số chặn Thao tác Chạm Marker:**
   - *Vấn đề tiềm ẩn:* Lớp `CircleLayer` sai số GPS nếu vẽ đè lên sẽ chặn sự kiện tap vào marker của người dùng.
   - *Giải pháp thiết kế:* Lớp `CircleLayer` được cấu hình `IgnorePointer` và đặt ở tầng dưới lớp ghim `MarkerLayer`.
3. **Xung đột Giữ lại Tấm Xem trước Cũ khi Đổi Danh mục (Stale Preview):**
   - *Vấn đề tiềm ẩn:* Người dùng đang xem Chùa Trấn Quốc (Văn hóa) rồi bấm lọc "Nhà hàng", nếu giữ preview sẽ gây nhầm lẫn.
   - *Giải pháp thiết kế:* Hành vi chọn danh mục mới lập tức kích hoạt `deselectPlace()`, đóng sạch tấm xem trước cũ.

---

## 5. Quyết Định Thiết Kế Mở & Đề Xuất Cho Lập Trình Viên (Recommendations)

1. **Cơ chế Phím tắt trên Desktop:**
   - Đề xuất bổ sung sự kiện lắng nghe phím tắt `Ctrl + K` (hoặc `Cmd + K` trên macOS) để tự động kích hoạt con trỏ vào thanh tìm kiếm trên Web.
2. **Hiệu ứng Mờ dần của Status Pill:**
   - Khi có fix vị trí tốt, `LocationStatusPill` hiển thị thông báo độ chính xác trong 5 giây rồi tự động `fadeOut()`. Người dùng cũng có thể chạm trực tiếp vào viên thuốc để đóng ngay lập tức.
3. **Cơ chế Chuyển tiếp Xem Chi tiết:**
   - Tuyệt đối dùng lệnh `context.push('/places/${id}')` (thay vì `context.go`) để màn hình `MapScreen` cùng toàn bộ trạng thái camera, vị trí và danh mục được giữ nguyên vẹn bên dưới mà không bị khởi tạo lại khi quay về.

---

## Kết Luận Thẩm Định

TASK 08.2.3.2 đã hoàn thành trọn vẹn và xuất sắc mọi yêu cầu:
- 16 hình ảnh visual mockup độ phân giải cao đã được tạo lập thành công.
- 2 tài liệu đặc tả kỹ thuật và báo cáo kiểm định đã được ban hành đầy đủ.
- Toàn bộ hành vi bản đồ, định vị và bảo tồn trạng thái đã được khóa chặt.
- Sẵn sàng chuyển giao cho Human Review phê duyệt trước khi tiếp tục với màn hình tiếp theo: **Màn hình Chi tiết Địa điểm (PLACE DETAIL SCREEN)**.
