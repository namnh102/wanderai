# GoMate Wandy AI Copilot — User Flow Specification V1

**Status:** APPROVED USER FLOW SPECIFICATION  
**Task:** TASK 08.2.3.4 — GOMATE WANDY AI COPILOT VISUAL MOCKUP V1  
**Applies to:** Mobile App & Desktop Web  
**Covers:** Core Flows W01 through W12  
**Source of Truth:** Master Reference Board (`media_1791138265499.jpg`), GoMate UX Architecture V1, User Flows V1  

---

## 1. Flow Matrix Overview

| Flow ID | Flow Name | Primary Screen Mockup | Core Interaction |
| :--- | :--- | :--- | :--- |
| **W01** | Open Wandy | `wandy-mobile-empty.png`, `wandy-desktop-empty.png` | Bottom Tab 3 tap or Desktop Nav click |
| **W02** | Quick Prompt Selection | `wandy-mobile-empty-prompts.png` | Tapping predefined travel category prompts |
| **W03** | Ask Freeform Question | `wandy-mobile-chat.png` | Typing question in chat input capsule |
| **W04** | Grounded Answer Display | `wandy-mobile-chat-sources.png` | RAG retrieval + source attribution rendering |
| **W05** | View Source Provenance | `wandy-mobile-source-detail.png` | Tapping source chip to inspect OSM / Wiki license |
| **W06** | View Place Detail | `wandy-mobile-place-recommendation.png` | Transitioning from chat card to Place Detail |
| **W07** | Open Map with Results | `wandy-mobile-multi-place-results.png` | Tapping "Xem tất cả trên bản đồ" |
| **W08** | Add Place to Trip | `wandy-mobile-add-to-trip-action.png` | Opening trip picker bottom sheet and saving |
| **W09** | Open AI Planner Entry | `wandy-mobile-planner-entry.png` | Triggering itinerary generator wizard |
| **W10** | Trip Context Awareness | `wandy-mobile-context-trip.png`, `wandy-desktop-chat-context.png` | Asking Wandy while inside an active trip plan |
| **W11** | Connection Error & Retry | `wandy-mobile-error.png`, `wandy-desktop-error.png` | Handling network drop or API 5xx |
| **W12** | Future Agent Confirmation | `wandy-mobile-agent-confirmation.png`, `wandy-desktop-agent-confirmation.png` | Human-in-the-loop confirmation before autonomous trip modification |

---

## 2. Detailed Flow Specifications

### FLOW W01: Open Wandy Copilot
- **Entry:** User taps Tab 3 (`Wandy AI`) in the mobile bottom navigation bar or clicks `Wandy AI` in the desktop header.
- **User Intent:** Access AI travel assistance, start a trip conversation, or seek local recommendations.
- **Action:** System mounts `/ai-chat` route.
- **Loading:** Skeleton loader ($<150\text{ms}$) or instant cached session load.
- **Success:**
  - If no prior history: Renders **Empty State** with Wandy mascot hero, greeting `Chào bạn! Mình là Wandy 👋`, and 4 prompt cards (`Lập lịch trình`, `Tìm địa điểm`, `Gợi ý món ngon`, `Khám phá gần bạn`).
  - If prior session exists: Resumes active chat scroll position with timestamp and message history.
- **Empty State:** Illustrated mascot hero with West Lake Pagoda scenery + prompt pills.
- **Error State:** N/A (local route mount).
- **Cancel / Back:** Tapping Tab 1 (`Khám phá`) returns to Home; tapping Tab 2 (`Bản đồ`) returns to Map preserving previous state.

---

### FLOW W02: Quick Prompt Selection
- **Entry:** User views Empty State or taps banner `Khám phá Việt Nam cùng Wandy`.
- **User Intent:** Quick discovery without needing to manually type on mobile keyboard.
- **Action:** User taps any prompt chip (e.g. `✨ Lập lịch trình 3 ngày ở Hà Nội` or `🍜 Ăn gì ở Hồ Tây?`).
- **Loading:** Immediately transfers prompt text into the chat stream as a user message bubble; transitions to thinking state.
- **Success:** Wandy replies with categorized recommendations or opens the appropriate sub-flow (Planner or Multi-place list).
- **Cancel / Back:** Tapping outside or tapping keyboard input dismisses suggestions.

