# GoMate — Responsive Layout & Accessibility Specification

**Tài liệu:** Đặc tả Tương thích Đa Màn hình & Khả năng Tiếp cận (Responsive & Accessibility Specification)  
**Phiên bản:** 1.0.0  
**Ngày ban hành:** 2026-10-04  
**Phạm vi:** Hành vi bố cục trên Mobile, Tablet, Desktop và các chuẩn tiếp cận WCAG 2.1 AA cho GoMate  

---

## 1. Phân cấp Điểm ngắt Màn hình (Breakpoint Hierarchy)

GoMate phân chia hệ thống hiển thị thành 3 bậc điểm ngắt (Breakpoints) rõ ràng:

| Phân khúc Thiết bị | Dải chiều rộng (Width) | Tỷ lệ Thiết bị Điển hình | Trọng tâm Trải nghiệm |
| :--- | :--- | :--- | :--- |
| **Mobile (Điện thoại)** | $< 720\text{ dp}$ | iPhone 13/14/15, Pixel 7/8, Galaxy S23 (360–430dp) | Tối ưu ngón tay cái (Thumb zone), 1 cột, Bottom Nav, Bottom Sheet trượt. |
| **Tablet (Máy tính bảng / Foldable)** | $720\text{ dp} - 1199\text{ dp}$ | iPad Mini, iPad 10.2", Surface Duo, Galaxy Tab | Lưới 2 cột, Max-width trung tâm, Modal nổi, Bottom Nav mở rộng. |
| **Desktop / Web Rộng** | $\ge 1200\text{ dp}$ | Laptop 13–15", Màn hình ngoài Full HD / 2K | Bố cục đa cột / Side panel, Max-width $800\text{dp}$ cho nội dung đọc, chuột & bàn phím. |

---

## 2. Quy tắc Bố cục & Giới hạn Chiều rộng (Max-Width Container Rules)

Một trong những vấn đề nghiêm trọng trên giao diện Web trước đây là nội dung bị kéo giãn toàn bộ màn hình khiến khoảng trắng mênh mông, khó đọc. GoMate giải quyết triệt để thông qua widget chuẩn `ResponsiveWrapper`:

```text
[                   Desktop Viewport (1440px)                   ]
|                                                               |
|         [=========== Responsive Container ===========]        |
|         |           Max Width: 640px / 720px         |        |
|         |   (Nội dung tập trung, dễ đọc, cân đối)   |        |
|         [============================================]        |
|                                                               |
```

### 2.1 Giới hạn Chiều rộng theo Loại Màn hình
- **Màn hình Nội dung Đọc & Form (`HomeScreen`, `PlaceDetailScreen`, `TripDetailScreen`):**
  - Giới hạn tối đa: $720\text{ dp}$.
  - Căn giữa (Center alignment) tự động với khoảng đệm lề trái/phải tối thiểu $16\text{ dp}$.
- **Khung Chat Wandy Copilot (`AiChatScreen`):**
  - Giới hạn tối đa: $720\text{ dp}$. Khung chat và thanh nhập liệu được giữ ở trung tâm tầm mắt, giúp người dùng không phải đảo mắt sang hai bên màn hình lớn.
- **Màn hình Bản đồ (`MapScreen`):**
  - Lớp bản đồ nền: Mở rộng $100\%$ chiều rộng màn hình để tận dụng tối đa không gian địa lý.
  - Các thành phần điều khiển nổi (Thanh tìm kiếm, Thanh chip danh mục, Huy hiệu số lượng): Được bọc trong `ResponsiveWrapper` với `maxWidth: 720px` căn giữa phía trên bản đồ.
- **Form Đăng nhập / Đăng ký (`AuthScreens`):**
  - Giới hạn tối đa: $420\text{ dp}$ căn giữa chính giữa màn hình (Card nổi trên nền xám nhẹ).

---

## 3. Hành vi Thành phần Giao diện theo Breakpoint

### 3.1 Thanh Điều hướng Chính (Navigation Architecture)
- **Mobile (<720dp):**
  - `NavigationBar` nằm ở đáy màn hình (Bottom Navigation Bar) gồm 5 icon và nhãn văn bản.
  - Chiều cao chuẩn: $64\text{ dp}$ (cộng thêm SafeArea đáy).
- **Tablet (720–1199dp):**
  - Vẫn sử dụng `NavigationBar` ở đáy nhưng được giới hạn chiều rộng trong `maxWidth: 720px` căn giữa, tạo cảm giác như một dock điều khiển thanh lịch.
- **Desktop (≥1200dp - Hướng phát triển):**
  - Tùy chọn chuyển đổi sang `NavigationRail` bên trái màn hình hoặc giữ Dock đáy căn giữa.
  - Các mục điều hướng có tooltip hiển thị tên khi rê chuột.

### 3.2 Tấm Trượt Ngữ cảnh (Modal Sheets & Dialogs)
- **Mobile:**
  - `showModalBottomSheet` trượt từ đáy màn hình, chiều rộng $100\%$, bo góc trên $20\text{ dp}$.
  - Có thanh kéo (drag handle) trực quan để vuốt xuống đóng.
- **Tablet & Desktop:**
  - Tự động chuyển đổi thành Modal Dialog nổi ở trung tâm màn hình hoặc Bottom Sheet có `maxWidth: 560px` bo tròn 4 góc.
  - Luôn có nút đóng (x) rõ ràng ở góc trên bên phải để người dùng click chuột đóng dễ dàng.

