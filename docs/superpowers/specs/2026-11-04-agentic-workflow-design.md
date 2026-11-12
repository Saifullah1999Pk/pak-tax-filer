# 007 Agentic Workflow: Design

**Date:** 2026-11-04 · **Status:** Proposed · **Feature:** 007 (README milestone 7) ·
**Governed by:** [Constitution](../../../.specify/memory/constitution.md)

## Intent

README milestone 7: "Agentic workflow wiring (document/validation/research agents, state
machine, human-approval gate before calculation)"; MVP: "document → validate → research →
calculate → explain → review with a mandatory human-approval gate before calculation". A
logged-in user runs one guided flow that takes them from their certificates to an explained tax
result, stopping for their approval before anything is calculated. It is also the project's
exercise in agentic workflows (README goal).

**Goals:** one run per user that remembers its step and resumes; document, validation and
research agents; a gate that blocks calculation until the user approves; runs end to end on
synthetic documents (roadmap).

**Non-goals:** new tax rules or document types; the wealth statement (stays its own page, as in
the README's list); PDF export and telemetry (008); filing on IRIS; replacing the existing pages
(the run sits **alongside** them; decided by Saifullah).

**Anti-goals** (failure even if it works):
- any agent confirming a certificate, changing a figure, or approving the gate (Principle III);
- any tax figure produced or adjusted by an AI (Principle I);
- unconfirmed data reaching the calculation;
- a research passage shown without its citation, or a cited passage that isn't from the corpus
  (Principle IV).

## Constraints

Builds on 002 (login, taxpayer profile), 003 (upload, confirmation, rule checks), 004 (engine,
breakdown, number check), 006 (search, the functions behind the three MCP tools). Stack as in the
constitution; no new components. Synthetic data only.

## The run

| Step | Who | Does |
|---|---|---|
| 1. Document | document agent | Checks the user's documents: a confirmed salary certificate is required, a bank certificate optional. Says in plain words what's missing and links to 003's pages. Never confirms anything. |
| 2. Validate | validation agent | Runs 003's rule checks on each confirmed certificate (salary checks through `validate_salary_information`, bank checks through 003's same rules module) and explains any issue, naming the certificate to fix. Never changes figures. |
| 3. Research | research agent | Chooses search queries for the user's situation, uses 006's search, and writes a short plain note on which passages apply and why (expected: salary §12, §149; with bank profit §7B, §151), each passage with its citation. |
| 4. Approval gate | the user | Sees confirmed figures, profile (tax year, ATL status) and the validation result; approves or goes back. |
| 5. Calculate | code | 004's engine. No agent. |
| 6. Explain | code (+ 004's checked summary) | 004's breakdown plus the step-3 passages as "where this comes from". |
| 7. Review | the user | Reads the result and marks the run done. |

**Any change to the inputs after approval** (a certificate added, deleted or re-confirmed; the
profile changed) sends the run back to step 4 and clears the old result (decided by Saifullah).
Steps 1–3 re-run first on the new inputs, so the gate never shows stale checks or passages; the
same happens for a change before approval. *(Builder's call.)*

## Approaches

| Approach | Trade-off | Outcome |
|---|---|---|
| **A. Backend state machine; small agents at steps 1–3** | Order and gate enforced and testable in code; agents are single Claude calls with tool use over the same functions as 006's MCP tools; Claude doesn't choose the flow | **Chosen** (Saifullah) |
| B. One orchestrator agent looping over the MCP tools | More autonomous; order not guaranteed, gate still needs a code check, harder to test, not a "state machine" | Rejected |
| C. As A, but agents call the real MCP server as clients | MCP end to end; an extra process per run, same results | Rejected (006 already exercises MCP) |

The Claude Agent SDK was not considered further: it would be a new stack component needing the
lead's approval.

## Decisions

- Approach A; alongside the existing pages; wealth statement outside the run; changes after
  approval return to the gate (Saifullah).
- One active run per user and tax year; starting again replaces a finished run. *(Builder's
  call.)*
- The gate is a recorded user action checked by the backend before step 5; agents have no tool
  that approves, confirms or edits. *(Builder's call.)*
- **Validation issues warn, they don't block approval**: the user is the authority on their
  documents (Principle III), and 003 already lets a certificate be confirmed with a rule issue
  shown. The issues are listed again on the gate screen. *(Builder's call; consistent with 003.)*
- **Number checks:** document and validation agent text passes 004's number check against the
  figures it was given; research text passes 006's check (every number appears in a cited
  passage, citations only from passages search returned). Failing text is replaced by plain
  code-written messages. *(Builder's call.)*
- **The result is recalculated, not stored** (as in 004). The run stores its step, the approval
  time and a fingerprint of the approved inputs; viewing the result recalculates from those
  inputs, and a fingerprint mismatch means "inputs changed" and returns to the gate. "Done"
  records only when the user marked it. *(Builder's call; consistent with 004.)*
- Without an API key, or if an agent fails, each agent step falls back to its plain-code result
  (missing-document list, rule issues, passages from search), so the run still completes.
  *(Builder's call.)*
- Every result screen carries the "not yet practitioner-reviewed" label. *(Builder's call.)*

## Done when

- A synthetic user goes from no documents to an explained result through the run.
- Calculation cannot happen without an approval recorded after the latest input change (tested).
- No agent output can confirm, edit, approve or introduce a tax figure (tested).
- The existing pages still work on their own.

## Left to the plan

Run table and states, API shape, model setting (same pattern as 003/004), prompts and tool
definitions, how input changes are detected, and the page layout.

## Addendum 2026-11-12: after the stack change and feature 006

The design above stands (approach A, alongside the existing pages, no wealth statement, changes
return to the gate). This updates it for what changed since 4 November. Decided by Saifullah:
adjust 007 to the stack as built; Awais's policy-based bill-approval agent (2026-11-11) is **not**
part of 007 and is left for after 008.

- **Gemini, not Claude.** Each agent is one Gemini call with function calling through
  `google-genai`, as 003–006 call Gemini; a `WORKFLOW_MODEL` setting (default
  `gemini-3.5-flash-lite`, effort `minimal`), like 006's `ANSWER_MODEL`. The Claude Agent SDK
  question no longer arises. No new dependency.
- **Research uses 006's search as built:** `app.rag.search` with its relevance cut-off, and its
  text passes 006's checks (`app.rag.checks`: citations among the passages found, every number
  with its scale from a cited passage). The research agent writes its own queries; no question
  the user types reaches it.
- **Time:** each agent step has 15 seconds, as 006's answers do (was 10). The page shows what
  each step is doing while it waits ("Checking your documents…", "Checking the figures…",
  "Finding the law that applies…"), like the Ask page. *(Proposed by Claude, accepted.)*
- **Shared free quota:** one run of steps 1–3 counts as one question against 006's limits (30
  an hour per user, 200 a day for the app), counted with 006's `use_question`. Past a limit, the
  steps use their code-written results, so the run still reaches the gate (SC-005). *(Proposed
  by Claude, accepted.)*
- **Navigation:** "Guided filing" joins the Filing group: a top-bar link on computers, an entry
  in the Filing sheet on phones (006's navigation, designed for it), and a link from Home.
- **Number checks** use 004's shared check, which since 006's review also refuses a scale stuck
  to digits ("26m").
- **Housekeeping:** the migration is `0008_workflow` (006 took 0007).
