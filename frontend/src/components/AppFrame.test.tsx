import { screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { hasProfile, mockFetch, noProfile } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// The shared app frame (feature 001, User Story 6, task T050; FR-027).

const ME = { status: 200, body: { email: "demo@example.com" } };
const LOGGED_OUT = {
  "GET /api/auth/me": () => ({
    status: 401,
    body: { detail: "Not logged in." },
  }),
};
const LOGGED_IN = {
  "GET /api/auth/me": () => ME,
  "GET /api/profile": hasProfile,
  "GET /api/documents": () => ({ status: 200, body: [] }),
};

afterEach(() => {
  vi.unstubAllGlobals();
});

test("a logged-in page has the header: app name home, the tax year and Log out", async () => {
  mockFetch(LOGGED_IN);
  renderApp("/documents");

  const banner = await screen.findByRole("banner");
  expect(
    within(banner)
      .getByRole("link", { name: /paktaxfiler/i })
      .getAttribute("href"),
  ).toBe("/");
  // "Tax year" is hidden on phones but still read out, so it is its own element.
  within(banner).getByText(
    (_, element) =>
      element?.tagName === "P" && element.textContent === "Tax year 2025-26",
  );
  within(banner).getByRole("button", { name: /log out/i });
});

test("one navigation lists the five pages and marks the current one", async () => {
  mockFetch(LOGGED_IN);
  renderApp("/documents");

  const nav = await screen.findByRole("navigation", { name: /main/i });
  const links = within(nav).getAllByRole("link");
  expect(links.map((link) => link.textContent)).toEqual([
    "Home",
    "Documents",
    "Tax",
    "Wealth statement",
    "Profile",
  ]);
  expect(links.map((link) => link.getAttribute("href"))).toEqual([
    "/",
    "/documents",
    "/tax",
    "/wealth",
    "/profile",
  ]);
  const current = within(nav).getByRole("link", { current: "page" });
  expect(current.textContent).toBe("Documents");
  expect(screen.getAllByRole("navigation", { name: /main/i })).toHaveLength(1);
});

test("'Skip to content' is the first link and points at the page content", async () => {
  mockFetch(LOGGED_IN);
  renderApp("/documents");

  await screen.findByRole("navigation", { name: /main/i });
  const first = screen.getAllByRole("link")[0];
  expect(first.textContent).toBe("Skip to content");
  const target = first.getAttribute("href")?.slice(1) ?? "";
  expect(document.getElementById(target)).not.toBeNull();
});

test.each(["/login", "/signup", "/no-such-page"])(
  "%s has no navigation",
  async (path) => {
    mockFetch(LOGGED_OUT);
    renderApp(path);

    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("navigation", { name: /main/i })).toBeNull();
  },
);

test("first-time profile setup has no navigation, but can log out", async () => {
  mockFetch({ "GET /api/auth/me": () => ME, "GET /api/profile": noProfile });
  renderApp("/profile");

  await screen.findByRole("heading", { name: /set up your profile/i });
  expect(screen.queryByRole("navigation", { name: /main/i })).toBeNull();
  expect(screen.getAllByRole("button", { name: /log out/i })).toHaveLength(1);
});

test("editing the profile has the full frame, with one Log out", async () => {
  mockFetch(LOGGED_IN);
  renderApp("/profile");

  await screen.findByRole("heading", { name: /your profile/i });
  const nav = screen.getByRole("navigation", { name: /main/i });
  expect(within(nav).getByRole("link", { current: "page" }).textContent).toBe(
    "Profile",
  );
  expect(screen.getAllByRole("button", { name: /log out/i })).toHaveLength(1);
});

test("pages no longer carry their own Home link", async () => {
  mockFetch({
    ...LOGGED_IN,
    "GET /api/tax/2025-26": () => new Promise(() => {}),
  });
  renderApp("/tax");

  await screen.findByRole("heading", { name: /your tax for 2025-26/i });
  const main = screen.getByRole("main");
  expect(within(main).queryByRole("link", { name: "Home" })).toBeNull();
});
