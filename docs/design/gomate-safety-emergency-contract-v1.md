# GoMate Safety & Emergency — Capability Audit, Safety Contract & Visual Mockup V1 (R1.1 Revision)

**Status:** APPROVED ARCHITECTURAL CONTRACT & DESIGN LOCK (R1.1 REVISION)  
**Task:** TASK 08.2.3.15-R1.1 — GOMATE SAFETY & EMERGENCY: CURRENT LEGAL BASIS, SOURCE EVIDENCE & UNKNOWN-METADATA HARDENING  
**Date:** October 5, 2026  
**Branch:** `feature/gomate-visual-mockups`  
**Target Viewports:** Mobile ($390 \times 844$), Desktop ($1440 \times 900$)  
**Source of Truth:**
- Database Schema: [`apps/backend/prisma/schema.prisma`](file:///d:/Do_an/wanderai/apps/backend/prisma/schema.prisma) (`model SafetyContact`, `model SafetyCheckin`, `model EmergencyEvent`, lines 598–645)
- Backend Source Code: [`apps/backend/src/`](file:///d:/Do_an/wanderai/apps/backend/src/)
- Mobile Client Code: [`apps/mobile/lib/core/router/app_router.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/core/router/app_router.dart) (`/safety` route, `_PlaceholderScreen`)
- Mobile Geolocation: [`apps/mobile/lib/features/location/providers/user_location_provider.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/location/providers/user_location_provider.dart)
- Mobile Dependencies: [`apps/mobile/pubspec.yaml`](file:///d:/Do_an/wanderai/apps/mobile/pubspec.yaml) (`geolocator: ^13.0.2`, `url_launcher: ^6.2.0`)
- Authoritative Source Card: [`docs/design/data/gomate-emergency-contact-source-card-v1.md`](file:///d:/Do_an/wanderai/docs/design/data/gomate-emergency-contact-source-card-v1.md)
- Upstream Design Contracts:
  - [`docs/design/gomate-trip-user-flow-spec-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-trip-user-flow-spec-v1.md)
  - [`docs/design/gomate-group-foundation-contract-v1.md`](file:///d:/Do_an/wanderai/docs/design/gomate-group-foundation-contract-v1.md)
- Master Visual Evidence Artifacts:
  - Mobile Safety Home V1 (R1): [`safety-mobile-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-home-v1-r1.png) ($390 \times 844$)
  - Mobile Emergency Directory V1 (R1.1 Final): [`safety-mobile-emergency-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1-r1-final.png) / [`safety-mobile-emergency-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1-r1.png) ($390 \times 844$)
  - Mobile Emergency Confirmation V1: [`safety-mobile-emergency-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-confirm-v1.png) ($390 \times 844$)
  - Mobile Trusted Contacts V1: [`safety-mobile-trusted-contacts-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contacts-v1.png) ($390 \times 844$)
  - Mobile Add Trusted Contact V1: [`safety-mobile-trusted-contact-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contact-add-v1.png) ($390 \times 844$)
  - Mobile Location Safety V1: [`safety-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-v1.png) ($390 \times 844$)
  - Mobile Location Permission Denied V1 (R1): [`safety-mobile-location-permission-denied-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-permission-denied-v1-r1.png) ($390 \times 844$)
  - Mobile Offline Safety V1 (R1): [`safety-mobile-offline-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-offline-v1-r1.png) ($390 \times 844$)
  - Desktop Safety Master V1 (R1.1 Final): [`safety-desktop-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1-r1-final.png) / [`safety-desktop-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1-r1.png) ($1440 \times 900$)

---

## 1. Product Role & Safety Mission

The **GoMate Safety & Emergency** module provides travelers with immediate, unambiguous access to critical emergency resources, official rescue hotlines, trusted contact channels, and honest GPS coordinate reporting.

### Core Architectural Distinctions:
1. **Safety is a ROOT Destination, NOT a Sub-feature of Trips:**
   Unlike contextual features (e.g. Shared Itinerary, Group Chat, Shared Expense), **Safety (`An toàn`)** is a first-class root capability accessible directly from the primary navigation bar:
   $$\text{Canonical Root IA} = \{\text{Khám phá}, \text{Bản đồ}, \text{Wandy AI}, \text{Chuyến đi}, \textbf{An toàn}\}$$
   A traveler facing danger must be able to reach emergency tools in **one tap**, even if they are not actively participating in a shared trip.
2. **Zero-Friction Access:**
   No authentication barriers, paywalls, or multi-step wizard dialogues may ever obstruct opening the Emergency Directory or viewing national rescue hotlines.

---

## 2. Repository Capability Reality (Audit Verdict)

A rigorous audit of the WanderAI / GoMate codebase reveals the exact implementation baseline:

### 2.1. Mobile Client (`apps/mobile/`):
1. **Root Safety Route:** In [`apps/mobile/lib/core/router/app_router.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/core/router/app_router.dart#L126), the `/safety` route routes to a static `_PlaceholderScreen` (lines 18–46):
   - Renders an icon `Icons.shield` and text *"Tính năng đang phát triển..."*.
   - **Verdict: STATIC PLACEHOLDER SCREEN.**
2. **Telephone Dialer Launching (`url_launcher: ^6.2.0`):**
   - Verified present and active in [`apps/mobile/lib/features/places/presentation/place_detail_screen.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/places/presentation/place_detail_screen.dart#L294) via `'tel:${phone}'`.
   - **Verdict: CURRENT CLIENT CAPABILITY** (Opens OS telephone dialer with prefilled number; does NOT make direct background calls).
3. **Geolocation (`geolocator: ^13.0.2`):**
   - Active in [`apps/mobile/lib/features/location/providers/user_location_provider.dart`](file:///d:/Do_an/wanderai/apps/mobile/lib/features/location/providers/user_location_provider.dart).
   - Provides foreground single fix, permission checks, and accuracy radius ($\pm\text{meters}$).
   - **Background location tracking:** **100% MISSING** (no background service or manifest permissions).
   - **Live location streaming/sharing:** **100% MISSING**.
   - **Verdict: FOREGROUND GPS CURRENT; BACKGROUND & LIVE SHARING MISSING.**

### 2.2. Backend & Database (`apps/backend/`):
1. **Database Schema (`apps/backend/prisma/schema.prisma` lines 598–645):**
   - `model SafetyContact`: Defined (`id, userId, name, phone, relation, createdAt, user`).
   - `model SafetyCheckin`: Defined (`id, userId, latitude, longitude, note, createdAt, user`).
   - `model EmergencyEvent`: Defined (`id, userId, latitude, longitude, status, message, resolvedAt, createdAt`).
   - **Verdict: SCHEMA PRESENT, BUT UNREFERENCED.**
2. **Backend Controllers & Services (`apps/backend/src/`):**
   - Grep for `SafetyContact`, `SafetyCheckin`, `EmergencyEvent`, `Safety`, `Emergency` produced **0 matches**.
   - **Verdict: MISSING BACKEND RUNTIME (No endpoints, no controllers, no services).**
3. **Block & Report Models (`UserBlock`, `UserReport`):**
   - **Verdict: SCHEMA GAP** (Neither model exists in Prisma).

### 2.3. AI Service (`apps/ai-service/`):
- Contains RAG safety guides from Wikivoyage (e.g. taxi safety tips).
- Zero emergency dispatch, zero SOS endpoints.
- **Verdict: INFORMATIONAL RAG ONLY.**

---

## 3. Critical Safety Principle: AI Boundary Lock

$$\textbf{User} \quad \mathbf{\xrightarrow{\quad \text{Direct Tap} \quad}} \quad \textbf{Safety Hub} \quad \mathbf{\xrightarrow{\quad \text{Explicit Action} \quad}} \quad \textbf{Emergency Dialer}$$

$$\textbf{PROHIBITED:} \quad \text{User} \quad \xrightarrow{\quad \text{Prompt} \quad} \quad \text{Wandy AI} \quad \xrightarrow{\quad \text{LLM Reasoning} \quad} \quad \text{Emergency Action}$$

### Invariant Rules:
1. **AI is NEVER a Gatekeeper:** In an emergency, seconds matter. GoMate strictly prohibits routing urgent emergency actions through an LLM prompt or chatbot workflow.
2. **No Autonomous Calls or Messaging:** Wandy AI **MUST NOT** autonomously dial emergency hotlines, message trusted contacts, or broadcast GPS coordinates.
3. **Role of Wandy:** Wandy serves solely as an informational advisor (e.g. providing travel tips, safety gear checklists, local consular office addresses during trip preparation).

---

## 4. Emergency Contact Directory Contract

### 4.1. Zero Fabrication Policy
All emergency numbers displayed in GoMate must be grounded in verified statutory regulations and official tourism portal records. Fabricating hotline numbers for UI realism is strictly forbidden.

### 4.2. Statutory National Emergency Services (Category A)
Pursuant to Circular No. 22/2014/TT-BTTTT (Article 9, Clause 1) of the Ministry of Information and Communications and 2025 civil defense legislation:

| Service Category | Short Dial Code | Canonical Governing Authority | Operating Hours | Telecom Charge | Official Source / Legal Basis |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **Cứu nạn & tình huống nguy cấp** | `112` | **Bộ Quốc phòng** (chủ trì) | 24/7 (`VERIFIED`) | **Miễn phí (`VERIFIED_FREE`)** | NĐ 200/2025/NĐ-CP, QĐ 2023/QĐ-TTg, QĐ 2024/QĐ-TTg |
| **Cảnh sát phản ứng nhanh** | `113` | **Bộ Công an** | 24/7 (`VERIFIED`) | **Miễn phí (`VERIFIED_FREE`)** | TT 22/2014/TT-BTTTT, [`bocongan.gov.vn`](https://bocongan.gov.vn) |
| **Cứu nạn, Cứu hộ & PCCC** | `114` | **Cục CS PCCC & CNCH (Bộ Công an)** | 24/7 (`VERIFIED`) | **Miễn phí (`VERIFIED_FREE`)** | Luật PCCC, [`canhsatpccc.gov.vn`](http://canhsatpccc.gov.vn) |
| **Cấp cứu Y tế khẩn cấp** | `115` | **Bộ Y tế** | 24/7 (`VERIFIED`) | **Miễn phí (`VERIFIED_FREE`)** | QĐ 01/2008/QĐ-BYT, [`moh.gov.vn`](https://moh.gov.vn) |

*Scope Note:* The statutory scope of 112 covers receiving information on incidents (sự cố), natural disasters (thiên tai), catastrophes (thảm họa), urgent emergencies (tình huống nguy cấp), and rescue assistance requests nationwide. Coordination note: *"Liên thông với hệ thống 113, 114, 115 theo quy định hiện hành."*

### 4.3. Emergency Number Transition Governance (Implementation Roadmap)
> [!NOTE]
> **Sourced Integration Roadmap Note:**
> - *"Đề án tích hợp 113/114/115 đang được triển khai theo lộ trình; giai đoạn 1 đến năm 2027, giai đoạn tiếp theo 2027–2028."*
> - **Coexistence Reality:** During these implementation stages, **112, 113, 114, and 115 remain fully operational and active concurrently** across all provinces and municipalities. None of the four statutory emergency services have ceased operation. GoMate V1 continues presenting all four numbers directly to travelers so they have instant access to specialized forces.

### 4.4. National Public Safety / Protection Hotlines (Category B)
Statutory public safety and social welfare hotlines are strictly separated from emergency telecommunications dispatch services:

| Service Category | Short Dial Code | Canonical Governing Authority | Operating Hours | Telecom Charge | Official Source |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **Tổng đài Quốc gia Bảo vệ Trẻ em** | `111` | **Cục Bà mẹ và Trẻ em — Bộ Y tế** | 24/7 (`VERIFIED`) | **Miễn phí (`VERIFIED_FREE`)** | Luật Trẻ em 2016, [`tongdai111.vn`](https://tongdai111.vn) |

### 4.5. Destination Visitor Support Hotlines (Verified Local Sources)
Local hotlines carry individual operational metadata; global "24/7" or "Free" badges are strictly prohibited across local entries:
- **TP. Đà Nẵng:** `(+84) 236 3550 111` (Nội địa: `0236 3550 111`) — Trung tâm Hỗ trợ Du khách Đà Nẵng, Sở Du lịch Đà Nẵng ([`danangfantasticity.com`](https://danangfantasticity.com)).
  - *Physical Address:* **18 Hùng Vương, Phường Hải Châu 1, Quận Hải Châu, TP. Đà Nẵng** *(Văn phòng đã chuyển từ 108 Bạch Đằng sang 18 Hùng Vương từ năm 2023)*.
  - *Operating Hours:* `UNKNOWN` *(Không tự tiện gán "Theo ca trực" khi chưa có thông cáo chính thức)*.
  - *Telecom Charge:* `UNKNOWN` *(Không tự tiện gán "Cước cố định" hay "Không miễn phí"; UNKNOWN != FALSE)*.
  - *UI Presentation:* Badges for hours and charges are omitted; card renders neutral metadata label `Thông tin hỗ trợ du khách`.
- **Hà Nội:** `1800 556 896` (`VERIFIED_FREE`) / `024 3926 1515` (`UNKNOWN`) — Sở Du lịch Hà Nội ([`sodulich.hanoi.gov.vn`](http://sodulich.hanoi.gov.vn)).
- **TP. Hồ Chí Minh:** `1022` (Nhánh 8) / `(+84) 28 3825 8558` — Sở Du lịch TP.HCM ([`visithcmc.vn`](https://visithcmc.vn)).

### 4.6. Hardened Conceptual Reference Data Architecture (Design Spec Only)
> [!CAUTION]
> **Design Specification Only:** Conceptual schema documentation for data integrity. Production `apps/backend/prisma/schema.prisma` is NOT modified.

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
  phoneNumber        String                @map("phone_number") @db.VarChar(30)
  physicalAddress    String?               @map("physical_address") @db.VarChar(255)
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

---

## 5. Emergency Action Semantics

$$\textbf{Tapping Emergency Button} \quad \mathbf{\longrightarrow} \quad \textbf{Confirmation Modal} \quad \mathbf{\longrightarrow} \quad \textbf{OS Dialer (tel:...)}$$

1. **Explicit Confirmation Modal:**
   - Tapping an emergency action button (e.g. `[ Gọi 115 ]`) displays a dedicated confirmation sheet ([`safety-mobile-emergency-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-confirm-v1.png)).
   - Displays the target hotline, agency name, and current coordinates (`16.054400° N, 108.202200° E`) so the user can read their location to dispatchers immediately.
2. **OS Dialer Handoff:**
   - Upon tapping `[ Mở trình quay số ]`, the app invokes `launchUrl(Uri.parse('tel:115'), mode: LaunchMode.externalApplication)`.
   - The user retains final authority to press the green "Call" button on their native phone app.
3. **Strict Prohibition of Silent Calling:**
   - GoMate will **NEVER** use telephony permissions (such as Android `CALL_PHONE`) to place calls without explicit OS dialer user interaction.

---

## 6. Trusted Contacts Contract

### 6.1. Conceptual Model (`SafetyContact`)
```prisma
// Aligned with existing schema.prisma lines 602-613
model SafetyContact {
  id        String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  userId    String   @map("user_id") @db.Uuid
  name      String   @db.VarChar(100)
  phone     String   @db.VarChar(30)
  relation  String   @db.VarChar(50) // "family", "friend", "colleague", "other"
  createdAt DateTime @default(now()) @map("created_at") @db.Timestamptz

  user      User     @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId])
  @@map("safety_contacts")
}
```

### 6.2. Sensitive Privacy Lock
Trusted contacts are sensitive personal safety records. Strict privacy boundaries are locked:
1. **Private by Design:** Only the owning user (`userId === req.user.id`) can view, create, edit, or delete trusted contacts.
2. **No Social Exposure:** Trusted contact phone numbers are **NEVER** exposed in Group Chat, Trip Member lists, Buddy Discovery, or public user profiles.
3. **Trip Deletion Independence:** Deleting a Trip does **NOT** delete trusted contacts. They are bound directly to the `User`.
4. **Quota Limit:** V1 caps trusted contacts at 3 individuals per traveler for focused emergency response.

---

## 7. Location Safety Contract (Honest Foreground GPS)

$$\textbf{Current Location (Foreground Fix)} \quad \ne \quad \textbf{Live Location Sharing} \quad \ne \quad \textbf{Background Tracking}$$

1. **Foreground GPS Only:**
   - GoMate reads GPS coordinates solely while the app is active and foregrounded via `Geolocator.getCurrentPosition()`.
   - The UI renders coordinates (`16.054400° N, 108.202200° E`), estimated locality, and accuracy radius (`±15 m (Tốt)`).
2. **No Background Tracking:**
   - GoMate contains zero background location workers and requests zero background location permissions (`ACCESS_BACKGROUND_LOCATION`).
   - The app never tracks or records traveler movements when backgrounded or closed.
3. **Explicit Refresh & Copy:**
   - Coordinates update only on explicit user tap (`[ Làm mới vị trí ]`).
   - `[ Sao chép tọa độ ]` copies formatted text to the device clipboard to paste into SMS or emergency calls.

---

## 8. Location Sharing Contract (Future / Design Target)

Live location sharing is classified as **DESIGN TARGET / FUTURE INFRASTRUCTURE**. When implemented, it must strictly adhere to the following safety invariants:
- **OFF by default:** Never enabled without explicit user interaction.
- **Explicit recipient selection:** Traveler chooses specific trusted contact or trip member.
- **Bounded duration:** User must select a finite time limit (15 min, 1 hour, 4 hours).
- **Persistent visual indicator:** Screen displays prominent active-sharing banner.
- **Instant revocation:** Single tap `[ Dừng chia sẻ ngay ]` terminates location broadcast immediately.
- **Zero autonomous sharing:** Wandy AI is strictly prohibited from activating live sharing.

---

## 9. SOS Action Hub Semantics

SOS in GoMate is an **Emergency Action Hub**, NOT an autonomous single-button dispatch sequence:

$$\textbf{SOS Hub} = \begin{cases}
\text{1. Danh bạ cứu trợ quốc gia (112, 113, 114, 115) & bảo vệ trẻ em (111)} \\
\text{2. Quay số nhanh người liên hệ tin cậy} \\
\text{3. Đọc & sao chép tọa độ vị trí hiện tại} \\
\text{4. Cẩm nang & chỉ dẫn an toàn tại chỗ}
\end{cases}$$

GoMate strictly rejects speculative workflows that automatically trigger mass SMS, broadcast audio, or call police simultaneously upon a single click.

---

## 10. Offline Behavior & Failure Safety UX

1. **Offline Emergency Directory:**
   - Core national emergency hotlines (`112`, `113`, `114`, `115`, `111`) are bundled statically in client cache.
   - **Neutral Telecom Copy:** *"Cuộc gọi khẩn cấp sử dụng dịch vụ thoại của nhà mạng và không cần kết nối Internet. Khả năng gọi vẫn phụ thuộc vùng phủ sóng và dịch vụ viễn thông trên thiết bị."* (Omit speculative promises of 2G/3G/4G network generations).
   - The offline screen ([`safety-mobile-offline-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-offline-v1-r1.png)) displays hotlines and cached GPS fix without error barriers.
2. **Permission Denied State Split (`denied` vs `deniedForever`):**
   - **Standard `denied`:** The user dismissed a previous dialog; the app can prompt again in-context. Primary CTA is `[ Cấp quyền vị trí ]`.
   - **Permanent `deniedForever`:** The user selected "Never ask again" or platform policy prevents further prompts. The system cannot display an in-app permission dialog. Primary CTA is `[ Mở Cài đặt hệ thống ]` ([`safety-mobile-location-permission-denied-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-permission-denied-v1-r1.png)).
   - **No Trapping:** In both permission-denied states, immediate direct access to national emergency hotlines (112, 113, 114, 115) is fully preserved without requiring GPS fix.
3. **No Technical Errors:**
   - Stacktraces, HTTP status codes (e.g. 500, 503), and raw socket exceptions are strictly prohibited.

---

## 11. Safety Disclaimer Contract

All Safety screens display a calm, legally precise product disclaimer:

> *"GoMate hỗ trợ bạn truy cập nhanh thông tin an toàn và danh bạ cứu nạn. GoMate không phải cơ quan điều phối cứu hộ. Trong tình huống khẩn cấp, vui lòng liên hệ ngay cơ quan chức năng hoặc người hỗ trợ tại địa phương."*

GoMate makes zero warranties regarding emergency response times, cellular network coverage, or authority availability.

---

## 12. User Block & Report Audit (Social Safety Dependency)

1. **Audit Finding:**
   - `model UserBlock` and `model UserReport` are **MISSING** in `apps/backend/prisma/schema.prisma`.
   - Backend contains zero block/report endpoints.
2. **Classification:**
   - **SCHEMA GAP / SAFETY DEPENDENCY**.
3. **Module Separation:**
   - Moderation (blocking, reporting harassing users, offensive messages) belongs to the **Social Safety** domain.
   - It is strictly decoupled from the **Emergency SOS Hub** to prevent cluttering urgent life-safety flows.

---

## 13. Safety Consent Matrix

| Action / Capability | Consent Requirement | Trigger Mechanism |
| :--- | :--- | :--- |
| **View Emergency Numbers** | None (Public Reference Data) | Navigate to Safety tab |
| **Open Phone Dialer (113/114/115)** | **Explicit Confirmation** | Tap `[ Gọi ]` $\rightarrow$ Confirm Sheet $\rightarrow$ OS Dialer |
| **Add Trusted Contact** | **Explicit User Input** | Form submit `[ Lưu người liên hệ ]` |
| **Delete Trusted Contact** | **Explicit Confirmation** | Modal confirmation `[ Xóa ]` |
| **Call Trusted Contact** | **Explicit User Tap** | Tap `[ Mở cuộc gọi ]` $\rightarrow$ OS Dialer |
| **Read Current GPS Coordinates** | **OS Location Permission** | `Geolocator.getCurrentPosition()` (Foreground) |
| **Refresh GPS Fix** | **Explicit Action** | Tap `[ Làm mới vị trí ]` |
| **Copy GPS Coordinates** | **Explicit Action** | Tap `[ Sao chép tọa độ ]` |
| **Live Location Sharing (Future)**| **Explicit Double Opt-in** | Select recipient + duration + confirm |
| **Wandy AI Safety Advice** | **Informational Only** | Chat query; **NEVER autonomous action** |

---

## 14. Master Visual Mockup Evidence

All 9 master mockups were rendered via headless Microsoft Edge browser at native resolutions and verified in `docs/audit/evidence/ui-08.2.3.15/`:

| Mockup File | Viewport | Target Resolution | Architectural & Visual Compliance Audit | Status |
| :--- | :---: | :---: | :--- | :---: |
| [`safety-mobile-home-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-home-v1-r1.png) | Mobile | $390 \times 844$ | 1. Status bar `9:41 5G 100%` + App bar `An toàn & Cứu trợ`.<br>2. Emergency SOS card displaying national services (112, 113, 114, 115) with `[ Mở danh bạ cứu trợ khẩn cấp › ]`.<br>3. Location safety card: Coordinates, locality, accuracy `±15 m (Tốt)`.<br>4. Trusted contacts summary (2/3 contacts) with private lock tag.<br>5. Travel safety handbook card.<br>6. Product disclaimer footnote.<br>7. Canonical 5-tab root navigation with `An toàn` active. | **PASS (LOCKED R1)** |
| [`safety-mobile-emergency-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-v1-r1-final.png) | Mobile | $390 \times 844$ | 1. App bar `< Danh bạ cứu trợ & bảo vệ` + Subtitle.<br>2. Sourced free-call notice for 112, 113, 114, 115, 111.<br>3. National emergency services section: 112 (Cứu nạn & tình huống nguy cấp · Bộ Quốc phòng chủ trì), 113 (Công an), 114 (Cứu nạn & PCCC), 115 (Cấp cứu) with individual 24/7 & free badges.<br>4. Separated National Child Protection Hotline section: 111 (Cục Bà mẹ và Trẻ em — Bộ Y tế).<br>5. Local tourist support: 0236 3550 111 (Đà Nẵng Visitor Center) at 18 Hùng Vương with neutral metadata `Thông tin hỗ trợ du khách` (purged unsupported badges).<br>6. Staged transition roadmap footnote: Stage 1 until 2027, subsequent stage 2027–2028.<br>7. Canonical 5-tab bottom navigation. | **PASS (LOCKED R1.1)** |
| [`safety-mobile-emergency-confirm-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-emergency-confirm-v1.png) | Mobile | $390 \times 844$ | 1. Dark semi-transparent modal overlay.<br>2. Confirmation sheet: `Gọi Cấp cứu Y tế 115?`.<br>3. Exact GPS coordinates and locality display for dispatcher communication.<br>4. Primary CTA: `[ Mở trình quay số 115 ]` (Red).<br>5. Secondary: `[ Hủy bỏ ]`. Zero silent calling. | **PASS (LOCKED)** |
| [`safety-mobile-trusted-contacts-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contacts-v1.png) | Mobile | $390 \times 844$ | 1. App bar `< Người liên hệ tin cậy` with `+ Thêm`.<br>2. Sensitive privacy guarantee banner (creator-only, hidden from group/profile).<br>3. 2 contact cards with `[ Mở cuộc gọi ]`, `[ Sửa ]`, `[ Xóa ]`.<br>4. Clarification note: Calls open OS dialer; deleting trips preserves contacts.<br>5. Canonical 5-tab bottom navigation. | **PASS (LOCKED)** |
| [`safety-mobile-trusted-contact-add-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-trusted-contact-add-v1.png) | Mobile | $390 \times 844$ | 1. App bar `Hủy`, `Thêm người liên hệ`, `Lưu`.<br>2. Form inputs: Full Name \*, Phone Number \*, Relationship chips.<br>3. Privacy commitment card explaining data protection.<br>4. Primary CTA: `[ Lưu người liên hệ tin cậy ]`. Clean layout contained in $844\text{px}$. | **PASS (LOCKED)** |
| [`safety-mobile-location-v1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-v1.png) | Mobile | $390 \times 844$ | 1. Mini map visual snippet with user marker and pulse halo.<br>2. GPS data: Coordinates `16.054400° N, 108.202200° E`, accuracy `±15 m (Tốt)`, timestamp.<br>3. Technical honesty disclosure: Foreground read only, no background tracking, no live sharing.<br>4. Actions: `[ Làm mới tọa độ GPS ]`, `[ Sao chép tọa độ ]`.<br>5. Canonical 5-tab bottom navigation. | **PASS (LOCKED)** |
| [`safety-mobile-location-permission-denied-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-location-permission-denied-v1-r1.png) | Mobile | $390 \times 844$ | 1. Orange shield icon + `Quyền truy cập vị trí đang bị tắt vĩnh viễn`.<br>2. Clear status: `deniedForever` explaining why system dialog cannot re-prompt.<br>3. Action button: `[ Mở Cài đặt hệ thống thiết bị ]` (strictly differentiated from temporary denial).<br>4. Safe Fallback section: Direct access to 112, 113, 114, 115 hotlines maintained (never traps user).<br>5. Canonical 5-tab bottom navigation. | **PASS (LOCKED R1)** |
| [`safety-mobile-offline-v1-r1.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-mobile-offline-v1-r1.png) | Mobile | $390 \times 844$ | 1. Offline status badge and banner.<br>2. Neutral telecom capability notice (phone call requires carrier network coverage, independent of Internet; omitted speculative 2G/3G/4G text).<br>3. Static cached emergency hotlines: 112, 113, 114, 115.<br>4. Cached last-known GPS fix.<br>5. Canonical 5-tab bottom navigation. | **PASS (LOCKED R1)** |
| [`safety-desktop-v1-r1-final.png`](file:///d:/Do_an/wanderai/docs/audit/evidence/ui-08.2.3.15/safety-desktop-v1-r1-final.png) | Desktop | $1440 \times 900$ | 1. Top nav: Logo `GoMate` + badge `Safety Hub` + Canonical 5 tabs (`Khám phá`, `Bản đồ`, `Wandy AI`, `Chuyến đi`, `An toàn` [Active]) + User pill.<br>2. Col 1 ($280\text{px}$): Safety menu & quick hotline box (112, 113, 114, 115, 111).<br>3. Col 2 ($780\text{px}$): National Emergency Grid (112, 113, 114, 115 · Bộ Quốc phòng chủ trì) + Separate row for 111 & Đà Nẵng hotline (18 Hùng Vương, neutral metadata label, no unsupported badges) + Foreground Location Safety card.<br>4. Col 3 ($340\text{px}$): Trusted contacts widget + Wandy Safety Copilot card (advisory only) + Sourced transition roadmap note (Giai đoạn 1 đến 2027, giai đoạn tiếp theo 2027–2028).<br>5. Zero debug labels; perfectly contained in $900\text{px}$. | **PASS (LOCKED R1.1)** |

---

## 15. Current vs. Future Capability Matrix (24 Dimensions)

| Dimension | Current Runtime Status | Architectural Contract V1 | Future Target |
| :--- | :---: | :---: | :--- |
| **1. Safety Root Tab** | **PARTIAL (Placeholder)** | **DESIGN LOCKED** | Flutter feature module replacing `_PlaceholderScreen` |
| **2. Emergency Directory Data** | **MISSING** | **REFERENCE DATA SPEC** | Static reference table `emergency_directory_entries` |
| **3. Emergency Dialer Launch** | **CURRENT** | **DESIGN LOCKED** | `url_launcher` via `tel:` intent with confirmation |
| **4. Direct Background Call** | **EXCLUDED** | **STRICTLY PROHIBITED** | Never implemented; user controls OS dialer |
| **5. Trusted Contact DB Model** | **PARTIAL (Schema only)** | **SCHEMA LOCKED** | `model SafetyContact` in PostgreSQL |
| **6. Trusted Contact API** | **MISSING** | **DESIGN TARGET** | NestJS `SafetyContactsController` CRUD |
| **7. Trusted Contact UI** | **MISSING** | **DESIGN LOCKED** | Flutter riverpod contact management |
| **8. Trusted Contact Privacy**| **DESIGN LOCKED** | **STRICTLY PRIVATE** | Creator-only; isolated from groups & profiles |
| **9. Foreground GPS Reading** | **CURRENT** | **DESIGN LOCKED** | `Geolocator.getCurrentPosition()` with accuracy pill |
| **10. Location Permission Flow** | **CURRENT** | **DESIGN LOCKED** | `checkPermission()` / `requestPermission()` |
| **11. Location Accuracy Grading** | **CURRENT** | **DESIGN LOCKED** | Good ($\le 50\text{m}$), Approx ($50-200\text{m}$), Poor ($>200\text{m}$) |
| **12. Live Location Sharing** | **MISSING** | **FUTURE SPECIFICATION** | Ephemeral sharing with explicit duration & stop button |
| **13. Background Location Tracking**| **MISSING** | **EXCLUDED FROM V1** | Not built; requires background OS service |
| **14. Location Persistence** | **PARTIAL (Checkin schema)**| **FUTURE SPECIFICATION**| `model SafetyCheckin` point-in-time logging |
| **15. SOS Action Hub** | **MISSING** | **DESIGN LOCKED** | Multi-channel action hub (Hotline, Contact, GPS) |
| **16. Autonomous Emergency Chain** | **EXCLUDED** | **STRICTLY PROHIBITED** | No automated mass actions upon single click |
| **17. Emergency SMS Sending** | **MISSING** | **FUTURE SPECIFICATION** | Requires telephony plugin & explicit confirmation |
| **18. Offline Emergency Directory**| **MISSING** | **DESIGN LOCKED** | Static bundled hotlines in client assets |
| **19. Wandy Safety Assistance** | **PARTIAL (RAG guides)** | **DESIGN LOCKED** | Informational tips and preparedness checklists |
| **20. Wandy Autonomous Dispatch** | **EXCLUDED** | **STRICTLY PROHIBITED** | Wandy cannot trigger calls, SMS, or GPS sharing |
| **21. User Block Capability** | **MISSING** | **SCHEMA GAP** | `model UserBlock` for social safety |
| **22. User Report Capability** | **MISSING** | **SCHEMA GAP** | `model UserReport` for moderation |
| **23. Message Report Capability** | **MISSING** | **SCHEMA GAP** | Reporting abusive messages in Group Chat |
| **24. Trip Deletion Impact** | **DESIGN LOCKED** | **ISOLATED LIFECYCLE** | Deleting trips never deletes trusted contacts |
