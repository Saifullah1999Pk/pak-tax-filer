# Feature 009: policy-based bill approval agent, design

2026-11-13. Brainstormed by Saifullah with Claude, from the lead's request.

## Intent and the why

The lead (Awais) asked for "some general agent" in this repo (2026-11-11), pointing at the
500-AI-Agents list, and proposed a real problem from his company's accounts department: staff
submit medical bills, and an agent reads each bill and approves it against company policy (a
Rs 1 lakh yearly budget; some items not allowed, such as pampers, energy drinks and equipment).
Nothing in that list does policy-based approval; the closest is a hospital-claims agent.

This feature builds that agent as a **general policy-approval engine**: a document comes in,
the AI reads it, plain code checks it against a policy, and a person decides what the code
can't. Medical bills are the first policy (certain, per the user); mobile and internet bills are
the second, to prove the engine is general rather than one-off. It reuses most of what features
003, 006, 007 and 008 built: Gemini document reading with retries, confirmation of what the AI
read, number-checked AI explanations, the approval-gate pattern, telemetry and the daily limits.

## Goals

1. An employee uploads a bill (PDF or photo), confirms what the AI read, and gets a decision in
   plain words: approved amount, what was cut and why, and the budget left.
2. The agent auto-decides what the policy settles clearly and sends everything else to an
   approver, always saying which rule applied.
3. An approver works through a queue of flagged claims and approves or rejects each, with a note.
4. Two policies: medical bills and mobile/internet bills.
5. Every amount (approved, cut, budget left) is deterministic code, provably following the
   policy (worked examples, as 004 and 005 have).

## Non-goals

Multiple companies or departments; approval chains or second approvers; paying claims; editing
policies in the app; any link to the tax calculation (approved reimbursements do not change the
tax result; that is a question for a tax practitioner, not this feature); the later ideas below.

## Anti-goals (a failure even if it works)

- The AI deciding an amount or an approval: it only reads, categorises (confirmed by the
  employee) and explains.
- An approver, or anyone, seeing data that isn't theirs beyond the flagged-claims queue.
- Real bills or real employee data anywhere (Principle V): synthetic bills only.
- An explanation stating a number that isn't the code's.

## Constraints

- **Constitution:** Principle VII limits the MVP to one taxpayer's tax filing and requires an
  approved spec that amends the scope first. 009 starts with a MINOR amendment (1.2.2 → 1.3.0):
  a second capability, policy-based bill approval, under the same principles. Principle I's
  rule (deterministic code, never an LLM, for every figure) extends to claim amounts; Principle
  II's "authoritative source" for a policy is the company's written policy, recorded with each
  rule; Principle III covers the confirmation of what the AI read and the approver's decision.
- **Scope cap:** the project planned 8 features; 009 needs the lead's agreement (he asked for
  it, but confirm in the PR).
- Stack and conventions as 001–008: FastAPI, async SQLAlchemy, Alembic, React; Gemini through
  google-genai; the guardrails, telemetry (`ai_call` for every Gemini use), contract check and
  e2e suite all extend to it.

## Approaches (the user chose A)

| | Approach | Trade-off |
|---|---|---|
| **A** | **A new `claims` area** with its own tables, pages and tests, reusing the shared pieces; the agent runs as steps: read and propose categories (AI) → employee confirms → policy decision (code) → explanation (AI, number-checked) → approve or route to the approver | Clean; can't disturb the tax features; some new UI (bill review with line items, approver queue) |
| B | A new document type in 003, reusing its upload and review screens | 003 assumes a fixed set of fields per certificate; bills have any number of lines; tangles tax and expense claims |
| C | A fully autonomous agent with tools (`check_policy`, `budget_left`) that decides | Most "agent"-like, but the AI decides money: breaks Principle I and can't be proven to follow the policy |

## Decided

**Roles.** Employee (every user) and approver (a flag set only by the admin command,
`python -m app.cli …`, as `create-user` is; no admin screens). An employee sees only their own
claims. An approver additionally sees the flagged-claims queue and each flagged claim's bill,
lines and reasons, nothing else of anyone's; everyone else gets `404` for a claim not theirs.

**Policies live in code as versioned data**, like the tax rates: one module per policy, each
rule with its source ("<Company> medical policy, 2026", synthetic for the demo), changed only by
a reviewed pull request, with signed-off worked examples (a test fails on an unsigned one).

