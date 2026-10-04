# GoMate — Master UX Architecture Blueprint (v1.0)

**Tài liệu:** Kiến trúc Trải nghiệm Người dùng Tổng thể (Master UX Architecture)  
**Phiên bản:** 1.0.0  
**Ngày ban hành:** 2026-10-04  
**Trạng thái:** Baseline Chính thức cho Thiết kế & Phát triển (Chỉ định kiến trúc, không redesign giao diện)  
**Phạm vi:** Ứng dụng du lịch đa nền tảng GoMate (Mobile / Tablet / Web)  

---

## 1. Tầm nhìn Sản phẩm & Định vị Cốt lõi

GoMate là nền tảng du lịch thông minh bản địa hóa cho thị trường Việt Nam, tích hợp:
- Trợ lý AI du lịch tương tác thời gian thực (**Wandy Copilot**) dựa trên RAG (Retrieval-Augmented Generation).
- Bản đồ tương tác dữ liệu mở (**OpenStreetMap**) với 357+ địa điểm đã xác minh thực tế, tính toán khoảng cách Haversine chuẩn tại thiết bị.
- Công cụ lập kế hoạch hành trình thông minh (**AI Trip Planner**) ràng buộc ngân sách và lịch trình tất định (deterministic arithmetic).
- Hệ thống định vị người dùng thực tế với Quality Gate kiểm soát sai số và minh bạch dữ liệu.
- Trung tâm thông tin an toàn du lịch (**Safety Center**).

### Lời hứa Trải nghiệm (Product Promise)
> *"Người dùng chia sẻ mong muốn du lịch; GoMate thấu hiểu ngữ cảnh, tra cứu dữ liệu địa điểm thực tế đã kiểm chứng, lập kế hoạch chi tiết minh bạch ngân sách, và bảo đảm an toàn trên mọi chặng đường."*

---

## 2. 12 Nguyên tắc Thiết kế UX Cốt lõi (GoMate UX Principles)

1. **Một hành động chính trên mỗi màn hình (One Primary Action Per Screen):** Mỗi trạng thái giao diện chỉ nhấn mạnh duy nhất một Primary CTA rõ ràng. Các hành động phụ sử dụng Secondary/Tertiary/Ghost buttons.
2. **Tiết lộ lũy tiến (Progressive Disclosure):** Hiển thị trước những thông tin thiết yếu nhất (Tên, Thể loại, Khoảng cách, Đánh giá trung thực); các thông tin chi tiết sâu (Giờ mở cửa, Liên hệ, Nguồn dữ liệu ODbL, Tọa độ) chỉ mở rộng khi người dùng chủ động yêu cầu.
3. **Nội dung thuần Việt tự nhiên (Vietnamese-First Content):** Toàn bộ nhãn, thông báo, hướng dẫn, trạng thái lỗi đều sử dụng tiếng Việt chuẩn mực, có dấu, biểu đạt ấm áp, tôn trọng và chuyên nghiệp.
4. **Nguồn gốc dữ liệu minh bạch (Clear Data Provenance):** Mọi địa điểm, đánh giá và khuyến nghị đều phải rõ nguồn gốc (OpenStreetMap, Wikivoyage). Người dùng luôn thấy nhãn "Nguồn: OpenStreetMap" kèm liên kết kiểm chứng ODbL.
5. **Tuyệt đối không bịa đặt dữ liệu thiếu (Never Fabricate Missing Information):** Khi địa điểm chưa có đánh giá $\rightarrow$ hiển thị *"Chưa có đánh giá"*; chưa có giờ mở cửa $\rightarrow$ *"Chưa có thông tin giờ mở cửa"*; chưa có địa chỉ $\rightarrow$ *"Chưa có thông tin địa chỉ"*. Tuyệt đối không sinh số sao giả (4.5☆) hay địa chỉ ghép tạm bợ.
6. **Định vị minh bạch và dễ hiểu (Location Understandability):** Công khai rõ ràng sai số định vị bằng mét (`±X m`). Differentiate rõ giữa GPS chính xác cao ($\le 50\text{m}$) và vị trí mạng/Wi-Fi ước lượng ($50\text{m} - 200\text{m}$). Không bao giờ đánh lừa người dùng rằng định vị trình duyệt là GPS tuyệt đối.
7. **AI có căn cứ thực tế (Grounded AI with Source Disclosure):** Mọi câu trả lời của Wandy Copilot về dữ liệu sự thật phải trích dẫn nguồn bằng các thẻ chip (`Wikivoyage`, `OpenStreetMap`). Khi thiếu dữ liệu, AI thừa nhận trung thực thay vì bịa đặt (hallucination).
8. **Điều hướng bảo toàn ngữ cảnh (Context-Preserving Navigation):** Khi chuyển tab, xem Place Detail rồi bấm quay lại, hoặc mở Wandy: bản đồ phải giữ nguyên góc nhìn, mức zoom, bộ lọc danh mục và tọa độ định vị. Không bao giờ reload/reset dữ liệu ngoài ý muốn.
9. **Thông báo lỗi có hướng khắc phục (Actionable Error Recovery):** Không chỉ thông báo lỗi chung chung; luôn cung cấp phương án xử lý cụ thể (ví dụ: *"Quyền vị trí bị từ chối"* đi kèm nút *"Mở cài đặt"*).
10. **Hạn chế tối đa Pop-up / Dialog chen ngang:** Ưu tiên Modal Bottom Sheet, Inline Feedback và Status Pill tự tắt sau 5s thay vì các hộp thoại Modal Dialog chặn dòng tương tác.
11. **Khu vực chạm thoải mái (Touch Target Ergonomics):** Mọi nút bấm, chip lọc, icon tương tác đều đạt kích thước tối thiểu $44 \times 44\text{ dp}$ (chuẩn WCAG 2.1 AA).
12. **Giảm thiểu tải nhận thức (Minimize Cognitive Load):** Phân nhóm thông tin rõ ràng qua Card, Spacing chuẩn ($4\text{dp} - 8\text{dp} - 16\text{dp} - 24\text{dp}$), màu sắc ngữ nghĩa đồng nhất theo Design System tokens.

