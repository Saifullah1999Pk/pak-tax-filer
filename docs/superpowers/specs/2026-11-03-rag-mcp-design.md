# 006 RAG Tax Assistant and MCP Server: Design

**Date:** 2026-11-03 · **Status:** Proposed · **Feature:** 006 (README milestone 6) ·
**Governed by:** [Constitution](../../../.specify/memory/constitution.md)

## Intent

README milestone 6: "RAG knowledge base (bounded corpus, pgvector) + retrieval eval + MCP server
(3 tools)". A salaried user asks a tax question and gets an answer drawn only from a fixed set of
FBR texts, with citations, or an explicit "my sources don't cover this". The same search, the
004 tax engine and 003's salary checks are exposed to AI clients (Claude Code, and later 007's
workflow) as exactly three MCP tools.

**Goals:** cited answers from the named corpus; honest refusals; a measured retrieval quality
that CI guards; three working MCP tools.

**Non-goals:** chat history or multi-turn conversation; any source beyond the corpus; the
agentic workflow (007); hosting the MCP server remotely.

**Anti-goals** (failure even if it works):
- answering from general knowledge instead of the passages;
- citing a passage that doesn't say what the answer claims;
- calculating or quoting a tax figure not in the cited passages (Principle I);
- presenting the filing manual as law, or anything as tax advice.

## Corpus (Principle II; constitution "Corpus")

