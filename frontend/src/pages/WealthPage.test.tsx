import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { Wealth } from "../api/wealth";
import { hasProfile, mockFetch } from "../test/mockFetch";
import type { FakeReply } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// The wealth statement page, per specs/005-wealth-statement/contracts/wealth-api.md (tasks
// T011, T017, T023). Figures and results come from the backend; the page does no maths.

const ME = { status: 200, body: { email: "demo@example.com" } };
const LABEL = "Not yet reviewed by a tax practitioner. Not tax advice.";
const SALARY_CERT = "Salary certificate uploaded 2026-11-09 14:05:02 UTC";

const SAVED: Wealth = {
  tax_year: "2025-26",
  statement: {
    previous_net_assets: "2100000",
    assets: [
      {
        category: "bank_account",
        description: "Savings account",
        amount: "1350000",
      },
    ],
    liabilities: [
      { description: "Car loan", creditor: "Bank", amount: "200000" },
    ],
    other_exempt_income: "0",
    foreign_remittance: "0",
    inheritance: "0",
    gifts_received: "0",
    family_contribution: "0",
    gifts_given: "0",
    expenses: { rent: "600000" },
    saved_at: "2026-11-10T10:00:00Z",
  },
  auto_filled: [
    {
      line: "7031",
      label: "Taxable salary",
      amount: "1800000",
      certificates: [SALARY_CERT],
      provisional: false,
    },
    {
      line: null,
      label: "Tax deducted and withheld at source (outflow)",
      amount: "82000",
      certificates: [SALARY_CERT],
      provisional: true,
    },
  ],
  certificates_changed: false,
  result: {
    not_ready_reason: null,
    message: "Your wealth statement reconciles.",
    net_assets: "1150000",
    increase: "-950000",
    inflows: "1800000",
    outflows: "2750000",
    unreconciled: "0",
    direction: "reconciled",
    where_to_look: [],
    steps: [
      {
        description:
          "Net assets this year: Rs 1,350,000 - Rs 200,000 = Rs 1,150,000",
        form_line: "703001",
        result: "1150000",
      },
      {
        description:
          "Unreconciled amount: Rs 1,800,000 - Rs 2,750,000 - (-Rs 950,000) = Rs 0",
        form_line: "703000",
        result: "0",
      },
    ],
    summary: null,
  },
  label: LABEL,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function serve(
  wealth: Partial<Wealth> = {},
  onSave?: (body: unknown) => FakeReply | Promise<FakeReply>,
) {
  const reply = (): FakeReply => ({
    status: 200,
    body: { ...SAVED, ...wealth },
  });
  return mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/wealth/2025-26": reply,
    "PUT /api/wealth/2025-26": ({ body }) => (onSave ? onSave(body) : reply()),
  });
}

async function open() {
  renderApp("/wealth");
  await screen.findByRole("heading", { name: /wealth statement for 2025-26/i });
  await screen.findByText(LABEL); // the statement has loaded
}

test("opens on the profile's tax year with three sections and the label", async () => {
  serve();
  await open();

  screen.getByRole("region", { name: /what i own/i });
  screen.getByRole("region", { name: /what i owe/i });
  screen.getByRole("region", { name: /money in and out/i });
  screen.getByText(LABEL);
});

test("the saved rows and amounts are filled in", async () => {
  serve();
  await open();

  const own = screen.getByRole("region", { name: /what i own/i });
  expect(within(own).getByLabelText(/description/i)).toHaveProperty(
    "value",
    "Savings account",
  );
  expect(within(own).getByLabelText(/amount/i)).toHaveProperty(
    "value",
    "1350000",
  );
  expect(screen.getByLabelText(/net assets on 30 june 2025/i)).toHaveProperty(
    "value",
    "2100000",
  );
  expect(screen.getByLabelText(/^rent$/i)).toHaveProperty("value", "600000");
});

