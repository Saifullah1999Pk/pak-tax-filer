# Feature Specification: Authentication Foundation

**Feature Branch**: `002-auth-foundation`

**Created**: 2026-11-03

**Status**: Draft

**Input**: Lead's request: "Establish custom authentication using our existing frontend. Define the minimum working authentication scope: user model, login/logout, session management, protected APIs and frontend integration. Keep signup, email verification, forgot password and password reset as subsequent implementation increments. AWS Cognito is out of scope. The objective is a clean, working authentication foundation that we can extend incrementally." Backend is FastAPI per the constitution. Source design: `docs/superpowers/specs/2026-11-03-auth-foundation-design.md`.

## Clarifications

### Session 2026-11-03

- Q: What should happen when someone keeps guessing passwords for the same account? → A: After 10 failed sign-in attempts for an email within 15 minutes, further attempts for that email are refused until the 15 minutes pass; no permanent lockout.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Log in and log out (Priority: P1)

A demo user, created by a developer, logs in with their email and password and later logs out.
Wrong details are refused without revealing which part was wrong, and repeated guessing is
slowed down.

**Why this priority**: every protected API and page depends on knowing who the user is.

**Independent Test**: create a demo user with the developer command, log in, log out, and check
that a wrong password is refused, that the old session stops working after logout, and that the
11th failed attempt within 15 minutes is refused.

**Acceptance Scenarios**:

1. **Given** a developer runs the user-creation command with an email and a password of at
   least 8 characters, **When** it completes, **Then** a user exists who can log in.
2. **Given** the command is run with an email already in use (in any letter case), **When** it
   runs, **Then** it refuses and creates nothing.
3. **Given** a user exists, **When** they log in with the correct email (in any letter case)
   and password, **Then** they are logged in.
4. **Given** a login attempt with an unknown email or a wrong password, **When** it fails,
   **Then** the same generic message is shown in both cases.
5. **Given** a logged-in user, **When** they log out, **Then** that session ends at once and
   cannot be used again, even from another tab.
6. **Given** 10 failed login attempts for an email within 15 minutes, **When** an 11th attempt
   is made, even with the correct password, **Then** it is refused with a message to try again
   later, and logging in works again once 15 minutes have passed.

---

### User Story 2 - Protected APIs (Priority: P2)

Backend endpoints that deal with a user's data accept requests only from a logged-in user and
know which user is asking. An example "who am I" endpoint returns the logged-in user's email.

**Why this priority**: every later feature (documents, calculations, wealth statement) builds
its endpoints on this protection.

**Independent Test**: call the example protected endpoint with no session, an expired session,
a logged-out session and a valid session; only the valid one succeeds and returns that user's
email.

**Acceptance Scenarios**:

1. **Given** no session, **When** a protected endpoint is called, **Then** it is refused as
   "not logged in" and reveals no data.
2. **Given** a valid session, **When** the "who am I" endpoint is called, **Then** it returns
   that user's email and nothing else.
3. **Given** a session older than 7 days, **When** it is used, **Then** it is refused as
   "not logged in".
4. **Given** a session that was logged out, **When** it is used, **Then** it is refused as
   "not logged in".

---

### User Story 3 - Frontend integration (Priority: P3)

The web app has a login page, keeps pages that need login behind it, shows a logout button
when logged in, and sends the user back to the login page when their session ends.

**Why this priority**: it makes the foundation usable in the app, but Stories 1 and 2 can be
tested without it.

**Independent Test**: in the browser, open a protected page while logged out (sent to login),
log in (taken to the page), log out (back to login), and let a session expire (back to login on
the next action).

**Acceptance Scenarios**:

1. **Given** a logged-out visitor, **When** they open a page that needs login, **Then** they
   are sent to the login page.
2. **Given** the login page, **When** it loads, **Then** a "demo data only, do not enter real
   personal information" notice is visible.
3. **Given** the login page, **When** the user logs in successfully, **Then** they are taken to
   the page they wanted, or a home page if none.
4. **Given** a logged-in user, **When** they look at any page, **Then** a logout button is
   visible; using it logs them out and shows the login page.
5. **Given** a session that has expired or been logged out elsewhere, **When** the user next
   does something that needs login, **Then** they are sent to the login page with a short
   explanation.

### Edge Cases

- Leading or trailing spaces around an email are ignored when creating users and logging in.
- A user logs in on two devices: both sessions work until each is logged out or expires;
  logging out on one does not log out the other.
- A user forgets their password: there is no reset yet; the login page says this is a demo and
  to contact the developer.
- The login page is opened while already logged in: the user is taken to the home page.
- The throttle message must not reveal whether the email is registered.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST store users with a unique email address, compared without regard
  to letter case and ignoring surrounding spaces, and a protected password.
- **FR-002**: Passwords MUST be at least 8 characters long; no other composition rules apply.
- **FR-003**: Passwords MUST never be stored or written to logs in readable form.
- **FR-004**: Developers MUST be able to create demo users with a command; there is no
  self-service sign-up in this feature.
- **FR-005**: Users MUST be able to log in with email and password, and log out.
- **FR-006**: A failed login MUST show the same message whether the email is unknown or the
  password is wrong.
- **FR-007**: After 10 failed logins for an email within 15 minutes, further attempts for that
  email MUST be refused until 15 minutes have passed, without revealing whether the email is
  registered.
- **FR-008**: Logging out MUST end that session immediately.
- **FR-009**: Sessions MUST expire 7 days after login.
- **FR-010**: The backend MUST provide a reusable protection for endpoints that refuses requests
  without a valid session and identifies the logged-in user to the endpoint.
- **FR-011**: The backend MUST provide a protected "who am I" endpoint returning only the
  logged-in user's email.
- **FR-012**: The frontend MUST provide a login page, send logged-out visitors from protected
  pages to it, return them to their intended page after login, and show a logout button while
  logged in.
- **FR-013**: When a session ends or expires, the frontend MUST send the user to the login page
  on their next action that needs login.
- **FR-014**: The login page MUST show a clear notice that the app is a demo and real personal
  information must not be entered.
- **FR-015**: The feature MUST NOT include sign-up, email verification, forgot password,
  password reset, a taxpayer profile, or any external identity provider.

### Key Entities

- **User**: someone who can log in. Email (unique, case-insensitive) and a protected form of
  their password. Has any number of Sessions.
- **Session**: proof that a User is logged in. Created at login; ends at logout or 7 days after
  creation, whichever comes first.
- **Failed login record**: a count of recent failed attempts per email, used only for
  throttling.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A demo user can log in and reach a protected page in under 30 seconds.
- **SC-002**: 100% of requests to protected endpoints without a valid session are refused in
  testing.
- **SC-003**: After logout, 100% of requests using the ended session are refused.
- **SC-004**: 0 passwords appear in readable form in stored data or logs.
- **SC-005**: The 11th failed login within 15 minutes is refused in 100% of tests.
- **SC-006**: The "demo data only" notice is visible on 100% of loads of the login page.

## Assumptions

- Builds on feature 001's running backend, frontend and database.
- Demo data only (constitution, Principle V); users have no identity fields.
- Sign-up, email verification, forgot password and password reset are later increments, per the
  lead; the taxpayer profile is a separate feature built on this one.
- The only client of the user-facing API is the project's own web app; non-browser clients are
  out of scope.
