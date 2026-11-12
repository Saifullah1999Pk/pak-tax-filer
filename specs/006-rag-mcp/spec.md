# Feature Specification: RAG Tax Assistant and MCP Server

**Feature Branch**: `006-rag-mcp`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "RAG tax assistant and MCP server (README milestone 6). A user asks a tax question and gets an answer drawn only from a fixed set of FBR texts (Ordinance §12, §13, §149, §7B, §151; the FBR-hosted 2026 return-filing manual's salaried-return and wealth-statement chapters), with citations, or an explicit 'not covered'. Retrieval quality is measured and guarded by CI. Exactly three MCP tools: search_tax_documents, calculate_income_tax on the user's confirmed certificates only, validate_salary_information on supplied figures; a personal access token identifies the user. Questions for the lead: embeddings approval, the manual as 'the guides', the pass mark, adding the First Schedule." Source design: `docs/superpowers/specs/2026-11-03-rag-mcp-design.md`.

## Clarifications

### Session 2026-11-03

- Q: Should the Ask page limit how many questions one user can ask in a period? → A: Yes: 30 questions per user per hour; beyond that, "try again later" (per-user quotas are the standard guard against unbounded AI cost).
- Q: When a question mixes a covered and an uncovered topic, answer partly or refuse? → A: Answer the covered part with citations and state clearly which part isn't covered; if the checks fail, refuse the whole question.

### Session 2026-11-11

Built after the switch to Gemini and the redesign; decided with Saifullah (design addendum 2026-11-11 (`docs/superpowers/specs/2026-11-03-rag-mcp-design.md`)):

- Q: Which embeddings? → A: Gemini's embedding API (`gemini-embedding-001`, 768 dimensions) in pgvector; no new stack component, so the embeddings-approval question to the lead no longer applies.
- Q: Gemini answers take about 3-9 s here and must be checked before they're shown; keep the 10-second target? → A: No: 15 seconds, with progress shown while waiting (SC-004).
- Q: Where does Ask go in the navigation, with more pages to come? → A: Flat on computers (Home, Documents, Tax, Wealth statement, Ask; a profile menu for Profile and Log out); on phones a bottom bar of Home, Filing, Ask, Account, with sheets for the groups (001 FR-027 amended).
- Q: Who uses the MCP server, and where are tokens made? → A: Developers, locally, from Gemini CLI or Claude Code; tokens come from a command (`create-token`, `revoke-token`), with no page in the app (FR-016).
- Q: Every feature shares one free Gemini key; cap Ask for the whole app? → A: Yes: 200 questions a day for the whole app (a setting), the MCP search counting too (FR-009b).
- Q: The retrieval eval now needs the Gemini key; where does it run? → A: As the extraction eval does: in CI where the secret exists; a fork PR attaches a local run's report (FR-011).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask a tax question and get a cited answer (Priority: P1)

A salaried user opens the Ask page, types a question about salary tax, withholding or the wealth
statement, and gets a short answer drawn only from the named FBR texts, with each source shown
(document, section or chapter, page).

**Why this priority**: the README's core promise for this milestone: "a RAG assistant that
answers tax questions with citations".

**Independent Test**: with the corpus built, ask questions whose answers are known to be in
specific passages and confirm each answer cites those passages and says nothing they don't.

**Acceptance Scenarios**:

1. **Given** a question answered by the corpus, **When** the user asks it, **Then** the answer
   cites at least one passage, each citation naming its document, location and page.
2. **Given** an answer, **When** it is shown, **Then** every cited passage is one that was
   actually found for this question, and every number in the answer appears in a cited passage.
3. **Given** a passage from the filing manual, **When** it is cited, **Then** it is presented as
   filing guidance, and passages from the Ordinance as the law.
4. **Given** any answer, **When** it is shown, **Then** the "not yet reviewed by a tax
   practitioner; not tax advice" label is visible.
5. **Given** an answer has been shown, **When** the user asks another question, **Then** it is
   answered on its own, with no memory of the previous one.

---

### User Story 2 - Honest refusal outside the sources (Priority: P2)

When a question isn't covered by the named texts, the assistant says so plainly instead of
guessing, and when the user asks for their own tax figure, it points them to the Tax page.

**Why this priority**: the constitution requires an explicit refusal outside the corpus;
answering from general knowledge is the most harmful failure.

**Independent Test**: ask out-of-corpus questions (rental income, dividends, sales tax) and a
"how much tax do I owe" question; confirm refusals and the Tax page pointer, with no figures.

**Acceptance Scenarios**:

1. **Given** a question the corpus doesn't cover, **When** the user asks it, **Then** they see
   "I can only answer from [the named sources], and they don't cover this", with no other
   content.
