# GOMATE W07 FAST-TRACK — GÓI QUYẾT ĐỊNH & KHẮC PHỤC KỸ THUẬT `OD-G15-05-AIPROXY` (ROUTE 2 — ZERO-HUMAN AI-PROXY)

- **Phiên bản hợp nhất thống nhất:** **`W07-ROUTE2-AIPROXY-HARMONIZED-V1.1`** (đồng bộ 100% qua mọi mã nguồn, bundle `GOMATE_W07_ROUTE2_AIPROXY_BUNDLE_V1_1`, và readiness report `GOMATE_W07_ROUTE2_ACTIVATION_READINESS_REPORT_V1_1`)
- **Ngày cập nhật:** `2026-11-23`
- **Quyết định của Project Owner:** Dừng hoàn toàn `Route 1A/1B` (không tuyển người gán nhãn thủ công), kích hoạt chuẩn bị **`OD-G15-05-AIPROXY (Route 2)`**.
- **Trạng thái cổng thực thi hiện tại:** **`HOLD`** (`$0.00` chi phí API; `0` live call khi còn `HOLD`; `0` `FINAL-50`; `STUB-01..05` giữ nguyên `PASS`; `G5 = HOLD_NOT_AUTHORIZED_BY_THIS_AMENDMENT`; `W08 = NOT_OPEN`)
- **Bàn giao kiểm toán:** `HANDOFF: READY_FOR_CHATGPT_W07_ROUTE2_DEV5_ACTIVATION_AUDIT`

---

## 1. Tài Liệu Baseline Đóng Băng Giữ Nguyên Bất Biến

- `Protocol v1.0` (`5056c5c2373ee9584b8850ba49411160cc2c382ad6315aaada4c05fb9b0030c2`)
- `Technical Annex v0.2.2` (`e78013fd4abae98c39ce287a8ae9ed2b6b68fee91d91360f07ecc91c67eee940`, `STUB-01..05 PASS`, MiniLM tokenizer `2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8`)
- `60` POIs đóng băng (`3a065165d038f300f5dc422180fcaf3cef265ac1a100ea8e841daaba1a82d5d4`), `137` docs Arm P (`97` B1B `9b0ed36e...` + `40` OSM `433c722d...` / Freeze V2 `f7517938...`, view `V = 046424e5...`), Prompt `v1.1` (`9d03fbce...`), Schema `S-4` (`544062c5...`).

---

## 2. Khắc Phục Đầy Đủ Các Điểm Kiểm Toán (`P0` & `P1`) Sau Đợt Audit `2026-11-23`

1. **Ranh giới dữ liệu `S / V` nghiêm ngặt (`P0`):**
   - **Lớp gửi ra Cloud (tuyệt đối chỉ dùng `Tier-T1 sanitized V`):** Hàm `build_sanitized_v_cloud_request_payload()` và tường lửa `assert_cloud_payload_v_boundary()` trong `route2_aiproxy.py` bảo đảm mọi request gửi lên cloud (kể cả `G2A-2` và `G2B`) **CHỈ chứa `safe_doc_v` được thoát delimiter từ `V`** + `packet_item_uuid` + `query_text`. Từ chối fail-closed nếu chứa `canonical_text_S`, thẻ `[CORROBORATED:...]`, lát cắt đã xóa `removed_r_audit`, `document_id`, `poi_id`, `source_url`, `T0_PRIVATE`, miền `Tier-T2` (`tripadvisor`/`booking`/`klook`/`traveloka`/`maps.google`) hoặc email PII.
   - **Lớp kiểm tra nội bộ 100% local (`canonical S`):** Mọi phép chiếu `safe_doc_v -> V -> S` (`project_cloud_quote_locally_to_canonical_s`), đối chiếu substring trên `canonical_text_S[s_start:s_end]`, kiểm `R_AUDIT` straddling, `CE9` và `CE4` **chỉ chạy nội bộ bằng Python trên máy**, tuyệt đối không gửi `S` lên cloud.

2. **Quyền kích hoạt gắn xác thực Ed25519 & Trust Root (`P0`):**
   - Hàm `validate_route2_authorization_bundle()` **không chấp nhận cờ boolean thô** (`UNAUTHENTICATED_BOOLEAN_CLAIM_WITHOUT_CRYPTOGRAPHIC_RECEIPT`). Khi `trust_artifacts=None` hoặc thiếu `PINNED_LIVE_ROUTE2_OWNER_PUBKEY_HEX` (chưa provision external trust root), hàm luôn khóa **`live_execution_authorized = False`** ngay cả khi tất cả boolean trong JSON bị sửa thủ công thành `true`.
   - `verify_route2_cryptographic_activation_receipts()` xác thực chữ ký số **RFC 8032 Ed25519 tách miền** (`ROUTE2_TRUST_ROOT_DOMAIN_TAG`, `ROUTE2_OWNER_ACTIVATION_DOMAIN_TAG`, `ROUTE2_OD_AE_05_DOMAIN_TAG`, `ROUTE2_PROVIDER_PREFLIGHT_DOMAIN_TAG`, `ROUTE2_AUDITOR_VERDICT_DOMAIN_TAG`, `ROUTE2_SV01_EVIDENCE_DOMAIN_TAG`) trên: Trust Root ngoài workspace (không symlink), Owner Activation bound tới `bundle_sha256`, `OD-AE-05` chấp thuận lưu trữ 29 ngày non-ZDR của Anthropic Batch & xóa ngay sau chạy, kết quả đo `count_tokens()`/`live rates` (`< 100K`), Auditor Verdict `PASS`, và hồ sơ `SV-01` (`SV01-A` hoặc ngoại lệ đồng ký `SV01-B`).

