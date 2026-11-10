# Contract: Wealth API

Requires `current_user`. Follows the
[API conventions](../../001-repo-foundations/contracts/api-conventions.md): money as decimal
strings (whole rupees), `{"detail": ...}` errors. A user only ever reads or writes their own
statement.

## GET /api/wealth/{tax_year}

Returns the saved statement (empty if never saved), the auto-filled lines and the freshly
computed result.

```json
{
  "tax_year": "2025-26",
  "statement": {
    "previous_net_assets": "2100000",
    "assets": [
      { "category": "bank_account", "description": "Savings account, synthetic bank", "amount": "1565000" },
      { "category": "motor_vehicle", "description": "Car, 2019 model", "amount": "1200000" }
    ],
    "liabilities": [ { "description": "Car loan", "creditor": "Synthetic bank", "amount": "200000" } ],
    "other_exempt_income": "0", "foreign_remittance": "0", "inheritance": "0",
    "gifts_received": "0", "family_contribution": "0", "gifts_given": "0",
    "expenses": { "rent": "600000", "electricity": "300000", "other_household": "600000" },
    "saved_at": "2026-11-03T12:00:00Z"
  },
  "auto_filled": [
    { "line": "7031", "label": "Taxable salary", "amount": "1800000", "certificates": ["Salary certificate uploaded 2026-11-03 10:15:02 UTC"] },
    { "line": "7032", "label": "Exempt part of salary (gross - taxable)", "amount": "200000", "certificates": ["Salary certificate uploaded 2026-11-03 10:15:02 UTC"], "provisional": true },
    { "line": "7033", "label": "Bank profit", "amount": "50000", "certificates": ["Bank profit certificate uploaded 2026-11-03 10:20:41 UTC"], "provisional": true },
    { "line": null, "label": "Tax deducted and withheld at source (outflow)", "amount": "85000", "certificates": ["Salary certificate uploaded 2026-11-03 10:15:02 UTC", "Bank profit certificate uploaded 2026-11-03 10:20:41 UTC"], "provisional": true }
  ],
  "certificates_changed": false,
  "result": {
    "not_ready_reason": null,
    "net_assets": "2565000", "increase": "465000",
    "inflows": "2050000", "outflows": "1585000", "unreconciled": "0",
    "direction": "reconciled", "message": "Your wealth statement reconciles.",
    "where_to_look": [],
    "steps": [
      { "description": "Net assets this year: Rs 2,765,000 − Rs 200,000 = Rs 2,565,000", "form_line": "703001", "result": "2565000" }
    ],
    "summary": null
  },
  "label": "Not yet reviewed by a tax practitioner. Not tax advice."
}
```

A certificate is named by its type and upload time (amended 2026-11-10): 003 never stores original file names (its research R4), and the Documents page shows the same two facts. `line` is the TY2026 form code, or `null` when the form has no separate code: the tax line is
part of outflows (7099, the total) without a sub-code of its own (provisional rule 1).

**Not ready:** `result` has `not_ready_reason` (`needs_previous_net_assets`,
`no_confirmed_salary_certificate`, `profit_over_limit`, `gross_below_taxable`), a `message`
(naming the certificate for `gross_below_taxable`), and all figures null.

**Not reconciled:** `direction` is `inflows_exceed_growth` or `growth_exceeds_inflows`;
`message` states the absolute amount in words; `where_to_look` is the fixed list for that
direction and never contains an amount.

## PUT /api/wealth/{tax_year}

Body: the `statement` object above without `saved_at`. Replaces the whole statement (rows
included), records `saved_at` and the confirmed certificate ids, and returns the same body as
GET.

## Errors

`401` not logged in; `404` unknown tax year; `422` validation (negative amount other than
`previous_net_assets`, non-whole rupees, unknown category, empty or over-long description).
