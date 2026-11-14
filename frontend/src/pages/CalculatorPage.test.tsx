import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { CalculatorResult } from "../api/calculator";
import { hasProfile, mockFetch } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// The simple tax calculator (feature 010, tasks T014, T017, T020), per
// specs/010-income-tax-engine/contracts/calculator-api.md. Figures are shown as the API gives
// them; the page does no tax maths (Principle I).

const ME = { status: 200, body: { email: "demo@example.com" } };
const LABEL = "Not yet reviewed by a tax practitioner. Not tax advice.";
const NOT_COVERED = [
  "Tax already deducted, and whether you owe more or get a refund",
];

// The lead's example (research R1): salary 250,000 and rent 140,000 a month.
const LEAD: CalculatorResult = {
  tax_year: "2025-26",
  blocked_reason: null,
  message: null,
  incomes: [
    {
      source: "salary",
      yearly_amount: "3000000",
      taxable_amount: "3000000",
      treatment: "slab",
    },
    {
      source: "rent",
      yearly_amount: "1680000",
      taxable_amount: "1344000",
      treatment: "slab",
    },
  ],
  taxable_income: "4344000",
  salary_share: "69.06",
  table: "non_salaried",
  slab_tax: "1107600",
  surcharge: "0",
  dividend_tax: "0",
  profit_tax: "0",
  total_tax: "1107600",
  effective_rate: "23.7",
  monthly: { salary_tax: "25000", take_home: "225000" },
  bonus_impact: null,
  filer_comparison: [],
  steps: [
    {
      description:
        "Property income: rent Rs 1,680,000 less the repairs allowance of one-fifth, Rs 336,000 = Rs 1,344,000",
      rule_location:
        "Income Tax Ordinance, 2001 (amended up to 31.07.2025), Section 15A(1)(a) (p. 57, PDF p. 76); effective 2025-07-01",
      result: "1344000",
    },
  ],
  not_covered: NOT_COVERED,
  label: LABEL,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Open the calculator with the backend answering `reply`; returns what was posted. */
function openCalculator(reply: Partial<CalculatorResult>) {
  const posted: unknown[] = [];
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "POST /api/tax/calculator": ({ body }) => {
      posted.push(body);
      return { status: 200, body: { ...LEAD, ...reply } };
    },
  });
  renderApp("/calculator");
  return posted;
}

async function type(label: RegExp, value: string) {
  fireEvent.change(await screen.findByLabelText(label), {
    target: { value },
  });
}

async function calculate() {
  fireEvent.click(await screen.findByRole("button", { name: /calculate/i }));
  return screen.findByRole("heading", { name: /your tax/i });
}

test("asks for the five amounts, and nothing about tax year or ATL status", async () => {
  openCalculator({});

  for (const label of [
    /salary per month/i,
    /bonus for the year/i,
    /rent per month/i,
    /dividends for the year/i,
    /bank profit for the year/i,
  ]) {
    expect(await screen.findByLabelText(label)).toBeTruthy();
  }
  expect(screen.queryByLabelText(/tax year/i)).toBeNull();
  expect(screen.queryByLabelText(/atl|filer/i)).toBeNull();
});

test("posts only the amounts typed, and shows the result as given", async () => {
  const posted = openCalculator({});
  await type(/salary per month/i, "250000");
  await type(/rent per month/i, "140000");

  await calculate();

  expect(posted).toEqual([
    { salary_monthly: "250000", rent_monthly: "140000" },
  ]);
  expect(screen.getAllByText("Rs 1,107,600").length).toBeGreaterThan(0);
  expect(screen.getByText(/23\.7%/)).toBeTruthy();
  expect(screen.getByText(/non-salaried table/i)).toBeTruthy();
  expect(screen.getByText(/69\.06%/)).toBeTruthy();
  expect(screen.getByText("Rs 4,344,000")).toBeTruthy();
  expect(screen.getByText("Rs 1,344,000")).toBeTruthy();
  expect(screen.getByText(LABEL)).toBeTruthy();
});

test("shows the monthly deduction and take-home, saying the rest is settled with the return", async () => {
  openCalculator({});
  await type(/salary per month/i, "250000");

  await calculate();

  const monthly = screen.getByRole("region", { name: /each month/i });
  expect(within(monthly).getByText("Rs 25,000")).toBeTruthy();
  expect(within(monthly).getByText("Rs 225,000")).toBeTruthy();
  expect(within(monthly).getByText(/settled with your return/i)).toBeTruthy();
});

test("shows what the bonus adds", async () => {
  openCalculator({ bonus_impact: "86000" });
  await type(/salary per month/i, "200000");
  await type(/bonus for the year/i, "1300000");

  await calculate();

  expect(screen.getByText(/your bonus adds/i).textContent).toContain(
    "Rs 86,000",
  );
});

test("shows dividend tax and the filer comparison as deductions, never a refund", async () => {
  openCalculator({
    dividend_tax: "150000",
    filer_comparison: [
      {
        source: "dividends",
        your_rate: "15",
        other_rate: "30",
        your_deduction: "150000",
        other_deduction: "300000",
        difference: "150000",
      },
    ],
  });
  await type(/dividends for the year/i, "1000000");

  await calculate();

  const comparison = screen.getByRole("region", { name: /filer/i });
  expect(within(comparison).getByText(/Rs 150,000/)).toBeTruthy();
  expect(within(comparison).getByText(/Rs 300,000/)).toBeTruthy();
  expect(within(comparison).getByText(/tax itself is the same/i)).toBeTruthy();
  expect(comparison.textContent).not.toMatch(/refund/i);
});

test("lists every step with its source, and what isn't covered", async () => {
  openCalculator({});
  await type(/salary per month/i, "250000");

  await calculate();

  const steps = screen.getByRole("list", { name: /how it was worked out/i });
  expect(within(steps).getByText(/repairs allowance/i)).toBeTruthy();
  expect(within(steps).getByText(/effective 2025-07-01/)).toBeTruthy();
  const notCovered = screen.getByRole("region", { name: /not covered/i });
  expect(within(notCovered).getByText(NOT_COVERED[0])).toBeTruthy();
});

test("a refusal shows its message and no figures", async () => {
  openCalculator({
    blocked_reason: "no_income",
    message: "Enter at least one income above zero.",
    incomes: [],
    taxable_income: null,
    salary_share: null,
    table: null,
    slab_tax: null,
    surcharge: null,
    dividend_tax: null,
    profit_tax: null,
    total_tax: null,
    effective_rate: null,
    monthly: null,
    steps: [],
  });

  await calculate();

  expect(
    screen.getByText("Enter at least one income above zero."),
  ).toBeTruthy();
  expect(screen.queryByText(/Rs 1,107,600/)).toBeNull();
  expect(screen.getByText(LABEL)).toBeTruthy();
});
