# WanderAI Engineering Rules

## Architecture
- Mobile: Flutter + Riverpod
- Backend: NestJS + Prisma
- AI: FastAPI + tool-calling
- Database: PostgreSQL + PostGIS + pgvector
- Cache: Redis + BullMQ

## KHÔNG ĐƯỢC:
- Thêm MongoDB hoặc DB khác
- Thêm ORM khác ngoài Prisma
- Thêm state manager khác ngoài Riverpod
- Tạo service mới chưa được duyệt
- Sửa DB không có migration
- Bypass API layer (AI không truy cập DB trực tiếp)
- Viết secrets vào source code
- Thêm dependency không có lý do
- Sửa file ngoài phạm vi task
- Dùng `any` type bừa bãi (TypeScript)
- Để AI tự thực hiện SOS, payment, delete account
- Push trực tiếp vào main
- Commit mà chưa chạy test

## PHẢI:
- Đọc AGENTS.md trước khi code
- Lập kế hoạch trước khi sửa code (list files affected)
- Viết test cho mọi service/tool
- Dùng Conventional Commits (feat/fix/refactor/test/docs/chore)
- Mọi API có Swagger docs
- Mọi mutation check ownership
- Tiền lưu integer VND
- Ngày lưu UTC TIMESTAMPTZ
- Mỗi feature 1 branch: feature/ten-tinh-nang
- Format + Lint trước mỗi commit
- Mỗi external API call có timeout + fallback

## Quy trình AI Agent:
```
LLM → Tool → Backend Service → Authorization → Database
```
AI KHÔNG được có quyền tự ý tạo SQL hoặc gọi DB trực tiếp.
AI chỉ: đề xuất → chuẩn bị action → yêu cầu confirmation → backend validate → execute.

## Quy trình code:
```
1. Read AGENTS.md
2. Inspect current architecture
3. Identify affected files
4. Explain the implementation plan
5. Do not code until the plan is approved
6. Code within scope only
7. Run formatter
8. Run linter
9. Run tests
10. Fix all failures
11. Show changed files
12. Explain remaining risks
```

## Data Sources:
- Destinations/Places: OpenStreetMap Overpass API (ODbL license)
- Images: Unsplash API (Unsplash License)
- Reviews: Mendeley CX Vietnamese Hotel Reviews (CC BY 4.0)
- Tourism knowledge: Kaggle Vietnam Tourism v2
- Weather: Open-Meteo API (free, no key)
- Fake users: Faker.js with vi locale
