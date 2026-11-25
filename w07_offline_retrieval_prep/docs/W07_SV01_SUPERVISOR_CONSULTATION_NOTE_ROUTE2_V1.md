# Đề Nghị Giảng Viên Hướng Dẫn Xác Nhận Phạm Vi Đánh Giá W07 (`Route 2 — OD-G15-05-AIPROXY / Zero-Human AI-Proxy`)

- **Đề tài / Kho lưu trữ:** `GoMate / WanderAI` (`do_an_2026` / `namnh102/wanderai`)
- **Tình trạng văn bản:** **`[BLANK — MẪU XIN XÁC NHẬN CHƯA KÝ]`** — KHÔNG tự điền, KHÔNG thay thế chữ ký hay bằng chứng thực tế.
- **Kế thừa & cập nhật từ:** `W07_SUPERVISOR_NOTE.md` (bản tham vấn `v0.4.2` ngoại tuyến trước đây chưa bao gồm `G2A` Zero-Human).

---

## 1. Bối Cảnh & Lý Do Xin Xác Nhận `Route 2` (`OD-G15-05-AIPROXY`)

1. `Protocol v1.0` (`5056c5c2...`) yêu cầu bộ 50 câu hỏi `FINAL-50` do người độc lập biên soạn/thẩm định (`G2A`) và `2` người gán nhãn + `1` trọng tài (`G2B`, `50 × 137 × 2 = 13,700` lượt chấm).
2. Nhóm đồ án hiện **không có đủ nhân sự và quỹ thời gian** để tổ chức gán nhãn thủ công (`Route 1A/1B` đã dừng theo quyết định Project Owner).
3. Toàn bộ thành phần khoa học lõi **được giữ nguyên 100% không thay đổi**:
   - `137` tài liệu Arm P & `60` POI đóng băng; làm sạch `R_AUDIT` (`46/46` tags -> `V`); `STUB-01..05 PASS` theo `Annex v0.2.2` (`e78013fd...`).
   - `6` hệ truy xuất CPU local (`C0/C1 × BM25/Dense/RRF`), ma trận `5 × 3` (`50` câu hỏi, `40` answerable + `10` unanswerable `S5`), `5` tương phản `K1..K5` (`PCG64`, bootstrap `95% CI`, Holm `alpha = 0.05`), và khóa **`G5 = HOLD`**.

---

## 2. Phạm Vi Điều Chỉnh Đề Xuất (`G2A v2.0.1` + `G2B v1.1` Hợp Nhất)

- **`G2A` (Zero-Human Proxy):** Dừng biên soạn/thẩm định thủ công; tách hai tiến trình độc lập:
  - `G2A-1`: Sinh câu hỏi mù hoàn toàn với corpus (chỉ nhận danh sách `60` POI an toàn, lọc trùng `>= 8` token với `V`).
  - `G2A-2`: Tự động kiểm chứng trích dẫn nguyên văn trên tài liệu chuẩn `S` mù hoàn toàn với kết quả xếp hạng `G3` (`S1..S4`) và quét đủ `137/137` tài liệu cho `S5`.
  - Gắn nhãn bắt buộc: `question_origin = "AI_GENERATED_NO_HUMAN_REVIEW"`, `human_ground_truth = false`.
- **`G2B` (Dual-LLM Blind Proxy Judging, `ORDER_A` `50 × 137 = 6,850` cặp/judge = `13,700` lượt):** Dùng `2` mô hình khác họ (`gpt-6-luna` + `claude-haiku-5-5`) chấm mù bất biến hạng, kiểm tra đảo thứ tự prompt (`>= 0.90`, `κ_w >= 0.75`), đồng thuận liên họ (`κ_w_AB >= 0.40`), `delta_min >= +0.030`, không cưỡng bức `NA/ERROR`. Nếu không đạt -> **`NO_CLEAR_PROXY_WINNER`**.
- **Giới hạn tuyên bố khoa học bắt buộc trong khóa luận:** Báo cáo rõ **`AI_PROXY_NOT_HUMAN`** và **`HumanGraded-GoMate-nDCG@10 = NOT_PERFORMED`**; kết quả phản ánh so sánh retrieval bằng AI-proxy có kiểm chứng trích dẫn/thứ tự, không phải ground truth con người hay chứng nhận an toàn sinh văn bản (`G5`).

---

## 3. Phần Xác Nhận Của Giảng Viên Hướng Dẫn (`[BLANK — CHỜ GVHD]`)

- `[ ]` **Đồng ý phương án `Route 2` (`OD-G15-05-AIPROXY`: Zero-Human `G2A v2.0.1` + Dual-LLM `G2B v1.1`)** với nhãn `AI_PROXY_NOT_HUMAN` và `G5 = HOLD`.
- `[ ]` **Đồng ý có điều kiện / yêu cầu chỉnh sửa:** `______________________________`
- `[ ]` **Không đồng ý AI-proxy; yêu cầu quay lại gán nhãn người thật (`Protocol v1.0` / `Route 1B`).**

- **Hình thức xác nhận (Email / Tin nhắn / Chữ ký biên bản):** `[BLANK]`
- **Họ tên GVHD:** `[BLANK]`
- **Ngày xác nhận:** `[BLANK]`
- **Mã SHA-256 gói tham chiếu (`W07_ROUTE2_AIPROXY_HARMONIZED_DECISION_PACK_V1.md`):** `08f19d1aea80b280ed58647f4c688df08410845d3e90da19b97c375f92c49f85`
