# WanderAI — AI Architecture Guide

## Nguyên tắc cốt lõi

> Code quản lý hệ thống, Data cung cấp sự thật, API cung cấp dữ liệu bên ngoài,
> ML/Recommendation tìm ra cái phù hợp, còn AI Agent hiểu nhu cầu và điều phối
> tất cả để hỗ trợ người dùng.

## Phân chia: Code vs AI

### Code xử lý (deterministic — phải đúng 100%):
- Auth, Permission, JWT
- Database CRUD
- Payment, Transaction
- SOS execution
- Booking confirmation
- Budget calculation (phép tính số)
- Validation (date, budget > 0)

### AI xử lý (probabilistic — hiểu, suy luận, gợi ý):
- Hiểu nhu cầu du lịch
- Lập/điều chỉnh itinerary
- Đề xuất ngân sách
- Tìm và đề xuất địa điểm
- Phân tích/tóm tắt review
- Phân tích video → tạo trip
- Recommendation cá nhân hóa
- Companion matching + giải thích
- RAG Q&A kiến thức du lịch
- Context-aware travel assistant
- Safety recommendations

## 8 AI Engines

### 1. AI Travel Agent (Level 2 — Agent)
User request → Intent → Tools → Data → Reason → Response

### 2. AI Trip Planner
Destination + Date + Budget + Style → Structured Itinerary JSON

### 3. AI Re-planning
Trip context + Weather change / Budget change → Adjusted itinerary

### 4. AI Review Intelligence
1000 reviews → Sentiment → Aspect extraction → Summary

### 5. AI Video Analysis
Video → Speech-to-text → LLM → Extract destination/budget/places → Create trip

### 6. Recommendation Engine
User behavior (view/like/save/book) → User profile vector → Similar destinations

### 7. Companion Matching
User A trip + User B trip → Compatibility score + Explanation

### 8. Safety Intelligence
Destination + Weather + Activities → Safety suggestions

## 10-12 Agent Tools

```
search_destination()    — tìm điểm đến
search_places()         — tìm địa điểm tham quan
search_hotel()          — tìm khách sạn theo budget
search_tour()           — tìm tour
search_transport()      — tìm phương tiện
get_weather()           — thời tiết real-time
get_route()             — tính khoảng cách/thời gian
calculate_budget()      — tính chi phí
search_reviews()        — tìm/tóm tắt review
find_companions()       — tìm bạn đồng hành
get_trip_context()      — lấy context chuyến đi hiện tại
check_trip_safety()     — kiểm tra an toàn
```

## AI Agent Flow

```
User → Intent → Choose tools → Execute tools → Observe → Reason → Response
```

## AI KHÔNG được:
- Tự thực hiện SOS
- Tự xác nhận booking/payment
- Tự tạo SQL trực tiếp
- Tự quyết định permission
- Tự thanh toán

AI chỉ: đề xuất → user xác nhận → backend validate → execute

## Priority (nếu cắt scope)

```
⭐⭐⭐⭐⭐ AI Travel Agent
⭐⭐⭐⭐⭐ AI Trip Planner
⭐⭐⭐⭐⭐ AI Review Summary
⭐⭐⭐⭐⭐ Companion Matching
⭐⭐⭐⭐  Video → Trip
⭐⭐⭐⭐  Recommendation
⭐⭐⭐   RAG
⭐⭐⭐   Safety Intelligence
```
