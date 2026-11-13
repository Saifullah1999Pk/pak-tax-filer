# Quickstart: Policy-Based Bill Approval Agent (009)

Validates the feature end to end. Contract: [contracts/claims-api.md](contracts/claims-api.md);
data: [data-model.md](data-model.md). Synthetic bills only (Principle V).

## Prerequisites

- The app running (`docker compose up -d`), migrated (`docker compose exec backend alembic
  upgrade head`), with a Gemini key in `.env` for the live scenarios.
- Three synthetic users with profiles (tax year 2025-26): `employee@example.com`, and two
  approvers made with `docker compose exec backend python -m app.cli make-approver --email
  approver1@example.com` (and `approver2@…`).
- Synthetic bills from `docker compose exec backend python -m evals.claims.generate`.

## Scenarios

1. **A medical bill decided by the policy (US1):** as the employee, on Claims choose Medical and
   upload the synthetic bill with medicines (Rs 4,200) and a baby product (Rs 800). **Expected:**
   the lines appear with categories; after Confirm, Rs 4,200 approved, Rs 800 cut ("baby products
   aren't covered"), Rs 95,800 left; the explanation has only those numbers; the provisional label
   shows. Under 3 minutes (SC-001).
2. **Editing (US1, clarifications):** upload another bill, add a line and remove one, confirm.
   **Expected:** a change under 10% of the read total is decided automatically; over 10% is
   flagged "total changed".
3. **The budget edge (US1):** with a test user whose budget left is Rs 3,000 (from earlier
   claims), confirm a Rs 5,000 bill. **Expected:** Rs 3,000 approved, "budget used up", Rs 0 left.
4. **An approver decides (US2):** as the employee, confirm a bill with a line in "other".
   **Expected:** flagged. As approver1: it's in the queue; approving more than the eligible
   amount is refused; approving less with a note decides it; the employee sees the note.
5. **No self-approval (US2):** as approver1, submit a flagged claim of your own. **Expected:** it
   isn't in approver1's queue and opening it as an approver is "not found"; approver2 sees and
   decides it. As the employee, `/approvals` and another person's claim are "not found".
6. **Mobile bills (US3):** confirm a March mobile bill of Rs 2,200, then a March internet bill
   of Rs 1,500. **Expected:** Rs 2,200, then Rs 800 ("March's cap used up"); a handset line cut;
   a January–March bill flagged "several months".
7. **Withdraw:** withdraw a flagged claim. **Expected:** it leaves the queue and uses no budget;
   withdrawing a decided claim is refused.
8. **Google busy:** (e2e) a bill the fake Gemini times out on says "busy, press Retry" and costs
   no try.
9. **Tests and checks:**

   ```bash
   docker compose exec backend pytest tests/claims tests/guardrails
   uv run --project backend python scripts/validate_contracts.py --all
   docker compose exec frontend npm test
   # e2e: see e2e/README.md
   docker compose exec backend python -m evals.claims.run   # needs GEMINI_API_KEY (SC-006)
   ```

   **Expected:** all pass; the eval shows line amounts ≥ 90% and categories ≥ 85%.
