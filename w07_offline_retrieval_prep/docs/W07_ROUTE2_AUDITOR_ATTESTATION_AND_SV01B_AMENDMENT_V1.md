# W07 Route 2 Amendment 02 — Wire Firewall Fixes (`Prompt v1.1` / OSM Email) & Auditor Text-Verdict Binding (`HOLD` Cho Tới Khi ChatGPT Kiểm Toán `PASS`)

- **Mã Amendment:** `W07-ROUTE2-AMENDMENT-02-TEXT-VERDICT-AND-SV01B`
- **Cơ sở phê duyệt phát triển:** `OWNER_APPROVED_W07_ROUTE2_CONDITIONAL_EXECUTION` (`2026-11-23`)
- **Trạng thái hiệu lực:** **`DRAFT_IMPLEMENTATION_AWAITING_CHATGPT_INDEPENDENT_AUDIT_PASS`** (`Amendment phải được kiểm toán trước khi có hiệu lực`).

---

## 1. Bốn Điều Chỉnh Kỹ Thuật Hẹp (Không Thay Đổi Corpus, Method, `STUB-01..05` Hay Trần Ngân Sách)

1. **Miễn trừ có ghim SHA-256 cho `system_prompt` của `Prompt v1.1` (`[SP-05]`):**
   - Trong `route2_aiproxy.py`, bổ sung hằng số `PINNED_STAGE1_SYSTEM_PROMPT_V1_1_SHA256 = "b02b56d2b843b442ecb65df92b35cb30593c4e8cb154b41e67ec9efa3b6241b6"` (băm UTF-8 của trường `system_prompt` trong `W07_DEV_STATIC_PROMPT_TEMPLATE_CANDIDATE_v1_1_offset01.json`, mẫu `9d03fbce...`).
   - `assert_cloud_payload_v_boundary()` chỉ cho phép 3 tên nhãn minh họa (`[SOURCE_REPORTED_UNVERIFIED]`, `[UNVERIFIED]`, `[SUPPRESSED_FACT_CONFLICT]`) trong kênh system prompt khớp **chính xác từng byte** với SHA-256 đã ghim; vẫn chặn tuyệt đối `canonical_text_S`, `removed_r_audit`, PII email, ID nhạy cảm, `[CORROBORATED:`, miền Tier-T2 và chặn 100% mọi nhãn cấm trong kênh dữ liệu `wire_user_prompt` / prompt bị sửa dù chỉ 1 byte.
2. **Che `[REDACTED_EMAIL]` khả nghịch cục bộ trên payload cloud (`046424e5...` giữ nguyên bất biến):**
   - Trong `build_sanitized_v_cloud_request_payload()`, các địa chỉ khớp `CLOUD_EMAIL_PII_RE` (hỗ trợ đầy đủ NFC/NFD Unicode ở cả local-part lẫn domain, ví dụ `một@example.com`, `abc@quán.vn`, `hòa@nhà-hàng.vn`) trong `sanitized_text_V` được thay trên kênh truyền cloud thành `[REDACTED_EMAIL]`; mọi token `@` bất thường chưa được che sẽ bị `UNRESOLVED_AT_EMAIL_FALLBACK_RE` chặn fail-closed ở cả `count_tokens` lẫn batch payloads.
   - Ánh xạ phân đoạn `safe_to_v_segments` giữ chính xác tuyệt đối tọa độ ký tự trên toàn bộ phần văn bản còn lại (`safe_doc_v -> V -> canonical_text_S`) và từ chối fail-closed mọi trích dẫn giao cắt `[REDACTED_EMAIL]`. Tệp corpus đóng băng `137` docs (`V = 046424e5...`) và `canonical S` hoàn toàn không thay đổi.