---

## 3. Ngôn ngữ & Phong cách Thiết kế (Style Direction)

- **Tươi sáng & Thân thiện (Bright & Approachable):** Sử dụng nền sạch (`#F8FAFC`), tông màu chính Teal/Primary (`#0D9488` / `#0F766E`) mang lại cảm giác an tâm, khám phá thiên nhiên và hiện đại.
- **Trầm tĩnh & Tin cậy (Calm & Trustworthy):** Hạn chế các hiệu ứng màu sắc lòe loẹt hoặc cảnh báo đỏ không cần thiết. Trạng thái cảnh báo dùng Amber (`#D97706`), thông tin dùng Soft Blue (`#0284C7`).
- **Hiện đại & Bản địa (Modern Vietnamese Character):** Typography rõ ràng, dễ đọc trên di động (Inter / Roboto), sử dụng từ ngữ du lịch Việt gần gũi (*Khám phá, Bản đồ, Chuyến đi, An toàn, Lập lịch trình*).
- **AI-Native nhưng thực tế:** Wandy xuất hiện như người đồng hành chu đáo (avatar Wandy, gợi ý thông minh, trích dẫn nguồn), không đóng khung như một chatbot cứng nhắc.

---

## 4. Mô hình Trạng thái Giao diện Đồng nhất (Unified UI State Model)

Mọi màn hình và thành phần dữ liệu trong GoMate phải tuân theo 9 trạng thái giao diện chuẩn:

