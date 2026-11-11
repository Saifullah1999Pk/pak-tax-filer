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
| `/signup` (added 2026-11-09) | everyone | Email, password and "confirm password"; "demo data only" notice; link "Already have an account? Log in". Passwords that don't match are refused on the page. On success the user is logged in and goes to `/profile` (setup). If already logged in, goes to `/`. The login page links here with "Create an account". Covers FR-025, FR-027. |

Any page wrapped in `RequireAuth` redirects logged-out users to `/login?next=<path>`. Any API
`401` sends the user to `/login` with "Your session has ended, please log in again." The logout
button calls `POST /api/auth/logout`, then shows `/login`. Covers FR-012, FR-013.

## Taxpayer profile page (added 2026-11-04)

| Path | Who can see it | Behaviour |
|---|---|---|
| `/profile` | logged-in users | Setup (no profile) or edit form: tax-year select from `supported_tax_years`; ATL yes/no with nothing preselected and the link "Check your ATL status on FBR's website" (research R12, new tab); the notice "This app covers people who live in Pakistan and earn a salary."; the logout button. Saving without an ATL answer shows "Tell us whether you are on the ATL." After saving, goes to `next` or `/`. |

Every page wrapped in `RequireAuth`, except `/profile`, is also wrapped in `RequireProfile`, which
redirects to `/profile?next=<path>` while `"profile"` is `null`. The home page links to
`/profile`. Covers FR-019 to FR-021.
