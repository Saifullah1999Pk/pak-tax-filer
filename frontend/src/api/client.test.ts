import { afterEach, expect, test, vi } from "vitest";
import { apiFetch, apiUpload } from "./client";

// The API helper (frontend review L5).

afterEach(() => {
  vi.unstubAllGlobals();
});

test("a successful reply that isn't JSON is an error, not an empty success", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response("<html>proxy error page</html>", { status: 200 }),
    ),
  );

  await expect(apiFetch("/api/auth/me")).rejects.toThrow();
});

test("an upload is sent as multipart form data, not JSON, and refusals carry the server's message", async () => {
  const fake = vi.fn(
    async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify({ detail: "The file is over 10 MB." }), {
        status: 413,
        headers: { "Content-Type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fake);
  const form = new FormData();
  form.append("doc_type", "salary_certificate");

  await expect(apiUpload("/api/documents", form)).rejects.toThrow(
    "The file is over 10 MB.",
  );

  const init = fake.mock.calls[0][1];
  expect(init?.method).toBe("POST");
  expect(init?.body).toBe(form);
  // The browser must set the multipart boundary itself, so no Content-Type is given.
  expect(new Headers(init?.headers).get("Content-Type")).toBeNull();
});
