# Quickstart: validating Authentication Foundation (002)

**Prerequisites:** feature 001 running (`docker compose up -d`).

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.cli create-user --email demo@example.com
```

## 1. Log in and out (User Story 1)

| Step | Expected |
|---|---|
| Create the same user again as `Demo@Example.com` | Refused, exit code 1 |
| `POST /api/auth/login` with the right password | `200`, `session` cookie set |
| Same with a wrong password, then with `nobody@example.com` | Identical `401` message |
| `POST /api/auth/logout`, then `GET /api/auth/me` with the old cookie | `204`, then `401` |
| 10 wrong passwords, then the right one | 11th attempt `429`; works after 15 minutes |

## 2. Protected APIs (User Story 2)

| Step | Expected |
|---|---|
| `GET /api/auth/me` with no cookie | `401` `{"detail": "Not logged in."}` |
| With a valid cookie | `200` `{"email": "demo@example.com"}` |
| With a session whose `expires_at` is in the past | `401` |

## 3. Frontend (User Story 3)

1. Open `http://localhost:5173/` logged out → sent to `/login`; demo notice visible.
2. Log in → back on `/`, showing "Logged in as demo@example.com" and a logout button.
3. Log out → on `/login`; pressing Back doesn't show the home page's data.
4. Log in, delete the session row in the database, click anything that calls the API → sent to
   `/login` with the session-ended message.

## 4. Tests

```bash
docker compose exec backend pytest
docker compose exec frontend npm test
```

Both pass. Contracts: [auth-api.md](contracts/auth-api.md),
[cli-and-ui.md](contracts/cli-and-ui.md).
