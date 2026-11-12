import { vi } from "vitest";

/** A fake backend reply: status and JSON body (204 replies have no body). */
export type FakeReply = { status: number; body?: unknown };

/**
 * Handlers keyed by "METHOD /path", e.g. "POST /api/auth/login". A handler may return a
 * promise, e.g. one that never settles to keep a request "in progress". The body is the
 * parsed JSON, or the FormData itself for a file upload.
 */
export type FakeRoutes = Record<
  string,
  (request: { body: unknown }) => FakeReply | Promise<FakeReply>
>;

/**
 * Replace global fetch with a fake backend. Unlisted requests fail the test loudly.
 * Returns the mock, so tests can check which requests were made.
 */
export function mockFetch(routes: FakeRoutes) {
  const fake = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const path = String(input);
    const handler = routes[`${method} ${path}`];
    if (!handler) {
      throw new Error(`Unexpected request in test: ${method} ${path}`);
    }
    const body =
      init?.body instanceof FormData
        ? init.body
        : init?.body
          ? JSON.parse(String(init.body))
          : undefined;
    const reply = await handler({ body });
    return new Response(
      reply.status === 204 ? null : JSON.stringify(reply.body ?? {}),
      {
        status: reply.status,
        headers: { "Content-Type": "application/json" },
      },
    );
  });
  vi.stubGlobal("fetch", fake);
  return fake;
}

/** A saved taxpayer profile, as GET /api/profile returns it (feature 002, US4). */
export const SAVED_PROFILE = {
  tax_year: "2025-26",
  on_atl: true,
  updated_at: "2026-11-05T10:00:00Z",
};

/** GET /api/profile for a user who has set up their profile. */
export const hasProfile = (): FakeReply => ({
  status: 200,
  body: { profile: SAVED_PROFILE, supported_tax_years: ["2025-26"] },
});

/** GET /api/profile for a user who hasn't set up their profile yet. */
export const noProfile = (): FakeReply => ({
  status: 200,
  body: { profile: null, supported_tax_years: ["2025-26"] },
});

/** GET /api/documents with nothing uploaded: Home asks for it (feature 001, User Story 6). */
export const noDocuments = (): FakeReply => ({ status: 200, body: [] });
