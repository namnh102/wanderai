# WanderAI — AI Travel & Social Companion

> Ứng dụng du lịch thông minh kết hợp AI chatbot, lập kế hoạch tự động, video feed cộng đồng và tìm bạn đồng hành.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile | Flutter 3.47 + Riverpod 2.0 + GoRouter |
| Backend | NestJS 10 + Prisma + PostgreSQL 16 |
| AI Service | FastAPI + Gemini/OpenAI + pgvector RAG |
| Cache | Redis 7 |
| Media | Cloudinary |
| Deploy | Supabase (DB) + Railway (API) |

## Cấu trúc project

```
wanderai/
├── apps/
│   ├── backend/          NestJS API (port 3000)
│   ├── ai-service/       FastAPI AI (port 8000)
│   └── mobile/           Flutter app
├── database/
│   ├── prisma/           Schema + migrations
│   └── seed/             Dữ liệu mẫu VN
├── docs/                 Tài liệu
├── docker-compose.yml    PostgreSQL + Redis
└── AGENTS.md             Luật kỹ thuật
```

## Chạy project

### 1. Database

```bash
docker compose up -d
```

### 2. Backend

```bash
cd apps/backend
cp ../.env.example .env   # Điền API keys
pnpm install
npx prisma migrate dev
npx prisma db seed
pnpm start:dev
# → http://localhost:3000/api (Swagger)
```

### 3. AI Service

```bash
cd apps/ai-service
cp ../.env.example .env   # Điền Gemini key
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs (FastAPI docs)
```

### 4. Mobile

```bash
cd apps/mobile
flutter pub get
flutter run
```

## Team

| Role | Nhiệm vụ |
|------|----------|
| P1 — PM + Mobile Lead | Flutter UI, UX, quản lý tiến độ |
| P2 — Backend Lead | NestJS API, Prisma, database |
| P3 — AI Lead | FastAPI, LLM, RAG, tools |
| P4 — Full-stack + DevOps | CI/CD, Docker, deploy, hỗ trợ chung |

## License

Private — Đồ án tốt nghiệp 2026
