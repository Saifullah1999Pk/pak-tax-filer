# Quickstart: validating Authentication Foundation and Taxpayer Profile (002)

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

## 4. Taxpayer profile (User Stories 4 and 5)

1. Log in as a new demo user → sent to `/profile`; opening `/` brings you back to `/profile`.
2. Tax year offers only 2025-26; ATL yes/no has nothing selected; the FBR link opens FBR's
   "Check Active Taxpayer Status" page in a new tab; the residency notice and logout button are
   shown. Saving without an ATL answer is refused.
3. Choose "No" and save → the home page opens, in under 1 minute from login (SC-007). Reopen
   `/profile` → "No".
4. Change to "Yes", save, reopen → "Yes"; nothing else changed.
5. Log out from `/profile` with a new user → works; the step reappears at the next login.

## 5. Tests

```bash
docker compose exec backend pytest
docker compose exec frontend npm test
```

Both pass. Contracts: [auth-api.md](contracts/auth-api.md),
[cli-and-ui.md](contracts/cli-and-ui.md).
