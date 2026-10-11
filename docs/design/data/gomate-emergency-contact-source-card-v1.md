# GoMate Emergency Contact Directory — Authoritative Source Card V1 (R1.1 Revision)

**Status:** APPROVED REFERENCE DATA SPECIFICATION & EVIDENCE HARDENING  
**Task:** TASK 08.2.3.15-R1.1 — GOMATE SAFETY & EMERGENCY: CURRENT LEGAL BASIS, SOURCE EVIDENCE & UNKNOWN-METADATA HARDENING  
**Date:** October 5, 2026  
**Jurisdiction / Primary Scope:** Vietnam (Toàn quốc & Điểm đến du lịch trọng điểm)  
**Applicability:** GoMate V1 Client Emergency Hub & Directory  

---

## 1. Governance & Data Honesty Principle

> [!IMPORTANT]
> **Zero Fabrication Policy & Taxonomy Integrity:**
> 1. Emergency contact numbers connect travelers to life-saving and civil defense services. Fabricating, guessing, or using mock phone numbers for visual realism is **STRICTLY PROHIBITED**.
> 2. **Strict Taxonomy Separation:** Statutory emergency services (`112`, `113`, `114`, `115`) must be cleanly distinguished from social protection/welfare hotlines (`111`) and local tourism support hotlines.
> 3. **No Blanket Claims & UNKNOWN != FALSE:** Do NOT apply global "24/7" or "Miễn phí" badges across heterogeneous contact categories. Where official verified evidence is absent, attributes **MUST REMAIN `UNKNOWN`** and not be converted into speculative assertions (such as claiming a phone number is "Không miễn phí" or "Theo ca trực" without statutory source evidence).

---

## 2. Statutory National Emergency Services (Category A: Dịch Vụ Khẩn Cấp Quốc Gia)

Pursuant to Circular No. 22/2014/TT-BTTTT of the Ministry of Information and Communications (Article 9, Clause 1 on Emergency Telecommunications Numbers) and current 2025 civil defense decrees:

### 2.1. Cứu Nạn & Tình Huống Nguy Cấp Quốc Gia — 112
- **Short Dial Number:** `112`
- **Official Title:** Tổng đài tiếp nhận thông tin về sự cố, thiên tai, thảm họa, nguy cơ xảy ra và yêu cầu trợ giúp trên phạm vi toàn quốc
- **Canonical Governing Authority:** **Bộ Quốc phòng** (Bộ Quốc phòng chủ trì)
- **Coordination Note:** Liên thông với hệ thống 113, 114, 115 theo quy định hiện hành.
- **Geographic Scope:** Toàn quốc (National) — bao gồm đất liền, hải đảo, sông suối, vùng núi hiểm trở và vùng biển Việt Nam.
- **Availability:** 24/7 (`VERIFIED_24_7`)
- **Telecom Charge:** **Miễn phí cước gọi (Free call — `VERIFIED_FREE`)**
- **Canonical Semantic & Operational Scope:**
  - Tiếp nhận thông tin về:
    - Sự cố
    - Thiên tai (bão lũ, ngập lụt, sạt lở đất)
    - Thảm họa
    - Tai nạn / tình huống nguy cấp
    - Yêu cầu trợ giúp khẩn cấp của công dân và du khách trên phạm vi toàn quốc
  - Compact UI Wording: `112 · Cứu nạn & tình huống nguy cấp`
- **Current Legal Basis (Canonical Sources):**
  - **Nghị định số 200/2025/NĐ-CP** của Chính phủ: Quy định chi tiết một số điều của Luật Phòng thủ dân sự.
  - **Quyết định số 2023/QĐ-TTg ngày 15/09/2025** của Thủ tướng Chính phủ: Về việc sử dụng số điện thoại 112 tiếp nhận thông tin về sự cố, thiên tai, thảm họa, nguy cơ xảy ra và yêu cầu trợ giúp trên phạm vi toàn quốc.
  - **Quyết định số 2024/QĐ-TTg ngày 15/09/2025** của Thủ tướng Chính phủ: Ban hành Quy chế sử dụng số điện thoại 112.
  - **Thông tư số 22/2014/TT-BTTTT** của Bộ Thông tin và Truyền thông: Quy hoạch kho số viễn thông (Điều 9, Khoản 1).
- **Historical / Superseded Background:**
  - *Quyết định số 226/QĐ-TTg (2016)* của Thủ tướng Chính phủ: Phê duyệt Đề án phát triển hệ thống thông tin cứu nạn khẩn cấp (Văn bản lịch sử tạo nền móng ban đầu, đã được thay thế/hoàn thiện bằng hệ thống văn bản quy phạm pháp luật năm 2025).
