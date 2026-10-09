# Contributing to Gomate

## Git Flow

- `main` ← production, chỉ merge từ develop
- `develop` ← integration branch
- `feature/*` ← mỗi tính năng 1 branch
- `fix/*` ← bug fixes

## Branch Naming

```
feature/auth-login
feature/ai-chat-v1
feature/home-screen
fix/jwt-refresh-bug
```

## Commit Convention (Conventional Commits)

```
feat: add login screen
fix: resolve JWT token refresh issue
refactor: extract auth service
test: add unit tests for trip service
docs: update API documentation
chore: upgrade dependencies
```

## Pull Request

Mỗi PR cần có:
1. **What** — Thay đổi gì
2. **Why** — Tại sao thay đổi
3. **Tests** — Đã test gì
4. **Screenshots** — Nếu có UI changes

## Code Style

- TypeScript: ESLint + Prettier
- Python: Black + isort
- Dart: flutter analyze
- Tất cả format trước khi commit

## Review Checklist

- [ ] Code đã format (prettier/black/dart format)
- [ ] Không có console.log/print debug
- [ ] Có test cho logic mới
- [ ] Swagger decorators cho API endpoints mới
- [ ] class-validator cho DTOs mới
- [ ] Không hardcode secrets
