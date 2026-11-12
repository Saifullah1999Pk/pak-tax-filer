# Quickstart: Agentic Workflow (007)

Validates the feature end to end. Contract: [contracts/workflow-api.md](contracts/workflow-api.md).

## Prerequisites

Features 002–006 built; stack running; corpus built (006); a demo user with a profile (ATL
"yes") and one confirmed synthetic salary certificate (taxable Rs 1,800,000, tax deducted Rs
75,000). `GEMINI_API_KEY` set for scenario 1; unset for scenario 4 (or a question limit reached:
the same code-written results).

## Scenarios

1. **Run to the gate (US1):** open `/workflow`, start. Expected: document step says the bank
   certificate is optional; validation finds no issues; research shows §12/§149 passages with
   locations; the gate shows the figures, 2025-26 and ATL "yes".
2. **Approve and review (US2):** approve. Expected: the result equals the Tax page (salary tax
   Rs 72,000, over-deducted Rs 3,000) with breakdown, passages and the practitioner label. Mark
   done → "Done" with today's date. From start to result takes under 3 minutes, excluding
   reading (SC-001).
3. **Changes (US3):** confirm a bank certificate (profit Rs 50,000, withheld Rs 10,000), reopen
   `/workflow`. Expected: back at the gate, research now includes §7B/§151, no old result;
   `GET /api/workflow/result` → `409` until approved again.
4. **No API key:** repeat scenario 1. Expected: each step shows its plain result marked as such,
   and the run still reaches a result.
5. **Tests:**

   ```bash
   docker compose exec backend pytest tests/workflow
   docker compose exec frontend npm test -- WorkflowPage
   ```

   Expected: all pass, including the gate guardrail tests.
