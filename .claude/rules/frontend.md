---
paths:
  - "frontend/**"
---

# Frontend Conventions (React + TypeScript)

- Function components and hooks; one page per file in `src/pages/`, its test beside it.
- Call the backend only through the helper in `src/api/`; never `fetch` directly in components.
- Money arrives as decimal strings: display it, never calculate with it (Principle I).
- Tests use React Testing Library and find elements as a user would (role, label, text), not by
  CSS classes or test ids.
- Keep TypeScript strict; no `any` without a comment explaining why.
- Show the "not yet practitioner-reviewed" label wherever a tax or wealth result appears
  (Principle IV).
- Check input in the frontend too, with the shared rules (the lead, 2026-11-16): every amount
  box is `MoneyInput` with the `AmountRule` its backend accepts (`components/amountRule.ts`);
  uploads and tax years use `components/fieldRules.ts`. Block the submit while a rule fails; the
  server still checks.
