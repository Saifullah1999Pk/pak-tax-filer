import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { DocumentSummary } from "../api/documents";
import { hasProfile, mockFetch } from "../test/mockFetch";
import type { FakeRoutes } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// Protected home page and logout (task T024, FR-012, FR-013), and its filing checklist
// (feature 001, User Story 6, task T052; FR-028).

const ME = { status: 200, body: { email: "demo@example.com" } };
const NOT_LOGGED_IN = { status: 401, body: { detail: "Not logged in." } };
const NO_DOCUMENTS = () => ({ status: 200, body: [] });

const CONFIRMED_SALARY: DocumentSummary = {
  id: "doc-1",
  doc_type: "salary_certificate",
  tax_year: "2025-26",
  status: "confirmed",
  failure_reason: null,
  media_type: "application/pdf",
  page_count: 1,
  created_at: "2026-11-05T10:00:00Z",
  confirmed_at: "2026-11-05T10:05:00Z",
};

/** A logged-in user with a profile; `routes` adds to or replaces the defaults. */
function loggedIn(routes: FakeRoutes = {}) {
  return mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "GET /api/documents": NO_DOCUMENTS,
    ...routes,
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test("a logged-out visitor is sent to the login page", async () => {
  mockFetch({ "GET /api/auth/me": () => NOT_LOGGED_IN });
  renderApp("/");

  await screen.findByRole("heading", { name: /log in/i });
});

test("a logged-in user sees their email and a logout button", async () => {
  loggedIn();
  renderApp("/");

  await screen.findByText(/logged in as demo@example\.com/i);
  screen.getByRole("button", { name: /log out/i });
  expect(screen.getByRole("link", { name: "Tax" }).getAttribute("href")).toBe(
    "/tax",
  );
});

test("logging out returns to the login page", async () => {
  let loggedInNow = true;
  mockFetch({
    "GET /api/auth/me": () => (loggedInNow ? ME : NOT_LOGGED_IN),
    "GET /api/profile": hasProfile,
    "GET /api/documents": NO_DOCUMENTS,
    "POST /api/auth/logout": () => {
      loggedInNow = false;
      return { status: 204 };
    },
  });
  renderApp("/");

  fireEvent.click(await screen.findByRole("button", { name: /log out/i }));

  await screen.findByRole("heading", { name: /log in/i });
});

test("a session that ended elsewhere sends the user to login with a message", async () => {
  // The app's first check finds a session; it has ended by the time the page asks again.
  let calls = 0;
  loggedIn({
    "GET /api/auth/me": () => (++calls === 1 ? ME : NOT_LOGGED_IN),
  });
  renderApp("/");

  await screen.findByText(/your session has ended, please log in again\./i);
  screen.getByRole("heading", { name: /log in/i });
});

test("logging out really ends the session on the server", async () => {
  let loggedInNow = true;
  const fake = mockFetch({
    "GET /api/auth/me": () => (loggedInNow ? ME : NOT_LOGGED_IN),
    "GET /api/profile": hasProfile,
    "GET /api/documents": NO_DOCUMENTS,
    "POST /api/auth/logout": () => {
      loggedInNow = false;
      return { status: 204 };
    },
  });
  renderApp("/");

  fireEvent.click(await screen.findByRole("button", { name: /log out/i }));
  await screen.findByRole("heading", { name: /log in/i });

  const logouts = fake.mock.calls.filter(
    ([url, init]) =>
      String(url) === "/api/auth/logout" && init?.method === "POST",
  );
  expect(logouts).toHaveLength(1);
});

test("a failed logout says so instead of pretending it worked", async () => {
  loggedIn({
    "POST /api/auth/logout": () => ({
      status: 500,
      body: { detail: "Server error." },
    }),
  });
  renderApp("/");

  fireEvent.click(await screen.findByRole("button", { name: /log out/i }));

  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Couldn't log out, try again.",
  );
  screen.getByText(/logged in as demo@example\.com/i);
});

test("a logged-out visitor sees no 'session ended' message", async () => {
  mockFetch({ "GET /api/auth/me": () => NOT_LOGGED_IN });
  renderApp("/");

  await screen.findByRole("heading", { name: /log in/i });
  expect(screen.queryByText(/session has ended/i)).toBeNull();
});

// The filing checklist (task T052).

/** The checklist's steps, once the documents step shows `detail`. */
async function stepsShowing(detail: string) {
  await screen.findByText(detail);
  const list = screen.getByRole("list", { name: /your steps/i });
  return within(list).getAllByRole("listitem");
}

