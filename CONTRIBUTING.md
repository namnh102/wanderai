# Contributing to WanderAI

## 10 Quy tắc vàng

1. No direct push to main.
2. Every feature starts with a GitHub Issue.
3. Every feature uses a dedicated branch.
4. Read AGENTS.md before coding.
5. AI-generated code must be reviewed.
6. Every business logic change needs tests.
7. Database changes require migrations.
8. No secrets in Git.
9. No direct database access from AI agents.
10. Code is DONE only when CI passes.

## Git Workflow

```
main        ← production-ready, chỉ merge từ develop
develop     ← integration branch
feature/*   ← mỗi tính năng 1 branch
```

### Branch naming
```
feature/ai-trip-planner
feature/auth-login
feature/safety-sos
fix/gemini-function-calling
```

### Commit convention
```
feat:      tính năng mới
fix:       sửa lỗi
refactor:  refactor code
test:      thêm/sửa test
docs:      tài liệu
chore:     config, dependencies
```

### Commit size
Nhỏ. Một commit = một việc cụ thể.
```
# Đúng
feat: add trip schema
feat: add trip creation API
test: add trip service tests

# Sai
feat: complete entire backend
```

## Trước khi commit

```bash
# Flutter
dart format .
flutter analyze

# NestJS
npm run format
npm run lint
npm run build

# Python
ruff format .
ruff check .
```

Không merge nếu còn lint error.

## Pull Request Checklist

```
- [ ] Requirement implemented
- [ ] Formatter passed
- [ ] Linter passed
- [ ] Unit tests passed
- [ ] Integration tests passed (if applicable)
- [ ] Swagger updated (if API changed)
- [ ] Migration added (if DB changed)
- [ ] No secrets in code
- [ ] No unrelated file changes
- [ ] Reviewed by teammate
```

## Definition of Done

Mỗi task chỉ được đánh DONE khi:
- ✅ Requirement đúng
- ✅ Code đúng architecture (đọc AGENTS.md)
- ✅ Type-safe (không dùng `any` bừa)
- ✅ Formatted + Lint passed
- ✅ Unit test written + passed
- ✅ API docs updated (Swagger)
- ✅ No secret in code
- ✅ No unrelated changes
- ✅ PR reviewed
- ✅ CI passed

## Quy trình cho mỗi feature

```
GitHub Issue → Specification → API contract → Branch →
AI đọc project → AI lập plan → Approve plan →
AI code → Format → Lint → Unit test → Integration test →
PR → Human review → CI → Merge develop
```

## Environment

```
.env          ← KHÔNG commit (trong .gitignore)
.env.example  ← Commit (template không có giá trị thật)
```
