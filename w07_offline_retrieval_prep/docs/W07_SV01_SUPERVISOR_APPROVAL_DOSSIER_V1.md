# GoMate W07 — Hồ Sơ `SV-01`: Xác Nhận Phạm Vi Của Giảng Viên Hướng Dẫn (`Route 2 / OD-G15-05-AIPROXY`)

- **Mã hồ sơ:** `SV-01`
- **Trạng thái trung thực hiện tại:** **`OWNER_REPORTED_APPROVAL`**
- **Bằng chứng văn bản / chữ ký GVHD trên đĩa:** **`FALSE` (`null`)**
- **Các bản nháp đóng băng hiện có cho phép tự miễn trừ mà không có xác nhận GVHD hay không?** **`FALSE`** (tất cả tài liệu `G2A v2.0.1`, `G2B v1.1`, `Decision Note 2026-11-21` và kiểm toán `2026-11-22` / `2026-11-23` đều yêu cầu **bằng chứng xác nhận thực tế từ GVHD**; lời báo cáo miệng/chat của Owner không tự động thay thế hợp đồng chữ ký).
- **Tệp dữ liệu kiểm chứng:** [`W07_SV01_SUPERVISOR_APPROVAL_RECORD_V1.json`](W07_SV01_SUPERVISOR_APPROVAL_RECORD_V1.json) & mẫu chờ ký cho GVHD [`W07_SV01_SUPERVISOR_CONSULTATION_NOTE_ROUTE2_V1.md`](W07_SV01_SUPERVISOR_CONSULTATION_NOTE_ROUTE2_V1.md).

---

## 1. Bằng Chứng Thực Tế Trên Đĩa

1. **Báo cáo từ Project Owner (`2026-11-14`, `2026-11-22`, `2026-11-23`):** Owner xác nhận dừng gán nhãn người thật (`Route 1A/1B`) và báo cáo **GVHD đã đồng ý phương án AI-proxy (`OD-G15-05-AIPROXY`)**.
2. **Bản tham vấn gốc `W07_SUPERVISOR_NOTE.md` (lưu ngoại tuyến ngoài repo):**
   - `3,065` bytes · SHA-256 `422aa1b6bad075c785034b516a332cdfe3737c9adf3fe2ea5c9fd7b51df96da8`.
   - Là dự thảo chưa ký (`[BLANK]`), chỉ đề cập `v0.4.2` (`G2B` AI-proxy + vẫn giữ `G2A` con người).
3. **Bản tham vấn mới cho Route 2 (`[BLANK]` chờ GVHD):** [`W07_SV01_SUPERVISOR_CONSULTATION_NOTE_ROUTE2_V1.md`](W07_SV01_SUPERVISOR_CONSULTATION_NOTE_ROUTE2_V1.md) — trình bày đúng phạm vi **Zero-Human `G2A v2.0.1` + Dual-LLM `G2B v1.1` + `AI_PROXY_NOT_HUMAN`** để Owner gửi GVHD xác nhận nhanh nếu cần.

---

## 2. Hai Lộ Trình Hợp Lệ Để Mở Cổng `SV-01` (Không Giả Mạo Chữ Ký)

1. **`SV01-A` (Đúng đúng hợp đồng các bản nháp đóng băng — Khuyến nghị):** Owner gắn minh chứng xác nhận thực tế của GVHD (email, ảnh chụp tin nhắn phản hồi, hoặc bản [`W07_SV01_SUPERVISOR_CONSULTATION_NOTE_ROUTE2_V1.md`](W07_SV01_SUPERVISOR_CONSULTATION_NOTE_ROUTE2_V1.md) có xác nhận + ngày) và cập nhật `supervisor_approval_status = "SUPERVISOR_WRITTEN_VERIFIED"`.
2. **`SV01-B` (Chỉ khi ChatGPT Auditor + Owner chủ động phê chuẩn thêm điều khoản sửa luật miễn trừ `SV-01`):** Bởi luật đóng băng hiện tại **không có sẵn điều khoản tự miễn trừ**, `validate_route2_authorization_bundle()` chỉ mở khóa không cần file ký của GVHD nếu cả **hai** cờ sau được phê chuẩn rõ ràng: `explicit_frozen_rule_sv01_waiver_amendment_ratified = true` VÀ `owner_reported_supervisor_waiver_accepted_by_audit_and_owner = true`, đồng thời khóa cứng mọi kết luận đầu ra dưới nhãn `AI_PROXY_NOT_HUMAN`.
