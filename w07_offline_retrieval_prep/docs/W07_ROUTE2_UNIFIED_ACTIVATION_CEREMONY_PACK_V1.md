# W07 Route 2 — Gói Kích Hoạt Thống Nhất & Tiền Kiểm Trực Tuyến (`HOLD` Cho Tới Khi Đủ Ký Số & API Keys)

- **Phiên bản chuẩn hóa:** `W07-ROUTE2-AIPROXY-HARMONIZED-V1.1`
- **Thư mục gói kích hoạt hợp nhất:** [`docs/route2_activation_pack/`](route2_activation_pack/ACTIVATION_PACK_INDEX.json)
- **Công cụ khởi tạo / kiểm chứng:** [`scripts/provision_route2_activation_ceremony.py`](../scripts/provision_route2_activation_ceremony.py)
- **Trạng thái hiện tại:** **`UNSIGNED_HOLD_PENDING_OWNER_GVHD_AUDITOR_PROVISIONING`** (`0` chữ ký giả, `0` boolean tự bật, `0` live API calls, `$0.00` chi phí).

## 1. Thành Phần Gói Kích Hoạt (`docs/route2_activation_pack/`)

| Tệp trong gói | Nội dung & Trạng thái trung thực | Điều kiện mở khóa hợp lệ |
|---|---|---|
| `bundle.json` | Schema `GOMATE_W07_ROUTE2_AIPROXY_BUNDLE_V1_1`, khóa mặc định `PA-1` (`UNAMENDED_20USD`: `$20.00` tổng / `$2.00` DEV), toàn bộ cờ mở khóa đang `false` | Gắn kèm bộ biên lai Ed25519 hợp lệ bên ngoài repo |
| `sv01_record.json` | Giữ trung thực `OWNER_REPORTED_APPROVAL`, `supervisor_written_evidence_on_disk = false` (chưa giả lập văn bản/chữ ký GVHD) | Đính kèm bằng chứng viết của GVHD (`SV01-A`) hoặc ngoại lệ đồng ký `Owner + Auditor` (`SV01-B`) khóa nhãn `AI_PROXY_NOT_HUMAN` |
| `od_ae_05_data_rights_commitment.json` | Khóa chỉ gửi Tier-`T1` sanitized `V` (`046424e5...`), cấm `S` gốc/`R_AUDIT`/`T0`/`T2`/PII, ghi rõ lưu trữ 29 ngày non-ZDR của Anthropic Batch + xóa bắt buộc sau tải | Owner ký số `od_ae_05_receipt.json` xác nhận điều khoản 29 ngày & S/V |
| `external_trust_root_spec.json` | Trỏ ngoài repo tại `C:/ProgramData/GoMate_W07_Owner_Trust_Root` (cấm symlink/reparse point), hiện `provisioned = false` | Owner tạo `trust_root_manifest.json` + khóa công khai Ed25519 thật ngoài repo |
| `provider_preflight_status.json` | Ghi nhận thực tế `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` đều đang **UNSET**, snapshot & giá thương mại tài khoản **chưa xác minh sống**, khóa trần `PA-1 <= $20 / DEV <= $2` | Cấp API key, chạy `run_authorized_provider_preflight_probes()` xác nhận `GET /v1/models` + `count_tokens()` `< 100K` và ký `provider_preflight_receipt.json` |
| `receipts/*.unsigned.json` | Mẫu 5 biên lai tách miền Ed25519 (`*_detached_signature_hex = null`) cho Owner & Independent Auditor | Chỉ thay bằng `receipts/*.json` đã ký bởi khóa thật khi được cấp phép |

## 2. Chốt Cổng Trước Live Adapter

- Entrypoint thực tế `validate_route2_live_activation_entrypoint()` & `verify_live_account_preflight_prerequisites()` **không nhận `_test_only_trusted_*_pubkey_hex`**, chặn mọi khóa giả từ môi trường và từ chối vượt trần `PA-1 ($20 tổng / $2 DEV)` hoặc động vào `FINAL-50`.
- Cho tới khi Audit `PASS` + Owner/GVHD hoàn tất ký số và cung cấp API key thực tế, `live_execution_authorized` luôn là `false` (`7` blockers).
