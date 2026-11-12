# WanderAI (GoMate) — AI Travel & Social Companion

> Ứng dụng du lịch thông minh kết hợp AI Copilot có đối chiếu kho tri thức (RAG), lập lịch trình tự động và khám phá điểm đến Việt Nam.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile | Flutter (Dart SDK `^3.1.0`) + Riverpod 2 + GoRouter 14 + Dio 5 |
| Backend | NestJS 10 + Prisma 5 + PostgreSQL 16 (`postgis`, `vector`, `uuid-ossp`) |
| AI Service | FastAPI (Python 3.11) + `google-genai` (Gemini) + `pgvector` RAG |
| Cache | Redis 7 |
| CI | GitHub Actions (`.github/workflows/ci.yml` — PostgreSQL 16 + PostGIS + pgvector) |

## Yêu cầu môi trường (Prerequisites)

- **Node.js 22** + **pnpm 10** *(lưu ý: repo không dùng `pnpm-workspace.yaml` ở thư mục gốc; chạy lệnh `pnpm` trực tiếp trong `apps/backend` hoặc dùng `pnpm --dir apps/backend ...`)*
- **Python 3.11** + `pip`
- **Flutter** (stable channel; Android SDK API 35 khi build/chạy Android)
- **Docker Desktop** (cung cấp PostgreSQL 16 + PostGIS + `pgvector` và Redis 7 cho môi trường phát triển cục bộ)

## Cấu trúc project

```text
wanderai/
├── apps/
│   ├── backend/
│   │   ├── prisma/           Prisma schema chính thức, migrations & tài liệu rollback
│   │   ├── src/              NestJS API gateway, JWT auth & AI internal-auth proxy (port 3000)
│   │   └── test/             Backend E2E suites (Jest + Supertest)
│   ├── ai-service/           FastAPI AI + pgvector RAG + Gemini tools (internal port 8000)
│   └── mobile/               Flutter client (Android / Web / Desktop)
├── database/
│   ├── init.sql              Khởi tạo PostgreSQL extensions (postgis, vector, uuid-ossp)
│   ├── seed/                 Dữ liệu seed JSON ban đầu (categories, destinations, places)
│   └── prisma/               Schema tham chiếu cũ (không dùng cho runtime/migrations hiện tại)
├── scripts/                  CI seed fail-closed, freeze checksum, OpenAPI export
├── docs/                     Tài liệu vận hành, API, kiểm thử và nghiên cứu (W05–W07)
├── .github/workflows/ci.yml  GitHub Actions CI (backend, ai-service, mobile, data-contract)
├── docker-compose.yml        PostgreSQL + Redis local
└── AGENTS.md                 Quy tắc kỹ thuật dự án
```

## Chạy project (Local Development)

Chi tiết đầy đủ về biến môi trường, kiểm thử và giới hạn vận hành xem tại [docs/w3/developer-runbook.md](docs/w3/developer-runbook.md).

### 1. Database & Redis

```bash
docker compose up -d
```
*(Đảm bảo PostgreSQL đã bật đầy đủ các extension trong `database/init.sql`: `postgis`, `vector`, `uuid-ossp`.)*

### 2. Backend (`apps/backend`)

Backend áp dụng cơ chế **fail-closed** khi khởi động và khi gọi AI proxy: ba biến `JWT_SECRET`, `JWT_REFRESH_SECRET` và `AI_INTERNAL_AUTH_SECRET` bắt buộc phải được cấu hình bằng các chuỗi mạnh (`>= 32` ký tự, tối thiểu `8` ký tự phân biệt, không dùng giá trị mẫu trong `.env.example` và **3 khóa phải hoàn toàn khác nhau**).

```bash
cd apps/backend
cp ../../.env.example .env      # Điền DATABASE_URL và 3 khóa bí mật >= 32 ký tự khác nhau
pnpm install --frozen-lockfile
pnpm exec prisma generate
pnpm exec prisma migrate status # Kiểm tra trạng thái migration và đúng DATABASE_URL đích
pnpm exec prisma migrate deploy # Áp dụng SQL migrations (có thể thay đổi schema & dữ liệu hiện có!)

# Chỉ chạy trên DB dev mới tinh (chưa có dữ liệu):
# pnpm exec prisma db seed      # Tạo destinations/categories ban đầu (không chạy lặp lại)
# pnpm run db:import-curated    # Upsert dữ liệu địa điểm đã chuẩn hóa

pnpm start:dev
# → http://localhost:3000/api (Swagger)
```