3. **Chế độ biên lai `AI_AUDIT_TEXT_OWNER_ATTESTED` với artifact JSON-only nghiêm ngặt & tách pha tuyệt đối (không parse Markdown/văn xuôi, không giả chữ ký ChatGPT):**
   - Nhãn chế độ chính thức là **`AI_AUDIT_TEXT_OWNER_ATTESTED`** kèm nhãn nguồn chữ ký **`OWNER_ATTESTED_AI_TEXT_NOT_AUDITOR_ED25519`** (tuyệt đối không sinh khóa/chữ ký Ed25519 giả cho ChatGPT: `auditor_ed25519_pubkey_hex = null`, `auditor_detached_signature_hex = null`).
   - **Báo cáo Markdown chỉ để con người đọc, không bao giờ là dữ liệu cấp quyền**; hệ thống **không** dùng regex/blacklist văn xuôi. Artifact cấp quyền bắt buộc là tệp **JSON thuần (`.json`)** đơn khối, không trùng khóa (`object_pairs_hook`), không hằng số `NaN/Infinity`, đúng đủ 11 khóa của schema `GOMATE_W07_INDEPENDENT_AUDIT_VERDICT_V1`.
   - **Tách riêng phán quyết Phase 1 và Phase 2 (chống leo thang quyền):**
     - **Phase 1 (`PRE_PREFLIGHT_PROBE_ONLY`):** `authorized_stage = "PRE_PREFLIGHT_PROBE_ONLY"`, `scope = ["PRE_PREFLIGHT_PROBE_ONLY"]`, `pre_preflight_probe_decision = "GO"`, `stage1_dev_canary_decision = "HOLD"`, `final_50_authorized = false`, `bound_preflight_artifacts = null`. Tuyệt đối không thể dùng artifact Phase 1 để mở `STAGE1_DEV_CANARY_ONLY`.
     - **Phase 2 (`STAGE1_DEV_CANARY_ONLY` / `STAGE1_LIVE`):** bắt buộc artifact JSON riêng biệt mới (`auditor_report_sha256 != phase1_auditor_verdict_sha256`) có `authorized_stage = "STAGE1_DEV_CANARY_ONLY"`, `scope = ["STAGE1_DEV_CANARY_ONLY"]`, `stage1_dev_canary_decision = "GO"`, `final_50_authorized = false`, và `bound_preflight_artifacts` khớp chính xác 4 mã SHA-256: `raw_probe_transcript_sha256`, `provider_preflight_status_sha256`, `rate_evidence_sha256`, `phase1_auditor_verdict_sha256` (gắn chặt với kết quả preflight và các receipt tương ứng).
   - Khớp `auditor_report_sha256` trên đĩa, out-of-band pin `out_of_band_auditor_report_sha256`, đúng `amendment_id`, đúng `target_zip_sha256`, đồng thời chặn replay mọi báo cáo/ZIP đã bị bác (`FORBIDDEN_PRIOR_PRE_AMENDMENT_AUDIT_SHA256S`, `REJECTED_PRIOR_AUDIT_ZIP_SHA256S` gồm cả `36d541c6...` và `a77a9345...`).
4. **Quyết định của Owner đối với `SV-01B` (`AI_PROXY_NOT_HUMAN`) & Bằng chứng giá Stage-2 (`--rate-evidence-json`):**
   - Khi không có văn bản GVHD (`SV01-A`), `sv01_resolution_receipt.json` theo `SV-01B` khóa `epistemic_label_locked = "AI_PROXY_NOT_HUMAN"`, mang chữ ký Ed25519 của Owner gắn cùng `auditor_report_sha256` đã được ChatGPT nghiệm thu `PASS` (tuyệt đối không giả chữ ký GVHD hay chữ ký Ed25519 của Auditor).
   - Ở pha `PRE_PREFLIGHT_PROBE_ONLY`, probe chỉ xác minh `model_snapshot_id` và `count_tokens`, giữ trung thực `live_account_rates_verified = false` (`account_pricing_status = "UNVERIFIED_CALLER_ESTIMATE_ONLY"`). Trước khi ký `STAGE1_LIVE` (`Phase 2`), bắt buộc cung cấp `--rate-evidence-json` (`GOMATE_W07_PROVIDER_RATE_EVIDENCE_V1`) có timestamp UTC, URL chính thức, SHA-256 tài liệu giá và xác nhận Owner để gắn vào `provider_preflight_receipt.json`.

---

## 2. Khung Ngân Sách Owner Phê Duyệt & Điều Kiện Kích Hoạt

- **Khung ngân sách Owner đã phê duyệt cho W07:** **`$40.00` tổng / cảnh báo sớm `$36.00` / trần cứng DEV-5 `<= $2.00`**.
- **Operational subcap `PA-1` (`UNAMENDED_20USD`):** **`$20.00` tổng / `<= $2.00` DEV-5** đóng vai trò operational subcap tạm thời cho tới khi có `Budget40` signed binding (`budget40_signed_activation_binding_verified = true`, `budget40_signed_binding_sha256`).
- `OD-AE-05`: chỉ gửi Tier-T1 `V` (đã che email Unicode/ASCII), chấp thuận lưu 29 ngày non-ZDR của Anthropic Batch kèm `DELETE` bắt buộc sau tải.
- Không kích hoạt cho tới khi **ChatGPT kiểm toán độc lập `PASS` cho gói Correction này**, sau đó Owner lưu báo cáo `PASS` mới, nhập API keys vào DPAPI vault, ký Trust Root ngoài repo và chạy `PRE_PREFLIGHT_PROBE_ONLY`.