test("adding, editing and removing rows is what gets saved", async () => {
  let saved: Record<string, unknown> | undefined;
  serve({}, (body) => {
    saved = body as Record<string, unknown>;
    return { status: 200, body: SAVED };
  });
  await open();

  const own = screen.getByRole("region", { name: /what i own/i });
  fireEvent.click(within(own).getByRole("button", { name: /add an asset/i }));
  const second = within(own).getByRole("group", { name: "Asset 2" });
  expect(within(second).getByLabelText(/category/i)).toHaveProperty(
    "value",
    "bank_account",
  );
  fireEvent.change(within(second).getByLabelText(/category/i), {
    target: { value: "motor_vehicle" },
  });
  fireEvent.change(within(second).getByLabelText(/description/i), {
    target: { value: "Car" },
  });
  fireEvent.change(within(second).getByLabelText(/amount/i), {
    target: { value: "1400000" },
  });
  const owe = screen.getByRole("region", { name: /what i owe/i });
  fireEvent.click(
    within(owe).getByRole("button", { name: "Remove liability 1" }),
  );
  expect(document.activeElement).toBe(
    within(owe).getByRole("button", { name: /add a liability/i }),
  );
  fireEvent.click(
    within(owe).getByRole("button", { name: /add a liability/i }),
  );
  const loan = within(owe).getByRole("group", { name: "Liability 1" });
  fireEvent.change(within(loan).getByLabelText(/description/i), {
    target: { value: "Loan from a friend" },
  });
  fireEvent.change(within(loan).getByLabelText(/amount/i), {
    target: { value: "5000" },
  });
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  await waitFor(() => expect(saved).toBeDefined());
  expect(saved?.assets).toEqual([
    {
      category: "bank_account",
      description: "Savings account",
      amount: "1350000",
    },
    { category: "motor_vehicle", description: "Car", amount: "1400000" },
  ]);
  expect(saved?.liabilities).toEqual([
    { description: "Loan from a friend", creditor: null, amount: "5000" },
  ]);
  expect(saved?.previous_net_assets).toBe("2100000");
});

test("removing an asset removes it from what is saved", async () => {
  let saved: Record<string, unknown> | undefined;
  serve({}, (body) => {
    saved = body as Record<string, unknown>;
    return { status: 200, body: SAVED };
  });
  await open();

  const own = screen.getByRole("region", { name: /what i own/i });
  fireEvent.click(within(own).getByRole("button", { name: "Remove asset 1" }));
  expect(document.activeElement).toBe(
    within(own).getByRole("button", { name: /add an asset/i }),
  );
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  await waitFor(() => expect(saved).toBeDefined());
  expect(saved?.assets).toEqual([]);
});

test("descriptions are required and sent trimmed", async () => {
  let saved: Record<string, unknown> | undefined;
  serve({}, (body) => {
    saved = body as Record<string, unknown>;
    return { status: 200, body: SAVED };
  });
  await open();

  const asset = screen.getByRole("group", { name: "Asset 1" });
  const description = within(asset).getByLabelText(/description/i);
  expect(description).toHaveProperty("required", true);
  const liability = screen.getByRole("group", { name: "Liability 1" });
  expect(within(liability).getByLabelText(/description/i)).toHaveProperty(
    "required",
    true,
  );
  fireEvent.change(description, { target: { value: "  Savings account  " } });
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  await waitFor(() => expect(saved).toBeDefined());
  const assets = (saved?.assets ?? []) as { description: string }[];
  expect(assets[0].description).toBe("Savings account");
});

