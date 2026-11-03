# Research: Authentication Foundation (002)

Each decision: what was chosen, why, and what else was considered.

## R1. Password hashing

- **Decision:** `pwdlib` with the Argon2 hasher.
- **Rationale:** Argon2 is the current recommended password hash (OWASP). `pwdlib` is what
  FastAPI's own security tutorial now uses; it is small and maintained.
- **Alternatives:** `passlib` (unmaintained, breaks on newer Python); bcrypt (fine, but older and
  limited to 72-byte passwords); writing our own on `argon2-cffi` (more code for no gain).

## R2. Session tokens and cookie

- **Decision:** at login, generate a random token (`secrets.token_urlsafe(32)`); store only its
  SHA-256 hash in the `sessions` table; send the token in a cookie named `session` with
  `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` of 7 days, and `Secure` on by default (a
  setting turns it off only for local development over plain HTTP).
- **Rationale:** an opaque token reveals nothing; hashing it means a leaked database can't be
  used to log in; `HttpOnly` keeps scripts from reading it.
- **Alternatives:** signed cookie holding the user ID (can't be revoked on logout); storing the
  raw token (a database leak would expose live sessions).

## R3. Cross-site request forgery (CSRF)

- **Decision:** rely on `SameSite=Lax` plus requiring `Content-Type: application/json` on all
  state-changing requests (login, logout). No CSRF token in this feature.
- **Rationale:** `Lax` stops the cookie being sent on cross-site POSTs, and a cross-site page
  can't send a JSON body without a CORS preflight that our backend won't approve. This is the
  standard defence for a same-origin JSON API.
- **Alternatives:** CSRF tokens (extra moving parts with no added protection here).

## R4. Login throttling

- **Decision:** a `login_failures` table records each failed attempt (normalized email,
  timestamp). Before checking a password, count failures for that email in the last 15 minutes;
  if 10 or more, refuse with `429` and a generic "try again later" message. Unknown emails are
  counted the same way.
- **Rationale:** survives restarts and works across several backend processes; simple to test.
  Treating unknown emails the same avoids revealing which emails exist.
- **Alternatives:** in-memory counter (lost on restart, per-process); Redis (a new stack
  component for one counter).

## R5. Equal treatment of unknown emails

- **Decision:** when the email is unknown, still run a password verification against a fixed
  dummy hash, then return the same `401` message as for a wrong password.
- **Rationale:** without this, unknown emails answer faster, which leaks which emails exist.

## R6. Session expiry

- **Decision:** absolute expiry 7 days after login, stored as `expires_at` and checked on every
  request. Expired sessions are deleted when next used; no background cleanup job yet.
- **Alternatives:** sliding expiry (spec says 7 days after login); a cleanup scheduler (not
  needed at demo scale).

## R7. Creating demo users

- **Decision:** `python -m app.cli create-user --email <email>`, prompting for the password
  (hidden input), using standard-library `argparse` and `getpass`.
- **Rationale:** passwords never land in shell history; no new dependency.
- **Alternatives:** Typer/Click (an extra dependency for one command); password as an argument
  (ends up in shell history).

## R8. API layout and errors

- **Decision:** auth endpoints under `/api/auth/` (`login`, `logout`, `me`). Errors use
  FastAPI's default shape `{"detail": "<message>"}`. Vite's dev server proxies `/api` to the
  backend, so the browser sees one origin.
- **Rationale:** a single `/api` prefix keeps the proxy rule simple and is the start of the
  API conventions requested in issue #4.

## R9. Frontend routing and auth state

- **Decision:** React Router for pages; an auth context that calls `GET /api/auth/me` on load;
  a `RequireAuth` wrapper that sends logged-out users to `/login?next=<page>`; one fetch helper
  that sends the user to `/login` whenever an API call returns `401`.
- **Alternatives:** storing "logged in" in local storage (gets out of sync with the real
  session); a larger state library (unneeded for one piece of state).

## R10. Testing against the database

- **Decision:** backend tests use a separate `pak_tax_filer_test` database in the same Postgres
  container, migrated once per test run, with each test inside a rolled-back transaction.
- **Rationale:** tests hit real PostgreSQL behaviour (unique indexes, timestamps) without
  touching development data.
- **Alternatives:** SQLite for tests (behaves differently from PostgreSQL); mocking the
  database (misses real constraint behaviour).
