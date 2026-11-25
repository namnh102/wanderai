# GoMate W07 Route 2 — Runbook Một Lượt Sau Khi ChatGPT Audit `PASS` Amendment 02

- **Tài liệu sửa đổi chờ kiểm toán:** [`W07_ROUTE2_AUDITOR_ATTESTATION_AND_SV01B_AMENDMENT_V1.md`](W07_ROUTE2_AUDITOR_ATTESTATION_AND_SV01B_AMENDMENT_V1.md) (`HOLD` cho tới khi có artifact JSON-only `PASS` riêng cho từng pha theo schema `GOMATE_W07_INDEPENDENT_AUDIT_VERDICT_V1`).
- **Ngân sách Owner đã duyệt vs Operational Subcap:** Owner duyệt khung W07 **`$40.00` tổng / cảnh báo `$36.00` / DEV-5 `<= $2.00`**; subcap vận hành tạm thời `PA-1` là **`<= $20.00` tổng / `<= $2.00` DEV-5** cho tới khi có chữ ký ràng buộc `Budget40`. `OD-AE-05` Tier-T1 `V` + Anthropic 29 ngày non-ZDR + xóa bắt buộc, `SV-01B` khóa nhãn `AI_PROXY_NOT_HUMAN`.

---

## Trình Tự Chủ Dự Án Thực Thi Sau Khi ChatGPT Cấp `PASS` (Artifact JSON-Only Riêng Cho Từng Pha)

*(Báo cáo Markdown chỉ dùng để đọc. Owner chỉ nạp các tệp JSON thuần `.json` khớp schema `GOMATE_W07_INDEPENDENT_AUDIT_VERDICT_V1` vào `--auditor-verdict-json`.)*

### Bước 1 — Nạp API Keys an toàn vào Windows DPAPI Vault ngoài mọi Repo
```powershell
cd <W07_PREP_ROOT>
python scripts/route2_stage1_activation_session.py secret-import-dotenv --dotenv-path <WANDERAI_REPO_ROOT>/apps/ai-service/.env
python scripts/route2_stage1_activation_session.py secret-status
```

### Bước 2 — Sinh khóa Ed25519 Owner ngoài repo & Ký Phase 1 (`PRE_PREFLIGHT_PROBE_ONLY`, dùng `PHASE1_VERDICT.json`)
*(Artifact Phase 1 bắt buộc có `authorized_stage="PRE_PREFLIGHT_PROBE_ONLY"`, `scope=["PRE_PREFLIGHT_PROBE_ONLY"]`, `stage1_dev_canary_decision="HOLD"`, `bound_preflight_artifacts=null`.)*
```powershell
python scripts/route2_stage1_activation_session.py owner-init-keypair --out-dir C:\GoMate_Owner_Private_Keys

python scripts/route2_stage1_activation_session.py ceremony-sign-phase1 `
  --owner-pem C:\GoMate_Owner_Private_Keys\owner_ed25519_private.pem `
  --trust-root-dir C:\ProgramData\GoMate_W07_Owner_Trust_Root `
  --auditor-verdict-mode AI_AUDIT_TEXT_OWNER_ATTESTED `
  --auditor-verdict-json C:\GoMate_Owner_Private_Evidence\CHATGPT_PHASE1_PREFLIGHT_VERDICT.json `
  --target-audit-zip-sha256 <CORRECTION_ZIP_SHA256> `
  --sv01-waiver-ratified `
  --accept-anthropic-29day-retention
```
*(Ghi lại 3 mã pin in ra trong `out_of_band_pins`: `owner_pubkey_sha256`, `auditor_report_sha256` (= `phase1_auditor_report_sha256`), `trust_root_manifest_sha256`.)*

### Bước 3 — Chạy `PRE_PREFLIGHT_PROBE_ONLY` (Đo `GET /v1/models` + `count_tokens`, `0` batch có phí, giữ `live_account_rates_verified=false`)
```powershell
python scripts/route2_stage1_activation_session.py run-preflight-probe `
  --trust-root-dir C:\ProgramData\GoMate_W07_Owner_Trust_Root `
  --oob-owner-sha256 <OWNER_PIN> `
  --oob-auditor-report-sha256 <PHASE1_VERDICT_SHA256> `
  --oob-manifest-sha256 <MANIFEST_PIN> `
  --allow-live-network
```

### Bước 4 — Xin Phán Quyết Phase 2 Riêng (`PHASE2_VERDICT.json` gắn preflight + rate evidence) & Ký `STAGE1_DEV_CANARY_ONLY`
*(Không được tái sử dụng `PHASE1_VERDICT.json`. `PHASE2_VERDICT.json` phải có `authorized_stage="STAGE1_DEV_CANARY_ONLY"`, `scope=["STAGE1_DEV_CANARY_ONLY"]`, `stage1_dev_canary_decision="GO"`, và `bound_preflight_artifacts` chứa đủ `raw_probe_transcript_sha256`, `provider_preflight_status_sha256`, `rate_evidence_sha256`, `phase1_auditor_verdict_sha256`.)*
```powershell
python scripts/route2_stage1_activation_session.py ceremony-sign-phase2 `
  --owner-pem C:\GoMate_Owner_Private_Keys\owner_ed25519_private.pem `
  --trust-root-dir C:\ProgramData\GoMate_W07_Owner_Trust_Root `
  --auditor-verdict-mode AI_AUDIT_TEXT_OWNER_ATTESTED `
  --auditor-verdict-json C:\GoMate_Owner_Private_Evidence\CHATGPT_PHASE2_STAGE1_CANARY_VERDICT.json `
  --target-audit-zip-sha256 <CORRECTION_ZIP_SHA256> `
  --rate-evidence-json C:\GoMate_Owner_Private_Evidence\provider_rate_evidence.json `
  --sv01-waiver-ratified `
  --oob-owner-sha256 <OWNER_PIN> `
  --oob-auditor-report-sha256 <PHASE2_VERDICT_SHA256> `
  --oob-manifest-sha256 <MANIFEST_PIN>
```
Gửi `docs/route2_activation_pack/raw_probe_transcript.json`, `docs/route2_activation_pack/provider_preflight_status.json`, và các receipt (tuyệt đối không gửi API key hay `.pem`) cho ChatGPT để quyết định mở batch live DEV-5 `<= $2.00`.
