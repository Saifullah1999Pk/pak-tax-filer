# Feature Specification: Policy-Based Bill Approval Agent

**Feature Branch**: `009-bill-approval`

**Created**: 2026-11-13

**Status**: Draft

**Input**: the lead's request (2026-11-11) for an agent in this repo, and his company's real
problem: staff submit medical bills, and an agent reads each bill and approves it per company
policy (a Rs 1 lakh yearly budget; some items not allowed, such as pampers, energy drinks and
equipment). Design: `docs/superpowers/specs/2026-11-13-bill-approval-agent-design.md` (approved
2026-11-13). Scope added by constitution v1.3.0, Principle VII.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get a medical bill decided automatically (Priority: P1)

An employee uploads a medical bill (a PDF or a photo). The agent reads every line and its amount
and suggests a category for each (medicine, consultation, lab test, baby product, drink,
equipment, other). The employee checks each line and the total, corrects anything wrong, and
confirms. The company's medical policy then decides: allowed lines are approved, banned lines
are cut with the reason, and nothing beyond the year's budget is approved. The employee sees the
approved amount, what was cut and why, the budget left, and a short explanation in plain words.

**Why this priority**: it is the lead's actual request and the core of the agent; everything
else builds on it.

**Independent Test**: as a synthetic employee with a fresh budget, upload a synthetic bill with
an allowed line and a banned line; confirm; the decision approves the allowed line, cuts the
banned one with its reason, and shows the budget left, all matching a signed-off worked example.

**Acceptance Scenarios**:

1. **Given** a bill with medicines of Rs 4,200 and a baby product of Rs 800, and Rs 100,000 of
   budget left, **When** the employee confirms the lines, **Then** Rs 4,200 is approved, the Rs
   800 line is cut as "baby products aren't covered", and Rs 95,800 is left.
2. **Given** Rs 3,000 of budget left and a confirmed bill of Rs 5,000 of allowed lines, **When**
   it is decided, **Then** Rs 3,000 is approved, saying the budget is used up, and Rs 0 is left.
3. **Given** the agent read a line as Rs 1,500 but the bill says Rs 1,050, **When** the employee
   corrects it and confirms, **Then** the decision uses Rs 1,050.
4. **Given** an employee has not confirmed every line, **When** they look at the claim, **Then**
   nothing is decided and no budget is used.
5. **Given** any decision, **Then** it says which policy rule applied to each line, its
   explanation contains only the decision's own numbers, and it is labelled "provisional,
   pending the accounts department".

---

### User Story 2 - An approver decides the unclear claims (Priority: P2)

Some claims the policy can't settle on its own: the bill couldn't be read, a line was put in
"other", the bill has no date or is from outside the policy year, the employee changed the total
a lot, or a mobile bill covers several months. These go to an approver's queue with the bill,
the confirmed lines and the reasons it was flagged. The approver approves an amount (never more
than the policy allows) or rejects it, always with a note, and the employee sees the outcome and
the note. An approver never sees or decides their own claims.

**Why this priority**: without a person for the unclear cases the agent either approves too much
or blocks real claims; the lead's flow has accounts handling the exceptions.

**Independent Test**: with two synthetic approvers, flag a claim of each; each approver's queue
shows the other's claim but not their own; approving above the eligible amount is refused; an
approval with a note uses that amount of budget and the employee sees it.

**Acceptance Scenarios**:

1. **Given** a confirmed bill with an "other" line, **When** it is decided, **Then** it is
   flagged with the reason, no budget is used, and it appears in approvers' queues.
2. **Given** a flagged claim whose eligible amount is Rs 2,000, **When** an approver approves Rs
   2,500, **Then** it is refused; **When** they approve Rs 1,800 with a note, **Then** Rs 1,800 is
   approved and used from the budget, and the employee sees the note.
3. **Given** an approver's own flagged claim, **When** they open their queue or the claim,
   **Then** it isn't there (the same "not found" anyone gets for a claim that isn't theirs), and
   another approver can decide it.
4. **Given** an employee who isn't an approver, **When** they open the queue or another person's
   claim, **Then** they get "not found".
5. **Given** two flagged claims of the same employee, **When** an approver decides the first and
   the budget falls, **Then** the second's eligible amount is worked out again from what's left.

---

### User Story 3 - Mobile and internet bills under a monthly cap (Priority: P3)