---

### FLOW W03: Ask Freeform Question
- **Entry:** User taps the bottom input capsule (`Hỏi Wandy điều gì đó...`).
- **User Intent:** Inquire about specific locations, budgets, timings, or cultural trivia.
- **Action:** Keyboard opens; user types prompt (e.g. `Tôi muốn tìm địa điểm văn hóa ở Hà Nội`) and taps the circular teal send button.
- **Loading:** Input disables briefly; user message animates into chat stream; thinking indicator appears below.
- **Success:** Assistant replies with conversational text + horizontal place card carousel.
- **Empty State:** If prompt is empty, send button remains disabled.
- **Error State:** If input contains blacklisted/unsafe content, a polite system notice appears.

---

### FLOW W04: Grounded Answer Display
- **Entry:** AI service completes RAG retrieval and synthesis.
- **User Intent:** Receive accurate, verified travel facts backed by authentic data sources.
- **Action:** Wandy renders response bubble with structured Markdown, accompanied by `Nguồn tham khảo` label and source chips (`[◎ OpenStreetMap]`, `[📖 Wikivoyage: Hanoi]`).
- **Loading:** Non-deterministic step-by-step thinking checklist (`Phân tích nhu cầu...`, `Tìm kiếm địa điểm...`, `Kiểm tra nguồn...`) with indeterminate progress bar (no fake percentage).
- **Success:** Rich place cards with real photos, visual layout sample (`★ 4.6 (128)`), and distances (`2.4 km từ bạn`).
- **Data Honesty Invariant:** No synthetic ratings. If a place has no ratings in DB, it strictly renders `Chưa có đánh giá`. Address/hours fall back to `Chưa có thông tin...` if absent in source data.
- **Demo State Notice:** Sample metadata in mockups is explicitly designated as `VISUAL DEMO STATE — NOT PRODUCTION DATA`.

---

### FLOW W05: View Source Provenance
- **Entry:** User taps any source chip (e.g. `[◎ OpenStreetMap]` or `[📖 Wikivoyage]`).
- **User Intent:** Verify data credibility, check author attribution, or view OSM coordinates.
- **Action:** Bottom sheet modal slides up (`wandy-mobile-source-detail.png`).
- **Content:**
  - Entity: `Chùa Trấn Quốc (Node #268491024)`
  - Coordinates: `21.0479° N, 105.8368° E` *(Demonstration metadata; in production, only rendered if provided by upstream source)*
  - License: `ODbL (Open Database License)`
  - Pipeline verification stamp: `Đã xác minh nguồn dữ liệu qua GoMate Data Pipeline` (Source Provenance Validation, NOT physical field inspection).
  - Data Honesty Alert: Clear statement that GoMate validates sources without claiming physical on-site audits or fabricating ratings.
- **Cancel / Back:** Tapping `[Đóng]` or tapping backdrop returns smoothly to chat without reloading.

---

### FLOW W06: View Place Detail
- **Entry:** User taps on any place card inside chat or clicks `[Xem địa điểm]`.
- **User Intent:** Deep dive into opening hours, address, reviews, photo gallery, and directions.
- **Action:** Navigates to `/places/:id` (Place Detail screen).
- **Success:** Place Detail opens with full hero gallery, verified badge, and mini map.
- **Back Navigation:** Tapping AppBar `← Quay lại` returns directly to Wandy chat with scroll position and conversation context fully intact.

---

### FLOW W07: Open Map with Results
- **Entry:** User taps `[Xem tất cả trên bản đồ]` below the multi-place list or carousel.
- **User Intent:** View spatial clustering, distances, and geographic relationships of the recommended places.
- **Action:** Navigates to Tab 2 (`Bản đồ`) passing recommended place IDs as filtered markers.
- **Success:** Map opens centered on the recommended cluster with POI pins highlighted.
- **Back Navigation:** Tapping Tab 3 (`Wandy AI`) returns to chat.

---

