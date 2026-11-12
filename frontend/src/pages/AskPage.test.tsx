import {
  act,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { AskResult } from "../api/ask";
import { hasProfile, mockFetch, noProfile } from "../test/mockFetch";
import type { FakeReply } from "../test/mockFetch";
import { renderApp } from "../test/renderApp";

// The tax assistant, per specs/006-rag-mcp/contracts/ask-and-tokens-api.md (tasks T014, T018).
// The page shows what the backend checked and returned; it writes no answer text itself.

const ME = { status: 200, body: { email: "demo@example.com" } };
const LABEL = "Not yet reviewed by a tax practitioner. Not tax advice.";

const ANSWERED: AskResult = {
  status: "answered",
  answer: "Your employer deducts tax from your salary at the average rate.",
  citations: [
    {
      title: "Income Tax Ordinance, 2001",
      kind: "law",
      location: "§149(1)",
      page: 327,
    },
    {
      title: "Normal Income Tax Return User Manual",
      kind: "guidance",
      location: "ch. 6.1",
      page: 11,
    },
  ],
  uncovered_part: null,
  tax_page_line: null,
  label: LABEL,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

/** The app at /ask, answering each question with the next reply (or never, if "pending"). */
function showAsk(...replies: (Partial<AskResult> | "pending")[]) {
  const queue = [...replies];
  return mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "POST /api/ask": () => {
      const next = queue.shift() ?? {};
      return next === "pending"
        ? new Promise<FakeReply>(() => {})
        : { status: 200, body: { ...ANSWERED, ...next } };
    },
  });
}

async function ask(question: string) {
  const box = await screen.findByLabelText("Your question");
  fireEvent.change(box, { target: { value: question } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
}

test("an answer shows its citations, telling law from guidance", async () => {
  const fetch = showAsk({});
  renderApp("/ask");

  await ask("Does my employer deduct tax?");

  expect(await screen.findByText(ANSWERED.answer)).toBeDefined();
  const sources = screen.getByRole("list", { name: "Sources" });
  const [law, guidance] = within(sources).getAllByRole("listitem");
  expect(law.textContent).toContain("Law");
  expect(law.textContent).toContain(
    "Income Tax Ordinance, 2001, §149(1), page 327",
  );
  expect(guidance.textContent).toContain("Guidance");
  expect(guidance.textContent).toContain("ch. 6.1, page 11");
  expect(fetch).toHaveBeenCalledWith(
    "/api/ask",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ question: "Does my employer deduct tax?" }),
    }),
  );
});

test("the practitioner label is visible before and after asking", async () => {
  showAsk({});
  renderApp("/ask");

  expect(await screen.findByText(LABEL)).toBeDefined();
  await ask("Does my employer deduct tax?");
  await screen.findByText(ANSWERED.answer);
  expect(screen.getByText(LABEL)).toBeDefined();
});

test("while waiting it shows its progress, and Ask can't be pressed again", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetch = showAsk("pending");
  renderApp("/ask");

  await ask("Does my employer deduct tax?");

  const status = screen.getByRole("status");
  expect(status.textContent).toContain("Searching the FBR texts…");
  act(() => {
    vi.advanceTimersByTime(1500);
  });
  expect(status.textContent).toContain("Writing a cited answer…");
  const button = screen.getByRole("button", { name: "Ask" });
  expect(button.getAttribute("aria-disabled")).toBe("true");
  fireEvent.click(button);
  expect(fetch.mock.calls.filter(([path]) => path === "/api/ask")).toHaveLength(
    1,
  );
  vi.useRealTimers();
});

test("once the answer arrives the progress clears and Ask works again", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  showAsk({});
  renderApp("/ask");

  await ask("Does my employer deduct tax?");
  await screen.findByText(ANSWERED.answer);
  act(() => {
    vi.advanceTimersByTime(3000);
  });

  expect(screen.getByRole("status").textContent).toBe("");
  expect(
    screen.getByRole("button", { name: "Ask" }).getAttribute("aria-disabled"),
  ).toBe("false");
  vi.useRealTimers();
});

