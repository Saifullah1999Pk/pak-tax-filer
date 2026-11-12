import { act, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { Run } from "../api/workflow";
import { hasProfile, mockFetch, noProfile } from "../test/mockFetch";
import type { FakeReply } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// The guided run, per specs/007-agentic-workflow/contracts/workflow-api.md (task T011). The
// page shows what the backend decided and checked; it computes nothing (Principle I).

const ME = { status: 200, body: { email: "demo@example.com" } };

const AT_GATE: Run = {
  step: "gate",
  tax_year: "2025-26",
  fingerprint: "f".repeat(64),
  document: {
    message: "Your salary certificate is confirmed.",
    missing: [],
    fallback: false,
  },
  validation: {
    message: "Your salary certificate shows taxable salary above gross salary.",
    issues: [
      {
        document_id: "doc-1",
        certificate: "Salary certificate uploaded 05 Nov 2026",
        field: "taxable_salary",
        reason: "Taxable salary is more than gross salary.",
      },
    ],
    fallback: false,
  },
  research: {
    note: "Your employer deducts tax from your salary.",
    passages: [
      {
        id: "p-1",
        source: "Income Tax Ordinance, 2001",
        kind: "law",
        location: "§149(1)",
        page: 327,
        text: "Every employer paying salary shall deduct tax.",
      },
    ],
    fallback: true,
  },
  gate: {
    figures: {
      taxable_salary: "1800000.00",
      tax_deducted: "75000.00",
      gross_profit: "0.00",
      tax_withheld: "0.00",
    },
    on_atl: true,
  },
  approved_at: null,
  done_at: null,
};

const MISSING: Run = {
  ...AT_GATE,
  step: "document",
  document: {
    message: "You need a confirmed salary certificate.",
    missing: ["salary_certificate"],
    fallback: true,
  },
  validation: null,
  research: null,
  gate: null,
};

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** The app at /workflow: GET answers `current` (or 404), POST /start answers `started`. */
function showWorkflow(current: Run | null, started: Run | "pending" = AT_GATE) {
  return mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/workflow": () =>
      current === null
        ? { status: 404, body: { detail: "No guided run yet." } }
        : { status: 200, body: current },
    "POST /api/workflow/start": () =>
      started === "pending"
        ? new Promise<FakeReply>(() => {})
        : { status: 200, body: started },
  });
}

test("before a run, the page explains it and offers to start", async () => {
  const fetch = showWorkflow(null);
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Start" }));

  expect(await screen.findByText("Rs 1,800,000.00")).toBeDefined();
  expect(fetch).toHaveBeenCalledWith(
    "/api/workflow/start",
    expect.objectContaining({ method: "POST" }),
  );
});

test("while the steps run, it shows what each is doing in turn", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  showWorkflow(null, "pending");
  renderApp("/workflow");

  fireEvent.click(await screen.findByRole("button", { name: "Start" }));

  const status = screen.getByRole("status");
  expect(status.textContent).toBe("Checking your documents…");
  act(() => {
    vi.advanceTimersByTime(2000);
  });
  expect(status.textContent).toBe("Checking the figures…");
  act(() => {
    vi.advanceTimersByTime(2000);
  });
  expect(status.textContent).toBe("Finding the law that applies…");
});

test("the step indicator marks where the run is", async () => {
  showWorkflow(AT_GATE);
  renderApp("/workflow");

  const steps = await screen.findByRole("list", { name: "Steps" });
  const current = within(steps).getByText("Approve");
  expect(current.closest("li")?.getAttribute("aria-current")).toBe("step");
});

test("a missing salary certificate is explained, with the way to fix it", async () => {
  showWorkflow(MISSING);
  renderApp("/workflow");

  expect(
    await screen.findByText("You need a confirmed salary certificate."),
  ).toBeDefined();
  expect(
    screen.getByRole("link", { name: "Go to documents" }).getAttribute("href"),
  ).toBe("/documents");
  expect(
    screen.queryByRole("heading", { name: "Before you approve" }),
  ).toBeNull();
});

test("the gate shows the figures, the profile, the issues and the cited law", async () => {
  showWorkflow(AT_GATE);
  renderApp("/workflow");

  const gate = await screen.findByRole("region", {
    name: "Before you approve",
  });
  within(gate).getByText("Rs 1,800,000.00");
  within(gate).getByText("Rs 75,000.00");
  within(gate).getByText("2025-26");
  within(gate).getByText("Yes");
  within(gate).getByText(
    "Salary certificate uploaded 05 Nov 2026: Taxable salary is more than gross salary.",
  );
  const passages = within(gate).getByRole("list", {
    name: "Where this comes from",
  });
  expect(passages.textContent).toContain(
    "Income Tax Ordinance, 2001, §149(1), page 327",
  );
});

test("text the app wrote without the AI is marked as such", async () => {
  showWorkflow(AT_GATE);
  renderApp("/workflow");

  await screen.findByRole("region", { name: "Before you approve" });
  // Only the research step used its plain result in AT_GATE.
  expect(
    screen.getAllByText("Written by the app (the AI wasn't used)"),
  ).toHaveLength(1);
});

test("without a profile, the run sends the user to set one up first", async () => {
  mockFetch({ "GET /api/auth/me": () => ME, "GET /api/profile": noProfile });
  renderApp("/workflow", { showLocation: true });

  expect(
    await screen.findByText("Location: /profile?next=%2Fworkflow"),
  ).toBeDefined();
});
