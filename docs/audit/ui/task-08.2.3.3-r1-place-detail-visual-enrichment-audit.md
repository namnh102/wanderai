# Báo Cáo Kiểm Toán Thiết Kế Thị Giác & Trải Nghiệm Đa Phương Tiện (Task 08.2.3.3-R1)

**Tài liệu:** Kiểm toán Thiết kế Thị giác & Làm Giàu Media Màn hình Chi tiết Địa điểm GoMate (Place Detail Visual Enrichment & Media Design Audit)  
**Mã kiểm toán:** `AUDIT-UI-08.2.3.3-R1`  
**Ngày thực hiện:** 2026-10-05  
**Nhánh Git:** `feature/gomate-visual-mockups`  
**Cơ sở đánh giá:** `develop` + UX Review Baseline (`TASK 08.2.2`) + Place Detail V1 (`TASK 08.2.3.3`)  
**Tình trạng:** HOÀN THÀNH — DESIGN ONLY (0 dòng mã nguồn ứng dụng bị thay đổi).

---

## 1. Mục Tiêu & Bối Cảnh Thực Hiện

Nhiệm vụ `TASK 08.2.3.3-R1` là đợt nâng cấp toàn diện thiết kế giao diện thị giác của màn hình **Chi tiết địa điểm** (`PLACE DETAIL` — route `/places/:id`) từ phiên bản V1 lên V2, chuyển trọng tâm từ một trang liệt kê thông số kỹ thuật thuần túy thành **Trải nghiệm Khám phá Du lịch (Travel Discovery Experience)**:
- Trực quan hơn với hình ảnh phong cảnh làm chủ đạo (Photo-First Hero).
- Tích hợp thư viện ảnh đa góc nhìn (Gallery strip & Fullscreen Lightbox).
- Hàng thông số nhanh (Quick Facts) gói gọn khoảng cách GPS, giờ mở cửa và đánh giá thực tế.
- Bổ sung tầng kể chuyện du lịch (Điểm nổi bật & Giới thiệu văn hóa).
- Bảo toàn tuyệt đối các nguyên tắc trung thực dữ liệu, minh bạch nguồn OpenStreetMap và luồng nghiệp vụ cốt lõi (Khám phá $\rightarrow$ Lên kế hoạch $\rightarrow$ Điều hướng).

---

## 2. Đánh Giá Đối Soát: Phiên Bản V1 vs Phiên Bản V2

### 2.1. Đánh Giá Phiên Bản V1 (TASK 08.2.3.3)
- **Điểm làm tốt (What Works):**
  - Thứ bậc thông tin mạch lạc, dễ đọc.
  - Trung thực dữ liệu tuyệt đối: không bịa đặt số sao, không ghép địa chỉ ảo, hiển thị chính xác dòng chữ *"☆ Chưa có đánh giá"* và *"📍 Chưa có thông tin địa chỉ."*.
  - Luồng thêm vào chuyến đi (Add to Trip) 3 bước rõ ràng và liên kết tốt với tính năng Trip.
  - Hành vi điều hướng bản đồ ngoài mở đúng tọa độ qua Google Maps.
  - Bảo toàn trạng thái bản đồ khi nhấn nút quay lại (`context.pop()`).
- **Điểm còn hạn chế (What Does Not Work):**
  - Thiếu cảm xúc du lịch (Travel Inspiration): Nhìn giống một trang cơ sở dữ liệu hành chính hoặc hồ sơ tra cứu hơn là ứng dụng truyền cảm hứng xê dịch.
  - Vắng bóng hình ảnh: Toàn bộ Hero chỉ là icon danh mục và card chữ, không có ảnh chụp thực địa.
  - Hội chứng "Card soup": Các khối thông tin bị bọc trong quá nhiều card trắng dày đặc, gây nặng nề và đơn điệu.
  - Chưa có cơ chế hiển thị thư viện ảnh hoặc ảnh do cộng đồng đóng góp.

