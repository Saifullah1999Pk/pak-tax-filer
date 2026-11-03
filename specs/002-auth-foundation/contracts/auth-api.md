# Contract: Auth API

Base path `/api/auth`. Request and response bodies are JSON. Errors are
`{"detail": "<message>"}`. The session is carried only by the `session` cookie
(see [research.md](../research.md), R2).

## POST /api/auth/login

Request (`Content-Type: application/json` required):

```json
{ "email": "demo@example.com", "password": "at-least-8-chars" }
```

| Outcome | Status | Body | Cookie |
|---|---|---|---|
| Success | `200` | `{"email": "demo@example.com"}` | sets `session` |
| Unknown email or wrong password | `401` | `{"detail": "Invalid email or password."}` | none |
| 10+ failures for this email in 15 min | `429` | `{"detail": "Too many attempts. Try again later."}` | none |
| Missing or invalid fields | `422` | FastAPI validation error | none |

The email is trimmed and lower-cased before use. A failed attempt (401) is recorded for
throttling; a throttled attempt (429) does not check the password.

## POST /api/auth/logout

No body required (`Content-Type: application/json`). Always `204`. Deletes the current session if
there is one and clears the `session` cookie.

## GET /api/auth/me

Protected. With a valid session: `200` `{"email": "demo@example.com"}`. Otherwise: `401`
`{"detail": "Not logged in."}`.

## Protecting other endpoints

Any endpoint that depends on `current_user` returns `401` `{"detail": "Not logged in."}` when the
session is missing, unknown, logged out or expired, and otherwise receives the logged-in user.
Covers FR-010.
