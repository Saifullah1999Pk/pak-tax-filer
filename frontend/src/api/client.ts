// The one place the frontend calls the backend (feature 002, task T025, research R9).
// JSON in and out, the session cookie sent along, and a 401 treated as "session ended".

/** An error reply from the API, carrying its status and the server's `detail` message. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

let onSessionEnded: () => void = () => {};

/** Register what happens when a request finds the session has ended (set by AuthContext). */
export function setSessionEndedHandler(handler: () => void): void {
  onSessionEnded = handler;
}

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Don't treat a 401 as "session ended" (login itself, and the first "who am I" check). */
  allowUnauthenticated?: boolean;
};

/** Call the backend; resolves to the parsed JSON body (or undefined for 204). */
export async function apiFetch<T>(
  path: string,
  options: Options = {},
): Promise<T> {
  const { method = "GET", body, allowUnauthenticated = false } = options;
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    // State-changing requests always send JSON (the backend refuses anything else).
    body: method === "GET" ? undefined : JSON.stringify(body ?? {}),
  });

  if (response.status === 204) {
    return undefined as T;
  }
  const data: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !allowUnauthenticated) {
      onSessionEnded();
    }
    const detail =
      typeof data === "object" &&
      data !== null &&
      "detail" in data &&
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status}).`;
    throw new ApiError(response.status, detail);
  }
  return data as T;
}