test("empty fields are sent as not entered, zero or left out, and amounts trimmed", async () => {
  let saved: Record<string, unknown> | undefined;
  serve({}, (body) => {
    saved = body as Record<string, unknown>;
    return { status: 200, body: SAVED };
  });
  await open();

  fireEvent.change(screen.getByLabelText(/net assets on 30 june 2025/i), {
    target: { value: "" },
  });
  fireEvent.change(screen.getByLabelText(/inheritance/i), {
    target: { value: "" },
  });
  fireEvent.change(screen.getByLabelText(/^rent$/i), { target: { value: "" } });
  fireEvent.change(screen.getByLabelText(/^medical$/i), {
    target: { value: " 5000 " },
  });
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  await waitFor(() => expect(saved).toBeDefined());
  expect(saved?.previous_net_assets).toBeNull();
  expect(saved?.inheritance).toBe("0");
  expect(saved?.expenses).toEqual({ medical: "5000" });
});

test("last year's net assets can be negative, so its keypad isn't digits-only", async () => {
  serve();
  await open();

  const previous = screen.getByLabelText(/net assets on 30 june 2025/i);
  expect(previous.getAttribute("inputmode")).toBeNull();
  const hint = document.getElementById(
    previous.getAttribute("aria-describedby") ?? "",
  );
  expect(hint?.textContent).toMatch(/may be negative/i);
  screen.getByText(/as on 30 june 2026/i);
});

test("the dates follow the profile's tax year", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": () => ({
      status: 200,
      body: {
        profile: {
          tax_year: "2024-25",
          on_atl: true,
          updated_at: "2026-11-05T10:00:00Z",
        },
        supported_tax_years: ["2024-25"],
      },
    }),
    "GET /api/wealth/2024-25": () => ({
      status: 200,
      body: { ...SAVED, tax_year: "2024-25" },
    }),
  });
  renderApp("/wealth");
  await screen.findByText(LABEL);

  screen.getByLabelText(/net assets on 30 june 2024/i);
  screen.getByText(/as on 30 june 2025/i);
});

test("certificate lines are read-only, name their certificate and say how to correct it", async () => {
  serve({
    auto_filled: [
      ...SAVED.auto_filled,
      {
        line: "7033",
        label: "Bank profit",
        amount: "0",
        certificates: [],
        provisional: true,
      },
    ],
  });
  await open();

  const money = screen.getByRole("region", { name: /money in and out/i });
  const fromCertificates = within(money).getByRole("list", {
    name: /from your certificates/i,
  });
  within(fromCertificates).getByText(/taxable salary \(7031\)/i);
  within(fromCertificates).getByText("Rs 1,800,000");
  expect(
    within(fromCertificates).getAllByText(new RegExp(SALARY_CERT)).length,
  ).toBeGreaterThan(0);
  within(fromCertificates).getByText("No confirmed certificate");
  expect(screen.queryByLabelText(/taxable salary/i)).toBeNull(); // nothing to type into
  within(money).getByText(/correct the certificate/i);
});

test("a save replaces the form and result with what the server saved, and says so", async () => {
  serve({}, () => ({
    status: 200,
    body: {
      ...SAVED,
      statement: {
        ...SAVED.statement,
        assets: [
          { category: "bank_account", description: "Renamed", amount: "1" },
        ],
      },
      result: { ...SAVED.result, message: "Saved and recalculated." },
    },
  }));
  await open();

  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  await screen.findByText("Saved and recalculated.");
  const own = screen.getByRole("region", { name: /what i own/i });
  expect(within(own).getByLabelText(/description/i)).toHaveProperty(
    "value",
    "Renamed",
  );
  screen.getByText("Saved.");
  // Keyboard and screen-reader users stay where they were, not at the top of the page.
  expect(document.activeElement).toBe(
    screen.getByRole("button", { name: /^save$/i }),
  );
});

test("there is one status region, so the save is announced, and the certificate notice isn't one", async () => {
  serve({ certificates_changed: true });
  await open();

  const statuses = screen.getAllByRole("status");
  expect(statuses).toHaveLength(1);
  expect(statuses[0].textContent).toBe("");
  expect(
    screen
      .getByText(/your confirmed certificates changed since you last saved/i)
      .getAttribute("role"),
  ).toBeNull();
});