The same agent handles a second policy: mobile and internet bills, with one cap per calendar
month covering both kinds (devices are never reimbursed). A second bill for the same month uses
what's left of that month's cap; a bill covering several months goes to an approver.

**Why this priority**: proves the agent is a general policy engine, not a one-off for medical
bills, at small extra cost; the lead's second likely use.

**Independent Test**: as a synthetic employee, submit a mobile bill and an internet bill for the
same month whose total passes the cap; the second is approved only up to what's left.

**Acceptance Scenarios**:

1. **Given** a Rs 3,000 monthly cap and a confirmed March mobile bill of Rs 2,200, **When** it is
   decided, **Then** Rs 2,200 is approved and Rs 800 of March's cap is left.
2. **Given** that, **When** a March internet bill of Rs 1,500 is confirmed, **Then** Rs 800 is
   approved, saying March's cap is used up.
3. **Given** a bill with a phone handset line, **When** it is decided, **Then** that line is cut
   as "devices aren't reimbursed".
4. **Given** a bill covering January to March, **When** it is decided, **Then** it is flagged for
   an approver.

---

### Edge Cases

- A bill the agent can't read at all (blurred, not a bill): the employee is told and can retry
  or still enter the lines themselves; the claim is flagged so a person checks it.
- Google doesn't answer in time: the employee is told plainly, the file is kept for Retry, and
  the try doesn't count against their daily limit (as for tax documents).
- A bill dated before or after the policy year: flagged, never decided automatically.
- Every line banned: Rs 0 approved, each line cut with its reason; no budget used.
- Budget already used up: Rs 0 approved, saying so; nothing flagged just for that.
- The policy's banned-items setting switched from "cut the line" to "reject the bill": the same
  bill is then rejected whole, with the reason.
- An employee submits the same bill twice: decided as a second bill (the approver sees both if
  flagged); duplicate detection is out of scope.
- An approver is also an employee: their own claims follow the same policy and go to another
  approver when flagged; with no other approver they wait.
- The employee's daily bill-reading limit is reached: refused before the AI is used, saying
  when they can try again.

## Requirements *(mandatory)*

### Functional Requirements

**Submitting and confirming**

- **FR-001**: An employee MUST be able to submit a bill (PDF, JPEG or PNG, as for tax
  documents) under one policy: medical, or mobile/internet.
- **FR-002**: The agent MUST read the bill's date (or billing period), each line's description
  and amount, and the total, and propose a category for each line from the policy's fixed list.
- **FR-003**: The employee MUST confirm or correct every line (description, amount, category),
  the date and the total before anything is decided; unconfirmed claims MUST NOT be decided or
  use budget, enforced by the system, not only the screen (Principle III).
- **FR-004**: An employee MUST see only their own claims; any other claim MUST be "not found".

**Deciding**

- **FR-005**: The decision MUST be made by deterministic code from the confirmed lines, the
  policy and the budget left, never by the AI (Principle I): for each line, approved, cut (with
  the rule) or flagged, and the claim's approved amount, the cut amount and the budget left.
- **FR-006**: A banned line MUST be cut and the rest approved ("cut the line"); the policy MUST
  also support "reject the bill" by one setting, with both behaviours tested.
- **FR-007**: The approved amount MUST NOT exceed the budget left for the period at the moment of
  the decision; when it is capped, the decision MUST say so.
- **FR-008**: Only decided claims (approved automatically or by an approver) MUST use budget; a
  flagged claim holds nothing back, and its eligible amount MUST be worked out again whenever it
  is decided.
- **FR-009**: A claim MUST be flagged, with each reason, when the bill or a line couldn't be read,
  a line is "other", the bill has no date or a date outside the policy period, the employee's
  confirmed total differs from the total read by more than a set share, or a mobile/internet bill
  covers more than one month; otherwise it MUST be decided automatically.
- **FR-010**: Each decision MUST show which rule applied to each line and be labelled
  "provisional, pending the accounts department" while the policy is provisional.

**Explaining**

- **FR-011**: The agent MUST explain each decision in plain words, written from the code's
  decision; the explanation MUST be shown only if every number in it is one of the decision's
  numbers, and otherwise a plain template explanation MUST be shown instead (Principle I).

**Approving flagged claims**

- **FR-012**: The approver role MUST be granted only by the administrator's command-line tool;
  there is no screen for it.
