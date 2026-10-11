# GoMate — Micro-Interactions & Motion Specification

**Tài liệu:** Đặc tả Vi tương tác, Chuyển động & Trạng thái Phản hồi (Interaction Specification)  
**Phiên bản:** 1.0.0  
**Ngày ban hành:** 2026-10-04  
**Phạm vi:** Các quy chuẩn vi tương tác, chính sách camera bản đồ, vòng đời thành phần và cử chỉ tương tác trong GoMate  

---

## 1. Chính sách Điều khiển & Chuyển động Camera Bản đồ (Map Camera Motion Policy)

Hành vi camera trên bản đồ là một trong những điểm nhạy cảm nhất đối với trải nghiệm người dùng du lịch. GoMate đặt ra các quy định nghiêm ngặt để đảm bảo sự ổn định và tránh gián đoạn góc nhìn.

### 1.1 Nguyên tắc "Không giật màn hình ngoài ý muốn" (Zero Unexpected Camera Jump)
- **Khi mở màn hình Bản đồ:** Camera giữ nguyên góc nhìn mặc định tại trung tâm Hà Nội (`21.0285, 105.8542`). Bản đồ tuyệt đối **không tự động recenter** sang vị trí người dùng trừ khi người dùng chủ động bấm nút định vị.
- **Khi chạm vào Marker POI:** Camera **đứng yên hoàn toàn**. Tấm `PlacePreviewSheet` trượt lên từ đáy; camera không được phép giật nhảy sang tâm marker được chọn.
- **Khi quay lại từ Màn hình Chi tiết (Place Detail):** Camera giữ nguyên 100% tọa độ tâm và mức zoom trước đó.

### 1.2 Hiệu ứng Lướt êm ái khi bấm "Vị trí của tôi" (Smooth Recentering Animation)
- **Thời lượng chuyển động:** $250\text{ ms}$.
- **Đường cong chuyển động (Easing Curve):** `Curves.easeInOutCubic`.
- **Quy tắc Mức Zoom (Zoom Preservation Policy):**
  - Nếu mức zoom hiện tại của người dùng đã cận cảnh ($\ge 14.0$): Giữ nguyên mức zoom hiện tại, chỉ lướt tâm camera về tọa độ người dùng.
  - Nếu mức zoom hiện tại đang ở góc nhìn bao quát ($< 14.0$): Lướt tâm camera về tọa độ người dùng đồng thời phóng to cận cảnh lên mức $15.0$ để người dùng thấy rõ các địa điểm xung quanh.
- **Mã cài đặt chuẩn (Flutter):**
  ```dart
  void _animatedMoveTo(LatLng destLocation, double destZoom) {
    final latTween = Tween<double>(begin: _mapController.camera.center.latitude, end: destLocation.latitude);
    final lngTween = Tween<double>(begin: _mapController.camera.center.longitude, end: destLocation.longitude);
    final zoomTween = Tween<double>(begin: _mapController.camera.zoom, end: destZoom);

    final controller = AnimationController(duration: const Duration(milliseconds: 250), vsync: this);
    final animation = CurvedAnimation(parent: controller, curve: Curves.easeInOutCubic);

    controller.addListener(() {
      _mapController.move(
        LatLng(latTween.evaluate(animation), lngTween.evaluate(animation)),
        zoomTween.evaluate(animation),
      );
    });
    controller.forward();
  }
  ```

---

## 2. Vòng đời & Vi tương tác Nút Định vị (Location Button Lifecycle)

Nút "Vị trí của tôi" (`my_location_button`) là một nút nổi tròn ($48 \times 48\text{ dp}$) phản ánh 6 trạng thái rõ ràng thông qua màu sắc và biểu tượng từ GoMate Design System:

| Trạng thái | Biểu tượng | Màu sắc Icon | Màu nền | Ý nghĩa trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **Idle** | `Icons.my_location` | `AppColors.textSecondary` (Xám) | `AppColors.surface` | Trạng thái nghỉ, chưa xác định vị trí. |
| **Requesting** | `CircularProgressIndicator` | `AppColors.primary` (Teal) | `AppColors.surface` | Đang truy vấn GPS / quét Wi-Fi (1-2s). |
| **Success (Good)** | `Icons.my_location` | `AppColors.info` (Xanh lam `#0284C7`) | `AppColors.surface` | Đã có vị trí chính xác cao ($\le 50\text{m}$). |
| **Approximate** | `Icons.location_searching` | `AppColors.warning` (Hổ phách `#D97706`) | `AppColors.surface` | Vị trí mạng / ước lượng ($50\text{m} - 200\text{m}$). |
| **Denied** | `Icons.location_disabled` | `AppColors.error` (Đỏ `#EF4444`) | `AppColors.surface` | Quyền vị trí bị chặn; nhắc mở cài đặt. |
| **Unavailable** | `Icons.location_off` | `AppColors.textTertiary` (Xám mờ) | `AppColors.surface` | GPS thiết bị đang tắt hoặc mất sóng. |

---

## 3. Vòng đời & Tương tác Status Pill (Location Status Pill Lifecycle)

Status Pill là viên thuốc thông báo nhỏ gọn ($32\text{dp}$ chiều cao) xuất hiện phía trên nút định vị để giải thích nhanh trạng thái:

- **Nội dung nhãn:**
  - `Đã xác định vị trí · ±25 m` (kèm icon `check_circle` xanh lam).
  - `Vị trí ước lượng · ±180 m` (kèm icon `help_outline` màu vàng).
  - `Vị trí chưa chính xác` (kèm icon `warning_amber`).
  - `Quyền vị trí bị từ chối` (kèm icon `block` màu đỏ).
  - `Không xác định được vị trí` (kèm icon `error_outline`).
- **Quy tắc Biến mất Tự động (Auto-Dismiss):**
  - Trạng thái thành công (`good` / `approximate`): Tự động mờ dần và biến mất sau $5.0\text{ giây}$.
  - Trạng thái từ chối / lỗi: Duy trì hiển thị cho đến khi người dùng thao tác tiếp.
- **Cử chỉ Chạm để Đóng (Tap-to-Dismiss):**
  - Người dùng có thể chạm trực tiếp vào viên thuốc bất cứ lúc nào để đóng nó ngay lập tức.
  - Khi chạm, hiệu ứng co nhỏ nhẹ (scale 0.95) rồi biến mất trong $150\text{ ms}$.

---

## 4. Tương tác Lớp Vòng tròn Sai số & Marker Người dùng

- **Vòng tròn Sai số (`CircleLayer`):**
  - Bán kính: Bằng đúng `accuracyMeters` (sử dụng thuộc tính `useRadiusInMeter: true` của FlutterMap).
  - Màu sắc: `AppColors.info.withValues(alpha: 0.12)`.
  - Đường viền: `AppColors.info.withValues(alpha: 0.35)` với độ dày $1.5\text{ dp}$.
  - Thứ tự lớp (Z-index): Nằm **dưới** lớp marker POI; không che khuất các địa điểm xung quanh.
- **Marker Điểm tròn Xanh (`user_location_marker`):**
  - Điểm tròn chính giữa: Đường kính $16\text{ dp}$, màu xanh lam `AppColors.info`, có viền trắng dày $2.5\text{ dp}$ và quầng tỏa sáng nhẹ (Halo radius: $24\text{ dp}$, `alpha: 0.25`).
  - **Quy tắc Tránh chặn Tương tác (Non-blocking Tap):** Marker người dùng và vòng tròn sai số được bọc trong `IgnorePointer(ignoring: true)` để đảm bảo khi người dùng chạm vào một địa điểm nằm gần chấm xanh, sự kiện chạm luôn ưu tiên kích hoạt chọn địa điểm du lịch.

---

## 5. Tương tác Thanh Lọc Danh mục & Dọn dẹp Preview Sheet

- **Thanh Chip lọc Danh mục (`_CategoryChipBar`):**
  - Lựa chọn đơn (Single-select): Tại một thời điểm chỉ chọn duy nhất 1 danh mục (*Tất cả* hoặc một danh mục cụ thể).
  - Chạm chip: Chip đang chọn đổi sang màu nền Primary đậm (`#0D9488`), chữ trắng; các chip khác có viền mỏng và chữ xám đậm.
  - Cuộn ngang tự động: Khi chạm một chip ở rìa màn hình, thanh cuộn tự động canh chỉnh đưa chip đó vào vùng nhìn rõ.
