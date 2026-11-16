import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, test } from "vitest";
import { MoneyInput } from "./MoneyInput";
import type { AmountRule } from "./amountRule";

// MoneyInput applies the one amount rule as the user types (lead, 2026-11-16).

const PAISA: AmountRule = { decimals: 2, allowNegative: false, maxDigits: 13 };

/** A labelled box holding its own value, as the pages do. */
function Box({
  rule,
  describedBy,
}: {
  rule?: AmountRule;
  describedBy?: string;
}) {
  const [value, setValue] = useState("");
  return (
    <label>
      Amount
      <MoneyInput
        rule={rule}
        aria-describedby={describedBy}
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
    </label>
  );
}

function type(text: string) {
  fireEvent.change(screen.getByLabelText(/^Amount/), {
    target: { value: text },
  });
}

test("letters, Rs and commas never reach the box", () => {
  render(<Box rule={PAISA} />);

  type("Rs 2,50abc,000");

  expect((screen.getByLabelText(/^Amount/) as HTMLInputElement).value).toBe(
    "250000",
  );
  expect(screen.queryByRole("alert")).toBeNull();
});

test("an amount the rule refuses is marked and explained next to the box", () => {
  render(<Box rule={PAISA} describedBy="page-hint" />);

  type("100.505");

  const box = screen.getByLabelText(/^Amount/);
  const error = screen.getByRole("alert");
  expect(error.textContent).toBe("At most 2 decimal places.");
  expect(box.getAttribute("aria-invalid")).toBe("true");
  expect(box.getAttribute("aria-describedby")?.split(" ")).toEqual([
    "page-hint",
    error.id,
  ]);
});

test("whole rupees is the default rule", () => {
  render(<Box />);

  type("100.50");

  expect(screen.getByRole("alert").textContent).toBe("Whole rupees only.");
});
