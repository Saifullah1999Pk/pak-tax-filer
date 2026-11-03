# 002 Taxpayer Profile + Auth: Design

**Date:** 2026-11-03 · **Status:** Proposed · **Feature:** 002 (README milestone 2) ·
**Governed by:** [Constitution v1.2.0](../../../.specify/memory/constitution.md)

## Intent

README milestone 2: "Taxpayer profile + auth". A user can sign up, log in and manage their one
taxpayer profile, visible only to them. It holds only what later features need to calculate
tax, so no real personal data can be entered (Principle V).

## Scope

- **Account:** sign up and log in with email + password; log out.
- **Profile** (exactly one per account):
  - **Tax year:** TY2026, stored as a value so later years can be added.
  - **ATL status:** whether the user is on FBR's Active Taxpayer List (affects §151 rates in
    feature 004).
  - **Display name** (optional): free text used to greet the user; not a legal name.
- **Privacy:** a user can only see and change their own account and profile. A clear
  "demo data only" notice appears on sign-up and on the profile page.

## Out of scope

Identity fields (legal name, CNIC, NTN, address); password reset and email verification (no
email service in the MVP); multiple profiles per account; admin users; non-resident taxpayers.

## Decisions

- **Profile holds calculation inputs only** (decided by Saifullah): no identity fields until a
  legal review allows real data.
- **Login uses a session cookie** (decided by Saifullah): the backend stores sessions in the
  database and gives the browser a secure, HttpOnly cookie; logout deletes the session.
  Passwords are hashed with Argon2. Login logic is our own small module on standard libraries,
  not an all-in-one auth framework.
- **Resident salaried individuals only.** *(Builder's call; matches the README's MVP.)*
- Emails are unique and compared case-insensitively; passwords need at least 8 characters, with
  no other composition rules (current NIST guidance). *(Builder's call.)*
- Sessions expire after 7 days. *(Builder's call.)*
- The profile is created at sign-up with tax year TY2026 and ATL status **unanswered**; the
  user must choose yes or no, since guessing would change the tax. *(Builder's call.)*
- Account deletion is out of scope for the MVP. *(Builder's call.)*
- The frontend reaches the backend through Vite's dev proxy, so the browser sees one origin and
  the cookie works without cross-origin setup. *(Builder's call.)*
- Login errors don't reveal whether an email is registered. *(Builder's call.)*

## Approaches

| Approach | Trade-off | Outcome |
|---|---|---|
| Session cookie | Simple, resistant to token theft by scripts, real logout; needs a sessions table | **Chosen** |
| JWT tokens | Popular; token in the browser can be stolen by a script, logout doesn't truly revoke | Rejected |
| AWS Cognito | Managed sign-up/sign-in with password reset, email verification and MFA built in; but needs an AWS account and a new stack component, can't run offline in Docker Compose, stores user emails with a third party (Principle V), and adds AWS lock-in | Rejected for the MVP; revisit if real users, password reset or MFA become requirements |
| Hosted login (Auth0, Clerk) | Same trade-offs as Cognito | Rejected |

**Why cookies suit our APIs:** the only client of the user-facing API is our own React app in
the browser, where an HttpOnly cookie is the safest place for a credential. The MCP server (006)
and the agentic workflow (007) run on the server and call the tax engine directly, so they
don't need user tokens. If a non-browser client ever needs the API, token auth can be added
alongside cookies without changing the user flows.

## Done when

- A new user can sign up, log in, see and edit their profile, and log out.
- After logout, the old session no longer works.
- A user cannot read or change another user's account or profile (tested).
- Passwords are never stored or logged in plain text.
- The "demo data only" notice is visible on sign-up and on the profile page.

## Left to the plan

Table design and migrations, API routes, React pages and routing, how the session cookie is
signed, and test structure.