> **Cảnh báo an toàn dữ liệu & migration:**
> - `prisma migrate deploy` có thể thay đổi schema và dữ liệu hiện có: trước khi chạy trên bất kỳ DB dùng chung/nghiên cứu nào phải kiểm tra môi trường, `DATABASE_URL` đích, nội dung migration và phương án backup/recovery (`pg_dump` + [`ROLLBACK_AND_RECOVERY.md`](apps/backend/prisma/migrations/20261110000000_sync_schema_drift/ROLLBACK_AND_RECOVERY.md)). Không tự chạy migration trên production.
> - Tuyệt đối không trỏ `scripts/seed_ci_database.py` vào database phát triển (`wanderai`). Script CI này thực hiện `TRUNCATE ... CASCADE` và được bảo vệ fail-closed chỉ dành riêng cho database kiểm thử cô lập `wanderai_ci_*`.

### 3. AI Service (`apps/ai-service`)

FastAPI là dịch vụ nội bộ, chỉ nhận yêu cầu có chữ ký HMAC-SHA256 (`X-WanderAI-Internal-Assertion`) từ NestJS thông qua cùng `AI_INTERNAL_AUTH_SECRET`. Không public cổng `8000` trực tiếp cho mobile client.

```bash
cd apps/ai-service
cp ../../.env.example .env      # Đồng bộ AI_INTERNAL_AUTH_SECRET với backend; điền GEMINI_API_KEY nếu gọi LLM thật
pip install -r requirements.txt # Dùng requirements-dev.txt nếu chạy pytest / ruff
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# → http://127.0.0.1:8000/docs (Internal FastAPI docs)
```

### 4. Mobile (`apps/mobile`) & cấu hình `API_BASE_URL`

Ứng dụng Flutter kết nối **duy nhất** tới NestJS API qua `--dart-define=API_BASE_URL=...` (không gọi trực tiếp FastAPI `:8000`):

```bash
cd apps/mobile
flutter pub get

# 1) Desktop / Web debug (mặc định nếu không truyền trên bản debug):
flutter run --dart-define=API_BASE_URL=http://localhost:3000

# 2) Android Emulator debug (AVD ánh xạ host loopback qua 10.0.2.2):
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:3000

# 3) Thiết bị Android vật lý cùng mạng Wi-Fi / LAN (chỉ bản debug; cần chạy backend với HOST=0.0.0.0):
flutter run --dart-define=API_BASE_URL=http://<DEV_MACHINE_LAN_IP>:3000

# 4) Bản build Release / Profile (bắt buộc HTTPS domain thật; tự động fail-closed nếu thiếu hoặc dùng HTTP/localhost/10.0.2.2):
flutter build apk --release --dart-define=API_BASE_URL=https://<YOUR_BACKEND_DOMAIN>
```

**Giới hạn xác minh Android hiện tại:**
- Smoke trên Android 15 Emulator ở trạng thái agent-reported `PASS` (đang bổ sung independent raw-evidence verification) và sử dụng offline-stubbed LLM (không phải nghiệm thu factuality khoa học W07).
- Smoke trên thiết bị Android vật lý hiện ở trạng thái `BLOCKED_BY_ENVIRONMENT`.
- Release/profile đã có kiểm tra fail-closed lúc runtime (`AppConstants.resolveApiBaseUrl` + `usesCleartextTraffic="false"`), chưa có kiểm tra compile-time ở tầng Gradle; cấu hình ký APK `release` vẫn đang dùng khóa `debug` (chưa dùng để phát hành production) và chưa xác minh bắt tay TLS trên HTTPS staging thật.

## Team

| Role | Nhiệm vụ |
|------|----------|
| P1 — PM + Mobile Lead | Flutter UI, UX, quản lý tiến độ |
| P2 — Backend Lead | NestJS API, Prisma, database |
| P3 — AI Lead | FastAPI, LLM, RAG, tools |
| P4 — Full-stack + DevOps | CI/CD, Docker, deploy, hỗ trợ chung |

## License

Private — Đồ án tốt nghiệp 2026