- **FR-013**: An approver MUST see a queue of flagged claims with each bill, its confirmed lines,
  the reasons and the eligible amount, and MUST NOT see their own claims there or anywhere else
  as an approver (both "not found").
- **FR-014**: An approver MUST approve an amount up to the eligible amount, or reject, each with
  a required note; an amount above the eligible amount MUST be refused. The employee MUST see the
  outcome and the note.

**Policies**

- **FR-015**: Each policy MUST be versioned data for its year, each rule recording the company's
  written policy it comes from (synthetic for the demo, and saying so), changed only by a
  reviewed change, never in the app (Principle II).
- **FR-016**: The medical policy MUST be: Rs 100,000 per employee per policy year (1 July to 30
  June, the profile's tax year), covering the employee and family with no patient recorded;
  banned categories baby products, energy drinks and equipment; bills within the policy year.
- **FR-017**: The mobile/internet policy MUST be: one cap per calendar month covering both kinds
  (Rs 3,000 by default); devices never reimbursed; a bill counts for the month of its billing
  period.
- **FR-018**: Every policy rule's effect MUST be covered by worked examples, worked by hand and
  signed off before the code that applies them (Principle VI); a test MUST fail on an unsigned
  example.

**Limits, reliability and privacy**

- **FR-019**: Reading bills MUST be limited to 10 per employee in any 24 hours, separate from tax
  documents, and count toward the app's shared 100 a day; over a limit, the request MUST be
  refused before the AI is used.
- **FR-020**: A try Google fails to answer (a server error, a timeout, no connection) MUST NOT
  count against the limit, and MUST say so with what to do.
- **FR-021**: Every AI use MUST be recorded by the app's telemetry with no user content.
- **FR-022**: Only synthetic bills and employees MUST be used in tests, evals and demos
  (Principle V); no patient, CNIC or account data MUST be stored.

### Key Entities

- **Policy**: a named, year-versioned set of rules (budget and its period, banned categories,
  caps, flagging thresholds, the banned-items setting), each with its written source.
- **Claim**: one submitted bill: its policy, owner, file, status (reading, needs confirmation,
  approved, flagged, decided by approver, rejected), the date or billing period, and the totals.
- **Bill line**: a line of a claim: description, amount, category, as read and as confirmed.
- **Decision**: the outcome for a claim: per-line result and rule, approved, cut and eligible
  amounts, budget left, flag reasons, the explanation, and who decided (the policy or an
  approver, with the note).
- **Budget use**: the approved amounts per employee, policy and period, from which the budget
  left is worked out.
- **Approver**: an employee with the approver role.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An employee goes from upload to a decision on a clear medical bill in under 3
  minutes, most of it checking the lines.
- **SC-002**: 100% of decisions in the worked examples match the hand-worked amounts to the rupee.
- **SC-003**: No sequence of decisions in the tests lets an employee's approved total pass the
  policy's budget for a period.
- **SC-004**: An approver never sees their own claim, and a non-approver never sees anyone
  else's: 100% of the access tests pass.
- **SC-005**: No shown explanation contains a number the decision doesn't have: 100% of the
  explanation tests pass, including deliberately wrong AI replies.
- **SC-006**: On a set of at least 10 synthetic bills, the agent reads line amounts correctly for
  at least 90% of lines and proposes the right category for at least 85%, measured by an eval.
- **SC-007**: Switching the banned-items setting changes the outcome of the affected examples and
  nothing else.

## Assumptions

- The policy figures and rules are **provisional defaults** until the lead's accounts department
  answers (asked 2026-11-13: partial approval, the budget edge, family, approvers, the banned
  list); each is one setting or one policy rule to change.
- Employees are the app's existing users; one company; the policy year is the profile's tax
  year (2025-26), so claims need a profile, like the tax features.
- Approved amounts don't change the tax result or the wealth statement (whether reimbursements
  affect tax is a question for a tax practitioner, out of scope).
- The demo has at least two approvers, so self-approval never blocks it.
- Reading and explaining reuse the app's existing AI provider, limits pattern, retries and
  telemetry; no new external service.
- Out of scope: multiple companies or departments, approval chains, payments, editing policies
  in the app, duplicate-bill detection, fuel and travel claims, vendor invoices and the other
  later ideas in the design.