| Trạng thái | Định nghĩa & Ý nghĩa UX | Thành phần hiển thị chuẩn |
| :--- | :--- | :--- |
| **Initial** | Trạng thái ban đầu trước khi kích hoạt tác vụ hoặc tải dữ liệu. | Skeleton mờ hoặc Empty placeholder trung tính. |
| **Loading** | Đang tải dữ liệu từ API / Đang chạy AI generation. | `AppLoading` spinner, Skeleton Shimmer, thanh tiến trình có ước lượng thời gian. |
| **Success** | Dữ liệu tải thành công, đầy đủ và hợp lệ. | Danh sách thẻ, Marker bản đồ, Chi tiết địa điểm, Tin nhắn phản hồi. |
| **Empty** | Tác vụ thành công nhưng không có kết quả phù hợp. | `AppEmptyState` với hình minh họa, thông báo nhã nhặn và gợi ý hành động tiếp theo. |
| **Error** | Lỗi kết nối mạng, lỗi 500 server hoặc lỗi định dạng. | `AppErrorState` với mô tả lỗi thân thiện bằng tiếng Việt và nút bấm "Thử lại". |
| **PermissionRequired** | Tính năng cần quyền hệ thống trước khi thực thi. | Hộp thoại hoặc banner giải thích lý do cần quyền (Ví dụ: quyền định vị để tính khoảng cách). |
| **PermissionDenied** | Người dùng đã từ chối cấp quyền hệ thống. | Status pill thông báo + SnackBar có nút CTA dẫn trực tiếp đến Cài đặt hệ thống. |
| **Unavailable** | Dịch vụ không khả dụng (GPS tắt, thiết bị không hỗ trợ). | Trạng thái dự phòng trung thực (Ví dụ: *"Khoảng cách chưa xác định"*). |
| **Offline** | Mất kết nối Internet hoàn toàn. | Banner thông báo mất mạng ở đỉnh màn hình, cho phép sử dụng dữ liệu đã lưu trong cache. |

---

## 5. Bản đồ Bộ Tài liệu Kiến trúc UX (Documentation Map)

Kiến trúc UX của GoMate được chi tiết hóa qua 6 tài liệu chuyên biệt:

1. **[gomate-information-architecture.md](file:///d:/Do_an/wanderai/docs/design/gomate-information-architecture.md):**  
   Cấu trúc phân cấp thông tin sản phẩm, phân định Screen Types (Root, Pushed Detail, Bottom Sheet, Overlays, Reusable Components) và quy tắc lưu trữ state.
2. **[gomate-user-flows.md](file:///d:/Do_an/wanderai/docs/design/gomate-user-flows.md):**  
   Đặc tả chi tiết 10 luồng người dùng cốt lõi (FLOW 01 đến FLOW 10) từ điểm chạm đầu vào, mục đích, hành động chính/phụ, đến xử lý loading/lỗi/hủy/quay lại.
3. **[gomate-screen-specification.md](file:///d:/Do_an/wanderai/docs/design/gomate-screen-specification.md):**  
   Đặc tả chi tiết từng màn hình (11 màn hình từ A đến K) với đầy đủ 13 thuộc tính kiến trúc chuẩn.
4. **[gomate-interaction-specification.md](file:///d:/Do_an/wanderai/docs/design/gomate-interaction-specification.md):**  
   Quy tắc vi tương tác, chính sách điều khiển Camera bản đồ, vòng sai số vị trí, vòng đời status pill, streaming Wandy, và modal lập lịch trình.
5. **[gomate-responsive-specification.md](file:///d:/Do_an/wanderai/docs/design/gomate-responsive-specification.md):**  
   Đặc tả hành vi tương thích đa màn hình: Mobile (<720px), Tablet (720–1199px), Desktop (≥1200px), giới hạn max-width, side panels và tương tác con trỏ.
6. **[task-08.2.1-ux-architecture-audit.md](file:///d:/Do_an/wanderai/docs/audit/ui/task-08.2.1-ux-architecture-audit.md):**  
   Báo cáo kiểm định đối chiếu hiện trạng code Flutter với kiến trúc mục tiêu, danh mục nợ kỹ thuật và kế hoạch lộ trình triển khai.

---

## 6. Nguyên tắc Kiểm soát & Chống thoái lui (Non-Regression Principles)

- **Không tái sinh lỗi "GlobalKey":** Giữ nguyên kiến trúc `RouterNotifier` với persistent root/shell navigator keys trong `app_router.dart`.
- **Không tái sinh lỗi giật Camera:** Bản đồ chỉ di chuyển camera khi người dùng chủ động bấm "Vị trí của tôi", không giật khi chọn POI hoặc quay về từ trang chi tiết.
- **Không tái sinh lỗi mất dữ liệu POI:** Bấm định vị người dùng không bao giờ được phép re-query tâm bản đồ làm biến mất các địa điểm du lịch đã tải.
- **Không tái sinh dữ liệu giả:** Giữ nghiêm ngặt quy tắc rating `null` hiển thị *"Chưa có đánh giá"* và địa chỉ thiếu hiển thị *"Chưa có thông tin địa chỉ"*.
