# 002 Authentication Foundation: Design

**Date:** 2026-11-03 · **Status:** Proposed · **Feature:** 002 (README milestone 2, first
increment) · **Governed by:** [Constitution v1.2.0](../../../.specify/memory/constitution.md)

## Intent

A clean, working authentication foundation that later increments extend, as requested by the
lead: a user model, login/logout, session management, protected APIs and frontend integration,
built as custom authentication in our FastAPI backend.

## Scope

- **User model:** email (unique, case-insensitive) and a protected password.
- **Creating users:** a developer command creates demo users, since sign-up is a later
  increment.
- **Login / logout:** email + password; logout ends the session immediately.
- **Session management:** sessions expire after 7 days; repeated failed logins are throttled.
- **Protected APIs:** a reusable check that refuses requests without a valid session, plus one
  example protected endpoint ("who am I").
- **Frontend integration:** a login page, pages that require login, a logout button, and a
  return to the login page when a session ends or expires.

## Later increments (out of scope here)

Sign-up, email verification, forgot password and password reset (lead's instruction); the
taxpayer profile (its own feature, built on this one); AWS Cognito (out of scope per the lead).

## Decisions

- **Session cookie** (decided by Saifullah): sessions stored in the database; the browser gets a
  secure, HttpOnly cookie; logout deletes the session. Passwords hashed with Argon2. Login logic
  is our own small module on standard libraries, not an all-in-one auth framework.
- **Throttling** (decided by Saifullah): after 10 failed logins for an email within 15 minutes,
  further attempts wait until the 15 minutes pass.
- Login errors don't reveal whether an email is registered. *(Builder's call.)*
- Passwords need at least 8 characters, no composition rules (NIST guidance). *(Builder's
  call.)*
- The frontend reaches the backend through Vite's dev proxy, so the cookie works without
  cross-origin setup. *(Builder's call.)*
- Demo users only (Principle V); the user model holds no identity fields. *(Builder's call.)*

## Approaches

| Approach | Trade-off | Outcome |
|---|---|---|
| Session cookie | Simple, resistant to token theft by scripts, real logout; needs a sessions table | **Chosen** |
| JWT tokens | Useful for many client types or servers; in a browser the token can be stolen by a script, and logout doesn't truly revoke it | Rejected for now |
| AWS Cognito | Managed reset, verification and MFA; but needs AWS, can't run offline in Docker Compose, stores emails with a third party | Out of scope (lead) |

**Why cookies suit our APIs:** the only client of the user-facing API is our own React app in
the browser, where an HttpOnly cookie is the safest place for a credential. The MCP server (006)
and agentic workflow (007) run on the server and call the tax engine directly. If non-browser
clients (a mobile app, third-party API access) or a managed provider are added later, token
auth can be added for them without changing the browser flow.

## Done when

- A demo user created by the developer command can log in, reach a protected page and API, and
  log out.
- After logout or expiry, the old session no longer works, on the API and in the UI.
- Requests without a valid session to protected APIs are refused.
- Passwords are never stored or logged in plain text.

## Left to the plan

Table design and migrations, API routes, React routing, session-cookie signing, and test
structure.
