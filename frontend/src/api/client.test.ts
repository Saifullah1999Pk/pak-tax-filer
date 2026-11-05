import { afterEach, expect, test, vi } from "vitest";
import { apiFetch } from "./client";

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