### FLOW W08: Add to Trip Action
- **Entry:** User taps `[Thêm vào chuyến đi]` on a place card.
- **User Intent:** Save the recommended spot into an existing or new travel itinerary.
- **Action:** Bottom sheet modal opens (`wandy-mobile-add-to-trip-action.png`).
- **Sheet Options:**
  - Lists existing trips (e.g. `Hà Nội 3N2Đ Mùa Thu • 15/10 - 17/10/2026`).
  - Button `+ Tạo chuyến đi mới`.
- **Selection:** User selects target trip and taps `[Tiếp tục (Chọn ngày) →]`.
- **Success:** Toast notification `✓ Đã thêm Chùa Trấn Quốc vào Ngày 2` appears; modal auto-dismisses.
- **Cancel / Back:** Tapping `✕` or backdrop dismisses modal with zero state mutation.

---

### FLOW W09: Open AI Planner Entry
- **Entry:** User taps `[✨ Lập lịch trình]` quick prompt or asks Wandy to build a full multi-day itinerary.
- **User Intent:** Launch automated itinerary generator.
- **Action:** Opens Planner Entry bridge screen (`wandy-mobile-planner-entry.png`).
- **Features Highlighted:**
  - `Tạo lịch trình cá nhân hóa`
  - `Tối ưu theo thời gian & ngân sách`
  - `Gợi ý địa điểm, ẩm thực, trải nghiệm`
- **CTA:** `[Bắt đầu lập lịch trình]` opens the Planner form (destination, duration, budget, pace).
- **Back Navigation:** Tapping `←` returns to Wandy chat.

---

### FLOW W10: Trip Context Awareness
- **Entry:** User accesses Wandy while currently planning or executing an active trip.
- **User Intent:** Ask contextual questions like `Chiều nay đi đâu gần và tiện đường?` without re-specifying city or dates.
- **UI Element:** Context Header Banner displays `Đang lập: Hà Nội 3N2Đ Mùa Thu • Ngày 2`.
- **Success:** Wandy tailors recommendations to Day 2's geographic route, remaining daily budget, and transit time.

---

### FLOW W11: Error & Retry Flow
- **Entry:** Network failure, timeout ($>30\text{s}$), or backend service degradation.
- **UI Element:** Error state card renders (`wandy-mobile-error.png`).
  - Icon: Disconnected Wi-Fi badge.
  - Headline: `Wandy đang gặp sự cố`.
  - Subtitle: `Không thể kết nối tới dịch vụ AI. Vui lòng kiểm tra kết nối mạng và thử lại.`
- **Actions:**
  - `[Thử lại]`: Re-dispatches the last pending query with exponential backoff.
  - `[Về màn hình chính]`: Navigates cleanly back to Home discovery feed.

---

### FLOW W12: Future Agent Confirmation Flow (Human-in-the-Loop Safeguard)
- **Scope & Status:** Strictly classified as **FUTURE AGENT UX** (Sprint 02+). Not part of current baseline RAG chat capability.
- **Entry:** Future autonomous AI agent proposes modifying user's saved trip (adding/swapping items, deleting slots, adjusting budget).
- **User Intent:** Safeguard itinerary integrity against unconfirmed AI hallucination or unwanted overwrites.
- **UI Element:** Modal dialog appears (`wandy-mobile-agent-confirmation.png` on mobile, `wandy-desktop-agent-confirmation.png` on desktop).
  - Scope Badge: `FUTURE AGENT UX • HUMAN-IN-THE-LOOP` (amber capsule).
  - Header: Wandy avatar icon with subtle halo.
  - Title: `Xác nhận hành động`.
  - Message: `Bạn có muốn thêm Chùa Trấn Quốc vào Hà Nội 3N2Đ Mùa Thu Ngày 2 (16/10/2026)?`
  - Safeguard Banner: `🛡️ Tác vụ sửa đổi lịch trình luôn yêu cầu người dùng xác nhận trực tiếp trước khi ghi dữ liệu.`
- **Actions:**
  - `[Xác nhận thêm vào chuyến đi]` (Solid Teal): User explicitly approves; executes trip update via API.
  - `[Hủy bỏ]` (Neutral): Aborts action and keeps itinerary untouched.
- **Golden Policy:** **ACTION MUTATION REQUIRES EXPLICIT USER CONFIRMATION.** Autonomous agents are NEVER permitted to delete trips, overwrite days, or add places solely from ambiguous chat prompts.