### 3.3 Lưới Thẻ Điểm đến & Chuyến đi (Card Grids)
- **Mobile:** 1 cột duy nhất cho danh sách chuyến đi; băng chuyền cuộn ngang cho điểm đến.
- **Tablet:** Lưới 2 cột (`crossAxisCount: 2`, tỉ lệ 1.4:1).
- **Desktop:** Lưới 3 cột (`crossAxisCount: 3`), có hiệu ứng đổ bóng nhẹ khi rê chuột (Hover Elevation).

---

## 4. Tương tác Cảm ứng vs Con trỏ Chuột (Touch vs Pointer Interaction)

| Khía cạnh Tương tác | Trên Thiết bị Cảm ứng (Touch) | Trên Máy tính / Web (Pointer & Mouse) |
| :--- | :--- | :--- |
| **Cử chỉ cuộn / lướt** | Vuốt ngón tay tự nhiên, quán tính mượt mà. | Con lăn chuột (Scroll wheel) hoặc kéo thanh cuộn. |
| **Phản hồi khi rê (Hover)** | Không có hiệu ứng hover; phản hồi ngay khi chạm (`onTapDown`). | Màu nền đổi sắc thái nhẹ ($5\%$), con trỏ chuyển sang hình bàn tay (`click`). |
| **Thao tác trên Bản đồ** | Dùng 2 ngón tay để chụm/mở zoom, xoay bản đồ. | Cuộn chuột để zoom, giữ chuột trái và rê để di chuyển bản đồ. |
| **Nhập liệu văn bản** | Bàn phím ảo hệ điều hành tự trồi lên đẩy nội dung. | Bàn phím vật lý; phím Enter để gửi tin nhắn hoặc kích hoạt tìm kiếm. |

---

## 5. Chuẩn mực Khả năng Tiếp cận Toàn diện (Accessibility Standards)

GoMate cam kết tuân thủ các hướng dẫn tiếp cận nội dung web và ứng dụng di động **WCAG 2.1 cấp độ AA**.

### 5.1 Diện tích Vùng Chạm Tối thiểu (Touch Target Ergonomics)
- Mọi nút bấm, icon action, chip lọc danh mục và ô chọn đều có kích thước tối thiểu:
  $$44\text{ dp} \times 44\text{ dp}$$
- Khoảng cách an toàn giữa hai thành phần tương tác kề nhau: tối thiểu $8\text{ dp}$ để tránh chạm nhầm.

### 5.2 Độ Tương phản Màu sắc (Color Contrast Ratios)
- **Văn bản thông thường (Regular Text):** Tỉ lệ tương phản tối thiểu $4.5 : 1$ so với màu nền.
  - Chữ chính (`AppColors.textPrimary` `#0F172A`) trên nền trắng (`#FFFFFF`): Tỉ lệ $15.8 : 1$ (Vượt chuẩn AAA).
  - Chữ phụ (`AppColors.textSecondary` `#64748B`) trên nền trắng: Tỉ lệ $4.6 : 1$ (Đạt chuẩn AA).
- **Văn bản lớn & Thành phần Giao diện (Large Text & UI Components):** Tỉ lệ tương phản tối thiểu $3.0 : 1$.
  - Nút Primary (`#0D9488`) với chữ trắng: Tỉ lệ $4.7 : 1$ (Đạt chuẩn AA).
  - Viền ô nhập liệu (`#CBD5E1`): Rõ ràng, dễ phân biệt.

### 5.3 Không truyền đạt thông tin duy nhất bằng màu sắc (Non-Color Indicators)
- Trạng thái thành công / cảnh báo / lỗi luôn kết hợp cả **Màu sắc + Biểu tượng + Nhãn văn bản rõ ràng**.
- Ví dụ:
  - Vị trí chính xác: Màu xanh lam + Icon `check_circle` + Nhãn *"Đã xác định vị trí · ±25 m"*.
  - Vị trí ước lượng: Màu hổ phách + Icon `help_outline` + Nhãn *"Vị trí ước lượng · ±180 m"*.
  - Địa điểm xác minh: Màu xanh ngọc + Icon `verified` + Nhãn *"Đã xác minh"*.

### 5.4 Điều hướng Bàn phím & Trạng thái Tiêu điểm trên Web (Keyboard Navigation & Focus)
- Người dùng có thể duyệt toàn bộ ứng dụng bằng phím `Tab`, `Shift+Tab`, `Space` và `Enter`.
- Khi một thành phần nhận tiêu điểm (Focus), xuất hiện viền sáng màu Primary dày $2\text{ dp}$ với offset $2\text{ dp}$ (`FocusRing`).
- Hỗ trợ phím tắt:
  - `Escape`: Đóng tấm Preview Sheet hoặc Modal Dialog đang mở.
  - `Enter`: Gửi tin nhắn trong khung chat Wandy.

### 5.5 Nhãn Ngữ nghĩa cho Trình đọc Màn hình (Screen Reader & Semantics)
- Toàn bộ các icon đơn lẻ (nút Vị trí, nút Gửi, nút Back) đều được gán thuộc tính `Semantics(label: "...", button: true)`.
- Marker trên bản đồ có nhãn ngữ nghĩa: `Semantics(label: "Địa điểm $name, thể loại $category, khoảng cách $distance")`.
- Các ảnh địa điểm có thuộc tính `excludeFromSemantics: false` và mô tả văn bản thay thế ngắn gọn.