### 2.2. Điểm Đột Phá Trong Phiên Bản V2 (TASK 08.2.3.3-R1)
- **Image-First Hero:** Đưa bức ảnh phong cảnh chất lượng cao lên làm tâm điểm thị giác hàng đầu, chiếm trọn 240px đỉnh màn hình mobile và 320px trên desktop.
- **Gallery Experience:** Tích hợp dải thumbnail 4 ô bên dưới Hero và chế độ xem toàn màn hình (Fullscreen Lightbox) với chỉ số ảnh `N / M`, chú thích ảnh và bản quyền giấy phép Creative Commons.
- **Soft Illustration Fallback:** Khi địa điểm chưa có ảnh trong hệ thống, giao diện kích hoạt minh họa kiến trúc mềm mại và thông báo *"Chưa có hình ảnh"*, tuyệt đối không tự ý nhặt ảnh Internet không rõ nguồn gốc.
- **Quick Facts Row:** Đưa 3 thông số then chốt (Khoảng cách GPS từ thiết bị, Giờ mở cửa, Đánh giá) lên thành hàng viên thuốc nhỏ gọn ngay dưới tên địa điểm.
- **Discovery Storytelling:** Thêm khu vực "Điểm nổi bật" với các tag văn hóa (ví dụ: *"🏮 Ngôi chùa 1.500 năm tuổi"*, *"🌅 Hoàng hôn Hồ Tây"*).
- **Two-Column Desktop Discovery Grid:** Bố cục máy tính chia 2 cột ($740\text{ px} + 410\text{ px}$) cân đối, kết hợp gợi ý thông minh từ AI Copilot (Wandy AI Tip) và Bản đồ Mini ghim vị trí thực địa.

---

## 3. Danh Mục 22 Visual Mockups Hoàn Chỉnh (`docs/audit/evidence/ui-08.2.3.3-r1/`)

Tất cả 22 mockups đã được xuất tự động bằng trình duyệt Edge Headless với chuẩn đồ họa pixel-perfect, màu sắc chuẩn GoMate Design System và phông chữ tiếng Việt chuẩn mực:

