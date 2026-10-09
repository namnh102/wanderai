# GoMate — Place Detail Screen Visual Specification (V2 / R1)

**Tài liệu:** Đặc tả Thiết kế Thị giác & Trải nghiệm Đa phương tiện Màn hình Chi tiết Địa điểm (GoMate Place Detail Visual Enrichment & Media Design Specification)  
**Phiên bản:** 2.0.0 (Bám sát 100% Bộ Design Master Board do User phê duyệt)  
**Ngày ban hành:** 2026-10-05  
**Nhánh Git:** `feature/gomate-visual-mockups`  
**Trạng thái:** Authoritative Visual Specification Baseline (P0 Place Detail V2)  
**Mục tiêu kết nối:** Khám phá (Discovery) $\rightarrow$ Thêm vào chuyến đi (Add to Trip) $\rightarrow$ Chỉ đường (Navigation)

---

## 1. Triết Lý Thiết Kế & Thứ Bậc Trực Quan (Theo Bản Mẫu Chuẩn)

Màn hình Chi tiết Địa điểm V2 tái hiện chính xác cấu trúc giao diện chuẩn hóa của GoMate từ bảng tổng hợp thiết kế:
$$\text{PLACE PHOTO HERO} \rightarrow \text{IDENTITY & BADGE} \rightarrow \text{RATING & TABS} \rightarrow \text{GIỚI THIỆU} \rightarrow \text{INFO CARDS} \rightarrow \text{MINI MAP} \rightarrow \text{STICKY ACTIONS}$$

### Thành phần giao diện cốt lõi (Mobile $390 \times 844\text{ px}$):
1. **Khối Hero Photo:**
   - Chiều cao: $230\text{ px}$, ảnh phong cảnh du lịch độ nét cao $16:9$.
   - Nút điều hướng nổi: Nút quay lại tròn màu trắng `←` ở góc trên trái; hai nút tròn màu trắng `♡` (Lưu yêu thích) và `↗` (Chia sẻ) ở góc trên phải.
   - Chỉ số ảnh: Huy hiệu viên thuốc tối mờ `1/8` ở góc dưới phải của ảnh.
2. **Khối Nhận diện Địa điểm:**
   - Dòng tiêu đề: Tên địa điểm `Chùa Trấn Quốc` ($22\text{ px}$ bold 800) đặt song song với huy hiệu `✓ Đã xác minh` (nền xanh lá nhạt `#E6F4EA`, viền `#CEEAD6`, chữ xanh đậm `#137333`, bo góc $6\text{ px}$).
   - Dòng phụ: `Văn hóa` · `📍 Hà Nội` · `2.4 km từ bạn` (chữ xám `#64748B`, khoảng cách GPS màu teal `#0F766E` đậm).
   - Dòng đánh giá: Năm ngôi sao vàng `★★★★★` + `4.6` bold + `(128 đánh giá)` (hoặc `☆☆☆☆☆ Chưa có đánh giá` khi vắng mặt dữ liệu).
3. **Thanh Tab Phân Đoạn (Segmented Sub-navigation Tabs):**
   - 4 tab điều hướng con: `[Tổng quan]` (Tab kích hoạt với đường kẻ viền đáy teal $2\text{ px}$), `[Hình ảnh]`, `[Đánh giá]`, `[Gần đây]`.
4. **Nội dung Tab Tổng quan:**
   - Đoạn văn bản giới thiệu ngắn gọn: *"Chùa Trấn Quốc là một trong những ngôi chùa cổ nhất tại Hà Nội và Việt Nam với lịch sử hơn 1500 năm, tọa lạc trên một bán đảo phía đông của Hồ Tây..."*.
   - Liên kết mở rộng: `Xem thêm` (màu teal `#0F766E` bold).
5. **Cặp Thẻ Thông Tin Nhanh (Side-by-Side Quick Info Cards):**
   - **Thẻ 1 (Giờ mở cửa):** Chiều rộng $48\%$, nền `#F8FAFC`, viền $1\text{ px}$ `#E2E8F0`, bo góc $12\text{ px}$, icon `🕒 Giờ mở cửa` + nội dung `07:30 – 17:30`.
   - **Thẻ 2 (Địa chỉ):** Chiều rộng $48\%$, nền `#F8FAFC`, viền $1\text{ px}$ `#E2E8F0`, bo góc $12\text{ px}$, icon `📍 Địa chỉ` + nội dung `Đường Thanh Niên, Tây Hồ, Hà Nội`.
6. **Bản đồ Thu nhỏ (Mini Map Preview):**
   - Khung bản đồ $90\text{ px}$ bo góc $12\text{ px}$, sử dụng gạch OpenStreetMap Humanitarian (HOT), ghim vị trí Chùa Trấn Quốc trên đảo Kim Ngư giữa Hồ Tây.
7. **Thanh Tác Vụ Dính Đáy (Sticky Action Bar):**
   - Cố định ở đáy màn hình, cao $68\text{ px}$, nền trắng viền trên $1\text{ px}$ `#E2E8F0`.
   - Nút thứ cấp: `+ Thêm vào chuyến đi` (nền `#E6FFFA` / `#CCFBF1`, chữ `#0F766E`, viền `#99F6E4`, bo góc $10\text{ px}$, cao $44\text{ px}$).
   - Nút chính: `🧭 Chỉ đường` (nền `#0F766E`, chữ trắng, bo góc $10\text{ px}$, cao $44\text{ px}$).

---

## 2. Quy Trình Thêm Địa Điểm Vào Chuyến Đi (Add to Trip Flow)

