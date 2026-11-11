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
  // The loaded page names the document type; the loading state is just "Check the figures".
  await screen.findByRole("heading", {
    level: 1,
    name: /check the figures: /i,
  });
}

test("a PDF is shown beside the fields", async () => {
  mockFetch(routes(DOCUMENT));
  await openReview();

  // <object> has no ARIA role, so its title is the way a user's tools find it.
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

test("editing a field and confirming it sends the new value, then shows what was saved", async () => {
  let sent: unknown = null;
  let current = DOCUMENT;
  mockFetch(
    routes(DOCUMENT, {
      "GET /api/documents/d1": () => ({ status: 200, body: current }),
      "PATCH /api/documents/d1/fields/gross_salary": ({ body }) => {
        sent = body;
        const saved = field("gross_salary", "1900000.00", {
          user_edited: true,
          confirmed: true,
        });
        current = {
          ...DOCUMENT,
          fields: DOCUMENT.fields.map((f) =>
            f.name === "gross_salary" ? saved : f,
          ),
        };
        return { status: 200, body: saved };
      },
    }),
  );
  await openReview();

  const gross = screen.getByRole("group", { name: /gross salary/i });
  fireEvent.change(within(gross).getByRole("textbox"), {
    target: { value: "1,900,000" },
  });
  fireEvent.click(within(gross).getByRole("button", { name: /confirm/i }));

  // The reload re-creates the row, so look it up again once it shows the saved state.
  await vi.waitFor(() =>
    within(screen.getByRole("group", { name: /gross salary/i })).getByText(
      /^confirmed\.$/i,
    ),
  );
  const saved = screen.getByRole("group", { name: /gross salary/i });
  within(saved).getByText(/you entered this/i);
  expect(within(saved).getByRole("textbox") as HTMLInputElement).toHaveProperty(
    "value",
    "1900000.00",
  );
  expect(sent).toEqual({ value: "1,900,000", confirmed: true });
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
    expect(box as HTMLInputElement).toHaveProperty("disabled", true);
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
    screen
      .getByRole("link", { name: /back to documents/i })
      .getAttribute("href"),
  ).toBe("/documents");
});

// Frontend review findings (2026-11-05).

test("every field shows its confidence, not only low ones", async () => {
  mockFetch(
    routes({
      ...DOCUMENT,
      fields: [
        field("tax_year", "2025-26"),
        field("gross_salary", "1800000.00", { confidence: "medium" }),
      ],
    }),
  );
  await openReview();

  within(screen.getByRole("group", { name: /tax year/i })).getByText(
    /confidence: high/i,
  );
  within(screen.getByRole("group", { name: /gross salary/i })).getByText(
    /confidence: medium/i,
  );
});

test("an unsaved change stops the document being confirmed", async () => {
  const fetch = mockFetch(routes(DOCUMENT));
  await openReview();

  const gross = screen.getByRole("group", { name: /gross salary/i });
  fireEvent.change(within(gross).getByRole("textbox"), {
    target: { value: "1,900,000" },
  });
  fireEvent.click(screen.getByRole("button", { name: /confirm document/i }));

  expect((await screen.findByRole("alert")).textContent).toMatch(
    /gross salary/i,
  );
  expect(
    fetch.mock.calls.some(([path]) => String(path).endsWith("/confirm")),
  ).toBe(false);
});

test("confirming the document makes it read-only", async () => {
  const confirmedDocument = {
    ...DOCUMENT,
    status: "confirmed",
    confirmed_at: "2026-11-05T11:00:00Z",
    fields: DOCUMENT.fields.map((f) => ({
      ...f,
      value: f.value ?? "0.00",
      confirmed: true,
    })),
  };
  mockFetch(
    routes(DOCUMENT, {
      "POST /api/documents/d1/confirm": () => ({
        status: 200,
        body: confirmedDocument,
      }),
    }),
  );
  await openReview();

  fireEvent.click(screen.getByRole("button", { name: /confirm document/i }));

  await screen.findByText(/this document is confirmed/i);
  for (const box of screen.getAllByRole("textbox")) {
    expect(box as HTMLInputElement).toHaveProperty("disabled", true);
  }
});

test("each input is described by where it was found and its confidence", async () => {
  mockFetch(routes(DOCUMENT));
  await openReview();

  const input = within(
    screen.getByRole("group", { name: /gross salary/i }),
  ).getByRole("textbox");
  const described = (input.getAttribute("aria-describedby") ?? "")
    .split(" ")
    .map((id) => document.getElementById(id)?.textContent ?? "")
    .join(" ");
  expect(described).toMatch(/page 1/i);
  expect(described).toMatch(/tax deducted is more than gross salary/i);
});

test("a not-found field shows no confidence, only that it wasn't found (task T043)", async () => {
  mockFetch(routes(DOCUMENT));
  await openReview();

  const deducted = screen.getByRole("group", { name: /tax deducted/i });
  within(deducted).getByText(/not found on the document/i);
  expect(within(deducted).queryByText(/confidence/i)).toBeNull();
  const gross = screen.getByRole("group", { name: /gross salary/i });
  within(gross).getByText(/low confidence/i);
});

// Feature 001, User Story 6 (frontend review M5): on a narrow screen the original starts folded
// away, so the figures aren't pushed far down; on a wide one it is open beside them.

function screenIsWide(wide: boolean) {
  vi.stubGlobal(
    "matchMedia",
    (query: string) => ({ matches: wide, media: query }) as MediaQueryList,
  );
}

const originalPanel = () =>
  screen.getByText("Original document", { selector: "summary" })
    .parentElement as HTMLDetailsElement;

test("on a phone the original document starts folded away, the figures still shown", async () => {
  screenIsWide(false);
  mockFetch(routes(DOCUMENT));
  await openReview();

  expect(originalPanel().open).toBe(false);
  screen.getByRole("button", { name: /confirm document/i });
});

test("on a wide screen the original document starts open", async () => {
  screenIsWide(true);
  mockFetch(routes(DOCUMENT));
  await openReview();

  expect(originalPanel().open).toBe(true);
});

// Feature 001, User Story 6, task T066: long amounts are repeated with digit grouping, so they
// are easy to check against the document (display only; the field keeps the plain value).

test("each amount is repeated with digit grouping beneath its field", async () => {
  mockFetch(routes(DOCUMENT));
  await openReview();

  screen.getByText("Rs 1,800,000.00");
  screen.getByText("Rs 1,700,000.00");
  expect(screen.getByLabelText("Gross salary")).toHaveProperty(
    "value",
    "1800000.00",
  );
  // The tax year is not an amount.
  expect(screen.queryByText(/Rs 2025/)).toBeNull();
});
