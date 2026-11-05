/**
 * Where to go after login or profile setup: the `next` page, but only within this app
 * (no open redirect). The browser's own URL parser decides, so tricks it would read as another
 * site, like `//evil.example`, `/\evil.example` or a tab inside the slashes, all go to "/".
 * The login page itself is never a destination, so a `next=/login` link can't loop.
 */
export function safeNext(next: string | null): string {
  if (!next || !next.startsWith("/")) {
    return "/";
  }
  const origin = window.location.origin;
  const url = new URL(next, origin);
  if (url.origin !== origin || url.pathname === "/login") {
    return "/";
  }
  return url.pathname + url.search + url.hash;
}
