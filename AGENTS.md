# WanderAI — Engineering Rules

> Tệp này là BỘ LUẬT KỸ THUẬT bắt buộc cho toàn bộ team và AI coding agents.
> Mọi code thay đổi PHẢI tuân thủ các quy tắc dưới đây.

## Tech Stack (KHÔNG ĐƯỢC THAY ĐỔI)

- **Mobile:** Flutter 3.x + Riverpod 2.0 + GoRouter + Dio
- **Backend:** NestJS 10+ + TypeScript + Prisma ORM
- **AI Service:** FastAPI + Python 3.11+ + Pydantic v2
- **Database:** PostgreSQL 16 + PostGIS + pgvector (MỘT database duy nhất)
- **Cache/Queue:** Redis 7 + BullMQ
- **Media:** Cloudinary
- **Deploy:** Supabase (DB) + Railway (API services)

## KHÔNG ĐƯỢC

- Thêm MongoDB, Firebase Firestore, hoặc bất kỳ database khác
- Thêm ORM khác ngoài Prisma (không TypeORM, không Drizzle, không Sequelize)
- Thêm state manager khác (không BLoC, không GetX, không Provider cũ)
- Dùng GraphQL (chỉ dùng REST API)
- Tạo microservice mới (giữ modular monolith)
- Sửa database schema mà không tạo Prisma migration
- Bypass NestJS API layer (Flutter KHÔNG gọi thẳng FastAPI)
- Viết secrets, API keys, passwords vào source code
- Commit file .env hoặc MY_KEYS.txt
- Thêm dependency mới mà không có lý do trong PR description
- Push trực tiếp lên main hoặc develop
- Commit code AI generate mà chưa review và test

## PHẢI

- Viết test cho mọi service method và AI tool
- Dùng Conventional Commits: `feat:` | `fix:` | `refactor:` | `test:` | `docs:` | `chore:`
- Mọi API endpoint phải có Swagger decorator (`@ApiTags`, `@ApiOperation`, `@ApiResponse`)
- Mọi DTO phải dùng `class-validator` decorators
- Mọi mutation phải kiểm tra ownership (user chỉ sửa/xóa dữ liệu của mình)
- Mọi PR phải có: What changed / Why / Tests / Known limitations

## Database Rules

- **ID:** UUID v4 (`gen_random_uuid()`)
- **Tiền tệ:** Số nguyên VND (`2000000` = 2 triệu), KHÔNG DÙNG FLOAT
- **Thời gian:** `TIMESTAMPTZ` (UTC), frontend convert sang `Asia/Ho_Chi_Minh`
- **Soft delete:** `deleted_at TIMESTAMPTZ` (không xóa thật)
- **Enum:** Dùng Prisma enum
- **Tọa độ:** `latitude Float` + `longitude Float`
- **Vector:** `vector(384)` cho MiniLM hoặc `vector(1536)` cho OpenAI embedding

## AI Rules

- LLM **KHÔNG ĐƯỢC** tự bịa dữ liệu live (giá, thời tiết, booking PHẢI từ Tool)
- Luồng bắt buộc: Agent → Tool → Service → Auth → DB
- Mọi AI response phải qua Pydantic validation
- Rate limit: 10 AI requests/phút/user cho chat, 5/phút cho planner
- Prompt injection guard PHẢI bật (regex filter input)
- System prompt phải có version number
- AI response phải disclaimer "thông tin tham khảo, kiểm tra trước khi đặt"

## Mobile Rules

- i18n cho mọi user-facing text (Vietnamese + English)
- Feature-first folder structure (`features/auth/`, `features/home/`, ...)
- Riverpod `AsyncNotifier` cho API calls
- GoRouter cho navigation + auth redirect
- Dio interceptor tự động refresh JWT token
- Không hardcode strings, dùng `AppLocalizations`

## Git Flow

- `main` ← production, chỉ merge từ develop
- `develop` ← integration, merge features vào đây
- `feature/*` ← mỗi tính năng 1 branch
- `fix/*` ← bug fixes