2. **Given** an answer whose citations or numbers fail the checks, **When** it would be shown,
   **Then** the refusal message is shown instead.
3. **Given** a question asking for the user's own tax amount, **When** it is answered, **Then**
   the response contains no calculated figure and includes the fixed line "To see your own
   calculated tax, open the Tax page."
4. **Given** the answering service is unavailable, **When** the user asks, **Then** they're told
   to try again later, and nothing unchecked is shown.
5. **Given** a user has asked 30 questions in the past hour, **When** they ask another, **Then**
   they're told to try again later, and no answer is generated.

---

### User Story 3 - Retrieval quality is measured (Priority: P3)

A reviewer can run a fixed set of test questions and see how often the right passage is found and
how often out-of-scope questions are refused, and every pull request is blocked if quality falls
below the agreed pass mark.

**Why this priority**: required by the constitution (Principle VI); protects every answer
invisibly.

**Independent Test**: run the eval and read the two scores; deliberately break the search (e.g.
return random passages) and confirm the check fails.

**Acceptance Scenarios**:

1. **Given** about 30 user-phrased questions, each labelled with the location(s) that answer it,
   **When** the eval runs, **Then** it reports the share whose labelled location is among the
   top 5 passages found.
2. **Given** about 10 out-of-corpus questions, **When** the eval runs, **Then** it reports the
   share refused by the relevance cut-off.
3. **Given** either score below the agreed pass mark, **When** the automated checks run on a pull
   request, **Then** they fail.
4. **Given** the eval, **When** it runs in automated checks on a pull request from a fork, **Then**
   it needs no secret key.

---

### User Story 4 - Use the tools from an AI assistant (Priority: P4)

A user (or developer) connects Claude Code to the app's MCP server with a personal access token
and can search the tax texts, calculate their own tax from their confirmed certificates, and
check salary figures for problems: exactly three tools.

**Why this priority**: the README's MCP milestone; also the foundation the 007 workflow will
call.

**Independent Test**: create a token for a synthetic user with confirmed dummy certificates,
connect Claude Code, call each tool, and compare with the Ask page, the Tax page and 003's checks.

**Acceptance Scenarios**:

1. **Given** a valid token, **When** the server's tools are listed, **Then** exactly three appear:
   search tax documents, calculate income tax, validate salary information.
2. **Given** a query, **When** search is called, **Then** it returns the same passages, with
   citations, as the Ask page would find, and no written answer.
3. **Given** a user with confirmed certificates and a taxpayer profile, **When** calculate is
   called, **Then** it uses the profile's tax year and ATL status and returns exactly the Tax
   page's figures and breakdown for that user.
4. **Given** a user with only unconfirmed certificates, **When** calculate is called, **Then** it
   returns the same "not ready" reason as the Tax page and no figures.
5. **Given** salary figures (e.g. taxable salary above gross), **When** validate is called,
   **Then** it returns the same problems 003's checks would report, and never a tax figure.
6. **Given** a missing, wrong, expired or revoked token, **When** any tool is called, **Then** it
   is refused.
7. **Given** a user, **When** they create, list or revoke tokens in the app, **Then** a new
   token's full value is shown once only, and a revoked token stops working immediately.

### Edge Cases

- Empty question, or one over 1,000 characters: rejected with a message, no answer.
- A question in Urdu: treated as not covered (out of scope).
- A question mixing a covered and an uncovered topic: answers the covered part with citations and
  states which part isn't covered; if the citation or number checks fail, the whole question is
  refused.
- An answer quoting a section number (e.g. "§149"): allowed only if it appears in a cited passage
  or its location.
- An answer writing an amount in words ("5 million"): refused unless a cited passage has that
  very phrase (amended 2026-11-11: the Ordinance itself writes some amounts in words, e.g.
  "Rs. 10 million"). A number is compared with its scale: "10m" passes only where a cited
  passage has 10 million, and a bare "10" can't stand for a cited "10 million".
- An FBR source file changes (different checksum): the corpus build stops and reports it; the
  existing corpus stays in use.
- FBR is unreachable during an automated check with no cached copy: the eval fails loudly rather
  than skipping.
- A token used after 90 days: refused as expired.
- One user's token can never read another user's certificates.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The corpus MUST contain only: Income Tax Ordinance 2001 (amended up to
  31.07.2025) §12, §13, §149, §7B, §151; and the FBR-hosted 2026 return-filing manual's chapters
  on filing, salary and tax deduction (4–6) and on the wealth statement (14).
- **FR-002**: Source documents MUST NOT be stored in the repository; only each document's
  official address, fingerprint and the page ranges used. Building the corpus MUST stop if a
  fingerprint doesn't match.
- **FR-003**: Each passage MUST keep its document, location (section, sub-section or chapter) and
  page.