test("Home lists the four filing steps in order, each with its action", async () => {
  loggedIn();
  renderApp("/");

  const items = await stepsShowing("None yet");
  expect(items).toHaveLength(4);
  within(items[0]).getByRole("heading", { name: /profile/i });
  within(items[0]).getByText("Tax year 2025-26, on the ATL");
  expect(
    within(items[0])
      .getByRole("link", { name: "Edit profile" })
      .getAttribute("href"),
  ).toBe("/profile");
  within(items[1]).getByRole("heading", { name: /documents/i });
  within(items[2]).getByRole("heading", { name: /tax/i });
  within(items[3]).getByRole("heading", { name: /wealth statement/i });
  expect(
    within(items[3])
      .getByRole("link", { name: "Open wealth statement" })
      .getAttribute("href"),
  ).toBe("/wealth");
});

test("with no documents, Documents is the next step", async () => {
  loggedIn();
  renderApp("/");

  const items = await stepsShowing("None yet");
  within(items[0]).getByText("Done");
  expect(items[1].getAttribute("aria-current")).toBe("step");
  within(items[1]).getByText("Next");
  within(items[1]).getByText("None yet");
  within(items[1]).getByRole("link", { name: "Upload documents" });
  within(items[2]).getByText("Needs a confirmed salary certificate");
  within(items[3]).getByText("Needs a confirmed salary certificate");
  expect(screen.getAllByText("Next")).toHaveLength(1);
});

test("with a confirmed salary certificate, Tax is the next step", async () => {
  loggedIn({
    "GET /api/documents": () => ({ status: 200, body: [CONFIRMED_SALARY] }),
  });
  renderApp("/");

  const items = await stepsShowing("1 confirmed");
  within(items[1]).getByText("Done");
  expect(items[2].getAttribute("aria-current")).toBe("step");
  within(items[2]).getByText("Ready");
  expect(
    within(items[2])
      .getByRole("link", { name: "See your tax" })
      .getAttribute("href"),
  ).toBe("/tax");
});

test("if the documents can't be loaded, Home says so, guesses nothing and can retry", async () => {
  let failing = true;
  loggedIn({
    "GET /api/documents": () =>
      failing
        ? { status: 500, body: { detail: "Server error." } }
        : { status: 200, body: [CONFIRMED_SALARY] },
  });
  renderApp("/");

  expect((await screen.findByRole("alert")).textContent).toMatch(
    /couldn't load your documents/i,
  );
  expect(screen.queryByText("Next")).toBeNull();
  expect(screen.queryByText("Ready")).toBeNull();
  expect(
    screen.queryByText(/needs a confirmed salary certificate/i),
  ).toBeNull();

  failing = false;
  fireEvent.click(screen.getByRole("button", { name: /try again/i }));

  await screen.findByText("1 confirmed");
  expect(screen.queryByRole("alert")).toBeNull();
});

// Feature 001, User Story 6, task T059 (FR-032): the top band names the next step. There is no
// step count: Tax and Wealth are never marked done, so a count could never reach the end.

/** The whole "Next step: ..." line (its label is a separate element inside it). */
const nextStepLine = (_: string, element: Element | null) =>
  element?.tagName === "P" &&
  (element.textContent ?? "").startsWith("Next step:");

test("the top band names the next step", async () => {
  loggedIn({
    "GET /api/documents": () => ({ status: 200, body: [CONFIRMED_SALARY] }),
  });
  renderApp("/");

  const band = await screen.findByText(nextStepLine);
  expect(band.textContent).toBe("Next step: See your tax");
  expect(screen.queryByRole("progressbar")).toBeNull();
});

test("with no documents, the band says to upload them", async () => {
  loggedIn();
  renderApp("/");

  const band = await screen.findByText(nextStepLine);
  expect(band.textContent).toBe("Next step: Upload documents");
});

test("no next step is named while the documents are unknown", async () => {
  loggedIn({
    "GET /api/documents": () => ({
      status: 500,
      body: { detail: "Server error." },
    }),
  });
  renderApp("/");

  await screen.findByRole("alert");
  expect(screen.queryByText(/next step:/i)).toBeNull();
});

test("while the documents load, Home says so and names no next step yet", async () => {
  loggedIn({ "GET /api/documents": () => new Promise(() => {}) });
  renderApp("/");

  await screen.findByText("Loading your documents…");
  expect(screen.queryByText(/next step:/i)).toBeNull();
});
