# Contract: Demo-user command and frontend routes

## Command: create a demo user

```bash
docker compose exec backend python -m app.cli create-user --email demo@example.com
```

- Prompts twice for the password (hidden input); refuses if the two don't match or it is under
  8 characters.
- Refuses, creating nothing, if the email (trimmed, any letter case) already exists.
- Prints `Created user demo@example.com` on success. Exit code `0` on success, `1` on refusal.
- Covers FR-002, FR-004.

## Frontend routes

| Path | Who can see it | Behaviour |
|---|---|---|
| `/login` | everyone | Email + password form; "demo data only" notice (FR-014); a note that password reset isn't available yet. If already logged in, goes to `/`. After login, goes to `next` or `/`. |
| `/` | logged-in users | Home page showing "Logged in as <email>" and the logout button |

Any page wrapped in `RequireAuth` redirects logged-out users to `/login?next=<path>`. Any API
`401` sends the user to `/login` with "Your session has ended, please log in again." The logout
button calls `POST /api/auth/logout`, then shows `/login`. Covers FR-012, FR-013.
