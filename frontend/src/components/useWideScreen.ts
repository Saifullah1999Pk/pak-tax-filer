import { useSyncExternalStore } from "react";

// Computer or phone layout (feature 006, task T035): the navigation renders one layout at a time,
// so the page never holds two menus. The same 720 px line as the CSS.

const QUERY = "(min-width: 720px)";

function subscribe(onChange: () => void): () => void {
  if (typeof window.matchMedia !== "function") {
    return () => {};
  }
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

/** True from 720 px wide; also true where `matchMedia` doesn't exist (tests, old browsers). */
const isWide = () =>
  typeof window.matchMedia !== "function" || window.matchMedia(QUERY).matches;

export function useWideScreen(): boolean {
  return useSyncExternalStore(subscribe, isWide, () => true);
}
