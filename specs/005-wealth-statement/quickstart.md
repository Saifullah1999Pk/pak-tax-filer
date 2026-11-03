# Quickstart: validating the Wealth Statement (005)

**Prerequisites:** features 001–004; a demo user with confirmed synthetic certificates;
`ANTHROPIC_API_KEY` only for the summary check in section 2.

## 0. Worked examples signed off (before any reconciliation code)

Open `backend/tests/wealth/worked_examples.yaml`. Every example must show the hand-working,
citing the IRIS FAQ formula and the SRO 1495 lines, with `signed_off_by` / `signed_off_date`
filled in. `pytest -k wealth_sign_off` fails until all are signed.

## 1. Enter and reconcile (User Story 1)

*Figures are illustrative; the authoritative cases are the signed-off worked examples.*

1. Confirm a salary certificate (gross Rs 2,000,000, taxable Rs 1,800,000, tax deducted
   Rs 75,000) and a bank certificate (profit Rs 50,000, withheld Rs 10,000).
2. Open **Wealth statement**: lines 7031, 7032, 7033 and the tax line are filled in, read-only,
   each naming its certificate.
3. Enter the assets, liability, previous net assets and expenses from the
   [contract example](contracts/wealth-api.md); save. Expected: "reconciles", unreconciled 0.
4. Reload the page: entries are still there, and the result appears within 5 seconds (SC-006).
5. The "not practitioner-reviewed" label is visible.

## 2. Explanation (User Story 2)

1. Lower rent by Rs 40,000 and save (outflows fall, so inflows − outflows = Rs 505,000 against
   an increase of Rs 465,000): "inflows exceed the growth in your assets by Rs 40,000", and the
   missing-asset or expense checklist, with no amounts in it.
2. Restore rent, then add a Rs 40,000 asset (increase Rs 505,000 against Rs 465,000): "your
   assets grew Rs 40,000 more than your inflows explain", and the missing-inflow checklist.
3. Each step shows its form line. With an API key, a summary appears and every number in it is
   in the steps. `pytest -k number_check` covers a wrong-number summary.

## 3. Limits and sync (User Story 3)

1. Clear previous net assets: not ready, with the reason.
2. Delete the salary certificate: not ready. Re-upload and confirm it: the notice says
   certificates changed since the last save.
3. Confirm a bank certificate with profit Rs 5,000,001: not ready, the same message as the tax
   page.
4. Confirm a certificate with gross below taxable: not ready, naming that certificate.

## 4. All tests

```bash
docker compose exec backend pytest
docker compose exec frontend npm test
```
