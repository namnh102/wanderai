# GoMate Emergency Contact Directory — Authoritative Source Card V1 (R1 Revision)

**Status:** APPROVED REFERENCE DATA SPECIFICATION & DIRECTORY CORRECTION  
**Task:** TASK 08.2.3.15-R1 — GOMATE SAFETY & EMERGENCY: AUTHORITATIVE DIRECTORY & CURRENT-GOVERNANCE CORRECTION  
**Date:** October 5, 2026  
**Jurisdiction / Primary Scope:** Vietnam (Toàn quốc & Điểm đến du lịch trọng điểm)  
**Applicability:** GoMate V1 Client Emergency Hub & Directory  

---

## 1. Governance & Data Honesty Principle

> [!IMPORTANT]
> **Zero Fabrication Policy & Taxonomy Integrity:**
> 1. Emergency contact numbers connect travelers to life-saving and civil defense services. Fabricating, guessing, or using mock phone numbers for visual realism is **STRICTLY PROHIBITED**.
> 2. **Strict Taxonomy Separation:** Statutory emergency services (112, 113, 114, 115) must be cleanly distinguished from social protection/welfare hotlines (111) and local tourism support hotlines.
> 3. **No Blanket Claims:** Do NOT apply global "24/7" or "Miễn phí" badges across heterogeneous contact categories. Every entry carries its own verified operational metadata.

---

## 2. Statutory National Emergency Services (Dịch Vụ Khẩn Cấp Quốc Gia)

Pursuant to Circular No. 22/2014/TT-BTTTT of the Ministry of Information and Communications (Article 9 on Emergency Telecommunications Numbers), four numbers constitute Vietnam's national emergency services:

### 2.1. Tìm Kiếm & Cứu Nạn Quốc Gia (Search, Rescue & Civil Defence) — 112
- **Short Dial Number:** `112`
- **Official Title:** Tổng đài tiếp nhận yêu cầu trợ giúp, tìm kiếm cứu nạn trên phạm vi toàn quốc
- **Governing Authority:** Ủy ban Quốc gia Ứng phó sự cố, thiên tai và Tìm kiếm Cứu nạn (VINASARCOM) / Cục Cứu hộ - Cứu nạn (Bộ Quốc phòng) phối hợp cùng các nhà mạng viễn thông.
- **Geographic Scope:** Toàn quốc (National) — bao gồm đất liền, sông suối, vùng núi hiểm trở và vùng biển Việt Nam.
- **Availability:** 24/7
- **Telecom Charge:** **Miễn phí cước gọi (Free call)**
- **Interconnection & Coordination:** 
  - Phối hợp và chia sẻ thông tin cứu nạn với các lực lượng Cảnh sát (113), Cảnh sát PCCC & CNCH (114), và Y tế (115).
  - Tiếp nhận các tình huống thiên tai, bão lũ, sạt lở đất, tàu thuyền gặp nạn trên biển, người mất tích khi leo núi hoặc thám hiểm dã ngoại.
