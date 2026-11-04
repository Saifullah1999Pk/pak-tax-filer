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

Sign-up, email verification, forgot password and password reset (lead's instruction); AWS
Cognito (out of scope per the lead). The taxpayer profile was added to this feature on
2026-11-04 (addendum below).

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

## Addendum (2026-11-04): taxpayer profile

README milestone 2 is "Taxpayer profile + auth", and the README's MVP has "one taxpayer profile,
one configurable tax year (TY2026)". The 8 README milestones are the 8 features, so the profile
is added here (User Stories 4 and 5), not as a separate feature. Brainstormed with Saifullah:

- **Fields:** tax year (one option, 2025-26) and ATL status (on FBR's Active Taxpayers' List:
  yes/no). Both required; no "not sure". A link to FBR's "Check Active Taxpayer Status" page
  sits beside the ATL question.
- **Residency** is a one-line notice ("This app covers people who live in Pakistan and earn a
  salary."), not a question: non-residents are outside the MVP.
- **No identity fields** (name, CNIC, NTN): Principle V.
- **When:** a "set up your profile" step on first login, before anything else; changeable any
  time; a change applies to the next calculation and changes nothing already saved.
- **Enforced by the backend**, not only the UI: helpers let later features read the profile or
  refuse without one.
- **Effect on 003–006:** they read the tax year and ATL status from the profile instead of a
  setting or a question (their specs are updated; constitution: "an update to every affected
  spec or plan").

| Approach | Trade-off | Outcome |
|---|---|---|
| **A. Separate profile table, one row per account** | One more table; keeps `users` login-only | **Chosen** (Saifullah) |
| B. Columns on `users` | Less code; mixes tax answers into the login table | Rejected |
| C. Answers per tax year | Ready for TY2027; builds for years the MVP doesn't have | Rejected for now; A → C later is one migration |

## Left to the plan

Table design and migrations, API routes, React routing, session-cookie signing, and test
structure.