- **FR-004**: Answers MUST be generated only from passages found for that question, and MUST cite
  them.
- **FR-005**: Before showing an answer, the system MUST verify that every citation is a passage
  found for that question and every number in the answer appears in a cited passage or its
  location, with the same scale (amended 2026-11-11: a number in words passes only if a cited
  passage has the very same phrase; research R6). On failure, the refusal message MUST be
  shown.
- **FR-006**: Questions the corpus doesn't cover MUST get the explicit refusal message. For a
  question only partly covered, the answer MUST cover the covered part with citations and MUST
  name the part that isn't covered.
- **FR-007**: When a question asks for the user's own tax figure, the response MUST NOT contain a
  calculated figure and MUST include the fixed Tax page line, written by the system, not by AI.
- **FR-008**: Every answer MUST carry the "not yet practitioner-reviewed; not tax advice" label.
- **FR-009**: No conversation history MUST be kept; each question is answered alone.
- **FR-009a**: Each user MUST be limited to 30 questions per hour; beyond that, no answer is
  generated and the user is told to try again later.
- **FR-009b** (added 2026-11-11): The whole app MUST be limited to 200 questions a day (a
  setting), counting the MCP search tool; beyond that, no question is embedded or answered and
  the user is told the assistant has reached today's limit. Before the corpus is first built,
  questions get "The tax assistant isn't ready yet".
- **FR-010**: A retrieval eval MUST measure the top-5 hit rate over labelled questions and the
  refusal rate over out-of-corpus questions; labels MUST name stable locations, not internal
  identifiers.
- **FR-011** (amended 2026-11-11): Automated checks MUST run the retrieval eval on pull requests
  where the Gemini key is available (as the extraction eval does), and MUST fail below the
  agreed pass mark; it MUST also run on every push to `main`, so a merge that lowers quality
  fails CI there; a pull request without the key (our fork PRs) attaches a local run's report.
- **FR-012**: The MCP server MUST expose exactly three tools: search tax documents, calculate
  income tax, validate salary information.
- **FR-013**: Calculate income tax MUST use only the authenticated user's confirmed certificates,
  through the same rules as the Tax page, and MUST return the same figures, breakdown and "not
  ready" reasons.
- **FR-014**: Validate salary information MUST check supplied figures with the same rules as 003
  and MUST NOT calculate tax.
- **FR-015**: Every tool call MUST require a valid personal access token; tokens MUST be stored
  only as hashes, shown in full once at creation, revocable, and expire after 90 days. The web
  app's own login MUST stay unchanged.
- **FR-016** (amended 2026-11-11): Developers MUST be able to create a token for a user and
  revoke it with commands (as `create-user` today); there is no token page in the app.
- **FR-017** (added 2026-11-11): Ask MUST appear in the app's navigation as 001 FR-027 (amended)
  describes, and the Ask page MUST show its progress ("Searching the FBR texts…", "Writing a
  cited answer…") while waiting.

### Key Entities

- **Source document**: name, official address, fingerprint, kind (law or filing guidance), page
  ranges used.
- **Passage**: text, document, location, page, and its search representation.
- **Eval question**: question text, expected locations (or "out of corpus").
- **Answer** (not stored): text, citations, refusal flag, Tax page line flag, label.
- **Personal access token**: owner, name, hash, created, expires, revoked, last used.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Retrieval meets the lead's pass mark (proposed: labelled location in the top 5 for
  at least 80% of questions; at least 90% of out-of-corpus questions refused).
- **SC-002**: 0 shown answers cite a passage not found for that question, or contain a number not
  in a cited passage (tested with deliberately bad answers).
- **SC-003**: 100% of shown answers carry the practitioner label.
- **SC-004** (amended 2026-11-11): An answer or a not-covered message appears within 15 seconds
  of asking, with progress shown while waiting.
- **SC-005**: Calculate income tax returns figures identical to the Tax page for 100% of 004's
  signed-off worked examples.
- **SC-006**: 100% of tool calls with a missing, wrong, expired or revoked token are refused.

## Assumptions

- FBR publishes no separate Form 114(1) or Form 116 guide for TY2026; the FBR-hosted 2026 filing
  manual's chapters are the current equivalent (asked of the lead).
- The search representation comes from Gemini's embedding API (amended 2026-11-11), already
  part of the stack, so no new component or approval is needed.
- The pass mark and adding the First Schedule (salaried slabs) to the corpus are asked of the
  lead.
- The MCP server runs locally and is used from Claude Code; tests use synthetic users with
  confirmed dummy certificates.
- English questions only.
- Out of scope: chat history, sources beyond the corpus, remote MCP hosting, tools beyond the
  three, the agentic workflow (007), telemetry (008).
