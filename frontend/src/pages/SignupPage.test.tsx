import { fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { hasProfile, mockFetch, noProfile } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// Sign-up page, per specs/002-auth-foundation/contracts/cli-and-ui.md (task T049, FR-024 to
// FR-027).

const LOGGED_OUT = {
  "GET /api/auth/me": () => ({
    status: 401,
    body: { detail: "Not logged in." },
  }),
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function fillIn(email: string, password: string, confirm: string) {
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: email },
  });
  fireEvent.change(screen.getByLabelText(/^password/i), {
    target: { value: password },
  });
  fireEvent.change(screen.getByLabelText(/confirm password/i), {
    target: { value: confirm },
  });
  fireEvent.click(screen.getByRole("button", { name: /create account/i }));
}

test("shows the fields, the demo notice and a link to log in", async () => {
  mockFetch(LOGGED_OUT);
  renderApp("/signup");

  await screen.findByRole("heading", { name: /create an account/i });
  screen.getByLabelText(/email/i);
  screen.getByLabelText(/^password/i);
  screen.getByLabelText(/confirm password/i);
  screen.getByText(/demo data only/i);
  expect(
    screen.getByRole("link", { name: /log in/i }).getAttribute("href"),
  ).toBe("/login");
});

test("passwords that don't match are refused without asking the server", async () => {
  const fetch = mockFetch(LOGGED_OUT);
  renderApp("/signup");

  await screen.findByRole("heading", { name: /create an account/i });
  fillIn("new@example.com", "new-pass-123", "new-pass-124");

  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toBe("The passwords don't match.");
  expect(fetch).toHaveBeenCalledTimes(1); // only the first "who am I"
});

test("a successful sign-up logs in and goes to the profile setup step", async () => {
  let signedUp = false;
  const fetch = mockFetch({
    "GET /api/auth/me": () =>
      signedUp
        ? { status: 200, body: { email: "new@example.com" } }
        : { status: 401, body: { detail: "Not logged in." } },
    "GET /api/profile": noProfile,
    "POST /api/auth/signup": () => {
      signedUp = true;
      return { status: 201, body: { email: "new@example.com" } };
    },
  });
  renderApp("/signup");

  await screen.findByRole("heading", { name: /create an account/i });
  fillIn("new@example.com", "new-pass-123", "new-pass-123");

  await screen.findByRole("heading", { name: /set up your profile/i });
  expect(fetch).toHaveBeenCalledWith(
    "/api/auth/signup",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        email: "new@example.com",
        password: "new-pass-123",
      }),
    }),
  );
});

test("an email that already has an account shows the server's message", async () => {
  mockFetch({
    ...LOGGED_OUT,
    "POST /api/auth/signup": () => ({
      status: 409,
      body: {
        detail: "An account with this email already exists. Log in instead.",
      },
    }),
  });
  renderApp("/signup");

  await screen.findByRole("heading", { name: /create an account/i });
  fillIn("demo@example.com", "new-pass-123", "new-pass-123");

  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toBe(
    "An account with this email already exists. Log in instead.",
  );
});

test("a logged-in visitor goes to the home page", async () => {
  mockFetch({
    "GET /api/auth/me": () => ({
      status: 200,
      body: { email: "demo@example.com" },
    }),
    "GET /api/profile": hasProfile,
  });
  renderApp("/signup");

  await screen.findByText(/logged in as demo@example\.com/i);
});

test("the login page links to sign-up", async () => {
  mockFetch(LOGGED_OUT);
  renderApp("/login");

  const link = await screen.findByRole("link", { name: /create an account/i });
  expect(link.getAttribute("href")).toBe("/signup");
});