| README source | FBR document used | Location |
|---|---|---|
| ITO §12, §13, §149, §7B, §151 | Income Tax Ordinance 2001, amended up to 31.07.2025 (`download1.fbr.gov.pk/Docs/2025881983148210Income-Tax-Ordinance,-2001-Amended-upto-31.07.2025.pdf`) | the five sections only |
| Form 114(1) (salaried return) guide | PRAL "Normal Income Tax Return User Manual" v1.1, © 2026, hosted by FBR at `e.fbr.gov.pk/SOP/IRIS/Iris_UGD_ITR_Urdu.pdf` (English despite the file name; linked from FBR's IRIS help page) | ch. 4–6 (return filing, salary, tax deduction) |
| Form 116 (wealth statement) guide | same manual | ch. 14 (wealth statement, personal assets/liabilities, reconciliation of net assets) |

FBR publishes no separate Form 114(1) or Form 116 guide for TY2026 (searched 2026-11-03; only
2009–2015 brochures exist). The manual's chapters are the current FBR-hosted equivalent;
**the lead is asked to confirm** this reading of "the guides" in the PR.

**Licensing:** the manual says it may not be reproduced outside its intended organisations
without PRAL's permission. The repo therefore stores only each document's URL, SHA-256 and the
page ranges used; the corpus build downloads the files from FBR and fails if a checksum changes.
The Ordinance is handled the same way for consistency.

**Passages:** each document is split along its own structure (Ordinance sub-sections; manual
headings), each passage keeping source, location (e.g. "§149(1)", "Manual ch. 14.3") and page,
so every citation points somewhere exact. The manual is cited as "how to file", the Ordinance as
"what the law says".

## The assistant (Ask page)

- One question in, one answer out; nothing is stored beyond what's needed to show it.
- The top passages are retrieved; Claude answers **only from them** and returns structured
  output (answer, cited passage ids, "not covered" flag).
- **Code checks** before showing: every citation must be one of the retrieved passages, and every
  number in the answer must appear in a cited passage (004's shared number check). On failure,
  the "not covered" message is shown instead. *"A number"* (builder's call): any digit sequence,
  normalised by removing commas and "Rs"; section and clause references (e.g. "§149",
  "114(1)") count as numbers and must also appear in a cited passage or its location; number
  words ("million", "lakh") are rejected, as in 004, and Claude is told to quote figures exactly
  as the passage writes them.
- **Not covered:** when retrieval finds nothing relevant enough or Claude flags it: "I can only
  answer from [the sources], and they don't cover this." If the question asks for the user's own
  tax figure, a fixed, code-written line is added: "To see your own calculated tax, open the Tax
  page." (decided by Saifullah: outside its sources, no figure). Detection: a yes/no flag in
  Claude's structured output; the line itself is fixed text added by code, and a test with a
  fake client checks it. *(Builder's call.)*
- Every answer carries the "not yet practitioner-reviewed; not tax advice" label.

## Retrieval eval (Principle VI)

- About 30 questions phrased as a salaried user would (not copying passage wording, some
  deliberately tricky), each labelled with the passage(s) that answer it, and about 10
  out-of-corpus questions that must be refused. Written by Claude (decided by Saifullah); the
  file is reviewed by the lead in the PR like any other file. The README and constitution require
  an eval, not human labelling.
- Labels name **stable locations** (e.g. "§149(1)", "Manual ch. 14.3"), not passage ids, so
  retuning passage size doesn't invalidate them. *(Builder's call.)*
- Measured: share of questions whose labelled location is in the top 5 passages; share of
  out-of-corpus questions refused **by the relevance cut-off**. This is retrieval only, needs no
  API key, and so runs in CI on fork PRs. Answer quality with Claude is checked by a separate
  local script, not in CI. *(Builder's call.)* **The pass mark is asked of the lead**; CI fails
  below it.
- **In CI** the FBR files are downloaded once and cached by checksum; if FBR is unreachable and
  there's no cache, the eval job fails loudly rather than skipping. *(Builder's call.)*
- **Text extraction checked (2026-11-03):** the manual's text extracts cleanly (about 83,000
  characters, including ch. 14), so no OCR or AI pass is needed to build the corpus.

## MCP server (exactly three tools; Python MCP SDK)

| Tool | Does | Data |
|---|---|---|
| `search_tax_documents(query)` | same retrieval as the Ask page; returns passages with citations, no written answer | corpus only |
| `calculate_income_tax()` | runs 004's engine for the tax year and ATL status in the token owner's taxpayer profile (feature 002; amended 2026-11-04) and returns figures and breakdown | **the authenticated user's confirmed certificates only** (decided by Saifullah); tests use synthetic users with confirmed dummy certificates |
| `validate_salary_information(fields)` | runs 003's plain-code rule checks on supplied salary figures and returns issues | figures passed in (validation happens before confirmation in 007's flow; it never calculates) |

**Runs locally** over stdio inside the backend container (Claude Code starts it via the repo's
`.mcp.json`, e.g. `docker compose exec -T backend python -m app.mcp_server`; README goal: learn
MCP). As 002's design says, it calls the backend's own functions directly, not over HTTP: the
**same service functions** the API uses (e.g. 003's `confirmed_documents`, 004's tax service),
so confirmed-data and own-data rules live in one place. *(Builder's call, following 002.)*

**Login:** a personal access token the user creates and revokes on a small page in the app; only
its hash is stored; it expires after 90 days. The MCP server reads it from its environment,
checks it against the stored hash, and acts as that user. All three tools require it (no
anonymous use). The web API stays cookie-only; tokens are accepted only by the MCP server.
*(Builder's call.)*

## Approaches (embeddings; decided by Saifullah, needs the lead's approval)

| Approach | Trade-off | Outcome |
|---|---|---|
| A. Small open-source embedding model inside the backend container | No key, no cost, text stays local, **eval runs in CI on fork PRs**; ~100 MB model | **Chosen, pending approval** |
| B. Voyage AI embeddings API | Better quality; new vendor, key, cost; eval can't run on fork PRs (no secrets) | Fallback if the lead prefers |
| C. PostgreSQL keyword search | No new component | Rejected: README specifies pgvector |

Claude has no embeddings API, so any choice adds a stack component; per the constitution, the
lead's approval is recorded in `plan.md`.

## Questions for the lead (in the PR)

1. Approve the embeddings component (A, or B).
2. Is the PRAL 2026 manual's ch. 4–6 and 14 what "the guides" means?
3. Retrieval pass mark (proposed: labelled passage in top 5 for at least 80% of questions; at
   least 90% of out-of-corpus questions refused).
4. Add the First Schedule (salaried slabs) to the corpus? It needs an approved spec change; the
   assistant would only quote it, never compute.

## Out of scope

Chat history; sources beyond the corpus; Urdu questions; remote MCP hosting; MCP tools beyond the
three; the agentic workflow (007); telemetry (008).

## Decisions left to the builder

Passage size and overlap, number of passages retrieved, the relevance cut-off, the answer model
setting (same pattern as 003/004), the embedding model's exact name, table layout, token UI.

## Done when

- The corpus builds from FBR URLs with checksums; every passage has source, location and page.
- Ask page answers cite real retrieved passages; uncovered questions are refused; label shown.
- The retrieval eval runs in CI and meets the agreed pass mark.
- The three MCP tools work from Claude Code (stdio) with a personal access token;
  `calculate_income_tax` uses only confirmed certificates.

## Addendum 2026-11-11: building it after the Gemini switch and the redesign

This design (and 006's plan) was written for Claude and a local embedding model. Since then the
app uses Gemini (free tier, `google-genai`; 003's "Stack change"), runs in production on one
1 GB e2-micro VM, and has a new look and navigation (001, User Story 6). Three decisions, made
with Saifullah on 2026-11-11 (superpowers:brainstorming):

### 1. Embeddings: Gemini's API (replaces approach A above)

| | Approach | Trade-off | Outcome |
|---|---|---|---|
| A | **Gemini embeddings** (`gemini-embedding-001`, 768 dimensions), stored in pgvector | Same key and provider as the rest of the app, free, nothing extra in memory on the 1 GB VM; the retrieval eval needs the key, so it can't run on fork PRs (the extraction eval already has this limit) | **Chosen** ("we could just use gemini ... we're already using it") |
| B | Local `fastembed` (bge-small), as first planned | Offline, eval runs anywhere; about 0.3-0.5 GB of memory and a bigger image on a VM already holding Postgres and the backend; a new stack component needing the lead's approval | Rejected |
| C | PostgreSQL keyword search | No embeddings | Rejected: the README specifies pgvector |

No new stack component, so PR #11's question 1 (embeddings approval) no longer applies. The
corpus is embedded once when it's built; each question costs one embedding call. Passage and
question embeddings use Gemini's retrieval task types (document vs query).

### 2. Answers: up to 15 seconds, with visible progress (replaces SC-004's 10 s)

Gemini answers take about 3-9 s from Pakistan (measured on 004's summaries), and an answer is
shown only after code checks it, so it can't be streamed. Options: 15 s with visible steps
(chosen); keep 10 s and fail slow answers more often; stream (rejected: shows unchecked text).
The Ask page shows "Searching the FBR texts…" then "Writing a cited answer…", then the checked
answer or the not-covered message. The answer call has a 15 s limit; past it, "That took too
long; try again." SC-004 becomes "an answer or a not-covered message appears within 15 seconds,
with progress shown while waiting".

### 3. Navigation for the whole app: flat on computers, grouped on phones

By 008 the app has about nine destinations: Home, Documents, Tax, Wealth statement, Guided filing
(007), Ask (006), Profile, Connect an AI assistant (006's tokens), Activity (008's telemetry
view). Options considered: grouped, flat where there's room (chosen); submenus everywhere (an
extra click on computers for core steps); a "More" tab (buries core steps); a side menu (heavy
for nine items; everything two taps away on phones).

- **Computers (720 px and up):** header links Home, Documents, Tax, Wealth statement, Ask (and
  Guided filing when 007 lands), then a profile icon opening a menu: Profile, (Activity in 008),
  Log out.
- **Phones:** a bottom bar of four: Home, Filing, Ask, Account. "Filing" opens a sheet with
  Documents, Tax, Wealth statement (and Guided filing); "Account" opens one with Profile,
  (Activity) and Log out. The current page's group is marked.
- New filing steps join Filing; new settings join Account, so the bar stays at four.
- 001's frame tests change with it (the five-link navigation becomes this structure); it is
  built in 006 because Ask is the first page that needs it.

### 4. MCP is for developers; tokens come from a command (replaces the token page)

The MCP server serves Claude Code on a developer's machine, as the README frames it (a training
goal: "learn ... Claude Code itself — hooks, permissions, MCP"). Options considered: a token page
only in local copies; remote MCP on the live site (a real-user feature beyond the README, and a
path to production data); tokens from a command, no page (chosen, Saifullah 2026-11-11). Tokens
are created with `python -m app.cli create-token --email <user>` (printed once; only the hash is
stored; 90 days) and removed with `revoke-token`, like `create-user` today. There is no "Connect
an AI assistant" page or menu entry. The MCP server still runs locally over stdio and acts as
the token's owner, as before.

**Clients: Gemini CLI and Claude Code.** MCP is an open standard, so one server serves any
client. Options considered: both (chosen, Saifullah 2026-11-11), Gemini CLI only (drops the
README's Claude Code learning goal), Claude Code only (out of step with the Gemini stack).
`docs/` shows how to connect each (Gemini CLI's settings file, the repo's `.mcp.json`), and
quickstart checks the three tools from both. Gemini CLI's current MCP setup is confirmed when
built, not assumed.

### 5. A whole-app daily cap on Ask (protects the shared free quota)

Every feature shares one free-tier Gemini key, and extraction (core to filing) is already capped
at 100 a day for the whole app. Ask gets the same kind of cap, beside its 30 per user per hour:
**200 questions a day for the whole app** (a setting), counted and locked the way
`use_extraction` is. Past it: "The tax assistant has reached today's limit; try again tomorrow."
The MCP `search_tax_documents` tool counts towards it too (each search embeds the query). Chosen
over accepting the risk (Saifullah, 2026-11-11).

### Unchanged

The corpus, the code checks before an answer is shown, the not-covered behaviour, the three MCP
tools and personal access tokens, the 30 questions per user per hour, and the practitioner
label. PR #11's other questions stay open with their proposed defaults: the manual's chapters
are "the guides"; the pass mark has both its parts (the labelled passage in the top 5 for at
least 80% of questions, and at least 90% of out-of-corpus questions refused by the relevance
cut-off); the First Schedule stays out of the corpus.

### Builder check (2026-11-11)

- **The retrieval eval needs the Gemini key now**, so it runs as the extraction eval does: in CI
  where the repository secret exists; a fork PR attaches a local run's report instead. FR-011's
  "on every pull request, without secrets" can't hold; the lead is told in the PR.
- **Building the corpus** (my call): a one-off command, `python -m app.rag.build`, run locally and
  once on the VM after a deploy that changes the sources (documented in `docs/deployment.md`),
  never on every deploy. It is all-or-nothing: if a download, a checksum or an embedding fails,
  the existing passages stay and Ask keeps working. Before the first build, Ask says "The tax
  assistant isn't ready yet" instead of answering.
