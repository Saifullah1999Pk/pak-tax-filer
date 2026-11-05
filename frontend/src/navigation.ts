/**
 * Where to go after login or profile setup: the `next` page, but only within this app.
 * A crafted link like `?next=//evil.example` goes to "/" instead (no open redirect).
 */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}