| STT | Tên file mockup | Độ phân giải | Mô tả trạng thái thiết kế |
| :---: | :--- | :---: | :--- |
| **01** | `place-v2-mobile-rich.png` | $390 \times 844$ | Trạng thái mặc định phong phú: Hero ảnh chùa Trấn Quốc, dải thumbnail, huy hiệu Đã xác minh, hàng Quick Facts, Điểm nổi bật, Giới thiệu, Thông tin cần biết, Bản đồ Mini HOT và Sticky Action Bar. |
| **02** | `place-v2-mobile-gallery.png` | $390 \times 844$ | Trình chiếu ảnh toàn màn hình (Fullscreen Lightbox): Nền tối điện ảnh `#0B132B`, bộ đếm `3 / 6 ảnh`, ảnh phóng to sắc nét, chú thích ảnh và bản quyền CC BY-SA 4.0. |
| **03** | `place-v2-mobile-no-image.png` | $390 \times 844$ | Fallback khi địa điểm chưa có ảnh: Vector minh họa kiến trúc thanh lịch + *"Chưa có hình ảnh · Dữ liệu đang được cập nhật từ nguồn mở"*. |
| **04** | `place-v2-mobile-image-error.png` | $390 \times 844$ | Trạng thái lỗi tải ảnh do mạng/CDN: Khung viền đứt nét đỏ nhạt, cảnh báo *"Không thể tải hình ảnh"* kèm nút *"Thử lại"*. |
| **05** | `place-v2-mobile-no-rating.png` | $390 \times 844$ | Trung thực đánh giá: Hero ảnh đẹp nhưng hiển thị nguyên văn *"☆ Chưa có đánh giá"*, không bịa đặt số sao giả. |
| **06** | `place-v2-mobile-sparse.png` | $390 \times 844$ | Dữ liệu tối thiểu: Không ảnh, không đánh giá, không địa chỉ, không giờ mở cửa, ẩn mục liên hệ/giới thiệu, khoảng cách chưa xác định. |
| **07** | `place-v2-mobile-unverified.png` | $390 \times 844$ | Địa điểm chưa xác minh nguồn: Huy hiệu cảnh báo hổ phách *"⚠ Chưa xác minh nguồn dữ liệu"*, không có huy hiệu xanh. |
| **08** | `place-v2-mobile-loading.png` | $390 \times 844$ | Trạng thái đang tải dữ liệu (Shimmer Skeleton): Khung xương xám chuyển động nhẹ nhàng từ Hero, thumbnail đến các hàng chữ. |
| **09** | `place-v2-mobile-error.png` | $390 \times 844$ | Lỗi tải toàn màn hình: Cảnh báo mất kết nối máy chủ/OSM kèm nút *"Thử lại"*. |
| **10** | `place-v2-mobile-404.png` | $390 \times 844$ | Không tìm thấy địa điểm (404 Empty State): Icon kính lúp xám, thông báo địa điểm không tồn tại kèm nút *"Quay lại Bản đồ"*. |
| **11** | `place-v2-mobile-add-trip.png` | $390 \times 844$ | Luồng Thêm vào chuyến đi - Bước 1: Bottom Sheet chọn chuyến đi trong danh sách cá nhân (Hà Nội Mùa Thu 3N2Đ). |
| **12** | `place-v2-mobile-select-day.png` | $390 \times 844$ | Luồng Thêm vào chuyến đi - Bước 2: Chọn ngày cụ thể (Ngày 1: 3 địa điểm, Ngày 2: 4 địa điểm...). |
| **13** | `place-v2-mobile-add-success.png` | $390 \times 844$ | Luồng Thêm vào chuyến đi - Bước 3: Modal xác nhận thành công rực rỡ với dấu tích xanh và 2 nút lựa chọn hành động. |
| **14** | `place-v2-mobile-navigation.png` | $390 \times 844$ | Modal xác nhận điều hướng: Hiển thị tọa độ GPS xuất phát và đích đến, mở ứng dụng Google Maps. |
| **15** | `place-v2-mobile-save-share.png` | $390 \times 844$ | Tác vụ tương tác: Thông báo toast *"Đã lưu vào Yêu thích"* phía trên và bảng chia sẻ (Zalo, Facebook, Copy link, QR) phía dưới. |
| **16** | `place-v2-desktop-rich.png` | $1440 \times 900$ | Desktop mặc định 2 cột: Cột trái $740\text{ px}$ (Ảnh Hero, Gallery, Tác vụ, Giới thiệu), Cột phải $410\text{ px}$ (Mini Map, Provenance, Wandy Tip). |
| **17** | `place-v2-desktop-gallery.png` | $1440 \times 900$ | Chế độ xem thư viện ảnh Desktop (Lightbox): Nền tối mờ, ảnh lớn trung tâm $880 \times 480\text{ px}$, mũi tên lật ảnh trái/phải, dải thumbnail đáy. |
| **18** | `place-v2-desktop-no-image.png` | $1440 \times 900$ | Desktop khi thiếu ảnh: Minh họa kiến trúc trang nhã ở cột trái. |
| **19** | `place-v2-desktop-sparse.png` | $1440 \times 900$ | Desktop dữ liệu tối thiểu: Xử lý sạch sẽ các khoảng trắng khi thiếu thông tin. |
| **20** | `place-v2-desktop-add-trip.png` | $1440 \times 900$ | Desktop Add to Trip: Modal hộp thoại căn giữa màn hình với bộ chọn chuyến đi và chọn ngày trực quan. |
| **21** | `place-v2-desktop-unverified.png` | $1440 \times 900$ | Desktop địa điểm chưa kiểm chứng: Banner cảnh báo màu hổ phách. |
| **22** | `place-v2-desktop-error.png` | $1440 \times 900$ | Desktop lỗi hệ thống: Giao diện căn giữa kèm nút thử lại. |

---

## 4. Kiểm Toán Khuyết Thiếu Hạ Tầng Media (Media Pipeline Gap Analysis)

