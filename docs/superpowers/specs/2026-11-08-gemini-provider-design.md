# Free AI provider: Gemini instead of Claude: Design

**Date:** 2026-11-08 · **Status:** Proposed · **Affects:** 003 now; 004–007 when built ·
**Governed by:** [Constitution](../../../.specify/memory/constitution.md)

## Intent

The lead has no Claude API key to give and asked for "anything free" (2026-11-07). The app's AI
features move to **Google's Gemini API free tier**. Feature 003 (document extraction) is already
built on Claude and is rewritten now; 004–007 use Gemini when they are built. The lead's message
is the approval the constitution requires for a stack change; it is recorded in 003's plan.

## Goals, non-goals, anti-goals

- **Goals:** 003 extracts figures with Gemini on the free tier; every test still runs with no key;
  the accuracy eval runs within the free limits and picks the model; the docs that name Claude say
  Gemini.
- **Non-goals:** a provider-neutral layer (approach B below); the paid tier; any change to 003's
  rules, review, confirmation or frontend; building 004–007 now.
- **Anti-goals:** the AI producing or checking any tax figure (Principle I, unchanged); real
  documents (Principle V, unchanged; it matters more now, see Constraints).

## Constraints (from Google's docs, read 2026-11-08)

- **Free models:** `gemini-3.8-flash`, `gemini-3.6-flash` (Flash); `gemini-3.5-flash-lite`,
  `gemini-3.1-flash-lite` (Flash-Lite); embeddings `gemini-embedding-2`, `gemini-embedding-001`.
- **Free limits aren't published:** they are set per project and shown in AI Studio; reports range
  from about 20 to 1,500 requests a day for Flash. Daily quotas reset at midnight Pacific time; an
  exceeded limit returns `429 RESOURCE_EXHAUSTED`.
- **No Batch API on the free tier**, so the eval sends cases one at a time.
- **Free-tier content is used to improve Google's products.** Acceptable only because the app
  handles synthetic data alone (Principle V); the upload page's demo notice already says so.
- **PDFs:** up to 50 MB or 1,000 pages, inline or via the Files API (our limit stays 10 MB and 5
  pages).
- **Key:** created in AI Studio, no card. It lives in the uncommitted `.env` as `GEMINI_API_KEY`.

## Approaches

| Approach | Trade-off | Outcome |
|---|---|---|
| A. Gemini through Google's official `google-genai` SDK | The only free option covering PDF and photo input, JSON output, tool calls (007) and embeddings (006) with one key; low, unpublished daily limits | **Chosen** (Saifullah, 2026-11-08) |
| B. Provider-neutral, OpenAI-compatible client (Gemini, OpenRouter, Groq by setting) | Flexible, but PDF and JSON support differ by provider; more testing for flexibility not needed yet | Rejected |
| C. Keep Claude, wait for a key | Not free | Rejected (lead: "anything free") |

Others considered and dropped: OpenRouter free models (50 requests a day, rotating list, vision
varies), Z.ai GLM-4.6V-Flash (small provider, free tier "may change"), Groq and Mistral (no free
vision), DeepSeek (no free tier), a local model (can't run on the 1 GB server).

## Decisions

- **SDK:** `google-genai`, using the call style Google's current docs show (the Interactions API:
  the PDF as a `document` part or the photo as an `image` part, then the instructions, with
  `response_format` set to JSON and the schema from the existing Pydantic models; the reply's
  text validated with `model_validate_json`).
- **Unchanged in 003:** the `Extractor` interface, `FakeExtractor`, the prompt, the schemas,
  normalisation, the rule checks, the review and confirmation flow, the frontend, the eval's
  scoring and generator.
- **`ClaudeExtractor` becomes `GeminiExtractor`:** the same inputs and outputs, a 60-second
  limit, and every failure turned into a short reason. A `429` says the free daily limit may be
  used up and to try later. Gemini has no server-side refusal fallback; a blocked or empty reply
  fails the document with a reason, as a refusal did.
- **Settings:** `GEMINI_API_KEY` replaces `ANTHROPIC_API_KEY` (still optional; still kept out of
  repr). `EXTRACTION_MODEL` defaults to `gemini-3.8-flash`. Docker Compose passes the new key
  through. `SUMMARY_MODEL` (004) defaults to a Gemini model too.
- **Model choice:** the eval runs on `gemini-3.8-flash` and `gemini-3.5-flash-lite`. Flash-Lite
  is chosen if it meets the bars, since its free limit is reported to be higher; otherwise Flash.
  **Outcome (2026-11-09):** Flash-Lite passed with 280 of 280 fields and is the default; Flash hit
  Google's 60-second deadline on a PDF on the free tier.
- **Eval runner:** one request per case instead of a batch, paced to stay under the per-minute
  limit, retrying a `429` after a pause; it stops with a clear message if the day's limit is
  reached, so a run may need two days. Scoring, bars and the report are unchanged.
- **CI eval workflow:** uses a `GEMINI_API_KEY` secret; otherwise unchanged.
- **Docs amended before the code (constitution workflow):** the constitution's stack line (a
  PATCH recording the lead's approval), `.claude/rules/architecture.md` ("Claude is used
  in exactly three places" becomes "the AI model"), 003's spec, plan, research (R1, R6–R8),
  contracts/eval.md, quickstart and tasks (new tasks for the rewrite). 004–007's plans get one line
  each saying they use Gemini, with details settled when each is built.
- **`.env.example`:** Claude may not read `.env*` files, so Saifullah renames
  `ANTHROPIC_API_KEY=` to `GEMINI_API_KEY=` in it by hand.

**README (builder's call, 2026-11-08):** left as the lead wrote it, as with the switch to FastAPI;
the constitution wins where they differ, and the PR says so.

**SDK call style (builder's call, 2026-11-08):** google-genai 3.0.0's typed
`client.aio.models.generate_content` (`response_mime_type="application/json"`,
`response_json_schema`, `ThinkingConfig`, `Part.from_bytes` for the PDF or photo) instead of the
Interactions API the docs now lead with: it is fully typed, so strict mypy checks it, and tests
can inject an `httpx2.AsyncClient` with a mock transport, as 003's Claude tests did.

## Left to the builder

The exact SDK calls, after checking the installed SDK version (the Interactions API or the
older `generate_content`), how to turn off or lower "thinking" for a reading task, the timeout
setting, the SDK's error classes, and how tests intercept HTTP (an injected transport if the SDK
allows it, otherwise a fake client object). Pacing numbers once AI Studio shows the project's
limits.