3. **Hoàn thiện Stage-1 `DEV-5` Mock-Only Runner (`route2_dev_canary_runner.py`, `P0`):**
   - `run_stage1_dev_canary_mock_batch()` khóa cứng **`is_offline_mock_transport = True`** & **`allow_live_network = False`**, chỉ nhận `split == "DEV"` (`<= 5` câu hỏi, chặn mọi truy vấn `FINAL`).
   - Hỗ trợ đủ wire format **`openai` (`/v1/batches` -> `/v1/responses`), `anthropic` (`/v1/messages/batches`), `google` (`batchGenerateContent`)** đúng `AUTO-R09` + kiểm tra tường lửa `S/V` trên từng request.
   - Đầy đủ kiểm soát vận hành: `count_tokens_mock()` + chặn cliff `< 100K`, kiểm `expected_snapshot_id` chống trôi snapshot (`MODEL_SNAPSHOT_DRIFT_ABORT`), tính chi phí theo **`usage` token thực trả** dưới trần cứng **`<= $2.00`**, retry **`<= 1` lần/item** & **`<= 15%`/batch**, tối đa **`1` failed batch**, **resume idempotent** không tính phí trùng từ append-only JSONL (`fsync`), và bắt buộc gọi **`delete_batch` + `delete_file`** sau khi tải kết quả.

4. **Đồng bộ Amendment Prompt-Order Coverage (`P1`), Version ID (`V1.1`) & `G2A-1`:**
   - Thống nhất mã duy nhất **`W07-ROUTE2-AIPROXY-HARMONIZED-V1.1`** trên toàn bộ mã nguồn, JSON và tài liệu (không còn lệch V1.0/V2.0).
   - Quy định rõ chế độ kiểm tra đảo thứ tự prompt theo lấy mẫu phân tầng: **`STRATIFIED_20PCT_DEV_AUDIT`** (`137/685` = `20%` trên DEV canary) và **`STRATIFIED_200PAIR_FINAL_AUDIT`** (`200/6,850` ≈ `2.92%` trên FINAL-50). Hàm `evaluate_prompt_order_bias()` tự tính `coverage_fraction` và khóa **`full_pair_invariance_claimed = False`** khi chưa phủ `100%` cặp.
   - Làm rõ **`G2A-1`:** Stage-1 `DEV-5` dùng gói nháp `685` cặp (`9bb5de09...`, chỉ mở sau khi Owner ký local `T0` Ed25519) -> chưa cần `G2A-1`; việc chọn `G2A-1` (`grok-4.20` đang `XAI_API_KEY=UNSET` hoặc local open-weight model) được ghi là cổng chặn **`HOLD_G2A1_PROVIDER_KEY_OR_LOCAL_RUNTIME_UNSELECTED_STAGE2_ONLY`** trước Stage-2 `FINAL-50`.

---

## 3. Hai AI Judge Chính, Ngân Sách (`$20` vs `$40`) & Hồ Sơ `SV-01`

- **Hai AI Judge chọn cho `G2B`:** **`gpt-6-luna`** (`1.05M` ctx, cliff `>272K`, Batch `$0.05/$0.25`) + **`claude-haiku-5-5`** (`1M` ctx, cliff 5× **`>100K`**, Batch `$0.05/$0.25` `<=100K`, **Message Batches lưu tối đa 29 ngày & không ZDR -> cần ký `OD-AE-05` + xóa sau tải**). Mọi tài liệu `137` Arm P (tối đa `78,290` B) nằm hoàn toàn dưới ngưỡng `100K`.
- **Đối chiếu ngân sách (chỉ là dự toán trước lúc kiểm account & `count_tokens()` sống, KHÔNG phải quyền chi):**
  - **`PA-1` (Mặc định ưu tiên `<= $20.00` trần gốc):** `G2B` (`gpt-6-luna + claude-haiku-5-5` Batch `ORDER_A` `13,700` base + `200` swap) + `G2A-2` (`gemini-2.5-flash-lite` Paid Gemini Dev API Batch `$0.05/$0.20`): dự báo **`$5.4863` heuristic / `$14.0120` byte-ceiling +15% retry** (`DEV-5 + 20% swap = $0.5156 / $1.3153 <= $2.00`).
  - **`PA-2` (`Budget40 $40.00`):** Chỉ kích hoạt nếu Owner ký số `Budget-Only Delta v1.0` nâng trần lên `$40.00` (vd dùng `gemini-3.8-flash` cho `G2A-2`: **`$9.2220` / `$23.4968`**).
- **`SV-01` (`OWNER_REPORTED_APPROVAL`):** Cần minh chứng xác nhận thực của GVHD trên [`W07_SV01_SUPERVISOR_CONSULTATION_NOTE_ROUTE2_V1.md`](W07_SV01_SUPERVISOR_CONSULTATION_NOTE_ROUTE2_V1.md) (**`SV01-A`**) hoặc biên bản ngoại lệ đồng ký số giữa Project Owner + Independent Auditor (**`SV01-B`**) giữ nguyên nhãn **`AI_PROXY_NOT_HUMAN`**.

---

## 4. Product PR `#98 / #99 / #100` (Tách Biệt, Không Auto-Merge)

- `develop` = `880ce7763c3006aaf59eff8ad2e2ebd9688ca371`; PR `#98` (`243a7a97...`), PR `#99` (`19cffea7...`), PR `#100` (`b7683698...`) giữ nguyên `OPEN`, chuẩn bị audit và merge tuần tự chỉ sau khi có `PASS` và Owner authorization.

---

`HANDOFF: READY_FOR_CHATGPT_W07_ROUTE2_DEV5_ACTIVATION_AUDIT`
