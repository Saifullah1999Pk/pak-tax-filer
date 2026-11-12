import { expect, test } from "vitest";
import type { DocStatus, DocType, DocumentSummary } from "../api/documents";
import type { Profile } from "../profile/ProfileContext";
import { filingSteps } from "./steps";

// Home's filing checklist (feature 001, User Story 6, task T051; FR-028). Only the profile's tax
// year counts: the tax and wealth pages use that year's confirmed certificates only.

const PROFILE: Profile = {
  tax_year: "2025-26",
  on_atl: true,
  updated_at: "2026-11-05T10:00:00Z",
};

let nextId = 0;
function doc(
  doc_type: DocType,
  status: DocStatus,
  tax_year = "2025-26",
): DocumentSummary {
  nextId += 1;
  return {
    id: `doc-${nextId}`,
    doc_type,
    tax_year,
    status,
    failure_reason: null,
    media_type: "application/pdf",
    page_count: 1,
    created_at: "2026-11-05T10:00:00Z",
    confirmed_at: status === "confirmed" ? "2026-11-05T10:05:00Z" : null,
  };
}

const byKey = (docs: DocumentSummary[] | null, profile = PROFILE) =>
  Object.fromEntries(
    filingSteps(profile, docs).map((step) => [step.key, step]),
  );

test("the four steps come in order", () => {
  expect(filingSteps(PROFILE, []).map((step) => step.title)).toEqual([
    "Profile",
    "Documents",
    "Tax",
    "Wealth statement",
  ]);
});

test("the profile is done and says the year and ATL status", () => {
  const { profile } = byKey([]);
  expect(profile.state).toBe("done");
  expect(profile.detail).toBe("Tax year 2025-26, on the ATL");
  expect(profile.action).toEqual({ to: "/profile", text: "Edit profile" });
  const notOnAtl = byKey([], { ...PROFILE, on_atl: false }).profile;
  expect(notOnAtl.detail).toBe("Tax year 2025-26, not on the ATL");
});

test("with no documents, Documents is next and Tax and Wealth wait for a salary certificate", () => {
  const { documents, tax, wealth } = byKey([]);
  expect(documents.state).toBe("next");
  expect(documents.detail).toBe("None yet");
  expect(documents.action).toEqual({
    to: "/documents",
    text: "Upload documents",
  });
  for (const step of [tax, wealth]) {
    expect(step.state).toBe("todo");
    expect(step.detail).toBe("Needs a confirmed salary certificate");
  }
  expect(tax.action).toEqual({ to: "/tax", text: "See your tax" });
  expect(wealth.action).toEqual({
    to: "/wealth",
    text: "Open wealth statement",
  });
});

test("a confirmed salary certificate with nothing to review: Documents done, Tax next", () => {
  const { documents, tax, wealth } = byKey([
    doc("salary_certificate", "confirmed"),
  ]);
  expect(documents.state).toBe("done");
  expect(documents.detail).toBe("1 confirmed");
  expect(tax.state).toBe("next");
  expect(tax.detail).toBe("Ready");
  expect(wealth.state).toBe("todo");
  expect(wealth.detail).toBe("Ready");
});

test("a document waiting for review keeps Documents next, with a link straight to it", () => {
  const waiting = doc("bank_profit_certificate", "needs_review");
  const { documents, tax } = byKey([
    doc("salary_certificate", "confirmed"),
    waiting,
  ]);
  expect(documents.state).toBe("next");
  expect(documents.detail).toBe("1 confirmed, 1 to review");
  expect(documents.action).toEqual({
    to: `/documents/${waiting.id}`,
    text: "Review the next document",
  });
  // A confirmed salary certificate already lets the tax be worked out.
  expect(tax.state).toBe("todo");
  expect(tax.detail).toBe("Ready");
});

test("failed documents are counted but don't hold the step back", () => {
  const { documents, tax } = byKey([
    doc("salary_certificate", "confirmed"),
    doc("bank_profit_certificate", "failed"),
  ]);
  expect(documents.detail).toBe("1 confirmed, 1 failed");
  expect(documents.state).toBe("done");
  expect(tax.state).toBe("next");
});

test("documents still being read count as neither done nor to review", () => {
  const { documents } = byKey([
    doc("salary_certificate", "uploaded"),
    doc("salary_certificate", "extracting"),
  ]);
  expect(documents.detail).toBe("2 being read");
  expect(documents.state).toBe("next");
  expect(documents.action.text).toBe("Upload documents");
});

test("a confirmed bank certificate alone doesn't make Tax ready", () => {
  const { documents, tax } = byKey([
    doc("bank_profit_certificate", "confirmed"),
  ]);
  expect(documents.state).toBe("next");
  expect(tax.detail).toBe("Needs a confirmed salary certificate");
});

test("only the profile's tax year counts", () => {
  const { documents, tax } = byKey([
    doc("salary_certificate", "confirmed", "2024-25"),
    doc("salary_certificate", "needs_review", "2024-25"),
  ]);
  expect(documents.detail).toBe("None yet");
  expect(documents.state).toBe("next");
  expect(tax.detail).toBe("Needs a confirmed salary certificate");
});

test("while the documents are unknown, nothing about them is guessed", () => {
  const { profile, documents, tax, wealth } = byKey(null);
  expect(profile.state).toBe("done");
  for (const step of [documents, tax, wealth]) {
    expect(step.state).toBe("todo");
    expect(step.detail).toBeNull();
  }
});