**Line categories.** The AI reads each line (description, amount) and proposes a category from a
fixed list (medical: medicine, consultation, lab test, baby product, drink, equipment, other;
mobile: plan, data, device, other); the employee confirms or corrects every line and the total
before any decision. Policy rules apply to confirmed categories only.

**Decisions** (provisional, pending the accounts department; the lead has been asked):
- *Partial approval:* a banned line is cut and the rest approved, with the reason per cut line.
  One policy setting (`banned_items: exclude_line | reject_bill`), tested both ways, so switching
  later is a small change.
- *Budget edge:* a bill larger than the budget left is approved up to what's left, saying so.
- *Flag for the approver:* the AI couldn't read the bill (or a line), a line is "other", the bill
  is undated or dated outside the policy year, or the employee changed a total by more than a
  set share. Everything else is decided automatically.

**Medical policy (provisional defaults):** Rs 100,000 per employee per policy year (July–June,
matching the tax year), shared with family; banned: baby products, energy drinks, equipment; no
per-bill limit; bills within the policy year.

**Mobile/internet policy (provisional defaults):** a fixed monthly cap (e.g. Rs 3,000) per
employee; the bill's month counts once; devices not reimbursed.

**The agent's explanation** is written by the AI from the code's decision and shown only if every
number in it is the code's (004's number check); otherwise a plain template explanation is used,
as 007's fallbacks do. Every Gemini use goes through `ai_call`; claims count against the existing
daily AI limits, and a try Google fails to answer isn't charged (as #43 does for uploads).

**Approver actions:** approve (an amount up to the code's eligible amount, never above the
policy) or reject, each with a required note; the employee sees the outcome and note.

**Settled after the builder check** (Claude's calls, within the user's decisions; each marked
so the user can check it):
- *Budget is used only by decided claims* (auto-approved, or approved by the approver): a
  ledger of approved amounts per employee and budget period. A flagged claim holds nothing back.
  The eligible amount is worked out again at the moment of each decision, from the budget left
  then, so no sequence of approvals can pass the limit. (Claude's call.)
- *Eligible amount of a flagged claim:* the policy run as usual on its confirmed lines: an
  "other" line counts as eligible (so the approver can only keep or cut it), a banned line is
  Rs 0, capped by the budget left. Undated, out-of-year or much-changed bills are worked out the
  same way; the flag only means a person must look before anything is paid. (Claude's call.)
- *"Shared with family"* only means one Rs 100,000 limit covers the employee's family's bills
  too: no patient or dependant is recorded (less personal data, Principle V). If accounts says
  otherwise, that's a later change. (Claude's call, matching the provisional default.)
- *Mobile/internet:* one cap per calendar month covering both kinds of bill; the month is the
  billing period the AI reads and the employee confirms; a second bill for a month uses what's
  left of that month's cap (decided automatically, as the yearly medical budget is); a bill
  covering several months is flagged. The medical flagging rules for unreadable bills, "other"
  lines and much-changed totals also apply. So the engine models a budget *period* (yearly or
  monthly), which is the point of the second policy. (Claude's call.)
- *Worked examples* are signed off by the author against the written provisional policy, as
  Saifullah signed 004's and 005's; the policy and every decision screen say "provisional,
  pending the accounts department". 009 can be built and merged before accounts replies.
  (Claude's call.)
- *Policy year* is the user's tax year from their profile (`require_profile`, 2025-26), and
  policy modules are keyed by year, as the tax rates are. (Claude's call.)
- *AI limits:* reading a bill counts against its own limit (10 a day per user), separate from
  tax-document extraction, so filing bills never blocks tax documents; the app-wide 100 a day is
  shared (it protects the one free quota). The explanation doesn't count, as the tax summary
  doesn't. (Claude's call.)
- *No one approves their own claim:* an approver's own flagged claims never appear in their
  queue and they can't decide them (`404`, like any claim not theirs to see); any other
  approver handles them, and with no other approver the claim waits. The demo has two
  approvers. (Claude's recommendation, accepted by the user: the usual separation of duties in
  finance.)

## Later list (not in 009)

Fuel and travel claims; vendor invoice check with withholding tax (needs FBR rates); a taxpayer
document inbox; a wealth-gap helper; purchase quotes; education reimbursement.

## Left to the builder (Spec Kit plan)

Table and endpoint design (`specs/009-*/contracts/`, following `docs/api-conventions.md`), the
extraction prompt and schema for bills (with an eval set of synthetic bills, as 003 has), page
layouts, the exact flagging thresholds, the explanation prompt, and how the e2e suite covers the
two roles.