- **Primary Source / Legal Basis:**
  - Quyết định số 226/QĐ-TTg của Thủ tướng Chính phủ phê duyệt Quy hoạch phát triển hệ thống thông tin cứu nạn khẩn cấp.
  - Thông tư số 22/2014/TT-BTTTT của Bộ Thông tin và Truyền thông ban hành Quy hoạch kho số viễn thông (Điều 9, Khoản 1).
  - Cổng thông tin Cục Cứu hộ - Cứu nạn: [http://vinasarcom.gov.vn](http://vinasarcom.gov.vn)
- **Snapshot Date:** 2026-10-05
- **Operational Scope in GoMate:** Sử dụng cho các trường hợp du khách đi trekking, lạc trong rừng/núi, gặp sự cố trên biển hoặc thiên tai lũ quét.

### 2.2. Cảnh Sát / Công An (Police & Public Security) — 113
- **Short Dial Number:** `113`
- **Official Title:** Tổng đài Cảnh sát phản ứng nhanh 113
- **Governing Authority:** Bộ Công an Việt Nam (Ministry of Public Security)
- **Geographic Scope:** Toàn quốc (National)
- **Availability:** 24/7
- **Telecom Charge:** **Miễn phí cước gọi (Free call)**
- **Primary Source / Legal Basis:**
  - Thông tư số 22/2014/TT-BTTTT (Bộ TTTT).
  - Cổng thông tin điện tử Bộ Công an: [https://bocongan.gov.vn](https://bocongan.gov.vn)
- **Snapshot Date:** 2026-10-05
- **Operational Scope in GoMate:** Can thiệp an ninh trật tự, trộm cắp, cướp giật, hành hung, tai nạn giao thông nghiêm trọng.

### 2.3. Cứu Hỏa & Cứu Nạn Cứu Hộ (Fire & Rescue) — 114
- **Short Dial Number:** `114`
- **Official Title:** Tổng đài Cứu nạn, Cứu hộ và Phòng cháy chữa cháy 114
- **Governing Authority:** Cục Cảnh sát PCCC và CNCH — Bộ Công an
- **Geographic Scope:** Toàn quốc (National)
- **Availability:** 24/7
- **Telecom Charge:** **Miễn phí cước gọi (Free call)**
- **Primary Source / Legal Basis:**
  - Luật Phòng cháy và chữa cháy; Nghị định số 136/2020/NĐ-CP; Thông tư số 22/2014/TT-BTTTT.
  - Trang thông tin điện tử Cục Cảnh sát PCCC và CNCH: [http://canhsatpccc.gov.vn](http://canhsatpccc.gov.vn)
- **Snapshot Date:** 2026-10-05
- **Operational Scope in GoMate:** Hỏa hoạn tại khách sạn/homestay, tai nạn mắc kẹt thang máy/xe khách, đuối nước tại bãi biển/hồ bơi.

### 2.4. Cấp Cứu Y Tế (Medical Emergency & Ambulance) — 115
- **Short Dial Number:** `115`
- **Official Title:** Tổng đài Cấp cứu Y tế 115
- **Governing Authority:** Bộ Y tế Việt Nam (Ministry of Health) / Trung tâm Cấp cứu 115 các tỉnh, thành phố
- **Geographic Scope:** Toàn quốc (National)
- **Availability:** 24/7
- **Telecom Charge:** **Miễn phí cước gọi (Free call)**
- **Primary Source / Legal Basis:**
  - Quyết định số 01/2008/QĐ-BYT về Quy chế Cấp cứu, Hồi sức tích cực và Chống độc.
  - Cổng thông tin điện tử Bộ Y tế: [https://moh.gov.vn](https://moh.gov.vn)
- **Snapshot Date:** 2026-10-05
- **Operational Scope in GoMate:** Chấn thương nặng, ngộ độc thực phẩm cấp, đột quỵ, sốc nhiệt, tai nạn đe dọa tính mạng.

---

## 3. Emergency Number Transition Governance (2026–2027 Coexistence Period)

> [!NOTE]
> **National 113 Integration Transition Status:**
> - Vietnam is currently implementing the roadmap to modernize command information centers and integrate emergency reception (113, 114, 115) toward a unified emergency response infrastructure centered on 113.
> - **Transition Classification:** `transitionStatus: "2026–2027 integration / coexistence period"`.
> - **Operational Reality:** During this transition window, **114 and 115 continue to operate actively** across all provinces and cities. They have NOT ceased operation. GoMate V1 continues presenting 112, 113, 114, and 115 explicitly so travelers have immediate direct access to specialized dispatch units while documenting the national integration direction.

---

## 4. National Public Safety / Protection Hotlines (Đường Dây Nóng An Sinh / Bảo Vệ Xã Hội)

This category represents statutory public welfare hotlines, distinct from emergency telecom dispatch services:

### 4.1. Tổng Đài Quốc Gia Bảo Vệ Trẻ Em — 111
- **Short Dial Number:** `111`
- **Official Title:** Tổng đài Quốc gia Bảo vệ Trẻ em 111
- **Governing Authority:** **Cục Bà mẹ và Trẻ em — Bộ Y tế** (Cập nhật phân công quản lý nhà nước hiện hành)
- **Geographic Scope:** Toàn quốc (National)
- **Availability:** 24/7
- **Telecom Charge:** **Miễn phí cước gọi (Free call)**
- **Primary Source / Legal Basis:**
  - Luật Trẻ em 2016; Nghị định 56/2017/NĐ-CP quy định chi tiết một số điều của Luật Trẻ em.
  - Cổng thông tin Tổng đài 111: [https://tongdai111.vn](https://tongdai111.vn)
- **Snapshot Date:** 2026-10-05
- **Operational Scope in GoMate:** Hỗ trợ khẩn cấp bảo vệ trẻ em trong chuyến đi gia đình: trẻ em bị thất lạc, tai nạn thương tích trẻ em, bạo lực, xâm hại hoặc nguy cơ tổn hại sức khỏe tâm lý/thể chất.

---

## 5. Destination Tourist Support Hotlines (Đường Dây Nóng Du Khách Địa Phương)

Dành cho phản ánh giá cả dịch vụ, hỗ trợ thông tin địa bàn, xử lý thất lạc hành lý và tranh chấp du lịch.

### 5.1. TP. Đà Nẵng (Đà Nẵng Visitor Support Center)
- **Hotline Number:** `(+84) 236 3550 111` (Nội địa: `0236 3550 111`)
- **Official Entity:** Trung tâm Hỗ trợ Du khách Đà Nẵng (Sở Du lịch TP. Đà Nẵng)
- **Physical Address:** 108 Bạch Đằng, Quận Hải Châu, TP. Đà Nẵng
- **Availability:** Giờ hành chính & theo ca trực hỗ trợ mùa du lịch cao điểm (KHÔNG xác nhận trực 24/7 toàn năm).
- **Telecom Charge:** **Cước viễn thông cố định tiêu chuẩn (Standard local call rate)** (KHÔNG phải miễn phí cước).
- **Official Portal:** [https://danangfantasticity.com](https://danangfantasticity.com)
- **Snapshot Date:** 2026-10-05

### 5.2. Thủ Đô Hà Nội (Hanoi Tourist Information & Support)
- **Hotline Numbers:** `1800 556 896` (Miễn phí cước) / `024 3926 1515` (Cước cố định)
- **Official Entity:** Trung tâm Thông tin và Hỗ trợ Khách Du lịch Hà Nội (Sở Du lịch Hà Nội)
- **Official Portal:** [http://sodulich.hanoi.gov.vn](http://sodulich.hanoi.gov.vn)
- **Snapshot Date:** 2026-10-05

---

## 6. Authoritative Metadata Evidence Matrix

| Number | Display Name | Category | Governing Authority | 24/7 | Free Call | Telecom Type |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- |
| **112** | Tìm kiếm & Cứu nạn | Khẩn cấp quốc gia | VINASARCOM / Bộ Quốc phòng | **Yes** | **Yes** | Statutory Emergency |
| **113** | Cảnh sát phản ứng nhanh | Khẩn cấp quốc gia | Bộ Công an | **Yes** | **Yes** | Statutory Emergency |
| **114** | Cứu nạn, Cứu hộ & PCCC | Khẩn cấp quốc gia | Cục CS PCCC & CNCH | **Yes** | **Yes** | Statutory Emergency |
| **115** | Cấp cứu y tế | Khẩn cấp quốc gia | Bộ Y tế | **Yes** | **Yes** | Statutory Emergency |
| **111** | Tổng đài Bảo vệ Trẻ em | Bảo vệ / An sinh | Cục Bà mẹ và Trẻ em — Bộ Y tế | **Yes** | **Yes** | Public Safety Hotline |
| **0236 3550 111** | Hỗ trợ Du khách Đà Nẵng | Du lịch địa phương | Sở Du lịch Đà Nẵng | **No (Ca trực)** | **No (Cước cố định)** | PSTN Landline |
| **1800 556 896** | Hỗ trợ Du khách Hà Nội | Du lịch địa phương | Sở Du lịch Hà Nội | **No (Giờ HC)** | **Yes (1800)** | Toll-free Hotline |