- **Quy tắc Dọn dẹp Trạng thái Cũ (Stale State Clearing):**
  - Khi tấm `PlacePreviewSheet` đang mở mà người dùng bấm sang một chip thể loại khác (ví dụ từ *Văn hóa* sang *Nhà hàng*): Tấm preview của địa điểm cũ **ngay lập tức được đóng lại sạch sẽ**, tránh tình trạng hiển thị địa điểm không thuộc thể loại mới chọn.

---

## 6. Tương tác Trích dẫn Nguồn & Hội thoại Wandy AI

- **Bong bóng suy nghĩ (Typing Indicator):**
  - Trong lúc đợi API AI Service trả về, xuất hiện 3 chấm nhảy nhịp nhàng với chu kỳ $1.2\text{ s}$.
  - Nút gửi tin nhắn chuyển sang biểu tượng dừng (hoặc spinner nhỏ mờ).
- **Thẻ chip trích dẫn nguồn (`SourceChip`):**
  - Kích thước nhỏ gọn ($28\text{dp}$ chiều cao), bo tròn $8\text{dp}$, nền xám nhạt (`#F1F5F9`), viền mỏng.
  - Biểu tượng OpenStreetMap (lá cây) hoặc Wikivoyage (la bàn).
  - Chạm vào chip: Hiển thị hiệu ứng sóng nước nhẹ (Ripple effect), sau đó mở URL nguồn kiểm chứng trong trình duyệt ngoài an toàn (`LaunchMode.externalApplication`).
  - Xử lý link dài: Nhãn nguồn tự động cắt gọn bằng dấu ba chấm (`overflow: TextOverflow.ellipsis`), không gây tràn màn hình (`RenderFlex overflow`).

---

## 7. Tương tác Lập lịch trình AI (AI Planner Preview & Apply)

- **Cửa sổ Tiến trình Xử lý (~30s):**
  - Hiển thị hộp thoại Modal Dialog với thông báo: *"Wandy đang phân tích địa điểm và cân đối ngân sách..."*.
  - Có thanh tiến trình chạy đều đặn và thông báo thời gian ước tính để người dùng yên tâm chờ đợi.
  - Có nút *"Hủy"* cho phép người dùng dừng tác vụ bất kỳ lúc nào mà không gây treo ứng dụng.
- **Tấm trượt Xem trước Lịch trình (`AiPlannerPreviewSheet`):**
  - Vuốt trượt từ đáy màn hình, người dùng có thể kéo lên để xem toàn bộ các ngày hoặc kéo nhẹ xuống để đóng.
  - Bấm nút *"Áp dụng vào chuyến đi"*:
    - Nếu chuyến đi chưa có hoạt động nào: Áp dụng ngay lập tức, đóng sheet và hiển thị thông báo thành công.
    - Nếu chuyến đi đã có sẵn hoạt động cũ: Xuất hiện hộp thoại cảnh báo: *"Chuyến đi đã có lịch trình. Bạn có chắc chắn muốn ghi đè bằng lịch trình mới từ AI không?"* với 2 nút: *"Hủy bỏ"* và *"Ghi đè lịch trình"*.
- **Hoàn tác Lịch trình:** Mọi hành vi xóa hoặc chỉnh sửa mục lịch trình đều đi kèm thanh SnackBar thông báo với nút *"Hoàn tác"* (Undo) hiển thị trong $4.0\text{ giây}$.

---

## 8. Chuẩn mực Ergonomics & Vùng Chạm (Touch Target & Feedback)

- **Kích thước Vùng chạm Tối thiểu:** Tất cả các thành phần tương tác (nút bấm, chip lọc, icon điều hướng, marker bản đồ) đều có diện tích chạm tối thiểu $44 \times 44\text{ dp}$ (khuyến nghị $48 \times 48\text{ dp}$).
- **Trạng thái Phản hồi Xúc giác & Thị giác:**
  - **Hover (Web / Desktop):** Màu nền đậm lên 5% khi rê chuột, con trỏ đổi sang hình bàn tay (`SystemMouseCursors.click`).
  - **Pressed (Mobile / Web):** Hiệu ứng InkSplash / Ripple phản hồi ngay dưới ngón tay khi chạm.
  - **Disabled:** Độ mờ giảm xuống $40\%$, con trỏ đổi sang `SystemMouseCursors.forbidden`, không phát sinh sự kiện click.
