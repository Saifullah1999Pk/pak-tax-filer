# Feature Specification: Taxpayer Profile + Auth

**Feature Branch**: `002-profile-auth`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Taxpayer profile + auth (README milestone 2). A user can sign up and log in with email + password, log out, and manage exactly one taxpayer profile visible only to them. Profile holds only calculation inputs: tax year (TY2026, stored so later years can be added), ATL status (yes/no, starts unanswered and must be chosen), optional display name (free text, not a legal name). Clear 'demo data only' notice on sign-up and profile page. Logout ends the session immediately. Emails unique, case-insensitive; passwords at least 8 characters; sessions expire after 7 days; login errors don't reveal whether an email is registered; passwords never stored or logged in plain text. Out of scope: identity fields, password reset, email verification, multiple profiles, admin users, account deletion, non-residents." Source design: `docs/superpowers/specs/2026-11-03-profile-auth-design.md`.

## Clarifications

### Session 2026-11-03

- Q: What should happen when someone keeps guessing passwords for the same account? → A: After 10 failed sign-in attempts for an email within 15 minutes, further attempts for that email are refused until the 15 minutes pass; no permanent lockout.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create an account and sign in (Priority: P1)

A salaried taxpayer trying the app creates an account with an email address and password,
is signed in, and can later sign out and sign back in. Before creating the account they see
that the app is a demo and must not be given real personal data.

**Why this priority**: nothing personal in the app (profile, documents, calculations) can exist
without knowing who the user is.

**Independent Test**: create an account, sign out, sign in again with the same details, and
sign out; check that a wrong password is refused and that pages needing sign-in are unavailable
after signing out.

**Acceptance Scenarios**:

1. **Given** a visitor on the sign-up page, **When** the page loads, **Then** a "demo data
   only, do not enter real personal information" notice is visible before they submit.
2. **Given** a visitor, **When** they sign up with a new email and a password of at least 8
   characters, **Then** the account is created and they are signed in.
3. **Given** an existing account for `Ali@Example.com`, **When** someone signs up with
   `ali@example.com`, **Then** sign-up is refused because that email is already in use.
4. **Given** a visitor, **When** they sign up with a password shorter than 8 characters,
   **Then** sign-up is refused with a message stating the minimum length.
5. **Given** a registered user, **When** they sign in with the correct email (in any letter
   case) and password, **Then** they are signed in.
6. **Given** a sign-in attempt with an unknown email or a wrong password, **When** it fails,
   **Then** the same generic message is shown in both cases.
7. **Given** a signed-in user, **When** they sign out, **Then** they are signed out at once,
   and their previous session can no longer be used, even from another tab.
8. **Given** 10 failed sign-in attempts for an email within 15 minutes, **When** an 11th attempt
   is made, even with the correct password, **Then** it is refused with a message to try again
   later, and sign-in works again once 15 minutes have passed.

---

### User Story 2 - Manage my taxpayer profile (Priority: P2)

A signed-in user opens their profile and sees their tax year (TY2026), chooses whether they are
on FBR's Active Taxpayer List (ATL), and optionally sets a display name the app uses to greet
them. They can come back and change these answers.

**Why this priority**: the tax calculation (feature 004) needs the tax year and ATL status, but
the profile can only exist once accounts do (Story 1).

**Independent Test**: as a new user, open the profile, see ATL status unanswered, choose an
answer and a display name, save, sign out and back in, and see the saved values.

**Acceptance Scenarios**:

1. **Given** a newly created account, **When** the user opens their profile, **Then** the tax
   year shows TY2026, ATL status shows as not yet answered, and the display name is empty.
2. **Given** the profile page, **When** it loads, **Then** the "demo data only" notice is
   visible.
3. **Given** ATL status is unanswered, **When** the user chooses yes or no and saves, **Then**
   the answer is stored and shown on later visits.
4. **Given** a saved profile, **When** the user changes ATL status or display name and saves,
   **Then** the new values replace the old ones.
5. **Given** a user, **When** they try to set ATL status to anything other than yes or no
   (including clearing it once answered), **Then** the change is refused.

---

### User Story 3 - My data is private to me (Priority: P3)

A user's account and profile can be seen and changed only by that user while signed in.
Nobody else, whether signed in as another user or not signed in, can read or change them.

**Why this priority**: required before any real use, but it is a property of Stories 1 and 2
rather than a separate screen.

