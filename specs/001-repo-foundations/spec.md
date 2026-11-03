# Feature Specification: Repo Foundations

**Feature Branch**: `001-repo-foundations`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Repo foundations (README milestone 1). Give the project a running, empty application skeleton and a Claude Code setup that enforces the constitution from day one: one command starts the database (with vector search enabled), backend and frontend on the README's ports; a CLAUDE.md guide for Claude Code with the key rules and commands; a shared guard that pauses and asks a human to approve any AI change to the tax-rates module, explaining rates must come from FBR's gazetted documents (asks, does not block); automatic formatting of every file the AI writes; shared permission settings (allowed without asking: tests, linters, formatters, read-only git; must ask: push, deletions; never: reading .env secrets); README setup section updated for the FastAPI backend. Out of scope: auth, database tables, tax logic, CI, real data." Source design: `docs/superpowers/specs/2026-11-03-repo-foundations-design.md`.

## Clarifications

### Session 2026-11-03

- Q: When Claude tries to change a tax-rates file through a shell command instead of its file-edit tool, should the guard also pause for approval? → A: Yes. Any shell command that mentions the tax-rates folder also asks for approval (best effort); PR review remains the final backstop.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start the whole app with one command (Priority: P1)

A developer clones the repository, follows the README's setup section, and with a single
command gets all three parts of the application running locally: the database, the backend
and the frontend. Each part shows it is alive, and each part's test suite can be run.

**Why this priority**: every later feature (002–008) is built on this skeleton. Without it,
nothing else can be developed or demonstrated.

**Independent Test**: on a machine with the README's prerequisites, clone the repo, run the
documented start command, and check that the backend reports healthy, the frontend shows a
placeholder page, vector search is available in the database, and both test commands pass.

**Acceptance Scenarios**:

1. **Given** a fresh clone and the README's prerequisites, **When** the developer runs the
   documented start command, **Then** the database, backend and frontend all start without
   further setup.
2. **Given** the app is running, **When** the developer opens the backend's health address,
   **Then** it reports that the backend is healthy.
3. **Given** the app is running, **When** the developer opens the frontend address, **Then**
   a placeholder page is shown.
4. **Given** the app is running, **When** the developer checks the database, **Then** vector
   search support is enabled.
5. **Given** the app is running, **When** the developer runs the README's backend and
   frontend test commands, **Then** each runs at least one test and all pass.

---

### User Story 2 - AI changes to tax rates need human approval (Priority: P2)

When the AI coding assistant tries to change anything in the tax-rates module, it pauses and
asks the developer to approve the change, explaining that tax rates must come only from FBR's
gazetted documents. The developer can approve or reject. Nothing is silently changed.

**Why this priority**: tax rates are the most sensitive data in the project (constitution
Principle II). The guard must exist before feature 004 adds the rates, so they are never
unprotected.

**Independent Test**: ask the AI assistant to edit a file in the tax-rates module and confirm
that an approval prompt appears with the FBR reason; approve once and reject once, and check
the file changed only when approved.

**Acceptance Scenarios**:

1. **Given** the shared AI settings are in place, **When** the AI assistant attempts to create,
   edit or overwrite a file in the tax-rates module, **Then** the developer is asked to approve
   it, and the prompt states that rates must come from FBR's gazetted documents.
2. **Given** the approval prompt is shown, **When** the developer rejects it, **Then** the file
   is left unchanged.
3. **Given** the approval prompt is shown, **When** the developer approves it, **Then** the
   change is applied.
4. **Given** the shared AI settings are in place, **When** the AI assistant runs a shell command
   that mentions the tax-rates module's folder, **Then** the same approval prompt appears.
5. **Given** the AI assistant edits a file outside the tax-rates module, **When** the edit runs,
   **Then** no tax-rates approval prompt appears.

---

### User Story 3 - The AI assistant follows the project's shared rules (Priority: P3)

Anyone working on the repository with the AI coding assistant gets the same rules
automatically: a guide file that tells the assistant the project's rules and commands, files
the assistant writes are formatted automatically, and a shared set of permissions decides what
the assistant may do freely, what it must ask about, and what it must never do.

**Why this priority**: it keeps every contributor's AI-assisted work consistent with the
constitution, but the app can be developed without it, unlike Stories 1 and 2.

**Independent Test**: in a fresh clone, have the AI assistant (a) write a badly formatted file,
(b) run the test suite, (c) attempt a push, and (d) attempt to read a secrets file; check that
(a) comes out formatted, (b) runs without a prompt, (c) asks first, and (d) is refused.

**Acceptance Scenarios**:

1. **Given** a fresh clone, **When** the AI assistant starts a session, **Then** it has access
   to a guide describing the constitution's key rules, the repo layout, and the commands to
   run, test and format the project.
2. **Given** the AI assistant writes or edits a source file, **When** the write completes,
   **Then** the file is automatically formatted to the project's standard.
3. **Given** the shared permissions, **When** the AI assistant runs tests, linters, formatters
   or read-only version-control commands, **Then** it does so without asking.
4. **Given** the shared permissions, **When** the AI assistant tries to push to a remote or
   delete files, **Then** it asks the developer first.
5. **Given** the shared permissions, **When** the AI assistant tries to read a local secrets
   file, **Then** it is refused.

### Edge Cases

- A required port (backend or frontend) is already in use on the developer's machine: the
  start fails with a message that names the busy port.
- The developer has no local secrets file: the skeleton still starts, since no feature in 001
  needs secrets.
- The AI assistant changes a tax-rates file through a shell command that never names the
  tax-rates folder (e.g. a script that builds the path itself): the guard cannot detect this;
  human review of the PR remains the backstop.
- The formatter cannot parse a file the AI assistant wrote (e.g. a syntax error): the file is
  kept as written and the assistant is told formatting failed, rather than the write being
  lost.
- A contributor works on Windows, macOS or Linux: the guard and formatting behave the same on
  all three.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST start its database, backend and frontend with a single command
  documented in the README.
- **FR-002**: The backend MUST be reachable on port 8000 and the frontend on port 5173, as the
  README states.
- **FR-003**: The backend MUST expose a health check that reports when it is running.
- **FR-004**: The frontend MUST serve a placeholder page.
- **FR-005**: The database MUST have vector search support enabled.
- **FR-006**: The backend and frontend MUST each have a test command, run as documented in the
  README, with at least one passing test.
- **FR-007**: The repository MUST contain a guide file for the AI coding assistant covering the
  constitution's key rules, the repo layout, and the commands to run, test and format.
- **FR-008**: The repository MUST reserve a fixed location for the tax-rates module, even
  though the rates themselves arrive in feature 004.
- **FR-009**: Any attempt by the AI assistant to create, edit or overwrite a file in the
  tax-rates module MUST pause for the developer's approval, with a message stating that rates
  must come from FBR's gazetted documents. Any shell command the AI assistant runs that
  mentions the tax-rates folder MUST trigger the same prompt (best effort). It MUST ask, not
  block.
- **FR-010**: Every source file the AI assistant writes or edits MUST be formatted
  automatically to the project's standard.
- **FR-011**: Shared AI permissions MUST allow tests, linters, formatters and read-only
  version-control commands without asking; require approval for pushing and deleting; and
  forbid reading local secrets files.
- **FR-012**: The guard, formatting and permissions MUST be shared through the repository, so
  every contributor gets them on clone, and MUST work on Windows, macOS and Linux.
- **FR-013**: The README's setup section MUST be updated so its commands work for the chosen
  backend (replacing the Django-specific step).
- **FR-014**: The skeleton MUST NOT include authentication, database tables, tax logic, CI or
  any real data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with the README's prerequisites goes from fresh clone to all three
  parts running in under 10 minutes, using only the README's setup section.
- **SC-002**: 100% of attempted AI changes to the tax-rates module through file edits, and of
  AI shell commands that mention the tax-rates folder, produce an approval prompt with the FBR
  reason.
- **SC-003**: 100% of attempts by the AI assistant to read a local secrets file are refused.
- **SC-004**: Every source file written by the AI assistant during a session ends up formatted,
  with no manual formatting step.
- **SC-005**: The backend and frontend test commands each pass on a fresh clone.
- **SC-006**: The same setup works unchanged on Windows and on macOS or Linux.

## Assumptions

- This feature is developer tooling rather than end-user functionality, so its "users" are the
  repo's developers (Saifullah, the lead) and the AI coding assistant itself. The README names
  some of the artefacts directly (Docker Compose, `CLAUDE.md`, Claude Code hooks), so those
  names appear here as requirements, not as implementation choices.
- The backend framework is FastAPI, as fixed by the constitution; other technical choices are
  made in the plan.
- The tax-rates guard covers the AI assistant's file edits and any shell command that names the
  tax-rates folder. Shell commands that reach the folder without naming it are not reliably
  detectable; PR review by the lead is the backstop.
- Actions not listed in the shared permissions (e.g. installing packages) fall back to the AI
  assistant's default behaviour of asking first.
- Developers have the README's prerequisites installed (Docker + Docker Compose, Python 3.12+,
  Node 20+).
- No secrets are needed for this feature; the local secrets file is first needed in feature 003.
