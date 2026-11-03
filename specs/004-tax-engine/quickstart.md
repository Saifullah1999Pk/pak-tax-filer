# Quickstart: validating the Deterministic Tax Engine (004)

**Prerequisites:** features 001–003; a demo user with confirmed synthetic certificates;
`ANTHROPIC_API_KEY` only for the summary check in section 2.

## 0. Worked examples signed off (before any engine code)

Open `backend/tests/tax/worked_examples.yaml`. Every example must show the hand-working with its
source row, and `signed_off_by` / `signed_off_date` filled in after checking against the Ordinance.
`pytest -k sign_off` fails until all are signed.

## 1. Results (User Story 1)

*Figures below are illustrative; the authoritative cases are the signed-off worked examples.*

1. Confirm a salary certificate with taxable salary Rs 1,800,000 and tax deducted Rs 75,000; open
   **Tax**, answer ATL "yes". Expected: salary tax Rs 72,000, over-deducted Rs 3,000
   ([contract](contracts/tax-api.md)).
2. Add a second confirmed salary certificate: figures are summed.
3. Add a bank certificate (profit Rs 50,000, withheld Rs 10,000): profit tax Rs 10,000, balance 0;
   balances shown separately, no combined total.
4. The "not practitioner-reviewed" label is visible.

## 2. Explanation (User Story 2)

1. Each step shows its rule location.
2. With an API key: a summary appears and every number in it appears in the steps.
3. Run `pytest -k summary_check`: a summary with a wrong number is rejected.

## 3. Honest limits (User Story 3)

Leave ATL unanswered; delete all salary certificates; confirm a bank certificate with profit
Rs 5,000,001: each shows its reason and no figures. Answer ATL "no" with 40% withheld: the
difference is labelled "to be confirmed".

## 4. Traceable rates (User Story 4)

`pytest -k rates`: every rate has a source; the band-continuity check passes. Change one fixed
amount by 1 rupee locally: the check fails. Revert.

## 5. All tests

```bash
docker compose exec backend pytest
docker compose exec frontend npm test
```