Sau khi kiểm tra trực tiếp mã nguồn backend và cơ sở dữ liệu:
1. **Schema Prisma (`apps/backend/prisma/schema.prisma`):**
   - Bảng `Place` có trường `coverImage String?` và `images String[] @default([])`.
   - **Tuy nhiên**, chưa có bảng quan hệ chuyên biệt để lưu trữ `PlaceMedia`, `sourceId`, `license`, `attribution`, `width`, `height`.
2. **Dữ liệu hạt giống (`database/seed/places.json`):**
   - Toàn bộ 58 địa điểm trong file seed **HOÀN TOÀN KHÔNG CÓ URL HÌNH ẢNH NÀO** (`coverImage` và `images` đều null/rỗng).
3. **Pipeline dữ liệu OpenStreetMap (TASK 07.4):**
   - Chỉ thu thập các trường văn bản từ OSM Node/Way (`amenity`, `tourism`, `historic`, `name`, `opening_hours`, `website`, `phone`). Bản thân OpenStreetMap không lưu trữ file ảnh trực tiếp mà chỉ có thể liên kết qua tag `wikidata` hoặc `wikimedia_commons`.
4. **Hạ tầng lưu trữ file (CDN / Storage):**
   - Dự án chưa cấu hình dịch vụ lưu trữ media (AWS S3, Cloudinary hoặc MinIO) dành riêng cho ảnh địa điểm.
5. **KẾT LUẬN KIỂM TOÁN HẠ TẦNG:**
   $$\text{MEDIA PIPELINE} = \mathbf{MISSING\ /\ NOT\ IMPLEMENTED}$$
   - Các hình ảnh trong bộ mockup này là **DEMO VISUAL ASSETS** phục vụ mục đích duyệt thiết kế giao diện và định hình tiêu chuẩn trải nghiệm.
   - Khi chuyển sang pha lập trình tính năng thực tế, backend cần xây dựng một **Media Enrichment Ingestion Service** (ví dụ: bóc tách ảnh có bản quyền tự do từ Wikimedia Commons API dựa trên tọa độ và liên kết Wikidata của OSM).
   - Tuyệt đối không cào ảnh trái phép từ Google Maps hoặc dùng ảnh không rõ nguồn gốc/bản quyền.

---

## 5. Kiểm Toán Tính Toàn Vẹn & Không Ảnh Hưởng Mã Nguồn

| Tiêu chuẩn Kiểm toán | Trạng thái | Minh chứng kiểm chứng |
| :--- | :---: | :--- |
| **Không sửa Dart / Flutter** | PASS | `git diff apps/mobile/` trả về rỗng (0 thay đổi). |
| **Không sửa Backend / Prisma** | PASS | `git diff apps/backend/` trả về rỗng (0 thay đổi). |
| **Không sửa Database Schema** | PASS | `schema.prisma` và thư mục `database/` nguyên vẹn. |
| **Kiểm tra linter Flutter** | PASS | `flutter analyze` chạy trên `apps/mobile`: `No issues found!`. |
| **Kiểm tra bộ test hồi quy** | PASS | `flutter test` chạy trên `apps/mobile`: `All tests passed! (152/152)`. |
| **Trạng thái nhánh Git** | PASS | Đang ở nhánh `feature/gomate-visual-mockups`, không merge, không push remote. |

---

## 6. Khuyến Nghị Lộ Trình Triển Khai Tiếp Theo

1. **Review & Khóa Thiết Kế (Design Lock):** Người dùng và đội ngũ sản phẩm tiến hành duyệt bộ 22 mockup visual V2.
2. **Hoàn thành thiết kế màn hình WANDY AI (`TASK 08.2.3.4`):** Đây là màn hình cuối cùng trong chuỗi 4 màn hình cốt lõi (Home $\rightarrow$ Map $\rightarrow$ Place Detail $\rightarrow$ Wandy AI).
3. **Lập trình UI Component (Sprint sau):** Triển khai các thành phần Flutter tương thích với thiết kế V2 (`PlaceHeroGallery`, `PlaceQuickFactsBar`, `PlaceStickyActionBar`) và giữ nguyên fallback minh họa cho đến khi hoàn thiện Media Service ở backend.
