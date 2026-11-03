# Quickstart: validating Repo Foundations (001)

**Prerequisites:** Docker + Docker Compose, `uv`, Node 24+. (Python is provided by `uv`.)

## 1. Start the app (User Story 1, SC-001)

```bash
git clone <repo> && cd pak-tax-filer
docker compose up -d
docker compose exec backend alembic upgrade head
```

| Check | Expected |
|---|---|
| `curl http://localhost:8000/health` | `{"status":"ok"}` ([contract](contracts/health.md)) |
| Open `http://localhost:5173` | Placeholder page |
| `docker compose exec db psql -U postgres -c "\dx"` | `vector` listed |
| `docker compose exec backend pytest` | All tests pass |
| `docker compose exec frontend npm test` | All tests pass |

## 2. Tax-rates guard (User Story 2, SC-002)

In Claude Code, in this repo:

1. Ask Claude to create `backend/app/tax/rates/example.py`. **Expected:** an approval prompt
   with the FBR reason. Reject → file not created. Repeat and approve → file created.
2. Ask Claude to run `ls backend/app/tax/rates`. **Expected:** the same approval prompt.
3. Ask Claude to edit any file outside that folder. **Expected:** no tax-rates prompt.

## 3. Shared rules (User Story 3, SC-003, SC-004)

1. Ask Claude to write a badly indented `.py` file. **Expected:** saved formatted.
2. Ask Claude to run `pytest`. **Expected:** runs without asking.
3. Ask Claude to `git push`. **Expected:** asks first.
4. Ask Claude to read `.env`. **Expected:** refused.

## 4. Cross-platform (SC-006)

Repeat sections 2 and 3 on a second OS (Windows and macOS/Linux). **Expected:** same results.