- **Snapshot Date:** 2026-10-05

### 2.2. Cảnh Sát Phản Ứng Nhanh (Police & Public Security) — 113
- **Short Dial Number:** `113`
- **Official Title:** Tổng đài Cảnh sát phản ứng nhanh 113
- **Canonical Governing Authority:** **Bộ Công an**
- **Geographic Scope:** Toàn quốc (National)
- **Availability:** 24/7 (`VERIFIED_24_7`)
- **Telecom Charge:** **Miễn phí cước gọi (`VERIFIED_FREE`)**
- **Primary Source / Legal Basis:**
  - Thông tư số 22/2014/TT-BTTTT (Bộ TTTT).
  - Cổng thông tin điện tử Bộ Công an: [https://bocongan.gov.vn](https://bocongan.gov.vn)
- **Snapshot Date:** 2026-10-05
- **Operational Scope in GoMate:** Can thiệp an ninh trật tự, tội phạm, trộm cướp, bạo lực, tai nạn giao thông nghiêm trọng.

### 2.3. Cứu Hỏa & Cứu Nạn Cứu Hộ (Fire & Rescue) — 114
- **Short Dial Number:** `114`
- **Official Title:** Tổng đài Cứu nạn, Cứu hộ và Phòng cháy chữa cháy 114
- **Canonical Governing Authority:** **Cục Cảnh sát PCCC và CNCH — Bộ Công an**
- **Geographic Scope:** Toàn quốc (National)
- **Availability:** 24/7 (`VERIFIED_24_7`)
- **Telecom Charge:** **Miễn phí cước gọi (`VERIFIED_FREE`)**
- **Primary Source / Legal Basis:**
  - Luật Phòng cháy và chữa cháy; Nghị định số 136/2020/NĐ-CP; Thông tư số 22/2014/TT-BTTTT.
  - Trang thông tin điện tử Cục Cảnh sát PCCC và CNCH: [http://canhsatpccc.gov.vn](http://canhsatpccc.gov.vn)
- **Snapshot Date:** 2026-10-05
- **Operational Scope in GoMate:** Hỏa hoạn tại khách sạn/homestay, tai nạn mắc kẹt thang máy/xe khách, đuối nước tại bãi biển/hồ bơi.

### 2.4. Cấp Cứu Y Tế (Medical Emergency & Ambulance) — 115
- **Short Dial Number:** `115`
- **Official Title:** Tổng đài Cấp cứu Y tế 115
- **Canonical Governing Authority:** **Bộ Y tế** / Trung tâm Cấp cứu 115 các tỉnh, thành phố
- **Geographic Scope:** Toàn quốc (National)
- **Availability:** 24/7 (`VERIFIED_24_7`)
- **Telecom Charge:** **Miễn phí cước gọi (`VERIFIED_FREE`)**
- **Primary Source / Legal Basis:**
  - Quyết định số 01/2008/QĐ-BYT về Quy chế Cấp cứu, Hồi sức tích cực và Chống độc.
  - Cổng thông tin điện tử Bộ Y tế: [https://moh.gov.vn](https://moh.gov.vn)
- **Snapshot Date:** 2026-10-05
- **Operational Scope in GoMate:** Chấn thương nặng, ngộ độc thực phẩm cấp, đột quỵ, sốc nhiệt, tai nạn đe dọa tính mạng.

---

## 3. Emergency Number Transition Roadmap Note

> [!NOTE]
> **Sourced Integration Roadmap Note:**
> - *"Đề án tích hợp 113/114/115 đang được triển khai theo lộ trình; giai đoạn 1 đến năm 2027, giai đoạn tiếp theo 2027–2028."*
> - **Operational Reality in GoMate V1:** Throughout these stages, **112, 113, 114, and 115 remain fully operational and active concurrently**. None of these four statutory emergency services have ceased operation. GoMate presents all four numbers directly to travelers so they have instant access to specialized units.

---

## 4. National Public Safety / Protection Hotlines (Category B: Đường Dây Nóng An Sinh / Bảo Vệ Xã Hội)

### 4.1. Tổng Đài Quốc Gia Bảo Vệ Trẻ Em — 111
- **Short Dial Number:** `111`
- **Official Title:** Tổng đài Quốc gia Bảo vệ Trẻ em 111
- **Canonical Governing Authority:** **Cục Bà mẹ và Trẻ em — Bộ Y tế**
- **Geographic Scope:** Toàn quốc (National)
- **Availability:** 24/7 (`VERIFIED_24_7`)
- **Telecom Charge:** **Miễn phí cước gọi (`VERIFIED_FREE`)**
- **Primary Source / Legal Basis:**
  - Luật Trẻ em 2016; Nghị định 56/2017/NĐ-CP quy định chi tiết một số điều của Luật Trẻ em.
  - Cổng thông tin Tổng đài 111: [https://tongdai111.vn](https://tongdai111.vn)
- **Snapshot Date:** 2026-10-05
- **Operational Scope in GoMate:** Hỗ trợ khẩn cấp bảo vệ trẻ em trong chuyến đi gia đình: trẻ em bị thất lạc, tai nạn thương tích trẻ em, bạo lực, xâm hại hoặc nguy cơ tổn hại sức khỏe tâm lý/thể chất.

---

## 5. Destination Tourist Support Hotlines (Category C: Đường Dây Nóng Du Khách Địa Phương)

### 5.1. TP. Đà Nẵng (Đà Nẵng Visitor Support Center)
- **Current Primary Hotline:** `*8899` *(Số định tuyến ngắn tiếp nhận hỗ trợ du khách được công bố trong ấn phẩm và truyền thông chính thức của Du lịch Đà Nẵng ngày 26/09/2026)*
- **Official Entity:** Trung tâm Hỗ trợ Du khách Đà Nẵng (Trung tâm Xúc tiến Du lịch Đà Nẵng — Sở Du lịch TP. Đà Nẵng)
- **Primary Physical Office:** **18 Hùng Vương, phường Hải Châu, Đà Nẵng** *(Văn phòng chính đã di dời từ 108 Bạch Đằng sang 18 Hùng Vương từ năm 2023)*
- **Secondary / Supporting Office Note:** **49 Phan Châu Trinh, phường Hội An, Đà Nẵng** *(Điểm liên kết hỗ trợ du khách khu vực kết nối Đà Nẵng - Hội An theo tư liệu xúc tiến 2026; không đưa vào giao diện chính để tránh quá tải thông tin)*
- **Operating Hours:** `UNKNOWN` *(Chưa công bố khung giờ trực tổng đài cụ thể trong ấn phẩm 2026; giao diện hiển thị nhãn trung lập "Thông tin hỗ trợ du khách")*
- **Telecom Charge:** `UNKNOWN` *(Đầu số ngắn *8899 chưa công bố chi tiết biểu cước viễn thông đối với người gọi; UNKNOWN != FALSE; TUYỆT ĐỐI KHÔNG tự tiện gán nhãn "Miễn phí" hoặc "Có phí")*
- **Official Portal:** [https://danangfantasticity.com](https://danangfantasticity.com)
- **Current Evidence Snapshot Date:** 2026-09-26 (Ấn phẩm Trung tâm Xúc tiến Du lịch Đà Nẵng) / 2026-10-05 (GoMate Review)
- **Legacy / Historical Hotline Record:**
  - **Number:** `(+84) 236 3550 111` (Nội địa: `0236 3550 111`)
  - **Evidence Period:** Xuất bản và lưu hành trong các tài liệu, ấn phẩm lịch sử của Trung tâm Hỗ trợ Du khách Đà Nẵng trước đây.
  - **Current Operational Status:** `UNKNOWN` *(Không tự tiện tuyên bố đã cắt số hoặc mất hiệu lực khi chưa có văn bản công bố hủy số; KHÔNG hiển thị làm hotline chính trên giao diện sản xuất GoMate V1)*.

### 5.2. Thủ Đô Hà Nội (Hanoi Tourist Information & Support)
- **Hotline Numbers:** `1800 556 896` (`VERIFIED_FREE`) / `024 3926 1515` (`UNKNOWN`)
- **Official Entity:** Trung tâm Thông tin và Hỗ trợ Khách Du lịch Hà Nội (Sở Du lịch Hà Nội)
- **Operating Hours:** `UNKNOWN`
- **Official Portal:** [http://sodulich.hanoi.gov.vn](http://sodulich.hanoi.gov.vn)
- **Snapshot Date:** 2026-10-05

---

## 6. Authoritative Metadata Evidence Matrix

| Number | Display Name | Category | Canonical Governing Authority | Availability | Charge Status | Scope & Source Notes |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- |
| **112** | Cứu nạn & tình huống nguy cấp | Khẩn cấp quốc gia (A) | **Bộ Quốc phòng** | `VERIFIED_24_7` | `VERIFIED_FREE` | NĐ 200/2025/NĐ-CP, QĐ 2023/QĐ-TTg, QĐ 2024/QĐ-TTg (Sự cố, thiên tai, thảm họa, nguy cấp) |
| **113** | Cảnh sát phản ứng nhanh | Khẩn cấp quốc gia (A) | **Bộ Công an** | `VERIFIED_24_7` | `VERIFIED_FREE` | TT 22/2014/TT-BTTTT, bocongan.gov.vn |
| **114** | Cứu hộ, Cứu nạn & PCCC | Khẩn cấp quốc gia (A) | **Cục CS PCCC & CNCH (Bộ CA)** | `VERIFIED_24_7` | `VERIFIED_FREE` | Luật PCCC, canhsatpccc.gov.vn |
| **115** | Cấp cứu y tế & Cứu thương | Khẩn cấp quốc gia (A) | **Bộ Y tế** | `VERIFIED_24_7` | `VERIFIED_FREE` | QĐ 01/2008/QĐ-BYT, moh.gov.vn |
| **111** | Tổng đài Bảo vệ Trẻ em | Bảo vệ / An sinh (B) | **Cục Bà mẹ và Trẻ em — Bộ Y tế** | `VERIFIED_24_7` | `VERIFIED_FREE` | Luật Trẻ em 2016, tongdai111.vn |
| ***8899** | Hỗ trợ Du khách Đà Nẵng (Chính) | Du lịch địa phương (C) | **Sở Du lịch TP. Đà Nẵng** | `UNKNOWN` | `UNKNOWN` | Hotline chính thức (26/09/2026), 18 Hùng Vương, phường Hải Châu, Đà Nẵng; danangfantasticity.com |
| *0236 3550 111* | *Hỗ trợ Du khách Đà Nẵng (Lịch sử)* | *Lịch sử / Đối chiếu (C)* | **Sở Du lịch TP. Đà Nẵng** | `UNKNOWN` | `UNKNOWN` | Số cố định lịch sử; trạng thái hiện tại UNKNOWN; không dùng làm hotline chính V1 |
| **1800 556 896** | Hỗ trợ Du khách Hà Nội | Du lịch địa phương (C) | **Sở Du lịch Hà Nội** | `UNKNOWN` | `VERIFIED_FREE` | sodulich.hanoi.gov.vn (Đầu số 1800) |

---

## 7. Hardened Conceptual Reference Data Schema (Design Specification Only)

> [!CAUTION]
> **Design Specification Only:** This schema is conceptual documentation for reference data integrity. DO NOT modify `apps/backend/prisma/schema.prisma`.

```prisma
// Conceptual Design Specification for Emergency Reference Data
enum MetadataEvidenceState {
  VERIFIED
  UNKNOWN
}

enum ChargeStatus {
  VERIFIED_FREE
  VERIFIED_CHARGED
  UNKNOWN
}

model EmergencyDirectoryEntry {
  id                 String                @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  countryCode        String                @map("country_code") @db.VarChar(2) // "VN"
  regionCode         String?               @map("region_code") @db.VarChar(10) // "DAD", "HAN", null (national)
  category           String                @db.VarChar(50) // "emergency_national", "protection_social", "tourist_support"
  displayName        String                @map("display_name") @db.VarChar(150)
  phoneNumber        String                @map("phone_number") @db.VarChar(30) // Primary current hotline: "*8899"
  legacyHotline      String?               @map("legacy_hotline") @db.VarChar(30) // "0236 3550 111" (historical)
  legacyStatus       MetadataEvidenceState @default(UNKNOWN) @map("legacy_status")
  physicalAddress    String?               @map("physical_address") @db.VarChar(255) // "18 Hùng Vương, phường Hải Châu, Đà Nẵng"
  secondaryAddress   String?               @map("secondary_address") @db.VarChar(255) // "49 Phan Châu Trinh, phường Hội An, Đà Nẵng"
  governingAuthority String                @map("governing_authority") @db.VarChar(150)
  coordinationNote   String?               @map("coordination_note") @db.Text
  sourceUrl          String                @map("source_url") @db.Text
  sourceName         String                @map("source_name") @db.VarChar(150)
  verifiedAt         DateTime              @map("verified_at") @db.Date
  chargeStatus       ChargeStatus          @default(UNKNOWN) @map("charge_status")
  operatingHours     String?               @map("operating_hours") @db.VarChar(50)
  hoursStatus        MetadataEvidenceState @default(UNKNOWN) @map("hours_status")
  transitionNote     String?               @map("transition_note") @db.Text

  @@index([countryCode, regionCode])
}
```
