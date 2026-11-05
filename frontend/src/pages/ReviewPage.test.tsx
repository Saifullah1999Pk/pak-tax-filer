import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { hasProfile, mockFetch } from "../test/mockFetch";
import type { FakeRoutes } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// Review, correct and confirm, per specs/003-document-extraction/contracts/documents-api.md
// (task T019; spec User Story 2, constitution Principle III).

const ME = { status: 200, body: { email: "demo@example.com" } };

type Field = {
  name: string;
  value: string | null;
  confidence: string;
  source_page: number | null;
  source_label: string | null;
  rule_reason: string | null;
  user_edited: boolean;
  confirmed: boolean;
};

function field(
  name: string,
  value: string | null,
  extra: Partial<Field> = {},
): Field {
  return {
    name,
    value,
    confidence: "high",
    source_page: value === null ? null : 1,
    source_label: value === null ? null : "Label",
    rule_reason: null,
    user_edited: false,
    confirmed: false,
    ...extra,
  };
}

const DOCUMENT = {
  id: "d1",
  doc_type: "salary_certificate",
  tax_year: "2025-26",
  status: "needs_review",
  failure_reason: null,
  media_type: "application/pdf",
  page_count: 1,
  created_at: "2026-11-05T10:00:00Z",
  confirmed_at: null,
  fields: [
    field("tax_year", "2025-26"),
    field("gross_salary", "1800000.00", {
      confidence: "low",
      rule_reason: "Tax deducted is more than gross salary.",
      source_label: "Gross Salary",
    }),
    field("taxable_salary", "1700000.00"),
    field("tax_deducted", null),
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function routes(document: unknown, extra: FakeRoutes = {}): FakeRoutes {
  return {
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/documents/d1": () => ({ status: 200, body: document }),
    ...extra,
  };
}

async function openReview() {
  renderApp("/documents/d1");
  await screen.findByRole("heading", { level: 1, name: /check the figures/i });
}

test("a PDF is shown beside the fields", async () => {
  mockFetch(routes(DOCUMENT));
  await openReview();

  const viewer = screen.getByTitle(/original document/i);
  expect(viewer.tagName).toBe("OBJECT");
  expect(viewer.getAttribute("data")).toBe("/api/documents/d1/file");
});

test("a photo is shown as an image", async () => {
  mockFetch(routes({ ...DOCUMENT, media_type: "image/jpeg" }));
  await openReview();

  expect(
    screen.getByRole("img", { name: /original document/i }).getAttribute("src"),
  ).toBe("/api/documents/d1/file");
});

test("each field shows its value, where it was found, and low confidence with the reason", async () => {
  mockFetch(routes(DOCUMENT));
  await openReview();

  const gross = screen.getByRole("group", { name: /gross salary/i });
  expect(within(gross).getByRole("textbox") as HTMLInputElement).toHaveProperty(
    "value",
    "1800000.00",
  );
  within(gross).getByText(/page 1/i);
  within(gross).getByText(/low confidence/i);
  within(gross).getByText(/tax deducted is more than gross salary/i);
  const deducted = screen.getByRole("group", { name: /tax deducted/i });
  within(deducted).getByText(/not found/i);
});

test("editing a field and confirming it sends the new value", async () => {
  let sent: unknown = null;
  mockFetch(
    routes(DOCUMENT, {
      "PATCH /api/documents/d1/fields/gross_salary": ({ body }) => {
        sent = body;
        return { status: 200, body: field("gross_salary", "1900000.00") };
      },
    }),
  );
  await openReview();

  const gross = screen.getByRole("group", { name: /gross salary/i });
  fireEvent.change(within(gross).getByRole("textbox"), {
    target: { value: "1,900,000" },
  });
  fireEvent.click(within(gross).getByRole("button", { name: /confirm/i }));

  await vi.waitFor(() =>
    expect(sent).toEqual({ value: "1,900,000", confirmed: true }),
  );
});

test("confirming an unchanged field sends only the confirmation", async () => {
  let sent: unknown = null;
  mockFetch(
    routes(DOCUMENT, {
      "PATCH /api/documents/d1/fields/tax_year": ({ body }) => {
        sent = body;
        return {
          status: 200,
          body: field("tax_year", "2025-26", { confirmed: true }),
        };
      },
    }),
  );
  await openReview();

  const year = screen.getByRole("group", { name: /tax year/i });
  fireEvent.click(within(year).getByRole("button", { name: /confirm/i }));

  await vi.waitFor(() => expect(sent).toEqual({ confirmed: true }));
});

test("a refused edit shows the server's message in that field", async () => {
  mockFetch(
    routes(DOCUMENT, {
      "PATCH /api/documents/d1/fields/gross_salary": () => ({
        status: 422,
        body: { detail: "Enter an amount in rupees, e.g. 1,800,000." },
      }),
    }),
  );
  await openReview();

  const gross = screen.getByRole("group", { name: /gross salary/i });
  fireEvent.change(within(gross).getByRole("textbox"), {
    target: { value: "abc" },
  });
  fireEvent.click(within(gross).getByRole("button", { name: /confirm/i }));

  expect((await within(gross).findByRole("alert")).textContent).toMatch(
    /enter an amount in rupees/i,
  );
});

test("confirming the document is blocked with the list of missing fields", async () => {
  const detail =
    "Confirm or fill in these fields first: gross_salary, tax_deducted.";
  mockFetch(
    routes(DOCUMENT, {
      "POST /api/documents/d1/confirm": () => ({
        status: 409,
        body: { detail },
      }),
    }),
  );
  await openReview();

  fireEvent.click(screen.getByRole("button", { name: /confirm document/i }));

  expect((await screen.findByRole("alert")).textContent).toContain(detail);
});

test("a confirmed document is read-only", async () => {
  mockFetch(
    routes({
      ...DOCUMENT,
      status: "confirmed",
      confirmed_at: "2026-11-05T11:00:00Z",
      fields: DOCUMENT.fields.map((f) => ({
        ...f,
        value: f.value ?? "0.00",
        confirmed: true,
      })),
    }),
  );
  await openReview();

  screen.getByText(/this document is confirmed/i);
  for (const box of screen.getAllByRole("textbox")) {
    expect(box as HTMLButtonElement | HTMLInputElement).toHaveProperty(
      "disabled",
      true,
    );
  }
  expect(screen.queryByRole("button", { name: /confirm/i })).toBeNull();
});

test("a failed document shows why and links back to the list", async () => {
  mockFetch(
    routes({
      ...DOCUMENT,
      status: "failed",
      failure_reason: "The AI declined to read this document.",
      fields: [],
    }),
  );
  await openReview();

  screen.getByText(/the ai declined to read this document/i);
  expect(
    screen.getByRole("link", { name: /documents/i }).getAttribute("href"),
  ).toBe("/documents");
});