Giao diện tái hiện chính xác 3 bước trong bản thiết kế:
- **Bước 1: Chọn chuyến đi (Màn hình 4.1 / 5):**
  - Bottom Sheet trượt lên với tiêu đề `Chọn chuyến đi` và nút đóng `✕`.
  - Danh sách thẻ chuyến đi dạng radio:
    - Thẻ 1 (Đang chọn): Thumbnail ảnh + `Hà Nội 3N2Đ Mùa Thu` / `15/10 - 17/10/2026 · 3 ngày` + dấu tích xanh `✓` trong vòng tròn teal. Viền thẻ $2\text{ px}$ teal `#0F766E`.
    - Thẻ 2: Thumbnail ảnh + `Khám phá Phố Cổ & Ẩm thực` / `24/10/2026 · 1 ngày`.
    - Thẻ 3: Thumbnail ảnh + `Hà Giang Mùa Hoa Tam Giác Mạch` / `10/11 - 14/11/2026 · 5 ngày`.
  - Nút thêm mới: `+ Tạo chuyến đi mới` (viền đứt nét teal).
  - Nút tiếp tục: `Tiếp tục (Chọn ngày) →` (nền teal `#0F766E`, chữ trắng, cao $44\text{ px}$).
- **Bước 2: Chọn ngày trong chuyến đi (Màn hình 4.2 / 6):**
  - Tiêu đề: `Chọn ngày trong chuyến đi` kèm banner tóm tắt chuyến đi (`Hà Nội 3N2Đ Mùa Thu`).
  - Danh sách chọn ngày:
    - `Ngày 1` (15/10/2026 · 3 địa điểm): Đang chọn với viền teal và dấu tích xanh `✓`.
    - `Ngày 2` (16/10/2026 · 5 địa điểm).
    - `Ngày 3` (17/10/2026 · 2 địa điểm).
  - Hai nút điều khiển đáy: `Quay lại` (nút phụ xám) và `Thêm vào ngày 1` (nút chính teal).
- **Bước 3: Xác nhận thành công (Màn hình 4.3 / 7):**
  - Hộp thoại modal xuất hiện giữa màn hình với vòng tròn xanh lục lớn chứa dấu tích `✓` và hiệu ứng pháo hoa chúc mừng.
  - Tiêu đề: `Đã thêm vào chuyến đi!`
  - Nội dung: `Chùa Trấn Quốc đã được thêm vào Hà Nội 3N2Đ Mùa Thu · Ngày 1 (15/10/2026)`.
  - Hai nút hành động: `🗺 Xem chuyến đi` (nền ngọc lam nhạt `#E6FFFA`, chữ teal `#0F766E`) và `Tiếp tục khám phá` (nút viền trắng).

---

## 3. Các Trạng Thái Phụ Trợ Chuẩn Hóa

- **Bảng Tùy Chọn Lưu / Chia Sẻ (Màn hình 8):**
  - Dòng 1: `❤️ Lưu địa điểm` / `Lưu vào danh sách yêu thích` + mũi tên `›`.
  - Dòng 2: `🔗 Chia sẻ địa điểm` + mũi tên `›`.
  - Dòng 3: `📋 Sao chép liên kết` / `https://gomate.app/places/123` + icon copy `❐`.
  - Nút `Hủy` màu xám ở đáy.
- **Trạng Thái Lỗi (Màn hình 9):**
  - Biểu tượng đám mây mất kết nối màu xanh lam trong vòng tròn nhạt.
  - Tiêu đề `Không thể tải thông tin`, phụ đề `Vui lòng kiểm tra kết nối và thử lại.`.
  - Hai nút bấm: `Thử lại` (nền teal) và `Về bản đồ` (nền xám).
- **Trạng Thái Không Tìm Thấy Địa Điểm (Màn hình 10):**
  - Biểu tượng kính lúp màu đỏ với dấu hỏi `?`.
  - Tiêu đề `Không tìm thấy địa điểm`, phụ đề `Địa điểm này có thể đã bị xóa hoặc không còn tồn tại.`.
  - Nút bấm: `Quay lại bản đồ`.
- **Thư Viện Ảnh Toàn Màn Hình (Màn hình 1.4):**
  - Nền đen tuyền điện ảnh `#0B0F19`.
  - Thanh trên: nút quay lại `←`, chỉ số `1 / 6` ở giữa, nút chia sẻ `↗` ở bên phải.
  - Ảnh lớn trung tâm, thanh thumbnail cuộn ngang ở chân màn hình.

---

## 4. Ma Trận Dữ Liệu Trung Thực (Data Honesty)

| Trường dữ liệu | Có sẵn trong DB / OSM | Vắng mặt (Null) | Hành vi giao diện |
| :--- | :--- | :--- | :--- |
| **Ảnh đại diện** | Render ảnh phong cảnh $16:9$ | `coverImage == null` | Render fallback minh họa kiến trúc + *"Chưa có hình ảnh"* |
| **Đánh giá** | `★★★★★ 4.6 (128 đánh giá)` | `rating == null` | Render trung thực: `☆☆☆☆☆ Chưa có đánh giá` |
| **Khoảng cách** | Tính Haversine từ GPS thiết bị | Chưa có GPS fix | Hiển thị: `Khoảng cách chưa xác định` |
| **Địa chỉ** | Đường Thanh Niên, Tây Hồ, Hà Nội | `address == null` | Hiển thị: `📍 Chưa có thông tin địa chỉ.` |
| **Giờ mở cửa** | `07:30 – 17:30` | `openingHours == null` | Hiển thị: `Chưa có thông tin giờ mở cửa.` |
| **Xác minh** | `isVerified == true` | `isVerified == false` | Hiển thị huy hiệu hổ phách: `⚠ Chưa xác minh nguồn` |