test("focus moves to the answer when it arrives", async () => {
  showAsk({});
  renderApp("/ask");

  await ask("Does my employer deduct tax?");

  const heading = await screen.findByRole("heading", { name: "Answer" });
  await waitFor(() => expect(document.activeElement).toBe(heading));
});

test("a second question clears the first answer while it waits", async () => {
  showAsk({}, "pending");
  renderApp("/ask");

  await ask("Does my employer deduct tax?");
  await screen.findByText(ANSWERED.answer);
  await ask("How is bank profit taxed?");

  await waitFor(() => expect(screen.queryByText(ANSWERED.answer)).toBeNull());
});

test("without a profile, Ask sends the user to set one up first", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": noProfile,
  });
  renderApp("/ask", { showLocation: true });

  expect(
    await screen.findByText("Location: /profile?next=%2Fask"),
  ).toBeDefined();
});

test("a network failure says so", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "POST /api/ask": () => Promise.reject(new TypeError("Failed to fetch")),
  });
  renderApp("/ask");

  await ask("Does my employer deduct tax?");

  expect((await screen.findByRole("alert")).textContent).toContain(
    "Couldn't reach the tax assistant",
  );
});

test("the label shows even if a reply's label is empty", async () => {
  showAsk({ label: "" });
  renderApp("/ask");

  await ask("Does my employer deduct tax?");
  await screen.findByText(ANSWERED.answer);

  expect(screen.getByText(LABEL)).toBeDefined();
});

test("a blank question isn't sent", async () => {
  const fetch = showAsk({});
  renderApp("/ask");

  await ask("   ");

  expect(fetch.mock.calls.filter(([path]) => path === "/api/ask")).toHaveLength(
    0,
  );
});

test.each([
  [
    "not_covered",
    "I can only answer from the Income Tax Ordinance and FBR's return-filing manual, and they don't cover this.",
  ],
  ["limited", "Please try again later."],
  ["unavailable", "Please try again later."],
  [
    "daily_limit",
    "The tax assistant has reached today's limit; try again tomorrow.",
  ],
  ["not_ready", "The tax assistant isn't ready yet."],
] as const)(
  "a %s reply shows its message and no sources",
  async (status, message) => {
    showAsk({ status, answer: message, citations: [] });
    renderApp("/ask");

    await ask("What is the sales tax on cars?");

    expect(await screen.findByText(message)).toBeDefined();
    expect(screen.queryByRole("list", { name: "Sources" })).toBeNull();
    expect(screen.getByText(LABEL)).toBeDefined();
  },
);

test("a partial answer names the part its sources don't cover", async () => {
  showAsk({ uncovered_part: "Rental income isn't covered by these sources." });
  renderApp("/ask");

  await ask("Is my salary and rent taxed?");

  expect(
    await screen.findByText("Rental income isn't covered by these sources."),
  ).toBeDefined();
});

test("asking for one's own tax links to the Tax page", async () => {
  showAsk({
    tax_page_line: "To see your own calculated tax, open the Tax page.",
  });
  renderApp("/ask", { showLocation: true });

  await ask("How much tax do I owe?");

  fireEvent.click(
    await screen.findByRole("link", { name: "open the Tax page" }),
  );
  expect(await screen.findByText("Location: /tax")).toBeDefined();
});

test("an error reply shows the server's message", async () => {
  mockFetch({
    "GET /api/auth/me": () => ME,
    "GET /api/profile": hasProfile,
    "POST /api/ask": () => ({
      status: 422,
      body: { detail: "Ask a question of up to 1,000 characters." },
    }),
  });
  renderApp("/ask");

  await ask("x");

  expect((await screen.findByRole("alert")).textContent).toContain(
    "Ask a question of up to 1,000 characters.",
  );
});

test("a refused question about one's own tax still links to the Tax page", async () => {
  showAsk({
    status: "not_covered",
    answer:
      "I can only answer from the Income Tax Ordinance and FBR's return-filing manual, and they don't cover this.",
    citations: [],
    tax_page_line: "To see your own calculated tax, open the Tax page.",
  });
  renderApp("/ask");

  await ask("How much tax do I owe?");

  expect(
    await screen.findByRole("link", { name: "open the Tax page" }),
  ).toBeDefined();
});
