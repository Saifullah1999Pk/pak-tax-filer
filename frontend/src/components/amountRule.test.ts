import { expect, test } from "vitest";
import { amountError, cleanAmount } from "./amountRule";
import type { AmountRule } from "./amountRule";

// The one rule for every amount box (the lead, 2026-11-16: "make 1 rule in React and apply
// where[ever]"). Each page passes what its own backend accepts; the server still checks.

const RUPEES: AmountRule = { decimals: 0, allowNegative: false, maxDigits: 14 };
const PAISA: AmountRule = { decimals: 2, allowNegative: false, maxDigits: 13 };
const SIGNED: AmountRule = { decimals: 0, allowNegative: true, maxDigits: 14 };

// Cleaning is the same for every rule: whether a minus or a point is allowed is amountError's
// call, so a value is never quietly changed (-500 into 500, 100.50 into 10050).
test.each([
  ["250000", "250000"],
  ["25abc0x00", "25000"],
  ["Rs 1,250,000", "1250000"],
  ["1.5.5", "1.55"],
  ["100.50", "100.50"],
  ["-500", "-500"],
  ["5-00", "500"],
  ["--5", "-5"],
  ["", ""],
])(
  "cleanAmount(%j) keeps only digits, a leading minus and the first point: %j",
  (raw, cleaned) => {
    expect(cleanAmount(raw)).toBe(cleaned);
  },
);

test.each([
  ["", PAISA, null],
  ["250000", PAISA, null],
  ["250000.5", PAISA, null],
  ["9999999999999.99", PAISA, null],
  ["12345678901234", PAISA, "At most 13 digits before the decimal point."],
  ["100.505", PAISA, "At most 2 decimal places."],
  ["12345678901234", RUPEES, null],
  ["123456789012345", RUPEES, "At most 14 digits."],
  [".", PAISA, "Enter an amount, e.g. 250000."],
  ["-", SIGNED, "Enter an amount, e.g. 250000."],
  ["-500", SIGNED, null],
  ["100.50", RUPEES, "Whole rupees only."],
  ["-500", PAISA, "Can't be negative."],
])("amountError(%j) is %j", (value, rule, error) => {
  expect(amountError(value, rule)).toBe(error);
});
