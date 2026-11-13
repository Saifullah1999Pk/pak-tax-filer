# End-to-end tests

The real app in a real browser (Playwright, Chromium): pages, API, database and the AI clients
together, the way a user goes through them. The unit and API tests check the parts; these check
the main flows still work end to end. CI runs them on every pull request (job `e2e`).

| Test | Flow |
|---|---|
| `tax.spec.ts` | Sign up → profile → upload a salary certificate → confirm its figures → the Tax page (Rs 72,000 salary tax, Rs 3,000 over-deducted, the label) → Download PDF |
| `wealth.spec.ts` | The same certificate → wealth statement → save → a labelled result → Download PDF |
| `workflow.spec.ts` | Guided filing: start → stops for approval (no result yet) → approve → the result → mark done |
| `busy.spec.ts` | An upload Google times out on (its 504) says so, offers Retry, and costs no try |

## No real AI, no real data

The stack runs with a **fake Gemini** (`fake_gemini/server.py`): `docker-compose.e2e.yml` sets
`GOOGLE_GEMINI_BASE_URL`, which the google-genai SDK reads, so the app's real Gemini clients talk
to it and the app has no test switch. It answers by the request's structure (the reply schema,
tools, the endpoint) with fixed synthetic data: a salary certificate with Rs 1,800,000 taxable
and Rs 75,000 deducted, a bank certificate, replies with no numbers for the summaries and agents,
"not covered" for the assistant, and Google's 504 for a file containing `E2E-GOOGLE-TIMEOUT`.

Each test signs up its own `e2e-…@example.com` user and uploads a one-page PDF it makes itself,
so tests don't depend on each other and no real document is used (Principle V).

## Running them locally

The e2e stack uses the development ports (8000, 5173), so stop the development stack first; its
data is kept. Run from the repository root:

```bash
docker compose stop                                   # the development stack (data kept)
docker compose -p pak-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build
docker compose -p pak-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec backend alembic upgrade head
cd e2e && npm ci && npx playwright install chromium   # once
npx playwright test                                   # about 10 seconds
docker compose -p pak-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v   # when done
docker compose start                                  # back to development
```

`-p pak-e2e` gives the e2e stack its own containers and database: it never touches development
data. A failed test leaves a screenshot and a trace in `test-results/`
(`npx playwright show-trace <trace.zip>`); in CI the report is attached to the run.

## Adding a test

- One flow per file in `tests/`, starting from the helpers in `tests/helpers.ts`
  (`signUpWithProfile`, `uploadSalaryCertificate`, `confirmEveryFigure`, `userWithConfirmedSalary`).
- Find elements as a user does (role, label, text), as the frontend's own tests do.
- Wait for what the user would see (e.g. every "Confirmed." before "Confirm document"), never a
  fixed delay.
- If a flow needs a new kind of AI answer, add it to `fake_gemini/server.py`, recognised by the
  request's structure, never by prompt wording.