**Independent Test**: with two accounts, try to read and change user A's profile while signed
in as user B and while signed out; every attempt is refused and A's data is unchanged.

**Acceptance Scenarios**:

1. **Given** users A and B, **When** B tries to read A's profile, **Then** the request is
   refused and nothing about A is revealed.
2. **Given** users A and B, **When** B tries to change A's profile, **Then** the request is
   refused and A's profile is unchanged.
3. **Given** a visitor who is not signed in, **When** they try to read or change any profile,
   **Then** they are refused and asked to sign in.
4. **Given** a session older than 7 days, **When** it is used, **Then** it is refused and the
   user must sign in again.

### Edge Cases

- A user signs up with leading or trailing spaces around their email: the spaces are ignored.
- A user submits the profile form twice quickly: the last save wins and only one profile exists.
- A user signs in on two devices: both sessions work until each is signed out or expires;
  signing out on one does not sign out the other.
- A user forgets their password: there is no reset in this feature; the sign-in page says so
  and that it is a demo.
- A very long display name is entered: it is refused above 50 characters.
- A user tries to create a second profile: impossible; each account has exactly one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Visitors MUST be able to create an account with an email address and a password.
- **FR-002**: Email addresses MUST be unique, compared without regard to letter case and
  ignoring surrounding spaces.
- **FR-003**: Passwords MUST be at least 8 characters long; no other composition rules apply.
- **FR-004**: Passwords MUST never be stored or written to logs in readable form.
- **FR-005**: Registered users MUST be able to sign in with their email and password, and sign
  out.
- **FR-006**: A failed sign-in MUST show the same message whether the email is unknown or the
  password is wrong.
- **FR-007**: Signing out MUST end that session immediately, so it cannot be used again.
- **FR-008**: Sessions MUST expire 7 days after sign-in.
- **FR-008a**: After 10 failed sign-in attempts for an email within 15 minutes, further sign-in
  attempts for that email MUST be refused until 15 minutes have passed; the refusal message MUST
  NOT reveal whether the email is registered.
- **FR-009**: Each account MUST have exactly one taxpayer profile, created with the account.
- **FR-010**: The profile MUST hold only: tax year, ATL status and an optional display name.
- **FR-011**: Tax year MUST be TY2026 for this release and MUST be stored as a value, not
  assumed, so later tax years can be supported.
- **FR-012**: ATL status MUST start unanswered and accept only yes or no once set.
- **FR-013**: Display name MUST be optional free text of at most 50 characters.
- **FR-014**: Users MUST be able to view and change their own ATL status and display name.
- **FR-015**: Only the signed-in owner MUST be able to read or change an account or profile;
  all other attempts MUST be refused without revealing the data.
- **FR-016**: The sign-up page and the profile page MUST show a clear notice that the app is a
  demo and real personal information must not be entered.
- **FR-017**: The feature MUST NOT collect identity details (legal name, CNIC, NTN, address)
  and MUST NOT include password reset, email verification, multiple profiles, admin users or
  account deletion.

### Key Entities

- **Account**: a person who can sign in. Email (unique, case-insensitive) and a protected form
  of their password. Owns exactly one Profile and any number of Sessions.
- **Session**: proof that an Account is signed in. Created at sign-in; ends at sign-out or
  7 days after creation, whichever comes first.
- **Taxpayer Profile**: calculation inputs for one Account: tax year (TY2026), ATL status
  (unanswered, yes or no) and optional display name.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can create an account and reach their profile in under 1 minute.
- **SC-002**: A user can answer ATL status and save their profile in under 30 seconds.
- **SC-003**: 100% of attempts to read or change another user's account or profile are refused
  in testing, signed in or not.
- **SC-004**: 0 passwords appear in readable form in stored data or logs.
- **SC-005**: After sign-out, 100% of requests using the ended session are refused.
- **SC-006**: The "demo data only" notice is visible on 100% of loads of the sign-up and
  profile pages.

## Assumptions

- Users are resident salaried individuals in Pakistan; non-residents are out of scope.
- Synthetic or demo data only (constitution, Principle V); the profile deliberately has no
  identity fields, so real personal identifiers cannot be entered.
- No email service exists in the MVP, so password reset and email verification are deferred.
- Builds on feature 001's running backend, frontend and database.
- Feature 004 will read tax year and ATL status from the profile; it must treat an unanswered
  ATL status as "cannot calculate yet" rather than guess.
