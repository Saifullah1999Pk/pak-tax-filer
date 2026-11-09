import { expect, test } from "vitest";
import { balanceWords, rupees } from "./tax";

// Display only: digit grouping on the string, never a float (Principle I).

test.each([
  ["0", "Rs 0"],
  ["999", "Rs 999"],
  ["1000", "Rs 1,000"],
  ["1234567.50", "Rs 1,234,567.50"],
  ["-1234567.5", "Rs 1,234,567.5"],
  ["12345678901234567890", "Rs 12,345,678,901,234,567,890"],
])("rupees(%s) is %s", (amount, shown) => {
  expect(rupees(amount)).toBe(shown);
});

test.each([
  ["12000", "Rs 12,000 payable"],
  ["-4000", "Rs 4,000 over-withheld"],
  ["0", "Nothing to pay"],
  ["0.00", "Nothing to pay"],
])("balanceWords(%s) is %s", (balance, words) => {
  expect(balanceWords(balance, "over-withheld")).toBe(words);
});
