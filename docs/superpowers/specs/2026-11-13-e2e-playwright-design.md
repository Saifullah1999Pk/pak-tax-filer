# End-to-end tests with Playwright: design

2026-11-13. Requested by the lead (Awais, 2026-11-12: "Playwright is a testing tool and its
purpose is to test the application; you should add some e2e tests also"), after his uploads
failed on the live site.

## Intent

Drive the real app in a real browser, the way a user does, so a broken main flow ("upload isn't
working") is caught in CI before anyone sees it. The unit and API tests check the parts; nothing
today checks that the pages, the API, the database and the AI clients work together.

**Goals:** the main flows pass in Chromium against the Docker stack, locally and in CI, with no
real AI and no real data. **Non-goals:** every page and edge case (the unit and API tests cover
those), other browsers, visual comparison, load. **Anti-goals:** a flaky suite; tests that call
real Gemini (quota, Principle VI's "tests never call the real AI"); a test switch inside the app.

## Approaches (the user chose B)

| | Approach | Trade-off |
|---|---|---|
| A | An `AI_MODE=fake` setting in the backend, on only in an e2e compose file | Quickest; but a test switch in production code, needing a guard |
| **B** | **A fake Gemini server in the e2e stack; the app's real clients point at it** | **No test code in the app, and the real clients are exercised; more work to give believable answers** |
| C | Only flows without AI | Skips upload → confirm → tax, the flow that broke |

B works without changing the app: the google-genai SDK reads `GOOGLE_GEMINI_BASE_URL` from the
environment (checked in google-genai 3.0.0, `_base_url.py`).

## Design

- **`e2e/fake_gemini/server.py`**: a small Python standard-library HTTP server standing in for
  `generativelanguage.googleapis.com`. It tells each request apart by what the app sends, never by
  prompt wording, and answers as Gemini would:
  - `…:batchEmbedContents` / `…:embedContent`: fixed 768-number vectors;
  - `…:generateContent` with a `document_type` in the response schema (extraction): a salary
    or bank certificate's fields, chosen by the fields the schema asks for, with synthetic
    figures (taxable salary Rs 1,800,000, tax deducted Rs 75,000, so a known tax result);
  - with a `not_covered` field (the assistant): a refusal, as no corpus is built in e2e;
  - with tools (the guided run's agents): a short reply with no numbers;
  - anything else (the summaries): a sentence with no numbers.
  A header in the request can ask for a 504, to test the "Google is busy" path from PR #43.
- **`docker-compose.e2e.yml`**: an override adding the `fake-gemini` service and setting the
  backend's `GOOGLE_GEMINI_BASE_URL=http://fake-gemini:8080` and a placeholder `GEMINI_API_KEY`.
  Run under its own project name (`-p pak-e2e`), so it never touches the development database.
  Migrations run once the stack is up.
- **`e2e/`**: its own `package.json` with `@playwright/test`, Chromium only; `e2e/tests/*.spec.ts`;
  a synthetic one-page PDF made in the test (Principle V: no real documents). Each test signs up a
  fresh `e2e-<random>@example.com` user, so tests don't depend on each other.
- **First tests:**
  1. sign up → set the profile → upload a salary certificate → review and confirm → the Tax page
     shows Rs 72,000 salary tax and the practitioner label → Download PDF saves a file;
  2. the wealth statement: enter the example statement → it reconciles;
  3. guided filing: start → approve → the result;
  4. an upload Google times out on shows the "busy, press Retry" message (with #43).
- **CI:** a job `e2e` that starts the stack, runs migrations, runs Playwright, and uploads the
  report when something fails.
- **Docs:** a short `e2e/README.md` (running it locally, adding a test) and a line in
  `CLAUDE.md`'s commands table.

## Decided by the builder (my calls)

Chromium only; standard-library server (no new dependency); the fake answers are fixed, not
configurable beyond the 504 header; a test that needs #43's message joins once #43 is merged
(this branch stacks on it).

## Left to the builder

Selectors (by role, label and text, as the frontend tests do), timeouts, and whether test 4 needs
a header the browser can't set (if so, a fake-server setting for that one test).