test("while saving, nothing can be typed or saved twice", async () => {
  serve({}, () => new Promise<FakeReply>(() => {}));
  await open();

  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  const saving = await screen.findByRole("button", { name: /saving/i });
  expect(saving).toHaveProperty("disabled", true);
  expect(
    screen.getByLabelText(/inheritance/i).closest("fieldset"),
  ).toHaveProperty("disabled", true);
});

test("a save error is shown beside the save button", async () => {
  serve({}, () => ({
    status: 422,
    body: { detail: "inheritance: must not be negative" },
  }));
  await open();

  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("must not be negative");
  const save = screen.getByRole("button", { name: /^save$/i });
  expect(save.getAttribute("aria-describedby")).toBe(alert.id);
  expect(document.activeElement).toBe(save);
});

test("a statement that can't be loaded says so", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/wealth/2025-26": () => ({
      status: 500,
      body: { detail: "Server error." },
    }),
  });
  renderApp("/wealth");

  expect((await screen.findByRole("alert")).textContent).toMatch(
    /server error/i,
  );
});

// Task T017 (User Story 2): the result explained.

test("the breakdown shows each step with its form line", async () => {
  serve();
  await open();

  const breakdown = screen.getByRole("list", {
    name: /how it was worked out/i,
  });
  const steps = within(breakdown).getAllByRole("listitem");
  expect(steps).toHaveLength(2);
  within(steps[0]).getByText(/Net assets this year/);
  within(steps[0]).getByText(/703001/);
  screen.getByText("Your wealth statement reconciles.");
  expect(screen.queryByRole("list", { name: /where to look/i })).toBeNull();
  expect(screen.queryByRole("region", { name: /summary/i })).toBeNull();
  within(screen.getByRole("region", { name: /^result$/i })).getByText(LABEL);
});

test("a gap shows its message, where to look, and the summary when there is one", async () => {
  serve({
    result: {
      ...SAVED.result,
      unreconciled: "-50000",
      direction: "growth_exceeds_inflows",
      message:
        "Your assets grew Rs 50,000 more than your inflows explain: an inflow may be missing.",
      where_to_look: ["A gift you received", "An inheritance"],
      summary: "Your assets grew Rs 50,000 more than your inflows explain.",
    },
  });
  await open();

  screen.getByText(
    /assets grew Rs 50,000 more than your inflows explain: an inflow/,
  );
  const look = screen.getByRole("list", { name: /where to look/i });
  within(look).getByText("A gift you received");
  within(screen.getByRole("region", { name: /summary/i })).getByText(
    "Your assets grew Rs 50,000 more than your inflows explain.",
  );
});

// Task T023 (User Story 3): honest limits and staying in sync.

test("a not-ready statement shows what to do and no breakdown", async () => {
  serve({
    result: {
      ...SAVED.result,
      not_ready_reason: "needs_previous_net_assets",
      message:
        "Enter your net assets as on 30 June 2025, from last year's wealth statement.",
      net_assets: null,
      increase: null,
      inflows: null,
      outflows: null,
      unreconciled: null,
      direction: null,
      steps: [],
    },
  });
  await open();

  screen.getByText(/enter your net assets as on 30 june 2025, from last year/i);
  expect(
    screen.queryByRole("list", { name: /how it was worked out/i }),
  ).toBeNull();
  expect(screen.queryByRole("list", { name: /where to look/i })).toBeNull();
  expect(screen.queryByRole("region", { name: /summary/i })).toBeNull();
  screen.getByText(LABEL);
});

test("changed certificates since the last save are pointed out", async () => {
  serve({ certificates_changed: true });
  await open();

  screen.getByText(/your confirmed certificates changed since you last saved/i);
});

test("the home page links to the wealth statement", async () => {
  serve();
  renderApp("/");

  const link = await screen.findByRole("link", { name: /wealth statement/i });
  expect(link.getAttribute("href")).toBe("/wealth");
});
