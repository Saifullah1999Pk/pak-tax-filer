import { fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import {
  hasProfile,
  mockFetch,
  noDocuments,
  noProfile,
} from "../test/mockFetch";
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

/** The field is marked invalid and points at the error message, and no other field is. */
function expectInvalid(label: RegExp, errorId: string) {
  for (const field of [/email/i, /^password$/i, /confirm password/i]) {
    const input = screen.getByLabelText(field);
    const isIt = field.source === label.source;
    expect(input.getAttribute("aria-invalid")).toBe(isIt ? "true" : "false");
    expect(input.getAttribute("aria-describedby") ?? "").toSatisfy(
      (ids: string) => ids.split(" ").includes(errorId) === isIt,
    );
  }
}

function fillIn(email: string, password: string, confirm: string) {
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: email },
  });
  fireEvent.change(screen.getByLabelText(/^password$/i), {
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
  const password = screen.getByLabelText(/^password$/i);
  expect(password.getAttribute("aria-describedby")).toContain(
    "signup-password-hint",
  );
  screen.getByText(/at least 8 characters/i);
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
  expectInvalid(/confirm password/i, alert.id);
  expect(fetch).toHaveBeenCalledTimes(1); // only the first "who am I"
});

test("a successful sign-up logs in and goes to the profile setup step", async () => {
  let signedUp = false;
  const fetch = mockFetch({
    "GET /api/auth/me": () =>
      signedUp
        ? { status: 200, body: { email: "new@example.com" } }
        : { status: 401, body: { detail: "Not logged in." } },
    "GET /api/documents": noDocuments,
    "GET /api/profile": noProfile,
    "POST /api/auth/signup": () => {
      signedUp = true;
      return { status: 201, body: { email: "new@example.com" } };
    },
  });
  renderApp("/signup", { showLocation: true });

  await screen.findByRole("heading", { name: /create an account/i });
  fillIn("new@example.com", "new-pass-123", "new-pass-123");

  await screen.findByRole("heading", { name: /set up your profile/i });
  // Straight to /profile, not "/" bounced there by RequireProfile (which adds ?next=).
  screen.getByText("Location: /profile");
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
  expectInvalid(/email/i, alert.id);
});

test("a password the server refuses as too short shows its message on that field", async () => {
  mockFetch({
    ...LOGGED_OUT,
    "POST /api/auth/signup": () => ({
      status: 422,
      body: { detail: "Password must be at least 8 characters." },
    }),
  });
  renderApp("/signup");

  await screen.findByRole("heading", { name: /create an account/i });
  fillIn("new@example.com", "short", "short");

  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toBe("Password must be at least 8 characters.");
  expectInvalid(/^password$/i, alert.id);
});

test("fixing the passwords clears the mismatch message", async () => {
  mockFetch(LOGGED_OUT);
  renderApp("/signup");

  await screen.findByRole("heading", { name: /create an account/i });
  fillIn("new@example.com", "new-pass-123", "new-pass-124");
  await screen.findByRole("alert");

  fireEvent.change(screen.getByLabelText(/confirm password/i), {
    target: { value: "new-pass-123" },
  });

  expect(screen.queryByRole("alert")).toBeNull();
});

test("a logged-in visitor goes to the home page", async () => {
  mockFetch({
    "GET /api/auth/me": () => ({
      status: 200,
      body: { email: "demo@example.com" },
    }),
    "GET /api/documents": noDocuments,
    "GET /api/profile": hasProfile,
  });
  renderApp("/signup");

  await screen.findByText(/logged in as demo@example\.com/i);
});
